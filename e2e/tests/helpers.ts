import { expect, type Page } from '@playwright/test';

/** Low quality + muted audio so SwiftShader keeps up. */
export async function prepare(page: Page) {
  await page.addInitScript(() => {
    if (!localStorage.getItem('touge-settings')) {
      localStorage.setItem(
        'touge-settings',
        JSON.stringify({ state: { quality: 'low', resolutionScale: 0.6, timeOfDay: 'night', masterVolume: 0, sfxVolume: 0, musicVolume: 0, assist: 1, autoShift: true, showGhost: true, showFps: false }, version: 1 }),
      );
    }
  });
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(e.message));
  page.on('console', (m) => {
    if (m.type() === 'error' && !/Failed to load resource/.test(m.text())) errors.push(m.text());
  });
  return errors;
}

export async function waitForTitle(page: Page) {
  // (a game that loads while two others draw on the same software renderer has taken over three minutes)
  await expect(page.locator('.title h1')).toBeVisible({ timeout: 420_000 });
  await page.waitForFunction(() => (window as any).__game?.phase === 'attract');
}
