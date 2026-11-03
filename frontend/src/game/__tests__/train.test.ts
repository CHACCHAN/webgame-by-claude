import { describe, expect, it } from 'vitest';
import * as THREE from 'three';
import { CAR_SPECS } from '../vehicle/carSpecs';
import { TRAIN_ORDER, trainBogiePath, trainNoseZ, trainTailZ } from '../vehicle/trains';
import { buildTrain, fitLamps, TRAIN } from '../render/TrainModel';

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

  it("a model's lamps sit on its cab faces, facing out (a sloped nose too)", () => {
    const mat = new THREE.MeshBasicMaterial();
    // a box car 20 m long, and a car whose nose slopes back 45° below 2 m
    const flat = new THREE.Group();
    flat.add(new THREE.Mesh(new THREE.BoxGeometry(2.8, 3.6, 20).translate(0, 1.8, 0), mat));
    const head = fitLamps(flat, { x: 0.8, y: 1.2, w: 0.2, h: 0.2 }, 1, 20, mat);
    expect(head).toHaveLength(2);
    for (const p of head) expect(p.z).toBeCloseTo(10.015, 3);
    expect(head.map((p) => p.x).sort()).toEqual([-0.8, 0.8]);
    const tail = fitLamps(flat, { x: 1.1, y: 1.2, w: 0.2, h: 0.2 }, -1, 20, mat);
    for (const p of tail) expect(p.z).toBeCloseTo(-10.015, 3);
    const nose = new THREE.Group();
    const wedge = new THREE.BoxGeometry(2.8, 4, 4).rotateX(Math.PI / 4).translate(0, 0, 10);
    nose.add(new THREE.Mesh(wedge, mat));
    fitLamps(nose, { x: 0.5, y: 0.5, w: 0.3, h: 0.1 }, 1, 20, mat);
    const lens = nose.children[1];
    const out = new THREE.Vector3(0, 0, 1).applyQuaternion(lens.quaternion);
    // on the 45° face: facing forward and up alike
    expect(out.z).toBeCloseTo(Math.SQRT1_2, 2);
    expect(Math.abs(out.y)).toBeCloseTo(Math.SQRT1_2, 2);
  });

  it('each recorded motor sound and running loop is shipped; the motor maps rising time to rising speed', async () => {
    const { existsSync } = await import('node:fs');
    const { TRAIN_INFO } = await import('../vehicle/trains');
    for (const id of TRAIN_ORDER) {
      const run = TRAIN_INFO[id].runningSound;
      if (run) {
        expect(existsSync(`public/audio/${run.file}.mp3`)).toBe(true);
        expect(run.loop[1] - run.loop[0]).toBeGreaterThan(10);
        expect(run.speed).toBeGreaterThan(30);
      }
      const rec = TRAIN_INFO[id].motorSound;
      if (!rec) continue;
      expect(existsSync(`public/audio/${rec.file}.mp3`)).toBe(true);
      expect(rec.knots[0][1]).toBe(0);
      for (let k = 1; k < rec.knots.length; k++) {
        expect(rec.knots[k][0]).toBeGreaterThan(rec.knots[k - 1][0]);
        expect(rec.knots[k][1]).toBeGreaterThan(rec.knots[k - 1][1]);
      }
    }
  });

  it('the VVVF drive: speed → inverter Hz from gear, wheel and poles; slip under power and braking; coasting keeps the brake pattern', async () => {
    const { E231_MITSUBISHI, hzPerKmh, vvvfDrive } = await import('../vehicle/vvvf');
    // 99:14 gear, 0.86 m wheels, 4-pole motors: ~1.45 Hz per km/h
    const k = hzPerKmh(E231_MITSUBISHI, 0.86);
    expect(k).toBeCloseTo(1.454, 2);
    const d = { hz: 0, rotorHz: 0, braking: false, powerOff: true };
    expect(vvvfDrive(E231_MITSUBISHI, 0.86, 50, 1, false, d)).toMatchObject({ braking: false, powerOff: false });
    expect(d.hz).toBeCloseTo(50 * k + 2, 6);
    expect(vvvfDrive(E231_MITSUBISHI, 0.86, 50, -1, false, d)).toMatchObject({ braking: true, powerOff: false });
    expect(d.hz).toBeCloseTo(50 * k - 2, 6);
    expect(vvvfDrive(E231_MITSUBISHI, 0.86, 50, 0, true, d)).toMatchObject({ braking: true, powerOff: true });
    expect(d.hz).toBeCloseTo(d.rotorHz, 6);
    expect(vvvfDrive(E231_MITSUBISHI, 0.86, 2, -1, true, d)).toMatchObject({ braking: true, powerOff: true });
    expect(vvvfDrive(E231_MITSUBISHI, 0.86, 0, 1, false, d).hz).toBeCloseTo(2, 6);
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

  it('cars of unequal length meet at their couplers', () => {
    // equal cars: bogies at 0 / 13.8, 20 / 33.8, 40 / 53.8; nose and tail half a car from the origin
    const even = { carLength: 20, bogies: 13.8 };
    expect(trainBogiePath(even)).toEqual([[0, 13.8], [20, 33.8], [40, 53.8]]);
    expect(trainNoseZ(even)).toBeCloseTo(10, 9);
    expect(trainTailZ(even)).toBeCloseTo(10, 9);
    // long-nosed end cars (the trailing one runs turned round: its nose last)
    const consist = [{ length: 26.5, bogies: 17.5, front: 7 }, { length: 25, bogies: 17.5, front: 3.75 }, { length: 26.5, bogies: 17.5, front: 2 }];
    const path = trainBogiePath({ carLength: 25, bogies: 17.5, consist });
    // car 0's rear coupler is 26.5 - 7 = 19.5 m behind its leading bogie; car 1's leading bogie 3.75 m behind that
    expect(path[0]).toEqual([0, 17.5]);
    expect(path[1][0]).toBeCloseTo(23.25, 9);
    expect(path[2][0]).toBeCloseTo(23.25 + 25 - 3.75 + 2, 9);
    expect(trainNoseZ({ carLength: 25, bogies: 17.5, consist })).toBeCloseTo(8.75 + 7, 9);
    expect(trainTailZ({ carLength: 25, bogies: 17.5, consist })).toBeCloseTo(26.5 - 2 - 8.75, 9);
  });
});
