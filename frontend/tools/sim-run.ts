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
const track = new Track(course.design);
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
    v.gripScale = Number(process.env.GRIP ?? 1);
    v.powerScale = Number(process.env.POWER ?? 1);
    const ai = new AIDriver(track, line, AI_PROFILES[level]);
    ai.calibrate(v);
    const input = emptyInput();
    let t = 0, impacts = 0, maxSpeed = 0, flips = 0, respawns = 0, maxSlip = 0;
    let started = -1;
    const splits: number[] = [];
    while (t < 420) {
      ai.update(v, PHYSICS_DT, input);
      v.input = input;
      v.preStep(PHYSICS_DT);
      physics.step();
      v.postStep(PHYSICS_DT);
      t += PHYSICS_DT;
      if (v.impact > 0.05) impacts++;
      maxSpeed = Math.max(maxSpeed, v.speed);
      maxSlip = Math.max(maxSlip, Math.abs(v.slipAngle));
      if (started < 0 && ai.s >= track.startS) started = t;
      if (started >= 0 && splits.length < track.sectorSplits.length && ai.s >= track.sectorSplits[splits.length]) splits.push(t - started);
      if (splits.length === track.sectorSplits.length) break;
      if (v.isFlipped || ai.needsRespawn || v.position.y < -50) {
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
