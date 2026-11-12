import * as THREE from 'three';
import type { PMREMGenerator } from 'three/webgpu';
import { FarShade } from './farShade';
import { LampField } from './lampField';

/** a car's headlights as a real light (the pooled spots take these values when they are a car's) */
export const HEADLIGHT = { color: '#fff1dc', intensity: 260, distance: 140, angle: 0.48, penumbra: 0.55, decay: 1.4 };

/**
 * The sun's / moon's shadow map: half the side of the square it covers (m), by the map's size. A texel stays under
 * 8 cm on the two upper settings and 12 cm on `medium` (what it was when the square was 120 m for all of them and
 * centred on the camera, half of it behind the viewer).
 */
export const shadowHalfFor = (mapSize: number) => (mapSize >= 4096 ? 100 : mapSize >= 2048 ? 80 : 60);
/** how far ahead of the camera the square's middle lies, as a share of its half side */
const SHADOW_AHEAD = 0.55;
/** the light stands this far (m) from the square's middle, towards the sun / moon */
const KEY_DISTANCE = 250;

const _f = new THREE.Vector3();

/** Something with headlights: fills where the light starts and what it is aimed at (world), returns its intensity (0 = dark). */
export interface BeamSource {
  headlight(position: THREE.Vector3, target: THREE.Vector3): number;
}

/**
 * Every light of the game, made once and never added to, taken from or moved within the scene graph afterwards.
 *
 * The renderer builds each material's shader for the set of lights it is drawn under (their ids, in the order the
 * scene graph gives them, and whether each throws shadows), for the scene's fog object and for the texture that is
 * its reflection environment. Whenever one of those changed — a car with its headlights came or went, the garage's
 * light was added, another course brought its own sun and fog, another time of day a new environment map — every
 * material in view was built again in one frame: 1.2–2.6 s of standing picture at each change of weather, each car
 * shown in the garage, each race start (measured, 11-11). So the set is fixed:
 *  - `key`, `hemi`, `fog`: the sky's light and the haze of whatever course is shown (`Environment` sets their values);
 *    the key's shadow map follows the camera (`aimKey`), and what lies beyond it is `farShade`'s (`render/keyShadow.ts`);
 *  - `lamps`: every street lamp of the course that is shown, as one light (`render/lampField.ts`);
 *  - `vending`: the vending machine's glow (the mountain courses);
 *  - three spots: the first throws shadows (when the quality has headlight shadows) and is the followed car's
 *    headlights, or the light from above in the garage and the waiting room (`showroom`); the others are the
 *    headlights of the cars next in line (`beams`). A car beyond that has its lamps and cones, but lights nothing;
 *  - `envTarget`: the one reflection environment, drawn into again when the time of day or the course changes.
 * A light that is not needed stays in the scene with intensity 0.
 */
export class LightRig {
  readonly group = new THREE.Group();
  readonly key = new THREE.DirectionalLight('#ffffff', 1);
  readonly hemi = new THREE.HemisphereLight('#ffffff', '#000000', 1);
  readonly fog = new THREE.FogExp2('#000000', 0.0005);
  readonly lamps = new LampField();
  readonly vending = new THREE.PointLight('#e8f4ff', 0, 14, 1.6);
  private readonly spots: THREE.SpotLight[] = [];
  /** the first spot is the garage's light from above (set its values on `showroom`), not a car's headlights */
  showroomOn = false;
  /** the shade beyond the shadow map, and of the land (the course's baked field: `Game.applyTimeOfDay` shows it) */
  readonly farShade = new FarShade();
  /** where the key light's shadow map lies: its middle, its two axes, half its side (the shader fades it out at the edge) */
  readonly keyMap = { at: new THREE.Vector3(), x: new THREE.Vector3(1, 0, 0), y: new THREE.Vector3(0, 0, 1), half: 60 };
  /** the reflection environment and what draws it (`Environment.buildEnvMap`) */
  envTarget: THREE.RenderTarget | null = null;
  pmrem: PMREMGenerator | null = null;

  constructor(q: { shadows: boolean; shadowMapSize: number; headlightShadows: boolean }) {
    this.group.name = 'lights';
    const key = this.key;
    key.castShadow = q.shadows;
    key.shadow.mapSize.set(q.shadowMapSize, q.shadowMapSize);
    const half = (this.keyMap.half = shadowHalfFor(q.shadowMapSize));
    key.shadow.camera.left = -half;
    key.shadow.camera.right = half;
    key.shadow.camera.top = half;
    key.shadow.camera.bottom = -half;
    key.shadow.camera.near = 1;
    key.shadow.camera.far = 2 * KEY_DISTANCE + 100;
    key.shadow.bias = -0.0004;
    key.shadow.normalBias = 0.04;
    this.group.add(key, key.target, this.hemi);
    this.group.add(this.lamps, this.vending);
    for (let i = 0; i < 3; i++) {
      const spot = new THREE.SpotLight(HEADLIGHT.color, 0, HEADLIGHT.distance, HEADLIGHT.angle, HEADLIGHT.penumbra, HEADLIGHT.decay);
      spot.castShadow = i === 0 && q.headlightShadows;
      spot.shadow.mapSize.set(1024, 1024);
      spot.shadow.camera.near = 0.5;
      spot.shadow.camera.far = 140;
      spot.shadow.bias = -0.0006;
      this.spots.push(spot);
      this.group.add(spot, spot.target);
    }
  }

  /**
   * Per frame: puts the key light, and with it its shadow map, where the camera looks. The square's middle lies
   * ahead of the eye (centred on it, half the map was spent behind the viewer and shadows ended 60 m ahead), and
   * moves in whole texels: a map that slides by fractions of one makes every shadow's edge crawl.
   * `toLight`: the unit vector towards the sun / moon.
   */
  aimKey(eye: THREE.Vector3, forward: THREE.Vector3, toLight: THREE.Vector3) {
    const { at, x, y, half } = this.keyMap;
    // the map's own axes: those of a camera that looks along the light with +Y up (as the shadow camera does)
    x.set(toLight.z, 0, -toLight.x);
    if (x.lengthSq() < 1e-6) x.set(1, 0, 0);
    x.normalize();
    y.crossVectors(toLight, x).normalize();
    _f.set(forward.x, 0, forward.z);
    // (a camera that looks straight down has no ahead)
    const flat = _f.length();
    at.copy(eye);
    if (flat > 1e-3) at.addScaledVector(_f, (Math.min(1, flat * 2) * SHADOW_AHEAD * half) / flat);
    const texel = (2 * half) / this.key.shadow.mapSize.x;
    const u = at.dot(x), v = at.dot(y);
    at.addScaledVector(x, Math.round(u / texel) * texel - u).addScaledVector(y, Math.round(v / texel) * texel - v);
    this.key.target.position.copy(at);
    this.key.position.copy(at).addScaledVector(toLight, KEY_DISTANCE);
  }

  /** the spot that throws shadows, as the garage's light from above while `showroomOn` */
  get showroom() {
    return this.spots[0];
  }

  /**
   * Per frame: the cars whose headlights light the road, the one the camera follows first (it gets the spot that
   * throws shadows, unless the showroom has it).
   */
  beams(sources: readonly (BeamSource | null | undefined)[]) {
    let k = this.showroomOn ? 1 : 0;
    for (const src of sources) {
      if (k >= this.spots.length) break;
      if (!src) continue;
      const spot = this.spots[k];
      const intensity = src.headlight(spot.position, spot.target.position);
      if (!(intensity > 0)) continue;
      spot.color.set(HEADLIGHT.color);
      spot.intensity = intensity;
      spot.distance = HEADLIGHT.distance;
      spot.angle = HEADLIGHT.angle;
      spot.penumbra = HEADLIGHT.penumbra;
      spot.decay = HEADLIGHT.decay;
      k++;
    }
    for (; k < this.spots.length; k++) this.spots[k].intensity = 0;
    // a spot that lights nothing does not draw its shadow map either
    const first = this.spots[0];
    first.shadow.autoUpdate = first.intensity > 0;
  }
}
