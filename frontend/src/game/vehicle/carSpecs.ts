// The original three ids are kept (records, ghosts and medals stay valid); the cars now carry the
// names of the real cars whose models replace them (see docs/ASSETS.md).
export type CarId = 'hayate' | 'raijin' | 'shiden' | 'supra' | 'r34' | 's15';

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
    name: 'SPRINTER TRUENO AE86',
    tagline: '軽量FRハッチバック',
    description: 'ハチロク。非力だが素直なハンドリングと軽さが武器。ドリフトの入りやすさは随一で、峠デビューに最適な一台。',
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
    name: 'IMPREZA WRX STI',
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
    name: 'RX-7 (FD3S)',
    tagline: 'ロータリーFRスポーツ',
    description: '甲高く吹け上がるロータリーと低い重心。速いがピーキーで、腕次第で最速を狙えるじゃじゃ馬。',
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
  supra: {
    id: 'supra',
    name: 'SUPRA RZ (JZA80)',
    tagline: '直6ツインターボFR',
    description: '分厚いトルクで坂を押し切る重量級FR。直線は最速クラスだが、重さを感じさせない丁寧なブレーキングが鍵。',
    drive: 'RWD',
    frontTorqueSplit: 0,
    mass: 1510,
    size: { width: 1.81, height: 0.64, length: 4.52 },
    wheelbase: 2.55,
    track: 1.52,
    comForward: 0.1,
    comHeight: 0.47,
    wheelRadius: 0.33,
    suspension: { rest: 0.32, stiffness: 46000, damping: 4000, antiRoll: 12000 },
    engine: {
      idleRpm: 800,
      redline: 6800,
      torque: [[1000, 180], [2400, 300], [3200, 440], [4400, 455], [5800, 415], [7000, 330]],
      cylinders: 6,
      turbo: true,
    },
    gears: [3.0, 1.9, 1.38, 1.08, 0.88, 0.74],
    finalDrive: 3.9,
    gripFront: 1.38,
    gripRear: 1.32,
    maxSteerDeg: 32,
    brakeForce: 13200,
    dragCoef: 0.36,
    downforce: 0.9,
    driftiness: 0.65,
    stats: { power: 10, grip: 7, drift: 7, weight: 4 },
    colors: { body: '#eeeeee', accent: '#111111' },
  },
  r34: {
    id: 'r34',
    name: 'SKYLINE GT-R (BNR34)',
    tagline: '直6ツインターボ4WD',
    description: '電子制御4WDが路面をつかみ、どこからでも加速する。重いがとにかく安定し、速さを引き出しやすい。',
    drive: 'AWD',
    frontTorqueSplit: 0.3,
    mass: 1560,
    size: { width: 1.785, height: 0.66, length: 4.6 },
    wheelbase: 2.665,
    track: 1.48,
    comForward: 0.14,
    comHeight: 0.48,
    wheelRadius: 0.33,
    suspension: { rest: 0.32, stiffness: 47000, damping: 4100, antiRoll: 13000 },
    engine: {
      idleRpm: 900,
      redline: 8000,
      torque: [[1000, 170], [2600, 280], [3600, 405], [4400, 425], [6400, 395], [7800, 320]],
      cylinders: 6,
      turbo: true,
    },
    gears: [3.0, 1.95, 1.4, 1.08, 0.87, 0.73],
    finalDrive: 4.1,
    gripFront: 1.42,
    gripRear: 1.38,
    maxSteerDeg: 31,
    brakeForce: 13600,
    dragCoef: 0.38,
    downforce: 1.2,
    driftiness: 0.4,
    stats: { power: 10, grip: 9, drift: 4, weight: 4 },
    colors: { body: '#2f4fa6', accent: '#111111' },
  },
  s15: {
    id: 's15',
    name: 'SILVIA spec-R (S15)',
    tagline: 'ターボFRクーペ',
    description: '軽い車体にほどよいターボ。テールの出方が素直で扱いやすい、ドリフトの教科書のような一台。',
    drive: 'RWD',
    frontTorqueSplit: 0,
    mass: 1240,
    size: { width: 1.695, height: 0.6, length: 4.445 },
    wheelbase: 2.525,
    track: 1.48,
    comForward: 0.06,
    comHeight: 0.44,
    wheelRadius: 0.31,
    suspension: { rest: 0.31, stiffness: 40000, damping: 3500, antiRoll: 10000 },
    engine: {
      idleRpm: 850,
      redline: 7500,
      torque: [[1000, 140], [2600, 220], [3200, 290], [4800, 305], [6400, 270], [7600, 215]],
      cylinders: 4,
      turbo: true,
    },
    gears: [3.3, 1.95, 1.4, 1.1, 0.9, 0.76],
    finalDrive: 4.3,
    gripFront: 1.36,
    gripRear: 1.28,
    maxSteerDeg: 35,
    brakeForce: 11600,
    dragCoef: 0.34,
    downforce: 0.8,
    driftiness: 0.9,
    stats: { power: 7, grip: 7, drift: 10, weight: 7 },
    colors: { body: '#f2c21a', accent: '#111111' },
  },
};

export const CAR_ORDER: CarId[] = ['hayate', 's15', 'shiden', 'supra', 'raijin', 'r34'];

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
