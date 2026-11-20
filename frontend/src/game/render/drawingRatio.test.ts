import { afterEach, describe, expect, it, vi } from 'vitest';
import { drawingRatio } from './drawingRatio';
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
