// Thin client for the Laravel API (served under /api by nginx).
import type { CarId } from '../game/vehicle/carSpecs';
import type { EncodedGhost } from '../game/race/Ghost';
import type { TimeOfDay } from '../game/render/Environment';
import { APP_VERSION } from '../version';

export const CLIENT_VERSION = APP_VERSION;
const BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? '/api';
/** a guest's token carried over the trip to Authentik and back, so the records just set become the member's */
const CLAIM_KEY = 'touge-claim';
/** the player a browser kept for good before accounts came from Authentik: of use only to a member, who can claim its records */
const LEGACY_KEY = 'touge-player';

/**
 * Who plays. A member is logged in through Authentik (the login is a cookie the scripts cannot read: no token here);
 * a guest is a name typed for a record or for an evening online, with a pass that ends by itself. Nothing of a
 * guest is kept by the browser (owner 11-11): the pass and the progress live in this page's memory only.
 */
export interface StoredPlayer {
  id: number;
  name: string;
  /** a guest's pass; a member has none */
  token?: string;
  member?: boolean;
}

export interface LeaderboardEntry {
  rank: number;
  run_id: number;
  player_id: number;
  player_name: string;
  is_bot: boolean;
  /** an account (Authentik); else a guest's name */
  is_member?: boolean;
  car_id: CarId;
  mode: string;
  time_ms: number;
  sector_ms: number[];
  has_ghost: boolean;
  created_at: string;
}

export interface SubmitResult {
  run_id: number;
  time_ms: number;
  is_personal_best: boolean;
  previous_best_ms: number | null;
  rank: number;
  total_players: number;
}

export interface GhostResponse extends EncodedGhost {
  run_id: number;
  player_name: string;
  car_id: CarId;
  track_id: string;
  time_ms: number;
  sector_ms: number[];
}

export class ApiError extends Error {
  constructor(message: string, readonly status: number, readonly details?: unknown) {
    super(message);
  }
}

async function request<T>(path: string, init: RequestInit = {}, token?: string): Promise<T> {
  // (the header: the server takes a member's cookie for a change only from this client, never from a form elsewhere)
  const headers: Record<string, string> = { Accept: 'application/json', 'X-Touge-Client': '1', ...(init.headers as Record<string, string>) };
  if (init.body) headers['Content-Type'] = 'application/json';
  if (token) headers.Authorization = `Bearer ${token}`;
  let res: Response;
  try {
    res = await fetch(BASE + path, { ...init, headers, credentials: 'same-origin' });
  } catch {
    throw new ApiError('サーバーに接続できません', 0);
  }
  const body = await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(body?.message ?? `HTTP ${res.status}`, res.status, body?.errors ?? body);
  return body as T;
}

const storage = (kind: 'session' | 'local'): Storage | null => {
  try {
    return kind === 'session' ? sessionStorage : localStorage;
  } catch {
    return null;
  }
};
const readStored = <T,>(kind: 'session' | 'local', key: string): T | null => {
  try {
    const raw = storage(kind)?.getItem(key);
    return raw ? (JSON.parse(raw) as T) : null;
  } catch {
    return null;
  }
};
const writeStored = (kind: 'session' | 'local', key: string, value: unknown | null) => {
  try {
    if (value === null) storage(kind)?.removeItem(key);
    else storage(kind)?.setItem(key, JSON.stringify(value));
  } catch {
    /* storage unavailable */
  }
};

/** the member this browser is logged in as (told by the server at start: `api.auth.me`) */
let member: StoredPlayer | null = null;

/** the guest of this page, once a name was typed (memory only: a reload is a new guest) */
let guest: StoredPlayer | null = null;

export const loadGuest = () => guest;

/** Who plays right now: the member, else the guest of this sitting, else nobody yet. */
export function loadPlayer(): StoredPlayer | null {
  return member ?? loadGuest();
}

export const currentMember = () => member;

/** The token of the player this browser kept before the accounts came from Authentik (for a member to claim). */
export const legacyToken = () => readStored<{ token?: string }>('local', LEGACY_KEY)?.token ?? null;
export const forgetLegacy = () => writeStored('local', LEGACY_KEY, null);
/** Before the browser leaves for Authentik: the guest's token goes along (the page is loaded anew on the way back). */
export const carryGuest = () => guest?.token && writeStored('session', CLAIM_KEY, guest.token);
/** Back from Authentik: the token carried along, taken out (whatever the login came to, it is not kept). */
export function takeCarried(): string | null {
  const token = readStored<string>('session', CLAIM_KEY);
  writeStored('session', CLAIM_KEY, null);
  return typeof token === 'string' ? token : null;
}

export interface PlayerProfile {
  id: number;
  name: string;
  member: boolean;
  bests: { track_id: string; car_id: CarId; best_ms: number; runs: number }[];
  best_runs: { run_id: number; track_id: string; car_id: CarId; time_ms: number; sector_ms: number[]; has_ghost: boolean; created_at: string }[];
}

export interface RoomMember {
  id: number;
  name: string;
  car_id: CarId;
  /** the paint they picked for it (#rrggbb; null or missing: none, the seat's colour) */
  color?: string | null;
  slot: number;
  /** their game has loaded the room's course (reported by the game itself) */
  loaded: boolean;
  /** they pressed 準備完了 (never before `loaded`; the host needs none: the start button is the host's) */
  ready: boolean;
  finish_ms: number | null;
}

export interface RoomState {
  code: string;
  track_id: string;
  /** conditions the host chose: the same for everyone in the room */
  time_of_day: TimeOfDay;
  status: 'waiting' | 'racing' | 'finished';
  race_no: number;
  host_id: number;
  start_at_ms: number | null;
  server_time_ms: number;
  max_players: number;
  players: RoomMember[];
}

export interface RealtimeInfo {
  enabled: boolean;
  key: string | null;
  max_players: number;
}

export const api = {
  health: () => request<{ status: string; database: string; version: string }>('/health'),

  /** The login through Authentik (members); everything of it happens on the server, the browser only goes there and back. */
  auth: {
    /** Who the server says this browser is; remembered for `loadPlayer`. */
    async me(): Promise<{ enabled: boolean; member: StoredPlayer | null }> {
      const r = await request<{ enabled: boolean; member: { id: number; name: string } | null }>('/auth/me');
      member = r.member ? { id: r.member.id, name: r.member.name, member: true } : null;
      return { enabled: r.enabled, member };
    },
    /** Where the browser goes to log in (it comes back to `path` with `?login=ok|failed|denied|off`). */
    loginUrl: (path = '/') => `${BASE}/auth/login?return=${encodeURIComponent(path)}`,
    async logout() {
      try {
        await request('/auth/logout', { method: 'POST' });
      } finally {
        member = null;
      }
    },
    /** A guest's records become the member's (the guest's token says whose they were). */
    claim: (token: string) => request<{ claimed: number }>('/auth/claim', { method: 'POST', body: JSON.stringify({ token }) }),
  },

  /** A member's save data on the server, with the revision it was read at (409: changed elsewhere meanwhile, `details` has it). */
  save: {
    get: () => request<{ rev: number; save: unknown | null }>('/players/me/save'),
    put: (rev: number, save: unknown) => request<{ rev: number }>('/players/me/save', { method: 'PUT', body: JSON.stringify({ rev, save }) }),
  },

  profile: (p: StoredPlayer) => request<PlayerProfile>('/players/me', {}, p.token),

  /**
   * The player a record or an online seat goes to. A member is themselves whatever `name` says. A guest is the
   * name typed: the pass of this sitting if it is for that name and the server still knows it, else a new guest
   * (another name is another entry on the board, not a rename of the records before).
   */
  async ensurePlayer(name: string): Promise<StoredPlayer> {
    if (member) return member;
    if (guest && guest.name === name) {
      try {
        await request('/players/me', {}, guest.token);
        return guest;
      } catch (e) {
        if (!(e instanceof ApiError && e.status === 401)) throw e;
      }
    }
    const created = await request<{ id: number; name: string; token: string }>('/players', {
      method: 'POST',
      body: JSON.stringify({ name }),
    });
    guest = { id: created.id, name: created.name, token: created.token };
    return guest;
  },

  realtime: () => request<{ realtime?: RealtimeInfo }>('/content').then((r) => r.realtime ?? { enabled: false, key: null, max_players: 5 }),

  /** The rivals' language model behind the server (facts in, a line or a decision out; 503 = nobody to ask). */
  ai: {
    enabled: () => request<{ ai?: { enabled: boolean } }>('/content').then((r) => !!r.ai?.enabled),
    taunt: (body: object, signal?: AbortSignal) => request<{ line: string }>('/ai/taunt', { method: 'POST', body: JSON.stringify(body), signal }),
    decide: (body: object, signal?: AbortSignal) =>
      request<{ block: number | null; horn: 'short' | 'long' | 'double' | null }>('/ai/decide', { method: 'POST', body: JSON.stringify(body), signal }),
  },

  rooms: {
    create: (p: StoredPlayer, trackId: string, timeOfDay: TimeOfDay, carId: CarId, color: string | null) =>
      request<RoomState>('/rooms', { method: 'POST', body: JSON.stringify({ track_id: trackId, time_of_day: timeOfDay, car_id: carId, color }) }, p.token),
    get: (p: StoredPlayer, code: string) => request<RoomState>(`/rooms/${encodeURIComponent(code)}`, {}, p.token),
    join: (p: StoredPlayer, code: string, carId: CarId, color: string | null) =>
      request<RoomState>(`/rooms/${encodeURIComponent(code)}/join`, { method: 'POST', body: JSON.stringify({ car_id: carId, color }) }, p.token),
    /** the vehicle and its paint (another paint alone keeps the 準備完了; another vehicle takes it back) */
    setCar: (p: StoredPlayer, code: string, carId: CarId, color: string | null) =>
      request<RoomState>(`/rooms/${encodeURIComponent(code)}/me`, { method: 'PATCH', body: JSON.stringify({ car_id: carId, color }) }, p.token),
    setLoaded: (p: StoredPlayer, code: string) =>
      request<RoomState>(`/rooms/${encodeURIComponent(code)}/me`, { method: 'PATCH', body: JSON.stringify({ loaded: true }) }, p.token),
    setReady: (p: StoredPlayer, code: string, ready: boolean) =>
      request<RoomState>(`/rooms/${encodeURIComponent(code)}/me`, { method: 'PATCH', body: JSON.stringify({ ready }) }, p.token),
    leave: (p: StoredPlayer, code: string) => request<{ left: boolean }>(`/rooms/${encodeURIComponent(code)}/leave`, { method: 'POST' }, p.token),
    start: (p: StoredPlayer, code: string) => request<RoomState>(`/rooms/${encodeURIComponent(code)}/start`, { method: 'POST' }, p.token),
    finish: (p: StoredPlayer, code: string, raceNo: number, timeMs: number) =>
      request<RoomState>(`/rooms/${encodeURIComponent(code)}/finish`, { method: 'POST', body: JSON.stringify({ race_no: raceNo, time_ms: timeMs }) }, p.token),
    rematch: (p: StoredPlayer, code: string) => request<RoomState>(`/rooms/${encodeURIComponent(code)}/rematch`, { method: 'POST' }, p.token),
  },

  /** Signed authorization for the room's presence channel (Pusher protocol, served by Laravel). */
  channelAuth: (p: StoredPlayer, socketId: string, channelName: string) =>
    request<{ auth: string; channel_data: string }>('/broadcasting/auth', { method: 'POST', body: JSON.stringify({ socket_id: socketId, channel_name: channelName }) }, p.token),

  leaderboard: (trackId: string, carId?: CarId | null, limit = 50) =>
    request<{ entries: LeaderboardEntry[] }>(
      `/tracks/${trackId}/leaderboard?limit=${limit}${carId ? `&car_id=${carId}` : ''}`,
    ).then((r) => r.entries),

  submitRun(
    player: StoredPlayer,
    run: { track_id: string; car_id: CarId; mode: string; time_ms: number; sector_ms: number[]; rival_level?: string; rival_won?: boolean; ghost?: EncodedGhost },
  ) {
    return request<SubmitResult>(
      '/runs',
      { method: 'POST', body: JSON.stringify({ client_version: CLIENT_VERSION, ...run }) },
      player.token,
    );
  },

  ghost: (runId: number) => request<GhostResponse>(`/runs/${runId}/ghost`),
};

// -------- the progress (best times and ghosts, records against rivals), per course. A member's is kept on the
// machine (a copy of what the server has: store/account.ts); a guest's lives in this page's memory and is gone with it.
// What a browser kept from before 11-11 stays where it is until a member logs in there and takes it along.
const guestProgress = new Map<string, string>();
/** A new guest: nothing of the one before (tests; a page starts like this by itself). */
export function resetGuest() {
  guest = null;
  guestProgress.clear();
}
/** told after the progress kept on this machine changed (store/account.ts sends a member's to the server) */
const progressListeners = new Set<() => void>();
export const onProgress = (f: () => void) => {
  progressListeners.add(f);
  return () => void progressListeners.delete(f);
};
const progressChanged = () => progressListeners.forEach((f) => f());
const LEGACY_TRACK = 'oboro-downhill';
const readJson = <T,>(key: string, legacy?: string): T | null => {
  try {
    const raw = member ? localStorage.getItem(key) ?? (legacy ? localStorage.getItem(legacy) : null) : guestProgress.get(key) ?? null;
    return raw ? (JSON.parse(raw) as T) : null;
  } catch {
    return null;
  }
};
const writeJson = (key: string, v: unknown) => {
  if (!member) return void guestProgress.set(key, JSON.stringify(v));
  try {
    localStorage.setItem(key, JSON.stringify(v));
  } catch {
    /* storage unavailable or full */
  }
};

export interface LocalBest {
  carId: CarId;
  timeMs: number;
  splits: number[];
  ghost: EncodedGhost;
  date: string;
}

export function loadLocalBest(trackId: string): LocalBest | null {
  return readJson<LocalBest>(`touge-local-best:${trackId}`, trackId === LEGACY_TRACK ? 'touge-local-best' : undefined);
}

export function saveLocalBest(trackId: string, b: LocalBest) {
  writeJson(`touge-local-best:${trackId}`, b);
}

export function loadCarBests(trackId: string): Partial<Record<CarId, number>> {
  return readJson(`touge-car-bests:${trackId}`, trackId === LEGACY_TRACK ? 'touge-car-bests' : undefined) ?? {};
}

/** Store a time; returns the previous best for that car on that course (null if none). */
export function saveCarBest(trackId: string, car: CarId, timeMs: number): number | null {
  const all = loadCarBests(trackId);
  const prev = all[car] ?? null;
  if (prev === null || timeMs < prev) {
    all[car] = timeMs;
    writeJson(`touge-car-bests:${trackId}`, all);
    progressChanged();
  }
  return prev;
}

/** Battles against a course's rival, as the player's own record (what the rival knows when it speaks). */
export interface RivalRecord {
  wins: number;
  losses: number;
}

export function loadRivalRecord(trackId: string, level: string): RivalRecord {
  const all = readJson<Record<string, RivalRecord>>(`touge-rivals:${trackId}`) ?? {};
  return { wins: all[level]?.wins ?? 0, losses: all[level]?.losses ?? 0 };
}

export function saveRivalResult(trackId: string, level: string, playerWon: boolean) {
  const all = readJson<Record<string, RivalRecord>>(`touge-rivals:${trackId}`) ?? {};
  const r = loadRivalRecord(trackId, level);
  all[level] = { wins: r.wins + (playerWon ? 1 : 0), losses: r.losses + (playerWon ? 0 : 1) };
  writeJson(`touge-rivals:${trackId}`, all);
  progressChanged();
}

// -------- the progress as one piece: a member's save data (store/account.ts), without the ghosts (the server has
// them with the runs: `PlayerProfile.best_runs`)
export interface Progress {
  v: 1;
  /** course → vehicle → best time (ms) */
  carBests: Record<string, Record<string, number>>;
  /** course → rival level → battles */
  rivals: Record<string, Record<string, RivalRecord>>;
  favourites: string[];
}

const CAR_BESTS = 'touge-car-bests:';
const RIVALS = 'touge-rivals:';
const LOCAL_BEST = 'touge-local-best:';
const keysWith = (prefix: string) => {
  const out: string[] = [];
  if (!member) return [...guestProgress.keys()].filter((k) => k.startsWith(prefix)).map((k) => k.slice(prefix.length));
  try {
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i);
      if (k?.startsWith(prefix)) out.push(k.slice(prefix.length));
    }
  } catch {
    /* storage unavailable */
  }
  return out;
};

export function readProgress(favourites: string[]): Progress {
  const p: Progress = { v: 1, carBests: {}, rivals: {}, favourites };
  for (const t of new Set([...keysWith(CAR_BESTS), LEGACY_TRACK])) {
    const bests = loadCarBests(t) as Record<string, number>;
    if (Object.keys(bests).length) p.carBests[t] = bests;
  }
  for (const t of keysWith(RIVALS)) p.rivals[t] = readJson<Record<string, RivalRecord>>(RIVALS + t) ?? {};
  return p;
}

/** The times and battles of a save written onto this machine (favourites are the garage store's). */
export function writeProgress(p: Progress) {
  for (const [t, bests] of Object.entries(p.carBests)) writeJson(CAR_BESTS + t, bests);
  for (const [t, r] of Object.entries(p.rivals)) writeJson(RIVALS + t, r);
}

/** What a logout leaves behind: nothing of the member (it is all on the server). */
export function clearProgress() {
  try {
    for (const prefix of [CAR_BESTS, RIVALS, LOCAL_BEST]) for (const t of keysWith(prefix)) localStorage.removeItem(prefix + t);
    for (const k of ['touge-local-best', 'touge-car-bests']) localStorage.removeItem(k);
  } catch {
    /* storage unavailable */
  }
}

const num = (v: unknown) => (typeof v === 'number' && Number.isFinite(v) && v > 0 ? v : null);

/** A save from the server or from an older build, made safe to read. */
export function asProgress(raw: unknown): Progress {
  const o = (raw && typeof raw === 'object' ? raw : {}) as Partial<Progress>;
  const p: Progress = { v: 1, carBests: {}, rivals: {}, favourites: [] };
  for (const [t, bests] of Object.entries(o.carBests ?? {})) {
    for (const [car, ms] of Object.entries(bests ?? {})) if (num(ms)) (p.carBests[t] ??= {})[car] = ms;
  }
  for (const [t, levels] of Object.entries(o.rivals ?? {})) {
    for (const [level, r] of Object.entries(levels ?? {})) {
      (p.rivals[t] ??= {})[level] = { wins: Math.floor(num(r?.wins) ?? 0), losses: Math.floor(num(r?.losses) ?? 0) };
    }
  }
  if (Array.isArray(o.favourites)) p.favourites = o.favourites.filter((f): f is string => typeof f === 'string').slice(0, 64);
  return p;
}

/**
 * Two copies of a member's progress made one (this machine's and the server's, or two machines'): the better time
 * of each vehicle, the larger count of each battle record (the same battles are in both: adding would count them
 * twice), every favourite of either.
 */
export function mergeProgress(a: Progress, b: Progress): Progress {
  const out = asProgress(a);
  for (const [t, bests] of Object.entries(b.carBests)) {
    for (const [car, ms] of Object.entries(bests)) {
      const mine = out.carBests[t]?.[car];
      if (mine === undefined || ms < mine) (out.carBests[t] ??= {})[car] = ms;
    }
  }
  for (const [t, levels] of Object.entries(b.rivals)) {
    for (const [level, r] of Object.entries(levels)) {
      const mine = out.rivals[t]?.[level] ?? { wins: 0, losses: 0 };
      (out.rivals[t] ??= {})[level] = { wins: Math.max(mine.wins, r.wins), losses: Math.max(mine.losses, r.losses) };
    }
  }
  out.favourites = [...new Set([...out.favourites, ...b.favourites])];
  return out;
}
