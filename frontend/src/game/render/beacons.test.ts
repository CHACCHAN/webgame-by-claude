import { describe, expect, it } from 'vitest';
import { BEACON_RATE, beaconPulse } from './beacons';

describe('obstruction lights', () => {
  it('flash as medium-intensity red ones do: 20–40 times a minute, softly, with a dark part', () => {
    expect(BEACON_RATE).toBeGreaterThanOrEqual(20);
    expect(BEACON_RATE).toBeLessThanOrEqual(40);
    const period = 60 / BEACON_RATE;
    let top = 0, dark = 0, steepest = 0, last = beaconPulse(0);
    const N = 2000;
    for (let k = 1; k <= N; k++) {
      const v = beaconPulse((k / N) * period);
      expect(v).toBeGreaterThanOrEqual(0);
      expect(v).toBeLessThanOrEqual(1);
      top = Math.max(top, v);
      if (v < 0.01) dark++;
      if (k < N) steepest = Math.max(steepest, Math.abs(v - last));
      last = v;
    }
    expect(top).toBeGreaterThan(0.99);
    // dark for a quarter of the period and more, and never a step (the old one was a blinker)
    expect(dark / N).toBeGreaterThan(0.25);
    expect(steepest * N).toBeLessThan(12);
    // the same a period later: every turbine of a farm is given the same time
    expect(beaconPulse(0.7)).toBeCloseTo(beaconPulse(0.7 + 5 * period), 6);
  });
});
