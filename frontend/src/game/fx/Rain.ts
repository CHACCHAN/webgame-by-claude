import * as THREE from 'three';

const DROPS = 7000;
const BOX = new THREE.Vector3(70, 34, 70);
/** roof quads (rock sheds) the shader checks, the nearest to the camera: 16 × 6 m covers the visible rain both ways */
const MAX_COVERS = 16;
/** re-pick the nearest roof quads after the camera has moved this far (m) */
const REPICK = 3;

/**
 * GPU rain: line-segment streaks that fall and wrap inside a box that follows
 * the camera, so the cost is one draw call regardless of where you drive.
 * No rain under a roof: streaks below the slab of the nearest rock-shed quads are dropped.
 */
export class Rain {
  readonly mesh: THREE.LineSegments;
  private uniforms: Record<string, THREE.IUniform>;
  private covers: Float32Array = new Float32Array(0);
  private picked = new THREE.Vector3(Infinity, 0, 0);
  private order: number[] = [];

  constructor() {
    const pos = new Float32Array(DROPS * 2 * 3);
    const seed = new Float32Array(DROPS * 2 * 3);
    for (let i = 0; i < DROPS; i++) {
      const x = Math.random(), y = Math.random(), z = Math.random();
      for (let e = 0; e < 2; e++) {
        const o = (i * 2 + e) * 3;
        pos.set([0, e, 0], o); // y component marks the streak end (0 = head, 1 = tail)
        seed.set([x, y, z], o);
      }
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    geo.setAttribute('seed', new THREE.BufferAttribute(seed, 3));
    this.uniforms = {
      uTime: { value: 0 },
      uCam: { value: new THREE.Vector3() },
      uBox: { value: BOX },
      uIntensity: { value: 0 },
      uColor: { value: new THREE.Color('#9fb2cc') },
      uVel: { value: new THREE.Vector3() },
      uCoverA: { value: Array.from({ length: MAX_COVERS }, () => new THREE.Vector4()) },
      uCoverB: { value: Array.from({ length: MAX_COVERS }, () => new THREE.Vector4()) },
      uCoverY: { value: new Array<number>(MAX_COVERS).fill(0) },
      uCoverN: { value: 0 },
      ...THREE.UniformsLib.fog,
    };
    const mat = new THREE.ShaderMaterial({
      transparent: true,
      depthWrite: false,
      fog: true,
      blending: THREE.AdditiveBlending,
      uniforms: this.uniforms,
      vertexShader: /* glsl */ `
        attribute vec3 seed;
        uniform float uTime; uniform vec3 uCam, uBox, uVel;
        uniform vec4 uCoverA[${MAX_COVERS}], uCoverB[${MAX_COVERS}];
        uniform float uCoverY[${MAX_COVERS}];
        uniform int uCoverN;
        varying float vA;
        #include <fog_pars_vertex>
        float edgeSide(vec2 a, vec2 b, vec2 q) { vec2 e = b - a, d = q - a; return e.x * d.y - e.y * d.x; }
        // under one of the roof quads (corners a b c d in order, either winding) and below its slab
        bool underRoof(vec3 w) {
          for (int k = 0; k < ${MAX_COVERS}; k++) {
            if (k >= uCoverN) break;
            if (w.y > uCoverY[k]) continue;
            vec2 a = uCoverA[k].xy, b = uCoverA[k].zw, c = uCoverB[k].xy, d = uCoverB[k].zw;
            vec4 s = vec4(edgeSide(a, b, w.xz), edgeSide(b, c, w.xz), edgeSide(c, d, w.xz), edgeSide(d, a, w.xz));
            if (all(greaterThanEqual(s, vec4(0.0))) || all(lessThanEqual(s, vec4(0.0)))) return true;
          }
          return false;
        }
        void main() {
          float speed = 16.0 + seed.y * 6.0;
          vec3 p;
          p.y = mod(seed.y * uBox.y - uTime * speed, uBox.y) - uBox.y * 0.5;
          p.x = mod(seed.x * uBox.x - uCam.x + uTime * 1.5, uBox.x) - uBox.x * 0.5;
          p.z = mod(seed.z * uBox.z - uCam.z, uBox.z) - uBox.z * 0.5;
          vec3 world = uCam + p;
          // both ends of a streak share its seed, so a drop under a roof loses the whole streak
          bool covered = underRoof(world);
          // streak direction: fall plus relative motion of the camera (driving into the rain)
          vec3 dir = normalize(vec3(-1.5, -speed, 0.0) - uVel * 0.6);
          world -= dir * position.y * (0.55 + length(uVel) * 0.012);
          vec4 mvPosition = viewMatrix * vec4(world, 1.0);
          gl_Position = projectionMatrix * mvPosition;
          float d = length(p.xz);
          vA = covered ? 0.0 : (1.0 - smoothstep(10.0, 34.0, d)) * (1.0 - position.y * 0.7);
          #include <fog_vertex>
        }`,
      fragmentShader: /* glsl */ `
        uniform vec3 uColor; uniform float uIntensity;
        varying float vA;
        #include <fog_pars_fragment>
        void main() {
          gl_FragColor = vec4(uColor * vA * 0.35 * uIntensity, 1.0);
          #include <fog_fragment>
        }`,
    });
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
    this.uniforms.uCoverN.value = 0;
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
    const A = this.uniforms.uCoverA.value as THREE.Vector4[], B = this.uniforms.uCoverB.value as THREE.Vector4[];
    const Y = this.uniforms.uCoverY.value as number[];
    near.forEach((i, k) => {
      const o = i * 9;
      A[k].set(c[o], c[o + 1], c[o + 2], c[o + 3]);
      B[k].set(c[o + 4], c[o + 5], c[o + 6], c[o + 7]);
      Y[k] = c[o + 8];
    });
    this.uniforms.uCoverN.value = near.length;
  }

  setIntensity(v: number) {
    this.uniforms.uIntensity.value = v;
    this.mesh.visible = v > 0.01;
  }

  update(time: number, camera: THREE.Vector3, velocity: THREE.Vector3) {
    if (!this.mesh.visible) return;
    this.uniforms.uTime.value = time;
    this.uniforms.uCam.value.copy(camera);
    this.uniforms.uVel.value.lerp(velocity, 0.1);
    if (this.covers.length) this.pickCovers(camera);
  }
}
