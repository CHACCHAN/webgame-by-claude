import type * as THREE from 'three';
import type { WebGPURenderer } from 'three/webgpu';

type Stored = { buffer?: { destroy(): void } };
type Backend = {
  isWebGPUBackend?: boolean;
  get(o: object): Stored;
  delete(o: object): void;
  attributeUtils?: { destroyAttribute(attribute: THREE.BufferAttribute | THREE.InterleavedBufferAttribute): void };
};

/**
 * three.js 0.186, WebGPU backend: freeing an interleaved attribute (`geometry.dispose()`; every meshopt GLB has
 * them) destroys the GPU buffer but keeps the destroyed buffer on the shared `InterleavedBuffer`, and the next
 * object drawn with that geometry gets it back. A model's clones share their geometry, so the car picked in the
 * garage came up on the grid with destroyed buffers: WebGPU then refuses the whole frame, every frame (the picture
 * stood still on the garage). The WebGL 2 backend forgets the shared buffer; this makes the WebGPU one do the same.
 */
export function fixInterleavedDispose(renderer: WebGPURenderer) {
  const backend = renderer.backend as unknown as Backend;
  const utils = backend.attributeUtils;
  if (!backend.isWebGPUBackend || !utils) return;
  utils.destroyAttribute = (attribute) => {
    const shared = (attribute as THREE.InterleavedBufferAttribute).isInterleavedBufferAttribute ? (attribute as THREE.InterleavedBufferAttribute).data : attribute;
    // the attributes of one interleaved buffer arrive one after the other: the buffer is gone after the first
    backend.get(shared).buffer?.destroy();
    backend.delete(shared);
    backend.delete(attribute);
  };
}

type BuiltShader = { usedTimes: number };
type NodeManager = { get(o: object): { nodeBuilderState?: BuiltShader }; delete(o: object): unknown };
type RenderObjectLike = { isRenderObject?: boolean; object?: THREE.Object3D & { count?: number; isBatchedMesh?: boolean }; geometry?: THREE.BufferGeometry };
type Pipelines = { _releasePipeline?: (p: unknown) => void; _releaseProgram?: (p: unknown) => void };

/**
 * Built shaders are kept. three.js counts the objects drawn with a shader (a material's shape × a geometry's layout
 * × the lights) and throws the built shader away with the last of them: a car taken out of the garage took its
 * 22–32 shaders along, and the next car, or the same one again, built them all anew in one frame (~0.5 s, every
 * time a car was shown and at every race start). One use that never ends keeps them; the GPU's pipelines and shader
 * modules likewise. What can pile up is bounded by the shapes of material the game has: shaders whose key names
 * one object (an `InstancedMesh`, morph targets) are left to three.js, or every course's trees would stay.
 */
export function keepShaders(renderer: WebGPURenderer) {
  const inner = renderer as unknown as { _nodes?: NodeManager; _pipelines?: Pipelines };
  const nodes = inner._nodes;
  if (nodes && typeof nodes.delete === 'function' && typeof nodes.get === 'function') {
    const drop = nodes.delete.bind(nodes);
    nodes.delete = (o: object) => {
      const ro = o as RenderObjectLike;
      if (ro.isRenderObject && ro.object) {
        const own = (ro.object as THREE.InstancedMesh).isInstancedMesh || (ro.object.count ?? 1) > 1 || ro.object.isBatchedMesh || Object.keys(ro.geometry?.morphAttributes ?? {}).length > 0;
        const state = nodes.get(o).nodeBuilderState;
        if (!own && state && state.usedTimes === 1) state.usedTimes++;
      }
      return drop(o);
    };
  }
  const pipelines = inner._pipelines;
  if (pipelines?._releasePipeline && pipelines._releaseProgram) {
    pipelines._releasePipeline = () => {};
    pipelines._releaseProgram = () => {};
  }
}
