import * as THREE from 'three';

export const GHOST_FORMAT = 1;
export const GHOST_INTERVAL_MS = 50;

/** One recorded sample: position (m), rotation, front steer angle (rad). */
export interface GhostFrame {
  x: number;
  y: number;
  z: number;
  qx: number;
  qy: number;
  qz: number;
  qw: number;
  steer: number;
}

export interface GhostData {
  intervalMs: number;
  frames: GhostFrame[];
}

export interface EncodedGhost {
  format: number;
  interval_ms: number;
  frame_count: number;
  data: string;
}

/** Records frames at a fixed interval of race time. */
export class GhostRecorder {
  frames: GhostFrame[] = [];
  private nextT = 0;

  reset() {
    this.frames = [];
    this.nextT = 0;
  }

  /** raceTime in seconds since GO */
  sample(raceTime: number, pos: THREE.Vector3, q: THREE.Quaternion, steer: number) {
    while (raceTime >= this.nextT) {
      this.frames.push({ x: pos.x, y: pos.y, z: pos.z, qx: q.x, qy: q.y, qz: q.z, qw: q.w, steer });
      this.nextT += GHOST_INTERVAL_MS / 1000;
    }
  }

  data(): GhostData {
    return { intervalMs: GHOST_INTERVAL_MS, frames: this.frames.slice() };
  }
}

const _qa = new THREE.Quaternion(), _qb = new THREE.Quaternion();

/** Plays back ghost data with interpolation. */
export class GhostPlayer {
  constructor(readonly data: GhostData) {}

  get duration() {
    return ((this.data.frames.length - 1) * this.data.intervalMs) / 1000;
  }

  pose(t: number, pos: THREE.Vector3, q: THREE.Quaternion) {
    const f = this.data.frames;
    if (!f.length) return { steer: 0, done: true };
    const x = Math.max(0, t) / (this.data.intervalMs / 1000);
    const i = Math.min(f.length - 1, Math.floor(x));
    const j = Math.min(f.length - 1, i + 1);
    const a = f[i], b = f[j];
    const k = Math.min(1, x - i);
    pos.set(a.x + (b.x - a.x) * k, a.y + (b.y - a.y) * k, a.z + (b.z - a.z) * k);
    _qa.set(a.qx, a.qy, a.qz, a.qw);
    _qb.set(b.qx, b.qy, b.qz, b.qw);
    q.slerpQuaternions(_qa, _qb, k);
    return { steer: a.steer + (b.steer - a.steer) * k, done: i >= f.length - 1 };
  }
}

// ---------------------------------------------------------------- codec
// Planar layout for good gzip ratios:
//   header: float64 x0, y0, z0
//   int32 deltas of x, y, z in millimetres (3 planes)
//   int16 quaternion components * 32767 (4 planes) + int16 steer * 10000

async function gzip(bytes: Uint8Array): Promise<Uint8Array> {
  const cs = new CompressionStream('gzip');
  const stream = new Blob([bytes as BlobPart]).stream().pipeThrough(cs);
  return new Uint8Array(await new Response(stream).arrayBuffer());
}

async function gunzip(bytes: Uint8Array): Promise<Uint8Array> {
  const ds = new DecompressionStream('gzip');
  const stream = new Blob([bytes as BlobPart]).stream().pipeThrough(ds);
  return new Uint8Array(await new Response(stream).arrayBuffer());
}

function toBase64(bytes: Uint8Array) {
  let s = '';
  for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(s);
}

function fromBase64(b64: string) {
  const s = atob(b64);
  const out = new Uint8Array(s.length);
  for (let i = 0; i < s.length; i++) out[i] = s.charCodeAt(i);
  return out;
}

export async function encodeGhost(g: GhostData): Promise<EncodedGhost> {
  const n = g.frames.length;
  const buf = new ArrayBuffer(24 + n * 3 * 4 + n * 5 * 2);
  const dv = new DataView(buf);
  const f0 = g.frames[0] ?? { x: 0, y: 0, z: 0 };
  dv.setFloat64(0, f0.x, true);
  dv.setFloat64(8, f0.y, true);
  dv.setFloat64(16, f0.z, true);
  let o = 24;
  const comps: ('x' | 'y' | 'z')[] = ['x', 'y', 'z'];
  const base = [f0.x, f0.y, f0.z];
  comps.forEach((c, ci) => {
    let prev = 0;
    for (let i = 0; i < n; i++) {
      const v = Math.round((g.frames[i][c] - base[ci]) * 1000);
      dv.setInt32(o, v - prev, true);
      prev = v;
      o += 4;
    }
  });
  for (const c of ['qx', 'qy', 'qz', 'qw'] as const) {
    for (let i = 0; i < n; i++) {
      dv.setInt16(o, Math.round(Math.max(-1, Math.min(1, g.frames[i][c])) * 32767), true);
      o += 2;
    }
  }
  for (let i = 0; i < n; i++) {
    dv.setInt16(o, Math.round(Math.max(-3, Math.min(3, g.frames[i].steer)) * 10000), true);
    o += 2;
  }
  const z = await gzip(new Uint8Array(buf));
  return { format: GHOST_FORMAT, interval_ms: g.intervalMs, frame_count: n, data: toBase64(z) };
}

export async function decodeGhost(e: EncodedGhost): Promise<GhostData> {
  if (e.format !== GHOST_FORMAT) throw new Error(`Unsupported ghost format ${e.format}`);
  const raw = await gunzip(fromBase64(e.data));
  const dv = new DataView(raw.buffer, raw.byteOffset, raw.byteLength);
  const n = e.frame_count;
  if (raw.byteLength !== 24 + n * 3 * 4 + n * 5 * 2) throw new Error('Corrupt ghost data');
  const base = [dv.getFloat64(0, true), dv.getFloat64(8, true), dv.getFloat64(16, true)];
  const frames: GhostFrame[] = Array.from({ length: n }, () => ({ x: 0, y: 0, z: 0, qx: 0, qy: 0, qz: 0, qw: 1, steer: 0 }));
  let o = 24;
  (['x', 'y', 'z'] as const).forEach((c, ci) => {
    let acc = 0;
    for (let i = 0; i < n; i++) {
      acc += dv.getInt32(o, true);
      frames[i][c] = base[ci] + acc / 1000;
      o += 4;
    }
  });
  for (const c of ['qx', 'qy', 'qz', 'qw'] as const) {
    for (let i = 0; i < n; i++) {
      frames[i][c] = dv.getInt16(o, true) / 32767;
      o += 2;
    }
  }
  for (let i = 0; i < n; i++) {
    frames[i].steer = dv.getInt16(o, true) / 10000;
    o += 2;
  }
  return { intervalMs: e.interval_ms, frames };
}
