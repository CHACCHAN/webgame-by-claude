import * as THREE from 'three';
import { Track } from '../track/Track';
import type { TerrainData } from '../track/terrain';
import { SHOULDER, type classifySides } from '../track/roadGeometry';
import { clamp, lerp, smoothstep } from '../util/math';
import { roadsidePart, type RoadsideId, type RoadsidePart } from './roadsideModels';
import { concreteMaterial, metalMaterial, netMaterial, reflectorMaterial, METAL } from './structureMaterials';

/**
 * What is built along the mountain road, for the layered look (quality medium and up; the low setting keeps
 * TrackScenery's plain ribbons). Everything is laid out in the road's own frame and baked into a few merged meshes:
 *
 *  - valley side: the guardrail in 4 m spans with its end terminals (Blender modules, bent with the road vertex by
 *    vertex), a delineator every 20 m behind it, the verge that falls away to the embankment;
 *  - mountain side: the gutter (an open U channel flush with the asphalt, a grating over a catch basin now and then),
 *    then either the verge rising into the slope, or where the cutting is high a retaining wall: sloped blocks
 *    (間知ブロック) up to some 4 m, sprayed concrete with its frame of beams (法枠) above that, a rockfall fence on top
 *    of the high ones;
 *  - kilometre posts.
 *
 * Nothing here is a collider: the car meets the invisible wall at the barrier line (track/roadGeometry.ts), which
 * every part stands just behind.
 *
 * `out` is metres outwards from the barrier line (half the road's width + SHOULDER), `h` metres above the road there.
 * A profile is a line of (out, h) points whose visible side is on the left of the way it is drawn (drawn outwards:
 * the top; drawn upwards: the side towards the road).
 *
 * Draw calls: one mesh per material for the whole course, except the steel (guardrail, posts, gratings, fences):
 * that is cut into stretches of road, each with its modelled parts and a plain stand-in for the distance.
 */
export type Profile = ReadonlyArray<readonly [number, number]>;
type Sides = ReturnType<typeof classifySides>;

const UP = new THREE.Vector3(0, 1, 0);
const _a = new THREE.Vector3(), _b = new THREE.Vector3(), _n = new THREE.Vector3(), _c = new THREE.Vector3();

/** triangles gathered for one mesh: position, normal, uv (metres), and for the steel what each vertex is made of */
export class Shape {
  readonly pos: number[] = [];
  readonly nor: number[] = [];
  readonly uv: number[] = [];
  readonly idx: number[] = [];
  private readonly tint: number[] | null;
  private readonly pbr: number[] | null;
  private paint: readonly number[] = METAL.galvanised;

  constructor(kind: 'plain' | 'metal' | 'tint' = 'plain') {
    this.tint = kind === 'plain' ? null : [];
    this.pbr = kind === 'metal' ? [] : null;
  }

  /** what the next vertices are made of: a name of `METAL`, or a colour */
  use(what: string | readonly [number, number, number]) {
    this.paint = typeof what === 'string' ? (METAL[what] ?? METAL.galvanised) : [...what, 0, 0.5];
    return this;
  }

  get count() {
    return this.pos.length / 3;
  }

  vertex(p: THREE.Vector3, n: THREE.Vector3, u = 0, v = 0) {
    this.pos.push(p.x, p.y, p.z);
    this.nor.push(n.x, n.y, n.z);
    this.uv.push(u, v);
    this.tint?.push(this.paint[0], this.paint[1], this.paint[2]);
    this.pbr?.push(this.paint[3], this.paint[4]);
    return this.count - 1;
  }

  /** a flat quad a → b → c → d, counter-clockwise seen from its front; uv in metres from (u0, v0) */
  quad(a: THREE.Vector3, b: THREE.Vector3, c: THREE.Vector3, d: THREE.Vector3, u0 = 0, v0 = 0) {
    _n.crossVectors(_a.subVectors(b, a), _b.subVectors(d, a)).normalize();
    const w = a.distanceTo(b), h = a.distanceTo(d);
    const i = this.vertex(a, _n, u0, v0);
    this.vertex(b, _n, u0 + w, v0);
    this.vertex(c, _n, u0 + w, v0 + h);
    this.vertex(d, _n, u0, v0 + h);
    this.idx.push(i, i + 1, i + 2, i, i + 2, i + 3);
  }

  /** the same quad, turned so that it faces away from the point `inside` */
  quadFrom(inside: THREE.Vector3, a: THREE.Vector3, b: THREE.Vector3, c: THREE.Vector3, d: THREE.Vector3, u0 = 0, v0 = 0) {
    _n.crossVectors(_a.subVectors(b, a), _b.subVectors(d, a));
    _c.addVectors(a, c).multiplyScalar(0.5).sub(inside);
    if (_n.dot(_c) < 0) this.quad(b, a, d, c, u0, v0);
    else this.quad(a, b, c, d, u0, v0);
  }

  geometry() {
    if (!this.idx.length) return null;
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(this.pos, 3));
    g.setAttribute('normal', new THREE.Float32BufferAttribute(this.nor, 3));
    g.setAttribute('uv', new THREE.Float32BufferAttribute(this.uv, 2));
    if (this.tint) g.setAttribute('tint', new THREE.Float32BufferAttribute(this.tint, 3));
    if (this.pbr) g.setAttribute('pbr', new THREE.Float32BufferAttribute(this.pbr, 2));
    g.setIndex(this.idx);
    return g;
  }
}

/** the ground beside the road (verge, the fill behind a wall): drawn with the terrain's material */
class GroundShape {
  readonly pos: number[] = [];
  readonly uv1: number[] = [];
  readonly surf: number[] = [];
  readonly idx: number[] = [];

  geometry() {
    if (!this.idx.length) return null;
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(this.pos, 3));
    g.setAttribute('uv1', new THREE.Float32BufferAttribute(this.uv1, 2));
    g.setAttribute('surf', new THREE.BufferAttribute(Uint8Array.from(this.surf), 4, true));
    g.setIndex(this.idx);
    g.computeVertexNormals();
    return g;
  }
}

export interface RoadsideOptions {
  /** the quality profile's surface detail (1–3) */
  detail: number;
  shadows: boolean;
  /** the terrain's material: the verge is the same ground */
  ground: THREE.Material;
  /** what grows at a place: [town 0..1, forest 0..1], as the terrain's own vertices say it */
  cover: (x: number, y: number, z: number) => [number, number];
}

const CHUNK = 160;

/** every sample from a to b in steps, b always included */
function rowsOf(a: number, b: number, step = 2) {
  const rows: number[] = [];
  for (let i = a; i < b; i += step) rows.push(i);
  rows.push(b);
  return rows;
}

/** the stretches of a..b (inclusive) where `ok` holds */
function stretches(a: number, b: number, ok: (i: number) => boolean) {
  const out: [number, number][] = [];
  let start = -1;
  for (let i = a; i <= b; i++) {
    if (ok(i)) {
      if (start < 0) start = i;
    } else if (start >= 0) {
      out.push([start, i - 1]);
      start = -1;
    }
  }
  if (start >= 0) out.push([start, b]);
  return out;
}

export class Roadside {
  readonly cast = new Shape();
  readonly formed = new Shape();
  readonly block = new Shape();
  readonly shotcrete = new Shape();
  readonly net = new Shape();
  readonly reflector = new Shape('tint');
  /** steel of the structures (bridge railings): one mesh for the course */
  readonly steelwork = new Shape('metal');
  private readonly ground = new GroundShape();
  private readonly chunks = new Map<number, { near: Shape; far: Shape }>();
  private readonly p = new THREE.Vector3();
  private readonly q = new THREE.Vector3();

  constructor(
    readonly track: Track,
    readonly terrain: TerrainData,
    readonly opts: RoadsideOptions,
  ) {}

  // ------------------------------------------------------------------ frame
  /** the point `out` metres beyond the barrier line of a side (+1 right, −1 left) at track distance s, h above the road */
  at(s: number, side: number, out: number, h: number, target = new THREE.Vector3()) {
    this.track.pointAt(s, side * (this.track.widthAt(s) / 2 + SHOULDER + out), target);
    target.y += h;
    return target;
  }

  /** the terrain's height above the road's edge line, `out` metres beyond the barrier */
  rise(s: number, side: number, out: number) {
    const p = this.at(s, side, out, 0, this.q);
    return this.terrain.heightAt(p.x, p.z) - p.y;
  }

  /** the steel of the stretch of road around s: its modelled parts, and their stand-in for the distance */
  steel(s: number) {
    const k = Math.floor(s / CHUNK);
    let c = this.chunks.get(k);
    if (!c) this.chunks.set(k, (c = { near: new Shape('metal'), far: new Shape('metal') }));
    return c;
  }

  // ------------------------------------------------------------------ shapes
  /**
   * A profile swept along the samples `rows`: hard edges across (every segment of the profile has its own vertices),
   * smooth along the road. uv = (metres along, metres along the profile from v0).
   */
  sweep(shape: Shape, rows: number[], side: number, profileAt: Profile | ((i: number) => Profile), v0 = 0) {
    if (rows.length < 2) return;
    const get = typeof profileAt === 'function' ? profileAt : () => profileAt;
    const pts: THREE.Vector3[][] = [], vs: number[][] = [];
    for (const i of rows) {
      const prof = get(i);
      const row: THREE.Vector3[] = [], v: number[] = [];
      let acc = v0;
      prof.forEach(([out, h], k) => {
        if (k > 0) acc += Math.hypot(out - prof[k - 1][0], h - prof[k - 1][1]);
        row.push(this.at(i, side, out, h));
        v.push(acc);
      });
      pts.push(row);
      vs.push(v);
    }
    const segs = pts[0].length - 1;
    const across = new THREE.Vector3(), along = new THREE.Vector3(), n = new THREE.Vector3();
    for (let k = 0; k < segs; k++) {
      const base = shape.count;
      for (let r = 0; r < rows.length; r++) {
        const r0 = Math.max(0, r - 1), r1 = Math.min(rows.length - 1, r + 1);
        across.subVectors(pts[r][k + 1], pts[r][k]);
        along.subVectors(pts[r1][k], pts[r0][k]).add(pts[r1][k + 1]).sub(pts[r0][k + 1]);
        if (side > 0) n.crossVectors(across, along);
        else n.crossVectors(along, across);
        if (n.lengthSq() < 1e-12) n.copy(UP);
        else n.normalize();
        shape.vertex(pts[r][k], n, rows[r], vs[r][k]);
        shape.vertex(pts[r][k + 1], n, rows[r], vs[r][k + 1]);
        if (r > 0) {
          const a0 = base + (r - 1) * 2, b0 = a0 + 1, c0 = base + r * 2, d0 = c0 + 1;
          if (side > 0) shape.idx.push(a0, b0, c0, b0, d0, c0);
          else shape.idx.push(a0, c0, b0, b0, c0, d0);
        }
      }
    }
  }

  /**
   * A box in the road's frame: from s0 to s1 along, out0 to out1 across, h0 to h1 high. `faces`: which to build, of
   * f (towards the road), b (away), s (start), e (end), t (top), u (underside).
   */
  box(shape: Shape, s0: number, s1: number, side: number, out0: number, out1: number, h0: number, h1: number, faces = 'fbsetu') {
    const c = (s: number, o: number, h: number) => this.at(s, side, o, h);
    const p000 = c(s0, out0, h0), p001 = c(s0, out0, h1), p010 = c(s0, out1, h0), p011 = c(s0, out1, h1);
    const p100 = c(s1, out0, h0), p101 = c(s1, out0, h1), p110 = c(s1, out1, h0), p111 = c(s1, out1, h1);
    const mid = c((s0 + s1) / 2, (out0 + out1) / 2, (h0 + h1) / 2);
    if (faces.includes('f')) shape.quadFrom(mid, p000, p100, p101, p001);
    if (faces.includes('b')) shape.quadFrom(mid, p010, p110, p111, p011);
    if (faces.includes('s')) shape.quadFrom(mid, p000, p010, p011, p001);
    if (faces.includes('e')) shape.quadFrom(mid, p100, p110, p111, p101);
    if (faces.includes('t')) shape.quadFrom(mid, p001, p101, p111, p011);
    if (faces.includes('u')) shape.quadFrom(mid, p000, p100, p110, p010);
  }

  /**
   * A module (render/roadsideModels.ts) stood on the road: its z runs along the road from s0 (`dz` −1: backwards, the
   * module mirrored), its x outwards from the line `base` metres beyond the barrier, its y up from `lift` above the
   * road. `sink` says which shape takes the triangles of a material (null: left out).
   */
  bake(part: RoadsidePart, sink: (material: string) => Shape | null, s0: number, side: number, dz: 1 | -1, base: number | ((s: number) => number), lift: number | ((s: number) => number) = 0) {
    const tr = this.track;
    const p = this.p, n = new THREE.Vector3();
    for (const [name, geo] of part) {
      const shape = sink(name);
      if (!shape) continue;
      if (name in METAL) shape.use(name);
      const pos = geo.getAttribute('position'), nor = geo.getAttribute('normal');
      const first = shape.count;
      for (let v = 0; v < pos.count; v++) {
        const s = s0 + dz * pos.getZ(v);
        this.at(s, side, (typeof base === 'function' ? base(s) : base) + pos.getX(v), (typeof lift === 'function' ? lift(s) : lift) + pos.getY(v), p);
        const o = clamp(Math.round(s), 0, tr.count - 1) * 3;
        const nx = nor.getX(v) * side, ny = nor.getY(v), nz = nor.getZ(v) * dz;
        n.set(tr.right[o] * nx + tr.fwd[o] * nz, tr.right[o + 1] * nx + ny + tr.fwd[o + 1] * nz, tr.right[o + 2] * nx + tr.fwd[o + 2] * nz).normalize();
        // (the optimiser drops the uv of a model without textures: the net's tiles of 0.5 m come from the module's own frame)
        shape.vertex(p, n, pos.getZ(v) * 2, pos.getY(v) * 2);
      }
      // (right, up, forward) is a left-handed frame: a module keeps its winding on the left side, forwards
      const flip = side * dz > 0;
      const ix = geo.index!.array;
      for (let t = 0; t + 2 < ix.length; t += 3) {
        if (flip) shape.idx.push(first + ix[t], first + ix[t + 2], first + ix[t + 1]);
        else shape.idx.push(first + ix[t], first + ix[t + 1], first + ix[t + 2]);
      }
    }
  }

  /**
   * A strip of ground: per row the points across, each (out, h). It starts on what is built and ends under the
   * terrain, so no gap can open between the two.
   */
  groundStrip(rows: number[], side: number, profileAt: (i: number) => Profile) {
    if (rows.length < 2) return;
    const g = this.ground, near = this.terrain.near, p = this.p;
    const base = g.pos.length / 3;
    let cols = 0;
    for (const i of rows) {
      const prof = profileAt(i);
      cols = prof.length;
      for (const [out, h] of prof) {
        this.at(i, side, out, h, p);
        g.pos.push(p.x, p.y, p.z);
        g.uv1.push(((p.x - near.x0) / near.cell + 0.5) / near.nx, ((p.z - near.z0) / near.cell + 0.5) / near.nz);
        const [urban, forest] = this.opts.cover(p.x, p.y, p.z);
        // (metres beyond the graded edge, which lies 0.6 m beyond the barrier line: see terrainMaterial.ts)
        g.surf.push(clamp((out - 0.6 + 2) / 34, 0, 1) * 255, 128, urban * 255, forest * 255);
      }
    }
    for (let r = 1; r < rows.length; r++)
      for (let k = 0; k < cols - 1; k++) {
        const a0 = base + (r - 1) * cols + k, b0 = a0 + 1, c0 = base + r * cols + k, d0 = c0 + 1;
        if (side > 0) g.idx.push(a0, b0, c0, b0, d0, c0);
        else g.idx.push(a0, c0, b0, b0, c0, d0);
      }
  }

  // ------------------------------------------------------------------ meshes
  finish(group: THREE.Group) {
    const { shadows, detail } = this.opts;
    const nightEmissive: THREE.MeshStandardMaterial[] = [];
    const add = (shape: { geometry(): THREE.BufferGeometry | null }, mat: THREE.Material, name: string, cast = false) => {
      const geo = shape.geometry();
      if (!geo) return null;
      const mesh = new THREE.Mesh(geo, mat);
      mesh.name = name;
      mesh.castShadow = cast && shadows;
      mesh.receiveShadow = true;
      group.add(mesh);
      return mesh;
    };
    add(this.cast, concreteMaterial('cast'), 'roadside-cast');
    add(this.formed, concreteMaterial('formed', { doubleSide: true }), 'roadside-formed', true);
    add(this.block, concreteMaterial('block'), 'roadside-block');
    add(this.shotcrete, concreteMaterial('shotcrete'), 'roadside-shotcrete');
    add(this.ground, this.opts.ground, 'roadside-verge');
    add(this.net, netMaterial(), 'roadside-net');
    const refl = reflectorMaterial();
    if (add(this.reflector, refl, 'roadside-reflector')) nightEmissive.push(refl as unknown as THREE.MeshStandardMaterial);
    const metal = metalMaterial();
    add(this.steelwork, metal, 'roadside-steelwork', true);
    const lods: { near: THREE.Mesh | null; far: THREE.Mesh | null; centre: THREE.Vector3; radius: number }[] = [];
    for (const [k, c] of this.chunks) {
      const near = add(c.near, metal, `roadside-steel-${k}`, true), far = add(c.far, metal, `roadside-steel-far-${k}`);
      const ref = near ?? far;
      if (!ref) continue;
      ref.geometry.computeBoundingSphere();
      const sphere = ref.geometry.boundingSphere!;
      if (near) near.visible = false;
      lods.push({ near, far, centre: sphere.center.clone(), radius: sphere.radius });
    }
    // how far the modelled steel is drawn before its stand-in takes over
    const reach = detail >= 2 ? 150 : 100;
    return {
      nightEmissive,
      update(camera: THREE.Vector3) {
        for (const l of lods) {
          const close = camera.distanceTo(l.centre) - l.radius < reach;
          if (l.near) l.near.visible = close;
          if (l.far) l.far.visible = !close || !l.near;
        }
      },
    };
  }
}

// ---------------------------------------------------------------------------------------------- the layout
// the gutter: an open U channel, its walls' tops flush with the asphalt
const GUTTER: Profile = [[0, 0.006], [0.14, 0.006], [0.14, -0.3], [0.64, -0.3], [0.64, 0.012], [0.78, 0.012]];
const GUTTER_TO_WALL: Profile = [[0.78, 0.012], [0.96, 0.02]];
/** where a wall's face starts, and how far it leans back per metre of height (1 : 0.3) */
const WALL_FOOT = 0.95, BATTER = 0.3;
// the guardrail's post line (the beam's face stands 0.11 m in front of it: just behind the barrier line)
const RAIL = 0.13;
const AMBER = [1, 0.42, 0.04] as const, WHITE = [0.9, 0.9, 0.84] as const;

/** Lays the roadside of a mountain course into `rs`. */
export function layRoadside(rs: Roadside, sides: Sides) {
  const { track } = rs;
  const n = track.count, last = n - 1;
  const bridge = new Uint8Array(n), shed = new Uint8Array(n);
  for (const [a, b] of track.zoneRanges('bridge')) for (let i = a; i <= b; i++) bridge[i] = 1;
  for (const [a, b] of track.zoneRanges('rockshed')) for (let i = a + 20; i <= b - 10; i++) shed[i] = 1;
  const parts = Object.fromEntries((['guardrail', 'guardrail_end', 'delineator', 'gutter_grate', 'rockfall_fence'] as RoadsideId[]).map((id) => [id, roadsidePart(id)])) as Record<RoadsideId, RoadsidePart | null>;
  const p = new THREE.Vector3(), q = new THREE.Vector3(), r = new THREE.Vector3(), t = new THREE.Vector3();

  const steelSink = (s: number, lensTint: readonly [number, number, number] = AMBER) => (material: string) => {
    if (material === 'reflector') return rs.reflector.use(lensTint);
    if (material === 'net') return rs.net;
    return rs.steel(s).near;
  };

  const delineator = (s: number, side: number, out: number) => {
    const tint = side > 0 ? AMBER : WHITE;
    if (parts.delineator) rs.bake(parts.delineator, steelSink(s, tint), s, side, 1, out);
    else {
      // no model: the lens alone
      rs.reflector.use(tint);
      rs.box(rs.reflector, s - 0.01, s + 0.01, side, out - 0.05, out + 0.05, 0.93, 1.03, 'se');
    }
  };

  const kmPost = (s: number, side: number, out: number) => {
    const steel = rs.steel(s).near;
    rs.box(steel.use('post_white'), s - 0.06, s + 0.06, side, out - 0.06, out + 0.06, -0.1, 0.42, 'fbse');
    rs.box(steel.use('blue'), s - 0.06, s + 0.06, side, out - 0.06, out + 0.06, 0.42, 0.52, 'fbset');
  };

  // -------------------------------------------------------------- valley side
  const guardrail = (a: number, b: number, side: number) => {
    const spans = Math.floor((b - a - 2) / 4);
    if (spans < 1) return;
    const s0 = a + (b - a - spans * 4) / 2;
    for (let k = 0; k < spans; k++) {
      const s = s0 + k * 4;
      const steel = rs.steel(s);
      if (parts.guardrail) rs.bake(parts.guardrail, steelSink(s), s, side, 1, RAIL);
      // the stand-in for the distance (and for a model that did not load): the beam's face and a flat post
      const far = parts.guardrail ? steel.far : steel.near;
      far.use('galvanised');
      const beam: Profile = [[RAIL - 0.06, 0.425], [RAIL - 0.11, 0.49], [RAIL - 0.07, 0.6], [RAIL - 0.11, 0.71], [RAIL - 0.06, 0.775]];
      rs.sweep(far, [s, s + 4], side, beam);
      rs.box(far, s + 1.94, s + 2.06, side, RAIL, RAIL + 0.11, -0.2, 0.76, 'fse');
    }
    if (parts.guardrail_end) {
      rs.bake(parts.guardrail_end, steelSink(s0), s0, side, -1, RAIL);
      rs.bake(parts.guardrail_end, steelSink(s0 + spans * 4), s0 + spans * 4, side, 1, RAIL);
    }
  };

  const valleyVerge = (i: number, side: number): Profile => {
    const g1 = rs.rise(i, side, 1.3), g2 = rs.rise(i, side, 2.3), g3 = rs.rise(i, side, 3.6);
    return [[0, 0], [0.6, -0.03], [1.3, Math.max(g1 + 0.06, -0.16)], [2.3, Math.max(g2 + 0.06, -0.7)], [3.6, g3 - 0.45]];
  };
  const mountainVerge = (i: number, side: number): Profile => {
    const g1 = rs.rise(i, side, 1.5), g2 = rs.rise(i, side, 2.6), g3 = rs.rise(i, side, 3.9);
    return [[0.78, 0.012], [1.5, Math.max(g1 + 0.06, 0.04)], [2.6, Math.max(g2 + 0.06, 0.02)], [3.9, g3 - 0.45]];
  };

  const valleyRun = (a: number, b: number, side: number) => {
    for (const [a2, b2] of stretches(a, b, (i) => !bridge[i])) {
      rs.groundStrip(rowsOf(a2, Math.min(b2 + 1, last)), side, (i) => valleyVerge(i, side));
      if (b2 - a2 < 6) continue;
      guardrail(a2, b2, side);
      for (let s = Math.ceil((a2 + 2) / 20) * 20; s <= b2 - 2; s += 20) delineator(s, side, RAIL + 0.3);
    }
  };

  // ------------------------------------------------------------ mountain side
  const wall = (a: number, b: number, side: number, want: Float32Array, wantFrom: number) => {
    // the wall's height at each sample, run out at both ends
    const count = b - a + 1;
    const H = new Float32Array(count);
    for (let i = a; i <= b; i++) H[i - a] = lerp(0.3, Math.max(0.3, want[i - wantFrom]), smoothstep(0, 7, Math.min(i - a, b - i)));
    const hAt = (s: number) => {
      const f = clamp(s - a, 0, count - 1), i = Math.min(count - 2, Math.floor(f));
      return count < 2 ? H[0] : lerp(H[i], H[i + 1], f - i);
    };
    let top = 0;
    for (const h of H) top = Math.max(top, h);
    const sprayed = top > 4.3;
    const rows = rowsOf(a, b);
    const topOut = (s: number) => WALL_FOOT + hAt(s) * BATTER;
    rs.sweep(sprayed ? rs.shotcrete : rs.block, rows, side, (i) => [[WALL_FOOT, -0.35], [topOut(i), hAt(i)]]);
    // the coping, and behind it the ground that meets the slope
    rs.sweep(rs.cast, rows, side, (i) => {
      const o = topOut(i), h = hAt(i);
      return [[o, h], [o - 0.05, h], [o - 0.05, h + 0.16], [o + 0.3, h + 0.16]];
    });
    rs.groundStrip(rows, side, (i) => {
      const o = topOut(i), h = hAt(i);
      return [[o + 0.3, h + 0.16], [o + 1.1, Math.max(rs.rise(i, side, o + 1.1) + 0.06, h - 0.25)], [o + 2.4, rs.rise(i, side, o + 2.4) - 0.45]];
    });
    rs.sweep(rs.cast, rowsOf(a, Math.min(b + 1, last)), side, GUTTER_TO_WALL);
    if (!sprayed) return;

    // the frame of beams on the sprayed slope (法枠): ribs every 2 m, a beam every 2 m of height
    const len = Math.hypot(1, BATTER), nx = -1 / len, ny = BATTER / len, proud = 0.11;
    const face = (s: number, height: number, lift: number, target: THREE.Vector3) => rs.at(s, side, WALL_FOOT + height * BATTER + nx * lift, height + ny * lift, target);
    for (const level of [1.3, 3.3, 5.3]) {
      for (const [a2, b2] of stretches(a, b, (i) => hAt(i) >= level + 0.5)) {
        if (b2 - a2 < 3) continue;
        const lo = level - 0.15, hi = level + 0.15;
        rs.sweep(rs.cast, rowsOf(a2, b2), side, [
          [WALL_FOOT + lo * BATTER, lo], [WALL_FOOT + lo * BATTER + nx * proud, lo + ny * proud],
          [WALL_FOOT + hi * BATTER + nx * proud, hi + ny * proud], [WALL_FOOT + hi * BATTER, hi],
        ]);
      }
    }
    for (let i = Math.ceil(a / 2) * 2; i <= b; i += 2) {
      const h = hAt(i);
      if (h < 1.2) continue;
      const s0 = i - 0.14, s1 = i + 0.14, lo = -0.3, hi = h - 0.02;
      const inside = face(i, (lo + hi) / 2, -0.3, t);
      rs.cast.quadFrom(inside, face(s0, lo, proud, p), face(s1, lo, proud, q), face(s1, hi, proud, r), face(s0, hi, proud, new THREE.Vector3()));
      for (const s of [s0, s1]) rs.cast.quadFrom(inside, face(s, lo, 0, p), face(s, lo, proud, q), face(s, hi, proud, r), face(s, hi, 0, new THREE.Vector3()));
    }
    // a rockfall fence on the coping of the high stretches
    for (const [a2, b2] of stretches(a, b, (i) => hAt(i) >= 3.6)) {
      const bays = Math.floor((b2 - a2) / 3);
      if (bays < 3) continue;
      const s0 = a2 + (b2 - a2 - bays * 3) / 2;
      for (let k = 0; k < bays; k++) {
        const s = s0 + k * 3;
        const base = (x: number) => topOut(x) + 0.13, lift = (x: number) => hAt(x) + 0.16;
        if (parts.rockfall_fence) rs.bake(parts.rockfall_fence, steelSink(s), s, side, 1, base, lift);
        const far = parts.rockfall_fence ? rs.steel(s).far : rs.steel(s).near;
        const o = base(s + 1.5), h = lift(s + 1.5);
        rs.box(far.use('rust'), s + 1.42, s + 1.58, side, o - 0.07, o + 0.07, h, h + 2, 'fse');
      }
    }
  };

  const mountainRun = (a: number, b: number, side: number) => {
    for (const [a2, b2] of stretches(a, b, (i) => !bridge[i])) {
      rs.sweep(rs.cast, rowsOf(a2, Math.min(b2 + 1, last)), side, GUTTER);
      if (b2 - a2 >= 6) {
        // (the grating's model has its top 0.06 m above its origin)
        if (parts.gutter_grate) for (let s = Math.ceil((a2 + 3) / 24) * 24 + 7; s <= b2 - 3; s += 24) rs.bake(parts.gutter_grate, steelSink(s), s, side, 1, 0.39, 0.012 - 0.06);
        for (let s = Math.ceil((a2 + 2) / 40) * 40 + 20; s <= b2 - 2; s += 40) delineator(s, side, 0.71);
      }
      // under a rock shed its back wall stands behind the gutter
      for (const [a3, b3] of stretches(a2, b2, (i) => !!shed[i])) rs.sweep(rs.cast, rowsOf(a3, Math.min(b3 + 1, last)), side, GUTTER_TO_WALL);
      for (const [a3, b3] of stretches(a2, b2, (i) => !shed[i])) {
        // A wall where the road is cut into the slope: three quarters as high as the ground stands 6 m behind the
        // barrier line (the terrain's own cutting starts gently, the wall is what makes it steep; the ground behind
        // its top is filled in). On the inside of a hairpin there is no room for a high one.
        const raw = new Float32Array(b3 - a3 + 1), want = new Float32Array(b3 - a3 + 1);
        for (let i = a3; i <= b3; i++) {
          const k = track.curvature[i];
          const room = side * k < -1e-4 ? (0.7 * (1 / Math.abs(k) - track.width[i] / 2 - SHOULDER) - WALL_FOOT - 2.4) / BATTER : 99;
          raw[i - a3] = clamp(Math.min(rs.rise(i, side, 6) * 0.75, room), 0, 6.5);
        }
        for (let i = a3; i <= b3; i++) {
          let sum = 0, count = 0;
          for (let k = Math.max(a3, i - 4); k <= Math.min(b3, i + 4); k++, count++) sum += raw[k - a3];
          want[i - a3] = sum / count;
        }
        let from = a3;
        for (const [a4, b4] of stretches(a3, b3, (i) => want[i - a3] >= 1)) {
          if (b4 - a4 < 8) continue;
          wall(a4, b4, side, want, a3);
          if (a4 > from) rs.groundStrip(rowsOf(from, a4), side, (i) => mountainVerge(i, side));
          from = b4;
        }
        if (from < Math.min(b3 + 1, last)) rs.groundStrip(rowsOf(from, Math.min(b3 + 1, last)), side, (i) => mountainVerge(i, side));
      }
    }
  };

  for (const [side, info] of [[1, sides.right], [-1, sides.left]] as const) {
    let start = 0;
    for (let i = 1; i <= n; i++) {
      if (i < n && info.valley[i] === info.valley[start]) continue;
      const a = start, b = i - 1;
      start = i;
      if (info.valley[a]) valleyRun(a, b, side);
      else mountainRun(a, b, side);
    }
    // a post every 200 m on the left
    if (side < 0) for (let s = 100; s < last - 10; s += 200) if (!bridge[s] && !shed[s]) kmPost(s, side, info.valley[s] ? RAIL + 0.42 : 0.71);
  }
}

// ---------------------------------------------------------------------------------------------- structures
/**
 * The rock sheds (洞門): a roof slab from the mountain's wall to a row of columns on the valley side, cross beams
 * under it, a low wall between the columns. Returns where its ceiling lights hang (track sample and position) and
 * adds the roof's footprint to `covers` (TrackScenery's `SceneryResult.covers`).
 */
export function layRocksheds(rs: Roadside, sides: Sides, covers: number[]) {
  const { track } = rs;
  const roofH = 5.6;
  const lights: { s: number; position: THREE.Vector3 }[] = [];
  const p = new THREE.Vector3();
  for (const [a0, b0] of track.zoneRanges('rockshed')) {
    const a = a0 + 20, b = b0 - 10;
    if (b - a < 8) continue;
    const mid = Math.round((a + b) / 2);
    const mountain = sides.right.valley[mid] ? -1 : 1;
    // the slab's valley edge, measured from the mountain side's barrier line
    const V = -(track.width[mid] + SHOULDER * 2 + 0.6);
    const rows = rowsOf(a, b);
    const slab: Profile = [[1.2, roofH + 0.9], [1.2, roofH], [V + 0.9, roofH], [V + 0.9, roofH - 0.55], [V, roofH - 0.55], [V, roofH + 0.9], [1.2, roofH + 0.9]];
    rs.sweep(rs.formed, rows, mountain, slab);
    rs.sweep(rs.formed, rows, mountain, [[0.9, -0.3], [0.9, roofH]]);
    // the portals: the slab's and the edge beam's end faces
    for (const [s, inward] of [[a, 1], [b, -1]] as const) {
      const inside = rs.at(s + inward, mountain, V / 2, roofH + 0.4);
      rs.formed.quadFrom(inside, rs.at(s, mountain, V, roofH), rs.at(s, mountain, 1.2, roofH), rs.at(s, mountain, 1.2, roofH + 0.9), rs.at(s, mountain, V, roofH + 0.9));
      rs.formed.quadFrom(inside, rs.at(s, mountain, V, roofH - 0.55), rs.at(s, mountain, V + 0.9, roofH - 0.55), rs.at(s, mountain, V + 0.9, roofH), rs.at(s, mountain, V, roofH));
    }
    // cross beams under the slab, columns under the edge beam, the low wall between them
    for (let i = a + 2; i <= b - 1; i += 5) {
      rs.box(rs.formed, i - 0.2, i + 0.2, mountain, V + 0.9, 0.9, roofH - 0.4, roofH, 'seu');
      rs.box(rs.formed, i - 0.3, i + 0.3, -mountain, 0.15, 0.75, -0.5, roofH - 0.55, 'fbse');
    }
    rs.sweep(rs.formed, rows, -mountain, [[0.3, -0.1], [0.3, 0.8], [0.6, 0.8], [0.6, -0.6]]);
    // the roof's footprint for the rain: quads every 6 m
    const edgeL = new THREE.Vector3(), edgeR = new THREE.Vector3();
    let prev: number[] | null = null;
    for (let i = a; ; i = Math.min(b, i + 6)) {
      const hw = track.width[i] / 2 + SHOULDER;
      track.pointAt(i, mountain * (hw + 1.2), edgeL);
      track.pointAt(i, mountain * (hw - (track.width[mid] + SHOULDER * 2 + 0.6)), edgeR);
      const row = [edgeL.x, edgeL.z, edgeR.x, edgeR.z, Math.max(edgeL.y, edgeR.y) + roofH + 0.9];
      if (prev) covers.push(prev[0], prev[1], prev[2], prev[3], row[2], row[3], row[0], row[1], Math.max(prev[4], row[4]));
      prev = row;
      if (i === b) break;
    }
    for (let i = a + 6; i <= b; i += 14) {
      track.pointAt(i, 0, p);
      lights.push({ s: i, position: p.clone().setY(p.y + roofH - 0.15) });
    }
  }
  return lights;
}

/**
 * The bridges: a concrete parapet with a steel rail on each side, the deck's edge, two box girders, piers with a
 * cap beam down to the gorge. Returns where its lamps stand.
 */
export function layBridges(rs: Roadside, terrain: TerrainData) {
  const { track } = rs;
  const lights: { s: number; position: THREE.Vector3 }[] = [];
  const p = new THREE.Vector3();
  for (const [a, b] of track.zoneRanges('bridge')) {
    const rows = rowsOf(a, b);
    for (const side of [1, -1]) {
      rs.sweep(rs.formed, rows, side, [[0.03, 0], [0.09, 0.28], [0.11, 0.92], [0.33, 0.92], [0.36, 0.25], [0.62, 0.22], [0.62, -0.5], [0.3, -0.62], [-0.9, -0.62], [-0.9, -2.2], [-2.7, -2.2], [-2.7, -0.62]]);
      // the rail on the parapet: a box tube on short posts
      rs.steelwork.use('bare');
      rs.sweep(rs.steelwork, rows, side, [[0.17, 1.12], [0.17, 1.2], [0.27, 1.2], [0.27, 1.12], [0.17, 1.12]]);
      for (let i = a + 1; i < b; i += 2) rs.box(rs.steelwork, i - 0.03, i + 0.03, side, 0.19, 0.25, 0.92, 1.12, 'fbse');
    }
    // the deck's underside between the girders
    rs.sweep(rs.formed, rows, 1, (i) => [[-2.7, -0.62], [-(track.width[i] + SHOULDER * 2 - 2.7), -0.62]]);
    // piers
    for (let i = a + 25; i < b - 10; i += 45) {
      track.pointAt(i, 0, p);
      const ground = terrain.heightAt(p.x, p.z);
      if (p.y - 2.2 - ground + 4 < 4) continue;
      const hw = track.width[i] / 2 + SHOULDER;
      rs.box(rs.formed, i - 1.1, i + 1.1, 1, -hw - 4.4, -hw + 4.4, -3.5, -2.2, 'fbseu');
      rs.box(rs.formed, i - 0.9, i + 0.9, 1, -hw - 2.4, -hw + 2.4, ground - 4 - p.y, -3.5, 'fbse');
    }
    let k = 0;
    for (let i = a + 10; i <= b - 5; i += 32) {
      const side = k++ % 2 ? 1 : -1;
      track.pointAt(i, side * (track.width[i] / 2 + SHOULDER + 0.3), p);
      lights.push({ s: i, position: p.clone() });
    }
  }
  return lights;
}
