// Writes a hillshaded PNG-able PPM of the near terrain grid with the road overlaid.
import { writeFileSync } from 'node:fs';
import { Track } from '../src/game/track/Track';
import { OBORO_DOWNHILL } from '../src/game/track/courseDesign';
import { buildTerrain } from '../src/game/track/terrain';

const track = new Track(OBORO_DOWNHILL);
const t0 = performance.now();
const terrain = buildTerrain(track);
console.log('terrain built in', (performance.now() - t0).toFixed(0), 'ms', terrain.near.nx, 'x', terrain.near.nz);
const g = terrain.near;
const img = Buffer.alloc(g.nx * g.nz * 3);
let minH = Infinity, maxH = -Infinity;
for (const h of g.heights) { minH = Math.min(minH, h); maxH = Math.max(maxH, h); }
for (let j = 1; j < g.nz - 1; j++)
  for (let i = 1; i < g.nx - 1; i++) {
    const h = g.heights[j * g.nx + i];
    const dx = g.heights[j * g.nx + i + 1] - g.heights[j * g.nx + i - 1];
    const dz = g.heights[(j + 1) * g.nx + i] - g.heights[(j - 1) * g.nx + i];
    const shade = Math.max(0, Math.min(1, 0.6 - (dx * 0.6 + dz * 0.4) / (g.cell * 2)));
    const e = (h - minH) / (maxH - minH);
    const o = (j * g.nx + i) * 3;
    const road = (g.roadDist![j * g.nx + i]) < 5;
    img[o] = road ? 255 : Math.round(shade * (80 + e * 150));
    img[o + 1] = road ? 220 : Math.round(shade * (120 + e * 100));
    img[o + 2] = road ? 60 : Math.round(shade * (70 + e * 60));
  }
writeFileSync(process.argv[2] ?? 'terrain.ppm', Buffer.concat([Buffer.from(`P6 ${g.nx} ${g.nz} 255\n`), img]));
console.log('height range', minH.toFixed(0), maxH.toFixed(0));
