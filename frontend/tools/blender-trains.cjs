// Our own train models, built from numbers in Blender (tools/blender/<id>.py with tools/blender/train_kit.py) and
// optimised like the imported ones (meshopt, one mesh per material per car; nodes car0, car1, car2):
//   node tools/blender-trains.cjs [ids]                  – writes public/models/trains/<id>.glb
//   node tools/blender-trains.cjs keikyu1000 --render    – also renders the build stages to /tmp/<id>-stage*.png
// BLENDER=<path> picks the Blender binary (default: `blender` on PATH; tested with 5.2 LTS).
const fs = require('fs');
const os = require('os');
const path = require('path');
const { execFileSync } = require('child_process');

const args = process.argv.slice(2);
const ids = (args.find((a) => !a.startsWith('--')) ?? 'keikyu1000').split(',');
const blender = process.env.BLENDER || 'blender';
const cli = path.join('node_modules/.bin/gltf-transform');
const gltf = (...a) => execFileSync(fs.existsSync(cli) ? cli : 'gltf-transform', a, { stdio: 'pipe' });
const build = (script, extra) => execFileSync(blender, ['--background', '--factory-startup', '--python', script, '--', ...extra], { stdio: 'pipe' });

/**
 * Blender's glTF exporter lists the materials and a mesh's primitives in an order that changes from run to run (the
 * geometry does not): sort both by material name, so rebuilding an unchanged script gives the same GLB.
 */
async function sortByMaterial(file) {
  const { NodeIO } = require('@gltf-transform/core');
  const io = new NodeIO();
  const doc = await io.read(file);
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
    for (const p of prims.sort((a, b) => (key(a) < key(b) ? -1 : key(a) > key(b) ? 1 : 0))) mesh.addPrimitive(p);
  }
  await io.write(file, doc);
}

(async () => {
  for (const id of ids) {
    const script = path.join(__dirname, 'blender', `${id}.py`);
    if (!fs.existsSync(script)) throw new Error(`no ${script}`);
    const tmp = fs.mkdtempSync(path.join(os.tmpdir(), `${id}-`));
    const raw = path.join(tmp, `${id}.raw.glb`);
    build(script, ['--out', raw]);
    await sortByMaterial(raw);
    const out = path.join('public/models/trains', `${id}.glb`);
    gltf('optimize', raw, out, '--compress', 'meshopt', '--flatten', 'false', '--join', 'true', '--palette', 'false', '--simplify', 'false', '--instance', 'false');
    fs.rmSync(tmp, { recursive: true, force: true });
    console.log(out, fs.statSync(out).size, 'bytes');
    if (args.includes('--render')) {
      for (const [stage, view] of [[1, 'front34'], [2, 'front34'], [3, 'front34'], [4, 'front34'], [5, 'side'], [5, 'rear34']]) {
        const png = path.join(os.tmpdir(), `${id}-stage${stage}-${view}.png`);
        build(script, ['--stage', String(stage), '--render', png, '--view', view]);
        console.log(png);
      }
    }
  }
})();
