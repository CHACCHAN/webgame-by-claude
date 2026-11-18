// The tanks' guns in the real game, on the host GPU (a build with the tanks: `VITE_TANKS=1 npm run build`):
// every tank in the garage → a rival battle in one of them, through the app's own race screen (HUD and gun sight
// mounted) → the sight laid on the rival by the game's own input path (`input.touchGun`, as a finger would) → a shot
// → the rival is put back on the road. Counts the GPU's validation errors and page errors on the way, as
// tools/gpu-errors.cjs does, and keeps pictures: garage, chase view, the gunner's sight, the muzzle flash, the
// impact, the HUD while loading.
//   node tools/tank-check.cjs <outDir>          exit code 1 when anything was reported or a step did not happen
// Env: URL (http://localhost:4173/), QUERY (e.g. ?webgl=1), TANK (type10), TIMES (night,dawn), COURSE,
// SET (JSON merged into the stored settings), PHONE=1 (844×390 with touch: the touch layout's picture and whether
// its parts overlap, instead of the above), CHROME, PW_MODULE.
// Serve with `API_PROXY=http://127.0.0.1:9 npx vite preview`; /api is also aborted in the browser.
const { chromium } = require(process.env.PW_MODULE || 'playwright');
const fs = require('fs');
const OUT = process.argv[2] || '.';
const TANK = process.env.TANK || 'type10';
const TIMES = (process.env.TIMES || 'night,dawn').split(',');
const PHONE = !!process.env.PHONE;
const TANKS = ['type10', 'type16', 'leopard2a5', 'm1a2', 't14'];

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({
    executablePath: process.env.CHROME || '/usr/bin/google-chrome',
    headless: true,
    args: ['--ignore-gpu-blocklist', '--use-angle=vulkan', '--enable-features=Vulkan'],
  });
  const ctx = await browser.newContext(PHONE ? { viewport: { width: 844, height: 390 }, hasTouch: true, isMobile: true } : { viewport: { width: 1280, height: 720 } });
  await ctx.route('**/api/**', (r) => r.abort());
  const page = await ctx.newPage();
  let step = 'boot';
  const seen = {};
  const failed = [];
  page.on('console', (m) => {
    if (m.type() !== 'error' && m.type() !== 'warning') return;
    const t = `${step}: ${m.text().slice(0, 160).replace(/\s+/g, ' ')}`;
    if (/net::ERR_FAILED|Failed to load resource|GL Driver Message \(OpenGL, Performance|ghost unavailable/.test(t)) return;
    seen[t] = (seen[t] || 0) + 1;
  });
  page.on('pageerror', (e) => (seen[`${step}: PAGE ERROR ${e.message.slice(0, 200)}`] = 1));
  const settings = { quality: 'high', timeOfDay: TIMES[0], masterVolume: 0, controlsGuide: false, ...(process.env.COURSE ? { courseId: process.env.COURSE } : {}), ...JSON.parse(process.env.SET || '{}') };
  await page.addInitScript((s) => localStorage.setItem('touge-settings', JSON.stringify({ state: s, version: 1 })), settings);
  await page.goto((process.env.URL || 'http://localhost:4173/') + (process.env.QUERY || ''));
  await page.waitForFunction(() => window.__game && window.__game.phase === 'attract', null, { timeout: 240000 });
  const backend = await page.evaluate(() => (window.__game.renderer.backend.isWebGPUBackend ? 'webgpu' : 'webgl2'));
  const shot = (name) => page.screenshot({ path: `${OUT}/${name}.jpg`, quality: 84, type: 'jpeg' });
  const want = (ok, what) => {
    if (!ok) failed.push(`${step}: ${what}`);
    console.log(`${ok ? 'ok  ' : 'FAIL'} ${step}: ${what}`);
  };

  /** A rival battle in the tank through the app's race screen; resolves at the green light. */
  const race = async (time) => {
    await page.evaluate(
      ([tank, tod]) => {
        const g = window.__game;
        if (g.timeOfDay !== tod) g.applyTimeOfDay(tod);
        window.__app.setState({ mode: 'rival', carId: tank, rivalLevel: 'rookie', paused: false, result: null });
        g.startRace({ mode: 'rival', carId: tank, rivalLevel: 'rookie' });
        window.__app.setState({ screen: 'race' });
        // what the gunnery asks of the game, counted
        const h = g.gunHost, n = (window.__guns = { fired: 0, struck: [], rival: 0, pauseOn: null });
        if (!h.__wrapped) {
          h.__wrapped = true;
          for (const k of ['fired', 'struck', 'respawnRival']) {
            const f = h[k];
            h[k] = (...a) => {
              const c = window.__guns;
              if (k === 'fired') c.fired++;
              if (k === 'struck') c.struck.push(a[1]);
              if (k === 'respawnRival') c.rival++;
              f(...a);
              // (hold the picture on the frame of the flash / the burst)
              if (c.pauseOn === k) setTimeout(() => window.__game.setPaused(true), 0);
            };
          }
        }
      },
      [TANK, time],
    );
    await page.waitForFunction(() => window.__game.phase === 'racing', null, { timeout: 60000 });
  };
  /** Lays the sight on the rival through the touch path until the gun is on it (true) or `ms` are over. */
  const lay = (ms) =>
    page.evaluate(
      (ms) =>
        new Promise((done) => {
          const g = window.__game, c = g.gunnery.control, t0 = performance.now();
          const tick = () => {
            const eye = g.gunnery.eye, at = g.rival.sim.position;
            const dx = at.x - eye.x, dy = at.y + 0.1 - eye.y, dz = at.z - eye.z;
            const yaw = Math.atan2(dx, dz), pitch = Math.atan2(dy, Math.hypot(dx, dz));
            // the error in the world; a finger's drag to the right turns the sight to the right (bearing down)
            const wrap = (a) => Math.atan2(Math.sin(a), Math.cos(a));
            const ey = wrap(yaw - c.world.yaw), ep = pitch - c.world.pitch;
            const mag = g.hud.gun.zoom;
            g.input.touchGun.dx = (-ey * 0.5 * mag) / 0.005;
            g.input.touchGun.dy = (-ep * 0.5 * mag) / 0.005;
            const on = Math.abs(ey) < 0.002 && Math.abs(ep) < 0.002 && c.off < 0.002 && c.lased;
            if (on || performance.now() - t0 > ms) return done({ on, range: c.range, off: c.off, ey, ep, dist: Math.hypot(dx, dy, dz) });
            requestAnimationFrame(tick);
          };
          tick();
        }),
      ms,
    );
  const guns = () => page.evaluate(() => ({ ...window.__guns, hud: window.__game.hud.gun && { ...window.__game.hud.gun }, rivalS: window.__game.rival?.proj.s, shells: window.__game.gunnery.shells.live.length }));
  const pauseOn = (k) => page.evaluate((k) => (window.__guns.pauseOn = k), k);
  const resume = () => page.evaluate(() => ((window.__guns.pauseOn = null), window.__game.setPaused(false)));
  const fire = async (on) => page.evaluate((on) => (window.__game.input.touchGun.fire = on), on);

  if (PHONE) {
    step = 'phone';
    await race(TIMES[0]);
    await page.waitForTimeout(2500);
    await shot('phone-race');
    const boxes = await page.evaluate(() => {
      const box = (s) => {
        const r = document.querySelector(s)?.getBoundingClientRect();
        return r ? { s, l: r.left, t: r.top, r: r.right, b: r.bottom } : null;
      };
      return ['.tc-top', '.tc-steer', '.tc-gun', '.tc-pedals', '.hud-tl', '.hud-br', '.hud-tr'].map(box);
    });
    const have = boxes.filter(Boolean);
    want(have.some((b) => b.s === '.tc-gun'), 'the gun buttons are there');
    for (const b of have) want(b.l >= 0 && b.t >= 0 && b.r <= 844 && b.b <= 390, `${b.s} is inside the screen (${Math.round(b.l)},${Math.round(b.t)} – ${Math.round(b.r)},${Math.round(b.b)})`);
    for (let i = 0; i < have.length; i++)
      for (let j = i + 1; j < have.length; j++) {
        const a = have[i], b = have[j];
        const over = Math.min(a.r, b.r) - Math.max(a.l, b.l) > 2 && Math.min(a.b, b.b) - Math.max(a.t, b.t) > 2;
        want(!over, `${a.s} and ${b.s} do not overlap`);
      }
    // the sight button is a switch; a drag on the right half moves the sight
    const before = await page.evaluate(() => window.__game.gunnery.control.sight.yaw);
    await page.touchscreen.tap(60, 200);
    await page.waitForTimeout(600);
    const g1 = await guns();
    want(g1.hud.scope, 'a tap on 照準 takes the sight up');
    await shot('phone-scope');
    await page.touchscreen.tap(60, 200);
    await page.waitForTimeout(400);
    want(!(await guns()).hud.scope, 'another tap puts it down');
    const cdp = await ctx.newCDPSession(page);
    const touch = (type, x, y) => cdp.send('Input.dispatchTouchEvent', { type, touchPoints: type === 'touchEnd' ? [] : [{ x, y, id: 1 }] });
    await touch('touchStart', 520, 120);
    for (let k = 1; k <= 10; k++) await touch('touchMove', 520 + k * 8, 120);
    await touch('touchEnd');
    await page.waitForTimeout(300);
    const after = await page.evaluate(() => window.__game.gunnery.control.sight.yaw);
    want(after < before - 0.2, `a drag to the right on the right half turns the sight to the right (${before.toFixed(2)} → ${after.toFixed(2)} rad)`);
    await page.touchscreen.tap(180, 200);
    await page.waitForTimeout(500);
    want((await guns()).fired === 1, 'a tap on 射撃 fires');
    await shot('phone-fired');
  } else {
    for (const id of TANKS) {
      step = `garage ${id}`;
      await page.evaluate((c) => window.__game.showGarage(c), id);
      await page.waitForTimeout(2500);
      await shot(`garage-${id}`);
    }
    for (const time of TIMES) {
      step = `race ${time}`;
      await race(time);
      const d0 = await page.evaluate(() => window.__game.camera.position.distanceTo(window.__game.player.sim.position));
      want(d0 < 40, `the camera is with the tank (${d0.toFixed(0)} m)`);
      // the tank stays on the grid (nobody steers it here); the rival drives off, until it is well ahead
      await page.waitForFunction(() => window.__game.rival.proj.s - window.__game.player.proj.s > 45, null, { timeout: 30000 });
      step = `aim ${time}`;
      const a = await lay(9000);
      want(a.on, `the sight is on the rival and the gun laid (range ${a.range.toFixed(0)} m, rival ${a.dist.toFixed(0)} m away)`);
      await shot(`${time}-chase`);
      step = `shot ${time}`;
      const s0 = (await guns()).rivalS;
      await pauseOn('fired');
      await fire(true);
      await page.waitForFunction(() => window.__game.paused, null, { timeout: 5000 }).catch(() => 0);
      await fire(false);
      await page.waitForTimeout(300);
      await shot(`${time}-flash`);
      await pauseOn('struck');
      await page.evaluate(() => window.__game.setPaused(false));
      await page.waitForFunction(() => window.__game.paused, null, { timeout: 8000 }).catch(() => 0);
      await page.waitForTimeout(300);
      await shot(`${time}-impact`);
      await resume();
      await page.waitForTimeout(900);
      let g = await guns();
      want(g.fired === 1, 'one shot was fired');
      want(g.struck.length === 1 && g.struck[0] === -1, `the shell met the rival (${JSON.stringify(g.struck)})`);
      want(g.rival === 1 && g.rivalS < s0 + 30, `the rival was put back on the road (s ${s0.toFixed(0)} → ${g.rivalS.toFixed(0)})`);
      want(g.hud.loaded < 1 && g.hud.reload > 0, `the next round is loading (${g.hud.reload.toFixed(1)} s to go)`);
      await shot(`${time}-loading`);
      // the gunner's sight, laid on the rival again; the next shot through it
      step = `sight ${time}`;
      await page.evaluate(() => (window.__game.input.touchGun.scope = true));
      const b = await lay(12000);
      await page.waitForFunction(() => window.__game.hud.gun.loaded >= 1, null, { timeout: 12000 }).catch(() => 0);
      await lay(4000);
      g = await guns();
      want(g.hud.scope && g.hud.zoom > 1, `through the sight at ×${g.hud.zoom} (laid: ${b.on})`);
      await shot(`${time}-sight`);
      await pauseOn('struck');
      await fire(true);
      await page.waitForFunction(() => window.__game.paused, null, { timeout: 8000 }).catch(() => 0);
      await fire(false);
      await page.waitForTimeout(300);
      await shot(`${time}-sight-impact`);
      await resume();
      await page.waitForTimeout(600);
      g = await guns();
      want(g.fired === 2, 'a second shot was fired through the sight');
      want(g.rival === 2, `the rival was put back again (${JSON.stringify(g.struck)})`);
      await page.evaluate(() => (window.__game.input.touchGun.scope = false));
      await page.waitForTimeout(500);
      want((await page.evaluate(() => window.__game.camera.fov)) > 50, 'the camera has its own lens back');
    }
    // the mouse: a click in the race takes the pointer, a movement turns the sight, Esc gives the pointer back
    step = 'pointer';
    await page.mouse.click(640, 300);
    await page.waitForTimeout(400);
    const locked = await page.evaluate(() => !!document.pointerLockElement);
    console.log(`     pointer lock after a click: ${locked}`);
    if (locked) {
      const y0 = await page.evaluate(() => window.__game.gunnery.control.sight.yaw);
      await page.mouse.move(740, 300, { steps: 5 });
      await page.waitForTimeout(300);
      const y1 = await page.evaluate(() => window.__game.gunnery.control.sight.yaw);
      console.log(`     sight bearing after a mouse movement to the right: ${y0.toFixed(3)} → ${y1.toFixed(3)} rad`);
      await page.keyboard.press('Escape');
      await page.waitForTimeout(500);
      const st = await page.evaluate(() => ({ locked: !!document.pointerLockElement, paused: window.__app.getState().paused }));
      want(!st.locked && st.paused, `Esc opens the pause menu and frees the pointer (${JSON.stringify(st)})`);
    }
    step = 'leave';
    await page.evaluate(() => {
      window.__app.setState({ paused: false, screen: 'title' });
      window.__game.setPaused(false);
      window.__game.startAttract();
    });
    await page.waitForTimeout(3000);
    want(await page.evaluate(() => !window.__game.gunnery && !window.__game.hud.gun && !window.__game.input.gunMode), 'nothing of the guns is left after the race');
  }
  const lines = Object.entries(seen);
  console.log(`${backend}: ${lines.length} distinct errors / warnings, ${failed.length} steps failed`);
  for (const [t, c] of lines.slice(0, 30)) console.log(`${c}× ${t}`);
  await browser.close();
  process.exit(lines.length || failed.length ? 1 : 0);
})().catch((e) => {
  console.error(String(e).slice(0, 600));
  process.exit(1);
});
