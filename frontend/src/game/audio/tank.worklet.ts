/**
 * AudioWorklet processor 'tank': a tank's engine and running gear (tank.ts), stereo, bundled by Vite
 * (`?worker&url`, audio/AudioEngine.ts). Options: { seed, params }. k-rate parameters, read once per 128-frame
 * block: rpm, load (0…1), speed (m/s), turn (0…1), level (0…1), distance (m from the listener). Message: 'stop'.
 */
import { TankSynth, type TankSoundParams } from './tank';

// the AudioWorkletGlobalScope (not in TypeScript's DOM library)
declare const sampleRate: number;
declare function registerProcessor(name: string, ctor: unknown): void;
declare class AudioWorkletProcessor {
  readonly port: MessagePort;
}

export interface TankProcessorOptions {
  seed: number;
  params: TankSoundParams;
}

class TankProcessor extends AudioWorkletProcessor {
  static get parameterDescriptors() {
    return [
      { name: 'rpm', defaultValue: 0, minValue: 0, automationRate: 'k-rate' },
      { name: 'load', defaultValue: 0, minValue: 0, maxValue: 1, automationRate: 'k-rate' },
      { name: 'speed', defaultValue: 0, minValue: 0, automationRate: 'k-rate' },
      { name: 'turn', defaultValue: 0, minValue: 0, maxValue: 1, automationRate: 'k-rate' },
      { name: 'level', defaultValue: 0, minValue: 0, maxValue: 1, automationRate: 'k-rate' },
      { name: 'distance', defaultValue: 0, minValue: 0, automationRate: 'k-rate' },
    ];
  }

  private sim: TankSynth;
  private alive = true;

  constructor(options: { processorOptions: TankProcessorOptions }) {
    super();
    this.sim = new TankSynth(sampleRate, options.processorOptions.seed, options.processorOptions.params);
    this.port.onmessage = (e: MessageEvent<'stop'>) => {
      if (e.data === 'stop') this.alive = false;
    };
  }

  process(_inputs: Float32Array[][], outputs: Float32Array[][], params: Record<string, Float32Array>) {
    const out = outputs[0];
    if (!out?.[0] || !this.alive) return this.alive;
    const s = this.sim;
    s.rpm = params.rpm[0];
    s.load = params.load[0];
    s.speed = params.speed[0];
    s.turn = params.turn[0];
    s.level = params.level[0];
    s.distance = params.distance[0];
    s.process(out[0], out[1] ?? out[0]);
    return true;
  }
}

registerProcessor('tank', TankProcessor);
