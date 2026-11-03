/**
 * The simulator's train-sound settings (Data/TrainAudio/Struct.cs) for one of the game's trains: its default motor and
 * volumes; no gear whine by default (as the simulator: its calculated one, SetCalculatedGearHarmonic, is ~40 dB louder
 * than the motor through the impulse response; the trains' running-noise recordings carry a real one).
 */
import type { TrainVvvf } from '../../vehicle/vvvf';
import { calculatedGearHarmonics, defaultTrainAudio, type TrainAudio } from './sim';

export function trainVvvfAudio(v: TrainVvvf): TrainAudio {
  const audio = defaultTrainAudio();
  const g = v.gearGain ?? 0;
  if (g === 0) return audio;
  calculatedGearHarmonics(audio, v.gear[0], v.gear[1]);
  if (g !== 1) {
    for (const h of audio.GearSound) {
      h.Amplitude.EndValue *= g;
      h.Amplitude.MaximumValue *= g;
    }
  }
  return audio;
}
