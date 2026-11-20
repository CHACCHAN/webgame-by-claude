import { afterEach, describe, expect, it, vi } from 'vitest';
import { DynamicResolution, drawingRatio } from './drawingRatio';
import { LOW_PIXELS, qualityProfile } from '../../store/settings';

/** quality low's rule as the settings give it on a screen of this many device px per CSS px */
function low(dpr: number, scale = 1) {
  vi.stubGlobal('window', { devicePixelRatio: dpr, matchMedia: () => ({ matches: false }) });
  return qualityProfile('low', scale);
}
const drawn = (dpr: number, w: number, h: number, scale = 1) => {
  const r = drawingRatio(low(dpr, scale), w, h);
  return { ratio: r, mp: (Math.round(w * r) * Math.round(h * r)) / 1e6 };
};

describe('drawing resolution', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('a plain ratio is taken as it is', () => {
    expect(drawingRatio({ pixelRatio: 1.5 }, 844, 390)).toBe(1.5);
    expect(drawingRatio({ pixelRatio: 1.5 }, 3840, 2160)).toBe(1.5);
  });

  it('low on a phone at DPR 3 draws its budget, not 0.75 CSS px', () => {
    const { ratio, mp } = drawn(3, 844, 390);
    expect(ratio).toBeGreaterThan(1);
    expect(mp).toBeLessThanOrEqual(LOW_PIXELS + 0.01);
    expect(mp).toBeGreaterThan(LOW_PIXELS * 0.97);
  });

  it('low never draws more than 0.75 of the device pixels per axis', () => {
    // (a small phone at DPR 2: 0.75 × 2 = 1.5 is less than the budget would allow)
    expect(drawn(2, 568, 320).ratio).toBeCloseTo(1.5);
    expect(drawn(1, 640, 360).ratio).toBeCloseTo(0.75);
  });

  it('low on a desktop at DPR 1 stays at 0.75 CSS px, whatever the window', () => {
    for (const [w, h] of [[1280, 720], [1920, 1080], [2560, 1440], [3840, 2160]]) expect(drawn(1, w, h).ratio).toBe(0.75);
  });

  it('low never goes coarser than 0.75 CSS px (a large screen at DPR 2)', () => {
    expect(drawn(2, 1440, 900).ratio).toBeGreaterThanOrEqual(0.75);
    expect(drawn(2, 2560, 1440).ratio).toBe(0.75);
  });

  it('the resolution scale shrinks what low draws, the budget by its square', () => {
    const full = drawn(3, 844, 390), half = drawn(3, 844, 390, 0.5);
    expect(half.ratio).toBeCloseTo(full.ratio * 0.5);
    expect(drawn(1, 1920, 1080, 0.5).ratio).toBeCloseTo(0.375);
  });

  it('the other qualities keep their ratios', () => {
    vi.stubGlobal('window', { devicePixelRatio: 3, matchMedia: () => ({ matches: false }) });
    expect(drawingRatio(qualityProfile('medium', 1), 844, 390)).toBe(1);
    expect(drawingRatio(qualityProfile('high', 1), 844, 390)).toBe(1.5);
    expect(drawingRatio(qualityProfile('ultra', 1), 844, 390)).toBe(2);
  });
});

function feed(dyn: DynamicResolution, count: number, ms: number | ((i: number) => number)): number[] {
  const changes: number[] = [];
  for (let i = 0; i < count; i++) {
    if (dyn.sample(typeof ms === 'function' ? ms(i) : ms)) changes.push(dyn.ratio);
  }
  return changes;
}

describe('dynamic resolution', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('is a no-op when ceiling <= floor (desktop DPR 1 low, large DPR 2 low, and medium/high/ultra)', () => {
    const desktop = new DynamicResolution(low(1), 1920, 1080);
    expect(desktop.active).toBe(false);
    expect(desktop.ratio).toBe(0.75);
    expect(feed(desktop, 500, 30)).toEqual([]);
    expect(desktop.ratio).toBe(0.75);

    const large = new DynamicResolution(low(2), 2560, 1440);
    expect(large.active).toBe(false);
    expect(large.ratio).toBe(0.75);
    expect(feed(large, 500, 30)).toEqual([]);

    vi.stubGlobal('window', { devicePixelRatio: 3, matchMedia: () => ({ matches: false }) });
    for (const [q, expected] of [['medium', 1], ['high', 1.5], ['ultra', 2]] as const) {
      const d = new DynamicResolution(qualityProfile(q, 1), 844, 390);
      expect(d.active).toBe(false);
      expect(d.ratio).toBe(expected);
      expect(feed(d, 500, 30)).toEqual([]);
      expect(d.ratio).toBe(expected);
    }
  });

  it('stays at ceiling on fast frames and ignores isolated hitches and background pauses', () => {
    const rule = low(3);
    const dyn = new DynamicResolution(rule, 844, 390);
    const ceiling = drawingRatio(rule, 844, 390);
    expect(dyn.active).toBe(true);
    expect(dyn.ratio).toBeCloseTo(1.232, 3);
    expect(dyn.ratio).toBe(ceiling);

    // fast frames (10–16 ms) and steady 60 Hz vsync (16.7 ms)
    expect(feed(dyn, 300, (i) => 10 + (i % 7))).toEqual([]);
    expect(feed(dyn, 300, 16.7)).toEqual([]);
    expect(dyn.ratio).toBe(ceiling);

    // isolated hitches (120 ms for 3 frames, or even a 10-frame race-start / GLB-decode burst) and pauses (> 200 ms) never trigger a drop
    expect(feed(dyn, 450, (i) => (i % DynamicResolution.WINDOW < 3 ? 120 : 16))).toEqual([]);
    expect(feed(dyn, DynamicResolution.WINDOW, (i) => (i < 10 ? 80 : 16.7))).toEqual([]);
    expect(feed(dyn, 200, 500)).toEqual([]);
    expect(feed(dyn, 50, 0)).toEqual([]);
    expect(feed(dyn, 50, -10)).toEqual([]);
    expect(feed(dyn, 50, Number.NaN)).toEqual([]);
    expect(dyn.ratio).toBe(ceiling);
  });

  it('steps down smoothly to pixelFloor (0.75, 633×292) under sustained heavy frames', () => {
    const dyn = new DynamicResolution(low(3), 844, 390);
    const steps = feed(dyn, DynamicResolution.WINDOW * 6, 21);
    expect(steps.length).toBe(DynamicResolution.MAX_STEPS);
    for (let i = 1; i < steps.length; i++) expect(steps[i]).toBeLessThan(steps[i - 1]);
    expect(steps[0]).toBeLessThan(dyn.ceiling);
    expect(dyn.ratio).toBe(0.75);
    expect(Math.floor(844 * dyn.ratio)).toBe(633);
    expect(Math.floor(390 * dyn.ratio)).toBe(292);
    // stays pinned at floor on further heavy frames
    expect(feed(dyn, DynamicResolution.WINDOW * 4, 25)).toEqual([]);
    expect(dyn.ratio).toBe(0.75);

    // honours resolutionScale (floor scales with it)
    const half = new DynamicResolution(low(3, 0.5), 844, 390);
    expect(half.ratio).toBeCloseTo(dyn.ceiling * 0.5);
    feed(half, DynamicResolution.WINDOW * 6, 21);
    expect(half.ratio).toBeCloseTo(0.375);
  });

  it('does not oscillate when stepping down brings frame time from 21 ms to 13.5 ms', () => {
    const dyn = new DynamicResolution(low(3), 844, 390);
    const down = feed(dyn, DynamicResolution.WINDOW, 21);
    expect(down).toHaveLength(1);
    const settled = dyn.ratio;
    expect(settled).toBeLessThan(dyn.ceiling);
    expect(settled).toBeGreaterThan(0.75);

    // deadband (13.5 ms and 16.67 ms vsync): stays steady with zero oscillation
    expect(feed(dyn, 1000, 13.5)).toEqual([]);
    expect(feed(dyn, 1000, 16.67)).toEqual([]);
    expect(dyn.ratio).toBe(settled);
  });

  it('recovers only under sustained very fast frames (< 11 ms) and locks a rung after repeated failures', () => {
    const rule = low(3);
    const dyn = new DynamicResolution(rule, 844, 390);
    const ceiling = dyn.ceiling;

    // 1st failure at ceiling -> step down
    expect(feed(dyn, DynamicResolution.WINDOW, 21)).toHaveLength(1);
    const lower = dyn.ratio;

    // interrupted fast stretch (3 fast windows then a 14 ms window) does not recover
    expect(feed(dyn, DynamicResolution.WINDOW * (DynamicResolution.UP_WINDOWS - 1), 10)).toEqual([]);
    expect(feed(dyn, DynamicResolution.WINDOW, 14)).toEqual([]);
    expect(dyn.ratio).toBe(lower);

    // full sustained recovery: 179 fast frames are not enough, 180th steps back up
    const need = DynamicResolution.WINDOW * DynamicResolution.UP_WINDOWS;
    expect(feed(dyn, need - 1, 10)).toEqual([]);
    expect(dyn.ratio).toBe(lower);
    expect(dyn.sample(10)).toBe(true);
    expect(dyn.ratio).toBe(ceiling);

    // 2nd failure at ceiling -> step down AND lock ceiling out
    expect(feed(dyn, DynamicResolution.WINDOW, 21)).toEqual([lower]);
    expect(feed(dyn, need * 4, 8)).toEqual([]);
    expect(dyn.ratio).toBe(lower);

    // unchanged configure() preserves the lower rung and its lock
    expect(dyn.configure(rule, 844, 390)).toBe(false);
    expect(feed(dyn, need * 2, 8)).toEqual([]);
    expect(dyn.ratio).toBe(lower);

    // canvas resize resets back to ceiling and clears the lock
    expect(dyn.configure(rule, 390, 844)).toBe(true);
    expect(dyn.ratio).toBe(dyn.ceiling);
    expect(feed(dyn, DynamicResolution.WINDOW, 21)).toHaveLength(1);
    expect(feed(dyn, need, 10)).toEqual([dyn.ceiling]);

    // rule change (e.g. resolutionScale) also resets
    expect(dyn.configure(low(3, 0.8), 390, 844)).toBe(true);
    expect(dyn.ratio).toBe(dyn.ceiling);
  });
});
