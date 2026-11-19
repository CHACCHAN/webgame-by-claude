// Thumbnails of the vehicles for the car select (public/img/vehicles/<id>.webp, 320×180), drawn by the game's own
// renderer: headless Google Chrome on the built game, each vehicle in the garage (default colour, the first course's
// summit, one time of day) seen from the same angle for its kind, the frame scaled down and encoded as WebP in the
// browser (no image tools needed on the host).
//   node tools/thumbs.cjs                 every vehicle of src/game/vehicle/vehicleStats.json (= VEHICLE_ORDER)
//   node tools/thumbs.cjs e5 roach        only these (a new model, a changed one): the other files are left alone
//   node tools/thumbs.cjs --sheet <file>  no rendering: one picture of all the thumbnails in the folder (.webp / .png)
// A picture depends only on the model, the course and the settings below, so an unchanged vehicle comes out the same
// (to the eye: the GPU's rounding may differ by a level here and there).
// Env: URL (default http://localhost:4173/; serve with `API_PROXY=http://127.0.0.1:9 npx vite preview`, /api is also
// aborted in the browser), CHROME, PW_MODULE, QUALITY (high), TOD (night), WEBP (quality 0–1, default 0.8),
// COURSE (oboro-downhill; the fighters stand on no road: `COURSE=edwards node tools/thumbs.cjs f15j f15c su47`, on a
// build that has the course: `VITE_EDWARDS=1 npm run build` until its release),
// RAW=<dir> (also keeps the full frames as PNG), SOFTWARE=1 (SwiftShader instead of the GPU: slow, for a check only).
// On the owner's PC the GPU needs the render group: ~/.local/opt/quality/gpurun.sh URL=… node tools/thumbs.cjs
const { chromium } = require(process.env.PW_MODULE || 'playwright');
const fs = require('fs');
const path = require('path');

const OUT = path.join(__dirname, '../public/img/vehicles');
const URL_ = process.env.URL || 'http://localhost:4173/';
const QUALITY = process.env.QUALITY || 'high';
const TOD = process.env.TOD || 'night';
const WEBP = +(process.env.WEBP || 0.8);
const W = 1280, H = 720, TW = 320, TH = 180;

/**
 * The camera per kind: the angle off the vehicle's nose and above the ground (rad), the distance as a multiple of the
 * garage's standard one for that kind (KIND_TRAITS.garage.scale; `fit`: for a vehicle up to that long in m, a longer
 * one is seen from that much further), and where it aims off the garage's focus: `up` and `pan` towards the nose (m at
 * a car's distance, as `Game.garageFraming`).
 */
const VIEWS = {
  car: { yaw: 0.72, pitch: 0.17, dist: 0.58, fit: 4.5, up: 0, pan: 0 },
  bike: { yaw: 1.0, pitch: 0.15, dist: 0.64, fit: 2.1, up: 0.5, pan: 0 },
  tank: { yaw: 0.72, pitch: 0.2, dist: 0.7, up: 0.2, pan: 0 },
  jet: { yaw: 0.8, pitch: 0.24, dist: 0.9, up: 0.2, pan: 0 },
  // seen from ahead: the face, and the leading car's side running back (the garage frames the middle of the leading
  // car: the aim moves towards the nose, a Shinkansen's is long)
  train: { yaw: 0.36, pitch: 0.08, dist: 1.0, up: 0.3, pan: 1.1 },
  creature: { yaw: 0.72, pitch: 0.22, dist: 0.62, up: 0, pan: 0 },
};

const args = process.argv.slice(2);
const sheetAt = args.indexOf('--sheet');
const sheet = sheetAt >= 0 ? args.splice(sheetAt, 2)[1] : null;
const ORDER = Object.keys(JSON.parse(fs.readFileSync(path.join(__dirname, '../src/game/vehicle/vehicleStats.json'), 'utf8')).vehicles);

function launch() {
  const gpu = ['--ignore-gpu-blocklist', '--use-angle=vulkan', '--enable-features=Vulkan'];
  const soft = ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'];
  return chromium.launch({ executablePath: process.env.CHROME || '/usr/bin/google-chrome', headless: true, args: process.env.SOFTWARE ? soft : gpu });
}

const frames = (page, n) =>
  page.evaluate((k) => new Promise((res) => {
    let i = 0;
    const f = () => (++i >= k ? res() : requestAnimationFrame(f));
    requestAnimationFrame(f);
  }), n);

/** PNG (base64) → WebP (base64) at the thumbnail's size, in a blank page of the same browser */
const toWebp = (tool, png) =>
  tool.evaluate(async ([b64, w, h, q]) => {
    const blob = await (await fetch(`data:image/png;base64,${b64}`)).blob();
    const bmp = await createImageBitmap(blob, { resizeWidth: w, resizeHeight: h, resizeQuality: 'high' });
    const c = new OffscreenCanvas(w, h);
    c.getContext('2d').drawImage(bmp, 0, 0);
    const out = await c.convertToBlob({ type: 'image/webp', quality: q });
    const bytes = new Uint8Array(await out.arrayBuffer());
    let s = '';
    for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
    return btoa(s);
  }, [png, TW, TH, WEBP]);

async function render(browser, ids) {
  const ctx = await browser.newContext({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
  await ctx.route('**/api/**', (r) => r.abort());
  const page = await ctx.newPage();
  const tool = await ctx.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  // shader and pipeline errors only reach the console (a vehicle that fails to draw leaves the previous picture)
  page.on('console', (m) => {
    if (m.type() === 'error' && !/net::ERR_FAILED|Failed to load resource/.test(m.text()) && errors.length < 20) errors.push(m.text().slice(0, 400));
  });
  const settings = { quality: QUALITY, resolutionScale: 1, timeOfDay: TOD, masterVolume: 0, sfxVolume: 0, musicVolume: 0, assist: 1, autoShift: true, showGhost: false, cornerGuide: false, controlsGuide: false, showFps: false, courseId: process.env.COURSE || 'oboro-downhill', upscale: false };
  await page.addInitScript((s) => localStorage.setItem('touge-settings', JSON.stringify({ state: s, version: 1 })), settings);
  await page.goto(URL_);
  await page.waitForFunction(() => window.__game && window.__game.phase === 'attract', null, { timeout: 180000 });
  await page.addStyleTag({ content: '.overlay, .fs-toggle, .touch-back { display: none !important; }' });
  await page.bringToFront();
  const backend = await page.evaluate(() => {
    const b = window.__game.renderer.backend;
    return b ? (b.isWebGPUBackend ? 'webgpu' : 'webgl2') : 'webgl';
  });
  console.log(`renderer: ${backend}, quality ${QUALITY}, ${TOD}`);
  fs.mkdirSync(OUT, { recursive: true });
  if (process.env.RAW) fs.mkdirSync(process.env.RAW, { recursive: true });
  // the game's frames are counted (its loop stands still while a new model's shaders compile; the page's own
  // animation frames go on meanwhile and say nothing)
  await page.evaluate(() => {
    const g = window.__game;
    const update = Object.getPrototypeOf(g).update.bind(g);
    g.__frames = 0;
    g.update = (dt) => {
      g.__frames++;
      update(dt);
    };
  });
  const state = () => page.evaluate(() => ({ n: window.__game.__frames, pos: window.__game.camera.position.toArray().map((x) => x.toFixed(4)).join() }));
  for (const id of ids) {
    // a model that is not loaded yet comes behind the menus: the garage shows the vehicle only once it is there
    await page.evaluate((vid) => window.__game.showGarage(vid), id);
    await page.waitForFunction((vid) => window.__game.garageCar && window.__game.garageCar.spec.id === vid, id, { timeout: 120000 });
    const kind = await page.evaluate(
      ([vid, views]) => {
        const g = window.__game;
        const spec = g.garageCar.spec;
        const k = spec.train ? 'train' : spec.creature ? 'creature' : spec.bike ? 'bike' : spec.tank ? 'tank' : spec.jet ? 'jet' : 'car';
        const v = views[k];
        // the camera on the side the garage looks from (the valley behind the vehicle), at the angle off its nose
        const nose = g.garageCar.root.rotation.y;
        const side = Math.cos(nose + v.yaw - g.garageViewYaw) >= Math.cos(nose - v.yaw - g.garageViewYaw) ? 1 : -1;
        const fit = v.fit ? Math.max(1, spec.size.length / v.fit) : 1;
        g.garageOrbit = { yaw: nose + side * v.yaw - g.garageViewYaw, pitch: v.pitch, dist: 8.6 * g.garageScale * v.dist * fit };
        // (the nose is to the camera's left when the camera stands to the vehicle's left)
        g.garageFraming = { right: -side * v.pan, up: v.up, zoom: 1 };
        return k;
      },
      [id, VIEWS],
    );
    // the camera glides to its place while the model's shaders compile: the picture is taken once the game has drawn
    // 40 frames with the vehicle and the camera has stood still over three looks, frames passing between them
    const from = (await state()).n;
    let prev = { n: from, pos: '' };
    let still = 0;
    for (const t0 = Date.now(); still < 3 || prev.n < from + 40; ) {
      if (Date.now() - t0 > 90000) throw new Error(`${id}: the game stopped drawing (frame ${prev.n - from})`);
      await page.waitForTimeout(120);
      const now = await state();
      if (now.n > prev.n) still = now.pos === prev.pos ? still + 1 : 0;
      prev = now;
    }
    // (two more of the page's frames: the last drawn one is on the canvas)
    await frames(page, 2);
    const png = (await page.screenshot({ type: 'png' })).toString('base64');
    if (process.env.RAW) fs.writeFileSync(path.join(process.env.RAW, `${id}.png`), Buffer.from(png, 'base64'));
    const webp = Buffer.from(await toWebp(tool, png), 'base64');
    fs.writeFileSync(path.join(OUT, `${id}.webp`), webp);
    console.log(`${id.padEnd(12)} ${kind.padEnd(8)} ${(webp.length / 1024).toFixed(1)} KB`);
  }
  if (errors.length) console.log('page errors:', errors.slice(0, 5));
  await ctx.close();
}

/** every thumbnail in the folder on one sheet, in the players' order, with its id */
async function contactSheet(browser, file) {
  const page = await browser.newPage();
  const have = ORDER.filter((id) => fs.existsSync(path.join(OUT, `${id}.webp`)));
  const tiles = have.map((id) => ({ id, src: `data:image/webp;base64,${fs.readFileSync(path.join(OUT, `${id}.webp`)).toString('base64')}` }));
  const b64 = await page.evaluate(async ([list, w, h, type]) => {
    const cols = 6, pad = 8, label = 20;
    const rows = Math.ceil(list.length / cols);
    const c = new OffscreenCanvas(pad + cols * (w + pad), pad + rows * (h + label + pad));
    const g = c.getContext('2d');
    g.fillStyle = '#0b111c';
    g.fillRect(0, 0, c.width, c.height);
    g.font = '13px sans-serif';
    for (let i = 0; i < list.length; i++) {
      const x = pad + (i % cols) * (w + pad), y = pad + Math.floor(i / cols) * (h + label + pad);
      g.drawImage(await createImageBitmap(await (await fetch(list[i].src)).blob()), x, y);
      g.fillStyle = '#e9edf5';
      g.fillText(list[i].id, x + 2, y + h + 15);
    }
    const out = await c.convertToBlob({ type, quality: 0.9 });
    const bytes = new Uint8Array(await out.arrayBuffer());
    let s = '';
    for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
    return btoa(s);
  }, [tiles, TW, TH, file.endsWith('.png') ? 'image/png' : 'image/webp']);
  fs.writeFileSync(file, Buffer.from(b64, 'base64'));
  console.log(`sheet of ${have.length} thumbnails: ${file}`);
}

(async () => {
  const browser = await launch();
  try {
    if (sheet) await contactSheet(browser, path.resolve(sheet));
    else await render(browser, args.length ? args : ORDER);
  } finally {
    await browser.close();
  }
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
