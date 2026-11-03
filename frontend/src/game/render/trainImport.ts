import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';

/**
 * Dev-only: cuts three cars (leading, middle, trailing) out of third-party train models and writes them as one
 * GLB with the nodes car0 / car1 / car2 (used by tools/import-trains.cjs through `window.__importTrain`).
 * Every car ends up in metres, centred on its own middle at road level, front towards +Z (the trailing car's
 * cab towards −Z). Triangles crossing a cut are clipped there. Materials collapse to vertex colours plus one
 * mesh per texture (the sources have up to a hundred materials per car); see/through glass becomes dark glass.
 */
export interface TrainCarCut {
  /** index into `files` */
  file: number;
  /** range along the source's length axis (source units) */
  from: number;
  to: number;
  /** turn the car round (its cab was at the wrong end) */
  flip?: boolean;
}

export interface TrainImportConfig {
  files: string[];
  /** source axis along the train */
  axis: 'x' | 'z';
  /** metres per source unit along the train, up, across */
  scale: [number, number, number];
  /** the leading end is at the low end of the axis (else at the high end) */
  frontAtMin?: boolean;
  cars: [TrainCarCut, TrainCarCut, TrainCarCut];
  /** label pattern ("<mesh> <material>") of parts to leave out (track, ground planes) */
  drop?: string;
}

interface Tri {
  /** 3 vertices × (x, y, z) in metres, train frame */
  p: number[];
  n: number[];
  uv: number[] | null;
  color: THREE.Color;
  map: THREE.Texture | null;
  glass: boolean;
}

async function loadTris(url: string, cfg: TrainImportConfig) {
  const gltf = await new GLTFLoader().loadAsync(url);
  gltf.scene.updateMatrixWorld(true);
  const drop = cfg.drop ? new RegExp(cfg.drop, 'i') : null;
  const out: Tri[] = [];
  const [sl, su, sw] = cfg.scale;
  const v = new THREE.Vector3(), nv = new THREE.Vector3(), nm = new THREE.Matrix3();
  gltf.scene.traverse((o) => {
    const m = o as THREE.Mesh;
    if (!m.isMesh || !m.visible) return;
    const mats = ([] as THREE.Material[]).concat(m.material);
    const geo = m.geometry.index ? m.geometry.toNonIndexed() : m.geometry;
    const pos = geo.getAttribute('position'), nor = geo.getAttribute('normal'), uvs = geo.getAttribute('uv');
    nm.getNormalMatrix(m.matrixWorld);
    const groups = geo.groups.length ? geo.groups : [{ start: 0, count: pos.count, materialIndex: 0 }];
    for (const g of groups) {
      const mat = mats[g.materialIndex ?? 0] as THREE.MeshStandardMaterial & { transmission?: number };
      if (drop && drop.test(`${m.name} ${mat.name}`)) continue;
      const glass = (mat.transmission ?? 0) > 0.1 || (mat.transparent && mat.opacity < 0.9);
      for (let i = g.start; i + 2 < g.start + g.count; i += 3) {
        const t: Tri = { p: [], n: [], uv: uvs && mat.map && !glass ? [] : null, color: mat.color?.clone() ?? new THREE.Color(1, 1, 1), map: glass ? null : (mat.map ?? null), glass };
        for (let k = 0; k < 3; k++) {
          v.fromBufferAttribute(pos, i + k).applyMatrix4(m.matrixWorld);
          // source → train frame: length along +z, up +y, across x (metres). For an x-long source this is a
          // quarter turn about y (x' = −z, z' = x); swapping the axes instead mirrored the model inside out
          const along = cfg.axis === 'x' ? v.x : v.z, across = cfg.axis === 'x' ? -v.z : v.x;
          t.p.push(across * sw, v.y * su, along * sl);
          if (nor) {
            nv.fromBufferAttribute(nor, i + k).applyMatrix3(nm);
            const na = cfg.axis === 'x' ? nv.x : nv.z, nc = cfg.axis === 'x' ? -nv.z : nv.x;
            const n = new THREE.Vector3(nc / sw, nv.y / su, na / sl).normalize();
            t.n.push(n.x, n.y, n.z);
          } else t.n.push(0, 1, 0);
          if (t.uv) t.uv.push(uvs!.getX(i + k), uvs!.getY(i + k));
        }
        out.push(t);
      }
    }
  });
  return out;
}

/** Sutherland–Hodgman clip of a triangle to z in [z0, z1]: 0..n triangles (fan of the clipped polygon). */
function clip(t: Tri, z0: number, z1: number): Tri[] {
  type V = { p: number[]; n: number[]; uv: number[] | null };
  let poly: V[] = [0, 1, 2].map((k) => ({ p: t.p.slice(k * 3, k * 3 + 3), n: t.n.slice(k * 3, k * 3 + 3), uv: t.uv ? t.uv.slice(k * 2, k * 2 + 2) : null }));
  const lerpV = (a: V, b: V, f: number): V => ({
    p: a.p.map((x, i) => x + (b.p[i] - x) * f),
    n: a.n.map((x, i) => x + (b.n[i] - x) * f),
    uv: a.uv && b.uv ? a.uv.map((x, i) => x + (b.uv![i] - x) * f) : null,
  });
  for (const [limit, keepAbove] of [[z0, true], [z1, false]] as const) {
    const inside = (q: V) => (keepAbove ? q.p[2] >= limit : q.p[2] <= limit);
    const next: V[] = [];
    for (let i = 0; i < poly.length; i++) {
      const a = poly[i], b = poly[(i + 1) % poly.length];
      if (inside(a)) next.push(a);
      if (inside(a) !== inside(b)) next.push(lerpV(a, b, (limit - a.p[2]) / (b.p[2] - a.p[2])));
    }
    poly = next;
    if (poly.length < 3) return [];
  }
  const tris: Tri[] = [];
  for (let i = 1; i + 1 < poly.length; i++) {
    const q = [poly[0], poly[i], poly[i + 1]];
    tris.push({ ...t, p: q.flatMap((x) => x.p), n: q.flatMap((x) => x.n), uv: t.uv ? q.flatMap((x) => x.uv!) : null });
  }
  return tris;
}

const GLASS = new THREE.Color('#1c2228');

function buildCar(tris: Tri[], flip: boolean) {
  const box = new THREE.Box3();
  for (const t of tris) for (let k = 0; k < 3; k++) box.expandByPoint(new THREE.Vector3(t.p[k * 3], t.p[k * 3 + 1], t.p[k * 3 + 2]));
  const c = box.getCenter(new THREE.Vector3());
  // centred on the car, wheels on y = 0; a flipped car turns half round about +y
  const place = new THREE.Matrix4().makeTranslation(-c.x, -box.min.y, -c.z);
  if (flip) place.premultiply(new THREE.Matrix4().makeRotationY(Math.PI));
  const byMap = new Map<THREE.Texture | null, Tri[]>();
  for (const t of tris) {
    if (!byMap.has(t.map)) byMap.set(t.map, []);
    byMap.get(t.map)!.push(t);
  }
  const group = new THREE.Group();
  for (const [map, list] of byMap) {
    const n = list.length * 3;
    const pos = new Float32Array(n * 3), nor = new Float32Array(n * 3), col = new Float32Array(n * 3), uv = map ? new Float32Array(n * 2) : null;
    list.forEach((t, i) => {
      pos.set(t.p, i * 9);
      nor.set(t.n, i * 9);
      const color = t.glass ? GLASS : t.color;
      for (let k = 0; k < 3; k++) col.set([color.r, color.g, color.b], i * 9 + k * 3);
      if (uv) uv.set(t.uv ?? [0, 0, 0, 0, 0, 0], i * 6);
    });
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    geo.setAttribute('normal', new THREE.BufferAttribute(nor, 3));
    geo.setAttribute('color', new THREE.BufferAttribute(col, 3));
    if (uv) geo.setAttribute('uv', new THREE.BufferAttribute(uv, 2));
    geo.applyMatrix4(place);
    // the sources are double-sided throughout (open shells, single planes)
    const mat = new THREE.MeshStandardMaterial({ map, vertexColors: true, roughness: 0.5, metalness: 0.25, side: THREE.DoubleSide });
    mat.name = map ? `train-tex-${byMap.size}` : 'train-colors';
    group.add(new THREE.Mesh(geo, mat));
  }
  box.applyMatrix4(place);
  return { group, size: box.getSize(new THREE.Vector3()) };
}

export async function importTrainModel(urls: string[], cfg: TrainImportConfig) {
  const sources = await Promise.all(urls.map((u) => loadTris(u, cfg)));
  const root = new THREE.Group();
  const stats: { length: number; width: number; height: number; tris: number; meshes: number }[] = [];
  cfg.cars.forEach((cut, k) => {
    const z0 = cut.from * cfg.scale[0], z1 = cut.to * cfg.scale[0];
    const tris = sources[cut.file].flatMap((t) => {
      const zs = [t.p[2], t.p[5], t.p[8]];
      if (Math.max(...zs) < z0 || Math.min(...zs) > z1) return [];
      if (Math.min(...zs) >= z0 && Math.max(...zs) <= z1) return [t];
      return clip(t, z0, z1);
    });
    // the leading end towards +z: models whose front is at the low end turn round as a whole
    const { group, size } = buildCar(tris, !!cfg.frontAtMin !== !!cut.flip);
    group.name = `car${k}`;
    root.add(group);
    stats.push({ length: +size.z.toFixed(2), width: +size.x.toFixed(2), height: +size.y.toFixed(2), tris: tris.length, meshes: group.children.length });
  });
  const { GLTFExporter } = await import('three/examples/jsm/exporters/GLTFExporter.js');
  const glb = await new Promise<ArrayBuffer>((resolve, reject) => new GLTFExporter().parse(root, (r) => resolve(r as ArrayBuffer), reject, { binary: true }));
  return { glb, stats };
}
