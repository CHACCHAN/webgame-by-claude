// The grains over the menus, as a cloud of fine points in depth: the simulation (no DOM: tested in Node).
// Tens of thousands of grains float in a volume behind the screen's plane. A group of them can be given a shape:
// points in the shape's own space, placed (turned, sized, moved) anew every frame. The grains then fly to their
// places and stay there, each a little alive; freed, they drift off again. The grains alone make the picture: a
// course's relief, a glyph, the edge of what is selected. Drawing: cloudRender.ts; what is shown where: Cloud.tsx.

/** the groups a grain can belong to: dust that only floats, the thing a screen shows, the edge of the selection */
export const AMBIENT = 0, OBJECT = 1, EMPHASIS = 2;
/** of every 16 grains: 5 float, 8 depict, 3 mark the selection (interleaved: any first part of the cloud has all three) */
const PATTERN = [0, 1, 1, 2, 1, 0, 1, 1, 0, 2, 1, 1, 0, 1, 2, 0];

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
  /** 0–1: this share of the group is in the shape, the rest floats (a picture that fills up) */
  fill: number;
}

export interface Cloud {
  n: number;
  /** only the first `active` grains live (a slow machine gets fewer) */
  active: number;
  w: number;
  h: number;
  /** the volume's half depth, pixels */
  deep: number;
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
  group: Uint8Array;
  /** the grain is the rank-th of its group */
  rank: Uint32Array;
  /** 0–1: how much the grain is in its place */
  held: Float32Array;
  shapes: (Shape | null)[];
  places: Placement[];
  /** when each group got its shape (grains leave for it one after another) */
  since: number[];
  /** r, g, b per tone */
  palette: Float32Array;
  time: number;
  /** the pointer on the screen's plane (NaN: none) */
  px: number;
  py: number;
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
    n, active: n, w, h, deep: 520,
    pos: new Float32Array(n * 3), vel: new Float32Array(n * 3), col: new Float32Array(n * 3), lum: new Float32Array(n),
    size: new Float32Array(n), seed: new Float32Array(n), s2: new Float32Array(n), s3: new Float32Array(n), look: new Uint8ClampedArray(n * 8), tick: 0, group: new Uint8Array(n), rank: new Uint32Array(n), held: new Float32Array(n),
    shapes: [null, null, null],
    places: [0, 1, 2].map(() => ({ x: 0, y: 0, z: 0, scale: 1, yaw: 0, pitch: 0, fill: 1 })),
    since: [0, 0, 0], palette, time: 0, px: NaN, py: NaN,
  };
  const count = [0, 0, 0];
  for (let i = 0; i < n; i++) {
    const g = PATTERN[i % 16];
    c.group[i] = g;
    c.rank[i] = count[g]++;
    c.seed[i] = rand();
    c.s2[i] = frac(c.seed[i] * 7.31 + 0.17);
    c.s3[i] = frac(c.seed[i] * 13.7 + 0.61);
    c.pos[i * 3] = rand() * w;
    c.pos[i * 3 + 1] = rand() * h;
    c.pos[i * 3 + 2] = (rand() * 2 - 1) * c.deep;
    c.col[i * 3] = palette[0];
    c.col[i * 3 + 1] = palette[1];
    c.col[i * 3 + 2] = palette[2];
    c.size[i] = 1;
  }
  return c;
}

/** how many grains of a group there are among the first `active` */
export function members(c: Cloud, group: number, active = c.active): number {
  let m = Math.floor(active / 16) * PATTERN.filter((g) => g === group).length;
  for (let k = 0; k < active % 16; k++) if (PATTERN[k] === group) m++;
  return m;
}

/** The screen changed its size: the floating grains keep their places in proportion. */
export function resizeCloud(c: Cloud, w: number, h: number) {
  const sx = w / (c.w || 1), sy = h / (c.h || 1);
  for (let i = 0; i < c.n; i++) {
    if (c.held[i] > 0.5) continue;
    c.pos[i * 3] *= sx;
    c.pos[i * 3 + 1] *= sy;
  }
  c.w = w;
  c.h = h;
}

/** Give a group a shape (its grains fly to it), another one (they move over), or none (they float off). */
export function bind(c: Cloud, group: number, shape: Shape | null) {
  if (c.shapes[group] === shape) return;
  const had = c.shapes[group];
  c.shapes[group] = shape;
  c.since[group] = c.time;
  if (!shape && had) scatter(c, group);
}

const anywhere = rng(4099);
/**
 * A shape let go dissolves into the dust: each of its grains is sent off to some place of its own in the volume
 * (the flow alone would carry the whole lump along for minutes: it has no sources or sinks).
 */
export function scatter(c: Cloud, group: number) {
  const f = c.h * FOCAL, near = -f * 0.55;
  // (a floating grain loses its speed at 0.9 a second, see stepCloud: with this much it comes to rest there)
  const rate = 0.9;
  for (let i = 0; i < c.active; i++) {
    if (c.group[i] !== group || c.held[i] < 0.2) continue;
    const a = i * 3;
    c.vel[a] += ((anywhere() * 1.44 - 0.22) * c.w - c.pos[a]) * rate;
    c.vel[a + 1] += ((anywhere() * 1.44 - 0.22) * c.h - c.pos[a + 1]) * rate;
    c.vel[a + 2] += (near + anywhere() * (c.deep - near) - c.pos[a + 2]) * rate;
  }
}

/** A push outward from where the group's shape stands (a choice made, a shape let go). */
export function burst(c: Cloud, group: number, speed: number) {
  const p = c.places[group];
  for (let i = 0; i < c.active; i++) {
    if (c.group[i] !== group || c.held[i] < 0.2) continue;
    const dx = c.pos[i * 3] - p.x, dy = c.pos[i * 3 + 1] - p.y, dz = c.pos[i * 3 + 2] - p.z;
    const d = Math.hypot(dx, dy, dz) + 1;
    const s = speed * (0.4 + 1.2 * frac(c.seed[i] * 7.31 + 0.17));
    c.vel[i * 3] += (dx / d) * s;
    c.vel[i * 3 + 1] += (dy / d) * s;
    c.vel[i * 3 + 2] += (dz / d) * s - s * 0.6;
  }
}

/** A change of screen: the floating grains rush past the eye (forward) or fall back from it. */
export function sweep(c: Cloud, dir: number) {
  for (let i = 0; i < c.active; i++) {
    if (c.held[i] > 0.5) continue;
    const s = 0.35 + frac(c.seed[i] * 13.7 + 0.61);
    c.vel[i * 3 + 2] -= dir * 620 * s;
    c.vel[i * 3] += (c.pos[i * 3] - c.w / 2) * 0.5 * dir * s;
    c.vel[i * 3 + 1] += (c.pos[i * 3 + 1] - c.h / 2) * 0.5 * dir * s;
  }
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

const DUST_TONE = 0;

// sines from a table (the grains' wandering needs no better, and there are tens of thousands of them every frame)
const LUT = 2048, SIN = new Float32Array(LUT), TO_LUT = LUT / (2 * Math.PI);
for (let k = 0; k < LUT; k++) SIN[k] = Math.sin(k / TO_LUT);
const lsin = (x: number) => SIN[((x * TO_LUT) | 0) & (LUT - 1)];
const lcos = (x: number) => SIN[((x * TO_LUT + LUT / 4) | 0) & (LUT - 1)];
const mats = new Float64Array(27), falls = new Float64Array(9);

/**
 * One step. What changes slowly (the flow that carries a floating grain, a grain's brightness, colour and size) is
 * worked out for a quarter of the grains each step, in turn; where a grain is, every step.
 */
export function stepCloud(c: Cloud, dt: number) {
  c.time += dt;
  c.tick++;
  const t = c.time, tick = c.tick, { pos, vel, col, lum, size, seed, s2: S2, s3: S3, held, palette, look, group, rank } = c;
  const f = c.h * FOCAL, cx = c.w / 2, cy = c.h / 2;
  const pointer = Number.isFinite(c.px), px = c.px, py = c.py;
  // per group: the placement as a matrix (yaw about y, then pitch about x)
  for (let g = 0; g < 3; g++) {
    const p = c.places[g];
    const cyw = Math.cos(p.yaw), syw = Math.sin(p.yaw), cp = Math.cos(p.pitch), sp = Math.sin(p.pitch), s = p.scale;
    mats.set([cyw * s, 0, syw * s, sp * syw * s, cp * s, -sp * cyw * s, -cp * syw * s, sp * s, cp * cyw * s], g * 9);
    // (how fast a travelling point moves on the screen: its grain is carried along, not dragged behind)
    const fall = c.shapes[g]?.fall, m = g * 9;
    for (let k = 0; k < 3; k++) falls[g * 3 + k] = fall ? (mats[m + k * 3] * fall.x + mats[m + k * 3 + 1] * fall.y + mats[m + k * 3 + 2] * fall.z) * fall.rate : 0;
  }
  const dt4 = Math.min(dt * 4, 0.2), ease = Math.min(1, dt4 * 5), easeHeld = Math.min(1, dt4 * 4);
  // the volume the floating grains live in (wider than the screen: the near grains spread beyond it)
  const mx = c.w * 0.22, my = c.h * 0.22, D = c.deep, near = -f * 0.55;
  const spanX = c.w + 2 * mx, spanY = c.h + 2 * my, spanZ = D - near, maxX = c.w + mx, maxY = c.h + my;
  for (let i = 0; i < c.active; i++) {
    const a = i * 3, g = group[i], shape = c.shapes[g], sd = seed[i], s2 = S2[i], s3 = S3[i];
    const turn = ((i + tick) & 3) === 0;
    let x = pos[a], y = pos[a + 1], z = pos[a + 2];
    let wantLum = 0, wantSize = 1, tone = DUST_TONE, wantHeld = 0;
    // the grain's turn to leave for the shape comes a moment after the shape (not all at once: they pour in)
    const place = c.places[g];
    if (shape !== null && s3 <= place.fill && t - c.since[g] >= sd * 0.45) {
      const pts = shape.points, k = rank[i] % (pts.length / 3), m = g * 9, k3 = k * 3;
      let lx = pts[k3], ly = pts[k3 + 1], lz = pts[k3 + 2];
      let vx = 0, vy = 0, vz = 0, shown = 1, again = false;
      const fall = shape.fall;
      if (fall !== undefined && shape.along !== undefined && shape.along[k] >= 0) {
        const u = frac(shape.along[k] + t * fall.rate), at = u - 0.5;
        lx += fall.x * at;
        ly += fall.y * at;
        lz += fall.z * at;
        vx = falls[g * 3];
        vy = falls[g * 3 + 1];
        vz = falls[g * 3 + 2];
        shown = lsin(u * Math.PI);
        again = u < fall.rate * dt * 1.5;
      }
      // a small orbit around its place: the shape breathes
      const w = t * (0.5 + 1.3 * s2) + sd * 40, r = shape.loose * (0.3 + s3), sw = lsin(w);
      const dx = mats[m] * lx + mats[m + 1] * ly + mats[m + 2] * lz + place.x + lcos(w) * r - x;
      const dy = mats[m + 3] * lx + mats[m + 4] * ly + mats[m + 5] * lz + place.y + lsin(w * 0.83 + 1.7) * r - y;
      const dz = mats[m + 6] * lx + mats[m + 7] * ly + mats[m + 8] * lz + place.z + sw * r - z;
      const d = Math.sqrt(dx * dx + dy * dy + dz * dz);
      // a spring, each grain its own (they do not arrive as one), and a turn about the way there: they spiral in
      const k1 = 26 + 46 * s2, damp = 2 * Math.sqrt(k1) * 0.82;
      const swirl = (d < 140 ? d / 140 : 1) * k1 * 1.1 * (s3 - 0.35);
      if (again && d < 400) {
        // its point started again at the other end: so does the grain (it does not fly back through the picture)
        x += dx;
        y += dy;
        z += dz;
        vel[a] = vx;
        vel[a + 1] = vy;
        vel[a + 2] = vz;
      } else {
        vel[a] += (dx * k1 - (vel[a] - vx) * damp - dy * swirl) * dt;
        vel[a + 1] += (dy * k1 - (vel[a + 1] - vy) * damp + dx * swirl) * dt;
        vel[a + 2] += (dz * k1 - (vel[a + 2] - vz) * damp) * dt;
        x += vel[a] * dt;
        y += vel[a + 1] * dt;
        z += vel[a + 2] * dt;
      }
      if (turn) {
        wantHeld = d < 26 ? 1 : 0.35;
        let l = (shape.lum ? shape.lum[k] : 1) * shape.gain;
        if (shape.along && shape.wave) {
          // the running light: a crest that goes round, twice the brightness where it is
          const u = frac(shape.along[k] - t * shape.wave);
          l *= 0.62 + 1.1 * Math.exp(-u * 9) + 0.5 * Math.exp(-(1 - u) * 28);
        }
        wantLum = l * shown * (d < 60 ? 1 : 0.55);
        wantSize = shape.size * (0.75 + 0.5 * s2);
        tone = shape.tones ? shape.tones[k] : shape.tone;
      }
    } else {
      if (turn) {
        // floating: a steady three-dimensional flow without sources or sinks (the grains never bunch up), slow
        const q = 1 / 210, ph = sd * 6.283;
        const speed = 9 + 13 * s2;
        const fx = lsin(z * q + t * 0.11 + ph) + lcos(y * q - t * 0.07);
        const fy = lsin(x * q - t * 0.09 + ph) + lcos(z * q + t * 0.05) - 0.28;
        const fz = lsin(y * q + t * 0.08) + lcos(x * q - t * 0.06 + ph);
        const rate = 0.9 * dt4;
        vel[a] += (fx * speed - vel[a]) * rate;
        vel[a + 1] += (fy * speed - vel[a + 1]) * rate;
        vel[a + 2] += (fz * speed * 0.8 - vel[a + 2]) * rate;
        if (pointer) {
          // around the pointer (where the grain is seen, not where it is) they turn and keep a little off it
          const s = f / (f + z);
          const dx = cx + (x - cx) * s - px, dy = cy + (y - cy) * s - py;
          const d2 = dx * dx + dy * dy, R = 170;
          if (d2 < R * R) {
            const d = Math.sqrt(d2) + 1, push = ((1 - d / R) * 190 * s * dt4) / d;
            vel[a] += -dy * push + dx * push * 0.4;
            vel[a + 1] += dx * push + dy * push * 0.4;
          }
        }
        // dust: a few of the grains bright (the renderer dims and blurs the near and the far ones)
        wantLum = (0.16 + 0.5 * s2 * s2 * s2) * (shape ? 0.6 : 1);
        wantSize = 1 + 1.3 * s3 * s3;
      }
      x += vel[a] * dt;
      y += vel[a + 1] * dt;
      z += vel[a + 2] * dt;
      // out at one side of the volume, in at the other
      if (x < -mx) x += spanX;
      else if (x > maxX) x -= spanX;
      if (y < -my) y += spanY;
      else if (y > maxY) y -= spanY;
      if (z < near) z += spanZ;
      else if (z > D) z -= spanZ;
    }
    pos[a] = x;
    pos[a + 1] = y;
    pos[a + 2] = z;
    if (turn) {
      held[i] += (wantHeld - held[i]) * easeHeld;
      lum[i] += (wantLum - lum[i]) * ease;
      size[i] += (wantSize - size[i]) * ease;
      const p3 = tone * 3, b = i * 8;
      col[a] += (palette[p3] - col[a]) * ease;
      col[a + 1] += (palette[p3 + 1] - col[a + 1]) * ease;
      col[a + 2] += (palette[p3 + 2] - col[a + 2]) * ease;
      look[b] = col[a] * 255;
      look[b + 1] = col[a + 1] * 255;
      look[b + 2] = col[a + 2] * 255;
      look[b + 3] = lum[i] * 255;
      look[b + 4] = size[i] * 31.875;
      look[b + 5] = sd * 255;
    }
  }
}
