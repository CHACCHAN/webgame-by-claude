import { Quaternion, Vector3 } from 'three';
import type { NetState } from './codec';

/** A car's pose at one moment, as far as the packets tell. */
export interface TrackPose {
  position: Vector3;
  quaternion: Quaternion;
  /** m/s, world frame, per wall-clock second */
  velocity: Vector3;
  /** forward speed (m/s), front wheel steer (rad), brake flag, throttle and rpm share: from the nearest packet */
  speed: number;
  steer: number;
  brake: boolean;
  throttle: number;
  rpm: number;
  /** seconds past the newest packet (0: the moment lies between two packets) */
  ahead: number;
  /** a fighter's take-off (`NetState.dep`): 0 = on its wheels */
  depart: number;
}

export function newPose(): TrackPose {
  return { position: new Vector3(), quaternion: new Quaternion(), velocity: new Vector3(), speed: 0, steer: 0, brake: false, throttle: 0, rpm: 0, ahead: 0, depart: 0 };
}

interface Snap {
  /** the moment of the pose on the sender's clock (ms) */
  t: number;
  p: Vector3;
  q: Quaternion;
  vel: Vector3;
  acc: Vector3;
  /** angular velocity as a turning axis and a rate (rad/s) */
  axis: Vector3;
  turn: number;
  speed: number;
  st: NetState;
}

/** a car is carried on along its last known motion for this long (s) … */
export const COAST = 0.25;
/** … then slowed to a stop by here: a peer that fell silent must not drive on for ever */
export const COAST_END = 0.6;

/** Seconds of motion granted `dt` seconds past the newest packet, and the share of the speed left there. */
export function coast(dt: number): [number, number] {
  if (dt <= COAST) return [dt, 1];
  if (dt >= COAST_END) return [(COAST + COAST_END) / 2, 0];
  const u = (dt - COAST) / (COAST_END - COAST);
  return [COAST + (dt - COAST) * (1 - u / 2), 1 - u];
}

const _v = new Vector3(), _q = new Quaternion();
const FWD = new Vector3(0, 0, 1);

/**
 * One peer's car as a path through time, on the sender's clock: the packets kept in order, and the pose at any
 * moment. Between two packets it is a cubic through both positions with both velocities (Hermite), so the car
 * passes each packet at the speed and heading it really had; past the newest packet it is that packet's motion
 * carried on (velocity, acceleration, turning rate), for a limited time.
 */
export class PeerTrack {
  private snaps: Snap[] = [];

  get length() {
    return this.snaps.length;
  }

  get newest(): NetState | null {
    return this.snaps.length ? this.snaps[this.snaps.length - 1].st : null;
  }

  /** the newest pose's moment on the sender's clock (ms) */
  get newestTime() {
    return this.snaps.length ? this.snaps[this.snaps.length - 1].t : -Infinity;
  }

  clear() {
    this.snaps.length = 0;
  }

  /** Adds a packet; false when it is not newer than the newest (a late one: the path is already past it). */
  push(st: NetState) {
    const t = st.t - st.age;
    if (t <= this.newestTime) return false;
    const q = new Quaternion(st.q[0], st.q[1], st.q[2], st.q[3]);
    const vel = new Vector3(st.vel[0], st.vel[1], st.vel[2]);
    const axis = new Vector3(st.w[0], st.w[1], st.w[2]), turn = axis.length();
    if (turn > 1e-9) axis.divideScalar(turn);
    this.snaps.push({ t, p: new Vector3(st.p[0], st.p[1], st.p[2]), q, vel, acc: new Vector3(st.acc[0], st.acc[1], st.acc[2]), axis, turn, speed: vel.dot(_v.copy(FWD).applyQuaternion(q)), st });
    if (this.snaps.length > 64) this.snaps.splice(0, this.snaps.length - 64);
    return true;
  }

  /** The pose at `t` (ms, sender's clock). False while there is no packet. */
  sample(t: number, out: TrackPose) {
    const n = this.snaps.length;
    if (!n) return false;
    const last = this.snaps[n - 1];
    if (t >= last.t) return this.carryOn(last, (t - last.t) / 1000, out);
    let i = n - 1;
    while (i > 0 && this.snaps[i - 1].t > t) i--;
    if (i === 0) return this.carryOn(this.snaps[0], 0, out);
    const a = this.snaps[i - 1], b = this.snaps[i];
    // a respawn between the two: nothing was driven from one to the other
    if (a.st.ep !== b.st.ep) return this.carryOn(a, Math.min((t - a.t) / 1000, COAST), out);
    const d = (b.t - a.t) / 1000, u = (t - a.t) / (b.t - a.t);
    const u2 = u * u, u3 = u2 * u;
    out.position
      .copy(a.p).multiplyScalar(2 * u3 - 3 * u2 + 1)
      .addScaledVector(a.vel, (u3 - 2 * u2 + u) * d)
      .addScaledVector(b.p, -2 * u3 + 3 * u2)
      .addScaledVector(b.vel, (u3 - u2) * d);
    out.velocity
      .copy(a.p).multiplyScalar((6 * u2 - 6 * u) / d)
      .addScaledVector(a.vel, 3 * u2 - 4 * u + 1)
      .addScaledVector(b.p, (-6 * u2 + 6 * u) / d)
      .addScaledVector(b.vel, 3 * u2 - 2 * u);
    out.quaternion.slerpQuaternions(a.q, b.q, u);
    const near = u < 0.5 ? a : b;
    out.speed = a.speed + (b.speed - a.speed) * u;
    out.steer = a.st.st + (b.st.st - a.st.st) * u;
    out.brake = near.st.br === 1;
    out.throttle = near.st.th;
    out.rpm = near.st.rp;
    out.depart = near.st.dep ?? 0;
    out.ahead = 0;
    return true;
  }

  /** A packet's motion carried on for `dt` seconds. */
  private carryOn(s: Snap, dt: number, out: TrackPose) {
    const [h, keep] = coast(dt);
    // braking may bring the car to a stop, never turn it round: from the moment it would stand, it stands
    const along = s.acc.dot(s.vel);
    const stop = along < 0 ? s.vel.lengthSq() / -along : Infinity;
    const stands = stop < h, hm = stands ? stop : h;
    out.position.copy(s.p).addScaledVector(s.vel, hm).addScaledVector(s.acc, 0.5 * hm * hm);
    if (stands) out.velocity.set(0, 0, 0);
    else out.velocity.copy(s.vel).addScaledVector(s.acc, hm).multiplyScalar(keep);
    out.quaternion.copy(_q.setFromAxisAngle(s.axis, s.turn * hm)).multiply(s.q);
    out.speed = stands ? 0 : s.speed * keep;
    out.steer = s.st.st;
    out.brake = s.st.br === 1;
    out.throttle = s.st.th;
    out.rpm = s.st.rp;
    out.depart = s.st.dep ?? 0;
    out.ahead = dt;
    return true;
  }
}
