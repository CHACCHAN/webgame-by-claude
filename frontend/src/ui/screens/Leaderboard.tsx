import { useEffect, useRef, useState } from 'react';
import { useApp } from '../../store/app';
import { useMenuInput, hoverSelect } from '../useMenuInput';
import { api, loadLocalBest, loadPlayer, type LeaderboardEntry } from '../../api/client';
import { CAR_SPECS, VEHICLE_ORDER, type CarId } from '../../game/vehicle/carSpecs';
import { formatTime } from '../format';
import { COURSES, COURSE_ORDER, type CourseId } from '../../game/track/courses';
import { currentCourseId } from '../../store/settings';
import { sfx } from '../sfx';
import { FocusFrame, Hint, Notice, ScreenHead } from '../kit';

export function LeaderboardScreen() {
  const { go, set, mode } = useApp();
  const [filter, setFilter] = useState<CarId | null>(null);
  const [entries, setEntries] = useState<LeaderboardEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [sel, setSel] = useState(0);
  const me = loadPlayer();
  const ghostMode = mode === 'ghost';
  // ghost battles use the loaded course; the ranking can browse every course
  const [course, setCourse] = useState<CourseId>(currentCourseId());
  const local = loadLocalBest(course);

  useEffect(() => {
    let alive = true;
    setEntries(null);
    setError(null);
    api
      .leaderboard(course, filter)
      .then((e) => alive && setEntries(e))
      .catch((e) => alive && setError(e.message));
    return () => {
      alive = false;
    };
  }, [filter, course, attempt]);

  const filters: (CarId | null)[] = [null, ...VEHICLE_ORDER];
  const rows = entries ?? [];
  // ghost battles: only the runs with a ghost can be picked; the ranking: every row can be stepped through
  const selectable = ghostMode ? rows.filter((r) => r.has_ghost) : rows;

  const challenge = (e: LeaderboardEntry) => {
    sfx.confirm();
    set({ mode: 'ghost', ghostChoice: { runId: e.run_id, label: e.player_name, carId: e.car_id, timeMs: e.time_ms } });
    go('garage');
  };
  const challengeLocal = () => {
    if (!local) return;
    sfx.confirm();
    set({ mode: 'ghost', ghostChoice: { runId: 'local', label: '自己ベスト', carId: local.carId, timeMs: local.timeMs } });
    go('garage');
  };

  useMenuInput((a) => {
    if (a === 'left' || a === 'right') {
      const k = filters.indexOf(filter);
      setFilter(filters[(k + (a === 'left' ? filters.length - 1 : 1)) % filters.length]);
      setSel(0);
      sfx.tab();
    }
    if (a === 'up' && sel > 0) { setSel(sel - 1); sfx.move(); }
    if (a === 'down' && sel < selectable.length - 1) { setSel(sel + 1); sfx.move(); }
    if (a === 'confirm' && ghostMode && selectable[sel]) challenge(selectable[sel]);
    if (a === 'back') {
      sfx.back();
      go(ghostMode ? 'conditions' : 'modes');
    }
  });
  // the selected row and the selected vehicle tab stay in view
  const wrap = useRef<HTMLDivElement>(null);
  const tabs = useRef<HTMLDivElement>(null);
  useEffect(() => {
    wrap.current?.querySelector('tr.active')?.scrollIntoView({ block: 'nearest' });
  }, [sel, entries]);
  useEffect(() => {
    tabs.current?.querySelector('button.on')?.scrollIntoView({ block: 'nearest', inline: 'nearest' });
  }, [filter]);

  return (
    <div className="screen panel-screen">
      <ScreenHead jp={ghostMode ? 'ゴースト選択' : 'ランキング'} en={ghostMode ? 'GHOST BATTLE' : 'RANKING'} note={`${COURSES[course].name}・${ghostMode ? '挑戦するゴーストを選択' : 'オンラインランキング'}`} />
      <div className="panel wide leaderboard">
        {!ghostMode && (
          <div className="tabs course-tabs">
            {COURSE_ORDER.map((c) => (
              <button key={c} className={c === course ? 'on' : ''} onClick={() => { sfx.tab(); setCourse(c); setSel(0); }}>
                {COURSES[c].name}
              </button>
            ))}
          </div>
        )}
        <div className="tabs car-tabs" ref={tabs}>
          {filters.map((f) => (
            <button key={f ?? 'all'} className={f === filter ? 'on' : ''} onClick={() => { sfx.tab(); setFilter(f); setSel(0); }}>
              {f ? CAR_SPECS[f].name : 'ALL CARS'}
            </button>
          ))}
        </div>
        {ghostMode && local && (
          <div className="local-ghost" onClick={challengeLocal}>
            <span>自己ベストのゴーストと走る</span>
            <b>{formatTime(local.timeMs)}</b>
            <em>{CAR_SPECS[local.carId].name}</em>
            <button className="mini">挑戦 ▶</button>
          </div>
        )}
        <div className="lb-table-wrap focus-box" ref={wrap}>
          {error && (
            <Notice className="lb-msg error" title="ランキングを取得できませんでした" action={<button className="mini" onClick={() => setAttempt((n) => n + 1)}>再試行</button>}>
              サーバーに接続できません（{error}）。記録はこの端末に残っていて、タイムアタックはそのまま遊べます。
            </Notice>
          )}
          {!error && !entries && (
            <div className="lb-msg lb-loading" aria-label="読み込み中">
              <span>読み込み中…</span>
              <i /><i /><i /><i /><i />
            </div>
          )}
          {!error && entries && entries.length === 0 && <div className="lb-msg">まだ記録がありません。最初の記録を刻もう。</div>}
          {!error && rows.length > 0 && (
            <>
              <table className="lb-table">
                <thead>
                  <tr><th>#</th><th>DRIVER</th><th>CAR</th><th>TIME</th><th className="hide-sm">SECTORS</th><th /></tr>
                </thead>
                <tbody key={`${course}-${filter}`} className="stagger">
                  {rows.map((e) => {
                    const idx = selectable.indexOf(e);
                    const active = idx === sel;
                    return (
                      <tr key={e.run_id} className={`${active ? 'active' : ''} ${me && e.player_id === me.id ? 'me' : ''} rank-${e.rank}`} {...hoverSelect(() => idx >= 0 && setSel(idx))}>
                        <td className="rank">{e.rank}</td>
                        <td className="name">{e.player_name}{e.is_bot && <span className="bot">CPU</span>}{e.is_member && <span className="bot member">MEMBER</span>}</td>
                        <td>{CAR_SPECS[e.car_id]?.name ?? e.car_id}</td>
                        <td className="time">{formatTime(e.time_ms)}</td>
                        <td className="sectors hide-sm">{e.sector_ms.map((s, i) => formatTime(s - (i ? e.sector_ms[i - 1] : 0)).replace(/^0:/, '')).join(' / ')}</td>
                        <td>{e.has_ghost && <button className="mini" onClick={() => challenge(e)}>挑戦 ▶</button>}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              <FocusFrame on="tr.active" deps={[sel, entries, filter, course]} kind="row" />
            </>
          )}
        </div>
      </div>
      <Hint items={ghostMode ? [['lr', '車種'], ['ud', '選択'], ['ok', '挑戦']] : [['lr', '車種'], ['ud', 'スクロール']]} />
    </div>
  );
}
