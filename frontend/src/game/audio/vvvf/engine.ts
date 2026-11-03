/**
 * The in-train sound of a VVVF train as the game drives it: VVVF-Simulator's calculation (sim.ts) run at about
 * 192 kHz (the simulator's real-time rate: `oversample` × the output rate), its control state updated every
 * 128 output frames (512 calculations at 192 kHz, as the simulator's real-time mode) from the train's speed instead
 * of a notch's rate, and decimated to the output rate through a windowed-sinc low-pass. The simulator's impulse
 * response (Filter.wav) is applied after this by a ConvolverNode (audio/TrainSound.ts) or by the render tool.
 * DOM-free: runs in the AudioWorklet (vvvf.worklet.ts) and in Node (tools/vvvf-train-wav.ts, tests).
 */
import type { VvvfData } from './data';
import { M_2PI } from './math';
import { Domain, analyze, gameFrequencyControl, trainSoundSample, type MotorSpec, type Rng, type TrainAudio } from './sim';

/** frames per control block (the AudioWorklet's render quantum) */
export const BLOCK = 128;
/** the simulator's real-time sampling rate */
export const SIM_RATE = 192000;

/** what the game sets (main thread → worklet) */
export interface VvvfDrive {
  /** inverter output (base wave) frequency, Hz */
  hz: number;
  /** the motor's electrical rotor frequency from the wheels, Hz (hz − rotorHz = the slip) */
  rotorHz: number;
  /** brake pattern (kept while coasting after a brake application, as the simulator's notch N) */
  braking: boolean;
  /** gates off: the voltage ramps down at the pattern's jerk rate (coasting) */
  powerOff: boolean;
}

/** the oversampling for an output rate: about the simulator's 192 kHz unless capped (slow devices) */
export function oversampleFor(sampleRate: number, max = 4) {
  return Math.max(1, Math.min(max, Math.round(SIM_RATE / sampleRate)));
}

/** Kaiser-windowed sinc low-pass for `os`× decimation: −6 dB at 0.46 of the output rate, ~70 dB stop band. */
export function decimationFilter(os: number) {
  if (os <= 1) return new Float64Array([1]);
  const taps = 32 * os + 1;
  const fc = 0.46 / os;
  const beta = 6.8;
  const i0 = (x: number) => {
    let sum = 1, term = 1;
    for (let k = 1; k < 30; k++) {
      term *= (x / (2 * k)) ** 2;
      sum += term;
    }
    return sum;
  };
  const h = new Float64Array(taps);
  const m = (taps - 1) / 2;
  let total = 0;
  for (let i = 0; i < taps; i++) {
    const x = i - m;
    const sinc = x === 0 ? 2 * fc : Math.sin(2 * Math.PI * fc * x) / (Math.PI * x);
    const r = x / m;
    h[i] = sinc * (i0(beta * Math.sqrt(Math.max(0, 1 - r * r))) / i0(beta));
    total += h[i];
  }
  for (let i = 0; i < taps; i++) h[i] /= total;
  return h;
}

export class VvvfEngine {
  readonly d: Domain;
  readonly os: number;
  /** the time constant (s) the base frequency follows the game's value with (it arrives once per frame) */
  smoothing = 0.04;
  readonly drive: VvvfDrive = { hz: 0, rotorHz: 0, braking: false, powerOff: true };
  private hz = 0;
  private rotor = 0;
  private readonly dt: number;
  private readonly teScale: number;
  private readonly h: Float64Array;
  /** the last taps' calculations, twice over (a window never wraps) */
  private readonly ring: Float64Array;
  private pos = 0;

  constructor(
    readonly data: VvvfData,
    readonly audio: TrainAudio,
    readonly sampleRate: number,
    oversample = oversampleFor(sampleRate),
    rng: Rng = Math.random,
    /** the rotor turns with the wheels (else, as in the simulator, it runs free on its own torque) */
    readonly pinRotor = true,
  ) {
    this.os = oversample;
    // the train's mass turns the motor: its speed follows the wheels, not its own torque
    const motor: MotorSpec = pinRotor ? { ...audio.motor, Inertia: 1e9 } : audio.motor;
    this.d = new Domain(motor, rng);
    this.dt = 1 / (sampleRate * oversample);
    // the ripple is a per-sample difference (∝ dt): at another rate it scales back to the simulator's 192 kHz
    this.teScale = 1 / (SIM_RATE * this.dt);
    this.h = decimationFilter(oversample);
    this.ring = new Float64Array(this.h.length * 2);
    this.silent = audio.GearSound.length === 0 && audio.HarmonicSound.length === 0;
  }

  /** no sound but the motor's (no gear or harmonic tones): it may skip the calculation while the gates are off */
  private readonly silent: boolean;

  /** Fill `out` (a multiple of BLOCK frames, or any length: the control state moves every BLOCK frames). */
  process(out: Float32Array) {
    for (let start = 0; start < out.length; start += BLOCK) this.block(out, start, Math.min(BLOCK, out.length - start));
  }

  private block(out: Float32Array, start: number, frames: number) {
    const d = this.d, os = this.os, dt = this.dt, h = this.h, ring = this.ring, n = h.length;
    const blockDt = frames * os * dt;
    const k = Math.min(1, blockDt / this.smoothing);
    const dr = this.drive;
    this.hz += (Math.max(0, dr.hz) - this.hz) * k;
    const rotor0 = this.rotor;
    this.rotor += (Math.max(0, dr.rotorHz) - this.rotor) * k;
    gameFrequencyControl(d, this.hz, dr.braking, dr.powerOff, blockDt, this.data);
    analyze(d, this.data);
    const m = d.motor;
    // gates off and the motor's currents gone: silence without the calculation (coasting, standing)
    if (this.silent && (d.es.isNone || d.es.isZeroOutput) && Math.abs(m.ids) + Math.abs(m.iqs) + Math.abs(m.ird) + Math.abs(m.irq) < 1e-6) {
      out.fill(0, start, start + frames);
      ring.fill(0);
      d.addTimeAll(blockDt);
      if (this.pinRotor) m.wr = M_2PI * this.rotor;
      return;
    }
    // the rotor's speed moves smoothly across the block
    const wr0 = M_2PI * rotor0, dwr = (M_2PI * (this.rotor - rotor0)) / (frames * os);
    let s = 0;
    for (let f = 0; f < frames; f++) {
      for (let i = 0; i < os; i++) {
        if (this.pinRotor) m.wr = wr0 + dwr * s++;
        d.addTimeAll(dt);
        const v = trainSoundSample(d, this.audio, this.teScale);
        ring[this.pos] = v;
        ring[this.pos + n] = v;
        if (++this.pos === n) this.pos = 0;
      }
      // the newest calculation sits at pos − 1: the window is ring[pos … pos + n − 1], oldest first
      let acc = 0;
      for (let j = 0, p = this.pos; j < n; j++, p++) acc += h[j] * ring[p];
      out[start + f] = acc;
    }
  }
}
