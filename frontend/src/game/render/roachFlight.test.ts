import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { ROACH_INFO } from '../vehicle/roach';
import { flightState, flightStep, wingPose } from './RoachModel';

const F = ROACH_INFO.flight;
const DT = 1 / 120;
/** run the wings' state for `seconds` in the air or on the ground */
const run = (s: ReturnType<typeof flightState>, airborne: boolean, seconds: number) => {
  for (let t = 0; t < seconds - 1e-9; t += DT) flightStep(s, F, airborne, DT);
  return s;
};

describe("the cockroach's wings", () => {
  it('stay shut on the ground and over a hop', () => {
    const s = flightState();
    run(s, false, 1);
    expect(s.opened).toBe(0);
    // (hop after hop: the time in the air does not add up over the landings between them)
    for (let k = 0; k < 5; k++) {
      run(s, true, F.after * 0.6);
      run(s, false, 0.05);
    }
    expect(s.opened).toBe(0);
    expect(s.flying).toBe(false);
  });

  it('open and beat in the air, and fold again after the landing', () => {
    const s = flightState();
    run(s, true, F.after + F.open + 0.05);
    expect(s.opened).toBe(1);
    const before = s.phase;
    run(s, true, 0.02);
    expect(s.phase).not.toBe(before);
    // a leg that touches for a moment (a tumble) folds nothing
    run(s, false, F.settle * 0.5);
    expect(s.opened).toBe(1);
    run(s, true, 0.05);
    expect(s.opened).toBe(1);
    run(s, false, F.settle + F.fold + 0.05);
    expect(s.opened).toBe(0);
    expect(s.phase).toBe(0);
  });

  it('lie as the model has them when folded, whatever the beat', () => {
    for (const phase of [0, 0.25, 0.6]) {
      const p = wingPose(F, 0, phase);
      // (toBeCloseTo: a product with zero may be −0)
      for (const w of [p.tegmen, p.hind]) for (const v of [w.sweep, w.lift, w.twist]) expect(v).toBeCloseTo(0, 12);
      expect(p.hind.unfold).toBe(1);
    }
  });

  it('open the wing cases first: the hind wings come out from under them', () => {
    const early = wingPose(F, 0.3, 0);
    expect(early.tegmen.sweep).toBeGreaterThan(0.5);
    expect(early.hind.sweep).toBe(0);
    expect(early.hind.unfold).toBe(1);
    const out = wingPose(F, 1, 0);
    expect(out.tegmen.sweep).toBeCloseTo((F.tegmen.sweep * Math.PI) / 180, 10);
    expect(out.hind.sweep).toBeCloseTo((F.hind.sweep * Math.PI) / 180, 10);
    expect(out.hind.unfold).toBeCloseTo(F.hind.unfold, 10);
  });

  it('keep the hind wings under the wing cases through the whole beat', () => {
    for (let k = 0; k < 40; k++) {
      const p = wingPose(F, 1, k / 40);
      expect(p.hind.lift).toBeLessThan(p.tegmen.lift - 0.1);
    }
  });

  // the model's check renders (the sheet the owner sees) pose the wings by the script's numbers, the game by its own
  it("use the angles of the model's script", () => {
    const py = readFileSync(new URL('../../../tools/blender/creatures/roach_anatomy.py', import.meta.url), 'utf8');
    const flight = /^FLIGHT = dict\(tegmen=dict\((.*?)\), hind=dict\((.*?)\)\)$/m.exec(py);
    expect(flight).not.toBeNull();
    const angles = (text: string) => Object.fromEntries(text.split(',').map((kv) => kv.trim().split('=')).map(([k, v]) => [k, Number(v)]));
    const { unfold, ...hind } = F.hind;
    expect(angles(flight![1])).toEqual(F.tegmen);
    expect(angles(flight![2])).toEqual(hind);
    expect(Number(/^HIND = dict\(.*unfold=([\d.]+)\)$/m.exec(py)?.[1])).toBe(unfold);
  });
});
