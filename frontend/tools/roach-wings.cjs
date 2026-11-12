// The cockroach's wings, in the game, on the host GPU: (1) a sheet of the poses in the garage (folded, opening, out,
// top and bottom of the beat; from the front quarter, the side and behind) and (2) a race in which the cockroach is
// lifted off the road and dropped: the wings must be out while it falls and folded again after the landing, with
// pictures of the fall. Page errors and the GPU's validation errors are reported as in tools/gpu-errors.cjs.
//   node tools/roach-wings.cjs <dir>      exit code 1 when the wings did not open / fold or anything errored
// Env: URL (http://localhost:4173/), QUERY (e.g. ?webgl=1), QUALITY (high), TOD (dawn), PAINT (a livery's swatch),
// CHROME, PW_MODULE. Serve with `API_PROXY=http://127.0.0.1:9 npx vite preview`; /api is also aborted in the browser.
const { chromium } = require(process.env.PW_MODULE || 'playwright');
const fs = require('fs');
const path = require('path');
const OUT = process.argv[2];
if (!OUT) throw new Error('usage: node tools/roach-wings.cjs <dir>');
const W = 960, H = 540;
const POSES = [['folded', 0, 0], ['opening', 0.5, 0], ['out', 1, 0], ['up', 1, 0.25], ['down', 1, 0.75]];
/** the garage camera: angle round the vehicle from where the garage looks (rad), height angle, distance (× the usual) */
const VIEWS = [['quarter', 0.7, 0.3, 1.0], ['side', 1.6, 0.12, 1.05], ['behind', 2.75, 0.5, 1.0]];

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({ executablePath: process.env.CHROME || '/usr/bin/google-chrome', headless: true, args: ['--ignore-gpu-blocklist', '--use-angle=vulkan', '--enable-features=Vulkan', '--autoplay-policy=no-user-gesture-required'] });
  const ctx = await browser.newContext({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
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
  const settings = { quality: process.env.QUALITY || 'high', timeOfDay: process.env.TOD || 'dawn', masterVolume: 0, uiMotion: false };
  await page.addInitScript((s) => localStorage.setItem('touge-settings', JSON.stringify({ state: s, version: 1 })), settings);
  await page.goto((process.env.URL || 'http://localhost:4173/') + (process.env.QUERY || ''));
  await page.waitForFunction(() => window.__game && window.__game.phase === 'attract', null, { timeout: 240000 });
  const backend = await page.evaluate(() => (window.__game.renderer.backend.isWebGPUBackend ? 'webgpu' : 'webgl2'));
  await page.addStyleTag({ content: 'body * { visibility: hidden !important } canvas { visibility: visible !important }' });
  // (the page made last is in front, and a page behind draws no frames)
  await page.bringToFront();
  const frames = (n) =>
    page.evaluate((k) => new Promise((res) => {
      let i = 0;
      const f = () => (++i >= k ? res() : requestAnimationFrame(f));
      requestAnimationFrame(f);
    }), n);

  // ---- the poses, in the garage
  step = 'garage';
  await page.evaluate((c) => window.__game.showGarage('roach', c || undefined), process.env.PAINT);
  await page.waitForFunction(() => window.__game.garageCar && window.__game.garageCar.spec.id === 'roach', null, { timeout: 60000 });
  const bones = await page.evaluate(() => {
    const names = [];
    window.__game.garageCar.root.traverse((o) => /^(wing|hind)_[LR]$/.test(o.name) && names.push(o.name));
    return names.sort();
  });
  if (bones.join() !== 'hind_L,hind_R,wing_L,wing_R') seen[`the model's wing bones: ${bones.join() || 'none'}`] = 1;
  const tiles = [];
  for (const [view, yaw, pitch, dist] of VIEWS) {
    await page.evaluate(([y, p, d]) => {
      const g = window.__game;
      g.garageOrbit = { yaw: y, pitch: p, dist: 8.6 * g.garageScale * d };
      g.garageFraming = { right: 0, up: 0.3, zoom: 1 };
    }, [yaw, pitch, dist]);
    await page.waitForTimeout(1500);
    const row = [];
    for (const [pose, opened, phase] of POSES) {
      step = `garage ${view} ${pose}`;
      await page.evaluate(([o, p]) => window.__game.garageCar.rig.creature.poseWings(o, p), [opened, phase]);
      await frames(5);
      const png = await page.screenshot({ type: 'png' });
      row.push(png.toString('base64'));
    }
    tiles.push(row);
  }
  await page.evaluate(() => window.__game.garageCar.rig.creature.poseWings(0, 0));
  // one picture: a row per view, a column per pose
  const sheet = await tool.evaluate(async ([rows, w, h, labels]) => {
    const tw = w / 2, th = h / 2;
    const c = new OffscreenCanvas(tw * rows[0].length, th * rows.length);
    const g = c.getContext('2d');
    for (let r = 0; r < rows.length; r++) {
      for (let k = 0; k < rows[r].length; k++) {
        const bmp = await createImageBitmap(await (await fetch(`data:image/png;base64,${rows[r][k]}`)).blob(), { resizeWidth: tw, resizeHeight: th, resizeQuality: 'high' });
        g.drawImage(bmp, k * tw, r * th);
        if (r === 0) {
          g.font = '16px sans-serif';
          g.fillStyle = '#fff';
          g.fillText(labels[k], k * tw + 8, 20);
        }
      }
    }
    const bytes = new Uint8Array(await (await c.convertToBlob({ type: 'image/png' })).arrayBuffer());
    let s = '';
    for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
    return btoa(s);
  }, [tiles, W, H, POSES.map((p) => p[0])]);
  fs.writeFileSync(path.join(OUT, `${backend}-poses.png`), Buffer.from(sheet, 'base64'));

  // ---- in the air: a race, the cockroach lifted off the road and dropped
  step = 'race';
  await page.bringToFront();
  // (with the sound running, at volume 0: the wings' flutter is read from its gain)
  await page.evaluate(() => window.__game.initAudio());
  await page.evaluate((c) => window.__game.startRace({ mode: 'time_attack', carId: 'roach', color: c || undefined }), process.env.PAINT);
  await page.waitForFunction(() => window.__game.phase === 'racing', null, { timeout: 60000 });
  await page.waitForTimeout(500);
  const state = () =>
    page.evaluate(() => {
      const g = window.__game, e = g.audio && g.audio.engine('player', g.player.sim.spec);
      return { flight: g.player.visual.flight, airborne: g.player.sim.airborne, flutter: e && e.flutterGain ? e.flutterGain.gain.value : -1 };
    });
  const before = await state();
  step = 'thrown';
  await page.evaluate(() => {
    const b = window.__game.player.sim.body, p = b.translation();
    // forward as the body stands (its +Z), at a town's speed, 9 m up
    const q = b.rotation();
    const fx = 2 * (q.x * q.z + q.w * q.y), fz = 1 - 2 * (q.x * q.x + q.y * q.y);
    b.setTranslation({ x: p.x, y: p.y + 9, z: p.z }, true);
    b.setLinvel({ x: fx * 14, y: 3, z: fz * 14 }, true);
  });
  let peak = 0, heard = 0;
  for (let k = 0; k < 4; k++) {
    await page.waitForTimeout(260);
    const s = await state();
    peak = Math.max(peak, s.flight);
    heard = Math.max(heard, s.flutter);
    fs.writeFileSync(path.join(OUT, `${backend}-air-${k}.png`), await page.screenshot({ type: 'png' }));
  }
  step = 'landed';
  await page.waitForTimeout(3500);
  const after = await state();
  fs.writeFileSync(path.join(OUT, `${backend}-landed.png`), await page.screenshot({ type: 'png' }));
  console.log(`${backend}: wing bones ${bones.join() || 'none'}; wings out before ${before.flight.toFixed(2)}, in the air ${peak.toFixed(2)}, after the landing ${after.flight.toFixed(2)} (airborne ${after.airborne})`);
  console.log(`the flutter's gain: before ${before.flutter.toFixed(3)}, in the air ${heard.toFixed(3)}, after the landing ${after.flutter.toFixed(3)}`);
  if (!(heard > 0.2) || !(before.flutter < 0.01) || !(after.flutter < 0.01)) seen['the flutter is not heard in the air only'] = 1;
  if (before.flight !== 0) seen['the wings were out on the ground before the throw'] = 1;
  if (peak < 0.95) seen[`the wings did not come out in the air (${peak.toFixed(2)})`] = 1;
  if (after.flight !== 0 && !after.airborne) seen[`the wings stayed out after the landing (${after.flight.toFixed(2)})`] = 1;
  const lines = Object.entries(seen);
  console.log(`${lines.length} distinct errors / warnings`);
  for (const [t, c] of lines.slice(0, 30)) console.log(`${c}× ${t}`);
  await browser.close();
  process.exit(lines.length ? 1 : 0);
})().catch((e) => {
  console.error(String(e).slice(0, 400));
  process.exit(1);
});
