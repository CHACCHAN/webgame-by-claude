import { clamp } from '../util/math';
import type { CarSpec } from '../vehicle/carSpecs';
import { TrainSound } from './TrainSound';
import { BugSound } from './BugSound';

interface LoopConfig {
  volume: number;
  /** where each repeat starts (s): skip quiet intros */
  loopFrom: number;
  /** where the crossfade into the next repeat begins (s): before fade-outs */
  loopAt?: number;
  xfade: number;
  fadeIn: number;
}
const DEFAULT_LOOP: LoopConfig = { volume: 0.6, loopFrom: 0, xfade: 3, fadeIn: 1.5 };
/**
 * Per-track loop points of the delivered files (all normalised to -15.4 LUFS): pairs of moments whose next
 * seconds sound alike (spectral self-similarity), moved onto the same beat phase so the kicks of both passes
 * coincide during the crossfade. Tracks whose sections never repeat closely get longer crossfades.
 */
const RACE = { volume: 0.5, xfade: 1.5, fadeIn: 0.8 };
const MUSIC: Record<string, Partial<LoopConfig>> = {
  bgm_menu: { volume: 0.6, loopFrom: 55.77, loopAt: 184.62, xfade: 4 },
  bgm_garage: { volume: 0.55, loopFrom: 9.57, loopAt: 141.8, xfade: 2 },
  bgm_online: { volume: 0.6, loopFrom: 23.59, loopAt: 99.38, xfade: 2 },
  bgm_results: { volume: 0.55, loopFrom: 18.76, loopAt: 136.51, xfade: 3, fadeIn: 2 },
  bgm_race: { ...RACE, loopFrom: 59.49, loopAt: 176.79 },
  bgm_race_kirifuri: { ...RACE, loopFrom: 4.5, loopAt: 184.83, xfade: 2 },
  bgm_race_tenrou: { ...RACE, loopFrom: 50.43, loopAt: 185.33 },
  bgm_race_rain: { ...RACE, loopFrom: 49.69, loopAt: 145.98 },
  bgm_race_dawn: { ...RACE, loopFrom: 59.26, loopAt: 159.83, xfade: 2 },
  bgm_rival: { ...RACE, loopFrom: 71.14, loopAt: 163.75, xfade: 2 },
  bgm_ghost: { ...RACE, loopFrom: 73.84, loopAt: 184.94 },
};

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

  update(rpm: number, throttle: number, boost: number, volume: number, redline: number, _brake = 0) {
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
  private engines = new Map<string, (EngineSound | TrainSound | BugSound) & { kind: string }>();
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

  /** The running sound of a vehicle: a synthesised engine, a train's traction equipment or a creature's legs. */
  engine(id: string, spec: CarSpec): EngineSound | TrainSound | BugSound {
    const e = this.engines.get(id);
    if (e && e.kind === spec.id) return e;
    if (e) this.removeEngine(id);
    const sound = spec.train
      ? this.trainSound(spec)
      : spec.creature
        ? new BugSound(this.ctx, this.noise, this.sfx)
        : new EngineSound(this.ctx, spec.engine.cylinders, spec.engine.turbo, this.noise, this.sfx);
    this.engines.set(id, Object.assign(sound, { kind: spec.id }));
    return sound;
  }

  /** A train's traction sound; its recording (if any) joins once decoded. */
  private trainSound(spec: CarSpec) {
    const t = spec.train!;
    const sound = new TrainSound(this.ctx, t.sound, this.noise, this.sfx, t.vmax);
    const rec = t.motorSound;
    if (rec) void this.loadTrack(rec.file).then((buffer) => buffer && sound.setRecording(buffer, rec.knots, rec.gain));
    return sound;
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

  private rainGain: GainNode | null = null;
  /** Rain ambience: hiss + low rumble from filtered noise. */
  setRain(level: number) {
    if (!this.rainGain) {
      const src = this.ctx.createBufferSource();
      src.buffer = this.noise;
      src.loop = true;
      const hp = this.ctx.createBiquadFilter();
      hp.type = 'bandpass';
      hp.frequency.value = 5200;
      hp.Q.value = 0.5;
      const lp = this.ctx.createBiquadFilter();
      lp.type = 'lowpass';
      lp.frequency.value = 9000;
      this.rainGain = this.ctx.createGain();
      this.rainGain.gain.value = 0;
      src.connect(hp).connect(lp).connect(this.rainGain).connect(this.sfx);
      src.start();
    }
    this.rainGain.gain.setTargetAtTime(level * 0.16, this.ctx.currentTime, 0.5);
  }

  silenceDriving() {
    const t = this.ctx.currentTime;
    this.squeal.gain.gain.setTargetAtTime(0, t, 0.05);
    this.wind.gain.gain.setTargetAtTime(0, t, 0.1);
    this.scrapeGain?.gain.setTargetAtTime(0, t, 0.05);
  }

  private scrapeGain: GainNode | null = null;

  /** Continuous metal-on-metal scrape while two cars rub (0 = silent). */
  scrape(level: number) {
    if (!this.scrapeGain) {
      if (level <= 0) return;
      const src = this.ctx.createBufferSource();
      src.buffer = this.noise;
      src.loop = true;
      const bp = this.ctx.createBiquadFilter();
      bp.type = 'bandpass';
      bp.frequency.value = 2600;
      bp.Q.value = 0.9;
      const g = this.ctx.createGain();
      g.gain.value = 0;
      src.connect(bp).connect(g).connect(this.sfx);
      src.start();
      this.scrapeGain = g;
    }
    this.scrapeGain.gain.setTargetAtTime(level * 0.3, this.ctx.currentTime, 0.04);
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

  /** Exhaust backfire: a sharp crack and a short low pop. */
  backfire(strength: number) {
    const t = this.ctx.currentTime;
    const src = this.ctx.createBufferSource();
    src.buffer = this.noise;
    const f = this.ctx.createBiquadFilter();
    f.type = 'bandpass';
    f.frequency.value = 1300 + Math.random() * 500;
    f.Q.value = 0.8;
    const g = this.ctx.createGain();
    g.gain.setValueAtTime(0.9 * strength, t);
    g.gain.exponentialRampToValueAtTime(0.001, t + 0.09);
    src.connect(f).connect(g).connect(this.sfx);
    src.start(t, Math.random(), 0.12);
    const o = this.ctx.createOscillator();
    o.type = 'triangle';
    o.frequency.setValueAtTime(150, t);
    o.frequency.exponentialRampToValueAtTime(48, t + 0.08);
    const og = this.ctx.createGain();
    og.gain.setValueAtTime(0.55 * strength, t);
    og.gain.exponentialRampToValueAtTime(0.001, t + 0.1);
    o.connect(og).connect(this.sfx);
    o.start(t);
    o.stop(t + 0.12);
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

  /** Pace-note beeps before a bend: one for a medium corner, two for a tight one, three for a hairpin. */
  cornerWarning(kind: 'hairpin' | 'tight' | 'medium') {
    const n = kind === 'hairpin' ? 3 : kind === 'tight' ? 2 : 1;
    const freq = kind === 'medium' ? 784 : 988;
    const t0 = this.ctx.currentTime + 0.01;
    for (let i = 0; i < n; i++) {
      const t = t0 + i * 0.13;
      const o = this.ctx.createOscillator();
      o.type = 'square';
      o.frequency.value = freq;
      const lp = this.ctx.createBiquadFilter();
      lp.type = 'lowpass';
      lp.frequency.value = 2400;
      const g = this.ctx.createGain();
      g.gain.setValueAtTime(0, t);
      g.gain.linearRampToValueAtTime(0.16, t + 0.008);
      g.gain.setValueAtTime(0.16, t + 0.07);
      g.gain.exponentialRampToValueAtTime(0.001, t + 0.11);
      o.connect(lp).connect(g).connect(this.sfx);
      o.start(t);
      o.stop(t + 0.13);
    }
  }

  chime(notes: number[], spacing = 0.09) {
    notes.forEach((n, i) => setTimeout(() => this.beep(n, 0.35, 'triangle', 0.18), i * spacing * 1000));
  }

  private tracks = new Map<string, Promise<AudioBuffer | null>>();
  private current: { name: string; voices: { src: AudioBufferSourceNode; gain: GainNode }[]; timer: number } | null = null;

  /** Load an optional audio file from /audio; resolves to null when it is not shipped. */
  private loadTrack(name: string): Promise<AudioBuffer | null> {
    let p = this.tracks.get(name);
    if (!p) {
      p = (async () => {
        try {
          const res = await fetch(`/audio/${name}.mp3`);
          const type = res.headers.get('content-type') ?? '';
          if (!res.ok || type.includes('text/html')) return null;
          return await this.ctx.decodeAudioData(await res.arrayBuffer());
        } catch {
          return null;
        }
      })();
      this.tracks.set(name, p);
    }
    return p;
  }

  /** Warm the decode cache (call during loading screens). */
  preload(...names: string[]) {
    for (const n of names) void this.loadTrack(n);
  }

  /**
   * Play a looping music track. Instead of a hard loop, each pass crossfades into
   * the next one at the track's loop point, which hides intros, fade-outs and MP3
   * padding. Falls back to the synthesised pad for menus when no file exists. `delay` (s) leaves room
   * for a jingle before the track fades in.
   */
  async playMusic(name: string | null, { fallback, delay = 0 }: { fallback?: string; delay?: number } = {}) {
    if (this.current?.name === name) return;
    this.stopMusic(1.2);
    if (!name) return;
    // a decoded 3-minute track takes ~75 MB: keep only the one asked for (the stopped one plays out its fade)
    for (const k of this.tracks.keys()) if (k.startsWith('bgm_') && k !== name && k !== fallback) this.tracks.delete(k);
    let track = name;
    let buf = await this.loadTrack(name);
    if (!buf && fallback) buf = await this.loadTrack((track = fallback));
    if (this.current) return; // another track was requested meanwhile
    if (!buf) {
      if (name.startsWith('bgm_menu')) this.startAmbient();
      return;
    }
    this.stopAmbient();
    const cfg = { ...DEFAULT_LOOP, ...MUSIC[track] };
    const loopAt = Math.min(cfg.loopAt ?? buf.duration - 3, buf.duration - cfg.xfade);
    const state = { name, voices: [] as { src: AudioBufferSourceNode; gain: GainNode }[], timer: 0 };
    this.current = state;
    const voice = (when: number, offset: number, fadeIn: number) => {
      const src = this.ctx.createBufferSource();
      src.buffer = buf!;
      const gain = this.ctx.createGain();
      gain.gain.setValueAtTime(0, when);
      gain.gain.linearRampToValueAtTime(cfg.volume, when + fadeIn);
      src.connect(gain).connect(this.music);
      src.start(when, offset);
      state.voices.push({ src, gain });
      // schedule the crossfade into the next pass
      const passEnd = when + (loopAt - offset);
      const lead = Math.max(0.1, passEnd - this.ctx.currentTime - 1.5);
      state.timer = window.setTimeout(() => {
        if (this.current !== state) return;
        gain.gain.setValueAtTime(cfg.volume, passEnd);
        gain.gain.linearRampToValueAtTime(0, passEnd + cfg.xfade);
        src.stop(passEnd + cfg.xfade + 0.05);
        state.voices = state.voices.filter((v) => v.src !== src);
        voice(passEnd, cfg.loopFrom, cfg.xfade);
      }, lead * 1000);
    };
    voice(this.ctx.currentTime + 0.05 + delay, 0, cfg.fadeIn);
  }

  stopMusic(fade = 1) {
    const cur = this.current;
    if (!cur) {
      this.stopAmbient();
      return;
    }
    this.current = null;
    clearTimeout(cur.timer);
    const t = this.ctx.currentTime;
    for (const v of cur.voices) {
      v.gain.gain.cancelScheduledValues(t);
      v.gain.gain.setValueAtTime(v.gain.gain.value, t);
      v.gain.gain.linearRampToValueAtTime(0, t + fade);
      v.src.stop(t + fade + 0.05);
    }
  }

  /** One-shot music sting (e.g. crossing the finish line). Resolves to its length (s), 0 when not shipped. */
  async playJingle(name: string, volume = 0.8) {
    const buf = await this.loadTrack(name);
    if (!buf) return 0;
    const src = this.ctx.createBufferSource();
    src.buffer = buf;
    const g = this.ctx.createGain();
    g.gain.value = volume;
    src.connect(g).connect(this.music);
    src.start();
    return buf.duration;
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
