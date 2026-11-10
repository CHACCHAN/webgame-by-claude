import type { CarSpec } from './carSpecs';

/**
 * Kinds of vehicle. Every vehicle shares the base `CarSpec` (physics, dimensions, drivetrain, credit); a kind adds its
 * own data (`spec.train`, `spec.creature`, `spec.bike`) and its own modules: the model (render/), the sound (audio/),
 * the camera profile and the spec sheet. What differs between kinds in shared code is read from `KIND_TRAITS` here or
 * dispatched on `kindOf(spec)`, so a new kind is one entry plus its modules, not a branch at every call site.
 */
export type VehicleKind = 'car' | 'bike' | 'train' | 'creature';

export const kindOf = (spec: Pick<CarSpec, 'train' | 'creature' | 'bike'>): VehicleKind =>
  spec.train ? 'train' : spec.creature ? 'creature' : spec.bike ? 'bike' : 'car';

export interface KindTraits {
  /** badge on the car select (the joke entries) */
  badge: string | null;
  /** what the single-ratio note calls it ("…は変速なし") */
  noun: string;
  /** tailpipe puffs and backfires (an electric car has none either: see `hasExhaust`) */
  exhaust: boolean;
  /** height of the headlamp spotlight above the body origin (m) */
  lampHeight: number;
  /** garage: model scale of the view, yaw off the road (rad), focus behind the root (m), key light height and power */
  garage: { scale: number; yaw: number; focusBack: number; lightHeight: number; light: number };
}

export const KIND_TRAITS: Record<VehicleKind, KindTraits> = {
  car: { badge: null, noun: 'この車', exhaust: true, lampHeight: 0.75, garage: { scale: 1, yaw: 0.35, focusBack: 0, lightHeight: 7, light: 70 } },
  // a bike is framed closer (a third of a car's length) and lit lower
  bike: { badge: null, noun: 'このバイク', exhaust: true, lampHeight: 0.45, garage: { scale: 0.62, yaw: 0.55, focusBack: 0, lightHeight: 5, light: 45 } },
  // a train stands straight along the road and is framed on its leading car (the root is its front bogie); the light
  // sits higher (right above its roof it burnt a white patch into it)
  train: { badge: 'TRAIN ・ ネタ枠', noun: '電車', exhaust: false, lampHeight: 1.1, garage: { scale: 2.6, yaw: 0, focusBack: 7, lightHeight: 16, light: 120 } },
  creature: { badge: 'CREATURE ・ ネタ枠', noun: 'この乗り物', exhaust: false, lampHeight: 0.75, garage: { scale: 1, yaw: 0.35, focusBack: 0, lightHeight: 7, light: 70 } },
};

export const traitsOf = (spec: Pick<CarSpec, 'train' | 'creature' | 'bike'>) => KIND_TRAITS[kindOf(spec)];

/** Puffs, backfires and pops from a tailpipe: engines only (not trains, the cockroach or electric cars). */
export const hasExhaust = (spec: CarSpec) => traitsOf(spec).exhaust && !spec.engine.electric;
