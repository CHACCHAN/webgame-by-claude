import * as THREE from 'three';
import type { TerrainData } from '../track/terrain';
import { rng } from '../util/math';
import { makeGlowTexture } from './textures';

export type TimeOfDay = 'night' | 'rain' | 'dawn';

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
  /** 0..1 rain intensity (wet roads, rain streaks, spray, less grip) */
  rain: number;
  /** moon/sun disc visibility */
  disc: number;
  overcast: number;
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
    rain: 0,
    disc: 1,
    overcast: 0,
  },
  rain: {
    zenith: '#05080d',
    horizon: '#1a2230',
    glow: '#ff9a50',
    cityGlow: 0.85,
    fog: '#121a26',
    fogDensity: 0.0011,
    keyColor: '#8fa3c8',
    keyIntensity: 0.5,
    keyDir: new THREE.Vector3(0.38, 0.5, 0.78).normalize(),
    hemiSky: '#37465f',
    hemiGround: '#121519',
    hemiIntensity: 0.95,
    stars: 0,
    exposure: 1.2,
    lampsOn: 1,
    cityLights: 0.8,
    sea: '#050b12',
    clouds: 1,
    cloudColor: '#1c2433',
    seaOfClouds: 0,
    rain: 1,
    disc: 0,
    overcast: 1,
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
    rain: 0,
    disc: 1,
    overcast: 0,
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
uniform vec3 uZenith, uHorizon, uGlow, uCloudColor, uKeyDir, uKeyColor, uCityDir, uGround;
uniform float uCityGlow, uStars, uTime, uClouds, uIsSun, uDisc, uOvercast;
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
  // strongest right at the horizon line, fading both upwards and below it (seen past the terrain edge)
  col += uGlow * pow(cityA, 2.5) * exp(-max(h + 0.02, 0.0) * 10.0) * smoothstep(-0.16, -0.02, h) * uCityGlow;
  // key light glow (sun at dawn) and disc (moon/sun)
  float kd = max(dot(d, uKeyDir), 0.0);
  col += uKeyColor * (pow(kd, 8.0) * 0.25 + pow(kd, 64.0) * 0.5) * (0.15 + uIsSun * 0.85);
  float disc = smoothstep(mix(0.99955, 0.9993, uIsSun), mix(0.9997, 0.9996, uIsSun), kd);
  vec3 discCol = mix(vec3(1.0, 0.97, 0.9) * 2.6, vec3(1.0, 0.85, 0.6) * 9.0, uIsSun);
  // subtle craters on the moon
  float crater = (1.0 - uIsSun) * (vnoise(d.xy * 900.0) * 0.25);
  col = mix(col, discCol * (1.0 - crater), disc * uDisc);
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
    // b * b, not pow(b, 2.0): pow of a negative base is undefined (NaN on Direct3D)
    float b = dot(d, normalize(vec3(0.35, 0.62, -0.7)));
    float band = exp(-b * b * 22.0);
    col += vec3(0.05, 0.055, 0.08) * band * smoothstep(0.45, 0.8, fbm(d.xz * 6.0 + d.y * 3.0)) * uStars;
  }
  // thin clouds
  if (h > 0.0 && uClouds > 0.0) {
    vec2 uv = d.xz / (h + 0.12) * 1.4 + vec2(uTime * 0.004, 0.0);
    float c = smoothstep(0.52 - uOvercast * 0.45, 0.85 - uOvercast * 0.3, fbm(uv));
    float lit = 0.5 + 0.5 * pow(kd, 4.0);
    col = mix(col, uCloudColor * lit, c * uClouds * smoothstep(0.0, 0.18, h));
  }
  // below the horizon the dome stands in for distant, fogged ground (past the edge of the terrain)
  col = mix(col, uGround, smoothstep(-0.004, -0.03, h));
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
  /** frees the reflection environment's render target */
  dispose(): void;
}

export function buildEnvironment(terrain: TerrainData): EnvironmentRig {
  const group = new THREE.Group();
  group.name = 'environment';

  let envRT: THREE.WebGLRenderTarget | null = null;

  // ---- sky dome
  const skyUniforms: Record<string, THREE.IUniform> = {
    uZenith: { value: new THREE.Color() },
    uHorizon: { value: new THREE.Color() },
    uGlow: { value: new THREE.Color() },
    uCloudColor: { value: new THREE.Color() },
    uKeyDir: { value: new THREE.Vector3() },
    uKeyColor: { value: new THREE.Color() },
    uCityDir: { value: new THREE.Vector3(...terrain.landform.cityGlowDir).normalize() },
    uCityGlow: { value: 1 },
    uGround: { value: new THREE.Color() },
    uStars: { value: 1 },
    uTime: { value: 0 },
    uClouds: { value: 0.4 },
    uIsSun: { value: 0 },
    uDisc: { value: 1 },
    uOvercast: { value: 0 },
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
  const seaMat = new THREE.MeshStandardMaterial({
    color: '#04101c',
    roughness: 0.12,
    metalness: 0.1,
    normalMap: seaNormal,
    normalScale: new THREE.Vector2(0.35, 0.35),
    envMapIntensity: 1.2,
  });
  const lf = terrain.landform;
  const wdef = lf.water ?? { x: 0, z: 0, w: 1, d: 1 };
  const sea = new THREE.Mesh(new THREE.PlaneGeometry(wdef.w, wdef.d).rotateX(-Math.PI / 2), seaMat);
  sea.position.set(wdef.x, (lf.waterLevel ?? -1000) + 0.2, wdef.z);
  sea.visible = lf.waterLevel !== null;
  seaNormal.repeat.set(wdef.w / 28, wdef.d / 28);
  sea.receiveShadow = false;
  group.add(sea);

  // ---- ground skirt: a fogged plane just under the lowest terrain so the sky never shows below the
  // horizon past the edge of the far terrain grid (dry and lake landscapes; the bay has its sea)
  const far = terrain.far;
  let lowest = Infinity;
  for (let k = 0; k < far.heights.length; k++) lowest = Math.min(lowest, far.heights[k]);
  const skirtMat = new THREE.MeshBasicMaterial({ color: '#000000', fog: true });
  const skirt = new THREE.Mesh(new THREE.PlaneGeometry(80000, 80000).rotateX(-Math.PI / 2), skirtMat);
  skirt.position.set(far.x0 + (far.nx * far.cell) / 2, lowest - 4, far.z0 + (far.nz * far.cell) / 2);
  skirt.visible = !lf.water || lf.water.w < 20000;
  group.add(skirt);

  // ---- sea of clouds (dawn): a coarse heightmap lets the layer thin out softly where
  // the mountainside rises into it instead of cutting hard lines across the slopes
  const HM = 256, hx0 = terrain.far.x0, hz0 = terrain.far.z0, hSpan = Math.max(terrain.far.nx, terrain.far.nz) * terrain.far.cell;
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
        uHeight: { value: heightTex }, uHeightBox: { value: new THREE.Vector3(hx0, hz0, hSpan) }, uLayer: { value: lf.cloudLevel },
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
  cloudSea.position.set(terrain.near.x0 + (terrain.near.nx * terrain.near.cell) / 2, lf.cloudLevel, terrain.near.z0 + (terrain.near.nz * terrain.near.cell) / 2);
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
      const p = { ...PRESETS[tod] };
      if (tod !== 'dawn') p.keyDir = new THREE.Vector3(...lf.moonDir).normalize();
      rig.preset = p;
      skyUniforms.uZenith.value.set(p.zenith);
      skyUniforms.uHorizon.value.set(p.horizon);
      skyUniforms.uGlow.value.set(p.glow);
      skyUniforms.uCityGlow.value = p.cityGlow * (lf.cityGlow ?? 1);
      skyUniforms.uStars.value = p.stars;
      skyUniforms.uClouds.value = p.clouds;
      skyUniforms.uCloudColor.value.set(p.cloudColor);
      skyUniforms.uKeyDir.value.copy(p.keyDir);
      skyUniforms.uKeyColor.value.set(p.keyColor);
      skyUniforms.uIsSun.value = tod === 'dawn' ? 1 : 0;
      skyUniforms.uDisc.value = p.disc;
      skyUniforms.uOvercast.value = p.overcast;
      key.color.set(p.keyColor);
      key.intensity = p.keyIntensity;
      hemi.color.set(p.hemiSky);
      hemi.groundColor.set(p.hemiGround);
      hemi.intensity = p.hemiIntensity;
      fog.color.set(p.fog);
      skirtMat.color.set(p.fog);
      skyUniforms.uGround.value.set(p.fog);
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
      envScene.traverse((o) => {
        if (o === skyClone || !(o as THREE.Mesh).isMesh) return;
        (o as THREE.Mesh).geometry.dispose();
      });
      lampMat.dispose();
      (ground.material as THREE.Material).dispose();
      envRT?.dispose();
      envRT = rt;
      return rt.texture;
    },
    dispose() {
      envRT?.dispose();
      envRT = null;
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
  const lf = terrain.landform;
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
  const water = lf.waterLevel;
  const ground = (x: number, z: number) => Math.max(terrain.heightAt(x, z), water ?? -1e9) + 1.5;
  const dry = (x: number, z: number) => water === null || terrain.heightAt(x, z) > water + 1.2;
  // keep lights off steep mountainsides
  const flat = (x: number, z: number) =>
    Math.abs(terrain.heightAt(x + 8, z) - terrain.heightAt(x - 8, z)) + Math.abs(terrain.heightAt(x, z + 8) - terrain.heightAt(x, z - 8)) < 9;

  for (const city of lf.cities) {
    const ca = Math.cos(city.angle), sa = Math.sin(city.angle);
    const inside = (ax: number, az: number) => (ax / city.rx) ** 2 + (az / city.rz) ** 2 < 1;
    const toWorld = (ax: number, az: number) => [city.x + ax * ca - az * sa, city.z + ax * sa + az * ca] as const;
    // street grid
    const span = Math.max(city.rx, city.rz);
    for (let g = -span; g <= span; g += 110) {
      for (let t = -span; t <= span; t += 16) {
        for (const [ax, az] of [[g, t], [t, g * 0.45]] as const) {
          if (!inside(ax, az) || r() < 0.15) continue;
          const [x, z] = toWorld(ax, az);
          if (!dry(x, z) || !flat(x, z)) continue;
          push(x, ground(x, z), z, sodium, 2.6);
        }
      }
    }
    // homes and buildings: density falls off from the centre
    const count = Math.round(26000 * city.density);
    for (let k = 0; k < count; k++) {
      const ax = (r() * 2 - 1) * city.rx, az = (r() * 2 - 1) * city.rz;
      if (!inside(ax, az)) continue;
      const [x, z] = toWorld(ax, az);
      if (!dry(x, z) || !flat(x, z)) continue;
      const d = Math.hypot(ax / city.rx, az / city.rz);
      if (r() > Math.exp(-d * 2.6) + 0.1) continue;
      const pick = r();
      c.copy(pick < 0.55 ? warm : pick < 0.85 ? cool : green).multiplyScalar(0.6 + r() * 0.6);
      const towerH = d < 0.2 && r() < 0.35 * city.downtown ? r() * 70 : 0;
      const y = ground(x, z) + towerH;
      push(x, y, z, c, 1.6 + r());
      if (towerH > 20) {
        for (let h = 6; h < towerH; h += 4 + r() * 4) push(x + (r() - 0.5) * 6, ground(x, z) + h, z + (r() - 0.5) * 6, c, 1.4);
        if (towerH > 50) push(x, y + 3, z, red, 3, 2);
      }
      if (d < 0.15 && r() < 0.04 * city.downtown) push(x, y + 2, z, neon[Math.floor(r() * 3)], 3.2);
    }
  }
  const coast = lf.features.coast;
  if (coast) {
    // coastal highway with moving traffic (anim ±1 = moving along x)
    for (let x = -3000; x < 4500; x += 9) {
      const z = coast(x) - 40;
      push(x, 6, z, sodium, 2.4);
      if (r() < 0.35) push(x, 4.5, z + 3, new THREE.Color('#fff5e0'), 2.2, 1 + r() * 0.5);
      if (r() < 0.35) push(x, 4.5, z - 3, new THREE.Color('#ff3020'), 2.0, -1 - r() * 0.5);
    }
    if (lf.features.ships) {
      for (let i = 0; i < 18; i++) {
        const x = -1500 + r() * 5000, z = coast(x) + 300 + r() * 2500;
        push(x, 4, z, warm, 3.2);
        push(x + 8, 6, z, red, 2.4, 2);
      }
    }
  }
  const fw = lf.features.ferrisWheel;
  if (fw) {
    for (let i = 0; i < 64; i++) push(fw[0], 45, fw[1], neon[i % 3], 3.2, 3 + i / 64);
  }
  // antenna towers and wind turbines carry blinking aviation lights
  for (const [x, z] of lf.features.towers) {
    const y = terrain.heightAt(x, z);
    for (let h = 0; h < 4; h++) push(x, y + 15 + h * 18, z, red, 3.8, 2);
  }
  for (const [x, z] of lf.features.turbines ?? []) push(x, terrain.heightAt(x, z) + 63, z, red, 3.4, 2);

  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  geo.setAttribute('color', new THREE.Float32BufferAttribute(col, 3));
  geo.setAttribute('size', new THREE.Float32BufferAttribute(size, 1));
  geo.setAttribute('anim', new THREE.Float32BufferAttribute(anim, 1));
  const mat = new THREE.ShaderMaterial({
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
    uniforms: {
      uTime: { value: 0 }, uIntensity: { value: 1 }, uMap: { value: makeGlowTexture() }, uPixelRatio: { value: 1 },
      uFerris: { value: new THREE.Vector3(fw?.[0] ?? 0, 45, fw?.[1] ?? 0) },
    },
    vertexShader: /* glsl */ `
      attribute float size; attribute float anim; attribute vec3 color;
      uniform float uTime, uPixelRatio; uniform vec3 uFerris;
      varying vec3 vColor; varying float vFade;
      void main() {
        vec3 p = position;
        float blink = 1.0;
        if (anim >= 3.0) {
          // ferris wheel rotation
          float a = (anim - 3.0) * 6.2831 + uTime * 0.05;
          p = uFerris + vec3(cos(a), sin(a), 0.0) * 35.0;
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
  return pts;
}
