import * as THREE from 'three';
import type { Node, TextureNode } from 'three/webgpu';
import { Fn, float, perspectiveDepthToViewZ, rtt, uniform, uv, vec3, select } from 'three/tsl';

/**
 * What the passes that work from the depth buffer share (ambient occlusion, the lights' glow in the haze): the scene
 * seen at a pixel, in "screen space" — x right, y DOWN, z into the picture (the distance along the view axis), in
 * metres — from the depth and two numbers of the projection, no matrix product per tap.
 */
export interface ScreenView {
  /** the distance along the view axis of what is seen at `p` (uv) */
  distance: (p: Node<'vec2'>) => Node<'float'>;
  /** the point seen at `p`, `d` away along the view axis */
  point: (p: Node<'vec2'>, d: Node<'float'>) => Node<'vec3'>;
  /** half the view's width and height at 1 m */
  half: Node<'vec2'>;
}

export function screenView(depth: TextureNode, camera: THREE.PerspectiveCamera): ScreenView {
  const range = new THREE.Vector2(), half = new THREE.Vector2();
  const read = () => {
    range.set(camera.near, camera.far);
    half.set(1 / camera.projectionMatrix.elements[0], 1 / camera.projectionMatrix.elements[5]);
  };
  read();
  const uRange = uniform(range).onRenderUpdate(read), uHalf = uniform(half).onRenderUpdate(read);
  return {
    distance: (p) => perspectiveDepthToViewZ(depth.sample(p).r, uRange.x, uRange.y).negate(),
    point: (p, d) => vec3(p.mul(2).sub(1).mul(uHalf).mul(d), d),
    half: uHalf,
  };
}

/** a view-space point or direction (three's: y up, z towards the viewer) in screen space */
export function toScreenSpace(v: THREE.Vector3) {
  v.y = -v.y;
  v.z = -v.z;
  return v;
}

/**
 * `node` drawn into a texture of `scale` times the output's size, per axis (`convertToTexture` is always full size):
 * one channel of 8 bits, or `colour`: HDR colour.
 */
export function scaledTexture(node: Node, scale: number, name: string, colour = false): TextureNode {
  const t = rtt(node, null, null, colour ? { resolutionScale: scale } : { resolutionScale: scale, type: THREE.UnsignedByteType, format: THREE.RedFormat });
  // (the name is what tools/perf-pass.cjs lists the pass under)
  if (t.renderTarget) t.renderTarget.texture.name = name;
  return t as unknown as TextureNode;
}

/**
 * `texture` averaged over five texels along `step`, each as far as it lies on the centre's surface (by its distance):
 * a blur that does not bleed over an edge. Five with equal weights: a pattern that repeats every five texels (the
 * taps of these passes are turned per pixel in one) cancels exactly over that many.
 *
 * "On the centre's surface" is measured against the surface's own slope: the ground seen at a low angle is
 * metres further from one row of pixels to the next, and taken for another surface the rows above and below
 * dropped out, the pattern no longer cancelled and came through as stripes across open ground (faint on dark
 * asphalt, plain on a runway's concrete and a dry lake). A plane's 1/distance runs evenly across the screen: the
 * slope is taken there, from the neighbour nearer in depth (the other may be another surface).
 */
export function surfaceBlur(texture: TextureNode, view: ScreenView, step: Node<'vec2'>): Node<'vec4'> {
  return Fn(() => {
    const at = uv();
    const centre = view.distance(at).toVar();
    const inv = float(1).div(centre).toVar();
    const before = float(1).div(view.distance(at.sub(step))).toVar(), after = float(1).div(view.distance(at.add(step))).toVar();
    const slope = select(before.sub(inv).abs().lessThan(after.sub(inv).abs()), inv.sub(before), after.sub(inv)).toVar();
    // (a difference of a twentieth of the distance is another surface: in 1/distance, that over the distance squared)
    const scale = centre.mul(centre).div(centre.mul(0.05).add(0.05)).toVar();
    const sum = texture.sample(at).mul(1e-3).toVar(), weights = float(1e-3).toVar();
    for (let i = -2; i <= 2; i++) {
      const p = at.add(step.mul(i));
      const there = i === -1 ? before : i === 1 ? after : i === 0 ? inv : float(1).div(view.distance(p));
      const w = there.sub(inv.add(slope.mul(i))).abs().mul(scale).oneMinus().saturate();
      sum.addAssign(texture.sample(p).mul(w));
      weights.addAssign(w);
    }
    return sum.div(weights);
  })();
}
