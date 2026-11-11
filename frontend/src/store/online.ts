import { create } from 'zustand';
import Pusher, { type PresenceChannel } from 'pusher-js';
import { api, ApiError, type RoomState, type StoredPlayer } from '../api/client';
import { gameHolder } from '../ui/GameCanvas';
import { useApp } from './app';
import { useSettings } from './settings';
import { parseImpairment, type NetTransport } from '../game/net/transport';
import type { CarId } from '../game/vehicle/carSpecs';
import type { CourseId } from '../game/track/courses';
import type { Game } from '../game/Game';
import type { TimeOfDay } from '../game/render/Environment';

/**
 * Online battle session (UI side). Lobby actions go through the Laravel API; while racing, car
 * states travel as client events on the room's presence channel (Laravel Reverb, Pusher protocol).
 * If the socket is unavailable the room state is still kept up to date by polling.
 */
interface OnlineState {
  player: StoredPlayer | null;
  room: RoomState | null;
  carId: CarId;
  realtime: 'off' | 'connecting' | 'live' | 'failed';
  error: string | null;
  busy: boolean;
  set: (patch: Partial<OnlineState>) => void;
}

export const useOnline = create<OnlineState>((set) => ({
  player: null,
  room: null,
  carId: 'hayate',
  realtime: 'off',
  error: null,
  busy: false,
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

export function chooseCar(carId: CarId) {
  st().set({ carId });
  const room = st().room;
  gameHolder.game?.showGarage(carId);
  if (room && room.status !== 'racing') {
    void run(async () => applyRoom(await api.rooms.setCar(onlinePlayer(), room.code, carId)));
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
    const room = await timed(() => api.rooms.create(onlinePlayer(), trackId, timeOfDay, st().carId));
    await enterRoom(room);
  });
}

export function joinRoom(code: string) {
  return run(async () => {
    const room = await timed(() => api.rooms.join(onlinePlayer(), code.trim().toUpperCase(), st().carId));
    await enterRoom(room);
  });
}

export function startOnlineRace() {
  const room = st().room;
  if (!room) return;
  return run(async () => applyRoom(await timed(() => api.rooms.start(onlinePlayer(), room.code))));
}

export function rematch() {
  const room = st().room;
  if (!room) return;
  return run(async () => applyRoom(await api.rooms.rematch(onlinePlayer(), room.code)));
}

export async function leaveRoom() {
  const room = st().room;
  stopLoops();
  if (channel && pusher) pusher.unsubscribe(channel.name);
  channel = null;
  pusher?.disconnect();
  pusher = null;
  st().set({ room: null, realtime: 'off', error: null });
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
  const app = useApp.getState();
  const game = gameHolder.game;
  st().set({ room });
  const me = room.players.find((p) => p.id === st().player?.id);
  if (me) st().set({ carId: me.car_id });
  useSettings.getState().set({ courseId: room.track_id as CourseId });
  if (game && game.course.id !== room.track_id) {
    app.set({ loading: { progress: 0, label: '' } });
    app.go('loading');
    await game.switchCourse(room.track_id as CourseId);
    app.set({ loading: null });
  }
  // everyone races in the conditions the host chose
  if (game && game.timeOfDay !== room.time_of_day) game.applyTimeOfDay(room.time_of_day);
  game?.showGarage(st().carId);
  useApp.getState().set({ mode: 'online' });
  useApp.getState().go('onlineRoom');
  hookGame();
  // after loading: building a course blocks the page long enough for the socket to give up on its first try
  connectRealtime(room.code);
  startPolling();
  applyRoom(room);
  if (st().room?.code === room.code) applyRoom(await api.rooms.setLoaded(onlinePlayer(), room.code));
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
        if (s.current === 'unavailable' || s.current === 'failed') st().set({ realtime: 'failed' });
      });
      channel = pusher.subscribe(`presence-room.${code}`) as PresenceChannel;
      channel.bind('pusher:subscription_succeeded', () => st().set({ realtime: 'live' }));
      channel.bind('pusher:subscription_error', () => st().set({ realtime: 'failed' }));
      channel.bind('room.updated', (data: { room: RoomState }) => applyRoom(data.room));
      bindStates(channel);
    })
    .catch(() => st().set({ realtime: 'failed' }));
}

/** Reacts to a new room state, whichever way it arrived (HTTP reply, broadcast or poll). */
export function applyRoom(room: RoomState) {
  const prev = st().room;
  if (!prev || prev.code !== room.code) return;
  // a reply overtaken by a newer state (a poll sent before the 準備完了 button was pressed) would undo it on screen
  if (room.server_time_ms < prev.server_time_ms) return;
  st().set({ room });
  const app = useApp.getState();
  if (room.status === 'racing' && room.start_at_ms && room.race_no > startedRace) beginRace(room);
  if (room.status === 'waiting' && (app.screen === 'onlineResults' || app.screen === 'race')) {
    // rematch: back to the lobby of the same room
    stopSending();
    gameHolder.game?.showGarage(st().carId);
    app.set({ paused: false });
    app.go('onlineRoom');
  }
  // players who left mid-race disappear from the road
  const game = gameHolder.game;
  if (game && room.status !== 'waiting') {
    for (const r of game.remotes.standings()) if (!room.players.some((p) => p.id === r.id)) game.remotes.removePeer(r.id);
  }
}

function beginRace(room: RoomState) {
  const game = gameHolder.game;
  const player = st().player;
  const me = room.players.find((p) => p.id === player?.id);
  if (!game || !player || !me || !room.start_at_ms) return;
  startedRace = room.race_no;
  if (game.timeOfDay !== room.time_of_day) game.applyTimeOfDay(room.time_of_day);
  const startAt = performance.now() + (room.start_at_ms - (Date.now() + clockOffset));
  const peers = room.players.filter((p) => p.id !== me.id).map((p) => ({ id: p.id, name: p.name, carId: p.car_id, slot: p.slot }));
  game.initAudio();
  game.onlineSelfId = me.id;
  game.startRace({ mode: 'online', carId: me.car_id, online: { startAt, slot: me.slot, peers } });
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
    const me = room.players.find((p) => p.id === player.id);
    // the room's course is on screen here: report it loaded if the server has not got it (failed call, rejoin)
    const ask = me && !me.loaded && gameHolder.game?.course.id === room.track_id ? api.rooms.setLoaded(player, room.code) : api.rooms.get(player, room.code);
    void timed(() => ask)
      .then(applyRoom)
      .catch((e) => {
        if (e instanceof ApiError && (e.status === 404 || e.status === 403)) {
          st().set({ error: 'ルームが閉じられました' });
          void leaveRoom();
        }
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
