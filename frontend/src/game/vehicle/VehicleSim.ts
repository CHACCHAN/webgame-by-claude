import { Quaternion, Vector3 } from 'three';
import { clamp, damp, lerp, smoothstep } from '../util/math';
import { type CarSpec, torqueAt } from './carSpecs';
import { TRACTION_RISE } from './vvvf';
import { GROUP_CAR, GROUP_GROUND, GROUP_PROXY, GROUP_WALL, PhysicsWorld, RAPIER, groups } from './PhysicsWorld';

export interface VehicleInput {
  throttle: number;
  brake: number;
  /** -1 = full left, +1 = full right */
  steer: number;
  handbrake: boolean;
  shiftUp?: boolean;
  shiftDown?: boolean;
  /** held on the line (countdown): brakes on, the engine revs freely, never into reverse */
  hold?: boolean;
}

export const emptyInput = (): VehicleInput => ({ throttle: 0, brake: 0, steer: 0, handbrake: false });

export interface WheelState {
  /** mount point in body space */
  mount: Vector3;
  front: boolean;
  left: boolean;
  driven: boolean;
  grounded: boolean;
  compression: number;
  /** current suspension length (mount → wheel center) */
  length: number;
  load: number;
  steer: number;
  /** accumulated spin angle (rad) for rendering */
  rotation: number;
  angularVelocity: number;
  slipAngle: number;
  /** 0..1 how hard this tyre is sliding (smoke, marks, squeal) */
  skid: number;
  contactPoint: Vector3;
  contactNormal: Vector3;
}

export type AssistLevel = 0 | 1 | 2;

const UP = new Vector3(0, 1, 0);
const _v = new Vector3(), _f = new Vector3(), _lat = new Vector3(), _r = new Vector3(), _w = new Vector3();
const _imp = new Vector3(), _p = new Vector3(), _n = new Vector3(), _away = new Vector3();
const _q = new Quaternion(), _qs = new Quaternion();

/**
 * Raycast vehicle on top of a Rapier rigid body with a custom, arcade-leaning
 * tyre model: friction-circle combined slip, power oversteer for RWD cars,
 * and drift assists that keep slides long, fast and catchable.
 */
export class VehicleSim {
  readonly spec: CarSpec;
  readonly body: RAPIER.RigidBody;
  readonly collider: RAPIER.Collider;
  readonly wheels: WheelState[] = [];
  private readonly physics: PhysicsWorld;
  private readonly ray = new RAPIER.Ray({ x: 0, y: 0, z: 0 }, { x: 0, y: -1, z: 0 });

  input: VehicleInput = emptyInput();
  assist: AssistLevel = 1;
  /** AI rivals get a slight grip handicap/bonus via this multiplier */
  gripScale = 1;
  powerScale = 1;
  autoShift = true;
  /** AI drivers grip-drive: feint/power drift triggers are disabled */
  gripDriver = false;

  // drivetrain state
  rpm = 900;
  gear = 1;
  private shiftTimer = 0;
  private shiftCooldown = 0;
  private reverseTimer = 0;
  boost = 0;
  private wheelSpin = 0;
  private steerSmoothed = 0;
  private limiterCut = 0;
  /** 0..1 drift state: while set, the rear tyres let go so slides are easy to start and hold */
  driftState = 0;
  private driftHold = 0;
  /** time since the current drift began (entry: lighter yaw damping) */
  private driftAge = 0;
  private lastHandbrake = false;
  /** trains: the share of the notch's tractive effort in use (0…1, follows the notch at a limited rate, TRACTION_RISE) */
  traction = 0;
  /** time since the throttle was last below half (a stab — lift, then floor it — starts a power-over) */
  private sinceLift = 9;
  /** how long the brake pedal has been held firmly (a short tap with a big steer is a feint) */
  private brakeTime = 0;
  /** touching a wall (and a moment after): bounce taken back, yaw rate capped */
  private wallTimer = 0;

  // derived state (read by HUD/audio/fx/camera)
  speed = 0;
  forwardSpeed = 0;
  slipAngle = 0;
  yawRate = 0;
  driftAmount = 0;
  airborne = false;
  impact = 0;
  readonly position = new Vector3();
  readonly quaternion = new Quaternion();
  readonly velocity = new Vector3();
  readonly forward = new Vector3();
  readonly up = new Vector3();
  readonly right = new Vector3();
  /** state before the last physics step, for render interpolation */
  readonly prevPosition = new Vector3();
  readonly prevQuaternion = new Quaternion();
  private lastVel = new Vector3();

  readonly rideHeight: number;
  readonly halfHeight: number;

  constructor(physics: PhysicsWorld, spec: CarSpec, position: Vector3, heading: number) {
    this.physics = physics;
    this.spec = spec;
    const { width, height, length } = spec.size;
    this.halfHeight = height / 2;
    const clearance = 0.16;
    const loadedLen = spec.suspension.rest - (spec.mass * 9.81) / 4 / spec.suspension.stiffness;
    // body origin height above the ground at rest
    this.rideHeight = clearance + this.halfHeight;
    const mountY = spec.wheelRadius + loadedLen - this.rideHeight;

    const q = new Quaternion().setFromAxisAngle(UP, heading);
    this.body = physics.world.createRigidBody(
      RAPIER.RigidBodyDesc.dynamic()
        .setTranslation(position.x, position.y + this.rideHeight + 0.05, position.z)
        .setRotation({ x: q.x, y: q.y, z: q.z, w: q.w })
        .setCcdEnabled(true)
        .setLinearDamping(spec.damping ?? 0.02)
        .setAngularDamping(0.6)
        .setCanSleep(false),
    );
    const m = spec.mass;
    const inertia = {
      x: (m / 12) * (height * height + length * length) * 0.9,
      y: (m / 12) * (width * width + length * length) * 0.95,
      z: (m / 12) * (width * width + height * height) * 1.2,
    };
    const comY = spec.comHeight - this.rideHeight;
    this.collider = physics.world.createCollider(
      RAPIER.ColliderDesc.roundCuboid(width / 2 - 0.08, height / 2 - 0.08, length / 2 - 0.08, 0.08)
        .setMassProperties(m, { x: 0, y: comY, z: spec.comForward }, inertia, { x: 0, y: 0, z: 0, w: 1 })
        .setCollisionGroups(groups(GROUP_CAR, GROUP_GROUND | GROUP_WALL | GROUP_CAR | GROUP_PROXY))
        .setFriction(0.15)
        .setRestitution(0.1),
      this.body,
    );

    for (const front of [true, false]) {
      for (const left of [true, false]) {
        const z = front ? spec.wheelbase / 2 : -spec.wheelbase / 2;
        const x = (left ? 1 : -1) * (spec.track / 2);
        this.wheels.push({
          mount: new Vector3(x, mountY, z),
          front,
          left,
          driven: spec.drive === 'AWD' || !front,
          grounded: false,
          compression: 0,
          length: spec.suspension.rest,
          load: 0,
          steer: 0,
          rotation: 0,
          angularVelocity: 0,
          slipAngle: 0,
          skid: 0,
          contactPoint: new Vector3(),
          contactNormal: new Vector3(0, 1, 0),
        });
      }
    }
    this.syncState();
    this.prevPosition.copy(this.position);
    this.prevQuaternion.copy(this.quaternion);
  }

  /** Place the car at rest at a position/heading (respawn, grid). */
  reset(position: Vector3, heading: number, speed = 0) {
    const q = _q.setFromAxisAngle(UP, heading);
    this.body.setTranslation({ x: position.x, y: position.y + this.rideHeight + 0.08, z: position.z }, true);
    this.body.setRotation({ x: q.x, y: q.y, z: q.z, w: q.w }, true);
    const f = _f.set(Math.sin(heading), 0, Math.cos(heading)).multiplyScalar(speed);
    this.body.setLinvel({ x: f.x, y: f.y, z: f.z }, true);
    this.body.setAngvel({ x: 0, y: 0, z: 0 }, true);
    this.gear = 1;
    this.rpm = this.spec.engine.idleRpm;
    this.wheelSpin = 0;
    this.traction = 0;
    for (const w of this.wheels) {
      w.compression = 0;
      w.angularVelocity = speed / this.spec.wheelRadius;
    }
    this.syncState();
    this.prevPosition.copy(this.position);
    this.prevQuaternion.copy(this.quaternion);
    this.lastVel.copy(this.velocity);
  }

  private syncState() {
    const t = this.body.translation();
    const r = this.body.rotation();
    const v = this.body.linvel();
    this.position.set(t.x, t.y, t.z);
    this.quaternion.set(r.x, r.y, r.z, r.w);
    this.velocity.set(v.x, v.y, v.z);
    this.forward.set(0, 0, 1).applyQuaternion(this.quaternion);
    this.up.set(0, 1, 0).applyQuaternion(this.quaternion);
    this.right.set(-1, 0, 0).applyQuaternion(this.quaternion);
  }

  get gearCount() {
    return this.spec.gears.length;
  }

  private gearRatio(g = this.gear) {
    // electric traction reverses the motors: same ratio both ways
    if (g === -1) return this.spec.engine.electric ? -this.spec.gears[0] : -3.4;
    if (g === 0) return 0;
    return this.spec.gears[g - 1];
  }

  /** Apply all vehicle forces for one physics step (call before world.step). */
  preStep(dt: number) {
    const spec = this.spec;
    const body = this.body;
    this.prevPosition.copy(this.position);
    this.prevQuaternion.copy(this.quaternion);
    this.syncState();

    const inp = this.input;
    const fwdSpeed = this.velocity.dot(this.forward);
    const latSpeed = this.velocity.dot(this.right);
    this.forwardSpeed = fwdSpeed;
    this.speed = this.velocity.length();
    const planarSpeed = Math.hypot(fwdSpeed, latSpeed);
    this.slipAngle = planarSpeed > 3 ? Math.atan2(latSpeed, Math.abs(fwdSpeed)) : 0;
    const av = body.angvel();
    this.yawRate = av.x * this.up.x + av.y * this.up.y + av.z * this.up.z;
    const drifting = smoothstep(0.1, 0.35, Math.abs(this.slipAngle)) * smoothstep(6, 12, planarSpeed);
    this.driftAmount = drifting;

    // ---------------- gearbox / reverse logic
    let throttle = clamp(inp.throttle, 0, 1);
    let brake = clamp(inp.brake, 0, 1);
    if (inp.hold) {
      // on the grid: brakes on, clutch out. (Holding the brake used to count as asking for reverse after 0.35 s,
      // and in reverse the brake pedal drives: cars backed away from the line before the start.)
      this.reverseTimer = 0;
      if (this.gear === -1) this.gear = 1;
      brake = 1;
    } else if (this.gear === -1) {
      // in reverse the pedals swap roles
      [throttle, brake] = [brake, throttle];
      if (inp.throttle > 0.1 && fwdSpeed > -1) this.gear = 1;
    } else if (inp.brake > 0.3 && inp.throttle < 0.1 && fwdSpeed < 0.6) {
      this.reverseTimer += dt;
      if (this.reverseTimer > 0.35) {
        this.gear = -1;
        this.reverseTimer = 0;
      }
    } else this.reverseTimer = 0;

    // a train's tractive effort follows the notch at a limited rate (its jerk limit): it builds up over TRACTION_RISE
    // and fades in half that after a notch-off (a quick re-notch keeps most of it); the brake or the grid hold cut it
    if (spec.train) {
      const want = throttle > 0.02 ? throttle : 0;
      if (inp.hold || brake > 0.1) this.traction = 0;
      else if (want >= this.traction) this.traction = Math.min(want, this.traction + dt / TRACTION_RISE);
      else this.traction = Math.max(want, this.traction - (2 * dt) / TRACTION_RISE);
      throttle = this.traction;
    }

    this.shiftCooldown = Math.max(0, this.shiftCooldown - dt);
    if (this.shiftTimer > 0) {
      this.shiftTimer -= dt;
      throttle *= 0.15;
    }
    if (this.gear > 0) {
      if (this.autoShift) {
        const up = this.rpm > spec.engine.redline * 0.95 && this.gear < this.gearCount && this.wheelSpin < 0.4;
        const lowerRpm = this.gear > 1 ? (this.rpm * this.gearRatio(this.gear - 1)) / this.gearRatio() : Infinity;
        const down = this.gear > 1 && this.rpm < spec.engine.redline * 0.5 && lowerRpm < spec.engine.redline * 0.88;
        if (this.shiftCooldown <= 0 && (up || down)) this.shift(up ? 1 : -1);
      } else {
        if (inp.shiftUp && this.gear < this.gearCount && this.shiftCooldown <= 0) this.shift(1);
        if (inp.shiftDown && this.gear > 1 && this.shiftCooldown <= 0) this.shift(-1);
      }
    }

    // ---------------- engine
    const ratio = this.gearRatio() * spec.finalDrive;
    let drivenRot = 0, drivenCount = 0;
    for (const w of this.wheels) {
      if (!w.driven) continue;
      drivenRot += w.angularVelocity;
      drivenCount++;
    }
    drivenRot /= Math.max(1, drivenCount);
    const wheelRpm = (Math.abs(drivenRot) * Math.abs(ratio) * 60) / (Math.PI * 2);
    // a clutch slips at launch (revs up); an electric motor gives full torque from standstill
    const launch = spec.engine.electric ? 0 : spec.engine.idleRpm + throttle * 3800 * (1 - smoothstep(4, 14, Math.abs(fwdSpeed)));
    let targetRpm = Math.max(wheelRpm * (1 + this.wheelSpin * 0.6), launch, spec.engine.idleRpm);
    const freeRevving = this.gear === 0 || !!inp.hold;
    if (freeRevving) targetRpm = spec.engine.idleRpm + throttle * (spec.engine.redline - spec.engine.idleRpm);
    this.rpm = damp(this.rpm, Math.min(targetRpm, spec.engine.redline + 250), 18, dt);
    if (this.rpm > spec.engine.redline) this.limiterCut = 0.08;
    if (this.limiterCut > 0) {
      this.limiterCut -= dt;
      throttle = 0;
    }
    const wantBoost = spec.engine.turbo && throttle > 0.5 && this.rpm > 2800 ? 1 : 0;
    this.boost = damp(this.boost, wantBoost, wantBoost ? 2.2 : 5, dt);
    let engineTorque = torqueAt(spec, this.rpm) * throttle * this.powerScale;
    if (spec.engine.turbo) engineTorque *= 0.72 + 0.28 * this.boost;
    // engine braking
    engineTorque -= (1 - throttle) * (this.rpm / spec.engine.redline) * 38 * smoothstep(1, 5, Math.abs(fwdSpeed));
    const driveForceTotal = freeRevving ? 0 : (engineTorque * ratio * 0.86) / spec.wheelRadius;

    // ---------------- steering
    const steerTarget = clamp(inp.steer, -1, 1);
    const returning = Math.abs(steerTarget) < Math.abs(this.steerSmoothed);
    const steerRate = returning ? 8 : 5.5;
    const ds = clamp(steerTarget - this.steerSmoothed, -steerRate * dt, steerRate * dt);
    this.steerSmoothed += ds;
    const speedFactor = lerp(1, 0.32, smoothstep(6, 46, planarSpeed));
    let maxSteer = ((spec.maxSteerDeg * Math.PI) / 180) * speedFactor;
    // counter-steering during a slide may use the full lock
    // (sliding with the tail out to the left means steering right is counter-steer)
    const isCounter = this.steerSmoothed * this.slipAngle > 0;
    if (drifting > 0 && isCounter) maxSteer = lerp(maxSteer, (spec.maxSteerDeg * Math.PI) / 180, drifting);
    // steer > 0 means right; positive rotation about up turns left
    let steerAngle = -this.steerSmoothed * maxSteer;
    if (this.assist > 0 && drifting > 0) {
      // nudge the front wheels towards the direction of travel (auto counter-steer)
      const k = this.assist === 2 ? 0.75 : 0.4;
      steerAngle += -this.slipAngle * k * drifting * (fwdSpeed > 0 ? 1 : 0);
      steerAngle = clamp(steerAngle, -0.75, 0.75);
    }

    // ---------------- wheels
    const world = this.physics.world;
    const restLen = spec.suspension.rest;
    const r = spec.wheelRadius;
    const com = body.worldCom();
    const lin = this.velocity;
    const angv = _w.set(av.x, av.y, av.z);
    let grounded = 0;
    const wheelMass = spec.mass / 4;
    // ---------------- drift state machine (arcade): handbrake + steer, a "feint" (brake +
    // sharp steer), power + steer, or an existing slide puts the car into a drift
    const steerAbs = Math.abs(this.steerSmoothed);
    const fast = planarSpeed > 8.5 && fwdSpeed > 0;
    // (the driver's pedals: a gear change cuts the engine's throttle for a moment, which is no stab)
    this.sinceLift = inp.throttle < 0.5 ? 0 : this.sinceLift + dt;
    const feint = inp.brake <= 0.5 && this.brakeTime > 0.04 && this.brakeTime < 0.45 && steerAbs > 0.7 && planarSpeed > 15;
    this.brakeTime = inp.brake > 0.5 ? this.brakeTime + dt : 0;
    // Starting a drift takes a deliberate input: a pull on the handbrake, a feint (a short firm tap of the brake,
    // released with a big steer), a stab of the throttle mid-corner (4WD cars too), or a slide already past ~16°.
    // Taking a bend flat out at full lock, or braking into it, stays a grip corner (it used to slide every keyboard
    // corner).
    const powerTrigger = throttle > 0.85 && this.sinceLift < 0.35 && steerAbs > 0.6 && this.gear > 0 && this.gear <= 3 && spec.driftiness > 0.35 && planarSpeed > 11;
    const trigger = this.gripDriver
      ? Math.abs(this.slipAngle) > 0.3
      : (inp.handbrake && steerAbs > 0.2) || feint || powerTrigger || Math.abs(this.slipAngle) > 0.28;
    if (fast && trigger) this.driftHold = 0.3;
    else this.driftHold = Math.max(0, this.driftHold - dt);
    // the drift lasts while it is driven (throttle) and the tail is out; once the car straightens to ~7° it grips
    const sustain = fast && (this.driftHold > 0 || (this.driftState > 0.3 && Math.abs(this.slipAngle) > 0.12 && throttle > 0.2));
    this.driftState = damp(this.driftState, sustain ? 1 : 0, sustain ? 7 : 2.5, dt);
    this.driftAge = this.driftState > 0.3 ? this.driftAge + dt : 0;
    // throttle widens the angle, lifting tightens it
    const character = lerp(0.55, 1, spec.driftiness) * (spec.drive === 'AWD' ? 0.95 : 1);
    let rearGripDrift = 1 - this.driftState * (0.26 + 0.2 * throttle) * character;
    // angle governor: the rear bites back beyond ~32° of slip (full grip by 50°), so a power slide settles at a
    // holdable angle instead of swinging out to 75° and spinning
    if (!this.gripDriver) rearGripDrift = lerp(rearGripDrift, 1.05, smoothstep(0.55, 0.87, Math.abs(this.slipAngle)));
    // a pull on the handbrake with steering starts the rotation (the rear alone barely turned the car)
    if (inp.handbrake && !this.lastHandbrake && fast && steerAbs > 0.2 && !this.gripDriver) {
      const iy = (spec.mass / 12) * (spec.size.width ** 2 + spec.size.length ** 2);
      body.applyTorqueImpulse(_imp.copy(this.up).multiplyScalar(-Math.sign(this.steerSmoothed) * iy * 0.9), true);
    }
    this.lastHandbrake = inp.handbrake;
    // grip assist (players with the assist on, outside a drift): the driven wheels only get the force the friction
    // circle leaves beside the cornering force, so flooring it in a bend no longer spins the rears and swings the
    // tail out. A deliberate drift (handbrake, feint, throttle stab) switches it off.
    const gripAssist = this.assist > 0 && !this.gripDriver && this.driftState < 0.3;
    let spinDemand = 0;

    for (const w of this.wheels) {
      const origin = _p.copy(w.mount).applyQuaternion(this.quaternion).add(this.position);
      const dir = _n.copy(this.up).negate();
      const ray = this.ray;
      ray.origin = { x: origin.x, y: origin.y, z: origin.z };
      ray.dir = { x: dir.x, y: dir.y, z: dir.z };
      const hit = world.castRayAndGetNormal(
        ray,
        restLen + r,
        true,
        undefined,
        groups(GROUP_CAR, GROUP_GROUND),
        undefined,
        body,
      );
      w.steer = w.front ? steerAngle : 0;
      const prevCompression = w.compression;
      if (!hit) {
        w.grounded = false;
        w.compression = 0;
        w.length = restLen;
        w.load = 0;
        w.skid = damp(w.skid, 0, 10, dt);
        // free wheel slowly matches the car speed; driven wheels spin with throttle
        const target = w.driven && throttle > 0.2 && this.gear > 0 ? w.angularVelocity + throttle * 60 * dt : fwdSpeed / r;
        w.angularVelocity = damp(w.angularVelocity, target, 2, dt);
        w.rotation += w.angularVelocity * dt;
        continue;
      }
      grounded++;
      w.grounded = true;
      const toi = hit.timeOfImpact;
      w.length = Math.max(0, toi - r);
      w.compression = restLen - w.length;
      w.contactPoint.copy(dir).multiplyScalar(toi).add(origin);
      w.contactNormal.set(hit.normal.x, hit.normal.y, hit.normal.z);

      // suspension
      const compVel = (w.compression - prevCompression) / dt;
      let fz = spec.suspension.stiffness * w.compression + spec.suspension.damping * compVel;
      fz = Math.max(0, fz);
      // bump stop
      if (w.length < 0.04) fz += (0.04 - w.length) * 400000;
      w.load = Math.min(fz, spec.mass * 9.81 * 1.6);
      _imp.copy(this.up).multiplyScalar(fz * dt);
      body.applyImpulseAtPoint(_imp, origin, true);
    }

    // anti-roll bars
    for (const front of [true, false]) {
      const [a, b] = this.wheels.filter((w) => w.front === front);
      const diff = (a.compression - b.compression) * spec.suspension.antiRoll;
      if (a.grounded) body.applyImpulseAtPoint(_imp.copy(this.up).multiplyScalar(diff * dt), _p.copy(a.mount).applyQuaternion(this.quaternion).add(this.position), true);
      if (b.grounded) body.applyImpulseAtPoint(_imp.copy(this.up).multiplyScalar(-diff * dt), _p.copy(b.mount).applyQuaternion(this.quaternion).add(this.position), true);
    }

    const handbrake = inp.handbrake;
    for (const w of this.wheels) {
      if (!w.grounded) continue;
      const n = w.contactNormal;
      // wheel heading
      _qs.setFromAxisAngle(this.up, w.steer);
      _f.copy(this.forward).applyQuaternion(_qs);
      _f.addScaledVector(n, -_f.dot(n)).normalize();
      _lat.crossVectors(_f, n).normalize(); // points right
      // velocity of the contact patch
      _r.set(w.contactPoint.x - com.x, w.contactPoint.y - com.y, w.contactPoint.z - com.z);
      _v.crossVectors(angv, _r).add(lin);
      const vF = _v.dot(_f);
      const vL = _v.dot(_lat);
      const load = w.load;

      // --- lateral
      let mu = (w.front ? spec.gripFront : spec.gripRear) * this.gripScale;
      if (!w.front) {
        mu *= rearGripDrift;
        // recover grip when the driver straightens up and lifts
        if (this.assist > 0 && drifting > 0 && throttle < 0.2 && steerAbs < 0.25) mu *= 1.1;
      }
      const alpha = Math.atan2(vL, Math.max(Math.abs(vF), 4));
      w.slipAngle = alpha;
      const a = Math.abs(alpha);
      const peak = w.front ? 0.16 : 0.13;
      const slideFrac = w.front ? 0.82 : lerp(0.86, 0.72, spec.driftiness);
      const curve = a < peak ? Math.sin((a / peak) * Math.PI * 0.5) : lerp(1, slideFrac, smoothstep(peak, peak * 4.5, a));
      let fy = -Math.sign(alpha) * mu * load * curve;
      // never push harder than needed to cancel the lateral velocity (stability at low speed)
      const stopLat = (Math.abs(vL) * wheelMass) / dt;
      if (Math.abs(fy) > stopLat) fy = Math.sign(fy) * stopLat;

      // --- longitudinal
      let fx = 0;
      if (w.driven && this.gear !== 0) {
        const share = spec.drive === 'AWD' ? (w.front ? spec.frontTorqueSplit : 1 - spec.frontTorqueSplit) / 2 : 0.5;
        fx += driveForceTotal * share;
      }
      const brakeShare = w.front ? 0.6 : 0.4;
      let brakeF = brake * spec.brakeForce * brakeShare * 0.5;
      const stopLong = (Math.abs(vF) * wheelMass) / dt;
      fx -= Math.sign(vF) * Math.min(brakeF, stopLong);
      // rolling resistance (roughly constant, ~1.5% of load for tyres)
      fx -= Math.sign(vF) * Math.min(Math.abs(vF) * 40, load * (spec.rolling ?? 0.015));
      const locked = handbrake && !w.front && Math.abs(vF) > 1;

      // --- friction circle (lateral keeps a share of grip even when spinning)
      const maxF = mu * load * 1.05;
      if (gripAssist && w.driven && fx > 0 && maxF > 1) {
        // only while cornering hard (a third of the grip and up): straight-line launches and pushes are unchanged
        const u = clamp((Math.abs(fy) / maxF - 0.3) / 0.7, 0, 1);
        fx = Math.min(fx, maxF * Math.max(Math.sqrt(1 - u * u), 0.25));
      }
      let spinning = 0;
      if (Math.abs(fx) > maxF) {
        spinning = (Math.abs(fx) - maxF) / Math.max(maxF, 1);
        fx = Math.sign(fx) * maxF;
      }
      const usage = clamp(Math.abs(fx) / Math.max(maxF, 1), 0, 1);
      const keep = 0.55 + (1 - spec.driftiness) * 0.25;
      const latCap = maxF * Math.sqrt(Math.max(0, 1 - usage * usage * (1 - keep * keep)));
      if (Math.abs(fy) > latCap) fy = Math.sign(fy) * latCap;
      if (locked) {
        // a locked wheel just slides: friction opposes the contact patch velocity
        const vs = Math.hypot(vF, vL) || 1;
        const slide = mu * 0.8 * load;
        fx = (-vF / vs) * slide;
        fy = (-vL / vs) * slide;
      }
      if (w.driven) spinDemand = Math.max(spinDemand, spinning);

      _imp.copy(_f).multiplyScalar(fx).addScaledVector(_lat, fy).multiplyScalar(dt);
      // apply between contact and COM height to tame body roll
      _p.copy(w.contactPoint).lerp(com as unknown as Vector3, 0.35);
      body.applyImpulseAtPoint(_imp, _p, true);

      // wheel rotation (visual + rpm source)
      const lockedRear = handbrake && !w.front;
      let omega = vF / r;
      if (w.driven && this.gear > 0) omega *= 1 + this.wheelSpin;
      if (lockedRear) omega = 0;
      w.angularVelocity = omega;
      w.rotation += omega * dt;
      const latSlide = smoothstep(2.2, 7, Math.abs(vL));
      const spinSlide = w.driven ? smoothstep(0.15, 0.6, this.wheelSpin) : 0;
      const lockSlide = lockedRear && Math.abs(vF) > 3 ? 0.8 : 0;
      w.skid = damp(w.skid, clamp(Math.max(latSlide, spinSlide, lockSlide), 0, 1), 12, dt);
    }
    this.wheelSpin = damp(this.wheelSpin, clamp(spinDemand * 0.8, 0, 1.5), spinDemand > this.wheelSpin ? 8 : 3, dt);
    this.airborne = grounded === 0;

    // ---------------- aero
    const v2 = planarSpeed * planarSpeed;
    _imp.copy(lin).normalize().multiplyScalar(-spec.dragCoef * v2 * dt);
    if (planarSpeed > 0.5) body.applyImpulse(_imp, true);
    if (grounded > 0) body.applyImpulse(_imp.copy(this.up).multiplyScalar(-spec.downforce * v2 * dt), true);

    // ---------------- assists
    if (grounded >= 2 && this.assist > 0 && planarSpeed > 6) {
      const level = this.assist === 2 ? 1.4 : 1;
      // keep momentum through slides: push along the direction of travel
      if (drifting > 0 && throttle > 0.25 && fwdSpeed > 0) {
        const push = throttle * spec.mass * 2.6 * drifting * level;
        _imp.copy(lin).setY(0).normalize().multiplyScalar(push * dt);
        body.applyImpulse(_imp, true);
      }
      // spin-out protection beyond ~45 degrees of slip
      const over = Math.abs(this.slipAngle) - 0.78;
      if (over > 0) {
        const tq = -Math.sign(this.slipAngle) * over * spec.mass * 9 * level;
        body.applyTorqueImpulse(_imp.copy(this.up).multiplyScalar(tq * dt), true);
      }
      // yaw damping while sliding so the car doesn't snap back (lighter for the first half second: it used to
      // kill handbrake and feint entries before they turned the car)
      const yd = -this.yawRate * spec.mass * 0.55 * drifting * level * lerp(0.35, 1, smoothstep(0.2, 0.6, this.driftAge));
      body.applyTorqueImpulse(_imp.copy(this.up).multiplyScalar(yd * dt), true);
    }
    if (grounded === 0) {
      // gentle self-righting in the air
      _imp.crossVectors(this.up, UP).multiplyScalar(spec.mass * 2.5 * dt);
      body.applyTorqueImpulse(_imp, true);
    }
  }

  private shift(dir: 1 | -1) {
    this.gear = clamp(this.gear + dir, 1, this.gearCount);
    this.shiftTimer = dir > 0 ? 0.12 : 0.06;
    this.shiftCooldown = 0.35;
  }

  /**
   * Arcade wall contact. The solver bounced a car off a wall it hit at an angle and spun it round (45° at
   * 100 km/h: ~35 km/h back off the wall, turned 90°, 6 m out into the road). While touching (and a moment after),
   * most of the motion away from the wall is taken back and the yaw rate is capped, so the car glances off and
   * lines up with the wall instead.
   */
  private softenWallHit(dt: number) {
    const world = this.physics.world;
    let touching = false;
    _away.set(0, 0, 0);
    world.contactPairsWith(this.collider, (other) => {
      if (((other.collisionGroups() >>> 16) & GROUP_WALL) === 0) return;
      world.contactPair(this.collider, other, (m, flipped) => {
        if (m.numContacts() === 0) return;
        const n = m.normal();
        // the normal points from the first collider to the second: away from the wall is wall → car
        const k = flipped ? 1 : -1;
        _away.x += n.x * k;
        _away.z += n.z * k;
        touching = true;
      });
    });
    if (touching && _away.lengthSq() > 1e-6) {
      _away.normalize();
      const lv = this.body.linvel();
      const out = lv.x * _away.x + lv.z * _away.z;
      // keep a little separation speed (0.5 m/s) so the car does not stick
      if (out > 0.5) this.body.setLinvel({ x: lv.x - _away.x * (out - 0.5), y: lv.y, z: lv.z - _away.z * (out - 0.5) }, true);
      this.wallTimer = 0.35;
    } else this.wallTimer = Math.max(0, this.wallTimer - dt);
    if (this.wallTimer > 0) {
      const av = this.body.angvel();
      const yaw = av.x * this.up.x + av.y * this.up.y + av.z * this.up.z;
      const cap = 1.6;
      if (Math.abs(yaw) > cap) {
        const cut = yaw - Math.sign(yaw) * cap;
        this.body.setAngvel({ x: av.x - this.up.x * cut, y: av.y - this.up.y * cut, z: av.z - this.up.z * cut }, true);
      }
    }
  }

  /** Post-step bookkeeping (call after world.step). */
  postStep(dt: number) {
    this.softenWallHit(dt);
    this.syncState();
    const dv = _v.copy(this.velocity).sub(this.lastVel).length() / dt;
    // anything well above braking/cornering accelerations is an impact
    this.impact = dv > 30 ? Math.min(1, (dv - 30) / 120) : 0;
    this.lastVel.copy(this.velocity);
  }

  /** Is the car upside down or on its side? */
  get isFlipped() {
    return this.up.y < 0.3;
  }

  dispose() {
    this.physics.world.removeRigidBody(this.body);
  }
}
