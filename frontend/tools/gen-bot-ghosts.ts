// Generates seed leaderboard entries (with ghosts) by letting AI drivers run the
// real simulation exactly like a player race: standing start at GO, 4 sectors.
// Output: backend/database/seeders/data/bot_runs.json
import { writeFileSync, mkdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { Track } from '../src/game/track/Track';
import { OBORO_DOWNHILL } from '../src/game/track/courseDesign';
import { PhysicsWorld, PHYSICS_DT, initRapier } from '../src/game/vehicle/PhysicsWorld';
import { VehicleSim, emptyInput } from '../src/game/vehicle/VehicleSim';
import { CAR_SPECS, type CarId } from '../src/game/vehicle/carSpecs';
import { AIDriver, AI_PROFILES, type AIProfile } from '../src/game/ai/AIDriver';
import { RacingLine } from '../src/game/ai/RacingLine';
import { GhostRecorder, encodeGhost } from '../src/game/race/Ghost';

await initRapier();
const track = new Track(OBORO_DOWNHILL);
const line = new RacingLine(track);

const bots: { name: string; car: CarId; profile: AIProfile; seed: number }[] = [
  { name: '朧', car: 'shiden', profile: AI_PROFILES.legend, seed: 1 },
  { name: '高嶺 遼', car: 'raijin', profile: AI_PROFILES.ace, seed: 2 },
  { name: '森 健太', car: 'hayate', profile: AI_PROFILES.rookie, seed: 3 },
  { name: '風間 翔', car: 'hayate', profile: { ...AI_PROFILES.legend, gripUse: 0.9, sloppiness: 0.2 }, seed: 4 },
  { name: 'NIGHT_OWL', car: 'raijin', profile: { ...AI_PROFILES.ace, gripUse: 0.83 }, seed: 5 },
  { name: 'ミッドナイト白石', car: 'shiden', profile: { ...AI_PROFILES.ace, gripUse: 0.76 }, seed: 6 },
  { name: 'hairpin_k', car: 'hayate', profile: { ...AI_PROFILES.ace, gripUse: 0.7 }, seed: 7 },
];

const out: unknown[] = [];
for (const b of bots) {
  const physics = new PhysicsWorld(track);
  const gridS = track.startS - 6;
  const v = new VehicleSim(physics, CAR_SPECS[b.car], track.pointAt(gridS), track.headingAt(gridS));
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
  out.push({ player_name: b.name, track_id: track.design.id, car_id: b.car, time_ms: timeMs, sector_ms: splits, ghost });
}
const file = resolve(import.meta.dirname, '../../backend/database/seeders/data/bot_runs.json');
mkdirSync(dirname(file), { recursive: true });
writeFileSync(file, JSON.stringify(out));
console.log('wrote', file);
