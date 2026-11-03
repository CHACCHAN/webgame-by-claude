import { useEffect, useRef, useState, type PointerEvent, type WheelEvent } from 'react';
import { useApp } from '../../store/app';
import { useMenuInput } from '../useMenuInput';
import { gameHolder } from '../GameCanvas';
import { CAR_SPECS, VEHICLE_ORDER, type CarId, type CarSpec } from '../../game/vehicle/carSpecs';
import { Hint } from './Menus';
import { TRAIN_INFO, TRAIN_ORDER, type TrainId } from '../../game/vehicle/trains';
import { ROACH_INFO } from '../../game/vehicle/roach';
import { sfx } from '../sfx';

/** Body colours offered for each car (first = default). */
export const COLORS: Record<CarId, string[]> = {
  // trains: one swatch per paint scheme (the band colour identifies it)
  ...(Object.fromEntries(TRAIN_ORDER.map((id) => [id, TRAIN_INFO[id].liveries.map((l) => l.band)])) as Record<TrainId, string[]>),
  hayate: ['#e8e6e1', '#b3121c', '#1b1d22', '#2f6db5', '#e0b400'],
  raijin: ['#d9dbde', '#1d4fa8', '#0c0c0e', '#8f1218', '#5e6b3a'],
  shiden: ['#f5c400', '#c8102e', '#f2f2f0', '#121214', '#3a7d44'],
  supra: ['#eeeeee', '#d8481c', '#c40d1e', '#121214', '#1f5fb5'],
  r34: ['#2f4fa6', '#e9e9ea', '#121214', '#8a8f96', '#4a2a63'],
  s15: ['#f5cf30', '#e9e9ea', '#121214', '#b3121c', '#2f6db5'],
  // the cockroach: one swatch per species colouring
  roach: ROACH_INFO.liveries.map((l) => l.swatch),
};

/** Peak power from the torque curve (linear between the points, up to the redline). */
export function peakPower(spec: CarSpec) {
  const t = spec.engine.torque;
  let best = { kw: 0, rpm: 0 };
  for (let rpm = t[0][0]; rpm <= spec.engine.redline; rpm += 50) {
    let k = 0;
    while (k < t.length - 2 && t[k + 1][0] < rpm) k++;
    const f = Math.min(1, Math.max(0, (rpm - t[k][0]) / (t[k + 1][0] - t[k][0])));
    const kw = ((t[k][1] + (t[k + 1][1] - t[k][1]) * f) * rpm * 2 * Math.PI) / 60 / 1000;
    if (kw > best.kw) best = { kw, rpm };
  }
  return { ps: Math.round(best.kw * 1.36), kw: Math.round(best.kw), rpm: Math.round(best.rpm / 100) * 100 };
}

/** [rpm, Nm] of the highest point of the torque curve */
export function peakTorque(spec: CarSpec) {
  return spec.engine.torque.reduce((a, b) => (b[1] > a[1] ? b : a));
}

function Stat({ label, v }: { label: string; v: number }) {
  return (
    <div className="stat">
      <span>{label}</span>
      <div className="stat-bar">
        <div style={{ width: `${v * 10}%` }} />
      </div>
      <b>{v}</b>
    </div>
  );
}

const two = (n: number) => String(n).padStart(2, '0');
/** km/h/s with at least one decimal (3.0, 2.23) */
const rate = (v: number) => (Number.isInteger(v * 10) ? v.toFixed(1) : String(v));

/** A train's figures: the real ones (vehicle/trains.ts). */
function TrainFigures({ spec, full }: { spec: CarSpec; full: boolean }) {
  const t = spec.train!;
  if (!full) {
    return (
      <div className="specs-row">
        <div><small>ACCEL</small><b>{rate(t.accel)} km/h/s</b></div>
        <div><small>TOP SPEED</small><b>{t.vmax} km/h</b></div>
        <div><small>WEIGHT</small><b>{t.mass} t</b></div>
      </div>
    );
  }
  return (
    <dl className="spec-table">
      <dt>形式</dt><dd>{t.operator} {t.series}</dd>
      <dt>編成</dt><dd>3両（Tc＋M＋Tc）</dd>
      <dt>起動加速度</dt><dd>{rate(t.accel)} km/h/s</dd>
      <dt>設計最高速度</dt><dd>{t.vmax} km/h</dd>
      <dt>減速度（常用／非常）</dt><dd>{rate(t.brake[0])} ／ {rate(t.brake[1])} km/h/s</dd>
      <dt>編成重量</dt><dd>{t.mass} t</dd>
      <dt>主電動機</dt><dd>{t.motor}</dd>
      <dt>制御方式</dt><dd>{t.control}</dd>
      <dt>歯車比</dt><dd>{t.gearRatio}</dd>
      <dt>車体幅</dt><dd>{t.width.toFixed(2)} m</dd>
    </dl>
  );
}

/** The cockroach's figures (vehicle/roach.ts). */
function CreatureFigures({ spec, full }: { spec: CarSpec; full: boolean }) {
  const c = spec.creature!.figures;
  if (!full) {
    return (
      <div className="specs-row">
        <div><small>0-100 km/h</small><b>{c.zeroToHundred.toFixed(1)} s</b></div>
        <div><small>TOP SPEED</small><b>{c.topSpeed} km/h</b></div>
        <div><small>WEIGHT</small><b>{spec.mass} kg</b></div>
      </div>
    );
  }
  return (
    <dl className="spec-table">
      <dt>種別</dt><dd>巨大ゴキブリ（昆虫綱ゴキブリ目）</dd>
      <dt>体長</dt><dd>約 {c.bodyLength} m（触角を除く）</dd>
      <dt>駆動</dt><dd>{c.legs}本脚（全脚駆動）</dd>
      <dt>0-100 km/h</dt><dd>{c.zeroToHundred.toFixed(1)} 秒</dd>
      <dt>最高速度</dt><dd>{c.topSpeed} km/h</dd>
      <dt>グリップ</dt><dd>スポーツカーの約 1.3 倍（脚の爪で路面をつかむ）</dd>
      <dt>体重</dt><dd>{spec.mass} kg</dd>
      <dt>変速機</dt><dd>なし</dd>
    </dl>
  );
}

/** Name, character and figures of a car: `full` adds the whole specification table (car list). */
export function CarSheet({ spec, index, full = false }: { spec: CarSpec; index: number; full?: boolean }) {
  const power = peakPower(spec);
  const [trqRpm, trq] = peakTorque(spec);
  return (
    <>
      <div className="car-index">
        {two(index + 1)} / {two(VEHICLE_ORDER.length)}
        {spec.train && <span className="train-badge">TRAIN ・ ネタ枠</span>}
        {spec.creature && <span className="train-badge">CREATURE ・ ネタ枠</span>}
      </div>
      <h2 className="car-name">{spec.name}</h2>
      <div className="car-tag">{spec.tagline} ・ {spec.train ? spec.train.operator : spec.creature ? `${spec.creature.figures.legs}本脚` : spec.drive}</div>
      <p className="car-desc">{spec.description}</p>
      <div className="stats">
        <Stat label="POWER" v={spec.stats.power} />
        <Stat label="GRIP" v={spec.stats.grip} />
        <Stat label="DRIFT" v={spec.stats.drift} />
        <Stat label="LIGHTNESS" v={spec.stats.weight} />
      </div>
      {spec.train ? (
        <TrainFigures spec={spec} full={full} />
      ) : spec.creature ? (
        <CreatureFigures spec={spec} full={full} />
      ) : full ? (
        <dl className="spec-table">
          <dt>エンジン</dt><dd>{spec.engineName}</dd>
          <dt>最高出力</dt><dd>{power.ps} PS / {power.rpm} rpm</dd>
          <dt>最大トルク</dt><dd>{trq} Nm / {trqRpm} rpm</dd>
          <dt>レッドゾーン</dt><dd>{spec.engine.redline} rpm</dd>
          <dt>車両重量</dt><dd>{spec.mass} kg</dd>
          <dt>パワーウェイトレシオ</dt><dd>{(spec.mass / power.ps).toFixed(2)} kg/PS</dd>
          <dt>駆動方式</dt><dd>{spec.drive === 'AWD' ? '4WD' : 'FR'}</dd>
          <dt>変速機</dt><dd>{spec.gears.length}速</dd>
          <dt>全長 × 全幅</dt><dd>{spec.size.length.toFixed(2)} × {spec.size.width.toFixed(2)} m</dd>
          <dt>ホイールベース</dt><dd>{spec.wheelbase.toFixed(2)} m</dd>
        </dl>
      ) : (
        <div className="specs-row">
          <div><small>MAX POWER</small><b>{power.ps} PS</b></div>
          <div><small>WEIGHT</small><b>{spec.mass} kg</b></div>
          <div><small>REDLINE</small><b>{spec.engine.redline} rpm</b></div>
        </div>
      )}
      {spec.model && (
        <p className="car-credit">
          3D model: “{spec.model.title}” by {spec.model.author} ({spec.model.license}, Sketchfab)
        </p>
      )}
    </>
  );
}

/**
 * Pointer handlers for a garage screen: hold the mouse (or a finger) on the empty part of the screen and
 * drag to look around the car; the wheel zooms.
 */
export function useGarageOrbit() {
  const last = useRef<{ x: number; y: number } | null>(null);
  const [dragging, setDragging] = useState(false);
  return {
    dragging,
    handlers: {
      onPointerDown: (e: PointerEvent<HTMLDivElement>) => {
        if (e.target !== e.currentTarget) return; // the card, buttons and arrows keep their clicks
        e.currentTarget.setPointerCapture(e.pointerId);
        last.current = { x: e.clientX, y: e.clientY };
        setDragging(true);
      },
      onPointerMove: (e: PointerEvent<HTMLDivElement>) => {
        if (!last.current) return;
        gameHolder.game?.orbitGarage(e.clientX - last.current.x, e.clientY - last.current.y);
        last.current = { x: e.clientX, y: e.clientY };
      },
      onPointerUp: () => {
        last.current = null;
        setDragging(false);
      },
      onWheel: (e: WheelEvent<HTMLDivElement>) => gameHolder.game?.zoomGarage(Math.exp(e.deltaY * 0.001)),
    },
  };
}

/** Car list from the main menu: every car with its figures, turned around by dragging. */
export function CarsScreen() {
  const { go, carId } = useApp();
  const [i, setI] = useState(Math.max(0, VEHICLE_ORDER.indexOf(carId)));
  const [c, setC] = useState(0);
  const id = VEHICLE_ORDER[i];
  const palette = COLORS[id];
  const color = palette[c % palette.length];
  const orbit = useGarageOrbit();
  useEffect(() => {
    gameHolder.game?.showGarage(id, color);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);
  useEffect(() => {
    gameHolder.game?.setGarageColor(color);
  }, [color]);
  useEffect(() => {
    void gameHolder.game?.audio?.playMusic('bgm_garage');
  }, []);
  const turn = (d: number) => {
    setI((x) => (x + d + VEHICLE_ORDER.length) % VEHICLE_ORDER.length);
    setC(0);
    sfx.move();
  };
  const back = () => {
    sfx.back();
    gameHolder.game?.startAttract();
    go('modes');
  };
  useMenuInput((a) => {
    if (a === 'left') turn(-1);
    if (a === 'right') turn(1);
    if (a === 'up') { setC((x) => x + palette.length - 1); sfx.move(); }
    if (a === 'down') { setC((x) => x + 1); sfx.move(); }
    if (a === 'back') back();
  });
  return (
    <div className={`screen garage cars ${orbit.dragging ? 'orbiting' : ''}`} {...orbit.handlers}>
      <div className="garage-top">
        <div className="crumb">CAR LIST ― 車両一覧</div>
      </div>
      <div className="garage-card">
        <CarSheet spec={CAR_SPECS[id]} index={i} full />
        <div className="colors">
          {palette.map((col, k) => (
            <button key={col} className={col === color ? 'swatch on' : 'swatch'} style={{ background: col }} onClick={() => setC(k)} aria-label={`color ${col}`} />
          ))}
        </div>
        <button className="cta small ghost" onClick={back}>メニューに戻る</button>
      </div>
      <button className="arrow left" onClick={() => turn(-1)}>‹</button>
      <button className="arrow right" onClick={() => turn(1)}>›</button>
      <div className="orbit-hint">ドラッグで車を見回す ・ ホイールでズーム</div>
      <Hint items={[['←→', '車両'], ['↑↓', 'カラー'], ['ドラッグ', '視点'], ['Esc', '戻る']]} />
    </div>
  );
}
