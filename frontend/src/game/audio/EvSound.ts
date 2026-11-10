/**
 * Synthesised running sound of an electric car (one fixed reduction gear, `CarSpec.engine.electric`): the motors'
 * electromagnetic whine (an order of the motor speed), the reduction gear's mesh an octave and a fifth above, both
 * louder under load and quieter (a little lower) while regenerating, and a faint, fixed inverter tone. Tyres and wind
 * come from the shared tyre / wind sounds.
 */
export class EvSound {
  private ctx: BaseAudioContext;
  readonly out: GainNode;
  private motor: OscillatorNode;
  private motorGain: GainNode;
  private gear: OscillatorNode;
  private gearGain: GainNode;
  private inverter: OscillatorNode;
  private inverterGain: GainNode;
  private hum: AudioBufferSourceNode;
  private humGain: GainNode;
  private humFilter: BiquadFilterNode;

  /** `orders`: whine orders of the motor speed (motor, gear mesh); `inverter`: switching tone (Hz) */
  constructor(ctx: BaseAudioContext, noise: AudioBuffer, destination: AudioNode, private orders: [number, number] = [6, 17], inverter = 9200) {
    this.ctx = ctx;
    this.out = ctx.createGain();
    this.out.gain.value = 0;
    this.out.connect(destination);
    const tone = (type: OscillatorType) => {
      const o = ctx.createOscillator();
      o.type = type;
      const g = ctx.createGain();
      g.gain.value = 0;
      o.connect(g).connect(this.out);
      o.start();
      return [o, g] as const;
    };
    [this.motor, this.motorGain] = tone('triangle');
    [this.gear, this.gearGain] = tone('sine');
    [this.inverter, this.inverterGain] = tone('sine');
    this.inverter.frequency.value = inverter;
    // a low, rough hum of the drive under load (the reduction gear and the body)
    this.hum = ctx.createBufferSource();
    this.hum.buffer = noise;
    this.hum.loop = true;
    this.humFilter = ctx.createBiquadFilter();
    this.humFilter.type = 'bandpass';
    this.humFilter.Q.value = 2;
    this.humGain = ctx.createGain();
    this.humGain.gain.value = 0;
    this.hum.connect(this.humFilter).connect(this.humGain).connect(this.out);
    this.hum.start();
  }

  update(rpm: number, throttle: number, _boost: number, volume: number, redline: number, brake = 0) {
    const t = this.ctx.currentTime;
    const turn = Math.abs(rpm) / 60;
    const rn = Math.min(1.1, Math.abs(rpm) / redline);
    // pulling, or regenerating (lifted off or braking: less, and the pitch sags a little)
    const regen = throttle < 0.05 ? Math.min(1, 0.35 + brake) : 0;
    const load = Math.max(throttle, regen * 0.45);
    const sag = 1 - regen * 0.03;
    this.out.gain.setTargetAtTime(volume, t, 0.05);
    this.motor.frequency.setTargetAtTime(Math.max(20, turn * this.orders[0] * sag), t, 0.02);
    this.gear.frequency.setTargetAtTime(Math.max(20, turn * this.orders[1] * sag), t, 0.02);
    // audible from walking pace, fading a little at the top where the wind drowns it
    const onset = Math.min(1, rn * 12);
    this.motorGain.gain.setTargetAtTime(onset * (0.025 + 0.06 * load) * (1 - 0.3 * rn), t, 0.05);
    this.gearGain.gain.setTargetAtTime(onset * (0.008 + 0.02 * load), t, 0.05);
    this.inverterGain.gain.setTargetAtTime(0.004 + 0.006 * load, t, 0.1);
    this.humFilter.frequency.setTargetAtTime(90 + rn * 260, t, 0.1);
    this.humGain.gain.setTargetAtTime(Math.min(1, rn * 6) * 0.05 * (0.4 + load), t, 0.1);
  }

  /** no turbo */
  blowOff() {
    return false;
  }

  dispose() {
    this.motor.stop();
    this.gear.stop();
    this.inverter.stop();
    this.hum.stop();
    this.out.disconnect();
  }
}
