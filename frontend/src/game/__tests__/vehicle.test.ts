import { beforeAll, describe, expect, it } from 'vitest';
import { Vector3 } from 'three';
import { RAPIER, initRapier, groups, GROUP_GROUND, GROUP_CAR, GROUP_WALL, PHYSICS_DT, PhysicsWorld } from '../vehicle/PhysicsWorld';
import { VehicleSim, emptyInput, type VehicleInput } from '../vehicle/VehicleSim';
import { CAR_ORDER, CAR_SPECS, type CarId } from '../vehicle/carSpecs';
import { TRAIN_INFO, TRAIN_ORDER } from '../vehicle/trains';
import { Track } from '../track/Track';
import { OBORO_DOWNHILL } from '../track/courseDesign';
import { RacingLine } from '../ai/RacingLine';
import { AIDriver, AI_PROFILES } from '../ai/AIDriver';
import { ProxyCar } from '../net/ProxyCar';
import { Quaternion } from 'three';

beforeAll(async () => {
  await initRapier();
});

function flatPad() {
  const world = new RAPIER.World({ x: 0, y: -9.81, z: 0 });
  world.timestep = PHYSICS_DT;
  // 40 km square: a Shinkansen at full power covers kilometres
  world.createCollider(RAPIER.ColliderDesc.cuboid(20000, 1, 20000).setTranslation(0, -1, 0).setCollisionGroups(groups(GROUP_GROUND, GROUP_CAR)));
  return { world } as unknown as PhysicsWorld;
}

function drive(car: CarId, seconds: number, control: (t: number, v: VehicleSim, i: VehicleInput) => void, speed = 0) {
  const phys = flatPad();
  const v = new VehicleSim(phys, CAR_SPECS[car], new Vector3(), 0);
  if (speed) v.reset(new Vector3(), 0, speed);
  const input = emptyInput();
  let maxSlip = 0;
  for (let t = 0; t < seconds; t += PHYSICS_DT) {
    control(t, v, input);
    v.input = input;
    v.preStep(PHYSICS_DT);
    phys.world.step();
    v.postStep(PHYSICS_DT);
    maxSlip = Math.max(maxSlip, Math.abs(v.slipAngle));
  }
  phys.world.free();
  return { v, maxSlip };
}

describe('VehicleSim', () => {
  it.each(CAR_ORDER)('%s settles on its suspension and accelerates', (car) => {
    const { v } = drive(car, 8, (_t, _v, i) => (i.throttle = 1));
    expect(v.speed * 3.6).toBeGreaterThan(80);
    expect(v.up.y).toBeGreaterThan(0.95);
    expect(v.wheels.every((w) => w.grounded)).toBe(true);
  });

  it('stops from 100 km/h within a sensible distance', () => {
    // release the pedal once stopped (holding it would engage reverse)
    const { v } = drive('hayate', 6, (_t, car, i) => (i.brake = car.forwardSpeed > 0.3 ? 1 : 0), 100 / 3.6);
    expect(v.speed).toBeLessThan(0.5);
    expect(Math.abs(v.position.z)).toBeLessThan(50);
  });

  it('handbrake + steer starts a slide, and the assist prevents spinning out', () => {
    const { maxSlip } = drive('hayate', 3, (t, _v, i) => {
      i.throttle = 0.5;
      i.steer = t > 0.2 && t < 1.2 ? -0.8 : 0;
      i.handbrake = t > 0.2 && t < 0.6;
    }, 60 / 3.6);
    expect(maxSlip).toBeGreaterThan(0.3);
    const abuse = drive('shiden', 4, (_t, _v, i) => { i.throttle = 1; i.steer = 1; }, 80 / 3.6);
    expect(abuse.maxSlip).toBeLessThan(1.6);
  });

  it('a 45° wall hit at 100 km/h glances off: no bounce, not spun round, not thrown out into the road', () => {
    for (const car of ['hayate', 's15', 'shiden'] as CarId[]) {
      const world = new RAPIER.World({ x: 0, y: -9.81, z: 0 });
      world.timestep = PHYSICS_DT;
      world.createCollider(RAPIER.ColliderDesc.cuboid(5000, 1, 5000).setTranslation(0, -1, 0).setCollisionGroups(groups(GROUP_GROUND, GROUP_CAR)));
      // a long wall along z at x = 0, the course walls' material
      world.createCollider(RAPIER.ColliderDesc.cuboid(0.2, 1, 2000).setTranslation(-0.2, 1, 0).setCollisionGroups(groups(GROUP_WALL, GROUP_CAR)).setFriction(0.05).setRestitution(0.15));
      const phys = { world } as unknown as PhysicsWorld;
      const heading = -Math.PI / 4;
      const v = new VehicleSim(phys, CAR_SPECS[car], new Vector3(4, 0, 0), heading);
      v.reset(new Vector3(4, 0, 0), heading, 100 / 3.6);
      const input = emptyInput();
      input.throttle = 0.4;
      let hit = -1, bounce = 0, yaw0 = 0, yaw1 = 0, off = 0;
      const yawOf = () => { const f = new Vector3(0, 0, 1).applyQuaternion(v.quaternion); return Math.atan2(f.x, f.z); };
      for (let t = 0; t < 3; t += PHYSICS_DT) {
        v.input = input;
        v.preStep(PHYSICS_DT);
        world.step();
        v.postStep(PHYSICS_DT);
        if (hit < 0 && v.impact > 0) { hit = t; yaw0 = yawOf(); }
        if (hit >= 0 && t - hit <= 1) { bounce = Math.max(bounce, v.velocity.x); yaw1 = yawOf(); off = v.position.x; }
      }
      world.free();
      expect(hit).toBeGreaterThan(0);
      // (before: S15 and RX-7 bounced off at ~35 km/h, turned 92° and ended 6 m from the wall)
      expect(bounce * 3.6).toBeLessThan(5);
      expect(Math.abs(yaw1 - yaw0)).toBeLessThan((55 * Math.PI) / 180);
      expect(off).toBeLessThan(2);
    }
  });

  it('a power slide (a stab of the throttle mid-corner) settles at a holdable angle, and the 4WD cars drift too', () => {
    const slide = (car: CarId) => {
      let held = 0, peak = 0;
      drive(car, 4, (t, v, i) => {
        i.throttle = t < 0.4 ? 0.3 : 1;
        i.steer = t < 2.5 ? 0.7 : 0;
        const s = Math.abs((v.slipAngle * 180) / Math.PI);
        if (s > 15 && v.speed > 5) held += PHYSICS_DT;
        peak = Math.max(peak, s);
      }, 70 / 3.6);
      return { held, peak };
    };
    for (const car of ['hayate', 's15', 'shiden'] as CarId[]) {
      const { held, peak } = slide(car);
      // (before: 73–77°, at the edge of a spin)
      expect(held).toBeGreaterThan(2);
      expect(peak).toBeLessThan(60);
    }
    // (before: the Impreza and the R34 could not power over at all)
    for (const car of ['raijin', 'r34'] as CarId[]) expect(slide(car).held).toBeGreaterThan(1.5);
  });

  it('a bend taken flat out at full lock, or braked into, stays a grip corner (no slide unless asked for)', () => {
    const corner = (car: CarId, kmh: number, control: (t: number, i: VehicleInput) => void) => {
      let peak = 0;
      drive(car, 3, (t, v, i) => {
        control(t, i);
        peak = Math.max(peak, Math.abs((v.slipAngle * 180) / Math.PI));
      }, kmh / 3.6);
      return peak;
    };
    for (const car of CAR_ORDER) {
      // keyboard style: floored on the straight, then full lock (before: every car slid to 32–54°)
      expect(corner(car, 60, (t, i) => { i.throttle = 1; i.steer = t > 0.5 ? 1 : 0; })).toBeLessThan(15);
      // braking into the bend with the wheel turned (before: 25–47° at 90 km/h)
      expect(corner(car, 90, (t, i) => { i.brake = t < 0.6 ? 0.7 : 0; i.steer = 0.8; i.throttle = t > 0.6 ? 0.6 : 0; })).toBeLessThan(15);
    }
    // a short tap of the brake with a big steer is still a feint into a drift
    expect(corner('s15', 70, (t, i) => { i.brake = t < 0.3 ? 0.8 : 0; i.steer = 0.8; i.throttle = t > 0.3 ? 0.9 : 0; })).toBeGreaterThan(30);
  });

  it('the cockroach (joke entry) out-accelerates, outruns and outbrakes every other vehicle', () => {
    const perf = (car: CarId) => {
      let t100 = Infinity, vmax = 0;
      drive(car, 60, (t, v, i) => {
        i.throttle = 1;
        if (t100 === Infinity && v.speed * 3.6 >= 100) t100 = t;
        vmax = Math.max(vmax, v.speed * 3.6);
      });
      // braking distance from 100 km/h (a held brake would then engage reverse)
      let stop = Infinity;
      drive(car, 25, (t, v, i) => {
        i.brake = 1;
        // (the derived speed is set by the first step)
        if (stop === Infinity && t > 0.1 && v.speed < 0.5) stop = Math.abs(v.position.z);
      }, 100 / 3.6);
      return { t100, vmax, stop };
    };
    const roach = perf('roach');
    expect(roach.t100).toBeLessThan(2);
    expect(roach.vmax).toBeGreaterThan(380);
    expect(roach.stop).toBeLessThan(25);
    for (const car of [...CAR_ORDER, 'e5'] as CarId[]) {
      const p = perf(car);
      expect(roach.t100).toBeLessThan(p.t100);
      expect(roach.vmax).toBeGreaterThan(p.vmax);
      expect(roach.stop).toBeLessThan(p.stop);
    }
  });

  it('held on the line it revs but neither moves nor drops into reverse', () => {
    for (const car of [...CAR_ORDER, ...TRAIN_ORDER, 'roach'] as CarId[]) {
      let maxRpm = 0;
      const { v } = drive(car, 4, (_t, sim, i) => {
        i.hold = true;
        i.handbrake = true;
        i.throttle = 0.8;
        maxRpm = Math.max(maxRpm, sim.rpm);
      });
      expect(v.gear).not.toBe(-1);
      expect(Math.abs(v.forwardSpeed)).toBeLessThan(0.2);
      if (!CAR_SPECS[car].engine.electric) expect(maxRpm).toBeGreaterThan(3000);
    }
  });

  it('reverses when braking from standstill', () => {
    const { v } = drive('raijin', 3, (_t, _v, i) => (i.brake = 1));
    expect(v.gear).toBe(-1);
    expect(v.forwardSpeed).toBeLessThan(-1);
  });
});

describe('trains (joke entries) perform like the real ones on level ground', () => {
  it.each(TRAIN_ORDER)('%s: starting acceleration, top speed, emergency brake', (id) => {
    const t = TRAIN_INFO[id];
    // 0 → 30 km/h is inside the constant-torque region: the starting acceleration (km/h/s)
    let t30 = 0;
    drive(id, 30, (time, car, i) => {
      i.throttle = 1;
      if (!t30 && car.forwardSpeed * 3.6 >= 30) t30 = time;
    });
    expect(t30).toBeGreaterThan(0);
    expect(30 / t30).toBeGreaterThan(t.accel * 0.85);
    expect(30 / t30).toBeLessThan(t.accel * 1.15);
    // flat out it settles around the design top speed (the motor runs out of revs there)
    // (a Shinkansen needs minutes to get there: the peak speed counts)
    let peak = 0;
    drive(id, t.vmax > 200 ? 300 : 150, (_t, car, i) => {
      i.throttle = 1;
      peak = Math.max(peak, car.forwardSpeed * 3.6);
    });
    expect(peak).toBeGreaterThan(t.vmax * 0.85);
    expect(peak).toBeLessThan(t.vmax * 1.08);
    // full brake from 80 km/h: the emergency rate (km/h/s)
    let tStop = 0;
    drive(id, 30, (time, car, i) => {
      i.brake = car.forwardSpeed > 0.3 ? 1 : 0;
      if (!tStop && time > 0.1 && car.forwardSpeed <= 0.3) tStop = time;
    }, 80 / 3.6);
    expect(80 / tStop).toBeGreaterThan(t.brake[1] * 0.9);
    expect(80 / tStop).toBeLessThan(t.brake[1] * 1.25);
  });
});

describe('AI on the course', () => {
  it('the legend completes the full downhill without respawning', () => {
    const track = new Track(OBORO_DOWNHILL);
    const physics = new PhysicsWorld(track);
    const start = track.pointAt(track.startS - 10);
    const v = new VehicleSim(physics, CAR_SPECS.shiden, start, track.headingAt(track.startS - 10));
    const ai = new AIDriver(track, new RacingLine(track), AI_PROFILES.legend);
    ai.calibrate(v);
    const input = emptyInput();
    let t = 0;
    while (t < 200 && ai.s < track.finishS) {
      ai.update(v, PHYSICS_DT, input);
      v.input = input;
      v.preStep(PHYSICS_DT);
      physics.step();
      v.postStep(PHYSICS_DT);
      t += PHYSICS_DT;
      expect(v.isFlipped).toBe(false);
    }
    expect(ai.s).toBeGreaterThanOrEqual(track.finishS);
    expect(t).toBeLessThan(130);
    physics.dispose();
  });

  it('closes up on a slow car ahead in its lane without running into it', () => {
    const track = new Track(OBORO_DOWNHILL);
    const line = new RacingLine(track);
    const physics = new PhysicsWorld(track);
    const s0 = track.startS + 10;
    const v = new VehicleSim(physics, CAR_SPECS.raijin, track.pointAt(s0, line.offsetAt(s0)), track.headingAt(s0));
    v.reset(track.pointAt(s0, line.offsetAt(s0)), track.headingAt(s0), 25);
    const ai = new AIDriver(track, line, AI_PROFILES.legend);
    ai.calibrate(v);
    const input = emptyInput();
    // a car crawling along the racing line 30 m ahead (8 m/s)
    let oppS = s0 + 30, closest = Infinity, overlap = false;
    for (let t = 0; t < 8; t += PHYSICS_DT) {
      oppS += 8 * PHYSICS_DT;
      const oppLat = line.offsetAt(oppS);
      ai.opponent = { s: oppS, lateral: oppLat, speed: 8 };
      ai.update(v, PHYSICS_DT, input);
      v.input = input;
      v.preStep(PHYSICS_DT);
      physics.step();
      v.postStep(PHYSICS_DT);
      const p = track.project(v.position.x, v.position.y, v.position.z);
      const gap = oppS - p.s;
      if (Math.abs(oppLat - p.lateral) < 1.8) {
        if (gap > 0) closest = Math.min(closest, gap);
        if (Math.abs(gap) < 4.4) overlap = true; // the two bodies would be inside each other
      }
    }
    expect(closest).toBeLessThan(12); // it did catch up
    expect(overlap).toBe(false); // but slowed or pulled out instead of ploughing into it
    physics.dispose();
  });
});

describe('car to car contact', () => {
  it('a car running into a parked one shoves it forward and they never interpenetrate', () => {
    const phys = flatPad();
    const parked = new VehicleSim(phys, CAR_SPECS.hayate, new Vector3(0, 0, 12), 0);
    const rammer = new VehicleSim(phys, CAR_SPECS.raijin, new Vector3(0, 0, 0), 0);
    rammer.reset(new Vector3(0, 0, 0), 0, 20);
    const go = emptyInput();
    go.throttle = 1;
    const idle = emptyInput();
    let minGap = Infinity;
    for (let t = 0; t < 2.5; t += PHYSICS_DT) {
      rammer.input = go;
      parked.input = idle;
      rammer.preStep(PHYSICS_DT);
      parked.preStep(PHYSICS_DT);
      phys.world.step();
      rammer.postStep(PHYSICS_DT);
      parked.postStep(PHYSICS_DT);
      // nose to tail (within a car's width across): once the parked car is shoved aside, centres may come closer
      if (Math.abs(parked.position.x - rammer.position.x) < (CAR_SPECS.hayate.size.width + CAR_SPECS.raijin.size.width) / 2) {
        minGap = Math.min(minGap, parked.position.z - rammer.position.z);
      }
    }
    // the parked car was pushed down the road
    expect(parked.position.z).toBeGreaterThan(16);
    expect(parked.speed).toBeGreaterThan(3);
    // and the bodies stayed apart (about the two half lengths)
    expect(minGap).toBeGreaterThan((CAR_SPECS.hayate.size.length + CAR_SPECS.raijin.size.length) / 2 - 0.4);
    phys.world.free();
  });
});

describe('online stand-in car', () => {
  it('takes a hit with real mass and then returns to its network position', () => {
    const phys = flatPad();
    const probe = new VehicleSim(phys, CAR_SPECS.supra, new Vector3(0, 0, -50), 0);
    const target = new Vector3(0, probe.rideHeight, 14);
    probe.dispose();
    const proxy = new ProxyCar(phys, CAR_SPECS.supra, target, new Quaternion());
    const rammer = new VehicleSim(phys, CAR_SPECS.s15, new Vector3(0, 0, 0), 0);
    rammer.reset(new Vector3(0, 0, 0), 0, 20);
    const go = emptyInput();
    go.throttle = 1;
    let pushed = 0, minGap = Infinity, slowest = Infinity;
    for (let t = 0; t < 4; t += PHYSICS_DT) {
      // the remote car is parked: network target and velocity stay put
      proxy.drive(target, new Quaternion(), new Vector3());
      rammer.input = t < 1.2 ? go : emptyInput();
      rammer.preStep(PHYSICS_DT);
      phys.world.step();
      rammer.postStep(PHYSICS_DT);
      pushed = Math.max(pushed, proxy.position.distanceTo(target));
      minGap = Math.min(minGap, proxy.position.z - rammer.position.z);
      if (t > 0.3) slowest = Math.min(slowest, rammer.forwardSpeed);
    }
    expect(slowest).toBeLessThan(12); // the rammer was stopped by a car-sized mass
    expect(pushed).toBeGreaterThan(0.15); // ...which gave way a little
    expect(proxy.position.distanceTo(target)).toBeLessThan(0.3); // and went back to its network track
    expect(minGap).toBeGreaterThan((CAR_SPECS.supra.size.length + CAR_SPECS.s15.size.length) / 2 - 0.4);
    phys.world.free();
  });
});
