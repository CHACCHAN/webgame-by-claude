import { Track } from '../../src/game/track/Track';
import { OBORO_DOWNHILL } from '../../src/game/track/courseDesign';
import { buildTerrain } from '../../src/game/track/terrain';
const t = new Track(OBORO_DOWNHILL);
const ter = buildTerrain(t);
for (let s = 60; s < 1100; s += 30) {
  const p = t.pointAt(s, 0);
  const r = t.getRight(Math.round(s));
  const h = (d: number) => ter.heightAt(p.x + r.x * d, p.z + r.z * d) - p.y;
  // does the low side face south (towards the city)?
  const lowRight = h(30) < h(-30);
  const dirZ = lowRight ? r.z : -r.z;
  console.log(s, 'R30', h(30).toFixed(0), 'L30', h(-30).toFixed(0), 'lowSide', lowRight ? 'R' : 'L', 'facesSouth', dirZ.toFixed(2), 'curv', t.curvature[Math.round(s)].toFixed(3));
}
