import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { TimeOfDay } from '../game/render/Environment';
import type { AssistLevel } from '../game/vehicle/VehicleSim';
import type { QualitySettings } from '../game/Game';
import { COURSES, DEFAULT_COURSE, type CourseId } from '../game/track/courses';
import { isTouchDevice } from '../ui/touch';
import type { BackendPref } from '../game/render/backendChoice';
import type { DrawingRule } from '../game/render/drawingRatio';

export type QualityLevel = 'low' | 'medium' | 'high' | 'ultra';

/**
 * How much smaller than the output the scene is drawn, per axis: FSR's modes by their ratios (`native`: full size,
 * FSR 3's Native AA = temporal anti-aliasing only; `ultra`: FSR 1's Ultra Quality, 1.3×; then FSR 3's Quality 1.5×,
 * Balanced 1.7×, Performance 2×).
 */
export type UpscaleMode = 'native' | 'ultra' | 'quality' | 'balanced' | 'performance';
export const UPSCALE_SCALE: Record<UpscaleMode, number> = { native: 1, ultra: 1 / 1.3, quality: 1 / 1.5, balanced: 1 / 1.7, performance: 1 / 2 };

export interface Settings {
  quality: QualityLevel;
  resolutionScale: number;
  /** the scene drawn smaller and upscaled (WebGPU: FSR 3 over time, which is also the anti-aliasing; WebGL 2: FSR 1) */
  upscale: boolean;
  upscaleMode: UpscaleMode;
  /** sharpening after the upscale, 0 … 1 */
  sharpness: number;
  timeOfDay: TimeOfDay;
  masterVolume: number;
  sfxVolume: number;
  musicVolume: number;
  /** the rain's sound, a share of the effects' volume (0: no rain sound is made at all) */
  rainVolume: number;
  assist: AssistLevel;
  autoShift: boolean;
  showGhost: boolean;
  cornerGuide: boolean;
  /** the renderer's backend: WebGPU where it works (`auto`), or one of the two by hand (render/backendChoice.ts) */
  backend: BackendPref;
  /** the rivals' lines and moves may come from the server's language model (off: the game's own) */
  rivalAi: boolean;
  /**
   * the rivals' lines are spoken (a speech model of ~400 MB on the GPU, fetched once): `ask` until the player has
   * said yes or no at their first rival battle
   */
  rivalVoice: 'ask' | 'on' | 'off';
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
      rainVolume: 1,
      assist: 1,
      autoShift: true,
      showGhost: true,
      cornerGuide: true,
      backend: 'auto',
      rivalAi: true,
      rivalVoice: 'ask',
      controlsGuide: true,
      showFps: false,
      uiMotion: true,
      courseId: DEFAULT_COURSE,
      set: (patch) => set(patch),
    }),
    { name: 'touge-settings', version: 1 },
  ),
);

export interface QualityProfile extends QualitySettings, DrawingRule {
  bloom: boolean;
  smaa: boolean;
  extraFx: boolean;
  /** ambient occlusion */
  ao: boolean;
  /** the street lamps' and headlights' glow in the haze (render/volumetricLights.ts) */
  volumetric: boolean;
  /** scanned asphalt/ground/rock/concrete textures (procedural fallbacks when off) */
  photoTextures: boolean;
  /** distance (m) up to which tree chunks use the detailed cedar mesh (the `legacy` vegetation of the low quality) */
  treeLod: number;
  /**
   * the ground, the road and what is built along it (render/terrainMaterial.ts, roadMaterial.ts, roadside.ts):
   * 0 = the plain materials and shapes, 1 = layered materials with 512 px textures, 2 = 1024 px and every normal
   * map, 3 = also the second texture scale against tiling
   */
  surfaceDetail: 0 | 1 | 2 | 3;
}

/**
 * What quality low draws at most, in millions of pixels (render/drawingRatio.ts), between 0.75 CSS px (what it drew
 * everywhere before 11-20: a desktop at DPR 1 keeps it, a large screen at DPR 2 too) and 0.75 of the screen's own
 * pixels per axis. A phone at DPR 3 (844 × 390 CSS px) draws 1040 × 481 instead of 633 × 292: one drawn pixel over
 * ~2.4 of the screen's instead of 4. Measured 11-20 in phone emulation on the RX 5700 XT (GPU time per pass, WebGPU):
 * low costs 0.40 ms + 1.16 ms per million pixels on oboro at night (0.94–1.23 per million along the road; Edwards
 * 0.11 + 0.99), so this is about 1.6× the GPU time of 0.75 CSS px on oboro, 2× on Edwards; 0.74 MP (1.5 px / CSS px)
 * would be 2× / 2.9×.
 */
export const LOW_PIXELS = 0.5;

export function qualityProfile(level: QualityLevel, scale: number): QualityProfile {
  const dpr = typeof window !== 'undefined' ? window.devicePixelRatio || 1 : 1;
  const base: Record<QualityLevel, QualityProfile> = {
    low: { pixelRatio: 0.75 * Math.max(1, dpr), pixelBudget: LOW_PIXELS, pixelFloor: 0.75, shadows: false, shadowMapSize: 1024, treeDensity: 0.45, headlightShadows: false, bloom: false, smaa: false, extraFx: false, ao: false, volumetric: false, photoTextures: false, treeLod: 240, surfaceDetail: 0, vegetation: { tier: 'legacy', range: 1, undergrowth: 0 } },
    medium: { pixelRatio: 1, shadows: true, shadowMapSize: 1024, treeDensity: 0.7, headlightShadows: false, bloom: true, smaa: true, extraFx: false, ao: false, volumetric: false, photoTextures: true, treeLod: 380, surfaceDetail: 1, vegetation: { tier: 'lite', range: 0.8, undergrowth: 0.5 } },
    high: { pixelRatio: Math.min(dpr, 1.5), shadows: true, shadowMapSize: 2048, treeDensity: 1, headlightShadows: true, bloom: true, smaa: true, extraFx: true, ao: true, volumetric: true, photoTextures: true, treeLod: 560, surfaceDetail: 2, vegetation: { tier: 'full', range: 1, undergrowth: 1 } },
    ultra: { pixelRatio: Math.min(dpr, 2), shadows: true, shadowMapSize: 4096, treeDensity: 1.25, headlightShadows: true, bloom: true, smaa: true, extraFx: true, ao: true, volumetric: true, photoTextures: true, treeLod: 720, surfaceDetail: 3, vegetation: { tier: 'full', range: 1.2, undergrowth: 1.4 } },
  };
  const p = base[level];
  // (the resolution scale shrinks whatever the quality would draw: the budget by its square, as it counts pixels)
  return { ...p, pixelRatio: p.pixelRatio * scale, pixelBudget: p.pixelBudget && p.pixelBudget * scale * scale, pixelFloor: p.pixelFloor && p.pixelFloor * scale };
}

/** The selected course, falling back to the default for unknown stored ids. */
export function currentCourseId(): CourseId {
  const id = useSettings.getState().courseId;
  return id in COURSES ? id : DEFAULT_COURSE;
}
