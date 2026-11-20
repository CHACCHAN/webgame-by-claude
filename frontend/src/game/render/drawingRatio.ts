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

/** target per-axis step when picking discrete rungs between floor and ceiling (~28% fewer pixels per step) */
const STEP_FACTOR = 0.85;

/**
 * Steps the drawing ratio down from a rule's ceiling towards its `pixelFloor` when sustained frame times miss
 * 60 fps, and back up only with clear headroom. A rule with no room between floor and ceiling (desktop DPR 1,
 * medium / high / ultra) stays fixed at its ceiling.
 *
 * Uses the median over `WINDOW` drawn frames (~0.75 s at 60 fps) so one-off hitches or short loading bursts
 * (garage swap, background vehicle GLB decode, race start) never trigger a drop. Stepping back up requires
 * `UP_WINDOWS` consecutive fast windows (~3 s) below `UP_MS` (~87 fps, leaving a deadband so a step down that
 * brings a 21 ms device to 13–16 ms never oscillates). A rung that fails `MAX_FAILS` times in the current
 * configuration / canvas size is locked out until `configure` or `reset`.
 */
export class DynamicResolution {
  /** drawn frames per evaluation window (~0.75 s at 60 fps) */
  static readonly WINDOW = 45;
  /** consecutive fast windows needed to step back up (`4 × 45 = 180` frames, ~3 s at 60 fps) */
  static readonly UP_WINDOWS = 4;
  /** median frame time (ms) above which the ratio steps down (~54 fps) */
  static readonly DOWN_MS = 18.5;
  /** median frame time (ms) below which a window counts as having headroom to step back up (~87 fps) */
  static readonly UP_MS = 11.5;
  /** frame intervals above this (ms) are tab switches / background pauses, not rendering load */
  static readonly MAX_SAMPLE_MS = 200;
  /** step-downs from a rung before that rung (and anything above it) is locked out until reset */
  static readonly MAX_FAILS = 2;
  /** at most this many steps between ceiling and floor (up to 4 discrete rungs) */
  static readonly MAX_STEPS = 3;

  private rungs: number[] = [1];
  private index = 0;
  /** highest rung index still allowed (lowered when an upper rung fails `MAX_FAILS` times) */
  private cap = 0;
  private fails: number[] = [0];
  private samples: number[] = [];
  private fastWindows = 0;
  private key = '';

  constructor(rule?: DrawingRule, width = 1, height = 1) {
    if (rule) this.configure(rule, width, height);
  }

  /** active device px per CSS px */
  get ratio(): number {
    return this.rungs[this.index];
  }

  /** highest ratio for the current rule and canvas size */
  get ceiling(): number {
    return this.rungs[this.rungs.length - 1];
  }

  /** lowest ratio for the current rule and canvas size */
  get floor(): number {
    return this.rungs[0];
  }

  /** whether the current rule and size have dynamic range between floor and ceiling */
  get active(): boolean {
    return this.rungs.length > 1;
  }

  /**
   * Updates the rule and canvas CSS size. No-op (preserving active rung and locks) when neither changed;
   * otherwise recomputes the rungs and resets to the ceiling. Returns true when reset.
   */
  configure(rule: DrawingRule, width: number, height: number): boolean {
    const w = Math.max(1, width), h = Math.max(1, height);
    const key = `${rule.pixelRatio}|${rule.pixelBudget ?? ''}|${rule.pixelFloor ?? ''}|${w}|${h}`;
    if (key === this.key) return false;
    this.key = key;
    const ceiling = drawingRatio(rule, w, h);
    const floor = rule.pixelBudget && rule.pixelFloor !== undefined ? Math.min(ceiling, rule.pixelFloor) : ceiling;
    this.rungs = buildRungs(floor, ceiling);
    this.reset();
    return true;
  }

  /** Resets to the ceiling and clears accumulated samples and rung locks for the current rule and size. */
  reset() {
    this.index = this.rungs.length - 1;
    this.cap = this.index;
    this.fails = new Array<number>(this.rungs.length).fill(0);
    this.samples.length = 0;
    this.fastWindows = 0;
  }

  /**
   * Feeds one normally drawn frame's interval (ms). Returns true when the active `ratio` changed and the
   * caller should apply it to the renderer.
   */
  sample(dtMs: number): boolean {
    if (this.rungs.length <= 1 || (this.index === 0 && this.cap === 0)) return false;
    if (!(dtMs > 0) || dtMs > DynamicResolution.MAX_SAMPLE_MS) return false;
    this.samples.push(dtMs);
    if (this.samples.length < DynamicResolution.WINDOW) return false;
    const m = median(this.samples);
    this.samples.length = 0;
    if (m > DynamicResolution.DOWN_MS && this.index > 0) {
      this.fails[this.index] += 1;
      if (this.fails[this.index] >= DynamicResolution.MAX_FAILS) this.cap = Math.min(this.cap, this.index - 1);
      this.index -= 1;
      this.fastWindows = 0;
      return true;
    }
    if (m < DynamicResolution.UP_MS && this.index < this.cap) {
      this.fastWindows += 1;
      if (this.fastWindows >= DynamicResolution.UP_WINDOWS) {
        this.index += 1;
        this.fastWindows = 0;
        return true;
      }
      return false;
    }
    this.fastWindows = 0;
    return false;
  }
}

function buildRungs(floor: number, ceiling: number): number[] {
  if (!(ceiling > floor * 1.01) || !(floor > 0)) return [ceiling];
  const steps = Math.max(1, Math.min(DynamicResolution.MAX_STEPS, Math.round(Math.log(ceiling / floor) / Math.log(1 / STEP_FACTOR))));
  const rungs: number[] = [floor];
  for (let i = 1; i < steps; i++) rungs.push(floor * Math.pow(ceiling / floor, i / steps));
  rungs.push(ceiling);
  return rungs;
}

function median(values: readonly number[]): number {
  const sorted = [...values].sort((a, b) => a - b);
  const mid = sorted.length >> 1;
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}
