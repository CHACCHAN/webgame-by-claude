import type { CarSpec } from './carSpecs';
import type { TrainRunning } from '../audio/running';
import { E231_MITSUBISHI, GINZA_TOSHIBA_STANDIN, KEIKYU_N1000_GTO, N700_ESTIMATE, type TrainVvvf } from './vvvf';

/**
 * Joke entries: three-car trains driven on the pass. The performance is the real train's (starting acceleration,
 * design top speed, emergency brake rate, gear ratio, wheel size); only the front bogie is simulated (a short heavy
 * vehicle), the three cars follow its path like rails (render/TrainModel.ts).
 */
export type TrainId = 'e231' | 'keikyu1000' | 'ginza1000' | 'n700';

/** Sound of the traction equipment (audio/TrainSound.ts). */
export type MotorKind = 'sic' | 'igbt3' | 'igbt' | 'gto' | 'chopper' | 'resistor';

/** One paint scheme: the swatch colour is `band` (the body colour of painted cars). */
export interface Livery {
  name: string;
  /** painted steel body; stainless / aluminium bodies stay bare */
  body?: string;
  band: string;
  band2?: string;
}

/** Face of the procedural stand-in body (used when the model is missing). */
export type FrontStyle = 'e235' | 'e231' | 'tobu50000' | 'tobu60000' | 'tobu8000' | 'tobu10000' | 'tobu30000' | 'jnr103';

/** A pair of lamps on a cab face (mirrored across the centre line): centre and size in metres; round = ellipse. */
export interface LampPair {
  x: number;
  y: number;
  w: number;
  h: number;
  round?: boolean;
}

export interface TrainInfo {
  series: string;
  operator: string;
  /** km/h/s */
  accel: number;
  /** design top speed, km/h */
  vmax: number;
  /** service and emergency brake rates, km/h/s */
  brake: [number, number];
  /** three cars, tonnes */
  mass: number;
  /** the mass is derived (no per-car figure published): shown as an estimate */
  massEstimated?: boolean;
  motor: string;
  control: string;
  sound: MotorKind;
  gearRatio: number;
  /** wheel diameter (m) */
  wheel: number;
  body: 'stainless' | 'aluminium' | 'painted';
  /** body width (m) */
  width: number;
  /** end of the constant-torque and of the constant-power region (km/h; commuter trains 40 / 80) */
  traction?: [number, number];
  /** aerodynamic drag of the simulated vehicle (default 0.2; a streamlined Shinkansen far less) */
  drag?: number;
  /** body damping of the simulated vehicle (default 0.002) */
  damping?: number;
  /** car length (m, coupler to coupler) and distance between its bogie centres */
  carLength: number;
  bogies: number;
  /** cars of unequal length (a Shinkansen's long-nosed end cars), in running order: see `trainCars` */
  consist?: TrainCar[];
  front: FrontStyle;
  liveries: Livery[];
  /**
   * Lights of the model (car-local, measured on head-on renders): head lamps on the leading cab, tail lamps on the
   * trailing cab (put on the surface by a ray from ahead), and the height band of the side windows lit at night
   * with the brightness (linear luminance) up to which a texel there counts as window (default 0.1).
   */
  lamps?: { head: LampPair; tail: LampPair; windows: [number, number]; windowLum?: number };
  /**
   * Running noise (wheels, rail joints, wind, rumble; synthesised by audio/running.ts): the track and body. Optional,
   * the defaults suit a commuter train on jointed track.
   */
  running?: TrainRunning;
  /** VVVF inverter: VVVF-Simulator's calculation on a control pattern */
  vvvf?: TrainVvvf;
}

/**
 * One car of the three, in running order: its length (coupler to coupler; an end car's from the nose tip), the
 * distance between its bogie centres, and how far its leading bogie sits behind its leading end (the trailing car
 * runs turned round: its leading end is its coupler end).
 */
export interface TrainCar {
  length: number;
  bogies: number;
  front: number;
}

/** The three cars of a train (equal cars with centred bogies unless `consist` says otherwise). */
export function trainCars(t: Pick<TrainInfo, 'carLength' | 'bogies' | 'consist'>): TrainCar[] {
  return t.consist ?? [0, 1, 2].map(() => ({ length: t.carLength, bogies: t.bogies, front: (t.carLength - t.bogies) / 2 }));
}

/**
 * Where each car runs, as distances back along the driven path from the leading bogie (the simulated vehicle): its
 * leading and trailing bogie. Cars meet at their couplers.
 */
export function trainBogiePath(t: Pick<TrainInfo, 'carLength' | 'bogies' | 'consist'>): [number, number][] {
  let s = 0;
  return trainCars(t).map((c, k, cars) => {
    if (k > 0) s += cars[k - 1].length - cars[k - 1].front + c.front;
    return [s, s + c.bogies];
  });
}

/** The leading car's nose ahead of its origin (the midpoint between its bogies), m. */
export const trainNoseZ = (t: Pick<TrainInfo, 'carLength' | 'bogies' | 'consist'>) => {
  const c = trainCars(t)[0];
  return c.bogies / 2 + c.front;
};

/** The trailing car's tail behind its origin, m. */
export const trainTailZ = (t: Pick<TrainInfo, 'carLength' | 'bogies' | 'consist'>) => {
  const c = trainCars(t)[2];
  return c.length - c.front - c.bogies / 2;
};

/**
 * The trains with a 3D model (public/models/trains/<id>.glb: cut from a third-party model by tools/import-trains.cjs,
 * or our own built in Blender by tools/blender-models.cjs, `model.own`). Figures from Japanese Wikipedia
 * (2026-11-03): starting acceleration, design top speed, brake rates, motors, control, gear ratio, car length;
 * masses as marked.
 */
export const TRAIN_INFO: Record<TrainId, TrainInfo & { name: string; tagline: string; description: string; model: { title: string; author: string; url: string; license: string; own?: boolean } }> = {
  e231: {
    name: 'E231系', series: 'E231系0番台（中央・総武緩行線）', operator: 'JR東日本', tagline: '首都圏の標準通勤形',
    description: '首都圏の通勤電車を一新した標準車両。IGBTのVVVFインバータの音はおなじみ。カナリアイエローの帯で峠を下る。',
    accel: 2.5, vmax: 120, brake: [4.2, 4.5], mass: 79.8, motor: 'MT73 95kW×4', control: 'IGBT-VVVFインバータ（3レベル・三菱電機）', sound: 'igbt3',
    gearRatio: 7.07, wheel: 0.86, body: 'stainless', width: 2.95, carLength: 20, bogies: 13.8, front: 'e231',
    liveries: [{ name: '中央・総武線（黄1号）', band: '#ffd400' }],
    // head and tail lamps share one unit under the windscreen
    lamps: { head: { x: 0.85, y: 1.19, w: 0.24, h: 0.14 }, tail: { x: 0.85, y: 1.19, w: 0.24, h: 0.14 }, windows: [1.78, 2.77] },
    // the in-train sound calculated from the inverter's control pattern (vehicle/vvvf.ts, audio/vvvf)
    vvvf: E231_MITSUBISHI,
    model: { title: 'JR東日本E231系電車', author: 'own.guest', url: 'https://sketchfab.com/3d-models/98d47a9e4aca454d9c02eb2c690fdaee', license: 'CC BY 4.0' },
  },
  keikyu1000: {
    name: '京急新1000形', series: '新1000形 1次車（2002年）', operator: '京浜急行電鉄', tagline: '発車で音階を奏でる「ドレミファインバータ」',
    description: '赤い車体に白い窓まわりの京急の主力。1・2次車はシーメンス製GTOのVVVFインバータで、発車のたびに「ファソラシドレミファソ～」と音階を奏でた。起動加速度3.5km/h/sの俊足で峠を下る。',
    accel: 3.5, vmax: 130, brake: [4.0, 4.5],
    // 4-car set of the 1st batch: Muc 33.0 t + Tpu 26.5 t + Msc 33.0 t (the formation's cars, one trailer left out)
    mass: 92.5, motor: 'シーメンス 1TB2010 190kW×4（かご形三相誘導電動機）', control: 'GTO-VVVFインバータ（シーメンス SIBAS32・1C4M）', sound: 'gto',
    // gear 83:14; wheel and bogie centres are our estimates (not published)
    gearRatio: 5.93, wheel: 0.86, body: 'painted', width: 2.83, carLength: 18, bogies: 12, front: 'tobu50000',
    liveries: [{ name: '京急レッド＋窓まわり白', body: '#d2192b', band: '#d2192b', band2: '#efeee8' }],
    // our own model (tools/blender/keikyu1000.py, parts/body_n1000.py): head lamps high in the windscreen (HEADLAMP),
    // the tail lamp the inner half of each lamp unit low on the nose (express lamp outside), side windows WIN
    lamps: { head: { x: 1.085, y: 3.16, w: 0.1, h: 0.1, round: true }, tail: { x: 0.844, y: 1.39, w: 0.17, h: 0.12 }, windows: [1.93, 2.81], windowLum: 0.06 },
    // the in-train sound calculated from the inverter's control pattern (vehicle/vvvf.ts, audio/vvvf): the scale is the
    // asynchronous carrier stepping through F G A B♭ C D E♭ F at the start
    vvvf: KEIKYU_N1000_GTO,
    model: { title: '京急新1000形 1次車', author: 'TOUGE NOCTURNE', url: '', license: '自作', own: true },
  },
  ginza1000: {
    name: '東京メトロ1000系', series: '1000系（銀座線）', operator: '東京メトロ', tagline: '黄色い地下鉄',
    description: '日本最古の地下鉄、銀座線の現役車両。16m級の小さな車体に永久磁石同期電動機。設計最高速度は80km/h、峠では一番の小回り。',
    accel: 3.3, vmax: 80, brake: [4.0, 4.5], mass: 82.3, massEstimated: true, motor: 'MM-S2B 120kW（永久磁石同期電動機）', control: 'IGBT-VVVFインバータ（東芝）', sound: 'igbt',
    gearRatio: 7.79, wheel: 0.78, body: 'painted', width: 2.55, carLength: 16, bogies: 10.3, front: 'tobu10000',
    liveries: [{ name: 'レモンイエロー', body: '#f2b705', band: '#f2b705', band2: '#c8102e' }],
    // the head lamps sit high on the roof dome
    lamps: { head: { x: 0.16, y: 3.28, w: 0.26, h: 0.26, round: true }, tail: { x: 1.05, y: 1.19, w: 0.15, h: 0.15, round: true }, windows: [1.8, 2.82], windowLum: 0.32 },
    // the in-train sound calculated from a control pattern (vehicle/vvvf.ts): a Toshiba stand-in (no PMSM pattern exists)
    vvvf: GINZA_TOSHIBA_STANDIN,
    model: { title: 'Japan Train Tokyo Metro Ginza Line (low poly)', author: 'ditovirnantio', url: 'https://sketchfab.com/3d-models/dc622d519f8d4b7ab1fd478815d129f8', license: 'CC BY 4.0' },
  },
  n700: {
    name: '新幹線N700系', series: 'N700系', operator: 'JR東海／JR西日本', tagline: '峠を下る新幹線（ネタ枠の本命）',
    description: '設計最高速度330km/hの新幹線。ただしブレーキは非常でも3.64km/h/s、下り坂ではまず止まらない。25mの長い車体で峠のヘアピンに挑む。',
    // 0→270 km/h takes about three minutes: full torque far higher than on a commuter train
    traction: [90, 300], drag: 0.03, damping: 0.0004,
    accel: 2.6, vmax: 330, brake: [2.7, 3.64], mass: 134, massEstimated: true, motor: '305kW×4（かご形三相誘導電動機）', control: 'PWMコンバータ＋IGBT-VVVFインバータ', sound: 'igbt',
    gearRatio: 2.79, wheel: 0.86, body: 'painted', width: 3.36, carLength: 25, bogies: 17.5, front: 'e231',
    liveries: [{ name: '白＋青帯', body: '#f4f5f6', band: '#1f3d8f' }],
    // lamps low on the sides of the nose
    lamps: { head: { x: 0.85, y: 1.05, w: 0.36, h: 0.12, round: true }, tail: { x: 0.85, y: 1.05, w: 0.36, h: 0.12, round: true }, windows: [1.72, 2.26] },
    // the in-train sound calculated from a control pattern (vehicle/vvvf.ts): our estimate (none published)
    vvvf: N700_ESTIMATE,
    // welded rail on slab track, 2.5 m bogies, pressure-tight body (audio/running.ts)
    running: { rail: 'welded', axle: 2.5, sealed: true },
    model: { title: 'N700-3000 Series Shinkansen', author: 'Layo', url: 'https://sketchfab.com/3d-models/f70820be44e0467d8b1614f2aa3045bd', license: 'CC BY 4.0' },
  },
};

export const TRAIN_ORDER: TrainId[] = ['e231', 'keikyu1000', 'ginza1000', 'n700'];

/** Simulated mass of the front bogie vehicle (kg): forces are scaled to give the real accelerations. */
const PHYS_MASS = 4200;
/** rolling resistance of steel wheels (share of the load; the sim's default 1.5 % is for tyres) */
const ROLLING = 0.002;

/**
 * Motor torque curve that reproduces the train's acceleration: constant up to the base speed, then constant power,
 * then the characteristic region (∝ 1/v²), as electric traction does (`TrainInfo.traction`).
 */
function tractionCurve(t: TrainInfo) {
  const r = t.wheel / 2;
  const f0 = PHYS_MASS * (t.accel / 3.6 + ROLLING * 9.81);
  const [vb, vp] = (t.traction ?? [40, 80]).map((k) => k / 3.6);
  const toRpm = (v: number) => ((v / r) * t.gearRatio * 60) / (2 * Math.PI);
  const force = (v: number) => (v <= vb ? f0 : v <= vp ? (f0 * vb) / v : (f0 * vb * vp) / (v * v));
  const top = (t.vmax / 3.6) * 1.05;
  const speeds = [0, vb, (vb + vp) / 2, vp, (vp + top) / 2, top];
  return speeds.map((v) => [Math.round(toRpm(v)), Math.round((force(v) * r) / (t.gearRatio * 0.86))] as [number, number]);
}

export function trainSpec(id: TrainId): CarSpec {
  const t = TRAIN_INFO[id];
  const r = t.wheel / 2;
  const redline = Math.round((((t.vmax / 3.6) / r) * t.gearRatio * 60) / (2 * Math.PI));
  const power = Math.round(2 + (t.accel - 2) * 4);
  return {
    id,
    name: t.name,
    tagline: t.tagline,
    description: t.description,
    engineName: t.control,
    drive: 'AWD',
    frontTorqueSplit: 0.5,
    mass: PHYS_MASS,
    // the simulated front bogie: a short, wide, low vehicle (the cars behind follow its path)
    size: { width: t.width, height: 0.7, length: 5 },
    wheelbase: 3.4,
    track: 2.0,
    comForward: 0,
    comHeight: 0.5,
    wheelRadius: r,
    suspension: { rest: 0.32, stiffness: 150000, damping: 13000, antiRoll: 40000 },
    engine: { idleRpm: 0, redline, torque: tractionCurve(t), cylinders: 0, turbo: false, electric: true },
    gears: [1],
    finalDrive: t.gearRatio,
    gripFront: 1.0,
    gripRear: 1.0,
    maxSteerDeg: 38,
    // full brake = the emergency rate (km/h/s → m/s²)
    brakeForce: Math.round(PHYS_MASS * (t.brake[1] / 3.6)),
    dragCoef: t.drag ?? 0.2,
    downforce: 0,
    // the cars' body damping would cap a train near 70 km/h
    damping: t.damping ?? 0.002,
    rolling: ROLLING,
    driftiness: 0.05,
    stats: { power: Math.min(10, Math.max(1, power)), grip: 4, drift: 0, weight: 1 },
    colors: { body: t.liveries[0].band, accent: '#2a2d33' },
    // a train's tail lamps are its only red light at night: brighter than a car's position lamps
    tailLampGain: 1.6,
    model: t.model,
    train: t,
  };
}
