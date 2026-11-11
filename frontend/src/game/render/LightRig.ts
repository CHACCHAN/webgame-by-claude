import * as THREE from 'three';
import type { PMREMGenerator } from 'three/webgpu';

/** a car's headlights as a real light (the pooled spots take these values when they are a car's) */
export const HEADLIGHT = { color: '#fff1dc', intensity: 260, distance: 140, angle: 0.48, penumbra: 0.55, decay: 1.4 };

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
 *  - `lamps`: the street lamps nearest the camera (`Game.updateLampLights`);
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
  readonly lamps: THREE.PointLight[] = [];
  readonly vending = new THREE.PointLight('#e8f4ff', 0, 14, 1.6);
  private readonly spots: THREE.SpotLight[] = [];
  /** the first spot is the garage's light from above (set its values on `showroom`), not a car's headlights */
  showroomOn = false;
  /** the reflection environment and what draws it (`Environment.buildEnvMap`) */
  envTarget: THREE.RenderTarget | null = null;
  pmrem: PMREMGenerator | null = null;

  constructor(q: { shadows: boolean; shadowMapSize: number; headlightShadows: boolean }) {
    this.group.name = 'lights';
    const key = this.key;
    key.castShadow = q.shadows;
    key.shadow.mapSize.set(q.shadowMapSize, q.shadowMapSize);
    key.shadow.camera.left = -60;
    key.shadow.camera.right = 60;
    key.shadow.camera.top = 60;
    key.shadow.camera.bottom = -60;
    key.shadow.camera.near = 1;
    key.shadow.camera.far = 600;
    key.shadow.bias = -0.0004;
    key.shadow.normalBias = 0.04;
    this.group.add(key, key.target, this.hemi);
    for (let i = 0; i < 6; i++) {
      const l = new THREE.PointLight('#ffa850', 0, 42, 1.7);
      this.lamps.push(l);
      this.group.add(l);
    }
    this.group.add(this.vending);
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
