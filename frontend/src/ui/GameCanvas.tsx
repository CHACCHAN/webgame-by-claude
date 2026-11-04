import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { Bloom, ChromaticAberration, EffectComposer, Noise, SMAA, ToneMapping, Vignette } from '@react-three/postprocessing';
import { BlendFunction, ToneMappingMode } from 'postprocessing';
import { useEffect, useMemo } from 'react';
import * as THREE from 'three';
import { Game } from '../game/Game';
import type { CarId } from '../game/vehicle/carSpecs';
import { currentCourseId, qualityProfile, useSettings } from '../store/settings';
import { useApp } from '../store/app';

/** The single game instance (the 3D world is expensive to build). */
export const gameHolder: { game: Game | null } = { game: null };

declare global {
  interface Window {
    __game?: Game;
  }
}

function GameBridge() {
  const { gl, scene, camera } = useThree();
  useEffect(() => {
    if (gameHolder.game) return;
    const s = useSettings.getState();
    const profile = qualityProfile(s.quality, s.resolutionScale);
    const game = new Game(gl, scene, camera as THREE.PerspectiveCamera, profile);
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
      // dev hook for tools/export-cars: returns a GLB as base64
      (window as unknown as Record<string, unknown>).__exportCar = async (id: CarId) => {
        const { exportCarGLB } = await import('../game/render/carAssets');
        const buf = new Uint8Array(await exportCarGLB(id));
        let bin = '';
        for (let i = 0; i < buf.length; i += 0x8000) bin += String.fromCharCode(...buf.subarray(i, i + 0x8000));
        return btoa(bin);
      };
      // dev hooks for tools/import-cars: third-party car models → game GLB (and orientation previews)
      const w = window as unknown as Record<string, unknown>;
      w.__importCar = async (url: string, id: CarId, cfg: import('../game/render/carImport').CarImportConfig) => {
        const [{ importCarModel }, { CAR_SPECS }] = await Promise.all([import('../game/render/carImport'), import('../game/vehicle/carSpecs')]);
        const { glb, stats } = await importCarModel(url, CAR_SPECS[id], cfg);
        const buf = new Uint8Array(glb);
        let bin = '';
        for (let i = 0; i < buf.length; i += 0x8000) bin += String.fromCharCode(...buf.subarray(i, i + 0x8000));
        return { b64: btoa(bin), stats };
      };
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
      w.__previewCar = async (url: string, rotation?: [number, number, number]) => {
        const { previewCarModel } = await import('../game/render/carImport');
        return previewCarModel(url, rotation);
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
  }, [gl, scene, camera]);
  useFrame((_, dt) => gameHolder.game?.update(dt), -1);
  return null;
}

function Effects() {
  const quality = useSettings((s) => s.quality);
  const scale = useSettings((s) => s.resolutionScale);
  const p = useMemo(() => qualityProfile(quality, scale), [quality, scale]);
  if (!p.bloom) return null;
  return (
    <EffectComposer multisampling={0} enableNormalPass={false}>
      <Bloom mipmapBlur luminanceThreshold={0.85} luminanceSmoothing={0.25} intensity={1.05} radius={0.72} />
      <ToneMapping mode={ToneMappingMode.ACES_FILMIC} />
      {p.smaa ? <SMAA /> : <></>}
      {p.extraFx ? <ChromaticAberration offset={new THREE.Vector2(0.0005, 0.0005)} radialModulation modulationOffset={0.35} /> : <></>}
      <Vignette offset={0.28} darkness={0.62} />
      {p.extraFx ? <Noise opacity={0.028} blendFunction={BlendFunction.OVERLAY} /> : <></>}
    </EffectComposer>
  );
}

export function GameCanvas() {
  const quality = useSettings((s) => s.quality);
  const scale = useSettings((s) => s.resolutionScale);
  const p = useMemo(() => qualityProfile(quality, scale), [quality, scale]);
  return (
    <Canvas
      className="game-canvas"
      dpr={p.pixelRatio}
      shadows={p.shadows ? 'percentage' : false}
      gl={{ antialias: false, powerPreference: 'high-performance', stencil: false, preserveDrawingBuffer: false }}
      camera={{ fov: 60, near: 0.25, far: 16000, position: [0, 600, 0] }}
      fallback={
        <div className="no-webgl">
          このブラウザでは WebGL2 が利用できないため、ゲームを表示できません。
          <br />
          最新の Chrome / Edge / Firefox で、ハードウェアアクセラレーションを有効にしてお試しください。
        </div>
      }
      onCreated={({ gl }) => {
        gl.toneMapping = THREE.ACESFilmicToneMapping;
        gl.setClearColor('#05070c');
      }}
    >
      <GameBridge />
      <Effects />
    </Canvas>
  );
}
