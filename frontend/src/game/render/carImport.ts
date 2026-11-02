import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import type { CarSpec } from '../vehicle/carSpecs';

/**
 * Dev-only: converts a third-party car model (e.g. a Sketchfab glTF download) into the game's car
 * GLB contract (see rigFromTemplate / docs/ASSETS.md). Used by tools/import-cars.cjs through
 * `window.__importCar` in a headless browser; not part of the normal game bundle path.
 *
 * Patterns are case-insensitive regular expressions matched against "<node name> <material name>".
 */
export interface CarImportConfig {
  /** Euler XYZ rotation (rad) applied first so that +Y is up and the car lies along Z */
  rotation?: [number, number, number];
  /** spinning wheel parts: tyres, rims, brake discs (merged meshes are split by corner) */
  wheels: string;
  /** parts that steer with the wheel but do not spin (calipers) */
  calipers?: string;
  /** body paint (becomes the tweakable "paint" material) */
  paint: string;
  glass?: string;
  /** front lamps (become the emissive "headlight" material); also decide which end is the front */
  headlights?: string;
  taillights?: string;
  /** parts to leave out (hidden internals, stands, duplicate shells) */
  drop?: string;
  /** set when the model's front is towards −Z and there are no headlight parts to tell */
  faceNegZ?: boolean;
  /** tweaks of the kept materials by label pattern, e.g. to tone down a show car's glowing rims */
  restyle?: Record<string, { color?: string; emissive?: string; metalness?: number; roughness?: number; map?: false }>;
  /**
   * extra decimation of over-detailed untextured parts (e.g. tyre tread): { pattern: { keep, error } } —
   * keep = target fraction of triangles, error = max deviation relative to the part's size (default 0.006)
   */
  reduce?: Record<string, { keep: number; error?: number }>;
  /**
   * retractable headlamps modelled raised: connected pieces lying wholly inside `box` (source units after
   * `rotation`, [x0, x1, y0, y1, z0, z1]; the x range applies to |x|, so it covers both sides) become the
   * hinged nodes "popup_l" / "popup_r" (hinge along their rear top edge, closing angle in the node's
   * extras) that the game folds into the bonnet by day; pieces matching `lens` get the "popup_lens" material.
   * `closed`: front-down angle (rad) that lays the pod's top flush with the bonnet
   */
  popUps?: { box: [number, number, number, number, number, number]; lens: string; closed: number };
}

interface Part {
  name: string;
  geo: THREE.BufferGeometry;
  material: THREE.Material;
  /** piece of a pop-up lamp (see CarImportConfig.popUps) */
  pod?: boolean;
}

const CORNERS = ['fl', 'fr', 'rl', 'rr'] as const;

async function loadParts(url: string, rotation?: [number, number, number]) {
  const gltf = await new GLTFLoader().loadAsync(url);
  const holder = new THREE.Group();
  holder.add(gltf.scene);
  if (rotation) holder.rotation.set(rotation[0], rotation[1], rotation[2]);
  holder.updateMatrixWorld(true);
  const parts: Part[] = [];
  gltf.scene.traverse((o) => {
    const m = o as THREE.Mesh;
    if (!m.isMesh || !m.visible) return;
    const mats = Array.isArray(m.material) ? m.material : [m.material];
    // non-indexed copy: keeps only referenced vertices (some exports carry stray ones that wreck bounds)
    const base = (m.geometry.index ? m.geometry.toNonIndexed() : m.geometry.clone()).applyMatrix4(m.matrixWorld);
    if (m.geometry.groups.length > 1 && mats.length > 1) {
      for (const g of m.geometry.groups) parts.push({ name: m.name, geo: subGeometry(base, g.start, g.count), material: mats[g.materialIndex ?? 0] });
    } else parts.push({ name: m.name, geo: base, material: mats[0] });
  });
  return parts;
}

/** Triangles [start, start + count) of an (indexed or not) geometry as a new non-indexed geometry. */
/**
 * Error-bounded decimation of an untextured part: welded by position only (so hard edges do not stop
 * the simplifier), smooth normals afterwards. Bounded so that holes (a tyre round its rim) stay open.
 */
async function decimate(geo: THREE.BufferGeometry, keep: number, error: number) {
  const { MeshoptSimplifier } = await import('three/examples/jsm/libs/meshopt_simplifier.module.js');
  const { mergeVertices } = await import('three/examples/jsm/utils/BufferGeometryUtils.js');
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

function subGeometry(geo: THREE.BufferGeometry, start: number, count: number) {
  const flat = geo.index ? geo.toNonIndexed() : geo;
  const out = new THREE.BufferGeometry();
  for (const [name, attr] of Object.entries(flat.attributes)) {
    const a = attr as THREE.BufferAttribute;
    out.setAttribute(name, new THREE.BufferAttribute(a.array.slice(start * a.itemSize, (start + count) * a.itemSize), a.itemSize, a.normalized));
  }
  return out;
}

/** Triangles `tris` of a non-indexed geometry as a new geometry. */
function pickTriangles(flat: THREE.BufferGeometry, tris: number[]) {
  const out = new THREE.BufferGeometry();
  for (const [name, attr] of Object.entries(flat.attributes)) {
    const a = attr as THREE.BufferAttribute;
    const arr = new (a.array.constructor as Float32ArrayConstructor)(tris.length * 3 * a.itemSize);
    tris.forEach((t, i) => arr.set(a.array.subarray(t * 3 * a.itemSize, (t + 1) * 3 * a.itemSize), i * 3 * a.itemSize));
    out.setAttribute(name, new THREE.BufferAttribute(arr, a.itemSize, a.normalized));
  }
  return out;
}

/** Splits a geometry into the four wheel corners by triangle centroid (merged wheel meshes). */
function splitByCorner(geo: THREE.BufferGeometry, cx: number, cz: number): (THREE.BufferGeometry | null)[] {
  const flat = geo.index ? geo.toNonIndexed() : geo;
  const pos = flat.getAttribute('position');
  const buckets: number[][] = [[], [], [], []];
  for (let t = 0; t < pos.count / 3; t++) {
    let x = 0, z = 0;
    for (let k = 0; k < 3; k++) {
      x += pos.getX(t * 3 + k);
      z += pos.getZ(t * 3 + k);
    }
    // fl: +x (left), +z (front); fr: −x; rl / rr: rear
    buckets[(z / 3 > cz ? 0 : 2) + (x / 3 > cx ? 0 : 1)].push(t);
  }
  return buckets.map((tris) => (tris.length ? pickTriangles(flat, tris) : null));
}

/**
 * Cuts the connected pieces (triangles sharing vertex positions) that lie wholly inside the box
 * (x range on |x|) out of a part: returns [pieces inside, the rest], either may be null.
 */
function cutPieces(geo: THREE.BufferGeometry, box: [number, number, number, number, number, number]) {
  const flat = geo.index ? geo.toNonIndexed() : geo;
  const pos = flat.getAttribute('position');
  const n = pos.count / 3;
  const parent = Array.from({ length: n }, (_, i) => i);
  const find = (i: number): number => (parent[i] === i ? i : (parent[i] = find(parent[i])));
  const owner = new Map<string, number>();
  for (let v = 0; v < pos.count; v++) {
    const key = `${pos.getX(v).toFixed(4)},${pos.getY(v).toFixed(4)},${pos.getZ(v).toFixed(4)}`;
    const t = Math.floor(v / 3);
    const o = owner.get(key);
    if (o === undefined) owner.set(key, t);
    else parent[find(t)] = find(o);
  }
  const [x0, x1, y0, y1, z0, z1] = box;
  const inBox = new Map<number, boolean>();
  for (let v = 0; v < pos.count; v++) {
    const r = find(Math.floor(v / 3));
    const x = Math.abs(pos.getX(v)), y = pos.getY(v), z = pos.getZ(v);
    const ok = x >= x0 && x <= x1 && y >= y0 && y <= y1 && z >= z0 && z <= z1;
    inBox.set(r, (inBox.get(r) ?? true) && ok);
  }
  const inside: number[] = [], rest: number[] = [];
  for (let t = 0; t < n; t++) (inBox.get(find(t)) ? inside : rest).push(t);
  return [inside.length ? pickTriangles(flat, inside) : null, rest.length ? pickTriangles(flat, rest) : null] as const;
}

const boxOf = (geos: THREE.BufferGeometry[]) => {
  const box = new THREE.Box3();
  for (const g of geos) {
    g.computeBoundingBox();
    box.union(g.boundingBox!);
  }
  return box;
};

export async function importCarModel(url: string, spec: CarSpec, cfg: CarImportConfig) {
  const re = (p?: string) => (p ? new RegExp(p, 'i') : null);
  const [wheelRe, caliperRe, paintRe, glassRe, headRe, tailRe, dropRe] = [cfg.wheels, cfg.calipers, cfg.paint, cfg.glass, cfg.headlights, cfg.taillights, cfg.drop].map(re);
  const label = (p: Part) => `${p.name} ${p.material.name}`;
  const parts = (await loadParts(url, cfg.rotation)).filter((p) => !(dropRe && dropRe.test(label(p))));
  for (const [pattern, r] of Object.entries(cfg.reduce ?? {})) {
    const rx = new RegExp(pattern, 'i');
    for (const p of parts) if (rx.test(label(p))) p.geo = await decimate(p.geo, r.keep, r.error ?? 0.006);
  }
  if (cfg.popUps) {
    for (const p of [...parts]) {
      if (wheelRe!.test(label(p))) continue;
      const [pod, rest] = cutPieces(p.geo, cfg.popUps.box);
      if (!pod) continue;
      // both sides stay in one part here: split by side once the car frame is known
      parts.push({ name: p.name, geo: pod, material: p.material, pod: true });
      if (rest) p.geo = rest;
      else parts.splice(parts.indexOf(p), 1);
    }
  }
  const podParts = parts.filter((p) => p.pod);
  const wheelParts = parts.filter((p) => !p.pod && wheelRe!.test(label(p)));
  const caliperParts = parts.filter((p) => !p.pod && !wheelRe!.test(label(p)) && caliperRe?.test(label(p)));
  const bodyParts = parts.filter((p) => !p.pod && !wheelParts.includes(p) && !caliperParts.includes(p));
  if (!wheelParts.length) throw new Error('no wheel parts matched');

  // ---- restyled copies of kept materials (one per source material and rule)
  const rules = Object.entries(cfg.restyle ?? {}).map(([p, s]) => ({ rx: new RegExp(p, 'i'), s }));
  const restyled = new Map<string, THREE.Material>();
  const restyle = (p: Part): THREE.Material => {
    const k = rules.findIndex((r) => r.rx.test(label(p)));
    if (k < 0) return p.material;
    const key = `${p.material.uuid}|${k}`;
    if (!restyled.has(key)) {
      const m = p.material.clone() as THREE.MeshStandardMaterial;
      const s = rules[k].s;
      if (s.color) m.color.set(s.color);
      if (s.emissive !== undefined) {
        m.emissive.set(s.emissive);
        m.emissiveIntensity = 1;
      }
      if (s.metalness !== undefined) m.metalness = s.metalness;
      if (s.roughness !== undefined) m.roughness = s.roughness;
      // e.g. blank number plates instead of a film car's well-known registration
      if (s.map === false) m.map = null;
      restyled.set(key, m);
    }
    return restyled.get(key)!;
  };

  // ---- front at +Z: decided by where the headlights are
  let flip = !!cfg.faceNegZ;
  if (headRe) {
    const heads = bodyParts.filter((p) => headRe.test(label(p)));
    const all = boxOf(parts.map((p) => p.geo));
    if (heads.length) flip = boxOf(heads.map((p) => p.geo)).getCenter(new THREE.Vector3()).z < all.getCenter(new THREE.Vector3()).z;
  }
  if (flip) for (const p of parts) p.geo.rotateY(Math.PI);

  // ---- wheel corners
  const wbox = boxOf(wheelParts.map((p) => p.geo));
  const wc = wbox.getCenter(new THREE.Vector3());
  const corner: { geos: { geo: THREE.BufferGeometry; material: THREE.Material; spin: boolean }[]; box: THREE.Box3 }[] = CORNERS.map(() => ({ geos: [], box: new THREE.Box3() }));
  for (const [list, spin] of [[wheelParts, true], [caliperParts, false]] as const) {
    for (const p of list) {
      splitByCorner(p.geo, wc.x, wc.z).forEach((g, q) => {
        if (!g) return;
        corner[q].geos.push({ geo: g, material: restyle(p), spin });
        if (spin) {
          g.computeBoundingBox();
          corner[q].box.union(g.boundingBox!);
        }
      });
    }
  }
  if (corner.some((c) => c.box.isEmpty())) throw new Error('a wheel corner is empty');
  const centers = corner.map((c) => c.box.getCenter(new THREE.Vector3()));
  const radii = corner.map((c) => {
    const s = c.box.getSize(new THREE.Vector3());
    return Math.max(s.y, s.z) / 2;
  });
  const wheelbase = (centers[0].z + centers[1].z) / 2 - (centers[2].z + centers[3].z) / 2;
  const scale = spec.wheelbase / wheelbase;
  const ground = Math.min(...centers.map((c, i) => c.y - radii[i]));
  const origin = new THREE.Vector3((centers[0].x + centers[1].x + centers[2].x + centers[3].x) / 4, ground, (centers[0].z + centers[1].z + centers[2].z + centers[3].z) / 4);
  const toCar = new THREE.Matrix4().makeScale(scale, scale, scale).multiply(new THREE.Matrix4().makeTranslation(-origin.x, -origin.y, -origin.z));

  // ---- materials: the names the game swaps for its tweakable ones
  // one renamed copy per (source material, role): a material shared by e.g. window and headlamp glass
  // must become two different game materials
  const renamed = new Map<string, Map<THREE.Material, THREE.Material>>();
  const named = (m: THREE.Material, name: string) => {
    const byRole = renamed.get(name) ?? new Map<THREE.Material, THREE.Material>();
    renamed.set(name, byRole);
    if (!byRole.has(m)) {
      const c = m.clone();
      c.name = name;
      // also tag it (exported as glTF extras) so the optimiser's de-duplication never merges two roles
      c.userData = { ...c.userData, carRole: name };
      byRole.set(m, c);
    }
    return byRole.get(m)!;
  };
  const materialFor = (p: Part) => {
    const l = label(p);
    if (paintRe!.test(l)) return named(p.material, 'paint');
    if (headRe?.test(l)) return named(p.material, 'headlight');
    if (tailRe?.test(l)) return named(p.material, 'taillight');
    if (glassRe?.test(l)) return named(p.material, 'glass');
    return restyle(p);
  };

  const root = new THREE.Group();
  root.name = `car-${spec.id}`;
  const body = new THREE.Group();
  body.name = 'body';
  root.add(body);
  for (const p of bodyParts) {
    p.geo.applyMatrix4(toCar);
    const mesh = new THREE.Mesh(p.geo, materialFor(p));
    mesh.name = p.name;
    body.add(mesh);
  }
  // ---- pop-up lamps: one hinge per side along the rear top edge of its pieces
  if (cfg.popUps && podParts.length) {
    const lensRe = new RegExp(cfg.popUps.lens, 'i');
    for (const p of podParts) p.geo.applyMatrix4(toCar);
    for (const side of [1, -1]) {
      const pieces = podParts.flatMap((p) => {
        // with the split line at −∞ along z only the left (+x) and right buckets are used
        const halves = splitByCorner(p.geo, 0, -Infinity);
        const mine = side > 0 ? halves[0] : halves[1];
        return mine ? [{ p, geo: mine }] : [];
      });
      if (!pieces.length) continue;
      const box = boxOf(pieces.map((q) => q.geo));
      // hinge along the rear top edge: the highest point of the pod's back end
      let rearTop = -Infinity;
      for (const { geo } of pieces) {
        const pos = geo.getAttribute('position');
        for (let v = 0; v < pos.count; v++) if (pos.getZ(v) < box.min.z + 0.15 * (box.max.z - box.min.z)) rearTop = Math.max(rearTop, pos.getY(v));
      }
      const hinge = new THREE.Group();
      hinge.name = side > 0 ? 'popup_l' : 'popup_r';
      hinge.position.set((box.min.x + box.max.x) / 2, rearTop, box.min.z);
      hinge.userData = { popupClosed: cfg.popUps.closed };
      for (const { p, geo } of pieces) {
        geo.translate(-hinge.position.x, -hinge.position.y, -hinge.position.z);
        const mesh = new THREE.Mesh(geo, lensRe.test(label(p)) ? named(p.material, 'popup_lens') : restyle(p));
        mesh.name = `${hinge.name}_${p.name}`;
        hinge.add(mesh);
      }
      body.add(hinge);
    }
  }
  CORNERS.forEach((q, i) => {
    const c = centers[i].clone().applyMatrix4(toCar);
    // fit the wheel to the physics wheel radius (small corrections only)
    const fit = THREE.MathUtils.clamp(spec.wheelRadius / (radii[i] * scale), 0.85, 1.15);
    const pivot = new THREE.Group();
    pivot.name = `wheel_${q}`;
    pivot.position.copy(c);
    const spin = new THREE.Group();
    spin.name = `spin_${q}`;
    pivot.add(spin);
    root.add(pivot);
    for (const g of corner[i].geos) {
      g.geo.applyMatrix4(toCar).translate(-c.x, -c.y, -c.z).scale(fit, fit, fit);
      const mesh = new THREE.Mesh(g.geo, g.material);
      (g.spin ? spin : pivot).add(mesh);
    }
  });

  // ---- light anchors (left/right halves of the lamp geometry) and exhaust
  const anchor = (name: string, at: THREE.Vector3) => {
    const o = new THREE.Object3D();
    o.name = name;
    o.position.copy(at);
    root.add(o);
  };
  const lamps = (rx: RegExp | null, prefix: string) => {
    if (!rx) return;
    const geos = body.children.filter((m) => (m as THREE.Mesh).isMesh).filter((m) => rx.test(`${m.name} ${(m as THREE.Mesh).material && ((m as THREE.Mesh).material as THREE.Material).name}`) || ((m as THREE.Mesh).material as THREE.Material).name === prefix).map((m) => (m as THREE.Mesh).geometry);
    if (!geos.length) return;
    const box = boxOf(geos);
    const c = box.getCenter(new THREE.Vector3());
    const half = (box.max.x - box.min.x) / 4;
    anchor(`anchor_${prefix}_0`, new THREE.Vector3(c.x + half, c.y, c.z));
    anchor(`anchor_${prefix}_1`, new THREE.Vector3(c.x - half, c.y, c.z));
  };
  lamps(headRe, 'headlight');
  lamps(tailRe, 'taillight');
  const bodyBox = boxOf(body.children.filter((m) => (m as THREE.Mesh).isMesh).map((m) => (m as THREE.Mesh).geometry));
  anchor('anchor_exhaust', new THREE.Vector3(-0.45 * (bodyBox.max.x - bodyBox.min.x) / 2, 0.3, bodyBox.min.z + 0.05));
  const target = new THREE.Object3D();
  target.name = 'headlight_target';
  target.position.set(0, 0.3, 30);
  root.add(target);

  const stats = {
    scale: +scale.toFixed(4),
    wheelbase: +(wheelbase * scale).toFixed(3),
    track: +((centers[0].x - centers[1].x) * scale).toFixed(3),
    wheelRadius: +(Math.max(...radii) * scale).toFixed(3),
    length: +(bodyBox.max.z - bodyBox.min.z).toFixed(3),
    width: +(bodyBox.max.x - bodyBox.min.x).toFixed(3),
    height: +bodyBox.max.y.toFixed(3),
    flipped: flip,
    parts: { body: bodyParts.length, wheel: wheelParts.length, caliper: caliperParts.length },
  };
  const { GLTFExporter } = await import('three/examples/jsm/exporters/GLTFExporter.js');
  const glb = await new Promise<ArrayBuffer>((resolve, reject) =>
    new GLTFExporter().parse(root, (r) => resolve(r as ArrayBuffer), reject, { binary: true }),
  );
  return { glb, stats };
}

/** Dev-only: renders a model from the side, top and front (for picking `rotation`). */
export async function previewCarModel(url: string, rotation?: [number, number, number]) {
  const gltf = await new GLTFLoader().loadAsync(url);
  const scene = new THREE.Scene();
  scene.background = new THREE.Color('#8a94a6');
  const holder = new THREE.Group();
  holder.add(gltf.scene);
  if (rotation) holder.rotation.set(rotation[0], rotation[1], rotation[2]);
  scene.add(holder, new THREE.HemisphereLight('#ffffff', '#445566', 2.5));
  const sun = new THREE.DirectionalLight('#ffffff', 2);
  sun.position.set(3, 5, 4);
  scene.add(sun);
  holder.updateMatrixWorld(true);
  const box = new THREE.Box3().setFromObject(holder);
  const c = box.getCenter(new THREE.Vector3());
  const r = box.getSize(new THREE.Vector3()).length() / 2;
  const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
  renderer.setSize(480, 320);
  const cam = new THREE.PerspectiveCamera(35, 1.5, r / 50, r * 20);
  const shots: Record<string, string> = {};
  for (const [name, dir] of [['side_+x', [1, 0, 0]], ['top_+y', [0, 1, 0.001]], ['front_+z', [0, 0, 1]]] as const) {
    cam.position.copy(c).addScaledVector(new THREE.Vector3(...dir), r * 3);
    cam.lookAt(c);
    renderer.render(scene, cam);
    shots[name] = renderer.domElement.toDataURL('image/png');
  }
  renderer.dispose();
  return { shots, box: { min: box.min.toArray(), max: box.max.toArray() } };
}
