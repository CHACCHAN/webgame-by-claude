// Cuts three cars out of third-party train models (Sketchfab glTF downloads, one folder each) through a headless
// browser (src/game/render/trainImport.ts) and optimises the result with the glTF-Transform CLI:
//   node tools/import-trains.cjs <srcRoot> [ids]   – writes public/models/trains/<id>.glb (nodes car0, car1, car2)
// Per-train settings: tools/train-import.json ({ id: { dir, config, metalrough?, simplify?, textureSize? } }).
// Needs `vite preview` on :4173 (rebuild first); CHROME=<path> uses an installed Chrome.
const { chromium } = require(process.env.PW_MODULE || 'playwright');
const fs = require('fs');
const path = require('path');
const http = require('http');
const { execFileSync } = require('child_process');

const [srcRoot, ids] = process.argv.slice(2);
const base = process.env.EXPORT_BASE || 'http://localhost:4173';
const trains = JSON.parse(fs.readFileSync(path.join(__dirname, 'train-import.json'), 'utf8'));
const wanted = ids?.split(',') ?? Object.keys(trains);
const cli = path.join('node_modules/.bin/gltf-transform');
const run = (...args) => execFileSync(fs.existsSync(cli) ? cli : 'gltf-transform', args, { stdio: 'pipe' });

const types = { '.gltf': 'model/gltf+json', '.glb': 'model/gltf-binary', '.bin': 'application/octet-stream', '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg' };
const tmp = fs.mkdtempSync(path.join(require('os').tmpdir(), 'trains-'));
const server = http.createServer((req, res) => {
  const rel = decodeURIComponent(new URL(req.url, 'http://x').pathname);
  // converted sources (spec-gloss → metal-rough) are served from the temp folder
  const file = rel.startsWith('/__tmp/') ? path.join(tmp, rel.slice(7)) : path.join(srcRoot, rel);
  if (!(file.startsWith(path.resolve(srcRoot)) || file.startsWith(tmp)) || !fs.existsSync(file)) {
    res.writeHead(404).end();
    return;
  }
  res.writeHead(200, { 'Access-Control-Allow-Origin': '*', 'Content-Type': types[path.extname(file)] || 'application/octet-stream' });
  fs.createReadStream(file).pipe(res);
});

(async () => {
  await new Promise((r) => server.listen(8099, r));
  const browser = await chromium.launch({ executablePath: process.env.CHROME, args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const page = await browser.newPage();
  page.on('pageerror', (e) => console.error('[page]', e.message));
  await page.goto(`${base}/?export=1`);
  await page.waitForFunction(() => window.__importTrain, null, { timeout: 180000 });
  fs.mkdirSync('public/models/trains', { recursive: true });
  for (const id of wanted) {
    const t = trains[id];
    const urls = t.config.files.map((f) => {
      const src = path.join(srcRoot, t.dir, f);
      if (!t.metalrough) return `http://localhost:8099/${path.join(t.dir, f)}`;
      // three.js no longer reads KHR_materials_pbrSpecularGlossiness: convert first
      const out = path.join(tmp, `${id}-${path.basename(f, path.extname(f))}.glb`);
      run('metalrough', src, out);
      return `http://localhost:8099/__tmp/${path.basename(out)}`;
    });
    const res = await page.evaluate(([u, c]) => window.__importTrain(u, c), [urls, t.config]);
    const raw = path.join('public/models/trains', `${id}.raw.glb`);
    const out = path.join('public/models/trains', `${id}.glb`);
    fs.writeFileSync(raw, Buffer.from(res.b64, 'base64'));
    const ratio = String(t.simplify ?? 1);
    run('optimize', raw, out, '--compress', 'meshopt', '--texture-compress', 'webp', '--texture-size', String(t.textureSize ?? 1024),
      '--simplify', ratio === '1' ? 'false' : 'true', '--simplify-ratio', ratio, '--simplify-error', '0.002',
      // keep the car0/car1/car2 nodes; merge meshes within each car
      '--flatten', 'false', '--join', 'true', '--palette', 'false');
    fs.unlinkSync(raw);
    console.log(id, JSON.stringify(res.stats), '→', out, fs.statSync(out).size, 'bytes');
  }
  await browser.close();
  server.close();
  fs.rmSync(tmp, { recursive: true, force: true });
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
