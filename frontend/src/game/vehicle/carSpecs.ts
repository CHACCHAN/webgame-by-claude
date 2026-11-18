// The original three ids are kept (records, ghosts and medals stay valid); the cars now carry the
// names of the real cars whose models replace them (see docs/ASSETS.md).
import { TRAIN_ORDER, trainSpec, type TrainId, type TrainInfo } from './trains';
import { ROACH_SPEC, type CreatureInfo } from './roach';
import { BIKE_ORDER, BIKE_SPECS, type BikeId, type BikeInfo } from './bikes';
import { TANK_ORDER, TANK_SPECS, type TankId, type TankInfo } from './tanks';
import { JET_ORDER, JET_SPECS, type JetId, type JetInfo } from './jets';
import { RELEASED } from '../release';

export type CarId = 'hayate' | 'raijin' | 'shiden' | 'supra' | 'r34' | 's15' | 'cybertruck' | 'u9' | BikeId | TankId | JetId | TrainId | 'roach';
/** the real cars (AI, bots, medals per course, procedural fallback bodies) */
export type RoadCarId = Exclude<CarId, TrainId | BikeId | TankId | JetId | 'roach'>;

export interface CarSpec {
  id: CarId;
  name: string;
  tagline: string;
  description: string;
  drive: 'RWD' | 'AWD';
  /** engine as shown in the car list (layout, displacement, aspiration) */
  engineName: string;
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
    /** electric traction: full torque from standstill, no clutch slip at launch */
    electric?: boolean;
    /** a two-stroke fires every turn (default 4) */
    strokes?: 2 | 4;
    /** a supercharger's whine follows the revs (sound only: the torque curve has the boost in it) */
    supercharger?: boolean;
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
  /** speed (m/s) beyond which the downforce stops growing (default: no limit) */
  downforceTopSpeed?: number;
  /** linear damping of the body (default 0.02: ~0.4 m/s² at 70 km/h, part of the cars' tuning) */
  damping?: number;
  /** rolling resistance as a share of the wheel load (default 0.015, tyres; steel wheels far less) */
  rolling?: number;
  /** 0..1, how much the car wants to rotate (rear slip tendency) */
  driftiness: number;
  /** UI stat bars 0..10 */
  stats: { power: number; grip: number; drift: number; weight: number };
  colors: { body: string; accent: string };
  /** third-party 3D model in public/models/cars/<id>.glb (attribution shown in the garage) */
  model?: { title: string; author: string; url: string; license: string; /** our own (built in Blender, tools/blender) */ own?: boolean };
  /**
   * retractable headlamps on the 3D model (modelled closed): pods rise when the lights are on.
   * x = pod centre off the centre line, z = lid centre behind the front of the body (m)
   */
  popUpLamps?: { x: number; z: number };
  /** tail lamp glow multiplier for models whose lens texture is dark (the lens glows through it) */
  tailLampGain?: number;
  /**
   * an unpainted metal body (the Cybertruck's brushed stainless): these swatches are the bare metal, drawn fully
   * metallic without the paint's clear coat; any other swatch is paint or a wrap (render/CarModel.ts `paintFinish`).
   * `clearcoat` keeps a coat over the metal (the Ninja H2's mirror-coated paint: a silver mirror under clear)
   */
  bareMetal?: { colors: string[]; roughness: number; clearcoat?: number };
  /**
   * How much of the cabin the glass hides, head-on (0…1; `GLASS_OPACITY` = 0.62 when not given: the cabin shows as in
   * a photograph). A model whose cabin is not yet fit to be seen keeps the old dark glass (0.88). It is the glass
   * material's own opacity, a uniform: no shader of its own.
   */
  glassOpacity?: number;
  /** tailpipe tip on the 3D model (body-local m, +x = left) where no part is named like an exhaust */
  exhaust?: [number, number, number];
  /** a train (joke entry, vehicle/trains.ts): drawn as three cars following the simulated front bogie */
  train?: TrainInfo;
  /** a creature (joke entry, vehicle/roach.ts): legs instead of wheels, no exhaust */
  creature?: CreatureInfo;
  /** a motorcycle (vehicle/bikes.ts): two wheels, leans, wheelie and stoppie limits, a rider */
  bike?: BikeInfo;
  /** a tank (vehicle/tanks.ts): tracks (or the 16式's eight wheels), a turret and a gun the player fires */
  tank?: TankInfo;
  /** a fighter aircraft (vehicle/jets.ts): thrust, lift and drag, a steered nose wheel, braked main wheels */
  jet?: JetInfo;
  /** belly clearance under the collision box (m; default 0.16) */
  clearance?: number;
  /** wheel track of the front axle when it differs (a jet's nose wheel) and its wheel radius */
  frontTrack?: number;
  frontWheelRadius?: number;
  /** overall reverse ratio (default: 3.4 × the final drive; an electric car its forward ratio) */
  reverseRatio?: number;
}

const CARS: Record<RoadCarId, CarSpec> = {
  hayate: {
    id: 'hayate',
    name: 'SPRINTER TRUENO AE86',
    tagline: '軽量FRハッチバック',
    description: 'ハチロク。非力だが素直なハンドリングと軽さが武器。ドリフトの入りやすさは随一で、峠デビューに最適な一台。',
    drive: 'RWD',
    engineName: '直列4気筒 DOHC 1.6L 自然吸気',
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
    // our own model (tools/blender/cars/hayate*.py, fitted to photos): pop-up lamps modelled raised (popup_l/_r, folded
    // by day), the beams start at their lenses; the tailpipe anchor comes from its mesh
    model: { title: 'スプリンタートレノ AE86 GT-APEX（後期）', author: 'TOUGE NOCTURNE', url: '', license: '自作', own: true },
  },
  raijin: {
    id: 'raijin',
    name: 'IMPREZA WRX STI',
    tagline: 'ターボ4WDセダン',
    description: '強烈なトルクと4WDのトラクションで立ち上がりが圧倒的。安定志向で、タイムを狙いやすい。',
    drive: 'AWD',
    engineName: '水平対向4気筒 2.0L ターボ',
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
    colors: { body: '#d9dbde', accent: '#1d4fa8' },
    // the stock single tip, rear left
    exhaust: [0.456, 0.296, -2.3],
    // our own model (tools/blender/cars/raijin*.py, fitted to photos; GDB-C 2004 with the factory wing)
    model: { title: 'インプレッサ WRX STI (GDB)', author: 'TOUGE NOCTURNE', url: '', license: '自作', own: true },
  },
  shiden: {
    id: 'shiden',
    name: 'RX-7 (FD3S)',
    tagline: 'ロータリーFRスポーツ',
    description: '甲高く吹け上がるロータリーと低い重心。速いがピーキーで、腕次第で最速を狙えるじゃじゃ馬。',
    drive: 'RWD',
    engineName: '2ローター 1.3L ツインターボ',
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
    colors: { body: '#f5c400', accent: '#111111' },
    // our own model (tools/blender/cars/shiden*.py, fitted to photos): pop-up lamps modelled raised (popup_l/_r), the
    // beams start at their lenses; the tailpipe anchor comes from its mesh
    model: { title: 'RX-7（FD3S 後期 Type RS）', author: 'TOUGE NOCTURNE', url: '', license: '自作', own: true },
    // (its cabin is still blocks: dark glass until the model has a real one)
    glassOpacity: 0.88,
  },
  supra: {
    id: 'supra',
    name: 'SUPRA RZ (JZA80)',
    tagline: '直6ツインターボFR',
    description: '分厚いトルクで坂を押し切る重量級FR。直線は最速クラスだが、重さを感じさせない丁寧なブレーキングが鍵。',
    drive: 'RWD',
    engineName: '直列6気筒 3.0L ツインターボ',
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
    // our own model (tools/blender/cars/supra*.py, fitted to photos; late RZ with the factory wing; the tailpipe is its `exhaust` part)
    model: { title: 'スープラ RZ (JZA80)', author: 'TOUGE NOCTURNE', url: '', license: '自作', own: true },
  },
  r34: {
    id: 'r34',
    name: 'SKYLINE GT-R (BNR34)',
    tagline: '直6ツインターボ4WD',
    description: '電子制御4WDが路面をつかみ、どこからでも加速する。重いがとにかく安定し、速さを引き出しやすい。',
    drive: 'AWD',
    engineName: '直列6気筒 2.6L ツインターボ',
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
    // our own model (tools/blender/cars/r34*.py, fitted to photos; V-spec look, the tailpipe is its `exhaust` part)
    model: { title: 'スカイライン GT-R (BNR34)', author: 'TOUGE NOCTURNE', url: '', license: '自作', own: true },
  },
  s15: {
    id: 's15',
    name: 'SILVIA spec-R (S15)',
    tagline: 'ターボFRクーペ',
    description: '軽い車体にほどよいターボ。テールの出方が素直で扱いやすい、ドリフトの教科書のような一台。',
    drive: 'RWD',
    engineName: '直列4気筒 2.0L ターボ',
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
    colors: { body: '#f5cf30', accent: '#111111' },
    // our own model (tools/blender/cars/s15*.py, fitted to photos; stock spec-R without the wing, `s15.py --wing` adds it)
    model: { title: 'シルビア S15 spec-R', author: 'TOUGE NOCTURNE', url: '', license: '自作', own: true },
  },
  cybertruck: {
    id: 'cybertruck',
    name: 'CYBERTRUCK',
    tagline: '3モーターの電動ピックアップ',
    description: 'ステンレスの平らな板で組んだテスラの電動ピックアップ（サイバービースト）。3トンを超える巨体が3つのモーターで0→100km/hを2.7秒で駆け抜ける。重さと背の高さはコーナーで正直に出る。',
    drive: 'AWD',
    engineName: '3モーター（前1・後2）電動 AWD',
    frontTorqueSplit: 0.4,
    // Cyberbeast: 6843 lb at the kerb
    mass: 3104,
    size: { width: 2.03, height: 1.1, length: 5.68 },
    // 143.1 in
    wheelbase: 3.635,
    track: 1.76,
    comForward: 0,
    // the battery sits low; higher than this the 3 t truck rolled over in hairpins at its grip
    comHeight: 0.62,
    // 35-inch tyres (LT285/65R20)
    wheelRadius: 0.452,
    suspension: { rest: 0.36, stiffness: 95000, damping: 9000, antiRoll: 30000 },
    engine: {
      idleRpm: 0,
      // the reduction gear reaches the 209 km/h limit (130 mph) at the motors' top speed
      redline: 11100,
      // ~630 kW (845 hp) together: full pull to ~2800 rpm (the tyres' limit at 1.2 g), then constant power
      torque: [[0, 2124], [2830, 2124], [4500, 1337], [6500, 925], [9000, 668], [11100, 542]],
      cylinders: 0,
      turbo: false,
      electric: true,
    },
    gears: [1],
    finalDrive: 9.04,
    // all-terrain tyres under 3 t
    gripFront: 1.16,
    gripRear: 1.14,
    maxSteerDeg: 32,
    brakeForce: 28000,
    // a big flat front: Cd ~0.34 × 3 m²
    dragCoef: 0.62,
    downforce: 0.05,
    driftiness: 0.3,
    stats: { power: 10, grip: 5, drift: 3, weight: 1 },
    colors: { body: '#b9bdc0', accent: '#1b1c1f' },
    // the body is bare brushed stainless (the other swatches are wraps)
    bareMetal: { colors: ['#b9bdc0'], roughness: 0.3 },
    // the light bar's lens texture is smoked dark, as on the unlit truck: the lamps glow through it
    tailLampGain: 12,
    model: { title: 'Cybertruck（Cyberbeast）', author: 'TOUGE NOCTURNE', url: '', license: '自作', own: true },
  },
  u9: {
    id: 'u9',
    name: 'YANGWANG U9 Xtreme',
    tagline: '最高速503km/hの電動ハイパーカー',
    description: 'BYDの高級ブランド仰望（ヤンワン）が1200Vの4モーターで3000馬力を絞り出したハイパーカー。2026年11月、量産車の最高速度503.17km/hをギネスとFIAが認定した。峠ではその力を路面に伝えきれるかが勝負。',
    drive: 'AWD',
    engineName: '4モーター（各555kW）電動 AWD・1200V',
    frontTorqueSplit: 0.45,
    mass: 2480,
    size: { width: 2.03, height: 0.66, length: 4.99 },
    wheelbase: 2.9,
    track: 1.72,
    comForward: -0.05,
    comHeight: 0.4,
    wheelRadius: 0.36,
    suspension: { rest: 0.3, stiffness: 82000, damping: 7200, antiRoll: 26000 },
    engine: {
      idleRpm: 0,
      // the motors spin to 30,000 rpm: 503 km/h at that speed on the reduction gear
      redline: 30000,
      // 2,220 kW together: full pull (the semi-slicks' limit, ~1.5 g) to ~10,600 rpm (~180 km/h), then constant power
      torque: [[0, 2000], [10600, 2000], [16000, 1325], [20000, 1060], [25000, 848], [30000, 707]],
      cylinders: 0,
      turbo: false,
      electric: true,
    },
    gears: [1],
    finalDrive: 8.09,
    // semi-slick tyres
    gripFront: 1.56,
    gripRear: 1.54,
    maxSteerDeg: 33,
    brakeForce: 30000,
    // tuned so the record's 503 km/h is its flat-out top speed on the level
    dragCoef: 0.6,
    downforce: 0.55,
    // as the cockroach: beyond ~290 km/h the springs would sink under the downforce
    downforceTopSpeed: 80,
    // the cars' body damping would cap it far below its top speed (as the cockroach's)
    damping: 0.004,
    driftiness: 0.3,
    stats: { power: 10, grip: 9, drift: 4, weight: 4 },
    colors: { body: '#1b1d22', accent: '#c9d400' },
    model: { title: '仰望 U9 Xtreme', author: 'TOUGE NOCTURNE', url: '', license: '自作', own: true },
  },
};

export const CAR_SPECS: Record<CarId, CarSpec> = {
  ...CARS,
  ...BIKE_SPECS,
  ...TANK_SPECS,
  ...JET_SPECS,
  ...(Object.fromEntries(TRAIN_ORDER.map((id) => [id, trainSpec(id)])) as Record<TrainId, CarSpec>),
  roach: ROACH_SPEC,
};

/** the cars (AI rivals, bot ghosts and models use these) */
export const CAR_ORDER: CarId[] = ['hayate', 's15', 'shiden', 'supra', 'raijin', 'r34', 'cybertruck', 'u9'];
/** everything a player can drive: the cars, the motorcycles, the tanks, the fighters (Edwards only: `allowedOn`), the
 * trains, then the cockroach */
/**
 * The tanks (no cannon yet) and the fighters with their course are kept out of every player-facing list until
 * their switch is on (`release.ts`).
 */
export const VEHICLE_ORDER: CarId[] = [...CAR_ORDER, ...BIKE_ORDER, ...(RELEASED.tanks ? TANK_ORDER : []), ...(RELEASED.edwards ? JET_ORDER : []), ...TRAIN_ORDER, 'roach'];

/** what a player may drive on a course (the fighters only at Edwards) */
export const vehiclesFor = (courseId: string): CarId[] => VEHICLE_ORDER.filter((id) => !CAR_SPECS[id].jet || CAR_SPECS[id].jet!.courses.includes(courseId));

/** one fixed ratio (trains, the cockroach, electric cars): no AT/MT choice */
export const singleRatio = (spec: CarSpec) => spec.gears.length === 1;

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
