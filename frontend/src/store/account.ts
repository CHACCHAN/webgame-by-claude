import { create } from 'zustand';
import {
  api,
  ApiError,
  asProgress,
  clearProgress,
  carryGuest,
  forgetLegacy,
  legacyToken,
  takeCarried,
  loadLocalBest,
  mergeProgress,
  onProgress,
  readProgress,
  saveLocalBest,
  writeProgress,
  type Progress,
  type StoredPlayer,
} from '../api/client';
import { useGarage } from './garage';
import type { CarId } from '../game/vehicle/carSpecs';

/**
 * Who plays. Members of the owner's platform log in through Authentik and are an account of the game: their
 * records and save data are theirs on any machine. Everyone else is a guest: nothing is kept that says who they
 * are, and a name is asked whenever a record is kept. (The server decides: `api.auth.me`.)
 */
interface AccountState {
  /** the answer to "who is this" has come (before it: no login button, nobody is asked for a name) */
  known: boolean;
  /** the server has a login at all (Authentik is set up); without it everyone is a guest */
  enabled: boolean;
  member: StoredPlayer | null;
  /** what the trip to Authentik came back with (for one message on the screen) */
  notice: 'ok' | 'failed' | 'denied' | 'off' | null;
  /** records of a guest (this sitting's, or the player this browser kept before) that became the member's at login */
  claimed: number;
}

export const useAccount = create<AccountState>(() => ({ known: false, enabled: false, member: null, notice: null, claimed: 0 }));

const NOTICES = ['ok', 'failed', 'denied', 'off'] as const;

/** At start: what a login came back with, who the server says we are, and a member's save data. */
export async function initAccount() {
  let notice: AccountState['notice'] = null;
  try {
    const url = new URL(location.href);
    const back = url.searchParams.get('login');
    if (back !== null) {
      notice = (NOTICES as readonly string[]).includes(back) ? (back as AccountState['notice']) : null;
      url.searchParams.delete('login');
      history.replaceState(history.state, '', url.pathname + url.search + url.hash);
    }
  } catch {
    /* no address to read (tests) */
  }
  // (a guest's token carried over the trip to Authentik: used once below, never kept)
  const carried = takeCarried();
  try {
    const me = await api.auth.me();
    // a guest starts with nothing: not even the stars a browser kept (they stay stored for a member to take along)
    if (!me.member) useGarage.setState({ favourites: [] });
    useAccount.setState({ known: true, enabled: me.enabled, member: me.member, notice });
    if (me.member) await memberArrived(carried);
  } catch {
    // no server: a guest
    useGarage.setState({ favourites: [] });
    useAccount.setState({ known: true, enabled: false, member: null, notice: notice === 'ok' ? 'failed' : notice });
  }
}

/** Off to Authentik; the game is loaded again when the browser comes back. */
export function login() {
  carryGuest();
  location.assign(api.auth.loginUrl(location.pathname));
}

export async function logout() {
  window.clearTimeout(pushTimer);
  // the member's progress is on the server: nothing of it stays on this machine (while still the member: a guest's
  // writes do not reach the machine's storage)
  clearProgress();
  writeBase(null);
  useGarage.setState({ favourites: [] });
  await api.auth.logout().catch(() => undefined);
  useAccount.setState({ member: null, notice: null, claimed: 0 });
}

export const dismissNotice = () => useAccount.setState({ notice: null });

// ---------------------------------------------------------------- a member's save data

/** the revision of the save this machine last read or wrote */
let rev = 0;
let pushTimer = 0;
let applying = false;

/** the favourites as last agreed with the server: what was starred or unstarred here since is this machine's change */
const BASE_KEY = 'touge-save-base';
const readBase = (id: number): string[] => {
  try {
    const b = JSON.parse(localStorage.getItem(BASE_KEY) ?? 'null') as { id: number; favourites: string[] } | null;
    return b && b.id === id && Array.isArray(b.favourites) ? b.favourites : [];
  } catch {
    return [];
  }
};
const writeBase = (b: { id: number; favourites: string[] } | null) => {
  try {
    if (b) localStorage.setItem(BASE_KEY, JSON.stringify(b));
    else localStorage.removeItem(BASE_KEY);
  } catch {
    /* storage unavailable */
  }
};

/** Favourites of two machines: the server's, plus what was starred here since the last exchange, minus what was unstarred here. */
export function mergeFavourites(local: string[], remote: string[], base: string[]): string[] {
  const added = local.filter((f) => !base.includes(f));
  const removed = base.filter((f) => !local.includes(f));
  return [...new Set([...remote, ...added])].filter((f) => !removed.includes(f));
}

const sorted = (v: unknown): unknown =>
  Array.isArray(v) ? v.map(sorted) : v && typeof v === 'object' ? Object.fromEntries(Object.entries(v).sort(([a], [b]) => (a < b ? -1 : 1)).map(([k, x]) => [k, sorted(x)])) : v;
const same = (a: Progress, b: Progress) => JSON.stringify(sorted(a)) === JSON.stringify(sorted(b));

const localProgress = () => readProgress(useGarage.getState().favourites);

function apply(p: Progress, id: number) {
  applying = true;
  writeProgress(p);
  useGarage.setState({ favourites: p.favourites as CarId[] });
  writeBase({ id, favourites: p.favourites });
  applying = false;
}

/** This machine's progress and the server's made one, on both sides. */
function reconcile(remote: Progress, id: number, extra?: Progress): Progress {
  const local = localProgress();
  let merged = mergeProgress(local, remote);
  if (extra) merged = mergeProgress(merged, extra);
  merged.favourites = mergeFavourites(local.favourites, remote.favourites, readBase(id));
  apply(merged, id);
  return merged;
}

async function push(p: Progress, id: number, retry = true): Promise<void> {
  try {
    rev = (await api.save.put(rev, p)).rev;
    writeBase({ id, favourites: p.favourites });
  } catch (e) {
    // written on another machine meanwhile: the server sends what it has; merge and send once more
    if (e instanceof ApiError && e.status === 409 && retry) {
      const now = e.details as { rev: number; save: unknown };
      rev = now.rev;
      const remote = asProgress(now.save);
      const merged = reconcile(remote, id);
      if (!same(merged, remote)) await push(merged, id, false);
    }
    // (anything else: the progress stays on this machine and goes with the next change or the next start)
  }
}

function schedulePush() {
  const member = useAccount.getState().member;
  if (!member || applying) return;
  window.clearTimeout(pushTimer);
  pushTimer = window.setTimeout(() => void push(localProgress(), member.id), 1500);
}

let listening = false;

/**
 * A member has arrived (at start, logged in): records set as a guest on this browser become theirs, the save data
 * of the server and the progress on this machine are made one, and the ghosts of their best runs are fetched.
 */
async function memberArrived(carried: string | null) {
  const member = useAccount.getState().member;
  if (!member) return;

  let claimed = 0;
  if (carried) claimed += await api.auth.claim(carried).then((r) => r.claimed, () => 0);
  const old = legacyToken();
  if (old) {
    try {
      claimed += (await api.auth.claim(old)).claimed;
      forgetLegacy();
    } catch {
      /* next start */
    }
  }
  if (claimed) useAccount.setState({ claimed });

  try {
    const [remote, profile] = await Promise.all([api.save.get(), api.profile(member)]);
    rev = remote.rev;
    // the times the server knows from the runs themselves (claimed records, runs from before the save existed)
    const fromRuns: Progress = { v: 1, carBests: {}, rivals: {}, favourites: [] };
    for (const b of profile.bests) (fromRuns.carBests[b.track_id] ??= {})[b.car_id] = b.best_ms;
    const saved = asProgress(remote.save);
    const merged = reconcile(saved, member.id, fromRuns);
    if (!same(merged, saved)) await push(merged, member.id);

    for (const run of profile.best_runs) {
      const mine = loadLocalBest(run.track_id);
      if (!run.has_ghost || (mine && mine.timeMs <= run.time_ms)) continue;
      const g = await api.ghost(run.run_id).catch(() => null);
      if (!g) continue;
      saveLocalBest(run.track_id, {
        carId: run.car_id,
        timeMs: run.time_ms,
        splits: run.sector_ms,
        ghost: { format: g.format, interval_ms: g.interval_ms, frame_count: g.frame_count, data: g.data },
        date: run.created_at,
      });
    }
  } catch {
    /* no server right now: this machine's progress stands, the next start tries again */
  }

  if (!listening) {
    listening = true;
    onProgress(schedulePush);
    useGarage.subscribe((s, prev) => {
      if (s.favourites !== prev.favourites) schedulePush();
    });
  }
}
