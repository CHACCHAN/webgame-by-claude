import { describe, expect, it } from 'vitest';
import { COURSES, COURSE_ORDER } from '../track/courses';
import { CAR_SPECS, VEHICLE_ORDER, type CarId } from '../vehicle/carSpecs';
import { TRAIN_ORDER } from '../vehicle/trains';
import { footprint, onlineGrid, GRID_MIN_S } from './grid';
import { cameraAhead, focusOf, GATE_CLEAR, lineupPlan, LONG_SHOWN, type LineupEntry } from './lineup';

const room = (...cars: CarId[]): LineupEntry[] => cars.map((carId, slot) => ({ slot, carId, browsing: false }));
const starts = [...new Set(COURSE_ORDER.map((id) => COURSES[id].design.startS ?? 40))];

describe('lineupPlan (the waiting room: where the vehicles stand, what the camera frames)', () => {
  it('stands the vehicles in the rows of the start grid, the whole grid moved back along the road', () => {
    const entries = room('hayate', 'supra', 'ninjah2', 'e235', 'roach');
    const plan = lineupPlan(entries, 40);
    const grid = onlineGrid(entries, 40);
    const back = grid.get(0)!.s - plan.spots.get(0)!.s;
    expect(back).toBeGreaterThan(0);
    for (const e of entries) {
      const a = plan.spots.get(e.slot)!, b = grid.get(e.slot)!;
      expect(a.lateral).toBeCloseTo(b.lateral, 9);
      expect(a.row).toBe(b.row);
      expect(b.s - a.s).toBeCloseTo(back, 9);
    }
  });

  it('keeps the camera before the start line (the gantry is not in its way) in every room of cars, on every course', () => {
    for (const startS of starts) {
      for (let n = 1; n <= 5; n++) {
        const plan = lineupPlan(room(...VEHICLE_ORDER.filter((id) => !CAR_SPECS[id].train).slice(0, n)), startS);
        expect(focusOf(plan.span) + cameraAhead(plan.scale), `${n} cars, start at ${startS}`).toBeLessThanOrEqual(startS - GATE_CLEAR + 1e-6);
      }
    }
  });

  it('keeps every vehicle on the road behind the start line, whatever the mix', () => {
    const mixes: CarId[][] = [
      ['hayate'], ['roach'], ['ninjah2', 'hayabusa'], ['e235'], ['hayate', 'e235'], ['cybertruck', 'cybertruck', 'cybertruck', 'cybertruck', 'cybertruck'],
      ['hayate', 'supra', 'ninjah2', 'e235', 'roach'], ['e5', 'l0', 'e235', 'hayate', 'roach'], [...TRAIN_ORDER].slice(0, 5),
    ];
    for (const startS of starts) {
      for (const cars of mixes) {
        const entries = room(...cars);
        const plan = lineupPlan(entries, startS);
        for (const e of entries) {
          const g = plan.spots.get(e.slot)!;
          expect(g.s, `${cars.join(',')} at ${startS}`).toBeGreaterThanOrEqual(GRID_MIN_S - 1e-6);
          // never further forward than the race will start them (a room of trains is too long for the road
          // behind the line: the race's grid reaches over it, and so does the line-up)
          expect(g.s).toBeLessThanOrEqual(onlineGrid(entries, startS).get(e.slot)!.s + 1e-6);
          if (cars.filter((c) => CAR_SPECS[c].train).length < 2) expect(g.s + footprint(CAR_SPECS[e.carId]).ahead).toBeLessThan(startS);
        }
      }
    }
  });

  it('frames a single car as the garage does, and a full room without backing off for a train\'s whole length', () => {
    expect(lineupPlan(room('hayate'), 40).scale).toBeGreaterThan(0.8);
    expect(lineupPlan(room('hayate'), 40).scale).toBeLessThan(1.3);
    expect(lineupPlan(room('nsr250r'), 40).scale).toBe(0.8);
    const five = lineupPlan(room('hayate', 'supra', 'r34', 's15', 'shiden'), 40);
    const train = lineupPlan(room('hayate', 'supra', 'r34', 's15', 'e235'), 40);
    expect(five.scale).toBeGreaterThan(2);
    expect(five.scale).toBeLessThan(4);
    // the train (60 m of it behind the cars) counts with its cab end only
    expect(train.scale).toBeLessThan(five.scale + 2.5);
    const alone = lineupPlan(room('e235'), 40);
    expect(alone.span.s1 - alone.span.s0).toBeCloseTo(LONG_SHOWN, 6);
  });

  it('an empty room frames a place on the road', () => {
    const plan = lineupPlan([], 40);
    expect(plan.spots.size).toBe(0);
    expect(plan.scale).toBe(1);
    expect(focusOf(plan.span)).toBeLessThan(40);
  });
});
