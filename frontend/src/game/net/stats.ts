import { seqDelta } from './codec';

/**
 * How one peer's packets arrive: the gaps in their sequence numbers (loss), how far apart they come, and how
 * unevenly (jitter, as RTP measures it: the mean change of transit time from one packet to the next).
 */
export class ArrivalStats {
  received = 0;
  /** sequence numbers that never came */
  lost = 0;
  /** packets that came after a newer one (dropped), or twice */
  late = 0;
  /** ms between arrivals, smoothed */
  interval = 0;
  /** ms, smoothed */
  jitter = 0;
  /** ms from the sender's stamp (on our clock) to arrival, smoothed: one-way delay once the clocks are matched */
  transit = 0;
  private highest = -1;
  private lastArrival = 0;
  private lastTransit = 0;
  /** arrivals of the last seconds: [time, sequence numbers missing before it] */
  private recent: [number, number][] = [];

  /**
   * One packet: `seq` its number, `sentLocal` its stamp on our clock, `arrival` when it came (ms).
   * Returns false when it is not newer than what we have (the caller drops it).
   */
  note(seq: number, sentLocal: number, arrival: number) {
    if (this.highest < 0) {
      this.highest = seq;
      this.received = 1;
      this.lastArrival = arrival;
      this.lastTransit = this.transit = arrival - sentLocal;
      this.recent.push([arrival, 0]);
      return true;
    }
    const d = seqDelta(seq, this.highest);
    if (d <= 0) {
      // it had been counted as lost when the newer one came
      this.late++;
      if (d < 0 && this.lost > 0) this.lost--;
      return false;
    }
    this.received++;
    this.lost += d - 1;
    this.highest = seq;
    const gap = arrival - this.lastArrival;
    this.lastArrival = arrival;
    this.interval = this.interval ? this.interval + (gap - this.interval) / 16 : gap;
    const transit = arrival - sentLocal;
    this.jitter += (Math.abs(transit - this.lastTransit) - this.jitter) / 16;
    this.lastTransit = transit;
    this.transit += (transit - this.transit) / 16;
    this.recent.push([arrival, d - 1]);
    while (this.recent.length > 600 || arrival - this.recent[0][0] > RECENT_MS) this.recent.shift();
    return true;
  }

  /** share of the last seconds' packets that never came (0…1) */
  get lossRecent() {
    let got = 0, missing = 0;
    for (const r of this.recent) {
      got++;
      missing += r[1];
    }
    return got + missing ? missing / (got + missing) : 0;
  }

  /** packets per second over the last seconds */
  get rate() {
    const n = this.recent.length;
    return n > 1 ? ((n - 1) * 1000) / Math.max(1, this.recent[n - 1][0] - this.recent[0][0]) : 0;
  }

  /**
   * How far behind the present a car must be drawn for two packets to bracket the moment nearly always: the
   * one-way delay, one send interval, and twice the jitter.
   */
  get bufferDelay() {
    return Math.max(0, this.transit) + this.interval + 2 * this.jitter;
  }
}

const RECENT_MS = 10000;
