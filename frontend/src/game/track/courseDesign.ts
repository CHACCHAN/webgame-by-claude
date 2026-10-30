// Oboro Pass (朧峠) downhill. The course is authored "turtle style": a list of
// straights and constant-radius arcs with a grade each. Curvature and grade
// are smoothed afterwards so transitions behave like real clothoids.
//
// Conventions: Y is up, +Z points south (towards the bay and the city lights),
// heading 0 = driving towards +Z, positive arc angles turn LEFT.

export type ZoneTag = 'start' | 'vista' | 'hairpins' | 'forest' | 'rockshed' | 'bridge' | 'finish';

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
