import * as THREE from 'three';
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js';
import type { CarSpec } from '../vehicle/carSpecs';
import { trainBogiePath, trainCars, trainNoseZ, trainTailZ, type LampPair, type Livery, type TrainInfo } from '../vehicle/trains';
import { createCarMaterials, type CarRig } from './CarModel';

/**
 * Three-car commuter trains (joke entries). The simulated vehicle is the leading car's front bogie; the cars are
 * drawn along the path that bogie has driven, so the whole train follows the road like rails. Cars are 20 m
 * apart (body 19.5 m) with bogie centres 13.8 m apart; the leading car's front is 2.85 m ahead of the bogie.
 * Car-local frame: +z forward, +x left, y = 0 at the road.
 */
export const TRAIN = { cars: 3, pitch: 20, bogies: 13.8, body: 19.5, floor: 1.15, bottom: 0.95, eave: 3.12, roof: 3.62 };
/** front of the leading car ahead of the simulated bogie (m) */
export const trainNose = (t: TrainInfo) => trainCars(t)[0].front;

/** Cars cut from third-party models (public/models/trains/<id>.glb: nodes car0..car2), by train id. */
const models = new Map<string, THREE.Object3D[]>();

export async function loadTrainModels(ids: string[]) {
  const { GLTFLoader } = await import('three/examples/jsm/loaders/GLTFLoader.js');
  const { MeshoptDecoder } = await import('three/examples/jsm/libs/meshopt_decoder.module.js');
  const loader = new GLTFLoader();
  loader.setMeshoptDecoder(MeshoptDecoder);
  await Promise.all(
    ids.map(async (id) => {
      if (models.has(id)) return;
      try {
        const gltf = await loader.loadAsync(`/models/trains/${id}.glb`);
        const cars = [0, 1, 2].map((k) => gltf.scene.getObjectByName(`car${k}`));
        if (cars.every(Boolean)) models.set(id, cars as THREE.Object3D[]);
      } catch (err) {
        console.warn(`train model ${id} not loaded, using the procedural cars`, err);
      }
    }),
  );
}

export interface TrainRig {
  /** place the cars behind the anchor (the leading bogie, at road level) along its driven path */
  update(anchor: THREE.Object3D): void;
  setLivery(color: string): void;
  /** interior lights behind the side windows (0 = off, 1 = night) */
  setInterior(level: number): void;
}

/** Path driven by the leading bogie: points every half metre, newest last, about 70 m kept. */
class TrainPath {
  private pts: THREE.Vector3[] = [];
  private head = new THREE.Vector3();

  reset(head: THREE.Vector3, fwd: THREE.Vector3) {
    this.head.copy(head);
    this.pts = [head.clone().addScaledVector(fwd, -80), head.clone()];
  }

  advance(head: THREE.Vector3, fwd: THREE.Vector3) {
    const last = this.pts[this.pts.length - 1];
    // a respawn or a new race: start a straight train behind
    if (!last || last.distanceTo(head) > 30) return this.reset(head, fwd);
    this.head.copy(head);
    // reversing: give back the path the bogie has backed over
    while (this.pts.length > 2) {
      const a = this.pts[this.pts.length - 2], b = this.pts[this.pts.length - 1];
      if (_d.subVectors(head, b).dot(_e.subVectors(b, a)) >= 0) break;
      this.pts.pop();
    }
    if (this.pts[this.pts.length - 1].distanceTo(head) >= 0.5) this.pts.push(head.clone());
    // keep ~70 m: drop the oldest points beyond it
    let len = 0;
    for (let i = this.pts.length - 1; i > 0; i--) {
      len += this.pts[i].distanceTo(this.pts[i - 1]);
      if (len > 70 && i > 1) {
        this.pts.splice(0, i - 1);
        break;
      }
    }
  }

  /** point `d` metres back along the path from the head (extrapolated past the oldest point) */
  at(d: number, out: THREE.Vector3) {
    let prev = this.head;
    for (let i = this.pts.length - 1; i >= 0; i--) {
      const p = this.pts[i];
      const seg = prev.distanceTo(p);
      if (seg >= d && seg > 1e-6) return out.lerpVectors(prev, p, d / seg);
      d -= seg;
      prev = p;
    }
    const a = this.pts[0], b = this.pts[1] ?? this.head;
    _d.subVectors(a, b).normalize();
    return out.copy(a).addScaledVector(_d, d);
  }
}

const _d = new THREE.Vector3(), _e = new THREE.Vector3(), _f = new THREE.Vector3(), _r = new THREE.Vector3();
const _x = new THREE.Vector3(), _y = new THREE.Vector3(), _z = new THREE.Vector3(), _c = new THREE.Vector3();
const _m = new THREE.Matrix4();
const UP = new THREE.Vector3(0, 1, 0);

type Mat = 'body' | 'band' | 'band2' | 'door' | 'glass' | 'mask' | 'dark' | 'roof' | 'head' | 'tail' | 'sign' | 'lower';

/** Rectangle on a car side (z0..z1 along the car, y0..y1 up), both sides, a hair off the body. */
function side(out: Map<Mat, THREE.BufferGeometry[]>, mat: Mat, w: number, z0: number, z1: number, y0: number, y1: number, lift = 0.004) {
  for (const s of [1, -1]) {
    const g = new THREE.PlaneGeometry(z1 - z0, y1 - y0).rotateY((s * Math.PI) / 2).translate(s * (w / 2 + lift), (y0 + y1) / 2, (z0 + z1) / 2);
    push(out, mat, g);
  }
}

/** Rectangle on an end face at z (facing +z when dir = 1). */
function face(out: Map<Mat, THREE.BufferGeometry[]>, mat: Mat, z: number, dir: number, x0: number, x1: number, y0: number, y1: number) {
  const g = new THREE.PlaneGeometry(x1 - x0, y1 - y0);
  if (dir < 0) g.rotateY(Math.PI);
  g.translate((x0 + x1) / 2, (y0 + y1) / 2, z);
  push(out, mat, g);
}

function box(out: Map<Mat, THREE.BufferGeometry[]>, mat: Mat, x: number, y: number, z: number, w: number, h: number, d: number) {
  push(out, mat, new THREE.BoxGeometry(w, h, d).translate(x, y, z));
}

function push(out: Map<Mat, THREE.BufferGeometry[]>, mat: Mat, g: THREE.BufferGeometry) {
  // one attribute layout for merging (BoxGeometry/PlaneGeometry/ExtrudeGeometry all have position, normal, uv)
  if (!out.has(mat)) out.set(mat, []);
  out.get(mat)!.push(g.index ? g.toNonIndexed() : g);
}

/** Body cross-section: straight sides, a shallow roof with rounded shoulders. */
function shell(w: number) {
  const { bottom, eave, roof } = TRAIN;
  const s = new THREE.Shape();
  s.moveTo(-w / 2, bottom);
  s.lineTo(w / 2, bottom);
  s.lineTo(w / 2, eave);
  s.lineTo(w / 2 - 0.28, eave + 0.34);
  s.lineTo(w / 2 - 0.85, roof - 0.03);
  s.lineTo(-w / 2 + 0.85, roof - 0.03);
  s.lineTo(-w / 2 + 0.28, eave + 0.34);
  s.lineTo(-w / 2, eave);
  s.closePath();
  return new THREE.ExtrudeGeometry(s, { depth: TRAIN.body, bevelEnabled: false }).translate(0, 0, -TRAIN.body / 2);
}

/** Door centres of a 20 m four-door commuter car. */
const DOORS = [-7.2, -2.4, 2.4, 7.2];

/** Side windows, doors and livery bands of one car. */
function sides(out: Map<Mat, THREE.BufferGeometry[]>, t: TrainInfo, liv: Livery, cab: number) {
  const w = t.width, L = TRAIN.body / 2;
  // windows between the doors (and towards the ends; a cab end has the cab window instead)
  const gaps: [number, number][] = [[-L + 0.9, -7.95], [-6.45, -3.15], [-1.65, 1.65], [3.15, 6.45], [7.95, L - 0.9]];
  for (const [z0, z1] of gaps) {
    if ((cab > 0 && z1 > 7) || (cab < 0 && z0 < -7)) {
      // cab: a short window for the driver, the rest body
      const zc = cab > 0 ? L - 1.1 : -L + 1.1;
      side(out, 'glass', w, zc - 0.35, zc + 0.35, 2.05, 2.8);
      continue;
    }
    side(out, 'glass', w, z0 + 0.15, z1 - 0.15, 1.95, 2.85);
  }
  const doorMat: Mat = t.front === 'e235' || t.front === 'tobu50000' ? 'band' : 'door';
  for (const z of DOORS) {
    side(out, doorMat, w, z - 0.68, z + 0.68, 1.12, 3.0, 0.006);
    side(out, 'glass', w, z - 0.5, z - 0.08, 1.95, 2.75, 0.01);
    side(out, 'glass', w, z + 0.08, z + 0.5, 1.95, 2.75, 0.01);
  }
  // bands (the length of the car; the doors cover them where they cross)
  const run = (mat: Mat, y0: number, y1: number) => side(out, mat, w, -L + 0.05, L - 0.05, y0, y1, 0.005);
  switch (t.front) {
    case 'e235':
      run('band', 3.0, 3.12);
      break;
    case 'e231':
      run('band', 1.72, 1.9);
      if (liv.band2) run('band2', 1.9, 1.98);
      run('band', 2.9, 3.0);
      break;
    case 'tobu50000':
      if (liv.band2) run('band', 2.9, 3.05);
      break;
    case 'tobu60000':
      run('band', 2.92, 3.08);
      for (const z of DOORS) side(out, 'band2', w, z + 0.7, z + 0.82, 1.2, 2.95, 0.007);
      break;
    case 'tobu8000':
      if (liv.band2) {
        run('band', 1.68, 1.82);
        run('band2', 1.6, 1.66);
        run('band', 2.92, 3.02);
      }
      break;
    case 'tobu10000':
    case 'tobu30000':
      run('band', 1.72, 1.86);
      break;
    case 'jnr103':
      break;
  }
}

/** Cab end: windscreen, destination sign, head and tail lamps and the colour of each series' face. */
function cabFace(out: Map<Mat, THREE.BufferGeometry[]>, t: TrainInfo, liv: Livery, dir: number) {
  const w = t.width, z = dir * (TRAIN.body / 2 + 0.012), hw = w / 2 - 0.05;
  const f = t.front;
  const lampY = f === 'tobu8000' || f === 'jnr103' ? 3.25 : 1.42;
  // face base
  const base: Mat = f === 'e235' || f === 'e231' || f === 'tobu50000' ? 'mask' : 'body';
  face(out, base, z, dir, -hw, hw, TRAIN.bottom, 3.25);
  const z2 = z + dir * 0.006;
  if (f === 'e235') face(out, 'band', z2, dir, -hw, hw, 3.0, 3.3);
  if (f === 'e231') {
    face(out, 'band', z2, dir, -hw, -hw + 0.32, TRAIN.bottom, 3.2);
    face(out, 'band', z2, dir, hw - 0.32, hw, TRAIN.bottom, 3.2);
  }
  if (f === 'tobu50000') face(out, liv.band2 ? 'band2' : 'band', z2, dir, -hw, hw, TRAIN.bottom, 1.7);
  if (f === 'tobu60000') face(out, 'band', z2, dir, -hw, hw, TRAIN.bottom, 1.75);
  if (f === 'tobu10000') face(out, 'lower', z2, dir, -0.8, 0.8, 1.9, 3.15);
  if (f === 'tobu8000' && liv.band2) face(out, 'band', z2, dir, -hw, hw, 1.62, 1.82);
  if (f === 'tobu10000' || f === 'tobu30000') face(out, 'band', z2, dir, -hw, hw, 1.72, 1.86);
  // windscreen: one sheet, or two with the through door between them
  const z3 = z2 + dir * 0.006;
  if (f === 'tobu8000' || f === 'tobu10000' || f === 'tobu30000' || f === 'jnr103') {
    face(out, 'glass', z3, dir, -hw + 0.18, -0.55, 2.0, 2.95);
    face(out, 'glass', z3, dir, 0.55, hw - 0.18, 2.0, 2.95);
    face(out, 'glass', z3, dir, -0.38, 0.38, 1.95, 2.9);
    face(out, 'dark', z2, dir, -0.45, 0.45, 1.05, 3.0);
  } else face(out, 'glass', z3, dir, -hw + 0.15, hw - 0.15, 1.95, 2.95);
  // destination sign
  face(out, 'sign', z3 + dir * 0.004, dir, -0.55, 0.55, f === 'jnr103' ? 2.95 : 2.98, f === 'jnr103' ? 3.12 : 3.2);
  // lamps: head (white) outside, tail (red) inside; the leading end shows white, the far end red
  const lz = z3 + dir * 0.006;
  const lead = dir > 0;
  if (f === 'jnr103') {
    face(out, lead ? 'head' : 'dark', lz, dir, -0.2, 0.2, 3.28, 3.45);
  } else {
    for (const s of [1, -1]) face(out, lead ? 'head' : 'dark', lz, dir, s * 0.95 - 0.16, s * 0.95 + 0.16, lampY - 0.07, lampY + 0.07);
  }
  const tailY = f === 'jnr103' ? 1.42 : lampY;
  for (const s of [1, -1]) face(out, lead ? 'dark' : 'tail', lz, dir, s * 1.18 - 0.07, s * 1.18 + 0.07, tailY - 0.06, tailY + 0.06);
  // skirt under the cab
  box(out, 'dark', 0, 0.78, dir * (TRAIN.body / 2 - 0.25), w - 0.4, 0.34, 0.12);
}

/** Bogies, underfloor equipment, roof units, pantograph (on the middle car), gangways. */
function running(out: Map<Mat, THREE.BufferGeometry[]>, t: TrainInfo, ends: [number, number], panto: boolean) {
  const r = t.wheel / 2;
  for (const zb of [TRAIN.bogies / 2, -TRAIN.bogies / 2]) {
    for (const s of [1, -1]) box(out, 'dark', s * 1.0, r + 0.12, zb, 0.14, 0.42, 2.7);
    box(out, 'dark', 0, r + 0.25, zb, 2.0, 0.22, 0.5);
    for (const za of [-1.05, 1.05]) {
      for (const s of [1, -1]) {
        const wheel = new THREE.CylinderGeometry(r, r, 0.14, 18).rotateZ(Math.PI / 2).translate(s * 0.72, r, zb + za);
        push(out, 'dark', wheel);
      }
    }
  }
  box(out, 'dark', 0, 0.72, 0, t.width - 0.6, 0.42, 7.5);
  box(out, 'roof', 0, TRAIN.roof + 0.15, 0, 2.1, 0.3, 4.2);
  if (panto) {
    box(out, 'dark', 0, TRAIN.roof + 0.08, -TRAIN.body / 2 + 3.2, 1.2, 0.14, 1.2);
    push(out, 'dark', new THREE.BoxGeometry(0.05, 1.1, 0.05).rotateX(-0.7).translate(0, TRAIN.roof + 0.55, -TRAIN.body / 2 + 3.0));
    push(out, 'dark', new THREE.BoxGeometry(0.05, 0.9, 0.05).rotateX(0.75).translate(0, TRAIN.roof + 0.95, -TRAIN.body / 2 + 2.9));
    box(out, 'dark', 0, TRAIN.roof + 1.28, -TRAIN.body / 2 + 3.2, 1.6, 0.05, 0.12);
  }
  // gangway ends between cars
  for (const [i, dir] of [[0, 1], [1, -1]] as const) {
    if (!ends[i]) continue;
    face(out, 'dark', dir * (TRAIN.body / 2 + 0.01), dir, -0.55, 0.55, 1.15, 3.0);
  }
}

function materials(t: TrainInfo, liv: Livery) {
  const metal = t.body !== 'painted';
  const body = new THREE.MeshStandardMaterial({
    color: metal ? (t.body === 'stainless' ? '#c7ccd1' : '#d4d7da') : (liv.body ?? '#f2f1ea'),
    metalness: metal ? 0.8 : 0.1,
    roughness: metal ? 0.4 : 0.5,
    envMapIntensity: 1.1,
  });
  const std = (color: string, extra: THREE.MeshStandardMaterialParameters = {}) => new THREE.MeshStandardMaterial({ color, roughness: 0.5, ...extra });
  return {
    body,
    band: std(liv.band),
    band2: std(liv.band2 ?? liv.band),
    door: body,
    glass: std('#10161c', { metalness: 0.5, roughness: 0.12, envMapIntensity: 1.4 }),
    mask: std('#14171b', { metalness: 0.3, roughness: 0.25 }),
    dark: std('#2a2c30', { metalness: 0.4, roughness: 0.7 }),
    roof: std(metal ? '#9ea3a8' : '#6d6f72', { metalness: 0.3, roughness: 0.6 }),
    sign: std('#201000', { emissive: '#ffb347', emissiveIntensity: 1.1 }),
    lower: std('#1e2a5a', { roughness: 0.4 }),
  };
}

/** brightness of the lit side windows at night */
const WINDOW_GLOW = 1.5;

/**
 * Night interior light of a model car: texels that are dark, face sideways and lie in the window band glow
 * (the models bake their windows into textures or plain dark colours, so there is no glass part to light).
 * `toCar`: the mesh's transform into the car's frame (meshopt quantization leaves a scale on every mesh).
 */
function lightWindows(mat: THREE.Material, uniforms: { uWinGlow: { value: number }; uWinBand: { value: THREE.Vector3 } }, toCar: THREE.Matrix4) {
  const own = { uToCar: { value: toCar }, uToCarN: { value: new THREE.Matrix3().getNormalMatrix(toCar) } };
  mat.onBeforeCompile = (shader) => {
    Object.assign(shader.uniforms, uniforms, own);
    shader.vertexShader = shader.vertexShader
      .replace('#include <common>', '#include <common>\nuniform mat4 uToCar;\nuniform mat3 uToCarN;\nvarying vec3 vCarPos;\nvarying vec3 vCarNrm;')
      .replace('#include <begin_vertex>', '#include <begin_vertex>\nvCarPos = (uToCar * vec4(position, 1.0)).xyz;\nvCarNrm = uToCarN * normal;');
    shader.fragmentShader = shader.fragmentShader
      .replace('#include <common>', '#include <common>\nuniform float uWinGlow;\nuniform vec3 uWinBand;\nvarying vec3 vCarPos;\nvarying vec3 vCarNrm;')
      .replace(
        '#include <emissivemap_fragment>',
        /* glsl */ `#include <emissivemap_fragment>
        float winLum = dot(diffuseColor.rgb, vec3(0.2126, 0.7152, 0.0722));
        float win = (1.0 - smoothstep(uWinBand.z * 0.3, uWinBand.z, winLum)) * smoothstep(0.6, 0.85, abs(normalize(vCarNrm).x))
          * smoothstep(uWinBand.x - 0.02, uWinBand.x + 0.04, vCarPos.y) * (1.0 - smoothstep(uWinBand.y - 0.04, uWinBand.y + 0.02, vCarPos.y));
        totalEmissiveRadiance += uWinGlow * win * vec3(1.0, 0.93, 0.8);`,
      );
  };
  mat.customProgramCacheKey = () => 'train-windows';
}

/**
 * Lenses for a pair of lamps on a model's cab end (`end` 1 = front, -1 = rear): each sits on the surface a ray from
 * ahead of the cab hits, a hair off it and facing out. Returns the lens centres (car frame).
 */
export function fitLamps(car: THREE.Object3D, pair: LampPair, end: number, reach: number, mat: THREE.Material) {
  car.updateMatrixWorld(true);
  const meshes: THREE.Object3D[] = [];
  car.traverse((o) => {
    if ((o as THREE.Mesh).isMesh) meshes.push(o);
  });
  const geo = pair.round ? new THREE.CircleGeometry(0.5, 20).scale(pair.w, pair.h, 1) : new THREE.PlaneGeometry(pair.w, pair.h);
  const ray = new THREE.Raycaster();
  const out: THREE.Vector3[] = [];
  for (const s of [1, -1]) {
    ray.set(new THREE.Vector3(s * pair.x, pair.y, end * (reach + 3)), new THREE.Vector3(0, 0, -end));
    const hit = ray.intersectObjects(meshes, false)[0];
    if (!hit) continue;
    const n = hit.face ? hit.face.normal.clone().transformDirection(hit.object.matrixWorld) : new THREE.Vector3(0, 0, end);
    // the models are double-sided: face the lens towards the side the ray came from
    if (n.z * end < 0) n.negate();
    const lens = new THREE.Mesh(geo, mat);
    lens.position.copy(hit.point).addScaledVector(n, 0.015);
    lens.lookAt(_c.copy(lens.position).add(n));
    car.add(lens);
    out.push(lens.position.clone());
  }
  return out;
}

export function buildTrain(spec: CarSpec, opts: { bodyColor?: string } = {}): CarRig & { train: TrainRig } {
  const t = spec.train!;
  const pick = (c?: string) => t.liveries.find((l) => l.band === c) ?? (c ? { ...t.liveries[0], band: c, band2: c } : t.liveries[0]);
  let liv = pick(opts.bodyColor);
  const carMats = createCarMaterials(spec, liv.band);
  const m = materials(t, liv);
  const all: Record<Mat, THREE.Material> = { ...m, head: carMats.headlight, tail: carMats.taillight };

  const root = new THREE.Group();
  root.name = `train-${spec.id}`;
  const body = new THREE.Group();
  root.add(body);
  // the vehicle sim drives four wheels: empty stand-ins (the bogies are drawn with the cars)
  const wheels = [0, 1, 2, 3].map(() => {
    const pivot = new THREE.Group(), spin = new THREE.Group();
    pivot.add(spin);
    root.add(pivot);
    return { pivot, spin };
  });
  // the cars: placed in world space every frame (their container cancels the rig's own transform)
  const consist = new THREE.Group();
  consist.matrixAutoUpdate = false;
  root.add(consist);
  const cars: THREE.Group[] = [];
  const model = models.get(spec.id);
  // window band (y from, to) and the luminance up to which a texel there is window
  const windows = { uWinGlow: { value: 0 }, uWinBand: { value: new THREE.Vector3(...(t.lamps?.windows ?? [0, 0]), t.lamps?.windowLum ?? 0.1) } };
  for (let k = 0; k < TRAIN.cars; k++) {
    const car = new THREE.Group();
    car.matrixAutoUpdate = false;
    if (model) {
      // the model's car (shared geometry, own copies of the materials so ghosts can recolour them)
      const piece = model[k].clone(true);
      piece.position.set(0, 0, 0);
      piece.updateMatrixWorld(true);
      piece.traverse((o) => {
        const m = o as THREE.Mesh;
        if (!m.isMesh) return;
        m.material = (m.material as THREE.Material).clone();
        if (t.lamps) lightWindows(m.material as THREE.Material, windows, m.matrixWorld.clone());
        m.castShadow = true;
        m.receiveShadow = true;
      });
      car.add(piece);
      consist.add(car);
      cars.push(car);
      continue;
    }
    const parts = new Map<Mat, THREE.BufferGeometry[]>();
    push(parts, 'body', shell(t.width));
    const cab = k === 0 ? 1 : k === TRAIN.cars - 1 ? -1 : 0;
    sides(parts, t, liv, cab);
    if (cab) cabFace(parts, t, liv, cab);
    running(parts, t, [k > 0 ? 1 : 0, k < TRAIN.cars - 1 ? 1 : 0], k === 1);
    for (const [mat, geos] of parts) {
      // drawn at the standard 20 m, stretched to the train's car length
      const mesh = new THREE.Mesh(mergeGeometries(geos)!.scale(1, 1, trainCars(t)[k].length / TRAIN.pitch), all[mat]);
      mesh.castShadow = true;
      mesh.receiveShadow = true;
      car.add(mesh);
    }
    consist.add(car);
    cars.push(car);
  }

  const path = new TrainPath();
  const bogiePath = trainBogiePath(t);
  const train: TrainRig = {
    update(anchor) {
      anchor.updateWorldMatrix(true, false);
      _c.setFromMatrixPosition(anchor.matrixWorld);
      _f.set(0, 0, 1).transformDirection(anchor.matrixWorld);
      path.advance(_c, _f);
      consist.matrix.copy(anchor.matrixWorld).invert();
      consist.matrixWorldNeedsUpdate = true;
      cars.forEach((car, k) => {
        const front = path.at(bogiePath[k][0], _d);
        const rear = path.at(bogiePath[k][1], _r);
        _z.subVectors(front, rear).normalize();
        _x.crossVectors(UP, _z).normalize();
        _y.crossVectors(_z, _x);
        _m.makeBasis(_x, _y, _z).setPosition(_e.addVectors(front, rear).multiplyScalar(0.5));
        car.matrix.copy(_m);
        car.matrixWorldNeedsUpdate = true;
      });
    },
    setLivery(color) {
      // a model keeps its own paint
      if (model) return;
      liv = pick(color);
      m.band.color.set(liv.band);
      m.band2.color.set(liv.band2 ?? liv.band);
      if (t.body === 'painted') m.body.color.set(liv.body ?? '#f2f1ea');
    },
    setInterior(level) {
      windows.uWinGlow.value = level * WINDOW_GLOW;
    },
  };

  // headlights on the leading car (its own frame: the nose at trainNoseZ), so in a bend they turn with the body;
  // on the simulated bogie they swung across the front of the car
  const nose = trainNoseZ(t) - 0.2;
  const anchors = {
    exhaust: new THREE.Vector3(),
    headlights: [new THREE.Vector3(0.95, 1.42, nose), new THREE.Vector3(-0.95, 1.42, nose)],
    taillights: [] as THREE.Vector3[],
  };
  // a model's own lamps are only painted on: glowing lenses over them (head lamps lead, tail lamps trail)
  if (model && t.lamps) {
    const head = fitLamps(cars[0], t.lamps.head, 1, trainNoseZ(t), carMats.headlight);
    if (head.length) anchors.headlights = head;
    anchors.taillights = fitLamps(cars[TRAIN.cars - 1], t.lamps.tail, -1, trainTailZ(t), carMats.taillight);
  }
  return { root, body, wheels, materials: carMats, headlightTargets: [], anchors, train, lampParent: cars[0] };
}

