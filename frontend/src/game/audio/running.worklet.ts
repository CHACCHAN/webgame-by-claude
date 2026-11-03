/**
 * AudioWorklet processor 'train-running': a train's running noise (running.ts), bundled by Vite (`?worker&url`,
 * audio/AudioEngine.ts). Options: { params: the train's RunningParams, seed }. k-rate parameters, read once per
 * 128-frame block: kmh (speed), brake (0…1) and lateral (lateral acceleration, m/s²). Message 'stop' ends it.
 */
import { RunningNoise, type RunningParams } from './running';

// the AudioWorkletGlobalScope (not in TypeScript's DOM library)
declare const sampleRate: number;
declare function registerProcessor(name: string, ctor: unknown): void;
declare class AudioWorkletProcessor {
  readonly port: MessagePort;
}

export interface RunningProcessorOptions {
  params: RunningParams;
  seed: number;
}

class TrainRunningProcessor extends AudioWorkletProcessor {
  static get parameterDescriptors() {
    return [
      { name: 'kmh', defaultValue: 0, minValue: 0, automationRate: 'k-rate' },
      { name: 'brake', defaultValue: 0, minValue: 0, maxValue: 1, automationRate: 'k-rate' },
      { name: 'lateral', defaultValue: 0, automationRate: 'k-rate' },
    ];
  }

  private sim: RunningNoise;
  private alive = true;

  constructor(options: { processorOptions: RunningProcessorOptions }) {
    super();
    const o = options.processorOptions;
    this.sim = new RunningNoise(o.params, sampleRate, o.seed);
    this.port.onmessage = (e: MessageEvent) => {
      if (e.data === 'stop') this.alive = false;
    };
  }

  process(_inputs: Float32Array[][], outputs: Float32Array[][], params: Record<string, Float32Array>) {
    const out = outputs[0]?.[0];
    if (!out || !this.alive) return this.alive;
    this.sim.kmh = params.kmh[0];
    this.sim.brake = params.brake[0];
    this.sim.lateral = params.lateral[0];
    this.sim.process(out);
    return true;
  }
}

registerProcessor('train-running', TrainRunningProcessor);
