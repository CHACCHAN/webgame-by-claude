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

const images = new Map<SurfaceName, HTMLImageElement>();
const textures = new Map<string, THREE.Texture>();
let loadedSize = 0;

/**
 * `detail`: the quality profile's `surfaceDetail` (0: the photo set of the plain materials only; 1: the layers at
 * 512 px; 2 and more: at 1024 px).
 */
export async function loadSurfaceTextures(detail = 0) {
  const size = detail <= 0 ? 0 : detail === 1 ? 512 : 1024;
  if (size !== loadedSize) {
    // another size than last time: the old pictures and the textures made from them go
    for (const n of [...LAYERS, ...SHARED]) images.delete(n);
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
      .map(
        ([n, src]) =>
          new Promise<void>((resolve) => {
            const img = new Image();
            img.onload = () => {
              images.set(n, img);
              resolve();
            };
            img.onerror = () => {
              console.warn(`surface texture ${n} unavailable, using procedural fallback`);
              resolve();
            };
            img.src = src;
          }),
      ),
  );
}

export function surfaceImage(name: SurfaceName): HTMLImageElement | null {
  return images.get(name) ?? null;
}

/** A repeating texture made from a loaded photo, or null when it is missing. */
export function surfaceTexture(name: SurfaceName, srgb: boolean): THREE.Texture | null {
  const img = images.get(name);
  if (!img) return null;
  const t = new THREE.Texture(img);
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
  t = new THREE.Texture(img);
  if (name.endsWith('_c') || name === 'asphalt_albedo' || name === 'wiremesh') t.colorSpace = THREE.SRGBColorSpace;
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.anisotropy = name === 'macro' ? 2 : 8;
  t.needsUpdate = !!img;
  textures.set(name, t);
  return t;
}
