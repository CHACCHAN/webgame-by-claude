/**
 * What carries car states between the players of a room. The engine only knows this much of it, so the relay
 * through Reverb (`store/online.ts`) and, later, a direct WebRTC DataChannel are interchangeable. A transport
 * need not be reliable or keep the order: every packet is a whole state with a sequence number.
 */
export interface NetTransport {
  /** can send now (subscribed, connected) */
  readonly ready: boolean;
  /** one packet to every other player in the room */
  send(data: number[]): void;
  /** set by the user: called for each packet with its sender's player id */
  onReceive: ((from: number, data: number[]) => void) | null;
}

/**
 * A worse network, one direction: every packet `delay` ± `jitter` ms later, a share `loss` (0…1) never. With
 * `resend`, a lost packet is not gone but comes that many ms late, holding back those behind it: what loss looks
 * like on a WebSocket, where TCP sends it again.
 */
export interface Impairment {
  delay: number;
  jitter: number;
  loss: number;
  resend?: number;
}

export interface ImpairConfig {
  send?: Impairment;
  recv?: Impairment;
  /** keep each sender's packets in order, as a WebSocket does (default); false lets jitter overtake, as UDP does */
  ordered?: boolean;
}

export interface Timers {
  now(): number;
  after(ms: number, fn: () => void): void;
}

const realTimers: Timers = { now: () => performance.now(), after: (ms, fn) => void setTimeout(fn, ms) };

/**
 * A transport made worse on purpose, in the client (no system changes): for testing the netcode against a given
 * round trip, jitter and loss. With `recv` set on every client of a room, each path gets that delay once.
 */
export class ImpairedTransport implements NetTransport {
  onReceive: ((from: number, data: number[]) => void) | null = null;
  /** when the last packet of each stream is due (ms): later ones may not overtake it */
  private due = new Map<number, number>();
  /** the packets of each stream on their way, in the order they came */
  private held = new Map<number, (() => void)[]>();

  constructor(
    private inner: NetTransport,
    public config: ImpairConfig,
    private timers: Timers = realTimers,
    private random: () => number = Math.random,
  ) {
    inner.onReceive = (from, data) => this.pass(this.config.recv, from, () => this.onReceive?.(from, data));
  }

  get ready() {
    return this.inner.ready;
  }

  send(data: number[]) {
    // (stream 0: no player has that id)
    this.pass(this.config.send, 0, () => this.inner.send(data));
  }

  private pass(imp: Impairment | undefined, stream: number, deliver: () => void) {
    if (!imp) return deliver();
    const lost = this.random() < imp.loss;
    if (lost && imp.resend === undefined) return;
    const now = this.timers.now();
    let at = now + Math.max(0, imp.delay + (this.random() * 2 - 1) * imp.jitter) + (lost ? imp.resend! : 0);
    if (this.config.ordered === false) return this.timers.after(at - now, deliver);
    at = Math.max(at, this.due.get(stream) ?? 0);
    this.due.set(stream, at);
    let held = this.held.get(stream);
    if (!held) this.held.set(stream, (held = []));
    held.push(deliver);
    // a browser's timers that fall due while a frame is busy do not fire in the order they were set: whichever
    // fires hands on everything up to its own packet
    const queue = held;
    this.timers.after(at - now, () => {
      const k = queue.indexOf(deliver);
      for (const d of queue.splice(0, k + 1)) d();
    });
  }
}

/**
 * `?netsim=<one-way delay ms>,<jitter ms>,<loss %>[,recv|send|both[,<resend ms>]]`: e.g. `50,20,2` on both clients of
 * a room is a 100 ms round trip with ±20 ms of jitter and 2 % loss each way. Null when the text is not that.
 */
export function parseImpairment(text: string | null | undefined): ImpairConfig | null {
  if (!text) return null;
  const [d, j = '0', l = '0', where = 'recv', again] = text.split(',');
  const imp: Impairment = { delay: Number(d), jitter: Number(j), loss: Number(l) / 100 };
  if (again !== undefined) imp.resend = Number(again);
  if (![imp.delay, imp.jitter, imp.loss, imp.resend ?? 0].every((x) => Number.isFinite(x) && x >= 0) || imp.loss > 1) return null;
  if (where === 'send') return { send: imp };
  if (where === 'both') return { send: imp, recv: imp };
  return where === 'recv' ? { recv: imp } : null;
}
