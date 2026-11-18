import type { Vector3 } from 'three';
import { GROUP_CAR, GROUP_GROUND, GROUP_PROXY, RAPIER, groups, type PhysicsWorld } from '../vehicle/PhysicsWorld';
import type { ShellTarget, ShellWorld } from './ballistics';

/**
 * What a shell (and the laser rangefinder) meets in the game's world:
 *   - the road and the vehicles: a ray through the physics world (Rapier). Vehicles are the real cars (the rival)
 *     and the other players' stand-ins (`ProxyCar`): a stand-in that is ghosted (just respawned, not heard from)
 *     has no collider and cannot be hit, as it cannot be touched;
 *   - the land: the terrain's heights, walked along the way (the physics world has no terrain: cars never leave
 *     the road).
 * NOT the road's walls: the physics' walls are 3.2 m of invisible fence that keeps cars on the road, and a shell
 * fired across a hairpin must not stop in the air above a 0.7 m guard rail. Scenery without a collider (rails,
 * rock sheds, signs, trees, the autobahn's traffic) does not stop a shell either.
 */
export class GameShellWorld implements ShellWorld {
  /** collider handle → what it is (a vehicle's key); the firer's own body is left out by `bodies` */
  readonly targets = new Map<number, number>();
  /** the firer → its body (never hit by its own shell) */
  readonly bodies = new Map<number, RAPIER.RigidBody>();
  private ray = new RAPIER.Ray({ x: 0, y: 0, z: 0 }, { x: 0, y: 0, z: 1 });
  private hit: { t: number; target: ShellTarget } = { t: 0, target: null };

  constructor(
    private physics: PhysicsWorld,
    /** the land's height at a place (m), or null where there is none (tests, a pad) */
    private heightAt: ((x: number, z: number) => number) | null,
  ) {}

  cast(from: Vector3, dir: Vector3, len: number, owner: number) {
    let t = Infinity;
    let target: ShellTarget = null;
    const ray = this.ray;
    ray.origin = { x: from.x, y: from.y, z: from.z };
    ray.dir = { x: dir.x, y: dir.y, z: dir.z };
    // (as a car's wheel rays: a member of the cars' group, so the road answers; vehicles and stand-ins too)
    const hit = this.physics.world.castRay(ray, len, true, undefined, groups(GROUP_CAR, GROUP_GROUND | GROUP_CAR | GROUP_PROXY), undefined, this.bodies.get(owner));
    if (hit) {
      t = hit.timeOfImpact;
      target = this.targets.get(hit.collider.handle) ?? null;
    }
    const land = this.land(from, dir, Math.min(len, t));
    if (land < t) {
      t = land;
      target = null;
    }
    if (t === Infinity) return null;
    this.hit.t = t;
    this.hit.target = target;
    return this.hit;
  }

  /**
   * How far along the way the land is met (Infinity: not within `len`): samples no further apart than 2.5 m near
   * the start, growing with the distance (a laser's 4 km are a few hundred samples), the crossing found by halving.
   */
  private land(from: Vector3, dir: Vector3, len: number) {
    const h = this.heightAt;
    if (!h) return Infinity;
    const over = (d: number) => from.y + dir.y * d - h(from.x + dir.x * d, from.z + dir.z * d);
    if (over(0) < 0) return 0;
    let a = 0;
    while (a < len) {
      const b = Math.min(len, a + Math.max(2.5, a * 0.012));
      if (over(b) < 0) {
        let lo = a, hi = b;
        for (let k = 0; k < 8; k++) {
          const mid = (lo + hi) / 2;
          if (over(mid) < 0) hi = mid;
          else lo = mid;
        }
        return hi;
      }
      a = b;
    }
    return Infinity;
  }
}
