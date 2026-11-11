import { describe, expect, it } from 'vitest';
import { BROWSE_INTERVAL_MS, BrowseBook, BrowseThrottle, lobbyEntries, parseBrowse } from './browse';
import type { CarId } from '../vehicle/carSpecs';

describe('BrowseThrottle (what a member sends while choosing a vehicle)', () => {
  it('sends a change at once, then at most one message per interval, and only the newest state', () => {
    const t = new BrowseThrottle();
    expect(t.set({ car: 'supra' }, 1000)).toEqual({ car: 'supra' });
    // three more within the interval: nothing goes out, the last one waits
    expect(t.set({ car: 'r34' }, 1100)).toBeNull();
    expect(t.set({ car: 's15' }, 1200)).toBeNull();
    expect(t.set({ car: 'e235' }, 1300)).toBeNull();
    expect(t.wait(1300)).toBe(BROWSE_INTERVAL_MS - 300);
    expect(t.poll(1499)).toBeNull();
    expect(t.poll(1500)).toEqual({ car: 'e235' });
    expect(t.wait(1500)).toBeNull();
    expect(t.poll(5000)).toBeNull();
  });

  it('never more than two messages a second, however fast the picker moves', () => {
    const t = new BrowseThrottle();
    const cars = ['supra', 'r34', 's15', 'hayate'] as const;
    const sent: number[] = [];
    for (let now = 0; now < 10_000; now += 16) {
      if (t.set({ car: cars[Math.floor(now / 16) % cars.length] }, now)) sent.push(now);
    }
    expect(sent.length).toBeGreaterThan(10);
    expect(sent.length).toBeLessThanOrEqual(20);
    for (let k = 1; k < sent.length; k++) expect(sent[k] - sent[k - 1]).toBeGreaterThanOrEqual(BROWSE_INTERVAL_MS);
  });

  it('sends nothing without a change', () => {
    const t = new BrowseThrottle();
    expect(t.set(null, 0)).toBeNull();
    expect(t.set({ car: 'supra' }, 1000)).not.toBeNull();
    expect(t.set({ car: 'supra' }, 3000)).toBeNull();
    // back and forth within the interval ends where it began: nothing to say
    expect(t.set({ car: 'r34' }, 3100)).not.toBeNull();
    expect(t.set({ car: 'supra' }, 3200)).toBeNull();
    expect(t.set({ car: 'r34' }, 3300)).toBeNull();
    expect(t.wait(3300)).toBeNull();
    expect(t.poll(9000)).toBeNull();
  });

  it('a livery is part of the state; the end of browsing is a message too', () => {
    const t = new BrowseThrottle();
    expect(t.set({ car: 'e231', livery: '#00b261' }, 0)).toEqual({ car: 'e231', livery: '#00b261' });
    expect(t.current).toEqual({ car: 'e231', livery: '#00b261' });
    expect(t.set({ car: 'e231', livery: '#f15a22' }, 1000)).toEqual({ car: 'e231', livery: '#f15a22' });
    expect(t.set(null, 2000)).toEqual({ car: null });
    expect(t.current).toBeNull();
    expect(t.set(null, 3000)).toBeNull();
  });

  it('repeats the state for a member who joined (throttled like the rest); nothing if not browsing', () => {
    const t = new BrowseThrottle();
    t.repeat();
    expect(t.poll(0)).toBeNull();
    expect(t.set({ car: 'roach' }, 1000)).not.toBeNull();
    t.repeat();
    expect(t.poll(1100)).toBeNull();
    expect(t.poll(1500)).toEqual({ car: 'roach' });
    // after leaving the room nothing is owed
    t.reset();
    t.repeat();
    expect(t.poll(99_000)).toBeNull();
  });
});

describe('parseBrowse (anything may come off the wire)', () => {
  it('takes a known vehicle, a swatch colour, and the end message', () => {
    expect(parseBrowse({ car: 'ninjah2' })).toEqual({ car: 'ninjah2' });
    expect(parseBrowse({ car: 'e231', livery: '#00B261' })).toEqual({ car: 'e231', livery: '#00b261' });
    expect(parseBrowse({ car: null })).toBeNull();
  });
  it('drops what it does not know', () => {
    for (const bad of [null, undefined, 'supra', 7, {}, { car: 'tardis' }, { car: 'constructor' }, { car: 3 }]) expect(parseBrowse(bad)).toBeUndefined();
    expect(parseBrowse({ car: 'supra', livery: 'url(javascript:1)' })).toEqual({ car: 'supra' });
    expect(parseBrowse({ car: 'supra' }, (c) => c !== 'supra')).toBeUndefined();
  });
});

describe('BrowseBook (what the others are looking at)', () => {
  const room = (...cars: [number, CarId][]) => cars.map(([id, car_id]) => ({ id, car_id }));

  it('keeps the last vehicle heard per member until they stop', () => {
    const b = new BrowseBook();
    b.sync(room([1, 'hayate'], [2, 'supra']));
    expect(b.get(2)).toBeNull();
    expect(b.receive(2, { car: 'r34' })).toBe(true);
    expect(b.receive(2, { car: 'r34' })).toBe(false);
    expect(b.receive(2, { car: 'e235' })).toBe(true);
    expect(b.get(2)).toEqual({ car: 'e235' });
    expect(b.receive(2, { car: 'nonsense' })).toBe(false);
    expect(b.get(2)).toEqual({ car: 'e235' });
    expect(b.receive(2, { car: null })).toBe(true);
    expect(b.get(2)).toBeNull();
    expect(b.receive(2, { car: null })).toBe(false);
  });

  it('ends a state when its sender confirms a vehicle, whichever it is', () => {
    const b = new BrowseBook();
    b.sync(room([1, 'hayate'], [2, 'supra']));
    b.receive(2, { car: 'e235' });
    // other members' changes, and their own ready or loaded marks, leave it alone
    expect(b.sync(room([1, 'shiden'], [2, 'supra']))).toBe(false);
    expect(b.get(2)).toEqual({ car: 'e235' });
    expect(b.sync(room([1, 'shiden'], [2, 'e235']))).toBe(true);
    expect(b.get(2)).toBeNull();
  });

  it('ends a state when its sender leaves the room or the channel', () => {
    const b = new BrowseBook();
    b.sync(room([1, 'hayate'], [2, 'supra'], [3, 'r34']));
    b.receive(2, { car: 'e235' });
    b.receive(3, { car: 'roach' });
    expect(b.sync(room([1, 'hayate'], [3, 'r34']))).toBe(true);
    expect(b.get(2)).toBeNull();
    expect(b.get(3)).toEqual({ car: 'roach' });
    expect(b.drop(3)).toBe(true);
    expect(b.drop(3)).toBe(false);
    expect(b.size).toBe(0);
  });

  it('a message that overtakes the room state of a new member is kept, and ends with their next confirmed change', () => {
    const b = new BrowseBook();
    b.sync(room([1, 'hayate']));
    b.receive(2, { car: 'roach' });
    expect(b.sync(room([1, 'hayate']))).toBe(false);
    expect(b.sync(room([1, 'hayate'], [2, 'supra']))).toBe(false);
    expect(b.get(2)).toEqual({ car: 'roach' });
    expect(b.sync(room([1, 'hayate'], [2, 'roach']))).toBe(true);
  });
});

describe('lobbyEntries (the line-up of a room)', () => {
  const players: { id: number; slot: number; car_id: CarId }[] = [
    { id: 11, slot: 1, car_id: 'supra' },
    { id: 10, slot: 0, car_id: 'hayate' },
    { id: 12, slot: 3, car_id: 'e235' },
  ];
  const at = (list: ReturnType<typeof lobbyEntries>, id: number) => list.find((e) => e.id === id)!;

  it('a late joiner, who has heard no browse event, sees the confirmed vehicles', () => {
    expect(lobbyEntries(players, new BrowseBook(), 12, null)).toEqual([
      { id: 10, slot: 0, carId: 'hayate', browsing: false },
      { id: 11, slot: 1, carId: 'supra', browsing: false },
      { id: 12, slot: 3, carId: 'e235', browsing: false },
    ]);
  });

  it('shows what a member is looking at in their seat, marked, until they confirm or stop', () => {
    const b = new BrowseBook();
    b.sync(players);
    b.receive(11, { car: 'ninjah2' });
    expect(at(lobbyEntries(players, b, 10, null), 11)).toEqual({ id: 11, slot: 1, carId: 'ninjah2', browsing: true });
    // confirmed: the room says so, the mark goes
    const confirmed = players.map((p) => (p.id === 11 ? { ...p, car_id: 'ninjah2' as const } : p));
    b.sync(confirmed);
    expect(at(lobbyEntries(confirmed, b, 10, null), 11)).toEqual({ id: 11, slot: 1, carId: 'ninjah2', browsing: false });
    // left the picker without confirming: back to the confirmed vehicle
    b.receive(12, { car: 'roach' });
    expect(at(lobbyEntries(confirmed, b, 10, null), 12).carId).toBe('roach');
    b.receive(12, { car: null });
    expect(at(lobbyEntries(confirmed, b, 10, null), 12)).toEqual({ id: 12, slot: 3, carId: 'e235', browsing: false });
  });

  it('the local player: their own picker, not the book; looking at the confirmed vehicle is not browsing', () => {
    const b = new BrowseBook();
    b.sync(players);
    // (an echo of one's own event would be ignored)
    b.receive(10, { car: 'roach' });
    const me = (own: Parameters<typeof lobbyEntries>[3]) => at(lobbyEntries(players, b, 10, own), 10);
    expect(me(null)).toEqual({ id: 10, slot: 0, carId: 'hayate', browsing: false });
    expect(me({ car: 'hayate' })).toEqual({ id: 10, slot: 0, carId: 'hayate', browsing: false });
    expect(me({ car: 'r34' })).toEqual({ id: 10, slot: 0, carId: 'r34', browsing: true });
    expect(me({ car: 'e231', livery: '#00b261' })).toEqual({ id: 10, slot: 0, carId: 'e231', livery: '#00b261', browsing: true });
  });
});
