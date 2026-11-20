import type { CarSpec } from './carSpecs';

/**
 * Tanks (joke entries on every course). Owner (2026-11-10): 「戦車たちには特殊効果でマウス操作を付与…砲撃ができることで
 * 狙った対象に当たると対象は強制リスタート」, 「史実通り仕様を改変しないで」: the figures are the published ones, and
 * where a maker or army publishes none (marked `estimated`, shown as （推定） on the spec sheet), a stated estimate
 * from comparable vehicles. Nothing is tuned for play.
 *
 * Sources (written from memory, then checked against published sources on 2026-11-18: docs/TANK_FIGURES.md lists every
 * figure with its source and verdict; what is not published stays `estimated`, with the basis of the estimate):
 *   10式, 16式        陸上自衛隊 装備品紹介 / 防衛装備庁（旧 技術研究本部）の公表諸元: 全備重量, 寸法, 最高速度, 機関と
 *                     その定格 (1,200 PS / 2,300 rpm; 570 PS / 2,100 rpm), 乗員, 砲. Nothing on the gun's laying
 *                     rates and limits, the rounds' velocity or the loading time is published: estimates (see each).
 *   Leopard 2A5       Krauss-Maffei Wegmann's data sheet and the Bundeswehr's figures (59.5 t, ≤ 70 km/h, 31 km/h back,
 *                     −9° / +20°, 42 rounds, the turret round in 9 s), MTU (MB 873 Ka-501: 1,103 kW at 2,600 rpm,
 *                     4,700 N·m), Rheinmetall (Rh 120 L/44; DM53: 1,670 m/s from the L/44, 8.35 kg shot, 8.9 kg
 *                     charge). Top speed: 68 km/h is the German army's figure for the A5/A6; 72 km/h is quoted for
 *                     the lighter A4. Checked 11-18: the maker (KNDS) gives ≤ 70 km/h and 9.67 m over the gun: taken.
 *   M1A2 SEPv3        US Army (Weapon Systems Handbook) and General Dynamics Land Systems: 73.6 short tons (66.8 t),
 *                     1,500 shp AGT1500 (Honeywell: 3,950 lb·ft at the output shaft), governed to 42 mph (67.6 km/h),
 *                     42 rounds, crew of four, sight 3× / 10×. The M829A4's velocity is not published: the M829A3's
 *                     1,552.5 m/s is taken (Northrop Grumman's sheet, 8.15 kg of RPD-380). Elevation: −10° / +20°
 *                     (Hunnicutt; −9° in some references). Gun forward 9.77 m (the Army's fact file; 9.83 m elsewhere).
 *   T-14              Uralvagonzavod's and the Russian ministry of defence's statements as reported (TASS, 2015–):
 *                     55 t, 10.8 × 3.9 × 3.3 m (first given at Army-2019, Rossiyskaya Gazeta; 48–49 t were earlier
 *                     unofficial reports), 1,500 hp (ChTZ 12N360; its rpm is not published), 75–80 km/h (90 in some),
 *                     2A82-1M, 45 rounds of which 32 in the autoloader, 10–12 rounds a minute, crew of three in the
 *                     hull. Gearbox: a reversible robotised one with eight speeds each way is taken (a twelve-speed
 *                     automatic in other reports), backwards 40–50 km/h as reported. Little else is confirmed by the
 *                     maker: estimates.
 *
 * The simulation is the cars' VehicleSim with:
 * - tracks (`running: 'tracks'`): four contact points at a quarter of the track's ground length from its middle (a
 *   uniform track's turning resistance, μ·W·L/4), all driven; no steered wheels: the steering is a yaw moment from the
 *   two tracks' difference, at most what the tracks hold (μ·W·gauge/2), up to the pivot rate; the 16式 has wheels;
 * - a continuously variable transmission (`cvt`, the 10式's HMT): the engine held at its rated speed under full throttle;
 * - the gun (`gun`): turret and gun laid by the mouse at their real traverse/elevation rates, a simulated shell
 *   (game/weapons/).
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
  /**
   * What leaves the muzzle (kg: penetrator and sabot) and the propellant behind it (kg). Only the recoil reads them:
   * its momentum is shot × muzzle velocity + charge × `GAS_SPEED` (weapons/gun.ts).
   */
  shot: number;
  charge: number;
  /** speed the round loses per kilometre of flight near the muzzle (m/s): a long rod's drag */
  dropPerKm: number;
  /** which of the figures above are estimates (nothing published) */
  estimated?: ('muzzleVelocity' | 'reload' | 'ammo' | 'elevation' | 'traverse' | 'elevationRate' | 'zoom' | 'recoil' | 'drag')[];
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
  /**
   * Where the gun is on the vehicle (m; the shell starts from these, the stand-in is built to them and a model must
   * agree with them: render/TankModel.ts): hull length/width/height, the turret ring forward of the origin and its
   * height above the ground, the trunnions above the ring and forward of the traverse axis, the muzzle ahead of the
   * trunnions (`barrel`: the published length over the gun less the hull's half and the trunnions' place), the
   * turret's length/width/height, and the gunner's sight head in the turret's frame (default: on the roof, right of
   * the gun: `sightOf` in weapons/gun.ts).
   */
  dims: { hull: [number, number, number]; turretZ: number; ringY: number; barrel: number; trunnion: number; trunnionZ: number; turret: [number, number, number]; sight?: [number, number, number] };
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
    // 全備重量 約44 t
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
    // 最高速度 70 km/h, forwards and backwards alike (the HMT)
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
        // not published: the 1,650 m/s of the JM33 (the licence-built DM33 the gun also fires) is taken, a lower bound
        muzzleVelocity: 1650,
        // not published: the 90式's autoloader is quoted at about 4 s a round, the 10式's is said to be no slower (a
        // firing video's 3.5 s between rounds is not an official figure)
        reload: 4,
        loader: 'auto',
        // the bustle autoloader's reported capacity (軍事研究 2008; not official; the rounds in the hull cannot be
        // loaded on the move)
        ammo: 14,
        // not published: the 90式's −7° / +10° (the same low turret; the suspension's hull tilt, which adds to both
        // on the real one, is not simulated)
        elevation: [-7, 10],
        traverse: 40,
        elevationRate: 15,
        zoom: [4, 10],
        // (the JM33 / DM33: 7.3 kg in the bore, 7.6 kg of propellant)
        shot: 7.3,
        charge: 7.6,
        dropPerKm: 60,
        estimated: ['muzzleVelocity', 'reload', 'ammo', 'elevation', 'traverse', 'elevationRate', 'zoom', 'recoil', 'drag'],
      },
      pivotRate: 30,
      // HMT: full tractive effort (the tracks' grip) at a standstill, 70 km/h at the rated speed
      cvt: { low: 34, high: (2300 * Math.PI) / 30 / (70 / 3.6 / SPROCKET) },
      reverseSpeed: 70,
      sound: 'diesel',
      // 全長 9.42 m over the gun, 全幅 3.24 m. The gun's places are our model's (tools/blender/tanks/type10.py prints
      // them as CONTRACT), fitted to photographs through solved cameras (fitdata/type10): the traverse axis 2 cm behind
      // the middle of the track contact, the trunnions 1.97 m up and 1.40 m ahead, the muzzle at 5.71 m (the hull ends
      // at −3.71: 9.42 m over the gun); the gunner's sight head is the model's forward roof hood, 0.40 m above and
      // 0.82 m left of the bore (the fire control converges the gun on its line at the lased range)
      dims: { hull: [7.5, 3.24, 1.3], turretZ: -0.02, ringY: 1.55, barrel: 4.31, trunnion: 0.42, trunnionZ: 1.42, turret: [4.6, 3.0, 0.6], sight: [0.82, 0.815, 1.13] },
      // our model's track: metres per texture repeat along the band (type10.py prints TRACKV)
      trackV: 1.273,
      camo: ['#4a5236', '#6b5a3e'],
      figures: { engine: '水冷4サイクル V型8気筒ディーゼル', power: '1,200 PS / 2,300 rpm', weight: '44 t', topSpeed: 70, crew: 3, transmission: 'HMT（油圧機械式無段変速）' },
      estimated: ['砲弾初速', '装填時間', '即応弾数', '砲塔旋回・俯仰速度', '俯仰角', '照準具の倍率'],
    },
    colors: { body: '#4a5236', accent: '#6b5a3e' },
    model: { title: '10式戦車', author: 'TOUGE NOCTURNE', url: '', license: '自作', own: true },
  },
  {
    id: 'type16',
    name: '16式機動戦闘車',
    tagline: '105mm砲を積んだ8輪の装輪戦車',
    description: '戦車並みの105mmライフル砲を26トンの8輪車体に載せた機動戦闘車。舗装路なら100km/hで駆け、前2軸のステアリングで峠のコーナーも曲がっていく。',
    // 全備重量 約26 t
    mass: 26000,
    // first to last axle; wheel track
    contact: 4.6,
    gauge: 2.55,
    clearance: 0.5,
    boxHeight: 1.85,
    wheelRadius: 0.6,
    engine: {
      idleRpm: 700,
      // 570 PS (419 kW) at 2,100 rpm: 1,906 N·m there; the curve below it is estimated
      redline: 2100,
      torque: [[700, 1500], [1100, 2150], [1400, 2300], [1800, 2150], [2100, 1906], [2200, 1300]],
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
        // the figure commonly quoted for the 93式 from the 105 mm gun; not in the army's own sheets
        muzzleVelocity: 1500,
        // a loader by hand (crew of four): no figure published
        reload: 6,
        loader: 'manual',
        ammo: 40,
        elevation: [-6, 15],
        traverse: 40,
        elevationRate: 15,
        zoom: [4, 8],
        shot: 5.8,
        charge: 5.6,
        dropPerKm: 60,
        estimated: ['muzzleVelocity', 'reload', 'ammo', 'elevation', 'traverse', 'elevationRate', 'zoom', 'recoil', 'drag'],
      },
      pivotRate: 0,
      reverseSpeed: 20,
      sound: 'diesel',
      // 全長 8.45 m over the gun, 全幅 2.98 m; the turret sits on the rear half (the engine is in the front left, the
      // driver front right). Ring, trunnions, muzzle and the gunner's sight head (right of the gun, low and forward)
      // are the model's (type16.glb, fitted to photos: ring 0.56 m behind the axles' middle at 1.80 m, muzzle 4.64 m
      // ahead of it); the hull stays the sim's.
      dims: { hull: [8.0, 2.98, 1.5], turretZ: -0.56, ringY: 1.8, barrel: 4.15, trunnion: 0.45, trunnionZ: 1.05, turret: [3.75, 2.64, 0.65], sight: [-0.64, 0.68, 0.94] },
      camo: ['#4a5236', '#6b5a3e'],
      figures: { engine: '水冷4サイクル 直列4気筒ターボディーゼル', power: '570 PS / 2,100 rpm', weight: '26 t', topSpeed: 100, crew: 4, transmission: '自動変速（8×8・前2軸操舵）' },
      estimated: ['変速段数', '後進速度', '砲弾初速', '装填時間', '搭載弾数', '砲塔旋回・俯仰速度', '俯仰角', '照準具の倍率'],
    },
    colors: { body: '#4a5236', accent: '#6b5a3e' },
    model: { title: '16式機動戦闘車', author: 'TOUGE NOCTURNE', url: '', license: '自作', own: true },
  },
  {
    id: 'leopard2a5',
    name: 'Leopard 2A5',
    tagline: '楔形装甲のドイツ主力戦車',
    description: '砲塔前面の楔形増加装甲が目印の2A5。60トン近い車体を1500馬力のV12ツインターボが70km/hまで運び、44口径120mm砲は数km先の目標も捉える。',
    // combat weight 59.5 t (the Bundeswehr's figure; 59.7 t is quoted too, and the maker's 62 t is for export builds)
    mass: 59500,
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
    // Renk HSWL 354: four forward, two reverse (31 km/h); the ratios are not published: spaced to the maker's ≤ 70 km/h
    gearSpeeds: [16.5, 29, 45, 70],
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
        // a loader by hand: no official figure (about 6 s is the usual one)
        reload: 6,
        loader: 'manual',
        ammo: 42,
        elevation: [-9, 20],
        // the turret round in 9 s
        traverse: 40,
        elevationRate: 15,
        // EMES 15: 12× (published); the low 4× (the thermal channel's) is not confirmed: estimated
        zoom: [4, 12],
        shot: 8.35,
        charge: 8.9,
        dropPerKm: 55,
        estimated: ['reload', 'elevationRate', 'zoom', 'drag'],
      },
      pivotRate: 30,
      reverseSpeed: 31,
      sound: 'diesel',
      // From our model (2026-11-19; fitted to four Commons photographs through solved cameras, the origin the middle of
      // the road wheels): the muzzle 5.69 m ahead of the middle, the hull rear at z −4.13 (the photos: −4.12…−4.20),
      // 9.82 m over the gun (published: 9.67 by the maker, 9.97 elsewhere); ring z 0.40 / y 1.70, trunnions 0.42 above and 1.08
      // ahead (2.12 m up), barrel 4.21. The sight head is the model's EMES 15 window on the roof's right front, 0.40 m
      // above and 0.86 m right of the bore (the fire control converges the bore on its line at the lased range).
      dims: { hull: [7.72, 3.76, 1.4], turretZ: 0.4, ringY: 1.7, barrel: 4.21, trunnion: 0.42, trunnionZ: 1.08, turret: [5.0, 3.6, 0.85], sight: [-0.86, 0.816, 1.035] },
      trackV: 1.48,
      camo: ['#3f4a33', '#5a4632'],
      figures: { engine: 'MTU MB 873 Ka-501 V型12気筒ツインターボディーゼル 47.6L', power: '1,500 PS / 2,600 rpm', weight: '59.5 t', topSpeed: 70, crew: 4, transmission: 'Renk HSWL 354（前進4段・後進2段）' },
      estimated: ['変速比', '装填時間', '俯仰速度', '照準具の低倍率', '超信地旋回の速さ'],
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
      // Honeywell AGT1500: 1,500 shp at 3,000 rpm (output; Honeywell's 2,750 lb·ft there would be 5 % more: the
      // power is kept); the torque below that is not published: 5,355 N·m at 1,000 rpm estimated (a turbine's
      // torque rises as the output slows)
      redline: 3000,
      torque: [[600, 5355], [1000, 5355], [1500, 5000], [2000, 4500], [2500, 4000], [3000, 3560], [3100, 2000]],
      cylinders: 0,
      turbo: false,
    },
    // Allison X1100-3B: four forward, two reverse; governed to 42 mph (67.6 km/h)
    gearSpeeds: [14, 27, 43, 67.6],
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
        // not published for the A4: the M829A3's (Northrop Grumman: 1,552.5 m/s)
        muzzleVelocity: 1552.5,
        // a loader by hand (the crew's qualification asks for 7 s; practised loaders are quicker)
        reload: 6,
        loader: 'manual',
        ammo: 42,
        elevation: [-10, 20],
        // the turret round in 9 s
        traverse: 40,
        elevationRate: 15,
        // the gunner's primary sight by day: 3× / 10×
        zoom: [3, 10],
        // (the M829A3: a 10.0 kg projectile, 8.15 kg of RPD-380: Northrop Grumman's sheet)
        shot: 10,
        charge: 8.15,
        dropPerKm: 50,
        estimated: ['muzzleVelocity', 'reload', 'elevationRate', 'recoil', 'drag'],
      },
      pivotRate: 30,
      // not in the army's sheets: 25 mph is the usual figure
      reverseSpeed: 40,
      sound: 'turbine',
      // 9.77 m over the gun (the Army's fact file; 9.83 m elsewhere), hull 7.93 m, 3.66 m wide: the muzzle
      // 9.77 − 7.93 / 2 = 5.81 m ahead of the middle; the bore axis 1.97 m above the ground (not published: measured on
      // five photographs through their solved cameras, docs/TANK_FIGURES.md), so the trunnions 0.12 m above the ring;
      // the gunner's sight head is the window of the model's primary sight (GPS) on the roof right of the gun, 0.46 m
      // above and 0.73 m right of the bore (triangulated on two photos; the fire control converges the gun on its line)
      dims: { hull: [7.93, 3.66, 1.3], turretZ: 0.3, ringY: 1.85, barrel: 3.72, trunnion: 0.12, trunnionZ: 1.79, turret: [5.6, 3.7, 0.8], sight: [-0.73, 0.58, 0.73] },
      // our model's track: metres per texture repeat along the band (m1a2.py prints TRACKV)
      trackV: 1.536,
      camo: ['#b9a47a', '#a8936a'],
      figures: { engine: 'Honeywell AGT1500 ガスタービン', power: '1,500 shp', weight: '66.8 t', topSpeed: 67, crew: 4, transmission: 'Allison X1100-3B（前進4段・後進2段）' },
      estimated: ['変速比', '後進速度', '砲弾初速（M829A3の値）', '装填時間', '俯仰速度', '超信地旋回の速さ'],
    },
    colors: { body: '#b9a47a', accent: '#a8936a' },
    model: { title: 'M1A2 SEPv3 エイブラムス', author: 'TOUGE NOCTURNE', url: '', license: '自作', own: true },
  },
  {
    id: 't14',
    name: 'T-14 アルマータ',
    tagline: '無人砲塔のロシア新世代戦車',
    description: '乗員3名は装甲カプセルに収まり、砲塔は無人。X型12気筒1500馬力と前後8段ずつのロボット変速機で、後ろ向きにも速く走れる。125mm砲は自動装填。',
    // 55 t (first given at Army-2019; 48–49 t were earlier unofficial figures)
    mass: 55000,
    contact: 5.3,
    gauge: 2.85,
    clearance: 0.5,
    boxHeight: 2.1,
    engine: {
      idleRpm: 800,
      // ChTZ 12N360 (A-85-3A): 1,500 hp (1,103 kW); its rated speed is not published (2,000 rpm estimated): 5,270 N·m
      // there; the curve below it is estimated
      redline: 2000,
      torque: [[800, 3800], [1100, 5200], [1400, 5800], [1700, 5600], [2000, 5270], [2100, 3500]],
      cylinders: 12,
      turbo: true,
    },
    // a robotised gearbox, eight forward and eight reverse; 80 km/h (the reports run from 75 to 90)
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
        // nothing published by the maker (claims run to 2,000 m/s): a figure of the 125 mm long rods before it
        muzzleVelocity: 1750,
        // 10–12 rounds a minute as reported
        reload: 5.5,
        loader: 'auto',
        // 45 rounds carried, 32 of them in the autoloader (as reported): the crew in the hull capsule cannot reach the
        // others, so the autoloader's count is taken (as the 10式's)
        ammo: 32,
        // not published: −7° / +15° as given in reference tables (no source named)
        elevation: [-7, 15],
        traverse: 40,
        elevationRate: 15,
        zoom: [4, 12],
        shot: 8.5,
        charge: 10,
        dropPerKm: 60,
        estimated: ['muzzleVelocity', 'reload', 'elevation', 'traverse', 'elevationRate', 'zoom', 'recoil', 'drag'],
      },
      pivotRate: 30,
      // the reversible gearbox (eight speeds each way): 40–50 km/h backwards as reported (Pervyy Tekhnicheskiy): 45
      reverseSpeed: 45,
      sound: 'diesel',
      // 10.8 m over the gun, hull 8.7 m, 3.9 m wide (Army-2019). The gun's places are measured on parade photos through
      // solved cameras (the own model, docs/TANK_FIGURES.md): the bore 2.15 m above the ground (0.10 above the ring),
      // the muzzle at 0° 6.37 m ahead of the origin (midway between the first and last road wheels, 0.2 m aft of the
      // hull's middle); the turret 4.25 m from the cheeks to the bustle's rear, 2.72 m over the cheeks, its roof 0.68 m
      // above the ring. The sight head is the model's gunner's sight (the box on the roof's right front): its window
      // 0.66 m right of the axis, 2.815 m above the ground, 0.63 m ahead of the ring's centre, so 0.67 m above and 0.66 m
      // beside the bore; the fire control converges the bore on the line of sight at the lased range (GunControl.laid)
      dims: { hull: [8.7, 3.9, 1.5], turretZ: 0.0, ringY: 2.05, barrel: 4.96, trunnion: 0.1, trunnionZ: 1.41, turret: [4.25, 2.72, 0.68], sight: [-0.66, 0.765, 0.63] },
      // the model's track texture: 8 links of 0.17 m per V unit
      trackV: 1.36,
      camo: ['#4c5638', '#2f3326'],
      figures: { engine: 'ChTZ 12N360 X型12気筒ディーゼル', power: '1,500 hp', weight: '55 t', topSpeed: 80, crew: 3, transmission: 'ロボット式（前進8段・後進8段）' },
      estimated: ['最高速度（公表は75〜80 km/h）', '変速段数（12段の報道も）', '後進速度（報道は40〜50 km/h）', '機関回転数', '砲弾初速', '装填時間', '俯仰角', '砲塔旋回・俯仰速度', '照準具の倍率'],
    },
    colors: { body: '#4c5638', accent: '#2f3326' },
    model: { title: 'T-14 アルマータ', author: 'TOUGE NOCTURNE', url: '', license: '自作', own: true },
  },
];

export const TANK_ORDER: TankId[] = TANKS.map((t) => t.id);
export const TANK_SPECS = Object.fromEntries(TANKS.map((t) => [t.id, tankSpec(t)])) as Record<TankId, CarSpec>;
