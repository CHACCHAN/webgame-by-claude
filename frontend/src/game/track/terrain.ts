import { clamp, fbm, lerp, ridged, smoothstep } from '../util/math';
import { DS, Track } from './Track';
import type { Landform } from './landforms';

export interface HeightGrid {
  x0: number;
  z0: number;
  /** cell size (m) */
  cell: number;
  nx: number;
  nz: number;
  heights: Float32Array;
  /** distance (m) from the road centerline, only for the near grid */
  roadDist?: Float32Array;
  /**
   * distance (m) beyond the graded edge of the road (its asphalt, shoulder and formation; negative inside), only
   * for the near grid: where the verge's gravel ends and the slope begins, whatever the road's width
   */
  edgeDist?: Float32Array;
}

export interface TerrainData {
  near: HeightGrid;
  far: HeightGrid;
  landform: Landform;
  heightAt: (x: number, z: number) => number;
  /** horizontal distance to the road centerline (near region only, else large) */
  roadDistAt: (x: number, z: number) => number;
}

/** The size and place of a grid, known before any height is. */
export interface GridFrame {
  x0: number;
  z0: number;
  cell: number;
  nx: number;
  nz: number;
}

/**
 * Every `n`th row of both grids, from row `k` on, packed row after row: the part of the terrain one thread works
 * out (`TerrainPlan.stripe`). The far grid's heights are still doubles here: `finish` sinks them under the near
 * grid before they are rounded, as the single-threaded build does (the result must be the same to the bit).
 */
export interface TerrainStripe {
  k: number;
  n: number;
  nearH: Float32Array;
  nearD: Float32Array;
  nearE: Float32Array;
  nearI: Int32Array;
  farH: Float64Array;
}

/**
 * The terrain of a course before its heights are worked out: the two grids' frames, the heights of any rows of
 * them (the costly part, independent row by row: `terrainJob.ts` gives the stripes to workers) and what is left
 * for one thread once all rows are there (`finish`).
 */
export interface TerrainPlan {
  near: GridFrame;
  far: GridFrame;
  stripe(k: number, n: number): TerrainStripe;
  finish(stripes: TerrainStripe[]): TerrainData;
}

/** Region where the road carves the terrain (m around the centerline). */
const ROAD_INFLUENCE = 320;

/**
 * Medium/fine relief, attenuated next to the road: rolling ground, and on it the spurs and gullies running water
 * leaves (a ridged noise bent by a slower one, so the ridges branch and wander instead of lying in rows) with
 * knobs of rock on them. None of it reaches the road: `fieldHeight` fades it out 14 m from the centreline.
 */
function detailHeight(lf: Landform, x: number, z: number): number {
  const r = lf.relief(x, z);
  if (r <= 0) return 0;
  const wx = x + fbm(x / 310 - 3.7, z / 310 + 8.2, 2) * 90, wz = z + fbm(x / 310 + 6.1, z / 310 - 1.3, 2) * 90;
  const spurs = (ridged(wx / 420 + 1.3, wz / 420 - 7.9, 3) - 0.45) * 15;
  const knobs = Math.max(0, ridged(x / 70 + 9.4, z / 70 + 2.6, 2) - 0.55) * 7;
  return (fbm(x / 160 + 4.4, z / 160 - 1.9, 4) * 9 + fbm(x / 45, z / 45, 3) * 2.2 + (spurs + knobs) * (lf.gullies ?? 1)) * r;
}

interface RoadSample {
  x: number;
  y: number;
  z: number;
  halfW: number;
  bridge: boolean;
  index: number;
  /** hillside gradient (height change per metre) used to tilt the local terrain plane */
  gx: number;
  gz: number;
  /** 0..1: the road runs along a crest, so the ground falls away on both sides */
  ridge: number;
}

/** Steepness of the hillside the road is cut into, per zone. */
const SLOPE: Partial<Record<string, number>> = {
  vista: 1.0, hairpins: 0.62, start: 0.38, forest: 0.58, rockshed: 0.95, bridge: 0.3, finish: 0.4, crest: 0.08, lakeside: 0.5,
  motorway: 0.5, overpass: 0.5, village: 0.4, interchange: 0.3,
};

function roadSamples(track: Track, lf: Landform, spacing: number): RoadSample[] {
  const baseHeight = (x: number, z: number) => lf.base(x, z);
  const out: RoadSample[] = [];
  for (let i = 0; i < track.count; i += spacing) {
    const x = track.pos[i * 3], z = track.pos[i * 3 + 2];
    // fall line of the large-scale landform around the sample
    const e = 40;
    let gx = (baseHeight(x + e, z) - baseHeight(x - e, z)) / (2 * e);
    let gz = (baseHeight(x, z + e) - baseHeight(x, z - e)) / (2 * e);
    const len = Math.hypot(gx, gz) || 1;
    const steep = (SLOPE[track.zone[i] ?? ''] ?? 0.55) * (lf.hillside ?? 1);
    gx = (gx / len) * steep;
    gz = (gz / len) * steep;
    const ridge = track.zone[i] === 'crest' ? 1 : track.zone[i] === 'start' && lf.treeLine < 1000 ? 0.7 : 0;
    out.push({ x, y: track.pos[i * 3 + 1], z, halfW: track.width[i] / 2, bridge: track.zone[i] === 'bridge', index: i, gx, gz, ridge });
  }
  // smooth the gradients along the road so the hillside doesn't twist abruptly
  for (let pass = 0; pass < 3; pass++) {
    for (let k = 1; k < out.length - 1; k++) {
      out[k].gx = (out[k - 1].gx + out[k].gx * 2 + out[k + 1].gx) / 4;
      out[k].gz = (out[k - 1].gz + out[k].gz * 2 + out[k + 1].gz) / 4;
    }
  }
  return out;
}

/**
 * Builds the terrain heightfields. The near grid is shaped around the road:
 * road heights are interpolated into the surrounding slopes (so switchback
 * legs sit on a consistent hillside), then the road corridor is cut/filled
 * with embankments. The bridge zone is never filled, leaving a gorge.
 */
export function buildTerrain(track: Track, lf: Landform, opts: TerrainOptions = {}): TerrainData {
  const plan = planTerrain(track, lf, opts);
  return plan.finish([plan.stripe(0, 1)]);
}

export interface TerrainOptions {
  nearCell?: number;
  farCell?: number;
}

export function planTerrain(track: Track, lf: Landform, opts: TerrainOptions = {}): TerrainPlan {
  const nearCell = opts.nearCell ?? lf.grid?.near ?? 4;
  const farCell = opts.farCell ?? lf.grid?.far ?? 24;
  // flat graded ground beyond the drivable edges (a motorway's median, opposite carriageway and verges)
  const formation = track.design.formation ?? { left: 0, right: 0 };
  // how far the ground lies under the road's surface
  const BED = track.design.bed ?? 0.45;
  const coarse = roadSamples(track, lf, 8);
  const baseHeight = (x: number, z: number) => lf.base(x, z);

  // gorge under the bridge: a valley line through the bridge midpoint
  const bridgeRanges = track.zoneRanges('bridge');
  const gorges = bridgeRanges.map(([a, b]) => {
    const mid = Math.round((a + b) / 2);
    const m = track.getPos(mid);
    const f = track.getFwd(mid);
    const fl = Math.hypot(f.x, f.z) || 1;
    return { x: m.x, z: m.z, y: m.y, fx: f.x / fl, fz: f.z / fl, half: ((b - a) / 2) * DS };
  });

  // spatial hash of coarse samples
  const CELL = 64;
  const hash = new Map<number, RoadSample[]>();
  const key = (cx: number, cz: number) => (cx + 1024) * 4096 + (cz + 1024);
  for (const s of coarse) {
    const k = key(Math.floor(s.x / CELL), Math.floor(s.z / CELL));
    let l = hash.get(k);
    if (!l) hash.set(k, (l = []));
    l.push(s);
  }
  const R = Math.ceil(ROAD_INFLUENCE / CELL);

  const gorgeDepth = (x: number, z: number, roadY: number) => {
    let d = 0;
    if (lf.viaducts) {
      // a viaduct spans a valley of the landform: as wide as the bridge, the ground follows that valley down
      for (const g of gorges) {
        const across = Math.abs((x - g.x) * g.fx + (z - g.z) * g.fz);
        const depth = Math.max(0, g.y - 6 - baseHeight(x, z));
        d = Math.max(d, depth * smoothstep(g.half + 40, g.half - 40, across));
      }
      return d;
    }
    for (const g of gorges) {
      // valley axis runs roughly north-south, meandering a little
      const ax = g.x + (z - g.z) * 0.18 + Math.sin((z - g.z) / 140) * 30;
      const lateral = Math.abs(x - ax);
      const along = smoothstep(900, 200, Math.abs(z - g.z));
      const depth = Math.max(0, g.y - 48 - baseHeight(x, z)) + 48;
      d = Math.max(d, depth * smoothstep(90, 12, lateral) * along);
      void roadY;
    }
    return d;
  };

  function fieldHeight(x: number, z: number, out: { dist: number; roadY: number; idx: number; lat: number }) {
    const base = baseHeight(x, z);
    const cx = Math.floor(x / CELL), cz = Math.floor(z / CELL);
    let wSum = 0, hSum = 0;
    let best = Infinity, bestS: RoadSample | null = null;
    for (let ox = -R; ox <= R; ox++)
      for (let oz = -R; oz <= R; oz++) {
        const list = hash.get(key(cx + ox, cz + oz));
        if (!list) continue;
        for (const s of list) {
          const dx = x - s.x, dz = z - s.z;
          const d2 = dx * dx + dz * dz;
          if (d2 < best) {
            best = d2;
            bestS = s;
          }
          if (d2 > ROAD_INFLUENCE * ROAD_INFLUENCE) continue;
          // taper to zero at the influence radius so there is no visible rim
          const taper = smoothstep(ROAD_INFLUENCE, ROAD_INFLUENCE * 0.5, Math.sqrt(d2));
          const w = ((s.bridge ? 0.05 : 1) * taper) / (d2 + 400);
          // each sample contributes a tilted plane: the road is cut into a hillside
          const along = 120 * Math.tanh((dx * s.gx + dz * s.gz) / Math.max(Math.hypot(s.gx, s.gz), 1e-6) / 120);
          let rise = along * Math.hypot(s.gx, s.gz);
          // crest roads: the ground drops away on both sides
          if (s.ridge > 0) rise -= s.ridge * 0.36 * Math.min(Math.sqrt(d2), 160) * smoothstep(8, 30, Math.sqrt(d2));
          wSum += w;
          hSum += w * (s.y + rise);
        }
      }
    out.dist = Infinity;
    out.roadY = 0;
    out.idx = -1;
    out.lat = 0;
    if (!bestS) return base + detailHeight(lf, x, z);

    // refine distance against the dense centerline around the nearest coarse sample
    let bestD = Infinity, bestI = bestS.index;
    for (let i = Math.max(0, bestS.index - 10); i <= Math.min(track.count - 1, bestS.index + 10); i++) {
      const dx = x - track.pos[i * 3], dz = z - track.pos[i * 3 + 2];
      const d = dx * dx + dz * dz;
      if (d < bestD) {
        bestD = d;
        bestI = i;
      }
    }
    const dist = Math.sqrt(bestD);
    out.dist = dist;
    out.roadY = track.pos[bestI * 3 + 1];
    out.idx = bestI;
    // signed: + = right of the centreline
    out.lat = (x - track.pos[bestI * 3]) * track.right[bestI * 3] + (z - track.pos[bestI * 3 + 2]) * track.right[bestI * 3 + 2];

    // Interpolated road surface field, fading into the natural landform.
    const roadField = wSum > 0 ? hSum / wSum : base;
    const influence = smoothstep(ROAD_INFLUENCE * 0.85, 120, dist) * (lf.follow ?? 1);
    const noiseAtten = smoothstep(14, 90, dist);
    let h = lerp(base + detailHeight(lf, x, z) * noiseAtten, roadField, influence * 0.92);
    h += fbm(x / 120 - 7.7, z / 120 + 3.3, 3) * 7 * noiseAtten * influence * (lf.roadsideRelief ?? 1);
    h -= gorgeDepth(x, z, out.roadY) * influence;
    return h;
  }

  function finalHeight(x: number, z: number, info: { dist: number; roadY: number; idx: number; lat: number }) {
    const h = fieldHeight(x, z, info);
    if (info.idx < 0) return h;
    const halfW = track.width[info.idx] / 2;
    const edge = halfW + 1.2 + (info.lat < 0 ? formation.left : formation.right);
    // banked corners drop the inner edge below the centreline: keep the bed under the lowest edge
    const bed = info.roadY - BED - Math.abs(track.bank[info.idx]) * edge;
    const isBridge = track.zone[info.idx] === 'bridge';
    if (info.dist < edge) {
      if (isBridge) return Math.min(h, bed - 9);
      return bed;
    }
    const diff = h - bed;
    // embankment / cutting width grows with the height difference
    const span = 3 + Math.abs(diff) * (diff > 0 ? 0.55 : 1.1);
    const t = smoothstep(0, 1, (info.dist - edge) / span);
    if (isBridge) {
      // never fill under the bridge; only cut back hillsides near the deck
      return diff > -9 ? lerp(bed - 9, h, t) : h;
    }
    return lerp(bed, h, t);
  }

  // ---- near grid
  let minX = Infinity, maxX = -Infinity, minZ = Infinity, maxZ = -Infinity;
  for (let i = 0; i < track.count; i += 4) {
    minX = Math.min(minX, track.pos[i * 3]);
    maxX = Math.max(maxX, track.pos[i * 3]);
    minZ = Math.min(minZ, track.pos[i * 3 + 2]);
    maxZ = Math.max(maxZ, track.pos[i * 3 + 2]);
  }
  const margin = ROAD_INFLUENCE + 60;
  const nx0 = Math.floor((minX - margin) / nearCell) * nearCell;
  const nz0 = Math.floor((minZ - margin) / nearCell) * nearCell;
  const nnx = Math.ceil((maxX + margin - nx0) / nearCell) + 1;
  const nnz = Math.ceil((maxZ + margin - nz0) / nearCell) + 1;
  const info = { dist: 0, roadY: 0, idx: -1, lat: 0 };
  /** one row of the near grid into the arrays, from index `at` on */
  const nearRow = (j: number, at: number, H: Float32Array, D: Float32Array, E: Float32Array, I: Int32Array) => {
    const z = nz0 + j * nearCell;
    for (let i = 0; i < nnx; i++) {
      const x = nx0 + i * nearCell;
      H[at + i] = finalHeight(x, z, info);
      D[at + i] = info.dist;
      I[at + i] = info.idx;
      E[at + i] = info.idx < 0 ? 1e6 : info.dist - (track.width[info.idx] / 2 + 1.2 + (info.lat < 0 ? formation.left : formation.right));
    }
  };

  // ---- far grid (pure landform; dips below the near grid so the near mesh wins)
  const cxm = (minX + maxX) / 2, czm = (minZ + maxZ) / 2;
  // an 11.2 × 10.4 km square around the course, or as far beyond the course as the landform asks
  const reach = lf.grid?.reach ?? 0;
  const fw = Math.max(11200, maxX - minX + 2 * reach), fd = Math.max(10400, maxZ - minZ + 2 * reach);
  const fx0 = Math.floor((cxm - fw / 2) / farCell) * farCell, fz0 = Math.floor((czm - fd / 2) / farCell) * farCell;
  const fnx = Math.ceil(fw / farCell) + 1;
  const fnz = Math.ceil(fd / farCell) + 1;
  const nearX1 = nx0 + (nnx - 1) * nearCell, nearZ1 = nz0 + (nnz - 1) * nearCell;
  /** one row of the far grid: the landform alone, sunk towards the grid's edges (not yet under the near grid) */
  const farRow = (j: number, at: number, H: Float64Array) => {
    const z = fz0 + j * farCell;
    for (let i = 0; i < fnx; i++) {
      const x = fx0 + i * farCell;
      let h = baseHeight(x, z) + detailHeight(lf, x, z);
      // sink the landscape towards the grid edges so the horizon never shows a cut-off cliff
      const edge = Math.min(i, fnx - 1 - i, j, fnz - 1 - j) * farCell;
      const floor = lf.waterLevel !== null ? lf.waterLevel - 30 : Math.min(h, 120);
      h = lerp(Math.min(h, floor), h, smoothstep(0, 1600, edge));
      H[at + i] = h;
    }
  };

  const rowsOf = (rows: number, k: number, n: number) => (k < rows ? Math.ceil((rows - k) / n) : 0);
  const stripe = (k: number, n: number): TerrainStripe => {
    const nr = rowsOf(nnz, k, n), fr = rowsOf(fnz, k, n);
    const out: TerrainStripe = { k, n, nearH: new Float32Array(nr * nnx), nearD: new Float32Array(nr * nnx), nearE: new Float32Array(nr * nnx), nearI: new Int32Array(nr * nnx), farH: new Float64Array(fr * fnx) };
    for (let r = 0; r < nr; r++) nearRow(k + r * n, r * nnx, out.nearH, out.nearD, out.nearE, out.nearI);
    for (let r = 0; r < fr; r++) farRow(k + r * n, r * fnx, out.farH);
    return out;
  };

  const finish = (stripes: TerrainStripe[]): TerrainData => {
    const nearH = new Float32Array(nnx * nnz);
    const nearD = new Float32Array(nnx * nnz);
    const nearE = new Float32Array(nnx * nnz);
    const nearI = new Int32Array(nnx * nnz);
    const farRaw = new Float64Array(fnx * fnz);
    // every row of both grids exactly once
    const nearSeen = new Uint8Array(nnz), farSeen = new Uint8Array(fnz);
    for (const st of stripes) {
      const nr = rowsOf(nnz, st.k, st.n), fr = rowsOf(fnz, st.k, st.n);
      if (st.nearH.length !== nr * nnx || st.nearD.length !== nr * nnx || st.nearE.length !== nr * nnx || st.nearI.length !== nr * nnx || st.farH.length !== fr * fnx) throw new Error('terrain: a stripe of the wrong size');
      for (let r = 0; r < nr; r++) {
        const j = st.k + r * st.n, a = r * nnx, b = a + nnx;
        nearH.set(st.nearH.subarray(a, b), j * nnx);
        nearD.set(st.nearD.subarray(a, b), j * nnx);
        nearE.set(st.nearE.subarray(a, b), j * nnx);
        nearI.set(st.nearI.subarray(a, b), j * nnx);
        nearSeen[j]++;
      }
      for (let r = 0; r < fr; r++) {
        const j = st.k + r * st.n;
        farRaw.set(st.farH.subarray(r * fnx, (r + 1) * fnx), j * fnx);
        farSeen[j]++;
      }
    }
    if (nearSeen.some((c) => c !== 1) || farSeen.some((c) => c !== 1)) throw new Error('terrain: rows missing or given twice');
    // Hairpins: a grid point that belongs to the other leg's cutting can sit above this leg's road edge,
    // and bilinear interpolation then lifts the ground over the asphalt. Keep every road corridor clear.
    for (let k = 0; k < track.count; k++) {
      if (track.zone[k] === 'bridge') continue;
      const px = track.pos[k * 3], py = track.pos[k * 3 + 1], pz = track.pos[k * 3 + 2];
      const reach = track.width[k] / 2 + 1.2 + nearCell;
      const i0 = Math.max(0, Math.floor((px - reach - nx0) / nearCell)), i1 = Math.min(nnx - 1, Math.ceil((px + reach - nx0) / nearCell));
      const j0 = Math.max(0, Math.floor((pz - reach - nz0) / nearCell)), j1 = Math.min(nnz - 1, Math.ceil((pz + reach - nz0) / nearCell));
      for (let jj = j0; jj <= j1; jj++) {
        for (let ii = i0; ii <= i1; ii++) {
          const g = jj * nnx + ii;
          if (Math.abs(nearI[g] - k) < 40) continue;
          if (Math.hypot(nx0 + ii * nearCell - px, nz0 + jj * nearCell - pz) > reach) continue;
          nearH[g] = Math.min(nearH[g], py - BED - Math.abs(track.bank[k]) * reach);
        }
      }
    }
    const near: HeightGrid = { x0: nx0, z0: nz0, cell: nearCell, nx: nnx, nz: nnz, heights: nearH, roadDist: nearD, edgeDist: nearE };

    // ---- far grid: under the near mesh it is hidden
    const farH = new Float32Array(fnx * fnz);
    // lowest near-grid height within one far cell of (x, z): the coarse mesh must stay under every road
    // cut of the near mesh, not only under the point it sits on
    const nearMin = (x: number, z: number) => {
      const i0 = Math.max(0, Math.floor((x - farCell - nx0) / nearCell)), i1 = Math.min(nnx - 1, Math.ceil((x + farCell - nx0) / nearCell));
      const j0 = Math.max(0, Math.floor((z - farCell - nz0) / nearCell)), j1 = Math.min(nnz - 1, Math.ceil((z + farCell - nz0) / nearCell));
      let m = Infinity;
      for (let jj = j0; jj <= j1; jj++) for (let ii = i0; ii <= i1; ii++) m = Math.min(m, nearH[jj * nnx + ii]);
      return m;
    };
    for (let j = 0; j < fnz; j++) {
      const z = fz0 + j * farCell;
      for (let i = 0; i < fnx; i++) {
        const x = fx0 + i * farCell;
        let h = farRaw[j * fnx + i];
        // sink it below the lowest near terrain around it
        // (the outermost cell is kept so the two meshes meet at the near grid's border)
        const inside = x > nx0 + farCell && x < nearX1 - farCell && z > nz0 + farCell && z < nearZ1 - farCell;
        if (inside) h = Math.min(h - 30, nearMin(x, z) - 8);
        farH[j * fnx + i] = h;
      }
    }
    const far: HeightGrid = { x0: fx0, z0: fz0, cell: farCell, nx: fnx, nz: fnz, heights: farH };

    const sample = (g: HeightGrid, arr: Float32Array, x: number, z: number) => {
      const gx = clamp((x - g.x0) / g.cell, 0, g.nx - 1.001);
      const gz = clamp((z - g.z0) / g.cell, 0, g.nz - 1.001);
      const i = Math.floor(gx), j = Math.floor(gz);
      const fx = gx - i, fz = gz - j;
      const a = arr[j * g.nx + i], b = arr[j * g.nx + i + 1];
      const c = arr[(j + 1) * g.nx + i], d = arr[(j + 1) * g.nx + i + 1];
      return lerp(lerp(a, b, fx), lerp(c, d, fx), fz);
    };
    const inNear = (x: number, z: number) => x >= nx0 && x <= nearX1 && z >= nz0 && z <= nearZ1;

    return {
      near,
      far,
      landform: lf,
      heightAt: (x, z) => (inNear(x, z) ? sample(near, nearH, x, z) : sample(far, farH, x, z)),
      roadDistAt: (x, z) => (inNear(x, z) ? sample(near, nearD, x, z) : 1e6),
    };
  };

  return { near: { x0: nx0, z0: nz0, cell: nearCell, nx: nnx, nz: nnz }, far: { x0: fx0, z0: fz0, cell: farCell, nx: fnx, nz: fnz }, stripe, finish };
}

export { DS };
