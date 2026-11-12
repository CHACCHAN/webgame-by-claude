import { describe, expect, it } from 'vitest';
import * as THREE from 'three';
import { FIELD_LAMPS, FIELD_SIZE, LAMP_REACH, LampField, layoutLamps, type FieldLamp } from './lampField';

const lamp = (x: number, z: number, y = 7): FieldLamp => ({ position: new THREE.Vector3(x, y, z), color: new THREE.Color(1, 0.6, 0.3) });
/** the lamps (indices) the shader would light the place from */
const listed = (l: ReturnType<typeof layoutLamps>, x: number, z: number) => {
  const cell = (v: number) => Math.min(FIELD_SIZE - 1, Math.max(0, Math.floor(v / l.cell)));
  const o = (cell(z - l.z0) * FIELD_SIZE + cell(x - l.x0)) * 4;
  return [...l.cells.slice(o, o + 4)].filter((v) => v > 0).map((v) => v - 1);
};

describe('the lamps\' field', () => {
  it('lists a lamp wherever its light reaches, and nowhere else', () => {
    const lamps = [lamp(100, -300), lamp(900, 250)];
    const l = layoutLamps(lamps);
    for (let i = 0; i < 400; i++) {
      const a = i * 2.4, r = (i % 40) * 3;
      const x = 100 + Math.cos(a) * r, z = -300 + Math.sin(a) * r;
      if (r < LAMP_REACH) expect(listed(l, x, z)).toContain(0);
      // (a cell lists what reaches any part of it)
      if (r > LAMP_REACH + l.cell * 1.5) expect(listed(l, x, z)).toEqual([]);
    }
    expect(listed(l, 900, 250)).toEqual([1]);
    expect(l.crowded).toBe(0);
  });

  it('gives a place outside the grid no lamp', () => {
    const l = layoutLamps([lamp(0, 0), lamp(3000, 500)]);
    for (const [x, z] of [[-9000, 0], [9000, 9000], [0, -5000], [1500, 4000]]) expect(listed(l, x, z)).toEqual([]);
  });

  it('keeps the four nearest where more reach (a rock shed\'s row, 14 m apart)', () => {
    const lamps = Array.from({ length: 20 }, (_, i) => lamp(i * 14, 0));
    const l = layoutLamps(lamps);
    expect(l.most).toBeGreaterThan(FIELD_LAMPS);
    const at = listed(l, 140, 1);
    expect(at).toHaveLength(FIELD_LAMPS);
    // what is left out is further than 21 m along the row: under a hundredth of the light at that place
    for (const i of at) expect(Math.abs(lamps[i].position.x - 140)).toBeLessThanOrEqual(30);
  });

  it('covers a long course with wider cells', () => {
    const l = layoutLamps([lamp(0, 0), lamp(60, 8500)]);
    expect(l.cell).toBeGreaterThan(8);
    expect(listed(l, 60, 8500 - 20)).toEqual([1]);
    expect(listed(l, 10, 30)).toEqual([0]);
  });

  it('is one light whose textures stay the same objects from course to course', () => {
    const field = new LampField();
    const { cells, table } = field;
    const a = [lamp(0, 0)], b = [lamp(500, 500), lamp(520, 500)];
    field.show(a);
    const first = field.frame.clone();
    field.show(b);
    expect(field.cells).toBe(cells);
    expect(field.table).toBe(table);
    expect(field.frame.equals(first)).toBe(false);
    expect((table.image.data as Float32Array)[2 * 4]).toBe(520);
    field.show([]);
    expect((cells.image.data as Uint8Array).some((v) => v > 0)).toBe(false);
  });
});
