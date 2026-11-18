import { CAR_SPECS, type CarId, type CarSpec } from '../vehicle/carSpecs';
import { trainCars } from '../vehicle/trains';

/** One racer of an online room: the seat the server gave them and their vehicle. */
export interface GridEntry {
  slot: number;
  carId: CarId;
}

/** Where a racer stands at the start: distance along the course (m), offset from the centre line (m, + = right), row (0 = front). */
export interface GridSpot {
  s: number;
  lateral: number;
  row: number;
}

/**
 * The narrowest road any course has around its start (朧峠 and 霧降湖 9.5 m, 天狼 10 m, the autobahn 14.5 m; the walls
 * stand 0.6 m further out on each side). The grid is laid out in this width on every course, so it needs to know the
 * room only; `grid.test.ts` checks the courses against it.
 */
export const GRID_WIDTH = 9.5;
/** least room between two vehicles side by side, and between a vehicle and the road's edge (m) */
export const GRID_CLEARANCE = 0.8;
/** room between the tail of one row and the nose of the next (m) */
export const GRID_ROW_GAP = 2.5;
/**
 * … and in front of a train: a car's chase camera sits 6.4 m behind its centre and 2.15 m up, above the roof of a car in
 * the row behind but inside the cab of a train there
 */
export const GRID_TRAIN_GAP = 6;
/** the front row stands this far before the start line (as the single-player grid) … */
export const GRID_FRONT = 6;
/** … unless the rows behind it would not fit on the road, which begins at s = 0: the last row stands no further back */
export const GRID_MIN_S = 6;
const MAX_ABREAST = 3;
/** a vehicle trailing more than this behind its origin (a train's cars) goes to the back of the grid */
const LONG_TAIL = 8;

/** What a vehicle takes up on the grid, from its origin (the simulated body: a train's is its leading bogie). */
export function footprint(spec: CarSpec): { width: number; ahead: number; behind: number } {
  if (spec.train) {
    // the nose is ahead of the leading bogie, the three cars trail behind it
    const cars = trainCars(spec.train);
    const length = cars.reduce((sum, c) => sum + c.length, 0);
    return { width: spec.size.width, ahead: cars[0].front, behind: length - cars[0].front };
  }
  // a fighter: its wings, not its fuselage box, and its origin is midway between the nose wheel and the main wheels,
  // well ahead of its middle
  if (spec.jet) {
    const ahead = spec.jet.noseGear + spec.wheelbase / 2;
    return { width: spec.jet.wing.span, ahead, behind: spec.size.length - ahead };
  }
  return { width: spec.size.width, ahead: spec.size.length / 2, behind: spec.size.length / 2 };
}

type Placed = GridEntry & ReturnType<typeof footprint>;

const fits = (row: Placed[], c: Placed, width: number) =>
  row.length < MAX_ABREAST && row.reduce((w, m) => w + m.width, c.width) + (row.length + 2) * GRID_CLEARANCE <= width + 1e-9;

/** Rows in order, each as wide as the road allows. */
function pack(list: Placed[], width: number): Placed[][] {
  const rows: Placed[][] = [];
  for (const c of list) {
    const row = rows[rows.length - 1];
    if (row && fits(row, c, width)) row.push(c);
    else rows.push([c]);
  }
  return rows;
}

/**
 * The start grid of an online race: a pure function of the room (who sits in which slot, in what), so every client
 * puts everybody in the same place. Five cars do not fit side by side on a mountain road:
 *
 * - Rows of up to three, as many as fit in `GRID_WIDTH` with `GRID_CLEARANCE` between them and to the road's edges
 *   (three cars; two trains), spread evenly across the road. Seats fill the grid in slot order, left to right, front
 *   to back: five cars stand 3 + 2, the back two behind the gaps of the front three.
 * - Vehicles with a long tail (a train is 54–80 m of cars trailing its leading bogie) stand behind all the others,
 *   in rows of their own, the longest last, so that the cars of most trains trail off the back of the grid instead
 *   of through the row behind.
 * - Rows are as far apart as the vehicles in them need: the longest tail of one row, the longest nose of the next,
 *   and `GRID_ROW_GAP` (`GRID_TRAIN_GAP` in front of a train). So a row behind a train is a train's length back, a row
 *   behind cars a car's length.
 * - The front row stands `GRID_FRONT` before the start line; a grid too deep for the road behind it (three trains or
 *   more) moves forward as a whole until its last row stands at `GRID_MIN_S`. The clock starts at the green light
 *   for everybody either way.
 * - `width`: the room a course gives its grid when it is not a road's (`CourseDesign.gridWidth`: the ramp at Edwards,
 *   where fighters 13–17 m across stand three abreast; they count as long and stand behind the cars).
 */
export function onlineGrid(room: readonly GridEntry[], startS: number, width = GRID_WIDTH): Map<number, GridSpot> {
  const tail = (c: Placed) => (c.behind > LONG_TAIL ? c.behind : 0);
  const all = room.map((e) => ({ slot: e.slot, carId: e.carId, ...footprint(CAR_SPECS[e.carId]) }));
  all.sort((a, b) => tail(a) - tail(b) || a.slot - b.slot);
  const short = all.filter((c) => !tail(c));
  // the long ones are packed from the back, so the row left short is their first and the fullest rows are the last
  const long = pack(all.filter((c) => tail(c)).reverse(), width).reverse().map((row) => row.reverse());
  const rows = [...pack(short, width), ...long];

  const out = new Map<number, GridSpot>();
  let back = 0;
  const backOf: number[] = [];
  rows.forEach((row, r) => {
    const gap = row.some(tail) ? GRID_TRAIN_GAP : GRID_ROW_GAP;
    if (r > 0) back += Math.max(...rows[r - 1].map((c) => c.behind)) + Math.max(...row.map((c) => c.ahead)) + gap;
    backOf.push(back);
  });
  const front = Math.max(startS - GRID_FRONT, GRID_MIN_S + back);
  rows.forEach((row, r) => {
    // the road's free width shared equally between the vehicles and the edges
    const gap = (width - row.reduce((w, c) => w + c.width, 0)) / (row.length + 1);
    let x = -width / 2;
    for (const c of row) {
      x += gap + c.width / 2;
      out.set(c.slot, { s: front - backOf[r], lateral: x, row: r });
      x += c.width / 2;
    }
    // alone behind a row of three: behind the gap to the right of its middle vehicle, not behind its bumper
    if (row.length === 1 && r > 0 && rows[r - 1].length === 3) {
      const ahead = rows[r - 1].map((c) => out.get(c.slot)!.lateral);
      out.get(row[0].slot)!.lateral = Math.min((ahead[1] + ahead[2]) / 2, width / 2 - GRID_CLEARANCE - row[0].width / 2);
    }
  });
  return out;
}
