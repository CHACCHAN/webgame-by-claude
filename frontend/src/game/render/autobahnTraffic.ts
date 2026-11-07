import * as THREE from 'three';
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js';
import type { Track } from '../track/Track';
import { clamp, rng, smoothstep } from '../util/math';

/**
 * The autobahn's background traffic (no physics, nobody to hit): oncoming cars and lorries on the opposite
 * carriageway, and tail lights far ahead in our direction that keep their distance (they fade out before the
 * player catches up with them). Each vehicle is a few light sprites in one Points draw plus a dark body in one
 * instanced mesh per kind, all moved on the CPU every frame (~100 vehicles).
 */

/** light sprites per vehicle (a car uses four) */
const LIGHTS = 10;

interface Vehicle {
  s: number;
  /** +1 our direction, −1 oncoming */
  dir: 1 | -1;
  lat: number;
  speed: number;
  truck: boolean;
}

interface LightDef {
  /** metres ahead of the vehicle's centre (its own forward), to its right, up */
  f: number;
  r: number;
  h: number;
  color: THREE.Color;
  size: number;
  /** +1 shines forward, −1 backward, 0 all round */
  facing: number;
}

const HEAD = new THREE.Color(1.0, 0.9, 0.74).multiplyScalar(3.2);
const XENON = new THREE.Color(0.86, 0.92, 1.0).multiplyScalar(3.4);
const TAIL = new THREE.Color(1.0, 0.06, 0.03).multiplyScalar(1.7);
const AMBER = new THREE.Color(1.0, 0.45, 0.08).multiplyScalar(1.2);

function carLights(xenon: boolean): LightDef[] {
  const head = xenon ? XENON : HEAD;
  return [
    { f: 2.32, r: 0.68, h: 0.66, color: head, size: 0.55, facing: 1 },
    { f: 2.32, r: -0.68, h: 0.66, color: head, size: 0.55, facing: 1 },
    { f: -2.32, r: 0.66, h: 0.86, color: TAIL, size: 0.4, facing: -1 },
    { f: -2.32, r: -0.66, h: 0.86, color: TAIL, size: 0.4, facing: -1 },
  ];
}

function truckLights(): LightDef[] {
  return [
    { f: 8.4, r: 0.95, h: 0.75, color: HEAD, size: 0.6, facing: 1 },
    { f: 8.4, r: -0.95, h: 0.75, color: HEAD, size: 0.6, facing: 1 },
    { f: -8.3, r: 1.05, h: 0.95, color: TAIL, size: 0.45, facing: -1 },
    { f: -8.3, r: -1.05, h: 0.95, color: TAIL, size: 0.45, facing: -1 },
    // marker lamps along the trailer and the cab roof
    { f: -4.5, r: 1.34, h: 0.62, color: AMBER, size: 0.22, facing: 0 },
    { f: -4.5, r: -1.34, h: 0.62, color: AMBER, size: 0.22, facing: 0 },
    { f: 1.5, r: 1.34, h: 0.62, color: AMBER, size: 0.22, facing: 0 },
    { f: 1.5, r: -1.34, h: 0.62, color: AMBER, size: 0.22, facing: 0 },
    { f: 7.4, r: 1.0, h: 3.85, color: AMBER, size: 0.25, facing: 1 },
    { f: 7.4, r: -1.0, h: 3.85, color: AMBER, size: 0.25, facing: 1 },
  ];
}

function bodyGeometry(truck: boolean) {
  if (truck) {
    // cab and box trailer, 16.6 m
    return mergeGeometries([
      new THREE.BoxGeometry(2.5, 2.9, 2.3).translate(0, 1.9, 7.1),
      new THREE.BoxGeometry(2.55, 3.4, 13.4).translate(0, 2.35, -1.4),
      new THREE.BoxGeometry(2.3, 0.7, 16.2).translate(0, 0.55, 0),
    ]);
  }
  return mergeGeometries([new THREE.BoxGeometry(1.8, 0.7, 4.5).translate(0, 0.62, 0), new THREE.BoxGeometry(1.5, 0.5, 2.3).translate(0, 1.2, -0.3)]);
}

export class AutobahnTraffic {
  readonly group = new THREE.Group();
  private readonly vehicles: Vehicle[] = [];
  private readonly lights: LightDef[][] = [];
  private readonly points: THREE.Points;
  private readonly bodies: { car: THREE.InstancedMesh; truck: THREE.InstancedMesh };
  private readonly pos: Float32Array;
  private readonly facing: Float32Array;
  private readonly gain: Float32Array;
  private readonly r = rng(4711);
  // (the lamps sit just outside the bodies: inside a box the body hides them)
  private hint = -1;
  private last = -1;

  /**
   * `oncomingLanes` / `ourLanes`: lane centres (lateral offsets, + = right of the centreline) of the opposite
   * carriageway and of ours (left to right: the fast lane first).
   */
  constructor(
    private readonly track: Track,
    private readonly oncomingLanes: number[],
    private readonly ourLanes: number[],
    counts = { oncoming: 64, ahead: 22 },
  ) {
    this.group.name = 'traffic';
    for (let k = 0; k < counts.oncoming + counts.ahead; k++) {
      const dir: 1 | -1 = k < counts.oncoming ? -1 : 1;
      const v: Vehicle = { s: 0, dir, lat: 0, speed: 0, truck: false };
      this.respawn(v, dir < 0 ? -400 + this.r() * 3600 : 400 + this.r() * 3000, true);
      this.vehicles.push(v);
      this.lights.push(v.truck ? truckLights() : carLights(this.r() < 0.4));
    }
    const n = this.vehicles.length * LIGHTS;
    this.pos = new Float32Array(n * 3);
    this.facing = new Float32Array(n * 3);
    this.gain = new Float32Array(n);
    const color = new Float32Array(n * 3), size = new Float32Array(n);
    this.lights.forEach((list, v) =>
      list.forEach((l, k) => {
        const o = v * LIGHTS + k;
        color.set([l.color.r, l.color.g, l.color.b], o * 3);
        size[o] = l.size;
      }),
    );
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(this.pos, 3).setUsage(THREE.DynamicDrawUsage));
    geo.setAttribute('facing', new THREE.BufferAttribute(this.facing, 3).setUsage(THREE.DynamicDrawUsage));
    geo.setAttribute('gain', new THREE.BufferAttribute(this.gain, 1).setUsage(THREE.DynamicDrawUsage));
    geo.setAttribute('color', new THREE.BufferAttribute(color, 3));
    geo.setAttribute('size', new THREE.BufferAttribute(size, 1));
    const mat = new THREE.ShaderMaterial({
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
      fog: true,
      uniforms: THREE.UniformsUtils.merge([THREE.UniformsLib.fog, { uIntensity: { value: 1 } }]),
      vertexShader: /* glsl */ `
        attribute vec3 color; attribute vec3 facing; attribute float size; attribute float gain;
        uniform float fogDensity, uIntensity;
        varying vec3 vColor;
        void main() {
          vec4 mv = modelViewMatrix * vec4(position, 1.0);
          float dist = -mv.z;
          vec3 toCam = normalize(cameraPosition - position);
          // a lamp shines towards where it faces; marker lamps (no facing) all round
          float face = dot(facing, facing) > 0.5 ? smoothstep(-0.05, 0.4, dot(facing, toCam)) : 1.0;
          float fog = exp(-fogDensity * fogDensity * dist * dist);
          float k = face * fog * gain;
          float px = size * 900.0 / max(dist, 0.5);
          // far away a lamp stays a 1.6 px dot and dims instead of shrinking away
          float dim = clamp(px / 1.6, 0.0, 1.0);
          gl_PointSize = clamp(px, 1.6, 44.0);
          vColor = color * k * dim * uIntensity;
          gl_Position = (k < 0.004 || dist < 0.5) ? vec4(2.0, 2.0, 2.0, 1.0) : projectionMatrix * mv;
        }`,
      fragmentShader: /* glsl */ `
        varying vec3 vColor;
        void main() {
          vec2 d = gl_PointCoord - 0.5;
          float r2 = dot(d, d) * 4.0;
          float a = exp(-r2 * 7.0) + 0.35 * exp(-r2 * 2.2);
          gl_FragColor = vec4(vColor * a, 1.0);
          #include <colorspace_fragment>
        }`,
    });
    this.points = new THREE.Points(geo, mat);
    this.points.frustumCulled = false;
    this.points.name = 'traffic-lights';
    const bodyMat = new THREE.MeshStandardMaterial({ color: '#16181b', roughness: 0.45, metalness: 0.4 });
    const nCar = this.vehicles.filter((v) => !v.truck).length;
    this.bodies = {
      car: new THREE.InstancedMesh(bodyGeometry(false), bodyMat, Math.max(1, nCar)),
      truck: new THREE.InstancedMesh(bodyGeometry(true), bodyMat, Math.max(1, this.vehicles.length - nCar)),
    };
    for (const b of Object.values(this.bodies)) {
      b.frustumCulled = false;
      b.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
      b.name = 'traffic-bodies';
      this.group.add(b);
    }
    this.group.add(this.points);
  }

  /** a vehicle's lane, speed and kind; at `s` relative to the camera's track distance `base` */
  private respawn(v: Vehicle, s: number, first = false) {
    const r = this.r;
    if (v.dir < 0) {
      // the opposite carriageway: fast lane next to the median, lorries keep right
      if (first) v.truck = r() < 0.25;
      const lane = v.truck ? this.oncomingLanes.length - 1 : Math.min(this.oncomingLanes.length - 1, Math.floor(r() * r() * 3));
      v.lat = this.oncomingLanes[lane];
      v.speed = v.truck ? 22 + r() * 2.5 : [41, 34, 28][lane] + r() * 8;
    } else {
      if (first) v.truck = r() < 0.2;
      const lane = v.truck ? this.ourLanes.length - 1 : Math.floor(r() * this.ourLanes.length);
      v.lat = this.ourLanes[lane];
      v.speed = v.truck ? 22 + r() * 2 : [40, 33, 27][lane] + r() * 7;
    }
    v.s = s;
  }

  update(time: number, camera: THREE.Vector3) {
    const dt = this.last < 0 ? 0 : clamp(time - this.last, 0, 0.1);
    this.last = time;
    const track = this.track;
    const pr = track.project(camera.x, camera.y, camera.z, this.hint);
    this.hint = pr.index;
    const cs = pr.s, end = track.count - 1;
    const p = new THREE.Vector3(), f = new THREE.Vector3(), rt = new THREE.Vector3(), up = new THREE.Vector3(0, 1, 0);
    const m = new THREE.Matrix4(), q = new THREE.Quaternion(), one = new THREE.Vector3(1, 1, 1), zero = new THREE.Vector3();
    let iCar = 0, iTruck = 0;
    this.vehicles.forEach((v, n) => {
      v.s += v.dir * v.speed * dt;
      const d = v.s - cs;
      if (v.dir < 0) {
        // oncoming: recycled behind the camera, far ahead again
        if (d < -450) this.respawn(v, cs + 2600 + this.r() * 700);
        else if (d > 3600) this.respawn(v, cs - 300 + this.r() * 3500);
      } else if (d < 380 || d > 3600) this.respawn(v, cs + 1800 + this.r() * 1600);
      const dd = v.s - cs;
      // ahead in our direction: faded in far off, faded out before the player is close
      let g = v.dir > 0 ? smoothstep(380, 620, dd) * smoothstep(3500, 3100, dd) : 1;
      if (v.s < 2 || v.s > end - 2) g = 0;
      const s = clamp(v.s, 0, end);
      track.pointAt(s, v.lat, p);
      const i = Math.min(end - 1, Math.floor(s));
      f.set(track.fwd[i * 3], 0, track.fwd[i * 3 + 2]).normalize().multiplyScalar(v.dir);
      rt.set(-f.z, 0, f.x);
      const lights = this.lights[n];
      for (let k = 0; k < LIGHTS; k++) {
        const o = (n * LIGHTS + k) * 3;
        const l = lights[k];
        if (!l) {
          this.gain[n * LIGHTS + k] = 0;
          continue;
        }
        this.pos[o] = p.x + f.x * l.f + rt.x * l.r;
        this.pos[o + 1] = p.y + l.h;
        this.pos[o + 2] = p.z + f.z * l.f + rt.z * l.r;
        this.facing[o] = f.x * l.facing;
        this.facing[o + 1] = 0;
        this.facing[o + 2] = f.z * l.facing;
        this.gain[n * LIGHTS + k] = g;
      }
      q.setFromAxisAngle(up, Math.atan2(f.x, f.z));
      m.compose(p, q, g > 0.05 ? one : zero);
      if (v.truck) this.bodies.truck.setMatrixAt(iTruck++, m);
      else this.bodies.car.setMatrixAt(iCar++, m);
    });
    const geo = this.points.geometry;
    for (const name of ['position', 'facing', 'gain']) geo.getAttribute(name).needsUpdate = true;
    this.bodies.car.instanceMatrix.needsUpdate = true;
    this.bodies.truck.instanceMatrix.needsUpdate = true;
  }
}
