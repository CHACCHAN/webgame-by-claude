import type { CarSpec } from './carSpecs';

/**
 * Tanks (joke entries on every course). Owner (2026-11-10): 「戦車たちには特殊効果でマウス操作を付与…砲撃ができることで
 * 狙った対象に当たると対象は強制リスタート」, 「史実通り仕様を改変しないで」: the figures are the published ones, and
 * where a maker or army publishes none (marked `estimated`), a stated estimate from comparable vehicles.
 *
 * The simulation is the cars' VehicleSim with:
 * - tracks (`running: 'tracks'`): four contact points at a quarter of the track's ground length from its middle (a
 *   uniform track's turning resistance, μ·W·L/4), all driven; no steered wheels: the steering is a yaw moment from the
 *   two tracks' difference, at most what the tracks hold (μ·W·gauge/2), up to the pivot rate; the 16式 has wheels;
 * - a continuously variable transmission (`cvt`, the 10式's HMT): the engine held at its rated speed under full throttle;
 * - the gun (`gun`): turret and gun laid by the mouse at their real traverse/elevation rates (game/weapons/).
 */
export type TankId = 'type10' | 'type16' | 'leopard2a5' | 'm1a2' | 't14';

export interface GunInfo {
  /** the gun as shown on the spec sheet */
  name: string;
  /** mm */
  calibre: number;
  /** the round fired and its muzzle velocity (m/s) */
  round: string;
  muzzleVelocity: number;
  /** seconds between rounds */
  reload: number;
  loader: 'auto' | 'manual';
  /** rounds carried */
  ammo: number;
  /** gun depression (−) and elevation (+) limits (degrees) */
  elevation: [number, number];
  /** turret traverse and gun elevation rates (degrees per second) */
  traverse: number;
  elevationRate: number;
  /** gunner's sight magnifications (low, high) */
  zoom: [number, number];
  /** which of the figures above are estimates (nothing published) */
  estimated?: ('muzzleVelocity' | 'reload' | 'ammo' | 'elevation' | 'traverse' | 'zoom')[];
}

export interface TankInfo {
  maker: string;
  /** country and in-service year for the spec sheet */
  origin: string;
  running: 'tracks' | 'wheels';
  gun: GunInfo;
  /** neutral (pivot) turn rate, degrees per second (tracks) */
  pivotRate: number;
  /** a hydro-mechanical CVT: overall ratios at the lowest and highest (the sim holds the engine at its rated speed) */
  cvt?: { low: number; high: number };
  /** published reverse top speed (km/h) */
  reverseSpeed: number;
  /** the engine's sound: a diesel (cylinders from the spec) or the M1's gas turbine */
  sound: 'diesel' | 'turbine';
  /** dimensions of the procedural stand-in and the effects: hull length/width/height (m), turret ring forward of the
   * origin (m), turret ring height, gun barrel length (m), trunnion height above the ring */
  dims: { hull: [number, number, number]; turretZ: number; ringY: number; barrel: number; trunnion: number; turret: [number, number, number] };
  /** metres of track one V unit of the model's track texture covers (default 1) */
  trackV?: number;
  /** the model's gun elevates with a negative rotation about X (1, default) or a positive one (−1) */
  gunSign?: 1 | -1;
  /** camouflage colours (base, second) for the procedural stand-in */
  camo: [string, string];
  /** published figures for the spec sheet */
  figures: { engine: string; power: string; weight: string; topSpeed: number; crew: number; transmission: string };
  /** which spec-sheet figures are estimates */
  estimated?: string[];
}

/** overall ratios (gearbox × final drive) reaching `kmh` at `rpm` in each gear on a sprocket of radius `r` */
function gearsFor(kmh: number[], rpm: number, r: number) {
  return kmh.map((v) => Math.round(((rpm * Math.PI) / 30 / (v / 3.6 / r)) * 1000) / 1000);
}

/** virtual sprocket radius of the tracked sims (m): the ratios above are computed for it */
const SPROCKET = 0.33;
/** air drag: ½ρ·Cd·A for a tank (Cd ≈ 1, ~9 m² frontal) */
const TANK_DRAG = 5.4;

interface TankDef {
  id: TankId;
  name: string;
  tagline: string;
  description: string;
  mass: number;
  /** track ground contact length (wheels: first to last axle) and gauge (track centre to centre / wheel track) */
  contact: number;
  gauge: number;
  /** belly clearance and height of the collision box above it (m) */
  clearance: number;
  boxHeight: number;
  engine: CarSpec['engine'];
  /** speed at the governed rpm in each forward gear (km/h); a CVT: its top speed only */
  gearSpeeds: number[];
  wheelRadius?: number;
  grip: number;
  rolling: number;
  maxSteerDeg?: number;
  stats: CarSpec['stats'];
  tank: TankInfo;
  colors: CarSpec['colors'];
  model: NonNullable<CarSpec['model']>;
}

function tankSpec(d: TankDef): CarSpec {
  const r = d.wheelRadius ?? SPROCKET;
  const rated = d.engine.redline;
  const gears = d.tank.cvt ? [d.tank.cvt.high] : gearsFor(d.gearSpeeds, rated, r);
  const tracks = d.tank.running === 'tracks';
  return {
    id: d.id,
    name: d.name,
    tagline: d.tagline,
    description: d.description,
    drive: 'AWD',
    engineName: d.tank.figures.engine,
    frontTorqueSplit: 0.5,
    mass: d.mass,
    size: { width: d.tank.dims.hull[1], height: d.boxHeight, length: d.tank.dims.hull[0] },
    // tracks: the four contact points at ±L/4 (see the header)
    wheelbase: tracks ? d.contact / 2 : d.contact,
    track: d.gauge,
    comForward: 0,
    comHeight: d.clearance + d.boxHeight * 0.42,
    wheelRadius: r,
    // torsion bars / hydropneumatics: ~1.3 Hz, well damped
    suspension: { rest: 0.42, stiffness: Math.round((d.mass * (2 * Math.PI * 1.3) ** 2) / 4), damping: Math.round(2 * 0.45 * Math.sqrt(((d.mass * (2 * Math.PI * 1.3) ** 2) / 4) * (d.mass / 4))), antiRoll: Math.round(d.mass * 18) },
    engine: d.engine,
    gears,
    finalDrive: 1,
    gripFront: d.grip,
    gripRear: d.grip,
    maxSteerDeg: d.maxSteerDeg ?? 0,
    // the brakes stop a tank at ~0.7 g (the tracks' grip on a dry road is the limit)
    brakeForce: Math.round(d.mass * 9.81 * 0.75),
    dragCoef: TANK_DRAG,
    downforce: 0,
    damping: 0.004,
    rolling: d.rolling,
    driftiness: 0,
    stats: d.stats,
    colors: d.colors,
    model: d.model,
    clearance: d.clearance,
    reverseRatio: (rated * Math.PI) / 30 / (d.tank.reverseSpeed / 3.6 / r),
    tank: d.tank,
  };
}

const TANKS: TankDef[] = [
  {
    id: 'type10',
    name: '10式戦車',
    tagline: '陸上自衛隊の第4世代主力戦車',
    description: '44トンの軽量な車体に1200馬力。無段変速のHMTで前進も後進も70km/h、スラローム射撃までこなす。自動装填の120mm滑腔砲が峠のライバルを狙う。',
    mass: 44000,
    contact: 4.3,
    gauge: 2.7,
    clearance: 0.45,
    boxHeight: 1.85,
    engine: {
      idleRpm: 700,
      // 1,200 PS (883 kW) at 2,300 rpm, the rated and governed speed
      redline: 2300,
      // rated torque 3,666 N·m (883 kW at 2,300 rpm); the peak below it is estimated (~15 % over, as diesels of its kind)
      torque: [[700, 2900], [1200, 3800], [1700, 4200], [2000, 4000], [2300, 3666], [2400, 2400]],
      cylinders: 8,
      turbo: true,
    },
    gearSpeeds: [70],
    grip: 0.8,
    rolling: 0.035,
    stats: { power: 6, grip: 7, drift: 0, weight: 2 },
    tank: {
      maker: '三菱重工業',
      origin: '日本（2012年配備）',
      running: 'tracks',
      gun: {
        name: '44口径120mm滑腔砲（日本製鋼所）',
        calibre: 120,
        round: '10式120mm装弾筒付翼安定徹甲弾',
        muzzleVelocity: 1650,
        reload: 4,
        loader: 'auto',
        ammo: 14,
        elevation: [-10, 20],
        traverse: 40,
        elevationRate: 15,
        zoom: [4, 10],
        estimated: ['muzzleVelocity', 'reload', 'ammo', 'elevation', 'traverse', 'zoom'],
      },
      pivotRate: 30,
      // HMT: full tractive effort (the tracks' grip) at a standstill, 70 km/h at the rated speed
      cvt: { low: 34, high: (2300 * Math.PI) / 30 / (70 / 3.6 / SPROCKET) },
      reverseSpeed: 70,
      sound: 'diesel',
      dims: { hull: [7.5, 3.24, 1.3], turretZ: 0.2, ringY: 1.75, barrel: 5.3, trunnion: 0.35, turret: [4.6, 3.0, 0.6] },
      camo: ['#4a5236', '#6b5a3e'],
      figures: { engine: '水冷4サイクル V型8気筒ディーゼル', power: '1,200 PS / 2,300 rpm', weight: '44 t', topSpeed: 70, crew: 3, transmission: 'HMT（油圧機械式無段変速）' },
      estimated: ['砲弾初速', '装填時間', '搭載弾数', '砲塔旋回速度', '俯仰角'],
    },
    colors: { body: '#4a5236', accent: '#6b5a3e' },
    model: { title: '10式戦車', author: 'TOUGE NOCTURNE', url: '', license: '自作', own: true },
  },
  {
    id: 'type16',
    name: '16式機動戦闘車',
    tagline: '105mm砲を積んだ8輪の装輪戦車',
    description: '戦車並みの105mmライフル砲を26トンの8輪車体に載せた機動戦闘車。舗装路なら100km/hで駆け、前2軸のステアリングで峠のコーナーも曲がっていく。',
    mass: 26000,
    // first to last axle; wheel track
    contact: 4.6,
    gauge: 2.55,
    clearance: 0.5,
    boxHeight: 1.85,
    wheelRadius: 0.6,
    engine: {
      idleRpm: 700,
      // 570 hp (425 kW); its rated speed is not published: 2,100 rpm estimated
      redline: 2100,
      torque: [[700, 1500], [1100, 2150], [1400, 2300], [1800, 2150], [2100, 1930], [2200, 1300]],
      cylinders: 4,
      turbo: true,
    },
    // an automatic gearbox (its ratios are not published: six speeds estimated) to 100 km/h
    gearSpeeds: [16, 27, 41, 58, 78, 100],
    grip: 0.95,
    rolling: 0.015,
    maxSteerDeg: 26,
    stats: { power: 4, grip: 6, drift: 0, weight: 4 },
    tank: {
      maker: '三菱重工業',
      origin: '日本（2016年配備）',
      running: 'wheels',
      gun: {
        name: '52口径105mmライフル砲（日本製鋼所）',
        calibre: 105,
        round: '93式105mm装弾筒付翼安定徹甲弾',
        muzzleVelocity: 1500,
        reload: 6,
        loader: 'manual',
        ammo: 40,
        elevation: [-6, 15],
        traverse: 40,
        elevationRate: 15,
        zoom: [4, 8],
        estimated: ['muzzleVelocity', 'reload', 'ammo', 'elevation', 'traverse', 'zoom'],
      },
      pivotRate: 0,
      reverseSpeed: 20,
      sound: 'diesel',
      dims: { hull: [8.0, 2.98, 1.5], turretZ: 0.1, ringY: 2.0, barrel: 5.5, trunnion: 0.3, turret: [3.6, 2.6, 0.6] },
      camo: ['#4a5236', '#6b5a3e'],
      figures: { engine: '水冷4サイクル 直列4気筒ターボディーゼル 11.3L', power: '570 hp', weight: '26 t', topSpeed: 100, crew: 4, transmission: '自動変速（8×8・前2軸操舵）' },
      estimated: ['定格回転数', '変速段数', '後進速度', '砲弾初速', '装填時間', '搭載弾数', '砲塔旋回速度', '俯仰角'],
    },
    colors: { body: '#4a5236', accent: '#6b5a3e' },
    model: { title: '16式機動戦闘車', author: 'TOUGE NOCTURNE', url: '', license: '自作', own: true },
  },
  {
    id: 'leopard2a5',
    name: 'Leopard 2A5',
    tagline: '楔形装甲のドイツ主力戦車',
    description: '砲塔前面の楔形増加装甲が目印の2A5。60トン近い車体を1500馬力のV12ツインターボが72km/hまで運び、44口径120mm砲は5km先の目標も捉える。',
    mass: 59700,
    contact: 4.95,
    gauge: 3.1,
    clearance: 0.54,
    boxHeight: 2.0,
    engine: {
      idleRpm: 750,
      // MTU MB 873 Ka-501: 1,500 PS (1,103 kW) at 2,600 rpm, 4,700 N·m at 1,600–1,700 rpm
      redline: 2600,
      torque: [[750, 3100], [1000, 3900], [1300, 4400], [1650, 4700], [2000, 4550], [2300, 4300], [2600, 4050], [2700, 2800]],
      cylinders: 12,
      turbo: true,
    },
    // Renk HSWL 354: four forward, two reverse (31 km/h); the ratios are not published: spaced to 72 km/h
    gearSpeeds: [17, 30, 46, 72],
    grip: 0.8,
    rolling: 0.035,
    stats: { power: 7, grip: 7, drift: 0, weight: 1 },
    tank: {
      maker: 'Krauss-Maffei Wegmann',
      origin: 'ドイツ（1995年配備）',
      running: 'tracks',
      gun: {
        name: 'Rh-120 L/44 120mm滑腔砲',
        calibre: 120,
        round: 'DM53 APFSDS',
        muzzleVelocity: 1670,
        reload: 6,
        loader: 'manual',
        ammo: 42,
        elevation: [-9, 20],
        traverse: 40,
        elevationRate: 15,
        zoom: [4, 12],
        estimated: ['reload'],
      },
      pivotRate: 30,
      reverseSpeed: 31,
      sound: 'diesel',
      dims: { hull: [7.72, 3.75, 1.4], turretZ: 0.4, ringY: 1.95, barrel: 5.3, trunnion: 0.4, turret: [5.0, 3.6, 0.85] },
      camo: ['#3f4a33', '#5a4632'],
      figures: { engine: 'MTU MB 873 Ka-501 V型12気筒ツインターボディーゼル 47.6L', power: '1,500 PS / 2,600 rpm', weight: '59.7 t', topSpeed: 72, crew: 4, transmission: 'Renk HSWL 354（前進4段・後進2段）' },
      estimated: ['変速比', '装填時間', '旋回性能'],
    },
    colors: { body: '#3f4a33', accent: '#5a4632' },
    model: { title: 'Leopard 2A5', author: 'TOUGE NOCTURNE', url: '', license: '自作', own: true },
  },
  {
    id: 'm1a2',
    name: 'M1A2 SEPv3',
    tagline: 'ガスタービンの米軍主力戦車',
    description: '1500馬力のガスタービンが甲高く唸るエイブラムスの最新型。67トンの巨体ながら出足は鋭く、劣化ウラン装甲の砲塔から120mm砲を放つ。',
    mass: 66800,
    contact: 4.6,
    gauge: 2.9,
    clearance: 0.48,
    boxHeight: 1.95,
    engine: {
      // the turbine's output shaft
      idleRpm: 600,
      // Honeywell AGT1500: 1,500 shp at 3,000 rpm (output), 5,355 N·m (3,950 lb·ft) at 1,000 rpm: a turbine's torque
      // rises as the output slows
      redline: 3000,
      torque: [[600, 5355], [1000, 5355], [1500, 5000], [2000, 4500], [2500, 4000], [3000, 3560], [3100, 2000]],
      cylinders: 0,
      turbo: false,
    },
    // Allison X1100-3B: four forward, two reverse (40 km/h); governed to 67 km/h (42 mph)
    gearSpeeds: [14, 27, 43, 67],
    grip: 0.8,
    rolling: 0.035,
    stats: { power: 7, grip: 7, drift: 0, weight: 1 },
    tank: {
      maker: 'General Dynamics Land Systems',
      origin: 'アメリカ（2020年配備）',
      running: 'tracks',
      gun: {
        name: 'M256 44口径120mm滑腔砲',
        calibre: 120,
        round: 'M829A4 APFSDS-T',
        muzzleVelocity: 1555,
        reload: 6,
        loader: 'manual',
        ammo: 42,
        elevation: [-9, 20],
        traverse: 40,
        elevationRate: 15,
        zoom: [3, 10],
        estimated: ['muzzleVelocity', 'reload'],
      },
      pivotRate: 30,
      reverseSpeed: 40,
      sound: 'turbine',
      dims: { hull: [7.93, 3.66, 1.3], turretZ: 0.3, ringY: 1.85, barrel: 5.3, trunnion: 0.35, turret: [5.6, 3.7, 0.8] },
      camo: ['#b9a47a', '#a8936a'],
      figures: { engine: 'Honeywell AGT1500 ガスタービン', power: '1,500 shp', weight: '66.8 t', topSpeed: 67, crew: 4, transmission: 'Allison X1100-3B（前進4段・後進2段）' },
      estimated: ['変速比', '装填時間', '旋回性能'],
    },
    colors: { body: '#b9a47a', accent: '#a8936a' },
    model: { title: 'M1A2 SEPv3 エイブラムス', author: 'TOUGE NOCTURNE', url: '', license: '自作', own: true },
  },
  {
    id: 't14',
    name: 'T-14 アルマータ',
    tagline: '無人砲塔のロシア新世代戦車',
    description: '乗員3名は装甲カプセルに収まり、砲塔は無人。X型12気筒1500馬力と前後8段ずつのロボット変速機で、後ろ向きにも前進と同じギアで走れる。125mm砲は自動装填。',
    mass: 48000,
    contact: 5.3,
    gauge: 2.85,
    clearance: 0.5,
    boxHeight: 2.1,
    engine: {
      idleRpm: 800,
      // ChTZ 12N360 (A-85-3A): 1,500 hp (1,103 kW) nominal; its rated speed is not published: 2,000 rpm estimated
      redline: 2000,
      torque: [[800, 3800], [1100, 5200], [1400, 5800], [1700, 5600], [2000, 5270], [2100, 3500]],
      cylinders: 12,
      turbo: true,
    },
    // a robotised gearbox, eight forward and eight reverse; 80 km/h (the published estimates run 80–90)
    gearSpeeds: [9, 14, 20, 28, 38, 49, 63, 80],
    grip: 0.8,
    rolling: 0.035,
    stats: { power: 8, grip: 7, drift: 0, weight: 2 },
    tank: {
      maker: 'ウラルヴァゴンザヴォード',
      origin: 'ロシア（2015年公開）',
      running: 'tracks',
      gun: {
        name: '2A82-1M 125mm滑腔砲',
        calibre: 125,
        round: '3BM69 APFSDS',
        muzzleVelocity: 1750,
        reload: 5.5,
        loader: 'auto',
        ammo: 45,
        elevation: [-5, 20],
        traverse: 40,
        elevationRate: 15,
        zoom: [4, 12],
        estimated: ['muzzleVelocity', 'reload', 'elevation', 'traverse', 'zoom'],
      },
      pivotRate: 30,
      // the reversible gearbox: the same eight ratios backwards
      reverseSpeed: 80,
      sound: 'diesel',
      dims: { hull: [8.7, 3.5, 1.5], turretZ: 0.0, ringY: 2.05, barrel: 6.0, trunnion: 0.3, turret: [4.4, 3.3, 0.75] },
      camo: ['#4c5638', '#2f3326'],
      figures: { engine: 'ChTZ 12N360 X型12気筒ディーゼル', power: '1,500 hp', weight: '48 t', topSpeed: 80, crew: 3, transmission: 'ロボット式（前進8段・後進8段）' },
      estimated: ['重量（48〜55 t の諸説）', '最高速度（80〜90 km/h の諸説）', '定格回転数', '後進速度', '砲弾初速', '装填時間', '俯仰角', '旋回性能'],
    },
    colors: { body: '#4c5638', accent: '#2f3326' },
    model: { title: 'T-14 アルマータ', author: 'TOUGE NOCTURNE', url: '', license: '自作', own: true },
  },
];

export const TANK_ORDER: TankId[] = TANKS.map((t) => t.id);
export const TANK_SPECS = Object.fromEntries(TANKS.map((t) => [t.id, tankSpec(t)])) as Record<TankId, CarSpec>;
