// Generates seed leaderboard entries (with ghosts) by letting AI drivers run the
// real simulation exactly like a player race: standing start at GO, 4 sectors.
// Output: backend/database/seeders/data/bot_runs.json
import { writeFileSync, mkdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { Track } from '../src/game/track/Track';
import { COURSES, COURSE_ORDER, type CourseId } from '../src/game/track/courses';
import { PhysicsWorld, PHYSICS_DT, initRapier } from '../src/game/vehicle/PhysicsWorld';
import { VehicleSim, emptyInput } from '../src/game/vehicle/VehicleSim';
import { CAR_SPECS, type CarId } from '../src/game/vehicle/carSpecs';
import { AIDriver, AI_PROFILES, type AILevel, type AIProfile } from '../src/game/ai/AIDriver';
import { RacingLine } from '../src/game/ai/RacingLine';
import { GhostRecorder, encodeGhost } from '../src/game/race/Ghost';

await initRapier();

type Bot = { name: string; car: CarId; profile: AIProfile; seed: number; power?: number };
const extras: Record<CourseId, Bot[]> = {
  'oboro-downhill': [
    { name: '風間 翔', car: 'hayate', profile: { ...AI_PROFILES.legend, gripUse: 0.9, sloppiness: 0.2 }, seed: 4 },
    { name: 'NIGHT_OWL', car: 'raijin', profile: { ...AI_PROFILES.ace, gripUse: 0.78 }, seed: 5 },
    { name: 'ミッドナイト白石', car: 'shiden', profile: { ...AI_PROFILES.ace, gripUse: 0.76 }, seed: 6 },
    { name: 'hairpin_k', car: 'hayate', profile: { ...AI_PROFILES.ace, gripUse: 0.7 }, seed: 7 },
  ],
  'kirifuri-lakeside': [
    { name: '湖畔のYUKI', car: 'shiden', profile: { ...AI_PROFILES.ace, gripUse: 0.84 }, seed: 8 },
    { name: '風間 翔', car: 'hayate', profile: { ...AI_PROFILES.legend, gripUse: 0.9, sloppiness: 0.2 }, seed: 9 },
    { name: 'MISTWALKER', car: 'raijin', profile: { ...AI_PROFILES.ace, gripUse: 0.7 }, seed: 10 },
  ],
  'tenrou-skyline': [
    { name: 'NIGHT_OWL', car: 'raijin', profile: { ...AI_PROFILES.ace, gripUse: 0.8 }, seed: 11 },
    { name: '稜線ハンター', car: 'shiden', profile: { ...AI_PROFILES.ace, gripUse: 0.8 }, seed: 12 },
    { name: 'hairpin_k', car: 'hayate', profile: { ...AI_PROFILES.ace, gripUse: 0.75 }, seed: 13 },
  ],
};

const out: unknown[] = [];
for (const course of COURSE_ORDER.map((id) => COURSES[id])) {
  const track = new Track(course.design);
  const line = new RacingLine(track);
  const levels: AILevel[] = ['legend', 'ace', 'rookie'];
  const bots: Bot[] = [
    ...levels.map((l, k) => ({ name: course.rivals[l].name, car: course.rivals[l].car, profile: AI_PROFILES[l], seed: k + 1, power: course.rivals[l].power })),
    ...extras[course.id],
  ];
  console.log(`--- ${course.name}`);
  for (const b of bots) {
    const physics = new PhysicsWorld(track);
    const gridS = track.startS - 6;
    const v = new VehicleSim(physics, CAR_SPECS[b.car], track.pointAt(gridS), track.headingAt(gridS));
    v.powerScale = b.power ?? 1;
    // a dry road of the course's surface (the leaderboard's bots raced on a clear night)
    v.gripScale = course.surface.grip;
    const ai = new AIDriver(track, line, b.profile, b.seed * 31);
    ai.calibrate(v);
    const input = emptyInput();
    const rec = new GhostRecorder();
    const splits: number[] = [];
    let t = 0;
    while (t < 300 && splits.length < track.sectorSplits.length) {
      ai.update(v, PHYSICS_DT, input);
      v.input = input;
      v.preStep(PHYSICS_DT);
      physics.step();
      v.postStep(PHYSICS_DT);
      t += PHYSICS_DT;
      rec.sample(t, v.position, v.quaternion, v.wheels[0].steer);
      if (ai.s >= track.sectorSplits[splits.length]) splits.push(Math.round(t * 1000));
      if (v.isFlipped || ai.needsRespawn) throw new Error(`${b.name} crashed at s=${ai.s}`);
    }
    physics.dispose();
    if (splits.length < track.sectorSplits.length) throw new Error(`${b.name} did not finish`);
    const timeMs = splits[splits.length - 1];
    const ghost = await encodeGhost(rec.data());
    console.log(`${b.name.padEnd(10)} ${b.car.padEnd(7)} ${(timeMs / 1000).toFixed(3)}s  ghost ${(ghost.data.length / 1024).toFixed(1)} KB`);
    out.push({ player_name: b.name, track_id: course.id, car_id: b.car, time_ms: timeMs, sector_ms: splits, ghost });
  }
}
const file = resolve(import.meta.dirname, '../../backend/database/seeders/data/bot_runs.json');
mkdirSync(dirname(file), { recursive: true });
writeFileSync(file, JSON.stringify(out));
console.log('wrote', file);
