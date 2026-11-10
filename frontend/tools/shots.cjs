// Fixed-viewpoint screenshots of the built game on the host GPU: the same frames every time, to compare the look of
// two builds (docs/FABLE_PLAN.md Phase A).
//   node tools/shots.cjs <label> [outDir]
// Opens every course × time of day, starts a time attack with the HUD hidden, puts the car at fixed points of the
// course (start, the tightest hairpin, fractions of the lap, the finish), lets the frame settle and saves a JPEG per
// point (the game is stepped by hand, so the frame does not depend on the frame rate); then a contact sheet per course (WebP, PIL on the host python) into <outDir>/sheets.
// Output: <outDir> (default ~/.local/opt/quality/<label>): <course>/<tod>/<nn>-<name>.jpg, sheets/<course>.webp,
// index.json (renderer, backend, viewpoints, page errors).
// Env: URL (default http://localhost:4173/), CHROME, W / H / DPR (1920×1080 at 1), QUALITY (ultra), CAR (r34),
// COURSES / TOD (comma lists), CAMERA (chase | near | bumper), WEBGPU=1 (adds the WebGPU launch flags),
// SET (JSON merged into the stored settings, e.g. '{"upscale":true,"upscaleMode":"quality"}'), MOVING (km/h: the
// car is driven by the AI from that speed and the picture is the 90th frame on the move, each a 1/60 s step, for
// what only shows in motion: trails behind the car, flicker; without it the frame is a still one), PW_MODULE. Serve with `API_PROXY=http://127.0.0.1:9 npx vite preview`; /api is also aborted in the browser.
const { chromium } = require(process.env.PW_MODULE || 'playwright');
const fs = require('fs');
const path = require('path');
const os = require('os');
const { execFileSync } = require('child_process');

const label = process.argv[2];
if (!label) {
  console.error('usage: node tools/shots.cjs <label> [outDir]');
  process.exit(1);
}
const OUT = process.argv[3] || path.join(os.homedir(), '.local/opt/quality', label);
const URL_ = process.env.URL || 'http://localhost:4173/';
const W = +(process.env.W || 1920), H = +(process.env.H || 1080), DPR = +(process.env.DPR || 1);
const QUALITY = process.env.QUALITY || 'ultra';
const CAR = process.env.CAR || 'r34';
const CAMERA = process.env.CAMERA || 'chase';
const SET = process.env.SET ? JSON.parse(process.env.SET) : {};
const MOVING = +(process.env.MOVING || 0);
const list = (v, all) => (v ? v.split(',') : all);
const COURSES = list(process.env.COURSES, ['oboro-downhill', 'kirifuri-lakeside', 'tenrou-skyline', 'autobahn']);
const TODS = list(process.env.TOD, ['night', 'rain', 'dawn']);
/** viewpoints as fractions of the timed lap (the tightest hairpin is added per course) */
const FRACTIONS = [
  ['start', 0.004],
  ['early', 0.16],
  ['third', 0.34],
  ['half', 0.5],
  ['late', 0.68],
  ['near-end', 0.86],
  ['finish', 0.985],
];

async function launch() {
  const args = ['--ignore-gpu-blocklist', '--use-angle=vulkan', '--enable-features=Vulkan'];
  if (process.env.WEBGPU) args.push('--enable-unsafe-webgpu', '--enable-features=Vulkan,WebGPU');
  return chromium.launch({ executablePath: process.env.CHROME || '/usr/bin/google-chrome', headless: true, args });
}

const frames = (page, n) =>
  page.evaluate((k) => new Promise((res) => {
    let i = 0;
    const f = () => (++i >= k ? res() : requestAnimationFrame(f));
    requestAnimationFrame(f);
  }), n);

async function main() {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await launch();
  const index = { label, url: URL_, size: [W, H, DPR], quality: QUALITY, car: CAR, camera: CAMERA, date: new Date().toISOString(), runs: [] };
  for (const courseId of COURSES) {
    for (const tod of TODS) {
      const ctx = await browser.newContext({ viewport: { width: W, height: H }, deviceScaleFactor: DPR });
      await ctx.route('**/api/**', (r) => r.abort());
      const page = await ctx.newPage();
      const errors = [];
      page.on('pageerror', (e) => errors.push(e.message));
      // shader compile errors and three.js warnings only reach the console
      const consoleMsgs = new Map();
      page.on('console', (m) => {
        if (m.type() !== 'error' && m.type() !== 'warning') return;
        const t = m.text().slice(0, 600);
        if (/net::ERR_FAILED|Failed to load resource/.test(t)) return;
        consoleMsgs.set(t, (consoleMsgs.get(t) || 0) + 1);
      });
      const settings = { quality: QUALITY, resolutionScale: 1, timeOfDay: tod, masterVolume: 0, sfxVolume: 0, musicVolume: 0, assist: 1, autoShift: true, showGhost: false, cornerGuide: false, controlsGuide: false, showFps: false, courseId, ...SET };
      await page.addInitScript((s) => localStorage.setItem('touge-settings', JSON.stringify({ state: s, version: 1 })), settings);
      await page.goto(URL_);
      await page.waitForFunction(() => window.__game && window.__game.phase === 'attract', null, { timeout: 180000 });
      await page.addStyleTag({ content: '.overlay, .hud, .touch-controls { display: none !important; }' });
      const info = await page.evaluate(
        ([car, cam]) => {
          const g = window.__game;
          g.startRace({ mode: 'time_attack', carId: car });
          g.countdownT = 0.01;
          g.chase.mode = cam;
          const r = g.renderer;
          let renderer = 'unknown';
          try {
            const gl = r.getContext();
            const e = gl.getExtension && gl.getExtension('WEBGL_debug_renderer_info');
            if (e) renderer = gl.getParameter(e.UNMASKED_RENDERER_WEBGL);
          } catch {}
          const backend = r.backend ? (r.backend.isWebGPUBackend ? 'webgpu' : 'webgl2 (WebGPURenderer)') : 'webgl2';
          // the tightest hairpin: a car's length before its apex
          const hair = [...g.corners].sort((a, b) => a.minRadius - b.minRadius)[0];
          return { renderer, backend, startS: g.track.startS, finishS: g.track.finishS, hairpin: hair ? hair.apex - 12 : null };
        },
        [CAR, CAMERA],
      );
      await page.waitForFunction(() => window.__game.phase === 'racing', null, { timeout: 30000 });
      const points = FRACTIONS.map(([name, f]) => [name, info.startS + f * (info.finishS - info.startS)]);
      if (info.hairpin !== null) points.splice(2, 0, ['hairpin', info.hairpin]);
      const dir = path.join(OUT, courseId, tod);
      fs.mkdirSync(dir, { recursive: true });
      const shots = [];
      for (let i = 0; i < points.length; i++) {
        const [name, s] = points[i];
        if (MOVING) await page.evaluate(([at, v]) => {
          const g = window.__game;
          const step = Object.getPrototypeOf(g).update.bind(g);
          g.update = () => {};
          g.setPaused(false);
          g.autoDrive = true;
          const lat = Math.max(-2, Math.min(2, g.line.offsetAt(at)));
          g.player.sim.reset(g.track.pointAt(at, lat), g.track.headingAt(at), v);
          g.player.proj.index = -1;
          g.chase.reset();
          for (let k = 0; k < 30; k++) step(1 / 60);
          // ninety frames on the move (an upscaler's history has settled by then), each one step of the game and one picture; the loop stops on the last one, so
          // the screenshot is a frame in motion (a still scene would go on gathering samples and hide the trails)
          const loop = g.renderer.getAnimationLoop();
          window.__loop = loop;
          return new Promise((res) => {
            let i = 0;
            g.renderer.setAnimationLoop((ms) => {
              step(1 / 60);
              loop(ms);
              if (++i >= 90) {
                g.renderer.setAnimationLoop(null);
                res();
              }
            });
          });
        }, [s, MOVING / 3.6]);
        else await page.evaluate((at) => {
          const g = window.__game;
          // the frame loop's own updates are swallowed and the game is stepped by hand at a fixed 1/60 s: the same
          // frame whatever the frame rate (a slow build used to roll further before its picture)
          const step = Object.getPrototypeOf(g).update.bind(g);
          g.update = () => {};
          g.setPaused(false);
          const lat = Math.max(-2, Math.min(2, g.line.offsetAt(at)));
          // rolling at 60 km/h: the chase camera and the lamps sit as they do on the move
          g.player.sim.reset(g.track.pointAt(at, lat), g.track.headingAt(at), 16.7);
          g.player.proj.index = -1;
          g.chase.reset();
          for (let k = 0; k < 45; k++) step(1 / 60);
          g.setPaused(true);
          for (let k = 0; k < 4; k++) step(1 / 60);
        }, s);
        // the frozen frame is drawn over and over: time for the tree LODs, the lamp pool and late pipelines
        if (!MOVING) await frames(page, 30);
        const file = path.join(dir, `${String(i).padStart(2, '0')}-${name}.jpg`);
        await page.screenshot({ path: file, type: 'jpeg', quality: 92 });
        if (MOVING) await page.evaluate(() => window.__game.renderer.setAnimationLoop(window.__loop));
        shots.push({ name, s: Math.round(s), file: path.relative(OUT, file) });
      }
      const consoleList = [...consoleMsgs].map(([text, count]) => ({ text, count }));
      index.runs.push({ courseId, tod, renderer: info.renderer, backend: info.backend, shots, errors, console: consoleList });
      for (const c of consoleList.slice(0, 12)) console.log(`  console ×${c.count}: ${c.text.slice(0, 300)}`);
      console.log(`${courseId} ${tod}: ${shots.length} shots, ${info.backend}, ${info.renderer}${errors.length ? `, PAGE ERRORS: ${errors.slice(0, 3).join(' | ')}` : ''}`);
      await ctx.close();
    }
  }
  await browser.close();
  fs.writeFileSync(path.join(OUT, 'index.json'), JSON.stringify(index, null, 1));
  // contact sheets: a row per time of day, a column per viewpoint
  const py = `
import json, sys, os
from PIL import Image, ImageDraw
out = sys.argv[1]
idx = json.load(open(os.path.join(out, 'index.json')))
os.makedirs(os.path.join(out, 'sheets'), exist_ok=True)
by = {}
for r in idx['runs']:
    by.setdefault(r['courseId'], []).append(r)
TW, TH = 480, 270
for course, runs in by.items():
    cols = max(len(r['shots']) for r in runs)
    sheet = Image.new('RGB', (cols * TW, len(runs) * TH), (0, 0, 0))
    d = ImageDraw.Draw(sheet)
    for j, r in enumerate(runs):
        for i, s in enumerate(r['shots']):
            im = Image.open(os.path.join(out, s['file'])).convert('RGB').resize((TW, TH), Image.LANCZOS)
            sheet.paste(im, (i * TW, j * TH))
            d.text((i * TW + 6, j * TH + 4), f"{r['tod']} / {s['name']}", fill=(255, 255, 255))
    sheet.save(os.path.join(out, 'sheets', course + '.webp'), quality=82)
    print('sheet', course, sheet.size)
`;
  console.log(execFileSync('python3', ['-c', py, OUT], { encoding: 'utf8' }));
  console.log(`saved to ${OUT}`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
