import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { MeshoptDecoder } from 'three/examples/jsm/libs/meshopt_decoder.module.js';

/**
 * Scenery props (third-party models converted by tools/import-props.cjs, see docs/ASSETS.md):
 * loaded once from /models/props/<id>.glb and placed as InstancedMesh by TrackScenery. A missing or
 * broken file leaves the prop unregistered and the scenery falls back to its procedural version.
 *
 * Prop space: metres, ground at y = 0, origin at the foot, front towards +Z (a lamp's arm along −X).
 */
export const PROP_IDS = [
  'street_light', 'led_light', 'wind_turbine', 'curve_mirror', 'vending', 'torii', 'lantern', 'bus_stop', 'cone',
  // plant sets (Poly Haven): one variant per plant, see render/Vegetation.ts
  'shrub_02', 'shrub_04', 'fern_02', 'grass_medium_01', 'weed_plant_02', 'nettle_plant',
] as const;
export type PropId = (typeof PROP_IDS)[number];

/** Attribution of the scenery models (Sketchfab CC BY 4.0, Poly Haven CC0): shown in the settings screen, see docs/ASSETS.md. */
export const PROP_CREDITS: { use: string; title: string; author: string; url: string; license: string }[] = [
  { use: '街灯', title: 'Street Light', author: 'KloWorks', url: 'https://sketchfab.com/3d-models/street-light-2d44b333f56c4faaab1bd2007868cc37', license: 'CC BY 4.0' },
  { use: '街灯（LED）', title: 'Various Low-Poly Street Lights', author: 'KMB3D', url: 'https://sketchfab.com/3d-models/various-low-poly-street-lights-1173b0c4d9b0400bbeaafbee0e94ca59', license: 'CC BY 4.0' },
  { use: '風力発電機', title: 'Animated Wind Turbine', author: 'Glowbox 3D', url: 'https://sketchfab.com/3d-models/animated-wind-turbine-e0678e6615a74ed29c1376a591262159', license: 'CC BY 4.0' },
  { use: 'カーブミラー', title: 'Blind spot traffic mirror', author: 'guru2fifa', url: 'https://sketchfab.com/3d-models/blind-spot-traffic-mirror-6b7baf381f6c45ef8d92411e0467492b', license: 'CC BY 4.0' },
  { use: '自販機', title: 'Japan Vending Machine Soft Drink', author: 'ditovirnantio', url: 'https://sketchfab.com/3d-models/japan-vending-machine-soft-drink-431394ee886141349e187fb8dcc2307a', license: 'CC BY 4.0' },
  { use: '鳥居', title: 'Japanese Torii Gate', author: 'Sahir Virmani', url: 'https://sketchfab.com/3d-models/japanese-torii-gate-2027a248de1b4b70985ff97e708fb50d', license: 'CC BY 4.0' },
  { use: '石灯籠', title: 'Stone Lantern', author: 'Jamie McFarlane', url: 'https://sketchfab.com/3d-models/stone-lantern-4e674d91b33a450781aebd9c490b0f05', license: 'CC BY 4.0' },
  { use: 'バス停', title: 'Kyoto Cityscene: Bus Stop', author: 'Mikail Karaca', url: 'https://sketchfab.com/3d-models/kyoto-cityscene-bus-stop-5eb07fc3b28f474dbf15b1bbac814c82', license: 'CC BY 4.0' },
  { use: 'コーン', title: 'Traffic Cone', author: 'Jamie McFarlane', url: 'https://sketchfab.com/3d-models/traffic-cone-66b282e65d3b4da8a883ae8579bfb33c', license: 'CC BY 4.0' },
  // plants: CC0 (no attribution required, credited anyway)
  { use: '茂み', title: 'Shrub 02', author: 'Poly Haven', url: 'https://polyhaven.com/a/shrub_02', license: 'CC0' },
  { use: '茂み', title: 'Shrub 04', author: 'Poly Haven', url: 'https://polyhaven.com/a/shrub_04', license: 'CC0' },
  { use: 'シダ', title: 'Fern 02', author: 'Poly Haven', url: 'https://polyhaven.com/a/fern_02', license: 'CC0' },
  { use: '草', title: 'Grass Medium 01', author: 'Poly Haven', url: 'https://polyhaven.com/a/grass_medium_01', license: 'CC0' },
  { use: '雑草', title: 'Weed Plant 02', author: 'Poly Haven', url: 'https://polyhaven.com/a/weed_plant_02', license: 'CC0' },
  { use: '雑草', title: 'Nettle Plant', author: 'Poly Haven', url: 'https://polyhaven.com/a/nettle_plant', license: 'CC0' },
];

export interface PropPart {
  /** geometry in prop space (rotor parts: rotor space), shared by every course */
  geometry: THREE.BufferGeometry;
  material: THREE.MeshStandardMaterial;
  /** game role of the material ("lamp": a lens lit at night, "glow": a self-lit display) */
  role?: string;
}

export interface PropTemplate {
  id: PropId;
  parts: PropPart[];
  /** spinning parts: rotor space → prop space, spin about the rotor's local +Z */
  rotor?: { parts: PropPart[]; matrix: THREE.Matrix4 };
  anchors: Record<string, THREE.Vector3>;
  min: THREE.Vector3;
  max: THREE.Vector3;
  /** plant sets: each variant stands at the origin (its parts are not in `parts`) */
  variants?: { name: string; parts: PropPart[] }[];
}

const templates = new Map<PropId, PropTemplate>();

export function getProp(id: PropId): PropTemplate | null {
  return templates.get(id) ?? null;
}

/** Positions as plain floats (meshopt-quantised attributes cannot take an arbitrary transform). */
function bake(geo: THREE.BufferGeometry, m: THREE.Matrix4) {
  const out = new THREE.BufferGeometry();
  for (const [name, attr] of Object.entries(geo.attributes)) {
    const a = attr as THREE.BufferAttribute;
    const f = new Float32Array(a.count * a.itemSize);
    for (let i = 0; i < a.count; i++) for (let c = 0; c < a.itemSize; c++) f[i * a.itemSize + c] = a.getComponent(i, c);
    out.setAttribute(name, new THREE.BufferAttribute(f, a.itemSize));
  }
  if (geo.index) out.setIndex(geo.index.clone());
  out.applyMatrix4(m);
  out.computeBoundingSphere();
  out.computeBoundingBox();
  // kept across course switches (Game.disposeWorld skips shared assets)
  out.userData.sharedAsset = true;
  return out;
}

export function registerPropTemplate(id: PropId, scene: THREE.Object3D) {
  let root: THREE.Object3D | null = null;
  scene.traverse((o) => {
    if (!root && o.userData.prop) root = o;
  });
  if (!root) throw new Error(`prop ${id}: no metadata`);
  const r = root as THREE.Object3D;
  r.updateMatrixWorld(true);
  const toRoot = r.matrixWorld.clone().invert();
  const rotorNode = r.getObjectByName('rotor') ?? null;
  const toRotor = rotorNode ? rotorNode.matrixWorld.clone().invert() : null;
  const parts: PropPart[] = [], rotorParts: PropPart[] = [];
  const variants = new Map<string, PropPart[]>();
  r.traverse((o) => {
    const mesh = o as THREE.Mesh;
    if (!mesh.isMesh) return;
    let inRotor = false, variant: string | null = null;
    for (let p: THREE.Object3D | null = mesh; p && p !== r; p = p.parent) {
      if (p === rotorNode) inRotor = true;
      if (p.name.startsWith('variant_')) variant = p.name.slice(8);
    }
    const material = mesh.material as THREE.MeshStandardMaterial;
    for (const v of Object.values(material)) if (v instanceof THREE.Texture) v.userData.sharedAsset = true;
    const role = ['lamp', 'glow'].includes(material.name) ? material.name : undefined;
    const geometry = bake(mesh.geometry, new THREE.Matrix4().multiplyMatrices(inRotor ? toRotor! : toRoot, mesh.matrixWorld));
    if (inRotor) {
      // culling bounds that hold at every angle: a sphere round the hub
      const pos = geometry.getAttribute('position');
      let r2 = 0;
      for (let i = 0; i < pos.count; i++) r2 = Math.max(r2, pos.getX(i) ** 2 + pos.getY(i) ** 2 + pos.getZ(i) ** 2);
      geometry.boundingSphere = new THREE.Sphere(new THREE.Vector3(), Math.sqrt(r2));
    }
    if (variant) variants.set(variant, [...(variants.get(variant) ?? []), { geometry, material, role }]);
    else (inRotor ? rotorParts : parts).push({ geometry, material, role });
  });
  const meta = r.userData.prop as { anchors: Record<string, number[]>; min: number[]; max: number[]; rotor?: { position: number[]; quaternion: number[] } };
  const anchors: Record<string, THREE.Vector3> = {};
  for (const [k, v] of Object.entries(meta.anchors ?? {})) anchors[k] = new THREE.Vector3().fromArray(v);
  const t: PropTemplate = { id, parts, anchors, min: new THREE.Vector3().fromArray(meta.min), max: new THREE.Vector3().fromArray(meta.max) };
  if (variants.size) t.variants = [...variants].sort(([a], [b]) => a.localeCompare(b)).map(([name, list]) => ({ name, parts: list }));
  if (rotorNode && rotorParts.length) {
    t.rotor = { parts: rotorParts, matrix: new THREE.Matrix4().multiplyMatrices(toRoot, rotorNode.matrixWorld) };
  }
  templates.set(id, t);
  return t;
}

export async function loadPropTemplates(ids: readonly PropId[] = PROP_IDS) {
  const loader = new GLTFLoader();
  loader.setMeshoptDecoder(MeshoptDecoder);
  const loaded: PropId[] = [];
  await Promise.all(
    ids.map(async (id) => {
      if (templates.has(id)) return;
      const url = `/models/props/${id}.glb`;
      try {
        const head = await fetch(url, { method: 'HEAD' });
        const type = head.headers.get('content-type') ?? '';
        if (!head.ok || type.includes('text/html')) return;
        const gltf = await loader.loadAsync(url);
        registerPropTemplate(id, gltf.scene);
        loaded.push(id);
      } catch (e) {
        console.warn(`prop model ${id} unavailable, using procedural fallback`, e);
      }
    }),
  );
  return loaded;
}

export interface PropInstances {
  group: THREE.Group;
  /** per-build material copies, by role ("" for plain parts) */
  materials: THREE.MeshStandardMaterial[];
  /** rotor meshes (one per rotor part); call spin() each frame */
  spin?: (angles: ArrayLike<number>) => void;
}

/**
 * One InstancedMesh per part for the given placements. Materials are copied per build (the time of day
 * changes their emissive strength) and may be adjusted with `material` before use.
 */
export function instanceProp(
  t: PropTemplate,
  placements: THREE.Matrix4[],
  opts: { castShadow?: boolean; receiveShadow?: boolean; material?: (m: THREE.MeshStandardMaterial, part: PropPart) => THREE.MeshStandardMaterial } = {},
): PropInstances {
  const group = new THREE.Group();
  group.name = `prop-${t.id}`;
  const materials: THREE.MeshStandardMaterial[] = [];
  if (!placements.length) return { group, materials };
  const copies = new Map<THREE.Material, THREE.MeshStandardMaterial>();
  const materialOf = (part: PropPart) => {
    if (!copies.has(part.material)) {
      const m = part.material.clone();
      const out = opts.material ? opts.material(m, part) : m;
      copies.set(part.material, out);
      materials.push(out);
    }
    return copies.get(part.material)!;
  };
  const make = (part: PropPart) => {
    const mesh = new THREE.InstancedMesh(part.geometry, materialOf(part), placements.length);
    mesh.castShadow = !!opts.castShadow;
    mesh.receiveShadow = opts.receiveShadow ?? true;
    group.add(mesh);
    return mesh;
  };
  for (const part of t.parts) {
    const mesh = make(part);
    placements.forEach((m, i) => mesh.setMatrixAt(i, m));
    mesh.computeBoundingSphere();
  }
  let spin: PropInstances['spin'];
  if (t.rotor) {
    const rotor = t.rotor;
    const meshes = rotor.parts.map(make);
    const base = placements.map((m) => new THREE.Matrix4().multiplyMatrices(m, rotor.matrix));
    const turn = new THREE.Matrix4(), out = new THREE.Matrix4();
    spin = (angles) => {
      for (let i = 0; i < base.length; i++) {
        out.multiplyMatrices(base[i], turn.makeRotationZ(angles[i]));
        for (const mesh of meshes) mesh.setMatrixAt(i, out);
      }
      for (const mesh of meshes) mesh.instanceMatrix.needsUpdate = true;
    };
    spin(new Float32Array(base.length));
    for (const mesh of meshes) mesh.computeBoundingSphere();
  }
  return { group, materials, spin };
}

/** Placement matrix: foot at `at`, front (+Z) turned by `yaw` about +Y. */
export function placeAt(at: THREE.Vector3, yaw: number, scale = 1) {
  return new THREE.Matrix4().compose(at, new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), yaw), new THREE.Vector3(scale, scale, scale));
}
