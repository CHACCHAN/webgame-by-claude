import { describe, expect, it } from 'vitest';
import { Quaternion, Vector3 } from 'three';
import { decodeState, encodeState, NET_VERSION, seqDelta, type NetState } from '../net/codec';
import { ClockSync } from '../net/clock';
import { ArrivalStats } from '../net/stats';
import { coast, COAST, COAST_END, newPose, PeerTrack } from '../net/PeerTrack';
import { PeerReceiver } from '../net/PeerReceiver';
import { ImpairedTransport, parseImpairment, type NetTransport, type Timers } from '../net/transport';
import { NetLink, type LocalState } from '../net/NetLink';
import { newSteerMemory, steerProxy } from '../net/steer';
import { PHYSICS_DT } from '../vehicle/PhysicsWorld';

/** a deterministic random source */
function rng(seed: number) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** A clock the test moves, with timers that fire as it passes them. */
class FakeTime implements Timers {
  t = 0;
  private due: { at: number; n: number; fn: () => void }[] = [];
  private n = 0;
  now = () => this.t;
  after = (ms: number, fn: () => void) => void this.due.push({ at: this.t + ms, n: this.n++, fn });
  run(until: number) {
    for (;;) {
      this.due.sort((a, b) => a.at - b.at || a.n - b.n);
      if (!this.due.length || this.due[0].at > until) break;
      const e = this.due.shift()!;
      this.t = e.at;
      e.fn();
    }
    this.t = until;
  }
}

const state = (over: Partial<NetState> = {}): NetState => ({
  seq: 7, t: 123456.7, age: 4.2, p: [812.345, -41.207, -1930.011], q: [0.0123, 0.7071, -0.0045, 0.707], vel: [-31.27, 0.42, 44.9], w: [0.01, -0.83, 0.02],
  acc: [3.1, -0.2, -7.75], st: -0.213, s: 1873.4, br: 1, ep: 2, th: 0.37, rp: 0.81, ...over,
});

/** a car on a circle of radius `r` at `v` m/s, as the game would describe it at `t` seconds */
function circling(t: number, r: number, v: number, seq = 0, ep = 0): NetState {
  // it starts at the origin heading +Z and turns towards −X: heading −a after an angle a
  const a = (v / r) * t, q = new Quaternion().setFromAxisAngle(new Vector3(0, 1, 0), -a);
  return state({
    seq, t: t * 1000, age: 0, ep,
    p: [-r * (1 - Math.cos(a)), 0, r * Math.sin(a)],
    q: [q.x, q.y, q.z, q.w],
    vel: [-v * Math.sin(a), 0, v * Math.cos(a)],
    acc: [(-v * v) / r * Math.cos(a), 0, (-v * v) / r * Math.sin(a)],
    w: [0, -v / r, 0],
  });
}
const circlePos = (t: number, r: number, v: number) => new Vector3(-r * (1 - Math.cos((v / r) * t)), 0, r * Math.sin((v / r) * t));

describe('state codec', () => {
  it('carries a state within its resolution, as whole numbers only', () => {
    const s = state({ fin: 61234, echo: { id: 42, t: 99887.6, hold: 12.3 } });
    const wire = encodeState(s);
    expect(wire.every(Number.isInteger)).toBe(true);
    // (what Reverb does to it on the way: PHP decodes and encodes the JSON again)
    const back = decodeState(JSON.parse(JSON.stringify(wire)))!;
    expect(back.seq).toBe(7);
    expect(back.t).toBeCloseTo(s.t, 1);
    expect(back.age).toBeCloseTo(s.age, 1);
    for (let i = 0; i < 3; i++) {
      expect(back.p[i]).toBeCloseTo(s.p[i], 3);
      expect(back.vel[i]).toBeCloseTo(s.vel[i], 2);
      expect(back.acc[i]).toBeCloseTo(s.acc[i], 2);
      expect(back.w[i]).toBeCloseTo(s.w[i], 3);
    }
    expect(new Quaternion(...back.q).angleTo(new Quaternion(...s.q).normalize())).toBeLessThan(5e-4);
    expect(Math.hypot(...back.q)).toBeCloseTo(1, 9);
    expect([back.st, back.s, back.br, back.ep, back.th, back.rp, back.fin]).toEqual([-0.213, 1873.4, 1, 2, 0.37, 0.81, 61234]);
    expect(back.echo).toEqual({ id: 42, t: 99887.6, hold: 12.3 });
    // well under Reverb's 10 000 bytes per message, with the Pusher envelope around it
    expect(JSON.stringify(wire).length).toBeLessThan(260);
  });

  it('leaves out what is not there', () => {
    const back = decodeState(encodeState(state()))!;
    expect(back.fin).toBeUndefined();
    expect(back.echo).toBeUndefined();
    expect(back.br).toBe(1);
    expect(decodeState(encodeState(state({ br: 0, ep: 3 })))!).toMatchObject({ br: 0, ep: 3 });
  });

  it('drops what is not a state of this build', () => {
    const wire = encodeState(state());
    expect(decodeState(null)).toBeNull();
    expect(decodeState({ t: 1, p: [0, 0, 0] })).toBeNull();
    expect(decodeState(wire.slice(0, -1))).toBeNull();
    expect(decodeState([NET_VERSION + 1, ...wire.slice(1)])).toBeNull();
    expect(decodeState(wire.map((x, k) => (k === 5 ? NaN : x)))).toBeNull();
    expect(decodeState(wire.map((x, k) => (k === 9 ? '1' : x)))).toBeNull();
    expect(decodeState(wire.map((x, k) => (k >= 7 && k <= 10 ? 0 : x)))).toBeNull();
  });

  it('orders sequence numbers across the wrap', () => {
    expect(seqDelta(5, 3)).toBe(2);
    expect(seqDelta(3, 5)).toBe(-2);
    expect(seqDelta(1, 65535)).toBe(2);
    expect(seqDelta(65535, 1)).toBe(-2);
    expect(seqDelta(9, 9)).toBe(0);
    expect(decodeState(encodeState(state({ seq: 65536 + 4 })))!.seq).toBe(4);
  });
});

describe('clock sync', () => {
  /** one exchange: we send at `t` (our clock), their clock is `offset` ahead, the trips take `out` and `back` ms */
  const exchange = (c: ClockSync, t: number, offset: number, out: number, back: number, hold = 7) =>
    c.sample(t, t + out + offset, t + out + hold + offset, t + out + hold + back);

  it('finds the offset and the round trip of a symmetric path', () => {
    const c = new ClockSync();
    expect(exchange(c, 1000, 123456.5, 50, 50)).toBe(true);
    expect(c.synced).toBe(true);
    expect(c.offset).toBeCloseTo(123456.5, 6);
    expect(c.rtt).toBeCloseTo(100, 6);
    expect(c.toRemote(2000)).toBeCloseTo(2000 + 123456.5, 6);
  });

  it('believes the exchange with the shortest round trip', () => {
    const c = new ClockSync(), r = rng(3);
    for (let k = 0; k < 300; k++) {
      exchange(c, k * 33, -98765.4, 50 + (r() * 2 - 1) * 20, 50 + (r() * 2 - 1) * 20);
      c.tick(33);
    }
    // any one exchange can be 20 ms off (40 ms of asymmetry); the best of the last seconds is within a couple
    expect(Math.abs(c.offset - -98765.4)).toBeLessThan(2.5);
    expect(c.rttMin).toBeLessThan(70);
    expect(c.rtt).toBeGreaterThan(85);
    expect(c.rtt).toBeLessThan(115);
  });

  it('assumes no delay until an exchange has completed, then takes the estimate at once', () => {
    const c = new ClockSync();
    // their packets, stamped on their clock (+5000), arrive 40–60 ms later
    c.heard(5000 + 100, 100 + 60);
    c.heard(5000 + 133, 133 + 40);
    c.heard(5000 + 166, 166 + 55);
    expect(c.synced).toBe(false);
    expect(c.offset).toBeCloseTo(5000 - 40, 6);
    exchange(c, 200, 5000, 50, 50);
    expect(c.offset).toBeCloseTo(5000, 6);
    // later packets do not pull it back
    c.heard(5000 + 300, 300 + 10);
    expect(c.offset).toBeCloseTo(5000, 6);
  });

  it('moves slowly to a slightly different estimate, at once to a very different one', () => {
    const c = new ClockSync();
    for (let k = 0; k < 16; k++) exchange(c, k - 16, 1000, 30, 30);
    // a shorter round trip with another offset: the new best
    exchange(c, 100, 1004, 10, 10);
    expect(c.offset).toBeCloseTo(1000, 6);
    c.tick(100);
    expect(c.offset).toBeCloseTo(1001, 6);
    c.tick(1000);
    expect(c.offset).toBeCloseTo(1004, 6);
    exchange(c, 200, 1500, 5, 5);
    expect(c.offset).toBeCloseTo(1500, 6);
  });

  it('refuses an exchange that cannot be', () => {
    const c = new ClockSync();
    // held longer than the whole round trip took
    expect(c.sample(1000, 5000, 5300, 1100)).toBe(false);
    expect(c.sample(NaN, 1, 2, 3)).toBe(false);
    expect(c.synced).toBe(false);
  });
});

describe('arrival statistics', () => {
  it('counts loss from the gaps in the sequence numbers, across the wrap', () => {
    const a = new ArrivalStats();
    const seqs = [65533, 65534, 0, 1, 4, 5];
    seqs.forEach((s, k) => expect(a.note(s, k * 40, k * 40 + 50)).toBe(true));
    // 65535, 2 and 3 never came
    expect(a.received).toBe(6);
    expect(a.lost).toBe(3);
    expect(a.lossRecent).toBeCloseTo(3 / 9, 9);
  });

  it('takes a late packet off the lost ones and tells the caller to drop it', () => {
    const a = new ArrivalStats();
    a.note(10, 0, 50);
    a.note(12, 80, 130);
    expect(a.lost).toBe(1);
    expect(a.note(11, 40, 135)).toBe(false);
    expect(a.lost).toBe(0);
    expect(a.late).toBe(1);
    // a duplicate
    expect(a.note(12, 80, 140)).toBe(false);
    expect(a.lost).toBe(0);
    expect(a.late).toBe(2);
    expect(a.received).toBe(2);
  });

  it('measures interval, jitter and the buffer delay they ask for', () => {
    const even = new ArrivalStats(), r = rng(9), uneven = new ArrivalStats();
    for (let k = 0; k < 400; k++) {
      even.note(k, k * 40, k * 40 + 50);
      uneven.note(k, k * 40, k * 40 + 50 + (r() * 2 - 1) * 20);
    }
    expect(even.interval).toBeCloseTo(40, 6);
    expect(even.jitter).toBeCloseTo(0, 6);
    expect(even.transit).toBeCloseTo(50, 6);
    expect(even.bufferDelay).toBeCloseTo(90, 6);
    expect(even.rate).toBeCloseTo(25, 1);
    // ±20 ms, uniform: the mean change of transit between two packets is 13.3 ms
    expect(uneven.jitter).toBeGreaterThan(9);
    expect(uneven.jitter).toBeLessThan(18);
    expect(uneven.interval).toBeGreaterThan(35);
    expect(uneven.interval).toBeLessThan(45);
    expect(uneven.bufferDelay).toBeCloseTo(uneven.transit + uneven.interval + 2 * uneven.jitter, 9);
  });
});

describe('path between packets', () => {
  const R = 60, V = 30, HZ = 30;

  it('runs through every packet at its velocity, and stays on a bend between them', () => {
    const track = new PeerTrack(), pose = newPose();
    for (let k = 0; k <= 30; k++) track.push(circling(k / HZ, R, V, k));
    // at a packet: its pose and velocity
    track.sample((10 / HZ) * 1000, pose);
    expect(pose.position.distanceTo(circlePos(10 / HZ, R, V))).toBeLessThan(1e-6);
    expect(pose.velocity.length()).toBeCloseTo(V, 6);
    expect(pose.ahead).toBe(0);
    // between packets, on a 60 m bend at 108 km/h: within a tenth of a millimetre (a straight line would cut 2 mm)
    let worst = 0;
    for (let t = 0.2; t < 0.9; t += 0.0037) {
      track.sample(t * 1000, pose);
      worst = Math.max(worst, pose.position.distanceTo(circlePos(t, R, V)));
      expect(pose.velocity.length()).toBeCloseTo(V, 2);
    }
    expect(worst).toBeLessThan(1e-4);
    expect(pose.speed).toBeCloseTo(V, 3);
  });

  it('carries the newest packet on along its bend', () => {
    const track = new PeerTrack(), pose = newPose();
    track.push(circling(1, R, V));
    // 100 ms past the packet: velocity alone would be 7.5 cm off the bend, with the acceleration it is millimetres
    track.sample(1100, pose);
    expect(pose.ahead).toBeCloseTo(0.1, 9);
    expect(pose.position.distanceTo(circlePos(1.1, R, V))).toBeLessThan(0.004);
    const straight = new Vector3(...circling(1, R, V).p).addScaledVector(new Vector3(...circling(1, R, V).vel), 0.1);
    expect(straight.distanceTo(circlePos(1.1, R, V))).toBeGreaterThan(0.07);
    // the heading turns with it (0.05 rad in that time)
    expect(pose.quaternion.angleTo(new Quaternion(...circling(1.1, R, V).q))).toBeLessThan(1e-3);
    expect(pose.quaternion.angleTo(new Quaternion(...circling(1, R, V).q))).toBeGreaterThan(0.04);
  });

  it('lets a silent car coast, then brings it to a stop', () => {
    expect(coast(0.1)).toEqual([0.1, 1]);
    expect(coast(COAST)[0]).toBeCloseTo(COAST, 9);
    // continuous in distance and speed where the slowing starts, standing from the end on
    expect(coast(COAST + 1e-6)[0]).toBeCloseTo(COAST, 5);
    expect(coast(COAST + 1e-6)[1]).toBeCloseTo(1, 5);
    expect(coast(COAST_END - 1e-6)[1]).toBeCloseTo(0, 5);
    expect(coast(COAST_END)).toEqual(coast(COAST_END + 5));
    const track = new PeerTrack(), a = newPose(), b = newPose();
    track.push(state({ t: 0, age: 0, vel: [0, 0, 40], acc: [0, 0, 0], w: [0, 0, 0] }));
    track.sample(3000, a);
    track.sample(9000, b);
    expect(a.position.distanceTo(b.position)).toBe(0);
    expect(a.velocity.length()).toBe(0);
    // 40 m/s for a quarter of a second, then half of that over the slowing
    expect(a.position.z - state().p[2]).toBeCloseTo(40 * (COAST + (COAST_END - COAST) / 2), 6);
  });

  it('never lets braking turn the car round', () => {
    const track = new PeerTrack(), pose = newPose();
    // 2 m/s, braking at 10 m/s²: it stands after 0.2 s and 0.2 m
    track.push(state({ t: 0, age: 0, p: [0, 0, 0], vel: [0, 0, 2], acc: [0, 0, -10], w: [0, 0, 0] }));
    track.sample(240, pose);
    expect(pose.position.z).toBeCloseTo(0.2, 6);
    expect(pose.velocity.z).toBeCloseTo(0, 6);
  });

  it('drops a packet older than the newest and does not drive through a respawn', () => {
    const track = new PeerTrack(), pose = newPose();
    expect(track.push(state({ t: 100, age: 0, p: [0, 0, 0], vel: [0, 0, 30], acc: [0, 0, 0], ep: 0 }))).toBe(true);
    expect(track.push(state({ t: 90, age: 0 }))).toBe(false);
    // the state's own moment counts, not when it was sent
    expect(track.push(state({ t: 120, age: 30 }))).toBe(false);
    expect(track.push(state({ t: 200, age: 0, p: [0, 0, -50], vel: [0, 0, 0], ep: 1 }))).toBe(true);
    track.sample(150, pose);
    // carried on from the old place, not half way to the new one
    expect(pose.position.z).toBeCloseTo(1.5, 6);
    track.sample(200, pose);
    expect(pose.position.z).toBeCloseTo(-50, 6);
  });
});

describe('peer receiver', () => {
  /** packets of a car on a bend arrive `delay` ms after their moment; returns the receiver after `n` of them */
  function feed(rx: PeerReceiver, n: number, delay = 50, hz = 30, from = 0) {
    for (let k = from; k < from + n; k++) rx.receive(circling(k / hz, 60, 30, k), (k / hz) * 1000 + delay, 1);
    return rx;
  }

  it('shows the car where it is now, not where the last packet had it', () => {
    const rx = feed(new PeerReceiver(2), 30, 0);
    const pose = newPose();
    // (no exchange yet and no delay: the clocks agree)
    const now = (29 / 30) * 1000 + 20;
    expect(rx.display(now, pose)).toBe(true);
    expect(pose.position.distanceTo(circlePos(now / 1000, 60, 30))).toBeLessThan(0.002);
    expect(pose.ahead).toBeCloseTo(0.02, 6);
  });

  it('eases a correction in: no jump when the packet arrives, none in speed, gone half a second later', () => {
    const rx = feed(new PeerReceiver(2), 30, 0);
    const before = newPose(), after = newPose(), raw = newPose();
    const now = 1000 + 12;
    rx.display(now, before);
    // the car is 0.25 m to the side of where its motion had pointed
    const st = circling(1, 60, 30, 30);
    st.p[0] += 0.25;
    rx.receive(st, now, 1);
    rx.display(now, after);
    rx.raw(now, raw);
    expect(raw.position.distanceTo(before.position)).toBeGreaterThan(0.2);
    expect(after.position.distanceTo(before.position)).toBeLessThan(1e-9);
    expect(after.velocity.distanceTo(before.velocity)).toBeLessThan(0.05);
    expect(rx.corrections[rx.corrections.length - 1]).toBeCloseTo(raw.position.distanceTo(before.position), 3);
    expect(rx.jumped).toBe(false);
    // on the way over the error shrinks steadily, never faster than a couple of m/s, and it arrives
    let last = after.position.distanceTo(raw.position), fastest = 0;
    for (let t = now + 4; t <= now + 500; t += 4) {
      rx.display(t, after);
      rx.raw(t, raw);
      const left = after.position.distanceTo(raw.position);
      expect(left).toBeLessThanOrEqual(last + 1e-9);
      fastest = Math.max(fastest, (last - left) / 0.004);
      last = left;
    }
    expect(fastest).toBeLessThan(2);
    rx.display(now + 500, after);
    rx.raw(now + 500, raw);
    expect(after.position.distanceTo(raw.position)).toBeLessThan(0.005);
    rx.display(now + 60, after);
    rx.raw(now + 60, raw);
    const left = after.position.distanceTo(raw.position);
    expect(left).toBeGreaterThan(0.1);
    expect(left).toBeLessThan(0.25);
  });

  it('puts the car in place after a respawn or a jump, and says so', () => {
    const rx = feed(new PeerReceiver(2), 30, 0);
    const pose = newPose(), now = 1000 + 5;
    const far = circling(1, 60, 30, 30);
    far.p[2] += 20;
    rx.receive(far, now, 1);
    expect(rx.jumped).toBe(true);
    expect(rx.snaps).toBe(1);
    rx.display(now, pose);
    expect(pose.position.z).toBeCloseTo(far.p[2] + far.vel[2] * 0.005, 2);
    rx.jumped = false;
    // a respawn a metre away is still a respawn
    const near = circling(31 / 30, 60, 30, 31, 1);
    near.p[2] += 21;
    rx.receive(near, now + 33, 1);
    expect(rx.jumped).toBe(true);
    expect(rx.corrections.length).toBe(29);
  });

  it('draws in the past when asked to, by the measured buffer delay', () => {
    const rx = new PeerReceiver(2);
    rx.mode = 'buffered';
    const pose = newPose();
    for (let k = 0; k < 120; k++) {
      rx.receive(circling(k / 30, 60, 30, k), (k / 30) * 1000, 1);
      rx.tick(33.3);
    }
    for (let k = 0; k < 600; k++) rx.tick(16.7);
    // no delay, 33 ms between packets, no jitter
    expect(rx.arrivals.bufferDelay).toBeCloseTo(1000 / 30, 3);
    expect(rx.lag).toBeCloseTo(1000 / 30, 1);
    const now = (119 / 30) * 1000 + 10;
    rx.display(now, pose);
    expect(pose.ahead).toBe(0);
    expect(pose.position.distanceTo(circlePos((now - rx.lag) / 1000, 60, 30))).toBeLessThan(1e-3);
    rx.countFrame(pose);
    expect(rx.stats().ahead).toBe(0);
  });

  it('keeps the numbers of its link', () => {
    const rx = new PeerReceiver(2), pose = newPose();
    // every tenth packet never comes
    for (let k = 0; k < 300; k++) if (k % 10 !== 9) rx.receive(circling(k / 30, 60, 30, k), (k / 30) * 1000 + 50, 1);
    for (let f = 0; f < 240; f++) {
      rx.display(9950 + 50 + f, pose);
      rx.countFrame(pose);
    }
    const s = rx.stats();
    expect(s.id).toBe(2);
    expect(s.received).toBe(270);
    expect(s.lost).toBe(29);
    expect(s.loss).toBeCloseTo(29 / 299, 2);
    expect(s.rate).toBeGreaterThan(26);
    expect(s.rate).toBeLessThan(28);
    expect(s.synced).toBe(false);
    expect(s.ahead).toBeGreaterThan(0.8);
    expect(s.horizon).toBeGreaterThan(50);
    // on a steady bend a new packet moves the prediction by millimetres
    expect(s.correctionMax).toBeLessThan(0.02);
    expect(s.snaps).toBe(0);
  });
});

describe('impairment injector', () => {
  function pipe(config: ConstructorParameters<typeof ImpairedTransport>[1], seed = 1) {
    const time = new FakeTime();
    const sent: number[][] = [];
    const inner: NetTransport = { ready: true, send: (d) => void sent.push(d), onReceive: null };
    const t = new ImpairedTransport(inner, config, time, rng(seed));
    return { time, sent, inner, t };
  }

  it('delays what is received by the delay ± jitter, loses the share asked for, keeps the order', () => {
    const { time, inner, t } = pipe({ recv: { delay: 50, jitter: 20, loss: 0.1 } });
    const got: [number, number][] = [];
    t.onReceive = (_from, data) => void got.push([data[0], time.t]);
    for (let k = 0; k < 2000; k++) {
      time.run(k * 10);
      inner.onReceive!(3, [k]);
    }
    time.run(30000);
    expect(got.length).toBeGreaterThan(1700);
    expect(got.length).toBeLessThan(1900);
    let late = 0;
    for (let i = 0; i < got.length; i++) {
      const d = got[i][1] - got[i][0] * 10;
      expect(d).toBeGreaterThanOrEqual(30 - 1e-9);
      // (held back behind an earlier packet at most)
      expect(d).toBeLessThanOrEqual(70 + 1e-9);
      if (d > 60) late++;
      if (i) expect(got[i][0]).toBeGreaterThan(got[i - 1][0]);
    }
    expect(late).toBeGreaterThan(got.length / 8);
  });

  it('keeps the order even when the timers do not fire in theirs', () => {
    const fired: (() => void)[] = [];
    const inner: NetTransport = { ready: true, send: () => {}, onReceive: null };
    const t = new ImpairedTransport(inner, { recv: { delay: 50, jitter: 20, loss: 0 } }, { now: () => 0, after: (_ms, fn) => void fired.push(fn) }, rng(4));
    const got: number[] = [];
    t.onReceive = (_from, data) => void got.push(data[0]);
    for (let k = 0; k < 6; k++) inner.onReceive!(3, [k]);
    // the fourth packet's timer first, then the rest back to front
    fired[3]();
    expect(got).toEqual([0, 1, 2, 3]);
    for (const fn of fired.reverse()) fn();
    expect(got).toEqual([0, 1, 2, 3, 4, 5]);
  });

  it('lets packets overtake when told the transport does not keep the order', () => {
    const { time, inner, t } = pipe({ recv: { delay: 50, jitter: 40, loss: 0 }, ordered: false });
    const got: number[] = [];
    t.onReceive = (_from, data) => void got.push(data[0]);
    for (let k = 0; k < 200; k++) {
      time.run(k * 10);
      inner.onReceive!(3, [k]);
    }
    time.run(5000);
    expect(got.length).toBe(200);
    expect(got.some((x, i) => i > 0 && x < got[i - 1])).toBe(true);
  });

  it('makes a lost packet late instead, holding back the ones behind it, when a resend time is given', () => {
    const { time, inner, t } = pipe({ recv: { delay: 10, jitter: 0, loss: 0.2, resend: 200 } });
    const got: [number, number][] = [];
    t.onReceive = (_from, data) => void got.push([data[0], time.t]);
    for (let k = 0; k < 300; k++) {
      time.run(k * 30);
      inner.onReceive!(3, [k]);
    }
    time.run(20000);
    expect(got.map((g) => g[0])).toEqual(Array.from({ length: 300 }, (_, k) => k));
    const delays = got.map((g) => g[1] - g[0] * 30);
    expect(Math.max(...delays)).toBeCloseTo(210, 6);
    expect(delays.filter((d) => d > 150).length).toBeGreaterThan(30);
    // those right behind a resent one wait for it
    expect(delays.filter((d) => d > 10.001 && d < 209.999).length).toBeGreaterThan(30);
  });

  it('impairs what is sent, and passes everything through untouched without a setting', () => {
    const { time, sent, inner, t } = pipe({ send: { delay: 25, jitter: 0, loss: 0 } });
    const got: number[][] = [];
    t.onReceive = (_from, data) => void got.push(data);
    t.send([1]);
    inner.onReceive!(9, [2]);
    expect(got).toEqual([[2]]);
    expect(sent).toEqual([]);
    time.run(24);
    expect(sent).toEqual([]);
    time.run(25);
    expect(sent).toEqual([[1]]);
    expect(t.ready).toBe(true);
  });

  it('reads the URL form', () => {
    expect(parseImpairment('50,20,2')).toEqual({ recv: { delay: 50, jitter: 20, loss: 0.02 } });
    expect(parseImpairment('80')).toEqual({ recv: { delay: 80, jitter: 0, loss: 0 } });
    expect(parseImpairment('30,5,1,send')).toEqual({ send: { delay: 30, jitter: 5, loss: 0.01 } });
    expect(parseImpairment('30,5,1,both,150')).toEqual({ send: { delay: 30, jitter: 5, loss: 0.01, resend: 150 }, recv: { delay: 30, jitter: 5, loss: 0.01, resend: 150 } });
    for (const bad of [null, '', 'abc', '50,x', '50,20,200', '-5', '50,20,2,sideways']) expect(parseImpairment(bad)).toBeNull();
  });
});

describe('net link', () => {
  /** players on a relay, each with its own clock (`offsets`, ms against the test's time) and the same impairment */
  function room(offsets: number[], recv = { delay: 50, jitter: 0, loss: 0 }, seed = 5) {
    const time = new FakeTime(), random = rng(seed);
    const ends = new Map<number, NetTransport>();
    const links = offsets.map((off, k) => {
      const id = k + 1;
      const timers: Timers = { now: () => time.t + off, after: time.after };
      const end: NetTransport = { ready: true, onReceive: null, send: (d) => ends.forEach((e, other) => other !== id && e.onReceive?.(id, d)) };
      ends.set(id, end);
      const link = new NetLink(timers.now, timers, random);
      link.selfId = id;
      for (let o = 1; o <= offsets.length; o++) if (o !== id) link.peer(o);
      link.impair({ recv });
      link.attach(end);
      return { id, off, link };
    });
    const local = (id: number, t: number, off: number): LocalState => {
      // (the physics state is 3 ms old when it leaves)
      const { seq: _s, t: _t, age: _a, echo: _e, ...rest } = circling((t - 3) / 1000, 60 + id * 5, 30);
      return { ...rest, at: t + off - 3 };
    };
    /** everyone sends 30 times a second for `seconds` */
    const play = (seconds: number) => {
      const from = time.t;
      for (let k = 0; k < seconds * 30; k++) {
        time.run(from + (k * 1000) / 30);
        for (const l of links) {
          l.link.send(local(l.id, time.t, l.off));
          // (the game does this once per frame for every car it draws)
          for (const s of l.link.stats()) l.link.peer(s.id).tick(1000 / 30);
        }
      }
      time.run(from + seconds * 1000);
    };
    return { time, links, play };
  }

  it('matches the clocks of two players through their own states', () => {
    const { links, play } = room([1000.5, 987654.25]);
    play(3);
    const [a, b] = links;
    const sa = a.link.stats()[0], sb = b.link.stats()[0];
    expect(sa.synced && sb.synced).toBe(true);
    // (the wire carries 0.1 ms)
    expect(sa.offset).toBeCloseTo(b.off - a.off, 0);
    expect(sb.offset).toBeCloseTo(a.off - b.off, 0);
    expect(Math.abs(sa.offset - (b.off - a.off))).toBeLessThan(0.2);
    expect(sa.rtt).toBeGreaterThan(99);
    expect(sa.rtt).toBeLessThan(101);
    expect(sa.received).toBeGreaterThan(85);
    expect(sa.lost).toBe(0);
    expect(sa.interval).toBeCloseTo(1000 / 30, 0);
    expect(a.link.sent).toBe(90);
    // and so the other car is shown where it is, 50 ms of network and all
    const pose = newPose(), t = 3000 - 5;
    a.link.peer(2).display(t + a.off, pose);
    expect(pose.position.distanceTo(circlePos(t / 1000, 70, 30))).toBeLessThan(0.02);
  });

  it('answers every peer in turn in a room of five, and counts what the network loses', () => {
    const { links, play } = room([0, 11111.1, -2222.2, 333333.3, 44.4], { delay: 40, jitter: 15, loss: 0.05 });
    play(8);
    for (const l of links) {
      const stats = l.link.stats();
      expect(stats.length).toBe(4);
      for (const s of stats) {
        const other = links[s.id - 1];
        expect(s.synced).toBe(true);
        expect(Math.abs(s.offset - (other.off - l.off))).toBeLessThan(6);
        expect(s.rttMin).toBeLessThan(75);
        expect(s.lost / (s.lost + s.received)).toBeGreaterThan(0.02);
        expect(s.lost / (s.lost + s.received)).toBeLessThan(0.09);
        expect(s.jitter).toBeGreaterThan(5);
      }
      expect(l.link.rejected).toBe(0);
    }
  });

  it('ignores strangers, itself and other builds', () => {
    const time = new FakeTime();
    const end: NetTransport = { ready: true, onReceive: null, send: () => undefined };
    const link = new NetLink(time.now, time);
    link.selfId = 1;
    link.peer(2);
    link.attach(end);
    const wire = encodeState(state({ seq: 0, t: 0, age: 0 }));
    end.onReceive!(9, wire);
    end.onReceive!(1, wire);
    expect(link.rejected).toBe(0);
    end.onReceive!(2, [1, 2, 3]);
    end.onReceive!(2, { t: 1 } as unknown as number[]);
    expect(link.rejected).toBe(2);
    expect(link.stats()[0].received).toBe(0);
    end.onReceive!(2, wire);
    expect(link.stats()[0].received).toBe(1);
    // nothing to send on: says so, sends nothing
    link.attach(null);
    expect(link.send({ ...state(), at: 0 })).toBe(false);
    expect(end.onReceive).toBeNull();
  });
});

describe('stand-in steering', () => {
  it('keeps a stand-in on the path of a braking, turning car without a lag', () => {
    const m = newSteerMemory(), cmd: [number, number, number] = [0, 0, 0];
    const pos = circlePos(0, 40, 30).toArray() as [number, number, number];
    let vel: number[] = [0, 0, 0], worst = 0;
    for (let k = 1; k <= 600; k++) {
      const t = k * PHYSICS_DT, target = circlePos(t, 40, 30), v = new Vector3(...circling(t, 40, 30).vel);
      steerProxy(m, pos, vel, target.toArray(), v.toArray(), PHYSICS_DT, cmd);
      for (let i = 0; i < 3; i++) pos[i] += cmd[i] * PHYSICS_DT;
      vel = [...cmd];
      if (k > 60) worst = Math.max(worst, target.distanceTo(new Vector3(...pos)));
    }
    // 22.5 m/s² of cornering: the old law (velocity blended over 0.15 s) trailed by more than a metre
    expect(worst).toBeLessThan(1e-3);
    expect(m.push.every((x) => Math.abs(x) < 1e-9)).toBe(true);
  });

  it('keeps what a hit did for a moment, then comes back to the path', () => {
    const m = newSteerMemory(), cmd: [number, number, number] = [0, 0, 0];
    const pos: [number, number, number] = [0, 0, 0];
    let vel: number[] = [0, 0, 20];
    const step = (k: number, hit = 0) => {
      steerProxy(m, pos, [vel[0] + hit, vel[1], vel[2]], [0, 0, 20 * k * PHYSICS_DT], [0, 0, 20], PHYSICS_DT, cmd);
      for (let i = 0; i < 3; i++) pos[i] += cmd[i] * PHYSICS_DT;
      vel = [...cmd];
    };
    for (let k = 1; k <= 10; k++) step(k);
    expect(Math.abs(pos[0])).toBeLessThan(1e-9);
    // shoved sideways at 3 m/s
    step(11, 3);
    expect(cmd[0]).toBeGreaterThan(2.5);
    let far = 0;
    for (let k = 12; k <= 12 + 17; k++) step(k);
    // 0.15 s later a third of it is left
    expect(m.push[0]).toBeGreaterThan(0.9);
    expect(m.push[0]).toBeLessThan(1.3);
    for (let k = 30; k <= 600; k++) {
      step(k);
      far = Math.max(far, Math.abs(pos[0]));
    }
    expect(far).toBeGreaterThan(0.2);
    expect(far).toBeLessThan(0.6);
    expect(Math.abs(pos[0])).toBeLessThan(0.01);
    expect(Math.abs(pos[2] - 20 * 600 * PHYSICS_DT)).toBeLessThan(0.01);
  });

  it('never pulls back faster than 8 m/s', () => {
    const m = newSteerMemory(), cmd: [number, number, number] = [0, 0, 0];
    steerProxy(m, [0, 0, 0], [0, 0, 0], [6, 0, 0], [0, 0, 0], PHYSICS_DT, cmd);
    expect(cmd[0]).toBeCloseTo(8, 6);
    steerProxy(newSteerMemory(), [0, 0, 0], [0, 0, 0], [1, 0, 0], [0, 0, 0], PHYSICS_DT, cmd);
    expect(cmd[0]).toBeCloseTo(3, 6);
  });

  it('is not flung after the path when the steps skip time: it is moved by what the path did meanwhile', () => {
    const m = newSteerMemory(), cmd: [number, number, number] = [0, 0, 0];
    // (pushed half a metre aside by a hit before: that stays)
    const pos: [number, number, number] = [0.5, 0, 0];
    const at = (t: number): [number, number, number] => [0, 0, 40 * t];
    for (let k = 1; k <= 5; k++) {
      steerProxy(m, pos, cmd, at(k * PHYSICS_DT), [0, 0, 40], PHYSICS_DT, cmd);
      for (let i = 0; i < 3; i++) pos[i] += cmd[i] * PHYSICS_DT;
      expect(m.shift).toEqual([0, 0, 0]);
    }
    const aside = pos[0];
    // a frame stalled for 0.1 s: the path is 4 m further on
    const t = 5 * PHYSICS_DT + 0.1 + PHYSICS_DT;
    steerProxy(m, pos, cmd, at(t), [0, 0, 40], PHYSICS_DT, cmd, true);
    expect(m.shift[2]).toBeCloseTo(4, 9);
    expect(cmd[2]).toBeCloseTo(40, 6);
    for (let i = 0; i < 3; i++) pos[i] += m.shift[i] + cmd[i] * PHYSICS_DT;
    expect(pos[2]).toBeCloseTo(at(t)[2], 9);
    expect(pos[0]).toBeGreaterThan(aside * 0.95);
    // a crash is no gap: the path's velocity changes at once, the body follows the path
    steerProxy(m, pos, cmd, [0, 0, pos[2]], [0, 0, 0], PHYSICS_DT, cmd);
    expect(m.shift).toEqual([0, 0, 0]);
    expect(Math.abs(cmd[2])).toBeLessThan(1e-6);
  });
});
