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
}

interface Part {
  name: string;
  geo: THREE.BufferGeometry;
  material: THREE.Material;
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
function subGeometry(geo: THREE.BufferGeometry, start: number, count: number) {
  const flat = geo.index ? geo.toNonIndexed() : geo;
  const out = new THREE.BufferGeometry();
  for (const [name, attr] of Object.entries(flat.attributes)) {
    const a = attr as THREE.BufferAttribute;
    out.setAttribute(name, new THREE.BufferAttribute(a.array.slice(start * a.itemSize, (start + count) * a.itemSize), a.itemSize, a.normalized));
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
  return buckets.map((tris) => {
    if (!tris.length) return null;
    const out = new THREE.BufferGeometry();
    for (const [name, attr] of Object.entries(flat.attributes)) {
      const a = attr as THREE.BufferAttribute;
      const arr = new (a.array.constructor as Float32ArrayConstructor)(tris.length * 3 * a.itemSize);
      tris.forEach((t, i) => arr.set(a.array.subarray(t * 3 * a.itemSize, (t + 1) * 3 * a.itemSize), i * 3 * a.itemSize));
      out.setAttribute(name, new THREE.BufferAttribute(arr, a.itemSize, a.normalized));
    }
    return out;
  });
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
  const wheelParts = parts.filter((p) => wheelRe!.test(label(p)));
  const caliperParts = parts.filter((p) => !wheelRe!.test(label(p)) && caliperRe?.test(label(p)));
  const bodyParts = parts.filter((p) => !wheelParts.includes(p) && !caliperParts.includes(p));
  if (!wheelParts.length) throw new Error('no wheel parts matched');

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
        corner[q].geos.push({ geo: g, material: p.material, spin });
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
    return p.material;
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
    const geos = body.children.filter((m) => rx.test(`${m.name} ${(m as THREE.Mesh).material && ((m as THREE.Mesh).material as THREE.Material).name}`) || ((m as THREE.Mesh).material as THREE.Material).name === prefix).map((m) => (m as THREE.Mesh).geometry);
    if (!geos.length) return;
    const box = boxOf(geos);
    const c = box.getCenter(new THREE.Vector3());
    const half = (box.max.x - box.min.x) / 4;
    anchor(`anchor_${prefix}_0`, new THREE.Vector3(c.x + half, c.y, c.z));
    anchor(`anchor_${prefix}_1`, new THREE.Vector3(c.x - half, c.y, c.z));
  };
  lamps(headRe, 'headlight');
  lamps(tailRe, 'taillight');
  const bodyBox = boxOf(body.children.map((m) => (m as THREE.Mesh).geometry));
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
