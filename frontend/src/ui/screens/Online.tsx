import { useEffect, useRef, useState, type PointerEvent, type WheelEvent } from 'react';
import { gameHolder } from '../GameCanvas';
import { useApp } from '../../store/app';
import { useMenuInput } from '../useMenuInput';
import { CAR_SPECS, singleRatio, vehiclesFor, type CarId } from '../../game/vehicle/carSpecs';
import { traitsOf } from '../../game/vehicle/kinds';
import { COURSES, COURSE_ORDER, type CourseId } from '../../game/track/courses';
import { currentCourseId, useSettings } from '../../store/settings';
import { loadPlayer, type RoomMember, type RoomState } from '../../api/client';
import { SLOT_COLORS } from '../../game/net/RemoteRacers';
import { formatTime } from '../format';
import { sfx } from '../sfx';
import { Hint, Notice, ScreenHead } from '../kit';
import { chooseCar, createRoom, joinRoom, leaveRoom, registerName, rematch, startOnlineRace, takeBackReady, toggleReady, useOnline } from '../../store/online';
import { showRoomLineup, useLobby } from '../../store/lobby';
import { CONDITIONS } from './RaceSetup';
import { neighbourVehicle, OnlineVehicle } from '../garage/OnlineVehicle';
import type { TimeOfDay } from '../../game/render/Environment';

const MAX_PLAYERS = 5;

/** AT / MT: each player's own choice (the course and conditions are the room's); trains and the cockroach have one ratio. */
function GearboxPicker({ carId, disabled }: { carId: CarId; disabled?: boolean }) {
  const autoShift = useSettings((s) => s.autoShift);
  const pick = (auto: boolean) => {
    sfx.move();
    // in a room: the entry changed, so the 準備完了 is taken back (as with another car)
    if (auto !== autoShift) takeBackReady();
    useSettings.getState().set({ autoShift: auto });
    if (gameHolder.game) gameHolder.game.autoShift = auto;
  };
  if (singleRatio(CAR_SPECS[carId])) {
    return <div className="ol-gearbox-none">{traitsOf(CAR_SPECS[carId]).noun}は変速なし（AT/MT の選択はありません）</div>;
  }
  return (
    <div className="ol-cars ol-gearbox">
      <button className={`chip ${autoShift ? 'on' : ''}`} disabled={disabled} onClick={() => pick(true)}>AT オートマ</button>
      <button className={`chip ${!autoShift ? 'on' : ''}`} disabled={disabled} onClick={() => pick(false)}>MT マニュアル</button>
    </div>
  );
}

/** Name, car, then create a room on a course or join one with its code. */
export function OnlineLobbyScreen() {
  const { player, carId, busy, error } = useOnline();
  const go = useApp((s) => s.go);
  const [name, setName] = useState(() => loadPlayer()?.name ?? '');
  const [course, setCourse] = useState<CourseId>(currentCourseId());
  const [tod, setTod] = useState<TimeOfDay>(useSettings.getState().timeOfDay);
  const [code, setCode] = useState('');
  // the car select open over this screen (on which vehicle); its keys replace this screen's meanwhile
  const [picking, setPicking] = useState<CarId | null>(null);
  // the fighters race only at Edwards: picking another course swaps one for the first vehicle it allows
  useEffect(() => {
    if (!vehiclesFor(course).includes(useOnline.getState().carId)) chooseCar(vehiclesFor(course)[0]);
  }, [course]);
  useEffect(() => {
    const stored = loadPlayer();
    if (stored?.member && !useOnline.getState().player) useOnline.getState().set({ player: stored });
    const { carId, carColor } = useOnline.getState();
    gameHolder.game?.showGarage(carId, carColor ?? undefined);
    void gameHolder.game?.audio?.playMusic('bgm_online');
  }, []);
  useMenuInput((a) => {
    if (a === 'back') { sfx.back(); go('modes'); }
    // ← →: the car select, on the previous / next vehicle (Enter there enters it)
    if ((a === 'left' || a === 'right') && useOnline.getState().player) {
      setPicking(neighbourVehicle(course, useOnline.getState().carId, a === 'left' ? -1 : 1));
      sfx.move();
    }
  }, !picking);
  return (
    <div className="screen online-lobby">
      <ScreenHead jp="オンライン対戦" en="ONLINE BATTLE" note={`最大${MAX_PLAYERS}人・ルームコードで集まる`} />
      <div className="ol-panel stagger">
        {!player ? (
          <form className="ol-section" onSubmit={(e) => { e.preventDefault(); sfx.confirm(); void registerName(name); }}>
            <label>走り屋ネーム（16文字まで）</label>
            <p className="ol-help">ルームとランキングに表示される名前です。</p>
            <div className="ol-row">
              <input className="ol-name" autoFocus maxLength={16} value={name} placeholder="名無しの走り屋" onChange={(e) => setName(e.target.value)} />
              <button className="cta small" type="submit" disabled={busy}>決定</button>
            </div>
          </form>
        ) : (
          <>
            <div className="ol-section">
              <label>エントリー</label>
              <div className="ol-me"><b>{player.name}</b></div>
              <OnlineVehicle carId={carId} course={course} picking={picking} onPicking={setPicking} />
              <GearboxPicker carId={carId} />
            </div>
            <div className="ol-split">
              <div className="ol-section">
                <label>ルームを作る</label>
                <div className="ol-courses">
                  {COURSE_ORDER.map((id) => (
                    <button key={id} className={`chip ${id === course ? 'on' : ''}`} onClick={() => { sfx.move(); setCourse(id); }}>
                      {COURSES[id].name}
                    </button>
                  ))}
                </div>
                <div className="ol-courses ol-tod">
                  {CONDITIONS.map((c) => (
                    <button key={c.id} className={`chip ${c.id === tod ? 'on' : ''}`} onClick={() => { sfx.move(); setTod(c.id); }}>
                      {c.jp}
                    </button>
                  ))}
                </div>
                <button className="cta small ol-create" disabled={busy} onClick={() => { sfx.confirm(); void createRoom(course, tod); }}>
                  ルームを作成
                </button>
              </div>
              <form className="ol-section" onSubmit={(e) => { e.preventDefault(); sfx.confirm(); void joinRoom(code); }}>
                <label>ルームコードで参加</label>
                <div className="ol-row">
                  <input className="ol-code" maxLength={8} value={code} placeholder="ABCD" onChange={(e) => setCode(e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, ''))} />
                  <button className="cta small" type="submit" disabled={busy || code.length < 4}>参加</button>
                </div>
              </form>
            </div>
          </>
        )}
        {error && <OnlineError message={error} />}
      </div>
      <Hint items={[['lr', '車両選択']]} />
    </div>
  );
}

/** What went wrong with the server or the room, and what can be done about it. */
function OnlineError({ message }: { message: string }) {
  // (no answer, or the proxy answering for a server that is down)
  const offline = message.includes('接続できません') || /^HTTP 5\d\d$/.test(message);
  // the server's own words (a status, a validation message in English): the detail under a line of ours
  const raw = /^[\x20-\x7e]+$/.test(message);
  return (
    <Notice className="ol-error" title={offline ? 'サーバーに接続できません' : raw ? '操作を完了できませんでした' : message}>
      {offline ? '通信状態を確かめて、もう一度お試しください。ひとりで走るモードはそのまま遊べます。' : null}
      {raw && <code className="notice-code">{message}</code>}
    </Notice>
  );
}

/** The room is gone under the player (closed by its host, or lost with the connection): say so, and the way out. */
function RoomGone() {
  const go = useApp((s) => s.go);
  const error = useOnline((s) => s.error);
  const leave = () => {
    sfx.back();
    go('online');
  };
  useMenuInput((a) => {
    if (a === 'back' || a === 'confirm') leave();
  });
  return (
    <div className="screen online-room room-gone">
      <ScreenHead jp="オンライン対戦" en="ONLINE BATTLE" />
      <div className="ol-panel">
        <Notice title={error ?? 'ルームが閉じられました'}>ホストが退出したか、通信が切れました。ロビーから新しいルームを作るか、別のコードで参加できます。</Notice>
        <div className="ol-actions">
          <button className="cta" onClick={leave}>ロビーに戻る</button>
        </div>
      </div>
    </div>
  );
}

function RealtimeBadge() {
  const realtime = useOnline((s) => s.realtime);
  const label = { off: 'OFFLINE', connecting: '接続中…', live: 'LIVE', failed: '通信: ポーリング' }[realtime];
  const title = { off: 'リアルタイム通信は切れています', connecting: 'リアルタイム通信に接続しています', live: 'リアルタイム通信中', failed: 'リアルタイム通信に接続できません。ルームの状態は数秒おきに取得しています' }[realtime];
  return <span className={`rt-badge ${realtime}`} title={title}>{label}</span>;
}

/**
 * What a member is doing, as their seat's row and their vehicle's name tag say it. `tag`: shorter, and in a crowded
 * room (`tight`) only the tick of the ready ones (the tags of five vehicles would cover the vehicles behind).
 */
function MemberMark({ p, room, choosing, tag, tight }: { p: RoomMember; room: RoomState; choosing: boolean; tag?: boolean; tight?: boolean }) {
  if (!p.loaded) return <em className="loading">ロード中…</em>;
  // (looking round the car select enters nothing: a ready member stays ready, and is shown as both)
  const ready = p.ready && p.id !== room.host_id;
  if (choosing) return <><em className="choosing">選択中</em>{ready && <em className="ready">{tag || tight ? '✓' : '準備完了 ✓'}</em>}</>;
  if (p.id === room.host_id) return null;
  if (tight) return p.ready ? <em className="ready">✓</em> : null;
  return <em className={p.ready ? 'ready' : 'not-ready'}>{p.ready ? (tag ? '準備OK ✓' : '準備完了 ✓') : '準備中'}</em>;
}

/**
 * Name tags over the vehicles of the line-up: whose it is and what they are doing (the same marks as the list).
 * Placed every animation frame from the game's camera, without React state.
 */
function LobbyTags({ room, playerId, choosing }: { room: RoomState; playerId: number; choosing: Record<number, CarId> }) {
  const tags = useRef(new Map<number, HTMLDivElement>());
  useEffect(() => {
    let raf = 0;
    const at = { x: 0, y: 0 };
    const place = () => {
      const game = gameHolder.game;
      const box = tags.current.values().next().value?.parentElement;
      const w = box?.clientWidth ?? 0, h = box?.clientHeight ?? 0;
      // (sizes are read before anything is moved: no layout in the middle of the frame)
      const shown: { el: HTMLDivElement; x: number; y: number; w: number; h: number }[] = [];
      for (const [slot, el] of tags.current) {
        if (game?.lobbyTag(slot, at) && w) shown.push({ el, x: at.x * w, y: at.y * h, w: el.offsetWidth, h: el.offsetHeight });
        else el.style.visibility = 'hidden';
      }
      // vehicles side by side stand closer in the picture than their tags are wide: from the nearest one up, a tag
      // that would cover another moves above it
      shown.sort((a, b) => b.y - a.y);
      shown.forEach((t, k) => {
        for (let pass = 0; pass < 4; pass++) {
          const hit = shown.slice(0, k).find((o) => Math.abs(o.x - t.x) < (o.w + t.w) / 2 + 2 && t.y > o.y - o.h - 2 && t.y - t.h < o.y + 2);
          if (!hit) break;
          t.y = hit.y - hit.h - 2;
        }
        t.el.style.visibility = 'visible';
        t.el.style.left = `${t.x.toFixed(1)}px`;
        t.el.style.top = `${t.y.toFixed(1)}px`;
      });
      raf = requestAnimationFrame(place);
    };
    raf = requestAnimationFrame(place);
    return () => cancelAnimationFrame(raf);
  }, []);
  return (
    <div className="lobby-tags">
      {room.players.map((p) => (
        <div
          key={p.slot}
          className={`lobby-tag ${p.id === playerId ? 'me' : ''}`}
          style={{ visibility: 'hidden' }}
          ref={(el) => { if (el) tags.current.set(p.slot, el); else tags.current.delete(p.slot); }}
        >
          <i style={{ background: SLOT_COLORS[p.slot] }} />
          <b>{p.name}</b>
          <MemberMark p={p} room={room} choosing={p.id in choosing} tag tight={room.players.length > 3} />
          {p.id === room.host_id && <em className="host">HOST</em>}
        </div>
      ))}
    </div>
  );
}

/** The room: code to share, who is in (and their vehicles on the course behind), car choice, and the host's start button. */
export function OnlineRoomScreen() {
  const { room, player, carId, busy, error } = useOnline();
  const choosing = useLobby((s) => s.choosing);
  const go = useApp((s) => s.go);
  const [picking, setPicking] = useState<CarId | null>(null);
  useEffect(() => {
    void gameHolder.game?.audio?.playMusic('bgm_online');
    // the members' vehicles on the course (again after a picker that showed the garage)
    showRoomLineup();
  }, []);
  // drag on the empty part of the screen to look around the line-up, the wheel zooms (as in the car select)
  const drag = useRef<{ x: number; y: number } | null>(null);
  const [dragging, setDragging] = useState(false);
  const orbit = {
    onPointerDown: (e: PointerEvent<HTMLDivElement>) => {
      if (e.target !== e.currentTarget) return;
      e.currentTarget.setPointerCapture(e.pointerId);
      drag.current = { x: e.clientX, y: e.clientY };
      setDragging(true);
    },
    onPointerMove: (e: PointerEvent<HTMLDivElement>) => {
      if (!drag.current) return;
      gameHolder.game?.orbitGarage(e.clientX - drag.current.x, e.clientY - drag.current.y);
      drag.current = { x: e.clientX, y: e.clientY };
    },
    onPointerUp: () => {
      drag.current = null;
      setDragging(false);
    },
    onPointerCancel: () => {
      drag.current = null;
      setDragging(false);
    },
    onWheel: (e: WheelEvent<HTMLDivElement>) => {
      if (e.target === e.currentTarget) gameHolder.game?.zoomGarage(Math.exp(e.deltaY * 0.001));
    },
  };
  // a fighter picked in the lobby cannot race this room's course: the first vehicle it allows instead
  const track = room?.track_id;
  useEffect(() => {
    if (track && !vehiclesFor(track).includes(carId)) chooseCar(vehiclesFor(track)[0]);
  }, [track, carId]);
  const exit = () => {
    sfx.back();
    void leaveRoom();
    go('online');
  };
  // the race starts when the host presses start, which needs two players or more, every game showing the course
  // (`loaded`, by itself) and every guest's 準備完了 (`ready`, their button); the server checks the same
  const me = room?.players.find((p) => p.id === player?.id);
  const isHost = !!room && room.host_id === player?.id;
  const waiting = room?.status === 'waiting';
  const enough = (room?.players.length ?? 0) >= 2;
  const loading = room ? room.players.filter((p) => !p.loaded).length : 0;
  const unready = room ? room.players.filter((p) => p.id !== room.host_id && !p.ready).length : 0;
  const canStart = waiting && enough && !loading && !unready;
  const start = () => {
    if (busy) return;
    if (!canStart) return void sfx.deny();
    sfx.confirm();
    void startOnlineRace();
  };
  const ready = () => {
    if (busy || !waiting || !me?.loaded) return;
    if (me.ready) sfx.back();
    else sfx.confirm();
    void toggleReady();
  };
  useMenuInput((a) => {
    if (a === 'back') exit();
    if (a === 'confirm') (isHost ? start : ready)();
    // ← →: the car select, on the previous / next vehicle (looking is no change of car: Enter there enters it)
    if ((a === 'left' || a === 'right') && room?.status === 'waiting') {
      setPicking(neighbourVehicle(room.track_id, carId, a === 'left' ? -1 : 1));
      sfx.move();
    }
  }, !picking && !!room);
  if (!player) return null;
  if (!room) return <RoomGone />;
  const course = COURSES[room.track_id as CourseId];
  return (
    <div className={`screen online-room ${dragging ? 'orbiting' : ''}`} {...orbit}>
      {!picking && <LobbyTags room={room} playerId={player.id} choosing={choosing} />}
      <ScreenHead jp="ルーム" en="ONLINE ROOM" note={<>{course?.name ?? room.track_id}・{CONDITIONS.find((c) => c.id === room.time_of_day)?.jp ?? ''} <RealtimeBadge /></>} />
      <div className="ol-panel">
        <div className="ol-code-big">
          <small>ROOM CODE</small>
          <b>{room.code}</b>
          <span>友達にこのコードを伝えてください</span>
        </div>
        <ul className="ol-slots">
          {Array.from({ length: room.max_players }, (_, slot) => {
            const p = room.players.find((m) => m.slot === slot);
            return (
              <li key={slot} className={p ? (p.id === player.id ? 'me' : '') : 'empty'}>
                <i style={{ background: SLOT_COLORS[slot] }} />
                {p ? (
                  <>
                    <b>{p.name}</b>
                    <span>{CAR_SPECS[choosing[p.id] ?? p.car_id].name}</span>
                    <MemberMark p={p} room={room} choosing={p.id in choosing} />
                    {p.id === room.host_id && <em className="host">HOST</em>}
                    {p.id === player.id && <em className="you">YOU</em>}
                  </>
                ) : (
                  <span className="wait">参加を待っています…</span>
                )}
              </li>
            );
          })}
        </ul>
        <OnlineVehicle carId={carId} course={room.track_id} disabled={room.status !== 'waiting'} picking={picking} onPicking={setPicking} room />
        <GearboxPicker carId={carId} disabled={room.status !== 'waiting'} />
        <div className="ol-actions">
          {isHost ? (
            <button className="cta ol-start" disabled={busy || !canStart} onClick={start}>
              {!enough ? '2人以上でスタートできます' : loading ? `読み込み待ち… あと${loading}人` : unready ? `準備完了待ち… あと${unready}人` : 'レース開始'}
            </button>
          ) : (
            <>
              <button className={`cta ol-ready ${me?.ready ? 'on' : ''}`} disabled={busy || !waiting || !me?.loaded} onClick={ready}>
                {!me?.loaded ? 'コースを読み込んでいます…' : me.ready ? '準備完了を取り消す' : '準備完了'}
              </button>
              {me?.ready && <div className="ol-waiting">ホストのスタートを待っています…</div>}
            </>
          )}
          <button className="cta small ghost ol-leave" onClick={exit}>退出</button>
        </div>
        {error && <OnlineError message={error} />}
      </div>
      <Hint items={[['lr', '車両選択'], ['drag', '視点'], ['ok', isHost ? 'スタート' : me?.ready ? '準備完了を取り消す' : '準備完了']]} />
    </div>
  );
}

/** Live results: finishers by time; the others show as still racing or retired. */
export function OnlineResultsScreen() {
  const { room, player, busy, error } = useOnline();
  const result = useApp((s) => s.result);
  const go = useApp((s) => s.go);
  useEffect(() => {
    // after the finish jingle
    void gameHolder.game?.audio?.playMusic('bgm_results', { delay: 4.5 });
  }, []);
  useMenuInput((a) => {
    if (a === 'back') { sfx.back(); void leaveRoom(); go('modes'); }
    // the host's Enter is the rematch button
    if (a === 'confirm' && room && player && room.host_id === player.id && !busy) { sfx.confirm(); void rematch(); }
  }, !!room);
  if (!player) return null;
  if (!room) return <RoomGone />;
  const isHost = room.host_id === player.id;
  const rows = [...room.players].sort((a, b) => (a.finish_ms ?? Infinity) - (b.finish_ms ?? Infinity));
  const winner = rows[0]?.finish_ms !== null ? rows[0] : null;
  return (
    <div className="screen online-results" data-wipe="none">
      <ScreenHead jp="リザルト" en="ONLINE BATTLE RESULT" note={COURSES[room.track_id as CourseId]?.name} />
      <div className="ol-panel">
        <div className={`ol-headline${winner?.id === player.id ? ' mine' : ''}`}>{winner ? (winner.id === player.id ? 'WINNER!' : `${winner.name} の勝利`) : '集計中…'}</div>
        <ol className="ol-standings stagger">
          {rows.map((p, k) => (
            <li key={p.id} className={p.id === player.id ? 'me' : ''}>
              <span className="pos">{p.finish_ms !== null ? k + 1 : '-'}</span>
              <i style={{ background: SLOT_COLORS[p.slot] }} />
              <b>{p.name}</b>
              <span className="car">{CAR_SPECS[p.car_id].name}</span>
              <span className="time">{p.finish_ms !== null ? formatTime(p.finish_ms) : room.status === 'finished' ? 'DNF' : '走行中…'}</span>
            </li>
          ))}
        </ol>
        {result && <div className="ol-mine">あなたのタイム <b>{formatTime(result.timeMs)}</b>　最高速 {Math.round(result.topSpeedKmh)} km/h</div>}
        <div className="ol-actions">
          {isHost ? (
            <button className="cta" disabled={busy} onClick={() => { sfx.confirm(); void rematch(); }}>もう一度走る</button>
          ) : (
            <div className="ol-waiting">ホストの再戦を待っています…</div>
          )}
          <button className="cta small ghost" onClick={() => { sfx.back(); void leaveRoom(); go('modes'); }}>ルームを出る</button>
        </div>
        {error && <OnlineError message={error} />}
      </div>
      {isHost && <Hint items={[['ok', 'もう一度走る']]} />}
    </div>
  );
}
