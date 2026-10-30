import { DS, Track } from '../track/Track';
import { clamp } from '../util/math';

/**
 * A minimum-curvature racing line computed by iteratively relaxing lateral
 * offsets ("elastic band"), plus a grip-limited target speed profile.
 */
export class RacingLine {
  readonly track: Track;
  /** lateral offset (m, + = right) per track sample */
  readonly offset: Float32Array;
  /** curvature of the racing line (1/m) */
  readonly curvature: Float32Array;

  constructor(track: Track, margin = 1.6) {
    this.track = track;
    const n = track.count;
    const u = new Float32Array(n);
    const px = new Float32Array(n), pz = new Float32Array(n);
    const K = 8; // neighbour span in samples
    for (let iter = 0; iter < 260; iter++) {
      for (let i = 0; i < n; i++) {
        px[i] = track.pos[i * 3] + track.right[i * 3] * u[i];
        pz[i] = track.pos[i * 3 + 2] + track.right[i * 3 + 2] * u[i];
      }
      for (let i = K; i < n - K; i++) {
        const mx = (px[i - K] + px[i + K]) / 2, mz = (pz[i - K] + pz[i + K]) / 2;
        const rx = track.right[i * 3], rz = track.right[i * 3 + 2];
        const rl = Math.hypot(rx, rz) || 1;
        const delta = ((mx - px[i]) * rx + (mz - pz[i]) * rz) / rl;
        const lim = track.width[i] / 2 - margin;
        u[i] = clamp(u[i] + delta * 0.5, -lim, lim);
      }
    }
    // keep the very start and end on the centerline-ish
    this.offset = u;

    // curvature of the resulting line via heading change
    this.curvature = new Float32Array(n);
    for (let i = 0; i < n; i++) {
      px[i] = track.pos[i * 3] + track.right[i * 3] * u[i];
      pz[i] = track.pos[i * 3 + 2] + track.right[i * 3 + 2] * u[i];
    }
    const W = 5;
    for (let i = W; i < n - W; i++) {
      const h1 = Math.atan2(px[i] - px[i - W], pz[i] - pz[i - W]);
      const h2 = Math.atan2(px[i + W] - px[i], pz[i + W] - pz[i]);
      let d = h2 - h1;
      while (d > Math.PI) d -= Math.PI * 2;
      while (d < -Math.PI) d += Math.PI * 2;
      const len = Math.hypot(px[i + W] - px[i - W], pz[i + W] - pz[i - W]);
      this.curvature[i] = d / Math.max(len * 0.5, 0.1);
    }
  }

  offsetAt(s: number) {
    const t = clamp(s / DS, 0, this.track.count - 1.001);
    const i = Math.floor(t);
    return this.offset[i] + (this.offset[i + 1] - this.offset[i]) * (t - i);
  }

  /**
   * Target speed (m/s) per sample for a given cornering grip (m/s²),
   * braking decel and acceleration capability.
   */
  speedProfile(latAccel: number, brakeDecel: number, accel: number, vmax: number): Float32Array {
    const n = this.track.count;
    const v = new Float32Array(n);
    for (let i = 0; i < n; i++) {
      // average curvature over a short window for robustness
      let k = 0;
      for (let j = Math.max(0, i - 3); j <= Math.min(n - 1, i + 3); j++) k = Math.max(k, Math.abs(this.curvature[j]));
      v[i] = Math.min(vmax, Math.sqrt(latAccel / Math.max(k, 1e-4)));
    }
    for (let i = n - 2; i >= 0; i--) v[i] = Math.min(v[i], Math.sqrt(v[i + 1] * v[i + 1] + 2 * brakeDecel * DS));
    for (let i = 1; i < n; i++) v[i] = Math.min(v[i], Math.sqrt(v[i - 1] * v[i - 1] + 2 * accel * DS));
    return v;
  }
}
