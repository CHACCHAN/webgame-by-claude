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
import { Hint, Notice, ScreenHead, type HintKey } from '../kit';
import { changeRoom, chooseCar, chooseConditions, createRoom, joinRoom, kickMember, leaveRoom, previewConditions, registerName, rematch, ROOM_REMOVED, startOnlineRace, takeBackReady, toggleReady, useOnline } from '../../store/online';
import { showRoomLineup, useLobby } from '../../store/lobby';
import { stalled, startHold } from '../../game/net/roomWait';
import { CONDITIONS, ConditionsSelect } from './RaceSetup';
import { CourseSelect } from './Menus';
import { useOverScreen } from '../Shell';
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
        <Notice title={error ?? 'ルームが閉じられました'}>
          {error === ROOM_REMOVED
            ? 'ホストがメンバーから外したか、通信が切れていました。ルームが続いていれば、同じコードでもう一度参加できます。'
            : 'ホストが退出したか、通信が切れました。ロビーから新しいルームを作るか、別のコードで参加できます。'}
        </Notice>
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
 * Loading the course comes before everything else: it is what the whole room waits for. `gone`: not on the room's
 * channel any more (the game closed, the connection lost).
 */
function MemberMark({ p, room, choosing, tag, tight, gone }: { p: RoomMember; room: RoomState; choosing: boolean; tag?: boolean; tight?: boolean; gone?: boolean }) {
  if (!p.loaded) return <em className="loading"><i className="busy-glyph" aria-hidden />{tag && tight ? '' : '読み込み中'}</em>;
  if (gone) return <em className="gone">切断</em>;
  // (looking round the car select enters nothing: a ready member stays ready, and is shown as both)
  const ready = p.ready && p.id !== room.host_id;
  if (choosing) return <><em className="choosing">選択中</em>{ready && <em className="ready">{tag || tight ? '✓' : '準備完了 ✓'}</em>}</>;
  if (p.id === room.host_id) return null;
  if (tight) return p.ready ? <em className="ready">✓</em> : null;
  return <em className={p.ready ? 'ready' : 'not-ready'}>{p.ready ? (tag ? '準備OK ✓' : '準備完了 ✓') : '準備中'}</em>;
}

/** The names of members in a line of text. */
const names = (who: readonly { name: string }[]) => who.map((p) => p.name).join('、');

/** One of the room's two settings: what it is, and for the host the way to change it. */
function SetupCell({ label, value, hint, onChange }: { label: string; value: string; hint: HintKey; onChange?: () => void }) {
  const body = (
    <>
      <span className="ol-set-name">
        <small>{label}</small>
        <b>{value}</b>
      </span>
      {onChange && <em>変更 ▶</em>}
    </>
  );
  return onChange ? (
    <button className={`ol-set ol-set-${hint}`} onClick={() => { sfx.confirm(); onChange(); }}>{body}</button>
  ) : (
    <div className="ol-set fixed">{body}</div>
  );
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

/**
 * The room: code to share, its course and conditions (the host's to change: the course select and the conditions
 * list come up over the room, and the change is sent when one is chosen), who is in and what each is doing (their
 * vehicles on the course behind), car choice, and the host's start button with what it still waits for.
 */
export function OnlineRoomScreen() {
  const { room, player, carId, busy, error, waits, present } = useOnline();
  const choosing = useLobby((s) => s.choosing);
  const go = useApp((s) => s.go);
  const [picking, setPicking] = useState<CarId | null>(null);
  // the host's change of course or conditions, up over the room
  const [setup, setSetup] = useState<'course' | 'conditions' | null>(null);
  useOverScreen(!!setup);
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
  const hold = room ? startHold(room) : null;
  const canStart = waiting && !hold;
  // a load that goes on and on is told as such after a while: looked at again every few seconds while one runs
  const someLoading = hold?.why === 'loading';
  const [, look] = useState(0);
  useEffect(() => {
    if (!someLoading) return;
    const t = setInterval(() => look((n) => n + 1), 5000);
    return () => clearInterval(t);
  }, [someLoading]);
  const now = Date.now();
  const slow = (p: RoomMember) => !p.loaded && stalled(waits[p.id], now);
  // (known only with a live connection here; a game that is still loading has not joined the channel yet)
  const gone = (p: RoomMember) => p.loaded && p.id !== player?.id && !!present && !present.includes(p.id);
  // whom the host may take out of the room: the start would wait for them for ever
  const removable = room && isHost && waiting ? room.players.filter((p) => p.id !== player?.id && (slow(p) || gone(p))) : [];
  const kick = (p: RoomMember) => {
    if (busy) return;
    sfx.back();
    void kickMember(p.id);
  };
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
  const canSet = isHost && waiting;
  // the race started, or the room went to another host, with the picker up
  useEffect(() => {
    if (setup && !canSet) {
      setSetup(null);
      previewConditions(null);
    }
  }, [setup, canSet]);
  useMenuInput((a) => {
    if (a === 'back') exit();
    if (a === 'confirm') (isHost ? start : ready)();
    // ← →: the car select, on the previous / next vehicle (looking is no change of car: Enter there enters it)
    if ((a === 'left' || a === 'right') && room?.status === 'waiting') {
      setPicking(neighbourVehicle(room.track_id, carId, a === 'left' ? -1 : 1));
      sfx.move();
    }
    // the host: X the course, C the time & weather; R takes a member out who holds the room up
    if (canSet && (a === 'optionX' || a === 'optionY')) {
      sfx.confirm();
      setSetup(a === 'optionX' ? 'course' : 'conditions');
    }
    if (a === 'optionSort' && removable.length) kick(removable[0]);
  }, !picking && !setup && !!room);
  if (!player) return null;
  if (!room) return <RoomGone />;
  const course = COURSES[room.track_id as CourseId];
  const conditions = CONDITIONS.find((c) => c.id === room.time_of_day);
  const roomNote = (what: string) => `ルーム ${room.code}・${what}`;
  if (setup === 'course' && canSet) {
    return (
      <CourseSelect
        head={<ScreenHead jp="コースを変更" en="ROOM COURSE" note={roomNote('決定すると全員のゲームがコースを読み込みます')} />}
        initial={room.track_id as CourseId}
        current={room.track_id as CourseId}
        plain
        confirm="このコースに変更"
        onChoose={(id) => {
          setSetup(null);
          void changeRoom({ track_id: id });
        }}
        onBack={() => setSetup(null)}
      />
    );
  }
  if (setup === 'conditions' && canSet && course) {
    return (
      <ConditionsSelect
        head={<ScreenHead jp="時間帯・天候を変更" en="ROOM CONDITIONS" note={roomNote('決定すると全員の画面が切り替わります')} />}
        course={course}
        initial={room.time_of_day}
        current={room.time_of_day}
        plain
        confirm="この条件に変更"
        // (this game shows what the cursor rests on; the others' change when it is chosen)
        onLook={previewConditions}
        onChoose={(tod) => {
          setSetup(null);
          void chooseConditions(tod);
        }}
        onBack={() => {
          setSetup(null);
          previewConditions(null);
        }}
      />
    );
  }
  // what the start still waits for, in words (the host's button and the guests' line)
  const others = hold && hold.why !== 'players' ? hold.who.filter((p) => p.id !== player.id) : [];
  const late = removable.filter((p) => !p.loaded), lost = removable.filter((p) => p.loaded);
  const waitLine = !waiting
    ? null
    : late.length
      ? `${names(late)} の読み込みに時間がかかっています。待つか、ルームから外せます。`
      : lost.length
        ? `${names(lost)} は接続が切れています。ルームから外せます。`
        : !hold || hold.why === 'players' || !others.length
          ? null
          : hold.why === 'loading'
            ? `${names(others)} がコースを読み込んでいます`
            : isHost || me?.ready
              ? `${names(others)} の準備完了を待っています`
              : null;
  const hints: [HintKey, string][] = [['lr', '車両選択'], ['drag', '視点']];
  if (canSet) hints.push(['fav', 'コース'], ['color', '天候']);
  if (removable.length) hints.push(['sort', `${removable[0].name} を外す`]);
  hints.push(['ok', isHost ? 'スタート' : me?.ready ? '準備完了を取り消す' : '準備完了']);
  return (
    <div className={`screen online-room ${dragging ? 'orbiting' : ''}`} {...orbit}>
      {!picking && <LobbyTags room={room} playerId={player.id} choosing={choosing} />}
      <ScreenHead jp="ルーム" en="ONLINE ROOM" note={<>{course?.name ?? room.track_id}・{conditions?.jp ?? ''} <RealtimeBadge /></>} />
      <div className="ol-panel">
        <div className="ol-code-big">
          <small>ROOM CODE</small>
          <b>{room.code}</b>
          <span>友達にこのコードを伝えてください</span>
        </div>
        <div className="ol-setup">
          <SetupCell label="コース" value={course?.name ?? room.track_id} hint="fav" onChange={canSet ? () => setSetup('course') : undefined} />
          <SetupCell label="時間帯・天候" value={conditions?.jp ?? ''} hint="color" onChange={canSet ? () => setSetup('conditions') : undefined} />
        </div>
        <ul className="ol-slots">
          {Array.from({ length: room.max_players }, (_, slot) => {
            const p = room.players.find((m) => m.slot === slot);
            const state = !p ? 'empty' : !p.loaded ? 'loading' : gone(p) ? 'gone' : p.ready && p.id !== room.host_id ? 'ready' : '';
            const pct = p && !p.loaded ? waits[p.id]?.pct ?? null : null;
            return (
              <li key={slot} className={`${state}${p?.id === player.id ? ' me' : ''}`}>
                <i style={{ background: SLOT_COLORS[slot] }} />
                {p ? (
                  <>
                    <b>{p.name}</b>
                    <span>{CAR_SPECS[choosing[p.id] ?? p.car_id].name}</span>
                    <MemberMark p={p} room={room} choosing={p.id in choosing} gone={gone(p)} />
                    {removable.includes(p) && <button className="mini ol-kick" disabled={busy} onClick={() => kick(p)}>外す</button>}
                    {p.id === room.host_id && <em className="host">HOST</em>}
                    {p.id === player.id && <em className="you">YOU</em>}
                    {/* how far their game has come with the course, when it tells (the bar; no figure) */}
                    {!p.loaded && <div className={`ol-load${pct === null ? ' blind' : ''}`} aria-hidden><div style={{ transform: `scaleX(${((pct ?? 0) / 100).toFixed(2)})` }} /></div>}
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
              {!hold ? 'レース開始' : hold.why === 'players' ? '2人以上でスタートできます' : hold.why === 'loading' ? `読み込み待ち… あと${hold.who.length}人` : `準備完了待ち… あと${hold.who.length}人`}
            </button>
          ) : (
            <button className={`cta ol-ready ${me?.ready ? 'on' : ''}`} disabled={busy || !waiting || !me?.loaded} onClick={ready}>
              {!me?.loaded ? 'コースを読み込んでいます…' : me.ready ? '準備完了を取り消す' : '準備完了'}
            </button>
          )}
          {waitLine ? (
            <div className={`ol-waiting ol-hold${late.length || (!lost.length && hold?.why === 'loading') ? ' amber' : lost.length ? ' alert' : ''}`}>{waitLine}</div>
          ) : (
            !isHost && me?.ready && <div className="ol-waiting">ホストのスタートを待っています…</div>
          )}
          <button className="cta small ghost ol-leave" onClick={exit}>退出</button>
        </div>
        {error && <OnlineError message={error} />}
      </div>
      <Hint items={hints} />
    </div>
  );
}

/** Live results: finishers by time; the others show as still racing or retired. */
export function OnlineResultsScreen() {
  const { room, player, busy, error } = useOnline();
  const result = useApp((s) => s.result);
  const go = useApp((s) => s.go);
  // the host picks another course for the next race: the course select, up over the results
  const [picking, setPicking] = useState(false);
  useOverScreen(picking);
  useEffect(() => {
    // after the finish jingle
    void gameHolder.game?.audio?.playMusic('bgm_results', { delay: 4.5 });
  }, []);
  const isHost = !!room && !!player && room.host_id === player.id;
  useEffect(() => {
    if (picking && !isHost) setPicking(false);
  }, [picking, isHost]);
  useMenuInput((a) => {
    if (a === 'back') { sfx.back(); void leaveRoom(); go('modes'); }
    // the host's Enter is the rematch button, X the next race on another course
    if (a === 'confirm' && isHost && !busy) { sfx.confirm(); void rematch(); }
    if (a === 'optionX' && isHost && !busy) { sfx.confirm(); setPicking(true); }
  }, !!room && !picking);
  if (!player) return null;
  if (!room) return <RoomGone />;
  if (picking && isHost) {
    return (
      <CourseSelect
        head={<ScreenHead jp="次のコース" en="NEXT COURSE" note={`ルーム ${room.code}・決定すると全員がルームに戻り、コースを読み込みます`} />}
        initial={room.track_id as CourseId}
        current={room.track_id as CourseId}
        plain
        confirm="このコースで次のレース"
        onChoose={(id) => {
          setPicking(false);
          void rematch(id === room.track_id ? {} : { track_id: id });
        }}
        onBack={() => setPicking(false)}
      />
    );
  }
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
            <>
              <button className="cta" disabled={busy} onClick={() => { sfx.confirm(); void rematch(); }}>もう一度走る</button>
              <button className="cta small ol-next" disabled={busy} onClick={() => { sfx.confirm(); setPicking(true); }}>コースを変えて走る</button>
            </>
          ) : (
            <div className="ol-waiting">ホストが次のレースを決めるのを待っています…</div>
          )}
          <button className="cta small ghost" onClick={() => { sfx.back(); void leaveRoom(); go('modes'); }}>ルームを出る</button>
        </div>
        {error && <OnlineError message={error} />}
      </div>
      {isHost && <Hint items={[['ok', 'もう一度走る'], ['fav', 'コースを変える']]} />}
    </div>
  );
}
