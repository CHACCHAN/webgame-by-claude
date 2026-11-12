import * as THREE from 'three';
import { LineBasicNodeMaterial } from 'three/webgpu';
import { attribute, float, fract, length, max, min, mod, normalize, positionGeometry, select, smoothstep, uniform, uniformArray, varying, vec3, vec4 } from 'three/tsl';
import type { Float, Vec2, Vec3, Vec4 } from '../render/tslNoise';

const DROPS = 7000;
const BOX = new THREE.Vector3(70, 34, 70);
/** roof quads (rock sheds) the shader checks, the nearest to the camera: 16 × 6 m covers the visible rain both ways */
const MAX_COVERS = 16;
/** re-pick the nearest roof quads after the camera has moved this far (m) */
const REPICK = 3;
/** the slab height of an unused roof slot: no drop is below it */
const NO_COVER = -1e9;

/**
 * GPU rain: line-segment streaks that fall and wrap inside a box that follows
 * the camera, so the cost is one draw call regardless of where you drive.
 * No rain under a roof: streaks below the slab of the nearest rock-shed quads are dropped.
 */
export class Rain {
  readonly mesh: THREE.LineSegments;
  private uTime = uniform(0);
  private uCam = uniform(new THREE.Vector3());
  private uVel = uniform(new THREE.Vector3());
  private uIntensity = uniform(0);
  /**
   * the picked roof quads: corners a, b (x z, x z) and c, d, and the slab's height in x (unused slots lie
   * far below; a vec4 each: narrower elements of a uniform array are padded differently by the two backends) */
  private coverA = Array.from({ length: MAX_COVERS }, () => new THREE.Vector4());
  private coverB = Array.from({ length: MAX_COVERS }, () => new THREE.Vector4());
  private coverY = Array.from({ length: MAX_COVERS }, () => new THREE.Vector4(NO_COVER, 0, 0, 0));
  private covers: Float32Array = new Float32Array(0);
  private picked = new THREE.Vector3(Infinity, 0, 0);
  private order: number[] = [];

  constructor() {
    const pos = new Float32Array(DROPS * 2 * 3);
    const seeds = new Float32Array(DROPS * 2 * 3);
    for (let i = 0; i < DROPS; i++) {
      const x = Math.random(), y = Math.random(), z = Math.random();
      for (let e = 0; e < 2; e++) {
        const o = (i * 2 + e) * 3;
        pos.set([0, e, 0], o); // y component marks the streak end (0 = head, 1 = tail)
        seeds.set([x, y, z], o);
      }
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    geo.setAttribute('seed', new THREE.BufferAttribute(seeds, 3));

    const { uTime, uCam, uVel } = this;
    const seed = attribute('seed', 'vec3') as unknown as Vec3;
    const end = (positionGeometry as unknown as Vec3).y;
    // each drop's own speed, from another seed than its height: with the height's seed the drops gathered into a
    // band during a race's first seconds (their heights stayed a function of one number)
    const speed = fract(seed.x.mul(7.31).add(seed.z.mul(3.17))).mul(6).add(16);
    // the drop inside the box that follows the camera
    const p = vec3(
      mod(seed.x.mul(BOX.x).sub(uCam.x).add(uTime.mul(1.5)), BOX.x).sub(BOX.x / 2),
      mod(seed.y.mul(BOX.y).sub(uTime.mul(speed)), BOX.y).sub(BOX.y / 2),
      mod(seed.z.mul(BOX.z).sub(uCam.z), BOX.z).sub(BOX.z / 2),
    );
    const head = uCam.add(p);
    // both ends of a streak share its seed, so a drop under a roof loses the whole streak:
    // under one of the roof quads (corners a b c d in order, either winding) and below its slab
    const cA = uniformArray(this.coverA), cB = uniformArray(this.coverB), cY = uniformArray(this.coverY);
    const side = (a: Vec2, b: Vec2, q: Vec2) => {
      const e = b.sub(a), d = q.sub(a);
      return e.x.mul(d.y).sub(e.y.mul(d.x));
    };
    let open: Float = float(1);
    for (let k = 0; k < MAX_COVERS; k++) {
      const A = cA.element(k) as unknown as Vec4, B = cB.element(k) as unknown as Vec4;
      const a = A.xy, b = A.zw, c = B.xy, d = B.zw, q = head.xz;
      const s1 = side(a, b, q), s2 = side(b, c, q), s3 = side(c, d, q), s4 = side(d, a, q);
      const inside = min(min(s1, s2), min(s3, s4)).greaterThanEqual(0).or(max(max(s1, s2), max(s3, s4)).lessThanEqual(0));
      open = open.mul(select(inside.and(head.y.lessThanEqual((cY.element(k) as unknown as Vec4).x)), 0, 1));
    }
    // streak direction: fall plus relative motion of the camera (driving into the rain)
    const dir = normalize(vec3(-1.5, speed.negate(), 0).sub(uVel.mul(0.6)));
    const mat = new LineBasicNodeMaterial({ transparent: true, depthWrite: false, fog: true, blending: THREE.AdditiveBlending });
    mat.positionNode = head.sub(dir.mul(end).mul(length(uVel).mul(0.012).add(0.55)));
    const alpha = varying(open.mul(smoothstep(10, 34, length(p.xz)).oneMinus()).mul(end.mul(0.7).oneMinus()));
    mat.colorNode = vec4(uniform(new THREE.Color('#9fb2cc')).mul(alpha).mul(0.35).mul(this.uIntensity), 1);
    // (the upscaler's reactive mask, RenderHost `surfaceReactive`: a streak is somewhere else every frame, so even a
    // faint one is most of its pixel; by its light alone the far and the fading ones were averaged away, 0.6 of
    // native's streak pixels; at 4 they stood bolder than native and left a copy behind, 1.4-1.6 of them; at 2: 0.9-1.2)
    mat.userData.reactive = 2;
    this.mesh = new THREE.LineSegments(geo, mat);
    this.mesh.frustumCulled = false;
    this.mesh.renderOrder = 6;
    this.mesh.visible = false;
  }

  /** the course's roofs (SceneryResult.covers: 9 floats per quad) */
  setCovers(covers: Float32Array) {
    this.covers = covers;
    this.order = Array.from({ length: covers.length / 9 }, (_, i) => i);
    this.picked.set(Infinity, 0, 0);
    for (const y of this.coverY) y.x = NO_COVER;
  }

  /** the roof quads nearest the camera (by their centres) into the shader's uniforms */
  private pickCovers(camera: THREE.Vector3) {
    if (this.picked.distanceToSquared(camera) < REPICK * REPICK) return;
    this.picked.copy(camera);
    const c = this.covers;
    const dist = (i: number) => {
      const o = i * 9;
      const x = (c[o] + c[o + 2] + c[o + 4] + c[o + 6]) / 4 - camera.x, z = (c[o + 1] + c[o + 3] + c[o + 5] + c[o + 7]) / 4 - camera.z;
      return x * x + z * z;
    };
    const near = this.order.filter((i) => dist(i) < 80 * 80).sort((i, j) => dist(i) - dist(j)).slice(0, MAX_COVERS);
    for (let k = 0; k < MAX_COVERS; k++) {
      if (k >= near.length) {
        this.coverY[k].x = NO_COVER;
        continue;
      }
      const o = near[k] * 9;
      this.coverA[k].set(c[o], c[o + 1], c[o + 2], c[o + 3]);
      this.coverB[k].set(c[o + 4], c[o + 5], c[o + 6], c[o + 7]);
      this.coverY[k].x = c[o + 8];
    }
  }

  setIntensity(v: number) {
    this.uIntensity.value = v;
    this.mesh.visible = v > 0.01;
  }

  update(time: number, camera: THREE.Vector3, velocity: THREE.Vector3) {
    if (!this.mesh.visible) return;
    this.uTime.value = time;
    this.uCam.value.copy(camera);
    this.uVel.value.lerp(velocity, 0.1);
    if (this.covers.length) this.pickCovers(camera);
  }
}
