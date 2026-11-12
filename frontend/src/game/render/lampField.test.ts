import { describe, expect, it } from 'vitest';
import * as THREE from 'three';
import { FIELD_LAMPS, LAMP_REACH, LampField, lampAt, layoutLamps, type FieldLamp } from './lampField';
import { CELLS_ROW, FIELD_SIZE, LightAtlas, SHADE_SIZE, TABLE_ROW } from './lightAtlas';

const SODIUM = new THREE.Color(1, 0.6, 0.3), LED = new THREE.Color(0.8, 0.9, 1);
const lamp = (x: number, z: number, y = 7, color = SODIUM): FieldLamp => ({ position: new THREE.Vector3(x, y, z), color: color.clone() });
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

  it('keeps every fixture\'s place to a few centimetres, and which of the two colours it has', () => {
    // a course 8 km long and 700 m high: 16 bits of the grid's side are 13 cm
    const lamps = [lamp(-812.37, 4021.9, 731.25), lamp(2954.11, -3977.03, 38.4, LED), lamp(15.5, 0.25, 402.007), lamp(16.5, 30, 399, LED)];
    const l = layoutLamps(lamps);
    lamps.forEach((it, i) => {
      const p = lampAt(l, i);
      expect(Math.abs(p.x - it.position.x)).toBeLessThan(0.08);
      expect(Math.abs(p.z - it.position.z)).toBeLessThan(0.08);
      expect(Math.abs(p.y - it.position.y)).toBeLessThan(0.01);
      // row 1: 0 = the first colour met, 255 = the other; 255 says there is a lamp
      expect([...l.table.slice((256 + i + 1) * 4 + 2, (256 + i + 1) * 4 + 4)]).toEqual([it.color.equals(SODIUM) ? 0 : 255, 255]);
    });
    expect(l.warm.equals(SODIUM)).toBe(true);
    expect(l.cool.equals(LED)).toBe(true);
    // entry 0 is "no lamp": black
    expect([...l.table.slice(0, 4), ...l.table.slice(256 * 4, 257 * 4)]).toEqual([0, 0, 0, 0, 0, 0, 0, 0]);
  });

  it('is one light whose texture stays the same object from course to course', () => {
    const atlas = new LightAtlas();
    const field = new LampField(atlas);
    const texture = atlas.texture;
    const a = [lamp(0, 0)], b = [lamp(500, 500), lamp(520, 500)];
    field.show(a);
    const first = field.frame.clone();
    const l = field.show(b);
    expect(atlas.texture).toBe(texture);
    expect(field.frame.equals(first)).toBe(false);
    // the lamps' rows lie under the far shade's, each at the atlas' width
    const row = (r: number, n: number) => atlas.data.slice(r * SHADE_SIZE * 4, (r * SHADE_SIZE + n) * 4);
    expect([...row(TABLE_ROW, 3)]).toEqual([...l.table.slice(0, 12)]);
    expect([...row(TABLE_ROW + 1, 3)]).toEqual([...l.table.slice(256 * 4, 259 * 4)]);
    const j = Math.floor((500 - l.z0) / l.cell), i = Math.floor((510 - l.x0) / l.cell);
    expect([...atlas.data.slice(((CELLS_ROW + j) * SHADE_SIZE + i) * 4, ((CELLS_ROW + j) * SHADE_SIZE + i) * 4 + 4)].filter((v) => v).sort()).toEqual([1, 2]);
    expect(atlas.data.slice(0, CELLS_ROW * SHADE_SIZE * 4).some((v) => v > 0)).toBe(false);
    field.show([]);
    expect(atlas.data.slice(CELLS_ROW * SHADE_SIZE * 4, (CELLS_ROW + FIELD_SIZE) * SHADE_SIZE * 4).some((v) => v > 0)).toBe(false);
  });
});
