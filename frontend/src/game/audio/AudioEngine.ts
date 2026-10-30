import { clamp } from '../util/math';

/** Synthesised engine/tyre/wind audio built with WebAudio nodes only. */
export class EngineSound {
  private ctx: AudioContext;
  readonly out: GainNode;
  private oscs: OscillatorNode[] = [];
  private oscGains: GainNode[] = [];
  private filter: BiquadFilterNode;
  private shaper: WaveShaperNode;
  private intake: AudioBufferSourceNode;
  private intakeGain: GainNode;
  private intakeFilter: BiquadFilterNode;
  private whistle: OscillatorNode | null = null;
  private whistleGain: GainNode | null = null;
  private lastThrottle = 0;
  private lastBoost = 0;

  constructor(ctx: AudioContext, private cylinders: number, turbo: boolean, noise: AudioBuffer, destination: AudioNode) {
    this.ctx = ctx;
    this.out = ctx.createGain();
    this.out.gain.value = 0;
    this.out.connect(destination);
    this.filter = ctx.createBiquadFilter();
    this.filter.type = 'lowpass';
    this.filter.Q.value = 2.5;
    this.shaper = ctx.createWaveShaper();
    this.shaper.curve = makeDistortion(cylinders >= 6 ? 6 : 12);
    this.shaper.connect(this.filter);
    this.filter.connect(this.out);
    // harmonics: half order (lumpy rumble), firing order, 2x, 3x
    const mix = [0.35, 0.55, 0.28, 0.12];
    const types: OscillatorType[] = ['sawtooth', 'sawtooth', 'square', 'sawtooth'];
    for (let i = 0; i < 4; i++) {
      const o = ctx.createOscillator();
      o.type = types[i];
      const g = ctx.createGain();
      g.gain.value = mix[i];
      o.connect(g).connect(this.shaper);
      o.start();
      this.oscs.push(o);
      this.oscGains.push(g);
    }
    this.intake = ctx.createBufferSource();
    this.intake.buffer = noise;
    this.intake.loop = true;
    this.intakeFilter = ctx.createBiquadFilter();
    this.intakeFilter.type = 'bandpass';
    this.intakeFilter.Q.value = 0.8;
    this.intakeGain = ctx.createGain();
    this.intakeGain.gain.value = 0;
    this.intake.connect(this.intakeFilter).connect(this.intakeGain).connect(this.out);
    this.intake.start();
    if (turbo) {
      this.whistle = ctx.createOscillator();
      this.whistle.type = 'sine';
      this.whistleGain = ctx.createGain();
      this.whistleGain.gain.value = 0;
      this.whistle.connect(this.whistleGain).connect(destination);
      this.whistle.start();
    }
  }

  update(rpm: number, throttle: number, boost: number, volume: number, redline: number) {
    const t = this.ctx.currentTime;
    const fire = (rpm / 60) * (this.cylinders / 2);
    const ratios = [0.5, 1, 2, 3];
    this.oscs.forEach((o, i) => o.frequency.setTargetAtTime(fire * ratios[i] * (1 + i * 0.003), t, 0.015));
    const load = 0.35 + throttle * 0.65;
    const rn = rpm / redline;
    this.filter.frequency.setTargetAtTime(400 + rn * 2600 * (0.5 + throttle * 0.6), t, 0.03);
    this.out.gain.setTargetAtTime(volume * (0.16 + load * 0.2) * (0.6 + rn * 0.5), t, 0.03);
    this.intakeFilter.frequency.setTargetAtTime(600 + rn * 2400, t, 0.05);
    this.intakeGain.gain.setTargetAtTime(throttle * rn * 0.55, t, 0.05);
    if (this.whistle && this.whistleGain) {
      this.whistle.frequency.setTargetAtTime(1800 + boost * 3600 + rn * 400, t, 0.05);
      this.whistleGain.gain.setTargetAtTime(volume * boost * throttle * 0.035, t, 0.08);
    }
    this.lastThrottle = throttle;
    this.lastBoost = boost;
  }

  /** True when a blow-off "pssh" should play (throttle lifted on boost). */
  blowOff(throttle: number, boost: number) {
    return !!this.whistle && this.lastThrottle > 0.6 && throttle < 0.2 && this.lastBoost > 0.6 && boost > 0.5;
  }

  dispose() {
    this.oscs.forEach((o) => o.stop());
    this.intake.stop();
    this.whistle?.stop();
    this.out.disconnect();
  }
}

function makeDistortion(k: number) {
  const n = 1024;
  const curve = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    const x = (i * 2) / n - 1;
    curve[i] = ((3 + k) * x * 20 * (Math.PI / 180)) / (Math.PI + k * Math.abs(x));
  }
  return curve;
}

export class AudioEngine {
  readonly ctx: AudioContext;
  readonly master: GainNode;
  readonly sfx: GainNode;
  readonly music: GainNode;
  private noise: AudioBuffer;
  private squeal: { src: AudioBufferSourceNode; gain: GainNode; filter: BiquadFilterNode };
  private wind: { gain: GainNode; filter: BiquadFilterNode };
  private engines = new Map<string, EngineSound>();
  private musicNodes: AudioNode[] = [];

  constructor() {
    const Ctx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    this.ctx = new Ctx();
    this.master = this.ctx.createGain();
    const comp = this.ctx.createDynamicsCompressor();
    comp.threshold.value = -14;
    comp.ratio.value = 4;
    this.master.connect(comp).connect(this.ctx.destination);
    this.sfx = this.ctx.createGain();
    this.sfx.connect(this.master);
    this.music = this.ctx.createGain();
    this.music.gain.value = 0.5;
    this.music.connect(this.master);
    this.noise = this.makeNoise();

    const src = this.ctx.createBufferSource();
    src.buffer = this.noise;
    src.loop = true;
    const filter = this.ctx.createBiquadFilter();
    filter.type = 'bandpass';
    filter.frequency.value = 1300;
    filter.Q.value = 7;
    const peak = this.ctx.createBiquadFilter();
    peak.type = 'peaking';
    peak.frequency.value = 2600;
    peak.gain.value = 9;
    const gain = this.ctx.createGain();
    gain.gain.value = 0;
    src.connect(filter).connect(peak).connect(gain).connect(this.sfx);
    src.start();
    this.squeal = { src, gain, filter };

    const wsrc = this.ctx.createBufferSource();
    wsrc.buffer = this.noise;
    wsrc.loop = true;
    const wf = this.ctx.createBiquadFilter();
    wf.type = 'lowpass';
    wf.frequency.value = 500;
    const wg = this.ctx.createGain();
    wg.gain.value = 0;
    wsrc.connect(wf).connect(wg).connect(this.sfx);
    wsrc.start();
    this.wind = { gain: wg, filter: wf };
  }

  private makeNoise() {
    const len = this.ctx.sampleRate * 2;
    const buf = this.ctx.createBuffer(1, len, this.ctx.sampleRate);
    const d = buf.getChannelData(0);
    for (let i = 0; i < len; i++) d[i] = Math.random() * 2 - 1;
    return buf;
  }

  resume() {
    if (this.ctx.state !== 'running') void this.ctx.resume();
  }

  setVolumes(master: number, sfx: number, music: number) {
    this.master.gain.value = master;
    this.sfx.gain.value = sfx;
    this.music.gain.value = music;
  }

  engine(id: string, cylinders: number, turbo: boolean) {
    let e = this.engines.get(id);
    if (!e) {
      e = new EngineSound(this.ctx, cylinders, turbo, this.noise, this.sfx);
      this.engines.set(id, e);
    }
    return e;
  }

  removeEngine(id: string) {
    this.engines.get(id)?.dispose();
    this.engines.delete(id);
  }

  removeAllEngines() {
    for (const id of [...this.engines.keys()]) this.removeEngine(id);
  }

  updateTyres(skid: number, speed: number) {
    const t = this.ctx.currentTime;
    const amt = clamp(skid, 0, 1) * clamp(speed / 8, 0, 1);
    this.squeal.gain.gain.setTargetAtTime(amt * 0.32, t, 0.04);
    this.squeal.filter.frequency.setTargetAtTime(1000 + amt * 700 + Math.sin(t * 13) * 60, t, 0.05);
  }

  updateWind(speed: number) {
    const t = this.ctx.currentTime;
    this.wind.gain.gain.setTargetAtTime(clamp(speed / 60, 0, 1) ** 2 * 0.22, t, 0.1);
    this.wind.filter.frequency.setTargetAtTime(300 + speed * 18, t, 0.1);
  }

  silenceDriving() {
    const t = this.ctx.currentTime;
    this.squeal.gain.gain.setTargetAtTime(0, t, 0.05);
    this.wind.gain.gain.setTargetAtTime(0, t, 0.1);
  }

  /** Noise burst + low thump. */
  impact(strength: number) {
    const t = this.ctx.currentTime;
    const src = this.ctx.createBufferSource();
    src.buffer = this.noise;
    const f = this.ctx.createBiquadFilter();
    f.type = 'lowpass';
    f.frequency.value = 900;
    const g = this.ctx.createGain();
    g.gain.setValueAtTime(0.8 * strength, t);
    g.gain.exponentialRampToValueAtTime(0.001, t + 0.35);
    src.connect(f).connect(g).connect(this.sfx);
    src.start(t, Math.random(), 0.4);
    const o = this.ctx.createOscillator();
    o.frequency.setValueAtTime(90, t);
    o.frequency.exponentialRampToValueAtTime(35, t + 0.25);
    const og = this.ctx.createGain();
    og.gain.setValueAtTime(0.7 * strength, t);
    og.gain.exponentialRampToValueAtTime(0.001, t + 0.3);
    o.connect(og).connect(this.sfx);
    o.start(t);
    o.stop(t + 0.32);
  }

  blowOff() {
    const t = this.ctx.currentTime;
    const src = this.ctx.createBufferSource();
    src.buffer = this.noise;
    const f = this.ctx.createBiquadFilter();
    f.type = 'highpass';
    f.frequency.value = 2500;
    const g = this.ctx.createGain();
    g.gain.setValueAtTime(0.25, t);
    g.gain.exponentialRampToValueAtTime(0.001, t + 0.45);
    src.connect(f).connect(g).connect(this.sfx);
    src.start(t, Math.random(), 0.5);
  }

  /** Short UI tone. */
  beep(freq: number, dur = 0.12, type: OscillatorType = 'sine', vol = 0.25) {
    const t = this.ctx.currentTime;
    const o = this.ctx.createOscillator();
    o.type = type;
    o.frequency.value = freq;
    const g = this.ctx.createGain();
    g.gain.setValueAtTime(0, t);
    g.gain.linearRampToValueAtTime(vol, t + 0.01);
    g.gain.exponentialRampToValueAtTime(0.001, t + dur);
    o.connect(g).connect(this.master);
    o.start(t);
    o.stop(t + dur + 0.02);
  }

  chime(notes: number[], spacing = 0.09) {
    notes.forEach((n, i) => setTimeout(() => this.beep(n, 0.35, 'triangle', 0.18), i * spacing * 1000));
  }

  private tracks = new Map<string, AudioBuffer | null>();
  private current: { name: string; src: AudioBufferSourceNode; gain: GainNode } | null = null;

  /** Load an optional music file; resolves to null when it is not shipped. */
  private async loadTrack(name: string): Promise<AudioBuffer | null> {
    if (this.tracks.has(name)) return this.tracks.get(name)!;
    let buf: AudioBuffer | null = null;
    try {
      const res = await fetch(`/audio/${name}.mp3`);
      const type = res.headers.get('content-type') ?? '';
      if (res.ok && !type.includes('text/html')) buf = await this.ctx.decodeAudioData(await res.arrayBuffer());
    } catch {
      buf = null;
    }
    this.tracks.set(name, buf);
    return buf;
  }

  /**
   * Play a looping music track (crossfade). Falls back to the synthesised pad for
   * the menu theme when no file is present; races are silent music-wise then.
   */
  async playMusic(name: 'bgm_menu' | 'bgm_race' | null) {
    if (this.current?.name === name) return;
    const t = this.ctx.currentTime;
    if (this.current) {
      const old = this.current;
      old.gain.gain.setTargetAtTime(0, t, 0.6);
      setTimeout(() => old.src.stop(), 3000);
      this.current = null;
    }
    if (!name) {
      this.stopAmbient();
      return;
    }
    const buf = await this.loadTrack(name);
    if (!buf) {
      if (name === 'bgm_menu') this.startAmbient();
      else this.stopAmbient();
      return;
    }
    this.stopAmbient();
    const src = this.ctx.createBufferSource();
    src.buffer = buf;
    src.loop = true;
    const gain = this.ctx.createGain();
    gain.gain.setValueAtTime(0, this.ctx.currentTime);
    gain.gain.linearRampToValueAtTime(name === 'bgm_race' ? 0.55 : 0.7, this.ctx.currentTime + 1.5);
    src.connect(gain).connect(this.music);
    src.start();
    this.current = { name, src, gain };
  }

  /** Slow evolving pad for menus (no assets needed). */
  startAmbient() {
    if (this.musicNodes.length) return;
    const t = this.ctx.currentTime;
    const chord = [110, 164.81, 207.65, 246.94, 329.63];
    const filter = this.ctx.createBiquadFilter();
    filter.type = 'lowpass';
    filter.frequency.value = 900;
    const g = this.ctx.createGain();
    g.gain.setValueAtTime(0, t);
    g.gain.linearRampToValueAtTime(0.09, t + 3);
    filter.connect(g).connect(this.music);
    const lfo = this.ctx.createOscillator();
    lfo.frequency.value = 0.07;
    const lfoGain = this.ctx.createGain();
    lfoGain.gain.value = 400;
    lfo.connect(lfoGain).connect(filter.frequency);
    lfo.start();
    this.musicNodes.push(lfo, g);
    for (const f of chord) {
      for (const det of [-6, 6]) {
        const o = this.ctx.createOscillator();
        o.type = 'sawtooth';
        o.frequency.value = f;
        o.detune.value = det;
        const og = this.ctx.createGain();
        og.gain.value = 0.12;
        o.connect(og).connect(filter);
        o.start();
        this.musicNodes.push(o);
      }
    }
  }

  stopAmbient() {
    const t = this.ctx.currentTime;
    for (const n of this.musicNodes) {
      if (n instanceof GainNode) n.gain.setTargetAtTime(0, t, 0.5);
    }
    const nodes = this.musicNodes;
    this.musicNodes = [];
    setTimeout(() => nodes.forEach((n) => (n instanceof OscillatorNode ? n.stop() : n.disconnect())), 2500);
  }
}
