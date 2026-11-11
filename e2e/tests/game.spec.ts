import { expect, test } from '@playwright/test';
import { prepare, waitForTitle } from './helpers';

test('boots to the title screen and renders the 3D world without errors', async ({ page }) => {
  const errors = await prepare(page);
  await page.goto('/');
  await expect(page.locator('.boot')).toBeVisible();
  await waitForTitle(page);
  const stats = await page.evaluate(() => {
    const g = (window as any).__game;
    return { lamps: g.scenery.lamps.length, trackLength: g.track.length };
  });
  expect(stats.lamps).toBeGreaterThan(30);
  expect(stats.trackLength).toBeGreaterThan(3000);
  // the canvas actually draws something (not a blank frame)
  const shot = await page.locator('canvas').screenshot();
  expect(shot.byteLength).toBeGreaterThan(20_000);
  expect(errors).toEqual([]);
});

test('menu navigation, settings persistence and controls screen', async ({ page }) => {
  await prepare(page);
  await page.goto('/');
  await waitForTitle(page);
  // fullscreen on and off: the button, then the F key
  await page.locator('.fs-toggle').click();
  await page.waitForFunction(() => !!document.fullscreenElement);
  await expect(page.locator('.fs-toggle')).toHaveText('全画面終了');
  await page.keyboard.press('KeyF');
  await page.waitForFunction(() => !document.fullscreenElement);
  await page.keyboard.press('Enter');
  await expect(page.locator('.menu-list li.active')).toContainText('TIME ATTACK');
  await page.keyboard.press('ArrowDown');
  await expect(page.locator('.menu-list li.active')).toContainText('RIVAL BATTLE');

  await page.locator('.menu-list li', { hasText: 'SETTINGS' }).click();
  // conditions and gearbox are chosen before each race now, not here
  await expect(page.locator('.settings-list')).not.toContainText('時間帯');
  await expect(page.locator('.settings-list')).not.toContainText('トランスミッション');
  const corner = page.locator('.settings-list li', { hasText: 'コーナー予告' });
  await expect(corner).toContainText('オン');
  await corner.locator('button[aria-label="increase"]').click();
  await expect(corner).toContainText('オフ');
  const stored = await page.evaluate(() => JSON.parse(localStorage.getItem('touge-settings')!).state.cornerGuide);
  expect(stored).toBe(false);
  // the interface's motion can be switched off: the app then only fades (and takes it back on again)
  const motion = page.locator('.settings-list li', { hasText: 'UI アニメーション' });
  await expect(motion).toContainText('オン');
  await expect(page.locator('.app')).not.toHaveClass(/motion-off/);
  await motion.locator('button[aria-label="increase"]').click();
  await expect(motion).toContainText('オフ');
  await expect(page.locator('.app')).toHaveClass(/motion-off/);
  await motion.locator('button[aria-label="increase"]').click();
  await expect(page.locator('.app')).not.toHaveClass(/motion-off/);
  // the shell: the trail says where this is, its back button is the Esc key
  await expect(page.locator('.shell-top .trail li.now')).toContainText('設定');
  await page.locator('.shell-nav .touch-back').click();
  await expect(page.locator('.menu-list')).toBeVisible();
  await expect(page.locator('.shell-top .trail li.now')).toContainText('メインメニュー');
  await page.locator('.menu-list li', { hasText: 'CONTROLS' }).click();
  await expect(page.locator('.controls-table')).toContainText('サイドブレーキ');
  // (a screen on its way out is not in the document any more: one screen at a time for every selector)
  await page.keyboard.press('Escape');
  await expect(page.locator('.overlay > .screen')).toHaveCount(1);

  // car list: figures of every car, dragging turns the camera around it
  await page.locator('.menu-list li', { hasText: 'CAR LIST' }).click();
  await expect(page.locator('.cars .car-name')).toHaveText('SPRINTER TRUENO AE86');
  await expect(page.locator('.spec-table')).toContainText('最高出力');
  await page.keyboard.press('ArrowRight');
  await expect(page.locator('.cars .car-name')).toHaveText('SILVIA spec-R (S15)');
  await page.mouse.move(300, 300);
  await page.mouse.down();
  await page.mouse.move(380, 320, { steps: 5 });
  await page.mouse.up();
  expect(await page.evaluate(() => (window as any).__game.garageOrbit !== null)).toBe(true);
  // the joke entries follow the cars and bikes: two to the left of the S15 is the last one, the cockroach, then the L0
  await page.keyboard.press('ArrowLeft');
  await page.keyboard.press('ArrowLeft');
  await expect(page.locator('.cars .car-name')).toHaveText('ゴキブリ');
  await expect(page.locator('.spec-table')).toContainText('6本脚');
  expect(await page.evaluate(() => !!(window as any).__game.garageCar.rig.creature)).toBe(true);
  await page.keyboard.press('ArrowLeft');
  await expect(page.locator('.cars .car-name')).toHaveText('L0系');
  await expect(page.locator('.train-badge')).toBeVisible();
  await expect(page.locator('.spec-table')).toContainText('起動加速度');
  expect(await page.evaluate(() => !!(window as any).__game.garageCar.rig.train)).toBe(true);
  await page.keyboard.press('Escape');
  await expect(page.locator('.menu-list')).toBeVisible();
});

test('ranking shows the seeded CPU drivers from the Laravel API', async ({ page }) => {
  await prepare(page);
  await page.goto('/');
  await waitForTitle(page);
  await page.keyboard.press('Enter');
  await page.locator('.menu-list li', { hasText: 'RANKING' }).click();
  await expect(page.locator('.lb-table tbody tr').first()).toBeVisible();
  await expect(page.locator('.lb-table')).toContainText('朧');
  await page.locator('.tabs button', { hasText: 'IMPREZA WRX STI' }).click();
  await expect(page.locator('.lb-table tbody tr td:nth-child(3)').first()).toHaveText('IMPREZA WRX STI');
});

test('ranking without the server: says what happened, and a retry brings the list back', async ({ page }) => {
  await prepare(page);
  await page.route('**/leaderboard**', (route) => route.abort());
  await page.goto('/');
  await waitForTitle(page);
  await page.keyboard.press('Enter');
  await page.locator('.menu-list li', { hasText: 'RANKING' }).click();
  await expect(page.locator('.lb-msg.error')).toContainText('ランキングを取得できませんでした');
  await expect(page.locator('.lb-table')).toHaveCount(0);
  await page.unroute('**/leaderboard**');
  await page.locator('.lb-msg.error button', { hasText: '再試行' }).click();
  await expect(page.locator('.lb-table tbody tr').first()).toBeVisible();
  await expect(page.locator('.lb-msg.error')).toHaveCount(0);
});

test('time attack: full autodriven run, results and online submission', async ({ page }) => {
  // (a frame takes over a second on the software renderer, and a frame carries at most 0.67 s of the race at this
  // timescale: the lap of 1:54 then takes three to four minutes. The same build took 3 minutes on 11-10 and over 4
  // on 11-11 on the same machine)
  test.setTimeout(600_000);
  await prepare(page);
  await page.goto('/?autodrive=1&timescale=10');
  await waitForTitle(page);
  await page.keyboard.press('Enter');
  await page.keyboard.press('Enter'); // TIME ATTACK
  await expect(page.locator('.course-card.active')).toContainText('OBORO PASS');
  await page.keyboard.press('Enter'); // default course
  await expect(page.locator('.choice-card.active')).toContainText('深夜・晴れ');
  await page.keyboard.press('Enter'); // conditions as last time
  await expect(page.locator('.car-name')).toHaveText('SPRINTER TRUENO AE86');
  await page.locator('.cta', { hasText: 'この車に決定' }).click();
  await expect(page.locator('.choice-card.active')).toContainText('AT');
  await page.keyboard.press('Enter'); // gearbox as last time
  await expect(page.locator('.hud')).toBeVisible();
  await page.waitForFunction(() => (window as any).__game.phase === 'racing', null, { timeout: 120_000 });
  // the camera goes with the car (it once stayed where the garage had it, and every other check still passed)
  await page.waitForFunction(() => (window as any).__game.hud.progress > 0.04, null, { timeout: 240_000 });
  expect(await page.evaluate(() => { const g = (window as any).__game; return g.camera.position.distanceTo(g.player.sim.position); })).toBeLessThan(60);
  await expect(page.locator('.results-time')).toBeVisible({ timeout: 480_000 });
  const time = await page.locator('.results-time').textContent();
  expect(time).toMatch(/^[1-3]:\d\d\.\d{3}$/);
  // first submission asks for a name
  const name = `E2E-${Date.now() % 100000}`;
  await page.locator('.name-form input').fill(name);
  await page.locator('.name-form button[type="submit"]').click();
  await expect(page.locator('.online-msg.ok')).toContainText('ONLINE RANK');
  // and the run appears in the ranking
  await page.locator('.results-actions button', { hasText: 'ランキング' }).click();
  await expect(page.locator('.lb-table')).toContainText(name);
});

test('ghost battle against a CPU ghost', async ({ page }) => {
  await prepare(page);
  await page.goto('/?autodrive=1&timescale=4');
  await waitForTitle(page);
  await page.keyboard.press('Enter');
  await page.locator('.menu-list li', { hasText: 'GHOST BATTLE' }).click();
  await page.locator('.course-card', { hasText: 'OBORO PASS' }).click();
  await page.locator('.choice-card', { hasText: '深夜・晴れ' }).click();
  const row = page.locator('.lb-table tbody tr', { hasText: '朧' });
  await row.locator('button', { hasText: '挑戦' }).click();
  await page.locator('.cta', { hasText: 'この車に決定' }).click();
  await page.locator('.choice-card', { hasText: 'オートマチック' }).click();
  // (the race starts once the ghost is fetched and its car built: over 30 s on the software renderer at times)
  await expect(page.locator('.ghost-tag')).toContainText('朧', { timeout: 90_000 });
  await page.waitForFunction(() => (window as any).__game.phase === 'racing', null, { timeout: 120_000 });
  await page.waitForFunction(() => (window as any).__game.hud.ghostProgress > 0.05, null, { timeout: 120_000 });
});

test('rival battle starts with an AI opponent and can be paused', async ({ page }) => {
  await prepare(page);
  await page.goto('/?autodrive=1&timescale=4');
  await waitForTitle(page);
  await page.keyboard.press('Enter');
  await page.locator('.menu-list li', { hasText: 'RIVAL BATTLE' }).click();
  await page.locator('.course-card', { hasText: 'OBORO PASS' }).click();
  // rain, manual gearbox: both reach the race
  await page.locator('.choice-card', { hasText: '深夜・雨' }).click();
  await page.locator('.cta', { hasText: 'この車に決定' }).click();
  await page.locator('.choice-card', { hasText: 'マニュアル' }).click();
  await page.locator('.rival-card.ace').click();
  await expect(page.locator('.versus')).toContainText('高嶺 遼');
  // the rival says something before the start (no model on the test stack: one of the game's own lines)
  await expect(page.locator('.vs-line')).toHaveText(/^「.+」$/, { timeout: 120_000 });
  const setup = await page.evaluate(() => {
    const g = (window as any).__game;
    return { tod: g.timeOfDay, auto: g.player.sim.autoShift, wet: g.weatherGrip < 1 };
  });
  expect(setup).toEqual({ tod: 'rain', auto: false, wet: true });
  await page.waitForFunction(() => (window as any).__game.phase === 'racing', null, { timeout: 120_000 });
  await page.waitForFunction(() => (window as any).__game.hud.rivalProgress > 0.02, null, { timeout: 120_000 });
  expect(await page.evaluate(() => { const g = (window as any).__game; return g.camera.position.distanceTo(g.player.sim.position); })).toBeLessThan(60);
  await page.keyboard.press('Escape');
  await expect(page.locator('.pause-title')).toBeVisible();
  const t1 = await page.evaluate(() => (window as any).__game.hud.raceTime);
  await page.waitForTimeout(1500);
  const t2 = await page.evaluate(() => (window as any).__game.hud.raceTime);
  expect(t2).toBeCloseTo(t1, 2);
  await page.keyboard.press('Escape');
  await expect(page.locator('.pause-title')).toBeHidden();
});

test('course select switches to another mountain and its own rivals', async ({ page }) => {
  const errors = await prepare(page);
  await page.goto('/');
  await waitForTitle(page);
  await page.keyboard.press('Enter');
  await page.locator('.menu-list li', { hasText: 'RIVAL BATTLE' }).click();
  await expect(page.locator('.course-card')).toHaveCount(4);
  await page.keyboard.press('ArrowRight');
  await expect(page.locator('.course-card.active')).toContainText('KIRIFURI LAKESIDE');
  await page.keyboard.press('Enter');
  // the world is rebuilt behind the course loading screen, then the conditions open
  await expect(page.locator('.choice-card.active')).toBeVisible({ timeout: 180_000 });
  const world = await page.evaluate(() => {
    const g = (window as any).__game;
    return { id: g.course.id, length: g.track.length, lamps: g.scenery.lamps.length };
  });
  expect(world.id).toBe('kirifuri-lakeside');
  expect(world.length).toBeGreaterThan(2500);
  expect(world.lamps).toBeGreaterThan(20);
  await page.keyboard.press('Enter');
  await page.locator('.cta', { hasText: 'この車に決定' }).click();
  await page.keyboard.press('Enter');
  await expect(page.locator('.rival-card.rookie')).toContainText('椎名 ほのか');
  // the choice is remembered for the next session
  const stored = await page.evaluate(() => JSON.parse(localStorage.getItem('touge-settings')!).state.courseId);
  expect(stored).toBe('kirifuri-lakeside');
  expect(errors).toEqual([]);
});

test('car select: tabs by kind, pictures, sorting, favourites, grid keys', async ({ page }) => {
  const errors = await prepare(page);
  await page.goto('/');
  await waitForTitle(page);
  await page.keyboard.press('Enter');
  await page.keyboard.press('Enter'); // TIME ATTACK
  await expect(page.locator('.course-card.active')).toContainText('OBORO PASS');
  await page.keyboard.press('Enter');
  await expect(page.locator('.choice-card.active')).toContainText('深夜・晴れ');
  await page.keyboard.press('Enter');
  // every vehicle on the first tab, each with its picture (no fallback tile)
  await expect(page.locator('.vp-tab.on')).toHaveAttribute('data-tab', 'all');
  const all = await page.locator('.vp-tile').count();
  expect(all).toBeGreaterThanOrEqual(18);
  await expect(page.locator('.vp-tab.on i')).toHaveText(String(all));
  await page.waitForFunction(() => [...document.querySelectorAll<HTMLImageElement>('.vp-thumb img')].every((i) => i.complete && i.naturalWidth > 0));
  await expect(page.locator('.vp-thumb img')).toHaveCount(all);
  await expect(page.locator('.vp-thumb-none')).toHaveCount(0);
  // measured figures of the highlighted car
  await expect(page.locator('.vp-tile.on')).toHaveAttribute('data-id', 'hayate');
  await expect(page.locator('.vp-bar')).toHaveCount(5);
  await expect(page.locator('.vp-bar').first()).toContainText('秒');
  // ← → step through the list as the old car select did, ↓ ↑ by a row; the garage shows the highlighted one
  await page.keyboard.press('ArrowRight');
  await expect(page.locator('.car-name')).toHaveText('SILVIA spec-R (S15)');
  expect(await page.evaluate(() => (window as any).__game.garageCar.spec.id)).toBe('s15');
  await page.keyboard.press('ArrowDown');
  await page.keyboard.press('ArrowUp');
  await expect(page.locator('.vp-tile.on')).toHaveAttribute('data-id', 's15');
  await page.keyboard.press('ArrowLeft');
  await page.keyboard.press('ArrowLeft');
  await expect(page.locator('.car-name')).toHaveText('ゴキブリ');
  // E / Q change the tab: the next one holds the cars only, and the cursor goes to its first
  await page.keyboard.press('KeyE');
  await expect(page.locator('.vp-tab.on')).toHaveAttribute('data-tab', 'car');
  await expect(page.locator('.car-name')).toHaveText('SPRINTER TRUENO AE86');
  await expect(page.locator('.vp-tile[data-id="e5"]')).toHaveCount(0);
  await page.locator('.vp-tab[data-tab="train"]').click();
  await expect(page.locator('.vp-tile').first()).toHaveAttribute('data-id', 'e231');
  await expect(page.locator('.vp-badge')).toBeVisible();
  // sorted by top speed: the maglev first, its figure on the tile
  await page.locator('.vp-sort[data-sort="speed"]').click();
  await expect(page.locator('.vp-tile').first()).toHaveAttribute('data-id', 'l0');
  await expect(page.locator('.vp-tile[data-id="l0"] .vp-tile-fig')).toHaveText('500 km/h');
  await page.keyboard.press('KeyR'); // the next order
  await expect(page.locator('.vp-sort.on')).toHaveAttribute('data-sort', 'corner');
  await page.locator('.vp-sort[data-sort="default"]').click();
  // favourites: X stars the highlighted vehicle, a tile's star another; they are kept and have their own tab
  await page.keyboard.press('KeyX');
  await page.locator('.vp-tile[data-id="e5"] .vp-star').click();
  await expect(page.locator('.vp-star.on')).toHaveCount(2);
  expect(await page.evaluate(() => JSON.parse(localStorage.getItem('touge-garage')!).state.favourites)).toEqual(['e231', 'e5']);
  await page.keyboard.press('KeyE');
  await page.keyboard.press('KeyE'); // その他 → ★
  await expect(page.locator('.vp-tab.on')).toHaveAttribute('data-tab', 'fav');
  await expect(page.locator('.vp-tile')).toHaveCount(2);
  await page.locator('.vp-tile[data-id="e5"] .vp-star').click();
  await expect(page.locator('.vp-tile')).toHaveCount(1);
  // a click highlights, a second one on the same tile confirms
  await page.locator('.vp-tab[data-tab="car"]').click();
  await page.locator('.vp-tile[data-id="shiden"]').click();
  await expect(page.locator('.car-name')).toHaveText('RX-7 (FD3S)');
  await page.locator('.vp-tile[data-id="shiden"]').click();
  await expect(page.locator('.choice-card.active')).toContainText('AT');
  expect(await page.evaluate(() => (window as any).__game.garageCar.spec.id)).toBe('shiden');
  // Esc from the gearbox: back in the car select, on the tab and the car left
  await page.keyboard.press('Escape');
  await expect(page.locator('.vp-tab.on')).toHaveAttribute('data-tab', 'car');
  await expect(page.locator('.vp-tile.on')).toHaveAttribute('data-id', 'shiden');
  await page.keyboard.press('Escape');
  await expect(page.locator('.choice-card.active')).toContainText('深夜・晴れ');
  expect(errors).toEqual([]);
});
