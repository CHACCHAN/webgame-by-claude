import * as THREE from 'three';
import { Track } from './track/Track';
import { COURSES, type CourseId, type CourseInfo } from './track/courses';
import { buildTerrain, type TerrainData } from './track/terrain';
import { PhysicsWorld, PHYSICS_DT, initRapier } from './vehicle/PhysicsWorld';
import { VehicleSim, emptyInput, type AssistLevel, type VehicleInput } from './vehicle/VehicleSim';
import { CAR_ORDER, CAR_SPECS, type CarId } from './vehicle/carSpecs';
import { RacingLine } from './ai/RacingLine';
import { AIDriver, AI_PROFILES, type AILevel } from './ai/AIDriver';
import { buildScenery, type SceneryResult } from './render/TrackScenery';
import { buildEnvironment, PRESETS, type EnvironmentRig, type TimeOfDay } from './render/Environment';
import { CarVisual } from './render/CarVisual';
import { loadCarTemplates } from './render/carAssets';
import { loadSurfaceTextures } from './render/surfaceTextures';
import { loadProps } from './render/props';
import { findCorners, type Corner, type CornerKind } from './track/corners';
import { RemoteRacers, SLOT_COLORS, type NetState, type Peer } from './net/RemoteRacers';

/** lateral grid positions of the (up to three) online racers, by slot */
const ONLINE_LANES = [-2.7, 2.7, 0];
import { CAR_CAMERA, ChaseCamera, TRAIN_CAMERA } from './camera/ChaseCamera';
import { InputManager } from './input/Input';
import { TireSmoke, SkidMarks } from './fx/TireEffects';
import { ExhaustFX, newExhaustState, type ExhaustState } from './fx/Exhaust';
import { Rain } from './fx/Rain';
import { AudioEngine } from './audio/AudioEngine';
import { GhostPlayer, GhostRecorder, type GhostData } from './race/Ghost';
import { clamp, damp, lerp, smoothstep } from './util/math';
import type { TrackProjection } from './track/Track';
import { loadTrainModels, trainNose } from './render/TrainModel';
import { TRAIN_ORDER } from './vehicle/trains';

export type GamePhase = 'loading' | 'attract' | 'garage' | 'countdown' | 'racing' | 'finished' | 'replay';
export type RaceMode = 'time_attack' | 'rival' | 'ghost' | 'online';

export interface QualitySettings {
  /** post-processing on: the scene is drawn into an offscreen buffer, not straight to the screen */
  bloom: boolean;
  shadows: boolean;
  shadowMapSize: number;
  treeDensity: number;
  headlightShadows: boolean;
  photoTextures: boolean;
  treeLod: number;
}

export interface RaceConfig {
  mode: RaceMode;
  carId: CarId;
  rivalLevel?: AILevel;
  /** body colour (a train: its livery) chosen in the car select */
  color?: string;
  ghost?: { data: GhostData; label: string; carId: CarId; timeMs: number; splits?: number[] } | null;
  /** online battle: shared green light (performance.now() ms), this client's grid slot, the others */
  online?: { startAt: number; slot: number; peers: Peer[] };
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
  /** online battle standings, leader first */
  online: { id: number; name: string; slot: number; me: boolean; s: number; finMs: number | null; lost: boolean }[] | null;
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
  exhaust: ExhaustState;
}

const _v = new THREE.Vector3(), _q = new THREE.Quaternion(), _f = new THREE.Vector3();
const _tip = new THREE.Vector3(), _back = new THREE.Vector3();
/** real-time lamp lights hang this far (m) below the lamp fixture */
const LAMP_LIGHT_DROP = 0.9;
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
  exhaust = new ExhaustFX();
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
    boost: 0, turbo: false, sectorFlashT: 0, corner: null, online: null,
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
  /** the chase camera was last set up for a train (cab view by default) */
  private cameraForTrain = false;
  /** camera dragged around the car (car list, car select); null = the slow automatic swing */
  private garageOrbit: { yaw: number; pitch: number; dist: number } | null = null;
  /** garage camera distance factor (a train is far longer than a car) and the point it frames */
  private garageScale = 1;
  private garageFocus = new THREE.Vector3();
  private garageLight = new THREE.SpotLight('#fff1e0', 0, 30, 0.55, 0.8, 1.2);
  private lampLights: THREE.PointLight[] = [];
  /** lamp index each pooled light is attached to (-1 = free) */
  private lampSlots: number[] = [];
  timeOfDay: TimeOfDay = 'night';
  assist: AssistLevel = 1;
  autoShift = true;
  showGhost = true;
  /** car-to-car contact of the player, gathered over the physics steps of a frame */
  private contact = { touching: false, wasTouching: false, impulse: 0, cooldown: 0 };
  private contactShake = 0;
  /** HUD pace notes + warning beeps before tight bends */
  cornerGuide = true;
  corners: Corner[] = [];
  /** other players' cars in an online battle */
  remotes!: RemoteRacers;
  /** id of the local player in an online battle */
  onlineSelfId = 0;
  private rideHeights = new Map<CarId, number>();
  /** stand-in for the post-processing buffer when compiling shaders (see precompile) */
  private compileTarget: THREE.WebGLRenderTarget | null = null;
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
    await Promise.all([loadCarTemplates(CAR_ORDER), loadTrainModels(TRAIN_ORDER), loadSurfaceTextures(), loadProps()]);
    this.root.add(this.smoke.points, this.skids.mesh, this.rain.mesh, this.exhaust.group);
    this.exhaust.density = this.quality.treeDensity < 0.6 ? 0.6 : 1;
    this.remotes = new RemoteRacers(this.root, (id) => this.rideHeightOf(id), false);
    // pooled lights for nearby street lamps
    for (let i = 0; i < 6; i++) {
      const l = new THREE.PointLight('#ffa850', 0, 42, 1.7);
      this.lampLights.push(l);
      this.lampSlots.push(-1);
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
    this.scenery = buildScenery(this.track, this.terrain, { treeDensity: this.quality.treeDensity, shadows: this.quality.shadows, photoTextures: this.quality.photoTextures, treeLod: this.quality.treeLod });
    this.root.add(this.scenery.group);
    this.lampSlots.fill(-1);
    await this.yieldFrame(0.75, '夜景を灯しています');
    this.env = buildEnvironment(this.terrain);
    this.root.add(this.env.group);
    this.env.key.castShadow = this.quality.shadows;
    this.env.key.shadow.mapSize.set(this.quality.shadowMapSize, this.quality.shadowMapSize);
    this.dryMaterials = {};
    this.applyTimeOfDay(this.timeOfDay);
    this.chase.reset();
    await this.yieldFrame(0.92, 'シェーダーを準備中');
    await this.precompile();
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
    // unknown values (e.g. corrupted saved settings) would poison the sky and fog with NaN: black screen
    if (!PRESETS[tod]) tod = 'night';
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
    this.exhaust.setColor(tod === 'dawn' ? '#c4c1bd' : tod === 'rain' ? '#9aa3ad' : '#a3a0a6');
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
  /** Static ride height of a car model (for visual-only cars such as remote players). */
  private rideHeightOf(carId: CarId) {
    let h = this.rideHeights.get(carId);
    if (h === undefined) {
      const tmp = new VehicleSim(this.physics, CAR_SPECS[carId], new THREE.Vector3(0, -500, 0), 0);
      h = tmp.rideHeight;
      tmp.dispose();
      this.rideHeights.set(carId, h);
    }
    return h;
  }

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
      exhaust: newExhaustState(),
    };
  }

  private removeRacer(r: Racer | null) {
    if (!r) return;
    this.root.remove(r.visual.root);
    r.visual.dispose();
    r.sim.dispose();
  }

  private clearRace() {
    this.remotes?.clear();
    this.hud.online = null;
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
    this.exhaust.clear();
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
    this.garageCar.setHeadlights(this.env.preset.lampsOn > 0.5 ? 1 : 0.5, true);
    // park at the summit, just before the start line, angled for the camera
    const s = this.track.startS - 14;
    const p = this.track.pointAt(s, 0.6);
    this.garageCar.root.position.copy(p);
    // a train stands straight along the road (its cars trail behind the root)
    this.garageCar.root.rotation.y = this.track.headingAt(s) + (spec.train ? 0 : 0.35);
    this.root.add(this.garageCar.root);
    this.garageCar.refresh();
    this.garageScale = spec.train ? 2.6 : 1;
    // a train is framed on its leading car (the root is its front bogie)
    this.garageFocus.copy(p).addScaledVector(_f.set(Math.sin(this.track.headingAt(s)), 0, Math.cos(this.track.headingAt(s))), spec.train ? -7 : 0);
    void ride;
    // showroom key light above and in front of the car
    // (higher over a train: right above its roof it burnt a white patch into it)
    this.garageLight.position.copy(p).add(new THREE.Vector3(0, spec.train ? 16 : 7, 0));
    this.garageLight.target.position.copy(p);
    this.garageLight.intensity = spec.train ? 120 : 70;
    this.garageLight.castShadow = this.quality.shadows;
    if (!this.garageLight.parent) this.root.add(this.garageLight, this.garageLight.target);
    // put the camera on the uphill side so the background is the valley, not the cutting
    const r = this.track.getRight(Math.round(s), new THREE.Vector3());
    const up = this.terrain.heightAt(p.x + r.x * 14, p.z + r.z * 14) > this.terrain.heightAt(p.x - r.x * 14, p.z - r.z * 14) ? 1 : -1;
    const side = Math.atan2(r.x * up, r.z * up);
    const ahead = this.track.headingAt(s);
    // too steep a bank on that side (ridge courses) hides the car: take the first direction whose whole
    // camera swing stays clear of the terrain (other side, then along the road)
    const clear = (yaw: number) => {
      for (let k = -3; k <= 3; k++) {
        const a = yaw + (k / 3) * 0.75;
        for (const d of [2.5, 4, 5.5, 7, 8.6]) {
          // the sight line from the camera (1.7 m up at 8.6 m) to the car body (0.6 m); the ground clamp in
          // garageCamera() may lift the camera spot itself a little, but not onto a bank
          const sight = d >= 8.6 ? p.y + 1.3 : p.y + 0.6 + 1.1 * (d / 8.6);
          if (this.terrain.heightAt(p.x + Math.sin(a) * d, p.z + Math.cos(a) * d) > sight) return false;
        }
      }
      return true;
    };
    this.garageViewYaw = [side, side + Math.PI, ahead, ahead + Math.PI].find(clear) ?? side;
    if (this.phase !== 'garage') {
      this.garageAngle = 0.6;
      this.garageOrbit = null;
    }
    this.setPhase('garage');
  }

  startRace(cfg: RaceConfig) {
    this.clearRace();
    this.config = cfg;
    const gridS = this.track.startS - 6;
    const lane = cfg.online ? ONLINE_LANES[cfg.online.slot % ONLINE_LANES.length] : cfg.mode === 'rival' ? 2.0 : 0;
    this.player = this.createRacer(cfg.carId, gridS, lane, {
      headlights: true,
      // the colour picked in the car select (it used to be ignored); online: the slot colour tells players apart
      color: cfg.online ? SLOT_COLORS[cfg.online.slot % SLOT_COLORS.length] : cfg.color,
    });
    // a train: the high chase, and its first race starts in the cab view
    const train = !!CAR_SPECS[cfg.carId].train;
    const t = CAR_SPECS[cfg.carId].train;
    // the cab view sits just behind the nose of the leading car
    this.chase.profile = t ? { ...TRAIN_CAMERA, front: { ...TRAIN_CAMERA.front, ahead: trainNose(t) - 0.35 } } : CAR_CAMERA;
    if (train !== this.cameraForTrain) this.chase.mode = train ? 'bumper' : 'chase';
    this.cameraForTrain = train;
    if (cfg.online) {
      this.remotes.setPeers(cfg.online.peers, (slot) => ({
        position: this.track.pointAt(gridS, ONLINE_LANES[slot % ONLINE_LANES.length]),
        heading: this.track.headingAt(gridS),
      }));
      this.remotes.setHeadlights(this.env.preset.lampsOn > 0.5 ? 1 : 0.6);
      // other players are solid: physical stand-ins the local car can bump into
      this.remotes.enablePhysics(this.physics);
    }
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
    this.countdownT = cfg.online ? (cfg.online.startAt - performance.now()) / 1000 : 3.999;
    this.hud.raceTime = 0;
    this.hud.online = null;
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
    // the race's lights (headlamp spots and their shadows) change every material's shader: compile them all in
    // the background during the countdown rather than each the first time it comes into view (mid-race hitches)
    void this.precompile();
    if (this.audio) {
      void this.audio.playMusic(this.raceMusic(cfg.mode), { fallback: this.course.music });
      this.audio.preload('jingle_finish', 'jingle_lose', 'jingle_rival_win', 'jingle_medal', 'jingle_record');
      const spec = CAR_SPECS[cfg.carId];
      this.audio.engine('player', spec);
      if (this.rival) this.audio.engine('rival', this.rival.sim.spec);
    }
    this.setPhase('countdown');
  }

  restart() {
    if (this.config) this.startRace(this.config);
  }

  /** Battles have their own tracks; otherwise rain and dawn have theirs, night runs the course's. */
  private raceMusic(mode: RaceMode) {
    if (mode === 'rival') return 'bgm_rival';
    if (mode === 'ghost') return 'bgm_ghost';
    if (this.timeOfDay === 'rain') return 'bgm_race_rain';
    if (this.timeOfDay === 'dawn') return 'bgm_race_dawn';
    return this.course.music;
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
    this.updateLampLights(dt);
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
      if (this.config?.online) this.remotes.stepProxies(performance.now(), this.player?.sim.position ?? null);
      this.physics.step();
      for (const r of racers) r.sim.postStep(PHYSICS_DT);
      this.detectCarContact();
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

  /** Physics step: is the player's car touching another car (rival or online stand-in), and how hard? */
  private detectCarContact() {
    const pl = this.player;
    if (!pl || this.paused) return;
    const others = this.rival ? [this.rival.sim.collider, ...this.remotes.colliders()] : this.remotes.colliders();
    for (const c of others) {
      this.physics.world.contactPair(pl.sim.collider, c, (m) => {
        for (let i = 0; i < m.numContacts(); i++) {
          // pairs are reported a little before the bodies meet (prediction distance): only real contact counts
          const impulse = m.contactImpulse(i);
          if (m.contactDist(i) > 0.02 && impulse <= 0) continue;
          this.contact.touching = true;
          this.contact.impulse = Math.max(this.contact.impulse, impulse);
        }
      });
    }
  }

  /** Per frame: a thud (scaled by the hit) when cars meet, a metal scrape while they stay together. */
  private carContactFeedback(dt: number) {
    const pl = this.player!;
    const c = this.contact;
    const dv = c.impulse / pl.sim.spec.mass;
    c.cooldown = Math.max(0, c.cooldown - dt);
    // a thud for every real hit (not only the first touch of a long rub), at most a few per second
    if (c.touching && dv > 0.2 && (c.cooldown === 0 || !c.wasTouching)) {
      this.audio?.impact(clamp(0.3 + dv / 6, 0.3, 1));
      this.contactShake = Math.max(this.contactShake, clamp(dv / 5, 0.25, 1));
      c.cooldown = 0.25;
    }
    this.audio?.scrape(c.touching ? clamp(pl.sim.speed / 30, 0.25, 1) : 0);
    this.contactShake *= Math.exp(-dt * 5);
    c.wasTouching = c.touching;
    c.touching = false;
    c.impulse = 0;
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
      if (pl && r === this.rival) r.ai.opponent = { s: pl.proj.s, lateral: pl.proj.lateral, speed: pl.sim.forwardSpeed };
      if (r.finished && r.ai.pullOver === null) r.ai.pullOver = r.proj.lateral >= 0 ? 10 : -10;
      r.ai.update(r.sim, dt, r.input);
      if (r.finished) {
        // pull over to its side and stop; once slow, hold it with the handbrake and a light foot brake
        // (VehicleSim engages reverse when the brake is held above 0.3 at a standstill)
        r.input.throttle = 0;
        r.input.brake = r.sim.forwardSpeed > 1.5 ? 0.4 : 0.25;
        r.input.handbrake = r.sim.forwardSpeed <= 1.5;
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
    // a parked rival past the line is solid: the cool-down driver steers round it
    const o = this.rival && this.rival !== r ? this.rival : null;
    r.ai.opponent = o ? { s: o.proj.s, lateral: o.proj.lateral, speed: o.sim.forwardSpeed } : null;
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
    // (a finished rival parks on purpose: not stuck)
    if (r.flippedTime > 2 || lost || (r.ai && r.ai.needsRespawn && r !== this.player && !r.finished)) this.respawn(r);
  }

  private respawn(r: Racer) {
    const s = clamp(Math.min(r.lastSafe.s, r.proj.s) - 4, 5, this.track.length - 20);
    const lat = clamp(this.line.offsetAt(s), -2, 2);
    r.sim.reset(this.track.pointAt(s, lat), this.track.headingAt(s), 0);
    r.proj.index = -1;
    r.flippedTime = 0;
    // a respawned car may land inside another player's car: ghost them until clear
    if (r === this.player && this.config?.online) this.remotes.ghostAll(performance.now() + 1500);
    r.lastSafe = { s, t: this.time };
    for (let i = 0; i < 4; i++) this.skids.break(i);
  }

  private updateCountdown(dt: number) {
    const prev = Math.ceil(this.countdownT);
    const online = this.config?.online;
    // online: everybody's lights follow the server's start time, not their own frame clock
    this.countdownT = online ? (online.startAt - performance.now()) / 1000 : this.countdownT - dt;
    const now = Math.ceil(this.countdownT);
    this.hud.countdown = Math.max(0, this.countdownT);
    if (now !== prev && now >= 1 && now <= 3) this.audio?.beep(660, 0.18, 'square', 0.18);
    if (this.countdownT <= 0) {
      this.audio?.beep(1320, 0.5, 'square', 0.22);
      this.raceStartTime = this.simTime + (online ? this.countdownT : 0);
      this.hud.countdown = 0;
      this.setPhase('racing');
    }
  }

  /** Per physics step: projection, recording, sector splits and finish detection. */
  private raceStep() {
    const pl = this.player;
    if (!pl) return;
    const raceTime = this.raceClock();
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
    const raceTime = pl.finished ? pl.finishTime : this.raceClock();
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
    }
    if (this.config?.online) this.updateOnlineStandings();
    if (!pl.finished) {
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

  /**
   * Race time of the local player. Online, a client whose frame rate drops runs its physics in slow
   * motion; taking the wall clock since the shared green light as a floor keeps that from paying off.
   */
  private raceClock() {
    const sim = this.simTime - this.raceStartTime;
    const online = this.config?.online;
    return online ? Math.max(sim, (performance.now() - online.startAt) / 1000) : sim;
  }

  /** Snapshot of the local car for the other players (online battles). */
  netState(): NetState | null {
    const pl = this.player;
    if (!pl || !this.config?.online || (this.phase !== 'countdown' && this.phase !== 'racing' && this.phase !== 'finished')) return null;
    const p = pl.sim.position, q = pl.sim.quaternion;
    const r = (v: number, k = 1000) => Math.round(v * k) / k;
    const st: NetState = {
      t: Math.round(performance.now()),
      p: [r(p.x), r(p.y), r(p.z)],
      q: [r(q.x, 1e4), r(q.y, 1e4), r(q.z, 1e4), r(q.w, 1e4)],
      v: r(pl.sim.forwardSpeed, 100),
      st: r(pl.sim.wheels[0]?.steer ?? 0, 1e3),
      s: r(pl.proj.s, 10),
      br: pl.sim.input.brake > 0.2 ? 1 : 0,
    };
    if (pl.finished) st.fin = Math.round(pl.finishTime * 1000);
    return st;
  }

  /** Live order of an online battle: finishers by time, then by distance covered. */
  private updateOnlineStandings() {
    const pl = this.player;
    if (!pl || !this.config?.online) return;
    const now = performance.now();
    const rows = [
      { id: this.onlineSelfId, name: 'YOU', slot: this.config.online.slot, me: true, s: pl.proj.s, finMs: pl.finished ? Math.round(pl.finishTime * 1000) : null, lost: false },
      ...this.remotes.standings().map((r) => ({ id: r.id, name: r.name, slot: r.slot, me: false, s: r.s, finMs: r.fin, lost: r.lastHeard > 0 && now - r.lastHeard > 5000 })),
    ];
    rows.sort((a, b) => {
      if (a.finMs !== null || b.finMs !== null) return (a.finMs ?? Infinity) - (b.finMs ?? Infinity);
      return b.s - a.s;
    });
    this.hud.online = rows;
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
      const lost = this.config?.online
        ? this.remotes.standings().some((r) => r.fin !== null && r.fin < pl.finishTime * 1000)
        : !!this.rival?.finished && this.rival.finishTime < pl.finishTime;
      const beatRival = !lost && !!this.rival;
      if (lost) void a.playJingle('jingle_lose').then((ok) => ok || a.chime([659, 587, 494, 440], 0.16));
      else void a.playJingle(beatRival ? 'jingle_rival_win' : 'jingle_finish').then((ok) => ok || a.chime([784, 988, 1175, 1568], 0.11));
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
      if (!this.paused) {
        this.emitTyreFx(r, dt);
        this.emitExhaust(r, dt);
      }
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
    if (this.config?.online && (this.phase === 'countdown' || this.phase === 'racing' || this.phase === 'finished')) {
      this.remotes.update(performance.now(), dt);
    }
    if (!this.paused) {
      this.smoke.update(dt);
      this.exhaust.update(dt);
    }
    this.smoke.setViewportHeight(this.renderer.domElement.height);
    this.exhaust.setViewportHeight(this.renderer.domElement.height);

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
        impact: Math.max(sim.impact, this.contactShake),
      });
    }

    // ---- HUD + audio
    if (this.player) {
      const sim = this.player.sim;
      this.hud.speedKmh = Math.abs(sim.forwardSpeed) * 3.6;
      this.hud.rpm = sim.rpm;
      this.hud.gear = sim.gear;
      this.hud.boost = sim.boost;
      // camera shake and contact bookkeeping must run with or without sound
      if (!this.paused) this.carContactFeedback(dt);
      if (this.audio && !this.paused) {
        const e = this.audio.engine('player', sim.spec);
        if (e.blowOff(sim.input.throttle, sim.boost)) this.audio.blowOff();
        e.update(sim.rpm, sim.input.throttle, sim.boost, 1, sim.spec.engine.redline, sim.input.brake);
        let skid = 0;
        for (const w of sim.wheels) if (w.grounded) skid = Math.max(skid, w.skid);
        this.audio.updateTyres(skid, sim.speed);
        this.audio.updateWind(sim.speed);
        if (sim.impact > 0.15) this.audio.impact(Math.min(1, sim.impact * 1.5));
        if (this.rival) {
          const re = this.audio.engine('rival', this.rival.sim.spec);
          const d = this.rival.sim.position.distanceTo(this.camera.position);
          re.update(this.rival.sim.rpm, this.rival.input.throttle, this.rival.sim.boost, clamp(1 - d / 140, 0, 1) * 0.8, this.rival.sim.spec.engine.redline);
        }
      }
    } else if (this.audio && this.attractCar && this.phase === 'attract') {
      const sim = this.attractCar.sim;
      const e = this.audio.engine('attract', sim.spec);
      const d = sim.position.distanceTo(this.camera.position);
      e.update(sim.rpm, sim.input.throttle, sim.boost, clamp(1 - d / 160, 0, 1) * 0.5, sim.spec.engine.redline);
    }
  }

  /** Exhaust puffs and backfires from the tailpipe (with a pop when the camera is close). */
  private emitExhaust(r: Racer, dt: number) {
    const sim = r.sim;
    if (sim.spec.train) return;
    const rig = r.visual.rig, root = r.visual.root;
    // tailpipe in world space from the car's pose (the model only sits lower by the ride height)
    _tip.copy(rig.anchors.exhaust).add(rig.root.position).applyQuaternion(root.quaternion).add(root.position);
    _back.copy(sim.forward).negate();
    const rpm = clamp(sim.rpm / sim.spec.engine.redline, 0, 1);
    const throttle = sim.gear === -1 ? 0.2 : sim.input.throttle;
    const bang = this.exhaust.emit(r.exhaust, _tip, _back, sim.velocity, throttle, rpm, sim.spec.engine.turbo, dt);
    if (bang && this.audio) {
      const d = _tip.distanceTo(this.camera.position);
      const gain = clamp(1 - d / 60, 0, 1);
      if (gain > 0.05) this.audio.backfire(0.25 + 0.55 * gain);
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

  /** Drag the garage camera around the car (pixels); it stays where it is left until the garage reopens. */
  orbitGarage(dx: number, dy: number) {
    const o = (this.garageOrbit ??= { yaw: Math.sin(this.garageAngle) * 0.75, pitch: 0.13, dist: 8.6 * this.garageScale });
    o.yaw -= dx * 0.008;
    o.pitch = clamp(o.pitch + dy * 0.005, 0.02, 1.2);
  }

  /** Wheel zoom of the garage camera: factor on the distance. */
  zoomGarage(factor: number) {
    const o = (this.garageOrbit ??= { yaw: Math.sin(this.garageAngle) * 0.75, pitch: 0.13, dist: 8.6 * this.garageScale });
    o.dist = clamp(o.dist * factor, 5.5 * this.garageScale, 13 * this.garageScale);
  }

  private garageCamera(dt: number) {
    const car = this.garageFocus;
    const o = this.garageOrbit;
    // swing slowly from the uphill side; the car sits left of centre beside the UI card
    this.garageAngle += dt * 0.2;
    const a = this.garageViewYaw + (o ? o.yaw : Math.sin(this.garageAngle) * 0.75);
    const cam = this.camera;
    const k = this.garageScale;
    const flat = o ? Math.cos(o.pitch) * o.dist : 8.6 * k;
    _v.set(car.x + Math.sin(a) * flat, car.y + (o ? 0.6 * k + Math.sin(o.pitch) * o.dist : 1.7 * k), car.z + Math.cos(a) * flat);
    // steep cuttings (ridge courses) would swallow the camera: keep it, and its glide in, above ground
    _v.y = Math.max(_v.y, this.terrain.heightAt(_v.x, _v.z) + 1.4);
    cam.position.lerp(_v, 1 - Math.exp(-dt * (o ? 14 : 3)));
    cam.position.y = Math.max(cam.position.y, this.terrain.heightAt(cam.position.x, cam.position.z) + 1.2);
    // aim to the right of the car so it is framed in the left part of the screen
    _f.set(-Math.cos(a), 0, Math.sin(a)).multiplyScalar(-2.4 * (o ? o.dist / 8.6 : k));
    cam.lookAt(car.x + _f.x, car.y + 0.6 * k, car.z + _f.z);
    if (Math.abs(cam.fov - 38) > 0.01) {
      cam.fov = damp(cam.fov, 38, 3, dt);
      cam.updateProjectionMatrix();
    }
  }

  setGarageColor(color: string) {
    this.garageCar?.setColor(color);
  }

  /** Move the pooled point lights to the lamps nearest the camera. */
  /**
   * Real-time lights for the street lamps nearest the camera (the baked lightmap covers the rest).
   * A light keeps its lamp while that lamp stays among the nearest ones and fades out before it moves
   * to another, so lamp pools never pop on and off.
   */
  private updateLampLights(dt: number) {
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
    const wanted = new Set(best.map((b) => b.i));
    const assigned = new Set(this.lampSlots.filter((i) => i >= 0 && wanted.has(i)));
    const fade = Math.min(1, dt * 4);
    this.lampLights.forEach((l, k) => {
      let lamp = this.lampSlots[k];
      if (lampsOn < 0.2) {
        l.intensity = 0;
        return;
      }
      if (lamp >= 0 && !wanted.has(lamp)) {
        // leaving lamp: fade out, then become free
        l.intensity = Math.max(0, l.intensity - 170 * lampsOn * fade);
        if (l.intensity > 0.5) return;
        lamp = -1;
      }
      if (lamp < 0) {
        const free = best.find((b) => !assigned.has(b.i));
        if (!free) {
          l.intensity = 0;
          this.lampSlots[k] = -1;
          return;
        }
        lamp = free.i;
        assigned.add(lamp);
        l.intensity = 0;
        // below the fixture, never right against it: a point light a few cm from the rock-shed
        // ceiling or a cutting made a blinding hot spot that flooded the screen with bloom
        l.position.copy(lamps[lamp].position);
        l.position.y -= LAMP_LIGHT_DROP;
        l.color.copy(lamps[lamp].color);
      }
      this.lampSlots[k] = lamp;
      const target = 170 * lampsOn * smoothstep(200, 90, Math.sqrt(lamps[lamp].position.distanceToSquared(cam)));
      l.intensity += (target - l.intensity) * fade;
    });
  }

  get currentConfig() {
    return this.config;
  }

  get playerSim() {
    return this.player?.sim ?? null;
  }

  /**
   * Compiles every material of the scene for the current lights, in parallel where the browser can. With
   * post-processing the scene is drawn into an offscreen buffer, whose shader variants (linear output, no tone
   * mapping) differ from the screen's ones: compiled against a stand-in target, or the work is wasted.
   */
  private precompile() {
    const r = this.renderer, prev = r.getRenderTarget();
    if (this.quality.bloom) r.setRenderTarget((this.compileTarget ??= new THREE.WebGLRenderTarget(1, 1)));
    const done = r.compileAsync(this.scene, this.camera);
    r.setRenderTarget(prev);
    return done.catch(() => undefined);
  }

  dispose() {
    this.clearRace();
    this.compileTarget?.dispose();
    this.input.dispose();
    this.physics?.dispose();
    this.scene.remove(this.root);
  }
}
