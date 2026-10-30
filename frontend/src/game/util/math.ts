// Small deterministic math helpers shared by generation code (DOM-free).

export const clamp = (v: number, lo: number, hi: number) => (v < lo ? lo : v > hi ? hi : v);
export const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
export const smoothstep = (e0: number, e1: number, x: number) => {
  const t = clamp((x - e0) / (e1 - e0), 0, 1);
  return t * t * (3 - 2 * t);
};
export const damp = (current: number, target: number, lambda: number, dt: number) =>
  lerp(current, target, 1 - Math.exp(-lambda * dt));
export const wrapAngle = (a: number) => {
  while (a > Math.PI) a -= Math.PI * 2;
  while (a < -Math.PI) a += Math.PI * 2;
  return a;
};

/** Mulberry32 seeded PRNG. */
export function rng(seed: number) {
  let s = seed >>> 0;
  return () => {
    s = (s + 0x6d2b79f5) >>> 0;
    let t = s;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// 2D gradient noise (Perlin-style) with a fixed permutation table.
const perm = new Uint8Array(512);
{
  const r = rng(1337);
  const p = Array.from({ length: 256 }, (_, i) => i);
  for (let i = 255; i > 0; i--) {
    const j = Math.floor(r() * (i + 1));
    [p[i], p[j]] = [p[j], p[i]];
  }
  for (let i = 0; i < 512; i++) perm[i] = p[i & 255];
}
const grad2 = (h: number, x: number, y: number) => {
  switch (h & 7) {
    case 0: return x + y;
    case 1: return -x + y;
    case 2: return x - y;
    case 3: return -x - y;
    case 4: return x;
    case 5: return -x;
    case 6: return y;
    default: return -y;
  }
};
const fade = (t: number) => t * t * t * (t * (t * 6 - 15) + 10);

/** Perlin noise in roughly [-1, 1]. */
export function noise2(x: number, y: number): number {
  const xi = Math.floor(x), yi = Math.floor(y);
  const xf = x - xi, yf = y - yi;
  const X = xi & 255, Y = yi & 255;
  const u = fade(xf), v = fade(yf);
  const aa = perm[perm[X] + Y], ab = perm[perm[X] + Y + 1];
  const ba = perm[perm[X + 1] + Y], bb = perm[perm[X + 1] + Y + 1];
  const x1 = lerp(grad2(aa, xf, yf), grad2(ba, xf - 1, yf), u);
  const x2 = lerp(grad2(ab, xf, yf - 1), grad2(bb, xf - 1, yf - 1), u);
  return lerp(x1, x2, v) * 0.85;
}

export function fbm(x: number, y: number, octaves = 5, lacunarity = 2, gain = 0.5): number {
  let a = 1, f = 1, sum = 0, norm = 0;
  for (let i = 0; i < octaves; i++) {
    sum += a * noise2(x * f, y * f);
    norm += a;
    a *= gain;
    f *= lacunarity;
  }
  return sum / norm;
}

/** Ridged multifractal: sharp crests, useful for mountain ridgelines. */
export function ridged(x: number, y: number, octaves = 5): number {
  let a = 0.5, f = 1, sum = 0, w = 1;
  for (let i = 0; i < octaves; i++) {
    let n = 1 - Math.abs(noise2(x * f, y * f));
    n *= n;
    n *= w;
    w = clamp(n * 2, 0, 1);
    sum += n * a;
    a *= 0.5;
    f *= 2.03;
  }
  return sum;
}
