import { Vector3 } from 'three';
import { RAPIER, initRapier, groups, GROUP_GROUND, GROUP_CAR, PHYSICS_DT } from '../../src/game/vehicle/PhysicsWorld';
import { VehicleSim, emptyInput } from '../../src/game/vehicle/VehicleSim';
import { CAR_SPECS } from '../../src/game/vehicle/carSpecs';
await initRapier();
const world = new RAPIER.World({ x: 0, y: -9.81, z: 0 });
world.timestep = PHYSICS_DT;
world.createCollider(RAPIER.ColliderDesc.cuboid(5000, 1, 5000).setTranslation(0, -1, 0).setCollisionGroups(groups(GROUP_GROUND, GROUP_CAR)));
const phys = { world } as any;
const v = new VehicleSim(phys, CAR_SPECS.hayate, new Vector3(0, 0, 0), 0);
const inp = emptyInput();
let t = 0;
for (let k = 0; k < 120 * 14; k++) {
  inp.throttle = 1;
  v.input = inp; v.preStep(PHYSICS_DT); world.step(); v.postStep(PHYSICS_DT); t += PHYSICS_DT;
  if (k % 60 === 0) console.log(t.toFixed(1), 'kmh', (v.speed*3.6).toFixed(0), 'gear', v.gear, 'rpm', v.rpm.toFixed(0), 'spin', (v as any).wheelSpin.toFixed(2), 'y', v.position.y.toFixed(3), 'loads', v.wheels.map(w=>w.load.toFixed(0)).join(','), 'grounded', v.wheels.map(w=>w.grounded?1:0).join(''));
}
