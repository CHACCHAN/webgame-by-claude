import { create } from 'zustand';
import type { CarId } from '../game/vehicle/carSpecs';
import type { AILevel } from '../game/ai/AIDriver';
import type { GamePhase, RaceMode, RaceResult } from '../game/Game';
import type { RenderBackend } from '../game/render/RenderHost';
import type { FallbackReason } from '../game/render/backendChoice';

export type Screen = 'boot' | 'title' | 'modes' | 'about' | 'conditions' | 'garage' | 'transmission' | 'cars' | 'rivals' | 'leaderboard' | 'settings' | 'controls' | 'race' | 'results' | 'replay' | 'courses' | 'loading' | 'online' | 'onlineRoom' | 'onlineResults';

export interface GhostChoice {
  runId: number | 'local';
  label: string;
  carId: CarId;
  timeMs: number;
}

interface AppState {
  screen: Screen;
  prevScreen: Screen;
  loading: { progress: number; label: string } | null;
  phase: GamePhase;
  mode: RaceMode;
  carId: CarId;
  carColor: string | null;
  rivalLevel: AILevel;
  ghostChoice: GhostChoice | null;
  /** screen after the race conditions (car select, or the ghost list in ghost battles) */
  afterLoad: Screen;
  result: RaceResult | null;
  /** the renderer that came up, and why it is WebGL 2 when it is (null until it is up) */
  renderer: { backend: RenderBackend; reason: FallbackReason | null } | null;
  /** work in the background the player waits for: a short label, null when idle */
  busy: string | null;
  /** what the rival said last (before the start, after the finish) */
  rivalLine: { moment: 'before' | 'won' | 'lost'; text: string } | null;
  paused: boolean;
  /** a picker is up over the screen (ui/Shell.tsx `useOverScreen`): the shell's back button closes it */
  over: boolean;
  go: (s: Screen) => void;
  set: (patch: Partial<AppState>) => void;
}

export const useApp = create<AppState>((set, get) => ({
  screen: 'boot',
  prevScreen: 'boot',
  loading: { progress: 0, label: '' },
  phase: 'loading',
  mode: 'time_attack',
  carId: 'hayate',
  carColor: null,
  rivalLevel: 'rookie',
  ghostChoice: null,
  afterLoad: 'garage',
  result: null,
  renderer: null,
  busy: null,
  rivalLine: null,
  paused: false,
  over: false,
  go: (s) => set({ prevScreen: get().screen, screen: s }),
  set: (patch) => set(patch),
}));
