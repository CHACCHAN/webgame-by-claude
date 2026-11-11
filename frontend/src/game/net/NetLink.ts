import { decodeState, encodeState, SEQ_MOD, type NetState } from './codec';
import { PeerReceiver, type LagMode, type PeerNetStats } from './PeerReceiver';
import { ImpairedTransport, type ImpairConfig, type NetTransport, type Timers } from './transport';

/** What the game fills in of a packet; the link adds the sequence number, the stamps and the clock echo. */
export type LocalState = Omit<NetState, 'seq' | 't' | 'age' | 'echo'> & {
  /** the moment of the pose on our clock (ms) */
  at: number;
};

/**
 * The engine's end of the car-state exchange of an online race: numbers the outgoing packets, answers the
 * peers' clock exchanges, and hands each incoming packet to its sender's `PeerReceiver`. It runs on any
 * `NetTransport` and has no DOM in it (the replay tool drives it on a simulated clock).
 */
export class NetLink {
  /** our player id (echoes addressed to it are ours) */
  selfId = 0;
  /** how the peers' cars are timed (see `LagMode`) */
  mode: LagMode = 'present';
  sent = 0;
  /** packets that were not one of ours (another build, garbage) */
  rejected = 0;
  private inner: NetTransport | null = null;
  private transport: NetTransport | null = null;
  private impairment: ImpairConfig | null = null;
  private peers = new Map<number, PeerReceiver>();
  private seq = 0;
  private turn = 0;

  constructor(
    private now: () => number = () => performance.now(),
    private timers?: Timers,
    private random?: () => number,
  ) {}

  /** The receiving end for a player of the race (made on first use). */
  peer(id: number) {
    let p = this.peers.get(id);
    if (!p) {
      p = new PeerReceiver(id);
      p.mode = this.mode;
      this.peers.set(id, p);
    }
    return p;
  }

  drop(id: number) {
    this.peers.delete(id);
  }

  clear() {
    this.peers.clear();
  }

  /** The transport to use from now on (null: none; the peers' cars then coast to a stop). */
  attach(transport: NetTransport | null) {
    if (this.transport) this.transport.onReceive = null;
    if (this.inner) this.inner.onReceive = null;
    this.inner = transport;
    this.transport = transport && this.impairment ? new ImpairedTransport(transport, this.impairment, this.timers, this.random) : transport;
    if (this.transport) this.transport.onReceive = (from, data) => this.receive(from, data);
  }

  /** Makes the network worse on purpose (testing; null: as it is). Also `?netsim=` and `window.__game.net.impair`. */
  impair(config: ImpairConfig | null) {
    this.impairment = config;
    this.attach(this.inner);
  }

  get impaired() {
    return this.impairment;
  }

  setMode(mode: LagMode) {
    this.mode = mode;
    for (const p of this.peers.values()) p.mode = mode;
  }

  /** Sends our car's state. False when there was nothing to send it on. */
  send(state: LocalState) {
    const transport = this.transport;
    if (!transport?.ready) return false;
    const t = this.now();
    const { at, ...rest } = state;
    const st: NetState = { ...rest, seq: this.seq, t, age: Math.max(0, t - at) };
    this.seq = (this.seq + 1) % SEQ_MOD;
    // one peer's clock exchange per packet, in turn: with four peers each still gets an answer six times a second
    const heard = [...this.peers.values()].filter((p) => p.lastHeard > 0 && t - p.lastHeard < 2000);
    if (heard.length) {
      const p = heard[this.turn++ % heard.length];
      st.echo = { id: p.id, t: p.lastStamp, hold: t - p.lastHeard };
    }
    transport.send(encodeState(st));
    this.sent++;
    return true;
  }

  stats(): PeerNetStats[] {
    return [...this.peers.values()].map((p) => p.stats());
  }

  private receive(from: number, data: unknown) {
    const peer = from === this.selfId ? undefined : this.peers.get(from);
    if (!peer) return;
    const st = decodeState(data);
    if (!st) {
      this.rejected++;
      return;
    }
    peer.receive(st, this.now(), this.selfId);
  }
}
