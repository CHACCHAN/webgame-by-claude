// VVVF inverter sound (audio/TrainSound.ts): the line-to-line voltage of a 2- or 3-level PWM inverter, made the way
// the inverter makes it: two phase references (sines at the output frequency, 120° apart, scaled by the modulation
// index) compared with a triangle carrier, either free-running (asynchronous, with optional random modulation of
// its frequency) or locked to the output (synchronous N-pulse; 1-pulse = square). 4x oversampled against aliasing.
// Parameters: freq (inverter output Hz), carrier (Hz, asynchronous), amp (modulation index). Port messages:
// { pulses: 0 (asynchronous) | N, level: 2 | 3, random: Hz }.
const TAU = Math.PI * 2;
const OS = 4;

class VvvfProcessor extends AudioWorkletProcessor {
  static get parameterDescriptors() {
    return [
      { name: 'freq', defaultValue: 0, minValue: 0, automationRate: 'k-rate' },
      { name: 'carrier', defaultValue: 1000, minValue: 0, automationRate: 'k-rate' },
      { name: 'amp', defaultValue: 0, minValue: 0, automationRate: 'k-rate' },
    ];
  }

  constructor() {
    super();
    this.theta = 0;
    this.carrierPhase = 0;
    this.pulses = 0;
    this.level = 2;
    this.random = 0;
    this.offset = 0;
    this.untilNext = 0;
    this.port.onmessage = (e) => Object.assign(this, e.data);
  }

  /** one inverter leg: +1 / 0 / -1 */
  leg(ref, tri) {
    if (this.pulses === 1) return ref >= 0 ? 1 : -1;
    if (this.level === 3) {
      // two level-shifted carriers: (0..1) above, (-1..0) below
      const c = (tri + 1) / 2;
      return ref > c ? 1 : ref < c - 1 ? -1 : 0;
    }
    return ref > tri ? 1 : -1;
  }

  process(_inputs, outputs, params) {
    const out = outputs[0][0];
    const f = params.freq[0], fc = params.carrier[0], m = params.amp[0];
    const dt = 1 / (sampleRate * OS);
    for (let i = 0; i < out.length; i++) {
      // random carrier modulation: a new offset every 0.2 ms
      if (--this.untilNext <= 0) {
        this.offset = this.random ? (Math.random() * 2 - 1) * this.random : 0;
        this.untilNext = Math.max(1, Math.round(sampleRate * 0.0002));
      }
      let acc = 0;
      for (let k = 0; k < OS; k++) {
        this.theta += TAU * f * dt;
        if (this.theta >= TAU) this.theta -= TAU;
        let phase;
        if (this.pulses > 0) {
          // synchronous: N carrier periods per output period, a carrier peak at the reference's zero crossing
          phase = ((this.theta / TAU) * this.pulses + 0.25) % 1;
        } else {
          this.carrierPhase += Math.max(0, fc + this.offset) * dt;
          if (this.carrierPhase >= 1) this.carrierPhase -= Math.floor(this.carrierPhase);
          phase = this.carrierPhase;
        }
        const tri = phase < 0.5 ? 4 * phase - 1 : 3 - 4 * phase;
        acc += this.leg(m * Math.sin(this.theta), tri) - this.leg(m * Math.sin(this.theta - TAU / 3), tri);
      }
      out[i] = (acc / OS) * 0.5;
    }
    return true;
  }
}

registerProcessor('vvvf', VvvfProcessor);
