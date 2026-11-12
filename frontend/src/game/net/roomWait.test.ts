import { describe, expect, it } from 'vitest';
import { gone, GONE_MS, heardLoad, LoadTeller, nextAbsent, nextWaits, readLoad, stalled, STALLED_MS, startHold, type WaitMember } from './roomWait';

const m = (id: number, loaded: boolean, ready: boolean): WaitMember => ({ id, name: `P${id}`, loaded, ready });

describe('what the start waits for', () => {
  it('needs two players, then every game loaded, then every guest ready (the host needs none)', () => {
    expect(startHold({ host_id: 1, players: [m(1, true, false)] })).toEqual({ why: 'players' });
    const loading = startHold({ host_id: 1, players: [m(1, true, false), m(2, false, false), m(3, true, true), m(4, false, false)] });
    expect(loading).toEqual({ why: 'loading', who: [m(2, false, false), m(4, false, false)] });
    // the host's own game counts as one that loads
    expect(startHold({ host_id: 1, players: [m(1, false, false), m(2, true, true)] })).toEqual({ why: 'loading', who: [m(1, false, false)] });
    expect(startHold({ host_id: 1, players: [m(1, true, false), m(2, true, false), m(3, true, true)] })).toEqual({ why: 'ready', who: [m(2, true, false)] });
    expect(startHold({ host_id: 1, players: [m(1, true, false), m(2, true, true), m(3, true, true)] })).toBeNull();
    // after the host left: the new host's ready is not asked for, the old guests' is
    expect(startHold({ host_id: 2, players: [m(2, true, false), m(3, true, true)] })).toBeNull();
  });
});

describe('who is loading', () => {
  it('keeps since when a member has been loading, and forgets one who is done', () => {
    let w = nextWaits({}, [m(1, true, false), m(2, false, false)], 1000);
    expect(w).toEqual({ 2: { since: 1000, pct: null, heard: 1000 } });
    w = heardLoad(w, 2, 50, 4000);
    w = nextWaits(w, [m(1, false, false), m(2, false, false)], 5000);
    expect(w).toEqual({ 1: { since: 5000, pct: null, heard: 5000 }, 2: { since: 1000, pct: 50, heard: 4000 } });
    w = nextWaits(w, [m(1, false, false), m(2, true, false)], 6000);
    expect(Object.keys(w)).toEqual(['1']);
    // loading again (another course): a new entry, nothing of the load before
    w = nextWaits(w, [m(1, false, false), m(2, false, false)], 9000);
    expect(w[2]).toEqual({ since: 9000, pct: null, heard: 9000 });
  });

  it('takes progress only from members who are loading', () => {
    const w = nextWaits({}, [m(2, false, false)], 0);
    expect(heardLoad(w, 7, 40, 100)).toEqual(w);
    expect(heardLoad(w, 2, 40, 100)[2]).toEqual({ since: 0, pct: 40, heard: 100 });
  });

  it('calls a load slow when nothing new was heard for a while', () => {
    const w = nextWaits({}, [m(2, false, false)], 0);
    expect(stalled(w[2], STALLED_MS)).toBe(false);
    expect(stalled(w[2], STALLED_MS + 1)).toBe(true);
    // progress told since: the load is alive
    const told = heardLoad(w, 2, 75, STALLED_MS);
    expect(stalled(told[2], STALLED_MS + 5000)).toBe(false);
    expect(stalled(told[2], 2 * STALLED_MS + 1)).toBe(true);
    expect(stalled(undefined, 1e9)).toBe(false);
  });
});

describe('who is gone', () => {
  it('is a loaded member who stays off the channel; a loading one is not there yet, and without a channel nobody is', () => {
    const players = [m(1, true, false), m(2, true, true), m(3, false, false)];
    expect(nextAbsent({}, players, null, 0)).toEqual({});
    let a = nextAbsent({}, players, [1], 1000);
    expect(a).toEqual({ 2: 1000 });
    expect(gone(a[2], 1000 + GONE_MS)).toBe(false);
    a = nextAbsent(a, players, [1], 1000 + GONE_MS + 1);
    expect(a).toEqual({ 2: 1000 });
    expect(gone(a[2], 1000 + GONE_MS + 1)).toBe(true);
    // back on the channel: forgotten; away again: counted from then
    a = nextAbsent(a, players, [1, 2], 20_000);
    expect(a).toEqual({});
    expect(nextAbsent(a, players, [1], 30_000)).toEqual({ 2: 30_000 });
    expect(gone(undefined, 1e9)).toBe(false);
  });
});

describe('client-load', () => {
  it('reads one whole percent and nothing else', () => {
    expect(readLoad([50])).toBe(50);
    expect(readLoad([49.6])).toBe(50);
    expect(readLoad([250])).toBe(100);
    expect(readLoad([-3])).toBe(0);
    for (const bad of [null, 50, '50', [], [1, 2], ['50'], [NaN], [Infinity], { 0: 50 }]) expect(readLoad(bad)).toBeNull();
  });

  it('sends whole numbers, a step only when it changed and never more than twice a second', () => {
    const t = new LoadTeller();
    expect(t.tell(0, 0)).toEqual([0]);
    expect(t.tell(0.12, 100)).toBeNull();
    expect(t.tell(0.25, 499)).toBeNull();
    expect(t.tell(0.25, 500)).toEqual([25]);
    expect(t.tell(0.25, 5000)).toBeNull();
    expect(t.tell(0.921, 5001)).toEqual([92]);
    const sent = t.tell(1, 6000)!;
    expect(sent).toEqual([100]);
    expect(sent.every(Number.isInteger)).toBe(true);
    // the next load starts over, at once
    t.reset();
    expect(t.tell(0, 6001)).toEqual([0]);
  });
});
