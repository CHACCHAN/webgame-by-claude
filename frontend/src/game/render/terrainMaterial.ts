import * as THREE from 'three';
import { IrradianceNode, MeshStandardNodeMaterial } from 'three/webgpu';
import {
  attribute, bumpMap, cameraPosition, cameraViewMatrix, clamp, float, materialLightMap, max, mix, normalWorldGeometry, normalize, positionWorld, sign,
  smoothstep, texture, vec2, vec3, vec4,
} from 'three/tsl';
import { HEIGHT_FLOOR, layerTexture, type LayerName } from './surfaceTextures';
import type { Float, Vec2, Vec3, Vec4 } from './tslNoise';
import { wetness } from './weather';

/**
 * The ground's material: it knows what the ground is. Rock on steep faces (textured from the sides, so nothing
 * stretches), the forest's floor under the trees, moss and grass on gentle open ground, gravel and dirt along the
 * road, sand at the water, each a photo layer (colour + height + normals) blended by slope, the shape of the land,
 * the distance to the road and slow noise, with the layers' own heights deciding who shows through at a border.
 * In rain everything darkens and shines, and hollows hold water.
 *
 * What it reads per vertex (`surf`, four bytes, `gridGeometry`): x = metres beyond the road's graded edge
 * ((x · 34) − 2), y = how convex the land is there (0.5 = flat), z = town, w = forest (trees grow here).
 * The far grid's variant draws the same land from far away: the layers at a coarse scale, bumps from the noise,
 * no normal maps.
 */
export interface GroundLook {
  /** the gentle ground's layer: mossy forest ground, or a meadow's grass (fields, the land above the tree line) */
  grass: 'moss' | 'grass';
  /** the lake's or the sea's surface: sand and wet stones just above it, dark bed below */
  waterLevel: number | null;
  /** overall brightness of the colours (default 1) */
  brightness?: number;
}

/** how much of the material a quality level pays for: 1 = medium, 2 = high, 3 = ultra */
export type GroundDetail = 1 | 2 | 3;

// what the layers' photos are multiplied with (linear): they come as bright as the day they were taken on,
// the game's ground is seen by lamps and the moon
const TINT = {
  rock: [0.88, 0.86, 0.84] as const,
  floor: [0.3, 0.35, 0.42] as const,
  moss: [0.16, 0.21, 0.25] as const,
  grass: [0.42, 0.44, 0.5] as const,
  gravel: [0.62, 0.62, 0.64] as const,
};

const c4 = (name: LayerName, at: Vec2) => texture(layerTexture(name), at) as unknown as Vec4;
/** a normal map's x and y, −1..1 */
const n2 = (name: LayerName, at: Vec2) => (texture(layerTexture(name), at) as unknown as Vec4).xy.mul(2).sub(1) as Vec2;
/** the height a colour texture carries in its alpha, 0..1 */
const heightOf = (c: Vec4) => c.a.sub(HEIGHT_FLOOR).div(1 - HEIGHT_FLOOR) as Float;
/** how much of a layer of weight `w` shows over a base: the higher surface wins around w = 0.5 */
const over = (w: Float, base: Float, top: Float) => clamp(w.sub(0.5).mul(4.4).add(top.sub(base).mul(1.2)).add(0.5), 0, 1) as Float;

export function groundMaterial(look: GroundLook, detail: GroundDetail, far = false): MeshStandardNodeMaterial {
  const mat = new MeshStandardNodeMaterial({ metalness: 0, roughness: 1 });
  mat.envMapIntensity = 0.3;
  mat.name = far ? 'ground-far' : 'ground';
  const P = positionWorld as unknown as Vec3;
  const N = normalize(normalWorldGeometry) as unknown as Vec3;
  const surf = attribute('surf', 'vec4') as unknown as Vec4;
  const macro = layerTexture('macro');
  // slow noises: patches of tens of metres, and whole hillsides
  const m1 = texture(macro, P.xz.div(211)) as unknown as Vec4;
  const m2 = texture(macro, P.xz.div(1730).add(0.37)) as unknown as Vec4;
  const slope = float(1).sub(N.y) as Float;
  const beyond = surf.x.mul(34).sub(2) as Float;
  const convex = surf.y.sub(0.5).mul(2) as Float;
  const urban = surf.z as Float, forest = surf.w as Float;
  const dist = P.sub(cameraPosition).length() as Float;
  const wet = wetness as unknown as Float;

  // ---- who is where
  // the road's cutting: bare for a while after the digger left
  const cut = smoothstep(24, 5, beyond).mul(smoothstep(0.1, 0.28, slope)) as Float;
  const rockW = smoothstep(0.25, 0.43, slope.add(m1.r.sub(0.5).mul(0.2)).add(convex.mul(0.06)).add(cut.mul(0.15))) as Float;
  const floorW = smoothstep(0.38, 0.62, forest.mul(0.82).add(m1.g.sub(0.5).mul(0.7)).add(m2.b.sub(0.5).mul(0.4)).add(cut.mul(0.2))) as Float;
  const gravelW = max(smoothstep(2.6, 0.2, beyond.add(m1.b.sub(0.5).mul(2.4))), urban.mul(0.92)) as Float;

  // ---- the layers
  const k = far ? 13 : 1;
  const grassAt = P.xz.div(2.7 * k) as Vec2, floorAt = P.xz.div(3.3 * k) as Vec2, gravelAt = P.xz.div(2.1) as Vec2;
  const grassName = look.grass === 'grass' ? 'grass' : 'moss';
  let grassC = c4(`${grassName}_c`, grassAt), floorC = c4('floor_c', floorAt);
  if (!far && detail >= 3) {
    // from a distance the same photo every three metres shows as a pattern: a second, wider copy takes over
    const wide = smoothstep(18, 70, dist).mul(0.75);
    grassC = mix(grassC, c4(`${grassName}_c`, grassAt.div(5.3).add(0.31)), wide) as unknown as Vec4;
    floorC = mix(floorC, c4('floor_c', floorAt.div(4.7).add(0.57)), wide) as unknown as Vec4;
  }
  const grassH = heightOf(grassC), floorH = heightOf(floorC);
  const tFloor = over(floorW, grassH, floorH);
  let col = mix(grassC.rgb.mul(vec3(...TINT[grassName])), floorC.rgb.mul(vec3(...TINT.floor)), tFloor) as unknown as Vec3;
  let height = mix(grassH, floorH, tFloor) as Float;
  let rough = mix(float(0.84), float(0.93), tFloor) as Float;
  // how much rain darkens a surface: soil drinks it, stone only shines
  let soak = mix(float(0.62), float(0.5), tFloor) as Float;

  let tGravel: Float | null = null;
  if (!far) {
    const gravelC = c4('gravel_c', gravelAt);
    tGravel = over(gravelW, height, heightOf(gravelC));
    col = mix(col, gravelC.rgb.mul(vec3(...TINT.gravel)), tGravel) as unknown as Vec3;
    height = mix(height, heightOf(gravelC), tGravel) as Float;
    rough = mix(rough, float(0.88), tGravel) as Float;
    soak = mix(soak, float(0.6), tGravel) as Float;
  } else col = mix(col, vec3(0.045, 0.045, 0.047), urban.mul(0.9)) as unknown as Vec3;

  // rock from its two sides (the top view would smear down a cliff)
  let rockC: Vec4;
  let rockSides: { atX: Vec2; atZ: Vec2; wx: Float; wz: Float; sx: Float; sz: Float } | null = null;
  if (far) rockC = c4('rock_c', P.xz.div(47));
  else {
    const sx = sign(N.x) as Float, sz = sign(N.z) as Float;
    const atX = vec2(P.z.mul(sx.negate()), P.y).div(4.3) as Vec2, atZ = vec2(P.x.mul(sz), P.y).div(4.3) as Vec2;
    const wx = N.x.mul(N.x) as Float, wz = N.z.mul(N.z) as Float;
    rockC = c4('rock_c', atX).mul(wx).add(c4('rock_c', atZ).mul(wz)).div(wx.add(wz).add(1e-4)) as unknown as Vec4;
    rockSides = { atX, atZ, wx, wz, sx, sz };
  }
  // moss creeps over rock that is not too steep; the cutting's rock is fresh and bare
  const mossy = smoothstep(0.55, 0.3, slope).mul(smoothstep(0.35, 0.7, m1.a)).mul(float(1).sub(cut)).mul(0.6) as Float;
  const rockCol = mix(rockC.rgb.mul(vec3(...TINT.rock)), rockC.rgb.mul(vec3(0.5, 0.74, 0.34)), mossy) as unknown as Vec3;
  const rockH = heightOf(rockC).mul(0.7).add(0.3) as Float;
  const tRock = over(rockW, height, rockH);
  col = mix(col, rockCol, tRock) as unknown as Vec3;
  height = mix(height, rockH, tRock) as Float;
  rough = mix(rough, float(0.8), tRock) as Float;
  soak = mix(soak, float(0.72), tRock) as Float;

  // ---- the land's own variation: lighter and darker hillsides, drier patches
  col = col.mul(m2.r.mul(0.5).add(0.74)).mul(m1.a.mul(0.24).add(0.88)) as unknown as Vec3;
  col = mix(col, col.mul(vec3(1.16, 1.02, 0.78)), m2.g.mul(float(1).sub(tRock)).mul(0.7)) as unknown as Vec3;
  // the small shadows between stones and leaves
  col = col.mul(height.mul(0.34).add(0.66)) as unknown as Vec3;
  if (look.waterLevel !== null) {
    const y = P.y.sub(look.waterLevel) as Float;
    // a rim of pale stones the water has washed, then the dark bed
    col = mix(col, vec3(0.2, 0.19, 0.165).mul(height.mul(0.5).add(0.6)), smoothstep(2.4, 0.5, y).mul(0.75)) as unknown as Vec3;
    col = mix(col, vec3(0.02, 0.035, 0.04), smoothstep(-0.3, -3.5, y)) as unknown as Vec3;
    rough = mix(rough, float(0.45), smoothstep(0.9, 0.2, y)) as Float;
  }
  if (look.brightness !== undefined && look.brightness !== 1) col = col.mul(look.brightness) as unknown as Vec3;

  // ---- rain: darker, glossier, and water standing in flat hollows
  const pool = wet.mul(smoothstep(0.02, 0.4, convex.negate())).mul(smoothstep(0.16, 0.04, slope)).mul(smoothstep(0.45, 0.75, m1.r)).mul(smoothstep(0.55, 0.2, height)) as Float;
  col = col.mul(mix(float(1), soak, wet)) as unknown as Vec3;
  rough = mix(mix(rough, rough.mul(0.52), wet), float(0.08), pool) as Float;

  mat.colorNode = vec4(col, 1);
  mat.roughnessNode = rough;

  // ---- the surface's small shape
  let nW: Vec3;
  if (far) {
    // the far land has no normal maps: the hillside noise as bumps, so slopes ten kilometres off are not smooth cones
    mat.normalNode = bumpMap((texture(macro, P.xz.div(160)) as unknown as Vec4).r.mul(0.6).add((texture(macro, P.xz.div(37)) as unknown as Vec4).g.mul(0.4)) as never, float(26));
    nW = N;
  } else {
    // (the grid's cells are metres wide: far away a normal map's detail is smaller than a pixel and only flickers)
    const strength = mix(float(1), float(0.35), smoothstep(40, 160, dist)).mul(float(1).sub(pool)) as Float;
    let flat = mix(n2(`${grassName}_n`, grassAt), n2('floor_n', floorAt), tFloor) as unknown as Vec2;
    if (detail >= 2 && tGravel) flat = mix(flat, n2('gravel_n', gravelAt), tGravel) as unknown as Vec2;
    // seen from above: the texture's u runs along +X, its v along +Z
    const nTop = normalize(vec3(N.x.add(flat.x.mul(strength)), N.y, N.z.add(flat.y.mul(strength)))) as unknown as Vec3;
    if (detail >= 2 && rockSides) {
      const { atX, atZ, wx, wz, sx, sz } = rockSides;
      const rx = n2('rock_n', atX).mul(strength.mul(1.25)) as Vec2, rz = n2('rock_n', atZ).mul(strength.mul(1.25)) as Vec2;
      // a side view's u runs along the wall (mirrored with the side it faces), its v upwards
      const nX = vec3(N.x, N.y.add(rx.y), N.z.sub(rx.x.mul(sx))) as unknown as Vec3;
      const nZ = vec3(N.x.add(rz.x.mul(sz)), N.y.add(rz.y), N.z) as unknown as Vec3;
      const nRock = normalize(nX.mul(wx).add(nZ.mul(wz)).add(N.mul(1e-3))) as unknown as Vec3;
      nW = normalize(mix(nTop, nRock, tRock)) as unknown as Vec3;
    } else nW = nTop;
    mat.normalNode = cameraViewMatrix.mul(vec4(nW, 0)).xyz.normalize();
    // the baked lamp light comes from above: a stone's top takes more of it than its flank
    const facing = clamp(nW.y.div(N.y.add(0.25)).mul(1.05).add(0.1), 0.35, 1.3);
    (mat as unknown as { setupLightMap: (b: { material: THREE.Material & { lightMap?: unknown } }) => unknown }).setupLightMap = (b) =>
      b.material.lightMap ? new IrradianceNode((materialLightMap as unknown as Vec3).mul(facing)) : null;
  }
  return mat;
}
