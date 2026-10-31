import * as THREE from 'three';
import { CarVisual } from '../render/CarVisual';
import { CAR_SPECS, type CarId } from '../vehicle/carSpecs';
import { clamp } from '../util/math';

/** Paint per grid slot so identical cars stay distinguishable (also shown in the lobby and HUD). */
export const SLOT_COLORS = ['#2a62d8', '#d6283c', '#ecedef'];

/** Car state a client broadcasts ~12 times a second while racing. */
export interface NetState {
  /** sender clock (ms, performance.now) */
  t: number;
  /** body position and orientation */
  p: [number, number, number];
  q: [number, number, number, number];
  /** forward speed (m/s), front wheel steer angle (rad) */
  v: number;
  st: number;
  /** progress along the course (m) and braking flag */
  s: number;
  br: 0 | 1;
  /** finish time (ms) once across the line */
  fin?: number;
}

export interface Peer {
  id: number;
  name: string;
  carId: CarId;
  slot: number;
}

interface RemoteCar {
  peer: Peer;
  visual: CarVisual;
  tag: THREE.Sprite;
  buf: NetState[];
  /** estimated (local receive time − sender time); the minimum seen is the one-way latency floor */
  offset: number;
  wheelSpin: number;
  s: number;
  fin: number | null;
  lastHeard: number;
}

/** Interpolation delay: render other cars this far in the past so two snapshots bracket the time. */
const DELAY_MS = 120;
const _a = new THREE.Vector3(), _b = new THREE.Vector3(), _qa = new THREE.Quaternion(), _qb = new THREE.Quaternion();

/**
 * Other players' cars in an online race: visual only (no collisions), driven by interpolated
 * network snapshots.
 */
export class RemoteRacers {
  private cars = new Map<number, RemoteCar>();

  constructor(
    private root: THREE.Object3D,
    private rideHeightOf: (carId: CarId) => number,
    private shadows: boolean,
  ) {}

  /** Creates cars for the peers, parked on their grid slots until their first state arrives. */
  setPeers(peers: Peer[], grid: (slot: number) => { position: THREE.Vector3; heading: number }) {
    for (const [id, car] of this.cars) if (!peers.some((p) => p.id === id)) this.remove(id, car);
    for (const peer of peers) {
      if (this.cars.has(peer.id)) continue;
      const spec = CAR_SPECS[peer.carId];
      const ride = this.rideHeightOf(peer.carId);
      const visual = new CarVisual(spec, { headlights: true, shadows: this.shadows, rideHeight: ride, bodyColor: SLOT_COLORS[peer.slot % SLOT_COLORS.length] });
      visual.rig.root.traverse((o) => {
        if ((o as THREE.SpotLight).isSpotLight) (o as THREE.SpotLight).castShadow = false;
      });
      const g = grid(peer.slot);
      visual.root.position.copy(g.position).add(new THREE.Vector3(0, ride, 0));
      visual.root.quaternion.setFromAxisAngle(new THREE.Vector3(0, 1, 0), g.heading);
      const tag = nameTag(peer.name, SLOT_COLORS[peer.slot % SLOT_COLORS.length]);
      tag.position.set(0, 2.1, 0);
      visual.root.add(tag);
      this.root.add(visual.root);
      this.cars.set(peer.id, { peer, visual, tag, buf: [], offset: Infinity, wheelSpin: 0, s: 0, fin: null, lastHeard: 0 });
    }
  }

  push(id: number, st: NetState, now: number) {
    const car = this.cars.get(id);
    if (!car) return;
    car.offset = Math.min(car.offset, now - st.t);
    car.lastHeard = now;
    const buf = car.buf;
    if (buf.length && st.t <= buf[buf.length - 1].t) return; // out of order
    buf.push(st);
    if (buf.length > 40) buf.splice(0, buf.length - 40);
    car.s = st.s;
    if (st.fin !== undefined) car.fin = st.fin;
  }

  setHeadlights(on: number) {
    for (const c of this.cars.values()) c.visual.setHeadlights(on);
  }

  update(now: number, dt: number) {
    for (const car of this.cars.values()) {
      const buf = car.buf;
      if (!buf.length) continue;
      // let the latency estimate creep up slowly so clock drift cannot freeze a car
      car.offset += dt * 5;
      const t = now - car.offset - DELAY_MS;
      let i = buf.length - 1;
      while (i > 0 && buf[i - 1].t > t) i--;
      const b = buf[i], a = buf[Math.max(0, i - 1)];
      let k = 1;
      if (b !== a) k = clamp((t - a.t) / (b.t - a.t), 0, 1.5); // up to half a gap of extrapolation
      _a.fromArray(a.p);
      _b.fromArray(b.p);
      _qa.fromArray(a.q);
      _qb.fromArray(b.q);
      const pos = _a.lerp(_b, k);
      const q = _qa.slerp(_qb, Math.min(k, 1));
      const v = a.v + (b.v - a.v) * Math.min(k, 1);
      car.wheelSpin += (v / CAR_SPECS[car.peer.carId].wheelRadius) * dt;
      car.visual.syncFromPose({ position: pos, quaternion: q, steer: b.st, wheelRotations: [car.wheelSpin, car.wheelSpin, car.wheelSpin, car.wheelSpin] }, dt);
      car.visual.setBrakeLights(b.br === 1);
    }
  }

  /** Progress of every remote car for live positions. */
  standings(): { id: number; name: string; slot: number; s: number; fin: number | null; lastHeard: number }[] {
    return [...this.cars.values()].map((c) => ({ id: c.peer.id, name: c.peer.name, slot: c.peer.slot, s: c.s, fin: c.fin, lastHeard: c.lastHeard }));
  }

  removePeer(id: number) {
    const car = this.cars.get(id);
    if (car) this.remove(id, car);
  }

  clear() {
    for (const [id, car] of this.cars) this.remove(id, car);
  }

  private remove(id: number, car: RemoteCar) {
    this.root.remove(car.visual.root);
    car.visual.dispose();
    (car.tag.material as THREE.SpriteMaterial).map?.dispose();
    car.tag.material.dispose();
    this.cars.delete(id);
  }
}

function nameTag(name: string, color: string) {
  const c = document.createElement('canvas');
  c.width = 256;
  c.height = 64;
  const g = c.getContext('2d')!;
  g.font = '600 30px "Zen Kaku Gothic New", sans-serif';
  const w = Math.min(240, g.measureText(name).width + 34);
  g.fillStyle = 'rgba(8,10,16,0.62)';
  g.beginPath();
  g.roundRect((256 - w) / 2, 10, w, 44, 10);
  g.fill();
  g.fillStyle = color;
  g.fillRect((256 - w) / 2 + 10, 22, 6, 20);
  g.fillStyle = '#ffffff';
  g.textAlign = 'center';
  g.textBaseline = 'middle';
  g.fillText(name, 128 + 6, 33, 200);
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true, depthWrite: false }));
  sprite.scale.set(3.2, 0.8, 1);
  sprite.renderOrder = 5;
  return sprite;
}
