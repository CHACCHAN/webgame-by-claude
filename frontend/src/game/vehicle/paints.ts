import type { CarId } from './carSpecs';
import { liverySwatch, TRAIN_INFO, TRAIN_ORDER, type TrainId } from './trains';
import { ROACH_INFO } from './roach';
import { BIKE_ORDER, BIKE_SPECS, type BikeId } from './bikes';
import { TANK_ORDER, TANK_SPECS, type TankId } from './tanks';
import { JET_ORDER, JET_SPECS, type JetId } from './jets';

/**
 * Body colours offered for each vehicle (first = default): the car select's swatches. Here, not in the UI, because
 * an online room's paints come from other players' games and the engine draws only what its vehicle offers
 * (`offeredPaint`).
 */
export const COLORS: Record<CarId, string[]> = {
  // trains: one swatch per line it runs on (its paint and displays)
  ...(Object.fromEntries(TRAIN_ORDER.map((id) => [id, TRAIN_INFO[id].liveries.map(liverySwatch)])) as Record<TrainId, string[]>),
  hayate: ['#e8e6e1', '#b3121c', '#1b1d22', '#2f6db5', '#e0b400'],
  raijin: ['#d9dbde', '#1d4fa8', '#0c0c0e', '#8f1218', '#5e6b3a'],
  shiden: ['#f5c400', '#c8102e', '#f2f2f0', '#121214', '#3a7d44'],
  supra: ['#eeeeee', '#d8481c', '#c40d1e', '#121214', '#1f5fb5'],
  r34: ['#2f4fa6', '#e9e9ea', '#121214', '#8a8f96', '#4a2a63'],
  s15: ['#f5cf30', '#e9e9ea', '#121214', '#b3121c', '#2f6db5'],
  // bare stainless, then wraps
  cybertruck: ['#b9bdc0', '#232427', '#e6e6e4', '#4b5a3a', '#7d1d1d'],
  u9: ['#1b1d22', '#e8e9ea', '#1f5bd6', '#c9d400', '#8c1c22'],
  // motorcycles: one swatch per factory colour
  ...(Object.fromEntries(BIKE_ORDER.map((id) => [id, BIKE_SPECS[id].bike!.liveries.map((l) => l.swatch)])) as Record<BikeId, string[]>),
  // tanks: their own camouflage
  ...(Object.fromEntries(TANK_ORDER.map((id) => [id, [TANK_SPECS[id].colors.body]])) as Record<TankId, string[]>),
  // fighters: one swatch per scheme / two-seat variant
  ...(Object.fromEntries(JET_ORDER.map((id) => [id, JET_SPECS[id].jet!.liveries.map((l) => l.swatch)])) as Record<JetId, string[]>),
  // the cockroach: one swatch per species colouring
  roach: ROACH_INFO.liveries.map((l) => l.swatch),
};

/**
 * A paint as the vehicle offers it (its swatch, as written in `COLORS`), or undefined for one it does not offer: a
 * colour that came from somewhere else (another player's game, an older or newer build, the server's pattern check)
 * is drawn only if it is one of the vehicle's own.
 */
export function offeredPaint(carId: CarId, color: string | null | undefined): string | undefined {
  if (!color) return undefined;
  const want = color.toLowerCase();
  return COLORS[carId]?.find((c) => c.toLowerCase() === want);
}
