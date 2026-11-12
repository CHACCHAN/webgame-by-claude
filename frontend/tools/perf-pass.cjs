// GPU time per render pass of the built game on the host GPU (WebGPU backend only: its timestamp queries), to see
// where a frame's GPU time goes: shadow maps, the scene, each post-processing pass. tools/perf-frame.cjs gives the
// whole frame's cost (and is the one to compare builds with); this one says which pass a difference comes from.
//   node tools/perf-pass.cjs [out.json]
// The page is opened with `?gputime=1` (RenderHost then asks the renderer to time its passes). A rival race driven
// by the autopilot, uncapped; every pass of every frame is timed for DURATION seconds and averaged per pass, passes
// named by their target's texture name and size, in the order they are drawn (`#2`: the second such pass of a frame).
// The upscaler's compute passes (FSR 3, `@pmndrs/upscaler`: not three.js' passes) are timed by the package itself and
// listed after them as `upscaler: <pass>`.
// Env: URL (default http://localhost:4173/; `a@http://…,b@http://…?x=1` runs each), VARIANTS (JSON, name → settings
// merged into the stored ones), DURATION (15 s), COURSE / TOD / QUALITY (oboro-downhill, night, ultra), W / H
// (1920×1080), CHROME, PW_MODULE. Serve with `API_PROXY=http://127.0.0.1:9 npx vite preview`; /api is also aborted.
const { chromium } = require(process.env.PW_MODULE || 'playwright');
const fs = require('fs');

const TARGETS = (process.env.URL || 'http://localhost:4173/').split(',').map((t) => {
  const at = t.indexOf('@');
  return at > 0 && !t.startsWith('http') ? { name: t.slice(0, at), url: t.slice(at + 1) } : { name: 'build', url: t };
});
const VARIANTS = process.env.VARIANTS ? JSON.parse(process.env.VARIANTS) : null;
if (VARIANTS) {
  const builds = TARGETS.splice(0);
  for (const b of builds) for (const [name, set] of Object.entries(VARIANTS)) TARGETS.push({ name: builds.length > 1 ? `${b.name}/${name}` : name, url: b.url, set });
}
const W = +(process.env.W || 1920), H = +(process.env.H || 1080);
const COURSE = process.env.COURSE || 'oboro-downhill', TOD = process.env.TOD || 'night', QUALITY = process.env.QUALITY || 'ultra';
const DURATION = +(process.env.DURATION || 15);

/** in the page: names every pass as it begins, and gathers the resolved times per name */
function instrument() {
  const g = window.__game, r = g.renderer, b = r.backend;
  const P = (window.__pass = { on: true, labels: new Map(), sum: {}, n: {}, order: [], frames: 0, tracked: !!b.trackTimestamp });
  const begin = b.beginRender.bind(b);
  let frame = '', seen = {};
  b.beginRender = (ctx) => {
    begin(ctx);
    const uid = b.getTimestampUID(ctx);
    if (!uid) return;
    const f = uid.slice(uid.lastIndexOf(':f'));
    if (f !== frame) {
      frame = f;
      seen = {};
      P.frames++;
    }
    const rt = ctx.renderTarget;
    const tex = rt ? (ctx.textures && ctx.textures[0]) || rt.texture : null;
    let label = `${rt ? tex.name || (rt.depthTexture && !ctx.textures?.length ? 'depth' : 'target') : 'canvas'} ${ctx.width}×${ctx.height}`;
    seen[label] = (seen[label] || 0) + 1;
    if (seen[label] > 1) label += ` #${seen[label]}`;
    P.labels.set(uid, label);
  };
  let k = 0;
  const pool = () => b.timestampQueryPool.render;
  P.up = { sum: {}, n: 0 };
  const tick = async () => {
    if (!P.on) return;
    // (the last timed frame's compute passes; a pass that did not run in it is not in the list and counts as 0)
    const fsr = window.__upscaler && window.__upscaler();
    const up = fsr ? Object.fromEntries(fsr.gpuTimings) : {};
    if (Object.keys(up).length) {
      P.up.n++;
      for (const [name, ms] of Object.entries(up)) P.up.sum[name] = (P.up.sum[name] || 0) + ms;
    }
    if (++k % 8 === 0 && pool()) {
      await r.resolveTimestampsAsync('render');
      for (const [uid, ms] of pool().timestamps) {
        const label = P.labels.get(uid);
        if (!label) continue;
        P.labels.delete(uid);
        if (!(label in P.sum)) {
          P.sum[label] = 0;
          P.n[label] = 0;
          P.order.push(label);
        }
        P.sum[label] += ms;
        P.n[label]++;
      }
    }
    requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}

async function run(browser, target) {
  const ctx = await browser.newContext({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
  await ctx.route('**/api/**', (r) => r.abort());
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  const settings = { quality: QUALITY, resolutionScale: 1, timeOfDay: TOD, masterVolume: 0, sfxVolume: 0, musicVolume: 0, assist: 1, autoShift: true, showGhost: true, cornerGuide: true, controlsGuide: false, showFps: false, courseId: COURSE, ...(target.set || {}) };
  await page.addInitScript((s) => localStorage.setItem('touge-settings', JSON.stringify({ state: s, version: 1 })), settings);
  await page.goto(target.url + (target.url.includes('?') ? '&' : '?') + 'gputime=1');
  await page.waitForFunction(() => window.__game && window.__game.phase === 'attract', null, { timeout: 180000 });
  await page.evaluate(() => {
    const g = window.__game;
    g.startRace({ mode: 'rival', carId: 'r34', rivalLevel: 'ace' });
    g.autoDrive = true;
    g.countdownT = 0.01;
  });
  await page.waitForFunction(() => window.__game.phase === 'racing', null, { timeout: 30000 });
  await page.waitForTimeout(4000);
  await page.evaluate(instrument);
  const t0 = Date.now();
  await page.waitForTimeout(DURATION * 1000);
  const r = await page.evaluate(() => {
    const P = window.__pass;
    P.on = false;
    return { tracked: P.tracked, frames: P.frames, passes: P.order.map((label) => ({ label, ms: P.sum[label] / P.n[label], share: P.n[label] })), compute: Object.entries(P.up.sum).map(([name, ms]) => ({ label: `upscaler: ${name}`, ms: ms / P.up.n, every: 1 })) };
  });
  const seconds = (Date.now() - t0) / 1000;
  await ctx.close();
  // (a pass that is not drawn every frame counts for the share of frames it is in)
  const most = Math.max(1, ...r.passes.map((p) => p.share));
  const passes = [...r.passes.map((p) => ({ label: p.label, ms: (p.ms * p.share) / most, every: p.share / most })), ...r.compute];
  return { name: target.name, tracked: r.tracked, fps: r.frames / seconds, total: passes.reduce((a, p) => a + p.ms, 0), passes, errors };
}

(async () => {
  const browser = await chromium.launch({
    executablePath: process.env.CHROME || '/usr/bin/google-chrome',
    headless: true,
    args: ['--ignore-gpu-blocklist', '--disable-gpu-vsync', '--disable-frame-rate-limit', '--use-angle=vulkan', '--enable-features=Vulkan', '--enable-webgpu-developer-features'],
  });
  const rows = [];
  for (const target of TARGETS) {
    const row = await run(browser, target);
    rows.push(row);
    console.log(`\n${row.name}: ${row.fps.toFixed(1)} fps, GPU ${row.total.toFixed(2)} ms in ${row.passes.length} passes${row.tracked ? '' : ' (NO TIMESTAMPS: not the WebGPU backend, or the build lacks ?gputime)'}${row.errors.length ? ` | PAGE ERRORS ${row.errors[0]}` : ''}`);
    for (const p of row.passes) console.log(`  ${p.ms.toFixed(3).padStart(7)} ms  ${p.label}${p.every < 0.99 ? `  (${Math.round(p.every * 100)} % of frames)` : ''}`);
  }
  await browser.close();
  if (process.argv[2]) fs.writeFileSync(process.argv[2], JSON.stringify({ date: new Date().toISOString(), size: [W, H], course: COURSE, tod: TOD, quality: QUALITY, duration: DURATION, rows }, null, 1));
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
