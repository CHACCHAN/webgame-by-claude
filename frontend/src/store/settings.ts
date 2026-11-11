import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { TimeOfDay } from '../game/render/Environment';
import type { AssistLevel } from '../game/vehicle/VehicleSim';
import type { QualitySettings } from '../game/Game';
import { COURSES, DEFAULT_COURSE, type CourseId } from '../game/track/courses';
import { isTouchDevice } from '../ui/touch';
import type { BackendPref } from '../game/render/backendChoice';

export type QualityLevel = 'low' | 'medium' | 'high' | 'ultra';

/** how much smaller than the output the scene is drawn, per axis (`native`: full size, temporal anti-aliasing only) */
export type UpscaleMode = 'native' | 'ultra' | 'quality' | 'balanced' | 'performance';
export const UPSCALE_SCALE: Record<UpscaleMode, number> = { native: 1, ultra: 0.77, quality: 0.67, balanced: 0.59, performance: 0.5 };

export interface Settings {
  quality: QualityLevel;
  resolutionScale: number;
  /** the scene drawn smaller and upscaled (WebGPU: over time, which is also the anti-aliasing; WebGL 2: FSR 1) */
  upscale: boolean;
  upscaleMode: UpscaleMode;
  /** sharpening after the upscale, 0 … 1 */
  sharpness: number;
  timeOfDay: TimeOfDay;
  masterVolume: number;
  sfxVolume: number;
  musicVolume: number;
  assist: AssistLevel;
  autoShift: boolean;
  showGhost: boolean;
  cornerGuide: boolean;
  /** the renderer's backend: WebGPU where it works (`auto`), or one of the two by hand (render/backendChoice.ts) */
  backend: BackendPref;
  /** the rivals' lines and moves may come from the server's language model (off: the game's own) */
  rivalAi: boolean;
  controlsGuide: boolean;
  showFps: boolean;
  /** the interface's motion: wipes between screens, counting numbers, the title's idle life (off: plain fades) */
  uiMotion: boolean;
  courseId: CourseId;
  set: (patch: Partial<Omit<Settings, 'set'>>) => void;
}

export const useSettings = create<Settings>()(
  persist(
    (set) => ({
      // phones and tablets start light (changeable in the settings)
      quality: isTouchDevice() ? 'low' : 'high',
      resolutionScale: 1,
      upscale: false,
      upscaleMode: 'quality',
      sharpness: 0.5,
      timeOfDay: 'night',
      masterVolume: 0.8,
      sfxVolume: 1,
      musicVolume: 0.6,
      assist: 1,
      autoShift: true,
      showGhost: true,
      cornerGuide: true,
      backend: 'auto',
      rivalAi: true,
      controlsGuide: true,
      showFps: false,
      uiMotion: true,
      courseId: DEFAULT_COURSE,
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
  /** ambient occlusion */
  ao: boolean;
  /** the street lamps' and headlights' glow in the haze (render/volumetricLights.ts) */
  volumetric: boolean;
  /** scanned asphalt/ground/rock/concrete textures (procedural fallbacks when off) */
  photoTextures: boolean;
  /** distance (m) up to which tree chunks use the detailed cedar mesh */
  treeLod: number;
  /**
   * the ground, the road and what is built along it (render/terrainMaterial.ts, roadMaterial.ts, roadside.ts):
   * 0 = the plain materials and shapes, 1 = layered materials with 512 px textures, 2 = 1024 px and every normal
   * map, 3 = also the second texture scale against tiling
   */
  surfaceDetail: 0 | 1 | 2 | 3;
}

export function qualityProfile(level: QualityLevel, scale: number): QualityProfile {
  const dpr = typeof window !== 'undefined' ? window.devicePixelRatio || 1 : 1;
  const base: Record<QualityLevel, QualityProfile> = {
    low: { pixelRatio: 0.75, shadows: false, shadowMapSize: 1024, treeDensity: 0.45, headlightShadows: false, bloom: false, smaa: false, extraFx: false, ao: false, volumetric: false, photoTextures: false, treeLod: 240, surfaceDetail: 0 },
    medium: { pixelRatio: 1, shadows: true, shadowMapSize: 1024, treeDensity: 0.7, headlightShadows: false, bloom: true, smaa: true, extraFx: false, ao: false, volumetric: false, photoTextures: true, treeLod: 380, surfaceDetail: 1 },
    high: { pixelRatio: Math.min(dpr, 1.5), shadows: true, shadowMapSize: 2048, treeDensity: 1, headlightShadows: true, bloom: true, smaa: true, extraFx: true, ao: true, volumetric: true, photoTextures: true, treeLod: 560, surfaceDetail: 2 },
    ultra: { pixelRatio: Math.min(dpr, 2), shadows: true, shadowMapSize: 4096, treeDensity: 1.35, headlightShadows: true, bloom: true, smaa: true, extraFx: true, ao: true, volumetric: true, photoTextures: true, treeLod: 720, surfaceDetail: 3 },
  };
  const p = base[level];
  return { ...p, pixelRatio: p.pixelRatio * scale };
}

/** The selected course, falling back to the default for unknown stored ids. */
export function currentCourseId(): CourseId {
  const id = useSettings.getState().courseId;
  return id in COURSES ? id : DEFAULT_COURSE;
}
