// The rivals' language model as the game's `RivalBrain`: the server's /api/ai/* (which holds the key and asks the
// model). No answer in time, or no model there: null, and the game's own lines and rules answer instead.
import type { RivalBrain } from '../game/ai/RivalMind';
import { api } from './client';

/** a line is waited for through the countdown; a decision is worth nothing a moment later */
const TAUNT_MS = 3200;
const DECIDE_MS = 1500;

let enabled: Promise<boolean> | null = null;
const on = () =>
  (enabled ??= api.ai.enabled().catch(() => {
    enabled = null;
    return false;
  }));

async function timed<T>(ms: number, call: (signal: AbortSignal) => Promise<T>): Promise<T | null> {
  const abort = new AbortController();
  const timer = setTimeout(() => abort.abort(), ms);
  try {
    return await call(abort.signal);
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}

/** to `digits` decimals (as a number that prints so: 6.1, not 6.1000000000000005) */
const round = (v: number, digits = 1) => Number(v.toFixed(digits));

export const serverBrain: RivalBrain = {
  name: 'server',
  async taunt(rival, facts) {
    if (!(await on())) return null;
    const out = await timed(TAUNT_MS, (signal) => api.ai.taunt({ rival, ...facts, gap_s: facts.gap_s === undefined ? undefined : round(facts.gap_s, 2) }, signal));
    return out?.line || null;
  },
  async decide(rival, s) {
    if (!(await on())) return null;
    const out = await timed(DECIDE_MS, (signal) =>
      api.ai.decide(
        {
          rival, ...s,
          remaining_m: Math.round(s.remaining_m), gap_m: round(s.gap_m), closing_kmh: round(s.closing_kmh), lateral_m: round(s.lateral_m),
          corner: { distance_m: Math.round(s.corner.distance_m), kind: s.corner.kind },
        },
        signal,
      ),
    );
    return out ? { block: out.block, horn: out.horn } : null;
  },
};
