import { describe, expect, it } from 'vitest';
import { Track } from '../track/Track';
import { COURSES, COURSE_ORDER } from '../track/courses';
import { CAR_SPECS, VEHICLE_ORDER, type CarId } from '../vehicle/carSpecs';
import { GRID_CLEARANCE, GRID_FRONT, GRID_MIN_S, GRID_ROW_GAP, GRID_TRAIN_GAP, GRID_WIDTH, footprint, onlineGrid, type GridEntry } from '../net/grid';

const START = 40;
const room = (...cars: CarId[]): GridEntry[] => cars.map((carId, slot) => ({ slot, carId }));

/** every room of 1–5 of these, in every seating order */
function* rooms(pool: CarId[], max = 5): Generator<CarId[]> {
  const walk = function* (r: CarId[]): Generator<CarId[]> {
    if (r.length) yield r;
    if (r.length < max) for (const c of pool) yield* walk([...r, c]);
  };
  yield* walk([]);
}

/** The rules a grid has to keep: nobody in anybody, room to the sides and to the road's edges, all of it on the road. */
function check(cars: CarId[], startS: number) {
  const entries = room(...cars);
  const grid = onlineGrid(entries, startS);
  const placed = entries.map((e) => ({ ...e, ...grid.get(e.slot)!, ...footprint(CAR_SPECS[e.carId]) }));
  const label = cars.join(',');
  expect(grid.size, label).toBe(cars.length);
  for (const a of placed) {
    // on the road, clear of its edges (the walls stand 0.6 m beyond them)
    expect(Math.abs(a.lateral) + a.width / 2, label).toBeLessThanOrEqual(GRID_WIDTH / 2 - GRID_CLEARANCE + 1e-6);
    expect(a.s, label).toBeGreaterThanOrEqual(GRID_MIN_S - 1e-6);
    for (const b of placed) {
      if (a.slot >= b.slot) continue;
      if (a.row === b.row) {
        expect(a.s, label).toBe(b.s);
        expect(Math.abs(a.lateral - b.lateral) - (a.width + b.width) / 2, label).toBeGreaterThanOrEqual(GRID_CLEARANCE - 1e-6);
      } else {
        // one wholly behind the other: its nose short of the other's tail (a train's tail is its last car's)
        const [front, rear] = a.row < b.row ? [a, b] : [b, a];
        expect(front.s - front.behind - (rear.s + rear.ahead), label).toBeGreaterThanOrEqual(GRID_ROW_GAP - 1e-6);
      }
    }
  }
  return { grid, placed, front: Math.max(...placed.map((p) => p.s)), nose: Math.max(...placed.map((p) => p.s + p.ahead)) };
}

describe('online start grid', () => {
  it('five cars stand three and two, the back row behind the gaps of the front row', () => {
    const { grid } = check(['hayate', 'raijin', 'shiden', 'supra', 'r34'], START);
    expect([0, 1, 2, 3, 4].map((slot) => grid.get(slot)!.row)).toEqual([0, 0, 0, 1, 1]);
    const x = [0, 1, 2, 3, 4].map((slot) => grid.get(slot)!.lateral);
    // slots left to right, the front row at the usual place before the line
    expect(x[0]).toBeLessThan(x[1]);
    expect(x[1]).toBeLessThan(x[2]);
    expect(grid.get(0)!.s).toBe(START - GRID_FRONT);
    expect(x[3]).toBeGreaterThan(x[0]);
    expect(x[3]).toBeLessThan(x[1]);
    expect(x[4]).toBeGreaterThan(x[1]);
    expect(x[4]).toBeLessThan(x[2]);
    // a car's length and the gap behind: no train-length holes in a grid of cars
    expect(grid.get(0)!.s - grid.get(3)!.s).toBeCloseTo(CAR_SPECS.raijin.size.length / 2 + CAR_SPECS.r34.size.length / 2 + GRID_ROW_GAP, 6);
  });

  it('two or three stand side by side, a fourth behind a gap of the front row', () => {
    const two = check(['hayate', 'hayate'], START).grid;
    expect(two.get(0)).toMatchObject({ row: 0, s: START - GRID_FRONT });
    expect(two.get(1)).toMatchObject({ row: 0, s: START - GRID_FRONT });
    expect(two.get(0)!.lateral).toBeLessThan(0);
    expect(two.get(0)!.lateral).toBeCloseTo(-two.get(1)!.lateral, 6);
    const four = check(['hayate', 'shiden', 'raijin', 'supra'], START).grid;
    expect([0, 1, 2, 3].map((slot) => four.get(slot)!.row)).toEqual([0, 0, 0, 1]);
    expect(Math.abs(four.get(1)!.lateral)).toBeLessThan(0.2);
    expect(four.get(3)!.lateral).toBeCloseTo((four.get(1)!.lateral + four.get(2)!.lateral) / 2, 6);
    const one = check(['hayate'], START).grid.get(0)!;
    expect(one).toMatchObject({ s: START - GRID_FRONT, row: 0 });
    expect(one.lateral).toBeCloseTo(0, 6);
  });

  it('is the same on every client: the order the room is listed in does not matter, the seats do', () => {
    const cars: CarId[] = ['e231', 'hayate', 'l0', 'hayabusa', 'cybertruck'];
    const a = onlineGrid(room(...cars), START);
    // as each client builds it: itself first, then the others
    for (let me = 0; me < cars.length; me++) {
      const entries = room(...cars);
      const mine = [entries[me], ...entries.filter((e) => e.slot !== me).reverse()];
      expect([...onlineGrid(mine, START)].sort((p, q) => p[0] - q[0])).toEqual([...a].sort((p, q) => p[0] - q[0]));
    }
    // seats need not be 0..n-1 (somebody left the room)
    const gap = onlineGrid([{ slot: 1, carId: 'hayate' }, { slot: 4, carId: 'shiden' }], START);
    expect([...gap.keys()].sort()).toEqual([1, 4]);
    expect(gap.get(1)!.lateral).toBeLessThan(gap.get(4)!.lateral);
  });

  it('trains stand behind the others, so their cars trail off the back of the grid', () => {
    // the train took the first seat: still behind the four cars, which keep a car's spacing
    const { grid, placed } = check(['e5', 'hayate', 'raijin', 'shiden', 'supra'], START);
    expect(grid.get(0)!.row).toBe(2);
    expect([1, 2, 3, 4].map((slot) => grid.get(slot)!.row)).toEqual([0, 0, 0, 1]);
    expect(grid.get(1)!.s).toBe(START - GRID_FRONT);
    expect(grid.get(1)!.s - grid.get(4)!.s).toBeLessThan(8);
    expect(placed[0].behind).toBeCloseTo(72.75, 6);
    // its cab stays behind the chase camera of the car ahead (6.4 m behind that car's centre)
    expect(grid.get(4)!.s - (grid.get(0)!.s + placed[0].ahead)).toBeGreaterThan(6.4 + 1);
    // two trains fit side by side, three do not
    expect(check(['e231', 'e5'], START).placed.map((p) => p.row)).toEqual([0, 0]);
    const three = check(['e231', 'e235', 'e5'], START);
    // the longest alone at the back would leave the row ahead a full train to clear: the short row is the first
    expect(three.placed.map((p) => p.row)).toEqual([0, 1, 1]);
    // a train's length between the rows, and the whole grid moved up the road (it begins at s = 0)
    expect(three.grid.get(0)!.s - three.grid.get(1)!.s).toBeCloseTo(56.9 + 5.25 + GRID_TRAIN_GAP, 6);
    expect(three.grid.get(1)!.s).toBeCloseTo(GRID_MIN_S, 6);
    expect(three.grid.get(0)!.s).toBeGreaterThan(START);
  });

  it('keeps every room apart and on the road, whatever is in it', () => {
    // the extremes: smallest and widest car, a bike, the cockroach, the widest and longest trains, the longest nose
    const pool: CarId[] = ['hayate', 'cybertruck', 'hayabusa', 'roach', 'e231', 'e5', 'l0'];
    let deepest = 0, count = 0;
    for (const cars of rooms(pool)) {
      const { front, nose } = check(cars, START);
      // the front row never stands behind its usual place
      expect(front).toBeGreaterThanOrEqual(START - GRID_FRONT);
      deepest = Math.max(deepest, nose);
      count++;
    }
    expect(count).toBe(7 + 7 ** 2 + 7 ** 3 + 7 ** 4 + 7 ** 5);
    // five trains: the grid reaches this far up the road at most (the widths below are checked that far)
    expect(deepest).toBeLessThan(200);
    // every released vehicle alone and five of a kind
    for (const id of VEHICLE_ORDER) {
      check([id], START);
      check([id, id, id, id, id], START);
    }
  });

  it('fits the road of every course around its start', () => {
    for (const id of COURSE_ORDER) {
      const track = new Track(COURSES[id].design);
      for (let s = 0; s <= 200; s++) expect(track.widthAt(s), `${id} at ${s} m`).toBeGreaterThanOrEqual(GRID_WIDTH);
      // a grid of cars stands before the line, where the road is straight
      const { placed } = check(['cybertruck', 'u9', 'r34', 'supra', 'raijin'], track.startS);
      for (const p of placed) {
        expect(p.s + p.ahead, id).toBeLessThan(track.startS);
        expect(Math.abs(track.curvatureAt(p.s)), id).toBeLessThan(1e-4);
      }
    }
  });
});
