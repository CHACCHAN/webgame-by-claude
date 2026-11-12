import * as THREE from 'three';
import { CarVisual } from '../render/CarVisual';
import { CAR_SPECS, type CarId } from '../vehicle/carSpecs';
import { offeredPaint } from '../vehicle/paints';
import { specForLivery } from '../vehicle/trains';
import type { PhysicsWorld, RAPIER } from '../vehicle/PhysicsWorld';
import { ProxyCar } from './ProxyCar';
import { newExhaustState, type ExhaustState } from '../fx/Exhaust';
import type { NetLink } from './NetLink';
import { RemoteBody } from './RemoteBody';
import { newPose } from './PeerTrack';

export type { NetState } from './codec';

/**
 * Colour per grid slot: the member's mark in name tags, the HUD and the lists (two members may pick the same paint),
 * and the paint of a vehicle whose member picked none.
 */
export const SLOT_COLORS = ['#2a62d8', '#d6283c', '#ecedef', '#22dd44', '#cc99dd'];

export interface Peer {
  id: number;
  name: string;
  carId: CarId;
  slot: number;
  /** the paint they picked (drawn only if the vehicle offers it; else the slot's colour) */
  color?: string | null;
}

/** What a member's vehicle is painted with online: their pick if the vehicle offers it, else the seat's colour. */
export const paintFor = (carId: CarId, color: string | null | undefined, slot: number) => offeredPaint(carId, color) ?? SLOT_COLORS[slot % SLOT_COLORS.length];

interface RemoteCar {
  peer: Peer;
  visual: CarVisual;
  tag: THREE.Sprite;
  /** the car as its packets describe it (`body.rx`: clock, path, corrections) and its solid stand-in (`body.proxy`) */
  body: RemoteBody;
  wheelSpin: number;
  /** what the exhaust needs this frame: forward speed (m/s), throttle and rpm share */
  fx: { speed: number; th?: number; rp?: number };
  exhaust: ExhaustState & { speed: number };
}

const _pose = newPose(), _scratch = newPose();

/**
 * Other players' cars in an online race, driven by network packets (`NetLink` → one `PeerReceiver` each). A car
 * is drawn on its path at the moment the local car is drawn at (so both are on screen at the same time of the
 * race, whatever the frame rate), and its solid stand-in (`ProxyCar`) is steered along the same path at each
 * physics step's own moment; what a bump does to the stand-in is added to the picture at once.
 */
export class RemoteRacers {
  private cars = new Map<number, RemoteCar>();
  /** the game's time scale (a test aid): packets speak in wall-clock seconds, the physics world in its own */
  timeScale = 1;
  private lastUpdate = 0;

  constructor(
    private root: THREE.Object3D,
    private rideHeightOf: (carId: CarId) => number,
    private shadows: boolean,
    private link: NetLink,
  ) {}

  /** Creates cars for the peers, parked on their grid slots until their first state arrives. */
  setPeers(peers: Peer[], grid: (slot: number) => { position: THREE.Vector3; heading: number }) {
    for (const [id, car] of this.cars) if (!peers.some((p) => p.id === id)) this.remove(id, car);
    for (const peer of peers) {
      if (this.cars.has(peer.id)) continue;
      const paint = paintFor(peer.carId, peer.color, peer.slot);
      // a train as fitted for its line (the model of that line)
      const spec = specForLivery(CAR_SPECS[peer.carId], paint);
      const ride = this.rideHeightOf(peer.carId);
      const visual = new CarVisual(spec, { headlights: true, shadows: this.shadows, rideHeight: ride, bodyColor: paint });
      const g = grid(peer.slot);
      visual.root.position.copy(g.position).add(new THREE.Vector3(0, ride, 0));
      visual.root.quaternion.setFromAxisAngle(new THREE.Vector3(0, 1, 0), g.heading);
      const tag = nameTag(peer.name, SLOT_COLORS[peer.slot % SLOT_COLORS.length]);
      tag.position.set(0, 2.1, 0);
      visual.root.add(tag);
      this.root.add(visual.root);
      // a train's cars are placed by its rig, not by the root: without this they stay at the origin until the first state
      visual.refresh();
      this.cars.set(peer.id, { peer, visual, tag, body: new RemoteBody(this.link.peer(peer.id), _scratch), wheelSpin: 0, fx: { speed: 0 }, exhaust: { ...newExhaustState(), speed: 0 } });
    }
  }

  /** Gives every remote car a physical stand-in so the local car can bump into it. */
  enablePhysics(physics: PhysicsWorld) {
    for (const car of this.cars.values()) {
      if (car.body.proxy) continue;
      car.body.proxy = new ProxyCar(physics, CAR_SPECS[car.peer.carId], car.visual.root.position, car.visual.root.quaternion);
    }
  }

  /** Physics step: every stand-in goes where its car is at `at` (ms, our clock; see `RemoteBody.step`). */
  stepProxies(at: number, now: number, localCar: THREE.Vector3 | null) {
    for (const car of this.cars.values()) car.body.step(at, now, localCar, this.timeScale);
  }

  /** After the local car respawns: nobody is solid until clear of it. */
  ghostAll(until: number) {
    for (const c of this.cars.values()) c.body.proxy?.ghost(until);
  }

  colliders(): RAPIER.Collider[] {
    const out: RAPIER.Collider[] = [];
    for (const c of this.cars.values()) if (c.body.proxy) out.push(c.body.proxy.collider);
    return out;
  }

  setHeadlights(on: number) {
    for (const c of this.cars.values()) c.visual.setHeadlights(on);
  }

  /** Per frame: every car drawn where it is at `at` (ms, our clock: the moment the local car is drawn at). */
  update(at: number, dt: number) {
    const wallMs = Math.min(250, Math.max(0, at - this.lastUpdate));
    this.lastUpdate = at;
    for (const car of this.cars.values()) {
      if (!car.body.frame(at, wallMs, _pose)) continue;
      car.fx = { speed: _pose.speed / this.timeScale, th: _pose.throttle, rp: _pose.rpm };
      car.wheelSpin += (_pose.speed / CAR_SPECS[car.peer.carId].wheelRadius) * (wallMs / 1000);
      car.visual.syncFromPose({ position: _pose.position, quaternion: _pose.quaternion, steer: _pose.steer, wheelRotations: [car.wheelSpin, car.wheelSpin, car.wheelSpin, car.wheelSpin] }, dt);
      car.visual.setBrakeLights(_pose.brake);
    }
  }

  /** Every remote car's visual with what its exhaust needs (see Game.emitExhaustFromPose). */
  forEachExhaust(cb: (visual: CarVisual, fx: RemoteCar['fx'], state: RemoteCar['exhaust']) => void) {
    for (const car of this.cars.values()) if (car.body.rx.track.length) cb(car.visual, car.fx, car.exhaust);
  }

  /** Progress of every remote car for live positions. */
  standings(): { id: number; name: string; slot: number; paint: string | undefined; s: number; fin: number | null; lastHeard: number }[] {
    return [...this.cars.values()].map((c) => {
      const st = c.body.rx.track.newest;
      return { id: c.peer.id, name: c.peer.name, slot: c.peer.slot, paint: c.visual.color, s: st?.s ?? 0, fin: st?.fin ?? null, lastHeard: c.body.rx.lastHeard };
    });
  }

  removePeer(id: number) {
    const car = this.cars.get(id);
    if (car) this.remove(id, car);
  }

  clear() {
    for (const [id, car] of this.cars) this.remove(id, car);
  }

  private remove(id: number, car: RemoteCar) {
    car.body.proxy?.dispose();
    this.root.remove(car.visual.root);
    car.visual.dispose();
    (car.tag.material as THREE.SpriteMaterial).map?.dispose();
    car.tag.material.dispose();
    this.cars.delete(id);
    this.link.drop(id);
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
