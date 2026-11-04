import type { CarSpec } from './carSpecs';
import type { TrainRunning } from '../audio/running';
import { E231_MITSUBISHI, E231_MUSASHINO_MITSUBISHI, E235_MITSUBISHI_SIC, E5_ESTIMATE, KEIKYU_N1000_GTO, TOBU30000_HITACHI, type TrainVvvf } from './vvvf';

/**
 * Joke entries: three-car trains driven on the pass. The performance is the real train's (starting acceleration,
 * design top speed, emergency brake rate, gear ratio, wheel size); only the front bogie is simulated (a short heavy
 * vehicle), the three cars follow its path like rails (render/TrainModel.ts).
 */
export type TrainId = 'e231' | 'e235' | 'keikyu1000' | 'tobu30000' | 'e5';

/** Sound of the traction equipment (audio/TrainSound.ts). */
export type MotorKind = 'sic' | 'igbt3' | 'igbt' | 'gto' | 'chopper' | 'resistor';

/**
 * One paint scheme, usually a line the train runs on: its colours, the model variant painted and signed for that line,
 * and what differs on that line's cars. The swatch in the car select is `swatch` or else `band`; it identifies the
 * livery everywhere (chosen colour, races, ghosts).
 */
export interface Livery {
  name: string;
  /** painted steel body; stainless / aluminium bodies stay bare */
  body?: string;
  band: string;
  band2?: string;
  /** swatch when two liveries share a band colour (same paint, another line) */
  swatch?: string;
  /** model variant for this line (public/models/trains/<id>-<variant>.glb: its paint and displays); default the base model */
  variant?: string;
  /** series and control equipment as fitted for this line (default: the train's) */
  series?: string;
  control?: string;
  /** the inverter on this line's cars (default: the train's) */
  vvvf?: TrainVvvf;
  /** lights of this line's model when its cab differs (another sub-series; default: the train's `lamps`) */
  lamps?: TrainLamps;
}

export const liverySwatch = (l: Livery) => l.swatch ?? l.band;

/** The livery a chosen colour stands for (the first one for any other colour). */
export const trainLivery = (t: Pick<TrainInfo, 'liveries'>, color?: string) => t.liveries.find((l) => liverySwatch(l) === color) ?? t.liveries[0];

/** File of the model drawn for a livery: public/models/trains/<key>.glb. */
export const trainModelKey = (id: string, l?: Livery) => (l?.variant ? `${id}-${l.variant}` : id);

/** Face of the procedural stand-in body (used when the model is missing). */
export type FrontStyle = 'e235' | 'e231' | 'tobu50000' | 'tobu60000' | 'tobu8000' | 'tobu10000' | 'tobu30000' | 'jnr103';

/** A pair of lamps on a cab face (mirrored across the centre line): centre and size in metres; round = ellipse. */
export interface LampPair {
  x: number;
  y: number;
  w: number;
  h: number;
  round?: boolean;
  /** lamps per side (default 1): the next ones `gap` m further out (the E5's row of four) */
  n?: number;
  gap?: number;
}

export interface TrainLamps {
  head: LampPair;
  tail: LampPair;
  windows: [number, number];
  windowLum?: number;
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
  lamps?: TrainLamps;
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
 * The trains with a 3D model (public/models/trains/<id>.glb: our own, built in Blender by tools/blender-models.cjs from
 * tools/blender/<id>.py, `model.own`). Figures from Japanese Wikipedia (2026-11-03): starting acceleration, design top
 * speed, brake rates, motors, control, gear ratio, car length; masses as marked.
 */
export const TRAIN_INFO: Record<TrainId, TrainInfo & { name: string; tagline: string; description: string; model: { title: string; author: string; url: string; license: string; own?: boolean } }> = {
  e231: {
    name: 'E231系', series: 'E231系0番台（武蔵野線）', operator: 'JR東日本', tagline: '武蔵野線・総武線・常磐線・東西線直通',
    description: 'JR東日本の通勤形の標準になったE231系。武蔵野線の車は機器更新でVVVFが三菱の2レベルIGBTに。カラーで武蔵野線・総武線各駅停車・常磐線快速、車体の細い800番台（地下鉄東西線直通）を選べる。',
    accel: 2.5, vmax: 120, brake: [4.2, 4.5], mass: 79.8, motor: 'MT73 95kW×4', control: 'IGBT-VVVFインバータ（2レベル・三菱電機、機器更新車）', sound: 'igbt',
    gearRatio: 7.07, wheel: 0.86, body: 'stainless', width: 2.95, carLength: 20, bogies: 13.8, front: 'e231',
    // the lines it runs on: Wikipedia (E231, 武蔵野線) orange #f15a22 + brown #3c060f (the cab front: orange only); the
    // Chuo-Sobu local's 黄1号, with the cars' original equipment (renewed only on the move to the Musashino Line)
    liveries: [
      { name: '武蔵野線', band: '#f15a22', band2: '#3c060f' },
      { name: '総武線各駅停車', band: '#ffd400', variant: 'sobu', series: 'E231系0番台（中央・総武緩行線）', control: 'IGBT-VVVFインバータ（3レベル・三菱電機）', vvvf: E231_MITSUBISHI },
      // Joban rapid / Narita Line (Matsudo sets): emerald over a yellow-green line, the cab face white FRP
      { name: '常磐線', band: '#339999', band2: '#99cc00', variant: 'joban', series: 'E231系0番台（常磐線快速）', control: 'IGBT-VVVFインバータ（3レベル・三菱電機）', vvvf: E231_MITSUBISHI },
      // E231-800 (Chuo-Sobu local through to the Tozai Line): its own 2.8 m body and asymmetric cab (the emergency door
      // on one side), sky blue under a dark blue line; lamps measured on its own model
      {
        name: '地下鉄東西線直通', band: '#00b2e5', band2: '#1d2f8c', variant: 'tozai', series: 'E231系800番台（地下鉄東西線直通）', control: 'IGBT-VVVFインバータ（三菱電機）', vvvf: E231_MITSUBISHI,
        lamps: { head: { x: 0.8, y: 1.439, w: 0.205, h: 0.175 }, tail: { x: 1.085, y: 1.439, w: 0.205, h: 0.175 }, windows: [1.95, 2.86], windowLum: 0.06 },
      },
    ],
    lamps: { head: { x: 0.79, y: 1.367, w: 0.2, h: 0.16 }, tail: { x: 1.05, y: 1.367, w: 0.19, h: 0.15 }, windows: [1.93, 2.86], windowLum: 0.06 },
    // the in-train sound calculated from the inverter's control pattern (vehicle/vvvf.ts, audio/vvvf)
    vvvf: E231_MUSASHINO_MITSUBISHI,
    model: { title: 'E231系0番台', author: 'TOUGE NOCTURNE', url: '', license: '自作', own: true },
  },
  e235: {
    name: 'E235系', series: 'E235系0番台（山手線）', operator: 'JR東日本', tagline: '山手線・横須賀・総武快速線・総武線各駅停車',
    description: '山手線の現役車両。SiC素子のVVVFで高速域も1パルスにせず27パルスで走る。カラーでウグイス色の山手線、スカ色の横須賀・総武快速線（1000番台）、2026年に移った黄色の総武線各駅停車を選べる。',
    // accel 3.0, design top 120, service brake 4.2; emergency 4.5 estimated (as E231 / E233)
    accel: 3.0, vmax: 120, brake: [4.2, 4.5],
    // クハE235 33.3 t + モハE235 31.7 t + クハE234 33.4 t
    mass: 98.4, motor: 'MT79 140kW×4（かご形三相誘導電動機）', control: 'フルSiC-VVVFインバータ（2レベル・三菱電機 SC104・1C4M）', sound: 'sic',
    // gear 7.07 (99:14); wheel and bogie centres estimated (JR East 20 m standard)
    gearRatio: 7.07, wheel: 0.86, body: 'stainless', width: 2.95, carLength: 20, bogies: 13.8, front: 'e235',
    // the lines: 山手線 (ウグイス色 #9acd32, black cab front) and the 1000番台 of the 横須賀・総武快速線 (スカ色: blue
    // #0067c0, the line colour, and cream)
    liveries: [
      { name: '山手線', band: '#9acd32', band2: '#1a1a1a' },
      { name: '横須賀・総武快速線', band: '#0067c0', band2: '#e8dcb0', variant: 'sobu', series: 'E235系1000番台（横須賀・総武快速線）' },
      // sets moved from the Yamanote Line in 2026, repainted canary yellow (no photo yet: the Yamanote layout recoloured)
      { name: '総武線各駅停車', band: '#ffd400', band2: '#1a1a1a', variant: 'chuosobu', series: 'E235系0番台（中央・総武緩行線）' },
    ],
    // our own model (tools/blender/e235.py): head lamps high at the outer ends of the black panel, the tail lamps beside
    // the front LED display; side windows (glass far darker than the stainless around it)
    lamps: { head: { x: 0.914, y: 3.37, w: 0.135, h: 0.12 }, tail: { x: 0.62, y: 3.35, w: 0.1, h: 0.16 }, windows: [1.915, 2.865], windowLum: 0.06 },
    vvvf: E235_MITSUBISHI_SIC,
    model: { title: 'E235系', author: 'TOUGE NOCTURNE', url: '', license: '自作', own: true },
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
  tobu30000: {
    name: '東武30000系', series: '30000系', operator: '東武鉄道', tagline: '半蔵門線直通のために生まれた',
    description: '半蔵門線への直通用に1996年に登場したステンレス車で、日立の3レベルIGBTインバータ。伊勢崎線から直通運転をこなし、今は東上線を走る。カラーでどちらも選べる。',
    // accel 3.3 (2.5 coupled with the 10000s), design top 120, service 3.5, emergency 4.5
    accel: 3.3, vmax: 120, brake: [3.5, 4.5],
    // only 29.0–37.5 t per car published: クハ31600 ~30.0 + モハ32600 (pantographs, VVVF, compressor) ~37.5 + クハ36600 ~30.0
    mass: 97.5, massEstimated: true, motor: 'TM-95 190kW×4（かご形三相誘導電動機）', control: 'IGBT-VVVFインバータ（3レベル・日立製作所 VFI-HR1420B・1C4M）', sound: 'igbt3',
    // gear 99:14; wheel and bogie centres estimated; 車体基準幅 2,770
    gearRatio: 7.07, wheel: 0.86, body: 'stainless', width: 2.77, carLength: 20, bogies: 13.8, front: 'tobu30000',
    // ロイヤルマルーン: the film sampled in sunlight on photos (#c0184a…#b31946; the model's colour). The same paint on
    // both lines it has run on: 東上線 (since 2011) and 伊勢崎線 (1996–2011, through to the Hanzomon Line); the
    // swatches differ by a hair so they stay apart
    liveries: [
      { name: '東上線', band: '#b91848' },
      { name: '伊勢崎線', band: '#b91848', swatch: '#b9184a', variant: 'isesaki' },
    ],
    // our own model (tools/blender/tobu30000.py): one chrome-framed unit per side in the red band, the LED head lamp
    // inside, the tail lamp outside; side windows
    lamps: { head: { x: 0.825, y: 1.435, w: 0.196, h: 0.116 }, tail: { x: 1.065, y: 1.435, w: 0.2, h: 0.14 }, windows: [1.98, 2.91], windowLum: 0.06 },
    vvvf: TOBU30000_HITACHI,
    model: { title: '東武30000系', author: 'TOUGE NOCTURNE', url: '', license: '自作', own: true },
  },
  e5: {
    name: '新幹線E5系', series: 'E5系（はやぶさ）', operator: 'JR東日本', tagline: '最高速度320km/h・東北／北海道新幹線',
    description: '東北新幹線の主力。15mの長いノーズで営業最高速度320km/h。常盤グリーンと飛雲ホワイトの車体にはやてピンクの帯（北海道新幹線のH5系は彩香パープル）。下り坂の峠ではブレーキの効きが心配。',
    // max 320 (balancing speed 360 on +3 ‰); accel 1.71. The rated 9,600 kW over 453.5 t at 1.71 km/h/s puts the end
    // of constant torque near 140–150 km/h (estimated)
    traction: [140, 320], drag: 0.03, damping: 0.0004,
    // no brake rates published: estimated like the N700's
    accel: 1.71, vmax: 320, brake: [2.7, 3.6],
    // E523 41.9 t + E525 (pantograph, converter-inverter) 46.0 t + E514 42.7 t
    mass: 130.6, motor: 'MT207 300kW×4（かご形三相誘導電動機）', control: '3レベルPWMコンバータ＋IGBT-VVVFインバータ（CI18・三菱電機／東芝／日立）', sound: 'igbt3',
    // gear 82:31 (2.645), wheel 860 mm, aluminium double skin (painted), width 3,350; end cars 26.5 m, middle 25 m,
    // bogie centres 17.5 m (estimated)
    gearRatio: 2.645, wheel: 0.86, body: 'painted', width: 3.35, carLength: 25, bogies: 17.5, front: 'e231',
    // the end cars' nose: 26.5 m cars with the leading bogie 5.25 m behind the nose tip (the coupler ends as the middle car's)
    consist: [{ length: 26.5, bogies: 17.5, front: 5.25 }, { length: 25, bogies: 17.5, front: 3.75 }, { length: 26.5, bogies: 17.5, front: 3.75 }],
    // upper 常盤グリーン #489a83, lower 飛雲ホワイト #d6dad9, band はやてピンク #df3687
    // the H5 (JR Hokkaido): the same car with a 彩香パープル band; its swatch is the band, the paint being the same
    liveries: [
      { name: '東北新幹線', body: '#d6dad9', band: '#489a83', band2: '#df3687' },
      { name: '北海道新幹線', body: '#d6dad9', band: '#489a83', band2: '#7a5aa6', swatch: '#7a5aa6', variant: 'h5', series: 'H5系（北海道新幹線・JR北海道）' },
    ],
    // four round units in a row along the canopy's top edge (inner x ±0.08, outer ±0.24; Ø0.104 lenses), each head
    // and tail lamp in one; side windows 2.17–2.62 (measured on the Blender model, tools/blender/e5.py)
    lamps: { head: { x: 0.08, y: 2.84, w: 0.104, h: 0.104, round: true, n: 2, gap: 0.16 }, tail: { x: 0.08, y: 2.84, w: 0.06, h: 0.06, round: true, n: 2, gap: 0.16 }, windows: [2.17, 2.62], windowLum: 0.06 },
    // our estimate of the inverter (none published; vehicle/vvvf.ts)
    vvvf: E5_ESTIMATE,
    // welded rail on slab track, 2.5 m bogies, pressure-tight body; the long nose and covered pantograph cut the wind
    // noise (audio/running.ts)
    running: { rail: 'welded', axle: 2.5, sealed: true, wind: 0.8 },
    model: { title: '新幹線E5系', author: 'TOUGE NOCTURNE', url: '', license: '自作', own: true },
  },
};

export const TRAIN_ORDER: TrainId[] = ['e231', 'e235', 'keikyu1000', 'tobu30000', 'e5'];

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

const liveried = new Map<string, CarSpec>();

/**
 * The vehicle as fitted for a livery (a train's line: its series, control equipment and inverter sound); the same
 * object for the same livery, any other spec as it is.
 */
export function specForLivery(spec: CarSpec, color?: string): CarSpec {
  const t = spec.train;
  if (!t) return spec;
  const l = trainLivery(t, color);
  if (!l.series && !l.control && !l.vvvf) return spec;
  const key = `${spec.id}|${liverySwatch(l)}`;
  let s = liveried.get(key);
  if (!s) {
    const train = { ...t, series: l.series ?? t.series, control: l.control ?? t.control, vvvf: l.vvvf ?? t.vvvf };
    s = { ...spec, engineName: train.control, train };
    liveried.set(key, s);
  }
  return s;
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
