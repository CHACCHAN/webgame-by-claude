/**
 * The calculation of VVVF-Simulator by VvvfGeeks (https://github.com/VvvfGeeks/VVVF-Simulator, C#), ported line by
 * line: the control state (`Vvvf/Model/Struct.cs` Domain), the carrier (`Modulation/Carrier.cs`), the pattern
 * solver (`Data/Vvvf/Analyze.cs`), the PWM of 2- and 3-level inverters (`Calculation/Common.cs`, `L2.cs`, `L3.cs`,
 * `Modulation/SVM.cs`, `DeltaSigma.cs`, `CustomPwm.GetPwm`), the induction motor (`Model/Motor.cs`), the in-train
 * sound (`Generation/Audio/TrainSound/Audio.cs`) and the real-time frequency control
 * (`Generation/Audio/RealTime.cs`). Terms of use of the original: free for non-commercial use, link to it.
 * The CHM / SHE switching-angle tables (`customPwm.ts`) are loaded per pattern, only the ones it uses (the simulator's
 * 30 MB of them stay out). Checked sample by sample against the C# build (vvvf.test.ts).
 * DOM-free: runs in the AudioWorklet (vvvf.worklet.ts) and in Node.
 */
import { ALT, type AmplitudeParameter, type FunctionValue, type JerkSettings, type PulseControl, type PulseDataKey, type VvvfData } from './data';
import { CustomPwm, customPwmName } from './customPwm';
import {
  M_2PI, M_2PI_3, M_2_PI, M_PI, M_PI_2, M_PI_3, M_PI_4, M_PI_6, M_SQRT3, M_SQRT3_2,
  compareTo, dotnetSort, roundEven, saw, sine, square, toInt, triangle,
} from './math';

export type Rng = () => number;

// ======================================================================= electrical state (Model/Struct.cs)

export interface CarrierParameter {
  randomRange: number;
  randomInterval: number;
  /** ConstantFrequency.Value (when `vibrato` is null) */
  constant: number;
  vibrato: { highest: number; lowest: number; interval: number } | null;
}

export interface ElectricalState {
  isNone: boolean;
  isZeroOutput: boolean;
  pwmLevel: number;
  pattern: PulseControl | null;
  carrier: CarrierParameter | null;
  pulseData: Partial<Record<PulseDataKey, number>>;
  baseWaveFrequency: number;
  baseWaveAngleFrequency: number;
  baseWaveAmplitude: number | null;
}

const noneState = (pwmLevel: number, baseWaveFrequency: number): ElectricalState => ({
  isNone: true,
  isZeroOutput: true,
  pwmLevel,
  pattern: null,
  carrier: null,
  pulseData: {},
  baseWaveFrequency,
  baseWaveAngleFrequency: M_2PI * baseWaveFrequency,
  baseWaveAmplitude: null,
});

/** Model/Config.GetPulseDataKeyDefaultConstant */
function pulseDataDefault(key: PulseDataKey) {
  switch (key) {
    case 'Dipolar':
      return -1;
    case 'Phase':
      return 0;
    case 'PulseWidth':
      return 0.2;
    case 'UpdateFrequency':
      return 440;
  }
}

/** Model/Config.GetAvailablePulseDataKey */
function availablePulseDataKeys(p: PulseControl['PulseMode'], level: number): PulseDataKey[] {
  if (level === 2) {
    if (p.PulseType === 'SYNC') {
      if ((p.PulseCount === 3 && p.Alternative === ALT.Alt1)) return ['Phase'];
      if ((p.PulseCount === 6 || p.PulseCount === 8) && p.Alternative === ALT.Alt1) return ['PulseWidth'];
      return [];
    }
    if (p.PulseType === 'ΔΣ') return ['UpdateFrequency'];
    return [];
  }
  if (level === 3) {
    if (p.PulseType === 'SYNC') {
      if (p.PulseCount === 1) return [];
      if (p.PulseCount === 5) return p.Alternative === ALT.Alt1 || p.Alternative === ALT.Alt2 ? ['PulseWidth'] : ['Dipolar'];
      return ['Dipolar'];
    }
    if (p.PulseType === 'ASYNC') return ['Dipolar'];
    return [];
  }
  return [];
}

const pulseData = (es: ElectricalState, key: PulseDataKey) => es.pulseData[key] ?? pulseDataDefault(key);

// ======================================================================= carrier (Modulation/Carrier.cs)

class RandomFrequency {
  private simple = false;
  private time = 0;
  private param: { range: number; interval: number } | null = null;
  private baseFrequency = 0;
  private lastRange = 0;
  private lastUpdateTime = 0;
  constructor(private rng: Rng) {}
  setState(simple: boolean, time: number) {
    this.simple = simple;
    this.time = time;
  }
  setCustomParameter(param: { range: number; interval: number }, baseFrequency: number) {
    this.param = param;
    this.baseFrequency = baseFrequency;
  }
  calculate() {
    const p = this.param;
    if (p === null) return NaN;
    if (this.simple) return this.baseFrequency;
    if (this.lastUpdateTime + p.interval < this.time) {
      let range = this.rng() * p.range;
      if (this.rng() < 0.5) range = -range;
      this.lastRange = range;
      this.lastUpdateTime = this.time;
    }
    return this.baseFrequency + this.lastRange;
  }
  resetTime(time: number) {
    this.time = time;
    this.lastUpdateTime = time;
  }
}

type VibratoWave = 'Sine' | 'Triangle' | 'Square' | 'SawUp' | 'SawDown';

class VibratoFrequency {
  private simple = false;
  private time = 0;
  private param: { highest: number; lowest: number; interval: number } | null = null;
  private wave: VibratoWave | null = null;
  private lastInterval = 0;
  private lastTime = 0;
  setState(simple: boolean, time: number) {
    this.simple = simple;
    this.time = time;
  }
  setCustomParameter(param: { highest: number; lowest: number; interval: number }, wave: VibratoWave) {
    this.param = param;
    this.wave = wave;
  }
  calculate() {
    const p = this.param;
    if (p === null || this.wave === null) return NaN;
    if (this.simple) return (p.highest + p.lowest) / 2.0;
    if (this.lastInterval !== p.interval) {
      this.lastTime = this.time - (this.time - this.lastTime) * (this.lastInterval === 0 ? 1 : p.interval / this.lastInterval);
      this.lastInterval = p.interval;
    }
    if (this.time - this.lastTime >= p.interval) this.lastTime = this.time;
    const phase = p.interval > 0 ? ((this.time - this.lastTime) / p.interval) * M_2PI : 0;
    switch (this.wave) {
      case 'Sine':
        return ((p.highest - p.lowest) / 2) * (sine(phase) + 1) + p.lowest;
      case 'Triangle':
        return ((p.highest - p.lowest) / 2) * (triangle(phase) + 1) + p.lowest;
      case 'Square':
        return ((p.highest - p.lowest) / 2) * (square(phase) + 1) + p.lowest;
      case 'SawUp':
        return ((p.highest - p.lowest) / 2) * (saw(phase) + 1) + p.lowest;
      default:
        return ((p.highest - p.lowest) / 2) * (-saw(phase) + 1) + p.lowest;
    }
  }
  resetTime(time: number) {
    this.time = time;
    this.lastTime = time;
  }
}

export class Carrier {
  angleFrequency = 0;
  time = 0;
  useSimpleFrequency = false;
  private random: RandomFrequency;
  private vibrato = new VibratoFrequency();
  constructor(rng: Rng) {
    this.random = new RandomFrequency(rng);
  }
  get frequency() {
    return this.angleFrequency / M_2PI;
  }
  set frequency(value: number) {
    this.angleFrequency = M_2PI * value;
  }
  /** the `AsyncFrequency` setter: keeps the phase (time × angular frequency) */
  setAsyncFrequency(value: number) {
    if (value === 0) this.time = 0;
    else this.time = (this.frequency / value) * this.time;
    this.frequency = value;
  }
  get phase() {
    return this.time * this.angleFrequency;
  }
  calculateBaseCarrierFrequency(time: number, es: ElectricalState) {
    if (es.isNone) return 0;
    const c = es.carrier!;
    if (c.vibrato === null) return c.constant;
    this.vibrato.setState(this.useSimpleFrequency, time);
    this.vibrato.setCustomParameter(c.vibrato, es.pattern!.AsyncModulationData.CarrierWaveData.VibratoData.BaseWave);
    return this.vibrato.calculate();
  }
  calculateCarrierFrequency(time: number, es: ElectricalState) {
    if (es.isNone) return 0;
    const base = this.calculateBaseCarrierFrequency(time, es);
    this.random.setState(this.useSimpleFrequency, time);
    this.random.setCustomParameter(this.randomParam(es.carrier!), base);
    return this.random.calculate();
  }
  private rp = { range: 0, interval: 0 };
  private randomParam(c: CarrierParameter) {
    this.rp.range = c.randomRange;
    this.rp.interval = c.randomInterval;
    return this.rp;
  }
  processCarrierFrequency(time: number, es: ElectricalState) {
    this.setAsyncFrequency(this.calculateCarrierFrequency(time, es));
  }
  resetIFrequencyTime(time: number) {
    this.random.resetTime(time);
    this.vibrato.resetTime(time);
  }
}

// ======================================================================= ΔΣ (Modulation/DeltaSigma.cs)

class DeltaSigma {
  private integrator = 0;
  private lastProcessTime = 0;
  private lastUpdateTime = 0;
  private lastOutBit = 0;
  feedbackInterval = 1e-4;
  process(input: number, nowTime: number) {
    const dt = nowTime - this.lastProcessTime;
    this.lastProcessTime = nowTime;
    const quantized = this.lastOutBit === 1 ? 1.0 : -1.0;
    this.integrator += (input - quantized) * dt;
    if (nowTime - this.lastUpdateTime >= this.feedbackInterval) {
      this.lastOutBit = this.integrator >= 0.0 ? 1 : 0;
      this.lastUpdateTime = nowTime;
    }
    return this.lastOutBit;
  }
  reset(nowTime = 0) {
    this.integrator = 0;
    this.lastOutBit = 0;
    this.lastUpdateTime = nowTime;
    this.lastProcessTime = nowTime;
  }
  resetIfLastTime(lastTime: number) {
    if (lastTime !== this.lastProcessTime) this.reset(lastTime);
  }
}

// ======================================================================= induction motor (Model/Motor.cs)

/** Data/TrainAudio/Struct.MotorSpecification (the simulator's defaults) */
export interface MotorSpec {
  V: number;
  Rs: number;
  Rr: number;
  Ls: number;
  Lr: number;
  Lm: number;
  Np: number;
  Damping: number;
  Inertia: number;
  Fd: number;
  Fc: number;
  Fs: number;
  StribeckOmega: number;
  FricSmoothK: number;
}

export const DEFAULT_MOTOR: MotorSpec = {
  V: 220, Rs: 0.45, Rr: 0.38, Ls: 0.012, Lr: 0.012, Lm: 0.011, Np: 2, Damping: 0.02, Inertia: 0.2,
  Fd: 0.001, Fc: 0.001, Fs: 0.01, StribeckOmega: 2.0, FricSmoothK: 50.0,
};

const COS_120 = Math.cos(M_2PI / 3), SIN_120 = Math.sin(M_2PI / 3);

export class Motor {
  // Status
  ids = 0;
  iqs = 0;
  ird = 0;
  irq = 0;
  vds = 0;
  vqs = 0;
  /** stator electrical angular speed */
  we = 0;
  /** rotor (electrical) angular speed */
  wr = 0;
  thR = 0;
  thMr = 0;
  TL = 0;
  Te = 0;
  phiR = 0;
  wsl = 0;
  preTe = 0;
  diffTe = 0;
  // the specification, unpacked (hot loop)
  private Rs: number;
  private Rr: number;
  private Ls: number;
  private Lr: number;
  private Lm: number;
  private p: number;
  private J: number;
  private Fd: number;
  private Fc: number;
  private Fs: number;
  private wS: number;
  private kS: number;
  /** the determinant of solve2x2(Ls, Lm, Lm, Lr) (the same every step) */
  private det: number;
  // derivatives of the last deriv() call
  private o0 = 0;
  private o1 = 0;
  private o2 = 0;
  private o3 = 0;
  private o4 = 0;

  constructor(readonly spec: MotorSpec) {
    this.Rs = spec.Rs;
    this.Rr = spec.Rr;
    this.Ls = spec.Ls;
    this.Lr = spec.Lr;
    this.Lm = spec.Lm;
    this.p = spec.Np;
    this.J = spec.Inertia;
    this.Fd = spec.Fd;
    this.Fc = spec.Fc;
    this.Fs = spec.Fs;
    this.wS = spec.StribeckOmega;
    this.kS = spec.FricSmoothK;
    let det = spec.Ls * spec.Lr - spec.Lm * spec.Lm;
    if (Math.abs(det) < 1e-12) det = Math.sign(det) * 1e-12 + 1e-12;
    this.det = det;
  }

  reset() {
    this.ids = this.iqs = this.ird = this.irq = this.vds = this.vqs = this.we = this.wr = 0;
    this.thR = this.thMr = this.TL = this.Te = this.phiR = this.wsl = this.preTe = this.diffTe = 0;
  }

  /** derivatives [dids, diqs, dird, dirq, dwr] into o0…o4 (solve2x2 and the friction model inlined) */
  private deriv(ids: number, iqs: number, ird: number, irq: number, wr: number) {
    const Ls = this.Ls, Lr = this.Lr, Lm = this.Lm, det = this.det;
    const ws = this.we;
    const psiSd = Ls * ids + Lm * ird;
    const psiSq = Ls * iqs + Lm * irq;
    const psiRd = Lm * ids + Lr * ird;
    const psiRq = Lm * iqs + Lr * irq;
    const b1d = this.vds - this.Rs * ids + ws * psiSq;
    const b2d = -this.Rr * ird + (ws - wr) * psiRq;
    this.o0 = (b1d * Lr - b2d * Lm) / det;
    this.o2 = (Ls * b2d - Lm * b1d) / det;
    const b1q = this.vqs - this.Rs * iqs - ws * psiSd;
    const b2q = -this.Rr * irq - (ws - wr) * psiRd;
    this.o1 = (b1q * Lr - b2q * Lm) / det;
    this.o3 = (Ls * b2q - Lm * b1q) / det;
    const p = this.p, TL = this.TL;
    const teInst = 1.5 * p * (psiSd * iqs - psiSq * ids);
    // friction: static + Stribeck + tanh smoothing (shortcuts with the same results: exp(−x²) underflows to 0 past
    // x ≈ 27.3, tanh is exactly ±1 past 19.1)
    const teMinusTL = teInst - TL;
    const absWr = Math.abs(wr);
    let tFric: number;
    if (absWr < 1e-6 && Math.abs(teMinusTL) < this.Fs) tFric = teMinusTL;
    else {
      const x = absWr / this.wS, k = this.kS * wr;
      const stribeckAmp = x > 28 ? this.Fs : this.Fs - (this.Fs - this.Fc) * Math.exp(-Math.pow(x, 2.0));
      const smoothSign = k > 20 ? 1 : k < -20 ? -1 : Math.tanh(k);
      tFric = this.Fd * wr + stribeckAmp * smoothSign;
    }
    this.o4 = (p * (teInst - TL - tFric)) / this.J;
  }

  process(dt: number, we: number, U: number, V: number, W: number) {
    this.we = we;
    const th = this.thMr;
    const V2 = this.spec.V;
    // Park transform; cos / sin(θ ± 2π/3) by the addition theorem (the original calls six trig functions: the results
    // differ in the last bits, ~1e-12 of the sound)
    const c = Math.cos(th), s = Math.sin(th);
    const cP = c * COS_120 - s * SIN_120, cM = c * COS_120 + s * SIN_120;
    const sP = s * COS_120 + c * SIN_120, sM = s * COS_120 - c * SIN_120;
    this.vds = ((c * U + cP * V + cM * W) * V2) / 2.0;
    this.vqs = ((-s * U - sP * V - sM * W) * V2) / 2.0;
    const ws = this.we;
    const wr0 = this.wr;
    const ids0 = this.ids, iqs0 = this.iqs, ird0 = this.ird, irq0 = this.irq;
    this.deriv(ids0, iqs0, ird0, irq0, wr0);
    const a0 = this.o0, a1 = this.o1, a2 = this.o2, a3 = this.o3, a4 = this.o4;
    this.deriv(ids0 + 0.5 * a0 * dt, iqs0 + 0.5 * a1 * dt, ird0 + 0.5 * a2 * dt, irq0 + 0.5 * a3 * dt, wr0 + 0.5 * a4 * dt);
    const b0 = this.o0, b1 = this.o1, b2 = this.o2, b3 = this.o3, b4 = this.o4;
    this.deriv(ids0 + 0.5 * b0 * dt, iqs0 + 0.5 * b1 * dt, ird0 + 0.5 * b2 * dt, irq0 + 0.5 * b3 * dt, wr0 + 0.5 * b4 * dt);
    const c0 = this.o0, c1 = this.o1, c2 = this.o2, c3 = this.o3, c4 = this.o4;
    this.deriv(ids0 + c0 * dt, iqs0 + c1 * dt, ird0 + c2 * dt, irq0 + c3 * dt, wr0 + c4 * dt);
    const e0 = this.o0, e1 = this.o1, e2 = this.o2, e3 = this.o3, e4 = this.o4;
    const h = dt / 6.0;
    const ids = ids0 + h * (a0 + 2 * b0 + 2 * c0 + e0);
    const iqs = iqs0 + h * (a1 + 2 * b1 + 2 * c1 + e1);
    const ird = ird0 + h * (a2 + 2 * b2 + 2 * c2 + e2);
    const irq = irq0 + h * (a3 + 2 * b3 + 2 * c3 + e3);
    const wr = wr0 + h * (a4 + 2 * b4 + 2 * c4 + e4);
    const Ls = this.Ls, Lr = this.Lr, Lm = this.Lm;
    const psiSd = Ls * ids + Lm * ird;
    const psiSq = Ls * iqs + Lm * irq;
    const psiRd = Lm * ids + Lr * ird;
    const psiRq = Lm * iqs + Lr * irq;
    this.phiR = Math.sqrt(psiRd * psiRd + psiRq * psiRq);
    this.Te = 1.5 * this.p * (psiSd * iqs - psiSq * ids);
    this.wsl = ws - wr;
    this.ids = ids;
    this.iqs = iqs;
    this.ird = ird;
    this.irq = irq;
    this.wr = wr;
    this.thR += this.wr * dt;
    this.thR %= 2.0 * Math.PI;
    if (this.thR < 0) this.thR += 2.0 * Math.PI;
    this.thMr += ws * dt;
    this.thMr %= 2.0 * Math.PI;
    if (this.thMr < 0) this.thMr += 2.0 * Math.PI;
    this.diffTe = this.Te - this.preTe;
    this.preTe = this.Te;
  }
}

// ======================================================================= control state (Model/Struct.cs Domain)

export class BaseWave {
  angleFrequency = 0;
  time = 0;
  get frequency() {
    return this.angleFrequency / M_2PI;
  }
  set frequency(value: number) {
    this.angleFrequency = M_2PI * value;
  }
}

export class Domain {
  brake = false;
  freeRun = false;
  controlFrequency = 0;
  powerOff = false;
  freeFrequencyChange = 0;
  allowBaseWaveTimeChange = true;
  lastT = 0;
  t = 0;
  readonly motor: Motor;
  es: ElectricalState = noneState(2, 0);
  readonly baseWave = new BaseWave();
  readonly carrier: Carrier;
  readonly deltaSigma = [new DeltaSigma(), new DeltaSigma(), new DeltaSigma()];
  /** CHM / SHE switching-angle tables by name (customPwm.ts), as loaded for the pattern */
  customPwm: Record<string, CustomPwm | undefined> = {};
  customPwmFor: object | null = null;
  customPwmLevel = 0;
  customPwmNow: CustomPwm | undefined;
  /** the last phase state (CalculatePhsaseState) */
  U = 0;
  V = 0;
  W = 0;

  constructor(motor: MotorSpec = DEFAULT_MOTOR, rng: Rng = Math.random) {
    this.motor = new Motor(motor);
    this.carrier = new Carrier(rng);
  }

  processControlParameter(dt: number, jerk: JerkSettings) {
    const pattern = this.brake ? jerk.Braking : jerk.Accelerating;
    if (!this.powerOff) {
      this.freeFrequencyChange = pattern.On.FrequencyChangeRate;
      const maxVoltageFreq = pattern.On.MaxControlFrequency;
      if (this.freeRun && this.controlFrequency > maxVoltageFreq) this.controlFrequency = this.baseWave.frequency;
    } else {
      this.freeFrequencyChange = pattern.Off.FrequencyChangeRate;
      const maxVoltageFreq = pattern.Off.MaxControlFrequency;
      if (this.freeRun && this.controlFrequency > maxVoltageFreq) this.controlFrequency = maxVoltageFreq;
    }
    if (!this.powerOff) {
      const F = this.baseWave.frequency;
      if (!this.freeRun) this.controlFrequency = F;
      else {
        const updated = this.controlFrequency + this.freeFrequencyChange * dt;
        if (F <= updated) {
          this.controlFrequency = F;
          this.freeRun = false;
        } else {
          this.controlFrequency = updated;
          this.freeRun = true;
        }
      }
    } else {
      const change = this.freeFrequencyChange * dt;
      const final = this.controlFrequency - change;
      this.controlFrequency = final > 0 ? final : 0;
      this.freeRun = true;
    }
  }

  addTimeAll(delta: number) {
    this.lastT = this.t;
    this.t = this.t + delta;
    this.baseWave.time += delta;
    this.carrier.time += delta;
  }
}

// ======================================================================= pattern solver (Data/Vvvf/Analyze.cs)

const changingValue = (x1: number, y1: number, x2: number, y2: number, x: number) => y1 + ((y2 - y1) / (x2 - x1)) * (x - x1);

function movingValue(d: FunctionValue, current: number) {
  let val = 1000;
  if (d.Type === 'Proportional') val = changingValue(d.Start, d.StartValue, d.End, d.EndValue, current);
  else if (d.Type === 'Pow2_Exponential')
    val = (Math.pow(2, Math.pow((current - d.Start) / (d.End - d.Start), d.Degree)) - 1) * (d.EndValue - d.StartValue) + d.StartValue;
  else if (d.Type === 'Inv_Proportional') {
    const x = changingValue(d.Start, 1 / d.StartValue, d.End, 1 / d.EndValue, current);
    const c = -d.CurveRate;
    const k = d.EndValue;
    const l = d.StartValue;
    const a = (1 / (1 / l - 1 / k)) * (1 / (l - c) - 1 / (k - c));
    const b = (1 / (1 - (1 / l) * k)) * (1 / (l - c) - ((1 / l) * k) / (k - c));
    val = 1 / (a * x + b) + c;
  } else if (d.Type === 'Sine') {
    const x = ((M_PI_2 - Math.asin(d.StartValue / d.EndValue)) / (d.End - d.Start)) * (current - d.Start) + Math.asin(d.StartValue / d.EndValue);
    val = Math.sin(x) * d.EndValue;
  }
  return val;
}

function amplitudeOf(p: AmplitudeParameter, current: number) {
  if (p.Mode === 'Table') {
    let target = 0;
    for (let i = 0; i < p.AmplitudeTable.length; i++) {
      if (p.AmplitudeTable[i][0] > current) break;
      target = i;
    }
    if (p.AmplitudeTableInterpolation && target + 1 < p.AmplitudeTable.length) {
      const [f0, a0] = p.AmplitudeTable[target];
      const [f1, a1] = p.AmplitudeTable[target + 1];
      return ((a1 - a0) / (f1 - f0)) * (current - f0) + a0;
    }
    return p.AmplitudeTable[target]?.[1] ?? 0;
  }
  let amplitude = 0;
  if (p.EndAmplitude === p.StartAmplitude) amplitude = p.StartAmplitude;
  else if (p.Mode === 'Linear') {
    if (!p.DisableRangeLimit) {
      if (current < p.StartFrequency) current = p.StartFrequency;
      if (current > p.EndFrequency) current = p.EndFrequency;
    }
    amplitude = ((p.EndAmplitude - p.StartAmplitude) / (p.EndFrequency - p.StartFrequency)) * (current - p.StartFrequency) + p.StartAmplitude;
  } else if (p.Mode === 'InverseProportional') {
    if (!p.DisableRangeLimit) {
      if (current < p.StartFrequency) current = p.StartFrequency;
      if (current > p.EndFrequency) current = p.EndFrequency;
    }
    const x = ((1.0 / p.EndAmplitude - 1.0 / p.StartAmplitude) / (p.EndFrequency - p.StartFrequency)) * (current - p.StartFrequency) + 1.0 / p.StartAmplitude;
    const c = -p.CurveChangeRate;
    const k = p.EndAmplitude;
    const l = p.StartAmplitude;
    const a = (1 / (1 / l - 1 / k)) * (1 / (l - c) - 1 / (k - c));
    const b = (1 / (1 - (1 / l) * k)) * (1 / (l - c) - ((1 / l) * k) / (k - c));
    amplitude = 1 / (a * x + b) + c;
  } else if (p.Mode === 'Exponential') {
    if (!p.DisableRangeLimit && current > p.EndFrequency) current = p.EndFrequency;
    const t = (1 / p.EndFrequency) * Math.log(p.EndAmplitude + 1);
    amplitude = Math.pow(Math.E, t * current) - 1;
  } else if (p.Mode === 'LinearPolynomial') {
    if (!p.DisableRangeLimit && current > p.EndFrequency) current = p.EndFrequency;
    amplitude = (Math.pow(current, p.Polynomial) / Math.pow(p.EndFrequency, p.Polynomial)) * p.EndAmplitude;
  } else if (p.Mode === 'Sine') {
    if (!p.DisableRangeLimit && current > p.EndFrequency) current = p.EndFrequency;
    const x = (Math.PI * current) / (2.0 * p.EndFrequency);
    amplitude = Math.sin(x) * p.EndAmplitude;
  }
  if (p.CutOffAmplitude > amplitude) amplitude = 0;
  if (p.MaxAmplitude !== -1 && p.MaxAmplitude < amplitude) amplitude = p.MaxAmplitude;
  return amplitude;
}

function isMatching(d: Domain, ysd: PulseControl) {
  const baseFrequency = d.baseWave.frequency;
  const enableFreeRun = d.freeRun && ((!d.powerOff && ysd.EnableFreeRunOn) || (d.powerOff && ysd.EnableFreeRunOff));
  const enableNormal = ysd.EnableNormal && !d.freeRun;
  if (!(enableFreeRun || enableNormal)) return false;
  const c1 = ysd.ControlFrequencyFrom <= d.controlFrequency;
  const c2 = ysd.RotateFrequencyFrom === -1 || ysd.RotateFrequencyFrom <= baseFrequency;
  const c3 = ysd.RotateFrequencyBelow === -1 || ysd.RotateFrequencyBelow > baseFrequency;
  if (!c2) return false;
  if (!c3) return false;
  if (!d.freeRun && c1) return true;
  if (!d.freeRun && !c1) return false;
  if (c1) return true;
  if ((ysd.StuckFreeRunOn && d.freeRun && !d.powerOff) || (ysd.StuckFreeRunOff && d.freeRun && d.powerOff)) {
    return baseFrequency > ysd.ControlFrequencyFrom;
  }
  return false;
}

/** the pattern lists in the order Analyze.Calculate searches them (sorted by start frequency, high to low) */
const sortedLists = new WeakMap<VvvfData, { accel: PulseControl[]; brake: PulseControl[] }>();
function patternsOf(data: VvvfData, braking: boolean) {
  let s = sortedLists.get(data);
  if (!s) {
    const desc = (a: PulseControl, b: PulseControl) => compareTo(b.ControlFrequencyFrom, a.ControlFrequencyFrom);
    s = { accel: dotnetSort([...data.AcceleratePattern], desc), brake: dotnetSort([...data.BrakingPattern], desc) };
    sortedLists.set(data, s);
  }
  return braking ? s.brake : s.accel;
}

/** Data.Vvvf.Analyze.Calculate: the electrical state for the control state */
export function analyze(d: Domain, data: VvvfData) {
  const baseFrequency = d.baseWave.frequency;
  const minBaseFrequency = d.brake ? data.MinimumFrequency.Braking : data.MinimumFrequency.Accelerating;
  if (0 < d.controlFrequency && d.controlFrequency < minBaseFrequency && !d.freeRun) d.controlFrequency = minBaseFrequency;
  d.allowBaseWaveTimeChange = !(baseFrequency < minBaseFrequency && d.controlFrequency > 0);
  const solvedBaseFrequency = d.allowBaseWaveTimeChange ? baseFrequency : minBaseFrequency;

  const list = patternsOf(data, d.brake);
  let solve: PulseControl | null = null;
  for (const ysd of list) {
    if (!isMatching(d, ysd)) continue;
    solve = ysd;
    break;
  }
  if (solve === null) {
    if (d.freeRun) d.controlFrequency = d.powerOff ? 0 : baseFrequency;
    d.es = noneState(data.Level, solvedBaseFrequency);
    return;
  }
  const pulse = solve.PulseMode;

  let carrier: CarrierParameter | null = null;
  if (pulse.PulseType === 'ASYNC') {
    const am = solve.AsyncModulationData;
    const cf = d.controlFrequency;
    const rr = am.RandomData.Range, ri = am.RandomData.Interval;
    carrier = {
      randomRange: rr.Mode === 'Moving' ? movingValue(rr.MovingValue, cf) : rr.Constant,
      randomInterval: ri.Mode === 'Moving' ? movingValue(ri.MovingValue, cf) : ri.Constant,
      constant: 0,
      vibrato: null,
    };
    const cw = am.CarrierWaveData;
    if (cw.Mode === 'Vibrato') {
      const v = (p: { Mode: 'Const' | 'Moving'; Constant: number; MovingValue: FunctionValue }) => (p.Mode === 'Moving' ? movingValue(p.MovingValue, cf) : p.Constant);
      carrier.vibrato = { highest: v(cw.VibratoData.Highest), lowest: v(cw.VibratoData.Lowest), interval: v(cw.VibratoData.Interval) };
    } else if (cw.Mode === 'Table') {
      const table = dotnetSort([...cw.CarrierFrequencyTable.Table], (a, b) => Math.sign(b.ControlFrequencyFrom - a.ControlFrequencyFrom));
      let target = 0;
      for (let i = 0; i < table.length; i++) {
        const e = table[i];
        const flag1 = e.FreeRunStuckAtHere && baseFrequency >= e.ControlFrequencyFrom && d.freeRun;
        const flag2 = d.controlFrequency > e.ControlFrequencyFrom;
        if (!flag1 && !flag2) continue;
        target = i;
        break;
      }
      carrier.constant = table[target].CarrierFrequency;
    } else if (cw.Mode === 'Moving') carrier.constant = movingValue(cw.MovingValue, cf);
    else carrier.constant = cw.Constant;
  }

  let amplitude = 0;
  if (d.freeRun) {
    const jerk = d.brake ? data.JerkSetting.Braking : data.JerkSetting.Accelerating;
    const param: AmplitudeParameter = { ...(d.powerOff ? solve.Amplitude.PowerOff : solve.Amplitude.PowerOn) };
    const maxControlFrequency = !d.powerOff ? jerk.On.MaxControlFrequency : jerk.Off.MaxControlFrequency;
    if (param.EndFrequency === -1) {
      if (solve.Amplitude.Default.DisableRangeLimit) param.EndFrequency = baseFrequency;
      else {
        param.EndFrequency = baseFrequency > maxControlFrequency ? maxControlFrequency : baseFrequency;
        param.EndFrequency = param.EndFrequency > solve.Amplitude.Default.EndFrequency ? solve.Amplitude.Default.EndFrequency : param.EndFrequency;
      }
    }
    if (param.EndAmplitude === -1) param.EndAmplitude = amplitudeOf(solve.Amplitude.Default, baseFrequency);
    if (param.StartAmplitude === -1) param.StartAmplitude = amplitudeOf(solve.Amplitude.Default, baseFrequency);
    amplitude = amplitudeOf(param, d.controlFrequency);
  } else amplitude = amplitudeOf(solve.Amplitude.Default, d.controlFrequency);

  const solvedPulseData: Partial<Record<PulseDataKey, number>> = {};
  for (const key of availablePulseDataKeys(pulse, data.Level)) {
    const value = pulse.PulseData[key];
    let val = pulseDataDefault(key);
    if (value) val = value.Mode === 'Moving' ? movingValue(value.MovingValue, d.controlFrequency) : value.Constant;
    solvedPulseData[key] = val;
  }

  if (d.powerOff && amplitude === 0) d.controlFrequency = 0;

  d.es = {
    isNone: false,
    isZeroOutput: d.es.baseWaveAmplitude === 0 || d.controlFrequency === 0,
    pwmLevel: data.Level,
    pattern: solve,
    carrier,
    pulseData: solvedPulseData,
    baseWaveFrequency: solvedBaseFrequency,
    baseWaveAngleFrequency: M_2PI * solvedBaseFrequency,
    baseWaveAmplitude: amplitude,
  };
}

// ======================================================================= PWM (Calculation/Common.cs, L2.cs, L3.cs)

const modulate = (signal: number, carrier: number) => (signal > carrier ? 1 : 0);

function discreteTimeLine(x: number, level: number, mode: 'Left' | 'Middle' | 'Right') {
  const seed = ((x % M_2PI) * level) / M_2PI;
  const time = mode === 'Left' ? Math.ceil(seed) : mode === 'Middle' ? roundEven(seed) : Math.floor(seed);
  return (time * M_2PI) / level;
}

/** RawX of the last baseWaveX call (GetBaseWaveParameter returns both) */
let rawX = 0;

/** GetBaseWaveParameter: X (the discretised angle; RawX in `rawX`) */
function baseWaveX(d: Domain, phase: number, initialPhase: number) {
  const es = d.es;
  if (es.isNone) {
    rawX = 0;
    return 0;
  }
  const raw = es.baseWaveAngleFrequency * d.baseWave.time + M_2PI_3 * phase + initialPhase;
  rawX = raw;
  const dt = es.pattern!.PulseMode.DiscreteTime;
  return dt.Enabled ? discreteTimeLine(raw, dt.Steps, dt.Mode) : raw;
}

// SVM (Modulation/SVM.cs)
function svmSector(alpha: number, beta: number) {
  const A = beta > 0.0 ? 0 : 1;
  const B = beta - M_SQRT3 * alpha > 0.0 ? 0 : 1;
  const C = beta + M_SQRT3 * alpha > 0.0 ? 0 : 1;
  switch (4 * A + 2 * B + C) {
    case 0: return 2;
    case 1: return 3;
    case 2: return 1;
    case 3: return 0;
    case 4: return 0;
    case 5: return 4;
    case 6: return 6;
    case 7: return 5;
    default: return 2;
  }
}

function svmPhase(u: number, v: number, w: number, phase: number) {
  const alpha = (2 * u - v - w) / 3;
  const beta = (v - w) / M_SQRT3;
  const sector = svmSector(alpha, beta);
  let T1 = 0, T2 = 0;
  switch (sector) {
    case 1: T1 = M_SQRT3_2 * alpha - 0.5 * beta; T2 = beta; break;
    case 2: T1 = M_SQRT3_2 * alpha + 0.5 * beta; T2 = 0.5 * beta - M_SQRT3_2 * alpha; break;
    case 3: T1 = beta; T2 = -(M_SQRT3_2 * alpha + 0.5 * beta); break;
    case 4: T1 = 0.5 * beta - M_SQRT3_2 * alpha; T2 = -beta; break;
    case 5: T1 = -(M_SQRT3_2 * alpha + 0.5 * beta); T2 = M_SQRT3_2 * alpha - 0.5 * beta; break;
    case 6: T1 = -beta; T2 = M_SQRT3_2 * alpha + 0.5 * beta; break;
  }
  const T0 = 1.0 - T1 - T2;
  let U = 0, V = 0, W = 0;
  switch (sector) {
    case 1: U = T1 + T2 + 0.5 * T0; V = T2 + 0.5 * T0; W = 0.5 * T0; break;
    case 2: U = T1 + 0.5 * T0; V = T1 + T2 + 0.5 * T0; W = 0.5 * T0; break;
    case 3: U = 0.5 * T0; V = T1 + T2 + 0.5 * T0; W = T2 + 0.5 * T0; break;
    case 4: U = 0.5 * T0; V = T1 + 0.5 * T0; W = T1 + T2 + 0.5 * T0; break;
    case 5: U = T2 + 0.5 * T0; V = 0.5 * T0; W = T1 + T2 + 0.5 * T0; break;
    case 6: U = T1 + T2 + 0.5 * T0; V = 0.5 * T0; W = T1 + 0.5 * T0; break;
  }
  return phase === 0 ? U : phase === 1 ? V : W;
}

/** GetBaseWaveform: the reference of one phase (−1…1) */
function baseWaveform(d: Domain, phase: number, ip: number): number {
  const es = d.es;
  if (es.isNone) return 0;
  const A = es.baseWaveAmplitude!;
  const pm = es.pattern!.PulseMode;
  const bw = pm.BaseWave;
  if (bw === 'SV') {
    const u = A * sine(baseWaveX(d, 0, ip));
    const v = A * sine(baseWaveX(d, 1, ip));
    const w = A * sine(baseWaveX(d, 2, ip));
    return svmPhase(u, v, w, phase) * 2 - 1;
  }
  if (bw === 'DPWM30') {
    const X = baseWaveX(d, phase, ip);
    const sector = toInt((X % M_2PI) / M_PI_6);
    switch (sector) {
      case 0: case 9: return A * sine(X) + (1 - A * sine(baseWaveX(d, phase, ip + M_2PI_3)));
      case 1: case 4: return 1;
      case 2: case 11: return A * sine(X) + (-1 - A * sine(baseWaveX(d, phase, ip - M_2PI_3)));
      case 3: case 6: return A * sine(X) + (-1 - A * sine(baseWaveX(d, phase, ip + M_2PI_3)));
      case 5: case 8: return A * sine(X) + (1 - A * sine(baseWaveX(d, phase, ip - M_2PI_3)));
      default: return -1;
    }
  }
  if (bw === 'DPWM60C') {
    const X = baseWaveX(d, phase, ip);
    const sector = toInt((X % M_2PI) / M_PI_3);
    switch (sector) {
      case 0: return A * sine(X) + (-1 - A * sine(baseWaveX(d, phase, ip - M_2PI_3)));
      case 1: return 1;
      case 2: return A * sine(X) + (-1 - A * sine(baseWaveX(d, phase, ip + M_2PI_3)));
      case 3: return A * sine(X) + (1 - A * sine(baseWaveX(d, phase, ip - M_2PI_3)));
      case 4: return -1;
      default: return A * sine(X) + (1 - A * sine(baseWaveX(d, phase, ip + M_2PI_3)));
    }
  }
  if (bw === 'DPWM60P') {
    const X = baseWaveX(d, phase, ip);
    const sector = toInt((X % M_2PI) / M_PI_6);
    switch (sector) {
      case 1: case 2: return A * sine(X) + (-1 - A * sine(baseWaveX(d, phase, ip - M_2PI_3)));
      case 3: case 4: return 1;
      case 5: case 6: return A * sine(X) + (-1 - A * sine(baseWaveX(d, phase, ip + M_2PI_3)));
      case 7: case 8: return A * sine(X) + (1 - A * sine(baseWaveX(d, phase, ip - M_2PI_3)));
      case 9: case 10: return -1;
      default: return A * sine(X) + (1 - A * sine(baseWaveX(d, phase, ip + M_2PI_3)));
    }
  }
  if (bw === 'DPWM60N') {
    const X = baseWaveX(d, phase, ip);
    const sector = toInt((X % M_2PI) / M_PI_6);
    switch (sector) {
      case 1: case 2: return 1;
      case 3: case 4: return A * sine(X) + (-1 - A * sine(baseWaveX(d, phase, ip + M_2PI_3)));
      case 5: case 6: return A * sine(X) + (1 - A * sine(baseWaveX(d, phase, ip - M_2PI_3)));
      case 7: case 8: return -1;
      case 9: case 10: return A * sine(X) + (1 - A * sine(baseWaveX(d, phase, ip + M_2PI_3)));
      default: return A * sine(X) + (-1 - A * sine(baseWaveX(d, phase, ip - M_2PI_3)));
    }
  }
  if (bw === 'DPWM120P') {
    const X = baseWaveX(d, phase, ip);
    const sector = toInt((X % M_2PI) / M_PI_6);
    if (sector >= 1 && sector <= 4) return 1;
    if (sector >= 5 && sector <= 8) return A * sine(X) + (1 - A * sine(baseWaveX(d, phase, ip - M_2PI_3)));
    return A * sine(X) + (1 - A * sine(baseWaveX(d, phase, ip + M_2PI_3)));
  }
  if (bw === 'DPWM120N') {
    const X = baseWaveX(d, phase, ip);
    const sector = toInt((X % M_2PI) / M_PI_6);
    if (sector >= 3 && sector <= 6) return A * sine(X) + (-1 - A * sine(baseWaveX(d, phase, ip + M_2PI_3)));
    if (sector >= 7 && sector <= 10) return -1;
    return A * sine(X) + (-1 - A * sine(baseWaveX(d, phase, ip - M_2PI_3)));
  }
  const X = baseWaveX(d, phase, ip);
  let shape = 0;
  switch (bw) {
    case 'Sine': shape = sine(X); break;
    case 'Saw': shape = triangle(X); break;
    case 'Square': shape = square(X); break;
    case 'ModifiedSine1': shape = roundEven(sine(X) * 1) / 1; break;
    case 'ModifiedSine2': shape = roundEven(sine(X) * 2) / 2; break;
    case 'ModifiedSaw1': {
      let y = triangle(X) * M_PI_2;
      if (Math.abs(y) > 0.5) y = y > 0 ? 1 : -1;
      shape = y;
      break;
    }
  }
  const base = A * shape;
  let harmonicWave = 0.0;
  const hs = pm.PulseHarmonics;
  for (let i = 0; i < hs.length; i++) {
    const h = hs[i];
    const hx = h.IsHarmonicProportional ? h.Harmonic * (X + h.InitialPhase) : M_2PI * h.Harmonic * (d.t + M_2PI_3 * phase + ip + h.InitialPhase);
    const v = h.Type === 'Sine' ? sine(hx) : h.Type === 'Saw' ? triangle(hx) : h.Type === 'Square' ? square(hx) : 0;
    harmonicWave += v * h.Amplitude * (h.IsAmplitudeProportional ? A : 1);
  }
  let wave = base + harmonicWave;
  wave = wave > 1 ? 1 : wave < -1 ? -1 : wave;
  return wave;
}

/** GetCarrierWaveform */
function carrierWaveform(d: Domain, time: number) {
  const es = d.es;
  if (es.isNone) return 0;
  const cw = es.pattern!.PulseMode.CarrierWave;
  switch (cw.Type) {
    case 'Triangle':
      return cw.Option === 'RaiseStart' ? triangle(time) : cw.Option === 'FallStart' ? -triangle(time) : cw.Option === 'TopStart' ? triangle(time + M_PI_2) : -triangle(time + M_PI_2);
    case 'Saw':
      return cw.Option === 'RaiseStart' ? saw(time) : cw.Option === 'FallStart' ? -saw(time) : cw.Option === 'TopStart' ? -saw(time + M_PI_2) : saw(time + M_PI_2);
    case 'Sine':
      return cw.Option === 'RaiseStart' ? sine(time) : cw.Option === 'FallStart' ? -sine(time) : cw.Option === 'TopStart' ? sine(time + M_PI_2) : -sine(time + M_PI_2);
  }
  return 0;
}

/** CustomPwm.GetPwm (static): a quarter-wave switching table → level 0…2 */
function customPwm(angles: number[], outputs: number[], X: number, startLevel: number) {
  X %= M_2PI;
  const orthant = toInt(X / M_PI_2);
  let angle = X % M_PI_2;
  if ((orthant & 0x01) === 1) angle = M_PI_2 - angle;
  let pwm = startLevel;
  for (let i = 0; i < angles.length; i++) {
    if (angles[i] <= angle) pwm = outputs[i];
    else break;
  }
  if (orthant > 1) pwm = 2 - pwm;
  return pwm;
}

const SQRT5 = Math.sqrt(5), SQRT3 = Math.sqrt(3);
const sync11Angles = [0, 0, 0, 0, 0];
const SYNC11_OUT = [2, 0, 2, 0, 2];

function l2Sync(d: Domain, ip: number, phase: number): number {
  const es = d.es;
  if (es.isNone) return 0;
  const X = baseWaveX(d, phase, ip);
  const RawX = rawX;
  const pm = es.pattern!.PulseMode;
  const A = es.baseWaveAmplitude!;
  const count = pm.PulseCount, alt = pm.Alternative;
  if (count === 1 && (alt === ALT.Alt1 || alt === ALT.Alt2)) {
    const sign = alt === ALT.Alt1 ? 1 : -1;
    const ampAbs = A < 0 ? -A : A;
    const ampSign = A < 0 ? -1 : 1;
    const sineVal = -triangle(X) + sign * (1 - Math.asin(Math.min(1, Math.max(0, ampAbs * M_PI_4))) * M_2_PI);
    return sineVal > 0 ? -ampSign + 1 : ampSign + 1;
  }
  if (count === 3 && alt === ALT.Alt1) {
    const sineVal = sine(RawX);
    const sawVal = -triangle(RawX - (pulseData(es, 'Phase') / 180.0) * M_PI);
    const pwm = (sineVal > 0 ? 1 : -1) * ((A * 2) / 3.0 + 1 / 3.0);
    const negate = sawVal > 0 ? sawVal - 1 : sawVal + 1;
    return modulate(pwm, negate) * 2;
  }
  if ((count === 5 || count === 9 || count === 13 || count === 17) && alt === ALT.Alt1) {
    const sineVal = baseWaveform(d, phase, ip);
    const sawValue = -triangle(27 * RawX);
    const fixedX = toInt(RawX / M_PI_2) % 2 === 1 ? M_PI_2 - (RawX % M_PI_2) : RawX % M_PI_2;
    d.carrier.angleFrequency = es.baseWaveAngleFrequency;
    d.carrier.time = d.baseWave.time;
    return fixedX < (M_PI * count) / 54 ? modulate(sineVal, sawValue) * 2 : toInt(RawX / M_PI_2) % 4 > 1 ? 0 : 2;
  }
  if (count === 11 && alt === ALT.Alt1) {
    const a = sync11Angles;
    a[0] = M_PI / 15 - ((1 + SQRT5) / (10 * SQRT3)) * A - ((2 * sine(M_PI / 30)) / (5 * SQRT3)) * A;
    a[1] = M_PI / 15 + ((SQRT5 - 1) / (10 * SQRT3)) * A + ((2 * sine((M_PI * 7.0) / 30.0)) / (5 * SQRT3)) * A;
    a[2] = M_PI / 6 - (1 / (5 * SQRT3)) * A;
    a[3] = (M_PI * 2.0) / 5 - ((2 * sine(M_PI / 30)) / (5 * SQRT3)) * A;
    a[4] = (M_PI * 2.0) / 5 + ((SQRT5 - 1) / (10 * SQRT3)) * A;
    if (A >= 0.9927) a[0] = 0;
    if (A >= 0.9203069589) {
      a[1] = 0.417331;
      a[2] = 0.417331;
      a[3] = 1.23442104526 + 0.278769982056 * (A - 0.9203069589);
      a[4] = 1.32231416347 - 0.824126360283 * (A - 0.9203069589);
    }
    return customPwm(a, SYNC11_OUT, X, 0);
  }
  if ((count === 6 || count === 8) && alt === ALT.Alt1) {
    const C = count === 6 ? 6 : 9;
    const sawVal = -triangle(C * RawX + M_PI_2);
    const orthant = toInt((RawX % M_2PI) / M_PI_2);
    const fixX = orthant % 2 === 1 ? M_PI_2 - (RawX % M_PI_2) : RawX % M_PI_2;
    let sig = orthant > 1 ? 1 : -1;
    if (fixX > pulseData(es, 'PulseWidth')) sig = orthant > 1 ? -1 : 1;
    sig *= A;
    return modulate(sig, sawVal) * 2;
  }
  if (alt === ALT.CP) {
    const sineVal = baseWaveform(d, phase, ip);
    const carrierFrequency = toInt(count / 2) * 6;
    let sawVal = carrierFrequency === 0 ? 0 : -triangle(carrierFrequency * RawX + M_PI_2) * (count % 2 === 1 ? 0.5 : -0.5) + 0.5;
    const cycleX = RawX % M_2PI;
    const orthant = toInt((RawX % M_PI) / M_PI_3);
    if (cycleX >= M_PI) sawVal = -sawVal;
    if (orthant !== 1) sawVal = 0;
    return modulate(sineVal, sawVal) * 2;
  }
  if (alt === ALT.Square) {
    let n = count;
    n += n % 2 === 0 ? 0 : -1;
    const carrierVal = 0.5 * ((count % 2 === 0 ? 1 : -1) * triangle(3 * n * RawX + M_PI_2) + 1);
    return modulate(X % M_2PI < M_PI ? A : -A, carrierVal) * 2;
  }
  const sineVal = baseWaveform(d, phase, ip);
  const carrierVal = carrierWaveform(d, count * RawX);
  d.carrier.angleFrequency = es.baseWaveAngleFrequency;
  d.carrier.time = d.baseWave.time;
  return modulate(sineVal, carrierVal) * 2;
}

const HO_KEYS: Record<number, number[]> = {
  5: [9, 2, 13, 2, 17, 2, 21, 2, 25, 2, 29, 2, 33, 2, 37, 2],
  7: [15, 4, 15, 3, 7, 1, 11, 2, 19, 4, 23, 4, 27, 4, 31, 4, 35, 4, 39, 4],
  9: [21, 6, 13, 3, 17, 4, 25, 6, 29, 6, 33, 6, 37, 6],
  11: [27, 8, 19, 5, 23, 6, 31, 8, 35, 8, 39, 8],
  13: [25, 7, 29, 8, 33, 10, 37, 10],
  15: [31, 9, 35, 10, 39, 12],
  17: [37, 11],
};

function ho(x: number, amplitude: number, carrier: number, width: number) {
  const totalSteps = carrier * 2;
  const fixedX = (x % M_PI) / (M_PI / totalSteps);
  const sawValue = triangle(carrier * x);
  let modulated: number;
  if (fixedX > totalSteps - 1) modulated = -1;
  else if (fixedX > toInt(totalSteps / 2) + width) modulated = 1;
  else if (fixedX > toInt(totalSteps / 2) - width) modulated = 2 * amplitude - 1;
  else if (fixedX > 1) modulated = 1;
  else modulated = -1;
  if (x % M_2PI > M_PI) modulated = -modulated;
  return modulate(modulated, sawValue);
}

function l2Ho(d: Domain, ip: number, phase: number) {
  const es = d.es;
  if (es.isNone) return 0;
  const X = baseWaveX(d, phase, ip);
  const pm = es.pattern!.PulseMode;
  const keys = HO_KEYS[pm.PulseCount] ?? [0];
  const n = pm.Alternative - ALT.Alt1 + 1;
  const index = pm.Alternative === ALT.Default || n >= toInt(keys.length / 2) ? 0 : n;
  return ho(X, es.baseWaveAmplitude!, keys[2 * index], keys[2 * index + 1]) * 2;
}

function l2DeltaSigma(d: Domain, ip: number, phase: number) {
  const es = d.es;
  if (es.isNone) return 0;
  const ds = d.deltaSigma[phase];
  ds.resetIfLastTime(d.lastT);
  ds.feedbackInterval = 1.0 / pulseData(es, 'UpdateFrequency');
  return ds.process(baseWaveform(d, phase, ip), d.t) * 2;
}

function l3Sync(d: Domain, ip: number, phase: number): number {
  const es = d.es;
  if (es.isNone) return 0;
  const X = baseWaveX(d, phase, ip);
  const RawX = rawX;
  const pm = es.pattern!.PulseMode;
  const A = es.baseWaveAmplitude!;
  if (pm.PulseCount === 1 && pm.Alternative === ALT.Alt1) {
    const sineVal = sine(X);
    const D = sineVal > 0 ? 1 : -1;
    const voltageFix = D * (1 - A);
    let gate = D * (sineVal - voltageFix) > 0 ? D : 0;
    gate += 1;
    return gate;
  }
  if (pm.PulseCount === 5 && pm.Alternative === ALT.Alt1) {
    const period = X % M_2PI;
    const orthant = toInt(period / M_PI_2);
    const quarter = period % M_PI_2;
    const pwm = (t: number) => {
      const a = M_PI_2 - A;
      const b = (pulseData(es, 'PulseWidth') / 180) * M_PI;
      if (t < a) return 1;
      if (t < a + b) return 2;
      if (t < a + 2 * b) return 1;
      return 2;
    };
    return orthant === 0 ? pwm(quarter) : orthant === 1 ? pwm(M_PI_2 - quarter) : orthant === 2 ? 2 - pwm(quarter) : 2 - pwm(M_PI_2 - quarter);
  }
  if (pm.PulseCount === 5 && pm.Alternative === ALT.Alt2) {
    const sineVal = A * sine(RawX);
    const beta = (pulseData(es, 'PulseWidth') / 180) * M_PI;
    const x = RawX % M_2PI;
    const orthant = toInt(x / M_PI_2) % 4;
    const carrierAt = (x: number, beta: number) => {
      if (0 <= x && x < beta) return -(1 / beta) * x + 1;
      else if (beta <= x && x < M_PI_2) return (-1 / (M_PI_2 - beta)) * (x - M_PI_2);
      return 0;
    };
    const sawVal = orthant === 0 ? carrierAt(x, beta) : orthant === 1 ? carrierAt(M_PI - x, beta) : orthant === 2 ? -carrierAt(x - M_PI, beta) : -carrierAt(M_2PI - x, beta);
    return orthant <= 1 ? modulate(sineVal, sawVal) + 1 : -modulate(sawVal, sineVal) + 1;
  }
  d.carrier.angleFrequency = es.baseWaveAngleFrequency;
  d.carrier.time = d.baseWave.time;
  const sineVal = baseWaveform(d, phase, ip);
  let carrierVal = carrierWaveform(d, pm.PulseCount * RawX);
  const dipolar = pulseData(es, 'Dipolar');
  carrierVal *= dipolar !== -1 ? dipolar : 0.5;
  return modulate(sineVal, carrierVal + 0.5) + modulate(sineVal, carrierVal - 0.5);
}

/** the CHM / SHE table of the current pulse mode (GetCustomPwm; none loaded → the mode is silent, as in the simulator) */
function customPwmOf(d: Domain) {
  const es = d.es, pm = es.pattern!.PulseMode;
  if (d.customPwmFor !== pm || d.customPwmLevel !== es.pwmLevel) {
    d.customPwmFor = pm;
    d.customPwmLevel = es.pwmLevel;
    d.customPwmNow = d.customPwm[customPwmName(es.pwmLevel, pm.PulseType, pm.PulseCount, pm.Alternative)];
  }
  return d.customPwmNow;
}

/** CalculatePhsaseState: the three legs' levels (0…2) into d.U / d.V / d.W, then the motor runs one step */
export function calculatePhaseState(d: Domain, ip: number) {
  const es = d.es;
  let U = 0, V = 0, W = 0;
  if (!es.isNone && !es.isZeroOutput) {
    const type = es.pattern!.PulseMode.PulseType;
    if (es.pwmLevel === 2) {
      if (type === 'ASYNC') {
        d.carrier.processCarrierFrequency(d.t, es);
        const c = carrierWaveform(d, d.carrier.phase);
        U = modulate(baseWaveform(d, 0, ip), c) * 2;
        V = modulate(baseWaveform(d, 1, ip), c) * 2;
        W = modulate(baseWaveform(d, 2, ip), c) * 2;
      } else if (type === 'SYNC') {
        U = l2Sync(d, ip, 0);
        V = l2Sync(d, ip, 1);
        W = l2Sync(d, ip, 2);
      } else if (type === 'HO') {
        U = l2Ho(d, ip, 0);
        V = l2Ho(d, ip, 1);
        W = l2Ho(d, ip, 2);
      } else if (type === 'ΔΣ') {
        U = l2DeltaSigma(d, ip, 0);
        V = l2DeltaSigma(d, ip, 1);
        W = l2DeltaSigma(d, ip, 2);
      } else {
        // CHM / SHE (FromCustomPwm)
        const t = customPwmOf(d);
        if (t) {
          const m = es.baseWaveAmplitude!;
          U = t.getPwm(m, baseWaveX(d, 0, ip));
          V = t.getPwm(m, baseWaveX(d, 1, ip));
          W = t.getPwm(m, baseWaveX(d, 2, ip));
        }
      }
    } else {
      if (type === 'ASYNC') {
        d.carrier.processCarrierFrequency(d.t, es);
        let c = carrierWaveform(d, d.carrier.phase);
        const dipolar = pulseData(es, 'Dipolar');
        c *= dipolar !== -1 ? dipolar : 0.5;
        let b = baseWaveform(d, 0, ip);
        U = modulate(b, c + 0.5) + modulate(b, c - 0.5);
        b = baseWaveform(d, 1, ip);
        V = modulate(b, c + 0.5) + modulate(b, c - 0.5);
        b = baseWaveform(d, 2, ip);
        W = modulate(b, c + 0.5) + modulate(b, c - 0.5);
      } else if (type === 'SYNC') {
        U = l3Sync(d, ip, 0);
        V = l3Sync(d, ip, 1);
        W = l3Sync(d, ip, 2);
      } else {
        const t = customPwmOf(d);
        if (t) {
          const m = es.baseWaveAmplitude!;
          U = t.getPwm(m, baseWaveX(d, 0, ip));
          V = t.getPwm(m, baseWaveX(d, 1, ip));
          W = t.getPwm(m, baseWaveX(d, 2, ip));
        }
      }
    }
  }
  d.U = U;
  d.V = V;
  d.W = W;
  d.motor.process(d.t - d.lastT, es.baseWaveAngleFrequency, U, V, W);
}

// ======================================================================= in-train sound (TrainSound/Audio.cs)

export interface HarmonicData {
  Harmonic: number;
  Amplitude: { Start: number; StartValue: number; End: number; EndValue: number; MinimumValue: number; MaximumValue: number };
  Range: { Start: number; End: number };
  Disappear: number;
}

/** Data/TrainAudio/Struct (the parts the sound uses; the impulse response is applied by the caller) */
export interface TrainAudio {
  motor: MotorSpec;
  GearSound: HarmonicData[];
  HarmonicSound: HarmonicData[];
  MotorVolumeDb: number;
  TotalVolumeDb: number;
}

export const defaultTrainAudio = (): TrainAudio => ({ motor: { ...DEFAULT_MOTOR }, GearSound: [], HarmonicSound: [], MotorVolumeDb: -2.0, TotalVolumeDb: 0.0 });

/** Struct.SetCalculatedGearHarmonic: gear whine from the tooth counts (gear1 = pinion) */
export function calculatedGearHarmonics(audio: TrainAudio, gear1: number, gear2: number) {
  const rotation = 120 / Math.pow(2, audio.motor.Np) / 60.0;
  const harmonic = [((9.0 * 2 * gear1) / gear2) * 189.0 / 225, (9.0 * 2 * gear1) / gear2, 9.0, 1.0];
  audio.GearSound = harmonic.map((h, i) => ({
    Harmonic: rotation * gear1 * h,
    Amplitude: { Start: 0, StartValue: 0x0, End: 40, EndValue: 0.1 * Math.pow(1.4, -i), MinimumValue: 0, MaximumValue: 0.1 },
    Range: { Start: 0, End: -1 },
    Disappear: -1,
  }));
}

function harmonicSounds(d: Domain, harmonics: HarmonicData[]) {
  const bw = d.baseWave;
  const f = bw.frequency;
  let sound = 0;
  for (let i = 0; i < harmonics.length; i++) {
    const h = harmonics[i];
    const a = h.Amplitude;
    if (h.Range.Start > f) continue;
    if (h.Range.End >= 0 && h.Range.End < f) continue;
    const harmonicFreq = h.Harmonic * f;
    if (h.Disappear !== -1 && harmonicFreq > h.Disappear) continue;
    let sineVal = Math.sin(bw.time * bw.angleFrequency * h.Harmonic);
    let amplitude = a.StartValue + ((a.EndValue - a.StartValue) / (a.End - a.Start)) * (f - a.Start);
    if (amplitude > a.MaximumValue) amplitude = a.MaximumValue;
    if (amplitude < a.MinimumValue) amplitude = a.MinimumValue;
    const disappear = harmonicFreq + 100.0 > h.Disappear ? (h.Disappear - harmonicFreq) / 100.0 : 1;
    sineVal *= amplitude * (h.Disappear === -1 ? 1 : disappear);
    sound += sineVal;
  }
  return sound;
}

/**
 * CalculateTrainSound: motor torque ripple + motor and gear harmonics (one sample; before the impulse response).
 * `teScale` scales the ripple (a per-sample difference: rate / 192000 keeps its level at other sampling rates).
 */
export function trainSoundSample(d: Domain, audio: TrainAudio, teScale = 1) {
  calculatePhaseState(d, 0);
  const motorPwmSound = d.motor.diffTe * teScale * gainOf(audio.MotorVolumeDb);
  const motorSound = audio.HarmonicSound.length ? harmonicSounds(d, audio.HarmonicSound) : 0;
  const gearSound = audio.GearSound.length ? harmonicSounds(d, audio.GearSound) : 0;
  return (motorPwmSound + motorSound + gearSound) * gainOf(audio.TotalVolumeDb);
}

/** Math.pow(10, db) of the last few volumes (the simulator's "dB" are powers of ten) */
let gainDb0 = NaN, gain0 = 0, gainDb1 = NaN, gain1 = 0;
function gainOf(db: number) {
  if (db === gainDb0) return gain0;
  if (db === gainDb1) return gain1;
  gainDb1 = gainDb0;
  gain1 = gain0;
  gainDb0 = db;
  gain0 = Math.pow(10, db);
  return gain0;
}

/** the inverter's line voltage (U − V) / 2, as the simulator's real-time "VVVF" sound */
export function lineVoltageSample(d: Domain) {
  calculatePhaseState(d, 0);
  return (d.U - d.V) * 0.5;
}

// ======================================================================= real-time control (Generation/Audio/RealTime.cs)

export interface Mascon {
  /** base frequency change rate (rad/s²: the controller's notch × 2π × Hz/s) */
  FrequencyChangeRate: number;
  IsBraking: boolean;
  /** power off (neutral notch) */
  IsFreeRunning: boolean;
}

/** RealTimeFrequencyControl: the simulator's own driving (a master controller changing the frequency) */
export function realTimeFrequencyControl(d: Domain, m: Mascon, dt: number, data: VvvfData) {
  d.brake = m.IsBraking;
  d.powerOff = m.IsFreeRunning;
  const bw = d.baseWave;
  let angleFrequency = bw.angleFrequency;
  angleFrequency += m.FrequencyChangeRate * dt;
  if (angleFrequency < 0) angleFrequency = 0;
  if (!d.freeRun) {
    if (d.allowBaseWaveTimeChange && angleFrequency !== 0) bw.time *= bw.angleFrequency / angleFrequency;
    bw.angleFrequency = angleFrequency;
    d.controlFrequency = bw.frequency;
  }
  d.processControlParameter(dt, data.JerkSetting);
}

/**
 * The game's driving: the base (inverter output) frequency follows the train's speed instead of a notch's rate.
 * Unlike RealTimeFrequencyControl it moves while the control frequency runs free too (the train keeps rolling
 * while the inverter ramps), keeping the phase continuous the same way.
 */
export function gameFrequencyControl(d: Domain, baseHz: number, braking: boolean, powerOff: boolean, dt: number, data: VvvfData) {
  d.brake = braking;
  d.powerOff = powerOff;
  const bw = d.baseWave;
  const angleFrequency = Math.max(0, M_2PI * baseHz);
  if (d.allowBaseWaveTimeChange && angleFrequency !== 0) bw.time *= bw.angleFrequency / angleFrequency;
  bw.angleFrequency = angleFrequency;
  if (!d.freeRun) d.controlFrequency = bw.frequency;
  d.processControlParameter(dt, data.JerkSetting);
}
