import * as THREE from 'three';
import { fbm, noise2, rng } from '../util/math';

/** Canvas helpers for procedurally generated textures (browser only). */
function canvas(w: number, h: number) {
  const c = document.createElement('canvas');
  c.width = w;
  c.height = h;
  return [c, c.getContext('2d')!] as const;
}

function finish(c: HTMLCanvasElement, srgb: boolean, repeat = true) {
  const t = new THREE.CanvasTexture(c);
  if (srgb) t.colorSpace = THREE.SRGBColorSpace;
  if (repeat) t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.anisotropy = 8;
  t.generateMipmaps = true;
  t.minFilter = THREE.LinearMipmapLinearFilter;
  return t;
}

/** Tileable value via wrapping the noise domain on a torus-like scheme. */
function tileNoise(x: number, y: number, period: number, octaves = 4) {
  // blend 4 samples so the texture tiles seamlessly
  const fx = x / period, fy = y / period;
  const a = fbm(x, y, octaves), b = fbm(x - period, y, octaves);
  const c = fbm(x, y - period, octaves), d = fbm(x - period, y - period, octaves);
  return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy;
}

function paintNoiseAsphalt(g: CanvasRenderingContext2D, W: number, H: number, r: () => number) {
  const img = g.createImageData(W, H);
  for (let y = 0; y < H; y++) {
    for (let x = 0; x < W; x++) {
      const n = tileNoise(x / 40, y / 40, W / 40, 4) * 0.5 + tileNoise(x / 6, y / 6, W / 6, 2) * 0.35;
      // worn wheel tracks are slightly lighter & smoother
      const u = x / W;
      const track = Math.exp(-(((u - 0.3) * 9) ** 2)) + Math.exp(-(((u - 0.7) * 9) ** 2));
      let v = 58 + n * 22 + track * 9 + (r() - 0.5) * 26;
      if (r() < 0.012) v += 40 * r(); // light aggregate
      const o = (y * W + x) * 4;
      img.data[o] = v;
      img.data[o + 1] = v;
      img.data[o + 2] = v + 3;
      img.data[o + 3] = 255;
    }
  }
  g.putImageData(img, 0, 0);
}

/**
 * Scanned asphalt tiled at real scale (4 tiles across the ~11 m wide u range,
 * 3 along the 8 m tile), then darker patching and lighter, polished wheel tracks.
 */
function paintPhotoAsphalt(g: CanvasRenderingContext2D, photo: CanvasImageSource, W: number, H: number) {
  const pw = (photo as HTMLImageElement).width || 1024, ph = (photo as HTMLImageElement).height || 1024;
  const pat = g.createPattern(photo, 'repeat')!;
  pat.setTransform(new DOMMatrix().scale(W / 4 / pw, H / 3 / ph));
  g.fillStyle = pat;
  g.fillRect(0, 0, W, H);
  const N = 128;
  const [pc, pg] = canvas(N, N);
  const patch = pg.createImageData(N, N);
  const [tc, tg] = canvas(N, N);
  const tracks = tg.createImageData(N, N);
  for (let y = 0; y < N; y++)
    for (let x = 0; x < N; x++) {
      const o = (y * N + x) * 4;
      const n = tileNoise(x / 16, y / 16, N / 16, 4);
      const v = 255 * Math.min(1, 0.8 + n * 0.35);
      patch.data[o] = patch.data[o + 1] = patch.data[o + 2] = v;
      patch.data[o + 3] = 255;
      const u = x / N;
      const t = Math.exp(-(((u - 0.3) * 9) ** 2)) + Math.exp(-(((u - 0.7) * 9) ** 2));
      tracks.data[o] = tracks.data[o + 1] = tracks.data[o + 2] = 255;
      tracks.data[o + 3] = 255 * t * 0.07;
    }
  pg.putImageData(patch, 0, 0);
  tg.putImageData(tracks, 0, 0);
  g.globalCompositeOperation = 'multiply';
  g.drawImage(pc, 0, 0, W, H);
  g.globalCompositeOperation = 'screen';
  g.drawImage(tc, 0, 0, W, H);
  g.globalCompositeOperation = 'source-over';
}

/**
 * Road albedo: asphalt with aggregate and wear, white edge lines and an
 * orange no-overtaking centre line. u spans the road width, the tile covers
 * 8 m along the road.
 */
export function makeRoadTexture(photo?: CanvasImageSource | null): THREE.Texture {
  const W = photo ? 1024 : 512, H = 1024;
  const [c, g] = canvas(W, H);
  const r = rng(42);
  if (photo) paintPhotoAsphalt(g, photo, W, H);
  else paintNoiseAsphalt(g, W, H, r);

  // markings (road u in [0,1] maps to width incl. shoulders)
  const line = (u0: number, u1: number, color: string, dash?: [number, number]) => {
    g.fillStyle = color;
    const x0 = u0 * W, x1 = u1 * W;
    if (!dash) g.fillRect(x0, 0, x1 - x0, H);
    else for (let y = 0; y < H; y += dash[0] + dash[1]) g.fillRect(x0, y, x1 - x0, dash[0]);
  };
  line(0.055, 0.07, 'rgba(235,235,228,0.92)');
  line(0.93, 0.945, 'rgba(235,235,228,0.92)');
  line(0.488, 0.512, 'rgba(236,160,40,0.95)');
  // wear on the paint
  const wear = g.getImageData(0, 0, W, H);
  for (let y = 0; y < H; y++)
    for (let x = 0; x < W; x++) {
      const o = (y * W + x) * 4;
      const n = noise2(x / 9, y / 9) * 0.5 + 0.5;
      if (wear.data[o] > 120 && n < 0.32) {
        const k = 0.55;
        wear.data[o] *= k;
        wear.data[o + 1] *= k;
        wear.data[o + 2] *= k;
      }
    }
  g.putImageData(wear, 0, 0);
  // tar seams
  g.strokeStyle = 'rgba(20,20,22,0.55)';
  g.lineWidth = 3;
  for (let i = 0; i < 6; i++) {
    g.beginPath();
    let x = r() * W, y = r() * H;
    g.moveTo(x, y);
    for (let k = 0; k < 8; k++) {
      x += (r() - 0.5) * 80;
      y += r() * 60;
      g.lineTo(x, y);
    }
    g.stroke();
  }
  return finish(c, true);
}

/** Normal map from a height function (tileable). */
function normalFromHeight(W: number, H: number, height: (x: number, y: number) => number, strength: number) {
  const [c, g] = canvas(W, H);
  const hts = new Float32Array(W * H);
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) hts[y * W + x] = height(x, y);
  const img = g.createImageData(W, H);
  for (let y = 0; y < H; y++)
    for (let x = 0; x < W; x++) {
      const l = hts[y * W + ((x - 1 + W) % W)], rr = hts[y * W + ((x + 1) % W)];
      const u = hts[((y - 1 + H) % H) * W + x], d = hts[((y + 1) % H) * W + x];
      let nx = (l - rr) * strength, ny = (u - d) * strength;
      const nz = 1;
      const len = Math.hypot(nx, ny, nz);
      nx /= len;
      ny /= len;
      const o = (y * W + x) * 4;
      img.data[o] = (nx * 0.5 + 0.5) * 255;
      img.data[o + 1] = (ny * 0.5 + 0.5) * 255;
      img.data[o + 2] = (nz / len) * 255;
      img.data[o + 3] = 255;
    }
  g.putImageData(img, 0, 0);
  return finish(c, false);
}

export function makeAsphaltNormal(): THREE.Texture {
  const r = rng(9);
  const grain = new Float32Array(256 * 256).map(() => r());
  return normalFromHeight(256, 256, (x, y) => grain[y * 256 + x] * 0.6 + tileNoise(x / 10, y / 10, 25.6, 3) * 0.8, 1.6);
}

/** Greyscale detail for terrain (multiplied with vertex colours). */
export function makeGroundDetail(): THREE.Texture {
  const W = 256;
  const [c, g] = canvas(W, W);
  const img = g.createImageData(W, W);
  const r = rng(5);
  for (let y = 0; y < W; y++)
    for (let x = 0; x < W; x++) {
      const n = tileNoise(x / 16, y / 16, W / 16, 4) * 0.5 + 0.5;
      const v = 150 + n * 90 + (r() - 0.5) * 40;
      const o = (y * W + x) * 4;
      img.data[o] = v;
      img.data[o + 1] = v;
      img.data[o + 2] = v;
      img.data[o + 3] = 255;
    }
  g.putImageData(img, 0, 0);
  return finish(c, true);
}

export function makeGroundNormal(): THREE.Texture {
  return normalFromHeight(256, 256, (x, y) => tileNoise(x / 12, y / 12, 256 / 12, 4) + tileNoise(x / 3, y / 3, 256 / 3, 2) * 0.3, 2.2);
}

/** Concrete with a lattice of slope-protection frames (法枠). */
export function makeConcreteTexture(lattice: boolean, photo?: CanvasImageSource | null): THREE.Texture {
  const W = photo ? 512 : 256;
  const [c, g] = canvas(W, W);
  const r = rng(77);
  if (photo) {
    g.drawImage(photo, 0, 0, W, W);
    // weathering: darker towards the foot of the wall
    const grad = g.createLinearGradient(0, 0, 0, W);
    grad.addColorStop(0, 'rgba(0,0,0,0)');
    grad.addColorStop(1, 'rgba(20,22,16,0.22)');
    g.fillStyle = grad;
    g.fillRect(0, 0, W, W);
  } else {
    const img = g.createImageData(W, W);
    for (let y = 0; y < W; y++)
      for (let x = 0; x < W; x++) {
        const n = tileNoise(x / 20, y / 20, W / 20, 4);
        const v = 150 + n * 30 + (r() - 0.5) * 20 - (y / W) * 18;
        const o = (y * W + x) * 4;
        img.data[o] = v;
        img.data[o + 1] = v * 0.99;
        img.data[o + 2] = v * 0.95;
        img.data[o + 3] = 255;
      }
    g.putImageData(img, 0, 0);
  }
  const q = W / 2;
  if (lattice) {
    g.fillStyle = 'rgba(40,52,30,0.55)';
    for (let i = 0; i < 2; i++)
      for (let j = 0; j < 2; j++) g.fillRect(i * q + q * 0.11, j * q + q * 0.11, q * 0.78, q * 0.78);
    g.strokeStyle = 'rgba(255,255,255,0.12)';
    g.lineWidth = W / 64;
    for (let i = 0; i <= 2; i++) {
      g.beginPath();
      g.moveTo(i * q, 0);
      g.lineTo(i * q, W);
      g.moveTo(0, i * q);
      g.lineTo(W, i * q);
      g.stroke();
    }
  }
  // streaks
  g.fillStyle = 'rgba(30,30,28,0.08)';
  for (let i = 0; i < 24; i++) g.fillRect(r() * W, 0, (2 + r() * 4) * (W / 256), W);
  return finish(c, true);
}

/**
 * Conifer foliage atlas. u 0..0.875: sprays of drooping branchlets with needles on a transparent
 * background (v = 0 at the trunk, 1 at the ragged branch tips, cut out with alphaTest);
 * u 0.9..1: opaque white so trunks and distant trees show only their vertex colours.
 */
export function makeFoliageTexture(): THREE.Texture {
  const W = 512, H = 256, FW = W * 0.875;
  const [c, g] = canvas(W, H);
  const r = rng(31);
  g.lineCap = 'round';
  // dense inner mass so the crown reads as solid near the trunk
  const grad = g.createLinearGradient(0, 0, 0, H);
  grad.addColorStop(0, 'rgba(34,52,30,1)');
  grad.addColorStop(0.4, 'rgba(40,60,34,0.95)');
  grad.addColorStop(0.55, 'rgba(40,60,34,0)');
  g.fillStyle = grad;
  g.fillRect(0, 0, FW, H);
  // branchlets: a stem from the inner part outwards (down the texture) with needles on both sides
  // only some branchlets reach the tips, so the alpha cut-out leaves a ragged, see-through edge
  for (let k = 0; k < 260; k++) {
    let x = 6 + r() * (FW - 12), y = r() * H * 0.3;
    const len = H * (0.3 + r() ** 1.6 * 0.7);
    const dir = (r() - 0.5) * 0.5;
    const shade = 0.75 + r() * 0.5;
    const steps = 14;
    for (let i = 0; i < steps; i++) {
      const nx = x + Math.sin(dir + i * 0.03) * (len / steps) * 0.4;
      const ny = y + len / steps;
      const t = i / steps;
      const col = `rgb(${Math.round(38 * shade + t * 22)},${Math.round(62 * shade + t * 34)},${Math.round(32 * shade + t * 14)})`;
      g.strokeStyle = col;
      g.lineWidth = 2.2 * (1 - t * 0.6);
      g.beginPath(); g.moveTo(x, y); g.lineTo(nx, ny); g.stroke();
      // needles
      g.lineWidth = 1.1;
      const nl = 11 * (1 - t * 0.4);
      for (const side of [-1, 1]) {
        g.beginPath();
        g.moveTo(nx, ny);
        g.lineTo(nx + side * nl * (0.7 + r() * 0.5), ny + nl * (0.25 + r() * 0.35));
        g.stroke();
      }
      x = Math.min(FW - 3, Math.max(3, nx));
      y = ny;
      if (y > H - 3) break;
    }
  }
  g.fillStyle = '#ffffff';
  g.fillRect(W * 0.9, 0, W * 0.1, H);
  const t = finish(c, true, false);
  t.wrapS = t.wrapT = THREE.ClampToEdgeWrapping;
  t.flipY = false; // v grows down the canvas: trunk side at v = 0, ragged tips at v = 1
  return t;
}

/** Soft round sprite used for lights, smoke and city glows. */
export function makeGlowTexture(): THREE.Texture {
  const W = 128;
  const [c, g] = canvas(W, W);
  const grad = g.createRadialGradient(W / 2, W / 2, 0, W / 2, W / 2, W / 2);
  grad.addColorStop(0, 'rgba(255,255,255,1)');
  grad.addColorStop(0.18, 'rgba(255,255,255,0.75)');
  grad.addColorStop(0.45, 'rgba(255,255,255,0.18)');
  grad.addColorStop(1, 'rgba(255,255,255,0)');
  g.fillStyle = grad;
  g.fillRect(0, 0, W, W);
  return finish(c, false, false);
}

export function makeSmokeTexture(): THREE.Texture {
  const W = 128;
  const [c, g] = canvas(W, W);
  const img = g.createImageData(W, W);
  for (let y = 0; y < W; y++)
    for (let x = 0; x < W; x++) {
      const dx = (x - W / 2) / (W / 2), dy = (y - W / 2) / (W / 2);
      const d = Math.sqrt(dx * dx + dy * dy);
      const n = fbm(x / 18, y / 18, 4) * 0.5 + 0.5;
      const a = Math.max(0, 1 - d) ** 1.6 * (0.55 + n * 0.6);
      const o = (y * W + x) * 4;
      img.data[o] = 255;
      img.data[o + 1] = 255;
      img.data[o + 2] = 255;
      img.data[o + 3] = Math.min(255, a * 255);
    }
  g.putImageData(img, 0, 0);
  return finish(c, false, false);
}

/** Simple sign face textures drawn on a canvas. */
export function makeSignTexture(kind: 'chevronL' | 'chevronR' | 'hairpin' | 'speed40' | 'start' | 'finish' | 'kanban'): THREE.Texture {
  const [c, g] = canvas(256, 256);
  if (kind === 'chevronL' || kind === 'chevronR') {
    g.fillStyle = '#f2c21a';
    g.fillRect(0, 0, 256, 256);
    g.fillStyle = '#111';
    for (let i = 0; i < 2; i++) {
      const x = 40 + i * 90;
      g.beginPath();
      if (kind === 'chevronL') {
        g.moveTo(x + 60, 30);
        g.lineTo(x, 128);
        g.lineTo(x + 60, 226);
        g.lineTo(x + 100, 226);
        g.lineTo(x + 40, 128);
        g.lineTo(x + 100, 30);
      } else {
        g.moveTo(x + 40, 30);
        g.lineTo(x + 100, 128);
        g.lineTo(x + 40, 226);
        g.lineTo(x, 226);
        g.lineTo(x + 60, 128);
        g.lineTo(x, 30);
      }
      g.fill();
    }
  } else if (kind === 'hairpin') {
    g.fillStyle = '#f2c21a';
    g.save();
    g.translate(128, 128);
    g.rotate(Math.PI / 4);
    g.fillRect(-88, -88, 176, 176);
    g.strokeStyle = '#111';
    g.lineWidth = 8;
    g.strokeRect(-80, -80, 160, 160);
    g.restore();
    g.strokeStyle = '#111';
    g.lineWidth = 16;
    g.beginPath();
    g.moveTo(100, 190);
    g.lineTo(100, 110);
    g.arc(128, 110, 28, Math.PI, 0);
    g.lineTo(156, 170);
    g.stroke();
    g.fillStyle = '#111';
    g.beginPath();
    g.moveTo(140, 165);
    g.lineTo(172, 165);
    g.lineTo(156, 195);
    g.fill();
  } else if (kind === 'speed40') {
    g.fillStyle = '#fff';
    g.beginPath();
    g.arc(128, 128, 120, 0, Math.PI * 2);
    g.fill();
    g.strokeStyle = '#d0141b';
    g.lineWidth = 26;
    g.beginPath();
    g.arc(128, 128, 104, 0, Math.PI * 2);
    g.stroke();
    g.fillStyle = '#1d3f9a';
    g.font = 'bold 110px sans-serif';
    g.textAlign = 'center';
    g.textBaseline = 'middle';
    g.fillText('40', 128, 134);
  } else if (kind === 'kanban') {
    g.fillStyle = '#1d4f8f';
    g.fillRect(0, 0, 256, 256);
    g.strokeStyle = '#fff';
    g.lineWidth = 6;
    g.strokeRect(8, 8, 240, 240);
    g.fillStyle = '#fff';
    g.font = 'bold 64px sans-serif';
    g.textAlign = 'center';
    g.fillText('朧峠', 128, 100);
    g.font = 'bold 30px sans-serif';
    g.fillText('OBORO PASS', 128, 150);
    g.fillText('標高 452m', 128, 200);
  } else {
    g.fillStyle = kind === 'start' ? '#101418' : '#101418';
    g.fillRect(0, 0, 256, 256);
    const sq = 32;
    for (let y = 0; y < 2; y++)
      for (let x = 0; x < 8; x++) {
        g.fillStyle = (x + y) % 2 ? '#fff' : '#111';
        g.fillRect(x * sq, 190 + y * sq - 30, sq, sq);
      }
    g.fillStyle = '#fff';
    g.font = 'bold 84px sans-serif';
    g.textAlign = 'center';
    g.fillText(kind === 'start' ? 'START' : 'GOAL', 128, 120);
  }
  return finish(c, true, false);
}

/** Front panel of a drinks vending machine (自動販売機). */
export function makeVendingTexture(seed: number): THREE.Texture {
  const [c, g] = canvas(128, 256);
  const r = rng(seed);
  const body = ['#d8262c', '#1f5fb5', '#f2f2f2'][seed % 3];
  g.fillStyle = body;
  g.fillRect(0, 0, 128, 256);
  // lit display window with rows of bottles/cans
  g.fillStyle = '#fdfbf2';
  g.fillRect(8, 10, 112, 130);
  for (let row = 0; row < 3; row++) {
    for (let k = 0; k < 6; k++) {
      g.fillStyle = `hsl(${Math.floor(r() * 360)}, ${50 + r() * 40}%, ${35 + r() * 30}%)`;
      g.fillRect(12 + k * 18, 16 + row * 42, 12, 28);
      g.fillStyle = '#e8402a';
      g.fillRect(12 + k * 18, 46 + row * 42, 12, 4);
    }
  }
  g.fillStyle = '#222';
  g.fillRect(20, 150, 88, 26);
  g.fillStyle = '#7dffb0';
  g.font = 'bold 16px sans-serif';
  g.fillText('つめた〜い', 26, 168);
  g.fillStyle = '#111';
  g.fillRect(14, 210, 100, 30);
  return finish(c, true, false);
}
