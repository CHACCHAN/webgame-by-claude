import * as THREE from 'three';
import type { TerrainData } from '../track/terrain';
import type { Track } from '../track/Track';
import { SHOULDER } from '../track/roadGeometry';
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
  // 藪: the bushes of the roadside
  yabu: { look: { translucency: 0.9, wind: 0.5 }, scale: [0.55, 1.25], bare: 0 },
  // 笹: bamboo grass, as thickets among the bushes and as undergrowth
  sasa: { look: { translucency: 1.1, wind: 0.6 }, scale: [0.75, 1.4], bare: 0 },
  // 岩: boulders and stones
  iwa: { look: { kind: 'rock', moss: 1 }, scale: [0.3, 1.25], bare: 0 },
  // 草: grass tufts
  kusa: { look: { translucency: 1.2, wind: 0.8 }, scale: [0.55, 1.15], bare: 0 },
  // ススキ: the tall grass along the rails
  susuki: { look: { translucency: 1.2, wind: 1 }, scale: [0.55, 1.0], bare: 0 },
  // シダ: ferns
  shida: { look: { translucency: 1.2, wind: 0.5 }, scale: [0.7, 1.3], bare: 0 },
};

/** the trees of a course, by its style (a species without a model is left out) */
export const TREE_SETS: Record<CourseStyle, string[]> = {
  touge: ['sugi', 'hinoki', 'buna', 'akamatsu'],
  autobahn: ['fichte', 'buna', 'birke'],
};

/** bushes and rocks beside the road (`buildClutter`) */
export const COVER_SET = ['yabu', 'sasa', 'iwa'];
/** what grows on the ground near the road */
export const UNDER_SET = ['kusa', 'susuki', 'shida', 'sasa'];

/** the model files a course of this style needs (`undergrowth`: the quality has any) */
export function vegetationFiles(style: CourseStyle, undergrowth = true) {
  return [...new Set([...TREE_SETS[style], ...COVER_SET, ...(undergrowth ? UNDER_SET : [])])];
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

export interface CoverOptions {
  /** the autobahn's: where along / beside the road (+ = right) anything may go */
  accept?: (s: number, lateral: number) => boolean;
  rocks?: boolean;
  /** undergrowth per metre of road, relative (0: none) */
  undergrowth: number;
  style: CourseStyle;
}

/**
 * Bushes and rocks along the road, and the undergrowth near it (grass at the edge, tall grass by the rails, ferns and
 * bamboo grass further in), placed in the road's own coordinates: `cover` and `under` index into `coverIds` / `underIds`.
 */
export function plantCover(
  track: Track,
  terrain: TerrainData,
  density: number,
  keepOut: { x: number; z: number; r: number }[],
  coverIds: string[],
  underIds: string[],
  opts: CoverOptions,
): { cover: Planted[]; under: Planted[] } {
  const cover: Planted[] = [], under: Planted[] = [];
  const lf = terrain.landform;
  const r = rng(77);
  const p = new THREE.Vector3();
  const touge = opts.style !== 'autobahn';

  /** the ground at a spot beside the road, or null where nothing grows */
  const spot = (s: number, lateral: number, tidyStart: boolean) => {
    const i = clamp(Math.round(s), 0, track.count - 1);
    if (track.zone[i] === 'bridge' || track.zone[i] === 'rockshed') return null;
    // keep the summit start area (garage, grid) tidy
    if (tidyStart && s < track.startS + 45 && Math.abs(lateral) < 16) return null;
    if (opts.accept && !opts.accept(s, lateral)) return null;
    track.pointAt(s, lateral, p);
    const x = p.x, z = p.z;
    if (keepOut.some((k) => (x - k.x) ** 2 + (z - k.z) ** 2 < k.r * k.r)) return null;
    const y = terrain.heightAt(x, z);
    if (Math.abs(y - p.y) > 14) return null;
    if (lf.waterLevel !== null && y < lf.waterLevel + 0.4) return null;
    const gx = (terrain.heightAt(x + 1.5, z) - terrain.heightAt(x - 1.5, z)) / 3;
    const gz = (terrain.heightAt(x, z + 1.5) - terrain.heightAt(x, z - 1.5)) / 3;
    return { x, y, z, steep: Math.hypot(gx, gz) };
  };
  const put = (list: Planted[], ids: string[], id: string, g: { x: number; y: number; z: number; steep: number }, size: number, sink: number) => {
    const species = ids.indexOf(id);
    if (species < 0) return;
    const def = SPECIES[id];
    const scale = (def.scale[0] + (def.scale[1] - def.scale[0]) * r()) * size;
    list.push({
      species,
      variant: Math.floor(r() * 8),
      x: g.x,
      y: g.y - sink * scale,
      z: g.z,
      yaw: r() * Math.PI * 2,
      scale,
      girth: 0.85 + r() * 0.4,
      tint: clamp(0.5 + noise2(g.x / 40, g.z / 40) * 0.45 + (r() - 0.5) * 0.5, 0, 1),
      seed: r(),
    });
  };

  // bushes and rocks
  const count = Math.round(9000 * density * (track.length / 3300));
  for (let k = 0; k < count; k++) {
    const s = r() * track.length;
    const side = r() < 0.5 ? -1 : 1;
    const off = track.width[clamp(Math.round(s), 0, track.count - 1)] / 2 + SHOULDER + 1.4 + r() ** 2 * 22;
    const g = spot(s, side * off, true);
    if (!g) continue;
    const rock = touge && (g.steep > 0.9 || r() < 0.18);
    if (rock) {
      if (opts.rocks === false) continue;
      // boulders are half buried, more so in a slope: on the cuttings they read as outcrops
      put(cover, coverIds, 'iwa', g, 1, 0.12 + Math.min(g.steep, 1.5) * 0.3);
    } else if (g.steep < 1.3) {
      const thicket = noise2(g.x / 55 + 3, g.z / 55 - 8) > 0.15;
      // (small at the road's edge: nothing reaches over the kerb)
      const reach = off - track.width[clamp(Math.round(s), 0, track.count - 1)] / 2 - SHOULDER;
      put(cover, coverIds, thicket && r() < 0.7 ? 'sasa' : 'yabu', g, clamp(reach / 3.5, 0.45, 1), 0.04 + g.steep * 0.12);
    }
  }

  // the undergrowth: strips beside the road, metre by metre
  const u = opts.undergrowth;
  if (u > 0 && underIds.length) {
    for (let s = 0; s < track.length; s += 1) {
      const e0 = track.width[clamp(Math.round(s), 0, track.count - 1)] / 2 + SHOULDER + 0.85;
      for (const side of [-1, 1]) {
        const at = (n: number, from: number, to: number, pow: number, pick: (g: { x: number; y: number; z: number; steep: number }, d: number) => string | null) => {
          for (let k = Math.floor(n * u + r()); k > 0; k--) {
            const d = from + (to - from) * r() ** pow;
            const g = spot(s + r(), side * (e0 + d), false);
            if (!g || g.steep > 1.25) continue;
            const id = pick(g, d);
            // (a little into the ground: a sprite's foot is not quite at its card's edge, and the ground slopes)
            if (id) put(under, underIds, id, g, 1, (id === 'susuki' ? 0.14 : 0.06) + g.steep * 0.08);
          }
        };
        // the verge: grass, and tall grass in patches and right behind the rail
        at(14, 0, 5, 1, (g, d) => {
          const tall = g.steep < 0.6 && noise2(g.x / 23 + 40, g.z / 23) > (d < 1.2 ? 0.0 : 0.35);
          return tall && r() < 0.55 ? 'susuki' : 'kusa';
        });
        // further in: thinner, with ferns and bamboo grass where the forest begins
        at(7, 5, 17, 1.3, (g) => {
          if (!touge) return noise2(g.x / 30, g.z / 30 + 9) > 0.1 ? 'kusa' : r() < 0.2 ? 'susuki' : null;
          const k = r();
          const thicket = noise2(g.x / 55 + 3, g.z / 55 - 8) > 0.15;
          return thicket && k < 0.5 ? 'sasa' : k < 0.45 ? 'kusa' : k < 0.85 ? 'shida' : 'sasa';
        });
        // the forest floor
        if (touge) at(3.5, 8, 34, 1, () => (r() < 0.65 ? 'shida' : 'sasa'));
      }
    }
  }
  return { cover, under };
}
