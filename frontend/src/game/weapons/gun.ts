import { Quaternion, Vector3 } from 'three';
import { clamp, wrapAngle } from '../util/math';
import type { CarSpec } from '../vehicle/carSpecs';
import type { GunInfo, TankInfo } from '../vehicle/tanks';

/**
 * A tank's gun (vehicle/tanks.ts `GunInfo`), DOM-free and stepped with the physics (120 Hz), so that what it does
 * does not depend on the frame rate: the line of sight the player moves, the turret and the gun laid after it at
 * their real rates and within their real limits, the loading time, the rounds left, the recoil.
 *
 * Angles: a bearing is a heading (0 = +Z, + towards +X, the vehicle's left: `atan2(x, z)`), an elevation is above
 * the horizon (world) or above the turret ring's plane (hull frame). The hull frame is the body's: +Z forward,
 * +X left, +Y up, origin at the body's origin (`rideHeight` above the ground at rest).
 *
 * The sight and the gun. The player moves the LINE OF SIGHT; the fire control lays the gun on it: the turret to
 * its bearing, the gun to its elevation plus the superelevation for the lased range (all five have a laser
 * rangefinder and a ballistic computer). Two ways of holding the sight:
 *   - carried (the driving views): the sight keeps its bearing and elevation relative to the hull, so the picture
 *     turns with the road as a chase camera's does;
 *   - stabilised (the gunner's sight): it keeps its direction in the world while the hull turns and pitches under
 *     it, as the real guns' stabilisers do; the turret's and the gun's drives then work against the hull's motion,
 *     at most at their rates.
 */

/** speed of the propellant gas leaving the muzzle (m/s): the usual figure for the gas's share of a recoil */
export const GAS_SPEED = 1400;
export const GRAVITY = 9.81;
/** range the fire control assumes when the laser finds nothing (sky): the battle-sight range (m) */
export const BATTLE_RANGE = 1000;
/** how far the laser ranges (m) */
export const LASE_RANGE = 4000;

export interface Angles {
  yaw: number;
  pitch: number;
}

export interface GunState {
  /** turret bearing relative to the hull (rad, + = left) and gun elevation above the ring's plane (rad) */
  yaw: number;
  pitch: number;
  /** seconds until the next round is loaded (0: ready) */
  reload: number;
  /** rounds left */
  ammo: number;
  /** rounds fired so far */
  shots: number;
}

export const newGun = (info: GunInfo): GunState => ({ yaw: 0, pitch: 0, reload: 0, ammo: info.ammo, shots: 0 });

const RAD = Math.PI / 180;
const _d = new Vector3(), _qi = new Quaternion();

/** The unit vector of a bearing and an elevation (in whatever frame they are of). */
export function dirOf(yaw: number, pitch: number, out: Vector3) {
  const c = Math.cos(pitch);
  return out.set(Math.sin(yaw) * c, Math.sin(pitch), Math.cos(yaw) * c);
}

/** The bearing and elevation of a direction (in the frame the direction is in). */
export function anglesOf(dir: Vector3, out: Angles) {
  out.yaw = Math.atan2(dir.x, dir.z);
  out.pitch = Math.asin(clamp(dir.y / (dir.length() || 1), -1, 1));
  return out;
}

/** A world direction as the turret bearing and gun elevation that point along it, for a hull at `q`. */
export function hullAngles(q: Quaternion, worldDir: Vector3, out: Angles) {
  return anglesOf(_d.copy(worldDir).applyQuaternion(_qi.copy(q).invert()), out);
}

/**
 * One step of the turret's and the gun's drives towards the wanted bearing and elevation (hull frame): at most
 * their rates, the turret the short way round, the gun within its limits.
 */
export function layGun(g: GunState, info: GunInfo, want: Angles, dt: number) {
  const turn = info.traverse * RAD * dt, lift = info.elevationRate * RAD * dt;
  g.yaw = wrapAngle(g.yaw + clamp(wrapAngle(want.yaw - g.yaw), -turn, turn));
  const pitch = clamp(want.pitch, info.elevation[0] * RAD, info.elevation[1] * RAD);
  g.pitch = clamp(g.pitch + clamp(pitch - g.pitch, -lift, lift), info.elevation[0] * RAD, info.elevation[1] * RAD);
}

/** drag as the share of its speed a round loses per metre (1/m): `dropPerKm` near the muzzle */
export const dragOf = (info: GunInfo) => info.dropPerKm / 1000 / info.muzzleVelocity;

/** Seconds a round takes to `range` (m): its speed falls by the same share every metre (`dragOf`). */
export function flightTime(info: GunInfo, range: number) {
  const k = dragOf(info);
  return k > 1e-9 ? (Math.exp(k * range) - 1) / (k * info.muzzleVelocity) : range / info.muzzleVelocity;
}

/** How far a round has fallen below its line of departure at `range` (m). */
export const dropAt = (info: GunInfo, range: number) => 0.5 * GRAVITY * flightTime(info, range) ** 2;

/** The angle (rad) the gun is laid above the line of sight to hit at `range` on that line (flat fire). */
export const superelevation = (info: GunInfo, range: number) => Math.atan2(dropAt(info, range), Math.max(range, 1));

/** momentum of one shot (N·s): what the hull takes back along the bore */
export const recoilOf = (info: GunInfo) => info.shot * info.muzzleVelocity + info.charge * GAS_SPEED;

/** The gunner's sight head in the turret's frame (m): the model's, or on the roof, right of the gun. */
export function sightOf(t: TankInfo): [number, number, number] {
  const [tl, tw, th] = t.dims.turret;
  return t.dims.sight ?? [-tw * 0.22, th + 0.12, tl * 0.18];
}

const _ring = new Vector3(), _local = new Vector3();

/**
 * Where the gun is in the world for a hull pose (the body's origin and orientation) and its angles: the trunnions,
 * the muzzle and the bore's direction. `rideHeight`: the body's origin above the ground at rest
 * (`VehicleSim.rideHeight`): the dimensions are measured from the ground.
 */
export function gunPose(spec: CarSpec, rideHeight: number, position: Vector3, q: Quaternion, yaw: number, pitch: number, out: { trunnion: Vector3; muzzle: Vector3; dir: Vector3 }) {
  const d = spec.tank!.dims;
  dirOf(yaw, pitch, _local);
  _ring.set(Math.sin(yaw) * d.trunnionZ, d.ringY - rideHeight + d.trunnion, d.turretZ + Math.cos(yaw) * d.trunnionZ);
  out.muzzle.copy(_ring).addScaledVector(_local, d.barrel).applyQuaternion(q).add(position);
  out.trunnion.copy(_ring).applyQuaternion(q).add(position);
  out.dir.copy(_local).applyQuaternion(q);
  return out;
}

/** The gunner's eye in the world: the sight head on the turret as it stands (`yaw`). */
export function sightEye(spec: CarSpec, rideHeight: number, position: Vector3, q: Quaternion, yaw: number, out: Vector3) {
  const t = spec.tank!;
  const [x, y, z] = sightOf(t);
  const c = Math.cos(yaw), s = Math.sin(yaw);
  return out.set(x * c + z * s, t.dims.ringY - rideHeight + y, t.dims.turretZ - x * s + z * c).applyQuaternion(q).add(position);
}

/** What the player's hands ask of the gun in one step. */
export interface GunInput {
  /** the line of sight moved by this much since the last step (rad; + = to the left, + = up) */
  dYaw: number;
  dPitch: number;
  /** the gunner's sight is in use: the sight is stabilised in the world */
  stabilised: boolean;
  /** turret back to twelve o'clock, gun level */
  recentre: boolean;
}

const _want: Angles = { yaw: 0, pitch: 0 };
const _los = new Vector3();

/**
 * The gun with its fire control: the line of sight (`sight`: relative to the hull, `world`: in the world; the one
 * that is not being held follows from the other every step) and the gun's own state.
 */
export class GunControl {
  readonly gun: GunState;
  readonly info: GunInfo;
  /** the line of sight relative to the hull and in the world */
  readonly sight: Angles = { yaw: 0, pitch: 0 };
  readonly world: Angles = { yaw: 0, pitch: 0 };
  /** the range the fire control works with (m): the laser's, or the battle-sight range */
  range = BATTLE_RANGE;
  /** the laser found something at `range` */
  lased = false;
  private stabilised = false;

  constructor(readonly spec: CarSpec) {
    this.info = spec.tank!.gun;
    this.gun = newGun(this.info);
  }

  /** A new race: the gun forward, loaded, its racks full. */
  reset() {
    Object.assign(this.gun, newGun(this.info));
    this.sight.yaw = this.sight.pitch = 0;
    this.stabilised = false;
    this.range = BATTLE_RANGE;
    this.lased = false;
  }

  /**
   * One physics step: the sight moved by the input and held as asked, the gun laid after it, the round on its way
   * into the breech. `q`: the hull's orientation after the step.
   */
  step(dt: number, q: Quaternion, input: GunInput) {
    const lim = this.info.elevation;
    if (input.recentre) {
      this.sight.yaw = this.sight.pitch = 0;
      this.stabilised = false;
    }
    if (input.stabilised && !input.recentre) {
      // (taking the sight up: it holds the direction it had at that moment)
      if (!this.stabilised) anglesOf(dirOf(this.sight.yaw, this.sight.pitch, _los).applyQuaternion(q), this.world);
      this.world.yaw = wrapAngle(this.world.yaw + input.dYaw);
      this.world.pitch = clamp(this.world.pitch + input.dPitch, -1.4, 1.4);
      hullAngles(q, dirOf(this.world.yaw, this.world.pitch, _los), this.sight);
      // the sight goes no further than the gun can follow: at a limit it is carried along by the hull
      const held = clamp(this.sight.pitch, lim[0] * RAD, lim[1] * RAD);
      if (held !== this.sight.pitch) {
        this.sight.pitch = held;
        anglesOf(dirOf(this.sight.yaw, held, _los).applyQuaternion(q), this.world);
      }
    } else {
      this.sight.yaw = wrapAngle(this.sight.yaw + input.dYaw);
      this.sight.pitch = clamp(this.sight.pitch + input.dPitch, lim[0] * RAD, lim[1] * RAD);
      anglesOf(dirOf(this.sight.yaw, this.sight.pitch, _los).applyQuaternion(q), this.world);
    }
    this.stabilised = input.stabilised && !input.recentre;
    _want.yaw = this.sight.yaw;
    _want.pitch = this.sight.pitch + superelevation(this.info, this.range);
    layGun(this.gun, this.info, _want, dt);
    if (this.gun.reload > 0) this.gun.reload = Math.max(0, this.gun.reload - dt);
  }

  /** the laser's answer (m; null: nothing within its reach) */
  lase(range: number | null) {
    this.lased = range !== null;
    this.range = range ?? BATTLE_RANGE;
  }

  get ready() {
    return this.gun.reload <= 0 && this.gun.ammo > 0;
  }

  /** how far the loading has come (0…1; 1 = ready; with the racks empty it stays 0) */
  get loaded() {
    return this.gun.ammo <= 0 ? 0 : 1 - this.gun.reload / this.info.reload;
  }

  /** how far the gun is off the line it is being laid on (rad) */
  get off() {
    return Math.hypot(wrapAngle(this.sight.yaw - this.gun.yaw) * Math.cos(this.gun.pitch), this.sight.pitch + superelevation(this.info, this.range) - this.gun.pitch);
  }

  /**
   * Fires if a round is in: one round less, the loading begins. Returns the shot's number (from 1), or 0 when
   * there was nothing to fire.
   */
  fire() {
    if (!this.ready) return 0;
    this.gun.ammo--;
    this.gun.reload = this.info.reload;
    return ++this.gun.shots;
  }
}
