// Headless duel: two AI cars share one physics world (solid car-to-car contact),
// the chaser starts right behind the leader. Checks that bumping never leaves a car
// stuck, flipped or unable to finish. Usage: COURSE=<id> npx tsx tools/sim-duel.ts [leadCar:level] [chaseCar:level]
import { Track } from '../src/game/track/Track';
import { COURSES, type CourseId } from '../src/game/track/courses';
import { PhysicsWorld, PHYSICS_DT, initRapier } from '../src/game/vehicle/PhysicsWorld';
import { VehicleSim, emptyInput } from '../src/game/vehicle/VehicleSim';
import { CAR_SPECS, type CarId } from '../src/game/vehicle/carSpecs';
import { AIDriver, AI_PROFILES, type AILevel } from '../src/game/ai/AIDriver';
import { RacingLine } from '../src/game/ai/RacingLine';
import type { TrackProjection } from '../src/game/track/Track';

await initRapier();
const course = COURSES[(process.env.COURSE ?? 'oboro-downhill') as CourseId];
const track = new Track(course.design);
const line = new RacingLine(track);
const parse = (a: string | undefined, d: string) => (a ?? d).split(':') as [CarId, AILevel];
const entries = [parse(process.argv[2], 'shiden:legend'), parse(process.argv[3], 'raijin:legend')];

const physics = new PhysicsWorld(track);
const cars = entries.map(([car, level], k) => {
  const s0 = track.startS - 12 - k * 8; // chaser 8 m behind, same lane
  const sim = new VehicleSim(physics, CAR_SPECS[car], track.pointAt(s0), track.headingAt(s0));
  const ai = new AIDriver(track, line, AI_PROFILES[level]);
  ai.calibrate(sim);
  const proj: TrackProjection = { index: -1, s: 0, lateral: 0, height: 0 };
  return { car, level, sim, ai, proj, input: emptyInput(), finish: -1, respawns: 0, flips: 0 };
});
let t = 0, contactSteps = 0, hits = 0, touching = false, maxDv = 0;
while (t < 480 && cars.some((c) => c.finish < 0)) {
  for (const c of cars) {
    const p = c.sim.position;
    track.project(p.x, p.y, p.z, c.proj.index, c.proj);
  }
  for (const [k, c] of cars.entries()) {
    const o = cars[1 - k];
    c.ai.opponent = { s: o.proj.s, lateral: o.proj.lateral, speed: o.sim.forwardSpeed };
    c.ai.update(c.sim, PHYSICS_DT, c.input);
    if (c.finish >= 0) {
      // park like the game's finished rival (holding the brake at a standstill would engage reverse)
      c.ai.pullOver = c.proj.lateral >= 0 ? 10 : -10;
      c.input.throttle = 0;
      c.input.brake = c.sim.forwardSpeed > 1.5 ? 0.4 : 0;
      c.input.handbrake = c.sim.forwardSpeed <= 1.5;
    }
    c.sim.input = c.input;
    c.sim.preStep(PHYSICS_DT);
  }
  physics.step();
  for (const c of cars) c.sim.postStep(PHYSICS_DT);
  t += PHYSICS_DT;
  let now = false, imp = 0;
  physics.world.contactPair(cars[0].sim.collider, cars[1].sim.collider, (m) => {
    for (let i = 0; i < m.numContacts(); i++) if (m.contactDist(i) <= 0.02 || m.contactImpulse(i) > 0) { now = true; imp = Math.max(imp, m.contactImpulse(i)); }
  });
  if (now) contactSteps++;
  if (now && !touching) hits++;
  touching = now;
  maxDv = Math.max(maxDv, imp / cars[0].sim.spec.mass);
  for (const c of cars) {
    if (c.finish < 0 && c.ai.s >= track.finishS) c.finish = t;
    if (c.finish < 0 && (c.sim.isFlipped || c.ai.needsRespawn || c.sim.position.y < -50)) {
      if (c.sim.isFlipped) c.flips++;
      c.respawns++;
      const s = Math.max(c.ai.s - 5, 0);
      c.sim.reset(track.pointAt(s), track.headingAt(s), 5);
      c.proj.index = -1;
    }
  }
}
console.log(`${course.id}  hits ${hits}  contact ${(contactSteps * PHYSICS_DT).toFixed(2)}s  max dv ${maxDv.toFixed(2)} m/s`);
for (const c of cars) {
  console.log(`  ${c.car.padEnd(7)} ${c.level.padEnd(7)} ${c.finish > 0 ? 'FINISH ' + c.finish.toFixed(2) + 's' : 'DNF at s=' + c.ai.s.toFixed(0)}  respawns ${c.respawns} flips ${c.flips}`);
}
physics.dispose();
