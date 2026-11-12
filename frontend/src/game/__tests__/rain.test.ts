import { describe, expect, it } from 'vitest';
import { coverShare, rainBodyOf, RainSynth, type RainBody } from '../audio/rain';

const RATE = 48000;

/** render `seconds` of the rain; returns both ears and the RMS (dBFS) after the first `skip` seconds */
function render(seconds: number, set: { level?: number; speed?: number; cover?: number; body?: RainBody; seed?: number }, skip = 2) {
  const s = new RainSynth(RATE, set.seed ?? 1);
  s.level = set.level ?? 1;
  s.speed = set.speed ?? 0;
  s.cover = set.cover ?? 0;
  s.body = set.body ?? 'car';
  const n = Math.floor((seconds * RATE) / 128) * 128, L = new Float32Array(n), R = new Float32Array(n);
  for (let o = 0; o < n; o += 128) s.process(L.subarray(o, o + 128), R.subarray(o, o + 128));
  let e = 0;
  for (let i = skip * RATE; i < n; i++) e += (L[i] * L[i] + R[i] * R[i]) / 2;
  return { L, R, db: 10 * Math.log10(e / (n - skip * RATE) + 1e-20) };
}

describe('rain sound', () => {
  it('is finite and bounded for every body, speed and cover', () => {
    for (const body of ['car', 'bike', 'train', 'none'] as const)
      for (const [speed, cover] of [[0, 0], [45, 0], [25, 1]]) {
        const { L, R } = render(3, { body, speed, cover });
        let peak = 0;
        for (let i = 0; i < L.length; i++) {
          expect(Number.isFinite(L[i]) && Number.isFinite(R[i])).toBe(true);
          peak = Math.max(peak, Math.abs(L[i]), Math.abs(R[i]));
        }
        expect(peak).toBeLessThan(0.9);
      }
  });

  it('is the same for a seed and differs between seeds', () => {
    const a = render(1, { seed: 5 }), b = render(1, { seed: 5 }), c = render(1, { seed: 6 });
    expect(Array.from(a.L.subarray(40000, 40100))).toEqual(Array.from(b.L.subarray(40000, 40100)));
    expect(Array.from(a.L.subarray(40000, 40100))).not.toEqual(Array.from(c.L.subarray(40000, 40100)));
  });

  it('is silent without rain and fades in and out with it', () => {
    expect(render(3, { level: 0 }).db).toBeLessThan(-150);
    const s = new RainSynth(RATE, 3);
    const L = new Float32Array(128), R = new Float32Array(128);
    s.level = 1;
    for (let k = 0; k < 2 * 375; k++) s.process(L, R);
    s.level = 0;
    for (let k = 0; k < 8 * 375; k++) s.process(L, R);
    expect(Math.max(...L.map(Math.abs))).toBe(0);
  });

  it('stands still near the old rain\'s level, louder with speed, quieter under a roof', () => {
    const still = render(20, {}).db;
    // the filtered noise it replaced measured -24.6 dBFS (tools/rain-wav.ts); gusts move a 20 s stretch by a few dB
    expect(still).toBeGreaterThan(-29);
    expect(still).toBeLessThan(-20);
    expect(render(20, { speed: 40 }).db).toBeGreaterThan(still + 2);
    expect(render(20, { speed: 22, cover: 1 }).db).toBeLessThan(render(20, { speed: 22 }).db - 5);
  });

  it('puts the two ears apart (a diffuse field, not one noise in the middle)', () => {
    const { L, R } = render(6, {});
    let lr = 0, ll = 0, rr = 0;
    for (let i = 0; i < L.length; i++) (lr += L[i] * R[i]), (ll += L[i] * L[i]), (rr += R[i] * R[i]);
    expect(Math.abs(lr / Math.sqrt(ll * rr))).toBeLessThan(0.4);
  });

  it('knows a roof and a vehicle', () => {
    const shed = new Float32Array([0, -5, 100, -5, 100, 5, 0, 5, 6]);
    expect(coverShare(shed, 50, 1, 0)).toBe(1);
    expect(coverShare(shed, 50, 8, 0)).toBe(0);
    expect(coverShare(shed, -20, 1, 0)).toBe(0);
    expect(coverShare(shed, 2, 1, 0)).toBeCloseTo(0.8);
    expect(coverShare(new Float32Array(0), 0, 0, 0)).toBe(0);
    expect(rainBodyOf('car')).toBe('car');
    expect(rainBodyOf('creature')).toBe('none');
    expect(rainBodyOf('train')).toBe('train');
  });
});
