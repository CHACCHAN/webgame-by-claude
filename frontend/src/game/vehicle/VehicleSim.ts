import { Quaternion, Vector3 } from 'three';
import { clamp, damp, lerp, smoothstep } from '../util/math';
import { type CarSpec, torqueAt } from './carSpecs';
import { TRACTION_RISE } from './vvvf';
import { bikeLimits } from './bikes';
import { EDWARDS_AIR, jetThrust } from './jets';
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
  /** tyre radius (m): a jet's nose wheel is smaller than its main wheels */
  radius: number;
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
  /** rolling resistance of the ground as a multiple of the tyres' own (loose dirt, a dry lake's clay) */
  rollScale = 1;
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
  /** a bike at its wheelie / stoppie limit (0…1, for the model's pitch) */
  wheelie = 0;
  stoppie = 0;
  /** forward acceleration (m/s², smoothed): a bike's load transfer */
  private longAcc = 0;
  private lastFwd = 0;
  /** a jet's engines: spool (0 = idle, 1 = military power), afterburner (0…1), thrust of all engines (N) */
  spool = 0;
  afterburner = 0;
  thrust = 0;
  /** a jet's lift as a share of its weight (0…0.97) */
  liftShare = 0;
  /** a CVT's (the 10式's HMT) current overall ratio */
  private cvtRatio = 0;

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
    const clearance = spec.clearance ?? 0.16;
    const loadedLen = spec.suspension.rest - (spec.mass * 9.81) / 4 / spec.suspension.stiffness;
    // body origin height above the ground at rest
    this.rideHeight = clearance + this.halfHeight;
    // a jet's nose wheel carries far less than its mains (and is smaller): each axle set at its own static load, so it
    // stands level (the cars keep the equal split their tuning was done on)
    const axleLen = (front: boolean) => {
      if (!spec.jet) return loadedLen;
      const share = front ? 0.5 + spec.comForward / spec.wheelbase : 0.5 - spec.comForward / spec.wheelbase;
      return spec.suspension.rest - (spec.mass * 9.81 * share) / 2 / spec.suspension.stiffness;
    };

    const q = new Quaternion().setFromAxisAngle(UP, heading);
    this.body = physics.world.createRigidBody(
      RAPIER.RigidBodyDesc.dynamic()
        .setTranslation(position.x, position.y + this.rideHeight + 0.05, position.z)
        .setRotation({ x: q.x, y: q.y, z: q.z, w: q.w })
        .setCcdEnabled(true)
        .setLinearDamping(spec.damping ?? 0.02)
        // (a fighter turns on a nose wheel that carries an eighth of its weight: the damping that steadies a car
        // took half of that wheel's turning moment; the air's own yaw damping is in `jetAero`)
        .setAngularDamping(spec.jet ? 0.12 : 0.6)
        .setCanSleep(false),
    );
    const m = spec.mass;
    // a bike's light, narrow box rolled and pitched over at the first kick from the road (200 km/h through a
    // crest): it sits on four times the pitch and roll inertia (the yaw, its quick turning, unchanged)
    const steady = spec.bike ? 4 : 1;
    // a fighter's mass sits around its middle (engines, fuel, wing box), not along its 19 m: about 0.42 of the
    // slab's pitch and yaw inertia (the Eagle's are ≈ 224,000 and 255,000 kg·m²: from memory, an estimate)
    const slender = spec.jet ? 0.42 : 1;
    const inertia = {
      x: (m / 12) * (height * height + length * length) * 0.9 * steady * slender,
      y: (m / 12) * (width * width + length * length) * 0.95 * slender,
      z: (m / 12) * (width * width + height * height) * 1.2 * steady,
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
        const x = (left ? 1 : -1) * ((front ? (spec.frontTrack ?? spec.track) : spec.track) / 2);
        const radius = front ? (spec.frontWheelRadius ?? spec.wheelRadius) : spec.wheelRadius;
        this.wheels.push({
          mount: new Vector3(x, radius + axleLen(front) - this.rideHeight, z),
          radius,
          front,
          left,
          // a jet's wheels roll free: its engines push
          driven: !spec.jet && (spec.drive === 'AWD' || !front),
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

  /**
   * Carried along a path by the game from here on (a fighter leaving the ground after the finish, `race/Departure.ts`):
   * no forces, no contacts, nothing from the wheels; the body is moved to each pose in the next physics step, so
   * whatever reads this simulation (the model, the camera, the peers' packets) sees the flight as it saw the drive.
   */
  carry(position: Vector3, quaternion: Quaternion, engines: { spool: number; afterburner: number }) {
    if (!this.carried) {
      this.carried = true;
      this.body.setBodyType(RAPIER.RigidBodyType.KinematicPositionBased, true);
      this.collider.setEnabled(false);
      for (const w of this.wheels) {
        w.grounded = false;
        w.skid = w.load = w.steer = 0;
      }
    }
    this.body.setNextKinematicTranslation(position);
    this.body.setNextKinematicRotation(quaternion);
    this.spool = engines.spool;
    this.afterburner = engines.afterburner;
  }
  carried = false;

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
    this.spool = this.afterburner = this.thrust = 0;
    for (const w of this.wheels) {
      w.compression = 0;
      w.angularVelocity = speed / w.radius;
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
    // electric traction reverses the motors: same ratio both ways (a tank: its own reverse gearing)
    if (g === -1) return this.spec.reverseRatio ? -this.spec.reverseRatio : this.spec.engine.electric ? -this.spec.gears[0] : -3.4;
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
    if (this.carried) {
      // in the air: only what the gauges, the sound and the camera read
      this.speed = this.forwardSpeed = this.velocity.length();
      this.slipAngle = this.yawRate = this.driftAmount = this.liftShare = 0;
      this.airborne = true;
      this.rpm = (65 + 35 * this.spool + 2 * this.afterburner) * 100;
      if (spec.jet) this.thrust = jetThrust(spec.jet.engines, this.spool, this.afterburner, this.speed / EDWARDS_AIR.sound);
      for (const w of this.wheels) w.angularVelocity *= Math.exp(-dt * 0.8), (w.rotation += w.angularVelocity * dt);
      return;
    }

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
    // a tank's or a jet's handbrake key is just the brakes, full on (no locked rear wheels to slide on)
    const heavy = !!(spec.tank || spec.jet);
    if (heavy && inp.handbrake) brake = 1;

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
    let ratio = this.gearRatio() * spec.finalDrive;
    let drivenRot = 0, drivenCount = 0;
    for (const w of this.wheels) {
      if (!w.driven) continue;
      drivenRot += w.angularVelocity;
      drivenCount++;
    }
    drivenRot /= Math.max(1, drivenCount);
    const cvt = spec.tank?.cvt;
    if (cvt && this.gear !== 0) {
      // the HMT holds the engine at the speed the throttle asks for (its rated speed flat out) and varies the ratio
      // between its lowest and highest, the same both ways
      const want = spec.engine.idleRpm + throttle * (spec.engine.redline - spec.engine.idleRpm);
      this.cvtRatio = clamp((want * Math.PI) / 30 / Math.max(Math.abs(drivenRot), 1e-3), cvt.high, cvt.low);
      ratio = this.cvtRatio * Math.sign(this.gear);
    }
    const wheelRpm = (Math.abs(drivenRot) * Math.abs(ratio) * 60) / (Math.PI * 2);
    // a clutch slips at launch (revs up); an electric motor gives full torque from standstill
    // (a bike's clutch is slipped higher, to the middle of its rev range; a tank's torque converter stalls at ~3/4 of
    // its governed speed)
    const launchRpm = spec.bike ? spec.engine.redline * 0.55 - spec.engine.idleRpm : spec.tank ? spec.engine.redline * 0.75 - spec.engine.idleRpm : 3800;
    const launch = spec.engine.electric ? 0 : spec.engine.idleRpm + throttle * launchRpm * (1 - smoothstep(4, 14, Math.abs(fwdSpeed)));
    let targetRpm = Math.max(wheelRpm * (1 + this.wheelSpin * 0.6), launch, spec.engine.idleRpm);
    const freeRevving = this.gear === 0 || !!inp.hold;
    if (freeRevving) targetRpm = spec.engine.idleRpm + throttle * (spec.engine.redline - spec.engine.idleRpm);
    this.rpm = damp(this.rpm, Math.min(targetRpm, spec.engine.redline + 250), 18, dt);
    // (a CVT holds the engine at the speed it asks for: no limiter)
    if (cvt && this.gear !== 0) this.rpm = damp(this.rpm, Math.max(spec.engine.idleRpm, (Math.abs(drivenRot) * this.cvtRatio * 30) / Math.PI), 18, dt);
    else if (this.rpm > spec.engine.redline) this.limiterCut = 0.08;
    if (this.limiterCut > 0) {
      this.limiterCut -= dt;
      throttle = 0;
    }
    // (the boost builds from 2,800 rpm, a slow diesel's from under half its governed speed)
    const wantBoost = spec.engine.turbo && throttle > 0.5 && this.rpm > Math.min(2800, spec.engine.redline * 0.45) ? 1 : 0;
    this.boost = damp(this.boost, wantBoost, wantBoost ? 2.2 : 5, dt);
    // a CVT at its highest ratio: the governor holds the rated speed
    if (cvt && this.rpm > spec.engine.redline) throttle *= clamp(1 - (this.rpm - spec.engine.redline) / 40, 0, 1);
    let engineTorque = torqueAt(spec, this.rpm) * throttle * this.powerScale;
    if (spec.engine.turbo) engineTorque *= 0.72 + 0.28 * this.boost;
    // engine braking
    engineTorque -= (1 - throttle) * (this.rpm / spec.engine.redline) * 38 * smoothstep(1, 5, Math.abs(fwdSpeed));
    // (a tank loses far more on the way to the ground than a car: torque converter, steering unit, tracks)
    let driveForceTotal = freeRevving || spec.jet ? 0 : (engineTorque * ratio * (spec.tank?.running === 'tracks' ? 0.62 : 0.86)) / spec.wheelRadius;
    // a tank's driver (and the 10式's HMT) feeds no more than its tracks or tyres hold: they never spin up like a car's
    if (spec.tank) driveForceTotal = clamp(driveForceTotal, -spec.gripRear * this.gripScale * spec.mass * 9.81 * 0.98, spec.gripRear * this.gripScale * spec.mass * 9.81 * 0.98);
    if (spec.jet) this.jetEngines(dt, throttle, !!inp.hold);
    if (spec.bike) {
      // a bike's front lifts once the drive passes its weight × (centre of mass ahead of the rear axle) / its height:
      // the drive is held at that limit (anti-wheelie) and the model shows the front going light; the brakes stop
      // short of the stoppie limit (CarSpec.brakeForce)
      const lim = bikeLimits(spec);
      const cap = spec.mass * lim.wheelie;
      const near = driveForceTotal > 0 && fwdSpeed > 0.5 && this.gear > 0 ? driveForceTotal / cap : 0;
      this.wheelie = damp(this.wheelie, smoothstep(0.85, 1.1, near), near > 0.85 ? 4 : 6, dt);
      this.stoppie = damp(this.stoppie, fwdSpeed > 4 && this.gear !== -1 ? smoothstep(0.75, 1, brake) : 0, 5, dt);
      driveForceTotal = Math.min(driveForceTotal, cap * 0.98);
    }

    // ---------------- steering
    const steerTarget = clamp(inp.steer, -1, 1);
    const returning = Math.abs(steerTarget) < Math.abs(this.steerSmoothed);
    const steerRate = returning ? 8 : 5.5;
    const ds = clamp(steerTarget - this.steerSmoothed, -steerRate * dt, steerRate * dt);
    this.steerSmoothed += ds;
    const speedFactor = lerp(1, 0.32, smoothstep(6, 46, planarSpeed));
    let maxSteer = ((spec.maxSteerDeg * Math.PI) / 180) * speedFactor;
    // a rider leans only as far as the tyres hold: the bars turn at most to the angle whose corner takes all the grip
    // (plus the front tyre's slip at its peak), so a full stab of the key at speed is a limit corner, not a spin (a bike's yaw is quick)
    if (spec.bike && planarSpeed > 3) {
      const mu = Math.min(spec.gripFront, spec.gripRear) * this.gripScale;
      maxSteer = Math.min(maxSteer, Math.atan((spec.wheelbase * mu * 9.81 * 1.1) / (planarSpeed * planarSpeed)) + 0.06);
    }
    // A fighter's nose wheel: full lock (45°) only at a walk, the take-off range (15°) from a jog on, and never more
    // than the angle whose turn the tyres can hold with what the wing leaves on them: above that the rudder steers
    // (`jetAero`), the nose wheel only follows.
    if (spec.jet) {
      maxSteer = ((spec.maxSteerDeg * Math.PI) / 180) * lerp(1, 0.33, smoothstep(3, 12, planarSpeed));
      const mu = Math.min(spec.gripFront, spec.gripRear) * this.gripScale * (1 - this.liftShare);
      // (plus the slip the nose tyre needs over the main tyres' to give its best: without it a taxi turn settled
      // at 0.5 g on tyres good for 0.7; less of it the faster, where the rudder does the turning)
      if (planarSpeed > 3) maxSteer = Math.min(maxSteer, Math.atan((spec.wheelbase * mu * 9.81 * 1.1) / (planarSpeed * planarSpeed)) + lerp(0.07, 0.015, smoothstep(20, 60, planarSpeed)));
    }
    // counter-steering during a slide may use the full lock
    // (sliding with the tail out to the left means steering right is counter-steer)
    const isCounter = this.steerSmoothed * this.slipAngle > 0;
    if (drifting > 0 && isCounter) maxSteer = lerp(maxSteer, (spec.maxSteerDeg * Math.PI) / 180, drifting);
    // steer > 0 means right; positive rotation about up turns left
    let steerAngle = -this.steerSmoothed * maxSteer;
    if (this.assist > 0 && drifting > 0 && !heavy) {
      // nudge the front wheels towards the direction of travel (auto counter-steer)
      const k = this.assist === 2 ? 0.75 : 0.4;
      steerAngle += -this.slipAngle * k * drifting * (fwdSpeed > 0 ? 1 : 0);
      steerAngle = clamp(steerAngle, -0.75, 0.75);
    }

    // ---------------- wheels
    const world = this.physics.world;
    const restLen = spec.suspension.rest;
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
    // the AI and a bike grip-drive: no drift tricks (on a bike the handbrake is just the rear brake)
    const noTricks = this.gripDriver || !!spec.bike || heavy;
    const trigger = noTricks
      ? Math.abs(this.slipAngle) > 0.3
      : (inp.handbrake && steerAbs > 0.2) || feint || powerTrigger || Math.abs(this.slipAngle) > 0.28;
    if (fast && trigger) this.driftHold = 0.3;
    else this.driftHold = Math.max(0, this.driftHold - dt);
    // the drift lasts while it is driven (throttle) and the tail is out; once the car straightens to ~7° it grips
    // (a bike never enters the drift state: its rear would lose grip to it)
    const sustain = fast && !spec.bike && !heavy && (this.driftHold > 0 || (this.driftState > 0.3 && Math.abs(this.slipAngle) > 0.12 && throttle > 0.2));
    this.driftState = damp(this.driftState, sustain ? 1 : 0, sustain ? 7 : 2.5, dt);
    this.driftAge = this.driftState > 0.3 ? this.driftAge + dt : 0;
    // throttle widens the angle, lifting tightens it
    const character = lerp(0.55, 1, spec.driftiness) * (spec.drive === 'AWD' ? 0.95 : 1);
    let rearGripDrift = 1 - this.driftState * (0.26 + 0.2 * throttle) * character;
    // angle governor: the rear bites back beyond ~32° of slip (full grip by 50°), so a power slide settles at a
    // holdable angle instead of swinging out to 75° and spinning
    if (!this.gripDriver) rearGripDrift = lerp(rearGripDrift, 1.05, smoothstep(0.55, 0.87, Math.abs(this.slipAngle)));
    if (heavy) rearGripDrift = 1;
    // a pull on the handbrake with steering starts the rotation (the rear alone barely turned the car)
    if (inp.handbrake && !this.lastHandbrake && fast && steerAbs > 0.2 && !noTricks) {
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
      const r = w.radius;
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
      // bump stop (as stiff for a 60 t tank or a 25 t jet as for a car)
      if (w.length < 0.04) fz += (0.04 - w.length) * 400000 * (heavy ? spec.mass / 1500 : 1);
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
    // a bike's load moves between its wheels with the real centre of mass (the sim's is kept low, so it never tips):
    // under power the rear tyre carries it all at the wheelie limit, under braking the front at the stoppie limit
    // A nose wheel turned further than its tyre's best slip angle only scrubs (it carries an eighth of the weight:
    // past the peak the aircraft ploughs straight on with the wheel across). The steering stops there, whatever
    // the stick asks: where the nose wheel is heading (its slip and angle of the last step) ± the peak.
    if (spec.jet && planarSpeed > 3) {
      const nose = this.wheels.find((w) => w.front && w.grounded);
      if (nose) {
        const course = nose.slipAngle - nose.steer;
        steerAngle = clamp(steerAngle, -course - 0.15, -course + 0.15);
      }
    }

    this.longAcc = damp(this.longAcc, (fwdSpeed - this.lastFwd) / dt, 12, dt);
    this.lastFwd = fwdSpeed;
    // (each tyre keeps a quarter of its static load: with none the rear lost all side grip under braking and the bike
    // spun round at every corner entry, the front all steering under power)
    const pitchShift = spec.bike ? (spec.mass * this.longAcc * spec.bike.com.height) / spec.wheelbase / 2 : 0;
    const bikeG = spec.bike ? spec.mass * 9.81 : 0;
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
      const load = pitchShift ? Math.max(w.load * 0.25, w.load + (w.front ? -pitchShift : pitchShift)) : w.load;

      // --- lateral (a bike corners on its lean, by the static load: the pitch shift only moves the drive and brake
      // limits; with it the rear's side grip vanished under braking and every corner entry spun the bike round)
      const sideLoad = spec.bike ? w.load : load;
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
      let fy = -Math.sign(alpha) * mu * sideLoad * curve;
      // never push harder than needed to cancel the lateral velocity (stability at low speed)
      const stopLat = (Math.abs(vL) * wheelMass) / dt;
      if (Math.abs(fy) > stopLat) fy = Math.sign(fy) * stopLat;

      // --- longitudinal
      let fx = 0;
      if (w.driven && this.gear !== 0) {
        const share = spec.drive === 'AWD' ? (w.front ? spec.frontTorqueSplit : 1 - spec.frontTorqueSplit) / 2 : 0.5;
        // (a bike's slipper clutch: engine braking never more than a third of what the rear tyre holds)
        fx += bikeG && driveForceTotal < 0 ? Math.max(driveForceTotal * share, -mu * load * 0.3) : driveForceTotal * share;
      }
      // a rider brakes each wheel by what it carries (hard on the front as the load comes onto it), a car 60:40, a jet
      // only its main wheels, a tank both tracks alike
      const brakeShare = bikeG ? (load / bikeG) * 2 : spec.jet ? (w.front ? 0 : 1) : spec.tank ? 0.5 : w.front ? 0.6 : 0.4;
      let brakeF = brake * spec.brakeForce * brakeShare * 0.5;
      // a bike's handbrake key is its rear brake, worked to the tyre's limit without locking it
      if (bikeG && handbrake && !w.front) brakeF = Math.max(brakeF, mu * load * 0.9);
      const stopLong = (Math.abs(vF) * wheelMass) / dt;
      fx -= Math.sign(vF) * Math.min(brakeF, stopLong);
      // rolling resistance (roughly constant, ~1.5% of load for tyres)
      fx -= Math.sign(vF) * Math.min(Math.abs(vF) * 40, load * (spec.rolling ?? 0.015) * this.rollScale);
      const locked = handbrake && !w.front && !bikeG && !heavy && Math.abs(vF) > 1;

      // --- friction circle (lateral keeps a share of grip even when spinning)
      const maxF = mu * load * 1.05;
      if (bikeG && w.driven && fx > 0 && maxF > 1) {
        // a rider (and the H2's traction control) feeds the throttle to what the rear tyre has left beside the
        // cornering force: a spinning rear on a bike is a crash, not a drift
        const u = clamp(Math.abs(fy) / (mu * sideLoad * 1.05 + 1), 0, 1);
        fx = Math.min(fx, maxF * Math.max(Math.sqrt(1 - u * u), 0.2) * 0.95);
      } else if (gripAssist && w.driven && fx > 0 && maxF > 1) {
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
      const latCap = (spec.bike ? mu * sideLoad * 1.05 : maxF) * Math.sqrt(Math.max(0, 1 - usage * usage * (1 - keep * keep)));
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
      const lockedRear = handbrake && !w.front && !bikeG && !heavy;
      let omega = vF / w.radius;
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
    if (spec.tank?.running === 'tracks' && grounded >= 2) this.skidSteer(dt, fwdSpeed);
    if (spec.jet) this.jetAero(dt, brake, fwdSpeed, latSpeed);

    // ---------------- aero
    const v2 = planarSpeed * planarSpeed;
    _imp.copy(lin).normalize().multiplyScalar(-spec.dragCoef * v2 * dt);
    if (planarSpeed > 0.5) body.applyImpulse(_imp, true);
    const dfV = spec.downforceTopSpeed ?? Infinity;
    if (grounded > 0) body.applyImpulse(_imp.copy(this.up).multiplyScalar(-spec.downforce * Math.min(v2, dfV * dfV) * dt), true);

    // ---------------- assists
    if (grounded >= 2 && this.assist > 0 && planarSpeed > 6 && !heavy) {
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

  /**
   * A tracked vehicle steers by the difference between its tracks: the steering asks for a yaw rate (the pivot rate at a
   * standstill; on the move what ~0.85 of the tracks' grip allows), and the tracks give a yaw moment towards it, at most
   * what they hold (μ·W·gauge/2). Reversing turns the hull the way a car's reversing does.
   */
  private skidSteer(dt: number, fwdSpeed: number) {
    const spec = this.spec;
    const t = spec.tank!;
    const v = Math.abs(fwdSpeed);
    const mu = spec.gripRear * this.gripScale;
    const pivot = (t.pivotRate * Math.PI) / 180;
    const wMax = Math.min(Math.max(pivot, v / 9), (mu * 9.81 * 0.85) / Math.max(v, 0.5));
    const dir = fwdSpeed < -0.5 ? -1 : 1;
    const target = -clamp(this.steerSmoothed, -1, 1) * wMax * dir;
    const iy = (spec.mass / 12) * (spec.size.width ** 2 + spec.size.length ** 2);
    const cap = mu * spec.mass * 9.81 * (spec.track / 2);
    const tq = clamp(iy * (target - this.yawRate) * 8, -cap, cap);
    this.body.applyTorqueImpulse(_imp.copy(this.up).multiplyScalar(tq * dt), true);
  }

  /**
   * A jet's engines: the spool follows the throttle with the engines' lag (idle ⇄ military power in `spoolUp` /
   * `spoolDown` s), the afterburner lights above 85 % throttle once at military power. Thrust per engine: the static
   * figure by the spool and the afterburner, less with the thinner air (σ^0.75) and changing with the Mach number as an
   * afterburning low-bypass turbofan's does (estimated lapse). On the grid the chocks hold it (no thrust applied).
   */
  private jetEngines(dt: number, throttle: number, hold: boolean) {
    const e = this.spec.jet!.engines;
    const wantN = Math.min(1, throttle / 0.85);
    const wantAb = throttle > 0.85 && this.spool > 0.95 ? (throttle - 0.85) / 0.15 : 0;
    this.spool += clamp(wantN - this.spool, -dt / e.spoolDown, dt / e.spoolUp);
    this.afterburner += clamp(wantAb - this.afterburner, -dt / 0.3, dt / 1.2);
    // the sound and the gauge: N2 from 65 % at idle to 100 % at military power (a touch more in reheat)
    this.rpm = (65 + 35 * this.spool + 2 * this.afterburner) * 100;
    this.thrust = jetThrust(e, this.spool, this.afterburner, this.speed / EDWARDS_AIR.sound);
    if (!hold) this.body.applyImpulse(_imp.copy(this.forward).multiplyScalar(this.thrust * dt), true);
  }

  /**
   * The air on a jet's airframe at the ground attitude: drag (zero-lift, gear and doors, the transonic rise from Mach
   * 0.85, the speed brake with the brake pedal), lift (held below the weight: it stays on the ground, with less and less
   * on its tyres), side force from the sideslip, and the yaw from the rudder (the steering), the fin's weathervane and
   * its damping.
   */
  private jetAero(dt: number, brake: number, fwdSpeed: number, latSpeed: number) {
    const spec = this.spec;
    const w = spec.jet!.wing;
    const v = this.speed;
    if (v < 0.5) {
      this.liftShare = 0;
      return;
    }
    const rho = EDWARDS_AIR.density;
    const q = 0.5 * rho * v * v;
    const m = v / EDWARDS_AIR.sound;
    const cd = w.cd0 + w.cdGear + 0.035 * smoothstep(0.85, 1.05, m);
    const drag = q * (w.area * cd + w.speedBrake * brake);
    const b = this.body;
    b.applyImpulse(_imp.copy(this.velocity).multiplyScalar((-drag / v) * dt), true);
    const weight = spec.mass * 9.81;
    const lift = Math.min(q * w.area * w.cl0 * Math.max(0, Math.sign(fwdSpeed)), weight * 0.97);
    this.liftShare = lift / weight;
    b.applyImpulse(_imp.copy(this.up).multiplyScalar(lift * dt), true);
    const beta = Math.atan2(latSpeed, Math.max(Math.abs(fwdSpeed), 1));
    b.applyImpulse(_imp.copy(this.right).multiplyScalar(-q * w.area * 0.6 * beta * dt), true);
    if (fwdSpeed > 5) {
      const qsb = q * w.area * w.span;
      const yaw = -qsb * 0.025 * this.steerSmoothed - qsb * 0.1 * beta - ((qsb * w.span) / (2 * v)) * 0.3 * this.yawRate;
      b.applyTorqueImpulse(_imp.copy(this.up).multiplyScalar(yaw * dt), true);
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
    if (this.carried) {
      this.syncState();
      this.impact = 0;
      this.lastVel.copy(this.velocity);
      return;
    }
    this.softenWallHit(dt);
    this.syncState();
    const dv = _v.copy(this.velocity).sub(this.lastVel).length() / dt;
    // anything well above braking/cornering accelerations is an impact: 3 g, or a quarter past what the tyres can give
    // (the cockroach corners and brakes beyond 3 g: on its own grip that would thud and shake all the time)
    const spec = this.spec;
    const v2 = Math.min(this.velocity.lengthSq(), (spec.downforceTopSpeed ?? Infinity) ** 2);
    const tyres = Math.max(spec.gripFront, spec.gripRear) * this.gripScale * (9.81 + (spec.downforce * v2) / spec.mass);
    const hard = Math.max(30, tyres * 1.25);
    this.impact = dv > hard ? Math.min(1, (dv - hard) / 120) : 0;
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
