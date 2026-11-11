import { describe, expect, it } from 'vitest';
import * as THREE from 'three';
import { HEADLIGHT, LightRig, type BeamSource } from './LightRig';
import { gpuBytes } from './gpuBytes';

const car = (x: number, intensity = HEADLIGHT.intensity): BeamSource => ({
  headlight(position, target) {
    position.set(x, 1, 0);
    target.set(x, 0, 30);
    return intensity;
  },
});
const lightIds = (rig: LightRig) => {
  const ids: string[] = [];
  rig.group.traverse((o) => void ((o as THREE.Light).isLight && ids.push(`${o.id}:${o.castShadow ? 1 : 0}`)));
  return ids.join(',');
};
const spots = (rig: LightRig) => rig.group.children.filter((o): o is THREE.SpotLight => (o as THREE.SpotLight).isSpotLight);

describe('the light rig', () => {
  it('keeps one set of lights whatever is shown (the shaders are built for the set)', () => {
    const rig = new LightRig({ shadows: true, shadowMapSize: 1024, headlightShadows: true });
    const before = lightIds(rig);
    rig.beams([car(1), car(2), car(3), car(4), car(5)]);
    rig.showroomOn = true;
    rig.showroom.intensity = 40;
    rig.beams([car(1)]);
    rig.showroomOn = false;
    rig.beams([]);
    expect(lightIds(rig)).toBe(before);
  });

  it('gives the first car the spot with shadows, the next two the others, and darkens what is left', () => {
    const rig = new LightRig({ shadows: true, shadowMapSize: 1024, headlightShadows: true });
    const s = spots(rig);
    rig.beams([car(1), null, car(2, 0), car(3), car(4), car(5)]);
    expect(s.map((x) => x.position.x)).toEqual([1, 3, 4]);
    expect(s.map((x) => x.castShadow)).toEqual([true, false, false]);
    expect(s.every((x) => x.intensity === HEADLIGHT.intensity)).toBe(true);
    rig.beams([car(7)]);
    expect(s.map((x) => x.intensity)).toEqual([HEADLIGHT.intensity, 0, 0]);
    expect(s[0].shadow.autoUpdate).toBe(true);
    rig.beams([]);
    expect(s[0].shadow.autoUpdate).toBe(false);
  });

  it('leaves the first spot to the showroom', () => {
    const rig = new LightRig({ shadows: true, shadowMapSize: 1024, headlightShadows: false });
    const s = spots(rig);
    rig.showroomOn = true;
    rig.showroom.intensity = 40;
    rig.showroom.angle = 0.85;
    rig.beams([car(1), car(2), car(3)]);
    expect(s[0].intensity).toBe(40);
    expect(s[0].angle).toBe(0.85);
    expect(s.map((x) => x.position.x).slice(1)).toEqual([1, 2]);
    expect(s[0].castShadow).toBe(false);
  });
});

describe('gpuBytes', () => {
  it('counts shared buffers and textures once', () => {
    const geo = new THREE.BoxGeometry(1, 1, 1);
    const tex = new THREE.DataTexture(new Uint8Array(4 * 64 * 64), 64, 64);
    tex.generateMipmaps = false;
    const mat = new THREE.MeshBasicMaterial({ map: tex });
    const one = new THREE.Group().add(new THREE.Mesh(geo, mat));
    const two = new THREE.Group().add(new THREE.Mesh(geo, mat), new THREE.Mesh(geo, mat));
    expect(gpuBytes(one)).toBeGreaterThan(64 * 64 * 4);
    expect(gpuBytes(two)).toBe(gpuBytes(one));
    expect(gpuBytes(one, two)).toBe(gpuBytes(one));
  });
});
