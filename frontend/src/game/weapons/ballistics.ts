import { Vector3 } from 'three';
import { GRAVITY } from './gun';

/**
 * Shells in flight, DOM-free and stepped with the physics (120 Hz): gravity, a drag that takes the same share of
 * the speed every metre (`GunInfo.dropPerKm`), and at every step the whole stretch flown is asked of the world
 * (`ShellWorld.cast`), so nothing is flown through between two steps (a round covers 14 m in one).
 */
export interface Shell {
  /** the firer (0: the local player; online: the member's id) and the shot's number of that firer */
  owner: number;
  shot: number;
  p: Vector3;
  v: Vector3;
  /** drag (1/m) */
  k: number;
  /** seconds and metres flown */
  age: number;
  flown: number;
  /** where it was a step ago (the picture draws between the two) */
  prev: Vector3;
}

/** what a shell can hit: a vehicle (its key in the game: `RIVAL`, a member's id) or the ground (null) */
export type ShellTarget = number | null;
/** the rival of a single-player battle as a target */
export const RIVAL = -1;

export interface ShellWorld {
  /**
   * The first thing on the way from `from` along the unit vector `dir`, at most `len` m away: how far, and what
   * (a vehicle's key, or null for the ground). Null: nothing. `owner`: whose shell it is (never hits its own gun).
   */
  cast(from: Vector3, dir: Vector3, len: number, owner: number): { t: number; target: ShellTarget } | null;
}

export interface Impact {
  shell: Shell;
  point: Vector3;
  target: ShellTarget;
}

/** a shell is taken away after this long (s) or this far (m), whatever it met: beyond every course */
export const SHELL_LIFE = 6;
export const SHELL_REACH = 6000;

const _step = new Vector3(), _dir = new Vector3();

export function newShell(owner: number, shot: number, p: Vector3, v: Vector3, k: number): Shell {
  return { owner, shot, p: p.clone(), v: v.clone(), k, age: 0, flown: 0, prev: p.clone() };
}

/**
 * One step of one shell. Returns what it met (the shell stands at that point then), or null: flown on, or spent
 * (`spent(shell)`).
 */
export function stepShell(s: Shell, dt: number, world: ShellWorld, out: Impact): Impact | null {
  const speed = s.v.length();
  // the step's own stretch: the velocity at its middle (drag and gravity for half the step)
  const loss = Math.exp(-s.k * speed * dt);
  _step.copy(s.v).multiplyScalar((1 + loss) / 2);
  _step.y -= GRAVITY * dt * 0.5;
  _step.multiplyScalar(dt);
  const len = _step.length();
  s.prev.copy(s.p);
  if (len > 1e-9) {
    const hit = world.cast(s.p, _dir.copy(_step).divideScalar(len), len, s.owner);
    if (hit) {
      s.p.addScaledVector(_dir, hit.t);
      s.flown += hit.t;
      s.age += dt * (hit.t / len);
      out.shell = s;
      out.point.copy(s.p);
      out.target = hit.target;
      return out;
    }
  }
  s.p.add(_step);
  s.v.multiplyScalar(loss);
  s.v.y -= GRAVITY * dt;
  s.flown += len;
  s.age += dt;
  return null;
}

export const spent = (s: Shell) => s.age >= SHELL_LIFE || s.flown >= SHELL_REACH;

/** Every shell in the air. */
export class Shells {
  readonly live: Shell[] = [];
  private impact: Impact = { shell: null as unknown as Shell, point: new Vector3(), target: null };

  add(shell: Shell) {
    this.live.push(shell);
    return shell;
  }

  /** One physics step of all of them; `onImpact` hears of each that met something (it is gone after the call). */
  step(dt: number, world: ShellWorld, onImpact: (impact: Impact) => void) {
    const live = this.live;
    for (let i = live.length - 1; i >= 0; i--) {
      const hit = stepShell(live[i], dt, world, this.impact);
      if (hit) onImpact(hit);
      if (hit || spent(live[i])) live.splice(i, 1);
    }
  }

  clear() {
    this.live.length = 0;
  }
}
