/**
 * A train's VVVF in-train sound along a run (stand → power → coast → brake → stand) with the game's code
 * (audio/vvvf/engine.ts, the drive of vehicle/vvvf.ts) and the simulator's impulse response (public/audio/
 * vvvf-filter.wav), to listen to and measure without the browser:
 *   npx tsx tools/vvvf-train-wav.ts <trainId> <out.wav> [--os N] [--rate Hz] [--top km/h] [--coast s] [--no-ir]
 * Prints the levels per phase. The game applies the same chain (TrainSound.setVvvf: ConvolverNode, 192 kHz / rate).
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { normalizeVvvf } from '../src/game/audio/vvvf/data';
import { xorshift32 } from '../src/game/audio/vvvf/math';
import { BLOCK, SIM_RATE, VvvfEngine, oversampleFor } from '../src/game/audio/vvvf/engine';
import { trainVvvfAudio } from '../src/game/audio/vvvf/train';
import { TRAIN_INFO, type TrainId } from '../src/game/vehicle/trains';
import { SLIP_RISE, vvvfDrive } from '../src/game/vehicle/vvvf';
import { tableFiles } from './vvvf-tables';

const root = join(fileURLToPath(import.meta.url), '..', '..');

/** 16-bit PCM / float WAV → mono samples and rate */
export function readWav(buf: Buffer) {
  let p = 12, rate = 0, bits = 16, fmt = 1, ch = 1;
  while (p < buf.length - 8) {
    const id = buf.toString('ascii', p, p + 4), size = buf.readUInt32LE(p + 4);
    if (id === 'fmt ') {
      fmt = buf.readUInt16LE(p + 8);
      ch = buf.readUInt16LE(p + 10);
      rate = buf.readUInt32LE(p + 12);
      bits = buf.readUInt16LE(p + 22);
    } else if (id === 'data') {
      const n = Math.floor(size / (bits / 8) / ch);
      const out = new Float32Array(n);
      for (let i = 0; i < n; i++) {
        const o = p + 8 + i * ch * (bits / 8);
        out[i] = fmt === 3 ? buf.readFloatLE(o) : bits === 16 ? buf.readInt16LE(o) / 32768 : buf.readInt32LE(o) / 2147483648;
      }
      return { samples: out, rate };
    }
    p += 8 + size + (size & 1);
  }
  throw new Error('no data chunk');
}

export function writeWav16(path: string, x: Float32Array, rate: number) {
  const b = Buffer.alloc(44 + x.length * 2);
  b.write('RIFF', 0);
  b.writeUInt32LE(36 + x.length * 2, 4);
  b.write('WAVEfmt ', 8);
  b.writeUInt32LE(16, 16);
  b.writeUInt16LE(1, 20);
  b.writeUInt16LE(1, 22);
  b.writeUInt32LE(rate, 24);
  b.writeUInt32LE(rate * 2, 28);
  b.writeUInt16LE(2, 32);
  b.writeUInt16LE(16, 34);
  b.write('data', 36);
  b.writeUInt32LE(x.length * 2, 40);
  for (let i = 0; i < x.length; i++) b.writeInt16LE(Math.round(Math.max(-1, Math.min(1, x[i])) * 32767), 44 + i * 2);
  writeFileSync(path, b);
}

/** in-place radix-2 FFT */
function fft(re: Float64Array, im: Float64Array, inverse: boolean) {
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
    const ang = ((inverse ? 2 : -2) * Math.PI) / len;
    const wr = Math.cos(ang), wi = Math.sin(ang);
    for (let i = 0; i < n; i += len) {
      let cr = 1, ci = 0;
      for (let k = 0; k < len / 2; k++) {
        const ar = re[i + k], ai = im[i + k];
        const br = re[i + k + len / 2] * cr - im[i + k + len / 2] * ci;
        const bi = re[i + k + len / 2] * ci + im[i + k + len / 2] * cr;
        re[i + k] = ar + br;
        im[i + k] = ai + bi;
        re[i + k + len / 2] = ar - br;
        im[i + k + len / 2] = ai - bi;
        const t = cr * wr - ci * wi;
        ci = cr * wi + ci * wr;
        cr = t;
      }
    }
  }
  if (inverse) for (let i = 0; i < n; i++) (re[i] /= n), (im[i] /= n);
}

/** x ∗ h (overlap-add), same length as x */
export function convolve(x: Float32Array, h: Float32Array) {
  let n = 1;
  while (n < h.length * 4) n <<= 1;
  const step = n - h.length + 1;
  const hr = new Float64Array(n), hi = new Float64Array(n);
  hr.set(h);
  fft(hr, hi, false);
  const out = new Float32Array(x.length + h.length);
  const re = new Float64Array(n), im = new Float64Array(n);
  for (let s = 0; s < x.length; s += step) {
    re.fill(0);
    im.fill(0);
    re.set(x.subarray(s, Math.min(x.length, s + step)));
    fft(re, im, false);
    for (let i = 0; i < n; i++) {
      const r = re[i] * hr[i] - im[i] * hi[i];
      im[i] = re[i] * hi[i] + im[i] * hr[i];
      re[i] = r;
    }
    fft(re, im, true);
    for (let i = 0; i < n && s + i < out.length; i++) out[s + i] += re[i];
  }
  return out.subarray(0, x.length);
}

/** RBJ peaking EQ (Web Audio's 'peaking' BiquadFilterNode) */
export function peaking(x: Float32Array, rate: number, f0: number, q: number, db: number) {
  const A = 10 ** (db / 40), w = (2 * Math.PI * f0) / rate, al = Math.sin(w) / (2 * q), c = Math.cos(w);
  const a0 = 1 + al / A;
  const b0 = (1 + al * A) / a0, b1 = (-2 * c) / a0, b2 = (1 - al * A) / a0, a1 = (-2 * c) / a0, a2 = (1 - al / A) / a0;
  const y = new Float32Array(x.length);
  let x1 = 0, x2 = 0, y1 = 0, y2 = 0;
  for (let i = 0; i < x.length; i++) {
    const v = b0 * x[i] + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2;
    x2 = x1;
    x1 = x[i];
    y2 = y1;
    y1 = v;
    y[i] = v;
  }
  return y;
}

/** a run: [seconds, notch, km/h at the end] — power at the train's rates, coast, service brake */
export function runProfile(id: TrainId, top: number, coast: number) {
  const t = TRAIN_INFO[id];
  const [vb, vp] = t.traction ?? [40, 80];
  const accel = (v: number) => t.accel * (v <= vb ? 1 : v <= vp ? vb / v : (vb * vp) / (v * v));
  const pts: { t: number; kmh: number; notch: 1 | 0 | -1 }[] = [];
  const dt = BLOCK / 48000;
  let time = 0, v = 0;
  const push = (notch: 1 | 0 | -1) => {
    pts.push({ t: time, kmh: v, notch });
    time += dt;
  };
  while (time < 1.5) push(0);
  while (v < top) {
    push(1);
    v += accel(v) * dt;
  }
  for (const end = time + coast; time < end; ) {
    push(0);
    v = Math.max(0, v - 0.05 * dt);
  }
  // an engineer's step from coasting to the brake
  for (const end = time + 0.6; time < end; ) push(0);
  while (v > 0) {
    push(-1);
    v = Math.max(0, v - t.brake[0] * dt);
  }
  for (const end = time + 2.5; time < end; ) push(0);
  return pts;
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  const args = process.argv.slice(2);
  const opt = (name: string, d: number) => {
    const i = args.indexOf(name);
    return i >= 0 ? +args[i + 1] : d;
  };
  const [id, outPath] = args as [TrainId, string];
  const info = TRAIN_INFO[id];
  if (!info?.vvvf) throw new Error(`${id}: no VVVF`);
  const v = { ...info.vvvf, slip: opt('--slip', info.vvvf.slip), gearGain: opt('--gear', info.vvvf.gearGain ?? 0) };
  const rate = opt('--rate', 48000);
  const os = opt('--os', oversampleFor(rate));
  const data = normalizeVvvf(JSON.parse(readFileSync(join(root, 'src/game/audio/vvvf/patterns', v.pattern + '.json'), 'utf8')));
  const engine = new VvvfEngine(data, trainVvvfAudio(v), rate, os, xorshift32(), !args.includes('--free'), tableFiles(data));
  const profile = runProfile(id, opt('--top', Math.min(info.vmax, 110)), opt('--coast', 4));
  const n = profile.length * BLOCK;
  const raw = new Float32Array(n);
  let braking = false;
  // the torque builds up as in the game (TrainSound.driveVvvf)
  let slipShare = 0, lastNotch: 1 | 0 | -1 = 0;
  const t0 = performance.now();
  for (let b = 0; b < profile.length; b++) {
    const p = profile[b];
    slipShare = p.notch === 0 || p.notch !== lastNotch ? 0 : Math.min(1, slipShare + BLOCK / rate / SLIP_RISE);
    lastNotch = p.notch;
    vvvfDrive(v, info.wheel, p.kmh, p.notch, braking, engine.drive, slipShare);
    braking = engine.drive.braking;
    engine.process(raw.subarray(b * BLOCK, (b + 1) * BLOCK));
  }
  const ms = performance.now() - t0;
  let out = raw;
  if (!args.includes('--no-ir')) {
    const ir = readWav(readFileSync(join(root, 'public/audio/vvvf-filter.wav')));
    if (ir.rate !== rate) throw new Error(`IR at ${ir.rate} Hz, output ${rate} Hz`);
    // the simulator convolves at 192 kHz: the same response at `rate` sums 192000 / rate times fewer taps
    const h = ir.samples.map((s) => (s * SIM_RATE) / rate);
    out = convolve(raw, h);
  }
  // --eq dB: a peaking filter on the body resonance (as TrainSound's, Web Audio's biquad = RBJ cookbook)
  const eq = opt('--eq', 0);
  if (eq !== 0) out = peaking(out, rate, opt('--eq-hz', 230), opt('--eq-q', 0.8), eq);
  if (args.includes('--normalize')) {
    let pk = 0;
    for (const x of out) pk = Math.max(pk, Math.abs(x));
    const g = 0.89 / pk;
    for (let i = 0; i < out.length; i++) out[i] *= g;
    console.log('normalised ×', g.toFixed(3));
  }
  // levels per phase
  const phases: Record<string, number[]> = {};
  for (let b = 0; b < profile.length; b++) {
    const p = profile[b];
    const bin = opt('--bin', 20);
    const key = `${p.notch === 1 ? 'power' : p.notch === -1 ? 'brake' : 'coast'} ${Math.floor(p.kmh / bin) * bin}`;
    let s = 0, pk = 0;
    for (let i = b * BLOCK; i < (b + 1) * BLOCK; i++) (s += out[i] * out[i]), (pk = Math.max(pk, Math.abs(out[i])));
    (phases[key] ??= [0, 0, 0])[0] += s;
    phases[key][1] += BLOCK;
    phases[key][2] = Math.max(phases[key][2], pk);
  }
  for (const [k, [s, c, pk]] of Object.entries(phases)) console.log(k.padEnd(12), 'rms', Math.sqrt(s / c).toFixed(4), 'peak', pk.toFixed(4));
  console.log(`${(n / rate).toFixed(1)} s at ${rate} Hz × ${os}: ${(ms / 1000).toFixed(2)} s (${((ms * 1e6) / (n * os)).toFixed(0)} ns per calculation)`);
  writeWav16(outPath, out, rate);
}
