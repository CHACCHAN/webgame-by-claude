import { AnalyticLightNode, type NodeBuilder, type Renderer } from 'three/webgpu';
import { cameraViewMatrix, clamp, float, floor, getDistanceAttenuation, int, ivec2, max, min, mix, normalWorld, positionWorld, renderGroup, smoothstep, textureLoad, uniform, vec2, vec3, vec4 } from 'three/tsl';
import { BEAM_SHAPE, FIELD_LAMPS, LAMP_DECAY, LAMP_LIGHT_DROP, LAMP_REACH, LampField } from './lampField';
import { CELLS_ROW, FIELD_SIZE, TABLE_ROW } from './lightAtlas';

type N = any; // eslint-disable-line @typescript-eslint/no-explicit-any

/**
 * The shader side of `LampField`: the pixel's cell of the grid names up to four lamps, and each of them lights it
 *  - to all sides as a point light does (the same fall-off and cut-off as three.js' own, through the material's
 *    lighting model: diffuse, the wet road's shine, a car's paint under its coat), from a little under the fixture;
 *  - downwards with its pool, on the materials that ask for it (`userData.lampBeam`): light on the surface, no
 *    shine, not on what lies far below the lamp (the road under a bridge: a lamp throws no shadow here).
 * A cell that lists fewer has "no lamp" in the rest (black), so there is no branch.
 */
export class LampFieldNode extends AnalyticLightNode<LampField> {
  static get type() {
    return 'LampFieldNode';
  }

  private field: FieldUniforms;
  private beam: N;

  constructor(light: LampField | null = null) {
    super(light);
    const l = light!;
    this.field = fieldUniforms(l);
    // (read from the light at every render: `LampField.beam` is a plain number)
    this.beam = uniform(0).setGroup(renderGroup).onRenderUpdate(() => l.beam);
  }

  override setup(builder: NodeBuilder): undefined {
    const P: N = positionWorld;
    const colour: N = (this as unknown as { colorNode: N }).colorNode;
    const userData = builder.material.userData as { lampBeam?: number; lampImage?: boolean };
    const pool = Number(userData.lampBeam ?? 0);
    const context = builder.context as unknown as { irradiance: N; lightingModel: { clearcoat?: boolean } };
    const lightsNode = (builder as unknown as { lightsNode: { setupDirectLight(b: NodeBuilder, n: unknown, d: unknown): void } }).lightsNode;
    // A material that shows the lamps as what they are in a mirror (`userData.lampImage`: a car's clear coat and its
    // glass, `carSurface.ts`) gets no clear-coat highlight from here: a point light's is one burning pixel in a
    // coat that smooth, there in one frame and gone in the next. (The lighting model reads the flag while the
    // light's nodes are made, so it is off just for this light.)
    const model = context.lightingModel;
    const coat = userData.lampImage === true && model.clearcoat === true;
    for (const { fixture, tint } of cellLamps(this.light!, P, this.field)) {
      const up: N = fixture.sub(P).toVar();
      const to: N = up.sub(vec3(0, LAMP_LIGHT_DROP, 0));
      const fade: N = getDistanceAttenuation({ lightDistance: to.length(), cutoffDistance: float(LAMP_REACH), decayExponent: float(LAMP_DECAY) } as never);
      if (coat) model.clearcoat = false;
      lightsNode.setupDirectLight(builder, this, {
        lightDirection: (cameraViewMatrix as N).mul(vec4(to, 0)).xyz.normalize(),
        lightColor: colour.mul(tint).mul(fade),
      });
      if (coat) model.clearcoat = true;
      if (pool > 0) context.irradiance.addAssign(lampPool(up, normalWorld, tint).mul(this.beam.mul(pool)));
    }
  }
}

/** what a shader needs of a `LampField` besides its texture, as uniforms that follow it */
export interface FieldUniforms {
  frame: N;
  scale: N;
  warm: N;
  cool: N;
}

export function fieldUniforms(l: LampField): FieldUniforms {
  return {
    frame: uniform(l.frame).setGroup(renderGroup),
    scale: uniform(l.scale).setGroup(renderGroup),
    warm: uniform(l.warm).setGroup(renderGroup),
    cool: uniform(l.cool).setGroup(renderGroup),
  };
}

/**
 * The lamps that reach the place `P` (world): its cell of the grid names up to four, the table says where each
 * fixture hangs and which of the two colours it has. A cell that lists fewer has "no lamp" in the rest (`tint`
 * black), so nothing branches.
 */
export function cellLamps(light: LampField, P: N, u: FieldUniforms): { fixture: N; tint: N }[] {
  const atlas = light.atlas.texture;
  const { frame, scale } = u;
  // two bytes of a texel as one number (0 … 65535)
  const WORD: N = vec2(255 * 256, 255);
  const cell: N = ivec2(clamp(floor(P.xz.sub(frame.xy).mul(frame.z)) as N, 0, FIELD_SIZE - 1) as N).add(ivec2(0, CELLS_ROW));
  const ids: N = (textureLoad(atlas, cell) as N).mul(255).add(0.5).toVar();
  const out: { fixture: N; tint: N }[] = [];
  for (let k = 0; k < FIELD_LAMPS; k++) {
    const id: N = int(ids[('xyzw' as const)[k]]);
    const a: N = (textureLoad(atlas, ivec2(id, TABLE_ROW)) as N).toVar(), b: N = (textureLoad(atlas, ivec2(id, TABLE_ROW + 1)) as N).toVar();
    const fixture: N = vec3(frame.x.add(a.rg.dot(WORD).mul(scale.x)), scale.y.add(b.rg.dot(WORD).mul(scale.z)), frame.y.add(a.ba.dot(WORD).mul(scale.x))).toVar();
    out.push({ fixture, tint: mix(u.warm, u.cool, b.b).mul(b.a).toVar() });
  }
  return out;
}

/**
 * The pool under a lamp on a surface: `up` leads from the surface to the fixture. Cos² of the angle from straight
 * down, times the surface's own cosine, as a share of `LampField.beam`; nothing far below the lamp.
 */
export function lampPool(up: N, normal: N, tint: N): N {
  const d2: N = up.dot(up).toVar();
  const shape: N = max(up.y, 0).mul(max(up.y, 0)).div(d2).mul(max((normal as N).dot(up), 0)).div(d2.sqrt()).mul(BEAM_SHAPE).div(d2.add(4));
  const here: N = smoothstep(float(20), float(14), up.y);
  return min(tint.mul(shape), vec3(1)).mul(here);
}

/** Tells the renderer what draws a `LampField` (once per renderer, before anything is compiled). */
export function registerLampField(renderer: Renderer) {
  const library = renderer.library as unknown as { getLightNodeClass(c: unknown): unknown; addLight(n: unknown, c: unknown): void };
  if (!library.getLightNodeClass(LampField)) library.addLight(LampFieldNode, LampField);
}
