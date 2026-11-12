import { create } from 'zustand';
import Pusher, { type PresenceChannel } from 'pusher-js';
import { api, ApiError, type RoomSetup, type RoomState, type StoredPlayer } from '../api/client';
import { gameHolder } from '../ui/GameCanvas';
import { useApp } from './app';
import { useSettings } from './settings';
import { parseImpairment, type NetTransport } from '../game/net/transport';
import { hideRoomLineup, lobbyChannel, lobbyRoom, previewCar, showRoomLineup } from './lobby';
import { heardLoad, LoadTeller, nextWaits, readLoad, type Waiting } from '../game/net/roomWait';
import type { CarId } from '../game/vehicle/carSpecs';
import type { CourseId } from '../game/track/courses';
import type { Game } from '../game/Game';
import type { TimeOfDay } from '../game/render/Environment';

/**
 * Online battle session (UI side). Lobby actions go through the Laravel API; while racing, car
 * states travel as client events on the room's presence channel (Laravel Reverb, Pusher protocol).
 * If the socket is unavailable the room state is still kept up to date by polling.
 *
 * The room's course and its time & weather are the host's to change while the room waits (`changeRoom`, or with
 * the rematch). Every game follows the room (`followRoom`): another course is built behind the loading screen,
 * the line-up comes back on it and the game reports `loaded` again; other conditions change the scene at once.
 */

/** What the host changed, for the members to read once (`n` tells one notice from the next). */
export interface RoomNotice {
  n: number;
  course: CourseId | null;
  conditions: TimeOfDay | null;
  /** this player's vehicle may not race on the new course: what it was, and what the server entered instead */
  replaced: [CarId, CarId] | null;
  /** this player's 準備完了 was taken back by the change */
  unready: boolean;
}

/** why a player is out of a room that goes on without them (`error`, read by the room screen) */
export const ROOM_CLOSED = 'ルームが閉じられました';
export const ROOM_REMOVED = 'ルームから外れました';

interface OnlineState {
  player: StoredPlayer | null;
  room: RoomState | null;
  carId: CarId;
  /** the paint picked for it (null: none, the seat's colour) */
  carColor: string | null;
  realtime: 'off' | 'connecting' | 'live' | 'failed';
  error: string | null;
  busy: boolean;
  notice: RoomNotice | null;
  /** why this game is building a course for the room (the loading screen says it); null: it is not */
  loadingFor: 'join' | 'change' | null;
  /** the members whose games are loading the room's course: since when, how far (game/net/roomWait.ts) */
  waits: Record<number, Waiting>;
  /** the members on the room's channel (null: not known here, no live connection) */
  present: number[] | null;
  set: (patch: Partial<OnlineState>) => void;
}

export const useOnline = create<OnlineState>((set) => ({
  player: null,
  room: null,
  carId: 'hayate',
  carColor: null,
  realtime: 'off',
  error: null,
  busy: false,
  notice: null,
  loadingFor: null,
  waits: {},
  present: null,
  set: (patch) => set(patch),
}));

/** server clock − local clock (ms), taken from the HTTP exchange with the shortest round trip */
let clockOffset = 0;
let bestRtt = Infinity;
let pusher: Pusher | null = null;
let channel: PresenceChannel | null = null;
let pollTimer = 0;
let startedRace = 0;
const hookedGames = new WeakSet<Game>();
/** the game is building a course for the room (`loadRoomCourse`) */
let following = false;
let reporting = false;
let noticeNo = 0;
/** conditions the host is looking at in the room's picker: this game shows them, the room's wait */
let preview: TimeOfDay | null = null;
const teller = new LoadTeller();

const st = () => useOnline.getState();
const message = (e: unknown) => (e instanceof ApiError ? e.message : 'サーバーに接続できません');

async function timed(call: () => Promise<RoomState>) {
  const t0 = Date.now();
  const room = await call();
  const t1 = Date.now();
  if (t1 - t0 < bestRtt) {
    bestRtt = t1 - t0;
    clockOffset = room.server_time_ms - (t0 + t1) / 2;
  }
  return room;
}

async function run(action: () => Promise<void>) {
  if (st().busy) return;
  st().set({ busy: true, error: null });
  try {
    await action();
  } catch (e) {
    st().set({ error: message(e) });
  } finally {
    st().set({ busy: false });
  }
}

/** A call that must not be dropped because another is under way (`run` lets one through at a time). */
async function idle() {
  for (let k = 0; k < 40 && st().busy; k++) await new Promise((r) => setTimeout(r, 120));
}

export function onlinePlayer() {
  const p = st().player;
  if (!p) throw new ApiError('名前を登録してください', 0);
  return p;
}

export function registerName(name: string) {
  return run(async () => {
    const p = await api.ensurePlayer(name.trim() || '名無しの走り屋');
    st().set({ player: p });
  });
}

/** The entry's vehicle and its paint (null: none picked, the seat's colour). */
export function chooseCar(carId: CarId, color: string | null = null) {
  st().set({ carId, carColor: color });
  const room = st().room;
  if (!room) {
    gameHolder.game?.showGarage(carId, color ?? undefined);
    return;
  }
  // in a room the line-up shows it in the player's seat (store/lobby.ts): 選択中 until the server has confirmed it
  if (room.status === 'waiting') previewCar(carId, color ?? undefined);
  if (room.status !== 'racing') void sendCar();
}

/**
 * The chosen car and paint to the server. A car picked while another call is under way (←→ pressed twice) follows
 * once that call is done: it used to be dropped, and the room raced the car before it.
 */
let sendingCar = false;
async function sendCar() {
  if (sendingCar) return;
  sendingCar = true;
  try {
    for (let tries = 0; tries < 40; tries++) {
      const room = st().room;
      const want = st().carId, color = st().carColor;
      const me = self();
      if (!room || room.status === 'racing' || (me?.car_id === want && (me.color ?? null) === color)) return;
      if (st().busy) await new Promise((r) => setTimeout(r, 120));
      else {
        await run(async () => applyRoom(await api.rooms.setCar(onlinePlayer(), room.code, want, color)));
        if (st().error) return;
      }
    }
  } finally {
    sendingCar = false;
  }
}

const self = () => st().room?.players.find((p) => p.id === st().player?.id);

/**
 * The 準備完了 button (guests; the host's is the start button): on, or taken back. Only once the course is loaded:
 * the server refuses it before. Another car takes it back (server side).
 */
export function toggleReady() {
  const room = st().room;
  const me = self();
  if (!room || !me || room.status !== 'waiting' || !me.loaded) return;
  return run(async () => applyRoom(await api.rooms.setReady(onlinePlayer(), room.code, !me.ready)));
}

/** The player changed something of their entry the server does not see (AT/MT): not ready any more. */
export function takeBackReady() {
  const room = st().room;
  const player = st().player;
  if (!room || !player || room.status !== 'waiting' || !self()?.ready) return;
  void api.rooms.setReady(player, room.code, false).then(applyRoom).catch(() => undefined);
}

export function createRoom(trackId: CourseId, timeOfDay: TimeOfDay) {
  return run(async () => {
    const room = await timed(() => api.rooms.create(onlinePlayer(), trackId, timeOfDay, st().carId, st().carColor));
    await enterRoom(room);
  });
}

export function joinRoom(code: string) {
  return run(async () => {
    const room = await timed(() => api.rooms.join(onlinePlayer(), code.trim().toUpperCase(), st().carId, st().carColor));
    await enterRoom(room);
  });
}

export function startOnlineRace() {
  const room = st().room;
  if (!room) return;
  return run(async () => applyRoom(await timed(() => api.rooms.start(onlinePlayer(), room.code))));
}

/** The host: back to the waiting room for another race; `to`: on another course (or in other conditions) at once. */
export function rematch(to: RoomSetup = {}) {
  const room = st().room;
  if (!room) return;
  return run(async () => applyRoom(await api.rooms.rematch(onlinePlayer(), room.code, to)));
}

/**
 * The host changes the room's course and / or its time & weather (only while it waits; the server checks both).
 * Sent once, when the choice is made: every game loads a new course, and everyone's 準備完了 goes back.
 */
export async function changeRoom(to: RoomSetup) {
  const room = st().room;
  if (!room || room.status !== 'waiting') return;
  // (what the room has already is no change: nothing to send, nobody's ready to take back)
  if ((to.track_id ?? room.track_id) === room.track_id && (to.time_of_day ?? room.time_of_day) === room.time_of_day) return;
  await idle();
  await run(async () => applyRoom(await api.rooms.change(onlinePlayer(), room.code, to)));
}

/**
 * The host looks through the conditions in the room's picker: this game shows them, nothing is sent (the others'
 * scenes change when the choice is made). Null: the room's own again.
 */
export function previewConditions(tod: TimeOfDay | null) {
  preview = tod;
  const game = gameHolder.game;
  const want = tod ?? st().room?.time_of_day;
  if (game && want && !following && game.timeOfDay !== want) game.applyTimeOfDay(want);
}

/** The host's choice of conditions: the scene keeps showing it while the server is told (no flick back in between). */
export async function chooseConditions(tod: TimeOfDay) {
  previewConditions(tod);
  await changeRoom({ time_of_day: tod });
  previewConditions(null);
}

/** The host takes a member out of the waiting room (one whose game does not finish loading, or who is gone). */
export async function kickMember(id: number) {
  const room = st().room;
  if (!room || room.status !== 'waiting' || room.host_id !== st().player?.id || id === room.host_id) return;
  await idle();
  await run(async () => applyRoom(await api.rooms.kick(onlinePlayer(), room.code, id)));
}

export function dismissRoomNotice() {
  if (st().notice) st().set({ notice: null });
}

/** `why`: the room goes on without this player (`ROOM_CLOSED`, `ROOM_REMOVED`): the room screen says it. */
export async function leaveRoom(why: string | null = null) {
  const room = st().room;
  stopLoops();
  preview = null;
  lobbyRoom(null, null);
  // (closing the connection takes the player out of the room's channel. An unsubscribe before it never got there:
  // pusher-js sends a tick later, on the socket that is closing by then, and the browser logs an error)
  channel = null;
  pusher?.disconnect();
  pusher = null;
  st().set({ room: null, realtime: 'off', error: why, notice: null, waits: {}, present: null });
  gameHolder.game?.remotes.clear();
  // back to the player's own conditions
  const tod = useSettings.getState().timeOfDay;
  if (room && gameHolder.game && gameHolder.game.timeOfDay !== tod) gameHolder.game.applyTimeOfDay(tod);
  if (room && st().player) await api.rooms.leave(st().player!, room.code).catch(() => undefined);
}

/**
 * The world must show the room's course before anyone can start: the server lets the host start only once
 * every member has reported `loaded` (sent here after loading, and again by the poll if that failed) and every
 * guest has pressed 準備完了 (`toggleReady`), which the server takes only from a loaded game.
 */
async function enterRoom(room: RoomState) {
  const game = gameHolder.game;
  st().set({ room, notice: null, waits: nextWaits({}, room.players, Date.now()), present: null });
  const me = room.players.find((p) => p.id === st().player?.id);
  if (me) st().set({ carId: me.car_id, carColor: me.color ?? null });
  hookGame();
  await loadRoomCourse('join');
  // everyone races in the conditions the host chose
  if (game && game.timeOfDay !== room.time_of_day) game.applyTimeOfDay(room.time_of_day);
  // the members' vehicles on the course (store/lobby.ts)
  lobbyRoom(room, st().player?.id ?? null);
  showRoomLineup();
  useApp.getState().set({ mode: 'online' });
  useApp.getState().go('onlineRoom');
  // after loading: building a course blocks the page long enough for the socket to give up on its first try
  connectRealtime(room.code);
  startPolling();
  // (a room that changed while the course was being built: the report's answer tells, and the game follows)
  applyRoom(room);
}

/**
 * Builds the room's course behind the loading screen, when the game shows another one; again if the host has moved
 * on meanwhile (the room's course at the end of a load is the one that counts). Nothing else touches the scene
 * while this runs (`following`): no line-up, no conditions, no report.
 */
async function loadRoomCourse(why: 'join' | 'change') {
  const game = gameHolder.game;
  if (!game || following) return;
  following = true;
  try {
    for (let room = st().room; room && game.course.id !== room.track_id; room = st().room) {
      const id = room.track_id as CourseId;
      // (the shell and the loading screen name the course from the settings)
      useSettings.getState().set({ courseId: id });
      hideRoomLineup();
      const app = useApp.getState();
      st().set({ loadingFor: why });
      app.set({ loading: { progress: 0, label: '' }, paused: false });
      if (app.screen !== 'loading') app.go('loading');
      teller.reset();
      tellLoad(0);
      // the loading screen gets its frame before the build takes the main thread
      await new Promise((r) => setTimeout(r, 50));
      await game.switchCourse(id);
    }
  } finally {
    following = false;
    st().set({ loadingFor: null });
    useApp.getState().set({ loading: null });
    const room = st().room;
    if (room) useSettings.getState().set({ courseId: room.track_id as CourseId });
  }
}

/**
 * The game follows the room while it waits: its course (built anew when the host picked another: `loaded` was
 * taken back by the server and is reported again here), its conditions, and the line-up on the course.
 */
async function followRoom() {
  const game = gameHolder.game;
  const room = st().room;
  if (!game || !room || following || room.status !== 'waiting') return;
  if (game.course.id !== room.track_id) {
    await loadRoomCourse('change');
    const app = useApp.getState();
    const now = st().room;
    // (the loading screen is left in any case: for the room, or for the word that it is gone)
    if (now?.status === 'waiting') showRoomLineup();
    if (app.screen === 'loading') app.go('onlineRoom');
    if (!now) return;
  }
  syncConditions();
  void reportLoaded();
}

/** Everyone races in the conditions the host chose: the scene changes with the room (no load needed for that). */
function syncConditions() {
  const game = gameHolder.game;
  const room = st().room;
  if (!game || !room || following || preview || room.status !== 'waiting') return;
  if (game.timeOfDay !== room.time_of_day) game.applyTimeOfDay(room.time_of_day);
}

/** Tells the server that this game shows the room's course, when it does and the server does not know. */
async function reportLoaded() {
  const game = gameHolder.game;
  const room = st().room;
  const player = st().player;
  const me = self();
  if (reporting || following || !game || !room || !player || !me || me.loaded || game.course.id !== room.track_id) return;
  reporting = true;
  try {
    applyRoom(await timed(() => api.rooms.setLoaded(player, room.code, room.track_id)));
  } catch (e) {
    // (the poll asks again; a room that is gone is its to tell)
    if (!(e instanceof ApiError)) throw e;
  } finally {
    reporting = false;
  }
}

/** How far this game's load has come, to the others (`client-load`; nothing without a live channel). */
function tellLoad(progress: number) {
  const m = teller.tell(progress, performance.now());
  if (m && channel?.subscribed && channel.pusher.connection.state === 'connected') channel.trigger('client-load', m);
}

/** Who is on the room's channel (a member who is not has closed the game or lost the connection). */
function readPresence() {
  const ids: number[] = [];
  channel?.members.each((m: { id: string }) => ids.push(Number(m.id)));
  st().set({ present: channel?.subscribed ? ids : null });
}

function connectRealtime(code: string) {
  if (pusher) return;
  st().set({ realtime: 'connecting' });
  void api
    .realtime()
    .then((info) => {
      if (!info.enabled || !info.key || st().room?.code !== code) {
        st().set({ realtime: 'failed' });
        return;
      }
      const port = Number(location.port || (location.protocol === 'https:' ? 443 : 80));
      pusher = new Pusher(info.key, {
        cluster: 'local',
        wsHost: location.hostname,
        wsPort: port,
        wssPort: port,
        forceTLS: location.protocol === 'https:',
        enabledTransports: ['ws', 'wss'],
        disableStats: true,
        channelAuthorization: {
          endpoint: '/api/broadcasting/auth',
          transport: 'ajax',
          customHandler: (params, callback) => {
            api
              .channelAuth(onlinePlayer(), params.socketId, params.channelName)
              .then((auth) => callback(null, auth))
              .catch((e) => callback(e instanceof Error ? e : new Error(String(e)), null));
          },
        },
      });
      pusher.connection.bind('state_change', (s: { current: string }) => {
        if (s.current === 'connected') st().set({ realtime: channel?.subscribed ? 'live' : 'connecting' });
        if (s.current === 'unavailable' || s.current === 'failed') st().set({ realtime: 'failed', present: null });
      });
      channel = pusher.subscribe(`presence-room.${code}`) as PresenceChannel;
      channel.bind('pusher:subscription_succeeded', () => {
        st().set({ realtime: 'live' });
        readPresence();
      });
      channel.bind('pusher:subscription_error', () => st().set({ realtime: 'failed', present: null }));
      channel.bind('pusher:member_added', readPresence);
      channel.bind('pusher:member_removed', readPresence);
      channel.bind('room.updated', (data: { room: RoomState }) => applyRoom(data.room));
      // how far a member's game has come with the course (game/net/roomWait.ts)
      channel.bind('client-load', (data: unknown, meta?: { user_id?: string }) => {
        const id = Number(meta?.user_id);
        const pct = readLoad(data);
        if (id && pct !== null && st().waits[id]) st().set({ waits: heardLoad(st().waits, id, pct, Date.now()) });
      });
      bindStates(channel);
      lobbyChannel(channel);
    })
    .catch(() => st().set({ realtime: 'failed' }));
}

/** Reacts to a new room state, whichever way it arrived (HTTP reply, broadcast or poll). */
export function applyRoom(room: RoomState) {
  const prev = st().room;
  if (!prev || prev.code !== room.code) return;
  // a reply overtaken by a newer state (a poll sent before the 準備完了 button was pressed) would undo it on screen
  if (room.server_time_ms < prev.server_time_ms) return;
  const selfId = st().player?.id ?? null;
  // taken out (by the host, or as one whose connection was gone): the room goes on without this player
  if (selfId !== null && !room.players.some((p) => p.id === selfId)) {
    void leaveRoom(ROOM_REMOVED);
    return;
  }
  st().set({ room, waits: nextWaits(st().waits, room.players, Date.now()) });
  announce(prev, room);
  lobbyRoom(room, selfId);
  const app = useApp.getState();
  if (room.status === 'racing' && room.start_at_ms && room.race_no > startedRace) beginRace(room);
  if (room.status === 'waiting' && (app.screen === 'onlineResults' || app.screen === 'race')) {
    // rematch: back to the lobby of the same room
    stopSending();
    showRoomLineup();
    app.set({ paused: false });
    app.go('onlineRoom');
  }
  // players who left mid-race disappear from the road
  const game = gameHolder.game;
  if (game && room.status !== 'waiting') {
    for (const r of game.remotes.standings()) if (!room.players.some((p) => p.id === r.id)) game.remotes.removePeer(r.id);
  }
  if (room.status === 'waiting') void followRoom();
}

/**
 * The host changed the room's course or conditions: a notice for the members (why their game starts loading, why
 * their 準備完了 is gone). The host reads it only when it cost them their own vehicle.
 */
function announce(prev: RoomState, room: RoomState) {
  const course = prev.track_id !== room.track_id;
  const conditions = prev.time_of_day !== room.time_of_day;
  if (!course && !conditions) return;
  const selfId = st().player?.id;
  const was = prev.players.find((p) => p.id === selfId);
  const me = room.players.find((p) => p.id === selfId);
  // the new course does not offer this player's vehicle: the server entered its first one, which is the entry now
  let replaced: [CarId, CarId] | null = null;
  if (course && was && me && was.car_id !== me.car_id && st().carId === was.car_id) {
    replaced = [was.car_id, me.car_id];
    st().set({ carId: me.car_id, carColor: me.color ?? null });
  }
  if (room.host_id === selfId && !replaced) return;
  st().set({ notice: { n: ++noticeNo, course: course ? (room.track_id as CourseId) : null, conditions: conditions ? room.time_of_day : null, replaced, unready: !!was?.ready && !me?.ready } });
}

function beginRace(room: RoomState) {
  const game = gameHolder.game;
  const player = st().player;
  const me = room.players.find((p) => p.id === player?.id);
  if (!game || !player || !me || !room.start_at_ms) return;
  startedRace = room.race_no;
  if (game.timeOfDay !== room.time_of_day) game.applyTimeOfDay(room.time_of_day);
  const startAt = performance.now() + (room.start_at_ms - (Date.now() + clockOffset));
  // (every vehicle in the paint its member picked: the game draws it if the vehicle offers it, else the seat's colour)
  const peers = room.players.filter((p) => p.id !== me.id).map((p) => ({ id: p.id, name: p.name, carId: p.car_id, slot: p.slot, color: p.color ?? null }));
  game.initAudio();
  game.onlineSelfId = me.id;
  game.startRace({ mode: 'online', carId: me.car_id, color: me.color ?? undefined, online: { startAt, slot: me.slot, peers } });
  useApp.getState().set({ mode: 'online', carId: me.car_id, screen: 'race', result: null, paused: false });
  startSending();
}

// ---- car states: the transport the engine's NetLink sends and receives on

const STATE_EVENT = 'client-state';

/**
 * Car states as client events on the room's presence channel: Reverb passes each on to the other members with
 * the sender's player id (`user_id`, set by the server from the channel auth, so nobody can speak for another).
 * This object is all the engine sees of the socket (`NetTransport`): a direct connection would be another one.
 */
const relay: NetTransport = {
  get ready() {
    return !!channel?.subscribed;
  },
  send(data) {
    channel?.trigger(STATE_EVENT, data);
  },
  onReceive: null,
};

function bindStates(ch: PresenceChannel) {
  ch.bind(STATE_EVENT, (data: number[], meta?: { user_id?: string }) => {
    const id = Number(meta?.user_id);
    if (id) relay.onReceive?.(id, data);
  });
}

/** The game sends its car's state itself, after its physics (`Game.step`), on whatever it is attached to. */
function startSending() {
  const game = gameHolder.game;
  if (!game) return;
  // testing: `?netsim=50,20,2` makes this client's network worse, `?netmode=buffered` draws the peers in the past
  const query = new URLSearchParams(location.search);
  const worse = parseImpairment(query.get('netsim'));
  if (worse && !game.net.impaired) game.net.impair(worse);
  if (query.get('netmode') === 'buffered') game.net.setMode('buffered');
  game.net.attach(relay);
}

function stopSending() {
  gameHolder.game?.net.attach(null);
}

function startPolling() {
  if (pollTimer) return;
  pollTimer = window.setInterval(() => {
    const room = st().room;
    const player = st().player;
    if (!room || !player) return;
    const screen = useApp.getState().screen;
    // racing state comes from the cars themselves; the lobby and results need the room
    if (screen !== 'onlineRoom' && screen !== 'onlineResults') return;
    // (the answer goes through `applyRoom`, which reports the course loaded if the server has not got it: a failed
    // call, a rejoin)
    void timed(() => api.rooms.get(player, room.code))
      .then(applyRoom)
      .catch((e) => {
        // (403: no member any more, taken out while the connection was away)
        if (e instanceof ApiError && (e.status === 404 || e.status === 403)) void leaveRoom(e.status === 403 ? ROOM_REMOVED : ROOM_CLOSED);
      });
  }, 2500);
}

function stopLoops() {
  stopSending();
  if (pollTimer) clearInterval(pollTimer);
  pollTimer = 0;
  startedRace = 0;
}

/** Posts the local finish time once the car crosses the line. */
function hookGame() {
  const game = gameHolder.game;
  if (!game || hookedGames.has(game)) return;
  hookedGames.add(game);
  game.on((e) => {
    // the course being built for the room: how far, to the others
    if (e.type === 'loading' && following) tellLoad(e.progress);
    if (e.type !== 'finish' || e.result.mode !== 'online') return;
    const room = st().room;
    const player = st().player;
    if (!room || !player) return;
    void api.rooms
      .finish(player, room.code, room.race_no, e.result.timeMs)
      .then(applyRoom)
      .catch((err) => st().set({ error: message(err) }));
  });
}
