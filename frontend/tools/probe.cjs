// Browser check helper: loads the built game (vite preview on :4173 by default) in headless Chromium
// (SwiftShader WebGL), waits for the title scene, then runs an async check script with the page.
//   node tools/probe.cjs <low|medium|high> <absolute path to script.cjs> [width] [height]
// The script exports `async (page, { fps, out }) => {}`; `window.__game` is the Game instance.
// Env: URL (default http://localhost:4173/, e.g. add ?timescale=8), OUT (screenshot folder, default
// tools/scratch — gitignored), PW_MODULE (playwright module path if `require('playwright')` fails).
// SwiftShader runs at ~1–6 fps: for logic-only checks set `window.__game.renderer.render = () => {}`.
const { chromium } = require(process.env.PW_MODULE || 'playwright');
const fs = require('fs');
const path = require('path');

(async () => {
  const [quality = 'low', scriptPath, w = '1280', h = '720'] = process.argv.slice(2);
  if (!scriptPath) throw new Error('usage: node tools/probe.cjs <quality> <script.cjs> [w] [h]');
  const out = path.resolve(process.env.OUT || 'tools/scratch');
  fs.mkdirSync(out, { recursive: true });
  const browser = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const page = await browser.newPage({ viewport: { width: +w, height: +h } });
  const logs = [];
  page.on('console', (m) => logs.push(`[${m.type()}] ${m.text()}`));
  page.on('pageerror', (e) => logs.push(`[pageerror] ${e.message}`));
  await page.addInitScript(
    (q) =>
      localStorage.setItem(
        'touge-settings',
        JSON.stringify({ state: { quality: q, resolutionScale: 1, timeOfDay: 'night', masterVolume: 0, sfxVolume: 0, musicVolume: 0, assist: 1, autoShift: true, showGhost: true, showFps: true }, version: 1 }),
      ),
    quality,
  );
  const t0 = Date.now();
  await page.goto(process.env.URL || 'http://localhost:4173/');
  await page.waitForFunction(() => window.__game && window.__game.phase === 'attract', null, { timeout: 180000 });
  console.log('loaded in', Date.now() - t0, 'ms');
  const fps = () =>
    page.evaluate(
      () =>
        new Promise((res) => {
          let n = 0;
          const t = performance.now();
          const f = () => {
            n++;
            if (performance.now() - t < 3000) requestAnimationFrame(f);
            else res((n / (performance.now() - t)) * 1000);
          };
          requestAnimationFrame(f);
        }),
    );
  await require(path.resolve(scriptPath))(page, { fps, out });
  const shown = logs.filter((l) => !l.includes('DevTools') && !l.includes('useProgram') && !l.includes('THREE.Clock'));
  if (shown.length) console.log(shown.map((l) => l.slice(0, 1500)).slice(0, 12).join('\n'));
  await browser.close();
})();
