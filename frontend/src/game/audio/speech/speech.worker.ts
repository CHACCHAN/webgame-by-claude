/**
 * The speech model (Supertonic 3, four ONNX graphs) on the GPU, off the main thread: bundled by Vite as a module
 * worker (Speech.ts). It fetches the model once into the browser's Cache Storage, sets the graphs up on WebGPU
 * (no CPU fallback: a line that cannot be spoken is only shown) and turns a line into sound.
 * The steps are the publisher's (web/helper.js of its example, MIT): duration → text encoding → a noise latent
 * denoised in a few steps → vocoder.
 */
import * as ort from 'onnxruntime-web/webgpu';
import wasmUrl from 'onnxruntime-web/ort-wasm-simd-threaded.asyncify.wasm?url';
import { GRAPHS, MODEL_BYTES, MODEL_CACHE, type FromWorker, type ToWorker } from './protocol';
import { encode, prepare, type VoiceId } from './text';

const scope = self as unknown as { postMessage(m: FromWorker, transfer?: Transferable[]): void; onmessage: ((e: MessageEvent<ToWorker>) => void) | null };
const say = (m: FromWorker, transfer?: Transferable[]) => scope.postMessage(m, transfer);

// one thread: more would need a cross-origin isolated page; the work is on the GPU anyway
ort.env.wasm.numThreads = 1;
ort.env.wasm.wasmPaths = { wasm: new URL(wasmUrl, self.location.href).href };
ort.env.logLevel = 'error';

type GraphName = (typeof GRAPHS)[number]['name'];
interface Model {
  base: string;
  graphs: Record<GraphName, ort.InferenceSession>;
  indexer: number[];
  rate: number;
  /** samples of sound per column of the latent, and the latent's rows */
  chunk: number;
  dim: number;
  styles: Map<VoiceId, { ttl: ort.Tensor; dp: ort.Tensor }>;
}
let model: Model | null = null;
let loading: Promise<void> | null = null;
/** one line at a time (the graphs cannot run twice at once) */
let line: Promise<unknown> = Promise.resolve();

async function openCache(): Promise<Cache | null> {
  try {
    return await caches.open(MODEL_CACHE);
  } catch {
    return null;
  }
}

/** A file of the model: from the browser's copy, else from the server (and then kept). `got` hears every piece arrive. */
async function file(cache: Cache | null, url: string, bytes: number | null, got: (n: number) => void): Promise<Uint8Array<ArrayBuffer>> {
  let res = (await cache?.match(url).catch(() => undefined)) ?? null;
  const kept = !!res;
  if (!res) {
    res = await fetch(url);
    if (!res.ok) throw new Error(`${url}: ${res.status}`);
  }
  const size = bytes ?? (Number(res.headers.get('Content-Length')) || 0);
  let buf = new Uint8Array(size);
  let n = 0;
  const reader = res.body!.getReader();
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    if (n + value.length > buf.length) {
      if (bytes !== null) throw new Error(`${url}: longer than its ${bytes} bytes`);
      const grown = new Uint8Array(Math.max(buf.length * 2, n + value.length));
      grown.set(buf.subarray(0, n));
      buf = grown;
    }
    buf.set(value, n);
    n += value.length;
    got(value.length);
  }
  if (bytes !== null && n !== bytes) {
    if (kept) await cache?.delete(url).catch(() => false);
    throw new Error(`${url}: ${n} bytes instead of ${bytes}`);
  }
  const data = n === buf.length ? buf : buf.slice(0, n);
  // (a full disk or a private window: the model works for this sitting and is fetched again next time)
  if (!kept && cache) await cache.put(url, new Response(data, { headers: { 'Content-Type': 'application/octet-stream', 'Content-Length': String(n) } })).catch(() => undefined);
  return data;
}

const json = async <T>(cache: Cache | null, url: string): Promise<T> => JSON.parse(new TextDecoder().decode(await file(cache, url, null, () => undefined))) as T;

interface Config { ae: { sample_rate: number; base_chunk_size: number }; ttl: { chunk_compress_factor: number; latent_dim: number } }
interface StyleFile { style_ttl: { data: unknown[]; dims: number[] }; style_dp: { data: unknown[]; dims: number[] } }

async function load(base: string) {
  const t0 = performance.now();
  const cache = await openCache();
  const cfg = await json<Config>(cache, `${base}/onnx/tts.json`);
  const indexer = await json<number[]>(cache, `${base}/onnx/unicode_indexer.json`);
  let loaded = 0;
  const graphs = {} as Model['graphs'];
  for (const g of GRAPHS) {
    const data = await file(cache, `${base}/onnx/${g.name}.onnx`, g.bytes, (n) => {
      loaded += n;
      say({ type: 'progress', loaded, total: MODEL_BYTES, building: false });
    });
    say({ type: 'progress', loaded, total: MODEL_BYTES, building: true });
    // (errors only: the runtime warns for every graph that a few small nodes stay on the CPU)
    graphs[g.name] = await ort.InferenceSession.create(data, { executionProviders: ['webgpu'], graphOptimizationLevel: 'all', logSeverityLevel: 3 });
  }
  model = {
    base, graphs, indexer, rate: cfg.ae.sample_rate,
    chunk: cfg.ae.base_chunk_size * cfg.ttl.chunk_compress_factor,
    dim: cfg.ttl.latent_dim * cfg.ttl.chunk_compress_factor,
    styles: new Map(),
  };
  // the first run builds the GPU's shaders (about a second): not while the first line waits. A line as long as
  // the rivals' and with as many steps, so that it builds what they will need
  await synth('ここは俺の庭だ。ついてこれるかな?', 'M1', 5, 1.05);
  say({ type: 'ready', ms: performance.now() - t0 });
}

async function style(m: Model, voice: VoiceId) {
  let s = m.styles.get(voice);
  if (!s) {
    const j = await json<StyleFile>(await openCache(), `${m.base}/voice_styles/${voice}.json`);
    const tensor = (o: { data: unknown[]; dims: number[] }) => new ort.Tensor('float32', Float32Array.from((o.data as number[][]).flat(Infinity as 1) as number[]), o.dims);
    s = { ttl: tensor(j.style_ttl), dp: tensor(j.style_dp) };
    m.styles.set(voice, s);
  }
  return s;
}

const gauss = () => Math.sqrt(-2 * Math.log(Math.max(1e-4, Math.random()))) * Math.cos(2 * Math.PI * Math.random());

async function synth(text: string, voice: VoiceId, steps: number, speed: number): Promise<Float32Array<ArrayBuffer>> {
  const m = model;
  if (!m) throw new Error('not loaded');
  const s = await style(m, voice);
  const { ids } = encode(prepare(text.slice(0, 160)), m.indexer);
  const n = ids.length;
  const textIds = new ort.Tensor('int64', BigInt64Array.from(ids, (x) => BigInt(x)), [1, n]);
  const textMask = new ort.Tensor('float32', new Float32Array(n).fill(1), [1, 1, n]);
  const dp = await m.graphs.duration_predictor.run({ text_ids: textIds, style_dp: s.dp, text_mask: textMask });
  const seconds = Math.min(20, (dp.duration.data as Float32Array)[0] / speed);
  const enc = await m.graphs.text_encoder.run({ text_ids: textIds, style_ttl: s.ttl, text_mask: textMask });
  const samples = Math.floor(seconds * m.rate);
  const len = Math.max(1, Math.ceil(samples / m.chunk));
  let latent = new Float32Array(m.dim * len);
  for (let i = 0; i < latent.length; i++) latent[i] = gauss();
  const latentMask = new ort.Tensor('float32', new Float32Array(len).fill(1), [1, 1, len]);
  const total = new ort.Tensor('float32', Float32Array.of(steps), [1]);
  for (let step = 0; step < steps; step++) {
    const out = await m.graphs.vector_estimator.run({
      noisy_latent: new ort.Tensor('float32', latent, [1, m.dim, len]), text_emb: enc.text_emb, style_ttl: s.ttl,
      latent_mask: latentMask, text_mask: textMask, current_step: new ort.Tensor('float32', Float32Array.of(step), [1]), total_step: total,
    });
    latent = Float32Array.from(out.denoised_latent.data as Float32Array);
  }
  const voc = await m.graphs.vocoder.run({ latent: new ort.Tensor('float32', latent, [1, m.dim, len]) });
  return Float32Array.from((voc.wav_tts.data as Float32Array).subarray(0, samples));
}

scope.onmessage = (e) => {
  const msg = e.data;
  if (msg.type === 'load') {
    loading ??= load(msg.base).catch((err: unknown) => {
      model = null;
      say({ type: 'failed', reason: String((err as Error)?.message ?? err) });
    });
  } else if (msg.type === 'speak') {
    line = line.then(async () => {
      const t0 = performance.now();
      try {
        const pcm = await synth(msg.text, msg.voice, msg.steps, msg.speed);
        say({ type: 'spoken', id: msg.id, pcm, rate: model!.rate, ms: performance.now() - t0 }, [pcm.buffer]);
      } catch (err) {
        say({ type: 'unspoken', id: msg.id, reason: String((err as Error)?.message ?? err) });
      }
    });
  }
};
