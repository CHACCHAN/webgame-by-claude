import { useEffect, useState } from 'react';

/** A phone or tablet: the primary pointer is a finger (a laptop with a touch screen keeps its mouse layout). */
export function isTouchDevice() {
  if (typeof window === 'undefined') return false;
  return !!window.matchMedia?.('(pointer: coarse)').matches;
}

/** Touch layout on: from the start on touch devices, or from the first touch (a laptop's touch screen). */
export function useTouch() {
  const [touch, setTouch] = useState(isTouchDevice);
  useEffect(() => {
    if (touch) return;
    const on = () => setTouch(true);
    window.addEventListener('touchstart', on, { once: true, passive: true });
    return () => window.removeEventListener('touchstart', on);
  }, [touch]);
  return touch;
}

/** Phones: fullscreen and landscape where the browser allows it (Android; iOS ignores both). */
export function enterFullscreenLandscape() {
  const el = document.documentElement as HTMLElement & { webkitRequestFullscreen?: () => void };
  const lock = () => (screen.orientation as ScreenOrientation & { lock?: (o: string) => Promise<void> })?.lock?.('landscape').catch(() => {});
  try {
    const p = el.requestFullscreen?.({ navigationUI: 'hide' }) ?? el.webkitRequestFullscreen?.();
    if (p && 'then' in p) void p.then(lock).catch(() => {});
    else lock();
  } catch {
    /* not allowed here */
  }
}
