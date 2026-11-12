import { Vector3 } from 'three';
import type { PeerReceiver } from './PeerReceiver';
import type { TrackPose } from './PeerTrack';
import { PHYSICS_DT } from '../vehicle/PhysicsWorld';
import type { ProxyCar } from './ProxyCar';

const _v = new Vector3();
/** a peer not heard from for this long (ms) stops being solid: its car is no longer there on its own screen either */
const SILENT_MS = 2000;

/**
 * One peer's car between its packets (`PeerReceiver`) and what the game does with it: the solid stand-in steered
 * at each physics step, the pose drawn each frame. Free of the DOM and of the car models, so the replay tool
 * (tools/net-replay.ts) runs exactly this.
 */
export class RemoteBody {
  /** physical stand-in (online contact); the picture adds how far hits have pushed it off the path */
  proxy: ProxyCar | null = null;
  private pose: TrackPose;
  /** the moment the last physics step ended at (ms, our clock) */
  private steppedAt = NaN;

  constructor(readonly rx: PeerReceiver, scratch: TrackPose) {
    this.pose = scratch;
  }

  /**
   * Physics step: steer the stand-in to where the car is at `at` (ms, our clock), the moment this step ends at;
   * `now` is the frame's time (ghosting). The local car's state after the step is of that same moment, so the two
   * meet where and when they do on the other player's screen. `timeScale`: the physics world's seconds per
   * wall-clock second (packets speak in the latter).
   */
  step(at: number, now: number, localCar: Vector3 | null, timeScale = 1) {
    const proxy = this.proxy, rx = this.rx, pose = this.pose;
    if (!proxy) return;
    proxy.updateGhost(now, localCar);
    // steps that do not follow each other in time: a stalled frame, or physics that cannot keep up with the clock
    const due = (PHYSICS_DT * 1000) / timeScale;
    const gap = Math.abs(at - this.steppedAt - due) > due / 2;
    this.steppedAt = at;
    // (no packet yet: parked on its grid place)
    if (!rx.display(at, pose)) return;
    if (rx.jumped) {
      rx.jumped = false;
      proxy.teleport(pose.position, pose.quaternion, now);
      return;
    }
    if (now - rx.lastHeard > SILENT_MS) proxy.ghost(now + 500);
    // a fighter taking off is no longer on the ground on its own screen: nothing can touch it from here on
    if (pose.depart) proxy.ghost(now + 500);
    proxy.drive(pose.position, pose.quaternion, pose.velocity.multiplyScalar(1 / timeScale), now, gap);
  }

  /**
   * Per frame: the pose to draw at `at` (ms, our clock), `wallMs` after the last frame. False while nothing has
   * been heard (the car stays parked).
   */
  frame(at: number, wallMs: number, out: TrackPose) {
    const rx = this.rx;
    rx.tick(wallMs);
    if (!rx.display(at, out)) return false;
    rx.countFrame(out);
    if (this.proxy) out.position.add(this.proxy.shove(_v));
    else rx.jumped = false;
    return true;
  }
}
