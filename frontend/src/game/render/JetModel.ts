import * as THREE from 'three';
import { MeshBasicNodeMaterial } from 'three/webgpu';
import { abs, clamp as clampNode, dot, mix, normalView, positionViewDirection, pow, sin, uniform, uv, vec3, vec4 } from 'three/tsl';
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

/** A stand-in fighter (until our model is in place): fuselage, intakes, wings, twin fins, tailplanes, canopy, gear, nozzles. */
function proceduralJet(spec: CarSpec, mats: CarMaterials) {
  const j = spec.jet!;
  const root = new THREE.Group();
  const body = new THREE.Group();
  body.name = 'body';
  root.add(body);
  const L = j.figures.length;
  const span = j.figures.span;
  const forward = spec.id === 'su47';
  const belly = (spec.clearance ?? 1) + 0.2;
  const yAxis = belly + 0.9;
  const camo2 = new THREE.MeshStandardMaterial({ color: j.camo[1], roughness: 0.6 });
  const metal = new THREE.MeshStandardMaterial({ color: '#7a7570', metalness: 1, roughness: 0.4 });
  const add = (parent: THREE.Object3D, geo: THREE.BufferGeometry, m: THREE.Material, x: number, y: number, z: number, name?: string) => {
    const mesh = new THREE.Mesh(geo, m);
    mesh.position.set(x, y, z);
    mesh.castShadow = true;
    if (name) mesh.name = name;
    parent.add(mesh);
    return mesh;
  };
  const tail = -L / 2 + spec.wheelbase * 0.0;
  // fuselage and nose cone (the root sits midway between the nose wheel and the mains)
  const zMid = -spec.comForward * 0.2;
  add(body, new THREE.CylinderGeometry(0.95, 1.1, L * 0.62, 18).rotateX(Math.PI / 2), mats.paint, 0, yAxis, zMid - L * 0.05);
  add(body, new THREE.ConeGeometry(0.95, L * 0.22, 18).rotateX(Math.PI / 2), mats.paint, 0, yAxis, zMid + L * 0.36);
  // intakes and the engine bay
  for (const s of [1, -1]) add(body, new THREE.BoxGeometry(1.0, 1.3, L * 0.45), mats.paint, s * 1.35, yAxis - 0.1, zMid - L * 0.08);
  // the canopy
  add(body, new THREE.SphereGeometry(0.62, 16, 10, 0, Math.PI * 2, 0, Math.PI / 2).scale(1, 0.9, 3.0), mats.glass, 0, yAxis + 0.75, zMid + L * 0.2);
  // wings: a flat planform (the Su-47's swept forward)
  const wing = new THREE.Shape();
  const root0 = L * 0.28, tipChord = 1.4, half = span / 2;
  const sweep = forward ? -2.2 : 4.4;
  wing.moveTo(0, root0 / 2);
  wing.lineTo(half, root0 / 2 - sweep - (forward ? 0 : 0));
  wing.lineTo(half, root0 / 2 - sweep - tipChord);
  wing.lineTo(0, -root0 / 2);
  wing.closePath();
  const wingGeo = new THREE.ExtrudeGeometry(wing, { depth: 0.12, bevelEnabled: false }).rotateX(Math.PI / 2);
  for (const s of [1, -1]) {
    const w = add(body, wingGeo, mats.paint, 0, yAxis + 0.05, zMid - L * 0.12);
    w.scale.x = s;
  }
  add(body, new THREE.BoxGeometry(span * 0.3, 0.13, 2.2), camo2, span * 0.18, yAxis + 0.12, zMid - L * 0.14);
  // twin fins
  for (const s of [1, -1]) {
    const fin = new THREE.Shape();
    fin.moveTo(0, 0);
    fin.lineTo(3.4, 0);
    fin.lineTo(1.6, 3.1);
    fin.lineTo(0.6, 3.1);
    fin.closePath();
    const g = new THREE.ExtrudeGeometry(fin, { depth: 0.1, bevelEnabled: false }).rotateY(-Math.PI / 2);
    const mesh = add(body, g, mats.paint, s * 1.3, yAxis + 0.4, tail + 1.2);
    mesh.rotation.z = s * 0.15;
  }
  // tailplanes (stabilators), canards on the Su-47
  for (const [s, name] of [[1, 'stab_l'], [-1, 'stab_r']] as const) {
    const pivot = new THREE.Group();
    pivot.name = name;
    pivot.position.set(s * 2.0, yAxis, tail + 1.6);
    body.add(pivot);
    add(pivot, new THREE.BoxGeometry(3.2, 0.08, 2.4), mats.paint, s * 1.5, 0, -0.6);
    if (forward) {
      const c = new THREE.Group();
      c.name = s > 0 ? 'canard_l' : 'canard_r';
      c.position.set(s * 1.6, yAxis + 0.3, zMid + L * 0.18);
      body.add(c);
      add(c, new THREE.BoxGeometry(2.2, 0.06, 1.4), mats.paint, s * 1.0, 0, 0);
    }
  }
  // nozzles
  for (const [s, name] of [[1, 'nozzle_l'], [-1, 'nozzle_r']] as const) {
    add(body, new THREE.CylinderGeometry(0.55, 0.62, 1.4, 16, 1, true).rotateX(Math.PI / 2), metal, s * 0.75, yAxis - 0.1, tail + 0.6, name);
  }
  // lamps: wing tips, tail, the taxi lamp on the nose gear
  const lamp = (name: string, color: string, x: number, y: number, z: number) => {
    const m = new THREE.MeshStandardMaterial({ color, emissive: color, emissiveIntensity: 0 });
    m.name = name;
    add(body, new THREE.SphereGeometry(0.09, 8, 6), m, x, y, z);
  };
  lamp('navlight_red', '#ff2a1a', half, yAxis + 0.05, zMid - L * 0.12 - (forward ? -2.2 : 4.4) * 0.9);
  lamp('navlight_green', '#2aff5a', -half, yAxis + 0.05, zMid - L * 0.12 - (forward ? -2.2 : 4.4) * 0.9);
  lamp('navlight_white', '#ffffff', 0, yAxis + 0.2, tail);
  lamp('beacon', '#ff3020', 0, yAxis + 1.0, zMid);
  // the gear: nose leg (steering), two main legs
  const r = spec.wheelRadius, rn = spec.frontWheelRadius ?? r;
  const leg = (name: string, spinName: string, x: number, z: number, radius: number, steer: boolean) => {
    const g = new THREE.Group();
    g.name = name;
    g.position.set(x, belly, z);
    body.add(g);
    let parent: THREE.Object3D = g;
    if (steer) {
      const s = new THREE.Group();
      s.name = 'steer_nose';
      g.add(s);
      parent = s;
    }
    add(parent, new THREE.CylinderGeometry(0.09, 0.09, belly - radius, 8), mats.chrome, 0, -(belly - radius) / 2, 0);
    const spin = new THREE.Group();
    spin.name = spinName;
    spin.position.set(0, radius - belly, 0);
    parent.add(spin);
    spin.add(new THREE.Mesh(new THREE.CylinderGeometry(radius, radius, radius * 0.6, 16).rotateZ(Math.PI / 2), mats.tire));
    spin.add(new THREE.Mesh(new THREE.CylinderGeometry(radius * 0.6, radius * 0.6, radius * 0.62, 12).rotateZ(Math.PI / 2), mats.rim));
    if (steer) {
      const m = new THREE.MeshStandardMaterial({ color: '#fffbe8' });
      m.name = 'taxilight';
      add(parent, new THREE.SphereGeometry(0.1, 8, 6), m, 0, -0.35, 0.2);
    }
  };
  leg('gear_nose', 'spin_nose', 0, spec.wheelbase / 2, rn, true);
  leg('gear_l', 'spin_l', spec.track / 2, -spec.wheelbase / 2, r, false);
  leg('gear_r', 'spin_r', -spec.track / 2, -spec.wheelbase / 2, r, false);
  return root;
}

/** Aircraft standing on an apron (scenery: no rig, no lights), or null when there is nothing to stand there. */
export function parkedJets(_spots: { position: THREE.Vector3; heading: number; id: string }[]): THREE.Object3D | null {
  return null;
}
