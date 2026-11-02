// Optimises third-party scenery models (Sketchfab glTF downloads, unpacked one folder each) into
// public/models/props/<id>.glb with the glTF-Transform CLI: meshopt geometry, WebP textures capped per prop,
// no simplification, named nodes kept apart (a turbine's rotor). Size, orientation and origin are set in the
// game (PROPS in src/game/render/props.ts), so a model only needs re-importing when its source changes.
//   node tools/import-props.cjs <srcRoot> [ids]
// Per-prop settings: tools/props-import.json ({ id: { dir, textureSize } }). Attribution: docs/ASSETS.md.
const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');

const [srcRoot, ids] = process.argv.slice(2);
if (!srcRoot) throw new Error('usage: node tools/import-props.cjs <srcRoot> [ids]');
const props = JSON.parse(fs.readFileSync(path.join(__dirname, 'props-import.json'), 'utf8'));
const outDir = path.join(__dirname, '../public/models/props');
fs.mkdirSync(outDir, { recursive: true });
const cli = path.join(__dirname, '../node_modules/.bin/gltf-transform');
for (const id of ids ? ids.split(',') : Object.keys(props)) {
  const p = props[id];
  const src = path.join(srcRoot, p.dir, 'scene.gltf');
  const out = path.join(outDir, `${id}.glb`);
  execFileSync(fs.existsSync(cli) ? cli : 'gltf-transform', ['optimize', src, out, '--compress', 'meshopt', '--texture-compress', 'webp',
    '--texture-size', String(p.textureSize ?? 1024), '--simplify', 'false', '--flatten', 'false', '--join', 'true', '--join-named', 'false',
    '--instance', 'false', '--palette', 'false'], { stdio: 'pipe' });
  console.log(id, '→', path.relative(process.cwd(), out), fs.statSync(out).size, 'bytes');
}
