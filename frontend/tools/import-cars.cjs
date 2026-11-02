// Converts third-party car models (e.g. Sketchfab glTF downloads, unpacked one folder per car)
// into the game's car GLBs through a headless browser (three.js loader/exporter, see
// src/game/render/carImport.ts), then optimises them with the glTF-Transform CLI.
//   node tools/import-cars.cjs preview <srcRoot> <outDir> [ids]   – side/top/front renders
//   node tools/import-cars.cjs import  <srcRoot> [ids]            – writes public/models/cars/<id>.glb
// Per-car settings: tools/car-import.json ({ id: { dir, config } }). Needs `vite preview` on :4173.
// CHROME=<path> uses an installed Chrome instead of Playwright's bundled browser (e.g. with playwright-core).
const { chromium } = require(process.env.PW_MODULE || 'playwright');
const fs = require('fs');
const path = require('path');
const http = require('http');
const { execFileSync } = require('child_process');

const [mode, srcRoot, ...rest] = process.argv.slice(2);
const base = process.env.EXPORT_BASE || 'http://localhost:4173';
const cars = JSON.parse(fs.readFileSync(path.join(__dirname, 'car-import.json'), 'utf8'));
const wanted = (mode === 'preview' ? rest[1] : rest[0])?.split(',') ?? Object.keys(cars);

// the source files are served with CORS so the game page can load them
const types = { '.gltf': 'model/gltf+json', '.bin': 'application/octet-stream', '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg' };
const server = http.createServer((req, res) => {
  const file = path.join(srcRoot, decodeURIComponent(new URL(req.url, 'http://x').pathname));
  if (!file.startsWith(path.resolve(srcRoot)) || !fs.existsSync(file)) {
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
  await page.waitForFunction(() => window.__importCar, null, { timeout: 180000 });
  for (const id of wanted) {
    const car = cars[id];
    const url = `http://localhost:8099/${car.dir}/scene.gltf`;
    if (mode === 'preview') {
      const out = rest[0];
      fs.mkdirSync(out, { recursive: true });
      const res = await page.evaluate(([u, r]) => window.__previewCar(u, r), [url, car.config.rotation]);
      for (const [name, data] of Object.entries(res.shots)) fs.writeFileSync(path.join(out, `${id}-${name}.png`), Buffer.from(data.split(',')[1], 'base64'));
      console.log(id, 'bbox', JSON.stringify(res.box));
    } else {
      const res = await page.evaluate(([u, i, c]) => window.__importCar(u, i, c), [url, id, car.config]);
      const raw = path.join('public/models/cars', `${id}.raw.glb`);
      const out = path.join('public/models/cars', `${id}.glb`);
      fs.writeFileSync(raw, Buffer.from(res.b64, 'base64'));
      const cli = path.join('node_modules/.bin/gltf-transform');
      const run = (...args) => execFileSync(fs.existsSync(cli) ? cli : 'gltf-transform', args, { stdio: 'pipe' });
      const ratio = String(car.simplify ?? 0.5);
      run('optimize', raw, out, '--compress', 'meshopt', '--texture-compress', 'webp', '--texture-size', String(car.textureSize ?? 1024),
        '--simplify', ratio === '1' ? 'false' : 'true', '--simplify-ratio', ratio, '--simplify-error', String(car.simplifyError ?? 0.0005), '--flatten', 'false', '--join', 'true',
        // keep material names: the game swaps paint / glass / lamp materials by name
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
