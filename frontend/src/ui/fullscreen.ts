import { useEffect, useState } from 'react';
import { isTouchDevice } from './touch';

type FsDocument = Document & { webkitFullscreenEnabled?: boolean; webkitFullscreenElement?: Element | null; webkitExitFullscreen?: () => void };
type FsElement = HTMLElement & { webkitRequestFullscreen?: () => void };

/** The browser can show the page fullscreen (iPhone Safari cannot). */
export function fullscreenSupported() {
  const d = document as FsDocument;
  return !!(d.fullscreenEnabled || d.webkitFullscreenEnabled);
}

export function isFullscreen() {
  const d = document as FsDocument;
  return !!(d.fullscreenElement || d.webkitFullscreenElement);
}

/** Fullscreen; on phones also landscape where the browser allows it (Android). Must run in a user gesture. */
export function enterFullscreen() {
  const el = document.documentElement as FsElement;
  const lock = () => {
    if (isTouchDevice()) (screen.orientation as ScreenOrientation & { lock?: (o: string) => Promise<void> })?.lock?.('landscape').catch(() => {});
  };
  try {
    const p = el.requestFullscreen?.({ navigationUI: 'hide' }) ?? el.webkitRequestFullscreen?.();
    if (p && 'then' in p) void p.then(lock).catch(() => {});
    else lock();
  } catch {
    /* not allowed here */
  }
}

export function toggleFullscreen() {
  if (!isFullscreen()) return enterFullscreen();
  const d = document as FsDocument;
  void (d.exitFullscreen?.() ?? d.webkitExitFullscreen?.());
}

/** Whether the page is fullscreen now (also after leaving it with Esc or the system back gesture). */
export function useFullscreen() {
  const [on, setOn] = useState(isFullscreen);
  useEffect(() => {
    const update = () => setOn(isFullscreen());
    document.addEventListener('fullscreenchange', update);
    document.addEventListener('webkitfullscreenchange', update);
    return () => {
      document.removeEventListener('fullscreenchange', update);
      document.removeEventListener('webkitfullscreenchange', update);
    };
  }, []);
  return on;
}
