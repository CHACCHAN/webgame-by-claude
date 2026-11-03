/**
 * A train's sound exactly as the game makes it (AudioEngine + TrainSound in Chrome: the VVVF AudioWorklet, the
 * convolver, the running-noise recording, the master compressor), rendered offline along the run of
 * tools/vvvf-train-wav.ts, updated 60 times a second like the game. Needs `vite preview` on :4173 serving a build
 * (`API_PROXY=http://127.0.0.1:9 npx vite preview --port 4173 --strictPort`) and playwright-core:
 *   PW_MODULE=<…>/node_modules/playwright-core npx tsx tools/vvvf-game-wav.ts <trainId> <out.wav> [--top km/h] [--coast s]
 * Prints the render time (the worklet's cost: real time / render time).
 */
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import type { TrainId } from '../src/game/vehicle/trains';
import { TRAIN_INFO } from '../src/game/vehicle/trains';
import { runProfile, writeWav16 } from './vvvf-train-wav';

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  const args = process.argv.slice(2);
  const opt = (name: string, d: number) => {
    const i = args.indexOf(name);
    return i >= 0 ? +args[i + 1] : d;
  };
  const [id, outPath] = args as [TrainId, string];
  const info = TRAIN_INFO[id];
  const profile = runProfile(id, opt('--top', Math.min(info.vmax, 110)), opt('--coast', 4));
  const plan: [number, number, number, number][] = [];
  let next = 0;
  for (const p of profile) {
    if (p.t < next) continue;
    plan.push([p.t, p.kmh, p.notch === 1 ? 1 : 0, p.notch === -1 ? 0.6 : 0]);
    next += 1 / 60;
  }
  const require = createRequire(import.meta.url);
  const { chromium } = require(process.env.PW_MODULE ?? 'playwright-core');
  const browser = await chromium.launch({
    executablePath: process.env.CHROME ?? '/usr/bin/google-chrome',
    // the host GPU (as tools/perf-gpu.cjs): with software WebGL the title scene starves the main thread, which
    // has to answer every suspend of the offline render
    args: ['--autoplay-policy=no-user-gesture-required', '--ignore-gpu-blocklist', '--use-angle=vulkan', '--enable-features=Vulkan'],
  });
  const page = await browser.newPage();
  page.on('console', (m: { type(): string; text(): string }) => m.type() === 'error' && console.log('page:', m.text()));
  await page.goto(`${process.env.URL ?? 'http://127.0.0.1:4173/'}?export=1`);
  await page.waitForFunction(() => '__renderTrainSound' in window, null, { timeout: 120000 });
  const { b64, ms } = await page.evaluate(
    ([id, plan]: [string, [number, number, number, number][]]) =>
      (window as unknown as { __renderTrainSound: (id: string, plan: unknown) => Promise<{ b64: string; ms: number }> }).__renderTrainSound(id, plan),
    [id, plan] as [string, [number, number, number, number][]],
  );
  await browser.close();
  const bytes = Buffer.from(b64, 'base64');
  const x = new Float32Array(bytes.buffer, bytes.byteOffset, bytes.length / 4);
  let peak = 0;
  for (const v of x) peak = Math.max(peak, Math.abs(v));
  const seconds = x.length / 48000;
  console.log(`${seconds.toFixed(1)} s rendered in ${(ms / 1000).toFixed(2)} s (${((ms / 1000 / seconds) * 100).toFixed(1)} % of real time), peak ${peak.toFixed(3)}`);
  writeWav16(outPath, x, 48000);
}
