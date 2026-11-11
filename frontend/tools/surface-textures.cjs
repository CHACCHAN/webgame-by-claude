// The ground's, the road's and the roadside's tiling textures (public/textures/terrain/<size>/…): photo sets from
// ambientCG (CC0, docs/ASSETS.md) repacked for the terrain material, and our own tiles computed here from numbers
// (the block wall, the sprayed concrete's lumps, the road's cracks, the fence's wire mesh, the macro noise).
//   node tools/surface-textures.cjs [photo|own|all]
// ACG=<dir> holds the unpacked ambientCG 1K-JPG sets, one folder per asset id (default ~/.local/opt/wt/terrain/acg;
// download: https://ambientcg.com/get?file=<id>_1K-JPG.zip). Deterministic: the same inputs give the same files.
// Per layer: <name>_c.webp = colour (sRGB) with the height in alpha (the material blends layers by it),
// <name>_n.webp = tangent-space normal (OpenGL: green up). Sizes 1024 (high, ultra) and 512 (medium).
const fs = require('fs');
const os = require('os');
const path = require('path');
const sharp = require('sharp');

const ACG = process.env.ACG || path.join(os.homedir(), '.local/opt/wt/terrain/acg');
const OUT = path.join(__dirname, '..', 'public', 'textures', 'terrain');
const SIZES = [1024, 512];
/** the height in a colour texture's alpha runs from this value to 255 (the material maps it back: HEIGHT_FLOOR in render/surfaceTextures.ts) */
const HEIGHT_FLOOR = 96;

/** ambientCG set → layer; `gain` scales the colour (the material tints per layer on top) */
const PHOTO = {
  rock: { id: 'Rock030', gain: 1.0 },
  floor: { id: 'Ground023', gain: 1.0 },
  moss: { id: 'Ground037', gain: 1.0 },
  grass: { id: 'Grass004', gain: 1.0 },
  gravel: { id: 'Gravel040', gain: 1.0 },
  shotcrete: { id: 'Concrete035', gain: 1.0 },
  concrete: { id: 'Concrete034', gain: 1.0 },
};

async function grey(file, size) {
  const { data } = await sharp(file).resize(size, size, { kernel: 'lanczos3' }).greyscale().raw().toBuffer({ resolveWithObject: true });
  return data;
}

/** stretch a grey channel between its 1st and 99th percentile */
function stretch(g) {
  const hist = new Uint32Array(256);
  for (const v of g) hist[v]++;
  let lo = 0, hi = 255, acc = 0;
  for (let k = 0; k < 256; k++) {
    acc += hist[k];
    if (acc < g.length * 0.01) lo = k;
    if (acc < g.length * 0.99) hi = k;
  }
  const out = Buffer.alloc(g.length);
  for (let k = 0; k < g.length; k++) out[k] = Math.max(0, Math.min(255, Math.round(((g[k] - lo) / Math.max(1, hi - lo)) * 255)));
  return out;
}

async function writeColour(name, size, rgb, height) {
  const n = size * size;
  const rgba = Buffer.alloc(n * 4);
  for (let k = 0; k < n; k++) {
    rgba[k * 4] = rgb[k * 3];
    rgba[k * 4 + 1] = rgb[k * 3 + 1];
    rgba[k * 4 + 2] = rgb[k * 3 + 2];
    // (never near 0: an encoder may drop the colour under a clear pixel, and a decoder that premultiplies loses its bits)
    rgba[k * 4 + 3] = height ? HEIGHT_FLOOR + Math.round((height[k] * (255 - HEIGHT_FLOOR)) / 255) : 255;
  }
  const dir = path.join(OUT, String(size));
  fs.mkdirSync(dir, { recursive: true });
  const file = path.join(dir, `${name}_c.webp`);
  await sharp(rgba, { raw: { width: size, height: size, channels: 4 } }).webp({ quality: 84, alphaQuality: 78, effort: 6, smartSubsample: true }).toFile(file);
  return fs.statSync(file).size;
}

async function writeNormal(name, size, rgb) {
  const dir = path.join(OUT, String(size));
  fs.mkdirSync(dir, { recursive: true });
  const file = path.join(dir, `${name}_n.webp`);
  // (sharp YUV: plain 4:2:0 subsampling smears a normal map's red against its green)
  await sharp(rgb, { raw: { width: size, height: size, channels: 3 } }).webp({ quality: 88, effort: 6, smartSubsample: true }).toFile(file);
  return fs.statSync(file).size;
}

async function photo() {
  for (const [name, def] of Object.entries(PHOTO)) {
    const base = path.join(ACG, def.id, `${def.id}_1K-JPG_`);
    for (const size of SIZES) {
      const { data: rgb } = await sharp(`${base}Color.jpg`).resize(size, size, { kernel: 'lanczos3' }).removeAlpha().raw().toBuffer({ resolveWithObject: true });
      if (def.gain !== 1) for (let k = 0; k < rgb.length; k++) rgb[k] = Math.min(255, rgb[k] * def.gain);
      const height = stretch(await grey(`${base}Displacement.jpg`, size));
      const { data: nrm } = await sharp(`${base}NormalGL.jpg`).resize(size, size, { kernel: 'lanczos3' }).removeAlpha().raw().toBuffer({ resolveWithObject: true });
      const a = await writeColour(name, size, rgb, height);
      const b = await writeNormal(name, size, nrm);
      // the mean colour (linear) and roughness, for the material's constants
      if (size === 1024) {
        const lin = [0, 0, 0];
        for (let k = 0; k < rgb.length; k += 3) for (let c = 0; c < 3; c++) lin[c] += Math.pow(rgb[k + c] / 255, 2.2);
        const r = await grey(`${base}Roughness.jpg`, 64);
        const rough = r.reduce((s, v) => s + v, 0) / r.length / 255;
        console.log(`${name} (${def.id}): ${((a + b) / 1024) | 0} KiB, mean linear colour ${lin.map((v) => (v / (rgb.length / 3)).toFixed(3)).join(' ')}, roughness ${rough.toFixed(2)}`);
      }
    }
  }
}

// ------------------------------------------------------------------------------------------------ our own tiles

/** 0..1 hash of an integer lattice point (wrapped to `period`) */
function hash(ix, iy, period, seed) {
  ix = ((ix % period) + period) % period;
  iy = ((iy % period) + period) % period;
  let h = (ix * 374761393 + iy * 668265263 + seed * 2147483647) | 0;
  h = Math.imul(h ^ (h >>> 13), 1274126177);
  h ^= h >>> 16;
  return (h >>> 0) / 4294967295;
}

/** tileable value noise, 0..1: `period` lattice cells across the tile; (u, v) in 0..1 */
function vnoise(u, v, period, seed) {
  const x = u * period, y = v * period;
  const ix = Math.floor(x), iy = Math.floor(y);
  let fx = x - ix, fy = y - iy;
  fx = fx * fx * (3 - 2 * fx);
  fy = fy * fy * (3 - 2 * fy);
  const a = hash(ix, iy, period, seed), b = hash(ix + 1, iy, period, seed);
  const c = hash(ix, iy + 1, period, seed), d = hash(ix + 1, iy + 1, period, seed);
  return (a + (b - a) * fx) * (1 - fy) + (c + (d - c) * fx) * fy;
}

function fbm(u, v, period, octaves, seed) {
  let s = 0, a = 0.5, n = 0;
  for (let o = 0; o < octaves; o++) {
    s += vnoise(u, v, period << o, seed + o * 17) * a;
    n += a;
    a *= 0.5;
  }
  return s / n;
}

/** tileable cellular noise: distances to the nearest and second nearest feature point, and the nearest cell's hash */
function worley(u, v, period, seed) {
  const x = u * period, y = v * period;
  const ix = Math.floor(x), iy = Math.floor(y);
  let f1 = 9, f2 = 9, id = 0;
  for (let oy = -1; oy <= 1; oy++)
    for (let ox = -1; ox <= 1; ox++) {
      const cx = ix + ox, cy = iy + oy;
      const px = cx + 0.15 + 0.7 * hash(cx, cy, period, seed), py = cy + 0.15 + 0.7 * hash(cx, cy, period, seed + 7);
      const d = Math.hypot(px - x, py - y);
      if (d < f1) {
        f2 = f1;
        f1 = d;
        id = hash(cx, cy, period, seed + 13);
      } else if (d < f2) f2 = d;
    }
  return { f1, f2, id };
}

/** normal map (RGB bytes) of a tileable height field in metres; `texel` = metres per pixel */
function normalsOf(h, size, texel, strength = 1) {
  const out = Buffer.alloc(size * size * 3);
  const at = (x, y) => h[((y + size) % size) * size + ((x + size) % size)];
  for (let y = 0; y < size; y++)
    for (let x = 0; x < size; x++) {
      // OpenGL convention: red along +u (image x), green along +v (image up)
      const nx = (-(at(x + 1, y) - at(x - 1, y)) / (2 * texel)) * strength;
      const ny = ((at(x, y + 1) - at(x, y - 1)) / (2 * texel)) * strength;
      const l = Math.hypot(nx, ny, 1);
      const o = (y * size + x) * 3;
      out[o] = Math.round((nx / l) * 127.5 + 127.5);
      out[o + 1] = Math.round((ny / l) * 127.5 + 127.5);
      out[o + 2] = Math.round((1 / l) * 127.5 + 127.5);
    }
  return out;
}

const smooth = (a, b, x) => {
  const t = Math.max(0, Math.min(1, (x - a) / (b - a)));
  return t * t * (3 - 2 * t);
};
const bytes = (f, size) => {
  const out = Buffer.alloc(size * size);
  let lo = Infinity, hi = -Infinity;
  for (const v of f) {
    lo = Math.min(lo, v);
    hi = Math.max(hi, v);
  }
  for (let k = 0; k < f.length; k++) out[k] = Math.round(((f[k] - lo) / (hi - lo || 1)) * 255);
  return out;
};

/**
 * 間知ブロックの谷積み: split-faced concrete blocks laid on the diagonal, four diamonds across a 2 m tile, mortar joints
 * set back 25 mm, a drain pipe (水抜き) in the middle of the tile with the streak it leaves.
 */
async function blockWall(size) {
  const T = 2.0, n = 4;
  const h = new Float32Array(size * size), rgb = Buffer.alloc(size * size * 3);
  for (let y = 0; y < size; y++)
    for (let x = 0; x < size; x++) {
      const u = (x + 0.5) / size, v = (y + 0.5) / size;
      const a = (u + v) * n, b = (u - v) * n;
      const ca = Math.floor(a), cb = Math.floor(b);
      const fa = a - ca, fb = b - cb;
      // distance to the block's edge (in block units) with slightly irregular joints
      const wob = (fbm(u, v, 16, 2, 5) - 0.5) * 0.05;
      const e = Math.min(fa, 1 - fa, fb, 1 - fb) + wob;
      const id = hash(ca, cb, n, 3), id2 = hash(ca, cb, n, 9);
      const face = smooth(0.035, 0.11, e);
      // the split face: a pillow with coarse breaks, each block its own
      const rough = fbm(u + id, v + id2, 24, 4, 21) - 0.5;
      const pillow = Math.pow(Math.max(0, Math.min(1, e / 0.5)), 0.45);
      let height = -0.025 * (1 - face) + face * (0.012 * pillow + rough * 0.022 + (id - 0.5) * 0.008);
      // the weep hole at the tile's centre, in a joint crossing
      const du = (u - 0.5) * T, dv = (v - 0.5) * T;
      const hole = Math.hypot(du, dv);
      const pipe = smooth(0.05, 0.04, hole);
      const lip = smooth(0.062, 0.05, hole) * (1 - pipe);
      height = height * (1 - Math.max(pipe, lip)) + lip * 0.016 - pipe * 0.06;
      h[y * size + x] = height;
      // colour: weathered grey concrete, each block a little different, dark damp joints
      const grain = fbm(u, v, 96, 3, 40) - 0.5;
      const blot = fbm(u, v, 6, 3, 60);
      let c = 132 + (id - 0.5) * 34 + grain * 30 + rough * 36 - (1 - face) * 62;
      let r = c * 1.0, g = c * 0.985, bl = c * 0.94;
      // lichen and dirt in blotches
      const dirt = smooth(0.52, 0.72, blot);
      r = r * (1 - dirt * 0.28);
      g = g * (1 - dirt * 0.2);
      bl = bl * (1 - dirt * 0.34);
      // the streak under the pipe (image y grows downwards = down the wall)
      const streak = smooth(0.11, 0.0, Math.abs(du) + fbm(u, v, 32, 2, 77) * 0.05) * smooth(-0.02, 0.05, dv) * smooth(0.95, 0.1, dv);
      const dark = 1 - 0.5 * streak - 0.8 * pipe;
      r *= dark * (1 - 0.0 * streak);
      g *= dark * (1 + 0.04 * streak);
      bl *= dark * (1 - 0.1 * streak);
      const o = (y * size + x) * 3;
      rgb[o] = Math.max(0, Math.min(255, r));
      rgb[o + 1] = Math.max(0, Math.min(255, g));
      rgb[o + 2] = Math.max(0, Math.min(255, bl));
    }
  return [await writeColour('blockwall', size, rgb, bytes(h, size)), await writeNormal('blockwall', size, normalsOf(h, size, T / size, 1.3))];
}

/** sprayed mortar (モルタル吹付): lumps of several sizes over a 3 m tile; the colour comes from the photo set */
async function shotcreteLumps(size) {
  const T = 3.0;
  const h = new Float32Array(size * size);
  for (let y = 0; y < size; y++)
    for (let x = 0; x < size; x++) {
      const u = (x + 0.5) / size, v = (y + 0.5) / size;
      const w = worley(u, v, 9, 4);
      const blobs = Math.sqrt(Math.max(0, 1 - w.f1 * w.f1 * 1.6));
      h[y * size + x] = blobs * 0.01 + fbm(u, v, 5, 3, 8) * 0.07 + fbm(u, v, 22, 3, 15) * 0.034 + fbm(u, v, 90, 3, 23) * 0.009;
    }
  return [await writeNormal('shotcrete', size, normalsOf(h, size, T / size, 1.0)), bytes(h, size)];
}

/**
 * The road's marks, one tile of 8 m: R = cracks (thin lines of a cellular pattern, broken up), G = the cells' ids
 * (patches of resurfacing take them), B = fine grit.
 */
async function roadMarks(size) {
  const rgb = Buffer.alloc(size * size * 3);
  for (let y = 0; y < size; y++)
    for (let x = 0; x < size; x++) {
      const u = (x + 0.5) / size, v = (y + 0.5) / size;
      // warp so the cracks wander
      const wu = u + (fbm(u, v, 12, 3, 31) - 0.5) * 0.06, wv = v + (fbm(u, v, 12, 3, 37) - 0.5) * 0.06;
      const w = worley(wu, wv, 5, 11);
      const edge = w.f2 - w.f1;
      const w2 = worley(wu, wv, 13, 19);
      const fine = w2.f2 - w2.f1;
      // main cracks 6–9 mm wide, hairlines off them
      const main = smooth(0.016, 0.004, edge);
      const hair = smooth(0.02, 0.004, fine) * smooth(0.3, 0.05, edge) * 0.7;
      const o = (y * size + x) * 3;
      rgb[o] = Math.round(Math.max(main, hair) * 255);
      rgb[o + 1] = Math.round(w.id * 255);
      rgb[o + 2] = Math.round(fbm(u, v, 128, 3, 51) * 255);
    }
  const dir = path.join(OUT, String(size));
  const file = path.join(dir, 'roadmarks.webp');
  await sharp(rgb, { raw: { width: size, height: size, channels: 3 } }).webp({ quality: 90, effort: 6, smartSubsample: true }).toFile(file);
  return fs.statSync(file).size;
}

/** chain-link / rockfall net: diamonds of 5 cm wire mesh over a 0.5 m tile, alpha = wire */
async function wireMesh() {
  const size = 256, n = 8;
  const rgba = Buffer.alloc(size * size * 4);
  for (let y = 0; y < size; y++)
    for (let x = 0; x < size; x++) {
      const u = (x + 0.5) / size, v = (y + 0.5) / size;
      const a = (u + v) * n, b = (u - v) * n;
      const e = Math.min(Math.abs(a - Math.round(a)), Math.abs(b - Math.round(b)));
      const wire = smooth(0.085, 0.045, e);
      const o = (y * size + x) * 4;
      const c = 150 + (hash(x, y, size, 5) - 0.5) * 30;
      rgba[o] = c * 0.95;
      rgba[o + 1] = c;
      rgba[o + 2] = c * 0.97;
      rgba[o + 3] = Math.round(wire * 255);
    }
  const file = path.join(OUT, 'wiremesh.webp');
  await sharp(rgba, { raw: { width: size, height: size, channels: 4 } }).webp({ quality: 90, alphaQuality: 95 }).toFile(file);
  return fs.statSync(file).size;
}

/** macro noise, 256 px: four independent tileable fractal noises (the materials' large-scale variation) */
async function macroNoise() {
  const size = 256;
  const rgba = Buffer.alloc(size * size * 4);
  for (let y = 0; y < size; y++)
    for (let x = 0; x < size; x++) {
      const u = (x + 0.5) / size, v = (y + 0.5) / size;
      const o = (y * size + x) * 4;
      for (let c = 0; c < 4; c++) rgba[o + c] = Math.round(Math.max(0, Math.min(1, (fbm(u, v, 4, 6, 100 + c * 31) - 0.5) * 1.9 + 0.5)) * 255);
    }
  const file = path.join(OUT, 'macro.webp');
  await sharp(rgba, { raw: { width: size, height: size, channels: 4 } }).webp({ lossless: true }).toFile(file);
  return fs.statSync(file).size;
}

async function own() {
  for (const size of SIZES) {
    fs.mkdirSync(path.join(OUT, String(size)), { recursive: true });
    const wall = await blockWall(size);
    const [lumps] = await shotcreteLumps(size);
    const marks = await roadMarks(size);
    console.log(`${size}: blockwall ${((wall[0] + wall[1]) / 1024) | 0} KiB, shotcrete normal ${(lumps / 1024) | 0} KiB, roadmarks ${(marks / 1024) | 0} KiB`);
  }
  console.log(`wiremesh ${((await wireMesh()) / 1024) | 0} KiB, macro ${((await macroNoise()) / 1024) | 0} KiB`);
}

(async () => {
  const what = process.argv[2] || 'all';
  if (what === 'photo' || what === 'all') await photo();
  // (after the photos: the sprayed concrete's normal map is ours and replaces the photo set's)
  if (what === 'own' || what === 'all') await own();
  let total = 0;
  for (const size of SIZES) {
    let sum = 0;
    for (const f of fs.readdirSync(path.join(OUT, String(size)))) sum += fs.statSync(path.join(OUT, String(size), f)).size;
    console.log(`${size}: ${(sum / 1048576).toFixed(2)} MiB`);
    total += sum;
  }
  console.log(`total ${(total / 1048576).toFixed(2)} MiB`);
})();
