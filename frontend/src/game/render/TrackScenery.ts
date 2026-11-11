import * as THREE from 'three';
import { mergeGeometries, mergeVertices } from 'three/examples/jsm/utils/BufferGeometryUtils.js';
import { Track } from '../track/Track';
import type { TerrainData, HeightGrid } from '../track/terrain';
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
import { layersLoaded, surfaceImage as photoImage, surfaceTexture as photoTexture, type SurfaceName } from './surfaceTextures';
import { groundMaterial, type GroundDetail, type GroundLook } from './terrainMaterial';
import { roadMaterial as roadSurface } from './roadMaterial';
import { findCorners } from '../track/corners';
import { placeProp, prop, type PropModel } from './props';
import type { CourseStyle } from '../track/courses';
import type { Landform } from '../track/landforms';
import { ChunkedLods, cutout } from './instancing';
import { Forest, vegetationFrame, type VegetationQuality } from './vegetation';
import { cityWeight, COVER_SETS, loadedSpecies, plantCover, plantTrees, TREE_SETS, UNDER_SETS } from './vegetationPlanting';
import { buildAutobahnScenery } from './autobahnScenery';
import { layBridges, layRoadside, layRocksheds, Roadside } from './roadside';

export interface Lamp {
  position: THREE.Vector3;
  color: THREE.Color;
  /** track distance, for lightmaps and pooling */
  s: number;
  /** where the post's arm points (default: the road's centreline at `s`) */
  aim?: THREE.Vector3;
}

export interface SceneryResult {
  group: THREE.Group;
  lamps: Lamp[];
  roadMaterial: THREE.MeshStandardMaterial;
  /** emissive materials that should brighten at night */
  nightEmissive: THREE.MeshStandardMaterial[];
  /** materials carrying the baked lamp lightmap (scaled with lamp state) */
  lightmapMats: THREE.MeshStandardMaterial[];
  /**
   * roofs over the road (the rock sheds), for the rain to stop under: quads of 9 floats each, corners a b c d in
   * order (x, z pairs) and the roof slab's top height
   */
  covers: Float32Array;
  update(time: number, cameraPos: THREE.Vector3): void;
}

export const SODIUM = new THREE.Color('#ffa850');
export const LED = new THREE.Color('#e4ecff');

export interface SceneryQuality {
  treeDensity: number;
  shadows: boolean;
  photoTextures: boolean;
  treeLod: number;
  /** the Blender-made vegetation (render/vegetation.ts); without it, or as `legacy`, the old procedural cedar and lumps */
  vegetation?: VegetationQuality;
  /** 0 (default): the plain materials and shapes; 1–3: the layered ground, road and roadside (store/settings.ts) */
  surfaceDetail?: number;
  /** 'autobahn': the motorway's own scenery (render/autobahnScenery.ts) instead of the mountain road's */
  style?: CourseStyle;
}

/** Builds every static mesh along and around the course. */
export function buildScenery(track: Track, terrain: TerrainData, quality: SceneryQuality): SceneryResult {
  if (quality.style === 'autobahn') return buildAutobahnScenery(track, terrain, quality);
  const group = new THREE.Group();
  group.name = 'scenery';
  const sides = classifySides(track, terrain);
  const nightEmissive: THREE.MeshStandardMaterial[] = [];
  const surfaceImage = (n: SurfaceName) => (quality.photoTextures ? photoImage(n) : null);
  const surfaceTexture = (n: SurfaceName, srgb: boolean) => (quality.photoTextures ? photoTexture(n, srgb) : null);

  // the layered materials and the modelled roadside, or (the low setting, or a texture that did not load) the plain ones
  const detail = surfaceDetailOf(quality);

  // ------------------------------------------------------------------ road
  const roadMaterial = detail ? (roadSurface({ markings: 'touge' }, detail) as unknown as THREE.MeshStandardMaterial) : plainRoadMaterial(surfaceImage, surfaceTexture);
  const road = new THREE.Mesh(buildRoadGeometry(track), roadMaterial);
  road.receiveShadow = true;
  road.name = 'road';
  group.add(road);

  // --------------------------------------------------------------- terrain
  const lf = terrain.landform;
  const look: GroundLook = { grass: lf.treeLine < 1000 ? 'grass' : 'moss', waterLevel: lf.waterLevel };
  const terrainMat = detail ? (groundMaterial(look, detail) as unknown as THREE.MeshStandardMaterial) : plainTerrainMaterial(surfaceTexture);
  const nearMesh = new THREE.Mesh(gridGeometry(terrain.near, terrain, true, !!detail), terrainMat);
  nearMesh.receiveShadow = true;
  nearMesh.name = 'terrain-near';
  group.add(nearMesh);
  const farMat = detail ? (groundMaterial(look, detail, true) as unknown as THREE.MeshStandardMaterial) : terrainMat.clone();
  if (!detail) farMat.normalMap = null;
  // where the two grids overlap at the near grid's border they are nearly coplanar: push the coarse
  // mesh back in depth so the near mesh always wins instead of z-fighting (flickering hillsides)
  farMat.polygonOffset = true;
  farMat.polygonOffsetFactor = 2;
  farMat.polygonOffsetUnits = 4;
  const farMesh = new THREE.Mesh(gridGeometry(terrain.far, terrain, false, !!detail), farMat);
  farMesh.name = 'terrain-far';
  group.add(farMesh);

  const lamps: Lamp[] = [];
  const covers: number[] = [];
  let roadsideUpdate: ((camera: THREE.Vector3) => void) | null = null;
  if (detail) {
    // ----------------------------------- roadside and structures, modelled
    const rs = new Roadside(track, terrain, { detail, shadows: quality.shadows, ground: terrainMat, cover: (x, y, z) => groundCover(lf, x, y, z) });
    layRoadside(rs, sides);
    for (const l of layRocksheds(rs, sides, covers)) lamps.push({ position: l.position, color: SODIUM.clone(), s: l.s });
    for (const l of layBridges(rs, terrain)) lamps.push({ position: l.position, color: LED.clone(), s: l.s });
    const built = rs.finish(group);
    nightEmissive.push(...built.nightEmissive);
    roadsideUpdate = built.update;
  } else plainRoadside(track, terrain, sides, group, quality, surfaceImage, surfaceTexture, nightEmissive, lamps, covers);

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
  const keepOut = buildLandmarks(track, terrain, sides, group, lamps);

  // ------------------------------------------------------------- trees
  const trees = buildTrees(terrain, quality.treeDensity, quality.treeLod, { vegetation: quality.vegetation });
  group.add(trees);
  const clutter = buildClutter(track, terrain, quality.treeDensity, surfaceTexture, keepOut, { vegetation: quality.vegetation });
  group.add(clutter);
  const turbines = buildTurbines(terrain);
  group.add(turbines.group);

  return {
    group,
    lamps,
    roadMaterial,
    nightEmissive,
    lightmapMats,
    covers: new Float32Array(covers),
    update(time, cameraPos) {
      vegetationFrame(time, cameraPos);
      updateTreeLods(trees, cameraPos);
      updateTreeLods(clutter, cameraPos);
      turbines.update(time);
      roadsideUpdate?.(cameraPos);
    },
  };
}

/** the low setting's roadside: ribbons for the rails, kerbs and walls, the rock sheds and bridges as plain slabs */
function plainRoadside(
  track: Track,
  terrain: TerrainData,
  sides: ReturnType<typeof classifySides>,
  group: THREE.Group,
  quality: SceneryQuality,
  surfaceImage: (n: SurfaceName) => HTMLImageElement | null,
  surfaceTexture: (n: SurfaceName, srgb: boolean) => THREE.Texture | null,
  nightEmissive: THREE.MeshStandardMaterial[],
  lamps: Lamp[],
  covers: number[],
) {
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

  buildRockshed(track, sides, group, concreteMat, lamps, nightEmissive, covers);
  buildBridge(track, terrain, group, concreteMat, steel, lamps);
}

/** the low setting's road: the lines painted into one texture over the asphalt photo (or noise) */
function plainRoadMaterial(surfaceImage: (n: SurfaceName) => HTMLImageElement | null, surfaceTexture: (n: SurfaceName, srgb: boolean) => THREE.Texture | null) {
  // scanned asphalt when available (normal/roughness at full resolution, 2.7 m tiles)
  const roadTex = makeRoadTexture(surfaceImage('asphalt_albedo'));
  roadTex.repeat.set(1, 1 / 8);
  const photoN = surfaceTexture('asphalt_normal', false);
  const asphaltN = photoN ?? makeAsphaltNormal();
  if (photoN) asphaltN.repeat.set(4, 3 / 8);
  else asphaltN.repeat.set(3, 1 / 2.4);
  const asphaltR = surfaceTexture('asphalt_rough', false);
  asphaltR?.repeat.copy(asphaltN.repeat);
  return new THREE.MeshStandardMaterial({
    map: roadTex,
    normalMap: asphaltN,
    normalScale: new THREE.Vector2(photoN ? 1 : 0.6, photoN ? 1 : 0.6),
    roughnessMap: asphaltR,
    roughness: asphaltR ? 1 : 0.78,
    metalness: 0.0,
    envMapIntensity: 0.6,
  });
}

/** the low setting's ground: vertex colours times one detail texture */
export function plainTerrainMaterial(surfaceTexture: (n: SurfaceName, srgb: boolean) => THREE.Texture | null) {
  return new THREE.MeshStandardMaterial({
    vertexColors: true,
    map: surfaceTexture('ground_detail', true) ?? makeGroundDetail(),
    normalMap: surfaceTexture('ground_normal', false) ?? makeGroundNormal(),
    normalScale: new THREE.Vector2(0.8, 0.8),
    roughness: 0.95,
    metalness: 0,
    envMapIntensity: 0.3,
  });
}

/** 1–3 when the layered materials are asked for and their textures are there, else 0 */
export function surfaceDetailOf(quality: SceneryQuality): 0 | GroundDetail {
  const d = Math.round(quality.surfaceDetail ?? 0);
  return d > 0 && layersLoaded() ? (Math.min(d, 3) as GroundDetail) : 0;
}

/** Soft pool of light under a lamp head at height h: roughly cos³ falloff. */
export function lampPool(dx: number, dy: number, dz: number) {
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

export function bakeTerrainLightmap(g: HeightGrid, lamps: Lamp[]) {
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

/** what covers the ground at a place: [town 0..1, forest 0..1] (the `surf` attribute's z and w) */
export function groundCover(lf: Landform, x: number, y: number, z: number): [number, number] {
  const urban = cityWeight(lf, x, z);
  let forest = smoothstep(0.15, 0.35, lf.relief(x, z)) * smoothstep(lf.treeLine + 35, lf.treeLine - 25, y) * (1 - urban);
  if (lf.waterLevel !== null) forest *= smoothstep(lf.waterLevel + 1.5, lf.waterLevel + 4, y);
  return [urban, forest];
}

// --------------------------------------------------------------------------
/**
 * A height grid's mesh. `layered`: for render/terrainMaterial.ts, which reads what the ground is from `surf` (four
 * bytes per vertex, see there) instead of vertex colours.
 */
export function gridGeometry(g: HeightGrid, terrain: TerrainData, near: boolean, layered = false) {
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
  if (layered) {
    const lf = terrain.landform;
    const surf = new Uint8Array(nx * nz * 4);
    const h = (i: number, j: number) => heights[clamp(j, 0, nz - 1) * nx + clamp(i, 0, nx - 1)];
    for (let j = 0; j < nz; j++)
      for (let i = 0; i < nx; i++) {
        const vi = j * nx + i;
        const x = x0 + i * cell, z = z0 + j * cell, y = heights[vi];
        const beyond = near && g.edgeDist ? g.edgeDist[vi] : 1e6;
        // convex (a spur, a bank's shoulder) above 0.5, hollow below: the land's second derivative, per metre
        const lap = (h(i - 1, j) + h(i + 1, j) + h(i, j - 1) + h(i, j + 1) - 4 * y) / (cell * cell);
        const [urban, forest] = groundCover(lf, x, y, z);
        surf[vi * 4] = clamp((beyond + 2) / 34, 0, 1) * 255;
        surf[vi * 4 + 1] = clamp(0.5 - lap * 7, 0, 1) * 255;
        surf[vi * 4 + 2] = urban * 255;
        surf[vi * 4 + 3] = forest * 255;
      }
    geo.setAttribute('surf', new THREE.BufferAttribute(surf, 4, true));
    geo.deleteAttribute('uv');
    return geo;
  }
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
  covers: number[],
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
    // the roof's footprint (the slab's two edges, as swept above) for the rain: quads every 6 m
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

export function buildLampMeshes(track: Track, lamps: Lamp[], group: THREE.Group, nightEmissive: THREE.MeshStandardMaterial[]) {
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
  const model = prop('streetLight');
  // where the light hangs: under the lamp head at the end of the arm
  const head = model ? lampHead(model) : new THREE.Vector3(-2.0, 7.2, 0);
  for (const lamp of lamps) {
    const i = Math.round(lamp.s);
    const inShed = track.zone[i] === 'rockshed' && lamp.position.y - track.pos[i * 3 + 1] > 3;
    if (inShed) {
      q.setFromAxisAngle(new THREE.Vector3(0, 1, 0), track.heading[i]);
      ceiling.push(new THREE.Matrix4().compose(lamp.position, q, s1));
      continue;
    }
    // arm points towards the road centre
    const center = lamp.aim ?? track.getPos(i);
    const dir = new THREE.Vector3().subVectors(center, lamp.position).setY(0).normalize();
    q.setFromAxisAngle(new THREE.Vector3(0, 1, 0), lampArmYaw(dir));
    const m = new THREE.Matrix4().compose(lamp.position, q, s1);
    poleMats.push(m);
    (lamp.color.equals(LED) ? led : sodium).push(m);
    // light source is at the lamp head
    lamp.position.add(head.clone().applyQuaternion(q));
  }
  const inst = (geo: THREE.BufferGeometry, mat: THREE.Material, list: THREE.Matrix4[], shadow = false) => {
    if (!list.length) return;
    const mesh = new THREE.InstancedMesh(geo, mat, list.length);
    list.forEach((m, i) => mesh.setMatrixAt(i, m));
    mesh.castShadow = shadow;
    group.add(mesh);
  };
  if (model) {
    // one copy of the model's material per lamp colour: its emissive map (the lamp glass) glows in that colour
    const tint = (color: THREE.Color) => (m: THREE.MeshStandardMaterial) => {
      if (!m.emissiveMap) return m;
      const c = m.clone();
      c.emissive.copy(color);
      c.emissiveIntensity = 6;
      nightEmissive.push(c);
      return c;
    };
    for (const [list, color] of [[sodium, SODIUM], [led, LED]] as const)
      if (list.length) group.add(placeProp(model, list, { castShadow: true, material: tint(color), name: 'street-lights' }).group);
  } else {
    inst(poleGeo, poleMat, poleMats, true);
    inst(headGeo, sodiumMat, sodium);
    inst(headGeo, ledMat, led);
  }
  inst(ceilingGeo, sodiumMat, ceiling);
}

/** Light position of the street light model: two thirds out along its arm (local −X), just under the top. */
function lampHead(model: PropModel) {
  const box = new THREE.Box3();
  for (const p of model.pieces) {
    p.geometry.computeBoundingBox();
    box.union(p.geometry.boundingBox!);
  }
  return new THREE.Vector3(box.min.x * 0.67, box.max.y - 0.25, 0);
}

/**
 * Curve mirrors (カーブミラー): one on the inside of each bend tighter than 30 m, at its sharpest point, the glass
 * (+Z of the model) turned to the road. (A per-sample curvature peak test put one every metre along
 * constant-radius arcs: ~200 per course, a fence of orange poles and 600 draw calls.)
 */
export function curveMirrorSpots(track: Track) {
  return findCorners(track, 30)
    .filter((c) => c.apex >= 30 && c.apex < track.count - 30)
    .map((c) => {
      const lateral = -c.dir * (track.width[c.apex] / 2 + SHOULDER + 0.8);
      // +lateral is the road's right: a mirror there looks left (heading + π/2), one on the left looks right
      // (every mirror used to get heading + π/2, so those on the left turned their back to the road)
      return { i: c.apex, lateral, yaw: track.heading[c.apex] + (lateral > 0 ? Math.PI / 2 : -Math.PI / 2) };
    });
}

const nightEmissiveSigns: THREE.MeshStandardMaterial[] = [];
/** where the vending machine's glow belongs on the course built last (the light itself: `LightRig.vending`); `on` = there is one */
export const vendingSpot = { position: new THREE.Vector3(), on: false };

function buildSigns(track: Track, sides: ReturnType<typeof classifySides>, group: THREE.Group) {
  // module-level list: only this course's materials (it used to keep every earlier course's)
  nightEmissiveSigns.length = 0;
  vendingSpot.on = false;
  const postMat = new THREE.MeshStandardMaterial({ color: '#9aa0a6', metalness: 0.6, roughness: 0.4 });
  const mats = {
    chevronL: new THREE.MeshStandardMaterial({ map: makeSignTexture('chevronL'), roughness: 0.35, emissive: '#ffffff', emissiveIntensity: 0.06 }),
    chevronR: new THREE.MeshStandardMaterial({ map: makeSignTexture('chevronR'), roughness: 0.35, emissive: '#ffffff', emissiveIntensity: 0.06 }),
    hairpin: cutout(new THREE.MeshStandardMaterial({ map: makeSignTexture('hairpin'), roughness: 0.35, transparent: true, alphaTest: 0.5 })),
    speed: cutout(new THREE.MeshStandardMaterial({ map: makeSignTexture('speed40'), roughness: 0.35, transparent: true, alphaTest: 0.5 })),
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
    // fronts (+Z) towards the road (they used to face the hillside)
    const yaw = track.heading[i] + (side > 0 ? Math.PI / 2 : -Math.PI / 2);
    const model = prop('vending');
    const machines: THREE.Matrix4[] = [];
    for (let k = 0; k < 3; k++) {
      track.pointAt(i + k * 1.3, side * (track.width[i] / 2 + SHOULDER + 1.6), p);
      if (model) {
        machines.push(new THREE.Matrix4().compose(p, new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), yaw), new THREE.Vector3(1, 1, 1)));
        continue;
      }
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
    if (model) {
      // the front glows through its emissive map (brighter at night)
      const glow = (m: THREE.MeshStandardMaterial) => {
        const c = m.clone();
        if (c.emissiveMap && c.emissive.getHex() === 0) c.emissive.set('#ffffff');
        c.emissiveIntensity = 1.3;
        nightEmissiveSigns.push(c);
        return c;
      };
      group.add(placeProp(model, machines, { castShadow: true, material: glow, name: 'vending-machines' }).group);
    }
    // the machines light their surroundings
    track.pointAt(i + 1, side * (track.width[i] / 2 + SHOULDER), p);
    vendingSpot.position.set(p.x, p.y + 1.4, p.z);
    vendingSpot.on = true;
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
    // traffic cones along both shoulders
    const coneModel = prop('cone');
    if (coneModel) {
      const cones: THREE.Matrix4[] = [];
      for (const side of [-1, 1])
        for (const ds of [-7, -4.5, 4.5, 7]) {
          const k = clamp(Math.round(s + ds), 0, track.count - 1);
          track.pointAt(k, side * (track.width[k] / 2 + SHOULDER * 0.55), p);
          cones.push(new THREE.Matrix4().compose(p, new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), ds * 1.7), new THREE.Vector3(1, 1, 1)));
        }
      group.add(placeProp(coneModel, cones, { castShadow: true, name: 'cones' }).group);
    }
  }

  // curve mirrors (カーブミラー)
  const mirrorPole = new THREE.MeshStandardMaterial({ color: '#e46a1c', roughness: 0.5 });
  const mirrorGlass = new THREE.MeshStandardMaterial({ color: '#c8d4dc', metalness: 1, roughness: 0.05, envMapIntensity: 1.5 });
  const frameGeo = mergeGeometries([
    new THREE.CylinderGeometry(0.05, 0.05, 2.8, 8).translate(0, 1.4, 0),
    new THREE.TorusGeometry(0.4, 0.05, 8, 24).translate(0, 3.1, 0),
  ]);
  const glassGeo = new THREE.CircleGeometry(0.38, 24).translate(0, 3.1, 0);
  const mirrors: THREE.Matrix4[] = [];
  const q = new THREE.Quaternion(), up = new THREE.Vector3(0, 1, 0), one = new THREE.Vector3(1, 1, 1);
  for (const { i, lateral, yaw } of curveMirrorSpots(track)) {
    track.pointAt(i, lateral, p);
    q.setFromAxisAngle(up, yaw);
    mirrors.push(new THREE.Matrix4().compose(p, q, one));
  }
  const mirrorModel = prop('curveMirror');
  if (mirrorModel && mirrors.length) group.add(placeProp(mirrorModel, mirrors, { castShadow: true, name: 'curve-mirrors' }).group);
  else if (mirrors.length) {
    for (const [geo, mat] of [[frameGeo, mirrorPole], [glassGeo, mirrorGlass]] as const) {
      const mesh = new THREE.InstancedMesh(geo, mat, mirrors.length);
      mirrors.forEach((m, k) => mesh.setMatrixAt(k, m));
      mesh.name = 'curve-mirrors';
      group.add(mesh);
    }
  }
}

/**
 * `opts` (the autobahn's): `clearance` from the centreline instead of the mountain road's 10.5 m, `keep` rejects a
 * spot, `extra` places more trees through `add` after the scattered ones.
 */
export function buildTrees(
  terrain: TerrainData,
  density: number,
  lodDistance: number,
  opts: {
    clearance?: number;
    keep?: (x: number, z: number) => boolean;
    extra?: (add: (x: number, z: number, scale: number) => void) => void;
    /** chunk size (m) of the trees in the near grid (default 320 m: a chunk changes its level of detail as a whole) and outside it */
    chunk?: number;
    farChunk?: number;
    /** the Blender-made species (see `SceneryQuality.vegetation`) and whose course they are for */
    vegetation?: VegetationQuality;
    style?: CourseStyle;
  } = {},
) {
  const group = new THREE.Group();
  group.name = 'trees';
  const veg = opts.vegetation;
  const set = veg && veg.tier !== 'legacy' ? loadedSpecies(TREE_SETS[opts.style ?? 'touge']) : null;
  if (veg && set?.ids.length) {
    // levels of detail: the twig cards up close, bough cards, a few big cards, then the impostors
    const full = veg.tier === 'full';
    const forest = new Forest(set.species, plantTrees(terrain, density, opts.style ?? 'touge', set.ids, opts), {
      ranges: [full ? 28 * veg.range : 0, (full ? 80 : 60) * veg.range, (full ? 190 : 160) * veg.range],
      // (the shadow map is a square of 120 m around the car)
      shadows: 80,
      prepass: true,
      // (beyond lod1 and in the shadow map one shape per species: 24 draw calls less, each ~30 µs of main-thread time)
      single: [false, false, true, true],
    });
    group.add(forest.group);
    group.userData.lods = forest;
    return group;
  }
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
  const add = (x: number, z: number, scale: number, chunk = opts.chunk ?? CHUNK) => {
    if (opts.keep && !opts.keep(x, z)) return;
    const y = terrain.heightAt(x, z);
    if (lf.waterLevel !== null && y < lf.waterLevel + 3) return;
    // thinning out towards the tree line, none above it
    if (y > lf.treeLine + noise2(x / 90, z / 90) * 40) return;
    if (lf.relief(x, z) < 0.25 || cityWeight(lf, x, z) > 0.2) return;
    // slope check
    const dx = terrain.heightAt(x + 3, z) - terrain.heightAt(x - 3, z);
    const dz = terrain.heightAt(x, z + 3) - terrain.heightAt(x, z - 3);
    if (Math.hypot(dx, dz) / 6 > 1.25) return;
    const key = chunk === CHUNK ? `${Math.floor(x / CHUNK)},${Math.floor(z / CHUNK)}` : `f${Math.floor(x / chunk)},${Math.floor(z / chunk)}`;
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
    if (d < (opts.clearance ?? hw + 3.5)) continue;
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
    add(x, z, (12 + r() * 10) / 14, opts.farChunk ?? CHUNK);
  }
  opts.extra?.(add);
  // two levels of detail, picked per chunk by camera distance (Scenery.update())
  const farGeo = farTreeGeometry();
  const lods = new ChunkedLods(geo, farGeo, mat, [...chunks].map(([key, matrices]) => ({ matrices, colors: colors.get(key)! })), lodDistance);
  lods.near.castShadow = lods.near.receiveShadow = true;
  group.add(lods.near, lods.far);
  group.userData.lods = lods;
  return group;
}

/** Switch tree chunks between the detailed and the impostor mesh. */
export function updateTreeLods(trees: THREE.Object3D, camera: THREE.Vector3) {
  // (the old lumps of quality low have no levels: nothing to pick)
  (trees.userData.lods as ChunkedLods | Forest | undefined)?.update(camera);
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
export function buildClutter(
  track: Track,
  terrain: TerrainData,
  density: number,
  surfaceTexture: (n: SurfaceName, srgb: boolean) => THREE.Texture | null,
  keepOut: { x: number; z: number; r: number }[],
  /** the autobahn's: where along / beside the road (+ = right) clutter may go, and no rocks */
  opts: { accept?: (s: number, lateral: number) => boolean; rocks?: boolean; vegetation?: VegetationQuality; style?: CourseStyle } = {},
) {
  const group = new THREE.Group();
  group.name = 'clutter';
  // the Blender-made bushes, rocks and undergrowth (medium quality and above); the lumps below are the low quality's
  const veg = opts.vegetation;
  const style = opts.style ?? 'touge';
  const coverSet = veg && veg.tier !== 'legacy' ? loadedSpecies(COVER_SETS[style]) : null;
  if (veg && coverSet?.ids.length) {
    const underSet = loadedSpecies(veg.undergrowth > 0 ? UNDER_SETS[style] : []);
    const planted = plantCover(track, terrain, density, keepOut, coverSet.ids, underSet.ids, {
      accept: opts.accept,
      rocks: opts.rocks,
      undergrowth: veg.undergrowth,
      style,
    });
    const full = veg.tier === 'full';
    const forests = [
      new Forest(coverSet.species, planted.cover, {
        ranges: [full ? 16 * veg.range : 0, 42 * veg.range, 120 * veg.range],
        shadows: 30,
        impostors: false,
        capacity: [200, 800, 3000, 800],
        single: [false, false, true, true],
      }),
    ];
    if (planted.under.length) {
      forests.push(
        new Forest(underSet.species, planted.under, {
          // (what is this small is not seen further away; the density is the quality's, not the reach)
          // two levels only (a draw call costs more than these few triangles): the modelled blades, then crossed cards
          ranges: [full ? 24 : 0, 24, 62 * Math.min(veg.range, 1.1)],
          shadows: 0,
          impostors: false,
          capacity: [3000, 3000, 12000, 1],
          strides: [3, 3, 6, 8],
          single: [false, false, true, false],
        }),
      );
    }
    for (const f of forests) group.add(f.group);
    group.userData.lods = { update: (camera: THREE.Vector3) => forests.forEach((f) => f.update(camera)), stats: () => forests.map((f) => f.stats()) };
    return group;
  }
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
    if (opts.accept && !opts.accept(s, side * off)) continue;
    track.pointAt(s, side * off, p);
    if (keepOut.some((k) => (p.x - k.x) ** 2 + (p.z - k.z) ** 2 < k.r * k.r)) continue;
    const y = terrain.heightAt(p.x, p.z);
    const gx = (terrain.heightAt(p.x + 1.5, p.z) - terrain.heightAt(p.x - 1.5, p.z)) / 3;
    const gz = (terrain.heightAt(p.x, p.z + 1.5) - terrain.heightAt(p.x, p.z - 1.5)) / 3;
    const steep = Math.hypot(gx, gz);
    if (Math.abs(y - p.y) > 14) continue;
    q.setFromAxisAngle(UP, r() * 6.28);
    const rock = steep > 0.9 || r() < 0.18;
    if (rock && opts.rocks === false) continue;
    if (rock) {
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
export function buildTurbines(terrain: TerrainData) {
  const group = new THREE.Group();
  group.name = 'turbines';
  const model = prop('windTurbine');
  if (model) {
    const towers: THREE.Matrix4[] = [];
    const facing = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), 0.6);
    for (const [x, z] of terrain.landform.features.turbines ?? []) {
      if (terrain.roadDistAt(x, z) < 45) continue;
      towers.push(new THREE.Matrix4().compose(new THREE.Vector3(x, terrain.heightAt(x, z) - 1, z), facing, new THREE.Vector3(1, 1, 1)));
    }
    const phase = towers.map(() => Math.random() * 6);
    const placed = placeProp(model, towers, { castShadow: true, name: 'turbine-models' });
    group.add(placed.group);
    return { group, update: (time: number) => placed.spin((k) => time * 0.9 + phase[k]) };
  }
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
  return {
    group,
    update(time: number) {
      for (const r of rotors) r.rotation.z = time * 0.9 + r.userData.phase;
    },
  };
}

/**
 * A level spot beside the road for a landmark: the footprint (±`halfWidth` along the road, `depth` away
 * from it, starting `gap` beyond the shoulder) whose ground stays closest to road level, on a straight bit
 * away from the structures, the start and finish, and the given points, preferably on the hill side.
 * Null when nothing is within `tol`.
 */
function roadsideSpot(
  track: Track,
  terrain: TerrainData,
  sides: ReturnType<typeof classifySides>,
  o: { range: [number, number]; halfWidth: number; depth: number; gap: number; avoid: THREE.Vector3[]; tol: number },
) {
  const p = new THREE.Vector3();
  let best: { i: number; side: 1 | -1; dev: number } | null = null;
  for (let i = Math.max(o.range[0], 0); i < Math.min(o.range[1], track.count); i += 3) {
    const zone = track.zone[i];
    if (zone === 'rockshed' || zone === 'bridge' || Math.abs(track.curvature[i]) > 1 / 150) continue;
    if (Math.abs(i - track.startS) < 70 || Math.abs(i - track.finishS) < 70) continue;
    const road = track.pos[i * 3 + 1];
    for (const side of [1, -1] as const) {
      const edge = track.width[i] / 2 + SHOULDER + o.gap;
      track.pointAt(i, side * (edge + o.depth / 2), p);
      if (o.avoid.some((a) => (a.x - p.x) ** 2 + (a.z - p.z) ** 2 < 12 * 12)) continue;
      let dev = 0;
      for (const a of [-o.halfWidth, 0, o.halfWidth])
        for (const d of [0, o.depth / 2, o.depth]) {
          track.pointAt(i + a, side * (edge + d), p);
          dev = Math.max(dev, Math.abs(terrain.heightAt(p.x, p.z) - road));
        }
      // the hill side unless only the valley side is level: there a guardrail stands in front of it
      if (sides[side > 0 ? 'right' : 'left'].valley[i]) dev += 0.6;
      if (dev < o.tol + 0.6 && (!best || dev < best.dev)) best = { i, side, dev };
    }
  }
  return best;
}

/**
 * Roadside landmarks from the scenery models: a small shrine (torii between two stone lanterns) in the first
 * half of the course and a bus shelter in the second. Returns keep-out circles for the roadside clutter.
 */
function buildLandmarks(track: Track, terrain: TerrainData, sides: ReturnType<typeof classifySides>, group: THREE.Group, lamps: Lamp[]) {
  const keepOut: { x: number; z: number; r: number }[] = [];
  const avoid = [...lamps.map((l) => l.position), ...curveMirrorSpots(track).map((m) => track.pointAt(m.i, m.lateral))];
  const UP = new THREE.Vector3(0, 1, 0), one = new THREE.Vector3(1, 1, 1);
  /** frame at a spot: origin `depth` from the footprint's road edge, local +Z towards the road */
  const frame = (spot: { i: number; side: 1 | -1 }, gap: number, depth: number) => {
    const at = track.pointAt(spot.i, spot.side * (track.width[spot.i] / 2 + SHOULDER + gap + depth));
    at.y = terrain.heightAt(at.x, at.z) - 0.05;
    const toRoad = track.getRight(spot.i, new THREE.Vector3()).multiplyScalar(-spot.side);
    const q = new THREE.Quaternion().setFromAxisAngle(UP, Math.atan2(toRoad.x, toRoad.z));
    return (x: number, z: number, yaw = 0) =>
      new THREE.Matrix4().compose(new THREE.Vector3(x, 0, z).applyQuaternion(q).add(at), q.clone().multiply(new THREE.Quaternion().setFromAxisAngle(UP, yaw)), one);
  };
  const torii = prop('torii'), lantern = prop('stoneLantern'), shelter = prop('busStop');
  if (torii) {
    const spot = roadsideSpot(track, terrain, sides, { range: [Math.round(track.startS + 100), Math.round(track.count * 0.55)], halfWidth: 3, depth: 4, gap: 0.8, avoid, tol: 1.2 });
    if (spot) {
      const at = frame(spot, 0.8, 2.4);
      group.add(placeProp(torii, [at(0, -0.6)], { castShadow: true, name: 'torii' }).group);
      if (lantern) group.add(placeProp(lantern, [at(-2.1, 1.2), at(2.1, 1.2)], { castShadow: true, name: 'stone-lanterns' }).group);
      const c = new THREE.Vector3().setFromMatrixPosition(at(0, 0));
      keepOut.push({ x: c.x, z: c.z, r: 5 });
      avoid.push(c);
    }
  }
  if (shelter) {
    const spot = roadsideSpot(track, terrain, sides, { range: [Math.round(track.count * 0.45), Math.round(track.finishS - 100)], halfWidth: 4.5, depth: 5, gap: 0.5, avoid, tol: 1.2 });
    if (spot) {
      // the shelter reaches 1.13 m ahead of its origin (open side to the road; 2.25 m deep)
      const at = frame(spot, 0.5, 1.75);
      group.add(placeProp(shelter, [at(0, 0)], { castShadow: true, name: 'bus-stop' }).group);
      const c = new THREE.Vector3().setFromMatrixPosition(at(0, 0));
      keepOut.push({ x: c.x, z: c.z, r: 6 });
    }
  }
  return keepOut;
}
