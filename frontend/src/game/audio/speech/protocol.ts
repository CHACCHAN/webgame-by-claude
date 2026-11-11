// What the game and the speech worker say to each other, and the model's files.
import type { VoiceId } from './text';

/** where the server keeps the model (docker-compose `tts` volume; absent on a stack that was not given it) */
export const MODEL_BASE = '/tts/supertonic-3';
/** the browser's own copy of the model's files (Cache Storage: the HTTP cache does not hold on to files this big) */
export const MODEL_CACHE = 'touge-tts-supertonic-3';

/** The model's graphs in the order they are used, with their sizes (the download's total; a file of another size is refused). */
export const GRAPHS = [
  { name: 'duration_predictor', bytes: 3_700_147 },
  { name: 'text_encoder', bytes: 36_416_150 },
  { name: 'vector_estimator', bytes: 256_534_781 },
  { name: 'vocoder', bytes: 101_424_195 },
] as const;
export const MODEL_BYTES = GRAPHS.reduce((a, g) => a + g.bytes, 0);

export type ToWorker =
  | { type: 'load'; base: string }
  | { type: 'speak'; id: number; text: string; voice: VoiceId; steps: number; speed: number };

export type FromWorker =
  /** `loaded` of `total` bytes are here (from the network or the browser's copy); `building`: the graphs are being set up on the GPU */
  | { type: 'progress'; loaded: number; total: number; building: boolean }
  | { type: 'ready'; ms: number }
  | { type: 'failed'; reason: string }
  | { type: 'spoken'; id: number; pcm: Float32Array; rate: number; ms: number }
  | { type: 'unspoken'; id: number; reason: string };
