import * as THREE from 'three';
import { BlendMode, RenderPipeline, WebGPURenderer, type Node, type NodeBuilder, type TextureNode } from 'three/webgpu';
import { Fn, convertToTexture, dot, float, fract, luminance, mrt, output, pass, renderOutput, sRGBTransferEOTF, sRGBTransferOETF, screenUV, sin, smoothstep, time, uniform, vec2, vec3, vec4, velocity } from 'three/tsl';
import { bloom } from 'three/addons/tsl/display/BloomNode.js';
import { fsr1 } from 'three/addons/tsl/display/FSR1Node.js';
import { sharpen } from 'three/addons/tsl/display/SharpenNode.js';
import { smaa } from 'three/addons/tsl/display/SMAANode.js';
import { ambientOcclusion } from './ambientOcclusion';
import { graded } from './grade';
import { beamCones, updateVolume, volumetricLights } from './volumetricLights';
import { compileAtPassDepth, fixInterleavedDispose, keepShaders } from './threeFixes';
import { ErrorBurst } from './backendChoice';
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
  /** ambient occlusion: creases, the underside of cars, where things meet the ground */
  ao: boolean;
  /** the lights' glow in the haze */
  volumetric: boolean;
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

/**
 * The ambient occlusion (`ambientOcclusion`, at half the output's size) and above which light (linear) a pixel is
 * left alone: the occlusion is laid over the finished picture, and a lamp or a lit pool of road is not ambient light.
 */
const AO = { scale: 0.5, radius: 1.4, maxScreen: 0.25, samples: 8, strength: 1.6, keepAbove: [1.2, 3.5] as const };

/** the size of the lights' glow in the haze (`volumetricLights`), as a fraction of the output's per axis */
const VOLUME_SCALE = 0.4;

/** which backend the renderer ended up with */
export type RenderBackend = 'webgpu' | 'webgl2';

/** what `RenderHost.create`'s `onTrouble` reports */
export type RenderTrouble = 'lost' | 'errors' | 'memory';

/** compiles side by side while the picture is held (`RenderHost.lanes`) */
const COMPILE_LANES = 6;

/**
 * Owns the canvas' renderer, the scene, the camera and the post-processing chain, and drives the frame loop:
 * `frame(dt)` (the game's update) then the render. Post-processing: scene (HDR) → bloom → tone mapping (AgX), output
 * colour space and the grade → SMAA → chromatic aberration → vignette → grain.
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
  /** runs the start of a compile so that it builds for the scene pass (`compileAtPassDepth`) */
  private forPass: <T>(start: () => T) => T = (start) => start();
  /** called once after the next frame that was drawn (see `precompile`) */
  private drawn: (() => void) | null = null;
  private renderThrew: ((err: unknown) => void) | null = null;

  private constructor(readonly renderer: GameRenderer, readonly canvas: HTMLCanvasElement, options: RenderOptions) {
    this.options = options;
    this.sharpness.value = rcasStops(options.sharpness);
  }

  /**
   * Creates the renderer on `canvas` (sized by its parent element): WebGPU, or the WebGL 2 backend when `forceWebGL`
   * or when the browser gives no WebGPU device (three.js then takes its fallback by itself). Rejects when the renderer
   * could not be built: on WebGPU the caller tries again with `forceWebGL` on a new canvas (one that has given a
   * `webgpu` context gives no `webgl2` one). `onTrouble`: the running renderer stopped being usable
   * (`render/backendChoice.ts` decides what follows): the device or context is lost (nothing is drawn any more), or
   * the WebGPU device reports errors in a burst, or that it is out of memory.
   */
  static async create(canvas: HTMLCanvasElement, options: RenderOptions, forceWebGL = false, onTrouble?: (kind: RenderTrouble, message: string) => void) {
    // (`?gputime`: the passes' GPU times, for tools/perf-pass.cjs)
    const renderer = new WebGPURenderer({ canvas, antialias: false, powerPreference: 'high-performance', stencil: false, forceWebGL, trackTimestamp: new URLSearchParams(location.search).has('gputime') });
    try {
      await renderer.init();
      fixInterleavedDispose(renderer);
      keepShaders(renderer);
      const host = new RenderHost(renderer, canvas, options);
      host.forPass = compileAtPassDepth(renderer, () => host.scenePass?.renderTarget ?? null);
      renderer.toneMapping = THREE.AgXToneMapping;
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
      if (onTrouble) host.watch(onTrouble);
      return host;
    } catch (err) {
      try {
        renderer.dispose();
      } catch {
        // a renderer that never came up has nothing to free
      }
      throw err;
    }
  }

  /** three.js only logs these two and, on a loss, stops drawing: tell the page as well */
  private watch(onTrouble: (kind: RenderTrouble, message: string) => void) {
    // (three's typings give `onError` a string; the backends pass an object)
    const r = this.renderer as unknown as { onDeviceLost: (info: { message?: string }) => void; onError: (info: { type?: string; message?: string }) => void };
    const lost = r.onDeviceLost, report = r.onError;
    r.onDeviceLost = (info) => {
      lost.call(r, info);
      onTrouble('lost', String(info?.message ?? ''));
    };
    if (this.backend !== 'webgpu') return;
    // the device's uncaptured errors, and a render that throws: each is a frame (or a part of one) not drawn
    const burst = new ErrorBurst();
    const count = (what: string) => burst.add(performance.now() / 1000) && onTrouble('errors', what);
    r.onError = (info) => {
      report.call(r, info);
      // out of video memory is not a broken backend: the game gives back what it only keeps (`Game.releaseKept`)
      if (/OutOfMemory/i.test(info?.type ?? '')) onTrouble('memory', String(info?.message ?? ''));
      else count(`${info?.type ?? 'GPUError'}: ${info?.message ?? ''}`);
    };
    this.renderThrew = (err) => count(String(err));
  }

  get backend(): RenderBackend {
    return (this.renderer.backend as { isWebGPUBackend?: boolean }).isWebGPUBackend ? 'webgpu' : 'webgl2';
  }

  /** Drawn by the processor (SwiftShader, llvmpipe: no GPU)? Then nothing but the game itself should draw. */
  get software(): boolean {
    const gl = (this.renderer.backend as { gl?: WebGL2RenderingContext }).gl;
    if (!gl) return false;
    const info = gl.getExtension('WEBGL_debug_renderer_info');
    return /swiftshader|llvmpipe|softpipe|software/i.test(info ? String(gl.getParameter(info.UNMASKED_RENDERER_WEBGL)) : '');
  }

  /**
   * The WebGPU device the game is drawn with (null on the WebGL 2 backend): what else draws on the page draws with
   * it (the interface's grains, ui/fx), not with a context of its own.
   */
  get gpuDevice(): unknown {
    return this.backend === 'webgpu' ? ((this.renderer.backend as { device?: unknown }).device ?? null) : null;
  }

  /** Changes the drawing resolution and the effects (the settings screen). */
  configure(options: RenderOptions) {
    const was = this.options;
    const rebuild = options.bloom !== was.bloom || options.smaa !== was.smaa || options.extraFx !== was.extraFx || options.ao !== was.ao || options.volumetric !== was.volumetric
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
    beamCones.value = o.volumetric ? 0 : 1;
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
    // (the occlusion goes in where the picture is put together, not in a pass of its own: a full-size pass less)
    if (o.ao) lit = this.occluded(hdr, scenePass.getTextureNode('depth'));
    // (the lights' glow in the haze lies over the scene, occluded or not)
    if (o.volumetric) lit = lit.add(vec4(volumetricLights(scenePass.getTextureNode('depth'), this.camera, VOLUME_SCALE).sample(screenUV).rgb, 0));
    if (o.bloom) {
      const glow = bloom(hdr, BLOOM.strength, BLOOM.radius, BLOOM.threshold);
      glow.smoothWidth.value = BLOOM.smooth;
      lit = lit.add(glow);
    }
    let out: Node<'vec4'> = graded(renderOutput(lit));
    // (the temporal upscaler is the anti-aliasing; FSR 1 wants an anti-aliased picture)
    if (o.smaa && !temporal) out = smaa(out) as unknown as Node<'vec4'>;
    if (spatial) out = fsr1(out, this.sharpness) as unknown as Node<'vec4'>;
    else if (temporal && o.sharpness > 0) out = sharpen(out, this.sharpness) as unknown as Node<'vec4'>;
    if (o.bloom) out = lens(out, o.extraFx);
    pipeline.outputNode = out;
    this.pipeline = pipeline;
  }

  /** `colour` darkened by the ambient occlusion worked out from `depth` (as part of whatever samples the returned node) */
  private occluded(colour: Node<'vec4'>, depth: TextureNode): Node<'vec4'> {
    const shade = ambientOcclusion(depth, this.camera, AO);
    return Fn(() => {
      const c = vec4(colour).toVar();
      const lit = smoothstep(AO.keepAbove[0], AO.keepAbove[1], luminance(c.rgb));
      return vec4(c.rgb.mul(shade.sample(screenUV).r.add(lit).min(1)), c.a);
    })();
  }

  /**
   * Compiles the shaders of everything in the scene, for the buffers the scene pass draws into (their formats and,
   * with the upscaler, the motion vectors' target are part of each pipeline): ahead of the first frame that shows
   * a thing, not as a hitch in it. `hold`: no frame is drawn until it is done (the loading screen is up). `what`: one
   * object that is not in the scene yet (a model about to be shown), compiled under the scene's lights.
   */
  precompile(hold = false, what: THREE.Object3D = this.scene): Promise<void> {
    // The renderer builds each shader for the target (and motion-vector outputs) it has *when that shader's turn
    // comes*, and that is spread over many frames: the scene pass' target stays set between the frames while a
    // compile runs (`aim`), the frame loop draws to the canvas and sets it again. One compile at a time, or the
    // second would hand back the first one's state.
    const run = async () => {
      this.compiling = true;
      this.holding = hold;
      this.aim();
      try {
        await Promise.all((hold ? this.lanes(what) : [what]).map((part) => this.forPass(() => this.renderer.compileAsync(part, this.camera, this.scene))));
        // three.js draws no shadow map while it compiles. A map first met in a compile therefore gets its depth
        // texture from a material's binding, as an ordinary texture, and the first drawing into the map replaces it
        // by a new one on the GPU. What three.js then takes for unchanged (a plain material on a thing that stands
        // still, no motion vectors) keeps its bind group with the destroyed texture: validation errors in every
        // frame, from the moment the headlights' map was first drawn (a race's start; the sun's is drawn in the
        // first frame anyway). So every map is drawn in the next frame, in which each of those bind groups is new.
        this.scene.traverse((o) => {
          const shadow = (o as THREE.DirectionalLight).isLight && o.castShadow ? (o as THREE.DirectionalLight).shadow : null;
          if (shadow) shadow.needsUpdate = true;
        });
      } finally {
        this.compiling = false;
        this.holding = false;
        this.renderer.setRenderTarget(null);
        this.renderer.setMRT(null);
        this.upscaler?.steadyVelocity(false);
      }
      // What a compile leaves to the first frame (the shadow maps' own shaders, the passes after the scene's) is
      // built in that frame, at once: behind the loading screen it is waited for here, or the title would stand
      // still under it. (A tab in the background draws no frame: not waited for longer than a moment.)
      if (hold) {
        await new Promise<void>((resolve) => {
          const done = () => {
            this.drawn = null;
            clearTimeout(late);
            resolve();
          };
          const late = setTimeout(done, 1500);
          this.drawn = done;
        });
      }
    };
    this.compileQueue = this.compileQueue.then(run, run);
    return this.compileQueue;
  }

  /**
   * `what` in parts that are compiled side by side. A compile takes its objects one after the other and waits for
   * each one's pipeline before it starts on the next; those waits were half of a course's compile (53 pipelines,
   * 3.1 of 6.3 s), and the GPU process can make several at a time. Behind the loading screen, where no frame has to
   * fit in between, `COMPILE_LANES` compiles run at once, each on its share of the drawn objects; the shares go by
   * material, so that objects with one shader meet in one lane and the second finds what the first built.
   */
  private lanes(what: THREE.Object3D): THREE.Object3D[] {
    what.updateMatrixWorld();
    const lanes: THREE.Object3D[] = [];
    const lane = new Map<THREE.Material, number>();
    let next = 0;
    const walk = (o: THREE.Object3D) => {
      if (!o.visible) return;
      const material = (o as THREE.Mesh).material;
      if (!(o as THREE.Mesh).geometry || !material) {
        for (const child of o.children) walk(child);
        return;
      }
      // (a drawn object goes with what hangs on it: the compile walks down from it)
      const first = Array.isArray(material) ? material[0] : material;
      let k = lane.get(first);
      if (k === undefined) lane.set(first, (k = next++ % COMPILE_LANES));
      // a stand-in parent: the objects stay where they are in the scene, and their own places are up to date
      const part = (lanes[k] ??= Object.assign(new THREE.Object3D(), { matrixWorldAutoUpdate: false }));
      part.children.push(o);
    };
    walk(what);
    return lanes.filter(Boolean);
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
      if (this.options.volumetric) updateVolume(this.camera);
      if (!this.holding) {
        try {
          this.pipeline.render();
        } catch (err) {
          // (a backend that throws on every frame: counted with the device's errors, see `watch`)
          this.renderThrew?.(err);
          throw err;
        }
        this.drawn?.();
      }
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
