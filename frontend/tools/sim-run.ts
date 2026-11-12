// Headless simulation: AI drivers run the full course on the real vehicle
// physics. Used for tuning and as a drivability check of the course.
import { Track } from '../src/game/track/Track';
import { COURSES, type CourseId } from '../src/game/track/courses';
import { PhysicsWorld, PHYSICS_DT, initRapier } from '../src/game/vehicle/PhysicsWorld';
import { VehicleSim, emptyInput } from '../src/game/vehicle/VehicleSim';
import { CAR_SPECS, type CarId } from '../src/game/vehicle/carSpecs';
import { AIDriver, AI_PROFILES, type AILevel } from '../src/game/ai/AIDriver';
import { RacingLine } from '../src/game/ai/RacingLine';

await initRapier();
const course = COURSES[(process.env.COURSE ?? 'oboro-downhill') as CourseId];
// AI_TOP=<m/s> overrides the course's AI speed cap (e.g. to see what an uncapped run takes)
const track = new Track(process.env.AI_TOP ? { ...course.design, aiTopSpeed: Number(process.env.AI_TOP) } : course.design);
console.log('course', course.id, 'length', track.length.toFixed(0));
const line = new RacingLine(track);
const pairs = process.argv[2] === 'rivals'
  ? ([['hayate', 'rookie'], ['raijin', 'ace'], ['shiden', 'legend']] as [CarId, AILevel][])
  : ((process.argv[2] ?? 'hayate,raijin,shiden').split(',') as CarId[]).flatMap((c) => ((process.argv[3] ?? 'rookie,ace,legend').split(',') as AILevel[]).map((l) => [c, l] as [CarId, AILevel]));

for (const [car, level] of pairs) {
  {
    const physics = new PhysicsWorld(track);
    const start = track.pointAt(track.startS - 12);
    const v = new VehicleSim(physics, CAR_SPECS[car], start, track.headingAt(track.startS - 12));
    // the course's surface (GRIP=<factor> overrides it)
    const baseGrip = Number(process.env.GRIP ?? course.surface.grip);
    v.gripScale = baseGrip;
    let proj = track.project(start.x, start.y, start.z);
    let strayed = false;
    v.powerScale = Number(process.env.POWER ?? 1);
    const ai = new AIDriver(track, line, AI_PROFILES[level]);
    ai.calibrate(v);
    const input = emptyInput();
    let t = 0, impacts = 0, maxSpeed = 0, flips = 0, respawns = 0, maxSlip = 0, lastLog = -1, lastTrace = -1e9;
    const prevVel = v.velocity.clone();
    let started = -1;
    const splits: number[] = [];
    while (t < (+process.env.LIMIT! || 420)) {
      ai.update(v, PHYSICS_DT, input);
      // the ground under the tyres, as the game sets it (`Game.trackRacer`)
      if (track.design.zoneGrip || track.design.verge) {
        proj = track.project(v.position.x, v.position.y, v.position.z, proj.index, proj);
        v.gripScale = baseGrip * track.surfaceGrip(proj.index, proj.lateral, v.position.x, v.position.z);
        v.rollScale = track.surfaceRoll(proj.index, proj.lateral, v.position.x, v.position.z);
        if (track.design.verge && Math.abs(proj.lateral) > track.width[proj.index] / 2 - 2) strayed = true;
      }
      v.input = input;
      v.preStep(PHYSICS_DT);
      physics.step();
      v.postStep(PHYSICS_DT);
      t += PHYSICS_DT;
      if (v.impact > 0.05) impacts++;
      const prevVelNext = v.velocity.clone();
      // DEBUG=1: where it goes wrong (hard impacts, big slides, a tipped body)
      if (process.env.DEBUG && (v.impact > 0.3 || Math.abs(v.slipAngle) > 1 || v.up.y < 0.7) && t - lastLog > 0.25) {
        lastLog = t;
        const d = v.velocity.clone().sub(prevVel).divideScalar(PHYSICS_DT);
        const fwd = d.dot(v.forward), up = d.dot(v.up);
        const pj = track.project(v.position.x, v.position.y, v.position.z);
        console.log(`  t ${t.toFixed(2)} s ${ai.s.toFixed(0)} lat ${pj.lateral.toFixed(2)}/${(track.widthAt(pj.s) / 2).toFixed(2)} ${(v.speed * 3.6).toFixed(0)} km/h impact ${v.impact.toFixed(2)} slip ${(v.slipAngle * 57.3).toFixed(0)}° up.y ${v.up.y.toFixed(2)} grounded ${v.wheels.filter((w) => w.grounded).length} steer ${input.steer.toFixed(2)} thr ${input.throttle.toFixed(2)} brake ${input.brake.toFixed(2)} acc fwd ${fwd.toFixed(0)} up ${up.toFixed(0)} side ${Math.sqrt(Math.max(0, d.lengthSq() - fwd * fwd - up * up)).toFixed(0)} comp ${v.wheels.map((w) => w.compression.toFixed(2)).join('/')}`);
      }
      // TRACE=<seconds>: a line every so often (where it is, how fast against what it aims for, what it does)
      if (process.env.TRACE && t - lastTrace >= Number(process.env.TRACE)) {
        lastTrace = t;
        const want = (ai as unknown as { speeds: Float32Array }).speeds[Math.min(track.count - 1, Math.max(0, Math.round(ai.s)))];
        console.log(`  t ${t.toFixed(1)} s ${ai.s.toFixed(0)} ${track.zoneAt(ai.s) ?? '-'} lat ${proj.lateral.toFixed(1)} v ${(v.speed * 3.6).toFixed(0)} want ${(want * 3.6).toFixed(0)} steer ${input.steer.toFixed(2)} thr ${input.throttle.toFixed(2)} brk ${input.brake.toFixed(2)} slip ${(v.slipAngle * 57.3).toFixed(0)}° lift ${(v.liftShare * 100).toFixed(0)}%`);
      }
      prevVel.copy(prevVelNext);
      maxSpeed = Math.max(maxSpeed, v.speed);
      maxSlip = Math.max(maxSlip, Math.abs(v.slipAngle));
      if (started < 0 && ai.s >= track.startS) started = t;
      if (started >= 0 && splits.length < track.sectorSplits.length && ai.s >= track.sectorSplits[splits.length]) splits.push(t - started);
      if (splits.length === track.sectorSplits.length) break;
      if (v.isFlipped || ai.needsRespawn || v.position.y < -50 || strayed) {
        strayed = false;
        proj.index = -1;
        if (process.env.TRACE) console.log(`  RESPAWN t ${t.toFixed(1)} s ${ai.s.toFixed(0)} lat ${proj.lateral.toFixed(1)} v ${(v.speed * 3.6).toFixed(0)} flipped ${v.isFlipped} stuck ${ai.needsRespawn}`);
        if (v.isFlipped) flips++;
        respawns++;
        const s = Math.max(ai.s - 5, 0);
        v.reset(track.pointAt(s), track.headingAt(s), 5);
      }
    }
    const done = splits.length === track.sectorSplits.length;
    console.log(
      `${car.padEnd(7)} ${level.padEnd(7)} ${done ? 'FINISH ' + splits[splits.length - 1].toFixed(2) + 's' : 'DNF at s=' + ai.s.toFixed(0)}  ` +
        `splits ${splits.map((x) => x.toFixed(1)).join('/')}  vmax ${(maxSpeed * 3.6).toFixed(0)}km/h  impacts ${impacts}  respawns ${respawns} flips ${flips} maxSlip ${(maxSlip * 57.3).toFixed(0)}°`,
    );
    physics.dispose();
  }
}
