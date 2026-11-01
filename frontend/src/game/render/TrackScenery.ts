import * as THREE from 'three';
import { mergeGeometries, mergeVertices } from 'three/examples/jsm/utils/BufferGeometryUtils.js';
import { Track } from '../track/Track';
import type { TerrainData, HeightGrid } from '../track/terrain';
import type { Landform } from '../track/landforms';
import { buildRoadGeometry, classifySides, SHOULDER } from '../track/roadGeometry';
import { clamp, fbm, lerp, noise2, rng, smoothstep } from '../util/math';
import {
  makeAsphaltNormal,
  makeConcreteTexture,
  makeGroundDetail,
  makeGroundNormal,
  makeRoadTexture,
  makeFoliageTexture,
  makeSignTexture,
  makeVendingTexture,
} from './textures';
import { surfaceImage as photoImage, surfaceTexture as photoTexture, type SurfaceName } from './surfaceTextures';
import { findCorners } from '../track/corners';

export interface Lamp {
  position: THREE.Vector3;
  color: THREE.Color;
  /** track distance, for lightmaps and pooling */
  s: number;
}

export interface SceneryResult {
  group: THREE.Group;
  lamps: Lamp[];
  roadMaterial: THREE.MeshStandardMaterial;
  /** emissive materials that should brighten at night */
  nightEmissive: THREE.MeshStandardMaterial[];
  /** materials carrying the baked lamp lightmap (scaled with lamp state) */
  lightmapMats: THREE.MeshStandardMaterial[];
  update(time: number, cameraPos: THREE.Vector3): void;
}

const SODIUM = new THREE.Color('#ffa850');
const LED = new THREE.Color('#e4ecff');

export interface SceneryQuality {
  treeDensity: number;
  shadows: boolean;
  photoTextures: boolean;
  treeLod: number;
}

/** Builds every static mesh along and around the course. */
export function buildScenery(track: Track, terrain: TerrainData, quality: SceneryQuality): SceneryResult {
  const group = new THREE.Group();
  group.name = 'scenery';
  const sides = classifySides(track, terrain);
  const nightEmissive: THREE.MeshStandardMaterial[] = [];
  const surfaceImage = (n: SurfaceName) => (quality.photoTextures ? photoImage(n) : null);
  const surfaceTexture = (n: SurfaceName, srgb: boolean) => (quality.photoTextures ? photoTexture(n, srgb) : null);

  // ------------------------------------------------------------------ road
  // scanned asphalt when available (normal/roughness at full resolution, 2.7 m tiles)
  const roadTex = makeRoadTexture(surfaceImage('asphalt_albedo'));
  roadTex.repeat.set(1, 1 / 8);
  const photoN = surfaceTexture('asphalt_normal', false);
  const asphaltN = photoN ?? makeAsphaltNormal();
  if (photoN) asphaltN.repeat.set(4, 3 / 8);
  else asphaltN.repeat.set(3, 1 / 2.4);
  const asphaltR = surfaceTexture('asphalt_rough', false);
  asphaltR?.repeat.copy(asphaltN.repeat);
  const roadMaterial = new THREE.MeshStandardMaterial({
    map: roadTex,
    normalMap: asphaltN,
    normalScale: new THREE.Vector2(photoN ? 1 : 0.6, photoN ? 1 : 0.6),
    roughnessMap: asphaltR,
    roughness: asphaltR ? 1 : 0.78,
    metalness: 0.0,
    envMapIntensity: 0.6,
  });
  const road = new THREE.Mesh(buildRoadGeometry(track), roadMaterial);
  road.receiveShadow = true;
  road.name = 'road';
  group.add(road);

  // --------------------------------------------------------------- terrain
  const detail = surfaceTexture('ground_detail', true) ?? makeGroundDetail();
  const groundN = surfaceTexture('ground_normal', false) ?? makeGroundNormal();
  const terrainMat = new THREE.MeshStandardMaterial({
    vertexColors: true,
    map: detail,
    normalMap: groundN,
    normalScale: new THREE.Vector2(0.8, 0.8),
    roughness: 0.95,
    metalness: 0,
    envMapIntensity: 0.3,
  });
  const nearMesh = new THREE.Mesh(gridGeometry(terrain.near, terrain, true), terrainMat);
  nearMesh.receiveShadow = true;
  nearMesh.name = 'terrain-near';
  group.add(nearMesh);
  const farMat = terrainMat.clone();
  farMat.normalMap = null;
  // where the two grids overlap at the near grid's border they are nearly coplanar: push the coarse
  // mesh back in depth so the near mesh always wins instead of z-fighting (flickering hillsides)
  farMat.polygonOffset = true;
  farMat.polygonOffsetFactor = 2;
  farMat.polygonOffsetUnits = 4;
  const farMesh = new THREE.Mesh(gridGeometry(terrain.far, terrain, false), farMat);
  farMesh.name = 'terrain-far';
  group.add(farMesh);

  // ------------------------------------------------------- roadside items
  const steel = new THREE.MeshStandardMaterial({ color: '#e9ebe8', metalness: 0.55, roughness: 0.38, side: THREE.DoubleSide });
  const postMat = new THREE.MeshStandardMaterial({ color: '#c9ccc8', metalness: 0.5, roughness: 0.45 });
  const concretePhoto = surfaceImage('concrete_albedo');
  const concreteN = surfaceTexture('concrete_normal', false);
  const concreteMat = new THREE.MeshStandardMaterial({ map: makeConcreteTexture(false, concretePhoto), normalMap: concreteN, roughness: 0.9 });
  const latticeTex = makeConcreteTexture(true, concretePhoto);
  const latticeMat = new THREE.MeshStandardMaterial({ map: latticeTex, normalMap: concreteN, roughness: 0.92, side: THREE.DoubleSide });

  const railGeos: THREE.BufferGeometry[] = [];
  const curbGeos: THREE.BufferGeometry[] = [];
  const wallGeos: THREE.BufferGeometry[] = [];
  const posts: THREE.Matrix4[] = [];
  const reflectors: THREE.Matrix4[] = [];
  const p = new THREE.Vector3();
  const tmpM = new THREE.Matrix4(), tmpQ = new THREE.Quaternion(), tmpS = new THREE.Vector3(1, 1, 1);
  const skipRanges = [...track.zoneRanges('rockshed')];
  const inRockshed = (i: number) => skipRanges.some(([a, b]) => i >= a && i <= b);

  for (const [sideSign, side] of [[1, sides.right], [-1, sides.left]] as const) {
    // contiguous runs of valley / mountain
    let runStart = 0;
    for (let i = 1; i <= track.count; i++) {
      const changed = i === track.count || side.valley[i] !== side.valley[runStart];
      if (!changed) continue;
      const a = runStart, b = i - 1;
      runStart = i;
      if (b - a < 4) continue;
      if (side.valley[a]) {
        railGeos.push(railRibbon(track, a, b, sideSign));
        for (let k = a; k <= b; k += 4) {
          const lat = sideSign * (track.width[k] / 2 + SHOULDER - 0.05);
          track.pointAt(k, lat, p);
          tmpQ.setFromAxisAngle(new THREE.Vector3(0, 1, 0), track.heading[k]);
          tmpM.compose(p.clone().setY(p.y + 0.38), tmpQ, tmpS);
          posts.push(tmpM.clone());
          if (k % 20 === 0) {
            track.pointAt(k, lat - sideSign * 0.12, p);
            tmpM.compose(p.clone().setY(p.y + 0.95), tmpQ, tmpS);
            reflectors.push(tmpM.clone());
          }
        }
      } else {
        curbGeos.push(curbRibbon(track, a, b, sideSign));
        if (!inRockshed(Math.round((a + b) / 2))) {
          const w = retainingWall(track, terrain, a, b, sideSign);
          if (w) wallGeos.push(w);
        }
      }
    }
  }
  if (railGeos.length) {
    const rails = new THREE.Mesh(mergeGeometries(railGeos), steel);
    rails.castShadow = quality.shadows;
    rails.receiveShadow = true;
    group.add(rails);
  }
  if (curbGeos.length) {
    const curbs = new THREE.Mesh(mergeGeometries(curbGeos), concreteMat);
    curbs.receiveShadow = true;
    group.add(curbs);
  }
  if (wallGeos.length) {
    const walls = new THREE.Mesh(mergeGeometries(wallGeos), latticeMat);
    walls.receiveShadow = true;
    group.add(walls);
  }
  const postGeo = new THREE.CylinderGeometry(0.07, 0.07, 1.0, 8);
  const postMesh = new THREE.InstancedMesh(postGeo, postMat, posts.length);
  posts.forEach((m, i) => postMesh.setMatrixAt(i, m));
  postMesh.castShadow = quality.shadows;
  group.add(postMesh);
  const reflMat = new THREE.MeshStandardMaterial({ color: '#ff9a20', emissive: '#ff8a10', emissiveIntensity: 0.4, roughness: 0.3 });
  nightEmissive.push(reflMat);
  const reflMesh = new THREE.InstancedMesh(new THREE.CylinderGeometry(0.05, 0.05, 0.02, 10).rotateX(Math.PI / 2), reflMat, reflectors.length);
  reflectors.forEach((m, i) => reflMesh.setMatrixAt(i, m));
  group.add(reflMesh);

  // ----------------------------------------------------------- structures
  const lamps: Lamp[] = [];
  buildRockshed(track, sides, group, concreteMat, lamps, nightEmissive);
  buildBridge(track, terrain, group, concreteMat, steel, lamps);

  // ------------------------------------------------------------- lamps
  placeLamps(track, sides, lamps);
  buildLampMeshes(track, lamps, group, nightEmissive);
  // baked pools of lamp light on the road and the ground around it
  const roadLightmap = bakeRoadLightmap(track, lamps, road.geometry);
  roadMaterial.lightMap = roadLightmap;
  roadMaterial.lightMapIntensity = 17;
  terrainMat.lightMap = bakeTerrainLightmap(terrain.near, lamps);
  terrainMat.lightMapIntensity = 13;
  const lightmapMats = [roadMaterial, terrainMat];

  // ------------------------------------------------------------- signs
  buildSigns(track, sides, group);
  nightEmissive.push(...nightEmissiveSigns);

  // ------------------------------------------------------------- trees
  const trees = buildTrees(terrain, quality.treeDensity, quality.treeLod);
  group.add(trees);
  group.add(buildClutter(track, terrain, quality.treeDensity, surfaceTexture));
  const turbines = buildTurbines(terrain);
  group.add(turbines.group);

  return {
    group,
    lamps,
    roadMaterial,
    nightEmissive,
    lightmapMats,
    update(time, cameraPos) {
      updateTreeLods(trees, cameraPos);
      for (const r of turbines.rotors) r.rotation.z = time * 0.9 + r.userData.phase;
    },
  };
}

/** Soft pool of light under a lamp head at height h: roughly cos³ falloff. */
function lampPool(dx: number, dy: number, dz: number) {
  const d2 = dx * dx + dy * dy + dz * dz;
  const h = Math.max(dy, 0.5);
  const cos = h / Math.sqrt(d2);
  return (cos * cos * cos * 55) / (d2 + 4);
}

function bakeRoadLightmap(track: Track, lamps: Lamp[], geo: THREE.BufferGeometry) {
  const rows = geo.userData.lightmapRows as number;
  const step = geo.userData.lightmapStep as number;
  const W = 16;
  const data = new Uint8Array(W * rows * 4);
  const sorted = [...lamps].sort((a, b) => a.s - b.s);
  const p = new THREE.Vector3();
  for (let r = 0; r < rows; r++) {
    const i = Math.min(r * step, track.count - 1);
    const hw = track.width[i] / 2 + SHOULDER;
    const near = sorted.filter((l) => Math.abs(l.s - i) < 70);
    for (let c = 0; c < W; c++) {
      const lat = -hw - 0.6 + ((c + 0.5) / W) * 2 * (hw + 0.6);
      track.pointAt(i, lat, p);
      let rr = 0, gg = 0, bb = 0;
      for (const l of near) {
        const k = lampPool(l.position.x - p.x, l.position.y - p.y, l.position.z - p.z);
        rr += l.color.r * k;
        gg += l.color.g * k;
        bb += l.color.b * k;
      }
      const o = (r * W + c) * 4;
      data[o] = Math.min(255, rr * 255);
      data[o + 1] = Math.min(255, gg * 255);
      data[o + 2] = Math.min(255, bb * 255);
      data[o + 3] = 255;
    }
  }
  const tex = new THREE.DataTexture(data, W, rows, THREE.RGBAFormat);
  tex.channel = 1;
  tex.magFilter = THREE.LinearFilter;
  tex.minFilter = THREE.LinearFilter;
  tex.needsUpdate = true;
  return tex;
}

function bakeTerrainLightmap(g: HeightGrid, lamps: Lamp[]) {
  const { nx, nz, cell, x0, z0, heights } = g;
  const data = new Uint8Array(nx * nz * 4);
  const R = 40;
  for (const l of lamps) {
    const ci = Math.round((l.position.x - x0) / cell), cj = Math.round((l.position.z - z0) / cell);
    const span = Math.ceil(R / cell);
    for (let j = Math.max(0, cj - span); j <= Math.min(nz - 1, cj + span); j++)
      for (let i = Math.max(0, ci - span); i <= Math.min(nx - 1, ci + span); i++) {
        const x = x0 + i * cell, z = z0 + j * cell;
        const dy = l.position.y - heights[j * nx + i];
        if (dy < 0) continue;
        const k = lampPool(l.position.x - x, dy, l.position.z - z);
        const o = (j * nx + i) * 4;
        data[o] = Math.min(255, data[o] + l.color.r * k * 255);
        data[o + 1] = Math.min(255, data[o + 1] + l.color.g * k * 255);
        data[o + 2] = Math.min(255, data[o + 2] + l.color.b * k * 255);
      }
  }
  for (let k = 3; k < data.length; k += 4) data[k] = 255;
  const tex = new THREE.DataTexture(data, nx, nz, THREE.RGBAFormat);
  tex.channel = 1;
  tex.magFilter = THREE.LinearFilter;
  tex.minFilter = THREE.LinearFilter;
  tex.needsUpdate = true;
  return tex;
}

// --------------------------------------------------------------------------
function gridGeometry(g: HeightGrid, terrain: TerrainData, near: boolean) {
  const { nx, nz, cell, x0, z0, heights } = g;
  const geo = new THREE.PlaneGeometry((nx - 1) * cell, (nz - 1) * cell, nx - 1, nz - 1);
  geo.rotateX(-Math.PI / 2);
  const pos = geo.getAttribute('position') as THREE.BufferAttribute;
  const uv = geo.getAttribute('uv') as THREE.BufferAttribute;
  const uv1 = new THREE.BufferAttribute(new Float32Array(nx * nz * 2), 2);
  geo.setAttribute('uv1', uv1);
  // PlaneGeometry rows go from +z to -z after rotation; map to grid rows
  for (let j = 0; j < nz; j++) {
    for (let i = 0; i < nx; i++) {
      const vi = j * nx + i;
      const x = x0 + i * cell;
      const z = z0 + j * cell;
      pos.setXYZ(vi, x, heights[j * nx + i], z);
      uv.setXY(vi, x / 7, z / 7);
      uv1.setXY(vi, (i + 0.5) / nx, (j + 0.5) / nz);
    }
  }
  // (rows now run towards +z, which keeps PlaneGeometry's winding facing +y)
  geo.computeVertexNormals();
  const nor = geo.getAttribute('normal') as THREE.BufferAttribute;
  const colors = new Float32Array(nx * nz * 3);
  const c = new THREE.Color();
  const grass = new THREE.Color('#2f4a22'), forest = new THREE.Color('#1c2e17'), rock = new THREE.Color('#4f4c47');
  const soil = new THREE.Color('#3b3a2c'), urban = new THREE.Color('#2b2b29'), sand = new THREE.Color('#8a7d63');
  const seabed = new THREE.Color('#1b2a2c'), cut = new THREE.Color('#5a5850'), gravel = new THREE.Color('#57544e');
  const meadow = new THREE.Color('#5d6b35');
  for (let vi = 0; vi < nx * nz; vi++) {
    const x = pos.getX(vi), y = pos.getY(vi), z = pos.getZ(vi);
    const ny = nor.getY(vi);
    const steep = smoothstep(0.82, 0.55, ny);
    const n = fbm(x / 60, z / 60, 3) * 0.5 + 0.5;
    c.copy(grass).lerp(forest, smoothstep(0.35, 0.7, n));
    c.lerp(soil, smoothstep(0.75, 0.95, fbm(x / 25 + 3, z / 25, 2) * 0.5 + 0.5) * 0.6);
    c.lerp(rock, steep);
    if (near && g.roadDist) {
      const d = g.roadDist[vi];
      c.lerp(cut, smoothstep(30, 8, d) * smoothstep(0.9, 0.6, ny) * 0.8);
      c.lerp(gravel, smoothstep(8.5, 6.5, d) * 0.85);
    }
    const lf = terrain.landform;
    c.lerp(meadow, smoothstep(lf.treeLine - 25, lf.treeLine + 35, y) * (1 - steep) * 0.85);
    c.lerp(urban, cityWeight(lf, x, z) * 0.9);
    if (lf.waterLevel !== null) {
      c.lerp(sand, smoothstep(lf.waterLevel + 2.5, lf.waterLevel + 0.5, y) * 0.8);
      c.lerp(seabed, smoothstep(lf.waterLevel - 0.5, lf.waterLevel - 4, y));
    }
    colors[vi * 3] = c.r;
    colors[vi * 3 + 1] = c.g;
    colors[vi * 3 + 2] = c.b;
  }
  geo.setAttribute('color', new THREE.BufferAttribute(colors, 3));
  return geo;
}

/** Ribbon helper: profile points (lateral offset outward, height) swept along samples a..b. */
function sweep(track: Track, a: number, b: number, sideSign: number, profile: [number, number][], step = 2, vScale = 1) {
  const rows: number[] = [];
  for (let i = a; i <= b; i += step) rows.push(i);
  if (rows[rows.length - 1] !== b) rows.push(b);
  const pos: number[] = [], uv: number[] = [], idx: number[] = [];
  const p = new THREE.Vector3();
  let vAcc = 0;
  rows.forEach((i, r) => {
    const hw = track.width[i] / 2 + SHOULDER;
    for (let k = 0; k < profile.length; k++) {
      const [out, h] = profile[k];
      track.pointAt(i, sideSign * (hw + out), p);
      pos.push(p.x, p.y + h, p.z);
      uv.push(i * vScale, k / (profile.length - 1));
    }
    if (r > 0) {
      const base = r * profile.length, prev = (r - 1) * profile.length;
      for (let k = 0; k < profile.length - 1; k++) {
        const a0 = prev + k, b0 = prev + k + 1, c0 = base + k, d0 = base + k + 1;
        // faces point back towards the road
        if (sideSign > 0) idx.push(a0, b0, c0, b0, d0, c0);
        else idx.push(a0, c0, b0, b0, c0, d0);
      }
    }
    vAcc += 1;
  });
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
  g.setIndex(idx);
  g.computeVertexNormals();
  return g;
}

function railRibbon(track: Track, a: number, b: number, sideSign: number) {
  // W-beam profile (outward offset, height), seen from the road
  return sweep(track, a, b, sideSign, [
    [-0.12, 0.5], [-0.17, 0.56], [-0.11, 0.62], [-0.11, 0.68], [-0.17, 0.74], [-0.12, 0.8],
  ]);
}

function curbRibbon(track: Track, a: number, b: number, sideSign: number) {
  return sweep(track, a, b, sideSign, [[-0.3, -0.05], [-0.3, 0.22], [-0.05, 0.25], [0.25, 0.0], [0.9, -0.3]], 2, 0.25);
}

function retainingWall(track: Track, terrain: TerrainData, a: number, b: number, sideSign: number) {
  // only where the slope above is high: find sub-runs
  const p = new THREE.Vector3();
  let any = false;
  const heights: number[] = [];
  for (let i = a; i <= b; i++) {
    track.pointAt(i, sideSign * (track.width[i] / 2 + SHOULDER + 3), p);
    const cutH = terrain.heightAt(p.x, p.z) - track.pos[i * 3 + 1];
    heights.push(cutH);
    if (cutH > 2.2) any = true;
  }
  if (!any) return null;
  const rows: number[] = [];
  for (let i = a; i <= b; i += 2) rows.push(i);
  const pos: number[] = [], uv: number[] = [], idx: number[] = [];
  rows.forEach((i, r) => {
    const h = clamp(heights[i - a] * 0.9, 0.3, 7.5);
    const hw = track.width[i] / 2 + SHOULDER;
    track.pointAt(i, sideSign * (hw + 0.95), p);
    pos.push(p.x, p.y - 0.4, p.z);
    track.pointAt(i, sideSign * (hw + 0.95 + h * 0.35), p);
    pos.push(p.x, p.y + h, p.z);
    uv.push(i / 5, 0, i / 5, h / 5);
    if (r > 0) {
      const c = r * 2, pr = (r - 1) * 2;
      if (sideSign > 0) idx.push(pr, pr + 1, c, pr + 1, c + 1, c);
      else idx.push(pr, c, pr + 1, pr + 1, c, c + 1);
    }
  });
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
  g.setIndex(idx);
  g.computeVertexNormals();
  return g;
}

function buildRockshed(
  track: Track,
  sides: ReturnType<typeof classifySides>,
  group: THREE.Group,
  concrete: THREE.MeshStandardMaterial,
  lamps: Lamp[],
  nightEmissive: THREE.MeshStandardMaterial[],
) {
  const roofH = 5.6;
  for (const [a0, b0] of track.zoneRanges('rockshed')) {
    const a = a0 + 20, b = b0 - 10;
    const mid = Math.round((a + b) / 2);
    // the mountain side is the non-valley side
    const mountain = sides.right.valley[mid] ? -1 : 1;
    const geos: THREE.BufferGeometry[] = [];
    // roof slab (from mountain wall to the valley columns)
    geos.push(
      sweep(track, a, b, mountain, [
        [1.2, roofH + 0.9], [1.2, roofH], [-(track.width[mid] + SHOULDER * 2 + 0.6), roofH], [-(track.width[mid] + SHOULDER * 2 + 0.6), roofH + 0.9], [1.2, roofH + 0.9],
      ]),
    );
    // back wall on the mountain side
    geos.push(sweep(track, a, b, mountain, [[0.9, -0.3], [0.7, roofH]]));
    const shed = new THREE.Mesh(mergeGeometries(geos), concrete);
    shed.castShadow = true;
    shed.receiveShadow = true;
    group.add(shed);
    // columns on the valley side
    const colGeo = new THREE.BoxGeometry(0.6, roofH, 0.8);
    const cols: THREE.Matrix4[] = [];
    const p = new THREE.Vector3();
    const q = new THREE.Quaternion();
    for (let i = a; i <= b; i += 7) {
      const lat = -mountain * (track.width[i] / 2 + SHOULDER + 0.45);
      track.pointAt(i, lat, p);
      q.setFromAxisAngle(new THREE.Vector3(0, 1, 0), track.heading[i]);
      cols.push(new THREE.Matrix4().compose(p.clone().setY(p.y + roofH / 2), q, new THREE.Vector3(1, 1, 1)));
    }
    const colMesh = new THREE.InstancedMesh(colGeo, concrete, cols.length);
    cols.forEach((m, i) => colMesh.setMatrixAt(i, m));
    colMesh.castShadow = true;
    group.add(colMesh);
    // ceiling lights
    for (let i = a + 6; i <= b; i += 14) {
      track.pointAt(i, 0, p);
      lamps.push({ position: p.clone().setY(p.y + roofH - 0.15), color: SODIUM.clone(), s: i });
    }
    void nightEmissive;
  }
}

function buildBridge(
  track: Track,
  terrain: TerrainData,
  group: THREE.Group,
  concrete: THREE.MeshStandardMaterial,
  steel: THREE.MeshStandardMaterial,
  lamps: Lamp[],
) {
  const p = new THREE.Vector3();
  for (const [a, b] of track.zoneRanges('bridge')) {
    const geos: THREE.BufferGeometry[] = [];
    const railGeos: THREE.BufferGeometry[] = [];
    for (const side of [1, -1]) {
      // girder / deck edge
      geos.push(sweep(track, a, b, side, [[0.0, 0.0], [0.5, 0.25], [0.65, 0.25], [0.65, -1.6], [-1.5, -2.2]]));
      // parapet + railing
      geos.push(sweep(track, a, b, side, [[0.05, 0.0], [0.05, 0.55], [0.35, 0.55]]));
      railGeos.push(sweep(track, a, b, side, [[0.2, 1.05], [0.2, 1.12]]));
      railGeos.push(sweep(track, a, b, side, [[0.2, 0.8], [0.2, 0.86]]));
    }
    // underside slab
    geos.push(sweep(track, a, b, 1, [[-(track.width[a] + SHOULDER * 2 + 1.5), -2.2], [-1.5, -2.2]], 2));
    const deck = new THREE.Mesh(mergeGeometries(geos), concrete);
    deck.castShadow = true;
    deck.receiveShadow = true;
    group.add(deck);
    const rails = new THREE.Mesh(mergeGeometries(railGeos), steel);
    group.add(rails);
    // piers
    const pierMat = concrete;
    for (let i = a + 25; i < b - 10; i += 45) {
      track.pointAt(i, 0, p);
      const ground = terrain.heightAt(p.x, p.z);
      const h = p.y - 2.2 - ground + 4;
      if (h < 4) continue;
      const pier = new THREE.Mesh(new THREE.BoxGeometry(5.5, h, 2.2), pierMat);
      pier.position.set(p.x, ground - 4 + h / 2, p.z);
      pier.rotation.y = track.heading[i];
      pier.castShadow = true;
      group.add(pier);
    }
    // LED lamps alternating sides
    let k = 0;
    for (let i = a + 10; i <= b - 5; i += 32) {
      const side = k++ % 2 ? 1 : -1;
      track.pointAt(i, side * (track.width[i] / 2 + SHOULDER + 0.3), p);
      lamps.push({ position: p.clone(), color: LED.clone(), s: i });
    }
  }
}

function placeLamps(track: Track, sides: ReturnType<typeof classifySides>, lamps: Lamp[]) {
  const p = new THREE.Vector3();
  const occupied = (s: number) => lamps.some((l) => Math.abs(l.s - s) < 14);
  const add = (i: number, side: number, color = SODIUM) => {
    i = clamp(Math.round(i), 0, track.count - 1);
    if (occupied(i)) return;
    track.pointAt(i, side * (track.width[i] / 2 + SHOULDER + 0.6), p);
    lamps.push({ position: p.clone(), color: color.clone(), s: i });
  };
  // summit: modern white LED lamps around the start
  for (let i = 6; i < track.startS + 80; i += 38) add(i, (i / 38) % 2 < 1 ? 1 : -1, LED);
  // finish
  for (let i = track.finishS - 60; i < track.count - 5; i += 30) add(i, 1);
  // corners: outside of every tight corner apex
  for (let i = 20; i < track.count - 20; i++) {
    const k = track.curvature[i];
    if (Math.abs(k) < 1 / 45) continue;
    // local maximum of curvature
    if (Math.abs(k) < Math.abs(track.curvature[i - 1]) || Math.abs(k) < Math.abs(track.curvature[i + 1])) continue;
    const outside = k > 0 ? 1 : -1;
    add(i, outside);
  }
  // sparse lamps elsewhere
  for (let i = 60; i < track.count - 60; i += 140) {
    const side = sides.right.valley[i] ? 1 : -1;
    add(i, side);
  }
}

/** Yaw that turns a lamp post's arm (modelled along local −X) towards the horizontal unit direction `dir`. */
export function lampArmYaw(dir: { x: number; z: number }) {
  // a rotation by θ about +Y maps local (−1, 0, 0) to (−cos θ, 0, sin θ)
  return Math.atan2(dir.z, -dir.x);
}

function buildLampMeshes(track: Track, lamps: Lamp[], group: THREE.Group, nightEmissive: THREE.MeshStandardMaterial[]) {
  const poleMat = new THREE.MeshStandardMaterial({ color: '#7d8287', metalness: 0.7, roughness: 0.4 });
  const sodiumMat = new THREE.MeshStandardMaterial({ color: '#ffd9a0', emissive: SODIUM, emissiveIntensity: 6, roughness: 0.3 });
  const ledMat = new THREE.MeshStandardMaterial({ color: '#ffffff', emissive: LED, emissiveIntensity: 6, roughness: 0.3 });
  nightEmissive.push(sodiumMat, ledMat);
  const pole = new THREE.CylinderGeometry(0.08, 0.12, 7.5, 8).translate(0, 3.75, 0);
  const arm = new THREE.CylinderGeometry(0.05, 0.05, 2.2, 6).rotateZ(Math.PI / 2).translate(-1.0, 7.4, 0);
  const poleGeo = mergeGeometries([pole, arm]);
  const headGeo = new THREE.BoxGeometry(0.75, 0.16, 0.34).translate(-2.0, 7.32, 0);
  const ceilingGeo = new THREE.BoxGeometry(0.9, 0.12, 0.3);
  const poleMats: THREE.Matrix4[] = [], sodium: THREE.Matrix4[] = [], led: THREE.Matrix4[] = [], ceiling: THREE.Matrix4[] = [];
  const q = new THREE.Quaternion(), s1 = new THREE.Vector3(1, 1, 1);
  for (const lamp of lamps) {
    const i = Math.round(lamp.s);
    const inShed = track.zone[i] === 'rockshed' && lamp.position.y - track.pos[i * 3 + 1] > 3;
    if (inShed) {
      q.setFromAxisAngle(new THREE.Vector3(0, 1, 0), track.heading[i]);
      ceiling.push(new THREE.Matrix4().compose(lamp.position, q, s1));
      continue;
    }
    // arm points towards the road centre
    const center = track.getPos(i);
    const dir = new THREE.Vector3().subVectors(center, lamp.position).setY(0).normalize();
    q.setFromAxisAngle(new THREE.Vector3(0, 1, 0), lampArmYaw(dir));
    const m = new THREE.Matrix4().compose(lamp.position, q, s1);
    poleMats.push(m);
    (lamp.color.equals(LED) ? led : sodium).push(m);
    // light source is at the lamp head
    const headOffset = new THREE.Vector3(-2.0, 7.2, 0).applyQuaternion(q);
    lamp.position.add(headOffset);
  }
  const inst = (geo: THREE.BufferGeometry, mat: THREE.Material, list: THREE.Matrix4[], shadow = false) => {
    if (!list.length) return;
    const mesh = new THREE.InstancedMesh(geo, mat, list.length);
    list.forEach((m, i) => mesh.setMatrixAt(i, m));
    mesh.castShadow = shadow;
    group.add(mesh);
  };
  inst(poleGeo, poleMat, poleMats, true);
  inst(headGeo, sodiumMat, sodium);
  inst(headGeo, ledMat, led);
  inst(ceilingGeo, sodiumMat, ceiling);
}

const nightEmissiveSigns: THREE.MeshStandardMaterial[] = [];
const vendingLight = new THREE.PointLight('#e8f4ff', 9, 14, 1.6);

function buildSigns(track: Track, sides: ReturnType<typeof classifySides>, group: THREE.Group) {
  group.add(vendingLight);
  const postMat = new THREE.MeshStandardMaterial({ color: '#9aa0a6', metalness: 0.6, roughness: 0.4 });
  const mats = {
    chevronL: new THREE.MeshStandardMaterial({ map: makeSignTexture('chevronL'), roughness: 0.35, emissive: '#ffffff', emissiveIntensity: 0.06 }),
    chevronR: new THREE.MeshStandardMaterial({ map: makeSignTexture('chevronR'), roughness: 0.35, emissive: '#ffffff', emissiveIntensity: 0.06 }),
    hairpin: new THREE.MeshStandardMaterial({ map: makeSignTexture('hairpin'), roughness: 0.35, transparent: true, alphaTest: 0.5 }),
    speed: new THREE.MeshStandardMaterial({ map: makeSignTexture('speed40'), roughness: 0.35, transparent: true, alphaTest: 0.5 }),
    kanban: new THREE.MeshStandardMaterial({ map: makeSignTexture('kanban'), roughness: 0.5 }),
    start: new THREE.MeshStandardMaterial({ map: makeSignTexture('start'), roughness: 0.5, emissive: '#ffffff', emissiveMap: null, emissiveIntensity: 0.15 }),
    finish: new THREE.MeshStandardMaterial({ map: makeSignTexture('finish'), roughness: 0.5, emissive: '#ffffff', emissiveIntensity: 0.15 }),
  };
  mats.start.emissiveMap = mats.start.map;
  mats.finish.emissiveMap = mats.finish.map;
  const p = new THREE.Vector3();
  const signAt = (i: number, side: number, mat: THREE.Material, size = 0.9, height = 1.6, facing = 0) => {
    i = clamp(Math.round(i), 0, track.count - 1);
    track.pointAt(i, side * (track.width[i] / 2 + SHOULDER + 0.5), p);
    const post = new THREE.Mesh(new THREE.CylinderGeometry(0.04, 0.04, height, 6), postMat);
    post.position.set(p.x, p.y + height / 2, p.z);
    group.add(post);
    const plate = new THREE.Mesh(new THREE.PlaneGeometry(size, size), mat);
    plate.position.set(p.x, p.y + height + size * 0.4, p.z);
    // face oncoming traffic (look back down the road)
    plate.rotation.y = track.heading[i] + Math.PI + facing;
    group.add(plate);
  };

  // one sign group per tight bend: chevrons along the outside, warning and speed signs before the entry
  for (const c of findCorners(track, 40)) {
    if (c.start < 30 || c.end > track.count - 30) continue;
    const outside = c.dir;
    const n = clamp(Math.round((c.end - c.start) / 10), 2, 7);
    for (let m = 0; m < n; m++) signAt(lerp(c.start, c.end, (m + 0.5) / n), outside, c.dir > 0 ? mats.chevronL : mats.chevronR, 0.75, 0.9, outside * 0.5);
    signAt(c.start - 45, -outside, mats.hairpin, 0.8, 1.8);
    if (c.minRadius < 30) signAt(c.start - 65, -outside, mats.speed, 0.7, 1.8);
  }
  // pass name board at the summit
  signAt(18, sides.right.valley[18] ? -1 : 1, mats.kanban, 1.6, 1.4);

  // a row of glowing vending machines on the summit shoulder
  {
    const i = 12;
    const side = sides.right.valley[i] ? -1 : 1;
    const yaw = track.heading[i] + (side > 0 ? -Math.PI / 2 : Math.PI / 2);
    for (let k = 0; k < 3; k++) {
      track.pointAt(i + k * 1.1, side * (track.width[i] / 2 + SHOULDER + 1.6), p);
      const face = new THREE.MeshStandardMaterial({ map: makeVendingTexture(k), emissive: '#ffffff', emissiveIntensity: 1.6, roughness: 0.4 });
      face.emissiveMap = face.map;
      const bodyMat = new THREE.MeshStandardMaterial({ color: ['#c8242a', '#1f5fb5', '#e6e6e6'][k], roughness: 0.5 });
      const vm = new THREE.Mesh(new THREE.BoxGeometry(1.0, 1.85, 0.75), [bodyMat, bodyMat, bodyMat, bodyMat, face, bodyMat]);
      vm.position.set(p.x, p.y + 0.93, p.z);
      vm.rotation.y = yaw;
      vm.castShadow = true;
      group.add(vm);
      nightEmissiveSigns.push(face);
    }
    // the machines light their surroundings
    track.pointAt(i + 1, side * (track.width[i] / 2 + SHOULDER), p);
    vendingLight.position.set(p.x, p.y + 1.4, p.z);
  }

  // start & finish gantries
  for (const [s, mat] of [[track.startS, mats.start], [track.finishS, mats.finish]] as const) {
    const i = Math.round(s);
    const hw = track.width[i] / 2 + SHOULDER + 0.6;
    const yaw = track.heading[i];
    for (const side of [-1, 1]) {
      track.pointAt(i, side * hw, p);
      const leg = new THREE.Mesh(new THREE.BoxGeometry(0.25, 6, 0.25), postMat);
      leg.position.set(p.x, p.y + 3, p.z);
      leg.rotation.y = yaw;
      group.add(leg);
    }
    track.pointAt(i, 0, p);
    const banner = new THREE.Mesh(new THREE.BoxGeometry(hw * 2, 1.2, 0.12), [postMat, postMat, postMat, postMat, mat, mat]);
    banner.position.set(p.x, p.y + 5.6, p.z);
    banner.rotation.y = yaw + Math.PI;
    group.add(banner);
    // painted line across the road
    const lineMat = new THREE.MeshBasicMaterial({ color: '#f0f0f0' });
    const line = new THREE.Mesh(new THREE.PlaneGeometry(hw * 2 - 1.2, 0.4), lineMat);
    line.rotation.x = -Math.PI / 2;
    line.rotation.z = -yaw;
    line.position.set(p.x, p.y + 0.03, p.z);
    group.add(line);
  }

  // curve mirrors (カーブミラー) at hairpins
  const mirrorPole = new THREE.MeshStandardMaterial({ color: '#e46a1c', roughness: 0.5 });
  const mirrorGlass = new THREE.MeshStandardMaterial({ color: '#c8d4dc', metalness: 1, roughness: 0.05, envMapIntensity: 1.5 });
  for (let i = 30; i < track.count - 30; i++) {
    const k = track.curvature[i];
    if (Math.abs(k) < 1 / 30) continue;
    if (Math.abs(k) < Math.abs(track.curvature[i - 1]) || Math.abs(k) < Math.abs(track.curvature[i + 1])) continue;
    const inside = k > 0 ? -1 : 1;
    track.pointAt(i, inside * (track.width[i] / 2 + SHOULDER + 0.8), p);
    const pole = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.05, 2.8, 8), mirrorPole);
    pole.position.set(p.x, p.y + 1.4, p.z);
    group.add(pole);
    const ring = new THREE.Mesh(new THREE.TorusGeometry(0.4, 0.05, 8, 24), mirrorPole);
    ring.position.set(p.x, p.y + 3.1, p.z);
    ring.rotation.y = track.heading[i] + Math.PI / 2;
    group.add(ring);
    const glass = new THREE.Mesh(new THREE.CircleGeometry(0.38, 24), mirrorGlass);
    glass.position.copy(ring.position);
    glass.rotation.y = ring.rotation.y;
    group.add(glass);
  }
}

/** Japanese cedar style conifers, instanced in spatial chunks for culling. */
/** 0..1 how much (x, z) lies inside one of the landform's towns. */
function cityWeight(lf: Landform, x: number, z: number) {
  let w = 0;
  for (const c of lf.cities) {
    const ca = Math.cos(c.angle), sa = Math.sin(c.angle);
    const dx = x - c.x, dz = z - c.z;
    const ax = dx * ca + dz * sa, az = -dx * sa + dz * ca;
    const d = Math.sqrt((ax / c.rx) ** 2 + (az / c.rz) ** 2);
    w = Math.max(w, smoothstep(1.05, 0.8, d));
  }
  return w;
}

function buildTrees(terrain: TerrainData, density: number, lodDistance: number) {
  const group = new THREE.Group();
  group.name = 'trees';
  const geo = treeGeometry();
  const mat = new THREE.MeshStandardMaterial({
    vertexColors: true,
    map: makeFoliageTexture(),
    alphaTest: 0.5,
    side: THREE.DoubleSide,
    roughness: 0.9,
    metalness: 0,
    envMapIntensity: 0.2,
  });
  const r = rng(2024);
  const CHUNK = 320;
  const chunks = new Map<string, THREE.Matrix4[]>();
  const colors = new Map<string, THREE.Color[]>();
  const lf = terrain.landform;
  const add = (x: number, z: number, scale: number) => {
    const y = terrain.heightAt(x, z);
    if (lf.waterLevel !== null && y < lf.waterLevel + 3) return;
    // thinning out towards the tree line, none above it
    if (y > lf.treeLine + noise2(x / 90, z / 90) * 40) return;
    if (lf.relief(x, z) < 0.25 || cityWeight(lf, x, z) > 0.2) return;
    // slope check
    const dx = terrain.heightAt(x + 3, z) - terrain.heightAt(x - 3, z);
    const dz = terrain.heightAt(x, z + 3) - terrain.heightAt(x, z - 3);
    if (Math.hypot(dx, dz) / 6 > 1.25) return;
    const key = `${Math.floor(x / CHUNK)},${Math.floor(z / CHUNK)}`;
    let list = chunks.get(key);
    if (!list) {
      chunks.set(key, (list = []));
      colors.set(key, []);
    }
    const q = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), r() * Math.PI * 2);
    const s = new THREE.Vector3(scale * (0.85 + r() * 0.3), scale, scale * (0.85 + r() * 0.3));
    list.push(new THREE.Matrix4().compose(new THREE.Vector3(x, y - 0.4, z), q, s));
    const tint = new THREE.Color().setHSL(0.24 + r() * 0.08, 0.35 + r() * 0.2, 0.75 + r() * 0.35);
    colors.get(key)!.push(tint);
  };
  // near area
  const g = terrain.near;
  const x1 = g.x0 + (g.nx - 1) * g.cell, z1 = g.z0 + (g.nz - 1) * g.cell;
  const nearCount = Math.round(16000 * density);
  for (let k = 0; k < nearCount; k++) {
    const x = g.x0 + r() * (x1 - g.x0), z = g.z0 + r() * (z1 - g.z0);
    const d = terrain.roadDistAt(x, z);
    const hw = 7;
    if (d < hw + 3.5) continue;
    // clearings via noise; denser near the road for that tunnel-of-trees feeling
    const n = noise2(x / 140, z / 140);
    if (n < -0.25 && d > 40) continue;
    add(x, z, (8 + r() * 9) / 14);
  }
  // far mountains
  const farCount = Math.round(9000 * density);
  for (let k = 0; k < farCount; k++) {
    const x = g.x0 - 2200 + r() * (x1 - g.x0 + 4400), z = g.z0 - 2200 + r() * (z1 - g.z0 + 4400);
    if (x > g.x0 && x < x1 && z > g.z0 && z < z1) continue;
    if (noise2(x / 300, z / 300) < -0.2) continue;
    add(x, z, (12 + r() * 10) / 14);
  }
  // two levels of detail per chunk; Scenery.update() picks one by camera distance
  const farGeo = farTreeGeometry();
  const lods: { near: THREE.InstancedMesh; far: THREE.InstancedMesh; center: THREE.Vector3 }[] = [];
  for (const [key, list] of chunks) {
    const cols = colors.get(key)!;
    const make = (g: THREE.BufferGeometry, shadow: boolean) => {
      const mesh = new THREE.InstancedMesh(g, mat, list.length);
      list.forEach((m, i) => {
        mesh.setMatrixAt(i, m);
        mesh.setColorAt(i, cols[i]);
      });
      mesh.castShadow = shadow;
      mesh.receiveShadow = shadow;
      mesh.computeBoundingSphere();
      group.add(mesh);
      return mesh;
    };
    const near = make(geo, true);
    const far = make(farGeo, false);
    far.visible = false;
    lods.push({ near, far, center: near.boundingSphere!.center.clone() });
  }
  group.userData.lods = lods;
  group.userData.lodDistance = lodDistance;
  return group;
}

/** Switch tree chunks between the detailed and the impostor mesh. */
export function updateTreeLods(trees: THREE.Object3D, camera: THREE.Vector3) {
  const lods = trees.userData.lods as { near: THREE.InstancedMesh; far: THREE.InstancedMesh; center: THREE.Vector3 }[];
  for (const l of lods) {
    // hysteresis: a chunk right at the switch distance must not flap between meshes every frame
    const d = l.center.distanceTo(camera);
    const lod = trees.userData.lodDistance as number;
    const near = l.near.visible ? d < lod + 60 : d < lod;
    l.near.visible = near;
    l.far.visible = !near;
  }
}

/** Builds an indexed mesh from vertex streams (position, soft "volume" normal, colour, uv). */
class MeshBuilder {
  pos: number[] = [];
  nrm: number[] = [];
  col: number[] = [];
  uv: number[] = [];
  idx: number[] = [];
  vert(x: number, y: number, z: number, nx: number, ny: number, nz: number, c: THREE.Color, k: number, u: number, v: number) {
    const l = Math.hypot(nx, ny, nz) || 1;
    this.pos.push(x, y, z);
    this.nrm.push(nx / l, ny / l, nz / l);
    this.col.push(c.r * k, c.g * k, c.b * k);
    this.uv.push(u, v);
    return this.pos.length / 3 - 1;
  }
  build() {
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(this.pos, 3));
    g.setAttribute('normal', new THREE.Float32BufferAttribute(this.nrm, 3));
    g.setAttribute('color', new THREE.Float32BufferAttribute(this.col, 3));
    g.setAttribute('uv', new THREE.Float32BufferAttribute(this.uv, 2));
    g.setIndex(this.idx);
    return g;
  }
}

/**
 * Japanese cedar: a straight trunk and drooping, ragged tiers that shrink towards the top. Normals
 * point away from the crown axis so the foliage shades like a volume instead of flat facets; the
 * inside of each tier and the lower tiers are darker. Foliage uses the alpha-tested branch texture.
 */
function treeGeometry() {
  const b = new MeshBuilder();
  const r = rng(7);
  const bark = new THREE.Color('#3b2b1f');
  const leaf = new THREE.Color(1, 1, 1);
  const TS = 6;
  const trunk: number[][] = [];
  for (let i = 0; i <= TS; i++) {
    const a = (i / TS) * Math.PI * 2, cx = Math.cos(a), cz = Math.sin(a);
    trunk.push([b.vert(cx * 0.32, -0.6, cz * 0.32, cx, 0, cz, bark, 0.8, 0.95, 0.5), b.vert(cx * 0.1, 11, cz * 0.1, cx, 0, cz, bark, 1, 0.95, 0.5)]);
  }
  for (let i = 0; i < TS; i++) b.idx.push(trunk[i][0], trunk[i][1], trunk[i + 1][0], trunk[i][1], trunk[i + 1][1], trunk[i + 1][0]);
  const N = 7, M = 11;
  for (let l = 0; l < N; l++) {
    const t = l / (N - 1);
    const R = lerp(2.6, 0.55, Math.pow(t, 0.9));
    const tierH = lerp(3.0, 1.5, t);
    const apexY = lerp(2.6 + tierH, 14.4, t);
    const ringY = apexY - tierH;
    const shade = lerp(0.62, 1.12, t);
    const phase = r() * Math.PI * 2;
    const rad: number[] = [], droop: number[] = [];
    for (let i = 0; i < M; i++) {
      rad.push(R * (i % 2 === 0 ? 1 : 0.76) * (0.82 + r() * 0.36));
      droop.push(tierH * (0.2 + r() * 0.3));
    }
    const apex = b.vert(0, apexY, 0, 0, 1, 0, leaf, shade * 0.45, 0.4375, 0);
    const mids: number[] = [], tips: number[] = [];
    for (let i = 0; i <= M; i++) {
      const ii = i % M;
      const a = phase + (i / M) * Math.PI * 2, cx = Math.cos(a), cz = Math.sin(a);
      const u = (i / M) * 0.85;
      mids.push(b.vert(cx * rad[ii] * 0.55, lerp(apexY, ringY, 0.45), cz * rad[ii] * 0.55, cx, 0.7, cz, leaf, shade * 0.75, u, 0.5));
      tips.push(b.vert(cx * rad[ii], ringY - droop[ii], cz * rad[ii], cx, 0.3, cz, leaf, shade * 1.1, u, 1));
    }
    for (let i = 0; i < M; i++) {
      b.idx.push(apex, mids[i + 1], mids[i]);
      b.idx.push(mids[i], mids[i + 1], tips[i + 1], mids[i], tips[i + 1], tips[i]);
    }
  }
  return b.build();
}

/** Distant cedar: two ragged tiers, untextured and dark, so far slopes read as forest, not specks. */
function farTreeGeometry() {
  const b = new MeshBuilder();
  const green = new THREE.Color('#1a2c16');
  const M = 8;
  for (const [y0, y1, R, k] of [[2.5, 9.5, 2.4, 0.75], [7.5, 14.6, 1.5, 0.95]] as const) {
    const apex = b.vert(0, y1, 0, 0, 1, 0, green, k * 0.8, 0.95, 0.5);
    const ring: number[] = [];
    for (let i = 0; i <= M; i++) {
      const a = (i / M) * Math.PI * 2, cx = Math.cos(a), cz = Math.sin(a);
      const rr = R * (i % 2 === 0 ? 1 : 0.8);
      ring.push(b.vert(cx * rr, y0, cz * rr, cx, 0.45, cz, green, k, 0.95, 0.5));
    }
    for (let i = 0; i < M; i++) b.idx.push(apex, ring[i + 1], ring[i]);
  }
  return b.build();
}

/**
 * Smooth, noise-displaced lump for rocks (flattened, planar-mapped for the scanned texture) and
 * bushes (rounder, with soft outward normals and darker undersides).
 */
function lumpGeometry(seed: number, amount: number, kind: 'rock' | 'bush') {
  let g: THREE.BufferGeometry = new THREE.IcosahedronGeometry(1, 1);
  g.deleteAttribute('normal');
  g.deleteAttribute('uv');
  g = mergeVertices(g);
  const pos = g.getAttribute('position') as THREE.BufferAttribute;
  const uv: number[] = [], col: number[] = [];
  for (let i = 0; i < pos.count; i++) {
    const x = pos.getX(i), y = pos.getY(i), z = pos.getZ(i);
    const n = fbm(x * 1.3 + seed, z * 1.3 - y * 0.9, 3) + noise2(x * 3.1 - y * 2.3, z * 3.1 + seed) * 0.35;
    let k = 1 + n * amount;
    if (kind === 'rock') k *= 1 - 0.18 * Math.max(0, y); // flatter tops
    const yy = kind === 'bush' ? Math.max(-0.25, y) : y;
    pos.setXYZ(i, x * k, yy * k * (kind === 'rock' ? 0.7 : 0.8), z * k);
    uv.push((x + z * 0.6) * 0.8, (y + x * 0.3) * 0.8);
    const ao = 0.55 + 0.45 * smoothstep(-0.6, 0.7, y);
    col.push(ao, ao, ao);
  }
  g.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
  g.setAttribute('color', new THREE.Float32BufferAttribute(col, 3));
  g.computeVertexNormals();
  if (kind === 'bush') {
    // blend towards the outward direction for a soft, foliage-like volume
    const nrm = g.getAttribute('normal') as THREE.BufferAttribute;
    const v = new THREE.Vector3(), o = new THREE.Vector3();
    for (let i = 0; i < nrm.count; i++) {
      o.set(pos.getX(i), pos.getY(i) * 0.6 + 0.2, pos.getZ(i)).normalize();
      v.set(nrm.getX(i), nrm.getY(i), nrm.getZ(i)).lerp(o, 0.6).normalize();
      nrm.setXYZ(i, v.x, v.y, v.z);
    }
  }
  return g;
}

/** Bushes and rocks scattered along the road for a less sterile roadside. */
function buildClutter(
  track: Track,
  terrain: TerrainData,
  density: number,
  surfaceTexture: (n: SurfaceName, srgb: boolean) => THREE.Texture | null,
) {
  const group = new THREE.Group();
  group.name = 'clutter';
  const r = rng(77);
  const bushGeo = lumpGeometry(11, 0.32, 'bush');
  const rockGeo = lumpGeometry(5, 0.22, 'rock');
  const bushMat = new THREE.MeshStandardMaterial({ color: '#2c4422', vertexColors: true, roughness: 0.95, envMapIntensity: 0.2 });
  const rockAlbedo = surfaceTexture('rock_albedo', true);
  const rockMat = new THREE.MeshStandardMaterial({
    vertexColors: true,
    color: rockAlbedo ? '#ffffff' : '#6b665e',
    map: rockAlbedo,
    normalMap: surfaceTexture('rock_normal', false),
    roughness: 0.88,
    envMapIntensity: 0.4,
  });
  const bushes: THREE.Matrix4[] = [], rocks: THREE.Matrix4[] = [];
  const UP = new THREE.Vector3(0, 1, 0), normal = new THREE.Vector3(), tilt = new THREE.Quaternion();
  const bushCol: THREE.Color[] = [], rockCol: THREE.Color[] = [];
  const p = new THREE.Vector3();
  const q = new THREE.Quaternion();
  const count = Math.round(9000 * density);
  for (let k = 0; k < count; k++) {
    const s = r() * track.length;
    const i = Math.round(s);
    const side = r() < 0.5 ? -1 : 1;
    const off = track.width[i] / 2 + SHOULDER + 1.4 + r() ** 2 * 22;
    // keep the summit start area (garage, grid) tidy
    if (s < track.startS + 45 && off < 16) continue;
    track.pointAt(s, side * off, p);
    const y = terrain.heightAt(p.x, p.z);
    const gx = (terrain.heightAt(p.x + 1.5, p.z) - terrain.heightAt(p.x - 1.5, p.z)) / 3;
    const gz = (terrain.heightAt(p.x, p.z + 1.5) - terrain.heightAt(p.x, p.z - 1.5)) / 3;
    const steep = Math.hypot(gx, gz);
    if (Math.abs(y - p.y) > 14) continue;
    q.setFromAxisAngle(UP, r() * 6.28);
    if (steep > 0.9 || r() < 0.18) {
      // boulders lie in the slope (tilted to the ground normal) and are half buried, so on steep
      // cuttings they read as rock outcrops rather than flat discs sticking out of the hill
      const sc = 0.3 + r() * 0.9;
      q.premultiply(tilt.setFromUnitVectors(UP, normal.set(-gx, 1, -gz).normalize()));
      rocks.push(new THREE.Matrix4().compose(new THREE.Vector3(p.x, y - sc * (0.25 + Math.min(steep, 1.5) * 0.2), p.z), q, new THREE.Vector3(sc * (1 + r() * 0.8), sc * (0.7 + r() * 0.3), sc * (1 + r() * 0.5))));
      rockCol.push(new THREE.Color().setHSL(0.08 + r() * 0.05, 0.05 + r() * 0.08, 0.6 + r() * 0.3));
    } else {
      const sc = 0.5 + r() * 1.1;
      bushes.push(new THREE.Matrix4().compose(new THREE.Vector3(p.x, y - steep * sc * 0.35, p.z), q, new THREE.Vector3(sc * (0.8 + r() * 0.6), sc, sc)));
      bushCol.push(new THREE.Color().setHSL(0.22 + r() * 0.1, 0.35 + r() * 0.2, 0.7 + r() * 0.5));
    }
  }
  const bushMesh = new THREE.InstancedMesh(bushGeo, bushMat, bushes.length);
  bushes.forEach((m, i) => {
    bushMesh.setMatrixAt(i, m);
    bushMesh.setColorAt(i, bushCol[i]);
  });
  bushMesh.receiveShadow = true;
  bushMesh.computeBoundingSphere();
  const rockMesh = new THREE.InstancedMesh(rockGeo, rockMat, rocks.length);
  rocks.forEach((m, i) => {
    rockMesh.setMatrixAt(i, m);
    rockMesh.setColorAt(i, rockCol[i]);
  });
  rockMesh.castShadow = true;
  rockMesh.receiveShadow = true;
  rockMesh.computeBoundingSphere();
  group.add(bushMesh, rockMesh);
  return group;
}

/** Wind turbines on the skyline ridge (rotors animate in Scenery.update). */
function buildTurbines(terrain: TerrainData) {
  const group = new THREE.Group();
  group.name = 'turbines';
  const rotors: THREE.Object3D[] = [];
  const mat = new THREE.MeshStandardMaterial({ color: '#d9dde2', roughness: 0.55, metalness: 0.2 });
  const towerGeo = new THREE.CylinderGeometry(1.1, 2.0, 60, 12).translate(0, 30, 0);
  const nacelleGeo = new THREE.BoxGeometry(2.4, 2.4, 7).translate(0, 0, -1.5);
  const bladeGeo = new THREE.BoxGeometry(0.8, 26, 0.25).translate(0, 13.5, 0);
  for (const [x, z] of terrain.landform.features.turbines ?? []) {
    if (terrain.roadDistAt(x, z) < 45) continue;
    const y = terrain.heightAt(x, z) - 1;
    const t = new THREE.Group();
    t.position.set(x, y, z);
    t.rotation.y = 0.6;
    const tower = new THREE.Mesh(towerGeo, mat);
    tower.castShadow = true;
    t.add(tower);
    const nacelle = new THREE.Mesh(nacelleGeo, mat);
    nacelle.position.y = 61;
    t.add(nacelle);
    const rotor = new THREE.Group();
    rotor.position.set(0, 61, 2.4);
    rotor.userData.phase = Math.random() * 6;
    for (let k = 0; k < 3; k++) {
      const b = new THREE.Mesh(bladeGeo, mat);
      b.rotation.z = (k / 3) * Math.PI * 2;
      rotor.add(b);
    }
    t.add(rotor);
    rotors.push(rotor);
    group.add(t);
  }
  return { group, rotors };
}
