import * as THREE from 'three';
import type { Node, TextureNode } from 'three/webgpu';
import { Fn, cos, cross, dot, float, int, mat2, normalize, screenCoordinate, select, sin, uv, vec2 } from 'three/tsl';
import { scaledTexture, screenView, surfaceBlur } from './screenSpace';

/**
 * Ambient occlusion from the depth buffer alone: how much of the half-space over each pixel's surface is taken by
 * nearby geometry. Our own, not three's GTAONode: that one cost 3.2 ms of GPU at 4K (half-size target) against the
 * whole scene's 10.9 ms, whatever its sample count, and this is a quarter of that for the same job here (corners,
 * under the cars, kerbs, bushes): the view position comes from the distance and two numbers of the projection
 * instead of a matrix product per tap, and the taps are eight on a spiral instead of horizons searched both ways.
 */
export interface OcclusionOptions {
  /** the occlusion's size as a fraction of the output's, per axis */
  scale: number;
  /** how far geometry occludes (m) */
  radius: number;
  /** the same, as the most it may span on screen (a fraction of the view's half height): taps far apart miss the texture cache */
  maxScreen: number;
  /** taps per pixel */
  samples: number;
  /** how dark full occlusion is */
  strength: number;
}

/** the cosine below which a tap does not count: a flat surface must not occlude itself through the depth's rounding */
const BIAS = 0.12;
/** the turn from one tap of the spiral to the next (the golden angle: no two taps line up) */
const TURN = 2.39996;

/**
 * The occlusion of the scene whose depth buffer is `depth` (1 = open, 0 = closed in), blurred, as a texture of
 * `scale` times the output's size: sample it at the screen's uv.
 */
export function ambientOcclusion(depth: TextureNode, camera: THREE.PerspectiveCamera, o: OcclusionOptions): TextureNode {
  const view = screenView(depth, camera);
  const { distance, point } = view, uHalf = view.half;

  const raw = Fn(() => {
    const at = uv();
    const d = distance(at).toVar();
    const P = point(at, d).toVar();
    // the surface's normal from the neighbours, on each axis the one nearer in depth (the other may be another surface)
    const texel = vec2(1).div(vec2(depth.size(int(0)) as unknown as Node<'ivec2'>)).toVar();
    const along = (step: Node<'vec2'>) => {
      const a = distance(at.sub(step)).toVar(), b = distance(at.add(step)).toVar();
      return select(a.sub(d).abs().lessThan(b.sub(d).abs()), P.sub(point(at.sub(step), a)), point(at.add(step), b).sub(P));
    };
    const n = normalize(cross(along(vec2(texel.x, 0)), along(vec2(0, texel.y)))).toVar();
    n.assign(select(dot(n, P).greaterThan(0), n.negate(), n));
    // the radius, no wider on screen than `maxScreen` (near the camera a metre is half the picture)
    const reach = float(o.radius).min(d.mul(uHalf.y).mul(o.maxScreen)).toVar();
    const span = reach.div(uHalf.mul(d).mul(2)).toVar();
    // the spiral turned per pixel, in a pattern that repeats every five pixels both ways: the blur's five taps cancel it
    const turn = screenCoordinate.x.floor().add(screenCoordinate.y.floor().mul(2)).mod(5).mul((Math.PI * 2) / 5);
    const dir = vec2(cos(turn), sin(turn)).toVar();
    const next = mat2(Math.cos(TURN), Math.sin(TURN), -Math.sin(TURN), Math.cos(TURN));
    const closed = float(0).toVar();
    for (let i = 0; i < o.samples; i++) {
      const q = at.add(dir.mul(span).mul((i + 0.5) / o.samples));
      const v = point(q, distance(q)).sub(P).toVar();
      const vv = dot(v, v).toVar();
      // how high the tap stands over the surface (as a cosine), fading out towards the radius
      const over = dot(v, n).mul(vv.add(1e-6).inverseSqrt()).sub(BIAS).max(0);
      closed.addAssign(over.mul(vv.div(reach.mul(reach)).oneMinus().saturate()));
      dir.assign(next.mul(dir));
    }
    // (the sky is open)
    return select(depth.sample(at).r.greaterThanEqual(1), 1, closed.mul(o.strength / o.samples).oneMinus().saturate());
  })();

  const noisy = scaledTexture(raw, o.scale, 'occlusion');
  const texel = vec2(1).div(vec2(noisy.size(int(0)) as unknown as Node<'ivec2'>));
  const across = scaledTexture(surfaceBlur(noisy, view, vec2(texel.x, 0)).r, o.scale, 'occlusion.across');
  return scaledTexture(surfaceBlur(across, view, vec2(0, texel.y)).r, o.scale, 'occlusion.down');
}
