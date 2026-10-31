import { expect, test, type APIRequestContext, type Browser, type Page } from '@playwright/test';
import { prepare, waitForTitle } from './helpers';

/** One player = one browser context (own localStorage, own player token). */
async function openPlayer(browser: Browser, name: string) {
  // three WebGL clients share one CPU (SwiftShader): small canvases
  const ctx = await browser.newContext({ viewport: { width: 640, height: 360 } });
  const page = await ctx.newPage();
  await page.addInitScript(() => localStorage.setItem('touge-settings', JSON.stringify({ state: { quality: 'low', resolutionScale: 0.5, timeOfDay: 'night', masterVolume: 0, sfxVolume: 0, musicVolume: 0, assist: 1, autoShift: true, showGhost: false, showFps: false, cornerGuide: true }, version: 1 })));
  const errors = await prepare(page);
  await page.goto('/?autodrive=1&timescale=4');
  await waitForTitle(page);
  await page.keyboard.press('Enter');
  await page.locator('.menu-list li', { hasText: 'ONLINE BATTLE' }).click();
  await page.locator('.ol-name').fill(name);
  await page.keyboard.press('Enter');
  await expect(page.locator('.ol-me')).toContainText(name);
  return { ctx, page, errors };
}

const game = (page: Page) => page.evaluate(() => {
  const g = (window as any).__game;
  return { phase: g.phase, course: g.course.id, remotes: g.remotes.standings(), standings: g.hud.online };
});

/** A fourth player straight through the API: the room must turn them away. */
async function fourthPlayer(request: APIRequestContext, code: string) {
  const reg = await request.post('/api/players', { data: { name: 'FOURTH' } });
  const { token } = await reg.json();
  return request.post(`/api/rooms/${code}/join`, { data: { car_id: 'hayate' }, headers: { Authorization: `Bearer ${token}` } });
}

test('online battle: three players join one room by code and race together', async ({ browser, request }) => {
  test.setTimeout(1_500_000);
  const tag = String(Date.now() % 10000);
  const host = await openPlayer(browser, `HOST${tag}`);
  await host.page.locator('.ol-courses .chip', { hasText: '天狼スカイライン' }).click();
  await host.page.locator('button', { hasText: 'ルームを作成' }).click();
  const code = (await host.page.locator('.ol-code-big b').textContent({ timeout: 180_000 }))!.trim();
  expect(code).toMatch(/^[A-Z2-9]{4}$/);
  await expect(host.page.locator('.rt-badge')).toHaveText('LIVE', { timeout: 60_000 });
  // alone, the host cannot start yet
  await expect(host.page.locator('.ol-actions .cta').first()).toBeDisabled();

  const guests = [];
  for (const name of [`B${tag}`, `C${tag}`]) {
    const g = await openPlayer(browser, name);
    await g.page.locator('.ol-code').fill(code);
    await g.page.locator('button', { hasText: '参加' }).click();
    await expect(g.page.locator('.ol-code-big b')).toHaveText(code, { timeout: 180_000 });
    guests.push(g);
  }
  const all = [host, ...guests];
  // everyone sees the full room (pushed over the socket or picked up by polling)
  for (const p of all) await expect(p.page.locator('.ol-slots li:not(.empty)')).toHaveCount(3, { timeout: 30_000 });
  for (const p of guests) await expect(p.page.locator('.ol-waiting')).toBeVisible();
  // a fourth player is turned away
  const full = await fourthPlayer(request, code);
  expect(full.status()).toBe(409);
  expect((await full.json()).message).toContain('満員');

  await host.page.locator('button', { hasText: 'レース開始' }).click();
  for (const p of all) {
    await p.page.waitForFunction(() => (window as any).__game.phase === 'racing', null, { timeout: 120_000 });
    const st = await game(p.page);
    expect(st.course).toBe('tenrou-skyline');
    expect(st.remotes).toHaveLength(2);
  }
  // car states flow between all three clients and the live order lists everybody
  for (const p of all) {
    await p.page.waitForFunction(() => (window as any).__game.remotes.standings().every((r: any) => r.lastHeard > 0 && r.s > 0), null, { timeout: 120_000 });
    await expect(p.page.locator('.online-standings li')).toHaveCount(3);
  }
  // shortcut to the finish once the race clock passes the course minimum (45 s), so the results
  // flow is covered without driving 2.4 km at ~1 fps
  for (const p of all) {
    await p.page.waitForFunction(() => (window as any).__game.hud.raceTime > 47, null, { timeout: 300_000, polling: 500 });
    await p.page.evaluate(() => {
      const g = (window as any).__game, t = g.track, s = t.finishS - 45;
      g.player.sim.reset(t.pointAt(s, 0), t.headingAt(s), 20);
      g.player.proj.index = -1;
      g.player.lastSafe = { s, t: g.time };
    });
  }
  for (const p of all) await expect(p.page.locator('.online-results')).toBeVisible({ timeout: 300_000 });
  for (const p of all) {
    await expect(p.page.locator('.ol-standings li .time')).toHaveText([/^\d:\d\d\.\d{3}$/, /^\d:\d\d\.\d{3}$/, /^\d:\d\d\.\d{3}$/], { timeout: 120_000 });
  }
  await expect(host.page.locator('button', { hasText: 'もう一度走る' })).toBeVisible();
  // rematch takes everyone back to the room
  await host.page.locator('button', { hasText: 'もう一度走る' }).click();
  for (const p of all) await expect(p.page.locator('.ol-code-big b')).toHaveText(code, { timeout: 30_000 });
  for (const p of all) expect(p.errors).toEqual([]);
  for (const p of all) await p.ctx.close();
});
