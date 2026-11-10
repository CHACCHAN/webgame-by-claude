import type { CarSpec } from './carSpecs';

/**
 * Joke entry: a giant cockroach, the cheat of the lineup. Six legs drive (an electric-style single ratio: full pull
 * from standstill to Mach 1, 1225 km/h, where the legs hit their limit), it clings to the road (grip ~2.6× a sports
 * car's, downforce) and stops on the spot. Owner (2026-11-10): 「ゴキブリがチート枠の威厳失ってきてるから性能2倍にして
 * ほしい、最大速度はマッハ1」: grip, pull and brakes doubled (0→100 km/h 1.56 → 0.88 s: the tyres' limit), the top speed Mach 1.
 * Drawn by render/RoachModel.ts (the legs scuttle with the distance covered), heard through audio/BugSound.ts.
 */
export interface CreatureInfo {
  /**
   * colour variants: the swatch shown in the car select, then either per-channel gains on the model's texture
   * (linear; the texture is red-brown with a tan pronotum, so only gains can turn it another hue) or a plain colour in its
   * place (the bump map stays), optionally metallic
   */
  liveries: { name: string; swatch: string; gain?: [number, number, number]; plain?: string; metal?: boolean }[];
  /** ground covered per cycle of the scuttle animation (m) */
  stride: number;
  /** car list figures */
  figures: { legs: number; topSpeed: number; zeroToHundred: number; bodyLength: number };
}

export const ROACH_INFO: CreatureInfo = {
  liveries: [
    { name: 'ワモンゴキブリ', swatch: '#7a3417' },
    { name: 'クロゴキブリ', swatch: '#2b1d16', gain: [0.2, 0.2, 0.22] },
    { name: 'チャバネゴキブリ', swatch: '#b98a4e', plain: '#a8723a' },
    { name: '黄金のゴキブリ', swatch: '#e2b632', plain: '#e8b54a', metal: true },
  ],
  stride: 1.6,
  figures: { legs: 6, topSpeed: 1225, zeroToHundred: 0.9, bodyLength: 3.4 },
};

const MASS = 700;

export const ROACH_SPEC: CarSpec = {
  id: 'roach',
  name: 'ゴキブリ',
  tagline: '全車両最速・チート枠',
  description: '峠に現れた体長3m超の巨大ゴキブリ。6本の脚で路面をつかんで離さず、0→100km/h 0.9秒、最高速はマッハ1（1225km/h）。壁ぎわでもひるまない、全車両最強のネタ枠。',
  drive: 'AWD',
  engineName: '6本脚（脚力のみ）',
  frontTorqueSplit: 0.5,
  mass: MASS,
  size: { width: 1.9, height: 0.55, length: 4.2 },
  wheelbase: 2.6,
  track: 1.7,
  comForward: 0,
  // low and wide: at 2 g of grip a higher centre of mass rolled it over in hairpins
  comHeight: 0.15,
  wheelRadius: 0.33,
  suspension: { rest: 0.28, stiffness: 42000, damping: 4200, antiRoll: 14000 },
  engine: {
    idleRpm: 0,
    // the legs' limit: the single ratio reaches Mach 1 (340.3 m/s, 1225 km/h at sea level) at the "redline"
    redline: 29540,
    // full pull all the way: at standstill just past the tyres' grip (as before: 1.17×), at Mach 1 ~11 MW, a little
    // more than the drag takes there, so it reaches the limiter
    torque: [[0, 3000], [1500, 3600], [29540, 3600]],
    cylinders: 0,
    turbo: false,
    electric: true,
  },
  gears: [1],
  finalDrive: 3,
  gripFront: 3.5,
  gripRear: 3.5,
  // the tyres corner twice as hard as they did for the same steering angle (cornering stiffness grows with the grip):
  // about half the lock keeps the response it had (at 40° the AI weaved into the walls)
  maxSteerDeg: 22,
  brakeForce: 30000,
  // a little sleeker than before (0.25): with the pull above it would have stalled ~15 km/h short of Mach 1
  dragCoef: 0.2,
  downforce: 2.0,
  // no more than at 250 km/h: at 400 km/h (the autobahn) the springs sank under 3.5× its weight and the belly hit the road
  downforceTopSpeed: 70,
  // the cars' body damping would cap it far below its top speed
  damping: 0.004,
  rolling: 0.01,
  driftiness: 0.6,
  stats: { power: 10, grip: 10, drift: 7, weight: 10 },
  colors: { body: ROACH_INFO.liveries[0].swatch, accent: '#1a0f0a' },
  // our own model: tools/blender/creatures/roach.py (an American cockroach, Periplaneta americana)
  model: { title: 'ワモンゴキブリ', author: 'TOUGE NOCTURNE', url: '', license: '自作', own: true },
  creature: ROACH_INFO,
};
