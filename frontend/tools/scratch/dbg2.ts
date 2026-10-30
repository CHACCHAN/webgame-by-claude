import { Vector3 } from 'three';
import { RAPIER, initRapier, groups, GROUP_GROUND, GROUP_CAR, PHYSICS_DT } from '../../src/game/vehicle/PhysicsWorld';
import { VehicleSim, emptyInput } from '../../src/game/vehicle/VehicleSim';
import { CAR_SPECS } from '../../src/game/vehicle/carSpecs';
await initRapier();
const world = new RAPIER.World({ x: 0, y: -9.81, z: 0 });
world.timestep = PHYSICS_DT;
world.createCollider(RAPIER.ColliderDesc.cuboid(5000, 1, 5000).setTranslation(0, -1, 0).setCollisionGroups(groups(GROUP_GROUND, GROUP_CAR)));
const v = new VehicleSim({ world } as any, CAR_SPECS.hayate, new Vector3(0, 0, 0), 0);
v.reset(new Vector3(0,0,0), 0, 60/3.6);
v.assist = 0;
const inp = emptyInput();
let t = 0;
for (let k = 0; k < 120 * 2; k++) {
  inp.throttle = 0.3; inp.steer = t > 0.2 && t < 1.2 ? -0.8 : 0; inp.handbrake = t > 0.2 && t < 0.8;
  v.input = inp; v.preStep(PHYSICS_DT); world.step(); v.postStep(PHYSICS_DT); t += PHYSICS_DT;
  if (k % 12 === 0) {
    const hd = Math.atan2(v.forward.x, v.forward.z) * 57.3, vh = Math.atan2(v.velocity.x, v.velocity.z) * 57.3;
    const av = v.body.angvel();
    console.log(t.toFixed(2), 'kmh', (v.speed*3.6).toFixed(0), 'heading', hd.toFixed(1), 'velDir', vh.toFixed(1), 'slip', (v.slipAngle*57.3).toFixed(1), 'yawRate', av.y.toFixed(2), 'steer', (v.wheels[0].steer*57.3).toFixed(1), 'wheelSlip', v.wheels.map(w=>(w.slipAngle*57.3).toFixed(0)).join('/'));
  }
}
