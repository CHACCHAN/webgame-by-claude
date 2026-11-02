import { Vector3 } from 'three';
import type { Track } from './Track';
import type { TerrainData } from './terrain';
import { SHOULDER, type Side } from './roadGeometry';
import { findCorners } from './corners';
import { clamp, smoothstep } from '../util/math';

/**
 * Roadside sites for the larger props (a small shrine, a rural bus stop): flat-ish ground on the
 * mountain side of a straight stretch, away from bends, tunnels, bridges and the other legs of the road.
 * The ground of each site is levelled to the road's bed so the props stand on it. DOM-free (tests, tools).
 */
export type SiteKind = 'shrine' | 'busStop';

export interface RoadsideSite {
  kind: SiteKind;
  /** track index of the site centre and the side of the road (+1 right, −1 left) */
  s: number;
  side: 1 | -1;
  /** footprint: ±halfLength along the road, depth away from it, starting `gap` beyond the road wall */
  halfLength: number;
  depth: number;
  /** yaw of the site's local +Z, which points at the road (props face the traffic) */
  yaw: number;
  /** worst ground deviation from the road bed before levelling (m) */
  flatness: number;
}

/** clear ground between the road wall (half width + shoulder) and a site: curb and low wall fit in it */
export const SITE_GAP = 1.4;

const SIZES: Record<SiteKind, { halfLength: number; depth: number }> = {
  shrine: { halfLength: 4.8, depth: 3.4 },
  busStop: { halfLength: 4.8, depth: 5.4 },
};

/** Height of the terrain bed beside the road at index i (as terrain.ts carves it). */
export function bedHeight(track: Track, i: number) {
  const k = clamp(Math.round(i), 0, track.count - 1);
  return track.pos[k * 3 + 1] - 0.45 - Math.abs(track.bank[k]) * (track.width[k] / 2 + 1.2);
}

/**
 * World position of a point in a site's frame: u along the road (+ = increasing s), v from the
 * footprint's road-side edge away from the road. y is the levelled ground there.
 */
export function sitePoint(track: Track, site: RoadsideSite, u: number, v: number, out = new Vector3()) {
  const i = clamp(Math.round(site.s + u), 0, track.count - 1);
  const lateral = site.side * (track.width[i] / 2 + SHOULDER + SITE_GAP + v);
  track.pointAt(site.s + u, lateral, out);
  out.y = bedHeight(track, site.s + u);
  return out;
}

/** Yaw that turns a prop's front (+Z) towards the road from the given side (+1 right, −1 left). */
export function faceRoadYaw(track: Track, s: number, side: number) {
  // +Z towards the road: −side × the road's right vector
  const i = clamp(Math.round(s), 0, track.count - 1);
  return Math.atan2(-side * track.right[i * 3], -side * track.right[i * 3 + 2]);
}

export function planRoadsideSites(track: Track, terrain: TerrainData, sides: { left: Side; right: Side }): RoadsideSite[] {
  const corners = findCorners(track, 40);
  const p = new Vector3();
  const candidates: Record<SiteKind, RoadsideSite[]> = { shrine: [], busStop: [] };
  const blocked = (i: number, reach: number) => {
    for (let k = Math.max(0, i - reach); k <= Math.min(track.count - 1, i + reach); k++) {
      const z = track.zone[k];
      if (z === 'rockshed' || z === 'bridge') return true;
      if (Math.abs(track.curvature[k]) > 1 / 150) return true;
    }
    return corners.some((c) => i > c.start - 75 && i < c.end + 15);
  };
  for (const kind of ['shrine', 'busStop'] as SiteKind[]) {
    const { halfLength, depth } = SIZES[kind];
    for (let i = Math.round(track.startS + 90); i < track.finishS - 90; i += 2) {
      if (blocked(i, Math.ceil(halfLength) + 8)) continue;
      for (const side of [1, -1] as const) {
        // mountain side along the whole footprint and a little beyond: no guardrail in front of the props
        const valley = (side > 0 ? sides.right : sides.left).valley;
        const reach = Math.ceil(halfLength) + 6;
        let rail = false;
        for (let k = Math.max(0, i - reach); k <= Math.min(track.count - 1, i + reach); k++) rail ||= valley[k] === 1;
        if (rail) continue;
        const site: RoadsideSite = { kind, s: i, side, halfLength, depth, yaw: faceRoadYaw(track, i, side), flatness: 0 };
        let worst = 0, ok = true;
        // the levelled area reaches 8 m round the footprint: no other leg of the road in it
        for (let u = -halfLength - 8; u <= halfLength + 8 && ok; u += 1) {
          for (let v = -1; v <= depth + 8; v += 1) {
            sitePoint(track, site, u, v, p);
            const lateral = track.width[i] / 2 + SHOULDER + SITE_GAP + v;
            if (terrain.roadDistAt(p.x, p.z) < lateral - 1.5) {
              ok = false;
              break;
            }
            if (Math.abs(u) <= halfLength && v >= 0 && v <= depth) worst = Math.max(worst, Math.abs(terrain.heightAt(p.x, p.z) - p.y));
          }
        }
        if (!ok) continue;
        site.flatness = worst;
        candidates[kind].push(site);
      }
    }
  }
  const out: RoadsideSite[] = [];
  const minGap = Math.max(250, track.count / 5);
  for (const kind of ['shrine', 'busStop'] as SiteKind[]) {
    const best = candidates[kind].filter((c) => c.flatness < 4 && out.every((o) => Math.abs(o.s - c.s) > minGap)).sort((a, b) => a.flatness - b.flatness)[0];
    if (best) out.push(best);
  }
  return out;
}

/**
 * Levels the near terrain grid under each site to the road bed: fully within one grid cell (4 m) round
 * the footprint so the mesh is flat under it, blending back to the natural ground over the next 4 m.
 * Grid points inside any road corridor are left alone.
 */
export function levelSites(track: Track, terrain: TerrainData, sites: RoadsideSite[]) {
  const g = terrain.near;
  const p = new Vector3();
  for (const site of sites) {
    const i = Math.round(site.s);
    const hw = track.width[i] / 2 + SHOULDER + SITE_GAP;
    const centre = sitePoint(track, site, 0, site.depth / 2, new Vector3());
    // site frame axes in world space
    const ax = Math.cos(site.yaw), az = -Math.sin(site.yaw); // local +X
    const bx = Math.sin(site.yaw), bz = Math.cos(site.yaw); // local +Z (towards the road)
    const reach = site.halfLength + site.depth + 12;
    const i0 = Math.max(0, Math.floor((centre.x - reach - g.x0) / g.cell)), i1 = Math.min(g.nx - 1, Math.ceil((centre.x + reach - g.x0) / g.cell));
    const j0 = Math.max(0, Math.floor((centre.z - reach - g.z0) / g.cell)), j1 = Math.min(g.nz - 1, Math.ceil((centre.z + reach - g.z0) / g.cell));
    for (let jj = j0; jj <= j1; jj++) {
      for (let ii = i0; ii <= i1; ii++) {
        const x = g.x0 + ii * g.cell, z = g.z0 + jj * g.cell;
        const k = jj * g.nx + ii;
        if ((g.roadDist?.[k] ?? 1e9) < track.width[i] / 2 + 1.2) continue;
        const dx = x - centre.x, dz = z - centre.z;
        // along the road (sign follows s: local +X may point either way) and away from it
        const along = dx * ax + dz * az;
        const away = -(dx * bx + dz * bz);
        const uSign = Math.sign((track.pos[Math.min(track.count - 1, i + 1) * 3] - track.pos[i * 3]) * ax + (track.pos[Math.min(track.count - 1, i + 1) * 3 + 2] - track.pos[i * 3 + 2]) * az) || 1;
        const u = along * uSign;
        const v = away + site.depth / 2;
        const out = Math.max(Math.abs(u) - site.halfLength - g.cell, v - site.depth - g.cell, 0);
        const w = 1 - smoothstep(0, 4, out);
        if (w <= 0 || v < -hw) continue;
        sitePoint(track, site, clamp(u, -site.halfLength - 8, site.halfLength + 8), 0, p);
        g.heights[k] += (p.y - g.heights[k]) * w;
      }
    }
  }
}

/** Circles (x, z, r) that trees and roadside clutter keep clear of. */
export function siteClearings(track: Track, sites: RoadsideSite[]) {
  return sites.map((site) => {
    const c = sitePoint(track, site, 0, site.depth / 2);
    return { x: c.x, z: c.z, r: Math.hypot(site.halfLength, site.depth / 2) + 1.5 };
  });
}
