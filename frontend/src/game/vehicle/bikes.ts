import type { CarSpec } from './carSpecs';

/**
 * Motorcycles. The simulation is the cars' (VehicleSim) on a narrow virtual track with a low centre of mass, so it
 * never tips; what makes it a bike:
 * - the drive is capped at the wheelie limit and the brakes at the stoppie limit, from the real centre of mass with
 *   the rider (`BikeInfo.com`), and the front lifts a little at the limit;
 * - no drift tricks (handbrake, feint, throttle stab): a bike grips, and the handbrake is the rear brake;
 * - the model leans into corners by the lateral acceleration (render/BikeModel.ts) and so does the rider's view.
 * Figures from the makers' published specifications; the riding mass adds a 70 kg rider.
 */
export type BikeId = 'nsr250r' | 'ninjah2' | 'hayabusa';

export interface BikeInfo {
  maker: string;
  /** model code and year shown in the spec sheet */
  type: string;
  /** centre of mass with the rider (m): height, and distance ahead of the rear axle */
  com: { height: number; fromRear: number };
  /** the most the model leans (rad) */
  maxLean: number;
  /** colours of the fairing (the model's `paint`), first = default */
  liveries: { name: string; swatch: string }[];
  /** published figures for the spec sheet */
  figures: { engine: string; displacement: number; power: string; torque: string; weight: string; topSpeed: number; seat: number };
}

/** the rider (kg) */
const RIDER = 70;

/**
 * Overall ratios (gearbox × primary × final) that reach `kmh` at `redline` in each gear: bikes list their gearing as
 * three ratios; the sim only needs the product.
 */
function gearsFor(kmh: number[], redline: number, r: number) {
  return kmh.map((v) => Math.round(((redline * Math.PI) / 30 / (v / 3.6 / r)) * 1000) / 1000);
}

interface BikeDef {
  id: BikeId;
  name: string;
  tagline: string;
  description: string;
  /** bike (kg, ready to ride) */
  mass: number;
  wheelbase: number;
  wheelRadius: number;
  engine: CarSpec['engine'];
  /** speed at the redline in each gear (km/h) */
  gearSpeeds: number[];
  grip: number;
  /** 0.5 ρ Cd A of bike and tucked rider (N per (m/s)²) */
  drag: number;
  stats: CarSpec['stats'];
  bike: BikeInfo;
  model: NonNullable<CarSpec['model']>;
}

function bikeSpec(d: BikeDef): CarSpec {
  const mass = d.mass + RIDER;
  const { height, fromRear } = d.bike.com;
  // the brakes stop short of lifting the rear wheel
  const stoppie = (d.wheelbase - fromRear) / height;
  return {
    id: d.id,
    name: d.name,
    tagline: d.tagline,
    description: d.description,
    drive: 'RWD',
    engineName: d.bike.figures.engine,
    frontTorqueSplit: 0,
    mass,
    // the box the collisions see: bars and rider's knees, rider's shoulders, wheel to wheel
    size: { width: 0.72, height: 0.9, length: d.wheelbase + 0.62 },
    wheelbase: d.wheelbase,
    // a virtual track: the body stays upright (the visual leans), on a low centre of mass so it never tips (0.56 m
    // and 0.18 m tipped over at ~1.5 g: the big bikes rolled over on the AI's wall hits)
    track: 0.7,
    comForward: fromRear - d.wheelbase / 2,
    comHeight: 0.1,
    wheelRadius: d.wheelRadius,
    suspension: { rest: 0.26, stiffness: Math.round((mass * 9.81) / 4 / 0.055), damping: Math.round(Math.sqrt(mass * 2000) * 0.9), antiRoll: 12000 },
    engine: d.engine,
    gears: gearsFor(d.gearSpeeds, d.engine.redline, d.wheelRadius),
    finalDrive: 1,
    gripFront: d.grip,
    gripRear: d.grip,
    maxSteerDeg: 30,
    brakeForce: Math.round(mass * 9.81 * stoppie * 0.97),
    dragCoef: d.drag,
    downforce: 0,
    // the cars' body damping would cost a bike 2 m/s² at 300 km/h: the drag above stands for it
    damping: 0.004,
    driftiness: 0.1,
    stats: d.stats,
    colors: { body: d.bike.liveries[0].swatch, accent: '#16181c' },
    model: d.model,
    bike: d.bike,
  };
}

const BIKES: BikeDef[] = [
  {
    id: 'nsr250r',
    name: 'NSR250R',
    tagline: '2ストローク・レーサーレプリカ',
    description: '90年代の峠を沸かせたホンダの2スト250cc。車重わずか150kg台、45馬力を11000回転まで回して、コーナーの立ち上がりで一気に前へ出る。軽さを活かした切り返しは全車両でも随一。',
    mass: 151,
    wheelbase: 1.345,
    wheelRadius: 0.3,
    engine: {
      idleRpm: 1500,
      redline: 11500,
      // 45 PS at 9500 rpm, 3.8 kgf·m at 8000 rpm (the Japanese 45 PS limit); a two-stroke's narrow power band
      torque: [[1500, 14], [4000, 19], [6000, 27], [7000, 33], [8000, 37.3], [9000, 36], [9500, 34], [10500, 27.5], [11500, 19]],
      cylinders: 2,
      turbo: false,
      strokes: 2,
    },
    gearSpeeds: [88, 118, 142, 163, 182, 200],
    grip: 1.32,
    drag: 0.15,
    stats: { power: 3, grip: 8, drift: 1, weight: 10 },
    bike: {
      maker: 'Honda',
      type: 'MC21（1990年）',
      com: { height: 0.58, fromRear: 0.68 },
      maxLean: 0.96,
      liveries: [
        { name: 'トリコロール', swatch: '#e9eaec' },
        { name: 'テラブルー', swatch: '#1c4fa0' },
        { name: 'ファイティングレッド', swatch: '#c8161d' },
        { name: 'ブラック', swatch: '#141518' },
      ],
      figures: { engine: '水冷2スト V型2気筒 249cc', displacement: 249, power: '45 PS / 9500 rpm', torque: '3.8 kgf·m / 8000 rpm', weight: '乾燥 132 kg', topSpeed: 190, seat: 0.775 },
    },
    model: { title: 'NSR250R（MC21）', author: 'TOUGE NOCTURNE', url: '', license: '自作', own: true },
  },
  {
    id: 'ninjah2',
    name: 'Ninja H2',
    tagline: 'スーパーチャージャー搭載のハイパーバイク',
    description: 'カワサキが自社製スーパーチャージャーを積んだ1000cc。231馬力の加速はウイリーとの戦いで、過給器の甲高い音とともに最高速は300km/hを大きく超える。',
    mass: 238,
    wheelbase: 1.455,
    wheelRadius: 0.31,
    engine: {
      idleRpm: 1100,
      redline: 14000,
      // 231 PS at 11500 rpm, 141.7 N·m at 11000 rpm (the supercharger's boost rises with the revs)
      torque: [[1100, 52], [3000, 72], [5000, 92], [7000, 112], [9000, 130], [11000, 141.7], [11500, 141], [12500, 131], [14000, 108]],
      cylinders: 4,
      turbo: false,
      supercharger: true,
    },
    gearSpeeds: [150, 195, 232, 268, 302, 340],
    grip: 1.36,
    drag: 0.163,
    stats: { power: 10, grip: 8, drift: 1, weight: 8 },
    bike: {
      maker: 'Kawasaki',
      type: '231 PS 仕様（2017年〜）',
      com: { height: 0.63, fromRear: 0.73 },
      maxLean: 0.98,
      liveries: [
        { name: 'ミラーコートスパークブラック', swatch: '#3a3d44' },
        { name: 'メタリックスパークブラック', swatch: '#121316' },
        { name: 'ライムグリーン', swatch: '#5fb820' },
      ],
      figures: { engine: '水冷4スト 並列4気筒 998cc スーパーチャージャー', displacement: 998, power: '231 PS / 11500 rpm', torque: '141.7 N·m / 11000 rpm', weight: '装備 238 kg', topSpeed: 330, seat: 0.825 },
    },
    model: { title: 'Ninja H2', author: 'TOUGE NOCTURNE', url: '', license: '自作', own: true },
  },
  {
    id: 'hayabusa',
    name: 'GSX1300R 隼',
    tagline: '最高速300km/h超のメガスポーツ',
    description: '1999年に量産車最速の座についた初代ハヤブサ。風洞で磨いた丸いカウルで312km/hに届く。長いホイールベースで高速域は盤石、峠では重さとの付き合い方が鍵。',
    mass: 250,
    wheelbase: 1.485,
    wheelRadius: 0.305,
    engine: {
      idleRpm: 1100,
      redline: 11000,
      // 175 PS at 9800 rpm, 138 N·m at 7000 rpm
      torque: [[1100, 70], [3000, 98], [5000, 122], [7000, 138], [8500, 133], [9800, 125.4], [11000, 108]],
      cylinders: 4,
      turbo: false,
    },
    gearSpeeds: [138, 180, 215, 250, 282, 318],
    grip: 1.3,
    drag: 0.142,
    stats: { power: 9, grip: 7, drift: 1, weight: 7 },
    bike: {
      maker: 'Suzuki',
      type: '初代 GSX1300R（1999年）',
      com: { height: 0.6, fromRear: 0.75 },
      maxLean: 0.94,
      liveries: [
        { name: 'キャンディアントラーズゴールド', swatch: '#b8873a' },
        { name: 'パールスズキディープブルー', swatch: '#1e2f6b' },
        { name: 'グラススパークルブラック', swatch: '#141414' },
        { name: 'パールソニックシルバー', swatch: '#b9bcc0' },
      ],
      figures: { engine: '水冷4スト 並列4気筒 1298cc', displacement: 1298, power: '175 PS / 9800 rpm', torque: '138 N·m / 7000 rpm', weight: '乾燥 215 kg', topSpeed: 312, seat: 0.805 },
    },
    model: { title: 'GSX1300R 隼（初代）', author: 'TOUGE NOCTURNE', url: '', license: '自作', own: true },
  },
];

export const BIKE_ORDER: BikeId[] = BIKES.map((b) => b.id);
export const BIKE_SPECS = Object.fromEntries(BIKES.map((b) => [b.id, bikeSpec(b)])) as Record<BikeId, CarSpec>;

/** the wheelie and stoppie limits as accelerations (m/s²) */
export function bikeLimits(spec: CarSpec) {
  const b = spec.bike!;
  return { wheelie: (9.81 * b.com.fromRear) / b.com.height, stoppie: (9.81 * (spec.wheelbase - b.com.fromRear)) / b.com.height };
}
