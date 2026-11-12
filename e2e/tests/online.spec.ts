import { expect, test, type APIRequestContext, type Browser, type BrowserContextOptions, type Page } from '@playwright/test';
import { prepare, waitForTitle } from './helpers';

// Time limits: twice what the software renderer needed on 11-10. On 11-11 the same machine drew 1.3–1.6× slower and
// a guest's course took over three minutes to load next to two other games.
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
  await expect(page.locator('.ol-me')).toContainText(name, { timeout: 180_000 });
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
    join: (code: string, car = 'hayate') => request.post(`/api/rooms/${code}/join`, { data: { car_id: car }, headers }),
    leave: (code: string) => request.post(`/api/rooms/${code}/leave`, { headers }),
    loaded: (code: string) => me(code, { loaded: true }),
    /** as a game reports it: the course it has loaded (dropped by the server when the room is on another one) */
    loadedOn: (code: string, track: string) => me(code, { loaded: true, track_id: track }),
    change: (code: string, data: object) => request.patch(`/api/rooms/${code}`, { data, headers }),
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
  test.setTimeout(2_400_000);
  const tag = String(Date.now() % 10000);
  const host = await openPlayer(browser, `HOST${tag}`);
  await host.page.locator('.ol-courses .chip', { hasText: '天狼スカイライン' }).click();
  await host.page.locator('.ol-tod .chip', { hasText: '深夜・雨' }).click();
  await host.page.locator('button', { hasText: 'ルームを作成' }).click();
  const code = (await host.page.locator('.ol-code-big b').textContent({ timeout: 420_000 }))!.trim();
  expect(code).toMatch(/^[A-Z2-9]{4}$/);
  await expect(host.page.locator('.rt-badge')).toHaveText('LIVE', { timeout: 120_000 });
  const start = host.page.locator('.ol-start');
  // five seats; alone, the host cannot start yet
  await expect(host.page.locator('.ol-slots li')).toHaveCount(5);
  await expect(start).toBeDisabled();
  await expect(start).toHaveText('2人以上でスタートできます');
  // nor while another player's game is still loading the course
  const slow = await apiPlayer(request, `SLOW${tag}`);
  expect((await slow.join(code)).status()).toBe(200);
  await expect(host.page.locator('.ol-slots em.loading')).toHaveCount(1, { timeout: 60_000 });
  await expect(start).toBeDisabled();
  await expect(start).toHaveText('読み込み待ち… あと1人');
  // nobody is ready before their game has loaded; and loaded is not ready: the player has to press the button
  expect((await slow.ready(code)).status()).toBe(409);
  expect((await slow.loaded(code)).status()).toBe(200);
  await expect(host.page.locator('.ol-slots em.not-ready')).toHaveCount(1, { timeout: 60_000 });
  await expect(start).toBeDisabled();
  await expect(start).toHaveText('準備完了待ち… あと1人');
  // (Enter is the start button: nothing yet)
  await host.page.keyboard.press('Enter');
  expect(await host.page.evaluate(() => (window as any).__game.phase)).toBe('garage');
  expect((await slow.leave(code)).status()).toBe(200);
  await expect(host.page.locator('.ol-slots li:not(.empty)')).toHaveCount(1, { timeout: 60_000 });

  const guests = [];
  for (const name of [`B${tag}`, `C${tag}`]) {
    const g = await openPlayer(browser, name);
    await g.page.locator('.ol-code').fill(code);
    await g.page.locator('button', { hasText: '参加' }).click();
    await expect(g.page.locator('.ol-code-big b')).toHaveText(code, { timeout: 420_000 });
    guests.push(g);
  }
  const [b, c] = guests;
  const all = [host, ...guests];
  // two more players without a game: the room is full with five
  const silent = [await apiPlayer(request, `D${tag}`), await apiPlayer(request, `E${tag}`)];
  for (const p of silent) expect((await p.join(code)).status()).toBe(200);
  // everyone sees the full room (pushed over the socket or picked up by polling)
  for (const p of all) await expect(p.page.locator('.ol-slots li:not(.empty)')).toHaveCount(5, { timeout: 60_000 });
  // a sixth player is turned away
  const full = await (await apiPlayer(request, 'SIXTH')).join(code);
  expect(full.status()).toBe(409);
  expect((await full.json()).message).toContain('満員');

  // the start waits until every game has loaded the course (the guests came from another course) …
  for (const p of silent) expect((await p.loaded(code)).status()).toBe(200);
  await expect(host.page.locator('.ol-slots em.loading')).toHaveCount(0, { timeout: 120_000 });
  // … and until every guest has pressed 準備完了
  await expect(start).toBeDisabled();
  await expect(start).toHaveText('準備完了待ち… あと4人');
  for (const p of silent) expect((await p.ready(code)).status()).toBe(200);
  await expect(start).toHaveText('準備完了待ち… あと2人', { timeout: 60_000 });
  // a guest has the ready button instead of the start button
  for (const p of guests) {
    await expect(p.page.locator('.ol-start')).toHaveCount(0);
    await expect(p.page.locator('.ol-ready')).toBeEnabled({ timeout: 120_000 });
    await expect(p.page.locator('.ol-ready')).toHaveText('準備完了');
    await expect(p.page.locator('.ol-waiting')).toHaveCount(0);
  }
  await b.page.locator('.ol-ready').click();
  await expect(b.page.locator('.ol-ready')).toHaveText('準備完了を取り消す', { timeout: 60_000 });
  await expect(b.page.locator('.ol-waiting')).toBeVisible();
  await expect(b.page.locator('.ol-slots li.me em.ready')).toHaveText('準備完了 ✓');
  await expect(start).toHaveText('準備完了待ち… あと1人', { timeout: 60_000 });
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
  await expect(b.page.locator('.ol-ready')).toHaveText('準備完了', { timeout: 240_000 });
  await expect(start).toHaveText('準備完了待ち… あと2人', { timeout: 60_000 });
  await expect(b.page.locator('.ol-ready')).toBeEnabled();
  await b.page.keyboard.press('Enter');
  await expect(b.page.locator('.ol-ready')).toHaveText('準備完了を取り消す', { timeout: 240_000 });
  await expect(start).toBeDisabled();
  await c.page.locator('.ol-ready').click();
  await expect(c.page.locator('.ol-waiting')).toBeVisible({ timeout: 60_000 });

  // all ready: the host starts (Enter is the start button)
  await expect(start).toHaveText('レース開始', { timeout: 60_000 });
  await expect(start).toBeEnabled();
  await host.page.keyboard.press('Enter');
  for (const p of all) {
    await p.page.waitForFunction(() => (window as any).__game.phase === 'racing', null, { timeout: 240_000 });
    const st = await game(p.page);
    expect(st.course).toBe('tenrou-skyline');
    // everyone races in the host's conditions, whatever their own last choice was
    expect(await p.page.evaluate(() => (window as any).__game.timeOfDay)).toBe('rain');
    expect(st.remotes).toHaveLength(4);
  }
  // the connection readout is off until asked for (N key), then lists the links
  await expect(all[0].page.locator('.net-stats')).toBeEmpty();
  await all[0].page.keyboard.press('n');
  await expect(all[0].page.locator('.net-stats')).toContainText('往復', { timeout: 120_000 });
  await all[0].page.keyboard.press('n');
  await expect(all[0].page.locator('.net-stats')).toBeEmpty({ timeout: 120_000 });
  // car states flow between the three games and the live order lists all five
  const parked: { slot: number; x: number; z: number; s: number; lateral: number }[][] = [];
  for (const p of all) {
    await p.page.waitForFunction(() => (window as any).__game.remotes.standings().filter((r: any) => r.lastHeard > 0 && r.s > 0).length === 2, null, { timeout: 240_000 });
    await expect(p.page.locator('.online-standings li')).toHaveCount(5);
    // each of the two other games is a link with its own clock exchange and statistics; nothing malformed came in
    await p.page.waitForFunction(() => (window as any).__game.net.stats().filter((s: any) => s.synced && s.received > 5).length === 2, null, { timeout: 240_000 });
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
    await p.page.waitForFunction(() => (window as any).__game.hud.raceTime > 47, null, { timeout: 480_000, polling: 500 });
    await nearFinish(p.page);
  }
  // the room is not finished before the two without a game are in as well
  for (const [k, p] of silent.entries()) expect((await p.finish(code, 61_000 + k * 1_500)).status()).toBe(200);
  for (const p of all) await expect(p.page.locator('.online-results')).toBeVisible({ timeout: 480_000 });
  for (const p of all) {
    await expect(p.page.locator('.ol-standings li .time')).toHaveText([TIME, TIME, TIME, TIME, TIME], { timeout: 240_000 });
  }
  await expect(host.page.locator('button', { hasText: 'もう一度走る' })).toBeVisible();
  // rematch takes everyone back to the room, where the readies have to be given again (three games change their
  // scene at once here: under the software renderer each page stood still for about 100 s)
  await host.page.locator('button', { hasText: 'もう一度走る' }).click();
  for (const p of all) await expect(p.page.locator('.ol-code-big b')).toHaveText(code, { timeout: 300_000 });
  await expect(start).toBeDisabled();
  await expect(start).toHaveText('準備完了待ち… あと4人', { timeout: 300_000 });
  for (const p of guests) await expect(p.page.locator('.ol-ready')).toHaveText('準備完了', { timeout: 300_000 });
  // … and where the five vehicles stand on the course again (the waiting room's line-up)
  for (const p of all) {
    await p.page.waitForFunction(() => {
      const s = (window as any).__game.lobbyState;
      return s?.length === 5 && s.every((e: any) => e.carId && !e.pending);
    }, null, { timeout: 240_000 });
  }
  for (const p of all) expect(p.errors).toEqual([]);
  for (const p of all) await p.ctx.close();
});

/** The waiting room's line-up on this screen: what stands in each seat (null when the line-up is not up). */
const lineup = (page: Page) => page.evaluate(() => (window as any).__game.lobbyState as { slot: number; carId: string | null; livery: string | null; browsing: boolean; pending: string | null }[] | null);
/** Waits until the seat shows this vehicle (its model swapped in), looked at or confirmed. */
const seat = (page: Page, slot: number, carId: string, browsing = false) => page.waitForFunction(([slot, carId, browsing]) => {
  const e = (window as any).__game.lobbyState?.find((x: any) => x.slot === slot);
  return !!e && e.carId === carId && e.browsing === browsing && !e.pending;
}, [slot, carId, browsing] as const, { timeout: 240_000 });
/** Line-ups left in the scene (there is one while the waiting room is up, none otherwise). */
const lineupsInScene = (page: Page) => page.evaluate(() => {
  let n = 0;
  (window as any).__game.root.traverse((o: any) => { if (o.name === 'lobby-lineup') n++; });
  return n;
});

test('online waiting room: the members\' vehicles stand on the course; one being looked at shows on the other screen, a confirmed one takes its place', async ({ browser, request }) => {
  test.setTimeout(2_000_000);
  const tag = String(Date.now() % 10000);
  const host = await openPlayer(browser, `HOST${tag}`);
  await host.page.locator('button', { hasText: 'ルームを作成' }).click();
  const code = (await host.page.locator('.ol-code-big b').textContent({ timeout: 420_000 }))!.trim();
  await expect(host.page.locator('.rt-badge')).toHaveText('LIVE', { timeout: 120_000 });
  const start = host.page.locator('.ol-start');
  // alone: the host's own car where the garage's car stood (the game is still in its garage phase)
  await seat(host.page, 0, 'hayate');
  expect(await lineup(host.page)).toHaveLength(1);
  expect(await host.page.evaluate(() => (window as any).__game.phase)).toBe('garage');
  // a member without a game, in a train, and a guest with a game: three vehicles on both screens
  const silent = await apiPlayer(request, `T${tag}`);
  expect((await silent.join(code, 'e235')).status()).toBe(200);
  const guest = await openPlayer(browser, `G${tag}`);
  await guest.page.locator('.ol-code').fill(code);
  await guest.page.locator('button', { hasText: '参加' }).click();
  await expect(guest.page.locator('.ol-code-big b')).toHaveText(code, { timeout: 420_000 });
  await expect(guest.page.locator('.rt-badge')).toHaveText('LIVE', { timeout: 120_000 });
  const both = [host, guest];
  for (const p of both) {
    await seat(p.page, 0, 'hayate');
    await seat(p.page, 1, 'e235');
    await seat(p.page, 2, 'hayate');
    expect(await lineup(p.page)).toHaveLength(3);
    expect(await lineupsInScene(p.page)).toBe(1);
  }
  // everyone ready: the host could start
  expect((await silent.loaded(code)).status()).toBe(200);
  expect((await silent.ready(code)).status()).toBe(200);
  await guest.page.locator('.ol-ready').click();
  await expect(start).toHaveText('レース開始', { timeout: 120_000 });

  // the guest opens the car select and looks at another vehicle: on their own screen the garage shows it, on the
  // host's it stands in their seat, marked 選択中 …
  const garageCar = (page: Page) => page.evaluate(() => (window as any).__game.garageCar?.spec.id ?? null);
  await guest.page.locator('.ol-vehicle').click();
  await guest.page.locator('.vp-tile[data-id="roach"]').click();
  await expect.poll(() => garageCar(guest.page), { timeout: 120_000 }).toBe('roach');
  expect(await lineup(guest.page)).toBeNull();
  await seat(host.page, 2, 'roach', true);
  const row = host.page.locator('.ol-slots li', { hasText: `G${tag}` });
  await expect(row.locator('em.choosing')).toHaveText('選択中');
  await expect(row.locator('span')).toHaveText('ゴキブリ');
  await expect(guest.page.locator('.ol-slots li.me em.choosing')).toHaveCount(1);
  // … and looking is not choosing: the guest is still ready, the host may still start
  await expect(start).toHaveText('レース開始');
  await expect(start).toBeEnabled();
  await expect(guest.page.locator('.ol-ready')).toHaveText('準備完了を取り消す');
  // the select is left without a choice: the line-up is back on the guest's screen, the entered car in the seat
  await guest.page.keyboard.press('Escape');
  await expect(guest.page.locator('.vp')).toHaveCount(0);
  for (const p of both) await seat(p.page, 2, 'hayate');
  expect(await lineupsInScene(guest.page)).toBe(1);
  await expect(guest.page.locator('.ol-code-big b')).toHaveText(code);
  await expect(host.page.locator('.ol-slots em.choosing')).toHaveCount(0);
  await expect(row.locator('em.ready')).toHaveCount(1);
  await expect(row.locator('span')).toHaveText('SPRINTER TRUENO AE86');

  // the paint is chosen in the same select: confirmed, the seat wears it on both screens, and the ready stays
  // (another paint changes nothing of the race); the others without a paint keep their seat's colour
  await guest.page.locator('.ol-vehicle').click();
  await guest.page.locator('.vp .colors .swatch').nth(1).click();
  await expect(guest.page.locator('.vp .colors .swatch.on')).toHaveAttribute('style', /179, 18, 28|#b3121c/i);
  await guest.page.locator('.vp .cta', { hasText: 'この車でエントリー' }).click();
  await expect(guest.page.locator('.vp')).toHaveCount(0);
  const seatPaint = (page: Page, slot: number) => lineup(page).then((l) => l?.find((e) => e.slot === slot && !e.pending && !e.browsing)?.livery ?? null);
  for (const p of both) await expect.poll(() => seatPaint(p.page, 2), { timeout: 240_000 }).toBe('#b3121c');
  for (const p of both) expect(await seatPaint(p.page, 1)).toBeNull();
  await expect(guest.page.locator('.ol-vehicle-paint')).toHaveCount(1);
  await expect(row.locator('em.ready')).toHaveCount(1);
  await expect(guest.page.locator('.ol-ready')).toHaveText('準備完了を取り消す');
  await expect(start).toHaveText('レース開始');

  // confirmed in the select: the model is swapped for good, and another vehicle takes the ready back
  await guest.page.locator('.ol-vehicle').click();
  await guest.page.locator('.vp-tile[data-id="roach"]').click();
  await guest.page.locator('.vp .cta', { hasText: 'この車でエントリー' }).click();
  await expect(guest.page.locator('.vp')).toHaveCount(0);
  for (const p of both) await seat(p.page, 2, 'roach');
  await expect(row.locator('span')).toHaveText('ゴキブリ');
  await expect(start).toHaveText('準備完了待ち… あと1人', { timeout: 60_000 });
  await expect(host.page.locator('.ol-slots em.choosing')).toHaveCount(0);

  // the guest leaves: their seat is cleared on the host's screen, nothing of the room is left in their own scene
  await guest.page.locator('.ol-leave').click();
  await host.page.waitForFunction(() => (window as any).__game.lobbyState?.length === 2, null, { timeout: 120_000 });
  expect((await lineup(host.page))!.map((e) => e.slot)).toEqual([0, 1]);
  await guest.page.waitForFunction(() => (window as any).__game.lobbyState === null, null, { timeout: 120_000 });
  expect(await lineupsInScene(guest.page)).toBe(0);
  // back in (the same seat), ready, and the host starts: the line-up makes way for the race
  await guest.page.locator('.ol-code').fill(code);
  await guest.page.locator('button', { hasText: '参加' }).click();
  await expect(guest.page.locator('.ol-code-big b')).toHaveText(code, { timeout: 420_000 });
  for (const p of both) await seat(p.page, 2, 'roach');
  await guest.page.locator('.ol-ready').click();
  await expect(start).toHaveText('レース開始', { timeout: 120_000 });
  await host.page.keyboard.press('Enter');
  for (const p of both) {
    await p.page.waitForFunction(() => ['countdown', 'racing'].includes((window as any).__game.phase), null, { timeout: 240_000 });
    expect(await lineup(p.page)).toBeNull();
    expect(await lineupsInScene(p.page)).toBe(0);
    expect((await game(p.page)).remotes).toHaveLength(2);
  }
  // in the race each car wears its member's paint (the guest's: the cockroach's first colouring, as it stood in the
  // select; the member without one: the seat's colour), the guest's own car too
  const roachPaint = await guest.page.evaluate(() => (window as any).__game.player.visual.color);
  expect(roachPaint).toMatch(/^#[0-9a-f]{6}$/);
  const paints = (await game(host.page)).remotes.map((r: any) => [r.slot, r.paint]).sort();
  expect(paints).toEqual([[1, '#d6283c'], [2, roachPaint]]);
  for (const p of both) expect(p.errors).toEqual([]);
  for (const p of both) await p.ctx.close();
});

test('online room: the host changes the conditions and the course, every game follows and the room says who is loading; the next race on another course', async ({ browser, request }) => {
  test.setTimeout(2_400_000);
  const tag = String(Date.now() % 10000);
  const host = await openPlayer(browser, `HOST${tag}`);
  await host.page.locator('button', { hasText: 'ルームを作成' }).click();
  const code = (await host.page.locator('.ol-code-big b').textContent({ timeout: 420_000 }))!.trim();
  await expect(host.page.locator('.rt-badge')).toHaveText('LIVE', { timeout: 120_000 });
  const guest = await openPlayer(browser, `G${tag}`);
  await guest.page.locator('.ol-code').fill(code);
  await guest.page.locator('button', { hasText: '参加' }).click();
  await expect(guest.page.locator('.ol-code-big b')).toHaveText(code, { timeout: 420_000 });
  await expect(guest.page.locator('.rt-badge')).toHaveText('LIVE', { timeout: 120_000 });
  const silent = await apiPlayer(request, `T${tag}`);
  expect((await silent.join(code)).status()).toBe(200);
  expect((await silent.loaded(code)).status()).toBe(200);
  expect((await silent.ready(code)).status()).toBe(200);
  const both = [host, guest];
  const start = host.page.locator('.ol-start');
  const ready = guest.page.locator('.ol-ready');
  const world = (page: Page) => page.evaluate(() => {
    const g = (window as any).__game;
    return { course: g.course.id as string, tod: g.timeOfDay as string, phase: g.phase as string, seats: (g.lobbyState?.length ?? null) as number | null };
  });
  await expect(ready).toBeEnabled({ timeout: 240_000 });
  await ready.click();
  await expect(start).toHaveText('レース開始', { timeout: 120_000 });

  // the room's course and conditions are on both screens; only the host has the way to change them
  await expect(host.page.locator('button.ol-set')).toHaveCount(2);
  await expect(guest.page.locator('button.ol-set')).toHaveCount(0);
  await expect(guest.page.locator('.ol-set.fixed')).toHaveText(['コース朧峠', '時間帯・天候深夜・晴れ']);
  await guest.page.keyboard.press('x');
  await guest.page.keyboard.press('c');
  await expect(guest.page.locator('.cond-list')).toHaveCount(0);
  expect((await silent.change(code, { track_id: 'autobahn' })).status()).toBe(403);

  // the host looks through the conditions: its own scene follows, nothing is sent; Esc leaves the room as it was
  await host.page.locator('.ol-set-color').click();
  await expect(host.page.locator('.cond-row')).toHaveCount(3);
  await expect(host.page.locator('.cond-row .row-now')).toHaveCount(1);
  await expect(host.page.locator('.touch-back')).toContainText('戻る');
  await host.page.keyboard.press('ArrowDown');
  await host.page.waitForFunction(() => (window as any).__game.timeOfDay === 'rain', null, { timeout: 120_000 });
  expect((await world(guest.page)).tod).toBe('night');
  await host.page.keyboard.press('Escape');
  await expect(host.page.locator('.ol-panel')).toBeVisible();
  await host.page.waitForFunction(() => (window as any).__game.timeOfDay === 'night', null, { timeout: 120_000 });
  await expect(start).toHaveText('レース開始');
  await expect(ready).toHaveText('準備完了を取り消す');

  // chosen: everyone's scene changes at once (no load), the readies go back, and the guest is told why
  await host.page.keyboard.press('c');
  await host.page.locator('.cond-row', { hasText: '深夜・雨' }).click();
  // (the notice first: it goes by itself after a few seconds)
  await expect(guest.page.locator('.room-notice')).toContainText('ホストが時間帯・天候を「深夜・雨」に変更しました準備完了は取り消されました', { timeout: 60_000 });
  await expect(host.page.locator('.room-notice')).toHaveCount(0);
  await expect(host.page.locator('.ol-panel')).toBeVisible();
  for (const p of both) {
    await p.page.waitForFunction(() => (window as any).__game.timeOfDay === 'rain', null, { timeout: 120_000 });
    await expect(p.page.locator('.ol-set').nth(1)).toContainText('深夜・雨');
    expect((await world(p.page)).course).toBe('oboro-downhill');
    await expect(p.page.locator('.ol-slots em.loading')).toHaveCount(0);
  }
  await expect(ready).toHaveText('準備完了', { timeout: 60_000 });
  await expect(start).toHaveText('準備完了待ち… あと2人', { timeout: 60_000 });
  // (the member without a game is on no channel: the host sees that, and whom the start waits for)
  await expect(host.page.locator('.ol-slots li.gone')).toHaveCount(1, { timeout: 60_000 });
  await expect(host.page.locator('.ol-hold')).toHaveText(`T${tag} は接続が切れています。ルームから外せます。`);
  await expect(host.page.locator('.ol-kick')).toHaveCount(1);
  await expect(guest.page.locator('.ol-kick')).toHaveCount(0);

  // another course: both games build it behind the loading screen and come back to the room on it
  await host.page.keyboard.press('x');
  await expect(host.page.locator('.crs-row')).toHaveCount(4);
  await host.page.locator('.crs-row', { hasText: '霧降湖' }).click();
  await expect(guest.page.locator('.room-notice')).toContainText('ホストがコースを「霧降湖」に変更しました', { timeout: 120_000 });
  for (const p of both) {
    await p.page.waitForFunction(() => (window as any).__game.course.id === 'kirifuri-lakeside' && (window as any).__game.lobbyState?.length === 3, null, { timeout: 600_000 });
    await expect(p.page.locator('.ol-code-big b')).toHaveText(code, { timeout: 120_000 });
    await expect(p.page.locator('.ol-set').first()).toContainText('霧降湖');
    expect(await world(p.page)).toMatchObject({ tod: 'rain', phase: 'garage', seats: 3 });
  }
  // the member whose game has not loaded it yet holds the start up, by name, on both screens
  await expect(host.page.locator('.ol-slots li.loading')).toHaveCount(1, { timeout: 120_000 });
  await expect(start).toHaveText('読み込み待ち… あと1人');
  await expect(start).toBeDisabled();
  await expect(guest.page.locator('.ol-hold')).toHaveText(`T${tag} がコースを読み込んでいます`, { timeout: 60_000 });
  // (the host is also told when it has been going on for long, and offered to take the member out)
  await expect(host.page.locator('.ol-hold')).toHaveText(new RegExp(`^T${tag} (がコースを読み込んでいます|の読み込みに時間がかかっています。待つか、ルームから外せます。)$`), { timeout: 60_000 });
  // (a report for the course the room has left is not taken)
  expect((await (await silent.loadedOn(code, 'oboro-downhill')).json()).players[2].loaded).toBe(false);
  expect((await (await silent.loadedOn(code, 'kirifuri-lakeside')).json()).players[2].loaded).toBe(true);
  await expect(host.page.locator('.ol-slots li.loading')).toHaveCount(0, { timeout: 60_000 });
  await expect(start).toHaveText('準備完了待ち… あと2人');
  expect((await silent.ready(code)).status()).toBe(200);
  await expect(ready).toHaveText('準備完了');
  await ready.click();
  await expect(start).toHaveText('レース開始', { timeout: 120_000 });

  // the race runs on the new course, in the rain
  await host.page.keyboard.press('Enter');
  for (const p of both) {
    await p.page.waitForFunction(() => (window as any).__game.phase === 'racing', null, { timeout: 420_000 });
    expect(await world(p.page)).toMatchObject({ course: 'kirifuri-lakeside', tod: 'rain' });
  }
  // (to the finish once the race clock has passed the course's minimum, which the server holds a finish to)
  for (const p of both) {
    await p.page.waitForFunction(() => (window as any).__game.hud.raceTime > 30, null, { timeout: 480_000, polling: 500 });
    await nearFinish(p.page);
  }
  expect((await silent.finish(code, 95_000)).status()).toBe(200);
  for (const p of both) await expect(p.page.locator('.online-results')).toBeVisible({ timeout: 600_000 });
  await expect(host.page.locator('.ol-standings .time').filter({ hasText: TIME })).toHaveCount(3, { timeout: 420_000 });

  // from the results the host picks the next course (one both games have kept): everyone is back in the room on it
  await expect(guest.page.locator('.ol-next')).toHaveCount(0);
  await host.page.locator('.ol-next').click();
  await expect(host.page.locator('.crs-row .row-now')).toHaveCount(1);
  await host.page.locator('.crs-row', { hasText: '朧峠' }).click();
  await expect(guest.page.locator('.room-notice')).toContainText('ホストがコースを「朧峠」に変更しました', { timeout: 120_000 });
  for (const p of both) {
    await p.page.waitForFunction(() => (window as any).__game.course.id === 'oboro-downhill' && (window as any).__game.lobbyState?.length === 3, null, { timeout: 600_000 });
    await expect(p.page.locator('.ol-code-big b')).toHaveText(code, { timeout: 120_000 });
    await expect(p.page.locator('.ol-set').first()).toContainText('朧峠');
  }
  expect((await silent.loadedOn(code, 'oboro-downhill')).status()).toBe(200);
  expect((await silent.ready(code)).status()).toBe(200);
  await expect(ready).toBeEnabled({ timeout: 120_000 });
  await ready.click();
  await expect(start).toHaveText('レース開始', { timeout: 120_000 });
  await host.page.keyboard.press('Enter');
  for (const p of both) {
    await p.page.waitForFunction(() => ['countdown', 'racing'].includes((window as any).__game.phase), null, { timeout: 420_000 });
    expect((await world(p.page)).course).toBe('oboro-downhill');
  }
  for (const p of both) expect(p.errors).toEqual([]);
  for (const p of both) await p.ctx.close();
});

test('online battle on a phone: five seats, the live order and five results fit the screen', async ({ browser, request }, testInfo) => {
  test.setTimeout(1_500_000);
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
  const code = (await page.locator('.ol-code-big b').textContent({ timeout: 420_000 }))!.trim();
  const others = [];
  for (const name of ['B', 'C', 'D', 'E']) {
    // (a long name: sixteen characters, the limit)
    const p = await apiPlayer(request, `${name}${tag}-長い名前の走り屋さん`.slice(0, 16));
    expect((await p.join(code)).status()).toBe(200);
    expect((await p.loaded(code)).status()).toBe(200);
    others.push(p);
  }
  // the room: all five seats and the start button in view at once, nothing cut off to the side
  await expect(page.locator('.ol-slots li:not(.empty)')).toHaveCount(5, { timeout: 60_000 });
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
  await expect(page.locator('.ol-slots em.ready')).toHaveCount(4, { timeout: 60_000 });
  await expect(page.locator('.ol-start')).toHaveText('レース開始');
  await page.screenshot({ path: testInfo.outputPath('phone-room-ready.png') });
  // the back button leaves the room (Esc on a keyboard) … not pressed here; the start button by a tap
  await expect(page.locator('.touch-back')).toBeVisible();
  await tap('.ol-start');
  await page.waitForFunction(() => (window as any).__game.phase === 'racing', null, { timeout: 420_000 });

  // the race: the live order of five under the clock, clear of the steering pad, the buttons and the bend warning
  await expect(page.locator('.online-standings li')).toHaveCount(5, { timeout: 120_000 });
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
  await page.waitForFunction(() => (window as any).__game.hud.raceTime > 26, null, { timeout: 480_000, polling: 500 });
  await nearFinish(page);
  for (const [k, p] of others.entries()) expect((await p.finish(code, 58_000 + k * 1_300)).status()).toBe(200);
  await expect(page.locator('.online-results')).toBeVisible({ timeout: 480_000 });
  await expect(page.locator('.ol-standings li .time')).toHaveText([TIME, TIME, TIME, TIME, TIME], { timeout: 240_000 });
  await page.locator('.ol-panel').evaluate((el) => el.scrollTo(0, 0));
  for (let k = 0; k < 5; k++) await expect(page.locator('.ol-standings li').nth(k)).toBeInViewport({ ratio: 1 });
  await expect(page.locator('button', { hasText: 'もう一度走る' })).toBeInViewport({ ratio: 1 });
  expect(await bottom('.ol-standings')).toBeLessThanOrEqual((await box('.ol-actions')).y);
  expect(await noSideScroll()).toBe(true);
  await page.screenshot({ path: testInfo.outputPath('phone-results.png') });
  expect(host.errors).toEqual([]);
  await host.ctx.close();
});
