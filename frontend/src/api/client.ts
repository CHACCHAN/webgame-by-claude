// Thin client for the Laravel API (served under /api by nginx).
import type { CarId } from '../game/vehicle/carSpecs';
import type { EncodedGhost } from '../game/race/Ghost';

export const TRACK_ID = 'oboro-downhill';
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

  leaderboard: (carId?: CarId | null, limit = 50) =>
    request<{ entries: LeaderboardEntry[] }>(
      `/tracks/${TRACK_ID}/leaderboard?limit=${limit}${carId ? `&car_id=${carId}` : ''}`,
    ).then((r) => r.entries),

  submitRun(
    player: StoredPlayer,
    run: { car_id: CarId; mode: string; time_ms: number; sector_ms: number[]; rival_level?: string; rival_won?: boolean; ghost?: EncodedGhost },
  ) {
    return request<SubmitResult>(
      '/runs',
      { method: 'POST', body: JSON.stringify({ track_id: TRACK_ID, client_version: CLIENT_VERSION, ...run }) },
      player.token,
    );
  },

  ghost: (runId: number) => request<GhostResponse>(`/runs/${runId}/ghost`),
};

// -------- local personal bests (work offline too)
const LOCAL_BEST = 'touge-local-best';
export interface LocalBest {
  carId: CarId;
  timeMs: number;
  splits: number[];
  ghost: EncodedGhost;
  date: string;
}

export function loadLocalBest(): LocalBest | null {
  try {
    const raw = localStorage.getItem(LOCAL_BEST);
    return raw ? (JSON.parse(raw) as LocalBest) : null;
  } catch {
    return null;
  }
}

export function saveLocalBest(b: LocalBest) {
  try {
    localStorage.setItem(LOCAL_BEST, JSON.stringify(b));
  } catch {
    /* ignore quota errors */
  }
}

// -------- per-car personal bests (times only)
const CAR_BESTS = 'touge-car-bests';
export function loadCarBests(): Partial<Record<CarId, number>> {
  try {
    return JSON.parse(localStorage.getItem(CAR_BESTS) ?? '{}');
  } catch {
    return {};
  }
}

/** Store a time; returns the previous best for that car (null if none). */
export function saveCarBest(car: CarId, timeMs: number): number | null {
  const all = loadCarBests();
  const prev = all[car] ?? null;
  if (prev === null || timeMs < prev) {
    all[car] = timeMs;
    try {
      localStorage.setItem(CAR_BESTS, JSON.stringify(all));
    } catch {
      /* ignore */
    }
  }
  return prev;
}
