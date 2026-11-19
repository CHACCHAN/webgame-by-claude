import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { PARKED_FILE, PARKED_TYPES } from './parkedJets';

const file = (name: string) => fileURLToPath(new URL(`../../../public/models/jets/${name}`, import.meta.url));

/** the JSON chunk of a GLB */
function gltfJson(bytes: Buffer) {
  const length = bytes.readUInt32LE(12);
  return JSON.parse(bytes.subarray(20, 20 + length).toString('utf8'));
}

// Edwards' parked aircraft are baked from the fighters' models by tools/parked-jets.ts: a model changed without baking
// them again would leave the apron with the old aircraft.
describe('the parked aircraft', () => {
  const json = gltfJson(readFileSync(file(PARKED_FILE)));
  it('are baked from the models as they are now', () => {
    const sources = json.extras?.sources ?? {};
    for (const id of PARKED_TYPES) expect(sources[id], `${id}: run npx tsx tools/parked-jets.ts`).toBe(createHash('sha1').update(readFileSync(file(`${id}.glb`))).digest('hex').slice(0, 8));
  });
  it('hold every type, with its airframe and glass', () => {
    const nodes = (json.nodes ?? []) as { name: string; mesh?: number }[];
    for (const id of PARKED_TYPES) {
      const node = nodes.find((n) => n.name === id);
      expect(node?.mesh, id).toBeTypeOf('number');
      const mats = json.meshes[node!.mesh!].primitives.map((p: { material: number }) => json.materials[p.material].name);
      expect(mats, id).toEqual(['parked-airframe', 'parked-glass']);
    }
  });
});
