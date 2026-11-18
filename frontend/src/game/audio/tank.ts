/**
 * A tank's sound, synthesised (no recordings), DOM-free: the same code runs in the AudioWorklet 'tank'
 * (tank.worklet.ts) and in Node (tools/tank-wav.ts renders and measures it), and the gun's shot and a shell's
 * burst are made here as plain sample arrays (`gunShot`, `shellBurst`: AudioEngine plays them from buffers).
 *
 * The running sound, heard from behind and above (the chase camera) or from the hatch:
 *   - a diesel (`engine: 'diesel'`): one pressure pulse per firing, the cylinders a little unequal (the half
 *     orders that make a big diesel lumpy), through the exhaust's low resonance; the combustion's knock, a burst of
 *     noise with every firing, strongest at idle; the gear train's and fans' broadband mechanical noise; the
 *     turbochargers' whistle with the load;
 *   - the M1's gas turbine (`'turbine'`): the compressor's whine (two tones that beat, and the tone an octave
 *     below), the hiss of the intake and the low roar of the exhaust through the recuperator: it hardly changes
 *     with the load, only with the gas generator's speed, and has no firing order at all;
 *   - tracks: every link meets the ground and the sprocket, `speed / pitch` times a second (60–130 Hz at speed), as
 *     clanks of the two tracks left and right, each with its own phase; the road wheels' rumble; in a turn the
 *     squeal of pins and pads;
 *   - wheels (the 16式): the block tread's hum and the tyres' roar.
 * `distance` (m from the listener) takes level and treble away.
 * Estimates throughout: resonances, link pitches and levels are set by ear and against the measurements
 * `tools/tank-wav.ts` prints (idle ≈ −31, full power at speed ≈ −20 dBFS RMS); they are not figures of the vehicles.
 */
export interface TankSoundParams {
  engine: 'diesel' | 'turbine';
  /** a diesel's cylinders */
  cylinders: number;
  /** engine speed at idle and at its rated power (rpm) */
  idle: number;
  rated: number;
  /** a track link's length (m); 0 = wheels */
  pitch: number;
}

/** overall level */
const MASTER = 0.42;
const TAU = Math.PI * 2;

export class Noise {
  private s: number;
  constructor(seed: number) {
    this.s = seed >>> 0 || 1;
  }
  /** white, −1…1 */
  next() {
    let x = this.s;
    x ^= x << 13;
    x ^= x >>> 17;
    x ^= x << 5;
    this.s = x >>> 0;
    return this.s / 2147483648 - 1;
  }
}

/** a state-variable filter (trapezoidal): stays stable while its frequency moves */
export class Svf {
  private a1 = 0;
  private a2 = 0;
  private a3 = 0;
  private k = 1;
  private ic1 = 0;
  private ic2 = 0;
  lp = 0;
  bp = 0;
  hp = 0;
  set(f: number, q: number, rate: number) {
    const g = Math.tan((Math.PI * Math.min(f, rate * 0.45)) / rate);
    this.k = 1 / q;
    this.a1 = 1 / (1 + g * (g + this.k));
    this.a2 = g * this.a1;
    this.a3 = g * this.a2;
  }
  run(x: number) {
    const v3 = x - this.ic2;
    const v1 = this.a1 * this.ic1 + this.a2 * v3;
    const v2 = this.ic2 + this.a2 * this.ic1 + this.a3 * v3;
    this.ic1 = 2 * v1 - this.ic1;
    this.ic2 = 2 * v2 - this.ic2;
    this.lp = v2;
    this.bp = v1;
    this.hp = x - this.k * v1 - v2;
  }
}

/** one track: its links' clanks */
class Track {
  phase: number;
  private a = new Svf();
  private b = new Svf();
  constructor(private noise: Noise, rate: number, f1: number, f2: number) {
    this.phase = (noise.next() + 1) / 2;
    this.a.set(f1, 5, rate);
    this.b.set(f2, 7, rate);
  }
  /** `step`: links per sample; `gain`: how hard they land */
  run(step: number, gain: number) {
    this.phase += step;
    let x = 0;
    if (this.phase >= 1) {
      this.phase -= 1;
      // (no two links land alike)
      // (one sample wide: it takes this much to ring the two resonances to a clank's level)
      x = gain * 7 * (0.65 + 0.35 * this.noise.next());
    }
    this.a.run(x);
    this.b.run(x);
    return this.a.bp * 1.6 + this.b.bp;
  }
}

/** the filters' frequencies are set anew every this many samples */
const SLOW = 32;

export class TankSynth {
  /** engine speed (rpm), the load (0…1: the throttle), the speed over the ground (m/s), how hard it turns (0…1) */
  rpm: number;
  load = 0;
  speed = 0;
  turn = 0;
  /** 0…1 */
  level = 1;
  /** m from the listener */
  distance = 0;

  private noise: Noise;
  private gains: number[] = [];
  private cyc = 0;
  private rev = 0;
  private boost = 0;
  private loadS = 0;
  private speedS = 0;
  private turnS = 0;
  private levelS = 0;
  private tick = 0;
  private exhaust = new Svf();
  private knock = new Svf();
  private mech = new Svf();
  private pWhistle = 0;
  private pWhine = 0;
  private pWhine2 = 0;
  private pSub = 0;
  private hiss = new Svf();
  private roar = new Svf();
  private wander = 0;
  private left: Track;
  private right: Track;
  private rumble = new Svf();
  private pSqueal = 0;
  private squealF = 2100;
  private pTread = 0;
  private tyre = new Svf();
  private farL = new Svf();
  private farR = new Svf();
  private dc = 0;

  constructor(private rate: number, seed: number, private p: TankSoundParams) {
    this.noise = new Noise(seed);
    this.rpm = p.idle;
    // each cylinder a little different from the next (fixed for the engine's life)
    for (let i = 0; i < Math.max(1, p.cylinders); i++) this.gains.push(1 + 0.22 * this.noise.next());
    this.left = new Track(this.noise, rate, 410, 1320);
    this.right = new Track(this.noise, rate, 440, 1240);
    this.rumble.set(85, 0.7, rate);
    this.mech.set(650, 0.6, rate);
    this.knock.set(1900, 0.9, rate);
    this.tyre.set(800, 0.7, rate);
  }

  process(L: Float32Array, R: Float32Array) {
    const { rate, p, noise } = this;
    const n = L.length;
    const dt = 1 / rate;
    for (let i = 0; i < n; i++) {
      if (this.tick-- <= 0) {
        this.tick = SLOW;
        const k = 1 - Math.exp((-SLOW * dt) / 0.06);
        this.rev += (Math.min(1.1, Math.max(0, (this.rpm - p.idle) / Math.max(1, p.rated - p.idle))) - this.rev) * k;
        this.loadS += (Math.min(1, Math.max(0, this.load)) - this.loadS) * k;
        this.speedS += (Math.abs(this.speed) - this.speedS) * k;
        this.turnS += (Math.min(1, Math.max(0, this.turn)) - this.turnS) * (1 - Math.exp((-SLOW * dt) / 0.25));
        this.levelS += (this.level / (1 + this.distance / 50) - this.levelS) * k;
        // the chargers take their time to come up
        this.boost += (this.loadS * (0.3 + 0.7 * this.rev) - this.boost) * (1 - Math.exp((-SLOW * dt) / 0.6));
        this.wander += (noise.next() - this.wander) * 0.02;
        this.exhaust.set(150 + 330 * this.loadS + 120 * this.rev, 1.1, rate);
        this.hiss.set(2600 + 3800 * this.rev, 0.6, rate);
        this.roar.set(260 + 420 * this.rev, 0.6, rate);
        const far = 15000 / (1 + this.distance / 45);
        this.farL.set(far, 0.7, rate);
        this.farR.set(far, 0.7, rate);
        if (noise.next() > 0.96) this.squealF = 1700 + 900 * (noise.next() + 1) * 0.5;
      }
      const rev = this.rev, load = this.loadS, v = this.speedS;
      const w = noise.next();
      let eng = 0;
      if (p.engine === 'diesel') {
        const rpm = p.idle + rev * (p.rated - p.idle);
        this.cyc += (rpm / 120) * dt;
        if (this.cyc >= 1) this.cyc -= 1;
        const ph = this.cyc * p.cylinders;
        const cyl = Math.floor(ph);
        const fr = ph - cyl;
        const g = this.gains[cyl % this.gains.length];
        // the firing's pressure pulse, then its ringing down until the next
        const pulse = g * Math.exp(-fr * 5) - 0.2;
        this.exhaust.run(pulse);
        this.knock.run(w * g * Math.exp(-fr * 14));
        this.mech.run(w);
        this.pWhistle += (3200 + 8200 * this.boost) * dt;
        if (this.pWhistle >= 1) this.pWhistle -= 1;
        eng =
          this.exhaust.lp * (0.5 + 0.75 * load) * (0.6 + 0.4 * rev) +
          this.knock.bp * (0.34 - 0.16 * load) * (0.7 + 0.5 * rev) +
          this.mech.bp * (0.05 + 0.16 * rev) +
          Math.sin(this.pWhistle * TAU) * 0.035 * this.boost * this.boost;
      } else {
        // the gas generator idles at about two thirds of its speed: the whine never goes away
        const f = 2300 + 4300 * rev + 60 * this.wander;
        this.pWhine += f * dt;
        if (this.pWhine >= 1) this.pWhine -= 1;
        this.pWhine2 += f * 1.013 * dt;
        if (this.pWhine2 >= 1) this.pWhine2 -= 1;
        this.pSub += f * 0.5 * dt;
        if (this.pSub >= 1) this.pSub -= 1;
        this.hiss.run(w);
        this.roar.run(noise.next());
        eng =
          (Math.sin(this.pWhine * TAU) + 0.8 * Math.sin(this.pWhine2 * TAU) + 0.5 * Math.sin(this.pSub * TAU)) * 0.045 * (0.55 + 0.45 * rev) +
          this.hiss.hp * (0.055 + 0.11 * rev) +
          this.roar.lp * (0.5 + 1.9 * rev * (0.6 + 0.4 * load)) * (1 + 0.25 * this.wander);
      }
      let l = eng, r = eng;
      if (p.pitch > 0) {
        // the tracks: clanks from each side, the wheels' rumble under them, the squeal in a turn
        const step = (v / p.pitch) * dt;
        const gain = Math.min(1, v / 5) * (0.35 + 0.65 * Math.min(1, v / 18));
        const tl = this.left.run(step * (1 - 0.06 * this.turnS), gain);
        const tr = this.right.run(step * (1 + 0.06 * this.turnS), gain);
        this.rumble.run(noise.next());
        const rum = this.rumble.lp * 1.6 * Math.min(1, v / 14);
        this.pSqueal += this.squealF * dt;
        if (this.pSqueal >= 1) this.pSqueal -= 1;
        const sq = Math.sin(this.pSqueal * TAU) * 0.02 * this.turnS * Math.min(1, v / 3) * (0.6 + 0.4 * this.wander);
        l += tl * 0.5 + tr * 0.12 + rum + sq;
        r += tr * 0.5 + tl * 0.12 + rum + sq * 0.7;
      } else {
        // eight big tyres: the tread blocks' hum and the roar
        this.pTread += (v / 0.11) * dt;
        if (this.pTread >= 1) this.pTread -= 1;
        this.tyre.run(noise.next());
        const hum = (Math.sin(this.pTread * TAU) + 0.4 * Math.sin(this.pTread * 2 * TAU)) * 0.05 * Math.min(1, v / 12);
        const roar = this.tyre.bp * 0.22 * Math.min(1, v / 22);
        l += hum + roar;
        r += hum + roar;
      }
      // (no standing offset: the pulse train has one)
      const mid = (l + r) / 2;
      this.dc += (mid - this.dc) * 0.0006;
      this.farL.run((l - this.dc) * MASTER * this.levelS);
      this.farR.run((r - this.dc) * MASTER * this.levelS);
      L[i] = Math.tanh(this.farL.lp);
      R[i] = Math.tanh(this.farR.lp);
    }
  }
}

/**
 * A tank gun's shot as heard beside the vehicle (mono, `seconds` long at `rate`): the blast's crack, the boom
 * under it, the rush of the gas, and the roll that comes back from the hills. `calibre` (mm): a 105 sits a little
 * higher and shorter than a 125.
 */
export function gunShot(rate: number, calibre: number, seed = 1, seconds = 2.6) {
  const n = Math.round(rate * seconds);
  const out = new Float32Array(n);
  const noise = new Noise(seed);
  const k = 120 / calibre;
  const body = new Svf(), tail = new Svf(), crack = new Svf();
  crack.set(2600 * k, 0.5, rate);
  tail.set(170 * k, 0.6, rate);
  // the hills' answers: a few later, duller copies of the boom
  const echoes = [0.31, 0.47, 0.74, 1.1].map((t, i) => ({ at: Math.round((t + 0.05 * noise.next()) * rate), g: 0.2 / (1 + i * 0.7) }));
  let ph = 0;
  for (let i = 0; i < n; i++) {
    const t = i / rate;
    const w = noise.next();
    // the pressure front: there at once, gone in a few milliseconds
    crack.run(w);
    const front = (crack.hp * 0.9 + w * 0.5) * Math.exp(-t / 0.012) * Math.min(1, t / 0.0004);
    // the boom: a low tone falling as the gas spreads
    ph += ((38 + 60 * Math.exp(-t / 0.06)) * k) / rate;
    const boom = Math.sin(ph * TAU) * Math.exp(-t / 0.22) * Math.min(1, t / 0.002);
    // the gas rushing out: noise that closes down
    body.set((180 + 2400 * Math.exp(-t / 0.07)) * k, 0.7, rate);
    body.run(w);
    const rush = body.lp * 1.3 * Math.exp(-t / 0.3);
    tail.run(noise.next());
    const roll = tail.lp * 1.1 * Math.exp(-t / 0.75) * Math.min(1, t / 0.08);
    out[i] = front * 1.4 + boom * 1.1 + rush + roll;
  }
  for (const e of echoes) for (let i = n - 1; i >= e.at; i--) out[i] += out[i - e.at] * e.g;
  // (duller: an echo has lost its top)
  let lp = 0;
  for (let i = Math.round(0.25 * rate); i < n; i++) {
    lp += (out[i] - lp) * 0.2;
    out[i] = lp;
  }
  const end = Math.round(0.3 * rate);
  for (let i = 0; i < n; i++) {
    const fade = i > n - end ? (n - i) / end : 1;
    out[i] = Math.tanh(out[i] * 1.5) * 0.8 * fade;
  }
  return out;
}

/**
 * A shell's end as heard near it (mono): on the ground a thud and the earth thrown up; on a vehicle (`metal`) the
 * crack of the strike and the plate ringing. (These rounds are darts: nothing explodes.)
 */
export function shellBurst(rate: number, metal: boolean, seed = 2, seconds = 1.2) {
  const n = Math.round(rate * seconds);
  const out = new Float32Array(n);
  const noise = new Noise(seed);
  const dirt = new Svf(), snap = new Svf();
  dirt.set(metal ? 900 : 420, 0.6, rate);
  snap.set(3200, 0.6, rate);
  const partials = metal ? [[470, 0.3, 1], [1130, 0.22, 0.8], [1870, 0.15, 0.6], [2950, 0.1, 0.45], [4100, 0.06, 0.3]] : [];
  let ph = 0;
  for (let i = 0; i < n; i++) {
    const t = i / rate;
    const w = noise.next();
    snap.run(w);
    dirt.run(noise.next());
    ph += (45 + 70 * Math.exp(-t / 0.04)) / rate;
    let x = snap.hp * Math.exp(-t / 0.006) * (metal ? 1.3 : 0.7) + Math.sin(ph * TAU) * Math.exp(-t / 0.16) * (metal ? 0.6 : 1) + dirt.lp * Math.exp(-t / (metal ? 0.12 : 0.35)) * 1.2;
    for (const [f, tau, g] of partials) x += Math.sin(TAU * f * t) * Math.exp(-t / tau) * g * 0.35;
    const fade = i > n - 2000 ? (n - i) / 2000 : 1;
    out[i] = Math.tanh(x * 1.2) * 0.7 * fade * Math.min(1, t / 0.0003);
  }
  return out;
}
