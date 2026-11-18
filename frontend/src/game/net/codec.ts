/**
 * What a client sends about its car while racing (~25 times a second), and its wire form: one flat array of
 * integers. Reverb takes a client event's `data` only as a JSON array or object and re-encodes it in PHP on the
 * way through, so whole numbers are the one form that arrives exactly as sent; a WebRTC DataChannel can carry the
 * same array.
 */
export interface NetState {
  /** counts up by one per packet (16 bit, wraps): the receiver sees losses as gaps */
  seq: number;
  /** sender clock when the packet left (ms, performance.now) */
  t: number;
  /** how old the physics state already was then (ms): the pose is the car at `t - age` */
  age: number;
  /** body position (m) and orientation */
  p: [number, number, number];
  q: [number, number, number, number];
  /** velocity (m/s) and acceleration (m/s², smoothed), world frame, per wall-clock second */
  vel: [number, number, number];
  acc: [number, number, number];
  /** angular velocity (rad/s, world frame): the yaw rate above all, and the pitch and roll of crests and banked bends */
  w: [number, number, number];
  /** front wheel steer angle (rad) */
  st: number;
  /** progress along the course (m) and braking flag */
  s: number;
  br: 0 | 1;
  /** counts the sender's respawns (2 bit, wraps): a new value means the car was moved, not driven, to its place */
  ep: number;
  /**
   * a fighter's take-off after the finish (`race/Departure.ts`; 2 bit): 1 = off its wheels' simulation (the nose
   * coming up, in the air), 2 = the gear going up, 3 = gone. From 1 on nobody can touch it.
   */
  dep?: number;
  /**
   * a tank's turret bearing relative to its hull (rad, + = left) and its gun's elevation (rad): how the others see
   * it aim. They ride in the spare bits of the flags' number (12 bits: 0.09°; 8 bits: 0.25°, ±32°), so the packet
   * keeps its length and every other vehicle's packet is what it was.
   */
  tu?: number;
  gp?: number;
  /** throttle and engine speed as a share of the redline (for the exhaust) */
  th: number;
  rp: number;
  /** finish time (ms) once across the line */
  fin?: number;
  /**
   * Clock exchange riding on the state stream (as RTCP's LSR/DLSR): "the last packet I had from player `id` was
   * stamped `t` on their clock, and I have held it for `hold` ms". Each packet answers one peer, in turn.
   */
  echo?: { id: number; t: number; hold: number };
}

/** first number of every packet: other layouts (an older build still open in a tab) are dropped, not misread */
export const NET_VERSION = 2;
export const SEQ_MOD = 65536;
const FIXED = 26;

/** Signed distance from sequence number `b` to `a` across the wrap (> 0: `a` is newer). */
export function seqDelta(a: number, b: number) {
  return ((((a - b) % SEQ_MOD) + SEQ_MOD + SEQ_MOD / 2) % SEQ_MOD) - SEQ_MOD / 2;
}

/** the turret's bearing in 12 bits and the gun's elevation in 8 (two's complement), above the flags' five bits */
export const TURRET_STEP = (2 * Math.PI) / 4096;
export const GUN_STEP = (0.25 * Math.PI) / 180;
const aimBits = (tu: number, gp: number) => {
  const yaw = ((Math.round(tu / TURRET_STEP) % 4096) + 4096) % 4096;
  const pitch = Math.max(-128, Math.min(127, Math.round(gp / GUN_STEP))) & 255;
  // (not a shift: the number stays a plain whole number whatever the engine's integer width)
  return yaw * 32 + pitch * 131072;
};

/** mm, 1e-4 of a quaternion component, cm/s, mrad/s, cm/s², 0.1 ms: finer than anything the receiver can show */
export function encodeState(s: NetState): number[] {
  const r = Math.round;
  const out = [
    NET_VERSION, s.seq % SEQ_MOD, r(s.t * 10), r(s.age * 10),
    r(s.p[0] * 1e3), r(s.p[1] * 1e3), r(s.p[2] * 1e3),
    r(s.q[0] * 1e4), r(s.q[1] * 1e4), r(s.q[2] * 1e4), r(s.q[3] * 1e4),
    r(s.vel[0] * 100), r(s.vel[1] * 100), r(s.vel[2] * 100),
    r(s.acc[0] * 100), r(s.acc[1] * 100), r(s.acc[2] * 100),
    r(s.w[0] * 1e3), r(s.w[1] * 1e3), r(s.w[2] * 1e3),
    r(s.st * 1e3), r(s.s * 10), (s.br ? 1 : 0) | ((s.ep & 3) << 1) | (((s.dep ?? 0) & 3) << 3) | aimBits(s.tu ?? 0, s.gp ?? 0),
    r(s.th * 100), r(s.rp * 100), s.fin === undefined ? -1 : r(s.fin),
  ];
  if (s.echo) out.push(s.echo.id, r(s.echo.t * 10), r(s.echo.hold * 10));
  return out;
}

/** The packet, or null for anything that is not one (wrong layout, a hole, not a number). */
export function decodeState(a: unknown): NetState | null {
  if (!Array.isArray(a) || (a.length !== FIXED && a.length !== FIXED + 3) || a[0] !== NET_VERSION) return null;
  for (const x of a) if (typeof x !== 'number' || !Number.isFinite(x)) return null;
  const n = a as number[];
  // a quaternion rounded to 1e-4 is no longer unit length
  const ql = Math.hypot(n[7], n[8], n[9], n[10]);
  if (ql < 1) return null;
  const st: NetState = {
    seq: n[1], t: n[2] / 10, age: n[3] / 10,
    p: [n[4] / 1e3, n[5] / 1e3, n[6] / 1e3],
    q: [n[7] / ql, n[8] / ql, n[9] / ql, n[10] / ql],
    vel: [n[11] / 100, n[12] / 100, n[13] / 100],
    acc: [n[14] / 100, n[15] / 100, n[16] / 100],
    w: [n[17] / 1e3, n[18] / 1e3, n[19] / 1e3],
    st: n[20] / 1e3, s: n[21] / 10, br: (n[22] & 1) as 0 | 1, ep: (n[22] >> 1) & 3,
    th: n[23] / 100, rp: n[24] / 100,
  };
  if ((n[22] >> 3) & 3) st.dep = (n[22] >> 3) & 3;
  const yaw = (n[22] >> 5) & 4095, pitch = (n[22] >> 17) & 255;
  if (yaw || pitch) {
    st.tu = (yaw >= 2048 ? yaw - 4096 : yaw) * TURRET_STEP;
    st.gp = (pitch >= 128 ? pitch - 256 : pitch) * GUN_STEP;
  }
  if (n[25] >= 0) st.fin = n[25];
  if (n.length === FIXED + 3 && n[26] > 0) st.echo = { id: n[26], t: n[27] / 10, hold: n[28] / 10 };
  return st;
}
