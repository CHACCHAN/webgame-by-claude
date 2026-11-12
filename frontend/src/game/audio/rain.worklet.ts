/**
 * AudioWorklet processor 'rain': the rain around the listener (rain.ts), stereo, bundled by Vite (`?worker&url`,
 * audio/AudioEngine.ts). Options: { seed }. k-rate parameters, read once per 128-frame block: level (the weather's
 * rain 0…1), speed (m/s), cover (0…1 under a roof). Messages: { body } (what the rain falls on: RainBody), 'stop'.
 */
import { RainSynth, type RainBody } from './rain';

// the AudioWorkletGlobalScope (not in TypeScript's DOM library)
declare const sampleRate: number;
declare function registerProcessor(name: string, ctor: unknown): void;
declare class AudioWorkletProcessor {
  readonly port: MessagePort;
}

export interface RainProcessorOptions {
  seed: number;
}

class RainProcessor extends AudioWorkletProcessor {
  static get parameterDescriptors() {
    return [
      { name: 'level', defaultValue: 0, minValue: 0, maxValue: 1, automationRate: 'k-rate' },
      { name: 'speed', defaultValue: 0, minValue: 0, automationRate: 'k-rate' },
      { name: 'cover', defaultValue: 0, minValue: 0, maxValue: 1, automationRate: 'k-rate' },
    ];
  }

  private sim: RainSynth;
  private alive = true;

  constructor(options: { processorOptions: RainProcessorOptions }) {
    super();
    this.sim = new RainSynth(sampleRate, options.processorOptions.seed);
    this.port.onmessage = (e: MessageEvent<'stop' | { body: RainBody }>) => {
      if (e.data === 'stop') this.alive = false;
      else this.sim.body = e.data.body;
    };
  }

  process(_inputs: Float32Array[][], outputs: Float32Array[][], params: Record<string, Float32Array>) {
    const out = outputs[0];
    if (!out?.[0] || !this.alive) return this.alive;
    this.sim.level = params.level[0];
    this.sim.speed = params.speed[0];
    this.sim.cover = params.cover[0];
    this.sim.process(out[0], out[1] ?? out[0]);
    return true;
  }
}

registerProcessor('rain', RainProcessor);
