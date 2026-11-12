import { CAR_SPECS, type CarId } from '../vehicle/carSpecs';
import { footprint, onlineGrid, type GridSpot } from './grid';

/**
 * Where the vehicles of an online waiting room stand and how the camera frames them: the arithmetic of
 * `LobbyLineup` (which builds and draws them), free of the renderer so it can be tested.
 */

/** One vehicle of the line-up: the seat, what stands there, and whether it is only being looked at (選択中). */
export interface LineupEntry {
  slot: number;
  carId: CarId;
  /** the paint picked (a car's colour, a train's line, a livery); without one the vehicle wears the seat's colour */
  livery?: string;
  browsing: boolean;
}

/** A stretch of road: distances along the course (s0 = back, s1 = front) and offsets from its centre line (m). */
export interface RoadSpan {
  s0: number;
  s1: number;
  l0: number;
  l1: number;
}

/** how much of a long vehicle (a train's 60 m) the camera frames, from its nose back (m): the cab end */
export const LONG_SHOWN = 6;
/**
 * The camera on the line-up: from the front, `turn` (rad) round from the roadside towards the road ahead, swinging
 * `swing` either way, `lift` high per unit of scale (the garage's camera looks at one car from the side, 1.7 up).
 * From ahead and above the rows read as rows, and a train stands behind them instead of across the picture.
 */
export const LINEUP_VIEW = { turn: 1.2, swing: 0.2, lift: 3.7 };
/** the garage camera's distance at scale 1 (m) */
export const VIEW_DISTANCE = 8.6;
/** the camera stays this far before the start line (m): the start gantry's legs and banner are not in its way */
export const GATE_CLEAR = 2;
/** width of road (m) that camera takes in beside the menu panel at scale 1 */
const VIEW_WIDTH = 4.6;
/**
 * The point the camera frames, as a share of the line-up's length from its front: nearer the front than the middle,
 * since the rows nearest the camera are the largest in the picture.
 */
const FOCUS = 0.32;
/** length of road the front row takes (m) */
const FRONT_ROW = 5;

/** Distance along the course of the point the camera frames. */
export const focusOf = (span: RoadSpan) => span.s1 - (span.s1 - span.s0) * FOCUS;

/** The start grid of the entries (`onlineGrid`) and the stretch of road it takes up, long vehicles by their cab end. */
function gridSpan(entries: readonly LineupEntry[], startS: number): { spots: Map<number, GridSpot>; span: RoadSpan } {
  const spots = onlineGrid(entries, startS);
  const span = { s0: Infinity, s1: -Infinity, l0: Infinity, l1: -Infinity };
  for (const e of entries) {
    const g = spots.get(e.slot)!, f = footprint(CAR_SPECS[e.carId]);
    span.s1 = Math.max(span.s1, g.s + f.ahead);
    span.s0 = Math.min(span.s0, g.s + f.ahead - Math.min(f.ahead + f.behind, LONG_SHOWN));
    span.l0 = Math.min(span.l0, g.lateral - f.width / 2);
    span.l1 = Math.max(span.l1, g.lateral + f.width / 2);
  }
  return { spots, span };
}

/**
 * Scale of the view that takes in a stretch of road: its width across the picture, seen from the camera's widest
 * angle off the road's direction. What stands behind the front row is further from the camera and smaller in the
 * picture: its length counts at the middle of the swing only.
 */
function viewScale(span: RoadSpan) {
  const off = Math.PI / 2 - LINEUP_VIEW.turn, wide = off + LINEUP_VIEW.swing;
  const length = span.s1 - span.s0, front = Math.min(length, FRONT_ROW);
  return Math.max(0.8, (front * Math.sin(wide) + (length - front) * Math.sin(off) + (span.l1 - span.l0) * Math.cos(wide) + 1) / VIEW_WIDTH);
}

/** How far ahead of the point it frames (m, along the road) the camera comes at most in its swing. */
export const cameraAhead = (scale: number) => VIEW_DISTANCE * scale * Math.sin(Math.min(Math.PI / 2, LINEUP_VIEW.turn + LINEUP_VIEW.swing));

/**
 * Where the members' vehicles stand in the waiting room (`spots`), the stretch of road they take up (`span`) and the
 * scale of the camera's view (1 = the garage's single car). They stand in the rows of the start grid (`onlineGrid`:
 * rows that fit the road whatever the mix, trains at the back), the whole grid moved back along the road until the
 * camera in front of it stands before the start line — as far as the road behind allows (`onlineGrid` keeps the
 * last row on it: a room full of trains stays further forward).
 */
export function lineupPlan(entries: readonly LineupEntry[], startS: number): { spots: Map<number, GridSpot>; span: RoadSpan; scale: number } {
  if (!entries.length) return { spots: new Map(), span: { s0: startS - 22, s1: startS - 18, l0: -1, l1: 1 }, scale: 1 };
  const grid = gridSpan(entries, startS);
  const scale = viewScale(grid.span);
  const back = focusOf(grid.span) + cameraAhead(scale) - (startS - GATE_CLEAR);
  return { ...(back > 0 ? gridSpan(entries, startS - back) : grid), scale };
}
