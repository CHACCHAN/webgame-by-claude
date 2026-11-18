import { jetEnvelope } from '../vehicle/jets';
import { Vector3 } from 'three';
import type { Track, TrackProjection } from '../track/Track';
import { clamp, rng, wrapAngle } from '../util/math';
import type { VehicleInput, VehicleSim } from '../vehicle/VehicleSim';
import { RacingLine } from './RacingLine';

export type AILevel = 'rookie' | 'ace' | 'legend';

export interface AIProfile {
  level: AILevel;
  name: string;
  title: string;
  /** usable lateral acceleration as a fraction of the car's grip */
  gripUse: number;
  brakeUse: number;
  /** random line wobble (m) */
  sloppiness: number;
  /** rubber band strength (0..1) */
  catchUp: number;
  /** 0..1: how firmly it closes the door on a car right behind it (side-by-side contact) */
  defend: number;
}

export const AI_PROFILES: Record<AILevel, AIProfile> = {
  rookie: { level: 'rookie', name: '森 健太', title: 'ROOKIE / 走り始めた新人', gripUse: 0.55, brakeUse: 0.46, sloppiness: 0.45, catchUp: 0.35, defend: 0 },
  ace: { level: 'ace', name: '高嶺 遼', title: 'LOCAL ACE / 朧峠の地元最速', gripUse: 0.72, brakeUse: 0.64, sloppiness: 0.3, catchUp: 0.25, defend: 0.6 },
  legend: { level: 'legend', name: '朧', title: 'LEGEND / 夜を走る幽霊', gripUse: 0.95, brakeUse: 0.86, sloppiness: 0.1, catchUp: 0.3, defend: 1 },
};

const _target = new Vector3();

/** Drives a VehicleSim along a racing line using pure pursuit + a speed profile. */
export class AIDriver {
  readonly track: Track;
  readonly line: RacingLine;
  readonly profile: AIProfile;
  private speeds: Float32Array;
  private proj: TrackProjection = { index: -1, s: 0, lateral: 0, height: 0 };
  private random: () => number;
  private wobblePhase: number;
  private stuckTime = 0;
  /** speed when it last counted as moving (the stuck check sees whether it speeds up since) */
  private stuckFrom = 0;
  /** extra lateral offset used to go around another car */
  private avoid = 0;
  /** progress (m), lateral offset and forward speed of a car to race against (rubber band, avoidance, no rear-ending) */
  opponent: { s: number; lateral: number; speed?: number } | null = null;
  s = 0;
  /** when set, steer for this lateral offset (m) instead of the racing line, e.g. to pull over after the finish */
  pullOver: number | null = null;
  /** seconds left on the blocking line (see `block`) */
  blocking = 0;

  constructor(track: Track, line: RacingLine, profile: AIProfile, seed = 7) {
    this.track = track;
    this.line = line;
    this.profile = profile;
    this.random = rng(seed);
    this.wobblePhase = this.random() * 100;
    this.speeds = new Float32Array(0);
  }

  /**
   * Take the line of the car behind for `seconds`: the one move the rival's mind (ai/RivalMind) can ask for. A rule,
   * not a manoeuvre of its own: while it lasts, and while that car is within 25 m behind, this driver puts itself in
   * front of it across the road (quicker and further than the standing `defend`), still inside the road's edges and
   * still at the speed its own line allows.
   */
  block(seconds: number) {
    this.blocking = Math.max(this.blocking, seconds);
  }

  private lastErr = 0;
  private errRate = 0;
  /** a fighter only: the sideways acceleration (m/s²) it plans with at a speed */
  private jetHolds: ((v: number) => number) | null = null;

  /** Must be called once the car spec is known. */
  calibrate(vehicle: VehicleSim) {
    vehicle.gripDriver = true;
    vehicle.assist = 2;
    const grip = Math.min(vehicle.spec.gripFront, vehicle.spec.gripRear) * vehicle.gripScale * 9.81;
    this.jetHolds = null;
    if (vehicle.spec.jet) {
      // a fighter: what its tyres hold falls as the wing takes the weight, and it stops by its drag more than by
      // its brakes; the engines go on pushing for seconds after the throttle is closed (a margin on the braking)
      const env = jetEnvelope(vehicle.spec), mu = grip / 9.81, p = this.profile;
      this.jetHolds = (v) => env.lat(v, mu) * p.gripUse * 0.6;
      this.speeds = this.line.speedProfile(0, 0, 50, this.track.design.aiTopSpeed ?? 62, {
        // (the nose wheel, an eighth of the weight, gives up first: a held turn settles at 0.7 of what the tyres'
        // friction says, `tools/jet-handling.ts`; the rest is the margin a driver keeps on a taxiway 23 m wide)
        lat: (v, g) => env.lat(v, mu * g) * p.gripUse * 0.6,
        brake: (v, g) => env.brake(v, mu * g) * p.brakeUse * 0.8,
      });
      return;
    }
    // the speed limit is the course's (62 m/s ≈ 223 km/h on the mountain passes; the autobahn lets everything run flat out)
    this.speeds = this.line.speedProfile(grip * this.profile.gripUse, grip * this.profile.brakeUse, 50, this.track.design.aiTopSpeed ?? 62);
  }

  update(vehicle: VehicleSim, dt: number, out: VehicleInput): VehicleInput {
    const p = vehicle.position;
    this.proj = this.track.project(p.x, p.y, p.z, this.proj.index, this.proj);
    const s = this.proj.s;
    this.s = s;
    const speed = vehicle.forwardSpeed;

    this.blocking = Math.max(0, this.blocking - dt);
    // rubber band: a little faster when behind, a little slower when far ahead
    let speedScale = 1;
    let speedCap = Infinity;
    if (this.opponent) {
      const gap = this.opponent.s - s; // >0 = opponent ahead
      speedScale += clamp(gap / 150, -1, 1) * 0.06 * this.profile.catchUp * 4;
      // overtaking / avoidance
      const lateralGap = this.opponent.lateral - this.proj.lateral;
      if (gap > 0 && gap < 18 && Math.abs(lateralGap) < 2.4) {
        this.avoid = clamp(this.avoid + (lateralGap > 0 ? -1 : 1) * dt * 3, -2.5, 2.5);
      }
      if (gap > 0 && gap < 40 && Math.abs(lateralGap) < 2.1 && this.opponent.speed !== undefined) {
        // the cars are solid: close up on the car ahead at a speed that still leaves a car length,
        // then pass once the avoidance offset has cleared it (a tap, not a rear-end crash)
        const other = Math.max(0, this.opponent.speed);
        const room = gap - 7 - Math.max(0, speed - other) * 0.4; // a car length plus reaction distance
        speedCap = other + Math.sqrt(2 * 4 * Math.max(0, room));
      } else if (this.blocking > 0 && gap < 0 && gap > -25) {
        // blocking: where the chaser is across the road, whatever the racing line says there
        const want = this.opponent.lateral - this.line.offsetAt(s + 7 + Math.max(speed, 0) * 0.42);
        this.avoid += (clamp(want, -6, 6) - this.avoid) * (1 - Math.exp(-dt * 4));
      } else if (gap < 0 && gap > -14 && Math.abs(lateralGap) < 3.5 && this.profile.defend > 0) {
        // defending: lean towards the side the chaser is trying to pass on, which leads to
        // door-to-door contact when the chaser commits
        const want = clamp(lateralGap, -1.6, 1.6) * this.profile.defend;
        this.avoid += (want - this.avoid) * (1 - Math.exp(-dt * 1.6));
      } else this.avoid *= Math.exp(-dt * 0.8);
    }

    // (a fighter answers its rudder slowly: it aims further down the road)
    const look = vehicle.spec.jet ? 14 + Math.max(speed, 0) * 1.1 : 7 + Math.max(speed, 0) * 0.42;
    const ts = s + look;
    const wobble = Math.sin(this.wobblePhase + s / 37) * this.profile.sloppiness;
    // (a fighter's main wheels are 2.75 m apart and its wing tips 13 m: it keeps further from the pavement's edge)
    const half = this.track.paveAt(ts) / 2 - (vehicle.spec.jet ? 3.5 : 1.1);
    const lat = clamp(this.pullOver ?? this.line.offsetAt(ts) + wobble + this.avoid, -half, half);
    this.track.pointAt(ts, lat, _target);

    // pure pursuit
    const dx = _target.x - p.x, dz = _target.z - p.z;
    const desired = Math.atan2(dx, dz);
    const heading = Math.atan2(vehicle.forward.x, vehicle.forward.z);
    const err = wrapAngle(desired - heading);
    // positive error = target to the left; steer input + = right
    let steer = clamp((-err * 2.6) / Math.max(0.35, 1 - Math.max(speed, 0) / 80), -1, 1);
    steer -= vehicle.yawRate * 0.04;
    // a fighter at speed is steered by its rudder: small, damped inputs (full rudder is a 14° skid)
    if (vehicle.spec.jet) {
      const lim = 1 - 0.5 * clamp((speed - 40) / 80, 0, 1);
      // (damped by how fast the nose is coming round onto the aim, not by the turn rate itself, which a bend needs)
      const rate = clamp(wrapAngle(err - this.lastErr) / Math.max(dt, 1e-3), -2, 2);
      this.errRate += (rate - this.errRate) * (1 - Math.exp(-dt * 12));
      this.lastErr = err;
      steer = clamp(-err * 3 - this.errRate * 0.8, -lim, lim);
    }
    out.steer = clamp(steer, -1, 1);

    // speed control
    // (a fighter's engines take seconds to run down: it looks that much further ahead)
    const idx = Math.min(this.speeds.length - 1, Math.max(0, Math.round(s + Math.max(speed, 0) * (vehicle.spec.jet ? 1.6 : 0.35))));
    let target = Math.min(this.speeds[idx] * speedScale, speedCap);
    // (and never faster than the place it is at allows: looking ahead only, it opened up in the middle of a bend)
    if (vehicle.spec.jet) target = Math.min(target, this.speeds[Math.min(this.speeds.length - 1, Math.max(0, Math.round(s)))] * speedScale);
    // (and never faster than it can turn onto the line it is aiming at: with a thrust near its weight it left a
    // taxi turn at three times the speed before its nose had come round, and went off the far side)
    // (only for a nose that is really off: a degree of wander at 800 km/h is not a turn to slow down for)
    const off = Math.abs(err) - 0.07;
    if (this.jetHolds && off > 0) target = Math.min(target, Math.sqrt(this.jetHolds(Math.max(speed, 0)) / ((2 * Math.sin(Math.min(off, 1.5))) / look)));
    // slow down if we're far off line or sliding a lot
    target *= 1 - clamp(Math.abs(vehicle.slipAngle) - 0.2, 0, 0.4);
    const diff = target - speed;
    if (this.jetHolds && diff < -0.4) {
      // (a fighter's idle thrust alone holds it above a taxi turn's speed: it brakes for a small excess too)
      out.throttle = 0;
      out.brake = clamp(-diff / 4, 0.1, 1);
    } else if (diff < -1.5) {
      out.throttle = 0;
      out.brake = clamp(-diff / 6, 0.2, 1);
    } else {
      out.brake = 0;
      out.throttle = clamp(diff / 3 + 0.35, 0, 1);
    }
    out.handbrake = false;

    // unstick: back up if pinned against a wall (a train slow off the mark, 1.7 km/h/s after its jerk-limited build-up,
    // is not stuck while it gathers speed)
    const stalled = Math.abs(speed) < 1 && out.throttle > 0.5;
    if (stalled && speed - this.stuckFrom > 0.15) {
      this.stuckTime = 0;
      this.stuckFrom = speed;
    } else if (stalled) this.stuckTime += dt;
    else {
      this.stuckTime = Math.max(0, this.stuckTime - dt);
      this.stuckFrom = speed;
    }
    if (this.stuckTime > 1.5) {
      out.throttle = 0;
      out.brake = 1;
      out.steer = -out.steer;
      if (this.stuckTime > 3.2) this.stuckTime = 0;
    }
    return out;
  }

  get needsRespawn() {
    return this.stuckTime > 3;
  }
}
