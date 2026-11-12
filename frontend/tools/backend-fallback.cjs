// The renderer's fallback from WebGPU to WebGL 2 (render/backendChoice.ts, ui/GameCanvas.tsx), on the host GPU.
// Each case is a fresh browser context; "up" = the game reached the attract phase and a frame was drawn.
//   node tools/backend-fallback.cjs            exit code 1 when a case did not end as expected
// Env: URL (http://localhost:4173/), CHROME, PW_MODULE, OUT (directory for a picture per case), ONLY (cases whose name
// holds this), SET (settings JSON laid over every case's stored settings, e.g. '{"upscale":true}').
// Serve with `API_PROXY=http://127.0.0.1:9 npx vite preview`; /api is also aborted in the browser.
const { chromium } = require(process.env.PW_MODULE || 'playwright');
const URL_ = process.env.URL || 'http://localhost:4173/';
const OUT = process.env.OUT;

const state = (page) => page.evaluate(() => ({
  backend: window.__game.renderer.backend.isWebGPUBackend ? 'webgpu' : 'webgl2',
  frames: window.__game.renderer.info.frame,
}));
const up = async (page) => {
  await page.waitForFunction(() => window.__game && window.__game.phase === 'attract', null, { timeout: 240000 });
  const a = await state(page);
  await page.waitForTimeout(1500);
  const b = await state(page);
  return { backend: b.backend, drawing: b.frames > a.frames };
};
// what the settings screen would say is running, and why (store/app.ts `renderer`): read through the page's modules
// is not possible from here, so the reason is taken from the console's note and the storage instead
const storage = (page) => page.evaluate(() => ({ lasting: localStorage.getItem('touge-backend-fallback'), session: sessionStorage.getItem('touge-backend-lost') }));

const CASES = [
  { name: 'WebGPU as it is', expect: 'webgpu' },
  { name: '?webgl=1', query: '?webgl=1', expect: 'webgl2' },
  { name: 'setting WebGL 2', settings: { backend: 'webgl2' }, expect: 'webgl2' },
  { name: 'no navigator.gpu', init: () => Object.defineProperty(Navigator.prototype, 'gpu', { get: () => undefined }), expect: 'webgl2' },
  { name: 'no adapter', init: () => (navigator.gpu.requestAdapter = async () => null), expect: 'webgl2' },
  {
    name: 'the device is refused',
    init: () => {
      const real = navigator.gpu.requestAdapter.bind(navigator.gpu);
      navigator.gpu.requestAdapter = async (o) => {
        const adapter = await real(o);
        adapter.requestDevice = async () => { throw new Error('test: no device'); };
        return adapter;
      };
    },
    expect: 'webgl2',
  },
  {
    // the canvas has given its `webgpu` context when the device fails: three.js' own fallback cannot take the same
    // canvas (no `webgl2` context from it), so the page starts again on a new one
    name: 'no device, the canvas already taken',
    init: () => {
      const real = navigator.gpu.requestAdapter.bind(navigator.gpu);
      navigator.gpu.requestAdapter = async (o) => {
        const adapter = await real(o);
        adapter.requestDevice = async () => {
          document.querySelector('canvas').getContext('webgpu');
          throw new Error('test: no device');
        };
        return adapter;
      };
    },
    expect: 'webgl2', remembered: true,
  },
  {
    // WebGPU comes up and then every frame throws: WebGL 2 after a reload
    name: 'drawing throws on WebGPU',
    init: () => {
      GPUCanvasContext.prototype.configure = function () {
        throw new Error('test: configure failed');
      };
    },
    boot: async (page) => page.waitForFunction(() => window.__game && !window.__game.renderer.backend.isWebGPUBackend, null, { timeout: 60000 }),
    expect: 'webgl2', remembered: true,
  },
  {
    name: 'errors in a burst',
    after: async (page) => {
      await Promise.all([
        page.waitForEvent('framenavigated', { timeout: 20000 }),
        page.evaluate(() => { for (let i = 0; i < 20; i++) window.__game.renderer.onError({ api: 'WebGPU', type: 'GPUValidationError', message: 'test' }); }),
      ]);
    },
    expect: 'webgl2', remembered: true,
  },
  {
    name: 'a few stray errors',
    after: async (page) => {
      await page.evaluate(() => { for (let i = 0; i < 5; i++) window.__game.renderer.onError({ api: 'WebGPU', type: 'GPUValidationError', message: 'test' }); });
      await page.waitForTimeout(1500);
    },
    expect: 'webgpu',
  },
  {
    name: 'errors in a burst, WebGPU chosen by hand',
    settings: { backend: 'webgpu' },
    after: async (page) => {
      await page.evaluate(() => { for (let i = 0; i < 20; i++) window.__game.renderer.onError({ api: 'WebGPU', type: 'GPUValidationError', message: 'test' }); });
      await page.waitForTimeout(1500);
    },
    expect: 'webgpu',
  },
  {
    name: 'the device is lost once',
    after: async (page) => {
      await Promise.all([
        page.waitForEvent('framenavigated', { timeout: 20000 }),
        page.evaluate(() => window.__game.renderer.onDeviceLost({ api: 'WebGPU', message: 'test', reason: 'unknown' })),
      ]);
    },
    expect: 'webgpu',
  },
  {
    name: 'the device is lost twice',
    after: async (page) => {
      for (let i = 0; i < 2; i++) {
        await Promise.all([
          page.waitForEvent('framenavigated', { timeout: 20000 }),
          page.evaluate(() => window.__game.renderer.onDeviceLost({ api: 'WebGPU', message: 'test', reason: 'unknown' })),
        ]);
        if (i === 0) await up(page);
      }
    },
    expect: 'webgl2',
  },
  {
    // … and the WebGL 2 context right after that reload: no third reload, a message instead
    name: 'lost a third time at once',
    after: async (page) => {
      for (let i = 0; i < 2; i++) {
        await Promise.all([
          page.waitForEvent('framenavigated', { timeout: 20000 }),
          page.evaluate(() => window.__game.renderer.onDeviceLost({ api: 'WebGPU', message: 'test', reason: 'unknown' })),
        ]);
        await up(page);
      }
      await page.evaluate(() => window.__game.renderer.onDeviceLost({ api: 'WebGL', message: 'test', reason: null }));
      await page.waitForTimeout(1500);
    },
    expect: 'webgl2', message: /繰り返し失われた/,
  },
];

(async () => {
  const browser = await chromium.launch({
    executablePath: process.env.CHROME || '/usr/bin/google-chrome',
    headless: true,
    args: ['--ignore-gpu-blocklist', '--use-angle=vulkan', '--enable-features=Vulkan'],
  });
  let bad = 0;
  const only = process.env.ONLY;
  for (const c of CASES) {
    if (only && !c.name.includes(only)) continue;
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 720 } });
    await ctx.route('**/api/**', (r) => r.abort());
    const page = await ctx.newPage();
    const errors = [];
    page.on('pageerror', (e) => errors.push(e.message.slice(0, 120)));
    const notes = [];
    page.on('console', (m) => /WebGPU is not available|renderer:/.test(m.text()) && notes.push(m.text().slice(0, 90)));
    await page.addInitScript((s) => {
      if (!localStorage.getItem('touge-settings')) localStorage.setItem('touge-settings', JSON.stringify({ state: { quality: 'low', timeOfDay: 'night', masterVolume: 0, ...s }, version: 1 }));
    }, { ...JSON.parse(process.env.SET || '{}'), ...(c.settings || {}) });
    if (c.init) await page.addInitScript(c.init);
    let got, why = '';
    try {
      await page.goto(URL_ + (c.query || ''));
      if (c.boot) await c.boot(page);
      await up(page);
      if (c.after) await c.after(page);
      got = await up(page);
      const st = await storage(page);
      const message = await page.evaluate(() => document.querySelector('.no-webgl')?.textContent || '');
      if (got.backend !== c.expect) why = `backend ${got.backend}`;
      // (after the message the renderer is expected to stand still)
      else if (!got.drawing && !c.message) why = 'nothing is drawn';
      else if (!!c.remembered !== !!st.lasting) why = `remembered: ${st.lasting}`;
      else if (c.message ? !c.message.test(message) : message) why = `message: "${message.slice(0, 40)}"`;
      if (OUT) await page.screenshot({ path: `${OUT}/${c.name.replace(/[^a-z0-9]+/gi, '-')}.jpg`, quality: 70, type: 'jpeg' });
    } catch (e) {
      why = String(e.message || e).split('\n')[0].slice(0, 160);
    }
    if (why) bad++;
    console.log(`${why ? 'FAIL' : 'ok  '} ${c.name.padEnd(44)} → ${got ? got.backend : '-'}${why ? `   (${why})` : ''}${notes.length ? `   [${[...new Set(notes)].join(' | ')}]` : ''}${errors.length ? `   page errors: ${errors.slice(0, 2).join(' | ')}` : ''}`);
    await ctx.close();
  }
  await browser.close();
  process.exit(bad ? 1 : 0);
})();
