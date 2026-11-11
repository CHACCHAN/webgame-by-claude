import { describe, expect, it } from 'vitest';
import { RivalMind, cornerAhead, scriptedBrain, type Decision, type RivalBrain, type Situation } from './RivalMind';

const rival = { name: '高嶺 遼', title: 'LOCAL ACE' };
const chased: Situation = { level: 'legend', remaining_m: 1200, rival_ahead: true, gap_m: 6, closing_kmh: 9, lateral_m: -1.4, corner: { distance_m: 80, kind: 'left_hairpin' }, blocks: 0, horns: 0 };
const apart: Situation = { ...chased, gap_m: 85, closing_kmh: 0 };
const settle = () => new Promise((r) => setTimeout(r, 0));

function brain(name: string, answer: () => Promise<Decision | null>): RivalBrain & { asked: Situation[] } {
  const asked: Situation[] = [];
  return { name, asked, taunt: async () => null, decide: (_r, s) => (asked.push(s), answer()) };
}

describe('the rival mind', () => {
  it('asks only when there is something to decide, and not again at once', async () => {
    const acts: string[] = [];
    const b = brain('model', async () => ({ block: 4, horn: null }));
    const mind = new RivalMind({ rival, level: 'ace', brains: [b], onBlock: (s) => acts.push(`block ${s}`), onHorn: (h) => acts.push(h) });
    mind.update(10, () => apart);
    expect(b.asked.length).toBe(0);
    mind.update(11, () => chased);
    mind.update(11.1, () => chased); // an answer is awaited
    await settle();
    expect(b.asked.length).toBe(1);
    expect(acts).toEqual(['block 4']);
    expect(mind.source).toBe('model');
    mind.update(13, () => chased); // too soon, and the block is still on
    mind.update(19.9, () => chased); // the block (4 s) and the time left open after it (4 s + 1 s) are not over
    expect(b.asked.length).toBe(1);
    mind.update(20.2, () => chased);
    await settle();
    expect(b.asked.length).toBe(2);
    expect(b.asked[1].blocks).toBe(1); // the model is told what it has done already
  });

  it('falls back to the rules when the model does not answer, and leaves it alone for a while', async () => {
    const acts: string[] = [];
    const dead = brain('model', async () => null);
    const mind = new RivalMind({ rival, level: 'legend', brains: [dead], seed: 3, onBlock: (s) => acts.push(`block ${s}`), onHorn: (h) => acts.push(h) });
    for (let t = 0; t < 60; t += 4) {
      mind.tick(t);
      mind.update(t, () => chased);
      await settle();
    }
    expect(dead.asked.length).toBe(1);
    expect(mind.source).toBe('scripted');
    expect(acts.length).toBeGreaterThan(3); // the legend shuts the door most of the time
    expect(acts.every((a) => a === 'block 3')).toBe(true); // (a hairpin is 80 m ahead: the short one)
  });

  it('drops an answer that comes after the moment has passed', async () => {
    const acts: string[] = [];
    let release!: (d: Decision) => void;
    const slow = brain('model', () => new Promise<Decision>((r) => (release = r)));
    const mind = new RivalMind({ rival, level: 'ace', brains: [slow], onBlock: () => acts.push('block'), onHorn: () => acts.push('horn') });
    mind.update(20, () => chased);
    mind.tick(24); // the race went on for four seconds
    release({ block: 4, horn: 'short' });
    await settle();
    expect(acts).toEqual([]);
  });

  it('always has a line, the same one for the same seed', async () => {
    const facts = { course: 'oboro-downhill', tod: 'night', player_car: 'hayate', rival_car: 'raijin', wins: 0, losses: 0, medal: 'none' as const, moment: 'before' as const };
    const a = await new RivalMind({ rival, level: 'ace', seed: 5, onBlock() {}, onHorn() {} }).taunt(facts);
    const b = await new RivalMind({ rival, level: 'ace', seed: 5, onBlock() {}, onHorn() {} }).taunt(facts);
    expect(a.length).toBeGreaterThan(3);
    expect(a).toBe(b);
    expect((await scriptedBrain(1).decide(rival, apart))).toEqual({ block: null, horn: null });
  });

  it('names the corner ahead', () => {
    const corners = [
      { start: 100, apex: 130, dir: 1 as const, kind: 'hairpin' as const },
      { start: 900, apex: 950, dir: -1 as const, kind: 'medium' as const },
    ];
    expect(cornerAhead(corners, 20)).toEqual({ distance_m: 80, kind: 'left_hairpin' });
    expect(cornerAhead(corners, 120)).toEqual({ distance_m: 0, kind: 'left_hairpin' });
    expect(cornerAhead(corners, 200)).toEqual({ distance_m: 400, kind: 'straight' });
    expect(cornerAhead(corners, 700)).toEqual({ distance_m: 200, kind: 'right_fast' });
    expect(cornerAhead(corners, 1000)).toEqual({ distance_m: 400, kind: 'straight' });
  });
});
