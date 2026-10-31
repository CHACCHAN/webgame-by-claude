import { useEffect, useState } from 'react';
import { gameHolder } from '../GameCanvas';
import { useApp } from '../../store/app';
import { useMenuInput } from '../useMenuInput';
import { CAR_ORDER, CAR_SPECS, type CarId } from '../../game/vehicle/carSpecs';
import { COURSES, COURSE_ORDER, type CourseId } from '../../game/track/courses';
import { currentCourseId } from '../../store/settings';
import { loadPlayer } from '../../api/client';
import { SLOT_COLORS } from '../../game/net/RemoteRacers';
import { formatTime } from '../format';
import { sfx } from '../sfx';
import { Hint } from './Menus';
import { chooseCar, createRoom, joinRoom, leaveRoom, registerName, rematch, startOnlineRace, useOnline } from '../../store/online';

const MAX_PLAYERS = 3;

function CarPicker({ carId, disabled }: { carId: CarId; disabled?: boolean }) {
  return (
    <div className="ol-cars">
      {CAR_ORDER.map((id) => (
        <button key={id} className={`chip ${id === carId ? 'on' : ''}`} disabled={disabled} onClick={() => { sfx.move(); chooseCar(id); }}>
          {CAR_SPECS[id].name}
        </button>
      ))}
    </div>
  );
}

/** Name, car, then create a room on a course or join one with its code. */
export function OnlineLobbyScreen() {
  const { player, carId, busy, error } = useOnline();
  const go = useApp((s) => s.go);
  const [name, setName] = useState(() => loadPlayer()?.name ?? '');
  const [course, setCourse] = useState<CourseId>(currentCourseId());
  const [code, setCode] = useState('');
  useEffect(() => {
    const stored = loadPlayer();
    if (stored && !useOnline.getState().player) useOnline.getState().set({ player: stored });
    gameHolder.game?.showGarage(useOnline.getState().carId);
  }, []);
  useMenuInput((a) => {
    if (a === 'back') { sfx.back(); go('modes'); }
    if (a === 'left' || a === 'right') {
      const i = CAR_ORDER.indexOf(useOnline.getState().carId);
      chooseCar(CAR_ORDER[(i + (a === 'left' ? CAR_ORDER.length - 1 : 1)) % CAR_ORDER.length]);
      sfx.move();
    }
  });
  return (
    <div className="screen online-lobby">
      <div className="crumb center">ONLINE BATTLE ― オンライン対戦（最大{MAX_PLAYERS}人）</div>
      <div className="ol-panel">
        {!player ? (
          <form className="ol-section" onSubmit={(e) => { e.preventDefault(); sfx.confirm(); void registerName(name); }}>
            <label>走り屋ネーム（16文字まで）</label>
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
              <CarPicker carId={carId} />
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
                <button className="cta small ol-create" disabled={busy} onClick={() => { sfx.confirm(); void createRoom(course); }}>
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
        {error && <div className="ol-error">{error}</div>}
      </div>
      <Hint items={[['←→', '車'], ['Esc', '戻る']]} />
    </div>
  );
}

function RealtimeBadge() {
  const realtime = useOnline((s) => s.realtime);
  const label = { off: 'OFFLINE', connecting: '接続中…', live: 'LIVE', failed: '通信: ポーリング' }[realtime];
  return <span className={`rt-badge ${realtime}`}>{label}</span>;
}

/** The room: code to share, who is in, car choice, and the host's start button. */
export function OnlineRoomScreen() {
  const { room, player, carId, busy, error } = useOnline();
  const go = useApp((s) => s.go);
  const exit = () => {
    sfx.back();
    void leaveRoom();
    go('online');
  };
  useMenuInput((a) => {
    if (a === 'back') exit();
    if ((a === 'left' || a === 'right') && room?.status === 'waiting') {
      const i = CAR_ORDER.indexOf(carId);
      chooseCar(CAR_ORDER[(i + (a === 'left' ? CAR_ORDER.length - 1 : 1)) % CAR_ORDER.length]);
      sfx.move();
    }
  });
  if (!room || !player) return null;
  const isHost = room.host_id === player.id;
  const canStart = room.players.length >= 2;
  const course = COURSES[room.track_id as CourseId];
  return (
    <div className="screen online-room">
      <div className="crumb center">ONLINE ROOM ― {course?.name ?? room.track_id} <RealtimeBadge /></div>
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
                    <span>{CAR_SPECS[p.car_id].name}</span>
                    {p.id === room.host_id && <em>HOST</em>}
                    {p.id === player.id && <em className="you">YOU</em>}
                  </>
                ) : (
                  <span className="wait">参加を待っています…</span>
                )}
              </li>
            );
          })}
        </ul>
        <CarPicker carId={carId} disabled={room.status !== 'waiting'} />
        <div className="ol-actions">
          {isHost ? (
            <button className="cta" disabled={busy || !canStart} onClick={() => { sfx.confirm(); void startOnlineRace(); }}>
              {canStart ? 'レース開始' : '2人以上でスタートできます'}
            </button>
          ) : (
            <div className="ol-waiting">ホストのスタートを待っています…</div>
          )}
          <button className="cta small ghost" onClick={exit}>退出</button>
        </div>
        {error && <div className="ol-error">{error}</div>}
      </div>
      <Hint items={[['←→', '車'], ['Esc', '退出']]} />
    </div>
  );
}

/** Live results: finishers by time; the others show as still racing or retired. */
export function OnlineResultsScreen() {
  const { room, player, busy, error } = useOnline();
  const result = useApp((s) => s.result);
  const go = useApp((s) => s.go);
  useMenuInput((a) => {
    if (a === 'back') { sfx.back(); void leaveRoom(); go('modes'); }
  });
  if (!room || !player) return null;
  const isHost = room.host_id === player.id;
  const rows = [...room.players].sort((a, b) => (a.finish_ms ?? Infinity) - (b.finish_ms ?? Infinity));
  const winner = rows[0]?.finish_ms !== null ? rows[0] : null;
  return (
    <div className="screen online-results">
      <div className="crumb center">ONLINE BATTLE RESULT ― {COURSES[room.track_id as CourseId]?.name}</div>
      <div className="ol-panel">
        <div className="ol-headline">{winner ? (winner.id === player.id ? 'WINNER!' : `${winner.name} の勝利`) : '集計中…'}</div>
        <ol className="ol-standings">
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
        {error && <div className="ol-error">{error}</div>}
      </div>
    </div>
  );
}
