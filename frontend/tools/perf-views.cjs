// Draw calls / triangles (and, with FPS=1 on a real GPU, frames per second) at 8 fixed views along each course,
// the same views for any build:  node tools/probe.cjs <quality> $PWD/tools/perf-views.cjs [w] [h]
// Env: COURSES=oboro-downhill,kirifuri-lakeside,tenrou-skyline  FPS=1 (3 s per view; meaningful with PW_GPU=1 only)
module.exports = async (page, { fps }) => {
  await page.evaluate(() => {
    const g = window.__game;
    window.__cam = null;
    const ov = g.updateVisuals.bind(g);
    g.updateVisuals = (dt) => {
      ov(dt);
      const c = window.__cam;
      if (!c) return;
      g.camera.position.set(...c.pos);
      g.camera.lookAt(...c.look);
      g.camera.updateMatrixWorld();
    };
    g.renderer.info.autoReset = false;
  });
  const frame = () => page.evaluate(() => new Promise((r) => requestAnimationFrame(() => r())));
  for (const course of (process.env.COURSES || 'oboro-downhill,kirifuri-lakeside,tenrou-skyline').split(',')) {
    await page.evaluate(async (c) => { const g = window.__game; if (g.course.id !== c) { await g.switchCourse(c); g.startAttract(); } }, course);
    const views = await page.evaluate(() => {
      const t = window.__game.track;
      const out = [];
      for (let k = 1; k <= 8; k++) {
        const s = (t.count * k) / 9;
        const a = t.pointAt(s, 0), b = t.pointAt(s + 40, 0);
        out.push({ s: Math.round(s), pos: [a.x, a.y + 2, a.z], look: [b.x, b.y + 1, b.z] });
      }
      return out;
    });
    let calls = 0, tris = 0;
    const rows = [];
    for (const v of views) {
      await page.evaluate((c) => (window.__cam = c), v);
      await frame();
      await frame();
      // the smallest of 3 samples (a sample sometimes spans two rendered frames)
      let info = null;
      for (let k = 0; k < 3; k++) {
        await page.evaluate(() => window.__game.renderer.info.reset());
        await frame();
        const x = await page.evaluate(() => ({ calls: window.__game.renderer.info.render.calls, tris: window.__game.renderer.info.render.triangles }));
        if (!info || x.tris < info.tris) info = x;
      }
      calls += info.calls;
      tris += info.tris;
      let f = '';
      if (process.env.FPS) f = '@' + (await fps()).toFixed(0) + 'fps';
      rows.push(`${v.s}:${info.calls}/${(info.tris / 1000).toFixed(0)}k${f}`);
    }
    const scene = await page.evaluate(() => { let meshes = 0, inst = 0; window.__game.scenery.group.traverse((o) => { if (o.isInstancedMesh) inst++; else if (o.isMesh) meshes++; }); return { meshes, inst }; });
    console.log(course, 'avg calls', (calls / views.length).toFixed(0), 'avg tris', (tris / views.length / 1000).toFixed(0) + 'k', 'scenery meshes', JSON.stringify(scene), rows.join(' '));
  }
};
