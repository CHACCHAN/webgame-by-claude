import * as THREE from 'three';
import { CELLS_ROW, FIELD_SIZE, FIELD_TABLE, TABLE_ROW, type LightAtlas } from './lightAtlas';

/**
 * The street lamps' light, for every lamp of a course at once and at any distance from the camera.
 *
 * The lamps used to be six real point lights handed to the lamps nearest the camera, faded out between 90 and 200 m,
 * and a baked light map on the road and the ground: a lamp further off than that (or the seventh of a rock shed's
 * row, 14 m apart) lit nothing but its pool on the asphalt, so walls, rails, trees and the wet road's shine under it
 * were there near the camera and gone further away (the owner's report, 11-12). Lamps do not move, so which of them
 * reach a place is worked out once per course: a grid over the ground (a cell lists up to four lamps whose light
 * reaches into it) and a table of the lamps. The shader of the one light that stands for them all (`LampFieldNode`)
 * looks its cell up and lights the pixel from those four. Four per pixel instead of six, no pool to hand round,
 * nothing that pops, and no light map: the pool under a lamp is part of the same light (`LAMP_BEAM`).
 *
 * The light is one object of the fixed set (`LightRig`); another course writes other numbers into the same texture.
 */

/** a lamp's light to all sides, as a point light: how far it reaches (m), how it falls off, how bright (cd, × the preset's `lampsOn`) */
export const LAMP_REACH = 42, LAMP_DECAY = 1.7, LAMP_CANDELA = 170;
/**
 * The pool under a lamp: what its reflector throws down, ∝ cos² of the angle from straight down, as light on a
 * surface (the old light map's numbers: 17 × 55 cos³ / (d² + 4) on level ground, capped where it would saturate).
 * A material takes `userData.lampBeam` of it (the road 1, verges less, anything else none unless it says so).
 */
export const LAMP_BEAM = 17, BEAM_SHAPE = 55;
/**
 * The point light hangs this far below the fixture, never right against it: a point light a few cm from the
 * rock-shed ceiling or a cutting made a blinding hot spot that flooded the screen with bloom.
 */
export const LAMP_LIGHT_DROP = 0.9;
/** lamps a cell can list */
export const FIELD_LAMPS = 4;
/** the smallest cell (m): a long course gets wider ones, so that the grid always covers it */
const CELL = 8;

export interface FieldLamp {
  position: THREE.Vector3;
  color: THREE.Color;
}

export interface FieldLayout {
  /** FIELD_SIZE² × 4 bytes: per cell the lamps that reach into it (index + 1, 0 = none) */
  cells: Uint8Array;
  /**
   * FIELD_TABLE × 2 rows of four bytes. Row 0: the fixture's x and z, 16 bits each (high byte first), as a share of
   * the grid's side. Row 1: its height (16 bits of `yRange` above `yBase`), which of the two colours it has
   * (0 `warm` … 255 `cool`), 255 for a lamp (entry 0: no lamp, all zero).
   */
  table: Uint8Array;
  /** the grid's corner (x, z) and the size of a cell */
  x0: number;
  z0: number;
  cell: number;
  yBase: number;
  yRange: number;
  /** the lamps' two colours (a course has sodium lamps and LED ones; a third colour would be drawn as the nearer of them) */
  warm: THREE.Color;
  cool: THREE.Color;
  /** cells that more than four lamps reach into, and the most that reach into one (the nearest four are kept) */
  crowded: number;
  most: number;
}

const put16 = (out: Uint8Array, o: number, share: number) => {
  const v = Math.min(65535, Math.max(0, Math.round(share * 65535)));
  out[o] = v >> 8;
  out[o + 1] = v & 255;
};
const get16 = (a: Uint8Array, o: number) => (a[o] * 256 + a[o + 1]) / 65535;

/** Which lamps light which piece of ground. */
export function layoutLamps(lamps: readonly FieldLamp[]): FieldLayout {
  const cells = new Uint8Array(FIELD_SIZE * FIELD_SIZE * 4);
  const table = new Uint8Array(FIELD_TABLE * 2 * 4);
  const n = Math.min(lamps.length, FIELD_TABLE - 1);
  const warm = new THREE.Color(0, 0, 0), cool = new THREE.Color(0, 0, 0);
  if (!n) return { cells, table, x0: 0, z0: 0, cell: CELL, yBase: 0, yRange: 1, warm, cool, crowded: 0, most: 0 };
  let xa = Infinity, xb = -Infinity, za = Infinity, zb = -Infinity, ya = Infinity, yb = -Infinity;
  for (let i = 0; i < n; i++) {
    const p = lamps[i].position;
    xa = Math.min(xa, p.x), xb = Math.max(xb, p.x), za = Math.min(za, p.z), zb = Math.max(zb, p.z), ya = Math.min(ya, p.y), yb = Math.max(yb, p.y);
  }
  // a ring of empty cells all round: whatever lies outside the grid reads its border and gets no lamp
  const cell = Math.max(CELL, (Math.max(xb - xa, zb - za) + 2 * LAMP_REACH) / (FIELD_SIZE - 3));
  const x0 = xa - LAMP_REACH - cell, z0 = za - LAMP_REACH - cell;
  const side = FIELD_SIZE * cell, yBase = ya - 1, yRange = yb - ya + 2;
  warm.copy(lamps[0].color);
  cool.copy(lamps.find((l) => !l.color.equals(warm))?.color ?? warm);
  const far = (a: THREE.Color, b: THREE.Color) => (a.r - b.r) ** 2 + (a.g - b.g) ** 2 + (a.b - b.b) ** 2;
  for (let i = 0; i < n; i++) {
    const { position: p, color: c } = lamps[i];
    put16(table, (i + 1) * 4, (p.x - x0) / side);
    put16(table, (i + 1) * 4 + 2, (p.z - z0) / side);
    put16(table, (FIELD_TABLE + i + 1) * 4, (p.y - yBase) / yRange);
    table[(FIELD_TABLE + i + 1) * 4 + 2] = far(c, cool) < far(c, warm) ? 255 : 0;
    table[(FIELD_TABLE + i + 1) * 4 + 3] = 255;
  }
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
  return { cells, table, x0, z0, cell, yBase, yRange, warm, cool, crowded, most };
}

/** where the table puts lamp `i`'s fixture (what the shader reads back: for tests) */
export function lampAt(l: FieldLayout, i: number, out = new THREE.Vector3()) {
  const side = FIELD_SIZE * l.cell;
  return out.set(l.x0 + get16(l.table, (i + 1) * 4) * side, l.yBase + get16(l.table, (FIELD_TABLE + i + 1) * 4) * l.yRange, l.z0 + get16(l.table, (i + 1) * 4 + 2) * side);
}

const layouts = new WeakMap<readonly FieldLamp[], FieldLayout>();

/**
 * The one light that is all the street lamps (its shader: `lampFieldNode.ts`). `intensity` is a lamp's light to all
 * sides in candela, `beam` the strength of the pool under it.
 */
export class LampField extends THREE.Light {
  readonly isLampField = true;
  override readonly type = 'LampField';
  beam = 0;
  /** the grid's corner (x, z) and cells per metre */
  readonly frame = new THREE.Vector3(0, 0, 1 / CELL);
  /** what the table's numbers stand for: metres per unit of x / z, the lowest fixture's height, metres per unit of height */
  readonly scale = new THREE.Vector3(1, 0, 1);
  readonly warm = new THREE.Color(0, 0, 0);
  readonly cool = new THREE.Color(0, 0, 0);

  constructor(readonly atlas: LightAtlas) {
    super('#ffffff', 0);
  }

  /** The lamps of the course that is shown (an empty list: none). Their layout is worked out once per list. */
  show(lamps: readonly FieldLamp[]) {
    let l = layouts.get(lamps);
    if (!l) layouts.set(lamps, (l = layoutLamps(lamps)));
    this.atlas.put(CELLS_ROW, FIELD_SIZE, l.cells);
    this.atlas.put(TABLE_ROW, FIELD_TABLE, l.table);
    this.frame.set(l.x0, l.z0, 1 / l.cell);
    // (a texel's two bytes come out of the shader as high × 256 + low, 0 … 65535)
    this.scale.set((FIELD_SIZE * l.cell) / 65535, l.yBase, l.yRange / 65535);
    this.warm.copy(l.warm);
    this.cool.copy(l.cool);
    return l;
  }
}
