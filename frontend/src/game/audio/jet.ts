/**
 * A twin-engined fighter's sound, synthesised (no recordings), DOM-free: the same code runs in the AudioWorklet 'jet'
 * (jet.worklet.ts) and in Node (tools/jet-wav.ts renders and measures it).
 *
 * Heard from behind and a little above, where the game's camera is. Per engine, each with its own noise and a
 * fraction of a percent apart in speed so that the two beat:
 *   - the fan's whine: its blade-passing tone (and the octave) following the low-pressure spool, which runs from
 *     about a fifth of its speed at idle; a fainter, higher tone of the compressor. They carry the sound at idle and
 *     on the taxiway and are drowned by the exhaust at power;
 *   - "buzz-saw" tones of the shaft's orders once the fan's tips are supersonic (above ~80 % fan speed);
 *   - the core's hiss (high-passed noise);
 *   - the exhaust: mixing noise around the Strouhal peak of the jet (150–260 Hz dry), a rumble below 70 Hz and the
 *     shear layer's tearing around 900 Hz, all growing steeply with the thrust and stirred by a slow turbulence;
 *   - the afterburner: more of the low roar, a thump as it lights, and crackle (short, one-sided bursts as from
 *     the shock-like waves of a supersonic exhaust).
 * `distance` (m from the listener: the take-off after the finish) takes level and treble away.
 * Estimates throughout: blade counts and speeds are those of an engine of the F100's class, the levels are set by
 * ear against the measurements `tools/jet-wav.ts` prints (idle ≈ −33, military ≈ −23, afterburner ≈ −17 dBFS RMS).
 */
export interface JetSoundParams {
  /** thrust at idle and at military power as shares of the thrust in full afterburner */
  idle: number;
  dry: number;
  /** fan blade-passing frequency at full speed (Hz) and the compressor tone's */
  fan: number;
  compressor: number;
  /** exhaust: the mixing noise's peak at military power (Hz) */
  peak: number;
}

export const JET_SOUND: JetSoundParams = { idle: 0.04, dry: 0.62, fan: 4600, compressor: 9300, peak: 250 };

/** overall level: full afterburner at the camera ≈ −17 dBFS RMS */
const MASTER = 0.5;

class Noise {
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
    return (this.s / 2147483648) - 1;
  }
}

/** a state-variable filter (trapezoidal): stays stable while its frequency moves */
class Svf {
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

const TAU = Math.PI * 2;
/** the buzz-saw's shaft orders and their (fixed, uneven) strengths */
const SAW_ORDER = [7, 9, 10, 12, 13];
const SAW_GAIN = [0.9, 0.6, 1, 0.5, 0.75];
/** a sine by table (phases are kept in turns): `Math.sin` per tone and sample cost a tenth of a core */
const TABLE = 4096;
const SIN = new Float32Array(TABLE);
for (let i = 0; i < TABLE; i++) SIN[i] = Math.sin((i / TABLE) * TAU);
const sin = (turns: number) => SIN[((turns - Math.floor(turns)) * TABLE) | 0];
/** the slow walks (the tones' wander, the flutter, the exhaust's turbulence) are stepped every this many samples */
const SLOW = 16;

class Engine {
  private noise: Noise;
  private detune: number;
  private pFan = 0;
  private pComp = 0;
  private pShaft = 0;
  private wander = 0;
  private flutter = 0;
  private turb = 0;
  private burst = 0;
  private thump = 0;
  private pThump = 0;
  private lit = false;
  private tick = 0;
  private hiss = new Svf();
  private roar = new Svf();
  private rumble = new Svf();
  private tear = new Svf();
  private crack = new Svf();
  // per block
  private gFan = 0;
  private gComp = 0;
  private gSaw = 0;
  private gHiss = 0;
  private gRoar = 0;
  private gRumble = 0;
  private gTear = 0;
  private gCrack = 0;
  private fFan = 0;
  private fComp = 0;
  private fShaft = 0;
  private crackRate = 0;

  constructor(private p: JetSoundParams, private rate: number, seed: number, side: number) {
    this.noise = new Noise(seed);
    this.detune = 1 + side * 0.0035;
    this.pFan = Math.abs(this.noise.next());
  }

  /** once per block: spool 0 = idle … 1 = military power, afterburner 0…1 */
  set(spool: number, ab: number) {
    const p = this.p, rate = this.rate;
    // the fan idles at about a fifth of its speed, the core at two thirds
    const n1 = (0.21 + 0.79 * Math.pow(spool, 1.25)) * this.detune;
    const n2 = (0.65 + 0.35 * spool) * this.detune;
    const thrust = p.idle + (p.dry - p.idle) * spool + (1 - p.dry) * ab;
    this.fFan = (p.fan * n1) / rate;
    this.fComp = (p.compressor * n2) / rate;
    this.fShaft = ((p.fan / 30) * n1) / rate;
    // the whine: there from idle, loudest in the middle of the range, under the exhaust at power
    this.gFan = 0.085 * (0.55 + 0.9 * n1) * (1 - 0.82 * spool) * (1 - 0.5 * ab);
    this.gComp = 0.02 * (0.6 + 0.4 * spool) * (1 - 0.6 * ab);
    this.gSaw = 0.035 * smooth(0.78, 0.97, n1) * (1 - 0.4 * ab);
    this.gHiss = 0.06 + 0.12 * spool * spool;
    this.gRoar = 0.12 + 5.5 * Math.pow(thrust, 1.5);
    this.gRumble = 6 * thrust * thrust * (0.6 + 0.8 * ab);
    this.gTear = 1.5 * Math.pow(thrust, 1.3);
    this.gCrack = 0.55 * ab;
    this.crackRate = (220 * ab * ab) / rate;
    this.hiss.set(3200 + 2600 * spool, 0.7, rate);
    // a hotter, faster jet at power: the peak moves up dry, and down again with the afterburner's wide plume
    this.roar.set((p.peak * (0.55 + 0.45 * spool) * (1 - 0.35 * ab)) * this.detune, 0.6, rate);
    this.rumble.set(70 - 15 * ab, 0.7, rate);
    this.tear.set(900 * (0.7 + 0.3 * spool), 0.5, rate);
    this.crack.set(2400, 0.8, rate);
    if (ab > 0.08 && !this.lit) {
      this.lit = true;
      this.thump = 1;
      this.pThump = 0;
    } else if (ab < 0.02) this.lit = false;
  }

  /** one sample */
  run() {
    const n = this.noise, rate = this.rate;
    const w = n.next();
    // slow walks: the tones' wander (≈30 Hz), their flutter and the exhaust's turbulence (≈8 Hz)
    if (++this.tick >= SLOW) {
      this.tick = 0;
      this.wander += (w - this.wander) * ((190 * SLOW) / rate);
      this.flutter += (n.next() - this.flutter) * ((60 * SLOW) / rate);
      this.turb += (n.next() - this.turb) * ((50 * SLOW) / rate);
    }
    const bend = 1 + this.wander * 0.006;
    this.pFan += this.fFan * bend;
    this.pComp += this.fComp * bend;
    this.pShaft += this.fShaft;
    if (this.pFan > 1) this.pFan -= 1;
    if (this.pComp > 1) this.pComp -= 1;
    if (this.pShaft > 4096) this.pShaft -= 4096;
    let out = (sin(this.pFan) + 0.35 * sin(2 * this.pFan)) * this.gFan * (1 + this.flutter * 1.2) + sin(this.pComp) * this.gComp;
    if (this.gSaw > 1e-4) {
      let saw = 0;
      for (let k = 0; k < SAW_ORDER.length; k++) saw += sin(this.pShaft * SAW_ORDER[k]) * SAW_GAIN[k];
      out += saw * this.gSaw;
    }
    this.hiss.run(w);
    out += this.hiss.hp * this.gHiss;
    const stir = 1 + this.turb * 1.6;
    const x = n.next();
    this.roar.run(x);
    this.rumble.run(x);
    this.tear.run(w);
    out += (this.roar.bp * this.gRoar + this.rumble.lp * this.gRumble + this.tear.bp * this.gTear) * stir;
    if (this.gCrack > 1e-4) {
      // crackle: short one-sided bursts at random moments, with the grain of band-passed noise
      if (x * 0.5 + 0.5 < this.crackRate) this.burst += 0.4 + w * w;
      this.burst *= 1 - 420 / rate;
      this.crack.run(w);
      out += this.burst * (0.8 + this.crack.bp * 1.4) * this.gCrack;
    }
    if (this.thump > 1e-3) {
      this.pThump += 52 / rate;
      out += sin(this.pThump) * this.thump * 0.35;
      this.thump *= 1 - 5.5 / rate;
    }
    return out;
  }
}

function smooth(a: number, b: number, x: number) {
  const t = Math.min(Math.max((x - a) / (b - a), 0), 1);
  return t * t * (3 - 2 * t);
}

export class JetSynth {
  /** inputs, read once per block: spool 0…1, afterburner 0…1, level 0…1, distance to the listener (m) */
  spool = 0;
  afterburner = 0;
  level = 1;
  distance = 0;

  private engines: [Engine, Engine];
  private sp = 0;
  private ab = 0;
  private lv = 0;
  private far = 0;
  private lpL = 0;
  private lpR = 0;
  private dcL = 0;
  private dcR = 0;

  constructor(private rate: number, seed: number, params: JetSoundParams = JET_SOUND) {
    this.engines = [new Engine(params, rate, seed * 2 + 1, 1), new Engine(params, rate, seed * 2 + 7919, -1)];
  }

  process(L: Float32Array, R: Float32Array) {
    const n = L.length, rate = this.rate;
    // (the inputs come per frame of the game: eased over a few blocks)
    const ease = 1 - Math.exp(-n / (0.06 * rate));
    this.sp += (this.spool - this.sp) * ease;
    this.ab += (this.afterburner - this.ab) * ease;
    this.lv += (this.level - this.lv) * ease;
    this.far += (this.distance - this.far) * ease;
    const [a, b] = this.engines;
    a.set(this.sp, this.ab);
    b.set(this.sp, this.ab);
    // away from the listener: 1 / distance beyond the first 160 m, and the air takes the treble first
    const gain = (MASTER * this.lv) / (1 + this.far / 160);
    const cut = 1 - Math.exp((-TAU * (16000 / (1 + this.far / 220))) / rate);
    if (gain < 1e-5) {
      L.fill(0);
      if (R !== L) R.fill(0);
      return;
    }
    for (let i = 0; i < n; i++) {
      const l = a.run(), r = b.run();
      // the left engine a little to the left, the right one to the right
      this.lpL += ((l * 0.62 + r * 0.38) * gain - this.lpL) * cut;
      this.lpR += ((r * 0.62 + l * 0.38) * gain - this.lpR) * cut;
      // (no standing offset from the one-sided crackle)
      this.dcL += (this.lpL - this.dcL) * (20 / rate);
      this.dcR += (this.lpR - this.dcR) * (20 / rate);
      L[i] = this.lpL - this.dcL;
      if (R !== L) R[i] = this.lpR - this.dcR;
    }
  }
}
