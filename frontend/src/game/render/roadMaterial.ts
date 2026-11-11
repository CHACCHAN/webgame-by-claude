import * as THREE from 'three';
import { MeshStandardNodeMaterial } from 'three/webgpu';
import { abs, attribute, clamp, exp, float, floor, fract, fwidth, max, min, mix, normalMap, sin, smoothstep, step, texture, time, uv, vec2, vec3, vec4 } from 'three/tsl';
import { layerTexture } from './surfaceTextures';
import { hash2, type Float, type Vec2, type Vec3, type Vec4 } from './tslNoise';
import { wetness } from './weather';

/**
 * The road's surface in one material (one draw call): scanned asphalt, and on it what years of traffic and road
 * works leave. Sections laid at different times with tar joints between them, cut-out repair patches, cracks (some
 * sealed with tar), wheel tracks polished by tyres with the oil line between them, grit creeping in from the edge,
 * manhole covers; the lines painted on top, worn where they are old and fresh where they were redone (the old line
 * still showing beside the new). In rain the asphalt darkens and shines, and water stands in the wheel tracks and
 * hollows, with the rings of the drops in it. Nothing here touches the geometry or the grip.
 *
 * Geometry: `uv` (u across, v = metres along) and `road` = (metres from the centreline, + = right; half width of
 * the asphalt up to the barriers), from track/roadGeometry.ts.
 */
export interface RoadLook {
  /**
   * 'touge': the mountain road's lines (white edge lines, orange centre line) are painted here. Or the autobahn's
   * marking atlas, sampled at `uv` × `atlasScale` (asphalt and lines come from it; wear and rain go on top).
   */
  markings: 'touge' | { atlas: THREE.Texture; scale: [number, number] };
  /** centres of the lanes (m from the centreline), for the wheel tracks: default one lane each way */
  lanes?: number[];
  /** brightness of the asphalt (default 1) */
  brightness?: number;
}

export function roadMaterial(look: RoadLook, detail: 1 | 2 | 3): MeshStandardNodeMaterial {
  const mat = new MeshStandardNodeMaterial({ metalness: 0, roughness: 1 });
  mat.envMapIntensity = 0.6;
  mat.name = 'road';
  const road = attribute('road', 'vec2') as unknown as Vec2;
  const lat = road.x as Float, hw = road.y as Float;
  const s = (uv() as unknown as Vec2).y as Float;
  const at = vec2(lat, s) as Vec2;
  /** metres inside the barrier line (negative: the skirt under the verge) */
  const inside = hw.sub(abs(lat)) as Float;
  const wet = wetness as unknown as Float;
  const touge = look.markings === 'touge';

  const marks = texture(layerTexture('roadmarks'), at.div(8)) as unknown as Vec4;
  // a second copy turned by 37°, so the two never line up
  const marks2 = texture(layerTexture('roadmarks'), vec2(lat.mul(0.8).add(s.mul(0.6)), s.mul(0.8).sub(lat.mul(0.6))).div(5.7)) as unknown as Vec4;
  const macro = layerTexture('macro');
  const mA = texture(macro, vec2(lat.div(23), s.div(61))) as unknown as Vec4;
  // drawn out along the road: what traffic and water do
  const mB = texture(macro, vec2(lat.div(9), s.div(230)).add(0.5)) as unknown as Vec4;

  // ---- asphalt
  const tile = at.div(2.7) as Vec2;
  let col: Vec3;
  if (touge) col = (texture(layerTexture('asphalt_albedo'), tile) as unknown as Vec4).rgb.mul(0.93) as unknown as Vec3;
  else {
    const m = look.markings as { atlas: THREE.Texture; scale: [number, number] };
    col = (texture(m.atlas, (uv() as unknown as Vec2).mul(vec2(m.scale[0], m.scale[1]))) as unknown as Vec4).rgb as unknown as Vec3;
  }
  let rough = touge ? (clamp((texture(layerTexture('asphalt_rough'), tile) as unknown as Vec4).r, 0.45, 1) as Float) : (float(0.8) as Float);
  col = col.mul(mA.r.mul(0.2).add(0.9)) as unknown as Vec3;

  // sections laid in different years, a tar joint across the road where they meet
  const sec = s.div(47).add(mB.r.mul(0.4)) as Float;
  const newer = step(0.6, hash2(vec2(floor(sec), 3.7))) as Float;
  const secEdge = min(fract(sec), float(1).sub(fract(sec))).mul(47) as Float;
  let tar = smoothstep(0.035, 0.012, secEdge) as Float;
  // repair patches: a rectangle cut out of one lane and filled, its edge sealed
  const cell = vec2(floor(s.div(9.1)), step(0, lat)) as Vec2;
  const ph = hash2(cell) as Float, ph2 = hash2(cell.add(vec2(5.3, 1.7))) as Float;
  const along = fract(s.div(9.1)).mul(9.1) as Float;
  const boxS = min(along.sub(ph2.mul(2).add(0.8)), ph2.mul(2).add(4.2).add(ph.mul(2)).sub(along)) as Float;
  const boxL = min(abs(lat).sub(ph2.mul(0.9).add(0.25)), hw.sub(1.15).sub(ph.mul(0.8)).sub(abs(lat))) as Float;
  const box = min(boxS, boxL) as Float;
  const hasPatch = step(0.84, ph) as Float;
  const patch = hasPatch.mul(step(0, box)) as Float;
  tar = max(tar, hasPatch.mul(smoothstep(0.04, 0.012, abs(box)))) as Float;
  const fresh = max(newer.mul(0.8), patch) as Float;
  col = col.mul(mix(float(1), float(0.72), fresh)) as unknown as Vec3;
  rough = mix(rough, rough.mul(0.94), fresh) as Float;

  // cracks where the old surface has tired; the wider ones are sealed with tar
  const gateA = smoothstep(0.58, 0.72, mA.b) as Float, gateB = smoothstep(0.66, 0.84, mA.a.mul(0.7).add(mB.g.mul(0.3))) as Float;
  const crack = max(marks.r.mul(gateA), marks2.r.mul(gateB)).mul(float(1).sub(fresh.mul(0.95))) as Float;
  const sealed = smoothstep(0.5, 0.6, mB.b) as Float;
  tar = max(tar, crack.mul(sealed)) as Float;
  const open = crack.mul(float(1).sub(sealed)) as Float;

  // wheel tracks: polished, a shade lighter; the oil line down the middle of a lane
  const lanes = look.lanes ?? null;
  let polish: Float = float(0), oil: Float = float(0);
  const track = (centre: Float) => {
    const d = abs(lat.sub(centre)) as Float;
    const w = d.sub(0.78).div(0.24) as Float;
    polish = polish.add(exp(w.mul(w).negate())) as Float;
    oil = oil.add(exp(d.div(0.3).mul(d.div(0.3)).negate())) as Float;
  };
  if (lanes) for (const c of lanes) track(float(c));
  else {
    const c = hw.sub(0.75).mul(0.5) as Float;
    track(c);
    track(c.negate() as Float);
  }
  polish = polish.mul(mB.a.mul(0.6).add(0.55)) as Float;
  col = col.mul(polish.mul(0.07).add(1)).mul(float(1).sub(oil.mul(0.08))) as unknown as Vec3;
  rough = rough.sub(polish.mul(0.13)) as Float;

  // ---- paint
  let paint: Float = float(0);
  if (touge) {
    const aa = fwidth(lat) as Float;
    const line = (d: Float, half: number) => smoothstep(aa.add(half), float(half).sub(aa), d) as Float;
    // stretches where the lines were redone: bright and whole, the old line still showing beside the new
    const redone = step(0.62, hash2(vec2(floor(s.div(83).add(0.3)), 9.1))) as Float;
    const wearAt = mix(mix(float(0.45), float(0.75), mB.g), float(0.9), redone) as Float;
    const worn = smoothstep(wearAt, wearAt.add(0.16), mA.a.mul(0.5).add(marks2.b.mul(0.3)).add(marks.b.mul(0.2))) as Float;
    const keep = float(1).sub(worn.mul(0.7)).mul(float(1).sub(crack.mul(0.85))) as Float;
    const edge = line(abs(inside.sub(0.75)) as Float, 0.075);
    const centre = line(abs(lat) as Float, 0.1);
    const ghost = line(abs(inside.sub(0.93)) as Float, 0.07).mul(redone).mul(0.16).mul(marks.b) as Float;
    const white = vec3(0.8, 0.8, 0.75), orange = vec3(0.82, 0.36, 0.03);
    const bright = mix(float(0.82), float(1.08), redone) as Float;
    col = mix(col, white.mul(0.55), ghost) as unknown as Vec3;
    paint = max(edge, centre).mul(keep) as Float;
    col = mix(col, mix(white, orange, centre).mul(bright).mul(marks2.b.mul(0.2).add(0.86)), paint) as unknown as Vec3;
    rough = mix(rough, float(0.62), paint) as Float;
  }

  // tar and open cracks go over everything
  col = mix(col, vec3(0.012, 0.012, 0.013), tar.mul(0.92)) as unknown as Vec3;
  col = col.mul(float(1).sub(open.mul(0.55))) as unknown as Vec3;
  rough = mix(mix(rough, float(0.56), tar), float(0.97), open) as Float;

  // a manhole cover now and then: cast iron in a square of newer asphalt
  let iron: Float = float(0);
  if (touge) {
    const mc = floor(s.div(163)) as Float;
    const mh = hash2(vec2(mc, 21.3)) as Float;
    const s0 = mc.add(mh.mul(0.5).add(0.25)).mul(163) as Float;
    const l0 = hw.sub(0.75).mul(0.5).mul(step(0.5, hash2(vec2(mc, 4.9))).mul(2).sub(1)) as Float;
    const dx = lat.sub(l0) as Float, dz = s.sub(s0) as Float;
    const d = vec2(dx, dz).length() as Float;
    const sq = max(abs(dx), abs(dz)) as Float;
    const surround = smoothstep(0.62, 0.6, sq) as Float;
    iron = smoothstep(0.335, 0.32, d) as Float;
    // the lid's pattern of raised squares, its rim and the frame's gap
    const studs = smoothstep(-0.2, 0.2, sin(dx.mul(52)).mul(sin(dz.mul(52)))).mul(smoothstep(0.27, 0.25, d)) as Float;
    const gap = smoothstep(0.012, 0.004, abs(d.sub(0.3))) as Float;
    col = mix(col, col.mul(0.7), surround) as unknown as Vec3;
    col = mix(col, vec3(0.012, 0.012, 0.013), smoothstep(0.03, 0.012, abs(sq.sub(0.61))).mul(0.9)) as unknown as Vec3;
    col = mix(col, vec3(0.05, 0.047, 0.043).mul(studs.mul(0.9).add(0.55)).mul(float(1).sub(gap.mul(0.8))), iron) as unknown as Vec3;
    rough = mix(rough, studs.mul(-0.12).add(0.5), iron) as Float;
    paint = paint.mul(float(1).sub(iron)) as Float;
    mat.metalnessNode = iron.mul(0.85);
  }

  // grit and dirt creeping in from the edge; the skirt under the verge is all dirt
  const grit = smoothstep(0.5, -0.05, inside.add(marks.b.sub(0.5).mul(0.5)).add(mA.g.sub(0.5).mul(0.55))).mul(float(1).sub(paint.mul(0.7))) as Float;
  col = mix(col, vec3(0.075, 0.066, 0.052).mul(marks2.b.mul(0.9).add(0.5)), grit) as unknown as Vec3;
  rough = mix(rough, float(0.96), grit) as Float;
  if (look.brightness !== undefined && look.brightness !== 1) col = col.mul(look.brightness) as unknown as Vec3;

  // ---- rain
  // water stands in the wheel tracks and in the road's hollows, never on the crown's fresh patches
  const hollow = mA.g.mul(0.62).add(mB.r.mul(0.38)).add(polish.mul(0.13)).sub(fresh.mul(0.08)).sub(grit.mul(0.3)) as Float;
  const puddle = smoothstep(0.585, 0.66, hollow).mul(wet).mul(float(1).sub(iron)) as Float;
  col = col.mul(mix(float(1), mix(float(0.5), float(0.62), paint), wet)) as unknown as Vec3;
  col = mix(col, col.mul(0.72), puddle) as unknown as Vec3;
  rough = mix(mix(rough, rough.mul(0.42).add(0.06), wet), float(0.03), puddle) as Float;

  mat.colorNode = vec4(col, 1);
  mat.roughnessNode = clamp(rough, 0.03, 1);

  // ---- the surface's small shape: the aggregate, flattened by paint, tar and water
  const bump = float(1).sub(max(max(paint.mul(0.6), tar.mul(0.8)), puddle)).mul(mix(float(1), float(0.55), wet)).mul(mix(float(1), float(0.7), fresh)) as Float;
  const nt = (texture(layerTexture('asphalt_normal'), tile) as unknown as Vec4).xyz as unknown as Vec3;
  let xy = nt.xy.mul(2).sub(1).mul(bump) as Vec2;
  if (detail >= 2) {
    // rings of the drops in the standing water: a drop per cell of 0.4 m, each on its own clock
    const g = at.div(0.4) as Vec2;
    const id = floor(g) as Vec2;
    const centre = vec2(hash2(id.add(1.7)), hash2(id.add(4.1))).mul(0.5).add(0.25) as Vec2;
    const off = fract(g).sub(centre) as Vec2;
    const r = off.length() as Float;
    const t = fract(time.mul(1.1).add(hash2(id).mul(7))) as Float;
    const front = r.sub(t.mul(0.5)) as Float;
    const ring = sin(front.mul(42)).mul(smoothstep(0.1, 0.0, abs(front))).mul(float(1).sub(t)) as Float;
    xy = xy.add(off.div(r.add(1e-3)).mul(ring).mul(puddle).mul(0.45)) as Vec2;
  }
  // (as a normal map's colour again: the node below unpacks it and turns it into the road's frame)
  const normal = normalMap(vec3(xy.mul(0.5).add(0.5), nt.z));
  mat.normalNode = normal;
  return mat;
}
