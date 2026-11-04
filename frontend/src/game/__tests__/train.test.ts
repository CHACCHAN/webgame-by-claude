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

  it('running noise: every axle of the three cars clicks over each rail joint, timed by speed and geometry', async () => {
    const { RAIL_LENGTH, axles, clickTimes, runningParams } = await import('../audio/running');
    const { TRAIN_INFO } = await import('../vehicle/trains');
    // E231: 20 m cars, bogie centres 13.8 m, axles 2.1 m apart (the default), 25 m rails
    const p = runningParams(TRAIN_INFO.e231);
    expect([p.axle, p.jointSpacing]).toEqual([2.1, RAIL_LENGTH]);
    const at = axles(p).map((a) => a.at);
    expect(at.map((x) => +x.toFixed(2))).toEqual([2.05, 4.15, 15.85, 17.95, 22.05, 24.15, 35.85, 37.95, 42.05, 44.15, 55.85, 57.95]);
    // the listener sits in the middle of the first car: its own bogies loudest, then the next car's
    const g = axles(p).map((a) => a.gain);
    expect(g[1]).toBeGreaterThan(g[4]);
    expect(g[4]).toBeGreaterThan(g[8]);
    // 90 km/h = 25 m/s: one rail length a second; each axle at its offset past a joint
    const t = clickTimes(p, 90, 1);
    const expected = [2.05, 4.15, 5.85, 7.95, 10.85, 12.95, 15.85, 17.05, 17.95, 19.15, 22.05, 24.15].map((s) => s / 25);
    expect(t.length).toBe(12);
    t.forEach((v, i) => expect(v).toBeCloseTo(expected[i], 9));
    // "ta-tan": a bogie's two axles 2.1 m apart, 84 ms at 90 km/h, 63 ms at 120 km/h; the pattern repeats per rail
    expect(t[1] - t[0]).toBeCloseTo(0.084, 9);
    const t120 = clickTimes(p, 120, 3);
    expect(t120[1] - t120[0]).toBeCloseTo(2.1 / (120 / 3.6), 9);
    expect(t120[12] - t120[0]).toBeCloseTo(RAIL_LENGTH / (120 / 3.6), 9);
    // welded rail (the E5): a joint every 400 m, 2.5 m bogies
    const n = runningParams(TRAIN_INFO.e5);
    expect([n.axle, n.jointSpacing, n.sealed]).toEqual([2.5, 400, true]);
    // 2 s at 300 km/h (167 m) from 20 m before a joint: the 12 axles once
    expect(clickTimes(n, 300, 2, 380).length).toBe(12);
  });

  it('running noise: the synthesis clicks at those times and plays at the recordings\' level', async () => {
    const { RunningNoise, runningParams } = await import('../audio/running');
    const { TRAIN_INFO } = await import('../vehicle/trains');
    const rate = 48000;
    const sim = new RunningNoise(runningParams(TRAIN_INFO.e231), rate, 7);
    const hits: [number, number][] = [];
    sim.onClick = (n, _amp, axle) => hits.push([n, axle]);
    sim.kmh = 90;
    const block = new Float32Array(128);
    let ms = 0, count = 0;
    for (let b = 0; b < (4 * rate) / 128; b++) {
      sim.process(block);
      if (b * 128 < rate) continue;
      for (const v of block) (ms += v * v), count++;
    }
    // after the speed has settled each axle meets a joint every 25 m / 25 m/s = 1 s, to the sample
    const axle0 = hits.filter(([n, a]) => a === 0 && n > rate).map(([n]) => n);
    expect(axle0.length).toBeGreaterThanOrEqual(2);
    for (let i = 1; i < axle0.length; i++) expect(Math.abs(axle0[i] - axle0[i - 1] - rate)).toBeLessThanOrEqual(1);
    // its partner axle 2.1 m behind: 84 ms later
    const axle1 = hits.filter(([n, a]) => a === 1 && n > axle0[0]).map(([n]) => n);
    expect(Math.abs(axle1[0] - axle0[0] - 0.084 * rate)).toBeLessThanOrEqual(1);
    // the level: the commuter recording played at ~-22 dBFS at 110 km/h; 90 km/h is ~2-3 dB quieter
    const db = 10 * Math.log10(ms / count);
    expect(db).toBeGreaterThan(-27);
    expect(db).toBeLessThan(-21);
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
