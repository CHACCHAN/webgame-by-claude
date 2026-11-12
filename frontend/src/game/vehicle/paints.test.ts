import { describe, expect, it } from 'vitest';
import { VEHICLE_ORDER } from './carSpecs';
import { COLORS, offeredPaint } from './paints';
import { paintFor, SLOT_COLORS } from '../net/RemoteRacers';

describe('paints', () => {
  it('every vehicle offers at least one paint, each as the server keeps it (#rrggbb, lower case)', () => {
    for (const id of VEHICLE_ORDER) {
      expect(COLORS[id]?.length, id).toBeGreaterThan(0);
      // (the server lowers a paint's case: a swatch written otherwise would never be found again)
      for (const c of COLORS[id]) expect(c, id).toMatch(/^#[0-9a-f]{6}$/);
    }
  });

  it("takes only a paint the vehicle offers", () => {
    expect(offeredPaint('supra', '#D8481C')).toBe('#d8481c');
    expect(offeredPaint('supra', '#00b2e5')).toBeUndefined();
    expect(offeredPaint('supra', null)).toBeUndefined();
    expect(offeredPaint('supra', 'red')).toBeUndefined();
  });

  it("online: the member's paint, else the seat's colour", () => {
    expect(paintFor('supra', '#d8481c', 3)).toBe('#d8481c');
    expect(paintFor('supra', null, 3)).toBe(SLOT_COLORS[3]);
    expect(paintFor('supra', '#00b2e5', 6)).toBe(SLOT_COLORS[1]);
  });
});
