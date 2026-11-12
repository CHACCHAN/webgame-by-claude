import { useEffect, useRef } from 'react';
import { useApp, type Screen } from '../../store/app';
import { screenDepth } from '../motion';
import { isTouchDevice } from '../touch';
import { COURSES, type CourseId } from '../../game/track/courses';
import { Track } from '../../game/track/Track';
import { AMBIENT, EMPHASIS, OBJECT, bind, burst, createCloud, members, resizeCloud, rng, stepCloud, sweep, type Cloud as Field, type Shape } from './cloud';
import { createCloudRenderer } from './cloudRender';
import { createCloudRendererGpu } from './cloudRenderGpu';
import { gameHolder, renderHost } from '../GameCanvas';
import { RELIEF_PITCH, RELIEF_SWAY, TONE, courseRelief, lineOutline, maskShape, medalShape, panelOutline, ringOutline, shellOf, skyScene } from './shapes';

/**
 * The grains over the menus (owner 11-11: fine, close to 3D particles; grains alone depict things and grains alone
 * emphasise them; the part in charge of beauty). One WebGL canvas over the interface that takes no input; the
 * simulation is ./cloud.ts, the shapes ./shapes.ts.
 *
 * - Dust floats in a volume behind the screen while nothing asks for the grains.
 * - **Emphasis**: what the pointer is on (the nearest thing with `cursor: pointer`), else the screen's `FocusFrame`,
 *   else an element with `data-grains` (`"line"` / `"ring"` / its panel; `data-grains-tone="magenta|amber"`;
 *   `data-grains-first="<ms>"`: before all of these for its first moments), gets its edge drawn by grains.
 * - **Things**: an element with `data-cloud` is depicted by grains where it stands: `course:<id>` (the course's
 *   relief), `glyph` (the element's own text), `sky:night|rain|dawn` (a time of day and its weather as a scene),
 *   `medal:gold|silver|bronze` (a medal, the element's text as its emblem). `data-cloud-fill="0…1"`: how much of
 *   it has gathered.
 * While the grains depict something the app has the class `cloud-on` (the page's own picture of it steps back).
 * A slow machine gets fewer grains, down to none. Not mounted in a race, nor with the interface's motion off.
 */

type Kind = 'panel' | 'line' | 'ring';
interface Target {
  el: Element;
  kind: Kind;
  tone: number;
  pad: number;
  cut: number;
  box: [number, number, number, number];
}

/** the nearest thing under the pointer that can be clicked: the outermost element of the run with `cursor: pointer` */
function clickable(from: Element | null, limit: Element): Element | null {
  let found: Element | null = null;
  for (let el = from; el && el !== limit; el = el.parentElement) {
    if (getComputedStyle(el).cursor === 'pointer') found = el;
    else if (found) break;
  }
  return found;
}

const kindOf = (el: Element): Kind => {
  const asked = (el as HTMLElement).dataset?.grains;
  return asked === 'line' || asked === 'ring' ? asked : 'panel';
};

function describe(el: Element, kind: Kind, viewW: number, viewH: number): Target | null {
  const r = el.getBoundingClientRect();
  if (r.width < 8 || r.height < 4) return null;
  // (the title is one large button: no edge around the whole screen)
  if (r.width > viewW * 0.8 && r.height > viewH * 0.6) return null;
  const style = getComputedStyle(el);
  // (not yet on show: a part of the screen waiting for its turn to come in)
  if (Number(style.opacity) < 0.05) return null;
  const cut = parseFloat(style.getPropertyValue('--c')) || 8;
  const data = (el as HTMLElement).dataset;
  const magenta = el.classList.contains('magenta') || el.classList.contains('rival-card') || data?.grainsTone === 'magenta';
  return { el, kind, tone: magenta ? TONE.magenta : data?.grainsTone === 'amber' ? TONE.amber : TONE.cyan, pad: kind === 'panel' ? 4 : 3, cut: Math.min(cut, 24), box: [r.left, r.top, r.width, r.height] };
}

/** the outline of a target in its own corner's coordinates (the shape is placed at the element every frame) */
function outlineOf(t: Target): Float32Array {
  const [, , w, h] = t.box;
  if (t.kind === 'ring') return ringOutline(w / 2, h / 2, Math.max(w, h) / 2 + t.pad);
  if (t.kind === 'line') return lineOutline(0, h + t.pad, w);
  return panelOutline(0, 0, w, h, t.cut, t.pad);
}

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

/** how many grains: a desktop, a phone */
const MANY = 48000, FEW = 12000;
/** the time the grains may take in a frame, milliseconds (their own work on the main thread) */
const BUDGET = 4;
/** below this many living grains they no longer depict things (too few to read): the page's own pictures stay */
const DEPICT = 9000;

export function Cloud() {
  const ref = useRef<HTMLCanvasElement>(null);
  const field = useRef<Field | null>(null);

  // a change of screen sends the floating grains past the eye, the way the wipe goes
  const screen = useApp((s) => s.screen);
  const last = useRef<Screen>(screen);
  useEffect(() => {
    const c = field.current;
    const dir = Math.sign(screenDepth(screen) - screenDepth(last.current)) || 1;
    last.current = screen;
    if (c) sweep(c, dir);
  }, [screen]);

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
    field.current = c;
    // (a start with few grains: the count grows while the frames keep coming)
    c.active = Math.min(n, 14000);
    const rand = rng(7);

    let w = 0, h = 0, left = 0, top = 0, ratio = 1;
    const size = () => {
      const r = app.getBoundingClientRect();
      left = r.left;
      top = r.top;
      const nr = Math.min(window.devicePixelRatio || 1, 2);
      if (r.width === w && r.height === h && nr === ratio) return;
      const first = w === 0;
      w = r.width;
      h = r.height;
      ratio = nr;
      renderer.resize(w, h, ratio);
      if (first) {
        c.w = w;
        c.h = h;
        for (let i = 0; i < c.n; i++) {
          c.pos[i * 3] *= w;
          c.pos[i * 3 + 1] *= h;
        }
      } else resizeCloud(c, w, h);
    };
    size();
    const watch = new ResizeObserver(size);
    watch.observe(app);

    // --- the pointer, and what the grains mark
    let hover: Element | null = null;
    let target: Target | null = null;
    let focusBox = '';
    let moved = false;
    let leanX = 0, leanY = 0;
    const overlay = app.querySelector('.overlay') ?? app;
    const onMove = (e: PointerEvent) => {
      if (e.pointerType === 'touch') {
        c.px = NaN;
        hover = null;
        return;
      }
      c.px = e.clientX - left;
      c.py = e.clientY - top;
      moved = true;
      hover = clickable(e.target as Element | null, app);
    };
    const onDown = (e: PointerEvent) => {
      onMove(e);
      // a choice made: the edge flies apart (it gathers again around whatever is selected next)
      if (target) burst(c, EMPHASIS, 300);
    };
    const onLeave = () => {
      c.px = NaN;
      hover = null;
    };
    const onKey = (e: KeyboardEvent) => {
      hover = null;
      if ((e.code === 'Enter' || e.code === 'Space') && target) burst(c, EMPHASIS, 300);
    };
    window.addEventListener('pointermove', onMove, { passive: true });
    window.addEventListener('pointerdown', onDown, { passive: true });
    document.addEventListener('pointerleave', onLeave);
    window.addEventListener('blur', onLeave);
    window.addEventListener('keydown', onKey);

    const firsts = new WeakMap<Element, number>();
    const choose = (): Target | null => {
      if (hover && !hover.isConnected) hover = null;
      const first = overlay.querySelector<HTMLElement>('[data-grains-first]');
      if (first) {
        const t = describe(first, kindOf(first), w, h);
        if (t) {
          const now = performance.now();
          const since = firsts.get(first) ?? now;
          firsts.set(first, since);
          if (now - since < Number(first.dataset.grainsFirst)) return t;
        }
      }
      // the selection moved while the pointer stood still (keys, pad): it takes over
      const frame = [...overlay.querySelectorAll<HTMLElement>('.focus-frame')].find((f) => f.style.opacity === '1' && f.offsetParent !== null);
      const box = frame ? frame.style.transform + frame.style.width : '';
      if (box !== focusBox && !moved) hover = null;
      focusBox = box;
      moved = false;
      if (hover) {
        const t = describe(hover, kindOf(hover), w, h);
        if (t) return t;
      }
      if (frame) {
        const t = describe(frame, 'panel', w, h);
        if (t) {
          t.pad = 2;
          return t;
        }
      }
      const asked = overlay.querySelector<HTMLElement>('[data-grains]');
      if (asked) return describe(asked, kindOf(asked), w, h);
      return null;
    };
    const shellKey = (t: Target) => `${t.kind}:${Math.round(t.box[2])}:${Math.round(t.box[3])}:${t.cut}:${t.tone}`;
    let shellAt = '';

    // --- the things the grains depict (built once each, when first asked for, between two frames)
    const things = new Map<string, Shape | 'making'>();
    let thing: { el: HTMLElement; key: string } | null = null;
    const objects = members(c, OBJECT, n);
    const make = (key: string, el: HTMLElement): Shape | null => {
      const [kind, arg] = key.split(':');
      if (kind === 'course' && arg in COURSES) {
        const info = COURSES[arg as CourseId];
        const t = new Track(info.design);
        return courseRelief({ count: t.count, pos: t.pos, startS: t.startS, finishS: t.finishS, base: (x, z) => info.landform.base(x, z), water: info.landform.waterLevel }, objects, rng(arg.length * 977 + 3));
      }
      if (kind === 'sky' && (arg === 'night' || arg === 'rain' || arg === 'dawn')) {
        return skyScene(arg, Number(key.split(':')[2]) || 3, objects, rng(arg.length * 131 + 7));
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
          mask.height = Math.ceil(px * 1.3);
          ctx.font = font;
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';
          ctx.fillStyle = '#fff';
          ctx.fillText(text, mask.width / 2, mask.height / 2);
          const data = ctx.getImageData(0, 0, mask.width, mask.height).data;
          alpha = new Uint8Array(mask.width * mask.height);
          for (let i = 0; i < alpha.length; i++) alpha[i] = data[i * 4 + 3];
        }
        if (kind === 'medal') return arg === 'gold' || arg === 'silver' || arg === 'bronze' ? medalShape(arg, objects, rng(arg.length * 53 + 11), alpha ? { alpha, w: mask.width, h: mask.height } : undefined) : null;
        return alpha ? maskShape(alpha, mask.width, mask.height, objects, TONE.white, rand) : null;
      }
      return null;
    };
    const keyOf = (el: HTMLElement, r: DOMRect) => {
      const asked = el.dataset.cloud ?? '';
      if (asked === 'glyph') return `glyph:${el.dataset.cloudText ?? el.textContent ?? ''}`;
      if (asked.startsWith('medal:')) return `${asked}:${el.dataset.cloudText ?? el.textContent ?? ''}`;
      // (a sky is made for the shape of its place)
      return asked.startsWith('sky:') ? `${asked}:${(r.width / r.height).toFixed(1)}` : asked;
    };
    const findThing = () => {
      thing = null;
      if (c.active < DEPICT) return;
      for (const el of overlay.querySelectorAll<HTMLElement>('[data-cloud]')) {
        const r = el.getBoundingClientRect();
        if (r.width < 8 || r.height < 8 || r.bottom < 0 || r.top > window.innerHeight) continue;
        thing = { el, key: keyOf(el, r) };
        return;
      }
    };
    let fontsReady = false;
    void document.fonts?.ready.then(() => (fontsReady = true));

    // --- the frame loop
    let raf = 0;
    let before = performance.now();
    let look = 0;
    let frames = 0, spent = 0, gauge = before, resting = false;
    const stats = { cost: 0 };
    const frame = (now: number) => {
      raf = requestAnimationFrame(frame);
      // a race under way with the menus still mounted (a tool that starts one through the game, not the screens):
      // the grains rest, they take nothing from a race (not so the replay: it goes on behind the results)
      const phase = gameHolder.game?.phase;
      if (phase === 'countdown' || phase === 'racing') {
        if (!resting) {
          resting = true;
          const living = c.active;
          c.active = 0;
          renderer.draw(c, ratio, 0, 0);
          c.active = living;
          app.classList.remove('cloud-on');
        }
        before = now;
        return;
      }
      resting = false;
      const gap = now - before;
      const dt = Math.min(gap / 1000, 0.05);
      before = now;

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
      app.classList.toggle('cloud-on', c.active >= DEPICT);

      // what is selected and what is to be depicted is looked up a few times a second; where it is, every frame
      if (now - look > 90) {
        look = now;
        const next = c.active ? choose() : null;
        if (!next) bind(c, EMPHASIS, null);
        target = next;
        if (next) {
          const key = shellKey(next);
          if (key !== shellAt || !c.shapes[EMPHASIS]) {
            shellAt = key;
            bind(c, EMPHASIS, shellOf(outlineOf(next), members(c, EMPHASIS, n), next.tone, rand));
          }
        } else shellAt = '';

        findThing();
        const t: { el: HTMLElement; key: string } | null = thing;
        if (!t) bind(c, OBJECT, null);
        else {
          const made = things.get(t.key);
          if (made && made !== 'making') bind(c, OBJECT, made);
          else if (!made && (fontsReady || !(t.key.startsWith('glyph') || t.key.startsWith('medal')))) {
            things.set(t.key, 'making');
            const { el, key } = t;
            setTimeout(() => {
              const shape = make(key, el);
              if (shape) things.set(key, shape);
            }, 0);
          }
        }
      }
      if (target) {
        if (!target.el.isConnected) {
          bind(c, EMPHASIS, null);
          target = null;
        } else {
          const r = target.el.getBoundingClientRect();
          const p = c.places[EMPHASIS];
          p.x = r.left - left;
          p.y = r.top - top;
          target.box = [r.left, r.top, r.width, r.height];
        }
      }
      const shown = c.shapes[OBJECT] && thing ? (thing as { el: HTMLElement; key: string }) : null;
      if (shown) {
        if (!shown.el.isConnected) bind(c, OBJECT, null);
        else {
          const r = shown.el.getBoundingClientRect();
          const p = c.places[OBJECT];
          const fill = shown.el.dataset.cloudFill;
          p.fill = fill === undefined ? 1 : Math.max(0, Math.min(1, Number(fill)));
          p.x = r.left - left + r.width / 2;
          p.y = r.top - top + r.height / 2;
          if (shown.key.startsWith('course')) {
            // a relief lying across its place, tipped towards the eye: it sways (and follows the pointer) rather
            // than turns, so that it stays inside its place
            const box = c.shapes[OBJECT]?.box ?? [0, 0, 1, 0.5];
            p.scale = Math.min(r.width / Math.max(box[2], 0.2), r.height / Math.max(box[3], 0.1)) * 0.95 * Number(shown.el.dataset.cloudScale ?? 1);
            p.x -= box[0] * p.scale;
            p.y -= box[1] * p.scale;
            p.pitch = RELIEF_PITCH + Math.sin(c.time * 0.17) * 0.04;
            p.yaw = RELIEF_SWAY * (Math.sin(c.time * 0.23) * 0.45 + (Number.isFinite(c.px) ? (c.px / w - 0.5) * 1.1 : 0));
            p.z = -10;
          } else if (shown.key.startsWith('sky')) {
            // a small scene in its place: it turns a little with the pointer, enough to part the near from the far
            p.scale = r.height * Number(shown.el.dataset.cloudScale ?? 1);
            p.yaw = Math.sin(c.time * 0.21) * 0.1 + (Number.isFinite(c.px) ? (c.px / w - 0.5) * 0.3 : 0);
            p.pitch = Math.sin(c.time * 0.17 + 1) * 0.04;
            p.z = 0;
          } else if (shown.key.startsWith('medal')) {
            // a medal on its ribbon: it swings a little and turns to the pointer, and the gleam goes round it
            p.scale = r.height * Number(shown.el.dataset.cloudScale ?? 1);
            p.yaw = Math.sin(c.time * 0.7) * 0.42 + (Number.isFinite(c.px) ? (c.px / w - 0.5) * 0.5 : 0);
            p.pitch = Math.sin(c.time * 0.45 + 1) * 0.08;
            p.z = 0;
          } else {
            // a glyph: it sways a little, enough to show that it is deep
            p.scale = (parseFloat(getComputedStyle(shown.el).fontSize) || r.height) * Number(shown.el.dataset.cloudScale ?? 1);
            p.yaw = Math.sin(c.time * 0.31) * 0.22;
            p.pitch = Math.sin(c.time * 0.23 + 1) * 0.07;
            p.z = 0;
          }
        }
      }

      // the eye leans a little with the pointer: near and far grains part
      const lx = Number.isFinite(c.px) ? (c.px / w - 0.5) * -0.05 : 0, ly = Number.isFinite(c.py) ? (c.py / h - 0.5) * -0.05 : 0;
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
      window.removeEventListener('pointerdown', onDown);
      document.removeEventListener('pointerleave', onLeave);
      window.removeEventListener('blur', onLeave);
      window.removeEventListener('keydown', onKey);
      app.classList.remove('cloud-on');
      renderer.dispose();
      field.current = null;
    };
  }, []);

  return <canvas ref={ref} className="grains" aria-hidden />;
}

void AMBIENT;
