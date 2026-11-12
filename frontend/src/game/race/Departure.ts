import { Quaternion, Vector3 } from 'three';
import type { CarSpec } from '../vehicle/carSpecs';
import { EDWARDS_AIR, jetThrust } from '../vehicle/jets';

/**
 * A fighter's take-off after the finish (owner, 2026-11-10: 「ゴール後は自動操縦で勝手に飛んで終わり」). Nothing here is
 * flown by the tyre and body simulation: from the moment the nose comes up the aircraft is carried along this path
 * (`VehicleSim.carry`), a point mass in the vertical plane of its heading:
 *   - `rotate`: on its main wheels in full afterburner, the nose rising 4° a second; it leaves the ground at the
 *     lift-off speed (`JetInfo.lof`) once the attitude gives the lift (far above that speed a degree or two is enough);
 *   - `climb`: thrust less drag (clean once the gear is up, induced drag by the load, the transonic rise) along the
 *     flight path, which is pulled up with at most 2 g to the angle the excess thrust holds (12°…38°: an Eagle goes
 *     up steeply); the gear comes up after a positive climb, in `GEAR_TIME`;
 *   - `gone` after `AWAY` seconds in the air: the game takes the aircraft off the scene.
 * The ground run before the rotation (lined up, afterburner, up to `JetInfo.vr`) is the simulation's own, driven by
 * the game. Estimates: the pull-up load, the induced drag factor, the attitudes; the speeds are the aircraft's.
 */
export type DepartureStage = 'roll' | 'rotate' | 'climb' | 'gone';

const G = 9.81;
const DEG = Math.PI / 180;
/** the nose comes up at this rate (rad/s), to at most this attitude on the ground */
const ROTATION_RATE = 4 * DEG;
const ROTATION = 10 * DEG;
/** the attitude that carries the weight at the lift-off speed */
const LIFT_OFF_ATTITUDE = 8 * DEG;
/** the pull-up's load factor */
const PULL = 2;
/** gear: up from this height (m), in this many seconds */
const GEAR_FROM = 4;
const GEAR_TIME = 4.5;
/** seconds in the air until it is out of the picture */
const AWAY = 26;
const _pitch = new Quaternion(), _axis = new Vector3();
const UP = new Vector3(0, 1, 0);

export class Departure {
  stage: DepartureStage = 'roll';
  /** seconds since the finish, and in the air */
  t = 0;
  airborne = 0;
  /** the body's pose and velocity (the simulation's body origin) */
  readonly position = new Vector3();
  readonly quaternion = new Quaternion();
  readonly velocity = new Vector3();
  speed = 0;
  /** height above the ground run (m), attitude and flight path angle (rad) */
  height = 0;
  pitch = 0;
  path = 0;
  /** landing gear 0 = down … 1 = stowed; the stabilators' nose-up command (rad) */
  gear = 0;
  elevator = 0;

  private readonly origin = new Vector3();
  private readonly dir = new Vector3();
  private readonly heading = new Quaternion();
  private along = 0;
  /** the body origin's distance ahead of the main wheels: the nose comes up about them */
  private readonly arm: number;

  constructor(readonly spec: CarSpec) {
    this.arm = spec.wheelbase / 2;
  }

  /** The ground run ends here: the body's place, its heading (rad, 0 = +Z) and its speed (m/s). */
  rotate(position: Vector3, heading: number, speed: number) {
    this.origin.copy(position);
    this.dir.set(Math.sin(heading), 0, Math.cos(heading));
    this.heading.setFromAxisAngle(UP, heading);
    this.speed = speed;
    this.along = this.height = this.pitch = this.path = 0;
    this.stage = 'rotate';
    this.pose();
  }

  step(dt: number) {
    this.t += dt;
    if (this.stage === 'roll' || this.stage === 'gone') return;
    const jet = this.spec.jet!, w = jet.wing, mass = this.spec.mass;
    const v = Math.max(this.speed, 1);
    const q = 0.5 * EDWARDS_AIR.density * v * v;
    const mach = v / EDWARDS_AIR.sound;
    // the attitude that carries the weight at this speed (lift ∝ v² × attitude)
    const carries = (load: number) => Math.min(Math.max(LIFT_OFF_ATTITUDE * (jet.lof / v) ** 2 * load, 1.2 * DEG), 13 * DEG);
    let load = 1;
    if (this.stage === 'rotate') {
      this.pitch = Math.min(this.pitch + ROTATION_RATE * dt, ROTATION);
      this.elevator = 0.3;
      if (this.speed >= jet.lof && this.pitch >= carries(1)) this.stage = 'climb';
    } else {
      this.airborne += dt;
      const thrust = jetThrust(jet.engines, 1, 1, mach);
      const excess = (thrust - q * w.area * (w.cd0 + 0.035 * smooth(0.85, 1.05, mach))) / (mass * G);
      const want = Math.min(Math.max(Math.asin(Math.min(Math.max(excess, 0), 1)) * 0.6, 12 * DEG), 38 * DEG);
      // (the pull begins gently: the first second off the ground is flown flat)
      const rate = (((PULL - 1) * G) / v) * smooth(0.2, 1.4, this.airborne);
      const step = Math.min(Math.max(want - this.path, -rate * dt), rate * dt);
      this.path += step;
      load = 1 + (v * (step / dt)) / G;
      const attitude = this.path + carries(load);
      this.pitch += (attitude - this.pitch) * (1 - Math.exp(-dt * 3));
      this.elevator += ((step > 1e-6 ? 0.16 : 0.03) - this.elevator) * (1 - Math.exp(-dt * 4));
      if (this.height > GEAR_FROM) this.gear = Math.min(1, this.gear + dt / GEAR_TIME);
      if (this.airborne > AWAY) this.stage = 'gone';
    }
    // along the flight path: thrust in full afterburner, less the drag (gear, lift by the load, the transonic rise)
    const cl = (load * mass * G) / (q * w.area);
    const cd = w.cd0 + w.cdGear * (1 - this.gear) + 0.15 * cl * cl * (this.stage === 'rotate' ? 0 : 1) + 0.035 * smooth(0.85, 1.05, mach);
    const accel = (jetThrust(jet.engines, 1, 1, mach) - q * w.area * cd) / mass - G * Math.sin(this.path);
    this.speed = Math.max(this.speed + accel * dt, 30);
    this.along += this.speed * Math.cos(this.path) * dt;
    this.height += this.speed * Math.sin(this.path) * dt;
    this.pose();
  }

  private pose() {
    // (on its main wheels the centre of mass rises as the nose comes up)
    const lift = this.arm * Math.sin(Math.min(this.pitch, ROTATION));
    this.position.copy(this.origin).addScaledVector(this.dir, this.along);
    this.position.y += this.height + lift;
    // nose up = a turn about the aircraft's left wing (+X) by −pitch
    _axis.set(1, 0, 0);
    this.quaternion.copy(this.heading).multiply(_pitch.setFromAxisAngle(_axis, -this.pitch));
    this.velocity.copy(this.dir).multiplyScalar(this.speed * Math.cos(this.path));
    this.velocity.y = this.speed * Math.sin(this.path);
  }
}

function smooth(a: number, b: number, x: number) {
  const t = Math.min(Math.max((x - a) / (b - a), 0), 1);
  return t * t * (3 - 2 * t);
}
