import type { CarSpec } from './carSpecs';

/**
 * Fighter aircraft, driven on the ground only, on the Edwards AFB course (owner, 2026-11-10: 「ここで使える限定車両として
 * 戦闘機3機を地上限定で走れるようにしますが、ゴール後は自動操縦で勝手に飛んで終わり」; the top speed: 「物理どおり」).
 *
 * The simulation is VehicleSim on a tricycle gear: the nose wheel (`frontTrack`, `frontWheelRadius`) steers, the main
 * wheels brake, no wheel is driven. The engines push (`thrust`: spool-up lag, afterburner, density and Mach lapse) and
 * the air acts on the airframe (`VehicleSim.jetAero`): drag (clean, gear down, the transonic rise, the speed brake),
 * lift at the ground attitude, which takes weight off the tyres as the speed builds (the aircraft is held on the
 * ground at 97 % of its weight: grip all but gone), side force, the rudder and the fin's weathervane. Figures: the
 * published ones; aerodynamic coefficients and the thrust lapse are estimates (`estimated`).
 */
export type JetId = 'f15j' | 'f15c' | 'su47';

/** the air at Edwards (field elevation 702 m, ISA): density (kg/m³) and the speed of sound (m/s) */
export const EDWARDS_AIR = { density: 1.145, sound: 338.4 };

export interface JetLivery {
  name: string;
  swatch: string;
  /** a model variant (public/models/jets/<id>-<variant>.glb): the two-seaters */
  variant?: string;
  crew: number;
  /** take-off mass of this variant (kg), when it differs */
  mass?: number;
}

export interface JetInfo {
  maker: string;
  /** country and first flight / service year for the spec sheet */
  origin: string;
  engines: {
    count: number;
    name: string;
    /** static sea-level thrust per engine (N): at idle, at military power (dry), with full afterburner */
    idle: number;
    dry: number;
    ab: number;
    /** seconds from idle to military power and back */
    spoolUp: number;
    spoolDown: number;
  };
  /** reference wing area (m²), span (m); coefficients at the ground attitude (lift, zero-lift drag, gear and doors,
   * speed brake area × its drag coefficient in m²) */
  wing: { area: number; span: number; cl0: number; cd0: number; cdGear: number; speedBrake: number };
  /** rotation and lift-off speeds for the take-off after the finish (m/s) */
  vr: number;
  lof: number;
  liveries: JetLivery[];
  /** the procedural stand-in's colours (paint, second tone) */
  camo: [string, string];
  /** landing gear retraction as measured on the model: per leg the hinge axis (model frame) and the stowing angle (rad) */
  gearFold?: Record<'nose' | 'left' | 'right', { axis: [number, number, number]; angle: number }>;
  /** the courses where it may race */
  courses: string[];
  figures: { engine: string; thrust: string; weight: string; maxSpeed: string; span: number; length: number };
  /** which spec-sheet figures are estimates */
  estimated?: string[];
}

interface JetDef {
  id: JetId;
  name: string;
  tagline: string;
  description: string;
  /** take-off mass (kg) */
  mass: number;
  length: number;
  /** nose wheel to main wheels, main-wheel track, the nose wheels' spread (one wheel: ~0.3) */
  wheelbase: number;
  track: number;
  noseTrack: number;
  mainRadius: number;
  noseRadius: number;
  /** share of the weight on the nose wheel */
  noseLoad: number;
  comHeight: number;
  /** fuselage collision box (width, height above the belly, belly clearance) */
  box: { width: number; height: number; clearance: number };
  maxSteerDeg: number;
  stats: CarSpec['stats'];
  jet: JetInfo;
  model: NonNullable<CarSpec['model']>;
}

function jetSpec(d: JetDef): CarSpec {
  const stroke = 0.14;
  return {
    id: d.id,
    name: d.name,
    tagline: d.tagline,
    description: d.description,
    drive: 'RWD',
    engineName: d.jet.figures.engine,
    frontTorqueSplit: 0,
    mass: d.mass,
    size: { width: d.box.width, height: d.box.height, length: d.length },
    wheelbase: d.wheelbase,
    track: d.track,
    frontTrack: d.noseTrack,
    // the centre of mass sits just ahead of the main gear (the nose wheel carries `noseLoad`)
    comForward: (d.noseLoad - 0.5) * d.wheelbase,
    comHeight: d.comHeight,
    wheelRadius: d.mainRadius,
    frontWheelRadius: d.noseRadius,
    clearance: d.box.clearance,
    // oleo struts: ~0.14 m static stroke
    suspension: { rest: 0.4, stiffness: Math.round((d.mass * 9.81) / 4 / stroke), damping: Math.round(2 * 0.5 * Math.sqrt(((d.mass * 9.81) / 4 / stroke) * (d.mass / 4))), antiRoll: Math.round(d.mass * 6) },
    engine: {
      // N2 in % × 100 (the sound and the gauge): idle 65 %, military power 100 %
      idleRpm: 6500,
      redline: 10300,
      torque: [[0, 0]],
      cylinders: 0,
      turbo: false,
    },
    gears: [1],
    finalDrive: 1,
    // aircraft tyres on dry concrete (high pressure, anti-skid): a little under a road car's
    gripFront: 0.7,
    gripRear: 0.75,
    maxSteerDeg: d.maxSteerDeg,
    // carbon brakes with anti-skid on the main wheels: ~0.5 g
    brakeForce: Math.round(d.mass * 9.81 * 0.5),
    dragCoef: 0,
    downforce: 0,
    damping: 0.001,
    rolling: 0.02,
    driftiness: 0,
    stats: d.stats,
    colors: { body: d.jet.liveries[0].swatch, accent: d.jet.camo[1] },
    model: d.model,
    jet: d.jet,
  };
}

const lbf = (x: number) => Math.round(x * 4.44822);

const F15_WING = { area: 56.5, span: 13.05, cl0: 0.08, cd0: 0.0175, cdGear: 0.016, speedBrake: 2.93 };
const F15_BASE = {
  length: 19.43,
  wheelbase: 5.42,
  track: 2.75,
  noseTrack: 0.3,
  // tyres: main 34.5×9.75-18, nose 22×6.6-10
  mainRadius: 0.438,
  noseRadius: 0.279,
  noseLoad: 0.12,
  comHeight: 1.9,
  box: { width: 3.2, height: 2.0, clearance: 0.95 },
  maxSteerDeg: 45,
};

const JETS: JetDef[] = [
  {
    id: 'f15j',
    name: 'F-15J イーグル',
    tagline: '航空自衛隊の主力戦闘機',
    description: '三菱重工がライセンス生産した日本のイーグル。推力10トン級のF100エンジン2基、アフターバーナーを焚けば滑走路の端から端まで一瞬。地上では曲がるのが一番難しい。',
    mass: 20200,
    ...F15_BASE,
    stats: { power: 10, grip: 3, drift: 0, weight: 2 },
    jet: {
      maker: '三菱重工業（McDonnell Douglas ライセンス）',
      origin: '日本（1981年配備）',
      // F100-IHI-220E: 23,450 lbf with afterburner, 14,590 lbf dry
      engines: { count: 2, name: 'F100-IHI-220E', idle: lbf(1200), dry: lbf(14590), ab: lbf(23450), spoolUp: 4, spoolDown: 3 },
      wing: F15_WING,
      vr: 66,
      lof: 75,
      liveries: [
        { name: 'F-15J 制空迷彩', swatch: '#8d949b', crew: 1 },
        { name: 'F-15DJ（複座）', swatch: '#79828a', variant: 'dj', crew: 2, mass: 20500 },
      ],
      camo: ['#8d949b', '#6e767e'],
      courses: ['edwards'],
      figures: { engine: 'IHI F100-IHI-220E ×2', thrust: '104.3 kN ×2（A/B）', weight: '20.2 t（全備）', maxSpeed: 'マッハ2.5', span: 13.05, length: 19.43 },
      estimated: ['空力係数', '推力の速度・高度変化'],
    },
    model: { title: 'F-15J / DJ', author: 'TOUGE NOCTURNE', url: '', license: '自作', own: true },
  },
  {
    id: 'f15c',
    name: 'F-15C イーグル',
    tagline: '空戦無敗の制空戦闘機',
    description: 'エドワーズ空軍基地の試験航空団にも配備されたアメリカ空軍のイーグル。F100-PW-220の2基で推力重量比は1を超え、ブレーキを放せば背中を押しつけられる加速。',
    mass: 20200,
    ...F15_BASE,
    stats: { power: 10, grip: 3, drift: 0, weight: 2 },
    jet: {
      maker: 'McDonnell Douglas',
      origin: 'アメリカ（1979年配備）',
      // F100-PW-220: 23,770 lbf with afterburner, 14,590 lbf dry
      engines: { count: 2, name: 'F100-PW-220', idle: lbf(1200), dry: lbf(14590), ab: lbf(23770), spoolUp: 4, spoolDown: 3 },
      wing: F15_WING,
      vr: 66,
      lof: 75,
      liveries: [
        { name: 'F-15C 412TW（ED）', swatch: '#7f8890', crew: 1 },
        { name: 'F-15D（複座）', swatch: '#6c757d', variant: 'd', crew: 2, mass: 20500 },
      ],
      camo: ['#7f8890', '#5f6870'],
      courses: ['edwards'],
      figures: { engine: 'Pratt & Whitney F100-PW-220 ×2', thrust: '105.7 kN ×2（A/B）', weight: '20.2 t（全備）', maxSpeed: 'マッハ2.5', span: 13.05, length: 19.43 },
      estimated: ['空力係数', '推力の速度・高度変化'],
    },
    model: { title: 'F-15C / D', author: 'TOUGE NOCTURNE', url: '', license: '自作', own: true },
  },
  {
    id: 'su47',
    name: 'Su-47 ベールクト',
    tagline: '前進翼の試作戦闘機',
    description: 'スホーイが1機だけ作った前進翼の実験機「01」。推力15トン級のD-30F6を2基積み、カナードと前進翼の独特な姿で地上を突っ走る。重いぶん、出足はイーグルに一歩譲る。',
    mass: 25670,
    length: 22.6,
    wheelbase: 6.0,
    track: 4.0,
    noseTrack: 0.6,
    mainRadius: 0.5,
    noseRadius: 0.33,
    noseLoad: 0.12,
    comHeight: 2.2,
    box: { width: 3.6, height: 2.2, clearance: 1.0 },
    maxSteerDeg: 45,
    stats: { power: 10, grip: 3, drift: 0, weight: 1 },
    jet: {
      maker: 'Sukhoi',
      origin: 'ロシア（1997年初飛行）',
      // D-30F6: 152 kN with afterburner, 83.4 kN dry (sources differ on the engine: D-30F6 / D-30F11)
      engines: { count: 2, name: 'D-30F6', idle: 6000, dry: 83400, ab: 152000, spoolUp: 5, spoolDown: 3.5 },
      wing: { area: 61.87, span: 16.7, cl0: 0.1, cd0: 0.02, cdGear: 0.016, speedBrake: 0 },
      vr: 72,
      lof: 82,
      liveries: [{ name: '「01」試作機', swatch: '#3b4049', crew: 1 }],
      camo: ['#3b4049', '#2a2e35'],
      courses: ['edwards'],
      figures: { engine: 'Aviadvigatel D-30F6 ×2', thrust: '152 kN ×2（A/B）', weight: '25.7 t（通常離陸）', maxSpeed: 'マッハ1.65', span: 16.7, length: 22.6 },
      estimated: ['車輪配置', '空力係数', '推力の速度・高度変化', '空虚重量（諸説）'],
    },
    model: { title: 'Su-47 ベールクト', author: 'TOUGE NOCTURNE', url: '', license: '自作', own: true },
  },
];

export const JET_ORDER: JetId[] = JETS.map((j) => j.id);
export const JET_SPECS = Object.fromEntries(JETS.map((j) => [j.id, jetSpec(j)])) as Record<JetId, CarSpec>;

/** A jet as flown in a livery (the two-seaters are heavier). */
export function jetForLivery(spec: CarSpec, color?: string): CarSpec {
  const l = spec.jet?.liveries.find((x) => x.swatch === color);
  if (!l?.mass || l.mass === spec.mass) return spec;
  return { ...spec, mass: l.mass, brakeForce: Math.round(l.mass * 9.81 * 0.5) };
}

/** Is this vehicle allowed on this course? (the fighters only at Edwards) */
export const allowedOn = (spec: Pick<CarSpec, 'jet'>, courseId: string) => !spec.jet || spec.jet.courses.includes(courseId);
