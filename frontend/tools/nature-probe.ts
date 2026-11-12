// What the planting does at the spot a picture's pixel shows:
//   npx tsx tools/nature-probe.ts <course> <lap fraction> <px 0..1> <py 0..1> [more px py pairs]
// (camera: the chase camera's rough place, 7 m behind and 2.6 m over the road, 60° upright field of view, 16:9)
import { COURSES } from '../src/game/track/courses';
import { Track } from '../src/game/track/Track';
import { buildTerrain } from '../src/game/track/terrain';
import { cityWeight, plantTrees, TREE_SETS, viewLimiter, SPECIES } from '../src/game/render/vegetationPlanting';
import { noise2 } from '../src/game/util/math';
import * as THREE from 'three';

const [courseId, frac, ...px] = process.argv.slice(2);
const course = COURSES[courseId as keyof typeof COURSES];
const track = new Track(course.design);
const terrain = buildTerrain(track, course.landform);
const lf = terrain.landform;
// ('hairpin': 12 m before the tightest bend, as tools/shots.cjs takes it)
let tight = 0;
for (let i = 0; i < track.count; i++) if (Math.abs(track.curvature[i]) > Math.abs(track.curvature[tight])) tight = i;
const s = frac === 'hairpin' ? tight - 12 : track.startS + +frac * (track.finishS - track.startS);
const p = track.pointAt(s - 7, 0, new THREE.Vector3());
const a = track.pointAt(s + 1, 0, new THREE.Vector3());
const fwd = a.clone().sub(p).setY(0).normalize();
const right = new THREE.Vector3(-fwd.z, 0, fwd.x); // screen right
const eye = p.clone().add(new THREE.Vector3(0, 2.6, 0));
const limit = course.style === 'touge' ? viewLimiter(track, terrain) : null;
const ids = TREE_SETS[course.style];
const trees = plantTrees(terrain, 1, course.style, ids, limit ? { views: limit } : {});
console.log(courseId, 's', s.toFixed(0), 'eye', eye.toArray().map((v) => v.toFixed(0)).join(','), 'trees', trees.length);
const tanV = Math.tan((30 * Math.PI) / 180), tanH = tanV * (16 / 9);
for (let i = 0; i + 1 < px.length; i += 2) {
  const u = (+px[i] - 0.5) * 2, v = (0.5 - +px[i + 1]) * 2;
  // (the chase camera looks slightly down: 4°)
  const dir = fwd.clone().addScaledVector(right, u * tanH).add(new THREE.Vector3(0, v * tanV - 0.07, 0)).normalize();
  let hit: THREE.Vector3 | null = null;
  for (let t = 5; t < 6000; t += Math.max(1, t * 0.004)) {
    const q = eye.clone().addScaledVector(dir, t);
    if (terrain.heightAt(q.x, q.z) > q.y) {
      hit = q;
      break;
    }
  }
  if (!hit) {
    console.log(px[i], px[i + 1], 'sky');
    continue;
  }
  const x = hit.x, z = hit.z, y = terrain.heightAt(x, z);
  const dx = terrain.heightAt(x + 3, z) - terrain.heightAt(x - 3, z), dz = terrain.heightAt(x, z + 3) - terrain.heightAt(x, z - 3);
  const d = terrain.roadDistAt(x, z);
  const near = trees.filter((t) => (t.x - x) ** 2 + (t.z - z) ** 2 < 40 * 40);
  const g = terrain.near;
  const inNear = x > g.x0 && x < g.x0 + (g.nx - 1) * g.cell && z > g.z0 && z < g.z0 + (g.nz - 1) * g.cell;
  console.log(
    px[i], px[i + 1],
    `at ${x.toFixed(0)},${y.toFixed(0)},${z.toFixed(0)} dist ${hit.distanceTo(eye).toFixed(0)} m`,
    `road ${d < 1e5 ? d.toFixed(0) : 'far'} ${inNear ? 'near-grid' : 'far-grid'}`,
    `slope ${(Math.hypot(dx, dz) / 6).toFixed(2)} relief ${lf.relief(x, z).toFixed(2)} city ${cityWeight(lf, x, z).toFixed(2)}`,
    `treeline ${lf.treeLine} water ${lf.waterLevel}`,
    `clear85 ${noise2(x / 140, z / 140).toFixed(2)} clear260 ${noise2(x / 220, z / 220).toFixed(2)} clearFar ${noise2(x / 300, z / 300).toFixed(2)}`,
    `limit ${limit ? (limit(x, z) - y).toFixed(1) : '-'}`,
    `trees within 40 m: ${near.length} (scales ${near.slice(0, 6).map((t) => t.scale.toFixed(2)).join(' ')}; ${[...new Set(near.map((t) => ids[t.species]))].join(',')})`,
  );
}
void SPECIES;
