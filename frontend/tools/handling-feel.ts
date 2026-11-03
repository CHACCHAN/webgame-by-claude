// Feel numbers on a flat pad: wall hits (rebound, speed kept, how much the car is spun) and drift entries
// (time held in a drift, peak slip, spins). Usage: npx tsx tools/handling-feel.ts [cars]
import { Quaternion, Vector3 } from 'three';
import { RAPIER, initRapier, groups, GROUP_GROUND, GROUP_CAR, GROUP_WALL, PHYSICS_DT } from '../src/game/vehicle/PhysicsWorld';
import type { PhysicsWorld } from '../src/game/vehicle/PhysicsWorld';
import { VehicleSim, emptyInput, type VehicleInput } from '../src/game/vehicle/VehicleSim';
import { CAR_SPECS, type CarId } from '../src/game/vehicle/carSpecs';

await initRapier();

/** Flat ground; with `wall`, a long wall along z at x = 0 with the course walls' material. */
function pad(wall: boolean) {
  const world = new RAPIER.World({ x: 0, y: -9.81, z: 0 });
  world.timestep = PHYSICS_DT;
  world.createCollider(RAPIER.ColliderDesc.cuboid(5000, 1, 5000).setTranslation(0, -1, 0).setCollisionGroups(groups(GROUP_GROUND, GROUP_CAR)));
  if (wall) {
    world.createCollider(
      RAPIER.ColliderDesc.cuboid(0.2, 1, 2000).setTranslation(-0.2, 1, 0).setCollisionGroups(groups(GROUP_WALL, GROUP_CAR)).setFriction(0.05).setRestitution(0.15),
    );
  }
  return { world, step: () => world.step(), dispose: () => world.free() } as unknown as PhysicsWorld;
}

function sim(car: CarId, wall: boolean, pos: Vector3, heading: number, speed: number, seconds: number, control: (t: number, v: VehicleSim, i: VehicleInput) => void, each: (t: number, v: VehicleSim) => void) {
  const phys = pad(wall);
  const v = new VehicleSim(phys, CAR_SPECS[car], pos, heading);
  v.assist = 1;
  v.reset(pos, heading, speed);
  const inp = emptyInput();
  for (let t = 0; t < seconds; t += PHYSICS_DT) {
    control(t, v, inp);
    v.input = inp;
    v.preStep(PHYSICS_DT);
    (phys as unknown as { step(): void }).step();
    v.postStep(PHYSICS_DT);
    each(t, v);
  }
  (phys as unknown as { dispose(): void }).dispose();
}

const yawOf = (q: Quaternion) => {
  const f = new Vector3(0, 0, 1).applyQuaternion(q);
  return Math.atan2(f.x, f.z);
};

const cars = (process.argv[2] ?? 'hayate,s15,raijin,shiden').split(',') as CarId[];
for (const car of cars) {
  console.log(`=== ${car}`);
  // wall hits: approach the wall (x = 0) from +x at `angle` off the wall's direction, holding a light throttle
  for (const kmh of [60, 100]) {
    const row: string[] = [];
    for (const deg of [10, 25, 45]) {
      const a = (deg * Math.PI) / 180;
      // heading 0 = +z; turn towards −x by `a`
      const heading = -a;
      let hitT = -1, rebound = 0, maxYawRate = 0, yaw0 = 0, yaw1 = 0, along = 0, away = 0, thuds = 0, lastThud = -1;
      sim(car, true, new Vector3(4, 0, 0), heading, kmh / 3.6, 3, (_t, _v, i) => { i.throttle = 0.4; }, (t, v) => {
        if (hitT < 0 && v.impact > 0) { hitT = t; yaw0 = yawOf(v.quaternion); }
        // the game plays an impact sound above 0.15: count separate ones (a new one after 0.1 s of quiet)
        if (v.impact > 0.15) { if (t - lastThud > 0.1) thuds++; lastThud = t; }
        if (hitT >= 0 && t - hitT <= 1) {
          rebound = Math.max(rebound, v.velocity.x);
          maxYawRate = Math.max(maxYawRate, Math.abs(v.yawRate));
          yaw1 = yawOf(v.quaternion);
          along = v.velocity.z;
          away = v.position.x;
        }
      });
      if (hitT < 0) { row.push(`${deg}°: no hit`); continue; }
      row.push(`${deg}°: bounce ${(rebound * 3.6).toFixed(0)}km/h keep ${((along * 3.6) / kmh * 100).toFixed(0)}% spun ${(((yaw1 - yaw0) * 180) / Math.PI).toFixed(0)}° yawRate ${maxYawRate.toFixed(1)} off ${away.toFixed(1)}m thuds ${thuds}`);
    }
    console.log(`  wall @${kmh}: ` + row.join(' | '));
  }
  // drift entries at 70 km/h: [label, control]
  const entries: [string, (t: number, v: VehicleSim, i: VehicleInput) => void][] = [
    ['power', (t, _v, i) => { i.throttle = 1; i.steer = t < 2.5 ? 0.7 : 0; }],
    ['handbrake', (t, v, i) => { i.handbrake = t < 0.35; i.steer = t < 2.5 ? (t < 0.6 ? 0.8 : -0.35 * Math.sign(v.slipAngle || 1) * -1) : 0; i.throttle = t > 0.35 ? 0.8 : 0; }],
    ['feint', (t, _v, i) => { i.brake = t < 0.4 ? 0.6 : 0; i.steer = t < 2.5 ? 0.8 : 0; i.throttle = t > 0.4 ? 0.9 : 0; }],
    // steer into the bend, a short pull on the handbrake, then power with the wheel held in
    ['handbrake-held', (t, _v, i) => { i.steer = t < 1.2 ? 0.8 : 0.25; i.handbrake = t < 0.3; i.throttle = t > 0.3 ? 0.9 : 0; }],
  ];
  const row: string[] = [];
  for (const [label, control] of entries) {
    let held = 0, peak = 0, spun = false;
    sim(car, false, new Vector3(0, 0, 0), 0, 70 / 3.6, 4, control, (_t, v) => {
      const s = Math.abs((v.slipAngle * 180) / Math.PI);
      if (s > 15 && v.speed > 5) held += PHYSICS_DT;
      peak = Math.max(peak, s);
      if (s > 100) spun = true;
    });
    row.push(`${label}: drift ${held.toFixed(1)}s peak ${peak.toFixed(0)}°${spun ? ' SPIN' : ''}`);
  }
  console.log('  drift @70: ' + row.join(' | '));
}
