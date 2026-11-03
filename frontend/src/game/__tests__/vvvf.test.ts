import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { convertPattern, patternFiles } from '../../../tools/vvvf-patterns';
import type { VvvfData } from '../audio/vvvf/data';
import { BLOCK, VvvfEngine, decimationFilter, oversampleFor } from '../audio/vvvf/engine';
import { roundEven, xorshift32 } from '../audio/vvvf/math';
import { Domain, analyze, calculatedGearHarmonics, defaultTrainAudio, lineVoltageSample, realTimeFrequencyControl, trainSoundSample, type Mascon } from '../audio/vvvf/sim';
import { trainVvvfAudio } from '../audio/vvvf/train';
import { TRAIN_INFO, TRAIN_ORDER } from '../vehicle/trains';
import { E231_MITSUBISHI, vvvfDrive } from '../vehicle/vvvf';
import fixture from './fixtures/vvvf-ref.json';

const pattern = (name: string) => JSON.parse(readFileSync(`src/game/audio/vvvf/patterns/${name}.json`, 'utf8')) as VvvfData;

describe('VVVF-Simulator port (audio/vvvf/sim.ts)', () => {
  it('the pattern JSONs are converted from the current YAMLs (npx tsx tools/vvvf-patterns.ts)', () => {
    const files = patternFiles();
    expect(files.length).toBeGreaterThanOrEqual(3);
    for (const { yaml, json } of files) expect(readFileSync(json, 'utf8')).toBe(convertPattern(readFileSync(yaml, 'utf8')));
  });

  // reference: the simulator's own C# files built as a console program (tools/vvvf-ref), float32 output
  it.each(fixture.cases)('matches the C# build sample by sample: $pattern ($mode)', (c) => {
    const data = pattern(c.pattern);
    const audio = defaultTrainAudio();
    if (c.gear) calculatedGearHarmonics(audio, c.gear[0], c.gear[1]);
    const d = new Domain(audio.motor, xorshift32(fixture.seed));
    const dt = 1 / fixture.fs, calc = fixture.calc;
    const m: Mascon = { FrequencyChangeRate: 0, IsBraking: false, IsFreeRunning: false };
    const f32 = new Float32Array(1);
    let n = 0, sumSq = 0, sumAbs = 0, worst = 0;
    for (const [sec, notch, rate] of fixture.scenario as [number, string, number][]) {
      const at = notch === 'P' ? 1 : notch === 'B' ? -1 : 0;
      m.FrequencyChangeRate = at * rate * Math.PI * 2;
      m.IsBraking = at === 0 ? m.IsBraking : at < 0;
      m.IsFreeRunning = at === 0;
      const blocks = roundEven(sec / (calc * dt));
      for (let b = 0; b < blocks; b++) {
        realTimeFrequencyControl(d, m, calc * dt, data);
        analyze(d, data);
        for (let i = 0; i < calc; i++) {
          d.addTimeAll(dt);
          f32[0] = c.mode === 'train' ? trainSoundSample(d, audio) : lineVoltageSample(d);
          const v = f32[0];
          sumSq += v * v;
          sumAbs += Math.abs(v);
          if (n % c.stride === 0) worst = Math.max(worst, Math.abs(v - c.samples[n / c.stride]));
          n++;
        }
      }
    }
    expect(n).toBe(c.n);
    expect(worst).toBeLessThan(1e-7);
    expect(sumSq).toBeCloseTo(c.sumSq, 6);
    expect(sumAbs).toBeCloseTo(c.sumAbs, 6);
  }, 60000);
});

describe("the game's VVVF engine (audio/vvvf/engine.ts)", () => {
  const data = pattern(E231_MITSUBISHI.pattern);
  const audio = trainVvvfAudio(E231_MITSUBISHI);
  const wheel = TRAIN_INFO.e231.wheel;

  /** rms of `seconds` at a speed and notch, after `settle` s */
  function run(engine: VvvfEngine, kmh: number, notch: 1 | 0 | -1, seconds: number, settle = 0.3) {
    const out = new Float32Array(BLOCK);
    let sum = 0, count = 0, peak = 0;
    const blocks = Math.round(((settle + seconds) * engine.sampleRate) / BLOCK);
    for (let b = 0; b < blocks; b++) {
      vvvfDrive(E231_MITSUBISHI, wheel, kmh, notch, engine.drive.braking, engine.drive);
      engine.process(out);
      if (b * BLOCK < settle * engine.sampleRate) continue;
      for (const v of out) {
        expect(Number.isFinite(v)).toBe(true);
        sum += v * v;
        peak = Math.max(peak, Math.abs(v));
        count++;
      }
    }
    return { rms: Math.sqrt(sum / count), peak };
  }

  it('decimates through a symmetric low-pass of unity gain', () => {
    expect(oversampleFor(48000)).toBe(4);
    expect(oversampleFor(44100)).toBe(4);
    expect(oversampleFor(96000)).toBe(2);
    expect(oversampleFor(48000, 2)).toBe(2);
    for (const os of [2, 4]) {
      const h = decimationFilter(os);
      expect(h.reduce((a, b) => a + b, 0)).toBeCloseTo(1, 12);
      for (let i = 0; i < h.length; i++) expect(h[i]).toBeCloseTo(h[h.length - 1 - i], 15);
      // response at the output's Nyquist and above: well down
      const at = (f: number) => {
        let re = 0, im = 0;
        h.forEach((x, i) => ((re += x * Math.cos(2 * Math.PI * f * i)), (im += x * Math.sin(2 * Math.PI * f * i))));
        return Math.hypot(re, im);
      };
      expect(at(0.4 / os)).toBeGreaterThan(0.9);
      expect(at(0.6 / os)).toBeLessThan(1e-3);
    }
  });

  it('is silent standing with the gates off, sounds under power, falls silent coasting, sounds braking', () => {
    const e = new VvvfEngine(data, audio, 48000, 4, xorshift32());
    expect(run(e, 0, 0, 0.5).peak).toBe(0);
    const start = run(e, 5, 1, 0.5);
    expect(start.rms).toBeGreaterThan(1e-4);
    const cruise = run(e, 80, 1, 0.5);
    expect(cruise.rms).toBeGreaterThan(1e-5);
    // the voltage ramps down at the pattern's rate, the currents die away: nothing after a second
    expect(run(e, 80, 0, 0.5, 1.5).peak).toBe(0);
    expect(run(e, 60, -1, 0.5).rms).toBeGreaterThan(1e-5);
    // the electric brake hands over to the air brake at walking pace
    expect(run(e, 2, -1, 0.5, 1.5).peak).toBe(0);
  });

  it('sounds alike at 4× and 2× oversampling (phones)', () => {
    for (const kmh of [10, 30, 70]) {
      const a = run(new VvvfEngine(data, audio, 48000, 4, xorshift32()), kmh, 1, 0.6, 0.5).rms;
      const b = run(new VvvfEngine(data, audio, 48000, 2, xorshift32()), kmh, 1, 0.6, 0.5).rms;
      expect(Math.abs(20 * Math.log10(b / a))).toBeLessThan(3);
    }
  });

  it('every VVVF train has its pattern, gear teeth matching its ratio, and slip only for induction motors', () => {
    for (const id of TRAIN_ORDER) {
      const t = TRAIN_INFO[id], v = t.vvvf;
      if (!v) continue;
      expect(pattern(v.pattern).AcceleratePattern.length).toBeGreaterThan(0);
      expect(v.gear[1] / v.gear[0]).toBeCloseTo(t.gearRatio, 2);
      expect(v.slip > 0).toBe(!t.motor.includes('永久磁石'));
    }
  });
});
