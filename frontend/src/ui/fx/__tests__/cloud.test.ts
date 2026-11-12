import { describe, expect, it } from 'vitest';
import { EMPHASIS, OBJECT, bind, createCloud, members, project, rng, stepCloud, sweep, type Shape } from '../cloud';
import { TONE, courseRelief, maskShape, medalShape, panelOutline, shellOf, skyScene } from '../shapes';

const palette = new Float32Array(9 * 3).fill(1);
const run = (c: ReturnType<typeof createCloud>, seconds: number) => {
  for (let i = 0; i < seconds * 60; i++) stepCloud(c, 1 / 60);
};
/** distance from a point to an outline (to its nearest sampled point) */
const off = (p: Float32Array, x: number, y: number) => {
  let best = Infinity;
  for (let k = 0; k < p.length; k += 2) best = Math.min(best, Math.hypot(p[k] - x, p[k + 1] - y));
  return best;
};

describe('the cloud of grains', () => {
  it('floats inside its volume and never stands still or runs away', () => {
    const c = createCloud(3200, 1280, 720, palette);
    run(c, 20);
    let moving = 0;
    for (let i = 0; i < c.n; i++) {
      expect(c.pos[i * 3]).toBeGreaterThan(-1280 * 0.23);
      expect(c.pos[i * 3]).toBeLessThan(1280 * 1.23);
      expect(c.pos[i * 3 + 1]).toBeGreaterThan(-720 * 0.23);
      expect(c.pos[i * 3 + 1]).toBeLessThan(720 * 1.23);
      expect(c.pos[i * 3 + 2]).toBeLessThanOrEqual(c.deep + 1);
      const v = Math.hypot(c.vel[i * 3], c.vel[i * 3 + 1], c.vel[i * 3 + 2]);
      expect(v).toBeLessThan(90);
      if (v > 1) moving++;
    }
    expect(moving).toBeGreaterThan(c.n * 0.9);
  });

  it('has all three groups in any first part of it', () => {
    const c = createCloud(4800, 1280, 720, palette);
    expect(members(c, 0) + members(c, 1) + members(c, 2)).toBe(4800);
    expect(members(c, OBJECT, 1600)).toBe(800);
    expect(members(c, EMPHASIS, 1600)).toBe(300);
    let seen = 0;
    for (let i = 0; i < 1600; i++) if (c.group[i] === OBJECT) expect(c.rank[i]).toBe(seen++);
  });

  it('draws the edge of a panel with its emphasis grains, follows it when it moves, and lets go', () => {
    const c = createCloud(4800, 1280, 720, palette);
    const outline = panelOutline(0, 0, 320, 120, 12);
    const shell = shellOf(outline, members(c, EMPHASIS), TONE.cyan, rng(1));
    c.places[EMPHASIS].x = 400;
    c.places[EMPHASIS].y = 300;
    bind(c, EMPHASIS, shell);
    run(c, 2.5);
    let onLine = 0, held = 0, all = 0;
    for (let i = 0; i < c.n; i++) {
      if (c.group[i] !== EMPHASIS) continue;
      all++;
      if (c.held[i] > 0.9) held++;
      if (off(outline, c.pos[i * 3] - 400, c.pos[i * 3 + 1] - 300) < 4 && Math.abs(c.pos[i * 3 + 2]) < 12) onLine++;
    }
    expect(held).toBeGreaterThan(all * 0.97);
    expect(onLine / all).toBeGreaterThan(0.3);
    // the other groups took no notice
    for (let i = 0; i < c.n; i++) if (c.group[i] !== EMPHASIS) expect(c.held[i]).toBeLessThan(0.05);

    c.places[EMPHASIS].x = 700;
    run(c, 2);
    onLine = 0;
    for (let i = 0; i < c.n; i++) if (c.group[i] === EMPHASIS && off(outline, c.pos[i * 3] - 700, c.pos[i * 3 + 1] - 300) < 4) onLine++;
    expect(onLine / all).toBeGreaterThan(0.3);

    bind(c, EMPHASIS, null);
    run(c, 4);
    for (let i = 0; i < c.n; i++) expect(c.held[i]).toBeLessThan(0.05);
    // let go, they do not stay together as a lump: they are all over the screen again
    let sum = 0, sq = 0;
    for (let i = 0; i < c.n; i++) {
      if (c.group[i] !== EMPHASIS) continue;
      sum += c.pos[i * 3];
      sq += c.pos[i * 3] ** 2;
    }
    expect(Math.sqrt(sq / all - (sum / all) ** 2)).toBeGreaterThan(c.w * 0.2);
  });

  it('fills a shape only as far as it is asked to', () => {
    const c = createCloud(3200, 1280, 720, palette);
    const shape: Shape = { points: new Float32Array(300), tone: 1, loose: 0, size: 1, gain: 1 };
    Object.assign(c.places[OBJECT], { x: 640, y: 360, scale: 100, fill: 0.3 });
    bind(c, OBJECT, shape);
    run(c, 3);
    let held = 0;
    for (let i = 0; i < c.n; i++) if (c.group[i] === OBJECT && c.held[i] > 0.9) held++;
    const share = held / members(c, OBJECT);
    expect(share).toBeGreaterThan(0.22);
    expect(share).toBeLessThan(0.38);
  });

  it('turns and sizes a shape as it is placed', () => {
    const c = createCloud(1600, 1000, 1000, palette);
    // one point, one unit to the right of the shape's middle
    const shape: Shape = { points: Float32Array.of(1, 0, 0), tone: 1, loose: 0, size: 1, gain: 1 };
    Object.assign(c.places[OBJECT], { x: 500, y: 500, z: 0, scale: 100, yaw: Math.PI / 2, pitch: 0 });
    bind(c, OBJECT, shape);
    run(c, 3);
    const i = [...c.group].indexOf(OBJECT);
    // a quarter turn about the upright axis: the point is before or behind the middle now, at the same height
    expect(c.pos[i * 3]).toBeCloseTo(500, 0);
    expect(c.pos[i * 3 + 1]).toBeCloseTo(500, 0);
    expect(Math.abs(c.pos[i * 3 + 2])).toBeCloseTo(100, 0);
    // what is farther is drawn nearer the middle and smaller
    const out: [number, number, number] = [0, 0, 0];
    project(c, 900, 500, 400, out);
    expect(out[0]).toBeLessThan(900);
    expect(out[2]).toBeLessThan(1);
  });

  it('a change of screen moves the floating grains in depth', () => {
    const c = createCloud(1600, 1280, 720, palette);
    run(c, 1);
    sweep(c, 1);
    let toward = 0;
    for (let i = 0; i < c.n; i++) if (c.vel[i * 3 + 2] < -100) toward++;
    expect(toward).toBeGreaterThan(c.n * 0.9);
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

  it('an edge of grains is dimmer when there are many grains for a short line', () => {
    const few = shellOf(panelOutline(0, 0, 600, 300, 12), 600, TONE.cyan, rng(2));
    const many = shellOf(panelOutline(0, 0, 60, 30, 6), 6000, TONE.cyan, rng(2));
    expect(few.gain).toBe(1);
    expect(many.gain).toBeLessThan(0.35);
  });
  it('a sky scene per time of day: stars and a moon, rain that falls, a sun over the clouds', () => {
    const night = skyScene('night', 3.5, 8000, rng(1));
    // the moon: a dense white patch right of the middle; nothing lit below the ridge except the town
    let moon = 0;
    for (let i = 0; i < 8000; i++) if (night.tones![i] === TONE.white && Math.hypot(night.points[i * 3] - 3.5 * 0.27, night.points[i * 3 + 1] + 0.16) < 0.26) moon++;
    expect(moon).toBeGreaterThan(900);
    expect(night.fall).toBeUndefined();

    const rain = skyScene('rain', 3.5, 8000, rng(2));
    expect(rain.fall!.y).toBeGreaterThan(1);
    let falling = 0;
    for (let i = 0; i < 8000; i++) if (rain.along![i] >= 0) falling++;
    expect(falling % 6).toBe(0);
    expect(falling).toBeGreaterThan(3500);
    expect(falling).toBeLessThan(6800);

    const dawn = skyScene('dawn', 3.5, 8000, rng(3));
    let disc = 0;
    // the sun's disc is cut off at the clouds: nothing of it below them
    for (let i = 0; i < 8000; i++) {
      // (the disc's grains are the ones at its own depth, inside its radius)
      if (dawn.points[i * 3 + 2] !== Math.fround(0.3) || Math.hypot(dawn.points[i * 3], dawn.points[i * 3 + 1] - 0.1) > 0.331) continue;
      expect(dawn.points[i * 3 + 1]).toBeLessThanOrEqual(0.061);
      disc++;
    }
    expect(disc).toBeGreaterThan(1200);
    for (const s of [night, rain, dawn]) for (let i = 0; i < 8000; i++) {
      expect(Number.isFinite(s.points[i * 3] + s.points[i * 3 + 1] + s.points[i * 3 + 2])).toBe(true);
      expect(s.lum![i]).toBeGreaterThanOrEqual(0);
      expect(s.lum![i]).toBeLessThanOrEqual(1.01);
    }
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
    const m = members(c, OBJECT);
    // every point at the shape's middle, travelling one unit down a cycle, each with its own phase
    const along = new Float32Array(m);
    for (let k = 0; k < m; k++) along[k] = k / m;
    const shape: Shape = { points: new Float32Array(m * 3), along, fall: { x: 0, y: 1, z: 0, rate: 0.5 }, tone: 1, loose: 0, size: 1, gain: 1 };
    Object.assign(c.places[OBJECT], { x: 640, y: 360, scale: 200 });
    bind(c, OBJECT, shape);
    run(c, 3);
    const where = (i: number) => 360 + 200 * ((((along[c.rank[i]] + c.time * 0.5) % 1) + 1) % 1 - 0.5);
    let off = 0, count = 0, top = Infinity, bottom = -Infinity;
    for (let i = 0; i < c.n; i++) {
      if (c.group[i] !== OBJECT) continue;
      off = Math.max(off, Math.abs(c.pos[i * 3 + 1] - where(i)));
      top = Math.min(top, c.pos[i * 3 + 1]);
      bottom = Math.max(bottom, c.pos[i * 3 + 1]);
      count++;
    }
    expect(count).toBe(m);
    // carried along (no lag behind the point), over the whole travel and nowhere else
    expect(off).toBeLessThan(3);
    expect(top).toBeGreaterThan(255);
    expect(top).toBeLessThan(265);
    expect(bottom).toBeLessThan(465);
    expect(bottom).toBeGreaterThan(455);
    // through two more cycles none of them is ever left behind (a grain flying back up through the picture)
    for (let k = 0; k < 240; k++) {
      stepCloud(c, 1 / 60);
      for (let i = 0; i < c.n; i++) if (c.group[i] === OBJECT) expect(Math.abs(c.pos[i * 3 + 1] - where(i))).toBeLessThan(6);
    }
  });
});
