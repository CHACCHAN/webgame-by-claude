import { AnalyticLightNode, type NodeBuilder, type Renderer } from 'three/webgpu';
import { cameraViewMatrix, clamp, float, floor, getDistanceAttenuation, int, ivec2, positionWorld, renderGroup, textureLoad, uniform, vec4 } from 'three/tsl';
import { FIELD_LAMPS, FIELD_SIZE, LAMP_DECAY, LAMP_REACH, LampField } from './lampField';

type N = any; // eslint-disable-line @typescript-eslint/no-explicit-any

/**
 * The shader side of `LampField`: the pixel's cell of the grid names up to four lamps, and each of them lights it as
 * a point light does (the same fall-off and cut-off as three.js' own, through the material's lighting model: diffuse,
 * the wet road's shine, a car's clear coat). A cell that lists fewer has "no lamp" in the rest: far away and black,
 * so there is no branch.
 */
export class LampFieldNode extends AnalyticLightNode<LampField> {
  static get type() {
    return 'LampFieldNode';
  }

  private frame: N;

  constructor(light: LampField | null = null) {
    super(light);
    this.frame = uniform(light!.frame).setGroup(renderGroup);
  }

  override setup(builder: NodeBuilder): undefined {
    const light = this.light!;
    const P: N = positionWorld;
    const frame: N = this.frame;
    const cell: N = ivec2(clamp(floor(P.xz.sub(frame.xy).mul(frame.z)) as N, 0, FIELD_SIZE - 1) as N);
    const ids: N = (textureLoad(light.cells, cell) as N).mul(255).add(0.5).toVar();
    const colour: N = (this as unknown as { colorNode: N }).colorNode;
    const lightsNode = (builder as unknown as { lightsNode: { setupDirectLight(b: NodeBuilder, n: unknown, d: unknown): void } }).lightsNode;
    for (let k = 0; k < FIELD_LAMPS; k++) {
      const id: N = int(ids.element(k));
      const to: N = (textureLoad(light.table, ivec2(id, 0)) as N).xyz.sub(P).toVar();
      const tint: N = (textureLoad(light.table, ivec2(id, 1)) as N).rgb;
      const fade: N = getDistanceAttenuation({ lightDistance: to.length(), cutoffDistance: float(LAMP_REACH), decayExponent: float(LAMP_DECAY) } as never);
      lightsNode.setupDirectLight(builder, this, {
        lightDirection: (cameraViewMatrix as N).mul(vec4(to, 0)).xyz.normalize(),
        lightColor: colour.mul(tint).mul(fade),
      });
    }
  }
}

/** Tells the renderer what draws a `LampField` (once per renderer, before anything is compiled). */
export function registerLampField(renderer: Renderer) {
  const library = renderer.library as unknown as { getLightNodeClass(c: unknown): unknown; addLight(n: unknown, c: unknown): void };
  if (!library.getLightNodeClass(LampField)) library.addLight(LampFieldNode, LampField);
}
