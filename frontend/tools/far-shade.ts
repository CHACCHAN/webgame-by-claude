// The baked far shade of a course from above, as a picture, and how long the bake takes:
//   npx tsx tools/far-shade.ts <course> [moon|sun] [out.ppm]
// Grey = lit ground, dark = in the land's own shade, blue-dark = shaded by the trees' crowns only (plain discs of the
// planting stand in for the models here: no GLB is loaded in Node), white = the road.
// (PPM: `python3 -c "from PIL import Image; import sys; Image.open(sys.argv[1]).save(sys.argv[2])" a.ppm a.png`.)
import * as fs from 'node:fs';
import * as THREE from 'three';
import { COURSES } from '../src/game/track/courses';
import { Track } from '../src/game/track/Track';
import { buildTerrain } from '../src/game/track/terrain';
import { bakeShade, litUnder, shadeAt, shadeScene, SHADE_SIZE, type ShadeCaster } from '../src/game/render/farShade';
import { plantTrees, TREE_SETS } from '../src/game/render/vegetationPlanting';

/** the morning sun (`PRESETS.dawn.keyDir` of render/Environment.ts, which does not load in Node) */
const SUN = new THREE.Vector3(0.82, 0.16, 0.55).normalize();

const [courseId = 'oboro-downhill', light = 'sun', out] = process.argv.slice(2);
const course = COURSES[courseId as keyof typeof COURSES];
const track = new Track(course.design);
const terrain = buildTerrain(track, course.landform);
const ids = TREE_SETS[course.style ?? 'touge'];
const casters: ShadeCaster[] = plantTrees(terrain, 1, course.style ?? 'touge', ids).filter((p) => p.casts !== false && !p.far).map((p) => ({ x: p.x, z: p.z, r: 2.4 * p.scale * p.girth, top: p.y + 13 * p.scale }));
let t = performance.now();
const scene = shadeScene(terrain, casters);
const tScene = performance.now() - t;
const dir = light === 'sun' ? SUN : new THREE.Vector3(...terrain.landform.moonDir).normalize();
t = performance.now();
const field = bakeShade(scene, dir);
const tBake = performance.now() - t;
let land = 0, all = 0;
const N = SHADE_SIZE;
const px = new Uint8Array(N * N * 3);
for (let j = 0; j < N; j++)
  for (let i = 0; i < N; i++) {
    const x = field.x0 + (i + 0.5) * field.cx, z = field.z0 + (j + 0.5) * field.cz;
    const y = scene.land[j * N + i];
    const [a, b] = shadeAt(field, x, z);
    const la = litUnder(field, a, y), lb = litUnder(field, b, y);
    land += 1 - la;
    all += 1 - lb;
    const road = terrain.roadDistAt(x, z) < 5;
    const o = (j * N + i) * 3;
    px[o] = road ? 255 * (0.35 + 0.65 * lb) : 40 + 150 * lb;
    px[o + 1] = road ? 255 * (0.35 + 0.65 * lb) : 40 + 150 * lb;
    px[o + 2] = road ? 255 * (0.35 + 0.65 * lb) : 60 + 130 * la;
  }
console.log(courseId, light, `cells ${field.cx.toFixed(2)} × ${field.cz.toFixed(2)} m, soft ${field.soft.toFixed(2)} m, trees ${casters.length}`);
console.log(`heights ${tScene.toFixed(0)} ms, sweep ${tBake.toFixed(0)} ms; in the land's shade ${((land / N / N) * 100).toFixed(1)} %, with trees ${((all / N / N) * 100).toFixed(1)} %`);
// the road: how much of it is shaded
let rs = 0, rl = 0;
const p = new THREE.Vector3();
for (let s = 0; s < track.count; s += 5) {
  track.pointAt(s, 0, p);
  const [a, b] = shadeAt(field, p.x, p.z);
  rl += 1 - litUnder(field, a, p.y + 0.05);
  rs += 1 - litUnder(field, b, p.y + 0.05);
}
const n = Math.ceil(track.count / 5);
console.log(`road: in the land's shade ${((rl / n) * 100).toFixed(1)} %, with trees ${((rs / n) * 100).toFixed(1)} %`);
if (out) fs.writeFileSync(out, Buffer.concat([Buffer.from(`P6 ${N} ${N} 255\n`), px]));
