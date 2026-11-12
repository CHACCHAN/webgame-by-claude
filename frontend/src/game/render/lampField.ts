import * as THREE from 'three';

/**
 * The street lamps' light, for every lamp of a course at once and at any distance from the camera.
 *
 * The lamps used to be six real point lights handed to the lamps nearest the camera, faded out between 90 and 200 m:
 * a lamp further off than that (or the seventh of a rock shed's row, 14 m apart) lit nothing but its baked pool on
 * the road, so walls, rails, trees and the wet road's shine under it were there near the camera and gone further
 * away (the owner's report, 11-12). Lamps do not move, so which of them reach a place is worked out once per course:
 * a grid over the ground (a cell lists up to four lamps whose light reaches into it) and a table of the lamps. The
 * shader of the one light that stands for them all (`LampFieldNode`) looks its cell up and lights the pixel from
 * those four as point lights. Four per pixel instead of six, no pool to hand round, nothing that pops.
 *
 * The light is one object of the fixed set (`LightRig`); another course writes other numbers into the same two
 * textures.
 */

/** a lamp's light as a point light: how far it reaches (m), how it falls off, how bright (cd, × the preset's `lampsOn`) */
export const LAMP_REACH = 42, LAMP_DECAY = 1.7, LAMP_CANDELA = 170;
/**
 * The light hangs this far below the fixture, never right against it: a point light a few cm from the rock-shed
 * ceiling or a cutting made a blinding hot spot that flooded the screen with bloom.
 */
export const LAMP_LIGHT_DROP = 0.9;
/** cells along each side of the grid, lamps a cell can list, and lamps a course can have (one byte each, 0 = none) */
export const FIELD_SIZE = 512, FIELD_LAMPS = 4, FIELD_TABLE = 256;
/** the smallest cell (m): a long course gets wider ones, so that the grid always covers it */
const CELL = 8;

export interface FieldLamp {
  position: THREE.Vector3;
  color: THREE.Color;
}

export interface FieldLayout {
  /** FIELD_SIZE² × 4 bytes: per cell the lamps that reach into it (index + 1, 0 = none) */
  cells: Uint8Array;
  /** FIELD_TABLE × 2 rows of four floats: where each lamp's light is, then its colour (entry 0: no lamp) */
  table: Float32Array;
  /** the grid's corner (x, z) and the size of a cell */
  x0: number;
  z0: number;
  cell: number;
  /** cells that more than four lamps reach into, and the most that reach into one (the nearest four are kept) */
  crowded: number;
  most: number;
}

/** Which lamps light which piece of ground. */
export function layoutLamps(lamps: readonly FieldLamp[]): FieldLayout {
  const cells = new Uint8Array(FIELD_SIZE * FIELD_SIZE * 4);
  const table = new Float32Array(FIELD_TABLE * 2 * 4);
  // (no lamp: nowhere near, and black)
  table[1] = -1e5;
  const n = Math.min(lamps.length, FIELD_TABLE - 1);
  let xa = Infinity, xb = -Infinity, za = Infinity, zb = -Infinity;
  for (let i = 0; i < n; i++) {
    const { position: p, color: c } = lamps[i];
    table.set([p.x, p.y - LAMP_LIGHT_DROP, p.z, 0], (i + 1) * 4);
    table.set([c.r, c.g, c.b, 0], (FIELD_TABLE + i + 1) * 4);
    xa = Math.min(xa, p.x), xb = Math.max(xb, p.x), za = Math.min(za, p.z), zb = Math.max(zb, p.z);
  }
  if (!n) return { cells, table, x0: 0, z0: 0, cell: CELL, crowded: 0, most: 0 };
  // a ring of empty cells all round: whatever lies outside the grid reads its border and gets no lamp
  const cell = Math.max(CELL, (Math.max(xb - xa, zb - za) + 2 * LAMP_REACH) / (FIELD_SIZE - 3));
  const x0 = xa - LAMP_REACH - cell, z0 = za - LAMP_REACH - cell;
  const lists = new Map<number, number[]>();
  const span = Math.ceil(LAMP_REACH / cell) + 1;
  for (let i = 0; i < n; i++) {
    const p = lamps[i].position;
    const ci = Math.floor((p.x - x0) / cell), cj = Math.floor((p.z - z0) / cell);
    for (let j = cj - span; j <= cj + span; j++)
      for (let k = ci - span; k <= ci + span; k++) {
        if (j < 0 || k < 0 || j >= FIELD_SIZE || k >= FIELD_SIZE) continue;
        // the lamp's distance to the cell's square, on the map (the height only shortens a lamp's reach)
        const dx = Math.max(x0 + k * cell - p.x, 0, p.x - (x0 + (k + 1) * cell));
        const dz = Math.max(z0 + j * cell - p.z, 0, p.z - (z0 + (j + 1) * cell));
        if (dx * dx + dz * dz >= LAMP_REACH * LAMP_REACH) continue;
        const key = j * FIELD_SIZE + k;
        let list = lists.get(key);
        if (!list) lists.set(key, (list = []));
        list.push(i);
      }
  }
  let crowded = 0, most = 0;
  for (const [key, list] of lists) {
    most = Math.max(most, list.length);
    if (list.length > FIELD_LAMPS) {
      crowded++;
      const cx = x0 + ((key % FIELD_SIZE) + 0.5) * cell, cz = z0 + (Math.floor(key / FIELD_SIZE) + 0.5) * cell;
      const d = (i: number) => (lamps[i].position.x - cx) ** 2 + (lamps[i].position.z - cz) ** 2;
      list.sort((a, b) => d(a) - d(b));
    }
    for (let k = 0; k < Math.min(list.length, FIELD_LAMPS); k++) cells[key * 4 + k] = list[k] + 1;
  }
  return { cells, table, x0, z0, cell, crowded, most };
}

const layouts = new WeakMap<readonly FieldLamp[], FieldLayout>();

/** The one light that is all the street lamps (its shader: `lampFieldNode.ts`). `intensity` is a lamp's, in candela. */
export class LampField extends THREE.Light {
  readonly isLampField = true;
  override readonly type = 'LampField';
  readonly cells: THREE.DataTexture;
  readonly table: THREE.DataTexture;
  /** the grid's corner (x, z) and cells per metre */
  readonly frame = new THREE.Vector3(0, 0, 1 / CELL);

  constructor() {
    super('#ffffff', 0);
    const empty = layoutLamps([]);
    this.cells = new THREE.DataTexture(empty.cells, FIELD_SIZE, FIELD_SIZE, THREE.RGBAFormat, THREE.UnsignedByteType);
    this.table = new THREE.DataTexture(empty.table, FIELD_TABLE, 2, THREE.RGBAFormat, THREE.FloatType);
    for (const t of [this.cells, this.table]) {
      t.magFilter = t.minFilter = THREE.NearestFilter;
      t.generateMipmaps = false;
      t.needsUpdate = true;
    }
    this.cells.name = 'lamp-cells';
    this.table.name = 'lamp-table';
  }

  /** The lamps of the course that is shown (an empty list: none). Their layout is worked out once per list. */
  show(lamps: readonly FieldLamp[]) {
    let layout = layouts.get(lamps);
    if (!layout) layouts.set(lamps, (layout = layoutLamps(lamps)));
    (this.cells.image.data as Uint8Array).set(layout.cells);
    (this.table.image.data as Float32Array).set(layout.table);
    this.cells.needsUpdate = this.table.needsUpdate = true;
    this.frame.set(layout.x0, layout.z0, 1 / layout.cell);
    return layout;
  }
}
