import { useEffect, useRef } from 'react';

export type MenuAction = 'up' | 'down' | 'left' | 'right' | 'confirm' | 'back' | 'prevTab' | 'nextTab' | 'optionX' | 'optionY' | 'optionSort';

/**
 * Keyboard + gamepad navigation for menus. The handler receives abstract
 * actions; gamepad D-pad/stick and A/B buttons are polled each frame.
 * Screens with tabs and extra functions (the car select) also get Q / E (LB / RB) as `prevTab` / `nextTab`,
 * X and C (the pad's X and Y) as `optionX` / `optionY`, and R (the pad's Back) as `optionSort`; the other screens
 * ignore them.
 */
export function useMenuInput(handler: (a: MenuAction) => void, enabled = true) {
  const ref = useRef(handler);
  ref.current = handler;
  useEffect(() => {
    if (!enabled) return;
    const onKey = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement)?.tagName === 'INPUT') {
        if (e.key === 'Escape') ref.current('back');
        return;
      }
      // (Ctrl+R, Ctrl+C … stay the browser's)
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      const map: Record<string, MenuAction> = {
        ArrowUp: 'up', KeyW: 'up', ArrowDown: 'down', KeyS: 'down', ArrowLeft: 'left', KeyA: 'left', ArrowRight: 'right', KeyD: 'right',
        Enter: 'confirm', Space: 'confirm', Escape: 'back', Backspace: 'back',
        KeyQ: 'prevTab', KeyE: 'nextTab', KeyX: 'optionX', KeyC: 'optionY', KeyR: 'optionSort',
      };
      const a = map[e.code];
      if (a) {
        e.preventDefault();
        ref.current(a);
      }
    };
    window.addEventListener('keydown', onKey);
    let raf = 0;
    let prev: Record<string, boolean> = {};
    let repeatT = 0;
    const poll = () => {
      const pad = Array.from(navigator.getGamepads?.() ?? []).find((p) => p && p.connected);
      if (pad) {
        const st: Record<string, boolean> = {
          up: !!pad.buttons[12]?.pressed || (pad.axes[1] ?? 0) < -0.6,
          down: !!pad.buttons[13]?.pressed || (pad.axes[1] ?? 0) > 0.6,
          left: !!pad.buttons[14]?.pressed || (pad.axes[0] ?? 0) < -0.6,
          right: !!pad.buttons[15]?.pressed || (pad.axes[0] ?? 0) > 0.6,
          confirm: !!pad.buttons[0]?.pressed || !!pad.buttons[9]?.pressed,
          back: !!pad.buttons[1]?.pressed,
          prevTab: !!pad.buttons[4]?.pressed,
          nextTab: !!pad.buttons[5]?.pressed,
          optionX: !!pad.buttons[2]?.pressed,
          optionY: !!pad.buttons[3]?.pressed,
          optionSort: !!pad.buttons[8]?.pressed,
        };
        const now = performance.now();
        for (const k of Object.keys(st)) {
          if (st[k] && (!prev[k] || (['up', 'down', 'left', 'right'].includes(k) && now - repeatT > 220))) {
            repeatT = now;
            ref.current(k as MenuAction);
          }
        }
        prev = st;
      }
      raf = requestAnimationFrame(poll);
    };
    raf = requestAnimationFrame(poll);
    return () => {
      window.removeEventListener('keydown', onKey);
      cancelAnimationFrame(raf);
    };
  }, [enabled]);
}

/**
 * Hover-to-select props. Browsers send synthetic mouse events when a new screen appears under a
 * resting cursor; those carry no movement and are ignored so they cannot override keyboard choices.
 */
export const hoverSelect = (select: () => void) => ({
  onMouseMove: (e: { movementX: number; movementY: number }) => {
    if (e.movementX !== 0 || e.movementY !== 0) select();
  },
});
