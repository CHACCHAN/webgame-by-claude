import * as THREE from 'three';
import { rng } from '../util/math';

/**
 * Procedural textures of the AUTOBAHN course (no photo pixels): the road marking atlas and the noise-wall panels.
 *
 * Road atlas: u spans ATLAS_W metres across, v spans ATLAS_L metres along (it repeats along the road). Layouts side
 * by side, each measured from its surface's left asphalt edge (the drivable edge is SHOULDER = 0.6 m inside it):
 *  - MAIN (0): our carriageway, 14.5 m drivable: edge line by the median, two dashed lane lines (German pattern 6 m
 *    line / 12 m gap, 0.15 m wide), the solid edge line before the hard shoulder (0.30 m);
 *  - EXIT (16): the same with the edge line as broad dashes (the exit lane on the hard shoulder);
 *  - SLIP (32): a slip road, 8 m of asphalt with solid edge lines;
 *  - PLAIN (40): a country road (the overpasses' roads): edge lines and a dashed centre line.
 */
export const ATLAS_W = 48;
export const ATLAS_L = 18;
export const LAYOUT = { main: 0, exit: 16, slip: 32, plain: 40 } as const;

/** A periodic value-noise field (wraps across W and H), values 0..1. */
function periodicNoise(W: number, H: number, cellsX: number, cellsY: number, seed: number) {
  const r = rng(seed);
  const lattice = new Float32Array(cellsX * cellsY).map(() => r());
  const out = new Float32Array(W * H);
  for (let y = 0; y < H; y++) {
    const gy = (y / H) * cellsY, j = Math.floor(gy), fy = gy - j;
    const sy = fy * fy * (3 - 2 * fy);
    const j0 = j % cellsY, j1 = (j + 1) % cellsY;
    for (let x = 0; x < W; x++) {
      const gx = (x / W) * cellsX, i = Math.floor(gx), fx = gx - i;
      const sx = fx * fx * (3 - 2 * fx);
      const i0 = i % cellsX, i1 = (i + 1) % cellsX;
      const a = lattice[j0 * cellsX + i0], b = lattice[j0 * cellsX + i1];
      const c = lattice[j1 * cellsX + i0], d = lattice[j1 * cellsX + i1];
      out[y * W + x] = (a + (b - a) * sx) * (1 - sy) + (c + (d - c) * sx) * sy;
    }
  }
  return out;
}

/** The marking atlas on fine dark motorway asphalt. `scale` 1 = 2048 × 1024 px, 0.5 for the low quality setting. */
export function makeAutobahnRoadTexture(scale = 1): THREE.Texture {
  const W = Math.round(2048 * scale), H = Math.round(1024 * scale);
  const c = document.createElement('canvas');
  c.width = W;
  c.height = H;
  const g = c.getContext('2d')!;
  const r = rng(1977);
  // asphalt: two octaves of periodic noise (patches, ~1 m and ~0.25 m), grain and light aggregate
  const n1 = periodicNoise(W, H, 48, 18, 3), n2 = periodicNoise(W, H, 192, 72, 4);
  const img = g.createImageData(W, H);
  for (let k = 0; k < W * H; k++) {
    let v = 50 + n1[k] * 16 + n2[k] * 9 + (r() - 0.5) * 22;
    if (r() < 0.01) v += 30 * r();
    const o = k * 4;
    img.data[o] = v;
    img.data[o + 1] = v;
    img.data[o + 2] = v + 2;
    img.data[o + 3] = 255;
  }
  g.putImageData(img, 0, 0);
  const X = (m: number) => (m / ATLAS_W) * W;
  const Y = (m: number) => (m / ATLAS_L) * H;
  // polished wheel tracks in each lane (lane centres measured from the drivable edge, 0.6 m in)
  g.fillStyle = 'rgba(255,255,255,0.035)';
  for (const base of [LAYOUT.main, LAYOUT.exit])
    for (const lane of [2.625, 6.375, 10.125]) for (const d of [-0.9, 0.9]) g.fillRect(X(base + 0.6 + lane + d - 0.35), 0, X(0.7), H);
  // markings: [atlas metres from, to] and the dash pattern along (metres: line, gap, repeated over ATLAS_L)
  const paint = 'rgba(234,234,226,0.93)';
  const line = (m0: number, m1: number, dash?: [number, number]) => {
    g.fillStyle = paint;
    if (!dash) g.fillRect(X(m0), 0, X(m1) - X(m0), H);
    else for (let y = 0; y < ATLAS_L - 1e-6; y += dash[0] + dash[1]) g.fillRect(X(m0), Y(y), X(m1) - X(m0), Y(dash[0]));
  };
  for (const base of [LAYOUT.main, LAYOUT.exit]) {
    const edge = base + 0.6;
    line(edge + 0.45, edge + 0.75);
    line(edge + 4.5 - 0.075, edge + 4.5 + 0.075, [6, 12]);
    line(edge + 8.25 - 0.075, edge + 8.25 + 0.075, [6, 12]);
    if (base === LAYOUT.main) line(edge + 12.0, edge + 12.3);
    else line(edge + 12.0, edge + 12.3, [6, 3]);
  }
  line(LAYOUT.slip + 0.6, LAYOUT.slip + 0.75);
  line(LAYOUT.slip + 7.25, LAYOUT.slip + 7.4);
  line(LAYOUT.plain + 0.4, LAYOUT.plain + 0.52);
  line(LAYOUT.plain + 7.48, LAYOUT.plain + 7.6);
  line(LAYOUT.plain + 3.94, LAYOUT.plain + 4.06, [3, 6]);
  // worn paint: darken the markings in noisy patches
  const wear = g.getImageData(0, 0, W, H);
  const n3 = periodicNoise(W, H, 384, 144, 9);
  for (let k = 0; k < W * H; k++) {
    const o = k * 4;
    if (wear.data[o] > 140 && n3[k] < 0.22) {
      wear.data[o] *= 0.78;
      wear.data[o + 1] *= 0.78;
      wear.data[o + 2] *= 0.78;
    }
  }
  g.putImageData(wear, 0, 0);
  // a few sealed cracks
  g.strokeStyle = 'rgba(16,16,18,0.5)';
  g.lineWidth = Math.max(1, 3 * scale);
  for (let i = 0; i < 10; i++) {
    g.beginPath();
    let x = r() * W, y = r() * H;
    g.moveTo(x, y);
    for (let k = 0; k < 6; k++) {
      x += (r() - 0.5) * 40 * scale;
      y += r() * 60 * scale;
      g.lineTo(x, y);
    }
    g.stroke();
  }
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.anisotropy = 8;
  t.generateMipmaps = true;
  t.minFilter = THREE.LinearMipmapLinearFilter;
  return t;
}

/** Noise-wall panels: horizontal aluminium cassettes (0.5 m) in grey-green, one tile = 4 m along × 4.5 m up. */
export function makeNoiseWallTexture(): THREE.Texture {
  const W = 256, H = 288;
  const c = document.createElement('canvas');
  c.width = W;
  c.height = H;
  const g = c.getContext('2d')!;
  const r = rng(31);
  g.fillStyle = '#6f7d72';
  g.fillRect(0, 0, W, H);
  const cass = H / 9;
  for (let k = 0; k < 9; k++) {
    const y = k * cass;
    const tone = 104 + Math.round((r() - 0.5) * 10);
    g.fillStyle = `rgb(${tone - 6},${tone + 10},${tone})`;
    g.fillRect(0, y + 2, W, cass - 4);
    // the cassette's perforated ribs
    g.fillStyle = 'rgba(0,0,0,0.12)';
    for (let x = 0; x < W; x += 6) g.fillRect(x, y + 6, 2, cass - 12);
    g.fillStyle = 'rgba(0,0,0,0.45)';
    g.fillRect(0, y, W, 2);
    g.fillStyle = 'rgba(255,255,255,0.12)';
    g.fillRect(0, y + 2, W, 2);
  }
  // grime towards the bottom
  const grd = g.createLinearGradient(0, H * 0.7, 0, H);
  grd.addColorStop(0, 'rgba(30,30,24,0)');
  grd.addColorStop(1, 'rgba(30,30,24,0.45)');
  g.fillStyle = grd;
  g.fillRect(0, 0, W, H);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.anisotropy = 4;
  return t;
}

/** Anti-glare slats on the median (alpha-tested): one tile = 1 m along × 1 m up, five slats with gaps between. */
export function makeAntiGlareTexture(): THREE.Texture {
  const S = 128;
  const c = document.createElement('canvas');
  c.width = c.height = S;
  const g = c.getContext('2d')!;
  g.clearRect(0, 0, S, S);
  for (let k = 0; k < 5; k++) {
    const x = (k / 5) * S;
    const grd = g.createLinearGradient(x, 0, x + S / 10, 0);
    grd.addColorStop(0, '#3c5a46');
    grd.addColorStop(1, '#22382b');
    g.fillStyle = grd;
    g.fillRect(x, 0, S / 10, S);
  }
  // the rails that hold them
  g.fillStyle = '#5d625f';
  g.fillRect(0, 6, S, 6);
  g.fillRect(0, S - 12, S, 6);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.anisotropy = 4;
  return t;
}

/** Wildlife fence (alpha-tested knotted mesh, wider at the top): one tile = 2 m along × 1.6 m up. */
export function makeFenceTexture(): THREE.Texture {
  const W = 256, H = 204;
  const c = document.createElement('canvas');
  c.width = W;
  c.height = H;
  const g = c.getContext('2d')!;
  g.clearRect(0, 0, W, H);
  g.strokeStyle = 'rgba(176,182,180,1)';
  g.lineWidth = 2;
  // horizontal wires closer together near the ground
  for (let k = 0; k <= 12; k++) {
    const y = H - Math.pow(k / 12, 1.4) * (H - 3) - 1;
    g.beginPath();
    g.moveTo(0, y);
    g.lineTo(W, y);
    g.stroke();
  }
  for (let x = 0; x < W; x += 19) {
    g.beginPath();
    g.moveTo(x + 1, 0);
    g.lineTo(x + 1, H);
    g.stroke();
  }
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.anisotropy = 4;
  return t;
}
