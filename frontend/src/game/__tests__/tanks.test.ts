import { beforeAll, describe, expect, it } from 'vitest';
import { Quaternion, Vector3 } from 'three';
import { TURRET_STEP, GUN_STEP, decodeState, encodeState, type NetState } from '../net/codec';
import { GUN_EVENT, GunReferee, decodeGunEvent, encodeGunEvent, isGunEvent, type HitEvent, type ShotEvent } from '../net/gunEvents';
import { InputManager, emptyHands } from '../input/Input';
import { NetLink } from '../net/NetLink';
import { PeerTrack, newPose } from '../net/PeerTrack';
import type { NetTransport } from '../net/transport';
import { medalFor } from '../race/medals';
import { ALL_COURSES, TANK_MEDALS } from '../track/courses';
import { GROUP_CAR, GROUP_GROUND, GROUP_PROXY, PHYSICS_DT, RAPIER, groups, initRapier, type PhysicsWorld } from '../vehicle/PhysicsWorld';
import { VehicleSim, emptyInput } from '../vehicle/VehicleSim';
import { CAR_SPECS } from '../vehicle/carSpecs';
import { TANK_ORDER, TANK_SPECS } from '../vehicle/tanks';
import { RIVAL, SHELL_LIFE, SHELL_REACH, Shells, newShell, spent, stepShell, type Impact, type ShellWorld } from '../weapons/ballistics';
import { Gunnery, type GunneryHost } from '../weapons/Gunnery';
import { BATTLE_RANGE, GRAVITY, GunControl, dirOf, dragOf, dropAt, flightTime, gunPose, hullAngles, layGun, newGun, recoilOf, sightEye, sightOf, superelevation } from '../weapons/gun';

// The tanks' guns are checked here whether the tanks are released or not (the lists a player sees leave them out
// until then).
const RAD = Math.PI / 180;
const DT = PHYSICS_DT;
const empty: ShellWorld = { cast: () => null };
const blank = (): Impact => ({ shell: null as never, point: new Vector3(), target: null });

beforeAll(async () => {
  await initRapier();
});

describe('the tanks\' figures', () => {
  it('every tank has a gun whose figures hang together', () => {
    expect(TANK_ORDER).toEqual(['type10', 'type16', 'leopard2a5', 'm1a2', 't14']);
    for (const id of TANK_ORDER) {
      const spec = TANK_SPECS[id], t = spec.tank!, g = t.gun;
      expect([105, 120, 125], id).toContain(g.calibre);
      expect(g.muzzleVelocity, id).toBeGreaterThan(1400);
      expect(g.muzzleVelocity, id).toBeLessThan(1800);
      expect(g.reload, id).toBeGreaterThanOrEqual(3);
      expect(g.reload, id).toBeLessThanOrEqual(8);
      expect(g.elevation[0], id).toBeLessThan(0);
      expect(g.elevation[1], id).toBeGreaterThan(8);
      expect(g.zoom[0], id).toBeLessThan(g.zoom[1]);
      expect(g.ammo, id).toBeGreaterThan(10);
      // one shot takes the hull back by less than a metre a second, and by more than a hand's width
      const dv = recoilOf(g) / spec.mass;
      expect(dv, id).toBeGreaterThan(0.2);
      expect(dv, id).toBeLessThan(1);
      // the muzzle is ahead of the hull's front and above the ground, the sight's eye on the turret
      const pose = { trunnion: new Vector3(), muzzle: new Vector3(), dir: new Vector3() };
      gunPose(spec, 0, new Vector3(), new Quaternion(), 0, 0, pose);
      expect(pose.muzzle.z, id).toBeGreaterThan(t.dims.hull[0] / 2);
      expect(pose.muzzle.y, id).toBeGreaterThan(1.5);
      expect(pose.dir.z, id).toBeCloseTo(1, 9);
      const eye = sightEye(spec, 0, new Vector3(), new Quaternion(), 0, new Vector3());
      expect(eye.y, id).toBeGreaterThan(pose.muzzle.y);
      // turned a quarter to the left the gun points along +X
      gunPose(spec, 0, new Vector3(), new Quaternion(), Math.PI / 2, 0, pose);
      expect(pose.dir.x, id).toBeCloseTo(1, 9);
      expect(pose.muzzle.x, id).toBeGreaterThan(3);
    }
  });

  it('have medal times on every course, gold before silver before bronze', () => {
    for (const course of ALL_COURSES)
      for (const id of TANK_ORDER) {
        const m = TANK_MEDALS[course][id];
        expect(m.gold, `${course} ${id}`).toBeLessThan(m.silver);
        expect(m.silver, `${course} ${id}`).toBeLessThan(m.bronze);
        expect(medalFor(course, id, m.gold)).toBe('gold');
        expect(medalFor(course, id, m.bronze + 1)).toBeNull();
      }
  });

  it('a tracked tank turns on the spot on flat ground: the tracks run opposite and the hull stays where it was', () => {
    // (on the flat: the passes' grids slope downhill, and a hull that never stops never shows a neutral turn)
    for (const id of TANK_ORDER) {
      const spec = TANK_SPECS[id];
      if (!spec.tank!.pivotRate) continue;
      const world = new RAPIER.World({ x: 0, y: -9.81, z: 0 });
      world.timestep = DT;
      world.createCollider(RAPIER.ColliderDesc.cuboid(500, 1, 500).setTranslation(0, -1, 0).setCollisionGroups(groups(GROUP_GROUND, GROUP_CAR)));
      const v = new VehicleSim({ world } as unknown as PhysicsWorld, spec, new Vector3(0, 0, 0), 0);
      const input = emptyInput();
      const from = new Vector3();
      let turned = 0, rate = 0, left = 0, right = 0;
      for (let k = 0; k < Math.round(8 / DT); k++) {
        input.steer = k * DT > 1 ? 1 : 0;
        v.input = input;
        v.preStep(DT);
        world.step();
        v.postStep(DT);
        if (k * DT <= 1) from.copy(v.position);
        else turned += v.yawRate * DT;
        if (k * DT > 6) {
          rate = Math.abs(v.yawRate) / RAD;
          // as the model scrolls them (`TankModel`): the hull's speed ∓ its yaw rate × half the gauge
          left = v.forwardSpeed - (v.yawRate * spec.track) / 2;
          right = v.forwardSpeed + (v.yawRate * spec.track) / 2;
        }
      }
      expect(left * right, id).toBeLessThan(0);
      expect(rate, id).toBeGreaterThan(15);
      expect(rate, id).toBeLessThanOrEqual(spec.tank!.pivotRate);
      expect(Math.abs(turned) / RAD, id).toBeGreaterThan(100);
      expect(Math.hypot(v.position.x - from.x, v.position.z - from.z), id).toBeLessThan(1);
      world.free();
    }
  });
});

describe('laying the gun', () => {
  const info = TANK_SPECS.type10.tank!.gun;

  it('turns the turret at its rate, the short way round, and the gun within its limits', () => {
    const g = newGun(info);
    for (let t = 0; t < 1 - 1e-9; t += DT) layGun(g, info, { yaw: Math.PI / 2, pitch: 0 }, DT);
    expect(g.yaw / RAD).toBeCloseTo(info.traverse, 3);
    // from 170° left to 170° right: 20° through the back, not 340° through the front
    g.yaw = 170 * RAD;
    let through = 0;
    for (let t = 0; t < 0.25 - 1e-9; t += DT) {
      layGun(g, info, { yaw: -170 * RAD, pitch: 0 }, DT);
      through = Math.max(through, Math.abs(g.yaw));
    }
    expect(through).toBeGreaterThan(175 * RAD);
    for (let t = 0; t < 1; t += DT) layGun(g, info, { yaw: -170 * RAD, pitch: 0 }, DT);
    expect(g.yaw / RAD).toBeCloseTo(-170, 6);
    // asked far above and far below: it stops at its limits, and gets there at its rate
    for (let t = 0; t < 0.2 - 1e-9; t += DT) layGun(g, info, { yaw: g.yaw, pitch: 1 }, DT);
    expect(g.pitch / RAD).toBeCloseTo(info.elevationRate * 0.2, 3);
    for (let t = 0; t < 5; t += DT) layGun(g, info, { yaw: g.yaw, pitch: 1 }, DT);
    expect(g.pitch / RAD).toBeCloseTo(info.elevation[1], 9);
    for (let t = 0; t < 5; t += DT) layGun(g, info, { yaw: g.yaw, pitch: -1 }, DT);
    expect(g.pitch / RAD).toBeCloseTo(info.elevation[0], 9);
  });

  it('loads in its loading time, counts its rounds down and stops when they are gone', () => {
    const c = new GunControl(TANK_SPECS.type10);
    const q = new Quaternion(), still = { dYaw: 0, dPitch: 0, stabilised: false, recentre: false };
    expect(c.ready).toBe(true);
    expect(c.loaded).toBe(1);
    expect(c.fire()).toBe(1);
    expect(c.ready).toBe(false);
    expect(c.fire()).toBe(0);
    expect(c.gun.ammo).toBe(info.ammo - 1);
    let t = 0;
    for (; !c.ready && t < 20; t += DT) c.step(DT, q, still);
    expect(t).toBeGreaterThan(info.reload - 2 * DT);
    expect(t).toBeLessThan(info.reload + 2 * DT);
    // half way through the loading the bar is half full
    expect(c.fire()).toBe(2);
    for (let k = 0; k < Math.round(info.reload / 2 / DT); k++) c.step(DT, q, still);
    expect(c.loaded).toBeCloseTo(0.5, 2);
    // the racks: every round can be fired, and no more
    for (let n = 3; n <= info.ammo; n++) {
      for (let k = 0; !c.ready && k < 2000; k++) c.step(DT, q, still);
      expect(c.fire()).toBe(n);
    }
    for (let k = 0; k < 2000; k++) c.step(DT, q, still);
    expect(c.gun.ammo).toBe(0);
    expect(c.ready).toBe(false);
    expect(c.loaded).toBe(0);
    expect(c.fire()).toBe(0);
    c.reset();
    expect(c.gun.ammo).toBe(info.ammo);
    expect(c.ready).toBe(true);
  });

  it('carries the sight with the hull in the driving views and holds it in the world through the gunner\'s sight', () => {
    const c = new GunControl(TANK_SPECS.leopard2a5);
    const q = new Quaternion();
    const turned = new Quaternion().setFromAxisAngle(new Vector3(0, 1, 0), 30 * RAD);
    // carried: 20° to the left of the hull, whatever the hull does
    c.step(DT, q, { dYaw: 20 * RAD, dPitch: 0, stabilised: false, recentre: false });
    c.step(DT, turned, { dYaw: 0, dPitch: 0, stabilised: false, recentre: false });
    expect(c.sight.yaw / RAD).toBeCloseTo(20, 6);
    expect(c.world.yaw / RAD).toBeCloseTo(50, 6);
    // held: the hull turns back under it, the line stays where it was in the world
    c.step(DT, turned, { dYaw: 0, dPitch: 0, stabilised: true, recentre: false });
    c.step(DT, q, { dYaw: 0, dPitch: 0, stabilised: true, recentre: false });
    expect(c.world.yaw / RAD).toBeCloseTo(50, 6);
    expect(c.sight.yaw / RAD).toBeCloseTo(50, 6);
    // the hull pitched nose down by more than the gun can rise: the sight is carried along at the limit
    const nose = new Quaternion().setFromAxisAngle(new Vector3(1, 0, 0), 40 * RAD);
    const c2 = new GunControl(TANK_SPECS.leopard2a5);
    c2.step(DT, q, { dYaw: 0, dPitch: 0, stabilised: true, recentre: false });
    c2.step(DT, nose, { dYaw: 0, dPitch: 0, stabilised: true, recentre: false });
    expect(c2.sight.pitch / RAD).toBeCloseTo(c2.info.elevation[1], 6);
    expect(c2.world.pitch / RAD).toBeCloseTo(c2.info.elevation[1] - 40, 4);
    // back to the front, once the gun has come round to the sight
    for (let t = 0; t < 3; t += DT) c.step(DT, q, { dYaw: 0, dPitch: 0, stabilised: true, recentre: false });
    // (the turret on the sight's bearing, turned in by the convergence on the line of sight at the range)
    expect((c.gun.yaw - c.lay.yaw) / RAD).toBeCloseTo(50, 6);
    expect(Math.abs(c.lay.yaw)).toBeLessThan(0.002);
    c.step(DT, q, { dYaw: 0, dPitch: 0, stabilised: true, recentre: true });
    expect(c.sight.yaw).toBe(0);
    // the gun follows at its rate: it is off its line until it has come round
    expect(c.off).toBeGreaterThan(0.3);
    for (let t = 0; t < 3; t += DT) c.step(DT, q, { dYaw: 0, dPitch: 0, stabilised: false, recentre: false });
    expect(c.off).toBeLessThan(1e-6);
    // laid on the point of the line of sight at the range the fire control has (the head is above the bore: the
    // gun is raised by the angle that makes over the range), plus the superelevation for that range
    expect(c.range).toBe(BATTLE_RANGE);
    const head = sightOf(c.spec.tank!), d = c.spec.tank!.dims;
    const converge = (r: number) => Math.atan2(head[1] - d.trunnion, r + head[2] - d.trunnionZ);
    expect(c.gun.pitch).toBeCloseTo(superelevation(c.info, BATTLE_RANGE) + converge(BATTLE_RANGE), 5);
    c.lase(2400);
    for (let t = 0; t < 1; t += DT) c.step(DT, q, { dYaw: 0, dPitch: 0, stabilised: false, recentre: false });
    expect(c.gun.pitch).toBeCloseTo(superelevation(c.info, 2400) + converge(2400), 5);
    expect(hullAngles(turned, dirOf(30 * RAD, 0.1, new Vector3()), { yaw: 0, pitch: 0 }).yaw).toBeCloseTo(0, 9);
  });
});

describe('the fire control converges the gun on the line of sight', () => {
  it('a shot laid through a sight 0.43 m above and 0.6 m beside the bore meets the aim point near and far', () => {
    const base = TANK_SPECS.type10;
    const spec = { ...base, tank: { ...base.tank!, dims: { ...base.tank!.dims, sight: [0.6, 0.849, 0.932] as [number, number, number] } } };
    const g = spec.tank.gun, q = new Quaternion(), origin = new Vector3();
    for (const [range, left, height] of [[90, 1.5, 0.7], [1500, -4, 1.2]]) {
      const c = new GunControl(spec);
      const eye = sightEye(spec, 0, origin, q, 0, new Vector3());
      const aim = new Vector3(left, height, range);
      // the gunner lays the sight on the aim point, the laser gives its range, the gun is laid after it
      const want = hullAngles(q, aim.clone().sub(eye), { yaw: 0, pitch: 0 });
      c.step(DT, q, { dYaw: want.yaw, dPitch: want.pitch, stabilised: false, recentre: false });
      for (let t = 0; t < 3; t += DT) {
        sightEye(spec, 0, origin, q, c.gun.yaw, eye);
        c.lase(aim.distanceTo(eye));
        c.step(DT, q, { dYaw: 0, dPitch: 0, stabilised: false, recentre: false });
      }
      expect(c.off, `${range}`).toBeLessThan(1e-6);
      const pose = { trunnion: new Vector3(), muzzle: new Vector3(), dir: new Vector3() };
      gunPose(spec, 0, origin, q, c.gun.yaw, c.gun.pitch, pose);
      const s = newShell(0, 1, pose.muzzle.clone(), pose.dir.clone().multiplyScalar(g.muzzleVelocity), dragOf(g));
      const out = blank();
      let last = s.p.clone();
      while (s.p.z < range) {
        last = s.p.clone();
        stepShell(s, DT, empty, out);
      }
      // where it crosses the aim point's distance
      const at = last.lerp(s.p, (range - last.z) / (s.p.z - last.z));
      expect(Math.abs(at.y - height), `${range} m: high by ${(at.y - height).toFixed(3)}`).toBeLessThan(0.1);
      expect(Math.abs(at.x - left), `${range} m: left by ${(at.x - left).toFixed(3)}`).toBeLessThan(0.1);
    }
  });
});

describe('a shell in flight', () => {
  const info = TANK_SPECS.m1a2.tank!.gun;

  it('falls as gravity has it and loses the same share of its speed every metre', () => {
    // without drag: a parabola
    const s = newShell(0, 1, new Vector3(0, 100, 0), new Vector3(0, 0, 1500), 0);
    const out = blank();
    for (let k = 0; k < 120; k++) stepShell(s, DT, empty, out);
    expect(s.age).toBeCloseTo(1, 9);
    expect(s.p.z).toBeCloseTo(1500, 6);
    expect(100 - s.p.y).toBeCloseTo(0.5 * GRAVITY, 3);
    // with the gun's drag: the speed left after a kilometre, the time it took, the fall
    const d = newShell(0, 1, new Vector3(0, 1000, 0), new Vector3(0, 0, info.muzzleVelocity), dragOf(info));
    let t = 0;
    while (d.p.z < 1000) {
      stepShell(d, DT, empty, out);
      t += DT;
    }
    expect(d.v.length()).toBeGreaterThan(info.muzzleVelocity - info.dropPerKm * 1.05);
    expect(d.v.length()).toBeLessThan(info.muzzleVelocity - info.dropPerKm * 0.9);
    expect(Math.abs(t - flightTime(info, 1000))).toBeLessThan(DT * 1.5);
    expect(Math.abs(1000 - d.p.y - dropAt(info, 1000))).toBeLessThan(0.08);
    // spent after its life, whatever it met
    while (!spent(d)) stepShell(d, DT, empty, out);
    expect(d.age >= SHELL_LIFE || d.flown >= SHELL_REACH).toBe(true);
  });

  it('laid by the superelevation, it comes down on the line of sight at the range', () => {
    for (const id of TANK_ORDER) {
      const g = TANK_SPECS[id].tank!.gun;
      for (const range of [500, 1000, 2000, 3000]) {
        const s = newShell(0, 1, new Vector3(), dirOf(0, superelevation(g, range), new Vector3()).multiplyScalar(g.muzzleVelocity), dragOf(g));
        const out = blank();
        while (s.p.z < range) stepShell(s, DT, empty, out);
        // within a third of a vehicle's height at three kilometres
        expect(Math.abs(s.p.y), `${id} ${range}`).toBeLessThan(0.15 + range * 0.00025);
      }
    }
  });

  it('meets what lies between two steps, however thin', () => {
    // a wall 2 cm thick 500.3 m away: a step is 13 m long
    const wall: ShellWorld = {
      cast(from, dir, len) {
        const t = (500.3 - from.z) / dir.z;
        return t >= 0 && t <= len ? { t, target: 7 } : null;
      },
    };
    const shells = new Shells();
    shells.add(newShell(3, 1, new Vector3(0, 2, 0), new Vector3(0, 0, info.muzzleVelocity), dragOf(info)));
    const met: { z: number; target: number | null; owner: number }[] = [];
    for (let k = 0; k < 240; k++) shells.step(DT, wall, (i) => met.push({ z: i.point.z, target: i.target, owner: i.shell.owner }));
    expect(met).toHaveLength(1);
    expect(met[0].z).toBeCloseTo(500.3, 6);
    expect(met[0]).toMatchObject({ target: 7, owner: 3 });
    expect(shells.live).toHaveLength(0);
  });
});

/** a level pad, a tank on it and, if asked, another vehicle ahead of its gun */
function range(opts: { rival?: number; peer?: number; at?: [number, number] } = {}) {
  const world = new RAPIER.World({ x: 0, y: -9.81, z: 0 });
  world.timestep = DT;
  world.createCollider(RAPIER.ColliderDesc.cuboid(5000, 1, 5000).setTranslation(0, -1, 0).setCollisionGroups(groups(GROUP_GROUND, GROUP_CAR)));
  const physics = { world } as unknown as PhysicsWorld;
  const tank = new VehicleSim(physics, CAR_SPECS.type10, new Vector3(opts.at?.[0] ?? 0, 0, opts.at?.[1] ?? 0), 0);
  const rival = opts.rival ? new VehicleSim(physics, CAR_SPECS.hayate, new Vector3(0, 0, opts.rival), 0) : null;
  // another member's stand-in: a body the size of a tank in the stand-ins' group
  let proxy: { body: RAPIER.RigidBody; collider: RAPIER.Collider } | null = null;
  if (opts.peer) {
    const body = world.createRigidBody(RAPIER.RigidBodyDesc.kinematicPositionBased().setTranslation(0, 1.3, opts.peer));
    proxy = { body, collider: world.createCollider(RAPIER.ColliderDesc.cuboid(1.7, 1.2, 4.5).setCollisionGroups(groups(GROUP_PROXY, GROUP_CAR)), body) };
  }
  const log = { fired: 0, struck: [] as (number | null)[], rival: 0, self: 0, sent: [] as number[][] };
  const host: GunneryHost = {
    fired: () => void log.fired++,
    struck: (_p, target) => void log.struck.push(target),
    respawnRival: () => void log.rival++,
    respawnSelf: () => void log.self++,
    send: (d) => void log.sent.push(d),
  };
  const g = new Gunnery(physics, () => 0, host);
  const input = emptyInput(), hands = { dYaw: 0, dPitch: 0, stabilised: false, recentre: false };
  let t = 0;
  /** `seconds` of the world; `fire`: the trigger is held; `turn` / `tilt`: the sight thrown round / up by this much at once */
  const run = (seconds: number, fire = false, turn = 0, tilt = 0) => {
    hands.dYaw = turn;
    hands.dPitch = tilt;
    for (let k = 0; k < Math.round(seconds / DT); k++) {
      for (const v of [tank, rival]) {
        if (!v) continue;
        v.input = input;
        v.preStep(DT);
      }
      world.step();
      tank.postStep(DT);
      rival?.postStep(DT);
      g.step(DT, tank, hands, fire, (t += DT) * 1000);
      hands.dYaw = hands.dPitch = 0;
      g.fly(DT);
    }
  };
  /** the sight laid on a point `z` m ahead and `y` m above the ground (the gunner's eye is on the turret's roof) */
  const layOn = (z: number, y: number) => {
    run(0.5);
    run(1.5, false, 0, -Math.atan2(g.eye.y - y, z - g.eye.z));
  };
  return { world, tank, rival, proxy, g, log, run, layOn, host };
}

describe('the guns of a race', () => {
  it('a hit puts the rival back on the road, and nothing else does', () => {
    const r = range({ rival: 140 });
    r.g.player(r.tank);
    r.g.rival(r.rival!.collider);
    r.layOn(140, 0.7);
    // the laser has the rival's range, the gun is laid for it
    expect(r.g.control!.lased).toBe(true);
    expect(r.g.control!.range).toBeGreaterThan(125);
    expect(r.g.control!.range).toBeLessThan(140);
    r.run(DT, true);
    expect(r.log.fired).toBe(1);
    expect(r.g.shells.live).toHaveLength(1);
    r.run(0.5);
    expect(r.log.struck).toEqual([RIVAL]);
    expect(r.log.rival).toBe(1);
    expect(r.log.self).toBe(0);
    expect(r.g.shells.live).toHaveLength(0);
    // the trigger held: nothing until the next round is in
    r.run(1, true);
    expect(r.log.fired).toBe(1);
    // a round fired past it (the sight thrown a quarter round) ends in the ground or flies on: nobody is put back
    r.run(r.g.control!.info.reload, false, Math.PI / 2);
    r.run(DT, true);
    expect(r.log.fired).toBe(2);
    r.run(SHELL_LIFE + 0.5);
    expect(r.log.rival).toBe(1);
    expect(r.log.struck.slice(1).every((t) => t === null)).toBe(true);
    r.world.free();
  });

  it('the shot pushes the hull back by its momentum, and never meets its own tank', () => {
    const r = range();
    r.g.player(r.tank);
    r.run(1);
    const before = r.tank.velocity.z;
    r.run(DT, true);
    r.run(2 * DT);
    const gun = r.g.control!.info;
    expect(before - r.tank.velocity.z).toBeGreaterThan((recoilOf(gun) / r.tank.spec.mass) * 0.6);
    expect(before - r.tank.velocity.z).toBeLessThan((recoilOf(gun) / r.tank.spec.mass) * 1.2);
    r.run(SHELL_LIFE + 0.5);
    // (it flew its life out over the pad or came down on it: never on the tank that fired it)
    expect(r.log.struck.every((t) => t === null)).toBe(true);
    expect(r.log.rival + r.log.self).toBe(0);
    r.world.free();
  });

  it('online the firer tells the others, and the member hit puts itself back after checking the claim', () => {
    // A (member 4) fires at B's stand-in (member 9), 300 m ahead
    const a = range({ peer: 300 });
    a.g.player(a.tank, 4);
    a.g.peer(9, CAR_SPECS.leopard2a5, a.proxy);
    a.layOn(300, 1.3);
    a.run(DT, true);
    a.run(1);
    expect(a.log.struck).toEqual([9]);
    // nothing is done to the other's vehicle here: it is told
    expect(a.log.rival + a.log.self).toBe(0);
    expect(a.log.sent).toHaveLength(2);
    const [shot, hit] = a.log.sent.map((d) => decodeGunEvent(JSON.parse(JSON.stringify(d)))!);
    expect(shot.kind).toBe('shot');
    expect(hit).toMatchObject({ kind: 'hit', n: 1, target: 9 });
    expect((hit as HitEvent).p[2]).toBeGreaterThan(294);

    // B's game: its own vehicle stands where A has its stand-in. The events arrive a little after they were sent.
    const tell = (b: ReturnType<typeof range>, me: { id: number; racing: boolean }, from = 4, at: Vector3 | null = new Vector3(0, 1.3, 0)) => {
      const mine = { id: me.id, position: b.tank.position, speed: 0, racing: me.racing };
      const sent = (decodeGunEvent(a.log.sent[0]) as ShotEvent).t;
      b.g.receive(from, a.log.sent[0], sent + 60, 0, at, mine);
      b.run(0.3);
      b.g.receive(from, a.log.sent[1], sent + 250, 0, at, mine);
    };
    const b = range({ at: [0, 300] });
    b.g.player(b.tank, 9);
    b.g.peer(4, CAR_SPECS.type10, null);
    tell(b, { id: 9, racing: true });
    expect(b.log.fired).toBe(1);
    expect(b.log.self).toBe(1);
    // (A's shell met B's vehicle on B's screen too: that alone does nothing; the burst comes with A's word)
    expect(b.log.struck).toEqual([9]);
    expect(b.g.shells.live).toHaveLength(0);
    // the same hit told twice counts once
    b.g.receive(4, a.log.sent[1], 9000, 0, new Vector3(0, 1.3, 0), { id: 9, position: b.tank.position, speed: 0, racing: true });
    expect(b.log.self).toBe(1);
    expect(b.g.referee.refused).toBe(1);

    // a third member, beside the two, sees the shot and the hit, and stays where it is
    const c = range({ at: [60, 100], peer: 300 });
    c.g.player(c.tank, 2);
    c.g.peer(4, CAR_SPECS.type10, null);
    c.g.peer(9, CAR_SPECS.leopard2a5, c.proxy);
    tell(c, { id: 2, racing: true });
    expect(c.log.fired).toBe(1);
    expect(c.log.struck).toEqual([9]);
    expect(c.log.self).toBe(0);

    // not in the race (before the green light, past the line): seen, not suffered
    const d = range({ at: [0, 300] });
    d.g.player(d.tank, 9);
    d.g.peer(4, CAR_SPECS.type10, null);
    tell(d, { id: 9, racing: false });
    expect(d.log.struck).toEqual([9]);
    expect(d.log.self).toBe(0);

    // far from where the hit is said to be: not ours
    const e = range({ at: [40, 300] });
    e.g.player(e.tank, 9);
    e.g.peer(4, CAR_SPECS.type10, null);
    tell(e, { id: 9, racing: true });
    expect(e.log.self).toBe(0);
    expect(e.g.referee.refused).toBe(1);

    // from a member who is not in a tank, from somebody who is not in the race at all, from a muzzle far from
    // where that member's vehicle is: nothing happens
    const f = range({ at: [0, 300] });
    f.g.player(f.tank, 9);
    f.g.peer(4, CAR_SPECS.hayate, null);
    tell(f, { id: 9, racing: true });
    tell(f, { id: 9, racing: true }, 77);
    const h = range({ at: [0, 300] });
    h.g.player(h.tank, 9);
    h.g.peer(4, CAR_SPECS.type10, null);
    tell(h, { id: 9, racing: true }, 4, new Vector3(0, 0, -200));
    for (const x of [f, h]) {
      expect(x.log.fired).toBe(0);
      expect(x.log.self).toBe(0);
      expect(x.g.shells.live).toHaveLength(0);
    }
    for (const x of [a, b, c, d, e, f, h]) x.world.free();
  });
});

describe('gun events on the wire', () => {
  const shot: ShotEvent = { kind: 'shot', n: 3, t: 8123456.78, p: [812.3456, -41.2071, -1930.0114], v: [-1031.273, 12.42, 1244.9] };
  const hit: HitEvent = { kind: 'hit', n: 3, target: 42, p: [512.3456, -44.2, -1630.5] };

  it('are whole numbers, small, and come back as they went', () => {
    for (const e of [shot, hit]) {
      const wire = encodeGunEvent(e);
      expect(wire[0]).toBe(GUN_EVENT);
      expect(wire.every(Number.isInteger)).toBe(true);
      expect(isGunEvent(wire)).toBe(true);
      expect(JSON.stringify(wire).length).toBeLessThan(110);
      const back = decodeGunEvent(JSON.parse(JSON.stringify(wire)))!;
      expect(back.kind).toBe(e.kind);
      expect(back.n).toBe(3);
      for (let i = 0; i < 3; i++) expect(back.p[i]).toBeCloseTo(e.p[i], 3);
      if (back.kind === 'shot') {
        expect(back.t).toBeCloseTo(shot.t, 1);
        for (let i = 0; i < 3; i++) expect(back.v[i]).toBeCloseTo(shot.v[i], 2);
      } else expect(back.target).toBe(42);
    }
  });

  it('are not car states, and car states are not gun events', () => {
    const state: NetState = { seq: 7, t: 1, age: 0, p: [0, 0, 0], q: [0, 0, 0, 1], vel: [0, 0, 0], w: [0, 0, 0], acc: [0, 0, 0], st: 0, s: 0, br: 0, ep: 0, th: 0, rp: 0 };
    expect(isGunEvent(encodeState(state))).toBe(false);
    expect(decodeState(encodeGunEvent(shot))).toBeNull();
    expect(decodeState(encodeGunEvent(hit))).toBeNull();
  });

  it('drop whatever is not one', () => {
    const wire = encodeGunEvent(shot);
    expect(decodeGunEvent(null)).toBeNull();
    expect(decodeGunEvent('71')).toBeNull();
    expect(decodeGunEvent(wire.slice(0, -1))).toBeNull();
    expect(decodeGunEvent([...wire, 0])).toBeNull();
    expect(decodeGunEvent(wire.map((x, k) => (k === 4 ? 0.5 : x)))).toBeNull();
    expect(decodeGunEvent(wire.map((x, k) => (k === 5 ? NaN : x)))).toBeNull();
    expect(decodeGunEvent(wire.map((x, k) => (k === 6 ? '1' : x)))).toBeNull();
    expect(decodeGunEvent(wire.map((x, k) => (k === 1 ? 3 : x)))).toBeNull();
    expect(decodeGunEvent(wire.map((x, k) => (k === 2 ? 0 : x)))).toBeNull();
    expect(decodeGunEvent(wire.map((x, k) => (k === 2 ? 10000 : x)))).toBeNull();
    expect(decodeGunEvent(encodeGunEvent({ ...hit, target: 0 }))).toBeNull();
  });

  it('reach the game through the link from members only, and never as a state', () => {
    const ends: NetTransport[] = [];
    const end = (k: number): NetTransport => ({ ready: true, onReceive: null, send: (d) => ends[1 - k].onReceive?.(k + 1, d) });
    ends.push(end(0), end(1));
    const a = new NetLink(), b = new NetLink();
    a.selfId = 1;
    b.selfId = 2;
    b.peer(1);
    a.attach(ends[0]);
    b.attach(ends[1]);
    const heard: [number, number[]][] = [];
    b.onEvent = (from, data) => void heard.push([from, data]);
    expect(a.sendEvent(encodeGunEvent(shot))).toBe(true);
    expect(heard).toHaveLength(1);
    expect(heard[0][0]).toBe(1);
    expect(decodeGunEvent(heard[0][1])).toMatchObject({ kind: 'shot', n: 3 });
    // a stranger's (no such peer in the race) is not heard
    ends[1].onReceive?.(55, encodeGunEvent(shot));
    expect(heard).toHaveLength(1);
    a.attach(null);
    expect(a.sendEvent(encodeGunEvent(shot))).toBe(false);
  });
});

describe('the referee of what the others say', () => {
  const gun = TANK_SPECS.type10.tank!.gun;
  const at = new Vector3(0, 1, 0);
  const fired = (n: number, speed = gun.muzzleVelocity, p: [number, number, number] = [0, 2.3, 6]): ShotEvent => ({ kind: 'shot', n, t: 0, p, v: [0, 0, speed] });

  it('believes a shot only from a tank, at its muzzle velocity, near its vehicle, no faster than it loads', () => {
    const r = new GunReferee((id) => (id === 4 ? gun : null));
    expect(r.shot(5, fired(1), 1000, at)).toBe(false);
    expect(r.shot(4, fired(1, gun.muzzleVelocity + 80), 1000, at)).toBe(false);
    expect(r.shot(4, fired(1, 300), 1000, at)).toBe(false);
    expect(r.shot(4, fired(1, gun.muzzleVelocity, [0, 2, 90]), 1000, at)).toBe(false);
    expect(r.shot(4, fired(gun.ammo + 1), 1000, at)).toBe(false);
    // (a hull at 20 m/s adds to the shell's speed)
    expect(r.shot(4, fired(1, gun.muzzleVelocity + 20), 1000, at)).toBe(true);
    // the next one a second later: no gun loads that fast; the same number again: no
    expect(r.shot(4, fired(2), 2000, at)).toBe(false);
    expect(r.shot(4, fired(1), 1000 + gun.reload * 1000, at)).toBe(false);
    expect(r.shot(4, fired(2), 1000 + gun.reload * 1000 - 300, at)).toBe(true);
    expect(r.refused).toBe(7);
    // where the vehicle is not known yet the muzzle cannot be checked: believed
    const fresh = new GunReferee(() => gun);
    expect(fresh.shot(4, fired(1, gun.muzzleVelocity, [0, 2, 900]), 0, null)).toBe(true);
  });

  it('believes a hit only on the path of a shot it heard, once, and not before the shell could be there', () => {
    const r = new GunReferee(() => gun);
    const claim = (n: number, z: number, x = 0, y = 2.3): HitEvent => ({ kind: 'hit', n, target: 9, p: [x, y - dropAt(gun, z), z] });
    expect(r.hit(4, claim(1, 600), 1000)).toBe(false);
    expect(r.shot(4, fired(1), 1000, at)).toBe(true);
    // 30 m beside the path; a shot never fired; 3 km away a tenth of a second after the shot
    expect(r.hit(4, claim(1, 600, 30), 1400)).toBe(false);
    expect(r.hit(4, claim(2, 600), 1400)).toBe(false);
    expect(r.hit(4, claim(1, 3000), 1100)).toBe(false);
    expect(r.hit(4, claim(1, 600), 1000 + flightTime(gun, 594) * 1000)).toBe(true);
    expect(r.hit(4, claim(1, 600), 1500)).toBe(false);
    // whose it is: named for us, and where we are (a vehicle at 30 m/s is given what it covers meanwhile)
    const e = claim(1, 600);
    expect(r.mine(e, 8, new Vector3(0, 1, 600), 0)).toBe(false);
    expect(r.mine(e, 9, new Vector3(0, 1, 600), 0)).toBe(true);
    expect(r.mine(e, 9, new Vector3(0, 1, 625), 0)).toBe(false);
    expect(r.mine(e, 9, new Vector3(0, 1, 625), 30)).toBe(true);
  });
});

describe('turret and gun in a car state', () => {
  const base: NetState = { seq: 7, t: 123456.7, age: 4.2, p: [812.345, -41.207, -1930.011], q: [0.0123, 0.7071, -0.0045, 0.707], vel: [-31.27, 0.42, 44.9], w: [0.01, -0.83, 0.02], acc: [3.1, -0.2, -7.75], st: -0.213, s: 1873.4, br: 1, ep: 2, th: 0.37, rp: 0.81 };

  it('ride in the packet as it was: no longer, the old fields where they were', () => {
    const plain = encodeState(base);
    const aimed = encodeState({ ...base, tu: 1.234, gp: -0.11 });
    expect(aimed).toHaveLength(plain.length);
    expect(aimed.every(Number.isInteger)).toBe(true);
    // one number differs: the flags' word, and its low bits (brake, respawn count, departure) are as before
    const differ = aimed.map((x, k) => (x === plain[k] ? -1 : k)).filter((k) => k >= 0);
    expect(differ).toHaveLength(1);
    expect(aimed[differ[0]] & 31).toBe(plain[differ[0]] & 31);
    expect(aimed[differ[0]]).toBeLessThan(2 ** 25);
    const back = decodeState(JSON.parse(JSON.stringify(aimed)))!;
    expect(back).toMatchObject({ br: 1, ep: 2, st: -0.213, s: 1873.4, th: 0.37, rp: 0.81 });
    expect(Math.abs(back.tu! - 1.234)).toBeLessThanOrEqual(TURRET_STEP / 2 + 1e-9);
    expect(Math.abs(back.gp! - -0.11)).toBeLessThanOrEqual(GUN_STEP / 2 + 1e-9);
    // a vehicle without a turret sends what it always sent, and reads back without one
    const old = decodeState(plain)!;
    expect(old.tu).toBeUndefined();
    expect(old.gp).toBeUndefined();
    expect(old).toMatchObject({ br: 1, ep: 2 });
    expect(decodeState(encodeState({ ...base, dep: 2, tu: -3, gp: 0.3 }))).toMatchObject({ dep: 2, br: 1, ep: 2 });
  });

  it('carry every bearing and every elevation a gun can have', () => {
    for (let deg = -180; deg < 180; deg += 7.3)
      for (const el of [-10, -6.2, 0, 3.1, 20]) {
        const back = decodeState(encodeState({ ...base, br: 0, ep: 0, tu: deg * RAD, gp: el * RAD }))!;
        const off = Math.atan2(Math.sin((back.tu ?? 0) - deg * RAD), Math.cos((back.tu ?? 0) - deg * RAD));
        expect(Math.abs(off), `${deg}`).toBeLessThanOrEqual(TURRET_STEP / 2 + 1e-9);
        expect(Math.abs((back.gp ?? 0) - el * RAD), `${el}`).toBeLessThanOrEqual(GUN_STEP / 2 + 1e-9);
      }
  });

  it('are drawn between the packets, the turret the short way round', () => {
    const track = new PeerTrack(), pose = newPose();
    track.push({ ...base, seq: 1, t: 0, age: 0, vel: [0, 0, 0], acc: [0, 0, 0], w: [0, 0, 0], tu: 170 * RAD, gp: 0 });
    track.push({ ...base, seq: 2, t: 100, age: 0, vel: [0, 0, 0], acc: [0, 0, 0], w: [0, 0, 0], tu: -170 * RAD, gp: 10 * RAD });
    track.sample(50, pose);
    expect(Math.abs(Math.abs(pose.turret) - Math.PI)).toBeLessThan(1e-6);
    expect(pose.gunPitch / RAD).toBeCloseTo(5, 6);
    track.sample(100, pose);
    expect(pose.turret / RAD).toBeCloseTo(-170, 6);
  });
});

describe('the trigger', () => {
  it('a pull shorter than a frame is still a shot; a held trigger stays pulled', () => {
    const none = () => undefined;
    const input = new InputManager({ addEventListener: none, removeEventListener: none } as unknown as Window);
    const hands = emptyHands();
    expect(input.pollGun(1 / 60, hands).fire).toBe(false);
    // a finger's tap: down and up between two frames (ui/hud/TouchControls.tsx)
    input.touchGun.fire = input.touchGun.shot = true;
    input.touchGun.fire = false;
    expect(input.pollGun(1 / 60, hands).fire).toBe(true);
    expect(input.pollGun(1 / 60, hands).fire).toBe(false);
    // held
    input.touchGun.fire = input.touchGun.shot = true;
    expect(input.pollGun(1 / 60, hands).fire).toBe(true);
    expect(input.pollGun(1 / 60, hands).fire).toBe(true);
    input.touchGun.fire = false;
    expect(input.pollGun(1 / 60, hands).fire).toBe(false);
    // a drag is taken once
    input.touchGun.dx = 40;
    expect(input.pollGun(1 / 60, hands).dx).toBeGreaterThan(0);
    expect(input.pollGun(1 / 60, hands).dx).toBe(0);
  });
});
