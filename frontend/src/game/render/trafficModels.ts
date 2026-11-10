import * as THREE from 'three';
import { mergeGeometries, toCreasedNormals } from 'three/examples/jsm/utils/BufferGeometryUtils.js';
import { buildCar } from './CarModel';
import { CAR_SPECS, type CarId } from '../vehicle/carSpecs';

/**
 * Light copies of the game's cars for background traffic (the autobahn's oncoming carriageway). Each car's model
 * (the same GLB the player drives, or its procedural fallback) is flattened into four merged meshes: the paint
 * (coloured per instance), glossy parts (glass, chrome, rims), matte parts and the lamps (always lit), every
 * material's colour baked into the vertices. Each material is welded and simplified to about a centimetre
 * (meshoptimizer, loaded only for this), so a car is drawn in four instanced draws of 3–12k triangles.
 */

export type TrafficPart = 'paint' | 'gloss' | 'matte' | 'lamp';
export const TRAFFIC_PARTS: TrafficPart[] = ['paint', 'gloss', 'matte', 'lamp'];

export interface TrafficModel {
  id: CarId;
  parts: Partial<Record<TrafficPart, THREE.BufferGeometry>>;
  /** lamp centres in the car's frame (+X left, +Z forward, ground at y = 0) */
  headlights: THREE.Vector3[];
  taillights: THREE.Vector3[];
  /** pop-up headlamps (the glare is warm halogen) */
  popUps: boolean;
}

/** geometric error allowed by the simplifier (m): under a pixel on the far carriageway */
const ERROR = 0.012;
const CREASE = 0.6;
/** lamp glow (linear, above 1 for the bloom) */
const HEAD_GLOW = new THREE.Color(1, 0.92, 0.8).multiplyScalar(2.4);
const TAIL_GLOW = new THREE.Color(1, 0.05, 0.03).multiplyScalar(1.8);
const PARK_GLOW = new THREE.Color(1, 0.86, 0.66).multiplyScalar(0.9);

type Simplifier = (typeof import('meshoptimizer'))['MeshoptSimplifier'];

const cache = new Map<CarId, TrafficModel>();

export function trafficModel(id: CarId) {
  return cache.get(id);
}

/** Build (once) the traffic copies of these cars; call after the car GLBs are loaded. */
export async function loadTrafficModels(ids: CarId[]) {
  if (ids.every((id) => cache.has(id))) return;
  let simplifier: Simplifier | null = null;
  try {
    const { MeshoptSimplifier } = await import('meshoptimizer');
    await MeshoptSimplifier.ready;
    if (MeshoptSimplifier.supported) simplifier = MeshoptSimplifier;
  } catch (e) {
    console.warn('mesh simplifier unavailable: traffic cars at full detail', e);
  }
  for (const id of ids) {
    if (cache.has(id)) continue;
    try {
      cache.set(id, buildTrafficModel(id, simplifier));
    } catch (e) {
      console.warn(`traffic model ${id} failed`, e);
    }
    // one car per task: the loading screen keeps animating
    await new Promise((r) => setTimeout(r, 0));
  }
}

interface Bucket {
  part: TrafficPart;
  color: THREE.Color;
  /** welded positions and triangle indices */
  pos: number[];
  idx: number[];
  lookup: Map<number, number>;
}

function buildTrafficModel(id: CarId, simplifier: Simplifier | null): TrafficModel {
  const rig = buildCar(CAR_SPECS[id]);
  const root = rig.root;
  root.updateMatrixWorld(true);
  const popUps = !!rig.popUps;
  const buckets = new Map<THREE.Material, Bucket | null>();
  const v = new THREE.Vector3();
  root.traverse((o) => {
    const mesh = o as THREE.Mesh;
    if (!mesh.isMesh || !mesh.visible) return;
    const geo = mesh.geometry;
    const pos = geo.getAttribute('position');
    if (!pos) return;
    const index = geo.getIndex();
    const mats = ([] as THREE.Material[]).concat(mesh.material);
    const groups = geo.groups.length ? geo.groups : [{ start: 0, count: index ? index.count : pos.count, materialIndex: 0 }];
    for (const g of groups) {
      const mat = mats[g.materialIndex ?? 0];
      if (!mat) continue;
      let b = buckets.get(mat);
      if (b === undefined) {
        const role = roleOf(mat as THREE.MeshStandardMaterial, popUps);
        buckets.set(mat, (b = role && { ...role, pos: [], idx: [], lookup: new Map() }));
      }
      if (!b) continue;
      const end = Math.min(g.start + g.count, index ? index.count : pos.count);
      for (let k = g.start; k < end; k++) {
        v.fromBufferAttribute(pos, index ? index.getX(k) : k).applyMatrix4(mesh.matrixWorld);
        b.idx.push(weld(b, v));
      }
    }
  });
  const parts: Partial<Record<TrafficPart, THREE.BufferGeometry[]>> = {};
  for (const b of buckets.values()) {
    if (!b) continue;
    let idx: Uint32Array = new Uint32Array(b.idx.length - (b.idx.length % 3));
    idx.set(b.idx.slice(0, idx.length));
    const pos = new Float32Array(b.pos);
    if (simplifier && idx.length > 3) idx = simplifier.simplify(idx, pos, 3, 0, ERROR, ['ErrorAbsolute', 'Prune'])[0];
    if (idx.length < 3) continue;
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    geo.setIndex(new THREE.BufferAttribute(idx, 1));
    const flat = toCreasedNormals(geo, CREASE);
    geo.dispose();
    const n = flat.getAttribute('position').count;
    const color = new Float32Array(n * 3);
    for (let k = 0; k < n; k++) color.set([b.color.r, b.color.g, b.color.b], k * 3);
    flat.setAttribute('color', new THREE.BufferAttribute(color, 3));
    for (const name of Object.keys(flat.attributes)) if (!['position', 'normal', 'color'].includes(name)) flat.deleteAttribute(name);
    (parts[b.part] ??= []).push(flat);
  }
  const merged: TrafficModel['parts'] = {};
  for (const p of TRAFFIC_PARTS) {
    const list = parts[p];
    if (!list?.length) continue;
    merged[p] = list.length === 1 ? list[0] : mergeGeometries(list);
    merged[p]!.computeBoundingSphere();
    if (list.length > 1) list.forEach((g) => g.dispose());
  }
  return { id, parts: merged, headlights: rig.anchors.headlights, taillights: rig.anchors.taillights, popUps };
}

/** index of the welded vertex at `p` (0.1 mm grid) */
function weld(b: Bucket, p: THREE.Vector3) {
  const q = (x: number) => Math.round(THREE.MathUtils.clamp(x, -9, 9) * 1e4) + 90000;
  const key = (q(p.x) * 180001 + q(p.y)) * 180001 + q(p.z);
  let i = b.lookup.get(key);
  if (i === undefined) {
    i = b.pos.length / 3;
    b.lookup.set(key, i);
    b.pos.push(p.x, p.y, p.z);
  }
  return i;
}

function roleOf(mat: THREE.MeshStandardMaterial, popUps: boolean): { part: TrafficPart; color: THREE.Color } | null {
  switch (mat.name) {
    case 'paint':
      return { part: 'paint', color: new THREE.Color(1, 1, 1) };
    case 'popup_lens':
      return { part: 'lamp', color: HEAD_GLOW };
    case 'headlight':
      // with pop-ups the 'headlight' parts are the bumper's parking lamps
      return { part: 'lamp', color: popUps ? PARK_GLOW : HEAD_GLOW };
    case 'taillight':
      return { part: 'lamp', color: TAIL_GLOW };
  }
  // cut-outs (alpha-masked decals, meshes) cannot be baked into an opaque copy
  if (mat.alphaTest > 0) return null;
  const color = (mat.color?.clone() ?? new THREE.Color(0.5, 0.5, 0.5)).multiply(textureMean(mat.map ?? null));
  // the glass is opaque here (nothing to see inside at night): a dark tint
  const glass = mat.name === 'glass' || (mat.transparent && mat.opacity < 0.95);
  if (glass) return { part: 'gloss', color: color.multiplyScalar(0.6) };
  // shiny and light: chrome, rims; dark parts (tyres, black plastics) stay matte even when a model calls them glossy
  const glossy = ((mat.metalness ?? 0) > 0.5 || (mat.roughness ?? 1) < 0.25) && 0.2126 * color.r + 0.7152 * color.g + 0.0722 * color.b > 0.08;
  return { part: glossy ? 'gloss' : 'matte', color };
}

const means = new WeakMap<THREE.Texture, THREE.Color>();

/** a texture's average colour (linear), white when it cannot be read */
function textureMean(tex: THREE.Texture | null): THREE.Color {
  const white = new THREE.Color(1, 1, 1);
  if (!tex) return white;
  const known = means.get(tex);
  if (known) return known;
  const img = tex.image as CanvasImageSource | undefined;
  if (!img || typeof document === 'undefined') return white;
  try {
    const c = document.createElement('canvas');
    c.width = c.height = 8;
    const g = c.getContext('2d', { willReadFrequently: true });
    if (!g) return white;
    g.drawImage(img, 0, 0, 8, 8);
    const d = g.getImageData(0, 0, 8, 8).data;
    let r = 0, gr = 0, bl = 0, w = 0;
    for (let k = 0; k < 64; k++) {
      const a = d[k * 4 + 3] / 255;
      r += d[k * 4] * a;
      gr += d[k * 4 + 1] * a;
      bl += d[k * 4 + 2] * a;
      w += a;
    }
    if (w < 0.5) return white;
    const out = new THREE.Color().setRGB(r / w / 255, gr / w / 255, bl / w / 255, THREE.SRGBColorSpace);
    means.set(tex, out);
    return out;
  } catch {
    return white;
  }
}
