import type { CarId } from '../vehicle/carSpecs';
import { COURSES, TRAIN_MEDALS, type CourseId } from '../track/courses';
import type { TrainId } from '../vehicle/trains';

export type Medal = 'gold' | 'silver' | 'bronze' | null;

/** Medal times live with each course (see courses.ts, derived from simulated AI laps). */
export function medalFor(course: CourseId, car: CarId, timeMs: number): Medal {
  const m = medalsOf(course, car);
  if (timeMs <= m.gold) return 'gold';
  if (timeMs <= m.silver) return 'silver';
  if (timeMs <= m.bronze) return 'bronze';
  return null;
}

/** The next medal to aim for and its time, or null when gold is already won. */
export function nextTarget(course: CourseId, car: CarId, bestMs: number | null): { medal: Exclude<Medal, null>; timeMs: number } | null {
  const m = medalsOf(course, car);
  if (bestMs === null || bestMs > m.bronze) return { medal: 'bronze', timeMs: m.bronze };
  if (bestMs > m.silver) return { medal: 'silver', timeMs: m.silver };
  if (bestMs > m.gold) return { medal: 'gold', timeMs: m.gold };
  return null;
}

function medalsOf(course: CourseId, car: CarId) {
  const c = COURSES[course];
  return car in c.medals ? c.medals[car as keyof typeof c.medals] : TRAIN_MEDALS[course][car as TrainId];
}

export const MEDAL_LABEL = { gold: 'GOLD', silver: 'SILVER', bronze: 'BRONZE' } as const;
