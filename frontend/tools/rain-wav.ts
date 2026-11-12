/**
 * The rain's sound (audio/rain.ts, the same code as the game's AudioWorklet 'rain') and the filtered noise it
 * replaced, rendered in Node to listen to, look at and measure:
 *   npx tsx tools/rain-wav.ts <outDir> [--seed N]
 * writes stereo WAVs and spectrogram PNGs (log frequency 40 Hz–20 kHz over time; under it the level in 50 ms steps):
 *   old-still   the old rain (one 2 s noise buffer looped, band-pass 5.2 kHz, mono), 20 s
 *   new-still   standing in full rain in a car, 20 s
 *   new-runup   0 → 150 km/h over 15 s, then 8 s at 150
 *   new-cover   80 km/h through a 200 m rock shed (under it from ~9 to ~18 s)
 *   new-bike / new-train / new-roach   100 km/h, 10 s
 *   new-weather the rain coming (at 1 s) and going (at 8 s), 14 s
 * and prints for each: level (RMS, dBFS), octave bands, crest factor, the correlation of the two ears (all, and
 * above 1 kHz), the level over time in 0.5 s windows (spread), the modulation spectrum of the envelope
 * (0.125–16 Hz, octaves), how alike the sound is 2 s later (the old loop repeats exactly), and the synthesis' speed.
 *   npx tsx tools/rain-wav.ts --analyse <file.wav> — the same measurements of any stereo or mono WAV.
 */
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { deflateSync } from 'node:zlib';
import { coverShare, RainSynth, type RainBody } from '../src/game/audio/rain';
import { rng } from '../src/game/util/math';
import { psd } from './train-run-wav';

const RATE = 48000;
const BLOCK = 128;
const dB = (ms: number) => 10 * Math.log10(ms + 1e-20);

// ------------------------------------------------------------------ the old rain (AudioEngine.setRain before)
/** WebAudio's biquads (Audio EQ Cookbook as the spec gives them: a lowpass' Q in dB, a bandpass' Q plain) */
function biquad(type: 'bandpass' | 'lowpass', f: number, q: number) {
  const w = (2 * Math.PI * f) / RATE, c = Math.cos(w);
  const alpha = type === 'lowpass' ? Math.sin(w) / (2 * Math.pow(10, q / 20)) : Math.sin(w) / (2 * q);
  const a0 = 1 + alpha;
  const [b0, b1, b2] = type === 'lowpass' ? [(1 - c) / 2, 1 - c, (1 - c) / 2] : [alpha, 0, -alpha];
  let x1 = 0, x2 = 0, y1 = 0, y2 = 0;
  return (x: number) => {
    const y = (b0 * x + b1 * x1 + b2 * x2 - (-2 * c) * y1 - (1 - alpha) * y2) / a0;
    x2 = x1;
    x1 = x;
    y2 = y1;
    y1 = y;
    return y;
  };
}

/** the old chain: a 2 s buffer of white noise looped → band-pass 5200 Hz Q 0.5 → low-pass 9 kHz → gain 0.16 × level (eased 0.5 s); mono */
function renderOld(seconds: number, level: (t: number) => number, seed: number) {
  const r = rng(seed), buf = new Float32Array(RATE * 2);
  for (let i = 0; i < buf.length; i++) buf[i] = r() * 2 - 1;
  const bp = biquad('bandpass', 5200, 0.5), lp = biquad('lowpass', 9000, 1);
  const n = Math.round(seconds * RATE), out = new Float32Array(n);
  let g = 0;
  const k = 1 - Math.exp(-1 / (0.5 * RATE));
  for (let i = 0; i < n; i++) {
    g += (0.16 * level(i / RATE) - g) * k;
    out[i] = lp(bp(buf[i % buf.length])) * g;
  }
  return { L: out, R: out, ms: 0 };
}

// ------------------------------------------------------------------ the new rain
interface Plan {
  level: (t: number) => number;
  speed: (t: number) => number;
  cover?: (t: number) => number;
  body: RainBody;
}

function renderNew(seconds: number, plan: Plan, seed: number) {
  const syn = new RainSynth(RATE, seed);
  const n = Math.floor((seconds * RATE) / BLOCK) * BLOCK, L = new Float32Array(n), R = new Float32Array(n);
  syn.body = plan.body;
  const t0 = performance.now();
  for (let o = 0; o < n; o += BLOCK) {
    const t = o / RATE;
    syn.level = plan.level(t);
    syn.speed = plan.speed(t);
    syn.cover = plan.cover?.(t) ?? 0;
    syn.process(L.subarray(o, o + BLOCK), R.subarray(o, o + BLOCK));
  }
  return { L, R, ms: performance.now() - t0 };
}

// ------------------------------------------------------------------ measurements
const OCT = [63, 125, 250, 500, 1000, 2000, 4000, 8000, 16000];

/** first-order high-pass (for the correlation above ~1 kHz) */
function highpass(x: Float32Array, f: number) {
  const a = Math.exp((-2 * Math.PI * f) / RATE), y = new Float32Array(x.length);
  let px = 0, py = 0;
  for (let i = 0; i < x.length; i++) {
    py = a * (py + x[i] - px);
    px = x[i];
    y[i] = py;
  }
  return y;
}

function corr(a: Float32Array, b: Float32Array) {
  let ab = 0, aa = 0, bb = 0;
  for (let i = 0; i < a.length; i++) (ab += a[i] * b[i]), (aa += a[i] * a[i]), (bb += b[i] * b[i]);
  return ab / Math.sqrt(aa * bb + 1e-30);
}

function analyse(name: string, L: Float32Array, R: Float32Array, skip = 0) {
  const s = Math.round(skip * RATE);
  L = L.subarray(s);
  R = R.subarray(s);
  const n = L.length;
  let ms = 0, peak = 0;
  for (let i = 0; i < n; i++) {
    ms += (L[i] * L[i] + R[i] * R[i]) / 2;
    peak = Math.max(peak, Math.abs(L[i]), Math.abs(R[i]));
  }
  ms /= n;
  const pl = psd(L, RATE), pr = psd(R, RATE);
  const bands = OCT.map((f) => {
    let e = 0;
    for (let k = 0; k < pl.p.length; k++) {
      const fk = k * pl.df;
      if (fk >= f / Math.SQRT2 && fk < f * Math.SQRT2) e += (pl.p[k] + pr.p[k]) / 2;
    }
    return dB(e);
  });
  // level over time: 0.5 s windows
  const W = RATE / 2, lev: number[] = [];
  for (let o = 0; o + W <= n; o += W) {
    let e = 0;
    for (let i = o; i < o + W; i++) e += (L[i] * L[i] + R[i] * R[i]) / 2;
    lev.push(dB(e / W));
  }
  const mean = lev.reduce((a, b) => a + b, 0) / Math.max(1, lev.length);
  const sd = Math.sqrt(lev.reduce((a, b) => a + (b - mean) ** 2, 0) / Math.max(1, lev.length));
  // modulation spectrum: the power envelope in 10 ms frames (100 Hz), relative to its mean, octave bands
  const F = RATE / 100, env: number[] = [];
  for (let o = 0; o + F <= n; o += F) {
    let e = 0;
    for (let i = o; i < o + F; i++) e += (L[i] * L[i] + R[i] * R[i]) / 2;
    env.push(e / F);
  }
  let N = 1;
  while (N * 2 <= env.length) N *= 2;
  const em = env.slice(0, N), avg = em.reduce((a, b) => a + b, 0) / N;
  const x = new Float32Array(N);
  for (let i = 0; i < N; i++) x[i] = em[i] / (avg + 1e-30) - 1;
  const mp = psd(x, 100, Math.min(N, 2048));
  const modBands = [0.125, 0.25, 0.5, 1, 2, 4, 8, 16].map((f) => {
    let e = 0;
    for (let k = 1; k < mp.p.length; k++) {
      const fk = k * mp.df;
      if (fk >= f / Math.SQRT2 && fk < f * Math.SQRT2) e += mp.p[k];
    }
    return dB(e);
  });
  // repetition: correlation with itself 2 s later
  const lag = 2 * RATE;
  const rep = n > lag * 2 ? corr(L.subarray(0, n - lag), L.subarray(lag)) : NaN;
  const hl = highpass(L, 1000), hr = highpass(R, 1000);
  // A-weighted level from the octave bands (the ear's loudness, roughly)
  const AW = [-26.2, -16.1, -8.6, -3.2, 0, 1.2, 1, -1.1, -6.6];
  const dBA = dB(bands.reduce((a, b, i) => a + Math.pow(10, (b + AW[i]) / 10), 0));
  const r = {
    name,
    rms: +dB(ms).toFixed(1),
    dBA: +dBA.toFixed(1),
    crest: +(20 * Math.log10(peak / Math.sqrt(ms + 1e-30))).toFixed(1),
    corr: +corr(L, R).toFixed(2),
    corrHi: +corr(hl, hr).toFixed(2),
    levelSpread: +sd.toFixed(2),
    levelRange: [+Math.min(...lev).toFixed(1), +Math.max(...lev).toFixed(1)],
    repeat2s: +rep.toFixed(3),
    octaves: bands.map((b) => +b.toFixed(1)),
    modulation: modBands.map((b) => +b.toFixed(1)),
  };
  console.log(`\n== ${name}`);
  console.log(`  level ${r.rms} dBFS (A-weighted ${r.dBA})   crest ${r.crest} dB   L/R correlation ${r.corr} (above 1 kHz ${r.corrHi})   alike 2 s later ${r.repeat2s}`);
  console.log(`  level over 0.5 s windows: ${r.levelRange[0]} … ${r.levelRange[1]} dB, spread ${r.levelSpread} dB`);
  console.log(`  octaves ${OCT.map((f, i) => `${f >= 1000 ? f / 1000 + 'k' : f}:${r.octaves[i]}`).join(' ')}`);
  console.log(`  modulation (dB, 0.125…16 Hz) ${[0.125, 0.25, 0.5, 1, 2, 4, 8, 16].map((f, i) => `${f}:${r.modulation[i]}`).join(' ')}`);
  return { r, lev };
}

// ------------------------------------------------------------------ files
function writeWavStereo(path: string, L: Float32Array, R: Float32Array) {
  const n = L.length, b = Buffer.alloc(44 + n * 4);
  b.write('RIFF', 0);
  b.writeUInt32LE(36 + n * 4, 4);
  b.write('WAVEfmt ', 8);
  b.writeUInt32LE(16, 16);
  b.writeUInt16LE(1, 20);
  b.writeUInt16LE(2, 22);
  b.writeUInt32LE(RATE, 24);
  b.writeUInt32LE(RATE * 4, 28);
  b.writeUInt16LE(4, 32);
  b.writeUInt16LE(16, 34);
  b.write('data', 36);
  b.writeUInt32LE(n * 4, 40);
  const q = (v: number) => Math.round(Math.max(-1, Math.min(1, v)) * 32767);
  for (let i = 0; i < n; i++) {
    b.writeInt16LE(q(L[i]), 44 + i * 4);
    b.writeInt16LE(q(R[i]), 46 + i * 4);
  }
  writeFileSync(path, b);
}

function readWavStereo(buf: Buffer) {
  let p = 12, ch = 1, bits = 16;
  while (p < buf.length - 8) {
    const id = buf.toString('ascii', p, p + 4), size = buf.readUInt32LE(p + 4);
    if (id === 'fmt ') (ch = buf.readUInt16LE(p + 10)), (bits = buf.readUInt16LE(p + 22));
    else if (id === 'data') {
      const n = Math.floor(size / (bits / 8) / ch), L = new Float32Array(n), R = new Float32Array(n);
      for (let i = 0; i < n; i++) {
        const o = p + 8 + i * ch * 2;
        L[i] = buf.readInt16LE(o) / 32768;
        R[i] = buf.readInt16LE(o + (ch > 1 ? 2 : 0)) / 32768;
      }
      return { L, R };
    }
    p += 8 + size + (size & 1);
  }
  throw new Error('no data chunk');
}

const CRC = new Int32Array(256).map((_, n) => {
  let c = n;
  for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
  return c;
});
function crc32(b: Buffer) {
  let c = -1;
  for (let i = 0; i < b.length; i++) c = CRC[(c ^ b[i]) & 255] ^ (c >>> 8);
  return (c ^ -1) >>> 0;
}
function writePng(path: string, w: number, h: number, rgb: Uint8Array) {
  const chunk = (type: string, data: Buffer) => {
    const len = Buffer.alloc(4);
    len.writeUInt32BE(data.length);
    const td = Buffer.concat([Buffer.from(type, 'ascii'), data]);
    const crc = Buffer.alloc(4);
    crc.writeUInt32BE(crc32(td));
    return Buffer.concat([len, td, crc]);
  };
  const raw = Buffer.alloc((w * 3 + 1) * h);
  for (let y = 0; y < h; y++) {
    raw[y * (w * 3 + 1)] = 0;
    Buffer.from(rgb.buffer, rgb.byteOffset + y * w * 3, w * 3).copy(raw, y * (w * 3 + 1) + 1);
  }
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(w, 0);
  ihdr.writeUInt32BE(h, 4);
  ihdr[8] = 8;
  ihdr[9] = 2;
  writeFileSync(path, Buffer.concat([Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), chunk('IHDR', ihdr), chunk('IDAT', deflateSync(raw)), chunk('IEND', Buffer.alloc(0))]));
}

/** heat colours 0…1 (black → blue → magenta → orange → white) */
function heat(v: number): [number, number, number] {
  const stops = [[0, 0, 0], [20, 30, 110], [150, 40, 150], [240, 130, 40], [255, 250, 220]];
  const x = Math.max(0, Math.min(0.9999, v)) * (stops.length - 1), k = Math.floor(x), f = x - k;
  return [0, 1, 2].map((c) => stops[k][c] + (stops[k + 1][c] - stops[k][c]) * f) as [number, number, number];
}

/** spectrogram of the left ear: 20 ms columns, 220 rows log 40 Hz–20 kHz, 75 dB range from -100 dBFS; level strip under it */
function spectrogram(path: string, x: Float32Array) {
  const N = 2048, hop = RATE / 50, cols = Math.floor((x.length - N) / hop), rows = 220, strip = 70;
  const w = new Float64Array(N);
  for (let i = 0; i < N; i++) w[i] = 0.5 - 0.5 * Math.cos((2 * Math.PI * i) / N);
  const img = new Uint8Array(cols * (rows + strip) * 3);
  const re = new Float64Array(N), im = new Float64Array(N);
  const lo = Math.log(40), hi = Math.log(20000);
  const levels: number[] = [];
  for (let c = 0; c < cols; c++) {
    im.fill(0);
    let e = 0;
    for (let i = 0; i < N; i++) re[i] = x[c * hop + i] * w[i];
    for (let i = 0; i < hop; i++) e += x[c * hop + i] ** 2;
    levels.push(dB(e / hop));
    fftInPlace(re, im);
    for (let r = 0; r < rows; r++) {
      const f0 = Math.exp(lo + ((hi - lo) * (rows - 1 - r)) / rows), f1 = Math.exp(lo + ((hi - lo) * (rows - r)) / rows);
      const k0 = Math.max(1, Math.floor((f0 * N) / RATE)), k1 = Math.max(k0 + 1, Math.ceil((f1 * N) / RATE));
      let p = 0;
      for (let k = k0; k < k1; k++) p += re[k] * re[k] + im[k] * im[k];
      const db = dB((p / (k1 - k0)) / (N * N * 0.375 * 0.25));
      const [R, G, B] = heat((db + 100) / 75);
      const o = (r * cols + c) * 3;
      img[o] = R;
      img[o + 1] = G;
      img[o + 2] = B;
    }
    // level strip: -60…-10 dBFS
    const y = Math.round(((levels[c] + 10) / -50) * (strip - 1));
    for (let s = 0; s < strip; s++) {
      const o = ((rows + s) * cols + c) * 3, on = s === Math.max(0, Math.min(strip - 1, y));
      img[o] = img[o + 1] = img[o + 2] = on ? 230 : s % 10 === 0 ? 40 : 12;
    }
  }
  // second marks along the top
  for (let c = 0; c < cols; c += 50) for (let r = 0; r < 4; r++) img[(r * cols + c) * 3] = img[(r * cols + c) * 3 + 1] = img[(r * cols + c) * 3 + 2] = 255;
  writePng(path, cols, rows + strip, img);
}

function fftInPlace(re: Float64Array, im: Float64Array) {
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

// ------------------------------------------------------------------ main
const args = process.argv.slice(2);
if (args[0] === '--analyse') {
  const { L, R } = readWavStereo(readFileSync(args[1]));
  analyse(args[1], L, R);
} else {
  const out = args[0] ?? '.';
  const seed = args.includes('--seed') ? Number(args[args.indexOf('--seed') + 1]) : 7;
  mkdirSync(out, { recursive: true });
  const full = () => 1;
  // a rock shed from 200 m to 400 m, 12 m wide, slab at 6 m; the car at 80 km/h along +x, the listener 1.2 m up
  const shed = new Float32Array([200, -6, 400, -6, 400, 6, 200, 6, 6]);
  const v80 = 80 / 3.6;
  const runs: [string, number, () => { L: Float32Array; R: Float32Array; ms: number }, number][] = [
    ['old-still', 23, () => renderOld(23, full, seed), 3],
    ['new-still', 23, () => renderNew(23, { level: full, speed: () => 0, body: 'car' }, seed), 3],
    ['new-runup', 23, () => renderNew(23, { level: full, speed: (t) => (Math.min(t, 15) / 15) * (150 / 3.6), body: 'car' }, seed), 0],
    ['new-cover', 27, () => renderNew(27, { level: full, speed: () => v80, cover: (t) => coverShare(shed, t * v80, 1.2, 0), body: 'car' }, seed), 0],
    ['new-bike', 13, () => renderNew(13, { level: full, speed: () => 100 / 3.6, body: 'bike' }, seed), 3],
    ['new-train', 13, () => renderNew(13, { level: full, speed: () => 100 / 3.6, body: 'train' }, seed), 3],
    ['new-roach', 13, () => renderNew(13, { level: full, speed: () => 100 / 3.6, body: 'none' }, seed), 3],
    ['new-weather', 14, () => renderNew(14, { level: (t) => (t > 1 && t < 8 ? 1 : 0), speed: () => 0, body: 'car' }, seed), 0],
  ];
  const summary: Record<string, unknown> = {};
  for (const [name, secs, render, skip] of runs) {
    const { L, R, ms } = render();
    writeWavStereo(join(out, `${name}.wav`), L, R);
    spectrogram(join(out, `${name}.png`), L);
    const { r, lev } = analyse(name, L, R, skip);
    if (ms) console.log(`  synthesis: ${(secs / (ms / 1000)).toFixed(0)}× real time (${((ms * 1000) / ((secs * RATE) / BLOCK)).toFixed(1)} µs per 128-sample block)`);
    if (name === 'new-runup' || name === 'new-cover' || name === 'new-weather') console.log(`  level per second: ${lev.filter((_, i) => i % 2 === 0).map((l) => l.toFixed(1)).join(' ')}`);
    summary[name] = r;
  }
  writeFileSync(join(out, 'summary.json'), JSON.stringify(summary, null, 1));
}
