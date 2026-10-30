import * as THREE from 'three';
import type { CarSpec } from '../vehicle/carSpecs';
import type { VehicleSim } from '../vehicle/VehicleSim';
import { buildCar, type CarRig } from './CarModel';
import { clamp, damp } from '../util/math';

const _q = new THREE.Quaternion(), _p = new THREE.Vector3();
const AXIS_Y = new THREE.Vector3(0, 1, 0), AXIS_X = new THREE.Vector3(1, 0, 0);

/** Pose source for a car visual: a live simulation or a ghost replay. */
export interface CarPose {
  position: THREE.Vector3;
  quaternion: THREE.Quaternion;
  /** body-local suspension length per wheel (FL, FR, RL, RR) */
  wheelLengths?: number[];
  wheelRotations?: number[];
  steer?: number;
  braking?: boolean;
  reversing?: boolean;
}

/**
 * Renderable car: procedural model + headlight spotlights + beam cones.
 * The visual pose is interpolated between physics steps.
 */
export class CarVisual {
  readonly rig: CarRig;
  readonly root: THREE.Group;
  readonly spec: CarSpec;
  readonly headlights: THREE.SpotLight[] = [];
  private beams: THREE.Mesh[] = [];
  private bodyPitch = 0;
  private bodyRoll = 0;
  private ghostMaterials: THREE.Material[] = [];
  readonly rideHeight: number;

  constructor(spec: CarSpec, opts: { headlights: boolean; shadows: boolean; ghost?: boolean; bodyColor?: string; rideHeight: number }) {
    this.spec = spec;
    this.rideHeight = opts.rideHeight;
    this.rig = buildCar(spec, { bodyColor: opts.bodyColor });
    this.root = new THREE.Group();
    this.root.add(this.rig.root);
    this.rig.root.position.y = -opts.rideHeight;

    this.rig.root.traverse((o) => {
      if ((o as THREE.Mesh).isMesh) {
        (o as THREE.Mesh).castShadow = opts.shadows && !opts.ghost;
        (o as THREE.Mesh).receiveShadow = !opts.ghost;
      }
    });

    if (opts.ghost) this.makeGhost();

    if (opts.headlights && !opts.ghost) {
      const front = this.rig.anchors.headlights[0]?.z ?? 2;
      const spot = new THREE.SpotLight('#fff1dc', 260, 140, 0.48, 0.55, 1.4);
      spot.position.set(0, 0.75, front + 0.1);
      spot.target.position.set(0, -0.4, front + 30);
      spot.castShadow = opts.shadows;
      spot.shadow.mapSize.set(1024, 1024);
      spot.shadow.camera.near = 0.5;
      spot.shadow.camera.far = 140;
      spot.shadow.bias = -0.0006;
      this.rig.root.add(spot, spot.target);
      this.headlights.push(spot);
      // volumetric-ish beam cones
      const beamMat = new THREE.ShaderMaterial({
        transparent: true,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
        side: THREE.DoubleSide,
        uniforms: { uIntensity: { value: 0.0 } },
        vertexShader: /* glsl */ `
          varying float vT; varying vec3 vN; varying vec3 vV;
          void main() {
            vT = uv.y;
            vN = normalize(normalMatrix * normal);
            vec4 mv = modelViewMatrix * vec4(position, 1.0);
            vV = normalize(-mv.xyz);
            gl_Position = projectionMatrix * mv;
          }`,
        fragmentShader: /* glsl */ `
          uniform float uIntensity; varying float vT; varying vec3 vN; varying vec3 vV;
          void main() {
            float edge = pow(abs(dot(vN, vV)), 1.5);
            float a = pow(vT, 2.2) * edge * uIntensity;
            gl_FragColor = vec4(vec3(1.0, 0.93, 0.8) * a, 1.0);
          }`,
      });
      for (const hl of this.rig.anchors.headlights) {
        const cone = new THREE.Mesh(new THREE.ConeGeometry(3.2, 22, 24, 1, true), beamMat);
        cone.rotation.x = -Math.PI / 2 - 0.05;
        cone.position.set(hl.x, hl.y, hl.z + 11);
        this.rig.root.add(cone);
        this.beams.push(cone);
      }
    }
  }

  setHeadlights(on: number) {
    for (const s of this.headlights) s.intensity = 260 * on;
    for (const b of this.beams) {
      ((b.material as THREE.ShaderMaterial).uniforms.uIntensity.value as number) = 0.05 * on;
      b.visible = on > 0.05;
    }
    this.rig.materials.headlight.emissiveIntensity = 4 * on;
  }

  private makeGhost() {
    this.rig.root.traverse((o) => {
      const m = o as THREE.Mesh;
      if (!m.isMesh) return;
      const mats = Array.isArray(m.material) ? m.material : [m.material];
      const ghostMats = mats.map(() => {
        const gm = new THREE.MeshBasicMaterial({
          color: '#7fd4ff',
          transparent: true,
          opacity: 0.22,
          depthWrite: false,
          blending: THREE.AdditiveBlending,
        });
        this.ghostMaterials.push(gm);
        return gm;
      });
      m.material = Array.isArray(m.material) ? ghostMats : ghostMats[0];
      m.castShadow = false;
    });
  }

  setGhostOpacity(o: number) {
    for (const m of this.ghostMaterials) (m as THREE.MeshBasicMaterial).opacity = o;
  }

  /** Update from a live simulation with interpolation factor alpha (0..1). */
  syncFromSim(sim: VehicleSim, alpha: number, dt: number) {
    this.root.position.lerpVectors(sim.prevPosition, sim.position, alpha);
    this.root.quaternion.slerpQuaternions(sim.prevQuaternion, sim.quaternion, alpha);
    // exaggerated body motion from the physics state
    const longAcc = clamp(-sim.forwardSpeed * 0, -1, 1);
    void longAcc;
    const targetRoll = clamp(sim.yawRate * sim.forwardSpeed * 0.0035, -0.06, 0.06);
    this.bodyRoll = damp(this.bodyRoll, targetRoll, 6, dt);
    const braking = sim.input.brake > 0.2 && sim.gear !== -1;
    const targetPitch = braking ? 0.018 : sim.input.throttle > 0.5 ? -0.012 : 0;
    this.bodyPitch = damp(this.bodyPitch, targetPitch, 5, dt);
    this.rig.body.rotation.set(this.bodyPitch, 0, this.bodyRoll);
    const r = this.spec.wheelRadius;
    sim.wheels.forEach((w, i) => {
      const wv = this.rig.wheels[i];
      // wheel centre in body space, expressed in the visual (ground-based) frame
      const y = w.mount.y - w.length + this.rideHeight;
      wv.pivot.position.y = damp(wv.pivot.position.y, Math.max(r * 0.8, y), 30, dt);
      wv.pivot.rotation.y = w.steer;
      wv.spin.rotation.x = w.rotation;
    });
    this.setBrakeLights(braking || sim.input.handbrake);
  }

  /** Update from a ghost pose. */
  syncFromPose(p: CarPose, dt: number) {
    this.root.position.copy(p.position);
    this.root.quaternion.copy(p.quaternion);
    if (p.wheelRotations) this.rig.wheels.forEach((w, i) => (w.spin.rotation.x = p.wheelRotations![i]));
    if (p.steer !== undefined) {
      this.rig.wheels[0].pivot.rotation.y = damp(this.rig.wheels[0].pivot.rotation.y, p.steer, 10, dt);
      this.rig.wheels[1].pivot.rotation.y = this.rig.wheels[0].pivot.rotation.y;
    }
  }

  setBrakeLights(on: boolean) {
    this.rig.materials.taillight.emissiveIntensity = on ? 7 : 1.6;
  }

  dispose() {
    this.root.traverse((o) => {
      const m = o as THREE.Mesh;
      if (m.isMesh) {
        m.geometry.dispose();
        const mats = Array.isArray(m.material) ? m.material : [m.material];
        mats.forEach((x) => x.dispose());
      }
    });
    void _q;
    void _p;
    void AXIS_X;
    void AXIS_Y;
  }
}
