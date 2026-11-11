/**
 * The other player's clock against ours, the NTP way: four timestamps of one exchange (ours out, theirs in,
 * theirs out, ours in) give the round trip and, if both directions take equally long, the offset. The exchange
 * rides on the car states themselves (`NetState.echo`), peer to peer over whatever carries them: Reverb has no
 * time source of its own (its `pusher:ping` answers without a timestamp), a server clock would describe the HTTP
 * path instead of the one the states take, and the same exchange keeps working over a direct connection.
 *
 * Of the last exchanges the one with the shortest round trip is believed (it had the least queueing, so the
 * least asymmetry); after the first few, the offset in use moves there slowly, since every millisecond of it moves
 * a car at 200 km/h by 6 cm.
 */
export class ClockSync {
  /** their clock − ours (ms), the value in use */
  offset = 0;
  /** an exchange has completed (before that the offset assumes a network without delay) */
  synced = false;
  /** round trip (ms): smoothed, and of the exchange believed */
  rtt = 0;
  rttMin = 0;
  private target = 0;
  private taken = 0;
  private samples: { rtt: number; offset: number; at: number }[] = [];
  /** before the first exchange: the largest (their stamp − our arrival) seen, i.e. the fastest packet */
  private floor = -Infinity;

  /** Every packet, before any exchange: without a round trip the best guess is that the fastest packet took no time. */
  heard(theirSend: number, ourArrival: number) {
    if (this.synced) return;
    this.floor = Math.max(this.floor, theirSend - ourArrival);
    this.offset = this.target = this.floor;
  }

  /**
   * One exchange: `t0` our send, `t1` their arrival, `t2` their send, `t3` our arrival (t0, t3 on our clock; t1, t2
   * on theirs). Returns false for one that cannot be (a negative round trip: a stale or forged echo).
   */
  sample(t0: number, t1: number, t2: number, t3: number) {
    const rtt = t3 - t0 - (t2 - t1);
    if (!(rtt >= 0) || rtt > 5000) return false;
    const offset = (t1 - t0 + (t2 - t3)) / 2;
    this.samples.push({ rtt, offset, at: t3 });
    while (this.samples.length > WINDOW || t3 - this.samples[0].at > WINDOW_MS) this.samples.shift();
    let best = this.samples[0];
    for (const s of this.samples) if (s.rtt < best.rtt) best = s;
    this.target = best.offset;
    this.rttMin = best.rtt;
    this.rtt = this.synced ? this.rtt + (rtt - this.rtt) * 0.1 : rtt;
    // the first exchanges (the cars still stand on the grid), or a clock that jumped (a laptop woken up): take it at once
    if (this.taken < SETTLING || Math.abs(this.target - this.offset) > STEP_MS) this.offset = this.target;
    this.taken++;
    this.synced = true;
    return true;
  }

  /** Once per frame: move the offset in use towards the estimate, at most `SLEW` ms per ms. */
  tick(dtMs: number) {
    const d = this.target - this.offset;
    const max = SLEW * Math.max(0, dtMs);
    this.offset += Math.abs(d) <= max ? d : Math.sign(d) * max;
  }

  /** our clock → theirs */
  toRemote(local: number) {
    return local + this.offset;
  }
}

const WINDOW = 512;
const WINDOW_MS = 15000;
/** 1 %: a car at 100 m/s is drawn 1 m/s off while the clock is being corrected */
const SLEW = 0.01;
const STEP_MS = 60;
const SETTLING = 16;
