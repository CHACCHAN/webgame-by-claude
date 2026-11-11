import { useEffect, useRef, useState } from 'react';
import { Game } from '../game/Game';
import { RenderHost, type RenderOptions, type RenderTrouble } from '../game/render/RenderHost';
import { noteDeviceLost, planBackend, rememberFailure, type BackendPlan } from '../game/render/backendChoice';
import type { CarId } from '../game/vehicle/carSpecs';
import { UPSCALE_SCALE, currentCourseId, qualityProfile, useSettings, type Settings } from '../store/settings';
import { useApp } from '../store/app';
import { isTouchDevice } from './touch';
import { serverBrain, warmRivalBrain } from '../api/rivalBrain';

/** The single game instance (the 3D world is expensive to build). */
export const gameHolder: { game: Game | null } = { game: null };

declare global {
  interface Window {
    __game?: Game;
  }
}

/** the renderer of the single game (kept with it: React may mount the canvas component twice in development) */
const hostHolder: { host: RenderHost | null; starting: Promise<RenderHost> | null } = { host: null, starting: null };

function startGame(host: RenderHost) {
  {
    if (gameHolder.game) return;
    const s = useSettings.getState();
    const profile = qualityProfile(s.quality, s.resolutionScale);
    const game = new Game(host.renderer, host.scene, host.camera, profile);
    // courses stay built once shown, by how much memory the machine has (`navigator.deviceMemory`, GB of RAM, is all
    // a page is told: video memory is not; no value = a desktop browser that does not say): none on phones and at
    // low quality, the previous one from 4 GB, all of them from 8 GB. Counted in MB on the GPU by our own estimate
    const ram = (navigator as { deviceMemory?: number }).deviceMemory ?? 8;
    game.keepBudget = isTouchDevice() || s.quality === 'low' || ram < 4 ? 0 : ram < 8 ? 500 : 2000;
    game.compileScene = (hold) => host.precompile(hold);
    game.compileObject = (object) => host.precompile(false, object);
    const params = new URLSearchParams(location.search);
    game.assist = s.assist;
    game.autoShift = s.autoShift;
    game.showGhost = s.showGhost;
    game.cornerGuide = s.cornerGuide ?? true;
    game.rivalBrains = (s.rivalAi ?? true) ? [serverBrain] : [];
    warmRivalBrain();
    if (params.get('autodrive') === '1') game.autoDrive = true;
    if (params.get('timescale')) game.timeScale = Math.max(0.1, Math.min(20, Number(params.get('timescale')) || 1));
    gameHolder.game = game;
    window.__game = game;
    if (params.get('export') === '1') {
      const w = window as unknown as Record<string, unknown>;
      // dev hook for tools/vvvf-game-wav.cjs: a vehicle's sound as the game drives it, rendered offline. `plan`: one
      // [seconds, km/h, throttle, brake] per update (the game calls update once per frame); returns float32 as base64
      w.__renderTrainSound = async (id: CarId, plan: [number, number, number, number][], rate = 48000) => {
        const [{ AudioEngine }, { CAR_SPECS }] = await Promise.all([import('../game/audio/AudioEngine'), import('../game/vehicle/carSpecs')]);
        const spec = CAR_SPECS[id];
        const seconds = plan[plan.length - 1][0] + 0.5;
        const ctx = new OfflineAudioContext(1, Math.ceil(seconds * rate), rate);
        const audio = new AudioEngine(ctx);
        const e = audio.engine('player', spec);
        await audio.loaded();
        const redline = spec.engine.redline, vmax = spec.train?.vmax ?? 300;
        for (const [t, kmh, throttle, brake] of plan) {
          void ctx.suspend(Math.round((t * rate) / 128) * (128 / rate)).then(() => {
            e.update((kmh / vmax) * redline, throttle, 0, 1, redline, brake);
            void ctx.resume();
          }, () => undefined);
        }
        const t0 = performance.now();
        const buf = await ctx.startRendering();
        const ms = performance.now() - t0;
        const bytes = new Uint8Array(buf.getChannelData(0).buffer);
        let bin = '';
        for (let i = 0; i < bytes.length; i += 0x8000) bin += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
        return { b64: btoa(bin), ms };
      };
    }
    game.on((e) => {
      const app = useApp.getState();
      if (e.type === 'loading') app.set({ loading: { progress: e.progress, label: e.label } });
      if (e.type === 'phase') {
        app.set({ phase: e.phase });
        if (e.phase === 'attract' && app.screen === 'boot') app.set({ screen: 'title', loading: null });
      }
      if (e.type === 'busy') app.set({ busy: e.label });
      if (e.type === 'rivalLine') app.set({ rivalLine: { moment: e.moment, text: e.text } });
      if (e.type === 'finish') app.set({ result: e.result, screen: e.result.mode === 'online' ? 'onlineResults' : 'results', paused: false });
    });
    void game.load(currentCourseId(), s.timeOfDay).catch((err) => {
      console.error(err);
      app().set({ loading: { progress: 0, label: `読み込みに失敗しました: ${String(err)}` } });
    });
    function app() {
      return useApp.getState();
    }
  }
  host.start((dt) => gameHolder.game?.update(dt));
}

const renderOptions = (s: Pick<Settings, 'quality' | 'resolutionScale' | 'upscale' | 'upscaleMode' | 'sharpness'>): RenderOptions => {
  const p = qualityProfile(s.quality, s.resolutionScale);
  return {
    pixelRatio: p.pixelRatio, shadows: p.shadows, bloom: p.bloom, smaa: p.smaa, extraFx: p.extraFx, ao: p.ao, volumetric: p.volumetric,
    upscale: s.upscale ?? false, renderScale: UPSCALE_SCALE[s.upscaleMode] ?? 1, sharpness: s.sharpness ?? 0,
  };
};

export function GameCanvas() {
  const quality = useSettings((s) => s.quality);
  const resolutionScale = useSettings((s) => s.resolutionScale);
  const upscale = useSettings((s) => s.upscale);
  const upscaleMode = useSettings((s) => s.upscaleMode);
  const sharpness = useSettings((s) => s.sharpness);
  const canvas = useRef<HTMLCanvasElement>(null);
  const busy = useApp((s) => s.busy);
  /** 0: the planned backend; 1: WebGL 2 on a new canvas, after WebGPU came up and the renderer could not be built */
  const [attempt, setAttempt] = useState(0);
  const [failed, setFailed] = useState<null | 'none' | 'lost'>(null);
  useEffect(() => {
    if (!canvas.current || hostHolder.host || hostHolder.starting) return;
    const s = useSettings.getState();
    const plan: BackendPlan = attempt > 0 ? { forceWebGL: true, reason: 'failed' } : planBackend(s.backend ?? 'auto', location.search);
    const trouble = (kind: RenderTrouble, message: string) => {
      if (kind === 'memory') {
        console.warn(`renderer: out of video memory (${message}): the courses kept built are freed`);
        gameHolder.game?.releaseKept();
        return;
      }
      console.error(`renderer: ${kind === 'lost' ? 'the device is lost' : 'errors in a burst'} (${message})`);
      if (kind === 'lost') {
        // nothing is drawn any more: once more from a reload (WebGL 2 from the second loss on), but never in a loop
        if (noteDeviceLost()) location.reload();
        else setFailed('lost');
      } else if ((useSettings.getState().backend ?? 'auto') === 'auto') {
        // the GPU refuses what WebGPU draws: WebGL 2 from now on (a WebGPU chosen by hand stays)
        rememberFailure(message);
        location.reload();
      }
    };
    const starting = RenderHost.create(canvas.current, renderOptions(s), plan.forceWebGL, trouble);
    hostHolder.starting = starting;
    starting.then(
      (host) => {
        hostHolder.host = host;
        // (WebGL 2 without having been asked for: three.js found no WebGPU device and took its fallback)
        useApp.getState().set({ renderer: { backend: host.backend, reason: host.backend === 'webgl2' ? (plan.reason ?? 'unsupported') : null } });
        if (attempt > 0) rememberFailure('the renderer could not be built on WebGPU');
        startGame(host);
      },
      (err) => {
        console.error(err);
        hostHolder.starting = null;
        if (!plan.forceWebGL) setAttempt(1);
        else setFailed('none');
      },
    );
  }, [attempt]);
  useEffect(() => {
    hostHolder.host?.configure(renderOptions({ quality, resolutionScale, upscale, upscaleMode, sharpness }));
  }, [quality, resolutionScale, upscale, upscaleMode, sharpness]);
  return (
    <div className="game-canvas">
      {/* (a new element per attempt: a canvas that has given a WebGPU context gives no WebGL 2 one) */}
      <canvas key={attempt} ref={canvas} />
      {busy && (
        <div className="busy-mark">
          <i />
          {busy}
        </div>
      )}
      {failed === 'none' && (
        <div className="no-webgl">
          このブラウザでは WebGPU / WebGL2 が利用できないため、ゲームを表示できません。
          <br />
          最新の Chrome / Edge / Firefox で、ハードウェアアクセラレーションを有効にしてお試しください。
        </div>
      )}
      {failed === 'lost' && (
        <div className="no-webgl">
          グラフィックスデバイスとの接続が繰り返し失われたため、描画を停止しました。
          <br />
          ほかの重いアプリやタブを閉じてから再読み込みしてください。
          <br />
          <button className="mini" onClick={() => location.reload()}>再読み込み</button>
        </div>
      )}
    </div>
  );
}
