/**
 * A train's running noise as heard inside the first car, synthesised from physical parameters (no recordings).
 * DOM-free: the game runs it in the AudioWorklet 'train-running' (running.worklet.ts), tools/train-run-wav.ts in
 * Node. Parts, all from one seeded noise generator (a render is reproducible):
 * - Rolling roar: noise shaped by nine octave bands (`BODY[].roll`: dBFS per octave at the body's reference speed).
 *   The spectrum slides up in frequency with the speed (the rail's roughness wavelengths are fixed, so their
 *   frequencies rise with it) and the power grows ∝ v^2.5; a slow random sway (track irregularity), deeper
 *   in the low bands (the body rumble). A pressure-tight body (Shinkansen) has its own spectrum: little above 200 Hz.
 * - Wind: the roar's power gains a part ∝ v⁶ (aerodynamic noise), unswayed: it catches up with the wheels at
 *   `WIND_EVEN` km/h (wind factor 1), and the roar grows steeper and smoother above.
 * - The motors' and gears' hum: the rotors turn at wheel revolutions × gear ratio (a tone and its 2nd harmonic,
 *   the loudest single line in both recordings) and the gear mesh (× pinion teeth) whines faintly.
 * - Rail joints: every axle of the three cars crosses each joint (`jointCrossings`), so each bogie goes "ta-tan" and
 *   the facing bogies of two cars "ta-tan ta-tan"; loudness by the axle's distance from the listener (middle of the
 *   first car). A click: a resonant thump (~110 Hz) and a short filtered clack; strength per joint and per hit
 *   varied a little at random. Welded rail and slab track: a weak one every `WELDED_SPACING` m only.
 * - Curve squeal: a light tone when cornering hard (radius under ~300 m) at low speed. Brake: a soft hiss and grind.
 * Levels in dBFS as mixed into TrainSound's output. The two bodies' spectra, the hum and the joint clicks were fitted
 * to measurements of two in-train recordings the game used to loop (a 223 series coasting at ~110 km/h, a 700 series
 * Shinkansen at ~203 km/h, at the half level the game played them; the numbers are in tools/train-run-wav.ts, which
 * prints the comparison).
 */
import type { TrainInfo } from '../vehicle/trains';
import { rng, smoothstep } from '../util/math';

/** Track and body of a train (TrainInfo.running): all optional, the defaults suit a commuter train on jointed track. */
export interface TrainRunning {
  /** 'jointed' (default): 25 m rails with joints; 'welded': long welded rail or slab track, hardly any joint */
  rail?: 'jointed' | 'welded';
  /** axle spacing in a bogie (m): 2.1 commuter bogies (default), 2.5 Shinkansen */
  axle?: number;
  /** aerodynamic noise against a typical car's (default 1): it grows ∝ v⁶ and dominates above ~200 km/h */
  wind?: number;
  /** pressure-tight body (Shinkansen): the high frequencies muffled */
  sealed?: boolean;
}

/** Everything the synthesis needs (`runningParams` from a TrainInfo). */
export interface RunningParams {
  carLength: number;
  bogies: number;
  axle: number;
  /** distance between joints (m) and their loudness (1 = a jointed line's) */
  jointSpacing: number;
  jointGain: number;
  wind: number;
  sealed: boolean;
  /** wheel diameter (m), gear ratio and pinion teeth: the motors' hum and the gear mesh */
  wheel: number;
  gearRatio: number;
  pinion: number;
}

/** rail length of Japanese conventional lines (m) */
export const RAIL_LENGTH = 25;
/** welded rail / slab track: an expansion joint or a weld every so often, weak */
export const WELDED_SPACING = 400;
const WELDED_GAIN = 0.35;
const CARS = 3;

export function runningParams(t: Pick<TrainInfo, 'carLength' | 'bogies' | 'wheel' | 'gearRatio' | 'running' | 'vvvf'>): RunningParams {
  const r = t.running ?? {};
  const welded = r.rail === 'welded';
  return {
    carLength: t.carLength,
    bogies: t.bogies,
    axle: r.axle ?? 2.1,
    jointSpacing: welded ? WELDED_SPACING : RAIL_LENGTH,
    jointGain: welded ? WELDED_GAIN : 1,
    wind: r.wind ?? 1,
    sealed: !!r.sealed,
    wheel: t.wheel,
    gearRatio: t.gearRatio,
    pinion: t.vvvf?.gear[0] ?? 15,
  };
}

/**
 * The axles of the three cars: distance behind the front of the train (m), front to back, and loudness at the
 * listener in the middle of the first car (falling with distance, and through each gangway).
 */
export function axles(p: Pick<RunningParams, 'carLength' | 'bogies' | 'axle'>) {
  const out: { at: number; gain: number }[] = [];
  const listener = p.carLength / 2;
  for (let c = 0; c < CARS; c++) {
    for (const b of [-1, 1]) {
      for (const a of [-1, 1]) {
        const at = c * p.carLength + p.carLength / 2 + (b * p.bogies) / 2 + (a * p.axle) / 2;
        out.push({ at, gain: Math.exp(-Math.abs(at - listener) / 10) * 0.5 ** c });
      }
    }
  }
  return out;
}

/**
 * Joints crossed while the front of the train runs from s0 to s1 (m along the track, s0 < s1; joints at every
 * multiple of `spacing`): [distance of the front when the axle meets the joint, axle index, joint index], in the
 * order they happen.
 */
export function jointCrossings(s0: number, s1: number, axleAt: number[], spacing: number) {
  const out: [number, number, number][] = [];
  for (let a = 0; a < axleAt.length; a++) {
    const x = axleAt[a];
    for (let j = Math.floor((s0 - x) / spacing) + 1; j * spacing + x <= s1; j++) out.push([j * spacing + x, a, j]);
  }
  return out.sort((u, v) => u[0] - v[0]);
}

/** The joint clicks (s) at a steady speed, the front starting at s0 (m): what RunningNoise plays. */
export function clickTimes(p: RunningParams, kmh: number, seconds: number, s0 = 0) {
  const v = kmh / 3.6;
  return jointCrossings(s0, s0 + v * seconds, axles(p).map((a) => a.at), p.jointSpacing).map(([s]) => (s - s0) / v);
}

/** octave band centres of the roar (Hz) */
const BANDS = [0, 1, 2, 3, 4, 5, 6, 7, 8].map((i) => 1000 * 2 ** (i - 5));
/**
 * The two bodies, [commuter car, pressure-tight car]: the reference speed (km/h) and there the roar per octave band
 * (dBFS, before the sway; wind included) and how far it follows the speed (`shift`: 1 = frequencies ∝ v; less in
 * the sealed car, where the body's own resonances shape more of it), the rotor hum (1st, 2nd harmonic) and gear mesh (dBFS), the clack's level.
 */
const BODY = [
  { kmh: 110, roll: [-44.4, -45.7, -31.7, -30.9, -29.9, -29.7, -39.2, -38.1, -52.1], shift: 0.7, rotor: -33, rotor2: -32.3, mesh: -50, clack: 1 },
  { kmh: 203, roll: [-46.3, -29.8, -31.9, -49.9, -67.9, -59.2, -62.4, -80.4, -73.8], shift: 0.4, rotor: -29.5, rotor2: -37.2, mesh: -62, clack: 0.1 },
];
/** top of the roar at the reference speed (Hz; it follows the speed like the spectrum) */
const TOP_HZ = 6000;
/** wind equals the rolling noise here (km/h, wind factor 1) */
const WIND_EVEN = 200;
/**
 * joints: the thump's and the clack's level per unit click (in 43 ms around the commuter recording's clicks: +5 dB
 * at 100–125 Hz, +2 dB at 300–800 Hz over the average); flange squeal and brake noise (light, by ear)
 */
const THUMP = 0.2, CLACK = 2.4;
const SQUEAL = 0.01, BRAKE = 0.012;

const TWO_PI = 2 * Math.PI;

/** RBJ band-pass (0 dB peak) coefficients [b0, a1, a2] (b1 = 0, b2 = -b0) */
function bandpass(f: number, q: number, rate: number) {
  const w = (TWO_PI * f) / rate, al = Math.sin(w) / (2 * q), a0 = 1 + al;
  return [al / a0, (-2 * Math.cos(w)) / a0, (1 - al) / a0];
}

/** RBJ low-pass (Q 0.707) into a filter state's coefficients */
function lowpass(f: { b0: number; a1: number; a2: number }, hz: number, rate: number) {
  const w = (TWO_PI * hz) / rate, al = Math.sin(w) / Math.SQRT2, c = Math.cos(w), a0 = 1 + al;
  f.b0 = (1 - c) / 2 / a0;
  f.a1 = (-2 * c) / a0;
  f.a2 = (1 - al) / a0;
}

/** dB of a table over octave bands at an arbitrary frequency (log interpolation; −12 dB/oct beyond the top) */
function atFreq(table: number[], f: number) {
  const x = Math.log2(f / BANDS[0]);
  if (x <= 0) return table[0] + 6 * x;
  const last = table.length - 1;
  if (x >= last) return table[last] - 12 * (x - last);
  const i = Math.floor(x);
  return table[i] + (table[i + 1] - table[i]) * (x - i);
}

const db = (v: number) => 10 ** (v / 20);

/**
 * The synthesis: set `kmh`, `brake` (0…1) and `lateral` (m/s²) and call `process` for each block; it integrates the
 * distance itself. `onClick` (tools, tests) hears every joint click: sample index from the start, amplitude, axle
 * (index into `axles`).
 */
export class RunningNoise {
  kmh = 0;
  brake = 0;
  lateral = 0;
  onClick: ((sample: number, amp: number, axle: number) => void) | null = null;

  private random: () => number;
  private seed: number;
  private axleAt: number[];
  private axleGain: number[];
  /** distance run by the front (m) and samples processed */
  private s: number;
  private n = 0;
  /** octave bands: two band-passes in series (states x, y and z), gain g, white-noise normalisation */
  private bands: { b0: number; a1: number; a2: number; x1: number; x2: number; y1: number; y2: number; z1: number; z2: number; g: number; norm: number }[];
  private v = 0;
  private sway = [0, 0, 0, 0];
  // hum oscillators
  private phRotor = 0;
  private phMesh = 0;
  private gRotor = 0;
  private gRotor2 = 0;
  private gMesh = 0;
  // joints: an impulse per click into the thump resonator, a decaying noise burst through the clack filter
  private exc: Float32Array;
  private th = { a1: 0, a2: 0, y1: 0, y2: 0 };
  private burst = 0;
  /** input scale of the thump resonator: its impulse response peaks near 1 */
  private thumpIn: number;
  private burstDecay: number;
  private clack = { b0: 0, a1: 0, a2: 0, x1: 0, x2: 0, y1: 0, y2: 0 };
  // squeal and brake
  private squealLevel = 0;
  private squealHz = 0;
  private phSq = 0;
  private gSq = 0;
  private brakeLevel = 0;
  private gBr = 0;
  /** low-pass on the roar and the joints (b1 = 2 b0, b2 = b0): the top end follows the speed */
  private lp = { b0: 0, a1: 0, a2: 0, x1: 0, x2: 0, y1: 0, y2: 0 };
  private hiss = { b0: 0, a1: 0, a2: 0, x1: 0, x2: 0, y1: 0, y2: 0 };
  private grind = { b0: 0, a1: 0, a2: 0, x1: 0, x2: 0, y1: 0, y2: 0 };

  constructor(
    private p: RunningParams,
    private rate: number,
    seed = 1,
  ) {
    this.random = rng(seed);
    this.seed = seed >>> 0;
    const ax = axles(p);
    this.axleAt = ax.map((a) => a.at);
    this.axleGain = ax.map((a) => a.gain);
    // somewhere between two joints
    this.s = this.random() * p.jointSpacing;
    this.bands = BANDS.filter((f) => f < rate * 0.42).map((f) => {
      const [b0, a1, a2] = bandpass(f, 1.4, rate);
      // white noise (uniform, mean square 1/3) through the band: its power gain is the impulse response's energy
      let e = 0;
      for (let i = 0, x1 = 0, x2 = 0, y1 = 0, y2 = 0, z1 = 0, z2 = 0; i < rate; i++) {
        const x = i === 0 ? 1 : 0;
        const y = b0 * (x - x2) - a1 * y1 - a2 * y2;
        const z = b0 * (y - y2) - a1 * z1 - a2 * z2;
        [x2, x1, y2, y1, z2, z1] = [x1, x, y1, y, z1, z];
        e += z * z;
      }
      return { b0, a1, a2, x1: 0, x2: 0, y1: 0, y2: 0, z1: 0, z2: 0, g: 0, norm: 1 / Math.sqrt(e / 3) };
    });
    this.exc = new Float32Array(128);
    // thump: a resonance at 110 Hz dying in ~30 ms; clack: a 9 ms burst of noise around 500 Hz
    const r = Math.exp(-1 / (0.03 * rate));
    this.th.a1 = 2 * r * Math.cos((TWO_PI * 110) / rate);
    this.th.a2 = r * r;
    this.thumpIn = Math.sin((TWO_PI * 110) / rate);
    this.burstDecay = Math.exp(-1 / (0.009 * rate));
    [this.clack.b0, this.clack.a1, this.clack.a2] = bandpass(500, 1, rate);
    [this.hiss.b0, this.hiss.a1, this.hiss.a2] = bandpass(1600, 1, rate);
    [this.grind.b0, this.grind.a1, this.grind.a2] = bandpass(420, 1.4, rate);
  }

  /** a joint's own strength (0.75…1.25): every axle meets the same dip */
  private jointStrength(j: number) {
    let h = Math.imul(j ^ this.seed, 0x9e3779b1);
    h = Math.imul(h ^ (h >>> 15), 0x85ebca6b);
    h ^= h >>> 13;
    return 0.75 + 0.5 * ((h >>> 0) / 4294967296);
  }

  /** slow random sway (unit spread) low-passed at `hz`, one step per block */
  private swayStep(i: number, hz: number, dt: number) {
    const a = Math.exp(-TWO_PI * hz * dt);
    this.sway[i] = a * this.sway[i] + (1 - a) * (this.random() * 2 - 1);
    return this.sway[i] / Math.sqrt(((1 / 3) * (1 - a)) / (1 + a));
  }

  process(out: Float32Array) {
    const N = out.length, rate = this.rate, p = this.p, dt = N / rate;
    if (this.exc.length < N) this.exc = new Float32Array(N);
    const exc = this.exc;
    exc.fill(0, 0, N);
    // speed eased over ~40 ms (the game sets it once a frame)
    const target = Math.abs(this.kmh) / 3.6;
    this.v += (target - this.v) * (1 - Math.exp(-dt / 0.04));
    const v = this.v, kmh = v * 3.6;
    const body = BODY[p.sealed ? 1 : 0];

    // ---- the roar's band gains (ramped across the block)
    const k = Math.max(kmh, 0.01) / body.kmh;
    const shift = k ** -body.shift;
    const roll = k ** 1.25;
    const sw = this.swayStep(0, 0.4 + v / 20, dt), swLow = this.swayStep(1, 0.3 + v / 30, dt);
    const swayDepth = p.jointGain < 1 ? 0.1 : 0.18;
    const mod = Math.exp(swayDepth * sw), modLow = mod * Math.exp(0.3 * swLow);
    const wind2 = p.wind * p.wind * (kmh / WIND_EVEN) ** 3.5;
    const bandOld = this.bands.map((b) => b.g);
    // bands below -90 dBFS are skipped (a sealed car's upper bands, the top at low speed)
    for (let i = 0; i < this.bands.length; i++) {
      const b = this.bands[i];
      const dbv = atFreq(body.roll, BANDS[i] * shift);
      const m = BANDS[i] <= 125 ? modLow : mod;
      b.g = kmh < 0.05 ? 0 : db(dbv) * roll * Math.sqrt(m * m + wind2) * b.norm;
    }
    const live = this.bands.map((b, i) => Math.max(b.g, bandOld[i]) > 3e-5 * b.norm);

    // ---- the roar's top end follows the speed
    lowpass(this.lp, Math.min(rate * 0.4, TOP_HZ / shift), rate);

    // ---- hum: rotor revolutions and gear mesh
    const rotorHz = (v / (Math.PI * p.wheel)) * p.gearRatio;
    const hl = k ** 1.5;
    // a rotor below ~25 Hz is felt more than heard
    const audible = smoothstep(12, 30, rotorHz);
    const gR0 = this.gRotor, gR20 = this.gRotor2, gM0 = this.gMesh;
    this.gRotor = db(body.rotor) * Math.SQRT2 * hl * audible * (1 + 0.15 * sw);
    this.gRotor2 = db(body.rotor2) * Math.SQRT2 * hl * audible;
    const meshHz = rotorHz * p.pinion;
    this.gMesh = meshHz < rate * 0.45 ? db(body.mesh) * Math.SQRT2 * hl : 0;

    // ---- joints in this block
    const s0 = this.s, s1 = s0 + v * dt;
    if (v > 0.05) {
      const amp0 = p.jointGain * Math.min(1.6, kmh / 110);
      for (const [s, a, j] of jointCrossings(s0, s1, this.axleAt, p.jointSpacing)) {
        const i = Math.min(N - 1, Math.max(0, Math.floor(((s - s0) / v) * rate)));
        const amp = amp0 * this.axleGain[a] * this.jointStrength(j) * (0.85 + 0.3 * this.random());
        exc[i] += amp;
        this.onClick?.(this.n + i, amp, a);
      }
    }
    this.s = s1;

    // ---- squeal: hard cornering (curvature from the lateral acceleration) at low speed
    const curv = Math.abs(this.lateral) / Math.max(v * v, 1);
    const sq = smoothstep(1 / 300, 1 / 80, curv) * smoothstep(4, 12, kmh) * (1 - smoothstep(45, 75, kmh));
    if (sq > 0.02 && this.squealLevel < 0.01) this.squealHz = [2150, 2900, 3550, 4300][Math.floor(this.random() * 4)] * (0.97 + 0.06 * this.random());
    this.squealLevel += (sq - this.squealLevel) * (1 - Math.exp(-dt / (sq > this.squealLevel ? 0.25 : 0.4)));
    const flutter = this.swayStep(2, 7, dt);
    const gSq0 = this.gSq;
    this.gSq = SQUEAL * this.squealLevel * Math.max(0, 0.7 + 0.3 * flutter);
    const sqHz = this.squealHz * (1 + 0.003 * flutter);

    // ---- brake: shoes and discs, more as the air brake takes over near the stop
    const br = this.brake * smoothstep(1, 6, kmh) * (0.5 + 0.5 * Math.min(1, kmh / 50)) * (1 + (1 - smoothstep(4, 20, kmh)));
    this.brakeLevel += (br - this.brakeLevel) * (1 - Math.exp(-dt / 0.15));
    const rough = this.swayStep(3, 30, dt);
    const gBr0 = this.gBr;
    this.gBr = BRAKE * this.brakeLevel * Math.max(0, 0.75 + 0.25 * rough);

    // ---- samples
    const bands = this.bands, nb = bands.length, th = this.th, ck = this.clack, hs = this.hiss, gr = this.grind;
    const dRot = rotorHz / rate, dMesh = meshHz / rate, dSq = sqHz / rate;
    const quiet = kmh < 0.05 && this.gSq < 1e-6 && gSq0 < 1e-6 && this.gBr < 1e-6 && Math.abs(th.y1) + Math.abs(th.y2) < 1e-7 && this.burst < 1e-7;
    if (quiet) {
      out.fill(0, 0, N);
      this.n += N;
      return;
    }
    const random = this.random;
    const lp = this.lp;
    const thumpGain = THUMP * this.thumpIn, clackGain = CLACK * body.clack;
    for (let n = 0; n < N; n++) {
      const t = (n + 1) / N;
      const w = random() * 2 - 1, w1 = random() * 2 - 1, w2 = random() * 2 - 1;
      let y = 0;
      for (let i = 0; i < nb; i++) {
        const b = bands[i];
        if (!live[i]) continue;
        // bands up to two octaves apart from independent noise (the skirts of one noise would interfere)
        const k3 = i % 3;
        const x = k3 === 0 ? w : k3 === 1 ? w1 : w2;
        const o = b.b0 * (x - b.x2) - b.a1 * b.y1 - b.a2 * b.y2;
        const o2 = b.b0 * (o - b.y2) - b.a1 * b.z1 - b.a2 * b.z2;
        b.x2 = b.x1;
        b.x1 = x;
        b.y2 = b.y1;
        b.y1 = o;
        b.z2 = b.z1;
        b.z1 = o2;
        y += o2 * (bandOld[i] + (b.g - bandOld[i]) * t);
      }
      // joints
      const e = exc[n];
      const thump = e + th.a1 * th.y1 - th.a2 * th.y2;
      th.y2 = th.y1;
      th.y1 = thump;
      this.burst = this.burst * this.burstDecay + e;
      const cx = (random() * 2 - 1) * this.burst;
      const c = ck.b0 * (cx - ck.x2) - ck.a1 * ck.y1 - ck.a2 * ck.y2;
      ck.x2 = ck.x1;
      ck.x1 = cx;
      ck.y2 = ck.y1;
      ck.y1 = c;
      y += thumpGain * thump + clackGain * c;
      // the top end falls away, lower at low speed
      const o = lp.b0 * (y + 2 * lp.x1 + lp.x2) - lp.a1 * lp.y1 - lp.a2 * lp.y2;
      lp.x2 = lp.x1;
      lp.x1 = y;
      lp.y2 = lp.y1;
      lp.y1 = o;
      y = o;
      // hum
      this.phRotor += dRot;
      if (this.phRotor > 1) this.phRotor -= 1;
      this.phMesh += dMesh;
      if (this.phMesh > 1) this.phMesh -= 1;
      y += Math.sin(TWO_PI * this.phRotor) * (gR0 + (this.gRotor - gR0) * t);
      y += Math.sin(2 * TWO_PI * this.phRotor + 0.7) * (gR20 + (this.gRotor2 - gR20) * t);
      y += Math.sin(TWO_PI * this.phMesh) * (gM0 + (this.gMesh - gM0) * t);
      // squeal
      const gs = gSq0 + (this.gSq - gSq0) * t;
      if (gs > 1e-6) {
        this.phSq += dSq;
        if (this.phSq > 1) this.phSq -= 1;
        y += gs * (Math.sin(TWO_PI * this.phSq) + 0.25 * Math.sin(2 * TWO_PI * this.phSq));
      }
      // brake
      const gb = gBr0 + (this.gBr - gBr0) * t;
      if (gb > 1e-6) {
        const h = hs.b0 * (w - hs.x2) - hs.a1 * hs.y1 - hs.a2 * hs.y2;
        hs.x2 = hs.x1;
        hs.x1 = w;
        hs.y2 = hs.y1;
        hs.y1 = h;
        const g = gr.b0 * (w - gr.x2) - gr.a1 * gr.y1 - gr.a2 * gr.y2;
        gr.x2 = gr.x1;
        gr.x1 = w;
        gr.y2 = gr.y1;
        gr.y1 = g;
        y += gb * (h + 1.6 * g);
      }
      out[n] = y;
    }
    this.n += N;
  }
}
