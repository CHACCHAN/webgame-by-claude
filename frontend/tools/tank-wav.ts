/**
 * The tanks' sound (audio/tank.ts, the same code as the game's AudioWorklet 'tank' and its gun's buffers) rendered
 * in Node to listen to and to measure:
 *   npx tsx tools/tank-wav.ts <outDir> [ids] [--seed N]
 * writes, per tank (stereo, 48 kHz, 16 bit):
 *   <id>-idle / -pull / -cruise / -turn   5 s each: standing at idle; full throttle at 10 km/h; top speed at half
 *                                         throttle; a tight turn at 25 km/h
 *   <id>-run                              12 s: from idle, full throttle at 1 s up to the top speed, lifted at 9 s
 * and once: gun-105 / gun-120 / gun-125 (the shot beside the vehicle), burst-earth / burst-plate (a shell's end).
 * Prints for each: level (RMS, dBFS), peak, crest factor, octave bands (31.5 Hz – 8 kHz), the correlation of the
 * two ears; for the running sounds the strongest line under 400 Hz (the firing order or the tracks' links) and
 * how fast the synthesis runs; for the one-shots the length to −40 dB.
 */
import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { TankSynth, gunShot, shellBurst } from '../src/game/audio/tank';
import { tankSoundOf } from '../src/game/audio/TankSound';
import { CAR_SPECS, type CarId } from '../src/game/vehicle/carSpecs';
import { TANK_ORDER } from '../src/game/vehicle/tanks';
import { OCTAVES, bandLevels, psd } from './train-run-wav';

const RATE = 48000;
const BLOCK = 128;
const dB = (ms: number) => 10 * Math.log10(ms + 1e-20);

type Plan = (t: number) => { rpm: number; load: number; speed: number; turn?: number; distance?: number };

function render(id: CarId, seconds: number, plan: Plan, seed: number) {
  const synth = new TankSynth(RATE, seed, tankSoundOf(CAR_SPECS[id]));
  const n = Math.round(seconds * RATE);
  const L = new Float32Array(n), R = new Float32Array(n);
  const t0 = performance.now();
  for (let i = 0; i + BLOCK <= n; i += BLOCK) {
    const p = plan(i / RATE);
    synth.rpm = p.rpm;
    synth.load = p.load;
    synth.speed = p.speed;
    synth.turn = p.turn ?? 0;
    synth.distance = p.distance ?? 0;
    synth.process(L.subarray(i, i + BLOCK), R.subarray(i, i + BLOCK));
  }
  return { L, R, ms: performance.now() - t0 };
}

function writeWav(path: string, L: Float32Array, R: Float32Array) {
  const n = L.length, buf = Buffer.alloc(44 + n * 4);
  buf.write('RIFF', 0);
  buf.writeUInt32LE(36 + n * 4, 4);
  buf.write('WAVEfmt ', 8);
  buf.writeUInt32LE(16, 16);
  buf.writeUInt16LE(1, 20);
  buf.writeUInt16LE(2, 22);
  buf.writeUInt32LE(RATE, 24);
  buf.writeUInt32LE(RATE * 4, 28);
  buf.writeUInt16LE(4, 32);
  buf.writeUInt16LE(16, 34);
  buf.write('data', 36);
  buf.writeUInt32LE(n * 4, 40);
  for (let i = 0; i < n; i++) {
    buf.writeInt16LE(Math.round(Math.max(-1, Math.min(1, L[i])) * 32767), 44 + i * 4);
    buf.writeInt16LE(Math.round(Math.max(-1, Math.min(1, R[i])) * 32767), 46 + i * 4);
  }
  writeFileSync(path, buf);
}

const rms = (x: Float32Array, from = 0, to = x.length) => {
  let s = 0;
  for (let i = from; i < to; i++) s += x[i] * x[i];
  return s / Math.max(1, to - from);
};

function analyse(name: string, L: Float32Array, R: Float32Array, skip: number, tail: string) {
  const from = Math.round(skip * RATE);
  const l = L.subarray(from), r = R.subarray(from);
  const mid = new Float32Array(l.length);
  let peak = 0, lr = 0, ll = 0, rr = 0, bad = 0;
  for (let i = 0; i < l.length; i++) {
    mid[i] = (l[i] + r[i]) / 2;
    if (!Number.isFinite(l[i]) || !Number.isFinite(r[i])) bad++;
    peak = Math.max(peak, Math.abs(l[i]), Math.abs(r[i]));
    lr += l[i] * r[i];
    ll += l[i] * l[i];
    rr += r[i] * r[i];
  }
  const m2 = (ll + rr) / 2 / l.length;
  const bands = bandLevels(mid, RATE, OCTAVES).map((b) => b.toFixed(0).padStart(4)).join('');
  console.log(
    `${name.padEnd(20)} ${dB(m2).toFixed(1).padStart(6)} dBFS  peak ${(20 * Math.log10(peak + 1e-9)).toFixed(1).padStart(5)}  crest ${(20 * Math.log10(peak / Math.sqrt(m2) + 1e-9)).toFixed(1).padStart(4)} dB  octaves${bands}  L/R ${(lr / Math.sqrt(ll * rr + 1e-30)).toFixed(2)}${bad ? `  NOT FINITE ×${bad}` : ''}  ${tail}`,
  );
  return mid;
}

/** the strongest line below 400 Hz of a steady sound */
function line(mid: Float32Array) {
  const N = 8192, p = psd(mid, RATE, N).p;
  let best = 0, bestK = 1;
  for (let k = 3; k < (400 * N) / RATE; k++) if (p[k] > best) (best = p[k]), (bestK = k);
  return `line ${((bestK * RATE) / N).toFixed(0).padStart(3)} Hz`;
}

const args = process.argv.slice(2);
const names = args.filter((a) => !a.startsWith('--') && args[args.indexOf(a) - 1] !== '--seed');
const out = names[0] ?? '.';
const ids = (names.length > 1 ? names.slice(1) : TANK_ORDER) as CarId[];
const seed = +(args[args.indexOf('--seed') + 1] || 1) || 1;
mkdirSync(out, { recursive: true });
console.log(`octave bands: ${OCTAVES.join(' ')} Hz (dB re full scale, mid channel)`);
for (const id of ids) {
  const spec = CAR_SPECS[id], e = spec.engine, top = spec.tank!.figures.topSpeed / 3.6;
  const held: [string, Plan][] = [
    ['idle', () => ({ rpm: e.idleRpm, load: 0, speed: 0 })],
    ['pull', () => ({ rpm: e.redline * 0.8, load: 1, speed: 10 / 3.6 })],
    ['cruise', () => ({ rpm: e.redline * 0.95, load: 0.5, speed: top })],
    ['turn', () => ({ rpm: e.redline * 0.7, load: 0.7, speed: 25 / 3.6, turn: 1 })],
  ];
  for (const [name, plan] of held) {
    const r = render(id, 5, plan, seed);
    writeWav(join(out, `${id}-${name}.wav`), r.L, r.R);
    const mid = analyse(`${id} ${name}`, r.L, r.R, 1, '');
    console.log(`${''.padEnd(20)} ${line(mid)}   ×${((5 / r.ms) * 1000).toFixed(0)} real time`);
  }
  const r = render(id, 12, (t) => {
    const k = Math.min(1, Math.max(0, (t - 1) / 7));
    return { rpm: e.idleRpm + (e.redline - e.idleRpm) * Math.min(1, k * 1.6), load: t > 1 && t < 9 ? 1 : 0, speed: top * k };
  }, seed);
  writeWav(join(out, `${id}-run.wav`), r.L, r.R);
  analyse(`${id} run`, r.L, r.R, 0, '');
  console.log(`${''.padEnd(20)} level per second: ${Array.from({ length: 12 }, (_, k) => dB(rms(r.L, k * RATE, (k + 1) * RATE)).toFixed(0)).join(' ')}`);
}
const shots: [string, Float32Array][] = [
  ['gun-105', gunShot(RATE, 105)],
  ['gun-120', gunShot(RATE, 120)],
  ['gun-125', gunShot(RATE, 125)],
  ['burst-earth', shellBurst(RATE, false)],
  ['burst-plate', shellBurst(RATE, true)],
];
for (const [name, x] of shots) {
  writeWav(join(out, `${name}.wav`), x, x);
  // how long until it stays 40 dB under its peak
  let peak = 0, last = 0;
  for (let i = 0; i < x.length; i++) peak = Math.max(peak, Math.abs(x[i]));
  for (let i = 0; i < x.length; i++) if (Math.abs(x[i]) > peak * 0.01) last = i;
  analyse(name, x, x, 0, `first 50 ms ${dB(rms(x, 0, RATE * 0.05)).toFixed(1)} dBFS, to −40 dB in ${(last / RATE).toFixed(2)} s`);
}
