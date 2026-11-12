import { describe, expect, it } from 'vitest';
import * as THREE from 'three';
import { bakeShade, litUnder, shadeAt, shadeScene, type ShadeField, type ShadeLand } from './farShade';
import { LightRig } from './LightRig';

/** a plain 3 km × 3 km wide with whatever stands on it */
const land = (heightAt: (x: number, z: number) => number): ShadeLand => ({ near: { x0: -1500, z0: -1500, cell: 4, nx: 751, nz: 751 }, heightAt });
const light = (x: number, y: number, z: number) => new THREE.Vector3(x, y, z).normalize();
/** how much light the ground (or a point `up` above it) gets: [the land's shade only, with trees and roofs] */
const lit = (f: ShadeField, ground: (x: number, z: number) => number, x: number, z: number, up = 0) => {
  const [a, b] = shadeAt(f, x, z);
  const y = ground(x, z) + up;
  return [litUnder(f, a, y), litUnder(f, b, y)];
};

describe('the far shade', () => {
  it('leaves level ground in the light, whatever the light\'s height', () => {
    const flat = () => 100;
    for (const dir of [light(0.82, 0.16, 0.55), light(0.38, 0.5, 0.78), light(-0.3, 0.9, 0.1), light(0, 0.3, -1)]) {
      const f = bakeShade(shadeScene(land(flat), []), dir);
      for (const [x, z] of [[0, 0], [-1400, 900], [1490, -1490], [333, -777]]) expect(lit(f, flat, x, z)).toEqual([1, 1]);
    }
  });

  it('throws a ridge\'s shadow as long as the light is low, on the side away from it', () => {
    // a ridge 60 m high along z at x = 0, the light from +x, 15° up: the shadow reaches 60 / tan 15° = 224 m to −x
    const ridge = (x: number) => 60 * Math.max(0, 1 - Math.abs(x) / 30);
    const dir = light(Math.cos(0.2618), Math.sin(0.2618), 0);
    const f = bakeShade(shadeScene(land(ridge), []), dir);
    const g = (x: number) => ridge(x);
    expect(lit(f, g, -100, 0)[0]).toBe(0);
    expect(lit(f, g, -200, 40)[0]).toBe(0);
    expect(lit(f, g, -260, 0)[0]).toBe(1);
    expect(lit(f, g, 100, 0)[0]).toBe(1);
    // the slope that faces the light is lit, the one that faces away is not
    expect(lit(f, g, 15, 0)[0]).toBe(1);
    expect(lit(f, g, -15, 0)[0]).toBe(0);
    // a point high enough above the shaded ground sees the light again (60 m ridge, 100 m behind it: above 33 m)
    expect(lit(f, g, -100, 0, 20)[0]).toBe(0);
    expect(lit(f, g, -100, 0, 40)[0]).toBe(1);
  });

  it('runs the same along the other axis and diagonally', () => {
    const hill = (x: number, z: number) => 50 * Math.max(0, 1 - Math.hypot(x, z) / 40);
    for (const a of [0.5, 1.2, 2.4, 3.9, 5.5]) {
      const dir = light(Math.cos(a) * Math.cos(0.3), Math.sin(0.3), Math.sin(a) * Math.cos(0.3));
      const f = bakeShade(shadeScene(land(hill), []), dir);
      // 100 m behind the hill (50 m high, the light 17° up: 160 m of shadow), and as far in front of it
      expect(lit(f, hill, -Math.cos(a) * 100, -Math.sin(a) * 100)[0]).toBeLessThan(0.05);
      expect(lit(f, hill, Math.cos(a) * 100, Math.sin(a) * 100)[0]).toBe(1);
      expect(lit(f, hill, -Math.cos(a) * 220, -Math.sin(a) * 220)[0]).toBe(1);
    }
  });

  it('keeps trees and roofs out of the land\'s own shade', () => {
    const flat = () => 0;
    const dir = light(1, 0.5, 0);
    // a tree 14 m tall at the origin, a roof 6 m up over a strip of road further on
    const scene = shadeScene(land(flat), [{ x: 0, z: 0, r: 4, top: 14 }], [200, -6, 260, -6, 260, 6, 200, 6, 6]);
    const f = bakeShade(scene, dir);
    // the tree's shadow lies towards −x, about 28 m long
    expect(lit(f, flat, -12, 0)).toEqual([1, 0]);
    expect(lit(f, flat, -60, 0)).toEqual([1, 1]);
    expect(lit(f, flat, 12, 0)[1]).toBe(1);
    // under the roof it is dark, on top of it light
    expect(lit(f, flat, 230, 0)).toEqual([1, 0]);
    expect(lit(f, flat, 230, 0, 7)[1]).toBe(1);
    expect(lit(f, flat, 230, 40)[1]).toBe(1);
  });

  it('takes the far land\'s skyline for what lies beyond the grid', () => {
    // a wall of mountains outside the grid, to the east, 600 m high
    const far = (x: number) => (x > 2000 ? 600 : 0);
    const f = bakeShade(shadeScene(land(far), []), light(1, 0.25, 0));
    // 600 m / 0.258 = 2.3 km of shadow from x = 2000: all the grid's east, not its west end
    expect(lit(f, far, 1000, 0)[0]).toBe(0);
    expect(lit(f, far, 0, 0)[0]).toBe(0);
    expect(lit(f, far, -1000, 0)[0]).toBe(1);
  });
});

describe('the shadow map\'s place', () => {
  const rig = () => new LightRig({ shadows: true, shadowMapSize: 2048, headlightShadows: false });
  const sun = light(0.82, 0.16, 0.55);

  it('lies ahead of the camera, and the light looks at its middle', () => {
    const r = rig();
    const { at, half } = r.keyMap;
    const eye = new THREE.Vector3(120, 300, -40);
    r.aimKey(eye, new THREE.Vector3(0, -0.2, 1).normalize(), sun);
    expect(at.z - eye.z).toBeGreaterThan(half * 0.5);
    expect(at.z - eye.z).toBeLessThan(half * 0.6);
    expect(Math.abs(at.x - eye.x)).toBeLessThan(0.2);
    expect(r.key.target.position.equals(at)).toBe(true);
    expect(r.key.position.clone().sub(at).normalize().distanceTo(sun)).toBeLessThan(1e-6);
    // straight down: around the camera
    r.aimKey(eye, new THREE.Vector3(0, -1, 0), sun);
    expect(at.distanceTo(eye)).toBeLessThan(0.2);
  });

  it('moves in whole texels along the map\'s own axes', () => {
    const r = rig();
    const { at, x, y, half } = r.keyMap;
    const texel = (2 * half) / 2048;
    const ahead = new THREE.Vector3(1, 0, 0);
    for (let k = 0; k < 40; k++) {
      r.aimKey(new THREE.Vector3(k * 0.731, 50 + k * 0.01, k * -0.377), ahead, sun);
      for (const axis of [x, y]) {
        const steps = at.dot(axis) / texel;
        expect(Math.abs(steps - Math.round(steps))).toBeLessThan(1e-3);
      }
      // the axes are the shadow camera's: across the light, at right angles to each other
      expect(Math.abs(x.dot(sun))).toBeLessThan(1e-6);
      expect(Math.abs(y.dot(sun))).toBeLessThan(1e-6);
      expect(Math.abs(x.dot(y))).toBeLessThan(1e-6);
    }
  });
});
