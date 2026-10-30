// Scripted manoeuvres on a flat pad to quantify handling (no track walls).
import { Vector3 } from 'three';
import { RAPIER, initRapier, groups, GROUP_GROUND, GROUP_CAR, PHYSICS_DT } from '../src/game/vehicle/PhysicsWorld';
import type { PhysicsWorld } from '../src/game/vehicle/PhysicsWorld';
import { VehicleSim, emptyInput, type VehicleInput } from '../src/game/vehicle/VehicleSim';
import { CAR_SPECS, type CarId } from '../src/game/vehicle/carSpecs';

await initRapier();

function pad() {
  const world = new RAPIER.World({ x: 0, y: -9.81, z: 0 });
  world.timestep = PHYSICS_DT;
  world.createCollider(RAPIER.ColliderDesc.cuboid(5000, 1, 5000).setTranslation(0, -1, 0).setCollisionGroups(groups(GROUP_GROUND, GROUP_CAR)));
  return { world, step: () => world.step(), dispose: () => world.free() } as unknown as PhysicsWorld;
}

function run(car: CarId, seconds: number, control: (t: number, v: VehicleSim, inp: VehicleInput) => void, assist: 0 | 1 | 2 = 1, startSpeed = 0) {
  const phys = pad();
  const v = new VehicleSim(phys, CAR_SPECS[car], new Vector3(0, 0, 0), 0);
  v.assist = assist;
  if (startSpeed) v.reset(new Vector3(0, 0, 0), 0, startSpeed);
  const inp = emptyInput();
  const log: { t: number; kmh: number; slip: number; yaw: number; x: number; z: number; gear: number; latG: number }[] = [];
  let t = 0;
  const prevV = new Vector3();
  while (t < seconds) {
    control(t, v, inp);
    v.input = inp;
    v.preStep(PHYSICS_DT);
    phys.step();
    v.postStep(PHYSICS_DT);
    const acc = new Vector3().subVectors(v.velocity, prevV).divideScalar(PHYSICS_DT);
    prevV.copy(v.velocity);
    const latG = Math.abs(acc.dot(v.right)) / 9.81;
    t += PHYSICS_DT;
    log.push({ t, kmh: v.speed * 3.6, slip: (v.slipAngle * 180) / Math.PI, yaw: v.yawRate, x: v.position.x, z: v.position.z, gear: v.gear, latG });
  }
  (phys as unknown as { dispose(): void }).dispose();
  return { log, v };
}

const cars = (process.argv[2] ?? 'hayate,raijin,shiden').split(',') as CarId[];
for (const car of cars) {
  console.log(`\n=== ${car}`);
  // 0-100 and top speed
  {
    const { log } = run(car, 30, (_t, _v, i) => { i.throttle = 1; });
    const t100 = log.find((l) => l.kmh >= 100)?.t;
    const t60 = log.find((l) => l.kmh >= 60)?.t;
    console.log(`0-60 ${t60?.toFixed(2)}s  0-100 ${t100?.toFixed(2)}s  speed@30s ${log[log.length - 1].kmh.toFixed(0)} km/h`);
  }
  // braking 100 -> 0
  {
    let startZ = 0, braking = false;
    const { log } = run(car, 12, (_t, v, i) => {
      if (!braking && v.speed * 3.6 >= 100) { braking = true; startZ = v.position.z; }
      i.throttle = braking ? 0 : 1; i.brake = braking ? 1 : 0;
    });
    const stop = log.find((l, k) => k > 10 && braking && l.kmh < 1);
    console.log(`brake 100-0: ${stop ? (stop.z - startZ).toFixed(1) + ' m' : 'n/a'}`);
  }
  // steady cornering at ~70 km/h with half steer, measure lateral g & slip
  {
    const { log } = run(car, 8, (t, v, i) => {
      const target = 70 / 3.6;
      i.throttle = v.speed < target ? 0.7 : 0.25; i.brake = 0;
      i.steer = t > 1 ? 0.55 : 0;
    }, 1, 70 / 3.6);
    const tail = log.slice(-240);
    const latG = tail.reduce((a, l) => a + l.latG, 0) / tail.length;
    const slip = tail.reduce((a, l) => a + Math.abs(l.slip), 0) / tail.length;
    console.log(`corner 70km/h steer .55: latG ${latG.toFixed(2)}  slip ${slip.toFixed(1)}°  end speed ${tail[tail.length - 1].kmh.toFixed(0)}`);
  }
  // power-on drift: 60 km/h, full steer + full throttle for 1.2 s, then counter-steer & modulate
  for (const assist of [1, 0] as const) {
    const { log } = run(car, 6, (t, v, i) => {
      if (t < 0.5) { i.throttle = 0.4; i.steer = 0; return; }
      if (t < 1.4) { i.throttle = 1; i.steer = -1; return; }
      // simple driver: counter-steer proportional to slip, keep throttle
      const slip = v.slipAngle;
      i.steer = Math.max(-1, Math.min(1, slip * 2.2));
      i.throttle = Math.abs(slip) > 0.6 ? 0.45 : 0.85;
    }, assist, 60 / 3.6);
    const maxSlip = Math.max(...log.map((l) => Math.abs(l.slip)));
    const driftTime = log.filter((l) => Math.abs(l.slip) > 15).length * PHYSICS_DT;
    const spun = log.some((l) => Math.abs(l.slip) > 100);
    const endKmh = log[log.length - 1].kmh;
    console.log(`power drift (assist ${assist}): maxSlip ${maxSlip.toFixed(0)}°  time>15° ${driftTime.toFixed(2)}s  spun ${spun}  end ${endKmh.toFixed(0)} km/h`);
  }
  // handbrake turn at 60 km/h
  {
    const { log, v } = run(car, 3, (t, _v, i) => {
      i.throttle = 0.3;
      i.steer = t > 0.2 && t < 1.2 ? -0.8 : 0;
      i.handbrake = t > 0.2 && t < 0.8;
    }, 1, 60 / 3.6);
    const heading = (Math.atan2(v.forward.x, v.forward.z) * 180) / Math.PI;
    console.log(`handbrake turn: maxSlip ${Math.max(...log.map((l) => Math.abs(l.slip))).toFixed(0)}°  heading change ${heading.toFixed(0)}°  end ${log[log.length - 1].kmh.toFixed(0)} km/h`);
  }
  // naive abuse: full throttle + full steer for 4 s from 80 km/h
  for (const assist of [1, 0] as const) {
    const { log } = run(car, 4, (_t0, _v, i) => { i.throttle = 1; i.steer = 1; }, assist, 80 / 3.6);
    console.log(`abuse (assist ${assist}): maxSlip ${Math.max(...log.map((l) => Math.abs(l.slip))).toFixed(0)}°  spun ${log.some((l) => Math.abs(l.slip) > 100)}`);
  }
}

// Closed-loop "skilled driver": feint into a drift, then hold a target slip angle with steer + throttle.
console.log('\n--- drift hold (target 30°, 6 s) ---');
for (const car of cars) {
  for (const assist of [1, 0] as const) {
    const target = 30 / 57.3;
    const { log } = run(car, 7, (t, v, i) => {
      if (t < 0.6) { i.throttle = 0.6; i.steer = 0; i.brake = 0; return; }
      if (t < 1.0) { i.throttle = 0; i.brake = 0.6; i.steer = -0.9; return; }   // feint: brake + steer left
      i.brake = 0;
      const slip = v.slipAngle; // >0: tail out to the right of travel in a left turn
      i.steer = Math.max(-1, Math.min(1, (slip - target) * 2.5 + 0.15));
      i.throttle = Math.max(0.15, Math.min(1, 0.7 + (target - slip) * 2.5));
    }, assist, 75 / 3.6);
    const hold = log.filter((l) => l.t > 1.5);
    const inBand = hold.filter((l) => Math.abs(l.slip) > 18 && Math.abs(l.slip) < 45).length / hold.length;
    const avgKmh = hold.reduce((a, l) => a + l.kmh, 0) / hold.length;
    const spun = log.some((l) => Math.abs(l.slip) > 100);
    console.log(`${car.padEnd(7)} assist ${assist}: in-band ${(inBand * 100).toFixed(0)}%  avg ${avgKmh.toFixed(0)} km/h  end ${log[log.length - 1].kmh.toFixed(0)} km/h  spun ${spun}`);
  }
}
