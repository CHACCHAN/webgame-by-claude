import { BufferAttribute, BufferGeometry, Vector3 } from 'three';
import { Track } from './Track';
import type { TerrainData } from './terrain';

/** Spacing (in samples) between road cross-sections. */
const STEP = 2;
/** Shoulder beyond the drivable edge where the barriers stand. */
export const SHOULDER = 0.6;
/** Height of the invisible collision walls. */
const WALL_HEIGHT = 3.2;

export interface Side {
  /** for each sample: true when the terrain drops away (valley side → guardrail) */
  valley: Uint8Array;
}

/**
 * Determine for each side of the road whether it faces a drop (valley) or a
 * rising slope (mountain). Used to pick guardrails vs. retaining walls.
 */
export function classifySides(track: Track, terrain: TerrainData): { left: Side; right: Side } {
  const n = track.count;
  const left = new Uint8Array(n), right = new Uint8Array(n);
  const p = new Vector3();
  for (let i = 0; i < n; i++) {
    const hw = track.width[i] / 2;
    const y = track.pos[i * 3 + 1];
    for (const [sign, arr] of [[1, right], [-1, left]] as const) {
      let drop = 0;
      for (const d of [4, 9, 16]) {
        track.pointAt(i, sign * (hw + d), p);
        drop += y - terrain.heightAt(p.x, p.z);
      }
      arr[i] = drop / 3 > 1.2 || track.zone[i] === 'bridge' ? 1 : 0;
    }
  }
  // remove short flickers
  for (const arr of [left, right]) {
    const copy = arr.slice();
    for (let i = 0; i < n; i++) {
      let s = 0, c = 0;
      for (let k = Math.max(0, i - 12); k <= Math.min(n - 1, i + 12); k++) {
        s += copy[k];
        c++;
      }
      arr[i] = s / c > 0.5 ? 1 : 0;
    }
  }
  return { left: { valley: left }, right: { valley: right } };
}

/**
 * Road surface: asphalt between the edges plus a short skirt that tucks under
 * the terrain. UV: u across (0..1 over the asphalt), v = meters along.
 */
export function buildRoadGeometry(track: Track): BufferGeometry {
  // cross-section lateral stations relative to the half width (+ = right)
  // [skirtL, edgeL, ... , edgeR, skirtR]
  const lanesAcross = 6;
  const cols = lanesAcross + 1 + 2;
  const rows = Math.floor((track.count - 1) / STEP) + 1;
  const pos = new Float32Array(rows * cols * 3);
  const nor = new Float32Array(rows * cols * 3);
  const uv = new Float32Array(rows * cols * 2);
  // lightmap coordinates: x across the full cross-section, y along the road (row)
  const uv1 = new Float32Array(rows * cols * 2);
  // (metres from the centreline, half width up to the barriers): what render/roadMaterial.ts paints by
  const road = new Float32Array(rows * cols * 2);
  const p = new Vector3(), up = new Vector3();
  for (let r = 0; r < rows; r++) {
    const i = Math.min(r * STEP, track.count - 1);
    const hw = track.width[i] / 2 + SHOULDER;
    track.getUp(i, up);
    for (let c = 0; c < cols; c++) {
      let lat: number, drop = 0, u: number;
      if (c === 0) {
        lat = -hw - 0.6;
        drop = 0.9;
        u = -0.04;
      } else if (c === cols - 1) {
        lat = hw + 0.6;
        drop = 0.9;
        u = 1.04;
      } else {
        const t = (c - 1) / lanesAcross;
        lat = -hw + t * hw * 2;
        u = t;
      }
      track.pointAt(i * 1, lat, p);
      p.addScaledVector(up, -drop);
      const o = (r * cols + c) * 3;
      pos[o] = p.x;
      pos[o + 1] = p.y;
      pos[o + 2] = p.z;
      nor[o] = up.x;
      nor[o + 1] = up.y;
      nor[o + 2] = up.z;
      uv[(r * cols + c) * 2] = u;
      road[(r * cols + c) * 2] = lat;
      road[(r * cols + c) * 2 + 1] = hw;
      uv1[(r * cols + c) * 2] = (lat + hw + 0.6) / (2 * (hw + 0.6));
      uv1[(r * cols + c) * 2 + 1] = (r + 0.5) / rows;
      uv[(r * cols + c) * 2 + 1] = i;
    }
  }
  const idx: number[] = [];
  // columns run left → right, rows run forward: (a, b, d) faces up
  for (let r = 0; r < rows - 1; r++)
    for (let c = 0; c < cols - 1; c++) {
      const a = r * cols + c, b = a + 1, d = a + cols, e = d + 1;
      idx.push(a, b, d, b, e, d);
    }
  const g = new BufferGeometry();
  g.setAttribute('position', new BufferAttribute(pos, 3));
  g.setAttribute('normal', new BufferAttribute(nor, 3));
  g.setAttribute('uv', new BufferAttribute(uv, 2));
  g.setAttribute('uv1', new BufferAttribute(uv1, 2));
  g.setAttribute('road', new BufferAttribute(road, 2));
  g.userData.lightmapRows = rows;
  g.userData.lightmapStep = STEP;
  g.setIndex(idx);
  return g;
}

/** Collision-only surface: the drivable road (no skirts). Returns raw arrays for Rapier. */
export function buildRoadCollider(track: Track) {
  const rows = Math.floor((track.count - 1) / STEP) + 1;
  const cols = 3;
  const verts = new Float32Array(rows * cols * 3);
  const p = new Vector3();
  for (let r = 0; r < rows; r++) {
    const i = Math.min(r * STEP, track.count - 1);
    const hw = track.width[i] / 2 + SHOULDER + 0.8;
    for (let c = 0; c < cols; c++) {
      track.pointAt(i, -hw + c * hw, p);
      verts.set([p.x, p.y, p.z], (r * cols + c) * 3);
    }
  }
  const idx: number[] = [];
  for (let r = 0; r < rows - 1; r++)
    for (let c = 0; c < cols - 1; c++) {
      const a = r * cols + c, b = a + 1, d = a + cols, e = d + 1;
      idx.push(a, b, d, b, e, d);
    }
  return { vertices: verts, indices: Uint32Array.from(idx) };
}

/** Invisible vertical walls along both road edges (Rapier trimesh data). */
export function buildWallColliders(track: Track) {
  const rows = Math.floor((track.count - 1) / STEP) + 1;
  const verts = new Float32Array(rows * 4 * 3);
  const p = new Vector3(), up = new Vector3();
  for (let r = 0; r < rows; r++) {
    const i = Math.min(r * STEP, track.count - 1);
    const hw = track.width[i] / 2 + SHOULDER;
    track.getUp(i, up);
    let k = 0;
    for (const side of [-1, 1]) {
      track.pointAt(i, side * hw, p);
      p.addScaledVector(up, -1);
      verts.set([p.x, p.y, p.z], (r * 4 + k++) * 3);
      p.addScaledVector(up, WALL_HEIGHT + 1);
      verts.set([p.x, p.y, p.z], (r * 4 + k++) * 3);
    }
  }
  const idx: number[] = [];
  for (let r = 0; r < rows - 1; r++) {
    for (const base of [0, 2]) {
      const a = r * 4 + base, b = a + 1, d = a + 4, e = d + 1;
      // double sided so the car can't slip through from either direction
      idx.push(a, d, b, b, d, e, a, b, d, b, e, d);
    }
  }
  return { vertices: verts, indices: Uint32Array.from(idx) };
}

/** Where an autobahn surface's texels sit in the shared road lightmap (render/autobahnScenery.ts). */
export interface RoadLightmapLayout {
  /** lateral range (m, + = right of the centreline) the lightmap's columns span */
  lat: [number, number];
  /** samples per lightmap row on the main road (rows of 2 m would overflow a 4096 texture on a long course) */
  step: number;
  /** rows of the whole lightmap (the main road's first, other surfaces after them) */
  rows: number;
}

/**
 * Autobahn carriageway: like buildRoadGeometry, but the texture's u is in metres across a marking atlas (the
 * markings keep their real widths and positions, measured from the left asphalt edge) and `layout(i)` picks the
 * atlas column (m) per sample: the plain layout or the exit lane's. Where the layout changes, the row is emitted
 * twice (the quad between them is empty) so no quad blends the two. uv1 addresses the shared lightmap by lateral
 * position and track distance.
 */
export function buildAutobahnRoadGeometry(
  track: Track,
  atlasWidth: number,
  layout: (i: number) => number,
  lm: RoadLightmapLayout,
  /** the opposite carriageway: its centre's lateral offset, mirrored (its left edge, the median's, on our left) */
  opts: { center?: number; mirror?: boolean } = {},
) {
  const center = opts.center ?? 0, mirror = opts.mirror ? -1 : 1;
  // a row every 4 m and four quads across: the motorway bends gently (R ≥ 1200 m) and has no banked hairpins
  const ROW = 4;
  const lanesAcross = 4;
  const cols = lanesAcross + 1 + 2;
  const samples: [number, number][] = [];
  let prev = layout(0);
  for (let i = 0; ; i = Math.min(i + ROW, track.count - 1)) {
    const l = layout(i);
    if (l !== prev) samples.push([i, prev]);
    samples.push([i, l]);
    prev = l;
    if (i === track.count - 1) break;
  }
  const rows = samples.length;
  const pos = new Float32Array(rows * cols * 3);
  const nor = new Float32Array(rows * cols * 3);
  const uv = new Float32Array(rows * cols * 2);
  const uv1 = new Float32Array(rows * cols * 2);
  const road = new Float32Array(rows * cols * 2);
  const p = new Vector3(), up = new Vector3();
  samples.forEach(([i, atlasU], r) => {
    const hw = track.width[i] / 2 + SHOULDER;
    track.getUp(i, up);
    for (let c = 0; c < cols; c++) {
      let lat: number, drop = 0;
      if (c === 0) {
        lat = -hw - 0.6;
        drop = 0.9;
      } else if (c === cols - 1) {
        lat = hw + 0.6;
        drop = 0.9;
      } else lat = -hw + ((c - 1) / lanesAcross) * hw * 2;
      const world = center + mirror * lat;
      track.pointAt(i, world, p);
      p.addScaledVector(up, -drop);
      const o = r * cols + c;
      pos.set([p.x, p.y, p.z], o * 3);
      nor.set([up.x, up.y, up.z], o * 3);
      uv[o * 2] = (atlasU + Math.max(-0.3, Math.min(lat + hw, 2 * hw + 0.3))) / atlasWidth;
      uv[o * 2 + 1] = i;
      // (the carriageway's own frame: + = its right, like the texture's u)
      road[o * 2] = lat;
      road[o * 2 + 1] = hw;
      uv1[o * 2] = (world - lm.lat[0]) / (lm.lat[1] - lm.lat[0]);
      uv1[o * 2 + 1] = (i / lm.step + 0.5) / lm.rows;
    }
  });
  const idx: number[] = [];
  for (let r = 0; r < rows - 1; r++)
    for (let c = 0; c < cols - 1; c++) {
      const a = r * cols + c, b = a + 1, d = a + cols, e = d + 1;
      // mirrored, the columns run right to left: swap the winding so the faces still point up
      if (mirror > 0) idx.push(a, b, d, b, e, d);
      else idx.push(a, d, b, b, d, e);
    }
  const g = new BufferGeometry();
  g.setAttribute('position', new BufferAttribute(pos, 3));
  g.setAttribute('normal', new BufferAttribute(nor, 3));
  g.setAttribute('uv', new BufferAttribute(uv, 2));
  g.setAttribute('uv1', new BufferAttribute(uv1, 2));
  g.setAttribute('road', new BufferAttribute(road, 2));
  g.setIndex(idx);
  return g;
}
