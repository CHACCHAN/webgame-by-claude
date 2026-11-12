// The fighters' figures as the game simulates them, next to the published ones they come from (level concrete at
// Edwards' air): npx tsx tools/jet-figures.ts [ids]
// Per aircraft: static thrust (sea level, and at the field), mass and thrust-to-weight, then full afterburner and
// military power (no afterburner) from a standing start with the engines already at power (as off the start grid,
// where the chocks hold it while they spool up): time to 100 and 300 km/h, time and ground run to the rotation and
// lift-off speeds, the speed at the far end of the 4,579 m runway and after 12 km, the highest speed reached and
// the share of the weight the wing carries then; and the stop from 300 km/h on the wheel brakes with the speed brake.
import { Vector3 } from 'three';
import { RAPIER, initRapier, groups, GROUP_GROUND, GROUP_CAR, PHYSICS_DT, type PhysicsWorld } from '../src/game/vehicle/PhysicsWorld';
import { VehicleSim, emptyInput } from '../src/game/vehicle/VehicleSim';
import { CAR_SPECS, type CarId } from '../src/game/vehicle/carSpecs';
import { EDWARDS_AIR, JET_ORDER, type JetId } from '../src/game/vehicle/jets';
import { EDWARDS_FIELD } from '../src/game/track/courseDesign';

const ids = (process.argv[2]?.split(',') ?? JET_ORDER) as JetId[];
await initRapier();
const RUNWAY = EDWARDS_FIELD.runway.length;

interface Run {
  t100: number; t300: number; tVr: number; dVr: number; tLof: number; dLof: number; endOfRunway: number; at12km: number; top: number; topMach: number; lift: number;
}

function run(id: JetId, throttle: number, spooled: boolean): Run {
  const spec = CAR_SPECS[id as CarId], jet = spec.jet!;
  const world = new RAPIER.World({ x: 0, y: -9.81, z: 0 });
  world.timestep = PHYSICS_DT;
  world.createCollider(RAPIER.ColliderDesc.cuboid(4000, 1, 60000).setTranslation(0, -1, 0).setCollisionGroups(groups(GROUP_GROUND, GROUP_CAR)));
  const z0 = -59000;
  const v = new VehicleSim({ world } as unknown as PhysicsWorld, spec, new Vector3(0, 0, z0), 0);
  const input = emptyInput();
  input.throttle = throttle;
  const step = () => {
    v.input = input;
    v.preStep(PHYSICS_DT);
    world.step();
    v.postStep(PHYSICS_DT);
  };
  // on the chocks until the engines are at the power asked for
  if (spooled) {
    input.hold = true;
    for (let t = 0; t < 12; t += PHYSICS_DT) step();
    input.hold = false;
  }
  const r: Run = { t100: NaN, t300: NaN, tVr: NaN, dVr: NaN, tLof: NaN, dLof: NaN, endOfRunway: NaN, at12km: NaN, top: 0, topMach: 0, lift: 0 };
  const start = v.position.z;
  for (let t = 0; t < 400; t += PHYSICS_DT) {
    step();
    const s = v.forwardSpeed, d = v.position.z - start;
    if (Number.isNaN(r.t100) && s >= 100 / 3.6) r.t100 = t;
    if (Number.isNaN(r.t300) && s >= 300 / 3.6) r.t300 = t;
    if (Number.isNaN(r.tVr) && s >= jet.vr) [r.tVr, r.dVr] = [t, d];
    if (Number.isNaN(r.tLof) && s >= jet.lof) [r.tLof, r.dLof] = [t, d];
    if (Number.isNaN(r.endOfRunway) && d >= RUNWAY) r.endOfRunway = s;
    if (Number.isNaN(r.at12km) && d >= 12000) r.at12km = s;
    if (s > r.top) [r.top, r.topMach, r.lift] = [s, s / EDWARDS_AIR.sound, v.liftShare];
    if (d > 100000) break;
  }
  world.free();
  return r;
}

/** the stop from 300 km/h: brakes and speed brake, engines at idle */
function stop(id: JetId) {
  const spec = CAR_SPECS[id as CarId];
  const world = new RAPIER.World({ x: 0, y: -9.81, z: 0 });
  world.timestep = PHYSICS_DT;
  world.createCollider(RAPIER.ColliderDesc.cuboid(4000, 1, 60000).setTranslation(0, -1, 0).setCollisionGroups(groups(GROUP_GROUND, GROUP_CAR)));
  const v = new VehicleSim({ world } as unknown as PhysicsWorld, spec, new Vector3(0, 0, -59000), 0);
  const input = emptyInput();
  const step = () => {
    v.input = input;
    v.preStep(PHYSICS_DT);
    world.step();
    v.postStep(PHYSICS_DT);
  };
  for (let t = 0; t < 2; t += PHYSICS_DT) step();
  v.reset(new Vector3(0, v.position.y, -50000), 0, 300 / 3.6);
  input.brake = 1;
  let t = 0;
  const from = v.position.z;
  while (v.forwardSpeed > 0.5 && t < 120) {
    step();
    t += PHYSICS_DT;
  }
  const out = { time: t, distance: v.position.z - from };
  world.free();
  return out;
}

const kmh = (v: number) => (v * 3.6).toFixed(0);
const kt = (v: number) => (v / 0.514444).toFixed(0);
const sigma = Math.pow(EDWARDS_AIR.density / 1.225, 0.75);
for (const id of ids) {
  const spec = CAR_SPECS[id as CarId], jet = spec.jet!, e = jet.engines;
  const weight = spec.mass * 9.81;
  console.log(`\n${spec.name}  (${e.name} ×${e.count})`);
  console.log(`  mass ${spec.mass} kg   static thrust, sea level: dry ${((e.dry * e.count) / 1000).toFixed(1)} kN, A/B ${((e.ab * e.count) / 1000).toFixed(1)} kN   at the field (σ^0.75 = ${sigma.toFixed(3)}): dry ${((e.dry * e.count * sigma) / 1000).toFixed(1)} kN, A/B ${((e.ab * e.count * sigma) / 1000).toFixed(1)} kN`);
  console.log(`  thrust / weight: sea level ${((e.ab * e.count) / weight).toFixed(2)} (A/B), ${((e.dry * e.count) / weight).toFixed(2)} (dry); at the field ${((e.ab * e.count * sigma) / weight).toFixed(2)} / ${((e.dry * e.count * sigma) / weight).toFixed(2)}`);
  console.log(`  rotation ${kmh(jet.vr)} km/h (${kt(jet.vr)} kt), lift-off ${kmh(jet.lof)} km/h (${kt(jet.lof)} kt)`);
  for (const [label, throttle] of [['afterburner', 1], ['military power', 0.85]] as const) {
    const r = run(id, throttle, true);
    console.log(`  ${label.padEnd(15)} 0–100 ${r.t100.toFixed(2)} s  0–300 ${r.t300.toFixed(2)} s  Vr ${r.tVr.toFixed(1)} s / ${r.dVr.toFixed(0)} m  lift-off ${r.tLof.toFixed(1)} s / ${r.dLof.toFixed(0)} m  end of 04R ${kmh(r.endOfRunway)} km/h (M ${(r.endOfRunway / EDWARDS_AIR.sound).toFixed(2)})  after 12 km ${kmh(r.at12km)} km/h  top ${kmh(r.top)} km/h (M ${r.topMach.toFixed(2)}, wing carries ${(r.lift * 100).toFixed(0)} %)`);
  }
  const cold = run(id, 1, false);
  console.log(`  from idle, afterburner: 0–100 ${cold.t100.toFixed(2)} s  0–300 ${cold.t300.toFixed(2)} s  end of 04R ${kmh(cold.endOfRunway)} km/h`);
  const st = stop(id);
  console.log(`  stop from 300 km/h: ${st.time.toFixed(1)} s, ${st.distance.toFixed(0)} m`);
}
