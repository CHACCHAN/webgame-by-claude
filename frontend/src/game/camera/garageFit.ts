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
 * The widest run of `clear` points over the swing (`count` of them, evenly from −1 to 1) at least `minWidth` wide,
 * as the part of the swing it spans, or null where none is. Jumps over spans that cannot reach the needed width so
 * blocked sides stop in a handful of probes.
 */
export function clearSwing(count: number, clear: (swing: number) => boolean, minWidth = 0): [number, number] | null {
  if (count < 2) return count === 1 && minWidth <= 0 && clear(0) ? [0, 0] : null;
  const step = 2 / (count - 1);
  const at = (i: number) => -1 + (2 * i) / (count - 1);
  let need = minWidth > 0 ? Math.max(0, Math.ceil((minWidth - 1e-9) / step)) : 0;
  let bestA = -1, bestSpan = -1;
  let left = 0;
  while (left + need < count) {
    const p = left + need;
    if (!clear(at(p))) {
      left = p + 1;
      continue;
    }
    let a = p;
    while (a > left && clear(at(a - 1))) a--;
    let b = p;
    while (b + 1 < count && clear(at(b + 1))) b++;
    const span = b - a;
    if (span >= need) {
      bestA = a;
      bestSpan = span;
      need = span + 1;
    }
    left = b + 2;
  }
  return bestA >= 0 ? [at(bestA), at(bestA + bestSpan)] : null;
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
  /** world-space bounding box [minX, minY, minZ, maxX, maxY, maxZ] (filled by `roadsideOccluders`) */
  worldBox?: Float32Array;
}

/** world-space AABB [minX, minY, minZ, maxX, maxY, maxZ] of local `box` transformed by affine matrix `m` */
function transformedBox(box: THREE.Box3, m: THREE.Matrix4): Float32Array {
  const me = m.elements;
  const cx = (box.min.x + box.max.x) * 0.5, cy = (box.min.y + box.max.y) * 0.5, cz = (box.min.z + box.max.z) * 0.5;
  const ex = (box.max.x - box.min.x) * 0.5, ey = (box.max.y - box.min.y) * 0.5, ez = (box.max.z - box.min.z) * 0.5;
  const wx = me[0] * cx + me[4] * cy + me[8] * cz + me[12];
  const wy = me[1] * cx + me[5] * cy + me[9] * cz + me[13];
  const wz = me[2] * cx + me[6] * cy + me[10] * cz + me[14];
  const rx = Math.abs(me[0]) * ex + Math.abs(me[4]) * ey + Math.abs(me[8]) * ez;
  const ry = Math.abs(me[1]) * ex + Math.abs(me[5]) * ey + Math.abs(me[9]) * ez;
  const rz = Math.abs(me[2]) * ex + Math.abs(me[6]) * ey + Math.abs(me[10]) * ez;
  const out = new Float32Array(6);
  out[0] = wx - rx; out[1] = wy - ry; out[2] = wz - rz;
  out[3] = wx + rx; out[4] = wy + ry; out[5] = wz + rz;
  return out;
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
  const cells = new Map<number, number[]>();
  const nx = near.x, ny = near.y, nz = near.z;
  const xLo = nx - within, xHi = nx + within;
  const yLo = ny - within, yHi = ny + within;
  const zLo = nz - within, zHi = nz + within;
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
          out.push({ inverse: m.clone().invert(), geometry: g, centre: sphere.center.clone(), radius: sphere.radius, worldBox: transformedBox(g.boundingBox!, m) });
          continue;
        }
        const pos = g.attributes.position, index = g.index, n = index ? index.count : pos.count;
        const flatPos = !(pos as THREE.InterleavedBufferAttribute).isInterleavedBufferAttribute && !pos.normalized && pos.itemSize === 3 ? (pos.array as ArrayLike<number>) : null;
        const idxArr = index ? (index.array as ArrayLike<number>) : null;
        const me = m.elements;
        const isId =
          me[0] === 1 && me[1] === 0 && me[2] === 0 && me[3] === 0 &&
          me[4] === 0 && me[5] === 1 && me[6] === 0 && me[7] === 0 &&
          me[8] === 0 && me[9] === 0 && me[10] === 1 && me[11] === 0 &&
          me[12] === 0 && me[13] === 0 && me[14] === 0 && me[15] === 1;
        const m0 = me[0], m4 = me[4], m8 = me[8], m12 = me[12];
        const m1 = me[1], m5 = me[5], m9 = me[9], m13 = me[13];
        const m2 = me[2], m6 = me[6], m10 = me[10], m14 = me[14];
        for (let i = 0; i + 2 < n; i += 3) {
          const i0 = idxArr ? idxArr[i] : i, i1 = idxArr ? idxArr[i + 1] : i + 1, i2 = idxArr ? idxArr[i + 2] : i + 2;
          let ax: number, ay: number, az: number, bx: number, by: number, bz: number, cx: number, cy: number, cz: number;
          if (flatPos) {
            const p0 = i0 * 3, p1 = i1 * 3, p2 = i2 * 3;
            ax = flatPos[p0]; ay = flatPos[p0 + 1]; az = flatPos[p0 + 2];
            bx = flatPos[p1]; by = flatPos[p1 + 1]; bz = flatPos[p1 + 2];
            cx = flatPos[p2]; cy = flatPos[p2 + 1]; cz = flatPos[p2 + 2];
          } else {
            ax = pos.getX(i0); ay = pos.getY(i0); az = pos.getZ(i0);
            bx = pos.getX(i1); by = pos.getY(i1); bz = pos.getZ(i1);
            cx = pos.getX(i2); cy = pos.getY(i2); cz = pos.getZ(i2);
          }
          if (!isId) {
            const tx0 = m0 * ax + m4 * ay + m8 * az + m12, ty0 = m1 * ax + m5 * ay + m9 * az + m13, tz0 = m2 * ax + m6 * ay + m10 * az + m14;
            const tx1 = m0 * bx + m4 * by + m8 * bz + m12, ty1 = m1 * bx + m5 * by + m9 * bz + m13, tz1 = m2 * bx + m6 * by + m10 * bz + m14;
            const tx2 = m0 * cx + m4 * cy + m8 * cz + m12, ty2 = m1 * cx + m5 * cy + m9 * cz + m13, tz2 = m2 * cx + m6 * cy + m10 * cz + m14;
            ax = tx0; ay = ty0; az = tz0; bx = tx1; by = ty1; bz = tz1; cx = tx2; cy = ty2; cz = tz2;
          }
          // (the triangle's box against the cube round `near`)
          if ((ax < xLo && bx < xLo && cx < xLo) || (ax > xHi && bx > xHi && cx > xHi)) continue;
          if ((az < zLo && bz < zLo && cz < zLo) || (az > zHi && bz > zHi && cz > zHi)) continue;
          if ((ay < yLo && by < yLo && cy < yLo) || (ay > yHi && by > yHi && cy > yHi)) continue;
          const gx = Math.floor((ax + bx + cx) / (3 * CELL)) + 32768;
          const gz = Math.floor((az + bz + cz) / (3 * CELL)) + 32768;
          const key = gx * 65536 + gz;
          let list = cells.get(key);
          if (!list) cells.set(key, (list = []));
          list.push(ax, ay, az, bx, by, bz, cx, cy, cz);
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
    const b = g.boundingBox!;
    const wb = new Float32Array(6);
    wb[0] = b.min.x; wb[1] = b.min.y; wb[2] = b.min.z; wb[3] = b.max.x; wb[4] = b.max.y; wb[5] = b.max.z;
    out.push({ inverse: identity, geometry: g, centre: g.boundingSphere!.center.clone(), radius: g.boundingSphere!.radius, worldBox: wb });
  }
  return out;
}

/**
 * Flat bounding-volume hierarchy over a geometry's triangles in its own space, built lazily on the first ray that
 * enters the geometry's box and kept per geometry via a WeakMap: a lamp's box is mostly air (2 478 triangles), a
 * vending machine has 7 240, so scanning every triangle per ray cost ~1 s on trains.
 */
interface TriAccel {
  /** leaf triangles packed contiguously: 9 floats per triangle (v0, e1 = v1 − v0, e2 = v2 − v0) */
  tris: Float32Array;
  /** node bounds: 6 floats per node (minX, minY, minZ, maxX, maxY, maxZ); empty when `count <= LEAF_TRIS` */
  nodes: Float32Array;
  /** 2 ints per node: leaf has `count > 0` at [2n+1] and `first` at [2n]; internal has `count = 0` and `right` at [2n] (left is `n + 1`) */
  meta: Int32Array;
  count: number;
}

const LEAF_TRIS = 12;
const EMPTY_F32 = new Float32Array(0);
const EMPTY_I32 = new Int32Array(0);
const _bvhStack = new Int32Array(64);
const accelCache = new WeakMap<THREE.BufferGeometry, TriAccel>();
const hullBoundsCache = new WeakMap<Float32Array, { cx: number; cy: number; cz: number; size: number }>();

function getAccel(g: THREE.BufferGeometry): TriAccel {
  const cached = accelCache.get(g);
  if (cached) return cached;
  const pos = g.attributes.position, index = g.index;
  const n = index ? index.count : pos.count;
  const count = Math.floor(n / 3);
  if (!count) {
    const empty: TriAccel = { tris: EMPTY_F32, nodes: EMPTY_F32, meta: EMPTY_I32, count: 0 };
    accelCache.set(g, empty);
    return empty;
  }
  const flatPos = !(pos as THREE.InterleavedBufferAttribute).isInterleavedBufferAttribute && !pos.normalized && pos.itemSize === 3 ? (pos.array as ArrayLike<number>) : null;
  const idxArr = index ? (index.array as ArrayLike<number>) : null;
  const raw = new Float32Array(count * 9);
  if (count <= LEAF_TRIS) {
    for (let t = 0; t < count; t++) {
      const k = t * 3;
      const i0 = idxArr ? idxArr[k] : k, i1 = idxArr ? idxArr[k + 1] : k + 1, i2 = idxArr ? idxArr[k + 2] : k + 2;
      let x0: number, y0: number, z0: number, x1: number, y1: number, z1: number, x2: number, y2: number, z2: number;
      if (flatPos) {
        const p0 = i0 * 3, p1 = i1 * 3, p2 = i2 * 3;
        x0 = flatPos[p0]; y0 = flatPos[p0 + 1]; z0 = flatPos[p0 + 2];
        x1 = flatPos[p1]; y1 = flatPos[p1 + 1]; z1 = flatPos[p1 + 2];
        x2 = flatPos[p2]; y2 = flatPos[p2 + 1]; z2 = flatPos[p2 + 2];
      } else {
        x0 = pos.getX(i0); y0 = pos.getY(i0); z0 = pos.getZ(i0);
        x1 = pos.getX(i1); y1 = pos.getY(i1); z1 = pos.getZ(i1);
        x2 = pos.getX(i2); y2 = pos.getY(i2); z2 = pos.getZ(i2);
      }
      const d = t * 9;
      raw[d] = x0; raw[d + 1] = y0; raw[d + 2] = z0;
      raw[d + 3] = x1 - x0; raw[d + 4] = y1 - y0; raw[d + 5] = z1 - z0;
      raw[d + 6] = x2 - x0; raw[d + 7] = y2 - y0; raw[d + 8] = z2 - z0;
    }
    const flat: TriAccel = { tris: raw, nodes: EMPTY_F32, meta: EMPTY_I32, count };
    accelCache.set(g, flat);
    return flat;
  }
  const bounds = new Float32Array(count * 6);
  const cent = new Float32Array(count * 3);
  const order = new Int32Array(count);
  for (let t = 0; t < count; t++) {
    order[t] = t;
    const k = t * 3;
    const i0 = idxArr ? idxArr[k] : k, i1 = idxArr ? idxArr[k + 1] : k + 1, i2 = idxArr ? idxArr[k + 2] : k + 2;
    let x0: number, y0: number, z0: number, x1: number, y1: number, z1: number, x2: number, y2: number, z2: number;
    if (flatPos) {
      const p0 = i0 * 3, p1 = i1 * 3, p2 = i2 * 3;
      x0 = flatPos[p0]; y0 = flatPos[p0 + 1]; z0 = flatPos[p0 + 2];
      x1 = flatPos[p1]; y1 = flatPos[p1 + 1]; z1 = flatPos[p1 + 2];
      x2 = flatPos[p2]; y2 = flatPos[p2 + 1]; z2 = flatPos[p2 + 2];
    } else {
      x0 = pos.getX(i0); y0 = pos.getY(i0); z0 = pos.getZ(i0);
      x1 = pos.getX(i1); y1 = pos.getY(i1); z1 = pos.getZ(i1);
      x2 = pos.getX(i2); y2 = pos.getY(i2); z2 = pos.getZ(i2);
    }
    const d = t * 9;
    raw[d] = x0; raw[d + 1] = y0; raw[d + 2] = z0;
    raw[d + 3] = x1 - x0; raw[d + 4] = y1 - y0; raw[d + 5] = z1 - z0;
    raw[d + 6] = x2 - x0; raw[d + 7] = y2 - y0; raw[d + 8] = z2 - z0;
    const minX = x0 < x1 ? (x0 < x2 ? x0 : x2) : (x1 < x2 ? x1 : x2);
    const maxX = x0 > x1 ? (x0 > x2 ? x0 : x2) : (x1 > x2 ? x1 : x2);
    const minY = y0 < y1 ? (y0 < y2 ? y0 : y2) : (y1 < y2 ? y1 : y2);
    const maxY = y0 > y1 ? (y0 > y2 ? y0 : y2) : (y1 > y2 ? y1 : y2);
    const minZ = z0 < z1 ? (z0 < z2 ? z0 : z2) : (z1 < z2 ? z1 : z2);
    const maxZ = z0 > z1 ? (z0 > z2 ? z0 : z2) : (z1 > z2 ? z1 : z2);
    const b = t * 6;
    bounds[b] = minX; bounds[b + 1] = minY; bounds[b + 2] = minZ;
    bounds[b + 3] = maxX; bounds[b + 4] = maxY; bounds[b + 5] = maxZ;
    cent[k] = minX + maxX; cent[k + 1] = minY + maxY; cent[k + 2] = minZ + maxZ;
  }
  const maxNodes = count * 2;
  const nodes = new Float32Array(maxNodes * 6);
  const meta = new Int32Array(maxNodes * 2);
  let nodeCount = 0;
  const build = (start: number, end: number, depth: number): number => {
    const node = nodeCount++;
    let bx0 = Infinity, by0 = Infinity, bz0 = Infinity;
    let bx1 = -Infinity, by1 = -Infinity, bz1 = -Infinity;
    let cx0 = Infinity, cy0 = Infinity, cz0 = Infinity;
    let cx1 = -Infinity, cy1 = -Infinity, cz1 = -Infinity;
    for (let i = start; i < end; i++) {
      const t = order[i];
      const b = t * 6, c = t * 3;
      const x0 = bounds[b], y0 = bounds[b + 1], z0 = bounds[b + 2];
      const x1 = bounds[b + 3], y1 = bounds[b + 4], z1 = bounds[b + 5];
      if (x0 < bx0) bx0 = x0; if (y0 < by0) by0 = y0; if (z0 < bz0) bz0 = z0;
      if (x1 > bx1) bx1 = x1; if (y1 > by1) by1 = y1; if (z1 > bz1) bz1 = z1;
      const cx = cent[c], cy = cent[c + 1], cz = cent[c + 2];
      if (cx < cx0) cx0 = cx; if (cy < cy0) cy0 = cy; if (cz < cz0) cz0 = cz;
      if (cx > cx1) cx1 = cx; if (cy > cy1) cy1 = cy; if (cz > cz1) cz1 = cz;
    }
    const n6 = node * 6;
    nodes[n6] = bx0; nodes[n6 + 1] = by0; nodes[n6 + 2] = bz0;
    nodes[n6 + 3] = bx1; nodes[n6 + 4] = by1; nodes[n6 + 5] = bz1;
    const len = end - start;
    if (len <= LEAF_TRIS || depth >= 40) {
      meta[node * 2] = start;
      meta[node * 2 + 1] = len;
      return node;
    }
    const ex = cx1 - cx0, ey = cy1 - cy0, ez = cz1 - cz0;
    const axis = ex >= ey && ex >= ez ? 0 : ey >= ez ? 1 : 2;
    const span = axis === 0 ? ex : axis === 1 ? ey : ez;
    if (span < 1e-6) {
      meta[node * 2] = start;
      meta[node * 2 + 1] = len;
      return node;
    }
    const split = (axis === 0 ? cx0 + cx1 : axis === 1 ? cy0 + cy1 : cz0 + cz1) * 0.5;
    let i = start, j = end - 1;
    while (i <= j) {
      if (cent[order[i] * 3 + axis] < split) i++;
      else {
        const tmp = order[i]; order[i] = order[j]; order[j] = tmp;
        j--;
      }
    }
    const mid = i === start || i === end ? (start + end) >> 1 : i;
    build(start, mid, depth + 1);
    const right = build(mid, end, depth + 1);
    meta[node * 2] = right;
    meta[node * 2 + 1] = 0;
    return node;
  };
  build(0, count, 0);
  const tris = new Float32Array(count * 9);
  for (let i = 0; i < count; i++) {
    const src = order[i] * 9, dst = i * 9;
    tris[dst] = raw[src]; tris[dst + 1] = raw[src + 1]; tris[dst + 2] = raw[src + 2];
    tris[dst + 3] = raw[src + 3]; tris[dst + 4] = raw[src + 4]; tris[dst + 5] = raw[src + 5];
    tris[dst + 6] = raw[src + 6]; tris[dst + 7] = raw[src + 7]; tris[dst + 8] = raw[src + 8];
  }
  const accel: TriAccel = { tris, nodes: nodes.slice(0, nodeCount * 6), meta: meta.slice(0, nodeCount * 2), count };
  accelCache.set(g, accel);
  return accel;
}

/** entry parameter into the box `nodes[n6..n6+5]` within `[slo, shi]`, or −1 when the segment misses it */
function slabHit(nodes: Float32Array, n6: number, ax: number, ay: number, az: number, invX: number, invY: number, invZ: number, slo: number, shi: number): number {
  let t0 = slo, t1 = shi;
  if (invX !== 0) {
    let u = (nodes[n6] - ax) * invX, v = (nodes[n6 + 3] - ax) * invX;
    if (u > v) { const w = u; u = v; v = w; }
    if (u > t0) t0 = u;
    if (v < t1) t1 = v;
    if (t0 > t1 + 1e-7) return -1;
  } else if (ax < nodes[n6] - 1e-7 || ax > nodes[n6 + 3] + 1e-7) return -1;
  if (invY !== 0) {
    let u = (nodes[n6 + 1] - ay) * invY, v = (nodes[n6 + 4] - ay) * invY;
    if (u > v) { const w = u; u = v; v = w; }
    if (u > t0) t0 = u;
    if (v < t1) t1 = v;
    if (t0 > t1 + 1e-7) return -1;
  } else if (ay < nodes[n6 + 1] - 1e-7 || ay > nodes[n6 + 4] + 1e-7) return -1;
  if (invZ !== 0) {
    let u = (nodes[n6 + 2] - az) * invZ, v = (nodes[n6 + 5] - az) * invZ;
    if (u > v) { const w = u; u = v; v = w; }
    if (u > t0) t0 = u;
    if (v < t1) t1 = v;
    if (t0 > t1 + 1e-7) return -1;
  } else if (az < nodes[n6 + 2] - 1e-7 || az > nodes[n6 + 5] + 1e-7) return -1;
  return t0;
}

/** whether one of the packed triangles `[first .. first + len)` crosses a → a + d strictly inside `(lo, hi)` */
function hitTris(tris: Float32Array, first: number, len: number, ax: number, ay: number, az: number, dx: number, dy: number, dz: number, lo: number, hi: number): boolean {
  for (let i = first * 9, end = (first + len) * 9; i < end; i += 9) {
    const v0x = tris[i], v0y = tris[i + 1], v0z = tris[i + 2];
    const e1x = tris[i + 3], e1y = tris[i + 4], e1z = tris[i + 5];
    const e2x = tris[i + 6], e2y = tris[i + 7], e2z = tris[i + 8];
    // (Möller–Trumbore, either face)
    const hx = dy * e2z - dz * e2y;
    const hy = dz * e2x - dx * e2z;
    const hz = dx * e2y - dy * e2x;
    const det = e1x * hx + e1y * hy + e1z * hz;
    if (det > -1e-12 && det < 1e-12) continue;
    const f = 1 / det;
    const sx = ax - v0x, sy = ay - v0y, sz = az - v0z;
    const u = f * (sx * hx + sy * hy + sz * hz);
    if (u < 0 || u > 1) continue;
    const qx = sy * e1z - sz * e1y;
    const qy = sz * e1x - sx * e1z;
    const qz = sx * e1y - sy * e1x;
    const v = f * (dx * qx + dy * qy + dz * qz);
    if (v < 0 || u + v > 1) continue;
    const t = f * (e2x * qx + e2y * qy + e2z * qz);
    if (t > lo && t < hi) return true;
  }
  return false;
}

/** whether the segment a → a + d enters `box` strictly inside `(0, 0.995)` */
function hitsBox(ax: number, ay: number, az: number, dx: number, dy: number, dz: number, box: THREE.Box3): boolean {
  let t0 = 0, t1 = 0.995;
  if (Math.abs(dx) >= 1e-12) {
    const inv = 1 / dx;
    let u = (box.min.x - ax) * inv, v = (box.max.x - ax) * inv;
    if (u > v) { const w = u; u = v; v = w; }
    if (u > t0) t0 = u;
    if (v < t1) t1 = v;
    if (t0 > t1) return false;
  } else if (ax < box.min.x || ax > box.max.x) return false;
  if (Math.abs(dy) >= 1e-12) {
    const inv = 1 / dy;
    let u = (box.min.y - ay) * inv, v = (box.max.y - ay) * inv;
    if (u > v) { const w = u; u = v; v = w; }
    if (u > t0) t0 = u;
    if (v < t1) t1 = v;
    if (t0 > t1) return false;
  } else if (ay < box.min.y || ay > box.max.y) return false;
  if (Math.abs(dz) >= 1e-12) {
    const inv = 1 / dz;
    let u = (box.min.z - az) * inv, v = (box.max.z - az) * inv;
    if (u > v) { const w = u; u = v; v = w; }
    if (u > t0) t0 = u;
    if (v < t1) t1 = v;
    if (t0 > t1) return false;
  } else if (az < box.min.z || az > box.max.z) return false;
  return t0 < 0.995 && t1 > 0;
}

/** whether one of the triangles of `accel` crosses the segment a → a + d strictly between `1e-4` and `0.995` */
function crossesAccel(ax: number, ay: number, az: number, dx: number, dy: number, dz: number, invX: number, invY: number, invZ: number, accel: TriAccel): boolean {
  const lo = 1e-4, hi = 0.995;
  if (accel.nodes.length === 0) return hitTris(accel.tris, 0, accel.count, ax, ay, az, dx, dy, dz, lo, hi);
  const slo = lo - 1e-6, shi = hi + 1e-6;
  const { tris, nodes, meta } = accel;
  let sp = 0, node = 0;
  for (;;) {
    const cnt = meta[node * 2 + 1];
    if (cnt > 0) {
      if (hitTris(tris, meta[node * 2], cnt, ax, ay, az, dx, dy, dz, lo, hi)) return true;
      if (sp === 0) return false;
      node = _bvhStack[--sp];
      continue;
    }
    const left = node + 1, right = meta[node * 2];
    const tl = slabHit(nodes, left * 6, ax, ay, az, invX, invY, invZ, slo, shi);
    const tr = slabHit(nodes, right * 6, ax, ay, az, invX, invY, invZ, slo, shi);
    if (tl >= 0 && tr >= 0) {
      if (tl <= tr) {
        _bvhStack[sp++] = right;
        node = left;
      } else {
        _bvhStack[sp++] = left;
        node = right;
      }
    } else if (tl >= 0) node = left;
    else if (tr >= 0) node = right;
    else {
      if (sp === 0) return false;
      node = _bvhStack[--sp];
    }
  }
}

interface NearOccluder {
  o: Occluder;
  box: THREE.Box3;
  accel: TriAccel | null;
  ax: number;
  ay: number;
  az: number;
  isId: boolean;
  me: number[];
}

let _nearBoxes = new Float32Array(256 * 6);
const _tmpMat = new THREE.Matrix4();

function testNearOccluder(
  item: NearOccluder,
  j6: number,
  ex: number,
  ey: number,
  ez: number,
  dx: number,
  dy: number,
  dz: number,
  invX: number,
  invY: number,
  invZ: number,
  px: number,
  py: number,
  pz: number,
): boolean {
  // quick world-space AABB slab test using the ray's precomputed inverse direction (zero divisions, zero matrix ops)
  if (slabHit(_nearBoxes, j6, ex, ey, ez, invX, invY, invZ, 0, 0.995) < 0) return false;
  if (item.isId) {
    const accel = (item.accel ??= getAccel(item.o.geometry));
    return crossesAccel(ex, ey, ez, dx, dy, dz, invX, invY, invZ, accel);
  }
  const me = item.me;
  const ldx = me[0] * px + me[4] * py + me[8] * pz + me[12] - item.ax;
  const ldy = me[1] * px + me[5] * py + me[9] * pz + me[13] - item.ay;
  const ldz = me[2] * px + me[6] * py + me[10] * pz + me[14] - item.az;
  // (not the last 0.5 %: the point itself is on the vehicle's surface)
  if (!hitsBox(item.ax, item.ay, item.az, ldx, ldy, ldz, item.box)) return false;
  const linvX = Math.abs(ldx) >= 1e-12 ? 1 / ldx : 0;
  const linvY = Math.abs(ldy) >= 1e-12 ? 1 / ldy : 0;
  const linvZ = Math.abs(ldz) >= 1e-12 ? 1 / ldz : 0;
  const accel = (item.accel ??= getAccel(item.o.geometry));
  return crossesAccel(item.ax, item.ay, item.az, ldx, ldy, ldz, linvX, linvY, linvZ, accel);
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
  // (only what intersects the cone of segments from the eye to the vehicle's bounding sphere can hide any of it)
  let hb = hullBoundsCache.get(hull);
  if (!hb) {
    let x0 = Infinity, y0 = Infinity, z0 = Infinity, x1 = -Infinity, y1 = -Infinity, z1 = -Infinity;
    for (let i = 0; i < hull.length; i += 3) {
      const x = hull[i], y = hull[i + 1], z = hull[i + 2];
      if (x < x0) x0 = x; if (x > x1) x1 = x;
      if (y < y0) y0 = y; if (y > y1) y1 = y;
      if (z < z0) z0 = z; if (z > z1) z1 = z;
    }
    hb = { cx: (x0 + x1) / 2, cy: (y0 + y1) / 2, cz: (z0 + z1) / 2, size: Math.hypot(x1 - x0, y1 - y0, z1 - z0) / 2 };
    hullBoundsCache.set(hull, hb);
  }
  const { cx, cy, cz, size } = hb;
  const ex = eye.x, ey = eye.y, ez = eye.z;
  const vx = cx - ex, vy = cy - ey, vz = cz - ez;
  const L = Math.hypot(vx, vy, vz);
  const sinA = L > size ? size / L : 1;
  const cosA = L > size ? Math.sqrt(1 - sinA * sinA) : 0;
  const tanA = cosA > 0 ? sinA / cosA : 0;
  const invL = L > 0 ? 1 / L : 0;
  const near: NearOccluder[] = [];
  for (let i = 0; i < occluders.length; i++) {
    const o = occluders[i];
    const ox = o.centre.x, oy = o.centre.y, oz = o.centre.z, rad = o.radius;
    if (L <= size) {
      if (Math.hypot(ox - cx, oy - cy, oz - cz) > rad + size + 1e-4) continue;
    } else {
      const wx = ox - ex, wy = oy - ey, wz = oz - ez;
      const s = (wx * vx + wy * vy + wz * vz) * invL;
      if (s < -rad - 1e-4 || s > L + size + rad + 1e-4) continue;
      const w2 = wx * wx + wy * wy + wz * wz;
      const h2 = w2 - s * s;
      const h = h2 > 0 ? Math.sqrt(h2) : 0;
      const uStar = (s + h * tanA) * invL;
      const minF = uStar <= 0 ? Math.sqrt(w2) : uStar >= 1 ? Math.hypot(ox - cx, oy - cy, oz - cz) - size : h * cosA - s * sinA;
      if (minF > rad + 1e-4) continue;
    }
    const me = o.inverse.elements;
    const isId =
      me[0] === 1 && me[1] === 0 && me[2] === 0 && me[3] === 0 &&
      me[4] === 0 && me[5] === 1 && me[6] === 0 && me[7] === 0 &&
      me[8] === 0 && me[9] === 0 && me[10] === 1 && me[11] === 0 &&
      me[12] === 0 && me[13] === 0 && me[14] === 0 && me[15] === 1;
    const ax = isId ? ex : me[0] * ex + me[4] * ey + me[8] * ez + me[12];
    const ay = isId ? ey : me[1] * ex + me[5] * ey + me[9] * ez + me[13];
    const az = isId ? ez : me[2] * ex + me[6] * ey + me[10] * ez + me[14];
    const box = o.geometry.boundingBox!;
    const wb = o.worldBox ?? (o.worldBox = isId ? new Float32Array([box.min.x, box.min.y, box.min.z, box.max.x, box.max.y, box.max.z]) : transformedBox(box, _tmpMat.copy(o.inverse).invert()));
    const idx = near.length;
    if ((idx + 1) * 6 > _nearBoxes.length) {
      const grown = new Float32Array(_nearBoxes.length * 2);
      grown.set(_nearBoxes);
      _nearBoxes = grown;
    }
    const n6 = idx * 6;
    _nearBoxes[n6] = wb[0]; _nearBoxes[n6 + 1] = wb[1]; _nearBoxes[n6 + 2] = wb[2];
    _nearBoxes[n6 + 3] = wb[3]; _nearBoxes[n6 + 4] = wb[4]; _nearBoxes[n6 + 5] = wb[5];
    near.push({ o, box, accel: accelCache.get(o.geometry) ?? null, ax, ay, az, isId, me });
  }
  if (!near.length) return 0;
  const total = Math.ceil(count / stride);
  const maxHidden = limit * total;
  let tested = 0, hidden = 0, lastHit = 0;
  const nearLen = near.length;
  for (let i = 0; i < count && hidden <= maxHidden; i += stride, tested++) {
    const px = hull[3 * i], py = hull[3 * i + 1], pz = hull[3 * i + 2];
    const dx = px - ex, dy = py - ey, dz = pz - ez;
    const invX = Math.abs(dx) >= 1e-12 ? 1 / dx : 0;
    const invY = Math.abs(dy) >= 1e-12 ? 1 / dy : 0;
    const invZ = Math.abs(dz) >= 1e-12 ? 1 / dz : 0;
    if (testNearOccluder(near[lastHit], lastHit * 6, ex, ey, ez, dx, dy, dz, invX, invY, invZ, px, py, pz)) {
      hidden++;
      continue;
    }
    for (let j = 0; j < nearLen; j++) {
      if (j === lastHit) continue;
      if (testNearOccluder(near[j], j * 6, ex, ey, ez, dx, dy, dz, invX, invY, invZ, px, py, pz)) {
        hidden++;
        lastHit = j;
        break;
      }
    }
  }
  return tested ? hidden / (hidden > maxHidden ? total : tested) : 0;
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
