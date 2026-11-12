// The film of a run that the course select shows (ui/screens/Menus.tsx `CourseRun`): a whole run on a course by the
// game's own AI driver (chase view, no HUD), recorded frame by frame on the host GPU. The game is stepped by hand
// (1/60 s, two steps a picture = 30 pictures a second of game time), so the film does not depend on how fast this
// machine draws. Writes <OUT>/<course>/f00000.jpg … and track.json (per picture: the share of the course covered,
// km/h); `tools/course-clip-encode.sh` makes the film, its still and its track from them.
//   URL=http://127.0.0.1:4173/ OUT=<frames dir> COURSE=oboro-downhill [TOD=night] [CAR=hayate] [QUALITY=ultra]
//     [W=960 H=540 DPR=1.5] [MAX=frames] node tools/course-clip.cjs
// Needs the GPU (as tools/perf-frame.cjs: Chrome, PW_MODULE) and a `vite preview` with the API cut off. The films
// in the game: oboro-downhill night, kirifuri-lakeside dawn, tenrou-skyline night, autobahn dawn, all in the hayate.
// After a change of a course's design or of the look of the game: record and encode again.
const fs = require('fs');
const path = require('path');
const { chromium } = require(process.env.PW_MODULE || 'playwright');
const COURSE = process.env.COURSE || 'oboro-downhill', CAR = process.env.CAR || 'hayate', TOD = process.env.TOD || 'night';
const W = +(process.env.W || 854), H = +(process.env.H || 480), DPR = +(process.env.DPR || 2), MAX = +(process.env.MAX || 9000);
const OUT = path.join(process.env.OUT, COURSE);
(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({ executablePath: '/usr/bin/google-chrome', headless: true, args: ['--ignore-gpu-blocklist', '--use-angle=vulkan', '--enable-features=Vulkan'] });
  const ctx = await browser.newContext({ viewport: { width: W, height: H }, deviceScaleFactor: DPR });
  await ctx.route('**/api/**', (r) => r.abort());
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message.slice(0, 200)));
  const settings = { quality: process.env.QUALITY || 'ultra', resolutionScale: 1, timeOfDay: TOD, courseId: COURSE, masterVolume: 0, sfxVolume: 0, musicVolume: 0, assist: 1, autoShift: true, showGhost: false, cornerGuide: false, controlsGuide: false, showFps: false };
  await page.addInitScript((s) => localStorage.setItem('touge-settings', JSON.stringify({ state: s, version: 1 })), settings);
  await page.goto(process.env.URL);
  await page.waitForFunction(() => window.__game && window.__game.phase === 'attract', null, { timeout: 240000 });
  await page.addStyleTag({ content: '.overlay, .hud, .touch-controls, .grains { display: none !important; }' });
  await page.evaluate(([car]) => {
    const g = window.__game;
    g.startRace({ mode: 'time_attack', carId: car });
    g.countdownT = 0.01;
    g.chase.mode = 'chase';
  }, [CAR]);
  await page.waitForFunction(() => window.__game.phase === 'racing', null, { timeout: 60000 });
  await page.evaluate(() => {
    const g = window.__game;
    const step = Object.getPrototypeOf(g).update.bind(g);
    g.update = () => {};
    g.setPaused(false);
    g.autoDrive = true;
    const loop = g.renderer.getAnimationLoop();
    g.renderer.setAnimationLoop(null);
    window.__film = () => new Promise((res) => {
      step(1 / 60);
      step(1 / 60);
      g.renderer.setAnimationLoop((ms) => {
        loop(ms);
        g.renderer.setAnimationLoop(null);
        const t = g.track, s = g.player.proj.s;
        res({ u: (s - t.startS) / (t.finishS - t.startS), v: Math.abs(g.player.sim.forwardSpeed) * 3.6, phase: g.phase });
      });
    });
  });
  const track = [];
  const t0 = Date.now();
  let after = 0;
  for (let i = 0; i < MAX; i++) {
    const f = await page.evaluate(() => window.__film());
    await page.screenshot({ path: path.join(OUT, `f${String(i).padStart(5, '0')}.jpg`), type: 'jpeg', quality: 93 });
    track.push([+Math.max(0, Math.min(1, f.u)).toFixed(4), Math.round(f.v)]);
    if (i % 300 === 0) console.log(COURSE, 'frame', i, 'u', f.u.toFixed(3), Math.round(f.v), 'km/h', f.phase, ((Date.now() - t0) / 1000).toFixed(0), 's');
    // (a second past the line, then the film ends)
    if (f.phase !== 'racing' && ++after >= 30) break;
  }
  fs.writeFileSync(path.join(OUT, 'track.json'), JSON.stringify({ course: COURSE, car: CAR, fps: 30, frames: track.length, track }));
  console.log(COURSE, 'frames', track.length, 'in', ((Date.now() - t0) / 1000).toFixed(0), 's', 'errors', JSON.stringify(errors));
  await browser.close();
})();
