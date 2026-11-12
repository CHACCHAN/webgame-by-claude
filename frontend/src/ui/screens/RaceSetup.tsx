import { useEffect, useRef, useState, type ReactNode } from 'react';
import { useApp } from '../../store/app';
import { currentCourseId, useSettings } from '../../store/settings';
import { useMenuInput, hoverSelect } from '../useMenuInput';
import { gameHolder } from '../GameCanvas';
import { COURSES, type CourseInfo } from '../../game/track/courses';
import { WET_GRIP } from '../../game/Game';
import type { TimeOfDay } from '../../game/render/Environment';
import { startRaceFromState } from './Menus';
import { sfx } from '../sfx';
import { FocusFrame, Hint, ScreenHead } from '../kit';

/** Race conditions shown before the car select (the online lobby offers the same list). */
export const CONDITIONS: { id: TimeOfDay; en: string; jp: string; desc: string; lamps: string; sight: string }[] = [
  { id: 'night', en: 'CLEAR NIGHT', jp: '深夜・晴れ', desc: '眼下に街の夜景。街灯とヘッドライトだけが頼りの定番コンディション。', lamps: '点灯', sight: '暗い' },
  { id: 'rain', en: 'RAIN', jp: '深夜・雨', desc: '濡れた路面はグリップが2割落ちて滑りやすい。ライトが路面に映り込み、ラインが読みにくい。', lamps: '点灯', sight: '雨で悪い' },
  { id: 'dawn', en: 'DAWN', jp: '夜明け', desc: '雲海の向こうから朝日が昇る。視界は良いが、街灯は消えている。', lamps: '消灯', sight: '良い' },
];

/**
 * Time of day and weather, chosen right after the course. The world behind the list switches with the choice and is
 * the picture of it (owner 11-12: the three cards with drawn skies over a car seen from above looked dowdy; layout
 * A of the two shown): a list where the menus have theirs, the selected one's figures at the bottom, the scene free.
 */
export function ConditionsScreen() {
  const { go, afterLoad, mode } = useApp();
  const course = COURSES[currentCourseId()];
  // the camera goes behind the car and looks down the road: the scene itself is the picture of the condition
  useEffect(() => {
    const game = gameHolder.game;
    if (!game) return;
    game.menuShot = 'sky';
    return () => { game.menuShot = null; };
  }, []);
  return (
    <ConditionsSelect
      head={<ScreenHead jp="時間帯・天候" en="TIME & WEATHER" note={`${course.name}${mode === 'ghost' ? '・ゴーストバトル' : ''}`} />}
      course={course}
      initial={useSettings.getState().timeOfDay}
      onLook={(tod) => gameHolder.game?.applyTimeOfDay(tod)}
      onChoose={(tod) => {
        useSettings.getState().set({ timeOfDay: tod });
        gameHolder.game?.applyTimeOfDay(tod);
        go(afterLoad);
      }}
      onBack={() => {
        // the world keeps the conditions that were last confirmed
        gameHolder.game?.applyTimeOfDay(useSettings.getState().timeOfDay);
        go('courses');
      }}
    />
  );
}

/**
 * The list of conditions itself, with the selected one's words and figures: the time & weather screen is this, and
 * so is an online room's change of conditions (`plain`: the words without the figures; `current`: the room's,
 * marked in the list). `onLook`: the condition the cursor rests on, for the scene behind to show.
 */
export function ConditionsSelect({ head, course, initial, current, plain, confirm = '決定', onLook, onChoose, onBack }: { head: ReactNode; course: CourseInfo; initial: TimeOfDay; current?: TimeOfDay; plain?: boolean; confirm?: string; onLook: (tod: TimeOfDay) => void; onChoose: (tod: TimeOfDay) => void; onBack: () => void }) {
  const [i, setI] = useState(Math.max(0, CONDITIONS.findIndex((c) => c.id === initial)));
  const look = useRef(onLook);
  look.current = onLook;
  useEffect(() => {
    // rebuilding the sky and env map takes a moment: only once the cursor rests
    const t = setTimeout(() => look.current(CONDITIONS[i].id), 180);
    return () => clearTimeout(t);
  }, [i]);
  const choose = (k = i) => {
    sfx.confirm();
    onChoose(CONDITIONS[k].id);
  };
  useMenuInput((a) => {
    if (a === 'left' || a === 'up') { setI((x) => (x + CONDITIONS.length - 1) % CONDITIONS.length); sfx.move(); }
    if (a === 'right' || a === 'down') { setI((x) => (x + 1) % CONDITIONS.length); sfx.move(); }
    if (a === 'confirm') choose();
    if (a === 'back') { sfx.back(); onBack(); }
  });
  const sel = CONDITIONS[i];
  const grip = Math.round(course.surface.grip * (sel.id === 'rain' ? WET_GRIP : 1) * 100);
  return (
    <div className={`screen cond${plain ? ' cond-plain' : ''}`}>
      {head}
      <div className="cond-list focus-box stagger">
        {CONDITIONS.map((c, k) => (
          <div key={c.id} className={`cond-row ${k === i ? 'active' : ''}`} {...hoverSelect(() => setI(k))} onClick={() => { setI(k); choose(k); }}>
            <span className="cw-no">0{k + 1}</span>
            <span className="cw-jp">{c.jp}{c.id === current && <em className="row-now">現在</em>}</span>
            <span className="cw-en">{c.en}</span>
          </div>
        ))}
        <FocusFrame on=".cond-row.active" deps={[i]} kind="row" />
      </div>
      {/* what the selected one means for the drive (the others' figures are a key away: the scene changes with them) */}
      <div className="cond-panel" key={i}>
        <p>{sel.desc}</p>
        {!plain && (
          <dl className="cond-read">
            <div className={sel.id === 'rain' ? 'warn' : ''}>
              <dt>グリップ<small>GRIP</small></dt>
              <dd><b>{grip}</b><i>%</i><span className="cr-bar"><span style={{ width: `${Math.min(100, grip / 1.1)}%` }} /></span></dd>
            </div>
            <div className={sel.lamps === '消灯' ? 'off' : ''}>
              <dt>街灯<small>LAMPS</small></dt>
              <dd><span className="cr-lamp" /><em>{sel.lamps}</em></dd>
            </div>
            <div className={sel.id === 'rain' ? 'warn' : ''}>
              <dt>視界<small>SIGHT</small></dt>
              <dd><span className={`cr-steps s${sel.id === 'dawn' ? 3 : sel.id === 'night' ? 2 : 1}`}><span /><span /><span /></span><em>{sel.sight}</em></dd>
            </div>
          </dl>
        )}
      </div>
      <Hint items={[['ud', '選択'], ['ok', confirm]]} />
    </div>
  );
}

const GEARBOXES = [
  { auto: true, en: 'AT', jp: 'オートマチック', desc: 'シフトは自動。アクセルとブレーキ、ステアリングに集中できる。' },
  { auto: false, en: 'MT', jp: 'マニュアル', desc: 'E / Q（パッドは Y / LB）で自分でシフト。回転を使い切れば AT より速く走れる。' },
];

/** AT or MT, after the car. */
export function TransmissionScreen() {
  const { go, mode } = useApp();
  const autoShift = useSettings((s) => s.autoShift);
  const [i, setI] = useState(autoShift ? 0 : 1);
  const choose = (k = i) => {
    sfx.confirm();
    const auto = GEARBOXES[k].auto;
    useSettings.getState().set({ autoShift: auto });
    if (gameHolder.game) gameHolder.game.autoShift = auto;
    if (mode === 'rival') go('rivals');
    else void startRaceFromState();
  };
  useMenuInput((a) => {
    if (a === 'left' || a === 'right' || a === 'up' || a === 'down') { setI((x) => 1 - x); sfx.move(); }
    if (a === 'confirm') choose();
    if (a === 'back') { sfx.back(); go('garage'); }
  });
  return (
    <div className="screen setup gearbox">
      <ScreenHead jp="トランスミッション" en="TRANSMISSION" />
      <div className="choice-cards two focus-box stagger">
        {GEARBOXES.map((g, k) => (
          <div key={g.en} className={`choice-card ${k === i ? 'active' : ''}`} {...hoverSelect(() => setI(k))} onClick={() => { setI(k); choose(k); }}>
            <div className="ch-big">{g.en}</div>
            <div className="ch-jp">{g.jp}</div>
            <p>{g.desc}</p>
          </div>
        ))}
        <FocusFrame on=".choice-card.active" deps={[i]} pad={5} />
      </div>
      <Hint items={[['ud', '選択'], ['ok', mode === 'rival' ? 'ライバル選択へ' : 'スタート']]} />
    </div>
  );
}
