/**
 * Which backend the renderer starts with, and what is remembered about WebGPU failing on this machine.
 *
 * WebGPU is tried first. The WebGL 2 backend takes over
 *  - at once, inside three.js, where the browser has no WebGPU (no `navigator.gpu`, no adapter, no device);
 *  - on a fresh canvas when WebGPU came up but the renderer could not be built on it (`ui/GameCanvas.tsx`);
 *  - after one reload when the running WebGPU device is lost twice in a session, or throws errors in a burst
 *    (drivers that accept the device and then refuse what is drawn): `noteDeviceLost` / `ErrorBurst`.
 * A burst and a failed build are remembered for `RETRY_AFTER` (a browser or driver update may have fixed it);
 * a lost device only for the session (a crashed GPU process is back after the reload).
 * The setting 描画方式 overrides: `webgl2` never tries WebGPU, `webgpu` ignores what is remembered.
 */
export type BackendPref = 'auto' | 'webgpu' | 'webgl2';

/** why the WebGL 2 backend runs: asked for in the address, chosen in the settings, WebGPU missing, or it failed */
export type FallbackReason = 'query' | 'setting' | 'unsupported' | 'failed';

export interface BackendPlan {
  forceWebGL: boolean;
  /** set when `forceWebGL` */
  reason: FallbackReason | null;
}

interface Store {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

const LASTING_KEY = 'touge-backend-fallback';
const SESSION_KEY = 'touge-backend-lost';
export const RETRY_AFTER = 7 * 24 * 3600 * 1000;
/** a device lost again this soon after the reload it caused is not answered with another reload */
const RELOAD_GAP = 60 * 1000;

const stores = (): { lasting: Store | null; session: Store | null } => {
  const take = (get: () => Store) => {
    try {
      return get();
    } catch {
      return null; // storage blocked
    }
  };
  return { lasting: take(() => localStorage), session: take(() => sessionStorage) };
};

const read = <T>(store: Store | null, key: string): T | null => {
  try {
    const raw = store?.getItem(key);
    return raw ? (JSON.parse(raw) as T) : null;
  } catch {
    return null;
  }
};

const write = (store: Store | null, key: string, value: unknown) => {
  try {
    store?.setItem(key, JSON.stringify(value));
  } catch {
    // storage full or blocked: the fallback then lasts for this page only
  }
};

/** What to start the renderer with. `search` is the address' query (`?webgl=1` forces WebGL 2). */
export function planBackend(pref: BackendPref, search: string, now = Date.now(), s = stores()): BackendPlan {
  if (new URLSearchParams(search).get('webgl') === '1') return { forceWebGL: true, reason: 'query' };
  if (pref === 'webgl2') return { forceWebGL: true, reason: 'setting' };
  if (pref === 'webgpu') return { forceWebGL: false, reason: null };
  const lasting = read<{ at: number }>(s.lasting, LASTING_KEY);
  if (lasting && now - lasting.at < RETRY_AFTER) return { forceWebGL: true, reason: 'failed' };
  const lost = read<{ count: number }>(s.session, SESSION_KEY);
  if (lost && lost.count >= 2) return { forceWebGL: true, reason: 'failed' };
  return { forceWebGL: false, reason: null };
}

/** WebGPU failed in a way that will repeat (the renderer could not be built, errors in a burst). */
export function rememberFailure(what: string, now = Date.now(), s = stores()) {
  write(s.lasting, LASTING_KEY, { at: now, what: what.slice(0, 200) });
}

/** The player chose a backend by hand: what was remembered no longer counts. */
export function forgetFailures(s = stores()) {
  try {
    s.lasting?.removeItem(LASTING_KEY);
    s.session?.removeItem(SESSION_KEY);
  } catch {
    // nothing to forget
  }
}

/**
 * The running device (WebGPU) or context (WebGL 2) is gone: nothing is drawn any more. Returns whether to reload
 * the page (once; not when the last reload for this was moments ago: the page then says so instead of looping).
 */
export function noteDeviceLost(now = Date.now(), s = stores()): boolean {
  const was = read<{ count: number; at: number }>(s.session, SESSION_KEY);
  write(s.session, SESSION_KEY, { count: (was?.count ?? 0) + 1, at: now });
  // (no session storage: a reload could not be told from the first visit, so none is made)
  return !!s.session && !(was && now - was.at < RELOAD_GAP && was.count >= 2);
}

/**
 * Counts the device's uncaptured errors: `BURST` of them within `WINDOW` seconds means the picture is broken
 * (every one is a draw or a pass the GPU refused), not a stray warning.
 */
export class ErrorBurst {
  static readonly BURST = 12;
  static readonly WINDOW = 10;
  private times: number[] = [];
  private fired = false;

  /** `t`: seconds on any clock. True once, when the burst is reached. */
  add(t: number): boolean {
    if (this.fired) return false;
    this.times.push(t);
    while (this.times.length && t - this.times[0] > ErrorBurst.WINDOW) this.times.shift();
    if (this.times.length < ErrorBurst.BURST) return false;
    this.fired = true;
    return true;
  }
}
