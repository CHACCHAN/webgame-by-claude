/**
 * One thread's share of a course's terrain (terrainJob.ts): it lays the course out again from its id (the design
 * and the landform are code, not data that could be sent) and works out every `n`th row of the two grids.
 */
import { COURSES, type CourseId } from './courses';
import { Track } from './Track';
import { planTerrain, type TerrainOptions, type TerrainStripe } from './terrain';

export interface StripeOrder {
  course: CourseId;
  opts: TerrainOptions;
  k: number;
  n: number;
}

const scope = self as unknown as { postMessage(m: TerrainStripe, transfer: Transferable[]): void; onmessage: ((e: MessageEvent<StripeOrder>) => void) | null };

scope.onmessage = (e) => {
  const { course, opts, k, n } = e.data;
  const info = COURSES[course];
  const s = planTerrain(new Track(info.design), info.landform, opts).stripe(k, n);
  scope.postMessage(s, [s.nearH.buffer, s.nearD.buffer, s.nearE.buffer, s.nearI.buffer, s.farH.buffer]);
};
