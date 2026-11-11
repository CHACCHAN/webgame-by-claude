import { useLayoutEffect, useRef, type ReactNode } from 'react';
import { useCount, useCountText, useTyped } from './motion';

/**
 * The parts every screen is built from: the heading, the hint bar (what the keys do, in the glyphs of the device
 * used last), the focus marker that moves between the items of a list, notices, numbers that count up.
 */

/** What a hint stands for: the bar prints its keys or its pad buttons. */
export type HintKey = 'ud' | 'lr' | 'all' | 'ok' | 'tab' | 'sort' | 'fav' | 'color' | 'drag' | 'net';
const GLYPHS: Record<HintKey, { key: string[]; pad: string[] | null }> = {
  ud: { key: ['↑', '↓'], pad: ['✚ ↕'] },
  lr: { key: ['←', '→'], pad: ['✚ ↔'] },
  all: { key: ['←↑↓→'], pad: ['✚'] },
  ok: { key: ['Enter'], pad: ['A'] },
  tab: { key: ['Q', 'E'], pad: ['LB', 'RB'] },
  sort: { key: ['R'], pad: ['Back'] },
  fav: { key: ['X'], pad: ['X'] },
  color: { key: ['C'], pad: ['Y'] },
  // (the pointer only)
  drag: { key: ['ドラッグ'], pad: null },
  net: { key: ['N'], pad: null },
};

/** A pad button as the hint bar draws it: round for the face buttons, a lozenge for the others. */
export function PadKey({ name }: { name: string }) {
  return <kbd className={`k-pad pad${name.length > 1 ? ' wide' : ''}`}>{name}</kbd>;
}

/** The hint bar: bottom right on every menu screen (the back button stands bottom left, from App). */
export function Hint({ items }: { items: [HintKey, string][] }) {
  return (
    <div className="hint-bar">
      {items.map(([k, label]) => {
        const g = GLYPHS[k];
        return (
          <span key={k} className={g.pad ? '' : 'hint-mouse'}>
            {g.key.map((c) => <kbd key={c} className="k-key">{c}</kbd>)}
            {g.pad?.map((c) => <PadKey key={c} name={c} />)}
            {label}
          </span>
        );
      })}
    </div>
  );
}

/** A screen's heading under the top bar: what is being chosen here. */
export function ScreenHead({ jp, en, note }: { jp: string; en: string; note?: ReactNode }) {
  return (
    <div className="screen-head">
      <h2>{jp}</h2>
      <span className="sh-en">{en}</span>
      {note && <span className="sh-note">{note}</span>}
    </div>
  );
}

/**
 * The focus marker of a list or a row of cards: one element that moves to the selected item (`on`: its selector
 * inside the marker's parent, which must be positioned) instead of each item lighting up by itself. Placed from the
 * layout (offsets, not the drawn boxes: the items may be sliding in).
 */
export function FocusFrame({ on, deps, kind = '', pad = 0 }: { on: string; deps: unknown[]; kind?: string; pad?: number }) {
  const ref = useRef<HTMLElement>(null);
  useLayoutEffect(() => {
    const el = ref.current, box = el?.parentElement;
    if (!el || !box) return;
    const place = () => {
      const t = box.querySelector<HTMLElement>(on);
      if (!t) {
        el.style.opacity = '0';
        return;
      }
      let x = 0, y = 0;
      for (let n: HTMLElement | null = t; n && n !== box; n = n.offsetParent as HTMLElement | null) {
        x += n.offsetLeft;
        y += n.offsetTop;
      }
      el.style.width = `${t.offsetWidth + pad * 2}px`;
      el.style.height = `${t.offsetHeight + pad * 2}px`;
      el.style.transform = `translate(${x - pad}px, ${y - pad}px)`;
      el.style.opacity = '1';
    };
    place();
    // from the second placement on it travels
    const live = requestAnimationFrame(() => el.classList.add('live'));
    const watch = new ResizeObserver(place);
    watch.observe(box);
    return () => {
      cancelAnimationFrame(live);
      watch.disconnect();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return <i ref={ref} className={`focus-frame ${kind}`} aria-hidden />;
}

/** An error or an offline state: what happened, and what the player can still do. */
export function Notice({ title, children, kind = 'error', className = '', action }: { title?: string; children?: ReactNode; kind?: 'error' | 'info'; className?: string; action?: ReactNode }) {
  return (
    <div className={`notice ${kind === 'info' ? 'info' : ''} ${className}`} role={kind === 'error' ? 'alert' : 'status'}>
      <div>
        {title && <b>{title}</b>}
        {children}
      </div>
      {action}
    </div>
  );
}

/** A figure that counts to its value when it appears, and on from there when it changes (motion.ts `useCount`). */
export function Count({ to, format = (v) => String(Math.round(v)), ms, delay, from, tick, className, as: Tag = 'b' }: { to: number; format?: (v: number) => string; ms?: number; delay?: number; from?: number; tick?: boolean; className?: string; as?: 'b' | 'span' | 'div' }) {
  const ref = useCount<HTMLElement>(to, format, { ms, delay, from, tick });
  // (one ref type for the three tags)
  const R = Tag as 'b';
  return <R ref={ref} className={className}>{format(to)}</R>;
}

/** A figure given as text with its unit: its number counts on to the new value when the text changes. */
export function CountText({ text, className }: { text: string; className?: string }) {
  const ref = useCountText<HTMLElement>(text);
  return <b ref={ref} className={className}>{text}</b>;
}

/** Text typed out as a transmission (motion.ts `useTyped`). */
export function Typed({ text, wrap, delay, cps, className }: { text: string; wrap?: [string, string]; delay?: number; cps?: number; className?: string }) {
  const ref = useTyped<HTMLSpanElement>(text, { wrap, delay, cps });
  return <span ref={ref} className={className} aria-label={(wrap?.[0] ?? '') + text + (wrap?.[1] ?? '')}>{(wrap?.[0] ?? '') + text + (wrap?.[1] ?? '')}</span>;
}
