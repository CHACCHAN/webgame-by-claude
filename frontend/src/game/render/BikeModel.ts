import * as THREE from 'three';
import type { CarSpec } from '../vehicle/carSpecs';
import { adoptMaterials, createCarMaterials, modelAnchors, type CarMaterials, type CarRig } from './CarModel';
import { damp, clamp, wrapAngle } from '../util/math';

/**
 * The motorcycles: our own models (public/models/bikes/<id>.glb, tools/blender/bikes/<id>.py) or a procedural
 * stand-in while one is missing. GLB contract: metres, +Z forward, +X = the bike's left, ground at y = 0, origin on the
 * ground midway between the tyre contact points; node `body` (frame, fairing, engine, swingarm, exhaust; the rider as
 * its child `rider`), `steer` (child of body: forks, yokes, bars; its local +Y is the steering axis), wheel pivots
 * `wheel_f` (child of steer) and `wheel_r` (child of body) with spinning children `spin_f` / `spin_r`.
 *
 * The bike leans by the lateral acceleration of whatever moves it (a live sim, a ghost, an online peer): speed × yaw
 * rate of the visual's root, so all three look the same. A live sim adds the front going light at the wheelie limit
 * and the rear at the stoppie limit.
 */
const templates = new Map<string, THREE.Object3D>();

export async function loadBikeModels(ids: string[]) {
  const todo = ids.filter((id) => !templates.has(id));
  if (!todo.length) return;
  const { GLTFLoader } = await import('three/examples/jsm/loaders/GLTFLoader.js');
  const { MeshoptDecoder } = await import('three/examples/jsm/libs/meshopt_decoder.module.js');
  const loader = new GLTFLoader();
  loader.setMeshoptDecoder(MeshoptDecoder);
  await Promise.all(
    todo.map(async (id) => {
      try {
        const gltf = await loader.loadAsync(`/models/bikes/${id}.glb`);
        templates.set(id, gltf.scene);
      } catch {
        // no model yet: the procedural stand-in
      }
    }),
  );
}

export interface BikeRig {
  /** lean angle (rad, + = to the left) */
  readonly lean: number;
  /** per frame: lean by the motion of `anchor` since the last call; `live` adds the sim's wheelie / stoppie state */
  update(anchor: THREE.Object3D, dt: number, live?: { wheelie: number; stoppie: number }): void;
}

/** front lift at the wheelie limit / rear lift at the stoppie limit (rad) */
const WHEELIE = 0.07;
const STOPPIE = 0.035;
/** share of the sim's steer angle the bars show (a bike turns its bars far less than a car its wheels) */
const BAR_SHARE = 0.45;

export function buildBike(spec: CarSpec, opts: { bodyColor?: string; procedural?: boolean } = {}): CarRig & { bike: BikeRig } {
  const tpl = opts.procedural ? null : templates.get(spec.id);
  const root = new THREE.Group();
  root.name = `bike-${spec.id}`;
  // lean about the contact line (y = 0), then pitch about the rear contact (wheelie) or the front one (stoppie)
  const lean = new THREE.Group();
  const rear = new THREE.Group(), front = new THREE.Group();
  const half = spec.wheelbase / 2;
  rear.position.z = -half;
  front.position.z = 2 * half;
  root.add(lean);
  lean.add(rear);
  rear.add(front);
  const model = new THREE.Group();
  model.position.z = -half;
  front.add(model);

  let mats: CarMaterials;
  let steer: THREE.Object3D | null, wheelF: THREE.Object3D | null, wheelR: THREE.Object3D | null;
  if (tpl) {
    const scene = tpl.clone(true);
    mats = adoptMaterials(scene, spec, opts.bodyColor);
    model.add(scene);
    steer = scene.getObjectByName('steer') ?? null;
    wheelF = scene.getObjectByName('spin_f') ?? null;
    wheelR = scene.getObjectByName('spin_r') ?? null;
  } else {
    mats = createCarMaterials(spec, opts.bodyColor);
    const p = proceduralBike(spec, mats);
    model.add(p.root);
    ({ steer, wheelF, wheelR } = p);
  }
  const steerBase = steer?.quaternion.clone() ?? new THREE.Quaternion();
  root.updateMatrixWorld(true);
  const anchors = modelAnchors(root, mats, spec);

  // the sim drives four wheels: stand-ins whose state the update copies onto the two real ones (not in the scene)
  const wheels = [0, 1, 2, 3].map(() => {
    const pivot = new THREE.Group(), spin = new THREE.Group();
    pivot.add(spin);
    return { pivot, spin };
  });
  // the car visual tilts `body` for a car's roll and pitch: a detached stand-in (a bike leans instead)
  const body = new THREE.Group();

  const fwd = new THREE.Vector3(), q = new THREE.Quaternion();
  const AXIS_Y = new THREE.Vector3(0, 1, 0);
  let last: { x: number; z: number; yaw: number } | null = null;
  let leanAngle = 0, pitchUp = 0, pitchDown = 0;
  const info = spec.bike!;
  const rig: BikeRig = {
    get lean() {
      return leanAngle;
    },
    update(anchor, dt, live) {
      if (dt > 0) {
        fwd.set(0, 0, 1).applyQuaternion(anchor.quaternion);
        const yaw = Math.atan2(fwd.x, fwd.z);
        const p = anchor.position;
        let target = leanAngle;
        if (last) {
          const v = Math.hypot(p.x - last.x, p.z - last.z) / dt;
          // (a teleport — respawn, the grid — is no motion)
          if (v < 160) {
            const yawRate = wrapAngle(yaw - last.yaw) / dt;
            const lateral = v * yawRate;
            target = clamp(Math.atan2(lateral, 9.81), -info.maxLean, info.maxLean) * Math.min(1, v / 3);
          }
        }
        last = { x: p.x, z: p.z, yaw };
        leanAngle = damp(leanAngle, target, 7, dt);
        pitchUp = damp(pitchUp, (live?.wheelie ?? 0) * WHEELIE, 5, dt);
        pitchDown = damp(pitchDown, (live?.stoppie ?? 0) * STOPPIE, 6, dt);
      }
      // + lean = to the left: the top tilts towards +X (a rotation about +Z by a negative angle)
      lean.rotation.z = -leanAngle;
      rear.rotation.x = -pitchUp;
      front.rotation.x = pitchDown;
      // the bars and both wheels from the sim's stand-ins (FL and RL)
      if (steer) steer.quaternion.copy(steerBase).multiply(q.setFromAxisAngle(AXIS_Y, wheels[0].pivot.rotation.y * BAR_SHARE));
      if (wheelF) wheelF.rotation.x = wheels[0].spin.rotation.x;
      if (wheelR) wheelR.rotation.x = wheels[2].spin.rotation.x;
    },
  };
  const target = new THREE.Object3D();
  target.position.set(0, 0.2, 30);
  lean.add(target);
  return { root, body, wheels, materials: mats, headlightTargets: [target], anchors, fromModel: !!tpl, lampParent: lean, bike: rig };
}

/** A stand-in bike from primitives (until the model is in place): wheels, fairing, tank, seat, exhaust and a rider. */
function proceduralBike(spec: CarSpec, mats: CarMaterials) {
  const root = new THREE.Group();
  const body = new THREE.Group();
  body.name = 'body';
  root.add(body);
  const r = spec.wheelRadius;
  const half = spec.wheelbase / 2;
  const box = (w: number, h: number, d: number, m: THREE.Material, x: number, y: number, z: number, rx = 0) => {
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), m);
    mesh.position.set(x, y, z);
    mesh.rotation.x = rx;
    body.add(mesh);
    return mesh;
  };
  const wheel = (name: string) => {
    const spin = new THREE.Group();
    spin.name = name;
    const tyre = new THREE.Mesh(new THREE.TorusGeometry(r - 0.06, 0.06, 10, 28).rotateY(Math.PI / 2), mats.tire);
    const rim = new THREE.Mesh(new THREE.CylinderGeometry(r - 0.1, r - 0.1, 0.05, 20).rotateZ(Math.PI / 2), mats.rim);
    const disc = new THREE.Mesh(new THREE.CylinderGeometry(0.15, 0.15, 0.11, 20).rotateZ(Math.PI / 2), mats.chrome);
    spin.add(tyre, rim, disc);
    return spin;
  };
  // the rear wheel, the swingarm, the engine block
  const wheelR = wheel('spin_r');
  wheelR.position.set(0, r, -half);
  body.add(wheelR);
  box(0.06, 0.06, half * 0.95, mats.trim, 0.1, r + 0.04, -half * 0.5, 0.12);
  box(0.06, 0.06, half * 0.95, mats.trim, -0.1, r + 0.04, -half * 0.5, 0.12);
  box(0.36, 0.34, 0.5, mats.trim, 0, r + 0.12, 0.02);
  // fairing (nose and flanks), screen, tank, seat unit, tail lamp, belly pan
  box(0.5, 0.5, 0.7, mats.paint, 0, r + 0.38, half * 0.55, -0.35);
  box(0.36, 0.06, 0.32, mats.glass, 0, r + 0.72, half * 0.62, -0.75);
  box(0.24, 0.12, 0.08, mats.headlight, 0, r + 0.44, half * 0.98);
  box(0.4, 0.24, 0.5, mats.paint, 0, r + 0.5, 0.05);
  box(0.26, 0.1, 0.5, mats.trim, 0, r + 0.52, -0.42);
  box(0.24, 0.2, 0.42, mats.paint, 0, r + 0.5, -0.78, 0.25);
  box(0.16, 0.06, 0.04, mats.taillight, 0, r + 0.52, -1.0);
  box(0.42, 0.16, 0.7, mats.paint, 0, r - 0.02, 0.15);
  // the silencer on the right
  const pipe = new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.07, 0.5, 14).rotateX(Math.PI / 2 - 0.18), mats.chrome);
  pipe.name = 'exhaust';
  pipe.position.set(-0.17, r + 0.12, -half * 0.75);
  body.add(pipe);
  // the steering: forks along the axis (raked 24°), bars, the front wheel
  const steer = new THREE.Group();
  steer.name = 'steer';
  // the head stock 0.66 m up the axis from the front axle (r, half): the axis leans back 0.42 rad
  steer.position.set(0, r + 0.66 * Math.cos(0.42), half - 0.66 * Math.sin(0.42));
  steer.rotation.x = -0.42;
  body.add(steer);
  for (const x of [0.09, -0.09]) {
    const leg = new THREE.Mesh(new THREE.CylinderGeometry(0.025, 0.025, 0.66, 8), mats.chrome);
    leg.position.set(x, -0.33, 0);
    steer.add(leg);
  }
  const bar = new THREE.Mesh(new THREE.CylinderGeometry(0.018, 0.018, 0.62, 8).rotateZ(Math.PI / 2), mats.trim);
  bar.position.set(0, 0.04, -0.06);
  steer.add(bar);
  const axle = new THREE.Group();
  // the axle at the end of the forks, in the steering frame
  axle.position.set(0, -0.66, 0);
  steer.add(axle);
  // (a rotation about X keeps the wheel in its plane: it spins about its own X as the rear one)
  const wheelF = wheel('spin_f');
  axle.add(wheelF);
  // the rider: legs, torso leaning over the tank, arms to the bars, the helmet
  const suit = new THREE.MeshStandardMaterial({ color: '#1d1f24', roughness: 0.6 });
  const helmet = new THREE.MeshStandardMaterial({ color: '#d8d9db', roughness: 0.25, metalness: 0.2 });
  const rider = new THREE.Group();
  rider.name = 'rider';
  body.add(rider);
  const part = (geo: THREE.BufferGeometry, m: THREE.Material, x: number, y: number, z: number, rx = 0) => {
    const mesh = new THREE.Mesh(geo, m);
    mesh.position.set(x, y, z);
    mesh.rotation.x = rx;
    rider.add(mesh);
  };
  const hip = r + 0.62;
  for (const x of [0.15, -0.15]) {
    part(new THREE.CapsuleGeometry(0.07, 0.36, 4, 8), suit, x, hip - 0.12, -0.2, 1.1);
    part(new THREE.CapsuleGeometry(0.06, 0.34, 4, 8), suit, x, hip - 0.3, -0.32, -0.5);
    part(new THREE.CapsuleGeometry(0.05, 0.4, 4, 8), suit, x * 1.3, hip + 0.28, 0.1, 1.15);
  }
  part(new THREE.CapsuleGeometry(0.17, 0.42, 4, 10), suit, 0, hip + 0.22, -0.12, 1.05);
  part(new THREE.SphereGeometry(0.15, 16, 12), helmet, 0, hip + 0.5, 0.12);
  return { root, steer: steer as THREE.Object3D, wheelF: wheelF as THREE.Object3D, wheelR: wheelR as THREE.Object3D };
}
