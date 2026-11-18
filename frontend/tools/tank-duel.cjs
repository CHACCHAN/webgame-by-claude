// A tank's gun between two games, on the host GPU: two browser contexts in one room of a stack of our own (NEVER
// the live one: the script makes players and a room), A in a tank, B in a car driven by the game (?autodrive=1).
// A lays its sight on B's vehicle as it is drawn on A's screen and fires; then B must be put back on the road by
// its OWN game (the hit is A's word, B checks it and respawns itself), and A must see it happen.
//   node tools/tank-duel.cjs <outDir>          exit code 1 when a step did not happen or a page reported an error
// The server must offer the tanks (`'tanks' => true` in backend/config/game.php of the tree the stack was built
// from) and the build too (`VITE_TANKS=1 npm run build`), served with the API proxied to that stack:
//   API_PROXY=http://127.0.0.1:<stack's port> npx vite preview --port <p> --strictPort --host 127.0.0.1
// Env: URL (required: the preview), TANK (type10), CAR (hayate), QUALITY (medium), SOFT=1 (software renderer:
// use QUALITY=low), CHROME, PW_MODULE.
const { chromium } = require(process.env.PW_MODULE || 'playwright');
const fs = require('fs');
const OUT = process.argv[2] || '.';
const URL_ = process.env.URL;
const TANK = process.env.TANK || 'type10';
const CAR = process.env.CAR || 'hayate';
const SOFT = !!process.env.SOFT;
// (two games on one software renderer take minutes to load)
const WAIT = SOFT ? 600000 : 240000;
if (!URL_ || /:8080\b/.test(URL_)) {
  console.error('URL=<a preview whose API is a test stack> (not the live one)');
  process.exit(1);
}

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({
    executablePath: process.env.CHROME || '/usr/bin/google-chrome',
    headless: true,
    // (SOFT=1: the software renderer, for the logic alone; no pictures worth keeping)
    args: process.env.SOFT ? ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] : ['--ignore-gpu-blocklist', '--use-angle=vulkan', '--enable-features=Vulkan'],
  });
  const seen = {};
  const failed = [];
  let step = 'boot';
  const want = (ok, what) => {
    if (!ok) failed.push(`${step}: ${what}`);
    console.log(`${ok ? 'ok  ' : 'FAIL'} ${step}: ${what}`);
  };
  const tag = String(Date.now() % 10000);
  const open = async (who, car, query) => {
    const ctx = await browser.newContext({ viewport: SOFT ? { width: 640, height: 360 } : { width: 960, height: 540 } });
    const page = await ctx.newPage();
    page.on('console', (m) => {
      if (m.type() !== 'error' && m.type() !== 'warning') return;
      const t = `${who} ${step}: ${m.text().slice(0, 160).replace(/\s+/g, ' ')}`;
      if (/Failed to load resource|GL Driver Message \(OpenGL, Performance|ghost unavailable/.test(t)) return;
      seen[t] = (seen[t] || 0) + 1;
    });
    page.on('pageerror', (e) => (seen[`${who} ${step}: PAGE ERROR ${e.message.slice(0, 200)}`] = 1));
    const settings = { quality: process.env.QUALITY || 'medium', timeOfDay: 'night', masterVolume: 0, controlsGuide: false, rivalVoice: 'off' };
    await page.addInitScript((s) => localStorage.setItem('touge-settings', JSON.stringify({ state: s, version: 1 })), settings);
    await page.goto(URL_ + query);
    await page.waitForFunction(() => window.__game && window.__game.phase === 'attract', null, { timeout: WAIT });
    await page.locator('.title h1').waitFor({ timeout: 60000 });
    await page.keyboard.press('Enter');
    await page.locator('.menu-list li', { hasText: 'ONLINE BATTLE' }).click();
    await page.locator('.ol-name').fill(`${who}${tag}`);
    await page.keyboard.press('Enter');
    await page.locator('.ol-me').waitFor({ timeout: 60000 });
    await page.evaluate((c) => window.__online.setState({ carId: c, carColor: null }), car);
    return page;
  };
  /** SOFT: a game that only has to wait draws nothing meanwhile (the other one gets the renderer) */
  const idle = (page, on) =>
    SOFT &&
    page.evaluate((on) => {
      const r = window.__game.renderer;
      r.__render ??= r.render;
      r.render = on ? () => {} : r.__render;
    }, on);
  const shot = (page, name) => page.screenshot({ path: `${OUT}/${name}.jpg`, quality: 84, type: 'jpeg' });
  /** counts what the gunnery asks of this page's game */
  const watch = (page) =>
    page.evaluate(() => {
      const h = window.__game.gunHost, n = (window.__guns = { fired: 0, struck: [], self: 0, sent: 0 });
      for (const k of ['fired', 'struck', 'respawnSelf', 'send']) {
        const f = h[k];
        h[k] = (...a) => {
          if (k === 'fired') n.fired++;
          if (k === 'struck') n.struck.push(a[1]);
          if (k === 'respawnSelf') n.self++;
          if (k === 'send') n.sent++;
          f(...a);
        };
      }
    });

  step = 'room';
  const a = await open('A', TANK, '');
  await a.locator('button', { hasText: 'ルームを作成' }).click();
  const code = (await a.locator('.ol-code-big b').textContent({ timeout: WAIT })).trim();
  await a.locator('.rt-badge', { hasText: 'LIVE' }).waitFor({ timeout: 60000 });
  console.log(`     room ${code} made by A`);
  await idle(a, true);
  const b = await open('B', CAR, '?autodrive=1');
  await b.locator('.ol-code').fill(code);
  await b.locator('button', { hasText: '参加' }).click();
  await b.locator('.ol-code-big b', { hasText: code }).waitFor({ timeout: WAIT });
  await idle(a, false);
  console.log('     B is in the room');
  const room = await a.evaluate(() => window.__online.getState().room.players.map((p) => ({ id: p.id, car: p.car_id, slot: p.slot })));
  want(room.length === 2 && room.some((p) => p.car === TANK) && room.some((p) => p.car === CAR), `room ${code}: ${JSON.stringify(room)}`);
  await shot(a, 'duel-a-room');
  await b.locator('.ol-ready:not([disabled])').click({ timeout: WAIT });
  await a.locator('.ol-start:not([disabled])').click({ timeout: 120000 });
  step = 'race';
  for (const p of [a, b]) await p.waitForFunction(() => window.__game.phase === 'racing', null, { timeout: WAIT });
  console.log('     both racing');
  await watch(a);
  await watch(b);
  const ids = await a.evaluate(() => ({ me: window.__game.onlineSelfId, peer: window.__game.remotes.standings()[0].id, gunnery: !!window.__game.gunnery?.control }));
  want(ids.gunnery, `A has its gun (A ${ids.me}, B ${ids.peer})`);
  want(await b.evaluate(() => !!window.__game.gunnery && !window.__game.gunnery.control), "B's game follows A's gun and has none of its own");
  // B drives off; A stays on the grid and turns its turret after it
  await a.waitForFunction(() => window.__game.remotes.standings()[0].s - window.__game.player.proj.s > 40, null, { timeout: 60000 });
  step = 'aim';
  const laid = await a.evaluate(
    ([peer, ms]) =>
      new Promise((done) => {
        const g = window.__game, c = g.gunnery.control, t0 = performance.now();
        const tick = () => {
          const eye = g.gunnery.eye, at = g.remotes.positionOf(peer);
          const dx = at.x - eye.x, dy = at.y + 0.5 - eye.y, dz = at.z - eye.z;
          const wrap = (x) => Math.atan2(Math.sin(x), Math.cos(x));
          const ey = wrap(Math.atan2(dx, dz) - c.world.yaw), ep = Math.atan2(dy, Math.hypot(dx, dz)) - c.world.pitch;
          g.input.touchGun.dx = (-ey * 0.5) / 0.005;
          g.input.touchGun.dy = (-ep * 0.5) / 0.005;
          const on = Math.abs(ey) < 0.003 && Math.abs(ep) < 0.003 && c.off < 0.003 && c.lased;
          if (on || performance.now() - t0 > ms) return done({ on, range: c.range, dist: Math.hypot(dx, dy, dz), turret: c.gun.yaw });
          requestAnimationFrame(tick);
        };
        tick();
      }),
    [ids.peer, 10000],
  );
  want(laid.on, `A's sight is on B and the gun laid (range ${laid.range.toFixed(0)} m, B ${laid.dist.toFixed(0)} m away, turret ${((laid.turret * 180) / Math.PI).toFixed(1)}°)`);
  // B sees A's turret where A has it (the state packet's 20 bits)
  await b.waitForTimeout(400);
  const seenTurret = await b.evaluate((id) => {
    const car = window.__game.remotes.cars.get(id), tank = car?.visual.rig.tank;
    return tank ? { yaw: tank.yaw, pitch: tank.pitch } : null;
  }, ids.me).catch(() => null);
  console.log(`     A's turret on B's screen: ${JSON.stringify(seenTurret)} (A: ${laid.turret.toFixed(3)} rad)`);
  await shot(a, 'duel-a-aim');
  step = 'shot';
  const before = await b.evaluate(() => ({ s: window.__game.player.proj.s, v: window.__game.player.sim.speed }));
  const peerS0 = await a.evaluate(() => window.__game.remotes.standings()[0].s);
  await a.evaluate(() => (window.__game.input.touchGun.fire = true));
  await a.waitForFunction(() => window.__guns.struck.length > 0, null, { timeout: 8000 }).catch(() => 0);
  await a.evaluate(() => (window.__game.input.touchGun.fire = false));
  await shot(a, 'duel-a-impact');
  await b.waitForFunction(() => window.__guns.self > 0, null, { timeout: 5000 }).catch(() => 0);
  await shot(b, 'duel-b-struck');
  const ga = await a.evaluate(() => ({ ...window.__guns }));
  const gb = await b.evaluate(() => ({ ...window.__guns, s: window.__game.player.proj.s, v: window.__game.player.sim.speed, refused: window.__game.gunnery.referee.refused }));
  want(ga.fired === 1 && ga.sent === 2, `A fired once and sent the shot and the hit (${JSON.stringify(ga)})`);
  want(ga.struck.length === 1 && ga.struck[0] === ids.peer, `on A's screen the shell met B (${JSON.stringify(ga.struck)})`);
  want(gb.fired === 1, "B's game saw A's shot");
  want(gb.self === 1 && gb.refused === 0, `B's game put B back on the road (${before.s.toFixed(0)} m at ${(before.v * 3.6).toFixed(0)} km/h → ${gb.s.toFixed(0)} m at ${(gb.v * 3.6).toFixed(0)} km/h)`);
  want(gb.struck.length === 1 && gb.struck[0] === ids.peer, `B's screen shows the burst on itself (${JSON.stringify(gb.struck)})`);
  await a.waitForTimeout(700);
  const peerS1 = await a.evaluate(() => window.__game.remotes.standings()[0].s);
  want(peerS1 < peerS0 + 12, `on A's screen B is back where it was put (s ${peerS0.toFixed(0)} → ${peerS1.toFixed(0)} m, 0.7 s later)`);
  await shot(a, 'duel-a-after');
  // B has no gun: nothing it could send would be believed; a second shot of A's waits for the loader
  const loading = await a.evaluate(() => ({ loaded: window.__game.hud.gun.loaded, reload: window.__game.hud.gun.reload, ammo: window.__game.hud.gun.ammo }));
  want(loading.loaded < 1 && loading.reload > 0, `A's next round is loading (${loading.reload.toFixed(1)} s, ${loading.ammo} left)`);

  const lines = Object.entries(seen);
  console.log(`${lines.length} distinct errors / warnings, ${failed.length} steps failed`);
  for (const [t, c] of lines.slice(0, 30)) console.log(`${c}× ${t}`);
  await browser.close();
  process.exit(lines.length || failed.length ? 1 : 0);
})().catch((e) => {
  console.error(String(e).slice(0, 600));
  process.exit(1);
});
