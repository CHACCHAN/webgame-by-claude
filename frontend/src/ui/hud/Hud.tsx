import { useEffect, useRef, useState } from 'react';
import { gameHolder } from '../GameCanvas';
import { useApp } from '../../store/app';
import { useSettings } from '../../store/settings';
import { formatTime, AI_LEVEL_LABEL } from '../format';
import { useMenuInput, hoverSelect } from '../useMenuInput';
import { startRaceFromState } from '../screens/Menus';
import { sfx } from '../sfx';
import { COURSES } from '../../game/track/courses';
import { currentCourseId } from '../../store/settings';
import { fullscreenSupported, toggleFullscreen, useFullscreen } from '../fullscreen';
import { CONTROL_ROWS, Portrait } from '../screens/Menus';
import type { Game, HudState } from '../../game/Game';
import { leaveRoom } from '../../store/online';
import { SLOT_COLORS } from '../../game/net/RemoteRacers';
import { FocusFrame, Hint } from '../kit';
import { motionOn } from '../motion';

/**
 * The rev band: a flat arc over the speed, its centre far below the cluster. Angles in degrees from straight up;
 * the band is one path whose length is normalised to 100, so a rev figure is a single dash offset per frame.
 */
const TACH = { cx: 160, cy: 646, r: 600, half: 13.7 };
const tachPoint = (deg: number, r = TACH.r) => {
  const a = (deg * Math.PI) / 180;
  return [TACH.cx + r * Math.sin(a), TACH.cy - r * Math.cos(a)] as const;
};
const tachArc = (f0: number, f1: number, r = TACH.r) => {
  const [x0, y0] = tachPoint(-TACH.half + f0 * 2 * TACH.half, r);
  const [x1, y1] = tachPoint(-TACH.half + f1 * 2 * TACH.half, r);
  return `M${x0.toFixed(1)},${y0.toFixed(1)} A${r},${r} 0 0 1 ${x1.toFixed(1)},${y1.toFixed(1)}`;
};

const CORNER_LABEL = { hairpin: ['ヘアピン', 'HAIRPIN'], tight: ['急カーブ', 'SHARP'], medium: ['カーブ', 'BEND'] } as const;

/** Pace note for the next tight bend (DOM updated directly every frame). */
function updateCornerNote(el: HTMLDivElement | null, c: HudState['corner']) {
  if (!el) return;
  if (!c) {
    el.classList.remove('show');
    return;
  }
  const key = `${c.seq}`;
  if (el.dataset.seq !== key) {
    el.dataset.seq = key;
    el.dataset.kind = c.kind;
    el.dataset.dir = c.dir > 0 ? 'left' : 'right';
    const [jp, en] = CORNER_LABEL[c.kind];
    const side = c.dir > 0 ? '左' : '右';
    el.querySelector('.cn-text b')!.textContent = `${side}${jp}`;
    el.querySelector('.cn-text small')!.textContent = `${en} ${c.dir > 0 ? 'LEFT' : 'RIGHT'}`;
    el.classList.remove('show');
    void el.offsetWidth;
  }
  el.classList.add('show');
  const d = el.querySelector('.cn-dist')!;
  const txt = c.dist > 8 ? `${Math.round(c.dist / 10) * 10}m` : '';
  if (d.textContent !== txt) d.textContent = txt;
}

/** Online battle order (built with DOM nodes: player names are user input). */
function updateStandings(el: HTMLOListElement | null, rows: HudState['online']) {
  if (!el) return;
  const list = rows ?? [];
  const lead = list.find((r) => r.finMs === null)?.s ?? 0;
  const cells = list.map((r, k) => [
    String(k + 1),
    r.name,
    r.finMs !== null ? formatTime(r.finMs) : r.lost ? '通信切断' : k === 0 || r.s >= lead ? '' : `-${Math.round(lead - r.s)} m`,
    SLOT_COLORS[r.slot % SLOT_COLORS.length],
    `${r.me ? 'me' : ''}${r.lost ? ' lost' : ''}`,
  ]);
  const key = JSON.stringify(cells);
  if (el.dataset.key === key) return;
  el.dataset.key = key;
  el.replaceChildren(
    ...cells.map(([pos, name, info, color, cls]) => {
      const li = document.createElement('li');
      li.className = cls;
      const p = document.createElement('span');
      p.className = 'pos';
      p.textContent = pos;
      const chip = document.createElement('i');
      chip.style.background = color;
      const b = document.createElement('b');
      b.textContent = name;
      const em = document.createElement('em');
      em.textContent = info;
      li.append(p, chip, b, em);
      return li;
    }),
  );
}

/**
 * The numbers of an online race's connections (off by default: the N key or a tap on the live order shows them,
 * `?netstats=1` too; remembered). Per player: round trip and its jitter, share of packets lost, packets per second,
 * how far past the newest packet the car is drawn (and in what share of the frames), how far a new packet moves
 * the prediction, and how far behind the present the car is drawn (with the delay a buffer would need).
 */
const NET_STATS_KEY = 'touge-netstats';
let netStatsOn = false;
try {
  netStatsOn = new URLSearchParams(location.search).get('netstats') === '1' || localStorage.getItem(NET_STATS_KEY) === '1';
} catch {
  // (no storage: off)
}
function toggleNetStats() {
  netStatsOn = !netStatsOn;
  try {
    localStorage.setItem(NET_STATS_KEY, netStatsOn ? '1' : '0');
  } catch {
    // (not remembered)
  }
}
let netStatsAt = 0;
function updateNetStats(el: HTMLPreElement | null, game: Game) {
  if (!el) return;
  if (!netStatsOn) {
    if (el.textContent) el.textContent = '';
    netStatsAt = 0;
    return;
  }
  // twice a second: these are for reading, not for watching
  const now = performance.now();
  if (now - netStatsAt < 500) return;
  netStatsAt = now;
  const names = new Map(game.remotes.standings().map((r) => [r.id, r.name]));
  const ms = (v: number) => `${Math.round(v)} ms`;
  const lines = game.net.stats().map((s) => {
    const cm = (v: number) => (v * 100).toFixed(v < 0.1 ? 1 : 0);
    return (
      `${names.get(s.id) ?? s.id}\n` +
      `  往復 ${s.synced ? ms(s.rtt) : '—'}  ゆらぎ ${ms(s.jitter)}  欠落 ${(s.loss * 100).toFixed(1)} %\n` +
      `  受信 ${s.rate.toFixed(0)} Hz / ${ms(s.interval)}  外挿 ${Math.round(s.ahead * 100)} % ${ms(s.horizon)}\n` +
      `  補正 ${cm(s.correction)} / ${cm(s.correctionMax)} cm  遅延 ${ms(s.lag)} (要 ${ms(s.bufferDelay)})`
    );
  });
  const worse = game.net.impaired?.recv ?? game.net.impaired?.send;
  if (worse) lines.push(`回線を悪化中: 片道 ${worse.delay}±${worse.jitter} ms  欠落 ${(worse.loss * 100).toFixed(0)} %`);
  const text = lines.join('\n');
  if (el.textContent !== text) el.textContent = text;
}

/** a design token's colour for the canvases (`--c-cyan` → "56 232 255") */
const token = (name: string) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

/**
 * The race's instruments. Everything that changes while driving is written straight to the DOM in one animation
 * frame callback (no React state per frame), and only what changed: text when its string differs, the rev band as
 * one dash offset, bars as transforms. Nothing here lays the page out again while the car is moving.
 */
export function Hud() {
  const { mode, rivalLevel, ghostChoice, phase } = useApp();
  const showFps = useSettings((s) => s.showFps);
  const guideOn = useSettings((s) => s.controlsGuide !== false);
  const autoShift = useSettings((s) => s.autoShift);
  const refs = {
    root: useRef<HTMLDivElement>(null),
    time: useRef<HTMLDivElement>(null),
    prog: useRef<HTMLElement>(null),
    speed: useRef<HTMLDivElement>(null),
    gear: useRef<HTMLDivElement>(null),
    cluster: useRef<HTMLDivElement>(null),
    rpmFill: useRef<SVGPathElement>(null),
    splits: useRef<HTMLDivElement>(null),
    countdown: useRef<HTMLDivElement>(null),
    cdBar: useRef<HTMLElement>(null),
    wrong: useRef<HTMLDivElement>(null),
    drift: useRef<HTMLDivElement>(null),
    pos: useRef<HTMLDivElement>(null),
    gap: useRef<HTMLDivElement>(null),
    line: useRef<HTMLDivElement>(null),
    map: useRef<HTMLCanvasElement>(null),
    boost: useRef<HTMLDivElement>(null),
    fps: useRef<HTMLDivElement>(null),
    delta: useRef<HTMLDivElement>(null),
    lines: useRef<HTMLCanvasElement>(null),
    corner: useRef<HTMLDivElement>(null),
    standings: useRef<HTMLOListElement>(null),
    net: useRef<HTMLPreElement>(null),
    guide: useRef<HTMLDivElement>(null),
  };
  const [redline, setRedline] = useState(8000);
  const [turbo, setTurbo] = useState(false);
  const [sectors, setSectors] = useState<number[]>([]);

  useEffect(() => {
    const game = gameHolder.game;
    if (!game) return;
    setRedline(game.hud.redline);
    setTurbo(game.hud.turbo);
    const track = game.track;
    const timed = track.finishS - track.startS;
    // where the sector lines cross the progress bar (the last one is the finish)
    setSectors(track.sectorSplits.slice(0, -1).map((s) => (s - track.startS) / timed));
    const cyan = token('--c-cyan'), magenta = token('--c-magenta'), steel = token('--c-steel'), ink = token('--c-void'), text = token('--c-text'), green = token('--c-green');
    // pre-render the course outline for the minimap
    let minX = Infinity, maxX = -Infinity, minZ = Infinity, maxZ = -Infinity;
    for (let i = 0; i < track.count; i += 5) {
      minX = Math.min(minX, track.pos[i * 3]); maxX = Math.max(maxX, track.pos[i * 3]);
      minZ = Math.min(minZ, track.pos[i * 3 + 2]); maxZ = Math.max(maxZ, track.pos[i * 3 + 2]);
    }
    const W = 220, H = 140, pad = 12;
    const sc = Math.min((W - pad * 2) / (maxX - minX), (H - pad * 2) / (maxZ - minZ));
    const ox = (W - (maxX - minX) * sc) / 2, oz = (H - (maxZ - minZ) * sc) / 2;
    const toMap = (x: number, z: number) => [ox + (x - minX) * sc, oz + (z - minZ) * sc] as const;
    const outline = document.createElement('canvas');
    outline.width = W * 2;
    outline.height = H * 2;
    const og = outline.getContext('2d')!;
    og.scale(2, 2);
    og.lineCap = og.lineJoin = 'round';
    for (const [w, c] of [[5.5, `rgb(${ink} / 0.8)`], [2.2, `rgb(${text} / 0.85)`]] as const) {
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
      og.fillStyle = s === track.startS ? `rgb(${green})` : `rgb(${text})`;
      og.fillRect(x - 3, y - 3, 6, 6);
    }

    let raf = 0;
    let lastSplits = -1;
    const deltas: (number | null)[] = [];
    let wasCounting = false, booted = false, goUntil = 0, lastCount = '';
    let typed = { seq: '', at: 0, n: -1 };
    let lastGear = '', lastSpeed = '', lastTime = '', lastGap = '', lastPos = 0, hot = false, lastDash = -1, lastProg = -1, lastBoost = -1, lastBar = -1;
    const streaks = Array.from({ length: 46 }, () => ({ a: Math.random() * Math.PI * 2, r: Math.random(), v: 0.6 + Math.random() }));
    let frames = 0, fpsT = performance.now();
    const loop = () => {
      const h = game.hud;
      const r = refs;
      const now = performance.now();
      // ---- the grid: the instruments power on once per start
      const counting = h.countdown > 0;
      if (counting && !booted) {
        booted = true;
        const root = r.root.current;
        if (root) {
          root.classList.remove('power-up');
          void root.offsetWidth;
          root.classList.add('power-up');
        }
        if (motionOn()) sfx.boot();
      }
      if (!counting && h.raceTime > 2) booted = false;
      // ---- clock, progress along the course
      const time = formatTime(h.raceTime * 1000);
      if (r.time.current && time !== lastTime) r.time.current.textContent = lastTime = time;
      const prog = Math.round(Math.max(0, Math.min(1, h.progress)) * 500) / 500;
      if (r.prog.current && prog !== lastProg) r.prog.current.style.transform = `scaleX(${(lastProg = prog)})`;
      // ---- speed, gear, revs
      const speed = String(Math.round(h.speedKmh));
      if (r.speed.current && speed !== lastSpeed) {
        r.speed.current.textContent = lastSpeed = speed;
        // four digits (the cockroach at Mach 1) in a smaller face
        r.speed.current.classList.toggle('wide', h.speedKmh >= 999.5);
      }
      const gear = h.gear === -1 ? 'R' : h.gear === 0 ? 'N' : String(h.gear);
      if (r.gear.current && gear !== lastGear) r.gear.current.textContent = lastGear = gear;
      const dash = Math.round((1 - Math.min(1, h.rpm / (h.redline + 500))) * 400) / 4;
      if (r.rpmFill.current && dash !== lastDash) r.rpmFill.current.style.strokeDashoffset = String((lastDash = dash));
      // the shift point: the band and the gear turn hot just before the red
      const isHot = h.rpm > h.redline * 0.93;
      if (isHot !== hot) r.cluster.current?.classList.toggle('hot', (hot = isHot));
      const boost = Math.round(h.boost * 50) / 50;
      if (r.boost.current && boost !== lastBoost) r.boost.current.style.transform = `scaleX(${(lastBoost = boost)})`;
      // ---- countdown: READY, 3, 2, 1 with the game's own beeps, GO as the clock starts
      const cd = r.countdown.current;
      if (cd) {
        if (wasCounting && !counting) goUntil = now + 900;
        wasCounting = counting;
        const c = h.countdown;
        const txt = counting ? (c > 3 ? 'READY' : String(Math.ceil(c))) : now < goUntil ? 'GO' : '';
        if (txt !== lastCount) {
          lastCount = txt;
          cd.dataset.n = txt;
          cd.firstElementChild!.textContent = txt;
          cd.classList.toggle('show', txt !== '');
          cd.classList.remove('pop');
          void cd.offsetWidth;
          if (txt) cd.classList.add('pop');
        }
        // the second running out under the numeral
        const bar = counting && c <= 3 ? Math.round((c - Math.floor(c - 1e-6)) * 60) / 60 : 0;
        if (r.cdBar.current && bar !== lastBar) r.cdBar.current.style.transform = `scaleX(${(lastBar = bar)})`;
      }
      if (r.wrong.current) r.wrong.current.classList.toggle('show', h.wrongWay);
      updateCornerNote(r.corner.current, h.corner);
      updateStandings(r.standings.current, h.online);
      updateNetStats(r.net.current, game);
      if (r.guide.current) {
        // during the countdown and the first seconds of the race, then it fades away
        const show = guideOn && (h.countdown > 0 || h.raceTime < 8);
        r.guide.current.classList.toggle('show', show);
        const pad = Array.from(navigator.getGamepads?.() ?? []).some((p) => p?.connected);
        r.guide.current.classList.toggle('pad', pad);
      }
      if (r.drift.current) {
        const show = h.driftCombo > 20;
        r.drift.current.classList.toggle('show', show);
        if (show) {
          const combo = `+${Math.round(h.driftCombo)}`;
          const b = r.drift.current.querySelector('b')!;
          if (b.textContent !== combo) b.textContent = combo;
          const total = String(h.driftScore);
          const i = r.drift.current.querySelector('i')!;
          if (i.textContent !== total) i.textContent = total;
        }
      }
      if (r.pos.current && h.rivalProgress !== null) {
        if (h.position !== lastPos) {
          lastPos = h.position;
          r.pos.current.textContent = h.position === 1 ? '1ST' : '2ND';
          r.pos.current.className = `pos ${h.position === 1 ? 'lead' : 'chase'}`;
        }
        const gap = `${h.gapMeters >= 0 ? '+' : ''}${Math.round(h.gapMeters)} m`;
        if (r.gap.current && gap !== lastGap) r.gap.current.textContent = lastGap = gap;
      }
      // the rival's line before the start, typed out as it comes over the radio: shown while the game keeps it
      const line = r.line.current, said = h.rivalLine?.moment === 'before' ? h.rivalLine : null;
      if (line) {
        const seq = String(said?.seq ?? '');
        if (typed.seq !== seq) {
          typed = { seq, at: now, n: -1 };
          line.dataset.seq = seq;
          line.parentElement!.classList.toggle('show', !!said);
        }
        if (said) {
          const chars = [...said.text];
          const n = motionOn() ? Math.min(chars.length, Math.floor((now - typed.at) / 32)) : chars.length;
          if (n !== typed.n) {
            typed.n = n;
            line.textContent = `「${chars.slice(0, n).join('')}」`;
            if (n < chars.length && n % 2 === 1) sfx.type();
          }
        }
      }
      if (r.splits.current && h.splits.length !== lastSplits) {
        lastSplits = h.splits.length;
        if (h.lastSplitIndex >= 0 && h.splits.length > 0) deltas[h.lastSplitIndex] = h.lastSplitDelta;
        if (h.splits.length === 0) deltas.length = 0;
        r.splits.current.innerHTML = h.splits
          .map((ms, i) => {
            const d = deltas[i];
            const delta = d === null || d === undefined ? '' : `<em class="${d <= 0 ? 'faster' : 'slower'}">${formatTime(d, { sign: true })}</em>`;
            return `<div class="split"><span>S${i + 1}</span><b>${formatTime(ms)}</b>${delta}</div>`;
          })
          .join('');
        if (r.delta.current && h.lastSplitIndex >= 0 && h.splits.length > 0) {
          const d = h.lastSplitDelta;
          const el = r.delta.current;
          el.innerHTML =
            `<small>SECTOR ${h.lastSplitIndex + 1}</small><b>${formatTime(h.splits[h.lastSplitIndex])}</b>` +
            (d === null ? '' : `<em>${formatTime(d, { sign: true })}</em><i>${d <= 0 ? 'AHEAD' : 'BEHIND'}</i>`);
          el.className = `split-flash ${d === null ? '' : d <= 0 ? 'faster' : 'slower'}`;
          void el.offsetWidth;
          el.classList.add('show');
        }
      }
      // speed lines towards the screen edges at high speed
      const lc = r.lines.current;
      if (lc) {
        if (lc.width !== lc.clientWidth || lc.height !== lc.clientHeight) {
          lc.width = lc.clientWidth;
          lc.height = lc.clientHeight;
        }
        const w = lc.width, hh = lc.height;
        const lg = lc.getContext('2d')!;
        lg.clearRect(0, 0, w, hh);
        const k = Math.max(0, Math.min(1, (h.speedKmh - 115) / 110));
        if (k > 0) {
          const cx = w / 2, cy = hh * 0.46, R = Math.hypot(w, hh) / 2;
          lg.lineWidth = 1.5;
          for (const st of streaks) {
            st.r += st.v * 0.045 * (0.5 + k);
            if (st.r > 1) { st.r = 0.55; st.a = Math.random() * Math.PI * 2; }
            const r0 = R * st.r, r1 = r0 + R * 0.12 * k * st.v;
            lg.strokeStyle = `rgb(${text} / ${((0.05 + 0.13 * k) * (st.r - 0.5) * 2).toFixed(3)})`;
            lg.beginPath();
            lg.moveTo(cx + Math.cos(st.a) * r0, cy + Math.sin(st.a) * r0 * 0.75);
            lg.lineTo(cx + Math.cos(st.a) * r1, cy + Math.sin(st.a) * r1 * 0.75);
            lg.stroke();
          }
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
        const dot = (s01: number | null, color: string, rad: number, ring = false) => {
          if (s01 === null) return;
          const s = track.startS + Math.max(0, Math.min(1, s01)) * timed;
          const p = track.pointAt(s);
          const [x, y] = toMap(p.x, p.z);
          g.fillStyle = color;
          g.shadowColor = color;
          g.shadowBlur = 8;
          g.beginPath();
          g.arc(x, y, rad, 0, Math.PI * 2);
          g.fill();
          if (ring) {
            g.shadowBlur = 0;
            g.strokeStyle = color;
            g.lineWidth = 1;
            g.beginPath();
            g.arc(x, y, rad + 3.5, 0, Math.PI * 2);
            g.stroke();
          }
        };
        dot(h.ghostProgress, `rgb(${steel})`, 3.5);
        dot(h.rivalProgress, `rgb(${magenta})`, 4);
        // online: the others, in the paint of their grid slots
        if (h.online) for (const o of h.online) if (!o.me && !o.lost) dot((o.s - track.startS) / timed, SLOT_COLORS[o.slot % SLOT_COLORS.length], 3.5);
        dot(h.progress, `rgb(${cyan})`, 4.5, true);
        g.restore();
      }
      frames++;
      if (now - fpsT > 500) {
        if (r.fps.current) r.fps.current.textContent = `${Math.round((frames * 1000) / (now - fpsT))} FPS`;
        frames = 0;
        fpsT = now;
      }
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    // the connection numbers of an online race: N, or a tap on the live order
    const onKey = (e: KeyboardEvent) => {
      if (e.code === 'KeyN' && !e.repeat && useApp.getState().mode === 'online') toggleNetStats();
    };
    const order = refs.standings.current;
    window.addEventListener('keydown', onKey);
    order?.addEventListener('click', toggleNetStats);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener('keydown', onKey);
      order?.removeEventListener('click', toggleNetStats);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // the rev band's scale: a tick and a figure per 1000 rpm, the red zone, the shift point
  const span = redline + 500;
  const ticks = [];
  for (let i = 0; i * 1000 <= span; i++) {
    const deg = -TACH.half + ((i * 1000) / span) * 2 * TACH.half;
    const [x0, y0] = tachPoint(deg, TACH.r + 11);
    const [x1, y1] = tachPoint(deg, TACH.r + 17);
    const [tx, ty] = tachPoint(deg, TACH.r + 27);
    ticks.push(
      <g key={i} className={i * 1000 >= redline ? 'red' : ''}>
        <line x1={x0} y1={y0} x2={x1} y2={y1} className="tick" />
        <text x={tx} y={ty + 3.5} className="tick-label">{i}</text>
      </g>,
    );
  }
  const [sx, sy] = tachPoint(-TACH.half + ((redline * 0.93) / span) * 2 * TACH.half, TACH.r - 14);
  const rival = mode === 'rival' ? COURSES[currentCourseId()].rivals[rivalLevel] : null;

  return (
    <div className={`hud phase-${phase}`} ref={refs.root}>
      <canvas className="speedlines" ref={refs.lines} />
      <div className="hud-tl">
        <div className="hud-clock">
          <div className="hud-label">TIME</div>
          <div className="hud-time" ref={refs.time}>0:00.000</div>
          <div className="hud-prog">
            <i ref={refs.prog} />
            {sectors.map((s) => <u key={s} style={{ left: `${(s * 100).toFixed(2)}%` }} />)}
          </div>
        </div>
        {/* online: the live order (up to five) under the clock, clear of the bend warning in the middle */}
        {mode === 'online' && <ol className="online-standings" ref={refs.standings} />}
        {mode === 'online' && <pre className="net-stats" ref={refs.net} />}
        <div className="hud-splits" ref={refs.splits} />
      </div>
      <div className="hud-tc">
        {rival && (
          <div className="versus">
            <div className="pos lead" ref={refs.pos}>1ST</div>
            <Portrait src={rival.portrait} className="vs-portrait" />
            <div className="vs-info">
              <small>VS {AI_LEVEL_LABEL[rivalLevel]}</small>
              <b>{rival.name}</b>
              <span ref={refs.gap}>+0 m</span>
            </div>
          </div>
        )}
        {rival && (
          <div className="vs-radio">
            <small>{rival.name}</small>
            <div className="vs-line" ref={refs.line} />
          </div>
        )}
        {mode === 'ghost' && ghostChoice && (
          <div className="ghost-tag">
            <small>GHOST</small> {ghostChoice.label} <b>{formatTime(ghostChoice.timeMs)}</b>
          </div>
        )}
        <div className="split-flash" ref={refs.delta} />
      </div>
      <div className="hud-tr">
        <div className="minimap-box">
          <canvas ref={refs.map} width={440} height={280} className="minimap" />
        </div>
        {showFps && <div className="fps" ref={refs.fps} />}
      </div>
      <div className="countdown" ref={refs.countdown}>
        <b />
        <i><i ref={refs.cdBar} /></i>
      </div>
      <div className="wrong-way" ref={refs.wrong}>
        <b>逆走中</b>
        <small>WRONG WAY</small>
      </div>
      {guideOn && (
        <div className="start-guide" ref={refs.guide}>
          {CONTROL_ROWS.filter(([a]) => !a.includes('MT時') || !autoShift).map(([action, key, padKey]) => (
            <div key={action}>
              <kbd className="k-key">{key}</kbd>
              <kbd className="k-pad">{padKey}</kbd>
              <span>{action}</span>
            </div>
          ))}
        </div>
      )}
      <div className="corner-note" ref={refs.corner}>
        <svg viewBox="0 0 100 100" className="cn-sign">
          <polygon points="50,3 97,50 50,97 3,50" className="cn-plate" />
          <polygon points="50,10 90,50 50,90 10,50" className="cn-rim" />
          <g className="cn-arrow cn-hairpin">
            <path d="M61 76 V46 A11 11 0 0 0 39 46 V60" />
            <polygon points="30,58 48,58 39,72" />
          </g>
          <g className="cn-arrow cn-tight">
            <path d="M60 76 V44 H42" />
            <polygon points="44,34 28,44 44,54" />
          </g>
          <g className="cn-arrow cn-medium">
            <path d="M58 76 V58 Q58 40 40 36" />
            <polygon points="43,27 28,35 42,45" />
          </g>
        </svg>
        <div className="cn-text">
          <b />
          <small />
        </div>
        <div className="cn-dist" />
      </div>
      <div className="drift" ref={refs.drift}>
        <span>DRIFT</span>
        <b>+0</b>
        <small>TOTAL <i>0</i></small>
      </div>
      <div className="hud-br" ref={refs.cluster}>
        <svg viewBox="0 0 320 76" className="tach">
          <path d={tachArc(0, 1)} className="tach-bg" />
          <path d={tachArc(0, 1)} className="tach-off" />
          <path d={tachArc(redline / span, 1, TACH.r + 10)} className="tach-red" />
          <path ref={refs.rpmFill} d={tachArc(0, 1)} className="tach-fill" pathLength={100} />
          {/* the band cut into segments */}
          <path d={tachArc(0, 1)} className="tach-comb" pathLength={100} />
          {ticks}
          <polygon points={`${sx.toFixed(1)},${(sy - 5).toFixed(1)} ${(sx - 4).toFixed(1)},${(sy + 2).toFixed(1)} ${(sx + 4).toFixed(1)},${(sy + 2).toFixed(1)}`} className="tach-shift" />
        </svg>
        <div className="speedo">
          <div className="gear-box">
            <small>GEAR</small>
            <div className="gear" ref={refs.gear}>1</div>
          </div>
          <div className="speed-box">
            <div className="speed" ref={refs.speed}>0</div>
            <div className="unit">km/h</div>
          </div>
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
  const online = useApp.getState().mode === 'online';
  const fullscreen = useFullscreen();
  const fsItem = fullscreenSupported() ? [{ label: fullscreen ? '全画面表示を終了' : '全画面表示にする', action: toggleFullscreen }] : [];
  const items = online
    ? [
        { label: 'レースに戻る', action: resume },
        ...fsItem,
        { label: 'リタイアしてルームを出る', action: () => { set({ paused: false }); void leaveRoom(); gameHolder.game?.startAttract(); go('online'); } },
      ]
    : [
    { label: 'レースに戻る', action: resume },
    { label: 'リスタート', action: () => { gameHolder.game?.setPaused(false); set({ paused: false }); void startRaceFromState(); } },
    { label: '車両選択へ', action: () => { gameHolder.game?.setPaused(false); set({ paused: false }); go('garage'); } },
    { label: 'メインメニューへ', action: () => { gameHolder.game?.setPaused(false); set({ paused: false }); gameHolder.game?.startAttract(); go('modes'); } },
    ...fsItem,
      ];
  useMenuInput((a) => {
    if (a === 'up') { setSel((s) => (s + items.length - 1) % items.length); sfx.move(); }
    if (a === 'down') { setSel((s) => (s + 1) % items.length); sfx.move(); }
    if (a === 'confirm') { sfx.confirm(); items[sel].action(); }
    if (a === 'back') { sfx.back(); resume(); }
  });
  return (
    <div className="screen pause" data-wipe="none">
      <div className="pause-box">
        <div className="pause-title">PAUSE</div>
        <div className="pause-sub">{online ? 'オンライン対戦は止まりません' : '一時停止中'}</div>
        <div className="focus-box">
          <ul className="menu-list compact">
            {items.map((it, i) => (
              <li key={it.label} className={i === sel ? 'active' : ''} {...hoverSelect(() => setSel(i))} onClick={() => { sfx.confirm(); it.action(); }}>
                <span className="mi-jp big">{it.label}</span>
              </li>
            ))}
          </ul>
          <FocusFrame on="li.active" deps={[sel, items.length]} kind="row" />
        </div>
      </div>
      <Hint items={[['ud', '選択'], ['ok', '決定']]} />
    </div>
  );
}
