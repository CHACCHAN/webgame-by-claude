/**
 * Render VVVF-Simulator's sound with the JS port (audio/vvvf/sim.ts) along a master-controller scenario, the way
 * the simulator's real-time mode drives it, to raw float32 samples + a trace per control block (same columns as
 * the C# reference driver, so the two can be compared sample by sample):
 *   npx tsx tools/vvvf-render.ts <pattern> <train|line> <scenario.txt> <fs> <calcCount> <out.f32> [gear1 gear2] [seed]
 * scenario lines: "<seconds> <P|N|B> <Hz per second>" (power / neutral / brake and the base frequency's rate).
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { normalizeVvvf } from '../src/game/audio/vvvf/data';
import { roundEven, xorshift32 } from '../src/game/audio/vvvf/math';
import { Domain, analyze, calculatedGearHarmonics, defaultTrainAudio, lineVoltageSample, realTimeFrequencyControl, trainSoundSample, type Mascon } from '../src/game/audio/vvvf/sim';

const root = join(fileURLToPath(import.meta.url), '..', '..');
const [name, mode, scen, fsArg, calcArg, outPath, g1 = '0', g2 = '0', seed = '2463534242'] = process.argv.slice(2);
const data = normalizeVvvf(JSON.parse(readFileSync(join(root, 'src/game/audio/vvvf/patterns', name + '.json'), 'utf8')));
const audio = defaultTrainAudio();
if (+g1 > 0) calculatedGearHarmonics(audio, +g1, +g2);
const d = new Domain(audio.motor, xorshift32(+seed));
const fs = +fsArg, calc = +calcArg, dt = 1 / fs;
const m: Mascon = { FrequencyChangeRate: 0, IsBraking: false, IsFreeRunning: false };
const lines = readFileSync(scen, 'utf8').split('\n');
let total = 0;
for (const l of lines) {
  const p = l.trim().split(/\s+/);
  if (p.length >= 3 && !p[0].startsWith('#')) total += roundEven(+p[0] / (calc * dt)) * calc;
}
const out = new Float32Array(total);
const trace: string[] = ['t,base,control,freeRun,powerOff,braking,none,zero,amp,type,count,alt,carrier,Te,wr'];
let n = 0, t = 0;
const t0 = performance.now();
for (const l of lines) {
  const p = l.trim().split(/\s+/);
  if (p.length < 3 || p[0].startsWith('#')) continue;
  const at = p[1] === 'P' ? 1 : p[1] === 'B' ? -1 : 0;
  m.FrequencyChangeRate = at * +p[2] * Math.PI * 2;
  const preBraking = m.IsBraking;
  m.IsFreeRunning = at === 0;
  m.IsBraking = at === 0 ? preBraking : at < 0;
  const blocks = roundEven(+p[0] / (calc * dt));
  for (let b = 0; b < blocks; b++) {
    realTimeFrequencyControl(d, m, calc * dt, data);
    analyze(d, data);
    const es = d.es;
    const carrier = !es.isNone && es.carrier ? (es.carrier.vibrato ? 'vib' : String(es.carrier.constant)) : '';
    trace.push([
      t, d.baseWave.frequency, d.controlFrequency, d.freeRun ? 1 : 0, d.powerOff ? 1 : 0, d.brake ? 1 : 0, es.isNone ? 1 : 0, es.isZeroOutput ? 1 : 0,
      es.baseWaveAmplitude ?? -1, es.isNone ? '' : es.pattern!.PulseMode.PulseType, es.isNone ? '' : es.pattern!.PulseMode.PulseCount, es.isNone ? '' : es.pattern!.PulseMode.Alternative,
      carrier, d.motor.Te, d.motor.wr,
    ].join(','));
    for (let i = 0; i < calc; i++) {
      d.addTimeAll(dt);
      out[n++] = mode === 'train' ? trainSoundSample(d, audio) : lineVoltageSample(d);
      t += dt;
    }
  }
}
const ms = performance.now() - t0;
writeFileSync(outPath, Buffer.from(out.buffer));
writeFileSync(outPath + '.trace.csv', trace.join('\n') + '\n');
console.log(`${n} samples (${(n / fs).toFixed(1)} s) in ${(ms / 1000).toFixed(2)} s: ${((ms * 1e6) / n).toFixed(0)} ns per sample`);
