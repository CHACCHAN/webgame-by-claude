import * as THREE from 'three';
import { clamp, damp, lerp, noise2, wrapAngle } from '../util/math';

export type CameraMode = 'chase' | 'near' | 'bumper';
export const CAMERA_MODES: CameraMode[] = ['chase', 'near', 'bumper'];

export interface CameraSubject {
  position: THREE.Vector3;
  quaternion: THREE.Quaternion;
  velocity: THREE.Vector3;
  speed: number;
  slipAngle: number;
  impact: number;
  /** a bike's lean (rad, + = left): the rider's view rolls with it, the chase view a little */
  lean?: number;
  /**
   * a tank: every view looks along its line of sight instead of along the hull: the sight's bearing off the hull's
   * (rad, + = left) and its elevation above the horizon
   */
  aim?: { yaw: number; pitch: number };
  /**
   * a tank's gunner's sight in use: the camera IS the sight (its eye, its line, the turret's up, its field of view
   * in degrees: the naked eye's divided by the magnification)
   */
  sight?: { eye: THREE.Vector3; dir: THREE.Vector3; up: THREE.Vector3; fov: number } | null;
}

/** Camera placement per vehicle: distances and heights of the chase views, the eye point of the bumper/cab view. */
export interface CameraProfile {
  chase: { dist: number; perKmh: number; height: number };
  near: { dist: number; perKmh: number; height: number };
  /** forward and up offsets of the bumper view (a train: the driver's cab; a bike: the rider's eyes, `height` above
   * the ground, which swing in and down as the bike leans) */
  front: { ahead: number; up: number; height?: number };
}
export const CAR_CAMERA: CameraProfile = {
  chase: { dist: 6.4, perKmh: 0.008, height: 2.15 },
  near: { dist: 4.6, perKmh: 0.005, height: 1.55 },
  front: { ahead: 0.6, up: 0.75 },
};
/** a bike: a closer, lower chase; the front view from the rider's helmet, tucked behind the screen */
export const BIKE_CAMERA: CameraProfile = {
  chase: { dist: 4.7, perKmh: 0.006, height: 1.75 },
  near: { dist: 3.3, perKmh: 0.004, height: 1.4 },
  front: { ahead: 0.05, up: 0.55, height: 1.16 },
};
/** a 60 m train: chase from high above the leading car, the front view from the cab (2.85 m ahead of the bogie) */
export const TRAIN_CAMERA: CameraProfile = {
  chase: { dist: 15, perKmh: 0.03, height: 7.5 },
  near: { dist: 9, perKmh: 0.02, height: 5 },
  front: { ahead: 2.5, up: 2.55 },
};

/** a fighter, 19–23 m long with a 13–17 m span: the chase takes all of it in; the front view from the cockpit */
export const JET_CAMERA: CameraProfile = {
  chase: { dist: 27, perKmh: 0.012, height: 8 },
  near: { dist: 21, perKmh: 0.008, height: 6.2 },
  front: { ahead: 3.6, up: 1.5 },
};

/**
 * a tank, 9–11 m over its gun and 3.2–3.8 m wide: the chase stands high enough to see the road over the turret
 * (the views look where the sight does: `CameraSubject.aim`); the front view is the commander's, head out of the hatch
 */
export const TANK_CAMERA: CameraProfile = {
  chase: { dist: 12.5, perKmh: 0.02, height: 5.4 },
  near: { dist: 9, perKmh: 0.012, height: 4.3 },
  front: { ahead: -0.2, up: 2.3 },
};

/** the most the chase camera trails its damped target (m): what ~500 km/h gives */
const MAX_LAG = 10;
const _fwd = new THREE.Vector3(), _desired = new THREE.Vector3(), _look = new THREE.Vector3(), _up = new THREE.Vector3();
const _left = new THREE.Vector3(), _worldUp = new THREE.Vector3(0, 1, 0);

/**
 * Third-person chase camera. During slides it swings towards the direction
 * of travel so the car is framed sideways, FOV widens with speed and there is
 * a little high-speed and impact shake.
 */
export class ChaseCamera {
  mode: CameraMode = 'chase';
  private yaw = 0;
  private pos = new THREE.Vector3();
  private initialized = false;
  private shakeT = 0;
  private impactShake = 0;
  private lookHeight = 1;
  fovBase = 60;
  profile = CAR_CAMERA;
  private inSight = false;

  constructor(readonly camera: THREE.PerspectiveCamera, private groundAt: (x: number, z: number) => number) {}

  reset() {
    this.initialized = false;
  }

  /** The eye off a tank's sight (its lens is taken out of the camera): whoever moves the camera next finds it as it was. */
  leaveSight() {
    if (!this.inSight) return;
    this.inSight = false;
    this.camera.fov = this.fovBase;
    this.camera.updateProjectionMatrix();
  }

  cycle() {
    this.mode = CAMERA_MODES[(CAMERA_MODES.indexOf(this.mode) + 1) % CAMERA_MODES.length];
    this.initialized = false;
  }

  update(dt: number, s: CameraSubject) {
    const cam = this.camera;
    if (s.sight) {
      // the gunner's sight: nothing of a chase camera in it; the picture moves only as the gun and the hull do
      cam.position.copy(s.sight.eye);
      cam.up.copy(s.sight.up);
      cam.lookAt(_look.copy(s.sight.eye).add(s.sight.dir));
      cam.up.set(0, 1, 0);
      if (Math.abs(cam.fov - s.sight.fov) > 0.01) {
        // (a change of magnification is a lens swung in: quick, not a zoom)
        cam.fov = this.inSight ? damp(cam.fov, s.sight.fov, 18, dt) : s.sight.fov;
        cam.updateProjectionMatrix();
      }
      this.inSight = true;
      this.initialized = false;
      return;
    }
    if (this.inSight) {
      // the eye off the sight: the driving view as it is, at once
      this.inSight = false;
      cam.fov = this.fovBase;
      cam.updateProjectionMatrix();
    }
    const aimYaw = s.aim?.yaw ?? 0, aimPitch = s.aim?.pitch ?? 0;
    _fwd.set(0, 0, 1).applyQuaternion(s.quaternion);
    const carYaw = Math.atan2(_fwd.x, _fwd.z);
    const planar = Math.hypot(s.velocity.x, s.velocity.z);
    const velYaw = planar > 3 ? Math.atan2(s.velocity.x, s.velocity.z) : carYaw;
    // follow the travel direction during slides
    const slide = clamp(Math.abs(s.slipAngle) / 0.6, 0, 1);
    const reversing = _fwd.dot(s.velocity) < -2;
    const targetYaw = reversing ? carYaw : carYaw + wrapAngle(velYaw - carYaw) * lerp(0.15, 0.6, slide);
    if (!this.initialized) this.yaw = targetYaw;
    this.yaw += wrapAngle(targetYaw - this.yaw) * (1 - Math.exp(-dt * (this.mode === 'bumper' ? 30 : 5.5)));

    const kmh = s.speed * 3.6;
    this.impactShake = Math.max(this.impactShake * Math.exp(-dt * 6), s.impact);
    this.shakeT += dt * (8 + kmh * 0.12);

    const lean = s.lean ?? 0;
    if (this.mode === 'bumper') {
      _up.set(0, 1, 0).applyQuaternion(s.quaternion);
      const front = this.profile.front;
      _desired.copy(s.position).addScaledVector(_fwd, front.ahead).addScaledVector(_up, front.up);
      if (front.height && lean) {
        // the rider's head swings in towards the bend (+X is the bike's left) and down
        _left.set(1, 0, 0).applyQuaternion(s.quaternion);
        _desired.addScaledVector(_left, front.height * Math.sin(lean)).addScaledVector(_up, -front.height * (1 - Math.cos(lean)));
      }
      this.pos.copy(_desired);
      if (s.aim) {
        const c = Math.cos(aimPitch) * 20;
        _look.set(Math.sin(carYaw + aimYaw) * c, Math.sin(aimPitch) * 20, Math.cos(carYaw + aimYaw) * c).add(_desired);
      } else _look.copy(_desired).addScaledVector(_fwd, 20);
      cam.position.copy(this.pos);
      cam.up.copy(_up).lerp(_worldUp, 0.6);
      // and the horizon tilts with the bike (most of its lean: a rider keeps the head a little more upright)
      if (lean) cam.up.applyAxisAngle(_fwd, -lean * 0.8);
      cam.lookAt(_look);
      cam.up.set(0, 1, 0);
    } else {
      const view = this.mode === 'chase' ? this.profile.chase : this.profile.near;
      // the camera falls back with speed, up to 500 km/h (beyond, at the cockroach's Mach 1, it would be a speck)
      const dist = view.dist + Math.min(kmh, 500) * view.perKmh;
      const height = view.height;
      const dir = new THREE.Vector3(Math.sin(this.yaw + aimYaw), 0, Math.cos(this.yaw + aimYaw));
      // (a sight raised or lowered: the camera swings the other way round the vehicle, half as far)
      _desired.copy(s.position).addScaledVector(dir, -dist * Math.cos(aimPitch));
      _desired.y += height - dist * Math.sin(aimPitch) * 0.5;
      if (!this.initialized) this.pos.copy(_desired);
      // stiffer horizontally, softer vertically for a floaty feel over crests
      this.pos.x = damp(this.pos.x, _desired.x, 14, dt);
      this.pos.z = damp(this.pos.z, _desired.z, 14, dt);
      // the damping trails the target by speed / 14 (8 m at 410 km/h): held to MAX_LAG so Mach 1 keeps it in view
      const lagX = this.pos.x - _desired.x, lagZ = this.pos.z - _desired.z;
      const lag = Math.hypot(lagX, lagZ);
      if (lag > MAX_LAG) {
        this.pos.x = _desired.x + (lagX * MAX_LAG) / lag;
        this.pos.z = _desired.z + (lagZ * MAX_LAG) / lag;
      }
      this.pos.y = damp(this.pos.y, _desired.y, 7, dt);
      const ground = this.groundAt(this.pos.x, this.pos.z) + 0.9;
      if (this.pos.y < ground) this.pos.y = ground;
      if (this.pos.y < s.position.y + 0.6) this.pos.y = s.position.y + 0.6;
      cam.position.copy(this.pos);
      this.lookHeight = damp(this.lookHeight, this.mode === 'chase' ? 1.0 : 0.9, 4, dt);
      _look.copy(s.position).addScaledVector(dir, 3 + kmh * 0.012 + (s.aim ? 30 : 0));
      _look.y += this.lookHeight + (s.aim ? 33 * Math.tan(aimPitch) : 0);
      cam.lookAt(_look);
      if (lean) cam.rotateZ(lean * 0.12);
    }

    // shake
    const speedShake = clamp((kmh - 110) / 120, 0, 1) * 0.012;
    const amt = speedShake + this.impactShake * 0.08;
    if (amt > 0.0005) {
      cam.rotation.x += noise2(this.shakeT, 1.3) * amt;
      cam.rotation.y += noise2(this.shakeT, 7.1) * amt;
    }
    const fov = this.fovBase + clamp(kmh / 200, 0, 1) * 16 + (this.mode === 'bumper' ? 6 : 0);
    if (Math.abs(cam.fov - fov) > 0.01) {
      cam.fov = damp(cam.fov, fov, 3, dt);
      cam.updateProjectionMatrix();
    }
    this.initialized = true;
  }
}
