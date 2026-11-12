/**
 * A course's terrain worked out on every core the machine has (owner 11-12: loading may use all the machine's
 * resources). The heights of the two grids are independent row by row and were 1.8 s of the main thread at every
 * course load; here each worker takes every `n`th row (so that the costly rows near the road are shared out
 * evenly) and the main thread only puts the rows together (`TerrainPlan.finish`). The result is the same to the
 * bit as `buildTerrain`'s, which stays the way of the Node tools and tests, and of a browser where a worker cannot
 * be made or fails.
 */
import type { CourseId } from './courses';
import type { Track } from './Track';
import type { Landform } from './landforms';
import { buildTerrain, planTerrain, type TerrainData, type TerrainOptions, type TerrainStripe } from './terrain';
import type { StripeOrder } from './terrain.worker';

/** threads for the rows: all cores but one (the page's own), within reason */
export function terrainThreads(cores = typeof navigator !== 'undefined' ? navigator.hardwareConcurrency : 1): number {
  return Math.max(1, Math.min(16, (cores || 1) - 1));
}

/** a worker that does not answer within this (ms) is given up on */
const PATIENCE = 20000;

export const terrainStats = { threads: 0, ms: 0, fallback: '' };

export function buildTerrainParallel(course: CourseId, track: Track, lf: Landform, opts: TerrainOptions = {}): Promise<TerrainData> {
  const t0 = performance.now();
  const alone = (why: string) => {
    const t = buildTerrain(track, lf, opts);
    Object.assign(terrainStats, { threads: 0, ms: performance.now() - t0, fallback: why });
    return t;
  };
  if (typeof Worker === 'undefined') return Promise.resolve(alone('no workers'));
  const n = terrainThreads();
  const workers: Worker[] = [];
  const stripes = new Promise<TerrainStripe[]>((resolve, reject) => {
    const got: TerrainStripe[] = [];
    const timer = setTimeout(() => reject(new Error('terrain workers: no answer')), PATIENCE);
    for (let k = 0; k < n; k++) {
      const w = new Worker(new URL('./terrain.worker.ts', import.meta.url), { type: 'module' });
      workers.push(w);
      w.onmessage = (e: MessageEvent<TerrainStripe>) => {
        got.push(e.data);
        if (got.length === n) {
          clearTimeout(timer);
          resolve(got);
        }
      };
      w.onerror = (e) => reject(new Error(`terrain worker: ${e.message || 'failed'}`));
      w.onmessageerror = () => reject(new Error('terrain worker: unreadable answer'));
      w.postMessage({ course, opts, k, n } satisfies StripeOrder);
    }
  });
  return stripes
    .then((s) => {
      const t = planTerrain(track, lf, opts).finish(s);
      Object.assign(terrainStats, { threads: n, ms: performance.now() - t0, fallback: '' });
      return t;
    })
    .catch((e: unknown) => {
      console.warn('[terrain] built on the main thread instead:', e instanceof Error ? e.message : e);
      return alone(e instanceof Error ? e.message : 'failed');
    })
    .finally(() => {
      for (const w of workers) w.terminate();
    });
}
