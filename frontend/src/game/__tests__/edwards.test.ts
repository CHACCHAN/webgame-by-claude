import { readFileSync } from 'node:fs';
import { Vector3 } from 'three';
import { beforeAll, describe, expect, it } from 'vitest';
import { AIDriver, AI_PROFILES } from '../ai/AIDriver';
import { RacingLine } from '../ai/RacingLine';
import { GRID_CLEARANCE, GRID_MIN_S, GRID_ROW_GAP, footprint, onlineGrid, type GridEntry } from '../net/grid';
import { decodeState, encodeState, type NetState } from '../net/codec';
import { Departure } from '../race/Departure';
import { medalFor, nextTarget } from '../race/medals';
import { RELEASED } from '../release';
import { Track } from '../track/Track';
import { ALL_COURSES, COURSES, COURSE_ORDER } from '../track/courses';
import { buildTerrain, planTerrain } from '../track/terrain';
import { PHYSICS_DT, PhysicsWorld, initRapier } from '../vehicle/PhysicsWorld';
import { VehicleSim, emptyInput } from '../vehicle/VehicleSim';
import { BIKE_ORDER } from '../vehicle/bikes';
import { CAR_ORDER, CAR_SPECS, VEHICLE_ORDER, vehiclesFor, type CarId } from '../vehicle/carSpecs';
import { JET_ORDER, enginesAt, jetForLivery, jetRpm } from '../vehicle/jets';
import { kindOf } from '../vehicle/kinds';
import { TRAIN_ORDER } from '../vehicle/trains';

// Edwards AFB and the fighters are checked here whether they are released or not (the lists a player sees leave
// them out until then: the other tests walk those lists).
const course = COURSES.edwards;
const track = new Track(course.design);

beforeAll(async () => {
  await initRapier();
});

describe('the release switch', () => {
  it('is the same on both sides: the client\'s lists and the server\'s', () => {
    const client = readFileSync(new URL('../release.ts', import.meta.url), 'utf8');
    const server = readFileSync(new URL('../../../../backend/config/game.php', import.meta.url), 'utf8');
    const c = /edwards: (true|false)\b/.exec(client), s = /'edwards' => (true|false)/.exec(server);
    expect(c && s).toBeTruthy();
    expect(c![1]).toBe(s![1]);
  });

  it('the server offers the vehicles on every course that the game does (config/game.php `courses`, `vehiclesFor`)', () => {
    const php = readFileSync(new URL('../../../../backend/config/game.php', import.meta.url), 'utf8');
    // the `$cars` list: one entry a line, 'id' => ['name' => …, 'courses' => ['a', 'b'], 'release' => 'x']
    const block = /\$cars = \[\n([\s\S]*?)\n\];/.exec(php)![1];
    const server: { id: string; courses?: string[]; release?: string }[] = [];
    for (const line of block.split('\n')) {
      const m = /^\s*'([a-z0-9]+)' => \[(.*)\],\s*$/.exec(line);
      if (!m) continue;
      const courses = /'courses' => \[([^\]]*)\]/.exec(m[2]);
      server.push({ id: m[1], courses: courses ? [...courses[1].matchAll(/'([^']+)'/g)].map((c) => c[1]) : undefined, release: /'release' => '([a-z]+)'/.exec(m[2])?.[1] });
    }
    expect(server.length).toBeGreaterThan(20);
    // (App\Support\Vehicles::on, with the switch as this run has it)
    const open = server.filter((c) => !c.release || RELEASED[c.release as keyof typeof RELEASED]);
    const on = (course: string) => open.filter((c) => !c.courses || c.courses.includes(course)).map((c) => c.id);
    for (const course of ALL_COURSES) {
      expect([...on(course)].sort(), course).toEqual([...vehiclesFor(course)].sort());
      // the vehicle a member is seated in when theirs does not run there: the first on both sides
      expect(on(course)[0], course).toBe(vehiclesFor(course)[0]);
    }
    // whatever the server binds to courses is bound to the same ones in the game, released or not
    for (const c of server.filter((x) => x.courses)) expect(CAR_SPECS[c.id as CarId].jet?.courses, c.id).toEqual(c.courses);
    for (const id of JET_ORDER) expect(server.find((c) => c.id === id)?.courses, id).toEqual(CAR_SPECS[id].jet!.courses);
  });

  it('keeps the course and the fighters out of every list until then, and the fighters at Edwards afterwards', () => {
    expect(ALL_COURSES).toContain('edwards');
    expect(COURSE_ORDER.includes('edwards')).toBe(RELEASED.edwards);
    for (const id of JET_ORDER) {
      expect(VEHICLE_ORDER.includes(id)).toBe(RELEASED.edwards);
      expect(CAR_SPECS[id].jet!.courses).toEqual(['edwards']);
      // never among the cars the AI, the bots and the traffic are taken from
      expect(CAR_ORDER as CarId[]).not.toContain(id);
      for (const c of ALL_COURSES) expect(vehiclesFor(c).includes(id)).toBe(RELEASED.edwards && c === 'edwards');
    }
    // everything else runs there too
    for (const id of VEHICLE_ORDER) if (!CAR_SPECS[id].jet) expect(vehiclesFor('edwards')).toContain(id);
  });
});

describe('Edwards AFB: the course', () => {
  it('runs ramp, taxiway, runway and lakebed in that order, about twelve kilometres timed', () => {
    expect(track.finishS - track.startS).toBeGreaterThan(11_500);
    expect(track.finishS - track.startS).toBeLessThan(12_500);
    const first = (tag: 'ramp' | 'taxiway' | 'runway' | 'lakebed') => track.zoneRanges(tag)[0][0];
    expect(first('ramp')).toBeLessThan(first('taxiway'));
    expect(first('taxiway')).toBeLessThan(first('runway'));
    expect(first('runway')).toBeLessThan(first('lakebed'));
    // runway 04R/22L: 4.5 km of it are driven in one piece
    const [a, b] = track.zoneRanges('runway')[0];
    expect(b - a).toBeGreaterThan(4400);
    // room to stop, or to leave by air, beyond the line
    expect(track.length - track.finishS).toBeGreaterThan(1500);
    // level ground: the whole of it within a few metres of height
    let lo = Infinity, hi = -Infinity;
    for (let i = 0; i < track.count; i += 10) {
      const y = track.pointAt(i, 0).y;
      lo = Math.min(lo, y);
      hi = Math.max(hi, y);
    }
    expect(hi - lo).toBeLessThan(12);
  });

  it('has the lakebed slower under the tyres than the concrete', () => {
    const at = (tag: 'runway' | 'lakebed') => {
      const [a, b] = track.zoneRanges(tag)[0];
      const i = Math.round((a + b) / 2), p = track.pointAt(i, 0);
      return track.surfaceGrip(i, 0, p.x, p.z);
    };
    expect(at('runway')).toBeCloseTo(1, 6);
    expect(at('lakebed')).toBeCloseTo(0.8, 6);
  });

  it('lies on its ground: the land is level with the pavement, never over it', () => {
    const T = buildTerrain(track, course.landform);
    let over = -Infinity, under = Infinity;
    for (let i = 0; i < track.count; i += 2) {
      const hw = track.paveAt(i) / 2;
      for (const lat of [-hw, -hw / 2, 0, hw / 2, hw]) {
        const p = track.pointAt(i, lat);
        const d = T.heightAt(p.x, p.z) - p.y;
        over = Math.max(over, d);
        under = Math.min(under, d);
      }
    }
    // (an airfield has no road bed: the pavement is drawn a little above the ground it lies on)
    expect(over).toBeLessThan(0.02);
    expect(under).toBeGreaterThan(-0.6);
  });

  it('has its terrain the same to the bit when the workers build it in stripes', () => {
    const same = (a: ArrayLike<number>, b: ArrayLike<number>) => {
      if (a.length !== b.length) return false;
      for (let i = 0; i < a.length; i++) if (!Object.is(a[i], b[i])) return false;
      return true;
    };
    const whole = buildTerrain(track, course.landform);
    // (each worker lays the course out again from its id)
    const n = 4, stripes = [2, 0, 3, 1].map((k) => planTerrain(new Track(COURSES.edwards.design), course.landform).stripe(k, n));
    const T = planTerrain(track, course.landform).finish(stripes);
    expect(same(T.near.heights, whole.near.heights)).toBe(true);
    expect(same(T.near.roadDist!, whole.near.roadDist!)).toBe(true);
    expect(same(T.near.edgeDist!, whole.near.edgeDist!)).toBe(true);
    expect(same(T.far.heights, whole.far.heights)).toBe(true);
  });

  it('has medals for everything that runs there, gold the hardest', () => {
    for (const id of [...CAR_ORDER, ...BIKE_ORDER, ...TRAIN_ORDER, ...JET_ORDER, 'roach'] as CarId[]) {
      const bronze = nextTarget('edwards', id, null)!;
      expect(bronze.medal, id).toBe('bronze');
      const silver = nextTarget('edwards', id, bronze.timeMs)!, gold = nextTarget('edwards', id, silver.timeMs)!;
      expect(gold.timeMs, id).toBeLessThan(silver.timeMs);
      expect(silver.timeMs, id).toBeLessThan(bronze.timeMs);
      // no placeholder left: a minute for the cockroach at Mach 1, under eight for the slowest train
      expect(gold.timeMs, id).toBeGreaterThan(60_000);
      expect(bronze.timeMs, id).toBeLessThan(520_000);
      expect(medalFor('edwards', id, gold.timeMs)).toBe('gold');
    }
    // the rivals drive what the course lists, a fighter among them
    expect(Object.values(course.rivals).some((r) => kindOf(CAR_SPECS[r.car]) === 'jet')).toBe(true);
  });
});

describe('Edwards AFB: the start grid', () => {
  const width = course.design.gridWidth!;
  const room = (...cars: CarId[]): GridEntry[] => cars.map((carId, slot) => ({ slot, carId }));

  function check(cars: CarId[]) {
    const entries = room(...cars);
    const grid = onlineGrid(entries, track.startS, width);
    const placed = entries.map((e) => ({ ...e, ...grid.get(e.slot)!, ...footprint(CAR_SPECS[e.carId]) }));
    const label = cars.join(',');
    for (const a of placed) {
      expect(Math.abs(a.lateral) + a.width / 2, label).toBeLessThanOrEqual(width / 2 - GRID_CLEARANCE + 1e-6);
      expect(a.s, label).toBeGreaterThanOrEqual(GRID_MIN_S - 1e-6);
      // on the apron's concrete, all of it
      expect(track.paveAt(Math.round(a.s)) / 2, label).toBeGreaterThanOrEqual(Math.abs(a.lateral) + a.width / 2);
      for (const b of placed) {
        if (a.slot >= b.slot) continue;
        if (a.row === b.row) expect(Math.abs(a.lateral - b.lateral) - (a.width + b.width) / 2, label).toBeGreaterThanOrEqual(GRID_CLEARANCE - 1e-6);
        else {
          const [front, rear] = a.row < b.row ? [a, b] : [b, a];
          expect(front.s - front.behind - (rear.s + rear.ahead), label).toBeGreaterThanOrEqual(GRID_ROW_GAP - 1e-6);
        }
      }
    }
    return placed;
  }

  it('a fighter stands by its wings and its real ends, not by a car\'s box', () => {
    for (const id of JET_ORDER) {
      const f = footprint(CAR_SPECS[id]), jet = CAR_SPECS[id].jet!;
      expect(f.width).toBe(jet.wing.span);
      expect(f.ahead + f.behind).toBeCloseTo(CAR_SPECS[id].size.length, 6);
      // the body's origin is between the nose wheel and the main wheels: more of the aircraft is behind it
      expect(f.behind).toBeGreaterThan(f.ahead);
    }
  });

  it('three fighters stand abreast on the ramp, five in two rows, wing tips clear', () => {
    expect(check(['f15j', 'f15c', 'su47']).map((p) => p.row)).toEqual([0, 0, 0]);
    expect(new Set(check(['f15j', 'f15c', 'su47', 'f15j', 'su47']).map((p) => p.row)).size).toBe(2);
  });

  it('keeps every room apart and on the concrete: fighters with cars, bikes, trains and the cockroach', () => {
    const pool: CarId[] = ['hayate', 'hayabusa', 'roach', 'e5', 'f15j', 'su47'];
    const walk = function* (r: CarId[]): Generator<CarId[]> {
      if (r.length) yield r;
      if (r.length < 4) for (const c of pool) yield* walk([...r, c]);
    };
    for (const cars of walk([])) check(cars);
    for (const id of [...VEHICLE_ORDER, ...JET_ORDER]) check([id, id, id, id, id]);
  });

  it('is the same on every client', () => {
    const cars: CarId[] = ['f15j', 'hayate', 'su47', 'e231', 'f15c'];
    const a = onlineGrid(room(...cars), track.startS, width);
    for (let me = 0; me < cars.length; me++) {
      const entries = room(...cars);
      const mine = [entries[me], ...entries.filter((e) => e.slot !== me).reverse()];
      expect([...onlineGrid(mine, track.startS, width)].sort((p, q) => p[0] - q[0])).toEqual([...a].sort((p, q) => p[0] - q[0]));
    }
  });
});

describe('a fighter on the ground', () => {
  it('the legend drives the F-15J from the ramp to the lakebed line without leaving the pavement', () => {
    const physics = new PhysicsWorld(track);
    const s0 = track.startS - 10;
    const sim = new VehicleSim(physics, CAR_SPECS.f15j, track.pointAt(s0), track.headingAt(s0));
    sim.gripScale = course.surface.grip;
    const ai = new AIDriver(track, new RacingLine(track), AI_PROFILES.legend);
    ai.calibrate(sim);
    const input = emptyInput();
    let t = 0, top = 0, respawns = 0;
    while (t < 260 && ai.s < track.finishS) {
      ai.update(sim, PHYSICS_DT, input);
      sim.input = input;
      sim.preStep(PHYSICS_DT);
      physics.step();
      sim.postStep(PHYSICS_DT);
      t += PHYSICS_DT;
      top = Math.max(top, sim.forwardSpeed);
      if (ai.needsRespawn || sim.isFlipped) respawns++;
    }
    physics.dispose();
    expect(ai.s).toBeGreaterThanOrEqual(track.finishS);
    expect(respawns).toBe(0);
    // the medal times were taken from this run: they hold as long as it does
    expect(t).toBeGreaterThan(175);
    expect(t).toBeLessThan(200);
    // well past the lift-off speed on the runway, and no faster than the aircraft is on the ground
    expect(top).toBeGreaterThan(CAR_SPECS.f15j.jet!.lof * 1.5);
    expect(top * 3.6).toBeLessThan(1300);
  }, 120_000);

  it('the two-seater is the heavier aircraft in a race too, and a little slower away', () => {
    const two = CAR_SPECS.f15j.jet!.liveries.find((l) => l.crew === 2)!;
    const spec = jetForLivery(CAR_SPECS.f15j, two.swatch);
    expect(spec.mass).toBe(two.mass);
    expect(spec.mass).toBeGreaterThan(CAR_SPECS.f15j.mass);
    // any other paint is the single-seater itself
    expect(jetForLivery(CAR_SPECS.f15j, CAR_SPECS.f15j.jet!.liveries[0].swatch)).toBe(CAR_SPECS.f15j);
    expect(jetForLivery(CAR_SPECS.hayate, two.swatch)).toBe(CAR_SPECS.hayate);
    // full power down the runway from a stand: the seconds to 300 km/h
    const run = (s: typeof spec) => {
      const physics = new PhysicsWorld(track);
      const at = track.zone.indexOf('runway') + 60;
      const sim = new VehicleSim(physics, s, track.pointAt(at), track.headingAt(at));
      sim.gripScale = course.surface.grip;
      const input = emptyInput();
      input.throttle = 1;
      let t = 0;
      while (t < 30 && sim.forwardSpeed < 300 / 3.6) {
        sim.input = input;
        sim.preStep(PHYSICS_DT);
        physics.step();
        sim.postStep(PHYSICS_DT);
        t += PHYSICS_DT;
      }
      physics.dispose();
      return t;
    };
    const one = run(CAR_SPECS.f15j), heavy = run(spec);
    expect(one).toBeGreaterThan(8);
    expect(one).toBeLessThan(16);
    expect(heavy).toBeGreaterThan(one);
    expect(heavy).toBeLessThan(one * 1.05);
  }, 60_000);
});

describe('the take-off after the finish', () => {
  const fly = (id: CarId, speed: number) => {
    const d = new Departure(CAR_SPECS[id]);
    d.rotate(new Vector3(10, 700, -20), 0.6, speed);
    const log: { t: number; h: number; gear: number; pitch: number; speed: number; stage: string }[] = [];
    for (let t = 0; t < 60 && d.stage !== 'gone'; t += PHYSICS_DT) {
      d.step(PHYSICS_DT);
      log.push({ t, h: d.height, gear: d.gear, pitch: d.pitch, speed: d.speed, stage: d.stage });
    }
    return { d, log };
  };

  it('rotates, leaves the ground at its lift-off speed, takes the gear up and climbs away', () => {
    for (const id of JET_ORDER) {
      const jet = CAR_SPECS[id].jet!;
      const { d, log } = fly(id, jet.vr);
      expect(d.stage, id).toBe('gone');
      const off = log.find((x) => x.stage === 'climb')!;
      // a few seconds on the main wheels, nose up, until the wing carries
      expect(off.t, id).toBeGreaterThan(1);
      expect(off.t, id).toBeLessThan(5);
      expect(off.speed, id).toBeGreaterThanOrEqual(jet.lof);
      let last = 0, lastGear = 0;
      for (const x of log) {
        // never back into the ground, the gear only ever goes up, the nose never past 45°
        expect(x.h).toBeGreaterThanOrEqual(last - 1e-9);
        expect(x.gear).toBeGreaterThanOrEqual(lastGear);
        expect(x.pitch).toBeLessThan(Math.PI / 4);
        expect(Number.isFinite(x.speed)).toBe(true);
        last = x.h;
        lastGear = x.gear;
      }
      expect(lastGear, id).toBe(1);
      // out of sight: more than a kilometre up
      expect(last, id).toBeGreaterThan(1000);
      // along its heading, level across (no bank)
      const f = new Vector3(0, 0, 1).applyQuaternion(d.quaternion), left = new Vector3(1, 0, 0).applyQuaternion(d.quaternion);
      expect(Math.atan2(f.x, f.z)).toBeCloseTo(0.6, 6);
      expect(left.y).toBeCloseTo(0, 6);
      expect(f.y).toBeGreaterThan(0.15);
    }
  });

  it('takes the aircraft over from the simulation without a standstill: its velocity goes on, step by step', () => {
    // as Game.depart hands it over: the path begun where the body is, this step's travel at once, then carried.
    // (Handed over where it stood, the body's velocity read zero for a step: the other players got that as a hit
    // and saw the aircraft stop and jump on.)
    const physics = new PhysicsWorld(track);
    const at = track.zone.indexOf('runway') + 800;
    const sim = new VehicleSim(physics, CAR_SPECS.f15j, track.pointAt(at), track.headingAt(at));
    sim.reset(track.pointAt(at), track.headingAt(at), 90);
    const input = emptyInput();
    input.throttle = 1;
    const step = () => {
      sim.input = input;
      sim.preStep(PHYSICS_DT);
      physics.step();
      sim.postStep(PHYSICS_DT);
    };
    for (let k = 0; k < 60; k++) step();
    const before = sim.velocity.length();
    expect(before).toBeGreaterThan(85);
    const d = new Departure(CAR_SPECS.f15j);
    d.rotate(sim.position, Math.atan2(sim.forward.x, sim.forward.z), sim.speed);
    d.step(PHYSICS_DT);
    sim.carry(d.position, d.quaternion, { spool: 1, afterburner: 1 });
    const from = sim.position.clone();
    let slowest = Infinity, fastest = 0;
    for (let k = 0; k < 240; k++) {
      step();
      slowest = Math.min(slowest, sim.velocity.length());
      fastest = Math.max(fastest, sim.velocity.length());
      d.step(PHYSICS_DT);
      sim.carry(d.position, d.quaternion, { spool: 1, afterburner: 1 });
    }
    physics.dispose();
    expect(slowest).toBeGreaterThan(before * 0.97);
    expect(fastest).toBeLessThan(before + 40);
    // two seconds on at that speed and more
    expect(sim.position.distanceTo(from)).toBeGreaterThan(before * 1.95);
  });

  it('from far above the lift-off speed it is off at once', () => {
    const { log } = fly('f15j', 220);
    expect(log.find((x) => x.stage === 'climb')!.t).toBeLessThan(0.6);
  });

  it('is told to the other players: nobody can touch it, the gear goes up on their screens too', () => {
    const st: NetState = { seq: 7, t: 1000, age: 4, p: [1, 2, 3], q: [0, 0, 0, 1], vel: [0, 0, 0], acc: [0, 0, 0], w: [0, 0, 0], st: 0, s: 12_000, br: 1, ep: 3, th: 1, rp: 0.99 };
    expect(decodeState(encodeState(st))!.dep).toBeUndefined();
    for (const dep of [1, 2, 3]) {
      const back = decodeState(encodeState({ ...st, dep }))!;
      // (beside the brake flag and the respawn count it shares a number with)
      expect([back.dep, back.br, back.ep]).toEqual([dep, 1, 3]);
    }
    // the flames on their screens come from the engine speed in the packet
    expect(enginesAt(jetRpm(0, 0))).toEqual({ spool: 0, afterburner: 0 });
    expect(enginesAt(jetRpm(1, 1))).toEqual({ spool: 1, afterburner: 1 });
    expect(enginesAt(jetRpm(0.5, 0)).spool).toBeCloseTo(0.5, 6);
  });
});
