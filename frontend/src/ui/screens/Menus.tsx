import { useEffect, useRef, useState } from 'react';
import { isTouchDevice } from '../touch';
import { enterFullscreen } from '../fullscreen';
import { gameHolder } from '../GameCanvas';
import { useApp } from '../../store/app';
import { useMenuInput, hoverSelect } from '../useMenuInput';
import { CAR_SPECS, singleRatio } from '../../game/vehicle/carSpecs';
import type { AILevel } from '../../game/ai/AIDriver';
import { COURSES, COURSE_ORDER, type CourseId } from '../../game/track/courses';
import { Track } from '../../game/track/Track';
import { currentCourseId, useSettings } from '../../store/settings';
import { decodeGhost } from '../../game/race/Ghost';
import { api, loadCarBests, loadLocalBest, loadRivalRecord } from '../../api/client';
import { medalFor } from '../../game/race/medals';
import { formatTime } from '../format';
import { sfx } from '../sfx';
import { COLORS } from './Cars';
import { FocusFrame, Hint, Notice, ScreenHead } from '../kit';

const TIPS = [
  'ブレーキで荷重を前に移し、ステアを切りながらアクセルを踏むとリアが流れ出します。',
  'Space（サイドブレーキ）はヘアピンの進入で一瞬だけ。引きすぎるとスピードを失います。',
  'C キーでカメラ切替。ドリフト中のカメラは進行方向を向きます。',
  'ゴーストバトルでは、ランキング上位者の走りを半透明の車で再現します。',
];

/**
 * The steps the game reports while it builds the world, as a boot log: each label it has sent stays as a line, the
 * one being worked on at the bottom.
 */
function BootLog() {
  const loading = useApp((s) => s.loading);
  const lines = useRef<string[]>([]);
  const label = loading?.label ?? '';
  if (label && lines.current[lines.current.length - 1] !== label) lines.current = [...lines.current, label].slice(-7);
  const p = loading?.progress ?? 0;
  const failed = label.startsWith('読み込みに失敗');
  return (
    <div className="boot-console">
      <ol className="boot-log">
        {lines.current.map((l, k) => {
          const last = k === lines.current.length - 1;
          return (
            <li key={l} className={last ? (p >= 1 ? 'done' : 'now') : 'done'}>
              <span>{l}</span>
              <em>{last && p < 1 ? (failed ? 'FAIL' : '…') : 'OK'}</em>
            </li>
          );
        })}
      </ol>
      <div className="boot-bar">
        <div className="boot-fill" style={{ transform: `scaleX(${p.toFixed(3)})` }} />
        {!failed && <i className="boot-sweep" aria-hidden />}
      </div>
      <div className="boot-read">
        <span className="boot-label">
          {!failed && p < 1 && <i className="busy-glyph" aria-hidden />}
          {failed ? '起動できませんでした' : label || 'システム起動中'}
        </span>
        <span className="boot-pct">{String(Math.round(p * 100)).padStart(3, '0')} %</span>
      </div>
      {failed && (
        <Notice title="読み込みに失敗しました" action={<button className="mini" onClick={() => location.reload()}>再読み込み</button>}>
          {label.replace(/^読み込みに失敗しました:\s*/, '')}
        </Notice>
      )}
    </div>
  );
}

export function BootScreen() {
  const [tip] = useState(() => TIPS[Math.floor(Math.random() * TIPS.length)]);
  return (
    <div className="screen boot">
      <video className="boot-video" src="/video/loading_loop.mp4" poster="/video/loading_poster.webp" autoPlay muted loop playsInline />
      <div className="boot-art" />
      <div className="boot-mark">
        <div className="logo-kanji">峠</div>
        <div className="logo-sub">TOUGE NOCTURNE</div>
      </div>
      <BootLog />
      <div className="boot-tip"><b>ヒント</b>{tip}</div>
    </div>
  );
}

export function TitleScreen() {
  const go = useApp((s) => s.go);
  const start = () => {
    // phones: fullscreen and landscape (where the browser allows it), from this tap
    if (isTouchDevice()) enterFullscreen();
    const a = gameHolder.game?.initAudio();
    void a?.playMusic('bgm_menu');
    sfx.confirm();
    go('modes');
  };
  useMenuInput((a) => {
    if (a === 'confirm') start();
  });
  // the passes of the game, running along the foot of the screen (twice over, so the loop has no seam)
  const passes = COURSE_ORDER.map((id) => COURSES[id]);
  return (
    <div className="screen title" onClick={start}>
      <div className="title-scan" />
      <div className="title-logo">
        <div className="title-small">{COURSES[currentCourseId()].nameEn} ・ {COURSE_ORDER.length} COURSES</div>
        <h1>
          <span className="kanji" data-text="峠">峠</span>
          <span className="en">TOUGE<br />NOCTURNE</span>
        </h1>
        <div className="title-jp">朧 峠 夜 想 曲</div>
      </div>
      <div className="press-start">{isTouchDevice() ? 'TAP TO START' : 'PRESS ENTER / CLICK TO START'}</div>
      <div className="title-ticker" aria-hidden>
        <div>
          {[0, 1].map((k) => (
            <span key={k}>
              {passes.map((c) => (
                <i key={c.id}>
                  <b>{c.nameEn}</b>
                  {c.name}　{c.tagline}
                </i>
              ))}
            </span>
          ))}
        </div>
      </div>
      <div className="title-foot">
        <span>v1.0</span>
        <span>© 2026 Touge Nocturne Project ― 峠・人物は架空です。車名・車両デザインは各メーカーの商標・意匠です（私的利用の非公開作品）</span>
      </div>
    </div>
  );
}

interface MenuItem {
  id: string;
  label: string;
  jp: string;
  desc: string;
  /** the first item of a group of the menu carries the group's name */
  group?: string;
  action: () => void;
}

export function ModesScreen() {
  const { go, set } = useApp();
  const [idx, setIdx] = useState(0);
  const items: MenuItem[] = [
    { id: 'ta', group: '走る', label: 'TIME ATTACK', jp: 'タイムアタック', desc: '峠を全開で駆け下り、自己ベストとメダル、オンラインランキング上位を狙う。', action: () => { set({ mode: 'time_attack', ghostChoice: null, afterLoad: 'garage' }); go('courses'); } },
    { id: 'rival', label: 'RIVAL BATTLE', jp: 'ライバルバトル', desc: '峠に棲む走り屋と1対1のダウンヒルバトル。先にゴールした方が勝ち。', action: () => { set({ mode: 'rival', ghostChoice: null, afterLoad: 'garage' }); go('courses'); } },
    { id: 'ghost', label: 'GHOST BATTLE', jp: 'ゴーストバトル', desc: 'ランキング上位者や自己ベストの走りを半透明のゴーストで再現。その背中を追え。', action: () => { set({ mode: 'ghost', afterLoad: 'leaderboard' }); go('courses'); } },
    { id: 'online', label: 'ONLINE BATTLE', jp: 'オンライン対戦', desc: '最大5人でルームを作って同時にダウンヒル。ルームコードを友達に伝えて一緒に走ろう。', action: () => { set({ mode: 'online', ghostChoice: null }); go('online'); } },
    { id: 'cars', group: '見る', label: 'CAR LIST', jp: '車両一覧', desc: '用意されている車の性能と詳細を見る。ドラッグで車をぐるりと見回せる。', action: () => go('cars') },
    { id: 'rank', label: 'RANKING', jp: 'ランキング', desc: 'コースごとのオンラインランキングを確認する。', action: () => { set({ mode: 'time_attack' }); go('leaderboard'); } },
    { id: 'settings', group: '整える', label: 'SETTINGS', jp: '設定', desc: 'グラフィック品質、サウンド、運転アシスト、表示。', action: () => go('settings') },
    { id: 'controls', label: 'CONTROLS', jp: '操作方法', desc: 'キーボード / ゲームパッド / スマホの操作を確認する。', action: () => go('controls') },
  ];
  useMenuInput((a) => {
    if (a === 'up') { setIdx((i) => (i + items.length - 1) % items.length); sfx.move(); }
    if (a === 'down') { setIdx((i) => (i + 1) % items.length); sfx.move(); }
    if (a === 'confirm') { sfx.confirm(); items[idx].action(); }
    if (a === 'back') { sfx.back(); go('title'); }
  });
  useEffect(() => {
    if (gameHolder.game && gameHolder.game.phase !== 'attract') gameHolder.game.startAttract();
    void gameHolder.game?.audio?.playMusic('bgm_menu');
  }, []);
  return (
    <div className="screen menu-screen">
      <div className="side-panel">
        <div className="focus-box">
          <ul className="menu-list stagger">
            {items.map((it, i) => (
              <li
                key={it.id}
                className={`${i === idx ? 'active' : ''}${it.group ? ' group-start' : ''}`}
                data-group={it.group}
                {...hoverSelect(() => setIdx(i))}
                onClick={() => { sfx.confirm(); it.action(); }}
              >
                <span className="mi-en">{it.label}</span>
                <span className="mi-jp">{it.jp}</span>
              </li>
            ))}
          </ul>
          <FocusFrame on="li.active" deps={[idx]} kind="row" />
        </div>
        <div className="menu-desc" key={idx}>{items[idx].desc}</div>
      </div>
      <Hint items={[['ud', '選択'], ['ok', '決定']]} />
    </div>
  );
}

export function RivalsScreen() {
  const { go, set, rivalLevel } = useApp();
  const levels: AILevel[] = ['rookie', 'ace', 'legend'];
  const [i, setI] = useState(levels.indexOf(rivalLevel));
  const course = COURSES[currentCourseId()];
  const start = (level: AILevel = levels[i]) => {
    set({ rivalLevel: level });
    sfx.confirm();
    void startRaceFromState(level);
  };
  useMenuInput((a) => {
    if (a === 'left' || a === 'up') { setI((x) => (x + 2) % 3); sfx.move(); }
    if (a === 'right' || a === 'down') { setI((x) => (x + 1) % 3); sfx.move(); }
    if (a === 'confirm') start();
    if (a === 'back') { sfx.back(); go(singleRatio(CAR_SPECS[useApp.getState().carId]) ? 'garage' : 'transmission'); }
  });
  return (
    <div className="screen rivals">
      <ScreenHead jp="ライバル選択" en="CHOOSE YOUR RIVAL" note={`${course.name}の走り屋`} />
      <div className="rival-cards focus-box stagger">
        {levels.map((l, k) => {
          const p = course.rivals[l];
          const record = loadRivalRecord(course.id, l);
          return (
            <div key={l} className={`rival-card ${l} ${k === i ? 'active' : ''}`} {...hoverSelect(() => setI(k))} onClick={() => { setI(k); start(l); }}>
              <Portrait src={p.portrait} />
              <div className="rc-body">
                <div className="rc-level" aria-label={`レベル ${k + 1}`}>
                  {levels.map((x, n) => <i key={x} className={n <= k ? 'on' : ''} />)}
                </div>
                <div className="rc-title">{p.title}</div>
                <div className="rc-name">{p.name}</div>
                <div className="rc-car">{CAR_SPECS[p.car].name}</div>
                <p>{p.description}</p>
                <div className="rc-record">
                  {record.wins + record.losses > 0 ? <>対戦成績 <b>{record.wins}</b> 勝 <b>{record.losses}</b> 敗</> : 'まだ対戦していません'}
                </div>
              </div>
            </div>
          );
        })}
        <FocusFrame on=".rival-card.active" deps={[i]} kind="magenta" pad={5} />
      </div>
      <Hint items={[['lr', '選択'], ['ok', 'バトル開始']]} />
    </div>
  );
}

/** Rival portrait with a silhouette fallback while the art is not delivered yet. */
export function Portrait({ src, className = '' }: { src: string; className?: string }) {
  const [ok, setOk] = useState(true);
  return (
    <div className={`portrait ${className} ${ok ? '' : 'missing'}`}>
      {ok ? <img src={src} alt="" onError={() => setOk(false)} draggable={false} /> : <div className="silhouette" />}
    </div>
  );
}

interface CourseFigures {
  km: string;
  drop: number;
  map: { d: string; start: [number, number]; end: [number, number] };
}
const figuresCache = new Map<CourseId, CourseFigures>();
/** Length, drop and the outline of a course from its centre line (built once per course). */
function courseFigures(id: CourseId): CourseFigures {
  const hit = figuresCache.get(id);
  if (hit) return hit;
  const t = new Track(COURSES[id].design);
  let minX = Infinity, maxX = -Infinity, minZ = Infinity, maxZ = -Infinity;
  for (let k = 0; k < t.count; k += 4) {
    minX = Math.min(minX, t.pos[k * 3]); maxX = Math.max(maxX, t.pos[k * 3]);
    minZ = Math.min(minZ, t.pos[k * 3 + 2]); maxZ = Math.max(maxZ, t.pos[k * 3 + 2]);
  }
  const sc = Math.min(260 / (maxX - minX), 150 / (maxZ - minZ));
  const ox = (300 - (maxX - minX) * sc) / 2, oz = (170 - (maxZ - minZ) * sc) / 2;
  const m = (k: number): [number, number] => [ox + (t.pos[k * 3] - minX) * sc, oz + (t.pos[k * 3 + 2] - minZ) * sc];
  let d = '';
  for (let k = 0; k < t.count; k += 6) d += (k ? 'L' : 'M') + m(k).map((v) => v.toFixed(1)).join(',');
  const y0 = t.pos[Math.round(t.startS) * 3 + 1], y1 = t.pos[Math.round(t.finishS) * 3 + 1];
  const out = { km: ((t.finishS - t.startS) / 1000).toFixed(2), drop: Math.round(y0 - y1), map: { d, start: m(Math.round(t.startS)), end: m(Math.round(t.finishS)) } };
  figuresCache.set(id, out);
  return out;
}

/** Mini map of a course drawn from its centerline (the line draws itself when its card is selected). */
function CourseMap({ id }: { id: CourseId }) {
  const path = courseFigures(id).map;
  return (
    <svg className="course-map" viewBox="0 0 300 170">
      <path d={path.d} className="cm-shadow" />
      <path d={path.d} className="cm-line" pathLength={1} />
      <circle cx={path.start[0]} cy={path.start[1]} r="5" className="cm-start" />
      <circle cx={path.end[0]} cy={path.end[1]} r="5" className="cm-end" />
    </svg>
  );
}

export function CoursesScreen() {
  const { go, set, mode } = useApp();
  const [i, setI] = useState(Math.max(0, COURSE_ORDER.indexOf(currentCourseId())));
  useEffect(() => {
    void gameHolder.game?.audio?.playMusic('bgm_menu');
  }, []);
  const choose = async (id: CourseId) => {
    sfx.confirm();
    useSettings.getState().set({ courseId: id });
    const game = gameHolder.game;
    if (game && game.course.id !== id) {
      set({ loading: { progress: 0, label: '' } });
      go('loading');
      await game.switchCourse(id);
      game.startAttract();
    }
    set({ loading: null });
    go('conditions');
  };
  useMenuInput((a) => {
    if (a === 'left' || a === 'up') { setI((x) => (x + COURSE_ORDER.length - 1) % COURSE_ORDER.length); sfx.move(); }
    if (a === 'right' || a === 'down') { setI((x) => (x + 1) % COURSE_ORDER.length); sfx.move(); }
    if (a === 'confirm') void choose(COURSE_ORDER[i]);
    if (a === 'back') { sfx.back(); go('modes'); }
  });
  const cards = useRef<HTMLDivElement>(null);
  useEffect(() => {
    // (narrow screens stack the cards and scroll)
    cards.current?.querySelector('.course-card.active')?.scrollIntoView({ block: 'nearest', inline: 'nearest' });
  }, [i]);
  return (
    <div className="screen courses">
      <ScreenHead jp="コース選択" en="SELECT COURSE" note={mode === 'ghost' ? 'ゴーストバトル' : undefined} />
      <div className="course-cards focus-box stagger" ref={cards}>
        {COURSE_ORDER.map((id, k) => {
          const c = COURSES[id];
          const info = courseFigures(id);
          const best = Math.min(...Object.values(loadCarBests(id)).filter((v): v is number => typeof v === 'number'));
          return (
            <div key={id} className={`course-card ${k === i ? 'active' : ''}`} {...hoverSelect(() => setI(k))} onClick={() => { setI(k); void choose(id); }}>
              <div className="cc-art" style={{ backgroundImage: `url(${c.art})` }}>
                <CourseMap id={id} />
              </div>
              <div className="cc-body">
                <div className="cc-en">{c.nameEn}</div>
                <div className="cc-name">{c.name}</div>
                <div className="cc-tag">{c.tagline}</div>
                <p>{c.description}</p>
                <div className="cc-stats">
                  <span><small>LENGTH</small>{info.km} km</span>
                  <span><small>DROP</small>{info.drop} m</span>
                  <span className={isFinite(best) ? 'has-best' : ''}><small>BEST</small>{isFinite(best) ? formatTime(best) : '--:--.---'}</span>
                </div>
                <div className="cc-road">
                  <small>ROAD</small>
                  {c.surface.label}・グリップ {Math.round(c.surface.grip * 100)}%
                </div>
              </div>
            </div>
          );
        })}
        <FocusFrame on=".course-card.active" deps={[i]} pad={5} />
      </div>
      <Hint items={[['lr', 'コース'], ['ok', '決定']]} />
    </div>
  );
}

/** Shown while a different course is being built. */
export function CourseLoadingScreen() {
  const c = COURSES[currentCourseId()];
  return (
    <div className="screen boot course-loading">
      <div className="boot-art" style={{ backgroundImage: `url(${c.art}), url(/img/keyart.webp)` }} />
      <div className="boot-mark">
        <div className="cl-en">{c.nameEn}</div>
        <div className="cl-name">{c.name}</div>
        <div className="cl-tag">{c.tagline}</div>
      </div>
      <BootLog />
    </div>
  );
}

/** Kick off a race using the current app state. */
export async function startRaceFromState(rival?: AILevel) {
  const app = useApp.getState();
  const game = gameHolder.game;
  if (!game) return;
  let ghost = null;
  try {
    if (app.mode === 'ghost' && app.ghostChoice) {
      if (app.ghostChoice.runId === 'local') {
        const lb = loadLocalBest(game.course.id);
        if (lb) ghost = { data: await decodeGhost(lb.ghost), label: '自己ベスト', carId: lb.carId, timeMs: lb.timeMs, splits: lb.splits };
      } else {
        const g = await api.ghost(app.ghostChoice.runId);
        ghost = { data: await decodeGhost(g), label: g.player_name, carId: g.car_id, timeMs: g.time_ms, splits: g.sector_ms };
      }
    } else if (app.mode === 'time_attack') {
      const lb = loadLocalBest(game.course.id);
      if (lb) ghost = { data: await decodeGhost(lb.ghost), label: '自己ベスト', carId: lb.carId, timeMs: lb.timeMs, splits: lb.splits };
    }
  } catch (e) {
    console.warn('ghost unavailable', e);
  }
  game.initAudio();
  const color = app.carColor && COLORS[app.carId].includes(app.carColor) ? app.carColor : undefined;
  const rivalLevel = app.mode === 'rival' ? (rival ?? app.rivalLevel) : undefined;
  // what the rival knows of the player when it speaks: their battles so far, the medal held with this car
  const best = loadCarBests(game.course.id)[app.carId];
  const rivalRecord = rivalLevel && { ...loadRivalRecord(game.course.id, rivalLevel), medal: (best ? medalFor(game.course.id, app.carId, best) : null) ?? ('none' as const) };
  game.startRace({ mode: app.mode, carId: app.carId, color, rivalLevel, rivalRecord, ghost });
  app.set({ screen: 'race', result: null, rivalLine: null, paused: false });
}

/** [action, keyboard, gamepad] — also shown briefly at every race start */
/** action, keyboard, gamepad, touch screen */
export const CONTROL_ROWS: [string, string, string, string][] = [
  ['アクセル', 'W / ↑', 'RT / A', '右下 アクセル'],
  ['ブレーキ・バック', 'S / ↓', 'LT / X', 'ブレーキ'],
  ['ステアリング', 'A D / ← →', '左スティック', '左下 ◀ ▶'],
  ['サイドブレーキ', 'Space', 'B / RB', 'サイド'],
  ['シフトアップ / ダウン（MT時）', 'E / Q', 'Y / LB', '▲ / ▼'],
  ['カメラ切替', 'C', '十字キー↑', '右上 CAM'],
  ['コースに復帰', 'R', 'Back', '右上 復帰'],
  ['クラクション', 'H', '右スティック押し込み', '—'],
  ['ポーズ', 'Esc / P', 'Start', '右上 II'],
  ['全画面表示の切り替え', 'F', '—', '左下 全画面'],
];

const DRIFT_STEPS = [
  ['減速', 'コーナー手前でしっかり減速し、ステアを切り始める。'],
  ['きっかけ', 'サイドブレーキを一瞬引く／ブレーキを短く踏んで離しながら大きく切る／コーナー中にアクセルを一度戻して踏み直す。（アクセルを踏みっぱなしで曲がるだけなら滑らない）'],
  ['角度を保つ', '車が向きを変えたら、カウンターステア（逆ハンドル）とアクセルで角度を保つ。'],
  ['立ち上がり', '出口が見えたらステアを戻してアクセル全開。'],
];

export function ControlsScreen() {
  const go = useApp((s) => s.go);
  useMenuInput((a) => {
    if (a === 'back' || a === 'confirm') { sfx.back(); go('modes'); }
  });
  const rows = CONTROL_ROWS;
  return (
    <div className="screen panel-screen">
      <ScreenHead jp="操作方法" en="CONTROLS" />
      <div className="panel wide controls">
        <table className="controls-table">
          <thead>
            <tr><th>操作</th><th>キーボード</th><th>ゲームパッド</th><th>スマホ</th></tr>
          </thead>
          <tbody className="stagger">
            {rows.map(([a, k, p, t]) => (
              <tr key={a}><td>{a}</td><td><kbd>{k}</kbd></td><td><kbd>{p}</kbd></td><td><kbd>{t}</kbd></td></tr>
            ))}
          </tbody>
        </table>
        <div className="drift-guide">
          <h3>ドリフトのコツ</h3>
          <ol>
            {DRIFT_STEPS.map(([name, text]) => (
              <li key={name}><b>{name}</b>{text}</li>
            ))}
          </ol>
          <p>運転アシスト「標準」ではカウンターステアとスピン防止が補助されます（設定で変更可）。</p>
        </div>
      </div>
      <Hint items={[['ok', '閉じる']]} />
    </div>
  );
}

export function useLocalBestLabel() {
  const lb = loadLocalBest(currentCourseId());
  return lb ? `${formatTime(lb.timeMs)} (${CAR_SPECS[lb.carId].name})` : null;
}
