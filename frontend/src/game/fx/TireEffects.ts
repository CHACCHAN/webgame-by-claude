import * as THREE from 'three';
import { MeshBasicNodeMaterial } from 'three/webgpu';
import { attribute, texture, uniform, uv, vec4 } from 'three/tsl';
import { makeSmokeTexture } from '../render/textures';
import type { Float } from '../render/tslNoise';
import { makeSpritePool, type SpritePool } from './SpritePool';

const MAX_SMOKE = 700;

/** Pooled billboard smoke particles drawn in one call. */
export class TireSmoke {
  readonly points: THREE.Object3D;
  private pool: SpritePool;
  private pos: Float32Array;
  private vel = new Float32Array(MAX_SMOKE * 3);
  private life = new Float32Array(MAX_SMOKE);
  private maxLife = new Float32Array(MAX_SMOKE);
  private size: Float32Array;
  private alpha: Float32Array;
  private cursor = 0;
  private color = uniform(new THREE.Color('#9aa3ad'));
  density = 1;

  constructor() {
    const pool = (this.pool = makeSpritePool(MAX_SMOKE));
    this.pos = pool.pos;
    this.size = pool.size;
    this.alpha = pool.alpha;
    pool.material.colorNode = vec4(this.color, texture(makeSmokeTexture(), uv()).a.mul(pool.nodes.alpha));
    this.points = pool.object;
    this.points.renderOrder = 5;
  }

  setColor(c: THREE.ColorRepresentation) {
    this.color.value.set(c);
  }

  emit(p: THREE.Vector3, v: THREE.Vector3, intensity: number) {
    const i = this.cursor;
    this.cursor = (this.cursor + 1) % MAX_SMOKE;
    this.pos[i * 3] = p.x + (Math.random() - 0.5) * 0.3;
    this.pos[i * 3 + 1] = p.y + 0.15;
    this.pos[i * 3 + 2] = p.z + (Math.random() - 0.5) * 0.3;
    this.vel[i * 3] = v.x * 0.25 + (Math.random() - 0.5) * 1.5;
    this.vel[i * 3 + 1] = 0.6 + Math.random() * 0.9;
    this.vel[i * 3 + 2] = v.z * 0.25 + (Math.random() - 0.5) * 1.5;
    this.maxLife[i] = 1.6 + Math.random() * 1.4;
    this.life[i] = this.maxLife[i];
    this.size[i] = 0.6;
    this.alpha[i] = 0.25 * intensity;
  }

  update(dt: number) {
    for (let i = 0; i < MAX_SMOKE; i++) {
      if (this.life[i] <= 0) {
        this.alpha[i] = 0;
        continue;
      }
      this.life[i] -= dt;
      // capped: in the frame a puff dies life < 0, and (1 - t) ** 1.3 of a negative base is NaN. A NaN alpha on
      // a puff next to the camera (drawn screen-sized) turned the whole frame NaN, which bloom made black.
      const t = Math.min(1, 1 - this.life[i] / this.maxLife[i]);
      const drag = Math.exp(-dt * 1.6);
      this.vel[i * 3] *= drag;
      this.vel[i * 3 + 2] *= drag;
      this.vel[i * 3 + 1] = this.vel[i * 3 + 1] * drag + dt * 0.2;
      this.pos[i * 3] += this.vel[i * 3] * dt;
      this.pos[i * 3 + 1] += this.vel[i * 3 + 1] * dt;
      this.pos[i * 3 + 2] += this.vel[i * 3 + 2] * dt;
      this.size[i] = 0.6 + t * 4.8;
      this.alpha[i] = Math.min(this.alpha[i] + dt * 0.6, 0.55) * (1 - t) ** 1.3;
    }
    this.pool.commit();
  }

  clear() {
    this.life.fill(0);
    this.alpha.fill(0);
    this.pool.commit();
  }
}

const MAX_SEGMENTS = 3000;

/** Ring buffer of quad strips laid at sliding contact patches. */
export class SkidMarks {
  readonly mesh: THREE.Mesh;
  private positions = new Float32Array(MAX_SEGMENTS * 4 * 3);
  private alphas = new Float32Array(MAX_SEGMENTS * 4);
  private cursor = 0;
  private last: (THREE.Vector3 | null)[] = [];
  private lastSide: THREE.Vector3[] = [];

  constructor(wheels: number) {
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(this.positions, 3).setUsage(THREE.DynamicDrawUsage));
    geo.setAttribute('alpha', new THREE.BufferAttribute(this.alphas, 1).setUsage(THREE.DynamicDrawUsage));
    const idx = new Uint32Array(MAX_SEGMENTS * 6);
    for (let i = 0; i < MAX_SEGMENTS; i++) {
      const b = i * 4;
      idx.set([b, b + 2, b + 1, b + 1, b + 2, b + 3], i * 6);
    }
    geo.setIndex(new THREE.BufferAttribute(idx, 1));
    const mat = new MeshBasicNodeMaterial({ transparent: true, depthWrite: false, polygonOffset: true, polygonOffsetFactor: -4, polygonOffsetUnits: -4, fog: false });
    mat.colorNode = vec4(0.02, 0.02, 0.02, (attribute('alpha', 'float') as unknown as Float).mul(0.7));
    this.mesh = new THREE.Mesh(geo, mat);
    this.mesh.frustumCulled = false;
    this.mesh.renderOrder = 1;
    for (let i = 0; i < wheels; i++) {
      this.last.push(null);
      this.lastSide.push(new THREE.Vector3());
    }
  }

  /** Add a mark for wheel w at contact point p (normal n, forward dir f). */
  add(w: number, p: THREE.Vector3, n: THREE.Vector3, f: THREE.Vector3, intensity: number) {
    const prev = this.last[w];
    const side = new THREE.Vector3().crossVectors(f, n).normalize().multiplyScalar(0.11);
    const pt = p.clone().addScaledVector(n, 0.02);
    if (!prev || intensity <= 0.05) {
      this.last[w] = intensity > 0.05 ? pt : null;
      this.lastSide[w].copy(side);
      return;
    }
    if (prev.distanceToSquared(pt) < 0.09) return;
    if (prev.distanceToSquared(pt) > 9) {
      this.last[w] = pt;
      return;
    }
    const i = this.cursor;
    this.cursor = (this.cursor + 1) % MAX_SEGMENTS;
    const ps = this.lastSide[w];
    const o = i * 12;
    this.positions.set([prev.x - ps.x, prev.y - ps.y, prev.z - ps.z, prev.x + ps.x, prev.y + ps.y, prev.z + ps.z], o);
    this.positions.set([pt.x - side.x, pt.y - side.y, pt.z - side.z, pt.x + side.x, pt.y + side.y, pt.z + side.z], o + 6);
    const a = Math.min(1, intensity);
    this.alphas.set([a, a, a, a], i * 4);
    this.last[w] = pt;
    this.lastSide[w].copy(side);
    const g = this.mesh.geometry;
    g.attributes.position.needsUpdate = true;
    g.attributes.alpha.needsUpdate = true;
  }

  break(w: number) {
    this.last[w] = null;
  }

  clear() {
    this.alphas.fill(0);
    this.mesh.geometry.attributes.alpha.needsUpdate = true;
    this.last.fill(null);
  }
}
