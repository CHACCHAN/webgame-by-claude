import { uniform } from 'three/tsl';

/**
 * 0..1 how wet the world is (the time of day's `rain`), set by `Game.applyTimeOfDay`. The ground's, the road's and
 * the roadside's materials read it: darker and glossier surfaces, puddles where the road lies flat.
 */
export const wetness = uniform(0);
