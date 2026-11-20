import type * as THREE from 'three';
import { NodeBuilder, ReferenceBaseNode, ReferenceNode, type WebGPURenderer } from 'three/webgpu';

type Stored = { buffer?: { destroy(): void } };
type Backend = {
  isWebGPUBackend?: boolean;
  get(o: object): Stored;
  delete(o: object): void;
  attributeUtils?: { destroyAttribute(attribute: THREE.BufferAttribute | THREE.InterleavedBufferAttribute): void };
};

/**
 * three.js 0.186, WebGPU backend: freeing an interleaved attribute (`geometry.dispose()`; every meshopt GLB has
 * them) destroys the GPU buffer but keeps the destroyed buffer on the shared `InterleavedBuffer`, and the next
 * object drawn with that geometry gets it back. A model's clones share their geometry, so the car picked in the
 * garage came up on the grid with destroyed buffers: WebGPU then refuses the whole frame, every frame (the picture
 * stood still on the garage). The WebGL 2 backend forgets the shared buffer; this makes the WebGPU one do the same.
 */
export function fixInterleavedDispose(renderer: WebGPURenderer) {
  const backend = renderer.backend as unknown as Backend;
  const utils = backend.attributeUtils;
  if (!backend.isWebGPUBackend || !utils) return;
  utils.destroyAttribute = (attribute) => {
    const shared = (attribute as THREE.InterleavedBufferAttribute).isInterleavedBufferAttribute ? (attribute as THREE.InterleavedBufferAttribute).data : attribute;
    // the attributes of one interleaved buffer arrive one after the other: the buffer is gone after the first
    backend.get(shared).buffer?.destroy();
    backend.delete(shared);
    backend.delete(attribute);
  };
}

type BuiltShader = { usedTimes: number };
type NodeManager = { get(o: object): { nodeBuilderState?: BuiltShader }; delete(o: object): unknown };
type RenderObjectLike = { isRenderObject?: boolean; object?: THREE.Object3D & { count?: number; isBatchedMesh?: boolean }; geometry?: THREE.BufferGeometry };
type Pipelines = { _releasePipeline?: (p: unknown) => void; _releaseProgram?: (p: unknown) => void };

/**
 * Built shaders are kept. three.js counts the objects drawn with a shader (a material's shape × a geometry's layout
 * × the lights) and throws the built shader away with the last of them: a car taken out of the garage took its
 * 22–32 shaders along, and the next car, or the same one again, built them all anew in one frame (~0.5 s, every
 * time a car was shown and at every race start). One use that never ends keeps them; the GPU's pipelines and shader
 * modules likewise. What can pile up is bounded by the shapes of material the game has: shaders whose key names
 * one object (an `InstancedMesh`, morph targets) are left to three.js, or every course's trees would stay.
 */
export function keepShaders(renderer: WebGPURenderer) {
  const inner = renderer as unknown as { _nodes?: NodeManager; _pipelines?: Pipelines };
  const nodes = inner._nodes;
  if (nodes && typeof nodes.delete === 'function' && typeof nodes.get === 'function') {
    const drop = nodes.delete.bind(nodes);
    nodes.delete = (o: object) => {
      const ro = o as RenderObjectLike;
      if (ro.isRenderObject && ro.object) {
        const own = (ro.object as THREE.InstancedMesh).isInstancedMesh || (ro.object.count ?? 1) > 1 || ro.object.isBatchedMesh || Object.keys(ro.geometry?.morphAttributes ?? {}).length > 0;
        const state = nodes.get(o).nodeBuilderState;
        if (!own && state && state.usedTimes === 1) state.usedTimes++;
      }
      return drop(o);
    };
  }
  const pipelines = inner._pipelines;
  if (pipelines?._releasePipeline && pipelines._releaseProgram) {
    pipelines._releasePipeline = () => {};
    pipelines._releaseProgram = () => {};
  }
}

type ShadowNodes = { version: number; colorNode: unknown; depthNode: unknown; positionNode: unknown };
type Caster = THREE.Material & { alphaHash?: boolean; alphaMap?: unknown; castShadowNode?: unknown; maskShadowNode?: unknown; maskNode?: unknown };
type ShadowRenderer = { _getShadowNodes?: (material: THREE.Material) => ShadowNodes; shadowMap: { transmitted?: boolean } };

/**
 * One shadow shader for all opaque casters of a shape (a vertex layout, a side, a light). three.js 0.186 draws a
 * caster with a map or a colour node into a shadow map with a colour made for that material (its map's or colour
 * node's alpha), and a node is part of a shader's key by its id: every material instance had shadow shaders of its
 * own. A vehicle's materials are cloned for each showing, so each car shown in the garage and each car of a race
 * built 3–5 shadow shaders again in the frame that first drew it, and `keepShaders` kept them all (11-19). That alpha
 * is read only to cut a shadow out (alpha test or hash, an alpha map, a mask node) or for coloured shadows
 * (`shadowMap.transmitted`): any other caster's depth is the same with the shadow material's own colour, which it
 * gets here. What it reaches into: `Renderer._getShadowNodes`; check when three.js is updated.
 */
export function shareShadowShaders(renderer: WebGPURenderer) {
  const r = renderer as unknown as ShadowRenderer;
  const own = r._getShadowNodes;
  if (typeof own !== 'function') return;
  const plain = new WeakMap<THREE.Material, ShadowNodes>();
  r._getShadowNodes = function (this: ShadowRenderer, material) {
    const nodes = own.call(this, material);
    if (nodes.colorNode === null || !plainCaster(material) || this.shadowMap.transmitted) return nodes;
    let shared = plain.get(material);
    if (!shared || shared.version !== nodes.version) plain.set(material, (shared = { ...nodes, colorNode: null }));
    return shared;
  };
}

/** A caster whose shadow is its depth alone: no cut-outs, no alpha, no shadow nodes of its own. */
export function plainCaster(material: THREE.Material) {
  const m = material as Caster;
  return !(m.alphaTest > 0) && !m.alphaHash && !m.alphaMap && !m.castShadowNode && !m.maskShadowNode && !m.maskNode;
}

type Contexts = { get(target?: THREE.RenderTarget | null, mrt?: unknown, depth?: number): unknown };

/**
 * A compile that builds what the frames then draw with. three.js 0.186 keeps a render context per (the target's
 * formats, the outputs, **how deep the `render` call is nested**), and a context's id is part of every shader's key.
 * `compileAsync` asks for the context of a call at the top; the scene is drawn one level in, by a pass inside the
 * drawing of the pipeline's screen quad. So nothing a compile built was what a frame looked for: each material's
 * shader was built by the compile and once more, in one go, by the first frame that drew it (only the GPU's
 * pipelines were found again, by their code). At a course's load that was the whole world twice.
 *
 * The returned function runs the start of a compile (`start`: the call of `compileAsync`, which takes its context
 * before it first waits) with the context of the depth at which `target` (by default `sceneTarget`) is drawn into: as
 * seen in the frames, one level in before the first of them. A shadow map is drawn one level deeper than the scene,
 * from inside its pass: a compile for a shadow pass names the map (`RenderHost.compileShadows`). It reaches into
 * `renderer._renderContexts`: check when three.js is updated (`~/.local/opt/quality/builds2.cjs`: a material's shader
 * must not be built again by the frame after a compile).
 */
export function compileAtPassDepth(renderer: WebGPURenderer, sceneTarget: () => THREE.RenderTarget | null): <T>(start: () => T, target?: THREE.RenderTarget | null) => T {
  const contexts = (renderer as unknown as { _renderContexts?: Contexts })._renderContexts;
  if (!contexts || typeof contexts.get !== 'function') return (start) => start();
  const get = contexts.get.bind(contexts);
  // (how deep each target was last drawn into; the scene's is kept when its target is made anew)
  const depths = new WeakMap<THREE.RenderTarget, number>();
  let sceneDepth = 1;
  let at: number | null = null;
  contexts.get = (target = null, mrt = null, callDepth = 0) => {
    if (at !== null) return get(target, mrt, at);
    if (target !== null && callDepth > 0) {
      depths.set(target, callDepth);
      if (target === sceneTarget()) sceneDepth = callDepth;
    }
    return get(target, mrt, callDepth);
  };
  return (start, target = null) => {
    at = target ? (depths.get(target) ?? sceneDepth + 1) : sceneDepth;
    try {
      return start();
    } finally {
      at = null;
    }
  };
}

type Reference = { node: unknown; updateReference(state: unknown): unknown; updateValue(): void };
type AsyncBuilder = {
  nodes: Set<object>;
  addNode(node: object): void;
  setBuildStage(stage: string | null): void;
  setShaderStage(stage: string | null): void;
  buildAsync(): Promise<unknown>;
};

/**
 * A shader built in the background (`compileAsync` → `NodeBuilder.buildAsync`, the garage's and the waiting room's
 * object compiles) is built from the material it is for, all through. three.js 0.186 yields to the frames between
 * the stages of such a build, and a material's textures are read through one reference node per property for ALL
 * materials (`MaterialNode`'s `_propertyCache`: `map`, `metalnessMap`, …), whose value every drawn object sets to
 * its own. So the frames in between left the build looking at whatever they drew last: the bindings were made with
 * the train's palette textures (nearest: no sampler), the code a stage later with a roadside prop's (filtered: a
 * sampler), and the pipeline failed (`Async render pipeline creation failed (renderPipeline_PaletteMaterial001…)`:
 * a sampler, depth or comparison type in the shader against another in the layout). Its draw was then skipped for
 * the rest of the session: a part of the E231 missing (11-19). Materials whose textures are filtered alike were
 * built with another material's texture without an error. Here every reference the build has met is set to the
 * build's own material and object again whenever the build changes stage, which is where it resumes after a yield.
 * It reaches into `NodeBuilder.buildAsync` / `addNode` / `setBuildStage` / `setShaderStage`: check them when three.js
 * is updated (`~/.local/opt/wt/garage-pipeline/repro.cjs` logs a texture that changed in a build, as DRIFT).
 */
export function steadyAsyncBuilds() {
  const proto = NodeBuilder.prototype as unknown as AsyncBuilder & { buildAsync: { steady?: boolean } };
  const { buildAsync, addNode, setBuildStage, setShaderStage } = proto;
  if (typeof buildAsync !== 'function' || buildAsync.steady || ![addNode, setBuildStage, setShaderStage].every((f) => typeof f === 'function')) return;
  // (the builds under way, with the references each has met; patched on the prototype, not on the builder: methods
  // of its own on one builder would make every builder's calls slower)
  const building = new Map<AsyncBuilder, Reference[]>();
  const again = (builder: AsyncBuilder) => {
    const refs = building.size ? building.get(builder) : undefined;
    if (!refs) return;
    for (const r of refs) {
      if (r.node === null) continue;
      r.updateReference(builder);
      r.updateValue();
    }
  };
  proto.addNode = function (node) {
    if (building.size && !this.nodes.has(node) && (node instanceof ReferenceNode || node instanceof ReferenceBaseNode)) building.get(this)?.push(node as unknown as Reference);
    addNode.call(this, node);
  };
  proto.setBuildStage = function (stage) {
    again(this);
    setBuildStage.call(this, stage);
  };
  proto.setShaderStage = function (stage) {
    again(this);
    setShaderStage.call(this, stage);
  };
  const steady = function (this: AsyncBuilder) {
    building.set(this, []);
    return buildAsync.call(this).finally(() => building.delete(this));
  };
  proto.buildAsync = Object.assign(steady, { steady: true });
}
