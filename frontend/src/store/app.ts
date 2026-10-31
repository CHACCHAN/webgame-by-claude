import { create } from 'zustand';
import type { CarId } from '../game/vehicle/carSpecs';
import type { AILevel } from '../game/ai/AIDriver';
import type { GamePhase, RaceMode, RaceResult } from '../game/Game';

export type Screen = 'boot' | 'title' | 'modes' | 'garage' | 'rivals' | 'leaderboard' | 'settings' | 'controls' | 'race' | 'results' | 'replay' | 'courses' | 'loading' | 'online' | 'onlineRoom' | 'onlineResults';

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
  /** screen to open once a course switch has finished loading */
  afterLoad: Screen;
  result: RaceResult | null;
  paused: boolean;
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
  paused: false,
  go: (s) => set({ prevScreen: get().screen, screen: s }),
  set: (patch) => set(patch),
}));
