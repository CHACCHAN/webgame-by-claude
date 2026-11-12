import { describe, expect, it } from 'vitest';
import { COURSES } from '../track/courses';
import { Track } from '../track/Track';
import { buildTerrain } from '../track/terrain';
import { COVER_SETS, plantCover, plantTrees, roadViews, SPECIES, TREE_SETS, UNDER_SETS, vegetationFiles, viewLimiter } from './vegetationPlanting';

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

  // what each pass is known for: the sea and the harbour town under oboro, the lake of kirifuri
  for (const course of Object.values(COURSES).filter((c) => ['oboro-downhill', 'kirifuri-lakeside'].includes(c.id))) {
    // (tenrou looks out all round: its own test below)
    it(`${course.id}: the road looks out, and no tree stands in the view`, () => {
      const track = new Track(course.design);
      const terrain = buildTerrain(track, course.landform);
      const ids = TREE_SETS[course.style];
      const views = roadViews(track, terrain);
      const open = views.filter((v) => v.open).length / views.length;
      expect(open).toBeGreaterThan(0.6);
      // (a view is to one side, but for a causeway in the lake: the mountain side keeps its forest)
      const bits = (n: number) => n.toString(2).split('1').length - 1;
      expect(views.reduce((sum, v) => sum + bits(v.open), 0) / views.length).toBeLessThan(7);
      const limit = viewLimiter(track, terrain);
      const plants = plantTrees(terrain, 1, course.style, ids, { views: limit });
      let near = 0, grown = 0;
      const high = (p: { species: number; scale: number }) => SPECIES[ids[p.species]].tall! * p.scale > 12;
      for (const p of plants) {
        const d = terrain.roadDistAt(p.x, p.z);
        if (!(d < 40)) continue;
        near++;
        if (high(p)) grown++;
        // (planted a little into the ground: the top is no higher than this)
        expect(p.y + SPECIES[ids[p.species]].tall! * p.scale).toBeLessThanOrEqual(limit(p.x, p.z) + 0.01);
      }
      // the forest is still there: by the road on the mountain side, and all of it behind
      const all = plantTrees(terrain, 1, course.style, ids);
      expect(near).toBeGreaterThan(1200);
      // (the valley side keeps trees too, but low ones: the tall trees by the road are fewer)
      expect(grown).toBeLessThan(all.filter((p) => terrain.roadDistAt(p.x, p.z) < 40 && high(p)).length * 0.8);
      expect(plants.length).toBeGreaterThan(all.length * 0.9);
      // the bushes at the road's edge stay under the eye there
      const coverIds = COVER_SETS[course.style];
      const c = plantCover(track, terrain, 1, [], coverIds, [], { undergrowth: 0, style: course.style, views: limit });
      expect(c.cover.length).toBeGreaterThan(1500);
      for (const p of c.cover) {
        const tall = SPECIES[coverIds[p.species]].tall;
        // (what is lower than the eye stands in no view)
        if (tall && tall * p.scale > 1.01) expect(p.y + tall * p.scale).toBeLessThanOrEqual(limit(p.x, p.z) + 0.11);
      }
    });
  }

  it('tenrou-skyline: the ridge looks out all round and is not shaved for it', () => {
    const course = COURSES['tenrou-skyline'];
    const track = new Track(course.design);
    const terrain = buildTerrain(track, course.landform);
    const ids = TREE_SETS[course.style];
    const limit = viewLimiter(track, terrain);
    const plants = plantTrees(terrain, 1, course.style, ids, { views: limit });
    let near = 0, low = 0;
    for (const p of plants) {
      const d = terrain.roadDistAt(p.x, p.z);
      if (!(d < 120)) continue;
      near++;
      const top = SPECIES[ids[p.species]].tall! * p.scale;
      if (top < 10) low++;
      expect(p.y + top).toBeLessThanOrEqual(limit(p.x, p.z) + 0.01);
    }
    // trees stand within sight of the road, most of them kept low: under the views, and stunted near the tree line
    expect(near).toBeGreaterThan(2500);
    expect(low).toBeGreaterThan(near * 0.4);
    // and where none may stand the ground has its thickets
    const coverIds = COVER_SETS[course.style];
    const c = plantCover(track, terrain, 1, [], coverIds, [], { undergrowth: 0, style: course.style, views: limit });
    expect(c.cover.length).toBeGreaterThan(12000);
    expect(c.cover.length).toBeLessThan(45000);
  });

  it('every species a course asks for has its numbers', () => {
    for (const style of ['touge', 'autobahn'] as const) for (const id of vegetationFiles(style)) expect(SPECIES[id]).toBeDefined();
  });
});
