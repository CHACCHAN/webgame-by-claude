import * as THREE from 'three';
import { Fn, luminance, mix, uniform, vec4 } from 'three/tsl';
import type { Node } from 'three/webgpu';

/**
 * The look laid over the tone-mapped picture. AgX keeps a lamp's colour up to white and rolls the highlights off
 * softly, but leaves the picture flat with lifted blacks; the grade gives the contrast back (an S-curve that keeps
 * black and white where they are), sets the saturation and tints the shadows and the highlights apart (cool
 * shadows, warm lights: the split a night of sodium lamps asks for). Set per time of day by `Environment`.
 */
export interface Grade {
  /** steepness of the S-curve around mid-grey (1 = none) */
  contrast: number;
  /** 1 = as tone-mapped */
  saturation: number;
  /** added to the shadows / the highlights (display values, small) */
  shadows: THREE.ColorRepresentation;
  highlights: THREE.ColorRepresentation;
}

export const NO_GRADE: Grade = { contrast: 1, saturation: 1, shadows: '#000000', highlights: '#000000' };

const contrast = uniform(1), saturation = uniform(1);
const shadows = uniform(new THREE.Color(0, 0, 0)), highlights = uniform(new THREE.Color(0, 0, 0));

export function setGrade(g: Grade) {
  contrast.value = g.contrast;
  saturation.value = g.saturation;
  // (the tints are display values as written, not colours to convert)
  shadows.value.set(g.shadows).convertLinearToSRGB();
  highlights.value.set(g.highlights).convertLinearToSRGB();
}

/** `input` (the displayed, sRGB-encoded picture) with the grade */
export function graded(input: Node<'vec4'>): Node<'vec4'> {
  return Fn(() => {
    const c = input.rgb.saturate();
    // x^k / (x^k + (1 - x)^k): steeper through the middle, 0 and 1 stay (the bases are clamped: no NaN)
    const up = c.max(1e-5).pow(contrast), down = c.oneMinus().max(1e-5).pow(contrast);
    const curved = up.div(up.add(down));
    const y = luminance(curved);
    const coloured = mix(y, curved, saturation);
    const dark = y.oneMinus().pow2(), light = y.pow2();
    return vec4(coloured.add(shadows.mul(dark)).add(highlights.mul(light)).saturate(), input.a);
  })();
}
