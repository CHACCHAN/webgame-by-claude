import * as THREE from 'three';

/**
 * The car select's framing checked against the vehicle itself.
 *
 * The picker (`ui/garage/picker.ts` `garageFramingFor`) aims the garage camera by a rule of thumb: a vehicle takes so
 * much height and width at a car's distance (`KindTraits.garage`). With a desktop's room that holds; a phone leaves
 * the vehicle a strip 70–110 px high above the card, and there the rule's misses showed (11-20, at 844×390): cars
 * stood 10–20 px low, a bike's rider 20–40 px, and a train's leading car, its near end looming, reached past the
 * strip's ends. So the game, which knows the vehicle's shape, takes points of it through the camera at points of the
 * camera's swing and, when they leave the free part of the screen, steps the camera back until they fit and aims it
 * to put them in the middle of it. A vehicle that fits keeps the picker's framing exactly. A camera further out can
 * have something by the road between it and the vehicle (天狼's name board hid half the cockroach at one end of the
 * swing, the Cybertruck's tail once the camera stood back; from the valley side the guardrail crossed the wheels):
 * what stands there is looked at triangle by triangle (`roadsideOccluders`, `hiddenShare`), and the camera takes the
 * side of the road, and the part of its swing (`clearSwing`), from which the vehicle is seen whole at the distance it
 * needs (`Game.fitGarage`). Only in the phone's layout (the picker hands on the free part there
 * only): on a desktop some vehicles reach past their part too (the Cybertruck's tail, a Shinkansen's nose and the
 * cockroach's antennae past the screen's right edge at 1920×1080), but its framing was to stay as it is.
 */

/** where the garage camera puts the vehicle: aim right of and above it (m at a car's distance), a factor on the distance */
export interface Framing {
  right: number;
  up: number;
  zoom: number;
  /** the part of the swing (−1…1, `SWING_SAMPLES`' scale) the camera keeps to: something by the road stands in the rest */
  swing?: readonly [number, number];
}

/** the swing points `SWING_SAMPLES` within the part `swing` of it */
export const swingSamples = (swing?: readonly [number, number]) => (swing ? SWING_SAMPLES.map((s) => swing[0] + ((s + 1) / 2) * (swing[1] - swing[0])) : SWING_SAMPLES);

/**
 * The widest run of `clear` points over the swing (`count` of them, evenly from −1 to 1), as the part of the swing it
 * spans, or null where none is.
 */
export function clearSwing(count: number, clear: (swing: number) => boolean): [number, number] | null {
  let best: [number, number] | null = null, start = -1;
  const at = (i: number) => -1 + (2 * i) / (count - 1);
  for (let i = 0; i <= count; i++) {
    const ok = i < count && clear(at(i));
    if (ok && start < 0) start = i;
    if (!ok && start >= 0) {
      if (!best || at(i - 1) - at(start) > best[1] - best[0]) best = [at(start), at(i - 1)];
      start = -1;
    }
  }
  return best;
}

/** a part of the screen in normalised device coordinates (x −1…1 left to right, y −1…1 bottom to top) */
export interface ScreenBox {
  left: number;
  right: number;
  top: number;
  bottom: number;
}

/** the camera's swing (`Game.garageCamera`: sin(angle) × 0.75 rad) is looked at in these points */
export const SWING_SAMPLES = [-1, -2 / 3, -1 / 3, 0, 1 / 3, 2 / 3, 1];
/** air left between the vehicle and the free part's edges, as a share of its height (the same in pixels sideways) */
export const FIT_AIR = 0.05;
/** half the screen's height at the standard distance (8.6 m, 38° field of view), m */
const HALF_HEIGHT = Math.tan((19 * Math.PI) / 180) * 8.6;

/**
 * Points on a vehicle's surface in world space (x, y, z, …): the extremes along the axes and the diagonals of the
 * ground (an antenna's tip is a handful of vertices) among some 12 000 of its vertices, and an even share of them, at
 * most about `budget` (a car's model has 30–60 000: all of them took 6–8 ms here, a phone's processor takes 3–4
 * times as long). Parts that are not drawn, and glows and beams (see-through without depth), are left out.
 */
export function vehicleHull(scope: THREE.Object3D, budget = 700): Float32Array {
  scope.updateWorldMatrix(true, true);
  const meshes: THREE.Mesh[] = [];
  let total = 0;
  scope.traverseVisible((o) => {
    const mesh = o as THREE.Mesh;
    if (!mesh.isMesh || !mesh.geometry?.attributes.position) return;
    const mat = (Array.isArray(mesh.material) ? mesh.material[0] : mesh.material) as THREE.Material | undefined;
    if (mat && mat.transparent && !mat.depthWrite) return;
    meshes.push(mesh);
    total += mesh.geometry.attributes.position.count * ((mesh as THREE.InstancedMesh).isInstancedMesh ? (mesh as THREE.InstancedMesh).count : 1);
  });
  // (every `look`-th vertex is looked at; every `step`-th of those is kept)
  const look = Math.max(1, Math.round(total / 12000));
  const step = Math.max(1, Math.ceil(total / look / budget));
  const out: number[] = [];
  const v = new THREE.Vector3(), m = new THREE.Matrix4(), im = new THREE.Matrix4();
  // the farthest point along +x, −x, +y, −y, +z, −z and the four diagonals of the ground (x + z, −x − z, x − z, z − x)
  const best = new Float64Array(10).fill(-Infinity), at = new Float64Array(30);
  const keep = (j: number, d: number) => {
    if (d <= best[j]) return;
    best[j] = d;
    at[3 * j] = v.x;
    at[3 * j + 1] = v.y;
    at[3 * j + 2] = v.z;
  };
  let n = 0;
  for (const mesh of meshes) {
    const pos = mesh.geometry.attributes.position;
    const inst = (mesh as THREE.InstancedMesh).isInstancedMesh ? (mesh as THREE.InstancedMesh) : null;
    const skinned = (mesh as THREE.SkinnedMesh).isSkinnedMesh;
    for (let k = 0; k < (inst ? inst.count : 1); k++) {
      if (inst) m.multiplyMatrices(mesh.matrixWorld, (inst.getMatrixAt(k, im), im));
      else m.copy(mesh.matrixWorld);
      for (let i = k % look; i < pos.count; i += look, n++) {
        // (a skinned part as it stands: bones applied)
        if (skinned) mesh.getVertexPosition(i, v);
        else v.set(pos.getX(i), pos.getY(i), pos.getZ(i));
        v.applyMatrix4(m);
        keep(0, v.x), keep(1, -v.x), keep(2, v.y), keep(3, -v.y), keep(4, v.z), keep(5, -v.z);
        keep(6, v.x + v.z), keep(7, -v.x - v.z), keep(8, v.x - v.z), keep(9, v.z - v.x);
        if (n % step === 0) out.push(v.x, v.y, v.z);
      }
    }
  }
  for (let j = 0; j < 10; j++) if (best[j] > -Infinity) out.push(at[3 * j], at[3 * j + 1], at[3 * j + 2]);
  return new Float32Array(out);
}

/** the share of the vehicle that may stand behind something by the road before the camera stays nearer instead */
export const HIDDEN_OK = 0.05;

/**
 * Something by the road that could stand between the garage camera and its vehicle (a sign and its post, a lamp, a
 * vending machine, a cone, a banner): its geometry, and how to take a point into its own space.
 */
export interface Occluder {
  /** world → its own space */
  inverse: THREE.Matrix4;
  geometry: THREE.BufferGeometry;
  /** its bounding sphere in the world */
  centre: THREE.Vector3;
  radius: number;
}

/** the cells (m, across the ground) a large part's triangles near the garage are kept in: the box test passes over most */
const CELL = 6;

/**
 * What of `scope` (the course's scenery) within `within` m of `near` could stand between the garage camera and the
 * vehicle, as occluders: a small thing (bounding sphere at most `largest` m: a sign, a post, a lamp, a vending
 * machine, a cone) whole; of a large one (the rails, walls and gantries merged along the road) its triangles there,
 * in cells of `CELL` m. Not what `skip` names (the land and the road, whose own rules look after them; the forest,
 * which the garage clears round the camera), nor glows (see-through without depth).
 */
export function roadsideOccluders(scope: THREE.Object3D, near: THREE.Vector3, within: number, skip: (o: THREE.Object3D) => boolean, largest = 8): Occluder[] {
  scope.updateWorldMatrix(true, true);
  const out: Occluder[] = [];
  const m = new THREE.Matrix4(), im = new THREE.Matrix4(), sphere = new THREE.Sphere();
  const a = new THREE.Vector3(), b = new THREE.Vector3(), c = new THREE.Vector3();
  const cells = new Map<string, number[]>();
  const walk = (o: THREE.Object3D) => {
    if (!o.visible || skip(o)) return;
    const mesh = o as THREE.Mesh;
    const mat = (Array.isArray(mesh.material) ? mesh.material[0] : mesh.material) as THREE.Material | undefined;
    if (mesh.isMesh && mesh.geometry?.attributes.position && !(mat && mat.transparent && !mat.depthWrite)) {
      const g = mesh.geometry;
      if (!g.boundingSphere) g.computeBoundingSphere();
      if (!g.boundingBox) g.computeBoundingBox();
      const inst = (mesh as THREE.InstancedMesh).isInstancedMesh ? (mesh as THREE.InstancedMesh) : null;
      for (let k = 0; k < (inst ? inst.count : 1); k++) {
        if (inst) m.multiplyMatrices(mesh.matrixWorld, (inst.getMatrixAt(k, im), im));
        else m.copy(mesh.matrixWorld);
        // (an instance scaled to nothing is not there)
        if (Math.abs(m.determinant()) < 1e-9) continue;
        sphere.copy(g.boundingSphere!).applyMatrix4(m);
        if (sphere.center.distanceTo(near) > within + sphere.radius) continue;
        if (sphere.radius <= largest) {
          out.push({ inverse: m.clone().invert(), geometry: g, centre: sphere.center.clone(), radius: sphere.radius });
          continue;
        }
        const pos = g.attributes.position, index = g.index, n = index ? index.count : pos.count;
        for (let i = 0; i + 2 < n; i += 3) {
          a.fromBufferAttribute(pos, index ? index.getX(i) : i).applyMatrix4(m);
          b.fromBufferAttribute(pos, index ? index.getX(i + 1) : i + 1).applyMatrix4(m);
          c.fromBufferAttribute(pos, index ? index.getX(i + 2) : i + 2).applyMatrix4(m);
          // (the triangle's box against the cube round `near`)
          if (Math.max(a.x, b.x, c.x) < near.x - within || Math.min(a.x, b.x, c.x) > near.x + within) continue;
          if (Math.max(a.z, b.z, c.z) < near.z - within || Math.min(a.z, b.z, c.z) > near.z + within) continue;
          if (Math.max(a.y, b.y, c.y) < near.y - within || Math.min(a.y, b.y, c.y) > near.y + within) continue;
          const key = `${Math.floor((a.x + b.x + c.x) / 3 / CELL)},${Math.floor((a.z + b.z + c.z) / 3 / CELL)}`;
          let list = cells.get(key);
          if (!list) cells.set(key, (list = []));
          list.push(a.x, a.y, a.z, b.x, b.y, b.z, c.x, c.y, c.z);
        }
      }
    }
    for (const child of o.children) walk(child);
  };
  walk(scope);
  const identity = new THREE.Matrix4();
  for (const list of cells.values()) {
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(list, 3));
    g.computeBoundingBox();
    g.computeBoundingSphere();
    out.push({ inverse: identity, geometry: g, centre: g.boundingSphere!.center.clone(), radius: g.boundingSphere!.radius });
  }
  return out;
}

const _e = new THREE.Vector3(), _p = new THREE.Vector3(), _d = new THREE.Vector3(), _c = new THREE.Vector3();
const _t0 = new THREE.Vector3(), _t1 = new THREE.Vector3(), _t2 = new THREE.Vector3(), _e1 = new THREE.Vector3(), _e2 = new THREE.Vector3(), _h = new THREE.Vector3(), _s = new THREE.Vector3(), _q = new THREE.Vector3();

/** where the segment a → a + d (parameter 0…1) enters and leaves `box`, or null where it misses it */
function boxSpan(a: THREE.Vector3, d: THREE.Vector3, box: THREE.Box3): [number, number] | null {
  let t0 = 0, t1 = 1;
  for (const ax of ['x', 'y', 'z'] as const) {
    const lo = box.min[ax], hi = box.max[ax];
    if (Math.abs(d[ax]) < 1e-12) {
      if (a[ax] < lo || a[ax] > hi) return null;
      continue;
    }
    let u = (lo - a[ax]) / d[ax], v = (hi - a[ax]) / d[ax];
    if (u > v) [u, v] = [v, u];
    t0 = Math.max(t0, u);
    t1 = Math.min(t1, v);
    if (t0 > t1) return null;
  }
  return [t0, t1];
}

/** whether one of the triangles of `g` crosses the segment a → a + d strictly between its ends (own space) */
function crossesTriangle(a: THREE.Vector3, d: THREE.Vector3, g: THREE.BufferGeometry, lo: number, hi: number): boolean {
  const pos = g.attributes.position, index = g.index;
  const n = index ? index.count : pos.count;
  for (let i = 0; i + 2 < n; i += 3) {
    const i0 = index ? index.getX(i) : i, i1 = index ? index.getX(i + 1) : i + 1, i2 = index ? index.getX(i + 2) : i + 2;
    _t0.fromBufferAttribute(pos, i0);
    _t1.fromBufferAttribute(pos, i1);
    _t2.fromBufferAttribute(pos, i2);
    // (Möller–Trumbore, either face)
    _e1.subVectors(_t1, _t0);
    _e2.subVectors(_t2, _t0);
    _h.crossVectors(d, _e2);
    const det = _e1.dot(_h);
    if (Math.abs(det) < 1e-12) continue;
    const f = 1 / det;
    _s.subVectors(a, _t0);
    const u = f * _s.dot(_h);
    if (u < 0 || u > 1) continue;
    _q.crossVectors(_s, _e1);
    const v = f * d.dot(_q);
    if (v < 0 || u + v > 1) continue;
    const t = f * _e2.dot(_q);
    if (t > lo && t < hi) return true;
  }
  return false;
}

/**
 * The share of the vehicle's points (`hull`, every `stride`-th) that one of `occluders` hides from `eye`: a point is
 * hidden where the line from the eye to it crosses one of an occluder's triangles on the way (only lines through its
 * box are followed that far: a lamp's box, pole and arm, is mostly air). Once more than `limit` of them is hidden the
 * count stops (the share returned is then above `limit`, not the whole of it).
 */
export function hiddenShare(eye: THREE.Vector3, hull: Float32Array, occluders: readonly Occluder[], stride = 1, limit = 1): number {
  const count = Math.floor(hull.length / 3);
  if (!count || !occluders.length) return 0;
  // (only what stands near the line from the eye to the vehicle can hide any of it)
  let x0 = Infinity, y0 = Infinity, z0 = Infinity, x1 = -Infinity, y1 = -Infinity, z1 = -Infinity;
  for (let i = 0; i < hull.length; i += 3) {
    x0 = Math.min(x0, hull[i]), x1 = Math.max(x1, hull[i]);
    y0 = Math.min(y0, hull[i + 1]), y1 = Math.max(y1, hull[i + 1]);
    z0 = Math.min(z0, hull[i + 2]), z1 = Math.max(z1, hull[i + 2]);
  }
  _c.set((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2);
  const size = Math.hypot(x1 - x0, y1 - y0, z1 - z0) / 2;
  _d.subVectors(_c, eye);
  const len2 = _d.lengthSq();
  const near: { o: Occluder; eye: THREE.Vector3 }[] = [];
  for (const o of occluders) {
    const t = len2 > 0 ? Math.min(1, Math.max(0, _p.subVectors(o.centre, eye).dot(_d) / len2)) : 0;
    if (_p.copy(eye).addScaledVector(_d, t).distanceTo(o.centre) < o.radius + size) near.push({ o, eye: eye.clone().applyMatrix4(o.inverse) });
  }
  if (!near.length) return 0;
  const total = Math.ceil(count / stride);
  let tested = 0, hidden = 0;
  for (let i = 0; i < count && hidden <= limit * total; i += stride, tested++) {
    _p.set(hull[3 * i], hull[3 * i + 1], hull[3 * i + 2]);
    for (const { o, eye: a } of near) {
      _e.copy(_p).applyMatrix4(o.inverse);
      _d.subVectors(_e, a);
      // (not the last 0.5 %: the point itself is on the vehicle's surface)
      const span = boxSpan(a, _d, o.geometry.boundingBox!);
      if (!span || span[0] >= 0.995 || span[1] <= 0) continue;
      if (crossesTriangle(a, _d, o.geometry, Math.max(1e-4, span[0] - 1e-6), Math.min(0.995, span[1] + 1e-6))) {
        hidden++;
        break;
      }
    }
  }
  return tested ? hidden / (hidden > limit * total ? total : tested) : 0;
}

/** the part of `free` the vehicle may take: `FIT_AIR` of its height left on every side */
export function fitBox(free: ScreenBox, aspect: number): ScreenBox {
  const air = FIT_AIR * (free.top - free.bottom);
  return { left: free.left + air / aspect, right: free.right - air / aspect, top: free.top - air, bottom: free.bottom + air };
}

export const inside = (e: ScreenBox, box: ScreenBox) => e.left >= box.left && e.right <= box.right && e.top <= box.top && e.bottom >= box.bottom;

/**
 * The framing that keeps the vehicle inside `free` (NDC) at every point of the swing: the picker's own when it does
 * already (the same object's numbers, untouched); else the camera steps back (never nearer than the picker asked)
 * until the vehicle's extent fits, and is aimed so that it stands in the middle. `extent` gives the vehicle's extent
 * on the screen over the swing for a framing; the screen is `aspect` wide for its height of 1. `maxZoom` bounds the
 * distance (a vehicle that cannot fit is then only put in the middle).
 */
export function fitFraming(frame: Framing, free: ScreenBox, aspect: number, extent: (f: Framing) => ScreenBox, maxZoom: number): Framing {
  const fit = { right: frame.right, up: frame.up, zoom: frame.zoom };
  if (!(free.right > free.left && free.top > free.bottom)) return fit;
  const box = fitBox(free, aspect);
  let e = extent(fit);
  if (inside(e, box)) return fit;
  for (let i = 0; i < 12; i++) {
    const m = Math.max((e.right - e.left) / (box.right - box.left), (e.top - e.bottom) / (box.top - box.bottom));
    if (m > 1.003 && fit.zoom < maxZoom) {
      // (a hair more: the perspective changes with the distance)
      fit.zoom = Math.min(maxZoom, fit.zoom * m * 1.01);
    } else {
      // aiming right of the vehicle moves it left on the screen, aiming above it moves it down
      const dx = (box.left + box.right - e.left - e.right) / 2, dy = (box.top + box.bottom - e.top - e.bottom) / 2;
      if (Math.abs(dx) < 0.003 && Math.abs(dy) < 0.003) break;
      fit.right -= dx * HALF_HEIGHT * aspect;
      fit.up -= dy * HALF_HEIGHT;
    }
    e = extent(fit);
  }
  return fit;
}
