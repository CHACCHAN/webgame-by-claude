import { useEffect, useRef, useState } from 'react';
import { gameHolder } from '../GameCanvas';
import { useApp } from '../../store/app';
import { useSettings } from '../../store/settings';
import { formatTime, AI_LEVEL_LABEL } from '../format';
import { useMenuInput } from '../useMenuInput';
import { startRaceFromState } from '../screens/Menus';
import { sfx } from '../sfx';
import { AI_PROFILES } from '../../game/ai/AIDriver';

const TACH_START = 135, TACH_SWEEP = 270;
const polar = (cx: number, cy: number, r: number, deg: number) => {
  const a = ((deg - 90) * Math.PI) / 180;
  return [cx + r * Math.cos(a), cy + r * Math.sin(a)];
};
const arc = (cx: number, cy: number, r: number, a0: number, a1: number) => {
  const [x0, y0] = polar(cx, cy, r, a0);
  const [x1, y1] = polar(cx, cy, r, a1);
  return `M${x0},${y0} A${r},${r} 0 ${a1 - a0 > 180 ? 1 : 0} 1 ${x1},${y1}`;
};

export function Hud() {
  const { mode, rivalLevel, ghostChoice, phase } = useApp();
  const showFps = useSettings((s) => s.showFps);
  const refs = {
    time: useRef<HTMLDivElement>(null),
    speed: useRef<HTMLDivElement>(null),
    gear: useRef<HTMLDivElement>(null),
    rpmFill: useRef<SVGPathElement>(null),
    needle: useRef<SVGLineElement>(null),
    splits: useRef<HTMLDivElement>(null),
    countdown: useRef<HTMLDivElement>(null),
    wrong: useRef<HTMLDivElement>(null),
    drift: useRef<HTMLDivElement>(null),
    pos: useRef<HTMLDivElement>(null),
    gap: useRef<HTMLDivElement>(null),
    map: useRef<HTMLCanvasElement>(null),
    boost: useRef<HTMLDivElement>(null),
    fps: useRef<HTMLDivElement>(null),
    delta: useRef<HTMLDivElement>(null),
  };
  const [redline, setRedline] = useState(8000);
  const [turbo, setTurbo] = useState(false);

  useEffect(() => {
    const game = gameHolder.game;
    if (!game) return;
    setRedline(game.hud.redline);
    setTurbo(game.hud.turbo);
    // pre-render the course outline for the minimap
    const track = game.track;
    let minX = Infinity, maxX = -Infinity, minZ = Infinity, maxZ = -Infinity;
    for (let i = 0; i < track.count; i += 5) {
      minX = Math.min(minX, track.pos[i * 3]); maxX = Math.max(maxX, track.pos[i * 3]);
      minZ = Math.min(minZ, track.pos[i * 3 + 2]); maxZ = Math.max(maxZ, track.pos[i * 3 + 2]);
    }
    const W = 220, H = 140, pad = 10;
    const sc = Math.min((W - pad * 2) / (maxX - minX), (H - pad * 2) / (maxZ - minZ));
    const ox = (W - (maxX - minX) * sc) / 2, oz = (H - (maxZ - minZ) * sc) / 2;
    const toMap = (x: number, z: number) => [ox + (x - minX) * sc, oz + (z - minZ) * sc] as const;
    const outline = document.createElement('canvas');
    outline.width = W * 2;
    outline.height = H * 2;
    const og = outline.getContext('2d')!;
    og.scale(2, 2);
    og.lineCap = og.lineJoin = 'round';
    for (const [w, c] of [[5, 'rgba(0,0,0,0.6)'], [2.4, 'rgba(255,255,255,0.75)']] as const) {
      og.strokeStyle = c;
      og.lineWidth = w;
      og.beginPath();
      for (let i = 0; i < track.count; i += 4) {
        const [x, y] = toMap(track.pos[i * 3], track.pos[i * 3 + 2]);
        if (i === 0) og.moveTo(x, y);
        else og.lineTo(x, y);
      }
      og.stroke();
    }
    for (const s of [track.startS, track.finishS]) {
      const p = track.pointAt(s);
      const [x, y] = toMap(p.x, p.z);
      og.fillStyle = s === track.startS ? '#7dffb0' : '#ffffff';
      og.beginPath();
      og.arc(x, y, 3.5, 0, Math.PI * 2);
      og.fill();
    }

    let raf = 0;
    let lastSplits = -1;
    let frames = 0, fpsT = performance.now();
    const loop = () => {
      const h = game.hud;
      const r = refs;
      if (r.time.current) r.time.current.textContent = formatTime(h.raceTime * 1000);
      if (r.speed.current) r.speed.current.textContent = String(Math.round(h.speedKmh));
      if (r.gear.current) r.gear.current.textContent = h.gear === -1 ? 'R' : h.gear === 0 ? 'N' : String(h.gear);
      const rpmFrac = Math.min(1, h.rpm / (h.redline + 500));
      const ang = TACH_START + rpmFrac * TACH_SWEEP;
      if (r.rpmFill.current) r.rpmFill.current.setAttribute('d', arc(100, 100, 82, TACH_START, Math.max(TACH_START + 0.5, ang)));
      if (r.needle.current) r.needle.current.setAttribute('transform', `rotate(${ang} 100 100)`);
      if (r.rpmFill.current) r.rpmFill.current.classList.toggle('hot', h.rpm > h.redline * 0.93);
      if (r.boost.current) r.boost.current.style.width = `${Math.round(h.boost * 100)}%`;
      if (r.countdown.current) {
        const c = h.countdown;
        const show = c > 0 && c < 3.7;
        r.countdown.current.style.opacity = show ? '1' : '0';
        const n = Math.ceil(c);
        const txt = c > 3 ? '' : String(n);
        if (r.countdown.current.textContent !== txt) {
          r.countdown.current.textContent = txt;
          r.countdown.current.classList.remove('pop');
          void r.countdown.current.offsetWidth;
          r.countdown.current.classList.add('pop');
        }
      }
      if (r.wrong.current) r.wrong.current.style.opacity = h.wrongWay ? '1' : '0';
      if (r.drift.current) {
        const show = h.driftCombo > 20;
        r.drift.current.style.opacity = show ? '1' : '0';
        if (show) r.drift.current.querySelector('b')!.textContent = `+${Math.round(h.driftCombo)}`;
        r.drift.current.querySelector('i')!.textContent = String(h.driftScore);
      }
      if (r.pos.current && h.rivalProgress !== null) {
        r.pos.current.textContent = h.position === 1 ? '1ST' : '2ND';
        r.pos.current.className = `pos ${h.position === 1 ? 'lead' : 'chase'}`;
        if (r.gap.current) r.gap.current.textContent = `${h.gapMeters >= 0 ? '+' : ''}${Math.round(h.gapMeters)} m`;
      }
      if (r.splits.current && h.splits.length !== lastSplits) {
        lastSplits = h.splits.length;
        r.splits.current.innerHTML = h.splits
          .map((ms, i) => `<div class="split"><span>S${i + 1}</span><b>${formatTime(ms)}</b></div>`)
          .join('');
        if (r.delta.current && h.lastSplitIndex >= 0 && h.splits.length > 0) {
          const d = h.lastSplitDelta;
          r.delta.current.textContent = d === null ? `SECTOR ${h.lastSplitIndex + 1}  ${formatTime(h.splits[h.lastSplitIndex])}` : `${formatTime(d, { sign: true })}`;
          r.delta.current.className = `split-flash ${d === null ? '' : d <= 0 ? 'faster' : 'slower'}`;
          void r.delta.current.offsetWidth;
          r.delta.current.classList.add('show');
        }
      }
      // minimap
      const cv = r.map.current;
      if (cv) {
        const g = cv.getContext('2d')!;
        g.clearRect(0, 0, cv.width, cv.height);
        g.drawImage(outline, 0, 0);
        g.save();
        g.scale(2, 2);
        const dot = (s01: number | null, color: string, rad: number) => {
          if (s01 === null) return;
          const s = track.startS + s01 * (track.finishS - track.startS);
          const p = track.pointAt(s);
          const [x, y] = toMap(p.x, p.z);
          g.fillStyle = color;
          g.shadowColor = color;
          g.shadowBlur = 8;
          g.beginPath();
          g.arc(x, y, rad, 0, Math.PI * 2);
          g.fill();
        };
        dot(h.ghostProgress, '#7fd4ff', 3.5);
        dot(h.rivalProgress, '#ff5050', 4);
        dot(h.progress, '#ffb020', 4.5);
        g.restore();
      }
      frames++;
      const now = performance.now();
      if (now - fpsT > 500) {
        if (r.fps.current) r.fps.current.textContent = `${Math.round((frames * 1000) / (now - fpsT))} FPS`;
        frames = 0;
        fpsT = now;
      }
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const ticks = [];
  const steps = Math.ceil((redline + 500) / 1000);
  for (let i = 0; i <= steps; i++) {
    const rpm = i * 1000;
    const a = TACH_START + (rpm / (redline + 500)) * TACH_SWEEP;
    if (a > TACH_START + TACH_SWEEP + 0.1) break;
    const [x0, y0] = polar(100, 100, 92, a);
    const [x1, y1] = polar(100, 100, 80, a);
    const [tx, ty] = polar(100, 100, 66, a);
    ticks.push(
      <g key={i}>
        <line x1={x0} y1={y0} x2={x1} y2={y1} className={rpm >= redline ? 'tick red' : 'tick'} />
        <text x={tx} y={ty + 4} className="tick-label">{i}</text>
      </g>,
    );
  }
  const redStart = TACH_START + (redline / (redline + 500)) * TACH_SWEEP;

  return (
    <div className={`hud phase-${phase}`}>
      <div className="hud-tl">
        <div className="hud-label">TIME</div>
        <div className="hud-time" ref={refs.time}>0:00.000</div>
        <div className="hud-splits" ref={refs.splits} />
      </div>
      <div className="hud-tc">
        {mode === 'rival' && (
          <div className="versus">
            <div className="pos lead" ref={refs.pos}>1ST</div>
            <div className="vs-info">
              <small>VS {AI_LEVEL_LABEL[rivalLevel]}</small>
              <b>{AI_PROFILES[rivalLevel].name}</b>
              <span ref={refs.gap}>+0 m</span>
            </div>
          </div>
        )}
        {mode === 'ghost' && ghostChoice && (
          <div className="ghost-tag">
            👻 VS {ghostChoice.label} <b>{formatTime(ghostChoice.timeMs)}</b>
          </div>
        )}
        <div className="split-flash" ref={refs.delta} />
      </div>
      <div className="hud-tr">
        <canvas ref={refs.map} width={440} height={280} className="minimap" />
        {showFps && <div className="fps" ref={refs.fps} />}
      </div>
      <div className="countdown" ref={refs.countdown} />
      <div className="wrong-way" ref={refs.wrong}>逆走中 ― WRONG WAY</div>
      <div className="drift" ref={refs.drift}>
        <span>DRIFT</span>
        <b>+0</b>
        <small>TOTAL <i>0</i></small>
      </div>
      <div className="hud-br">
        <svg viewBox="0 0 200 200" className="tach">
          <path d={arc(100, 100, 82, TACH_START, TACH_START + TACH_SWEEP)} className="tach-bg" />
          <path d={arc(100, 100, 86, redStart, TACH_START + TACH_SWEEP)} className="tach-red" />
          <path ref={refs.rpmFill} d={arc(100, 100, 82, TACH_START, TACH_START + 1)} className="tach-fill" />
          {ticks}
          <line ref={refs.needle} x1="100" y1="100" x2="100" y2="24" className="needle" />
          <circle cx="100" cy="100" r="5" className="hub" />
          <text x="100" y="150" className="rpm-label">×1000 rpm</text>
        </svg>
        <div className="speedo">
          <div className="gear" ref={refs.gear}>1</div>
          <div className="speed" ref={refs.speed}>0</div>
          <div className="unit">km/h</div>
          {turbo && (
            <div className="boost">
              <small>BOOST</small>
              <div><div ref={refs.boost} /></div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export function PauseMenu() {
  const { go, set } = useApp();
  const [sel, setSel] = useState(0);
  const resume = () => {
    gameHolder.game?.setPaused(false);
    set({ paused: false });
  };
  const items = [
    { label: 'レースに戻る', action: resume },
    { label: 'リスタート', action: () => { gameHolder.game?.setPaused(false); set({ paused: false }); void startRaceFromState(); } },
    { label: '車両選択へ', action: () => { gameHolder.game?.setPaused(false); set({ paused: false }); go('garage'); } },
    { label: 'メインメニューへ', action: () => { gameHolder.game?.setPaused(false); set({ paused: false }); gameHolder.game?.startAttract(); go('modes'); } },
  ];
  useMenuInput((a) => {
    if (a === 'up') { setSel((s) => (s + items.length - 1) % items.length); sfx.move(); }
    if (a === 'down') { setSel((s) => (s + 1) % items.length); sfx.move(); }
    if (a === 'confirm') { sfx.confirm(); items[sel].action(); }
    if (a === 'back') resume();
  });
  return (
    <div className="screen pause">
      <div className="pause-box">
        <div className="pause-title">PAUSE</div>
        <ul className="menu-list compact">
          {items.map((it, i) => (
            <li key={it.label} className={i === sel ? 'active' : ''} onMouseEnter={() => setSel(i)} onClick={() => { sfx.confirm(); it.action(); }}>
              <span className="mi-jp big">{it.label}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
