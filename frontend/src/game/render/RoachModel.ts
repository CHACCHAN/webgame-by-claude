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
    model = { scene: gltf.scene, clip: gltf.animations[0] ?? null };
  } catch (err) {
    console.warn('cockroach model not loaded, using the procedural body', err);
  }
}

/** overall length the model is scaled to, antennae and hind legs included (m): the body (head to wing tips) is 3.4 m */
const LENGTH = 6.76;
/** most leg cycles per second (beyond it the gait would strobe at 60 fps) */
const MAX_CYCLES = 9;

export interface CreatureRig {
  /** run the legs by the distance the anchor moved since the last call */
  update(anchor: THREE.Object3D, dt: number): void;
  setLivery(color: string): void;
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
  let duration = 1;
  let eyes = new THREE.Vector3(0, 0.55, 1.6);
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
    if (model.clip) {
      mixer = new THREE.AnimationMixer(scene);
      mixer.clipAction(model.clip).play();
      duration = model.clip.duration || 1;
      mixer.setTime(0);
    }
    // scale to size, centred across and along, feet on the ground (posed bounds: the skinning applied)
    scene.updateMatrixWorld(true);
    const box = new THREE.Box3().setFromObject(scene, true);
    const size = box.getSize(new THREE.Vector3());
    const s = LENGTH / size.z;
    const holder = new THREE.Group();
    holder.scale.setScalar(s);
    const c = box.getCenter(new THREE.Vector3());
    scene.position.set(-c.x, -box.min.y, -c.z);
    holder.add(scene);
    body.add(holder);
    // the eyes: at the foremost head bone (`head_eyes`, between the compound eyes)
    body.updateMatrixWorld(true);
    let head: THREE.Object3D | null = null;
    const at = new THREE.Vector3();
    scene.traverse((o) => {
      if (!(o as THREE.Bone).isBone || !o.name.startsWith('head')) return;
      if (!head || o.getWorldPosition(at).z > head.getWorldPosition(new THREE.Vector3()).z) head = o;
    });
    if (head) eyes = (head as THREE.Object3D).getWorldPosition(new THREE.Vector3());
  } else {
    buildStandIn(body, tinted);
  }
  // eyes glow as headlights at night (the beams start there): on the compound eyes, ±0.2 m
  const eyeX = model ? 0.2 : 0.26;
  const eyeGeo = new THREE.SphereGeometry(0.09, 12, 8);
  for (const x of [eyeX, -eyeX]) {
    const eye = new THREE.Mesh(eyeGeo, carMats.headlight);
    eye.position.set(x, eyes.y, eyes.z);
    body.add(eye);
  }
  const base = tinted.map((m) => ({ color: m.color.clone(), map: m.map, metalness: m.metalness, roughness: m.roughness }));
  const setLivery = (color: string) => {
    const liv = info.liveries.find((l) => l.swatch === color) ?? info.liveries[0];
    tinted.forEach((m, i) => {
      const b = base[i];
      const map = liv.plain ? null : b.map;
      if (m.map !== map) m.needsUpdate = true;
      m.map = map;
      if (liv.plain) m.color.set(liv.plain);
      else m.color.setRGB(b.color.r * (liv.gain?.[0] ?? 1), b.color.g * (liv.gain?.[1] ?? 1), b.color.b * (liv.gain?.[2] ?? 1));
      m.metalness = liv.metal ? 1 : b.metalness;
      m.roughness = liv.metal ? 0.3 : b.roughness;
    });
  };
  setLivery(opts.bodyColor ?? info.liveries[0].swatch);

  let phase = 0;
  const last = new THREE.Vector3();
  let placed = false;
  const fwd = new THREE.Vector3(), p = new THREE.Vector3();
  const creature: CreatureRig = {
    update(anchor, dt) {
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
  };

  const anchors = { exhaust: new THREE.Vector3(), headlights: [new THREE.Vector3(eyeX, eyes.y, eyes.z + 0.1), new THREE.Vector3(-eyeX, eyes.y, eyes.z + 0.1)], taillights: [] as THREE.Vector3[] };
  return { root, body, wheels, materials: carMats, headlightTargets: [], anchors, fromModel: !!model, creature };
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
