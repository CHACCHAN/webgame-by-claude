import { expect, test, type APIRequestContext, type Browser, type BrowserContextOptions, type Page } from '@playwright/test';
import { prepare, waitForTitle } from './helpers';

/** One player = one browser context (own localStorage, own player token). */
async function openPlayer(browser: Browser, name: string, options: BrowserContextOptions = { viewport: { width: 640, height: 360 } }) {
  // three WebGL clients share one CPU (SwiftShader): small canvases
  const ctx = await browser.newContext(options);
  const page = await ctx.newPage();
  await page.addInitScript(() => localStorage.setItem('touge-settings', JSON.stringify({ state: { quality: 'low', resolutionScale: 0.5, timeOfDay: 'night', masterVolume: 0, sfxVolume: 0, musicVolume: 0, assist: 1, autoShift: true, showGhost: false, showFps: false, cornerGuide: true }, version: 1 })));
  const errors = await prepare(page);
  await page.goto('/?autodrive=1&timescale=4');
  await waitForTitle(page);
  await page.keyboard.press('Enter');
  await page.locator('.menu-list li', { hasText: 'ONLINE BATTLE' }).click();
  await page.locator('.ol-name').fill(name);
  await page.keyboard.press('Enter');
  // (three software-rendered browsers at once: the entry can take a while to show)
  await expect(page.locator('.ol-me')).toContainText(name, { timeout: 90_000 });
  return { ctx, page, errors };
}

const game = (page: Page) => page.evaluate(() => {
  const g = (window as any).__game;
  return { phase: g.phase, course: g.course.id, remotes: g.remotes.standings(), standings: g.hud.online };
});

/**
 * A player straight through the API (no game): in the room, and only as far as the test says — the course loaded
 * (`loaded`), the 準備完了 button (`ready`), a finish time. Its car stays parked on its grid place.
 */
async function apiPlayer(request: APIRequestContext, name: string) {
  const reg = await request.post('/api/players', { data: { name } });
  const headers = { Authorization: `Bearer ${(await reg.json()).token}` };
  const me = (code: string, data: object) => request.patch(`/api/rooms/${code}/me`, { data, headers });
  return {
    join: (code: string) => request.post(`/api/rooms/${code}/join`, { data: { car_id: 'hayate' }, headers }),
    leave: (code: string) => request.post(`/api/rooms/${code}/leave`, { headers }),
    loaded: (code: string) => me(code, { loaded: true }),
    ready: (code: string) => me(code, { ready: true }),
    finish: async (code: string, timeMs: number) => {
      const room = await (await request.get(`/api/rooms/${code}`, { headers })).json();
      return request.post(`/api/rooms/${code}/finish`, { data: { race_no: room.race_no, time_ms: timeMs }, headers });
    },
  };
}

/** The stand-ins of the other cars in this client's physics world, by grid slot: where, and whether its player sends states. */
const standIns = (page: Page) => page.evaluate(() => {
  const g = (window as any).__game;
  const peers = g.remotes.standings();
  return g.remotes.colliders().map((c: any, k: number) => {
    const t = c.translation();
    const pr = g.track.project(t.x, t.y, t.z);
    return { slot: peers[k].slot as number, live: peers[k].lastHeard > 0, x: t.x as number, z: t.z as number, s: pr.s as number, lateral: pr.lateral as number, height: Math.abs(pr.height) };
  });
});

/** Puts the local car just before the finish, each slot on its own place (the cars are solid). */
const nearFinish = (page: Page) => page.evaluate(() => {
  const g = (window as any).__game, t = g.track, slot = g.currentConfig.online.slot;
  const s = t.finishS - 45 - slot * 9;
  g.player.sim.reset(t.pointAt(s, [-2.7, 2.7, 0][slot % 3]), t.headingAt(s), 20);
  g.player.proj.index = -1;
  g.player.lastSafe = { s, t: g.time };
});

const TIME = /^\d:\d\d\.\d{3}$/;

test('online battle: five in one room (three games, two more through the API), everyone ready, race, rematch', async ({ browser, request }) => {
  test.setTimeout(1_500_000);
  const tag = String(Date.now() % 10000);
  const host = await openPlayer(browser, `HOST${tag}`);
  await host.page.locator('.ol-courses .chip', { hasText: '天狼スカイライン' }).click();
  await host.page.locator('.ol-tod .chip', { hasText: '深夜・雨' }).click();
  await host.page.locator('button', { hasText: 'ルームを作成' }).click();
  const code = (await host.page.locator('.ol-code-big b').textContent({ timeout: 180_000 }))!.trim();
  expect(code).toMatch(/^[A-Z2-9]{4}$/);
  await expect(host.page.locator('.rt-badge')).toHaveText('LIVE', { timeout: 60_000 });
  const start = host.page.locator('.ol-start');
  // five seats; alone, the host cannot start yet
  await expect(host.page.locator('.ol-slots li')).toHaveCount(5);
  await expect(start).toBeDisabled();
  await expect(start).toHaveText('2人以上でスタートできます');
  // nor while another player's game is still loading the course
  const slow = await apiPlayer(request, `SLOW${tag}`);
  expect((await slow.join(code)).status()).toBe(200);
  await expect(host.page.locator('.ol-slots em.loading')).toHaveCount(1, { timeout: 30_000 });
  await expect(start).toBeDisabled();
  await expect(start).toHaveText('読み込み待ち… あと1人');
  // nobody is ready before their game has loaded; and loaded is not ready: the player has to press the button
  expect((await slow.ready(code)).status()).toBe(409);
  expect((await slow.loaded(code)).status()).toBe(200);
  await expect(host.page.locator('.ol-slots em.not-ready')).toHaveCount(1, { timeout: 30_000 });
  await expect(start).toBeDisabled();
  await expect(start).toHaveText('準備完了待ち… あと1人');
  // (Enter is the start button: nothing yet)
  await host.page.keyboard.press('Enter');
  expect(await host.page.evaluate(() => (window as any).__game.phase)).toBe('garage');
  expect((await slow.leave(code)).status()).toBe(200);
  await expect(host.page.locator('.ol-slots li:not(.empty)')).toHaveCount(1, { timeout: 30_000 });

  const guests = [];
  for (const name of [`B${tag}`, `C${tag}`]) {
    const g = await openPlayer(browser, name);
    await g.page.locator('.ol-code').fill(code);
    await g.page.locator('button', { hasText: '参加' }).click();
    await expect(g.page.locator('.ol-code-big b')).toHaveText(code, { timeout: 180_000 });
    guests.push(g);
  }
  const [b, c] = guests;
  const all = [host, ...guests];
  // two more players without a game: the room is full with five
  const silent = [await apiPlayer(request, `D${tag}`), await apiPlayer(request, `E${tag}`)];
  for (const p of silent) expect((await p.join(code)).status()).toBe(200);
  // everyone sees the full room (pushed over the socket or picked up by polling)
  for (const p of all) await expect(p.page.locator('.ol-slots li:not(.empty)')).toHaveCount(5, { timeout: 30_000 });
  // a sixth player is turned away
  const full = await (await apiPlayer(request, 'SIXTH')).join(code);
  expect(full.status()).toBe(409);
  expect((await full.json()).message).toContain('満員');

  // the start waits until every game has loaded the course (the guests came from another course) …
  for (const p of silent) expect((await p.loaded(code)).status()).toBe(200);
  await expect(host.page.locator('.ol-slots em.loading')).toHaveCount(0, { timeout: 60_000 });
  // … and until every guest has pressed 準備完了
  await expect(start).toBeDisabled();
  await expect(start).toHaveText('準備完了待ち… あと4人');
  for (const p of silent) expect((await p.ready(code)).status()).toBe(200);
  await expect(start).toHaveText('準備完了待ち… あと2人', { timeout: 30_000 });
  // a guest has the ready button instead of the start button
  for (const p of guests) {
    await expect(p.page.locator('.ol-start')).toHaveCount(0);
    await expect(p.page.locator('.ol-ready')).toBeEnabled({ timeout: 60_000 });
    await expect(p.page.locator('.ol-ready')).toHaveText('準備完了');
    await expect(p.page.locator('.ol-waiting')).toHaveCount(0);
  }
  await b.page.locator('.ol-ready').click();
  await expect(b.page.locator('.ol-ready')).toHaveText('準備完了を取り消す', { timeout: 30_000 });
  await expect(b.page.locator('.ol-waiting')).toBeVisible();
  await expect(b.page.locator('.ol-slots li.me em.ready')).toHaveText('準備完了 ✓');
  await expect(start).toHaveText('準備完了待ち… あと1人', { timeout: 30_000 });
  await expect(host.page.locator('.ol-slots em.ready')).toHaveCount(3);
  // looking around in the car select enters nothing (the ready stays); the car confirmed there takes the ready
  // back; Enter gives it again
  await b.page.locator('.ol-vehicle').click();
  await b.page.locator('.vp-tile[data-id="shiden"]').click();
  await expect(b.page.locator('.vp .car-name')).toHaveText('RX-7 (FD3S)');
  expect(await b.page.evaluate(() => (window as any).__game.garageCar.spec.id)).toBe('shiden');
  await b.page.waitForTimeout(1500);
  await expect(host.page.locator('.ol-slots em.ready')).toHaveCount(3);
  await b.page.locator('.vp .cta', { hasText: 'この車でエントリー' }).click();
  await expect(b.page.locator('.vp')).toHaveCount(0);
  await expect(b.page.locator('.ol-vehicle')).toContainText('RX-7 (FD3S)');
  await expect(b.page.locator('.ol-ready')).toHaveText('準備完了', { timeout: 30_000 });
  await expect(start).toHaveText('準備完了待ち… あと2人', { timeout: 30_000 });
  await expect(b.page.locator('.ol-ready')).toBeEnabled();
  await b.page.keyboard.press('Enter');
  await expect(b.page.locator('.ol-ready')).toHaveText('準備完了を取り消す', { timeout: 30_000 });
  await expect(start).toBeDisabled();
  await c.page.locator('.ol-ready').click();
  await expect(c.page.locator('.ol-waiting')).toBeVisible({ timeout: 30_000 });

  // all ready: the host starts (Enter is the start button)
  await expect(start).toHaveText('レース開始', { timeout: 30_000 });
  await expect(start).toBeEnabled();
  await host.page.keyboard.press('Enter');
  for (const p of all) {
    await p.page.waitForFunction(() => (window as any).__game.phase === 'racing', null, { timeout: 120_000 });
    const st = await game(p.page);
    expect(st.course).toBe('tenrou-skyline');
    // everyone races in the host's conditions, whatever their own last choice was
    expect(await p.page.evaluate(() => (window as any).__game.timeOfDay)).toBe('rain');
    expect(st.remotes).toHaveLength(4);
  }
  // the connection readout is off until asked for (N key), then lists the links
  await expect(all[0].page.locator('.net-stats')).toBeEmpty();
  await all[0].page.keyboard.press('n');
  await expect(all[0].page.locator('.net-stats')).toContainText('往復', { timeout: 60_000 });
  await all[0].page.keyboard.press('n');
  await expect(all[0].page.locator('.net-stats')).toBeEmpty({ timeout: 60_000 });
  // car states flow between the three games and the live order lists all five
  const parked: { slot: number; x: number; z: number; s: number; lateral: number }[][] = [];
  for (const p of all) {
    await p.page.waitForFunction(() => (window as any).__game.remotes.standings().filter((r: any) => r.lastHeard > 0 && r.s > 0).length === 2, null, { timeout: 120_000 });
    await expect(p.page.locator('.online-standings li')).toHaveCount(5);
    // each of the two other games is a link with its own clock exchange and statistics; nothing malformed came in
    await p.page.waitForFunction(() => (window as any).__game.net.stats().filter((s: any) => s.synced && s.received > 5).length === 2, null, { timeout: 120_000 });
    const link = await p.page.evaluate(() => {
      const net = (window as any).__game.net;
      return { rejected: net.rejected as number, stats: (net.stats() as any[]).filter((s) => s.synced) };
    });
    expect(link.rejected).toBe(0);
    for (const s of link.stats) {
      expect(s.rtt).toBeGreaterThan(0);
      expect(s.rtt).toBeLessThan(2000);
      expect(s.loss).toBeLessThan(0.5);
    }
    // the other four cars are solid stand-ins in this client's physics world, riding on the road: the two games' cars
    // at their network pose, the two players without a game still on their grid places
    const solid = await standIns(p.page);
    expect(solid).toHaveLength(4);
    for (const s of solid) {
      expect(s.s).toBeGreaterThan(0);
      expect(s.height).toBeLessThan(3);
    }
    parked.push(solid.filter((s: any) => !s.live).sort((p, q) => p.slot - q.slot));
  }
  // the grid is the same on every client: the parked cars (slots 3 and 4: the second row of 3 + 2) stand in the same
  // place on all three screens, side by side behind the start line and clear of each other
  for (const seen of parked) {
    expect(seen.map((s) => s.slot)).toEqual([3, 4]);
    for (const [k, s] of seen.entries()) {
      expect(Math.hypot(s.x - parked[0][k].x, s.z - parked[0][k].z)).toBeLessThan(0.05);
      expect(Math.abs(s.lateral)).toBeLessThan(4);
    }
    expect(Math.abs(seen[0].s - seen[1].s)).toBeLessThan(0.1);
    expect(seen[1].lateral - seen[0].lateral).toBeGreaterThan(2.5);
    expect(await host.page.evaluate(() => (window as any).__game.track.startS) - seen[0].s).toBeGreaterThan(10);
  }
  // shortcut to the finish once the race clock passes the course minimum, so the results
  // flow is covered without driving 2.4 km at ~1 fps
  for (const p of all) {
    await p.page.waitForFunction(() => (window as any).__game.hud.raceTime > 47, null, { timeout: 300_000, polling: 500 });
    await nearFinish(p.page);
  }
  // the room is not finished before the two without a game are in as well
  for (const [k, p] of silent.entries()) expect((await p.finish(code, 61_000 + k * 1_500)).status()).toBe(200);
  for (const p of all) await expect(p.page.locator('.online-results')).toBeVisible({ timeout: 300_000 });
  for (const p of all) {
    await expect(p.page.locator('.ol-standings li .time')).toHaveText([TIME, TIME, TIME, TIME, TIME], { timeout: 120_000 });
  }
  await expect(host.page.locator('button', { hasText: 'もう一度走る' })).toBeVisible();
  // rematch takes everyone back to the room, where the readies have to be given again
  await host.page.locator('button', { hasText: 'もう一度走る' }).click();
  for (const p of all) await expect(p.page.locator('.ol-code-big b')).toHaveText(code, { timeout: 30_000 });
  await expect(start).toBeDisabled();
  await expect(start).toHaveText('準備完了待ち… あと4人', { timeout: 30_000 });
  for (const p of guests) await expect(p.page.locator('.ol-ready')).toHaveText('準備完了', { timeout: 30_000 });
  for (const p of all) expect(p.errors).toEqual([]);
  for (const p of all) await p.ctx.close();
});

test('online battle on a phone: five seats, the live order and five results fit the screen', async ({ browser, request }, testInfo) => {
  test.setTimeout(900_000);
  const tag = String(Date.now() % 10000);
  // a phone held sideways, as in mobile.spec.ts
  const host = await openPlayer(browser, `PHONE${tag}`, { viewport: { width: 844, height: 390 }, hasTouch: true, isMobile: true });
  const page = host.page;
  const tap = async (sel: string) => {
    const box = (await page.locator(sel).first().boundingBox())!;
    await page.touchscreen.tap(box.x + box.width / 2, box.y + box.height / 2);
  };
  const noSideScroll = () => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);
  await expect(page.locator('.app')).toHaveClass(/touch/);
  await page.locator('.ol-courses .chip', { hasText: '天狼スカイライン' }).click();
  await page.locator('button', { hasText: 'ルームを作成' }).click();
  const code = (await page.locator('.ol-code-big b').textContent({ timeout: 180_000 }))!.trim();
  const others = [];
  for (const name of ['B', 'C', 'D', 'E']) {
    // (a long name: sixteen characters, the limit)
    const p = await apiPlayer(request, `${name}${tag}-長い名前の走り屋さん`.slice(0, 16));
    expect((await p.join(code)).status()).toBe(200);
    expect((await p.loaded(code)).status()).toBe(200);
    others.push(p);
  }
  // the room: all five seats and the start button in view at once, nothing cut off to the side
  await expect(page.locator('.ol-slots li:not(.empty)')).toHaveCount(5, { timeout: 30_000 });
  await page.locator('.ol-panel').evaluate((el) => el.scrollTo(0, 0));
  const box = async (sel: string) => (await page.locator(sel).first().boundingBox())!;
  const bottom = async (sel: string) => { const b = await box(sel); return b.y + b.height; };
  for (let k = 0; k < 5; k++) await expect(page.locator('.ol-slots li').nth(k)).toBeInViewport({ ratio: 1 });
  await expect(page.locator('.ol-start')).toBeInViewport({ ratio: 1 });
  // (the buttons stay at the panel's foot: not over the seats)
  expect(await bottom('.ol-slots')).toBeLessThanOrEqual((await box('.ol-actions')).y);
  await expect(page.locator('.ol-start')).toHaveText('準備完了待ち… あと4人');
  await expect(page.locator('.ol-slots em.not-ready')).toHaveCount(4);
  expect(await noSideScroll()).toBe(true);
  await page.screenshot({ path: testInfo.outputPath('phone-room.png') });
  for (const p of others) expect((await p.ready(code)).status()).toBe(200);
  await expect(page.locator('.ol-slots em.ready')).toHaveCount(4, { timeout: 30_000 });
  await expect(page.locator('.ol-start')).toHaveText('レース開始');
  await page.screenshot({ path: testInfo.outputPath('phone-room-ready.png') });
  // the back button leaves the room (Esc on a keyboard) … not pressed here; the start button by a tap
  await expect(page.locator('.touch-back')).toBeVisible();
  await tap('.ol-start');
  await page.waitForFunction(() => (window as any).__game.phase === 'racing', null, { timeout: 180_000 });

  // the race: the live order of five under the clock, clear of the steering pad, the buttons and the bend warning
  await expect(page.locator('.online-standings li')).toHaveCount(5, { timeout: 60_000 });
  const order = await box('.online-standings'), steer = await box('.tc-steer'), note = await box('.corner-note'), top = await box('.tc-top');
  expect(order.y).toBeGreaterThanOrEqual(0);
  expect(order.y + order.height).toBeLessThanOrEqual(steer.y);
  expect(order.x + order.width).toBeLessThanOrEqual(Math.min(note.x, top.x));
  // (the rows are rebuilt as the gaps change: measured in one go, not one locator after another)
  const rows = await page.evaluate(() => [...document.querySelectorAll('.online-standings li')].map((li) => {
    const r = li.getBoundingClientRect();
    return r.left >= 0 && r.top >= 0 && r.right <= window.innerWidth && r.bottom <= window.innerHeight && r.height > 8;
  }));
  expect(rows).toEqual([true, true, true, true, true]);
  expect(await noSideScroll()).toBe(true);
  await page.screenshot({ path: testInfo.outputPath('phone-race.png') });

  // the results: five rows and the buttons in view
  await page.waitForFunction(() => (window as any).__game.hud.raceTime > 26, null, { timeout: 300_000, polling: 500 });
  await nearFinish(page);
  for (const [k, p] of others.entries()) expect((await p.finish(code, 58_000 + k * 1_300)).status()).toBe(200);
  await expect(page.locator('.online-results')).toBeVisible({ timeout: 300_000 });
  await expect(page.locator('.ol-standings li .time')).toHaveText([TIME, TIME, TIME, TIME, TIME], { timeout: 120_000 });
  await page.locator('.ol-panel').evaluate((el) => el.scrollTo(0, 0));
  for (let k = 0; k < 5; k++) await expect(page.locator('.ol-standings li').nth(k)).toBeInViewport({ ratio: 1 });
  await expect(page.locator('button', { hasText: 'もう一度走る' })).toBeInViewport({ ratio: 1 });
  expect(await bottom('.ol-standings')).toBeLessThanOrEqual((await box('.ol-actions')).y);
  expect(await noSideScroll()).toBe(true);
  await page.screenshot({ path: testInfo.outputPath('phone-results.png') });
  expect(host.errors).toEqual([]);
  await host.ctx.close();
});
