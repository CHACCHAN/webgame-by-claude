// The rivals' voice between the interface and the game: the player's answer, when the model is brought up and
// when its memory is given back (the model itself: game/audio/speech).
import { useSyncExternalStore } from 'react';
import { speech } from '../game/audio/speech/Speech';
import type { Game } from '../game/Game';
import { useApp } from './app';
import { useSettings } from './settings';

// for probes, as `__app` and `__game` are
(window as unknown as { __speech?: unknown }).__speech = speech;

// the voice's model runs on WebGPU only next to a game that is drawn with WebGPU (Speech.usable)
speech.usable = () => useApp.getState().renderer?.backend === 'webgpu';

let version = 0;
speech.subscribe(() => void version++);
/** the voice's state, for a component that shows it */
export function useSpeech() {
  useSyncExternalStore(speech.subscribe, () => version);
  return speech;
}

/** The player's answer to "shall the rivals speak?": yes fetches the model (once) and sets it up. */
export function chooseVoice(on: boolean) {
  useSettings.getState().set({ rivalVoice: on ? 'on' : 'off' });
  if (on) void speech.load(true);
  else speech.release();
}

/** Throw the browser's copy of the model away (and stop speaking). */
export function forgetVoice() {
  useSettings.getState().set({ rivalVoice: 'off' });
  return speech.forget();
}

export function wireVoice(game: Game) {
  game.rivalVoice = (text, voice) => (useSettings.getState().rivalVoice === 'on' ? speech.speak(text, voice) : Promise.resolve(null));
}

// On the way to a rival battle the voice is brought up (the set-up takes seconds: the course loads meanwhile);
// a race of another kind gives its video memory back (the model's weights are ~400 MB there).
useApp.subscribe((s, prev) => {
  if (s.mode === prev.mode && s.screen === prev.screen) return;
  const menu = s.screen === 'boot' || s.screen === 'title' || s.screen === 'modes' || s.screen === 'settings';
  if (s.mode === 'rival' && !menu) {
    if (useSettings.getState().rivalVoice === 'on') void speech.load();
    else void speech.probe();
  } else if (s.screen === 'race' && s.mode !== 'rival') speech.release();
});
