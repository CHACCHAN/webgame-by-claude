import { expect, test, type Page } from '@playwright/test';
import { prepare, waitForTitle } from './helpers';

// ABOUT and the desk (About → AI窓口). The test stack has no gateway to a language model, so the desk offers the
// plain report form only: the way a report takes when there is no model, or none that answers.

const openAbout = async (page: Page) => {
  await page.goto('/');
  await waitForTitle(page);
};

test('about: the menu entry, the sections by keys, a report through the form, Esc back', async ({ page }) => {
  const errors = await prepare(page);
  await openAbout(page);
  await page.keyboard.press('Enter');
  await page.locator('.menu-list li', { hasText: 'ABOUT' }).click();
  await expect(page.locator('.about-panel')).toBeVisible();
  await expect(page.locator('.shell-top .trail li.now')).toContainText('このゲームについて');
  const open = page.locator('.about-tabs button.on');
  await expect(open).toHaveAttribute('data-tab', 'game');
  await expect(page.locator('.ab-figures')).toContainText('COURSES');

  // who made it comes from the server's configuration: the project's name and no links when nothing is set
  await page.keyboard.press('ArrowRight');
  await expect(open).toHaveAttribute('data-tab', 'maker');
  await expect(page.locator('.ab-who h3')).toHaveText('Touge Nocturne Project');
  await expect(page.locator('.ab-links')).toHaveCount(0);

  await page.keyboard.press('KeyE');
  await expect(open).toHaveAttribute('data-tab', 'tech');
  await expect(page.locator('[data-live="backend"]')).toHaveText(/^(WebGPU|WebGL 2)$/);
  await page.keyboard.press('ArrowRight');
  await expect(open).toHaveAttribute('data-tab', 'credits');
  await expect(page.locator('.ab-credits')).toContainText('VVVF Simulator');
  await expect(page.locator('.ab-credits')).toContainText('OpenRAIL-M');
  await expect(page.locator('.ab-credits a[href*="VVVF-Simulator"]')).toHaveAttribute('rel', /noopener/);

  // the desk without a model: the form
  await page.keyboard.press('ArrowRight');
  await expect(open).toHaveAttribute('data-tab', 'desk');
  await expect(page.locator('.desk-status')).toContainText('FORM ONLY');
  await expect(page.locator('.desk-compose')).toHaveCount(0);
  const field = page.locator('.desk-form textarea');
  await page.keyboard.press('Enter');
  await expect(field).toBeFocused();
  // what is typed stays in the field: no tab changes (A, D, arrows), no way back (Backspace), no fullscreen (F)
  const mark = `e2e-${Date.now()}`;
  await page.keyboard.type(`wasd qe f h ${mark}x`);
  await page.keyboard.press('Backspace');
  await page.keyboard.press('ArrowLeft');
  await page.keyboard.press('ArrowRight');
  // (in the form Enter is a new line; only the chat sends with it)
  await page.keyboard.press('Enter');
  await page.keyboard.type('second line');
  await expect(field).toHaveValue(`wasd qe f h ${mark}\nsecond line`);
  await expect(open).toHaveAttribute('data-tab', 'desk');
  expect(await page.evaluate(() => !!document.fullscreenElement)).toBe(false);
  await page.locator('.desk-kinds .chip[data-kind="request"]').click();
  await expect(page.locator('.desk-kinds .chip.on')).toHaveAttribute('data-kind', 'request');
  await page.locator('.desk-form .cta').click();
  await expect(page.locator('.desk-filed b')).toHaveText(/^[0-9A-Z]{6}$/);
  await expect(page.locator('.desk-filed')).toContainText('要望を受け付けました');
  await expect(field).toHaveValue('');

  // Esc in the field leaves the field, the next one the screen; the menu's focus is on the row left through
  await field.focus();
  await page.keyboard.press('Escape');
  await expect(field).not.toBeFocused();
  await expect(page.locator('.about-panel')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.locator('.menu-list li.active')).toContainText('ABOUT');
  await expect(page.locator('.overlay > .screen')).toHaveCount(1);
  expect(errors).toEqual([]);
});

test('about: the server says what the desk offers; without a model the chat answers 503', async ({ request }) => {
  const content = await (await request.get('/api/content')).json();
  expect(content.desk).toEqual({ enabled: true, ai: false });
  expect(content.about).toEqual({ creator: 'Touge Nocturne Project', note: '', links: [] });
  const chat = await request.post('/api/desk/chat', { data: { messages: [{ role: 'user', content: 'ドリフトのやり方は？' }] } });
  expect(chat.status()).toBe(503);
  expect((await chat.json()).message).toContain('フォーム');
  expect((await request.post('/api/desk/chat', { data: { messages: [{ role: 'system', content: 'x' }] } })).status()).toBe(422);
  expect((await request.post('/api/desk/report', { data: { kind: 'praise', text: 'すばらしい' } })).status()).toBe(422);
});

test.describe('phone', () => {
  // a phone held sideways
  test.use({ viewport: { width: 844, height: 390 }, hasTouch: true, isMobile: true });

  test('about: the panel and the desk fit beside the back button', async ({ page }) => {
    const errors = await prepare(page);
    // (parts slide in: the place to tap is the one that has stopped moving, as in mobile.spec.ts)
    const tap = async (sel: string, text?: string) => {
      const target = page.locator(sel, text ? { hasText: text } : {}).first();
      await target.evaluate(async (el) => {
        for (let n: Element | null = el; n; n = n.parentElement) {
          const running = n.getAnimations().filter((a) => a.effect?.getComputedTiming().iterations !== Infinity);
          await Promise.all(running.map((a) => a.finished.catch(() => undefined)));
        }
      });
      await target.scrollIntoViewIfNeeded();
      let box = (await target.boundingBox())!;
      for (let i = 0; i < 40; i++) {
        await page.waitForTimeout(100);
        const next = (await target.boundingBox())!;
        const still = Math.abs(next.x - box.x) < 0.5 && Math.abs(next.y - box.y) < 0.5;
        box = next;
        if (still) break;
      }
      await page.touchscreen.tap(box.x + box.width / 2, box.y + box.height / 2);
    };
    await openAbout(page);
    await page.touchscreen.tap(422, 195);
    await tap('.menu-list li', 'ABOUT');
    await expect(page.locator('.about-panel')).toBeVisible();
    // every section's tab is on the screen, and the panel keeps clear of the back button's column
    await expect(page.locator('.about-tabs button')).toHaveCount(5);
    for (const b of await page.locator('.about-tabs button').all()) await expect(b).toBeInViewport({ ratio: 1 });
    const panel = (await page.locator('.about-panel').boundingBox())!;
    const back = (await page.locator('.touch-back').boundingBox())!;
    expect(panel.x).toBeGreaterThanOrEqual(back.x + back.width);
    expect(panel.y + panel.height).toBeLessThanOrEqual(390);

    await tap('.about-tabs button[data-tab="desk"]');
    await expect(page.locator('.desk-status')).toContainText('FORM ONLY');
    await expect(page.locator('.desk-form textarea')).toBeInViewport({ ratio: 1 });
    await expect(page.locator('.desk-form .cta')).toBeInViewport({ ratio: 1 });
    // no page-wide scrolling, whatever the section holds
    for (const id of ['credits', 'tech', 'maker', 'game']) {
      await tap(`.about-tabs button[data-tab="${id}"]`);
      await expect(page.locator('.about-tabs button.on')).toHaveAttribute('data-tab', id);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth && document.querySelector('.about-body')!.scrollWidth <= document.querySelector('.about-body')!.clientWidth)).toBe(true);
    }
    // no Esc key on a phone: the on-screen back button
    await tap('.touch-back');
    await expect(page.locator('.menu-list li', { hasText: 'ABOUT' })).toBeVisible();
    expect(errors).toEqual([]);
  });
});
