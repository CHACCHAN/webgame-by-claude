import * as THREE from 'three';
import { SpriteNodeMaterial } from 'three/webgpu';
import { instancedDynamicBufferAttribute } from 'three/tsl';
import type { Float, Vec3 } from '../render/tslNoise';

/**
 * World size of a particle per unit of `size`. The particles used to be GL points of `size × 0.55 × viewport height
 * / distance` pixels; at the camera's 60° field of view that is this many metres across.
 */
const SIZE_TO_WORLD = 0.55 / (2 * Math.tan(Math.PI / 6)) * 2;

/**
 * A pool of camera-facing particles drawn in one call (instanced quads: WebGPU has no sized points). The arrays hold
 * each particle's position (world), size and alpha; `commit()` uploads them after a change. The caller gives the
 * material its colour and opacity from `nodes`.
 */
export interface SpritePool {
  readonly object: THREE.Sprite;
  readonly material: SpriteNodeMaterial;
  readonly pos: Float32Array;
  readonly size: Float32Array;
  readonly alpha: Float32Array;
  readonly nodes: { pos: Vec3; size: Float; alpha: Float };
  commit(): void;
}

export function makeSpritePool(n: number, opts: { additive?: boolean; fog?: boolean } = {}): SpritePool {
  const pos = new Float32Array(n * 3), size = new Float32Array(n), alpha = new Float32Array(n);
  const attrs = [new THREE.InstancedBufferAttribute(pos, 3), new THREE.InstancedBufferAttribute(size, 1), new THREE.InstancedBufferAttribute(alpha, 1)];
  for (const a of attrs) a.setUsage(THREE.DynamicDrawUsage);
  const nodes = {
    pos: instancedDynamicBufferAttribute(attrs[0], 'vec3') as unknown as Vec3,
    size: instancedDynamicBufferAttribute(attrs[1], 'float') as unknown as Float,
    alpha: instancedDynamicBufferAttribute(attrs[2], 'float') as unknown as Float,
  };
  const material = new SpriteNodeMaterial({ transparent: true, depthWrite: false, fog: opts.fog ?? true });
  if (opts.additive) material.blending = THREE.AdditiveBlending;
  material.positionNode = nodes.pos;
  material.scaleNode = nodes.size.mul(SIZE_TO_WORLD);
  const object = new THREE.Sprite(material as unknown as THREE.SpriteMaterial);
  object.count = n;
  object.frustumCulled = false;
  return {
    object, material, pos, size, alpha, nodes,
    commit() {
      for (const a of attrs) a.needsUpdate = true;
    },
  };
}
