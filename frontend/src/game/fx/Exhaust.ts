import * as THREE from 'three';
import { mix, smoothstep, texture, uniform, uv, vec3, vec4 } from 'three/tsl';
import { makeSmokeTexture } from '../render/textures';
import { makeSpritePool, type SpritePool } from './SpritePool';

const MAX_PUFFS = 420;
const MAX_FLAMES = 48;

/** Per-car exhaust state (throttle history for backfires). */
export interface ExhaustState {
  lastThrottle: number;
  carry: number;
  flameTime: number;
}

export const newExhaustState = (): ExhaustState => ({ lastThrottle: 0, carry: 0, flameTime: 0 });

interface Pool {
  sprites: SpritePool;
  pos: Float32Array;
  vel: Float32Array;
  life: Float32Array;
  maxLife: Float32Array;
  size: Float32Array;
  alpha: Float32Array;
  /** alpha at birth */
  base: Float32Array;
  /** born this frame: drawn once before it starts to age (short flames would vanish unseen at low frame rates) */
  fresh: Uint8Array;
  cursor: number;
}

function makePool(n: number, additive: boolean): Pool {
  const sprites = makeSpritePool(n, { additive, fog: !additive });
  return { sprites, pos: sprites.pos, vel: new Float32Array(n * 3), life: new Float32Array(n), maxLife: new Float32Array(n), size: sprites.size, alpha: sprites.alpha, base: new Float32Array(n), fresh: new Uint8Array(n), cursor: 0 };
}

/**
 * How much of the exhaust gas is seen at a speed (m/s), 0…1: all of it standing still, half at 22 km/h, a tenth
 * at 65 km/h, none from 90 km/h on.
 */
export function exhaustSeen(speed: number) {
  const seen = 1 / (1 + (speed / 6) ** 2);
  return seen < 0.055 ? 0 : seen;
}

/**
 * Exhaust gas: thin puffs from the tailpipe (more on throttle and high revs, seen at low speed only:
 * `exhaustSeen`), and short backfire flames when the throttle is snapped shut at high revs.
 */
export class ExhaustFX {
  readonly group = new THREE.Group();
  private puffs: Pool;
  private flames: Pool;
  private color = uniform(new THREE.Color('#8a9099'));
  density = 1;

  constructor() {
    const map = makeSmokeTexture();
    this.puffs = makePool(MAX_PUFFS, false);
    this.puffs.sprites.material.colorNode = vec4(this.color, texture(map, uv()).a.mul(this.puffs.sprites.nodes.alpha));
    this.flames = makePool(MAX_FLAMES, true);
    {
      const t = texture(map, uv()).a;
      // blue-white core, orange edge; bright enough to bloom
      const c = mix(vec3(1, 0.42, 0.08), vec3(0.75, 0.85, 1), smoothstep(0.35, 1, t));
      this.flames.sprites.material.colorNode = vec4(c.mul(t).mul(this.flames.sprites.nodes.alpha).mul(3), 1);
    }
    this.puffs.sprites.object.renderOrder = 5;
    this.flames.sprites.object.renderOrder = 6;
    this.group.add(this.puffs.sprites.object, this.flames.sprites.object);
  }

  setColor(c: THREE.ColorRepresentation) {
    this.color.value.set(c);
  }

  /**
   * One frame of one car. `tip` = tailpipe in world space, `back` = unit vector out of the pipe,
   * `rpm` = revs as a fraction of the redline.
   * Returns true when a backfire went off (for the sound).
   */
  emit(s: ExhaustState, tip: THREE.Vector3, back: THREE.Vector3, carVel: THREE.Vector3, throttle: number, rpm: number, turbo: boolean, dt: number) {
    const speed = carVel.length();
    // puffs: a light idle trickle, more under load. What is seen of the gas falls with the speed: standing and
    // pulling away it is a plume, on the move the airstream takes it apart at once. (It used to be thinned out in
    // number only: a few puffs a second at full opacity, which trailed the car as a row of white balls, 11-12.)
    const seen = exhaustSeen(speed);
    if (seen > 0) {
      s.carry += (9 + 34 * throttle * rpm) * this.density * dt;
      while (s.carry >= 1) {
        s.carry -= 1;
        this.spawn(this.puffs, tip, carVel, back, 1.5 + 3.5 * throttle, 0.16, 0.8 + Math.random() * 0.8, (0.3 + 0.3 * throttle * rpm) * seen);
      }
    } else s.carry = 0;
    // backfire: throttle snapped shut at high revs
    let bang = false;
    if (s.lastThrottle > 0.6 && throttle < 0.15 && rpm > 0.62 && Math.random() < (turbo ? 0.75 : 0.45)) {
      s.flameTime = 0.1 + Math.random() * 0.1;
      bang = true;
    }
    s.lastThrottle = throttle;
    if (s.flameTime > 0) {
      s.flameTime -= dt;
      const n = Math.max(1, Math.round(dt / 0.016));
      for (let k = 0; k < n; k++) this.spawn(this.flames, tip, carVel, back, 7, 0.45, 0.07 + Math.random() * 0.05, 1);
    }
    return bang;
  }

  private spawn(pool: Pool, tip: THREE.Vector3, carVel: THREE.Vector3, back: THREE.Vector3, jet: number, size: number, life: number, alpha: number) {
    const i = pool.cursor;
    pool.cursor = (pool.cursor + 1) % pool.life.length;
    pool.pos[i * 3] = tip.x + (Math.random() - 0.5) * 0.05;
    pool.pos[i * 3 + 1] = tip.y + (Math.random() - 0.5) * 0.05;
    pool.pos[i * 3 + 2] = tip.z + (Math.random() - 0.5) * 0.05;
    pool.vel[i * 3] = carVel.x * 0.85 + back.x * jet + (Math.random() - 0.5) * 0.6;
    pool.vel[i * 3 + 1] = carVel.y * 0.85 + back.y * jet + 0.15 + Math.random() * 0.3;
    pool.vel[i * 3 + 2] = carVel.z * 0.85 + back.z * jet + (Math.random() - 0.5) * 0.6;
    pool.maxLife[i] = life;
    pool.life[i] = life;
    pool.size[i] = size;
    pool.alpha[i] = alpha;
    pool.base[i] = alpha;
    pool.fresh[i] = 1;
  }

  update(dt: number) {
    this.step(this.puffs, dt, (t, base) => [0.12 + t * 0.95, base * (1 - t) ** 1.4], 2.4);
    this.step(this.flames, dt, (t, base) => [0.45 * (1 + t * 0.7), base * (1 - t)], 0);
  }

  private step(pool: Pool, dt: number, shape: (t: number, base: number) => [number, number], dragK: number) {
    const drag = Math.exp(-dt * dragK);
    for (let i = 0; i < pool.life.length; i++) {
      if (pool.life[i] <= 0) {
        pool.alpha[i] = 0;
        continue;
      }
      if (pool.fresh[i]) pool.fresh[i] = 0;
      else pool.life[i] -= dt;
      const t = Math.min(1, 1 - pool.life[i] / pool.maxLife[i]);
      for (let k = 0; k < 3; k++) {
        pool.vel[i * 3 + k] *= drag;
        pool.pos[i * 3 + k] += pool.vel[i * 3 + k] * dt;
      }
      pool.vel[i * 3 + 1] += dt * 0.25; // warm gas rises a little
      const [size, alpha] = shape(t, pool.base[i]);
      pool.size[i] = size;
      pool.alpha[i] = alpha;
    }
    pool.sprites.commit();
  }

  clear() {
    for (const pool of [this.puffs, this.flames]) {
      pool.life.fill(0);
      pool.alpha.fill(0);
      pool.sprites.commit();
    }
  }
}
