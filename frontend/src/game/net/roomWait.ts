/**
 * What an online room waits for before its host can start, and who is loading its course. The room's `loaded` and
 * `ready` flags are the server's (`room.updated`); how far a member's game has come with the course travels as a
 * client event on the room's presence channel (`client-load`: one whole number, the percent; relayed by Reverb,
 * never stored), so that a course being built on a slower machine does not look like a member who is gone. This
 * file is the bookkeeping of both, free of sockets and timers so it can be tested.
 */

export interface WaitMember {
  id: number;
  name: string;
  loaded: boolean;
  ready: boolean;
}

export interface WaitRoom {
  host_id: number;
  players: readonly WaitMember[];
}

/**
 * Why the host cannot start yet (the server checks the same, in this order): too few players, games still loading
 * the course, guests who have not pressed 準備完了. Null: nothing holds the start.
 */
export type StartHold = { why: 'players' } | { why: 'loading' | 'ready'; who: WaitMember[] } | null;

export function startHold(room: WaitRoom, min = 2): StartHold {
  if (room.players.length < min) return { why: 'players' };
  const loading = room.players.filter((p) => !p.loaded);
  if (loading.length) return { why: 'loading', who: loading };
  const unready = room.players.filter((p) => p.id !== room.host_id && !p.ready);
  return unready.length ? { why: 'ready', who: unready } : null;
}

/** A member whose game is loading the course, as seen from here (times in ms on the caller's clock). */
export interface Waiting {
  /** first seen loading */
  since: number;
  /** how far, 0–100, as they last told it (null: not told: no connection yet, or an older game) */
  pct: number | null;
  /** when they last told it */
  heard: number;
}

/** The members who are loading after a new room state: those who went on loading keep their entry. */
export function nextWaits(prev: Readonly<Record<number, Waiting>>, players: readonly WaitMember[], now: number): Record<number, Waiting> {
  const out: Record<number, Waiting> = {};
  for (const p of players) if (!p.loaded) out[p.id] = prev[p.id] ?? { since: now, pct: null, heard: now };
  return out;
}

/**
 * a load that has told nothing new for this long is taking long: the host is told so and offered to take the member
 * out (an offer only: a course takes 5–20 s on a desktop, a step of it can take longer than that on a phone)
 */
export const STALLED_MS = 45_000;

export const stalled = (w: Waiting | undefined, now: number) => !!w && now - Math.max(w.since, w.heard) > STALLED_MS;

/**
 * The members who are not on the room's channel though their game has loaded the course (the game closed, the
 * connection lost), and since when. `present`: the ids on the channel (null: not known here, nobody is called
 * absent). A game that has just loaded joins the channel a moment later: see `GONE_MS`.
 */
export function nextAbsent(prev: Readonly<Record<number, number>>, players: readonly WaitMember[], present: readonly number[] | null, now: number): Record<number, number> {
  const out: Record<number, number> = {};
  if (present) for (const p of players) if (p.loaded && !present.includes(p.id)) out[p.id] = prev[p.id] ?? now;
  return out;
}

/** absent for this long: gone, as far as the room can tell (the host is offered to take the member out) */
export const GONE_MS = 8_000;

export const gone = (since: number | undefined, now: number) => since !== undefined && now - since > GONE_MS;

/** `client-load` as received: the percent, or null for anything that is not one. */
export function readLoad(data: unknown): number | null {
  const n = Array.isArray(data) && data.length === 1 ? data[0] : null;
  return typeof n === 'number' && Number.isFinite(n) ? Math.min(100, Math.max(0, Math.round(n))) : null;
}

/** A member told how far their load is: their entry with it (members who are not loading are not kept). */
export function heardLoad(waits: Readonly<Record<number, Waiting>>, id: number, pct: number, now: number): Record<number, Waiting> {
  const w = waits[id];
  return w ? { ...waits, [id]: { since: w.since, pct, heard: now } } : { ...waits };
}

/** at most two messages a second */
export const LOAD_INTERVAL_MS = 500;

/**
 * The sending end: the game's progress (0–1) as a message when the whole percent has changed, never sooner than
 * `interval` after the one before (the steps in between are never sent; the end is the server's `loaded`).
 */
export class LoadTeller {
  private told = -1;
  private last = -Infinity;

  constructor(readonly interval = LOAD_INTERVAL_MS) {}

  /** A new load begins: its first step goes out at once. */
  reset() {
    this.told = -1;
    this.last = -Infinity;
  }

  tell(progress: number, now: number): number[] | null {
    const pct = Math.min(100, Math.max(0, Math.round(progress * 100)));
    if (pct === this.told || now - this.last < this.interval) return null;
    this.told = pct;
    this.last = now;
    return [pct];
  }
}
