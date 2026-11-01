import { beforeAll, describe, expect, it } from 'vitest';
import { Vector3 } from 'three';
import { RAPIER, initRapier, groups, GROUP_GROUND, GROUP_CAR, PHYSICS_DT, PhysicsWorld } from '../vehicle/PhysicsWorld';
import { VehicleSim, emptyInput, type VehicleInput } from '../vehicle/VehicleSim';
import { CAR_ORDER, CAR_SPECS, type CarId } from '../vehicle/carSpecs';
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
  world.createCollider(RAPIER.ColliderDesc.cuboid(4000, 1, 4000).setTranslation(0, -1, 0).setCollisionGroups(groups(GROUP_GROUND, GROUP_CAR)));
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

  it('reverses when braking from standstill', () => {
    const { v } = drive('raijin', 3, (_t, _v, i) => (i.brake = 1));
    expect(v.gear).toBe(-1);
    expect(v.forwardSpeed).toBeLessThan(-1);
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
      minGap = Math.min(minGap, parked.position.z - rammer.position.z);
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
