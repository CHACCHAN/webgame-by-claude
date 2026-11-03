import type { MotorKind } from '../vehicle/trains';
import { vvvfDrive, type TrainVvvf } from '../vehicle/vvvf';
import { RecordingFollower, RunningLoop } from './TrainRecordings';
import { SIM_RATE, type VvvfDrive } from './vvvf/engine';

/**
 * The VVVF in-train sound after the simulator's impulse response, whose body resonance (150–350 Hz, ~25 dB above
 * 100 Hz and 500 Hz) makes the synchronous few-pulse modes (their 6f torque ripple sits there) ~20 dB louder than the
 * rest: a peaking cut there (dB, 0 = as the simulator), and the level (the loudest then peaks near 0.4).
 */
export const VVVF_BODY = { db: -15, hz: 230, q: 0.8 };
const VVVF_GAIN = 1.4;

/**
 * Traction sound of a train (joke entries). Always, while it moves: running noise (a recorded loop once loaded,
 * `setRunning`; else synthesised rumble). Under power or braking the equipment sings on top: a VVVF train's in-train
 * sound calculated by VVVF-Simulator's model from the inverter's control pattern (`setVvvf`: audio/vvvf, an
 * AudioWorklet, then the simulator's impulse response), or a recording of the real train pulling away followed at
 * the point matching the speed (`setRecording`, audio/TrainRecordings.ts), or until one is ready a simple synthesis:
 * carrier tones stepping through the pulse modes, a chopper's steady tone, or the growl of DC motors on resistance
 * control. `speed` below is the motor speed as a share of the design top speed.
 */
export class TrainSound {
  private ctx: BaseAudioContext;
  readonly out: GainNode;
  private gear: OscillatorNode;
  private gearGain: GainNode;
  private motor: OscillatorNode;
  private motorGain: GainNode;
  private motorFilter: BiquadFilterNode;
  private inv: OscillatorNode;
  private invGain: GainNode;
  private invFilter: BiquadFilterNode;
  private roll: AudioBufferSourceNode;
  private rollGain: GainNode;
  private rollFilter: BiquadFilterNode;
  private load = 0;
  private follower: RecordingFollower | null = null;
  private vvvf: { node: AudioWorkletNode; v: TrainVvvf; wheel: number; drive: VvvfDrive } | null = null;
  private running: RunningLoop | null = null;
  private lastT = 0;
  private disposed = false;

  constructor(ctx: BaseAudioContext, private kind: MotorKind, noise: AudioBuffer, destination: AudioNode, private vmax: number) {
    this.ctx = ctx;
    this.out = ctx.createGain();
    this.out.gain.value = 0;
    this.out.connect(destination);
    const osc = (type: OscillatorType) => {
      const o = ctx.createOscillator();
      o.type = type;
      o.start();
      return o;
    };
    this.gear = osc('sine');
    this.gearGain = ctx.createGain();
    this.gearGain.gain.value = 0;
    this.gear.connect(this.gearGain).connect(this.out);
    this.motor = osc(kind === 'resistor' || kind === 'chopper' ? 'sawtooth' : 'triangle');
    this.motorFilter = ctx.createBiquadFilter();
    this.motorFilter.type = 'lowpass';
    this.motorFilter.frequency.value = 600;
    this.motorGain = ctx.createGain();
    this.motorGain.gain.value = 0;
    this.motor.connect(this.motorFilter).connect(this.motorGain).connect(this.out);
    this.inv = osc('square');
    this.invFilter = ctx.createBiquadFilter();
    this.invFilter.type = 'bandpass';
    this.invFilter.Q.value = 6;
    this.invGain = ctx.createGain();
    this.invGain.gain.value = 0;
    this.inv.connect(this.invFilter).connect(this.invGain).connect(this.out);
    this.roll = ctx.createBufferSource();
    this.roll.buffer = noise;
    this.roll.loop = true;
    this.rollFilter = ctx.createBiquadFilter();
    this.rollFilter.type = 'lowpass';
    this.rollGain = ctx.createGain();
    this.rollGain.gain.value = 0;
    this.roll.connect(this.rollFilter).connect(this.rollGain).connect(this.out);
    this.roll.start();
  }

  /** Inverter tone (Hz) at a motor speed share, or 0 once it runs without a carrier (one pulse / no inverter). */
  private carrier(speed: number, fOut: number) {
    switch (this.kind) {
      case 'sic':
        // SiC: a soft, high asynchronous carrier almost to the top
        return speed < 0.55 ? 1000 + speed * 500 : 0;
      case 'igbt3':
        if (speed < 0.18) return 700 + speed * 1600;
        break;
      case 'igbt':
        if (speed < 0.12) return 1050;
        break;
      case 'chopper':
        return 660;
      case 'resistor':
        return 0;
    }
    for (const [upTo, pulses] of [[0.25, 27], [0.34, 15], [0.43, 9], [0.52, 5], [0.6, 3]] as const) if (speed < upTo) return fOut * pulses;
    return 0;
  }

  /** A recording of the equipment pulling away and its [seconds, km/h] speed points (vehicle/trains.ts). */
  setRecording(buffer: AudioBuffer, knots: [number, number][], gain = 1) {
    if (this.disposed) return;
    const out = this.ctx.createGain();
    out.gain.value = 0.9 * gain;
    out.connect(this.out);
    this.follower = new RecordingFollower(this.ctx, out, buffer, knots);
  }

  /**
   * The VVVF in-train sound: an AudioWorkletNode of 'vvvf-sim' (audio/vvvf/vvvf.worklet.ts) through the simulator's
   * impulse response (public/audio/vvvf-filter.wav, decoded at the context's rate).
   */
  setVvvf(node: AudioWorkletNode, ir: AudioBuffer, v: TrainVvvf, wheel: number) {
    if (this.disposed) {
      node.port.postMessage('stop');
      return;
    }
    const conv = this.ctx.createConvolver();
    conv.normalize = false;
    conv.buffer = ir;
    const body = this.ctx.createBiquadFilter();
    body.type = 'peaking';
    body.frequency.value = VVVF_BODY.hz;
    body.Q.value = VVVF_BODY.q;
    body.gain.value = VVVF_BODY.db;
    const gain = this.ctx.createGain();
    // the simulator convolves at 192 kHz: the same response at the context's rate sums proportionally fewer taps
    gain.gain.value = ((VVVF_BODY.db === 0 ? 0.35 : VVVF_GAIN) * SIM_RATE) / this.ctx.sampleRate;
    node.connect(conv).connect(body).connect(gain).connect(this.out);
    this.vvvf = { node, v, wheel, drive: { hz: 0, rotorHz: 0, braking: false, powerOff: true } };
  }

  /** speed and notch → the worklet's k-rate parameters (it smooths them itself) */
  private driveVvvf(kmh: number, notch: 1 | -1 | 0) {
    const s = this.vvvf!;
    const d = vvvfDrive(s.v, s.wheel, kmh, notch, s.drive.braking, s.drive);
    const t = this.ctx.currentTime;
    const prm = s.node.parameters;
    prm.get('hz')!.setValueAtTime(d.hz, t);
    prm.get('rotor')!.setValueAtTime(d.rotorHz, t);
    prm.get('braking')!.setValueAtTime(d.braking ? 1 : 0, t);
    prm.get('power')!.setValueAtTime(d.powerOff ? 0 : 1, t);
  }

  /** A loop of running noise (`loop`: its seamless window, s) recorded at `speed` km/h. */
  setRunning(buffer: AudioBuffer, loop: [number, number], speed: number, gain = 1) {
    if (this.disposed) return;
    this.running = new RunningLoop(this.ctx, this.out, buffer, loop, speed, 0.5 * gain);
  }

  update(rpm: number, throttle: number, _boost: number, volume: number, redline: number, brake = 0) {
    const t = this.ctx.currentTime;
    const speed = Math.min(1.2, Math.abs(rpm) / redline);
    // motor electrical frequency (4-pole motor) and the gear mesh (15-tooth pinion)
    const fOut = (Math.abs(rpm) / 60) * 2;
    const mesh = (Math.abs(rpm) / 60) * 15;
    this.load += ((Math.max(throttle, brake * 0.8) > 0.05 ? 1 : 0) - this.load) * 0.2;
    const lv = this.load * Math.min(1, speed * 12);
    this.out.gain.setTargetAtTime(volume, t, 0.05);
    const dt = Math.min(0.1, Math.max(0, t - this.lastT));
    this.lastT = t;
    const kmh = speed * this.vmax;
    // the recordings replace the synthesised motor and inverter (braking: the same equipment, a little softer)
    // and the synthesised rumble
    const recorded = !!this.follower || !!this.vvvf;
    const dir = throttle > 0.05 ? 1 : brake > 0.05 ? -1 : 0;
    this.follower?.update(kmh, dir, lv * (throttle > 0.05 ? 1 : 0.7), dt);
    if (this.vvvf) this.driveVvvf(kmh, dir);
    this.running?.update(kmh);
    this.gear.frequency.setTargetAtTime(Math.max(20, mesh), t, 0.02);
    // (the recordings carry the real gear whine)
    this.gearGain.gain.setTargetAtTime(this.running ? 0 : Math.min(1, speed * 4) * (recorded ? 0.02 : 0.03 + 0.05 * lv), t, 0.05);
    const dc = this.kind === 'resistor' || this.kind === 'chopper';
    this.motor.frequency.setTargetAtTime(Math.max(20, dc ? fOut * 2 : fOut), t, 0.02);
    this.motorFilter.frequency.setTargetAtTime(300 + speed * (dc ? 1800 : 900), t, 0.05);
    this.motorGain.gain.setTargetAtTime(recorded ? 0 : lv * (dc ? 0.12 : 0.06), t, 0.05);
    const f = this.carrier(speed, fOut);
    if (f > 0) {
      this.inv.frequency.setTargetAtTime(f, t, 0.008);
      this.invFilter.frequency.setTargetAtTime(f, t, 0.008);
    }
    const invLevel = this.kind === 'sic' ? 0.035 : this.kind === 'chopper' ? 0.02 : 0.06;
    this.invGain.gain.setTargetAtTime(f > 0 && !recorded ? lv * invLevel : 0, t, 0.03);
    this.rollFilter.frequency.setTargetAtTime(200 + speed * 900, t, 0.1);
    this.rollGain.gain.setTargetAtTime(this.running ? 0 : Math.min(1, speed * 3) * 0.12, t, 0.1);
  }

  /** no turbo */
  blowOff() {
    return false;
  }

  dispose() {
    this.disposed = true;
    this.follower?.stop();
    this.running?.stop();
    if (this.vvvf) {
      this.vvvf.node.port.postMessage('stop');
      this.vvvf.node.disconnect();
    }
    for (const o of [this.gear, this.motor, this.inv]) o.stop();
    this.roll.stop();
    this.out.disconnect();
  }
}
