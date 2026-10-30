import * as THREE from 'three';

const DROPS = 7000;
const BOX = new THREE.Vector3(70, 34, 70);

/**
 * GPU rain: line-segment streaks that fall and wrap inside a box that follows
 * the camera, so the cost is one draw call regardless of where you drive.
 */
export class Rain {
  readonly mesh: THREE.LineSegments;
  private uniforms: Record<string, THREE.IUniform>;

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
        varying float vA;
        #include <fog_pars_vertex>
        void main() {
          float speed = 16.0 + seed.y * 6.0;
          vec3 p;
          p.y = mod(seed.y * uBox.y - uTime * speed, uBox.y) - uBox.y * 0.5;
          p.x = mod(seed.x * uBox.x - uCam.x + uTime * 1.5, uBox.x) - uBox.x * 0.5;
          p.z = mod(seed.z * uBox.z - uCam.z, uBox.z) - uBox.z * 0.5;
          vec3 world = uCam + p;
          // streak direction: fall plus relative motion of the camera (driving into the rain)
          vec3 dir = normalize(vec3(-1.5, -speed, 0.0) - uVel * 0.6);
          world -= dir * position.y * (0.55 + length(uVel) * 0.012);
          vec4 mvPosition = viewMatrix * vec4(world, 1.0);
          gl_Position = projectionMatrix * mvPosition;
          float d = length(p.xz);
          vA = (1.0 - smoothstep(10.0, 34.0, d)) * (1.0 - position.y * 0.7);
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

  setIntensity(v: number) {
    this.uniforms.uIntensity.value = v;
    this.mesh.visible = v > 0.01;
  }

  update(time: number, camera: THREE.Vector3, velocity: THREE.Vector3) {
    if (!this.mesh.visible) return;
    this.uniforms.uTime.value = time;
    this.uniforms.uCam.value.copy(camera);
    this.uniforms.uVel.value.lerp(velocity, 0.1);
  }
}
