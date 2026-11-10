import * as THREE from 'three';
import { RenderPipeline, WebGPURenderer, type Node } from 'three/webgpu';
import { Fn, convertToTexture, dot, float, fract, pass, renderOutput, sRGBTransferEOTF, sRGBTransferOETF, screenUV, sin, smoothstep, time, uniform, vec2, vec3, vec4 } from 'three/tsl';
import { bloom } from 'three/addons/tsl/display/BloomNode.js';
import { smaa } from 'three/addons/tsl/display/SMAANode.js';

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
}

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
  private observer: ResizeObserver | null = null;
  private last = 0;
  private options: RenderOptions;

  private constructor(readonly renderer: GameRenderer, readonly canvas: HTMLCanvasElement, options: RenderOptions) {
    this.options = options;
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
    const rebuild = options.bloom !== this.options.bloom || options.smaa !== this.options.smaa || options.extraFx !== this.options.extraFx;
    this.options = options;
    this.renderer.shadowMap.enabled = options.shadows;
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
    const hdr = scenePass.getTextureNode('output');
    let lit: Node<'vec4'> = hdr;
    if (o.bloom) {
      const glow = bloom(hdr, BLOOM.strength, BLOOM.radius, BLOOM.threshold);
      glow.smoothWidth.value = BLOOM.smooth;
      lit = hdr.add(glow);
    }
    let out: Node<'vec4'> = renderOutput(lit);
    if (o.smaa) out = smaa(out) as unknown as Node<'vec4'>;
    if (o.bloom) out = lens(out, o.extraFx);
    pipeline.outputNode = out;
    this.pipeline = pipeline;
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
      frame(dt);
      this.pipeline.render();
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
