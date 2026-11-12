/**
 * A fighter's engine sound (audio/jet.ts, the same code as the game's AudioWorklet 'jet') rendered in Node to listen
 * to and to measure:
 *   npx tsx tools/jet-wav.ts <outDir> [--seed N]
 * writes stereo WAVs (48 kHz, 16 bit):
 *   idle / taxi / military / afterburner   6 s each at a held setting (taxi: a quarter of the spool)
 *   runup      idle, the throttle opened at 1 s (the spool takes the engine's 4 s), the afterburner lit at 6 s, 12 s
 *   away       full afterburner going away from the listener: 0 → 6 km in 26 s (the take-off after the finish)
 * and prints for each: level (RMS, dBFS), peak, crest factor, octave bands (31.5 Hz – 8 kHz), the strongest narrow
 * tone between 600 Hz and 8 kHz (the fan's whine) and how far it stands above the noise around it, the skewness of
 * the wave (crackle is one-sided: > 0 only in afterburner), the correlation of the two ears, and how fast the
 * synthesis runs. For `away`: the level in 4 s steps.
 */
import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { JetSynth } from '../src/game/audio/jet';
import { OCTAVES, bandLevels, psd } from './train-run-wav';

const RATE = 48000;
const BLOCK = 128;
const dB = (ms: number) => 10 * Math.log10(ms + 1e-20);

type Plan = (t: number) => { spool: number; ab: number; distance?: number };

function render(seconds: number, plan: Plan, seed: number) {
  const synth = new JetSynth(RATE, seed);
  const n = Math.round(seconds * RATE);
  const L = new Float32Array(n), R = new Float32Array(n);
  const t0 = performance.now();
  for (let i = 0; i + BLOCK <= n; i += BLOCK) {
    const p = plan(i / RATE);
    synth.spool = p.spool;
    synth.afterburner = p.ab;
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

function analyse(name: string, L: Float32Array, R: Float32Array, ms: number, skip = 1) {
  const from = Math.round(skip * RATE);
  const l = L.subarray(from), r = R.subarray(from);
  const mid = new Float32Array(l.length);
  let peak = 0, m2 = 0, m3 = 0, lr = 0, ll = 0, rr = 0;
  for (let i = 0; i < l.length; i++) {
    mid[i] = (l[i] + r[i]) / 2;
    peak = Math.max(peak, Math.abs(l[i]), Math.abs(r[i]));
    m2 += l[i] * l[i];
    m3 += l[i] * l[i] * l[i];
    lr += l[i] * r[i];
    ll += l[i] * l[i];
    rr += r[i] * r[i];
  }
  m2 /= l.length;
  m3 /= l.length;
  const level = dB((rms(l) + rms(r)) / 2);
  // the strongest narrow line between 600 Hz and 8 kHz against the median of the third-octave around it
  const N = 8192, p = psd(mid, RATE, N).p;
  let best = 0, bestK = 0;
  for (let k = Math.round((600 * N) / RATE); k < (8000 * N) / RATE; k++) {
    const around: number[] = [];
    for (let j = Math.round(k / 1.12); j <= k * 1.12; j++) around.push(p[j]);
    around.sort((a, b) => a - b);
    const over = p[k] / (around[around.length >> 1] + 1e-20);
    if (over > best) (best = over), (bestK = k);
  }
  const bands = bandLevels(mid, RATE, OCTAVES).map((b) => b.toFixed(0).padStart(4)).join('');
  console.log(
    `${name.padEnd(12)} ${level.toFixed(1).padStart(6)} dBFS  peak ${(20 * Math.log10(peak + 1e-9)).toFixed(1).padStart(5)}  crest ${(20 * Math.log10(peak / Math.sqrt(m2) + 1e-9)).toFixed(1).padStart(4)} dB  octaves${bands}  tone ${((bestK * RATE) / N).toFixed(0).padStart(5)} Hz +${(10 * Math.log10(best)).toFixed(0).padStart(2)} dB  skew ${(m3 / Math.pow(m2, 1.5)).toFixed(2).padStart(5)}  L/R ${(lr / Math.sqrt(ll * rr)).toFixed(2)}  ×${((L.length / RATE / ms) * 1000).toFixed(0)} real time`,
  );
}

const args = process.argv.slice(2);
const out = args.find((a) => !a.startsWith('--')) ?? '.';
const seed = +(args[args.indexOf('--seed') + 1] || 1) || 1;
mkdirSync(out, { recursive: true });
console.log(`octave bands: ${OCTAVES.join(' ')} Hz (dB re full scale, mid channel)`);
const held: [string, number, number][] = [['idle', 0, 0], ['taxi', 0.25, 0], ['military', 1, 0], ['afterburner', 1, 1]];
for (const [name, spool, ab] of held) {
  const r = render(6, () => ({ spool, ab }), seed);
  writeWav(join(out, `jet-${name}.wav`), r.L, r.R);
  analyse(name, r.L, r.R, r.ms);
}
{
  const r = render(12, (t) => ({ spool: Math.min(1, Math.max(0, (t - 1) / 4)), ab: Math.min(1, Math.max(0, (t - 6) / 1.2)) }), seed);
  writeWav(join(out, 'jet-runup.wav'), r.L, r.R);
  analyse('runup', r.L, r.R, r.ms, 0);
  console.log('  level per second: ' + Array.from({ length: 12 }, (_, k) => dB(rms(r.L, k * RATE, (k + 1) * RATE)).toFixed(0)).join(' '));
}
{
  const r = render(26, (t) => ({ spool: 1, ab: 1, distance: (6000 * t) / 26 }), seed);
  writeWav(join(out, 'jet-away.wav'), r.L, r.R);
  analyse('away', r.L, r.R, r.ms, 0);
  console.log('  level per 4 s (0 → 6 km): ' + Array.from({ length: 6 }, (_, k) => dB(rms(r.L, k * 4 * RATE, (k + 1) * 4 * RATE)).toFixed(0)).join(' '));
}
