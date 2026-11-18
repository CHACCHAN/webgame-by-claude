import * as THREE from 'three';
import { DirectionalLightNode, SpotLightNode, type NodeBuilder, type Renderer } from 'three/webgpu';
import { BRDF_GGX, clearcoatNormalView, clearcoatRoughness, float, max, renderGroup, uniform, vec3 } from 'three/tsl';

type N = any; // eslint-disable-line @typescript-eslint/no-explicit-any

/**
 * How a light of the rig shows in a car's clear coat and glass (the materials with `userData.lampImage`,
 * `carSurface.ts`).
 *
 * three.js' lights are points without a size, and a coat is as smooth as the renderer lets a surface be: the
 * highlight was a pixel or two of enormous brightness, which the bloom made into a white ball on the rear window
 * (the moon's, as bright as the sun's: the moonlight here is a film's, the moon in the sky is not) and which was
 * there in one frame and gone in the next on a curved panel. A real source has a size, and its highlight is as
 * wide as the source is seen from the panel and so much fainter. So for these materials the coat's highlight is
 * drawn here: as wide as the roughness `size` makes it, and `gain` of it (the moon: next to nothing). The paint under
 * the coat, and every other material, get the light as three.js gives it.
 */
export interface CoatGlint {
  size: number;
  gain: number;
}

/** the sun or moon */
export class KeyLight extends THREE.DirectionalLight {
  coat: CoatGlint = { size: 0.08, gain: 1 };
}

/** a car's headlights, or the light from above in the garage */
export class BeamLight extends THREE.SpotLight {
  coat: CoatGlint = { size: 0.12, gain: 0.6 };
}

interface Direct {
  lightDirection: N;
  lightColor: N;
}
interface Model {
  clearcoat?: boolean;
  clearcoatSpecularDirect: N;
}

const uniforms = new WeakMap<object, { size: N; gain: N }>();

/** the light without its highlight in the coat (`plain`: three.js' own set-up, which leaves its direction and colour in `seen`), then ours */
function softGlint(builder: NodeBuilder, light: { coat: CoatGlint }, plain: () => void, seen: () => Direct | null) {
  const model = (builder.context as unknown as { lightingModel: Model }).lightingModel;
  if (builder.material.userData.lampImage !== true || model.clearcoat !== true) return plain();
  // (the lighting model reads the flag while the light's nodes are made: off for this light only)
  model.clearcoat = false;
  plain();
  model.clearcoat = true;
  const direct = seen();
  if (!direct) return;
  let u = uniforms.get(light);
  if (!u) uniforms.set(light, (u = { size: uniform(0).setGroup(renderGroup).onRenderUpdate(() => light.coat.size), gain: uniform(0).setGroup(renderGroup).onRenderUpdate(() => light.coat.gain) }));
  const { size, gain } = u;
  const { lightDirection, lightColor } = direct;
  const facing: N = (clearcoatNormalView as N).dot(lightDirection).clamp();
  const lobe: N = (BRDF_GGX as N)({ lightDirection, f0: vec3(0.04), f90: float(1), roughness: max(clearcoatRoughness, size), normalView: clearcoatNormalView });
  model.clearcoatSpecularDirect.addAssign(lightColor.mul(facing).mul(lobe).mul(gain));
}

class KeyLightNode extends DirectionalLightNode {
  static get type() {
    return 'KeyLightNode';
  }
  private seen: Direct | null = null;
  override setupDirect(builder: NodeBuilder) {
    return (this.seen = (super.setupDirect as (b: NodeBuilder) => Direct)(builder)) as never;
  }
  override setup(builder: NodeBuilder) {
    softGlint(builder, this.light as unknown as KeyLight, () => super.setup(builder), () => this.seen);
    return undefined as never;
  }
}

class BeamLightNode extends SpotLightNode {
  static get type() {
    return 'BeamLightNode';
  }
  private seen: Direct | null = null;
  override setupDirect(builder: NodeBuilder) {
    return (this.seen = (super.setupDirect as (b: NodeBuilder) => Direct)(builder)) as never;
  }
  override setup(builder: NodeBuilder) {
    softGlint(builder, this.light as unknown as BeamLight, () => super.setup(builder), () => this.seen);
    return undefined as never;
  }
}

/** Tells the renderer what draws the rig's lights (once per renderer, before anything is compiled). */
export function registerRigLights(renderer: Renderer) {
  const library = renderer.library as unknown as { getLightNodeClass(c: unknown): unknown; addLight(n: unknown, c: unknown): void };
  if (!library.getLightNodeClass(KeyLight)) library.addLight(KeyLightNode, KeyLight);
  if (!library.getLightNodeClass(BeamLight)) library.addLight(BeamLightNode, BeamLight);
}
