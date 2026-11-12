import { useEffect, useRef } from 'react';
import { GameCanvas, gameHolder } from './ui/GameCanvas';
import { useApp, type Screen } from './store/app';
import { useSettings } from './store/settings';
import { BootScreen, ControlsScreen, CourseLoadingScreen, CoursesScreen, ModesScreen, RivalsScreen, TitleScreen } from './ui/screens/Menus';
import { GarageScreen } from './ui/garage/GarageScreen';
import { LeaderboardScreen } from './ui/screens/Leaderboard';
import { SettingsScreen } from './ui/screens/Settings';
import { AboutScreen } from './ui/screens/About';
import { ReplayOverlay, ResultsScreen } from './ui/screens/Results';
import { Hud, PauseMenu } from './ui/hud/Hud';
import { OnlineLobbyScreen, OnlineResultsScreen, OnlineRoomScreen } from './ui/screens/Online';
import { ConditionsScreen, TransmissionScreen } from './ui/screens/RaceSetup';
import { CarsScreen } from './ui/screens/Cars';
import { TouchControls } from './ui/hud/TouchControls';
import { useTouch } from './ui/touch';
import { toggleFullscreen } from './ui/fullscreen';
import { AccountNotice, BusyMark, RoomNotice, ShellNav, ShellTop } from './ui/Shell';
import { useScreenWipe } from './ui/motion';
import { noteInput } from './ui/inputDevice';
import { Cloud } from './ui/fx/Cloud';

declare global {
  interface Window {
    /** the app's store, for tests and probes (as `__game` is the game): `__app.setState({ busy: '…' })` */
    __app?: typeof useApp;
  }
}
window.__app = useApp;

/** the menu screens: the shell (trail, back, fullscreen) stands around them */
const SHELLED: Screen[] = ['modes', 'courses', 'conditions', 'garage', 'transmission', 'cars', 'rivals', 'leaderboard', 'settings', 'controls', 'about', 'online', 'onlineRoom', 'onlineResults'];

export function App() {
  const screen = useApp((s) => s.screen);
  const paused = useApp((s) => s.paused);
  const phase = useApp((s) => s.phase);
  const touch = useTouch();
  const uiMotion = useSettings((s) => s.uiMotion !== false);
  const overlay = useRef<HTMLDivElement>(null);
  const wipeHost = useRef<HTMLDivElement>(null);
  const wipeScan = useRef<HTMLElement>(null);
  useScreenWipe(overlay, wipeHost, wipeScan);

  // pause handling during races
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      // F: fullscreen on / off, anywhere (not while typing a name)
      if (e.code === 'KeyF' && !e.repeat && (e.target as HTMLElement)?.tagName !== 'INPUT') toggleFullscreen();
      const app = useApp.getState();
      if (app.screen !== 'race' || app.paused) return;
      if (e.code === 'Escape' || e.code === 'KeyP') {
        // an online race keeps running for everyone: only the menu opens
        if (app.mode !== 'online') gameHolder.game?.setPaused(true);
        app.set({ paused: true });
      }
    };
    window.addEventListener('keydown', onKey);
    let raf = 0;
    let prevStart = false;
    const poll = () => {
      const pad = Array.from(navigator.getGamepads?.() ?? []).find((p) => p && p.connected);
      const start = !!pad?.buttons[9]?.pressed;
      const app = useApp.getState();
      if (start && !prevStart && app.screen === 'race' && !app.paused) {
        noteInput('pad');
        if (app.mode !== 'online') gameHolder.game?.setPaused(true);
        app.set({ paused: true });
      }
      prevStart = start;
      raf = requestAnimationFrame(poll);
    };
    raf = requestAnimationFrame(poll);
    const onBlur = () => {
      const app = useApp.getState();
      if (app.screen === 'race' && !app.paused && app.phase === 'racing' && app.mode !== 'online') {
        gameHolder.game?.setPaused(true);
        app.set({ paused: true });
      }
    };
    window.addEventListener('blur', onBlur);
    return () => {
      window.removeEventListener('keydown', onKey);
      window.removeEventListener('blur', onBlur);
      cancelAnimationFrame(raf);
    };
  }, []);

  // apply audio volumes
  useEffect(() => {
    const apply = () => {
      const s = useSettings.getState();
      // (settings stored before the rain had a volume carry none: full)
      gameHolder.game?.audio?.setVolumes(s.masterVolume, s.sfxVolume, s.musicVolume, s.rainVolume ?? 1);
    };
    apply();
    const id = setInterval(apply, 500);
    return () => clearInterval(id);
  }, []);

  // motion reduced by the setting or by the system: the styles swap every movement for a fade (tokens.css)
  const calm = !uiMotion || (typeof window !== 'undefined' && !!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches);

  const inRace = screen === 'race' || (screen === 'results' && phase !== 'replay') || screen === 'onlineResults';
  const shelled = SHELLED.includes(screen);
  return (
    <div className={`app screen-${screen}${touch ? ' touch' : ''}${calm ? ' motion-off' : ''}`}>
      <GameCanvas />
      <div className="overlay" ref={overlay}>
        {shelled && <div className="shell-foot" />}
        {screen === 'boot' && <BootScreen />}
        {screen === 'title' && <TitleScreen />}
        {screen === 'modes' && <ModesScreen />}
        {screen === 'courses' && <CoursesScreen />}
        {screen === 'loading' && <CourseLoadingScreen />}
        {screen === 'conditions' && <ConditionsScreen />}
        {screen === 'garage' && <GarageScreen />}
        {screen === 'transmission' && <TransmissionScreen />}
        {screen === 'cars' && <CarsScreen />}
        {screen === 'rivals' && <RivalsScreen />}
        {screen === 'leaderboard' && <LeaderboardScreen />}
        {screen === 'settings' && <SettingsScreen />}
        {screen === 'controls' && <ControlsScreen />}
        {screen === 'about' && <AboutScreen />}
        {screen === 'online' && <OnlineLobbyScreen />}
        {screen === 'onlineRoom' && <OnlineRoomScreen />}
        {screen === 'onlineResults' && <OnlineResultsScreen />}
        {/* one HUD from the grid to the finish (it boots at every start by itself) */}
        {inRace && (phase === 'countdown' || phase === 'racing' || phase === 'finished') && <Hud key={String(gameHolder.game?.currentConfig?.carId)} />}
        {screen === 'results' && <ResultsScreen />}
        {screen === 'replay' && <ReplayOverlay />}
        {screen === 'race' && paused && <PauseMenu />}
        {touch && screen === 'race' && !paused && (phase === 'countdown' || phase === 'racing') && <TouchControls />}
        {/* the screen on its way out (ui/motion.ts) and the scan line of the wipe */}
        <div className="wipe-host" ref={wipeHost} />
        <i className="wipe-scan" ref={wipeScan} />
        {shelled && <ShellTop />}
        {(shelled || screen === 'title') && <ShellNav screen={screen} back={shelled} />}
      </div>
      {/* the grains over the menus: not in a race (the HUD has the frame's time), not when motion is off */}
      {!calm && screen !== 'race' && screen !== 'replay' && screen !== 'boot' && <Cloud />}
      <BusyMark />
      <AccountNotice />
      <RoomNotice />
      {touch && (
        <div className="rotate-hint">
          <svg viewBox="0 0 48 48" aria-hidden>
            <rect x="15" y="5" width="18" height="38" rx="3" />
            <path d="M22 38h4" />
          </svg>
          横向きにしてプレイしてください
        </div>
      )}
    </div>
  );
}
