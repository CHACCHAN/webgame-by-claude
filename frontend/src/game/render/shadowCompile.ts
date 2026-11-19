import * as THREE from 'three';
import type { WebGPURenderer } from 'three/webgpu';
import { plainCaster } from './threeFixes';

/**
 * A compile for the shadow maps (`RenderHost.compileShadows`). three.js draws no shadow map while it compiles, so a
 * vehicle compiled before it is shown still built its casters' shadow shaders in the frame that first drew it into
 * a map (11-19). A light's map is drawn with that light's shadow material standing in for every caster's own, set
 * per caster (`Renderer.renderObject`: its side, see-through or not, …), into the map, at one level deeper than the
 * scene; a compile of stand-ins carrying a copy of that material, set the same way, for the same target at the same
 * depth, builds exactly the shaders and pipelines the frame then looks for. It reaches into how three.js 0.186 sets
 * the shadow material (`Renderer.renderObject`, `_getShadowNodes`): check when three.js is updated (step.cjs in
 * ~/.local/opt/wt/first-showing lists the shadow shaders a frame still builds).
 */

/** a shadow map as the frames draw it: the light's shadow material and the map */
export interface ShadowPass {
  material: THREE.Material;
  target: THREE.RenderTarget;
}

type Overridden = { overrideMaterial: (THREE.Material & { isShadowPassMaterial?: boolean }) | null };

/** Notes every shadow map's pass as the frames draw it, by its shadow camera. */
export function watchShadowPasses(renderer: WebGPURenderer): Map<THREE.Camera, ShadowPass> {
  const passes = new Map<THREE.Camera, ShadowPass>();
  const r = renderer as unknown as { render(scene: THREE.Object3D, camera: THREE.Camera): unknown };
  const render = r.render.bind(renderer);
  r.render = (scene, camera) => {
    const override = (scene as unknown as Overridden).overrideMaterial;
    if (override?.isShadowPassMaterial) {
      const target = renderer.getRenderTarget();
      const known = passes.get(camera);
      if (target && (known?.material !== override || known.target !== target)) passes.set(camera, { material: override, target });
    }
    return render(scene, camera);
  };
  return passes;
}

const SHADOW_SIDE: Record<number, THREE.Side> = { [THREE.FrontSide]: THREE.BackSide, [THREE.BackSide]: THREE.FrontSide, [THREE.DoubleSide]: THREE.DoubleSide };

type Source = THREE.Material & {
  shadowSide: THREE.Side | null;
  allowOverride?: boolean;
  transmission?: number;
  transmissionNode?: unknown;
  backdropNode?: unknown;
  positionNode?: unknown;
  castShadowPositionNode?: unknown;
  depthNode?: unknown;
  alphaMap?: unknown;
  displacementMap?: unknown;
  displacementScale?: number;
  displacementBias?: number;
};

/** the part of a geometry that is in a shader's key (three.js `RenderObject.getGeometryCacheKey`) */
function layout(g: THREE.BufferGeometry) {
  let key = '';
  for (const name of Object.keys(g.attributes).sort()) {
    const a = g.attributes[name] as THREE.BufferAttribute & Partial<THREE.InterleavedBufferAttribute>;
    key += `${name},${a.data?.stride ?? ''},${a.offset ?? ''},${a.itemSize},${a.normalized ? 'n' : ''};`;
  }
  return key + (g.index ? 'index' : '');
}

/**
 * Stand-ins for the casters under `what` as `pass` draws them: one mesh per shape of shader (the geometry's layout,
 * the side, see-through or not, taking shadows or not) with a copy of the light's shadow material set as three.js
 * sets it for that caster. Casters with a shadow shader of their own (cut-outs, moved vertices, skins, instances,
 * morph targets) are left to the frame.
 */
export function shadowProxies(what: THREE.Object3D, pass: ShadowPass, vsm: boolean): { root: THREE.Object3D; dispose(): void } {
  const root = new THREE.Group();
  root.matrixWorldAutoUpdate = false;
  const made: THREE.Material[] = [];
  const shapes = new Set<string>();
  const base = pass.material as Source;
  what.updateMatrixWorld();
  what.traverseVisible((o) => {
    const mesh = o as THREE.Mesh & { isSkinnedMesh?: boolean; isInstancedMesh?: boolean; isBatchedMesh?: boolean };
    if (!mesh.isMesh || !mesh.castShadow || mesh.isSkinnedMesh || mesh.isInstancedMesh || mesh.isBatchedMesh || Object.keys(mesh.geometry.morphAttributes).length) return;
    for (const m of (Array.isArray(mesh.material) ? mesh.material : [mesh.material]) as Source[]) {
      if (!plainCaster(m) || m.allowOverride === false || m.positionNode || m.castShadowPositionNode || m.depthNode || m.displacementMap) continue;
      const side = m.shadowSide ?? (vsm ? m.side : SHADOW_SIDE[m.side]);
      // (three.js' own expression, to the value: a caster without transmission leaves `undefined` or `null` there, and
      // the key spells either out, apart from `false`)
      const transparent: unknown = m.transparent || (m.transmission as number) > 0 || (m.transmissionNode && (m.transmissionNode as { isNode?: boolean }).isNode) || (m.backdropNode && (m.backdropNode as { isNode?: boolean }).isNode);
      const shape = `${layout(mesh.geometry)}|${side}|${String(transparent)}|${mesh.receiveShadow}|${m.displacementScale}|${m.displacementBias}`;
      if (shapes.has(shape)) continue;
      shapes.add(shape);
      const mat = base.clone() as Source & { isShadowPassMaterial?: boolean };
      mat.isShadowPassMaterial = true;
      // (what three.js has added to the light's material while drawing casters with it, in the same order: a
      // material's own properties are part of a shader's key; `copy` takes only those a new material has)
      for (const k of Object.keys(base)) if (!(k in mat)) (mat as unknown as Record<string, unknown>)[k] = (base as unknown as Record<string, unknown>)[k];
      // (as `Renderer.renderObject` sets them, in its order)
      Object.assign(mat, { alphaTest: m.alphaTest, alphaMap: m.alphaMap, displacementMap: m.displacementMap, displacementScale: m.displacementScale, displacementBias: m.displacementBias, transparent, side });
      made.push(mat);
      const proxy = new THREE.Mesh(mesh.geometry, mat);
      proxy.matrixAutoUpdate = false;
      proxy.matrixWorldAutoUpdate = false;
      proxy.matrixWorld.copy(mesh.matrixWorld);
      proxy.castShadow = true;
      proxy.receiveShadow = mesh.receiveShadow;
      proxy.frustumCulled = false;
      root.add(proxy);
    }
  });
  return { root, dispose: () => made.forEach((m) => m.dispose()) };
}
