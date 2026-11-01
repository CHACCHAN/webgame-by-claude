import { Quaternion, Vector3 } from 'three';
import { GROUP_CAR, GROUP_PROXY, PHYSICS_DT, PhysicsWorld, RAPIER, groups } from '../vehicle/PhysicsWorld';
import type { CarSpec } from '../vehicle/carSpecs';

const _p = new Vector3(), _q = new Quaternion();
/** per-step velocity blend: ~0.15 s time constant at the physics rate */
const BLEND = 1 - Math.exp(-PHYSICS_DT / 0.15);

/**
 * Physical stand-in for another player's car in an online race: a body with the car's real mass and
 * chassis shape, steered every physics step towards where the network says that car is. The local car
 * bumps into it with finite mass (both get pushed); the spring then pulls it back onto the network
 * track. It only collides with real cars — never with the ground, walls or other stand-ins.
 */
export class ProxyCar {
  readonly body: RAPIER.RigidBody;
  readonly collider: RAPIER.Collider;
  /** no contact until this time (ms) and until clear of the local car: after jumps and respawns */
  private ghostUntil = 0;

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
  }

  /**
   * One physics step: velocity = network velocity plus a spring towards the network position;
   * jumps (respawns, lag spikes) are teleported.
   */
  drive(target: Vector3, targetQ: Quaternion, velocity: Vector3, now = 0) {
    const t = this.body.translation();
    _p.set(target.x - t.x, target.y - t.y, target.z - t.z);
    if (_p.lengthSq() > 64) {
      this.body.setTranslation({ x: target.x, y: target.y, z: target.z }, true);
      _p.set(0, 0, 0);
      this.ghost(now + 1500);
    }
    // the wanted velocity is the network velocity plus a (capped) pull back onto the track; the body
    // only blends towards it, so the momentum of a hit survives for a moment and the car gets shoved
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

  dispose() {
    this.physics.world.removeRigidBody(this.body);
  }
}
