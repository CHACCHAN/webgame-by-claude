import * as THREE from 'three';
import { MeshStandardNodeMaterial } from 'three/webgpu';
import { Fn, attribute, mat4, materialColor, mix, normalLocal, positionLocal, positionPrevious, smoothstep, texture, transformNormal, uniform, uv, vec4 } from 'three/tsl';
import type { Vec3, Vec4 } from './tslNoise';

/**
 * Fixed instances (scenery that never moves) drawn as plain meshes. The WebGPU renderer builds a shader of its own
 * for every `InstancedMesh` (its instance buffer is part of the built shader), so hundreds of tree chunks meant
 * hundreds of builds, each a hitch when its chunk first came into view. Here the matrices and tints are attributes
 * of the geometry, read by name: every mesh of a material shares one shader. And a draw call costs this renderer
 * some 30 µs of main thread, so the chunks of a level are one mesh (`ChunkedLods`).
 */

const twins = new WeakMap<THREE.Material, MeshStandardNodeMaterial>();

/** the node material with `src`'s values (its own copy(): a plain material has no node slots for the node material's to read) */
function nodeTwin(src: THREE.MeshStandardMaterial) {
  const mat = new MeshStandardNodeMaterial();
  THREE.MeshStandardMaterial.prototype.copy.call(mat, src);
  cutOut(mat);
  return mat;
}

/**
 * An alpha-tested map cut out by a mask node instead of `alphaTest`. The renderer draws every shadow caster with one
 * shared shadow material and copies the caster's `alphaTest` onto it; each change between "tested" and "not tested"
 * marks that material as changed, and every caster then recomputes its cache key every frame (3 ms a frame here).
 * The mask cuts the picture and the shadow alike and changes nothing on the shared material.
 */
function cutOut(mat: MeshStandardNodeMaterial) {
  if (!mat.map || !(mat.alphaTest > 0)) return;
  // (the map itself, not the material's colour node: in a shadow map that would be the shadow material's)
  mat.maskNode = texture(mat.map, uv()).a.greaterThanEqual(mat.alphaTest);
  mat.alphaTest = 0;
}

/** `src` as it is, or (alpha-tested) its twin that cuts out by a mask: see `cutOut`. Use the returned material from then on. */
export function cutout(src: THREE.MeshStandardMaterial): THREE.MeshStandardMaterial {
  return src.map && src.alphaTest > 0 ? (nodeTwin(src) as unknown as THREE.MeshStandardMaterial) : src;
}

/**
 * A round clearing among the chunked instances (the trees): x, z of its centre and its radius (m; negative: none).
 * Instances standing inside shrink to nothing, with their shadows, over the last three metres of the radius. The
 * garage and the waiting room open one around what they show: their camera stands off the road, where the trees are.
 */
export const clearing = uniform(new THREE.Vector3(0, 0, -10));

/**
 * The material that draws `staticInstances` like `src` (a twin per source material): each vertex goes through its
 * instance's matrix and the colour is multiplied by the instance's tint.
 */
export function instancedMaterial(src: THREE.MeshStandardMaterial): MeshStandardNodeMaterial {
  let mat = twins.get(src);
  if (mat) return mat;
  mat = nodeTwin(src);
  const col = (k: number) => attribute(`instM${k}`, 'vec4') as unknown as Vec4;
  const matrix = mat4(col(0), col(1), col(2), col(3));
  mat.positionNode = Fn(() => {
    normalLocal.assign(transformNormal(normalLocal, matrix));
    // an instance inside the clearing is drawn at no size, at its foot
    const foot = col(3).xyz;
    const size = smoothstep(clearing.z.sub(3), clearing.z, foot.xz.sub(clearing.xy).length());
    // (the motion vectors' side: where the vertex was a frame ago, which for fixed instances is where it is)
    positionPrevious.assign(mix(foot, matrix.mul(vec4(positionPrevious, 1)).xyz, size));
    return mix(foot, matrix.mul(vec4(positionLocal, 1)).xyz, size);
  })();
  // (the map is part of the material's colour; the vertex colours are multiplied in by the material itself)
  const base = materialColor as unknown as Vec4;
  mat.colorNode = vec4(base.rgb.mul(attribute('instColor', 'vec3') as unknown as Vec3), base.a);
  twins.set(src, mat);
  return mat;
}

/** `base` with room for `capacity` instances: the matrices (instM0…3) and the tints (instColor), all empty */
function instanceGeometry(base: THREE.BufferGeometry, capacity: number) {
  const geo = new THREE.InstancedBufferGeometry();
  geo.index = base.index;
  for (const name of Object.keys(base.attributes)) geo.setAttribute(name, base.attributes[name]);
  // (not DynamicDrawUsage: the renderer uploads a dynamic buffer every frame, changed or not)
  const matrices = new THREE.InstancedInterleavedBuffer(new Float32Array(capacity * 16), 16, 1);
  for (let k = 0; k < 4; k++) geo.setAttribute(`instM${k}`, new THREE.InterleavedBufferAttribute(matrices, 4, k * 4));
  const tints = new THREE.InstancedBufferAttribute(new Float32Array(capacity * 3), 3);
  geo.setAttribute('instColor', tints);
  geo.instanceCount = 0;
  return { geo, matrices, tints };
}

interface Chunk {
  matrices: Float32Array;
  tints: Float32Array;
  count: number;
  center: THREE.Vector3;
  near: boolean;
}

/**
 * Chunks of instances, each drawn with the detailed or with the simple geometry by its distance from the camera:
 * two draw calls in all (one mesh per level; a chunk's instances are copied into the level it is at when a chunk
 * changes level). Nothing is culled by the frustum: the far level is a few triangles per instance.
 */
export class ChunkedLods {
  readonly near: THREE.Mesh;
  readonly far: THREE.Mesh;
  private chunks: Chunk[] = [];
  private levels: ReturnType<typeof instanceGeometry>[];
  private dirty = true;

  constructor(
    nearGeometry: THREE.BufferGeometry,
    farGeometry: THREE.BufferGeometry,
    material: THREE.MeshStandardMaterial,
    chunks: { matrices: THREE.Matrix4[]; colors?: THREE.Color[] }[],
    /** a chunk nearer than this (to its centre) is drawn detailed */
    private readonly distance: number,
  ) {
    const p = new THREE.Vector3();
    let total = 0;
    for (const c of chunks) {
      const n = c.matrices.length;
      if (!n) continue;
      total += n;
      const matrices = new Float32Array(n * 16), tints = new Float32Array(n * 3).fill(1);
      const box = new THREE.Box3();
      c.matrices.forEach((m, i) => {
        m.toArray(matrices, i * 16);
        c.colors?.[i]?.toArray(tints, i * 3);
        box.expandByPoint(p.setFromMatrixPosition(m));
      });
      this.chunks.push({ matrices, tints, count: n, center: box.getCenter(new THREE.Vector3()), near: false });
    }
    const mat = instancedMaterial(material) as unknown as THREE.Material;
    this.levels = [instanceGeometry(nearGeometry, total), instanceGeometry(farGeometry, total)];
    this.near = new THREE.Mesh(this.levels[0].geo, mat);
    this.far = new THREE.Mesh(this.levels[1].geo, mat);
    this.near.frustumCulled = this.far.frustumCulled = false;
  }

  update(camera: THREE.Vector3) {
    for (const c of this.chunks) {
      // hysteresis: a chunk right at the switch distance must not flap between the levels every frame
      const near = c.center.distanceTo(camera) < this.distance + (c.near ? 60 : 0);
      if (near !== c.near) {
        c.near = near;
        this.dirty = true;
      }
    }
    if (!this.dirty) return;
    this.dirty = false;
    this.levels.forEach((level, k) => {
      let n = 0;
      for (const c of this.chunks) {
        if (c.near !== (k === 0)) continue;
        (level.matrices.array as Float32Array).set(c.matrices, n * 16);
        (level.tints.array as Float32Array).set(c.tints, n * 3);
        n += c.count;
      }
      level.geo.instanceCount = n;
      level.matrices.clearUpdateRanges();
      level.matrices.addUpdateRange(0, n * 16);
      level.matrices.needsUpdate = true;
      level.tints.clearUpdateRanges();
      level.tints.addUpdateRange(0, n * 3);
      level.tints.needsUpdate = true;
    });
    this.near.visible = this.levels[0].geo.instanceCount > 0;
    this.far.visible = this.levels[1].geo.instanceCount > 0;
  }
}
