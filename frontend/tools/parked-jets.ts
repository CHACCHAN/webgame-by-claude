/**
 * The aircraft parked on Edwards' apron (render/parkedJets.ts), baked from the fighters' own models into one small
 * file: public/models/jets/parked.glb. Per type (a node named after its id, metres, nose +Z, ground at y = 0 with
 * the gear down, as the source) one mesh of two primitives: `parked-airframe` (the airframe, gear and nozzles; the
 * type's atlas at a quarter of its size in a slot of a shared 3072×1024 atlas: base colour, and occlusion /
 * roughness / metalness) and `parked-glass` (the canopy and the lamps' lenses: dark, colour per vertex). Each part is
 * simplified to 2 cm (meshoptimizer; the texture seams kept). No normal map, no lamps: from the course they are below
 * a pixel. The file records the stamp of each source model; a vitest fails when a model changed without this.
 *   npx tsx tools/parked-jets.ts            (after any change of public/models/jets/{f15c,f15j,su47}.glb)
 */
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import * as THREE from 'three';
import { Document, NodeIO, type Material, type Primitive } from '@gltf-transform/core';
import { ALL_EXTENSIONS, EXTTextureWebP } from '@gltf-transform/extensions';
import { meshopt, prune } from '@gltf-transform/functions';
import { MeshoptDecoder, MeshoptEncoder, MeshoptSimplifier } from 'meshoptimizer';
import sharp from 'sharp';
import { PARKED_FILE, PARKED_TYPES } from '../src/game/render/parkedJets';

const DIR = path.join(import.meta.dirname, '../public/models/jets');
/** one type's atlas in the shared one (px; the models' own are 2048) */
const SLOT = 1024;
/** geometric error allowed by the simplifier (m): under a pixel of a 1080-line screen from 30 m */
const ERROR = 0.02;
/** materials drawn from the atlas; the rest is glass and lenses */
const ATLAS_MATERIALS = new Set(['airframe', 'navlight_all']);

interface Part {
  pos: number[];
  normal: number[];
  color: number[];
  uv: number[];
  index: number[];
}
/** a picture put into the atlas at its slot */
interface Layer {
  input: Buffer;
  left: number;
  top: number;
}
const part = (): Part => ({ pos: [], normal: [], color: [], uv: [], index: [] });

/** the glass and the lamps' lenses, unlit: dark */
function glassTint(mat: Material | null): [number, number, number] {
  const c = mat?.getBaseColorFactor() ?? [0.02, 0.02, 0.02, 1];
  const k = mat?.getName() === 'glass' ? 1 : 0.45;
  return [c[0] * k, c[1] * k, c[2] * k];
}

async function main() {
  await Promise.all([MeshoptDecoder.ready, MeshoptEncoder.ready, MeshoptSimplifier.ready]);
  const io = new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({ 'meshopt.decoder': MeshoptDecoder, 'meshopt.encoder': MeshoptEncoder });
  const out = new Document();
  const buffer = out.createBuffer();
  const scene = out.createScene('parked');
  const sources: Record<string, string> = {};
  const baseLayers: Layer[] = [], ormLayers: Layer[] = [];
  const airMat = out.createMaterial('parked-airframe').setBaseColorFactor([1, 1, 1, 1]).setMetallicFactor(1).setRoughnessFactor(1);
  const glassMat = out.createMaterial('parked-glass').setBaseColorFactor([1, 1, 1, 1]).setMetallicFactor(0).setRoughnessFactor(0.14);
  for (const [slot, id] of PARKED_TYPES.entries()) {
    const file = path.join(DIR, `${id}.glb`);
    const bytes = fs.readFileSync(file);
    sources[id] = crypto.createHash('sha1').update(bytes).digest('hex').slice(0, 8);
    const doc = await io.readBinary(new Uint8Array(bytes));
    const air = part(), glass = part();
    let atlas: Material | null = null;
    for (const node of doc.getRoot().listNodes()) {
      const mesh = node.getMesh();
      if (!mesh) continue;
      const m = new THREE.Matrix4().fromArray(node.getWorldMatrix());
      const nm = new THREE.Matrix3().getNormalMatrix(m);
      // (a mirrored node turns its triangles inside out)
      const flip = m.determinant() < 0;
      for (const prim of mesh.listPrimitives()) add(prim, m, nm, flip);
    }
    function add(prim: Primitive, m: THREE.Matrix4, nm: THREE.Matrix3, flip: boolean) {
      const mat = prim.getMaterial();
      const P = prim.getAttribute('POSITION'), N = prim.getAttribute('NORMAL'), U = prim.getAttribute('TEXCOORD_0'), C = prim.getAttribute('COLOR_0');
      if (!P || !N) return;
      const onAtlas = ATLAS_MATERIALS.has(mat?.getName() ?? '') && !!U && !!mat?.getBaseColorTexture();
      if (mat?.getName() === 'airframe' && mat.getBaseColorTexture()) atlas ??= mat;
      const b = onAtlas ? air : glass;
      const tint = onAtlas ? null : glassTint(mat);
      const base = b.pos.length / 3, v = new THREE.Vector3(), e: number[] = [];
      for (let i = 0; i < P.getCount(); i++) {
        v.fromArray(P.getElement(i, e)).applyMatrix4(m);
        b.pos.push(v.x, v.y, v.z);
        v.fromArray(N.getElement(i, e)).applyMatrix3(nm).normalize();
        b.normal.push(v.x, v.y, v.z);
        if (tint) b.color.push(...tint);
        else if (C) {
          C.getElement(i, e);
          b.color.push(e[0], e[1], e[2]);
        } else b.color.push(1, 1, 1);
        if (onAtlas) {
          U!.getElement(i, e);
          b.uv.push((slot + Math.min(1, Math.max(0, e[0]))) / PARKED_TYPES.length, e[1]);
        }
      }
      const I = prim.getIndices();
      const n = I ? I.getCount() : P.getCount();
      for (let k = 0; k + 2 < n; k += 3) {
        const a = I ? I.getScalar(k) : k, b1 = I ? I.getScalar(k + 1) : k + 1, c = I ? I.getScalar(k + 2) : k + 2;
        b.index.push(base + a, base + (flip ? c : b1), base + (flip ? b1 : c));
      }
    }
    if (!atlas) throw new Error(`${id}: no airframe atlas`);
    const atlasMat: Material = atlas;
    const node = out.createNode(id);
    const mesh = out.createMesh(id);
    for (const [p, mat, name] of [[air, airMat, 'airframe'], [glass, glassMat, 'glass']] as const) {
      const prim = primitive(out, buffer, p, name === 'airframe');
      if (!prim) continue;
      prim.setMaterial(mat);
      mesh.addPrimitive(prim);
      console.log(id, name, 'triangles', prim.getIndices()!.getCount() / 3, 'of', p.index.length / 3);
    }
    node.setMesh(mesh);
    scene.addChild(node);
    // the atlases' slots: base colour; occlusion / roughness / metalness (no occlusion map: the red channel is none)
    const at = { left: slot * SLOT, top: 0 };
    const baseTex = atlasMat.getBaseColorTexture()!;
    baseLayers.push({ input: await sharp(Buffer.from(baseTex.getImage()!)).resize(SLOT, SLOT, { kernel: 'lanczos3' }).png().toBuffer(), ...at });
    const mr = atlasMat.getMetallicRoughnessTexture();
    let orm: Buffer;
    if (mr) {
      const { data, info } = await sharp(Buffer.from(mr.getImage()!)).resize(SLOT, SLOT, { kernel: 'lanczos3' }).removeAlpha().raw().toBuffer({ resolveWithObject: true });
      const occ = atlasMat.getOcclusionTexture();
      if (occ && occ !== mr) throw new Error(`${id}: occlusion in its own texture (not handled)`);
      if (!occ) for (let k = 0; k < data.length; k += info.channels) data[k] = 255;
      orm = await sharp(data, { raw: { width: SLOT, height: SLOT, channels: info.channels } }).png().toBuffer();
    } else {
      const r = Math.round(atlasMat.getRoughnessFactor() * 255), mt = Math.round(atlasMat.getMetallicFactor() * 255);
      orm = await sharp({ create: { width: SLOT, height: SLOT, channels: 3, background: { r: 255, g: r, b: mt } } }).png().toBuffer();
    }
    ormLayers.push({ input: orm, ...at });
  }
  const sheet = (layers: Layer[], quality: number) =>
    sharp({ create: { width: SLOT * PARKED_TYPES.length, height: SLOT, channels: 3, background: { r: 128, g: 128, b: 128 } } }).composite(layers).webp({ quality }).toBuffer();
  out.createExtension(EXTTextureWebP).setRequired(true);
  const base = out.createTexture('parked-base').setImage(new Uint8Array(await sheet(baseLayers, 90))).setMimeType('image/webp');
  const orm = out.createTexture('parked-orm').setImage(new Uint8Array(await sheet(ormLayers, 92))).setMimeType('image/webp');
  airMat.setBaseColorTexture(base).setOcclusionTexture(orm).setMetallicRoughnessTexture(orm);
  out.getRoot().setExtras({ sources });
  await out.transform(prune({ keepAttributes: true }), meshopt({ encoder: MeshoptEncoder, level: 'medium' }));
  const file = path.join(DIR, PARKED_FILE);
  await io.write(file, out);
  console.log(file, fs.statSync(file).size, 'bytes; sources', JSON.stringify(sources));
}

/** one part, simplified and compacted, as a primitive */
function primitive(doc: Document, buffer: ReturnType<Document['createBuffer']>, p: Part, uv: boolean): Primitive | null {
  if (p.index.length < 3) return null;
  const pos = new Float32Array(p.pos);
  const index = MeshoptSimplifier.simplify(new Uint32Array(p.index), pos, 3, 0, ERROR, ['ErrorAbsolute', 'Prune'])[0];
  if (index.length < 3) return null;
  const remap = new Int32Array(pos.length / 3).fill(-1);
  let n = 0;
  for (let k = 0; k < index.length; k++) {
    if (remap[index[k]] < 0) remap[index[k]] = n++;
    index[k] = remap[index[k]];
  }
  const take = (src: number[], size: number) => {
    const a = new Float32Array(n * size);
    for (let i = 0; i < remap.length; i++) if (remap[i] >= 0) for (let c = 0; c < size; c++) a[remap[i] * size + c] = src[i * size + c];
    return a;
  };
  const acc = (a: Float32Array<ArrayBuffer> | Uint32Array<ArrayBuffer>, type: 'VEC3' | 'VEC2' | 'SCALAR') => doc.createAccessor().setArray(a).setType(type).setBuffer(buffer);
  const prim = doc
    .createPrimitive()
    .setAttribute('POSITION', acc(take(p.pos, 3), 'VEC3'))
    .setAttribute('NORMAL', acc(take(p.normal, 3), 'VEC3'))
    .setAttribute('COLOR_0', acc(take(p.color, 3), 'VEC3'))
    .setIndices(acc(new Uint32Array(index), 'SCALAR'));
  if (uv) prim.setAttribute('TEXCOORD_0', acc(take(p.uv, 2), 'VEC2'));
  return prim;
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
