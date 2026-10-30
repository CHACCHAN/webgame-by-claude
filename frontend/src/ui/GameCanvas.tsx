import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { Bloom, ChromaticAberration, EffectComposer, Noise, SMAA, ToneMapping, Vignette } from '@react-three/postprocessing';
import { BlendFunction, ToneMappingMode } from 'postprocessing';
import { useEffect, useMemo } from 'react';
import * as THREE from 'three';
import { Game } from '../game/Game';
import { qualityProfile, useSettings } from '../store/settings';
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
    game.assist = s.assist;
    game.autoShift = s.autoShift;
    game.showGhost = s.showGhost;
    gameHolder.game = game;
    window.__game = game;
    game.on((e) => {
      const app = useApp.getState();
      if (e.type === 'loading') app.set({ loading: { progress: e.progress, label: e.label } });
      if (e.type === 'phase') {
        app.set({ phase: e.phase });
        if (e.phase === 'attract' && app.screen === 'boot') app.set({ screen: 'title', loading: null });
      }
      if (e.type === 'finish') app.set({ result: e.result, screen: 'results' });
    });
    void game.load(s.timeOfDay).catch((err) => {
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
