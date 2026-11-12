import { create } from 'zustand';
import type { PresenceChannel } from 'pusher-js';
import type { RoomState } from '../api/client';
import { gameHolder } from '../ui/GameCanvas';
import { useApp } from './app';
import type { Game } from '../game/Game';
import { BrowseBook, BrowseThrottle, isConfirmed, lobbyEntries, type Browse, type LobbyEntry } from '../game/net/browse';
import { vehiclesFor, type CarId } from '../game/vehicle/carSpecs';
import { offeredPaint } from '../game/vehicle/paints';

/**
 * The waiting room's vehicles (UI side of game/net/LobbyLineup.ts and game/net/browse.ts). `store/online.ts` hands
 * every room state (`lobbyRoom`) and the presence channel (`lobbyChannel`) to this file; it knows nothing of the
 * race's car states.
 *
 * - The line-up: `showRoomLineup()` puts every member's vehicle on the course, and each change of the room after it.
 * - Vehicles being looked at: whatever shows a vehicle in the garage while the player is in a room that waits (a
 *   picker calling `game.showGarage` / `setGarageColor`), or `previewCar` for a picker that leaves the line-up up,
 *   is told to the others (`client-browse`, at most twice a second, only changes) and shown in the player's seat as
 *   選択中 until `chooseCar` has it confirmed by the server or the picker is left (`endPreview`, `showRoomLineup`).
 */
interface LobbyState {
  /** members who are choosing (the local player too): member id → the vehicle they are looking at */
  choosing: Record<number, CarId>;
}

export const useLobby = create<LobbyState>(() => ({ choosing: {} }));

const book = new BrowseBook();
const throttle = new BrowseThrottle();
let room: RoomState | null = null;
let selfId: number | null = null;
let channel: PresenceChannel | null = null;
/** what the local player is looking at (null: their confirmed vehicle) */
let own: Browse | null = null;
/** the game shows the line-up (false: something else has the scene, a picker's garage or a race) */
let lineup = false;
let timer = 0;
const hooked = new WeakSet<Game>();

const me = () => room?.players.find((p) => p.id === selfId);
const waiting = () => room?.status === 'waiting';


/** Every room state as it is applied, and null when the room is left. */
export function lobbyRoom(next: RoomState | null, self: number | null) {
  if (!next) {
    const last = me();
    room = null;
    selfId = null;
    forget();
    lobbyChannel(null);
    // nothing of the room stays on the course: back to the player's own vehicle in the garage
    if (lineup && last) gameHolder.game?.showGarage(last.car_id, offeredPaint(last.car_id, last.color));
    lineup = false;
    publish();
    return;
  }
  if (room && room.code !== next.code) forget();
  room = next;
  selfId = self;
  hook();
  book.sync(next.players);
  if (next.status !== 'waiting') {
    // the race has the scene; nobody is choosing any more
    lineup = false;
    forget();
  } else if (own && me() && isConfirmed(own, me()!)) {
    // confirmed by the server: not "choosing" any more
    look(null);
  }
  publish();
}

/** The room's presence channel, once subscribed to (null: left). */
export function lobbyChannel(ch: PresenceChannel | null) {
  channel = ch;
  if (!ch) return;
  ch.bind('client-browse', (data: unknown, meta?: { user_id?: string }) => {
    const id = Number(meta?.user_id);
    if (!id || id === selfId || !waiting()) return;
    const course = room!.track_id;
    if (book.receive(id, data, (car) => vehiclesFor(course).includes(car))) publish();
  });
  // (also after a reconnection: what was heard before may have ended meanwhile, and the others have forgotten us)
  ch.bind('pusher:subscription_succeeded', () => {
    book.clear();
    if (room) book.sync(room.players);
    throttle.repeat();
    publish();
    pump();
  });
  // someone new has not heard what is being looked at here
  ch.bind('pusher:member_added', () => {
    throttle.repeat();
    pump();
  });
  ch.bind('pusher:member_removed', (member: { id: string | number }) => {
    if (book.drop(Number(member.id))) publish();
  });
}

/**
 * The waiting room's line-up takes the scene (the room screen is up): every member's vehicle, the local player's
 * confirmed one included. Until the next thing that shows a vehicle in the garage (the car select), or the race.
 */
export function showRoomLineup(keep = false) {
  const game = gameHolder.game;
  // (not while the room's course is still being built: `enterRoom` calls once it is there)
  if (!room || !waiting() || !game || game.course?.id !== room.track_id || useApp.getState().loading) return;
  lineup = true;
  // (`keep`: a picker that had the scene was closed on a choice the server has yet to confirm: it stays 選択中)
  if (!keep) look(null);
  publish();
}

/** The line-up is gone from the scene (the game builds another course): nothing is shown until `showRoomLineup`. */
export function hideRoomLineup() {
  lineup = false;
}

/** A vehicle looked at in a picker that leaves the line-up on screen: shown in the player's seat, told to the others. */
export function previewCar(carId: CarId, livery?: string) {
  if (!waiting()) return;
  look({ car: carId, livery: offeredPaint(carId, livery) });
  publish();
}

/** The picker was left without a choice: the player's confirmed vehicle again. */
export function endPreview() {
  if (!own) return;
  look(null);
  publish();
}

function look(b: Browse | null) {
  // one's confirmed vehicle in its paint is not a choice in the making
  const m = me();
  own = b && m && isConfirmed(b, m) ? null : b;
  throttle.look(own);
  pump();
}

/** Sends what is due, and comes back when the next message may go. */
function pump() {
  clearTimeout(timer);
  timer = 0;
  // (a connection that dropped still calls itself subscribed: what is due goes out when it is back, see
  // `pusher:subscription_succeeded`)
  if (!channel?.subscribed || channel.pusher.connection.state !== 'connected') return;
  const m = throttle.poll(performance.now());
  if (m) channel.trigger('client-browse', m);
  const wait = throttle.wait(performance.now());
  if (wait !== null) timer = window.setTimeout(pump, wait + 5);
}

function forget() {
  book.clear();
  if (room) {
    // (a last "not choosing any more" goes out if the others were told of a vehicle)
    if (own) look(null);
    book.sync(room.players);
    return;
  }
  // the room is left: nothing more is sent (the connection closes, and with it the others drop what this player
  // was looking at)
  own = null;
  throttle.reset();
  clearTimeout(timer);
  timer = 0;
}

/** The line-up from the room and the browse states: to the screens, and to the game while it shows the line-up. */
function publish() {
  const entries: LobbyEntry[] = room && waiting() ? lobbyEntries(room.players, book, selfId, own) : [];
  const choosing: Record<number, CarId> = {};
  for (const e of entries) if (e.browsing) choosing[e.id] = e.carId;
  const was = useLobby.getState().choosing;
  const same = Object.keys(was).length === Object.keys(choosing).length && Object.entries(choosing).every(([id, car]) => was[Number(id)] === car);
  if (!same) useLobby.setState({ choosing });
  // (never into a course that is being built, or one the room has left)
  const game = gameHolder.game;
  if (lineup && entries.length && game && game.course?.id === room!.track_id && !useApp.getState().loading) game.showLobby(entries);
}

/** A picker's choice reaching the engine (`showGarage`, `setGarageColor`) while in a room: that is browsing. */
function hook() {
  const game = gameHolder.game;
  if (!game || hooked.has(game)) return;
  hooked.add(game);
  game.on((e) => {
    if (e.type !== 'garage' || !room || !waiting()) return;
    // the garage has the scene now (the line-up comes back with `showRoomLineup`)
    lineup = false;
    look({ car: e.carId, livery: offeredPaint(e.carId, e.color) });
    publish();
  });
}
