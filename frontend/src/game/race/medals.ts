import { CAR_SPECS, type CarId, type RoadCarId } from '../vehicle/carSpecs';
import { BIKE_MEDALS, COURSES, JET_MEDALS, ROACH_MEDALS, TRAIN_MEDALS, type CourseId } from '../track/courses';
import type { JetId } from '../vehicle/jets';
import type { TrainId } from '../vehicle/trains';
import type { BikeId } from '../vehicle/bikes';
import { kindOf } from '../vehicle/kinds';

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
  switch (kindOf(CAR_SPECS[car])) {
    case 'creature':
      return ROACH_MEDALS[course];
    case 'train':
      return TRAIN_MEDALS[course][car as TrainId];
    case 'bike':
      return BIKE_MEDALS[course][car as BikeId];
    case 'jet':
      // (they run at Edwards only)
      return JET_MEDALS[car as JetId];
    default:
      return COURSES[course].medals[car as RoadCarId];
  }
}

export const MEDAL_LABEL = { gold: 'GOLD', silver: 'SILVER', bronze: 'BRONZE' } as const;
