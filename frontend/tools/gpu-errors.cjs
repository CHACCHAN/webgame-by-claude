// The GPU's validation errors (and page errors) over the paths that free models and show them again, on the host GPU:
// garage with several vehicles (one of them twice) → race in the car just shown → restart → another course → garage
// → rival race → back to the first course → attract. A check that starts a race directly misses these: on WebGPU a
// buffer destroyed with one clone of a model and used by the next freezes the picture (render/threeFixes.ts).
//   node tools/gpu-errors.cjs            exit code 1 when anything was reported
// Env: URL (http://localhost:4173/), QUERY (e.g. ?webgl=1), VEHICLES (comma list shown in the garage),
// OUT (directory for three pictures: race, rival race, attract), CHROME, PW_MODULE.
// Serve with `API_PROXY=http://127.0.0.1:9 npx vite preview`; /api is also aborted in the browser.
const { chromium } = require(process.env.PW_MODULE || 'playwright');
const VEHICLES = (process.env.VEHICLES || 'hayate,r34,hayate,e231,nsr250r,roach,hayate').split(',');
const OUT = process.env.OUT;

(async () => {
  const browser = await chromium.launch({
    executablePath: process.env.CHROME || '/usr/bin/google-chrome',
    headless: true,
    args: ['--ignore-gpu-blocklist', '--use-angle=vulkan', '--enable-features=Vulkan'],
  });
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 720 } });
  await ctx.route('**/api/**', (r) => r.abort());
  const page = await ctx.newPage();
  let step = 'boot';
  const seen = {};
  page.on('console', (m) => {
    if (m.type() !== 'error' && m.type() !== 'warning') return;
    const t = `${step}: ${m.text().slice(0, 160).replace(/\s+/g, ' ')}`;
    // the aborted /api calls; the GL driver's performance notes (WebGL 2 backend on ANGLE/Vulkan)
    if (/net::ERR_FAILED|Failed to load resource|GL Driver Message \(OpenGL, Performance/.test(t)) return;
    seen[t] = (seen[t] || 0) + 1;
  });
  page.on('pageerror', (e) => (seen[`${step}: PAGE ERROR ${e.message.slice(0, 200)}`] = 1));
  await page.addInitScript(() => localStorage.setItem('touge-settings', JSON.stringify({ state: { quality: 'high', timeOfDay: 'night', masterVolume: 0 }, version: 1 })));
  await page.goto((process.env.URL || 'http://localhost:4173/') + (process.env.QUERY || ''));
  await page.waitForFunction(() => window.__game && window.__game.phase === 'attract', null, { timeout: 240000 });
  const backend = await page.evaluate(() => (window.__game.renderer.backend.isWebGPUBackend ? 'webgpu' : 'webgl2'));
  const run = async (name, fn, arg, wait = 2500) => {
    step = name;
    await page.evaluate(fn, arg);
    await page.waitForTimeout(wait);
  };
  const shot = async (name) => OUT && page.screenshot({ path: `${OUT}/${name}.jpg`, quality: 80, type: 'jpeg' });
  const last = VEHICLES[VEHICLES.length - 1];
  for (const id of VEHICLES) await run(`garage ${id}`, (c) => window.__game.showGarage(c), id);
  await run(`race ${last}`, (c) => window.__game.startRace({ mode: 'time_attack', carId: c }), last, 9000);
  await shot('race');
  await run('restart', () => window.__game.restart(), null, 6000);
  await run('other course', () => window.__game.switchCourse('autobahn'), null, 30000);
  await run(`garage ${last} (other course)`, (c) => window.__game.showGarage(c), last);
  await run('rival race', () => window.__game.startRace({ mode: 'rival', carId: 'shiden', rivalLevel: 'legend' }), null, 9000);
  await shot('rival');
  await run('first course again', () => window.__game.switchCourse('oboro-downhill'), null, 30000);
  await run('attract', () => window.__game.startAttract(), null, 5000);
  await shot('attract');
  const lines = Object.entries(seen);
  console.log(`${backend}: ${lines.length} distinct errors / warnings`);
  for (const [t, c] of lines.slice(0, 30)) console.log(`${c}× ${t}`);
  await browser.close();
  process.exit(lines.length ? 1 : 0);
})().catch((e) => {
  console.error(String(e).slice(0, 400));
  process.exit(1);
});
