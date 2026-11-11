import { useEffect, useRef, type RefObject } from 'react';
import { useSettings } from '../store/settings';
import { useApp, type Screen } from '../store/app';
import { sfx } from './sfx';

/**
 * The interface's motion that CSS alone cannot do: the wipe between two screens, numbers that count to their
 * figure, text typed out. Everything here writes to the DOM directly (no React state per frame) and gives way to a
 * plain cut when motion is reduced (the settings' UI アニメーション, or the system's `prefers-reduced-motion`).
 */
export function motionOn() {
  if (useSettings.getState().uiMotion === false) return false;
  return !window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
}

/** How deep in the menus a screen is: a change to a deeper one wipes left to right, back the other way. */
const DEPTH: Record<Screen, number> = {
  boot: 0, title: 1, modes: 2, courses: 3, loading: 3.5, conditions: 4, leaderboard: 4.5, garage: 5, transmission: 6, rivals: 7,
  cars: 3, settings: 3, controls: 3, online: 3, onlineRoom: 4, race: 8, results: 9, replay: 10, onlineResults: 9,
};

const WIPE_MS = 240;
const WIPE_EASE = 'cubic-bezier(0.7, 0, 0.3, 1)';

/**
 * Screen changes: React takes the old screen out of `.overlay` and puts the new one in at once (so the new screen
 * has the keys from the first frame). This watches that happen and animates around it: the node React removed is
 * kept on show for the length of the wipe, clipped away from one side while the new screen is uncovered from the
 * same side, a scan line running along the edge between them.
 *
 * The outgoing node lives in a closed shadow root meanwhile: nothing that looks for elements in the document (the
 * screens' own queries, the E2E tests' selectors) can find a screen that is no longer there. The shadow root gets
 * copies of the page's style sheets and of `.app`'s classes so the node looks the same in it.
 */
export function useScreenWipe(overlay: RefObject<HTMLElement | null>, host: RefObject<HTMLElement | null>, scan: RefObject<HTMLElement | null>) {
  useEffect(() => {
    const box = overlay.current, hostEl = host.current;
    if (!box || !hostEl) return;
    const root = hostEl.shadowRoot ?? hostEl.attachShadow({ mode: 'closed' });
    for (const n of document.querySelectorAll('style, link[rel="stylesheet"]')) root.appendChild(n.cloneNode(true));
    const app = document.createElement('div');
    const layer = document.createElement('div');
    layer.className = 'overlay wipe-layer';
    app.appendChild(layer);
    root.appendChild(app);

    // the direction of the change now happening, from the app's screen before and after
    let dir = 1;
    let last = useApp.getState().screen;
    const unsubscribe = useApp.subscribe((s) => {
      if (s.screen === last) return;
      dir = DEPTH[s.screen] >= DEPTH[last] ? 1 : -1;
      last = s.screen;
    });

    const isScreen = (n: Node): n is HTMLElement => n instanceof HTMLElement && n.classList.contains('screen');
    const plain = (n: HTMLElement) => n.dataset.wipe === 'none';
    const watch = new MutationObserver((records) => {
      const gone: HTMLElement[] = [], come: HTMLElement[] = [];
      for (const r of records) {
        r.removedNodes.forEach((n) => isScreen(n) && gone.push(n));
        r.addedNodes.forEach((n) => isScreen(n) && n.isConnected && come.push(n));
      }
      if (!gone.length && !come.length) return;
      if (!motionOn()) return;
      // a screen over another (the online car select) coming or going: forwards in, backwards out
      const d = gone.length && come.length ? dir : come.length ? 1 : -1;
      const hidden = d > 0 ? 'inset(0 0 0 100%)' : 'inset(0 100% 0 0)';
      const covered = d > 0 ? 'inset(0 100% 0 0)' : 'inset(0 0 0 100%)';
      const shown = 'inset(0 0 0 0)';
      let wiped = false;
      for (const n of gone) {
        app.className = box.parentElement?.className ?? '';
        n.inert = true;
        layer.appendChild(n);
        const keys = plain(n) ? [{ opacity: 1 }, { opacity: 0 }] : [{ clipPath: shown, opacity: 1 }, { clipPath: hidden, opacity: 0.5 }];
        wiped ||= !plain(n);
        const a = n.animate(keys, { duration: plain(n) ? 140 : WIPE_MS, easing: WIPE_EASE, fill: 'forwards' });
        const drop = () => n.remove();
        a.finished.then(drop, drop);
        // (a tab in the background runs no animation frames: never leave a dead screen lying around)
        setTimeout(drop, WIPE_MS + 400);
      }
      for (const n of come) {
        if (plain(n)) continue;
        wiped = true;
        n.animate([{ clipPath: covered }, { clipPath: shown }], { duration: WIPE_MS, easing: WIPE_EASE });
      }
      if (wiped && scan.current) {
        const w = box.clientWidth;
        scan.current.animate(
          [{ transform: `translateX(${d > 0 ? 0 : w}px)`, opacity: 1 }, { transform: `translateX(${d > 0 ? w : 0}px)`, opacity: 1, offset: 0.92 }, { transform: `translateX(${d > 0 ? w : 0}px)`, opacity: 0 }],
          { duration: WIPE_MS, easing: WIPE_EASE },
        );
        sfx.wipe();
      }
    });
    watch.observe(box, { childList: true });
    return () => {
      watch.disconnect();
      unsubscribe();
      root.replaceChildren();
    };
  }, [overlay, host, scan]);
}

const easeOut = (t: number) => 1 - Math.pow(1 - t, 3);

/**
 * A number that counts to its figure. The element's text is always the final value; while it counts, the running
 * value is drawn over it from `data-count` (base.css), so the layout never moves and a reader gets the real figure.
 * A later change of `to` counts on from the value shown.
 */
export function useCount<T extends HTMLElement>(to: number, format: (v: number) => string, opts: { ms?: number; delay?: number; from?: number; tick?: boolean } = {}) {
  const ref = useRef<T>(null);
  const shown = useRef<number | null>(null);
  const fmt = useRef(format);
  fmt.current = format;
  const { ms = 600, delay = 0, from = 0, tick = false } = opts;
  useEffect(() => {
    const el = ref.current;
    const start = shown.current ?? from;
    shown.current = to;
    if (!el || !motionOn() || !isFinite(to) || !isFinite(start) || start === to || ms <= 0) {
      if (el) delete el.dataset.count;
      return;
    }
    let raf = 0;
    let lastTick = 0;
    const t0 = performance.now() + delay;
    el.dataset.count = fmt.current(start);
    const step = (now: number) => {
      const t = Math.min(1, Math.max(0, (now - t0) / ms));
      const v = start + (to - start) * easeOut(t);
      shown.current = v;
      if (t >= 1) {
        delete el.dataset.count;
        shown.current = to;
        return;
      }
      const text = fmt.current(v);
      if (el.dataset.count !== text) el.dataset.count = text;
      if (tick && t > 0 && now - lastTick > 70) {
        lastTick = now;
        sfx.tick();
      }
      raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => {
      cancelAnimationFrame(raf);
      delete el.dataset.count;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [to, ms, delay]);
  return ref;
}

const NUMBER = /\d[\d,]*(?:\.\d+)?/;

/**
 * The same for a figure that comes as text with its unit ("4.7 秒", "1,040 kg"): the first number in it counts to
 * its value, written as the text writes it (decimals, thousands), the rest of the text stands.
 */
export function useCountText<T extends HTMLElement>(text: string, ms = 420) {
  const m = NUMBER.exec(text);
  const to = m ? Number(m[0].replace(/,/g, '')) : NaN;
  const decimals = m?.[0].split('.')[1]?.length ?? 0;
  const commas = !!m?.[0].includes(',');
  const format = (v: number) => {
    if (!m) return text;
    const n = commas ? v.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals }) : v.toFixed(decimals);
    return text.slice(0, m.index) + n + text.slice(m.index + m[0].length);
  };
  // (a text without a number, or the first figure shown, does not count: `from` is the value itself)
  return useCount<T>(to, format, { ms, from: to });
}

/**
 * Text typed out letter by letter into the element (a transmission coming in). The element's `aria-label` carries
 * the whole text from the start.
 */
export function useTyped<T extends HTMLElement>(text: string, opts: { cps?: number; delay?: number; wrap?: [string, string] } = {}) {
  const ref = useRef<T>(null);
  const { cps = 28, delay = 0, wrap = ['', ''] } = opts;
  const [open, close] = wrap;
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const whole = open + text + close;
    if (!motionOn()) {
      el.textContent = whole;
      return;
    }
    const chars = [...text];
    let raf = 0;
    let n = -1;
    const t0 = performance.now() + delay;
    el.textContent = open + close;
    const step = (now: number) => {
      const k = Math.min(chars.length, Math.max(0, Math.floor(((now - t0) / 1000) * cps)));
      if (k !== n) {
        n = k;
        el.textContent = open + chars.slice(0, k).join('') + close;
        if (k > 0 && k % 2 === 1) sfx.type();
      }
      if (k < chars.length) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => {
      cancelAnimationFrame(raf);
      el.textContent = whole;
    };
  }, [text, cps, delay, open, close]);
  return ref;
}
