import { useLayoutEffect, useRef, useState } from 'react';
import { useApp, type Screen } from '../store/app';
import { currentCourseId, useSettings } from '../store/settings';
import { useOnline } from '../store/online';
import { COURSES } from '../game/track/courses';
import { CAR_SPECS } from '../game/vehicle/carSpecs';
import { fullscreenSupported, toggleFullscreen, useFullscreen } from './fullscreen';
import { PadKey } from './kit';

/**
 * The shell around every menu screen: the trail at the top (where you are, and what was chosen on the way), back
 * and fullscreen always bottom left. The screens themselves print the heading and the hint bar.
 */

interface Crumb {
  en: string;
  /** the step's name, or the choice made there once it is behind */
  jp: string;
  state: 'done' | 'now' | 'todo';
}

const MODE_JP = { time_attack: 'タイムアタック', rival: 'ライバルバトル', ghost: 'ゴーストバトル', online: 'オンライン対戦' } as const;
const TOD_JP = { night: '深夜・晴れ', rain: '深夜・雨', dawn: '夜明け' } as const;
const PLACES: Partial<Record<Screen, [string, string]>> = {
  cars: ['CAR LIST', '車両一覧'],
  settings: ['SETTINGS', '設定'],
  controls: ['CONTROLS', '操作方法'],
  leaderboard: ['RANKING', 'ランキング'],
};
/** the screens of the way to a race, in order (the ghost list only in ghost battles, the rival only in rival battles) */
const FLOW: Screen[] = ['courses', 'conditions', 'leaderboard', 'garage', 'transmission', 'rivals'];

function useTrail(): Crumb[] {
  const { screen, mode, carId, ghostChoice } = useApp();
  const tod = useSettings((s) => s.timeOfDay);
  const autoShift = useSettings((s) => s.autoShift);
  const room = useOnline((s) => s.room);
  const menu: Crumb = { en: 'MENU', jp: 'メインメニュー', state: screen === 'modes' ? 'now' : 'done' };
  if (screen === 'modes') return [menu];
  if (screen === 'online' || screen === 'onlineRoom' || screen === 'onlineResults') {
    const out: Crumb[] = [menu, { en: 'ONLINE', jp: 'オンライン対戦', state: screen === 'online' ? 'now' : 'done' }];
    if (screen !== 'online') out.push({ en: 'ROOM', jp: room ? `ルーム ${room.code}` : 'ルーム', state: screen === 'onlineRoom' ? 'now' : 'done' });
    if (screen === 'onlineResults') out.push({ en: 'RESULT', jp: 'リザルト', state: 'now' });
    return out;
  }
  const flowScreen = screen === 'loading' ? 'courses' : screen;
  const inFlow = FLOW.includes(flowScreen) && !(flowScreen === 'leaderboard' && mode !== 'ghost');
  if (!inFlow) {
    const place = PLACES[screen];
    return place ? [menu, { en: place[0], jp: place[1], state: 'now' }] : [menu];
  }
  const steps: { screen: Screen; en: string; name: string; chosen: string }[] = [
    { screen: 'courses', en: 'COURSE', name: 'コース', chosen: COURSES[currentCourseId()].name },
    { screen: 'conditions', en: 'CONDITIONS', name: '時間帯・天候', chosen: TOD_JP[tod] },
    ...(mode === 'ghost' ? [{ screen: 'leaderboard' as Screen, en: 'GHOST', name: 'ゴースト', chosen: ghostChoice?.label ?? '' }] : []),
    { screen: 'garage', en: 'MACHINE', name: '車両', chosen: CAR_SPECS[carId].name },
    { screen: 'transmission', en: 'GEARBOX', name: '変速', chosen: autoShift ? 'AT' : 'MT' },
    ...(mode === 'rival' ? [{ screen: 'rivals' as Screen, en: 'RIVAL', name: 'ライバル', chosen: '' }] : []),
  ];
  const at = steps.findIndex((s) => s.screen === flowScreen);
  return [
    { en: 'MODE', jp: MODE_JP[mode], state: 'done' },
    ...steps.map((s, k): Crumb => ({ en: s.en, jp: k < at ? s.chosen : s.name, state: k < at ? 'done' : k === at ? 'now' : 'todo' })),
  ];
}

/** The trail and the course it is all about. */
export function ShellTop() {
  const trail = useTrail();
  const course = COURSES[currentCourseId()];
  useSettings((s) => s.courseId);
  return (
    <header className="shell-top">
      <span className="shell-mark">峠</span>
      <ol className="trail">
        {trail.map((c) => (
          <li key={c.en} className={c.state}>
            <small>{c.en}</small>
            <b>{c.jp}</b>
          </li>
        ))}
      </ol>
      <div className="shell-meta">
        COURSE <b>{course.nameEn}</b>
      </div>
    </header>
  );
}

const BACK_LABEL: Partial<Record<Screen, string>> = { modes: 'タイトル', onlineRoom: '退出', onlineResults: 'ルームを出る' };

/**
 * Back and fullscreen, bottom left on every menu screen. Back sends Esc, which every screen maps to its own way
 * back; on a phone it is the only way (no Esc key there).
 */
export function ShellNav({ screen, back }: { screen: Screen; back: boolean }) {
  const fullscreen = useFullscreen();
  return (
    <div className="shell-nav">
      {back && (
        <button
          className="touch-back"
          onPointerDown={(e) => {
            e.preventDefault();
            window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', code: 'Escape', bubbles: true }));
          }}
        >
          ◀ {BACK_LABEL[screen] ?? '戻る'}
          <kbd className="k-key">Esc</kbd>
          <PadKey name="B" />
        </button>
      )}
      {fullscreenSupported() && (
        <button className="fs-toggle" onClick={toggleFullscreen} title="全画面表示の切り替え（F キー）">
          {fullscreen ? '全画面終了' : '全画面'}
        </button>
      )}
    </div>
  );
}

/** how long the game must be busy before the mark shows (short work passes unseen), and its fade out */
const BUSY_DELAY = 150;
const BUSY_FADE = 260;

/**
 * The mark for work in the background the player waits for (`useApp().busy`: a model on its way, a course being
 * built): a turning mark and the label, in a corner, above every screen and the HUD, never in the way of the input.
 *
 * It must keep turning while the game holds the main thread (building a course, compiling shaders), so everything
 * that moves here is a CSS animation of `transform` / `opacity`, which the compositor runs by itself; the delay
 * before it shows is the animation's own delay, not a timer. (Whoever sets `busy` has to let one frame through
 * before the heavy work starts, or the mark is not on the screen yet.)
 */
export function BusyMark() {
  const busy = useApp((s) => s.busy);
  const label = useRef('');
  const since = useRef<number | null>(null);
  const [leaving, setLeaving] = useState(false);
  if (busy !== null) label.current = busy;
  const on = busy !== null;
  useLayoutEffect(() => {
    if (on) {
      since.current = performance.now();
      setLeaving(false);
      return;
    }
    if (since.current === null) return;
    const seen = performance.now() - since.current > BUSY_DELAY;
    since.current = null;
    if (!seen) return;
    setLeaving(true);
    const t = setTimeout(() => setLeaving(false), BUSY_FADE);
    return () => clearTimeout(t);
  }, [on]);
  if (!on && !leaving) return null;
  return (
    <div className={`busy-mark${on ? '' : ' out'}`} role="status" aria-live="polite">
      <i className="busy-glyph" aria-hidden />
      <span>{label.current}</span>
    </div>
  );
}
