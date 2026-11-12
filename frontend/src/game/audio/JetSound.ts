/**
 * A fighter's engines for the game: the controller of the AudioWorklet 'jet' (jet.ts: fan whine by the spool, exhaust
 * roar by the thrust, afterburner thump and crackle), with the same face as the other vehicles' sounds. The node
 * joins once its module is loaded (`setNode`); until then, and where AudioWorklet is missing, a plain stand-in
 * sounds: a whine and filtered noise that follow the spool.
 *
 * The simulation's "rpm" of a jet is its core speed in % × 100 (6500 at idle, 10000 at military power, up to 10200
 * in full afterburner: `VehicleSim.jetEngines`), from which spool and afterburner are read back here.
 */
export class JetSound {
  private ctx: BaseAudioContext;
  readonly out: GainNode;
  private node: AudioWorkletNode | null = null;
  private far = 0;
  // the stand-in
  private whine: OscillatorNode;
  private whineGain: GainNode;
  private roar: AudioBufferSourceNode;
  private roarFilter: BiquadFilterNode;
  private roarGain: GainNode;

  constructor(ctx: BaseAudioContext, noise: AudioBuffer, destination: AudioNode) {
    this.ctx = ctx;
    this.out = ctx.createGain();
    this.out.gain.value = 0;
    this.out.connect(destination);
    this.whine = ctx.createOscillator();
    this.whine.type = 'sine';
    this.whineGain = ctx.createGain();
    this.whineGain.gain.value = 0;
    this.whine.connect(this.whineGain).connect(this.out);
    this.whine.start();
    this.roar = ctx.createBufferSource();
    this.roar.buffer = noise;
    this.roar.loop = true;
    this.roarFilter = ctx.createBiquadFilter();
    this.roarFilter.type = 'lowpass';
    this.roarFilter.Q.value = 0.5;
    this.roarGain = ctx.createGain();
    this.roarGain.gain.value = 0;
    this.roar.connect(this.roarFilter).connect(this.roarGain).connect(this.out);
    this.roar.start();
  }

  /** the worklet's node takes over from the stand-in */
  setNode(node: AudioWorkletNode) {
    this.node = node;
    node.connect(this.out);
    const t = this.ctx.currentTime;
    this.whineGain.gain.setTargetAtTime(0, t, 0.05);
    this.roarGain.gain.setTargetAtTime(0, t, 0.05);
  }

  /** how far the aircraft is from the listener (m): its take-off is heard going away */
  distance(d: number) {
    this.far = Math.max(0, d);
  }

  update(rpm: number, _throttle: number, _boost: number, volume: number, _redline?: number, _brake?: number) {
    const t = this.ctx.currentTime;
    const spool = Math.min(1, Math.max(0, (rpm - 6500) / 3500));
    const ab = Math.min(1, Math.max(0, (rpm - 10000) / 200));
    this.out.gain.setTargetAtTime(1, t, 0.05);
    const n = this.node;
    if (n) {
      n.parameters.get('spool')!.setValueAtTime(spool, t);
      n.parameters.get('afterburner')!.setValueAtTime(ab, t);
      n.parameters.get('level')!.setValueAtTime(Math.min(1, Math.max(0, volume)), t);
      n.parameters.get('distance')!.setValueAtTime(this.far, t);
      return;
    }
    const near = volume / (1 + this.far / 70);
    this.whine.frequency.setTargetAtTime(950 + 3600 * spool, t, 0.05);
    this.whineGain.gain.setTargetAtTime(0.02 * (1 - 0.6 * spool) * near, t, 0.05);
    this.roarFilter.frequency.setTargetAtTime(300 + 900 * spool, t, 0.1);
    this.roarGain.gain.setTargetAtTime((0.03 + 0.25 * spool * spool + 0.3 * ab) * near, t, 0.08);
  }

  /** no turbocharger */
  blowOff() {
    return false;
  }

  dispose() {
    this.node?.port.postMessage('stop');
    this.node?.disconnect();
    this.whine.stop();
    this.roar.stop();
    this.out.disconnect();
  }
}
