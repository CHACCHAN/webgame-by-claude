import { describe, expect, it } from 'vitest';
import { Track } from '../track/Track';
import { OBORO_DOWNHILL } from '../track/courseDesign';
import { buildTerrain } from '../track/terrain';

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
    const terrain = buildTerrain(track);
    for (let s = 20; s < track.length; s += 97) {
      if (track.zoneAt(s) === 'bridge') continue;
      const p = track.pointAt(s);
      const h = terrain.heightAt(p.x, p.z);
      expect(h).toBeLessThan(p.y);
      expect(p.y - h).toBeLessThan(3);
    }
  });
});
