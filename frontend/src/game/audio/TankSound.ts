import type { CarSpec } from '../vehicle/carSpecs';
import type { TankSoundParams } from './tank';

/** a track link's length (m): an estimate for all four tracked ones, for the sound only (audio/tank.ts) */
const LINK = 0.17;

/** What a tank's sound is made from: its engine's kind and speeds, its running gear. */
export function tankSoundOf(spec: CarSpec): TankSoundParams {
  const t = spec.tank!;
  return {
    engine: t.sound,
    cylinders: Math.max(1, spec.engine.cylinders),
    idle: spec.engine.idleRpm,
    rated: spec.engine.redline,
    pitch: t.running === 'tracks' ? LINK : 0,
  };
}

/** the stand-in's face: the game's plain engine sound (`EngineSound` in AudioEngine.ts) */
interface Plain {
  update(rpm: number, throttle: number, boost: number, volume: number, redline: number, brake?: number): void;
  dispose(): void;
}

/**
 * A tank's engine and running gear for the game: the controller of the AudioWorklet 'tank' (tank.ts), with the same
 * face as the other vehicles' sounds. The node joins once its module is loaded (`setNode`); until then, and where
 * AudioWorklet is missing, the game's plain engine sound stands in (no tracks in it).
 */
export class TankSound {
  readonly out: GainNode;
  private node: AudioWorkletNode | null = null;
  private plain: Plain | null;
  private far = 0;
  private speed = 0;
  private turn = 0;

  /** `plain`: makes the stand-in, sounding into the node it is given */
  constructor(private ctx: BaseAudioContext, destination: AudioNode, plain: (out: AudioNode) => Plain) {
    this.out = ctx.createGain();
    this.out.connect(destination);
    this.plain = plain(this.out);
  }

  /** the worklet's node takes over from the stand-in */
  setNode(node: AudioWorkletNode) {
    this.node = node;
    node.connect(this.out);
    this.plain?.dispose();
    this.plain = null;
  }

  /** how far the vehicle is from the listener (m) */
  distance(d: number) {
    this.far = Math.max(0, d);
  }

  /** the speed over the ground (m/s) and how hard it turns (rad/s): the tracks' clatter and squeal */
  motion(speed: number, yawRate: number) {
    this.speed = Math.abs(speed);
    this.turn = Math.min(1, Math.abs(yawRate) / 0.5);
  }

  update(rpm: number, throttle: number, boost: number, volume: number, redline: number, brake?: number) {
    const n = this.node;
    if (!n) {
      this.plain?.update(rpm, throttle, boost, volume / (1 + this.far / 50), redline, brake);
      return;
    }
    const t = this.ctx.currentTime;
    n.parameters.get('rpm')!.setValueAtTime(Math.max(0, rpm), t);
    n.parameters.get('load')!.setValueAtTime(Math.min(1, Math.max(0, throttle)), t);
    n.parameters.get('speed')!.setValueAtTime(this.speed, t);
    n.parameters.get('turn')!.setValueAtTime(this.turn, t);
    n.parameters.get('level')!.setValueAtTime(Math.min(1, Math.max(0, volume)), t);
    n.parameters.get('distance')!.setValueAtTime(this.far, t);
  }

  /** no blow-off valve to hear */
  blowOff() {
    return false;
  }

  dispose() {
    this.node?.port.postMessage('stop');
    this.node?.disconnect();
    this.plain?.dispose();
    this.out.disconnect();
  }
}
