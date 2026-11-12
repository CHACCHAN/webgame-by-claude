/**
 * Rain as heard from a vehicle on a mountain road at night, synthesised (no recordings). DOM-free: the game runs it in
 * the AudioWorklet 'rain' (rain.worklet.ts), tools/rain-wav.ts in Node to render and measure it.
 *
 * What it is made of (each layer measured in tools/rain-wav.ts):
 *  - the wash: the whole hillside at once. Broadband noise, separate per ear above ~300 Hz (a diffuse field: the two
 *    ears hear different drops) over a shared low rumble; its level and brightness breathe with the gusts.
 *  - the near fall: drops landing on the asphalt and the leaves around. Single impacts (Poisson, ~2500 a second in
 *    full rain), each an impulse into a bank of resonators (the drop's pitch: where between two of them it lands),
 *    its loudness from its distance (spread evenly over the ground within 25 m, so most are faint and a few close
 *    ones stand out), placed between the ears. Now and then one falls into a puddle: a bubble's rising ping.
 *  - the body: drops on the car's roof and glass (dull panel thuds, glass ticks), more of them with speed (the car
 *    drives into the falling rain: the windscreen sweeps it up); a helmet for a bike, the cab's windscreen for a
 *    train, nothing for the cockroach (it is down among the drops: the near fall is its sound).
 *  - the spray: the tyres cutting the water film (a hiss that grows with speed), the water thrown into the wheel
 *    arches (a low wash), louder through puddles now and then.
 *  - under a roof (a rock shed): the fall on the body and the near drops stop, the wash outside is muffled, and
 *    drips fall from the roof's edge.
 *  - gusts: two slow random walks (7 s and 16 s) move the wash's level and colour and the drops' rate together.
 *
 * Inputs (set between blocks): `level` 0…1 (the weather's rain), `speed` (m/s), `cover` 0…1 (share of the
 * listener's surroundings under a roof: `coverShare`), `body` (`rainBodyOf`). Everything is eased inside, so the
 * inputs may jump.
 */
import type { VehicleKind } from '../vehicle/kinds';

/** what the rain falls on next to the listener */
export type RainBody = 'car' | 'bike' | 'train' | 'none';

export const rainBodyOf = (kind: VehicleKind | null): RainBody =>
  kind === 'car' || kind === 'tank' || kind === 'jet' ? 'car' : kind === 'bike' ? 'bike' : kind === 'train' ? 'train' : 'none';

/**
 * Share of the ground around (x, z) that is under one of the course's roofs (SceneryResult.covers: 9 floats per
 * quad, corners a b c d as x z pairs and the slab's height) above the listener at height y: the place itself and
 * four points 5 m around it, so that the change is spread over the ~10 m around a roof's edge.
 */
export function coverShare(covers: Float32Array, x: number, y: number, z: number): number {
  if (!covers.length) return 0;
  let hit = 0;
  for (let p = 0; p < 5; p++) {
    const px = x + (p === 1 ? 5 : p === 2 ? -5 : 0), pz = z + (p === 3 ? 5 : p === 4 ? -5 : 0);
    for (let o = 0; o < covers.length; o += 9) {
      if (y > covers[o + 8]) continue;
      let pos = 0, neg = 0;
      for (let k = 0; k < 4; k++) {
        const ax = covers[o + k * 2], az = covers[o + k * 2 + 1];
        const bx = covers[o + ((k + 1) % 4) * 2], bz = covers[o + ((k + 1) % 4) * 2 + 1];
        const s = (bx - ax) * (pz - az) - (bz - az) * (px - ax);
        if (s >= 0) pos++;
        if (s <= 0) neg++;
      }
      if (pos === 4 || neg === 4) {
        hit++;
        break;
      }
    }
  }
  return hit / 5;
}

/** a two-pole band-pass resonator (RBJ, b2 = −b0) for two channels, its input scaled to unit impulse-response energy */
class Reson {
  b0: number;
  a1: number;
  a2: number;
  norm: number;
  l1 = 0;
  l2 = 0;
  r1 = 0;
  r2 = 0;
  xl1 = 0;
  xl2 = 0;
  xr1 = 0;
  xr2 = 0;
  /** excitation waiting for this sample */
  el = 0;
  er = 0;
  constructor(rate: number, f: number, q: number) {
    const w = (2 * Math.PI * Math.min(f, rate * 0.45)) / rate, alpha = Math.sin(w) / (2 * q), a0 = 1 + alpha;
    this.b0 = alpha / a0;
    this.a1 = (-2 * Math.cos(w)) / a0;
    this.a2 = (1 - alpha) / a0;
    // energy of the impulse response
    let y1 = 0, y2 = 0, e = 0;
    for (let i = 0; i < 8192; i++) {
      const x = i === 0 ? 1 : 0, x2 = i === 2 ? 1 : 0;
      const y = this.b0 * (x - x2) - this.a1 * y1 - this.a2 * y2;
      y2 = y1;
      y1 = y;
      e += y * y;
    }
    this.norm = 1 / Math.sqrt(e);
  }
}

/** one-pole low-pass coefficient for a cutoff (Hz) */
const onePole = (f: number, rate: number) => 1 - Math.exp((-2 * Math.PI * f) / rate);

interface Ping {
  on: boolean;
  ph: number;
  f: number;
  rise: number;
  amp: number;
  decay: number;
  gl: number;
  gr: number;
}

// resonator banks: frequency (Hz), Q
const NEAR: [number, number][] = [[700, 1.1], [1150, 1.3], [1800, 1.5], [2700, 1.8], [3900, 2.2], [5600, 2.6], [8000, 3]];
const ROOF: [number, number][] = [[150, 5], [240, 6], [370, 7], [560, 8]];
const GLASS: [number, number][] = [[1250, 9], [1900, 10], [2900, 12]];
const HELMET: [number, number][] = [[620, 4], [1050, 5], [1650, 6]];
const CAB: [number, number][] = [[850, 9], [1400, 10], [2200, 12]];

/** body sounds: drops a second in full rain standing still, speed (m/s) that doubles them, level, share on glass, width */
const BODY: Record<RainBody, { rate: number; vDouble: number; gain: number; glass: number; width: number }> = {
  car: { rate: 260, vDouble: 16, gain: 1, glass: 0.3, width: 0.55 },
  bike: { rate: 70, vDouble: 9, gain: 0.8, glass: 0, width: 0.9 },
  train: { rate: 110, vDouble: 15, gain: 0.45, glass: 1, width: 0.5 },
  none: { rate: 0, vDouble: 1, gain: 0, glass: 0, width: 0 },
};
/** the tyres' spray per body (a train runs on rails, the cockroach throws a little) */
const SPRAY: Record<RainBody, number> = { car: 1, bike: 0.65, train: 0, none: 0.12 };
/**
 * How much of the rain outside (the wash, the near fall) reaches the listener through the vehicle's shell. A train is
 * heard from inside its cab, and its own sound is the quietest of all (a commuter train at 60 km/h: −35.5 dB(A),
 * 11 dB under a car under power): the rain outside is 6.5 dB lower there, so that the inverter stands over it
 * (6 dB over a long time, level with it in a gust's peak).
 */
const OUTSIDE: Record<RainBody, number> = { car: 1, bike: 1, train: 0.47, none: 1 };

/**
 * The layers' levels, set against the vehicles' own sound in the game's mix (tools/rain-mix.ts: A-weighted, before
 * the master's compressor; a car under power is −23 … −25 dB(A) at any speed, −27 … −31 coasting). The rain is a
 * bed under the drive:
 *  - outside: −36.6 dB(A) with the gusts held still, −35.8 over a long time with them, −30 in a gust's peak.
 *    It was 10 dB higher until v2.1.1 (all three were 2.6), at the A-weighted level of the filtered noise it had
 *    replaced. But that noise was a hiss at 4–8 kHz, above where an engine or an inverter sounds, and this rain is
 *    broad: at the same figure it had 5–8 dB more in the octaves 500 Hz … 2 kHz, was as loud as a car at full
 *    throttle and 10 dB over a commuter train at 60 km/h (a player's report: a train in the rain). Now it is
 *    2–5 dB under the old noise in those octaves.
 *  - spray: −38.5 dB(A) at 120 km/h, −36 from 137 km/h on for a car (9 dB lower than it was): with speed it
 *    becomes the larger part and lifts the rain by 4–5 dB, and the whole stays 7–8 dB under the engine.
 *  - body: the drops on the vehicle's own panels and glass, as they were (−48 … −40 dB(A) on a car): 14–22 dB
 *    under the rain outside they were hardly heard; now they are the detail on the bed.
 * A change here: `npx tsx tools/rain-wav.ts <dir>` (the layers alone, over time, in a gust), then
 * `tools/rain-mix.ts` (against the vehicles), and the bounds in rain.test.ts.
 */
const LEVEL = { outside: 0.82, body: 2.6, spray: 0.92 };

export class RainSynth {
  level = 0;
  speed = 0;
  cover = 0;
  body: RainBody = 'none';
  /** the gusts' and the water film's swing (1 = as heard; 0 holds them still, to measure a level: tools/rain-wav.ts) */
  gusts = 1;
  /** the layers' shares (all 1 = as heard; the tool sets two of them to 0 to measure the third alone) */
  layers = { outside: 1, body: 1, spray: 1 };

  private rate: number;
  private s: number;
  // eased inputs
  private lv = 0;
  private cv = 0;
  private cvSlow = 0;
  private v = 0;
  private bodyMix: Record<RainBody, number> = { car: 0, bike: 0, train: 0, none: 1 };
  // gusts: two Ornstein–Uhlenbeck walks (unit variance) and the spray's water film
  private g1 = 0;
  private g2 = 0;
  private film = 0;
  // wash filters: per ear band-pass state, gust/cover low-pass, shared rumble
  private wbL = [0, 0, 0, 0];
  private wbR = [0, 0, 0, 0];
  private wb: { b0: number; a1: number; a2: number };
  private lpL = 0;
  private lpR = 0;
  private rum1 = 0;
  private rum2 = 0;
  // spray: hiss band-pass per ear, arch band-pass shared
  private sh: { b0: number; a1: number; a2: number };
  private shL = [0, 0, 0, 0];
  private shR = [0, 0, 0, 0];
  private sa: { b0: number; a1: number; a2: number };
  private saS = [0, 0, 0, 0];
  private puddle = 0;
  private puddleRise = 0;
  // event clocks: remaining unit-rate exponential mass until the next event
  private eNear: number;
  private ePing: number;
  private eBody: number;
  private eDrip: number;
  private near: Reson[];
  private roof: Reson[];
  private glass: Reson[];
  private helmet: Reson[];
  private cab: Reson[];
  private pings: Ping[];

  constructor(rate: number, seed: number) {
    this.rate = rate;
    this.s = seed >>> 0 || 0x9e3779b9;
    const mk = (bank: [number, number][]) => bank.map(([f, q]) => new Reson(rate, f, q));
    this.near = mk(NEAR);
    this.roof = mk(ROOF);
    this.glass = mk(GLASS);
    this.helmet = mk(HELMET);
    this.cab = mk(CAB);
    this.pings = Array.from({ length: 10 }, () => ({ on: false, ph: 0, f: 0, rise: 0, amp: 0, decay: 0, gl: 0, gr: 0 }));
    const bp = (f: number, q: number) => {
      const w = (2 * Math.PI * f) / rate, alpha = Math.sin(w) / (2 * q), a0 = 1 + alpha;
      return { b0: alpha / a0, a1: (-2 * Math.cos(w)) / a0, a2: (1 - alpha) / a0 };
    };
    this.wb = bp(3200, 0.45);
    this.sh = bp(2600, 0.6);
    this.sa = bp(380, 0.8);
    this.eNear = this.exp();
    this.ePing = this.exp();
    this.eBody = this.exp();
    this.eDrip = this.exp();
  }

  /** uniform 0…1 (xorshift32) */
  private u() {
    let s = this.s;
    s ^= s << 13;
    s ^= s >>> 17;
    s ^= s << 5;
    this.s = s >>> 0;
    return this.s / 4294967296;
  }

  private exp() {
    return -Math.log(1 - this.u());
  }

  /** a drop: an impulse of `amp` into the bank, between two of its resonators at `x` (0…bank length − 1), at `pan` −1…1 */
  private strike(bank: Reson[], x: number, amp: number, pan: number) {
    const k = Math.min(bank.length - 2, Math.floor(x)), f = Math.min(1, x - k);
    const a = this.u() < 0.5 ? -amp : amp;
    const th = ((pan + 1) * Math.PI) / 4, gl = Math.cos(th), gr = Math.sin(th);
    const r0 = bank[k], r1 = bank[k + 1];
    r0.el += a * (1 - f) * gl * r0.norm;
    r0.er += a * (1 - f) * gr * r0.norm;
    r1.el += a * f * gl * r1.norm;
    r1.er += a * f * gr * r1.norm;
  }

  /** a bubble's ping (a drop into a puddle, a drip): a sine whose pitch rises as it decays */
  private ping(f: number, rise: number, decay: number, amp: number, pan: number) {
    const p = this.pings.find((q) => !q.on);
    if (!p) return;
    const th = ((pan + 1) * Math.PI) / 4;
    p.on = true;
    p.ph = 0;
    p.f = (2 * Math.PI * f) / this.rate;
    p.rise = 1 + rise / this.rate;
    p.amp = amp;
    p.decay = Math.exp(-1 / (decay * this.rate));
    p.gl = Math.cos(th);
    p.gr = Math.sin(th);
  }

  /** Fill one block (both ears). */
  process(L: Float32Array, R: Float32Array) {
    const n = L.length, rate = this.rate, dt = n / rate;
    const ease = (tau: number) => 1 - Math.exp(-dt / tau);
    this.lv += (Math.min(1, Math.max(0, this.level)) - this.lv) * ease(0.6);
    this.cv += (Math.min(1, Math.max(0, this.cover)) - this.cv) * ease(0.12);
    this.cvSlow += (this.cv - this.cvSlow) * ease(0.3);
    this.v += (Math.max(0, this.speed) - this.v) * ease(0.08);
    for (const b of ['car', 'bike', 'train', 'none'] as const) this.bodyMix[b] += ((b === this.body ? 1 : 0) - this.bodyMix[b]) * ease(0.3);
    const lv = this.lv;
    if (lv < 1e-4 && this.level <= 0) {
      L.fill(0);
      R.fill(0);
      return;
    }
    // gusts: OU walks, one step per block
    const gauss = () => (this.u() + this.u() + this.u() - 1.5) * 2; // variance 1
    this.g1 += -this.g1 * (dt / 7) + Math.sqrt((2 * dt) / 7) * gauss();
    this.g2 += -this.g2 * (dt / 16) + Math.sqrt((2 * dt) / 16) * gauss();
    this.film += -this.film * (dt / 0.35) + Math.sqrt((2 * dt) / 0.35) * gauss();
    const gust = Math.max(-2.2, Math.min(2.2, 0.55 * this.g1 + 0.85 * this.g2)) * this.gusts;
    const v = this.v, open = 1 - this.cv, shelter = 1 - this.cvSlow;
    const bm = this.bodyMix;
    // what is outside the vehicle (the wash, the near fall, the drips), as much of it as its shell lets through
    const outside = (bm.car * OUTSIDE.car + bm.bike * OUTSIDE.bike + bm.train * OUTSIDE.train + bm.none * OUTSIDE.none) * this.layers.outside * LEVEL.outside;

    // wash: level ±3 dB and brightness with the gusts; muffled and lower under a roof
    const washGain = 0.075 * lv * Math.pow(10, (3 * gust) / 20) * (0.4 + 0.6 * shelter) * outside;
    const lpA = onePole(Math.min(16000, 7000 * Math.pow(2, 0.5 * gust)) * shelter + 750 * (1 - shelter), rate);
    const rumGain = 0.05 * lv * (0.6 + 0.4 * shelter) * Math.pow(10, (2 * gust) / 20) * outside;
    const rumA = onePole(160, rate);

    // the near fall: rate with the gusts; under a roof only what still reaches the open sides
    const gustRate = Math.exp(0.35 * gust);
    const nearRate = 2500 * lv * gustRate * (0.12 + 0.88 * open);
    const nearGain = 0.095 * outside;
    const pingRate = 5 * lv * gustRate * open;
    const dripRate = 4.5 * lv * this.cv;

    // the body: more drops with speed (it drives into the falling rain), none under a roof
    let bodyRate = 0;
    for (const b of ['car', 'bike', 'train'] as const) bodyRate += bm[b] * BODY[b].rate * (1 + v / BODY[b].vDouble);
    bodyRate *= lv * open * gustRate;
    const car = bm.car, bike = bm.bike, train = bm.train, bodySum = car + bike + train;
    const glassShare = car * Math.min(0.75, BODY.car.glass + v / 60) + train;

    // spray: hiss grows with speed, the arches' wash with it, puddles now and then
    const spray = (bm.car * SPRAY.car + bm.bike * SPRAY.bike + bm.train * SPRAY.train + bm.none * SPRAY.none) * lv * (0.55 + 0.45 * shelter);
    const sv = Math.min(1, v / 38);
    const sprayLevel = spray * sv * Math.sqrt(sv) * Math.pow(10, (2.5 * this.gusts * Math.max(-2, Math.min(2, this.film))) / 20) * this.layers.spray * LEVEL.spray;
    const puddleRate = v > 6 ? 0.35 * (v / 25) * lv * shelter * (bm.car + bm.bike) : 0;
    const puddleDecay = Math.exp(-dt / 0.45);

    const pNear = nearRate / rate, pPing = pingRate / rate, pBody = bodyRate / rate, pDrip = dripRate / rate;
    const wb = this.wb, sh = this.sh, sa = this.sa, wL = this.wbL, wR = this.wbR, hL = this.shL, hR = this.shR, aS = this.saS;
    const near = this.near, roof = this.roof, glass = this.glass, helmet = this.helmet, cab = this.cab;
    const bodyGain = (car * BODY.car.gain + bike * BODY.bike.gain + train * BODY.train.gain) * 0.16 * this.layers.body * LEVEL.body;
    // the banks that sound (a bank left behind rings out within ~0.3 s, while its body's share fades)
    if (this.u() < puddleRate * dt) this.puddleRise = 0.5 + this.u();
    const live = 1 | (car > 1e-3 ? 6 : 0) | (bike > 1e-3 ? 8 : 0) | (train > 1e-3 ? 16 : 0);
    for (let i = 0; i < n; i++) {
      // ---- events
      this.eNear -= pNear;
      while (this.eNear <= 0) {
        this.eNear += this.exp();
        // distance spread evenly over the ground from 1.5 to 25 m: loudness ∝ 1 / distance
        const r = Math.sqrt(2.25 + this.u() * (625 - 2.25)), amp = (1.5 / r) * (0.35 + 0.65 * this.u());
        // the far ones a little duller (leaves and the ground's lie between)
        const x = this.u() * (near.length - 1) * (0.55 + 0.45 * Math.min(1, amp * 3));
        this.strike(near, x, amp * nearGain, this.u() * 2 - 1);
      }
      this.ePing -= pPing;
      if (this.ePing <= 0) {
        this.ePing += this.exp();
        const r = 1.5 + this.u() * 12;
        this.ping(900 * Math.pow(4, this.u()), 15 + this.u() * 35, 0.006 + this.u() * 0.012, (0.05 / r) * outside, this.u() * 2 - 1);
      }
      this.eDrip -= pDrip;
      if (this.eDrip <= 0) {
        this.eDrip += this.exp();
        const pan = this.u() * 2 - 1;
        this.ping(650 * Math.pow(3, this.u()), 8 + this.u() * 20, 0.015 + this.u() * 0.025, (0.012 + this.u() * 0.02) * outside, pan);
        this.strike(near, this.u() * 3, (0.25 + 0.4 * this.u()) * nearGain, pan);
      }
      this.eBody -= pBody;
      while (this.eBody <= 0 && bodySum > 0.01) {
        this.eBody += this.exp();
        // drop sizes: many small, few big (the impact's loudness ∝ about the drop's mass)
        const u = this.u(), amp = u * u * u * bodyGain;
        const pick = this.u() * bodySum;
        if (pick < car) {
          const w = BODY.car.width * (this.u() * 2 - 1);
          if (this.u() < glassShare / Math.max(1e-6, car)) this.strike(glass, this.u() * (glass.length - 1), amp * 0.7, w);
          else this.strike(roof, this.u() * (roof.length - 1), amp, w);
        } else if (pick < car + bike) this.strike(helmet, this.u() * (helmet.length - 1), amp, BODY.bike.width * (this.u() * 2 - 1));
        else this.strike(cab, this.u() * (cab.length - 1), amp, BODY.train.width * (this.u() * 2 - 1));
      }
      // ---- wash: own noise per ear above the rumble, the rumble shared
      const nl = this.u() * 2 - 1, nr = this.u() * 2 - 1, nc = this.u() * 2 - 1;
      let yl = wb.b0 * (nl - wL[1]) - wb.a1 * wL[2] - wb.a2 * wL[3];
      wL[1] = wL[0];
      wL[0] = nl;
      wL[3] = wL[2];
      wL[2] = yl;
      let yr = wb.b0 * (nr - wR[1]) - wb.a1 * wR[2] - wb.a2 * wR[3];
      wR[1] = wR[0];
      wR[0] = nr;
      wR[3] = wR[2];
      wR[2] = yr;
      this.lpL += (yl - this.lpL) * lpA;
      this.lpR += (yr - this.lpR) * lpA;
      this.rum1 += (nc - this.rum1) * rumA;
      this.rum2 += (this.rum1 - this.rum2) * rumA;
      const rum = this.rum2 * rumGain * 1.6;
      let outL = this.lpL * washGain + rum, outR = this.lpR * washGain + rum;

      // ---- resonators (drops)
      for (let b = 0; b < 5; b++) {
        if (!(live & (1 << b))) continue;
        const bank = b === 0 ? near : b === 1 ? roof : b === 2 ? glass : b === 3 ? helmet : cab;
        for (let k = 0; k < bank.length; k++) {
          const q = bank[k];
          const xl = q.el, xr = q.er;
          q.el = 0;
          q.er = 0;
          const ol = q.b0 * (xl - q.xl2) - q.a1 * q.l1 - q.a2 * q.l2;
          q.xl2 = q.xl1;
          q.xl1 = xl;
          q.l2 = q.l1;
          q.l1 = ol;
          const or = q.b0 * (xr - q.xr2) - q.a1 * q.r1 - q.a2 * q.r2;
          q.xr2 = q.xr1;
          q.xr1 = xr;
          q.r2 = q.r1;
          q.r1 = or;
          outL += ol;
          outR += or;
        }
      }
      // ---- pings
      for (let k = 0; k < this.pings.length; k++) {
        const p = this.pings[k];
        if (!p.on) continue;
        const s = Math.sin(p.ph) * p.amp;
        outL += s * p.gl;
        outR += s * p.gr;
        p.ph += p.f;
        p.f *= p.rise;
        p.amp *= p.decay;
        if (p.amp < 1e-5) p.on = false;
      }
      // ---- spray: hiss per ear (half shared: it comes from both sides of the car), arches' wash shared
      if (sprayLevel > 1e-5) {
        const hl = 0.6 * nl + 0.8 * nc, hr = 0.6 * nr + 0.8 * nc;
        yl = sh.b0 * (hl - hL[1]) - sh.a1 * hL[2] - sh.a2 * hL[3];
        hL[1] = hL[0];
        hL[0] = hl;
        hL[3] = hL[2];
        hL[2] = yl;
        yr = sh.b0 * (hr - hR[1]) - sh.a1 * hR[2] - sh.a2 * hR[3];
        hR[1] = hR[0];
        hR[0] = hr;
        hR[3] = hR[2];
        hR[2] = yr;
        const xa = nc;
        const ya = sa.b0 * (xa - aS[1]) - sa.a1 * aS[2] - sa.a2 * aS[3];
        aS[1] = aS[0];
        aS[0] = xa;
        aS[3] = aS[2];
        aS[2] = ya;
        const swell = 1 + 2.2 * this.puddle;
        const hiss = 0.05 * sprayLevel * (1 + 0.6 * this.puddle), arch = 0.065 * sprayLevel * swell;
        outL += yl * hiss + ya * arch;
        outR += yr * hiss + ya * arch;
      }
      L[i] = outL;
      R[i] = outR;
    }
    // a puddle swells in ~60 ms and dies over ~0.45 s
    this.puddle += (this.puddleRise - this.puddle) * ease(0.06);
    this.puddleRise *= puddleDecay;
  }
}
