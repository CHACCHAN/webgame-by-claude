/**
 * AudioWorklet processor 'vvvf-sim': a train's in-train VVVF sound (engine.ts: VVVF-Simulator's calculation),
 * bundled by Vite (`?worker&url`, audio/AudioEngine.ts). Options: { data: the control pattern, audio: the motor and
 * gear sounds, oversample, tables: the pattern's CHM / SHE switching angles }. k-rate parameters, read once per 128-frame block: hz (inverter output), rotor (the
 * motor's electrical frequency from the wheels), braking and power (0 / 1). Message 'stop' ends the processor.
 */
import type { VvvfData } from './data';
import { VvvfEngine } from './engine';
import type { TrainAudio } from './sim';

// the AudioWorkletGlobalScope (not in TypeScript's DOM library)
declare const sampleRate: number;
declare function registerProcessor(name: string, ctor: unknown): void;
declare class AudioWorkletProcessor {
  readonly port: MessagePort;
}

export interface VvvfProcessorOptions {
  data: VvvfData;
  audio: TrainAudio;
  oversample: number;
  /** the CHM / SHE switching-angle tables of the pattern (name → .bin bytes) */
  tables: Record<string, ArrayBuffer>;
}

class VvvfSimProcessor extends AudioWorkletProcessor {
  static get parameterDescriptors() {
    return [
      { name: 'hz', defaultValue: 0, minValue: 0, automationRate: 'k-rate' },
      { name: 'rotor', defaultValue: 0, minValue: 0, automationRate: 'k-rate' },
      { name: 'braking', defaultValue: 0, minValue: 0, maxValue: 1, automationRate: 'k-rate' },
      { name: 'power', defaultValue: 0, minValue: 0, maxValue: 1, automationRate: 'k-rate' },
    ];
  }

  private engine: VvvfEngine;
  private alive = true;

  constructor(options: { processorOptions: VvvfProcessorOptions }) {
    super();
    const o = options.processorOptions;
    this.engine = new VvvfEngine(o.data, o.audio, sampleRate, o.oversample, Math.random, true, o.tables);
    this.port.onmessage = (e: MessageEvent) => {
      if (e.data === 'stop') this.alive = false;
    };
  }

  process(_inputs: Float32Array[][], outputs: Float32Array[][], params: Record<string, Float32Array>) {
    const out = outputs[0]?.[0];
    if (!out || !this.alive) return this.alive;
    const dr = this.engine.drive;
    dr.hz = params.hz[0];
    dr.rotorHz = params.rotor[0];
    dr.braking = params.braking[0] > 0.5;
    dr.powerOff = params.power[0] < 0.5;
    this.engine.process(out);
    return true;
  }
}

registerProcessor('vvvf-sim', VvvfSimProcessor);
