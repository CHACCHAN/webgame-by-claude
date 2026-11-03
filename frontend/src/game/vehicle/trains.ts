import type { CarSpec } from './carSpecs';
import { E231_MITSUBISHI, GINZA_TOSHIBA_STANDIN, N700_APPROX, type VvvfPattern } from './vvvf';

/**
 * Joke entries: three-car trains driven on the pass. The performance is the real train's (starting acceleration,
 * design top speed, emergency brake rate, gear ratio, wheel size); only the front bogie is simulated (a short heavy
 * vehicle), the three cars follow its path like rails (render/TrainModel.ts).
 */
export type TrainId = 'e231' | 'jr117' | 'keisei3300' | 'ginza1000' | 'n700';

/** Sound of the traction equipment (audio/TrainSound.ts). */
export type MotorKind = 'sic' | 'igbt3' | 'igbt' | 'chopper' | 'resistor';

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

export interface SoundCredit {
  title: string;
  author: string;
  license: string;
  url: string;
}

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
  front: FrontStyle;
  liveries: Livery[];
  /**
   * Lights of the model (car-local, measured on head-on renders): head lamps on the leading cab, tail lamps on the
   * trailing cab (put on the surface by a ray from ahead), and the height band of the side windows lit at night
   * with the brightness (linear luminance) up to which a texel there counts as window (default 0.1).
   */
  lamps?: { head: LampPair; tail: LampPair; windows: [number, number]; windowLum?: number };
  /**
   * A recording of the traction equipment pulling away (public/audio/<file>.mp3, credits in docs/ASSETS.md) and
   * when it reached which speed: [seconds into the clip, km/h], rising. Played at the point matching the speed.
   */
  motorSound?: { file: string; knots: [number, number][]; gain?: number; credit: SoundCredit };
  /** running noise (wheels, rails, rumble) heard whenever the train moves: a loop (public/audio/<file>.mp3, its seamless
   * window `loop` in s) recorded at `speed` km/h, played faster or slower with the speed */
  runningSound?: { file: string; loop: [number, number]; speed: number; gain?: number; credit: SoundCredit };
  /** VVVF inverter: synthesised from this control pattern (instead of a motor recording) */
  vvvf?: VvvfPattern;
}

/**
 * The trains with a 3D model (public/models/trains/<id>.glb, cut by tools/import-trains.cjs). Figures from Japanese
 * Wikipedia (2026-11-03): starting acceleration, design top speed, brake rates, motors, control, gear ratio,
 * car length; masses as marked.
 */
export const TRAIN_INFO: Record<TrainId, TrainInfo & { name: string; tagline: string; description: string; model: { title: string; author: string; url: string; license: string } }> = {
  e231: {
    name: 'E231系', series: 'E231系0番台（中央・総武緩行線）', operator: 'JR東日本', tagline: '首都圏の標準通勤形',
    description: '首都圏の通勤電車を一新した標準車両。IGBTのVVVFインバータの音はおなじみ。カナリアイエローの帯で峠を下る。',
    accel: 2.5, vmax: 120, brake: [4.2, 4.5], mass: 79.8, motor: 'MT73 95kW×4', control: 'IGBT-VVVFインバータ（3レベル・三菱電機）', sound: 'igbt3',
    gearRatio: 7.07, wheel: 0.86, body: 'stainless', width: 2.95, carLength: 20, bogies: 13.8, front: 'e231',
    liveries: [{ name: '中央・総武線（黄1号）', band: '#ffd400' }],
    // head and tail lamps share one unit under the windscreen
    lamps: { head: { x: 0.85, y: 1.19, w: 0.24, h: 0.14 }, tail: { x: 0.85, y: 1.19, w: 0.24, h: 0.14 }, windows: [1.78, 2.77] },
    // the inverter synthesised from its control pattern (vehicle/vvvf.ts)
    vvvf: E231_MITSUBISHI,
    runningSound: {
      file: 'run_emu', loop: [0.3, 63.3], speed: 110,
      credit: { title: '223系2000番台 東芝VVVF 惰性走行', author: '321keiHIKARI', license: 'CC BY-SA 3.0', url: "https://commons.wikimedia.org/wiki/File:TOSHIBA_Omi_imazu-Shin_asahi_M'_222-3031Dasei.ogg" },
    },
    model: { title: 'JR東日本E231系電車', author: 'own.guest', url: 'https://sketchfab.com/3d-models/98d47a9e4aca454d9c02eb2c690fdaee', license: 'CC BY 4.0' },
  },
  jr117: {
    name: '117系', series: '117系（快速サンライナー）', operator: '国鉄／JR西日本', tagline: '岡山の快速「サンライナー」',
    description: '京阪神の新快速として登場した2扉の近郊形。この編成は岡山地区の快速「サンライナー」の白い塗装。抵抗制御のモーター音を響かせて峠を下る。',
    // field weakening keeps the power up to high speed (it ran the 115 km/h rapid service)
    traction: [45, 100],
    accel: 2.0, vmax: 115, brake: [3.5, 5.0], mass: 115.5, motor: 'MT54D 120kW×4（直流直巻）', control: '抵抗制御（直並列・弱め界磁）', sound: 'resistor',
    gearRatio: 4.82, wheel: 0.86, body: 'painted', width: 2.9, carLength: 20, bogies: 13.8, front: 'jnr103',
    liveries: [{ name: 'サンライナー（白＋赤帯）', body: '#f2efe8', band: '#f2efe8', band2: '#d8261c' }],
    lamps: { head: { x: 0.56, y: 1.99, w: 0.22, h: 0.22, round: true }, tail: { x: 1.0, y: 1.3, w: 0.18, h: 0.18, round: true }, windows: [1.94, 2.85], windowLum: 0.4 },
    // on board a 117 motor car (MoHa 117-15) leaving a station; speeds from a motor line (0.237 km/h per Hz)
    motorSound: {
      file: 'motor_jr117', knots: [[3, 0], [25.5, 45], [35, 61], [45, 70.4], [55, 77.7], [65, 83.9], [75, 88.9], [85, 91.2], [105, 94.3], [120, 97.9], [135, 102.9], [150, 106.7], [160, 108.8]],
      credit: { title: '117系 モハ117-15 走行音', author: 'spaceaero2', license: 'CC BY 3.0', url: 'https://commons.wikimedia.org/wiki/File:JR_west_117_shinkaisoku_moha117-15_akashi.ogg' },
    },
    runningSound: {
      file: 'run_jr117', loop: [0.3, 61.3], speed: 105,
      credit: { title: '117系 モハ117-15 走行音', author: 'spaceaero2', license: 'CC BY 3.0', url: 'https://commons.wikimedia.org/wiki/File:JR_west_117_shinkaisoku_moha117-15_akashi.ogg' },
    },
    model: { title: '117系 サンライナー | 117 series『Sun Liner』', author: 'own.guest', url: 'https://sketchfab.com/3d-models/6434932c06974d10927c2fe36c2c7f8e', license: 'CC BY 4.0' },
  },
  keisei3300: {
    name: '京成3300形', series: '3300形（赤電）', operator: '京成電鉄', tagline: '昭和の私鉄「赤電」',
    description: '1968年登場、全車が電動車の京成の通勤車。起動加速度3.5km/h/sは今回の電車で最強。ファイヤーオレンジとモーンアイボリーの赤電塗装。',
    accel: 3.5, vmax: 110, brake: [4.0, 4.5], mass: 99, massEstimated: true, motor: '100kW×4（全電動車）', control: '抵抗制御', sound: 'resistor',
    gearRatio: 6.06, wheel: 0.86, body: 'painted', width: 2.8, carLength: 18, bogies: 12.6, front: 'jnr103',
    liveries: [{ name: '赤電（ファイヤーオレンジ＋モーンアイボリー）', body: '#e05a1a', band: '#e05a1a', band2: '#efe3c4' }],
    lamps: { head: { x: 0.8, y: 1.84, w: 0.22, h: 0.22 }, tail: { x: 1.1, y: 1.84, w: 0.22, h: 0.22 }, windows: [2.09, 3.08] },
    // Keikyu's first 1000 series (1959, all motor cars, resistor control, ran with Keisei's cars): 3.5 km/h/s to 40
    motorSound: {
      file: 'motor_keisei3300', knots: [[3.7, 0], [15.1, 40], [20, 54.4], [30, 75.9], [40, 92.5], [45, 99.8]],
      credit: { title: '京急旧1000形 走行音', author: 'toshinori baba', license: 'パブリックドメイン', url: 'https://commons.wikimedia.org/wiki/File:Keikyu_kyu1000kei_rokuon.ogg' },
    },
    runningSound: {
      file: 'run_jr117', loop: [0.3, 61.3], speed: 105,
      credit: { title: '117系 モハ117-15 走行音', author: 'spaceaero2', license: 'CC BY 3.0', url: 'https://commons.wikimedia.org/wiki/File:JR_west_117_shinkaisoku_moha117-15_akashi.ogg' },
    },
    model: { title: '京成3300形(赤電) 先頭車1・中間車1・先頭車2', author: 'V3B4', url: 'https://sketchfab.com/V3B4', license: 'CC BY-NC 4.0' },
  },
  ginza1000: {
    name: '東京メトロ1000系', series: '1000系（銀座線）', operator: '東京メトロ', tagline: '黄色い地下鉄',
    description: '日本最古の地下鉄、銀座線の現役車両。16m級の小さな車体に永久磁石同期電動機。設計最高速度は80km/h、峠では一番の小回り。',
    accel: 3.3, vmax: 80, brake: [4.0, 4.5], mass: 82.3, massEstimated: true, motor: 'MM-S2B 120kW（永久磁石同期電動機）', control: 'IGBT-VVVFインバータ（東芝）', sound: 'igbt',
    gearRatio: 7.79, wheel: 0.78, body: 'painted', width: 2.55, carLength: 16, bogies: 10.3, front: 'tobu10000',
    liveries: [{ name: 'レモンイエロー', body: '#f2b705', band: '#f2b705', band2: '#c8102e' }],
    // the head lamps sit high on the roof dome
    lamps: { head: { x: 0.16, y: 3.28, w: 0.26, h: 0.26, round: true }, tail: { x: 1.05, y: 1.19, w: 0.15, h: 0.15, round: true }, windows: [1.8, 2.82], windowLum: 0.32 },
    // the inverter synthesised from its control pattern (vehicle/vvvf.ts): a Toshiba stand-in (no PMSM pattern exists)
    vvvf: GINZA_TOSHIBA_STANDIN,
    runningSound: {
      file: 'run_emu', loop: [0.3, 63.3], speed: 110,
      credit: { title: '223系2000番台 東芝VVVF 惰性走行', author: '321keiHIKARI', license: 'CC BY-SA 3.0', url: "https://commons.wikimedia.org/wiki/File:TOSHIBA_Omi_imazu-Shin_asahi_M'_222-3031Dasei.ogg" },
    },
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
    // the inverter synthesised from its control pattern (vehicle/vvvf.ts): an approximation (none published)
    vvvf: N700_APPROX,
    runningSound: {
      file: 'run_n700', loop: [0.3, 61.3], speed: 203,
      credit: { title: '700系 のぞみ 車内走行音', author: 'spaceaero2', license: 'CC BY 3.0', url: 'https://commons.wikimedia.org/wiki/File:JR_central_700series_nozomi_387_717-53_shinosaka.ogg' },
    },
    model: { title: 'N700-3000 Series Shinkansen', author: 'Layo', url: 'https://sketchfab.com/3d-models/f70820be44e0467d8b1614f2aa3045bd', license: 'CC BY 4.0' },
  },
};

export const TRAIN_ORDER: TrainId[] = ['e231', 'jr117', 'keisei3300', 'ginza1000', 'n700'];

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
