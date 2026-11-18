import * as THREE from 'three';
import { MeshBasicNodeMaterial } from 'three/webgpu';
import { abs, clamp as clampNode, dot, normalView, positionViewDirection, pow, uniform, uv, vec3, vec4 } from 'three/tsl';
import type { CarSpec } from '../vehicle/carSpecs';
import { trainNoseZ } from '../vehicle/trains';
import { traitsOf } from '../vehicle/kinds';
import type { VehicleSim } from '../vehicle/VehicleSim';
import { buildCar, paintFinish, type CarRig } from './CarModel';
import { clamp, damp } from '../util/math';
import { beamCones, type VolumeSpot } from './volumetricLights';
import { HEADLIGHT } from './LightRig';

const _q = new THREE.Quaternion(), _p = new THREE.Vector3(), _aim = new THREE.Vector3();
const AXIS_Y = new THREE.Vector3(0, 1, 0), AXIS_X = new THREE.Vector3(1, 0, 0);
/** the materials of a car model's parts that throw shadows */
const SHADOW_PARTS = /^(paint|accent|trim|glass|tire|rim|airframe)$/;
/** headlight level from which pop-up lamps open and position lamps count as "on" (below: daytime) */
const LIGHTS_ON = 0.75;
/** pop-up pod: width, height, depth (m); hinge angle closed / open (rad, + = folded into the bonnet) */
const POD = { w: 0.36, h: 0.13, d: 0.25, closed: 1.45, open: -0.06 };

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
  /** a fighter's engines (the flames), when no simulation is behind the pose */
  engines?: { spool: number; afterburner: number };
}

/**
 * Renderable car: procedural model + headlight spotlights + beam cones.
 * The visual pose is interpolated between physics steps.
 */
export class CarVisual {
  readonly rig: CarRig;
  readonly root: THREE.Group;
  readonly spec: CarSpec;
  /** the body colour (a train's or the cockroach's livery swatch) */
  color: string | undefined;
  /**
   * Where the headlights' real light starts and what it is aimed at; the light itself is one of the game's pooled
   * spots (render/LightRig.ts): one per vehicle, so it starts between the lamps, at their height, just ahead of
   * the nose (inside the body the shell would throw its shadow over all of it).
   */
  private lampOrigin: THREE.Object3D | null = null;
  private lampAim: THREE.Object3D | null = null;
  /** the lamps themselves, in the frame of what they hang on: where the glow in the haze starts (a cone each) */
  private lampSources: THREE.Vector3[] = [];
  private lampParent: THREE.Object3D | null = null;
  private beamIntensity = 0;
  private beams: THREE.Mesh[] = [];
  /** brightness of the beam cones (shared by this car's cones) */
  private beamLevel = uniform(0);
  private bodyPitch = 0;
  private bodyRoll = 0;
  private ghostMaterials: THREE.Material[] = [];
  readonly rideHeight: number;
  /** retractable headlamp pods (hinges), their lens material and opening state 0..1 */
  private pods: THREE.Object3D[] = [];
  private podLens: THREE.MeshStandardMaterial | null = null;
  /** hinge angles; runtime pods are hidden while folded, the model's own fold into the bonnet */
  private podAngles = { closed: POD.closed, open: POD.open };
  private podHide = true;
  private podOpen = 0;
  private podTarget = 0;
  private lightLevel = 0;
  /** tail lamp glow when not braking (position lamps at night) */
  private tailBase = 0.9;
  /** the live sim this visual follows (a bike's wheelie / stoppie), if any */
  private live: VehicleSim | null = null;
  private engines: { spool: number; afterburner: number } | null = null;

  constructor(spec: CarSpec, opts: { headlights: boolean; shadows: boolean; ghost?: boolean; bodyColor?: string; rideHeight: number }) {
    this.spec = spec;
    this.color = opts.bodyColor;
    this.rideHeight = opts.rideHeight;
    this.rig = buildCar(spec, { bodyColor: opts.bodyColor });
    this.root = new THREE.Group();
    this.root.add(this.rig.root);
    this.rig.root.position.y = -opts.rideHeight;

    const meshes: THREE.Mesh[] = [];
    this.rig.root.traverse((o) => {
      if ((o as THREE.Mesh).isMesh) meshes.push(o as THREE.Mesh);
    });
    const named = (m: THREE.Mesh, test: (name: string) => boolean) => ([] as THREE.Material[]).concat(m.material).some((x) => test(x.name));
    // on our car models (their materials carry the contract's names) only the shell, the glass and the wheels throw
    // shadows: every caster is a draw call in every shadow map, and the lamps, the cabin and the brakes sit inside
    // (a fighter's model is one atlas, `airframe`: its lamps and the afterburner's plume throw none)
    const sorted = meshes.some((m) => named(m, (n) => n === 'paint' || n === 'airframe'));
    for (const m of meshes) {
      m.castShadow = opts.shadows && !opts.ghost && (!sorted || named(m, (n) => SHADOW_PARTS.test(n)));
      m.receiveShadow = !opts.ghost;
    }

    if (opts.ghost) this.makeGhost();
    if (this.rig.popUps && !opts.ghost) this.useModelPods(this.rig.popUps);
    else if (spec.popUpLamps && this.rig.fromModel && !opts.ghost) this.buildPods(spec.popUpLamps);

    if (opts.headlights && !opts.ghost) {
      // a train's lamps sit on its leading car, which follows the path and not the simulated bogie's yaw
      const lamps = (this.lampParent = this.rig.lampParent ?? this.rig.root);
      // the beams come out of the raised pods on pop-up cars
      const sources = this.pods.length ? this.pods.map((h) => new THREE.Vector3(h.position.x, h.position.y + POD.h * 0.55, h.position.z + POD.d)) : this.rig.anchors.headlights;
      // The light comes from where the lamps are (owner 11-12: every vehicle's light started in the wrong place:
      // at one height per kind — above a car's bonnet, at a motorcycle's front wheel, under a train's roof lamps).
      const height = sources.length ? sources.reduce((sum, v) => sum + v.y, 0) / sources.length : traitsOf(spec).lampHeight;
      const lens = sources.length ? Math.max(...sources.map((v) => v.z)) : 2;
      let front = lens + 0.1;
      if (spec.train) {
        // a train's lamps can sit back on a long nose: its light starts at the tip, clear of the body's shadow
        front = trainNoseZ(spec.train) + 0.3;
      } else {
        // just ahead of whatever of the body stands before the lamps (a bumper, a bike's front wheel); a skinned
        // model's box is its rest pose's, in another scale
        const box = new THREE.Box3();
        this.rig.root.traverse((o) => {
          const m = o as THREE.SkinnedMesh;
          if (m.isMesh && !m.isSkinnedMesh) box.expandByObject(m);
        });
        if (!box.isEmpty()) front = Math.max(front, Math.min(box.max.z, lens + 0.6) + 0.05);
      }
      const origin = (this.lampOrigin = new THREE.Object3D());
      const aim = (this.lampAim = new THREE.Object3D());
      origin.position.set(0, height, front);
      aim.position.set(0, -0.4, front + 30);
      lamps.add(origin, aim);
      // (two lamps close together glow as one: a Shinkansen's pair on the cab roof)
      const spread = sources.length ? Math.max(...sources.map((v) => v.x)) - Math.min(...sources.map((v) => v.x)) : 0;
      this.lampSources = spread >= 0.5 ? sources.map((v) => v.clone()) : [new THREE.Vector3(0, height, lens)];
      // volumetric-ish beam cones
      const beamMat = new MeshBasicNodeMaterial({ transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide, fog: false });
      {
        // brightest seen along the cone's wall, fading to nothing at its far rim. The clamp matters: interpolation
        // leaves v a hair below 0 at the rim, pow() of a negative base is NaN, and one NaN pixel spread by the bloom
        // blur blacked out the whole frame
        const edge = pow(abs(dot(normalView, positionViewDirection)), 1.5);
        // (with the lights' glow in the haze on, that pass draws the beams: render/volumetricLights.ts)
        const a = pow(clampNode(uv().y, 0, 1), 2.2).mul(edge).mul(this.beamLevel).mul(beamCones);
        beamMat.colorNode = vec4(vec3(1, 0.93, 0.8).mul(a), 1);
      }
      for (const hl of sources) {
        const cone = new THREE.Mesh(new THREE.ConeGeometry(3.2, 22, 24, 1, true), beamMat);
        // apex at the lamp, dipping towards the road 22 m ahead (more from high lamps, e.g. a train's roof lamps)
        const dip = clamp((hl.y - 0.3) / 22, 0.03, 0.15);
        cone.rotation.x = -Math.PI / 2 + dip;
        cone.position.set(hl.x, hl.y - 11 * Math.sin(dip), hl.z + 11 * Math.cos(dip));
        lamps.add(cone);
        this.beams.push(cone);
      }
    }
  }

  /**
   * Headlight level (1 at night; ~0.5 by day = daytime running lights). Pop-up lamps open only at
   * night and stay shut (and dark) by day; `instant` skips their animation (garage).
   */
  setHeadlights(on: number, instant = false) {
    this.lightLevel = on;
    this.tailBase = on >= LIGHTS_ON ? 3.4 : 0.9;
    this.rig.train?.setInterior(on >= LIGHTS_ON ? 1 : 0);
    if (this.pods.length) {
      this.podTarget = on >= LIGHTS_ON ? 1 : 0;
      if (instant) this.podOpen = this.podTarget;
      // the bumper lamps of a pop-up car are only parking lamps
      this.rig.materials.headlight.emissiveIntensity = on >= LIGHTS_ON ? 1.2 : 0;
      this.applyPods();
    } else {
      this.applyBeams(on);
      this.rig.materials.headlight.emissiveIntensity = 4 * on;
      this.rig.jet?.setLights(on >= LIGHTS_ON ? 1 : 0);
    }
    this.setBrakeLights(false);
  }

  /**
   * The headlights' cones, for the glow in the haze (render/volumetricLights.ts): one from each lamp, into `pool`
   * from `at` on, as many as fit. Returns how many (0 when the car has no lamps or they are off).
   */
  beamsInto(pool: VolumeSpot[], at: number): number {
    const intensity = this.beamNow();
    if (!this.lampOrigin || !this.lampParent || !(intensity > 0) || !this.root.visible) return 0;
    // (this also brings the lamps' parent up to date)
    this.lampOrigin.getWorldPosition(_p);
    this.lampAim!.getWorldPosition(_aim).sub(_p).normalize();
    const n = Math.min(this.lampSources.length, pool.length - at);
    for (let k = 0; k < n; k++) {
      const out = pool[at + k];
      out.position.copy(this.lampSources[k]).applyMatrix4(this.lampParent.matrixWorld);
      out.direction.copy(_aim);
      out.color.set(HEADLIGHT.color);
      // (together they are the one real light)
      out.intensity = intensity / this.lampSources.length;
      out.angle = HEADLIGHT.angle;
      out.penumbra = HEADLIGHT.penumbra;
    }
    return n;
  }

  /** The headlights as a real light, for one of the game's pooled spots (`LightRig.beams`): 0 when dark or absent. */
  headlight(position: THREE.Vector3, target: THREE.Vector3): number {
    const intensity = this.beamNow();
    if (!this.lampOrigin || !(intensity > 0) || !this.root.visible) return 0;
    this.lampOrigin.getWorldPosition(position);
    this.lampAim!.getWorldPosition(target);
    return intensity;
  }

  /** the headlights' strength now: a fighter's taxi lamp goes out with its gear (only the spot's intensity changes) */
  private beamNow() {
    return this.rig.jet ? this.beamIntensity * this.rig.jet.taxiLamp() : this.beamIntensity;
  }

  private applyBeams(level: number) {
    this.beamIntensity = this.lampOrigin ? HEADLIGHT.intensity * level : 0;
    this.beamLevel.value = 0.05 * level;
    for (const b of this.beams) {
      b.visible = level > 0.05;
    }
  }

  /** Pods hinged at the rear edge of their lid, lying folded inside the bonnet until they open. */
  private buildPods(cfg: { x: number; z: number }) {
    const body = this.rig.body;
    this.rig.root.updateMatrixWorld(true);
    const box = new THREE.Box3().setFromObject(body);
    const toRig = this.rig.root.matrixWorld.clone().invert();
    const meshes: THREE.Object3D[] = [];
    body.traverse((o) => {
      if ((o as THREE.Mesh).isMesh) meshes.push(o);
    });
    const ray = new THREE.Raycaster();
    const front = box.clone().applyMatrix4(toRig).max.z;
    this.podLens = new THREE.MeshStandardMaterial({ color: '#dfe6ee', emissive: '#fff4e0', emissiveIntensity: 0, roughness: 0.1, metalness: 0.3 });
    const geoBox = new THREE.BoxGeometry(POD.w, POD.h, POD.d).translate(0, POD.h / 2, POD.d / 2);
    const geoBezel = new THREE.PlaneGeometry(POD.w * 0.94, POD.h * 0.86).translate(0, POD.h / 2, POD.d + 0.002);
    const geoLens = new THREE.PlaneGeometry(POD.w * 0.8, POD.h * 0.62).translate(0, POD.h / 2, POD.d + 0.004);
    for (const side of [1, -1]) {
      const x = side * cfg.x, zc = front - cfg.z;
      // bonnet height at the lid centre: cast down onto the body
      const from = new THREE.Vector3(x, box.max.y + 1, zc).applyMatrix4(this.rig.root.matrixWorld);
      ray.set(from, new THREE.Vector3(0, -1, 0));
      const hit = ray.intersectObjects(meshes, false)[0];
      const y = hit ? hit.point.applyMatrix4(toRig).y : box.clone().applyMatrix4(toRig).max.y - 0.5;
      const hinge = new THREE.Group();
      hinge.name = 'popup_pod';
      hinge.position.set(x, y - 0.012, zc - POD.d / 2);
      const shell = new THREE.Mesh(geoBox, this.rig.materials.paint);
      const bezel = new THREE.Mesh(geoBezel, this.rig.materials.trim);
      const lens = new THREE.Mesh(geoLens, this.podLens);
      for (const m of [shell, bezel, lens]) {
        m.castShadow = true;
        hinge.add(m);
      }
      body.add(hinge);
      this.pods.push(hinge);
    }
    this.applyPods();
  }

  /** Pop-up lamps that are part of the model (modelled raised): they fold forward into the bonnet by day. */
  private useModelPods(p: NonNullable<CarRig['popUps']>) {
    this.pods = p.hinges;
    this.podLens = p.lens;
    this.podAngles = { closed: p.closed, open: 0 };
    this.podHide = false;
    this.applyPods();
  }

  private applyPods() {
    const k = this.podOpen;
    const { closed, open } = this.podAngles;
    for (const h of this.pods) {
      h.rotation.x = closed + (open - closed) * k;
      h.visible = !this.podHide || k > 0.02;
    }
    // full beam only once the pods are (nearly) up
    const lit = this.lightLevel * THREE.MathUtils.smoothstep(k, 0.6, 1);
    if (this.podLens) this.podLens.emissiveIntensity = 5 * lit;
    this.applyBeams(lit);
  }

  /** Re-place the parts that follow the pose (a train's cars) after moving the root by hand (garage). */
  refresh() {
    this.rig.train?.update(this.rig.root);
  }

  /** Recolour: the paint, a train's livery or a creature's colouring. */
  setColor(color: string) {
    this.color = color;
    if (this.rig.train) this.rig.train.setLivery(color);
    else if (this.rig.creature) this.rig.creature.setLivery(color);
    else paintFinish(this.rig.materials.paint, this.spec, color);
  }

  /** Per-frame animation (pop-up lamps take ~0.6 s; a train's cars follow the leading bogie; a creature's legs run). */
  private tick(dt: number) {
    this.rig.train?.update(this.rig.root, dt);
    this.rig.creature?.update(this.root, dt, this.live?.airborne);
    this.rig.bike?.update(this.root, dt, this.live ?? undefined);
    this.rig.tank?.update(this.root, dt);
    this.rig.jet?.update(this.root, dt, this.live ?? this.engines);
    if (!this.pods.length || this.podOpen === this.podTarget) return;
    const step = dt / 0.6;
    this.podOpen = this.podTarget > this.podOpen ? Math.min(this.podTarget, this.podOpen + step) : Math.max(this.podTarget, this.podOpen - step);
    this.applyPods();
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
    this.live = sim;
    this.tick(dt);
  }

  /** a bike's lean (rad, + = left; 0 for anything else): the rider's view rolls with it */
  get lean() {
    return this.rig.bike?.lean ?? 0;
  }

  /** how far a creature's wings are out (0…1; 0 for anything else): its sound flutters with them */
  get flight() {
    return this.rig.creature?.flight ?? 0;
  }

  /** Update from a ghost pose. */
  syncFromPose(p: CarPose, dt: number) {
    this.live = null;
    this.engines = p.engines ?? null;
    this.root.position.copy(p.position);
    this.root.quaternion.copy(p.quaternion);
    if (p.wheelRotations) this.rig.wheels.forEach((w, i) => (w.spin.rotation.x = p.wheelRotations![i]));
    if (p.steer !== undefined) {
      this.rig.wheels[0].pivot.rotation.y = damp(this.rig.wheels[0].pivot.rotation.y, p.steer, 10, dt);
      this.rig.wheels[1].pivot.rotation.y = this.rig.wheels[0].pivot.rotation.y;
    }
    this.tick(dt);
  }

  setBrakeLights(on: boolean) {
    this.rig.materials.taillight.emissiveIntensity = (on ? 9 : this.tailBase) * (this.spec.tailLampGain ?? 1);
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
