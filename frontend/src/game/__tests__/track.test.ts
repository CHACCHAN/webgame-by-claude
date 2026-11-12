import { describe, expect, it } from 'vitest';
import { Track } from '../track/Track';
import { OBORO_DOWNHILL } from '../track/courseDesign';
import { buildTerrain, planTerrain } from '../track/terrain';
import { terrainThreads } from '../track/terrainJob';
import { BAY } from '../track/landforms';
import { findCorners } from '../track/corners';
import { COURSES, COURSE_ORDER } from '../track/courses';
import { AUTOBAHN } from '../track/courseDesign';
import { PLATEAU } from '../track/landforms';

/** the mountain passes (the autobahn has no bends worth a pace note, mirror or sign) */
const TOUGE = COURSE_ORDER.filter((id) => COURSES[id].style === 'touge');

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

describe('AUTOBAHN', () => {
  const t = new Track(AUTOBAHN);
  const y = (s: number) => t.pos[Math.round(s) * 3 + 1];

  it('is about 8 km, gently downhill, with radii of 1200 m or more', () => {
    const timed = t.finishS - t.startS;
    expect(timed).toBeGreaterThan(7500);
    expect(timed).toBeLessThan(8500);
    const grade = (y(t.finishS) - y(t.startS)) / timed;
    expect(grade).toBeLessThan(-0.02);
    expect(grade).toBeGreaterThan(-0.025);
    let kMax = 0, gMin = 0;
    for (let i = 0; i < t.count; i++) kMax = Math.max(kMax, Math.abs(t.curvature[i]));
    for (let i = 1; i < t.count; i++) gMin = Math.min(gMin, t.pos[i * 3 + 1] - t.pos[(i - 1) * 3 + 1]);
    expect(1 / kMax).toBeGreaterThanOrEqual(1200);
    expect(gMin).toBeGreaterThan(-0.045);
    expect(findCorners(t, 600)).toHaveLength(0);
    expect(t.width[Math.round(t.length / 2)]).toBeCloseTo(14.5, 1);
  });

  it('has room for a train behind the grid and a straight run-off to stop on', () => {
    expect(t.startS).toBeGreaterThanOrEqual(90);
    expect(t.length - t.finishS).toBeGreaterThanOrEqual(600);
    for (let s = t.finishS; s < t.length; s++) expect(Math.abs(t.curvatureAt(s))).toBeLessThan(1e-4);
  });

  it('tags the zones the scenery is built from', () => {
    const count = (tag: Parameters<Track['zoneRanges']>[0]) => t.zoneRanges(tag).length;
    expect(count('overpass')).toBeGreaterThanOrEqual(2);
    expect(count('interchange')).toBeGreaterThanOrEqual(1);
    expect(count('village')).toBeGreaterThanOrEqual(1);
    expect(count('bridge')).toBeGreaterThanOrEqual(1);
    expect(count('start')).toBe(1);
    expect(count('finish')).toBe(1);
    const len = (tag: Parameters<Track['zoneRanges']>[0]) => t.zoneRanges(tag).reduce((a, [p, q]) => a + q - p, 0);
    expect(len('forest')).toBeGreaterThan(2000);
    expect(len('motorway')).toBeGreaterThan(1500);
  });

  it('grades flat ground for the median and the opposite carriageway; the viaduct spans a valley', () => {
    const T = buildTerrain(t, PLATEAU);
    for (let s = 20; s < t.length - 20; s += 50) {
      const zone = t.zoneAt(s);
      for (const lat of [-28, -20, -12, 12, 20]) {
        const p = t.pointAt(s, lat);
        const h = T.heightAt(p.x, p.z);
        if (zone === 'bridge') expect(p.y - h).toBeGreaterThan(8);
        else {
          expect(h).toBeLessThan(p.y);
          expect(p.y - h).toBeLessThan(1);
        }
      }
    }
    const [a, b] = t.zoneRanges('bridge')[0];
    const mid = t.getPos(Math.round((a + b) / 2));
    expect(mid.y - T.heightAt(mid.x, mid.z)).toBeGreaterThan(25);
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

  it('every mountain pass has bends worth a call before them', () => {
    expect(TOUGE).toHaveLength(3);
    for (const id of TOUGE) {
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
    for (const id of TOUGE) {
      const t = new Track(COURSES[id].design);
      const spots = curveMirrorSpots(t);
      const tight = findCorners(t, 30).length;
      expect(spots.length).toBeGreaterThan(0);
      expect(spots.length).toBeLessThanOrEqual(tight);
      for (let k = 1; k < spots.length; k++) expect(spots[k].i - spots[k - 1].i).toBeGreaterThan(20);
      // on the inside of the bend: curvature > 0 turns left, lateral > 0 is right of the centreline
      for (const s of spots) expect(Math.sign(s.lateral)).toBe(-Math.sign(t.curvature[s.i]));
      // the glass (model +Z turned by yaw) looks at the road, on both sides
      for (const s of spots) {
        const at = t.pointAt(s.i, s.lateral), centre = t.pointAt(s.i, 0);
        const toRoad = centre.sub(at).setY(0).normalize();
        expect(Math.sin(s.yaw) * toRoad.x + Math.cos(s.yaw) * toRoad.z).toBeGreaterThan(0.9);
      }
      expect(new Set(spots.map((s) => Math.sign(s.lateral))).size).toBe(2);
    }
  });
});

describe('terrain worked out in stripes (the rows each worker takes)', () => {
  const same = (a: ArrayLike<number>, b: ArrayLike<number>) => {
    if (a.length !== b.length) return false;
    for (let i = 0; i < a.length; i++) if (!Object.is(a[i], b[i])) return false;
    return true;
  };
  const c = COURSES['tenrou-skyline'];
  const t = new Track(c.design);

  it('is the same to the bit as the terrain built in one go, in whatever order the stripes arrive', () => {
    const whole = buildTerrain(t, c.landform);
    // (each worker lays the course out again: another Track of the same design)
    const n = 5, stripes = [3, 0, 4, 2, 1].map((k) => planTerrain(new Track(c.design), c.landform).stripe(k, n));
    const T = planTerrain(t, c.landform).finish(stripes);
    expect(same(T.near.heights, whole.near.heights)).toBe(true);
    expect(same(T.near.roadDist!, whole.near.roadDist!)).toBe(true);
    expect(same(T.near.edgeDist!, whole.near.edgeDist!)).toBe(true);
    expect(same(T.far.heights, whole.far.heights)).toBe(true);
    expect([T.near.x0, T.near.z0, T.near.nx, T.near.nz, T.far.x0, T.far.z0, T.far.nx, T.far.nz]).toEqual([whole.near.x0, whole.near.z0, whole.near.nx, whole.near.nz, whole.far.x0, whole.far.z0, whole.far.nx, whole.far.nz]);
    expect(T.heightAt(t.pos[300] + 40, t.pos[302] - 25)).toBe(whole.heightAt(t.pos[300] + 40, t.pos[302] - 25));
  });

  it('refuses rows that are missing, given twice or of another size', () => {
    const plan = planTerrain(t, c.landform, { nearCell: 16, farCell: 96 });
    const a = plan.stripe(0, 2), b = plan.stripe(1, 2);
    expect(() => plan.finish([a])).toThrow();
    expect(() => plan.finish([a, b, b])).toThrow();
    expect(() => plan.finish([a, { ...b, nearH: b.nearH.subarray(1) }])).toThrow();
    // more stripes than rows: the late ones are empty, and that is fine
    const many = 400, all = Array.from({ length: many }, (_, k) => plan.stripe(k, many));
    expect(all[many - 1].nearH.length + all[many - 1].farH.length).toBe(0);
    expect(same(plan.finish(all).near.heights, plan.finish([a, b]).near.heights)).toBe(true);
  });

  it('uses all cores but the page\'s own, within reason', () => {
    expect(terrainThreads(20)).toBe(16);
    expect(terrainThreads(8)).toBe(7);
    expect(terrainThreads(2)).toBe(1);
    expect(terrainThreads(1)).toBe(1);
    expect(terrainThreads(0)).toBe(1);
  });
});
