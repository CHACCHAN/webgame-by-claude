import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { MeshoptDecoder } from 'three/examples/jsm/libs/meshopt_decoder.module.js';
import { registerCarTemplate } from './CarModel';
import type { CarId } from '../vehicle/carSpecs';

/**
 * Loads the car GLBs from /models/cars/<id>.glb. Missing or broken files are
 * skipped silently and the procedural builder is used instead.
 */
export async function loadCarTemplates(ids: CarId[]) {
  const loader = new GLTFLoader();
  loader.setMeshoptDecoder(MeshoptDecoder);
  const loaded: CarId[] = [];
  await Promise.all(
    ids.map(async (id) => {
      const url = `/models/cars/${id}.glb`;
      try {
        const head = await fetch(url, { method: 'HEAD' });
        const type = head.headers.get('content-type') ?? '';
        if (!head.ok || type.includes('text/html')) return;
        const gltf = await loader.loadAsync(url);
        registerCarTemplate(id, gltf.scene);
        loaded.push(id);
      } catch (e) {
        console.warn(`car model ${id} unavailable, using procedural fallback`, e);
      }
    }),
  );
  return loaded;
}
