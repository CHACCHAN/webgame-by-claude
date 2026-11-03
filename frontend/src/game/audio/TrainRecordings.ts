/**
 * Recorded train sounds played by speed (audio/TrainSound.ts): a recording of the equipment pulling away followed
 * continuously at the point matching the speed, and a loop of running noise.
 */

/** crossfade (s) when the recording is re-cued */
const XFADE = 0.45;
/** re-cue when the playing point is this far (s) from the one matching the speed */
const DRIFT = 0.9;

interface Voice {
  src: AudioBufferSourceNode;
  gain: GainNode;
  /** 1: the recording forwards (power), -1: backwards (braking: the same sounds, speed falling) */
  dir: 1 | -1;
  /** position in the playing buffer (s) */
  pos: number;
  rate: number;
  /** time (s) it has been silent: power cut for a moment keeps it running, faded */
  idle: number;
}

/**
 * The motor: one voice plays the recording continuously; its rate sets the pitch to the speed (the recording's
 * pitch at that point times speed over its speed there), so it follows any acceleration, and a crossfade re-cues it
 * when it has drifted away (a different acceleration, a stop). Past the recorded top speed it loops the last
 * stretch, pitched up; braking plays the recording backwards.
 */
export class RecordingFollower {
  private voice: Voice | null = null;
  private rev: AudioBuffer | null = null;

  constructor(
    private ctx: AudioContext,
    private out: AudioNode,
    private buffer: AudioBuffer,
    /** [seconds into the recording, km/h], rising */
    private knots: [number, number][],
  ) {}

  /** recording time at a speed, clamped to the recorded range */
  private timeAt(kmh: number) {
    const k = this.knots;
    if (kmh <= k[0][1]) return k[0][0];
    for (let i = 1; i < k.length; i++) {
      if (kmh <= k[i][1]) return k[i - 1][0] + ((k[i][0] - k[i - 1][0]) * (kmh - k[i - 1][1])) / (k[i][1] - k[i - 1][1]);
    }
    return k[k.length - 1][0];
  }

  /** speed at a recording time */
  private speedAt(t: number) {
    const k = this.knots;
    if (t <= k[0][0]) return k[0][1];
    for (let i = 1; i < k.length; i++) {
      if (t <= k[i][0]) return k[i - 1][1] + ((k[i][1] - k[i - 1][1]) * (t - k[i - 1][0])) / (k[i][0] - k[i - 1][0]);
    }
    return k[k.length - 1][1];
  }

  private reversed() {
    if (!this.rev) {
      const b = this.buffer;
      this.rev = this.ctx.createBuffer(1, b.length, b.sampleRate);
      const s = b.getChannelData(0), d = this.rev.getChannelData(0);
      for (let i = 0, n = b.length; i < n; i++) d[i] = s[n - 1 - i];
    }
    return this.rev;
  }

  /** forward recording time of a voice */
  private time(v: Voice) {
    return v.dir === 1 ? v.pos : this.buffer.duration - v.pos;
  }

  private cue(dir: 1 | -1, t: number, rate: number, level: number) {
    const now = this.ctx.currentTime;
    this.fade();
    const src = this.ctx.createBufferSource();
    src.buffer = dir === 1 ? this.buffer : this.reversed();
    src.playbackRate.value = rate;
    const gain = this.ctx.createGain();
    gain.gain.setValueAtTime(0, now);
    gain.gain.linearRampToValueAtTime(level, now + XFADE);
    src.connect(gain).connect(this.out);
    const pos = Math.max(0, dir === 1 ? t : this.buffer.duration - t);
    src.start(now, pos);
    src.onended = () => gain.disconnect();
    this.voice = { src, gain, dir, pos, rate, idle: 0 };
  }

  /** Let the playing voice die away. */
  private fade() {
    const v = this.voice;
    if (!v) return;
    const now = this.ctx.currentTime;
    v.gain.gain.cancelScheduledValues(now);
    v.gain.gain.setValueAtTime(v.gain.gain.value, now);
    v.gain.gain.linearRampToValueAtTime(0, now + XFADE);
    v.src.stop(now + XFADE + 0.05);
    this.voice = null;
  }

  /** `dir` 1 under power, -1 braking, 0 silent; `level` its loudness. */
  update(kmh: number, dir: 1 | -1 | 0, level: number, dt: number) {
    if (dir === 0 || level < 0.01 || (dir === -1 && kmh < 3)) {
      // silent: fade but keep playing for a moment (a throttle eased off and on again would re-cue every time)
      const v = this.voice;
      if (!v) return;
      v.pos += v.rate * dt;
      v.idle += dt;
      if (v.idle > 1.5 || v.pos > this.buffer.duration - 0.1) return this.fade();
      v.gain.gain.setTargetAtTime(0, this.ctx.currentTime, 0.1);
      return;
    }
    const k = this.knots;
    const [tTop, vTop] = k[k.length - 1];
    // past the recorded top speed the last 3 s loop, pitched up
    const beyond = kmh > vTop;
    const target = beyond ? tTop - 1.5 : this.timeAt(kmh);
    let v = this.voice;
    // how far the speed is ahead of the playing point (s of recording, in the direction it plays)
    let ahead = 0;
    if (v) {
      v.pos += v.rate * dt;
      const t = this.time(v);
      ahead = (target - t) * dir;
      const loopOut = beyond && dir === 1 && t > tTop;
      const ended = dir === -1 ? t <= k[0][0] : v.pos > this.buffer.duration - 0.1;
      if (v.dir !== dir || loopOut || ended || (!beyond && Math.abs(ahead) > DRIFT)) v = null;
      else ahead = 0;
    }
    // pitch to the speed: the recording's pitch at the playing point scaled by speed over its speed there; a little
    // faster or slower to catch up with the point matching the speed (a train accelerating unlike the recording)
    const here = v ? this.speedAt(this.time(v)) : beyond ? vTop : kmh;
    const pitch = kmh < 8 || here < 8 ? 1 : Math.min(beyond ? 2 : 1.35, Math.max(0.75, kmh / here));
    const lag = v && !beyond ? (target - this.time(v)) * dir : 0;
    const rate = pitch * Math.min(1.2, Math.max(0.9, 1 + 0.4 * lag));
    if (!v) {
      // re-cued for drifting: a little beyond the matching point, in the direction the speed is running away
      const lead = Math.sign(ahead) * Math.min(0.4, Math.abs(ahead)) * dir;
      this.cue(dir, beyond ? tTop - 3 : target + lead, rate, level);
      return;
    }
    v.rate = rate;
    v.idle = 0;
    const now = this.ctx.currentTime;
    v.src.playbackRate.setTargetAtTime(rate, now, 0.05);
    v.gain.gain.setTargetAtTime(level, now, 0.08);
  }

  stop() {
    this.fade();
  }
}

/** Running noise (wheels, rails, under-floor rumble): a seamless loop, its rate and loudness following the speed. */
export class RunningLoop {
  private src: AudioBufferSourceNode;
  private gain: GainNode;

  constructor(
    private ctx: AudioContext,
    out: AudioNode,
    buffer: AudioBuffer,
    loop: [number, number],
    /** speed of the recording (km/h) */
    private speed: number,
    private level = 1,
  ) {
    this.src = ctx.createBufferSource();
    this.src.buffer = buffer;
    this.src.loop = true;
    [this.src.loopStart, this.src.loopEnd] = loop;
    this.gain = ctx.createGain();
    this.gain.gain.value = 0;
    this.src.connect(this.gain).connect(out);
    this.src.start(0, loop[0]);
  }

  update(kmh: number) {
    const now = this.ctx.currentTime;
    this.src.playbackRate.setTargetAtTime(Math.min(2.2, Math.max(0.25, kmh / this.speed)), now, 0.1);
    const t = Math.min(1, Math.max(0, (kmh - 2) / 40));
    this.gain.gain.setTargetAtTime(this.level * t * t * (3 - 2 * t), now, 0.15);
  }

  stop() {
    this.src.stop();
    this.gain.disconnect();
  }
}
