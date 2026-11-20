// GPU time per render pass at several drawing resolutions inside ONE race (WebGPU timestamps, as tools/perf-pass.cjs),
// as a phone by default (844×390 CSS px, DPR 3, touch, mobile): the renderer's pixel ratio is switched in place (as
// RenderHost.resize does) in short interleaved slices, the order reversed every other round, so the stretch of road
// and the GPU's clock drift are shared by every size. What a pixel costs is the slope of GPU time against megapixels;
// fit it only on slices at the GPU's high clock (the RX 5700 XT idles at 800 MHz core / 500 MHz memory while the
// frame is small: compare `MHz` / `mem` per row). The core and memory clocks are read from amdgpu's pp_dpm files.
//   node tools/perf-res.cjs [out.json]
// Env: URL (http://localhost:4173/), QUALITY (low), COURSE (oboro-downhill), TOD (night), CAR (r34; a rival race
// against the ace, autopilot), PRS (device px per CSS px, default 0.75,1,1.5,2,3), SLICE (ms, 1500), SETTLE (ms before a
// slice is counted, 400), ROUNDS (6), SET (JSON merged into the stored settings), QUERY, FIXED=1 (no switching: the
// page's own ratio for SLICE × ROUNDS × the number of PRS, e.g. with the upscaler), CHROME, PW_MODULE.
// Serve with `API_PROXY=http://127.0.0.1:9 npx vite preview`; /api is also aborted in the browser.
const { chromium } = require(process.env.PW_MODULE || 'playwright');
const fs = require('fs');
const URL_ = process.env.URL || 'http://localhost:4173/';
const QUALITY = process.env.QUALITY || 'low', COURSE = process.env.COURSE || 'oboro-downhill', TOD = process.env.TOD || 'night';
const CAR = process.env.CAR || 'r34';
const PRS = (process.env.PRS || '0.75,1,1.5,2,3').split(',').map(Number);
const SLICE = +(process.env.SLICE || 1500), SETTLE = +(process.env.SETTLE || 400), ROUNDS = +(process.env.ROUNDS || 6);
const FIXED = !!process.env.FIXED;
const SCLK = (() => {
  try {
    const dir = fs.readdirSync('/sys/class/drm').find((d) => /^card\d+$/.test(d) && fs.existsSync(`/sys/class/drm/${d}/device/pp_dpm_sclk`));
    return dir ? `/sys/class/drm/${dir}/device/pp_dpm_sclk` : null;
  } catch { return null; }
})();
const level = (file) => {
  if (!file) return null;
  const line = fs.readFileSync(file, 'utf8').split('\n').find((l) => l.includes('*'));
  return line ? parseInt(line.split(':')[1]) : null;
};
const clock = () => level(SCLK);
const mclock = () => level(SCLK && SCLK.replace('sclk', 'mclk'));
const pct = (a, p) => { const s = [...a].sort((x, y) => x - y); return s.length ? s[Math.min(s.length - 1, Math.floor((p / 100) * s.length))] : 0; };

function instrument() {
  const g = window.__game, r = g.renderer, b = r.backend;
  const P = (window.__pass = { on: true, rec: false, tag: '', labels: new Map(), sum: {}, n: {}, frames: {}, tracked: !!b.trackTimestamp, ft: {}, cpu: {}, info: {} });
  const begin = b.beginRender.bind(b);
  let frame = '', seen = {};
  b.beginRender = (ctx) => {
    begin(ctx);
    const uid = b.getTimestampUID(ctx);
    if (!uid || !P.rec) return;
    const f = uid.slice(uid.lastIndexOf(':f'));
    if (f !== frame) { frame = f; seen = {}; P.frames[P.tag] = (P.frames[P.tag] || 0) + 1; }
    const rt = ctx.renderTarget;
    const tex = rt ? (ctx.textures && ctx.textures[0]) || rt.texture : null;
    let label = `${rt ? tex.name || (rt.depthTexture && !ctx.textures?.length ? 'depth' : 'target') : 'canvas'} ${ctx.width}×${ctx.height}`;
    seen[label] = (seen[label] || 0) + 1;
    if (seen[label] > 1) label += ` #${seen[label]}`;
    P.labels.set(uid, `${P.tag}|${label}`);
  };
  // frame intervals and main-thread time of the frame's callbacks, per tag
  const raf = window.requestAnimationFrame.bind(window);
  let last = -1, cur = 0;
  window.requestAnimationFrame = (cb) => raf((ts) => {
    if (ts !== last) {
      if (P.rec && last >= 0) { (P.ft[P.tag] ||= []).push(ts - last); (P.cpu[P.tag] ||= []).push(cur); }
      last = ts; cur = 0;
    }
    const t0 = performance.now();
    try { cb(ts); } finally { cur += performance.now() - t0; }
  });
  let k = 0;
  P.up = {};
  const tick = async () => {
    if (!P.on) return;
    const fsr = window.__upscaler && window.__upscaler();
    if (fsr && P.rec) {
      const u = (P.up[P.tag] ||= { sum: {}, n: 0 });
      const t = Object.fromEntries(fsr.gpuTimings);
      if (Object.keys(t).length) { u.n++; for (const [name, ms] of Object.entries(t)) u.sum[name] = (u.sum[name] || 0) + ms; }
    }
    if (P.rec) { const i = r.info.render; (P.info[P.tag] ||= []).push([i.drawCalls ?? i.calls, i.triangles]); }
    if (++k % 8 === 0 && b.timestampQueryPool.render) {
      await r.resolveTimestampsAsync('render');
      for (const [uid, ms] of b.timestampQueryPool.render.timestamps) {
        const label = P.labels.get(uid);
        if (!label) continue;
        P.labels.delete(uid);
        P.sum[label] = (P.sum[label] || 0) + ms;
        P.n[label] = (P.n[label] || 0) + 1;
      }
    }
    raf(tick);
  };
  raf(tick);
}

(async () => {
  const browser = await chromium.launch({
    executablePath: process.env.CHROME || '/usr/bin/google-chrome',
    headless: true,
    args: ['--ignore-gpu-blocklist', '--disable-gpu-vsync', '--disable-frame-rate-limit', '--use-angle=vulkan', '--enable-features=Vulkan', '--enable-webgpu-developer-features'],
  });
  const ctx = await browser.newContext({ viewport: { width: 844, height: 390 }, hasTouch: true, isMobile: true, deviceScaleFactor: 3 });
  await ctx.route('**/api/**', (r) => r.abort());
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text().slice(0, 160)); });
  const settings = { quality: QUALITY, resolutionScale: 1, timeOfDay: TOD, masterVolume: 0, sfxVolume: 0, musicVolume: 0, assist: 1, autoShift: true, showGhost: true, cornerGuide: true, controlsGuide: false, showFps: false, courseId: COURSE, ...JSON.parse(process.env.SET || '{}') };
  await page.addInitScript((s) => localStorage.setItem('touge-settings', JSON.stringify({ state: s, version: 1 })), settings);
  await page.goto(URL_ + '?gputime=1' + (process.env.QUERY || ''));
  await page.waitForFunction(() => window.__game && window.__game.phase === 'attract', null, { timeout: 240000 });
  const backend = await page.evaluate(({ car }) => {
    const g = window.__game;
    g.startRace({ mode: 'rival', carId: car, rivalLevel: 'ace' });
    g.autoDrive = true;
    g.countdownT = 0.01;
    return g.renderer.backend.isWebGPUBackend ? 'webgpu' : 'webgl2';
  }, { car: CAR });
  await page.waitForFunction(() => window.__game.phase === 'racing', null, { timeout: 60000 });
  await page.waitForTimeout(4000);
  await page.evaluate(instrument);
  const native = await page.evaluate(() => window.__game.renderer.getPixelRatio());
  const clocks = {};
  let tag = '';
  const mclocks = {};
  const sampler = setInterval(() => { if (tag) { (clocks[tag] ||= []).push(clock()); (mclocks[tag] ||= []).push(mclock()); } }, 200);
  const setPr = (pr) => page.evaluate((pr) => {
    const r = window.__game.renderer, c = r.domElement, p = c.parentElement;
    if (pr) { r.setPixelRatio(pr); r.setSize(Math.max(1, p.clientWidth), Math.max(1, p.clientHeight), false); }
    return [c.width, c.height];
  }, pr);
  const sizes = {};
  const plan = FIXED ? [[native]] : Array.from({ length: ROUNDS }, (_, i) => (i % 2 ? [...PRS].reverse() : PRS));
  for (const round of plan) for (const pr of round) {
    const name = FIXED ? `fixed ${native}` : `pr ${pr}`;
    sizes[name] = await setPr(FIXED ? 0 : pr);
    await page.evaluate((t) => { window.__pass.rec = false; window.__pass.tag = t; }, name);
    tag = '';
    await page.waitForTimeout(SETTLE);
    await page.evaluate(() => (window.__pass.rec = true));
    tag = name;
    await page.waitForTimeout(FIXED ? SLICE * ROUNDS * PRS.length : SLICE);
  }
  tag = '';
  clearInterval(sampler);
  await page.evaluate(() => (window.__pass.rec = false));
  await page.waitForTimeout(800);
  const R = await page.evaluate(() => {
    const P = window.__pass; P.on = false;
    return { tracked: P.tracked, sum: P.sum, n: P.n, frames: P.frames, ft: P.ft, cpu: P.cpu, up: P.up, info: P.info, phase: window.__game.phase, s: window.__game.player.proj.s };
  });
  await browser.close();
  const out = { date: new Date().toISOString(), url: URL_, quality: QUALITY, course: COURSE, tod: TOD, car: CAR, backend, tracked: R.tracked, errors: [...new Set(errors)], distance: Math.round(R.s), phase: R.phase, rows: [] };
  for (const name of Object.keys(sizes)) {
    const [w, h] = sizes[name];
    const frames = R.frames[name] || 1;
    const passes = Object.keys(R.sum).filter((l) => l.startsWith(name + '|') && R.n[l] >= 0.05 * frames).map((l) => ({ label: l.slice(name.length + 1), ms: R.sum[l] / frames, per: R.sum[l] / R.n[l], count: R.n[l] }));
    const up = R.up[name] ? Object.entries(R.up[name].sum).map(([k, v]) => ({ label: `upscaler: ${k}`, ms: v / R.up[name].n })) : [];
    const ft = R.ft[name] || [], cpu = R.cpu[name] || [], mhz = (clocks[name] || []).filter(Boolean), info = R.info[name] || [];
    out.rows.push({ name, size: [w, h], mp: (w * h) / 1e6, gpu: passes.reduce((a, p) => a + p.ms, 0) + up.reduce((a, p) => a + p.ms, 0), passes: [...passes, ...up], frames,
      fps: ft.length ? (1000 * ft.length) / ft.reduce((a, b) => a + b, 0) : 0, frameP50: pct(ft, 50), cpuP50: pct(cpu, 50), mhz: pct(mhz, 50), mhzMin: Math.min(...mhz), mhzMax: Math.max(...mhz), mclk: pct((mclocks[name] || []).filter(Boolean), 50),
      draws: pct(info.map((x) => x[0]), 50), tris: pct(info.map((x) => x[1]), 50) });
  }
  console.log(`${QUALITY} ${COURSE} ${TOD} ${backend}${R.tracked ? '' : ' NO TIMESTAMPS'} | ${out.distance} m, ${out.phase}${out.errors.length ? ' | ERRORS ' + out.errors.join(' ; ') : ''}`);
  for (const r of out.rows) {
    console.log(`${r.name.padEnd(10)} ${r.size.join('×').padEnd(10)} ${r.mp.toFixed(3)} MP | GPU ${r.gpu.toFixed(3)} ms | ${r.fps.toFixed(0)} fps frame p50 ${r.frameP50.toFixed(2)} cpu p50 ${r.cpuP50.toFixed(2)} | ${r.mhz} MHz (${r.mhzMin}–${r.mhzMax}) mem ${r.mclk} | draws ${r.draws} tris ${r.tris} | frames ${r.frames}`);
    for (const p of r.passes) console.log(`     ${p.ms.toFixed(3).padStart(7)} ms  ${p.label}${p.count ? ` (${p.per.toFixed(3)} each, ${p.count})` : ''}`);
  }
  if (process.argv[2]) fs.writeFileSync(process.argv[2], JSON.stringify(out, null, 1));
})().catch((e) => { console.error(e); process.exit(1); });
