import type * as THREE from 'three';
import { abs, clamp, float, floor, ivec2, max, mix, positionWorld, renderGroup, shadow, smoothstep, textureLoad, uniform, vec2, vec3 } from 'three/tsl';
import type { FarShade } from './farShade';
import { SHADE_SIZE } from './lightAtlas';

type N = any; // eslint-disable-line @typescript-eslint/no-explicit-any

/** where the shadow map lies this frame (`LightRig.aimKey`): its middle, its two axes on the ground of the light, half its side */
export interface KeyMapFrame {
  at: THREE.Vector3;
  x: THREE.Vector3;
  y: THREE.Vector3;
  half: number;
}

/** the shadow map gives way to the baked shade over this share of its half side, at its edge */
const EDGE = 0.18;

/**
 * How much of the baked shade's light a point gets: x from the land alone, y from the land, the roofs and the trees
 * (`render/farShade.ts`). Four texels read and blended by hand: the land's height is 16 bits in two bytes, which no
 * sampler can blend.
 */
export function bakedShade(shade: FarShade, P: N = positionWorld): N {
  const frame: N = uniform(shade.frame).setGroup(renderGroup), scale: N = uniform(shade.scale).setGroup(renderGroup);
  const g: N = P.xz.sub(frame.xy).mul(frame.zw).sub(0.5);
  const i: N = floor(g).toVar(), f: N = g.sub(i).toVar();
  // per texel: the land's shadow height (as 0 … 65535), the roofs' above it (m), the trees' light
  const read = (dx: number, dz: number): N => {
    const t: N = textureLoad(shade.atlas.texture, ivec2(clamp(i.add(vec2(dx, dz)), 0, SHADE_SIZE - 1) as N));
    return vec3(t.r.mul(256).add(t.g).mul(255), t.b.mul(shade.roofStep), t.a);
  };
  const here: N = mix(mix(read(0, 0), read(1, 0), f.x), mix(read(0, 1), read(1, 1), f.x), f.y).toVar();
  const land: N = here.x.mul(scale.y.div(65535)).add(scale.x);
  // (level ground just clear of a shadow is one cell's drop above it: fully lit)
  const lit: N = smoothstep(0, 1, P.y.sub(vec2(land, land.add(here.y))).mul(scale.z).add(0.25));
  return mix(vec2(1, 1), vec2(lit.x, lit.y.mul(here.z)), scale.w);
}

/**
 * The sun's / moon's shadow on anything that takes shadows (`light.shadow.shadowNode`): the shadow map where it
 * reaches, darkened by the land's own shade (the map has no terrain in it), and towards the map's edge the baked
 * shade of land, roofs and trees instead, so that shadows do not end at a line some way ahead of the camera.
 */
export function keyShadowNode(light: THREE.DirectionalLight, shade: FarShade, map: KeyMapFrame): N {
  const P: N = positionWorld;
  const baked: N = bakedShade(shade, P).toVar();
  const rel: N = P.sub(uniform(map.at).setGroup(renderGroup));
  const off: N = max(abs(rel.dot(uniform(map.x).setGroup(renderGroup))), abs(rel.dot(uniform(map.y).setGroup(renderGroup)))).div(map.half);
  const inMap: N = smoothstep(float(1), float(1 - EDGE), off);
  return mix(baked.y, (shadow(light) as N).mul(baked.x), inMap);
}
