import * as THREE from 'three';
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js';

/** nodes the game moves by themselves (CarModel's GLB contract): what hangs under one stays under it */
const PIVOT = /^(body|wheel_|spin_|popup_|steer|headlight_target|anchor_)/;
/** parts found again by their name (the tailpipe: CarModel.deriveAnchors) */
const KEEP = /muffler|exhaust|tailpipe/i;

/** the geometry with plain float attributes in `matrix`'s frame (the models' are quantized integers under a scaled node) */
function baked(src: THREE.BufferGeometry, matrix: THREE.Matrix4) {
  const geo = new THREE.BufferGeometry();
  for (const name of Object.keys(src.attributes)) {
    const a = src.attributes[name] as THREE.BufferAttribute;
    const out = new Float32Array(a.count * a.itemSize);
    for (let i = 0; i < a.count; i++) for (let c = 0; c < a.itemSize; c++) out[i * a.itemSize + c] = a.getComponent(i, c);
    geo.setAttribute(name, new THREE.BufferAttribute(out, a.itemSize));
  }
  const count = src.attributes.position.count;
  const index = src.index ? Array.from(src.index.array) : Array.from({ length: count }, (_, i) => i);
  // a mirrored part: its triangles turn the other way round
  if (matrix.determinant() < 0) for (let i = 0; i < index.length; i += 3) [index[i + 1], index[i + 2]] = [index[i + 2], index[i + 1]];
  geo.setIndex(index);
  geo.applyMatrix4(matrix);
  return geo;
}

/**
 * Fewer draw calls for a loaded model: the meshes of one rigid part (everything under the same moving node) that
 * share a material and a vertex layout become one mesh. A car arrives as ~50 meshes and every one is a draw call in
 * the picture and in each shadow map. Call once on the template, before it is cloned. Returns the meshes before and after.
 */
export function mergeRigidParts(scene: THREE.Object3D) {
  scene.updateMatrixWorld(true);
  const groups = new Map<string, { pivot: THREE.Object3D; material: THREE.Material; meshes: THREE.Mesh[] }>();
  let before = 0;
  scene.traverse((o) => {
    const m = o as THREE.Mesh;
    if (!m.isMesh) return;
    before++;
    if ((m as unknown as THREE.SkinnedMesh).isSkinnedMesh || Array.isArray(m.material) || m.children.length || KEEP.test(m.name) || PIVOT.test(m.name)) return;
    if (Object.keys(m.geometry.morphAttributes).length || m.geometry.groups.length > 1) return;
    let pivot: THREE.Object3D = m.parent ?? scene;
    while (pivot !== scene && pivot.parent && !PIVOT.test(pivot.name)) pivot = pivot.parent;
    const key = `${pivot.id}|${m.material.uuid}|${Object.keys(m.geometry.attributes).sort().join(',')}`;
    let g = groups.get(key);
    if (!g) groups.set(key, (g = { pivot, material: m.material, meshes: [] }));
    g.meshes.push(m);
  });
  let removed = 0;
  const toPivot = new THREE.Matrix4();
  for (const g of groups.values()) {
    if (g.meshes.length < 2) continue;
    toPivot.copy(g.pivot.matrixWorld).invert();
    const merged = mergeGeometries(g.meshes.map((m) => baked(m.geometry, new THREE.Matrix4().multiplyMatrices(toPivot, m.matrixWorld))), false);
    if (!merged) continue;
    const mesh = new THREE.Mesh(merged, g.material);
    mesh.name = `merged_${g.material.name || 'part'}`;
    g.pivot.add(mesh);
    for (const m of g.meshes) m.removeFromParent();
    removed += g.meshes.length - 1;
  }
  scene.updateMatrixWorld(true);
  return { before, after: before - removed };
}
