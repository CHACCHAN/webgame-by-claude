import { describe, expect, it } from 'vitest';
import { ErrorBurst, RETRY_AFTER, forgetFailures, noteDeviceLost, planBackend, rememberFailure } from './backendChoice';

const store = () => {
  const m = new Map<string, string>();
  return { getItem: (k: string) => m.get(k) ?? null, setItem: (k: string, v: string) => void m.set(k, v), removeItem: (k: string) => void m.delete(k) };
};
const both = () => ({ lasting: store(), session: store() });

describe('the renderer backend plan', () => {
  it('tries WebGPU unless told otherwise', () => {
    const s = both();
    expect(planBackend('auto', '', 0, s)).toEqual({ forceWebGL: false, reason: null });
    expect(planBackend('auto', '?webgl=1', 0, s)).toEqual({ forceWebGL: true, reason: 'query' });
    expect(planBackend('webgl2', '', 0, s)).toEqual({ forceWebGL: true, reason: 'setting' });
    expect(planBackend('webgpu', '?webgl=1', 0, s).reason).toBe('query');
  });

  it('remembers a failure for a week, and not against an explicit choice of WebGPU', () => {
    const s = both();
    rememberFailure('errors', 1000, s);
    expect(planBackend('auto', '', 2000, s)).toEqual({ forceWebGL: true, reason: 'failed' });
    expect(planBackend('webgpu', '', 2000, s).forceWebGL).toBe(false);
    expect(planBackend('auto', '', 1000 + RETRY_AFTER + 1, s).forceWebGL).toBe(false);
    forgetFailures(s);
    expect(planBackend('auto', '', 2000, s).forceWebGL).toBe(false);
  });

  it('reloads on a lost device, falls back on the second, and does not loop', () => {
    const s = both();
    expect(noteDeviceLost(0, s)).toBe(true);
    expect(planBackend('auto', '', 1, s).forceWebGL).toBe(false); // a crashed GPU process: WebGPU once more
    expect(noteDeviceLost(5000, s)).toBe(true);
    expect(planBackend('auto', '', 5001, s)).toEqual({ forceWebGL: true, reason: 'failed' });
    expect(noteDeviceLost(9000, s)).toBe(false); // the WebGL 2 context went too, right after the reload: stop
    expect(noteDeviceLost(9000 + 120000, s)).toBe(true); // much later: worth one reload again
    expect(noteDeviceLost(0, { lasting: null, session: null })).toBe(false);
  });

  it('survives broken storage', () => {
    const bad = { getItem: () => '{', setItem: () => { throw new Error('full'); }, removeItem: () => undefined };
    const s = { lasting: bad, session: bad };
    expect(planBackend('auto', '', 0, s).forceWebGL).toBe(false);
    rememberFailure('x', 0, s);
  });

  it('tells a burst of errors from stray ones', () => {
    const stray = new ErrorBurst();
    for (let i = 0; i < 40; i++) expect(stray.add(i * 2)).toBe(false);
    const burst = new ErrorBurst();
    let fired = 0;
    for (let i = 0; i < 40; i++) if (burst.add(100 + i * 0.016)) fired++;
    expect(fired).toBe(1);
  });
});
