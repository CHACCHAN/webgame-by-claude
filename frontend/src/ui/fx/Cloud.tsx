import { useEffect, useRef } from 'react';
import { isTouchDevice } from '../touch';
import { COURSES, type CourseId } from '../../game/track/courses';
import { Track } from '../../game/track/Track';
import { bind, createCloud, resizeCloud, rng, stepCloud, type Cloud as Field, type Shape } from './cloud';
import { splat } from './fluid';
import { createCloudRenderer } from './cloudRender';
import { createCloudRendererGpu } from './cloudRenderGpu';
import { gameHolder, renderHost } from '../GameCanvas';
import { RELIEF_PITCH, RELIEF_SWAY, TONE, courseRelief, maskShape, medalShape } from './shapes';

/**
 * The grains of the menus. Owner 11-12: grains around every button and dust over the whole screen all the time
 * were too much ("しつこい"), a fluid-like motion would be beautiful, and the rest is ours to judge. So the grains do
 * one thing: **they are the picture of a thing, in the few places where a picture belongs**, and they hang in water.
 *
 * - An element with `data-cloud` is depicted by grains where it stands: `course:<id>` (the course's relief),
 *   `glyph` (the element's own text),
 *   `medal:gold|silver|bronze` (a medal, the element's text as its emblem). `data-cloud-fill="0…1"`: how much of
 *   it is there. A thing condenses when it is asked for and comes apart like ink when it is let go.
 *   `data-cloud-once="<ms>"`: an entrance only: after that long in grains the element gets `data-cloud-done` and
 *   its own picture takes over (the title's kanji: type is finer than grains can be at that size).
 * - The pointer stirs the water (./fluid.ts): a stroke through a picture carries its grains off, and they come home.
 * - Nothing else: no dust, nothing around buttons or the selection (the drawn `FocusFrame` marks that). A screen
 *   without a `data-cloud` has no grains, and then this costs nothing: no step, no draw.
 * While the grains depict something the app has the class `cloud-on` (the page's own picture of it steps back).
 * One canvas over the interface that takes no input; the simulation is ./cloud.ts, the shapes ./shapes.ts.
 * A slow machine gets fewer grains, down to none. Not mounted in a race, nor with the interface's motion off.
 */

const TOKENS: [number, string, number[]][] = [
  [TONE.dust, '', [176, 205, 225]],
  [TONE.cyan, '--c-cyan', [120, 235, 255]],
  [TONE.magenta, '--c-magenta', [255, 60, 150]],
  [TONE.amber, '--c-amber', [255, 190, 80]],
  [TONE.white, '', [255, 255, 255]],
  [TONE.green, '--c-green', [110, 255, 170]],
  [TONE.deep, '', [70, 120, 190]],
  [TONE.silver, '--c-silver', [205, 216, 230]],
  [TONE.bronze, '--c-bronze', [224, 142, 94]],
];

/** how many grains: a desktop, a phone (all of them are the picture) */
const MANY = 32000, FEW = 8000;
/** the time the grains may take in a frame, milliseconds (their own work on the main thread) */
const BUDGET = 3.5;
/** below this many grains they no longer depict things (too few to read): the page's own pictures stay */
const DEPICT = 4500;
/** a glyph's mask is this many em high (shapes are in units of their mask's height) */
const GLYPH_EM = 1.3;
/** how much of the pointer's speed the water takes */
const STIR = 0.45;

export function Cloud() {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current;
    const app = canvas?.parentElement;
    if (!canvas || !app) return;
    const n = isTouchDevice() ? FEW : MANY;
    // drawn with what the game is drawn with (its WebGPU device, or WebGL 2 next to its WebGL 2): never the other
    const host = renderHost();
    // (no GPU: no grains, and no second context next to the game's: on SwiftShader that one blanked the game's canvas)
    if (!host || host.software) return;
    const renderer = host.backend === 'webgpu' ? createCloudRendererGpu(canvas, n, host.gpuDevice) : createCloudRenderer(canvas, n);
    if (!renderer) return;
    const css = getComputedStyle(app);
    const palette = new Float32Array(TOKENS.length * 3);
    for (const [tone, token, fallback] of TOKENS) {
      const read = token ? css.getPropertyValue(token).trim().split(/[\s,]+/).map(Number).filter(Number.isFinite) : [];
      const rgb = read.length === 3 ? read : fallback;
      for (let k = 0; k < 3; k++) palette[tone * 3 + k] = rgb[k] / 255;
    }
    const c = createCloud(n, 1, 1, palette);
    // (a start with few grains: the count grows while the frames keep coming)
    c.active = Math.min(n, 12000);
    const rand = rng(7);

    let w = 0, h = 0, left = 0, top = 0, ratio = 1;
    const size = () => {
      const r = app.getBoundingClientRect();
      left = r.left;
      top = r.top;
      const nr = Math.min(window.devicePixelRatio || 1, 2);
      if (r.width === w && r.height === h && nr === ratio) return;
      w = r.width;
      h = r.height;
      ratio = nr;
      renderer.resize(w, h, ratio);
      resizeCloud(c, w, h);
    };
    size();
    const watch = new ResizeObserver(size);
    watch.observe(app);

    // --- the pointer: it stirs the water, and the pictures turn a little towards it
    let pointer = false, px = 0, py = 0, stirX = 0, stirY = 0, stirred = false;
    let leanX = 0, leanY = 0;
    const overlay = app.querySelector('.overlay') ?? app;
    const onMove = (e: PointerEvent) => {
      if (e.pointerType === 'touch') {
        pointer = false;
        return;
      }
      const x = e.clientX - left, y = e.clientY - top;
      if (!pointer) {
        stirX = x;
        stirY = y;
      }
      px = x;
      py = y;
      pointer = true;
      stirred = true;
    };
    const onLeave = () => (pointer = false);
    window.addEventListener('pointermove', onMove, { passive: true });
    document.addEventListener('pointerleave', onLeave);
    window.addEventListener('blur', onLeave);

    // --- the things the grains depict (built once each, when first asked for, between two frames)
    const things = new Map<string, Shape | 'making'>();
    let thing: { el: HTMLElement; key: string } | null = null;
    const make = (key: string, el: HTMLElement): Shape | null => {
      const [kind, arg] = key.split(':');
      if (kind === 'course' && arg in COURSES) {
        const info = COURSES[arg as CourseId];
        const t = new Track(info.design);
        return courseRelief({ count: t.count, pos: t.pos, startS: t.startS, finishS: t.finishS, base: (x, z) => info.landform.base(x, z), water: info.landform.waterLevel }, n, rng(arg.length * 977 + 3));
      }
      if (kind === 'glyph' || kind === 'medal') {
        // the element's own text in its own type, drawn into a mask
        const style = getComputedStyle(el);
        const text = el.dataset.cloudText ?? el.textContent ?? '';
        const px = 220;
        const mask = document.createElement('canvas');
        const ctx = mask.getContext('2d', { willReadFrequently: true });
        let alpha: Uint8Array | null = null;
        if (ctx && text) {
          const font = `${style.fontWeight} ${px}px ${style.fontFamily}`;
          ctx.font = font;
          mask.width = Math.ceil(ctx.measureText(text).width + px * 0.3);
          mask.height = Math.ceil(px * GLYPH_EM);
          ctx.font = font;
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';
          ctx.fillStyle = '#fff';
          ctx.fillText(text, mask.width / 2, mask.height / 2);
          const data = ctx.getImageData(0, 0, mask.width, mask.height).data;
          alpha = new Uint8Array(mask.width * mask.height);
          for (let i = 0; i < alpha.length; i++) alpha[i] = data[i * 4 + 3];
        }
        if (kind === 'medal') return arg === 'gold' || arg === 'silver' || arg === 'bronze' ? medalShape(arg, n, rng(arg.length * 53 + 11), alpha ? { alpha, w: mask.width, h: mask.height } : undefined) : null;
        return alpha ? maskShape(alpha, mask.width, mask.height, n, TONE.white, rand) : null;
      }
      return null;
    };
    const keyOf = (el: HTMLElement) => {
      const asked = el.dataset.cloud ?? '';
      if (asked === 'glyph') return `glyph:${el.dataset.cloudText ?? el.textContent ?? ''}`;
      if (asked.startsWith('medal:')) return `${asked}:${el.dataset.cloudText ?? el.textContent ?? ''}`;
      return asked;
    };
    const findThing = () => {
      thing = null;
      if (c.active < DEPICT) return;
      for (const el of overlay.querySelectorAll<HTMLElement>('[data-cloud]')) {
        const r = el.getBoundingClientRect();
        if (r.width < 8 || r.height < 8 || r.bottom < 0 || r.top > window.innerHeight || el.dataset.cloudDone !== undefined) continue;
        thing = { el, key: keyOf(el) };
        return;
      }
    };
    let fontsReady = false;
    void document.fonts?.ready.then(() => (fontsReady = true));

    // --- the frame loop
    let raf = 0;
    let before = performance.now();
    let look = 0, boundAt = 0;
    let frames = 0, spent = 0, gauge = before, resting = false;
    const stats = { cost: 0 };
    /** nothing on the canvas: once, then it is left alone */
    const clear = () => {
      const living = c.active;
      c.active = 0;
      renderer.draw(c, ratio, 0, 0);
      c.active = living;
    };
    const frame = (now: number) => {
      raf = requestAnimationFrame(frame);
      // a race under way with the menus still mounted (a tool that starts one through the game, not the screens):
      // the grains rest, they take nothing from a race (not so the replay: it goes on behind the results)
      const phase = gameHolder.game?.phase;
      if (phase === 'countdown' || phase === 'racing') {
        if (!resting) {
          resting = true;
          clear();
          app.classList.remove('cloud-on');
        }
        before = now;
        return;
      }
      const dt = Math.min((now - before) / 1000, 0.05);
      before = now;

      // what is to be depicted is looked up a few times a second; where it is, every frame
      if (now - look > 90) {
        look = now;
        findThing();
        const t: { el: HTMLElement; key: string } | null = thing;
        if (!t) bind(c, null);
        else {
          const made = things.get(t.key);
          if (made && made !== 'making') {
            if (c.shape !== made) boundAt = now;
            bind(c, made);
            // an entrance only: the grains have drawn it, the page's own picture takes over and they come apart
            const once = Number(t.el.dataset.cloudOnce);
            if (once > 0 && now - boundAt > once) t.el.dataset.cloudDone = '';
          } else if (!made && (fontsReady || !(t.key.startsWith('glyph') || t.key.startsWith('medal')))) {
            things.set(t.key, 'making');
            const { el, key } = t;
            setTimeout(() => {
              const shape = make(key, el);
              if (shape) things.set(key, shape);
            }, 0);
          }
        }
        app.classList.toggle('cloud-on', c.active >= DEPICT);
      }
      // nothing to show and nothing left of what was: no step, no draw
      if (!c.shape && c.live === 0) {
        if (!resting) {
          resting = true;
          clear();
          stats.cost = 0;
        }
        stirred = false;
        stirX = px;
        stirY = py;
        return;
      }
      resting = false;

      // as many grains as cost little: by the time the grains themselves take in a frame (the frame's own length
      // says nothing: a course being built or the scene behind the menus makes frames long, and the grains would
      // go for something they did not do). They are an ornament: never the reason for a slow menu.
      frames++;
      if (now - gauge > 700 && frames > 8) {
        const cost = spent / frames;
        stats.cost = cost;
        if (cost > BUDGET * 1.25) c.active = c.active > 3000 ? Math.max(3000, Math.floor((c.active * BUDGET) / cost)) : 0;
        else if (cost < BUDGET * 0.55 && c.active < n) c.active = Math.min(n, Math.ceil(Math.max(c.active, 3000) * 1.5));
        frames = spent = 0;
        gauge = now;
      }

      const shown = c.shape && thing ? (thing as { el: HTMLElement; key: string }) : null;
      if (shown) {
        if (!shown.el.isConnected) bind(c, null);
        else {
          const r = shown.el.getBoundingClientRect();
          const p = c.place;
          const fill = shown.el.dataset.cloudFill;
          p.fill = fill === undefined ? 1 : Math.max(0, Math.min(1, Number(fill)));
          p.x = r.left - left + r.width / 2;
          p.y = r.top - top + r.height / 2;
          if (shown.key.startsWith('course')) {
            // a relief lying across its place, tipped towards the eye: it sways (and follows the pointer) rather
            // than turns, so that it stays inside its place
            const box = c.shape?.box ?? [0, 0, 1, 0.5];
            p.scale = Math.min(r.width / Math.max(box[2], 0.2), r.height / Math.max(box[3], 0.1)) * 0.95 * Number(shown.el.dataset.cloudScale ?? 1);
            p.x -= box[0] * p.scale;
            p.y -= box[1] * p.scale;
            p.pitch = RELIEF_PITCH + Math.sin(c.time * 0.17) * 0.04;
            p.yaw = RELIEF_SWAY * (Math.sin(c.time * 0.23) * 0.45 + (pointer ? (px / w - 0.5) * 1.1 : 0));
            p.z = -10;
          } else if (shown.key.startsWith('medal')) {
            // a medal on its ribbon: it swings a little and turns to the pointer, and the gleam goes round it
            p.scale = r.height * Number(shown.el.dataset.cloudScale ?? 1);
            p.yaw = Math.sin(c.time * 0.7) * 0.42 + (pointer ? (px / w - 0.5) * 0.5 : 0);
            p.pitch = Math.sin(c.time * 0.45 + 1) * 0.08;
            p.z = 0;
          } else {
            // a glyph, as large as the element's own type (the mask is 1.3 em high: `make`), so that the type can
            // take over from it; it sways a little, enough to show that it is deep
            p.scale = (parseFloat(getComputedStyle(shown.el).fontSize) || r.height) * GLYPH_EM * Number(shown.el.dataset.cloudScale ?? 1);
            p.yaw = Math.sin(c.time * 0.31) * 0.1;
            p.pitch = Math.sin(c.time * 0.23 + 1) * 0.04;
            p.z = 0;
          }
        }
      }

      // a stroke of the pointer stirs the water where it went
      if (stirred && pointer && dt > 0) {
        splat(c.fluid, px, py, ((px - stirX) / dt) * STIR, ((py - stirY) / dt) * STIR, h * 0.05);
      }
      stirred = false;
      stirX = px;
      stirY = py;

      // the eye leans a little with the pointer: near and far grains part
      const lx = pointer ? (px / w - 0.5) * -0.05 : 0, ly = pointer ? (py / h - 0.5) * -0.05 : 0;
      leanX += (lx - leanX) * Math.min(1, dt * 3);
      leanY += (ly - leanY) * Math.min(1, dt * 3);
      const from = performance.now();
      stepCloud(c, dt);
      renderer.draw(c, ratio, leanX, leanY);
      spent += performance.now() - from;
    };
    raf = requestAnimationFrame(frame);
    // (for probes: the cloud itself)
    (window as unknown as { __cloud?: Field; __cloudStats?: { cost: number } }).__cloud = c;
    (window as unknown as { __cloudStats?: { cost: number } }).__cloudStats = stats;
    return () => {
      cancelAnimationFrame(raf);
      watch.disconnect();
      window.removeEventListener('pointermove', onMove);
      document.removeEventListener('pointerleave', onLeave);
      window.removeEventListener('blur', onLeave);
      app.classList.remove('cloud-on');
      renderer.dispose();
    };
  }, []);

  return <canvas ref={ref} className="grains" aria-hidden />;
}
