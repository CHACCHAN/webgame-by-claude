// How many trees a course gets, by species and by distance from the road:  npx tsx tools/nature-count.ts [density]
// (every species counts as loaded here; the game leaves out the ones whose model is missing)
import { COURSES } from '../src/game/track/courses';
import { Track } from '../src/game/track/Track';
import { buildTerrain } from '../src/game/track/terrain';
import { COVER_SET, plantCover, plantTrees, TREE_SETS, UNDER_SET } from '../src/game/render/vegetationPlanting';

const density = +(process.argv[2] ?? 1);
for (const course of Object.values(COURSES)) {
  const track = new Track(course.design);
  const terrain = buildTerrain(track, course.landform);
  const ids = TREE_SETS[course.style];
  const t0 = performance.now();
  const plants = plantTrees(terrain, density, course.style, ids);
  const ms = performance.now() - t0;
  const by: Record<string, number> = {};
  const bands = [0, 0, 0, 0];
  for (const p of plants) {
    by[ids[p.species]] = (by[ids[p.species]] ?? 0) + 1;
    const d = terrain.roadDistAt(p.x, p.z);
    bands[d < 85 ? 0 : d < 260 ? 1 : d < 1e5 ? 2 : 3]++;
  }
  // bushes, rocks and undergrowth (no keep-out circles and none of the autobahn's own rules here)
  const t1 = performance.now();
  const c = plantCover(track, terrain, density, [], COVER_SET, UNDER_SET, { undergrowth: 1, style: course.style });
  const tally = (list: { species: number }[], names: string[]) => names.map((n, i) => `${n} ${list.filter((p) => p.species === i).length}`).join(', ');
  console.log(`  cover ${c.cover.length} (${tally(c.cover, COVER_SET)}); undergrowth ${c.under.length} (${tally(c.under, UNDER_SET)}) in ${(performance.now() - t1).toFixed(0)} ms`);
  const g = terrain.near, f = terrain.far;
  const x1 = g.x0 + (g.nx - 1) * g.cell, z1 = g.z0 + (g.nz - 1) * g.cell;
  const inside = plants.filter((p) => p.x > g.x0 && p.x < x1 && p.z > g.z0 && p.z < z1).length;
  console.log(`  in the near grid ${inside}; far grid ${((f.nx * f.cell) / 1000).toFixed(1)} × ${((f.nz * f.cell) / 1000).toFixed(1)} km`);
  console.log(
    course.id,
    `${plants.length} trees in ${ms.toFixed(0)} ms`,
    JSON.stringify(by),
    `<85 m: ${bands[0]}, <260 m: ${bands[1]}, near: ${bands[2]}, far: ${bands[3]}`,
    `near grid ${((g.nx * g.cell) / 1000).toFixed(1)} × ${((g.nz * g.cell) / 1000).toFixed(1)} km, road ${(track.length / 1000).toFixed(1)} km`,
  );
}
