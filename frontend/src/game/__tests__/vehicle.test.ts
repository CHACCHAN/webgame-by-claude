import { beforeAll, describe, expect, it } from 'vitest';
import { Vector3 } from 'three';
import { RAPIER, initRapier, groups, GROUP_GROUND, GROUP_CAR, PHYSICS_DT, PhysicsWorld } from '../vehicle/PhysicsWorld';
import { VehicleSim, emptyInput, type VehicleInput } from '../vehicle/VehicleSim';
import { CAR_ORDER, CAR_SPECS, type CarId } from '../vehicle/carSpecs';
import { Track } from '../track/Track';
import { OBORO_DOWNHILL } from '../track/courseDesign';
import { RacingLine } from '../ai/RacingLine';
import { AIDriver, AI_PROFILES } from '../ai/AIDriver';

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
});
