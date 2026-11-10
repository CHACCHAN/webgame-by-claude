import { dot, float, floor, fract, mix, sin, vec2 } from 'three/tsl';
import type { Node } from 'three/webgpu';

export type Float = Node<'float'>;
export type Vec2 = Node<'vec2'>;
export type Vec3 = Node<'vec3'>;
export type Vec4 = Node<'vec4'>;

/** 0..1 hash of a 2D cell */
export const hash2 = (p: Vec2): Float => fract(sin(dot(p, vec2(127.1, 311.7))).mul(43758.5453));

/** 0..1 hash of a 3D cell */
export const hash3 = (p: Vec3): Float => {
  const q = fract(p.mul(0.3183099).add(0.1)).mul(17);
  return fract(q.x.mul(q.y).mul(q.z).mul(q.x.add(q.y).add(q.z)));
};

/** smooth value noise, 0..1 */
export const vnoise = (p: Vec2): Float => {
  const i = floor(p).toVar();
  const f0 = fract(p).toVar();
  const f = f0.mul(f0).mul(f0.mul(-2).add(3)).toVar();
  return mix(mix(hash2(i), hash2(i.add(vec2(1, 0))), f.x), mix(hash2(i.add(vec2(0, 1))), hash2(i.add(vec2(1, 1))), f.x), f.y);
};

/** fractal sum of `octaves` value noises (each `lacunarity` times finer and half as strong) */
export function fbm(p: Vec2, octaves: number, lacunarity: number): Float {
  let sum: Float = float(0);
  let q = p;
  let a = 0.5;
  for (let i = 0; i < octaves; i++) {
    sum = sum.add(vnoise(q).mul(a));
    q = q.mul(lacunarity);
    a *= 0.5;
  }
  return sum;
}
