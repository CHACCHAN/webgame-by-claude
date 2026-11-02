// Real-GPU performance pass: drives the built game (vite preview) in headless Google Chrome on the host GPU
// (ANGLE over Vulkan by default) and records, per frame, the main-thread time of the animation-frame callbacks,
// Game.update, draw calls / triangles, and the GPU time (EXT_disjoint_timer_query_webgl2) split into shadow maps,
// the main pass and post-processing.
//   node tools/perf-gpu.cjs <course|quality|ab|census> [out.json]
//   course   rival race over each full course (high, night)
//   quality  low/medium/high/ultra × night/rain/dawn, first 40 s of a rival race on 朧峠
//   ab       high, night: freeze frames along each course, each feature switched off in turn
//   census   scene contents per course (meshes, instances, lights, shadow casters, programs)
// The browser runs uncapped (no vsync), so the numbers are costs, not waits. The GPU still picks its own clock
// (an RX 5700 XT moves between 800 and 2100 MHz under this load, with frame costs ~2x apart): the sampled clock is
// reported with every run, and builds are compared with paired runs that alternate (URL=before@…,after@…).
// Env: URL (default http://localhost:4173/; a comma list of name@url pairs runs every config once per build),
// CHROME (default /usr/bin/google-chrome), ANGLE (vulkan | gl-egl),
// W, H, DPR (default 1920×1080 at 1), QUALITY / TOD / COURSES (comma lists) to narrow a plan, DURATION,
// PW_MODULE (playwright or playwright-core module path).
// Serve with `API_PROXY=http://127.0.0.1:9 npx vite preview` so nothing can reach a live backend on :8080
// (preview inherits the dev proxy); /api requests are also aborted in the browser.
const { chromium } = require(process.env.PW_MODULE || 'playwright');
const fs = require('fs');

const TARGETS = (process.env.URL || 'http://localhost:4173/').split(',').map((t) => {
  const at = t.indexOf('@');
  return at > 0 ? { name: t.slice(0, at), url: t.slice(at + 1) } : { name: '', url: t };
});
const W = +(process.env.W || 1920), H = +(process.env.H || 1080), DPR = +(process.env.DPR || 1);
const ALL_COURSES = ['oboro-downhill', 'kirifuri-lakeside', 'tenrou-skyline'];
const list = (v, all) => (v ? v.split(',') : all);
const PLAYER_CAR = 'r34';

/** Runs in the page before any game code: frame and GPU instrumentation on window.__perf. */
function instrument(settings) {
  localStorage.setItem('touge-settings', JSON.stringify({ state: settings, version: 1 }));
  const P = (window.__perf = { on: false, frames: [], cur: null, seg: null, pending: [], pool: [], gl: null, ext: null, game: null });
  const raf = window.requestAnimationFrame.bind(window);
  let lastTs = -1;
  window.requestAnimationFrame = (cb) =>
    raf((ts) => {
      if (ts !== lastTs) {
        lastTs = ts;
        P.newFrame(ts);
      }
      const t0 = performance.now();
      try {
        cb(ts);
      } finally {
        if (P.cur) P.cur.cpu += performance.now() - t0;
        P.endSeg();
      }
    });
  P.newFrame = (ts) => {
    const g = P.game;
    if (P.cur && g) {
      const info = g.renderer.info.render;
      P.cur.calls = info.calls;
      P.cur.tris = info.triangles;
      if (P.on) P.frames.push(P.cur);
    }
    if (g) g.renderer.info.reset();
    P.poll();
    P.cur = P.on && g ? { ts, cpu: 0, upd: 0, calls: 0, tris: 0, sh: 0, gpu: {}, pend: 0, bad: false, s: g.hud.progress, kmh: g.hud.speedKmh } : null;
  };
  P.beginSeg = (name) => {
    if (!P.ext || !P.cur) return;
    if (P.seg && P.seg.name === name) return;
    P.endSeg();
    const q = P.pool.pop() || P.gl.createQuery();
    P.gl.beginQuery(P.ext.TIME_ELAPSED_EXT, q);
    P.seg = { name, q, frame: P.cur };
    P.cur.pend++;
  };
  P.endSeg = () => {
    if (!P.seg) return;
    P.gl.endQuery(P.ext.TIME_ELAPSED_EXT);
    P.pending.push(P.seg);
    P.seg = null;
  };
  P.poll = () => {
    if (!P.ext) return;
    const gl = P.gl;
    const disjoint = gl.getParameter(P.ext.GPU_DISJOINT_EXT);
    while (P.pending.length) {
      const s = P.pending[0];
      if (!gl.getQueryParameter(s.q, gl.QUERY_RESULT_AVAILABLE)) break;
      const ns = gl.getQueryParameter(s.q, gl.QUERY_RESULT);
      P.pending.shift();
      P.pool.push(s.q);
      s.frame.pend--;
      if (disjoint) s.frame.bad = true;
      else s.frame.gpu[s.name] = (s.frame.gpu[s.name] || 0) + ns / 1e6;
    }
  };
  P.hook = (g) => {
    P.game = g;
    const r = g.renderer;
    P.gl = r.getContext();
    P.ext = P.gl.getExtension('EXT_disjoint_timer_query_webgl2');
    r.info.autoReset = false;
    const render = r.render.bind(r);
    r.render = (scene, camera) => {
      P.beginSeg(scene === g.scene ? 'main' : 'post');
      return render(scene, camera);
    };
    const sm = r.shadowMap;
    const smRender = sm.render.bind(sm);
    // three calls this on every render(), post-processing quads included (with no lights)
    sm.render = (lights, ...a) => {
      if (!P.cur || !lights.length || !sm.enabled) return smRender(lights, ...a);
      const before = r.info.render.calls;
      const resume = P.seg ? P.seg.name : 'main';
      P.beginSeg('shadow');
      smRender(lights, ...a);
      P.cur.sh += r.info.render.calls - before;
      P.beginSeg(resume);
    };
    const update = g.update.bind(g);
    g.update = (dt) => {
      const t0 = performance.now();
      update(dt);
      if (P.cur) P.cur.upd += performance.now() - t0;
    };
    return !!P.ext;
  };
  /** frames recorded since the last take, compacted (GPU results still pending are dropped) */
  P.take = () => {
    P.poll();
    const out = P.frames.filter((f) => f.pend === 0 && !f.bad).map((f) => [f.ts, f.cpu, f.upd, f.calls, f.tris, f.sh, f.gpu.shadow || 0, f.gpu.main || 0, f.gpu.post || 0, f.s, f.kmh]);
    const dropped = P.frames.length - out.length;
    P.frames = [];
    return { frames: out, dropped };
  };
}

const COLS = ['ts', 'cpu', 'upd', 'calls', 'tris', 'sh', 'gShadow', 'gMain', 'gPost', 's', 'kmh'];
const col = (frames, name) => frames.map((f) => f[COLS.indexOf(name)]);
const pct = (arr, p) => {
  if (!arr.length) return NaN;
  const a = [...arr].sort((x, y) => x - y);
  return a[Math.min(a.length - 1, Math.floor((p / 100) * a.length))];
};
const r1 = (x) => Math.round(x * 10) / 10;
const r2 = (x) => Math.round(x * 100) / 100;

function summarize(frames) {
  const ts = col(frames, 'ts');
  const iv = ts.slice(1).map((t, i) => t - ts[i]).filter((d) => d > 0);
  const gpu = frames.map((f) => f[6] + f[7] + f[8]);
  const wall = (ts[ts.length - 1] - ts[0]) / 1000;
  return {
    frames: frames.length,
    fps: r1((frames.length - 1) / wall),
    frameMs: { p50: r2(pct(iv, 50)), p95: r2(pct(iv, 95)), p99: r2(pct(iv, 99)), max: r2(Math.max(...iv)) },
    cpuMs: { p50: r2(pct(col(frames, 'cpu'), 50)), p95: r2(pct(col(frames, 'cpu'), 95)), max: r2(Math.max(...col(frames, 'cpu'))) },
    updateMs: { p50: r2(pct(col(frames, 'upd'), 50)), p95: r2(pct(col(frames, 'upd'), 95)) },
    gpuMs: { p50: r2(pct(gpu, 50)), p95: r2(pct(gpu, 95)), p99: r2(pct(gpu, 99)), max: r2(Math.max(...gpu)) },
    gpuSplitP50: { shadow: r2(pct(col(frames, 'gShadow'), 50)), main: r2(pct(col(frames, 'gMain'), 50)), post: r2(pct(col(frames, 'gPost'), 50)) },
    calls: { p50: pct(col(frames, 'calls'), 50), max: Math.max(...col(frames, 'calls')) },
    shadowCalls: { p50: pct(col(frames, 'sh'), 50), max: Math.max(...col(frames, 'sh')) },
    trisK: { p50: Math.round(pct(col(frames, 'tris'), 50) / 1000), max: Math.round(Math.max(...col(frames, 'tris')) / 1000) },
  };
}

/** amdgpu core clock levels (MHz, current one marked *), or null on other drivers */
const SCLK = (() => {
  try {
    const dir = fs.readdirSync('/sys/class/drm').find((d) => /^card\d+$/.test(d) && fs.existsSync(`/sys/class/drm/${d}/device/pp_dpm_sclk`));
    return dir ? `/sys/class/drm/${dir}/device/pp_dpm_sclk` : null;
  } catch {
    return null;
  }
})();
function sampleClock() {
  if (!SCLK) return null;
  const line = fs.readFileSync(SCLK, 'utf8').split('\n').find((l) => l.includes('*'));
  return line ? parseInt(line.split(':')[1]) : null;
}

/** heaviest stretches of road: GPU / CPU medians per 2 % of the course */
function hotspots(frames, n = 5) {
  const bins = new Map();
  for (const f of frames) {
    const b = Math.floor(f[9] * 50);
    if (!bins.has(b)) bins.set(b, []);
    bins.get(b).push(f);
  }
  const rows = [...bins.entries()].map(([b, fs]) => ({
    at: `${b * 2}-${b * 2 + 2}%`,
    gpu: r2(pct(fs.map((f) => f[6] + f[7] + f[8]), 50)),
    shadow: r2(pct(fs.map((f) => f[6]), 50)),
    cpu: r2(pct(fs.map((f) => f[1]), 50)),
    calls: pct(fs.map((f) => f[3]), 50),
    sh: pct(fs.map((f) => f[5]), 50),
  }));
  return { gpu: [...rows].sort((a, b) => b.gpu - a.gpu).slice(0, n), calls: [...rows].sort((a, b) => b.calls - a.calls).slice(0, n) };
}

async function launch() {
  const angle = process.env.ANGLE || 'vulkan';
  const args = ['--ignore-gpu-blocklist', '--disable-gpu-vsync', '--disable-frame-rate-limit', `--use-angle=${angle}`];
  if (angle === 'vulkan') args.push('--enable-features=Vulkan');
  else args.push('--use-gl=angle');
  return chromium.launch({ executablePath: process.env.CHROME || '/usr/bin/google-chrome', headless: true, args });
}

async function openGame(browser, { quality, courseId, tod }, target = TARGETS[0]) {
  const ctx = await browser.newContext({ viewport: { width: W, height: H }, deviceScaleFactor: DPR });
  await ctx.route('**/api/**', (r) => r.abort());
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  const settings = { quality, resolutionScale: 1, timeOfDay: tod, masterVolume: 0, sfxVolume: 0, musicVolume: 0, assist: 1, autoShift: true, showGhost: true, cornerGuide: true, controlsGuide: false, showFps: false, courseId };
  await page.addInitScript(instrument, settings);
  const t0 = Date.now();
  await page.goto(target.url);
  await page.waitForFunction(() => window.__game && window.__game.phase === 'attract', null, { timeout: 180000 });
  const loadMs = Date.now() - t0;
  const timer = await page.evaluate(() => window.__perf.hook(window.__game));
  const renderer = await page.evaluate(() => {
    const gl = window.__game.renderer.getContext();
    const e = gl.getExtension('WEBGL_debug_renderer_info');
    return e ? gl.getParameter(e.UNMASKED_RENDERER_WEBGL) : 'unknown';
  });
  if (!timer) throw new Error('EXT_disjoint_timer_query_webgl2 unavailable: no GPU timings');
  return { ctx, page, errors, loadMs, renderer };
}

/** rival race with the autopilot; resolves once the countdown is skipped and the race runs */
async function startRace(page, rivalLevel = 'ace') {
  await page.evaluate(
    ([car, lvl]) => {
      const g = window.__game;
      g.startRace({ mode: 'rival', carId: car, rivalLevel: lvl });
      g.autoDrive = true;
      g.countdownT = 0.01;
    },
    [PLAYER_CAR, rivalLevel],
  );
  await page.waitForFunction(() => window.__game.phase === 'racing', null, { timeout: 30000 });
}

const frameWait = (page, n) =>
  page.evaluate((k) => new Promise((res) => {
    let i = 0;
    const f = () => (++i >= k ? res() : requestAnimationFrame(f));
    requestAnimationFrame(f);
  }), n);

async function measure(page, { seconds, untilFinish = false }) {
  await page.evaluate(() => { window.__perf.frames = []; window.__perf.on = true; });
  const t0 = Date.now();
  let chunks = [], dropped = 0;
  const clocks = [];
  const sampler = setInterval(() => clocks.push(sampleClock()), 500);
  while (Date.now() - t0 < seconds * 1000) {
    await page.waitForTimeout(2000);
    const r = await page.evaluate(() => window.__perf.take());
    chunks.push(...r.frames);
    dropped += r.dropped;
    if (untilFinish && (await page.evaluate(() => window.__game.phase)) !== 'racing') break;
  }
  clearInterval(sampler);
  await page.evaluate(() => { window.__perf.on = false; });
  await frameWait(page, 4);
  const r = await page.evaluate(() => window.__perf.take());
  chunks.push(...r.frames);
  const mhz = clocks.filter((c) => c);
  const gpuClock = mhz.length ? { p50: pct(mhz, 50), min: Math.min(...mhz), max: Math.max(...mhz) } : null;
  return { frames: chunks, dropped: dropped + r.dropped, wallS: (Date.now() - t0) / 1000, gpuClock };
}

function printSummary(label, s, clock) {
  console.log(
    `${label.padEnd(40)}${clock ? ` ${clock.p50}MHz` : ''} fps ${String(s.fps).padStart(6)} | frame p50 ${s.frameMs.p50} p99 ${s.frameMs.p99} max ${s.frameMs.max} | cpu p50 ${s.cpuMs.p50} p95 ${s.cpuMs.p95} (update ${s.updateMs.p50}) | gpu p50 ${s.gpuMs.p50} p95 ${s.gpuMs.p95} max ${s.gpuMs.max} [sh ${s.gpuSplitP50.shadow} main ${s.gpuSplitP50.main} post ${s.gpuSplitP50.post}] | calls ${s.calls.p50}/${s.calls.max} (shadow ${s.shadowCalls.p50}) | tris ${s.trisK.p50}k/${s.trisK.max}k`,
  );
}

async function planCourse(browser, out) {
  for (const courseId of list(process.env.COURSES, ALL_COURSES)) {
    const quality = process.env.QUALITY || 'high';
    const tod = process.env.TOD || 'night';
    for (const target of TARGETS) {
      const g = await openGame(browser, { quality, courseId, tod }, target);
      await startRace(g.page);
      const m = await measure(g.page, { seconds: +(process.env.DURATION || 330), untilFinish: true });
      const s = summarize(m.frames);
      const label = `${target.name ? target.name + ' ' : ''}${courseId} ${quality}/${tod}`;
      printSummary(label, s, m.gpuClock);
      const hs = hotspots(m.frames);
      console.log('  heaviest GPU:', hs.gpu.map((h) => `${h.at} ${h.gpu}ms (sh ${h.shadow}, calls ${h.calls})`).join(' · '));
      console.log('  most calls:  ', hs.calls.map((h) => `${h.at} ${h.calls} (shadow ${h.sh})`).join(' · '));
      out.push({ plan: 'course', build: target.name, label, courseId, quality, tod, loadMs: g.loadMs, renderer: g.renderer, gpuClock: m.gpuClock, summary: s, hotspots: hs, droppedFrames: m.dropped, errors: g.errors });
      await g.ctx.close();
    }
  }
}

async function planQuality(browser, out) {
  const courseId = list(process.env.COURSES, ALL_COURSES)[0];
  for (const quality of list(process.env.QUALITY, ['low', 'medium', 'high', 'ultra'])) {
    for (const tod of list(process.env.TOD, ['night', 'rain', 'dawn'])) {
      for (const target of TARGETS) {
        const g = await openGame(browser, { quality, courseId, tod }, target);
        await startRace(g.page);
        const m = await measure(g.page, { seconds: +(process.env.DURATION || 40) });
        const s = summarize(m.frames);
        const label = `${target.name ? target.name + ' ' : ''}${courseId} ${quality}/${tod}`;
        printSummary(label, s, m.gpuClock);
        out.push({ plan: 'quality', build: target.name, label, courseId, quality, tod, loadMs: g.loadMs, renderer: g.renderer, gpuClock: m.gpuClock, summary: s, droppedFrames: m.dropped, errors: g.errors });
        await g.ctx.close();
      }
    }
  }
}

/** features switched off one at a time on a frozen frame; each returns its undo */
const VARIANTS = {
  base: () => () => {},
  noSunShadow: () => {
    const g = window.__game;
    const was = g.env.key.castShadow;
    g.env.key.castShadow = false;
    return () => { g.env.key.castShadow = was; };
  },
  noHeadlightShadows: () => {
    const spots = [];
    window.__game.scene.traverse((o) => { if (o.isSpotLight && o.castShadow) spots.push(o); });
    spots.forEach((s) => (s.castShadow = false));
    return () => spots.forEach((s) => (s.castShadow = true));
  },
  noLampLights: () => {
    const ls = window.__game.lampLights;
    ls.forEach((l) => (l.visible = false));
    return () => ls.forEach((l) => (l.visible = true));
  },
  noTrees: () => {
    const t = window.__game.scenery.group.getObjectByName('trees');
    t.visible = false;
    return () => { t.visible = true; };
  },
  noClutter: () => {
    const t = window.__game.scenery.group.getObjectByName('clutter');
    t.visible = false;
    return () => { t.visible = true; };
  },
  noTransmission: () => {
    const mats = new Map();
    window.__game.scene.traverse((o) => {
      if (o.isMesh) for (const m of [].concat(o.material)) if (m.transmission > 0) mats.set(m, m.transmission);
    });
    mats.forEach((_, m) => (m.transmission = 0));
    return () => mats.forEach((t, m) => (m.transmission = t));
  },
  noMirrors: () => {
    const ms = window.__game.scenery.group.children.filter((o) => {
      const p = o.geometry && o.geometry.parameters;
      return o.name === 'curve-mirrors' || (o.isMesh && (o.geometry.type === 'TorusGeometry' || o.geometry.type === 'CircleGeometry' || (o.geometry.type === 'CylinderGeometry' && p.radiusTop === 0.05 && p.height === 2.8)));
    });
    ms.forEach((m) => (m.visible = false));
    return () => ms.forEach((m) => (m.visible = true));
  },
  noTerrain: () => {
    const g = window.__game.scenery.group;
    const ts = ['terrain-near', 'terrain-far'].map((n) => g.getObjectByName(n));
    ts.forEach((t) => (t.visible = false));
    return () => ts.forEach((t) => (t.visible = true));
  },
};

async function planAB(browser, out) {
  for (const courseId of list(process.env.COURSES, ALL_COURSES)) {
    const quality = process.env.QUALITY || 'high';
    const tod = process.env.TOD || 'night';
    const g = await openGame(browser, { quality, courseId, tod });
    await startRace(g.page);
    const points = [];
    for (let k = 0; k < +(process.env.POINTS || 10); k++) {
      await g.page.waitForTimeout(12000);
      if ((await g.page.evaluate(() => window.__game.phase)) !== 'racing') break;
      await g.page.evaluate(() => window.__game.setPaused(true));
      await frameWait(g.page, 30);
      const row = { s: await g.page.evaluate(() => window.__game.hud.progress) };
      for (const [name, fn] of Object.entries(VARIANTS)) {
        await g.page.evaluate(`window.__undo = (${fn.toString()})()`);
        await frameWait(g.page, 20);
        const m = await measureFrames(g.page, 45);
        await g.page.evaluate(() => window.__undo());
        row[name] = { gpu: r2(pct(m.map((f) => f[6] + f[7] + f[8]), 50)), shadow: r2(pct(col(m, 'gShadow'), 50)), main: r2(pct(col(m, 'gMain'), 50)), post: r2(pct(col(m, 'gPost'), 50)), calls: pct(col(m, 'calls'), 50), cpu: r2(pct(col(m, 'cpu'), 50)) };
      }
      points.push(row);
      console.log(`${courseId} @${Math.round(row.s * 100)}%`, Object.entries(row).filter(([k]) => k !== 's').map(([k, v]) => `${k} ${v.gpu}ms/${v.calls}`).join(' · '));
      await g.page.evaluate(() => window.__game.setPaused(false));
    }
    const avg = {};
    for (const name of Object.keys(VARIANTS)) {
      const d = points.map((p) => p.base.gpu - p[name].gpu);
      avg[name] = { savedGpuMsP50: r2(pct(d, 50)), savedGpuMsMax: r2(Math.max(...d)), savedCallsP50: pct(points.map((p) => p.base.calls - p[name].calls), 50) };
    }
    console.log(`${courseId} median saving per feature:`, JSON.stringify(avg));
    out.push({ plan: 'ab', courseId, quality, tod, renderer: g.renderer, points, saving: avg, errors: g.errors });
    await g.ctx.close();
  }
}

async function measureFrames(page, n) {
  await page.evaluate(() => { window.__perf.frames = []; window.__perf.on = true; });
  await frameWait(page, n);
  await page.evaluate(() => { window.__perf.on = false; });
  await frameWait(page, 6);
  return (await page.evaluate(() => window.__perf.take())).frames;
}

async function planCensus(browser, out) {
  for (const courseId of list(process.env.COURSES, ALL_COURSES)) {
    const quality = process.env.QUALITY || 'high';
    const g = await openGame(browser, { quality, courseId, tod: 'night' });
    await startRace(g.page);
    await g.page.waitForTimeout(3000);
    const c = await g.page.evaluate(() => {
      const game = window.__game;
      const res = { meshes: 0, instanced: 0, instances: 0, points: 0, lines: 0, lights: {}, shadowLights: 0, casters: 0, casterTris: 0, materials: new Set(), byGroup: {} };
      const triCount = (geo) => (geo.index ? geo.index.count : geo.attributes.position ? geo.attributes.position.count : 0) / 3;
      game.scene.traverse((o) => {
        if (o.isLight) {
          res.lights[o.type] = (res.lights[o.type] || 0) + 1;
          if (o.castShadow) res.shadowLights++;
        }
        if (o.isPoints) res.points++;
        if (o.isLine || o.isLineSegments) res.lines++;
        if (!o.isMesh) return;
        let top = o;
        while (top.parent && top.parent !== game.scenery.group && top.parent !== game.root && top.parent !== game.scene) top = top.parent;
        const key = top.parent === game.scenery.group ? `scenery/${top.name || top.type}` : top.name || top.type;
        res.byGroup[key] = (res.byGroup[key] || 0) + 1;
        res.meshes++;
        const inst = o.isInstancedMesh ? o.count : 1;
        if (o.isInstancedMesh) { res.instanced++; res.instances += o.count; }
        (Array.isArray(o.material) ? o.material : [o.material]).forEach((m) => res.materials.add(m.uuid));
        if (o.castShadow) { res.casters++; res.casterTris += triCount(o.geometry) * inst; }
      });
      res.materials = res.materials.size;
      res.casterTris = Math.round(res.casterTris);
      res.lamps = game.scenery.lamps.length;
      res.programs = game.renderer.info.programs.length;
      res.memory = { ...game.renderer.info.memory };
      return res;
    });
    console.log(courseId, JSON.stringify(c));
    // one frame's draws by scene group (main pass and shadow maps separately)
    const draws = await g.page.evaluate(() => new Promise((res) => {
      const game = window.__game, r = game.renderer;
      const tally = { main: {}, shadow: {} };
      let inShadow = false, on = false;
      const keyOf = (o) => {
        let top = o;
        while (top.parent && top.parent !== game.scenery.group && top.parent !== game.root && top.parent !== game.scene) top = top.parent;
        const base = top.parent === game.scenery.group ? `scenery/${top.name || top.type}` : top.name || top.type;
        return base === 'scenery/Mesh' ? `scenery/Mesh:${o.geometry.type}` : base;
      };
      const rbd = r.renderBufferDirect;
      r.renderBufferDirect = function (camera, scene, geometry, material, object, group) {
        if (on && game.scene.getObjectById(object.id)) {
          const t = tally[inShadow ? 'shadow' : 'main'];
          const k = keyOf(object);
          const e = (t[k] ??= { calls: 0, ktris: 0 });
          const n = group ? group.count : geometry.index ? geometry.index.count : geometry.attributes.position.count;
          e.calls++;
          e.ktris += (n / 3) * (object.isInstancedMesh ? object.count : 1) / 1000;
        }
        return rbd.apply(this, arguments);
      };
      const sm = r.shadowMap, smr = sm.render;
      sm.render = function (lights) {
        inShadow = lights.length > 0;
        try { return smr.apply(this, arguments); } finally { inShadow = false; }
      };
      requestAnimationFrame(() => {
        on = true;
        requestAnimationFrame(() => {
          on = false;
          r.renderBufferDirect = rbd;
          sm.render = smr;
          for (const t of Object.values(tally)) for (const e of Object.values(t)) e.ktris = Math.round(e.ktris);
          res(tally);
        });
      });
    }));
    for (const pass of ['main', 'shadow']) {
      const rows = Object.entries(draws[pass]).sort((a, b) => b[1].calls - a[1].calls);
      console.log(`  ${pass}:`, rows.map(([k, v]) => `${k} ${v.calls}/${v.ktris}k`).join(' · '));
    }
    out.push({ plan: 'census', courseId, quality, census: c, draws, errors: g.errors });
    await g.ctx.close();
  }
}

module.exports = { launch, openGame, startRace, measure, measureFrames, frameWait, summarize };

if (require.main === module) (async () => {
  const [plan = 'quality', outFile] = process.argv.slice(2);
  const plans = { course: planCourse, quality: planQuality, ab: planAB, census: planCensus };
  if (!plans[plan]) throw new Error(`unknown plan ${plan}: ${Object.keys(plans).join(', ')}`);
  const browser = await launch();
  const out = [];
  try {
    await plans[plan](browser, out);
  } finally {
    await browser.close();
    if (outFile) fs.writeFileSync(outFile, JSON.stringify({ viewport: [W, H, DPR], results: out }, null, 1));
  }
  const errs = out.flatMap((r) => r.errors || []);
  if (errs.length) console.log('page errors:', [...new Set(errs)].slice(0, 8).join('\n'));
})();
