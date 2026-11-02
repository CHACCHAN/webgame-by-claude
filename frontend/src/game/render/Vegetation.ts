import * as THREE from 'three';
import type { Track } from '../track/Track';
import type { TerrainData } from '../track/terrain';
import { SHOULDER, type Side } from '../track/roadGeometry';
import { clamp, rng } from '../util/math';
import { getProp, type PropId, type PropPart } from './propAssets';

/**
 * Roadside plants from the Poly Haven sets (render/propAssets.ts): bushes, grass tufts, ferns and weeds.
 *
 * Instances live in a grid of CELL-sized cells. Each plant part is one InstancedMesh holding only the
 * instances of the cells round the camera ("near" fields), refilled when the camera enters another cell,
 * so the draw calls stay at one per part however long the course is. Bushes also have a "far" field:
 * the cheap procedural lump everywhere outside that radius.
 */
const CELL = 40;

interface Cell {
  m: number[];
  c: number[];
}

interface Field {
  parts: PropPart[];
  near: boolean;
  /** cells (Chebyshev distance) round the camera's cell that count as near */
  radius: number;
  cells: Map<number, Cell>;
  meshes: THREE.InstancedMesh[];
  count: number;
}

const key = (x: number, z: number) => (Math.floor(x / CELL) + 4096) * 8192 + (Math.floor(z / CELL) + 4096);

export interface BushInstance {
  matrix: THREE.Matrix4;
  color: THREE.Color;
}

export interface VegetationOptions {
  /** 0..1 like the tree density setting */
  density: number;
  /** circles the plants keep clear of (shrine, bus stop) */
  clearings: { x: number; z: number; r: number }[];
  /** bushes placed by the clutter pass; drawn as `farBush` beyond the near radius */
  bushes: BushInstance[];
  farBush: PropPart;
}

export interface VegetationResult {
  group: THREE.Group;
  /** refills the near / far fields when the camera has moved into another cell */
  update(camera: THREE.Vector3): void;
  /** instances per field kind, for checks */
  counts(): Record<string, number>;
}

const SMALL: Record<'grass' | 'weed' | 'nettle' | 'fern', PropId> = {
  grass: 'grass_medium_01',
  weed: 'weed_plant_02',
  nettle: 'nettle_plant',
  fern: 'fern_02',
};

/** null when the plant models are missing (the clutter pass then keeps its lumps everywhere). */
export function buildVegetation(track: Track, terrain: TerrainData, sides: { left: Side; right: Side }, opts: VegetationOptions): VegetationResult | null {
  const shrubs = [getProp('shrub_02'), getProp('shrub_04')].flatMap((t) => t?.variants ?? []);
  if (!shrubs.length) return null;
  const group = new THREE.Group();
  group.name = 'vegetation';
  const fields: Field[] = [];
  const fieldOf = new Map<string, Field>();
  // near radius in cells: bushes (and their far lumps) switch at 2 cells (80–120 m) from medium up; the
  // low plants show to 2 cells on high / ultra, 1 cell (40–80 m) below
  const bushRadius = opts.density < 0.6 ? 1 : 2;
  const plantRadius = opts.density < 0.95 ? 1 : 2;
  const field = (name: string, parts: PropPart[], near: boolean, radius = plantRadius) => {
    if (!fieldOf.has(name)) {
      const f: Field = { parts, near, radius, cells: new Map(), meshes: [], count: 0 };
      fieldOf.set(name, f);
      fields.push(f);
    }
    return fieldOf.get(name)!;
  };
  const add = (f: Field, m: THREE.Matrix4, c: THREE.Color) => {
    const k = key(m.elements[12], m.elements[14]);
    let cell = f.cells.get(k);
    if (!cell) f.cells.set(k, (cell = { m: [], c: [] }));
    cell.m.push(...m.elements);
    cell.c.push(c.r, c.g, c.b);
    f.count++;
  };
  const r = rng(9031);
  const UP = new THREE.Vector3(0, 1, 0);
  const q = new THREE.Quaternion(), tilt = new THREE.Quaternion(), n = new THREE.Vector3();
  const pos = new THREE.Vector3(), scl = new THREE.Vector3(), rot = new THREE.Quaternion();
  // slight per-plant colour variation (multiplies the texture)
  const tint = () => new THREE.Color(0.82 + r() * 0.18, 0.88 + r() * 0.12, 0.78 + r() * 0.22);

  // ---- bushes: a shrub model near the camera, the lump further away
  const farBush = field('bush-lump', [opts.farBush], false, bushRadius);
  for (const b of opts.bushes) {
    add(farBush, b.matrix, b.color);
    b.matrix.decompose(pos, rot, scl);
    const v = shrubs[Math.floor(r() * shrubs.length)];
    q.setFromAxisAngle(UP, r() * Math.PI * 2);
    const s = clamp(scl.y * 0.9, 0.55, 1.4);
    // foot on the ground (the lump sits partly buried)
    pos.y = terrain.heightAt(pos.x, pos.z) - 0.08;
    add(field(`shrub-${v.name}`, v.parts, true, bushRadius), new THREE.Matrix4().compose(pos, q, new THREE.Vector3(s, s, s)), tint());
  }

  // ---- grass, weeds and ferns along the verges and up the cuttings (near only)
  const sets = Object.fromEntries(Object.entries(SMALL).map(([k, id]) => [k, getProp(id)?.variants ?? []])) as Record<keyof typeof SMALL, { name: string; parts: PropPart[] }[]>;
  const water = terrain.landform.waterLevel;
  const p = new THREE.Vector3();
  // two passes: a dense verge strip next to the road wall (grass, weeds), then the slopes behind it
  const passes = [
    { count: Math.round(track.count * 2 * 2.2 * opts.density), from: 0.9, span: 2.8, power: 1 },
    { count: Math.round(track.count * 2 * 1.4 * opts.density), from: 3.7, span: 18, power: 1.6 },
  ];
  for (const pass of passes) {
    for (let k = 0; k < pass.count; k++) {
      const s = r() * (track.count - 1);
      const i = Math.round(s);
      const side = r() < 0.5 ? -1 : 1;
      const hw = track.width[i] / 2 + SHOULDER;
      const off = hw + pass.from + r() ** pass.power * pass.span;
      if (s < track.startS + 45 && off < 16) continue;
      // under the rock shed's roof (mountain side) nothing grows
      const valley = (side > 0 ? sides.right : sides.left).valley[i];
      if (track.zone[i] === 'rockshed' && !valley && off < hw + 9) continue;
      track.pointAt(s, side * off, p);
      if (opts.clearings.some((c) => (p.x - c.x) ** 2 + (p.z - c.z) ** 2 < c.r * c.r)) continue;
      // the nearest road must be this one (hairpin legs)
      if (terrain.roadDistAt(p.x, p.z) < off - 2) continue;
      const y = terrain.heightAt(p.x, p.z);
      if (Math.abs(y - p.y) > 12 || (water !== null && y < water + 0.6)) continue;
      const gx = (terrain.heightAt(p.x + 1, p.z) - terrain.heightAt(p.x - 1, p.z)) / 2;
      const gz = (terrain.heightAt(p.x, p.z + 1) - terrain.heightAt(p.x, p.z - 1)) / 2;
      const steep = Math.hypot(gx, gz);
      if (steep > 1.5) continue;
      const roll = r();
      let kind: keyof typeof SMALL;
      if (pass.from < 1) kind = roll < 0.65 ? 'grass' : roll < 0.85 ? 'weed' : 'nettle';
      else if (steep > 0.6) kind = roll < 0.5 ? 'fern' : roll < 0.85 ? 'grass' : 'nettle';
      else kind = roll < 0.45 ? 'grass' : roll < 0.75 ? 'fern' : roll < 0.9 ? 'nettle' : 'weed';
      const list = sets[kind];
      if (!list.length) continue;
      const v = list[Math.floor(r() * list.length)];
      q.setFromAxisAngle(UP, r() * Math.PI * 2);
      // low plants lean with the slope, stems stay upright
      if (kind !== 'nettle') q.premultiply(tilt.setFromUnitVectors(UP, n.set(-gx * 0.6, 1, -gz * 0.6).normalize()));
      const sc = (kind === 'grass' ? 0.95 : 0.75) + r() * 0.6;
      add(field(`${kind}-${v.name}`, v.parts, true), new THREE.Matrix4().compose(new THREE.Vector3(p.x, y - 0.04, p.z), q, new THREE.Vector3(sc, sc, sc)), tint());
    }
  }

  // ---- one InstancedMesh per part, sized for every instance of its field. No shadow casting: the old
  // lump bushes never cast shadows either, and the shadow pass would draw every plant a second time.
  for (const f of fields) {
    if (!f.count) continue;
    for (const part of f.parts) {
      const material = part === opts.farBush ? part.material : part.material.clone();
      const mesh = new THREE.InstancedMesh(part.geometry, material, f.count);
      mesh.instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(f.count * 3), 3);
      mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
      mesh.count = 0;
      mesh.receiveShadow = true;
      mesh.castShadow = false;
      mesh.name = fieldOfName(f);
      f.meshes.push(mesh);
      group.add(mesh);
    }
  }
  function fieldOfName(f: Field) {
    for (const [k, v] of fieldOf) if (v === f) return k;
    return '';
  }

  let lastKey = NaN;
  return {
    group,
    update(camera) {
      const cx = Math.floor(camera.x / CELL), cz = Math.floor(camera.z / CELL);
      const k = (cx + 4096) * 8192 + (cz + 4096);
      if (k === lastKey) return;
      lastKey = k;
      for (const f of fields) {
        if (!f.meshes.length) continue;
        let used = 0;
        const m = f.meshes[0].instanceMatrix.array as Float32Array;
        const c = f.meshes[0].instanceColor!.array as Float32Array;
        for (const [ck, cell] of f.cells) {
          const dx = Math.floor(ck / 8192) - 4096 - cx, dz = (ck % 8192) - 4096 - cz;
          const inside = Math.abs(dx) <= f.radius && Math.abs(dz) <= f.radius;
          if (inside !== f.near) continue;
          m.set(cell.m, used * 16);
          c.set(cell.c, used * 3);
          used += cell.m.length / 16;
        }
        for (const [j, mesh] of f.meshes.entries()) {
          if (j > 0) {
            (mesh.instanceMatrix.array as Float32Array).set(m.subarray(0, used * 16));
            (mesh.instanceColor!.array as Float32Array).set(c.subarray(0, used * 3));
          }
          mesh.count = used;
          mesh.instanceMatrix.needsUpdate = true;
          mesh.instanceColor!.needsUpdate = true;
          mesh.computeBoundingSphere();
        }
      }
    },
    counts() {
      const out: Record<string, number> = {};
      for (const [name, f] of fieldOf) out[name.split('-')[0]] = (out[name.split('-')[0]] ?? 0) + f.count;
      return out;
    },
  };
}
