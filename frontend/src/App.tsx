import { useEffect } from 'react';
import { GameCanvas, gameHolder } from './ui/GameCanvas';
import { useApp } from './store/app';
import { useSettings } from './store/settings';
import { BootScreen, ControlsScreen, GarageScreen, ModesScreen, RivalsScreen, TitleScreen } from './ui/screens/Menus';
import { LeaderboardScreen } from './ui/screens/Leaderboard';
import { SettingsScreen } from './ui/screens/Settings';
import { ReplayOverlay, ResultsScreen } from './ui/screens/Results';
import { Hud, PauseMenu } from './ui/hud/Hud';

export function App() {
  const screen = useApp((s) => s.screen);
  const paused = useApp((s) => s.paused);
  const phase = useApp((s) => s.phase);

  // pause handling during races
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const app = useApp.getState();
      if (app.screen !== 'race' || app.paused) return;
      if (e.code === 'Escape' || e.code === 'KeyP') {
        gameHolder.game?.setPaused(true);
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
        gameHolder.game?.setPaused(true);
        app.set({ paused: true });
      }
      prevStart = start;
      raf = requestAnimationFrame(poll);
    };
    raf = requestAnimationFrame(poll);
    const onBlur = () => {
      const app = useApp.getState();
      if (app.screen === 'race' && !app.paused && app.phase === 'racing') {
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

  const inRace = screen === 'race' || (screen === 'results' && phase !== 'replay');
  return (
    <div className={`app screen-${screen}`}>
      <GameCanvas />
      <div className="overlay">
        {screen === 'boot' && <BootScreen />}
        {screen === 'title' && <TitleScreen />}
        {screen === 'modes' && <ModesScreen />}
        {screen === 'garage' && <GarageScreen />}
        {screen === 'rivals' && <RivalsScreen />}
        {screen === 'leaderboard' && <LeaderboardScreen />}
        {screen === 'settings' && <SettingsScreen />}
        {screen === 'controls' && <ControlsScreen />}
        {inRace && (phase === 'countdown' || phase === 'racing' || phase === 'finished') && <Hud key={String(gameHolder.game?.currentConfig?.carId) + phase.length} />}
        {screen === 'results' && <ResultsScreen />}
        {screen === 'replay' && <ReplayOverlay />}
        {screen === 'race' && paused && <PauseMenu />}
      </div>
    </div>
  );
}
