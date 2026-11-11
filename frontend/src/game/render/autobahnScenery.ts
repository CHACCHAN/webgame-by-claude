import * as THREE from 'three';
import { vegetationFrame } from './vegetation';
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js';
import type { Track } from '../track/Track';
import type { TerrainData } from '../track/terrain';
import { buildAutobahnRoadGeometry, SHOULDER } from '../track/roadGeometry';
import { clamp, lerp, rng, smoothstep } from '../util/math';
import { makeAsphaltNormal, makeConcreteTexture, makeGroundDetail, makeGroundNormal } from './textures';
import { ATLAS_L, ATLAS_W, LAYOUT, makeAntiGlareTexture, makeAutobahnRoadTexture, makeFenceTexture, makeNoiseWallTexture } from './autobahnTextures';
import { autobahnSignAtlas, placeProp, prop, type PropModel } from './props';
import SIGN_ATLAS from './autobahnSigns.json';
import {
  LED,
  SODIUM,
  bakeTerrainLightmap,
  buildClutter,
  buildLampMeshes,
  buildTrees,
  buildTurbines,
  gridGeometry,
  lampPool,
  surfaceDetailOf,
  updateTreeLods,
  type Lamp,
  type SceneryQuality,
  type SceneryResult,
} from './TrackScenery';
import { AutobahnTraffic } from './autobahnTraffic';
import { cutout } from './instancing';
import { groundMaterial, type GroundLook } from './terrainMaterial';
import { roadMaterial as roadSurface } from './roadMaterial';
import { concreteMaterial } from './structureMaterials';

/*
 * AUTOBAHN scenery (CourseInfo.style 'autobahn'): a German motorway at night, all procedural or our own models.
 *
 * Cross-section, lateral offsets from our centreline (+ = right), E = the asphalt edge (drivable half width + SHOULDER):
 *   +E          right guardrail (the physics wall stands here), verge, delineators on the rail, emergency phones
 *   −E          our median guardrail; median grass (anti-glare slats near the junction and the village)
 *   −(E+2.6)    the opposite carriageway's median edge and its guardrail; its asphalt to −(3E+2.6), oncoming traffic
 * The terrain is graded flat over that width (CourseDesign.formation).
 */

const MEDIAN = 2.6;
/** road lightmap: rows every LM_STEP samples on the main road, LM_W columns across both carriageways */
const LM_STEP = 4;
const LM_W = 32;
const UP = new THREE.Vector3(0, 1, 0);

type Signs = Record<string, { x: number; y: number; w: number; h: number; w_m: number; h_m: number }>;
const SIGNS = (SIGN_ATLAS as { size: number; signs: Signs }).signs;
const SIGN_SIZE = (SIGN_ATLAS as { size: number }).size;

// ------------------------------------------------------------------ geometry helpers

/**
 * Strips between profile rows: rows[r][k] is profile point k of row r (all rows the same length), `along[r]` the
 * row's distance (u = along × uScale, v = length along the profile × vScale). Each profile segment is its own strip,
 * so profile corners stay sharp. Double-sided materials make the winding irrelevant.
 */
function loft(rows: THREE.Vector3[][], along: number[], uScale = 0.25, vScale = 0.25) {
  const n = rows[0].length;
  const R = rows.length;
  const pos = new Float32Array((n - 1) * R * 2 * 3);
  const uv = new Float32Array((n - 1) * R * 2 * 2);
  const idx: number[] = [];
  for (let r = 0; r < R; r++) {
    let acc = 0;
    for (let k = 0; k < n - 1; k++) {
      const a = rows[r][k], b = rows[r][k + 1];
      const o = (k * R + r) * 2;
      pos.set([a.x, a.y, a.z, b.x, b.y, b.z], o * 3);
      const len = a.distanceTo(b);
      uv.set([along[r] * uScale, acc * vScale, along[r] * uScale, (acc + len) * vScale], o * 2);
      acc += len;
      if (r > 0) {
        const p0 = (k * R + r - 1) * 2;
        idx.push(p0, p0 + 1, o, p0 + 1, o + 1, o);
      }
    }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  g.setAttribute('uv', new THREE.BufferAttribute(uv, 2));
  g.setIndex(idx);
  g.computeVertexNormals();
  return g;
}

/** A profile of (lateral, height above the road) pairs swept along the track from a to b. */
function ribbon(track: Track, a: number, b: number, profile: (i: number) => [number, number][], step = 4, uScale = 0.25, vScale = 0.25) {
  a = clamp(Math.round(a), 0, track.count - 1);
  b = clamp(Math.round(b), 0, track.count - 1);
  const rows: THREE.Vector3[][] = [], along: number[] = [];
  for (let i = a; ; i = Math.min(b, i + step)) {
    rows.push(profile(i).map(([lat, h]) => track.pointAt(i, lat).setY(track.pointAt(i, lat).y + h)));
    along.push(i);
    if (i >= b) break;
  }
  return rows.length > 1 ? loft(rows, along, uScale, vScale) : null;
}

/** An oriented box (axes x, y, z unit and orthogonal) with its uvs in metres / 4. */
function box(center: THREE.Vector3, x: THREE.Vector3, y: THREE.Vector3, z: THREE.Vector3, sx: number, sy: number, sz: number) {
  // a left-handed basis would mirror the box and turn its faces inside out (the box is symmetric: flip z instead)
  if (new THREE.Vector3().crossVectors(x, y).dot(z) < 0) z = z.clone().negate();
  const g = new THREE.BoxGeometry(sx, sy, sz);
  const uv = g.getAttribute('uv') as THREE.BufferAttribute;
  // faces in order +x −x +y −y +z −z, four vertices each: scale each face's uv to its size
  const dims: [number, number][] = [[sz, sy], [sz, sy], [sx, sz], [sx, sz], [sx, sy], [sx, sy]];
  for (let f = 0; f < 6; f++)
    for (let k = 0; k < 4; k++) uv.setXY(f * 4 + k, (uv.getX(f * 4 + k) * dims[f][0]) / 4, (uv.getY(f * 4 + k) * dims[f][1]) / 4);
  g.applyMatrix4(new THREE.Matrix4().makeBasis(x, y, z).setPosition(center));
  return g;
}

/** Triangles from explicit vertex lists (each face its own vertices: flat shading), uv planar in metres / 4. */
function faces(polys: THREE.Vector3[][]) {
  const pos: number[] = [], uv: number[] = [], idx: number[] = [];
  for (const poly of polys) {
    const base = pos.length / 3;
    const n = new THREE.Vector3().subVectors(poly[1], poly[0]).cross(new THREE.Vector3().subVectors(poly[2], poly[0])).normalize();
    const ax = Math.abs(n.x) > 0.7 ? 'z' : 'x';
    for (const v of poly) {
      pos.push(v.x, v.y, v.z);
      uv.push(v[ax] / 4, (Math.abs(n.y) > 0.7 ? v.z : v.y) / 4);
    }
    for (let k = 1; k < poly.length - 1; k++) idx.push(base, base + k, base + k + 1);
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
  g.setIndex(idx);
  g.computeVertexNormals();
  return g;
}

/**
 * Asphalt strips (the slip road, the overpasses' roads) for the merged road mesh: rows of points across, with the
 * marking atlas' u per point, the distance along per row and the lightmap's uv per point. Faces turned up.
 */
function asphalt(rows: { pts: THREE.Vector3[]; u: number[]; v: number; lm: [number, number][] }[]) {
  const n = rows[0].pts.length, R = rows.length;
  const pos = new Float32Array(n * R * 3), nor = new Float32Array(n * R * 3), uv = new Float32Array(n * R * 2), uv1 = new Float32Array(n * R * 2);
  const road = new Float32Array(n * R * 2);
  rows.forEach((row, r) =>
    row.pts.forEach((p, k) => {
      const o = r * n + k;
      pos.set([p.x, p.y, p.z], o * 3);
      nor.set([0, 1, 0], o * 3);
      uv.set([row.u[k] / ATLAS_W, row.v], o * 2);
      uv1.set(row.lm[k], o * 2);
      // (metres from the strip's middle, half its width between the skirts: what render/roadMaterial.ts paints by)
      const half = row.pts[1].distanceTo(row.pts[n - 2]) / 2;
      road.set([row.pts[1].distanceTo(p) * (k === 0 ? -1 : 1) - half, half], o * 2);
    }),
  );
  // which winding faces up
  const a = rows[0].pts[0], b = rows[0].pts[1], c = rows[1].pts[0];
  const upward = new THREE.Vector3().subVectors(b, a).cross(new THREE.Vector3().subVectors(c, a)).y > 0;
  const idx: number[] = [];
  for (let r = 0; r < R - 1; r++)
    for (let k = 0; k < n - 1; k++) {
      const i0 = r * n + k, i1 = i0 + 1, i2 = i0 + n, i3 = i2 + 1;
      if (upward) idx.push(i0, i1, i2, i1, i3, i2);
      else idx.push(i0, i2, i1, i1, i2, i3);
    }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  g.setAttribute('normal', new THREE.BufferAttribute(nor, 3));
  g.setAttribute('uv', new THREE.BufferAttribute(uv, 2));
  g.setAttribute('uv1', new THREE.BufferAttribute(uv1, 2));
  g.setAttribute('road', new THREE.BufferAttribute(road, 2));
  g.setIndex(idx);
  return g;
}

/** Instances grouped in chunks along the road (each chunk its own mesh, so the renderer culls the far ones). */
function chunked(geo: THREE.BufferGeometry, mat: THREE.Material, items: { m: THREE.Matrix4; s: number }[], name: string, shadow = false, chunk = 600) {
  const group = new THREE.Group();
  group.name = name;
  const bins = new Map<number, THREE.Matrix4[]>();
  for (const it of items) {
    const k = Math.floor(it.s / chunk);
    if (!bins.has(k)) bins.set(k, []);
    bins.get(k)!.push(it.m);
  }
  for (const list of bins.values()) {
    const mesh = new THREE.InstancedMesh(geo, mat, list.length);
    list.forEach((m, k) => mesh.setMatrixAt(k, m));
    mesh.computeBoundingSphere();
    mesh.castShadow = shadow;
    mesh.receiveShadow = true;
    group.add(mesh);
  }
  return group;
}

/**
 * A terrain grid (gridGeometry: PlaneGeometry order, nx × nz vertices) cut into tiles that share its vertex buffers,
 * so the renderer culls those behind the camera (normals, colours and lightmap uvs stay those of the whole grid).
 */
function tiles(geo: THREE.BufferGeometry, nx: number, nz: number, tx: number, tz: number, mat: THREE.Material, name: string) {
  const group = new THREE.Group();
  group.name = name;
  const index = geo.index!.array;
  const pos = geo.getAttribute('position') as THREE.BufferAttribute;
  const cx = nx - 1, cz = nz - 1;
  for (let a = 0; a < tx; a++)
    for (let b = 0; b < tz; b++) {
      const i0 = Math.floor((a * cx) / tx), i1 = Math.floor(((a + 1) * cx) / tx);
      const j0 = Math.floor((b * cz) / tz), j1 = Math.floor(((b + 1) * cz) / tz);
      const idx = new Uint32Array((i1 - i0) * (j1 - j0) * 6);
      let o = 0;
      for (let j = j0; j < j1; j++) {
        idx.set(index.subarray((j * cx + i0) * 6, (j * cx + i1) * 6), o);
        o += (i1 - i0) * 6;
      }
      const g = new THREE.BufferGeometry();
      for (const [k, v] of Object.entries(geo.attributes)) g.setAttribute(k, v);
      g.setIndex(new THREE.BufferAttribute(idx, 1));
      const box = new THREE.Box3();
      const v = new THREE.Vector3();
      for (const j of [j0, j1]) for (let i = i0; i <= i1; i++) box.expandByPoint(v.fromBufferAttribute(pos, j * nx + i));
      for (let j = j0; j <= j1; j++) for (const i of [i0, i1]) box.expandByPoint(v.fromBufferAttribute(pos, j * nx + i));
      // heights inside the tile
      let lo = box.min.y, hi = box.max.y;
      for (let j = j0; j <= j1; j += 2) for (let i = i0; i <= i1; i += 2) {
        const y = pos.getY(j * nx + i);
        lo = Math.min(lo, y);
        hi = Math.max(hi, y);
      }
      box.min.y = lo - 1;
      box.max.y = hi + 1;
      g.boundingBox = box;
      g.boundingSphere = box.getBoundingSphere(new THREE.Sphere());
      const mesh = new THREE.Mesh(g, mat);
      mesh.name = name;
      group.add(mesh);
    }
  return group;
}

/** A merged geometry with one vertex colour per part. */
function coloured(parts: [THREE.BufferGeometry, string][]) {
  return mergeGeometries(
    parts.map(([g, c]) => {
      const col = new THREE.Color(c);
      const n = g.getAttribute('position').count;
      g.setAttribute('color', new THREE.Float32BufferAttribute(new Array(n).fill(0).flatMap(() => [col.r, col.g, col.b]), 3));
      return g;
    }),
  );
}

/** Row by row lamp light: `at(r, c, out)` gives texel (r, c)'s world position, or false for an unlit row. */
function bakeLightmap(rows: number, lamps: Lamp[], at: (r: number, c: number, out: THREE.Vector3) => boolean) {
  const data = new Uint8Array(LM_W * rows * 4);
  const p = new THREE.Vector3(), mid = new THREE.Vector3();
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < LM_W; c++) data[(r * LM_W + c) * 4 + 3] = 255;
    if (!at(r, LM_W / 2, mid)) continue;
    const near = lamps.filter((l) => (l.position.x - mid.x) ** 2 + (l.position.z - mid.z) ** 2 < 95 * 95);
    if (!near.length) continue;
    for (let c = 0; c < LM_W; c++) {
      at(r, c, p);
      let rr = 0, gg = 0, bb = 0;
      for (const l of near) {
        const k = lampPool(l.position.x - p.x, l.position.y - p.y, l.position.z - p.z);
        rr += l.color.r * k;
        gg += l.color.g * k;
        bb += l.color.b * k;
      }
      const o = (r * LM_W + c) * 4;
      data[o] = Math.min(255, rr * 255);
      data[o + 1] = Math.min(255, gg * 255);
      data[o + 2] = Math.min(255, bb * 255);
    }
  }
  const tex = new THREE.DataTexture(data, LM_W, rows, THREE.RGBAFormat);
  tex.channel = 1;
  tex.magFilter = THREE.LinearFilter;
  tex.minFilter = THREE.LinearFilter;
  tex.needsUpdate = true;
  return tex;
}

/** A sign face (and its grey back) as a quad of the sign atlas. */
function signQuad(name: string, center: THREE.Vector3, right: THREE.Vector3, facing: THREE.Vector3, w?: number, h?: number) {
  const s = SIGNS[name], back = SIGNS.back;
  const W = w ?? s.w_m, H = h ?? s.h_m;
  const quad = (rect: typeof s, c: THREE.Vector3, rt: THREE.Vector3) => {
    const u0 = rect.x / SIGN_SIZE, u1 = (rect.x + rect.w) / SIGN_SIZE, v0 = 1 - (rect.y + rect.h) / SIGN_SIZE, v1 = 1 - rect.y / SIGN_SIZE;
    const corners = [
      [-0.5, -0.5, u0, v0], [0.5, -0.5, u1, v0], [0.5, 0.5, u1, v1], [-0.5, 0.5, u0, v1],
    ];
    const pos: number[] = [], uv: number[] = [], nor: number[] = [];
    const n = new THREE.Vector3().crossVectors(rt, UP);
    for (const [x, y, u, v] of corners) {
      pos.push(c.x + rt.x * x * W, c.y + y * H, c.z + rt.z * x * W);
      uv.push(u, v);
      nor.push(n.x, n.y, n.z);
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
    g.setAttribute('normal', new THREE.Float32BufferAttribute(nor, 3));
    g.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
    g.setIndex([0, 1, 2, 0, 2, 3]);
    return g;
  };
  // the front looks along −facing (towards whoever it faces): seen from there, `right` runs left to right
  const front = quad(s, center, right);
  const behind = center.clone().addScaledVector(facing, -0.04);
  const backQuad = quad(back, behind, right.clone().negate());
  return [front, backQuad];
}

// ------------------------------------------------------------------ the scenery

export function buildAutobahnScenery(track: Track, terrain: TerrainData, quality: SceneryQuality): SceneryResult {
  const group = new THREE.Group();
  group.name = 'scenery';
  const nightEmissive: THREE.MeshStandardMaterial[] = [];
  const shadows = quality.shadows;
  // the low setting (phones): half-size textures, no fence
  const low = !quality.photoTextures;
  const end = track.count - 1;
  const E = track.width[0] / 2 + SHOULDER;
  /** the opposite carriageway: centre, outer asphalt edge */
  const OPP = -(2 * E + MEDIAN), OUT = -(3 * E + MEDIAN);
  const LM_LAT: [number, number] = [OUT - 0.6, E + 0.6];
  const keepOut: { x: number; z: number; r: number }[] = [];
  const lamps: Lamp[] = [];
  const covers: number[] = [];
  const zones = (tag: Parameters<Track['zoneRanges']>[0]) => track.zoneRanges(tag);
  const inRanges = (s: number, ranges: [number, number][], pad = 0) => ranges.some(([a, b]) => s >= a - pad && s <= b + pad);
  /** horizontal frame at s: forward, right, heading */
  const frame = (s: number) => {
    const i = clamp(Math.round(s), 0, end);
    const f = new THREE.Vector3(track.fwd[i * 3], 0, track.fwd[i * 3 + 2]).normalize();
    return { i, f, r: new THREE.Vector3(-f.z, 0, f.x), h: track.heading[i] };
  };
  const at = (s: number, lat: number, h = 0) => {
    const v = track.pointAt(clamp(s, 0, end), lat);
    v.y += h;
    return v;
  };
  const yawQ = (yaw: number) => new THREE.Quaternion().setFromAxisAngle(UP, yaw);
  const one = new THREE.Vector3(1, 1, 1);

  const bridges = zones('bridge'), overpasses = zones('overpass'), villages = zones('village'), forests = zones('forest');
  const junction = zones('interchange')[0] ?? null;
  // the exit: its lane (the hard shoulder, marked off with broad dashes) from e0, the slip road leaves at the gore
  const e0 = junction ? junction[0] + 60 : -1e9;
  const gore = e0 + 240;
  /** no guardrail on the right where the exit lane leads off */
  const railGap: [number, number] = [e0 - 30, gore + 150];
  const inGap = (s: number) => s > railGap[0] && s < railGap[1];

  // ---------------------------------------------------------------- materials
  const steel = new THREE.MeshStandardMaterial({ color: '#e1e4e1', metalness: 0.55, roughness: 0.38, side: THREE.DoubleSide });
  const galvanised = new THREE.MeshStandardMaterial({ color: '#b9bdba', metalness: 0.5, roughness: 0.5 });
  // the layered look (quality medium and up): the ground, the road's wear and the concrete of render/structureMaterials.ts
  const detail = surfaceDetailOf(quality);
  const concrete = detail
    ? (concreteMaterial('formed', { doubleSide: true, uvScale: 4 }) as unknown as THREE.MeshStandardMaterial)
    : new THREE.MeshStandardMaterial({ map: makeConcreteTexture(false, null), roughness: 0.9, side: THREE.DoubleSide });
  const grass = new THREE.MeshStandardMaterial({ color: '#33452a', roughness: 0.97, side: THREE.DoubleSide, envMapIntensity: 0.3 });
  const reflMat = new THREE.MeshStandardMaterial({ color: '#f4f1e8', emissive: '#fff1d0', emissiveIntensity: 0.55, roughness: 0.3 });
  nightEmissive.push(reflMat);

  // ---------------------------------------------------------------- the interchange's slip road
  interface SlipRow { left: THREE.Vector3; r: THREE.Vector3; w: number; v: number; d: number }
  const slip: SlipRow[] = [];
  if (junction) {
    // taper: the asphalt widens to the right over 110 m before the gore
    for (let s = gore - 110; s < gore; s += 2) {
      const { r } = frame(s);
      slip.push({ left: at(s, E), r, w: 8 * smoothstep(0, 1, (s - gore + 110) / 110), v: s - gore + 110, d: s - gore });
    }
    // then it leaves at a shallow angle and bends right (heading falls), climbing with the land
    const c = at(gore, E + 4);
    let hd = track.heading[clamp(gore, 0, end)];
    let turned = 0;
    const path: { c: THREE.Vector3; h: number; d: number }[] = [];
    for (let d = 0; d <= 520; d += 2) {
      path.push({ c: c.clone(), h: hd, d });
      const k = d < 70 ? 1 / 2500 : d < 190 ? lerp(1 / 2500, 1 / 240, (d - 70) / 120) : turned < 1.2 ? 1 / 240 : 0;
      hd -= k * 2;
      turned += k * 2;
      c.x += Math.sin(hd) * 2;
      c.z += Math.cos(hd) * 2;
    }
    // heights: the main road's at first, then the ground's (smoothed), never below the ground across its width
    const ground = (q: THREE.Vector3, h: number) => {
      const rt = new THREE.Vector3(-Math.cos(h), 0, Math.sin(h));
      let g = -Infinity;
      for (const u of [-4.6, 0, 4.6]) g = Math.max(g, terrain.heightAt(q.x + rt.x * u, q.z + rt.z * u));
      return g;
    };
    let ys = path.map(({ c, h, d }) => lerp(track.pos[clamp(gore + d, 0, end) * 3 + 1], ground(c, h) + 0.35, smoothstep(30, 170, d)));
    for (let pass = 0; pass < 3; pass++) {
      ys = ys.map((_, k) => {
        let sum = 0, n = 0;
        for (let j = Math.max(0, k - 8); j <= Math.min(ys.length - 1, k + 8); j++, n++) sum += ys[j];
        return sum / n;
      });
      ys = ys.map((y, k) => (path[k].d > 50 ? Math.max(y, ground(path[k].c, path[k].h) + 0.25) : y));
    }
    path.forEach(({ c: cc, h, d }, k) => {
      const r = new THREE.Vector3(-Math.cos(h), 0, Math.sin(h));
      const left = cc.clone().addScaledVector(r, -4);
      left.y = ys[k];
      slip.push({ left, r, w: 8, v: 110 + d, d });
    });
    // lamps along its outer edge, delineators on both sides, keep the trees off it
    for (const row of slip) {
      const centre = row.left.clone().addScaledVector(row.r, row.w / 2);
      if (row.d % 10 === 0) keepOut.push({ x: centre.x, z: centre.z, r: 13 });
      if (row.d >= 30 && row.d <= 340 && row.d % 40 === 30)
        lamps.push({ position: row.left.clone().addScaledVector(row.r, row.w + 1.1), color: SODIUM.clone(), s: gore + row.d, aim: centre });
    }
  }
  const slipLeft = (row: SlipRow, u: number) => row.left.clone().addScaledVector(row.r, u);

  // ---------------------------------------------------------------- lamps
  // the junction is lit from masts in the median, the start and the finish with white LED lamps
  const medianLamp = (s: number, color: THREE.Color) => {
    const i = clamp(Math.round(s), 0, end);
    lamps.push({ position: at(i, -(E + MEDIAN / 2), -0.45), color: color.clone(), s: i });
  };
  if (junction) for (let s = junction[0] - 100; s <= junction[1] + 100; s += 48) medianLamp(s, SODIUM);
  for (let s = track.startS - 80; s <= track.startS + 230; s += 50) medianLamp(s, LED);
  for (let s = track.finishS - 150; s <= Math.min(end - 20, track.finishS + 400); s += 50) medianLamp(s, LED);
  buildLampMeshes(track, lamps, group, nightEmissive);

  // ---------------------------------------------------------------- road
  const mainRows = Math.ceil(end / LM_STEP) + 1;
  const slipRow0 = mainRows;
  const blackRow = slipRow0 + slip.length;
  const lmRows = blackRow + 1;
  const lmY = (row: number) => (row + 0.5) / lmRows;
  const lm = { lat: LM_LAT, step: LM_STEP, rows: lmRows };
  const roadGeos: THREE.BufferGeometry[] = [
    buildAutobahnRoadGeometry(track, ATLAS_W, (i) => (i >= e0 && i < gore ? LAYOUT.exit : LAYOUT.main), lm),
    buildAutobahnRoadGeometry(track, ATLAS_W, () => LAYOUT.main, lm, { center: OPP, mirror: true }),
  ];
  if (slip.length > 1) {
    roadGeos.push(
      asphalt(
        slip.map((row, j) => {
          const us = [-0.6, 0, row.w * 0.25, row.w * 0.5, row.w * 0.75, row.w, row.w + 0.6];
          const pts = us.map((u) => slipLeft(row, u));
          pts[0].y -= 1.4;
          pts[pts.length - 1].y -= 1.4;
          // the right edge line keeps its place while the taper widens (the left one appears once it is 7.4 m)
          const tex = us.map((u) => LAYOUT.slip + clamp(8 - row.w + u, -0.3, 8.3));
          return { pts, u: tex, v: row.v, lm: us.map((u) => [(u + 0.6) / 9.2, lmY(slipRow0 + j)] as [number, number]) };
        }),
      ),
    );
  }
  const overpassRoads: THREE.BufferGeometry[] = [];

  // ---------------------------------------------------------------- guardrails, posts, delineators
  const railGeos: THREE.BufferGeometry[] = [];
  const W_BEAM: [number, number][] = [[-0.12, 0.5], [-0.17, 0.56], [-0.11, 0.62], [-0.11, 0.68], [-0.17, 0.74], [-0.12, 0.8]];
  const rightRuns: [number, number][] = junction ? [[0, railGap[0]], [railGap[1], end]] : [[0, end]];
  for (const [a, b] of rightRuns) {
    const g = ribbon(track, a, b, () => W_BEAM.map(([o, h]) => [E + o, h] as [number, number]));
    if (g) railGeos.push(g);
  }
  // ours and the opposite carriageway's in the median (each faces its own road)
  railGeos.push(ribbon(track, 0, end, () => W_BEAM.map(([o, h]) => [-(E + o), h] as [number, number]))!);
  railGeos.push(ribbon(track, 0, end, () => W_BEAM.map(([o, h]) => [-(E + MEDIAN) + o, h] as [number, number]))!);
  const posts: { m: THREE.Matrix4; s: number }[] = [];
  for (let i = 0; i <= end; i += 4) {
    const q = yawQ(track.heading[i]);
    const lats = [-(E - 0.05), -(E + MEDIAN) - 0.05];
    if (!inGap(i)) lats.push(E - 0.05);
    for (const lat of lats) posts.push({ m: new THREE.Matrix4().compose(at(i, lat, 0.38), q, one), s: i });
  }
  group.add(chunked(new THREE.BoxGeometry(0.1, 1.0, 0.12), galvanised, posts, 'guardrail-posts', shadows));

  // delineators: short ones on the guardrails, full posts where there is none; reflectors face the traffic
  const shortPost = coloured([[new THREE.BoxGeometry(0.1, 0.5, 0.12).translate(0, 0.25, 0), '#f2f2ee'], [new THREE.BoxGeometry(0.106, 0.22, 0.126).translate(0, 0.36, 0), '#111111']]);
  const tallPost = coloured([[new THREE.BoxGeometry(0.12, 1.25, 0.14).translate(0, 0.62, 0), '#f2f2ee'], [new THREE.BoxGeometry(0.126, 0.25, 0.146).translate(0, 1.08, 0), '#111111']]);
  const delMat = new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.55 });
  const shortList: { m: THREE.Matrix4; s: number }[] = [], tallList: { m: THREE.Matrix4; s: number }[] = [];
  const reflectors: THREE.Matrix4[] = [];
  const reflGeo = new THREE.PlaneGeometry(0.09, 0.15);
  /**
   * a delineator at (s, lat); its reflector faces back down the road (ours) or up it (the opposite traffic's), or
   * along `towards` (the slip road's)
   */
  const delineator = (s: number, lat: number, tall: boolean, theirs = false, base?: THREE.Vector3, towards?: THREE.Vector3) => {
    const { f } = frame(s);
    const pos = base ?? at(s, lat, tall ? -0.45 : 0.78);
    const facing = towards ?? (theirs ? f : f.clone().negate());
    const q = yawQ(Math.atan2(facing.x, facing.z));
    (tall ? tallList : shortList).push({ m: new THREE.Matrix4().compose(pos, q, one), s });
    const rp = pos.clone().addScaledVector(facing, tall ? 0.075 : 0.065);
    rp.y += tall ? 1.08 : 0.36;
    reflectors.push(new THREE.Matrix4().compose(rp, yawQ(Math.atan2(facing.x, facing.z)), one));
  };
  for (let s = 25; s < end; s += 50) {
    if (inGap(s)) delineator(s, E + 1.0, true);
    else delineator(s, E - 0.05, false);
    delineator(s, -(E - 0.05), false);
    delineator(s, -(E + MEDIAN) - 0.05, false, true);
    delineator(s, OUT - 0.9, true, true);
  }
  for (const row of slip)
    if (row.d > 40 && row.d % 50 === 0) {
      // facing back along the slip road (its forward is (r.z, 0, −r.x))
      const back = new THREE.Vector3(-row.r.z, 0, row.r.x);
      for (const u of [-0.9, row.w + 0.9]) {
        const b = slipLeft(row, u);
        b.y -= 0.45;
        delineator(gore + row.d, 0, true, false, b, back);
      }
    }
  group.add(chunked(shortPost, delMat, shortList, 'delineators', false, 1200));
  group.add(chunked(tallPost, delMat, tallList, 'delineators-tall', false, 1200));
  const reflMesh = new THREE.InstancedMesh(reflGeo, reflMat, reflectors.length);
  reflectors.forEach((m, k) => reflMesh.setMatrixAt(k, m));
  reflMesh.name = 'reflectors';
  group.add(reflMesh);

  // anti-glare slats on the median by the junction and the village
  const glareRanges: [number, number][] = [...(junction ? [[junction[0] - 300, junction[1] + 150] as [number, number]] : []), ...villages];
  const slatMat = cutout(new THREE.MeshStandardMaterial({ map: makeAntiGlareTexture(), alphaTest: 0.5, side: THREE.DoubleSide, roughness: 0.8 }));
  const slatGeos = glareRanges.map(([a, b]) => ribbon(track, a, b, () => [[-(E + MEDIAN / 2), 0.75], [-(E + MEDIAN / 2), 1.75]], 4, 1, 1)).filter((g): g is THREE.BufferGeometry => !!g);
  if (slatGeos.length) {
    const slats = new THREE.Mesh(mergeGeometries(slatGeos), slatMat);
    slats.name = 'anti-glare';
    group.add(slats);
  }

  // ---------------------------------------------------------------- structures
  const concreteGeos: THREE.BufferGeometry[] = [];
  const grassGeos: THREE.BufferGeometry[] = [];
  const piers: THREE.Matrix4[] = [];
  /** a vertical box pier from the ground up to `top` (scaled unit box) */
  const pier = (c: THREE.Vector3, yaw: number, w: number, d: number, bottom: number, top: number) =>
    piers.push(new THREE.Matrix4().compose(new THREE.Vector3(c.x, (bottom + top) / 2, c.z), yawQ(yaw), new THREE.Vector3(w, top - bottom, d)));

  // overpasses: a two-span road bridge across both carriageways at the zone's midpoint (pier in the median),
  // paved slopes in front of the abutments, its road on embankments either side
  for (const [a, b] of overpasses) {
    const m = Math.round((a + b) / 2);
    const { f: A, r: D, h } = frame(m);
    const C = at(m, 0);
    const L0 = E + 9, L1 = OUT - 9, DW = 6;
    const yb = C.y + 5.3, yt = yb + 1.25;
    const P = (l: number, s: number, y: number) => new THREE.Vector3(C.x + D.x * l + A.x * s, y, C.z + D.z * l + A.z * s);
    const gAt = (l: number) => terrain.heightAt(C.x + D.x * l, C.z + D.z * l);
    concreteGeos.push(box(P((L0 + L1) / 2, 0, (yb + yt) / 2), D, UP, A, L0 - L1, yt - yb, 2 * DW));
    for (const side of [-1, 1]) concreteGeos.push(box(P((L0 + L1) / 2, side * (DW - 0.7), yt + 0.15), D, UP, A, L0 - L1 + 0.4, 0.3, 1.6));
    // median pier: three columns under a cross beam
    const lm0 = -(E + MEDIAN / 2), g0 = C.y - 0.45;
    concreteGeos.push(box(P(lm0, 0, yb - 0.4), D, UP, A, 1.3, 0.8, 2 * DW - 1));
    for (const s of [-3.6, 0, 3.6]) pier(P(lm0, s, 0), h, 0.8, 0.8, g0 - 1, yb - 0.75);
    for (const [lEnd, out] of [[L0, 1], [L1, -1]] as const) {
      // abutment wall and the paved slope down to the verge
      const gEnd = Math.min(gAt(lEnd + out * 0.5), g0);
      concreteGeos.push(box(P(lEnd + out * 0.5, 0, (yb + gEnd - 1.5) / 2), D, UP, A, 1.0, yb - gEnd + 1.5, 2 * DW + 1));
      const run = 1.5 * (yb - 0.2 - g0);
      const top = yb - 0.2, foot = lEnd - out * run;
      const w = DW + 1;
      const t0 = P(lEnd, -w, top), t1 = P(lEnd, w, top), f0 = P(foot, -w, g0 - 0.2), f1 = P(foot, w, g0 - 0.2), b0 = P(lEnd, -w, g0 - 0.2), b1 = P(lEnd, w, g0 - 0.2);
      concreteGeos.push(faces([[t0, t1, f1, f0], [t0, f0, b0], [t1, b1, f1]]));
      // the road beyond: on an embankment that comes down to the ground over 90 m
      const rows: THREE.Vector3[][] = [], along: number[] = [];
      for (let d = 1; d <= 91; d += 3) {
        const l = lEnd + out * d;
        const g = gAt(l);
        const ytop = lerp(yt, g + 0.3, smoothstep(0, 1, d / 90));
        const sl = 1.5 * Math.max(0, ytop - g) + 0.5;
        rows.push([P(l, -(DW + sl), g - 0.4), P(l, -DW, ytop - 0.03), P(l, DW, ytop - 0.03), P(l, DW + sl, g - 0.4)]);
        along.push(d);
      }
      grassGeos.push(loft(rows, along));
    }
    // the road across: asphalt from embankment to embankment (unlit: the lightmap's black row)
    const roadRows: { pts: THREE.Vector3[]; u: number[]; v: number; lm: [number, number][] }[] = [];
    for (let l = L1 - 91; l <= L0 + 91; l += 3) {
      const d = l > L0 ? l - L0 : l < L1 ? L1 - l : 0;
      const g = gAt(l);
      const ytop = d > 0 ? lerp(yt, g + 0.3, smoothstep(0, 1, d / 90)) : yt;
      const as = [-4.5, -4, -2, 0, 2, 4, 4.5];
      roadRows.push({
        pts: as.map((s) => P(l, s, ytop + (Math.abs(s) > 4.2 ? -0.2 : 0.03))),
        u: as.map((s) => LAYOUT.plain + clamp(s + 4, -0.3, 8.3)),
        v: l,
        lm: as.map(() => [0.5, lmY(blackRow)] as [number, number]),
      });
    }
    overpassRoads.push(asphalt(roadRows));
    // railings on the caps
    for (const side of [-1, 1]) {
      const sa = side * (DW - 0.25);
      for (const hh of [0.55, 1.05]) railGeos.push(box(P((L0 + L1) / 2, sa, yt + 0.3 + hh), D, UP, A, L0 - L1, 0.07, 0.07));
      for (let l = L1 + 1; l < L0; l += 2) railGeos.push(box(P(l, sa, yt + 0.3 + 0.52), D, UP, A, 0.05, 1.05, 0.05));
    }
    // no rain under the deck
    const parts = 3;
    for (let k = 0; k < parts; k++) {
      const la = lerp(L1, L0, k / parts), lb = lerp(L1, L0, (k + 1) / parts);
      const c0 = P(la, -DW, 0), c1 = P(lb, -DW, 0), c2 = P(lb, DW, 0), c3 = P(la, DW, 0);
      covers.push(c0.x, c0.z, c1.x, c1.z, c2.x, c2.z, c3.x, c3.z, yt + 0.3);
    }
    for (let l = L1 - 90; l <= L0 + 90; l += 10) keepOut.push({ x: C.x + D.x * l, z: C.z + D.z * l, r: 16 });
  }

  // the viaduct: two box-girder decks with a gap over the median, railings on every edge, wall piers to the valley
  for (const [a, b] of bridges) {
    const decks: [number, number][] = [[-(E + 0.7), E + 0.7], [-(E + MEDIAN - 0.7), OUT - 0.7]];
    for (const [d0, d1] of decks) {
      const l0 = Math.min(d0, d1), l1 = Math.max(d0, d1);
      const g = ribbon(track, a - 2, b + 2, () => [
        [l0 + 0.65, -0.05], [l0 + 0.65, 0.25], [l0, 0.25], [l0, -0.5], [l0 + 2.4, -0.75], [l0 + 3.4, -3.3],
        [l1 - 3.4, -3.3], [l1 - 2.4, -0.75], [l1, -0.5], [l1, 0.25], [l1 - 0.65, 0.25], [l1 - 0.65, -0.05],
      ]);
      if (g) concreteGeos.push(g);
      for (const lat of [l0 + 0.3, l1 - 0.3]) {
        for (const hh of [0.8, 1.25]) {
          const r = ribbon(track, a, b, () => [[lat, hh], [lat, hh + 0.08]], 4);
          if (r) railGeos.push(r);
        }
        for (let s = a; s <= b; s += 2.5) {
          const { f, r } = frame(s);
          railGeos.push(box(at(s, lat, 0.75), r, UP, f, 0.05, 1.0, 0.05));
        }
      }
      for (let s = a + 35; s < b - 30; s += 45) {
        const c = at(s, (l0 + l1) / 2);
        const ground = terrain.heightAt(c.x, c.z);
        const top = c.y - 3.3;
        if (top - ground < 2.5) continue;
        const yaw = track.heading[Math.round(s)];
        // local x across the road: the pier wall is wide across, thin along
        piers.push(new THREE.Matrix4().compose(new THREE.Vector3(c.x, (ground - 2 + top - 0.9) / 2, c.z), yawQ(yaw), new THREE.Vector3(4.2, top - 0.9 - ground + 2, 2.0)));
        piers.push(new THREE.Matrix4().compose(new THREE.Vector3(c.x, top - 0.45, c.z), yawQ(yaw), new THREE.Vector3(l1 - l0 - 6.4, 0.9, 2.6)));
      }
    }
  }

  // noise walls along the village (right, behind the verge): aluminium cassettes on steel posts
  const wallGeos: THREE.BufferGeometry[] = [];
  const wallPosts: { m: THREE.Matrix4; s: number }[] = [];
  const WALL = E + 2.2;
  for (const [a0, b0] of villages) {
    const a = a0 + 50, b = b0 - 30;
    const hAt = (i: number) => 4.5 * Math.min(1, 0.25 + 0.75 * smoothstep(a, a + 30, i), 0.25 + 0.75 * smoothstep(b, b - 30, i));
    const g = ribbon(track, a, b, (i) => [[WALL, -0.6], [WALL, hAt(i) - 0.45]], 2, 0.25, 1 / 4.5);
    if (g) wallGeos.push(g);
    for (let i = a; i <= b; i += 4) wallPosts.push({ m: new THREE.Matrix4().compose(at(i, WALL + 0.12, (hAt(i) - 0.45 - 0.6) / 2), yawQ(track.heading[i]), new THREE.Vector3(1, hAt(i) + 0.15, 1)), s: i });
  }
  if (wallGeos.length) {
    const wallMat = new THREE.MeshStandardMaterial({ map: makeNoiseWallTexture(), roughness: 0.7, metalness: 0.2, side: THREE.DoubleSide });
    const walls = new THREE.Mesh(mergeGeometries(wallGeos), wallMat);
    walls.name = 'noise-walls';
    walls.castShadow = shadows;
    walls.receiveShadow = true;
    group.add(walls);
    group.add(chunked(new THREE.BoxGeometry(0.16, 1, 0.16), galvanised, wallPosts, 'noise-wall-posts'));
  }

  // wildlife fence along the forest (not on phones)
  if (!low && forests.length) {
    const fenceMat = cutout(new THREE.MeshStandardMaterial({ map: makeFenceTexture(), alphaTest: 0.4, side: THREE.DoubleSide, roughness: 0.6, metalness: 0.4 }));
    const fenceGeos = forests.map(([a, b]) => ribbon(track, a, b, () => [[E + 6, -0.45], [E + 6, 1.35]], 4, 0.5, 1 / 1.8)).filter((g): g is THREE.BufferGeometry => !!g);
    const fencePosts: { m: THREE.Matrix4; s: number }[] = [];
    for (const [a, b] of forests) for (let i = a; i <= b; i += 4) fencePosts.push({ m: new THREE.Matrix4().compose(at(i, E + 6, 0.5), yawQ(track.heading[i]), one), s: i });
    const fence = new THREE.Mesh(mergeGeometries(fenceGeos), fenceMat);
    fence.name = 'fence';
    group.add(fence);
    group.add(chunked(new THREE.CylinderGeometry(0.06, 0.07, 1.95, 6), new THREE.MeshStandardMaterial({ color: '#4d4136', roughness: 0.9 }), fencePosts, 'fence-posts'));
  }

  // ---------------------------------------------------------------- signs
  const atlas = autobahnSignAtlas();
  const signGeos: THREE.BufferGeometry[] = [];
  const postGeos: THREE.BufferGeometry[] = [];
  /** a sign on posts beside the road; `theirs`: it faces the opposite traffic (we see its back) */
  const groundSign = (name: string, s: number, lat: number, bottom: number, theirs = false) => {
    if (!SIGNS[name]) return;
    const { f, r } = frame(s);
    const facing = theirs ? f.clone() : f.clone().negate();
    const right = theirs ? r.clone().negate() : r.clone();
    const ground = at(s, lat).y - 0.45;
    const { w_m: w, h_m: h } = SIGNS[name];
    const c = at(s, lat);
    c.y = ground + bottom + h / 2;
    signGeos.push(...signQuad(name, c, right, facing));
    const offsets = w < 1.5 ? [0] : [-w * 0.3, w * 0.3];
    for (const o of offsets) {
      const pc = c.clone().addScaledVector(right, o).addScaledVector(facing, -0.08);
      const top = c.y + h / 2 - 0.1;
      pc.y = (ground - 0.3 + top) / 2;
      postGeos.push(new THREE.CylinderGeometry(0.045, 0.05, top - ground + 0.3, 8).translate(pc.x, pc.y, pc.z));
    }
  };
  // gantries: our own model, stretched to span the carriageway between the median and the verge
  const gantries: THREE.Matrix4[] = [];
  const GANTRY_L = -(E + MEDIAN / 2), GANTRY_R = E + 1.6;
  const gantry = (s: number, boards: [string, number][], bottom = 4.7) => {
    const { f, r, h } = frame(s);
    const c = at(s, (GANTRY_L + GANTRY_R) / 2, -0.45);
    gantries.push(new THREE.Matrix4().compose(c, yawQ(h + Math.PI), new THREE.Vector3((GANTRY_R - GANTRY_L) / 19, 1, 1)));
    for (const [name, lat] of boards) {
      if (!SIGNS[name]) continue;
      const bc = at(s, lat).addScaledVector(f, -0.75);
      bc.y += bottom + SIGNS[name].h_m / 2;
      signGeos.push(...signQuad(name, bc, r, f.clone().negate()));
    }
  };
  gantry(track.startS, [['start', 0]], 5.0);
  gantry(track.finishS, [['goal', 0]], 5.0);
  groundSign('limit120', 30, E + 1.4, 1.7);
  groundSign('limit120', 30, -(E + MEDIAN / 2), 1.7);
  groundSign('autobahn', track.startS + 130, E + 1.6, 1.6);
  groundSign('derestrict', track.startS + 260, E + 1.4, 1.7);
  groundSign('derestrict', track.startS + 260, -(E + MEDIAN / 2), 1.7);
  groundSign('dist_a', track.startS + 700, E + 3.0, 1.4);
  groundSign('exit_1000', 900, OUT - 3.0, 1.4, true);
  if (junction) {
    groundSign('exit_2000', e0 - 2000, E + 2.8, 1.5);
    groundSign('exit_1000', e0 - 1000, E + 2.8, 1.5);
    gantry(e0 - 500, [['g1_main', -2.75], ['g1_exit', 3.2]]);
    gantry(e0, [['g2_main', -1.6], ['g2_exit', 6.5]]);
    groundSign('ausfahrt', gore + 30, E + 2.2, 1.0);
    groundSign('dist_b', junction[1] + 400, E + 3.0, 1.4);
    groundSign('exit_2000', junction[1] - 200, OUT - 3.0, 1.4, true);
  }
  for (const [a] of bridges) groundSign('bridge', a - 70, E + 1.8, 1.3);
  if (atlas && signGeos.length) {
    const signMat = cutout(new THREE.MeshStandardMaterial({ map: atlas, emissive: '#ffffff', emissiveMap: atlas, emissiveIntensity: 0.12, roughness: 0.45, alphaTest: 0.5 }));
    nightEmissive.push(signMat);
    const signs = new THREE.Mesh(mergeGeometries(signGeos), signMat);
    signs.name = 'signs';
    group.add(signs);
  }
  if (postGeos.length) railGeos.push(...postGeos);
  const gantryModel = prop('signGantry');
  if (gantryModel && gantries.length) group.add(placeProp(gantryModel, gantries, { castShadow: shadows, name: 'gantries' }).group);
  else
    for (const m of gantries) {
      // fallback: two legs and a box beam
      const legs = [-9.5, 9.5].map((x) => new THREE.BoxGeometry(0.4, 7.7, 0.4).translate(x, 3.85, 0).applyMatrix4(m));
      railGeos.push(...legs, new THREE.BoxGeometry(20.3, 1.4, 1.2).translate(0, 6.6, 0).applyMatrix4(m));
    }
  // start and finish lines
  {
    const lineGeos = [track.startS, track.finishS].map((s) => {
      const { f, r } = frame(s);
      return box(at(s, 0, 0.025), r, UP, f, 2 * E - 1.2, 0.01, 0.5);
    });
    const lines = new THREE.Mesh(mergeGeometries(lineGeos), new THREE.MeshStandardMaterial({ color: '#efefea', roughness: 0.6 }));
    lines.name = 'start-finish-lines';
    group.add(lines);
  }

  // emergency phones every 2 km on both sides (behind the guardrail, facing the road)
  const phones: THREE.Matrix4[] = [];
  const phoneAt = (s: number, theirs: boolean) => {
    while (inRanges(s, bridges, 40) || inGap(s) || inRanges(s, overpasses, -100)) s += 60;
    if (s < 30 || s > end - 30) return;
    const { h } = frame(s);
    phones.push(new THREE.Matrix4().compose(at(s, theirs ? OUT - 1.4 : E + 1.3, -0.45), yawQ(theirs ? h - Math.PI / 2 : h + Math.PI / 2), one));
  };
  for (let s = track.startS + 500; s < track.finishS; s += 2000) phoneAt(s, false);
  for (let s = track.startS + 1500; s < track.finishS; s += 2000) phoneAt(s, true);
  const phoneModel = prop('emergencyPhone');
  if (phoneModel) group.add(placeProp(phoneModel, phones, { castShadow: shadows, name: 'emergency-phones' }).group);
  else {
    const mesh = new THREE.InstancedMesh(new THREE.BoxGeometry(0.36, 1.5, 0.28).translate(0, 0.75, 0), new THREE.MeshStandardMaterial({ color: '#e8641c', roughness: 0.5 }), phones.length);
    phones.forEach((m, k) => mesh.setMatrixAt(k, m));
    group.add(mesh);
  }

  // ---------------------------------------------------------------- villages
  const glow = (m: THREE.MeshStandardMaterial) => {
    if (!m.emissiveMap) return m;
    const c = m.clone();
    c.emissive.set('#ffd29a');
    c.emissiveIntensity = 1.1;
    nightEmissive.push(c);
    return c;
  };
  const houses: THREE.Matrix4[] = [], farms: THREE.Matrix4[] = [], churches: THREE.Matrix4[] = [];
  const village = (city: { x: number; z: number; rx: number; rz: number; angle: number }, n: number, church: boolean, seed: number) => {
    const r = rng(seed);
    const placed: { x: number; z: number; rad: number }[] = [];
    const ca = Math.cos(city.angle), sa = Math.sin(city.angle);
    const tryPlace = (list: THREE.Matrix4[], rad: number, near: number) => {
      for (let attempt = 0; attempt < 60; attempt++) {
        const t = r() * Math.PI * 2, d = Math.sqrt(r()) * near;
        const lx = Math.cos(t) * d * city.rx, lz = Math.sin(t) * d * city.rz;
        const x = city.x + lx * ca - lz * sa, z = city.z + lx * sa + lz * ca;
        if (terrain.roadDistAt(x, z) < 45 + rad) continue;
        if (placed.some((o) => (o.x - x) ** 2 + (o.z - z) ** 2 < (o.rad + rad + 6) ** 2)) continue;
        const yaw = city.angle + Math.floor(r() * 4) * (Math.PI / 2) + (r() - 0.5) * 0.25;
        let lo = Infinity, hi = -Infinity;
        for (const [dx, dz] of [[-rad, -rad], [rad, -rad], [rad, rad], [-rad, rad], [0, 0]]) {
          const y = terrain.heightAt(x + dx * 0.7, z + dz * 0.7);
          lo = Math.min(lo, y);
          hi = Math.max(hi, y);
        }
        if (hi - lo > 3.5 || (terrain.landform.waterLevel !== null && lo < terrain.landform.waterLevel + 1)) continue;
        list.push(new THREE.Matrix4().compose(new THREE.Vector3(x, lo + 0.05, z), yawQ(yaw), one));
        placed.push({ x, z, rad });
        keepOut.push({ x, z, r: rad + 4 });
        return;
      }
    };
    if (church) tryPlace(churches, 17, 0.35);
    for (let k = 0; k < n; k++) {
      if (r() < 0.3) tryPlace(farms, 9, 0.95);
      else tryPlace(houses, 6.5, 0.9);
    }
  };
  const cities = terrain.landform.cities;
  for (const [a, b] of villages) {
    const mid = at((a + b) / 2, 0);
    const city = [...cities].sort((c1, c2) => Math.hypot(c1.x - mid.x, c1.z - mid.z) - Math.hypot(c2.x - mid.x, c2.z - mid.z))[0];
    if (city && Math.hypot(city.x - mid.x, city.z - mid.z) < 1200) village(city, 30, true, 5);
  }
  if (junction) {
    const mid = at(gore + 200, 0);
    const city = [...cities].sort((c1, c2) => Math.hypot(c1.x - mid.x, c1.z - mid.z) - Math.hypot(c2.x - mid.x, c2.z - mid.z))[0];
    if (city && Math.hypot(city.x - mid.x, city.z - mid.z) < 1200) village(city, 14, false, 6);
  }
  for (const [id, list, name] of [['villageHouse', houses, 'houses'], ['villageFarmhouse', farms, 'farmhouses'], ['villageChurch', churches, 'church']] as const) {
    const model: PropModel | null = prop(id);
    if (model && list.length) group.add(placeProp(model, list, { castShadow: shadows, material: glow, name }).group);
  }

  // ---------------------------------------------------------------- merged meshes
  roadGeos.push(...overpassRoads);
  const roadTex = makeAutobahnRoadTexture(low ? 0.5 : 1);
  roadTex.repeat.set(1, 1 / ATLAS_L);
  const asphaltN = makeAsphaltNormal();
  asphaltN.repeat.set(18, 1 / 2.4);
  const laneCentres = [3.225, 6.975, 10.725].map((u) => -E + u);
  const roadMaterial = detail
    ? (roadSurface({ markings: { atlas: roadTex, scale: [1, 1 / ATLAS_L] }, lanes: laneCentres }, detail) as unknown as THREE.MeshStandardMaterial)
    : new THREE.MeshStandardMaterial({
        map: roadTex,
        normalMap: asphaltN,
        normalScale: new THREE.Vector2(0.55, 0.55),
        roughness: 0.8,
        metalness: 0,
        envMapIntensity: 0.6,
      });
  const road = new THREE.Mesh(mergeGeometries(roadGeos), roadMaterial);
  road.receiveShadow = true;
  road.name = 'road';
  group.add(road);
  const rails = new THREE.Mesh(mergeGeometries(railGeos), steel);
  rails.name = 'guardrails';
  rails.castShadow = shadows;
  rails.receiveShadow = true;
  group.add(rails);
  if (concreteGeos.length) {
    const structures = new THREE.Mesh(mergeGeometries(concreteGeos), concrete);
    structures.name = 'structures';
    structures.castShadow = shadows;
    structures.receiveShadow = true;
    group.add(structures);
  }
  if (grassGeos.length) {
    const banks = new THREE.Mesh(mergeGeometries(grassGeos), grass);
    banks.name = 'embankments';
    banks.receiveShadow = true;
    group.add(banks);
  }
  if (piers.length) {
    const pierMesh = new THREE.InstancedMesh(new THREE.BoxGeometry(1, 1, 1), concrete, piers.length);
    piers.forEach((m, k) => pierMesh.setMatrixAt(k, m));
    pierMesh.castShadow = shadows;
    pierMesh.receiveShadow = true;
    pierMesh.name = 'piers';
    group.add(pierMesh);
  }

  // ---------------------------------------------------------------- terrain
  // (moonlit mown grass read as snow at the mountain roads' brightness: the plain material's 0.72, the layered one's look)
  const look: GroundLook = { grass: 'grass', waterLevel: terrain.landform.waterLevel, brightness: 0.8 };
  const terrainMat = detail
    ? (groundMaterial(look, detail) as unknown as THREE.MeshStandardMaterial)
    : new THREE.MeshStandardMaterial({
        vertexColors: true,
        map: makeGroundDetail(),
        normalMap: makeGroundNormal(),
        normalScale: new THREE.Vector2(0.8, 0.8),
        roughness: 0.95,
        metalness: 0,
        envMapIntensity: 0.3,
      });
  if (!detail) terrainMat.color.setScalar(0.72);
  const nearTiles = tiles(gridGeometry(terrain.near, terrain, true, !!detail), terrain.near.nx, terrain.near.nz, 16, 2, terrainMat, 'terrain-near');
  nearTiles.traverse((o) => (o.receiveShadow = true));
  group.add(nearTiles);
  const farMat = detail ? (groundMaterial(look, detail, true) as unknown as THREE.MeshStandardMaterial) : terrainMat.clone();
  if (!detail) farMat.normalMap = null;
  farMat.polygonOffset = true;
  farMat.polygonOffsetFactor = 2;
  farMat.polygonOffsetUnits = 4;
  group.add(tiles(gridGeometry(terrain.far, terrain, false, !!detail), terrain.far.nx, terrain.far.nz, 8, 4, farMat, 'terrain-far'));

  // ---------------------------------------------------------------- baked lamp light
  roadMaterial.lightMap = bakeLightmap(lmRows, lamps, (r, c, out) => {
    if (r < mainRows) {
      track.pointAt(Math.min(r * LM_STEP, end), lerp(LM_LAT[0], LM_LAT[1], (c + 0.5) / LM_W), out);
      return true;
    }
    if (r < blackRow) {
      const row = slip[r - slipRow0];
      out.copy(slipLeft(row, -0.6 + ((c + 0.5) / LM_W) * 9.2));
      return true;
    }
    return false;
  });
  roadMaterial.lightMapIntensity = 17;
  terrainMat.lightMap = bakeTerrainLightmap(terrain.near, lamps);
  // the pools of light on the verges stay dimmer than the road (a row of LED lamps lit the ground like snow)
  terrainMat.lightMapIntensity = 7;

  // ---------------------------------------------------------------- trees, bushes, turbines
  const inForest = (s: number) => inRanges(s, forests);
  const clear = (x: number, z: number) => !keepOut.some((k) => (x - k.x) ** 2 + (z - k.z) ** 2 < k.r * k.r);
  const trees = buildTrees(terrain, quality.treeDensity, quality.treeLod, {
    vegetation: quality.vegetation,
    style: 'autobahn',
    clearance: -OUT + 5,
    keep: clear,
    // the land around is wide and mostly far forest: big chunks (draw calls) where only the far mesh ever shows
    chunk: 480,
    farChunk: 1280,
    extra: (add) => {
      // the forest comes close to the verges (behind the fence on the right, beyond the opposite carriageway)
      const r = rng(99);
      const q = new THREE.Vector3();
      for (let s = 0; s < end; s += 3) {
        const forest = inForest(s);
        const n = (forest ? 1.8 : 0.5) * quality.treeDensity;
        for (const side of [1, -1]) {
          if (side > 0 && (inRanges(s, villages, 30) || (junction && s > junction[0] - 40 && s < junction[1] + 60))) continue;
          if (inRanges(s, bridges, 10)) continue;
          for (let k = 0; k < n + r() - 1; k++) {
            const lat = side > 0 ? E + 8.5 + r() ** 1.6 * 34 : OUT - 4 - r() ** 1.6 * 30;
            track.pointAt(s + r() * 3, lat, q);
            add(q.x, q.z, (8 + r() * 9) / 14);
          }
        }
      }
    },
  });
  group.add(trees);
  const clutter = buildClutter(track, terrain, quality.treeDensity * 0.6, () => null, keepOut, {
    accept: (s, lat) => !inRanges(s, bridges, 10) && (lat > 0 ? lat > E + 7 && !inGap(s) : lat < OUT - 3),
    rocks: false,
    vegetation: quality.vegetation,
    style: 'autobahn',
  });
  group.add(clutter);
  const turbines = buildTurbines(terrain);
  group.add(turbines.group);

  // ---------------------------------------------------------------- traffic
  const lanes = [3.225, 6.975, 10.725];
  const traffic = new AutobahnTraffic(
    track,
    lanes.map((u) => -(E + MEDIAN) - u),
    lanes.map((u) => -E + u),
    undefined,
    low ? 500 : 1000,
  );
  group.add(traffic.group);

  return {
    group,
    lamps,
    roadMaterial,
    nightEmissive,
    lightmapMats: [roadMaterial, terrainMat],
    covers: new Float32Array(covers),
    update(time, cameraPos, view) {
      vegetationFrame(time, cameraPos);
      updateTreeLods(trees, cameraPos, view);
      updateTreeLods(clutter, cameraPos, view);
      turbines.update(time);
      traffic.update(time, cameraPos);
    },
  };
}
