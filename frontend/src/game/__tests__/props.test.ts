import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import * as THREE from 'three';
import { Track } from '../track/Track';
import { buildTerrain } from '../track/terrain';
import { classifySides, SHOULDER } from '../track/roadGeometry';
import { COURSES, COURSE_ORDER } from '../track/courses';
import { levelSites, planRoadsideSites, SITE_GAP, sitePoint } from '../track/propSites';

describe('roadside prop sites', () => {
  for (const id of COURSE_ORDER) {
    it(`${id}: a shrine and a bus stop on levelled ground beside the road`, () => {
      const course = COURSES[id];
      const track = new Track(course.design);
      const terrain = buildTerrain(track, course.landform);
      const sides = classifySides(track, terrain);
      const sites = planRoadsideSites(track, terrain, sides);
      expect(sites.map((s) => s.kind).sort()).toEqual(['busStop', 'shrine']);
      expect(Math.abs(sites[0].s - sites[1].s)).toBeGreaterThan(250);

      // the road corridor must not change when the sites are levelled
      const g = terrain.near;
      const before = g.heights.slice();
      levelSites(track, terrain, sites);
      for (let k = 0; k < g.heights.length; k++) if ((g.roadDist?.[k] ?? 1e9) < 6) expect(g.heights[k]).toBe(before[k]);

      for (const site of sites) {
        expect(track.startS + 80).toBeLessThan(site.s);
        expect(site.s).toBeLessThan(track.finishS - 80);
        const hw = track.width[site.s] / 2 + SHOULDER;
        // no guardrail (valley side) in front of the props
        const valley = site.side > 0 ? sides.right.valley : sides.left.valley;
        for (let k = site.s - site.halfLength - 5; k <= site.s + site.halfLength + 5; k++) expect(valley[Math.round(k)]).toBe(0);
        for (let u = -site.halfLength; u <= site.halfLength; u += 0.5) {
          for (let v = 0; v <= site.depth; v += 0.5) {
            const p = sitePoint(track, site, u, v);
            const k = Math.round(site.s + u);
            expect(['rockshed', 'bridge']).not.toContain(track.zone[k]);
            // beyond the road wall, and this leg is the nearest road
            const proj = track.project(p.x, p.y, p.z);
            expect(Math.abs(proj.lateral)).toBeGreaterThan(hw + SITE_GAP - 0.2);
            expect(terrain.roadDistAt(p.x, p.z)).toBeGreaterThan(hw + SITE_GAP - 1.5);
            // flat ground at the road bed
            expect(Math.abs(terrain.heightAt(p.x, p.z) - p.y)).toBeLessThan(0.15);
          }
        }
        // the site's +Z (the props' front) points at the road
        const c = sitePoint(track, site, 0, site.depth / 2);
        const road = track.getPos(site.s);
        const toRoad = new THREE.Vector3(road.x - c.x, 0, road.z - c.z).normalize();
        expect(toRoad.dot(new THREE.Vector3(Math.sin(site.yaw), 0, Math.cos(site.yaw)))).toBeGreaterThan(0.98);
        // a prop's local +X maps onto u = −side · x (used to put props beside each other)
        const ux = sitePoint(track, site, -site.side, 0).sub(sitePoint(track, site, 0, 0)).setY(0).normalize();
        expect(ux.dot(new THREE.Vector3(Math.cos(site.yaw), 0, -Math.sin(site.yaw)))).toBeGreaterThan(0.98);
      }
    });
  }
});

describe('prop models', () => {
  // untextured props load in Node (textured ones need the browser's image decoder)
  for (const id of ['led_light', 'curve_mirror'] as const) {
    it(`${id}.glb: quantised parts are baked back to metres, anchors and bounds match`, async () => {
      const { GLTFLoader } = await import('three/examples/jsm/loaders/GLTFLoader.js');
      const { MeshoptDecoder } = await import('three/examples/jsm/libs/meshopt_decoder.module.js');
      const { registerPropTemplate } = await import('../render/propAssets');
      const buf = readFileSync(new URL(`../../../public/models/props/${id}.glb`, import.meta.url));
      const loader = new GLTFLoader().setMeshoptDecoder(MeshoptDecoder);
      const gltf = await loader.parseAsync(buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength), '');
      const t = registerPropTemplate(id, gltf.scene);
      const box = new THREE.Box3();
      for (const p of t.parts) box.union(p.geometry.boundingBox!);
      expect(box.min.distanceTo(t.min)).toBeLessThan(0.02);
      expect(box.max.distanceTo(t.max)).toBeLessThan(0.02);
      // standing on the ground with the foot at the origin
      expect(Math.abs(box.min.y)).toBeLessThan(0.2);
      if (id === 'led_light') {
        // lamp: arm along −X, the lens is a "lamp" part and the light anchor sits under it
        expect(t.parts.some((p) => p.role === 'lamp')).toBe(true);
        expect(t.anchors.light.x).toBeLessThan(-2);
        expect(t.anchors.light.y).toBeGreaterThan(7);
        expect(box.max.x).toBeLessThan(0.5);
      } else {
        // mirror faces +Z
        expect(t.anchors.mirror.z).toBeGreaterThan(0.1);
      }
    });
  }

  it('instances rotor parts about the hub', async () => {
    const { instanceProp } = await import('../render/propAssets');
    const geo = new THREE.BoxGeometry(0.2, 10, 0.2).translate(0, 5, 0);
    const mat = new THREE.MeshStandardMaterial();
    const t = {
      id: 'wind_turbine' as const,
      parts: [{ geometry: geo, material: mat }],
      rotor: { parts: [{ geometry: geo, material: mat }], matrix: new THREE.Matrix4().makeTranslation(0, 60, 2) },
      anchors: {},
      min: new THREE.Vector3(),
      max: new THREE.Vector3(),
    };
    const inst = instanceProp(t, [new THREE.Matrix4().makeTranslation(100, 0, 0)]);
    inst.spin!([Math.PI / 2]);
    const rotor = inst.group.children[1] as THREE.InstancedMesh;
    const m = new THREE.Matrix4();
    rotor.getMatrixAt(0, m);
    // the blade tip (0, 10, 0) turns a quarter about +Z round the hub at (100, 60, 2)
    const tip = new THREE.Vector3(0, 10, 0).applyMatrix4(m);
    expect(tip.x).toBeCloseTo(90, 5);
    expect(tip.y).toBeCloseTo(60, 5);
    expect(tip.z).toBeCloseTo(2, 5);
  });
});
