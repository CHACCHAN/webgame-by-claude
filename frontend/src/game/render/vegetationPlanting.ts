import type { TerrainData } from '../track/terrain';
import type { Landform } from '../track/landforms';
import type { CourseStyle } from '../track/courses';
import { clamp, noise2, rng, smoothstep } from '../util/math';
import { plantModel, type ForestSpecies, type PlantLook, type Planted } from './vegetation';

/**
 * Which plant stands where: the species of a course's forests by altitude, slope and distance to the road, in
 * stands as a forester (or the lack of one) leaves them.
 */

export interface SpeciesDef {
  look: PlantLook;
  /** size relative to the model as built: a stand's range */
  scale: [number, number];
  /** the trunk below the crown (m, at scale 1): a tree seen from afar only stands that deep in the ground, since at
   *  that size its trunk is thinner than a pixel and the crown would hang in the air over a ridge */
  bare: number;
}

/** every species the game has a model for (tools/blender/nature/<id>.py) */
export const SPECIES: Record<string, SpeciesDef> = {
  // 杉: the planted forest of the lower and middle slopes
  sugi: { look: { tint: [1, 1, 1], translucency: 0.7 }, scale: [0.72, 1.15], bare: 5 },
  // 檜: planted too, on the drier slopes
  hinoki: { look: { tint: [1, 1, 1], translucency: 0.8 }, scale: [0.75, 1.1], bare: 4.5 },
  // ブナ: the natural forest higher up, and the edges
  buna: { look: { tint: [1, 1, 1], translucency: 1.3 }, scale: [0.7, 1.15], bare: 4 },
  // 赤松: ridges and rocky, dry places
  akamatsu: { look: { tint: [1, 1, 1], translucency: 0.7 }, scale: [0.75, 1.15], bare: 6.5 },
  // Fichte (Norway spruce): the autobahn's forests
  fichte: { look: { tint: [1, 1, 1], translucency: 0.6 }, scale: [0.75, 1.2], bare: 2 },
  // Birke: the edges of those forests and the copses in the fields
  birke: { look: { tint: [1, 1, 1], translucency: 1.4 }, scale: [0.7, 1.1], bare: 4 },
};

/** the trees of a course, by its style (a species without a model is left out) */
export const TREE_SETS: Record<CourseStyle, string[]> = {
  touge: ['sugi', 'hinoki', 'buna', 'akamatsu'],
  autobahn: ['fichte', 'buna', 'birke'],
};

/** the model files a course of this style needs */
export function vegetationFiles(style: CourseStyle) {
  return [...TREE_SETS[style]];
}

/** the species of `ids` whose model is loaded */
export function loadedSpecies(ids: string[]): { ids: string[]; species: ForestSpecies[] } {
  const there = ids.filter((id) => plantModel(id));
  return { ids: there, species: there.map((id) => ({ model: plantModel(id)!, look: SPECIES[id].look })) };
}

/** 0..1 how much (x, z) lies inside one of the landform's towns. */
export function cityWeight(lf: Landform, x: number, z: number) {
  let w = 0;
  for (const c of lf.cities) {
    const ca = Math.cos(c.angle), sa = Math.sin(c.angle);
    const dx = x - c.x, dz = z - c.z;
    const ax = dx * ca + dz * sa, az = -dx * sa + dz * ca;
    const d = Math.sqrt((ax / c.rx) ** 2 + (az / c.rz) ** 2);
    w = Math.max(w, smoothstep(1.05, 0.8, d));
  }
  return w;
}

/** a tree further than this from the road (m) never comes within the mesh levels' reach: an impostor only */
const FAR = 330;

export interface TreeOptions {
  /** nearest a trunk stands to the centreline (m; default the mountain road's 10.5) */
  clearance?: number;
  /** rejects a spot */
  keep?: (x: number, z: number) => boolean;
  /** places more trees through `add` after the scattered ones (`scale` 1 ≈ a grown tree) */
  extra?: (add: (x: number, z: number, scale: number) => void) => void;
}

/**
 * The trees of a course. Density falls with the distance from the road (the car is the camera): close ranks in the
 * first 85 m, thinner behind, and beyond the near terrain the far mountains' forest as fewer, bigger trees.
 */
export function plantTrees(terrain: TerrainData, density: number, style: CourseStyle, ids: string[], opts: TreeOptions = {}): Planted[] {
  const out: Planted[] = [];
  if (!ids.length) return out;
  const r = rng(2024);
  const lf = terrain.landform;
  const g = terrain.near;
  const x1 = g.x0 + (g.nx - 1) * g.cell, z1 = g.z0 + (g.nz - 1) * g.cell;
  // the course's range of heights, for "higher up"
  let lo = Infinity, hi = -Infinity;
  for (let i = 0; i < g.heights.length; i += 97) {
    lo = Math.min(lo, g.heights[i]);
    hi = Math.max(hi, g.heights[i]);
  }
  const has = (id: string) => ids.includes(id);
  const of = (id: string) => Math.max(0, ids.indexOf(id));
  const clearance = opts.clearance ?? 10.5;

  /** the species for a spot: [id, size factor] */
  const pick = (x: number, z: number, y: number, slope: number, d: number): [string, number] => {
    const stand = noise2(x / 210 + 7.3, z / 210 - 2.1);
    const dry = noise2(x / 95 + 31, z / 95 - 17);
    const edge = d < clearance + 7;
    if (style === 'autobahn') {
      // spruce plantations with beech between them; birches where the light gets in
      if (has('birke') && (edge ? r() < 0.5 : dry > 0.5 && r() < 0.6)) return ['birke', edge ? 0.75 : 1];
      if (has('buna') && (stand < -0.12 ? r() < 0.75 : r() < 0.12)) return ['buna', edge ? 0.7 : 1];
      return [has('fichte') ? 'fichte' : ids[0], edge ? 0.8 : 1];
    }
    const alt = clamp((y - lo) / Math.max(hi - lo, 1), 0, 1);
    // the mantle along the road: young broadleaves under the planted trees' edge
    if (edge && has('buna') && r() < 0.45) return ['buna', 0.5 + r() * 0.25];
    // red pines hold the dry, steep and rocky places
    if (has('akamatsu') && (slope > 0.62 || dry > 0.52) && r() < 0.7) return ['akamatsu', 1];
    // higher up the planted forest gives way to the natural beech forest
    if (has('buna') && alt + stand * 0.18 > 0.66 && r() < 0.75) return ['buna', 1];
    if (stand > 0.02) return [has('buna') && r() < 0.07 ? 'buna' : 'sugi', 1];
    if (stand < -0.2 && has('hinoki')) return [has('buna') && r() < 0.1 ? 'buna' : 'hinoki', 1];
    const k = r();
    return [k < 0.5 || !has('hinoki') ? 'sugi' : k < 0.78 ? 'hinoki' : has('buna') ? 'buna' : 'sugi', 1];
  };

  const add = (x: number, z: number, size: number, d: number) => {
    if (opts.keep && !opts.keep(x, z)) return;
    const y = terrain.heightAt(x, z);
    if (lf.waterLevel !== null && y < lf.waterLevel + 3) return;
    // thinning out towards the tree line, none above it
    if (y > lf.treeLine + noise2(x / 90, z / 90) * 40) return;
    if (lf.relief(x, z) < 0.25 || cityWeight(lf, x, z) > 0.2) return;
    const dx = terrain.heightAt(x + 3, z) - terrain.heightAt(x - 3, z);
    const dz = terrain.heightAt(x, z + 3) - terrain.heightAt(x, z - 3);
    const slope = Math.hypot(dx, dz) / 6;
    if (slope > 1.25) return;
    const [id, k] = pick(x, z, y, slope, d);
    const def = SPECIES[id];
    // a stand is of one age: its trees are of a height, give or take
    const age = 0.5 + 0.5 * noise2(x / 300 - 11, z / 300 + 50);
    const scale = (def.scale[0] + (def.scale[1] - def.scale[0]) * clamp(age * 0.8 + r() * 0.35, 0, 1)) * k * size;
    out.push({
      species: of(id),
      variant: Math.floor(r() * 8),
      x,
      // sunk a little: the root flare stands in the ground on a slope too
      y: y - 0.25 - slope * 0.35 * scale - (d >= 260 ? def.bare * 0.8 * scale : 0),
      z,
      yaw: r() * Math.PI * 2,
      scale,
      girth: 0.88 + r() * 0.26,
      tint: clamp(0.5 + noise2(x / 60, z / 60) * 0.5 + (r() - 0.5) * 0.5, 0, 1),
      seed: r(),
      far: d > FAR,
    });
  };
  /** (beyond the road's reach the terrain has no distance: far away) */
  const roadDist = (x: number, z: number) => {
    const d = terrain.roadDistAt(x, z);
    return d < 1e6 ? d : 1e6;
  };

  /** a jittered grid of `cell` metres over a rectangle */
  const scatter = (xa: number, za: number, xb: number, zb: number, cell: number, at: (x: number, z: number) => void) => {
    for (let z = za; z < zb; z += cell) for (let x = xa; x < xb; x += cell) at(x + r() * cell, z + r() * cell);
  };
  // (the motorway's land is four times the passes': the same number of trees, further apart)
  const k = (style === 'autobahn' ? 1.3 : 1) / Math.sqrt(Math.max(density, 0.05));
  // the ranks along the road
  scatter(g.x0, g.z0, x1, z1, 5.3 * k, (x, z) => {
    const d = roadDist(x, z);
    if (d < clearance || d >= 85) return;
    // (clearings; the road's edge stays wooded for the tunnel of trees)
    if (d > 40 && noise2(x / 140, z / 140) < -0.32) return;
    add(x, z, 1, d);
  });
  // behind them
  scatter(g.x0, g.z0, x1, z1, 7 * k, (x, z) => {
    const d = roadDist(x, z);
    if (d < 85 || d >= 260) return;
    if (noise2(x / 140, z / 140) < -0.3) return;
    add(x, z, 1.1, d);
  });
  // the rest of the near terrain: seen from afar only, as fewer and bigger trees
  scatter(g.x0, g.z0, x1, z1, 8.5 * k, (x, z) => {
    const d = roadDist(x, z);
    if (d < 260) return;
    if (noise2(x / 220, z / 220) < -0.28) return;
    add(x, z, 1.25, d);
  });
  // the far mountains, as far as the terrain goes
  const f = terrain.far;
  const reach = 2200;
  scatter(Math.max(g.x0 - reach, f.x0 + f.cell), Math.max(g.z0 - reach, f.z0 + f.cell), Math.min(x1 + reach, f.x0 + (f.nx - 2) * f.cell), Math.min(z1 + reach, f.z0 + (f.nz - 2) * f.cell), 22 * k, (x, z) => {
    if (x > g.x0 && x < x1 && z > g.z0 && z < z1) return;
    if (noise2(x / 300, z / 300) < -0.2) return;
    add(x, z, 1.8, 1e6);
  });
  opts.extra?.((x, z, scale) => add(x, z, scale, roadDist(x, z)));
  return out;
}
