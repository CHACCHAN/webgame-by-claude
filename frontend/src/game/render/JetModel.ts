import * as THREE from 'three';
import { MeshBasicNodeMaterial } from 'three/webgpu';
import { abs, clamp as clampNode, dot, mix, normalView, positionViewDirection, pow, sin, uniform, uv, vec3, vec4 } from 'three/tsl';
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js';
import type { CarSpec } from '../vehicle/carSpecs';
import { adoptMaterials, createCarMaterials, modelAnchors, type CarMaterials, type CarRig } from './CarModel';
import { clamp, damp } from '../util/math';

/**
 * The fighters: our own models (public/models/jets/<id>[-<variant>].glb, tools/blender/jets/<id>.py) or a procedural
 * stand-in while one is missing. GLB contract: metres, nose toward +Z, +X = the left wing, ground at y = 0 with the gear
 * down, origin on the ground midway between the nose wheel and the main wheels; node `body`; nose gear `gear_nose`
 * (origin at its retraction hinge) → `steer_nose` (steering about its Y) → `spin_nose` (the wheel, about X); main gears
 * `gear_l` / `gear_r` (origin at the hinge) → `spin_l` / `spin_r`; meshes `nozzle_l` / `nozzle_r` (the afterburner flame
 * at each one's aft end); optional `stab_l` / `stab_r` / `canard_l` / `canard_r` pitching about X. Lamp materials
 * navlight_red / navlight_green / navlight_white / beacon / formation / taxilight (the headlight).
 *
 * The gear retracts after the take-off (`setGear`): each leg turns by its fold (`JetInfo.gearFold`, measured on the
 * model; by default forward through 90°) and is hidden once stowed.
 */
const templates = new Map<string, THREE.Object3D>();
const loading = new Map<string, Promise<void>>();

/** model file key of a jet in a livery: the two-seaters are their own models */
export function jetModelKey(spec: CarSpec, color?: string) {
  const l = spec.jet?.liveries.find((x) => x.swatch === color);
  return l?.variant ? `${spec.id}-${l.variant}` : spec.id;
}

/** Load a jet's model (by `jetModelKey`) once; a missing file leaves the base model or the procedural stand-in. */
export function loadJetModel(key: string): Promise<void> {
  if (templates.has(key)) return Promise.resolve();
  let p = loading.get(key);
  if (!p) {
    p = (async () => {
      const { GLTFLoader } = await import('three/examples/jsm/loaders/GLTFLoader.js');
      const { MeshoptDecoder } = await import('three/examples/jsm/libs/meshopt_decoder.module.js');
      const loader = new GLTFLoader();
      loader.setMeshoptDecoder(MeshoptDecoder);
      try {
        const gltf = await loader.loadAsync(`/models/jets/${key}.glb`);
        templates.set(key, gltf.scene);
      } catch {
        // no model yet
      }
    })();
    loading.set(key, p);
  }
  return p;
}

export const jetModelReady = (key: string) => templates.has(key);

export interface JetRig {
  /** per frame: nose wheel steering and wheel spin from the sim's stand-ins, engines, the beacon */
  update(anchor: THREE.Object3D, dt: number, live?: { spool: number; afterburner: number } | null): void;
  /** landing gear: 0 = down … 1 = stowed */
  setGear(k: number): void;
  /** stabilators (and canards): + = nose-up command (rad) */
  setPitch(a: number): void;
  /** navigation, formation and taxi lights (0…1) */
  setLights(on: number): void;
  /** the nozzles' exits in the root's frame (the afterburner flames, heat) */
  readonly nozzles: { pos: THREE.Vector3; radius: number }[];
}

const _q = new THREE.Quaternion(), _v = new THREE.Vector3();
const AXIS_X = new THREE.Vector3(1, 0, 0), AXIS_Y = new THREE.Vector3(0, 1, 0);

/** the afterburner plume: a hot core, an orange sheath and shock diamonds (additive, never written to depth) */
function flameMaterial() {
  const uAb = uniform(0), uMil = uniform(0), uTime = uniform(0);
  const material = new MeshBasicNodeMaterial({ transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide, fog: false });
  // uv.y: 1 at the nozzle, 0 at the tail of the plume
  const t = clampNode(uv().y, 0, 1);
  const edge = clampNode(abs(dot(normalView, positionViewDirection)), 0, 1);
  const core = edge.mul(edge);
  const diamonds = sin(t.oneMinus().mul(28).sub(uTime.mul(3))).mul(0.35).add(0.65);
  const ab = uAb.mul(pow(t, 0.8)).mul(diamonds);
  const mil = uMil.mul(pow(t, 6));
  const hot = mix(vec3(1, 0.45, 0.12), vec3(0.75, 0.82, 1), core);
  material.colorNode = vec4(hot.mul(ab).mul(core).mul(1.6).add(vec3(1, 0.4, 0.15).mul(mil).mul(core).mul(0.5)), 1);
  return { material, uAb, uMil, uTime };
}

export function buildJet(spec: CarSpec, opts: { bodyColor?: string; procedural?: boolean } = {}): CarRig & { jet: JetRig } {
  const info = spec.jet!;
  const key = jetModelKey(spec, opts.bodyColor);
  const tpl = opts.procedural ? null : (templates.get(key) ?? templates.get(spec.id) ?? null);
  const root = new THREE.Group();
  root.name = `jet-${spec.id}`;
  let mats: CarMaterials;
  let model: THREE.Object3D;
  if (tpl) {
    model = tpl.clone(true);
    mats = adoptMaterials(model, spec, opts.bodyColor);
  } else {
    mats = createCarMaterials(spec, opts.bodyColor);
    mats.paint.clearcoat = 0.2;
    mats.paint.roughness = 0.55;
    mats.paint.metalness = 0.1;
    model = proceduralJet(spec, mats);
  }
  root.add(model);
  root.updateMatrixWorld(true);

  const node = (name: string) => model.getObjectByName(name) ?? null;
  const gears = (['gear_nose', 'gear_l', 'gear_r'] as const).map((name, k) => {
    const n = node(name);
    const fold = info.gearFold?.[(['nose', 'left', 'right'] as const)[k]];
    return n ? { node: n, base: n.quaternion.clone(), axis: new THREE.Vector3(...(fold?.axis ?? [1, 0, 0])).normalize(), angle: fold?.angle ?? -Math.PI / 2 } : null;
  });
  const steerNose = node('steer_nose');
  const steerBase = steerNose?.quaternion.clone() ?? new THREE.Quaternion();
  const spins = [node('spin_nose'), node('spin_l'), node('spin_r')];
  const surfaces = ['stab_l', 'stab_r', 'canard_l', 'canard_r'].map((n) => node(n)).filter((n): n is THREE.Object3D => !!n).map((n) => ({ node: n, base: n.quaternion.clone(), canard: n.name.startsWith('canard') }));

  // nozzles: each exit's centre and radius in the root's frame, with a plume
  const nozzles: JetRig['nozzles'] = [];
  const flames: ReturnType<typeof flameMaterial>[] = [];
  const toRoot = root.matrixWorld.clone().invert();
  for (const name of ['nozzle_l', 'nozzle_r']) {
    const n = node(name);
    if (!n) continue;
    const box = new THREE.Box3().setFromObject(n).applyMatrix4(toRoot);
    const radius = Math.max(0.2, Math.min(box.max.x - box.min.x, box.max.y - box.min.y) / 2);
    const pos = new THREE.Vector3((box.min.x + box.max.x) / 2, (box.min.y + box.max.y) / 2, box.min.z);
    nozzles.push({ pos, radius });
    const flame = flameMaterial(), mat = flame.material;
    flames.push(flame);
    const len = radius * 9;
    const plume = new THREE.Mesh(new THREE.CylinderGeometry(radius * 0.85, radius * 0.25, len, 20, 1, true).rotateX(-Math.PI / 2).translate(0, 0, -len / 2), mat);
    plume.position.copy(pos);
    plume.renderOrder = 5;
    plume.frustumCulled = false;
    root.add(plume);
  }

  // lights: the taxi lamp is the headlight (adopted by name), the rest glow at night
  const lamps: { mat: THREE.MeshStandardMaterial; beacon: boolean }[] = [];
  const seen = new Set<THREE.Material>();
  model.traverse((o) => {
    const m = o as THREE.Mesh;
    if (!m.isMesh) return;
    for (const mat of Array.isArray(m.material) ? m.material : [m.material]) {
      if (seen.has(mat)) continue;
      seen.add(mat);
      if (/^(navlight_|beacon|formation)/.test(mat.name)) lamps.push({ mat: mat as THREE.MeshStandardMaterial, beacon: mat.name.startsWith('beacon') });
      if (mat.name === 'taxilight') {
        const sm = mat as THREE.MeshStandardMaterial;
        sm.emissive = new THREE.Color('#fff4e0');
        // the visual's headlight level drives it through the shared headlight material
        m.material = Array.isArray(m.material) ? m.material.map((x) => (x === mat ? mats.headlight : x)) : mats.headlight;
      }
    }
  });
  let lightOn = 0, time = 0;

  const anchors = modelAnchors(root, mats, spec);
  // the sim's four wheel stand-ins (nose pair, mains), read for the nose steer and the spin
  const standIns = [0, 1, 2, 3].map(() => {
    const pivot = new THREE.Group(), spin = new THREE.Group();
    pivot.add(spin);
    return { pivot, spin };
  });
  let gearK = 0, spool = 0, ab = 0;
  const rig: JetRig = {
    nozzles,
    update(_anchor, dt, live) {
      time += dt;
      if (steerNose) steerNose.quaternion.copy(steerBase).multiply(_q.setFromAxisAngle(AXIS_Y, standIns[0].pivot.rotation.y));
      if (spins[0]) spins[0].rotation.x = standIns[0].spin.rotation.x;
      if (spins[1]) spins[1].rotation.x = standIns[2].spin.rotation.x;
      if (spins[2]) spins[2].rotation.x = standIns[3].spin.rotation.x;
      if (live) {
        spool = damp(spool, live.spool, 6, dt);
        ab = damp(ab, live.afterburner, 10, dt);
      }
      for (const f of flames) {
        f.uAb.value = ab * (0.9 + 0.1 * Math.sin(time * 37));
        f.uMil.value = spool * (1 - ab);
        f.uTime.value = time;
      }
      // the anti-collision beacons flash about once a second
      for (const l of lamps) l.mat.emissiveIntensity = l.beacon ? (time % 1.1 < 0.12 ? 6 : 0) : 3 * lightOn;
    },
    setGear(k) {
      gearK = clamp(k, 0, 1);
      const e = gearK * gearK * (3 - 2 * gearK);
      for (const g of gears) {
        if (!g) continue;
        g.node.quaternion.copy(g.base).multiply(_q.setFromAxisAngle(g.axis, g.angle * e));
        g.node.visible = gearK < 0.98;
      }
    },
    setPitch(a) {
      for (const s of surfaces) s.node.quaternion.copy(s.base).multiply(_q.setFromAxisAngle(AXIS_X, (s.canard ? 1 : -1) * a));
    },
    setLights(on) {
      lightOn = on;
    },
  };
  rig.setGear(0);
  void _v;
  const body = new THREE.Group();
  const target = new THREE.Object3D();
  target.position.set(0, 0, 40);
  root.add(target);
  return { root, body, wheels: standIns, materials: mats, headlightTargets: [target], anchors, fromModel: !!tpl, jet: rig };
}

// ------------------------------------------------------------------------------------------------ the stand-in
// Until our own models are in place the fighters are drawn from their published dimensions: a lofted fuselage,
// intakes and engine nacelles, wings, fins and tailplanes as tapered panels, canopy, nozzles and gear. Stations are
// metres aft of the nose tip (`d`), heights above the ground with the gear down.

interface Section { d: number; y: number; w: number; h: number; e?: number; x?: number }

/** A body lofted through elliptic (e = 2) to boxy (e ≥ 4) sections; both ends are closed. */
function loft(zNose: number, sections: Section[], seg = 18): THREE.BufferGeometry {
  const pos: number[] = [], idx: number[] = [];
  const ring = (s: Section) => {
    const e = 2 / (s.e ?? 2);
    for (let k = 0; k < seg; k++) {
      const a = (k / seg) * Math.PI * 2, c = Math.cos(a), sn = Math.sin(a);
      pos.push((s.x ?? 0) + s.w * Math.sign(c) * Math.pow(Math.abs(c), e), s.y + s.h * Math.sign(sn) * Math.pow(Math.abs(sn), e), zNose - s.d);
    }
  };
  sections.forEach(ring);
  for (let i = 0; i + 1 < sections.length; i++) for (let k = 0; k < seg; k++) {
    const a = i * seg + k, b = i * seg + ((k + 1) % seg), c = a + seg, d2 = b + seg;
    idx.push(a, c, b, b, c, d2);
  }
  const cap = (i: number, flip: boolean) => {
    const s = sections[i], centre = pos.length / 3;
    pos.push(s.x ?? 0, s.y, zNose - s.d);
    for (let k = 0; k < seg; k++) {
      const a = i * seg + k, b = i * seg + ((k + 1) % seg);
      if (flip) idx.push(centre, a, b);
      else idx.push(centre, b, a);
    }
  };
  cap(0, true);
  cap(sections.length - 1, false);
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setIndex(idx);
  g.computeVertexNormals();
  return g;
}

interface Station { u: number; le: number; te: number; t: number; v?: number }

/**
 * A wing, fin or tailplane: a tapered panel between two stations (u = out along the span, le / te = the leading and
 * trailing edge as metres aft of the nose, t = thickness, v = rise), thickest at a third of the chord. `frame` maps
 * (u, v) to the model's (x, y): a wing's u is x, a fin's is y.
 */
function panel(zNose: number, root: Station, tip: Station, frame: (u: number, v: number) => [number, number], flip: boolean): THREE.BufferGeometry {
  const pts: number[] = [];
  for (const s of [root, tip]) {
    const mid = s.le + (s.te - s.le) * 0.33, v = s.v ?? 0;
    for (const [d, dv] of [[s.le, 0], [mid, s.t / 2], [s.te, 0], [mid, -s.t / 2]] as const) {
      const [x, y] = frame(s.u, v + dv);
      pts.push(x, y, zNose - d);
    }
  }
  // quads: over the top (front, rear), under the bottom, the tip and root ends
  const quads = [[0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7], [4, 5, 6, 7], [3, 2, 1, 0]];
  const pos: number[] = [];
  for (const q of quads) for (const k of flip ? [0, 2, 1, 0, 3, 2] : [0, 1, 2, 0, 2, 3]) pos.push(pts[q[k] * 3], pts[q[k] * 3 + 1], pts[q[k] * 3 + 2]);
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.computeVertexNormals();
  return g;
}

interface Airframe {
  /** nose tip ahead of the root (m), height of the fuselage's axis */
  zNose: number;
  axis: number;
  fuselage: Section[];
  /** a darker radome over the first metres */
  radome: number;
  /** the canopy: from / to (m aft of the nose), half width, height over the axis */
  canopy: { from: number; to: number; w: number; top: number };
  /** intake and engine nacelle of one side (mirrored), and the nozzle's exit radius */
  nacelle: Section[];
  nozzle: { x: number; y: number; d: number; radius: number; length: number };
  /** wing panels of one side (root → tip), each mirrored */
  wings: [Station, Station][];
  wingY: number;
  fin: { x: number; base: number; cant: number; root: Station; tip: Station };
  stab: { x: number; y: number; root: Station; tip: Station };
  canard?: { x: number; y: number; root: Station; tip: Station };
  /** tail booms beside the nozzles (one side; the Su-47's are of unequal length) */
  booms: { x: number; y: number; from: number; to: [number, number]; w: number; h: number }[];
  /** light leading edges (the Su-47's white ones): strips along the wing's leading edge */
  edges: boolean;
}

function airframe(spec: CarSpec): Airframe {
  const L = spec.jet!.figures.length, half = spec.jet!.figures.span / 2;
  if (spec.id === 'su47') {
    // 22.6 m long, 16.7 m span, 6.4 m high: the nose gear 5.6 m aft of the nose
    const zNose = 5.6 + spec.wheelbase / 2, axis = 2.35;
    return {
      zNose, axis, radome: 2.6,
      fuselage: [
        { d: 0, y: axis - 0.15, w: 0.03, h: 0.03 }, { d: 1.0, y: axis - 0.1, w: 0.36, h: 0.36 }, { d: 2.8, y: axis, w: 0.7, h: 0.72 },
        { d: 5.0, y: axis + 0.05, w: 0.86, h: 0.95 }, { d: 7.6, y: axis + 0.1, w: 1.0, h: 1.0, e: 2.6 }, { d: 10.5, y: axis + 0.2, w: 1.5, h: 0.7, e: 3 },
        { d: 15.0, y: axis + 0.25, w: 1.7, h: 0.55, e: 3 }, { d: 19.2, y: axis + 0.25, w: 1.2, h: 0.32, e: 3 }, { d: 21.0, y: axis + 0.25, w: 0.5, h: 0.14, e: 3 },
      ],
      canopy: { from: 3.5, to: 7.4, w: 0.52, top: 1.55 },
      nacelle: [
        { d: 8.6, x: 1.3, y: axis - 0.62, w: 0.6, h: 0.5, e: 6 }, { d: 10.6, x: 1.3, y: axis - 0.6, w: 0.68, h: 0.62, e: 5 }, { d: 14.0, x: 1.3, y: axis - 0.45, w: 0.72, h: 0.72, e: 2.6 },
        { d: 18.4, x: 1.3, y: axis - 0.3, w: 0.7, h: 0.7 }, { d: 19.4, x: 1.3, y: axis - 0.3, w: 0.62, h: 0.62 },
      ],
      nozzle: { x: 1.3, y: axis - 0.3, d: 19.3, radius: 0.5, length: 1.3 },
      // a short swept-back inner panel, then the wing swept forward to the tip
      wings: [
        [{ u: 1.2, le: 8.7, te: 16.2, t: 0.3 }, { u: 2.9, le: 10.9, te: 16.0, t: 0.34 }],
        [{ u: 2.9, le: 10.9, te: 16.0, t: 0.34 }, { u: half, le: 8.9, te: 10.5, t: 0.08, v: 0.12 }],
      ],
      wingY: axis + 0.2,
      fin: { x: 2.0, base: axis + 0.35, cant: 0.12, root: { u: 0, le: 15.6, te: 19.6, t: 0.2 }, tip: { u: 6.4 - (axis + 0.35), le: 18.4, te: 19.9, t: 0.06 } },
      stab: { x: 2.1, y: axis + 0.15, root: { u: 0, le: 18.0, te: 21.0, t: 0.14 }, tip: { u: 1.9, le: 20.1, te: 21.3, t: 0.05 } },
      canard: { x: 1.25, y: axis + 0.46, root: { u: 0, le: 6.6, te: 9.0, t: 0.12 }, tip: { u: 2.5, le: 8.7, te: 9.5, t: 0.04 } },
      booms: [{ x: 2.1, y: axis + 0.15, from: 16.5, to: [L, L - 1.5], w: 0.24, h: 0.2 }],
      edges: true,
    };
  }
  // the Eagle: 19.43 m long, 13.05 m span, 5.63 m high: the nose gear 5.0 m aft of the nose
  const zNose = 5.0 + spec.wheelbase / 2, axis = 2.1;
  return {
    zNose, axis, radome: 2.2,
    fuselage: [
      { d: 0, y: axis - 0.12, w: 0.03, h: 0.03 }, { d: 0.9, y: axis - 0.08, w: 0.34, h: 0.34 }, { d: 2.3, y: axis, w: 0.6, h: 0.62 },
      { d: 4.2, y: axis + 0.05, w: 0.74, h: 0.9 }, { d: 6.4, y: axis + 0.12, w: 0.85, h: 1.02, e: 2.6 }, { d: 9.5, y: axis + 0.22, w: 1.25, h: 0.82, e: 3 },
      { d: 14.0, y: axis + 0.22, w: 1.45, h: 0.66, e: 3 }, { d: 17.6, y: axis + 0.15, w: 1.5, h: 0.5, e: 3 }, { d: 18.3, y: axis + 0.12, w: 1.45, h: 0.3, e: 3 },
    ],
    canopy: { from: 3.0, to: 6.9, w: 0.5, top: 1.72 },
    // the intakes' lips rake forward at the top; the trunks run back into the engine bays
    nacelle: [
      { d: 5.6, x: 1.32, y: axis + 0.1, w: 0.5, h: 0.56, e: 7 }, { d: 6.4, x: 1.32, y: axis - 0.08, w: 0.52, h: 0.74, e: 7 }, { d: 10.5, x: 1.3, y: axis - 0.12, w: 0.56, h: 0.72, e: 5 },
      { d: 14.5, x: 1.0, y: axis - 0.12, w: 0.66, h: 0.66, e: 2.6 }, { d: 17.3, x: 0.86, y: axis - 0.1, w: 0.64, h: 0.64 }, { d: 17.9, x: 0.86, y: axis - 0.1, w: 0.58, h: 0.58 },
    ],
    nozzle: { x: 0.86, y: axis - 0.1, d: 17.8, radius: 0.48, length: 1.25 },
    // 45° at the leading edge, a straight trailing edge, the tip cut off at an angle
    wings: [
      [{ u: 1.75, le: 7.3, te: 13.7, t: 0.34 }, { u: half - 0.7, le: 11.4, te: 13.95, t: 0.1, v: -0.08 }],
      [{ u: half - 0.7, le: 11.4, te: 13.95, t: 0.1, v: -0.08 }, { u: half, le: 12.6, te: 13.9, t: 0.05, v: -0.09 }],
    ],
    wingY: axis + 0.62,
    fin: { x: 1.6, base: axis + 0.5, cant: 0, root: { u: 0, le: 13.5, te: 17.7, t: 0.18 }, tip: { u: 5.63 - (axis + 0.5), le: 16.0, te: 17.5, t: 0.06 } },
    stab: { x: 1.65, y: axis + 0.05, root: { u: 0, le: 15.1, te: 18.7, t: 0.14 }, tip: { u: 2.65, le: 18.2, te: L, t: 0.05 } },
    booms: [{ x: 1.62, y: axis + 0.22, from: 13.6, to: [18.9, 18.9], w: 0.2, h: 0.3 }],
    edges: false,
  };
}

/** A stand-in fighter: fuselage, intakes, wings, twin fins, tailplanes, canopy, gear, nozzles (see the contract above). */
function proceduralJet(spec: CarSpec, mats: CarMaterials) {
  const j = spec.jet!;
  const A = airframe(spec);
  const root = new THREE.Group();
  const body = new THREE.Group();
  body.name = 'body';
  root.add(body);
  const camo2 = new THREE.MeshStandardMaterial({ color: j.camo[1], roughness: 0.62, metalness: 0.1 });
  const metal = new THREE.MeshStandardMaterial({ color: '#57534f', metalness: 0.9, roughness: 0.45, side: THREE.DoubleSide });
  const dark = new THREE.MeshStandardMaterial({ color: '#0c0d0f', roughness: 0.9 });
  const edge = new THREE.MeshStandardMaterial({ color: '#d4d4cc', roughness: 0.6 });
  const add = (parent: THREE.Object3D, geo: THREE.BufferGeometry, m: THREE.Material, x = 0, y = 0, z = 0, name?: string) => {
    const mesh = new THREE.Mesh(geo, m);
    mesh.position.set(x, y, z);
    mesh.castShadow = true;
    if (name) mesh.name = name;
    parent.add(mesh);
    return mesh;
  };
  const z = (d: number) => A.zNose - d;

  // fuselage; the radome is the same shape again, a hair larger, in the second tone
  add(body, loft(A.zNose, A.fuselage), mats.paint);
  const nose = A.fuselage.filter((s) => s.d <= A.radome + 0.01).map((s) => ({ ...s, w: s.w * 1.012, h: s.h * 1.012 }));
  const at = (d: number): Section => {
    const i = Math.max(1, A.fuselage.findIndex((s) => s.d >= d)), a = A.fuselage[i - 1], b = A.fuselage[i], k = (d - a.d) / (b.d - a.d);
    return { d, y: a.y + (b.y - a.y) * k, w: (a.w + (b.w - a.w) * k) * 1.012, h: (a.h + (b.h - a.h) * k) * 1.012 };
  };
  if (nose[nose.length - 1].d < A.radome - 0.01) nose.push(at(A.radome));
  add(body, loft(A.zNose, nose), camo2);
  // the canopy: a long bubble, its frame the fuselage under it
  const c = A.canopy, len = c.to - c.from;
  add(body, new THREE.SphereGeometry(1, 18, 10, 0, Math.PI * 2, 0, Math.PI / 2).scale(c.w, c.top - 0.82, len / 2), mats.glass, 0, A.axis + 0.8, z((c.from + c.to) / 2 - len * 0.04));
  // intakes and nacelles, the intake's mouth dark
  for (const s of [1, -1]) {
    const side = A.nacelle.map((q) => ({ ...q, x: (q.x ?? 0) * s }));
    add(body, loft(A.zNose, side), mats.paint);
    const lip = side[0];
    add(body, new THREE.BoxGeometry(lip.w * 1.7, lip.h * 1.7, 0.06), dark, lip.x, lip.y, z(lip.d) + 0.02);
    for (const b of A.booms) {
      const to = b.to[s > 0 ? 0 : 1];
      add(body, new THREE.BoxGeometry(b.w * 2, b.h * 2, to - b.from), mats.paint, b.x * s, b.y, z((b.from + to) / 2));
    }
  }
  // wings (and their light leading edges), fins
  for (const s of [1, -1]) {
    const wing = (u: number, v: number): [number, number] => [u * s, A.wingY + v];
    for (const [a, b] of A.wings) {
      add(body, panel(A.zNose, a, b, wing, s > 0), mats.paint);
      if (A.edges) add(body, panel(A.zNose, { ...a, te: a.le + 0.28, t: a.t * 0.5, le: a.le - 0.03 }, { ...b, te: b.le + 0.2, t: b.t * 0.5, le: b.le - 0.03 }, (u, v) => [u * s, A.wingY + v + 0.012], s > 0), edge);
    }
    const f = A.fin;
    const fin = (u: number, v: number): [number, number] => [(f.x + u * Math.sin(f.cant)) * s + v * s, f.base + u * Math.cos(f.cant)];
    add(body, panel(A.zNose, f.root, f.tip, fin, s < 0), mats.paint);
    // the fin's cap in the second tone
    const k = 0.86, cap: Station = { u: f.tip.u * k, le: f.root.le + (f.tip.le - f.root.le) * k, te: f.root.te + (f.tip.te - f.root.te) * k, t: f.root.t + (f.tip.t - f.root.t) * k + 0.02 };
    add(body, panel(A.zNose, cap, { ...f.tip, t: f.tip.t + 0.02 }, fin, s < 0), A.edges ? edge : camo2);
  }
  // tailplanes (all-moving) and canards: each on a pivot at a third of its root chord
  const moving = (name: string, def: NonNullable<Airframe['canard']>, s: number) => {
    const pivotD = def.root.le + (def.root.te - def.root.le) * 0.4;
    const pivot = new THREE.Group();
    pivot.name = name;
    pivot.position.set(def.x * s, def.y, z(pivotD));
    body.add(pivot);
    const g = panel(A.zNose, def.root, def.tip, (u, v) => [u * s, v], s > 0).translate(0, 0, -z(pivotD));
    add(pivot, g, mats.paint);
  };
  for (const s of [1, -1]) {
    moving(s > 0 ? 'stab_l' : 'stab_r', A.stab, s);
    if (A.canard) moving(s > 0 ? 'canard_l' : 'canard_r', A.canard, s);
  }
  // nozzles: the petals narrowing to the exit, dark inside (`nozzle_*`: the rig hangs the plume on its aft end)
  const n = A.nozzle;
  for (const [s, name] of [[1, 'nozzle_l'], [-1, 'nozzle_r']] as const) {
    add(body, new THREE.CylinderGeometry(n.radius, n.radius * 1.28, n.length, 18, 1, true).rotateX(-Math.PI / 2), metal, n.x * s, n.y, z(n.d + n.length / 2), name);
    add(body, new THREE.CircleGeometry(n.radius * 1.2, 18), dark, n.x * s, n.y, z(n.d + 0.15)).rotation.y = Math.PI;
  }
  // lamps: wing tips, the fins' tops, the beacon on the spine
  const lamp = (name: string, color: string, x: number, y: number, d: number, r = 0.09) => {
    const m = new THREE.MeshStandardMaterial({ color, emissive: color, emissiveIntensity: 0 });
    m.name = name;
    add(body, new THREE.SphereGeometry(r, 8, 6), m, x, y, z(d));
  };
  const tip = A.wings[A.wings.length - 1][1];
  lamp('navlight_red', '#ff2a1a', tip.u, A.wingY + (tip.v ?? 0), tip.le + 0.3);
  lamp('navlight_green', '#2aff5a', -tip.u, A.wingY + (tip.v ?? 0), tip.le + 0.3);
  lamp('navlight_white', '#ffffff', A.fin.x + A.fin.tip.u * Math.sin(A.fin.cant), A.fin.base + A.fin.tip.u * Math.cos(A.fin.cant), A.fin.tip.te);
  lamp('beacon', '#ff3020', 0, A.axis + 1.0, (A.canopy.to + A.fin.root.le) / 2, 0.11);

  // the gear: nose leg (steering; the Su-47's has two wheels), two main legs. Each hangs from its hinge under the belly
  const r = spec.wheelRadius, rn = spec.frontWheelRadius ?? r;
  const leg = (name: string, spinName: string, x: number, zAt: number, hinge: number, radius: number, steer: boolean) => {
    const g = new THREE.Group();
    g.name = name;
    g.position.set(x, hinge, zAt);
    body.add(g);
    let parent: THREE.Object3D = g;
    if (steer) {
      const st = new THREE.Group();
      st.name = 'steer_nose';
      g.add(st);
      parent = st;
    }
    add(parent, new THREE.CylinderGeometry(0.075, 0.095, hinge - radius, 10), mats.chrome, 0, -(hinge - radius) / 2, 0);
    // the drag brace and the door hanging beside the leg
    add(parent, new THREE.CylinderGeometry(0.04, 0.04, (hinge - radius) * 0.8, 6).rotateX(0.5), mats.chrome, 0, -(hinge - radius) * 0.42, -0.24);
    add(parent, new THREE.BoxGeometry(0.03, (hinge - radius) * 0.62, 0.7), mats.paint, (x >= 0 ? 1 : -1) * (steer ? 0.3 : 0.34), -(hinge - radius) * 0.34, 0);
    const spin = new THREE.Group();
    spin.name = spinName;
    spin.position.set(0, radius - hinge, 0);
    parent.add(spin);
    const twin = steer && (spec.frontTrack ?? 0) > 0.45 ? (spec.frontTrack ?? 0) / 2 : 0;
    for (const dx of twin ? [-twin, twin] : [0]) {
      const tyre = new THREE.Mesh(new THREE.CylinderGeometry(radius, radius, radius * 0.56, 18).rotateZ(Math.PI / 2), mats.tire);
      const hub = new THREE.Mesh(new THREE.CylinderGeometry(radius * 0.55, radius * 0.55, radius * 0.58, 12).rotateZ(Math.PI / 2), mats.rim);
      tyre.position.x = hub.position.x = dx;
      tyre.castShadow = true;
      spin.add(tyre, hub);
    }
    if (steer) {
      const m = new THREE.MeshStandardMaterial({ color: '#fffbe8' });
      m.name = 'taxilight';
      add(parent, new THREE.SphereGeometry(0.11, 10, 8), m, 0, -(hinge - radius) * 0.45, 0.16);
    }
  };
  const belly = A.axis - 0.7;
  leg('gear_nose', 'spin_nose', 0, spec.wheelbase / 2, belly, rn, true);
  leg('gear_l', 'spin_l', spec.track / 2, -spec.wheelbase / 2, belly, r, false);
  leg('gear_r', 'spin_r', -spec.track / 2, -spec.wheelbase / 2, belly, r, false);
  return root;
}

/**
 * Aircraft standing on an apron (scenery: no rig, no lights, one mesh for all of them): the stand-in shapes in
 * their first livery's colours, as vertex colours.
 */
export function parkedJets(spots: { position: THREE.Vector3; heading: number; id: string }[], specOf: (id: string) => CarSpec | undefined): THREE.Object3D | null {
  const parts: THREE.BufferGeometry[] = [];
  const cache = new Map<string, THREE.BufferGeometry>();
  for (const spot of spots) {
    const spec = specOf(spot.id);
    if (!spec?.jet) continue;
    let flat = cache.get(spot.id);
    if (!flat) {
      const model = proceduralJet(spec, createCarMaterials(spec));
      model.updateMatrixWorld(true);
      const list: THREE.BufferGeometry[] = [];
      model.traverse((o) => {
        const m = o as THREE.Mesh;
        if (!m.isMesh) return;
        const mat = m.material as THREE.MeshStandardMaterial;
        // (lamps and the taxi light are too small to matter from the course)
        if (/^(navlight_|beacon|taxilight)/.test(mat.name)) return;
        const g = (m.geometry.index ? m.geometry.toNonIndexed() : m.geometry.clone()).applyMatrix4(m.matrixWorld);
        for (const name of Object.keys(g.attributes)) if (name !== 'position' && name !== 'normal') g.deleteAttribute(name);
        const count = g.attributes.position.count, col = new Float32Array(count * 3);
        const tone = mat.color.clone();
        for (let i = 0; i < count; i++) col.set([tone.r, tone.g, tone.b], i * 3);
        g.setAttribute('color', new THREE.BufferAttribute(col, 3));
        list.push(g);
      });
      flat = mergeGeometries(list)!;
      cache.set(spot.id, flat);
    }
    parts.push(flat.clone().rotateY(spot.heading).translate(spot.position.x, spot.position.y, spot.position.z));
  }
  if (!parts.length) return null;
  const mesh = new THREE.Mesh(mergeGeometries(parts)!, new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.6, metalness: 0.1 }));
  mesh.name = 'parked-aircraft';
  return mesh;
}
