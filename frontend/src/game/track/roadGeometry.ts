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
