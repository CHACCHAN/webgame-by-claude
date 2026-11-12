/**
 * Where the rain stands against a vehicle's own sound in the game's mix: is it a bed under the drive, or on top?
 *   npx tsx tools/rain-mix.ts <outDir> [vehicle ids…] [--wet]
 * For each vehicle (default: one or two of every kind of sound):
 *  1. the game's simulation on a flat pad (Node, as tools/vehicle-stats.ts) gives what the sound is driven with at
 *     a standstill and when a full-throttle run passes 60, 120, 200 km/h and settles at its top speed: revs, boost,
 *     a train's tractive effort;
 *  2. Chrome renders the game's own sound chain offline (`__renderMix`, ui/GameCanvas.tsx: AudioEngine, the vehicle's
 *     sound, the wind, updated 60 times a second as Game.update does), 5 s per state: under power (throttle 1) and
 *     coasting (throttle 0) at each speed. Taken before the master's compressor, with master and effects at 100 %
 *     (the defaults, master 80 %, move everything by −1.9 dB alike);
 *  3. the rain (audio/rain.ts in Node, the worklet's code; tools/rain-wav.ts `rainLevel`: full rain, gusts held
 *     still) for the vehicle's kind at the same speeds. Both enter the same effects bus, so the figures compare.
 * Printed and written to <outDir>/mix.json: A-weighted levels (dB(A) re full scale, tools/rain-wav.ts `levels`) of
 * the vehicle's own sound (`own`: engine / inverter and running noise / legs), of that with the shared wind
 * (`drive`), of the rain in the open and under a roof; the rain over the drive (positive: the rain is the louder
 * of the two) and in how many of the octaves 250 Hz…8 kHz the rain lies above the drive (there it covers it).
 * Vehicle renders are kept in <outDir>/vehicles.json and reused (they change only with the vehicles' sounds:
 * `--fresh` renders them again), so after a change of the rain only Node runs.
 * `--wet` also renders each vehicle with the rain in Chrome and gives what is heard after the compressor, dry and
 * in the rain: how much the rain adds to the whole.
 * Needs `vite preview` of a build (`URL`, default http://127.0.0.1:4193/) and Chrome on the GPU:
 *   ~/.local/opt/quality/gpurun.sh URL=… npx tsx tools/rain-mix.ts <outDir>
 */
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { join } from 'node:path';
import { Vector3 } from 'three';
import { rainBodyOf } from '../src/game/audio/rain';
import { CAR_SPECS, type CarId } from '../src/game/vehicle/carSpecs';
import { kindOf } from '../src/game/vehicle/kinds';
import { RAPIER, initRapier, groups, GROUP_GROUND, GROUP_CAR, PHYSICS_DT, type PhysicsWorld } from '../src/game/vehicle/PhysicsWorld';
import { VehicleSim, emptyInput } from '../src/game/vehicle/VehicleSim';
import { GUST_PEAK, OCT, gustsAdd, levels, rainLevel, rainOverTime } from './rain-wav';

const RATE = 48000;
/** seconds per state, and from when it is measured (a train's effort builds up over 1.2 s after a notch) */
const HOLD = 5, FROM = 1.8;
const SPEEDS = [60, 120, 200];
const DEFAULT: CarId[] = ['hayate', 'r34', 'u9', 'nsr250r', 'hayabusa', 'keikyu1000', 'e235', 'e5', 'l0', 'roach'];

interface State {
  kmh: number;
  mode: 'idle' | 'power' | 'coast';
  rpm: number;
  boost: number;
}
interface Level {
  rms: number;
  dBA: number;
  octaves: number[];
}
interface Measured extends State {
  own: Level;
  drive: Level;
  /** what is heard (after the compressor), dry and in the rain */
  heard?: number;
  heardWet?: number;
}

/** what drives the sound at a standstill, as a full-throttle run passes each speed, and at the speed it settles at */
function states(id: CarId): State[] {
  const world = new RAPIER.World({ x: 0, y: -9.81, z: 0 });
  world.timestep = PHYSICS_DT;
  world.createCollider(RAPIER.ColliderDesc.cuboid(30000, 1, 30000).setTranslation(0, -1, 0).setCollisionGroups(groups(GROUP_GROUND, GROUP_CAR)));
  const v = new VehicleSim({ world } as unknown as PhysicsWorld, CAR_SPECS[id], new Vector3(0, 0, 0), 0);
  const input = emptyInput();
  const step = () => {
    v.input = input;
    v.preStep(PHYSICS_DT);
    world.step();
    v.postStep(PHYSICS_DT);
  };
  for (let t = 0; t < 1.5; t += PHYSICS_DT) step();
  const out: State[] = [{ kmh: 0, mode: 'idle', rpm: v.rpm, boost: 0 }];
  const at = (kmh: number) => {
    out.push({ kmh, mode: 'power', rpm: v.rpm, boost: v.boost }, { kmh, mode: 'coast', rpm: v.rpm, boost: 0 });
  };
  input.throttle = 1;
  const want = [...SPEEDS];
  let top = 0, mark = 0, markT = 0;
  for (let t = 0; t < 1800; t += PHYSICS_DT) {
    step();
    const kmh = v.forwardSpeed * 3.6;
    if (want.length && kmh >= want[0]) at(want.shift()!);
    top = Math.max(top, kmh);
    // settled: less than 0.2 km/h gained in 20 s
    if (t - markT >= 20) {
      if (top - mark < 0.2) break;
      mark = top;
      markT = t;
    }
    if (v.position.z > 10000) {
      const p = v.body.translation();
      v.body.setTranslation({ x: p.x, y: p.y, z: p.z - 20000 }, true);
    }
  }
  // (not once more where a listed speed is the top speed)
  if (!SPEEDS.some((s) => Math.abs(s - top) < 5)) at(Math.round(top));
  world.free();
  return out;
}

const f1 = (x: number, w = 6) => x.toFixed(1).padStart(w);

async function main() {
  const args = process.argv.slice(2);
  const flags = args.filter((a) => a.startsWith('--')), rest = args.filter((a) => !a.startsWith('--'));
  const out = rest[0] ?? '.';
  const ids = (rest.length > 1 ? rest.slice(1) : DEFAULT) as CarId[];
  const wet = flags.includes('--wet');
  mkdirSync(out, { recursive: true });
  const cacheFile = join(out, 'vehicles.json');
  const cache: Record<string, Measured[]> = !flags.includes('--fresh') && existsSync(cacheFile) ? JSON.parse(readFileSync(cacheFile, 'utf8')) : {};
  await initRapier();

  // ---- the vehicles' own sound: Chrome, the game's chain
  const todo = ids.filter((id) => !cache[id] || (wet && cache[id][0].heardWet === undefined));
  if (todo.length) {
    const require = createRequire(import.meta.url);
    const { chromium } = require(process.env.PW_MODULE ?? 'playwright-core');
    const browser = await chromium.launch({
      executablePath: process.env.CHROME ?? '/usr/bin/google-chrome',
      // the host GPU (as tools/vvvf-game-wav.ts): with software rendering the title scene starves the main thread,
      // which has to answer every suspend of the offline render
      args: ['--autoplay-policy=no-user-gesture-required', '--ignore-gpu-blocklist', '--use-angle=vulkan', '--enable-features=Vulkan'],
    });
    const page = await browser.newPage({ viewport: { width: 640, height: 360 } });
    page.on('console', (m: { type(): string; text(): string }) => m.type() === 'error' && console.log('page:', m.text()));
    page.on('pageerror', (e: Error) => console.log('page error:', e.message));
    await page.goto(`${process.env.URL ?? 'http://127.0.0.1:4193/'}?export=1`);
    await page.waitForFunction(() => '__renderMix' in window, null, { timeout: 120000 });
    const render = async (id: CarId, plan: number[][], o: { pick: number[]; rain?: number }) => {
      const { b64, ms } = (await page.evaluate(
        ([id, plan, o]: [string, number[][], unknown]) =>
          (window as unknown as { __renderMix: (id: string, plan: unknown, o: unknown) => Promise<{ b64: string; ms: number }> }).__renderMix(id, plan, o),
        [id, plan, o] as [string, number[][], unknown],
      )) as { b64: string; ms: number };
      const bytes = Buffer.from(b64, 'base64');
      const all = new Float32Array(bytes.buffer, bytes.byteOffset, bytes.length / 4), n = all.length / o.pick.length;
      return { ch: o.pick.map((_, k) => all.subarray(k * n, (k + 1) * n)), ms };
    };
    for (const id of todo) {
      const st = states(id);
      const plan: number[][] = [];
      st.forEach((s, k) => {
        for (let i = 0; i < HOLD * 60; i++) plan.push([k * HOLD + i / 60, s.rpm, s.mode === 'power' ? 1 : 0, s.boost, 0, s.kmh / 3.6]);
      });
      const cut = (x: Float32Array, k: number) => x.subarray(Math.round((k * HOLD + FROM) * RATE), (k + 1) * HOLD * RATE);
      // dry: what is heard (0; mono sources: one ear is both), the master before the compressor (2, 3), the vehicle alone (4)
      const dry = await render(id, plan, { pick: [0, 2, 3, 4] });
      const m: Measured[] = st.map((s, k) => ({
        ...s,
        own: levels(cut(dry.ch[3], k)),
        drive: levels(cut(dry.ch[1], k), cut(dry.ch[2], k)),
        heard: levels(cut(dry.ch[0], k)).dBA,
      }));
      let note = `${id}: ${st.length} states, dry ${(dry.ms / 1000).toFixed(1)} s`;
      if (wet) {
        const w = await render(id, plan, { pick: [0, 1], rain: 1 });
        m.forEach((s, k) => (s.heardWet = levels(cut(w.ch[0], k), cut(w.ch[1], k)).dBA));
        note += `, in the rain ${(w.ms / 1000).toFixed(1)} s`;
      }
      console.log(note);
      cache[id] = m;
      writeFileSync(cacheFile, JSON.stringify(cache));
    }
    await browser.close();
  }

  // ---- the rain at the same speeds (Node), and the table
  const gust = gustsAdd();
  const rains = new Map<string, { open: ReturnType<typeof rainOverTime>; roof: Level }>();
  const rainAt = (id: CarId, kmh: number) => {
    const body = rainBodyOf(kindOf(CAR_SPECS[id])), key = `${body}|${kmh}`;
    if (!rains.has(key)) rains.set(key, { open: rainOverTime(body, kmh), roof: rainLevel(body, kmh, 1) });
    return rains.get(key)!;
  };
  // octaves 250 Hz … 8 kHz: where both a drive and the rain have their sound
  const mid = OCT.map((f, i) => (f >= 250 && f <= 8000 ? i : -1)).filter((i) => i >= 0);
  const rows: Record<string, unknown>[] = [];
  const r1 = (x: number) => +x.toFixed(1);
  console.log('\nA-weighted levels, dB(A) re full scale, before the compressor (master and effects 100 %), full rain.');
  console.log(`rain: over a long time (the gusts add ${gust.toFixed(1)} dB to the rain outside); gust: in a gust's peak (+${GUST_PEAK} dB outside); roof: gusts held still`);
  console.log('vehicle      rain on  km/h  state    own   drive |   rain  −drive   gust −drive  octaves over | under a roof −drive' + (wet ? ' | heard dry  in rain  rain adds' : ''));
  for (const id of ids) {
    const body = rainBodyOf(kindOf(CAR_SPECS[id]));
    for (const s of cache[id]) {
      const r = rainAt(id, s.kmh);
      // (the octaves with the gusts held still, lifted as the whole is over a long time)
      const over = mid.filter((i) => r.open.octaves[i] + r.open.long - r.open.still > s.drive.octaves[i]).length;
      const row = {
        id, body, kmh: s.kmh, state: s.mode, own: r1(s.own.dBA), drive: r1(s.drive.dBA), rain: r1(r.open.long), rainOverDrive: r1(r.open.long - s.drive.dBA),
        gustOverDrive: r1(r.open.peak - s.drive.dBA), octavesOver: over, roof: r1(r.roof.dBA), roofOverDrive: r1(r.roof.dBA - s.drive.dBA),
        ...(s.heardWet !== undefined && s.heard !== undefined ? { heard: r1(s.heard), heardWet: r1(s.heardWet), rainAdds: r1(s.heardWet - s.heard) } : {}),
      };
      rows.push(row);
      console.log(
        `${id.padEnd(12)} ${body.padEnd(6)} ${String(s.kmh).padStart(5)}  ${s.mode.padEnd(5)} ${f1(s.own.dBA)}  ${f1(s.drive.dBA)} | ${f1(r.open.long)}  ${f1(row.rainOverDrive)}        ${f1(row.gustOverDrive)}     ${over} of ${mid.length}      |    ${f1(r.roof.dBA)}  ${f1(row.roofOverDrive)}` +
          (wet && row.heard !== undefined ? ` |   ${f1(row.heard)}   ${f1(row.heardWet!)}    ${f1(row.rainAdds!)}` : ''),
      );
    }
  }
  writeFileSync(join(out, 'mix.json'), JSON.stringify(rows, null, 1));
  // the summary a decision needs: per state of driving, the rain over the drive across the vehicles
  for (const mode of ['idle', 'coast', 'power'] as const) {
    const of = rows.filter((r) => r.state === mode);
    const d = of.map((r) => r.rainOverDrive as number).sort((a, b) => a - b);
    const louder = of.filter((r) => (r.rainOverDrive as number) > 0).map((r) => `${r.id} ${r.kmh}`);
    if (d.length) console.log(`rain − drive over a long time, ${mode.padEnd(5)}: ${f1(d[0])} … ${f1(d[d.length - 1])} dB, median ${f1(d[d.length >> 1])}; the rain is the louder in ${louder.length} of ${d.length}${louder.length && louder.length <= 12 ? ` (${louder.join(', ')})` : ''}`);
  }
}

await main();
