/**
 * Which device the player used last in the menus: the hint bar prints its glyphs (keys, or the pad's buttons).
 * Kept on <html data-input> so that the styles switch without a React render.
 */
export type InputDevice = 'key' | 'pad';

let device: InputDevice = 'key';

export function noteInput(d: InputDevice) {
  if (d === device) return;
  device = d;
  document.documentElement.dataset.input = d;
}

export const inputDevice = () => device;
