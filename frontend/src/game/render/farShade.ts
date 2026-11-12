import * as THREE from 'three';
import { SHADE_SIZE, type LightAtlas } from './lightAtlas';

export { SHADE_SIZE };

/**
 * The shadows that the shadow map cannot hold: the sun's / moon's shade far from the camera, and the shade of the
 * land itself anywhere.
 *
 * The shadow map is a square of some hundred metres around the camera; beyond it everything stood in full light, and
 * the land never threw a shadow at all (a ridge between the road and a sun 9° up left the road sunlit). Nothing that
 * matters at that distance moves, so the shade is worked out once per course and light: for every cell of a grid over
 * the course, **how high the shadow reaches there** (the height below which a point does not see the light). One
 * number answers for the ground, a wall, a tree top or a car at that place, and between cells it changes evenly, so
 * the edge of a shadow is as soft as a cell is wide. Per cell:
 *  - `land`: how high the terrain's shadow reaches. Used everywhere, next to the shadow map too (the map has no
 *    terrain in it);
 *  - `all`: the same with the rock sheds' roofs on the land;
 *  - `canopy`: how much light the trees leave on the ground there (0 … 1). Not a height: a crown is no slab, and a
 *    row of trees as solid blocks put the whole road behind it in the dark where the shadow map, next to it, drew
 *    stripes of light and shade. What is kept is the share of light, so that the far road is as bright as the near
 *    one is on the whole.
 * `all` and `canopy` are used where the shadow map ends, faded in at its edge (`render/keyShadow.ts` reads them).
 *
 * Worked out by one sweep from the light's side: the shadow's height at a cell is what the cell before it towards
 * the light holds (its own top, or the shadow already over it), lowered by the light's slope over that step.
 */

// (`SHADE_SIZE` cells along each side: the grid is stretched over the course's near terrain, so a cell is 2–8 m)

/** a tree: a crown of radius `r` (m, as wide as it is on the whole, not at its widest) with its top at `top` */
export interface ShadeCaster {
  x: number;
  z: number;
  r: number;
  top: number;
}

/** the land as the bake needs it (`TerrainData` fits) */
export interface ShadeLand {
  near: { x0: number; z0: number; cell: number; nx: number; nz: number };
  heightAt(x: number, z: number): number;
}

export interface ShadeField {
  /**
   * SHADE_SIZE² × 4 bytes: `land` as 16 bits (high byte first) of (height − base) / range, how far `all` is above
   * it in steps of `ROOF_STEP`, `canopy` as a byte
   */
  data: Uint8Array;
  x0: number;
  z0: number;
  /** a cell's size along x and z (m) */
  cx: number;
  cz: number;
  base: number;
  range: number;
  /** the height the light loses over one cell (m): how soft a shadow's edge is */
  soft: number;
}

export interface ShadeScene {
  /** per cell: the land's height, the same with the roofs on it, the share of the cell under crowns and their top */
  land: Float32Array;
  all: Float32Array;
  cover: Float32Array;
  crown: Float32Array;
  x0: number;
  z0: number;
  cx: number;
  cz: number;
  lo: number;
  hi: number;
  heightAt(x: number, z: number): number;
}

/**
 * What shades, as heights per cell: the terrain, with the casters' discs and the roofs (`SceneryResult.covers`:
 * quads of 9 floats) laid on it.
 */
export function shadeScene(land: ShadeLand, casters: readonly ShadeCaster[], covers: ArrayLike<number> = []): ShadeScene {
  const N = SHADE_SIZE, g = land.near;
  const x0 = g.x0, z0 = g.z0, cx = ((g.nx - 1) * g.cell) / N, cz = ((g.nz - 1) * g.cell) / N;
  const H = new Float32Array(N * N);
  let lo = Infinity, hi = -Infinity;
  for (let j = 0; j < N; j++) {
    const z = z0 + (j + 0.5) * cz;
    for (let i = 0; i < N; i++) {
      const h = land.heightAt(x0 + (i + 0.5) * cx, z);
      H[j * N + i] = h;
      if (h < lo) lo = h;
      if (h > hi) hi = h;
    }
  }
  const all = H.slice();
  const raise = (i: number, j: number, top: number) => {
    if (i < 0 || j < 0 || i >= N || j >= N) return;
    const o = j * N + i;
    if (top > all[o]) all[o] = top;
  };
  const cover = new Float32Array(N * N), crown = new Float32Array(N * N).fill(-Infinity);
  for (const c of casters) {
    // the crown's share of every cell it reaches into (its square's overlap, as a disc's: × π / 4)
    const i0 = Math.max(0, Math.floor((c.x - c.r - x0) / cx)), i1 = Math.min(N - 1, Math.floor((c.x + c.r - x0) / cx));
    const j0 = Math.max(0, Math.floor((c.z - c.r - z0) / cz)), j1 = Math.min(N - 1, Math.floor((c.z + c.r - z0) / cz));
    for (let j = j0; j <= j1; j++) {
      const oz = Math.min(c.z + c.r, z0 + (j + 1) * cz) - Math.max(c.z - c.r, z0 + j * cz);
      for (let i = i0; i <= i1; i++) {
        const ox = Math.min(c.x + c.r, x0 + (i + 1) * cx) - Math.max(c.x - c.r, x0 + i * cx);
        const o = j * N + i;
        cover[o] = Math.min(1, cover[o] + (ox * oz * Math.PI) / 4 / (cx * cz));
        crown[o] = Math.max(crown[o], c.top);
      }
    }
  }
  for (let q = 0; q + 8 < covers.length; q += 9) {
    // a roof's quad (a, b, c, d in order): the cells whose centre is inside it
    const xs = [covers[q], covers[q + 2], covers[q + 4], covers[q + 6]], zs = [covers[q + 1], covers[q + 3], covers[q + 5], covers[q + 7]];
    const top = covers[q + 8];
    const i0 = Math.floor((Math.min(...xs) - x0) / cx), i1 = Math.ceil((Math.max(...xs) - x0) / cx);
    const j0 = Math.floor((Math.min(...zs) - z0) / cz), j1 = Math.ceil((Math.max(...zs) - z0) / cz);
    for (let j = j0; j <= j1; j++)
      for (let i = i0; i <= i1; i++) {
        const x = x0 + (i + 0.5) * cx, z = z0 + (j + 0.5) * cz;
        let pos = 0, neg = 0;
        for (let k = 0; k < 4; k++) {
          const n = (k + 1) % 4;
          // (half a cell of slack: a roof narrower than a cell still covers the cells along it)
          const cross = (xs[n] - xs[k]) * (z - zs[k]) - (zs[n] - zs[k]) * (x - xs[k]);
          const slack = 0.5 * Math.hypot((xs[n] - xs[k]) * cz, (zs[n] - zs[k]) * cx);
          if (cross > slack) pos++;
          else if (cross < -slack) neg++;
        }
        if (!(pos && neg)) raise(i, j, top);
      }
    if (top > hi) hi = top;
  }
  return { land: H, all, cover, crown, x0, z0, cx, cz, lo, hi, heightAt: land.heightAt };
}

/** `all` is kept as its height above `land`, in steps of this (m): a roof's shadow is never far above the ground's */
const ROOF_STEP = 0.1;
/** how much of the light a cell wholly under crowns takes from a ray through it (the shadow map's hulls have holes too) */
const CROWN_SHADE = 0.7;
/** the share of a tree's height, from the top down, over which its crown widens to its full width */
const CROWN_TIP = 0.6;
/** a crown's shadow is followed this far (m) */
const CROWN_REACH = 170;

/**
 * How high the shadow reaches in every cell, and what the trees leave of the light, for light coming from `toLight`
 * (unit vector towards the sun / moon). `landShades: false`: the land itself throws no shadow (`Landform.dawnShade`),
 * only the roofs and the trees do.
 */
export function bakeShade(scene: ShadeScene, toLight: { x: number; y: number; z: number }, landShades = true): ShadeField {
  const N = SHADE_SIZE;
  const { cover, crown, x0, z0, cx, cz, lo, hi } = scene;
  // what throws the two shadows: the land, and the land with the roofs (without the land: the roofs alone)
  const NONE = -1e9;
  const land = landShades ? scene.land : new Float32Array(N * N).fill(NONE);
  const all = landShades ? scene.all : scene.all.map((h, o) => (h > scene.land[o] ? h : NONE));
  const flat = Math.hypot(toLight.x, toLight.z);
  const base = lo - 80, range = hi + 20 - base;
  const data = new Uint8Array(N * N * 4);
  for (let o = 3; o < data.length; o += 4) data[o] = 255;
  const field: ShadeField = { data, x0, z0, cx, cz, base, range, soft: 1 };
  // (a light straight overhead shades nothing beside what is under it: everything stays lit)
  if (flat < 1e-3 || toLight.y <= 0) return field;
  const ux = toLight.x / flat, uz = toLight.z / flat, slope = toLight.y / flat;
  // one cell at a time along the axis the light's direction runs along most, in cells
  const alongX = Math.abs(ux / cx) >= Math.abs(uz / cz);
  const lead = alongX ? ux / cx : uz / cz;
  const side = (alongX ? uz / cz : ux / cx) / Math.abs(lead);
  const dir = lead > 0 ? 1 : -1;
  const step = alongX ? cx / Math.abs(ux) : cz / Math.abs(uz);
  const drop = step * slope;
  field.soft = Math.min(drop, 6);
  const sT = new Float32Array(N * N), sA = new Float32Array(N * N);
  const at = (a: number, b: number) => (alongX ? b * N + a : a * N + b);
  // beyond the grid: the far land's skyline as seen from there, by walking towards the light
  const outside = (a: number, b: number) => {
    const i = alongX ? a : b, j = alongX ? b : a;
    const x = x0 + (i + 0.5) * cx, z = z0 + (j + 0.5) * cz;
    if (!landShades) return NONE;
    let top = -Infinity;
    for (let t = 0, d = Math.max(cx, cz); t < 5000; t += d, d *= 1.06) top = Math.max(top, scene.heightAt(x + ux * t, z + uz * t) - t * slope);
    return top;
  };
  for (let n = 0; n < N; n++) {
    const a = dir > 0 ? N - 1 - n : n, ap = a + dir;
    for (let b = 0; b < N; b++) {
      const bp = b + side;
      let oT: number, oA: number;
      if (ap < 0 || ap >= N || bp < 0 || bp > N - 1) oT = oA = outside(ap, bp);
      else {
        const b0 = Math.floor(bp), f = bp - b0, b1 = Math.min(N - 1, b0 + 1);
        const p = at(ap, b0), q = at(ap, b1);
        oT = Math.max(land[p], sT[p]) * (1 - f) + Math.max(land[q], sT[q]) * f;
        oA = Math.max(all[p], sA[p]) * (1 - f) + Math.max(all[q], sA[q]) * f;
      }
      const o = at(a, b);
      sT[o] = oT - drop;
      sA[o] = oA - drop;
    }
  }
  if (!landShades)
    for (let o = 0; o < N * N; o++) {
      // (as on level ground in the light: the shadow's top a cell's drop under the ground)
      sT[o] = scene.land[o] - drop;
      sA[o] = Math.max(sA[o], sT[o]);
    }
  // the trees: every cell under crowns takes its share of the light from the cells behind it, as far as its top's
  // shadow runs above their ground
  const light = new Float32Array(N * N).fill(1);
  const reach = Math.min(N, Math.ceil(CROWN_REACH / step));
  for (let a = 0; a < N; a++)
    for (let b = 0; b < N; b++) {
      const src = at(a, b);
      if (!(cover[src] > 0)) continue;
      const dim = CROWN_SHADE * cover[src], top = crown[src];
      // a crown narrows to its tip: a ray that passes through its upper part meets less of it (under a low sun the
      // road behind a tree is shaded by the tip alone)
      const taper = 1 / (CROWN_TIP * Math.max(1, top - scene.land[src]));
      const thin = (h: number) => Math.min(1, (top - h) * taper) ** 2;
      for (let n = 0; n <= reach; n++) {
        const ra = a - dir * n, rb = b - side * n;
        if (ra < 0 || ra >= N || rb < 0 || rb > N - 1 || top - n * drop < lo) break;
        const b0 = Math.floor(rb), f = rb - b0;
        const p = at(ra, b0);
        if (scene.land[p] + n * drop < top) light[p] *= 1 - dim * thin(scene.land[p] + n * drop) * (1 - f);
        if (f > 0) {
          const q = at(ra, b0 + 1);
          if (scene.land[q] + n * drop < top) light[q] *= 1 - dim * thin(scene.land[q] + n * drop) * f;
        }
      }
    }
  const k = 65535 / range;
  for (let o = 0; o < N * N; o++) {
    const t = Math.min(65535, Math.max(0, Math.round((sT[o] - base) * k)));
    data[o * 4] = t >> 8;
    data[o * 4 + 1] = t & 255;
    data[o * 4 + 2] = Math.min(255, Math.max(0, Math.ceil((sA[o] - sT[o]) / ROOF_STEP)));
    data[o * 4 + 3] = Math.round(light[o] * 255);
  }
  return field;
}

/**
 * The shade at a place as the shader reads it (for tests and probes): how high the land's shadow reaches, how high
 * with the roofs, and the share of the light the trees leave on the ground.
 */
export function shadeAt(f: ShadeField, x: number, z: number): [number, number, number] {
  const N = SHADE_SIZE;
  const u = (x - f.x0) / f.cx - 0.5, v = (z - f.z0) / f.cz - 0.5;
  const i = Math.floor(u), j = Math.floor(v), fu = u - i, fv = v - j;
  const read = (i: number, j: number): [number, number, number] => {
    const o = (Math.min(N - 1, Math.max(0, j)) * N + Math.min(N - 1, Math.max(0, i))) * 4;
    const land = ((f.data[o] * 256 + f.data[o + 1]) / 65535) * f.range + f.base;
    return [land, land + f.data[o + 2] * ROOF_STEP, f.data[o + 3] / 255];
  };
  const a = read(i, j), b = read(i + 1, j), c = read(i, j + 1), d = read(i + 1, j + 1);
  const mix = (k: number) => (a[k] * (1 - fu) + b[k] * fu) * (1 - fv) + (c[k] * (1 - fu) + d[k] * fu) * fv;
  return [mix(0), mix(1), mix(2)];
}

/** how much of the light a point at height `y` gets under a shadow that reaches `top` (the shader's formula) */
export function litUnder(f: ShadeField, top: number, y: number) {
  const t = Math.min(1, Math.max(0, (y - top) / f.soft + 0.25));
  return t * t * (3 - 2 * t);
}

/**
 * The shade of the course that is shown, in the texture the shaders read (`LightAtlas`, its first rows; the light's
 * shader is built once: another course or another light writes other numbers into it).
 */
export class FarShade {
  /** x0, z0, cells per metre along x and z */
  readonly frame = new THREE.Vector4(0, 0, 1, 1);
  /** base, range, 1 / soft; w: 1 while there is a field (0: everything is lit) */
  readonly scale = new THREE.Vector4(0, 1, 1, 0);
  /** metres per step of the roofs' height above the land's shadow, for a byte read as 0 … 1 */
  readonly roofStep = 255 * ROOF_STEP;
  private shown: ShadeField | null = null;

  constructor(readonly atlas: LightAtlas) {}

  show(f: ShadeField | null) {
    this.scale.w = f ? 1 : 0;
    if (!f || f === this.shown) return;
    this.shown = f;
    this.atlas.put(0, SHADE_SIZE, f.data);
    this.frame.set(f.x0, f.z0, 1 / f.cx, 1 / f.cz);
    this.scale.set(f.base, f.range, 1 / f.soft, 1);
  }
}
