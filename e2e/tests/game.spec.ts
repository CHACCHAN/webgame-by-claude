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
  await page.keyboard.press('Escape');
  await page.locator('.menu-list li', { hasText: 'CONTROLS' }).click();
  await expect(page.locator('.controls-table')).toContainText('サイドブレーキ');
  await page.keyboard.press('Escape');

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

test('time attack: full autodriven run, results and online submission', async ({ page }) => {
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
  await expect(page.locator('.results-time')).toBeVisible({ timeout: 200_000 });
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
  await expect(page.locator('.ghost-tag')).toContainText('朧');
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
  const setup = await page.evaluate(() => {
    const g = (window as any).__game;
    return { tod: g.timeOfDay, auto: g.player.sim.autoShift, wet: g.weatherGrip < 1 };
  });
  expect(setup).toEqual({ tod: 'rain', auto: false, wet: true });
  await page.waitForFunction(() => (window as any).__game.phase === 'racing', null, { timeout: 120_000 });
  await page.waitForFunction(() => (window as any).__game.hud.rivalProgress > 0.02, null, { timeout: 120_000 });
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
  await expect(page.locator('.course-card')).toHaveCount(3);
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
