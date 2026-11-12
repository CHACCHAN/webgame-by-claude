// How much of a course's road lies in the land's own shade, by the sun's bearing (0 = +x, 90 = +z) and height:
//   npx tsx tools/sun-sweep.ts <course> <degrees up> [more heights…]   (for choosing a landform's `dawnSun`)
import * as THREE from 'three';
import { COURSES } from '../src/game/track/courses';
import { Track } from '../src/game/track/Track';
import { buildTerrain } from '../src/game/track/terrain';
import { bakeShade, litUnder, shadeAt, shadeScene } from '../src/game/render/farShade';

const [id, ...els] = process.argv.slice(2);
const course = (COURSES as any)[id];
const track = new Track(course.design);
const terrain = buildTerrain(track, course.landform);
const scene = shadeScene(terrain, []);
const p = new THREE.Vector3();
for (const elDeg of els.map(Number)) {
  const out: string[] = [];
  for (let deg = 0; deg < 360; deg += 15) {
    const a = (deg * Math.PI) / 180, el = (elDeg * Math.PI) / 180;
    const dir = new THREE.Vector3(Math.cos(a) * Math.cos(el), Math.sin(el), Math.sin(a) * Math.cos(el));
    const f = bakeShade(scene, dir);
    let n = 0, dark = 0;
    for (let s = 0; s < track.count; s += 10) {
      track.pointAt(s, 0, p);
      dark += 1 - litUnder(f, shadeAt(f, p.x, p.z)[0], p.y + 0.05);
      n++;
    }
    out.push(`${deg}:${Math.round((dark / n) * 100)}`);
  }
  console.log(id, `sun ${elDeg} deg up; bearing (0 = +x, 90 = +z): % of the road in the land's shade:`, out.join(' '));
}
