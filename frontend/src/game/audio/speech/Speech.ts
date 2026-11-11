/**
 * The rivals' voice: the speech model in a worker (speech.worker.ts), started only when the player wants it.
 * It needs WebGPU and the model on the server; without either, when the download or the set-up fails, or while it
 * is not there yet, `speak` gives nothing and the line is only shown.
 */
import { MODEL_BASE, MODEL_BYTES, MODEL_CACHE, GRAPHS, type FromWorker, type ToWorker } from './protocol';
import { speakable, type VoiceId } from './text';

export type SpeechState =
  /** not looked at yet */
  | 'unknown'
  /** no WebGPU here: there will be no voice */
  | 'unsupported'
  /** this server has no model */
  | 'absent'
  /** could speak, the model is not loaded */
  | 'idle'
  | 'loading'
  | 'ready'
  | 'failed';

export interface Spoken { pcm: Float32Array<ArrayBuffer>; rate: number; ms: number }

export class Speech {
  state: SpeechState = 'unknown';
  /** 0–1 of the model's bytes here; `building`: the GPU is setting the graphs up */
  progress = 0;
  building = false;
  /** why it failed (for the settings' note and the console) */
  reason = '';
  /** denoising steps: 5 is the publisher's quick setting (10 took twice as long for a difference in the detail) */
  steps = 5;
  speed = 1.05;
  private worker: Worker | null = null;
  private waiting = new Map<number, (s: Spoken | null) => void>();
  private seq = 0;
  private listeners = new Set<() => void>();
  private probing: Promise<SpeechState> | null = null;

  subscribe = (fn: () => void) => {
    this.listeners.add(fn);
    return () => void this.listeners.delete(fn);
  };
  private set(state: SpeechState) {
    this.state = state;
    for (const fn of this.listeners) fn();
  }

  /** Can this browser, with this server, speak at all? (asked once) */
  probe(): Promise<SpeechState> {
    return (this.probing ??= (async () => {
      const gpu = (navigator as Navigator & { gpu?: { requestAdapter(): Promise<unknown> } }).gpu;
      const adapter = gpu && typeof Worker !== 'undefined' && typeof caches !== 'undefined' ? await gpu.requestAdapter().catch(() => null) : null;
      if (!adapter) return this.settle('unsupported');
      // (a server without the model answers with the app's page: it must be the model's own description)
      const cfg = await fetch(`${MODEL_BASE}/onnx/tts.json`, { cache: 'no-cache' }).then((r) => (r.ok ? r.json() : null)).catch(() => null) as { ae?: { sample_rate?: number } } | null;
      return this.settle(cfg?.ae?.sample_rate ? 'idle' : 'absent');
    })());
  }
  private settle(state: SpeechState) {
    if (this.state === 'unknown') this.set(state);
    return this.state;
  }

  /** Is the whole model in this browser already? (then loading it asks nothing of the network) */
  async kept(): Promise<boolean> {
    try {
      const cache = await caches.open(MODEL_CACHE);
      for (const g of GRAPHS) if (!(await cache.match(`${MODEL_BASE}/onnx/${g.name}.onnx`))) return false;
      return true;
    } catch {
      return false;
    }
  }

  /**
   * Fetch the model (once: the browser keeps it) and set it up on the GPU. A set-up that failed is tried again
   * only when the player asks (`again`), not at every rival battle.
   */
  async load(again = false) {
    await this.probe();
    if (this.worker || !(this.state === 'idle' || (again && this.state === 'failed'))) return;
    this.progress = 0;
    this.building = false;
    this.reason = '';
    try {
      this.worker = new Worker(new URL('./speech.worker.ts', import.meta.url), { type: 'module' });
    } catch (err) {
      this.fail(String(err));
      return;
    }
    this.worker.onmessage = (e: MessageEvent<FromWorker>) => this.hear(e.data);
    this.worker.onerror = (e) => this.fail(e.message || 'worker');
    this.set('loading');
    this.post({ type: 'load', base: MODEL_BASE });
  }

  /** Give the GPU's memory back (the model stays in the browser's copy). */
  release() {
    if (!this.worker) return;
    this.stop();
    this.set('idle');
  }

  /** Throw the browser's copy of the model away. */
  async forget() {
    this.release();
    await caches.delete(MODEL_CACHE).catch(() => false);
    for (const fn of this.listeners) fn();
  }

  /** A line as sound, or nothing (not ready, nothing to say, a failure, or `within` ms passed). */
  speak(text: string, voice: VoiceId, within = 4000): Promise<Spoken | null> {
    if (this.state !== 'ready' || !speakable(text)) return Promise.resolve(null);
    const id = ++this.seq;
    return new Promise((resolve) => {
      const timer = setTimeout(() => this.answer(id, null), within);
      this.waiting.set(id, (s) => {
        clearTimeout(timer);
        resolve(s);
      });
      this.post({ type: 'speak', id, text, voice, steps: this.steps, speed: this.speed });
    });
  }

  private post(m: ToWorker) {
    this.worker?.postMessage(m);
  }
  private answer(id: number, s: Spoken | null) {
    const fn = this.waiting.get(id);
    this.waiting.delete(id);
    fn?.(s);
  }
  private hear(m: FromWorker) {
    if (m.type === 'progress') {
      this.progress = m.loaded / (m.total || MODEL_BYTES);
      this.building = m.building;
      for (const fn of this.listeners) fn();
    } else if (m.type === 'ready') {
      this.progress = 1;
      this.building = false;
      this.set('ready');
    } else if (m.type === 'failed') this.fail(m.reason);
    else if (m.type === 'spoken') this.answer(m.id, { pcm: m.pcm as Float32Array<ArrayBuffer>, rate: m.rate, ms: m.ms });
    else this.answer(m.id, null);
  }
  private stop() {
    this.worker?.terminate();
    this.worker = null;
    for (const id of [...this.waiting.keys()]) this.answer(id, null);
  }
  private fail(reason: string) {
    this.stop();
    this.reason = reason;
    console.warn('[speech] no voice:', reason);
    this.set('failed');
  }
}

/** the one voice of the app */
export const speech = new Speech();
