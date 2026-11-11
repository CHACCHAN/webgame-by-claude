import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { api, asProgress, legacyToken, loadGuest, loadPlayer, mergeProgress, type Progress } from '../client';
import { mergeFavourites } from '../../store/account';

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const memory = () => {
  const store = new Map<string, string>();
  return {
    store,
    getItem: (k: string) => store.get(k) ?? null,
    setItem: (k: string, v: string) => void store.set(k, v),
    removeItem: (k: string) => void store.delete(k),
    key: (i: number) => [...store.keys()][i] ?? null,
    get length() {
      return store.size;
    },
  };
};

// Members come from Authentik (a cookie the scripts never see); everyone else is a guest with a pass for the sitting.
describe('who plays', () => {
  let local: ReturnType<typeof memory>;
  let session: ReturnType<typeof memory>;
  let calls: string[];
  let known: Set<string>;
  let member: { id: number; name: string } | null;
  let made: number;

  beforeEach(async () => {
    local = memory();
    session = memory();
    calls = [];
    known = new Set();
    member = null;
    made = 0;
    vi.stubGlobal('localStorage', local);
    vi.stubGlobal('sessionStorage', session);
    vi.stubGlobal('fetch', async (url: string, init: RequestInit = {}) => {
      const method = init.method ?? 'GET';
      const headers = init.headers as Record<string, string>;
      calls.push(`${method} ${url}${headers.Authorization ? ' as ' + headers.Authorization.replace('Bearer ', '') : ''}`);
      expect(headers['X-Touge-Client']).toBe('1');
      expect(init.credentials).toBe('same-origin');
      const token = (headers.Authorization ?? '').replace('Bearer ', '');
      if (url.endsWith('/auth/me')) return json(200, { enabled: true, member });
      if (url.endsWith('/players') && method === 'POST') {
        const { name } = JSON.parse(init.body as string);
        const t = `pass-${++made}`;
        known.add(t);
        return json(201, { id: 10 + made, name, token: t, expires_at: 'soon' });
      }
      if (url.endsWith('/players/me')) return known.has(token) ? json(200, { id: 3, name: 'a' }) : json(401, { message: 'Unauthenticated player.' });
      return json(404, {});
    });
    await api.auth.me();
    calls.length = 0;
  });

  afterEach(() => vi.unstubAllGlobals());

  it('a guest is the name typed: a pass for the sitting, kept in the tab only', async () => {
    expect(loadPlayer()).toBeNull();
    const p = await api.ensurePlayer('a');
    expect(p).toEqual({ id: 11, name: 'a', token: 'pass-1' });
    expect(loadGuest()?.token).toBe('pass-1');
    expect(local.store.size).toBe(0);
    // the same name again in this sitting is the same guest
    expect((await api.ensurePlayer('a')).token).toBe('pass-1');
    expect(calls).toEqual(['POST /api/players', 'GET /api/players/me as pass-1']);
  });

  it('another name is another guest, not a rename of the records before', async () => {
    await api.ensurePlayer('a');
    const p = await api.ensurePlayer('b');
    expect(p).toEqual({ id: 12, name: 'b', token: 'pass-2' });
    expect(calls).toEqual(['POST /api/players', 'POST /api/players']);
  });

  it('a pass the server no longer knows is replaced', async () => {
    session.store.set('touge-guest', JSON.stringify({ id: 3, name: 'a', token: 'over' }));
    expect((await api.ensurePlayer('a')).token).toBe('pass-1');
    expect(calls).toEqual(['GET /api/players/me as over', 'POST /api/players']);
  });

  it('the player a browser kept from before logs nobody in', async () => {
    local.store.set('touge-player', JSON.stringify({ id: 3, name: 'old', token: 'for-good' }));
    expect(loadPlayer()).toBeNull();
    expect(legacyToken()).toBe('for-good');
    expect((await api.ensurePlayer('old')).token).toBe('pass-1');
  });

  it('a member is themselves whatever name is typed, and carries no token', async () => {
    member = { id: 5, name: 'ryo' };
    await api.auth.me();
    calls.length = 0;
    expect(await api.ensurePlayer('someone else')).toEqual({ id: 5, name: 'ryo', member: true });
    expect(loadPlayer()?.name).toBe('ryo');
    expect(calls).toEqual([]);
    expect(session.store.size + local.store.size).toBe(0);
  });
});

describe("a member's save data", () => {
  const p = (over: Partial<Progress>): Progress => ({ v: 1, carBests: {}, rivals: {}, favourites: [], ...over });

  it('two copies become one: the better time, the larger battle record, every favourite', () => {
    const a = p({ carBests: { oboro: { hayate: 150_000, r34: 140_000 } }, rivals: { oboro: { ace: { wins: 2, losses: 1 } } }, favourites: ['hayate'] });
    const b = p({ carBests: { oboro: { hayate: 149_000 }, kirifuri: { supra: 200_000 } }, rivals: { oboro: { ace: { wins: 1, losses: 3 }, rookie: { wins: 1, losses: 0 } } }, favourites: ['r34', 'hayate'] });
    expect(mergeProgress(a, b)).toEqual(
      p({
        carBests: { oboro: { hayate: 149_000, r34: 140_000 }, kirifuri: { supra: 200_000 } },
        rivals: { oboro: { ace: { wins: 2, losses: 3 }, rookie: { wins: 1, losses: 0 } } },
        favourites: ['hayate', 'r34'],
      }),
    );
    // (neither copy is changed)
    expect(a.carBests.oboro.hayate).toBe(150_000);
  });

  it('whatever the server holds is read safely', () => {
    expect(asProgress(null)).toEqual(p({}));
    expect(asProgress({ carBests: { oboro: { hayate: 'fast', r34: -1, supra: 1000 } }, rivals: { oboro: { ace: { wins: 2.7 } } }, favourites: ['a', 3, null] })).toEqual(
      p({ carBests: { oboro: { supra: 1000 } }, rivals: { oboro: { ace: { wins: 2, losses: 0 } } }, favourites: ['a'] }),
    );
  });

  it('a star taken away on this machine stays away, one given on another arrives', () => {
    // last agreed: hayate, r34. Here r34 was unstarred and supra starred; elsewhere s15 was starred.
    expect(mergeFavourites(['hayate', 'supra'], ['hayate', 'r34', 's15'], ['hayate', 'r34'])).toEqual(['hayate', 's15', 'supra']);
    // a first login: everything of both
    expect(mergeFavourites(['hayate'], ['r34'], [])).toEqual(['r34', 'hayate']);
  });
});
