// The grains of the menus: the simulation (no DOM: tested in Node).
// The grains are there only to depict a thing: a course's relief, a glyph, a sky, a medal (shapes.ts). A thing is a
// shape: points in its own space, placed (turned, sized, moved) anew every frame. While nothing is shown there are
// no grains at all, and a step costs nothing. A thing asked for condenses: its grains come into being around their
// places in wisps and draw together; let go, it comes apart like ink in water and is gone within a second. The
// grains hang in a fluid (fluid.ts) that the pointer stirs: a stroke through a picture carries its grains off in
// two eddies, and they find their way back as the water comes to rest.
// (Owner 11-12: the dust all over the screen and the grains around every button were too much. So: no dust, no
// ornaments; the grains are a picture in a few places, or they are not there.)
// Drawing: cloudRender.ts / cloudRenderGpu.ts; what is shown where: Cloud.tsx.
import { createFluid, stepFluid, type Fluid } from './fluid';

export interface Shape {
  /** x, y, z per point in the shape's own space, in an order in which any first part is an even sample */
  points: Float32Array;
  /** brightness per point, 0–1 (all 1 without it) */
  lum?: Float32Array;
  /** colour per point: an index into the cloud's palette (the shape's `tone` without it) */
  tones?: Uint8Array;
  tone: number;
  /** how far a grain wanders around its place, pixels */
  loose: number;
  /** the grains' size, pixels at the screen's plane */
  size: number;
  /** all brightness times this (a small shape with many grains would burn out) */
  gain: number;
  /** a light that runs through the shape: per point where it is along the shape (0–1); `wave` turns a second */
  along?: Float32Array;
  wave?: number;
  /**
   * Points that travel: every point with `along` ≥ 0 moves this far through the shape's own space in one cycle
   * (`rate` cycles a second, `along` its phase), then starts again at the other end, dark at both ends (rain).
   */
  fall?: { x: number; y: number; z: number; rate: number };
  /** where its picture is in its own space, as it is shown (centre x, centre y, width, height): what fits it into a box */
  box?: [number, number, number, number];
}

/** Where a shape stands: its own space turned (yaw about its y, then pitch about x), sized and moved to the screen. */
export interface Placement {
  x: number;
  y: number;
  z: number;
  scale: number;
  yaw: number;
  pitch: number;
  /** 0–1: this share of the grains is there (a picture that fills up) */
  fill: number;
}

/** a grain is not there, on its way to its place or in it, or let go and fading */
export const GONE = 0, PLACED = 1, FREE = 2;

export interface Cloud {
  n: number;
  /** only the first `active` grains are used (a slow machine gets fewer) */
  active: number;
  w: number;
  h: number;
  pos: Float32Array;
  vel: Float32Array;
  /** colour (r, g, b: 0–1), brightness and size as they are now (they ease to what the grain's place asks) */
  col: Float32Array;
  lum: Float32Array;
  size: Float32Array;
  seed: Float32Array;
  /** two more numbers per grain, 0–1, made from its seed */
  s2: Float32Array;
  s3: Float32Array;
  /** what the renderers draw a grain with, eight bytes each: r, g, b, brightness, size / 8, seed (written here) */
  look: Uint8ClampedArray;
  /** steps so far (what changes slowly is worked out for a quarter of the grains each step) */
  tick: number;
  /** GONE / PLACED / FREE per grain */
  state: Uint8Array;
  /** how many grains were there at the last step (none, and nothing to show: nothing needs to be stepped or drawn) */
  live: number;
  shape: Shape | null;
  place: Placement;
  /** when the shape was given (its grains leave for it one after another) */
  since: number;
  /** r, g, b per tone */
  palette: Float32Array;
  time: number;
  /** the water the grains hang in */
  fluid: Fluid;
}

/** the distance of the eye from the screen's plane, in screen heights */
export const FOCAL = 1.25;
const frac = (v: number) => v - Math.floor(v);

/** A deterministic stream of numbers (mulberry32): the cloud looks the same every time it is made. */
export function rng(seed: number) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function createCloud(n: number, w: number, h: number, palette: Float32Array): Cloud {
  const rand = rng(20261111);
  const c: Cloud = {
    n, active: n, w, h,
    pos: new Float32Array(n * 3), vel: new Float32Array(n * 3), col: new Float32Array(n * 3), lum: new Float32Array(n),
    size: new Float32Array(n), seed: new Float32Array(n), s2: new Float32Array(n), s3: new Float32Array(n), look: new Uint8ClampedArray(n * 8), tick: 0,
    state: new Uint8Array(n), live: 0, shape: null,
    place: { x: 0, y: 0, z: 0, scale: 1, yaw: 0, pitch: 0, fill: 1 },
    since: 0, palette, time: 0, fluid: createFluid(w, h),
  };
  for (let i = 0; i < n; i++) {
    c.seed[i] = rand();
    c.s2[i] = frac(c.seed[i] * 7.31 + 0.17);
    c.s3[i] = frac(c.seed[i] * 13.7 + 0.61);
    c.size[i] = 1;
  }
  return c;
}

/** The screen changed its size (the water starts anew, at rest). */
export function resizeCloud(c: Cloud, w: number, h: number) {
  c.w = w;
  c.h = h;
  c.fluid = createFluid(w, h);
}

/** Show a shape (its grains condense around it), another one (they move over), or none (they come apart and fade). */
export function bind(c: Cloud, shape: Shape | null) {
  if (c.shape === shape) return;
  c.shape = shape;
  c.since = c.time;
}

/** Where a point of the volume is on the screen, and how large things are there (1 at the screen's plane). */
export function project(c: Cloud, x: number, y: number, z: number, out: [number, number, number]) {
  const f = c.h * FOCAL;
  const s = f / (f + z);
  out[0] = c.w / 2 + (x - c.w / 2) * s;
  out[1] = c.h / 2 + (y - c.h / 2) * s;
  out[2] = s;
  return out;
}

// sines from a table (the grains' wandering needs no better, and there are tens of thousands of them every frame)
const LUT = 2048, SIN = new Float32Array(LUT), TO_LUT = LUT / (2 * Math.PI);
for (let k = 0; k < LUT; k++) SIN[k] = Math.sin(k / TO_LUT);
const lsin = (x: number) => SIN[((x * TO_LUT) | 0) & (LUT - 1)];
const lcos = (x: number) => SIN[((x * TO_LUT + LUT / 4) | 0) & (LUT - 1)];
const mat = new Float64Array(9);
/** a flow this fast (pixels a second) halves the pull of a grain's place: the water carries it, then lets it home */
const CARRIED = 150;

/**
 * One step. What changes slowly (a grain's brightness, colour and size, the drift of a grain let go) is worked out
 * for a quarter of the grains each step, in turn; where a grain is, every step. Grains that are not there cost a
 * comparison.
 */
export function stepCloud(c: Cloud, dt: number) {
  c.time += dt;
  c.tick++;
  const fl = c.fluid;
  stepFluid(fl, dt);
  const shape = c.shape, place = c.place;
  if (shape === null && c.live === 0) return;
  const t = c.time, tick = c.tick, { pos, vel, col, lum, size, seed, s2: S2, s3: S3, palette, look, state } = c;
  const f = c.h * FOCAL, cx = c.w / 2, cy = c.h / 2;
  // the placement as a matrix (yaw about y, then pitch about x)
  {
    const cyw = Math.cos(place.yaw), syw = Math.sin(place.yaw), cp = Math.cos(place.pitch), sp = Math.sin(place.pitch), s = place.scale;
    mat.set([cyw * s, 0, syw * s, sp * syw * s, cp * s, -sp * cyw * s, -cp * syw * s, sp * s, cp * cyw * s]);
  }
  const m0 = mat[0], m1 = mat[1], m2 = mat[2], m3 = mat[3], m4 = mat[4], m5 = mat[5], m6 = mat[6], m7 = mat[7], m8 = mat[8];
  // (how fast a travelling point moves on the screen: its grain is carried along, not dragged behind)
  const fall = shape?.fall, along = shape?.along;
  const fvx = fall ? (m0 * fall.x + m1 * fall.y + m2 * fall.z) * fall.rate : 0;
  const fvy = fall ? (m3 * fall.x + m4 * fall.y + m5 * fall.z) * fall.rate : 0;
  const fvz = fall ? (m6 * fall.x + m7 * fall.y + m8 * fall.z) * fall.rate : 0;
  const pts = shape ? shape.points : null, np = pts ? pts.length / 3 : 1;
  const flowing = !fl.still, fu = fl.u, fv = fl.v, fnx = fl.nx, fny = fl.ny, toCell = 1 / fl.cell, soften = 1 / (CARRIED * CARRIED);
  const dt4 = Math.min(dt * 4, 0.2), ease = Math.min(1, dt4 * 5);
  // how far from its place a grain comes into being
  const R = c.h * 0.12;
  const fill = place.fill, since = c.since;
  let live = 0;
  for (let i = 0; i < c.active; i++) {
    const sd = seed[i], s3 = S3[i], st = state[i];
    const wanted = pts !== null && s3 <= fill;
    // the grain's turn to leave for the shape comes a moment after the shape (not all at once: they pour in)
    const due = wanted && t - since >= sd * 0.45;
    if (st === GONE && !due) continue;
    live++;
    const a = i * 3, s2 = S2[i], b = i * 8;
    const turn = ((i + tick) & 3) === 0;
    let x = pos[a], y = pos[a + 1], z = pos[a + 2];
    // the water where the grain is seen
    let ux = 0, uy = 0;
    if (flowing && st !== GONE) {
      const s = f / (f + z), gx = (cx + (x - cx) * s) * toCell + 1.5, gy = (cy + (y - cy) * s) * toCell + 1.5;
      if (gx >= 0 && gy >= 0 && gx < fnx - 1 && gy < fny - 1) {
        const i0 = gx | 0, j0 = gy | 0, tx = gx - i0, ty = gy - j0, o = j0 * fnx + i0;
        const k00 = (1 - tx) * (1 - ty), k10 = tx * (1 - ty), k01 = (1 - tx) * ty, k11 = tx * ty;
        ux = fu[o] * k00 + fu[o + 1] * k10 + fu[o + fnx] * k01 + fu[o + fnx + 1] * k11;
        uy = fv[o] * k00 + fv[o + 1] * k10 + fv[o + fnx] * k01 + fv[o + fnx + 1] * k11;
      }
    }
    if (due) {
      const sh = shape as Shape, P = sh.points, k = i % np, k3 = k * 3;
      let lx = P[k3], ly = P[k3 + 1], lz = P[k3 + 2];
      let vx = 0, vy = 0, vz = 0, shown = 1, again = false;
      if (fall !== undefined && along !== undefined && along[k] >= 0) {
        const u = frac(along[k] + t * fall.rate), at = u - 0.5;
        lx += fall.x * at;
        ly += fall.y * at;
        lz += fall.z * at;
        vx = fvx;
        vy = fvy;
        vz = fvz;
        shown = lsin(u * Math.PI);
        again = u < fall.rate * dt * 1.5;
      }
      const tx = m0 * lx + m1 * ly + m2 * lz + place.x, ty = m3 * lx + m4 * ly + m5 * lz + place.y, tz = m6 * lx + m7 * ly + m8 * lz + place.z;
      if (st === GONE) {
        // it comes into being off its place, with its neighbours on one side of theirs: wisps that draw together
        const ang = 3.1 * (lsin(tx * 0.013 + ty * 0.007) + lcos(ty * 0.017 - tx * 0.005)) + (s2 - 0.5) * 0.9;
        const r = R * (0.25 + 1.1 * s2), ca = lcos(ang), sa = lsin(ang);
        x = tx + ca * r;
        y = ty + sa * r;
        z = tz + (sd - 0.5) * 2 * R;
        vel[a] = -sa * r * 1.6 + vx;
        vel[a + 1] = ca * r * 1.6 + vy;
        vel[a + 2] = vz;
        lum[i] = 0;
        size[i] = sh.size;
        const p3 = (sh.tones ? sh.tones[k] : sh.tone) * 3;
        col[a] = palette[p3];
        col[a + 1] = palette[p3 + 1];
        col[a + 2] = palette[p3 + 2];
      }
      state[i] = PLACED;
      // a small orbit around its place: the shape breathes
      const w = t * (0.5 + 1.3 * s2) + sd * 40, r = sh.loose * (0.3 + s3), sw = lsin(w);
      const dx = tx + lcos(w) * r - x, dy = ty + lsin(w * 0.83 + 1.7) * r - y, dz = tz + sw * r - z;
      const d = Math.sqrt(dx * dx + dy * dy + dz * dz);
      if (again && d < 400) {
        // its point started again at the other end: so does the grain (it does not fly back through the picture)
        x += dx;
        y += dy;
        z += dz;
        vel[a] = vx;
        vel[a + 1] = vy;
        vel[a + 2] = vz;
      } else {
        // a spring, each grain its own (they do not arrive as one), and a turn about the way there: they spiral in.
        // Where the water runs the spring is weak: the grain goes with the water and comes home when it rests.
        const k0 = 26 + 46 * s2, damp = 2 * Math.sqrt(k0) * 0.82;
        const k1 = flowing ? k0 / (1 + (ux * ux + uy * uy) * soften) : k0;
        const swirl = (d < 140 ? d / 140 : 1) * k1 * 1.1 * (s3 - 0.35);
        vel[a] += (dx * k1 - (vel[a] - vx) * damp - dy * swirl) * dt;
        vel[a + 1] += (dy * k1 - (vel[a + 1] - vy) * damp + dx * swirl) * dt;
        vel[a + 2] += (dz * k1 - (vel[a + 2] - vz) * damp) * dt;
        x += (vel[a] + ux) * dt;
        y += (vel[a + 1] + uy) * dt;
        z += vel[a + 2] * dt;
      }
      if (turn) {
        let l = (sh.lum ? sh.lum[k] : 1) * sh.gain;
        if (along && sh.wave) {
          // the running light: a crest that goes round, twice the brightness where it is
          const u = frac(along[k] - t * sh.wave);
          l *= 0.62 + 1.1 * Math.exp(-u * 9) + 0.5 * Math.exp(-(1 - u) * 28);
        }
        const wantLum = l * shown * (d < 60 ? 1 : 0.55), wantSize = sh.size * (0.75 + 0.5 * s2);
        const p3 = (sh.tones ? sh.tones[k] : sh.tone) * 3;
        lum[i] += (wantLum - lum[i]) * ease;
        size[i] += (wantSize - size[i]) * ease;
        col[a] += (palette[p3] - col[a]) * ease;
        col[a + 1] += (palette[p3 + 1] - col[a + 1]) * ease;
        col[a + 2] += (palette[p3 + 2] - col[a + 2]) * ease;
      }
    } else if (wanted) {
      // another shape is coming and this grain's turn has not: it stays where it is, as it is
      const slow = 1 - Math.min(1, dt * 6);
      vel[a] *= slow;
      vel[a + 1] *= slow;
      vel[a + 2] *= slow;
      x += (vel[a] + ux) * dt;
      y += (vel[a + 1] + uy) * dt;
      z += vel[a + 2] * dt;
    } else {
      // let go: ink in water. One slow turbulence for all of them (the picture shears into strands, it does not
      // fuzz), a little upward, and whatever the water does; fainter all the while, then gone.
      state[i] = FREE;
      if (turn) {
        const q = 1 / 46, speed = 46 + 44 * s2, ph = sd * 0.7;
        const gx = lsin(y * q + t * 0.5 + ph) + lcos(z * q - t * 0.37);
        const gy = lsin(x * q - t * 0.43 + ph) + lcos(z * q + t * 0.29) - 0.45;
        const gz = lsin(y * q + t * 0.41) + lcos(x * q - t * 0.31 + ph);
        const rate = 2.4 * dt4;
        vel[a] += (gx * speed - vel[a]) * rate;
        vel[a + 1] += (gy * speed - vel[a + 1]) * rate;
        vel[a + 2] += (gz * speed - vel[a + 2]) * rate;
        lum[i] -= lum[i] * Math.min(1, dt4 * (3.4 + 3 * s2));
        size[i] += (2.4 - size[i]) * dt4 * 0.5;
        if (lum[i] < 0.02) {
          lum[i] = 0;
          state[i] = GONE;
          vel[a] = vel[a + 1] = vel[a + 2] = 0;
          live--;
        }
      }
      x += (vel[a] + ux) * dt;
      y += (vel[a + 1] + uy) * dt;
      z += vel[a + 2] * dt;
    }
    pos[a] = x;
    pos[a + 1] = y;
    pos[a + 2] = z;
    if (turn) {
      look[b] = col[a] * 255;
      look[b + 1] = col[a + 1] * 255;
      look[b + 2] = col[a + 2] * 255;
      look[b + 3] = lum[i] * 255;
      look[b + 4] = size[i] * 31.875;
      look[b + 5] = sd * 255;
    }
  }
  // (grains past `active`, left there when a slow machine was given fewer: they are not drawn, and gone)
  c.live = live;
}
