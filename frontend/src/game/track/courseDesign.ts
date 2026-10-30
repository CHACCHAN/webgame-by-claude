// Oboro Pass (朧峠) downhill. The course is authored "turtle style": a list of
// straights and constant-radius arcs with a grade each. Curvature and grade
// are smoothed afterwards so transitions behave like real clothoids.
//
// Conventions: Y is up, +Z points south (towards the bay and the city lights),
// heading 0 = driving towards +Z, positive arc angles turn LEFT.

export type ZoneTag = 'start' | 'vista' | 'hairpins' | 'forest' | 'rockshed' | 'bridge' | 'finish' | 'crest' | 'lakeside';

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
}

export interface CourseDesign {
  id: string;
  start: { x: number; y: number; z: number; heading: number };
  segs: Seg[];
  baseWidth: number;
  /** number of timing sectors (the finish line closes the last one) */
  sectors: number;
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
