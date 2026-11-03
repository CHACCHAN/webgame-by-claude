import { useEffect } from 'react';
import { GameCanvas, gameHolder } from './ui/GameCanvas';
import { useApp } from './store/app';
import { useSettings } from './store/settings';
import { BootScreen, ControlsScreen, CourseLoadingScreen, CoursesScreen, GarageScreen, ModesScreen, RivalsScreen, TitleScreen } from './ui/screens/Menus';
import { LeaderboardScreen } from './ui/screens/Leaderboard';
import { SettingsScreen } from './ui/screens/Settings';
import { ReplayOverlay, ResultsScreen } from './ui/screens/Results';
import { Hud, PauseMenu } from './ui/hud/Hud';
import { OnlineLobbyScreen, OnlineResultsScreen, OnlineRoomScreen } from './ui/screens/Online';
import { ConditionsScreen, TransmissionScreen } from './ui/screens/RaceSetup';
import { CarsScreen } from './ui/screens/Cars';
import { TouchControls } from './ui/hud/TouchControls';
import { useTouch } from './ui/touch';
import { fullscreenSupported, toggleFullscreen, useFullscreen } from './ui/fullscreen';

export function App() {
  const screen = useApp((s) => s.screen);
  const paused = useApp((s) => s.paused);
  const phase = useApp((s) => s.phase);
  const touch = useTouch();
  const fullscreen = useFullscreen();

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
      gameHolder.game?.audio?.setVolumes(s.masterVolume, s.sfxVolume, s.musicVolume);
    };
    apply();
    const id = setInterval(apply, 500);
    return () => clearInterval(id);
  }, []);

  const inRace = screen === 'race' || (screen === 'results' && phase !== 'replay') || screen === 'onlineResults';
  // phones have no Esc key: a back button on the menu screens sends it (every screen maps Esc to its "back")
  const touchBack = touch && !['boot', 'title', 'loading', 'race', 'results', 'replay', 'onlineResults'].includes(screen);
  return (
    <div className={`app screen-${screen}${touch ? ' touch' : ''}`}>
      <GameCanvas />
      <div className="overlay">
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
        {screen === 'online' && <OnlineLobbyScreen />}
        {screen === 'onlineRoom' && <OnlineRoomScreen />}
        {screen === 'onlineResults' && <OnlineResultsScreen />}
        {inRace && (phase === 'countdown' || phase === 'racing' || phase === 'finished') && <Hud key={String(gameHolder.game?.currentConfig?.carId) + phase.length} />}
        {screen === 'results' && <ResultsScreen />}
        {screen === 'replay' && <ReplayOverlay />}
        {screen === 'race' && paused && <PauseMenu />}
        {touch && screen === 'race' && !paused && (phase === 'countdown' || phase === 'racing') && <TouchControls />}
      </div>
      {fullscreenSupported() && !['boot', 'race'].includes(screen) && (
        <button className={touchBack ? 'fs-toggle above-back' : 'fs-toggle'} onClick={toggleFullscreen} title="全画面表示の切り替え（F キー）">
          {fullscreen ? '全画面終了' : '全画面'}
        </button>
      )}
      {touchBack && (
        <button
          className="touch-back"
          onPointerDown={(e) => {
            e.preventDefault();
            window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', code: 'Escape', bubbles: true }));
          }}
        >
          ◀ 戻る
        </button>
      )}
      {touch && (
        <div className="rotate-hint">
          <div>📱↻</div>
          横向きにしてプレイしてください
        </div>
      )}
    </div>
  );
}
