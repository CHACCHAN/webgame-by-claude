// Oboro Pass (朧峠) downhill. The course is authored "turtle style": a list of
// straights and constant-radius arcs with a grade each. Curvature and grade
// are smoothed afterwards so transitions behave like real clothoids.
//
// Conventions: Y is up, +Z points south (towards the bay and the city lights),
// heading 0 = driving towards +Z, positive arc angles turn LEFT.

import { Track } from './Track';

export type ZoneTag =
  | 'start'
  | 'vista'
  | 'hairpins'
  | 'forest'
  | 'rockshed'
  | 'bridge'
  | 'finish'
  | 'crest'
  | 'lakeside'
  // the autobahn's zones (scenery: render/TrackScenery.ts):
  /** plain motorway */
  | 'motorway'
  /** a road bridge crosses above the carriageway at the zone's midpoint (no rain under its deck) */
  | 'overpass'
  /** noise walls on the right, village lights beyond */
  | 'village'
  /** street lamps, an exit lane and slip road on the right, overhead gantry signs before it */
  | 'interchange'
  // the air base's zones (scenery: render/airbaseScenery.ts):
  /** the flight line's concrete apron */
  | 'ramp'
  | 'taxiway'
  | 'runway'
  /** the dry lake: no pavement, the playa itself is the surface */
  | 'lakebed';

export interface Seg {
  /** straight length (m) when r is undefined, otherwise the arc radius (m) */
  len?: number;
  r?: number;
  /** arc angle in degrees, positive = left */
  deg?: number;
  /** road grade, negative = downhill */
  g: number;
  tag?: ZoneTag;
  /** optional road width override (m, full drivable width) */
  w?: number;
  /** paved width (m) inside `w`, where the pavement is narrower than what can be driven on (default: all of `w`) */
  pave?: number;
}

/** A paved rectangle beside or under the road (an apron, a runway wider than the way onto it): world x / z of the
 * middle of its near end, the heading of its long axis (as the road's), its length and width (m). */
export interface Slab {
  id: string;
  x: number;
  z: number;
  heading: number;
  length: number;
  width: number;
}

export interface CourseDesign {
  id: string;
  start: { x: number; y: number; z: number; heading: number };
  segs: Seg[];
  baseWidth: number;
  /** number of timing sectors (the finish line closes the last one) */
  sectors: number;
  /** distance of the start line from the beginning of the road (m, default 40) */
  startS?: number;
  /** road left after the finish line to stop on (m, default 120) */
  runoff?: number;
  /** moving-average windows (m) of curvature and grade: longer = gentler transitions (default 24 / 60) */
  smoothing?: { curvature?: number; grade?: number };
  /**
   * Flat graded ground (m) beyond the drivable edges, left and right: room for a median and the opposite
   * carriageway, verges and slip roads. The terrain rises or falls into the landscape only beyond it (default 0).
   */
  formation?: { left: number; right: number };
  /** the AI's speed limit on this course (m/s, default 62 ≈ 223 km/h on the mountain passes) */
  aiTopSpeed?: number;
  /** the room for the start grid where it is not a road's (m; `net/grid.ts`: 9.5 on every road): an apron */
  gridWidth?: number;
  /** level ground: no banking in the bends and no widening of tight ones (an airfield) */
  flat?: boolean;
  /** how far the ground under the road lies below its surface (m, default 0.45; 0: the ground is the surface) */
  bed?: number;
  /** tyre grip by zone, as a share of the course's (default 1), and rolling resistance by zone, as a multiple of the tyre's on pavement */
  zoneGrip?: Partial<Record<ZoneTag, number>>;
  zoneRoll?: Partial<Record<ZoneTag, number>>;
  /**
   * The road has no barriers: beside the pavement (`Seg.pave`, `slabs`) lies open ground one can drive on with this
   * share of the grip, and whoever reaches the edge of `w` is put back on the road (`Game.trackRacer`).
   */
  verge?: { grip: number; roll: number };
  /** paved rectangles that count as pavement whatever the road's own paved width is there */
  slabs?: Slab[];
}

const S = (len: number, g: number, tag?: ZoneTag): Seg => ({ len, g, tag });
const L = (r: number, deg: number, g: number, tag?: ZoneTag): Seg => ({ r, deg, g, tag });
const R = (r: number, deg: number, g: number, tag?: ZoneTag): Seg => ({ r, deg: -deg, g, tag });

export const OBORO_DOWNHILL: CourseDesign = {
  id: 'oboro-downhill',
  start: { x: -220, y: 430, z: -620, heading: Math.PI * 0.5 },
  baseWidth: 9.5,
  sectors: 4,
  segs: [
    // Summit: start straight past the parking area, heading east along the ridge.
    S(120, -0.02, 'start'),
    R(260, 42, -0.045),
    S(90, -0.06),
    L(110, 58, -0.065),
    S(60, -0.07),
    R(70, 88, -0.07),
    // The vista: a long left-hander hanging on the cliff with the bay below.
    S(70, -0.075, 'vista'),
    L(190, 62, -0.08, 'vista'),
    S(150, -0.085, 'vista'),
    // Hairpin ladder down the south face.
    R(26, 168, -0.06, 'hairpins'),
    S(150, -0.09, 'hairpins'),
    L(24, 176, -0.06, 'hairpins'),
    S(165, -0.09, 'hairpins'),
    R(27, 172, -0.06, 'hairpins'),
    S(120, -0.09, 'hairpins'),
    L(23, 170, -0.06, 'hairpins'),
    S(90, -0.08),
    // Forest esses.
    R(75, 52, -0.07, 'forest'),
    L(62, 78, -0.07, 'forest'),
    R(58, 66, -0.07, 'forest'),
    S(60, -0.06, 'forest'),
    // Rock shed gallery cut into the cliff.
    L(420, 28, -0.065, 'rockshed'),
    S(110, -0.065, 'rockshed'),
    // Over the gorge on the bridge, the whole bay opens up.
    R(260, 46, -0.03, 'bridge'),
    S(60, -0.03, 'bridge'),
    L(45, 115, -0.06),
    S(110, -0.07),
    R(140, 48, -0.06),
    S(160, -0.04, 'finish'),
  ],
};

// 霧降湖 (Kirifuri Lake): from the caldera rim through cedar forest and a hairpin pair
// down to a long, fast lakeside run that ends in a hot-spring town.
export const KIRIFURI_LAKESIDE: CourseDesign = {
  id: 'kirifuri-lakeside',
  start: { x: 0, y: 470, z: 0, heading: Math.PI * 0.5 },
  baseWidth: 9.5,
  sectors: 4,
  segs: [
    S(110, -0.03, 'start'),
    R(150, 40, -0.05),
    S(80, -0.07),
    L(70, 75, -0.08, 'forest'),
    R(45, 95, -0.08, 'forest'),
    S(100, -0.09, 'forest'),
    L(24, 170, -0.07, 'hairpins'),
    S(140, -0.09, 'hairpins'),
    R(26, 165, -0.07, 'hairpins'),
    S(120, -0.09, 'forest'),
    L(110, 55, -0.08, 'forest'),
    R(60, 80, -0.07, 'rockshed'),
    S(120, -0.06, 'rockshed'),
    L(200, 40, -0.05, 'vista'),
    S(100, -0.05, 'vista'),
    R(35, 120, -0.06),
    S(80, -0.04, 'lakeside'),
    L(300, 35, -0.02, 'lakeside'),
    R(220, 45, -0.01, 'lakeside'),
    S(150, -0.01, 'lakeside'),
    L(160, 60, -0.01, 'lakeside'),
    R(90, 70, -0.02, 'bridge'),
    S(80, -0.01, 'bridge'),
    L(120, 40, 0, 'finish'),
    S(140, 0, 'finish'),
  ],
};

// 天狼スカイライン (Tenrou Skyline): flat-out sweepers along a windswept ridge, then
// the "seven bends" ladder down the south face into the valley.
export const TENROU_SKYLINE: CourseDesign = {
  id: 'tenrou-skyline',
  start: { x: 0, y: 640, z: 0, heading: Math.PI * 0.5 },
  baseWidth: 10,
  sectors: 4,
  segs: [
    S(140, -0.01, 'start'),
    L(400, 25, 0.01, 'crest'),
    S(150, -0.02, 'crest'),
    R(350, 40, -0.02, 'crest'),
    S(120, -0.03, 'crest'),
    L(250, 50, -0.03, 'crest'),
    R(300, 30, -0.04, 'crest'),
    S(150, -0.05, 'crest'),
    R(60, 70, -0.07, 'vista'),
    S(70, -0.09, 'hairpins'),
    L(22, 175, -0.07, 'hairpins'),
    S(110, -0.1, 'hairpins'),
    R(22, 175, -0.07, 'hairpins'),
    S(110, -0.1, 'hairpins'),
    L(22, 175, -0.07, 'hairpins'),
    S(110, -0.1, 'hairpins'),
    R(24, 170, -0.07, 'hairpins'),
    S(90, -0.09),
    L(80, 60, -0.07, 'forest'),
    R(120, 45, -0.06, 'forest'),
    S(160, -0.05, 'finish'),
  ],
};

// AUTOBAHN (アウトバーン): a German motorway at night, from a forested plateau down to a river valley. Three
// lanes and a hard shoulder, every radius ≥ 1200 m: the trains and the cockroach finally run flat out.
// The carriageway is ours alone (the median and the opposite carriageway on the left are scenery).
export const AUTOBAHN: CourseDesign = {
  id: 'autobahn',
  start: { x: -4300, y: 440, z: -300, heading: Math.PI * 0.5 },
  // 0.75 m edge strip + 3 × 3.75 m lanes + 2.5 m hard shoulder
  baseWidth: 14.5,
  sectors: 4,
  // room behind the grid for a three-car train; a long run-off to stop from 300 km/h
  startS: 100,
  runoff: 650,
  smoothing: { curvature: 160, grade: 220 },
  // median + opposite carriageway on the left, verge (and the interchange's slip road) on the right
  formation: { left: 30, right: 22 },
  // no vehicle but the cockroach goes faster than 140 m/s (the U9 Xtreme's 503 km/h): the cap lets it run to Mach 1
  aiTopSpeed: 345,
  segs: [
    // the plateau: start straight, then a long left through the forest
    S(420, -0.004, 'start'),
    S(160, -0.01, 'motorway'),
    L(1800, 26, -0.014, 'forest'),
    S(200, -0.016, 'forest'),
    S(260, -0.018, 'overpass'),
    R(1400, 42, -0.022, 'motorway'),
    S(100, -0.02, 'motorway'),
    // the interchange, lit, with its exit on the right
    S(620, -0.016, 'interchange'),
    // off the plateau's edge, the viaduct over the side valley
    L(1300, 34, -0.03, 'forest'),
    S(160, -0.03, 'forest'),
    S(520, -0.018, 'bridge'),
    R(1600, 32, -0.032, 'forest'),
    S(240, -0.032, 'overpass'),
    S(120, -0.032, 'motorway'),
    L(2000, 20, -0.032, 'village'),
    S(180, -0.034, 'village'),
    // the last descent into the river valley
    R(1300, 20, -0.04, 'motorway'),
    S(150, -0.035, 'motorway'),
    S(140, -0.008, 'finish'),
    S(650, 0, 'finish'),
  ],
};

// EDWARDS AFB (エドワーズ空軍基地): from the flight line down the parallel taxiway to the threshold of runway 04R,
// its 4.6 km of concrete, out onto Rogers Dry Lake past the compass rose and north along a lakebed runway.
// True bearings; a bearing θ is the heading π − θ here (+X east, +Z south). The airfield's frame: `a` metres along
// 04R from its threshold, `b` metres to its left (north-west). The runway's length, width and surface and the
// lake's level are the published ones (15,024 × 300 ft of concrete; field 2,311 ft, lake 2,277 ft); the bearing
// (057° true for magnetic 044°), where the ramp and the taxiway lie and which lakebed runway passes the compass
// rose are from memory of the field's diagram, not measured.
const DEG = Math.PI / 180;
export const EDWARDS_FIELD = {
  /** world x / z of the 04R threshold's middle */
  x: 0,
  z: 0,
  /** true bearing of runway 04R (degrees) */
  bearing: 57,
  runway: { length: 4579.3, width: 91.44 },
  /** elevation of the 04R threshold and of the lakebed (m): the runway runs down to the lake */
  top: 704.3,
  lake: 694.0,
  /**
   * the parallel taxiway and the ramp's taxi lane: metres left of the runway's centre line (380 and 620, to the
   * metre the road is sampled by: two quarter turns and a whole number of metres between them, see `EDWARDS_ROUTE`)
   */
  taxiway: 320 / Math.PI + 278,
  lane: 640 / Math.PI + 278 + 138,
  /** the ramp's apron: from / to along the runway, from / to left of it */
  apron: { a0: 1930, a1: 2720, b0: 562, b1: 770 },
  /** the compass rose: its middle in the field's frame and its radius (4,000 ft across, from memory) */
  rose: { a: 5523, b: 809, radius: 610 },
};
/** the field's frame: unit vectors along 04R and to its left, and a point of it in the world */
export const edwardsFrame = () => {
  const t = EDWARDS_FIELD.bearing * DEG;
  const ax = Math.sin(t), az = -Math.cos(t);
  const bx = Math.sin(t - Math.PI / 2), bz = -Math.cos(t - Math.PI / 2);
  return {
    ax, az, bx, bz,
    at: (a: number, b: number): [number, number] => [EDWARDS_FIELD.x + a * ax + b * bx, EDWARDS_FIELD.z + a * az + b * bz],
    /** a world point in the field's frame */
    of: (x: number, z: number): [number, number] => [(x - EDWARDS_FIELD.x) * ax + (z - EDWARDS_FIELD.z) * az, (x - EDWARDS_FIELD.x) * bx + (z - EDWARDS_FIELD.z) * bz],
  };
};
/** the land's height along the runway: level at the top, down to the lake at the far threshold, level on the lake */
export const edwardsHeight = (a: number) => EDWARDS_FIELD.lake + (EDWARDS_FIELD.top - EDWARDS_FIELD.lake) * Math.min(1, Math.max(0, (EDWARDS_FIELD.runway.length - a) / EDWARDS_FIELD.runway.length));

/** where the course's parts begin and end along the runway's axis (the scenery reads them) */
// (the road is laid out in whole metres: a quarter turn of 80 m and a 45° sweep of 1100 m have the radii below,
// so that the runway's part of the road lies on the runway's centre line to the centimetre)
export const EDWARDS_ROUTE = { turn: 160 / Math.PI, startA: 2600, rampLen: 520, overrun: 700, sweepR: 4400 / Math.PI, sweepDeg: 45, last: 2500, runoff: 1800 };

function edwardsDesign(shiftB: number): CourseDesign {
  const F = EDWARDS_FIELD, f = edwardsFrame(), R = EDWARDS_ROUTE;
  // the runway's fall per metre (towards the lake)
  const fall = (F.top - F.lake) / F.runway.length;
  /** a quarter turn's grade when it takes the road `da` metres along the runway */
  const quarter = (da: number) => (-da * fall) / ((Math.PI / 2) * R.turn);
  const taxi = { w: 55, pave: 23 }, runway = { w: 140, pave: F.runway.width }, lake = { w: 320 };
  const [x, z] = f.at(R.startA, F.lane + shiftB);
  const along = Math.round(R.startA - R.rampLen - 3 * R.turn);
  return {
    id: 'edwards',
    start: { x, y: edwardsHeight(R.startA), z, heading: Math.PI - (F.bearing + 180) * DEG },
    baseWidth: 110,
    sectors: 4,
    // room behind the line for a row of 20 m aircraft; after the finish, room to stop from Mach 1 or to take off
    startS: 80,
    runoff: R.runoff,
    flat: true,
    bed: 0,
    // the lake's dry clay: hard enough for any aircraft (250 psi), but dusty: less grip than concrete and twice the
    // rolling resistance (estimates); the desert's graded dirt beside the pavements: loose, and it drags
    zoneGrip: { lakebed: 0.8 },
    zoneRoll: { lakebed: 2 },
    verge: { grip: 0.6, roll: 5 },
    slabs: [
      { id: 'runway', x: F.x, z: F.z, heading: Math.PI - F.bearing * DEG, length: F.runway.length, width: F.runway.width },
      { id: 'apron', x: f.at(F.apron.a0, (F.apron.b0 + F.apron.b1) / 2)[0], z: f.at(F.apron.a0, (F.apron.b0 + F.apron.b1) / 2)[1], heading: Math.PI - F.bearing * DEG, length: F.apron.a1 - F.apron.a0, width: F.apron.b1 - F.apron.b0 },
    ],
    // the fighters run to Mach 1 on the runway; nothing else comes near (the cockroach's own top speed is Mach 1)
    aiTopSpeed: 345,
    // the grid stands across the flight line: three fighters abreast, wing tips ten metres apart
    gridWidth: 80,
    segs: [
      // along the flight line, past the hangars and the tower
      { len: R.rampLen, g: fall, tag: 'ramp' },
      // off the apron and across to the parallel taxiway
      { r: R.turn, deg: 90, g: quarter(-R.turn), tag: 'taxiway', ...taxi },
      { len: F.lane - F.taxiway - 2 * R.turn, g: 0, tag: 'taxiway', ...taxi },
      { r: R.turn, deg: -90, g: quarter(-R.turn), tag: 'taxiway', ...taxi },
      // the parallel taxiway, south-west to the runway's end
      { len: along, g: fall, tag: 'taxiway', ...taxi },
      { r: R.turn, deg: 90, g: quarter(-R.turn), tag: 'taxiway', ...taxi },
      { len: F.taxiway - 2 * R.turn, g: 0, tag: 'taxiway', ...taxi },
      // onto the runway at the threshold of 04R
      { r: R.turn, deg: 90, g: quarter(R.turn), tag: 'taxiway', ...taxi },
      { len: F.runway.length - R.turn, g: -fall, tag: 'runway', ...runway },
      // the lakebed: straight on over the overrun, a long left past the compass rose, north along lakebed runway 36
      { len: R.overrun, g: 0, tag: 'lakebed', ...lake },
      { r: R.sweepR, deg: R.sweepDeg, g: 0, tag: 'lakebed', ...lake },
      { len: R.last + R.runoff, g: 0, tag: 'lakebed', ...lake },
    ],
  };
}
/**
 * The bends' eased ends (the smoothing of the curvature) move the road sideways by a metre or two over the four
 * quarter turns: laid out once to see by how much, the start is moved so that the road runs down the middle of
 * the runway.
 */
export const EDWARDS: CourseDesign = (() => {
  const trial = new Track(edwardsDesign(0));
  const i = Math.round(3183 + EDWARDS_FIELD.runway.length / 2);
  return edwardsDesign(-edwardsFrame().of(trial.pos[i * 3], trial.pos[i * 3 + 2])[1]);
})();
