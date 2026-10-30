import { Vector3 } from 'three';
import { clamp, lerp } from '../util/math';
import type { CourseDesign, ZoneTag } from './courseDesign';

/** Distance between centerline samples (m). */
export const DS = 1;

export interface TrackProjection {
  /** index of the sample just before the projected point */
  index: number;
  /** distance along the track (m) */
  s: number;
  /** signed lateral offset, positive = right of the centerline */
  lateral: number;
  /** height of the point above the road plane */
  height: number;
}

function movingAverage(src: Float64Array, window: number): Float64Array {
  const n = src.length;
  const out = new Float64Array(n);
  const half = Math.floor(window / 2);
  // prefix sums for O(n)
  const pre = new Float64Array(n + 1);
  for (let i = 0; i < n; i++) pre[i + 1] = pre[i] + src[i];
  for (let i = 0; i < n; i++) {
    const a = Math.max(0, i - half);
    const b = Math.min(n, i + half + 1);
    out[i] = (pre[b] - pre[a]) / (b - a);
  }
  return out;
}

/**
 * Dense centerline representation of a course: positions, frames, width,
 * curvature and zone tags every DS meters, plus fast projection queries.
 */
export class Track {
  readonly design: CourseDesign;
  readonly count: number;
  readonly length: number;
  /** xyz per sample */
  readonly pos: Float32Array;
  /** unit forward (includes grade) */
  readonly fwd: Float32Array;
  /** unit right (includes banking) */
  readonly right: Float32Array;
  /** unit up (road normal) */
  readonly up: Float32Array;
  readonly width: Float32Array;
  /** signed curvature (1/m), positive = left */
  readonly curvature: Float32Array;
  readonly heading: Float32Array;
  readonly bank: Float32Array;
  readonly zone: (ZoneTag | undefined)[];
  /** track distance of the start line */
  readonly startS: number;
  /** track distance of the finish line (the road continues a little after it) */
  readonly finishS: number;
  /** track distance of each sector split; the last equals finishS */
  readonly sectorSplits: number[];

  private grid = new Map<number, number[]>();
  private static readonly CELL = 24;

  constructor(design: CourseDesign) {
    this.design = design;

    // 1. Rasterise the segment list into per-meter curvature / grade / width.
    const kRaw: number[] = [];
    const gRaw: number[] = [];
    const wRaw: number[] = [];
    const zones: (ZoneTag | undefined)[] = [];
    for (const seg of design.segs) {
      const isArc = seg.r !== undefined;
      const len = isArc ? Math.abs((seg.deg! * Math.PI) / 180) * seg.r! : seg.len!;
      const k = isArc ? Math.sign(seg.deg!) / seg.r! : 0;
      const steps = Math.max(1, Math.round(len / DS));
      for (let i = 0; i < steps; i++) {
        kRaw.push(k);
        gRaw.push(seg.g);
        wRaw.push(seg.w ?? design.baseWidth);
        zones.push(seg.tag);
      }
    }
    const n = kRaw.length + 1;
    kRaw.push(0);
    gRaw.push(gRaw[gRaw.length - 1]);
    wRaw.push(wRaw[wRaw.length - 1]);
    zones.push(zones[zones.length - 1]);

    // Smoothing keeps the integral (total heading change) intact.
    const k = movingAverage(Float64Array.from(kRaw), 24);
    const g = movingAverage(Float64Array.from(gRaw), 60);
    const widthBase = movingAverage(Float64Array.from(wRaw), 40);

    this.count = n;
    this.length = (n - 1) * DS;
    this.pos = new Float32Array(n * 3);
    this.fwd = new Float32Array(n * 3);
    this.right = new Float32Array(n * 3);
    this.up = new Float32Array(n * 3);
    this.width = new Float32Array(n);
    this.curvature = new Float32Array(n);
    this.heading = new Float32Array(n);
    this.bank = new Float32Array(n);
    this.zone = zones;

    // 2. Integrate heading & position.
    let x = design.start.x, y = design.start.y, z = design.start.z;
    let h = design.start.heading;
    const widen = new Float64Array(n);
    for (let i = 0; i < n; i++) {
      this.pos[i * 3] = x;
      this.pos[i * 3 + 1] = y;
      this.pos[i * 3 + 2] = z;
      this.heading[i] = h;
      this.curvature[i] = k[i];
      // Hairpins get wider, like real mountain roads.
      widen[i] = clamp((Math.abs(k[i]) - 1 / 70) * 160, 0, 3.2);
      // advance (midpoint rule)
      const hm = h + k[i] * DS * 0.5;
      x += Math.sin(hm) * DS;
      z += Math.cos(hm) * DS;
      y += g[i] * DS;
      h += k[i] * DS;
    }
    const widenSm = movingAverage(widen, 30);
    const bankRaw = new Float64Array(n);
    for (let i = 0; i < n; i++) {
      this.width[i] = widthBase[i] + widenSm[i];
      // Bank into the corner, capped at ~4.5 degrees.
      bankRaw[i] = clamp(k[i] * 3.2, -0.08, 0.08);
    }
    const bankSm = movingAverage(bankRaw, 30);

    // 3. Frames.
    const f = new Vector3(), r = new Vector3(), u = new Vector3(), worldUp = new Vector3(0, 1, 0);
    for (let i = 0; i < n; i++) {
      const a = Math.max(0, i - 1), b = Math.min(n - 1, i + 1);
      f.set(
        this.pos[b * 3] - this.pos[a * 3],
        this.pos[b * 3 + 1] - this.pos[a * 3 + 1],
        this.pos[b * 3 + 2] - this.pos[a * 3 + 2],
      ).normalize();
      r.crossVectors(f, worldUp).normalize();
      // bank: positive curvature (left turn) raises the right edge
      const bank = bankSm[i];
      this.bank[i] = bank;
      r.applyAxisAngle(f, -bank);
      u.crossVectors(r, f).normalize();
      f.toArray(this.fwd, i * 3);
      r.toArray(this.right, i * 3);
      u.toArray(this.up, i * 3);
    }

    // 4. Timing lines and sector splits evenly by distance.
    this.startS = 40;
    this.finishS = this.length - 120;
    this.sectorSplits = [];
    const timed = this.finishS - this.startS;
    for (let i = 1; i <= design.sectors; i++) this.sectorSplits.push(this.startS + (timed * i) / design.sectors);

    // 5. Spatial hash for global projection queries.
    for (let i = 0; i < n; i += 2) {
      const key = this.cellKey(this.pos[i * 3], this.pos[i * 3 + 2]);
      let list = this.grid.get(key);
      if (!list) this.grid.set(key, (list = []));
      list.push(i);
    }
  }

  private cellKey(x: number, z: number) {
    const cx = Math.floor(x / Track.CELL) + 4096;
    const cz = Math.floor(z / Track.CELL) + 4096;
    return cx * 8192 + cz;
  }

  getPos(i: number, out = new Vector3()) {
    i = clamp(i, 0, this.count - 1);
    return out.fromArray(this.pos, i * 3);
  }
  getFwd(i: number, out = new Vector3()) {
    i = clamp(i, 0, this.count - 1);
    return out.fromArray(this.fwd, i * 3);
  }
  getRight(i: number, out = new Vector3()) {
    i = clamp(i, 0, this.count - 1);
    return out.fromArray(this.right, i * 3);
  }
  getUp(i: number, out = new Vector3()) {
    i = clamp(i, 0, this.count - 1);
    return out.fromArray(this.up, i * 3);
  }

  /** Interpolated centerline point at distance s plus a lateral offset (m, + = right). */
  pointAt(s: number, lateral = 0, out = new Vector3()) {
    const t = clamp(s / DS, 0, this.count - 1.0001);
    const i = Math.floor(t), f = t - i;
    const o = i * 3;
    for (let c = 0; c < 3; c++) {
      const p = lerp(this.pos[o + c], this.pos[o + 3 + c], f);
      const rr = lerp(this.right[o + c], this.right[o + 3 + c], f);
      out.setComponent(c, p + rr * lateral);
    }
    return out;
  }

  headingAt(s: number) {
    const t = clamp(s / DS, 0, this.count - 1.0001);
    const i = Math.floor(t);
    return lerp(this.heading[i], this.heading[i + 1], t - i);
  }

  widthAt(s: number) {
    const t = clamp(s / DS, 0, this.count - 1.0001);
    const i = Math.floor(t);
    return lerp(this.width[i], this.width[i + 1], t - i);
  }

  curvatureAt(s: number) {
    const t = clamp(s / DS, 0, this.count - 1.0001);
    const i = Math.floor(t);
    return lerp(this.curvature[i], this.curvature[i + 1], t - i);
  }

  zoneAt(s: number) {
    return this.zone[clamp(Math.round(s / DS), 0, this.count - 1)];
  }

  /**
   * Project a world position onto the track. When a hint index is given only
   * a local window is searched (cheap, used every physics step); otherwise the
   * spatial hash is used.
   */
  project(x: number, y: number, z: number, hint = -1, out?: TrackProjection): TrackProjection {
    let best = -1;
    let bestD = Infinity;
    const test = (i: number) => {
      const dx = this.pos[i * 3] - x, dz = this.pos[i * 3 + 2] - z;
      const dy = (this.pos[i * 3 + 1] - y) * 2; // vertical bias to separate stacked legs
      const d = dx * dx + dz * dz + dy * dy;
      if (d < bestD) {
        bestD = d;
        best = i;
      }
    };
    if (hint >= 0) {
      const a = Math.max(0, hint - 40), b = Math.min(this.count - 1, hint + 60);
      for (let i = a; i <= b; i++) test(i);
    }
    if (hint < 0 || bestD > 30 * 30) {
      const cx = Math.floor(x / Track.CELL), cz = Math.floor(z / Track.CELL);
      for (let ox = -2; ox <= 2; ox++)
        for (let oz = -2; oz <= 2; oz++) {
          const list = this.grid.get((cx + ox + 4096) * 8192 + (cz + oz + 4096));
          if (!list) continue;
          for (const i of list) {
            for (let j = Math.max(0, i - 1); j <= Math.min(this.count - 1, i + 1); j++) test(j);
          }
        }
      if (best < 0) for (let i = 0; i < this.count; i += 4) test(i);
    }

    // refine on the segment between best and its neighbour
    let i0 = best;
    const fx = this.fwd[best * 3], fy = this.fwd[best * 3 + 1], fz = this.fwd[best * 3 + 2];
    const along = (x - this.pos[best * 3]) * fx + (y - this.pos[best * 3 + 1]) * fy + (z - this.pos[best * 3 + 2]) * fz;
    if (along < 0 && i0 > 0) i0 -= 1;
    i0 = Math.min(i0, this.count - 2);
    const o = i0 * 3;
    const px = x - this.pos[o], py = y - this.pos[o + 1], pz = z - this.pos[o + 2];
    const t = clamp(px * this.fwd[o] + py * this.fwd[o + 1] + pz * this.fwd[o + 2], 0, DS);
    const lateral = px * this.right[o] + py * this.right[o + 1] + pz * this.right[o + 2];
    const height = px * this.up[o] + py * this.up[o + 1] + pz * this.up[o + 2];
    const res = out ?? { index: 0, s: 0, lateral: 0, height: 0 };
    res.index = i0;
    res.s = i0 * DS + t;
    res.lateral = lateral;
    res.height = height;
    return res;
  }

  /** Iterate over contiguous index ranges of a zone tag. */
  zoneRanges(tag: ZoneTag): [number, number][] {
    const out: [number, number][] = [];
    let start = -1;
    for (let i = 0; i < this.count; i++) {
      const inZone = this.zone[i] === tag;
      if (inZone && start < 0) start = i;
      if (!inZone && start >= 0) {
        out.push([start, i - 1]);
        start = -1;
      }
    }
    if (start >= 0) out.push([start, this.count - 1]);
    return out;
  }
}
