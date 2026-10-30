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
}

const _fwd = new THREE.Vector3(), _desired = new THREE.Vector3(), _look = new THREE.Vector3(), _up = new THREE.Vector3();

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

  constructor(readonly camera: THREE.PerspectiveCamera, private groundAt: (x: number, z: number) => number) {}

  reset() {
    this.initialized = false;
  }

  cycle() {
    this.mode = CAMERA_MODES[(CAMERA_MODES.indexOf(this.mode) + 1) % CAMERA_MODES.length];
    this.initialized = false;
  }

  update(dt: number, s: CameraSubject) {
    const cam = this.camera;
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

    if (this.mode === 'bumper') {
      _up.set(0, 1, 0).applyQuaternion(s.quaternion);
      _desired.copy(s.position).addScaledVector(_fwd, 0.6).addScaledVector(_up, 0.75);
      this.pos.copy(_desired);
      _look.copy(_desired).addScaledVector(_fwd, 20);
      cam.position.copy(this.pos);
      cam.up.copy(_up).lerp(new THREE.Vector3(0, 1, 0), 0.6);
      cam.lookAt(_look);
      cam.up.set(0, 1, 0);
    } else {
      const dist = this.mode === 'chase' ? 6.4 + kmh * 0.008 : 4.6 + kmh * 0.005;
      const height = this.mode === 'chase' ? 2.15 : 1.55;
      const dir = new THREE.Vector3(Math.sin(this.yaw), 0, Math.cos(this.yaw));
      _desired.copy(s.position).addScaledVector(dir, -dist);
      _desired.y += height;
      if (!this.initialized) this.pos.copy(_desired);
      // stiffer horizontally, softer vertically for a floaty feel over crests
      this.pos.x = damp(this.pos.x, _desired.x, 14, dt);
      this.pos.z = damp(this.pos.z, _desired.z, 14, dt);
      this.pos.y = damp(this.pos.y, _desired.y, 7, dt);
      const ground = this.groundAt(this.pos.x, this.pos.z) + 0.9;
      if (this.pos.y < ground) this.pos.y = ground;
      if (this.pos.y < s.position.y + 0.6) this.pos.y = s.position.y + 0.6;
      cam.position.copy(this.pos);
      this.lookHeight = damp(this.lookHeight, this.mode === 'chase' ? 1.0 : 0.9, 4, dt);
      _look.copy(s.position).addScaledVector(dir, 3 + kmh * 0.012);
      _look.y += this.lookHeight;
      cam.lookAt(_look);
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
