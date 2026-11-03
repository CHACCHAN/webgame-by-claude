import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { MeshoptDecoder } from 'three/examples/jsm/libs/meshopt_decoder.module.js';
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js';

/**
 * Scenery models, our own: built by Blender scripts (tools/blender/props/<file>.py → `node tools/blender-models.cjs
 * props` → public/models/props). They are built to one convention, which every model is also brought to when it
 * loads: metres, base on y = 0 at the origin, its front (mirror glass, vending machine front, the way through a torii,
 * the open side of the bus shelter) towards +Z, a street light's arm along −X. Scenery falls back to its procedural
 * shapes for a model that did not load.
 */
export type PropId = 'streetLight' | 'windTurbine' | 'curveMirror' | 'vending' | 'torii' | 'stoneLantern' | 'busStop' | 'cone';

interface PropDef {
  file: string;
  /** height (m) the whole model is scaled to */
  height: number;
  /** turn about +Y (rad) after scaling, onto the convention above */
  yaw?: number;
  /** source x, z that becomes the origin (default: centre of the bounding box) */
  origin?: [number, number];
  /** node whose meshes turn on their own (a turbine's rotor): kept apart, pivoting at that node */
  moving?: string;
  /**
   * Box in prop coordinates (x0, x1, z0, z1; metres, after scaling and yaw) whose triangles are left out, e.g. a
   * part that came with a model. The scale still comes from the whole model.
   */
  drop?: [number, number, number, number];
}

// heights as built (the street light is stretched 0.5 % to the lamp height the lighting is placed for)
const PROPS: Record<PropId, PropDef> = {
  streetLight: { file: 'street_light.glb', height: 7.6, origin: [0, 0] },
  windTurbine: { file: 'wind_turbine.glb', height: 86, origin: [0, 0], moving: 'Blades' },
  curveMirror: { file: 'curve_mirror.glb', height: 3.57, origin: [0, 0] },
  vending: { file: 'vending_machine.glb', height: 1.83 },
  torii: { file: 'torii.glb', height: 4.6 },
  stoneLantern: { file: 'stone_lantern.glb', height: 1.6 },
  busStop: { file: 'bus_stop.glb', height: 2.59, origin: [0, 0] },
  cone: { file: 'traffic_cone.glb', height: 0.7 },
};

export interface PropPiece {
  geometry: THREE.BufferGeometry;
  material: THREE.MeshStandardMaterial;
  /** part of the moving node (geometry relative to `PropModel.pivot`) */
  moving: boolean;
}

export interface PropModel {
  /** merged per material: one draw call each */
  pieces: PropPiece[];
  /** where the moving part turns (prop coordinates) */
  pivot: THREE.Vector3 | null;
  size: THREE.Vector3;
}

const models = new Map<PropId, PropModel>();

/** The loaded model, or null (procedural fallback). */
export function prop(id: PropId) {
  return models.get(id) ?? null;
}

export async function loadProps() {
  const loader = new GLTFLoader();
  loader.setMeshoptDecoder(MeshoptDecoder);
  await Promise.all(
    (Object.entries(PROPS) as [PropId, PropDef][]).map(async ([id, def]) => {
      if (models.has(id)) return;
      try {
        const gltf = await loader.loadAsync(`/models/props/${def.file}`);
        models.set(id, normalise(gltf.scene, def));
      } catch (err) {
        console.warn(`scenery model ${def.file} not loaded, using the procedural shape`, err);
      }
    }),
  );
}

/** Float copies of position / normal / uv (the optimiser quantises them), the rest dropped. */
function plain(geo: THREE.BufferGeometry) {
  const out = new THREE.BufferGeometry();
  for (const [name, size] of [['position', 3], ['normal', 3], ['uv', 2]] as const) {
    const a = geo.getAttribute(name);
    if (!a) continue;
    const arr = new Float32Array(a.count * size);
    for (let i = 0; i < a.count; i++) for (let k = 0; k < size; k++) arr[i * size + k] = a.getComponent(i, k);
    out.setAttribute(name, new THREE.BufferAttribute(arr, size));
  }
  if (geo.index) out.setIndex(Array.from(geo.index.array));
  if (!out.getAttribute('normal')) out.computeVertexNormals();
  return out;
}

/** The geometry without the triangles whose centre lies in the box (x0, x1, z0, z1), or null if none is left. */
function withoutBox(geo: THREE.BufferGeometry, [x0, x1, z0, z1]: [number, number, number, number]) {
  const pos = geo.getAttribute('position');
  const index = geo.index ? Array.from(geo.index.array) : [...Array(pos.count).keys()];
  const keep: number[] = [];
  for (let t = 0; t + 2 < index.length; t += 3) {
    const [a, b, c] = [index[t], index[t + 1], index[t + 2]];
    const x = (pos.getX(a) + pos.getX(b) + pos.getX(c)) / 3, z = (pos.getZ(a) + pos.getZ(b) + pos.getZ(c)) / 3;
    if (x >= x0 && x <= x1 && z >= z0 && z <= z1) continue;
    keep.push(a, b, c);
  }
  if (!keep.length) return null;
  geo.setIndex(keep);
  return geo;
}

function normalise(scene: THREE.Object3D, def: PropDef): PropModel {
  scene.updateMatrixWorld(true);
  const box = new THREE.Box3().setFromObject(scene);
  const s = def.height / (box.max.y - box.min.y);
  const [ox, oz] = def.origin ?? [(box.min.x + box.max.x) / 2, (box.min.z + box.max.z) / 2];
  const toProp = new THREE.Matrix4()
    .makeRotationY(def.yaw ?? 0)
    .multiply(new THREE.Matrix4().makeScale(s, s, s))
    .multiply(new THREE.Matrix4().makeTranslation(-ox, -box.min.y, -oz));
  const moving = def.moving ? (scene.getObjectByName(def.moving) ?? null) : null;
  const pivot = moving ? new THREE.Vector3().setFromMatrixPosition(moving.matrixWorld).applyMatrix4(toProp) : null;
  const groups = new Map<string, { material: THREE.MeshStandardMaterial; geos: THREE.BufferGeometry[]; moving: boolean }>();
  scene.traverse((o) => {
    const m = o as THREE.Mesh;
    if (!m.isMesh) return;
    let inMoving = false;
    for (let p: THREE.Object3D | null = m; p; p = p.parent) if (p === moving) inMoving = true;
    const full = plain(m.geometry).applyMatrix4(new THREE.Matrix4().multiplyMatrices(toProp, m.matrixWorld));
    const geo = def.drop ? withoutBox(full, def.drop) : full;
    if (!geo) return;
    if (inMoving && pivot) geo.translate(-pivot.x, -pivot.y, -pivot.z);
    const material = m.material as THREE.MeshStandardMaterial;
    const key = `${material.uuid}|${inMoving}`;
    if (!groups.has(key)) groups.set(key, { material, geos: [], moving: inMoving });
    groups.get(key)!.geos.push(geo.index ? geo : geo.setIndex([...Array(geo.getAttribute('position').count).keys()]));
  });
  const pieces = [...groups.values()].map((g) => {
    const uv = g.geos.every((x) => x.getAttribute('uv'));
    if (!uv) for (const x of g.geos) x.deleteAttribute('uv');
    return { geometry: g.geos.length > 1 ? mergeGeometries(g.geos)! : g.geos[0], material: g.material, moving: g.moving };
  });
  return { pieces, pivot, size: box.getSize(new THREE.Vector3()).multiplyScalar(s) };
}

export interface PlacedProps {
  group: THREE.Group;
  /** turns the moving pieces (e.g. rotors) of every instance: angle per instance */
  spin(angle: (k: number) => number): void;
}

/**
 * One InstancedMesh per piece placing the prop at every matrix. `material` may swap a piece's material
 * (e.g. a tinted lamp glass); moving pieces turn about the prop's local Z through the pivot.
 */
export function placeProp(
  model: PropModel,
  matrices: THREE.Matrix4[],
  opts: { castShadow?: boolean; receiveShadow?: boolean; material?: (m: THREE.MeshStandardMaterial) => THREE.Material; name?: string } = {},
): PlacedProps {
  const group = new THREE.Group();
  group.name = opts.name ?? 'prop';
  const moving: THREE.InstancedMesh[] = [];
  for (const piece of model.pieces) {
    const mesh = new THREE.InstancedMesh(piece.geometry, opts.material ? opts.material(piece.material) : piece.material, matrices.length);
    matrices.forEach((m, k) => mesh.setMatrixAt(k, m));
    mesh.castShadow = !!opts.castShadow;
    mesh.receiveShadow = opts.receiveShadow ?? true;
    mesh.computeBoundingSphere();
    group.add(mesh);
    if (piece.moving) moving.push(mesh);
  }
  const turn = new THREE.Matrix4(), at = new THREE.Matrix4(), out = new THREE.Matrix4();
  const pivot = model.pivot ?? new THREE.Vector3();
  return {
    group,
    spin(angle) {
      if (!moving.length) return;
      matrices.forEach((m, k) => {
        out.multiplyMatrices(m, at.makeTranslation(pivot.x, pivot.y, pivot.z)).multiply(turn.makeRotationZ(angle(k)));
        for (const mesh of moving) mesh.setMatrixAt(k, out);
      });
      for (const mesh of moving) mesh.instanceMatrix.needsUpdate = true;
    },
  };
}
