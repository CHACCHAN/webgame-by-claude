import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { MeshoptDecoder } from 'three/examples/jsm/libs/meshopt_decoder.module.js';

/**
 * The roadside's modules, our own: built by Blender scripts (tools/blender/roadside/<id>.py → `node
 * tools/blender-models.cjs roadside` → public/models/roadside). A module is written in the road's frame (z = metres
 * along the road, x = outwards from the line it stands on, y = up) and render/roadside.ts lays it along the road
 * vertex by vertex, so a guardrail span bends with a hairpin. The models' materials only name what a part is made of
 * (`galvanised`, `reflector`, …): the game's own materials are put in their place.
 */
export type RoadsideId = 'guardrail' | 'guardrail_end' | 'delineator' | 'gutter_grate' | 'rockfall_fence';

const IDS: RoadsideId[] = ['guardrail', 'guardrail_end', 'delineator', 'gutter_grate', 'rockfall_fence'];

/** a module's triangles per material name (float position / normal / uv, indexed) */
export type RoadsidePart = Map<string, THREE.BufferGeometry>;

const parts = new Map<RoadsideId, RoadsidePart>();

/** The loaded module, or null (the scenery then keeps its plain shapes). */
export function roadsidePart(id: RoadsideId) {
  return parts.get(id) ?? null;
}

export function roadsideLoaded() {
  return IDS.every((id) => parts.has(id));
}

/** Float copies of position / normal / uv (the optimiser quantises them) in the module's frame. */
function plain(mesh: THREE.Mesh) {
  const geo = mesh.geometry;
  const out = new THREE.BufferGeometry();
  for (const [name, size] of [['position', 3], ['normal', 3], ['uv', 2]] as const) {
    const a = geo.getAttribute(name);
    const arr = new Float32Array(geo.getAttribute('position').count * size);
    if (a) for (let i = 0; i < a.count; i++) for (let k = 0; k < size; k++) arr[i * size + k] = a.getComponent(i, k);
    out.setAttribute(name, new THREE.BufferAttribute(arr, size));
  }
  out.setIndex(geo.index ? Array.from(geo.index.array) : [...Array(geo.getAttribute('position').count).keys()]);
  out.applyMatrix4(mesh.matrixWorld);
  return out;
}

export async function loadRoadsideModels() {
  const loader = new GLTFLoader();
  loader.setMeshoptDecoder(MeshoptDecoder);
  await Promise.all(
    IDS.filter((id) => !parts.has(id)).map(async (id) => {
      try {
        const gltf = await loader.loadAsync(`/models/roadside/${id}.glb`);
        gltf.scene.updateMatrixWorld(true);
        const part: RoadsidePart = new Map();
        gltf.scene.traverse((o) => {
          const m = o as THREE.Mesh;
          if (!m.isMesh) return;
          const name = (m.material as THREE.Material).name;
          // (the optimiser joins a model's meshes per material: one mesh each)
          if (!part.has(name)) part.set(name, plain(m));
        });
        parts.set(id, part);
      } catch (err) {
        console.warn(`roadside model ${id} not loaded, the roadside keeps its plain shapes`, err);
      }
    }),
  );
}
