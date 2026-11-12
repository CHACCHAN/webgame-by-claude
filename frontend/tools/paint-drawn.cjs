// Is a vehicle still drawn after its paint was changed? On the host GPU (or SOFTWARE=1): the garage with the vehicle,
// every paint it offers set the way the car select does it (`game.setGarageColor`), then the vehicle built anew in
// each paint (`showGarage(id, paint)`: what a race, the waiting room and another player's game do), then a race in
// the last paint. "Drawn" is measured, not assumed: the picture with the vehicle against the same picture with its
// root hidden; a paint under which less than MIN of the frame changes counts as not drawn. Page errors and the GPU's
// validation errors are reported as in tools/gpu-errors.cjs.
//   node tools/paint-drawn.cjs [ids…]     default: roach; exit code 1 when a paint is not drawn or anything errored
// Env: URL (http://localhost:4173/), QUERY (e.g. ?webgl=1), QUALITY (high), TOD (night), SET (more settings, JSON),
// OUT (directory for the pictures), SOFTWARE=1, CHROME, PW_MODULE.
// Serve with `API_PROXY=http://127.0.0.1:9 npx vite preview`; /api is also aborted in the browser.
const { chromium } = require(process.env.PW_MODULE || 'playwright');
const fs = require('fs');
const IDS = process.argv.slice(2).length ? process.argv.slice(2) : ['roach'];
const OUT = process.env.OUT;
const QUALITY = process.env.QUALITY || 'high', TOD = process.env.TOD || 'night';
/** share of the frame a vehicle must change to count as drawn (the cockroach in the garage covers ~10 %) */
const MIN = 0.01;

(async () => {
  const gpu = ['--ignore-gpu-blocklist', '--use-angle=vulkan', '--enable-features=Vulkan'];
  const soft = ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'];
  const browser = await chromium.launch({ executablePath: process.env.CHROME || '/usr/bin/google-chrome', headless: true, args: process.env.SOFTWARE ? soft : gpu });
  const ctx = await browser.newContext({ viewport: { width: 960, height: 540 }, deviceScaleFactor: 1 });
  await ctx.route('**/api/**', (r) => r.abort());
  const page = await ctx.newPage();
  const tool = await ctx.newPage();
  let step = 'boot';
  const seen = {};
  page.on('console', (m) => {
    if (m.type() !== 'error' && m.type() !== 'warning') return;
    const t = `${step}: ${m.text().slice(0, 200).replace(/\s+/g, ' ')}`;
    if (/net::ERR_FAILED|Failed to load resource|GL Driver Message \(OpenGL, Performance/.test(t)) return;
    seen[t] = (seen[t] || 0) + 1;
  });
  page.on('pageerror', (e) => (seen[`${step}: PAGE ERROR ${e.message.slice(0, 200)}`] = 1));
  const settings = { quality: QUALITY, timeOfDay: TOD, masterVolume: 0, uiMotion: false, ...JSON.parse(process.env.SET || '{}') };
  await page.addInitScript((s) => localStorage.setItem('touge-settings', JSON.stringify({ state: s, version: 1 })), settings);
  await page.goto((process.env.URL || 'http://localhost:4173/') + (process.env.QUERY || ''));
  await page.waitForFunction(() => window.__game && window.__game.phase === 'attract', null, { timeout: 240000 });
  const backend = await page.evaluate(() => (window.__game.renderer.backend.isWebGPUBackend ? 'webgpu' : 'webgl2'));
  // the menus over the scene move by themselves: only the game's picture is compared
  await page.addStyleTag({ content: 'body * { visibility: hidden !important } canvas { visibility: visible !important }' });
  // (the page made last is in front, and a page behind draws no frames: a picture of it never comes)
  await page.bringToFront();
  const frames = (n) =>
    page.evaluate((k) => new Promise((res) => {
      let i = 0;
      const f = () => (++i >= k ? res() : requestAnimationFrame(f));
      requestAnimationFrame(f);
    }), n);
  /** share of the pixels that differ between two PNGs (a channel by more than 12 levels) */
  const differ = (a, b) =>
    tool.evaluate(async ([x, y]) => {
      const px = async (b64) => {
        const bmp = await createImageBitmap(await (await fetch(`data:image/png;base64,${b64}`)).blob());
        const c = new OffscreenCanvas(bmp.width, bmp.height);
        const g = c.getContext('2d');
        g.drawImage(bmp, 0, 0);
        return g.getImageData(0, 0, bmp.width, bmp.height).data;
      };
      const p = await px(x), q = await px(y);
      let n = 0;
      for (let i = 0; i < p.length; i += 4) if (Math.abs(p[i] - q[i]) > 12 || Math.abs(p[i + 1] - q[i + 1]) > 12 || Math.abs(p[i + 2] - q[i + 2]) > 12) n++;
      return n / (p.length / 4);
    }, [a.toString('base64'), b.toString('base64')]);
  const visible = (which, on) => page.evaluate(([w, v]) => ((w === 'garage' ? window.__game.garageCar : window.__game.player.visual).root.visible = v), [which, on]);
  const report = [];
  /** the picture with the vehicle and with its root hidden: how much of the frame is the vehicle */
  const check = async (name, which) => {
    step = name;
    // the garage's camera swings by itself: hold it; a race's car is held where it stands
    await page.evaluate((w) => {
      const g = window.__game;
      if (w === 'garage') g.garageOrbit = { yaw: 0.7, pitch: 0.2, dist: 8.8 * g.garageScale };
      else g.paused = true;
    }, which);
    await page.waitForTimeout(1500);
    await frames(4);
    const withIt = await page.screenshot({ type: 'png' });
    if (OUT) fs.writeFileSync(`${OUT}/${backend}-${name.replace(/[^a-z0-9]+/gi, '_')}.png`, withIt);
    await visible(which, false);
    await frames(6);
    const without = await page.screenshot({ type: 'png' });
    await visible(which, true);
    const share = await differ(withIt, without);
    report.push(`${share < MIN ? 'NOT DRAWN' : 'drawn    '} ${(share * 100).toFixed(1).padStart(5)} %  ${name}`);
    if (share < MIN) seen[`${name}: not drawn (${(share * 100).toFixed(2)} % of the frame)`] = 1;
  };
  for (const id of IDS) {
    step = `garage ${id}`;
    await page.evaluate((c) => window.__game.showGarage(c), id);
    await page.waitForFunction((c) => window.__game.garageCar && window.__game.garageCar.spec.id === c, id, { timeout: 60000 });
    // the paints the vehicle offers, as vehicle/paints.ts lists them for the kinds that have liveries
    const paints = await page.evaluate(() => {
      const s = window.__game.garageCar.spec;
      const l = (s.creature || s.train || s.bike || s.jet || {}).liveries;
      return l ? l.map((x) => x.swatch || x.band) : [s.colors.body, '#b3121c'];
    });
    await check(`${id} default`, 'garage');
    // the car select's way: the paint of the vehicle that stands there is changed (and back to the first at the end)
    for (const c of [...paints.slice(1), paints[0]]) {
      step = `${id} set ${c}`;
      await page.evaluate((x) => window.__game.setGarageColor(x), c);
      await page.waitForFunction((x) => window.__game.garageCar && window.__game.garageCar.color === x, c, { timeout: 60000 }).catch(() => (seen[`${step}: the paint did not arrive`] = 1));
      await check(`${id} set ${c}`, 'garage');
    }
    // built in the paint: a race's car, the waiting room's, another player's
    for (const c of paints.slice(1)) {
      step = `${id} built ${c}`;
      await page.evaluate(([x, y]) => window.__game.showGarage(x, y), [id, c]);
      await page.waitForFunction((x) => window.__game.garageCar && window.__game.garageCar.color === x, c, { timeout: 60000 }).catch(() => (seen[`${step}: the vehicle did not arrive`] = 1));
      await check(`${id} built ${c}`, 'garage');
    }
    const last = paints[paints.length - 1];
    step = `${id} race ${last}`;
    await page.evaluate(([x, y]) => window.__game.startRace({ mode: 'time_attack', carId: x, color: y }), [id, last]);
    await page.waitForFunction(() => window.__game.phase === 'racing', null, { timeout: 60000 });
    await check(`${id} race ${last}`, 'race');
    await page.evaluate(() => (window.__game.paused = false));
  }
  console.log(`${backend}, quality ${QUALITY}, ${TOD}${process.env.SET ? ', ' + process.env.SET : ''}`);
  for (const l of report) console.log(l);
  const lines = Object.entries(seen);
  console.log(`${lines.length} distinct errors / warnings`);
  for (const [t, c] of lines.slice(0, 30)) console.log(`${c}× ${t}`);
  await browser.close();
  process.exit(lines.length ? 1 : 0);
})().catch((e) => {
  console.error(String(e).slice(0, 400));
  process.exit(1);
});
