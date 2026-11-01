import RAPIER from '@dimforge/rapier3d-compat';
import type { Track } from '../track/Track';
import { buildRoadCollider, buildWallColliders } from '../track/roadGeometry';

export const PHYSICS_HZ = 120;
export const PHYSICS_DT = 1 / PHYSICS_HZ;

// Collision group bits
export const GROUP_GROUND = 0x0001;
export const GROUP_WALL = 0x0002;
export const GROUP_CAR = 0x0004;
/** stand-ins for other players' cars in online races: they only touch real cars */
export const GROUP_PROXY = 0x0008;
export const groups = (membership: number, filter: number) => (membership << 16) | filter;

let initPromise: Promise<void> | null = null;
export function initRapier() {
  if (!initPromise) initPromise = RAPIER.init();
  return initPromise;
}

export { RAPIER };

/** Rapier world holding the static road/wall colliders. Vehicles add their own bodies. */
export class PhysicsWorld {
  readonly world: RAPIER.World;
  readonly track: Track;

  constructor(track: Track) {
    this.track = track;
    this.world = new RAPIER.World({ x: 0, y: -9.81, z: 0 });
    this.world.timestep = PHYSICS_DT;

    const road = buildRoadCollider(track);
    this.world.createCollider(
      RAPIER.ColliderDesc.trimesh(road.vertices, road.indices)
        .setCollisionGroups(groups(GROUP_GROUND, GROUP_CAR))
        .setFriction(0.9),
    );
    const walls = buildWallColliders(track);
    this.world.createCollider(
      RAPIER.ColliderDesc.trimesh(walls.vertices, walls.indices)
        .setCollisionGroups(groups(GROUP_WALL, GROUP_CAR))
        .setFriction(0.05)
        .setRestitution(0.15),
    );
    // End caps so nobody can drive off either end of the road.
    for (const s of [0, track.length]) {
      const p = track.pointAt(s);
      const h = track.headingAt(s);
      const w = track.widthAt(s);
      const q = { x: 0, y: Math.sin(h / 2), z: 0, w: Math.cos(h / 2) };
      this.world.createCollider(
        RAPIER.ColliderDesc.cuboid(w / 2 + 3, 3, 0.5)
          .setTranslation(p.x, p.y + 1, p.z)
          .setRotation(q)
          .setCollisionGroups(groups(GROUP_WALL, GROUP_CAR)),
      );
    }
  }

  step() {
    this.world.step();
  }

  dispose() {
    this.world.free();
  }
}
