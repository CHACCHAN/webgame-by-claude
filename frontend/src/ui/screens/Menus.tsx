import { useEffect, useState } from 'react';
import { gameHolder } from '../GameCanvas';
import { useApp } from '../../store/app';
import { useMenuInput, hoverSelect } from '../useMenuInput';
import { CAR_SPECS, VEHICLE_ORDER, type CarId } from '../../game/vehicle/carSpecs';
import type { AILevel } from '../../game/ai/AIDriver';
import { COURSES, COURSE_ORDER, type CourseId } from '../../game/track/courses';
import { Track } from '../../game/track/Track';
import { currentCourseId, useSettings } from '../../store/settings';
import { decodeGhost } from '../../game/race/Ghost';
import { api, loadCarBests, loadLocalBest } from '../../api/client';
import { MEDAL_LABEL, medalFor, nextTarget } from '../../game/race/medals';
import { formatTime } from '../format';
import { sfx } from '../sfx';
import { CarSheet, COLORS, useGarageOrbit } from './Cars';

export function BootScreen() {
  const loading = useApp((s) => s.loading);
  const tips = [
    'ヒント：ブレーキで荷重を前に移し、ステアを切りながらアクセルを踏むとリアが流れ出します。',
    'ヒント：Space（サイドブレーキ）はヘアピンの進入で一瞬だけ。引きすぎるとスピードを失います。',
    'ヒント：Cキーでカメラ切替。ドリフト中のカメラは進行方向を向きます。',
    'ヒント：ゴーストバトルでは、ランキング上位者の走りを半透明の車で再現します。',
  ];
  const [tip] = useState(() => tips[Math.floor(Math.random() * tips.length)]);
  const p = loading?.progress ?? 0;
  return (
    <div className="screen boot">
      <video className="boot-video" src="/video/loading_loop.mp4" poster="/video/loading_poster.webp" autoPlay muted loop playsInline />
      <div className="boot-art" />
      <div className="boot-mark">
        <div className="logo-kanji">峠</div>
        <div className="logo-sub">TOUGE NOCTURNE</div>
      </div>
      <div className="boot-bar">
        <div className="boot-fill" style={{ width: `${Math.round(p * 100)}%` }} />
      </div>
      <div className="boot-label">{loading?.label ?? ''}</div>
      <div className="boot-tip">{tip}</div>
    </div>
  );
}

export function TitleScreen() {
  const go = useApp((s) => s.go);
  const start = () => {
    const a = gameHolder.game?.initAudio();
    void a?.playMusic('bgm_menu');
    sfx.confirm();
    go('modes');
  };
  useMenuInput((a) => {
    if (a === 'confirm') start();
  });
  return (
    <div className="screen title" onClick={start}>
      <div className="title-logo">
        <div className="title-small">{COURSES[currentCourseId()].nameEn} ・ 3 COURSES</div>
        <h1>
          <span className="kanji">峠</span>
          <span className="en">TOUGE<br />NOCTURNE</span>
        </h1>
        <div className="title-jp">朧 峠 夜 想 曲</div>
      </div>
      <div className="press-start">PRESS ENTER / CLICK TO START</div>
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
  action: () => void;
}

export function ModesScreen() {
  const { go, set } = useApp();
  const [idx, setIdx] = useState(0);
  const items: MenuItem[] = [
    { id: 'ta', label: 'TIME ATTACK', jp: 'タイムアタック', desc: '峠を全開で駆け下り、自己ベストとメダル、オンラインランキング上位を狙う。', action: () => { set({ mode: 'time_attack', ghostChoice: null, afterLoad: 'garage' }); go('courses'); } },
    { id: 'rival', label: 'RIVAL BATTLE', jp: 'ライバルバトル', desc: '峠に棲む走り屋と1対1のダウンヒルバトル。先にゴールした方が勝ち。', action: () => { set({ mode: 'rival', ghostChoice: null, afterLoad: 'garage' }); go('courses'); } },
    { id: 'ghost', label: 'GHOST BATTLE', jp: 'ゴーストバトル', desc: 'ランキング上位者や自己ベストの走りを半透明のゴーストで再現。その背中を追え。', action: () => { set({ mode: 'ghost', afterLoad: 'leaderboard' }); go('courses'); } },
    { id: 'online', label: 'ONLINE BATTLE', jp: 'オンライン対戦', desc: '最大3人でルームを作って同時にダウンヒル。ルームコードを友達に伝えて一緒に走ろう。', action: () => { set({ mode: 'online', ghostChoice: null }); go('online'); } },
    { id: 'cars', label: 'CAR LIST', jp: '車両一覧', desc: '用意されている車の性能と詳細を見る。ドラッグで車をぐるりと見回せる。', action: () => go('cars') },
    { id: 'rank', label: 'RANKING', jp: 'ランキング', desc: 'オンラインランキングを確認する。', action: () => { set({ mode: 'time_attack' }); go('leaderboard'); } },
    { id: 'settings', label: 'SETTINGS', jp: '設定', desc: 'グラフィック品質、サウンド、運転アシスト、表示。', action: () => go('settings') },
    { id: 'controls', label: 'CONTROLS', jp: '操作方法', desc: 'キーボード / ゲームパッドの操作を確認する。', action: () => go('controls') },
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
        <div className="panel-heading">
          <span className="kanji-badge">峠</span>
          <div>
            <div className="ph-en">MAIN MENU</div>
            <div className="ph-jp">{COURSES[currentCourseId()].name}</div>
          </div>
        </div>
        <ul className="menu-list">
          {items.map((it, i) => (
            <li
              key={it.id}
              className={i === idx ? 'active' : ''}
              {...hoverSelect(() => setIdx(i))}
              onClick={() => { sfx.confirm(); it.action(); }}
            >
              <span className="mi-en">{it.label}</span>
              <span className="mi-jp">{it.jp}</span>
            </li>
          ))}
        </ul>
        <div className="menu-desc">{items[idx].desc}</div>
      </div>
      <Hint items={[['↑↓', '選択'], ['Enter', '決定'], ['Esc', '戻る']]} />
    </div>
  );
}

export function Hint({ items }: { items: [string, string][] }) {
  return (
    <div className="hint-bar">
      {items.map(([k, v]) => (
        <span key={k}>
          <kbd>{k}</kbd> {v}
        </span>
      ))}
    </div>
  );
}


export function GarageScreen() {
  const { go, set, carId, mode, carColor } = useApp();
  const [i, setI] = useState(Math.max(0, VEHICLE_ORDER.indexOf(carId)));
  const id = VEHICLE_ORDER[i];
  const spec = CAR_SPECS[id];
  const palette = COLORS[id];
  const color = carColor && palette.includes(carColor) ? carColor : palette[0];
  useEffect(() => {
    gameHolder.game?.showGarage(id, color);
    set({ carId: id });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);
  useEffect(() => {
    gameHolder.game?.setGarageColor(color);
  }, [color]);
  useEffect(() => {
    void gameHolder.game?.audio?.playMusic('bgm_garage');
  }, []);
  const cycleColor = (d: number) => {
    const k = (palette.indexOf(color) + d + palette.length) % palette.length;
    set({ carColor: palette[k] });
    sfx.move();
  };
  const orbit = useGarageOrbit();
  const confirm = () => {
    sfx.confirm();
    // a train has a single gear ratio: no AT/MT choice
    if (!spec.train) go('transmission');
    else if (mode === 'rival') go('rivals');
    else void startRaceFromState();
  };
  useMenuInput((a) => {
    if (a === 'left') { setI((x) => (x + VEHICLE_ORDER.length - 1) % VEHICLE_ORDER.length); sfx.move(); }
    if (a === 'right') { setI((x) => (x + 1) % VEHICLE_ORDER.length); sfx.move(); }
    if (a === 'up') cycleColor(-1);
    if (a === 'down') cycleColor(1);
    if (a === 'confirm') confirm();
    if (a === 'back') { sfx.back(); go(mode === 'ghost' ? 'leaderboard' : 'conditions'); }
  });
  return (
    <div className={`screen garage ${orbit.dragging ? 'orbiting' : ''}`} {...orbit.handlers}>
      <div className="garage-top">
        <div className="crumb">SELECT YOUR CAR ― 車両選択</div>
      </div>
      <div className="garage-card">
        <CarSheet spec={spec} index={i} />
        <CarRecord id={id} />
        <div className="colors">
          {palette.map((c) => (
            <button key={c} className={c === color ? 'swatch on' : 'swatch'} style={{ background: c }} onClick={() => set({ carColor: c })} aria-label={`color ${c}`} />
          ))}
        </div>
        <button className="cta" onClick={confirm}>
          この車に決定 <span>▶</span>
        </button>
      </div>
      <button className="arrow left" onClick={() => setI((x) => (x + VEHICLE_ORDER.length - 1) % VEHICLE_ORDER.length)}>‹</button>
      <button className="arrow right" onClick={() => setI((x) => (x + 1) % VEHICLE_ORDER.length)}>›</button>
      <Hint items={[['←→', '車両'], ['↑↓', 'カラー'], ['ドラッグ', '視点'], ['Enter', '決定'], ['Esc', '戻る']]} />
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
    if (a === 'back') { sfx.back(); go(CAR_SPECS[useApp.getState().carId].train ? 'garage' : 'transmission'); }
  });
  return (
    <div className="screen rivals">
      <div className="crumb center">CHOOSE YOUR RIVAL ― {course.name}の走り屋</div>
      <div className="rival-cards">
        {levels.map((l, k) => {
          const p = course.rivals[l];
          return (
            <div key={l} className={`rival-card ${l} ${k === i ? 'active' : ''}`} {...hoverSelect(() => setI(k))} onClick={() => { setI(k); start(l); }}>
              <Portrait src={p.portrait} />
              <div className="rc-body">
                <div className="rc-level">{['★', '★★', '★★★'][k]}</div>
                <div className="rc-title">{p.title}</div>
                <div className="rc-name">{p.name}</div>
                <div className="rc-car">{CAR_SPECS[p.car].name}</div>
                <p>{p.description}</p>
              </div>
            </div>
          );
        })}
      </div>
      <Hint items={[['←→', '選択'], ['Enter', 'バトル開始'], ['Esc', '戻る']]} />
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

/** Mini map of a course drawn from its centerline. */
function CourseMap({ id }: { id: CourseId }) {
  const [path, setPath] = useState<{ d: string; start: [number, number]; end: [number, number] } | null>(null);
  useEffect(() => {
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
    setPath({ d, start: m(Math.round(t.startS)), end: m(Math.round(t.finishS)) });
  }, [id]);
  if (!path) return <svg className="course-map" viewBox="0 0 300 170" />;
  return (
    <svg className="course-map" viewBox="0 0 300 170">
      <path d={path.d} className="cm-shadow" />
      <path d={path.d} className="cm-line" />
      <circle cx={path.start[0]} cy={path.start[1]} r="5" className="cm-start" />
      <circle cx={path.end[0]} cy={path.end[1]} r="5" className="cm-end" />
    </svg>
  );
}

export function CoursesScreen() {
  const { go, set, mode } = useApp();
  const [i, setI] = useState(Math.max(0, COURSE_ORDER.indexOf(currentCourseId())));
  const stats = (id: CourseId) => {
    const t = new Track(COURSES[id].design);
    const y0 = t.pos[Math.round(t.startS) * 3 + 1], y1 = t.pos[Math.round(t.finishS) * 3 + 1];
    return { km: ((t.finishS - t.startS) / 1000).toFixed(2), drop: Math.round(y0 - y1) };
  };
  const [info] = useState(() => Object.fromEntries(COURSE_ORDER.map((id) => [id, stats(id)])) as Record<CourseId, { km: string; drop: number }>);
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
  return (
    <div className="screen courses">
      <div className="crumb center">SELECT COURSE ― コース選択{mode === 'ghost' ? '（ゴーストバトル）' : ''}</div>
      <div className="course-cards">
        {COURSE_ORDER.map((id, k) => {
          const c = COURSES[id];
          const best = Math.min(...Object.values(loadCarBests(id)).filter((v): v is number => typeof v === 'number'));
          return (
            <div key={id} className={`course-card ${k === i ? 'active' : ''}`} {...hoverSelect(() => setI(k))} onClick={() => { setI(k); void choose(id); }}>
              <div className="cc-art" style={{ backgroundImage: `url(${c.art}), radial-gradient(ellipse at 70% 115%, rgba(255, 150, 60, 0.32), transparent 60%), linear-gradient(180deg, #0f1c36, #05080e)` }}>
                <CourseMap id={id} />
              </div>
              <div className="cc-body">
                <div className="cc-en">{c.nameEn}</div>
                <div className="cc-name">{c.name}</div>
                <div className="cc-tag">{c.tagline}</div>
                <p>{c.description}</p>
                <div className="cc-stats">
                  <span><small>LENGTH</small>{info[id].km} km</span>
                  <span><small>DROP</small>{info[id].drop} m</span>
                  <span><small>BEST</small>{isFinite(best) ? formatTime(best) : '--:--.---'}</span>
                </div>
                <div className="cc-road">
                  <small>ROAD</small>
                  {c.surface.label}・グリップ {Math.round(c.surface.grip * 100)}%
                </div>
              </div>
            </div>
          );
        })}
      </div>
      <Hint items={[['←→', 'コース'], ['Enter', '決定'], ['Esc', '戻る']]} />
    </div>
  );
}

/** Shown while a different course is being built. */
export function CourseLoadingScreen() {
  const loading = useApp((s) => s.loading);
  const c = COURSES[currentCourseId()];
  const p = loading?.progress ?? 0;
  return (
    <div className="screen boot course-loading">
      <div className="boot-art" style={{ backgroundImage: `url(${c.art}), url(/img/keyart.webp)` }} />
      <div className="boot-mark">
        <div className="cl-en">{c.nameEn}</div>
        <div className="cl-name">{c.name}</div>
        <div className="cl-tag">{c.tagline}</div>
      </div>
      <div className="boot-bar">
        <div className="boot-fill" style={{ width: `${Math.round(p * 100)}%` }} />
      </div>
      <div className="boot-label">{loading?.label ?? ''}</div>
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
  game.startRace({ mode: app.mode, carId: app.carId, color, rivalLevel: app.mode === 'rival' ? (rival ?? app.rivalLevel) : undefined, ghost });
  app.set({ screen: 'race', result: null, paused: false });
}

/** [action, keyboard, gamepad] — also shown briefly at every race start */
export const CONTROL_ROWS: [string, string, string][] = [
  ['アクセル', 'W / ↑', 'RT / A'],
  ['ブレーキ・バック', 'S / ↓', 'LT / X'],
  ['ステアリング', 'A D / ← →', '左スティック'],
  ['サイドブレーキ', 'Space', 'B / RB'],
  ['シフトアップ / ダウン（MT時）', 'E / Q', 'Y / LB'],
  ['カメラ切替', 'C', '十字キー↑'],
  ['コースに復帰', 'R', 'Back'],
  ['ポーズ', 'Esc / P', 'Start'],
];

export function ControlsScreen() {
  const go = useApp((s) => s.go);
  useMenuInput((a) => {
    if (a === 'back' || a === 'confirm') { sfx.back(); go('modes'); }
  });
  const rows = CONTROL_ROWS;
  return (
    <div className="screen panel-screen">
      <div className="panel wide">
        <div className="panel-title">CONTROLS <small>操作方法</small></div>
        <table className="controls-table">
          <thead>
            <tr><th>操作</th><th>キーボード</th><th>ゲームパッド</th></tr>
          </thead>
          <tbody>
            {rows.map(([a, k, p]) => (
              <tr key={a}><td>{a}</td><td><kbd>{k}</kbd></td><td><kbd>{p}</kbd></td></tr>
            ))}
          </tbody>
        </table>
        <div className="drift-guide">
          <h3>ドリフトのコツ</h3>
          <ol>
            <li>コーナー手前でしっかり減速し、ステアを切り始める。</li>
            <li>ステアを切ったままアクセルを踏み込むか、Spaceを一瞬引いてリアを流す。</li>
            <li>車が向きを変えたら、カウンターステア（逆ハンドル）とアクセルで角度を保つ。</li>
            <li>出口が見えたらステアを戻してアクセル全開。</li>
          </ol>
          <p>運転アシスト「標準」ではカウンターステアとスピン防止が補助されます（設定で変更可）。</p>
        </div>
        <button className="cta small" onClick={() => go('modes')}>戻る</button>
      </div>
    </div>
  );
}

export function useLocalBestLabel() {
  const lb = loadLocalBest(currentCourseId());
  return lb ? `${formatTime(lb.timeMs)} (${CAR_SPECS[lb.carId].name})` : null;
}

function CarRecord({ id }: { id: CarId }) {
  const course = currentCourseId();
  const best = loadCarBests(course)[id] ?? null;
  const medal = best !== null ? medalFor(course, id, best) : null;
  const next = nextTarget(course, id, best);
  return (
    <div className="car-record">
      <div>
        <small>PERSONAL BEST</small>
        <b>{best !== null ? formatTime(best) : '--:--.---'}</b>
        {medal && <span className={`medal-dot medal-${medal}`}>{MEDAL_LABEL[medal]}</span>}
      </div>
      <div>
        <small>NEXT TARGET</small>
        {next ? (
          <b className={`medal-${next.medal}`}>{MEDAL_LABEL[next.medal]} {formatTime(next.timeMs)}</b>
        ) : (
          <b className="medal-gold">COMPLETE</b>
        )}
      </div>
    </div>
  );
}
