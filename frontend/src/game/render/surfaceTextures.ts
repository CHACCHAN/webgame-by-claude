import * as THREE from 'three';

/**
 * Surface textures served from /textures: photo scans (CC0, ambientCG; see docs/ASSETS.md) and our own tiles
 * (tools/surface-textures.cjs). They are optional: anything missing falls back to the procedural textures in
 * textures.ts, and the scenery to its plain materials.
 */
export type SurfaceName =
  | 'asphalt_albedo'
  | 'asphalt_normal'
  | 'asphalt_rough'
  | 'ground_detail'
  | 'ground_normal'
  | 'rock_albedo'
  | 'rock_normal'
  | 'concrete_albedo'
  | 'concrete_normal'
  | LayerName;

/**
 * The layers of the ground and the roadside (textures/terrain/<size>/): `_c` is the colour with the surface's height
 * in alpha (from `HEIGHT_FLOOR` to 1), `_n` its normal map. `roadmarks`: cracks (r), cell ids (g), grit (b).
 * `macro`: four slow noises. `wiremesh`: a fence's wire net, cut out by its alpha.
 */
export type LayerName =
  | 'rock_c' | 'rock_n' | 'floor_c' | 'floor_n' | 'moss_c' | 'moss_n' | 'grass_c' | 'grass_n' | 'gravel_c' | 'gravel_n'
  | 'shotcrete_c' | 'shotcrete_n' | 'concrete_c' | 'concrete_n' | 'blockwall_c' | 'blockwall_n' | 'roadmarks' | 'macro' | 'wiremesh';

/** the alpha a colour texture's lowest point has (tools/surface-textures.cjs) */
export const HEIGHT_FLOOR = 96 / 255;

const BASE: SurfaceName[] = [
  'asphalt_albedo', 'asphalt_normal', 'asphalt_rough',
  'ground_detail', 'ground_normal',
  'rock_albedo', 'rock_normal',
  'concrete_albedo', 'concrete_normal',
];
const LAYERS: LayerName[] = [
  'rock_c', 'rock_n', 'floor_c', 'floor_n', 'moss_c', 'moss_n', 'grass_c', 'grass_n', 'gravel_c', 'gravel_n',
  'shotcrete_c', 'shotcrete_n', 'concrete_c', 'concrete_n', 'blockwall_c', 'blockwall_n', 'roadmarks',
];
const SHARED: LayerName[] = ['macro', 'wiremesh'];

/**
 * The pictures: from the layered materials' sizes on (`detail` 1 and more) decoded into bitmaps on the browser's
 * other threads while they load, upside down as the textures want them (`flipY` off: the same on both backends;
 * WebGL ignores the flip for a bitmap). As image elements, each was decoded on the main thread when its texture was
 * first uploaded, in the course's compile: 0.6 s of the title's load (measured 11-18). The plain materials draw
 * their pictures into canvases and keep the image elements (`surfaceImage`).
 */
type Picture = HTMLImageElement | ImageBitmap;
const isBitmap = (p: Picture): p is ImageBitmap => typeof (p as ImageBitmap).close === 'function';
const images = new Map<SurfaceName, Picture>();
const textures = new Map<string, THREE.Texture>();
let loadedSize = 0;

/** a picture as an image element (null: missing) */
const asImage = (src: string) =>
  new Promise<HTMLImageElement | null>((resolve) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => resolve(null);
    img.src = src;
  });

/** a picture decoded off the main thread, upside down; else (the browser refused the bitmap) as an image element */
const asBitmap = async (src: string): Promise<Picture | null> => {
  let blob: Blob;
  try {
    const res = await fetch(src);
    if (!res.ok) return null;
    blob = await res.blob();
  } catch {
    return null;
  }
  try {
    return await createImageBitmap(blob, { imageOrientation: 'flipY', premultiplyAlpha: 'none', colorSpaceConversion: 'none' });
  } catch {
    return asImage(src);
  }
};

/**
 * `detail`: the quality profile's `surfaceDetail` (0: the photo set of the plain materials only; 1: the layers at
 * 512 px; 2 and more: at 1024 px).
 */
export async function loadSurfaceTextures(detail = 0) {
  const size = detail <= 0 ? 0 : detail === 1 ? 512 : 1024;
  const bitmaps = size > 0 && typeof createImageBitmap === 'function';
  if (size !== loadedSize) {
    // another size than last time: the old pictures and the textures made from them go (and the base set when it
    // is wanted in the other form)
    for (const n of [...LAYERS, ...SHARED]) images.delete(n);
    for (const n of BASE) {
      const p = images.get(n);
      if (p && isBitmap(p) !== bitmaps) images.delete(n);
    }
    for (const t of textures.values()) t.dispose();
    textures.clear();
    loadedSize = size;
  }
  const wanted: [SurfaceName, string][] = BASE.map((n) => [n, `/textures/${n}.webp`]);
  if (size) {
    for (const n of LAYERS) wanted.push([n, `/textures/terrain/${size}/${n}.webp`]);
    for (const n of SHARED) wanted.push([n, `/textures/terrain/${n}.webp`]);
  }
  await Promise.all(
    wanted
      .filter(([n]) => !images.has(n))
      .map(async ([n, src]) => {
        const picture = bitmaps ? await asBitmap(src) : await asImage(src);
        if (picture) images.set(n, picture);
        else console.warn(`surface texture ${n} unavailable, using procedural fallback`);
      }),
  );
}

/** a photo as an image element (the plain materials' canvases), or null when it is missing or held as a bitmap */
export function surfaceImage(name: SurfaceName): HTMLImageElement | null {
  const p = images.get(name);
  return p && !isBitmap(p) ? p : null;
}

/** a texture of a loaded picture, the right way up whatever its form */
function pictureTexture(p: Picture | undefined) {
  const t = new THREE.Texture(p);
  if (p && isBitmap(p)) t.flipY = false;
  return t;
}

/** A repeating texture made from a loaded photo, or null when it is missing. */
export function surfaceTexture(name: SurfaceName, srgb: boolean): THREE.Texture | null {
  const img = images.get(name);
  if (!img) return null;
  const t = pictureTexture(img);
  if (srgb) t.colorSpace = THREE.SRGBColorSpace;
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.anisotropy = 8;
  t.needsUpdate = true;
  return t;
}

/** every layer the ground's materials need is there (else the scenery keeps its plain materials) */
export function layersLoaded() {
  return loadedSize > 0 && [...LAYERS, ...SHARED].every((n) => images.has(n));
}

/**
 * A layer's texture, one per name for all materials. They outlive a course: the materials hold them in their
 * nodes, which the scenery's disposal does not walk. `_c` textures are sRGB, the rest data.
 */
export function layerTexture(name: LayerName | 'asphalt_albedo' | 'asphalt_normal' | 'asphalt_rough'): THREE.Texture {
  let t = textures.get(name);
  if (t) return t;
  const img = images.get(name);
  t = pictureTexture(img);
  if (name.endsWith('_c') || name === 'asphalt_albedo' || name === 'wiremesh') t.colorSpace = THREE.SRGBColorSpace;
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.anisotropy = name === 'macro' ? 2 : 8;
  t.needsUpdate = !!img;
  textures.set(name, t);
  return t;
}
