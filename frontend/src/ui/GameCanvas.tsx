import { useEffect, useRef, useState } from 'react';
import { Game } from '../game/Game';
import { RenderHost, type RenderOptions } from '../game/render/RenderHost';
import type { CarId } from '../game/vehicle/carSpecs';
import { UPSCALE_SCALE, currentCourseId, qualityProfile, useSettings, type Settings } from '../store/settings';
import { useApp } from '../store/app';

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
    game.compileScene = (hold) => host.precompile(hold);
    game.compileObject = (object) => host.precompile(false, object);
    const params = new URLSearchParams(location.search);
    game.assist = s.assist;
    game.autoShift = s.autoShift;
    game.showGhost = s.showGhost;
    game.cornerGuide = s.cornerGuide ?? true;
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
    pixelRatio: p.pixelRatio, shadows: p.shadows, bloom: p.bloom, smaa: p.smaa, extraFx: p.extraFx,
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
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    if (!canvas.current || hostHolder.host || hostHolder.starting) return;
    const s = useSettings.getState();
    // ?webgl=1: the WebGL 2 backend even where WebGPU works (comparisons, troubleshooting)
    const forceWebGL = new URLSearchParams(location.search).get('webgl') === '1';
    hostHolder.starting = RenderHost.create(canvas.current, renderOptions(s), forceWebGL);
    hostHolder.starting.then(
      (host) => {
        hostHolder.host = host;
        startGame(host);
      },
      (err) => {
        console.error(err);
        setFailed(true);
      },
    );
  }, []);
  useEffect(() => {
    hostHolder.host?.configure(renderOptions({ quality, resolutionScale, upscale, upscaleMode, sharpness }));
  }, [quality, resolutionScale, upscale, upscaleMode, sharpness]);
  return (
    <div className="game-canvas">
      <canvas ref={canvas} />
      {failed && (
        <div className="no-webgl">
          このブラウザでは WebGPU / WebGL2 が利用できないため、ゲームを表示できません。
          <br />
          最新の Chrome / Edge / Firefox で、ハードウェアアクセラレーションを有効にしてお試しください。
        </div>
      )}
    </div>
  );
}
