import * as THREE from 'three';
import { describe, expect, it, vi } from 'vitest';
import { CAR_SPECS } from '../vehicle/carSpecs';

// A stand-in for a fighter's GLB: what the F-15s' files held up to v2.8.0, the anti-collision beacon with a black
// glow (its emission strength 0 in tools/blender/jets/f15.py), beside a navigation lamp that has a glow of its own.
const BEACON = '#ff3020', NAV = '#2aff5a';
vi.mock('three/examples/jsm/loaders/GLTFLoader.js', () => ({
  GLTFLoader: class {
    setMeshoptDecoder() {}
    async loadAsync() {
      const scene = new THREE.Group();
      const body = new THREE.Group();
      body.name = 'body';
      scene.add(body);
      const lamp = (name: string, color: string, emissive: string) => {
        const m = new THREE.Mesh(new THREE.BoxGeometry(0.2, 0.2, 0.2), new THREE.MeshStandardMaterial({ name, color, emissive }));
        body.add(m);
      };
      lamp('beacon', BEACON, '#000000');
      lamp('navlight_green', '#204020', NAV);
      return { scene };
    }
  },
}));
vi.mock('three/examples/jsm/libs/meshopt_decoder.module.js', () => ({ MeshoptDecoder: {} }));

const { buildJet, loadJetModel } = await import('../render/JetModel');

describe("a fighter's lamps", () => {
  it('a beacon exported with a black glow flashes in its own colour; a lamp with a glow keeps that', async () => {
    await loadJetModel('f15j');
    const rig = buildJet(CAR_SPECS.f15j);
    expect(rig.fromModel).toBe(true);
    const mat = (name: string) => {
      let found: THREE.MeshStandardMaterial | null = null;
      rig.root.traverse((o) => {
        const m = (o as THREE.Mesh).material as THREE.MeshStandardMaterial | undefined;
        if ((o as THREE.Mesh).isMesh && m?.name === name) found = m;
      });
      return found! as THREE.MeshStandardMaterial;
    };
    const beacon = mat('beacon'), nav = mat('navlight_green');
    const anchor = new THREE.Object3D();
    // in a flash (the first 0.12 s of every 1.1 s): six times the lamp's colour
    rig.jet.update(anchor, 0.05);
    expect(beacon.emissive.getHex()).not.toBe(0);
    const flash = new THREE.Color(BEACON).multiplyScalar(6);
    expect(beacon.emissive.r).toBeCloseTo(flash.r, 5);
    expect(beacon.emissive.g).toBeCloseTo(flash.g, 5);
    expect(beacon.emissive.b).toBeCloseTo(flash.b, 5);
    expect(beacon.emissiveIntensity).toBe(1);
    // between the flashes: dark
    rig.jet.update(anchor, 0.5);
    expect(beacon.emissive.getHex()).toBe(0);
    // the navigation lamp glows in its glow colour (not its base colour) once the lights are on
    rig.jet.setLights(1);
    rig.jet.update(anchor, 0.1);
    const lit = new THREE.Color(NAV).multiplyScalar(3);
    expect(nav.emissive.g).toBeCloseTo(lit.g, 5);
    expect(nav.emissive.r).toBeCloseTo(lit.r, 5);
  });
});
