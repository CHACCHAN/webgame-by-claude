import * as THREE from 'three';
import { MeshPhysicalNodeMaterial, TempNode, type NodeBuilder } from 'three/webgpu';
import { clamp, clearcoatRoughness, dot, exp, float, getDistanceAttenuation, materialOpacity, max, mix, normalView, normalize, pmremTexture, positionViewDirection, positionWorld, pow, renderGroup, roughness, smoothstep, uniform, uniformArray, vec3 } from 'three/tsl';
import type { Preset } from './Environment';
import { LAMP_DECAY, LAMP_LIGHT_DROP, LAMP_REACH, type FieldLamp, type LampField } from './lampField';
import { lampPool } from './lampFieldNode';
import { wetness } from './weather';

type N = any; // eslint-disable-line @typescript-eslint/no-explicit-any

/**
 * What a car's glossy surfaces mirror: the surroundings as a car on a road has them, worked out per pixel.
 *
 * The game's one reflection environment (`Environment.buildEnvMap`: the sky and a ring of warm lights, blurred into
 * a PMREM) knows nothing near the car, and by night it is nearly black: paint was a flat colour with one soft
 * highlight, glass a dark sheet with orange smears. A cube map drawn around the car would show what stands there,
 * but it is a second drawing of the scene (every draw call again, every shader built again for another target, the
 * shadow maps drawn again), a face a frame behind the car at speed, and one car's view for all of them. What a clear
 * coat shows of a road is little and regular, so it is put together here instead, for the mirror direction of each
 * pixel, in the world's own coordinates:
 *  - the sky as the dome draws it (gradient, the glow round sun or moon, the town's glow, the cloud cover), sharp;
 *  - the road under the car: a plane through the car's wheels (`onCarsGround`), lit by the sky, the sun or moon and
 *    the street lamps around the place the mirror ray comes down on; far off, the land in the haze;
 *  - the street lamps themselves, in the clear coat: the lamps nearest the camera (`lampsAround`, as far as
 *    `NEAR_REACH`: the lamp field's own cells end at 42 m, and it is the lamps far ahead that a roof and a rear
 *    window show from behind, at a flat angle and so at their brightest) as the small bright disc with a glow
 *    round it that a lamp is in a mirror, as large as the lamp is seen from there, and as much larger and fainter
 *    as the coat is rough. A point light's highlight in a coat this smooth is one pixel that flickers; the disc
 *    slides over bonnet, roof and glass as the car drives under the lamps.
 * The diffuse light of the surroundings still comes from the game's environment map.
 *
 * It is the `envNode` of the materials made here, one node for all of them: what differs per car comes from the
 * mesh through a per-object uniform, so every car's paint is one shader.
 */

/** the luminous face of a street lamp as a mirror shows it: its radius (m) and the share of the lamp's light it carries */
const LAMP_FACE = 0.3, LAMP_IMAGE = 0.5;
/** the glow round it (the lamp's housing, the lit haze): radius (m) and share */
const LAMP_GLOW = 1.5, LAMP_GLOW_IMAGE = 0.3;
/** lamps the mirror images know, and how far from the camera the furthest of them can be (m) */
const NEAR = 8, NEAR_REACH = 180;
/** asphalt: what it gives back of the light on it (albedo / π), dry and wet */
const ROAD_DRY = 0.1 / Math.PI, ROAD_WET = 0.055 / Math.PI;
/** land beside the road, seen far off */
const LAND = 0.12 / Math.PI;

/** the sky and the land's light as the mirror image needs them (`showSurroundings`) */
const sky: { [k in 'zenith' | 'horizon' | 'keyDir' | 'keyGlow' | 'cityDir' | 'cityGlow' | 'cloud' | 'ground' | 'land']: N } = {
  zenith: uniform(new THREE.Color(0, 0, 0)),
  horizon: uniform(new THREE.Color(0, 0, 0)),
  keyDir: uniform(new THREE.Vector3(0, 1, 0)),
  keyGlow: uniform(new THREE.Color(0, 0, 0)),
  cityDir: uniform(new THREE.Vector3(1, 0, 0)),
  cityGlow: uniform(new THREE.Color(0, 0, 0)),
  /** the cloud cover's colour and how much of the sky it hides */
  cloud: uniform(new THREE.Vector4(0, 0, 0, 0)),
  /** light on level ground from the sky and the sun or moon (irradiance) */
  ground: uniform(new THREE.Color(0, 0, 0)),
  /** far land in the haze, as it looks */
  land: uniform(new THREE.Color(0, 0, 0)),
};

const _c = new THREE.Color();

/**
 * The time of day's sky and light for the mirror images (`Game.applyTimeOfDay`, with the course's own sun or moon
 * in the preset). `city`: where the town's glow stands on the horizon and how strong it is there.
 */
export function showSurroundings(p: Preset, sun: boolean, city: { dir: readonly [number, number, number]; glow: number }) {
  sky.zenith.value.set(p.zenith);
  sky.horizon.value.set(p.horizon);
  sky.keyDir.value.copy(p.keyDir);
  sky.keyGlow.value.set(p.keyColor).multiplyScalar(sun ? 1 : 0.15);
  sky.cityDir.value.set(...city.dir).normalize();
  sky.cityGlow.value.set(p.glow).multiplyScalar(p.cityGlow * city.glow);
  // (the dome's clouds are wisps under a clear sky and a closed cover under an overcast one)
  _c.set(p.cloudColor).multiplyScalar(0.75);
  sky.cloud.value.set(_c.r, _c.g, _c.b, p.clouds * (0.3 + 0.6 * p.overcast));
  sky.ground.value.set(p.hemiSky).multiplyScalar(p.hemiIntensity);
  // (the sun or moon on level ground; some of the ground a car mirrors lies in a shadow)
  sky.ground.value.add(_c.set(p.keyColor).multiplyScalar(p.keyIntensity * Math.max(p.keyDir.y, 0) * 0.7));
  sky.land.value.copy(sky.ground.value).multiplyScalar(LAND * 0.8).add(_c.set(p.fog).multiplyScalar(0.2));
}

/** the vehicle a mesh belongs to, and that vehicle's ground (not in `userData`: a clone would copy it as JSON) */
const roots = new WeakMap<THREE.Object3D, THREE.Object3D>();
const planes = new WeakMap<THREE.Object3D, THREE.Vector4>();

/**
 * Tells every mesh under a vehicle's root (a node with its origin on the ground under the wheels and its +Y the
 * vehicle's up) which road it stands on: the mirror images lay the ground through that point. Call again after
 * adding parts.
 */
export function onCarsGround<T extends THREE.Object3D>(root: T): T {
  root.traverse((o) => {
    if ((o as THREE.Mesh).isMesh) roots.set(o, root);
  });
  return root;
}

const NO_CAR = new THREE.Vector4(0, 1, 0, 1e4);
const _n = new THREE.Vector3(), _o = new THREE.Vector3();
/**
 * The road under the vehicle the mesh belongs to, as a plane (normal, offset): the vehicle's own up through the
 * point its wheels stand on (`onCarsGround`). A mesh nobody spoke for has its ground far below, which mirrors as
 * land in the haze.
 */
const groundPlane: N = (uniform(new THREE.Vector4(0, 1, 0, 1e4)) as N).onObjectUpdate(({ object }: { object: THREE.Object3D | null }) => {
  const root = object ? roots.get(object) : undefined;
  if (!root) return NO_CAR;
  const e = root.matrixWorld.elements;
  _n.set(e[4], e[5], e[6]).normalize();
  _o.set(e[12], e[13], e[14]);
  let plane = planes.get(root);
  if (!plane) planes.set(root, (plane = new THREE.Vector4()));
  return plane.set(_n.x, _n.y, _n.z, -_n.dot(_o));
});

// ---- the lamps near the camera: where each fixture hangs + how much of it counts (it comes in from nothing at the
// edge of the list), and its colour
const nearAt = Array.from({ length: NEAR }, () => new THREE.Vector4(0, 1e4, 0, 0));
const nearTint = Array.from({ length: NEAR }, () => new THREE.Vector4(0, 0, 0, 0));
const picked: { d: number; lamp: FieldLamp }[] = [];
let field: LampField | null = null;

/** The street lamps the mirror images show (`LightRig`: the game has one lamp field for the page's life). */
export function mirrorLamps(lamps: LampField) {
  field = lamps;
}

/**
 * Per frame: the lamps nearest `eye` (the camera), for the mirror images of every car in the picture. The list
 * ends where its furthest lamp would be the next one out, and a lamp counts for nothing there: none pops in or out.
 */
export function lampsAround(eye: THREE.Vector3) {
  const lamps = field?.shown ?? [];
  picked.length = 0;
  let edge = NEAR_REACH * NEAR_REACH;
  for (const lamp of lamps) {
    const d = lamp.position.distanceToSquared(eye);
    if (d >= edge) continue;
    // (kept sorted: the nearest NEAR and the one after them, whose distance is the list's edge)
    let k = picked.length;
    while (k > 0 && picked[k - 1].d > d) k--;
    picked.splice(k, 0, { d, lamp });
    if (picked.length > NEAR) {
      picked.length = NEAR + 1;
      edge = picked[NEAR].d;
    }
  }
  const reach = Math.sqrt(edge);
  for (let k = 0; k < NEAR; k++) {
    const p = k < picked.length ? picked[k] : null;
    if (!p) {
      nearAt[k].set(0, 1e4, 0, 0);
      nearTint[k].set(0, 0, 0, 0);
      continue;
    }
    const { position: at, color } = p.lamp;
    nearAt[k].set(at.x, at.y, at.z, 1 - THREE.MathUtils.smoothstep(Math.sqrt(p.d), reach * 0.7, reach));
    nearTint[k].set(color.r, color.g, color.b, 0);
  }
}

class SurroundingsNode extends TempNode {
  static get type() {
    return 'CarSurroundingsNode';
  }

  /** a lamp's light to all sides (colour × candela) and the strength of the pool under it, as the lamp field has them now */
  private readonly lampLight: N;
  private readonly beam: N;
  private readonly at: N = uniformArray(nearAt);
  private readonly tint: N = uniformArray(nearTint);
  private readonly pmrem = new WeakMap<THREE.Texture, N>();

  constructor(lamps: LampField) {
    super('vec3');
    const light = new THREE.Color();
    this.lampLight = (uniform(light) as N).setGroup(renderGroup).onRenderUpdate(() => light.copy(lamps.color).multiplyScalar(lamps.intensity));
    this.beam = (uniform(0) as N).setGroup(renderGroup).onRenderUpdate(() => lamps.beam);
  }

  /** the game's environment map: the diffuse light, and whatever asks in a way this node does not know */
  private blurred(builder: NodeBuilder): N {
    const env = (builder as unknown as { scene: THREE.Scene | null }).scene?.environment ?? null;
    if (!env) return vec3(0);
    let node = this.pmrem.get(env);
    if (!node) this.pmrem.set(env, (node = pmremTexture(env)));
    return node;
  }

  override setup(builder: NodeBuilder): N {
    // (three.js asks an environment three times: for the light on the surface, for the mirror image in the paint
    // and for the one in the coat; `getTextureLevel` is the roughness it wants the image blurred by)
    const context = builder.context as unknown as { getUV?: (n: unknown, b: NodeBuilder) => N; getTextureLevel?: (n: unknown) => N };
    const level: N = context.getTextureLevel?.(this);
    const coat = level === clearcoatRoughness;
    if (!context.getUV || (!coat && level !== roughness)) return this.blurred(builder);
    return this.mirrored(context.getUV(this, builder), level, coat);
  }

  /** what is seen from the pixel in the direction `D` (world), blurred as a surface of roughness `rough` does */
  private mirrored(D: N, rough: N, coat: boolean): N {
    const P: N = positionWorld;
    // the half width of a mirror image's blur, as an angle (GGX: the lobe of the mirror direction is twice the normals')
    const blur: N = rough.mul(rough).mul(2).toVar();

    // ---- the sky, as `Environment.skyMaterial` draws it
    const h: N = D.y;
    const col: N = mix(sky.horizon, sky.zenith, pow(clamp(h, 0, 1), 0.42)).toVar();
    const flat: N = normalize(vec3(D.x, 0, D.z).add(1e-5));
    col.addAssign(sky.cityGlow.mul(pow(max(dot(flat, sky.cityDir), 0), 2.5)).mul(exp(max(h.add(0.02), 0).mul(-10))));
    const kd: N = max(dot(D, sky.keyDir), 0).toVar();
    col.addAssign(sky.keyGlow.mul(pow(kd, 8).mul(0.25).add(pow(kd, 64).mul(0.5))));
    col.assign(mix(col, sky.cloud.rgb, sky.cloud.a.mul(smoothstep(0, 0.18, h))));

    // ---- the road under the car, and the land beyond it
    const n: N = groundPlane.xyz;
    const height: N = max(dot(n, P).add(groundPlane.w), 0.05);
    const dip: N = dot(n, D).negate().toVar();
    const reach: N = height.div(max(dip, 0.01)).toVar();
    const hit: N = P.add(D.mul(reach)).toVar();
    const light: N = vec3(sky.ground).toVar();
    for (let k = 0; k < NEAR; k++) {
      const lamp: N = this.at.element(k), tint: N = this.tint.element(k).rgb.mul(lamp.w).toVar();
      const up: N = lamp.xyz.sub(hit).toVar();
      const to: N = up.sub(vec3(0, LAMP_LIGHT_DROP, 0)).toVar();
      const far: N = to.length().toVar();
      const fade: N = getDistanceAttenuation({ lightDistance: far, cutoffDistance: float(LAMP_REACH), decayExponent: float(LAMP_DECAY) } as never);
      light.addAssign(lampPool(up, vec3(0, 1, 0), tint).mul(this.beam));
      light.addAssign(this.lampLight.mul(tint).mul(fade.mul(max(to.y, 0)).div(far)));
    }
    const road: N = light.mul(mix(float(ROAD_DRY), float(ROAD_WET), wetness));
    const ground: N = mix(road, sky.land, smoothstep(40, 160, reach));
    const edge: N = blur.add(0.012);
    col.assign(mix(col, ground, smoothstep(edge.negate(), edge, dip)));

    // ---- the lamps themselves: only a coat is smooth enough to show them (the paint under it has the lamp field's
    // own highlight)
    if (coat) {
      const spread: N = blur.mul(blur);
      for (let k = 0; k < NEAR; k++) {
        const lamp: N = this.at.element(k);
        const to: N = lamp.xyz.sub(P).toVar();
        const d2: N = to.dot(to).toVar();
        // the angle between the mirror direction and the lamp, squared
        const off: N = max(float(1).sub(dot(D, to).div(d2.sqrt())), 0).mul(2).toVar();
        // a disc of the size the lamp's face has from here (as an angle, squared), widened by the coat's blur, which
        // spreads the same light thinner; and the glow round it likewise
        const face: N = float(LAMP_FACE * LAMP_FACE).div(d2).add(spread).toVar(), glow: N = float(LAMP_GLOW * LAMP_GLOW).div(d2).add(spread).toVar();
        const image: N = exp(off.div(face).negate()).div(face.mul(Math.PI / LAMP_IMAGE)).add(exp(off.div(glow).negate()).div(glow.mul(Math.PI / LAMP_GLOW_IMAGE)));
        col.addAssign(this.lampLight.mul(this.tint.element(k).rgb).mul(image.mul(lamp.w).div(d2)));
      }
    }
    return col;
  }
}

let around: { lamps: LampField; node: SurroundingsNode } | null = null;

/** the one node all the materials share */
function surroundings(): SurroundingsNode | null {
  if (!field) return null;
  if (around?.lamps !== field) around = { lamps: field, node: new SurroundingsNode(field) };
  return around.node;
}

/** Gives a physical node material the car's mirror images instead of the game's environment map. */
function mirroring<T extends MeshPhysicalNodeMaterial>(mat: T): T {
  const node = surroundings();
  if (node) {
    mat.envNode = node as never;
    // (the lights: no point highlight in this material's coat, `coatGlint.ts`; the lamps are in its mirror image)
    mat.userData.lampImage = true;
  }
  return mat;
}

/** Paint under a clear coat (the body colour, the two-tone's second colour). */
export function paintMaterial(params: THREE.MeshPhysicalMaterialParameters): THREE.MeshPhysicalMaterial {
  return mirroring(new MeshPhysicalNodeMaterial(params as never)) as unknown as THREE.MeshPhysicalMaterial;
}

/**
 * A pane of glass: it mirrors like the coat, and lets the cabin behind it through, dimmed by its tint (`opacity`),
 * less and less towards a flat angle. Drawn blended with its depth written, as the glass always was; but the
 * mirror image is added whole, not thinned by the pane's opacity as a plain see-through material's is (which left
 * an eighth of a lamp's image in the glass).
 */
class GlassMaterial extends MeshPhysicalNodeMaterial {
  static override get type() {
    return 'CarGlassMaterial';
  }

  // (three.js would multiply the lit colour by the opacity here; ours is already what the pane itself sends out)
  override setupPremultipliedAlpha(_builder: NodeBuilder, outputNode: N): N {
    return outputNode;
  }
}

export function glassMaterial(params: THREE.MeshPhysicalMaterialParameters): THREE.MeshPhysicalMaterial {
  const mat = new GlassMaterial(params as never);
  mat.transparent = true;
  mat.premultipliedAlpha = true;
  // what the pane mirrors does not come through it: Fresnel's share, from a twenty-fifth head-on to all of it
  const facing: N = (normalView as N).dot(positionViewDirection).clamp();
  mat.opacityNode = mix(materialOpacity, float(1), pow(facing.oneMinus(), 5).mul(0.96).add(0.04));
  return mirroring(mat) as unknown as THREE.MeshPhysicalMaterial;
}
