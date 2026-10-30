import type { Track } from './Track';

export type CornerKind = 'hairpin' | 'tight' | 'medium';

export interface Corner {
  /** sample index (≈ metres) where the bend begins, its sharpest point and its end */
  start: number;
  apex: number;
  end: number;
  /** +1 = left, -1 = right */
  dir: 1 | -1;
  minRadius: number;
  /** angle turned inside the bend (rad) */
  angle: number;
  kind: CornerKind;
}

/**
 * Bends sharper than `maxRadius`: one entry per run of same-direction curvature
 * above the threshold (runs split by a short dip are merged).
 */
export function findCorners(track: Track, maxRadius = 70): Corner[] {
  const k = track.curvature;
  const kMin = 1 / maxRadius;
  const out: Corner[] = [];
  for (let i = 1; i < track.count - 1; i++) {
    if (Math.abs(k[i]) < kMin) continue;
    const dir = (k[i] > 0 ? 1 : -1) as 1 | -1;
    let j = i, apex = i, angle = 0;
    for (let gap = 0; j < track.count - 1 && gap < 8; j++) {
      const same = Math.abs(k[j]) >= kMin && Math.sign(k[j]) === dir;
      gap = same ? 0 : gap + 1;
      if (Math.sign(k[j]) === dir) angle += Math.abs(k[j]);
      if (Math.abs(k[j]) > Math.abs(k[apex])) apex = j;
    }
    const end = j - 8;
    const minRadius = 1 / Math.abs(k[apex]);
    const kind: CornerKind = minRadius <= 32 && angle > 1.9 ? 'hairpin' : minRadius <= 45 ? 'tight' : 'medium';
    out.push({ start: i, apex, end, dir, minRadius, angle, kind });
    i = end;
  }
  return out;
}
