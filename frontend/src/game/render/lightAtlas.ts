import * as THREE from 'three';

/**
 * The one texture in which a course's fixed light is kept for the shaders: the far shade (`farShade.ts`), the grid
 * of the street lamps and their table (`lampField.ts`). One texture and not three, because every lit material reads
 * them and a fragment shader may sample 16 textures (WebGPU's default limit, and many phones' in WebGL 2): the
 * ground and the cast concrete already used 14. Bytes only, read texel by texel (`textureLoad`): no sampler blends
 * across the parts, and no float texture is needed anywhere.
 */

/** cells along each side of the far shade's grid */
export const SHADE_SIZE = 768;
/** cells along each side of the lamps' grid, and lamps a course can have (one byte names one: 0 = none) */
export const FIELD_SIZE = 512, FIELD_TABLE = 256;
/** the rows where the lamps' grid and their table (two rows) begin */
export const CELLS_ROW = SHADE_SIZE, TABLE_ROW = SHADE_SIZE + FIELD_SIZE;
const WIDTH = SHADE_SIZE, HEIGHT = TABLE_ROW + 4;

export class LightAtlas {
  readonly data = new Uint8Array(WIDTH * HEIGHT * 4);
  readonly texture: THREE.DataTexture;

  constructor() {
    const t = (this.texture = new THREE.DataTexture(this.data, WIDTH, HEIGHT, THREE.RGBAFormat, THREE.UnsignedByteType));
    t.magFilter = t.minFilter = THREE.NearestFilter;
    t.generateMipmaps = false;
    t.name = 'course-light';
    t.needsUpdate = true;
  }

  /** Writes rows of `width` texels (4 bytes each), the first at `row`. */
  put(row: number, width: number, src: Uint8Array) {
    const rows = src.length / (width * 4);
    if (width === WIDTH) this.data.set(src, row * WIDTH * 4);
    else for (let r = 0; r < rows; r++) this.data.set(src.subarray(r * width * 4, (r + 1) * width * 4), (row + r) * WIDTH * 4);
    this.texture.needsUpdate = true;
  }
}
