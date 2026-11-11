import { Quaternion, Vector3 } from 'three';
import { ClockSync } from './clock';
import type { NetState } from './codec';
import { ArrivalStats } from './stats';
import { newPose, PeerTrack, type TrackPose } from './PeerTrack';

/**
 * When a peer's car is shown: `present` = where it is now (the newest packet carried on over the time it took to
 * get here), `buffered` = where it was one buffer delay ago (`ArrivalStats.bufferDelay`), between two packets.
 * Races use `present`: the cars are solid, and two players only see the same bump at the same moment if each
 * screen shows the other car where it is now, not where it was (at 180 km/h a 130 ms buffer is 6.5 m of road).
 */
export type LagMode = 'present' | 'buffered';

/** The numbers of one peer's link, for the in-race readout and the replay tool. */
export interface PeerNetStats {
  id: number;
  /** round trip (ms): smoothed, the shortest of the last seconds; false until a clock exchange has completed */
  rtt: number;
  rttMin: number;
  synced: boolean;
  /** their clock − ours (ms) */
  offset: number;
  /** ms between packets, packets per second, jitter (ms) */
  interval: number;
  rate: number;
  jitter: number;
  /** share lost of the last seconds (0…1), and the counts since the start */
  loss: number;
  lost: number;
  late: number;
  received: number;
  /** the buffer delay this link would need (ms), and how far behind the present the car is drawn (ms; 0 = present) */
  bufferDelay: number;
  lag: number;
  /** share of the last frames drawn past the newest packet (0…1), and how far past on average (ms) */
  ahead: number;
  horizon: number;
  /** how far a new packet moved the predicted position (m): mean and largest of the last ones; jumps taken at once */
  correction: number;
  correctionMax: number;
  snaps: number;
}

/** a correction is spread over about this long: a critically damped spring of this rate (1/s) */
const SETTLE = 18;
/** further than this the car is not eased over but put there (a respawn seen late, a long stall) */
const SNAP = 8;
/** the buffered mode's delay follows the measured one with this time constant (ms), so the picture is not warped */
const LAG_TAU = 1000;

const _before = newPose(), _after = newPose();
const _e = new Vector3(), _qe = new Quaternion(), _id = new Quaternion();

/**
 * Everything known about one peer's car from its packets, free of the DOM (the replay tool runs it in Node):
 * the clock offset, the arrival statistics, the path, and the pose to show at a moment of our clock. A new
 * packet rarely agrees with the prediction made from the older ones; the difference is not shown as a jump but
 * kept as an error that dies away smoothly. The position shown stays continuous; the velocity takes the packet's
 * at once (holding on to the old one as well measured worse: after a crash it carried the car on into the wall).
 */
export class PeerReceiver {
  readonly clock = new ClockSync();
  readonly arrivals = new ArrivalStats();
  readonly track = new PeerTrack();
  mode: LagMode = 'present';
  /** our clock at the newest packet's arrival (ms; 0 = none yet), and that packet's stamp on their clock */
  lastHeard = 0;
  lastStamp = 0;
  /** the car was put somewhere (respawn, stall): whoever consumes the pose clears this after acting on it */
  jumped = false;
  /** how far behind the present the car is drawn (ms) */
  lag = 0;
  // the error still to be eased away: value and rate at `errAt` (ms, our clock), and the same for the orientation
  private e0 = new Vector3();
  private de0 = new Vector3();
  private q0 = new Quaternion();
  private errAt = 0;
  // statistics: totals for the tools, smoothed values for the readout
  frames = 0;
  aheadFrames = 0;
  aheadSum = 0;
  snaps = 0;
  readonly corrections: number[] = [];
  private aheadShare = 0;
  private horizon = 0;

  constructor(readonly id: number) {}

  /**
   * A packet from this peer, arrived at `arrival` (ms, our clock). `selfId`: our player id (an echo addressed to
   * us completes a clock exchange). False when the packet was late or a duplicate.
   */
  receive(st: NetState, arrival: number, selfId: number) {
    // (what is on screen now, before this packet changes the clock or the path)
    const had = this.track.length > 0 && this.display(arrival, _before);
    const respawned = this.track.newest !== null && this.track.newest.ep !== st.ep;
    // a late packet's stamps are as good as any for the clock; its pose is not wanted any more
    this.clock.heard(st.t, arrival);
    if (st.echo && st.echo.id === selfId) this.clock.sample(st.echo.t, st.t - st.echo.hold, st.t, arrival);
    if (!this.arrivals.note(st.seq, st.t - this.clock.offset, arrival)) return false;
    this.lastHeard = arrival;
    this.lastStamp = st.t;
    if (!this.track.push(st)) return false;
    if (!had || !this.raw(arrival, _after)) return true;
    // the error to ease away is whatever keeps the shown pose where it was; the correction itself is how far the
    // prediction moved, i.e. that without the error that was still left
    this.errAtTime(arrival, _e);
    const size = _after.position.distanceTo(_before.position.clone().sub(_e));
    if (respawned || _before.position.distanceTo(_after.position) > SNAP) {
      this.e0.set(0, 0, 0);
      this.de0.set(0, 0, 0);
      this.q0.identity();
      this.jumped = true;
      this.snaps++;
    } else {
      // (the rate first: it is read from the old curve)
      this.errRate(arrival, this.de0);
      this.e0.subVectors(_before.position, _after.position);
      this.q0.copy(_before.quaternion).multiply(_qe.copy(_after.quaternion).invert());
      this.corrections.push(size);
      if (this.corrections.length > 4096) this.corrections.splice(0, 2048);
    }
    this.errAt = arrival;
    return true;
  }

  /** Once per frame: the clock offset and the buffer delay move slowly towards their estimates. */
  tick(dtMs: number) {
    this.clock.tick(dtMs);
    const want = this.mode === 'buffered' ? this.arrivals.bufferDelay : 0;
    this.lag += (want - this.lag) * (1 - Math.exp(-Math.max(0, dtMs) / LAG_TAU));
  }

  /** The pose to show at `local` (ms, our clock): the path's, plus what is left of the last corrections. */
  display(local: number, out: TrackPose) {
    if (!this.raw(local, out)) return false;
    const tau = Math.max(0, (local - this.errAt) / 1000);
    const f = Math.exp(-SETTLE * tau);
    if (f > 1e-4) {
      out.position.add(this.errAtTime(local, _e));
      out.velocity.add(this.errRate(local, _e));
      out.quaternion.premultiply(_qe.copy(_id).slerp(this.q0, f));
    }
    return true;
  }

  /** The path alone, without the easing. */
  raw(local: number, out: TrackPose) {
    return this.track.sample(this.clock.toRemote(local) - this.lag, out);
  }

  /** Statistics of a drawn frame (call once per rendered frame with the pose shown). */
  countFrame(pose: TrackPose) {
    this.frames++;
    if (pose.ahead > 0) this.aheadFrames++;
    this.aheadSum += pose.ahead;
    this.aheadShare += ((pose.ahead > 0 ? 1 : 0) - this.aheadShare) / 120;
    this.horizon += (pose.ahead * 1000 - this.horizon) / 120;
  }

  stats(): PeerNetStats {
    const a = this.arrivals, c = this.corrections.slice(-256);
    return {
      id: this.id,
      rtt: this.clock.rtt, rttMin: this.clock.rttMin, synced: this.clock.synced, offset: this.clock.offset,
      interval: a.interval, rate: a.rate, jitter: a.jitter,
      loss: a.lossRecent, lost: a.lost, late: a.late, received: a.received,
      bufferDelay: a.bufferDelay, lag: this.lag,
      ahead: this.aheadShare, horizon: this.horizon,
      correction: c.length ? c.reduce((s, x) => s + x, 0) / c.length : 0,
      correctionMax: c.length ? Math.max(...c) : 0,
      snaps: this.snaps,
    };
  }

  // e(τ) = (e0 + (de0 + ω e0) τ) exp(−ω τ): critically damped, so it neither overshoots nor starts with a kick
  private errAtTime(local: number, out: Vector3) {
    const tau = Math.max(0, (local - this.errAt) / 1000);
    return out.copy(this.de0).addScaledVector(this.e0, SETTLE).multiplyScalar(tau).add(this.e0).multiplyScalar(Math.exp(-SETTLE * tau));
  }

  private errRate(local: number, out: Vector3) {
    const tau = Math.max(0, (local - this.errAt) / 1000);
    const k = -SETTLE * tau;
    // d/dτ of the above: (de0 − ω (de0 + ω e0) τ) exp(−ω τ)
    const dx = this.de0.x + k * (this.de0.x + SETTLE * this.e0.x), dy = this.de0.y + k * (this.de0.y + SETTLE * this.e0.y), dz = this.de0.z + k * (this.de0.z + SETTLE * this.e0.z);
    return out.set(dx, dy, dz).multiplyScalar(Math.exp(-SETTLE * tau));
  }
}
