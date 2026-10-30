import { useEffect, useState } from 'react';
import { gameHolder } from '../GameCanvas';
import { useApp } from '../../store/app';
import { useMenuInput } from '../useMenuInput';
import { CAR_ORDER, CAR_SPECS } from '../../game/vehicle/carSpecs';
import { AI_PROFILES, type AILevel } from '../../game/ai/AIDriver';
import { decodeGhost } from '../../game/race/Ghost';
import { api, loadLocalBest } from '../../api/client';
import { formatTime } from '../format';
import { sfx } from '../sfx';

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
    a?.startAmbient();
    sfx.confirm();
    go('modes');
  };
  useMenuInput((a) => {
    if (a === 'confirm') start();
  });
  return (
    <div className="screen title" onClick={start}>
      <div className="title-logo">
        <div className="title-small">OBORO PASS DOWNHILL</div>
        <h1>
          <span className="kanji">峠</span>
          <span className="en">TOUGE<br />NOCTURNE</span>
        </h1>
        <div className="title-jp">朧 峠 夜 想 曲</div>
      </div>
      <div className="press-start">PRESS ENTER / CLICK TO START</div>
      <div className="title-foot">
        <span>v1.0</span>
        <span>© 2026 Touge Nocturne Project ― 本作は架空の峠・車両・人物を描いたオリジナル作品です</span>
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
    { id: 'ta', label: 'TIME ATTACK', jp: 'タイムアタック', desc: '朧峠ダウンヒルを全開で駆け下り、自己ベストとオンラインランキング上位を狙う。', action: () => { set({ mode: 'time_attack', ghostChoice: null }); go('garage'); } },
    { id: 'rival', label: 'RIVAL BATTLE', jp: 'ライバルバトル', desc: '峠に棲む走り屋と1対1のダウンヒルバトル。先にゴールした方が勝ち。', action: () => { set({ mode: 'rival', ghostChoice: null }); go('garage'); } },
    { id: 'ghost', label: 'GHOST BATTLE', jp: 'ゴーストバトル', desc: 'ランキング上位者や自己ベストの走りを半透明のゴーストで再現。その背中を追え。', action: () => { set({ mode: 'ghost' }); go('leaderboard'); } },
    { id: 'rank', label: 'RANKING', jp: 'ランキング', desc: 'オンラインランキングを確認する。', action: () => { set({ mode: 'time_attack' }); go('leaderboard'); } },
    { id: 'settings', label: 'SETTINGS', jp: '設定', desc: 'グラフィック品質、時間帯、サウンド、運転アシスト。', action: () => go('settings') },
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
  }, []);
  return (
    <div className="screen menu-screen">
      <div className="side-panel">
        <div className="panel-heading">
          <span className="kanji-badge">峠</span>
          <div>
            <div className="ph-en">MAIN MENU</div>
            <div className="ph-jp">朧峠 ダウンヒル</div>
          </div>
        </div>
        <ul className="menu-list">
          {items.map((it, i) => (
            <li
              key={it.id}
              className={i === idx ? 'active' : ''}
              onMouseEnter={() => setIdx(i)}
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

const COLORS: Record<string, string[]> = {
  hayate: ['#e8e6e1', '#b3121c', '#1b1d22', '#2f6db5', '#e0b400'],
  raijin: ['#1d4fa8', '#d6d9de', '#0c0c0e', '#8f1218', '#5e6b3a'],
  shiden: ['#c8102e', '#f2f2f0', '#121214', '#f2a900', '#3a7d44'],
};

export function GarageScreen() {
  const { go, set, carId, mode, carColor } = useApp();
  const [i, setI] = useState(CAR_ORDER.indexOf(carId));
  const id = CAR_ORDER[i];
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
  const cycleColor = (d: number) => {
    const k = (palette.indexOf(color) + d + palette.length) % palette.length;
    set({ carColor: palette[k] });
    sfx.move();
  };
  const confirm = () => {
    sfx.confirm();
    if (mode === 'rival') go('rivals');
    else startRaceFromState();
  };
  useMenuInput((a) => {
    if (a === 'left') { setI((x) => (x + CAR_ORDER.length - 1) % CAR_ORDER.length); sfx.move(); }
    if (a === 'right') { setI((x) => (x + 1) % CAR_ORDER.length); sfx.move(); }
    if (a === 'up') cycleColor(-1);
    if (a === 'down') cycleColor(1);
    if (a === 'confirm') confirm();
    if (a === 'back') { sfx.back(); go(mode === 'ghost' ? 'leaderboard' : 'modes'); }
  });
  const stat = (label: string, v: number) => (
    <div className="stat" key={label}>
      <span>{label}</span>
      <div className="stat-bar">
        <div style={{ width: `${v * 10}%` }} />
      </div>
      <b>{v}</b>
    </div>
  );
  return (
    <div className="screen garage">
      <div className="garage-top">
        <div className="crumb">SELECT YOUR CAR ― 車両選択</div>
      </div>
      <div className="garage-card">
        <div className="car-index">0{i + 1} / 0{CAR_ORDER.length}</div>
        <h2 className="car-name">{spec.name}</h2>
        <div className="car-tag">{spec.tagline} ・ {spec.drive}</div>
        <p className="car-desc">{spec.description}</p>
        <div className="stats">
          {stat('POWER', spec.stats.power)}
          {stat('GRIP', spec.stats.grip)}
          {stat('DRIFT', spec.stats.drift)}
          {stat('LIGHTNESS', spec.stats.weight)}
        </div>
        <div className="specs-row">
          <div><small>MAX TORQUE</small><b>{Math.max(...spec.engine.torque.map((t) => t[1]))} Nm</b></div>
          <div><small>WEIGHT</small><b>{spec.mass} kg</b></div>
          <div><small>REDLINE</small><b>{spec.engine.redline} rpm</b></div>
        </div>
        <div className="colors">
          {palette.map((c) => (
            <button key={c} className={c === color ? 'swatch on' : 'swatch'} style={{ background: c }} onClick={() => set({ carColor: c })} aria-label={`color ${c}`} />
          ))}
        </div>
        <button className="cta" onClick={confirm}>
          {mode === 'rival' ? 'ライバルを選ぶ' : 'この車で出走'} <span>▶</span>
        </button>
      </div>
      <button className="arrow left" onClick={() => setI((x) => (x + CAR_ORDER.length - 1) % CAR_ORDER.length)}>‹</button>
      <button className="arrow right" onClick={() => setI((x) => (x + 1) % CAR_ORDER.length)}>›</button>
      <Hint items={[['←→', '車両'], ['↑↓', 'カラー'], ['Enter', '決定'], ['Esc', '戻る']]} />
    </div>
  );
}

export function RivalsScreen() {
  const { go, set, rivalLevel } = useApp();
  const levels: AILevel[] = ['rookie', 'ace', 'legend'];
  const [i, setI] = useState(levels.indexOf(rivalLevel));
  const desc: Record<AILevel, string> = {
    rookie: '免許を取ったばかりの新人。ラインは甘いが、峠への情熱は本物。',
    ace: '朧峠を知り尽くした地元最速の男。ミスを待っていても勝てない。',
    legend: '夜明け前にだけ現れるという白い影。誰も、その背中に追いついたことがない。',
  };
  const car: Record<AILevel, string> = { rookie: 'HAYATE TR-S', ace: 'RAIJIN GT-X', legend: 'SHIDEN RS' };
  const start = () => {
    set({ rivalLevel: levels[i] });
    sfx.confirm();
    startRaceFromState(levels[i]);
  };
  useMenuInput((a) => {
    if (a === 'left' || a === 'up') { setI((x) => (x + 2) % 3); sfx.move(); }
    if (a === 'right' || a === 'down') { setI((x) => (x + 1) % 3); sfx.move(); }
    if (a === 'confirm') start();
    if (a === 'back') { sfx.back(); go('garage'); }
  });
  return (
    <div className="screen rivals">
      <div className="crumb center">CHOOSE YOUR RIVAL ― 対戦相手</div>
      <div className="rival-cards">
        {levels.map((l, k) => {
          const p = AI_PROFILES[l];
          return (
            <div key={l} className={`rival-card ${l} ${k === i ? 'active' : ''}`} onMouseEnter={() => setI(k)} onClick={() => { setI(k); start(); }}>
              <div className="rc-level">{['★', '★★', '★★★'][k]}</div>
              <div className="rc-title">{p.title}</div>
              <div className="rc-name">{p.name}</div>
              <div className="rc-car">{car[l]}</div>
              <p>{desc[l]}</p>
            </div>
          );
        })}
      </div>
      <Hint items={[['←→', '選択'], ['Enter', 'バトル開始'], ['Esc', '戻る']]} />
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
        const lb = loadLocalBest();
        if (lb) ghost = { data: await decodeGhost(lb.ghost), label: '自己ベスト', carId: lb.carId, timeMs: lb.timeMs, splits: lb.splits };
      } else {
        const g = await api.ghost(app.ghostChoice.runId);
        ghost = { data: await decodeGhost(g), label: g.player_name, carId: g.car_id, timeMs: g.time_ms, splits: g.sector_ms };
      }
    } else if (app.mode === 'time_attack') {
      const lb = loadLocalBest();
      if (lb) ghost = { data: await decodeGhost(lb.ghost), label: '自己ベスト', carId: lb.carId, timeMs: lb.timeMs, splits: lb.splits };
    }
  } catch (e) {
    console.warn('ghost unavailable', e);
  }
  game.initAudio();
  game.startRace({ mode: app.mode, carId: app.carId, rivalLevel: app.mode === 'rival' ? (rival ?? app.rivalLevel) : undefined, ghost });
  app.set({ screen: 'race', result: null, paused: false });
}

export function ControlsScreen() {
  const go = useApp((s) => s.go);
  useMenuInput((a) => {
    if (a === 'back' || a === 'confirm') { sfx.back(); go('modes'); }
  });
  const rows: [string, string, string][] = [
    ['アクセル', 'W / ↑', 'RT / A'],
    ['ブレーキ・バック', 'S / ↓', 'LT / X'],
    ['ステアリング', 'A D / ← →', '左スティック'],
    ['サイドブレーキ', 'Space', 'B / RB'],
    ['シフトアップ / ダウン（MT時）', 'E / Q', 'Y / LB'],
    ['カメラ切替', 'C', '十字キー↑'],
    ['コースに復帰', 'R', 'Back'],
    ['ポーズ', 'Esc / P', 'Start'],
  ];
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
  const lb = loadLocalBest();
  return lb ? `${formatTime(lb.timeMs)} (${CAR_SPECS[lb.carId].name})` : null;
}
