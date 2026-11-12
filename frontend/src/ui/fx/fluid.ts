// The water the grains hang in: a small incompressible flow over the screen (no DOM: tested in Node).
// Stable fluids on a coarse grid (Stam): what stirs it adds velocity, the velocity is carried along by itself, and
// a pressure solve takes its divergence away, which is what makes it look like water: a stroke through it leaves
// two eddies turning against each other, not a smear. It dies down by itself and then costs nothing (`still`).
// Only velocity is kept: the "ink" is the grains themselves (cloud.ts carries them by it).

export interface Fluid {
  /** cells across and down, two rings of resting cells around the screen included */
  nx: number;
  ny: number;
  /** a cell's side, pixels */
  cell: number;
  /** velocity per cell, pixels a second (cell (i, j) has its centre at ((i − 1.5) · cell, (j − 1.5) · cell)) */
  u: Float32Array;
  v: Float32Array;
  u0: Float32Array;
  v0: Float32Array;
  p: Float32Array;
  div: Float32Array;
  /** nothing moves: a step does nothing */
  still: boolean;
}

/** how fast the flow dies down, 1 / seconds */
const DECAY = 1.8;
/** the fastest anything flows, pixels a second (a pointer thrown across the screen is ten times that) */
export const FASTEST = 700;
/**
 * How much the eddies are kept turning (vorticity confinement: the coarse grid would smooth them away), 1 / seconds.
 * Less than DECAY, or an eddy feeds itself and the water never comes to rest.
 */
const CURL = 0.7;
const ROUNDS = 14;
/** how far past its new value a pressure is taken in a round (1: Gauss–Seidel; 14 rounds of that left a quarter) */
const OVER = 1.7;

export function createFluid(w: number, h: number, rows = 40): Fluid {
  const cell = Math.max(4, h / rows);
  const nx = Math.max(8, Math.ceil(w / cell) + 4), ny = Math.max(8, Math.ceil(h / cell) + 4);
  const make = () => new Float32Array(nx * ny);
  return { nx, ny, cell, u: make(), v: make(), u0: make(), v0: make(), p: make(), div: make(), still: true };
}

/**
 * Stir: the flow within `r` of a place is drawn towards a velocity (a stroke of the pointer; drawn towards, not
 * added: two strokes in one frame do not double it).
 */
export function splat(f: Fluid, x: number, y: number, vx: number, vy: number, r: number) {
  const sp = Math.hypot(vx, vy);
  if (!(sp > 0) || !Number.isFinite(x + y + sp)) return;
  if (sp > FASTEST) {
    vx *= FASTEST / sp;
    vy *= FASTEST / sp;
  }
  const { nx, ny, cell, u, v } = f;
  const gx = x / cell + 1.5, gy = y / cell + 1.5, gr = r / cell, reach = Math.ceil(gr * 2.2);
  const i0 = Math.max(2, Math.floor(gx - reach)), i1 = Math.min(nx - 3, Math.ceil(gx + reach));
  const j0 = Math.max(2, Math.floor(gy - reach)), j1 = Math.min(ny - 3, Math.ceil(gy + reach));
  for (let j = j0; j <= j1; j++) {
    for (let i = i0; i <= i1; i++) {
      const dx = i - gx, dy = j - gy, k = Math.exp(-(dx * dx + dy * dy) / (gr * gr)), o = j * nx + i;
      u[o] += (vx - u[o]) * k;
      v[o] += (vy - v[o]) * k;
    }
  }
  f.still = false;
}

/** The flow at a place of the screen (between the cells' centres), into `out`. */
export function flowAt(f: Fluid, x: number, y: number, out: [number, number]) {
  const gx = Math.min(f.nx - 1.001, Math.max(0, x / f.cell + 1.5)), gy = Math.min(f.ny - 1.001, Math.max(0, y / f.cell + 1.5));
  const i = gx | 0, j = gy | 0, tx = gx - i, ty = gy - j, o = j * f.nx + i;
  const a = (1 - tx) * (1 - ty), b = tx * (1 - ty), c = (1 - tx) * ty, d = tx * ty;
  out[0] = f.u[o] * a + f.u[o + 1] * b + f.u[o + f.nx] * c + f.u[o + f.nx + 1] * d;
  out[1] = f.v[o] * a + f.v[o + 1] * b + f.v[o + f.nx] * c + f.v[o + f.nx + 1] * d;
  return out;
}

/** how much flows out of the cells (root mean square of the divergence, 1 / seconds): what the pressure takes away */
export function divergence(f: Fluid): number {
  const { nx, ny, u, v, cell } = f;
  let sum = 0;
  for (let j = 2; j < ny - 2; j++) {
    for (let i = 2; i < nx - 2; i++) {
      const o = j * nx + i, d = (u[o + 1] - u[o - 1] + v[o + nx] - v[o - nx]) / (2 * cell);
      sum += d * d;
    }
  }
  return Math.sqrt(sum / ((nx - 4) * (ny - 4)));
}

/**
 * Take the divergence out of the flow (the pressure of the last step is where the solve starts from).
 * Velocity and pressure live in the same cells, so the pressure's own neighbours are two cells away (the divergence
 * of a gradient taken across two cells each): solved with those, what is left is what the rounds did not reach;
 * with the next cells instead (the usual short cut) a stroke three cells wide kept half its divergence.
 */
export function project(f: Fluid, rounds = ROUNDS) {
  const { nx, ny, u, v, p, div } = f;
  const nx2 = nx * 2;
  for (let j = 2; j < ny - 2; j++) {
    for (let i = 2, o = j * nx + 2; i < nx - 2; i++, o++) div[o] = 0.5 * (u[o + 1] - u[o - 1] + v[o + nx] - v[o - nx]);
  }
  // (in place, row after row, each value taken past its new one: successive over-relaxation; the rings stay at 0:
  // the screen's edge is open)
  for (let k = 0; k < rounds; k++) {
    for (let j = 2; j < ny - 2; j++) {
      for (let i = 2, o = j * nx + 2; i < nx - 2; i++, o++) p[o] += OVER * ((p[o - 2] + p[o + 2] + p[o - nx2] + p[o + nx2]) * 0.25 - div[o] - p[o]);
    }
  }
  for (let j = 2; j < ny - 2; j++) {
    for (let i = 2, o = j * nx + 2; i < nx - 2; i++, o++) {
      u[o] -= 0.5 * (p[o + 1] - p[o - 1]);
      v[o] -= 0.5 * (p[o + nx] - p[o - nx]);
    }
  }
}

export function stepFluid(f: Fluid, dt: number) {
  if (f.still || !(dt > 0)) return;
  const { nx, ny, cell, u, v, u0, v0, div } = f;
  // the eddies are kept turning: a push around every place where the flow turns more than around it
  // (`div` is free here: it holds how much the flow turns)
  const w = div;
  for (let j = 1; j < ny - 1; j++) {
    for (let i = 1, o = j * nx + 1; i < nx - 1; i++, o++) w[o] = 0.5 * (v[o + 1] - v[o - 1] - u[o + nx] + u[o - nx]);
  }
  const push = CURL * dt;
  u0.set(u);
  v0.set(v);
  for (let j = 3; j < ny - 3; j++) {
    for (let i = 3, o = j * nx + 3; i < nx - 3; i++, o++) {
      const gx = Math.abs(w[o + 1]) - Math.abs(w[o - 1]), gy = Math.abs(w[o + nx]) - Math.abs(w[o - nx]);
      const g = Math.sqrt(gx * gx + gy * gy) + 1e-3;
      u0[o] += (gy / g) * w[o] * push;
      v0[o] -= (gx / g) * w[o] * push;
    }
  }
  // the flow carries itself: every cell takes what was upstream of it
  const keep = Math.exp(-DECAY * dt), back = dt / cell;
  let fastest = 0;
  for (let j = 2; j < ny - 2; j++) {
    for (let i = 2, o = j * nx + 2; i < nx - 2; i++, o++) {
      const x = Math.min(nx - 1.001, Math.max(0, i - u0[o] * back)), y = Math.min(ny - 1.001, Math.max(0, j - v0[o] * back));
      const a = x | 0, b = y | 0, tx = x - a, ty = y - b, q = b * nx + a;
      const k00 = (1 - tx) * (1 - ty), k10 = tx * (1 - ty), k01 = (1 - tx) * ty, k11 = tx * ty;
      const nu = (u0[q] * k00 + u0[q + 1] * k10 + u0[q + nx] * k01 + u0[q + nx + 1] * k11) * keep;
      const nv = (v0[q] * k00 + v0[q + 1] * k10 + v0[q + nx] * k01 + v0[q + nx + 1] * k11) * keep;
      u[o] = nu;
      v[o] = nv;
      const s = nu * nu + nv * nv;
      if (s > fastest) fastest = s;
    }
  }
  if (!(fastest < FASTEST * FASTEST * 4)) {
    // (never: but a flow that ran away would carry every grain off the screen)
    calm(f);
    return;
  }
  if (fastest < 2.5) {
    calm(f);
    return;
  }
  project(f);
}

/** All of it at rest. */
export function calm(f: Fluid) {
  f.u.fill(0);
  f.v.fill(0);
  f.u0.fill(0);
  f.v0.fill(0);
  f.p.fill(0);
  f.still = true;
}
