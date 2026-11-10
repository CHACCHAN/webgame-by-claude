import * as THREE from 'three';
import { SpriteNodeMaterial } from 'three/webgpu';
import { cameraPosition, cameraProjectionMatrix, cameraViewMatrix, clamp as clampNode, dot, exp, instancedBufferAttribute, instancedDynamicBufferAttribute, max, normalize, saturate as clamp01, select, smoothstep as smoothstepNode, uniform, uv, varying, vec4 } from 'three/tsl';
import type { Float, Vec3, Vec4 } from './tslNoise';
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js';
import type { Track } from '../track/Track';
import { clamp, rng, smoothstep } from '../util/math';
import { CAR_ORDER, CAR_SPECS } from '../vehicle/carSpecs';
import { TRAFFIC_PARTS, trafficModel, type TrafficModel } from './trafficModels';

/**
 * The autobahn's background traffic (no physics, nobody to hit): the game's own cars coming the other way on the
 * opposite carriageway, and tail lights far ahead in our direction that keep their distance (they fade out before
 * the player catches up with them). Each vehicle is a few light sprites in one Points draw; within `modelRange` a
 * car is drawn as a light copy of its model (render/trafficModels.ts: four instanced meshes per car, paint
 * coloured per instance), the lorries ahead as a dark box. All moved on the CPU every frame (~100 vehicles).
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
  /** which car (index into CAR_ORDER) */
  kind: number;
  color: THREE.Color;
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

/** the lamps where the car's model has them (pop-ups: warm halogen) */
function modelLights(model: TrafficModel | undefined, xenon: boolean): LightDef[] {
  if (!model || model.headlights.length < 2 || model.taillights.length < 2) return carLights(xenon);
  const head = xenon && !model.popUps ? XENON : HEAD;
  // just outside the lens: a sprite inside the body would be hidden by it
  return [
    ...model.headlights.slice(0, 2).map((a) => ({ f: a.z + 0.2, r: -a.x, h: a.y, color: head, size: 0.55, facing: 1 })),
    ...model.taillights.slice(0, 2).map((a) => ({ f: a.z - 0.18, r: -a.x, h: a.y, color: TAIL, size: 0.4, facing: -1 })),
  ];
}

/** everyday paint for the traffic (a car also comes in its own colour) */
const PAINTS = ['#e9e9ea', '#121214', '#8a8f96', '#4f545b', '#c9ccd1', '#1f3f7a', '#8f1218', '#2b2d31'];

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

interface CarKind {
  /** one instanced mesh per model part (the paint first, coloured per instance) */
  meshes: THREE.InstancedMesh[];
  paint: THREE.InstancedMesh | null;
  used: number;
}

export class AutobahnTraffic {
  readonly group = new THREE.Group();
  private readonly vehicles: Vehicle[] = [];
  private readonly lights: LightDef[][] = [];
  private readonly points: THREE.Sprite;
  private readonly dynamic: THREE.InstancedBufferAttribute[] = [];
  /** the scene's fog density (read from the scene the group is in) */
  private readonly fogDensity = uniform(0);
  private readonly trucks: THREE.InstancedMesh;
  private readonly kinds: CarKind[] = [];
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
    /** how far ahead a car is drawn as a model (beyond: its lamps only) */
    private readonly modelRange = 1000,
  ) {
    this.group.name = 'traffic';
    const models = CAR_ORDER.map((id) => trafficModel(id));
    for (let k = 0; k < counts.oncoming + counts.ahead; k++) {
      const dir: 1 | -1 = k < counts.oncoming ? -1 : 1;
      const v: Vehicle = { s: 0, dir, lat: 0, speed: 0, truck: false, kind: Math.floor(this.r() * CAR_ORDER.length), color: new THREE.Color() };
      this.respawn(v, dir < 0 ? -400 + this.r() * 3600 : 400 + this.r() * 3000, true);
      this.vehicles.push(v);
      this.lights.push(v.truck ? truckLights() : modelLights(models[v.kind], this.r() < 0.4));
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
    // one camera-facing quad per lamp (instanced: WebGPU has no sized points), sized in pixels of a 1080-line frame
    const dyn = (array: Float32Array, size: number) => {
      const attr = new THREE.InstancedBufferAttribute(array, size).setUsage(THREE.DynamicDrawUsage);
      this.dynamic.push(attr);
      return attr;
    };
    const aPos = instancedDynamicBufferAttribute(dyn(this.pos, 3), 'vec3') as unknown as Vec3;
    const aFacing = instancedDynamicBufferAttribute(dyn(this.facing, 3), 'vec3') as unknown as Vec3;
    const aGain = instancedDynamicBufferAttribute(dyn(this.gain, 1), 'float') as unknown as Float;
    const aColor = instancedBufferAttribute(new THREE.InstancedBufferAttribute(color, 3), 'vec3') as unknown as Vec3;
    const aSize = instancedBufferAttribute(new THREE.InstancedBufferAttribute(size, 1), 'float') as unknown as Float;
    const mat = new SpriteNodeMaterial({ transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, fog: false });
    mat.sizeAttenuation = false;
    const toLamp = aPos.sub(cameraPosition);
    const dist = (cameraViewMatrix.mul(vec4(aPos, 1)) as unknown as Vec4).z.negate();
    // a lamp shines towards where it faces; marker lamps (no facing) all round
    const face = select(dot(aFacing, aFacing).greaterThan(0.5), smoothstepNode(-0.05, 0.4, dot(aFacing, normalize(toLamp).negate())), 1);
    // the scene's fog dims the lamp (drawn additively: it cannot be mixed towards the fog's colour)
    const fd = this.fogDensity.mul(dist);
    const k = face.mul(exp(fd.mul(fd).negate())).mul(aGain);
    const px = aSize.mul(900).div(max(dist, 0.5));
    // far away a lamp stays a 1.6 px dot and dims instead of shrinking away
    const dim = clamp01(px.div(1.6));
    const shown = k.greaterThanEqual(0.004).and(dist.greaterThanEqual(0.5));
    const projY = (cameraProjectionMatrix as unknown as Float[][])[1][1];
    mat.positionNode = aPos;
    mat.scaleNode = select(shown, clampNode(px, 1.6, 44).div(1080).mul(2).div(projY), 0);
    const lit = varying(aColor.mul(k).mul(dim));
    {
      const d = uv().sub(0.5);
      const r2 = dot(d, d).mul(4);
      // the halo fades to nothing at the sprite's rim (close up its square edge showed)
      const halo = exp(r2.mul(-7)).add(exp(r2.mul(-2.2)).mul(0.35)).mul(clamp01(r2.oneMinus()));
      mat.colorNode = vec4(lit.mul(halo), 1);
    }
    this.points = new THREE.Sprite(mat as unknown as THREE.SpriteMaterial);
    this.points.count = n;
    this.points.frustumCulled = false;
    this.points.name = 'traffic-lights';
    const bodyMat = new THREE.MeshStandardMaterial({ color: '#16181b', roughness: 0.45, metalness: 0.4 });
    const side = THREE.DoubleSide;
    const mats = {
      paint: new THREE.MeshStandardMaterial({ vertexColors: true, metalness: 0.5, roughness: 0.3, envMapIntensity: 1.2, side }),
      gloss: new THREE.MeshStandardMaterial({ vertexColors: true, metalness: 0.6, roughness: 0.26, side }),
      matte: new THREE.MeshStandardMaterial({ vertexColors: true, metalness: 0.1, roughness: 0.65, side }),
      lamp: new THREE.MeshBasicMaterial({ vertexColors: true, side }),
    };
    const instanced = (geo: THREE.BufferGeometry, mat: THREE.Material, n: number, name: string) => {
      const mesh = new THREE.InstancedMesh(geo, mat, Math.max(1, n));
      mesh.frustumCulled = false;
      mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
      mesh.name = name;
      this.group.add(mesh);
      return mesh;
    };
    CAR_ORDER.forEach((id, kind) => {
      const n = this.vehicles.filter((v) => !v.truck && v.kind === kind).length;
      const model = models[kind];
      const meshes = model
        ? TRAFFIC_PARTS.flatMap((p) => (model.parts[p] ? [instanced(model.parts[p], mats[p], n, `traffic-${id}-${p}`)] : []))
        : [instanced(bodyGeometry(false), mats.paint, n, `traffic-${id}-box`)];
      const paint = model ? meshes.find((m) => m.material === mats.paint) ?? null : meshes[0];
      if (paint) paint.instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(Math.max(1, n) * 3), 3).setUsage(THREE.DynamicDrawUsage);
      this.kinds.push({ meshes, paint, used: 0 });
    });
    this.trucks = instanced(bodyGeometry(true), bodyMat, this.vehicles.filter((v) => v.truck).length, 'traffic-lorries');
    this.group.add(this.points);
  }

  /** a vehicle's lane, speed and kind; at `s` relative to the camera's track distance `base` */
  private respawn(v: Vehicle, s: number, first = false) {
    const r = this.r;
    // a new paint job each time it comes round again
    const id = CAR_ORDER[v.kind];
    v.color.set(r() < 0.3 ? CAR_SPECS[id].colors.body : PAINTS[Math.floor(r() * PAINTS.length)]);
    if (v.dir < 0) {
      // the opposite carriageway: the game's cars only, the fast lane next to the median
      const lane = Math.min(this.oncomingLanes.length - 1, Math.floor(r() * r() * 3));
      v.lat = this.oncomingLanes[lane];
      v.speed = [41, 34, 28][lane] + r() * 8;
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
    const p = new THREE.Vector3(), f = new THREE.Vector3(), lt = new THREE.Vector3(), up = new THREE.Vector3();
    const m = new THREE.Matrix4(), zero = new THREE.Matrix4().makeScale(0, 0, 0);
    let iTruck = 0;
    for (const k of this.kinds) k.used = 0;
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
      // the vehicle's frame on the road: forward (with the grade), up (the road's normal), left
      f.fromArray(track.fwd, i * 3).multiplyScalar(v.dir);
      up.fromArray(track.up, i * 3);
      lt.crossVectors(up, f).normalize();
      up.crossVectors(f, lt);
      const lights = this.lights[n];
      for (let k = 0; k < LIGHTS; k++) {
        const o = (n * LIGHTS + k) * 3;
        const l = lights[k];
        if (!l) {
          this.gain[n * LIGHTS + k] = 0;
          continue;
        }
        this.pos[o] = p.x + f.x * l.f - lt.x * l.r + up.x * l.h;
        this.pos[o + 1] = p.y + f.y * l.f - lt.y * l.r + up.y * l.h;
        this.pos[o + 2] = p.z + f.z * l.f - lt.z * l.r + up.z * l.h;
        this.facing[o] = f.x * l.facing;
        this.facing[o + 1] = 0;
        this.facing[o + 2] = f.z * l.facing;
        this.gain[n * LIGHTS + k] = g;
      }
      m.makeBasis(lt, up, f).setPosition(p);
      if (v.truck) this.trucks.setMatrixAt(iTruck++, g > 0.05 ? m : zero);
      else if (g > 0.05 && dd > -250 && dd < this.modelRange) {
        const kind = this.kinds[v.kind];
        const slot = kind.used++;
        for (const mesh of kind.meshes) mesh.setMatrixAt(slot, m);
        kind.paint?.setColorAt(slot, v.color);
      }
    });
    for (const attr of this.dynamic) attr.needsUpdate = true;
    let top: THREE.Object3D = this.group;
    while (top.parent) top = top.parent;
    this.fogDensity.value = ((top as THREE.Scene).fog as THREE.FogExp2 | null)?.density ?? 0;
    this.trucks.instanceMatrix.needsUpdate = true;
    for (const k of this.kinds) {
      for (const mesh of k.meshes) {
        mesh.count = k.used;
        // no draw call for a model with no car in range
        mesh.visible = k.used > 0;
        mesh.instanceMatrix.needsUpdate = true;
      }
      if (k.paint?.instanceColor) k.paint.instanceColor.needsUpdate = true;
    }
  }
}
