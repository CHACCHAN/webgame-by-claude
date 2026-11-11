import { useEffect, useState } from 'react';
import { useApp } from '../../store/app';
import { currentCourseId, useSettings } from '../../store/settings';
import { useMenuInput, hoverSelect } from '../useMenuInput';
import { gameHolder } from '../GameCanvas';
import { COURSES } from '../../game/track/courses';
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

/** Time of day and weather, chosen right after the course; the world behind the cards switches with the choice. */
export function ConditionsScreen() {
  const { go, afterLoad, mode } = useApp();
  const tod = useSettings((s) => s.timeOfDay);
  const [i, setI] = useState(Math.max(0, CONDITIONS.findIndex((c) => c.id === tod)));
  const course = COURSES[currentCourseId()];
  useEffect(() => {
    // rebuilding the sky and env map takes a moment: only once the cursor rests
    const t = setTimeout(() => gameHolder.game?.applyTimeOfDay(CONDITIONS[i].id), 180);
    return () => clearTimeout(t);
  }, [i]);
  const choose = (k = i) => {
    sfx.confirm();
    useSettings.getState().set({ timeOfDay: CONDITIONS[k].id });
    gameHolder.game?.applyTimeOfDay(CONDITIONS[k].id);
    go(afterLoad);
  };
  useMenuInput((a) => {
    if (a === 'left' || a === 'up') { setI((x) => (x + CONDITIONS.length - 1) % CONDITIONS.length); sfx.move(); }
    if (a === 'right' || a === 'down') { setI((x) => (x + 1) % CONDITIONS.length); sfx.move(); }
    if (a === 'confirm') choose();
    if (a === 'back') {
      sfx.back();
      // the world keeps the conditions that were last confirmed
      gameHolder.game?.applyTimeOfDay(useSettings.getState().timeOfDay);
      go('courses');
    }
  });
  return (
    <div className="screen setup">
      <ScreenHead jp="時間帯・天候" en="TIME & WEATHER" note={`${course.name}${mode === 'ghost' ? '・ゴーストバトル' : ''}`} />
      <div className="choice-cards focus-box stagger">
        {CONDITIONS.map((c, k) => (
          <div key={c.id} className={`choice-card tod-${c.id} ${k === i ? 'active' : ''}`} {...hoverSelect(() => setI(k))} onClick={() => { setI(k); choose(k); }}>
            <div className="ch-sky" />
            <div className="ch-en">{c.en}</div>
            <div className="ch-jp">{c.jp}</div>
            <p>{c.desc}</p>
            <dl className="ch-data">
              <div><dt>グリップ</dt><dd>{Math.round(course.surface.grip * (c.id === 'rain' ? WET_GRIP : 1) * 100)}%</dd></div>
              <div><dt>街灯</dt><dd>{c.lamps}</dd></div>
              <div><dt>視界</dt><dd>{c.sight}</dd></div>
            </dl>
          </div>
        ))}
        <FocusFrame on=".choice-card.active" deps={[i]} pad={5} />
      </div>
      <Hint items={[['lr', '選択'], ['ok', '決定']]} />
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
