import type { CarSpec } from './carSpecs';

/**
 * Kinds of vehicle. Every vehicle shares the base `CarSpec` (physics, dimensions, drivetrain, credit); a kind adds its
 * own data (`spec.train`, `spec.creature`, `spec.bike`) and its own modules: the model (render/), the sound (audio/),
 * the camera profile and the spec sheet. What differs between kinds in shared code is read from `KIND_TRAITS` here or
 * dispatched on `kindOf(spec)`, so a new kind is one entry plus its modules, not a branch at every call site.
 */
export type VehicleKind = 'car' | 'bike' | 'tank' | 'jet' | 'train' | 'creature';

type KindKeys = Pick<CarSpec, 'train' | 'creature' | 'bike' | 'tank' | 'jet'>;

export const kindOf = (spec: KindKeys): VehicleKind =>
  spec.train ? 'train' : spec.creature ? 'creature' : spec.bike ? 'bike' : spec.tank ? 'tank' : spec.jet ? 'jet' : 'car';

export interface KindTraits {
  /** the kind's tab on the car select */
  label: string;
  /** badge on the car select (the joke entries) */
  badge: string | null;
  /** what the single-ratio note calls it ("…は変速なし") */
  noun: string;
  /** tailpipe puffs and backfires (an electric car has none either: see `hasExhaust`) */
  exhaust: boolean;
  /** height of the headlamp spotlight above the body origin (m) */
  lampHeight: number;
  /**
   * garage: model scale of the view, yaw off the road (rad), focus behind the root (m), key light height and power,
   * and for a view that puts the vehicle at a given place on the screen (the car select): the height of what is to
   * be seen's middle above the road (m; a bike's with its rider) and the width the picture has to take in (m; a
   * train's is its leading car)
   */
  garage: { scale: number; yaw: number; focusBack: number; lightHeight: number; light: number; middle: number; span: number };
}

export const KIND_TRAITS: Record<VehicleKind, KindTraits> = {
  car: { label: '車', badge: null, noun: 'この車', exhaust: true, lampHeight: 0.75, garage: { scale: 1, yaw: 0.35, focusBack: 0, lightHeight: 7, light: 70, middle: 0.65, span: 5.2 } },
  // a bike is framed closer (a third of a car's length) and lit lower
  bike: { label: 'バイク', badge: null, noun: 'このバイク', exhaust: true, lampHeight: 0.45, garage: { scale: 0.62, yaw: 0.55, focusBack: 0, lightHeight: 5, light: 45, middle: 0.95, span: 3.2 } },
  // a train stands straight along the road and is framed on its leading car (the root is its front bogie); the light
  // sits higher (right above its roof it burnt a white patch into it)
  train: { label: '電車', badge: 'TRAIN ・ ネタ枠', noun: '電車', exhaust: false, lampHeight: 1.1, garage: { scale: 2.6, yaw: 0, focusBack: 7, lightHeight: 16, light: 120, middle: 1.9, span: 22 } },
  // a tank sits higher and wider than a car; its lamps are small convoy lamps on the hull front
  tank: { label: '戦車', badge: 'TANK ・ ネタ枠', noun: 'この戦車', exhaust: false, lampHeight: 1.4, garage: { scale: 1.6, yaw: 0.45, focusBack: 0, lightHeight: 10, light: 110, middle: 1.2, span: 8.3 } },
  // a fighter is framed whole (19–23 m long, 13–17 m span); the taxi lamp sits on the nose gear
  jet: { label: '戦闘機', badge: 'FIGHTER ・ エドワーズ限定', noun: 'この機体', exhaust: false, lampHeight: 1.6, garage: { scale: 3.2, yaw: 0.6, focusBack: 1.5, lightHeight: 16, light: 160, middle: 2.0, span: 16.6 } },
  creature: { label: 'その他', badge: 'CREATURE ・ ネタ枠', noun: 'この乗り物', exhaust: false, lampHeight: 0.75, garage: { scale: 1, yaw: 0.35, focusBack: 0, lightHeight: 7, light: 70, middle: 0.4, span: 5.2 } },
};

/** the kinds in the order of the car select's tabs (a tab shows only when the list has a vehicle of its kind) */
export const KIND_ORDER: VehicleKind[] = ['car', 'bike', 'tank', 'jet', 'train', 'creature'];

export const traitsOf = (spec: KindKeys) => KIND_TRAITS[kindOf(spec)];

/** Puffs, backfires and pops from a tailpipe: engines only (not trains, the cockroach or electric cars). */
export const hasExhaust = (spec: CarSpec) => traitsOf(spec).exhaust && !spec.engine.electric;
