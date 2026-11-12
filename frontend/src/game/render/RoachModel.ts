import * as THREE from 'three';
import { clone as cloneSkinned } from 'three/examples/jsm/utils/SkeletonUtils.js';
import type { CarSpec } from '../vehicle/carSpecs';
import type { CreatureInfo } from '../vehicle/roach';
import { createCarMaterials, type CarRig } from './CarModel';

/**
 * The giant cockroach (joke entry): our own model with a skinned scuttle cycle (public/models/roach/roach.glb, built
 * by tools/blender-models.cjs from tools/blender/creatures/roach.py: alternating tripods, 1.6 m of ground per cycle),
 * or a procedural stand-in when it is missing. The legs run with the distance covered (capped so they do not strobe
 * at speed). Head +Z, feet on y = 0.
 */
let model: { scene: THREE.Object3D; clip: THREE.AnimationClip | null } | null = null;

export async function loadRoachModel() {
  if (model) return;
  const { GLTFLoader } = await import('three/examples/jsm/loaders/GLTFLoader.js');
  const { MeshoptDecoder } = await import('three/examples/jsm/libs/meshopt_decoder.module.js');
  const loader = new GLTFLoader();
  loader.setMeshoptDecoder(MeshoptDecoder);
  try {
    const gltf = await loader.loadAsync('/models/roach/roach.glb');
    const clip = gltf.animations[0] ?? null;
    // the wings are posed by the game (flight): the cycle must not hold them, should an export have keyed them
    if (clip) clip.tracks = clip.tracks.filter((t) => !WING_BONE.test(t.name.split('.')[0]));
    model = { scene: gltf.scene, clip };
  } catch (err) {
    console.warn('cockroach model not loaded, using the procedural body', err);
  }
}

/** the model's wing bones: `wing_L` / `wing_R` carry the wing cases (tegmina), `hind_L` / `hind_R` the hind wings */
const WING_BONE = /^(wing|hind)_[LR]$/;

/** overall length the model is scaled to, antennae and hind legs included (m): the body (head to wing tips) is 3.4 m */
const LENGTH = 6.76;
/** most leg cycles per second (beyond it the gait would strobe at 60 fps) */
const MAX_CYCLES = 9;

export interface CreatureRig {
  /**
   * run the legs by the distance the anchor moved since the last call; `airborne` (a live sim's: no leg on the
   * ground) opens the wings and lets them beat
   */
  update(anchor: THREE.Object3D, dt: number, airborne?: boolean): void;
  setLivery(color: string): void;
  /** how far the wings are out (0 folded … 1 flying): the sound's flutter follows it */
  readonly flight: number;
  /** hold the wings in a pose (pictures and probes: tools/roach-wings.cjs); the next flight takes over again */
  poseWings(opened: number, phase: number): void;
}

type Flight = CreatureInfo['flight'];
/** the wings' state: seconds off / on the ground, whether it flies, how far the wings are out, where the beat is */
export interface FlightState {
  air: number;
  ground: number;
  flying: boolean;
  opened: number;
  phase: number;
}
export const flightState = (): FlightState => ({ air: 0, ground: 0, flying: false, opened: 0, phase: 0 });

/**
 * A step of the wings' state. A hop shorter than `after` opens nothing, and a touch of a leg shorter than
 * `settle` folds nothing (a tumbling cockroach touches down again and again).
 */
export function flightStep(s: FlightState, f: Flight, airborne: boolean, dt: number) {
  if (airborne) {
    s.air += dt;
    s.ground = 0;
    if (s.air >= f.after) s.flying = true;
  } else {
    s.ground += dt;
    s.air = 0;
    if (s.ground >= f.settle) s.flying = false;
  }
  s.opened = s.flying ? Math.min(1, s.opened + dt / f.open) : Math.max(0, s.opened - dt / f.fold);
  s.phase = s.opened > 0 ? (s.phase + dt * f.rate) % 1 : 0;
  return s;
}

const RAD = Math.PI / 180;
const ramp = (a: number, b: number, x: number) => THREE.MathUtils.smoothstep(x, a, b);

/**
 * The wings' pose (rad; `unfold` = the hind wings' scale across the chord) by how far they are out and where the
 * beat is (0…1). The wing cases go first, the hind wings come out from under them and unfold, and the beat only
 * comes with the wings out. The same sum as tools/blender/creatures/roach_rig.py `flight_angles`: keep both alike.
 */
export function wingPose(f: Flight, opened: number, phase: number) {
  const at = ramp(0, 0.6, opened), ah = ramp(0.3, 1, opened), beat = ramp(0.7, 1, opened);
  const s = Math.sin(2 * Math.PI * phase), c = Math.cos(2 * Math.PI * phase);
  const of = (w: Flight['tegmen'], a: number) => ({ sweep: w.sweep * a * RAD, lift: (w.lift * a + w.beat * beat * s) * RAD, twist: w.twist * beat * c * RAD });
  return { tegmen: of(f.tegmen, at), hind: { ...of(f.hind, ah), unfold: 1 + (f.hind.unfold - 1) * ah * ah } };
}

/** a wing bone, its side (+1 left), what it has at rest, its parent's turn in the model's frame and the axis its fan opens along */
interface Wing {
  bone: THREE.Object3D;
  hind: boolean;
  side: number;
  rest: THREE.Quaternion;
  parent: THREE.Quaternion;
  parentInv: THREE.Quaternion;
  chord: 'x' | 'y' | 'z';
}
const AXES = { x: new THREE.Vector3(1, 0, 0), y: new THREE.Vector3(0, 1, 0), z: new THREE.Vector3(0, 0, 1) };
const _w = new THREE.Quaternion(), _t = new THREE.Quaternion();

/**
 * The model's wing bones as they rest (to be read before the cycle moves anything). The model's frame is the
 * game's: +X the insect's left, +Y up, +Z ahead; a wing lies with its tip to the rear.
 */
function findWings(scene: THREE.Object3D): Wing[] {
  const wings: Wing[] = [];
  scene.updateMatrixWorld(true);
  const inv = scene.getWorldQuaternion(new THREE.Quaternion()).invert();
  scene.traverse((o) => {
    if (!WING_BONE.test(o.name) || !o.parent) return;
    const parent = inv.clone().multiply(o.parent.getWorldQuaternion(new THREE.Quaternion()));
    // the fan opens across the insect: along the bone's own axis that lies nearest to the model's X
    const world = parent.clone().multiply(o.quaternion);
    const across = (k: 'x' | 'y' | 'z') => Math.abs(_v.copy(AXES[k]).applyQuaternion(world).x);
    const chord = (['x', 'y', 'z'] as const).reduce((a, b) => (across(b) > across(a) ? b : a));
    wings.push({ bone: o, hind: o.name.startsWith('hind'), side: o.name.endsWith('L') ? 1 : -1, rest: o.quaternion.clone(), parent, parentInv: parent.clone().invert(), chord });
  });
  return wings;
}
const _v = new THREE.Vector3();

/** Turn the wing bones to a pose: about the model's axes at the hinge (swung out, lifted, feathered), said in the parent's frame. */
function poseWings(wings: Wing[], pose: ReturnType<typeof wingPose>) {
  for (const w of wings) {
    const a = w.hind ? pose.hind : pose.tegmen;
    _w.setFromAxisAngle(AXES.y, -w.side * a.sweep).multiply(_t.setFromAxisAngle(AXES.x, a.lift)).multiply(_t.setFromAxisAngle(AXES.z, w.side * a.twist));
    w.bone.quaternion.copy(w.parentInv).multiply(_w).multiply(w.parent).multiply(w.rest);
    if (w.hind) w.bone.scale[w.chord] = pose.hind.unfold;
  }
}

export function buildRoach(spec: CarSpec, opts: { bodyColor?: string } = {}): CarRig & { creature: CreatureRig } {
  const info = spec.creature as CreatureInfo;
  const carMats = createCarMaterials(spec);
  const root = new THREE.Group();
  root.name = `creature-${spec.id}`;
  const body = new THREE.Group();
  root.add(body);
  // the sim drives four wheels: empty stand-ins (the legs are the model's own)
  const wheels = [0, 1, 2, 3].map(() => {
    const pivot = new THREE.Group(), spin = new THREE.Group();
    pivot.add(spin);
    root.add(pivot);
    return { pivot, spin };
  });

  const tinted: THREE.MeshStandardMaterial[] = [];
  let mixer: THREE.AnimationMixer | null = null;
  let wings: Wing[] = [];
  let duration = 1;
  let eyes = new THREE.Vector3(0, 0.55, 1.6);
  /** where the beams start: the eyes' centres (body space), left first */
  let lamps: THREE.Vector3[] | null = null;
  if (model) {
    const scene = cloneSkinned(model.scene);
    scene.traverse((o) => {
      const m = o as THREE.Mesh;
      if (!m.isMesh) return;
      // own copies of the materials (tint, ghosts)
      m.material = (m.material as THREE.MeshStandardMaterial).clone();
      tinted.push(m.material as THREE.MeshStandardMaterial);
      m.castShadow = true;
      m.receiveShadow = true;
      // the skinned bounds of the bind pose miss the moving legs
      m.frustumCulled = false;
    });
    wings = findWings(scene);
    if (model.clip) {
      mixer = new THREE.AnimationMixer(scene);
      mixer.clipAction(model.clip).play();
      duration = model.clip.duration || 1;
      mixer.setTime(0);
    }
    // scale to size, centred along, feet on the ground (posed bounds: the skinning applied). Across, the model's own
    // plane of symmetry (x = 0) stays on the centreline: the posed bounds are lopsided (the long antennae and the
    // tripod gait), and centring on them put the whole cockroach 0.35 m off its body and its eyes off the lamps
    scene.updateMatrixWorld(true);
    const box = new THREE.Box3().setFromObject(scene, true);
    const size = box.getSize(new THREE.Vector3());
    const s = LENGTH / size.z;
    const holder = new THREE.Group();
    holder.scale.setScalar(s);
    const c = box.getCenter(new THREE.Vector3());
    scene.position.set(0, -box.min.y, -c.z);
    holder.add(scene);
    body.add(holder);
    body.updateMatrixWorld(true);
    // the compound eyes themselves are the headlights (glossy dark by day, glowing at night)
    lamps = lightEyes(scene, carMats.headlight);
    if (!lamps) {
      // no eye patch found: lamps at the foremost head bone (`head_eyes`, between the compound eyes)
      let head: THREE.Object3D | null = null;
      const at = new THREE.Vector3();
      scene.traverse((o) => {
        if (!(o as THREE.Bone).isBone || !o.name.startsWith('head')) return;
        if (!head || o.getWorldPosition(at).z > head.getWorldPosition(new THREE.Vector3()).z) head = o;
      });
      if (head) eyes = (head as THREE.Object3D).getWorldPosition(new THREE.Vector3());
    }
  } else {
    buildStandIn(body, tinted);
  }
  if (lamps) {
    carMats.headlight.color.set('#1c1510');
    carMats.headlight.roughness = 0.15;
    carMats.headlight.metalness = 0.3;
  } else {
    // glowing spheres on the stand-in's head (or round the model's head bone)
    const eyeX = model ? 0.2 : 0.26;
    const eyeGeo = new THREE.SphereGeometry(0.09, 12, 8);
    for (const x of [eyeX, -eyeX]) {
      const eye = new THREE.Mesh(eyeGeo, carMats.headlight);
      eye.position.set(x, eyes.y, eyes.z);
      body.add(eye);
    }
    lamps = [new THREE.Vector3(eyeX, eyes.y, eyes.z), new THREE.Vector3(-eyeX, eyes.y, eyes.z)];
  }
  const base = tinted.map(liveryBase);
  const setLivery = (color: string) => {
    const liv = info.liveries.find((l) => l.swatch === color) ?? info.liveries[0];
    tinted.forEach((m, i) => applyLivery(m, base[i], liv));
  };
  setLivery(opts.bodyColor ?? info.liveries[0].swatch);

  let phase = 0;
  const last = new THREE.Vector3();
  let placed = false;
  const fwd = new THREE.Vector3(), p = new THREE.Vector3();
  const flight = flightState();
  const creature: CreatureRig = {
    update(anchor, dt, airborne = false) {
      if (wings.length) {
        // (the state is stepped every frame: left alone on the ground, the time in the air of one hop would be
        // added to the next one's; the bones are only touched while the wings are out, and once more to shut them)
        const was = flight.opened;
        flightStep(flight, info.flight, airborne, dt);
        if (was > 0 || flight.opened > 0) poseWings(wings, wingPose(info.flight, flight.opened, flight.phase));
      }
      if (!mixer) return;
      anchor.updateWorldMatrix(true, false);
      p.setFromMatrixPosition(anchor.matrixWorld);
      if (!placed) {
        last.copy(p);
        placed = true;
        return;
      }
      fwd.set(0, 0, 1).transformDirection(anchor.matrixWorld);
      const d = last.sub(p).dot(fwd) * -1;
      last.copy(p);
      // a respawn or a jump of the anchor: no step
      if (Math.abs(d) > 20) return;
      const cycles = Math.max(-MAX_CYCLES * dt, Math.min(MAX_CYCLES * dt, d / info.stride));
      phase = (((phase + cycles) % 1) + 1) % 1;
      mixer.setTime(phase * duration);
    },
    setLivery,
    get flight() {
      return flight.opened;
    },
    poseWings(opened, phase) {
      poseWings(wings, wingPose(info.flight, opened, phase));
    },
  };

  const anchors = { exhaust: new THREE.Vector3(), headlights: lamps.map((l) => l.clone().setZ(l.z + 0.1)), taillights: [] as THREE.Vector3[] };
  return { root, body, wheels, materials: carMats, headlightTargets: [], anchors, fromModel: !!model, creature };
}

type Livery = CreatureInfo['liveries'][number];
/** what a livery changes of a material, as the model has it */
export interface LiveryBase {
  color: THREE.Color;
  map: THREE.Texture | null;
  metalness: number;
  roughness: number;
}
export const liveryBase = (m: THREE.MeshStandardMaterial): LiveryBase => ({ color: m.color.clone(), map: m.map, metalness: m.metalness, roughness: m.roughness });

/**
 * One white texel that stands in for a colour texture under a plain livery, sampled as that texture is (the same
 * sampler and colour space: the material's shader stays the one it has).
 */
const blanks = new WeakMap<THREE.Texture, THREE.Texture>();
function blankLike(map: THREE.Texture) {
  let t = blanks.get(map);
  if (!t) {
    t = new THREE.DataTexture(new Uint8Array([255, 255, 255, 255]), 1, 1);
    t.name = 'livery-blank';
    t.colorSpace = map.colorSpace;
    t.wrapS = map.wrapS;
    t.wrapT = map.wrapT;
    t.magFilter = map.magFilter;
    t.minFilter = map.minFilter;
    // (a mipmap filter without mipmaps is an incomplete texture in WebGL: black)
    t.generateMipmaps = true;
    t.needsUpdate = true;
    blanks.set(map, t);
  }
  return t;
}

/**
 * Put a livery on one of the model's materials. **A material that has a colour texture keeps one**: a plain livery
 * swaps in a white texel, it never sets `map` to null. Taking the map away from a material that was already drawn
 * stopped the whole game (players' reports, v2.1.0: "the cockroach is not drawn after a change of colour"): three.js
 * 0.186 builds a shadow caster's shadow shader with a reference to the material's `map` (its alpha) and does not
 * build it again when the material changes, so the next shadow map read `null.matrix` and every frame from then on
 * threw. The same texture slot also means no shader is built for a change of livery.
 */
export function applyLivery(m: THREE.MeshStandardMaterial, b: LiveryBase, liv: Livery) {
  m.map = b.map && liv.plain ? blankLike(b.map) : b.map;
  if (liv.plain) m.color.set(liv.plain);
  else m.color.setRGB(b.color.r * (liv.gain?.[0] ?? 1), b.color.g * (liv.gain?.[1] ?? 1), b.color.b * (liv.gain?.[2] ?? 1));
  m.metalness = liv.metal ? 1 : b.metalness;
  m.roughness = liv.metal ? 0.3 : b.roughness;
}

/** the compound eyes' patch of the roach_body atlas in glTF UVs (roach_tex.py LAYOUT['eye'] = u 0.75–1, v 0–0.15, v flipped) */
const EYE_UV = { u: 0.75, v: 0.85 };

/**
 * Give the compound eyes' triangles (found by their atlas patch) the lamp material and return the eyes' centres
 * (body space, posed at the clip's start; left eye first), or null when the model has no such patch.
 */
function lightEyes(scene: THREE.Object3D, lamp: THREE.MeshStandardMaterial): THREE.Vector3[] | null {
  const sums = [new THREE.Vector3(), new THREE.Vector3()];
  const counts = [0, 0];
  const v = new THREE.Vector3();
  scene.traverse((o) => {
    const m = o as THREE.SkinnedMesh;
    if (!m.isSkinnedMesh || Array.isArray(m.material) || m.material.name !== 'roach_body') return;
    const g = m.geometry, uv = g.getAttribute('uv'), index = g.index;
    if (!uv || !index) return;
    // a triangle's UV centroid lies inside its own patch (vertices on a patch edge are shared with the neighbour's)
    const rest: number[] = [], eye: number[] = [];
    for (let t = 0; t < index.count; t += 3) {
      const a = index.getX(t), b = index.getX(t + 1), c = index.getX(t + 2);
      const u = (uv.getX(a) + uv.getX(b) + uv.getX(c)) / 3, w = (uv.getY(a) + uv.getY(b) + uv.getY(c)) / 3;
      (u > EYE_UV.u && w > EYE_UV.v ? eye : rest).push(a, b, c);
    }
    if (!eye.length) return;
    for (const i of new Set(eye)) {
      m.getVertexPosition(i, v).applyMatrix4(m.matrixWorld);
      const side = v.x > 0 ? 0 : 1;
      sums[side].add(v);
      counts[side]++;
    }
    // an own index (the loaded geometry is shared by every clone): the eyes last, as a second material group
    const geo = new THREE.BufferGeometry();
    for (const [name, attr] of Object.entries(g.attributes)) geo.setAttribute(name, attr);
    geo.setIndex([...rest, ...eye]);
    geo.addGroup(0, rest.length, 0);
    geo.addGroup(rest.length, eye.length, 1);
    geo.boundingBox = g.boundingBox;
    geo.boundingSphere = g.boundingSphere;
    m.geometry = geo;
    m.material = [m.material, lamp];
  });
  if (!counts[0] || !counts[1]) return null;
  return sums.map((s, i) => s.divideScalar(counts[i]));
}

/** Procedural cockroach (no model): shell, head and six legs; tinted like the model. */
function buildStandIn(body: THREE.Group, tinted: THREE.MeshStandardMaterial[]) {
  const shell = new THREE.MeshStandardMaterial({ color: '#7a3417', roughness: 0.35, metalness: 0.2 });
  const legMat = new THREE.MeshStandardMaterial({ color: '#4a2210', roughness: 0.6 });
  tinted.push(shell, legMat);
  const abdomen = new THREE.Mesh(new THREE.SphereGeometry(1, 20, 12).scale(0.85, 0.32, 1.6), shell);
  abdomen.position.set(0, 0.55, -0.3);
  const head = new THREE.Mesh(new THREE.SphereGeometry(1, 16, 10).scale(0.55, 0.26, 0.4), shell);
  head.position.set(0, 0.5, 1.45);
  body.add(abdomen, head);
  const leg = new THREE.CylinderGeometry(0.05, 0.035, 1.3, 6).rotateZ(Math.PI / 2.6);
  for (const z of [0.9, 0, -0.9]) {
    for (const s of [1, -1]) {
      const l = new THREE.Mesh(leg, legMat);
      l.position.set(s * 1.05, 0.3, z);
      l.scale.x = s;
      body.add(l);
    }
  }
  for (const m of body.children as THREE.Mesh[]) m.castShadow = true;
}
