import { TextureNode, type Camera, type NodeBuilder } from 'three/webgpu';
import {
  Fn, context, convertToTexture, exp, float, ivec2, luminance, max, mix, outputStruct, property, texture, uniform, uv, vec2, vec4, velocity,
  OnAfterRenderPipeline, OnBeforeRenderPipeline,
} from 'three/tsl';
import TAAUNode from 'three/addons/tsl/display/TAAUNode.js';
// @ts-expect-error (no type declarations for this helper module)
import { clipAABB, flickerReduction, sampleCurrentDepth, samplePreviousDepth } from 'three/addons/tsl/utils/TAAUtils.js';

/** a frame's knowledge of an output pixel halves when its nearest sample is half an output pixel from the centre */
const NEARNESS = Math.LN2 / 0.25;
/** the most a pixel's history counts for, in frames with a sample on the pixel's centre */
const MAX_KNOWN = 16;
/** … divided by 1 + this × the pixel's motion (output pixels a frame) */
const SPEED_FADE = 0.5;
/** the thin-feature lock is gone at 1 / this pixels a frame */
const LOCK_FADE = 0.5;

/* eslint-disable @typescript-eslint/no-explicit-any */
/** the shader maths below is written against the untyped helpers above */
type N = any;

/**
 * The temporal upscaler: the scene is drawn smaller than the output with the camera jittered inside a pixel, and
 * each output pixel gathers the frames (the history, carried along the motion vectors) into a full-size, anti-aliased
 * picture. Built on three.js' `TAAUNode` (its targets, jitter and history upkeep are used as they are); the resolve
 * is ours, for what a race at speed asks of it:
 * - the history is read with a Catmull-Rom filter (five taps): read bilinearly every frame, a surface that moves
 *   under the camera, as the road always does, went soft within a few frames;
 * - with a sharp history, motion alone no longer hands the pixel to the (small, aliased) current frame as fast;
 * - each pixel carries how much its history knows, and a frame counts by how near its sample fell: a still picture
 *   settles instead of shimmering, a newly uncovered one fills in at once;
 * - a reactive mask: where rain, smoke, sparks or lamps were drawn over the surface (see RenderHost
 *   `surfaceReactive`) the current frame counts for more, or they were averaged away.
 */
export class TemporalUpscaler extends TAAUNode {
  /** the history gives way to the current frame as the motion nears this many (input) pixels a frame */
  maxVelocityLength = 320;
  /** the least a frame with a sample on the pixel's centre counts for (what follows a change of light in a still picture) */
  currentFrameWeight = 0.04;
  /** the current frame's share where the reactive mask is full */
  reactiveWeight = 0.9;

  constructor(beauty: TextureNode, depth: TextureNode, velocity: TextureNode, private readonly reactive: TextureNode, camera: Camera) {
    super(beauty, depth, velocity, camera);
  }

  /**
   * For shaders built outside a frame (RenderHost `precompile`): the motion vectors are to be worked out with the
   * camera's projection before the jitter, which three.js hands to the velocity node only while a frame is drawn,
   * and a shader built without it takes the jittered one for good. Its motion vectors then carry the jitter, the
   * history is read a fraction of a pixel off every frame, and the whole picture shimmers and goes soft.
   */
  steadyVelocity(on: boolean) {
    velocity.setProjectionMatrix(on ? (this as N)._originalProjectionMatrix : null);
  }

  setup(builder: NodeBuilder) {
    const self = this as N;
    const state = (builder as N).context.renderPipelineState;
    if ((builder as N).renderPipeline && !state.viewOffsetOwner) {
      state.viewOffsetOwner = this;
      self._needsPostProcessingSync = true;
      const inputSize = () => {
        const target = self.beautyNode.isRTTNode ? self.beautyNode.renderTarget : self.beautyNode.passNode.renderTarget;
        return [target.texture.width, target.texture.height] as const;
      };
      OnBeforeRenderPipeline(() => this.setViewOffset(...inputSize()));
      OnAfterRenderPipeline(() => this.clearViewOffset());
    }
    const historyTexture = self._historyRenderTarget.textures[0];
    const historyNode: N = texture(historyTexture);
    const beauty: N = this.beautyNode, depth: N = this.depthNode, velocity: N = this.velocityNode, reactive: N = this.reactive;
    const jitter: N = self._jitterOffset;

    const colorOutput: N = property('vec4');
    const lockOutput: N = property('vec4');
    const outputNode = outputStruct(colorOutput, lockOutput);

    /** the history at `at`, Catmull-Rom filtered with five bilinear taps (the four corner taps of the nine are left out) */
    const sharpHistory = (at: N): N => {
      const size: N = vec2(historyNode.size());
      const pos = at.mul(size);
      const centre = pos.sub(0.5).floor().add(0.5);
      const f = pos.sub(centre);
      const w0 = f.mul(f.mul(f.mul(-0.5).add(1)).sub(0.5));
      const w1 = f.mul(f).mul(f.mul(1.5).sub(2.5)).add(1);
      const w2 = f.mul(f.mul(f.mul(-1.5).add(2)).add(0.5));
      const w3 = f.mul(f).mul(f.mul(0.5).sub(0.5));
      const w12 = w1.add(w2);
      const p0 = centre.sub(1).div(size), p3 = centre.add(2).div(size), p12 = centre.add(w2.div(w12)).div(size);
      const tap = (x: N, y: N, w: N) => vec4(historyNode.sample(vec2(x, y)).rgb.mul(w), w);
      const sum: N = tap(p12.x, p0.y, w12.x.mul(w0.y))
        .add(tap(p0.x, p12.y, w0.x.mul(w12.y)))
        .add(tap(p12.x, p12.y, w12.x.mul(w12.y)))
        .add(tap(p3.x, p12.y, w3.x.mul(w12.y)))
        .add(tap(p12.x, p3.y, w12.x.mul(w3.y)));
      // (the filter's negative lobes can undershoot next to a lamp: no negative light)
      return vec4(sum.rgb.div(sum.a).max(0), 1);
    };

    const resolve = Fn(() => {
      const uvNode: N = uv();
      const inputSize: N = vec2(beauty.size());
      // the output pixel's centre in input pixels, and the input sample nearest to it (drawn at texel + 0.5 + jitter)
      const pIn = uvNode.mul(inputSize);
      const closestTapF = pIn.sub(vec2(0.5).add(jitter)).round();
      const closestTap: N = ivec2(closestTapF);

      // the motion of the nearest surface around that sample (an edge moves with what is in front)
      const currentDepth: N = sampleCurrentDepth(depth, closestTapF, self._cameraNearFar);
      const closestDepth = currentDepth.get('closestDepth');
      const farthestDepth = currentDepth.get('farthestDepth');
      const offsetUV = velocity.load(currentDepth.get('closestPositionTexel')).xy.mul(vec2(0.5, -0.5));
      const historyUV = uvNode.sub(offsetUV);
      const previousDepth: N = samplePreviousDepth(self._previousDepthNode, historyUV, self._previousCameraProjectionMatrixInverse, self._previousCameraWorldMatrix, self._cameraWorldMatrixInverse, self._cameraNearFar, this.camera);

      const isValidUV = historyUV.greaterThanEqual(0).all().and(historyUV.lessThanEqual(1).all());
      const isEdge = farthestDepth.sub(closestDepth).greaterThan(this.edgeDepthDiff);
      const isDisocclusion = closestDepth.sub(previousDepth).greaterThan(this.depthThreshold);
      const hasValidHistory = isValidUV.and(isEdge.or(isDisocclusion.not()));

      // the current frame at this output pixel: the 3×3 input samples around it, each weighted by its distance
      // (a Gaussian close to a Blackman-Harris window); the same nine give the colour range the history may keep
      const sumColor: N = vec4(0).toVar();
      const sumWeight: N = float(0).toVar();
      const moment1: N = vec4(0).toVar();
      const moment2: N = vec4(0).toVar();
      let count = 0;
      for (let y = -1; y <= 1; y++) for (let x = -1; x <= 1; x++) {
        const tap = closestTap.add(ivec2(x, y));
        const delta = pIn.sub(vec2(tap).add(vec2(0.5).add(jitter)));
        const w = exp(delta.dot(delta).mul(-2.29));
        // (no NaN or negative light into the history: it would stay)
        const c = vec4(beauty.load(tap).rgb.max(0), 1);
        sumColor.addAssign(c.mul(w));
        sumWeight.addAssign(w);
        moment1.addAssign(c);
        moment2.addAssign(c.pow2());
        count++;
      }
      const currentColor = sumColor.div(sumWeight.max(1e-5));
      const mean = moment1.div(count);
      const motionFactor = uvNode.sub(historyUV).mul(inputSize).length().div(this.maxVelocityLength).saturate();
      const varianceGamma = mix(0.75, 1.25, motionFactor.oneMinus().pow2());
      const variance = moment2.div(count).sub(mean.pow2()).max(0).sqrt().mul(varianceGamma);
      const minColor = mean.sub(variance), maxColor = mean.add(variance);

      const historyColor = sharpHistory(historyUV);
      const clippedHistoryColor: N = clipAABB(mean.clamp(minColor, maxColor), historyColor, minColor, maxColor);

      // thin bright things (a wire, a rail's edge) that the colour range would cut: the history is kept as it is
      // while the depth there holds
      const currentLuma = luminance(currentColor.rgb);
      const meanLuma = luminance(mean.rgb).toConst();
      const thinFeature = currentLuma.sub(meanLuma).abs().div(meanLuma.max(1e-4)).smoothstep(0, 0.2);
      const isDepthChanged = closestDepth.sub(previousDepth).abs().greaterThan(this.depthThreshold);
      // (only where the picture holds still: on the move the range must cut, or a post leaves its ghosts behind)
      const speed = uvNode.sub(historyUV).mul(vec2(historyNode.size())).length();
      const lock = isValidUV.and(isDepthChanged.not()).select(thinFeature, float(0)).mul(speed.mul(LOCK_FADE).oneMinus().saturate());
      const lockedHistoryColor = mix(clippedHistoryColor, historyColor, lock);

      // What this frame knows about this output pixel: all of it when one of its samples fell on the pixel's
      // centre, little when the nearest is most of a pixel away (the scene has fewer samples than the output has
      // pixels, and the jitter moves them every frame). The history carries the sum of what its frames knew, and the
      // frame joins by its share of that sum (kept in the history's alpha, which no picture needs): a running average weighted by nearness. So a still picture settles
      // (every frame counting the same, each edge pixel swung by whatever sample came nearest: a shimmer on every
      // thin line), and a pixel that just came into view takes its first frames whole instead of creeping up.
      const nearest = pIn.sub(closestTapF.add(vec2(0.5).add(jitter))).mul(vec2(historyNode.size()).div(inputSize));
      const knows = exp(nearest.dot(nearest).mul(-NEARNESS));
      // On the move the history is worth less the faster it goes: it is resampled every frame, and driving forward
      // stretches it (what was three pixels is five a moment later), so what it knows is capped by the speed and
      // the detail comes from the frames at hand. Still: the full sum; at 200 km/h the road by the car: this frame.
      const cap = float(MAX_KNOWN).div(speed.mul(SPEED_FADE).add(1));
      const known = hasValidHistory.select(historyNode.sample(historyUV).a, float(0)).add(knows).min(cap);
      const reactiveShare = reactive.sample(uvNode).r.saturate();
      const forced = motionFactor.add(reactiveShare.mul(this.reactiveWeight));
      const currentWeight = max(knows.div(known), knows.mul(this.currentFrameWeight), forced).saturate();

      colorOutput.assign(vec4(flickerReduction(currentColor, lockedHistoryColor, currentWeight).rgb, known));
      lockOutput.assign(0);
      return vec4(0);
    });

    const sharedContext = context((builder as N).getSharedContext());
    self._resolveMaterial.contextNode = sharedContext;
    self._resolveMaterial.colorNode = resolve();
    self._resolveMaterial.outputNode = outputNode;
    self._seedMaterial.colorNode = Fn(() => {
      colorOutput.assign(vec4(beauty.sample(uv()).rgb, 0));
      lockOutput.assign(0);
      return vec4(0);
    })();
    self._seedMaterial.contextNode = sharedContext;
    self._seedMaterial.outputNode = outputNode;
    return self._textureNode;
  }
}

/** the scene (`beauty`, with its depth, motion vectors and reactive mask, all at the scene's resolution) at the output's size */
export const temporalUpscale = (beauty: TextureNode, depth: TextureNode, velocity: TextureNode, reactive: TextureNode, camera: Camera) =>
  new TemporalUpscaler(convertToTexture(beauty) as unknown as TextureNode, depth, velocity, reactive, camera);

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
