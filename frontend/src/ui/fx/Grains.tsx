import { useEffect, useRef } from 'react';
import { useApp, type Screen } from '../../store/app';
import { screenDepth } from '../motion';
import { isTouchDevice } from '../touch';
import { createGrains, lineOutline, moveShape, panelOutline, resizeGrains, ringOutline, setShape, stepGrains, sweep, type Grains as Field } from './grains';

/**
 * The grains over the menus (the simulation: ./grains.ts): dust in the light while nothing is pointed at; what is
 * pointed at or selected gets its frame from them. One canvas over the interface that takes no input.
 *
 * What they gather around, the first that exists:
 *  1. what the pointer is on: the nearest thing that can be clicked (`cursor: pointer`), unless it is the whole screen;
 *  2. the selection of the keys or the pad: the screen's focus frame (`FocusFrame`);
 *  3. an element that asks for it: `data-grains` (`"line"`: a line under it, `"ring"`: a circle, else its panel).
 * Whichever of pointer and keys moved last decides between 1 and 2.
 * Not mounted in a race, nor when the interface's motion is off (App.tsx).
 */

/** the outline of an element's box, by its kind */
type Kind = 'panel' | 'line' | 'ring';
interface Target {
  el: Element;
  kind: Kind;
  tone: number;
  /** how far outside the element's edge the frame runs */
  pad: number;
  cut: number;
  box: [number, number, number, number];
}

const TONES = ['--c-cyan', '--c-magenta', '--c-amber'];

function outline(t: Target, ox: number, oy: number): Float32Array {
  const [x, y, w, h] = t.box;
  if (t.kind === 'ring') return ringOutline(x - ox + w / 2, y - oy + h / 2, Math.max(w, h) / 2 + t.pad);
  if (t.kind === 'line') return lineOutline(x - ox, y - oy + h + t.pad, w);
  return panelOutline(x - ox, y - oy, w, h, t.cut, t.pad);
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

function describe(el: Element, kind: Kind, viewW: number, viewH: number): Target | null {
  const r = el.getBoundingClientRect();
  if (r.width < 8 || r.height < 4) return null;
  // (the title is one large button: no frame around the whole screen)
  if (r.width > viewW * 0.8 && r.height > viewH * 0.6) return null;
  const style = getComputedStyle(el);
  const cut = parseFloat(style.getPropertyValue('--c')) || 8;
  const magenta = el.classList.contains('magenta') || el.classList.contains('rival-card') || (el as HTMLElement).dataset?.grainsTone === 'magenta';
  const amber = (el as HTMLElement).dataset?.grainsTone === 'amber';
  return { el, kind, tone: magenta ? 1 : amber ? 2 : 0, pad: kind === 'panel' ? 5 : 3, cut: Math.min(cut, 24), box: [r.left, r.top, r.width, r.height] };
}

export function Grains() {
  const ref = useRef<HTMLCanvasElement>(null);
  const field = useRef<Field | null>(null);

  // a change of screen sweeps the floating grains the way the wipe goes
  const screen = useApp((s) => s.screen);
  const last = useRef<Screen>(screen);
  useEffect(() => {
    const g = field.current;
    const dir = Math.sign(screenDepth(screen) - screenDepth(last.current)) || 1;
    last.current = screen;
    if (g) sweep(g, dir * 520, -40);
  }, [screen]);

  useEffect(() => {
    const canvas = ref.current;
    const ctx = canvas?.getContext('2d');
    const app = canvas?.parentElement;
    if (!canvas || !ctx || !app) return;
    const touch = isTouchDevice();
    const g = createGrains(touch ? 150 : 420, 1, 1);
    field.current = g;
    let w = 0, h = 0, left = 0, top = 0, ratio = 1;
    const size = () => {
      const r = app.getBoundingClientRect();
      left = r.left;
      top = r.top;
      // (grains are a pixel or two: more than 1.5 device pixels per pixel only costs fill)
      ratio = Math.min(window.devicePixelRatio || 1, 1.5);
      if (r.width === w && r.height === h && canvas.width === Math.round(w * ratio)) return;
      const first = w === 0;
      w = r.width;
      h = r.height;
      canvas.width = Math.round(w * ratio);
      canvas.height = Math.round(h * ratio);
      if (first) {
        g.w = 1;
        g.h = 1;
      }
      resizeGrains(g, w, h);
    };
    size();
    const watch = new ResizeObserver(size);
    watch.observe(app);

    const css = getComputedStyle(app);
    const tones = TONES.map((name) => css.getPropertyValue(name).trim().split(/[\s,]+/).map(Number).filter(Number.isFinite));
    const rgb = (k: number) => (tones[k]?.length === 3 ? tones[k] : [120, 235, 255]).join(',');
    const toneCss = [0, 1, 2].map(rgb);

    // --- what the grains gather around
    let hover: Element | null = null;
    let target: Target | null = null;
    let focusBox = '';
    let moved = false;
    const overlay = app.querySelector('.overlay') ?? app;
    const onMove = (e: PointerEvent) => {
      if (e.pointerType === 'touch') {
        g.px = NaN;
        hover = null;
        return;
      }
      g.px = e.clientX - left;
      g.py = e.clientY - top;
      moved = true;
      hover = clickable(e.target as Element | null, app);
    };
    const onLeave = () => {
      g.px = NaN;
      hover = null;
    };
    const onKey = () => {
      hover = null;
    };
    window.addEventListener('pointermove', onMove, { passive: true });
    window.addEventListener('pointerdown', onMove, { passive: true });
    document.addEventListener('pointerleave', onLeave);
    window.addEventListener('blur', onLeave);
    window.addEventListener('keydown', onKey);

    const choose = (): Target | null => {
      if (hover && !hover.isConnected) hover = null;
      // the selection moved while the pointer stood still (keys, pad): it takes over
      const frame = [...overlay.querySelectorAll<HTMLElement>('.focus-frame')].find((f) => f.style.opacity === '1' && f.offsetParent !== null);
      const box = frame ? frame.style.transform + frame.style.width : '';
      if (box !== focusBox && !moved) hover = null;
      focusBox = box;
      moved = false;
      if (hover) {
        const t = describe(hover, (hover as HTMLElement).dataset?.grains === 'line' ? 'line' : (hover as HTMLElement).dataset?.grains === 'ring' ? 'ring' : 'panel', w, h);
        if (t) return t;
      }
      if (frame) {
        const t = describe(frame, 'panel', w, h);
        if (t) {
          t.pad = 3;
          return t;
        }
      }
      const asked = overlay.querySelector<HTMLElement>('[data-grains]');
      if (asked) return describe(asked, asked.dataset.grains === 'line' ? 'line' : asked.dataset.grains === 'ring' ? 'ring' : 'panel', w, h);
      return null;
    };

    // --- the frame loop
    let raf = 0;
    let before = performance.now();
    let look = 0;
    const frame = (now: number) => {
      raf = requestAnimationFrame(frame);
      const dt = Math.min((now - before) / 1000, 0.05);
      before = now;

      // what is selected is looked up a few times a second; where it is, every frame (it may be sliding)
      if (now - look > 90) {
        look = now;
        const next = choose();
        if (!next) {
          if (target) setShape(g, null);
        } else if (!target || target.el !== next.el || target.kind !== next.kind) {
          setShape(g, { points: outline(next, left, top), tone: next.tone });
        }
        target = next;
      }
      if (target) {
        if (!target.el.isConnected) {
          setShape(g, null);
          target = null;
        } else {
          const r = target.el.getBoundingClientRect();
          const b = target.box;
          if (Math.abs(r.left - b[0]) + Math.abs(r.top - b[1]) + Math.abs(r.width - b[2]) + Math.abs(r.height - b[3]) > 0.5) {
            target.box = [r.left, r.top, r.width, r.height];
            moveShape(g, outline(target, left, top));
          }
        }
      }

      stepGrains(g, dt);
      draw(ctx, g, ratio, toneCss);
    };
    raf = requestAnimationFrame(frame);
    return () => {
      cancelAnimationFrame(raf);
      watch.disconnect();
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerdown', onMove);
      document.removeEventListener('pointerleave', onLeave);
      window.removeEventListener('blur', onLeave);
      window.removeEventListener('keydown', onKey);
      field.current = null;
    };
  }, []);

  return <canvas ref={ref} className="grains" aria-hidden />;
}

/** the colour of the floating grains: the pale steel of the interface's lines */
const DUST = '176,205,225';
const STEPS = 5;

function draw(ctx: CanvasRenderingContext2D, g: Field, ratio: number, tones: string[]) {
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  ctx.globalCompositeOperation = 'source-over';
  ctx.clearRect(0, 0, g.w, g.h);
  ctx.globalCompositeOperation = 'lighter';
  const t = g.time;
  const tone = tones[g.shape?.tone ?? 0] ?? tones[0];

  // the frame itself condenses out of the grains: the outline as a thin line, as bright as they have arrived
  if (g.shape) {
    let sum = 0, seated = 0;
    for (let i = 0; i < g.n; i++) {
      if (g.seat[i] < 0) continue;
      sum += g.held[i];
      seated++;
    }
    const held = seated ? (sum / seated) ** 2 : 0;
    const p = g.shape.points;
    ctx.beginPath();
    ctx.moveTo(p[0], p[1]);
    for (let k = 2; k < p.length; k += 2) ctx.lineTo(p[k], p[k + 1]);
    ctx.closePath();
    ctx.strokeStyle = `rgba(${tone},${(0.5 * held).toFixed(3)})`;
    ctx.lineWidth = 1;
    ctx.stroke();
  }

  // the floating ones in a few steps of brightness (one fill each); the fast ones draw a short streak
  for (let s = 0; s < STEPS; s++) {
    ctx.fillStyle = `rgba(${DUST},${(0.16 + 0.66 * ((s + 0.5) / STEPS) ** 1.5).toFixed(3)})`;
    ctx.beginPath();
    for (let i = 0; i < g.n; i++) {
      if (g.held[i] > 0.6) continue;
      const depth = g.depth[i];
      const light = Math.max(0, Math.min(0.999, ((depth - 0.35) / 0.65) * (0.7 + 0.3 * Math.sin(t * 1.3 + g.phase[i] * 5)) * (1 - g.held[i])));
      if (Math.floor(light * STEPS) !== s) continue;
      const size = 1 + 2.1 * depth;
      ctx.rect(g.x[i] - size / 2, g.y[i] - size / 2, size, size);
    }
    ctx.fill();
  }
  ctx.beginPath();
  for (let i = 0; i < g.n; i++) {
    const v2 = g.vx[i] * g.vx[i] + g.vy[i] * g.vy[i];
    if (v2 < 90 * 90) continue;
    ctx.moveTo(g.x[i], g.y[i]);
    ctx.lineTo(g.x[i] - g.vx[i] * 0.045, g.y[i] - g.vy[i] * 0.045);
  }
  ctx.strokeStyle = `rgba(${DUST},0.3)`;
  ctx.lineWidth = 1;
  ctx.stroke();

  // the gathered ones in the selection's colour: those on the line bright with a glow, the loose dust around it dim
  for (let pass = 0; pass < 3; pass++) {
    ctx.beginPath();
    for (let i = 0; i < g.n; i++) {
      const held = g.held[i];
      if (held <= 0.02) continue;
      const loose = g.off[i] > 3;
      if (pass === 0 ? loose : pass === 1 ? !loose : loose || held < 0.3) continue;
      const free = 1 + 2.1 * g.depth[i];
      const size = pass === 2 ? 9 * held : free * (1 - held) + (loose ? 1.1 + 1.2 * g.depth[i] : 1.5 + 2.4 * g.depth[i]) * held;
      ctx.rect(g.x[i] - size / 2, g.y[i] - size / 2, size, size);
    }
    ctx.fillStyle = `rgba(${tone},${pass === 0 ? 0.95 : pass === 1 ? 0.5 : 0.07})`;
    ctx.fill();
  }
}
