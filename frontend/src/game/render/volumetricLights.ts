import * as THREE from 'three';
import type { Node, TextureNode } from 'three/webgpu';
import { Fn, atan, dot, float, int, max, min, screenCoordinate, select, smoothstep, tan, uniform, uniformArray, uv, vec2, vec3, vec4 } from 'three/tsl';
import { scaledTexture, screenView, surfaceBlur, toScreenSpace } from './screenSpace';

/**
 * The lights' glow in the air: what the haze (or the rain) between the eye and the scene scatters towards the eye
 * from the street lamps and the headlights. Worked out per pixel from the depth buffer, half the output's size:
 * - a street lamp shines equally over its lower half-space, as far as a radius: the light gathered along the view
 *   ray is a closed form (the integral of 1/d² − 1/R² along a line), no steps;
 * - a headlight is a cone: a few steps along the part of the ray that is inside it, placed where the light is (equal
 *   angles seen from the lamp), turned per pixel in the five-pixel pattern the blur cancels.
 * No shadows in the air (a tree does not cut a shaft), but the scene cuts the ray: a lamp's glow ends at the wall
 * behind it and does not shine through the car in front of it, which the old sprites and beam cones could not do.
 */

/** the lamps nearest the camera that glow, and the headlight cones (a cone per headlamp: four cars' pairs) */
const LAMPS = 16, SPOTS = 8;
export const VOLUME_SPOTS = SPOTS;
/** a lamp further than this from the camera does not glow (m); it fades in over the last third */
const LAMP_REACH = 210;
/** how far from a lamp its light still shows in the air (m) */
const LAMP_RADIUS = 15;
/** how narrowly a lamp shines down (the power of the cosine from straight down) */
const LAMP_SPREAD = 1.5;
/** a lamp's light in the air against the pooled light's on surfaces (the lamp heads throw most of theirs at the road) */
const LAMP_GAIN = 0.4;
/** steps along the view ray per headlight cone */
const STEPS = 6;
/** how far a headlight's glow reaches (m), and its light in the air against the SpotLight's on surfaces */
const SPOT_REACH = 50, SPOT_GAIN = 0.32;
/** the size of a headlamp for the light in the air (m): softens the cone's tip */
const SPOT_SIZE = 1.6;
/** the ray is not followed further than this (m): the sky has no depth */
const FAR = 400;
/** how much more the haze scatters forward than sideways (Henyey–Greenstein g) */
const FORWARD = 0.45;

export interface VolumeSpot {
  /** world position and direction (unit) of the cone */
  position: THREE.Vector3;
  direction: THREE.Vector3;
  color: THREE.Color;
  /** candela-ish, as the SpotLight's intensity */
  intensity: number;
  /** half angle of the cone (rad) and the share of it that is the soft edge, as the SpotLight's */
  angle: number;
  penumbra: number;
}

/** What glows: set by the game (the course's lamps once, the cones every frame). */
export const volume = {
  /** scattering per metre (0 = no haze: the pass draws black) */
  density: 0,
  lamps: [] as { position: THREE.Vector3; color: THREE.Color }[],
  /** the lamps' intensity (0 by day) */
  lampIntensity: 0,
  spots: [] as VolumeSpot[],
};

/** the cars' old beam cones (see-through meshes) show only where this pass does not run: 1 or 0, set by the RenderHost */
export const beamCones = uniform(1);

/** an empty cone, for a pool */
export const volumeSpot = (): VolumeSpot => ({ position: new THREE.Vector3(), direction: new THREE.Vector3(0, 0, 1), color: new THREE.Color(), intensity: 0, angle: 0.5, penumbra: 0.5 });

const vec4s = (n: number) => Array.from({ length: n }, () => new THREE.Vector4());
// lamps: position (screen space) + weight, colour; cones: position + intensity, axis + cosine of the half angle, colour + cosine of the inner cone
const lampAt = vec4s(LAMPS), lampColour = vec4s(LAMPS);
const spotAt = vec4s(SPOTS), spotAxis = vec4s(SPOTS), spotColour = vec4s(SPOTS);
const down = new THREE.Vector3();
const uDensity = uniform(0);

const _v = new THREE.Vector3();
const _near: { d: number; i: number }[] = [];

/** The lights as the camera sees them this frame, into the shader's uniforms. Call once per frame, the camera final. */
export function updateVolume(camera: THREE.PerspectiveCamera) {
  uDensity.value = volume.density;
  camera.updateMatrixWorld();
  const view = camera.matrixWorldInverse;
  toScreenSpace(down.set(0, -1, 0).transformDirection(view));
  // the nearest lamps
  _near.length = 0;
  if (volume.lampIntensity > 0 && volume.density > 0) {
    const reach = LAMP_REACH * LAMP_REACH;
    for (let i = 0; i < volume.lamps.length; i++) {
      const d = volume.lamps[i].position.distanceToSquared(camera.position);
      if (d < reach) _near.push({ d, i });
    }
    _near.sort((a, b) => a.d - b.d);
  }
  for (let k = 0; k < LAMPS; k++) {
    if (k >= _near.length) {
      lampAt[k].set(0, 0, -1e4, 0);
      continue;
    }
    const lamp = volume.lamps[_near[k].i];
    toScreenSpace(_v.copy(lamp.position).applyMatrix4(view));
    const fade = 1 - THREE.MathUtils.smoothstep(Math.sqrt(_near[k].d), LAMP_REACH * 0.67, LAMP_REACH);
    lampAt[k].set(_v.x, _v.y, _v.z, fade * volume.lampIntensity * LAMP_GAIN);
    lampColour[k].set(lamp.color.r, lamp.color.g, lamp.color.b, 0);
  }
  for (let k = 0; k < SPOTS; k++) {
    const s = volume.spots[k];
    if (!s || !(s.intensity > 0)) {
      spotAt[k].set(0, 0, -1e4, 0);
      continue;
    }
    toScreenSpace(_v.copy(s.position).applyMatrix4(view));
    spotAt[k].set(_v.x, _v.y, _v.z, s.intensity * SPOT_GAIN);
    toScreenSpace(_v.copy(s.direction).transformDirection(view));
    spotAxis[k].set(_v.x, _v.y, _v.z, Math.cos(s.angle));
    spotColour[k].set(s.color.r, s.color.g, s.color.b, Math.cos(s.angle * (1 - s.penumbra)));
  }
}

/** The glow as a texture of `scale` times the output's size (HDR colour, to be added to the picture): sample it at the screen's uv. */
export function volumetricLights(depth: TextureNode, camera: THREE.PerspectiveCamera, scale: number): TextureNode {
  const view = screenView(depth, camera);
  const uLampAt = uniformArray(lampAt), uLampColour = uniformArray(lampColour);
  const uSpotAt = uniformArray(spotAt), uSpotAxis = uniformArray(spotAxis), uSpotColour = uniformArray(spotColour);
  const uDown = uniform(down);
  /** how much of the light going along `to` (unit) is scattered towards the eye, which looks along `ray` (isotropic = 1) */
  const phase = (to: Node<'vec3'>, ray: Node<'vec3'>): Node<'float'> => {
    const base = float(1 + FORWARD * FORWARD).add(dot(to, ray).mul(2 * FORWARD)).max(1e-3);
    return float(1 - FORWARD * FORWARD).div(base.mul(base.sqrt()));
  };

  const raw = Fn(() => {
    const at = uv();
    // the view ray, and how far along it the scene is
    const along = view.point(at, float(1)).toVar();
    const ray = along.normalize().toVar();
    const end = view.distance(at).mul(along.length()).min(FAR).toVar();
    const glow = vec3(0).toVar();

    for (let k = 0; k < LAMPS; k++) {
      const L = (uLampAt.element(k) as unknown as Node<'vec4'>).toVar();
      const b = dot(L.xyz, ray).toVar();
      // the lamp's distance from the ray (not under a hand's width: looking straight at the lamp)
      const h = dot(L.xyz, L.xyz).sub(b.mul(b)).max(0.09).sqrt().toVar();
      // ∫ (1/d² − 1/R²) dt from the eye to the scene, inside the sphere of radius R about the lamp: the lamp lights
      // the air about itself and no further (without an end, sixteen lamps' faint far light adds up to a glowing sky)
      const reach = float(LAMP_RADIUS * LAMP_RADIUS).sub(h.mul(h)).max(0).sqrt().toVar();
      const s0 = b.negate().clamp(reach.negate(), reach).toVar(), s1 = end.sub(b).clamp(reach.negate(), reach).toVar();
      const gathered = atan(s1.div(h)).sub(atan(s0.div(h))).div(h).sub(s1.sub(s0).div(LAMP_RADIUS * LAMP_RADIUS)).max(0);
      // where the ray passes the lamp nearest: is that under the lamp (it shines down), and how is it seen from there
      const to = ray.mul(b.add(float(0).clamp(s0, s1))).sub(L.xyz).normalize().toVar();
      // (brightest straight down, nothing sideways: a lamp head's pattern, and no hard edge at the lamp's height)
      const under = dot(to, uDown).max(0).pow(LAMP_SPREAD);
      glow.addAssign((uLampColour.element(k) as unknown as Node<'vec4'>).rgb.mul(gathered.mul(under).mul(phase(to, ray)).mul(L.w)));
    }

    // (the cones' steps turn with the pixel in a pattern that repeats every five both ways)
    const turn = screenCoordinate.x.floor().add(screenCoordinate.y.floor().mul(2)).mod(5).div(5);
    for (let k = 0; k < SPOTS; k++) {
      const S = (uSpotAt.element(k) as unknown as Node<'vec4'>).toVar();
      const axis = (uSpotAxis.element(k) as unknown as Node<'vec4'>).toVar();
      const colour = (uSpotColour.element(k) as unknown as Node<'vec4'>).toVar();
      const b = dot(S.xyz, ray).toVar();
      const h = dot(S.xyz, S.xyz).sub(b.mul(b)).max(0.01).sqrt().toVar();
      // The part of the ray that is inside the cone (a quadratic in the distance along it), in front of the scene
      // and within the light's reach: the steps go there and nowhere else. Spread over the whole ray, a camera
      // standing in a beam and looking at its lamp had one step or none in the light (it lies in a sixth of the
      // angle seen from the lamp) and the pixels came out lit or unlit by chance: grains wherever the blur could
      // not even them out (foliage, a net: the owner's "the top of the screen turns grainy in the light", 11-12).
      const cos2 = axis.w.mul(axis.w).toVar();
      const run = dot(ray, axis.xyz).toVar(), apex = dot(S.xyz, axis.xyz).toVar();
      const qa = run.mul(run).sub(cos2).toVar();
      const qb = cos2.mul(b).sub(run.mul(apex)).toVar();
      const qc = apex.mul(apex).sub(cos2.mul(dot(S.xyz, S.xyz))).toVar();
      const root = qb.mul(qb).sub(qa.mul(qc)).max(0).sqrt().toVar();
      const inv = float(1).div(select(qa.abs().lessThan(1e-5), float(1e-5), qa)).toVar();
      const r0 = qb.negate().sub(root).mul(inv).toVar(), r1 = qb.negate().add(root).mul(inv).toVar();
      // (a ray across the cone is inside between the two; a ray that runs along it is inside from one of them on,
      // on the side the light shines to)
      const across = qa.lessThan(0), forward = run.greaterThan(0);
      const enter = select(across, min(r0, r1), select(forward, max(r0, r1), float(-1e6)));
      const leave = select(across, max(r0, r1), select(forward, float(1e6), min(r0, r1)));
      const within = float(SPOT_REACH * SPOT_REACH).sub(h.mul(h)).max(0).sqrt().toVar();
      const t0 = max(enter, max(b.sub(within), 0)).toVar(), t1 = min(leave, min(b.add(within), end)).toVar();
      // steps at equal angles as seen from the lamp: where 1/d² is large there are many
      const from = atan(t0.sub(b).div(h)).toVar(), span = atan(t1.sub(b).div(h)).sub(from).max(0).toVar();
      const lit = float(0).toVar();
      for (let i = 0; i < STEPS; i++) {
        const t = b.add(h.mul(tan(from.add(span.mul(turn.add(i).div(STEPS))))));
        const to = ray.mul(t).sub(S.xyz).toVar();
        const far = dot(to, to).toVar();
        const dir = to.mul(far.max(1e-4).inverseSqrt()).toVar();
        const cone = smoothstep(axis.w, colour.w, dot(dir, axis.xyz));
        const reach = far.div(SPOT_REACH * SPOT_REACH).oneMinus().saturate();
        lit.addAssign(cone.mul(reach.mul(reach)).mul(phase(dir, ray)));
      }
      // (1/(d² + a²) instead of 1/d²: a lamp is not a point, and a view ray grazing it must not turn white —
      // the garage looks across a bike's beam from two metres)
      glow.addAssign(colour.rgb.mul(lit.mul(span).div(h.mul(h).add(SPOT_SIZE * SPOT_SIZE).sqrt().mul(STEPS)).mul(S.w)));
    }
    return vec4(glow.mul(uDensity), 1);
  })();

  const noisy = scaledTexture(raw, scale, 'volume', true);
  const texel = vec2(1).div(vec2(noisy.size(int(0)) as unknown as Node<'ivec2'>));
  const across = scaledTexture(surfaceBlur(noisy, view, vec2(texel.x, 0)), scale, 'volume.across', true);
  return scaledTexture(surfaceBlur(across, view, vec2(0, texel.y)), scale, 'volume.down', true);
}
