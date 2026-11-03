import type { CarSpec } from './carSpecs';

/**
 * Joke entry: a giant cockroach, the cheat of the lineup. Six legs drive (an electric-style single ratio: full pull
 * from standstill to ~410 km/h), it clings to the road (grip ~1.3× a sports car's, downforce) and stops on the spot.
 * Drawn by render/RoachModel.ts (the legs scuttle with the distance covered), heard through audio/BugSound.ts.
 */
export interface CreatureInfo {
  /**
   * colour variants: the swatch shown in the car select, then either per-channel gains on the model's texture
   * (linear; the texture is a deep red-brown, so only gains can turn it another hue) or a plain colour in its
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
    { name: 'クロゴキブリ', swatch: '#2b1d16', gain: [0.25, 0.7, 1.2] },
    { name: 'チャバネゴキブリ', swatch: '#b98a4e', plain: '#a8723a' },
    { name: '黄金のゴキブリ', swatch: '#e2b632', plain: '#e8b54a', metal: true },
  ],
  stride: 1.6,
  figures: { legs: 6, topSpeed: 410, zeroToHundred: 1.6, bodyLength: 3.4 },
};

const MASS = 700;

export const ROACH_SPEC: CarSpec = {
  id: 'roach',
  name: 'ゴキブリ',
  tagline: '全車両最速・チート枠',
  description: '峠に現れた体長3m超の巨大ゴキブリ。6本の脚で路面をつかんで離さず、0→100km/h 1.6秒、最高速410km/h。壁ぎわでもひるまない、全車両最強のネタ枠。',
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
    // the single ratio reaches ~420 km/h at the "redline"
    redline: 10200,
    // full pull (the grip's limit) to ~3000 rpm, then ~570 kW
    torque: [[0, 1800], [3000, 1800], [4500, 1220], [6000, 915], [8000, 690], [10200, 540]],
    cylinders: 0,
    turbo: false,
    electric: true,
  },
  gears: [1],
  finalDrive: 3,
  gripFront: 1.75,
  gripRear: 1.75,
  maxSteerDeg: 40,
  brakeForce: 15000,
  dragCoef: 0.25,
  downforce: 2.0,
  // the cars' body damping would cap it far below its top speed
  damping: 0.004,
  rolling: 0.01,
  driftiness: 0.6,
  stats: { power: 10, grip: 10, drift: 7, weight: 10 },
  colors: { body: ROACH_INFO.liveries[0].swatch, accent: '#1a0f0a' },
  model: { title: 'Cockroach', author: 'CK (xcellf)', url: 'https://sketchfab.com/3d-models/cockroach-cead55b8aa8643d48d67240bad028592', license: 'CC BY 4.0' },
  creature: ROACH_INFO,
};
