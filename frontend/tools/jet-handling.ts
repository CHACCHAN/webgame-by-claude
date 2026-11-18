// How a fighter turns on the ground, as the game simulates it (level, dry concrete, the field's air):
//   npx tsx tools/jet-handling.ts [ids]
// 1. Held turns: at a held speed the stick is put hard over and kept there; what the aircraft settles at: the nose
//    wheel's angle, the turn's radius, the sideways acceleration, the skid angle. Shows where the nose wheel's
//    steering ends and the rudder's begins, and that neither spins it round.
// 2. A lane change: a one-second stab of full rudder and back at speed: how far it moves sideways, the largest
//    skid angle, and whether it comes back straight by itself.
import { Vector3 } from 'three';
import { RAPIER, initRapier, groups, GROUP_GROUND, GROUP_CAR, PHYSICS_DT, type PhysicsWorld } from '../src/game/vehicle/PhysicsWorld';
import { VehicleSim, emptyInput } from '../src/game/vehicle/VehicleSim';
import { CAR_SPECS, type CarId } from '../src/game/vehicle/carSpecs';
import { JET_ORDER, type JetId } from '../src/game/vehicle/jets';

const ids = (process.argv[2]?.split(',') ?? JET_ORDER) as JetId[];
await initRapier();

function world() {
  const w = new RAPIER.World({ x: 0, y: -9.81, z: 0 });
  w.timestep = PHYSICS_DT;
  w.createCollider(RAPIER.ColliderDesc.cuboid(30000, 1, 30000).setTranslation(0, -1, 0).setCollisionGroups(groups(GROUP_GROUND, GROUP_CAR)));
  return w;
}

function make(id: JetId, speed: number) {
  const w = world();
  const v = new VehicleSim({ world: w } as unknown as PhysicsWorld, CAR_SPECS[id as CarId], new Vector3(0, 0, 0), 0);
  const input = emptyInput();
  const step = () => {
    // the throttle holds the speed (no afterburner needed below ~Mach 0.8)
    input.throttle = Math.min(1, Math.max(0, 0.4 + (speed - v.forwardSpeed) * 0.5));
    input.brake = v.forwardSpeed > speed + 3 ? 0.4 : 0;
    v.input = input;
    v.preStep(PHYSICS_DT);
    w.step();
    v.postStep(PHYSICS_DT);
  };
  for (let t = 0; t < 1.5; t += PHYSICS_DT) step();
  v.reset(new Vector3(0, v.position.y, 0), 0, speed);
  for (let t = 0; t < 3; t += PHYSICS_DT) step();
  return { w, v, input, step };
}

for (const id of ids) {
  const spec = CAR_SPECS[id as CarId];
  console.log(`\n${spec.name}`);
  console.log('  held turn (full stick):  speed   sideways   radius   skid   wing carries   spun?');
  for (const kmh of [20, 40, 60, 100, 150, 200, 300, 450, 600, 800]) {
    const speed = kmh / 3.6;
    const { w, v, input, step } = make(id, speed);
    input.steer = 1;
    let lat = 0, skid = 0, n = 0, worst = 0;
    for (let t = 0; t < 14; t += PHYSICS_DT) {
      step();
      worst = Math.max(worst, Math.abs(v.slipAngle));
      if (t > 9) {
        lat += v.forwardSpeed * Math.abs(v.yawRate);
        skid += Math.abs(v.slipAngle);
        n++;
      }
    }
    lat /= n;
    skid /= n;
    console.log(`  ${String(kmh).padStart(26)} km/h  ${(lat / 9.81).toFixed(2)} g  ${(v.forwardSpeed ** 2 / Math.max(lat, 1e-3)).toFixed(0).padStart(6)} m  ${(skid * 57.3).toFixed(1).padStart(5)}°  ${(v.liftShare * 100).toFixed(0).padStart(3)} %  ${worst > 0.6 ? 'yes (' + (worst * 57.3).toFixed(0) + '°)' : 'no'}`);
    w.free();
  }
  console.log('  one second of full rudder, then centred:  speed   moved sideways after 4 s   largest skid   skid 3 s after');
  for (const kmh of [200, 400, 700, 1000]) {
    const speed = kmh / 3.6;
    const { w, v, input, step } = make(id, speed);
    const x0 = v.position.x;
    let worst = 0;
    for (let t = 0; t < 4; t += PHYSICS_DT) {
      input.steer = t < 1 ? 1 : 0;
      step();
      worst = Math.max(worst, Math.abs(v.slipAngle));
    }
    console.log(`  ${String(kmh).padStart(47)} km/h  ${Math.abs(v.position.x - x0).toFixed(1).padStart(6)} m  ${(worst * 57.3).toFixed(1).padStart(5)}°  ${(Math.abs(v.slipAngle) * 57.3).toFixed(1).padStart(5)}°`);
    w.free();
  }
}
