import { Vector3 } from 'three';
import { GRAVITY } from '../weapons/gun';
import { SHELL_LIFE } from '../weapons/ballistics';
import type { GunInfo } from '../vehicle/tanks';

/**
 * A tank's shots and hits between the players of an online race: client events on the room's presence channel
 * (`client-gun`; `store/online.ts` picks the event's name by an array's first number), whole numbers only as the
 * car states (`codec.ts`: Reverb re-encodes JSON in PHP), relayed by the server with the sender's player id and
 * nothing else: **the server judges nothing, every receiver does** (`GunReferee`).
 *
 * Who decides a hit: **the firer's game**. Its shell is simulated there against the other vehicles as that
 * screen has them (drawn in the present, `PeerTrack`), and when it meets one the firer says so (`hit`). The
 * vehicle hit puts itself back on the road when it hears that (what its own R key does), after checking that the
 * claim can be true. That is the honest simple choice: the firer sees what it aimed at being hit, nobody waits a
 * round trip for it, and at the latencies the game runs with (tens of ms) the two screens differ by less than a
 * car's length for most shots. Its price: a member with a changed client could claim hits; the checks below bound
 * what such a claim can do (no faster than the gun loads, only along a shot's own path, only near where the
 * victim is).
 *
 *   shot  [GUN_EVENT, 1, n, t, px, py, pz, vx, vy, vz]   n: the firer's shot number (1…), t: its clock (0.1 ms),
 *                                                        muzzle (mm) and the shell's velocity there (cm/s)
 *   hit   [GUN_EVENT, 2, n, target, px, py, pz]          shot n met the member `target` (player id) at p (mm)
 */
export const GUN_EVENT = 71;

export interface ShotEvent {
  kind: 'shot';
  n: number;
  /** the firer's clock when the round left (ms, performance.now) */
  t: number;
  p: [number, number, number];
  v: [number, number, number];
}

export interface HitEvent {
  kind: 'hit';
  n: number;
  /** player id of the member whose vehicle was met */
  target: number;
  p: [number, number, number];
}

export type GunEvent = ShotEvent | HitEvent;

export function encodeGunEvent(e: GunEvent): number[] {
  const r = Math.round;
  if (e.kind === 'shot') return [GUN_EVENT, 1, e.n, r(e.t * 10), r(e.p[0] * 1e3), r(e.p[1] * 1e3), r(e.p[2] * 1e3), r(e.v[0] * 100), r(e.v[1] * 100), r(e.v[2] * 100)];
  return [GUN_EVENT, 2, e.n, e.target, r(e.p[0] * 1e3), r(e.p[1] * 1e3), r(e.p[2] * 1e3)];
}

/** Is this array one of ours at all (whatever is in it)? The link hands such arrays to the game, not to the car states. */
export const isGunEvent = (a: unknown): a is number[] => Array.isArray(a) && a[0] === GUN_EVENT;

/** The event, or null for anything that is not one (another layout, a hole, not a whole number, a number out of range). */
export function decodeGunEvent(a: unknown): GunEvent | null {
  if (!isGunEvent(a) || (a.length !== 10 && a.length !== 7)) return null;
  for (const x of a) if (typeof x !== 'number' || !Number.isInteger(x) || Math.abs(x) > 1e12) return null;
  const n = a as number[];
  if (n[2] < 1 || n[2] > 9999) return null;
  if (n[1] === 1 && n.length === 10) return { kind: 'shot', n: n[2], t: n[3] / 10, p: [n[4] / 1e3, n[5] / 1e3, n[6] / 1e3], v: [n[7] / 100, n[8] / 100, n[9] / 100] };
  if (n[1] === 2 && n.length === 7 && n[3] > 0) return { kind: 'hit', n: n[2], target: n[3], p: [n[4] / 1e3, n[5] / 1e3, n[6] / 1e3] };
  return null;
}

/** a shot is believed this far from where we have its vehicle (m): the turret's reach plus what a bad link adds */
const MUZZLE_SLACK = 45;
/** the shell's speed may differ from the gun's muzzle velocity by the hull's own speed and this much (m/s) */
const SPEED_SLACK = 45;
/** two shots of one gun are believed this much closer together than its loading time (ms): the link's jitter */
const RATE_SLACK = 600;
/** an impact is believed this far off the shot's own path (m): half a vehicle, and what the rounding adds */
const PATH_SLACK = 8;
/** … and this far from where the victim's vehicle is now, plus what it covers in `MOVE_TIME` s */
const NEAR_SLACK = 12;
const MOVE_TIME = 0.6;
/** a hit may come this much before the shell could have arrived (ms): the two events' own jitter */
const EARLY_SLACK = 350;

interface Heard {
  n: number;
  at: number;
  p: Vector3;
  v: Vector3;
  k: number;
  used: boolean;
}

const _p = new Vector3(), _v = new Vector3();

/**
 * The receiving end's judgement of what the others say about their guns. One per race; `gunOf(id)` gives a
 * member's gun (null: not a member of this race, or not in a tank: nothing from them counts).
 */
export class GunReferee {
  /** per member: its shots heard lately (the newest last) */
  private heard = new Map<number, Heard[]>();
  /** counted for the readout and the tests */
  refused = 0;

  constructor(private gunOf: (id: number) => GunInfo | null) {}

  clear() {
    this.heard.clear();
    this.refused = 0;
  }

  /**
   * A shot heard from `from` at `now` (ms, our clock); `at`: where we have that member's vehicle (null: not
   * known yet). True: it may be shown and its hits may count.
   */
  shot(from: number, e: ShotEvent, now: number, at: Vector3 | null): boolean {
    const gun = this.gunOf(from);
    if (!gun) return this.no();
    let list = this.heard.get(from);
    if (!list) this.heard.set(from, (list = []));
    const last = list[list.length - 1];
    // the shots count up, no more of them than the gun has rounds, no faster than it loads
    if (e.n > gun.ammo || (last && (e.n <= last.n || now - last.at < gun.reload * 1000 - RATE_SLACK))) return this.no();
    const speed = Math.hypot(e.v[0], e.v[1], e.v[2]);
    if (Math.abs(speed - gun.muzzleVelocity) > SPEED_SLACK) return this.no();
    _p.set(e.p[0], e.p[1], e.p[2]);
    if (at && _p.distanceTo(at) > MUZZLE_SLACK) return this.no();
    list.push({ n: e.n, at: now, p: _p.clone(), v: new Vector3(e.v[0], e.v[1], e.v[2]), k: gun.dropPerKm / 1000 / gun.muzzleVelocity, used: false });
    if (list.length > 4) list.shift();
    return true;
  }

  /**
   * A hit heard from `from` at `now`. True: the claim can be true (a shot of theirs we heard, not yet used, whose
   * path runs through the point, not before the shell could be there). Whether it is OUR vehicle and near the
   * point is `mine`'s question.
   */
  hit(from: number, e: HitEvent, now: number): boolean {
    const shot = this.heard.get(from)?.find((s) => s.n === e.n);
    if (!this.gunOf(from) || !shot || shot.used) return this.no();
    // the shot's path without the world (gravity and drag as the shell's), until it is nearest the point
    _p.copy(shot.p);
    _v.copy(shot.v);
    const dt = 1 / 240;
    let best = Infinity, when = 0;
    for (let t = 0; t < SHELL_LIFE; t += dt) {
      const d = Math.hypot(_p.x - e.p[0], _p.y - e.p[1], _p.z - e.p[2]);
      if (d < best) {
        best = d;
        when = t;
      } else if (d > best + 50) break;
      const loss = Math.exp(-shot.k * _v.length() * dt);
      _p.addScaledVector(_v, dt);
      _v.multiplyScalar(loss);
      _v.y -= GRAVITY * dt;
    }
    if (best > PATH_SLACK || now - shot.at < when * 1000 - EARLY_SLACK || now - shot.at > (SHELL_LIFE + 2) * 1000) return this.no();
    shot.used = true;
    return true;
  }

  /** Is a hit that `hit()` believed one on our own vehicle: named for us, and where we are? */
  mine(e: HitEvent, selfId: number, position: Vector3, speed: number): boolean {
    if (e.target !== selfId) return false;
    if (Math.hypot(position.x - e.p[0], position.y - e.p[1], position.z - e.p[2]) > NEAR_SLACK + speed * MOVE_TIME) return this.no();
    return true;
  }

  private no() {
    this.refused++;
    return false;
  }
}
