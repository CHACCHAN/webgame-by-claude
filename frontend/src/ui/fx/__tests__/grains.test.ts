import { describe, expect, it } from 'vitest';
import { createGrains, lineOutline, moveShape, panelOutline, pointAt, ringOutline, seatsFor, setShape, stepGrains } from '../grains';

const run = (g: ReturnType<typeof createGrains>, seconds: number) => {
  for (let i = 0; i < seconds * 60; i++) stepGrains(g, 1 / 60);
};
/** distance from a point to the outline (to its nearest sampled point) */
const off = (p: Float32Array, x: number, y: number) => {
  let best = Infinity;
  for (let k = 0; k < p.length; k += 2) best = Math.min(best, Math.hypot(p[k] - x, p[k + 1] - y));
  return best;
};

describe('the interface grains', () => {
  it('float inside the screen and never stand still or run away', () => {
    const g = createGrains(400, 1280, 720);
    run(g, 20);
    let moving = 0;
    for (let i = 0; i < g.n; i++) {
      expect(g.x[i]).toBeGreaterThanOrEqual(-9);
      expect(g.x[i]).toBeLessThanOrEqual(1289);
      expect(g.y[i]).toBeGreaterThanOrEqual(-9);
      expect(g.y[i]).toBeLessThanOrEqual(729);
      const v = Math.hypot(g.vx[i], g.vy[i]);
      expect(v).toBeLessThan(80);
      if (v > 1) moving++;
    }
    expect(moving).toBeGreaterThan(g.n * 0.9);
  });

  it('gather into the outline of what is selected, and travel along it', () => {
    const g = createGrains(600, 1280, 720);
    run(g, 1);
    const outline = panelOutline(400, 300, 320, 56, 10);
    setShape(g, { points: outline, tone: 0 });
    const seated = [...g.seat].filter((s) => s >= 0).length;
    expect(seated).toBe(seatsFor(g, g.length));
    expect(seated).toBeGreaterThan(100);
    run(g, 1.5);
    const where: number[] = [];
    let onLine = 0;
    for (let i = 0; i < g.n; i++) {
      if (g.seat[i] < 0) continue;
      // on the line or loosely around it, bright
      const d = off(outline, g.x[i], g.y[i]);
      expect(d).toBeLessThan(21);
      if (d < 3.5) onLine++;
      expect(g.held[i]).toBeGreaterThan(0.95);
      where.push(g.x[i]);
    }
    expect(onLine / seated).toBeGreaterThan(0.55);
    run(g, 0.5);
    let k = 0, moved = 0;
    for (let i = 0; i < g.n; i++) if (g.seat[i] >= 0 && Math.abs(g.x[i] - where[k++]) > 2) moved++;
    expect(moved).toBeGreaterThan(seated * 0.5);
  });

  it('move over to the next selection instead of forming anew, and float again when nothing is selected', () => {
    const g = createGrains(600, 1280, 720);
    setShape(g, { points: panelOutline(100, 100, 300, 50, 10), tone: 0 });
    run(g, 1.5);
    const first = new Set<number>();
    for (let i = 0; i < g.n; i++) if (g.seat[i] >= 0) first.add(i);
    const next = panelOutline(100, 400, 300, 50, 10);
    setShape(g, { points: next, tone: 1 });
    let kept = 0;
    for (let i = 0; i < g.n; i++) if (g.seat[i] >= 0 && first.has(i)) kept++;
    expect(kept).toBe(first.size);
    run(g, 1.5);
    for (let i = 0; i < g.n; i++) if (g.seat[i] >= 0) expect(off(next, g.x[i], g.y[i])).toBeLessThan(21);

    setShape(g, null);
    expect([...g.seat].every((s) => s < 0)).toBe(true);
    run(g, 2);
    for (let i = 0; i < g.n; i++) expect(g.held[i]).toBeLessThan(0.05);
  });

  it('a panel outline is closed, cut at two corners and evenly spaced', () => {
    const p = panelOutline(0, 0, 200, 60, 10);
    const g = createGrains(10, 400, 400);
    setShape(g, { points: p, tone: 0 });
    expect(g.length).toBeCloseTo(2 * (200 + 60) - 4 * 10 + 2 * Math.hypot(10, 10), 3);
    const at: [number, number] = [0, 0];
    pointAt(g, 0, at);
    expect(at).toEqual([10, 0]);
    pointAt(g, 1, at);
    expect(at).toEqual([10, 0]);
    // the cut corners are not on the outline, the square ones are
    expect(off(p, 0, 0)).toBeGreaterThan(5);
    expect(off(p, 200, 60)).toBeGreaterThan(5);
    expect(off(p, 200, 0)).toBeLessThan(0.01);
    expect(off(p, 0, 60)).toBeLessThan(0.01);
    for (let k = 2; k < p.length; k += 2) expect(Math.hypot(p[k] - p[k - 2], p[k + 1] - p[k - 1])).toBeLessThan(8);
  });

  it('follow an outline that moves without changing seats', () => {
    const g = createGrains(500, 1280, 720);
    setShape(g, { points: panelOutline(100, 100, 300, 50, 10), tone: 0 });
    const seats = Float32Array.from(g.seat);
    const next = panelOutline(500, 300, 200, 80, 10);
    moveShape(g, next);
    expect([...g.seat]).toEqual([...seats]);
    run(g, 1.5);
    for (let i = 0; i < g.n; i++) if (g.seat[i] >= 0) expect(off(next, g.x[i], g.y[i])).toBeLessThan(21);
  });

  it('rings and underlines are closed and evenly spaced', () => {
    const r = ringOutline(100, 100, 40);
    for (let k = 0; k < r.length; k += 2) expect(Math.hypot(r[k] - 100, r[k + 1] - 100)).toBeCloseTo(40, 3);
    expect(r[0]).toBeCloseTo(100, 3);
    expect(r[1]).toBeCloseTo(60, 3);
    const l = lineOutline(10, 50, 120);
    for (let k = 2; k < l.length; k += 2) expect(Math.hypot(l[k] - l[k - 2], l[k + 1] - l[k - 1])).toBeLessThan(8);
    expect(Math.min(...[...l].filter((_, k) => k % 2 === 0))).toBe(10);
    expect(Math.max(...[...l].filter((_, k) => k % 2 === 0))).toBe(130);
  });
});
