import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { TimeOfDay } from '../game/render/Environment';
import type { AssistLevel } from '../game/vehicle/VehicleSim';
import type { QualitySettings } from '../game/Game';

export type QualityLevel = 'low' | 'medium' | 'high' | 'ultra';

export interface Settings {
  quality: QualityLevel;
  resolutionScale: number;
  timeOfDay: TimeOfDay;
  masterVolume: number;
  sfxVolume: number;
  musicVolume: number;
  assist: AssistLevel;
  autoShift: boolean;
  showGhost: boolean;
  showFps: boolean;
  set: (patch: Partial<Omit<Settings, 'set'>>) => void;
}

export const useSettings = create<Settings>()(
  persist(
    (set) => ({
      quality: 'high',
      resolutionScale: 1,
      timeOfDay: 'night',
      masterVolume: 0.8,
      sfxVolume: 1,
      musicVolume: 0.6,
      assist: 1,
      autoShift: true,
      showGhost: true,
      showFps: false,
      set: (patch) => set(patch),
    }),
    { name: 'touge-settings', version: 1 },
  ),
);

export interface QualityProfile extends QualitySettings {
  pixelRatio: number;
  bloom: boolean;
  smaa: boolean;
  extraFx: boolean;
}

export function qualityProfile(level: QualityLevel, scale: number): QualityProfile {
  const dpr = typeof window !== 'undefined' ? window.devicePixelRatio || 1 : 1;
  const base: Record<QualityLevel, QualityProfile> = {
    low: { pixelRatio: 0.75, shadows: false, shadowMapSize: 1024, treeDensity: 0.45, headlightShadows: false, bloom: false, smaa: false, extraFx: false },
    medium: { pixelRatio: 1, shadows: true, shadowMapSize: 1024, treeDensity: 0.7, headlightShadows: false, bloom: true, smaa: true, extraFx: false },
    high: { pixelRatio: Math.min(dpr, 1.5), shadows: true, shadowMapSize: 2048, treeDensity: 1, headlightShadows: true, bloom: true, smaa: true, extraFx: true },
    ultra: { pixelRatio: Math.min(dpr, 2), shadows: true, shadowMapSize: 4096, treeDensity: 1.35, headlightShadows: true, bloom: true, smaa: true, extraFx: true },
  };
  const p = base[level];
  return { ...p, pixelRatio: p.pixelRatio * scale };
}
