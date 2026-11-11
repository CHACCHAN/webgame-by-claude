// The netcode as it was before Phase G (commit 588ddb3), kept only so tools/net-replay.ts can print "before"
// numbers next to the current code's under the same network: the state the game sent (`Game.netState`, from a
// 80 ms interval timer), the receive side of `RemoteRacers` (push / stepProxies) and `ProxyCar.drive`, copied with
// their arithmetic unchanged. Nothing in the game imports this file.
import { Quaternion, Vector3 } from 'three';
import { GROUP_CAR, GROUP_PROXY, PHYSICS_DT, RAPIER, groups } from '../src/game/vehicle/PhysicsWorld';
import type { CarSpec } from '../src/game/vehicle/carSpecs';

export interface LegacyState {
  t: number;
  p: [number, number, number];
  q: [number, number, number, number];
  v: number;
  st: number;
  s: number;
  br: 0 | 1;
}

/** `Game.netState` as it was: the latest physics state, stamped with the time of sending. */
export function legacyState(now: number, p: Vector3, q: Quaternion, forwardSpeed: number, steer: number, s: number): LegacyState {
  const r = (v: number, k = 1000) => Math.round(v * k) / k;
  return { t: Math.round(now), p: [r(p.x), r(p.y), r(p.z)], q: [r(q.x, 1e4), r(q.y, 1e4), r(q.z, 1e4), r(q.w, 1e4)], v: r(forwardSpeed, 100), st: r(steer, 1e3), s: r(s, 10), br: 0 };
}

export const LEGACY_SEND_MS = 80;
const MAX_EXTRAPOLATION = 0.25;
const clamp = (v: number, a: number, b: number) => Math.min(b, Math.max(a, v));
const _b = new Vector3(), _qb = new Quaternion(), _vel = new Vector3();

/** One peer's car in the old `RemoteRacers`: the buffer, the "minimum delay" clock estimate, the stand-in's target. */
export class LegacyPeer {
  buf: LegacyState[] = [];
  offset = Infinity;
  /** seconds the newest state was carried on at the last step (for the statistics) */
  age = 0;

  push(st: LegacyState, now: number) {
    this.offset = Math.min(this.offset, now - st.t);
    const buf = this.buf;
    if (buf.length && st.t <= buf[buf.length - 1].t) return;
    buf.push(st);
    if (buf.length > 40) buf.splice(0, buf.length - 40);
  }

  /** `RemoteRacers.stepProxies` for one car. */
  step(proxy: LegacyProxyCar, now: number, localCar: Vector3 | null) {
    const buf = this.buf;
    proxy.updateGhost(now, localCar);
    if (!buf.length) return;
    const b = buf[buf.length - 1], a = buf.length > 1 ? buf[buf.length - 2] : null;
    if (a && b.t > a.t) _vel.set((b.p[0] - a.p[0]) / ((b.t - a.t) / 1000), (b.p[1] - a.p[1]) / ((b.t - a.t) / 1000), (b.p[2] - a.p[2]) / ((b.t - a.t) / 1000));
    else _vel.set(0, 0, 0);
    this.age = clamp((now - (b.t + this.offset)) / 1000, 0, MAX_EXTRAPOLATION);
    _b.fromArray(b.p).addScaledVector(_vel, this.age);
    _qb.fromArray(b.q);
    proxy.drive(_b, _qb, _vel, now);
  }

  /** `RemoteRacers.update`: "let the latency estimate creep up slowly so clock drift cannot freeze a car". */
  frame(dt: number) {
    if (this.buf.length) this.offset += dt * 5;
  }
}

const _p = new Vector3(), _q = new Quaternion();
const BLEND = 1 - Math.exp(-PHYSICS_DT / 0.15);

/** `ProxyCar` as it was. */
export class LegacyProxyCar {
  readonly body: RAPIER.RigidBody;
  readonly collider: RAPIER.Collider;
  private ghostUntil = 0;

  constructor(world: RAPIER.World, spec: CarSpec, position: Vector3, quaternion: Quaternion) {
    this.body = world.createRigidBody(
      RAPIER.RigidBodyDesc.dynamic()
        .setTranslation(position.x, position.y, position.z)
        .setRotation({ x: quaternion.x, y: quaternion.y, z: quaternion.z, w: quaternion.w })
        .setGravityScale(0)
        .setCcdEnabled(true)
        .setAngularDamping(4)
        .setCanSleep(false),
    );
    const { width, height, length } = spec.size;
    this.collider = world.createCollider(
      RAPIER.ColliderDesc.roundCuboid(width / 2 - 0.08, height / 2 - 0.08, length / 2 - 0.08, 0.08)
        .setMass(spec.mass)
        .setCollisionGroups(groups(GROUP_PROXY, GROUP_CAR))
        .setFriction(0.15)
        .setRestitution(0.1),
      this.body,
    );
  }

  drive(target: Vector3, targetQ: Quaternion, velocity: Vector3, now = 0) {
    const t = this.body.translation();
    _p.set(target.x - t.x, target.y - t.y, target.z - t.z);
    if (_p.lengthSq() > 64) {
      this.body.setTranslation({ x: target.x, y: target.y, z: target.z }, true);
      _p.set(0, 0, 0);
      this.ghost(now + 1500);
    }
    const k = Math.min(3, 8 / Math.max(0.5, _p.length()));
    const v = this.body.linvel();
    const a = BLEND;
    this.body.setLinvel(
      { x: v.x + (velocity.x + _p.x * k - v.x) * a, y: v.y + (velocity.y + _p.y * k - v.y) * a, z: v.z + (velocity.z + _p.z * k - v.z) * a },
      true,
    );
    const r = this.body.rotation();
    _q.set(r.x, r.y, r.z, r.w).slerp(targetQ, 0.25);
    this.body.setRotation({ x: _q.x, y: _q.y, z: _q.z, w: _q.w }, true);
    this.body.setAngvel({ x: 0, y: 0, z: 0 }, true);
  }

  ghost(until: number) {
    this.ghostUntil = Math.max(this.ghostUntil, until);
    this.collider.setEnabled(false);
  }

  updateGhost(now: number, localCar: Vector3 | null) {
    if (this.collider.isEnabled() || now < this.ghostUntil) return;
    if (localCar && this.position.distanceTo(localCar) < 5) return;
    this.collider.setEnabled(true);
  }

  get position() {
    const t = this.body.translation();
    return _p.set(t.x, t.y, t.z);
  }

  get quaternion() {
    const r = this.body.rotation();
    return _q.set(r.x, r.y, r.z, r.w);
  }
}
