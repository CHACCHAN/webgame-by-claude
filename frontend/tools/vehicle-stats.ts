// Measured figures of every vehicle for the car select's performance bars, taken from the game's own simulation on a
// flat, dry pad (Node, no browser): 0–100 km/h and top speed on a straight at full throttle (automatic gearbox, the
// player's assists as in a race), the peak lateral acceleration on a skid circle (45.7 m radius, the 300 ft pad of the
// magazines: a little faster each lap until the vehicle runs wide), plus the mass and peak power the spec gives.
// A fighter's circle is found another way (`heldCircle`): its idle thrust alone speeds it up, so it cannot be led
// round a little faster each lap; it is held at a speed with the stick hard over, and the speed is sought at which
// the turn it settles into is the pad's circle.
//   npx tsx tools/vehicle-stats.ts            every vehicle a player can pick (VEHICLE_ORDER); rewrites the file
//   npx tsx tools/vehicle-stats.ts u9 e5      only these: their entries are replaced, the others kept
//   npx tsx tools/vehicle-stats.ts --check    measures, writes nothing, fails if the file would change (after a
//                                             change of physics or specs)
//   TRACE=1 npx tsx tools/vehicle-stats.ts --check <id>   the skid circle every 2 s (speed, steering, distance off)
// Output: src/game/vehicle/vehicleStats.json (read through vehicle/stats.ts; the vehicle test wants an entry per id).
// The simulation is deterministic: an unchanged vehicle gives the same numbers.
import { readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { Vector3 } from 'three';
import { RAPIER, initRapier, groups, GROUP_GROUND, GROUP_CAR, PHYSICS_DT, type PhysicsWorld } from '../src/game/vehicle/PhysicsWorld';
import { VehicleSim, emptyInput } from '../src/game/vehicle/VehicleSim';
import { CAR_SPECS, VEHICLE_ORDER, type CarId } from '../src/game/vehicle/carSpecs';
import { specFigures, type VehicleStats } from '../src/game/vehicle/stats';

const FILE = fileURLToPath(new URL('../src/game/vehicle/vehicleStats.json', import.meta.url));
const G = 9.81;
/** skid circle radius (m) */
const R = 45.7;
const TRACE = !!process.env.TRACE;
const clamp = (x: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, x));

await initRapier();

function pad() {
  const world = new RAPIER.World({ x: 0, y: -G, z: 0 });
  world.timestep = PHYSICS_DT;
  world.createCollider(RAPIER.ColliderDesc.cuboid(30000, 1, 30000).setTranslation(0, -1, 0).setCollisionGroups(groups(GROUP_GROUND, GROUP_CAR)));
  return world;
}

/** Full throttle from standstill on the level: seconds to 100 km/h (null: never) and the speed it settles at. */
function straight(id: CarId) {
  const world = pad();
  const v = new VehicleSim({ world } as unknown as PhysicsWorld, CAR_SPECS[id], new Vector3(0, 0, 0), 0);
  const input = emptyInput();
  input.throttle = 1;
  let zeroTo100: number | null = null;
  let top = 0;
  let prev = 0;
  /** the top speed 20 s ago: the run ends once it gains less than 0.2 km/h in that time */
  let mark = 0;
  let markT = 0;
  let t = 0;
  // (a Shinkansen needs ~6 minutes: half an hour at most)
  for (; t < 1800; t += PHYSICS_DT) {
    v.input = input;
    v.preStep(PHYSICS_DT);
    world.step();
    v.postStep(PHYSICS_DT);
    const kmh = v.forwardSpeed * 3.6;
    if (zeroTo100 === null && kmh >= 100) zeroTo100 = t + PHYSICS_DT * (1 - (kmh - 100) / Math.max(1e-6, kmh - prev));
    prev = kmh;
    top = Math.max(top, kmh);
    if (t - markT >= 20) {
      if (top - mark < 0.2) break;
      mark = top;
      markT = t;
    }
    // the pad is 60 km long and single precision gets coarse far out: carried back as it goes
    if (v.position.z > 10000) {
      const p = v.body.translation();
      v.body.setTranslation({ x: p.x, y: p.y, z: p.z - 20000 }, true);
    }
  }
  world.free();
  return { zeroTo100, topSpeed: top, seconds: t };
}

/**
 * Skid circle (to the left), as a magazine runs it: round and round a little faster each lap until the vehicle cannot
 * hold the line. The steering follows a point on the circle ahead (pure pursuit) plus what the distance off the line
 * asks for (the steering lock shrinks with speed, so the same input turns less); the throttle follows a speed that
 * rises 0.25 m/s every second. The figure is the highest lateral acceleration held for a second within 2 m of the
 * line; the run ends when the vehicle is 6 m off it, spins, or has no power left to go faster (a train).
 */
function skidCircle(id: CarId) {
  const world = pad();
  const spec = CAR_SPECS[id];
  const v0 = 8;
  const v = new VehicleSim({ world } as unknown as PhysicsWorld, spec, new Vector3(-R, 0, 0), 0);
  v.reset(new Vector3(-R, 0, 0), 0, v0);
  const input = emptyInput();
  const span = Math.round(1 / PHYSICS_DT);
  const samples: number[] = [];
  let sum = 0;
  let peak = 0;
  let peakV = 0;
  let power = 0;
  let trim = 0;
  let end = 'time';
  const last = new Vector3().copy(v.velocity);
  const acc = new Vector3();
  const to = new Vector3();
  const lock = (spec.maxSteerDeg * Math.PI) / 180;
  for (let t = 0; t < 400; t += PHYSICS_DT) {
    const want = v0 + 0.25 * t;
    const err = want - v.speed;
    power = clamp(power + err * 0.3 * PHYSICS_DT, 0, 1);
    input.throttle = clamp(err * 0.6 + power, 0, 1);
    // heading 0 = +Z at (−R, 0): the centre is on the left (+X), so further out asks for more left (negative) steer
    const off = Math.hypot(v.position.x, v.position.z) - R;
    const look = Math.max(5, v.speed * 0.45);
    const a = Math.atan2(v.position.x, v.position.z) + look / R;
    to.set(Math.sin(a) * R - v.position.x, 0, Math.cos(a) * R - v.position.z).normalize();
    // (+X is the vehicle's left: forward × to points up when the target is to the left)
    const left = v.forward.z * to.x - v.forward.x * to.z;
    trim = clamp(trim + off * 0.15 * PHYSICS_DT, -1, 1);
    input.steer = clamp(-Math.atan2(2 * spec.wheelbase * left, look) / lock - off * 0.12 - trim, -1, 1);
    v.input = input;
    v.preStep(PHYSICS_DT);
    world.step();
    v.postStep(PHYSICS_DT);
    acc.copy(v.velocity).sub(last).divideScalar(PHYSICS_DT);
    last.copy(v.velocity);
    const lat = acc.dot(v.right);
    samples.push(lat);
    sum += lat;
    if (samples.length > span) sum -= samples[samples.length - 1 - span];
    if (samples.length >= span && Math.abs(off) < 2) {
      const g = Math.abs(sum / span) / G;
      if (g > peak) {
        peak = g;
        peakV = v.speed;
      }
    }
    if (TRACE && samples.length % 240 === 0) {
      console.log(`  ${t.toFixed(0).padStart(3)} s  ${(v.speed * 3.6).toFixed(0).padStart(3)} km/h  ${(Math.abs(sum / span) / G).toFixed(2)} g  off ${off.toFixed(2)} m  steer ${input.steer.toFixed(2)}  throttle ${input.throttle.toFixed(2)}  slip ${v.slipAngle.toFixed(2)}`);
    }
    if (Math.abs(off) > 6) {
      end = off > 0 ? 'ran wide' : 'cut in';
      break;
    }
    if (Math.abs(v.slipAngle) > 0.9) {
      end = 'spun';
      break;
    }
    if (want - v.speed > 4) {
      end = 'out of power';
      break;
    }
  }
  world.free();
  return { lateralG: peak, at: peakV * 3.6, end };
}

/**
 * A fighter on the same circle: held at a speed (throttle and wheel brakes), the stick hard over for 14 s; the radius
 * it settles into grows with the speed (the nose wheel's angle and the tyres give no more), and the figure is the
 * lateral acceleration at the speed whose radius is the pad's.
 */
function heldCircle(id: CarId) {
  const spec = CAR_SPECS[id];
  const radiusAt = (speed: number) => {
    const world = pad();
    const v = new VehicleSim({ world } as unknown as PhysicsWorld, spec, new Vector3(0, 0, 0), 0);
    v.reset(new Vector3(0, 0, 0), 0, speed);
    const input = emptyInput();
    let yaw = 0, n = 0;
    for (let t = 0; t < 14; t += PHYSICS_DT) {
      input.throttle = clamp(0.4 + (speed - v.forwardSpeed) * 0.5, 0, 1);
      input.brake = v.forwardSpeed > speed + 0.3 ? clamp((v.forwardSpeed - speed) * 0.4, 0.05, 0.6) : 0;
      input.steer = t < 2 ? 0 : 1;
      v.input = input;
      v.preStep(PHYSICS_DT);
      world.step();
      v.postStep(PHYSICS_DT);
      if (t > 9) {
        yaw += Math.abs(v.yawRate);
        n++;
      }
    }
    const r = v.forwardSpeed / Math.max(yaw / n, 1e-6);
    const at = v.forwardSpeed;
    world.free();
    return { r, at };
  };
  let lo = 6, hi = 30, at = 0;
  for (let k = 0; k < 14; k++) {
    const mid = (lo + hi) / 2;
    const m = radiusAt(mid);
    at = m.at;
    if (m.r < R) lo = mid;
    else hi = mid;
  }
  return { lateralG: (at * at) / R / G, at: at * 3.6, end: 'held turn' };
}

const args = process.argv.slice(2);
const check = args.includes('--check');
const ids = args.filter((a) => !a.startsWith('--')) as CarId[];
for (const id of ids) if (!CAR_SPECS[id]) throw new Error(`unknown vehicle: ${id}`);
const todo = ids.length ? ids : VEHICLE_ORDER;

const round = (x: number, digits: number) => Math.round(x * 10 ** digits) / 10 ** digits;
const old: Record<string, VehicleStats> = (() => {
  try {
    return JSON.parse(readFileSync(FILE, 'utf8')).vehicles;
  } catch {
    return {};
  }
})();
const measured: Record<string, VehicleStats> = {};
console.log('id            0-100 km/h   top speed            lateral g                         mass      power');
for (const id of todo) {
  const s = straight(id);
  const c = CAR_SPECS[id].jet ? heldCircle(id) : skidCircle(id);
  const f = specFigures(CAR_SPECS[id]);
  const m: VehicleStats = {
    zeroTo100: s.zeroTo100 === null ? null : round(s.zeroTo100, 2),
    topSpeed: round(s.topSpeed, 1),
    lateralG: round(c.lateralG, 2),
    massKg: f.massKg,
    powerKw: f.powerKw,
  };
  measured[id] = m;
  console.log(
    `${id.padEnd(12)} ${(m.zeroTo100 === null ? '-' : m.zeroTo100.toFixed(2) + ' s').padStart(9)}   ${m.topSpeed.toFixed(1).padStart(7)} km/h (${s.seconds.toFixed(0).padStart(4)} s)  ${m.lateralG.toFixed(2)} g @ ${c.at.toFixed(0).padStart(3)} km/h (${c.end.padEnd(12)}) ${String(m.massKg).padStart(7)} kg ${String(m.powerKw).padStart(6)} kW`,
  );
}
// in the players' order (then anything measured that is not on their list), whatever was asked for; entries of
// vehicles that no longer exist are dropped
const merged: Record<string, VehicleStats> = {};
for (const id of new Set([...VEHICLE_ORDER, ...Object.keys(CAR_SPECS)])) {
  const row = measured[id] ?? old[id];
  if (row) merged[id] = row;
}
const text = JSON.stringify({ note: 'generated by tools/vehicle-stats.ts: do not edit', vehicles: merged }, null, 1) + '\n';
if (check) {
  let same = false;
  try {
    same = readFileSync(FILE, 'utf8') === text;
  } catch {
    /* no file yet */
  }
  console.log(same ? 'vehicleStats.json is up to date' : 'vehicleStats.json differs: run npx tsx tools/vehicle-stats.ts');
  process.exit(same ? 0 : 1);
}
writeFileSync(FILE, text);
console.log(`wrote ${FILE}`);
