/**
 * AudioWorklet processor 'jet': a fighter's engines (jet.ts), stereo, bundled by Vite (`?worker&url`,
 * audio/AudioEngine.ts). Options: { seed, params }. k-rate parameters, read once per 128-frame block: spool
 * (0 = idle … 1 = military power), afterburner (0…1), level (0…1), distance (m from the listener). Message: 'stop'.
 */
import { JetSynth, type JetSoundParams } from './jet';

// the AudioWorkletGlobalScope (not in TypeScript's DOM library)
declare const sampleRate: number;
declare function registerProcessor(name: string, ctor: unknown): void;
declare class AudioWorkletProcessor {
  readonly port: MessagePort;
}

export interface JetProcessorOptions {
  seed: number;
  params: JetSoundParams;
}

class JetProcessor extends AudioWorkletProcessor {
  static get parameterDescriptors() {
    return [
      { name: 'spool', defaultValue: 0, minValue: 0, maxValue: 1, automationRate: 'k-rate' },
      { name: 'afterburner', defaultValue: 0, minValue: 0, maxValue: 1, automationRate: 'k-rate' },
      { name: 'level', defaultValue: 0, minValue: 0, maxValue: 1, automationRate: 'k-rate' },
      { name: 'distance', defaultValue: 0, minValue: 0, automationRate: 'k-rate' },
    ];
  }

  private sim: JetSynth;
  private alive = true;

  constructor(options: { processorOptions: JetProcessorOptions }) {
    super();
    this.sim = new JetSynth(sampleRate, options.processorOptions.seed, options.processorOptions.params);
    this.port.onmessage = (e: MessageEvent<'stop'>) => {
      if (e.data === 'stop') this.alive = false;
    };
  }

  process(_inputs: Float32Array[][], outputs: Float32Array[][], params: Record<string, Float32Array>) {
    const out = outputs[0];
    if (!out?.[0] || !this.alive) return this.alive;
    this.sim.spool = params.spool[0];
    this.sim.afterburner = params.afterburner[0];
    this.sim.level = params.level[0];
    this.sim.distance = params.distance[0];
    this.sim.process(out[0], out[1] ?? out[0]);
    return true;
  }
}

registerProcessor('jet', JetProcessor);
