// Tempo and loop points of a music track: the pair of moments a whole number of bars apart whose next 8 s sound
// most alike (band-spectrum similarity), as `MUSIC` in audio/AudioEngine.ts wants them (loopFrom, loopAt).
//   node tools/music-loop.cjs <mono 11025 Hz s16 wav> [minimum loop length in s, default 60]
//   (ffmpeg -i track.mp3 -ac 1 -ar 11025 -c:a pcm_s16le mono.wav)
const fs = require('fs');
const buf = fs.readFileSync(process.argv[2]);
const MIN_LOOP = +(process.argv[3] || 60);
const data = buf.indexOf('data', 12, 'latin1') + 8, rate = buf.readUInt32LE(24);
const x = new Float32Array((buf.length - data) >> 1);
for (let i = 0; i < x.length; i++) x[i] = buf.readInt16LE(data + i * 2) / 32768;
const N = 1024, HOP = 256, BANDS = 24, dt = HOP / rate;
const win = Float32Array.from({ length: N }, (_, i) => 0.5 - 0.5 * Math.cos((2 * Math.PI * i) / N));
const edges = Array.from({ length: BANDS + 1 }, (_, b) => Math.round(2 * Math.pow((N / 2 - 1) / 2, b / BANDS)));
const frames = Math.floor((x.length - N) / HOP);
const feat = new Float32Array(frames * BANDS), onset = new Float32Array(frames);
const re = new Float32Array(N), im = new Float32Array(N);
function fft() {
  for (let i = 1, j = 0; i < N; i++) { let bit = N >> 1; for (; j & bit; bit >>= 1) j ^= bit; j ^= bit; if (i < j) { let t = re[i]; re[i] = re[j]; re[j] = t; t = im[i]; im[i] = im[j]; im[j] = t; } }
  for (let len = 2; len <= N; len <<= 1) { const a = (-2 * Math.PI) / len; for (let i = 0; i < N; i += len) for (let k = 0; k < len / 2; k++) { const c = Math.cos(a * k), s = Math.sin(a * k), ur = re[i + k], ui = im[i + k], vr = re[i + k + len / 2] * c - im[i + k + len / 2] * s, vi = re[i + k + len / 2] * s + im[i + k + len / 2] * c; re[i + k] = ur + vr; im[i + k] = ui + vi; re[i + k + len / 2] = ur - vr; im[i + k + len / 2] = ui - vi; } }
}
for (let f = 0; f < frames; f++) {
  for (let i = 0; i < N; i++) { re[i] = x[f * HOP + i] * win[i]; im[i] = 0; }
  fft();
  for (let b = 0; b < BANDS; b++) { let e = 1e-9; for (let k = edges[b]; k < Math.max(edges[b] + 1, edges[b + 1]); k++) e += re[k] * re[k] + im[k] * im[k]; feat[f * BANDS + b] = Math.log10(e); }
  if (f) { let o = 0; for (let b = 0; b < BANDS; b++) o += Math.max(0, feat[f * BANDS + b] - feat[(f - 1) * BANDS + b]); onset[f] = o; }
}
// tempo: the lag at which the onsets repeat, between 80 and 200 beats a minute
let best = 0, bestLag = 0;
for (let lag = Math.round(60 / 200 / dt); lag <= Math.round(60 / 80 / dt); lag++) { let s = 0; for (let f = lag; f < frames; f++) s += onset[f] * onset[f - lag]; s /= frames - lag; if (s > best) { best = s; bestLag = lag; } }
// (refined over 16 beats, where a frame of error in the lag shows)
let fine = bestLag * 16, fineBest = 0;
for (let lag = bestLag * 16 - 16; lag <= bestLag * 16 + 16; lag++) { let s = 0; for (let f = lag; f < frames; f++) s += onset[f] * onset[f - lag]; s /= frames - lag; if (s > fineBest) { fineBest = s; fine = lag; } }
const beat = (fine / 16) * dt, bar = beat * 4;
// the level over time, to see an intro, breakdowns and whether the end fades
const level = (t0, t1) => { let s = 0, n = 0; for (let i = Math.floor(t0 * rate); i < Math.min(x.length, Math.floor(t1 * rate)); i++) { s += x[i] * x[i]; n++; } return n ? (10 * Math.log10(s / n + 1e-12)).toFixed(1) : '-'; };
const len = x.length / rate;
console.log(`length ${len.toFixed(2)} s, tempo ${(60 / beat).toFixed(2)} bpm (bar ${bar.toFixed(3)} s)`);
console.log('level per 10 s (dB):', Array.from({ length: Math.ceil(len / 10) }, (_, k) => level(k * 10, k * 10 + 10)).join(' '));
console.log('last 6 s (dB per s):', Array.from({ length: 6 }, (_, k) => level(len - 6 + k, len - 5 + k)).join(' '));
// loop: a and b = a + n bars, compared over the 8 s that follow each
const W = Math.round(8 / dt), STEP = 4;
const sim = (fa, fb) => { let s = 0, n = 0; for (let k = 0; k < W; k += STEP) { let ab = 0, aa = 0, bb = 0; for (let b = 0; b < BANDS; b++) { const p = feat[(fa + k) * BANDS + b] + 9, q = feat[(fb + k) * BANDS + b] + 9; ab += p * q; aa += p * p; bb += q * q; const d = p - q; s -= d * d * 0.02; } s += ab / Math.sqrt(aa * bb); n++; } return s / n; };
const found = [];
for (let a = 2; a < len - MIN_LOOP - 9; a += 0.05) {
  const fa = Math.round(a / dt);
  for (let n = Math.ceil(MIN_LOOP / bar); a + n * bar < len - 8.5; n++) { const b = a + n * bar, fb = Math.round(b / dt); if (fb + W >= frames) break; found.push({ a, b, bars: n, s: sim(fa, fb) }); }
}
found.sort((p, q) => q.s - p.s);
const shown = [];
for (const c of found) { if (shown.every((d) => Math.abs(d.a - c.a) > 2 || Math.abs(d.b - c.b) > 2)) shown.push(c); if (shown.length === 6) break; }
for (const c of shown) console.log(`loopFrom ${c.a.toFixed(2)}  loopAt ${c.b.toFixed(2)}  (${c.bars} bars, ${(c.b - c.a).toFixed(1)} s)  likeness ${c.s.toFixed(4)}`);
