import { describe, expect, it } from 'vitest';
import * as THREE from 'three';
import { ROACH_INFO } from '../vehicle/roach';
import { applyLivery, liveryBase } from './RoachModel';

describe("the cockroach's liveries", () => {
  const texture = () => {
    const t = new THREE.DataTexture(new Uint8Array([122, 52, 23, 255]), 1, 1);
    t.colorSpace = THREE.SRGBColorSpace;
    t.minFilter = THREE.LinearMipmapLinearFilter;
    t.magFilter = THREE.LinearFilter;
    t.wrapS = t.wrapT = THREE.RepeatWrapping;
    return t;
  };

  // players' reports, v2.1.0: after a change of colour the cockroach was no longer drawn. A plain livery took the
  // colour texture away (`map = null`), and three.js' shadow pass went on reading the drawn material's map: every
  // frame threw from then on (tools/paint-drawn.cjs shows it on the GPU)
  it('never take the colour texture away from a material that has one, whatever the order of the liveries', () => {
    const map = texture();
    const m = new THREE.MeshStandardMaterial({ color: '#ffffff', map, metalness: 0.1, roughness: 0.5 });
    const base = liveryBase(m);
    const all = ROACH_INFO.liveries;
    expect(all.some((l) => l.plain)).toBe(true);
    for (const from of all) {
      for (const to of all) {
        applyLivery(m, base, from);
        applyLivery(m, base, to);
        expect(m.map, `${from.name} → ${to.name}`).toBeInstanceOf(THREE.Texture);
        // the texture itself for the liveries that tint it, a stand-in sampled the same way for the plain ones
        if (to.plain) {
          expect(m.map).not.toBe(map);
          expect([m.map!.colorSpace, m.map!.minFilter, m.map!.magFilter, m.map!.wrapS, m.map!.wrapT]).toEqual([map.colorSpace, map.minFilter, map.magFilter, map.wrapS, map.wrapT]);
          expect(Array.from((m.map as THREE.DataTexture).image.data as Uint8Array)).toEqual([255, 255, 255, 255]);
        } else expect(m.map).toBe(map);
      }
    }
  });

  it('give the model its own look back after any other livery', () => {
    const m = new THREE.MeshStandardMaterial({ color: '#c0a080', map: texture(), metalness: 0.1, roughness: 0.5 });
    const base = liveryBase(m);
    const was = { color: m.color.getHex(), map: m.map };
    for (const liv of ROACH_INFO.liveries.slice(1)) {
      applyLivery(m, base, liv);
      applyLivery(m, base, ROACH_INFO.liveries[0]);
      expect({ color: m.color.getHex(), map: m.map }).toEqual(was);
      expect([m.metalness, m.roughness]).toEqual([0.1, 0.5]);
    }
  });

  it('leave a material without a texture without one (the stand-in body)', () => {
    const m = new THREE.MeshStandardMaterial({ color: '#7a3417' });
    const base = liveryBase(m);
    for (const liv of ROACH_INFO.liveries) {
      applyLivery(m, base, liv);
      expect(m.map).toBeNull();
    }
  });
});
