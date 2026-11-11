// The grains of the interface: a field of floating points that gathers into the outline of whatever is selected
// (owner 11-11: "grains float → over an option they change shape and become the button's decoration").
// The simulation alone, without the DOM (ui/fx/Grains.tsx draws it): runs in Node for the tests.

export interface Shape {
  /** points along the outline, x0, y0, x1, y1, … in CSS pixels, in drawing order (closed) */
  points: Float32Array;
  /** which colour the gathered grains take (index into the drawing's palette) */
  tone: number;
}

export interface Grains {
  n: number;
  w: number;
  h: number;
  x: Float32Array;
  y: Float32Array;
  vx: Float32Array;
  vy: Float32Array;
  /** 0.35–1: nearer grains are larger, brighter and drift faster */
  depth: Float32Array;
  phase: Float32Array;
  /** seated: how far outside the outline a grain keeps (px; most on the line, a few as loose dust around it) */
  off: Float32Array;
  /** seated: how fast it travels along the outline, against the others (they overtake: no row of beads) */
  rate: Float32Array;
  /** the place on the outline a grain keeps (as a fraction of its length), or −1 while it floats */
  seat: Float32Array;
  /** 0 floating … 1 part of the outline (eased: brightness and colour follow it) */
  held: Float32Array;
  shape: Shape | null;
  /** distance along the outline at each of its points, and its whole length */
  along: Float32Array;
  length: number;
  time: number;
  /** the pointer in CSS pixels (NaN: none) */
  px: number;
  py: number;
}

/** A small generator of our own: the field looks the same at every start (and in the tests). */
function seeded(seed: number) {
  let s = seed >>> 0;
  return () => {
    s = (s + 0x6d2b79f5) >>> 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function createGrains(n: number, w: number, h: number, seed = 7): Grains {
  const rnd = seeded(seed);
  const g: Grains = {
    n, w, h,
    x: new Float32Array(n), y: new Float32Array(n), vx: new Float32Array(n), vy: new Float32Array(n),
    depth: new Float32Array(n), phase: new Float32Array(n), off: new Float32Array(n), rate: new Float32Array(n), seat: new Float32Array(n).fill(-1), held: new Float32Array(n),
    shape: null, along: new Float32Array(0), length: 0, time: 0, px: NaN, py: NaN,
  };
  for (let i = 0; i < n; i++) {
    g.x[i] = rnd() * w;
    g.y[i] = rnd() * h;
    // (most grains far: a few near ones carry the depth)
    g.depth[i] = 0.35 + 0.65 * rnd() ** 2.2;
    g.phase[i] = rnd() * Math.PI * 2;
    const u = rnd();
    g.off[i] = u < 0.62 ? (rnd() - 0.4) * 2.4 : 2 + 13 * ((u - 0.62) / 0.38) ** 2;
    g.rate[i] = (rnd() < 0.5 ? -1 : 1) * (0.35 + 1.5 * rnd());
  }
  return g;
}

/** The screen changed size: the floating grains spread over the new one. */
export function resizeGrains(g: Grains, w: number, h: number) {
  if (g.w > 0 && g.h > 0) {
    for (let i = 0; i < g.n; i++) {
      g.x[i] *= w / g.w;
      g.y[i] *= h / g.h;
    }
  }
  g.w = w;
  g.h = h;
}

/** how many grains an outline of this length takes (one every few pixels, never most of the field) */
export const seatsFor = (g: Grains, length: number) => Math.min(Math.floor(g.n * 0.45), Math.max(24, Math.round(length / 5)));

/**
 * What the grains gather into from now on (null: they all float again). Grains already in an outline move over to
 * the new one first (the shape changes rather than one dissolving and another forming); the nearest floating ones
 * fill the rest.
 */
export function setShape(g: Grains, shape: Shape | null) {
  const before: number[] = [];
  for (let i = 0; i < g.n; i++) if (g.seat[i] >= 0) before.push(i);
  g.seat.fill(-1);
  g.shape = shape && shape.points.length >= 4 ? shape : null;
  if (!g.shape) {
    // let go with a small push outwards, so the outline bursts rather than fades
    for (const i of before) {
      const a = g.phase[i] + g.time;
      g.vx[i] += Math.cos(a) * 40;
      g.vy[i] += Math.sin(a) * 40;
    }
    return;
  }
  const p = g.shape.points;
  const m = p.length / 2;
  measure(g);
  const seats = seatsFor(g, g.length);

  // who sits: those who sat before, then the floating grains nearest to the outline's middle
  let cx = 0, cy = 0;
  for (let k = 0; k < m; k++) {
    cx += p[k * 2] / m;
    cy += p[k * 2 + 1] / m;
  }
  const taken = new Uint8Array(g.n);
  const chosen = before.slice(0, seats);
  for (const i of chosen) taken[i] = 1;
  if (chosen.length < seats) {
    const rest: number[] = [];
    for (let i = 0; i < g.n; i++) if (!taken[i]) rest.push(i);
    const d = (i: number) => (g.x[i] - cx) ** 2 + (g.y[i] - cy) ** 2;
    rest.sort((a, b) => d(a) - d(b));
    for (const i of rest.slice(0, seats - chosen.length)) chosen.push(i);
  }
  // each one the seat nearest to where it is now (by angle around the middle: paths do not cross much)
  const order = chosen.map((i) => ({ i, a: Math.atan2(g.y[i] - cy, g.x[i] - cx) })).sort((u, v) => u.a - v.a);
  const first = Math.atan2(p[1] - cy, p[0] - cx);
  let start = 0;
  for (let k = 0; k < order.length; k++) if (Math.abs(order[k].a - first) < Math.abs(order[start].a - first)) start = k;
  // (the outline is drawn clockwise on the screen, as the angles grow)
  for (let k = 0; k < order.length; k++) g.seat[order[(start + k) % order.length].i] = k / order.length;
}

function measure(g: Grains) {
  const p = g.shape!.points;
  const m = p.length / 2;
  g.along = new Float32Array(m + 1);
  for (let k = 1; k <= m; k++) {
    const a = (k - 1) * 2, b = (k % m) * 2;
    g.along[k] = g.along[k - 1] + Math.hypot(p[b] - p[a], p[b + 1] - p[a + 1]);
  }
  g.length = g.along[m];
}

/** The same outline somewhere else or in another size (its element moved): every grain keeps its seat. */
export function moveShape(g: Grains, points: Float32Array) {
  if (!g.shape || points.length < 4) return;
  g.shape.points = points;
  measure(g);
}

/** The point of the outline at a fraction of its length. */
export function pointAt(g: Grains, fraction: number, out: [number, number], normal?: [number, number]) {
  const p = g.shape!.points;
  const m = p.length / 2;
  const want = (((fraction % 1) + 1) % 1) * g.length;
  let lo = 0, hi = m;
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1;
    if (g.along[mid] <= want) lo = mid;
    else hi = mid;
  }
  const span = g.along[lo + 1] - g.along[lo] || 1;
  const t = (want - g.along[lo]) / span;
  const a = lo * 2, b = ((lo + 1) % m) * 2;
  out[0] = p[a] + (p[b] - p[a]) * t;
  out[1] = p[a + 1] + (p[b + 1] - p[a + 1]) * t;
  if (normal) {
    // (the outline runs clockwise on the screen: outside is to the left of the way it runs)
    normal[0] = (p[b + 1] - p[a + 1]) / span;
    normal[1] = -(p[b] - p[a]) / span;
  }
}

/** px/s the outline's grains travel along it, each at its own rate (the frame is alive, not a drawn line) */
const MARCH = 22;
const tmp: [number, number] = [0, 0];
const out: [number, number] = [0, 0];

export function stepGrains(g: Grains, dt: number) {
  dt = Math.min(dt, 0.05);
  g.time += dt;
  const t = g.time;
  const pointer = Number.isFinite(g.px);
  const march = g.shape ? (t * MARCH) / Math.max(g.length, 1) : 0;
  for (let i = 0; i < g.n; i++) {
    const depth = g.depth[i];
    let ax = 0, ay = 0;
    if (g.seat[i] >= 0 && g.shape) {
      // a seat on the outline: a spring towards it, damped just short of critically (it arrives with a small swing)
      pointAt(g, g.seat[i] + march * g.rate[i], tmp, out);
      // (the loose ones breathe in and out a little)
      const off = g.off[i] * (1 + 0.25 * Math.sin(t * 1.7 + g.phase[i] * 7));
      ax = (tmp[0] + out[0] * off - g.x[i]) * 90 - g.vx[i] * 15;
      ay = (tmp[1] + out[1] * off - g.y[i]) * 90 - g.vy[i] * 15;
      g.held[i] += (1 - g.held[i]) * Math.min(1, dt * 6);
    } else {
      // floating: a slow field of swirls, faster for the near grains, and a rise as of dust in warm air
      const k = 0.0042, ph = g.phase[i];
      const fx = Math.sin(g.y[i] * k * 1.7 + t * 0.21 + ph) + 0.6 * Math.sin((g.x[i] + g.y[i]) * k - t * 0.13);
      const fy = Math.cos(g.x[i] * k * 1.3 - t * 0.17 + ph) + 0.6 * Math.sin((g.x[i] - g.y[i]) * k * 0.8 + t * 0.11) - 0.35;
      const speed = 22 * depth;
      ax = (fx * speed - g.vx[i]) * 1.4;
      ay = (fy * speed - g.vy[i]) * 1.4;
      if (pointer) {
        // around the pointer they turn, and keep a little off it
        const dx = g.x[i] - g.px, dy = g.y[i] - g.py;
        const d2 = dx * dx + dy * dy;
        if (d2 < 150 * 150) {
          const d = Math.sqrt(d2) + 1;
          const f = (1 - d / 150) * 260 * depth;
          ax += (-dy / d) * f + (dx / d) * f * 0.35;
          ay += (dx / d) * f + (dy / d) * f * 0.35;
        }
      }
      g.held[i] += (0 - g.held[i]) * Math.min(1, dt * 3);
    }
    g.vx[i] += ax * dt;
    g.vy[i] += ay * dt;
    g.x[i] += g.vx[i] * dt;
    g.y[i] += g.vy[i] * dt;
    if (g.seat[i] < 0) {
      // off one edge, in at the other
      if (g.x[i] < -8) g.x[i] += g.w + 16;
      else if (g.x[i] > g.w + 8) g.x[i] -= g.w + 16;
      if (g.y[i] < -8) g.y[i] += g.h + 16;
      else if (g.y[i] > g.h + 8) g.y[i] -= g.h + 16;
    }
  }
}

/** A push on every floating grain (a screen change sweeps them along). */
export function sweep(g: Grains, vx: number, vy: number) {
  for (let i = 0; i < g.n; i++) {
    if (g.seat[i] >= 0) continue;
    g.vx[i] += vx * g.depth[i];
    g.vy[i] += vy * g.depth[i];
  }
}

/**
 * The outline of a cut panel (two corners chamfered, as the interface's panels are: top left and bottom right), as
 * points a few pixels apart, clockwise from the top left cut.
 */
export function panelOutline(x: number, y: number, w: number, h: number, cut: number, pad = 0): Float32Array {
  x -= pad;
  y -= pad;
  w += pad * 2;
  h += pad * 2;
  const c = Math.max(0, Math.min(cut, w / 3, h / 3));
  const corners = [x + c, y, x + w, y, x + w, y + h - c, x + w - c, y + h, x, y + h, x, y + c];
  const out: number[] = [];
  for (let k = 0; k < 6; k++) {
    const ax = corners[k * 2], ay = corners[k * 2 + 1];
    const bx = corners[((k + 1) % 6) * 2], by = corners[((k + 1) % 6) * 2 + 1];
    const steps = Math.max(1, Math.round(Math.hypot(bx - ax, by - ay) / 6));
    for (let s = 0; s < steps; s++) out.push(ax + ((bx - ax) * s) / steps, ay + ((by - ay) * s) / steps);
  }
  return new Float32Array(out);
}

/** A ring (round things: a medal, a dial), clockwise from the top. */
export function ringOutline(cx: number, cy: number, r: number): Float32Array {
  const steps = Math.max(12, Math.round((Math.PI * 2 * r) / 6));
  const out = new Float32Array(steps * 2);
  for (let s = 0; s < steps; s++) {
    const a = (s / steps) * Math.PI * 2 - Math.PI / 2;
    out[s * 2] = cx + Math.cos(a) * r;
    out[s * 2 + 1] = cy + Math.sin(a) * r;
  }
  return out;
}

/** A line under something (a word, a bar): out along it and back a little lower, so that it closes. */
export function lineOutline(x: number, y: number, w: number, gap = 3): Float32Array {
  const steps = Math.max(2, Math.round(w / 6));
  const out: number[] = [];
  for (let s = 0; s < steps; s++) out.push(x + (w * s) / steps, y);
  for (let s = 0; s < steps; s++) out.push(x + w - (w * s) / steps, y + gap);
  return new Float32Array(out);
}
