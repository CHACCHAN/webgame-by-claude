import type { DeskFacts } from '../../api/client';
import { useApp } from '../../store/app';
import { currentCourseId, useSettings } from '../../store/settings';
import { APP_VERSION } from '../../version';
import { renderHost } from '../GameCanvas';
import { isTouchDevice } from '../touch';

/**
 * What this machine says about itself: shown on the About screen's 技術 section, and sent along with a question or
 * a report to the desk. Short enums and whole numbers only (the server keeps nothing else): no free text, nothing
 * that names the player.
 */

/** The graphics adapter as the renderer's own API names it (null when it does not say). */
export function gpuName(): string | null {
  const host = renderHost();
  if (!host) return null;
  let name = '';
  try {
    const device = host.gpuDevice as { adapterInfo?: { vendor?: string; architecture?: string; device?: string; description?: string } } | null;
    if (device) {
      const info = device.adapterInfo;
      name = info?.description || [info?.vendor, info?.architecture].filter(Boolean).join(' ');
    } else {
      const gl = (host.renderer.backend as { gl?: WebGL2RenderingContext }).gl;
      const ext = gl?.getExtension('WEBGL_debug_renderer_info');
      name = gl && ext ? String(gl.getParameter(ext.UNMASKED_RENDERER_WEBGL)) : '';
    }
  } catch {
    name = '';
  }
  // (the characters such names are made of: the server takes no others)
  name = name.replace(/[^A-Za-z0-9 ()[\]/.,:_+-]+/g, ' ').replace(/ {2,}/g, ' ').trim().slice(0, 96);
  return name || null;
}

export function deskFacts(): DeskFacts {
  const app = useApp.getState();
  const s = useSettings.getState();
  const host = renderHost();
  const pad = Array.from(navigator.getGamepads?.() ?? []).some((p) => p && p.connected);
  return {
    version: APP_VERSION,
    course: currentCourseId(),
    vehicle: app.carId,
    tod: s.timeOfDay,
    mode: app.mode,
    quality: s.quality,
    backend: app.renderer?.backend,
    software: host ? host.software : undefined,
    upscale: s.upscale,
    upscale_mode: s.upscaleMode,
    scale: Math.round(s.resolutionScale * 100),
    w: Math.round(window.innerWidth),
    h: Math.round(window.innerHeight),
    dpr: Math.round((window.devicePixelRatio || 1) * 100),
    touch: isTouchDevice(),
    pad,
    gpu: gpuName() ?? undefined,
    lang: navigator.language || undefined,
  };
}
