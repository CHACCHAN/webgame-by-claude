// Renders a top-down map + elevation profile of the course to SVG and reports
// layout problems (legs that come too close to each other).
import { writeFileSync } from 'node:fs';
import { Track } from '../src/game/track/Track';
import { OBORO_DOWNHILL, KIRIFURI_LAKESIDE, TENROU_SKYLINE } from '../src/game/track/courseDesign';

const designs = { oboro: OBORO_DOWNHILL, kirifuri: KIRIFURI_LAKESIDE, tenrou: TENROU_SKYLINE };
const t = new Track(designs[(process.argv[3] ?? 'oboro') as keyof typeof designs]);
const out = process.argv[2] ?? 'track.svg';
let minX = Infinity, maxX = -Infinity, minZ = Infinity, maxZ = -Infinity, minY = Infinity, maxY = -Infinity;
for (let i = 0; i < t.count; i++) {
  const x = t.pos[i * 3], y = t.pos[i * 3 + 1], z = t.pos[i * 3 + 2];
  minX = Math.min(minX, x); maxX = Math.max(maxX, x);
  minZ = Math.min(minZ, z); maxZ = Math.max(maxZ, z);
  minY = Math.min(minY, y); maxY = Math.max(maxY, y);
}
const pad = 60, scale = 0.5;
const W = (maxX - minX + pad * 2) * scale, H = (maxZ - minZ + pad * 2) * scale;
const px = (x: number) => (x - minX + pad) * scale;
const pz = (z: number) => (z - minZ + pad) * scale;
let svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${W + 20}" height="${H + 260}" style="background:#111">`;
for (let i = 0; i < t.count - 1; i += 2) {
  const y = t.pos[i * 3 + 1];
  const c = Math.round(((y - minY) / (maxY - minY)) * 255);
  const zone = t.zone[i];
  const col = zone === 'bridge' ? '#4af' : zone === 'rockshed' ? '#fa4' : zone === 'lakeside' ? '#0ff' : zone === 'crest' ? '#f0f' : `rgb(${c},${255 - c},120)`;
  svg += `<line x1="${px(t.pos[i * 3])}" y1="${pz(t.pos[i * 3 + 2])}" x2="${px(t.pos[i * 3 + 6])}" y2="${pz(t.pos[i * 3 + 8])}" stroke="${col}" stroke-width="${t.width[i] * scale}"/>`;
}
for (let s = 0; s < t.length; s += 250) {
  const p = t.pointAt(s);
  svg += `<text x="${px(p.x) + 6}" y="${pz(p.z)}" fill="#fff" font-size="11">${s}m</text>`;
}
// elevation profile
const py0 = H + 30;
let d = '';
for (let i = 0; i < t.count; i += 4) {
  const x = (i / t.count) * W;
  const y = py0 + 200 - ((t.pos[i * 3 + 1] - minY) / (maxY - minY)) * 200;
  d += (i === 0 ? 'M' : 'L') + x.toFixed(1) + ',' + y.toFixed(1);
}
svg += `<path d="${d}" stroke="#fff" fill="none"/></svg>`;
writeFileSync(out, svg);

// Layout checks
const problems: string[] = [];
for (let i = 0; i < t.count; i += 3) {
  for (let j = i + 120; j < t.count; j += 3) {
    const dx = t.pos[i * 3] - t.pos[j * 3], dz = t.pos[i * 3 + 2] - t.pos[j * 3 + 2];
    const dy = t.pos[i * 3 + 1] - t.pos[j * 3 + 1];
    const dist = Math.hypot(dx, dz);
    const need = (t.width[i] + t.width[j]) / 2 + 14;
    if (dist < need) problems.push(`s=${i} vs s=${j}: ${dist.toFixed(1)}m apart (dy ${dy.toFixed(1)})`);
  }
}
const end = t.getPos(t.count - 1);
console.log(`length ${t.length.toFixed(0)}m, drop ${(maxY - minY).toFixed(0)}m (y ${maxY.toFixed(0)}..${minY.toFixed(0)}), x ${minX.toFixed(0)}..${maxX.toFixed(0)}, z ${minZ.toFixed(0)}..${maxZ.toFixed(0)}, end (${end.x.toFixed(0)},${end.z.toFixed(0)})`);
console.log(problems.length ? `${problems.length} proximity problems, e.g.\n` + problems.filter((_, k) => k % 10 === 0).slice(0, 12).join('\n') : 'no proximity problems');
