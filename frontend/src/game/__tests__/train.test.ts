import { describe, expect, it } from 'vitest';
import * as THREE from 'three';
import { CAR_SPECS } from '../vehicle/carSpecs';
import { TRAIN_ORDER } from '../vehicle/trains';
import { buildTrain, TRAIN } from '../render/TrainModel';

/** Car centres (world) of a built train after its anchor drove along `path`. */
function drive(path: (t: number) => { p: THREE.Vector3; heading: number }, steps: number) {
  const rig = buildTrain(CAR_SPECS.e231);
  const scene = new THREE.Group();
  const anchor = new THREE.Group();
  scene.add(anchor);
  anchor.add(rig.root);
  for (let k = 0; k <= steps; k++) {
    const { p, heading } = path(k / steps);
    anchor.position.copy(p);
    anchor.rotation.set(0, heading, 0);
    rig.train.update(rig.root);
  }
  scene.updateMatrixWorld(true);
  const consist = rig.root.children.find((c) => !c.matrixAutoUpdate && c.children.length === TRAIN.cars)!;
  return consist.children.map((car) => new THREE.Vector3().setFromMatrixPosition(car.matrixWorld));
}

describe('trains', () => {
  it('every train builds (three cars, both cab ends)', () => {
    for (const id of TRAIN_ORDER) {
      const rig = buildTrain(CAR_SPECS[id]);
      expect(rig.wheels).toHaveLength(4);
      expect(rig.anchors.headlights).toHaveLength(2);
    }
  });

  it('the cars follow the path of the leading bogie round a bend, 20 m apart', () => {
    // a 40 m radius bend driven anticlockwise from the +x axis, heading along the tangent
    const R = 40;
    const centres = drive((t) => {
      const a = t * Math.PI * 1.2;
      return { p: new THREE.Vector3(R * Math.cos(a), 0, R * Math.sin(a)), heading: Math.atan2(-Math.sin(a), Math.cos(a)) };
    }, 600);
    for (const c of centres) {
      // a car's centre sits inside the arc by the chord sag of its bogies (13.8 m chord: ~0.6 m at R 40)
      const r = Math.hypot(c.x, c.z);
      expect(r).toBeGreaterThan(R - 1.2);
      expect(r).toBeLessThan(R + 0.1);
    }
    for (let k = 1; k < centres.length; k++) {
      const gap = centres[k].distanceTo(centres[k - 1]);
      expect(gap).toBeGreaterThan(TRAIN.pitch * 0.95);
      expect(gap).toBeLessThan(TRAIN.pitch * 1.01);
    }
  });

  it('the headlights turn with the leading car in a bend (not with the simulated bogie)', async () => {
    const { CarVisual } = await import('../render/CarVisual');
    const visual = new CarVisual(CAR_SPECS.e231, { headlights: true, shadows: false, rideHeight: 0 });
    const scene = new THREE.Group();
    scene.add(visual.root);
    const R = 40;
    let worst = 0;
    for (let k = 0; k <= 600; k++) {
      const a = (k / 600) * Math.PI * 1.2;
      // the bogie's own yaw wanders (steering, slides): ±0.25 rad off the tangent
      visual.root.position.set(R * Math.cos(a), 0, R * Math.sin(a));
      visual.root.rotation.set(0, Math.atan2(-Math.sin(a), Math.cos(a)) + 0.25 * Math.sin(k * 0.3), 0);
      visual.syncFromPose({ position: visual.root.position, quaternion: visual.root.quaternion }, 1 / 60);
      if (k < 300) continue;
      scene.updateMatrixWorld(true);
      // the leading car: first car of the consist (the container that cancels the rig's own transform)
      const car = visual.rig.root.children.find((c) => !c.matrixAutoUpdate && c.children.length === TRAIN.cars)!.children[0];
      const fwd = new THREE.Vector3(0, 0, 1).transformDirection(car.matrixWorld).setY(0).normalize();
      const spot = visual.headlights[0];
      const beam = new THREE.Vector3().setFromMatrixPosition(spot.target.matrixWorld).sub(new THREE.Vector3().setFromMatrixPosition(spot.matrixWorld)).setY(0).normalize();
      worst = Math.max(worst, fwd.angleTo(beam));
    }
    expect(worst).toBeLessThan(0.01);
  });

  it('backing up pulls the cars back along the same path', () => {
    const out = (t: number) => ({ p: new THREE.Vector3(0, 0, t * 60), heading: 0 });
    const ahead = drive(out, 300);
    const back = drive((t) => (t < 0.5 ? out(t * 2) : out(1 - (t - 0.5))), 600);
    // drove 60 m forward then 30 m back: every car 30 m further back, still on the line
    ahead.forEach((c, k) => {
      expect(back[k].z).toBeCloseTo(c.z - 30, 0);
      expect(Math.abs(back[k].x)).toBeLessThan(0.01);
    });
  });
});
