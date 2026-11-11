// Online netcode without browsers: 2–5 simulated players exchange car states through the game's own receive code
// (NetLink → PeerReceiver → RemoteBody / ProxyCar in a Rapier world, the client-side impairment injector) on a
// simulated clock, under a given round trip, jitter and loss, and the numbers are printed:
//
//   COURSE=<id> npx tsx tools/net-replay.ts [vehicles] [key=value …]
//     vehicles  comma list, one per player in turn (default shiden,e231); every player is seen by all the others
//     rtt=100 jitter=20 loss=2    the network between any two players (ms, ± ms, %), each way half the round trip
//     resend=<ms>                 a lost packet is not gone but comes this late and holds back the next ones (TCP)
//     players=2 fps=60 seconds=90 seed=1
//     path=both|new|old           the current code, the code before Phase G (tools/net-legacy.ts), or both
//     mode=present|buffered       how the current code times the peers (see PeerReceiver.LagMode)
//     duel=1 [power=0.6 gap=10 runs=6]   instead: two cars, the first (short of power) caught by the second from
//                                 `gap` m behind, each simulated on its own client with the other as its solid
//                                 stand-in: when does each screen see the first touch, and how far apart are the
//                                 cars really at that moment?
//
// Replay: each vehicle is driven once over the course by the AI on the real physics (the truth, every physics
// step); each player plays that back as "its" car and sends it; every other player receives it and steers and
// draws it as the game does. Per frame the pose drawn is compared with where the sender's own screen has the car
// at that moment. A train's three cars are laid along the drawn path as the model does (TrainPath).
//   err    distance between drawn and true position (m): mean / 95th percentile / max (trains: the worst car)
//   step   how much the drawn car's movement in one frame differs from the true movement (cm): p95 / max;
//          jumps = frames where that is more than 0.3 m
//   head   heading error (°), p95
//   ahead  share of frames drawn past the newest packet, and how far past on average (ms)
//   corr   how far a new packet moved the prediction (m): mean / max      (current code only)
//   link   what the receiver measured itself: round trip, jitter, loss, the buffer delay that link would need
// DEBUG=<m> prints every frame whose error is larger.
import { Quaternion, Vector3 } from 'three';
import { Track } from '../src/game/track/Track';
import { COURSES, type CourseId } from '../src/game/track/courses';
import { PhysicsWorld, PHYSICS_DT, RAPIER, initRapier } from '../src/game/vehicle/PhysicsWorld';
import { VehicleSim, emptyInput } from '../src/game/vehicle/VehicleSim';
import { CAR_SPECS, type CarId } from '../src/game/vehicle/carSpecs';
import { AIDriver, AI_PROFILES } from '../src/game/ai/AIDriver';
import { RacingLine } from '../src/game/ai/RacingLine';
import { trainBogiePath } from '../src/game/vehicle/trains';
import { TrainPath } from '../src/game/render/TrainPath';
import { NetLink, type LocalState } from '../src/game/net/NetLink';
import { RemoteBody } from '../src/game/net/RemoteBody';
import { ProxyCar } from '../src/game/net/ProxyCar';
import { newPose } from '../src/game/net/PeerTrack';
import type { LagMode } from '../src/game/net/PeerReceiver';
import { ImpairedTransport, type Impairment, type NetTransport, type Timers } from '../src/game/net/transport';
import { LEGACY_SEND_MS, LegacyPeer, LegacyProxyCar, legacyState, type LegacyState } from './net-legacy';

await initRapier();

// ------------------------------------------------------------------ arguments
const argv = process.argv.slice(2);
const opt = new Map(argv.filter((a) => a.includes('=')).map((a) => a.split('=') as [string, string]));
const num = (k: string, d: number) => (opt.has(k) ? Number(opt.get(k)) : d);
const vehicles = (argv.find((a) => !a.includes('=')) ?? 'shiden,e231').split(',') as CarId[];
const RTT = num('rtt', 100), JITTER = num('jitter', 20), LOSS = num('loss', 2), FPS = num('fps', 60), SECONDS = num('seconds', 90), SEED = num('seed', 1);
const PLAYERS = Math.max(2, num('players', Math.max(2, vehicles.length)));
const PATHS = (opt.get('path') ?? 'both') === 'both' ? (['old', 'new'] as const) : ([opt.get('path')] as ('old' | 'new')[]);
const MODE = (opt.get('mode') ?? 'present') as LagMode;
const impairment: Impairment = { delay: RTT / 2, jitter: JITTER, loss: LOSS / 100, ...(opt.has('resend') ? { resend: num('resend', 200) } : {}) };
const DT_MS = PHYSICS_DT * 1000;
const SEND_INTERVAL = 1 / 30;

const course = COURSES[(process.env.COURSE ?? 'oboro-downhill') as CourseId];
const track = new Track(course.design);
const line = new RacingLine(track);

function mulberry32(seed: number) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// ------------------------------------------------------------------ simulated time
class Sched {
  t = 0;
  private heap: { t: number; n: number; fn: () => void }[] = [];
  private n = 0;

  at(t: number, fn: () => void) {
    const h = this.heap, e = { t, n: this.n++, fn };
    let i = h.push(e) - 1;
    while (i > 0) {
      const p = (i - 1) >> 1;
      if (h[p].t < e.t || (h[p].t === e.t && h[p].n < e.n)) break;
      h[i] = h[p];
      i = p;
    }
    h[i] = e;
  }

  run(until: number) {
    const h = this.heap, less = (a: (typeof h)[0], b: (typeof h)[0]) => a.t < b.t || (a.t === b.t && a.n < b.n);
    while (h.length && h[0].t <= until) {
      const top = h[0], last = h.pop()!;
      if (h.length) {
        let i = 0;
        for (;;) {
          let c = 2 * i + 1;
          if (c >= h.length) break;
          if (c + 1 < h.length && less(h[c + 1], h[c])) c++;
          if (!less(h[c], last)) break;
          h[i] = h[c];
          i = c;
        }
        h[i] = last;
      }
      this.t = top.t;
      top.fn();
    }
    this.t = until;
  }

  /** a client's clock: the wall clock plus that machine's own offset */
  timers(off: number): Timers {
    return { now: () => this.t + off, after: (ms, fn) => this.at(this.t + ms, fn) };
  }
}

/** The room's relay: what one sends, all the others get (the network's faults are added at each receiver). */
class Hub<T> {
  private ends = new Map<number, { onReceive: ((from: number, data: T) => void) | null }>();

  join(id: number) {
    const ends = this.ends;
    const end = {
      ready: true,
      onReceive: null as ((from: number, data: T) => void) | null,
      send(data: T) {
        for (const [other, e] of ends) if (other !== id) e.onReceive?.(id, data);
      },
    };
    ends.set(id, end);
    return end;
  }
}

// ------------------------------------------------------------------ the truth
interface CarState {
  p: Vector3;
  q: Quaternion;
  vel: Vector3;
  w: Vector3;
  acc: Vector3;
  fwd: number;
  steer: number;
  s: number;
  ep: number;
  /** this step was a hit (wall): the game sends such a state at once */
  hit: boolean;
}

/** One vehicle driven over the course by the AI: its state after every physics step (as the game would send it). */
function record(carId: CarId, seconds: number): CarState[] {
  const physics = new PhysicsWorld(track);
  const s0 = track.startS - 12;
  const sim = new VehicleSim(physics, CAR_SPECS[carId], track.pointAt(s0), track.headingAt(s0));
  sim.gripScale = course.surface.grip;
  const ai = new AIDriver(track, line, AI_PROFILES.legend);
  ai.calibrate(sim);
  const input = emptyInput();
  const out: CarState[] = [];
  const acc = new Vector3(), last = new Vector3(), d = new Vector3();
  let ep = 0;
  for (let k = 0; k < seconds / PHYSICS_DT && ai.s < track.finishS; k++) {
    // two seconds on the grid first, as in a countdown (the clocks are matched meanwhile)
    if (k * PHYSICS_DT < 2) Object.assign(input, emptyInput(), { hold: true });
    else {
      input.hold = false;
      ai.update(sim, PHYSICS_DT, input);
    }
    sim.input = input;
    sim.preStep(PHYSICS_DT);
    physics.step();
    sim.postStep(PHYSICS_DT);
    // (the smoothed acceleration, as Game.step keeps it)
    if (sim.impact === 0) acc.lerp(d.subVectors(sim.velocity, last).divideScalar(PHYSICS_DT).clampLength(0, 40), 1 - Math.exp(-PHYSICS_DT / 0.06));
    last.copy(sim.velocity);
    const w = sim.body.angvel();
    out.push({ p: sim.position.clone(), q: sim.quaternion.clone(), vel: sim.velocity.clone(), w: new Vector3(w.x, w.y, w.z), acc: acc.clone(), fwd: sim.forwardSpeed, steer: sim.wheels[0]?.steer ?? 0, s: ai.s, ep, hit: sim.impact > 0 });
    if (sim.isFlipped || ai.needsRespawn || sim.position.y < -50) {
      const s = Math.max(ai.s - 5, 0);
      sim.reset(track.pointAt(s), track.headingAt(s), 5);
      ep = (ep + 1) & 3;
      acc.set(0, 0, 0);
      last.copy(sim.velocity);
    }
  }
  physics.dispose();
  return out;
}

// ------------------------------------------------------------------ measuring
const pct = (a: number[], p: number) => (a.length ? [...a].sort((x, y) => x - y)[Math.min(a.length - 1, Math.floor(a.length * p))] : 0);
const mean = (a: number[]) => (a.length ? a.reduce((s, x) => s + x, 0) / a.length : 0);
const maxOf = (a: number[]) => a.reduce((m, x) => Math.max(m, x), 0);

const _f = new Vector3(), _a = new Vector3(), _b = new Vector3();

/** A vehicle's drawn points: the body, or a train's three cars along the path the body has drawn. */
class Shape {
  private path: TrainPath | null;
  private bogies: [number, number][] = [];
  readonly points: Vector3[];
  private prev: Vector3[];
  private seen = false;
  /** metres driven since the first pose: until a train's length is behind it, its rear cars stand on an assumed path */
  private driven = 0;
  private last = new Vector3();

  constructor(carId: CarId) {
    const t = CAR_SPECS[carId].train;
    this.path = t ? new TrainPath() : null;
    if (t) this.bogies = trainBogiePath(t);
    this.points = (t ? this.bogies : [0]).map(() => new Vector3());
    this.prev = this.points.map(() => new Vector3());
  }

  /** Places the points for a pose; returns false on the first call (nothing to compare the movement with). */
  place(p: Vector3, q: Quaternion) {
    this.points.forEach((x, k) => this.prev[k].copy(x));
    if (this.path) {
      this.path.advance(p, _f.set(0, 0, 1).applyQuaternion(q));
      this.bogies.forEach(([front, rear], k) => this.points[k].addVectors(this.path!.at(front, _a), this.path!.at(rear, _b)).multiplyScalar(0.5));
    } else this.points[0].copy(p);
    if (this.seen) this.driven += this.last.distanceTo(p);
    this.last.copy(p);
    const had = this.seen;
    this.seen = true;
    return had;
  }

  /** how many of the points stand on driven path */
  get valid() {
    return this.driven > 80 ? this.points.length : 1;
  }

  /** movement of point k since the last pose */
  moved(k: number, out: Vector3) {
    return out.subVectors(this.points[k], this.prev[k]);
  }
}

class Meter {
  err: number[] = [];
  step: number[] = [];
  head: number[] = [];
  jumps = 0;
  ahead: number[] = [];
  past: number[] = [];
  private shown: Shape;
  private truth: Shape;

  constructor(carId: CarId) {
    this.shown = new Shape(carId);
    this.truth = new Shape(carId);
  }

  add(p: Vector3, q: Quaternion, truth: CarState, count: boolean) {
    const a = this.shown.place(p, q), b = this.truth.place(truth.p, truth.q);
    if (!a || !b || !count) return;
    let e = 0, s = 0;
    this.shown.points.slice(0, Math.min(this.shown.valid, this.truth.valid)).forEach((x, k) => {
      e = Math.max(e, x.distanceTo(this.truth.points[k]));
      s = Math.max(s, this.shown.moved(k, _a).sub(this.truth.moved(k, _b)).length());
    });
    if (process.env.DEBUG && e > Number(process.env.DEBUG)) console.log(`   err ${e.toFixed(2)} lead ${this.shown.points[0].distanceTo(this.truth.points[0]).toFixed(2)} cars ${this.shown.points.map((x, k) => x.distanceTo(this.truth.points[k]).toFixed(2)).join('/')} step ${s.toFixed(2)} at ${truth.p.x.toFixed(0)},${truth.p.z.toFixed(0)}`);
    this.err.push(e);
    this.step.push(s);
    if (s > 0.3) this.jumps++;
    this.head.push((q.angleTo(truth.q) * 180) / Math.PI);
  }
}

// ------------------------------------------------------------------ a player
const _pose = newPose(), _scratch = newPose();
const _state: CarState = { p: new Vector3(), q: new Quaternion(), vel: new Vector3(), w: new Vector3(), acc: new Vector3(), fwd: 0, steer: 0, s: 0, ep: 0, hit: false };

interface Car {
  carId: CarId;
  /** the latest physics state, and the wall time (ms) it is of */
  state(): CarState;
  stateWall(): number;
  /** where the player's own screen has the car at wall time `t` (ms) */
  at(t: number, out: CarState): CarState;
  /** physics steps up to wall time `t` (ms); `each(stepEnd)` runs before each step with the wall time it ends at.
   * True when one of the steps was a hit. */
  advance(t: number, each: (stepEnd: number) => void): boolean;
}

/** A recorded run played back: state `n` is of wall time `phase + n × step`. */
class Playback implements Car {
  private n = 0;

  constructor(readonly carId: CarId, private states: CarState[], private phase: number, private shift: number) {}

  private get(k: number) {
    return this.states[Math.min(this.states.length - 1, Math.max(0, k + this.shift))];
  }
  state() {
    return this.get(this.n);
  }
  stateWall() {
    return this.phase + this.n * DT_MS;
  }
  at(t: number, out: CarState) {
    const x = (t - this.phase) / DT_MS, i = Math.floor(x), u = x - i;
    const a = this.get(i), b = this.get(i + 1);
    out.p.lerpVectors(a.p, b.p, u);
    out.q.slerpQuaternions(a.q, b.q, u);
    return out;
  }
  advance(t: number, each: (stepEnd: number) => void) {
    const to = Math.floor((t - this.phase) / DT_MS + 1e-6);
    let hit = false;
    for (let m = this.n + 1; m <= to; m++) {
      each(this.phase + m * DT_MS);
      hit ||= this.get(m).hit;
    }
    this.n = Math.max(this.n, to);
    return hit;
  }
}

/**
 * A car simulated on this client (duel): the AI drives it on the real physics, and the other player's stand-in is
 * a body in the same world, so the two can touch. State `n` is of wall time `phase + n × step`.
 */
class Live implements Car {
  readonly physics = new PhysicsWorld(track);
  readonly sim: VehicleSim;
  private ai = new AIDriver(track, line, AI_PROFILES.legend);
  private input = emptyInput();
  private n = 0;
  private acc = new Vector3();
  private last = new Vector3();
  private cur: CarState;
  /** the car's position after every step (the truth the other screen is measured against) */
  private trail: Vector3[] = [];
  /** the other cars' stand-ins in this world */
  others: RAPIER.Collider[] = [];
  /** wall time (ms) of the first touch on this screen, seconds in touch, number of separate touches, hardest hit (m/s) */
  firstContact = -1;
  contactTime = 0;
  hits = 0;
  hardest = 0;
  private touching = false;

  constructor(readonly carId: CarId, s0: number, power: number, private phase: number, private go: number) {
    this.sim = new VehicleSim(this.physics, CAR_SPECS[carId], track.pointAt(s0), track.headingAt(s0));
    this.sim.gripScale = course.surface.grip;
    this.ai.calibrate(this.sim);
    this.sim.powerScale = power;
    this.cur = this.snapshot(false);
    this.trail.push(this.sim.position.clone());
  }

  private snapshot(hit: boolean): CarState {
    const sim = this.sim, w = sim.body.angvel();
    return { p: sim.position.clone(), q: sim.quaternion.clone(), vel: sim.velocity.clone(), w: new Vector3(w.x, w.y, w.z), acc: this.acc.clone(), fwd: sim.forwardSpeed, steer: sim.wheels[0]?.steer ?? 0, s: this.ai.s, ep: 0, hit };
  }
  state() {
    return this.cur;
  }
  stateWall() {
    return this.phase + this.n * DT_MS;
  }
  at(t: number, out: CarState) {
    const x = Math.max(0, (t - this.phase) / DT_MS), i = Math.min(this.trail.length - 1, Math.floor(x));
    out.p.lerpVectors(this.trail[i], this.trail[Math.min(this.trail.length - 1, i + 1)], x - Math.floor(x));
    return out;
  }
  advance(t: number, each: (stepEnd: number) => void) {
    const to = Math.floor((t - this.phase) / DT_MS + 1e-6), sim = this.sim;
    let hit = false;
    for (let m = this.n + 1; m <= to; m++) {
      const wall = this.phase + m * DT_MS;
      if (wall < this.go) Object.assign(this.input, emptyInput(), { hold: true });
      else {
        this.input.hold = false;
        this.ai.update(sim, PHYSICS_DT, this.input);
      }
      sim.input = this.input;
      sim.preStep(PHYSICS_DT);
      each(wall);
      this.physics.step();
      sim.postStep(PHYSICS_DT);
      if (sim.impact > 0) hit = true;
      else this.acc.lerp(_a.subVectors(sim.velocity, this.last).divideScalar(PHYSICS_DT).clampLength(0, 40), 1 - Math.exp(-PHYSICS_DT / 0.06));
      this.last.copy(sim.velocity);
      this.trail.push(sim.position.clone());
      // (as Game.detectCarContact)
      let now = false, impulse = 0;
      for (const c of this.others) {
        this.physics.world.contactPair(sim.collider, c, (mf) => {
          for (let i = 0; i < mf.numContacts(); i++) {
            const imp = mf.contactImpulse(i);
            if (mf.contactDist(i) > 0.02 && imp <= 0) continue;
            now = true;
            impulse = Math.max(impulse, imp);
          }
        });
      }
      if (now) {
        this.contactTime += PHYSICS_DT;
        if (this.firstContact < 0) this.firstContact = wall;
        if (!this.touching) this.hits++;
        this.hardest = Math.max(this.hardest, impulse / sim.spec.mass);
      }
      this.touching = now;
    }
    this.n = Math.max(this.n, to);
    this.cur = this.snapshot(hit);
    return hit;
  }
}

type Path = 'old' | 'new';
const v3 = (v: Vector3): [number, number, number] => [v.x, v.y, v.z];

class Player {
  readonly timers: Timers;
  readonly world: RAPIER.World;
  // current code
  readonly link: NetLink;
  readonly bodies = new Map<number, RemoteBody>();
  // code before Phase G
  readonly legacy = new Map<number, { peer: LegacyPeer; proxy: LegacyProxyCar }>();
  private legacyOut: NetTransport | null = null;
  readonly meters = new Map<number, Meter>();
  private sendT = 0;
  private lastFrame = -1;
  /** the local car's position when it is simulated here (duel) */
  localCar: Vector3 | null = null;

  constructor(
    readonly id: number,
    readonly car: Car,
    readonly path: Path,
    sched: Sched,
    /** this machine's clock against the wall clock (ms) */
    readonly off: number,
    world?: RAPIER.World,
  ) {
    this.timers = sched.timers(off);
    this.world = world ?? new RAPIER.World({ x: 0, y: 0, z: 0 });
    this.world.timestep = PHYSICS_DT;
    this.link = new NetLink(this.timers.now, this.timers, random);
    this.link.selfId = id;
    this.link.setMode(MODE);
  }

  join(hub: Hub<number[]>, legacyHub: Hub<LegacyState>, peers: Player[]) {
    for (const p of peers) {
      if (p === this) continue;
      const s = p.car.state();
      this.meters.set(p.id, new Meter(p.car.carId));
      if (this.path === 'new') {
        const body = new RemoteBody(this.link.peer(p.id), _scratch);
        body.proxy = new ProxyCar({ world: this.world } as PhysicsWorld, CAR_SPECS[p.car.carId], s.p, s.q);
        this.bodies.set(p.id, body);
      } else this.legacy.set(p.id, { peer: new LegacyPeer(), proxy: new LegacyProxyCar(this.world, CAR_SPECS[p.car.carId], s.p, s.q) });
    }
    if (this.path === 'new') {
      this.link.impair({ recv: impairment });
      this.link.attach(hub.join(this.id));
    } else {
      const end = new ImpairedTransport(legacyHub.join(this.id) as unknown as NetTransport, { recv: impairment }, this.timers, random);
      end.onReceive = (from, data) => this.legacy.get(from)?.peer.push(data as unknown as LegacyState, this.timers.now());
      this.legacyOut = end;
    }
  }

  /** The old client's 80 ms interval timer: the latest physics state, stamped now. */
  legacySend() {
    const s = this.car.state();
    this.legacyOut?.send(legacyState(this.timers.now(), s.p, s.q, s.fwd, s.steer, s.s) as unknown as number[]);
  }

  /** One frame at wall time `t` (ms): physics steps, a state sent, the peers drawn and measured. As Game.update. */
  frame(t: number, measure: boolean) {
    const now = t + this.off;
    const dt = this.lastFrame < 0 ? 1000 / FPS : t - this.lastFrame;
    this.lastFrame = t;
    const urgent = this.car.advance(t, (stepEnd) => {
      if (this.path === 'new') for (const b of this.bodies.values()) b.step(stepEnd + this.off, now, this.localCar);
      else for (const l of this.legacy.values()) l.peer.step(l.proxy, now, this.localCar);
      // (a car simulated here steps the world itself, with its own forces)
      if (this.car instanceof Playback) this.world.step();
    });
    if (this.path === 'new') {
      this.sendT += dt / 1000;
      if ((urgent && !opt.has('nourgent')) || this.sendT >= SEND_INTERVAL - 0.002) {
        this.sendT = urgent && !opt.has('nourgent') ? 0 : Math.min(this.sendT - SEND_INTERVAL, SEND_INTERVAL);
        const s = this.car.state();
        const st: LocalState = { at: this.car.stateWall() + this.off, p: v3(s.p), q: [s.q.x, s.q.y, s.q.z, s.q.w], vel: v3(s.vel), w: v3(s.w), acc: opt.has('noacc') ? [0, 0, 0] : v3(s.acc), st: s.steer, s: s.s, br: 0, ep: s.ep, th: 0, rp: 0 };
        this.link.send(st);
      }
    }
    // the local car is drawn one physics step behind the frame's moment: so are the others
    const at = t - DT_MS;
    for (const p of players) {
      const meter = this.meters.get(p.id);
      if (!meter) continue;
      const truth = p.car.at(at, _state);
      if (this.path === 'new') {
        const body = this.bodies.get(p.id)!;
        if (!body.frame(at + this.off, dt, _pose)) continue;
        meter.add(_pose.position, _pose.quaternion, truth, measure);
        if (measure) meter.ahead.push(_pose.ahead * 1000);
        // drawn in the past on purpose: how well does it follow the road it was on then?
        if (measure && MODE === 'buffered') meter.past.push(_pose.position.distanceTo(p.car.at(at - body.rx.lag, _state).p));
      } else {
        const l = this.legacy.get(p.id)!;
        l.peer.frame(dt / 1000);
        if (!l.peer.buf.length) continue;
        meter.add(l.proxy.position, l.proxy.quaternion, truth, measure);
        if (measure) meter.ahead.push(l.peer.age * 1000);
      }
    }
  }
}

let random = mulberry32(SEED);
let players: Player[] = [];

// ------------------------------------------------------------------ replay
function replay(path: Path, truths: Map<CarId, CarState[]>) {
  random = mulberry32(SEED);
  const sched = new Sched();
  const hub = new Hub<number[]>(), legacyHub = new Hub<LegacyState>();
  const frame = 1000 / FPS;
  players = Array.from({ length: PLAYERS }, (_, k) => {
    const carId = vehicles[k % vehicles.length];
    // every player's frames, physics and clock are its own; cars of one kind run a second apart
    const car = new Playback(carId, truths.get(carId)!, random() * frame, Math.floor(k / vehicles.length) * 120);
    return new Player(k + 1, car, path, sched, Math.round(random() * 1e7) / 10);
  });
  for (const p of players) p.join(hub, legacyHub, players);
  const end = Math.min(SECONDS, Math.min(...[...truths.values()].map((s) => s.length)) * PHYSICS_DT - 2 * PLAYERS) * 1000;
  for (const p of players) {
    const phase = random() * frame;
    const tick = (t: number) => {
      p.frame(t, t > 3000);
      if (t + frame < end) sched.at(t + frame, () => tick(t + frame));
    };
    sched.at(phase, () => tick(phase));
    if (path === 'old') {
      const send = (t: number) => {
        p.legacySend();
        if (t + LEGACY_SEND_MS < end) sched.at(t + LEGACY_SEND_MS, () => send(t + LEGACY_SEND_MS));
      };
      const first = random() * LEGACY_SEND_MS;
      sched.at(first, () => send(first));
    }
  }
  sched.run(end);
  // one row per vehicle: every receiver's view of every player driving it
  for (const carId of new Set(players.map((p) => p.car.carId))) {
    const seen = players.flatMap((rx) => players.filter((p) => p !== rx && p.car.carId === carId).map((p) => ({ rx, p, m: rx.meters.get(p.id)! })));
    const err = seen.flatMap((x) => x.m.err), step = seen.flatMap((x) => x.m.step), head = seen.flatMap((x) => x.m.head), ahead = seen.flatMap((x) => x.m.ahead);
    const jumps = seen.reduce((n, x) => n + x.m.jumps, 0);
    let row = `${course.id.padEnd(15)} ${carId.padEnd(7)} ${path}  err ${mean(err).toFixed(3)} / ${pct(err, 0.95).toFixed(3)} / ${maxOf(err).toFixed(3)} m   step ${(pct(step, 0.95) * 100).toFixed(1)} / ${(maxOf(step) * 100).toFixed(1)} cm  jumps ${String(jumps).padStart(4)} of ${err.length}   head ${pct(head, 0.95).toFixed(2)}°   ahead ${((ahead.filter((x) => x > 0).length / Math.max(1, ahead.length)) * 100).toFixed(0)} % ${mean(ahead).toFixed(0)} ms`;
    if (path === 'new' && MODE === 'buffered') {
      const past = seen.flatMap((x) => x.m.past);
      row += `   against where it was one lag ago: ${mean(past).toFixed(3)} / ${pct(past, 0.95).toFixed(3)} / ${maxOf(past).toFixed(3)} m`;
    }
    if (path === 'new') {
      const st = seen.map((x) => x.rx.link.peer(x.p.id)), corr = st.flatMap((r) => r.corrections);
      const s = st.map((r) => r.stats());
      row += `   corr ${mean(corr).toFixed(3)} / ${maxOf(corr).toFixed(3)} m snaps ${s.reduce((n, x) => n + x.snaps, 0)}   link rtt ${mean(s.map((x) => x.rtt)).toFixed(0)} (min ${mean(s.map((x) => x.rttMin)).toFixed(0)}) jitter ${mean(s.map((x) => x.jitter)).toFixed(1)} loss ${((s.reduce((n, x) => n + x.lost, 0) / Math.max(1, s.reduce((n, x) => n + x.lost + x.received, 0))) * 100).toFixed(1)} % buffer ${mean(s.map((x) => x.bufferDelay)).toFixed(0)} ms lag ${mean(s.map((x) => x.lag)).toFixed(0)} ms`;
    }
    console.log(row);
  }
}

// ------------------------------------------------------------------ duel
/**
 * Two players, each simulating its own car with the other's as a stand-in: the leader (short of power) is caught
 * by the chaser from 10 m behind in the same lane. Before they touch nothing the network does changes either
 * car, so the first touch has a true moment (the cars' own simulations one length apart); each screen's first
 * touch is compared with it and with the other screen's.
 */
function duel(path: Path, seed: number) {
  random = mulberry32(seed);
  const sched = new Sched();
  const hub = new Hub<number[]>(), legacyHub = new Hub<LegacyState>();
  const frame = 1000 / FPS;
  const [lead, chase] = [vehicles[0], vehicles[1] ?? vehicles[0]];
  const cars = [new Live(lead, track.startS - 12, num('power', 0.6), random() * frame, 2000), new Live(chase, track.startS - 12 - num('gap', 10), 1, random() * frame, 2000)];
  players = cars.map((car, k) => {
    const p = new Player(k + 1, car, path, sched, Math.round(random() * 1e7) / 10, car.physics.world);
    p.localCar = car.sim.position;
    return p;
  });
  for (const p of players) p.join(hub, legacyHub, players);
  cars.forEach((car, k) => (car.others = path === 'new' ? [...players[k].bodies.values()].map((b) => b.proxy!.collider) : [...players[k].legacy.values()].map((l) => l.proxy.collider)));
  const end = SECONDS * 1000;
  for (const p of players) {
    const phase = random() * frame;
    const tick = (t: number) => {
      p.frame(t, false);
      if (t + frame < end) sched.at(t + frame, () => tick(t + frame));
    };
    sched.at(phase, () => tick(phase));
    if (path === 'old') {
      const send = (t: number) => {
        p.legacySend();
        if (t + LEGACY_SEND_MS < end) sched.at(t + LEGACY_SEND_MS, () => send(t + LEGACY_SEND_MS));
      };
      const first = random() * LEGACY_SEND_MS;
      sched.at(first, () => send(first));
    }
  }
  sched.run(end);
  // the cars' own simulations, centre to centre, at a wall time
  const gap = (t: number) => cars[0].at(t, _state).p.distanceTo(cars[1].at(t, { ..._state, p: _a }).p);
  const out = { first: cars.map((c) => c.firstContact), gap: cars.map((c) => (c.firstContact < 0 ? NaN : gap(c.firstContact))), time: cars.map((c) => c.contactTime), hits: cars.map((c) => c.hits), hardest: cars.map((c) => c.hardest) };
  for (const c of cars) c.physics.dispose();
  return out;
}

function duels() {
  const runs = num('runs', 6);
  const len = (CAR_SPECS[vehicles[0]].size.length + CAR_SPECS[vehicles[1] ?? vehicles[0]].size.length) / 2;
  console.log(`duel: ${vehicles[0]} (power ${num('power', 0.6)}) caught by ${vehicles[1] ?? vehicles[0]} from ${num('gap', 10)} m behind; the cars touch ${len.toFixed(2)} m apart (centre to centre, nose to tail)`);
  for (const path of PATHS) {
    const skews: number[] = [], gaps: number[] = [];
    for (let k = 0; k < runs; k++) {
      const r = duel(path, SEED + k);
      const both = r.first[0] >= 0 && r.first[1] >= 0;
      if (both) skews.push(Math.abs(r.first[0] - r.first[1]));
      gaps.push(...r.gap.filter((g) => !Number.isNaN(g)).map((g) => Math.abs(g - len)));
      console.log(`  ${path} run ${k + 1}: first touch on the leader's screen ${r.first[0] < 0 ? 'never' : (r.first[0] / 1000).toFixed(3) + ' s'}, on the chaser's ${r.first[1] < 0 ? 'never' : (r.first[1] / 1000).toFixed(3) + ' s'}${both ? `  (apart ${Math.abs(r.first[0] - r.first[1]).toFixed(0)} ms)` : ''}; the cars' true distance then ${r.gap.map((g) => g.toFixed(2)).join(' / ')} m; touching for ${r.time.map((x) => x.toFixed(2)).join(' / ')} s in ${r.hits.join(' / ')} touches, hardest ${r.hardest.map((x) => x.toFixed(2)).join(' / ')} m/s`);
    }
    console.log(`${course.id.padEnd(15)} ${path}  first touch on the two screens apart: ${skews.length ? `mean ${mean(skews).toFixed(0)} ms, max ${maxOf(skews).toFixed(0)} ms` : 'n/a'} (${skews.length} of ${runs} runs touched on both screens)   true distance off the touching distance then: mean ${mean(gaps).toFixed(2)} m, max ${maxOf(gaps).toFixed(2)} m`);
  }
}

// ------------------------------------------------------------------ main
console.log(`course ${course.id}  players ${PLAYERS} (${vehicles.join(', ')})  ${FPS} fps  network: rtt ${RTT} ms, jitter ±${JITTER} ms, loss ${LOSS} %${opt.has('resend') ? ` (resent after ${impairment.resend} ms)` : ''}${MODE === 'buffered' ? '  mode buffered' : ''}`);
if (opt.has('duel')) {
  duels();
  process.exit(0);
}
const truths = new Map<CarId, CarState[]>();
for (const id of new Set(vehicles)) {
  const states = record(id, SECONDS + 2 * PLAYERS + 2);
  truths.set(id, states);
  console.log(`  ${id}: ${(states.length * PHYSICS_DT).toFixed(0)} s driven, top ${(Math.max(...states.map((s) => s.vel.length())) * 3.6).toFixed(0)} km/h`);
}
for (const path of PATHS) replay(path, truths);
