export type CarId = 'hayate' | 'raijin' | 'shiden';

export interface CarSpec {
  id: CarId;
  name: string;
  tagline: string;
  description: string;
  drive: 'RWD' | 'AWD';
  /** fraction of drive torque sent to the front axle (AWD only) */
  frontTorqueSplit: number;
  mass: number;
  /** chassis collision box (m) */
  size: { width: number; height: number; length: number };
  wheelbase: number;
  track: number;
  /** distance of the center of mass ahead of the wheelbase midpoint (m) */
  comForward: number;
  comHeight: number;
  wheelRadius: number;
  suspension: { rest: number; stiffness: number; damping: number; antiRoll: number };
  engine: {
    idleRpm: number;
    redline: number;
    /** [rpm, Nm] pairs */
    torque: [number, number][];
    /** sound character: number of cylinders and growl */
    cylinders: number;
    turbo: boolean;
  };
  gears: number[];
  finalDrive: number;
  /** tyre friction coefficients */
  gripFront: number;
  gripRear: number;
  maxSteerDeg: number;
  brakeForce: number;
  dragCoef: number;
  downforce: number;
  /** 0..1, how much the car wants to rotate (rear slip tendency) */
  driftiness: number;
  /** UI stat bars 0..10 */
  stats: { power: number; grip: number; drift: number; weight: number };
  colors: { body: string; accent: string };
}

export const CAR_SPECS: Record<CarId, CarSpec> = {
  hayate: {
    id: 'hayate',
    name: 'HAYATE TR-S',
    tagline: '軽量FRハッチバック',
    description: '素直なハンドリングと軽さが武器。ドリフトの入りやすさは随一で、峠デビューに最適な一台。',
    drive: 'RWD',
    frontTorqueSplit: 0,
    mass: 1040,
    size: { width: 1.66, height: 0.62, length: 4.2 },
    wheelbase: 2.4,
    track: 1.42,
    comForward: 0.06,
    comHeight: 0.45,
    wheelRadius: 0.3,
    suspension: { rest: 0.32, stiffness: 36000, damping: 3200, antiRoll: 9000 },
    engine: {
      idleRpm: 900,
      redline: 7800,
      torque: [[1000, 110], [3000, 135], [5000, 152], [6600, 156], [7600, 140], [8200, 118]],
      cylinders: 4,
      turbo: false,
    },
    gears: [3.3, 2.1, 1.5, 1.15, 0.92],
    finalDrive: 4.1,
    gripFront: 1.32,
    gripRear: 1.24,
    maxSteerDeg: 34,
    brakeForce: 9800,
    dragCoef: 0.36,
    downforce: 0.6,
    driftiness: 0.85,
    stats: { power: 5, grip: 6, drift: 9, weight: 9 },
    colors: { body: '#e8e6e1', accent: '#16181c' },
  },
  raijin: {
    id: 'raijin',
    name: 'RAIJIN GT-X',
    tagline: 'ターボ4WDセダン',
    description: '強烈なトルクと4WDのトラクションで立ち上がりが圧倒的。安定志向で、タイムを狙いやすい。',
    drive: 'AWD',
    frontTorqueSplit: 0.38,
    mass: 1320,
    size: { width: 1.78, height: 0.66, length: 4.45 },
    wheelbase: 2.62,
    track: 1.52,
    comForward: 0.12,
    comHeight: 0.48,
    wheelRadius: 0.32,
    suspension: { rest: 0.32, stiffness: 44000, damping: 3900, antiRoll: 12000 },
    engine: {
      idleRpm: 950,
      redline: 7200,
      torque: [[1000, 150], [2600, 250], [3400, 380], [5200, 395], [6600, 350], [7500, 290]],
      cylinders: 4,
      turbo: true,
    },
    gears: [3.1, 1.95, 1.4, 1.08, 0.87],
    finalDrive: 4.2,
    gripFront: 1.42,
    gripRear: 1.38,
    maxSteerDeg: 32,
    brakeForce: 12500,
    dragCoef: 0.4,
    downforce: 1.1,
    driftiness: 0.45,
    stats: { power: 9, grip: 9, drift: 5, weight: 5 },
    colors: { body: '#1d4fa8', accent: '#d8dce4' },
  },
  shiden: {
    id: 'shiden',
    name: 'SHIDEN RS',
    tagline: '高回転FRスポーツ',
    description: '甲高く吹け上がるエンジンと低い重心。速いがピーキーで、腕次第で最速を狙えるじゃじゃ馬。',
    drive: 'RWD',
    frontTorqueSplit: 0,
    mass: 1230,
    size: { width: 1.76, height: 0.58, length: 4.3 },
    wheelbase: 2.43,
    track: 1.5,
    comForward: 0.02,
    comHeight: 0.42,
    wheelRadius: 0.31,
    suspension: { rest: 0.3, stiffness: 42000, damping: 3600, antiRoll: 10500 },
    engine: {
      idleRpm: 1000,
      redline: 8800,
      torque: [[1000, 120], [3000, 190], [5000, 255], [6500, 300], [8000, 285], [9200, 240]],
      cylinders: 6,
      turbo: false,
    },
    gears: [3.2, 2.15, 1.6, 1.25, 1.0],
    finalDrive: 4.0,
    gripFront: 1.4,
    gripRear: 1.3,
    maxSteerDeg: 33,
    brakeForce: 11800,
    dragCoef: 0.33,
    downforce: 0.9,
    driftiness: 0.75,
    stats: { power: 8, grip: 7, drift: 8, weight: 6 },
    colors: { body: '#c8102e', accent: '#111111' },
  },
};

export const CAR_ORDER: CarId[] = ['hayate', 'raijin', 'shiden'];

export function torqueAt(spec: CarSpec, rpm: number): number {
  const t = spec.engine.torque;
  if (rpm <= t[0][0]) return t[0][1];
  for (let i = 1; i < t.length; i++) {
    if (rpm <= t[i][0]) {
      const f = (rpm - t[i - 1][0]) / (t[i][0] - t[i - 1][0]);
      return t[i - 1][1] + (t[i][1] - t[i - 1][1]) * f;
    }
  }
  return t[t.length - 1][1];
}
