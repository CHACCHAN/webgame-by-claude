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
 * the edge of a shadow is as soft as a cell is wide. Two of them per cell:
 *  - `land`: what the terrain alone shades. Used everywhere, next to the shadow map too (the map has no terrain in it);
 *  - `all`: terrain, the trees' crowns and the rock sheds' roofs. Used where the shadow map ends, faded in at its edge.
 * (`render/keyShadow.ts` reads them in the shader.)
 *
 * Worked out by one sweep from the light's side: the shadow's height at a cell is what the cell before it towards
 * the light holds (its own top, or the shadow already over it), lowered by the light's slope over that step.
 */

// (`SHADE_SIZE` cells along each side: the grid is stretched over the course's near terrain, so a cell is 2–8 m)

/** something that stands on the land and shades it: a disc of radius `r` (m) with its top at `top` */
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
  /** SHADE_SIZE² × 4 bytes: `land` then `all`, each 16 bits (high byte first) of (height − base) / range */
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
  /** the tops of the land, and of everything on it, per cell */
  land: Float32Array;
  all: Float32Array;
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
  for (const c of casters) {
    // (a crown is no slab: its rim is lower than its top, and a cell it only touches is not covered)
    const ri = c.r / cx, rj = c.r / cz;
    const ci = (c.x - x0) / cx - 0.5, cj = (c.z - z0) / cz - 0.5;
    for (let j = Math.floor(cj - rj); j <= Math.ceil(cj + rj); j++)
      for (let i = Math.floor(ci - ri); i <= Math.ceil(ci + ri); i++) {
        const d = Math.hypot((i - ci) / Math.max(ri, 0.5), (j - cj) / Math.max(rj, 0.5));
        if (d > 1.2) continue;
        const ground = i >= 0 && j >= 0 && i < N && j < N ? H[j * N + i] : c.top;
        raise(i, j, ground + (c.top - ground) * (1 - 0.45 * Math.min(1, d) ** 2));
      }
    if (c.top > hi) hi = c.top;
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
  return { land: H, all, x0, z0, cx, cz, lo, hi, heightAt: land.heightAt };
}

/**
 * How high the shadow reaches in every cell, for light coming from `toLight` (unit vector towards the sun / moon).
 */
export function bakeShade(scene: ShadeScene, toLight: { x: number; y: number; z: number }): ShadeField {
  const N = SHADE_SIZE;
  const { land, all, x0, z0, cx, cz, lo, hi } = scene;
  const flat = Math.hypot(toLight.x, toLight.z);
  const base = lo - 80, range = hi + 20 - base;
  const data = new Uint8Array(N * N * 4);
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
  const k = 65535 / range;
  for (let o = 0; o < N * N; o++) {
    const t = Math.min(65535, Math.max(0, Math.round((sT[o] - base) * k)));
    const s = Math.min(65535, Math.max(0, Math.round((sA[o] - base) * k)));
    data[o * 4] = t >> 8;
    data[o * 4 + 1] = t & 255;
    data[o * 4 + 2] = s >> 8;
    data[o * 4 + 3] = s & 255;
  }
  return field;
}

/** how high the shadow reaches at a place, as the shader reads it (for tests and probes): [land, all] */
export function shadeAt(f: ShadeField, x: number, z: number): [number, number] {
  const N = SHADE_SIZE;
  const u = (x - f.x0) / f.cx - 0.5, v = (z - f.z0) / f.cz - 0.5;
  const i = Math.floor(u), j = Math.floor(v), fu = u - i, fv = v - j;
  const read = (i: number, j: number, c: number) => {
    const o = (Math.min(N - 1, Math.max(0, j)) * N + Math.min(N - 1, Math.max(0, i))) * 4 + c;
    return ((f.data[o] * 256 + f.data[o + 1]) / 65535) * f.range + f.base;
  };
  const mix = (c: number) => (read(i, j, c) * (1 - fu) + read(i + 1, j, c) * fu) * (1 - fv) + (read(i, j + 1, c) * (1 - fu) + read(i + 1, j + 1, c) * fu) * fv;
  return [mix(0), mix(2)];
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
