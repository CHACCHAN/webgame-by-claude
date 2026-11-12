import * as THREE from 'three';
import { DAWN_SUN, dawnSun } from '../track/landforms';
import { MeshBasicNodeMaterial, PMREMGenerator, SpriteNodeMaterial } from 'three/webgpu';
import {
  Fn, abs, cameraProjectionMatrix, clamp, cos, dot, exp, float, floor, fract, instancedBufferAttribute, max, mix, mod, modelViewMatrix, normalize,
  positionLocal, positionWorld, pow, select, sin, smoothstep, step, texture, uniform, uv, vec2, vec3, vec4,
} from 'three/tsl';
import type { GameRenderer } from './RenderHost';
import { fbm, hash3, vnoise, type Float, type Vec3 } from './tslNoise';
import type { TerrainData } from '../track/terrain';
import { rng } from '../util/math';
import { setGrade, type Grade } from './grade';
import { makeGlowTexture } from './textures';
import type { LightRig } from './LightRig';

export type TimeOfDay = 'night' | 'rain' | 'dawn';

interface Preset {
  zenith: string;
  horizon: string;
  glow: string;
  cityGlow: number;
  fog: string;
  fogDensity: number;
  /** how much the air scatters the lamps' and headlights' light towards the eye, per metre (render/volumetricLights.ts) */
  haze: number;
  keyColor: string;
  keyIntensity: number;
  keyDir: THREE.Vector3;
  hemiSky: string;
  hemiGround: string;
  hemiIntensity: number;
  stars: number;
  exposure: number;
  /** the look over the tone-mapped picture (render/grade.ts) */
  grade: Grade;
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
    haze: 0.005,
    keyColor: '#a9bfff',
    keyIntensity: 1.5,
    keyDir: new THREE.Vector3(0.38, 0.5, 0.78).normalize(),
    hemiSky: '#3c5584',
    hemiGround: '#141820',
    hemiIntensity: 1.15,
    stars: 1,
    exposure: 1.15,
    grade: { contrast: 1.32, saturation: 1.12, shadows: '#00030a', highlights: '#0a0500' },
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
    haze: 0.008,
    keyColor: '#8fa3c8',
    keyIntensity: 0.5,
    keyDir: new THREE.Vector3(0.38, 0.5, 0.78).normalize(),
    hemiSky: '#37465f',
    hemiGround: '#121519',
    hemiIntensity: 0.95,
    stars: 0,
    exposure: 1.2,
    grade: { contrast: 1.3, saturation: 1.08, shadows: '#00040a', highlights: '#080400' },
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
    haze: 0.003,
    keyColor: '#ffbf80',
    keyIntensity: 2.6,
    keyDir: new THREE.Vector3(...DAWN_SUN).normalize(),
    hemiSky: '#9cb6d6',
    hemiGround: '#3d3427',
    hemiIntensity: 0.9,
    stars: 0,
    exposure: 0.95,
    grade: { contrast: 1.25, saturation: 1.1, shadows: '#000308', highlights: '#0a0600' },
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

const NO_AHEAD = new THREE.Vector3();

/** a uniform the rig sets by `.value` */
type U<T> = { value: T };
interface SkyUniforms {
  uZenith: U<THREE.Color>; uHorizon: U<THREE.Color>; uGlow: U<THREE.Color>; uCloudColor: U<THREE.Color>; uKeyDir: U<THREE.Vector3>;
  uKeyColor: U<THREE.Color>; uCityDir: U<THREE.Vector3>; uGround: U<THREE.Color>;
  uCityGlow: U<number>; uStars: U<number>; uTime: U<number>; uClouds: U<number>; uIsSun: U<number>; uDisc: U<number>; uOvercast: U<number>;
}

/** The sky dome: gradient, the city's glow on the horizon, moon or sun, stars and the milky band, thin clouds. */
function skyMaterial(cityDir: THREE.Vector3) {
  const u = {
    uZenith: uniform(new THREE.Color()), uHorizon: uniform(new THREE.Color()), uGlow: uniform(new THREE.Color()),
    uCloudColor: uniform(new THREE.Color()), uKeyDir: uniform(new THREE.Vector3(0, 1, 0)), uKeyColor: uniform(new THREE.Color()),
    uCityDir: uniform(cityDir), uGround: uniform(new THREE.Color()),
    uCityGlow: uniform(1), uStars: uniform(1), uTime: uniform(0), uClouds: uniform(0.4), uIsSun: uniform(0), uDisc: uniform(1), uOvercast: uniform(0),
  };
  const colour = Fn(() => {
    const d = normalize(positionLocal);
    const h = d.y;
    const col = mix(u.uHorizon, u.uZenith, pow(clamp(h, 0, 1), 0.42)).toVar();
    col.assign(mix(col, u.uHorizon.mul(0.55), smoothstep(0, -0.25, h)));
    // light pollution from the city below: strongest right at the horizon line, fading both upwards and below it
    // (seen past the terrain edge)
    const flatDir = normalize(vec3(d.x, 0, d.z).add(1e-5));
    const cityA = max(dot(flatDir, u.uCityDir), 0);
    col.addAssign(u.uGlow.mul(pow(cityA, 2.5)).mul(exp(max(h.add(0.02), 0).mul(-10))).mul(smoothstep(-0.16, -0.02, h)).mul(u.uCityGlow));
    // key light glow (sun at dawn) and disc (moon/sun)
    const kd = max(dot(d, u.uKeyDir), 0);
    col.addAssign(u.uKeyColor.mul(pow(kd, 8).mul(0.25).add(pow(kd, 64).mul(0.5))).mul(u.uIsSun.mul(0.85).add(0.15)));
    const disc = smoothstep(mix(0.99955, 0.9993, u.uIsSun), mix(0.9997, 0.9996, u.uIsSun), kd);
    const discCol = mix(vec3(1, 0.97, 0.9).mul(2.6), vec3(1, 0.85, 0.6).mul(9), u.uIsSun);
    // subtle craters on the moon
    const crater = float(1).sub(u.uIsSun).mul(vnoise(d.xy.mul(900)).mul(0.25));
    col.assign(mix(col, discCol.mul(float(1).sub(crater)), disc.mul(u.uDisc)));
    // stars (above the horizon): one in ~70 cells of a 320-unit grid on the dome
    const above = step(0, h);
    const sp = d.mul(320);
    const r = hash3(floor(sp));
    const f = fract(sp).sub(0.5);
    const tw = sin(u.uTime.mul(r.mul(6).add(1.5)).add(r.mul(100))).mul(0.35).add(0.65);
    const star = smoothstep(0.25, 0, f.length()).mul(max(r.sub(0.985), 0).div(0.015));
    col.addAssign(vec3(r.mul(0.2).add(0.8), 0.85, 1).mul(star).mul(tw).mul(1.6).mul(u.uStars).mul(smoothstep(0, 0.25, h)).mul(above));
    // faint milky band
    const bandDot = dot(d, normalize(vec3(0.35, 0.62, -0.7)));
    const band = exp(bandDot.mul(bandDot).mul(-22));
    col.addAssign(vec3(0.05, 0.055, 0.08).mul(band).mul(smoothstep(0.45, 0.8, fbm(d.xz.mul(6).add(d.y.mul(3)), 5, 2.03))).mul(u.uStars).mul(above));
    // thin clouds
    const cuv = d.xz.div(max(h, 0).add(0.12)).mul(1.4).add(vec2(u.uTime.mul(0.004), 0));
    const c = smoothstep(u.uOvercast.mul(-0.45).add(0.52), u.uOvercast.mul(-0.3).add(0.85), fbm(cuv, 5, 2.03));
    const lit = pow(kd, 4).mul(0.5).add(0.5);
    col.assign(mix(col, u.uCloudColor.mul(lit), c.mul(u.uClouds).mul(smoothstep(0, 0.18, h)).mul(above)));
    // below the horizon the dome stands in for distant, fogged ground (past the edge of the terrain)
    col.assign(mix(col, u.uGround, smoothstep(-0.004, -0.03, h)));
    return vec4(col, 1);
  });
  const mat = new MeshBasicNodeMaterial({ side: THREE.BackSide, depthWrite: false, depthTest: false, fog: false });
  mat.colorNode = colour();
  return { mat, uniforms: u as SkyUniforms };
}

export interface EnvironmentRig {
  group: THREE.Group;
  sky: THREE.Mesh;
  skyUniforms: SkyUniforms;
  key: THREE.DirectionalLight;
  hemi: THREE.HemisphereLight;
  fog: THREE.FogExp2;
  city: THREE.Object3D;
  sea: THREE.Mesh;
  cloudSea: THREE.Mesh;
  preset: Preset;
  apply(tod: TimeOfDay, scene: THREE.Scene, renderer: GameRenderer): void;
  /** `ahead`: where the camera at `focus` looks (the shadow map is laid out in front of it) */
  update(time: number, focus: THREE.Vector3, ahead?: THREE.Vector3): void;
  /** draws the reflection environment of the time of day last applied into the game's one target, and returns it */
  buildEnvMap(renderer: GameRenderer): THREE.Texture;
  /** frees what the reflection environment was drawn from */
  dispose(): void;
}

export function buildEnvironment(terrain: TerrainData, lights: LightRig): EnvironmentRig {
  const group = new THREE.Group();
  group.name = 'environment';

  // what the reflection environment is drawn from (made when first needed, then kept)
  let envScene: { scene: THREE.Scene; lampMat: THREE.MeshBasicMaterial; groundMat: THREE.MeshBasicMaterial } | null = null;

  // ---- sky dome (drawn first and without depth: everything else covers it)
  const skyParts = skyMaterial(new THREE.Vector3(...terrain.landform.cityGlowDir).normalize());
  const skyUniforms = skyParts.uniforms;
  const sky = new THREE.Mesh(new THREE.SphereGeometry(9000, 48, 24), skyParts.mat);
  sky.frustumCulled = false;
  sky.renderOrder = -10;
  group.add(sky);

  // ---- lights and haze: the game's one set (render/LightRig.ts), given this course's values by `apply`
  const { key, hemi, fog } = lights;

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
  const cloudU = {
    uTime: uniform(0), uColor: uniform(new THREE.Color('#fff0e6')), uShade: uniform(new THREE.Color('#8a90a8')), uOpacity: uniform(1),
    uHeightBox: uniform(new THREE.Vector3(hx0, hz0, hSpan)), uLayer: uniform(lf.cloudLevel),
  };
  const cloudMat = new MeshBasicNodeMaterial({ transparent: true, depthWrite: false, fog: true });
  // a wide soft layer: nothing in it for the upscaler to keep from the current frame (RenderHost `surfaceReactive`)
  cloudMat.userData.reactive = 0;
  {
    const wp = positionWorld;
    const cuv = wp.xz.div(900).add(vec2(cloudU.uTime.mul(0.003), cloudU.uTime.mul(0.0015)));
    const n = fbm(cuv, 6, 2.07);
    const n2 = fbm(cuv.mul(3).add(7), 6, 2.07);
    const huv = wp.xz.sub(cloudU.uHeightBox.xy).div(cloudU.uHeightBox.z);
    const ground = texture(heightTex, huv).r;
    // thins out where the mountainside rises into the layer
    const density = smoothstep(0.32, 0.62, n.mul(0.8).add(n2.mul(0.3))).mul(smoothstep(-5, 45, cloudU.uLayer.sub(ground)));
    // fake lighting: crests catch the low sun
    const crest = smoothstep(0.45, 0.9, n2);
    cloudMat.colorNode = mix(cloudU.uShade, cloudU.uColor, crest.mul(0.65).add(0.35));
    cloudMat.opacityNode = density.mul(cloudU.uOpacity);
  }
  const cloudSea = new THREE.Mesh(new THREE.PlaneGeometry(30000, 30000, 1, 1).rotateX(-Math.PI / 2), cloudMat);
  cloudSea.position.set(terrain.near.x0 + (terrain.near.nx * terrain.near.cell) / 2, lf.cloudLevel, terrain.near.z0 + (terrain.near.nz * terrain.near.cell) / 2);
  cloudSea.renderOrder = 2;
  group.add(cloudSea);

  // ---- city lights
  const cityLights = buildCityLights(terrain);
  const city = cityLights.object;
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
      p.keyDir = new THREE.Vector3(...(tod === 'dawn' ? dawnSun(lf) : lf.moonDir)).normalize();
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
      setGrade(p.grade);
      seaMat.color.set(p.sea);
      cityLights.uniforms.uIntensity.value = p.cityLights;
      city.visible = p.cityLights > 0;
      cloudSea.visible = p.seaOfClouds > 0;
    },
    update(time, focus, ahead = NO_AHEAD) {
      skyUniforms.uTime.value = time;
      sky.position.copy(focus);
      cityLights.uniforms.uTime.value = time;
      cloudU.uTime.value = time;
      seaNormal.offset.set(time * 0.002, time * 0.0013);
      // the shadow map goes with the camera
      lights.aimKey(focus, ahead, rig.preset.keyDir);
    },
    buildEnvMap(renderer) {
      // environment for reflections: the sky plus a ring of warm lights, drawn into the game's one target (the
      // texture stays the same object: a new one would have every material's shader built again)
      if (!envScene) {
        const scene = new THREE.Scene();
        const skyClone = new THREE.Mesh(sky.geometry, sky.material);
        // (a tenth of the dome's size: on the WebGL 2 backend the generator's camera keeps its own far plane, 2 km,
        // whatever is asked, and the sky was cut out of the reflections there; the dome's colour is by direction only)
        skyClone.scale.setScalar(0.1);
        scene.add(skyClone);
        const lampMat = new THREE.MeshBasicMaterial();
        const r = rng(3);
        for (let i = 0; i < 14; i++) {
          const a = (i / 14) * Math.PI * 2 + r() * 0.3;
          const m = new THREE.Mesh(new THREE.PlaneGeometry(30, 6), lampMat);
          m.position.set(Math.cos(a) * 200, 60 + r() * 50, Math.sin(a) * 200);
          m.lookAt(0, 0, 0);
          scene.add(m);
        }
        const groundMat = new THREE.MeshBasicMaterial();
        const ground = new THREE.Mesh(new THREE.PlaneGeometry(2000, 2000).rotateX(-Math.PI / 2), groundMat);
        ground.position.y = -20;
        scene.add(ground);
        envScene = { scene, lampMat, groundMat };
      }
      envScene.lampMat.color.set('#ffb070').multiplyScalar(4 * rig.preset.lampsOn + 0.2);
      envScene.groundMat.color.set(rig.preset.hemiGround);
      lights.pmrem ??= new PMREMGenerator(renderer);
      lights.envTarget = lights.pmrem.fromScene(envScene.scene, 0.02, 1, 12000, lights.envTarget ? { renderTarget: lights.envTarget } : {});
      return lights.envTarget.texture;
    },
    dispose() {
      if (!envScene) return;
      envScene.scene.traverse((o) => {
        const m = o as THREE.Mesh;
        // (the sky's own geometry and material go with the course's group)
        if (m.isMesh && m.geometry !== sky.geometry) m.geometry.dispose();
      });
      envScene.lampMat.dispose();
      envScene.groundMat.dispose();
      envScene = null;
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
  // antenna towers carry blinking aviation lights (the wind turbines' are their own: render/beacons.ts)
  for (const [x, z] of lf.features.towers) {
    const y = terrain.heightAt(x, z);
    for (let h = 0; h < 4; h++) push(x, y + 15 + h * 18, z, red, 3.8, 2);
  }

  // one camera-facing quad per light (WebGPU has no sized points): the position, colour, size and animation kind
  // of each are per-instance attributes
  const n = size.length;
  const aPos = instancedBufferAttribute(new THREE.InstancedBufferAttribute(new Float32Array(pos), 3), 'vec3') as unknown as Vec3;
  const aCol = instancedBufferAttribute(new THREE.InstancedBufferAttribute(new Float32Array(col), 3), 'vec3') as unknown as Vec3;
  const aSize = instancedBufferAttribute(new THREE.InstancedBufferAttribute(new Float32Array(size), 1), 'float') as unknown as Float;
  const aAnim = instancedBufferAttribute(new THREE.InstancedBufferAttribute(new Float32Array(anim), 1), 'float') as unknown as Float;
  const uniforms = { uTime: uniform(0), uIntensity: uniform(1), uFerris: uniform(new THREE.Vector3(fw?.[0] ?? 0, 45, fw?.[1] ?? 0)) };
  const glow = makeGlowTexture();
  const mat = new SpriteNodeMaterial({ transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, fog: false });
  // ferris wheel gondolas go round (anim ≥ 3), traffic runs along x (|anim| ≥ 1)
  const wheelA = aAnim.sub(3).mul(6.2831).add(uniforms.uTime.mul(0.05));
  const onWheel = uniforms.uFerris.add(vec3(cos(wheelA), sin(wheelA), 0).mul(35));
  const moving = vec3(mod(aPos.x.add(3000).add(uniforms.uTime.mul(22).mul(aAnim)), 7500).sub(3000), aPos.y, aPos.z);
  const isTraffic = abs(aAnim).greaterThanEqual(1).and(aAnim.lessThan(2));
  const p = select(aAnim.greaterThanEqual(3), onWheel, select(isTraffic, moving, aPos));
  // aviation lights blink (2 ≤ anim < 3)
  const blink = select(aAnim.greaterThanEqual(2).and(aAnim.lessThan(3)), step(0.5, fract(uniforms.uTime.mul(0.5).add(aPos.x.mul(0.01)))), 1);
  const dist = modelViewMatrix.mul(vec4(p, 1)).z.negate();
  // 1 / tan(half the vertical field of view)
  const projY = (cameraProjectionMatrix as unknown as Float[][])[1][1];
  mat.positionNode = p;
  // sized in pixels of a 1080-line screen (1.2–18 px), whatever the distance and the drawing resolution
  mat.sizeAttenuation = false;
  mat.scaleNode = clamp(aSize.mul(900).div(max(dist, 1)), 1.2, 18).div(1080).mul(2).div(projY);
  const fade = exp(dist.mul(-0.00016));
  mat.colorNode = aCol.mul(blink).mul(texture(glow, uv()).r).mul(uniforms.uIntensity).mul(fade.mul(1.6).add(0.35));
  const pts = new THREE.Sprite(mat as unknown as THREE.SpriteMaterial);
  pts.count = n;
  pts.frustumCulled = false;
  pts.name = 'city';
  return { object: pts, uniforms };
}
