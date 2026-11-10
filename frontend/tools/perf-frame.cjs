// Frame cost of the built game on the host GPU, whatever the renderer's backend (WebGPU or WebGL 2): headless Google
// Chrome running uncapped (no vsync), a rival race driven by the autopilot, and per frame the interval between
// animation frames (the whole cost: main thread and GPU) and the main-thread time of the frame's callbacks.
// tools/perf-gpu.cjs splits the GPU time by pass but needs the old WebGLRenderer's timer queries.
//   node tools/perf-frame.cjs [out.json]
// Env: URL (default http://localhost:4173/; `before@http://…:4174/,after@http://…:4173/` runs every case once per
// build and round, alternating: the GPU picks its own clock, so only paired runs compare), ROUNDS (2), DURATION (30 s),
// COURSES / TOD / QUALITY (comma lists; default oboro-downhill, night, high), W / H / DPR (1920×1080 at 1), CHROME,
// PW_MODULE. Serve with `API_PROXY=http://127.0.0.1:9 npx vite preview`; /api is also aborted in the browser.
const { chromium } = require(process.env.PW_MODULE || 'playwright');
const fs = require('fs');

const TARGETS = (process.env.URL || 'http://localhost:4173/').split(',').map((t) => {
  const at = t.indexOf('@');
  return at > 0 ? { name: t.slice(0, at), url: t.slice(at + 1) } : { name: 'build', url: t };
});
const W = +(process.env.W || 1920), H = +(process.env.H || 1080), DPR = +(process.env.DPR || 1);
const list = (v, all) => (v ? v.split(',') : all);
const COURSES = list(process.env.COURSES, ['oboro-downhill']);
const TODS = list(process.env.TOD, ['night']);
const QUALITIES = list(process.env.QUALITY, ['high']);
const ROUNDS = +(process.env.ROUNDS || 2), DURATION = +(process.env.DURATION || 30);

/** runs in the page before any game code: frame timestamps and callback time on window.__perf */
function instrument(settings) {
  localStorage.setItem('touge-settings', JSON.stringify({ state: settings, version: 1 }));
  const P = (window.__perf = { on: false, ts: [], cpu: [], cur: 0 });
  const raf = window.requestAnimationFrame.bind(window);
  let last = -1;
  window.requestAnimationFrame = (cb) =>
    raf((ts) => {
      if (ts !== last) {
        if (P.on && last >= 0) {
          P.ts.push(ts);
          P.cpu.push(P.cur);
        }
        last = ts;
        P.cur = 0;
      }
      const t0 = performance.now();
      try {
        cb(ts);
      } finally {
        P.cur += performance.now() - t0;
      }
    });
}

const SCLK = (() => {
  try {
    const dir = fs.readdirSync('/sys/class/drm').find((d) => /^card\d+$/.test(d) && fs.existsSync(`/sys/class/drm/${d}/device/pp_dpm_sclk`));
    return dir ? `/sys/class/drm/${dir}/device/pp_dpm_sclk` : null;
  } catch {
    return null;
  }
})();
const clock = () => {
  if (!SCLK) return null;
  const line = fs.readFileSync(SCLK, 'utf8').split('\n').find((l) => l.includes('*'));
  return line ? parseInt(line.split(':')[1]) : null;
};
const pct = (a, p) => {
  const s = [...a].sort((x, y) => x - y);
  return s.length ? s[Math.min(s.length - 1, Math.floor((p / 100) * s.length))] : 0;
};
const r2 = (v) => Math.round(v * 100) / 100;

async function run(browser, target, c) {
  const ctx = await browser.newContext({ viewport: { width: W, height: H }, deviceScaleFactor: DPR });
  await ctx.route('**/api/**', (r) => r.abort());
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  const settings = { quality: c.quality, resolutionScale: 1, timeOfDay: c.tod, masterVolume: 0, sfxVolume: 0, musicVolume: 0, assist: 1, autoShift: true, showGhost: true, cornerGuide: true, controlsGuide: false, showFps: false, courseId: c.courseId };
  await page.addInitScript(instrument, settings);
  const t0 = Date.now();
  await page.goto(target.url);
  await page.waitForFunction(() => window.__game && window.__game.phase === 'attract', null, { timeout: 180000 });
  const loadMs = Date.now() - t0;
  const backend = await page.evaluate(() => {
    const g = window.__game;
    g.startRace({ mode: 'rival', carId: 'r34', rivalLevel: 'ace' });
    g.autoDrive = true;
    g.countdownT = 0.01;
    const b = g.renderer.backend;
    return b ? (b.isWebGPUBackend ? 'webgpu' : 'webgl2 backend') : 'webgl (old renderer)';
  });
  await page.waitForFunction(() => window.__game.phase === 'racing', null, { timeout: 30000 });
  // the first seconds compile what the race shows first
  await page.waitForTimeout(4000);
  await page.evaluate(() => { window.__perf.ts = []; window.__perf.cpu = []; window.__perf.on = true; });
  const clocks = [];
  const sampler = setInterval(() => clocks.push(clock()), 500);
  await page.waitForTimeout(DURATION * 1000);
  clearInterval(sampler);
  const r = await page.evaluate(() => {
    const P = window.__perf;
    P.on = false;
    const g = window.__game;
    return { ts: P.ts, cpu: P.cpu, phase: g.phase, s: g.player ? g.player.proj.s : 0 };
  });
  await ctx.close();
  const iv = r.ts.slice(1).map((t, i) => t - r.ts[i]).filter((d) => d > 0);
  const mhz = clocks.filter((v) => v);
  return {
    build: target.name, ...c, backend, loadMs, frames: r.ts.length, distance: Math.round(r.s), phase: r.phase,
    fps: r2((iv.length * 1000) / iv.reduce((a, b) => a + b, 0)),
    frameMs: { p50: r2(pct(iv, 50)), p95: r2(pct(iv, 95)), p99: r2(pct(iv, 99)), max: r2(Math.max(...iv)) },
    cpuMs: { p50: r2(pct(r.cpu, 50)), p95: r2(pct(r.cpu, 95)) },
    gpuMHz: mhz.length ? pct(mhz, 50) : null,
    errors,
  };
}

(async () => {
  const browser = await chromium.launch({
    executablePath: process.env.CHROME || '/usr/bin/google-chrome',
    headless: true,
    args: ['--ignore-gpu-blocklist', '--disable-gpu-vsync', '--disable-frame-rate-limit', '--use-angle=vulkan', '--enable-features=Vulkan'],
  });
  const rows = [];
  for (const courseId of COURSES) for (const tod of TODS) for (const quality of QUALITIES) {
    for (let round = 0; round < ROUNDS; round++) {
      for (const target of TARGETS) {
        const row = await run(browser, target, { courseId, tod, quality });
        rows.push(row);
        console.log(
          `${target.name.padEnd(8)} ${courseId} ${tod} ${quality} #${round + 1}: ${row.backend}, ${row.fps} fps | frame p50 ${row.frameMs.p50} p95 ${row.frameMs.p95} p99 ${row.frameMs.p99} max ${row.frameMs.max} ms | cpu p50 ${row.cpuMs.p50} p95 ${row.cpuMs.p95} ms | ${row.gpuMHz ?? '?'} MHz | load ${row.loadMs} ms, ${row.distance} m${row.errors.length ? ` | PAGE ERRORS ${row.errors[0]}` : ''}`,
        );
      }
    }
  }
  await browser.close();
  if (process.argv[2]) fs.writeFileSync(process.argv[2], JSON.stringify({ date: new Date().toISOString(), size: [W, H, DPR], duration: DURATION, rows }, null, 1));
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
