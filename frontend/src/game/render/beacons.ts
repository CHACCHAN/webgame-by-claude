import * as THREE from 'three';
import { SpriteNodeMaterial } from 'three/webgpu';
import { cameraPosition, cameraProjectionMatrix, clamp, exp, instancedBufferAttribute, max, modelViewMatrix, uniform, uv, vec3, vec4 } from 'three/tsl';
import type { Float, Vec3 } from './tslNoise';

/**
 * The red obstruction lights of tall things (a wind turbine's nacelle carries two): what is seen of such a lamp by
 * night is its lens, 0.3 m across in the model, and the glare around it, which is made in the eye and in a camera's
 * lens and so has a size on the screen, not in the world. One camera-facing quad per lamp (no light: the game's set
 * of lights is fixed), a hot point with a tight soft halo, between `MIN_PX` and `MAX_PX` across whatever the
 * distance: near, it does not grow into a ball, and two kilometres off it is still a point (the bloom adds the rest).
 * It used to be one of the far lights (`Environment.buildCityLights`): up to 18 px across with a wide glow, 1–4 m
 * of red ball on a turbine a hundred metres away, switched on and off like a blinker, every turbine at its own time.
 */

/** flashes a minute: medium-intensity red obstruction lights flash 20–60 times a minute, a farm's all together */
export const BEACON_RATE = 30;
/** the halo's width in metres where that lies between the two limits, and the limits in pixels of a 1080-line screen */
const HALO = 1.3, MIN_PX = 6, MAX_PX = 12;
/** the light at the middle of the point (linear, before exposure; much more and the tone mapping turns the red orange) */
const GAIN = 3.2;

const smooth = (t: number) => {
  const x = Math.min(1, Math.max(0, t));
  return x * x * (3 - 2 * x);
};

/**
 * A flash over its period, 0…1: up in under half a second, held, down more slowly (a lamp of this kind is faded by
 * its driver, it is not a strobe), dark for the rest.
 */
export function beaconPulse(time: number) {
  const ph = ((time * BEACON_RATE) / 60) % 1;
  return smooth(ph / 0.22) * (1 - smooth((ph - 0.36) / 0.34));
}

export interface Beacons {
  /** null when there is no lamp (an object without instances must not reach the scene) */
  object: THREE.Object3D | null;
  /** how brightly they shine now: the night's share × the flash */
  level: { value: number };
}

export function buildBeacons(points: THREE.Vector3[], colour = '#ff1a0a'): Beacons {
  const level = uniform(0);
  if (!points.length) return { object: null, level };
  const pos = new Float32Array(points.length * 3);
  points.forEach((p, k) => p.toArray(pos, k * 3));
  const aPos = instancedBufferAttribute(new THREE.InstancedBufferAttribute(pos, 3), 'vec3') as unknown as Vec3;
  const mat = new SpriteNodeMaterial({ transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, fog: false });
  // a hand's width towards the camera: the lens the glare belongs to must not hide its middle, the nacelle still does
  const p = aPos.add(cameraPosition.sub(aPos).normalize().mul(0.3));
  const dist = modelViewMatrix.mul(vec4(p, 1)).z.negate();
  // 1 / tan(half the vertical field of view)
  const projY = (cameraProjectionMatrix as unknown as Float[][])[1][1];
  mat.positionNode = p;
  mat.sizeAttenuation = false;
  const px = clamp(projY.mul(HALO * 540).div(max(dist, 1)), MIN_PX, MAX_PX);
  mat.scaleNode = px.div(1080).mul(2).div(projY);
  // one bell of the distance from the middle (no power of anything: nothing to clamp), brought to nothing at the
  // quad's edge: half as bright a third of the way out, so the point is 2 px wide at the smallest size and 4 px at
  // the largest (a narrower one fell between the pixels at 1.5 km and was not there at all)
  const d = uv().sub(0.5).length().mul(2);
  const shape = exp(d.mul(d).mul(-5.5)).mul(d.oneMinus().saturate());
  // the air between takes a little of it; near, where the lit lens itself is seen under the glare, the glare is
  // a third (the two together turned from red to a pale orange in the tone mapping)
  const fade = exp(dist.mul(-0.00016)).mul(0.8).add(0.2);
  const near = dist.sub(40).div(200).saturate().mul(0.65).add(0.35);
  mat.colorNode = vec3(...new THREE.Color(colour).toArray()).mul(shape).mul(level).mul(GAIN).mul(fade).mul(near);
  const sprite = new THREE.Sprite(mat as unknown as THREE.SpriteMaterial);
  sprite.count = points.length;
  sprite.frustumCulled = false;
  sprite.name = 'beacons';
  return { object: sprite, level };
}
