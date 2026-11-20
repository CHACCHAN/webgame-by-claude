import * as THREE from 'three';
import { describe, expect, it } from 'vitest';
import { SWING_SAMPLES, clearSwing, fitBox, fitFraming, hiddenShare, inside, roadsideOccluders, swingSamples, vehicleHull, type Framing, type ScreenBox } from './garageFit';

const H = Math.tan((19 * Math.PI) / 180) * 8.6;
const aspect = 844 / 390;
// a phone's strip right of the list, above the card (844×390: x 437–844, y 30–103)
const strip: ScreenBox = { left: (2 * 437) / 844 - 1, right: 1, top: 1 - (2 * 30) / 390, bottom: 1 - (2 * 103) / 390 };

/**
 * a vehicle whose picture is a box `w` × `h` (NDC) around (cx, cy) under the framing `at` (right −3.3, up −2, zoom
 * 1.6), that the aim moves and the distance shrinks as the garage's camera does
 */
const model = (cx: number, cy: number, w: number, h: number, at: Framing = { right: -3.3, up: -2, zoom: 1.6 }) => (f: Framing): ScreenBox => {
  const x = cx - (f.right - at.right) / (H * aspect), y = cy - (f.up - at.up) / H, s = at.zoom / f.zoom;
  return { left: x - (w / 2) * s, right: x + (w / 2) * s, top: y + (h / 2) * s, bottom: y - (h / 2) * s };
};
const centre = (b: ScreenBox) => [(b.left + b.right) / 2, (b.top + b.bottom) / 2];

describe('the car select framing checked against the vehicle', () => {
  it('keeps the picker framing while the vehicle stands inside its part of the screen', () => {
    const frame = { right: -3.3, up: -2, zoom: 1.6 };
    const at = model(0.5, 0.6, 0.3, 0.2);
    expect(inside(at(frame), fitBox(strip, aspect))).toBe(true);
    expect(fitFraming(frame, strip, aspect, at, 4)).toEqual(frame);
  });

  it('steps back and puts the vehicle in the middle when it does not fit', () => {
    const frame = { right: -3.3, up: -2, zoom: 1.6 };
    // (too big for the strip and too low: the phone's case)
    const at = model(0.45, 0.55, 0.9, 0.7);
    const fit = fitFraming(frame, strip, aspect, at, 4);
    expect(fit.zoom).toBeGreaterThan(frame.zoom);
    const box = fitBox(strip, aspect);
    expect(inside(at(fit), box)).toBe(true);
    const [x, y] = centre(at(fit)), [bx, by] = centre(box);
    expect(x).toBeCloseTo(bx, 2);
    expect(y).toBeCloseTo(by, 2);
  });

  it('only aims anew when the vehicle is small enough but out of place', () => {
    const frame = { right: -3.3, up: -2, zoom: 1.6 };
    const at = model(0.5, 0.3, 0.3, 0.15);
    const fit = fitFraming(frame, strip, aspect, at, 4);
    expect(fit.zoom).toBe(frame.zoom);
    expect(inside(at(fit), fitBox(strip, aspect))).toBe(true);
  });

  it('never steps back beyond the bound, and leaves a framing alone without room', () => {
    const frame = { right: -3.3, up: -2, zoom: 1.6 };
    const fit = fitFraming(frame, strip, aspect, model(0.5, 0.6, 20, 20), 4);
    expect(fit.zoom).toBeLessThanOrEqual(4);
    expect(Number.isFinite(fit.right + fit.up)).toBe(true);
    const none = { left: 1, right: 1, top: 1, bottom: 1 };
    expect(fitFraming(frame, none, aspect, model(0.5, 0.6, 1, 1), 4)).toEqual(frame);
  });

  it('takes the drawn parts of a vehicle, their extremes included, and leaves glows and hidden parts out', () => {
    const root = new THREE.Group();
    const body = new THREE.Mesh(new THREE.BoxGeometry(2, 1, 4, 8, 8, 8), new THREE.MeshStandardMaterial());
    body.position.set(10, 0.5, 0);
    const glow = new THREE.Mesh(new THREE.BoxGeometry(50, 50, 50), new THREE.MeshBasicMaterial({ transparent: true, depthWrite: false }));
    const hidden = new THREE.Mesh(new THREE.BoxGeometry(40, 40, 40), new THREE.MeshStandardMaterial());
    hidden.visible = false;
    root.add(body, glow, hidden);
    const hull = vehicleHull(root, 50);
    const xs = [], ys = [], zs = [];
    for (let i = 0; i < hull.length; i += 3) xs.push(hull[i]), ys.push(hull[i + 1]), zs.push(hull[i + 2]);
    expect(Math.min(...xs)).toBeCloseTo(9, 6);
    expect(Math.max(...xs)).toBeCloseTo(11, 6);
    expect([Math.min(...ys), Math.max(...ys)]).toEqual([0, 1]);
    expect([Math.min(...zs), Math.max(...zs)]).toEqual([-2, 2]);
    expect(hull.length / 3).toBeLessThan(80);
  });

  // a car-sized box at the origin, seen from 12 m along +x, 2 m up
  const car = () => {
    const root = new THREE.Group();
    const body = new THREE.Mesh(new THREE.BoxGeometry(2, 1.2, 4, 6, 6, 6), new THREE.MeshStandardMaterial());
    body.position.y = 0.6;
    root.add(body);
    return vehicleHull(root, 300);
  };
  const eye = new THREE.Vector3(12, 2, 0);
  const scenery = (...parts: THREE.Object3D[]) => {
    const g = new THREE.Group();
    g.add(...parts);
    return roadsideOccluders(g, new THREE.Vector3(), 40, (o) => o.name === 'trees');
  };

  it('finds what by the road hides the vehicle from the camera, and nothing beside the line of sight', () => {
    const hull = car();
    // a 1.6 m name board on a post, 5 m in front of the camera, facing it
    const board = () => {
      const plate = new THREE.Mesh(new THREE.PlaneGeometry(1.6, 1.6), new THREE.MeshStandardMaterial());
      plate.position.set(7, 1.8, 0.4);
      plate.rotation.y = Math.PI / 2;
      return plate;
    };
    const across = scenery(board());
    expect(across.length).toBe(1);
    expect(hiddenShare(eye, hull, across)).toBeGreaterThan(0.3);
    // the same board 3 m to the side of the line
    const aside = board();
    aside.position.z = 3.4;
    expect(hiddenShare(eye, hull, scenery(aside))).toBe(0);
    // behind the vehicle it hides nothing
    const behind = board();
    behind.position.x = -4;
    expect(hiddenShare(eye, hull, scenery(behind))).toBe(0);
  });

  it('looks at the triangles of a part, not its box', () => {
    const hull = car();
    // a lamp: a pole beside the line of sight and its arm over it (their box covers the line, they do not)
    const lamp = new THREE.Mesh(
      (() => {
        const pole = new THREE.CylinderGeometry(0.08, 0.08, 6, 6).translate(7, 3, 2.6);
        const arm = new THREE.BoxGeometry(0.1, 0.1, 3).translate(7, 6, 1.1);
        const g = new THREE.BufferGeometry();
        const a = pole.toNonIndexed().attributes.position.array, b = arm.toNonIndexed().attributes.position.array;
        g.setAttribute('position', new THREE.Float32BufferAttribute([...a, ...b], 3));
        return g;
      })(),
      new THREE.MeshStandardMaterial(),
    );
    const occ = scenery(lamp);
    expect(hiddenShare(eye, hull, occ)).toBe(0);
    // (its box does lie across the line of sight)
    const box = lamp.geometry.boundingBox!;
    expect(box.min.z < 0.5 && box.max.y > 2).toBe(true);
    // a lump in the same place hides it
    const lump = new THREE.Mesh(new THREE.BoxGeometry(0.4, 3, 2.4, 20, 20, 20), new THREE.MeshStandardMaterial());
    lump.position.set(7, 1.5, 0);
    expect(hiddenShare(eye, hull, scenery(lump))).toBeGreaterThan(0.3);
    // the count can stop early: past the limit is enough to know
    expect(hiddenShare(eye, hull, scenery(lump), 1, 0.05)).toBeGreaterThan(0.05);
  });

  it('keeps the camera to the widest clear part of its swing', () => {
    // a board in the way at the swing's right end (from 0.6 on), a post at −0.5
    expect(clearSwing(17, (s) => s < 0.6 && Math.abs(s + 0.5) > 0.01)).toEqual([-0.375, 0.5]);
    expect(clearSwing(17, () => true)).toEqual([-1, 1]);
    expect(clearSwing(17, () => false)).toBeNull();
    expect(swingSamples()).toEqual(SWING_SAMPLES);
    const part = swingSamples([-0.5, 0.25]);
    expect(part[0]).toBeCloseTo(-0.5, 9);
    expect(part[part.length - 1]).toBeCloseTo(0.25, 9);
  });

  it('takes of a long merged part the triangles near the garage, and leaves out a skipped group, glows and instances scaled away', () => {
    const hull = car();
    // a wall 200 m long, 3 m high, across the line of sight 7 m out
    const wall = new THREE.Mesh(new THREE.BoxGeometry(0.2, 3, 200, 1, 1, 50), new THREE.MeshStandardMaterial());
    wall.position.set(7, 1.5, 0);
    const cells = scenery(wall);
    expect(cells.length).toBeGreaterThan(1);
    // (only what lies within reach, 40 m, is kept)
    for (const c of cells) expect(Math.hypot(c.centre.x, c.centre.z)).toBeLessThan(40 + 6);
    expect(hiddenShare(eye, hull, cells)).toBeGreaterThan(0.9);
    const trees = new THREE.Group();
    trees.name = 'trees';
    const crown = new THREE.Mesh(new THREE.SphereGeometry(1.5), new THREE.MeshStandardMaterial());
    crown.position.set(7, 1.8, 0);
    trees.add(crown);
    const glow = new THREE.Mesh(new THREE.BoxGeometry(2, 2, 2), new THREE.MeshBasicMaterial({ transparent: true, depthWrite: false }));
    glow.position.set(7, 1.8, 0);
    const cones = new THREE.InstancedMesh(new THREE.ConeGeometry(0.2, 0.7), new THREE.MeshStandardMaterial(), 3);
    cones.setMatrixAt(0, new THREE.Matrix4().makeTranslation(7, 0.35, 0));
    cones.setMatrixAt(1, new THREE.Matrix4().makeScale(0, 0, 0));
    cones.setMatrixAt(2, new THREE.Matrix4().makeTranslation(70, 0.35, 0));
    const occ = scenery(trees, glow, cones);
    // (only the cone in the line, the one far off is out of reach)
    expect(occ.length).toBe(1);
    expect(occ[0].radius).toBeLessThan(1);
  });
});
