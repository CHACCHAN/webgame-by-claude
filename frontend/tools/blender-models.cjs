// Our own 3D models, built from numbers by Python scripts in Blender (tools/blender/) and optimised for the game:
//   node tools/blender-models.cjs trains [ids]   tools/blender/<id>.py        → public/models/trains/<id>.glb
//   node tools/blender-models.cjs cars [ids]     tools/blender/cars/<id>.py   → public/models/cars/<id>.glb
//   node tools/blender-models.cjs bikes [ids]    tools/blender/bikes/<id>.py  → public/models/bikes/<id>.glb
//   node tools/blender-models.cjs props [ids]    tools/blender/props/<id>.py  → public/models/props/<id>.glb
//   node tools/blender-models.cjs roadside [ids] tools/blender/roadside/<id>.py → public/models/roadside/<id>.glb
//   node tools/blender-models.cjs creatures      tools/blender/creatures/roach.py → public/models/roach/roach.glb
//   node tools/blender-models.cjs jets [ids]     tools/blender/jets/<id>.py   → public/models/jets/<id>.glb
//   node tools/blender-models.cjs tanks [ids]    tools/blender/tanks/<id>.py  → public/models/tanks/<id>.glb
//   node tools/blender-models.cjs nature [ids]   tools/blender/nature/<id>.py → public/models/nature/<id>.glb + <id>.lite.glb
//   … --render [dir]   also renders each model's check views with its script (default dir: /tmp/<id>-render)
// A train's line variants (`variants`: the same model painted and signed for another line, `Livery.variant` in
// vehicle/trains.ts) are built by the same script with `--variant <name>` → <id>-<name>.glb.
// BLENDER=<path> picks the Blender binary (default: `blender` on PATH; tested with 5.2 LTS). Without ids, all of a kind
// (KINDS[kind].ids).
//
// Optimisation (glTF-Transform): meshopt geometry, one mesh per material per node, WebP textures. Trains also merge
// their solid-colour materials into palette textures (the game keeps a train's materials as they are); cars and props
// keep every material, since the game swaps some of them by name (paint, glass, lamps, …). A creature's skinned
// animation is resampled (keys on straight runs dropped).
const fs = require('fs');
const os = require('os');
const path = require('path');
const { execFileSync } = require('child_process');

// ids: what a kind builds by default; outDir: the script's --out takes a folder and writes <id>.glb into it;
// joinNamed: merge sibling meshes even when named (a train's car parts), else named nodes stay apart (a turbine's
// rotor, a car's exhaust found by its mesh name)
const KINDS = {
  trains: {
    dir: 'tools/blender', out: 'public/models/trains', palette: true, joinNamed: true, textureSize: 2048, big: { led: 4096 },
    ids: ['e231', 'e235', 'keikyu1000', 'tobu30000', 'e5', 'l0'],
    variants: { e231: ['sobu', 'joban', 'tozai', 'kinkou'], e235: ['sobu', 'chuosobu'], tobu30000: ['isesaki'], e5: ['h5'] },
  },
  cars: { dir: 'tools/blender/cars', out: 'public/models/cars', palette: false, textureSize: 1024, big: {}, ids: ['hayate', 'raijin', 'shiden', 'supra', 'r34', 's15', 'cybertruck', 'u9', 'su7'] },
  // the motorcycles: nodes steer / spin_f / spin_r stay apart (render/BikeModel.ts turns and spins them)
  bikes: { dir: 'tools/blender/bikes', out: 'public/models/bikes', palette: false, textureSize: 1024, big: {}, ids: ['nsr250r', 'ninjah2', 'hayabusa'] },
  // (a prop's script bakes each of its textures at the size it should have, 2048 px at most: tools/blender/props/prop_bake.py)
  props: {
    dir: 'tools/blender/props', out: 'public/models/props', palette: false, textureSize: 2048, big: {}, outDir: true,
    ids: [
      'street_light', 'wind_turbine', 'curve_mirror', 'vending_machine', 'torii', 'stone_lantern', 'bus_stop', 'traffic_cone',
      // the autobahn's (their textures and the sign atlas: tools/blender/props/paint_autobahn.py)
      'sign_gantry', 'emergency_phone', 'village_house', 'village_farmhouse', 'village_church',
    ],
  },
  // what stands along the road in modules (render/roadside.ts lays them out; materials are swapped by name)
  roadside: {
    dir: 'tools/blender/roadside', out: 'public/models/roadside', palette: false, textureSize: 512, big: {}, outDir: true,
    ids: ['guardrail', 'guardrail_end', 'delineator', 'gutter_grate', 'rockfall_fence'],
  },
  // the fighters (render/JetModel.ts: named nodes for gear, nozzles and moving surfaces stay apart; one atlas each)
  jets: { dir: 'tools/blender/jets', out: 'public/models/jets', palette: false, textureSize: 2048, big: {}, ids: ['f15j', 'f15c', 'su47'], variants: { f15j: ['dj'], f15c: ['d'] } },
  // the tanks (render/TankModel.ts: body / turret / gun / roll_* nodes stay apart; one atlas `armor` each, the tracks'
  // own small texture under track_l / track_r; tools/blender/tanks/tank_kit.py)
  // (uniqueNames: materials of different names stay apart: track_l and track_r are the same material twice, and the game
  // tells the two tracks apart by name)
  tanks: { dir: 'tools/blender/tanks', out: 'public/models/tanks', palette: false, textureSize: 2048, big: {}, uniqueNames: true, ids: ['type10'] },
  creatures: { dir: 'tools/blender/creatures', out: 'public/models/roach', palette: false, textureSize: 1024, big: {}, resample: true, ids: ['roach'] },
  // trees, bushes, undergrowth, rocks (tools/blender/nature/nature_kit.py): the script writes the geometry (every level
  // of detail a node) and its textures as PNG files next to it, which `textures` puts into the materials by name
  // (`<id>_<file>.png`; the normal maps carry a mask in their alpha, which Blender's exporter would drop). `lite`:
  // a second GLB for the medium quality without the nodes matching `drop` and with the textures at half size.
  nature: {
    dir: 'tools/blender/nature', out: 'public/models/nature', palette: false, textureSize: 2048, big: {},
    textures: { foliage: { base: 'leaf', normal: 'leaf_n', mask: true }, impostor: { base: 'imp', normal: 'imp_n', mask: true }, rock: { base: 'rock', normal: 'rock_n' } },
    lite: { drop: /_lod0$/, scale: 0.5 },
    // (the small plants' sprites are seen from a few metres at most)
    sizes: { kusa: 512, susuki: 512, shida: 512, sasa: 512 },
    ids: ['sugi', 'hinoki', 'buna', 'akamatsu', 'fichte', 'birke', 'yabu', 'sasa', 'shida', 'kusa', 'susuki', 'iwa'],
  },
};

const args = process.argv.slice(2);
const kind = KINDS[args[0]];
if (!kind) throw new Error(`usage: node tools/blender-models.cjs <${Object.keys(KINDS).join('|')}> [ids] [--render [dir]]`);
const named = args[1] && !args[1].startsWith('--') ? args[1].split(',') : null;
const ids = named ?? kind.ids;
const renderAt = args.indexOf('--render');
const renderDir = renderAt < 0 ? null : args[renderAt + 1] && !args[renderAt + 1].startsWith('--') ? args[renderAt + 1] : '';
const blender = process.env.BLENDER || 'blender';
const build = (script, extra) =>
  execFileSync(blender, ['-t', '4', '--background', '--factory-startup', '--python', script, '--', ...extra], { stdio: 'pipe', maxBuffer: 64 << 20 });

/**
 * Blender's glTF exporter lists the materials and a mesh's primitives in an order that changes from run to run (the
 * geometry does not): sort both by material name, so rebuilding an unchanged script gives the same GLB.
 */
function sortByMaterial(doc) {
  const root = doc.getRoot();
  const byName = (a, b) => (a.getName() < b.getName() ? -1 : a.getName() > b.getName() ? 1 : 0);
  // re-create the materials in name order (the root keeps them in creation order)
  for (const old of [...root.listMaterials()].sort(byName)) {
    const copy = old.clone();
    for (const parent of old.listParents()) if (parent !== root) parent.swap(old, copy);
    old.dispose();
  }
  const key = (p) => p.getMaterial()?.getName() ?? '';
  for (const mesh of root.listMeshes()) {
    const prims = mesh.listPrimitives();
    for (const p of prims) mesh.removePrimitive(p);
    for (const p of prims.sort((a, b) => (key(a) < key(b) ? -1 : key(a) > key(b) ? 1 : 0))) {
      sortTriangles(p);
      mesh.addPrimitive(p);
    }
  }
}

/** the exporter's triangle order also varies a little between runs (same triangles): put them in index order */
function sortTriangles(prim) {
  const acc = prim.getIndices();
  if (!acc || prim.getMode() !== 4) return;
  const ix = acc.getArray();
  const tris = [];
  for (let k = 0; k + 2 < ix.length; k += 3) {
    const t = [ix[k], ix[k + 1], ix[k + 2]];
    const r = t.indexOf(Math.min(...t)); // rotate the lowest index first (keeps the winding)
    tris.push([t[r], t[(r + 1) % 3], t[(r + 2) % 3]]);
  }
  tris.sort((a, b) => a[0] - b[0] || a[1] - b[1] || a[2] - b[2]);
  const out = new ix.constructor(ix.length);
  tris.forEach((t, k) => out.set(t, k * 3));
  acc.setArray(out);
}

/** the PNG files a nature script left next to its GLB, into the materials that are named for them */
function addTextures(doc, raw, id) {
  const dir = path.dirname(raw);
  for (const mat of doc.getRoot().listMaterials()) {
    const def = kind.textures[mat.getName()];
    if (!def) continue;
    const tex = (name) => {
      const file = path.join(dir, `${id}_${name}.png`);
      if (!fs.existsSync(file)) throw new Error(`no ${file} for the material ${mat.getName()}`);
      return doc.createTexture(`${id}_${name}`).setImage(fs.readFileSync(file)).setMimeType('image/png');
    };
    mat.setBaseColorTexture(tex(def.base)).setBaseColorFactor([1, 1, 1, 1]).setMetallicFactor(0).setRoughnessFactor(0.8);
    if (def.normal) mat.setNormalTexture(tex(def.normal));
    if (def.mask) mat.setAlphaMode('MASK').setAlphaCutoff(0.5).setDoubleSided(true);
  }
}

/** the same model for the medium quality: without the heaviest level of detail, textures at `scale` */
async function writeLite(io, doc, out) {
  const sharp = require('sharp');
  const F = require('@gltf-transform/functions');
  const { MeshoptEncoder } = require('meshoptimizer');
  for (const node of doc.getRoot().listNodes()) if (kind.lite.drop.test(node.getName())) node.dispose();
  for (const tex of doc.getRoot().listTextures()) {
    const [w, h] = tex.getSize();
    const buf = await sharp(Buffer.from(tex.getImage())).resize(Math.round(w * kind.lite.scale), Math.round(h * kind.lite.scale)).webp({ quality: 88 }).toBuffer();
    tex.setImage(buf).setMimeType('image/webp');
  }
  await doc.transform(F.prune({ keepAttributes: true }), F.meshopt({ encoder: MeshoptEncoder, level: 'high' }));
  await io.write(out, doc);
}

async function optimise(raw, out, id) {
  const { NodeIO } = require('@gltf-transform/core');
  const { ALL_EXTENSIONS } = require('@gltf-transform/extensions');
  const F = require('@gltf-transform/functions');
  const { MeshoptEncoder } = require('meshoptimizer');
  const sharp = require('sharp');
  await MeshoptEncoder.ready;
  const io = new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({ 'meshopt.encoder': MeshoptEncoder });
  const doc = await io.read(raw);
  sortByMaterial(doc);
  if (kind.textures) addTextures(doc, raw, id);
  // no accessor dedup before quantisation: two parts of identical geometry (a train's two end cars) would become one
  // mesh shared by both nodes, and join + quantize then distort it (the L0's end cars came out squashed). meshopt's
  // own cleanup still shares identical buffers once they are quantised.
  const { PropertyType } = require('@gltf-transform/core');
  const steps = kind.uniqueNames
    ? [F.dedup({ propertyTypes: [PropertyType.MESH, PropertyType.TEXTURE, PropertyType.SKIN] }), F.dedup({ propertyTypes: [PropertyType.MATERIAL], keepUniqueNames: true })]
    : [F.dedup({ propertyTypes: [PropertyType.MESH, PropertyType.TEXTURE, PropertyType.MATERIAL, PropertyType.SKIN] })];
  if (kind.resample) steps.push(F.resample());
  if (kind.palette) steps.push(F.palette({ min: 5 }));
  steps.push(F.join({ keepNamed: !kind.joinNamed }), F.weld(), F.prune(kind.textures ? { keepAttributes: true } : {}), F.sparse());
  // the palettes lossless (lossy WebP smears neighbouring colour blocks into each other), the rest as good-quality WebP
  // (a pattern is tried on the name and on the URI, which is empty for embedded images: never match an empty string)
  const big = Object.keys(kind.big);
  for (const [name, size] of Object.entries(kind.big)) {
    steps.push(F.textureCompress({ encoder: sharp, targetFormat: 'webp', pattern: new RegExp(`^${name}(\\.|$)`), resize: [size, size], quality: 92 }));
  }
  const others = new RegExp(`^(?!(${['Palette', ...big].join('|')})(\\.|$|[A-Z0-9]))..*$`);
  steps.push(F.textureCompress({ encoder: sharp, targetFormat: 'webp', pattern: others, resize: [kind.sizes?.[id] ?? kind.textureSize, kind.sizes?.[id] ?? kind.textureSize], quality: 90 }));
  if (kind.palette) steps.push(F.textureCompress({ encoder: sharp, targetFormat: 'webp', pattern: /^Palette/, lossless: true }));
  steps.push(F.meshopt({ encoder: MeshoptEncoder, level: 'high' }));
  await doc.transform(...steps);
  await io.write(out, doc);
  if (kind.lite) {
    const lite = out.replace(/\.glb$/, '.lite.glb');
    await writeLite(io, doc, lite);
    console.log(lite, fs.statSync(lite).size, 'bytes');
  }
}

(async () => {
  for (const id of ids) {
    const script = path.join(kind.dir, `${id}.py`);
    if (!fs.existsSync(script)) throw new Error(`no ${script}`);
    // the model, then its line variants
    for (const variant of [null, ...(kind.variants?.[id] ?? [])]) {
      const name = variant ? `${id}-${variant}` : id;
      const tmp = fs.mkdtempSync(path.join(os.tmpdir(), `${name}-`));
      const raw = kind.outDir ? path.join(tmp, `${id}.glb`) : path.join(tmp, `${name}.raw.glb`);
      // (a nature script renders its sheet from what it has just built: in the same run)
      const sheet = kind.textures && renderDir !== null ? ['--render', path.resolve(renderDir || path.join(os.tmpdir(), `${id}-render`))] : [];
      const log = build(script, [...(variant ? ['--variant', variant] : []), '--out', kind.outDir ? tmp : raw, ...sheet]).toString();
      for (const line of log.split('\n')) if (/^(TRIS|MATERIALS|PROP|NATURE|SHEET)/.test(line)) console.log(`  ${line}`);
      const out = path.join(kind.out, `${name}.glb`);
      fs.mkdirSync(kind.out, { recursive: true });
      await optimise(raw, out, id);
      fs.rmSync(tmp, { recursive: true, force: true });
      console.log(out, fs.statSync(out).size, 'bytes');
    }
    if (renderDir !== null && !kind.textures) {
      const dir = path.resolve(renderDir || path.join(os.tmpdir(), `${id}-render`), renderDir ? id : '');
      fs.mkdirSync(dir, { recursive: true });
      build(script, ['--render', dir]);
      console.log('  renders in', dir);
    }
  }
})();
