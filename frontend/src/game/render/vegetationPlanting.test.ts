import { describe, expect, it } from 'vitest';
import { COURSES } from '../track/courses';
import { Track } from '../track/Track';
import { buildTerrain } from '../track/terrain';
import { COVER_SETS, plantCover, plantTrees, SPECIES, TREE_SETS, UNDER_SETS, vegetationFiles } from './vegetationPlanting';

describe('vegetation planting', () => {
  for (const course of Object.values(COURSES)) {
    const track = new Track(course.design);
    const terrain = buildTerrain(track, course.landform);
    const ids = TREE_SETS[course.style];

    it(`${course.id}: a forest of every species, within the budget, none on the road`, () => {
      const plants = plantTrees(terrain, 1, course.style, ids);
      // (the mesh levels and the impostor buffers are sized for this order of magnitude)
      expect(plants.length).toBeGreaterThan(30000);
      expect(plants.length).toBeLessThan(220000);
      const seen = new Set<number>();
      let near = 0;
      for (const p of plants) {
        expect(Number.isFinite(p.x + p.y + p.z + p.scale + p.yaw)).toBe(true);
        seen.add(p.species);
        const d = terrain.roadDistAt(p.x, p.z);
        // far from the road the terrain knows no distance (NaN / Infinity): those are impostors only
        if (d < 330) near++;
        else expect(p.far).toBe(true);
      }
      expect(seen.size).toBe(ids.length);
      // the trees that can come within the mesh levels' reach are the smaller part
      expect(near).toBeLessThan(90000);
    });

    it(`${course.id}: bushes, rocks and undergrowth beside the road`, () => {
      const c = plantCover(track, terrain, 1, [], COVER_SETS[course.style], UNDER_SETS[course.style], { undergrowth: 1, style: course.style });
      expect(c.cover.length).toBeGreaterThan(2000);
      expect(c.under.length).toBeGreaterThan(30000);
      expect(c.under.length).toBeLessThan(300000);
      for (const plant of [...c.cover, ...c.under]) {
        expect(Number.isFinite(plant.x + plant.y + plant.z + plant.scale)).toBe(true);
        // nothing grows on the carriageway (the terrain's distance to the centreline is a coarse grid: a margin)
        expect(terrain.roadDistAt(plant.x, plant.z)).toBeGreaterThan(2.5);
      }
      expect(plantCover(track, terrain, 1, [], COVER_SETS[course.style], UNDER_SETS[course.style], { undergrowth: 0, style: course.style }).under.length).toBe(0);
    });
  }

  it('every species a course asks for has its numbers', () => {
    for (const style of ['touge', 'autobahn'] as const) for (const id of vegetationFiles(style)) expect(SPECIES[id]).toBeDefined();
  });
});
