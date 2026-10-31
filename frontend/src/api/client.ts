// Thin client for the Laravel API (served under /api by nginx).
import type { CarId } from '../game/vehicle/carSpecs';
import type { EncodedGhost } from '../game/race/Ghost';

export const CLIENT_VERSION = '1.0.0';
const BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? '/api';
const TOKEN_KEY = 'touge-player';

export interface StoredPlayer {
  id: number;
  name: string;
  token: string;
}

export interface LeaderboardEntry {
  rank: number;
  run_id: number;
  player_id: number;
  player_name: string;
  is_bot: boolean;
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
  const headers: Record<string, string> = { Accept: 'application/json', ...(init.headers as Record<string, string>) };
  if (init.body) headers['Content-Type'] = 'application/json';
  if (token) headers.Authorization = `Bearer ${token}`;
  let res: Response;
  try {
    res = await fetch(BASE + path, { ...init, headers });
  } catch {
    throw new ApiError('サーバーに接続できません', 0);
  }
  const body = await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(body?.message ?? `HTTP ${res.status}`, res.status, body?.errors);
  return body as T;
}

export function loadPlayer(): StoredPlayer | null {
  try {
    const raw = localStorage.getItem(TOKEN_KEY);
    return raw ? (JSON.parse(raw) as StoredPlayer) : null;
  } catch {
    return null;
  }
}

function savePlayer(p: StoredPlayer) {
  try {
    localStorage.setItem(TOKEN_KEY, JSON.stringify(p));
  } catch {
    /* storage unavailable */
  }
}

export interface RoomMember {
  id: number;
  name: string;
  car_id: CarId;
  slot: number;
  finish_ms: number | null;
}

export interface RoomState {
  code: string;
  track_id: string;
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

  async ensurePlayer(name: string): Promise<StoredPlayer> {
    const existing = loadPlayer();
    if (existing) {
      if (existing.name !== name) {
        try {
          await request('/players/me', { method: 'PATCH', body: JSON.stringify({ name }) }, existing.token);
          existing.name = name;
          savePlayer(existing);
        } catch (e) {
          if (e instanceof ApiError && e.status === 401) {
            localStorage.removeItem(TOKEN_KEY);
            return api.ensurePlayer(name);
          }
          throw e;
        }
      }
      return existing;
    }
    const created = await request<{ id: number; name: string; token: string }>('/players', {
      method: 'POST',
      body: JSON.stringify({ name }),
    });
    const p = { id: created.id, name: created.name, token: created.token };
    savePlayer(p);
    return p;
  },

  realtime: () => request<{ realtime?: RealtimeInfo }>('/content').then((r) => r.realtime ?? { enabled: false, key: null, max_players: 3 }),

  rooms: {
    create: (p: StoredPlayer, trackId: string, carId: CarId) =>
      request<RoomState>('/rooms', { method: 'POST', body: JSON.stringify({ track_id: trackId, car_id: carId }) }, p.token),
    get: (p: StoredPlayer, code: string) => request<RoomState>(`/rooms/${encodeURIComponent(code)}`, {}, p.token),
    join: (p: StoredPlayer, code: string, carId: CarId) =>
      request<RoomState>(`/rooms/${encodeURIComponent(code)}/join`, { method: 'POST', body: JSON.stringify({ car_id: carId }) }, p.token),
    setCar: (p: StoredPlayer, code: string, carId: CarId) =>
      request<RoomState>(`/rooms/${encodeURIComponent(code)}/me`, { method: 'PATCH', body: JSON.stringify({ car_id: carId }) }, p.token),
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

// -------- local personal bests (work offline too), per course
const LEGACY_TRACK = 'oboro-downhill';
const readJson = <T,>(key: string, legacy?: string): T | null => {
  try {
    const raw = localStorage.getItem(key) ?? (legacy ? localStorage.getItem(legacy) : null);
    return raw ? (JSON.parse(raw) as T) : null;
  } catch {
    return null;
  }
};
const writeJson = (key: string, v: unknown) => {
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
  }
  return prev;
}
