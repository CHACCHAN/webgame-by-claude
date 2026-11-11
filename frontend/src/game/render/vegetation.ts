import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { MeshoptDecoder } from 'three/examples/jsm/libs/meshopt_decoder.module.js';
import { MeshBasicNodeMaterial, MeshSSSNodeMaterial, MeshStandardNodeMaterial } from 'three/webgpu';
import {
  Fn, atan, attribute, cameraViewMatrix, cos, float, floor, fract, lights, max, mix, normalLocal, normalViewGeometry, positionLocal, positionPrevious,
  positionView, renderGroup, screenCoordinate, sin, smoothstep, step, texture, uniform, uv, varying, vec2, vec3, vec4,
} from 'three/tsl';
import { clearing } from './instancing';

/**
 * The vegetation: trees, bushes, undergrowth and rocks from our own Blender models (tools/blender/nature →
 * public/models/nature/<id>.glb, `.lite.glb` for the medium quality), drawn instanced.
 *
 * A species is one texture pair (twig and bough sprites over a band of bark: one material draws the whole tree) and,
 * per shape variant, three meshes (lod0: boughs and twig cards, lod1: bough cards, lod2: a few big cards) plus an
 * impostor (eight views around the tree). `Forest` keeps every tree in chunks and gives each level the chunks in
 * its range; inside a level every tree decides for itself in the shader (distance to the viewer), and where two
 * levels meet they swap through a dither in the cutout mask over some metres: no pop, no alpha blending, and the
 * temporal upscaler sees opaque pixels with true motion vectors. The impostors are one static mesh per species
 * holding every tree; the near ones draw at no size.
 *
 * Draw calls: one per variant and level that has trees in range, one per species for the impostors, and one per
 * variant in the moon's / sun's shadow map only (the lod2 mesh on `SHADOW_LAYER`: the detailed levels throw none).
 *
 * What the forest costs is the pixels, not the triangles (measured on the RX 5700 XT: hiding the 2.4 million
 * triangles of the nearest level changed nothing, the trees behind them were shaded instead): cards over cards,
 * each pixel lit by every light of the scene. So the vegetation is drawn before everything else and from the
 * viewer outwards (`renderOrder` by level, the plants of a level nearest first, the impostors by their distance
 * from the road, where the viewer is), which lets the depth test throw the hidden layers away unshaded; the far
 * levels take no shadows, the impostors only the sun / moon and the sky; and only the plants that stand near the
 * road throw shadows (`Planted.casts`), the trees as a closed hull of their crown with holes from a noise (no
 * texture, one layer): a shadow map full of cutout cards cost 10 ms.
 *
 * And the trees are drawn twice (`ForestOptions.prepass`). A fragment that the cutout throws away still runs its
 * whole shader (WebGPU's `discard` only marks it), so every transparent corner of every card in front of a leaf paid
 * for the scene's twelve lights: 5.6 ms of a 11 ms scene. The first pass draws the cutout with the leaf's colour under
 * the sky's light alone (cheap, and it writes the depth and the motion vectors); the second draws the same triangles
 * lit, without a cutout, where the depth is equal: exactly the pixels that are seen. Where a driver rounds the two
 * shaders' depths differently a pixel keeps the first pass' flat colour: no holes.
 */

/* eslint-disable @typescript-eslint/no-explicit-any */
/** the shader maths is written against three's loosely typed TSL helpers */
type N = any;

/** objects on this layer are drawn into the key light's shadow map only (Game enables it on that shadow camera) */
export const SHADOW_LAYER = 1;

export type VegetationTier = 'legacy' | 'lite' | 'full';

export interface VegetationQuality {
  /** `legacy`: the old procedural cedar and lumps (low quality: nothing to download); `lite`: no lod0, half-size textures */
  tier: VegetationTier;
  /** scale of every level-of-detail distance */
  range: number;
  /** undergrowth (grass, ferns, bamboo grass) per square metre, relative; 0 = none */
  undergrowth: number;
}

// ------------------------------------------------------------------------------------------------ frame state

// These are the same for every plant, so they live in the renderer's shared group: in a uniform of its own each of
// them is copied into every drawn mesh's buffer, and one that changes every frame (the viewer, the wind's clock) made
// the renderer write ~150 buffers a frame for the vegetation alone.
/** where the level of detail is measured from (the camera of the picture, also while a shadow map is drawn) */
const viewer = uniform(new THREE.Vector3()).setGroup(renderGroup);
const windNow = uniform(0).setGroup(renderGroup);
let windDrawn = 0;
/**
 * The wind's clock of the frame drawn before this one, for the motion vectors: taken when a frame is drawn, not when
 * the game steps, so a picture that stands still (the game not stepping) has no motion in it.
 */
const windBefore = (uniform(0).setGroup(renderGroup) as N).onFrameUpdate(() => {
  const t = windDrawn;
  windDrawn = windNow.value;
  return t;
});
const windPower = uniform(0.6).setGroup(renderGroup);
const wet = uniform(0).setGroup(renderGroup);
const WIND = new THREE.Vector2(0.86, 0.51);

/** once a frame: the game's clock (wind) and the camera */
export function vegetationFrame(time: number, camera: THREE.Vector3) {
  windNow.value = time;
  viewer.value.copy(camera);
}

/** rain (0 … 1): wet leaves and bark are darker and glossier, and the wind is up */
/**
 * While the world's shaders are compiled every mesh of every forest stays in the scene, also those that hold no
 * plant at that moment (the renderer compiles what is visible: a species first met halfway down the course would
 * otherwise stop the picture for its shader). `Game` holds before it builds the scenery and lets go after the compile.
 */
let held = false;
export function vegetationHold(on: boolean) {
  held = on;
}

/** the sun / moon and the sky's light (`LightRig`): all that the impostors are lit by (unset: every light of the scene) */
let farLights: THREE.Light[] | null = null;
/** the sky's light as a colour, for the first of the trees' two passes */
const skyColor = new THREE.Color(0.02, 0.02, 0.02);
const skyLight = (uniform(skyColor).setGroup(renderGroup) as N).onFrameUpdate(() => {
  const sky = farLights?.[1];
  // (a surface under a hemisphere light gets its colour × intensity / π at most: a crown's inside about half of that)
  return sky ? skyColor.copy(sky.color).multiplyScalar(sky.intensity * 0.16) : skyColor;
});
/** where the sun / moon stands (the direction towards it), for the shade of a hillside that faces away from it */
const keyAt = new THREE.Vector3(0, 1, 0);
const keyDir = (uniform(keyAt).setGroup(renderGroup) as N).onFrameUpdate(() => {
  const key = farLights?.[0] as THREE.DirectionalLight | undefined;
  return key ? keyAt.copy(key.position).sub(key.target.position).normalize() : keyAt;
});
export function vegetationLights(key: THREE.DirectionalLight, sky: THREE.Light) {
  farLights = [key, sky];
}

export function vegetationWeather(rain: number) {
  wet.value = rain;
  windPower.value = 0.55 + 0.8 * rain;
}

// ------------------------------------------------------------------------------------------------ models

interface ImpostorFrame {
  /** half the card's width and its height (m, at scale 1), how far its foot is under the ground */
  half: number;
  height: number;
  base: number;
  /** the first view's cell in the atlas: u0, v0, width, height (the other seven follow to the right) */
  cell: [number, number, number, number];
}

interface Variant {
  /** lod0 (null in the lite set), lod1, lod2 */
  lods: (THREE.BufferGeometry | null)[];
  impostor: ImpostorFrame | null;
  /** trees: the crown and trunk as one closed shape, for the shadow map */
  hull: THREE.BufferGeometry | null;
}

export interface PlantModel {
  id: string;
  variants: Variant[];
  leaf: THREE.Texture;
  leafN: THREE.Texture | null;
  imp: THREE.Texture | null;
  impN: THREE.Texture | null;
  /** triangles of each variant's levels (for the numbers) */
  tris: number[][];
}

const models = new Map<string, PlantModel>();
let loadedTier: VegetationTier | null = null;

export function plantModel(id: string) {
  return models.get(id) ?? null;
}

/** position / normal / uv as floats (the optimiser quantises them), the model's vertex colour as `veg` */
function plain(mesh: THREE.Mesh) {
  const src = mesh.geometry;
  const out = new THREE.BufferGeometry();
  const pos = src.getAttribute('position');
  const p = new Float32Array(pos.count * 3);
  const v = new THREE.Vector3();
  for (let i = 0; i < pos.count; i++) v.fromBufferAttribute(pos, i).applyMatrix4(mesh.matrixWorld).toArray(p, i * 3);
  out.setAttribute('position', new THREE.BufferAttribute(p, 3));
  const nrm = src.getAttribute('normal');
  if (nrm) {
    const n = new Float32Array(nrm.count * 3);
    for (let i = 0; i < nrm.count; i++) v.fromBufferAttribute(nrm, i).normalize().toArray(n, i * 3);
    out.setAttribute('normal', new THREE.BufferAttribute(n, 3));
  }
  const tex = src.getAttribute('uv');
  if (tex) {
    const t = new Float32Array(tex.count * 2);
    for (let i = 0; i < tex.count; i++) {
      t[i * 2] = tex.getX(i);
      t[i * 2 + 1] = tex.getY(i);
    }
    out.setAttribute('uv', new THREE.BufferAttribute(t, 2));
  }
  const col = src.getAttribute('color');
  const c = new Uint8Array(pos.count * 4).fill(255);
  if (col) for (let i = 0; i < col.count; i++) for (let k = 0; k < col.itemSize; k++) c[i * 4 + k] = Math.round(THREE.MathUtils.clamp(col.getComponent(i, k), 0, 1) * 255);
  out.setAttribute('veg', new THREE.BufferAttribute(c, 4, true));
  if (src.index) out.setIndex(Array.from(src.index.array));
  return out;
}

function parse(id: string, scene: THREE.Object3D): PlantModel {
  scene.updateMatrixWorld(true);
  const model: PlantModel = { id, variants: [], leaf: null as unknown as THREE.Texture, leafN: null, imp: null, impN: null, tris: [] };
  const tune = (t: THREE.Texture | null) => {
    if (t) t.anisotropy = 4;
    return t;
  };
  scene.traverse((o) => {
    const mesh = o as THREE.Mesh;
    if (!mesh.isMesh) return;
    // (the optimiser may hang the mesh under the named node)
    const name = /^v\d+_/.test(mesh.name) ? mesh.name : (mesh.parent?.name ?? '');
    const m = /^v(\d+)_(lod(\d)|imp)/.exec(name);
    if (!m) return;
    const k = +m[1];
    const variant = (model.variants[k] ??= { lods: [null, null, null], impostor: null, hull: null });
    const mat = mesh.material as THREE.MeshStandardMaterial;
    if (m[2] === 'imp') {
      const g = plain(mesh);
      g.computeBoundingBox();
      const b = g.boundingBox!;
      const t = g.getAttribute('uv');
      let u0 = 1, v0 = 1, u1 = 0, v1 = 0;
      for (let i = 0; i < t.count; i++) {
        u0 = Math.min(u0, t.getX(i)), u1 = Math.max(u1, t.getX(i));
        v0 = Math.min(v0, t.getY(i)), v1 = Math.max(v1, t.getY(i));
      }
      variant.impostor = { half: (b.max.x - b.min.x) / 2, height: b.max.y - b.min.y, base: b.min.y, cell: [u0, v0, u1 - u0, v1 - v0] };
      model.imp = tune(mat.map);
      model.impN = tune(mat.normalMap);
    } else {
      const g = plain(mesh);
      variant.lods[+m[3]] = g;
      (model.tris[k] ??= [0, 0, 0])[+m[3]] = (g.index ? g.index.count : g.getAttribute('position').count) / 3;
      model.leaf = tune(mat.map)!;
      model.leafN = tune(mat.normalMap);
    }
  });
  if (!model.variants.length || !model.leaf) throw new Error(`vegetation model ${id}: no variants`);
  // (what has an impostor is a tree)
  for (const v of model.variants) if (v.impostor && (v.lods[1] ?? v.lods[2])) v.hull = hullOf((v.lods[1] ?? v.lods[2])!);
  return model;
}

/**
 * A tree's shadow shape: rings around the trunk's axis, each as wide as the tree reaches at that height in that
 * direction (a little less: the cards' corners are air). `veg.a` says where it is crown (the shadow material cuts
 * its holes there), the other channels as the wind wants them for a stiff part.
 */
function hullOf(src: THREE.BufferGeometry) {
  const BANDS = 9, SECTORS = 7;
  const pos = src.getAttribute('position');
  let top = 0.1;
  for (let i = 0; i < pos.count; i++) top = Math.max(top, pos.getY(i));
  const reach = new Float32Array(BANDS * SECTORS);
  for (let i = 0; i < pos.count; i++) {
    const x = pos.getX(i), y = pos.getY(i), z = pos.getZ(i);
    if (y < 0) continue;
    const b = Math.min(BANDS - 1, Math.floor((y / top) * BANDS));
    const sec = Math.min(SECTORS - 1, Math.floor((Math.atan2(z, x) / (2 * Math.PI) + 0.5) * SECTORS));
    reach[b * SECTORS + sec] = Math.max(reach[b * SECTORS + sec], Math.hypot(x, z));
  }
  const p: number[] = [], veg: number[] = [], index: number[] = [];
  // rings: one on the ground, one in the middle of every band; then the tip
  for (let ring = 0; ring <= BANDS; ring++) {
    const b = Math.max(0, ring - 1);
    let mean = 0;
    for (let k = 0; k < SECTORS; k++) mean += reach[b * SECTORS + k] / SECTORS;
    for (let k = 0; k < SECTORS; k++) {
      // (a direction the tree does not reach into at this height: no deeper a notch than half the ring)
      const r = Math.max(reach[b * SECTORS + k], mean * 0.5, 0.12) * 0.8;
      const a = ((k + 0.5) / SECTORS - 0.5) * 2 * Math.PI;
      p.push(Math.cos(a) * r, ring === 0 ? 0 : ((b + 0.5) / BANDS) * top, Math.sin(a) * r);
      veg.push(255, 0, 0, r > 0.7 ? 255 : 0);
    }
  }
  p.push(0, top, 0);
  veg.push(255, 0, 0, 0);
  for (let ring = 0; ring < BANDS; ring++) {
    for (let k = 0; k < SECTORS; k++) {
      const a = ring * SECTORS + k, b = ring * SECTORS + ((k + 1) % SECTORS);
      index.push(a, a + SECTORS, b, b, a + SECTORS, b + SECTORS);
    }
  }
  for (let k = 0; k < SECTORS; k++) index.push(BANDS * SECTORS + k, (BANDS + 1) * SECTORS, BANDS * SECTORS + ((k + 1) % SECTORS));
  const out = new THREE.BufferGeometry();
  out.setAttribute('position', new THREE.BufferAttribute(new Float32Array(p), 3));
  out.setAttribute('uv', new THREE.BufferAttribute(new Float32Array((p.length / 3) * 2), 2));
  out.setAttribute('veg', new THREE.BufferAttribute(new Uint8Array(veg), 4, true));
  out.setIndex(index);
  return out;
}

/**
 * Loads the species that are not there yet (`lite`: the medium quality's files). A species that fails to load is
 * left out: whoever plants falls back on the others, or on the old procedural trees when none is there.
 */
export async function loadVegetation(ids: string[], tier: VegetationTier) {
  if (tier === 'legacy') return;
  if (loadedTier !== tier) models.clear();
  loadedTier = tier;
  const loader = new GLTFLoader();
  loader.setMeshoptDecoder(MeshoptDecoder);
  await Promise.all(
    ids.map(async (id) => {
      if (models.has(id)) return;
      try {
        const gltf = await loader.loadAsync(`/models/nature/${id}${tier === 'lite' ? '.lite' : ''}.glb`);
        models.set(id, parse(id, gltf.scene));
      } catch (err) {
        console.warn(`vegetation model ${id} not loaded`, err);
      }
    }),
  );
}

// ------------------------------------------------------------------------------------------------ shading

/** screen-door pattern for the levels' cross-fade (the same for every level: where one lets go the next takes over) */
const dither = (): N => {
  const p: N = screenCoordinate;
  return fract(fract(p.x.mul(0.06711056).add(p.y.mul(0.00583715))).mul(52.9829189));
};

/** `n` (tangent space, from a normal map) laid onto the surface normal `surf` (view space), the frame from the uv's screen derivatives */
const perturb = (surf: N, n: N, coord: N): N => {
  const dpx: N = (positionView as N).dFdx(), dpy: N = (positionView as N).dFdy();
  const dux: N = coord.dFdx(), duy: N = coord.dFdy();
  const q1: N = dpy.cross(surf), q0: N = surf.cross(dpx);
  const T: N = q1.mul(dux.x).add(q0.mul(duy.x));
  const B: N = q1.mul(dux.y).add(q0.mul(duy.y));
  const det: N = max(T.dot(T), B.dot(B));
  const k: N = det.greaterThan(1e-20).select(det.inverseSqrt(), 0);
  return T.mul(n.x.mul(k)).add(B.mul(n.y.mul(k))).add(surf.mul(n.z)).normalize();
};

/**
 * The wind's push on a vertex (m, world): the trunk leans with a slow gust (by height², the same for the whole tree),
 * a bough nods (`veg.g`: how far out on its bough the vertex is), a leaf flutters (`veg.b`); `veg.a` is the bough's
 * phase. Gusts travel across the forest (the phase runs with the tree's place).
 */
const windPush = (lp: N, veg: N, foot: N, seed: N, t: N): N => {
  const ph: N = seed.mul(6.283).add(foot.x.mul(0.031)).add(foot.z.mul(0.047));
  const gust: N = sin(t.mul(0.7).add(ph)).mul(0.5).add(sin(t.mul(1.9).add(ph.mul(1.7))).mul(0.25)).add(0.35);
  const h: N = max(lp.y, 0).mul(1 / 16);
  const lean: N = h.mul(h).mul(gust).mul(0.3);
  const nod: N = sin(t.mul(1.6).add(ph).add(veg.a.mul(6.283))).mul(veg.g).mul(0.12);
  const flutter: N = sin(t.mul(6.5).add(veg.a.mul(37)).add(lp.x.mul(2.3)).add(lp.z.mul(1.9)).add(lp.y.mul(2.9))).mul(veg.b).mul(0.024);
  const along: N = lean.add(nod.mul(0.6)).add(flutter.mul(0.5));
  return vec3(along.mul(WIND.x), nod.add(flutter), along.mul(WIND.y)).mul(windPower);
};

/** a level's span of distances: where it starts (x) with the band it fades in over (y), where it ends (z) and that band (w) */
type Span = { value: THREE.Vector4 };
type Reach = { value: number };

interface InstanceNodes {
  foot: N;
  /** how far the instance is from the viewer */
  dist: N;
  /** the local point scaled and turned by the instance */
  place: (v: N) => N;
  turn: (v: N) => N;
  /** 0 inside the garage's clearing … 1 */
  open: N;
  tint: N;
  seed: N;
  /**
   * How much of the sun's / moon's light the plant keeps on its hillside (0.4, an impostor 0.28, on a slope that faces away from a low
   * sun … 1): the shadow map reaches 60 m, and beyond it a forest on the dark side of a mountain shone like the one
   * on the lit side (`far`: from where on it counts; nearer, the shadow map and the lamps do the work).
   */
  shade: (far: boolean) => N;
}

/**
 * The instance's two attributes as shader nodes. instA: x, y, z, yaw; instB: height scale, girth, the ground's
 * slope and the tint in one number (`packLook`), variant + seed.
 */
function instanceNodes(): InstanceNodes {
  const A: N = attribute('instA', 'vec4'), B: N = attribute('instB', 'vec4');
  const packed: N = floor(B.z);
  const sz: N = floor(packed.div(64));
  // the ground's normal, its horizontal part (6 bits each way)
  const slope: N = vec2(packed.sub(sz.mul(64)), sz).div(31.5).sub(1);
  // (how far the slope leans away from the light, as seen from above)
  const away: N = slope.dot((keyDir as N).xz).negate();
  const foot: N = A.xyz;
  const c: N = cos(A.w), s: N = sin(A.w);
  const turn = (v: N): N => vec3(v.x.mul(c).add(v.z.mul(s)), v.y, v.z.mul(c).sub(v.x.mul(s)));
  const girth: N = B.x.mul(B.y);
  return {
    foot,
    dist: foot.sub(viewer).length(),
    turn,
    place: (v: N) => v.mul(vec3(girth, B.x, girth)),
    open: smoothstep((clearing as N).z.sub(3), (clearing as N).z, foot.xz.sub((clearing as N).xy).length()),
    tint: fract(B.z),
    seed: fract(B.w),
    shade: (far: boolean) => {
      const dim: N = smoothstep(0.05, 0.45, away).mul(far ? 0.72 : 0.6);
      return float(1).sub(far ? dim : dim.mul(smoothstep(55, 110, foot.sub(viewer).length())));
    },
  };
}

/** the ground's slope under a plant (the normal's x and z) and its tint (0…1) in one float: see `instanceNodes` */
function packLook(nx: number, nz: number, tint: number) {
  const q = (v: number) => Math.round((Math.min(1, Math.max(-1, v)) + 1) * 31.5);
  return q(nx) + q(nz) * 64 + Math.min(0.999, Math.max(0, tint));
}

/** what a species looks like beyond its textures */
export interface PlantLook {
  /** multiplies the leaf colour (linear) */
  tint?: [number, number, number];
  /** how much light the leaves let through (the glow of a crown against the sun or a lamp) */
  translucency?: number;
  /** strength of the wind on it (a bush moves less than a tree top) */
  wind?: number;
  /** `rock`: no leaves, no wind; the texture pair is colour and the normal in the model's own frame (tools/blender/nature/iwa.py) */
  kind?: 'plant' | 'rock';
  /** rocks: how much moss grows on what faces the sky (0…1) */
  moss?: number;
}

/** what the picture's material and the depth-only one share: where a vertex goes and the cutout */
function plantNodes(model: PlantModel, look: PlantLook, span: Span) {
  const I = instanceNodes();
  const veg: N = attribute('veg', 'vec4');
  const S: N = span;
  const windK = look.wind ?? 1;
  // `sway`: the motion vector has the wind's own movement in it (the nearest level). Further away that movement is
  // a fraction of a pixel a frame, and working the wind out a second time for the frame before doubled the vertex
  // stage of every tree under the upscaler (scene pass 8.9 ms against 4.7 ms without vegetation, 1440p quality)
  const position = (sway: boolean): N =>
    Fn(() => {
      // outside the level's span (and inside the garage's clearing) the instance is drawn at no size, at its foot
      const size: N = I.open.mul(step(S.x.sub(S.y), I.dist)).mul(step(I.dist, S.z));
      const lp: N = I.place(positionLocal).toVar();
      const at: N = I.foot.add(I.turn(lp)).toVar();
      (normalLocal as N).assign(I.turn(normalLocal));
      const now: N = mix(I.foot, at.add(windPush(lp, veg, I.foot, I.seed, windNow).mul(windK)), size).toVar();
      (positionPrevious as N).assign(sway ? mix(I.foot, at.add(windPush(lp, veg, I.foot, I.seed, windBefore).mul(windK)), size) : now);
      return now;
    })();
  // per instance, worked out in the vertex stage: the dither's two thresholds and the cutout's (far cards keep
  // their thin twigs: a mip's alpha is the coverage, and half of it would leave the crown bald)
  const fade: N = varying(
    vec3(float(1).sub(smoothstep(S.x.sub(S.y), S.x, I.dist)), float(1).sub(smoothstep(S.z.sub(S.w), S.z, I.dist)), mix(0.5, 0.26, smoothstep(5, 50, I.dist))),
  );
  const tex: N = texture(model.leaf, uv());
  const d: N = dither();
  const mask: N = tex.a.greaterThan(fade.z).and(d.lessThan(fade.y)).and(d.greaterThanEqual(fade.x));
  // x: the hillside's shade; y: 0 near … 1 beyond the shadow map's reach, where nothing stands between a tree and
  // the sun in this picture: there the light through the leaves and the wet shine are taken back (a whole forest
  // glowed against a low sun, and glittered under the moon in the rain)
  const lit: N = varying(vec2(I.shade(false), smoothstep(50, 110, I.dist)));
  return { I, veg, position, mask, tex, shade: lit.x, far: lit.y };
}

/**
 * The material of a level's meshes: bark and foliage from the species' one texture pair. `second`: the lit pass of
 * two (see the file's header): no cutout, only where the first pass left this very depth.
 */
function plantMaterial(model: PlantModel, look: PlantLook, span: Span, second = false, sway = true) {
  const mat = new MeshSSSNodeMaterial();
  mat.side = THREE.DoubleSide;
  mat.metalness = 0;
  mat.envMapIntensity = 0.3;
  const { I, veg, position, mask, tex, shade, far } = plantNodes(model, look, span);
  mat.positionNode = position(sway);
  const texN: N = model.leafN ? texture(model.leafN, uv()) : vec4(0.5, 0.5, 1, 1);
  if (second) {
    mat.depthFunc = THREE.EqualDepth;
    mat.depthWrite = false;
  } else mat.maskNode = mask;
  const leaf: N = texN.a;
  const hue: N = mix(vec3(0.8, 0.9, 0.74), vec3(1.14, 1.06, 0.9), I.tint).mul(vec3(...(look.tint ?? [1, 1, 1])));
  const ao: N = veg.r;
  const albedo: N = tex.rgb
    .mul(mix(vec3(1), hue, leaf.mul(0.75).add(0.25)))
    .mul(ao.mul(0.6).add(0.4))
    .mul(mix(1, 0.68, wet))
    .mul(shade);
  mat.colorNode = vec4(albedo, 1);
  // (wet leaves shine, but not as mirrors: at 0.3 a forest in the rain glittered white under the moon)
  mat.roughnessNode = mix(mix(0.92, 0.72, leaf), 0.46, wet.mul(0.85).mul(float(1).sub(far)));
  // (far foliage is dark, and against a low sun or the moon its surface shine was more light than its colour: a
  // hillside of pale dots, whatever the leaves' colour was set to)
  mat.specularIntensityNode = mix(1, 0.1, far);
  mat.aoNode = ao;
  const n: N = texN.rgb.mul(2).sub(1);
  mat.normalNode = perturb(normalViewGeometry, vec3(n.xy.mul(1.2), n.z), uv());
  // light through the leaves: the crown's rim glows against the sun, a lamp, headlights
  mat.thicknessColorNode = albedo.mul(leaf).mul((look.translucency ?? 1) * 1.6).mul(mix(1, 0.2, far));
  mat.thicknessDistortionNode = float(0.4);
  mat.thicknessAmbientNode = float(0);
  mat.thicknessAttenuationNode = float(1);
  mat.thicknessPowerNode = float(3);
  mat.thicknessScaleNode = float(2);
  return mat;
}

/** The first of a tree level's two passes: the cutout, the depth, the motion vectors, and the colour under the sky's light. */
function firstMaterial(model: PlantModel, look: PlantLook, span: Span, sway = true) {
  const mat = new MeshBasicNodeMaterial();
  mat.side = THREE.DoubleSide;
  const { I, veg, position, mask, tex, shade } = plantNodes(model, look, span);
  mat.positionNode = position(sway);
  mat.maskNode = mask;
  const hue: N = mix(vec3(0.8, 0.9, 0.74), vec3(1.14, 1.06, 0.9), I.tint).mul(vec3(...(look.tint ?? [1, 1, 1])));
  mat.colorNode = vec4(tex.rgb.mul(hue).mul(veg.r.mul(0.6).add(0.4)).mul(mix(1, 0.68, wet)).mul(shade).mul(skyLight), 1);
  return mat;
}

/** a rock: its colour and normal from the octahedral map, moss on what faces the sky, darker and shinier in rain */
function rockMaterial(model: PlantModel, look: PlantLook, span: Span) {
  const mat = new MeshStandardNodeMaterial();
  mat.metalness = 0;
  mat.envMapIntensity = 0.4;
  const I = instanceNodes();
  const S: N = span;
  mat.positionNode = Fn(() => {
    const size: N = I.open.mul(step(S.x.sub(S.y), I.dist)).mul(step(I.dist, S.z));
    const at: N = mix(I.foot, I.foot.add(I.turn(I.place(positionLocal))), size).toVar();
    (normalLocal as N).assign(I.turn(normalLocal));
    (positionPrevious as N).assign(at);
    return at;
  })();
  const fade: N = varying(vec2(float(1).sub(smoothstep(S.x.sub(S.y), S.x, I.dist)), float(1).sub(smoothstep(S.z.sub(S.w), S.z, I.dist))));
  const d: N = dither();
  mat.maskNode = d.lessThan(fade.y).and(d.greaterThanEqual(fade.x));
  const tex: N = texture(model.leaf, uv());
  const texN: N = model.leafN ? texture(model.leafN, uv()) : vec4(0.5, 1, 0.5, 0.5);
  // the normal in the rock's frame, turned with the instance: the world's
  const world: N = I.turn(texN.rgb.mul(2).sub(1)).normalize();
  const moss: N = smoothstep(0.5, 0.82, world.y.mul(0.7).add(texN.a.mul(0.5))).mul(look.moss ?? 1);
  const shade: N = mix(0.82, 1.12, I.tint);
  const albedo: N = mix(tex.rgb.mul(shade).mul(vec3(...(look.tint ?? [1, 1, 1]))), vec3(0.075, 0.115, 0.035).mul(tex.g.mul(1.6).add(0.45)), moss).mul(mix(1, 0.62, wet));
  mat.colorNode = vec4(albedo, 1);
  mat.roughnessNode = mix(mix(0.88, 0.97, moss), 0.32, wet.mul(0.85));
  mat.normalNode = (cameraViewMatrix as N).mul(vec4(world, 0)).xyz.normalize();
  return mat;
}

/**
 * The material of the shadow meshes: only where the vertex goes and the cutout. `hull`: a tree's closed shape
 * (`hullOf`), one side of it, with holes where a noise in the tree's own space says so (the light that falls through
 * a crown, without a texture to read per texel).
 */
function shadowMaterial(model: PlantModel, look: PlantLook, reach: Reach, hull: boolean) {
  const mat = new MeshBasicNodeMaterial();
  mat.side = hull ? THREE.FrontSide : THREE.DoubleSide;
  const I = instanceNodes();
  const veg: N = attribute('veg', 'vec4');
  mat.positionNode = Fn(() => {
    const size: N = I.open.mul(step(I.dist, reach as N));
    const lp: N = I.place(positionLocal).toVar();
    return mix(I.foot, I.foot.add(I.turn(lp)).add(windPush(lp, veg, I.foot, I.seed, windNow).mul(look.wind ?? 1)), size);
  })();
  if (hull) {
    const q: N = varying(positionLocal), crown: N = varying(veg.a);
    // (holes under a metre across, each wave bent by another: at 1.5 m they lay on a wall as blots, and straight
    // waves made a lattice of round spots on the road)
    const gaps: N = sin(q.x.mul(7.3).add(sin(q.z.mul(2.9).add(q.y.mul(1.7))).mul(2.1)))
      .mul(sin(q.z.mul(6.1).add(sin(q.x.mul(3.7).sub(q.y.mul(2.3))).mul(2.3))))
      .add(sin(q.y.mul(9.7).add(sin(q.x.mul(4.3).add(q.z.mul(5.1))).mul(1.9))).mul(0.5));
    mat.maskShadowNode = gaps.lessThan(mix(9, 0.3, crown));
  } else mat.maskShadowNode = (texture(model.leaf, uv()) as N).a.greaterThan(0.4);
  return mat;
}

/** the impostors' material: a card that turns to the viewer about the vertical and shows the nearest of the eight views */
function impostorMaterial(model: PlantModel, look: PlantLook, span: Span) {
  const mat = new MeshSSSNodeMaterial();
  mat.metalness = 0;
  mat.envMapIntensity = 0.3;
  const I = instanceNodes();
  const B: N = attribute('instB', 'vec4');
  // (half width, height, foot depth, first row) and the cell (u0, v0, width, height) of the instance's variant
  const F: N = attribute('instC', 'vec4'), C: N = attribute('instD', 'vec4');
  const S: N = span;
  const to: N = viewer.xz.sub(I.foot.xz);
  const dir: N = to.div(max(to.length(), 0.001));
  // the view as the Blender bake framed it: from the azimuth (measured from +Z towards +X), picture x to the right
  const right: N = vec3(dir.y, 0, dir.x.negate());
  const corner: N = positionLocal;
  const lean = (t: N): N => {
    const ph: N = I.seed.mul(6.283).add(I.foot.x.mul(0.031)).add(I.foot.z.mul(0.047));
    const gust: N = sin(t.mul(0.7).add(ph)).mul(0.5).add(sin(t.mul(1.9).add(ph.mul(1.7))).mul(0.25)).add(0.35);
    const h: N = corner.y.mul(F.y).mul(B.x).mul(1 / 16);
    return vec3(WIND.x, 0, WIND.y).mul(h.mul(h).mul(gust).mul(0.3 * (look.wind ?? 1))).mul(windPower);
  };
  mat.positionNode = Fn(() => {
    const size: N = I.open.mul(step(S.x.sub(S.y), I.dist));
    // (far away the cards are drawn wider: the crowns of a hillside close into a canopy, where trees a few pixels
    // wide with the dark ground between them were a grain)
    const wide: N = mix(1, 1.8, smoothstep(S.x, S.x.add(350), I.dist));
    const at: N = I.foot
      .add(right.mul(corner.x.mul(F.x).mul(B.x).mul(B.y).mul(wide)))
      .add(vec3(0, 1, 0).mul(corner.y.mul(F.y).add(F.z).mul(B.x)))
      .toVar();
    (positionPrevious as N).assign(mix(I.foot, at.add(lean(windBefore)), size));
    return mix(I.foot, at.add(lean(windNow)), size);
  })();
  // which of the eight views: the viewer's azimuth as the turned tree sees it
  const az: N = atan(dir.x, dir.y).sub(attribute('instA', 'vec4').w);
  const view: N = floor(fract(az.mul(1 / (2 * Math.PI)).add(1 / 16)).mul(8));
  const cell: N = varying(vec4(C.x.add(view.mul(C.z)), C.y, C.z, C.w));
  const coord: N = vec2(cell.x.add(uv().x.mul(cell.z)), cell.y.add(float(1).sub(uv().y).mul(cell.w)));
  // (z: how much of the card's height is drawn. Far away the texture's small mips mix a view with the cells around
  // it, and the trunk's foot of the variant in the row above showed as a dot in the air over every distant tree)
  const fade: N = varying(
    vec3(float(1).sub(smoothstep(S.x.sub(S.y), S.x, I.dist)), mix(0.45, 0.25, smoothstep(150, 600, I.dist)), mix(1.0, 0.93, smoothstep(230, 600, I.dist))),
  );
  const tex: N = texture(model.imp!, coord);
  mat.maskNode = tex.a.greaterThan(fade.y).and(dither().greaterThanEqual(fade.x)).and(uv().y.lessThan(fade.z));
  const hue: N = mix(vec3(0.8, 0.9, 0.74), vec3(1.14, 1.06, 0.9), I.tint).mul(vec3(...(look.tint ?? [1, 1, 1])));
  // (a far hillside is a canopy: its trees stand in each other's shade. Lit one by one as if each stood alone they
  // were bright dots on the darker ground, a grain over the whole mountain at dawn)
  // (from where the impostors begin, so that the last mesh level hands over at the same brightness)
  const canopy: N = mix(1, 0.45, smoothstep(S.x, S.x.add(350), I.dist));
  const albedo: N = tex.rgb.mul(mix(vec3(1), hue, 0.85)).mul(mix(1, 0.68, wet)).mul(varying(I.shade(true).mul(canopy)));
  mat.colorNode = vec4(albedo, 1);
  mat.roughnessNode = float(0.8);
  // (see `plantMaterial` on the shine of far foliage)
  mat.specularIntensityNode = float(0.1);
  // the baked normal is in the view's frame: right, up, towards the viewer
  const basis: N = varying(vec4(right.x, right.z, dir.x, dir.y));
  const n: N = model.impN ? (texture(model.impN, coord) as N).rgb.mul(2).sub(1) : vec3(0, 0, 1);
  const world: N = vec3(basis.x.mul(n.x).add(basis.z.mul(n.z)), n.y, basis.y.mul(n.x).add(basis.w.mul(n.z)));
  mat.normalNode = (cameraViewMatrix as N).mul(vec4(world, 0)).xyz.normalize();
  // (a tree this far away is out of the lamps' and the headlights' reach)
  if (farLights) mat.lightsNode = lights(farLights) as N;
  // (little: see `plantNodes` on the far trees)
  mat.thicknessColorNode = albedo.mul((look.translucency ?? 1) * 0.3);
  mat.thicknessDistortionNode = float(0.4);
  mat.thicknessAmbientNode = float(0);
  mat.thicknessAttenuationNode = float(1);
  mat.thicknessPowerNode = float(3);
  mat.thicknessScaleNode = float(2);
  return mat;
}

// ------------------------------------------------------------------------------------------------ instances

/** floats per instance: x, y, z, yaw, height scale, girth, tint, seed */
const STRIDE = 8;

function instanced(base: THREE.BufferGeometry, capacity: number, stride = STRIDE) {
  const geo = new THREE.InstancedBufferGeometry();
  geo.index = base.index;
  for (const name of Object.keys(base.attributes)) geo.setAttribute(name, base.attributes[name]);
  // (not DynamicDrawUsage: the renderer uploads a dynamic buffer every frame, changed or not)
  const data = new THREE.InstancedInterleavedBuffer(new Float32Array(Math.max(1, capacity) * stride), stride, 1);
  const names = ['instA', 'instB', 'instC', 'instD'];
  for (let k = 0; k * 4 < stride; k++) geo.setAttribute(names[k], new THREE.InterleavedBufferAttribute(data, 4, k * 4));
  geo.instanceCount = 0;
  return { geo, data };
}

/** a plant to stand somewhere */
export interface Planted {
  /** index into the forest's species, and the shape variant */
  species: number;
  variant: number;
  x: number;
  y: number;
  z: number;
  yaw: number;
  /** height scale and girth (width relative to it) */
  scale: number;
  girth: number;
  /** 0 … 1 across the species' range of leaf colour */
  tint: number;
  /** the ground's normal under it, x and z (default: level ground) */
  nx?: number;
  nz?: number;
  seed: number;
  /** it never comes near the viewer (far from the road): an impostor only */
  far?: boolean;
  /** it throws a shadow (default: it does). Only what stands by the road should: the others' shadows fall in the forest, unseen */
  casts?: boolean;
  /** how far from the road it stands (m): the impostors are drawn in this order, nearest first (see the file's header) */
  order?: number;
}

export interface ForestSpecies {
  model: PlantModel;
  look: PlantLook;
}

export interface ForestOptions {
  /** where each mesh level ends (m): lod0, lod1, lod2; the impostors take over from there (or nothing: `impostors: false`) */
  ranges: [number, number, number];
  /** how far around the viewer the trees throw shadows (0: none) */
  shadows: number;
  impostors?: boolean;
  /** side of a chunk (m) */
  chunk?: number;
  receiveShadow?: boolean;
  /** most instances a mesh of each level holds (lod0, lod1, lod2, shadow) */
  capacity?: [number, number, number, number];
  /** how far the viewer moves before a level's instances are picked again (m; lod0, lod1, lod2, shadow) */
  strides?: [number, number, number, number];
  /**
   * Levels (lod0, lod1, lod2, shadow) that draw every plant of a species with its first variant's shape (as tall as
   * its own): a draw call per species instead of one per variant, where the difference cannot be told (far, shadows).
   */
  single?: [boolean, boolean, boolean, boolean];
  /** the mesh levels are drawn in two passes, the cutout first and the lighting where it is seen (trees: see the file's header) */
  prepass?: boolean;
}

interface Chunk {
  x: number;
  z: number;
  radius: number;
  /** per species × variant: the instances' data */
  sets: Map<number, Float32Array>;
  /** the same of those that throw shadows */
  casters: Map<number, Float32Array>;
  /** distance to the viewer at the pick under way */
  d: number;
}

interface LevelMesh {
  mesh: THREE.Mesh;
  /** the first pass' twin (`ForestOptions.prepass`) */
  pre: THREE.Mesh | null;
  geo: THREE.InstancedBufferGeometry;
  data: THREE.InstancedInterleavedBuffer;
  capacity: number;
  /** the species × variant sets it draws, and what each one's height is multiplied by (a `single` level: the variant's height over the drawn shape's) */
  keys: number[];
  fit: number[];
  tris: number;
  n: number;
}

interface Level {
  /** the span of distances the level draws, the fade band before `near` included */
  near: number;
  far: number;
  /** its instances are picked again when the viewer has moved this far (m) */
  stride: number;
  at: THREE.Vector3;
  meshes: LevelMesh[];
}

const MAX_VARIANTS = 8;
/** how tall a shape stands (m) */
function tall(geo: THREE.BufferGeometry) {
  if (!geo.boundingBox) geo.computeBoundingBox();
  return Math.max(0.01, geo.boundingBox!.max.y);
}
/**
 * The nearest level's place in the drawing order: before everything else in the scene (see the file's header) but
 * the sky, which is at -10 and does not test the depth (it would paint over the forest).
 */
const FIRST = -8;
/** most instances a mesh of each level holds (lod0, lod1, lod2, shadow) */
const CAPACITY = [400, 1600, 6000, 3000];
/** how far the viewer moves before a level's instances are picked again (lod0, lod1, lod2, shadow) */
const STRIDES = [2, 4, 8, 8];

/**
 * Plants in chunks; each mesh level of detail holds the plants within its span, picked plant by plant on the CPU
 * whenever the viewer has moved a few metres (a hero tree is 17 000 triangles: one too many is not free), with a
 * margin as wide as that move, inside which the shader draws the plant at no size (see the file's header).
 * A plant marked `far` never comes near the road: it is an impostor only. `update` once a frame with the camera.
 */
export class Forest {
  readonly group = new THREE.Group();
  private chunks: Chunk[] = [];
  private levels: Level[] = [];
  private impostorMeshes: { mesh: THREE.Mesh; count: number }[] = [];
  private reach = uniform(0);
  private materials = new Map<number, THREE.Material>();
  /** every mesh is in the scene, empty or not (see `vegetationHold`) */
  private showingAll = true;
  private inReach: Chunk[] = [];
  count = 0;

  constructor(private readonly species: ForestSpecies[], plants: Planted[], opts: ForestOptions) {
    const size = opts.chunk ?? 32;
    const lists = new Map<string, Map<number, number[]>>();
    const castLists = new Map<string, Map<number, number[]>>();
    const total = new Map<number, number>(), totalCast = new Map<number, number>();
    // (stable: plants without an order stay as they were planted)
    plants = [...plants].sort((a, b) => (a.order ?? 0) - (b.order ?? 0));
    /** per species: every plant's data, for the impostors */
    const all: number[][] = species.map(() => []);
    for (const p of plants) {
      const sp = species[p.species];
      if (!sp) continue;
      const variant = p.variant % sp.model.variants.length;
      const k = p.species * MAX_VARIANTS + variant;
      const row = [p.x, p.y, p.z, p.yaw, p.scale, p.girth, packLook(p.nx ?? 0, p.nz ?? 0, p.tint), variant + Math.min(0.999, Math.max(0, p.seed))];
      const list0 = all[p.species];
      for (const v of row) list0.push(v);
      this.count++;
      if (p.far) continue;
      const ck = `${Math.floor(p.x / size)},${Math.floor(p.z / size)}`;
      let sets = lists.get(ck);
      if (!sets) lists.set(ck, (sets = new Map()));
      let list = sets.get(k);
      if (!list) sets.set(k, (list = []));
      for (const v of row) list.push(v);
      total.set(k, (total.get(k) ?? 0) + 1);
      if (p.casts === false || !(opts.shadows > 0)) continue;
      let cast = castLists.get(ck);
      if (!cast) castLists.set(ck, (cast = new Map()));
      let clist = cast.get(k);
      if (!clist) cast.set(k, (clist = []));
      for (const v of row) clist.push(v);
      totalCast.set(k, (totalCast.get(k) ?? 0) + 1);
    }
    for (const [ck, sets] of lists) {
      let x0 = Infinity, x1 = -Infinity, z0 = Infinity, z1 = -Infinity;
      const out = new Map<number, Float32Array>(), casters = new Map<number, Float32Array>();
      for (const [k, list] of sets) {
        out.set(k, new Float32Array(list));
        for (let i = 0; i < list.length; i += STRIDE) {
          x0 = Math.min(x0, list[i]), x1 = Math.max(x1, list[i]);
          z0 = Math.min(z0, list[i + 2]), z1 = Math.max(z1, list[i + 2]);
        }
      }
      for (const [k, list] of castLists.get(ck) ?? []) casters.set(k, new Float32Array(list));
      this.chunks.push({ x: (x0 + x1) / 2, z: (z0 + z1) / 2, radius: Math.hypot(x1 - x0, z1 - z0) / 2, sets: out, casters, d: 0 });
    }

    // the mesh levels and the shadow level (index 3)
    const [r0, r1, r2] = opts.ranges;
    const impostors = opts.impostors !== false;
    const band = (r: number) => Math.min(14, Math.max(3, r * 0.2));
    const bounds = [0, r0, r1, r2];
    for (let l = 0; l < 4; l++) {
      const shadow = l === 3;
      const near = shadow ? 0 : bounds[l], far = shadow ? opts.shadows : bounds[l + 1];
      // (the last mesh level without impostors behind it fades out into nothing over a long band)
      const span = uniform(new THREE.Vector4(near, l === 0 ? 0 : band(near), far, l === 2 && !impostors ? far * 0.3 : band(far)));
      const level: Level = { near: near - (l === 0 ? 0 : band(near)), far, stride: (opts.strides ?? STRIDES)[l], at: new THREE.Vector3(1e9, 0, 0), meshes: [] };
      this.levels.push(level);
      if (far <= near) continue;
      species.forEach((sp, si) => {
        const one = !!opts.single?.[l];
        const shape = (v: Variant) => (shadow ? (v.hull ?? v.lods[2]) : v.lods[l]);
        sp.model.variants.forEach((variant, vi) => {
          if (one && vi > 0) return;
          const base = shape(variant);
          const drawn = sp.model.variants.map((_, j) => j).filter((j) => (one || j === vi) && shape(sp.model.variants[j]));
          const keys = drawn.map((j) => si * MAX_VARIANTS + j);
          const fit = drawn.map((j) => (base ? tall(shape(sp.model.variants[j])!) / tall(base) : 1));
          const n = keys.reduce((sum, k) => sum + ((shadow ? totalCast : total).get(k) ?? 0), 0);
          if (!n || !base) return;
          const capacity = Math.min(n, (opts.capacity ?? CAPACITY)[l]);
          const { geo, data } = instanced(base, capacity);
          const prepass = !shadow && !!opts.prepass && sp.look.kind !== 'rock';
          const mat = shadow ? this.material(si, 4 + (variant.hull ? 1 : 0), span) : this.material(si, l, span, prepass);
          const mesh = new THREE.Mesh(geo, mat as unknown as THREE.Material);
          mesh.frustumCulled = false;
          mesh.name = `${sp.model.id}-v${vi}-${shadow ? 'shadow' : `lod${l}`}`;
          if (shadow) {
            mesh.castShadow = true;
            mesh.layers.set(SHADOW_LAYER);
          } else {
            // (a level that begins beyond the shadow map's reach, 60 m, takes no shadows: one texture read less)
            mesh.receiveShadow = opts.receiveShadow !== false && near < 60;
            mesh.renderOrder = FIRST + l;
          }
          this.group.add(mesh);
          let pre: THREE.Mesh | null = null;
          if (prepass) {
            pre = new THREE.Mesh(geo, this.material(si, 8 + l, span));
            pre.frustumCulled = false;
            pre.name = `${sp.model.id}-v${vi}-first${l}`;
            pre.renderOrder = FIRST - 1.5 + l * 0.1;
            this.group.add(pre);
          }
          const tris = shadow ? (geo.index ? geo.index.count / 3 : 0) : (sp.model.tris[vi]?.[l] ?? 0);
          level.meshes.push({ mesh, pre, geo, data, capacity, keys, fit, tris, n: 0 });
        });
      });
    }
    this.reach.value = opts.shadows;

    // the impostors: every plant of a species in one mesh that never changes
    if (impostors) {
      const quad = new THREE.BufferGeometry();
      quad.setAttribute('position', new THREE.BufferAttribute(new Float32Array([-1, 0, 0, 1, 0, 0, 1, 1, 0, -1, 1, 0]), 3));
      quad.setAttribute('uv', new THREE.BufferAttribute(new Float32Array([0, 0, 1, 0, 1, 1, 0, 1]), 2));
      quad.setIndex([0, 1, 2, 0, 2, 3]);
      const span = uniform(new THREE.Vector4(r2, band(r2), 1e9, 1));
      species.forEach((sp, si) => {
        const rows = all[si];
        const n = rows.length / STRIDE;
        if (!sp.model.imp || !n) return;
        const { geo, data } = instanced(quad, n, 16);
        const arr = data.array as Float32Array;
        for (let i = 0; i < n; i++) {
          for (let k = 0; k < STRIDE; k++) arr[i * 16 + k] = rows[i * STRIDE + k];
          const f = sp.model.variants[Math.floor(rows[i * STRIDE + 7])].impostor;
          if (f) arr.set([f.half, f.height, f.base, 0, ...f.cell], i * 16 + 8);
        }
        geo.instanceCount = n;
        const mesh = new THREE.Mesh(geo, impostorMaterial(sp.model, sp.look, span) as unknown as THREE.Material);
        mesh.frustumCulled = false;
        mesh.name = `${sp.model.id}-impostors`;
        mesh.renderOrder = FIRST + 3;
        this.group.add(mesh);
        this.impostorMeshes.push({ mesh, count: n });
      });
    }
  }

  /** one material per species and level (its span differs); `level` 4 / 5: the shadows' (cards / hull), 8…: the depth pass of level − 8 */
  private material(species: number, level: number, span: Span, prepass = false) {
    const key = species * 16 + level;
    let m = this.materials.get(key);
    if (!m) {
      const sp = this.species[species];
      if (level >= 8) m = firstMaterial(sp.model, sp.look, span, level === 8) as unknown as THREE.Material;
      else if (level >= 4) m = shadowMaterial(sp.model, sp.look, this.reach, level === 5) as unknown as THREE.Material;
      else m = (sp.look.kind === 'rock' ? rockMaterial(sp.model, sp.look, span) : plantMaterial(sp.model, sp.look, span, prepass, level === 0)) as unknown as THREE.Material;
      this.materials.set(key, m);
    }
    return m;
  }

  update(camera: THREE.Vector3) {
    if (this.showingAll && !held) {
      this.showingAll = false;
      for (const lv of this.levels) for (const lm of lv.meshes) lm.mesh.visible = lm.n > 0, lm.pre && (lm.pre.visible = lm.n > 0);
    }
    for (const lv of this.levels) {
      if (!lv.meshes.length || lv.at.distanceToSquared(camera) < lv.stride * lv.stride) continue;
      lv.at.copy(camera);
      // (as wide as the move that comes before the next pick, and a little)
      const margin = lv.stride + 1.5;
      const lo = Math.max(0, lv.near - margin), hi = lv.far + margin;
      const lo2 = lo * lo, hi2 = hi * hi;
      const shadow = lv === this.levels[3];
      for (const lm of lv.meshes) lm.n = 0;
      // the chunks in reach, nearest first: what is drawn first hides what comes after it
      const near = this.inReach;
      near.length = 0;
      for (const c of this.chunks) {
        c.d = Math.hypot(c.x - camera.x, c.z - camera.z);
        if (c.d - c.radius <= hi) near.push(c);
      }
      near.sort((a, b) => a.d - b.d);
      for (const c of near) {
        for (const lm of lv.meshes) {
          const arr = lm.data.array as Float32Array;
          for (let j = 0; j < lm.keys.length; j++) {
            const set = (shadow ? c.casters : c.sets).get(lm.keys[j]);
            if (!set) continue;
            const fit = lm.fit[j];
            for (let i = 0; i < set.length && lm.n < lm.capacity; i += STRIDE) {
              const dx = set[i] - camera.x, dy = set[i + 1] - camera.y, dz = set[i + 2] - camera.z;
              const d2 = dx * dx + dy * dy + dz * dz;
              if (d2 > hi2 || d2 < lo2) continue;
              const o = lm.n++ * STRIDE;
              for (let k = 0; k < STRIDE; k++) arr[o + k] = set[i + k];
              arr[o + 4] *= fit;
            }
          }
        }
      }
      for (const lm of lv.meshes) {
        lm.geo.instanceCount = lm.n;
        lm.mesh.visible = lm.n > 0 || this.showingAll;
        if (lm.pre) lm.pre.visible = lm.mesh.visible;
        if (!lm.n) continue;
        lm.data.clearUpdateRanges();
        lm.data.addUpdateRange(0, lm.n * STRIDE);
        lm.data.needsUpdate = true;
      }
    }
  }

  /** what is being drawn: draw calls, instances and triangles per level (lod0, lod1, lod2, shadow, impostors) */
  stats() {
    const levels = this.levels.map((lv) => {
      let draws = 0, instances = 0, triangles = 0;
      for (const lm of lv.meshes) {
        if (!lm.mesh.visible || !lm.geo.instanceCount) continue;
        draws += lm.pre ? 2 : 1;
        instances += lm.geo.instanceCount;
        triangles += lm.geo.instanceCount * lm.tris;
      }
      return { draws, instances, triangles };
    });
    const count = this.impostorMeshes.reduce((s, m) => s + m.count, 0);
    levels.push({ draws: this.impostorMeshes.length, instances: count, triangles: count * 2 });
    return { plants: this.count, chunks: this.chunks.length, levels };
  }
}
