// The tanks' figures out of the game's own simulation (Node, no browser), to hold against the published ones:
//   TANKS=1 npx tsx tools/tank-figures.ts [ids]          per tank: 0→32 and 0→50 km/h, top speed forward and in
//                                                         reverse, the neutral turn's rate, one shot's recoil (the
//                                                         hull's speed backwards and its pitch), the gun's laying
//                                                         (a half turn of the turret, the gun through its arc), and
//                                                         the ballistic table (time of flight, speed left, fall,
//                                                         superelevation at 500…3000 m)
//   TANKS=1 npx tsx tools/tank-figures.ts --courses      per course: how far the land stands over the road along
//                                                         its middle (a shell meets the land by `terrain.heightAt`:
//                                                         land over the gun would end every shot at the muzzle),
//                                                         and a shot fired level down the road every 200 m: how
//                                                         far it flies and what it meets
import { Quaternion, Vector3 } from 'three';
import { RAPIER, initRapier, groups, GROUP_GROUND, GROUP_CAR, PHYSICS_DT, PhysicsWorld } from '../src/game/vehicle/PhysicsWorld';
import { VehicleSim, emptyInput } from '../src/game/vehicle/VehicleSim';
import { CAR_SPECS, type CarId } from '../src/game/vehicle/carSpecs';
import { TANK_ORDER } from '../src/game/vehicle/tanks';
import { Gunnery, type GunneryHost } from '../src/game/weapons/Gunnery';
import { dropAt, flightTime, recoilOf, superelevation, dragOf, gunPose } from '../src/game/weapons/gun';
import { Shells, newShell } from '../src/game/weapons/ballistics';
import { GameShellWorld } from '../src/game/weapons/world';
import { ALL_COURSES, COURSES } from '../src/game/track/courses';
import { Track } from '../src/game/track/Track';
import { buildTerrain } from '../src/game/track/terrain';

await initRapier();
const args = process.argv.slice(2);
const DEG = 180 / Math.PI;

function pad() {
  const world = new RAPIER.World({ x: 0, y: -9.81, z: 0 });
  world.timestep = PHYSICS_DT;
  world.createCollider(RAPIER.ColliderDesc.cuboid(30000, 1, 30000).setTranslation(0, -1, 0).setCollisionGroups(groups(GROUP_GROUND, GROUP_CAR)));
  return world;
}

const quiet: GunneryHost = { fired() {}, struck() {}, respawnRival() {}, respawnSelf() {}, send() {} };

function run(id: CarId, seconds: number, drive: (t: number, v: VehicleSim) => { throttle?: number; brake?: number; steer?: number }, each?: (t: number, v: VehicleSim) => void) {
  const world = pad();
  const v = new VehicleSim({ world } as unknown as PhysicsWorld, CAR_SPECS[id], new Vector3(0, 0, 0), 0);
  const input = emptyInput();
  for (let t = 0; t < seconds; t += PHYSICS_DT) {
    Object.assign(input, { throttle: 0, brake: 0, steer: 0 }, drive(t, v));
    v.input = input;
    v.preStep(PHYSICS_DT);
    world.step();
    v.postStep(PHYSICS_DT);
    each?.(t, v);
  }
  world.free();
}

if (!args.includes('--courses')) {
  const ids = (args.length ? args : TANK_ORDER) as CarId[];
  for (const id of ids) {
    const spec = CAR_SPECS[id], tank = spec.tank!, gun = tank.gun;
    let t32 = NaN, t50 = NaN, top = 0;
    run(id, 90, () => ({ throttle: 1 }), (t, v) => {
      const kmh = v.forwardSpeed * 3.6;
      if (Number.isNaN(t32) && kmh >= 32) t32 = t;
      if (Number.isNaN(t50) && kmh >= 50) t50 = t;
      top = Math.max(top, kmh);
    });
    let back = 0;
    run(id, 60, () => ({ brake: 1 }), (_t, v) => (back = Math.min(back, v.forwardSpeed * 3.6)));
    let pivot = 0;
    run(id, 8, (t) => ({ steer: t > 1 ? 1 : 0 }), (t, v) => t > 6 && (pivot = Math.max(pivot, Math.abs(v.yawRate) * DEG)));
    // one shot over the front, standing: what the hull does
    let dv = 0, pitch = 0, half = NaN, arc = NaN;
    {
      const world = pad();
      const v = new VehicleSim({ world } as unknown as PhysicsWorld, spec, new Vector3(0, 0, 0), 0);
      const g = new Gunnery({ world } as unknown as PhysicsWorld, () => 0, quiet);
      g.player(v);
      const input = emptyInput();
      input.handbrake = false;
      const hands = { dYaw: 0, dPitch: 0, stabilised: false, recentre: false };
      for (let t = 0; t < 40; t += PHYSICS_DT) {
        v.input = input;
        v.preStep(PHYSICS_DT);
        world.step();
        v.postStep(PHYSICS_DT);
        // 2 s: the shot; 6 s: the sight thrown half round; 20 s: back to the front and up to the top of the arc
        hands.dYaw = Math.abs(t - 6) < PHYSICS_DT / 2 ? Math.PI : 0;
        hands.dPitch = Math.abs(t - 20) < PHYSICS_DT / 2 ? 1 : Math.abs(t - 19) < PHYSICS_DT / 2 ? -1 : 0;
        hands.recentre = Math.abs(t - 18) < PHYSICS_DT / 2;
        g.step(PHYSICS_DT, v, hands, Math.abs(t - 2) < PHYSICS_DT / 2, t * 1000);
        g.fly(PHYSICS_DT);
        if (t > 2 && t < 4) {
          dv = Math.min(dv, v.forwardSpeed);
          pitch = Math.max(pitch, Math.asin(Math.max(-1, Math.min(1, v.forward.y))) * DEG);
        }
        const c = g.control!;
        if (t > 6 && Number.isNaN(half) && Math.abs(Math.abs(c.gun.yaw) - Math.PI) < 0.01) half = t - 6;
        if (t > 20 && Number.isNaN(arc) && c.gun.pitch * DEG > gun.elevation[1] - 0.05) arc = t - 20;
      }
      world.free();
    }
    console.log(`\n${id}  ${tank.gun.name}`);
    console.log(`  0→32 km/h ${t32.toFixed(1)} s   0→50 km/h ${t50.toFixed(1)} s   top ${top.toFixed(1)} km/h   reverse ${(-back).toFixed(1)} km/h (sheet ${tank.reverseSpeed})   neutral turn ${pivot.toFixed(1)} °/s (spec ${tank.pivotRate})`);
    console.log(`  shot: momentum ${(recoilOf(gun) / 1000).toFixed(1)} kN·s → hull ${(dv * 100).toFixed(1)} cm/s back at most, nose up ${pitch.toFixed(2)}° at most   turret half round ${half.toFixed(1)} s (${gun.traverse} °/s)   gun ${gun.elevation[0]}°→${gun.elevation[1]}° in ${arc.toFixed(1)} s (${gun.elevationRate} °/s)`);
    console.log('  range m   flight s   speed m/s   fall m   superelevation mrad');
    for (const r of [500, 1000, 2000, 3000]) {
      const speed = gun.muzzleVelocity * Math.exp(-dragOf(gun) * r);
      console.log(`  ${String(r).padStart(7)}   ${flightTime(gun, r).toFixed(3).padStart(8)}   ${speed.toFixed(0).padStart(9)}   ${dropAt(gun, r).toFixed(2).padStart(6)}   ${(superelevation(gun, r) * 1000).toFixed(2).padStart(8)}`);
    }
  }
} else {
  const spec = CAR_SPECS.leopard2a5;
  for (const id of ALL_COURSES) {
    const course = COURSES[id];
    const track = new Track(course.design);
    const terrain = buildTerrain(track, course.landform);
    const physics = new PhysicsWorld(track);
    const world = new GameShellWorld(physics, terrain.heightAt);
    let over = -Infinity, overS = 0, covered = 0, n = 0;
    for (let s = 0; s < track.length; s += 5) {
      const p = track.pointAt(s, 0);
      const d = terrain.heightAt(p.x, p.z) - p.y;
      n++;
      if (d > 0.3) covered++;
      if (d > over) {
        over = d;
        overS = s;
      }
    }
    // a round fired level down the road every 200 m, from where the gun is
    const shells = new Shells();
    const pose = { trunnion: new Vector3(), muzzle: new Vector3(), dir: new Vector3() };
    const stand = new VehicleSim(physics, spec, track.pointAt(track.startS - 30), track.headingAt(track.startS - 30));
    world.bodies.set(0, stand.body);
    const ride = stand.rideHeight;
    let atMuzzle = 0, shots = 0, sum = 0, least = Infinity;
    for (let s = track.startS; s < track.finishS; s += 200) {
      const p = track.pointAt(s, 0).clone();
      p.y += ride;
      const q = new Quaternion().setFromAxisAngle(new Vector3(0, 1, 0), track.headingAt(s));
      gunPose(spec, ride, p, q, 0, 0, pose);
      const from = pose.muzzle.clone();
      shells.add(newShell(0, ++shots, pose.muzzle, pose.dir.clone().multiplyScalar(spec.tank!.gun.muzzleVelocity), dragOf(spec.tank!.gun)));
      let flew = NaN;
      for (let k = 0; k < 720 && Number.isNaN(flew); k++) shells.step(PHYSICS_DT, world, (i) => (flew = i.point.distanceTo(from)));
      shells.clear();
      if (Number.isNaN(flew)) continue;
      if (flew < 1) atMuzzle++;
      sum += flew;
      least = Math.min(least, flew);
    }
    console.log(`${id.padEnd(18)} length ${track.length.toFixed(0).padStart(6)} m   land over the road's middle: at most ${over.toFixed(2)} m (s=${overS}), over 0.3 m on ${((covered / n) * 100).toFixed(1)} % of it   level shots down the road: ${shots}, ended at the muzzle ${atMuzzle}, flew ${least.toFixed(0)} m at least, ${(sum / shots).toFixed(0)} m on average`);
    physics.dispose();
  }
}
