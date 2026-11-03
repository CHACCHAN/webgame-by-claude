/**
 * A train's running noise (audio/running.ts, the same code as the game's AudioWorklet) rendered in Node, to listen
 * to and measure:
 *   npx tsx tools/train-run-wav.ts <trainId> <outDir> [--speeds 20,40,60,80,110,200,300] [--seconds 8] [--top km/h] [--seed N]
 * writes <id>-<km/h>.wav at steady speeds (those up to the train's top speed), <id>-runup.wav (stand → power to
 * --top at the train's rates → coast → service brake → stand) and <id>-curve.wav (35 km/h through a tight curve:
 * the flange squeal), and prints per speed the level, the octave bands, the joint rhythm and, at the reference
 * speeds, the difference from the recordings the synthesis was fitted to.
 *   npx tsx tools/train-run-wav.ts --analyse <file.wav> — the same measurements of any WAV.
 */
import { mkdirSync } from 'node:fs';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { RunningNoise, runningParams } from '../src/game/audio/running';
import { TRAIN_INFO, type TrainId } from '../src/game/vehicle/trains';
import { readWav, writeWav16 } from './vvvf-train-wav';

export const OCTAVES = [31.5, 63, 125, 250, 500, 1000, 2000, 4000, 8000];

/**
 * The recordings the game used to play (Wikimedia Commons, deleted since), measured over the whole loop: octave
 * band levels and total (dBFS) as the game mixed them (half level). Commuter: a 223 series coasting at ~110 km/h
 * (Kosei line); sealed: a 700 series Shinkansen on board at ~203 km/h.
 */
export const RECORDED = {
  commuter: { kmh: 110, rms: -21.9, octaves: [-43.3, -32.1, -27.7, -30.1, -28.8, -28.9, -34.8, -38.0, -50.9] },
  sealed: { kmh: 203, rms: -22.7, octaves: [-38.0, -24.8, -27.8, -38.0, -49.5, -56.9, -56.7, -69.1, -77.2] },
};

function fft(re: Float64Array, im: Float64Array) {
  const n = re.length;
  for (let i = 1, j = 0; i < n; i++) {
    let bit = n >> 1;
    for (; j & bit; bit >>= 1) j ^= bit;
    j ^= bit;
    if (i < j) {
      [re[i], re[j]] = [re[j], re[i]];
      [im[i], im[j]] = [im[j], im[i]];
    }
  }
  for (let len = 2; len <= n; len <<= 1) {
    const ang = (-2 * Math.PI) / len, wr = Math.cos(ang), wi = Math.sin(ang);
    for (let i = 0; i < n; i += len) {
      let cr = 1, ci = 0;
      for (let k = 0; k < len / 2; k++) {
        const a = i + k, b = a + len / 2;
        const br = re[b] * cr - im[b] * ci, bi = re[b] * ci + im[b] * cr;
        re[b] = re[a] - br;
        im[b] = im[a] - bi;
        re[a] += br;
        im[a] += bi;
        const t = cr * wr - ci * wi;
        ci = cr * wi + ci * wr;
        cr = t;
      }
    }
  }
}

/** Welch power spectrum (mean square per bin, Hann, half overlap) */
export function psd(x: Float32Array, rate: number, N = 8192) {
  const w = new Float64Array(N);
  let w2 = 0;
  for (let i = 0; i < N; i++) (w[i] = 0.5 - 0.5 * Math.cos((2 * Math.PI * i) / N)), (w2 += w[i] * w[i]);
  const p = new Float64Array(N / 2 + 1);
  let frames = 0;
  const re = new Float64Array(N), im = new Float64Array(N);
  for (let s = 0; s + N <= x.length; s += N / 2, frames++) {
    im.fill(0);
    for (let i = 0; i < N; i++) re[i] = x[s + i] * w[i];
    fft(re, im);
    for (let k = 0; k <= N / 2; k++) p[k] += ((re[k] * re[k] + im[k] * im[k]) * (k && k < N / 2 ? 2 : 1)) / (N * w2);
  }
  for (let k = 0; k <= N / 2; k++) p[k] /= Math.max(1, frames);
  return { p, df: rate / N };
}

const dB = (ms: number) => 10 * Math.log10(ms + 1e-20);

/** level (dBFS) per band of width `per` octaves around each centre */
export function bandLevels(x: Float32Array, rate: number, centres: number[], per = 1) {
  const { p, df } = psd(x, rate);
  return centres.map((f) => {
    let s = 0;
    for (let k = 1; k < p.length; k++) if (k * df >= f * 2 ** (-per / 2) && k * df < f * 2 ** (per / 2)) s += p[k];
    return dB(s);
  });
}

/**
 * Joint-like events: peaks of the 40–250 Hz energy (5 ms frames) at least `over` dB above the median of the
 * surrounding second; times (s) and heights (dB).
 */
export function events(x: Float32Array, rate: number, over = 7) {
  const y = new Float32Array(x.length);
  const a = Math.exp((-2 * Math.PI * 40) / rate), b = Math.exp((-2 * Math.PI * 250) / rate);
  for (let i = 0, hp = 0, px = 0, lp = 0; i < x.length; i++) {
    hp = a * (hp + x[i] - px);
    px = x[i];
    lp = (1 - b) * hp + b * lp;
    y[i] = lp;
  }
  const hop = Math.round(rate * 0.005), e: number[] = [];
  for (let s = 0; s + hop <= y.length; s += hop) {
    let m = 0;
    for (let i = s; i < s + hop; i++) m += y[i] * y[i];
    e.push(dB(m / hop));
  }
  const W = 100, out: [number, number][] = [];
  for (let i = W; i < e.length - W; i++) {
    let top = true;
    for (let j = i - 6; j <= i + 6 && top; j++) if (e[j] > e[i]) top = false;
    if (!top) continue;
    const med = e.slice(i - W, i + W).sort((u, v) => u - v)[W];
    if (e[i] - med > over) out.push([i * 0.005, e[i] - med]);
  }
  return out;
}

/** a joint click's spectrum: third-octave levels of 43 ms windows at `times` against the whole signal (dB) */
export function clickSpectrum(x: Float32Array, rate: number, times: number[], centres: number[]) {
  const N = 2048, all = psd(x, rate, N);
  const acc = new Float64Array(all.p.length);
  let n = 0;
  for (const t of times) {
    const s = Math.round((t - 0.01) * rate);
    if (s < 0 || s + N > x.length) continue;
    const { p } = psd(x.subarray(s, s + N), rate, N);
    for (let k = 0; k < p.length; k++) acc[k] += p[k];
    n++;
  }
  return centres.map((f) => {
    let a = 0, b = 0;
    for (let k = 1; k < acc.length; k++) if (k * all.df >= f * 2 ** (-1 / 6) && k * all.df < f * 2 ** (1 / 6)) (a += acc[k] / n), (b += all.p[k]);
    return 10 * Math.log10(a / b);
  });
}

export function report(x: Float32Array, rate: number, label: string, ref?: { rms: number; octaves: number[] }) {
  let ms = 0;
  for (const v of x) ms += v * v;
  const oct = bandLevels(x, rate, OCTAVES);
  const ev = events(x, rate);
  const gaps = ev.slice(1).map((v, i) => v[0] - ev[i][0]);
  const f = (v: number) => v.toFixed(1).padStart(6);
  console.log(`${label}: rms ${dB(ms / x.length).toFixed(1)} dBFS${ref ? ` (recording ${ref.rms})` : ''}, ${(ev.length / (x.length / rate)).toFixed(2)} joint-like events/s`);
  console.log('  octave  ' + OCTAVES.map((o) => String(o).padStart(6)).join(''));
  console.log('  dBFS    ' + oct.map(f).join(''));
  if (ref) {
    console.log('  recorded' + ref.octaves.map(f).join(''));
    console.log('  diff    ' + oct.map((v, i) => f(v - ref.octaves[i])).join(''));
  }
  if (gaps.length) console.log('  event gaps (s)', gaps.slice(0, 16).map((g) => g.toFixed(3)).join(' '));
  return { oct, ev };
}

/** one steady speed: samples and the click times */
export function renderSteady(id: TrainId, kmh: number, seconds: number, rate = 48000, seed = 1, lateral = 0) {
  const sim = new RunningNoise(runningParams(TRAIN_INFO[id]), rate, seed);
  const clicks: number[] = [];
  sim.onClick = (n) => clicks.push(n / rate);
  sim.kmh = kmh;
  sim.lateral = lateral;
  const x = new Float32Array(Math.round(seconds * rate));
  // settle the eased speed first
  const pre = new Float32Array(128);
  for (let i = 0; i < 100; i++) sim.process(pre);
  clicks.length = 0;
  for (let s = 0; s < x.length; s += 128) sim.process(x.subarray(s, Math.min(x.length, s + 128)));
  return { x, clicks: clicks.map((t) => t - (100 * 128) / rate) };
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  const args = process.argv.slice(2);
  const opt = (name: string, d: string) => {
    const i = args.indexOf(name);
    return i >= 0 ? args[i + 1] : d;
  };
  if (args[0] === '--analyse') {
    const { samples, rate } = readWav(readFileSync(args[1]));
    report(samples, rate, args[1]);
    process.exit(0);
  }
  const [id, outDir] = args as [TrainId, string];
  const info = TRAIN_INFO[id];
  if (!info) throw new Error(`no train ${id}`);
  mkdirSync(outDir, { recursive: true });
  const rate = 48000, seconds = +opt('--seconds', '8'), seed = +opt('--seed', '1');
  const p = runningParams(info);
  const ref = p.sealed ? RECORDED.sealed : RECORDED.commuter;
  console.log(`${id}: joints every ${p.jointSpacing} m, axles ${p.axle} m apart, bogie centres ${info.bogies} m, cars ${info.carLength} m, wind ${p.wind}${p.sealed ? ', sealed body' : ''}`);
  for (const kmh of opt('--speeds', '20,40,60,80,110,200,300').split(',').map(Number)) {
    if (kmh > info.vmax * 1.05) continue;
    const { x, clicks } = renderSteady(id, kmh, seconds, rate, seed);
    report(x, rate, `${kmh} km/h`, kmh === ref.kmh ? ref : undefined);
    const gaps = clicks.slice(1, 13).map((t, i) => (t - clicks[i]).toFixed(3));
    if (clicks.length) console.log(`  clicks: ${clicks.length} in ${seconds} s, first at ${clicks[0].toFixed(3)} s, gaps ${gaps.join(' ')}`);
    writeWav16(join(outDir, `${id}-${kmh}.wav`), x, rate);
  }
  // the run-up: stand, power at the train's rates (constant torque, then power), coast, service brake, stand
  {
    const top = +opt('--top', String(Math.min(info.vmax, 120)));
    const sim = new RunningNoise(p, rate, seed);
    const [vb, vp] = info.traction ?? [40, 80];
    const accel = (v: number) => info.accel * (v <= vb ? 1 : v <= vp ? vb / v : (vb * vp) / (v * v));
    const out: number[] = [];
    const block = new Float32Array(128), dt = 128 / rate;
    let v = 0, t = 0, phase = 0, coast = 0;
    while (phase < 4) {
      if (phase === 0 && t > 1) phase = 1;
      if (phase === 1 && (v += accel(v) * dt) >= top) (phase = 2), (coast = t);
      if (phase === 2 && t > coast + 4) phase = 3;
      if (phase === 3 && (v = Math.max(0, v - info.brake[0] * dt)) === 0) (phase = 4), (coast = t);
      sim.kmh = v;
      sim.brake = phase === 3 ? 0.6 : 0;
      sim.process(block);
      for (const s of block) out.push(s);
      t += dt;
    }
    for (let i = 0; i < 2 * rate; i += 128) {
      sim.kmh = 0;
      sim.process(block);
      for (const s of block) out.push(s);
    }
    writeWav16(join(outDir, `${id}-runup.wav`), Float32Array.from(out), rate);
    console.log(`run-up to ${top} km/h: ${(out.length / rate).toFixed(1)} s`);
  }
  // a tight curve at 35 km/h: radius 60 m for 4 s in the middle (lateral acceleration v² / r)
  {
    const sim = new RunningNoise(p, rate, seed);
    const out = new Float32Array(10 * rate);
    sim.kmh = 35;
    for (let s = 0; s < out.length; s += 128) {
      const t = s / rate;
      sim.lateral = t > 3 && t < 7 ? (35 / 3.6) ** 2 / 60 : 0;
      sim.process(out.subarray(s, s + 128));
    }
    writeWav16(join(outDir, `${id}-curve.wav`), out, rate);
  }
}
