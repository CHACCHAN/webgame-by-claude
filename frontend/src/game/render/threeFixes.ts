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
