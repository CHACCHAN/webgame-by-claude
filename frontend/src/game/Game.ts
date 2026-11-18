import * as THREE from 'three';
import { Track } from './track/Track';
import { COURSES, type CourseId, type CourseInfo } from './track/courses';
import type { TerrainData } from './track/terrain';
import { buildTerrainParallel, terrainStats } from './track/terrainJob';
import { PhysicsWorld, PHYSICS_DT, initRapier } from './vehicle/PhysicsWorld';
import { VehicleSim, emptyInput, type AssistLevel, type VehicleInput } from './vehicle/VehicleSim';
import { CAR_ORDER, CAR_SPECS, VEHICLE_ORDER, type CarId } from './vehicle/carSpecs';
import { RacingLine } from './ai/RacingLine';
import { AIDriver, AI_PROFILES, type AILevel } from './ai/AIDriver';
import type { VoiceId } from './audio/speech/text';
import { RivalMind, cornerAhead, type Horn, type Moment, type RivalBrain, type Situation } from './ai/RivalMind';
import { buildScenery, vendingSpot, type SceneryResult } from './render/TrackScenery';
import { buildEnvironment, PRESETS, type EnvironmentRig, type TimeOfDay } from './render/Environment';
import { CarVisual } from './render/CarVisual';
import { clearing } from './render/instancing';
import { loadVegetation, SHADOW_LAYER, vegetationHold, vegetationLights, vegetationWeather, type VegetationQuality } from './render/vegetation';
import { vegetationFiles } from './render/vegetationPlanting';
import { VOLUME_SPOTS, volume, volumeSpot } from './render/volumetricLights';
import { gpuBytes } from './render/gpuBytes';
import { bakeShade } from './render/farShade';
import { dawnSun } from './track/landforms';
import { keyShadowNode } from './render/keyShadow';
import { LAMP_BEAM, LAMP_CANDELA } from './render/lampField';
import { registerLampField } from './render/lampFieldNode';
import { LightRig } from './render/LightRig';
import { lampStreak, lampsAround, mirrorLamps, showSurroundings } from './render/carSurface';
import { registerRigLights } from './render/coatGlint';
import { ensureVehicleModels, onModelWait, preloadVehicleModels, vehicleModelReady } from './render/vehicleModels';
import { loadTrafficModels } from './render/trafficModels';
import { loadSurfaceTextures } from './render/surfaceTextures';
import { loadProps } from './render/props';
import { loadRoadsideModels } from './render/roadsideModels';
import { wetness } from './render/weather';
import { findCorners, type Corner, type CornerKind } from './track/corners';
import { paintFor, RemoteRacers, type Peer } from './net/RemoteRacers';
import { NetLink, type LocalState } from './net/NetLink';
import type { GameRenderer } from './render/RenderHost';
import { footprint, onlineGrid } from './net/grid';
import { LobbyLineup } from './net/LobbyLineup';
import { LINEUP_VIEW, type LineupEntry } from './net/lineup';
import { BIKE_CAMERA, CAR_CAMERA, ChaseCamera, JET_CAMERA, TRAIN_CAMERA } from './camera/ChaseCamera';
import { hasExhaust, traitsOf } from './vehicle/kinds';
import { InputManager } from './input/Input';
import { TireSmoke, SkidMarks } from './fx/TireEffects';
import { ExhaustFX, newExhaustState, type ExhaustState } from './fx/Exhaust';
import { Rain } from './fx/Rain';
import { AudioEngine } from './audio/AudioEngine';
import { coverShare, rainBodyOf } from './audio/rain';
import { kindOf } from './vehicle/kinds';
import { GhostPlayer, GhostRecorder, type GhostData } from './race/Ghost';
import { clamp, damp, lerp, smoothstep, wrapAngle } from './util/math';
import { Departure } from './race/Departure';
import { jetForLivery } from './vehicle/jets';
import type { TrackProjection } from './track/Track';
import { loadTrainModel, loadTrainVariants, trainModelReady, trainNose } from './render/TrainModel';
import { specForLivery, trainLivery, trainModelKey, TRAIN_ORDER } from './vehicle/trains';

/** A built course: everything `buildWorld` makes. */
interface World {
  course: CourseInfo;
  track: Track;
  corners: Corner[];
  line: RacingLine;
  terrain: TerrainData;
  physics: PhysicsWorld;
  scenery: SceneryResult;
  env: EnvironmentRig;
  dry: { road?: { roughness: number; color: THREE.Color; normal: number; env: number }; terrain?: number };
  /** where the vending machine glows, if the course has one */
  vending: THREE.Vector3 | null;
  /** what it holds on the GPU, roughly (MB; counted when it is put aside) */
  mb: number;
}

/** the car of the title's attract run: the one vehicle the game waits for before it opens */
const ATTRACT_CAR: CarId = 'shiden';

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
  /** the Blender-made vegetation: which set, how far its levels of detail reach, how much undergrowth */
  vegetation: VegetationQuality;
  /** the ground's, the road's and the roadside's layered materials: 0 = the plain ones, 1–3 = medium to ultra */
  surfaceDetail?: number;
}

export interface RaceConfig {
  mode: RaceMode;
  carId: CarId;
  rivalLevel?: AILevel;
  /** the player's record against this rival and the medal held on the course: what the rival knows when it speaks */
  rivalRecord?: { wins: number; losses: number; medal: 'none' | 'bronze' | 'silver' | 'gold' };
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
  /** what the rival says (before the start, at the finish); `seq` changes with every new line */
  rivalLine: { text: string; moment: Moment; seq: number } | null;
  ghostProgress: number | null;
  position: number;
  gapMeters: number;
  wrongWay: boolean;
  driftCombo: number;
  driftScore: number;
  boost: number;
  turbo: boolean;
  /** a fighter: the engine box shows its engines' speed (N2 %) and the afterburner (0…1) instead of a gear */
  jet: boolean;
  afterburner: number;
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
  /** work in the background the player waits for (a model on its way): a short label, null when it is over */
  | { type: 'busy'; label: string | null }
  | { type: 'finish'; result: RaceResult }
  /** the rival spoke (`hud.rivalLine`): the results screen shows what it says after the race */
  | { type: 'rivalLine'; moment: Moment; text: string }
  /** the garage shows a vehicle (a picker's choice reaching the engine): what an online room tells the others */
  | { type: 'garage'; carId: CarId; color?: string }
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
  /** a fighter past the line: its take-off */
  departure?: Departure;
}

const _v = new THREE.Vector3(), _w = new THREE.Vector3(), _q = new THREE.Quaternion(), _f = new THREE.Vector3();
const _tip = new THREE.Vector3(), _back = new THREE.Vector3();
/** tyre grip on a wet road (rain) as a share of the dry grip */
export const WET_GRIP = 0.8;
const _zero = new THREE.Vector3();
/** car states go out this often (s): every other frame of a 60 Hz screen, so the peers get them evenly spaced */
/** how long a rival's line waits for its voice before it is shown without it, ms */
const VOICE_WAIT = 700;
const NET_SEND_INTERVAL = 1 / 30;
/** the acceleration sent with a state is smoothed over about this long (s): suspension chatter and wall hits are not a trend */
const NET_ACC_TAU = 0.06;

export class Game {
  readonly root = new THREE.Group();
  /** how the street lamps' highlights in the cars' clear coats are drawn (render/carSurface.ts; uniforms: probes may try values) */
  readonly lampStreak = lampStreak;
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
  /** tyre grip multiplier from the weather (wet roads); the course's own surface multiplies in (`roadGrip`) */
  weatherGrip = 1;
  course!: CourseInfo;
  /** the courses that were shown before and are still built, the one left longest ago first */
  private kept = new Map<CourseId, World>();
  private vending: THREE.Vector3 | null = null;
  /**
   * Courses stay built besides the one shown (coming back to one is then a matter of a second instead of a
   * rebuild): each holds its geometry and textures on the GPU and its terrain and physics in memory. At most
   * `keepCourses` of them and `keepBudget` MB of GPU memory by our own count (`render/gpuBytes.ts`); what was left
   * longest ago is freed first. 0 = nothing is kept.
   */
  keepCourses = 3;
  keepBudget = 0;
  private dryMaterials: { road?: { roughness: number; color: THREE.Color; normal: number; env: number }; terrain?: number } = {};

  phase: GamePhase = 'loading';
  paused = false;
  hud: HudState = {
    speedKmh: 0, rpm: 0, redline: 8000, gear: 1, raceTime: 0, countdown: 0, splits: [], lastSplitDelta: null, lastSplitIndex: -1,
    progress: 0, rivalProgress: null, rivalLine: null, ghostProgress: null, position: 1, gapMeters: 0, wrongWay: false, driftCombo: 0, driftScore: 0,
    boost: 0, turbo: false, jet: false, afterburner: 0, sectorFlashT: 0, corner: null, online: null,
  };

  private listeners = new Set<Listener>();
  private accumulator = 0;
  private time = 0;
  /** advances only with physics steps: race timing is independent of the frame rate */
  private simTime = 0;
  private player: Racer | null = null;
  private rival: Racer | null = null;
  /**
   * Whom a rival may ask for its lines and for its two moves, blocking and the horn (`ai/RivalMind.ts`: the
   * server's language model, set by the UI). Empty: the game's own lines and rules. Nobody asked ever drives.
   */
  rivalBrains: RivalBrain[] = [];
  /**
   * The rivals' voice, given by the interface like the brains (audio/speech: a model on the GPU, there only when
   * the player wanted it and WebGPU exists): a line as sound, or nothing — then the line is only shown.
   */
  rivalVoice: ((text: string, voice: VoiceId) => Promise<{ pcm: Float32Array<ArrayBuffer>; rate: number } | null>) | null = null;
  private mind: RivalMind | null = null;
  private lineSeq = 0;
  /** game time at which the line on the HUD is taken away */
  private lineUntil = 0;
  private attractCar: Racer | null = null;
  private ghost: { player: GhostPlayer; visual: CarVisual; label: string; splits?: number[] } | null = null;
  private recorder = new GhostRecorder();
  private rivalRecorder = new GhostRecorder();
  private replay: {
    cars: { player: GhostPlayer; visual: CarVisual; wheelRot: number; last: THREE.Vector3; exhaust: ExhaustState & { speed: number } }[];
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
  /** a shot a menu asks for and holds while it is up (the conditions screen: the road ahead under the sky) */
  menuShot: 'sky' | null = null;
  /**
   * For probes (tools/, a report to look into): the camera stands at `from` and looks at `at`, whatever the phase.
   * `lookFrom` sets it in the road's own terms.
   */
  spy: { from: THREE.Vector3; at: THREE.Vector3 } | null = null;
  private cinematic = { shot: 0, t: 0, anchor: new THREE.Vector3(), anchorS: 0, pos: new THREE.Vector3(), side: 1, fore: 1, last: new THREE.Vector3(), look: new THREE.Vector3() };
  private garageCar: CarVisual | null = null;
  /** counts what was asked to be shown: a show that waited for a model goes ahead only if nothing came after it */
  private asked = 0;
  /** the colour last picked in the garage (a train's other line is shown once its model is loaded) */
  private garageWant: string | undefined;
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
  /**
   * Where the garage camera puts the vehicle on the screen: it aims this far to its right of and above the vehicle
   * (m at a car's distance; the default leaves the car left of centre, beside the card on the right; the car select
   * has its list on the left and the thumbnail tool wants it in the middle), with a factor on the distance.
   */
  garageFraming = { right: 2.4, up: 0, zoom: 1 };
  /** every light of the game, made once (the shaders are built for the set: see there) */
  private lights!: LightRig;
  /** camera height above the focus per unit of scale, in the automatic swing (a line-up is looked at from higher up) */
  private garageLift = 1.7;
  /** the online waiting room's vehicles, in place of the garage's single car (`showLobby`) */
  private lobby: LobbyLineup | null = null;
  /** where the line-up's camera is heading (the framing follows the members as they come, go and change vehicles) */
  private lobbyView = { focus: new THREE.Vector3(), scale: 1, ends: [new THREE.Vector3(), new THREE.Vector3()] as const };
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
  /** the car-state exchange of an online battle (`remotes` draws what it receives); `net.stats()` are its numbers */
  readonly net = new NetLink();
  /**
   * The frame's moment on the wall clock (ms, as performance.now): advanced by the frame time, like the physics,
   * and only nudged towards performance.now(), which is read at an uneven point of every frame. Online, a
   * millisecond of unevenness would move the other cars by 5 cm at 180 km/h.
   */
  private wall = 0;
  /** the moment of the latest physics state on that clock (ms) */
  private stateWall = 0;
  private netSendT = 0;
  /** physics seconds per wall-clock second, smoothed */
  private simRate = 1;
  private netUrgent = false;
  /** counts the local car's respawns for the peers (2 bit) */
  private netEpoch = 0;
  private netAcc = new THREE.Vector3();
  private netVel = new THREE.Vector3();
  private rideHeights = new Map<CarId, number>();
  /** stand-in for the post-processing buffer when compiling shaders (see precompile) */
  private compileTarget: THREE.RenderTarget | null = null;
  /** compiles the scene's shaders for the buffers it is really drawn into (the render host's scene pass), when given */
  compileScene: ((hold: boolean) => Promise<unknown>) | null = null;
  /** … and those of one object that is not in the scene yet (a model about to be shown), when given */
  compileObject: ((object: THREE.Object3D) => Promise<unknown>) | null = null;
  private cornerIdx = 0;
  private warnedCorner = -1;
  /** debug/testing: let an AI drive the player car and speed up simulated time */
  autoDrive = false;
  timeScale = 1;

  constructor(
    readonly renderer: GameRenderer,
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

  /**
   * A course laid out and its terrain on the way: the heights are worked out on the other cores
   * (`track/terrainJob.ts`) while this thread goes on with whatever does not need them.
   */
  private survey(courseId: CourseId) {
    const course = COURSES[courseId];
    const track = new Track(course.design);
    return { courseId, track, terrain: buildTerrainParallel(courseId, track, course.landform) };
  }
  /** how the last terrain was worked out (threads, ms, why not on workers): for probes */
  readonly terrainJob = terrainStats;
  /** the first course's, begun before the downloads so that both run at the same time */
  private surveyed: { courseId: CourseId; track: Track; terrain: Promise<TerrainData> } | null = null;

  async load(courseId: CourseId, timeOfDay: TimeOfDay) {
    this.timeOfDay = timeOfDay;
    this.surveyed = this.survey(courseId);
    await this.yieldFrame(0.05, '物理エンジンを初期化中');
    await initRapier();
    await this.yieldFrame(0.08, 'コースの素材を読み込み中');
    // only what the title needs (the course's textures and props, the car of the attract run); the other vehicles
    // follow in the background once the title is up, and whoever shows one asks for it first (`needs`)
    onModelWait((n) => this.emit({ type: 'busy', label: n > 0 ? '車両モデルを読み込み中' : null }));
    await Promise.all([ensureVehicleModels([ATTRACT_CAR]), loadSurfaceTextures(this.quality.surfaceDetail ?? 0), loadProps(), this.quality.surfaceDetail ? loadRoadsideModels() : null]);
    this.root.add(this.smoke.points, this.skids.mesh, this.rain.mesh, this.exhaust.group);
    this.exhaust.density = this.quality.treeDensity < 0.6 ? 0.6 : 1;
    this.remotes = new RemoteRacers(this.root, (id) => this.rideHeightOf(id), false, this.net);
    // the lights: all of them now, none later (the street lamps are one of them, whatever the course)
    registerLampField(this.renderer);
    registerRigLights(this.renderer);
    this.lights = new LightRig(this.quality);
    // (a car's paint and glass show the lamps as a mirror does; the lowest quality keeps the plain environment map)
    if (this.quality.surfaceDetail) mirrorLamps(this.lights.lamps);
    // (the sun's / moon's shadow: the map near the camera, the course's baked shade beyond it)
    if (this.quality.shadows) this.lights.key.shadow.shadowNode = keyShadowNode(this.lights.key, this.lights.farShade, this.lights.keyMap);
    // (the trees' shadow meshes are drawn into this light's shadow map only)
    this.lights.key.shadow.camera.layers.enable(SHADOW_LAYER);
    vegetationLights(this.lights.key, this.lights.hemi, this.quality.shadows ? this.lights.farShade : null);
    this.root.add(this.lights.group);
    this.scene.fog = this.lights.fog;
    this.scene.add(this.root);
    this.chase = new ChaseCamera(this.camera, (x, z) => this.terrain.heightAt(x, z));
    // the title's car is made with the world, under the loading screen, and its shaders built in the world's compile:
    // made with the title, the title's first frame built them (0.5 s of standing picture, 11-18)
    await this.buildWorld(courseId, () => this.startAttract(false));
    this.setPhase('attract');
    // the rest in the order of the car select (the trains' other lines last), never during a race
    const idle = () => this.phase !== 'racing' && this.phase !== 'countdown';
    void preloadVehicleModels(VEHICLE_ORDER, idle).then(() => loadTrainVariants(TRAIN_ORDER));
  }

  /** Whether a vehicle's model is there (it is fetched when first asked for, and in the background after the title). */
  vehicleReady(id: CarId) {
    return vehicleModelReady(id);
  }

  /** The vehicles a race will show. */
  private raceVehicles(cfg: RaceConfig): CarId[] {
    const ids = [cfg.carId, ...(cfg.online?.peers.map((p) => p.carId) ?? [])];
    if (cfg.mode === 'rival' && cfg.rivalLevel) ids.push(this.course.rivals[cfg.rivalLevel].car);
    if (cfg.ghost) ids.push(cfg.ghost.carId);
    return ids;
  }

  /** Resolves when everything a race needs is there (the menus wait on it before `startRace`). */
  prepareRace(cfg: RaceConfig) {
    return ensureVehicleModels(this.raceVehicles(cfg));
  }

  /**
   * True when these vehicles' models are there. Else they are fetched and `again` is called when they are, unless
   * something else was asked to be shown meanwhile (`clearRace` or another `needs`).
   */
  private needs(ids: CarId[], again: () => void): boolean {
    const ask = ++this.asked;
    if (ids.every(vehicleModelReady)) return true;
    void ensureVehicleModels(ids).then(() => {
      if (ask === this.asked) again();
    });
    return false;
  }

  /**
   * Shows another course: one that was shown before and is still kept (`keepCourses`) comes back as it was, in the
   * time it takes to check its shaders; else it is built. The course that is left is kept in its place.
   */
  async switchCourse(courseId: CourseId) {
    if (this.course?.id === courseId) return;
    this.clearRace();
    this.setPhase('loading');
    // (taken out before the course that is left goes in: making room for that one must not free this one)
    const kept = this.kept.get(courseId);
    this.kept.delete(courseId);
    this.leaveWorld();
    if (kept) {
      await this.yieldFrame(0.5, `${kept.course.name} に戻っています`);
      this.enterWorld(kept);
      await this.yieldFrame(0.92, 'シェーダーを準備中');
      await this.precompile(true);
      await this.yieldFrame(1, '準備完了');
    } else {
      await this.buildWorld(courseId);
    }
  }

  /** `ready`: whatever else goes into the scene with the world (before its compile) */
  private async buildWorld(courseId: CourseId, ready?: () => void) {
    const course = COURSES[courseId];
    this.course = course;
    const ahead = this.surveyed?.courseId === courseId ? this.surveyed : this.survey(courseId);
    this.surveyed = null;
    await this.yieldFrame(0.12, `${course.name} を測量中`);
    this.track = ahead.track;
    this.corners = findCorners(this.track);
    this.line = new RacingLine(this.track);
    await this.yieldFrame(0.25, '山の地形を生成中');
    // (the models that need no terrain come in while the other cores work out the heights)
    const [terrain] = await Promise.all([
      ahead.terrain,
      loadVegetation(vegetationFiles(course.style ?? 'touge', this.quality.vegetation.undergrowth > 0), this.quality.vegetation.tier),
      // the autobahn's oncoming traffic is the game's own cars (light copies of their models)
      course.style === 'autobahn' ? ensureVehicleModels(CAR_ORDER).then(() => loadTrafficModels(CAR_ORDER)) : null,
    ]);
    this.terrain = terrain;
    await this.yieldFrame(0.5, '道路と森を配置中');
    this.physics = new PhysicsWorld(this.track);
    // (every level of every species stays in the scene until its shader is compiled)
    vegetationHold(true);
    vendingSpot.on = false;
    this.scenery = buildScenery(this.track, this.terrain, { treeDensity: this.quality.treeDensity, shadows: this.quality.shadows, shadowHalf: this.lights.keyMap.half, photoTextures: this.quality.photoTextures, treeLod: this.quality.treeLod, surfaceDetail: this.quality.surfaceDetail, vegetation: this.quality.vegetation, style: course.style, board: { name: course.name, roman: course.nameEn } });
    // an instanced mesh without instances has an empty matrix buffer, which WebGPU refuses to bind
    const empty: THREE.Object3D[] = [];
    this.scenery.group.traverse((o) => {
      if ((o as THREE.InstancedMesh).isInstancedMesh && (o as THREE.InstancedMesh).instanceMatrix.count === 0) empty.push(o);
    });
    for (const o of empty) o.removeFromParent();
    // the shade beyond the shadow map, for the moon of this course and for the morning sun
    const shading = this.scenery.shadeScene;
    if (shading) {
      this.scenery.shades = { moon: bakeShade(shading, _v.set(...this.terrain.landform.moonDir).normalize()), sun: bakeShade(shading, new THREE.Vector3(...dawnSun(this.terrain.landform)).normalize()) };
      this.scenery.shadeScene = null;
    }
    await this.yieldFrame(0.75, '夜景を灯しています');
    this.env = buildEnvironment(this.terrain, this.lights);
    this.dryMaterials = {};
    this.vending = vendingSpot.on ? vendingSpot.position.clone() : null;
    this.showWorld();
    ready?.();
    // (no frame between the world going into the scene and the compile that holds the picture: a frame there built
    // every shader of the new world at once, on the main thread, and the compile then built them a second time)
    this.emit({ type: 'loading', progress: 0.92, label: 'シェーダーを準備中' });
    await this.precompile(true);
    vegetationHold(false);
    await this.yieldFrame(1, '準備完了');
  }

  /** The course in `this.track` … `this.env` goes into the scene, under the time of day that is set. */
  private showWorld() {
    this.root.add(this.scenery.group, this.env.group);
    this.rain.setCovers(this.scenery.covers);
    this.lights.lamps.show(this.scenery.lamps);
    if (this.vending) this.lights.vending.position.copy(this.vending);
    this.lights.vending.intensity = this.vending ? 9 : 0;
    this.applyTimeOfDay(this.timeOfDay);
    this.chase.reset();
  }

  private enterWorld(w: World) {
    this.course = w.course;
    this.track = w.track;
    this.corners = w.corners;
    this.line = w.line;
    this.terrain = w.terrain;
    this.physics = w.physics;
    this.scenery = w.scenery;
    this.env = w.env;
    this.dryMaterials = w.dry;
    this.vending = w.vending;
    this.showWorld();
  }

  /**
   * Takes the course out of the scene. It stays built (geometry, textures and compiled shaders on the GPU, the
   * physics world, the terrain) while `keepCourses` allows; the one left longest ago is freed for it.
   */
  private leaveWorld() {
    if (!this.scenery) return;
    const w: World = { course: this.course, track: this.track, corners: this.corners, line: this.line, terrain: this.terrain, physics: this.physics, scenery: this.scenery, env: this.env, dry: this.dryMaterials, vending: this.vending, mb: 0 };
    this.root.remove(w.scenery.group, w.env.group);
    this.scene.environment = null;
    // (the lamps' light and the haze stop pointing into the course that is gone)
    this.lights.lamps.intensity = 0;
    volume.lamps = [];
    w.mb = gpuBytes(w.scenery.group, w.env.group) / 1e6;
    this.kept.set(w.course.id, w);
    this.trimKept();
  }

  /** what is kept built, for the settings screen and the tools: courses, and MB on the GPU by our own count */
  get keptCourses() {
    return [...this.kept.values()].map((w) => ({ id: w.course.id, mb: Math.round(w.mb) }));
  }

  /** Frees kept courses, the one left longest ago first, until they fit `keepCourses` and `keepBudget`. */
  private trimKept() {
    const total = () => [...this.kept.values()].reduce((s, w) => s + w.mb, 0);
    while (this.kept.size && (this.kept.size > this.keepCourses || total() > this.keepBudget)) {
      const [oldest] = this.kept.keys();
      this.disposeWorld(this.kept.get(oldest)!);
      this.kept.delete(oldest);
    }
  }

  /** The GPU ran out of memory (or the page was told to give some back): everything kept goes, and nothing is kept from now on. */
  releaseKept() {
    this.keepBudget = 0;
    this.trimKept();
  }

  private disposeWorld(w: World) {
    // what the courses that stay built (the kept ones, the one shown) draw with is not freed: texture sets, prop
    // models and their materials are shared between courses, and a kept course would be left with bindings to
    // textures the GPU no longer has
    const others = new Set<unknown>();
    const parts = (o: THREE.Object3D, each: (x: THREE.BufferGeometry | THREE.Material | THREE.Texture) => void) => {
      const m = o as THREE.Mesh;
      if (!m.geometry) return;
      each(m.geometry);
      for (const mat of Array.isArray(m.material) ? m.material : [m.material]) {
        if (!mat) continue;
        each(mat);
        for (const v of Object.values(mat)) if (v instanceof THREE.Texture) each(v);
      }
    };
    const alive = [...this.kept.values()].filter((k) => k !== w);
    if (this.scenery && this.scenery !== w.scenery && this.scenery.group.parent) alive.push({ scenery: this.scenery, env: this.env } as World);
    for (const k of alive) for (const g of [k.scenery.group, k.env.group]) g.traverse((o) => parts(o, (x) => void others.add(x)));
    const free = new Set<THREE.BufferGeometry | THREE.Material | THREE.Texture>();
    for (const g of [w.scenery.group, w.env.group]) {
      g.traverse((o) => {
        // per-instance buffers are not freed with the geometry
        if ((o as THREE.InstancedMesh).isInstancedMesh) (o as THREE.InstancedMesh).dispose();
        // every Sprite draws three.js' one shared quad: freeing it with a course took it from the sprites that stay
        // (smoke, sparks, the next course's lamps), and the WebGL 2 backend never drew a sprite again
        const sprite = (o as THREE.Sprite).isSprite;
        parts(o, (x) => {
          if (!others.has(x) && !(sprite && (x as THREE.BufferGeometry).isBufferGeometry)) free.add(x);
        });
      });
    }
    free.forEach((x) => x.dispose());
    w.env.dispose();
    w.physics.dispose();
  }

  applyTimeOfDay(tod: TimeOfDay) {
    // unknown values (e.g. corrupted saved settings) would poison the sky and fog with NaN: black screen
    if (!PRESETS[tod]) tod = 'night';
    this.timeOfDay = tod;
    this.env.apply(tod, this.scene, this.renderer);
    const envMap = this.env.buildEnvMap(this.renderer);
    this.scene.environment = envMap;
    showSurroundings(this.env.preset, tod === 'dawn', { dir: this.terrain.landform.cityGlowDir, glow: this.terrain.landform.cityGlow ?? 1 });
    // (the moon's light here is far brighter than the moon: its highlight in a clear coat is next to nothing)
    this.lights.key.coat.gain = tod === 'dawn' ? 1 : 0.04;
    this.scene.background = null;
    // the lamps' light (by day they are off: what is left of them is their glass and the pools under them, faint),
    // and their glow in the haze, as bright
    this.lights.lamps.intensity = this.env.preset.lampsOn < 0.2 ? 0 : LAMP_CANDELA * this.env.preset.lampsOn;
    volume.lamps = this.scenery.lamps;
    volume.lampIntensity = LAMP_CANDELA * this.env.preset.lampsOn;
    this.lights.farShade.show(this.scenery.shades?.[tod === 'dawn' ? 'sun' : 'moon'] ?? null);
    volume.density = this.env.preset.haze;
    const lamps = this.env.preset.lampsOn;
    this.lights.lamps.beam = LAMP_BEAM * lamps;
    for (const m of this.scenery.nightEmissive) {
      m.userData.baseIntensity ??= m.emissiveIntensity;
      m.emissiveIntensity = (m.userData.baseIntensity as number) * lamps;
    }
    this.smoke.setColor(tod === 'dawn' ? '#d9d4cf' : tod === 'rain' ? '#9aa6b4' : '#7d8794');
    this.exhaust.setColor(tod === 'dawn' ? '#c4c1bd' : tod === 'rain' ? '#9aa3ad' : '#a3a0a6');
    // wet roads: glossy, darker asphalt and slicker terrain; less tyre grip
    const wet = this.env.preset.rain;
    wetness.value = wet;
    const road = this.scenery.roadMaterial;
    this.dryMaterials.road ??= { roughness: road.roughness, color: road.color.clone(), normal: road.normalScale.x, env: road.envMapIntensity };
    const dry = this.dryMaterials.road;
    road.roughness = lerp(dry.roughness, 0.2, wet);
    road.color.copy(dry.color).multiplyScalar(lerp(1, 0.6, wet));
    road.normalScale.setScalar(lerp(dry.normal, 0.08, wet));
    road.envMapIntensity = lerp(dry.env, 1.8, wet);
    const terrain = this.scenery.terrainMaterial;
    this.dryMaterials.terrain ??= terrain.roughness;
    terrain.roughness = lerp(this.dryMaterials.terrain, 0.62, wet);
    this.rain.setIntensity(wet);
    vegetationWeather(wet, lamps);
    this.weatherGrip = lerp(1, WET_GRIP, wet);
    this.audio?.setRain(wet);
    this.lobby?.setLamps(lamps > 0.5 ? 1 : 0.5);
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

  private createRacer(carId: CarId, s: number, lateral: number, opts: { ai?: AILevel; headlights: boolean; color?: string; rival?: boolean }): Racer {
    // a train as fitted for its line (the livery picked: its inverter sound), a fighter's two-seater with its own mass
    const spec = jetForLivery(specForLivery(CAR_SPECS[carId], opts.color), opts.color);
    const p = this.track.pointAt(s, lateral);
    const sim = new VehicleSim(this.physics, spec, p, this.track.headingAt(s));
    sim.assist = this.assist;
    sim.gripScale = this.roadGrip;
    const visual = new CarVisual(spec, {
      headlights: opts.headlights,
      shadows: this.quality.shadows,
      rideHeight: sim.rideHeight,
      bodyColor: opts.color,
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
    this.asked++;
    this.departEye = null;
    this.remotes?.clear();
    this.hud.online = null;
    this.removeRacer(this.player);
    this.removeRacer(this.rival);
    this.removeRacer(this.attractCar);
    this.player = this.rival = this.attractCar = null;
    this.mind = null;
    this.audio?.hush();
    this.hud.rivalLine = null;
    if (this.ghost) {
      this.root.remove(this.ghost.visual.root);
      this.ghost.visual.dispose();
      this.ghost = null;
    }
    this.lights.showroomOn = false;
    this.lights.showroom.intensity = 0;
    if (this.garageCar) {
      this.root.remove(this.garageCar.root);
      this.garageCar.dispose();
      this.garageCar = null;
    }
    this.lobby?.dispose();
    this.lobby = null;
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
  /** `announce`: false leaves the phase as it is (the first load: the title comes once the car's shaders are built) */
  startAttract(announce = true) {
    this.clearRace();
    this.attractCar = this.createRacer(ATTRACT_CAR, this.track.startS - 10, 0, { ai: 'legend', headlights: true });
    // open on the slow orbit at the summit, then cycle through the other shots
    this.cinematic.shot = 0;
    this.cinematic.t = 0;
    if (announce) this.setPhase('attract');
  }

  showGarage(carId: CarId, color?: string) {
    // (a model still on its way: what stands there stays until it has come)
    if (!this.needs([carId], () => this.showGarage(carId, color))) return;
    const spec = CAR_SPECS[carId];
    const visual = new CarVisual(spec, { headlights: true, shadows: this.quality.shadows, rideHeight: 0, bodyColor: color });
    visual.setHeadlights(this.env.preset.lampsOn > 0.5 ? 1 : 0.5, true);
    // park at the summit, just before the start line, angled for the camera
    const s = this.track.startS - 14;
    const p = this.track.pointAt(s, 0.6);
    visual.root.position.copy(p);
    // the view per kind of vehicle (a train stands straight along the road, its cars trailing behind the root, and is
    // framed on its leading car)
    const view = traitsOf(spec).garage;
    visual.root.rotation.y = this.track.headingAt(s) + view.yaw;
    visual.refresh();
    // (building its shaders ahead with `compileObject` was tried, 11-11: the frame that first draws it stood just as
    // long, with the compile's own slow frames before it)
    this.placeGarage(visual, color, s, p);
  }

  private placeGarage(visual: CarVisual, color: string | undefined, s: number, p: THREE.Vector3) {
    const spec = visual.spec, carId = spec.id as CarId;
    const view = traitsOf(spec).garage;
    this.clearRace();
    this.garageWant = color;
    this.garageCar = visual;
    this.root.add(visual.root);
    visual.refresh();
    this.garageScale = view.scale;
    this.garageFocus.copy(p).addScaledVector(_f.set(Math.sin(this.track.headingAt(s)), 0, Math.cos(this.track.headingAt(s))), -view.focusBack);
    // showroom key light above and in front of the car
    const light = this.lights.showroom;
    this.lights.showroomOn = true;
    light.color.set('#fff1e0');
    light.position.copy(p).add(new THREE.Vector3(0, view.lightHeight, 0));
    light.target.position.copy(p);
    light.intensity = view.light;
    light.angle = 0.55;
    light.penumbra = 0.8;
    light.distance = 30;
    light.decay = 1.2;
    this.garageLift = 1.7;
    // (measured at the kind's scale, around the point the camera circles: a train's camera stands 22 m out, and a
    // bank there used to carry it 15 m up, looking down on the roof)
    this.garageViewYaw = this.garageSide(this.garageFocus, s, 0, view.scale);
    if (this.phase !== 'garage') {
      this.garageAngle = 0.6;
      this.garageOrbit = null;
    }
    this.emit({ type: 'garage', carId, color });
    this.setPhase('garage');
  }

  /**
   * World yaw from which the garage camera looks at `p` (on the road at `s`): from the uphill side, so that the
   * background is the valley and not the cutting. `turn` (rad) brings it round towards the front of what stands
   * there; `k` is the view's scale (the camera's distance).
   */
  private garageSide(p: THREE.Vector3, s: number, turn = 0, k = 1, lineup?: { swing: number; see: readonly THREE.Vector3[] }) {
    const r = this.track.getRight(Math.round(s), new THREE.Vector3());
    const up = this.terrain.heightAt(p.x + r.x * 14, p.z + r.z * 14) > this.terrain.heightAt(p.x - r.x * 14, p.z - r.z * 14) ? 1 : -1;
    const ahead = this.track.headingAt(s);
    // (the road's right is a quarter turn clockwise of its heading: towards the front is against that turn)
    const side = Math.atan2(r.x * up, r.z * up) + up * turn;
    // too steep a bank on that side (ridge courses) hides the car: take the first direction whose whole
    // camera swing stays clear of the terrain (other side, then along the road)
    const clear = (yaw: number) => {
      for (let j = -3; j <= 3; j++) {
        const a = yaw + (j / 3) * 0.75;
        for (const d of [2.5, 4, 5.5, 7, 8.6]) {
          // the sight line from the camera (1.7 m up at 8.6 m) to the car body (0.6 m); the ground clamp in
          // garageCamera() may lift the camera spot itself a little, but not onto a bank
          const sight = d >= 8.6 ? p.y + (this.garageLift - 0.4) * k : p.y + (0.6 + (this.garageLift - 0.6) * (d / 8.6)) * k;
          if (this.terrain.heightAt(p.x + Math.sin(a) * d * k, p.z + Math.cos(a) * d * k) > sight) return false;
        }
      }
      // a line-up is long: the camera has to see its two ends as well (half a metre above the road there)
      for (const t of lineup?.see ?? []) {
        for (let j = -2; j <= 2; j++) {
          const a = yaw + (j / 2) * lineup!.swing;
          const cx = p.x + Math.sin(a) * 8.6 * k, cz = p.z + Math.cos(a) * 8.6 * k, cy = p.y + this.garageLift * k;
          for (let i = 1; i < 12; i++) {
            const f = i / 12;
            if (this.terrain.heightAt(cx + (t.x - cx) * f, cz + (t.z - cz) * f) > cy + (t.y + 0.5 - cy) * f) return false;
          }
        }
      }
      return true;
    };
    return [side, side + Math.PI - 2 * up * turn, ahead, ahead + Math.PI].find(clear) ?? side;
  }

  /**
   * The online waiting room: every member's vehicle on the start grid in its paint (net/LobbyLineup.ts), in
   * place of the garage's single car, under the garage's camera (the slow swing, drag, wheel) and key light. Call it
   * again with every change of the room: a seat's model is swapped when its new one is ready. Anything else the game
   * is asked to show (`showGarage`, a race, the attract run, another course) takes the line-up away.
   */
  showLobby(entries: readonly LineupEntry[]) {
    // (a garage that is still waiting for its model does not come up over the line-up)
    this.asked++;
    const fresh = !this.lobby;
    if (!this.lobby) {
      this.clearRace();
      this.lobby = new LobbyLineup(this.track, { shadows: this.quality.shadows, compile: this.compileObject });
      this.lobby.setLamps(this.env.preset.lampsOn > 0.5 ? 1 : 0.5);
      this.root.add(this.lobby.group);
    }
    this.lobby.set(entries);
    const view = this.lobbyView;
    const { s, scale, radius } = this.lobby.frame(view.focus, view.ends[0], view.ends[1]);
    view.scale = scale;
    // one key light over them all: wide enough for the rows, as bright on the road as the garage's
    const h = Math.max(8, radius * 1.15);
    const light = this.lights.showroom;
    this.lights.showroomOn = true;
    light.color.set('#fff1e0');
    light.decay = 1.2;
    light.angle = 0.85;
    light.penumbra = 0.6;
    light.distance = 0;
    light.position.copy(view.focus).add(_v.set(0, h, 0));
    light.target.position.copy(view.focus);
    light.intensity = 8 * Math.pow(h, light.decay);
    this.garageLift = LINEUP_VIEW.lift;
    // the side the camera stands on, again with every change of the room: a longer line-up moves it further out,
    // where a bank that was out of its way may stand between it and the front row
    const was = this.garageViewYaw;
    this.garageViewYaw = this.garageSide(view.focus, s, LINEUP_VIEW.turn, view.scale, { swing: LINEUP_VIEW.swing, see: view.ends });
    // (a camera the player has dragged stays where they put it)
    if (!fresh && this.garageOrbit) this.garageOrbit.yaw += was - this.garageViewYaw;
    if (!fresh) return;
    this.garageFocus.copy(view.focus);
    this.garageScale = view.scale;
    this.garageAngle = 0.6;
    this.garageOrbit = null;
    this.setPhase('garage');
  }

  /** The waiting room's line-up, when it is up (what stands in each seat: tests, the name tags). */
  get lobbyState() {
    return this.lobby?.state() ?? null;
  }

  /**
   * Where a seat's name tag belongs on screen: x and y as shares of the canvas (from the top left) into `out`.
   * False when nothing stands there yet or it is behind the camera.
   */
  lobbyTag(slot: number, out: { x: number; y: number }): boolean {
    if (!this.lobby?.tagAnchor(slot, _v)) return false;
    _v.project(this.camera);
    if (_v.z < -1 || _v.z > 1) return false;
    out.x = _v.x * 0.5 + 0.5;
    out.y = 0.5 - _v.y * 0.5;
    return true;
  }

  startRace(cfg: RaceConfig) {
    if (!this.needs(this.raceVehicles(cfg), () => this.startRace(cfg))) return;
    this.clearRace();
    this.config = cfg;
    // online: everybody's place on the grid follows from the room alone, so every client agrees (net/grid.ts)
    const grid = cfg.online ? onlineGrid([{ slot: cfg.online.slot, carId: cfg.carId }, ...cfg.online.peers], this.track.startS, this.track.design.gridWidth) : null;
    const spot = grid?.get(cfg.online!.slot);
    // alone or against a rival: side by side, as far apart as the two are wide (a fighter's wings are 13–17 m
    // across), the longer nose a metre short of the line
    const mine = footprint(CAR_SPECS[cfg.carId]);
    const theirs = cfg.mode === 'rival' && cfg.rivalLevel ? footprint(CAR_SPECS[this.course.rivals[cfg.rivalLevel].car]) : null;
    const apart = theirs ? Math.max(2, (mine.width + theirs.width) / 4 + 0.6) : 0;
    const gridS = spot ? spot.s : this.track.startS - Math.max(6, mine.ahead + 1, (theirs?.ahead ?? 0) + 1);
    const lane = spot ? spot.lateral : apart;
    this.player = this.createRacer(cfg.carId, gridS, lane, {
      headlights: true,
      // the colour picked in the car select; online the member's paint as the room has it, the seat's colour without
      // one (the seat's colour stays their mark in the tags and the HUD)
      color: cfg.online ? paintFor(cfg.carId, cfg.color, cfg.online.slot) : cfg.color,
    });
    // a train: the high chase, and its first race starts in the cab view
    const train = !!CAR_SPECS[cfg.carId].train;
    const t = CAR_SPECS[cfg.carId].train;
    // the cab view sits just behind the nose of the leading car
    this.chase.profile = t ? { ...TRAIN_CAMERA, front: { ...TRAIN_CAMERA.front, ahead: trainNose(t) - 0.35 } } : CAR_SPECS[cfg.carId].bike ? BIKE_CAMERA : CAR_SPECS[cfg.carId].jet ? JET_CAMERA : CAR_CAMERA;
    if (train !== this.cameraForTrain) this.chase.mode = train ? 'bumper' : 'chase';
    this.cameraForTrain = train;
    if (cfg.online) {
      this.remotes.setPeers(cfg.online.peers, (slot) => {
        const g = grid!.get(slot)!;
        return { position: this.track.pointAt(g.s, g.lateral), heading: this.track.headingAt(g.s) };
      });
      this.remotes.setHeadlights(this.env.preset.lampsOn > 0.5 ? 1 : 0.6);
      // other players are solid: physical stand-ins the local car can bump into
      this.remotes.enablePhysics(this.physics);
      this.remotes.timeScale = this.timeScale;
      this.net.selfId = this.onlineSelfId;
      this.netSendT = 0;
      this.simRate = this.timeScale;
      this.netUrgent = false;
      this.netEpoch = 0;
      this.netAcc.set(0, 0, 0);
      this.netVel.set(0, 0, 0);
    }
    this.player.sim.autoShift = this.autoShift;
    if (cfg.mode === 'rival' && cfg.rivalLevel) {
      const rival = this.course.rivals[cfg.rivalLevel];
      this.rival = this.createRacer(rival.car, gridS, -apart, { ai: cfg.rivalLevel, headlights: true, color: rival.color, rival: true });
      this.rival.sim.powerScale = rival.power ?? 1;
      const ai = this.rival.ai;
      this.mind = new RivalMind({
        rival: { name: rival.name, title: rival.title, description: rival.description },
        level: cfg.rivalLevel,
        brains: this.rivalBrains,
        seed: (Date.now() & 0xffff) | 1,
        onBlock: (seconds) => ai?.block(seconds),
        onHorn: (style) => this.rivalHorn(style),
      });
      this.rivalSays('before');
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
    this.hud.jet = !!CAR_SPECS[cfg.carId].jet;
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
      this.audio.engine('player', this.player.sim.spec);
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
    const real = performance.now(), next = this.wall + dtRaw * 1000;
    this.wall = Math.abs(real - next) > 50 ? real : next + (real - next) * 0.05;

    if (this.input.menuPressed('camera')) this.chase.cycle();
    if (this.hud.rivalLine && this.time > this.lineUntil) this.hud.rivalLine = null;

    if (!this.paused) {
      this.step(dt, dtRaw);
    }
    this.updateVisuals(dt);
    this.env.update(this.time, this.camera.position, this.camera.getWorldDirection(_f));
    lampsAround(this.camera.position);
    this.rain.update(this.time, this.camera.position, this.player?.sim.velocity ?? _zero);
    this.scenery.update(this.time, this.camera.position, this.camera);
    this.updateBeams();
  }

  private beamPool = Array.from({ length: VOLUME_SPOTS }, volumeSpot);
  private beamCars: CarVisual[] = [];
  /**
   * The cars with their headlights on, the one the camera is with first and the others by their distance from it:
   * the first few light the road (the pooled spots), their cones glow in the haze.
   */
  private updateBeams() {
    const cars = this.beamCars;
    cars.length = 0;
    const first = this.phase === 'garage' ? this.garageCar : (this.player?.visual ?? this.attractCar?.visual ?? this.replay?.cars[0]?.visual);
    if (this.rival) cars.push(this.rival.visual);
    if (this.replay) for (const c of this.replay.cars) if (c.visual !== first) cars.push(c.visual);
    this.remotes?.forEachExhaust((visual) => void cars.push(visual));
    const cam = this.camera.position;
    if (cars.length > 1) cars.sort((a, b) => a.root.position.distanceToSquared(cam) - b.root.position.distanceToSquared(cam));
    if (first) cars.unshift(first);
    this.lights.beams(cars);
    const spots = volume.spots;
    spots.length = 0;
    // (a cone from each lamp: two for a car, as long as there is room)
    let used = 0;
    for (const visual of cars) {
      if (used >= this.beamPool.length) break;
      used += visual.beamsInto(this.beamPool, used);
    }
    for (let k = 0; k < used; k++) spots.push(this.beamPool[k]);
  }

  private racers(): Racer[] {
    return [this.player, this.rival, this.attractCar].filter((r): r is Racer => !!r);
  }

  private step(dt: number, dtRaw: number) {
    const phase = this.phase;
    // ---- input / AI
    if (this.player) {
      if (phase === 'racing') {
        if (this.player.finished || this.autoDrive) {
          // AI-controlled player (after the finish, or autodrive testing) — see driveAI
        } else {
          this.input.poll(dt, this.player.input);
          if (this.input.menuPressed('reset')) this.respawn(this.player);
          if (this.input.menuPressed('horn')) this.audio?.horn('short');
        }
      } else if (phase === 'countdown') {
        // allow revving on the line, but hold the car
        const tmp = this.input.poll(dt, emptyInput());
        this.player.input.throttle = tmp.throttle;
        this.player.input.brake = 0;
        this.player.input.steer = 0;
        this.player.input.handbrake = true;
      }
    }
    // every car is held on the line until the green light
    for (const r of this.racers()) r.input.hold = phase === 'countdown';

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
      // the stand-ins of the other players' cars go where those cars are at the moment this step ends at
      if (this.config?.online) this.remotes.stepProxies(this.wall - ((this.accumulator - PHYSICS_DT) / this.timeScale) * 1000, this.wall, this.player?.sim.position ?? null);
      this.physics.step();
      for (const r of racers) r.sim.postStep(PHYSICS_DT);
      if (this.config?.online && this.player) {
        const v = this.player.sim.velocity;
        // a hit (wall, another car) is no trend to carry on, but news the peers cannot guess: it goes out at once
        if (this.player.sim.impact > 0) this.netUrgent = true;
        else this.netAcc.lerp(_v.subVectors(v, this.netVel).divideScalar(PHYSICS_DT).clampLength(0, 40), 1 - Math.exp(-PHYSICS_DT / NET_ACC_TAU));
        this.netVel.copy(v);
      }
      this.detectCarContact();
      this.simTime += PHYSICS_DT;
      if (this.phase === 'racing' || this.phase === 'finished') this.raceStep();
      this.accumulator -= PHYSICS_DT;
      steps++;
    }
    if (steps === maxSteps) this.accumulator = 0;
    this.stateWall = this.wall - (this.accumulator / this.timeScale) * 1000;
    // how fast the physics really runs against the wall clock: the time scale, unless this machine cannot keep up
    // (under 15 fps the steps of a frame are capped and the race runs in slow motion)
    if (dtRaw > 0) this.simRate += ((steps * PHYSICS_DT) / dtRaw - this.simRate) * (1 - Math.exp(-dtRaw / 0.5));
    if (this.config?.online) {
      // sent here, straight after the physics, so a state is as fresh as it can be when it leaves
      this.netSendT += dt / this.timeScale;
      if (this.netUrgent || this.netSendT >= NET_SEND_INTERVAL - 0.002) {
        this.netSendT = this.netUrgent ? 0 : Math.min(this.netSendT - NET_SEND_INTERVAL, NET_SEND_INTERVAL);
        this.netUrgent = false;
        const st = this.netState();
        if (st) this.net.send(st);
      }
    }

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
      if (pl.finished && pl.sim.spec.jet) this.depart(pl, dt);
      else if (pl.finished) this.autopilot(pl, dt);
      else if (this.autoDrive) this.autoDriver(pl, dt);
    }
    for (const r of [this.rival, this.attractCar]) {
      if (!r || !r.ai) continue;
      if (phase === 'countdown') {
        r.input.throttle = 0.3;
        r.input.brake = 0;
        r.input.handbrake = true;
        continue;
      }
      if (pl && r === this.rival) r.ai.opponent = { s: pl.proj.s, lateral: pl.proj.lateral, speed: pl.sim.forwardSpeed };
      if (r.finished && r.sim.spec.jet) {
        this.depart(r, dt);
        continue;
      }
      if (r.finished && r.ai.pullOver === null) r.ai.pullOver = r.proj.lateral >= 0 ? 10 : -10;
      r.ai.update(r.sim, dt, r.input);
      if (r.finished) {
        // pull over to its side and stop; once slow, hold it with the handbrake and a light foot brake
        // (VehicleSim engages reverse when the brake is held above 0.3 at a standstill)
        r.input.throttle = 0;
        r.input.brake = r.sim.forwardSpeed > 1.5 ? this.stopBrake(r, 0.4, dt) : 0.25;
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

  /**
   * A fighter past the line leaves by air (`race/Departure.ts`). The ground run is the simulation's own: the game
   * holds it straight where it is (no swerve back to the middle at 800 km/h) in full afterburner; from the rotation
   * speed on, once it runs straight, it is carried along the take-off, and taken off the scene when it is away.
   */
  private depart(r: Racer, dt: number) {
    const d = (r.departure ??= new Departure(r.sim.spec));
    const sim = r.sim;
    if (d.stage === 'gone') return;
    if (d.stage !== 'roll') {
      d.step(dt);
      sim.carry(d.position, d.quaternion, { spool: 1, afterburner: 1 });
      return;
    }
    d.step(dt);
    if (!r.ai) {
      r.ai = new AIDriver(this.track, this.line, AI_PROFILES.rookie, 3);
      r.ai.calibrate(sim);
    }
    if (r.ai.pullOver === null) r.ai.pullOver = r.proj.lateral;
    r.ai.opponent = null;
    r.ai.update(sim, dt, r.input);
    r.input.throttle = 1;
    r.input.brake = 0;
    r.input.handbrake = false;
    const heading = Math.atan2(sim.forward.x, sim.forward.z);
    const straight = Math.abs(wrapAngle(heading - this.track.headingAt(r.proj.s))) < 0.035 && Math.abs(sim.yawRate) < 0.03 && Math.abs(sim.slipAngle) < 0.035;
    // (the lake goes on past the end of the course: whoever is not straight by then goes as it is)
    const room = this.track.length - 200 - r.proj.s;
    if ((sim.forwardSpeed >= sim.spec.jet!.vr && straight && d.t > 0.8) || room < 0) {
      d.rotate(sim.position, heading, sim.speed);
      // (this step's travel at once: handed over where it stands, the body stood still for a step, its velocity
      // read zero, and that went to the other players as a hit: they saw the aircraft stop for a packet and jump on)
      d.step(dt);
      sim.carry(d.position, d.quaternion, { spool: 1, afterburner: 1 });
    }
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
    // to a standstill: a light foot brake and the handbrake once slow (above 0.3 at a standstill VehicleSim engages
    // reverse; coasting instead, a train rolled on for a minute and met the end of the road)
    const slow = r.sim.forwardSpeed <= 1.5;
    r.input.brake = slow ? 0.25 : this.stopBrake(r, 0.35, dt);
    r.input.handbrake = slow;
  }

  /**
   * Brake input for a car past the finish line: at least `gentle`, harder when the road left would not be enough to
   * stop on. A train's brakes (~1 m/s²) cannot stop it from 300 km/h on any run-off: past the line a retarder takes
   * off what they lack, so nothing reaches the end of the road at speed.
   */
  private stopBrake(r: Racer, gentle: number, dt: number) {
    const v = r.sim.forwardSpeed;
    const room = Math.max(5, this.track.length - 40 - r.proj.s);
    const need = (v * v) / (2 * room);
    const spec = r.sim.spec;
    const brakes = Math.min(spec.brakeForce / spec.mass, Math.min(spec.gripFront, spec.gripRear) * 9.81 * 0.8);
    if (need > brakes) {
      const lv = r.sim.body.linvel();
      const k = Math.max(0, 1 - ((need - brakes) * dt) / Math.max(v, 1));
      r.sim.body.setLinvel({ x: lv.x * k, y: lv.y, z: lv.z * k }, true);
    }
    return clamp(Math.max(gentle, need / brakes), 0, 1);
  }

  private trackRacer(r: Racer, dt: number) {
    const p = r.sim.position;
    r.proj = this.track.project(p.x, p.y, p.z, r.proj.index, r.proj);
    const onRoad = Math.abs(r.proj.lateral) < this.track.width[r.proj.index] / 2 + 1 && Math.abs(r.proj.height) < 3;
    const design = this.track.design;
    // what the tyres stand on: a zone's own ground (a dry lake's clay), the open ground beside a pavement
    if (design.zoneGrip || design.verge) {
      r.sim.gripScale = this.roadGrip * this.track.surfaceGrip(r.proj.index, r.proj.lateral, p.x, p.z);
      r.sim.rollScale = this.track.surfaceRoll(r.proj.index, r.proj.lateral, p.x, p.z);
    }
    // a course without barriers: whoever reaches the edge of the ground it gives is put back on it
    const strayed = !!design.verge && Math.abs(r.proj.lateral) > this.track.width[r.proj.index] / 2 - 2;
    if (onRoad && !r.sim.isFlipped && r.sim.speed > 2) r.lastSafe = { s: r.proj.s, t: this.time };
    // automatic recovery
    if (r.sim.isFlipped) r.flippedTime += dt;
    else r.flippedTime = 0;
    const lost = Math.abs(r.proj.height) > 12 || r.sim.position.y < -20;
    // (an aircraft in the air is where it should be)
    if (r.sim.carried) return;
    // (a finished rival parks on purpose: not stuck)
    if (r.flippedTime > 2 || lost || strayed || (r.ai && r.ai.needsRespawn && r !== this.player && !r.finished)) this.respawn(r);
  }

  private respawn(r: Racer) {
    const s = clamp(Math.min(r.lastSafe.s, r.proj.s) - 4, 5, this.track.length - 20);
    const lat = clamp(this.line.offsetAt(s), -2, 2);
    r.sim.reset(this.track.pointAt(s, lat), this.track.headingAt(s), 0);
    r.proj.index = -1;
    r.flippedTime = 0;
    // a respawned car may land inside another player's car: ghost them until clear
    if (r === this.player && this.config?.online) {
      this.remotes.ghostAll(this.wall + 1500);
      // the peers put the car here instead of easing it over
      this.netEpoch = (this.netEpoch + 1) & 3;
      this.netAcc.set(0, 0, 0);
      this.netVel.copy(r.sim.velocity);
    }
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
      if (this.mind && this.phase === 'racing' && !pl.finished && !this.rival.finished) this.mind.update(raceTime, () => this.rivalSituation());
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

  /**
   * The local car for the other players (online battles): the latest physics state with the moment it is of.
   * Rates are per wall-clock second (they differ from the physics' own under a time scale, a test aid, and on a
   * machine too slow to run the physics in real time).
   */
  netState(): LocalState | null {
    const pl = this.player;
    if (!pl || !this.config?.online || (this.phase !== 'countdown' && this.phase !== 'racing' && this.phase !== 'finished')) return null;
    const p = pl.sim.position, q = pl.sim.quaternion, v = pl.sim.velocity, w = pl.sim.body.angvel(), a = this.netAcc;
    // (the smoothed rate ripples with the frame rate: within a tenth of the time scale it is the time scale)
    const ts = Math.abs(this.simRate / this.timeScale - 1) < 0.1 ? this.timeScale : this.simRate;
    const st: LocalState = {
      at: this.stateWall,
      p: [p.x, p.y, p.z],
      q: [q.x, q.y, q.z, q.w],
      vel: [v.x * ts, v.y * ts, v.z * ts],
      acc: [a.x * ts * ts, a.y * ts * ts, a.z * ts * ts],
      w: [w.x * ts, w.y * ts, w.z * ts],
      st: pl.sim.wheels[0]?.steer ?? 0,
      s: pl.proj.s,
      br: pl.sim.input.brake > 0.2 ? 1 : 0,
      ep: this.netEpoch,
      th: pl.sim.input.throttle,
      rp: clamp(pl.sim.rpm / pl.sim.spec.engine.redline, 0, 1),
    };
    // a fighter's take-off after the finish: the others draw its gear by it, and cannot touch it any more
    const d = pl.departure;
    if (d && d.stage !== 'roll') st.dep = d.stage === 'gone' ? 3 : d.gear > 0 ? 2 : 1;
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
    if (this.rival) {
      // the gap at the line; a rival still on its way: what it has left at the pace it is running
      const r = this.rival;
      const behind = (this.track.finishS - r.proj.s) / Math.max(r.sim.forwardSpeed, 15);
      this.rivalSays(result.rivalWon ? 'won' : 'lost', rivalTime === undefined ? Math.max(0, behind) : Math.abs(rivalTime - pl.finishTime));
    }
    this.setPhase('finished');
    this.emit({ type: 'finish', result });
  }

  // ------------------------------------------------------------- the rival's lines and moves
  /** The race as the rival sees it: the numbers a brain decides on (`ai/RivalMind.ts`). */
  private rivalSituation(): Situation {
    const pl = this.player!, r = this.rival!;
    const ahead = r.proj.s >= pl.proj.s;
    const front = ahead ? r : pl, back = ahead ? pl : r;
    return {
      level: this.config!.rivalLevel!,
      remaining_m: Math.max(0, this.track.finishS - r.proj.s),
      rival_ahead: ahead,
      gap_m: Math.abs(r.proj.s - pl.proj.s),
      closing_kmh: (back.sim.forwardSpeed - front.sim.forwardSpeed) * 3.6,
      // (the track's lateral is + to the right)
      lateral_m: r.proj.lateral - pl.proj.lateral,
      corner: cornerAhead(this.corners, r.proj.s),
      blocks: 0,
      horns: 0,
    };
  }

  /** The rival's horn, as loud as it is near. */
  private rivalHorn(style: Horn) {
    const r = this.rival;
    if (!r || !this.audio) return;
    const d = r.sim.position.distanceTo(this.camera.position);
    this.audio.horn(style, clamp(1 - d / 150, 0.2, 1), 0.92);
  }

  /**
   * A line from the rival: `before` the start (shown on the HUD if it comes while the race is still young), or
   * once it has `won` or `lost` (kept for the results). `gap`: seconds between the two at the line.
   */
  private rivalSays(moment: Moment, gap?: number) {
    const mind = this.mind, cfg = this.config, r = this.rival;
    if (!mind || !cfg || !r) return;
    const record = cfg.rivalRecord ?? { wins: 0, losses: 0, medal: 'none' as const };
    void mind
      .taunt({ course: this.course.id, tod: this.timeOfDay, player_car: cfg.carId, rival_car: r.sim.spec.id, ...record, moment, gap_s: gap })
      .then((text) => {
        if (this.mind !== mind || !text) return;
        const show = () => {
          if (this.mind !== mind) return 0;
          if (moment === 'before' && !(this.phase === 'countdown' || (this.phase === 'racing' && this.raceClock() < 3))) return 0;
          this.hud.rivalLine = { text, moment, seq: ++this.lineSeq };
          this.lineUntil = moment === 'before' ? this.time + 5.5 * this.timeScale : Infinity;
          this.emit({ type: 'rivalLine', moment, text });
          return this.lineSeq;
        };
        const sound = this.rivalVoice?.(text, this.course.rivals[cfg.rivalLevel ?? 'rookie'].voice).catch(() => null);
        if (!sound) return void show();
        // The line and its voice come together when the voice is quick (a quarter of a second on a desktop GPU);
        // a slow one joins the line that is already shown, as long as it still is.
        let seq = -1;
        const late = setTimeout(() => (seq = show()), VOICE_WAIT);
        void sound.then((s) => {
          clearTimeout(late);
          if (seq < 0) seq = show();
          if (!s || !seq || this.hud.rivalLine?.seq !== seq || !this.audio) return;
          const seconds = this.audio.say(s.pcm, s.rate);
          // (a line before the start stays until it has been said)
          if (moment === 'before') this.lineUntil = Math.max(this.lineUntil, this.time + (seconds + 0.8) * this.timeScale);
        });
      });
  }

  // ------------------------------------------------------------- visuals
  private updateVisuals(dt: number) {
    const alpha = clamp(this.accumulator / PHYSICS_DT, 0, 1);
    for (const r of this.racers()) {
      r.visual.syncFromSim(r.sim, this.paused ? 1 : alpha, dt);
      if (r.departure) {
        r.visual.rig.jet?.setGear(r.departure.gear);
        r.visual.rig.jet?.setPitch(r.departure.elevator);
        r.visual.root.visible = r.departure.stage !== 'gone';
      }
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
      // the local car is drawn one physics step behind the frame's moment (the interpolation between its last two
      // states): the others at that same moment
      this.remotes.update(this.wall - (PHYSICS_DT / this.timeScale) * 1000, dt);
      if (!this.paused) this.remotes.forEachExhaust((visual, fx, state) => this.emitExhaustFromPose(visual, state, fx.speed, dt, fx.th, fx.rp));
    }
    if (!this.paused) {
      this.smoke.update(dt);
      this.exhaust.update(dt);
    }

    // ---- camera
    if (this.phase === 'attract' && this.attractCar) this.cinematicCamera(dt, this.attractCar.visual.root, this.attractCar.proj.s);
    else if (this.phase === 'replay' && this.replay) this.updateReplay(dt);
    else if (this.phase === 'garage' && (this.garageCar || this.lobby)) this.garageCamera(dt);
    else if (this.player?.departure && this.player.departure.stage !== 'roll') this.departureCamera(dt, this.player);
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
        lean: this.player.visual.lean,
      });
    }
    // (the garage's clearing among the trees closes with any other view; its own statement: written into the
    // chain above it cut the race camera off, and the car drove away from a camera left at the garage)
    if (this.phase !== 'garage') clearing.value.z = -10;
    if (this.spy) {
      this.camera.position.copy(this.spy.from);
      this.camera.lookAt(this.spy.at);
    }

    // ---- HUD + audio
    if (this.player) {
      const sim = this.player.sim;
      this.hud.speedKmh = Math.abs(sim.forwardSpeed) * 3.6;
      this.hud.rpm = sim.rpm;
      this.hud.gear = sim.gear;
      this.hud.boost = sim.boost;
      this.hud.afterburner = sim.afterburner;
      // camera shake and contact bookkeeping must run with or without sound
      if (!this.paused) this.carContactFeedback(dt);
      if (this.audio && !this.paused) {
        const e = this.audio.engine('player', sim.spec);
        if (e.blowOff(sim.input.throttle, sim.boost)) this.audio.blowOff();
        // a train's sound follows its tractive effort (it builds up after a notch-on, as in VehicleSim)
        // a train's flanges squeal in tight curves (lateral acceleration = yaw rate × speed)
        if ('cornering' in e) e.cornering(sim.yawRate * sim.forwardSpeed);
        // a creature's wings are heard as far as they are out (thrown into the air)
        if ('flight' in e) e.flight(this.player.visual.flight);
        // a fighter leaving after the finish is heard going away, and not at all once it is gone
        const away = this.player.departure;
        if ('distance' in e) e.distance(away && away.stage !== 'roll' ? this.player.visual.root.position.distanceTo(this.camera.position) : 0);
        if (away?.stage === 'gone') e.update(sim.rpm, 0, 0, 0, sim.spec.engine.redline);
        else e.update(sim.rpm, sim.spec.train ? sim.traction : sim.input.throttle, sim.boost, 1, sim.spec.engine.redline, sim.input.brake);
        let skid = 0;
        for (const w of sim.wheels) if (w.grounded) skid = Math.max(skid, w.skid);
        this.audio.updateTyres(skid, sim.speed);
        this.audio.updateWind(sim.speed);
        if (sim.impact > 0.15) this.audio.impact(Math.min(1, sim.impact * 1.5));
        if (this.rival) {
          const re = this.audio.engine('rival', this.rival.sim.spec);
          const d = this.rival.sim.position.distanceTo(this.camera.position);
          // (a fighter's engines carry their own fall-off with the distance, far beyond a car's 140 m)
          if ('distance' in re) re.distance(d);
          if ('distance' in re) re.update(this.rival.sim.rpm, 0, 0, this.rival.departure?.stage === 'gone' ? 0 : 0.8, 0);
          else re.update(this.rival.sim.rpm, this.rival.input.throttle, this.rival.sim.boost, clamp(1 - d / 140, 0, 1) * 0.8, this.rival.sim.spec.engine.redline);
          if ('flight' in re) re.flight(this.rival.visual.flight);
        }
      }
    } else if (this.audio && this.attractCar && this.phase === 'attract') {
      const sim = this.attractCar.sim;
      const e = this.audio.engine('attract', sim.spec);
      const d = sim.position.distanceTo(this.camera.position);
      if ('distance' in e) e.distance(d);
      e.update(sim.rpm, sim.input.throttle, sim.boost, clamp(1 - d / 160, 0, 1) * 0.5, sim.spec.engine.redline);
    }
    // the rain as heard from the player's vehicle (its speed, a roof over it, what the drops land on); in the menus
    // from the camera, with no body under the rain
    if (this.audio && this.env?.preset.rain) {
      const sim = this.player?.sim;
      const at = sim ? sim.position : this.camera.position;
      const cover = this.scenery ? coverShare(this.scenery.covers, at.x, at.y + 1.2, at.z) : 0;
      this.audio.updateRain(sim && !this.paused ? sim.speed : 0, cover, sim ? rainBodyOf(kindOf(sim.spec)) : 'none');
    }
  }

  /** Exhaust puffs and backfires from the tailpipe (with a pop when the camera is close). */
  private emitExhaust(r: Racer, dt: number) {
    const sim = r.sim;
    const rpm = clamp(sim.rpm / sim.spec.engine.redline, 0, 1);
    const throttle = sim.gear === -1 ? 0.2 : sim.input.throttle;
    this.puff(r.visual, r.exhaust, sim.velocity, throttle, rpm, dt);
  }

  /**
   * Exhaust of a car known only by its pose (online peers, replays): the throttle and engine speed are sent by
   * peers; otherwise they are read from the speed change (pulling away = throttle, a hard slow-down = lifted).
   */
  private emitExhaustFromPose(visual: CarVisual, state: ExhaustState & { speed: number }, speed: number, dt: number, throttle?: number, rpm?: number) {
    const accel = dt > 0 ? (speed - state.speed) / dt : 0;
    state.speed = speed;
    const th = throttle ?? (accel > 0.4 ? 1 : accel > -1 ? 0.3 : 0);
    const rp = rpm ?? clamp(0.3 + speed / 70, 0.3, 1);
    _v.set(0, 0, 1).applyQuaternion(visual.root.quaternion).multiplyScalar(speed);
    this.puff(visual, state, _v, th, rp, dt);
  }

  /** Puffs and backfires from a car's tailpipe (with a pop when the camera is close). */
  private puff(visual: CarVisual, state: ExhaustState, velocity: THREE.Vector3, throttle: number, rpm: number, dt: number) {
    if (!hasExhaust(visual.spec)) return;
    const rig = visual.rig, root = visual.root;
    // tailpipe in world space from the car's pose (the model only sits lower by the ride height)
    _tip.copy(rig.anchors.exhaust).add(rig.root.position).applyQuaternion(root.quaternion).add(root.position);
    _back.set(0, 0, -1).applyQuaternion(root.quaternion);
    const bang = this.exhaust.emit(state, _tip, _back, velocity, throttle, rpm, visual.spec.engine.turbo, dt);
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
      return { player: new GhostPlayer(data), visual, wheelRot: 0, last: new THREE.Vector3(), exhaust: { ...newExhaustState(), speed: 0 } };
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
      // (a jump back to the start when the replay loops is no speed)
      if (dt > 0 && moved < 5) this.emitExhaustFromPose(c.visual, c.exhaust, moved / dt, dt);
      if (i === 0) rp.proj = this.track.project(_v.x, _v.y, _v.z, rp.proj.index, rp.proj);
    });
    this.cinematicCamera(dt, rp.cars[0].visual.root, rp.proj.s);
  }

  /**
   * The take-off is watched from the lake: a camera standing beside the path where the aircraft leaves the ground,
   * a man's height up, that turns with it and closes in as it climbs away (the chase camera would hang behind a
   * tail going up at 30°, looking at the sky).
   */
  private departureCamera(dt: number, r: Racer) {
    const d = r.departure!;
    const cam = this.camera;
    const at = r.visual.root.position;
    if (!this.departEye) {
      const f = r.sim.forward, ahead = clamp(d.speed * 3, 240, 800);
      const eye = (this.departEye = new THREE.Vector3(at.x + f.x * ahead - f.z * 42, 0, at.z + f.z * ahead + f.x * 42));
      eye.y = this.terrain.heightAt(eye.x, eye.z) + 1.8;
      this.departAim.copy(at);
    }
    this.departAim.lerp(at, 1 - Math.exp(-dt * 30));
    cam.position.copy(this.departEye);
    cam.lookAt(this.departAim.x, this.departAim.y + 1.5, this.departAim.z);
    // the results card stands in the middle of the screen: the aircraft climbs through the free upper part of the
    // picture, a seventh of its height from the top (the card's title begins at three tenths). An online battle's
    // results stand in the upper half (an eighth to under a half): there it climbs through the lower part, seven
    // tenths down, the sky all around it
    cam.rotateX(((this.config?.online ? 0.2 : -0.36) * cam.fov * Math.PI) / 180);
    // a long lens as it goes away: the aircraft keeps about a fifth of the picture's width for the first 2.5 km
    const fov = clamp((2 * Math.atan(20 / Math.max(cam.position.distanceTo(at), 1)) * 180) / Math.PI, 0.9, 58);
    cam.fov = damp(cam.fov, fov, 3.5, dt);
    cam.updateProjectionMatrix();
  }
  private departEye: THREE.Vector3 | null = null;
  private departAim = new THREE.Vector3();

  get replayTime() {
    return this.replay?.t ?? 0;
  }

  /**
   * The camera of the title and of the replay: four shots in turn. Every one of them stands over the road or where
   * the ground lets it see the road: a camera placed by an offset from the car alone ended up inside a slope, behind
   * a mound or with a post of the roadside across the picture.
   */
  /**
   * Probe: stand at `s` metres along the road, `side` metres to the left of its middle and `up` above it, and look
   * at the place given the same way (`null`: the game's own camera again).
   */
  lookFrom(from: [number, number, number] | null, at: [number, number, number] = [0, 0, 0]) {
    if (!from || !this.track) return void (this.spy = null);
    const place = ([s, side, up]: [number, number, number]) => {
      const p = this.track!.pointAt(s, side, new THREE.Vector3());
      p.y += up;
      return p;
    };
    this.spy = { from: place(from), at: place(at) };
  }

  private cinematicCamera(dt: number, root: THREE.Object3D, trackS: number) {
    const c = this.cinematic;
    c.t += dt;
    // (a menu holds a shot of its own: the turn of the four goes on underneath and is there again afterwards)
    const shot = this.phase === 'attract' && this.menuShot === 'sky' ? 4 : c.shot;
    const car = root.position;
    const track = this.track;
    const shots = 4;
    if (c.t > 7) {
      c.t = 0;
      c.shot = (c.shot + 1) % shots;
      // the standing camera of the pan: ahead of the car
      if (c.shot === 1) this.tracksideAnchor(trackS + 70, c.anchor);
      // (the swing: from ahead of the car this time, from behind it the next)
      if (c.shot === 0) c.fore = -c.fore;
    }
    // how far from the centre line a camera may stand and still be on the road, inside the rails
    const inside = (s: number) => Math.max(1.2, track.widthAt(s) / 2 - 0.7);
    const cam = this.camera;
    // The shots that travel with the car are carried along by its own movement first, and eased only in what is
    // left: eased towards a place ahead of a fast car, the camera fell back by speed / rate (five metres at
    // 140 km/h) and the low front shot looked down on the bonnet from above it.
    if (shot !== 1 && shot !== 3 && c.last.distanceToSquared(car) < 25) cam.position.add(_v.subVectors(car, c.last));
    c.last.copy(car);
    let fov = 45;
    switch (shot) {
      case 0: {
        // a slow swing along the road, from ahead of the car (or behind it) to beside it, on the side of the car
        // where the road has room, and never nearer than five metres: a full orbit as wide as the road stood right
        // over a car that drove along its edge (a picture of a roof, six seconds into the title), and on a narrow
        // road there is no room beside a car at all
        track.pointAt(trackS, 0, _v);
        track.pointAt(trackS, 1, _w);
        const lateral = (car.x - _v.x) * (_w.x - _v.x) + (car.z - _v.z) * (_w.z - _v.z);
        if (lateral * c.side > 0.3) c.side = -c.side;
        const a = this.time * 0.25;
        const room = inside(trackS);
        const gap = Math.abs(clamp(lateral + c.side * Math.abs(Math.sin(a)) * 6, -room, room) - lateral);
        const s = trackS + c.fore * Math.max(Math.abs(Math.cos(a)) * 9, Math.sqrt(Math.max(0, 27 - gap * gap)));
        track.pointAt(s, clamp(lateral + c.side * gap, -inside(s), inside(s)), c.pos);
        // (beside the car it is only half a road away: higher there, so that the whole car is in the picture)
        c.pos.y = Math.max(c.pos.y, car.y) + 1.7 + 2.6 * Math.abs(Math.sin(a));
        cam.position.lerp(c.pos, 1 - Math.exp(-dt * 6));
        cam.lookAt(car.x, car.y + 0.6, car.z);
        fov = 52;
        break;
      }
      case 1: {
        // trackside pan
        if (c.anchor.lengthSq() === 0) this.tracksideAnchor(trackS + 70, c.anchor);
        cam.position.copy(c.anchor);
        cam.lookAt(car.x, car.y + 0.6, car.z);
        fov = clamp(40 - c.anchor.distanceTo(car) * 0.1, 18, 40);
        // the car went behind the hill, or far down the road (small, and behind the trees): on to the next shot
        if (c.t > 1.5 && (trackS > c.anchorS + 80 || !this.groundClear(c.anchor.x, c.anchor.y, c.anchor.z, car.x, car.y + 0.8, car.z))) c.t = 7;
        break;
      }
      case 2: {
        // low front three-quarter tracking shot: ahead of the car and beside its lamps' cones (inside them their
        // glow in the haze whitens the picture), on the side where the road has room
        track.pointAt(trackS, 0, _v);
        track.pointAt(trackS, 1, _w);
        const lateral = (car.x - _v.x) * (_w.x - _v.x) + (car.z - _v.z) * (_w.z - _v.z);
        if (lateral * c.side > 0.3) c.side = -c.side;
        const s = trackS + 5.5;
        const off = clamp(lateral + c.side * 3.2, -inside(s), inside(s));
        track.pointAt(s, off, c.pos);
        // (where the road leaves less room beside the cones: over them)
        c.pos.y = Math.max(c.pos.y + 0.45, car.y) + 0.6 + Math.max(0, 2.4 - Math.abs(off - lateral)) * 1.1;
        cam.position.lerp(c.pos, 1 - Math.exp(-dt * 8));
        cam.lookAt(car.x, car.y + 0.5, car.z);
        fov = 50;
        break;
      }
      case 4: {
        // the conditions screen: behind the car and beside it, at a driver's height, looking down the road. What a
        // time of day and its weather look like is the sky, the lamps and the road ahead, not a car from above.
        track.pointAt(trackS, 0, _v);
        track.pointAt(trackS, 1, _w);
        const lateral = (car.x - _v.x) * (_w.x - _v.x) + (car.z - _v.z) * (_w.z - _v.z);
        const s = trackS - 7.5;
        // (on the car's left: the car stands right of the middle, clear of the screen's list)
        track.pointAt(s, clamp(lateral - 2.6, -inside(s), inside(s)), c.pos);
        c.pos.y = Math.max(c.pos.y, car.y) + 2.2;
        cam.position.lerp(c.pos, 1 - Math.exp(-dt * 5));
        track.pointAt(trackS + 38, 0, _v);
        c.look.lerp(_w.set(_v.x, Math.max(_v.y, car.y - 1.5) + 2.4, _v.z), c.look.lengthSq() === 0 ? 1 : 1 - Math.exp(-dt * 2.5));
        cam.lookAt(c.look);
        fov = 56;
        break;
      }
      default: {
        // high wide shot showing the valley and the city: over the road behind the car
        track.pointAt(trackS - 24, 0, c.pos);
        c.pos.y = Math.max(c.pos.y, car.y) + 16;
        cam.position.lerp(c.pos, 1 - Math.exp(-dt * 2));
        track.pointAt(trackS + 40, 0, _v);
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

  /**
   * Where a camera stands beside the road at `s` to watch a car come past: of a few places on either side (out on
   * the verge, nearer and higher, at last on the shoulder) the one from which the ground hides least of the road
   * before and after it.
   */
  private tracksideAnchor(s: number, out: THREE.Vector3) {
    const track = this.track;
    this.cinematic.anchorS = s;
    const half = track.widthAt(s) / 2;
    let best = -Infinity;
    for (const side of [1, -1]) {
      // (high enough to look over the bushes of the verge, which the ground's heights do not know)
      for (const [off, up, liked] of [[4, 3.3, 0], [2.4, 4.2, -1], [-0.5, 1.6, -4]]) {
        track.pointAt(s, (half + off) * side, _v);
        const x = _v.x, z = _v.z;
        const want = _v.y + up;
        const y = Math.max(want, this.terrain.heightAt(x, z) + 1.3);
        let seen = 0;
        for (let ds = -70; ds <= 90; ds += 10) {
          track.pointAt(s + ds, 0, _w);
          if (this.groundClear(x, y, z, _w.x, _w.y + 0.6, _w.z)) seen++;
        }
        // (a camera the ground had to lift far above its place looks down a slope: less liked)
        const score = seen + liked - (y - want) * 0.3;
        if (score > best) {
          best = score;
          out.set(x, y, z);
        }
      }
    }
  }

  /** Does the ground leave the line between two points free? (the terrain only: walls and posts are not asked) */
  private groundClear(ax: number, ay: number, az: number, bx: number, by: number, bz: number) {
    const steps = Math.max(4, Math.ceil(Math.hypot(bx - ax, bz - az) / 3));
    for (let k = 1; k < steps; k++) {
      const f = k / steps;
      if (this.terrain.heightAt(ax + (bx - ax) * f, az + (bz - az) * f) > ay + (by - ay) * f - 0.25) return false;
    }
    return true;
  }

  /** Drag the garage camera around the car (pixels); it stays where it is left until the garage reopens. */
  orbitGarage(dx: number, dy: number) {
    const o = (this.garageOrbit ??= this.orbitFromSwing());
    o.yaw -= dx * 0.008;
    o.pitch = clamp(o.pitch + dy * 0.005, 0.02, 1.2);
  }

  /** Wheel zoom of the garage camera: factor on the distance. */
  zoomGarage(factor: number) {
    const o = (this.garageOrbit ??= this.orbitFromSwing());
    o.dist = clamp(o.dist * factor, 5.5 * this.garageScale, 13 * this.garageScale);
  }

  /** The dragged camera starts where the automatic swing is. */
  private orbitFromSwing() {
    const pitch = Math.atan2(this.garageLift - 0.6, 8.6);
    return { yaw: Math.sin(this.garageAngle) * (this.lobby ? LINEUP_VIEW.swing : 0.75), pitch, dist: (8.6 * this.garageScale) / Math.cos(pitch) };
  }

  private garageCamera(dt: number) {
    if (this.lobby) {
      // the line-up grows, shrinks and moves with the room: the framing glides after it (a dragged camera keeps its
      // angle and its share of the distance)
      const f = 1 - Math.exp(-dt * 3);
      const was = this.garageScale;
      this.garageFocus.lerp(this.lobbyView.focus, f);
      this.garageScale += (this.lobbyView.scale - this.garageScale) * f;
      if (this.garageOrbit) this.garageOrbit.dist *= this.garageScale / was;
    }
    const car = this.garageFocus;
    const o = this.garageOrbit;
    // swing slowly from the uphill side; the car sits left of centre beside the UI card
    this.garageAngle += dt * 0.2;
    const a = this.garageViewYaw + (o ? o.yaw : Math.sin(this.garageAngle) * (this.lobby ? LINEUP_VIEW.swing : 0.75));
    const cam = this.camera;
    const k = this.garageScale;
    const frame = this.garageFraming;
    let zoom = frame.zoom;
    let dist = 0;
    for (;;) {
      dist = (o ? o.dist : 8.6 * k) * zoom;
      const flat = o ? Math.cos(o.pitch) * dist : dist;
      _v.set(car.x + Math.sin(a) * flat, car.y + (o ? 0.6 * k + Math.sin(o.pitch) * dist : this.garageLift * k * zoom), car.z + Math.cos(a) * flat);
      // stepping back further than the standard spot (the car select) must not carry the camera up a bank, from
      // where it would look down on the roof (the ground clamp below may lift it a little, some 7° more of a
      // downward look): it stays as much nearer as it has to
      if (zoom <= 1 || this.terrain.heightAt(_v.x, _v.z) + 1.4 <= _v.y + 0.12 * dist) break;
      zoom = Math.max(1, zoom - 0.1);
    }
    // no tree between the camera and what it shows, wherever it swings or is dragged: a clearing as wide as the
    // camera stands off, and a tree's crown more (the trees keep 10.5 m from the road: a car's view loses none)
    clearing.value.set(car.x, car.z, Math.hypot(_v.x - car.x, _v.z - car.z) + 5);
    // steep cuttings (ridge courses) would swallow the camera: keep it, and its glide in, above ground
    _v.y = Math.max(_v.y, this.terrain.heightAt(_v.x, _v.z) + 1.4);
    cam.position.lerp(_v, 1 - Math.exp(-dt * (o ? 14 : 3)));
    cam.position.y = Math.max(cam.position.y, this.terrain.heightAt(cam.position.x, cam.position.z) + 1.2);
    // aim beside the car (to the camera's right by default, so the car is framed in the left part of the screen)
    const reach = dist / 8.6;
    _f.set(Math.cos(a), 0, -Math.sin(a)).multiplyScalar(frame.right * reach);
    cam.lookAt(car.x + _f.x, car.y + 0.6 * k + frame.up * reach, car.z + _f.z);
    if (Math.abs(cam.fov - 38) > 0.01) {
      cam.fov = damp(cam.fov, 38, 3, dt);
      cam.updateProjectionMatrix();
    }
  }

  setGarageColor(color: string) {
    const car = this.garageCar;
    if (!car) return;
    this.garageWant = color;
    const t = car.spec.train;
    const id = car.spec.id;
    // another line of a train: its own model (loaded if need be), so the train is built again
    if (t && trainModelKey(id, trainLivery(t, color)) !== trainModelKey(id, trainLivery(t, car.color))) {
      const l = trainLivery(t, color);
      // (unless another colour or vehicle was picked meanwhile)
      const show = () => this.garageWant === color && this.garageCar?.spec.id === id && this.showGarage(id, color);
      if (trainModelReady(id, l)) show();
      else void loadTrainModel(trainModelKey(id, l)).then(show);
      return;
    }
    car.setColor(color);
    this.emit({ type: 'garage', carId: id, color });
  }

  /** tyre grip of this course's surface in the current weather */
  get roadGrip() {
    return this.weatherGrip * this.course.surface.grip;
  }

  get currentConfig() {
    return this.config;
  }

  get playerSim() {
    return this.player?.sim ?? null;
  }

  /**
   * Compiles every material of the scene for the current lights, in parallel where the browser can. The scene is
   * drawn into the post-processing chain's offscreen buffer (half-float colour, depth): pipelines are compiled per
   * target format, so against a stand-in target of that format, or the work is wasted.
   */
  private precompile(loading = false) {
    if (!loading || !this.env) return this.precompileScene(loading);
    // (behind the loading screen: with what only another time of day shows)
    this.env.holdParts(true);
    const env = this.env;
    return this.precompileScene(true).finally(() => env.holdParts(false));
  }

  private precompileScene(loading: boolean) {
    if (this.compileScene) return this.compileScene(loading).catch(() => undefined);
    const r = this.renderer, prev = r.getRenderTarget();
    this.compileTarget ??= new THREE.RenderTarget(1, 1, { type: THREE.HalfFloatType, depthTexture: new THREE.DepthTexture(1, 1) });
    r.setRenderTarget(this.compileTarget);
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
