import { expect, test } from '@playwright/test';
import { prepare, waitForTitle } from './helpers';

// a phone held sideways
test.use({ viewport: { width: 844, height: 390 }, hasTouch: true, isMobile: true });

test('phone: menus by taps, back button, a race driven with the touch controls', async ({ page }) => {
  const errors = await prepare(page);
  const tap = async (sel: string, text?: string) => {
    const box = (await page.locator(sel, text ? { hasText: text } : {}).first().boundingBox())!;
    await page.touchscreen.tap(box.x + box.width / 2, box.y + box.height / 2);
  };
  await page.goto('/');
  await waitForTitle(page);
  await expect(page.locator('.app')).toHaveClass(/touch/);
  await expect(page.locator('.press-start')).toHaveText('TAP TO START');
  await page.touchscreen.tap(422, 195);
  await expect(page.locator('.menu-list li', { hasText: 'CONTROLS' })).toBeVisible();
  // no Esc key on a phone: the on-screen back button
  await tap('.menu-list li', 'SETTINGS');
  await expect(page.locator('.settings-list')).toBeVisible();
  await tap('.touch-back');
  await expect(page.locator('.menu-list li', { hasText: 'TIME ATTACK' })).toBeVisible();

  await tap('.menu-list li', 'TIME ATTACK');
  await tap('.course-card');
  await expect(page.locator('.choice-card').first()).toBeVisible({ timeout: 120_000 });
  await tap('.choice-card');
  // the car select's button is in view without scrolling
  await expect(page.locator('.cta', { hasText: 'この車に決定' })).toBeInViewport({ timeout: 60_000 });
  await tap('.cta', 'この車に決定');
  await tap('.choice-card');
  await page.waitForFunction(() => (window as any).__game.phase === 'racing', null, { timeout: 120_000 });
  await expect(page.locator('.tc-pedal.gas')).toBeVisible();

  // hold the accelerator (touch events reach the buttons as pointer events), then steer with a second finger
  const cdp = await page.context().newCDPSession(page);
  const centre = async (sel: string, fx = 0.5) => {
    const b = (await page.locator(sel).first().boundingBox())!;
    return { x: b.x + b.width * fx, y: b.y + b.height / 2 };
  };
  const gas = await centre('.tc-pedal.gas');
  const right = await centre('.tc-steer', 0.8);
  await cdp.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x: gas.x, y: gas.y, id: 1 }] });
  await page.waitForFunction(() => (window as any).__game.player.input.throttle > 0.9, null, { timeout: 10_000 });
  await cdp.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x: gas.x, y: gas.y, id: 1 }, { x: right.x, y: right.y, id: 2 }] });
  await page.waitForFunction(() => (window as any).__game.player.input.steer > 0.9, null, { timeout: 10_000 });
  await cdp.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
  await page.waitForFunction(() => (window as any).__game.player.input.throttle === 0, null, { timeout: 10_000 });

  await tap('.tc-btn', 'II');
  await expect(page.locator('.pause-box')).toBeVisible();
  expect(errors).toEqual([]);
});
