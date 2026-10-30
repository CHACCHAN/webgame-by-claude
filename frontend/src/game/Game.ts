import * as THREE from 'three';
import { Track } from './track/Track';
import { COURSES, type CourseId, type CourseInfo } from './track/courses';
import { buildTerrain, type TerrainData } from './track/terrain';
import { PhysicsWorld, PHYSICS_DT, initRapier } from './vehicle/PhysicsWorld';
import { VehicleSim, emptyInput, type AssistLevel, type VehicleInput } from './vehicle/VehicleSim';
import { CAR_SPECS, type CarId } from './vehicle/carSpecs';
import { RacingLine } from './ai/RacingLine';
import { AIDriver, AI_PROFILES, type AILevel } from './ai/AIDriver';
import { buildScenery, type SceneryResult } from './render/TrackScenery';
import { buildEnvironment, type EnvironmentRig, type TimeOfDay } from './render/Environment';
import { CarVisual } from './render/CarVisual';
import { loadCarTemplates } from './render/carAssets';
import { loadSurfaceTextures } from './render/surfaceTextures';
import { findCorners, type Corner, type CornerKind } from './track/corners';
import { ChaseCamera } from './camera/ChaseCamera';
import { InputManager } from './input/Input';
import { TireSmoke, SkidMarks } from './fx/TireEffects';
import { Rain } from './fx/Rain';
import { AudioEngine } from './audio/AudioEngine';
import { GhostPlayer, GhostRecorder, type GhostData } from './race/Ghost';
import { clamp, damp, lerp, smoothstep } from './util/math';
import type { TrackProjection } from './track/Track';

export type GamePhase = 'loading' | 'attract' | 'garage' | 'countdown' | 'racing' | 'finished' | 'replay';
export type RaceMode = 'time_attack' | 'rival' | 'ghost';

export interface QualitySettings {
  shadows: boolean;
  shadowMapSize: number;
  treeDensity: number;
  headlightShadows: boolean;
  photoTextures: boolean;
}

export interface RaceConfig {
  mode: RaceMode;
  carId: CarId;
  rivalLevel?: AILevel;
  ghost?: { data: GhostData; label: string; carId: CarId; timeMs: number; splits?: number[] } | null;
}

export interface RaceResult {
  trackId: CourseId;
  mode: RaceMode;
  carId: CarId;
  timeMs: number;
  splitsMs: number[];
  rivalLevel?: AILevel;
  rivalWon?: boolean;
  rivalTimeMs?: number;
  rivalCarId?: CarId;
  rivalGhost?: GhostData;
  ghost: GhostData;
  topSpeedKmh: number;
  driftScore: number;
}

/** Mutable HUD snapshot read by the React overlay every animation frame. */
export interface HudState {
  speedKmh: number;
  rpm: number;
  redline: number;
  gear: number;
  raceTime: number;
  countdown: number;
  splits: number[];
  lastSplitDelta: number | null;
  lastSplitIndex: number;
  progress: number;
  rivalProgress: number | null;
  ghostProgress: number | null;
  position: number;
  gapMeters: number;
  wrongWay: boolean;
  driftCombo: number;
  driftScore: number;
  boost: number;
  turbo: boolean;
  sectorFlashT: number;
  /** pace note for the next tight bend; null when none is close */
  corner: { dir: 1 | -1; kind: CornerKind; dist: number; seq: number } | null;
}

type Listener = (e: GameEvent) => void;
export type GameEvent =
  | { type: 'phase'; phase: GamePhase }
  | { type: 'loading'; progress: number; label: string }
  | { type: 'finish'; result: RaceResult }
  | { type: 'sector'; index: number; timeMs: number; deltaMs: number | null };

interface Racer {
  sim: VehicleSim;
  visual: CarVisual;
  ai?: AIDriver;
  input: VehicleInput;
  proj: TrackProjection;
  lastSafe: { s: number; t: number };
  flippedTime: number;
  finished: boolean;
  finishTime: number;
}

const _v = new THREE.Vector3(), _q = new THREE.Quaternion(), _f = new THREE.Vector3();
const _zero = new THREE.Vector3();

export class Game {
  readonly root = new THREE.Group();
  track!: Track;
  terrain!: TerrainData;
  physics!: PhysicsWorld;
  line!: RacingLine;
  scenery!: SceneryResult;
  env!: EnvironmentRig;
  input: InputManager;
  audio: AudioEngine | null = null;
  chase!: ChaseCamera;
  smoke = new TireSmoke();
  skids = new SkidMarks(8);
  rain = new Rain();
  /** tyre grip multiplier from the weather (wet roads) */
  weatherGrip = 1;
  course!: CourseInfo;
  private dryMaterials: { road?: { roughness: number; color: THREE.Color; normal: number; env: number }; terrain?: number } = {};

  phase: GamePhase = 'loading';
  paused = false;
  hud: HudState = {
    speedKmh: 0, rpm: 0, redline: 8000, gear: 1, raceTime: 0, countdown: 0, splits: [], lastSplitDelta: null, lastSplitIndex: -1,
    progress: 0, rivalProgress: null, ghostProgress: null, position: 1, gapMeters: 0, wrongWay: false, driftCombo: 0, driftScore: 0,
    boost: 0, turbo: false, sectorFlashT: 0, corner: null,
  };

  private listeners = new Set<Listener>();
  private accumulator = 0;
  private time = 0;
  /** advances only with physics steps: race timing is independent of the frame rate */
  private simTime = 0;
  private player: Racer | null = null;
  private rival: Racer | null = null;
  private attractCar: Racer | null = null;
  private ghost: { player: GhostPlayer; visual: CarVisual; label: string; splits?: number[] } | null = null;
  private recorder = new GhostRecorder();
  private rivalRecorder = new GhostRecorder();
  private replay: {
    cars: { player: GhostPlayer; visual: CarVisual; wheelRot: number; last: THREE.Vector3 }[];
    t: number;
    duration: number;
    proj: TrackProjection;
  } | null = null;
  private config: RaceConfig | null = null;
  private countdownT = 0;
  private raceStartTime = 0;
  private wrongWayT = 0;
  private topSpeed = 0;
  private driftT = 0;
  private bestSplits: number[] | null = null;
  private cinematic = { shot: 0, t: 0, anchor: new THREE.Vector3(), pos: new THREE.Vector3() };
  private garageCar: CarVisual | null = null;
  private garageAngle = 0;
  /** world yaw of the camera offset that looks from the hillside out over the valley */
  private garageViewYaw = 0;
  private garageLight = new THREE.SpotLight('#fff1e0', 0, 30, 0.55, 0.8, 1.2);
  private lampLights: THREE.PointLight[] = [];
  timeOfDay: TimeOfDay = 'night';
  assist: AssistLevel = 1;
  autoShift = true;
  showGhost = true;
  /** HUD pace notes + warning beeps before tight bends */
  cornerGuide = true;
  corners: Corner[] = [];
  private cornerIdx = 0;
  private warnedCorner = -1;
  /** debug/testing: let an AI drive the player car and speed up simulated time */
  autoDrive = false;
  timeScale = 1;

  constructor(
    readonly renderer: THREE.WebGLRenderer,
    readonly scene: THREE.Scene,
    readonly camera: THREE.PerspectiveCamera,
    readonly quality: QualitySettings,
  ) {
    this.root.name = 'game-root';
    this.input = new InputManager();
  }

  on(l: Listener) {
    this.listeners.add(l);
    return () => this.listeners.delete(l);
  }
  private emit(e: GameEvent) {
    this.listeners.forEach((l) => l(e));
  }

  private async yieldFrame(progress: number, label: string) {
    this.emit({ type: 'loading', progress, label });
    await new Promise((r) => setTimeout(r, 0));
  }

  async load(courseId: CourseId, timeOfDay: TimeOfDay) {
    this.timeOfDay = timeOfDay;
    await this.yieldFrame(0.05, '物理エンジンを初期化中');
    await initRapier();
    await this.yieldFrame(0.08, '車両モデルを読み込み中');
    await Promise.all([loadCarTemplates(['hayate', 'raijin', 'shiden']), loadSurfaceTextures()]);
    this.root.add(this.smoke.points, this.skids.mesh, this.rain.mesh);
    // pooled lights for nearby street lamps
    for (let i = 0; i < 6; i++) {
      const l = new THREE.PointLight('#ffa850', 0, 42, 1.7);
      this.lampLights.push(l);
      this.root.add(l);
    }
    this.scene.add(this.root);
    this.chase = new ChaseCamera(this.camera, (x, z) => this.terrain.heightAt(x, z));
    await this.buildWorld(courseId);
    this.startAttract();
  }

  /** Tear down the current course and build another one. */
  async switchCourse(courseId: CourseId) {
    if (this.course?.id === courseId) return;
    this.clearRace();
    this.setPhase('loading');
    this.disposeWorld();
    await this.buildWorld(courseId);
  }

  private async buildWorld(courseId: CourseId) {
    const course = COURSES[courseId];
    this.course = course;
    await this.yieldFrame(0.12, `${course.name} を測量中`);
    this.track = new Track(course.design);
    this.corners = findCorners(this.track);
    this.line = new RacingLine(this.track);
    await this.yieldFrame(0.25, '山の地形を生成中');
    this.terrain = buildTerrain(this.track, course.landform);
    await this.yieldFrame(0.5, '道路と森を配置中');
    this.physics = new PhysicsWorld(this.track);
    this.scenery = buildScenery(this.track, this.terrain, { treeDensity: this.quality.treeDensity, shadows: this.quality.shadows, photoTextures: this.quality.photoTextures });
    this.root.add(this.scenery.group);
    await this.yieldFrame(0.75, '夜景を灯しています');
    this.env = buildEnvironment(this.terrain);
    this.root.add(this.env.group);
    this.env.key.castShadow = this.quality.shadows;
    this.env.key.shadow.mapSize.set(this.quality.shadowMapSize, this.quality.shadowMapSize);
    this.dryMaterials = {};
    this.applyTimeOfDay(this.timeOfDay);
    this.chase.reset();
    await this.yieldFrame(0.92, 'シェーダーを準備中');
    this.renderer.compile(this.scene, this.camera);
    await this.yieldFrame(1, '準備完了');
  }

  private disposeWorld() {
    if (!this.scenery) return;
    for (const g of [this.scenery.group, this.env.group]) {
      this.root.remove(g);
      const textures = new Set<THREE.Texture>();
      g.traverse((o) => {
        // shadow map render targets and per-instance buffers are not freed with the geometry
        (o as THREE.DirectionalLight).shadow?.dispose();
        if ((o as THREE.InstancedMesh).isInstancedMesh) (o as THREE.InstancedMesh).dispose();
        const m = o as THREE.Mesh;
        if (!m.geometry) return;
        m.geometry.dispose();
        for (const mat of Array.isArray(m.material) ? m.material : [m.material]) {
          if (!mat) continue;
          for (const v of Object.values(mat)) if (v instanceof THREE.Texture) textures.add(v);
          const uniforms = (mat as THREE.ShaderMaterial).uniforms;
          if (uniforms) for (const u of Object.values(uniforms)) if (u.value instanceof THREE.Texture) textures.add(u.value);
          mat.dispose();
        }
      });
      textures.forEach((t) => t.dispose());
    }
    this.env.dispose();
    this.scene.environment = null;
    this.physics.dispose();
  }

  applyTimeOfDay(tod: TimeOfDay) {
    this.timeOfDay = tod;
    this.env.apply(tod, this.scene, this.renderer);
    const envMap = this.env.buildEnvMap(this.renderer);
    this.scene.environment = envMap;
    this.scene.background = null;
    const lamps = this.env.preset.lampsOn;
    for (const m of this.scenery.lightmapMats) {
      m.userData.baseLightMap ??= m.lightMapIntensity;
      m.lightMapIntensity = (m.userData.baseLightMap as number) * lamps;
    }
    for (const m of this.scenery.nightEmissive) {
      m.userData.baseIntensity ??= m.emissiveIntensity;
      m.emissiveIntensity = (m.userData.baseIntensity as number) * lamps;
    }
    this.smoke.setColor(tod === 'dawn' ? '#d9d4cf' : tod === 'rain' ? '#9aa6b4' : '#7d8794');
    // wet roads: glossy, darker asphalt and slicker terrain; less tyre grip
    const wet = this.env.preset.rain;
    const road = this.scenery.roadMaterial;
    this.dryMaterials.road ??= { roughness: road.roughness, color: road.color.clone(), normal: road.normalScale.x, env: road.envMapIntensity };
    const dry = this.dryMaterials.road;
    road.roughness = lerp(dry.roughness, 0.2, wet);
    road.color.copy(dry.color).multiplyScalar(lerp(1, 0.6, wet));
    road.normalScale.setScalar(lerp(dry.normal, 0.08, wet));
    road.envMapIntensity = lerp(dry.env, 1.8, wet);
    const terrain = this.scenery.lightmapMats[1];
    this.dryMaterials.terrain ??= terrain.roughness;
    terrain.roughness = lerp(this.dryMaterials.terrain, 0.62, wet);
    this.rain.setIntensity(wet);
    this.weatherGrip = lerp(1, 0.86, wet);
    this.audio?.setRain(wet);
  }

  initAudio() {
    if (!this.audio) {
      this.audio = new AudioEngine();
      if (this.env) this.audio.setRain(this.env.preset.rain);
    }
    this.audio.resume();
    return this.audio;
  }

  // ------------------------------------------------------------- racers
  private createRacer(carId: CarId, s: number, lateral: number, opts: { ai?: AILevel; headlights: boolean; color?: string }): Racer {
    const spec = CAR_SPECS[carId];
    const p = this.track.pointAt(s, lateral);
    const sim = new VehicleSim(this.physics, spec, p, this.track.headingAt(s));
    sim.assist = this.assist;
    sim.gripScale = this.weatherGrip;
    const visual = new CarVisual(spec, {
      headlights: opts.headlights,
      shadows: this.quality.shadows,
      rideHeight: sim.rideHeight,
      bodyColor: opts.color,
    });
    visual.rig.root.traverse((o) => {
      if ((o as THREE.SpotLight).isSpotLight) (o as THREE.SpotLight).castShadow = this.quality.headlightShadows;
    });
    visual.setHeadlights(this.env.preset.lampsOn > 0.5 ? 1 : 0.6);
    this.root.add(visual.root);
    let ai: AIDriver | undefined;
    if (opts.ai) {
      ai = new AIDriver(this.track, this.line, AI_PROFILES[opts.ai], opts.ai.length * 31);
      ai.calibrate(sim);
    }
    return {
      sim,
      visual,
      ai,
      input: emptyInput(),
      proj: { index: -1, s, lateral, height: 0 },
      lastSafe: { s, t: 0 },
      flippedTime: 0,
      finished: false,
      finishTime: 0,
    };
  }

  private removeRacer(r: Racer | null) {
    if (!r) return;
    this.root.remove(r.visual.root);
    r.visual.dispose();
    r.sim.dispose();
  }

  private clearRace() {
    this.removeRacer(this.player);
    this.removeRacer(this.rival);
    this.removeRacer(this.attractCar);
    this.player = this.rival = this.attractCar = null;
    if (this.ghost) {
      this.root.remove(this.ghost.visual.root);
      this.ghost.visual.dispose();
      this.ghost = null;
    }
    this.garageLight.intensity = 0;
    if (this.garageCar) {
      this.root.remove(this.garageCar.root);
      this.garageCar.dispose();
      this.garageCar = null;
    }
    if (this.replay) {
      for (const c of this.replay.cars) {
        this.root.remove(c.visual.root);
        c.visual.dispose();
      }
      this.replay = null;
    }
    this.smoke.clear();
    this.skids.clear();
    this.audio?.removeAllEngines();
    this.audio?.silenceDriving();
  }

  private setPhase(p: GamePhase) {
    this.phase = p;
    this.emit({ type: 'phase', phase: p });
  }

  // ------------------------------------------------------------- modes
  startAttract() {
    this.clearRace();
    this.attractCar = this.createRacer('shiden', this.track.startS - 10, 0, { ai: 'legend', headlights: true });
    // open on the slow orbit at the summit, then cycle through the other shots
    this.cinematic.shot = 0;
    this.cinematic.t = 0;
    this.setPhase('attract');
  }

  showGarage(carId: CarId, color?: string) {
    this.clearRace();
    const spec = CAR_SPECS[carId];
    const tmp = new VehicleSim(this.physics, spec, new THREE.Vector3(0, -500, 0), 0);
    const ride = tmp.rideHeight;
    tmp.dispose();
    this.garageCar = new CarVisual(spec, { headlights: true, shadows: this.quality.shadows, rideHeight: 0, bodyColor: color });
    this.garageCar.setHeadlights(this.env.preset.lampsOn > 0.5 ? 1 : 0.5);
    // park at the summit, just before the start line, angled for the camera
    const s = this.track.startS - 14;
    const p = this.track.pointAt(s, 0.6);
    this.garageCar.root.position.copy(p);
    this.garageCar.root.rotation.y = this.track.headingAt(s) + 0.35;
    this.root.add(this.garageCar.root);
    void ride;
    // showroom key light above and in front of the car
    this.garageLight.position.copy(p).add(new THREE.Vector3(0, 7, 0));
    this.garageLight.target.position.copy(p);
    this.garageLight.intensity = 70;
    this.garageLight.castShadow = this.quality.shadows;
    if (!this.garageLight.parent) this.root.add(this.garageLight, this.garageLight.target);
    // put the camera on the uphill side so the background is the valley, not the cutting
    const r = this.track.getRight(Math.round(s), new THREE.Vector3());
    const up = this.terrain.heightAt(p.x + r.x * 14, p.z + r.z * 14) > this.terrain.heightAt(p.x - r.x * 14, p.z - r.z * 14) ? 1 : -1;
    this.garageViewYaw = Math.atan2(r.x * up, r.z * up);
    if (this.phase !== 'garage') this.garageAngle = 0.6;
    this.setPhase('garage');
  }

  startRace(cfg: RaceConfig) {
    this.clearRace();
    this.config = cfg;
    const gridS = this.track.startS - 6;
    const lane = cfg.mode === 'rival' ? 2.0 : 0;
    this.player = this.createRacer(cfg.carId, gridS, lane, { headlights: true });
    this.player.sim.autoShift = this.autoShift;
    if (cfg.mode === 'rival' && cfg.rivalLevel) {
      const rival = this.course.rivals[cfg.rivalLevel];
      this.rival = this.createRacer(rival.car, gridS, -2.0, { ai: cfg.rivalLevel, headlights: true, color: rival.color });
      this.rival.sim.powerScale = rival.power ?? 1;
    }
    if (cfg.ghost && (cfg.mode === 'ghost' || this.showGhost)) {
      const spec = CAR_SPECS[cfg.ghost.carId];
      const visual = new CarVisual(spec, { headlights: false, shadows: false, ghost: true, rideHeight: 0.16 + spec.size.height / 2 });
      this.root.add(visual.root);
      this.ghost = { player: new GhostPlayer(cfg.ghost.data), visual, label: cfg.ghost.label, splits: cfg.ghost.splits };
    }
    this.bestSplits = cfg.ghost?.splits ?? null;
    this.recorder.reset();
    this.rivalRecorder.reset();
    this.countdownT = 3.999;
    this.hud.raceTime = 0;
    this.hud.splits = [];
    this.hud.lastSplitDelta = null;
    this.hud.lastSplitIndex = -1;
    this.hud.driftScore = 0;
    this.hud.driftCombo = 0;
    this.hud.corner = null;
    this.cornerIdx = 0;
    this.warnedCorner = -1;
    this.hud.turbo = CAR_SPECS[cfg.carId].engine.turbo;
    this.hud.redline = CAR_SPECS[cfg.carId].engine.redline;
    this.topSpeed = 0;
    this.chase.reset();
    this.accumulator = 0;
    this.paused = false;
    if (this.audio) {
      void this.audio.playMusic(this.course.music, 'bgm_race');
      const spec = CAR_SPECS[cfg.carId];
      this.audio.engine('player', spec.engine.cylinders, spec.engine.turbo);
      if (this.rival) this.audio.engine('rival', this.rival.sim.spec.engine.cylinders, this.rival.sim.spec.engine.turbo);
    }
    this.setPhase('countdown');
  }

  restart() {
    if (this.config) this.startRace(this.config);
  }

  setPaused(p: boolean) {
    this.paused = p;
    if (p) this.audio?.silenceDriving();
    if (this.audio) this.audio.sfx.gain.value = p ? 0 : 1;
  }

  // ------------------------------------------------------------- loop
  update(dtRaw: number) {
    if (this.phase === 'loading') return;
    const dt = Math.min(dtRaw, 0.1) * this.timeScale;
    this.time += dt;

    if (this.input.menuPressed('camera')) this.chase.cycle();

    if (!this.paused) {
      this.step(dt);
    }
    this.updateVisuals(dt);
    this.env.update(this.time, this.camera.position);
    this.rain.update(this.time, this.camera.position, this.player?.sim.velocity ?? _zero);
    this.scenery.update(this.time, this.camera.position);
    this.updateLampLights();
  }

  private racers(): Racer[] {
    return [this.player, this.rival, this.attractCar].filter((r): r is Racer => !!r);
  }

  private step(dt: number) {
    const phase = this.phase;
    // ---- input / AI
    if (this.player) {
      if (phase === 'racing') {
        if (this.player.finished || this.autoDrive) {
          // AI-controlled player (after the finish, or autodrive testing) — see driveAI
        } else {
          this.input.poll(dt, this.player.input);
          if (this.input.menuPressed('reset')) this.respawn(this.player);
        }
      } else if (phase === 'countdown') {
        // allow revving on the line, but hold the car
        const tmp = this.input.poll(dt, emptyInput());
        this.player.input.throttle = tmp.throttle;
        this.player.input.brake = 1;
        this.player.input.steer = 0;
        this.player.input.handbrake = true;
      }
    }

    // ---- fixed-step physics (AI and race timing run per step, independent of frame rate)
    this.accumulator += dt;
    let steps = 0;
    const racers = this.racers();
    const maxSteps = 8 * Math.ceil(this.timeScale);
    while (this.accumulator >= PHYSICS_DT && steps < maxSteps) {
      this.driveAI(phase);
      for (const r of racers) {
        if (!r.ai) r.sim.assist = this.assist;
        r.sim.input = r.input;
        r.sim.preStep(PHYSICS_DT);
      }
      this.physics.step();
      for (const r of racers) r.sim.postStep(PHYSICS_DT);
      this.simTime += PHYSICS_DT;
      if (this.phase === 'racing' || this.phase === 'finished') this.raceStep();
      this.accumulator -= PHYSICS_DT;
      steps++;
    }
    if (steps === maxSteps) this.accumulator = 0;

    // ---- race logic
    for (const r of racers) this.trackRacer(r, dt);
    if (phase === 'countdown') this.updateCountdown(dt);
    if (phase === 'racing' || phase === 'finished') this.updateRace(dt);
    if (phase === 'attract' && this.attractCar && this.attractCar.proj.s > this.track.finishS + 40) {
      this.attractCar.sim.reset(this.track.pointAt(this.track.startS - 10), this.track.headingAt(this.track.startS - 10), 0);
      this.attractCar.proj.index = -1;
    }
  }

  /** AI inputs, evaluated every physics step. */
  private driveAI(phase: GamePhase) {
    const dt = PHYSICS_DT;
    const pl = this.player;
    if (pl && (phase === 'racing' || phase === 'finished')) {
      if (pl.finished) this.autopilot(pl, dt);
      else if (this.autoDrive) this.autoDriver(pl, dt);
    }
    for (const r of [this.rival, this.attractCar]) {
      if (!r || !r.ai) continue;
      if (phase === 'countdown') {
        r.input.throttle = 0.3;
        r.input.brake = 1;
        r.input.handbrake = true;
        continue;
      }
      if (pl && r === this.rival) r.ai.opponent = { s: pl.proj.s, lateral: pl.proj.lateral };
      r.ai.update(r.sim, dt, r.input);
      if (r.finished) {
        r.input.throttle = 0;
        r.input.brake = 0.4;
      }
    }
  }

  private autoDriver(r: Racer, dt: number) {
    if (!r.ai) {
      r.ai = new AIDriver(this.track, this.line, AI_PROFILES.ace, 11);
      r.ai.calibrate(r.sim);
    }
    r.ai.update(r.sim, dt, r.input);
  }

  private autopilot(r: Racer, dt: number) {
    if (!r.ai) {
      r.ai = new AIDriver(this.track, this.line, AI_PROFILES.rookie, 3);
      r.ai.calibrate(r.sim);
    }
    r.ai.update(r.sim, dt, r.input);
    r.input.throttle = 0;
    r.input.brake = r.sim.forwardSpeed > 4 ? 0.35 : 0;
  }

  private trackRacer(r: Racer, dt: number) {
    const p = r.sim.position;
    r.proj = this.track.project(p.x, p.y, p.z, r.proj.index, r.proj);
    const onRoad = Math.abs(r.proj.lateral) < this.track.width[r.proj.index] / 2 + 1 && Math.abs(r.proj.height) < 3;
    if (onRoad && !r.sim.isFlipped && r.sim.speed > 2) r.lastSafe = { s: r.proj.s, t: this.time };
    // automatic recovery
    if (r.sim.isFlipped) r.flippedTime += dt;
    else r.flippedTime = 0;
    const lost = Math.abs(r.proj.height) > 12 || r.sim.position.y < -20;
    if (r.flippedTime > 2 || lost || (r.ai && r.ai.needsRespawn && r !== this.player)) this.respawn(r);
  }

  private respawn(r: Racer) {
    const s = clamp(Math.min(r.lastSafe.s, r.proj.s) - 4, 5, this.track.length - 20);
    const lat = clamp(this.line.offsetAt(s), -2, 2);
    r.sim.reset(this.track.pointAt(s, lat), this.track.headingAt(s), 0);
    r.proj.index = -1;
    r.flippedTime = 0;
    r.lastSafe = { s, t: this.time };
    for (let i = 0; i < 4; i++) this.skids.break(i);
  }

  private updateCountdown(dt: number) {
    const prev = Math.ceil(this.countdownT);
    this.countdownT -= dt;
    const now = Math.ceil(this.countdownT);
    this.hud.countdown = Math.max(0, this.countdownT);
    if (now !== prev && now >= 1 && now <= 3) this.audio?.beep(660, 0.18, 'square', 0.18);
    if (this.countdownT <= 0) {
      this.audio?.beep(1320, 0.5, 'square', 0.22);
      this.raceStartTime = this.simTime;
      this.hud.countdown = 0;
      this.setPhase('racing');
    }
  }

  /** Per physics step: projection, recording, sector splits and finish detection. */
  private raceStep() {
    const pl = this.player;
    if (!pl) return;
    const raceTime = this.simTime - this.raceStartTime;
    const p = pl.sim.position;
    pl.proj = this.track.project(p.x, p.y, p.z, pl.proj.index, pl.proj);
    if (this.rival) {
      const rp = this.rival.sim.position;
      this.rival.proj = this.track.project(rp.x, rp.y, rp.z, this.rival.proj.index, this.rival.proj);
      if (!this.rival.finished && this.rival.proj.s >= this.track.finishS) {
        this.rival.finished = true;
        this.rival.finishTime = raceTime;
      }
    }
    if (pl.finished) return;
    this.recorder.sample(raceTime, pl.sim.position, pl.sim.quaternion, pl.sim.wheels[0].steer);
    if (this.rival && !this.rival.finished) this.rivalRecorder.sample(raceTime, this.rival.sim.position, this.rival.sim.quaternion, this.rival.sim.wheels[0].steer);
    const s = pl.proj.s;
    const next = this.hud.splits.length;
    if (next < this.track.sectorSplits.length && s >= this.track.sectorSplits[next]) {
      const ms = Math.round(raceTime * 1000);
      this.hud.splits.push(ms);
      const ref = this.bestSplits?.[next];
      this.hud.lastSplitDelta = ref ? ms - ref : null;
      this.hud.lastSplitIndex = next;
      this.hud.sectorFlashT = this.time;
      this.emit({ type: 'sector', index: next, timeMs: ms, deltaMs: this.hud.lastSplitDelta });
      if (next < this.track.sectorSplits.length - 1) this.audio?.chime([880, 1320]);
    }
    if (s >= this.track.finishS && this.hud.splits.length >= this.track.sectorSplits.length) {
      pl.finished = true;
      pl.finishTime = raceTime;
      this.finishRace();
    }
  }

  private updateRace(dt: number) {
    const pl = this.player;
    if (!pl) return;
    const raceTime = pl.finished ? pl.finishTime : this.simTime - this.raceStartTime;
    this.hud.raceTime = raceTime;
    const s = pl.proj.s;
    this.hud.progress = clamp((s - this.track.startS) / (this.track.finishS - this.track.startS), 0, 1);
    this.topSpeed = Math.max(this.topSpeed, pl.sim.speed * 3.6);

    if (!pl.finished) {
      // wrong way
      this.track.getFwd(pl.proj.index, _f);
      const wrong = pl.sim.forward.dot(_f) < -0.3 && pl.sim.speed > 4;
      this.wrongWayT = wrong ? this.wrongWayT + dt : 0;
      this.hud.wrongWay = this.wrongWayT > 1.2;
      this.updateCornerGuide(s, pl.sim.speed);
      // drift scoring
      const drifting = Math.abs(pl.sim.slipAngle) > 0.2 && pl.sim.speed > 12 && !pl.sim.airborne;
      if (drifting) {
        this.driftT += dt;
        this.hud.driftCombo += dt * pl.sim.speed * Math.abs(pl.sim.slipAngle) * 4;
      } else if (this.driftT > 0) {
        this.driftT = 0;
        if (this.hud.driftCombo > 30) this.hud.driftScore += Math.round(this.hud.driftCombo);
        this.hud.driftCombo = 0;
      }
    }

    // rival
    if (this.rival) {
      const rs = this.rival.proj.s;
      this.hud.rivalProgress = clamp((rs - this.track.startS) / (this.track.finishS - this.track.startS), 0, 1);
      const ahead = pl.finished
        ? !this.rival.finished || pl.finishTime <= this.rival.finishTime
        : this.rival.finished
          ? false
          : s >= rs;
      this.hud.position = ahead ? 1 : 2;
      this.hud.gapMeters = s - rs;
    } else this.hud.rivalProgress = null;

    if (this.ghost) {
      const gp = this.ghost.player;
      const pose = gp.pose(raceTime, _v, _q);
      const gs = this.track.project(_v.x, _v.y, _v.z).s;
      this.hud.ghostProgress = clamp((gs - this.track.startS) / (this.track.finishS - this.track.startS), 0, 1);
      if (pose.done) this.ghost.visual.root.visible = false;
    } else this.hud.ghostProgress = null;
  }

  /** Shows the next tight bend a couple of seconds before its entry (until its apex) and beeps once. */
  private updateCornerGuide(s: number, speed: number) {
    const cs = this.corners;
    while (this.cornerIdx > 0 && cs[this.cornerIdx - 1].apex >= s) this.cornerIdx--;
    while (this.cornerIdx < cs.length && cs[this.cornerIdx].apex < s) this.cornerIdx++;
    const c = cs[this.cornerIdx];
    this.hud.corner = null;
    if (!c || !this.cornerGuide) return;
    const dist = c.start - s;
    const lookahead = clamp(speed * 2.6, 45, 150);
    // medium bends only deserve a call when arriving faster than they can be taken
    const relevant = c.kind !== 'medium' || speed > Math.sqrt(9.81 * c.minRadius) * 1.05 || this.warnedCorner === this.cornerIdx;
    if (dist > lookahead || !relevant) return;
    this.hud.corner = { dir: c.dir, kind: c.kind, dist: Math.max(0, dist), seq: this.cornerIdx };
    if (this.warnedCorner !== this.cornerIdx) {
      this.warnedCorner = this.cornerIdx;
      this.audio?.cornerWarning(c.kind);
    }
  }

  private finishRace() {
    const pl = this.player!;
    this.hud.corner = null;
    if (this.audio) {
      const a = this.audio;
      a.stopMusic(0.8);
      const lost = !!this.rival?.finished && this.rival.finishTime < pl.finishTime;
      if (lost) void a.playJingle('jingle_lose').then((ok) => ok || a.chime([659, 587, 494, 440], 0.16));
      else void a.playJingle('jingle_finish').then((ok) => ok || a.chime([784, 988, 1175, 1568], 0.11));
    }
    if (this.hud.driftCombo > 30) this.hud.driftScore += Math.round(this.hud.driftCombo);
    this.hud.driftCombo = 0;
    const rivalTime = this.rival?.finished ? this.rival.finishTime : undefined;
    const result: RaceResult = {
      trackId: this.course.id,
      mode: this.config!.mode,
      carId: this.config!.carId,
      timeMs: Math.round(pl.finishTime * 1000),
      splitsMs: this.hud.splits.slice(),
      rivalLevel: this.config!.rivalLevel,
      rivalWon: this.rival ? !(rivalTime === undefined || pl.finishTime <= rivalTime) : undefined,
      rivalTimeMs: rivalTime !== undefined ? Math.round(rivalTime * 1000) : undefined,
      ghost: this.recorder.data(),
      rivalCarId: this.rival?.sim.spec.id,
      rivalGhost: this.rival ? this.rivalRecorder.data() : undefined,
      topSpeedKmh: Math.round(this.topSpeed),
      driftScore: this.hud.driftScore,
    };
    // the last split must equal the total time
    result.splitsMs[result.splitsMs.length - 1] = result.timeMs;
    this.setPhase('finished');
    this.emit({ type: 'finish', result });
  }

  // ------------------------------------------------------------- visuals
  private updateVisuals(dt: number) {
    const alpha = clamp(this.accumulator / PHYSICS_DT, 0, 1);
    for (const r of this.racers()) {
      r.visual.syncFromSim(r.sim, this.paused ? 1 : alpha, dt);
      if (!this.paused) this.emitTyreFx(r, dt);
    }
    if (this.ghost && (this.phase === 'racing' || this.phase === 'finished' || this.phase === 'countdown')) {
      const t = this.phase === 'countdown' ? 0 : this.player?.finished ? this.player.finishTime : this.simTime - this.raceStartTime;
      const pose = this.ghost.player.pose(t, _v, _q);
      // ghost frames store the body origin; the visual expects ground-relative pose
      this.ghost.visual.syncFromPose({ position: _v, quaternion: _q, steer: pose.steer }, dt);
      // fade the ghost when the player is right on top of it
      if (this.player) {
        const d = this.player.sim.position.distanceTo(_v);
        this.ghost.visual.setGhostOpacity(lerp(0.05, 0.24, smoothstep(2, 10, d)));
      }
    }
    if (!this.paused) this.smoke.update(dt);
    this.smoke.setViewportHeight(this.renderer.domElement.height);

    // ---- camera
    if (this.phase === 'attract' && this.attractCar) this.cinematicCamera(dt, this.attractCar.visual.root, this.attractCar.proj.s);
    else if (this.phase === 'replay' && this.replay) this.updateReplay(dt);
    else if (this.phase === 'garage' && this.garageCar) this.garageCamera(dt);
    else if (this.player) {
      const sim = this.player.sim;
      const v = this.player.visual.root;
      this.chase.update(dt, {
        position: v.position,
        quaternion: v.quaternion,
        velocity: sim.velocity,
        speed: sim.speed,
        slipAngle: sim.slipAngle,
        impact: sim.impact,
      });
    }

    // ---- HUD + audio
    if (this.player) {
      const sim = this.player.sim;
      this.hud.speedKmh = Math.abs(sim.forwardSpeed) * 3.6;
      this.hud.rpm = sim.rpm;
      this.hud.gear = sim.gear;
      this.hud.boost = sim.boost;
      if (this.audio && !this.paused) {
        const e = this.audio.engine('player', sim.spec.engine.cylinders, sim.spec.engine.turbo);
        if (e.blowOff(sim.input.throttle, sim.boost)) this.audio.blowOff();
        e.update(sim.rpm, sim.input.throttle, sim.boost, 1, sim.spec.engine.redline);
        let skid = 0;
        for (const w of sim.wheels) if (w.grounded) skid = Math.max(skid, w.skid);
        this.audio.updateTyres(skid, sim.speed);
        this.audio.updateWind(sim.speed);
        if (sim.impact > 0.15) this.audio.impact(Math.min(1, sim.impact * 1.5));
        if (this.rival) {
          const re = this.audio.engine('rival', this.rival.sim.spec.engine.cylinders, this.rival.sim.spec.engine.turbo);
          const d = this.rival.sim.position.distanceTo(this.camera.position);
          re.update(this.rival.sim.rpm, this.rival.input.throttle, this.rival.sim.boost, clamp(1 - d / 140, 0, 1) * 0.8, this.rival.sim.spec.engine.redline);
        }
      }
    } else if (this.audio && this.attractCar && this.phase === 'attract') {
      const sim = this.attractCar.sim;
      const e = this.audio.engine('attract', sim.spec.engine.cylinders, sim.spec.engine.turbo);
      const d = sim.position.distanceTo(this.camera.position);
      e.update(sim.rpm, sim.input.throttle, sim.boost, clamp(1 - d / 160, 0, 1) * 0.5, sim.spec.engine.redline);
    }
  }

  private emitTyreFx(r: Racer, dt: number) {
    const sim = r.sim;
    const isPlayer = r === this.player;
    const wet = this.env.preset.rain;
    sim.wheels.forEach((w, i) => {
      const id = (isPlayer ? 0 : 4) + i;
      if (wet > 0 && w.grounded && !w.front && sim.speed > 9 && Math.random() < wet * (sim.speed / 45) * 14 * dt) {
        this.smoke.emit(w.contactPoint, sim.velocity, 0.45);
      }
      if (!w.grounded || w.skid < 0.25) {
        this.skids.break(id);
        return;
      }
      _f.copy(sim.forward);
      this.skids.add(id, w.contactPoint, w.contactNormal, _f, w.skid);
      const rate = w.skid * 38 * this.smoke.density;
      if (Math.random() < rate * dt) this.smoke.emit(w.contactPoint, sim.velocity, w.skid);
    });
  }

  /** Cinematic replay of a finished race from the recorded ghost data. */
  startReplay(result: RaceResult) {
    this.clearRace();
    const entries: [CarId, GhostData][] = [[result.carId, result.ghost]];
    if (result.rivalGhost && result.rivalCarId) entries.push([result.rivalCarId, result.rivalGhost]);
    const cars = entries.map(([carId, data], i) => {
      const spec = CAR_SPECS[carId];
      const visual = new CarVisual(spec, {
        headlights: true,
        shadows: this.quality.shadows,
        rideHeight: 0.16 + spec.size.height / 2,
        bodyColor: i === 1 ? '#e9e9ea' : undefined,
      });
      visual.setHeadlights(this.env.preset.lampsOn > 0.5 ? 1 : 0.6);
      this.root.add(visual.root);
      return { player: new GhostPlayer(data), visual, wheelRot: 0, last: new THREE.Vector3() };
    });
    this.replay = { cars, t: 0, duration: cars[0].player.duration, proj: { index: -1, s: 0, lateral: 0, height: 0 } };
    this.cinematic.shot = 0;
    this.cinematic.t = 6.5;
    this.setPhase('replay');
  }

  private updateReplay(dt: number) {
    const rp = this.replay!;
    rp.t += dt;
    if (rp.t > rp.duration + 1.5) {
      rp.t = 0;
      rp.proj.index = -1;
    }
    rp.cars.forEach((c, i) => {
      const pose = c.player.pose(rp.t, _v, _q);
      const moved = c.last.lengthSq() > 0 ? _v.distanceTo(c.last) : 0;
      c.wheelRot += moved / 0.3;
      c.last.copy(_v);
      c.visual.syncFromPose({ position: _v, quaternion: _q, steer: pose.steer, wheelRotations: [c.wheelRot, c.wheelRot, c.wheelRot, c.wheelRot] }, dt);
      if (i === 0) rp.proj = this.track.project(_v.x, _v.y, _v.z, rp.proj.index, rp.proj);
    });
    this.cinematicCamera(dt, rp.cars[0].visual.root, rp.proj.s);
  }

  get replayTime() {
    return this.replay?.t ?? 0;
  }

  private cinematicCamera(dt: number, root: THREE.Object3D, trackS: number) {
    const c = this.cinematic;
    c.t += dt;
    const car = root.position;
    const fwd = _f.set(0, 0, 1).applyQuaternion(root.quaternion);
    const shots = 4;
    if (c.t > 7) {
      c.t = 0;
      c.shot = (c.shot + 1) % shots;
      // trackside anchor for the static shot: ahead of the car
      const s = trackS + 70;
      this.track.pointAt(s, (this.track.widthAt(s) / 2 + 4) * (c.shot % 2 ? 1 : -1), c.anchor);
      c.anchor.y += 2.2;
    }
    const cam = this.camera;
    let fov = 45;
    switch (c.shot) {
      case 0: {
        // slow orbit
        const a = this.time * 0.25;
        c.pos.set(car.x + Math.sin(a) * 9, car.y + 2.6, car.z + Math.cos(a) * 9);
        cam.position.lerp(c.pos, 1 - Math.exp(-dt * 6));
        cam.lookAt(car.x, car.y + 0.6, car.z);
        fov = 42;
        break;
      }
      case 1: {
        // trackside pan
        if (c.anchor.lengthSq() === 0) this.track.pointAt(trackS + 70, 8, c.anchor);
        cam.position.copy(c.anchor);
        cam.lookAt(car.x, car.y + 0.6, car.z);
        fov = clamp(40 - c.anchor.distanceTo(car) * 0.1, 18, 40);
        break;
      }
      case 2: {
        // low front tracking shot
        c.pos.copy(car).addScaledVector(fwd, 7).setY(car.y + 0.7);
        cam.position.lerp(c.pos, 1 - Math.exp(-dt * 8));
        cam.lookAt(car.x, car.y + 0.5, car.z);
        fov = 50;
        break;
      }
      default: {
        // high wide shot showing the valley and the city
        c.pos.copy(car).addScaledVector(fwd, -24).setY(car.y + 16);
        cam.position.lerp(c.pos, 1 - Math.exp(-dt * 2));
        _v.copy(car).addScaledVector(fwd, 40);
        _v.z += 30;
        cam.lookAt(_v);
        fov = 58;
      }
    }
    const ground = this.terrain.heightAt(cam.position.x, cam.position.z) + 1;
    if (cam.position.y < ground) cam.position.y = ground;
    if (Math.abs(cam.fov - fov) > 0.01) {
      cam.fov = damp(cam.fov, fov, 2, dt);
      cam.updateProjectionMatrix();
    }
  }

  private garageCamera(dt: number) {
    const car = this.garageCar!.root.position;
    // swing slowly from the uphill side; the car sits left of centre beside the UI card
    this.garageAngle += dt * 0.2;
    const a = this.garageViewYaw + Math.sin(this.garageAngle) * 0.75;
    const cam = this.camera;
    _v.set(car.x + Math.sin(a) * 8.6, car.y + 1.7, car.z + Math.cos(a) * 8.6);
    cam.position.lerp(_v, 1 - Math.exp(-dt * 3));
    // aim to the right of the car so it is framed in the left part of the screen
    _f.set(-Math.cos(a), 0, Math.sin(a)).multiplyScalar(-2.4);
    cam.lookAt(car.x + _f.x, car.y + 0.6, car.z + _f.z);
    if (Math.abs(cam.fov - 38) > 0.01) {
      cam.fov = damp(cam.fov, 38, 3, dt);
      cam.updateProjectionMatrix();
    }
  }

  setGarageColor(color: string) {
    this.garageCar?.rig.materials.paint.color.set(color);
  }

  /** Move the pooled point lights to the lamps nearest the camera. */
  private updateLampLights() {
    const lampsOn = this.env.preset.lampsOn;
    const cam = this.camera.position;
    const lamps = this.scenery.lamps;
    const n = this.lampLights.length;
    const best: { d: number; i: number }[] = [];
    for (let i = 0; i < lamps.length; i++) {
      const d = lamps[i].position.distanceToSquared(cam);
      if (best.length < n) best.push({ d, i });
      else {
        let worst = 0;
        for (let k = 1; k < n; k++) if (best[k].d > best[worst].d) worst = k;
        if (d < best[worst].d) best[worst] = { d, i };
      }
    }
    this.lampLights.forEach((l, k) => {
      const b = best[k];
      if (!b || lampsOn < 0.2) {
        l.intensity = 0;
        return;
      }
      const lamp = lamps[b.i];
      l.position.copy(lamp.position);
      l.color.copy(lamp.color);
      // fade by distance so swapping lights never pops
      l.intensity = 170 * lampsOn * smoothstep(200, 90, Math.sqrt(b.d));
    });
  }

  get currentConfig() {
    return this.config;
  }

  get playerSim() {
    return this.player?.sim ?? null;
  }

  dispose() {
    this.clearRace();
    this.input.dispose();
    this.physics?.dispose();
    this.scene.remove(this.root);
  }
}
