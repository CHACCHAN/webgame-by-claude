import { describe, expect, it } from 'vitest';
import { FREE, GONE, PLACED, bind, createCloud, project, rng, stepCloud, type Shape } from '../cloud';
import { calm, createFluid, divergence, flowAt, project as settle, splat, stepFluid } from '../fluid';
import { TONE, courseRelief, maskShape, medalShape } from '../shapes';

const palette = new Float32Array(9 * 3).fill(1);
const run = (c: ReturnType<typeof createCloud>, seconds: number) => {
  for (let i = 0; i < seconds * 60; i++) stepCloud(c, 1 / 60);
};
const count = (c: ReturnType<typeof createCloud>, state: number) => c.state.reduce((sum, s) => sum + (s === state ? 1 : 0), 0);
/** a square of points, one unit wide, around the shape's middle */
const square = (n: number): Shape => {
  const points = new Float32Array(n * 3), rand = rng(5);
  for (let k = 0; k < n; k++) {
    points[k * 3] = rand() - 0.5;
    points[k * 3 + 1] = rand() - 0.5;
  }
  return { points, tone: 1, loose: 0, size: 1, gain: 1 };
};

describe('the grains', () => {
  it('are not there while nothing is shown: nothing lives, nothing is lit, a step changes nothing', () => {
    const c = createCloud(3200, 1280, 720, palette);
    run(c, 2);
    expect(c.live).toBe(0);
    expect(count(c, GONE)).toBe(c.n);
    expect(c.look.every((b) => b === 0)).toBe(true);
    expect(c.pos.every((v) => v === 0)).toBe(true);
  });

  it('condense around a thing from close by, one after another, and stay in it', () => {
    const c = createCloud(3200, 1280, 720, palette);
    Object.assign(c.place, { x: 640, y: 360, scale: 200 });
    const shape = square(c.n);
    bind(c, shape);
    stepCloud(c, 1 / 60);
    // the first of them are there, dark still, near the thing (not from all over the screen)
    expect(c.live).toBeGreaterThan(0);
    expect(c.live).toBeLessThan(c.n * 0.2);
    for (let i = 0; i < c.n; i++) {
      if (c.state[i] !== PLACED) continue;
      expect(Math.abs(c.pos[i * 3] - 640)).toBeLessThan(100 + 720 * 0.2);
      expect(Math.abs(c.pos[i * 3 + 1] - 360)).toBeLessThan(100 + 720 * 0.2);
      expect(c.lum[i]).toBeLessThan(0.4);
    }
    run(c, 3);
    expect(c.live).toBe(c.n);
    let off = 0;
    for (let i = 0; i < c.n; i++) {
      const k = (i % c.n) * 3;
      off = Math.max(off, Math.hypot(c.pos[i * 3] - 640 - shape.points[k] * 200, c.pos[i * 3 + 1] - 360 - shape.points[k + 1] * 200, c.pos[i * 3 + 2]));
      expect(c.lum[i]).toBeGreaterThan(0.9);
    }
    expect(off).toBeLessThan(2);
  });

  it('come apart and are gone within two seconds when the thing is let go', () => {
    const c = createCloud(3200, 1280, 720, palette);
    Object.assign(c.place, { x: 640, y: 360, scale: 200 });
    bind(c, square(c.n));
    run(c, 3);
    bind(c, null);
    run(c, 0.3);
    // on their way out: fainter, and no longer where they were
    expect(count(c, FREE)).toBeGreaterThan(c.n * 0.5);
    let lit = 0;
    for (let i = 0; i < c.n; i++) lit += c.lum[i];
    expect(lit / c.n).toBeLessThan(0.75);
    run(c, 1.7);
    expect(c.live).toBe(0);
    expect(count(c, GONE)).toBe(c.n);
    for (let i = 0; i < c.n; i++) expect(c.look[i * 8 + 3]).toBe(0);
    // and they never went far (ink that thins out, not sparks)
    for (let i = 0; i < c.n; i++) expect(Math.hypot(c.pos[i * 3] - 640, c.pos[i * 3 + 1] - 360)).toBeLessThan(330);
  });

  it('move over to another thing without going out', () => {
    const c = createCloud(1600, 1280, 720, palette);
    Object.assign(c.place, { x: 400, y: 360, scale: 100 });
    bind(c, square(c.n));
    run(c, 3);
    c.place.x = 900;
    bind(c, square(c.n));
    for (let k = 0; k < 120; k++) {
      stepCloud(c, 1 / 60);
      expect(c.live).toBe(c.n);
      expect(count(c, FREE)).toBe(0);
    }
    for (let i = 0; i < c.n; i++) expect(Math.abs(c.pos[i * 3] - 900)).toBeLessThan(60);
  });

  it('fill a shape only as far as asked, and the rest is not there', () => {
    const c = createCloud(3200, 1280, 720, palette);
    Object.assign(c.place, { x: 640, y: 360, scale: 100, fill: 0.3 });
    bind(c, square(c.n));
    run(c, 3);
    expect(count(c, PLACED) / c.n).toBeGreaterThan(0.22);
    expect(count(c, PLACED) / c.n).toBeLessThan(0.38);
    expect(count(c, GONE)).toBe(c.n - count(c, PLACED));
    c.place.fill = 1;
    run(c, 2);
    expect(count(c, PLACED)).toBe(c.n);
  });

  it('turn and size with the shape as it is placed', () => {
    const c = createCloud(1600, 1000, 1000, palette);
    // one point, one unit to the right of the shape's middle
    const shape: Shape = { points: Float32Array.of(1, 0, 0), tone: 1, loose: 0, size: 1, gain: 1 };
    Object.assign(c.place, { x: 500, y: 500, z: 0, scale: 100, yaw: Math.PI / 2, pitch: 0 });
    bind(c, shape);
    run(c, 3);
    // a quarter turn about the upright axis: the point is before or behind the middle now, at the same height
    expect(c.pos[0]).toBeCloseTo(500, 0);
    expect(c.pos[1]).toBeCloseTo(500, 0);
    expect(Math.abs(c.pos[2])).toBeCloseTo(100, 0);
    // what is farther is drawn nearer the middle and smaller
    const out: [number, number, number] = [0, 0, 0];
    project(c, 900, 500, 400, out);
    expect(out[0]).toBeLessThan(900);
    expect(out[2]).toBeLessThan(1);
  });

  it('are carried off by a stroke through the water and come home when it rests', () => {
    const c = createCloud(3200, 1280, 720, palette);
    Object.assign(c.place, { x: 640, y: 360, scale: 200 });
    const shape = square(c.n);
    bind(c, shape);
    run(c, 3);
    const away = () => {
      let sum = 0, far = 0;
      for (let i = 0; i < c.n; i++) {
        const k = i * 3, d = Math.hypot(c.pos[k] - 640 - shape.points[k] * 200, c.pos[k + 1] - 360 - shape.points[k + 1] * 200);
        sum += d;
        far = Math.max(far, d);
      }
      return { mean: sum / c.n, far };
    };
    expect(away().far).toBeLessThan(2);
    // a quick stroke from left to right through the middle of the picture
    for (let k = 0; k < 12; k++) {
      splat(c.fluid, 560 + k * 14, 360, 840 * 0.6, 0, 54);
      stepCloud(c, 1 / 60);
    }
    run(c, 0.3);
    const stirred = away();
    expect(stirred.far).toBeGreaterThan(25);
    expect(stirred.far).toBeLessThan(260);
    expect(stirred.mean).toBeGreaterThan(3);
    // nobody was lost on the way, and all of them are lit
    expect(c.live).toBe(c.n);
    run(c, 5);
    expect(c.fluid.still).toBe(true);
    expect(away().far).toBeLessThan(2);
  });
});

describe('the water', () => {
  it('is at rest until it is stirred, and a step then costs nothing', () => {
    const f = createFluid(1280, 720);
    expect(f.still).toBe(true);
    stepFluid(f, 1 / 60);
    expect(f.u.every((v) => v === 0)).toBe(true);
    // a stroke that does not move stirs nothing
    splat(f, 640, 360, 0, 0, 50);
    expect(f.still).toBe(true);
  });

  it('flows where it is pushed, and back around on both sides: two eddies', () => {
    const f = createFluid(1280, 720);
    for (let k = 0; k < 10; k++) {
      splat(f, 640, 360, 500, 0, 50);
      stepFluid(f, 1 / 60);
    }
    const at: [number, number] = [0, 0];
    expect(flowAt(f, 660, 360, at)[0]).toBeGreaterThan(150);
    // beside the stroke the water comes back the other way, the same on both sides
    const above = flowAt(f, 640, 250, [0, 0])[0], below = flowAt(f, 640, 470, [0, 0])[0];
    expect(above).toBeLessThan(-4);
    expect(below).toBeLessThan(-4);
    expect(Math.abs(above - below)).toBeLessThan(Math.abs(above) * 0.2);
    // before the stroke it parts to both sides
    expect(flowAt(f, 760, 320, [0, 0])[1]).toBeLessThan(-2);
    expect(flowAt(f, 760, 400, [0, 0])[1]).toBeGreaterThan(2);
  });

  it('keeps what flows into a place equal to what flows out of it', () => {
    const f = createFluid(1280, 720);
    splat(f, 640, 360, 600, 200, 60);
    const before = divergence(f);
    settle(f, 60);
    // (not to nothing: the solve is the cheap one, exact only for what is wider than two cells)
    expect(divergence(f)).toBeLessThan(before * 0.25);
    // and in a run, step after step
    calm(f);
    let worst = 0, pushed = 0;
    for (let k = 0; k < 90; k++) {
      if (k < 20) {
        splat(f, 300 + k * 30, 360 + Math.sin(k) * 80, 700, Math.cos(k) * 300, 55);
        pushed = Math.max(pushed, divergence(f));
      }
      stepFluid(f, 1 / 60);
      if (k >= 20) worst = Math.max(worst, divergence(f));
    }
    // (the flow carrying itself makes a little anew every step: a third of what the strokes put in, at most)
    expect(worst).toBeLessThan(pushed * 0.33);
  });

  it('dies down by itself, never runs away, and is still again', () => {
    const f = createFluid(1280, 720);
    let fastest = 0;
    for (let k = 0; k < 600; k++) {
      // (a pointer thrown about, far faster than the water may flow)
      if (k < 60) splat(f, 200 + ((k * 97) % 900), 100 + ((k * 53) % 500), 20000 * Math.cos(k), 20000 * Math.sin(k * 1.7), 60);
      stepFluid(f, 1 / 60);
      for (let o = 0; o < f.u.length; o++) {
        const s = Math.hypot(f.u[o], f.v[o]);
        expect(Number.isFinite(s)).toBe(true);
        if (s > fastest) fastest = s;
      }
    }
    expect(fastest).toBeGreaterThan(300);
    expect(fastest).toBeLessThan(1400);
    expect(f.still).toBe(true);
    expect(f.u.every((v) => v === 0)).toBe(true);
  });
});

describe('the shapes of grains', () => {
  it('a course relief has a bright road inside a unit box, land around it, beams at both ends', () => {
    // a straight road that drops 200 m over 2 km, on a tilted plane with a lake at its foot
    const count = 2000, pos = new Float32Array(count * 3);
    for (let k = 0; k < count; k++) {
      pos[k * 3] = 100;
      pos[k * 3 + 1] = 300 - k * 0.1;
      pos[k * 3 + 2] = k;
    }
    const s = courseRelief({ count, pos, startS: 100, finishS: 1900, base: (_x, z) => 300 - z * 0.1, water: 120 }, 6000, rng(5));
    const tones = [...s.tones!];
    expect(tones.filter((t) => t === TONE.cyan).length).toBeGreaterThan(900);
    expect(tones.filter((t) => t === TONE.green).length).toBeGreaterThan(60);
    expect(tones.filter((t) => t === TONE.amber).length).toBeGreaterThan(60);
    expect(tones.filter((t) => t === TONE.deep).length).toBeGreaterThan(20);
    for (let i = 0; i < 6000; i++) {
      // (white is the road's sparkle and the high ground's lines: cyan is the road alone)
      if (s.tones![i] !== TONE.cyan) continue;
      // (it lies across the picture: along x, the start on the left)
      expect(Math.abs(s.points[i * 3 + 2])).toBeLessThan(0.02);
      expect(Math.abs(s.points[i * 3])).toBeLessThan(0.51);
      expect(s.lum![i]).toBe(1);
    }
    // the start is high (up the screen: negative) and on the left, the finish low and on the right
    const mean = (tone: number, axis: number) => {
      let sum = 0, m = 0;
      for (let i = 0; i < 6000; i++) if (s.tones![i] === tone) { sum += s.points[i * 3 + axis]; m++; }
      return sum / m;
    };
    expect(mean(TONE.green, 0)).toBeLessThan(mean(TONE.amber, 0) - 0.8);
    // the course's own place in the picture: as wide as the road is long, around the middle
    expect(s.box![2]).toBeGreaterThan(0.95);
    expect(s.box![2]).toBeLessThan(1.15);
    expect(Math.abs(s.box![0])).toBeLessThan(0.05);
    expect(mean(TONE.green, 1)).toBeLessThan(mean(TONE.amber, 1));
  });

  it('a mask becomes grains inside it only, brighter along its edges', () => {
    // a filled square in the middle of a 40 × 40 mask
    const w = 40, h = 40, alpha = new Uint8Array(w * h);
    for (let y = 10; y < 30; y++) for (let x = 10; x < 30; x++) alpha[y * w + x] = 255;
    const s = maskShape(alpha, w, h, 2000, TONE.white, rng(9));
    let edge = 0;
    for (let i = 0; i < 2000; i++) {
      expect(Math.abs(s.points[i * 3])).toBeLessThanOrEqual(0.26);
      expect(Math.abs(s.points[i * 3 + 1])).toBeLessThanOrEqual(0.26);
      if (s.lum![i] === 1) edge++;
    }
    expect(edge).toBeGreaterThan(400);
    expect(edge).toBeLessThan(1600);
    // nothing in the mask: nothing bright
    const none = maskShape(new Uint8Array(w * h), w, h, 100, TONE.white, rng(9));
    expect([...none.lum!].every((l) => l === 0)).toBe(true);
  });

  it('a medal: a disc on a ribbon, its emblem in the middle, in its own metal', () => {
    const R = 0.3, cy = 0.17;
    for (const [kind, metal] of [['gold', TONE.amber], ['silver', TONE.silver], ['bronze', TONE.bronze]] as const) {
      const m = medalShape(kind, 6000, rng(5));
      let rim = 0, ribbon = 0, star = 0, metalled = 0;
      for (let i = 0; i < 6000; i++) {
        const x = m.points[i * 3], y = m.points[i * 3 + 1], r = Math.hypot(x, y - cy);
        expect(Number.isFinite(x + y + m.points[i * 3 + 2])).toBe(true);
        expect(m.lum![i]).toBeGreaterThanOrEqual(0);
        expect(m.lum![i]).toBeLessThanOrEqual(1);
        expect(m.along![i]).toBeGreaterThanOrEqual(0);
        expect(m.along![i]).toBeLessThan(1);
        if (m.tones![i] === metal) metalled++;
        if (y < cy - R - 0.07) {
          // above the disc there is only the ribbon: none of the metal
          ribbon++;
          expect(m.tones![i]).not.toBe(metal);
        } else if (Math.abs(r - R) < 0.006) rim++;
        else if (r < R * 0.41 && m.lum![i] > 0.4) star++;
        // nothing of the metal outside the disc and the ring it hangs by
        if (m.tones![i] === metal) expect(r).toBeLessThan(R * 1.25);
      }
      expect(rim).toBeGreaterThan(700);
      expect(ribbon).toBeGreaterThan(400);
      expect(star).toBeGreaterThan(900);
      expect(metalled).toBeGreaterThan(3000);
    }
    // with a mask the emblem is the mask's picture: a bar across the middle stays a bar
    const w = 40, h = 52, alpha = new Uint8Array(w * h);
    for (let y = 22; y < 30; y++) for (let x = 4; x < 36; x++) alpha[y * w + x] = 255;
    const barred = medalShape('gold', 6000, rng(6), { alpha, w, h });
    let bar = 0, off = 0;
    for (let i = 0; i < 6000; i++) {
      const x = barred.points[i * 3], y = barred.points[i * 3 + 1] - cy;
      if (Math.hypot(x, y) > R * 0.34 || barred.points[i * 3 + 2] > -0.03) continue;
      if (Math.abs(y) < R * 0.1 && Math.abs(x) < R * 0.345) bar++;
      else off++;
    }
    expect(bar).toBeGreaterThan(700);
    expect(off).toBe(0);
  });

  it('grains ride with points that travel, and start again with them at the other end', () => {
    const c = createCloud(1600, 1280, 720, palette);
    const m = c.n;
    // every point at the shape's middle, travelling one unit down a cycle, each with its own phase
    const along = new Float32Array(m);
    for (let k = 0; k < m; k++) along[k] = k / m;
    const shape: Shape = { points: new Float32Array(m * 3), along, fall: { x: 0, y: 1, z: 0, rate: 0.5 }, tone: 1, loose: 0, size: 1, gain: 1 };
    Object.assign(c.place, { x: 640, y: 360, scale: 200 });
    bind(c, shape);
    run(c, 3);
    const where = (i: number) => 360 + 200 * ((((along[i] + c.time * 0.5) % 1) + 1) % 1 - 0.5);
    let off = 0, top = Infinity, bottom = -Infinity;
    for (let i = 0; i < c.n; i++) {
      off = Math.max(off, Math.abs(c.pos[i * 3 + 1] - where(i)));
      top = Math.min(top, c.pos[i * 3 + 1]);
      bottom = Math.max(bottom, c.pos[i * 3 + 1]);
    }
    expect(c.live).toBe(m);
    // carried along (no lag behind the point), over the whole travel and nowhere else
    expect(off).toBeLessThan(3);
    expect(top).toBeGreaterThan(255);
    expect(top).toBeLessThan(265);
    expect(bottom).toBeLessThan(465);
    expect(bottom).toBeGreaterThan(455);
    // through two more cycles none of them is ever left behind (a grain flying back up through the picture)
    for (let k = 0; k < 240; k++) {
      stepCloud(c, 1 / 60);
      for (let i = 0; i < c.n; i++) expect(Math.abs(c.pos[i * 3 + 1] - where(i))).toBeLessThan(6);
    }
  });
});
