/**
 * Synthesised running sound of the cockroach (joke entry): the patter of six legs (a loop of dry ticks played
 * faster with speed, turning into a rattle), a wing-like buzz that rises with speed and a rush of air. `speed`
 * below is the share of the top speed (motor rpm / redline: one fixed ratio).
 */
export class BugSound {
  private ctx: BaseAudioContext;
  readonly out: GainNode;
  private ticks: AudioBufferSourceNode;
  private tickGain: GainNode;
  private buzz: OscillatorNode;
  private buzzGain: GainNode;
  private buzzFilter: BiquadFilterNode;
  private air: AudioBufferSourceNode;
  private airGain: GainNode;
  private airFilter: BiquadFilterNode;

  constructor(ctx: BaseAudioContext, noise: AudioBuffer, destination: AudioNode) {
    this.ctx = ctx;
    this.out = ctx.createGain();
    this.out.gain.value = 0;
    this.out.connect(destination);
    // one second of footfalls: 12 short clicks, slightly uneven like six legs in two tripods
    const rate = ctx.sampleRate;
    const buf = ctx.createBuffer(1, rate, rate);
    const d = buf.getChannelData(0);
    for (let k = 0; k < 12; k++) {
      const at = Math.floor(((k + (k % 2) * 0.18) / 12) * rate);
      const amp = 0.55 + 0.45 * ((k * 7) % 5) / 4;
      const len = Math.floor(rate * 0.006);
      for (let i = 0; i < len && at + i < d.length; i++) {
        const env = Math.exp(-i / (len * 0.25));
        d[at + i] += (Math.random() * 2 - 1) * env * amp;
      }
    }
    this.ticks = ctx.createBufferSource();
    this.ticks.buffer = buf;
    this.ticks.loop = true;
    const tickFilter = ctx.createBiquadFilter();
    tickFilter.type = 'highpass';
    tickFilter.frequency.value = 1800;
    this.tickGain = ctx.createGain();
    this.tickGain.gain.value = 0;
    this.ticks.connect(tickFilter).connect(this.tickGain).connect(this.out);
    this.ticks.start();
    this.buzz = ctx.createOscillator();
    this.buzz.type = 'sawtooth';
    this.buzz.start();
    this.buzzFilter = ctx.createBiquadFilter();
    this.buzzFilter.type = 'bandpass';
    this.buzzFilter.Q.value = 3;
    this.buzzGain = ctx.createGain();
    this.buzzGain.gain.value = 0;
    this.buzz.connect(this.buzzFilter).connect(this.buzzGain).connect(this.out);
    this.air = ctx.createBufferSource();
    this.air.buffer = noise;
    this.air.loop = true;
    this.airFilter = ctx.createBiquadFilter();
    this.airFilter.type = 'bandpass';
    this.airGain = ctx.createGain();
    this.airGain.gain.value = 0;
    this.air.connect(this.airFilter).connect(this.airGain).connect(this.out);
    this.air.start();
  }

  update(rpm: number, throttle: number, _boost: number, volume: number, redline: number) {
    const t = this.ctx.currentTime;
    const speed = Math.min(1.1, Math.abs(rpm) / redline);
    this.out.gain.setTargetAtTime(volume, t, 0.05);
    // footfalls: 12 per buffer second at rate 1; up to ~70 a second (a rattle), pitched up with it
    this.ticks.playbackRate.setTargetAtTime(Math.max(0.05, Math.min(6, speed * 14)), t, 0.05);
    this.tickGain.gain.setTargetAtTime(Math.min(1, speed * 25) * (0.18 + 0.12 * throttle), t, 0.05);
    // the buzz comes in from ~60 km/h
    const f = 90 + speed * 260;
    this.buzz.frequency.setTargetAtTime(f, t, 0.05);
    this.buzzFilter.frequency.setTargetAtTime(f * 2.5, t, 0.05);
    this.buzzGain.gain.setTargetAtTime(Math.max(0, Math.min(1, (speed - 0.12) * 3)) * (0.025 + 0.025 * throttle), t, 0.08);
    this.airFilter.frequency.setTargetAtTime(400 + speed * 2400, t, 0.1);
    this.airGain.gain.setTargetAtTime(Math.min(1, speed * 2) * 0.1, t, 0.1);
  }

  /** no turbo */
  blowOff() {
    return false;
  }

  dispose() {
    this.ticks.stop();
    this.buzz.stop();
    this.air.stop();
    this.out.disconnect();
  }
}
