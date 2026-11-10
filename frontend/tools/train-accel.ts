// A train's acceleration over its whole speed range, as the game simulates it (level track, and a balancing run up a
// gradient): npx tsx tools/train-accel.ts [trainId=e5] [gradient‰=3]
import { Vector3 } from 'three';
import { RAPIER, initRapier, groups, GROUP_GROUND, GROUP_CAR, PHYSICS_DT, type PhysicsWorld } from '../src/game/vehicle/PhysicsWorld';
import { VehicleSim, emptyInput } from '../src/game/vehicle/VehicleSim';
import { CAR_SPECS, type CarId } from '../src/game/vehicle/carSpecs';
import { TRAIN_INFO, type TrainId } from '../src/game/vehicle/trains';

const id = (process.argv[2] ?? 'e5') as TrainId;
const grade = +(process.argv[3] ?? 3) / 1000;
await initRapier();

/** full power from standstill for `seconds`; samples [t, km/h, distance m] every 0.5 s */
function run(seconds: number, slope: number) {
  // a 120 km pad, started near its far edge (a Shinkansen covers tens of kilometres)
  const g = 9.81;
  const world = new RAPIER.World({ x: 0, y: -g / Math.sqrt(1 + slope * slope), z: (-g * slope) / Math.sqrt(1 + slope * slope) });
  world.timestep = PHYSICS_DT;
  world.createCollider(RAPIER.ColliderDesc.cuboid(4000, 1, 60000).setTranslation(0, -1, 0).setCollisionGroups(groups(GROUP_GROUND, GROUP_CAR)));
  const z0 = -59000;
  const v = new VehicleSim({ world } as unknown as PhysicsWorld, CAR_SPECS[id as CarId], new Vector3(0, 0, z0), 0);
  const input = emptyInput();
  input.throttle = 1;
  const out: [number, number, number][] = [];
  let next = 0;
  for (let t = 0; t < seconds; t += PHYSICS_DT) {
    v.input = input;
    v.preStep(PHYSICS_DT);
    world.step();
    v.postStep(PHYSICS_DT);
    if (t >= next) {
      out.push([t, v.forwardSpeed * 3.6, v.position.z - z0]);
      next += 0.5;
    }
    if (v.position.z > 59000) break;
  }
  world.free();
  return out;
}

const t = TRAIN_INFO[id];
console.log(`${t.name}: accel ${t.accel} km/h/s, vmax ${t.vmax} km/h, traction ${t.traction ?? [40, 80]}`);
const level = run(900, 0);
const at = (kmh: number) => level.find((s) => s[1] >= kmh);
console.log('level: time and distance to reach');
for (const k of [30, 100, 150, 200, 250, 270, 300, 320]) {
  const s = at(k);
  console.log(`  ${String(k).padStart(3)} km/h  ${s ? `${s[0].toFixed(1).padStart(6)} s  ${(s[2] / 1000).toFixed(2).padStart(6)} km` : 'not reached'}`);
}
console.log('level: acceleration (km/h/s) around');
for (const k of [20, 100, 150, 200, 250, 280, 300, 320]) {
  const i = level.findIndex((s) => s[1] >= k);
  if (i < 2 || i + 2 >= level.length) {
    console.log(`  ${String(k).padStart(3)} km/h  -`);
    continue;
  }
  const a = (level[i + 2][1] - level[i - 2][1]) / (level[i + 2][0] - level[i - 2][0]);
  console.log(`  ${String(k).padStart(3)} km/h  ${a.toFixed(3)}`);
}
console.log(`level: top ${Math.max(...level.map((s) => s[1])).toFixed(1)} km/h after ${level[level.length - 1][0].toFixed(0)} s`);
const up = run(900, grade);
console.log(`+${grade * 1000}‰: top ${Math.max(...up.map((s) => s[1])).toFixed(1)} km/h`);
