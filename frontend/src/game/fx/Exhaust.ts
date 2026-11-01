import * as THREE from 'three';
import { makeSmokeTexture } from '../render/textures';

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
  points: THREE.Points;
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

function makePool(n: number, material: THREE.ShaderMaterial): Pool {
  const pos = new Float32Array(n * 3), size = new Float32Array(n), alpha = new Float32Array(n);
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3).setUsage(THREE.DynamicDrawUsage));
  geo.setAttribute('size', new THREE.BufferAttribute(size, 1).setUsage(THREE.DynamicDrawUsage));
  geo.setAttribute('alpha', new THREE.BufferAttribute(alpha, 1).setUsage(THREE.DynamicDrawUsage));
  const points = new THREE.Points(geo, material);
  points.frustumCulled = false;
  return { points, pos, vel: new Float32Array(n * 3), life: new Float32Array(n), maxLife: new Float32Array(n), size, alpha, base: new Float32Array(n), fresh: new Uint8Array(n), cursor: 0 };
}

const vertexShader = /* glsl */ `
  attribute float size; attribute float alpha;
  uniform float uScale;
  varying float vAlpha;
  #include <fog_pars_vertex>
  void main() {
    vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
    gl_PointSize = size * uScale / max(-mvPosition.z, 0.5);
    gl_Position = projectionMatrix * mvPosition;
    vAlpha = alpha;
    #include <fog_vertex>
  }`;

/**
 * Exhaust gas: thin puffs from the tailpipe (more on throttle and high revs, mostly visible at low
 * speed), and short backfire flames when the throttle is snapped shut at high revs.
 */
export class ExhaustFX {
  readonly group = new THREE.Group();
  private puffs: Pool;
  private flames: Pool;
  private uniforms: Record<string, THREE.IUniform>;
  private flameUniforms: Record<string, THREE.IUniform>;
  density = 1;

  constructor() {
    const map = makeSmokeTexture();
    this.uniforms = { uMap: { value: map }, uColor: { value: new THREE.Color('#8a9099') }, uScale: { value: 600 }, ...THREE.UniformsLib.fog };
    this.puffs = makePool(
      MAX_PUFFS,
      new THREE.ShaderMaterial({
        transparent: true,
        depthWrite: false,
        fog: true,
        uniforms: this.uniforms,
        vertexShader,
        fragmentShader: /* glsl */ `
          uniform sampler2D uMap; uniform vec3 uColor;
          varying float vAlpha;
          #include <fog_pars_fragment>
          void main() {
            vec4 t = texture2D(uMap, gl_PointCoord);
            gl_FragColor = vec4(uColor, t.a * vAlpha);
            #include <fog_fragment>
            #include <colorspace_fragment>
          }`,
      }),
    );
    this.flameUniforms = { uMap: { value: map }, uScale: { value: 600 }, ...THREE.UniformsLib.fog };
    this.flames = makePool(
      MAX_FLAMES,
      new THREE.ShaderMaterial({
        transparent: true,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
        uniforms: this.flameUniforms,
        vertexShader,
        fragmentShader: /* glsl */ `
          uniform sampler2D uMap;
          varying float vAlpha;
          void main() {
            vec4 t = texture2D(uMap, gl_PointCoord);
            float core = smoothstep(0.35, 1.0, t.a);
            // blue-white core, orange edge; bright enough to bloom
            vec3 c = mix(vec3(1.0, 0.42, 0.08), vec3(0.75, 0.85, 1.0), core);
            gl_FragColor = vec4(c * t.a * vAlpha * 3.0, 1.0);
          }`,
      }),
    );
    this.puffs.points.renderOrder = 5;
    this.flames.points.renderOrder = 6;
    this.group.add(this.puffs.points, this.flames.points);
  }

  setColor(c: THREE.ColorRepresentation) {
    this.uniforms.uColor.value.set(c);
  }

  setViewportHeight(h: number) {
    this.uniforms.uScale.value = h * 0.55;
    this.flameUniforms.uScale.value = h * 0.55;
  }

  /**
   * One frame of one car. `tip` = tailpipe in world space, `back` = unit vector out of the pipe,
   * `rpm` = revs as a fraction of the redline.
   * Returns true when a backfire went off (for the sound).
   */
  emit(s: ExhaustState, tip: THREE.Vector3, back: THREE.Vector3, carVel: THREE.Vector3, throttle: number, rpm: number, turbo: boolean, dt: number) {
    const speed = carVel.length();
    // puffs: a light idle trickle, more under load; thinned out at speed where the gas disperses at once
    const rate = (9 + 34 * throttle * rpm) * this.density * (1 / (1 + speed / 12));
    s.carry += rate * dt;
    while (s.carry >= 1) {
      s.carry -= 1;
      this.spawn(this.puffs, tip, carVel, back, 1.5 + 3.5 * throttle, 0.16, 0.8 + Math.random() * 0.8, 0.34 + 0.32 * throttle * rpm);
    }
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
    const g = pool.points.geometry;
    g.attributes.position.needsUpdate = true;
    g.attributes.size.needsUpdate = true;
    g.attributes.alpha.needsUpdate = true;
  }

  clear() {
    for (const pool of [this.puffs, this.flames]) {
      pool.life.fill(0);
      pool.alpha.fill(0);
      pool.points.geometry.attributes.alpha.needsUpdate = true;
    }
  }
}
