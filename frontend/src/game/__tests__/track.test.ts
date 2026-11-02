import { describe, expect, it } from 'vitest';
import { Track } from '../track/Track';
import { OBORO_DOWNHILL } from '../track/courseDesign';
import { buildTerrain } from '../track/terrain';
import { BAY } from '../track/landforms';
import { findCorners } from '../track/corners';
import { COURSES, COURSE_ORDER } from '../track/courses';

const track = new Track(OBORO_DOWNHILL);

describe('Track', () => {
  it('has a sensible length, drop and timing lines', () => {
    expect(track.length).toBeGreaterThan(3000);
    expect(track.length).toBeLessThan(3600);
    const drop = track.pos[1] - track.pos[(track.count - 1) * 3 + 1];
    expect(drop).toBeGreaterThan(150);
    expect(track.startS).toBeLessThan(track.finishS);
    expect(track.sectorSplits).toHaveLength(OBORO_DOWNHILL.sectors);
    expect(track.sectorSplits.at(-1)).toBeCloseTo(track.finishS);
  });

  it('projects points back onto the centerline', () => {
    for (const s of [50, 800, 1500, 2600, 3100]) {
      const p = track.pointAt(s, 2.5);
      const proj = track.project(p.x, p.y, p.z);
      expect(proj.s).toBeCloseTo(s, 0);
      expect(proj.lateral).toBeCloseTo(2.5, 1);
    }
  });

  it('never lets two separate legs of the road overlap', () => {
    for (let i = 0; i < track.count; i += 5) {
      for (let j = i + 150; j < track.count; j += 5) {
        const d = Math.hypot(track.pos[i * 3] - track.pos[j * 3], track.pos[i * 3 + 2] - track.pos[j * 3 + 2]);
        expect(d).toBeGreaterThan((track.width[i] + track.width[j]) / 2 + 4);
      }
    }
  });

  it('carves the terrain just below the road surface', () => {
    const terrain = buildTerrain(track, BAY);
    for (let s = 20; s < track.length; s += 97) {
      if (track.zoneAt(s) === 'bridge') continue;
      const p = track.pointAt(s);
      const h = terrain.heightAt(p.x, p.z);
      expect(h).toBeLessThan(p.y);
      expect(p.y - h).toBeLessThan(3);
    }
  });
});

describe('corner detection (pace notes and roadside signs)', () => {
  it('finds every authored hairpin once, in order, with the right direction', () => {
    const t = new Track(OBORO_DOWNHILL);
    const hairpins = findCorners(t).filter((c) => c.kind === 'hairpin');
    // the ladder: R26, L24, R27, L23
    expect(hairpins.map((c) => c.dir)).toEqual([-1, 1, -1, 1]);
    for (let i = 1; i < hairpins.length; i++) expect(hairpins[i].start).toBeGreaterThan(hairpins[i - 1].end);
    for (const c of hairpins) expect(c.minRadius).toBeLessThan(30);
  });

  it('every course has bends worth a call before them', () => {
    for (const id of COURSE_ORDER) {
      const corners = findCorners(new Track(COURSES[id].design));
      expect(corners.filter((c) => c.kind !== 'medium').length).toBeGreaterThanOrEqual(2);
    }
  });
});

describe('terrain never covers the road (all courses)', () => {
  for (const id of COURSE_ORDER) {
    it(`${id}: near terrain stays under the asphalt, the coarse far mesh under both`, () => {
      const c = COURSES[id];
      const t = new Track(c.design);
      const T = buildTerrain(t, c.landform);
      const f = T.far;
      const farAt = (x: number, z: number) => {
        const gx = (x - f.x0) / f.cell, gz = (z - f.z0) / f.cell;
        const i = Math.floor(gx), j = Math.floor(gz), u = gx - i, v = gz - j;
        const h = (a: number, b: number) => f.heights[b * f.nx + a];
        return (h(i, j) * (1 - u) + h(i + 1, j) * u) * (1 - v) + (h(i, j + 1) * (1 - u) + h(i + 1, j + 1) * u) * v;
      };
      let worstNear = -Infinity, worstFar = -Infinity;
      for (let i = 0; i < t.count; i += 2) {
        const hw = t.width[i] / 2;
        for (const lat of [-hw, -hw / 2, 0, hw / 2, hw]) {
          const p = t.pointAt(i, lat);
          // bridges span a gorge: the terrain there is far below anyway
          worstNear = Math.max(worstNear, T.heightAt(p.x, p.z) - p.y);
          worstFar = Math.max(worstFar, farAt(p.x, p.z) - Math.min(p.y, T.heightAt(p.x, p.z)));
        }
      }
      expect(worstNear).toBeLessThan(-0.05);
      expect(worstFar).toBeLessThan(-1);
    });
  }
});

describe('street lamps', () => {
  it('turn their arm (local −X) towards the road in every direction', async () => {
    const THREE = await import('three');
    const { lampArmYaw } = await import('../render/TrackScenery');
    for (let a = 0; a < Math.PI * 2; a += Math.PI / 7) {
      const dir = new THREE.Vector3(Math.cos(a), 0, Math.sin(a));
      const q = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), lampArmYaw(dir));
      const arm = new THREE.Vector3(-1, 0, 0).applyQuaternion(q);
      expect(arm.distanceTo(dir)).toBeLessThan(1e-9);
    }
  });
});

describe('curve mirrors', () => {
  it('stand once per tight bend on the inside, not in a row along it', async () => {
    const { curveMirrorSpots } = await import('../render/TrackScenery');
    for (const id of COURSE_ORDER) {
      const t = new Track(COURSES[id].design);
      const spots = curveMirrorSpots(t);
      const tight = findCorners(t, 30).length;
      expect(spots.length).toBeGreaterThan(0);
      expect(spots.length).toBeLessThanOrEqual(tight);
      for (let k = 1; k < spots.length; k++) expect(spots[k].i - spots[k - 1].i).toBeGreaterThan(20);
      // on the inside of the bend: curvature > 0 turns left, lateral > 0 is right of the centreline
      for (const s of spots) expect(Math.sign(s.lateral)).toBe(-Math.sign(t.curvature[s.i]));
    }
  });
});
