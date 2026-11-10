import * as THREE from 'three';
import { BlendMode, RenderPipeline, WebGPURenderer, type Node, type NodeBuilder } from 'three/webgpu';
import { Fn, convertToTexture, dot, float, fract, luminance, mrt, output, pass, renderOutput, sRGBTransferEOTF, sRGBTransferOETF, screenUV, sin, smoothstep, time, uniform, vec2, vec3, vec4, velocity } from 'three/tsl';
import { bloom } from 'three/addons/tsl/display/BloomNode.js';
import { fsr1 } from 'three/addons/tsl/display/FSR1Node.js';
import { sharpen } from 'three/addons/tsl/display/SharpenNode.js';
import { smaa } from 'three/addons/tsl/display/SMAANode.js';
import { TemporalUpscaler, biasSceneTextures, sceneTextureBias, temporalUpscale } from './TemporalUpscaler';

/** The renderer every engine module draws with (WebGPU, or its WebGL 2 backend where the browser has no WebGPU). */
export type GameRenderer = WebGPURenderer;

export interface RenderOptions {
  /** device pixels per CSS pixel the scene is drawn at */
  pixelRatio: number;
  shadows: boolean;
  bloom: boolean;
  smaa: boolean;
  /** chromatic aberration and film grain */
  extraFx: boolean;
  /**
   * The scene drawn at `renderScale` of the output and brought up to it: over time from jittered frames (WebGPU: the
   * temporal upscaler, which is also the anti-aliasing) or within the frame (the WebGL 2 backend: FSR 1).
   */
  upscale: boolean;
  /** the scene's resolution as a fraction of the output's, per axis (0.5 … 1; 1 = temporal anti-aliasing only) */
  renderScale: number;
  /** sharpening after the upscale, 0 (none) … 1 */
  sharpness: number;
}

/** RCAS takes its strength in stops of attenuation: 0 = the most it does, 2 = next to none */
const rcasStops = (sharpness: number) => 2 * (1 - Math.min(1, Math.max(0, sharpness)));

/**
 * The motion vector a material leaves in the velocity target, with the weight it is blended in by: a surface that
 * writes depth leaves its own; smoke, lamps, rain and beams (see-through, no depth) leave the surface behind them
 * as it is, since the upscaler follows the depth buffer's surface.
 */
const surfaceVelocity = Fn((builder: NodeBuilder) => {
  const m = builder.material;
  return m && m.transparent && !m.depthWrite ? vec4(0) : vec4(velocity as unknown as Node<'vec2'>, 0, 1);
});

/** the velocity target's blending: by the weight `surfaceVelocity` gives (the picture's own blending is the material's) */
const VELOCITY_BLEND = new BlendMode(THREE.NormalBlending);

/**
 * How much of a pixel is something the motion vectors do not describe: rain, smoke, sparks, lamps and beams are
 * drawn over the surface whose motion the pixel carries, and the upscaler, following that surface, would average
 * them away (a rain streak is somewhere else every frame) or drag them along it. Each such fragment leaves its
 * share here (its opacity; for an additive one its light, a streak in the night being all of the pixel long before
 * it is white), and the upscaler takes that much more of the current frame there. `userData.reactive` on a material
 * scales it (0 for wide soft layers like the cloud sea, which gain nothing and would lose the anti-aliasing of
 * every silhouette in front of them).
 */
const surfaceReactive = Fn((builder: NodeBuilder) => {
  const m = builder.material;
  if (!m || !m.transparent || m.depthWrite) return vec4(0);
  const scale = typeof m.userData.reactive === 'number' ? m.userData.reactive : 1;
  if (scale <= 0) return vec4(0);
  const share = m.blending === THREE.AdditiveBlending ? luminance(output.rgb).mul(output.a).mul(ADDITIVE_REACTIVE) : output.a;
  return vec4(1, 1, 1, share.mul(scale).saturate());
});
/** an additive fragment's light (linear) × this = its share of the pixel */
const ADDITIVE_REACTIVE = 6;

/** the bloom: what is brighter than `threshold` (… + `smooth`: fully) glows, summed over five blur levels */
const BLOOM = { strength: 0.3, radius: 0.6, threshold: 0.85, smooth: 0.25 };

/** which backend the renderer ended up with */
export type RenderBackend = 'webgpu' | 'webgl2';

/**
 * Owns the canvas' renderer, the scene, the camera and the post-processing chain, and drives the frame loop:
 * `frame(dt)` (the game's update) then the render. Post-processing: scene (HDR) → bloom → tone mapping and output
 * colour space → SMAA → chromatic aberration → vignette → grain.
 */
export class RenderHost {
  readonly scene = new THREE.Scene();
  readonly camera = new THREE.PerspectiveCamera(60, 1, 0.25, 16000);
  private pipeline!: RenderPipeline;
  private scenePass!: ReturnType<typeof pass>;
  private upscaler: TemporalUpscaler | null = null;
  private observer: ResizeObserver | null = null;
  private last = 0;
  private options: RenderOptions;
  private readonly sharpness = uniform(0);
  /** a `precompile` is running (see there) */
  private compiling = false;
  /** … and nothing is drawn meanwhile (behind the loading screen: the compile is then not paced by the frames) */
  private holding = false;
  private compileQueue: Promise<void> = Promise.resolve();

  private constructor(readonly renderer: GameRenderer, readonly canvas: HTMLCanvasElement, options: RenderOptions) {
    this.options = options;
    this.sharpness.value = rcasStops(options.sharpness);
  }

  /** Creates the renderer on `canvas` (sized by its parent element). Rejects when neither WebGPU nor WebGL 2 works. */
  static async create(canvas: HTMLCanvasElement, options: RenderOptions, forceWebGL = false) {
    const renderer = new WebGPURenderer({ canvas, antialias: false, powerPreference: 'high-performance', stencil: false, forceWebGL });
    await renderer.init();
    const host = new RenderHost(renderer, canvas, options);
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.setClearColor('#05070c');
    renderer.shadowMap.enabled = options.shadows;
    renderer.shadowMap.type = THREE.PCFShadowMap;
    host.camera.position.set(0, 600, 0);
    host.buildPipeline();
    host.resize();
    const parent = canvas.parentElement;
    if (parent && typeof ResizeObserver !== 'undefined') {
      host.observer = new ResizeObserver(() => host.resize());
      host.observer.observe(parent);
    }
    return host;
  }

  get backend(): RenderBackend {
    return (this.renderer.backend as { isWebGPUBackend?: boolean }).isWebGPUBackend ? 'webgpu' : 'webgl2';
  }

  /** Changes the drawing resolution and the effects (the settings screen). */
  configure(options: RenderOptions) {
    const was = this.options;
    const rebuild = options.bloom !== was.bloom || options.smaa !== was.smaa || options.extraFx !== was.extraFx
      || options.upscale !== was.upscale || options.renderScale !== was.renderScale || (options.sharpness > 0) !== (was.sharpness > 0);
    this.options = options;
    this.renderer.shadowMap.enabled = options.shadows;
    this.sharpness.value = rcasStops(options.sharpness);
    if (rebuild) this.buildPipeline();
    this.resize();
  }

  private buildPipeline() {
    const o = this.options;
    this.pipeline?.dispose();
    const pipeline = new RenderPipeline(this.renderer);
    // tone mapping happens inside the chain (SMAA and the lens effects work on the displayed colours)
    pipeline.outputColorTransform = false;
    const scenePass = pass(this.scene, this.camera);
    this.scenePass = scenePass;
    this.upscaler = null;
    // over time where the backend has the motion vectors' own blending (WebGPU), else within the frame
    const temporal = o.upscale && this.backend === 'webgpu';
    const spatial = o.upscale && !temporal && o.renderScale < 1;
    if (temporal || spatial) scenePass.setResolutionScale(o.renderScale);
    const colour = scenePass.getTextureNode('output');
    let hdr: Node<'vec4'> = colour;
    if (temporal) {
      const targets = mrt({ output, velocity: surfaceVelocity(), reactive: surfaceReactive() });
      targets.setBlendMode('velocity', VELOCITY_BLEND);
      targets.setBlendMode('reactive', VELOCITY_BLEND);
      scenePass.setMRT(targets);
      biasSceneTextures();
      sceneTextureBias.value = Math.log2(o.renderScale);
      // jitters the camera, gathers the frames at the output's resolution: everything after it works at full size
      this.upscaler = temporalUpscale(colour, scenePass.getTextureNode('depth'), scenePass.getTextureNode('velocity'), scenePass.getTextureNode('reactive'), this.camera);
      // (its alpha is the upscaler's own bookkeeping)
      hdr = vec4((this.upscaler as unknown as Node<'vec4'>).rgb, 1);
    }
    let lit: Node<'vec4'> = hdr;
    if (o.bloom) {
      const glow = bloom(hdr, BLOOM.strength, BLOOM.radius, BLOOM.threshold);
      glow.smoothWidth.value = BLOOM.smooth;
      lit = hdr.add(glow);
    }
    let out: Node<'vec4'> = renderOutput(lit);
    // (the temporal upscaler is the anti-aliasing; FSR 1 wants an anti-aliased picture)
    if (o.smaa && !temporal) out = smaa(out) as unknown as Node<'vec4'>;
    if (spatial) out = fsr1(out, this.sharpness) as unknown as Node<'vec4'>;
    else if (temporal && o.sharpness > 0) out = sharpen(out, this.sharpness) as unknown as Node<'vec4'>;
    if (o.bloom) out = lens(out, o.extraFx);
    pipeline.outputNode = out;
    this.pipeline = pipeline;
  }

  /**
   * Compiles the shaders of everything in the scene, for the buffers the scene pass draws into (their formats and,
   * with the upscaler, the motion vectors' target are part of each pipeline): ahead of the first frame that shows
   * a thing, not as a hitch in it. `hold`: no frame is drawn until it is done (the loading screen is up).
   */
  precompile(hold = false): Promise<void> {
    // The renderer builds each shader for the target (and motion-vector outputs) it has *when that shader's turn
    // comes*, and that is spread over many frames: the scene pass' target stays set between the frames while a
    // compile runs (`aim`), the frame loop draws to the canvas and sets it again. One compile at a time, or the
    // second would hand back the first one's state.
    const run = async () => {
      this.compiling = true;
      this.holding = hold;
      this.aim();
      try {
        await this.renderer.compileAsync(this.scene, this.camera);
      } finally {
        this.compiling = false;
        this.holding = false;
        this.renderer.setRenderTarget(null);
        this.renderer.setMRT(null);
        this.upscaler?.steadyVelocity(false);
      }
    };
    this.compileQueue = this.compileQueue.then(run, run);
    return this.compileQueue;
  }

  /** the renderer's target and outputs as the scene pass has them when it draws */
  private aim() {
    this.renderer.setRenderTarget(this.scenePass.renderTarget);
    this.renderer.setMRT(this.scenePass.getMRT());
    this.upscaler?.steadyVelocity(true);
  }

  private resize() {
    const parent = this.canvas.parentElement;
    const w = Math.max(1, parent?.clientWidth ?? window.innerWidth), h = Math.max(1, parent?.clientHeight ?? window.innerHeight);
    this.renderer.setPixelRatio(this.options.pixelRatio);
    this.renderer.setSize(w, h, false);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
  }

  /** Starts the frame loop: `frame(dt)` with the seconds since the previous frame, then the render. */
  start(frame: (dt: number) => void) {
    this.last = 0;
    void this.renderer.setAnimationLoop((ms: number) => {
      const dt = this.last ? Math.min((ms - this.last) / 1000, 0.25) : 1 / 60;
      this.last = ms;
      if (this.compiling) {
        this.renderer.setRenderTarget(null);
        this.renderer.setMRT(null);
      }
      frame(dt);
      if (!this.holding) this.pipeline.render();
      if (this.compiling) this.aim();
    });
  }

  dispose() {
    void this.renderer.setAnimationLoop(null);
    this.observer?.disconnect();
    this.pipeline?.dispose();
    this.renderer.dispose();
  }
}

/**
 * The lens: a little chromatic aberration towards the corners and film grain (`extra`), and a vignette. `input` is
 * the displayed (sRGB-encoded) picture; the vignette and the grain work on its linear values, as light would.
 */
function lens(input: Node<'vec4'>, extra: boolean): Node<'vec4'> {
  const tex = convertToTexture(input);
  const vignette = uniform(vec2(0.28, 0.62));
  return Fn(() => {
    const uv = screenUV;
    const centred = uv.sub(0.5);
    let col = tex.sample(uv).rgb;
    if (extra) {
      // red and blue part ways from the centre outwards (nothing in the middle of the frame)
      const shift = centred.mul(smoothstep(0.35, 0.75, centred.length())).mul(0.0035);
      col = vec3(tex.sample(uv.add(shift)).r, col.g, tex.sample(uv.sub(shift)).b);
    }
    col = sRGBTransferEOTF(col) as unknown as Node<'vec3'>;
    const d = centred.length();
    col = col.mul(smoothstep(0.8, vignette.x.mul(0.799), d.mul(vignette.x.add(vignette.y))));
    if (extra) {
      const n = fract(sin(dot(uv.add(fract(time)), vec2(12.9898, 78.233))).mul(43758.5453));
      // an overlay: grain shows in the mid-tones, not in the blacks
      col = col.add(n.sub(0.5).mul(0.05).mul(col.mul(float(1).sub(col)).mul(4)));
    }
    return vec4(sRGBTransferOETF(col) as unknown as Node<'vec3'>, 1);
  })();
}
