import * as THREE from 'three';
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js';
import type { CarSpec } from '../vehicle/carSpecs';
import { adoptMaterials, createCarMaterials, modelAnchors, type CarMaterials, type CarRig } from './CarModel';
import { wrapAngle } from '../util/math';

/**
 * The tanks: our own models (public/models/tanks/<id>.glb, tools/blender/tanks/<id>.py) or a procedural stand-in while
 * one is missing. GLB contract: metres, +Z forward, +X = the vehicle's left, ground at y = 0, origin on the ground at the
 * middle of the track contact; node `body` (hull, tracks, skirts); `turret` (child of body, origin on the traverse axis
 * at the ring, turning about its Y); `gun` (child of turret, origin on the trunnion axis, elevating about its X, the
 * bore along +Z: the farthest +Z point of its geometry is the muzzle); `roll_l<n>` / `roll_r<n>` road wheels, sprockets
 * and idlers spinning about X with their side's track; the 16式's wheel pivots `wheel_<axle><l|r>` with `spin_*` children
 * (axles 1 and 2 steer). Track materials `track_l` / `track_r`: the texture scrolls along V with the distance each side
 * covers (`TankInfo.trackV`, metres per V unit).
 *
 * **The gun's places are the simulation's, not the model's**: the shell leaves from `TankInfo.dims` (the ring at
 * `turretZ` / `ringY`, the trunnions `trunnion` above and `trunnionZ` ahead of the traverse axis, the muzzle
 * `barrel` ahead of the trunnions: `weapons/gun.ts` `gunPose`), the gunner's eye is `dims.sight` (turret frame;
 * default on the roof right of the gun). A model is built to those figures, or the figures are set from the model
 * with it (the flash is drawn at the model's own muzzle, `TankRig.muzzle`: a model that disagrees shows its flash
 * beside the shell's start). What the rig needs of a model, in short: `body`, `turret` (yaw about Y at the ring),
 * `gun` (pitch about X at the trunnions, bore along +Z, its farthest +Z vertex = the muzzle); `setAim` turns the
 * two (the local player's from its simulation, an online peer's from its packets), `fire()` runs the gun back.
 *
 * Everything moves by the root's motion (live sim, ghost, online peer alike): each track's speed is the root's forward
 * speed ± its yaw rate × half the gauge.
 *
 * Draw calls: the `roll_*` nodes (2 × 7–10 of them) are merged at build into ONE skinned mesh per material, a bone per
 * node (`mergeRolls`), so the whole running gear is one call however many wheels it has; a track material's every
 * texture slot (colour, normal, roughness / metalness, occlusion) scrolls together.
 */
const templates = new Map<string, THREE.Object3D>();
const loading = new Map<string, Promise<void>>();

/** Load a tank's model once (later calls wait for the same load); a missing file leaves the procedural stand-in. */
export function loadTankModel(id: string): Promise<void> {
  if (templates.has(id)) return Promise.resolve();
  let p = loading.get(id);
  if (!p) {
    p = (async () => {
      const { GLTFLoader } = await import('three/examples/jsm/loaders/GLTFLoader.js');
      const { MeshoptDecoder } = await import('three/examples/jsm/libs/meshopt_decoder.module.js');
      const loader = new GLTFLoader();
      loader.setMeshoptDecoder(MeshoptDecoder);
      try {
        const gltf = await loader.loadAsync(`/models/tanks/${id}.glb`);
        templates.set(id, gltf.scene);
      } catch {
        // no model yet: the procedural stand-in
      }
    })();
    loading.set(id, p);
  }
  return p;
}

export const tankModelReady = (id: string) => templates.has(id);

export interface TankRig {
  readonly turret: THREE.Object3D;
  readonly gun: THREE.Object3D;
  /** turret yaw relative to the hull (rad, + = to the left) and gun elevation (rad, + = up) as shown */
  readonly yaw: number;
  readonly pitch: number;
  setAim(yaw: number, pitch: number): void;
  /** the muzzle (world) and the bore's direction (world, unit) */
  muzzle(pos: THREE.Vector3, dir?: THREE.Vector3): void;
  /** the gun runs back on firing and returns */
  fire(): void;
  update(anchor: THREE.Object3D, dt: number): void;
}

const _v = new THREE.Vector3(), _q = new THREE.Quaternion();
/** the gun's recoil stroke (m) and how long its run-out takes (s) */
const RECOIL = 0.45;
const RUN_OUT = 0.9;

export function buildTank(spec: CarSpec, opts: { bodyColor?: string; procedural?: boolean } = {}): CarRig & { tank: TankRig } {
  const info = spec.tank!;
  const tpl = opts.procedural ? null : templates.get(spec.id);
  const root = new THREE.Group();
  root.name = `tank-${spec.id}`;
  let mats: CarMaterials;
  let model: THREE.Object3D;
  if (tpl) {
    model = tpl.clone(true);
    model.userData = { ...model.userData, tankTemplate: tpl };
    mats = adoptMaterials(model, spec, opts.bodyColor);
  } else {
    mats = createCarMaterials(spec, opts.bodyColor);
    mats.paint.clearcoat = 0;
    mats.paint.roughness = 0.85;
    mats.paint.metalness = 0;
    model = proceduralTank(spec, mats);
  }
  root.add(model);
  const turret = model.getObjectByName('turret') ?? new THREE.Group();
  const gun = model.getObjectByName('gun') ?? new THREE.Group();
  const turretBase = turret.quaternion.clone();
  const gunBase = gun.quaternion.clone();
  const gunHome = gun.position.clone();

  // the muzzle: the farthest point of the gun's geometry along its bore (+Z of the gun node)
  root.updateMatrixWorld(true);
  const muzzleLocal = new THREE.Vector3(0, 0, info.dims.barrel);
  {
    const inv = gun.matrixWorld.clone().invert();
    let maxZ = -Infinity;
    gun.traverse((o) => {
      const m = o as THREE.Mesh;
      if (!m.isMesh) return;
      const pos = m.geometry.getAttribute('position');
      for (let i = 0; i < pos.count; i++) {
        _v.fromBufferAttribute(pos, i).applyMatrix4(m.matrixWorld).applyMatrix4(inv);
        if (_v.z > maxZ) maxZ = _v.z;
      }
    });
    if (Number.isFinite(maxZ)) muzzleLocal.set(0, 0, maxZ);
  }

  if (tpl) mergeRolls(model);
  // tracks: the scrolling materials (each instance its own copy), the rolling wheels, the 16式's wheels
  const trackMats: { mat: THREE.MeshStandardMaterial; left: boolean; scrolled: THREE.Texture[] }[] = [];
  const rolls: { node: THREE.Object3D; left: boolean; radius: number }[] = [];
  const wheels8: { pivot: THREE.Object3D; spin: THREE.Object3D; axle: number; base: THREE.Quaternion; radius: number }[] = [];
  model.traverse((o) => {
    const m = o as THREE.Mesh;
    if (m.isMesh) {
      const list = Array.isArray(m.material) ? m.material : [m.material];
      const swapped = list.map((mat) => {
        if (mat.name !== 'track_l' && mat.name !== 'track_r') return mat;
        const own = (mat as THREE.MeshStandardMaterial).clone();
        // every slot its own copy of the texture (one offset each; a slot shared by two, as glTF's roughness and
        // metalness are, keeps one copy for both)
        const copies = new Map<THREE.Texture, THREE.Texture>();
        const scrolled: THREE.Texture[] = [];
        for (const slot of TRACK_SLOTS) {
          const tex = own[slot] as THREE.Texture | null;
          if (!tex) continue;
          let c = copies.get(tex);
          if (!c) {
            c = tex.clone();
            c.wrapS = c.wrapT = THREE.RepeatWrapping;
            c.needsUpdate = true;
            copies.set(tex, c);
            scrolled.push(c);
          }
          (own as unknown as Record<string, THREE.Texture>)[slot] = c;
        }
        trackMats.push({ mat: own, left: mat.name === 'track_l', scrolled });
        return own;
      });
      m.material = Array.isArray(m.material) ? swapped : swapped[0];
    }
    const roll = /^roll_([lr])\d+/.exec(o.name);
    if (roll) {
      // (a merged wheel is a bone: its radius was measured before the merge)
      const box = new THREE.Box3().setFromObject(o);
      const radius = (o.userData.radius as number | undefined) ?? Math.max(0.05, (box.max.y - box.min.y) / 2);
      rolls.push({ node: o, left: roll[1] === 'l', radius });
    }
    const wheel = /^wheel_(\d)([lr])$/.exec(o.name);
    if (wheel) {
      const spin = o.getObjectByName(`spin_${wheel[1]}${wheel[2]}`) ?? o;
      const box = new THREE.Box3().setFromObject(spin);
      wheels8.push({ pivot: o, spin, axle: +wheel[1], base: o.quaternion.clone(), radius: Math.max(0.1, (box.max.y - box.min.y) / 2) });
    }
  });
  const trackV = info.trackV ?? 1;
  const gauge = spec.track;

  const anchors = modelAnchors(root, mats, spec);
  // the sim drives four wheels: stand-ins whose steer the 16式's front axles copy (not in the scene)
  const standIns = [0, 1, 2, 3].map(() => {
    const pivot = new THREE.Group(), spin = new THREE.Group();
    pivot.add(spin);
    return { pivot, spin };
  });

  let yaw = 0, pitch = 0, recoil = 0;
  let last: { x: number; z: number; yaw: number } | null = null;
  let distL = 0, distR = 0;
  const fwd = new THREE.Vector3();
  const AXIS_Y = new THREE.Vector3(0, 1, 0), AXIS_X = new THREE.Vector3(1, 0, 0);
  const rig: TankRig = {
    turret,
    gun,
    get yaw() {
      return yaw;
    },
    get pitch() {
      return pitch;
    },
    setAim(y, p) {
      yaw = y;
      pitch = p;
      turret.quaternion.copy(turretBase).multiply(_q.setFromAxisAngle(AXIS_Y, yaw));
      // (about +X a positive angle tips +Z down: elevation is the negative rotation)
      gun.quaternion.copy(gunBase).multiply(_q.setFromAxisAngle(AXIS_X, -pitch * (info.gunSign ?? 1)));
    },
    muzzle(pos, dir) {
      gun.updateWorldMatrix(true, false);
      pos.copy(muzzleLocal).applyMatrix4(gun.matrixWorld);
      if (dir) dir.set(0, 0, 1).transformDirection(gun.matrixWorld);
    },
    fire() {
      recoil = 1;
    },
    update(anchor, dt) {
      if (dt <= 0) return;
      fwd.set(0, 0, 1).applyQuaternion(anchor.quaternion);
      const heading = Math.atan2(fwd.x, fwd.z);
      const p = anchor.position;
      if (last) {
        const dx = p.x - last.x, dz = p.z - last.z;
        const along = dx * fwd.x + dz * fwd.z;
        // (a teleport — respawn, the grid — is no motion)
        if (Math.hypot(dx, dz) < 40) {
          const turn = wrapAngle(heading - last.yaw);
          // + turn = to the left: the left track runs slower
          distL += along - (turn * gauge) / 2;
          distR += along + (turn * gauge) / 2;
        }
      }
      last = { x: p.x, z: p.z, yaw: heading };
      for (const t of trackMats) {
        const d = (t.left ? distL : distR) / trackV;
        for (const tex of t.scrolled) tex.offset.y = -d;
      }
      for (const r of rolls) r.node.rotation.x = (r.left ? distL : distR) / r.radius;
      const steer = standIns[0].pivot.rotation.y;
      for (const w of wheels8) {
        // the second axle steers about 2/3 as far as the first (Ackermann on a long wheelbase)
        const a = w.axle === 1 ? steer : w.axle === 2 ? steer * 0.66 : 0;
        w.pivot.quaternion.copy(w.base).multiply(_q.setFromAxisAngle(AXIS_Y, a));
        w.spin.rotation.x = (distL + distR) / 2 / w.radius;
      }
      // the gun runs back at once and out again over RUN_OUT
      recoil = Math.max(0, recoil - dt / RUN_OUT);
      gun.position.copy(gunHome).addScaledVector(_v.set(0, 0, -1).applyQuaternion(gun.quaternion), RECOIL * recoil * recoil);
    },
  };
  rig.setAim(0, 0);
  const body = new THREE.Group();
  return { root, body, wheels: standIns, materials: mats, headlightTargets: [], anchors, fromModel: !!tpl, tank: rig };
}

/** the texture slots of a track material that scroll with it */
const TRACK_SLOTS = ['map', 'normalMap', 'roughnessMap', 'metalnessMap', 'aoMap'] as const;

/** the merged running gear of each model (geometry per material, the bones' places), made once per template */
interface RollMerge {
  parent: string;
  bones: { name: string; matrix: THREE.Matrix4; radius: number }[];
  parts: { geometry: THREE.BufferGeometry; material: THREE.Material; cast: boolean }[];
}
const rollCache = new Map<THREE.Object3D, RollMerge>();

/**
 * The `roll_*` nodes of a model (a copy of a template) become bones of one skinned mesh per material: each node's
 * meshes are put into its parent's frame with the node's index as their bone, and the node itself is replaced by a
 * `THREE.Bone` of the same name and place (so the rig turns it as before). One draw call for the whole running gear.
 * The roll nodes must share one parent (the contract has them under `body`).
 */
function mergeRolls(model: THREE.Object3D) {
  const rolls: THREE.Object3D[] = [];
  model.traverse((o) => {
    if (/^roll_[lr]\d+/.test(o.name)) rolls.push(o);
  });
  if (rolls.length < 2) return;
  const parent = rolls[0].parent!;
  if (rolls.some((r) => r.parent !== parent)) return;
  const tpl = templateOf(model);
  let cache = tpl ? rollCache.get(tpl) : undefined;
  model.updateMatrixWorld(true);
  const toParent = parent.matrixWorld.clone().invert();
  if (!cache) {
    const byMat = new Map<THREE.Material, { geos: THREE.BufferGeometry[]; cast: boolean }>();
    rolls.forEach((r, i) => {
      r.traverse((o) => {
        const m = o as THREE.Mesh;
        if (!m.isMesh || Array.isArray(m.material)) return;
        const g = m.geometry.clone().applyMatrix4(toParent.clone().multiply(m.matrixWorld));
        const n = g.getAttribute('position').count;
        g.setAttribute('skinIndex', new THREE.Uint16BufferAttribute(new Uint16Array(n * 4).map((_, k) => (k % 4 === 0 ? i : 0)), 4));
        g.setAttribute('skinWeight', new THREE.Float32BufferAttribute(new Float32Array(n * 4).map((_, k) => (k % 4 === 0 ? 1 : 0)), 4));
        for (const name of Object.keys(g.attributes)) if (!['position', 'normal', 'uv', 'skinIndex', 'skinWeight'].includes(name)) g.deleteAttribute(name);
        const e = byMat.get(m.material) ?? { geos: [], cast: false };
        e.geos.push(g);
        e.cast ||= m.castShadow;
        byMat.set(m.material, e);
      });
    });
    const parts: RollMerge['parts'] = [];
    for (const [material, e] of byMat) {
      // (all indexed or none: mixed, the indexed ones are expanded)
      const mixed = e.geos.some((g) => !g.index) && e.geos.some((g) => !!g.index);
      const geometry = mergeGeometries(e.geos.map((g) => (mixed && g.index ? g.toNonIndexed() : g)), false);
      if (geometry) parts.push({ geometry, material, cast: e.cast });
    }
    // each wheel's radius: half its height (as the rig measured it on the node before)
    const radius = (r: THREE.Object3D) => {
      const box = new THREE.Box3().setFromObject(r);
      return Math.max(0.05, (box.max.y - box.min.y) / 2);
    };
    cache = { parent: parent.name, bones: rolls.map((r) => ({ name: r.name, matrix: toParent.clone().multiply(r.matrixWorld), radius: radius(r) })), parts };
    if (tpl) rollCache.set(tpl, cache);
  }
  for (const r of rolls) r.removeFromParent();
  const bones = cache.bones.map((b) => {
    const bone = new THREE.Bone();
    bone.name = b.name;
    bone.userData.radius = b.radius;
    b.matrix.decompose(bone.position, bone.quaternion, bone.scale);
    parent.add(bone);
    return bone;
  });
  parent.updateMatrixWorld(true);
  const skeleton = new THREE.Skeleton(bones);
  for (const p of cache.parts) {
    const mesh = new THREE.SkinnedMesh(p.geometry, p.material);
    mesh.name = 'running_gear';
    mesh.castShadow = p.cast;
    parent.add(mesh);
    mesh.updateMatrixWorld(true);
    mesh.bind(skeleton);
  }
}

/** the template a model was cloned from (set on the copy by buildTank) */
const templateOf = (model: THREE.Object3D) => model.userData.tankTemplate as THREE.Object3D | undefined;

/** a tileable track-link texture (dark steel links, rubber pads), drawn once */
let linkTexture: THREE.CanvasTexture | null = null;
function trackTexture() {
  if (linkTexture) return linkTexture;
  const c = document.createElement('canvas');
  c.width = 64;
  c.height = 64;
  const g = c.getContext('2d')!;
  g.fillStyle = '#1c1d1b';
  g.fillRect(0, 0, 64, 64);
  for (let k = 0; k < 4; k++) {
    g.fillStyle = '#3a3b36';
    g.fillRect(4, k * 16 + 2, 56, 10);
    g.fillStyle = '#121311';
    g.fillRect(28, k * 16 + 4, 8, 6);
  }
  linkTexture = new THREE.CanvasTexture(c);
  linkTexture.wrapS = linkTexture.wrapT = THREE.RepeatWrapping;
  linkTexture.colorSpace = THREE.SRGBColorSpace;
  return linkTexture;
}

/** A stand-in tank from boxes and cylinders (until our model is in place): hull, tracks or eight wheels, turret, gun. */
function proceduralTank(spec: CarSpec, mats: CarMaterials) {
  const t = spec.tank!;
  const d = t.dims;
  const root = new THREE.Group();
  const body = new THREE.Group();
  body.name = 'body';
  root.add(body);
  const [L, W, H] = d.hull;
  const clear = spec.clearance ?? 0.45;
  const camo2 = new THREE.MeshStandardMaterial({ color: t.camo[1], roughness: 0.9 });
  const box = (parent: THREE.Object3D, w: number, h: number, l: number, m: THREE.Material, x: number, y: number, z: number, rx = 0) => {
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(w, h, l), m);
    mesh.position.set(x, y, z);
    mesh.rotation.x = rx;
    mesh.castShadow = true;
    parent.add(mesh);
    return mesh;
  };
  const tracked = t.running === 'tracks';
  const hullW = tracked ? W - 1.2 : W;
  // the hull, a sloped glacis and a camouflage patch on the deck
  box(body, hullW, H, L * 0.86, mats.paint, 0, clear + H / 2, -L * 0.04);
  box(body, hullW, H * 0.7, L * 0.22, mats.paint, 0, clear + H * 0.55, L * 0.42, -0.75);
  box(body, hullW * 0.5, 0.04, L * 0.3, camo2, hullW * 0.15, clear + H + 0.02, -L * 0.2);
  box(body, 0.3, 0.12, 0.05, mats.headlight, hullW / 2 - 0.25, clear + H - 0.15, L / 2 - 0.05);
  box(body, 0.3, 0.12, 0.05, mats.headlight, -hullW / 2 + 0.25, clear + H - 0.15, L / 2 - 0.05);
  box(body, 0.2, 0.08, 0.05, mats.taillight, hullW / 2 - 0.2, clear + H - 0.15, -L / 2 + 0.05);
  box(body, 0.2, 0.08, 0.05, mats.taillight, -hullW / 2 + 0.2, clear + H - 0.15, -L / 2 + 0.05);
  if (tracked) {
    const tex = trackTexture();
    for (const left of [true, false]) {
      const m = new THREE.MeshStandardMaterial({ map: tex.clone(), roughness: 0.75, metalness: 0.3 });
      m.name = left ? 'track_l' : 'track_r';
      m.map!.wrapS = m.map!.wrapT = THREE.RepeatWrapping;
      // the box's side faces carry the links along their length: the texture's V along +Z after the rotation below
      m.map!.repeat.set(1, L / 0.64);
      m.map!.needsUpdate = true;
      const x = (left ? 1 : -1) * (W / 2 - 0.33);
      const band = new THREE.Mesh(new THREE.BoxGeometry(0.62, clear + 0.45, L * 0.95), m);
      // rotate each face's UVs so V runs along the track: swap u/v on the geometry
      const uv = band.geometry.getAttribute('uv');
      for (let i = 0; i < uv.count; i++) uv.setXY(i, uv.getY(i), uv.getX(i));
      band.position.set(x, (clear + 0.45) / 2, 0);
      band.castShadow = true;
      body.add(band);
      // the skirt over the top run
      box(body, 0.08, 0.5, L * 0.92, mats.paint, (left ? 1 : -1) * (W / 2 - 0.02), clear + 0.5, 0.05);
      // road wheels showing below the skirts
      for (let k = 0; k < 6; k++) {
        const roll = new THREE.Group();
        roll.name = `roll_${left ? 'l' : 'r'}${k}`;
        roll.position.set((left ? 1 : -1) * (W / 2 - 0.62), 0.38, L * 0.4 - (k * L * 0.8) / 5);
        const wheel = new THREE.Mesh(new THREE.CylinderGeometry(0.36, 0.36, 0.2, 14).rotateZ(Math.PI / 2), mats.trim);
        roll.add(wheel);
        body.add(roll);
      }
    }
  } else {
    // eight wheels, the first two axles steering
    const axles = [L * 0.36, L * 0.16, -L * 0.14, -L * 0.34];
    const r = spec.wheelRadius;
    axles.forEach((z, k) => {
      for (const left of [true, false]) {
        const pivot = new THREE.Group();
        pivot.name = `wheel_${k + 1}${left ? 'l' : 'r'}`;
        pivot.position.set((left ? 1 : -1) * (spec.track / 2), r, z);
        const spin = new THREE.Group();
        spin.name = `spin_${k + 1}${left ? 'l' : 'r'}`;
        spin.add(new THREE.Mesh(new THREE.CylinderGeometry(r, r, 0.42, 18).rotateZ(Math.PI / 2), mats.tire));
        spin.add(new THREE.Mesh(new THREE.CylinderGeometry(r * 0.55, r * 0.55, 0.44, 12).rotateZ(Math.PI / 2), mats.rim));
        pivot.add(spin);
        body.add(pivot);
      }
    });
  }
  // the turret on its ring, the gun on its trunnions
  const turret = new THREE.Group();
  turret.name = 'turret';
  turret.position.set(0, d.ringY, d.turretZ);
  body.add(turret);
  const [tl, tw, th] = d.turret;
  box(turret, tw, th, tl, mats.paint, 0, th / 2, -tl * 0.12);
  box(turret, tw * 0.7, th * 0.8, tl * 0.25, mats.paint, 0, th * 0.42, tl * 0.32, -0.3);
  box(turret, tw * 0.4, 0.03, tl * 0.4, camo2, -tw * 0.1, th + 0.02, -tl * 0.2);
  box(turret, 0.35, 0.3, 0.4, mats.trim, tw * 0.25, th + 0.15, -tl * 0.05);
  const gun = new THREE.Group();
  gun.name = 'gun';
  gun.position.set(0, d.trunnion, d.trunnionZ);
  turret.add(gun);
  box(gun, 0.7, 0.5, 0.6, mats.paint, 0, 0, 0.1);
  const r0 = (t.gun.calibre / 1000) * 1.2;
  // (from the mantlet to the muzzle, `barrel` ahead of the trunnions)
  const barrel = new THREE.Mesh(new THREE.CylinderGeometry(r0, r0 * 1.15, d.barrel - 0.3, 14).rotateX(Math.PI / 2), mats.paint);
  barrel.position.z = (d.barrel + 0.3) / 2;
  barrel.castShadow = true;
  gun.add(barrel);
  const sleeve = new THREE.Mesh(new THREE.CylinderGeometry(r0 * 1.7, r0 * 1.7, 0.7, 14).rotateX(Math.PI / 2), mats.paint);
  sleeve.position.z = d.barrel * 0.55;
  gun.add(sleeve);
  return root;
}
