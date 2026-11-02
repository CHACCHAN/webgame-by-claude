// Converts third-party scenery models (e.g. Sketchfab glTF downloads, unpacked one folder per model)
// into the game's prop GLBs through a headless browser (three.js loader/exporter, see
// src/game/render/propImport.ts), then optimises them with the glTF-Transform CLI.
//   node tools/import-props.cjs raw     <srcRoot> <outDir> [ids]   – source model as delivered (front/side/top/back)
//   node tools/import-props.cjs preview <srcRoot> <outDir> [ids]   – converted prop with a 1 m grid, red arrow = +Z
//   node tools/import-props.cjs import  <srcRoot> [ids]            – writes public/models/props/<id>.glb
// Per-prop settings: tools/prop-import.json ({ id: { dir, config, textureSize? } }). Needs `vite preview` on :4173.
const { chromium } = require(process.env.PW_MODULE || 'playwright');
const fs = require('fs');
const path = require('path');
const http = require('http');
const { execFileSync } = require('child_process');

const [mode, srcRoot, ...rest] = process.argv.slice(2);
if (!['raw', 'preview', 'import'].includes(mode) || !srcRoot) throw new Error('usage: node tools/import-props.cjs raw|preview|import <srcRoot> [outDir] [ids]');
const base = process.env.EXPORT_BASE || 'http://localhost:4173';
const props = JSON.parse(fs.readFileSync(path.join(__dirname, 'prop-import.json'), 'utf8'));
const shots = mode !== 'import';
const wanted = (shots ? rest[1] : rest[0])?.split(',') ?? Object.keys(props).filter((k) => !k.startsWith('_'));

// the source files are served with CORS so the game page can load them
const types = { '.gltf': 'model/gltf+json', '.bin': 'application/octet-stream', '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg' };
// (a prop's `file` overrides scene.gltf, e.g. Poly Haven's <name>_1k.gltf)
const root = path.resolve(srcRoot);
const server = http.createServer((req, res) => {
  const file = path.join(root, decodeURIComponent(new URL(req.url, 'http://x').pathname));
  if (!file.startsWith(root) || !fs.existsSync(file)) {
    res.writeHead(404).end();
    return;
  }
  res.writeHead(200, { 'Access-Control-Allow-Origin': '*', 'Content-Type': types[path.extname(file)] || 'application/octet-stream' });
  fs.createReadStream(file).pipe(res);
});

(async () => {
  await new Promise((r) => server.listen(8098, r));
  const browser = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const page = await browser.newPage();
  page.on('pageerror', (e) => console.error('[page]', e.message));
  page.on('console', (m) => m.type() === 'error' && console.error('[console]', m.text()));
  await page.goto(`${base}/?export=1`);
  await page.waitForFunction(() => window.__importProp, null, { timeout: 180000 });
  const outDir = 'public/models/props';
  fs.mkdirSync(outDir, { recursive: true });
  for (const id of wanted) {
    const prop = props[id];
    if (!prop) throw new Error(`unknown prop ${id}`);
    const url = `http://localhost:8098/${prop.dir}/${prop.file ?? 'scene.gltf'}`;
    if (shots) {
      const out = rest[0];
      fs.mkdirSync(out, { recursive: true });
      const res = await page.evaluate(([u, c, i]) => window.__previewProp(u, c, i), [url, mode === 'preview' ? prop.config : undefined, id]);
      for (const [name, data] of Object.entries(res.shots)) fs.writeFileSync(path.join(out, `${id}-${mode}-${name}.png`), Buffer.from(data.split(',')[1], 'base64'));
      console.log(id, 'bbox', JSON.stringify(res.box));
    } else {
      const res = await page.evaluate(([u, i, c]) => window.__importProp(u, i, c), [url, id, prop.config]);
      const raw = path.join(outDir, `${id}.raw.glb`);
      const out = path.join(outDir, `${id}.glb`);
      fs.writeFileSync(raw, Buffer.from(res.b64, 'base64'));
      const cli = path.join('node_modules/.bin/gltf-transform');
      const run = (...args) => execFileSync(fs.existsSync(cli) ? cli : 'gltf-transform', args, { stdio: 'pipe' });
      const ratio = String(prop.simplify ?? 1);
      run('optimize', raw, out, '--compress', 'meshopt', '--texture-compress', 'webp', '--texture-size', String(prop.textureSize ?? 512),
        '--simplify', ratio === '1' ? 'false' : 'true', '--simplify-ratio', ratio, '--simplify-error', String(prop.simplifyError ?? 0.001), '--flatten', 'false', '--join', 'true',
        // keep material names: the game finds role materials (lamp lenses) by name
        '--palette', 'false');
      fs.unlinkSync(raw);
      console.log(id, JSON.stringify(res.stats), '→', out, fs.statSync(out).size, 'bytes');
    }
  }
  await browser.close();
  server.close();
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
