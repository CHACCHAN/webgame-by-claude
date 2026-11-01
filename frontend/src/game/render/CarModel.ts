import * as THREE from 'three';
import type { CarId, CarSpec } from '../vehicle/carSpecs';

/**
 * Procedural car bodies. Each car is lofted from cross sections along its
 * length: the section outline carries a notch that opens into a wheel arch
 * near the axles, a shoulder crease and a crowned top. The glasshouse is a
 * second loft with tinted glass, a painted roof and pillars.
 */

interface BodyStyle {
  /** z of the front/rear extremes relative to the wheelbase midpoint */
  front: number;
  rear: number;
  halfWidth: number;
  bottom: number;
  shoulder: number;
  /** top surface heights: nose, cowl (windscreen base), deck (trunk), tail */
  noseTop: number;
  cowlTop: number;
  deckTop: number;
  tailTop: number;
  roof: number;
  /** z positions of the glasshouse */
  windshieldBase: number;
  roofFront: number;
  roofRear: number;
  rearGlassBase: number;
  /** roof width relative to body width */
  tumblehome: number;
  /** 0 = sharp boxy edges, 1 = soft rounded */
  softness: number;
  /** plan-view corner rounding at the ends (m) */
  cornerRound: number;
  archGap: number;
  flare: number;
  wing: 'none' | 'ducktail' | 'high';
  headlights: 'rect' | 'popup' | 'slim';
  twoTone: boolean;
}

const BASE_STYLES = {
  hayate: {
    front: 2.0, rear: -2.15, halfWidth: 0.83, bottom: 0.2, shoulder: 0.78,
    noseTop: 0.78, cowlTop: 0.95, deckTop: 1.0, tailTop: 0.98, roof: 1.33,
    windshieldBase: 0.62, roofFront: -0.05, roofRear: -1.1, rearGlassBase: -1.9,
    tumblehome: 0.82, softness: 0.25, cornerRound: 0.32, archGap: 0.05, flare: 0.02,
    wing: 'ducktail', headlights: 'rect', twoTone: true,
  },
  raijin: {
    front: 2.15, rear: -2.28, halfWidth: 0.9, bottom: 0.18, shoulder: 0.84,
    noseTop: 0.8, cowlTop: 0.98, deckTop: 1.06, tailTop: 1.04, roof: 1.42,
    windshieldBase: 0.72, roofFront: -0.02, roofRear: -0.95, rearGlassBase: -1.52,
    tumblehome: 0.8, softness: 0.45, cornerRound: 0.4, archGap: 0.04, flare: 0.07,
    wing: 'high', headlights: 'slim', twoTone: false,
  },
  shiden: {
    front: 2.12, rear: -2.17, halfWidth: 0.88, bottom: 0.17, shoulder: 0.7,
    noseTop: 0.62, cowlTop: 0.88, deckTop: 0.92, tailTop: 0.9, roof: 1.2,
    windshieldBase: 0.58, roofFront: -0.18, roofRear: -0.82, rearGlassBase: -1.6,
    tumblehome: 0.76, softness: 0.9, cornerRound: 0.55, archGap: 0.04, flare: 0.05,
    wing: 'ducktail', headlights: 'popup', twoTone: false,
  },
} satisfies Record<'hayate' | 'raijin' | 'shiden', BodyStyle>;

/** Fallback bodies for the newer cars until their GLB models are in place. */
const STYLES: Record<CarId, BodyStyle> = {
  ...BASE_STYLES,
  supra: { ...BASE_STYLES.shiden, front: 2.15, rear: -2.35, halfWidth: 0.9, headlights: 'slim' },
  r34: { ...BASE_STYLES.raijin },
  s15: { ...BASE_STYLES.shiden, headlights: 'slim' },
};

const smooth = (e0: number, e1: number, x: number) => {
  const t = Math.min(1, Math.max(0, (x - e0) / (e1 - e0)));
  return t * t * (3 - 2 * t);
};
const mix = (a: number, b: number, t: number) => a + (b - a) * t;

export interface CarMaterials {
  paint: THREE.MeshPhysicalMaterial;
  accent: THREE.MeshStandardMaterial;
  glass: THREE.MeshPhysicalMaterial;
  trim: THREE.MeshStandardMaterial;
  chrome: THREE.MeshStandardMaterial;
  headlight: THREE.MeshStandardMaterial;
  taillight: THREE.MeshStandardMaterial;
  tire: THREE.MeshStandardMaterial;
  rim: THREE.MeshStandardMaterial;
  brake: THREE.MeshStandardMaterial;
}

export function createCarMaterials(spec: CarSpec, bodyColor = spec.colors.body): CarMaterials {
  const mats: CarMaterials = {
    paint: new THREE.MeshPhysicalMaterial({
      color: bodyColor,
      metalness: 0.45,
      roughness: 0.32,
      clearcoat: 1,
      clearcoatRoughness: 0.035,
      envMapIntensity: 1.25,
    }),
    accent: new THREE.MeshStandardMaterial({ color: spec.colors.accent, metalness: 0.3, roughness: 0.45 }),
    glass: new THREE.MeshPhysicalMaterial({
      color: '#0b1016',
      metalness: 0.1,
      roughness: 0.04,
      clearcoat: 1,
      clearcoatRoughness: 0.02,
      envMapIntensity: 1.6,
      transparent: true,
      opacity: 0.88,
    }),
    trim: new THREE.MeshStandardMaterial({ color: '#0d0e10', metalness: 0.2, roughness: 0.6 }),
    chrome: new THREE.MeshStandardMaterial({ color: '#d8dade', metalness: 1, roughness: 0.12 }),
    headlight: new THREE.MeshStandardMaterial({ color: '#dfe6ee', emissive: '#fff4e0', emissiveIntensity: 0, roughness: 0.1, metalness: 0.4 }),
    taillight: new THREE.MeshStandardMaterial({ color: '#4a0505', emissive: '#ff1a10', emissiveIntensity: 1.2, roughness: 0.25 }),
    tire: new THREE.MeshStandardMaterial({ color: '#151515', roughness: 0.92, metalness: 0 }),
    rim: new THREE.MeshStandardMaterial({ color: '#b9bcc2', metalness: 0.95, roughness: 0.22 }),
    brake: new THREE.MeshStandardMaterial({ color: '#c41d14', roughness: 0.4, metalness: 0.3 }),
  };
  // material names are the contract for GLB models (see docs/ASSETS.md)
  for (const [k, m] of Object.entries(mats)) m.name = k;
  return mats;
}

const WHEEL_NAMES = ['wheel_fl', 'wheel_fr', 'wheel_rl', 'wheel_rr'];

/**
 * Build a rig from a GLB template. Contract: metres, +Z forward, ground at y = 0,
 * a node "body", wheel pivots "wheel_fl|fr|rl|rr" (each with a child "spin_*"),
 * optional empties "anchor_headlight_*", "anchor_taillight_*", "anchor_exhaust",
 * and materials named after the CarMaterials keys (paint, glass, headlight, ...).
 */
export function rigFromTemplate(template: THREE.Object3D, spec: CarSpec, opts: { bodyColor?: string } = {}): CarRig {
  const root = template.clone(true) as THREE.Group;
  root.name = `car-${spec.id}`;
  const fresh = createCarMaterials(spec, opts.bodyColor);
  const byName = fresh as unknown as Record<string, THREE.Material>;
  const cloned = new Map<THREE.Material, THREE.Material>();
  root.traverse((o) => {
    const m = o as THREE.Mesh;
    if (!m.isMesh) return;
    const swap = (mat: THREE.Material) => {
      if (byName[mat.name]) {
        // keep the GLB textures but take over the shared, tweakable material
        const target = byName[mat.name] as THREE.MeshStandardMaterial;
        const src = mat as THREE.MeshStandardMaterial;
        if (src.map && !target.map) {
          target.map = src.map;
          // lamp lenses glow through their own texture (the bright parts of the lens light up)
          if (mat.name === 'taillight' || mat.name === 'headlight') {
            target.emissiveMap = src.map;
            target.color.set('#ffffff');
          }
        }
        return target;
      }
      if (!cloned.has(mat)) cloned.set(mat, mat.clone());
      return cloned.get(mat)!;
    };
    m.material = Array.isArray(m.material) ? m.material.map(swap) : swap(m.material);
  });
  const body = (root.getObjectByName('body') as THREE.Group) ?? root;
  const wheels = WHEEL_NAMES.map((n) => {
    const pivot = root.getObjectByName(n) as THREE.Group;
    const spin = (pivot?.getObjectByName(n.replace('wheel', 'spin')) as THREE.Group) ?? pivot;
    return { pivot, spin };
  });
  const anchors = { exhaust: new THREE.Vector3(), headlights: [] as THREE.Vector3[], taillights: [] as THREE.Vector3[] };
  root.updateMatrixWorld(true);
  root.traverse((o) => {
    if (o.name.startsWith('anchor_headlight')) anchors.headlights.push(o.position.clone());
    if (o.name.startsWith('anchor_taillight')) anchors.taillights.push(o.position.clone());
    if (o.name === 'anchor_exhaust') anchors.exhaust.copy(o.position);
  });
  deriveAnchors(root, fresh, anchors);
  const target = root.getObjectByName('headlight_target') ?? new THREE.Object3D();
  if (!target.parent) {
    target.position.set(0, 0.3, 30);
    root.add(target);
  }
  return { root, body, wheels, materials: fresh, headlightTargets: [target], anchors, fromModel: true };
}

/**
 * The model optimiser prunes empty nodes, so imported GLBs arrive without their anchor empties:
 * rebuild them from the geometry — lamps from the lamp-material meshes (left/right halves), the
 * tailpipe from a muffler/exhaust mesh at the back if there is one, else low at the rear left.
 */
function deriveAnchors(root: THREE.Object3D, mats: CarMaterials, anchors: CarRig['anchors']) {
  const boxOf = (pred: (m: THREE.Mesh) => boolean) => {
    const box = new THREE.Box3();
    root.traverse((o) => {
      const m = o as THREE.Mesh;
      if (m.isMesh && pred(m)) box.expandByObject(m);
    });
    return box;
  };
  const halves = (box: THREE.Box3) => {
    const c = box.getCenter(new THREE.Vector3());
    const q = (box.max.x - box.min.x) / 4;
    return [new THREE.Vector3(c.x + q, c.y, c.z), new THREE.Vector3(c.x - q, c.y, c.z)];
  };
  const uses = (m: THREE.Mesh, mat: THREE.Material) => (Array.isArray(m.material) ? m.material.includes(mat) : m.material === mat);
  if (!anchors.headlights.length) {
    const b = boxOf((m) => uses(m, mats.headlight));
    if (!b.isEmpty()) anchors.headlights.push(...halves(b));
  }
  if (!anchors.taillights.length) {
    const b = boxOf((m) => uses(m, mats.taillight));
    if (!b.isEmpty()) anchors.taillights.push(...halves(b));
  }
  if (anchors.exhaust.lengthSq() === 0) {
    const body = boxOf(() => true);
    if (body.isEmpty()) return;
    const len = body.max.z - body.min.z;
    const pipe = boxOf((m) => /muffler|exhaust|tailpipe/i.test(m.name) && new THREE.Box3().setFromObject(m).max.z < body.min.z + len * 0.25);
    if (!pipe.isEmpty() && pipe.max.y < 0.8) {
      anchors.exhaust.set((pipe.min.x + pipe.max.x) / 2, (pipe.min.y + pipe.max.y) / 2, pipe.min.z - 0.02);
    } else {
      anchors.exhaust.set(-0.45 * (body.max.x - body.min.x) / 2, 0.3, body.min.z + 0.05);
    }
  }
}

/** Optional GLB car models (public/models/cars/<id>.glb); procedural cars are the fallback. */
const templates = new Map<string, THREE.Object3D>();
export function registerCarTemplate(id: string, scene: THREE.Object3D) {
  templates.set(id, scene);
}
export function carTemplate(id: string) {
  return templates.get(id) ?? null;
}

interface LoftOptions {
  stations: number[];
  /** returns the half-section outline (from bottom center, outwards and up, to top center) */
  section: (z: number) => [number, number][];
  /** material index for the face between point k and k+1 of the half section at z */
  materialOf: (z: number, k: number) => number;
  capStart?: boolean;
  capEnd?: boolean;
  materials: number;
}

/** Builds a mirrored lofted surface with per-face material groups. */
function loft(opts: LoftOptions): THREE.BufferGeometry {
  const rings: number[][] = [];
  const positions: number[] = [];
  let ringSize = 0;
  for (const z of opts.stations) {
    const half = opts.section(z);
    // full ring: right side (x<0 is right because +x is left) then mirrored
    const ring: [number, number][] = [];
    for (const [x, y] of half) ring.push([-x, y]);
    for (let k = half.length - 2; k >= 1; k--) ring.push([half[k][0], half[k][1]]);
    ringSize = ring.length;
    const idx: number[] = [];
    for (const [x, y] of ring) {
      idx.push(positions.length / 3);
      positions.push(x, y, z);
    }
    rings.push(idx);
  }
  const halfLen = opts.section(opts.stations[0]).length;
  const groups: number[][] = Array.from({ length: opts.materials }, () => []);
  const ringToHalf = (k: number) => (k < halfLen ? k : ringSize - k);
  for (let s = 0; s < rings.length - 1; s++) {
    const zMid = (opts.stations[s] + opts.stations[s + 1]) / 2;
    for (let k = 0; k < ringSize; k++) {
      const k2 = (k + 1) % ringSize;
      const a = rings[s][k], b = rings[s][k2], c = rings[s + 1][k], d = rings[s + 1][k2];
      // half-section edge index for material lookup
      const hk = k < halfLen - 1 ? k : ringToHalf(k2);
      const m = opts.materialOf(zMid, Math.min(hk, halfLen - 2));
      groups[m].push(a, c, b, b, c, d);
    }
  }
  // end caps (nose / tail panel) take the body colour of the upper side
  const capMat = opts.materialOf(opts.stations[0], halfLen - 3);
  const cap = (ring: number[], flip: boolean, z: number) => {
    // fan from the ring centroid
    let cx = 0, cy = 0;
    for (const i of ring) {
      cx += positions[i * 3];
      cy += positions[i * 3 + 1];
    }
    const center = positions.length / 3;
    positions.push(cx / ring.length, cy / ring.length, z);
    for (let k = 0; k < ring.length; k++) {
      const a = ring[k], b = ring[(k + 1) % ring.length];
      if (flip) groups[capMat].push(center, b, a);
      else groups[capMat].push(center, a, b);
    }
  };
  if (opts.capStart) cap(rings[0], false, opts.stations[0]);
  if (opts.capEnd) cap(rings[rings.length - 1], true, opts.stations[opts.stations.length - 1]);

  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  const index: number[] = [];
  groups.forEach((g, m) => {
    geo.addGroup(index.length, g.length, m);
    index.push(...g);
  });
  geo.setIndex(index);
  geo.computeVertexNormals();
  return geo;
}

function range(a: number, b: number, n: number, extra: number[] = []) {
  const out: number[] = [];
  for (let i = 0; i <= n; i++) out.push(mix(a, b, i / n));
  return [...new Set([...out, ...extra])].sort((x, y) => x - y);
}

export interface CarRig {
  root: THREE.Group;
  body: THREE.Group;
  /** steer pivot + spin node for each wheel (FL, FR, RL, RR) */
  wheels: { pivot: THREE.Group; spin: THREE.Group }[];
  materials: CarMaterials;
  headlightTargets: THREE.Object3D[];
  /** world-space-ish anchor points (body local) for effects */
  anchors: { exhaust: THREE.Vector3; headlights: THREE.Vector3[]; taillights: THREE.Vector3[] };
  /** a GLB model (vs the procedural fallback body) */
  fromModel?: boolean;
}

export function buildCar(spec: CarSpec, opts: { bodyColor?: string; procedural?: boolean } = {}): CarRig {
  const tpl = opts.procedural ? null : carTemplate(spec.id);
  if (tpl) return rigFromTemplate(tpl, spec, opts);
  return buildProceduralCar(spec, opts);
}

export function buildProceduralCar(spec: CarSpec, opts: { bodyColor?: string } = {}): CarRig {
  const st = STYLES[spec.id];
  const mats = createCarMaterials(spec, opts.bodyColor);
  const root = new THREE.Group();
  root.name = `car-${spec.id}`;
  const body = new THREE.Group();
  body.name = 'body';
  root.add(body);

  const W = st.halfWidth;
  const r = spec.wheelRadius;
  const axleF = spec.wheelbase / 2, axleR = -spec.wheelbase / 2;
  const archR = r + st.archGap + 0.02;
  const tireW = 0.21;

  // --- lower body
  const topAt = (z: number) => {
    if (z > st.windshieldBase) {
      const t = (z - st.windshieldBase) / (st.front - st.windshieldBase);
      return mix(st.cowlTop, st.noseTop, Math.pow(t, 1.15));
    }
    if (z < st.rearGlassBase) {
      const t = (st.rearGlassBase - z) / (st.rearGlassBase - st.rear);
      return mix(st.deckTop, st.tailTop, t);
    }
    // under the glasshouse: belt line rising slightly to the rear
    const t = (st.windshieldBase - z) / (st.windshieldBase - st.rearGlassBase);
    return mix(st.cowlTop, st.deckTop, t);
  };
  const planWidth = (z: number) => {
    // round the corners in plan view
    const dF = st.front - z, dR = z - st.rear;
    const d = Math.min(dF, dR);
    const c = st.cornerRound;
    let w = W;
    if (d < c) w -= c - Math.sqrt(Math.max(0, c * c - (c - d) * (c - d)));
    // fender flares over the wheels
    const fl = Math.max(smooth(0.75, 0.2, Math.abs(z - axleF)), smooth(0.75, 0.2, Math.abs(z - axleR)));
    return w + fl * st.flare;
  };
  const archHeight = (z: number) => {
    let h = st.bottom;
    for (const az of [axleF, axleR]) {
      const dz = Math.abs(z - az);
      if (dz < archR) h = Math.max(h, r + Math.sqrt(archR * archR - dz * dz));
    }
    return h;
  };
  const endDrop = (z: number) => {
    // ends of the body taper down/up a little (bumpers)
    const f = smooth(st.front - 0.35, st.front, z), b = smooth(st.rear + 0.3, st.rear, z);
    return { top: f * 0.06 + b * 0.04, bottom: f * 0.08 + b * 0.1 };
  };

  const lowerSection = (z: number): [number, number][] => {
    const w = planWidth(z);
    const top = topAt(z) - endDrop(z).top;
    const bot = st.bottom + endDrop(z).bottom;
    const arch = Math.max(archHeight(z), bot);
    const inner = Math.min(w - tireW - 0.07, w * 0.7);
    const sh = Math.min(st.shoulder, top - 0.06);
    const soft = st.softness;
    const shoulderIn = mix(0.012, 0.04, soft);
    const topIn = mix(0.03, 0.14, soft);
    return [
      [0, bot],
      [inner, bot],
      [inner, arch],
      [w - 0.06, arch],
      [w - 0.01, arch + 0.07],
      [w, mix(arch + 0.07, sh, 0.5)],
      [w, sh - 0.04],
      [w - shoulderIn, sh],
      [w - topIn * 0.6, mix(sh, top, 0.6)],
      [w - topIn, top - 0.005],
      [w * 0.55, top + 0.012],
      [0, top + 0.018],
    ];
  };
  const lowerStations = range(st.rear, st.front, 64, [axleF - archR, axleF + archR, axleR - archR, axleR + archR]);
  // material ids: 0 paint, 1 accent (two-tone / lower trim), 2 trim
  const lowerGeo = loft({
    stations: lowerStations,
    section: lowerSection,
    materials: 3,
    capStart: true,
    capEnd: true,
    materialOf: (_z, k) => {
      if (k <= 3) return 2; // underside, wheel well & rocker
      if (st.twoTone && k === 4) return 1; // lower body accent colour
      return 0;
    },
  });
  const lower = new THREE.Mesh(lowerGeo, [mats.paint, mats.accent, mats.trim]);
  lower.castShadow = true;
  body.add(lower);

  // --- glasshouse
  const roofAt = (z: number) => {
    if (z >= st.roofFront) {
      const t = (z - st.roofFront) / (st.windshieldBase - st.roofFront);
      return mix(st.roof, topAt(st.windshieldBase), Math.pow(Math.min(1, t), 1.15));
    }
    if (z <= st.roofRear) {
      const t = (st.roofRear - z) / (st.roofRear - st.rearGlassBase);
      return mix(st.roof, topAt(st.rearGlassBase), Math.pow(Math.min(1, t), 0.9));
    }
    return st.roof + 0.015 * Math.sin(((z - st.roofRear) / (st.roofFront - st.roofRear)) * Math.PI);
  };
  const cabinSection = (z: number): [number, number][] => {
    const belt = topAt(z);
    const roof = Math.max(roofAt(z), belt + 0.002);
    const wBelt = planWidth(z) - mix(0.04, 0.16, st.softness);
    const wRoof = W * st.tumblehome;
    const h = roof - belt;
    const edgeIn = mix(0.04, 0.1, st.softness);
    return [
      [0, belt - 0.02],
      [wBelt * 0.9, belt - 0.02],
      [wBelt, belt],
      [mix(wBelt, wRoof, 0.55), belt + h * 0.62],
      [wRoof, roof - 0.03],
      [wRoof - edgeIn, roof],
      [0, roof + 0.012],
    ];
  };
  const cabinStations = range(st.rearGlassBase - 0.01, st.windshieldBase + 0.01, 40, [st.roofFront, st.roofRear]);
  const cabinGeo = loft({
    stations: cabinStations,
    section: cabinSection,
    materials: 2,
    materialOf: (z, k) => {
      const onRoof = z < st.roofFront - 0.02 && z > st.roofRear + 0.02;
      if (k >= 4 && onRoof) return 0;
      if (k === 0 || k === 1) return 0;
      return 1;
    },
  });
  const cabin = new THREE.Mesh(cabinGeo, [mats.paint, mats.glass]);
  cabin.castShadow = true;
  body.add(cabin);

  // pillars along the glass edges
  const pillar = (pts: THREE.Vector3[], radius: number) => {
    const curve = new THREE.CatmullRomCurve3(pts);
    const m = new THREE.Mesh(new THREE.TubeGeometry(curve, 12, radius, 6, false), mats.paint);
    body.add(m);
  };
  for (const side of [1, -1]) {
    const roofEdge = (z: number) => {
      const s = cabinSection(z);
      return new THREE.Vector3(side * s[4][0], s[4][1], z);
    };
    const beltEdge = (z: number) => {
      const s = cabinSection(z);
      return new THREE.Vector3(side * s[2][0], s[2][1], z);
    };
    // A pillar
    pillar([beltEdge(st.windshieldBase - 0.04), roofEdge(mix(st.windshieldBase, st.roofFront, 0.5)), roofEdge(st.roofFront + 0.02)], 0.042);
    // C pillar (wide) for coupes / sedans
    const cMid = mix(st.roofRear, st.rearGlassBase, 0.5);
    pillar([roofEdge(st.roofRear), roofEdge(cMid), beltEdge(st.rearGlassBase + 0.02)], 0.05);
    // B pillar
    const bz = mix(st.roofFront, st.roofRear, 0.48);
    pillar([beltEdge(bz), roofEdge(bz)], 0.03);
    // window trim along the belt
    pillar([beltEdge(st.windshieldBase - 0.05), beltEdge(mix(st.windshieldBase, st.rearGlassBase, 0.5)), beltEdge(st.rearGlassBase + 0.05)], 0.012);
  }

  // --- lights
  const anchors = { exhaust: new THREE.Vector3(), headlights: [] as THREE.Vector3[], taillights: [] as THREE.Vector3[] };
  const lampY = st.noseTop - 0.14;
  for (const side of [1, -1]) {
    const x = side * (W - 0.3);
    if (st.headlights === 'popup') {
      // pop-up pods (raised at night) + a slim bumper lamp
      const pod = new THREE.Mesh(new THREE.BoxGeometry(0.42, 0.12, 0.26), mats.paint);
      pod.position.set(x, st.noseTop + 0.03, st.front - 0.42);
      pod.rotation.x = -0.25;
      body.add(pod);
      const lens = new THREE.Mesh(new THREE.BoxGeometry(0.36, 0.09, 0.02), mats.headlight);
      lens.position.set(x, st.noseTop + 0.05, st.front - 0.28);
      lens.rotation.x = -0.25;
      body.add(lens);
      anchors.headlights.push(lens.position.clone());
    } else {
      const h = st.headlights === 'slim' ? 0.075 : 0.13;
      const w = st.headlights === 'slim' ? 0.4 : 0.34;
      // sit just proud of the body surface near the front corner
      const lz = st.front - 0.04 - (W - Math.abs(x)) * 0.05;
      const lens = new THREE.Mesh(new THREE.BoxGeometry(w, h, 0.03), mats.headlight);
      lens.position.set(x, lampY, lz);
      lens.rotation.set(-0.12, side * 0.18, 0);
      body.add(lens);
      const bezel = new THREE.Mesh(new THREE.BoxGeometry(w + 0.03, h + 0.03, 0.025), mats.trim);
      bezel.position.copy(lens.position).add(new THREE.Vector3(0, 0, -0.012));
      bezel.rotation.copy(lens.rotation);
      body.add(bezel);
      anchors.headlights.push(lens.position.clone());
    }
    // fog lamps in the bumper
    const fog = new THREE.Mesh(new THREE.BoxGeometry(0.16, 0.05, 0.03), mats.headlight);
    fog.position.set(side * (W - 0.25), st.bottom + 0.16, st.front - 0.03);
    body.add(fog);

    // tail lights
    const tl = new THREE.Mesh(new THREE.BoxGeometry(0.5, st.wing === 'ducktail' ? 0.1 : 0.13, 0.05), mats.taillight);
    tl.position.set(side * (W - 0.34), st.tailTop - 0.17, st.rear + 0.04);
    body.add(tl);
    anchors.taillights.push(tl.position.clone());

    // mirrors
    const mirrorZ = st.windshieldBase - 0.16;
    const beltW = planWidth(mirrorZ) - mix(0.04, 0.16, st.softness);
    const mirror = new THREE.Mesh(new THREE.BoxGeometry(0.15, 0.085, 0.1), mats.paint);
    mirror.position.set(side * (beltW + 0.1), topAt(mirrorZ) + 0.09, mirrorZ);
    body.add(mirror);
    const stalk = new THREE.Mesh(new THREE.BoxGeometry(0.1, 0.03, 0.05), mats.trim);
    stalk.position.set(side * (beltW + 0.03), topAt(mirrorZ) + 0.07, mirrorZ);
    body.add(stalk);
    const mglass = new THREE.Mesh(new THREE.PlaneGeometry(0.12, 0.06), mats.chrome);
    mglass.position.copy(mirror.position).add(new THREE.Vector3(0, 0, -0.051));
    mglass.rotation.y = Math.PI;
    body.add(mglass);
  }
  // door shut lines and handles: tiny details that read as "real car" at a glance
  const seamMat = new THREE.MeshBasicMaterial({ color: '#050506' });
  const doorFront = axleF - archR - 0.06;
  const doorRear = mix(st.roofFront, st.roofRear, 0.48) - (spec.id === 'raijin' ? 0.9 : 0.05);
  for (const side of [1, -1]) {
    for (const z of spec.id === 'raijin' ? [doorFront, mix(doorFront, doorRear, 0.52), doorRear] : [doorFront, doorRear]) {
      const top = topAt(z) - 0.03;
      const bot = archHeight(z) + 0.1;
      const seam = new THREE.Mesh(new THREE.BoxGeometry(0.006, top - bot, 0.008), seamMat);
      seam.position.set(side * (planWidth(z) + 0.002), (top + bot) / 2, z);
      body.add(seam);
    }
    const hz = doorRear + 0.18;
    const handle = new THREE.Mesh(new THREE.BoxGeometry(0.012, 0.025, 0.14), mats.trim);
    handle.position.set(side * (planWidth(hz) + 0.004), Math.min(st.shoulder, topAt(hz)) - 0.08, hz);
    body.add(handle);
  }

  // grille + front lip
  const grille = new THREE.Mesh(new THREE.BoxGeometry(W * 0.9, 0.12, 0.04), mats.trim);
  grille.position.set(0, st.bottom + 0.2, st.front - 0.03);
  body.add(grille);
  const lip = new THREE.Mesh(new THREE.BoxGeometry(W * 1.6, 0.025, 0.1), mats.trim);
  lip.position.set(0, st.bottom + 0.06, st.front - 0.12);
  body.add(lip);
  // side skirts
  for (const side of [1, -1]) {
    const skirt = new THREE.Mesh(new THREE.BoxGeometry(0.05, 0.07, spec.wheelbase - archR * 2 - 0.1), mats.trim);
    skirt.position.set(side * (W - 0.01), st.bottom + 0.03, 0);
    body.add(skirt);
  }
  // rear panel garnish + plate
  const garnish = new THREE.Mesh(new THREE.BoxGeometry(W * 0.75, 0.1, 0.03), mats.trim);
  garnish.position.set(0, st.tailTop - 0.17, st.rear + 0.025);
  body.add(garnish);
  const plateTex = makePlateTexture(spec.id);
  const plateMat = new THREE.MeshStandardMaterial({ map: plateTex, roughness: 0.5 });
  const plate = new THREE.Mesh(new THREE.PlaneGeometry(0.33, 0.165), plateMat);
  plate.position.set(0, st.bottom + 0.3, st.rear + 0.01);
  plate.rotation.y = Math.PI;
  body.add(plate);
  const fplate = plate.clone();
  fplate.position.set(0, st.bottom + 0.18, st.front + 0.005);
  fplate.rotation.y = 0;
  body.add(fplate);
  // exhaust
  const exhaust = new THREE.Mesh(new THREE.CylinderGeometry(0.045, 0.05, 0.2, 14, 1, true), mats.chrome);
  exhaust.rotation.x = Math.PI / 2;
  exhaust.position.set(-(W - 0.35), st.bottom + 0.05, st.rear - 0.02);
  body.add(exhaust);
  anchors.exhaust.copy(exhaust.position);
  if (spec.drive === 'AWD') {
    const ex2 = exhaust.clone();
    ex2.position.x = W - 0.35;
    body.add(ex2);
  }

  // wing
  if (st.wing === 'high') {
    const wing = new THREE.Mesh(new THREE.BoxGeometry(W * 1.8, 0.03, 0.26), mats.paint);
    wing.position.set(0, st.deckTop + 0.24, st.rear + 0.25);
    wing.rotation.x = 0.08;
    body.add(wing);
    for (const side of [1, -1]) {
      const stay = new THREE.Mesh(new THREE.BoxGeometry(0.04, 0.24, 0.14), mats.paint);
      stay.position.set(side * W * 0.62, st.deckTop + 0.12, st.rear + 0.27);
      body.add(stay);
      const plateEnd = new THREE.Mesh(new THREE.BoxGeometry(0.02, 0.1, 0.3), mats.paint);
      plateEnd.position.set(side * W * 0.9, st.deckTop + 0.26, st.rear + 0.25);
      body.add(plateEnd);
    }
  } else if (st.wing === 'ducktail') {
    const duck = new THREE.Mesh(new THREE.BoxGeometry(W * 1.6, 0.04, 0.16), mats.paint);
    duck.position.set(0, st.tailTop + 0.02, st.rear + 0.12);
    duck.rotation.x = 0.18;
    body.add(duck);
  }

  // --- wheels
  const wheels: CarRig['wheels'] = [];
  const tireGeo = makeTireGeometry(r, tireW);
  const rimGeo = makeRimGeometry(r * 0.66, tireW * 0.8, spec.id);
  const discGeo = new THREE.CylinderGeometry(r * 0.52, r * 0.52, 0.025, 24);
  discGeo.rotateZ(Math.PI / 2);
  const discMat = new THREE.MeshStandardMaterial({ color: '#555', metalness: 0.8, roughness: 0.35 });
  const caliperGeo = new THREE.BoxGeometry(0.06, 0.12, 0.16);
  for (const front of [true, false]) {
    for (const left of [true, false]) {
      const pivot = new THREE.Group();
      const x = (left ? 1 : -1) * (spec.track / 2 + 0.02);
      pivot.position.set(x, r, front ? axleF : axleR);
      const spin = new THREE.Group();
      pivot.add(spin);
      const tire = new THREE.Mesh(tireGeo, mats.tire);
      tire.castShadow = true;
      spin.add(tire);
      const rim = new THREE.Mesh(rimGeo, mats.rim);
      if (!left) rim.rotation.y = Math.PI;
      spin.add(rim);
      const disc = new THREE.Mesh(discGeo, discMat);
      disc.position.x = (left ? -1 : 1) * 0.05;
      spin.add(disc);
      // calipers don't spin
      const cal = new THREE.Mesh(caliperGeo, mats.brake);
      cal.position.set((left ? -1 : 1) * 0.04, r * 0.32, front ? -0.08 : 0.08);
      pivot.add(cal);
      root.add(pivot);
      const wn = WHEEL_NAMES[wheels.length];
      pivot.name = wn;
      spin.name = wn.replace('wheel', 'spin');
      wheels.push({ pivot, spin });
    }
  }

  // headlight beam targets (for spotlights)
  const headlightTargets: THREE.Object3D[] = [];
  const target = new THREE.Object3D();
  target.name = 'headlight_target';
  // named empties so GLB exports keep the effect anchors
  const anchorNode = (name: string, v: THREE.Vector3) => {
    const o = new THREE.Object3D();
    o.name = name;
    o.position.copy(v);
    body.add(o);
  };
  anchors.headlights.forEach((v, i) => anchorNode(`anchor_headlight_${i}`, v));
  anchors.taillights.forEach((v, i) => anchorNode(`anchor_taillight_${i}`, v));
  anchorNode('anchor_exhaust', anchors.exhaust);
  target.position.set(0, 0, st.front + 30);
  root.add(target);
  headlightTargets.push(target);

  return { root, body, wheels, materials: mats, headlightTargets, anchors };
}

function makeTireGeometry(r: number, w: number) {
  // rounded sidewall profile revolved around the axle
  const pts: THREE.Vector2[] = [];
  const inner = r * 0.66;
  const segs = 8;
  pts.push(new THREE.Vector2(inner, -w / 2 + 0.01));
  for (let i = 0; i <= segs; i++) {
    const a = -Math.PI / 2 + (i / segs) * (Math.PI / 2);
    pts.push(new THREE.Vector2(r - 0.04 + Math.cos(a) * 0.04, -w / 2 + 0.04 + Math.sin(a) * 0.04));
  }
  for (let i = 0; i <= segs; i++) {
    const a = (i / segs) * (Math.PI / 2);
    pts.push(new THREE.Vector2(r - 0.04 + Math.cos(a) * 0.04, w / 2 - 0.04 + Math.sin(a) * 0.04));
  }
  pts.push(new THREE.Vector2(inner, w / 2 - 0.01));
  const g = new THREE.LatheGeometry(pts, 36);
  // lathe revolves around Y; wheels spin around X
  g.rotateZ(Math.PI / 2);
  return g;
}

function makeRimGeometry(radius: number, depth: number, id: CarId) {
  const shape = new THREE.Shape();
  shape.absarc(0, 0, radius, 0, Math.PI * 2, false);
  const spokes = id === 'raijin' ? 10 : id === 'shiden' ? 5 : 8;
  const holeOuter = radius * 0.86, holeInner = radius * 0.34;
  for (let i = 0; i < spokes; i++) {
    const a0 = (i / spokes) * Math.PI * 2 + (id === 'shiden' ? 0.32 : 0.2);
    const a1 = ((i + 1) / spokes) * Math.PI * 2 - (id === 'shiden' ? 0.32 : 0.2);
    const hole = new THREE.Path();
    hole.absarc(0, 0, holeOuter, a0, a1, false);
    hole.absarc(0, 0, holeInner, a1 - 0.05, a0 + 0.05, true);
    shape.holes.push(hole);
  }
  const g = new THREE.ExtrudeGeometry(shape, { depth: 0.03, bevelEnabled: true, bevelThickness: 0.012, bevelSize: 0.01, bevelSegments: 2, curveSegments: 24 });
  g.rotateY(Math.PI / 2);
  g.translate(depth * 0.35, 0, 0);
  // barrel
  const barrel = new THREE.CylinderGeometry(radius, radius, depth * 0.9, 28, 1, true);
  barrel.rotateZ(Math.PI / 2);
  const merged = mergeSimple([g, barrel]);
  return merged;
}

function mergeSimple(geos: THREE.BufferGeometry[]) {
  const pos: number[] = [], nor: number[] = [], idx: number[] = [];
  let offset = 0;
  for (const g0 of geos) {
    const g = g0.index ? g0 : g0;
    const p = g.getAttribute('position'), n = g.getAttribute('normal');
    for (let i = 0; i < p.count; i++) {
      pos.push(p.getX(i), p.getY(i), p.getZ(i));
      nor.push(n.getX(i), n.getY(i), n.getZ(i));
    }
    if (g.index) for (let i = 0; i < g.index.count; i++) idx.push(g.index.getX(i) + offset);
    else for (let i = 0; i < p.count; i++) idx.push(i + offset);
    offset += p.count;
  }
  const out = new THREE.BufferGeometry();
  out.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  out.setAttribute('normal', new THREE.Float32BufferAttribute(nor, 3));
  out.setIndex(idx);
  return out;
}

function makePlateTexture(id: CarId) {
  const c = typeof document !== 'undefined' ? document.createElement('canvas') : null;
  if (!c) return null;
  c.width = 256;
  c.height = 128;
  const g = c.getContext('2d')!;
  g.fillStyle = '#f4f2e8';
  g.fillRect(0, 0, 256, 128);
  g.strokeStyle = '#1c5a2c';
  g.lineWidth = 6;
  g.strokeRect(4, 4, 248, 120);
  g.fillStyle = '#1c5a2c';
  g.font = 'bold 30px sans-serif';
  g.textAlign = 'center';
  g.fillText('朧  300', 128, 42);
  g.font = 'bold 62px sans-serif';
  const num = id === 'hayate' ? '86-04' : id === 'raijin' ? '57-10' : '13-07';
  g.fillText(num, 140, 108);
  g.font = 'bold 30px sans-serif';
  g.fillText('と', 30, 100);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = 4;
  return t;
}

/** Ground offset of the body origin: the visual model has y = 0 at the ground. */
export function carVisualOffset(rideHeight: number) {
  return -rideHeight;
}
