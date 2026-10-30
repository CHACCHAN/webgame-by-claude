import { fbm, lerp, ridged, smoothstep } from '../util/math';

/** A cluster of town/city lights. */
export interface CityDef {
  x: number;
  z: number;
  /** half extents (m) of the populated ellipse */
  rx: number;
  rz: number;
  /** street grid rotation (rad) */
  angle: number;
  /** relative number of lights */
  density: number;
  /** 0..1 share of tall lit buildings near the centre */
  downtown: number;
}

/**
 * Large-scale landscape of a course, independent of the road. The terrain near
 * the road is shaped by the road itself (see terrain.ts); the landform decides
 * slopes, water, where towns sit and what decorates the horizon.
 */
export interface Landform {
  base(x: number, z: number): number;
  /** 0..1 weight of mountain relief (0 on plains, towns and lakes) */
  relief(x: number, z: number): number;
  /** sea or lake surface height, or null for dry landscapes */
  waterLevel: number | null;
  /** water plane extent (centre and size, m) */
  water?: { x: number; z: number; w: number; d: number };
  /** cut-off for trees (grassland above) */
  treeLine: number;
  cities: CityDef[];
  /** horizontal direction of the strongest light pollution on the sky */
  cityGlowDir: [number, number, number];
  /** strength of that light pollution (1 = big harbour city) */
  cityGlow?: number;
  /** direction towards the moon at night (scenic placement per course) */
  moonDir: [number, number, number];
  /** height of the dawn sea of clouds */
  cloudLevel: number;
  features: {
    ferrisWheel?: [number, number];
    /** coastal highway with moving traffic along z = coast(x) - 40 */
    coast?: (x: number) => number;
    ships?: boolean;
    towers: [number, number][];
    turbines?: [number, number][];
  };
}

// --------------------------------------------------------------- 朧峠: bay
const bayCoast = (x: number) => 1950 + 160 * fbm(x / 900 + 3.1, 0.7, 3);

export const BAY: Landform = {
  base(x, z) {
    // one smooth profile: steady mountain slope easing into the coastal plain
    const slope = 470 - (z + 700) * 0.22;
    let h = lerp(slope, 6, smoothstep(150, 1350, z));
    const coast = bayCoast(x);
    h -= 32 * smoothstep(coast - 120, coast + 260, z);
    const mountain = smoothstep(1350, 300, z);
    h += fbm(x / 520 + 11.3, z / 900 - 4.2, 4) * 70 * mountain;
    h += fbm(x / 210 - 2.7, z / 210 + 8.1, 4) * 22 * mountain;
    h += ridged(x / 760 + 5.1, z / 760 - 1.4, 5) * 330 * smoothstep(-300, -1500, z);
    h += ridged(x / 600, z / 600 + 9.0, 4) * 220 * smoothstep(1900, 3400, Math.abs(x - 900)) * smoothstep(800, 2400, z);
    h += fbm(x / 140, z / 140, 3) * 2.5 * (1 - mountain);
    return h;
  },
  relief: (_x, z) => smoothstep(1350, 300, z),
  waterLevel: 0,
  water: { x: 900, z: 7000, w: 26000, d: 16000 },
  treeLine: 2000,
  cities: [{ x: 900, z: 1650, rx: 2600, rz: 520, angle: 0.18, density: 1, downtown: 1 }],
  cityGlowDir: [0.1, 0, 1],
  moonDir: [0.38, 0.5, 0.78],
  cloudLevel: 150,
  features: {
    ferrisWheel: [1350, bayCoast(1350) - 70],
    coast: bayCoast,
    ships: true,
    towers: [[-900, -1500], [1700, -1300], [2600, -600]],
  },
};

// ---------------------------------------------------------- 霧降湖: caldera lake
const LAKE = { x: 310, z: 560, level: 344 };
const lakeR = (x: number, z: number) => {
  // slightly irregular shoreline
  const a = Math.atan2(z - LAKE.z, x - LAKE.x);
  return Math.hypot(x - LAKE.x, z - LAKE.z) * (1 + 0.12 * Math.sin(a * 3 + 1.3) + 0.06 * Math.sin(a * 7));
};

export const CALDERA: Landform = {
  base(x, z) {
    const r = lakeR(x, z);
    // lake bed → shore → steep inner wall → rim → gentle outer flanks
    let h: number;
    if (r < 330) h = LAKE.level - 25 + smoothstep(330, 0, r) * -10;
    else if (r < 900) h = lerp(LAKE.level - 25, 540, smoothstep(330, 900, r));
    else h = lerp(540, 260, smoothstep(900, 3200, r));
    const rimMask = smoothstep(450, 900, r) * smoothstep(3500, 1000, r);
    h += ridged(x / 520 + 3.3, z / 520 - 7.1, 5) * 160 * rimMask;
    h += fbm(x / 300 + 1.7, z / 300 + 4.2, 4) * 35 * smoothstep(350, 700, r);
    // far mountain ranges around the caldera
    h += ridged(x / 900 - 2.2, z / 900 + 5.5, 4) * 380 * smoothstep(2600, 4500, r);
    return h;
  },
  relief: (x, z) => smoothstep(360, 520, lakeR(x, z)),
  waterLevel: LAKE.level,
  water: { x: LAKE.x, z: LAKE.z, w: 1800, d: 1800 },
  treeLine: 2000,
  cities: [
    // hot-spring town at the end of the course and hotels along the far shore
    { x: -180, z: 1180, rx: 260, rz: 200, angle: 0.5, density: 0.18, downtown: 0.25 },
    { x: 60, z: 380, rx: 180, rz: 120, angle: -0.4, density: 0.06, downtown: 0.1 },
  ],
  cityGlowDir: [-0.4, 0, 0.9],
  cityGlow: 0.4,
  moonDir: [-0.45, 0.42, 0.79],
  cloudLevel: 320,
  features: { towers: [[1500, -1200], [-1300, 600]] },
};

// ------------------------------------------------------- 天狼スカイライン: ridge
const AX = { x0: -600, z0: 60, x1: 1350, z1: -260 };
const ridgeFrame = (x: number, z: number) => {
  const dx = AX.x1 - AX.x0, dz = AX.z1 - AX.z0;
  const len = Math.hypot(dx, dz);
  const ux = dx / len, uz = dz / len;
  const px = x - AX.x0, pz = z - AX.z0;
  return { along: px * ux + pz * uz, across: -px * uz + pz * ux, len };
};

export const RIDGE: Landform = {
  base(x, z) {
    const { along, across, len } = ridgeFrame(x, z);
    // crest height along the ridge, dropping off past its eastern end
    const t = along / len;
    let crest = lerp(700, 610, Math.min(Math.max(t, 0), 1));
    crest = lerp(crest, 380, smoothstep(len * 0.95, len * 1.6, along));
    crest += fbm(along / 700 + 2.1, 0.3, 2) * 45;
    // steep flanks into valleys on both sides, cut by gullies
    const a = Math.abs(across);
    let h = crest - 0.42 * a * smoothstep(0, 140, a) - 0.12 * Math.max(0, a - 900);
    const gully = 1 - ridged(x / 380 + 1.9, z / 380 - 6.4, 4);
    h -= gully * 70 * smoothstep(90, 600, a);
    h = Math.max(h, 180 + fbm(x / 400, z / 400, 3) * 30);
    h += fbm(x / 260 + 5.1, z / 260 - 2.6, 4) * 34 * smoothstep(60, 400, a);
    h += fbm(x / 90, z / 90, 3) * 6 * smoothstep(40, 200, a);
    // distant peaks
    h += ridged(x / 1000 + 7.7, z / 1000 - 3.3, 4) * 420 * smoothstep(2200, 4200, a);
    return h;
  },
  relief: () => 1,
  waterLevel: null,
  treeLine: 600,
  cities: [
    { x: 2350, z: 120, rx: 330, rz: 260, angle: 0.3, density: 0.22, downtown: 0.3 },
    // a big city on the plain far to the south, glowing on the horizon
    { x: 1200, z: 4200, rx: 2600, rz: 900, angle: 0.1, density: 1.1, downtown: 1 },
  ],
  cityGlowDir: [0.15, 0, 1],
  cityGlow: 0.75,
  moonDir: [-0.3, 0.55, -0.78],
  cloudLevel: 430,
  features: {
    towers: [[-1600, 900], [2900, -1500]],
    turbines: (() => {
      const out: [number, number][] = [];
      for (let k = 0; k < 9; k++) {
        const t = 0.05 + k * 0.11;
        const x = lerp(AX.x0, AX.x1, t), z = lerp(AX.z0, AX.z1, t);
        const side = k % 2 ? 1 : -1;
        // offset across the ridge so they stand clear of the road
        out.push([x + side * 75 * 0.16, z + side * 165]);
      }
      return out;
    })(),
  },
};
