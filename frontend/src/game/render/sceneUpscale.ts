import { Matrix4, type Camera } from 'three';
import { TextureNode, type NodeBuilder } from 'three/webgpu';
import { uniform, velocity } from 'three/tsl';
import { UpscalerNode } from '@pmndrs/upscaler';

/* eslint-disable @typescript-eslint/no-explicit-any */
type N = any;

/**
 * The camera's projection before the upscaler's jitter, for the motion vectors (`velocity`): **one matrix for the
 * page's whole life**. three.js writes the matrix object a velocity shader is built with into that shader, and the
 * package hands over its own (`Upscaler.unjitteredProjectionMatrix`), one per upscaler: after a change of settings
 * (a new pipeline, a new upscaler) the shaders kept from before would go on reading the old one's, which nothing
 * updates any more. `RenderHost` copies the camera's projection in before every frame, outside the pipeline's
 * render, where the camera carries no jitter.
 */
export const steadyProjection = new Matrix4();

/**
 * What the package multiplies the scene's light by before it gathers the frames in a squeezed range
 * (`c / (1 + max(c))`, undone afterwards): fixed, and small. The package's own choice (mid-grey from the picture's
 * average, at most 8) is at its top in every night scene, and a small bright thing averaged with its dark surround
 * in that range comes out far darker than its light: the lamps and the glints on a car lost the glow the bloom makes
 * of them (a still night picture 5 % darker than without upscaling, a quarter to a third darker around a lamp; the
 * first half second after a cut 3 % brighter, while the average settled). At 0.01 the range is nearly straight up
 * to a light of ~30: the picture is within 1.2 % of native (0.2 at 0.002, where the still picture's flicker begins to
 * rise), the detail on the move the same at every value. The price is the package's hold on thin steady
 * things, which wants a contrast of 0.02 in that range (its `LOCK_CONTRAST_LO`): only lights reach it now.
 */
const PRE_EXPOSURE = 0.01;

/**
 * The temporal upscaler of the WebGPU backend: FSR 3's upscaling (the FSR 2 / 3 temporal pass graph, without frame
 * generation) from `@pmndrs/upscaler`, raw WGSL compute passes on the renderer's own device. The scene is drawn
 * smaller than the output with the camera jittered inside a pixel (the package's node does that around the pipeline's
 * render), and its colour, depth, motion vectors and reactive mask are gathered over the frames into a full-size,
 * anti-aliased picture, sharpened by the package's RCAS. The node is the package's, as it is; what this adds:
 * - the motion vectors' projection is `steadyProjection` (see there), from the moment the node is made: a shader
 *   built before the first frame (`RenderHost.precompile`) would else take the camera's jittered projection for good,
 *   the history be read a fraction of a pixel off every frame, and the whole picture shimmer and go soft;
 * - the sharpening can be set before the package's upscaler exists (it is made when the node is first built).
 */
export class SceneUpscaler extends UpscalerNode {
  // (`_` names: three.js walks a node's other properties as parts of the graph)
  private _sharpness = 0;

  /** `ratio`: output size / scene size per axis; `timed`: the package gathers its passes' GPU times (`upscaler.gpuTimings`) */
  constructor(colour: TextureNode, depth: TextureNode, motion: TextureNode, reactive: TextureNode, camera: Camera, ratio: number, timed = false) {
    super(colour, depth, motion, camera, { ratio, reactive, gpuTiming: timed });
    velocity.setProjectionMatrix(steadyProjection);
  }

  setup(builder: NodeBuilder) {
    const out = super.setup(builder);
    // (the package has just pinned its own matrix, or none where it could not jitter: ours, always)
    velocity.setProjectionMatrix(steadyProjection);
    this.apply();
    return out;
  }

  /** RCAS after the upscale, 0 (none: a plain resolve) … 1 */
  set sharpness(value: number) {
    this._sharpness = Math.min(1, Math.max(0, value));
    this.apply();
  }

  private apply() {
    const settings = this.upscaler?.settings;
    if (!settings) return;
    settings.sharpness = this._sharpness;
    settings.autoExposure = false;
    settings.exposure = PRE_EXPOSURE;
  }

  /**
   * Resolves when the upscaler's compute pipelines are built (off the main thread; until then the node passes the
   * scene through as it is, so nothing waits for them but the loading screen).
   */
  async ready(): Promise<void> {
    try {
      await this.upscaler?.prepare();
    } catch {
      // (the package has logged which pass failed; the node keeps passing the scene through)
    }
  }

  dispose() {
    velocity.setProjectionMatrix(null);
    super.dispose();
  }
}

/**
 * Level-of-detail bias of the scene's textures while it is drawn smaller than the output: the GPU picks a texture's
 * mip level by the pixels it is drawn in, so at 67 % every texture came a good half level blurrier than the output
 * could show (and normal maps flatter). The bias (log2 of the scale) picks the level for the output's size; the
 * jitter and the history take care of the shimmer that sharper levels bring.
 */
export const sceneTextureBias = uniform(0);

let biased = false;
/**
 * From now on, textures sampled by the scene's materials while the upscaler's targets are set take `sceneTextureBias`
 * (three.js has no such switch: its texture node's setup is wrapped). Left alone: textures read at an explicit
 * level or gradient, shadow comparisons, depth and render-target textures, and everything the post-processing reads.
 */
export function biasSceneTextures() {
  if (biased) return;
  biased = true;
  const proto = TextureNode.prototype as unknown as { setup(builder: NodeBuilder): unknown };
  const setup = proto.setup;
  proto.setup = function (this: TextureNode, builder: NodeBuilder) {
    const result = setup.call(this, builder);
    const p = (builder as N).getNodeProperties(this) as Record<string, unknown>;
    const tex = this.value as N;
    const plain = !p.biasNode && !p.levelNode && !p.gradNode && !p.gatherNode && !p.compareNode && !p.compareStepNode && (this as N).sampler !== false;
    const mipped = tex && !tex.isDepthTexture && !tex.isRenderTargetTexture && !tex.isCubeTexture && (tex.generateMipmaps || (tex.mipmaps?.length ?? 0) > 1);
    if (plain && mipped && builder.renderer.getMRT()?.has('reactive')) p.biasNode = sceneTextureBias;
    return result;
  };
}
