import * as THREE from 'three';
import { mix, smoothstep, texture, uniform, uv, vec3, vec4 } from 'three/tsl';
import { makeSmokeTexture } from '../render/textures';
import { makeSpritePool, type SpritePool } from './SpritePool';
import type { Shell } from '../weapons/ballistics';

const MAX_SMOKE = 320;
const MAX_FIRE = 64;
const MAX_TRACERS = 16;

interface Pool {
  sprites: SpritePool;
  vel: Float32Array;
  life: Float32Array;
  maxLife: Float32Array;
  /** size at birth and at the end of its life, alpha at birth */
  from: Float32Array;
  to: Float32Array;
  base: Float32Array;
  /** born this frame: drawn once before it starts to age (a muzzle flash lasts a few frames) */
  fresh: Uint8Array;
  cursor: number;
}

function makePool(n: number, additive: boolean): Pool {
  const sprites = makeSpritePool(n, { additive, fog: !additive });
  return { sprites, vel: new Float32Array(n * 3), life: new Float32Array(n), maxLife: new Float32Array(n), from: new Float32Array(n), to: new Float32Array(n), base: new Float32Array(n), fresh: new Uint8Array(n), cursor: 0 };
}

const _p = new THREE.Vector3(), _side = new THREE.Vector3(), _up = new THREE.Vector3(0, 1, 0);

/**
 * What a tank gun's shot looks like, as far as the game shows it (owner 11-12: in a race the look is realism
 * first): the flash at the muzzle (a few frames, bright enough to bloom), the propellant smoke rolling out along
 * the bore and drifting, the tracer in the shell's tail, and at the other end the burst of dust or of sparks.
 * Camera-facing sprites in three pools (`SpritePool`: one draw call each); no light is added (the shaders are built
 * for the game's fixed set of lights, `render/LightRig.ts`).
 *
 * Made the first time a race has a tank in it, and from then on part of the scene (hidden outside such races).
 */
export class GunFx {
  readonly group = new THREE.Group();
  private smoke: Pool;
  private fire: Pool;
  private tracers: SpritePool;
  private color = uniform(new THREE.Color('#8f8f8a'));

  constructor() {
    const map = makeSmokeTexture();
    this.smoke = makePool(MAX_SMOKE, false);
    this.smoke.sprites.material.colorNode = vec4(this.color, texture(map, uv()).a.mul(this.smoke.sprites.nodes.alpha));
    this.fire = makePool(MAX_FIRE, true);
    {
      const t = texture(map, uv()).a;
      // a white-yellow core, orange at the edge
      const c = mix(vec3(1, 0.45, 0.1), vec3(1, 0.92, 0.7), smoothstep(0.3, 0.9, t));
      this.fire.sprites.material.colorNode = vec4(c.mul(t).mul(this.fire.sprites.nodes.alpha).mul(5), 1);
    }
    this.tracers = makeSpritePool(MAX_TRACERS, { additive: true, fog: false });
    {
      const t = texture(map, uv()).a;
      this.tracers.material.colorNode = vec4(vec3(1, 0.5, 0.2).mul(t).mul(this.tracers.nodes.alpha).mul(4), 1);
    }
    // thin additive things that are elsewhere every frame: marked for the upscaler as the flames are not (they
    // are gone in a few frames), the tracers are (render/sceneUpscale.ts)
    this.tracers.material.userData.reactive = 2;
    this.smoke.sprites.object.renderOrder = 5;
    this.fire.sprites.object.renderOrder = 6;
    this.tracers.object.renderOrder = 6;
    this.group.add(this.smoke.sprites.object, this.fire.sprites.object, this.tracers.object);
  }

  /** the smoke takes the light of the time of day, as the tyre smoke does */
  setColor(c: THREE.ColorRepresentation) {
    this.color.value.set(c);
  }

  /**
   * A shot: `muzzle` and the bore's direction `dir` (unit), the firer's velocity, the calibre (mm: a 105 makes a
   * little less of everything than a 125).
   */
  shot(muzzle: THREE.Vector3, dir: THREE.Vector3, velocity: THREE.Vector3, calibre: number) {
    const k = calibre / 120;
    // the flash: a ball at the muzzle and a tongue ahead of it
    this.spawn(this.fire, muzzle, velocity, 0, 0, 0, 3.2 * k, 4.6 * k, 0.07, 1);
    for (let i = 1; i <= 4; i++) {
      _p.copy(muzzle).addScaledVector(dir, i * 0.9 * k);
      this.spawn(this.fire, _p, velocity, dir.x * 30, dir.y * 30, dir.z * 30, (2.6 - i * 0.4) * k, (3.4 - i * 0.4) * k, 0.05 + Math.random() * 0.04, 0.9);
    }
    // the smoke: pushed out along the bore, the nearest puffs slowest, and a ring thrown sideways at the muzzle
    for (let i = 0; i < 16; i++) {
      const f = i / 15;
      const speed = 3 + 26 * f * (0.7 + Math.random() * 0.6);
      _p.copy(muzzle).addScaledVector(dir, f * 1.5);
      this.spawn(this.smoke, _p, velocity, dir.x * speed + (Math.random() - 0.5) * 2.5, dir.y * speed + (Math.random() - 0.3) * 2, dir.z * speed + (Math.random() - 0.5) * 2.5, 0.9 * k, (4.5 + Math.random() * 3) * k, 2.2 + Math.random() * 1.8, 0.42);
    }
    _side.crossVectors(dir, _up).normalize();
    for (let i = 0; i < 10; i++) {
      const a = (i / 10) * Math.PI * 2, s = 5 + Math.random() * 4;
      const sx = Math.cos(a), sy = Math.sin(a);
      this.spawn(this.smoke, muzzle, velocity, (_side.x * sx) * s + dir.x * 2, sy * s * 0.6 + 0.5, (_side.z * sx) * s + dir.z * 2, 0.7 * k, 3.4 * k, 1.4 + Math.random(), 0.3);
    }
  }

  /** A shell met the ground (dust thrown up) or a vehicle (`metal`: sparks and a darker puff). */
  impact(point: THREE.Vector3, metal: boolean) {
    this.spawn(this.fire, point, null, 0, 0, 0, metal ? 2.4 : 1.4, metal ? 3.8 : 2.2, metal ? 0.09 : 0.06, 1);
    if (metal) for (let i = 0; i < 10; i++) this.spawn(this.fire, point, null, (Math.random() - 0.5) * 34, Math.random() * 18, (Math.random() - 0.5) * 34, 0.35, 0.12, 0.25 + Math.random() * 0.3, 0.9);
    const n = metal ? 12 : 18;
    for (let i = 0; i < n; i++) {
      const up = (metal ? 2 : 5) + Math.random() * (metal ? 4 : 9);
      this.spawn(this.smoke, point, null, (Math.random() - 0.5) * 9, up, (Math.random() - 0.5) * 9, 0.8, 3.5 + Math.random() * 3, 1.8 + Math.random() * 2, metal ? 0.4 : 0.5);
    }
  }

  private spawn(pool: Pool, at: THREE.Vector3, carry: THREE.Vector3 | null, vx: number, vy: number, vz: number, from: number, to: number, life: number, alpha: number) {
    const i = pool.cursor;
    pool.cursor = (pool.cursor + 1) % pool.life.length;
    const pos = pool.sprites.pos;
    pos[i * 3] = at.x;
    pos[i * 3 + 1] = at.y;
    pos[i * 3 + 2] = at.z;
    // (the gas leaves with the gun's own speed, most of which the air takes at once)
    pool.vel[i * 3] = vx + (carry ? carry.x * 0.5 : 0);
    pool.vel[i * 3 + 1] = vy + (carry ? carry.y * 0.5 : 0);
    pool.vel[i * 3 + 2] = vz + (carry ? carry.z * 0.5 : 0);
    pool.life[i] = pool.maxLife[i] = life;
    pool.from[i] = from;
    pool.to[i] = to;
    pool.base[i] = alpha;
    pool.fresh[i] = 1;
    pool.sprites.size[i] = from;
    pool.sprites.alpha[i] = alpha;
  }

  /**
   * Per frame: the puffs age; a tracer is drawn in each live shell's tail, between its last two steps (`alpha`:
   * how far the frame is into the physics step), no smaller than a few pixels however far it is from `eye`.
   */
  update(dt: number, shells: readonly Shell[], alpha: number, eye: THREE.Vector3) {
    this.step(this.smoke, dt, 2.6, 0.35, 1.5);
    this.step(this.fire, dt, 3, -6, 1);
    const tr = this.tracers;
    for (let i = 0; i < MAX_TRACERS; i++) {
      const s = shells[i];
      if (!s) {
        tr.alpha[i] = 0;
        continue;
      }
      _p.lerpVectors(s.prev, s.p, alpha);
      tr.pos[i * 3] = _p.x;
      tr.pos[i * 3 + 1] = _p.y;
      tr.pos[i * 3 + 2] = _p.z;
      // (the tracer lights a moment after the muzzle)
      tr.alpha[i] = s.flown > 12 ? 1 : 0;
      tr.size[i] = Math.max(0.5, _p.distanceTo(eye) * 0.006);
    }
    tr.commit();
  }

  private step(pool: Pool, dt: number, dragK: number, rise: number, fade: number) {
    const drag = Math.exp(-dt * dragK);
    const { pos, size, alpha } = pool.sprites;
    for (let i = 0; i < pool.life.length; i++) {
      if (pool.life[i] <= 0) {
        alpha[i] = 0;
        continue;
      }
      if (pool.fresh[i]) pool.fresh[i] = 0;
      else pool.life[i] -= dt;
      // (clamped: in the frame a puff dies its age passes 1, and a power of a negative base is NaN, which a
      // sprite next to the camera spreads over the whole picture)
      const t = Math.min(1, Math.max(0, 1 - pool.life[i] / pool.maxLife[i]));
      for (let k = 0; k < 3; k++) {
        pool.vel[i * 3 + k] *= drag;
        pos[i * 3 + k] += pool.vel[i * 3 + k] * dt;
      }
      pool.vel[i * 3 + 1] += dt * rise;
      // quick to swell, slow to finish
      size[i] = pool.from[i] + (pool.to[i] - pool.from[i]) * (1 - (1 - t) * (1 - t));
      alpha[i] = pool.base[i] * Math.pow(1 - t, fade);
    }
    pool.sprites.commit();
  }

  clear() {
    for (const pool of [this.smoke, this.fire]) {
      pool.life.fill(0);
      pool.sprites.alpha.fill(0);
      pool.sprites.commit();
    }
    this.tracers.alpha.fill(0);
    this.tracers.commit();
  }

  dispose() {
    for (const s of [this.smoke.sprites, this.fire.sprites, this.tracers]) s.material.dispose();
  }
}
