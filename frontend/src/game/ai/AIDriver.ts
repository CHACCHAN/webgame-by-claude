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
}

export const AI_PROFILES: Record<AILevel, AIProfile> = {
  rookie: { level: 'rookie', name: '森 健太', title: 'ROOKIE / 走り始めた新人', gripUse: 0.55, brakeUse: 0.46, sloppiness: 0.45, catchUp: 0.35 },
  ace: { level: 'ace', name: '高嶺 遼', title: 'LOCAL ACE / 朧峠の地元最速', gripUse: 0.72, brakeUse: 0.64, sloppiness: 0.3, catchUp: 0.25 },
  legend: { level: 'legend', name: '朧', title: 'LEGEND / 夜を走る幽霊', gripUse: 0.95, brakeUse: 0.86, sloppiness: 0.1, catchUp: 0.3 },
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
  /** extra lateral offset used to go around another car */
  private avoid = 0;
  /** progress (m) of a car to race against, for rubber banding / avoidance */
  opponent: { s: number; lateral: number } | null = null;
  s = 0;

  constructor(track: Track, line: RacingLine, profile: AIProfile, seed = 7) {
    this.track = track;
    this.line = line;
    this.profile = profile;
    this.random = rng(seed);
    this.wobblePhase = this.random() * 100;
    this.speeds = new Float32Array(0);
  }

  /** Must be called once the car spec is known. */
  calibrate(vehicle: VehicleSim) {
    vehicle.gripDriver = true;
    vehicle.assist = 2;
    const grip = Math.min(vehicle.spec.gripFront, vehicle.spec.gripRear) * 9.81;
    this.speeds = this.line.speedProfile(grip * this.profile.gripUse, grip * this.profile.brakeUse, 50, 62);
  }

  update(vehicle: VehicleSim, dt: number, out: VehicleInput): VehicleInput {
    const p = vehicle.position;
    this.proj = this.track.project(p.x, p.y, p.z, this.proj.index, this.proj);
    const s = this.proj.s;
    this.s = s;
    const speed = vehicle.forwardSpeed;

    // rubber band: a little faster when behind, a little slower when far ahead
    let speedScale = 1;
    if (this.opponent) {
      const gap = this.opponent.s - s; // >0 = opponent ahead
      speedScale += clamp(gap / 150, -1, 1) * 0.06 * this.profile.catchUp * 4;
      // overtaking / avoidance
      const lateralGap = this.opponent.lateral - this.proj.lateral;
      if (gap > 0 && gap < 18 && Math.abs(lateralGap) < 2.4) {
        this.avoid = clamp(this.avoid + (lateralGap > 0 ? -1 : 1) * dt * 3, -2.5, 2.5);
      } else this.avoid *= Math.exp(-dt * 0.8);
    }

    const look = 7 + Math.max(speed, 0) * 0.42;
    const ts = s + look;
    const wobble = Math.sin(this.wobblePhase + s / 37) * this.profile.sloppiness;
    const half = this.track.widthAt(ts) / 2 - 1.1;
    const lat = clamp(this.line.offsetAt(ts) + wobble + this.avoid, -half, half);
    this.track.pointAt(ts, lat, _target);

    // pure pursuit
    const dx = _target.x - p.x, dz = _target.z - p.z;
    const desired = Math.atan2(dx, dz);
    const heading = Math.atan2(vehicle.forward.x, vehicle.forward.z);
    const err = wrapAngle(desired - heading);
    // positive error = target to the left; steer input + = right
    let steer = clamp((-err * 2.6) / Math.max(0.35, 1 - Math.max(speed, 0) / 80), -1, 1);
    steer -= vehicle.yawRate * 0.04;
    out.steer = clamp(steer, -1, 1);

    // speed control
    const idx = Math.min(this.speeds.length - 1, Math.max(0, Math.round(s + Math.max(speed, 0) * 0.35)));
    let target = this.speeds[idx] * speedScale;
    // slow down if we're far off line or sliding a lot
    target *= 1 - clamp(Math.abs(vehicle.slipAngle) - 0.2, 0, 0.4);
    const diff = target - speed;
    if (diff < -1.5) {
      out.throttle = 0;
      out.brake = clamp(-diff / 6, 0.2, 1);
    } else {
      out.brake = 0;
      out.throttle = clamp(diff / 3 + 0.35, 0, 1);
    }
    out.handbrake = false;

    // unstick: back up if pinned against a wall
    if (Math.abs(speed) < 1 && out.throttle > 0.5) this.stuckTime += dt;
    else this.stuckTime = Math.max(0, this.stuckTime - dt);
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
