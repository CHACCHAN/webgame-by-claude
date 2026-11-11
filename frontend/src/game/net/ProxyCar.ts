import { Quaternion, Vector3 } from 'three';
import { GROUP_CAR, GROUP_PROXY, PHYSICS_DT, PhysicsWorld, RAPIER, groups } from '../vehicle/PhysicsWorld';
import type { CarSpec } from '../vehicle/carSpecs';
import { newSteerMemory, steerProxy } from './steer';

const _p = new Vector3(), _q = new Quaternion();
const _cmd: [number, number, number] = [0, 0, 0];

/**
 * Physical stand-in for another player's car in an online race: a body with the car's real mass and
 * chassis shape, steered every physics step along the path the network gives for that car (`steerProxy`).
 * The local car bumps into it with finite mass (both get pushed); a soft pull then brings it back onto the
 * path. It only collides with real cars — never with the ground, walls or other stand-ins.
 */
export class ProxyCar {
  readonly body: RAPIER.RigidBody;
  readonly collider: RAPIER.Collider;
  /** no contact until this time (ms) and until clear of the local car: after jumps and respawns */
  private ghostUntil = 0;
  private memory = newSteerMemory();
  /** where the network had the car at the end of the last step: the body's distance from it is what hits did */
  private aim = new Vector3();

  constructor(private physics: PhysicsWorld, spec: CarSpec, position: Vector3, quaternion: Quaternion) {
    this.body = physics.world.createRigidBody(
      RAPIER.RigidBodyDesc.dynamic()
        .setTranslation(position.x, position.y, position.z)
        .setRotation({ x: quaternion.x, y: quaternion.y, z: quaternion.z, w: quaternion.w })
        .setGravityScale(0)
        .setCcdEnabled(true)
        .setAngularDamping(4)
        .setCanSleep(false),
    );
    const { width, height, length } = spec.size;
    this.collider = physics.world.createCollider(
      RAPIER.ColliderDesc.roundCuboid(width / 2 - 0.08, height / 2 - 0.08, length / 2 - 0.08, 0.08)
        .setMass(spec.mass)
        .setCollisionGroups(groups(GROUP_PROXY, GROUP_CAR))
        .setFriction(0.15)
        .setRestitution(0.1),
      this.body,
    );
    this.aim.copy(position);
  }

  /**
   * One physics step: `target`, `targetQ`, `velocity` are the car's pose and velocity (in the physics world's
   * seconds) at the end of this step. Jumps (respawns, lag spikes) are teleported. `gap`: time was skipped since
   * the last step (see `steerProxy`).
   */
  drive(target: Vector3, targetQ: Quaternion, velocity: Vector3, now = 0, gap = false) {
    const t = this.body.translation();
    if (_p.set(target.x - t.x, target.y - t.y, target.z - t.z).lengthSq() > 64) return this.teleport(target, targetQ, now);
    const v = this.body.linvel();
    steerProxy(this.memory, [t.x, t.y, t.z], [v.x, v.y, v.z], [target.x, target.y, target.z], [velocity.x, velocity.y, velocity.z], PHYSICS_DT, _cmd, gap);
    if (gap) {
      const s = this.memory.shift;
      this.body.setTranslation({ x: t.x + s[0], y: t.y + s[1], z: t.z + s[2] }, true);
    }
    this.body.setLinvel({ x: _cmd[0], y: _cmd[1], z: _cmd[2] }, true);
    // the heading is the network's, as it is: a hit shoves the stand-in, it does not spin it
    this.body.setRotation({ x: targetQ.x, y: targetQ.y, z: targetQ.z, w: targetQ.w }, true);
    this.body.setAngvel({ x: 0, y: 0, z: 0 }, true);
    this.aim.copy(target);
  }

  /** Puts the stand-in at a pose (the car was moved, not driven, there): no momentum, no contact for a moment. */
  teleport(target: Vector3, targetQ: Quaternion, now = 0) {
    this.body.setTranslation({ x: target.x, y: target.y, z: target.z }, true);
    this.body.setRotation({ x: targetQ.x, y: targetQ.y, z: targetQ.z, w: targetQ.w }, true);
    this.body.setLinvel({ x: 0, y: 0, z: 0 }, true);
    this.body.setAngvel({ x: 0, y: 0, z: 0 }, true);
    this.memory = newSteerMemory();
    this.aim.copy(target);
    this.ghost(now + 1500);
  }

  /** Pass through cars until `until` (ms) — it might have landed inside one. */
  ghost(until: number) {
    this.ghostUntil = Math.max(this.ghostUntil, until);
    this.collider.setEnabled(false);
  }

  /** Becomes solid again once the ghost time is over and it is clear of the local car. */
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

  /** How far hits have pushed the body off the network's path (m): what the picture adds to the path's pose. */
  shove(out: Vector3) {
    const t = this.body.translation();
    return out.set(t.x - this.aim.x, t.y - this.aim.y, t.z - this.aim.z);
  }

  dispose() {
    this.physics.world.removeRigidBody(this.body);
  }
}
