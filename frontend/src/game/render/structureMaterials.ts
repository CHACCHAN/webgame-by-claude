import * as THREE from 'three';
import { MeshStandardNodeMaterial } from 'three/webgpu';
import {
  abs, attribute, cameraPosition, clamp, float, fract, materialEmissive, max, min, mix, normalMap, normalize, normalWorldGeometry, positionView, positionWorld,
  smoothstep, texture, uv, vec2, vec3, vec4,
} from 'three/tsl';
import { layerTexture, type LayerName } from './surfaceTextures';
import type { Float, Vec2, Vec3, Vec4 } from './tslNoise';
import { wetness } from './weather';

/**
 * What the things built along the road are made of (render/roadside.ts, the rock shed, the bridge, the autobahn's
 * walls). All of them read `uv` in metres (u along the road, v up the face from its foot), so a texture has its true
 * size on every part.
 *
 *  - concrete: cast in place (kerbs, gutters, copings, the slope frames), cast against formwork (rock shed, bridge:
 *    panel joints and tie holes), sprayed on a cut slope (吹付), or the wall of sloped blocks (間知ブロック) with its
 *    weep holes. Rain water runs down a face in streaks, the foot of a wall is green, everything darkens when wet.
 *  - metal: one material for every steel part; a vertex says what it is (`tint` = colour, `pbr` = metalness,
 *    roughness), so a whole stretch of roadside steel is one draw call.
 *  - reflector: the delineators' lenses throw the light back where it came from: bright when the camera's own
 *    lamps look at them, dark from the side.
 *  - net: the rockfall fence's wire mesh, cut out of a sheet by a mask (no blending).
 */
export type ConcreteKind = 'cast' | 'formed' | 'shotcrete' | 'block';

const LAYER: Record<ConcreteKind, { c: LayerName; n: LayerName; tile: number; tint: [number, number, number]; rough: number; bump: number }> = {
  cast: { c: 'concrete_c', n: 'concrete_n', tile: 2.4, tint: [0.4, 0.4, 0.39], rough: 0.86, bump: 0.7 },
  formed: { c: 'concrete_c', n: 'concrete_n', tile: 2.4, tint: [0.36, 0.36, 0.35], rough: 0.82, bump: 0.6 },
  shotcrete: { c: 'shotcrete_c', n: 'shotcrete_n', tile: 3, tint: [0.52, 0.51, 0.5], rough: 0.95, bump: 1.4 },
  block: { c: 'blockwall_c', n: 'blockwall_n', tile: 2, tint: [0.7, 0.7, 0.68], rough: 0.9, bump: 1.2 },
};

export function concreteMaterial(kind: ConcreteKind, opts: { doubleSide?: boolean; brightness?: number; uvScale?: number } = {}): MeshStandardNodeMaterial {
  const L = LAYER[kind];
  const mat = new MeshStandardNodeMaterial({ metalness: 0, roughness: 1, side: opts.doubleSide ? THREE.DoubleSide : THREE.FrontSide });
  mat.name = `concrete-${kind}`;
  mat.envMapIntensity = 0.35;
  // (`uvScale`: for geometry whose uv is not in metres, the metres one unit of it stands for)
  const at = (opts.uvScale ? uv().mul(opts.uvScale) : uv()) as unknown as Vec2;
  const wet = wetness as unknown as Float;
  const macro = layerTexture('macro');
  const tile = at.div(L.tile) as Vec2;
  const c = texture(layerTexture(L.c), tile) as unknown as Vec4;
  let col = c.rgb.mul(vec3(...L.tint)) as unknown as Vec3;
  let rough: Float = float(L.rough);
  // slow change along the wall: pours of different days, patches that stay damp
  const slow = texture(macro, at.div(vec2(37, 19))) as unknown as Vec4;
  col = col.mul(slow.r.mul(0.36).add(0.8)) as unknown as Vec3;
  // water runs down the face: dark streaks, drawn out along v
  const run = texture(macro, vec2(at.x.div(2.3), at.y.div(31))) as unknown as Vec4;
  const streak = smoothstep(0.52, 0.8, run.g.mul(0.7).add(slow.b.mul(0.3))) as Float;
  col = col.mul(mix(float(1), float(0.62), streak.mul(kind === 'cast' ? 0.5 : 1))) as unknown as Vec3;

  if (kind === 'formed') {
    // formwork: a panel joint every 1.8 m × 0.9 m, a tie hole at the panels' quarter points
    const g = at.div(vec2(1.8, 0.9)) as Vec2;
    const f = fract(g) as Vec2;
    const edge = min(min(f.x, float(1).sub(f.x)).mul(1.8), min(f.y, float(1).sub(f.y)).mul(0.9)) as Float;
    const joint = smoothstep(0.012, 0.004, edge) as Float;
    const hole = vec2(abs(fract(g.x.mul(2)).sub(0.5)).mul(0.9), abs(f.y.sub(0.5)).mul(0.9)).length() as Float;
    const tie = smoothstep(0.022, 0.014, hole) as Float;
    col = col.mul(float(1).sub(max(joint.mul(0.45), tie.mul(0.75)))) as unknown as Vec3;
    // each panel a shade of its own
    const panel = texture(macro, g.floor().add(0.5).div(64)) as unknown as Vec4;
    col = col.mul(panel.a.mul(0.22).add(0.89)) as unknown as Vec3;
  }
  if (kind === 'shotcrete' || kind === 'block' || kind === 'formed') {
    // the foot of a wall: splashed dirt, then moss where it stays wet
    const foot = smoothstep(1.1, 0.0, at.y.add(run.r.sub(0.5).mul(0.9))) as Float;
    const moss = foot.mul(smoothstep(0.4, 0.7, slow.g)).mul(kind === 'formed' ? 0.45 : 0.8) as Float;
    col = mix(col, col.mul(vec3(0.5, 0.48, 0.42)), foot.mul(0.6)) as unknown as Vec3;
    col = mix(col, vec3(0.035, 0.06, 0.022).mul(c.a.mul(0.8).add(0.5)), moss) as unknown as Vec3;
    rough = mix(rough, float(0.97), moss) as Float;
  }
  if (opts.brightness !== undefined && opts.brightness !== 1) col = col.mul(opts.brightness) as unknown as Vec3;
  // rain: concrete drinks it and darkens, most where the streaks already run
  col = col.mul(mix(float(1), mix(float(0.66), float(0.5), streak), wet)) as unknown as Vec3;
  rough = mix(rough, rough.mul(0.55), wet) as Float;
  mat.colorNode = vec4(col, 1);
  mat.roughnessNode = clamp(rough, 0.05, 1);
  mat.normalNode = normalMap(texture(layerTexture(L.n), tile), vec2(L.bump, L.bump));
  return mat;
}

/** what a steel part is: colour (linear), metalness, roughness */
export const METAL: Record<string, [number, number, number, number, number]> = {
  // the guardrail's white paint over galvanised steel
  galvanised: [0.66, 0.67, 0.66, 0.3, 0.42],
  bare: [0.5, 0.52, 0.53, 0.85, 0.4],
  grating: [0.1, 0.105, 0.11, 0.8, 0.5],
  post_white: [0.74, 0.74, 0.7, 0, 0.5],
  rust: [0.12, 0.062, 0.036, 0.3, 0.85],
  pit: [0.003, 0.003, 0.003, 0, 1],
  blue: [0.02, 0.09, 0.3, 0, 0.5],
};

export function metalMaterial(): MeshStandardNodeMaterial {
  const mat = new MeshStandardNodeMaterial({ side: THREE.DoubleSide });
  mat.name = 'roadside-metal';
  const tint = attribute('tint', 'vec3') as unknown as Vec3;
  const pbr = attribute('pbr', 'vec2') as unknown as Vec2;
  const P = positionWorld as unknown as Vec3;
  const wet = wetness as unknown as Float;
  const macro = layerTexture('macro');
  // weather on the paint: a slow change, and grime that gathers low on a part
  const n = texture(macro, vec2(P.x.add(P.z).div(3.1), P.y.div(0.9).add(P.x.sub(P.z).div(7.3)))) as unknown as Vec4;
  const grime = smoothstep(0.45, 0.8, n.g.mul(0.6).add(n.b.mul(0.4))) as Float;
  let col = tint.mul(n.r.mul(0.3).add(0.82)) as unknown as Vec3;
  col = mix(col, col.mul(vec3(0.6, 0.57, 0.52)), grime.mul(0.28)) as unknown as Vec3;
  // rust blooms through painted steel here and there (never on what is not metal at all)
  const rusty = smoothstep(0.8, 0.9, n.a).mul(smoothstep(0.1, 0.3, pbr.x)).mul(0.6) as Float;
  col = mix(col, vec3(0.13, 0.065, 0.035), rusty) as unknown as Vec3;
  mat.colorNode = vec4(col, 1);
  mat.metalnessNode = pbr.x.mul(float(1).sub(rusty));
  mat.roughnessNode = clamp(mix(pbr.y.add(grime.mul(0.2)).add(rusty.mul(0.3)), pbr.y.mul(0.6), wet), 0.08, 1);
  return mat;
}

/**
 * The delineators' lenses. Push the returned material onto the scenery's `nightEmissive`: its emissive intensity is
 * the lamps' state (the lenses answer headlights, which are on when the lamps are).
 */
export function reflectorMaterial(): MeshStandardNodeMaterial {
  const mat = new MeshStandardNodeMaterial({ roughness: 0.25, metalness: 0, side: THREE.DoubleSide });
  mat.name = 'roadside-reflector';
  mat.emissive = new THREE.Color(1, 1, 1);
  mat.emissiveIntensity = 1;
  const tint = attribute('tint', 'vec3') as unknown as Vec3;
  const P = positionWorld as unknown as Vec3;
  const toEye = cameraPosition.sub(P) as unknown as Vec3;
  const d = toEye.length() as Float;
  const N = normalize(normalWorldGeometry) as unknown as Vec3;
  // a lens returns light within some 25° of its axis, either face
  const facing = smoothstep(0.25, 0.8, abs(N.dot(toEye.div(d)))) as Float;
  // the car's lamps point where the camera looks: in their cone, fading with the square of the way there and back
  const ahead = smoothstep(0.6, 0.92, (normalize(positionView) as unknown as Vec3).z.negate()) as Float;
  const reach = float(1).div(d.div(55).mul(d.div(55)).add(1)) as Float;
  mat.colorNode = vec4(tint.mul(0.5), 1);
  mat.emissiveNode = (materialEmissive as unknown as Vec3).mul(tint).mul(facing.mul(ahead).mul(reach).mul(3.2).add(0.04));
  return mat;
}

/** the wire mesh of a rockfall fence: a sheet with uv in units of one texture tile (0.5 m) */
export function netMaterial(): MeshStandardNodeMaterial {
  const mat = new MeshStandardNodeMaterial({ metalness: 0.6, roughness: 0.55, side: THREE.DoubleSide });
  mat.name = 'roadside-net';
  const a = (texture(layerTexture('wiremesh'), uv()) as unknown as Vec4).a as Float;
  mat.colorNode = vec4(0.3, 0.31, 0.3, 1);
  // (a mask, not alphaTest: see render/instancing.ts `cutOut`)
  mat.maskNode = a.greaterThan(0.3);
  return mat;
}
