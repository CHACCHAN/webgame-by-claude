import * as THREE from 'three';

/**
 * Photo-scanned surface textures (CC0, ambientCG; see docs/ASSETS.md) served
 * from /textures/<name>.webp. They are optional: anything missing falls back to
 * the procedural textures in textures.ts.
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
  | 'concrete_normal';

const NAMES: SurfaceName[] = [
  'asphalt_albedo', 'asphalt_normal', 'asphalt_rough',
  'ground_detail', 'ground_normal',
  'rock_albedo', 'rock_normal',
  'concrete_albedo', 'concrete_normal',
];

const images = new Map<SurfaceName, HTMLImageElement>();

export async function loadSurfaceTextures() {
  await Promise.all(
    NAMES.filter((n) => !images.has(n)).map(
      (n) =>
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
          img.src = `/textures/${n}.webp`;
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
