import type { CarId } from '../vehicle/carSpecs';

export type Medal = 'gold' | 'silver' | 'bronze' | null;

/**
 * Target times (ms, dry, standing start). Gold is roughly the "legend" AI on
 * the same car (see tools/sim-run.ts), silver/bronze give stepping stones.
 */
export const MEDAL_TIMES: Record<CarId, { gold: number; silver: number; bronze: number }> = {
  hayate: { gold: 108_000, silver: 115_000, bronze: 125_000 },
  raijin: { gold: 96_000, silver: 103_000, bronze: 113_000 },
  shiden: { gold: 97_000, silver: 104_000, bronze: 115_000 },
};

export function medalFor(car: CarId, timeMs: number): Medal {
  const m = MEDAL_TIMES[car];
  if (timeMs <= m.gold) return 'gold';
  if (timeMs <= m.silver) return 'silver';
  if (timeMs <= m.bronze) return 'bronze';
  return null;
}

/** The next medal to aim for and its time, or null when gold is already won. */
export function nextTarget(car: CarId, bestMs: number | null): { medal: Exclude<Medal, null>; timeMs: number } | null {
  const m = MEDAL_TIMES[car];
  if (bestMs === null || bestMs > m.bronze) return { medal: 'bronze', timeMs: m.bronze };
  if (bestMs > m.silver) return { medal: 'silver', timeMs: m.silver };
  if (bestMs > m.gold) return { medal: 'gold', timeMs: m.gold };
  return null;
}

export const MEDAL_LABEL = { gold: 'GOLD', silver: 'SILVER', bronze: 'BRONZE' } as const;
