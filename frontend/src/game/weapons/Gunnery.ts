import { Vector3 } from 'three';
import type { CarSpec } from '../vehicle/carSpecs';
import type { PhysicsWorld, RAPIER } from '../vehicle/PhysicsWorld';
import type { GunInfo } from '../vehicle/tanks';
import type { VehicleSim } from '../vehicle/VehicleSim';
import { GunReferee, decodeGunEvent, encodeGunEvent } from '../net/gunEvents';
import { RIVAL, Shells, newShell, stepShell, type Impact, type Shell, type ShellTarget } from './ballistics';
import { GunControl, LASE_RANGE, dirOf, dragOf, gunPose, recoilOf, sightEye, superelevation, type GunInput } from './gun';
import { GameShellWorld } from './world';

/** What the gunnery asks of the game around it (effects, sound, the respawns, the link to the other players). */
export interface GunneryHost {
  /** a gun went off: its muzzle, the bore's direction, the firer's velocity; whose (`own`: the local player's) */
  fired(muzzle: Vector3, dir: Vector3, velocity: Vector3, gun: GunInfo, firer: number, own: boolean): void;
  /** a shell met the ground (target null) or a vehicle */
  struck(point: Vector3, target: ShellTarget, own: boolean): void;
  /** the rival's vehicle was hit: it is put back on the road, as the R key does for the player's */
  respawnRival(): void;
  /** our own vehicle was hit by another member's shell: the same */
  respawnSelf(): void;
  /** to the other members of an online race (nothing to send to otherwise) */
  send(data: number[]): void;
}

/** the laser ranges this often (s) */
const LASE_EVERY = 0.1;
/** a shot heard from another member is flown on by at most this long (s) to where it is now */
const CATCH_UP = 0.5;

const _v = new Vector3(), _at = new Vector3(), _zero = new Vector3();

/**
 * The guns of a race, DOM-free and stepped with the physics: the local player's gun (if it drives a tank), every
 * shell in the air (its own and, online, the other members'), and what a hit does.
 *
 * **A hit forces the vehicle hit to respawn, exactly as its R key would** (owner 11-10). Who can be hit: the rival
 * of a single-player battle and, online, the other members' vehicles; never a ghost, the replay or the autobahn's
 * traffic (they have no body), never the firer. Online the firer's game decides (`net/gunEvents.ts`): it tells the
 * others of each shot (they fly it for the picture) and of a hit; the member hit respawns itself after checking
 * the claim. Nothing is scored.
 */
export class Gunnery {
  readonly shells = new Shells();
  readonly world: GameShellWorld;
  readonly referee: GunReferee;
  /** the local player's gun (null: not in a tank) */
  control: GunControl | null = null;
  /** the local gun where the last step left it: trunnions, muzzle, the bore's direction */
  readonly pose = { trunnion: new Vector3(), muzzle: new Vector3(), dir: new Vector3() };
  /** the gunner's eye and the line the sight shows: the bore's less the superelevation */
  readonly eye = new Vector3();
  readonly line = new Vector3();
  /** the local player's key as a firer: its member id online, 0 alone */
  private self = 0;
  private guns = new Map<number, GunInfo | null>();
  private laseT = 0;
  private caught: Impact = { shell: null as unknown as Shell, point: new Vector3(), target: null };

  constructor(physics: PhysicsWorld, heightAt: ((x: number, z: number) => number) | null, private host: GunneryHost) {
    this.world = new GameShellWorld(physics, heightAt);
    this.referee = new GunReferee((id) => this.guns.get(id) ?? null);
  }

  /** The local player's vehicle (`id`: its member id online). */
  player(sim: VehicleSim, id = 0) {
    this.self = id;
    this.world.bodies.set(id, sim.body);
    // (to another member's shell our own vehicle is a vehicle: see `onImpact`)
    this.world.targets.set(sim.collider.handle, id);
    this.control = sim.spec.tank ? new GunControl(sim.spec) : null;
    if (this.control) this.aim(sim);
  }

  /** The rival's vehicle: it can be hit. */
  rival(collider: RAPIER.Collider) {
    this.world.targets.set(collider.handle, RIVAL);
  }

  /** Another member's vehicle: its gun (if it is a tank) may be heard, its stand-in (if it has one) can be hit. */
  peer(id: number, spec: CarSpec, proxy: { body: RAPIER.RigidBody; collider: RAPIER.Collider } | null) {
    this.guns.set(id, spec.tank?.gun ?? null);
    if (proxy) {
      this.world.targets.set(proxy.collider.handle, id);
      this.world.bodies.set(id, proxy.body);
    }
  }

  private aim(sim: VehicleSim) {
    const c = this.control!;
    gunPose(sim.spec, sim.rideHeight, sim.position, sim.quaternion, c.gun.yaw, c.gun.pitch, this.pose);
    sightEye(sim.spec, sim.rideHeight, sim.position, sim.quaternion, c.gun.yaw, this.eye);
    dirOf(c.gun.yaw, c.gun.pitch - superelevation(c.info, c.range), this.line).applyQuaternion(sim.quaternion);
  }

  /**
   * One physics step of the local gun, after the world's step: the sight and the gun moved, the laser, and the
   * shot if `fire` is asked and a round is in. `now`: our clock (ms). Returns the shot's number, or 0.
   */
  step(dt: number, sim: VehicleSim, input: GunInput, fire: boolean, now: number) {
    const c = this.control;
    if (!c) return 0;
    c.step(dt, sim.quaternion, input);
    this.aim(sim);
    this.laseT -= dt;
    if (this.laseT <= 0) {
      this.laseT = LASE_EVERY;
      const hit = this.world.cast(this.eye, dirOf(c.world.yaw, c.world.pitch, _v), LASE_RANGE, this.self);
      // (nearer than the gun's own length there is nothing to range)
      c.lase(hit && hit.t > 8 ? hit.t : hit ? 8 : null);
    }
    const n = fire ? c.fire() : 0;
    if (!n) return 0;
    const { muzzle, dir, trunnion } = this.pose;
    _v.copy(dir).multiplyScalar(c.info.muzzleVelocity).add(sim.velocity);
    this.shells.add(newShell(this.self, n, muzzle, _v, dragOf(c.info)));
    this.host.send(encodeGunEvent({ kind: 'shot', n, t: now, p: [muzzle.x, muzzle.y, muzzle.z], v: [_v.x, _v.y, _v.z] }));
    // the recoil: the shot's momentum back along the bore, through the trunnions
    const j = recoilOf(c.info);
    sim.body.applyImpulseAtPoint({ x: -dir.x * j, y: -dir.y * j, z: -dir.z * j }, trunnion, true);
    this.host.fired(muzzle, dir, sim.velocity, c.info, this.self, true);
    return n;
  }

  /** One physics step of every shell in the air. */
  fly(dt: number) {
    if (this.shells.live.length) this.shells.step(dt, this.world, this.onImpact);
  }

  private onImpact = (i: Impact) => {
    const own = i.shell.owner === this.self;
    // another member's shell that meets a vehicle on OUR screen ends there without a word: whether it was a hit
    // is its firer's screen's to say, and if it was, the burst comes with that word (`receive`)
    if (!own && i.target !== null) return;
    if (own && i.target !== null) {
      if (i.target === RIVAL) this.host.respawnRival();
      else this.host.send(encodeGunEvent({ kind: 'hit', n: i.shell.shot, target: i.target, p: [i.point.x, i.point.y, i.point.z] }));
    }
    this.host.struck(i.point, i.target, own);
  };

  /**
   * What another member says about its gun, heard at `now` (ms, our clock). `offset`: their clock − ours (ms);
   * `at`: where we have their vehicle (null: nowhere yet); `me`: our own vehicle, and whether it is in the race
   * (after the green light, before the line). Whatever cannot be true is dropped (`GunReferee`).
   */
  receive(from: number, data: unknown, now: number, offset: number, at: Vector3 | null, me: { id: number; position: Vector3; speed: number; racing: boolean }) {
    const e = decodeGunEvent(data);
    if (!e) return;
    if (e.kind === 'shot') {
      if (!this.referee.shot(from, e, now, at)) return;
      const gun = this.guns.get(from)!;
      _at.set(e.p[0], e.p[1], e.p[2]);
      _v.set(e.v[0], e.v[1], e.v[2]);
      const shell = this.shells.add(newShell(from, e.n, _at, _v, dragOf(gun)));
      this.host.fired(_at, _v.clone().normalize(), _zero, gun, from, false);
      // flown on to where it is by now (the time the event took), through the world as any step
      for (let late = Math.min(CATCH_UP, Math.max(0, (now - (e.t - offset)) / 1000)); late > 1e-4; late -= 1 / 120) {
        const hit = stepShell(shell, Math.min(late, 1 / 120), this.world, this.caught);
        if (!hit) continue;
        this.shells.live.splice(this.shells.live.indexOf(shell), 1);
        this.onImpact(hit);
        break;
      }
      return;
    }
    if (!this.referee.hit(from, e, now)) return;
    // the shell ends there on every screen
    const k = this.shells.live.findIndex((s) => s.owner === from && s.shot === e.n);
    if (k >= 0) this.shells.live.splice(k, 1);
    _at.set(e.p[0], e.p[1], e.p[2]);
    this.host.struck(_at, e.target, false);
    if (me.racing && this.referee.mine(e, me.id, me.position, me.speed)) this.host.respawnSelf();
  }

  clear() {
    this.shells.clear();
    this.referee.clear();
  }
}
