import * as THREE from 'three';
import type { TerrainData } from '../track/terrain';
import { fbm, rng, smoothstep } from '../util/math';
import { makeGlowTexture } from './textures';

export type TimeOfDay = 'night' | 'dawn';

interface Preset {
  zenith: string;
  horizon: string;
  glow: string;
  cityGlow: number;
  fog: string;
  fogDensity: number;
  keyColor: string;
  keyIntensity: number;
  keyDir: THREE.Vector3;
  hemiSky: string;
  hemiGround: string;
  hemiIntensity: number;
  stars: number;
  exposure: number;
  lampsOn: number;
  cityLights: number;
  sea: string;
  clouds: number;
  cloudColor: string;
  seaOfClouds: number;
}

export const PRESETS: Record<TimeOfDay, Preset> = {
  night: {
    zenith: '#010309',
    horizon: '#0f1b30',
    glow: '#ff8c42',
    cityGlow: 0.55,
    fog: '#101d33',
    fogDensity: 0.00038,
    keyColor: '#a9bfff',
    keyIntensity: 1.5,
    keyDir: new THREE.Vector3(0.38, 0.5, 0.78).normalize(),
    hemiSky: '#3c5584',
    hemiGround: '#141820',
    hemiIntensity: 1.15,
    stars: 1,
    exposure: 1.15,
    lampsOn: 1,
    cityLights: 1,
    sea: '#04101c',
    clouds: 0.35,
    cloudColor: '#26324a',
    seaOfClouds: 0,
  },
  dawn: {
    zenith: '#2f5c96',
    horizon: '#f4b37f',
    glow: '#ffb27a',
    cityGlow: 0.0,
    fog: '#b7a7a6',
    fogDensity: 0.00032,
    keyColor: '#ffbf80',
    keyIntensity: 2.6,
    keyDir: new THREE.Vector3(0.82, 0.16, 0.55).normalize(),
    hemiSky: '#9cb6d6',
    hemiGround: '#3d3427',
    hemiIntensity: 0.9,
    stars: 0,
    exposure: 0.95,
    lampsOn: 0.15,
    cityLights: 0.0,
    sea: '#3b5470',
    clouds: 0.5,
    cloudColor: '#f6c8a8',
    seaOfClouds: 1,
  },
};

const skyVert = /* glsl */ `
varying vec3 vDir;
void main() {
  vDir = position;
  vec4 p = modelViewMatrix * vec4(position, 1.0);
  gl_Position = projectionMatrix * p;
  gl_Position.z = gl_Position.w; // at infinity
}`;

const skyFrag = /* glsl */ `
uniform vec3 uZenith, uHorizon, uGlow, uCloudColor, uKeyDir, uKeyColor, uCityDir;
uniform float uCityGlow, uStars, uTime, uClouds, uIsSun;
varying vec3 vDir;
float hash(vec3 p) { p = fract(p * 0.3183099 + 0.1); p *= 17.0; return fract(p.x * p.y * p.z * (p.x + p.y + p.z)); }
float hash2(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float vnoise(vec2 p) {
  vec2 i = floor(p), f = fract(p);
  f = f * f * (3.0 - 2.0 * f);
  return mix(mix(hash2(i), hash2(i + vec2(1, 0)), f.x), mix(hash2(i + vec2(0, 1)), hash2(i + vec2(1, 1)), f.x), f.y);
}
float fbm(vec2 p) { float a = 0.5, s = 0.0; for (int i = 0; i < 5; i++) { s += a * vnoise(p); p *= 2.03; a *= 0.5; } return s; }
void main() {
  vec3 d = normalize(vDir);
  float h = d.y;
  vec3 col = mix(uHorizon, uZenith, pow(clamp(h, 0.0, 1.0), 0.42));
  col = mix(col, uHorizon * 0.55, smoothstep(0.0, -0.25, h));
  // light pollution from the city below
  vec3 flatDir = normalize(vec3(d.x, 0.0, d.z) + 1e-5);
  float cityA = max(dot(flatDir, uCityDir), 0.0);
  col += uGlow * pow(cityA, 2.5) * exp(-max(h + 0.02, 0.0) * 10.0) * uCityGlow;
  // key light glow (sun at dawn) and disc (moon/sun)
  float kd = max(dot(d, uKeyDir), 0.0);
  col += uKeyColor * (pow(kd, 8.0) * 0.25 + pow(kd, 64.0) * 0.5) * (0.15 + uIsSun * 0.85);
  float disc = smoothstep(mix(0.99955, 0.9993, uIsSun), mix(0.9997, 0.9996, uIsSun), kd);
  vec3 discCol = mix(vec3(1.0, 0.97, 0.9) * 2.6, vec3(1.0, 0.85, 0.6) * 9.0, uIsSun);
  // subtle craters on the moon
  float crater = (1.0 - uIsSun) * (vnoise(d.xy * 900.0) * 0.25);
  col = mix(col, discCol * (1.0 - crater), disc);
  // stars
  if (uStars > 0.0 && h > 0.0) {
    vec3 sp = d * 320.0;
    vec3 cell = floor(sp);
    float r = hash(cell);
    if (r > 0.985) {
      vec3 f = fract(sp) - 0.5;
      float tw = 0.65 + 0.35 * sin(uTime * (1.5 + r * 6.0) + r * 100.0);
      float b = smoothstep(0.25, 0.0, length(f)) * (r - 0.985) / 0.015;
      col += vec3(0.8 + r * 0.2, 0.85, 1.0) * b * tw * 1.6 * uStars * smoothstep(0.0, 0.25, h);
    }
    // faint milky band
    float band = exp(-pow(dot(d, normalize(vec3(0.35, 0.62, -0.7))), 2.0) * 22.0);
    col += vec3(0.05, 0.055, 0.08) * band * smoothstep(0.45, 0.8, fbm(d.xz * 6.0 + d.y * 3.0)) * uStars;
  }
  // thin clouds
  if (h > 0.0 && uClouds > 0.0) {
    vec2 uv = d.xz / (h + 0.12) * 1.4 + vec2(uTime * 0.004, 0.0);
    float c = smoothstep(0.52, 0.85, fbm(uv));
    float lit = 0.5 + 0.5 * pow(kd, 4.0);
    col = mix(col, uCloudColor * lit, c * uClouds * smoothstep(0.0, 0.18, h));
  }
  gl_FragColor = vec4(col, 1.0);
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}`;

export interface EnvironmentRig {
  group: THREE.Group;
  sky: THREE.Mesh;
  skyUniforms: Record<string, THREE.IUniform>;
  key: THREE.DirectionalLight;
  hemi: THREE.HemisphereLight;
  fog: THREE.FogExp2;
  city: THREE.Points;
  sea: THREE.Mesh;
  cloudSea: THREE.Mesh;
  preset: Preset;
  apply(tod: TimeOfDay, scene: THREE.Scene, renderer: THREE.WebGLRenderer): void;
  update(time: number, focus: THREE.Vector3): void;
  buildEnvMap(renderer: THREE.WebGLRenderer): THREE.Texture;
}

export function buildEnvironment(terrain: TerrainData): EnvironmentRig {
  const group = new THREE.Group();
  group.name = 'environment';

  // ---- sky dome
  const skyUniforms: Record<string, THREE.IUniform> = {
    uZenith: { value: new THREE.Color() },
    uHorizon: { value: new THREE.Color() },
    uGlow: { value: new THREE.Color() },
    uCloudColor: { value: new THREE.Color() },
    uKeyDir: { value: new THREE.Vector3() },
    uKeyColor: { value: new THREE.Color() },
    uCityDir: { value: new THREE.Vector3(0.1, 0, 1).normalize() },
    uCityGlow: { value: 1 },
    uStars: { value: 1 },
    uTime: { value: 0 },
    uClouds: { value: 0.4 },
    uIsSun: { value: 0 },
  };
  const sky = new THREE.Mesh(
    new THREE.SphereGeometry(9000, 48, 24),
    new THREE.ShaderMaterial({ uniforms: skyUniforms, vertexShader: skyVert, fragmentShader: skyFrag, side: THREE.BackSide, depthWrite: false }),
  );
  sky.frustumCulled = false;
  sky.renderOrder = -10;
  group.add(sky);

  // ---- lights
  const key = new THREE.DirectionalLight('#ffffff', 1);
  key.castShadow = true;
  key.shadow.mapSize.set(2048, 2048);
  key.shadow.camera.left = -60;
  key.shadow.camera.right = 60;
  key.shadow.camera.top = 60;
  key.shadow.camera.bottom = -60;
  key.shadow.camera.near = 1;
  key.shadow.camera.far = 600;
  key.shadow.bias = -0.0004;
  key.shadow.normalBias = 0.04;
  group.add(key);
  group.add(key.target);
  const hemi = new THREE.HemisphereLight('#ffffff', '#000000', 1);
  group.add(hemi);
  const fog = new THREE.FogExp2('#000000', 0.0005);

  // ---- sea
  const seaNormal = makeWaveNormal();
  seaNormal.repeat.set(220, 220);
  const seaMat = new THREE.MeshStandardMaterial({
    color: '#04101c',
    roughness: 0.12,
    metalness: 0.1,
    normalMap: seaNormal,
    normalScale: new THREE.Vector2(0.35, 0.35),
    envMapIntensity: 1.2,
  });
  const sea = new THREE.Mesh(new THREE.PlaneGeometry(26000, 16000).rotateX(-Math.PI / 2), seaMat);
  sea.position.set(900, 0.2, 7000);
  sea.receiveShadow = false;
  group.add(sea);

  // ---- sea of clouds (dawn): a coarse heightmap lets the layer thin out softly where
  // the mountainside rises into it instead of cutting hard lines across the slopes
  const HM = 256, hx0 = -4800, hz0 = -4200, hSpan = 11200;
  const hData = new Float32Array(HM * HM);
  for (let j = 0; j < HM; j++)
    for (let i = 0; i < HM; i++) hData[j * HM + i] = terrain.heightAt(hx0 + (i / (HM - 1)) * hSpan, hz0 + (j / (HM - 1)) * hSpan);
  // half floats are linearly filterable on every WebGL2 device (full floats need an extension)
  const hHalf = new Uint16Array(hData.length);
  for (let k = 0; k < hData.length; k++) hHalf[k] = THREE.DataUtils.toHalfFloat(hData[k]);
  const heightTex = new THREE.DataTexture(hHalf, HM, HM, THREE.RedFormat, THREE.HalfFloatType);
  heightTex.magFilter = THREE.LinearFilter;
  heightTex.minFilter = THREE.LinearFilter;
  heightTex.needsUpdate = true;
  const cloudMat = new THREE.ShaderMaterial({
    transparent: true,
    depthWrite: false,
    fog: true,
    uniforms: THREE.UniformsUtils.merge([
      THREE.UniformsLib.fog,
      {
        uTime: { value: 0 }, uColor: { value: new THREE.Color('#fff0e6') }, uShade: { value: new THREE.Color('#8a90a8') },
        uSun: { value: new THREE.Vector3() }, uOpacity: { value: 1 },
        uHeight: { value: heightTex }, uHeightBox: { value: new THREE.Vector3(hx0, hz0, hSpan) }, uLayer: { value: 150 },
      },
    ]),
    vertexShader: /* glsl */ `
      varying vec3 vWorld;
      #include <fog_pars_vertex>
      void main() {
        vec4 wp = modelMatrix * vec4(position, 1.0);
        vWorld = wp.xyz;
        vec4 mvPosition = viewMatrix * wp;
        gl_Position = projectionMatrix * mvPosition;
        #include <fog_vertex>
      }`,
    fragmentShader: /* glsl */ `
      uniform float uTime, uOpacity, uLayer; uniform vec3 uColor, uShade, uSun, uHeightBox;
      uniform sampler2D uHeight;
      varying vec3 vWorld;
      #include <fog_pars_fragment>
      float hash2(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
      float vnoise(vec2 p) { vec2 i = floor(p), f = fract(p); f = f*f*(3.0-2.0*f);
        return mix(mix(hash2(i), hash2(i+vec2(1,0)), f.x), mix(hash2(i+vec2(0,1)), hash2(i+vec2(1,1)), f.x), f.y); }
      float fbm(vec2 p) { float a = 0.5, s = 0.0; for (int i = 0; i < 6; i++) { s += a * vnoise(p); p *= 2.07; a *= 0.5; } return s; }
      void main() {
        vec2 uv = vWorld.xz / 900.0 + vec2(uTime * 0.003, uTime * 0.0015);
        float n = fbm(uv);
        float n2 = fbm(uv * 3.0 + 7.0);
        float density = smoothstep(0.32, 0.62, n * 0.8 + n2 * 0.3);
        vec2 huv = (vWorld.xz - uHeightBox.xy) / uHeightBox.z;
        float ground = texture2D(uHeight, huv).r;
        density *= smoothstep(-5.0, 45.0, uLayer - ground);
        // fake lighting: crests catch the low sun
        float crest = smoothstep(0.45, 0.9, n2);
        vec3 col = mix(uShade, uColor, 0.35 + crest * 0.65);
        gl_FragColor = vec4(col, density * uOpacity);
        #include <fog_fragment>
        #include <tonemapping_fragment>
        #include <colorspace_fragment>
      }`,
  });
  const cloudSea = new THREE.Mesh(new THREE.PlaneGeometry(30000, 30000, 1, 1).rotateX(-Math.PI / 2), cloudMat);
  cloudSea.position.set(900, 150, 3000);
  cloudSea.renderOrder = 2;
  group.add(cloudSea);

  // ---- city lights
  const city = buildCityLights(terrain);
  group.add(city);

  const rig: EnvironmentRig = {
    group,
    sky,
    skyUniforms,
    key,
    hemi,
    fog,
    city,
    sea,
    cloudSea,
    preset: PRESETS.night,
    apply(tod, scene, renderer) {
      const p = PRESETS[tod];
      rig.preset = p;
      skyUniforms.uZenith.value.set(p.zenith);
      skyUniforms.uHorizon.value.set(p.horizon);
      skyUniforms.uGlow.value.set(p.glow);
      skyUniforms.uCityGlow.value = p.cityGlow;
      skyUniforms.uStars.value = p.stars;
      skyUniforms.uClouds.value = p.clouds;
      skyUniforms.uCloudColor.value.set(p.cloudColor);
      skyUniforms.uKeyDir.value.copy(p.keyDir);
      skyUniforms.uKeyColor.value.set(p.keyColor);
      skyUniforms.uIsSun.value = tod === 'dawn' ? 1 : 0;
      key.color.set(p.keyColor);
      key.intensity = p.keyIntensity;
      hemi.color.set(p.hemiSky);
      hemi.groundColor.set(p.hemiGround);
      hemi.intensity = p.hemiIntensity;
      fog.color.set(p.fog);
      fog.density = p.fogDensity;
      scene.fog = fog;
      renderer.toneMappingExposure = p.exposure;
      seaMat.color.set(p.sea);
      (city.material as THREE.ShaderMaterial).uniforms.uIntensity.value = p.cityLights;
      city.visible = p.cityLights > 0;
      cloudSea.visible = p.seaOfClouds > 0;
      cloudMat.uniforms.uSun.value.copy(p.keyDir);
    },
    update(time, focus) {
      skyUniforms.uTime.value = time;
      sky.position.copy(focus);
      (city.material as THREE.ShaderMaterial).uniforms.uTime.value = time;
      cloudMat.uniforms.uTime.value = time;
      seaNormal.offset.set(time * 0.002, time * 0.0013);
      // keep the shadow frustum around the focus point
      key.position.copy(focus).addScaledVector(rig.preset.keyDir, 250);
      key.target.position.copy(focus);
    },
    buildEnvMap(renderer) {
      // environment for reflections: the sky plus a ring of warm lights
      const envScene = new THREE.Scene();
      const skyClone = new THREE.Mesh(sky.geometry, sky.material);
      envScene.add(skyClone);
      const lampMat = new THREE.MeshBasicMaterial({ color: new THREE.Color('#ffb070').multiplyScalar(4 * rig.preset.lampsOn + 0.2) });
      const r = rng(3);
      for (let i = 0; i < 14; i++) {
        const a = (i / 14) * Math.PI * 2 + r() * 0.3;
        const m = new THREE.Mesh(new THREE.PlaneGeometry(30, 6), lampMat);
        m.position.set(Math.cos(a) * 200, 60 + r() * 50, Math.sin(a) * 200);
        m.lookAt(0, 0, 0);
        envScene.add(m);
      }
      const ground = new THREE.Mesh(new THREE.PlaneGeometry(2000, 2000).rotateX(-Math.PI / 2), new THREE.MeshBasicMaterial({ color: new THREE.Color(rig.preset.hemiGround) }));
      ground.position.y = -20;
      envScene.add(ground);
      const pmrem = new THREE.PMREMGenerator(renderer);
      const rt = pmrem.fromScene(envScene, 0.02, 1, 12000);
      pmrem.dispose();
      return rt.texture;
    },
  };
  return rig;
}

function makeWaveNormal() {
  const W = 256;
  const c = document.createElement('canvas');
  c.width = c.height = W;
  const g = c.getContext('2d')!;
  const img = g.createImageData(W, W);
  const h = new Float32Array(W * W);
  for (let y = 0; y < W; y++)
    for (let x = 0; x < W; x++) {
      // tileable by summing periodic sines with noise phase
      const u = (x / W) * Math.PI * 2, v = (y / W) * Math.PI * 2;
      h[y * W + x] = Math.sin(u * 3 + Math.sin(v * 2) * 1.5) * 0.5 + Math.sin(v * 5 + u * 2) * 0.3 + Math.sin(u * 9 - v * 7) * 0.15;
    }
  for (let y = 0; y < W; y++)
    for (let x = 0; x < W; x++) {
      const dx = h[y * W + ((x + 1) % W)] - h[y * W + ((x - 1 + W) % W)];
      const dy = h[((y + 1) % W) * W + x] - h[((y - 1 + W) % W) * W + x];
      const o = (y * W + x) * 4;
      img.data[o] = 128 - dx * 60;
      img.data[o + 1] = 128 - dy * 60;
      img.data[o + 2] = 255;
      img.data[o + 3] = 255;
    }
  g.putImageData(img, 0, 0);
  const t = new THREE.CanvasTexture(c);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  return t;
}

/** Thousands of glowing points: streets, homes, downtown towers, harbour, traffic. */
function buildCityLights(terrain: TerrainData) {
  const r = rng(99);
  const pos: number[] = [], col: number[] = [], size: number[] = [], anim: number[] = [];
  const c = new THREE.Color();
  const push = (x: number, y: number, z: number, color: THREE.Color, s: number, a = 0) => {
    pos.push(x, y, z);
    col.push(color.r, color.g, color.b);
    size.push(s);
    anim.push(a);
  };
  const sodium = new THREE.Color('#ff9a3c'), warm = new THREE.Color('#ffd29a'), cool = new THREE.Color('#d6e6ff');
  const green = new THREE.Color('#9dffc8'), red = new THREE.Color('#ff2a1a'), neon = [new THREE.Color('#ff4fb0'), new THREE.Color('#4fd0ff'), new THREE.Color('#ffe14f')];
  const centerX = 900, centerZ = 1650;
  const ground = (x: number, z: number) => Math.max(terrain.heightAt(x, z), 0.5) + 1.5;
  // street grid (slightly rotated)
  const ang = 0.18;
  const ca = Math.cos(ang), sa = Math.sin(ang);
  for (let gx = -2400; gx <= 2600; gx += 110) {
    for (let t = -900; t <= 1100; t += 16) {
      for (const [ax, az] of [[gx, t], [t * 2.2, gx * 0.45]] as const) {
        const x = centerX + ax * ca - az * sa, z = centerZ + ax * sa + az * ca;
        if (z < 1150 || z > terrain.coastZ(x) - 15) continue;
        if (r() < 0.15) continue;
        push(x, ground(x, z), z, sodium, 2.6);
      }
    }
  }
  // homes and buildings: density falls off from the centre
  for (let k = 0; k < 26000; k++) {
    const x = centerX + (r() - 0.5) * 5200, z = 1150 + r() * 950;
    if (z > terrain.coastZ(x) - 10) continue;
    const d = Math.hypot((x - centerX) / 1.8, z - centerZ);
    if (r() > Math.exp(-d / 900) + 0.1) continue;
    const pick = r();
    c.copy(pick < 0.55 ? warm : pick < 0.85 ? cool : green).multiplyScalar(0.6 + r() * 0.6);
    const towerH = d < 500 && r() < 0.35 ? r() * 70 : 0;
    const y = ground(x, z) + towerH;
    push(x, y, z, c, 1.6 + r());
    if (towerH > 20) {
      // window column
      for (let h = 6; h < towerH; h += 4 + r() * 4) push(x + (r() - 0.5) * 6, ground(x, z) + h, z + (r() - 0.5) * 6, c, 1.4);
      if (towerH > 50) push(x, y + 3, z, red, 3, 2); // aviation light (blink)
    }
    if (d < 350 && r() < 0.04) push(x, y + 2, z, neon[Math.floor(r() * 3)], 3.2);
  }
  // coastal highway with moving traffic (anim 1 = moving along x)
  for (let x = -3000; x < 4500; x += 9) {
    const z = terrain.coastZ(x) - 40;
    push(x, 6, z, sodium, 2.4);
    if (r() < 0.35) push(x, 4.5, z + 3, new THREE.Color('#fff5e0'), 2.2, 1 + r() * 0.5);
    if (r() < 0.35) push(x, 4.5, z - 3, new THREE.Color('#ff3020'), 2.0, -1 - r() * 0.5);
  }
  // ferris wheel
  const fwX = 1350, fwZ = terrain.coastZ(1350) - 70;
  for (let i = 0; i < 64; i++) {
    const a = (i / 64) * Math.PI * 2;
    push(fwX + Math.cos(a) * 35, 45 + Math.sin(a) * 35, fwZ, neon[i % 3], 3.2, 3 + i / 64);
  }
  // ships
  for (let i = 0; i < 18; i++) {
    const x = -1500 + r() * 5000, z = terrain.coastZ(x) + 300 + r() * 2500;
    push(x, 4, z, warm, 3.2);
    push(x + 8, 6, z, red, 2.4, 2);
  }
  // antenna towers on the mountains
  for (const [x, z] of [[-900, -1500], [1700, -1300], [2600, -600]]) {
    const y = terrain.heightAt(x, z);
    for (let h = 0; h < 4; h++) push(x, y + 15 + h * 18, z, red, 3.8, 2);
  }

  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  geo.setAttribute('color', new THREE.Float32BufferAttribute(col, 3));
  geo.setAttribute('size', new THREE.Float32BufferAttribute(size, 1));
  geo.setAttribute('anim', new THREE.Float32BufferAttribute(anim, 1));
  const mat = new THREE.ShaderMaterial({
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
    uniforms: { uTime: { value: 0 }, uIntensity: { value: 1 }, uMap: { value: makeGlowTexture() }, uPixelRatio: { value: 1 } },
    vertexShader: /* glsl */ `
      attribute float size; attribute float anim; attribute vec3 color;
      uniform float uTime, uPixelRatio;
      varying vec3 vColor; varying float vFade;
      void main() {
        vec3 p = position;
        float blink = 1.0;
        if (anim >= 3.0) {
          // ferris wheel rotation
          float a = (anim - 3.0) * 6.2831 + uTime * 0.05;
          vec3 c = vec3(1350.0, 45.0, p.z);
          p = c + vec3(cos(a), sin(a), 0.0) * 35.0;
        } else if (anim >= 2.0) {
          blink = step(0.5, fract(uTime * 0.5 + p.x * 0.01));
        } else if (abs(anim) >= 1.0) {
          p.x = mod(p.x + 3000.0 + uTime * 22.0 * anim, 7500.0) - 3000.0;
        }
        vec4 mv = modelViewMatrix * vec4(p, 1.0);
        float dist = -mv.z;
        gl_PointSize = clamp(size * 900.0 / dist, 1.2, 18.0) * uPixelRatio;
        gl_Position = projectionMatrix * mv;
        vColor = color * blink;
        vFade = exp(-dist * 0.00016);
      }`,
    fragmentShader: /* glsl */ `
      uniform sampler2D uMap; uniform float uIntensity;
      varying vec3 vColor; varying float vFade;
      void main() {
        float a = texture2D(uMap, gl_PointCoord).r;
        gl_FragColor = vec4(vColor * a * uIntensity * (0.35 + vFade * 1.6), 1.0);
        #include <colorspace_fragment>
      }`,
  });
  const pts = new THREE.Points(geo, mat);
  pts.frustumCulled = false;
  pts.name = 'city';
  void fbm;
  void smoothstep;
  return pts;
}
