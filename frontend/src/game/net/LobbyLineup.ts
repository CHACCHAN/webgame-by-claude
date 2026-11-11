import * as THREE from 'three';
import { CarVisual } from '../render/CarVisual';
import { loadTrainModel, trainModelReady } from '../render/TrainModel';
import { CAR_SPECS, type CarId } from '../vehicle/carSpecs';
import { trainLivery, trainModelKey } from '../vehicle/trains';
import type { Track } from '../track/Track';
import { SLOT_COLORS } from './RemoteRacers';
import { focusOf, lineupPlan, type LineupEntry, type RoadSpan } from './lineup';

/** a new model is shown once its shaders are compiled, or after this long (ms) if that never comes back */
const COMPILE_WAIT = 4000;

interface Standing {
  slot: number;
  /** the vehicle that stands there (null: the first one is still on its way) and what it is */
  visual: CarVisual | null;
  key: string;
  /** its height (m): where its name tag hangs */
  top: number;
  /** the vehicle wanted when it is not the one standing: built, its shaders compiling */
  pending: { key: string; visual: CarVisual } | null;
  entry: LineupEntry;
  /** its place on the road and the road's heading there */
  spot: THREE.Vector3;
  heading: number;
}

const keyOf = (e: LineupEntry) => `${e.carId}|${e.livery ?? ''}`;
const _box = new THREE.Box3();

/**
 * The vehicles of an online waiting room, standing on the course in their seats' colours. A seat's vehicle changes
 * while the room is up (another one confirmed, or looked at in the picker): the new model is built, its shaders are
 * compiled off the frame loop (`compile`, when the renderer offers it) and only then does it take the place of the
 * one before it, which is disposed. The vehicles have no headlamp beams: a light more or less in the scene would
 * rebuild every material's shader at each change.
 */
export class LobbyLineup {
  readonly group = new THREE.Group();
  private slots = new Map<number, Standing>();
  private entries: LineupEntry[] = [];
  private span: RoadSpan = { s0: 0, s1: 0, l0: 0, l1: 0 };
  private scale = 1;
  private lamps = 1;
  private disposed = false;

  constructor(
    private track: Track,
    private opts: { shadows: boolean; compile?: ((o: THREE.Object3D) => Promise<unknown>) | null },
  ) {
    this.group.name = 'lobby-lineup';
  }

  /** The room as it is now: seats filled, emptied, or showing another vehicle. */
  set(entries: readonly LineupEntry[]) {
    if (this.disposed) return;
    this.entries = entries.map((e) => ({ ...e })).sort((a, b) => a.slot - b.slot);
    const { spots, span, scale } = lineupPlan(this.entries, this.track.startS);
    this.span = span;
    this.scale = scale;
    for (const [slot, st] of this.slots) {
      if (this.entries.some((e) => e.slot === slot)) continue;
      this.discard(st.visual);
      this.discard(st.pending?.visual ?? null);
      st.visual = null;
      st.pending = null;
      this.slots.delete(slot);
    }
    for (const e of this.entries) {
      let st = this.slots.get(e.slot);
      if (!st) {
        st = { slot: e.slot, visual: null, key: '', top: 1.4, pending: null, entry: e, spot: new THREE.Vector3(), heading: 0 };
        this.slots.set(e.slot, st);
      }
      st.entry = e;
      const g = spots.get(e.slot)!;
      this.track.pointAt(g.s, g.lateral, st.spot);
      st.heading = this.track.headingAt(g.s);
      if (st.visual) this.place(st.visual, st);
      if (keyOf(e) !== (st.pending?.key ?? st.key)) this.build(st);
      else if (st.pending) this.place(st.pending.visual, st);
      st.visual?.setHeadlights(this.lampLevel(st), true);
    }
  }

  /** Lamps of the vehicles (1 at night, ~0.5 by day); one that is only being looked at stays dark. */
  setLamps(level: number) {
    this.lamps = level;
    for (const st of this.slots.values()) st.visual?.setHeadlights(this.lampLevel(st), true);
  }

  private lampLevel(st: Standing) {
    // (while the vehicle standing there is still the one before, it keeps its lamps)
    return st.entry.browsing && !st.pending ? 0 : this.lamps;
  }

  /** The seat's vehicle as its entry wants it: built now, shown once its shaders are there. `again`: even if it stands already. */
  private build(st: Standing, again = false) {
    // the one that was on its way is not wanted any more
    this.discard(st.pending?.visual ?? null);
    st.pending = null;
    const e = st.entry, key = keyOf(e);
    if (st.visual && key === st.key && !again) return;
    const spec = CAR_SPECS[e.carId];
    const visual = new CarVisual(spec, { headlights: false, shadows: this.opts.shadows, rideHeight: 0, bodyColor: e.livery ?? SLOT_COLORS[e.slot % SLOT_COLORS.length] });
    const pending = { key, visual };
    st.pending = pending;
    this.place(visual, st);
    // a train's line is a model of its own, fetched when first wanted: the base model stands in until it is there,
    // then the train is built again
    const line = spec.train && e.livery ? trainLivery(spec.train, e.livery) : undefined;
    if (line && !trainModelReady(spec.id, line)) {
      void loadTrainModel(trainModelKey(spec.id, line)).then(() => {
        if (!this.disposed && this.slots.get(st.slot) === st && keyOf(st.entry) === key && trainModelReady(spec.id, line)) this.build(st, true);
      });
    }
    const show = () => {
      if (this.disposed || st.pending !== pending) return;
      this.discard(st.visual);
      st.pending = null;
      st.visual = visual;
      st.key = key;
      this.group.add(visual.root);
      visual.root.updateMatrixWorld(true);
      st.top = _box.setFromObject(visual.rig.root).max.y - visual.root.position.y;
      if (!Number.isFinite(st.top)) st.top = 1.4;
      visual.setHeadlights(this.lampLevel(st), true);
    };
    const compile = this.opts.compile;
    if (!compile) return show();
    // not in the scene yet: compiled where it will stand (the renderer skips what the camera cannot see), as it
    // will look
    visual.setHeadlights(e.browsing ? 0 : this.lamps, true);
    visual.root.updateMatrixWorld(true);
    let done = false;
    const once = () => {
      if (done) return;
      done = true;
      show();
    };
    void compile(visual.root).then(once, once);
    setTimeout(once, COMPILE_WAIT);
  }

  private place(visual: CarVisual, st: Standing) {
    const root = visual.root, p = st.spot;
    if (root.position.distanceToSquared(p) < 1e-6 && Math.abs(root.rotation.y - st.heading) < 1e-6) return;
    root.rotation.set(0, st.heading, 0);
    if (visual.spec.train) {
      // a train's cars follow the path its leading bogie has driven: a step to another place on the grid would bend
      // them. A jump of more than its length starts a straight train (as at a respawn): out, and back in
      root.position.set(p.x, p.y - 1000, p.z);
      visual.refresh();
    }
    root.position.copy(p);
    visual.refresh();
  }

  private discard(visual: CarVisual | null) {
    if (!visual) return;
    this.group.remove(visual.root);
    visual.dispose();
  }

  /**
   * What the camera frames: a point of the line-up (on the road, into `focus`), its distance along the course, the
   * scale of the view (1 = the garage's single car) and the radius around the point the key light has to cover (m).
   */
  frame(focus: THREE.Vector3, front?: THREE.Vector3, back?: THREE.Vector3): { s: number; scale: number; radius: number } {
    const { s0, s1, l0, l1 } = this.span;
    const s = focusOf(this.span);
    this.track.pointAt(s, (l0 + l1) / 2, focus);
    // (the two ends of the stretch of road the vehicles take)
    if (front) this.track.pointAt(s1, (l0 + l1) / 2, front);
    if (back) this.track.pointAt(s0, (l0 + l1) / 2, back);
    return { s, scale: this.scale, radius: Math.hypot(Math.max(s1 - s, s - s0), (l1 - l0) / 2) };
  }

  /** World position of a seat's name tag: above the vehicle (a train: above its cab). */
  tagAnchor(slot: number, out: THREE.Vector3): boolean {
    const st = this.slots.get(slot);
    const v = st?.visual;
    if (!st || !v) return false;
    out.copy(v.root.position);
    out.y += st.top + 0.3;
    if (v.spec.train) {
      out.x -= Math.sin(st.heading) * 3;
      out.z -= Math.cos(st.heading) * 3;
    }
    return true;
  }

  /** What stands in each seat now (tests, debugging): the vehicle shown, and the one on its way if any. */
  state(): { slot: number; carId: CarId | null; livery: string | null; browsing: boolean; pending: CarId | null; x: number; y: number; z: number }[] {
    return [...this.slots.values()]
      .sort((a, b) => a.slot - b.slot)
      .map((st) => ({
        slot: st.slot,
        carId: st.visual?.spec.id ?? null,
        livery: st.visual ? st.key.split('|')[1] || null : null,
        browsing: st.entry.browsing,
        pending: st.pending ? st.pending.visual.spec.id : null,
        x: st.spot.x,
        y: st.spot.y,
        z: st.spot.z,
      }));
  }

  dispose() {
    this.disposed = true;
    for (const st of this.slots.values()) {
      this.discard(st.visual);
      this.discard(st.pending?.visual ?? null);
      st.visual = null;
      st.pending = null;
    }
    this.slots.clear();
    this.group.removeFromParent();
  }
}
