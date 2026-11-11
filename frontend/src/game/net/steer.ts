import { PHYSICS_DT } from '../vehicle/PhysicsWorld';

type V3 = [number, number, number];

/** what a stand-in remembers between physics steps */
export interface SteerMemory {
  /** velocity it was told to have at the last step, where the path had the car at the end of that step, and whether there was one */
  cmd: V3;
  aim: V3;
  primed: boolean;
  /** after a gap in time: how far the path moved in the time skipped (the body is moved by as much) */
  shift: V3;
  /** what hits have added to its velocity and has not died away yet */
  push: V3;
}

export const newSteerMemory = (): SteerMemory => ({ cmd: [0, 0, 0], aim: [0, 0, 0], primed: false, shift: [0, 0, 0], push: [0, 0, 0] });

/** a hit's momentum survives for about this long (s) */
const PUSH_TAU = 0.15;
const KEEP = Math.exp(-PHYSICS_DT / PUSH_TAU);
/** pull back onto the network's path: rate (1/s) and the most it may add (m/s) */
const PULL = 3;
const PULL_MAX = 8;

/**
 * The velocity a stand-in is given for one physics step (pure numbers: `ProxyCar` applies it to the body).
 *
 * `pos`, `vel`: the body now (its velocity as the solver left it); `target`, `targetVel`: where the network's path
 * has the car at the end of this step, and how fast; `dt`: the step. All velocities in the physics world's own
 * seconds. The body is moved by exactly what the path moves in this step, so without a hit it stays on the path
 * with no lag at all when the car brakes or turns (blending towards the reported velocity trailed by a metre in a
 * hard corner). Whatever the solver changed since the last command is a hit: that part is kept and dies away over
 * `PUSH_TAU` (both cars get shoved), while a soft pull brings the body back onto the path.
 *
 * `gap`: this step does not follow the last one in time (a stalled frame, a client too slow to keep its physics in
 * real time), so the path has moved further than one step's worth. The body must not be flung after it: the caller
 * moves it by `m.shift` first (what the path did in the time skipped), and the velocity returned takes it on from
 * there. The caller knows a gap by the clock, not by the path: a crash changes a car's velocity by more in one
 * packet than a skipped frame does.
 */
export function steerProxy(m: SteerMemory, pos: ArrayLike<number>, vel: ArrayLike<number>, target: ArrayLike<number>, targetVel: ArrayLike<number>, dt: number, out: V3, gap = false) {
  const e: V3 = [0, 0, 0], ff: V3 = [0, 0, 0];
  let len = 0;
  for (let i = 0; i < 3; i++) {
    if (m.primed) m.push[i] += vel[i] - m.cmd[i];
    // where the path had the car when this step began
    const from = m.primed && !gap ? m.aim[i] : target[i] - targetVel[i] * dt;
    m.shift[i] = m.primed && gap ? from - m.aim[i] : 0;
    ff[i] = (target[i] - from) / dt;
    // (how far hits have pushed the body off the path: the same before and after a shift)
    e[i] = (m.primed ? m.aim[i] : from) - pos[i];
    len += e[i] * e[i];
    m.aim[i] = target[i];
  }
  const k = Math.min(PULL, PULL_MAX / Math.max(0.5, Math.sqrt(len)));
  for (let i = 0; i < 3; i++) {
    m.push[i] *= KEEP;
    out[i] = m.cmd[i] = ff[i] + e[i] * k + m.push[i];
  }
  m.primed = true;
}
