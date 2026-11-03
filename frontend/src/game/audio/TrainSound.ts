import type { MotorKind } from '../vehicle/trains';

/**
 * Synthesised traction sound of a train (joke entries): gear whine and rolling rumble rise with speed; under power
 * or braking the equipment sings: a VVVF inverter's carrier (asynchronous at a fixed pitch, then synchronous modes
 * that step down through 27/15/9/5/3 pulses: the rising-and-dropping whine), a chopper's steady tone, or the growl
 * of DC motors on resistance control. `speed` below is the motor speed as a share of the design top speed.
 */
export class TrainSound {
  private ctx: AudioContext;
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

  constructor(ctx: AudioContext, private kind: MotorKind, noise: AudioBuffer, destination: AudioNode) {
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

  update(rpm: number, throttle: number, _boost: number, volume: number, redline: number, brake = 0) {
    const t = this.ctx.currentTime;
    const speed = Math.min(1.2, Math.abs(rpm) / redline);
    // motor electrical frequency (4-pole motor) and the gear mesh (15-tooth pinion)
    const fOut = (Math.abs(rpm) / 60) * 2;
    const mesh = (Math.abs(rpm) / 60) * 15;
    this.load += ((Math.max(throttle, brake * 0.8) > 0.05 ? 1 : 0) - this.load) * 0.2;
    const lv = this.load * Math.min(1, speed * 12);
    this.out.gain.setTargetAtTime(volume, t, 0.05);
    this.gear.frequency.setTargetAtTime(Math.max(20, mesh), t, 0.02);
    this.gearGain.gain.setTargetAtTime(Math.min(1, speed * 4) * (0.03 + 0.05 * lv), t, 0.05);
    const dc = this.kind === 'resistor' || this.kind === 'chopper';
    this.motor.frequency.setTargetAtTime(Math.max(20, dc ? fOut * 2 : fOut), t, 0.02);
    this.motorFilter.frequency.setTargetAtTime(300 + speed * (dc ? 1800 : 900), t, 0.05);
    this.motorGain.gain.setTargetAtTime(lv * (dc ? 0.12 : 0.06), t, 0.05);
    const f = this.carrier(speed, fOut);
    if (f > 0) {
      this.inv.frequency.setTargetAtTime(f, t, 0.008);
      this.invFilter.frequency.setTargetAtTime(f, t, 0.008);
    }
    const invLevel = this.kind === 'sic' ? 0.035 : this.kind === 'chopper' ? 0.02 : 0.06;
    this.invGain.gain.setTargetAtTime(f > 0 ? lv * invLevel : 0, t, 0.03);
    this.rollFilter.frequency.setTargetAtTime(200 + speed * 900, t, 0.1);
    this.rollGain.gain.setTargetAtTime(Math.min(1, speed * 3) * 0.12, t, 0.1);
  }

  /** no turbo */
  blowOff() {
    return false;
  }

  dispose() {
    for (const o of [this.gear, this.motor, this.inv]) o.stop();
    this.roll.stop();
    this.out.disconnect();
  }
}
