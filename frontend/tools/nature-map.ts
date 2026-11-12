// The planting from above, as a picture:  npx tsx tools/nature-map.ts <course> <out.ppm> [metres per pixel = 3] [x0 z0 x1 z1]
// Relief in grey, water blue, the road white (red where it looks out: `roadViews`), trees as discs of their crown's
// width (conifers dark green, beech olive, pine blue-green; the lighter the smaller against a grown one), bushes
// orange, rocks grey, undergrowth not drawn. (PPM: `python3 -c "from PIL import Image; Image.open(a).save(b)"`.)
import * as fs from 'node:fs';
import * as THREE from 'three';
import { COURSES } from '../src/game/track/courses';
import { Track } from '../src/game/track/Track';
import { buildTerrain } from '../src/game/track/terrain';
import { COVER_SETS, plantCover, plantTrees, roadViews, SPECIES, TREE_SETS, viewLimiter } from '../src/game/render/vegetationPlanting';

const [courseId, out, mpp = '3', ...box] = process.argv.slice(2);
const course = COURSES[courseId as keyof typeof COURSES];
const track = new Track(course.design);
const terrain = buildTerrain(track, course.landform);
const lf = terrain.landform;
const g = terrain.near;
const m = +mpp;
const [bx0, bz0, bx1, bz1] = box.length === 4 ? box.map(Number) : [g.x0, g.z0, g.x0 + (g.nx - 1) * g.cell, g.z0 + (g.nz - 1) * g.cell];
const W = Math.round((bx1 - bx0) / m), H = Math.round((bz1 - bz0) / m);
const px = new Uint8Array(W * H * 3);
const set = (i: number, j: number, r: number, gg: number, b: number, a = 1) => {
  if (i < 0 || j < 0 || i >= W || j >= H) return;
  const k = (j * W + i) * 3;
  px[k] = px[k] * (1 - a) + r * a;
  px[k + 1] = px[k + 1] * (1 - a) + gg * a;
  px[k + 2] = px[k + 2] * (1 - a) + b * a;
};
const disc = (x: number, z: number, rad: number, c: [number, number, number], a = 1) => {
  const ci = (x - bx0) / m, cj = (z - bz0) / m, rr = Math.max(0.6, rad / m);
  for (let j = Math.floor(cj - rr); j <= cj + rr; j++) for (let i = Math.floor(ci - rr); i <= ci + rr; i++) if ((i + 0.5 - ci) ** 2 + (j + 0.5 - cj) ** 2 <= rr * rr) set(i, j, c[0], c[1], c[2], a);
};
// the land
for (let j = 0; j < H; j++)
  for (let i = 0; i < W; i++) {
    const x = bx0 + (i + 0.5) * m, z = bz0 + (j + 0.5) * m;
    const y = terrain.heightAt(x, z);
    const sx = (terrain.heightAt(x + 4, z) - terrain.heightAt(x - 4, z)) / 8, sz = (terrain.heightAt(x, z + 4) - terrain.heightAt(x, z - 4)) / 8;
    const shade = Math.max(0.25, Math.min(1, 0.7 - sx * 0.5 - sz * 0.35));
    const steep = Math.hypot(sx, sz);
    if (lf.waterLevel !== null && y <= lf.waterLevel + 0.3) set(i, j, 40, 70, 120);
    else if (steep > 1.25) set(i, j, 150 * shade, 120 * shade, 110 * shade);
    else set(i, j, 190 * shade, 180 * shade, 160 * shade);
  }
const touge = course.style === 'touge';
const limit = touge ? viewLimiter(track, terrain) : undefined;
const ids = TREE_SETS[course.style];
const trees = plantTrees(terrain, +(process.env.DENSITY ?? 1), course.style, ids, { views: limit });
const COL: Record<string, [number, number, number]> = { sugi: [20, 70, 30], hinoki: [35, 85, 45], buna: [95, 110, 30], akamatsu: [20, 90, 90], fichte: [20, 70, 30], birke: [120, 130, 50] };
let small = 0;
for (const t of trees) {
  const id = ids[t.species];
  const grown = (SPECIES[id].scale[0] + SPECIES[id].scale[1]) / 2;
  const k = Math.min(1, t.scale / grown);
  if (k < 0.7) small++;
  const c = COL[id] ?? [30, 80, 30];
  const pale = (1 - k) * 0.6;
  disc(t.x, t.z, 3.2 * t.scale, [c[0] + (255 - c[0]) * pale, c[1] + (255 - c[1]) * pale, c[2] + (255 - c[2]) * pale], 0.85);
}
const cover = plantCover(track, terrain, 1, [], COVER_SETS[course.style], [], { undergrowth: 0, style: course.style, views: limit });
for (const b of cover.cover) {
  const id = COVER_SETS[course.style][b.species];
  disc(b.x, b.z, id === 'iwa' ? 1 : 1.2 * b.scale, id === 'iwa' ? [90, 90, 95] : [230, 140, 30]);
}
// the road, and where it looks out
const p = new THREE.Vector3();
for (let s = 0; s < track.length; s += 1) {
  track.pointAt(s, 0, p);
  disc(p.x, p.z, track.widthAt(s) / 2, [255, 255, 255]);
}
if (touge) {
  for (const v of roadViews(track, terrain)) {
    for (let k = 0; k < 16; k++) {
      if (!((v.open >> k) & 1)) continue;
      const a = ((k + 0.5) / 16) * Math.PI * 2;
      for (let d = 6; d < 16; d += m) disc(v.x + Math.cos(a) * d, v.z + Math.sin(a) * d, m * 0.5, [220, 40, 40], 0.7);
    }
  }
}
fs.writeFileSync(out, Buffer.concat([Buffer.from(`P6\n${W} ${H}\n255\n`), Buffer.from(px)]));
console.log(courseId, `${W}×${H}`, `trees ${trees.length} (${small} under 0.7 of a grown one), bushes and rocks ${cover.cover.length}`);
