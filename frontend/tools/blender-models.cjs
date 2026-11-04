// Our own 3D models, built from numbers by Python scripts in Blender (tools/blender/) and optimised for the game:
//   node tools/blender-models.cjs trains [ids]   tools/blender/<id>.py        → public/models/trains/<id>.glb
//   node tools/blender-models.cjs cars [ids]     tools/blender/cars/<id>.py   → public/models/cars/<id>.glb
//   node tools/blender-models.cjs props [ids]    tools/blender/props/<id>.py  → public/models/props/<id>.glb
//   node tools/blender-models.cjs creatures      tools/blender/creatures/roach.py → public/models/roach/roach.glb
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
    ids: ['e231', 'e235', 'keikyu1000', 'tobu30000', 'e5'],
    variants: { e231: ['sobu', 'joban', 'tozai'], e235: ['sobu', 'chuosobu'], tobu30000: ['isesaki'], e5: ['h5'] },
  },
  cars: { dir: 'tools/blender/cars', out: 'public/models/cars', palette: false, textureSize: 1024, big: {}, ids: ['hayate', 'raijin', 'shiden', 'supra', 'r34', 's15'] },
  props: {
    dir: 'tools/blender/props', out: 'public/models/props', palette: false, textureSize: 1024, big: {}, outDir: true,
    ids: ['street_light', 'wind_turbine', 'curve_mirror', 'vending_machine', 'torii', 'stone_lantern', 'bus_stop', 'traffic_cone'],
  },
  creatures: { dir: 'tools/blender/creatures', out: 'public/models/roach', palette: false, textureSize: 1024, big: {}, resample: true, ids: ['roach'] },
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

async function optimise(raw, out) {
  const { NodeIO } = require('@gltf-transform/core');
  const { ALL_EXTENSIONS } = require('@gltf-transform/extensions');
  const F = require('@gltf-transform/functions');
  const { MeshoptEncoder } = require('meshoptimizer');
  const sharp = require('sharp');
  await MeshoptEncoder.ready;
  const io = new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({ 'meshopt.encoder': MeshoptEncoder });
  const doc = await io.read(raw);
  sortByMaterial(doc);
  const steps = [F.dedup()];
  if (kind.resample) steps.push(F.resample());
  if (kind.palette) steps.push(F.palette({ min: 5 }));
  steps.push(F.join({ keepNamed: !kind.joinNamed }), F.weld(), F.prune(), F.sparse());
  // the palettes lossless (lossy WebP smears neighbouring colour blocks into each other), the rest as good-quality WebP
  // (a pattern is tried on the name and on the URI, which is empty for embedded images: never match an empty string)
  const big = Object.keys(kind.big);
  for (const [name, size] of Object.entries(kind.big)) {
    steps.push(F.textureCompress({ encoder: sharp, targetFormat: 'webp', pattern: new RegExp(`^${name}(\\.|$)`), resize: [size, size], quality: 92 }));
  }
  const others = new RegExp(`^(?!(${['Palette', ...big].join('|')})(\\.|$|[A-Z0-9]))..*$`);
  steps.push(F.textureCompress({ encoder: sharp, targetFormat: 'webp', pattern: others, resize: [kind.textureSize, kind.textureSize], quality: 90 }));
  if (kind.palette) steps.push(F.textureCompress({ encoder: sharp, targetFormat: 'webp', pattern: /^Palette/, lossless: true }));
  steps.push(F.meshopt({ encoder: MeshoptEncoder, level: 'high' }));
  await doc.transform(...steps);
  await io.write(out, doc);
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
      const log = build(script, [...(variant ? ['--variant', variant] : []), '--out', kind.outDir ? tmp : raw]).toString();
      for (const line of log.split('\n')) if (/^(TRIS|MATERIALS|PROP)/.test(line)) console.log(`  ${line}`);
      const out = path.join(kind.out, `${name}.glb`);
      await optimise(raw, out);
      fs.rmSync(tmp, { recursive: true, force: true });
      console.log(out, fs.statSync(out).size, 'bytes');
    }
    if (renderDir !== null) {
      const dir = path.resolve(renderDir || path.join(os.tmpdir(), `${id}-render`), renderDir ? id : '');
      fs.mkdirSync(dir, { recursive: true });
      build(script, ['--render', dir]);
      console.log('  renders in', dir);
    }
  }
})();
