import { useEffect, useState } from 'react';
import { useApp } from '../../store/app';
import { currentCourseId, useSettings } from '../../store/settings';
import { useMenuInput, hoverSelect } from '../useMenuInput';
import { gameHolder } from '../GameCanvas';
import { COURSES } from '../../game/track/courses';
import type { TimeOfDay } from '../../game/render/Environment';
import { Hint, startRaceFromState } from './Menus';
import { sfx } from '../sfx';

/** Race conditions shown before the car select (the online lobby offers the same list). */
export const CONDITIONS: { id: TimeOfDay; en: string; jp: string; desc: string }[] = [
  { id: 'night', en: 'CLEAR NIGHT', jp: '深夜・晴れ', desc: '眼下に街の夜景。街灯とヘッドライトだけが頼りの定番コンディション。' },
  { id: 'rain', en: 'RAIN', jp: '深夜・雨', desc: '濡れた路面はグリップが2割落ちて滑りやすい。ライトが路面に映り込み、ラインが読みにくい。' },
  { id: 'dawn', en: 'DAWN', jp: '夜明け', desc: '雲海の向こうから朝日が昇る。視界は良いが、街灯は消えている。' },
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
      <div className="crumb center">TIME &amp; WEATHER ― 時間帯・天候{mode === 'ghost' ? '（ゴーストバトル）' : ''} ・ {course.name}</div>
      <div className="choice-cards">
        {CONDITIONS.map((c, k) => (
          <div key={c.id} className={`choice-card tod-${c.id} ${k === i ? 'active' : ''}`} {...hoverSelect(() => setI(k))} onClick={() => { setI(k); choose(k); }}>
            <div className="ch-en">{c.en}</div>
            <div className="ch-jp">{c.jp}</div>
            <p>{c.desc}</p>
          </div>
        ))}
      </div>
      <Hint items={[['←→', '選択'], ['Enter', '決定'], ['Esc', '戻る']]} />
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
    <div className="screen setup">
      <div className="crumb center">TRANSMISSION ― トランスミッション</div>
      <div className="choice-cards two">
        {GEARBOXES.map((g, k) => (
          <div key={g.en} className={`choice-card ${k === i ? 'active' : ''}`} {...hoverSelect(() => setI(k))} onClick={() => { setI(k); choose(k); }}>
            <div className="ch-big">{g.en}</div>
            <div className="ch-jp">{g.jp}</div>
            <p>{g.desc}</p>
          </div>
        ))}
      </div>
      <Hint items={[['←→', '選択'], ['Enter', mode === 'rival' ? 'ライバル選択へ' : 'スタート'], ['Esc', '戻る']]} />
    </div>
  );
}
