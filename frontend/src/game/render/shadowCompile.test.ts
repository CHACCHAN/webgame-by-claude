import { describe, expect, it } from 'vitest';
import * as THREE from 'three';
import { MeshPhysicalNodeMaterial, NodeMaterial, Renderer } from 'three/webgpu';
import { vec4 } from 'three/tsl';
import { shadowProxies, type ShadowPass } from './shadowCompile';

/** a light's shadow material as three.js 0.186 makes it (`ShadowBaseNode`) */
function lightMaterial() {
  const m = new NodeMaterial();
  m.colorNode = vec4(0, 0, 0, 1);
  Object.assign(m, { isShadowPassMaterial: true });
  m.name = 'ShadowMaterial';
  m.blending = THREE.NoBlending;
  m.fog = false;
  return m;
}

/** a material's part of a shader's key as three.js spells it (`RenderObject.getMaterialCacheKey`), with the names */
function key(m: THREE.Material) {
  const keys = Object.keys(m);
  for (let p = Object.getPrototypeOf(m); p; p = Object.getPrototypeOf(p)) {
    const d = Object.getOwnPropertyDescriptors(p);
    for (const k in d) if (typeof d[k].get === 'function') keys.push(k);
  }
  let out = (m as NodeMaterial).customProgramCacheKey();
  for (const k of keys) {
    if (/^(is[A-Z]|_)|^(visible|version|uuid|name|opacity|userData)$/.test(k)) continue;
    const v = (m as unknown as Record<string, unknown>)[k];
    let s: string;
    if (v !== null && typeof v === 'number') s = k === 'side' ? String(v) : v !== 0 ? '1' : '0';
    else if (v !== null && typeof v === 'object') s = `{${(v as THREE.Texture).isTexture ? (v as THREE.Texture).mapping : ''}}`;
    else s = String(v);
    out += `${k}:${s},`;
  }
  return out;
}

const camera = new THREE.PerspectiveCamera();

/** the keys a draw of `mesh` asks for, by three.js' own `renderObject` (a shadow map's: `override` set on the scene) */
function drawn(mesh: THREE.Mesh, override: THREE.Material | null) {
  const asked: string[] = [];
  const renderer = {
    _handleObjectFunction: (_o: THREE.Object3D, material: THREE.Material) => void asked.push(`side ${material.side}: ${key(material)}`),
    // (`shareShadowShaders`: a plain caster adds nothing of its own)
    _getShadowNodes: () => ({ colorNode: null, depthNode: null, positionNode: null }),
    shadowMap: { type: THREE.PCFShadowMap },
    _currentSourceMaterial: null,
  };
  const scene = new THREE.Scene();
  scene.overrideMaterial = override;
  const render = Renderer.prototype.renderObject as unknown as (...a: unknown[]) => void;
  render.call(renderer, mesh, scene, camera, mesh.geometry, mesh.material, null, null);
  return asked;
}

const box = () => new THREE.BoxGeometry(1, 1, 1);
const casters = () => {
  const meshes = [
    new THREE.Mesh(box(), new THREE.MeshStandardMaterial({ map: new THREE.Texture(), side: THREE.DoubleSide })),
    new THREE.Mesh(box(), new MeshPhysicalNodeMaterial({ clearcoat: 1 })),
    new THREE.Mesh(box(), new THREE.MeshStandardMaterial({ transparent: true, opacity: 0.4 })),
    new THREE.Mesh(box(), new THREE.MeshStandardMaterial({ transparent: true, side: THREE.DoubleSide })),
    new THREE.Mesh(box(), new THREE.MeshBasicMaterial()),
  ];
  for (const m of meshes) {
    m.castShadow = true;
    m.receiveShadow = true;
  }
  return meshes;
};

describe('the shadow compile stand-ins', () => {
  it('ask for exactly the shaders a frame draws their casters with', () => {
    const base = lightMaterial();
    const what = new THREE.Group();
    const meshes = casters();
    what.add(...meshes);
    // (the frames have drawn with the light's material before: what it has gathered stays on it)
    for (const m of meshes) drawn(m, base);
    const pass: ShadowPass = { material: base, target: new THREE.RenderTarget(1, 1) };
    const proxies = shadowProxies(what, pass, false);
    expect(proxies.root.children).toHaveLength(meshes.length);
    for (const [i, mesh] of meshes.entries()) {
      const proxy = proxies.root.children[i] as THREE.Mesh;
      expect(drawn(proxy, null)).toEqual(drawn(mesh, base));
      expect(proxy.matrixWorld.equals(mesh.matrixWorld)).toBe(true);
    }
    proxies.dispose();
  });

  it('a caster without transmission leaves an undefined or null `transparent`: three.js keys those apart from false', () => {
    const base = lightMaterial();
    const [standard, physical] = casters();
    expect(drawn(standard, base)[0]).toContain('transparent:undefined');
    expect(drawn(physical, base)[0]).toContain('transparent:null');
  });

  it('one stand-in per shape of shader; cut-outs, skins and non-casters are left to the frame', () => {
    const base = lightMaterial();
    const what = new THREE.Group();
    const a = new THREE.Mesh(box(), new THREE.MeshStandardMaterial({ color: 'red' }));
    const b = new THREE.Mesh(box(), new THREE.MeshStandardMaterial({ color: 'blue' }));
    const cut = new THREE.Mesh(box(), new THREE.MeshStandardMaterial({ alphaTest: 0.5 }));
    const quiet = new THREE.Mesh(box(), new THREE.MeshStandardMaterial());
    const skinned = new THREE.SkinnedMesh(box(), new THREE.MeshStandardMaterial());
    for (const m of [a, b, cut, skinned]) m.castShadow = true;
    what.add(a, b, cut, quiet, skinned);
    const proxies = shadowProxies(what, { material: base, target: new THREE.RenderTarget(1, 1) }, false);
    expect(proxies.root.children).toHaveLength(1);
    proxies.dispose();
  });

  it("disposing the stand-ins leaves the light's material and what is drawn with it alone", () => {
    const base = lightMaterial();
    const what = new THREE.Group();
    const meshes = casters();
    what.add(...meshes);
    for (const m of meshes) drawn(m, base);
    // (each render object a frame draws with the light's material listens for its `dispose`)
    let gone = 0;
    base.addEventListener('dispose', () => gone++);
    const proxies = shadowProxies(what, { material: base, target: new THREE.RenderTarget(1, 1) }, false);
    for (const proxy of proxies.root.children) expect((proxy as THREE.Mesh).material).not.toHaveProperty('_listeners', (base as unknown as { _listeners: unknown })._listeners);
    proxies.dispose();
    expect(gone).toBe(0);
  });
});
