// What the grains can depict (cloud.ts): each function gives points in the shape's own space, in an order in which
// any first part is an even sample of the whole (a slow machine shows the same shape with fewer grains). No DOM.
import type { Shape } from './cloud';

type Rand = () => number;
/** a number from the bell curve (mean 0, deviation 1) */
const bell = (rand: Rand) => Math.sqrt(-2 * Math.log(Math.max(1e-6, rand()))) * Math.cos(6.2832 * rand());

/** tones: indices into the cloud's palette (Cloud.tsx fills it from the interface's colours) */
export const TONE = { dust: 0, cyan: 1, magenta: 2, amber: 3, white: 4, green: 5, deep: 6, silver: 7, bronze: 8 } as const;

/** What a course's relief is made from: its centre line and the height of the land (Track, Landform). */
export interface CourseSource {
  count: number;
  /** x, y, z per metre of the centre line */
  pos: Float32Array;
  startS: number;
  finishS: number;
  base: (x: number, z: number) => number;
  /** the surface of the sea or the lake, when there is one */
  water: number | null;
}

/**
 * A course as a relief of grains: the road a bright line, the land around it in contour lines that fade with the
 * distance from the road, water a dim plane, a beam of light over the start and one over the finish.
 * Own space: x east, y up the screen's way (negative = high), z north (far); the course's larger side is 1 long.
 */
/** how far a relief is tipped towards the eye (0: seen from the side, π/2: from above) */
export const RELIEF_PITCH = 0.8;
/** how far it turns to either side while it is shown (it sways and follows the pointer) */
export const RELIEF_SWAY = 0.32;

export function courseRelief(src: CourseSource, n: number, rand: Rand): Shape {
  let minX = Infinity, maxX = -Infinity, minZ = Infinity, maxZ = -Infinity, minY = Infinity, maxY = -Infinity;
  const a = Math.round(src.startS), b = Math.min(src.count - 1, Math.round(src.finishS));
  for (let k = 0; k < src.count; k += 3) {
    minX = Math.min(minX, src.pos[k * 3]);
    maxX = Math.max(maxX, src.pos[k * 3]);
    minY = Math.min(minY, src.pos[k * 3 + 1]);
    maxY = Math.max(maxY, src.pos[k * 3 + 1]);
    minZ = Math.min(minZ, src.pos[k * 3 + 2]);
    maxZ = Math.max(maxZ, src.pos[k * 3 + 2]);
  }
  const extent = Math.max(maxX - minX, maxZ - minZ, 1);
  const mx = (minX + maxX) / 2, mz = (minZ + maxZ) / 2, my = (minY + maxY) / 2;
  // heights drawn larger than they are: a pass is a few hundred metres high over several kilometres
  const up = Math.min(2.4, Math.max(1.2, 0.2 / ((maxY - minY) / extent || 1)));
  const points = new Float32Array(n * 3), lum = new Float32Array(n), tones = new Uint8Array(n), along = new Float32Array(n);
  const course = new Uint8Array(n);
  const put = (i: number, x: number, y: number, z: number, l: number, tone: number, u: number) => {
    points[i * 3] = (x - mx) / extent;
    points[i * 3 + 1] = (-(y - my) / extent) * up;
    points[i * 3 + 2] = -(z - mz) / extent;
    lum[i] = l;
    tones[i] = tone;
    along[i] = u;
  };
  const reach = extent * 0.15, contour = Math.max(14, Math.round((maxY - minY) / 6));
  const hx = (maxX - minX) / 2 + extent * 0.12, hz = (maxZ - minZ) / 2 + extent * 0.12;
  /** how far a height is from the nearest contour line, metres */
  const off = (y: number) => {
    const c = Math.abs(((y / contour) % 1) + 1) % 1;
    return Math.min(c, 1 - c) * contour;
  };
  for (let i = 0; i < n; i++) {
    const role = rand();
    const k = Math.min(src.count - 1, Math.floor(rand() * src.count));
    const rx = src.pos[k * 3], ry = src.pos[k * 3 + 1], rz = src.pos[k * 3 + 2];
    const u = (k - a) / Math.max(1, b - a);
    if (role < 0.26) {
      // the road: a line a few metres wide (the part that is raced brighter than the run-in and the run-out)
      const raced = k >= a && k <= b;
      course[i] = 1;
      put(i, rx + bell(rand) * 3, ry + 2, rz + bell(rand) * 3, raced ? 1 : 0.35, raced ? (rand() < 0.3 ? TONE.white : TONE.cyan) : TONE.dust, u);
    } else if (role < 0.3) {
      // the beams over the start and the finish
      const start = role < 0.28, s = start ? a : b, h = rand();
      course[i] = 1;
      put(i, src.pos[s * 3] + bell(rand) * extent * 0.004, src.pos[s * 3 + 1] + h * h * extent * 0.11, src.pos[s * 3 + 2] + bell(rand) * extent * 0.004, 1 - 0.75 * h, start ? TONE.green : TONE.amber, start ? 0 : 1);
    } else {
      // the land, an island around the course: most of its grains on contour lines (of a few places tried, the one
      // nearest to a line), the rest a thin dusting between them; it thins out towards its rim
      const lines = role < 0.86;
      let x = 0, y = 0, z = 0, fade = 0, line = Infinity;
      for (let tries = lines ? 5 : 1; tries > 0; tries--) {
        let tx: number, tz: number, ty: number, tf: number;
        if (rand() < 0.5) {
          // around the road
          const dx = bell(rand) * reach, dz = bell(rand) * reach, d = Math.hypot(dx, dz);
          tx = rx + dx;
          tz = rz + dz;
          ty = src.base(tx, tz);
          // (next to the road the ground is the road's: cuttings and embankments)
          const near = Math.max(0, 1 - d / 45);
          ty += (ry - ty) * near * near;
          tf = 0.5 + 0.5 * Math.exp(-(d * d) / (reach * reach * 3.2));
        } else {
          // anywhere on the island
          const ang = rand() * 6.2832, r = Math.sqrt(rand());
          tx = mx + Math.cos(ang) * r * hx;
          tz = mz + Math.sin(ang) * r * hz;
          ty = src.base(tx, tz);
          tf = 0.9 * (1 - r * r * r * r);
        }
        const water = src.water !== null && ty <= src.water;
        const tl = water ? 0 : off(ty);
        if (tl < line) {
          x = tx;
          z = tz;
          y = water ? (src.water as number) : ty;
          fade = tf;
          line = tl;
          if (water) break;
        }
      }
      const water = src.water !== null && y <= src.water;
      // (the land's brightness is its own: the light that runs along the road dims what it is not on)
      const high = (y - minY) / (maxY - minY || 1);
      if (water) put(i, x, y, z, (0.4 + 0.4 * rand()) * fade, TONE.deep, u);
      else if (lines) put(i, x, y, z, (0.45 + 1.1 * Math.exp(-(line * line) / 1.6)) * fade, high > 0.8 ? TONE.white : high < 0.2 ? TONE.deep : TONE.dust, u);
      else put(i, x, y, z, (0.25 + 0.3 * rand()) * fade, TONE.deep, u);
    }
  }
  // turned so that the course lies across the screen, its start on the left (a relief stands in a wide, low place):
  // about the vertical, by the road's longest direction
  let sxx = 0, szz = 0, sxz = 0;
  for (let k = 0; k < src.count; k += 3) {
    const x = (src.pos[k * 3] - mx) / extent, z = -(src.pos[k * 3 + 2] - mz) / extent;
    sxx += x * x;
    szz += z * z;
    sxz += x * z;
  }
  const long = 0.5 * Math.atan2(2 * sxz, sxx - szz);
  let cos = Math.cos(long), sin = Math.sin(long);
  const along0 = ((src.pos[a * 3] - mx) * cos - (src.pos[a * 3 + 2] - mz) * sin) / extent;
  const along1 = ((src.pos[b * 3] - mx) * cos - (src.pos[b * 3 + 2] - mz) * sin) / extent;
  if (along0 > along1) {
    cos = -cos;
    sin = -sin;
  }
  // and where the course itself (not the land around it) then is in the picture, at every turn it is shown with
  const cp = Math.cos(RELIEF_PITCH), sp = Math.sin(RELIEF_PITCH);
  const cw = Math.cos(RELIEF_SWAY), sw = Math.sin(RELIEF_SWAY);
  let x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity;
  for (let i = 0; i < n; i++) {
    const x = points[i * 3], z = points[i * 3 + 2];
    const tx = x * cos + z * sin, tz = -x * sin + z * cos;
    points[i * 3] = tx;
    points[i * 3 + 2] = tz;
    if (!course[i]) continue;
    const y = cp * points[i * 3 + 1];
    for (let turn = -1; turn <= 1; turn++) {
      const px = cw * tx + turn * sw * tz, py = sp * turn * sw * tx + y - sp * cw * tz;
      x0 = Math.min(x0, px);
      x1 = Math.max(x1, px);
      y0 = Math.min(y0, py);
      y1 = Math.max(y1, py);
    }
  }
  return { points, lum, tones, along, wave: 0.11, tone: TONE.cyan, loose: 0.6, size: 1.55, gain: 1, box: [(x0 + x1) / 2, (y0 + y1) / 2, x1 - x0, y1 - y0] };
}

/**
 * A picture given as a mask (a glyph drawn into a canvas: `alpha` per pixel, `w` × `h`), as grains: bright along its
 * edges, fainter inside, a little deep. Own space: the mask's height is 1, centred.
 */
export function maskShape(alpha: ArrayLike<number>, w: number, h: number, n: number, tone: number, rand: Rand, depth = 0.05): Shape {
  const points = new Float32Array(n * 3), lum = new Float32Array(n);
  const at = (x: number, y: number) => (x < 0 || y < 0 || x >= w || y >= h ? 0 : alpha[y * w + x]);
  let filled = 0;
  for (let i = 0; i < w * h; i++) if (alpha[i] > 110) filled++;
  let i = 0, tries = 0;
  const limit = filled ? n * Math.ceil((w * h) / filled) * 8 : 0;
  while (i < n && tries++ < limit) {
    const x = Math.floor(rand() * w), y = Math.floor(rand() * h);
    if (at(x, y) <= 110) continue;
    const edge = at(x - 2, y) < 60 || at(x + 2, y) < 60 || at(x, y - 2) < 60 || at(x, y + 2) < 60;
    // (the inside is thinned out: the edges carry the picture)
    if (!edge && rand() > 0.6) continue;
    points[i * 3] = (x + rand() - w / 2) / h;
    points[i * 3 + 1] = (y + rand() - h / 2) / h;
    points[i * 3 + 2] = bell(rand) * depth * (edge ? 0.5 : 1);
    lum[i] = edge ? 1 : 0.42 + 0.4 * rand();
    i++;
  }
  // (an empty mask: nothing to show; the grains gather in a point and are dark)
  for (; i < n; i++) lum[i] = 0;
  return { points, lum, tone, loose: 0.5, size: 1.15, gain: 1 };
}

/**
 * A time of day and its weather as a small scene of grains: a starry night with the moon over the lights of a town,
 * rain falling on a wet road under a lamp, the sun coming up out of a sea of clouds. Own space: the place it is
 * shown in is 1 high and `aspect` wide, centred; the sky spills over that place on all sides, thinning out.
 */
export function skyScene(kind: 'night' | 'rain' | 'dawn', aspect: number, n: number, rand: Rand): Shape {
  const a = aspect, points = new Float32Array(n * 3), lum = new Float32Array(n), tones = new Uint8Array(n), along = new Float32Array(n).fill(-1);
  const put = (i: number, x: number, y: number, z: number, l: number, tone: number) => {
    points[i * 3] = x;
    points[i * 3 + 1] = y;
    points[i * 3 + 2] = z;
    lum[i] = Math.min(1, l);
    tones[i] = tone;
  };
  /** 1 inside the place, falling to 0 a place's height above and below it and half its width beside it */
  const inside = (x: number, y: number) => Math.exp(-Math.pow(Math.abs(x) / (a * 0.6), 6) - Math.pow(Math.abs(y) / 0.9, 4));
  const ridge = (x: number) => 0.17 + 0.07 * Math.sin(x * 2.3 + 0.8) + 0.04 * Math.sin(x * 5.1 + 2) + 0.02 * Math.sin(x * 11.3);
  if (kind === 'night') {
    const mx = a * 0.27, my = -0.16, R = 0.25;
    for (let i = 0; i < n; i++) {
      const role = rand();
      if (role < 0.46) {
        // stars: most of them faint, a few bright, at every depth
        const x = (rand() - 0.5) * a * 1.7, y = (rand() - 0.5) * 2.6 - 0.25, b = Math.pow(rand(), 5);
        if (y > ridge(x)) put(i, x, y, 0, 0, TONE.dust);
        else put(i, x, y, (rand() - 0.5) * 0.9, (0.14 + 0.86 * b) * inside(x, y), b > 0.35 ? TONE.white : rand() < 0.2 ? TONE.cyan : TONE.dust);
      } else if (role < 0.6) {
        // the band of the galaxy across the sky
        const u = rand() * 2 - 1, x = u * a * 0.62, y = -u * 0.42 - 0.3 + bell(rand) * 0.13;
        put(i, x, y, 0.25 + bell(rand) * 0.15, (0.16 + 0.22 * rand()) * inside(x, y), rand() < 0.5 ? TONE.deep : TONE.dust);
      } else if (role < 0.76) {
        // the moon, a few days from full: a disc with another disc taken out of it, its lit limb the brightest
        let x = 0, y = 0, tries = 0;
        do {
          const ang = rand() * 6.2832, r = Math.sqrt(rand()) * R;
          x = Math.cos(ang) * r;
          y = Math.sin(ang) * r;
        } while (Math.hypot(x + 0.15, y + 0.06) < R * 0.93 && tries++ < 20);
        const limb = Math.hypot(x, y) / R;
        put(i, mx + x, my + y, 0, 0.5 + 0.5 * Math.pow(limb, 5), TONE.white);
      } else if (role < 0.86) {
        // the ridge the road runs along
        const x = (rand() - 0.5) * a * 1.25, off = rand() * rand() * 0.05;
        put(i, x, ridge(x) + off, -0.05, (0.75 - off * 9) * inside(x, 0.17), TONE.cyan);
      } else {
        // the town below it: warm lights, denser towards the bay
        // (in quarters: the lights gather in a few places, thinner between them and towards the water)
        const quarter = Math.floor(rand() * 5), d = rand(), b = Math.pow(rand(), 1.6);
        const x = rand() < 0.6 ? (quarter / 4 - 0.5) * a * 0.8 + Math.sin(quarter * 2.4) * 0.12 + bell(rand) * 0.16 : (rand() - 0.5) * a * 1.05;
        const y = ridge(x) + 0.06 + d * d * 0.24;
        put(i, x, y, -0.05 - d * 0.12, (0.35 + 0.65 * b) * inside(x, y), b > 0.6 ? TONE.white : TONE.amber);
      }
    }
    return { points, lum, tones, tone: TONE.white, loose: 0.5, size: 1.25, gain: 1 };
  }
  if (kind === 'rain') {
    // (streaks are six grains in a row that fall together; the others stay where they are)
    const lean = -0.24, lampX = -a * 0.27, road = 0.22;
    let i = 0;
    while (i < n) {
      const role = rand();
      // (a streak takes six grains for one draw: a third of the draws are three quarters of the grains)
      if (role < 0.34 && i + 6 <= n) {
        const x = (rand() - 0.5) * a * 1.6, z = (rand() - 0.5) * 1.1, phase = rand(), len = 0.1 + 0.16 * rand(), b = 0.45 + 0.55 * rand();
        // (in the lamp's cone the rain is lit warm)
        const lit = Math.exp(-Math.pow((x - lampX) / 0.42, 2));
        for (let j = 0; j < 6; j++, i++) {
          put(i, x - lean * len * (j / 5), -len * (j / 5), z, b * (1 - j * 0.15) * (0.7 + 0.3 * lit) * inside(x, 0), lit > 0.5 && rand() < lit ? TONE.amber : j < 2 ? TONE.white : TONE.dust);
          along[i] = phase;
        }
      } else if (role < 0.48) {
        // the lamp: a head of light and its cone thinning out downwards
        const h = rand(), w = 0.03 + h * 0.55;
        put(i, lampX + bell(rand) * w * 0.4, -0.42 + h * (road + 0.42), bell(rand) * 0.05, (1 - h) * (1 - h) * 0.9 + 0.08, h < 0.06 ? TONE.white : TONE.amber);
        i++;
      } else if (role < 0.82) {
        // the wet road: rings where drops fall, seen flat
        const cx = (Math.floor(rand() * 6) - 2.5) * a * 0.19 + 0.05, cy = road + 0.07 + (Math.floor(rand() * 2)) * 0.07, r = 0.07 + Math.floor(rand() * 3) * 0.07, ang = rand() * 6.2832;
        const x = cx + Math.cos(ang) * r, y = cy + Math.sin(ang) * r * 0.26;
        put(i, x, y, bell(rand) * 0.02, (0.8 - r * 2.4) * inside(x, y), TONE.cyan);
        i++;
      } else {
        // and the lamp once more, drawn out in the water
        const h = rand();
        put(i, lampX + bell(rand) * (0.02 + h * 0.03), road + 0.02 + h * 0.3, 0, (1 - h) * 0.75, h < 0.3 ? TONE.white : TONE.amber);
        i++;
      }
    }
    return { points, lum, tones, along, fall: { x: lean * 2.3, y: 2.3, z: 0, rate: 0.85 }, tone: TONE.dust, loose: 0.2, size: 1.6, gain: 1 };
  }
  // dawn
  const sy = 0.1, R = 0.33, clouds = 0.06;
  for (let i = 0; i < n; i++) {
    const role = rand();
    if (role < 0.22) {
      // the sun, as much of it as is over the clouds
      let x = 0, y = 0, tries = 0;
      do {
        const ang = rand() * 6.2832, r = Math.pow(rand(), 0.4) * R;
        x = Math.cos(ang) * r;
        y = sy + Math.sin(ang) * r;
      } while (y > clouds && tries++ < 20);
      const limb = Math.hypot(x, y - sy) / R;
      put(i, x, y, 0.3, 0.8 + 0.2 * Math.pow(limb, 4), rand() > limb * 0.9 ? TONE.white : TONE.amber);
    } else if (role < 0.36) {
      // its glow in the haze
      const ang = -rand() * Math.PI, r = R + Math.abs(bell(rand)) * 0.3;
      const x = Math.cos(ang) * r * 1.25, y = sy + Math.sin(ang) * r;
      put(i, x, y, 0.3 + bell(rand) * 0.1, 0.4 * Math.exp(-(r - R) / 0.22), TONE.amber);
    } else if (role < 0.48) {
      // rays between the clouds
      const ray = Math.floor(rand() * 11), ang = -Math.PI * (0.06 + (ray / 10) * 0.88) + bell(rand) * 0.012, r = R * 1.15 + rand() * 0.95;
      const x = Math.cos(ang) * r * 1.2, y = sy + Math.sin(ang) * r;
      put(i, x, y, 0.2, 0.42 * Math.pow(1 - (r - R) / 1.1, 2) * inside(x, y), TONE.amber);
    } else if (role < 0.86) {
      // the sea of clouds: rows of swell, the near ones lower and nearer, lit where they face the sun
      const d = Math.pow(rand(), 1.4), row = Math.floor(d * 9), x = (rand() - 0.5) * a * 1.5;
      const swell = Math.sin(x * (2.2 + row * 0.35) + row * 1.7) * 0.5 + Math.sin(x * 6.1 + row) * 0.25;
      const y = clouds + 0.015 + row * 0.04 + rand() * 0.03 - swell * 0.02, sun = Math.exp(-Math.pow(x / (0.25 + d * 0.5), 2));
      put(i, x, y, 0.25 - d * 0.75, (0.3 + 0.5 * sun + 0.25 * (swell > 0.3 ? 1 : 0)) * inside(x, y), sun > 0.55 ? (rand() < 0.4 ? TONE.white : TONE.amber) : swell > 0.3 ? TONE.white : TONE.dust);
    } else {
      // two peaks that stand out of the clouds, their sunward side lit
      const left = rand() < 0.55, px = left ? -a * 0.3 : a * 0.34, top = left ? -0.26 : -0.14, wide = left ? 0.5 : 0.36;
      const h = rand(), side = rand() < 0.5 ? -1 : 1, x = px + side * h * wide * (0.9 + 0.2 * Math.sin(h * 14 + (left ? 0 : 2)));
      const y = top + h * (clouds - top) + rand() * rand() * 0.03, sunward = left ? side > 0 : side < 0;
      put(i, x, y, 0.1, (sunward ? 0.75 : 0.35) * (1 - h * 0.5), sunward ? TONE.amber : TONE.dust);
    }
  }
  return { points, lum, tones, tone: TONE.amber, loose: 0.45, size: 1.25, gain: 1 };
}

/**
 * A medal of grains: a disc with a fluted rim, a wreath and an emblem in its middle (the mask's picture: the medal's
 * character; a star without one), hanging on a ribbon. Own space: its place is 1 high, centred; the disc faces the
 * eye and has an edge, so that it can be turned a little. A gleam runs round it (`along` is the angle about the
 * disc's centre, 0 at the top).
 */
export function medalShape(kind: 'gold' | 'silver' | 'bronze', n: number, rand: Rand, emblem?: { alpha: ArrayLike<number>; w: number; h: number }): Shape {
  const points = new Float32Array(n * 3), lum = new Float32Array(n), tones = new Uint8Array(n), along = new Float32Array(n);
  const metal = kind === 'gold' ? TONE.amber : kind === 'silver' ? TONE.silver : TONE.bronze;
  const shine = kind === 'bronze' ? TONE.amber : TONE.white;
  const cy = 0.17, R = 0.3, T = 0.02;
  const put = (i: number, x: number, y: number, z: number, l: number, tone: number) => {
    points[i * 3] = x;
    points[i * 3 + 1] = y;
    points[i * 3 + 2] = z;
    lum[i] = Math.min(1, l);
    tones[i] = tone;
    along[i] = (Math.atan2(y - cy, x) / 6.2832 + 1.25) % 1;
  };
  // the emblem's filled pixels, once
  const filled: number[] = [];
  if (emblem) for (let k = 0; k < emblem.w * emblem.h; k++) if (emblem.alpha[k] > 110) filled.push(k);
  const at = (x: number, y: number) => (!emblem || x < 0 || y < 0 || x >= emblem.w || y >= emblem.h ? 0 : emblem.alpha[y * emblem.w + x]);
  for (let i = 0; i < n; i++) {
    const role = rand();
    if (role < 0.13) {
      // the rim: a bright line round the face
      const ang = rand() * 6.2832, r = R * (1 - Math.abs(bell(rand)) * 0.012);
      put(i, Math.cos(ang) * r, cy + Math.sin(ang) * r, -T, 0.85 + 0.15 * rand(), rand() < 0.35 ? shine : metal);
    } else if (role < 0.19) {
      // its edge: what shows of the disc's thickness when it turns
      const ang = rand() * 6.2832;
      put(i, Math.cos(ang) * R, cy + Math.sin(ang) * R, -T + rand() * T * 3, 0.42, metal);
    } else if (role < 0.25) {
      // a second line inside the rim
      const ang = rand() * 6.2832, r = R * (0.8 + bell(rand) * 0.006);
      put(i, Math.cos(ang) * r, cy + Math.sin(ang) * r, -T, 0.7, metal);
    } else if (role < 0.34) {
      // the fluting between the two
      const ang = (Math.floor(rand() * 64) / 64) * 6.2832, r = R * (0.835 + rand() * 0.13);
      put(i, Math.cos(ang) * r, cy + Math.sin(ang) * r, -T, 0.5, metal);
    } else if (role < 0.56) {
      // the wreath: two branches from the bottom up the sides, a pair of leaves at each of nine places
      const side = rand() < 0.5 ? -1 : 1, node = Math.floor(rand() * 9), rb = R * 0.655;
      if (rand() < 0.2) {
        const th = Math.PI / 2 + side * (0.16 + rand() * 2.5);
        put(i, Math.cos(th) * rb, cy + Math.sin(th) * rb, -T, 0.55, metal);
      } else {
        const th = Math.PI / 2 + side * (0.22 + (node / 8.6) * 2.4);
        const nx = Math.cos(th), ny = Math.sin(th), tx = -side * ny, ty = side * nx;
        // (a leaf leans out of the branch, to its outside or its inside)
        const lean = (rand() < 0.5 ? 0.62 : -0.62), dx = tx * Math.cos(lean) + nx * Math.sin(lean), dy = ty * Math.cos(lean) + ny * Math.sin(lean);
        const u = rand(), half = Math.sin(u * Math.PI) * R * 0.042, edge = rand() < 0.7, across = edge ? (rand() < 0.5 ? -1 : 1) : (rand() * 2 - 1) * 0.6;
        const len = R * 0.17;
        put(i, nx * rb + dx * u * len - dy * half * across, cy + ny * rb + dy * u * len + dx * half * across, -T - 0.004, edge ? 0.85 : 0.5, edge && rand() < 0.3 ? shine : metal);
      }
    } else if (role < 0.8) {
      if (emblem && filled.length) {
        // the medal's character, its edges the brightest
        let k = 0, x = 0, y = 0, edge = false, tries = 0;
        do {
          k = filled[Math.floor(rand() * filled.length)];
          x = k % emblem.w;
          y = Math.floor(k / emblem.w);
          edge = at(x - 2, y) < 60 || at(x + 2, y) < 60 || at(x, y - 2) < 60 || at(x, y + 2) < 60;
        } while (!edge && rand() > 0.25 && tries++ < 8);
        // (its strokes' edges carry it: filled in, a character of many strokes is a blot at this size)
        const scale = (R * 1.17) / emblem.h;
        put(i, (x + rand() - emblem.w / 2) * scale, cy + (y + rand() - emblem.h / 2) * scale, -T - 0.012 + bell(rand) * 0.004, edge ? 1 : 0.2 + 0.12 * rand(), edge ? shine : metal);
      } else {
        // a star of five points: its outline, and a thinner filling
        const point = Math.floor(rand() * 10), a0 = (point / 10) * 6.2832 - Math.PI / 2, a1 = ((point + 1) / 10) * 6.2832 - Math.PI / 2;
        const r0 = R * (point % 2 ? 0.17 : 0.4), r1 = R * (point % 2 ? 0.4 : 0.17), u = rand(), inward = rand() < 0.7 ? 1 : Math.sqrt(rand());
        const x = (Math.cos(a0) * r0 * (1 - u) + Math.cos(a1) * r1 * u) * inward, y = (Math.sin(a0) * r0 * (1 - u) + Math.sin(a1) * r1 * u) * inward;
        put(i, x, cy + y, -T - 0.012, inward === 1 ? 1 : 0.5, inward === 1 ? shine : metal);
      }
    } else if (role < 0.86) {
      // the face itself, faint
      const ang = rand() * 6.2832, r = Math.sqrt(rand()) * R * 0.78;
      put(i, Math.cos(ang) * r, cy + Math.sin(ang) * r, -T, 0.14 + 0.16 * rand(), metal);
    } else if (role < 0.98) {
      // the ribbon: two bands up from the ring and apart, a light stripe down the middle of each, bright edges
      const side = rand() < 0.5 ? -1 : 1, v = rand(), a = rand() - 0.5, top = cy - R - 0.03;
      const x = side * (0.035 + v * 0.2) + a * 0.105, y = top - v * (top + 0.56) + Math.abs(a) * 0.02;
      const stripe = Math.abs(a) < 0.09, edge = Math.abs(a) > 0.44;
      put(i, x, y, 0.03 + side * 0.012, (stripe ? 0.85 : edge ? 0.75 : 0.4 + 0.1 * rand()) * Math.min(1, (1 - v) * 5), stripe ? TONE.white : edge ? TONE.cyan : TONE.deep);
    } else {
      // the ring it hangs by
      const ang = rand() * 6.2832;
      put(i, Math.cos(ang) * 0.034, cy - R - 0.026 + Math.sin(ang) * 0.034, 0, 0.8, metal);
    }
  }
  return { points, lum, tones, along, wave: 0.22, tone: metal, loose: 0.35, size: 1.2, gain: 1 };
}
