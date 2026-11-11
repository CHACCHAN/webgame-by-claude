import { CAR_SPECS, type CarId } from '../vehicle/carSpecs';

/**
 * Vehicles being browsed in an online waiting room. A member's confirmed vehicle is the room's (`room.updated`, from
 * the server); what they are looking at in the vehicle picker meanwhile travels as a client event on the room's
 * presence channel (`client-browse`: relayed by Reverb, never stored, never seen by the server's ready rules). This
 * file is the bookkeeping of both ends, free of sockets and timers so it can be tested: what to send and when
 * (`BrowseThrottle`), what the others are looking at (`BrowseBook`), and the line-up that follows from the room and
 * the two (`lobbyEntries`).
 */

/** `client-browse`: the vehicle a member is looking at (with the livery picked for it, if any); `car: null` = none any more. */
export interface BrowseMessage {
  car: CarId | null;
  livery?: string;
}

/** A vehicle being looked at. */
export interface Browse {
  car: CarId;
  livery?: string;
}

/** at most two messages a second */
export const BROWSE_INTERVAL_MS = 500;

const NONE: BrowseMessage = { car: null };
const same = (a: BrowseMessage, b: BrowseMessage) => a.car === b.car && (a.car === null || a.livery === b.livery);
const message = (b: Browse | null): BrowseMessage => (b ? (b.livery ? { car: b.car, livery: b.livery } : { car: b.car }) : NONE);

/**
 * The sending end: a message only when what is looked at has changed from what the others were last told, and never
 * sooner than `interval` after the previous one (the newest state waits; the ones in between are never sent).
 */
export class BrowseThrottle {
  private want: BrowseMessage = NONE;
  private told: BrowseMessage = NONE;
  private last = -Infinity;

  constructor(readonly interval = BROWSE_INTERVAL_MS) {}

  /** The vehicle looked at now (null: none); `poll` says when it is to be sent. */
  look(browse: Browse | null) {
    this.want = message(browse);
  }

  /** `look`, and the message to send right away, if any. */
  set(browse: Browse | null, now: number): BrowseMessage | null {
    this.look(browse);
    return this.poll(now);
  }

  /** The message that is due at `now`, if any (call again after `wait`). */
  poll(now: number): BrowseMessage | null {
    if (same(this.want, this.told) || now - this.last < this.interval) return null;
    this.told = this.want;
    this.last = now;
    return this.want;
  }

  /** ms until `poll` has something to send; null while nothing is waiting. */
  wait(now: number): number | null {
    return same(this.want, this.told) ? null : Math.max(0, this.last + this.interval - now);
  }

  /** Someone joined who has not heard it: a vehicle being looked at is sent once more (as rarely as any other). */
  repeat() {
    if (this.want.car !== null) this.told = NONE;
  }

  /** What is looked at now, as the others will hear it. */
  get current(): Browse | null {
    return this.want.car === null ? null : this.want.livery ? { car: this.want.car, livery: this.want.livery } : { car: this.want.car };
  }

  /** Out of the room: nothing looked at, nothing owed to anybody. */
  reset() {
    this.want = this.told = NONE;
    this.last = -Infinity;
  }
}

/** A message as it came off the wire (anything a client may have sent): the vehicle, null for "none", undefined if malformed. */
export function parseBrowse(data: unknown, allowed?: (car: CarId) => boolean): Browse | null | undefined {
  if (!data || typeof data !== 'object') return undefined;
  const { car, livery } = data as { car?: unknown; livery?: unknown };
  if (car === null) return null;
  if (typeof car !== 'string' || !Object.hasOwn(CAR_SPECS, car)) return undefined;
  if (allowed && !allowed(car as CarId)) return undefined;
  // a colour as the garage's swatches give it (#rrggbb); anything else is dropped, the vehicle still counts
  return typeof livery === 'string' && /^#[0-9a-f]{6}$/i.test(livery) ? { car: car as CarId, livery: livery.toLowerCase() } : { car: car as CarId };
}

interface Seen extends Browse {
  /** the sender's confirmed vehicle when the message came (null: not in the room state yet) */
  base: CarId | null;
}

/**
 * The receiving end: what each other member was last heard looking at. A state ends when its sender says so, leaves
 * the room or the channel, or confirms a vehicle (their vehicle in the room state changes); a client that has heard
 * nothing (a late joiner) simply has no state, and shows the confirmed vehicles.
 */
export class BrowseBook {
  private seen = new Map<number, Seen>();
  private members = new Map<number, CarId>();

  /** A `client-browse` from member `id`. Returns whether anything changed. */
  receive(id: number, data: unknown, allowed?: (car: CarId) => boolean): boolean {
    const b = parseBrowse(data, allowed);
    if (b === undefined) return false;
    if (b === null) return this.seen.delete(id);
    const was = this.seen.get(id);
    if (was && was.car === b.car && was.livery === b.livery) return false;
    this.seen.set(id, { ...b, base: this.members.get(id) ?? null });
    return true;
  }

  /** The room's members and their confirmed vehicles (every room state). Returns whether a browse state ended. */
  sync(members: readonly { id: number; car_id: CarId }[]): boolean {
    const now = new Map(members.map((m) => [m.id, m.car_id]));
    let changed = false;
    for (const [id, s] of this.seen) {
      const car = now.get(id);
      // gone from the room, or the vehicle they entered with is not the one they had when they started looking
      // (a message that overtook the room state it belongs to has no base yet: it takes the first one it sees)
      if (car === undefined ? this.members.has(id) : s.base !== null && car !== s.base) changed = this.seen.delete(id) || changed;
      else if (car !== undefined) s.base = car;
    }
    this.members = now;
    return changed;
  }

  /** The member's socket left the channel (closed tab, lost connection): they are not choosing any more. */
  drop(id: number): boolean {
    return this.seen.delete(id);
  }

  get(id: number): Browse | null {
    const s = this.seen.get(id);
    return s ? (s.livery ? { car: s.car, livery: s.livery } : { car: s.car }) : null;
  }

  get size() {
    return this.seen.size;
  }

  clear() {
    this.seen.clear();
    this.members.clear();
  }
}

/** One vehicle of the waiting room's line-up: whose seat, what stands there, and whether it is only being looked at. */
export interface LobbyEntry {
  id: number;
  slot: number;
  carId: CarId;
  livery?: string;
  /** not their confirmed vehicle: the one they are looking at in the picker (選択中) */
  browsing: boolean;
}

/**
 * The line-up of a room: each member's confirmed vehicle, or the one they are looking at (`own` for the local
 * player `selfId`, the book for the others). Looking at one's confirmed vehicle is not browsing.
 */
export function lobbyEntries(
  players: readonly { id: number; slot: number; car_id: CarId }[],
  book: BrowseBook,
  selfId: number | null,
  own: Browse | null,
): LobbyEntry[] {
  return players
    .map((p): LobbyEntry => {
      const b = p.id === selfId ? own : book.get(p.id);
      if (b && (b.car !== p.car_id || b.livery)) return { id: p.id, slot: p.slot, carId: b.car, ...(b.livery ? { livery: b.livery } : {}), browsing: true };
      return { id: p.id, slot: p.slot, carId: p.car_id, browsing: false };
    })
    .sort((a, b) => a.slot - b.slot);
}
