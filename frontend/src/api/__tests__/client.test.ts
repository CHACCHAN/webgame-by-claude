import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { api, loadPlayer } from '../client';

// A stored token the server no longer knows (its players were reset) must not make every later submission fail:
// ensurePlayer checks it and registers the player again.
describe('ensurePlayer', () => {
  let store: Map<string, string>;
  let calls: string[];
  let known: Set<string>;

  const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

  beforeEach(() => {
    store = new Map();
    calls = [];
    known = new Set();
    vi.stubGlobal('localStorage', {
      getItem: (k: string) => store.get(k) ?? null,
      setItem: (k: string, v: string) => void store.set(k, v),
      removeItem: (k: string) => void store.delete(k),
    });
    vi.stubGlobal('fetch', async (url: string, init: RequestInit = {}) => {
      const method = init.method ?? 'GET';
      calls.push(`${method} ${url}`);
      const token = ((init.headers as Record<string, string>).Authorization ?? '').replace('Bearer ', '');
      if (url.endsWith('/players') && method === 'POST') {
        const { name } = JSON.parse(init.body as string);
        known.add('new-token');
        return json(201, { id: 7, name, token: 'new-token' });
      }
      if (url.endsWith('/players/me')) {
        if (!known.has(token)) return json(401, { message: 'Unauthenticated.' });
        return json(200, { id: 3, name: 'a' });
      }
      return json(404, {});
    });
  });

  afterEach(() => vi.unstubAllGlobals());

  it('registers again when the stored token is unknown, with the same name', async () => {
    store.set('touge-player', JSON.stringify({ id: 3, name: 'a', token: 'stale' }));
    const p = await api.ensurePlayer('a');
    expect(p).toEqual({ id: 7, name: 'a', token: 'new-token' });
    expect(loadPlayer()?.token).toBe('new-token');
    expect(calls).toEqual(['GET /api/players/me', 'POST /api/players']);
  });

  it('registers again when the stored token is unknown and the name changed', async () => {
    store.set('touge-player', JSON.stringify({ id: 3, name: 'a', token: 'stale' }));
    const p = await api.ensurePlayer('b');
    expect(p.token).toBe('new-token');
    expect(p.name).toBe('b');
    expect(calls).toEqual(['PATCH /api/players/me', 'POST /api/players']);
  });

  it('keeps a valid token', async () => {
    known.add('good');
    store.set('touge-player', JSON.stringify({ id: 3, name: 'a', token: 'good' }));
    const p = await api.ensurePlayer('a');
    expect(p.token).toBe('good');
    expect(calls).toEqual(['GET /api/players/me']);
  });
});
