// Exports the procedural cars to GLB through a headless browser (GLTFExporter needs a DOM),
// then the glTF-Transform CLI optimises them (see package.json "assets:cars").
// usage: node tools/export-cars.cjs http://localhost:4173 public/models/cars/raw
const { chromium } = require(process.env.PW_MODULE || 'playwright');
const fs = require('fs');
const path = require('path');
(async () => {
  const [base = 'http://localhost:4173', outDir = 'public/models/cars/raw'] = process.argv.slice(2);
  fs.mkdirSync(outDir, { recursive: true });
  const b = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  const p = await b.newPage();
  await p.goto(`${base}/?export=1`);
  await p.waitForFunction(() => window.__exportCar, null, { timeout: 120000 });
  for (const id of ['hayate', 'raijin', 'shiden']) {
    const b64 = await p.evaluate((id) => window.__exportCar(id), id);
    const file = path.join(outDir, `${id}.glb`);
    fs.writeFileSync(file, Buffer.from(b64, 'base64'));
    console.log('wrote', file, fs.statSync(file).size, 'bytes');
  }
  await b.close();
})();
