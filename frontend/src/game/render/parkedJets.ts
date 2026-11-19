import * as THREE from 'three';

/**
 * The aircraft parked on Edwards' apron, from the fighters' own models (scenery: seen from 30 m to a few hundred).
 * `tools/parked-jets.ts` bakes the types' models (public/models/jets/<id>.glb) into one small file, `PARKED_FILE`:
 * per type the airframe, gear and nozzles simplified to 2 cm on a shared atlas (each type's at a quarter of its size:
 * base colour; occlusion / roughness / metalness), and the canopy's glass with the lamps' lenses (dark, colour per
 * vertex), as the autobahn's traffic flattens the cars (`trafficModels.ts`). Here every parked aircraft of every
 * type goes into two meshes, their places baked into the vertices (they never move): two draw calls, two shaders,
 * one of them throws a shadow. No lamps, no flames, no normal map: from the course these are below a pixel.
 *
 * Fetched at the start of the course's load (`Game.survey`, Edwards only) and waited for in `Game.buildWorld`, so the
 * scenery is built and its shaders compiled behind the loading screen; without the file (or a type in it) the
 * aircraft are the procedural stand-ins (`JetModel.parkedJets`), as before.
 */

/** the types that stand on the apron: the order is each one's slot in the shared atlas */
export const PARKED_TYPES = ['f15c', 'f15j', 'su47'] as const;
/** the baked file, in public/models/jets/ */
export const PARKED_FILE = 'parked.glb';

interface Part {
  pos: Float32Array;
  normal: Float32Array;
  color: Float32Array;
  /** atlas coordinates (the airframe only) */
  uv: Float32Array | null;
  index: Uint32Array;
}
interface Kit {
  types: Map<string, { airframe: Part | null; glass: Part | null }>;
  base: TexImageSource | null;
  orm: TexImageSource | null;
}

let kit: Kit | null = null;
let pending: Promise<void> | null = null;

/** how the last load went (ms from its start to the file's arrival, main-thread ms of reading it out): for probes */
export const parkedStats = { fetchMs: 0, readMs: 0, types: 0 };

/** Fetch the baked aircraft (once). A failure leaves the stand-ins. */
export function loadParkedJets(): Promise<void> {
  return (pending ??= load().catch((e) => console.warn('parked aircraft: the stand-ins', e)));
}

/**
 * `loadParkedJets`, waited for at most `ms`: on a slow link the course does not wait for scenery (the file goes on
 * loading, and the next build of the course has it).
 */
export function parkedJetsWithin(ms: number): Promise<void> {
  return Promise.race([loadParkedJets(), new Promise<void>((r) => setTimeout(r, ms))]);
}

/** the types that can be drawn from their models (after `loadParkedJets`) */
export const parkedModelReady = (id: string) => !!kit?.types.has(id);

async function load() {
  if (typeof document === 'undefined') return;
  const t0 = performance.now();
  const { GLTFLoader } = await import('three/examples/jsm/loaders/GLTFLoader.js');
  const { MeshoptDecoder } = await import('three/examples/jsm/libs/meshopt_decoder.module.js');
  const loader = new GLTFLoader();
  loader.setMeshoptDecoder(MeshoptDecoder);
  const gltf = await loader.loadAsync(`/models/jets/${PARKED_FILE}`);
  parkedStats.fetchMs = Math.round(performance.now() - t0);
  const t1 = performance.now();
  gltf.scene.updateMatrixWorld(true);
  const types: Kit['types'] = new Map();
  let base: TexImageSource | null = null, orm: TexImageSource | null = null;
  for (const id of PARKED_TYPES) {
    const node = gltf.scene.getObjectByName(id);
    if (!node) continue;
    const parts: { airframe: Part | null; glass: Part | null } = { airframe: null, glass: null };
    node.traverse((o) => {
      const mesh = o as THREE.Mesh;
      if (!mesh.isMesh) return;
      const mat = mesh.material as THREE.MeshStandardMaterial;
      if (mat.name === 'parked-airframe') {
        parts.airframe = read(mesh, true);
        base ??= (mat.map?.image as TexImageSource | undefined) ?? null;
        orm ??= (mat.roughnessMap?.image as TexImageSource | undefined) ?? null;
      } else if (mat.name === 'parked-glass') parts.glass = read(mesh, false);
    });
    if (parts.airframe) types.set(id, parts);
  }
  parkedStats.readMs = Math.round(performance.now() - t1);
  parkedStats.types = types.size;
  if (!base) return;
  kit = { types, base, orm };
}

/** a mesh's geometry in its type's frame (quantised attributes read out, the node's transform applied) */
function read(mesh: THREE.Mesh, uv: boolean): Part {
  const g = mesh.geometry;
  const P = g.getAttribute('position'), N = g.getAttribute('normal'), C = g.getAttribute('color'), U = g.getAttribute('uv');
  const n = P.count;
  const out: Part = { pos: new Float32Array(n * 3), normal: new Float32Array(n * 3), color: new Float32Array(n * 3), uv: uv && U ? new Float32Array(n * 2) : null, index: new Uint32Array(g.index ? g.index.count : n) };
  const nm = new THREE.Matrix3().getNormalMatrix(mesh.matrixWorld), v = new THREE.Vector3();
  for (let i = 0; i < n; i++) {
    v.fromBufferAttribute(P, i).applyMatrix4(mesh.matrixWorld).toArray(out.pos, i * 3);
    v.fromBufferAttribute(N, i).applyMatrix3(nm).normalize().toArray(out.normal, i * 3);
    if (C) for (let c = 0; c < 3; c++) out.color[i * 3 + c] = C.getComponent(i, c);
    else out.color.fill(1, i * 3, i * 3 + 3);
    if (out.uv && U) {
      out.uv[i * 2] = U.getX(i);
      out.uv[i * 2 + 1] = U.getY(i);
    }
  }
  if (g.index) out.index.set(g.index.array);
  else for (let i = 0; i < n; i++) out.index[i] = i;
  return out;
}

export interface ParkedSpot {
  position: THREE.Vector3;
  heading: number;
  id: string;
}

/**
 * The parked aircraft of these spots that have a model, as two meshes (airframe, glass); null when none has.
 * Every call makes its own geometry, textures and materials (a course that is freed frees them).
 */
export function parkedFromModels(spots: ParkedSpot[]): THREE.Group | null {
  if (!kit) return null;
  const list = spots.filter((s) => kit!.types.has(s.id));
  if (!list.length) return null;
  const group = new THREE.Group();
  group.name = 'parked-aircraft';
  const tex = (img: TexImageSource | null, srgb: boolean) => {
    if (!img) return null;
    const t = new THREE.Texture(img as THREE.Texture['image']);
    // (glTF's way up: the picture's first row is v = 0)
    t.flipY = false;
    t.colorSpace = srgb ? THREE.SRGBColorSpace : THREE.NoColorSpace;
    t.wrapS = t.wrapT = THREE.ClampToEdgeWrapping;
    t.anisotropy = 4;
    t.needsUpdate = true;
    return t;
  };
  const baseTex = tex(kit.base, true), ormTex = tex(kit.orm, false);
  const airMat = new THREE.MeshStandardMaterial({ map: baseTex, aoMap: ormTex, roughnessMap: ormTex, metalnessMap: ormTex, roughness: 1, metalness: ormTex ? 1 : 0.2, vertexColors: true });
  airMat.name = 'parked-airframe';
  const glassMat = new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.14, metalness: 0 });
  glassMat.name = 'parked-glass';
  for (const [part, mat] of [['airframe', airMat], ['glass', glassMat]] as const) {
    const parts = list.map((s) => ({ s, p: kit!.types.get(s.id)![part] })).filter((x): x is { s: ParkedSpot; p: Part } => !!x.p);
    if (!parts.length) continue;
    const verts = parts.reduce((n, x) => n + x.p.pos.length / 3, 0), tris = parts.reduce((n, x) => n + x.p.index.length, 0);
    const pos = new Float32Array(verts * 3), normal = new Float32Array(verts * 3), color = new Float32Array(verts * 3);
    const uv = part === 'airframe' ? new Float32Array(verts * 2) : null;
    const index = new Uint32Array(tris);
    let v = 0, t = 0;
    for (const { s, p } of parts) {
      const c = Math.cos(s.heading), sn = Math.sin(s.heading);
      const n = p.pos.length / 3;
      for (let i = 0; i < n; i++) {
        const x = p.pos[i * 3], z = p.pos[i * 3 + 2], nx = p.normal[i * 3], nz = p.normal[i * 3 + 2];
        // (a turn about +Y by the heading, as `rotateY`)
        pos[(v + i) * 3] = s.position.x + c * x + sn * z;
        pos[(v + i) * 3 + 1] = s.position.y + p.pos[i * 3 + 1];
        pos[(v + i) * 3 + 2] = s.position.z - sn * x + c * z;
        normal[(v + i) * 3] = c * nx + sn * nz;
        normal[(v + i) * 3 + 1] = p.normal[i * 3 + 1];
        normal[(v + i) * 3 + 2] = -sn * nx + c * nz;
      }
      color.set(p.color, v * 3);
      if (uv && p.uv) uv.set(p.uv, v * 2);
      for (let k = 0; k < p.index.length; k++) index[t + k] = p.index[k] + v;
      v += n;
      t += p.index.length;
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    geo.setAttribute('normal', new THREE.BufferAttribute(normal, 3));
    geo.setAttribute('color', new THREE.BufferAttribute(color, 3));
    if (uv) geo.setAttribute('uv', new THREE.BufferAttribute(uv, 2));
    geo.setIndex(new THREE.BufferAttribute(index, 1));
    geo.computeBoundingSphere();
    const mesh = new THREE.Mesh(geo, mat);
    mesh.name = `parked-${part}`;
    group.add(mesh);
  }
  return group;
}
