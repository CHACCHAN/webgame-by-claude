import * as THREE from 'three';

/**
 * Roughly what the objects under `roots` hold on the GPU (bytes): their geometry buffers and their materials'
 * textures, each counted once. A browser does not tell a page how much video memory there is or how much it uses,
 * so what is kept built (`Game.keepBudget`) is counted by this estimate.
 */
export function gpuBytes(...roots: THREE.Object3D[]): number {
  const buffers = new Set<ArrayBufferLike>();
  const textures = new Set<THREE.Texture>();
  let bytes = 0;
  const array = (a: { array?: ArrayLike<number> & { buffer?: ArrayBufferLike; byteLength?: number } } | null | undefined) => {
    const buf = a?.array?.buffer;
    if (!buf || buffers.has(buf)) return;
    buffers.add(buf);
    bytes += a!.array!.byteLength ?? 0;
  };
  for (const root of roots) {
    root.traverse((o) => {
      const m = o as THREE.Mesh;
      if (!m.geometry) return;
      for (const attr of Object.values(m.geometry.attributes)) {
        // (an interleaved attribute's numbers live in its buffer's array)
        array((attr as THREE.InterleavedBufferAttribute).isInterleavedBufferAttribute ? (attr as THREE.InterleavedBufferAttribute).data : (attr as THREE.BufferAttribute));
      }
      array(m.geometry.index);
      const inst = o as THREE.InstancedMesh;
      if (inst.isInstancedMesh) {
        array(inst.instanceMatrix);
        array(inst.instanceColor);
      }
      for (const mat of Array.isArray(m.material) ? m.material : [m.material]) {
        if (!mat) continue;
        for (const v of Object.values(mat)) if (v instanceof THREE.Texture) textures.add(v);
      }
    });
  }
  for (const t of textures) {
    const img = t.image as { width?: number; height?: number } | undefined;
    const mips = t.mipmaps as { data?: { byteLength: number } }[] | undefined;
    if (mips?.length && mips[0].data) bytes += mips.reduce((s, m) => s + (m.data?.byteLength ?? 0), 0);
    else if (img?.width && img.height) bytes += img.width * img.height * 4 * (t.generateMipmaps ? 4 / 3 : 1);
  }
  return bytes;
}
