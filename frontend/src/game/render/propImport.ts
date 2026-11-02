import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { mergeGeometries, mergeVertices } from 'three/examples/jsm/utils/BufferGeometryUtils.js';

/**
 * Dev-only: converts a third-party scenery model (e.g. a Sketchfab glTF download) into the game's prop
 * GLB contract (see propAssets.ts / docs/ASSETS.md). Used by tools/import-props.cjs through
 * `window.__importProp` in a headless browser; not part of the normal game bundle path.
 *
 * Patterns are case-insensitive regular expressions matched against "<node path> <material name>", where
 * the node path is the names of the mesh and its ancestors joined with "/".
 */
export interface PropImportConfig {
  /** keep only the parts whose label matches (one model out of a pack) */
  select?: string;
  /** parts to leave out */
  drop?: string;
  /** Euler XYZ rotation (rad) applied first so that +Y is up */
  rotation?: [number, number, number];
  /** yaw (rad) applied next so that the prop's front faces +Z (for a lamp: its arm points along −X) */
  yaw?: number;
  /** height of the prop in metres (from `ground` to the top); or give `scale` */
  height?: number;
  scale?: number;
  /**
   * parts whose bounding-box centre (x, z) becomes the origin, or "@base" for the centre of what touches
   * the ground (a lamp's foot); default: the whole prop's box
   */
  pivot?: string;
  /** source y (after rotation, before scaling) that becomes ground level; default: lowest point */
  ground?: number;
  /** tweaks of the kept materials by label pattern */
  restyle?: Record<string, { color?: string; emissive?: string; emissiveIntensity?: number; metalness?: number; roughness?: number; map?: false }>;
  /** decimation of over-detailed untextured parts: { pattern: { keep, error } } */
  reduce?: Record<string, { keep: number; error?: number }>;
  /**
   * game roles by label pattern: matching parts get their own material named after the role
   * (e.g. "lamp": the glowing lens, switched with the time of day)
   */
  roles?: Record<string, string>;
  /** parts that turn (a wind turbine's blades): exported under node "rotor", spinning about its local +Z */
  rotor?: { parts: string; /** node animated in the source; its pivot and animation axis define the hub */ node?: string };
  /** named points: the centre of the matched parts' box ("<pattern>@bottom" for the bottom centre) */
  anchors?: Record<string, string>;
  /**
   * plant sets: a regular expression whose first capture group names the variant a part belongs to; each
   * variant is exported as its own node `variant_<name>` with its foot at the origin (scale from `scale`)
   */
  variants?: string;
  /** split each variant into this many plants standing side by side along X (sets modelled as one mesh) */
  splitX?: number;
  /**
   * decimation of textured parts keeping their UVs and normals (vertices are only removed, never moved):
   * keep = target fraction of triangles, error = max deviation relative to the part's size
   */
  simplify?: { keep: number; error?: number; /** never below this many triangles per part */ minTris?: number };
  /** render the kept materials opaque (the source asks for alpha cutout but its colour map has no alpha) */
  opaque?: boolean;
}

interface Part {
  label: string;
  geo: THREE.BufferGeometry;
  material: THREE.Material;
}

async function loadSource(url: string) {
  const gltf = await new GLTFLoader().loadAsync(url);
  return gltf;
}

function collectParts(scene: THREE.Object3D) {
  scene.updateMatrixWorld(true);
  const parts: Part[] = [];
  scene.traverse((o) => {
    const m = o as THREE.Mesh;
    if (!m.isMesh || !m.visible) return;
    const names: string[] = [];
    for (let p: THREE.Object3D | null = m; p && p !== scene; p = p.parent) if (p.name) names.unshift(p.name);
    const mats = Array.isArray(m.material) ? m.material : [m.material];
    const base = (m.geometry.index ? m.geometry.toNonIndexed() : m.geometry.clone()).applyMatrix4(m.matrixWorld);
    const add = (geo: THREE.BufferGeometry, mat: THREE.Material) => parts.push({ label: `${names.join('/')} ${mat.name}`, geo, material: mat });
    if (m.geometry.groups.length > 1 && mats.length > 1) {
      for (const g of m.geometry.groups) add(subGeometry(base, g.start, g.count), mats[g.materialIndex ?? 0]);
    } else add(base, mats[0]);
  });
  return parts;
}

function subGeometry(geo: THREE.BufferGeometry, start: number, count: number) {
  const out = new THREE.BufferGeometry();
  for (const [name, attr] of Object.entries(geo.attributes)) {
    const a = attr as THREE.BufferAttribute;
    out.setAttribute(name, new THREE.BufferAttribute(a.array.slice(start * a.itemSize, (start + count) * a.itemSize), a.itemSize, a.normalized));
  }
  return out;
}

async function decimate(geo: THREE.BufferGeometry, keep: number, error: number) {
  const { MeshoptSimplifier } = await import('three/examples/jsm/libs/meshopt_simplifier.module.js');
  await MeshoptSimplifier.ready;
  const bare = new THREE.BufferGeometry();
  bare.setAttribute('position', geo.getAttribute('position'));
  const welded = mergeVertices(bare, 1e-5);
  const index = welded.getIndex()!;
  const target = Math.max(3, Math.floor((index.count * keep) / 3) * 3);
  const [indices] = MeshoptSimplifier.simplify(new Uint32Array(index.array), welded.getAttribute('position').array as Float32Array, 3, target, error);
  welded.setIndex(new THREE.BufferAttribute(indices, 1));
  welded.computeVertexNormals();
  return welded.toNonIndexed();
}

/** UV-preserving decimation: a subset of the welded vertices is kept with their attributes. */
async function simplifyTextured(geo: THREE.BufferGeometry, keep: number, error: number) {
  const { MeshoptSimplifier } = await import('three/examples/jsm/libs/meshopt_simplifier.module.js');
  await MeshoptSimplifier.ready;
  const flat = geo.index ? geo.toNonIndexed() : geo;
  for (const n of Object.keys(flat.attributes)) if (!['position', 'normal', 'uv'].includes(n)) flat.deleteAttribute(n);
  const g = mergeVertices(flat, 1e-6);
  const index = g.getIndex()!;
  const pos = new Float32Array(g.getAttribute('position').array);
  const uv = g.getAttribute('uv');
  const attrs = new Float32Array(uv.count * 2);
  for (let i = 0; i < uv.count; i++) {
    attrs[i * 2] = uv.getX(i);
    attrs[i * 2 + 1] = uv.getY(i);
  }
  const target = Math.max(3, Math.floor((index.count * keep) / 3) * 3);
  // (present in three's meshoptimizer build, missing from its type declarations)
  const simplifier = MeshoptSimplifier as unknown as { simplifyWithAttributes: (...args: unknown[]) => [Uint32Array, number] };
  const [indices] = simplifier.simplifyWithAttributes(new Uint32Array(index.array), pos, 3, attrs, 2, [1.5, 1.5], null, target, error);
  g.setIndex(new THREE.BufferAttribute(indices, 1));
  // drop the vertices no triangle uses any more
  return mergeVertices(g.toNonIndexed(), 1e-6);
}

const boxOf = (geos: THREE.BufferGeometry[]) => {
  const box = new THREE.Box3();
  for (const g of geos) {
    g.computeBoundingBox();
    box.union(g.boundingBox!);
  }
  return box;
};

/** Axis (world space) and pivot of a node's rotation animation. */
function animatedHub(gltf: Awaited<ReturnType<typeof loadSource>>, nodeName: string) {
  const node = gltf.scene.getObjectByName(nodeName);
  if (!node) throw new Error(`rotor node ${nodeName} not found`);
  const pivot = node.getWorldPosition(new THREE.Vector3());
  let axis: THREE.Vector3 | null = null;
  for (const clip of gltf.animations) {
    for (const track of clip.tracks) {
      if (!track.name.endsWith('.quaternion') || !track.name.startsWith(node.name)) continue;
      const v = track.values;
      const n = v.length / 4;
      const q0 = new THREE.Quaternion().fromArray(v, 0);
      const q1 = new THREE.Quaternion().fromArray(v, Math.min(n - 1, Math.max(1, Math.floor(n / 4))) * 4);
      // node-local rotation between two keys: q0⁻¹·q1 = rotation about an axis in the node's frame
      const rel = q0.clone().invert().multiply(q1);
      const s = Math.sqrt(1 - rel.w * rel.w);
      if (s < 1e-6) continue;
      const local = new THREE.Vector3(rel.x / s, rel.y / s, rel.z / s);
      // to world: the node's parent frame times the node's rest rotation
      const parentQ = node.parent!.getWorldQuaternion(new THREE.Quaternion());
      axis = local.applyQuaternion(q0).applyQuaternion(parentQ).normalize();
    }
  }
  if (!axis) throw new Error(`no rotation animation on ${nodeName}`);
  return { pivot, axis };
}

export async function importPropModel(url: string, id: string, cfg: PropImportConfig) {
  if (cfg.variants) return importVariants(url, id, cfg);
  const re = (p?: string) => (p ? new RegExp(p, 'i') : null);
  const gltf = await loadSource(url);
  const holder = new THREE.Group();
  holder.add(gltf.scene);
  if (cfg.rotation) holder.rotation.set(cfg.rotation[0], cfg.rotation[1], cfg.rotation[2]);
  holder.rotateOnWorldAxis(new THREE.Vector3(0, 1, 0), cfg.yaw ?? 0);
  holder.updateMatrixWorld(true);
  const hub = cfg.rotor?.node ? animatedHub(gltf, cfg.rotor.node) : null;
  const [selectRe, dropRe] = [re(cfg.select), re(cfg.drop)];
  let parts = collectParts(holder).filter((p) => (!selectRe || selectRe.test(p.label)) && !(dropRe && dropRe.test(p.label)));
  if (!parts.length) throw new Error('no parts left');
  for (const [pattern, r] of Object.entries(cfg.reduce ?? {})) {
    const rx = new RegExp(pattern, 'i');
    for (const p of parts) if (rx.test(p.label)) p.geo = await decimate(p.geo, r.keep, r.error ?? 0.006);
  }

  // ---- to metres: origin under the pivot parts, ground at y = 0
  const all = boxOf(parts.map((p) => p.geo));
  const ground = cfg.ground ?? all.min.y;
  let pivotBox = all;
  if (cfg.pivot === '@base') {
    // whatever stands on the ground (a lamp's foot, not its arm): vertices in the lowest 3 %
    pivotBox = new THREE.Box3();
    const limit = ground + 0.03 * (all.max.y - ground);
    const v = new THREE.Vector3();
    for (const p of parts) {
      const pos = p.geo.getAttribute('position');
      for (let i = 0; i < pos.count; i++) if (v.fromBufferAttribute(pos, i).y <= limit) pivotBox.expandByPoint(v);
    }
  } else if (cfg.pivot) {
    const rx = new RegExp(cfg.pivot, 'i');
    pivotBox = boxOf(parts.filter((p) => rx.test(p.label)).map((p) => p.geo));
  }
  if (pivotBox.isEmpty()) throw new Error('no pivot parts matched');
  const c = pivotBox.getCenter(new THREE.Vector3());
  const scale = cfg.scale ?? (cfg.height ? cfg.height / (all.max.y - ground) : 1);
  const toProp = new THREE.Matrix4().makeScale(scale, scale, scale).multiply(new THREE.Matrix4().makeTranslation(-c.x, -ground, -c.z));
  for (const p of parts) p.geo.applyMatrix4(toProp);

  // ---- materials: restyled copies, role materials
  const rules = Object.entries(cfg.restyle ?? {}).map(([p, s]) => ({ rx: new RegExp(p, 'i'), s }));
  const roles = Object.entries(cfg.roles ?? {}).map(([p, name]) => ({ rx: new RegExp(p, 'i'), name }));
  const cache = new Map<string, THREE.Material>();
  const materialFor = (p: Part): THREE.Material => {
    const r = rules.findIndex((x) => x.rx.test(p.label));
    const role = roles.find((x) => x.rx.test(p.label))?.name;
    const key = `${p.material.uuid}|${r}|${role ?? ''}`;
    if (!cache.has(key)) {
      const m = p.material.clone() as THREE.MeshStandardMaterial;
      if (r >= 0) {
        const s = rules[r].s;
        if (s.map === false) m.map = null;
        if (s.color) m.color.set(s.color);
        if (s.emissive !== undefined) {
          m.emissive.set(s.emissive);
          m.emissiveIntensity = s.emissiveIntensity ?? 1;
          if (s.emissive === '#000000') m.emissiveMap = null;
        }
        if (s.metalness !== undefined) m.metalness = s.metalness;
        if (s.roughness !== undefined) m.roughness = s.roughness;
      }
      if (role) {
        m.name = role;
        // exported as glTF extras so the optimiser's de-duplication never merges two roles
        m.userData = { ...m.userData, propRole: role };
      }
      cache.set(key, m);
    }
    return cache.get(key)!;
  };

  // ---- rotor: hub at the node origin, spin axis → local +Z
  const rotorRe = re(cfg.rotor?.parts);
  const rotorParts = rotorRe ? parts.filter((p) => rotorRe.test(p.label)) : [];

  const meta: Record<string, unknown> = { id };
  // ---- anchors
  const anchors: Record<string, number[]> = {};
  for (const [name, spec] of Object.entries(cfg.anchors ?? {})) {
    const [pattern, where] = spec.split('@');
    const rx = new RegExp(pattern, 'i');
    const geos = [...parts, ...rotorParts].filter((p) => rx.test(p.label)).map((p) => p.geo);
    if (!geos.length) throw new Error(`anchor ${name}: no parts matched`);
    const b = boxOf(geos);
    const at = b.getCenter(new THREE.Vector3());
    if (where === 'bottom') at.y = b.min.y;
    anchors[name] = at.toArray().map((v) => +v.toFixed(4));
  }
  meta.anchors = anchors;
  const box = boxOf([...parts, ...rotorParts].map((p) => p.geo));
  meta.size = box.getSize(new THREE.Vector3()).toArray().map((v) => +v.toFixed(3));
  meta.min = box.min.toArray().map((v) => +v.toFixed(3));
  meta.max = box.max.toArray().map((v) => +v.toFixed(3));
  parts = parts.filter((p) => !rotorParts.includes(p));
  const root = new THREE.Group();
  root.name = `prop-${id}`;
  const merged = (list: Part[], parent: THREE.Object3D) => {
    const byMat = new Map<THREE.Material, THREE.BufferGeometry[]>();
    for (const p of list) {
      const m = materialFor(p);
      byMat.set(m, [...(byMat.get(m) ?? []), p.geo]);
    }
    for (const [mat, geos] of byMat) {
      // same attribute set for every piece (some exports carry uv1 / colours on a few meshes only)
      const names = Object.keys(geos[0].attributes).filter((n) => geos.every((g) => g.getAttribute(n)));
      for (const g of geos) for (const n of Object.keys(g.attributes)) if (!names.includes(n)) g.deleteAttribute(n);
      const geo = mergeVertices(mergeGeometries(geos)!, 1e-6);
      const mesh = new THREE.Mesh(geo, mat);
      mesh.name = `${id}_${mat.name || 'part'}`;
      parent.add(mesh);
    }
  };
  merged(parts, root);
  if (rotorParts.length) {
    const rotor = new THREE.Group();
    rotor.name = 'rotor';
    const pivot = hub ? hub.pivot.clone().applyMatrix4(toProp) : boxOf(rotorParts.map((p) => p.geo)).getCenter(new THREE.Vector3());
    const axis = hub ? hub.axis.clone() : new THREE.Vector3(0, 0, 1);
    // the spin direction is the game's choice: keep the axis pointing forward
    if (axis.z < 0) axis.negate();
    const q = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 0, 1), axis);
    const toRotor = new THREE.Matrix4().compose(pivot, q, new THREE.Vector3(1, 1, 1)).invert();
    for (const p of rotorParts) p.geo.applyMatrix4(toRotor);
    rotor.position.copy(pivot);
    rotor.quaternion.copy(q);
    merged(rotorParts, rotor);
    root.add(rotor);
    meta.rotor = { position: pivot.toArray(), quaternion: q.toArray() };
  }

  // stored on the root node (glTF extras): the optimiser keeps it, empties would be pruned
  root.userData = { prop: meta };

  const tris = [...parts, ...rotorParts].reduce((n, p) => n + p.geo.getAttribute('position').count / 3, 0);
  const stats = { scale: +scale.toFixed(5), tris, materials: cache.size, ...meta };
  const { GLTFExporter } = await import('three/examples/jsm/exporters/GLTFExporter.js');
  const glb = await new Promise<ArrayBuffer>((resolve, reject) => new GLTFExporter().parse(root, (r) => resolve(r as ArrayBuffer), reject, { binary: true }));
  return { glb, stats };
}

/**
 * Splits parts into `k` plants along X: 1-D k-means of the triangle centres (started at the quantiles),
 * then any cluster with under 5 % of the triangles (a stray leaf) joins its nearest neighbour.
 */
function splitAlongX(parts: Part[], k: number): Part[][] {
  const tris: { part: Part; t: number; x: number; g: number }[] = [];
  for (const part of parts) {
    const flat = part.geo.index ? part.geo.toNonIndexed() : part.geo;
    part.geo = flat;
    const pos = flat.getAttribute('position');
    for (let t = 0; t < pos.count / 3; t++) tris.push({ part, t, x: (pos.getX(t * 3) + pos.getX(t * 3 + 1) + pos.getX(t * 3 + 2)) / 3, g: 0 });
  }
  tris.sort((a, b) => a.x - b.x);
  let centres = Array.from({ length: k }, (_, j) => tris[Math.floor(((j + 0.5) / k) * tris.length)].x);
  for (let it = 0; it < 30; it++) {
    for (const e of tris) {
      let best = 0;
      for (let j = 1; j < centres.length; j++) if (Math.abs(e.x - centres[j]) < Math.abs(e.x - centres[best])) best = j;
      e.g = best;
    }
    centres = centres.map((c, j) => {
      const members = tris.filter((e) => e.g === j);
      return members.length ? members.reduce((sum, e) => sum + e.x, 0) / members.length : c;
    });
  }
  const sizes = centres.map((_, j) => tris.filter((e) => e.g === j).length);
  for (let j = 0; j < centres.length; j++) {
    if (sizes[j] >= 0.05 * tris.length || sizes[j] === 0) continue;
    let to = -1;
    for (let o = 0; o < centres.length; o++) if (o !== j && sizes[o] >= 0.05 * tris.length && (to < 0 || Math.abs(centres[o] - centres[j]) < Math.abs(centres[to] - centres[j]))) to = o;
    for (const e of tris) if (e.g === j) e.g = to;
    sizes[to] += sizes[j];
    sizes[j] = 0;
  }
  const out: Part[][] = [];
  for (let g = 0; g < centres.length; g++) {
    if (!sizes[g]) continue;
    const byPart = new Map<Part, number[]>();
    for (const e of tris) if (e.g === g) byPart.set(e.part, [...(byPart.get(e.part) ?? []), e.t]);
    out.push(
      [...byPart].map(([part, list]) => {
        const geo = new THREE.BufferGeometry();
        for (const [n, attr] of Object.entries(part.geo.attributes)) {
          const a = attr as THREE.BufferAttribute;
          const arr = new Float32Array(list.length * 3 * a.itemSize);
          list.forEach((t, j) => {
            for (let c = 0; c < 3 * a.itemSize; c++) arr[j * 3 * a.itemSize + c] = a.array[t * 3 * a.itemSize + c];
          });
          geo.setAttribute(n, new THREE.BufferAttribute(arr, a.itemSize, a.normalized));
        }
        return { label: part.label, geo, material: part.material };
      }),
    );
  }
  return out;
}

/** Plant sets: one node per variant, each standing at the origin, decimated with UVs kept. */
async function importVariants(url: string, id: string, cfg: PropImportConfig) {
  const gltf = await loadSource(url);
  const holder = new THREE.Group();
  holder.add(gltf.scene);
  if (cfg.rotation) holder.rotation.set(cfg.rotation[0], cfg.rotation[1], cfg.rotation[2]);
  holder.updateMatrixWorld(true);
  const rx = new RegExp(cfg.variants!, 'i');
  const dropRe = cfg.drop ? new RegExp(cfg.drop, 'i') : null;
  const groups = new Map<string, Part[]>();
  let before = 0;
  for (const p of collectParts(holder)) {
    if (dropRe?.test(p.label)) continue;
    const name = rx.exec(p.label)?.[1];
    if (!name) continue;
    before += p.geo.getAttribute('position').count / 3;
    groups.set(name, [...(groups.get(name) ?? []), p]);
  }
  if (!groups.size) throw new Error('no variants matched');
  if (cfg.splitX && cfg.splitX > 1) {
    for (const [name, parts] of [...groups]) {
      groups.delete(name);
      splitAlongX(parts, cfg.splitX).forEach((list, k) => groups.set(`${name}_${k}`, list));
    }
  }
  const scale = cfg.scale ?? 1;
  const materials = new Map<THREE.Material, THREE.MeshStandardMaterial>();
  const materialFor = (m: THREE.Material) => {
    if (!materials.has(m)) {
      const c = m.clone() as THREE.MeshStandardMaterial;
      if (cfg.opaque) {
        c.alphaTest = 0;
        c.transparent = false;
      }
      c.side = THREE.DoubleSide;
      materials.set(m, c);
    }
    return materials.get(m)!;
  };
  const root = new THREE.Group();
  root.name = `prop-${id}`;
  const variants: { name: string; tris: number; min: number[]; max: number[] }[] = [];
  let after = 0;
  for (const [name, parts] of [...groups].sort(([a], [b]) => a.localeCompare(b))) {
    if (cfg.simplify) {
      for (const p of parts) {
        const tris = (p.geo.index?.count ?? p.geo.getAttribute('position').count) / 3;
        const keep = Math.min(1, Math.max(cfg.simplify.keep, (cfg.simplify.minTris ?? 0) / tris));
        if (keep < 1) p.geo = await simplifyTextured(p.geo, keep, cfg.simplify.error ?? 0.01);
      }
    }
    // foot: centre of what touches the ground, lowest point at y = 0
    const box = boxOf(parts.map((p) => p.geo));
    const limit = box.min.y + 0.05 * (box.max.y - box.min.y);
    const foot = new THREE.Box3();
    const v = new THREE.Vector3();
    for (const p of parts) {
      const pos = p.geo.getAttribute('position');
      for (let i = 0; i < pos.count; i++) if (v.fromBufferAttribute(pos, i).y <= limit) foot.expandByPoint(v);
    }
    const c = foot.getCenter(new THREE.Vector3());
    const m = new THREE.Matrix4().makeScale(scale, scale, scale).multiply(new THREE.Matrix4().makeTranslation(-c.x, -box.min.y, -c.z));
    const node = new THREE.Group();
    node.name = `variant_${name}`;
    const byMat = new Map<THREE.Material, THREE.BufferGeometry[]>();
    for (const p of parts) {
      p.geo.applyMatrix4(m);
      const mat = materialFor(p.material);
      byMat.set(mat, [...(byMat.get(mat) ?? []), p.geo]);
    }
    let tris = 0;
    for (const [mat, geos] of byMat) {
      const names = Object.keys(geos[0].attributes).filter((n) => geos.every((g) => g.getAttribute(n)));
      for (const g of geos) for (const n of Object.keys(g.attributes)) if (!names.includes(n)) g.deleteAttribute(n);
      const geo = mergeVertices(mergeGeometries(geos.map((g) => (g.index ? g.toNonIndexed() : g)))!, 1e-6);
      tris += geo.getIndex()!.count / 3;
      const mesh = new THREE.Mesh(geo, mat);
      mesh.name = `${id}_${name}`;
      node.add(mesh);
    }
    after += tris;
    const vb = boxOf(node.children.map((o) => (o as THREE.Mesh).geometry));
    variants.push({ name, tris, min: vb.min.toArray().map((x) => +x.toFixed(3)), max: vb.max.toArray().map((x) => +x.toFixed(3)) });
    root.add(node);
  }
  const all = boxOf(root.children.flatMap((n) => n.children.map((o) => (o as THREE.Mesh).geometry)));
  root.userData = { prop: { id, anchors: {}, variants, min: all.min.toArray(), max: all.max.toArray() } };
  const stats = { scale, trisBefore: before, tris: after, variants };
  const { GLTFExporter } = await import('three/examples/jsm/exporters/GLTFExporter.js');
  const glb = await new Promise<ArrayBuffer>((resolve, reject) => new GLTFExporter().parse(root, (r) => resolve(r as ArrayBuffer), reject, { binary: true }));
  return { glb, stats };
}

/**
 * Dev-only: renders a model from the front (+Z), side (+X) and top, with a 1 m grid and a red marker
 * along +Z, for picking `rotation` / `yaw`. With a config the converted prop is shown instead.
 */
export async function previewPropModel(url: string, cfg?: PropImportConfig, id = 'preview') {
  let object: THREE.Object3D;
  if (cfg) {
    const { glb } = await importPropModel(url, id, cfg);
    const gltf = await new GLTFLoader().parseAsync(glb, '');
    object = gltf.scene;
    // plant sets: variants side by side along X
    const variants: THREE.Object3D[] = [];
    object.traverse((o) => o.name.startsWith('variant_') && variants.push(o));
    let x = 0;
    for (const v of variants) {
      const b = new THREE.Box3().setFromObject(v);
      v.position.x = x - b.min.x;
      x += b.max.x - b.min.x + 0.2;
    }
  } else {
    object = (await loadSource(url)).scene;
  }
  const scene = new THREE.Scene();
  scene.background = new THREE.Color('#8a94a6');
  scene.add(object, new THREE.HemisphereLight('#ffffff', '#445566', 2.5));
  const sun = new THREE.DirectionalLight('#ffffff', 2);
  sun.position.set(3, 5, 4);
  scene.add(sun);
  object.updateMatrixWorld(true);
  const box = new THREE.Box3().setFromObject(object);
  const c = box.getCenter(new THREE.Vector3());
  const r = box.getSize(new THREE.Vector3()).length() / 2;
  if (cfg) {
    const grid = new THREE.GridHelper(Math.ceil(r * 2.5), Math.ceil(r * 2.5), '#ffffff', '#c0c4cc');
    const arrow = new THREE.ArrowHelper(new THREE.Vector3(0, 0, 1), new THREE.Vector3(0, 0.05, 0), r, '#ff2020');
    scene.add(grid, arrow);
  }
  const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
  renderer.setSize(480, 360);
  const cam = new THREE.PerspectiveCamera(35, 480 / 360, r / 50, r * 20);
  const shots: Record<string, string> = {};
  for (const [name, dir] of [['front_+z', [0, 0.25, 1]], ['side_+x', [1, 0.25, 0]], ['top_+y', [0, 1, 0.001]], ['back_-z', [0, 0.25, -1]]] as const) {
    cam.position.copy(c).addScaledVector(new THREE.Vector3(...dir).normalize(), r * 3);
    cam.lookAt(c);
    renderer.render(scene, cam);
    shots[name] = renderer.domElement.toDataURL('image/png');
  }
  renderer.dispose();
  return { shots, box: { min: box.min.toArray(), max: box.max.toArray() } };
}
