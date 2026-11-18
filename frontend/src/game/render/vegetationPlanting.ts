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
  /** trees and bushes: how tall a grown one stands (m, at scale 1), for the views it must not close */
  tall?: number;
}

/** every species the game has a model for (tools/blender/nature/<id>.py) */
export const SPECIES: Record<string, SpeciesDef> = {
  // 杉: the planted forest of the lower and middle slopes
  sugi: { look: { tint: [1, 1, 1], translucency: 0.7 }, scale: [0.72, 1.15], bare: 5, tall: 19.5 },
  // 檜: planted too, on the drier slopes
  hinoki: { look: { tint: [1, 1, 1], translucency: 0.8 }, scale: [0.75, 1.1], bare: 4.5, tall: 17.8 },
  // ブナ: the natural forest higher up, and the edges
  buna: { look: { tint: [1, 1, 1], translucency: 1.3 }, scale: [0.7, 1.15], bare: 4, tall: 19 },
  // 赤松: ridges and rocky, dry places
  akamatsu: { look: { tint: [1, 1, 1], translucency: 0.7 }, scale: [0.75, 1.15], bare: 6.5, tall: 18 },
  // Fichte (Norway spruce): the autobahn's forests
  fichte: { look: { tint: [1, 1, 1], translucency: 0.6 }, scale: [0.75, 1.2], bare: 2, tall: 21 },
  // Birke: the edges of those forests and the copses in the fields
  birke: { look: { tint: [0.78, 0.84, 0.74], translucency: 1.1 }, scale: [0.7, 1.1], bare: 4, tall: 19 },
  // 藪: the bushes of the roadside
  yabu: { look: { tint: [0.8, 0.84, 0.8], translucency: 0.8, wind: 0.5 }, scale: [0.55, 1.25], bare: 0, tall: 2.7 },
  // 笹: bamboo grass, as thickets among the bushes and as undergrowth
  // (its leaves are pale: in a low sun a thicket shone out of the darker forest)
  sasa: { look: { tint: [0.6, 0.66, 0.62], translucency: 0.8, wind: 0.6 }, scale: [0.75, 1.4], bare: 0, tall: 1.3 },
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
  // the desert floor and a dry lake: nothing grows where the course runs
  airbase: [],
};

/** bushes and rocks beside the road (`buildClutter`), by the course's style */
export const COVER_SETS: Record<CourseStyle, string[]> = { touge: ['yabu', 'sasa', 'iwa'], autobahn: ['yabu'], airbase: [] };
/** what grows on the ground near the road */
export const UNDER_SETS: Record<CourseStyle, string[]> = { touge: ['kusa', 'susuki', 'shida', 'sasa'], autobahn: ['kusa', 'susuki'], airbase: [] };

/** the model files a course of this style needs (`undergrowth`: the quality has any) */
export function vegetationFiles(style: CourseStyle, undergrowth = true) {
  return [...new Set([...TREE_SETS[style], ...COVER_SETS[style], ...(undergrowth ? UNDER_SETS[style] : [])])];
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

/**
 * 0..1 how much of a town stands at (x, z): `cityWeight` where the land can be built on. A town's outline is an
 * ellipse and takes no notice of the mountain it lies against (kirifuri's hot-spring town reaches up the caldera's
 * wall): on steep ground there are no houses (the lights keep off it by the same measure) but forest.
 */
export function townWeight(terrain: TerrainData, x: number, z: number) {
  const w = cityWeight(terrain.landform, x, z);
  if (w <= 0) return 0;
  const steep = (Math.abs(terrain.heightAt(x + 8, z) - terrain.heightAt(x - 8, z)) + Math.abs(terrain.heightAt(x, z + 8) - terrain.heightAt(x, z - 8))) / 16;
  return w * smoothstep(0.62, 0.42, steep);
}

// ------------------------------------------------------------------------------------------------ the views

/** how far apart the road is sampled for its views (m), and how far from it a tree can stand in one */
const VIEW_STEP = 12, VIEW_REACH = 260;
const VIEW_CELL = 128;
/** the directions around a point of the road that are looked into */
const VIEW_SECTORS = 16;
/** the eye over the road (m) */
const VIEW_EYE = 1.5;
/** how steeply a view looks down, at least and at most (a tree's top stays under that line) */
const VIEW_DROP = [0.035, 0.09];
/** a bend tighter than this radius (m) has no view to its inside: the land there lies between its own two legs */
const VIEW_BEND = 55;
/** the least a tree is given (m; scrub of that height): where less is free under a view only the thickets stand (`plantCover`) */
const LOW = 2.5;
/** what is this low (m) closes no view wherever it stands: it is under the eye of whoever looks over it */
const UNDER_EYE = 1.0;

/** a point of the road and which directions around it look out: bit k = the azimuth (k + 0.5) / 16 of a turn, from +X towards +Z */
export interface ViewPoint {
  x: number;
  y: number;
  z: number;
  open: number;
  /** per direction: how steeply the view looks down (0: closed), and how far away what is seen begins (m) */
  drop: Float32Array;
  reach: Float32Array;
}

/**
 * Where the road looks out. A course is known for what is seen from it (the sea and the town below, the lake, the
 * sea of clouds under the ridge): a direction is open where an eye over the road sees one of them below it, over
 * all the land in between. That
 * is the valley side, and straight ahead where the road runs down towards the view (one direction is enough: the
 * lake at the end of a straight); the mountain side, the inside of a hairpin and the stretches that face nothing
 * stay closed, and the forest stands over the road there.
 */
export function roadViews(track: Track, terrain: TerrainData): ViewPoint[] {
  const lf = terrain.landform;
  const f = terrain.far;
  const fx1 = f.x0 + (f.nx - 1) * f.cell, fz1 = f.z0 + (f.nz - 1) * f.cell;
  // (close enough together that a lake a few hundred metres across is not stepped over)
  const REACH = [40, 65, 90, 125, 160, 210, 260, 330, 400, 500, 600, 750, 900, 1100, 1300, 1550, 1800, 2100, 2400];
  /** [how steeply the eye looks down on the nearest thing it sees, how far away that is] or null */
  const sees = (x: number, y: number, z: number, dx: number, dz: number, town: number): [number, number] | null => {
    const eye = y + VIEW_EYE;
    // how steeply a line from the eye may look down and still clear the land so far
    let block = Infinity;
    let last = Infinity, far = 0;
    for (const d of REACH) {
      const px = x + dx * d, pz = z + dz * d;
      // (a town in this direction, nearer than this sample: its middle is looked at)
      if (town && town < d) {
        const h = terrain.heightAt(x + dx * town, z + dz * town);
        const down = (eye - h) / town;
        return h < eye - 8 && down > 0.012 && down < block ? [down, town] : null;
      }
      if (px <= f.x0 || px >= fx1 || pz <= f.z0 || pz >= fz1) break;
      const h = terrain.heightAt(px, pz);
      const water = lf.waterLevel !== null && h <= lf.waterLevel + 0.5;
      // (the sea of clouds under a ridge: its top is what is seen)
      const clouds = !water && lf.cloudLevel !== null && h < lf.cloudLevel - 5 && lf.cloudLevel < eye - 20;
      last = water ? lf.waterLevel! : h;
      far = d;
      const down = (eye - (clouds ? lf.cloudLevel! : last)) / d;
      if (down > 0.012 && down < block && (water || clouds || (last < eye - 8 && cityWeight(lf, px, pz) > 0.2))) return [down, d];
      block = Math.min(block, (eye - last - 0.3) / d);
    }
    // the land ends low, at the shore: the sea beyond it goes on to the horizon, over everything that lies under the eye
    if (!town && lf.waterLevel !== null && last < lf.waterLevel + 15 && block > 0.012) return [block, far];
    return null;
  };
  const pts: ViewPoint[] = [];
  const p = new THREE.Vector3(), pa = new THREE.Vector3(), pb = new THREE.Vector3();
  for (let s = 0; s <= track.length; s += VIEW_STEP) {
    track.pointAt(s, 0, p);
    let open = 0;
    const drop = new Float32Array(VIEW_SECTORS), reach = new Float32Array(VIEW_SECTORS);
    // the inside of a tight bend: towards the middle of the chord between the road before and after
    track.pointAt(Math.max(0, s - 12), 0, pa);
    track.pointAt(Math.min(track.length, s + 12), 0, pb);
    const ix = (pa.x + pb.x) / 2 - p.x, iz = (pa.z + pb.z) / 2 - p.z;
    const half = Math.hypot(pb.x - pa.x, pb.z - pa.z) / 2;
    const inside = Math.hypot(ix, iz) > (half * half) / (2 * VIEW_BEND) ? Math.atan2(iz, ix) : null;
    const look = (k: number, seen: [number, number] | null) => {
      if (!seen || (open >> k) & 1) return;
      if (inside !== null) {
        const off = ((k + 0.5) / VIEW_SECTORS) * Math.PI * 2 - inside;
        if (Math.abs(Math.atan2(Math.sin(off), Math.cos(off))) < 1.25) return;
      }
      open |= 1 << k;
      // (under the steepest line that sees it, with room to spare: what is seen is wider than its near edge)
      drop[k] = clamp(seen[0] * 0.6, VIEW_DROP[0], VIEW_DROP[1]);
      reach[k] = seen[1];
    };
    for (let k = 0; k < VIEW_SECTORS; k++) {
      const a = ((k + 0.5) / VIEW_SECTORS) * Math.PI * 2;
      look(k, sees(p.x, p.y, p.z, Math.cos(a), Math.sin(a), 0));
    }
    // the towns, each looked at by itself (the rays above pass a small or far one by): the directions it fills
    for (const c of lf.cities) {
      const d = Math.hypot(c.x - p.x, c.z - p.z);
      if (d < 60 || d > 7000) continue;
      const seen = sees(p.x, p.y, p.z, (c.x - p.x) / d, (c.z - p.z) / d, d);
      if (!seen) continue;
      const a = Math.atan2(c.z - p.z, c.x - p.x), w = Math.atan(Math.min(c.rx, c.rz) / d);
      for (let k = 0; k < VIEW_SECTORS; k++) {
        const off = ((k + 0.5) / VIEW_SECTORS) * Math.PI * 2 - a;
        if (Math.abs(Math.atan2(Math.sin(off), Math.cos(off))) < w + Math.PI / VIEW_SECTORS) look(k, seen);
      }
    }
    pts.push({ x: p.x, y: p.y, z: p.z, open, drop, reach });
  }
  return pts;
}

/**
 * How high a tree's top may reach at a spot (the height above the sea; Infinity: as high as it grows): under the
 * line of sight of every point of the road that looks out past it. What stands beyond the thing seen (the forest on
 * the lake's far shore) is the view's backdrop, not in its way.
 */
export function viewLimiter(track: Track, terrain: TerrainData): (x: number, z: number) => number {
  const pts = roadViews(track, terrain);
  const grid = new Map<number, number[]>();
  const key = (cx: number, cz: number) => (cx + 4096) * 8192 + cz + 4096;
  pts.forEach((v, i) => {
    if (!v.open) return;
    const k = key(Math.floor(v.x / VIEW_CELL), Math.floor(v.z / VIEW_CELL));
    const list = grid.get(k);
    if (list) list.push(i);
    else grid.set(k, [i]);
  });
  const n = Math.ceil(VIEW_REACH / VIEW_CELL);
  // (per view: the square of how far its furthest open direction reaches, at most VIEW_REACH)
  const far2 = pts.map((v) => Math.min(VIEW_REACH, v.reach.reduce((m, r, k) => ((v.open >> k) & 1 ? Math.max(m, r) : m), 0)) ** 2);
  // Asked a quarter of a million times for a course (every 4 m square of ground near the road), with a hundred
  // views around each: the cheap tests come first, the angle only for a view that is near and looks down on the spot.
  /** per cell of the grid: the views that can reach into it (those of the cells around it), found when first asked for */
  const around = new Map<number, number[]>();
  const reaching = (cx: number, cz: number) => {
    const k = key(cx, cz);
    let list = around.get(k);
    if (!list) {
      list = [];
      const mx = (cx + 0.5) * VIEW_CELL, mz = (cz + 0.5) * VIEW_CELL;
      for (let j = -n; j <= n; j++) {
        for (let i = -n; i <= n; i++) {
          for (const at of grid.get(key(cx + i, cz + j)) ?? []) {
            if (Math.hypot(pts[at].x - mx, pts[at].z - mz) < Math.sqrt(far2[at]) + VIEW_CELL * 0.71) list.push(at);
          }
        }
      }
      around.set(k, list);
    }
    return list;
  };
  const at = (x: number, z: number) => {
    let limit = Infinity;
    let h = NaN;
    for (const at of reaching(Math.floor(x / VIEW_CELL), Math.floor(z / VIEW_CELL))) {
      const v = pts[at];
      const ex = x - v.x, ez = z - v.z;
      const out2 = ex * ex + ez * ez;
      // (the square with a hair to spare: the distance itself decides, as it always did)
      if (out2 < 15.9 || out2 > far2[at] + 1) continue;
      const out = Math.hypot(ex, ez);
      if (out < 4 || out > VIEW_REACH) continue;
      // (land that rises to the eye's own height is this view's edge, not in it: what stands on it hides sky)
      if (h !== h) h = terrain.heightAt(x, z);
      if (h > v.y + VIEW_EYE - 0.012 * out) continue;
      const k = Math.floor((Math.atan2(ez, ex) / (Math.PI * 2) + 1) * VIEW_SECTORS) % VIEW_SECTORS;
      if (!((v.open >> k) & 1) || out > v.reach[k]) continue;
      limit = Math.min(limit, v.y + VIEW_EYE - 0.2 - v.drop[k] * out);
    }
    return limit;
  };
  // (asked for every tree, thicket and vertex of the ground near the road: worked out once per 4 m square)
  const CELL = 4;
  const known = new Map<number, number>();
  return (x, z) => {
    const cx = Math.round(x / CELL), cz = Math.round(z / CELL);
    const k = (cx + 32768) * 65536 + cz + 32768;
    let limit = known.get(k);
    if (limit === undefined) known.set(k, (limit = at(cx * CELL, cz * CELL)));
    return limit;
  };
}

/** a tree this tall (m) and taller is drawn with the levels of detail at their full distances (`Planted.small`) */
const GROWN = 13;
/** a tree further than this from the road (m) never comes within the mesh levels' reach: an impostor only */
const FAR = 330;
/** a tree further than this from the road (m) throws no shadow: it would fall deep inside the forest, unseen (nearer, the forest shades itself: its inside is dark) */
const SHADE = 60;

export interface TreeOptions {
  /** nearest a trunk stands to the centreline (m; default the mountain road's 10.5) */
  clearance?: number;
  /** rejects a spot */
  keep?: (x: number, z: number) => boolean;
  /** places more trees through `add` after the scattered ones (`scale` 1 ≈ a grown tree) */
  extra?: (add: (x: number, z: number, scale: number) => void) => void;
  /** the road's views (`viewLimiter`): no tree stands between an open stretch and what is seen from it */
  views?: (x: number, z: number) => number;
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
  const limit = opts.views ?? null;

  /** the species for a spot: [id, size factor] (`young`: growth kept low, under a view or at the tree line) */
  const pick = (x: number, z: number, y: number, slope: number, d: number, young: boolean): [string, number] => {
    const stand = noise2(x / 210 + 7.3, z / 210 - 2.1);
    const dry = noise2(x / 95 + 31, z / 95 - 17);
    const edge = d < clearance + 7;
    // a stand is not of one kind to the last tree: others have seeded themselves in
    if (r() < 0.1) return [ids[Math.floor(r() * ids.length)], 1];
    if (style === 'autobahn') {
      // spruce plantations with beech between them; birches where the light gets in
      if (has('birke') && (edge ? r() < 0.5 : dry > 0.5 && r() < 0.6)) return ['birke', edge ? 0.75 : 1];
      if (has('buna') && (stand < -0.12 ? r() < 0.75 : r() < 0.12)) return ['buna', edge ? 0.7 : 1];
      return [has('fichte') ? 'fichte' : ids[0], edge ? 0.8 : 1];
    }
    const alt = clamp((y - lo) / Math.max(hi - lo, 1), 0, 1);
    // what stays low is what came by itself: broadleaves and pines, few of the planted conifers
    if (young && r() < 0.6) return [has('buna') && r() < 0.55 ? 'buna' : has('akamatsu') ? 'akamatsu' : ids[0], 1];
    // rock faces: pines hold on where nothing else does
    if (slope > 1.25 && has('akamatsu') && (slope > 1.7 || r() < 0.5)) return ['akamatsu', 0.65 + r() * 0.3];
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

  const add = (x: number, z: number, size: number, d: number, second = false) => {
    if (opts.keep && !opts.keep(x, z)) return;
    const y = terrain.heightAt(x, z);
    if (lf.waterLevel !== null && y < lf.waterLevel + 3) return;
    // towards the tree line the forest opens and its trees stay small (over 70 m of height, in patches): none above it
    const above = y - (lf.treeLine + noise2(x / 90, z / 90) * 40 + (r() - 0.5) * 24);
    if (above > 0) return;
    const high = clamp((above + 70) / 70, 0, 1);
    if (r() < high ** 2 * 0.45) return;
    if (lf.relief(x, z) < 0.25 || townWeight(terrain, x, z) > 0.2) return;
    const dx = terrain.heightAt(x + 3, z) - terrain.heightAt(x - 3, z);
    const dz = terrain.heightAt(x, z + 3) - terrain.heightAt(x, z - 3);
    const slope = Math.hypot(dx, dz) / 6;
    // steep ground: the forest holds up to 60° (seen across a lake such a wall is green), thins out above and the
    // last pines stand in a rock face of 70°; by the road the cuttings and their walls stay clear
    if (slope > 1.25 && (d < 45 || r() > smoothstep(2.9, 1.8, slope))) return;
    // how high a tree may stand here (m): under the line of sight of the road's views
    const room = limit && d < VIEW_REACH + 40 ? limit(x, z) - y : Infinity;
    if (room < LOW) return;
    const [id, k] = pick(x, z, y, slope, d, room < 15 || high > 0.45);
    const def = SPECIES[id];
    const tall = def.tall ?? 18;
    // a stand is of one age: its trees are of a height, give or take
    const age = 0.5 + 0.5 * noise2(x / 300 - 11, z / 300 + 50);
    let scale = (def.scale[0] + (def.scale[1] - def.scale[0]) * clamp(age * 0.8 + r() * 0.35, 0, 1)) * k * size;
    // … but not to the last tree (a rank of equal trees on a ridge is a comb against the sky): young ones stand
    // among the grown, a few stand over them. (Not far away: a small tree there is a hole in the canopy.)
    const u = r();
    if (d < 260 && u < 0.24) scale *= 0.45 + r() * 0.35;
    else if (u > 0.92) scale *= 1.12;
    // wind-shorn and crooked near the tree line
    scale *= 1 - 0.62 * high ** 1.3;
    let small = false;
    if (room < scale * tall) {
      // a tree that stays under the line: of every height the room allows from a good half of it up (all of them
      // grown up to the line, they stood there as a clipped hedge)
      scale = (room * (room < 5 ? 0.75 + 0.25 * r() : 0.6 + 0.4 * r())) / tall;
      small = true;
    }
    // (small trees leave the ground between them open: one more beside it)
    if (small && !second && scale * tall < 10 && r() < 0.75) add(x + (r() - 0.5) * 5.5, z + (r() - 0.5) * 5.5, size, d, true);
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
      // (the hillside's normal: a forest on the side away from the sun is in the mountain's shade)
      nx: -dx / 6 / Math.hypot(dx / 6, dz / 6, 1),
      nz: -dz / 6 / Math.hypot(dx / 6, dz / 6, 1),
      seed: r(),
      // (a young tree is as small in the picture as a grown one further away: `Planted.small`)
      small: clamp(GROWN / (scale * tall), 1, 3.1),
      far: d > FAR,
      // (a tree's shadow is seen where it falls on the road and the verge)
      casts: d < SHADE,
      order: Math.min(d, 1e5),
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
    // (the forest's edge is no line drawn along the road: it stands back in places)
    if (d < clearance + 7 * Math.max(0, noise2(x / 31 + 9, z / 31 - 4)) || d >= 85) return;
    // (clearings; the road's edge stays wooded for the tunnel of trees)
    if (d > 40 && noise2(x / 140, z / 140) < -0.32 + (r() - 0.5) * 0.16) return;
    // (and gaps a few trees wide: a windthrow, a rock)
    if (noise2(x / 34 - 20, z / 34 + 13) < -0.42 && r() < 0.85) return;
    add(x, z, 1, d);
  });
  // behind them
  scatter(g.x0, g.z0, x1, z1, 7 * k, (x, z) => {
    const d = roadDist(x, z);
    if (d < 85 || d >= 260) return;
    if (noise2(x / 140, z / 140) < -0.3 + (r() - 0.5) * 0.16) return;
    add(x, z, 1.1, d);
  });
  // the rest of the near terrain: seen from afar only, as fewer and bigger trees
  scatter(g.x0, g.z0, x1, z1, 8.5 * k, (x, z) => {
    const d = roadDist(x, z);
    if (d < 260) return;
    // (seen from afar a clearing's edge is ragged: cut along the planting grid it was a staircase; and clearings are
    // few there: across a lake they are bare patches in what should read as a forested mountain)
    if (noise2(x / 220, z / 220) < -0.6 + (r() - 0.5) * 0.24) return;
    add(x, z, 1.25, d);
  });
  // the far mountains, as far as the terrain goes
  const f = terrain.far;
  const reach = 2200;
  scatter(Math.max(g.x0 - reach, f.x0 + f.cell), Math.max(g.z0 - reach, f.z0 + f.cell), Math.min(x1 + reach, f.x0 + (f.nx - 2) * f.cell), Math.min(z1 + reach, f.z0 + (f.nz - 2) * f.cell), 22 * k, (x, z) => {
    if (x > g.x0 && x < x1 && z > g.z0 && z < z1) return;
    if (noise2(x / 300, z / 300) < -0.62 + (r() - 0.5) * 0.24) return;
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
  /** the road's views (`viewLimiter`): a bush on the valley side's verge stays under the eye */
  views?: (x: number, z: number) => number;
  /** thickets where no tree may stand (under a view, above the tree line), so far from the road (m; default 130, 0: none) */
  thickets?: number;
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
  const put = (list: Planted[], ids: string[], id: string, g: { x: number; y: number; z: number; steep: number }, size: number, sink: number, casts = false) => {
    const species = ids.indexOf(id);
    if (species < 0) return;
    const def = SPECIES[id];
    let scale = (def.scale[0] + (def.scale[1] - def.scale[0]) * r()) * size;
    if (opts.views && def.tall) {
      // (a bush may stand a little higher in a view than a tree's top: it is at the road's edge, under the eye;
      // and what is lower than the eye is in nobody's way)
      const room = Math.max(UNDER_EYE, opts.views(g.x, g.z) + 0.1 - g.y) / def.tall;
      if (room < scale) scale = room * (0.7 + 0.3 * r());
    }
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
      casts,
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
    // (how far from the road's edge: only the first rows' shadows are seen)
    const reach = off - track.width[clamp(Math.round(s), 0, track.count - 1)] / 2 - SHOULDER;
    if (rock) {
      if (opts.rocks === false) continue;
      // boulders are half buried, more so in a slope: on the cuttings they read as outcrops
      put(cover, coverIds, 'iwa', g, 1, 0.12 + Math.min(g.steep, 1.5) * 0.3, reach < 12);
    } else if (g.steep < 1.3) {
      const thicket = noise2(g.x / 55 + 3, g.z / 55 - 8) > 0.15;
      // (small at the road's edge: nothing reaches over the kerb)
      // (bamboo grass is the Japanese passes')
      put(cover, coverIds, thicket && r() < 0.7 && coverIds.includes('sasa') ? 'sasa' : 'yabu', g, clamp(reach / 3.5, 0.45, 1), 0.04 + g.steep * 0.12, reach < 8);
    }
  }

  // thickets where no tree may stand: under a view's line of sight and above the tree line the ground is not bare
  // (bamboo grass and low scrub, in patches; they are what makes a valley side read as overgrown from above)
  const reach = opts.thickets ?? 130;
  if (touge && reach > 0 && (opts.views || lf.treeLine < 1500)) {
    const grid = terrain.near;
    const gx1 = grid.x0 + (grid.nx - 1) * grid.cell, gz1 = grid.z0 + (grid.nz - 1) * grid.cell;
    const cell = 3.3 / Math.sqrt(Math.max(density, 0.05));
    const proj = { index: 0, s: 0, lateral: 0, height: 0 } as ReturnType<Track['project']>;
    for (let z0 = grid.z0; z0 < gz1; z0 += cell) {
      for (let x0 = grid.x0; x0 < gx1; x0 += cell) {
        const x = x0 + r() * cell, z = z0 + r() * cell;
        const d = terrain.roadDistAt(x, z);
        if (!(d < reach) || d < 8) continue;
        const y = terrain.heightAt(x, z);
        const above = y - (lf.treeLine + noise2(x / 90, z / 90) * 40);
        // in patches: closer together under a view than on the open ridge
        if (noise2(x / 19 + 60, z / 19 - 33) + noise2(x / 61, z / 61 + 7) * 0.6 < (above > -30 ? 0.05 : -0.22)) continue;
        const room = opts.views ? opts.views(x, z) - y : Infinity;
        // (where trees stand the forest floor is the undergrowth's)
        if (room >= LOW + 2 && above < -30) continue;
        if (lf.waterLevel !== null && y < lf.waterLevel + 0.4) continue;
        if (townWeight(terrain, x, z) > 0.2 || keepOut.some((k) => (x - k.x) ** 2 + (z - k.z) ** 2 < k.r * k.r)) continue;
        const gx = (terrain.heightAt(x + 1.5, z) - terrain.heightAt(x - 1.5, z)) / 3, gz = (terrain.heightAt(x, z + 1.5) - terrain.heightAt(x, z - 1.5)) / 3;
        const steep = Math.hypot(gx, gz);
        if (steep > 1.2) continue;
        if (d < 26) {
          // by the road: not on its verge, its structures or the start's apron
          track.project(x, y, z, -1, proj);
          const i = clamp(Math.round(proj.s), 0, track.count - 1);
          if (track.zone[i] === 'bridge' || track.zone[i] === 'rockshed') continue;
          if (Math.abs(proj.lateral) < track.width[i] / 2 + SHOULDER + 2.5) continue;
          if (proj.s < track.startS + 45 && Math.abs(proj.lateral) < 16) continue;
          if (opts.accept && !opts.accept(proj.s, proj.lateral)) continue;
        }
        const low = (opts.views ? Math.max(UNDER_EYE, room + 0.1) : Infinity) < 1.5 || above > -10;
        const id = (low ? r() < 0.75 : r() < 0.35) && coverIds.includes('sasa') ? 'sasa' : 'yabu';
        put(cover, coverIds, id, { x, y, z, steep }, id === 'yabu' && above > -30 ? 0.6 : 1, 0.04 + steep * 0.12);
      }
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
