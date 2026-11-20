/**
 * How finely the scene is drawn: device pixels per CSS pixel of the canvas (what `renderer.setPixelRatio` takes).
 * A quality gives a ratio, and may give a number of pixels instead (`budget`): what the low path costs on the GPU
 * grows with the pixels drawn, so a budget is about the same cost on any screen, where a ratio in CSS pixels is not
 * (0.75 CSS px was 0.19 MP on a phone at DPR 3, one drawn pixel over 4 × 4 of the screen's, and 1.2 MP in a
 * 1920 × 1080 window).
 */
export interface DrawingRule {
  /** device px per CSS px (with a `pixelBudget`: the most it may be) */
  pixelRatio: number;
  /** at most this many pixels drawn, in millions (then as many as that, between `pixelFloor` and `pixelRatio`) */
  pixelBudget?: number;
  /** never coarser than this many device px per CSS px, whatever the budget says (a big window keeps what it had) */
  pixelFloor?: number;
}

/** device px per CSS px for a canvas of `width` × `height` CSS px */
export function drawingRatio(rule: DrawingRule, width: number, height: number): number {
  if (!rule.pixelBudget) return rule.pixelRatio;
  const fit = Math.sqrt((rule.pixelBudget * 1e6) / Math.max(1, width * height));
  return Math.max(rule.pixelFloor ?? 0, Math.min(rule.pixelRatio, fit));
}
