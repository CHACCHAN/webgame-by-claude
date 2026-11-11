// What a rival says and decides, apart from its driving. A language model may be asked (through a `RivalBrain`:
// the server's /api/ai/*, later one that runs in the browser), but it never drives: in a race it can only call
// two things the game then does by rule, take the blocking line for some seconds (AIDriver.block) and sound the
// horn. With no brain that answers, the rules and lines below stand in, so a race is the same game without a model.
import type { AILevel } from './AIDriver';

export type Horn = 'short' | 'long' | 'double';
export type CornerAhead = 'straight' | 'left' | 'right' | 'left_fast' | 'right_fast' | 'left_hairpin' | 'right_hairpin';
export type Moment = 'before' | 'won' | 'lost';

export interface Decision {
  /** seconds on the blocking line, or null */
  block: number | null;
  horn: Horn | null;
}
export interface RivalPersona {
  name: string;
  title: string;
  description?: string;
}
/** The race as the rival sees it, in the numbers the model is given (the server's `decide` request). */
export interface Situation {
  level: AILevel;
  remaining_m: number;
  rival_ahead: boolean;
  /** between the two cars along the road */
  gap_m: number;
  /** + = the car behind is the faster one */
  closing_kmh: number;
  /** where the player is across the road, seen from the rival: + = to its left */
  lateral_m: number;
  corner: { distance_m: number; kind: CornerAhead };
  blocks: number;
  horns: number;
}
export interface TauntFacts {
  course: string;
  tod: string;
  player_car: string;
  rival_car: string;
  wins: number;
  losses: number;
  medal: 'none' | 'bronze' | 'silver' | 'gold';
  moment: Moment;
  gap_s?: number;
}

/** Someone to ask. null = no answer (not there, failed, too slow): the next one is asked. */
export interface RivalBrain {
  readonly name: string;
  taunt(rival: RivalPersona, facts: TauntFacts, level: AILevel): Promise<string | null>;
  decide(rival: RivalPersona, situation: Situation): Promise<Decision | null>;
}

const LINES: Record<AILevel, Record<Moment, string[]>> = {
  rookie: {
    before: ['お、お手柔らかにお願いします！', '今日こそ、ついていってみせます。', '負けても笑わないでくださいね。'],
    won: ['えっ、勝っちゃった…？', 'やった！ 練習の成果が出ました！'],
    lost: ['やっぱり速いなあ…。また教えてください。', '次はもう少し食らいつきます！'],
  },
  ace: {
    before: ['この道は俺の庭だ。ミラーから消えるなよ。', '地元をなめるな。コーナー三つで終わらせる。', 'ついて来られるなら、来てみろ。'],
    won: ['悪くなかった。だが、まだ俺の庭だ。', 'その走りじゃ、この道は譲れない。'],
    lost: ['…やるな。次は同じ手は食わない。', '今日は譲る。覚えておけ。'],
  },
  legend: {
    before: ['……追えるものなら。', 'テールランプを、よく見ておくといい。', '夜は短い。始めよう。'],
    won: ['……まだ遠い。', '夜明けには、まだ早かったな。'],
    lost: ['……見事だ。', '久しぶりに、前を走る灯りを見た。'],
  },
};

const mulberry = (seed: number) => () => {
  seed = (seed + 0x6d2b79f5) | 0;
  let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
  t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
  return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
};

/** The game's own lines and rules: always answers. */
export function scriptedBrain(seed = 1): RivalBrain {
  const random = mulberry(seed);
  const eager = { rookie: 0.15, ace: 0.6, legend: 0.85 };
  return {
    name: 'scripted',
    async taunt(_rival, facts, level) {
      const lines = LINES[level][facts.moment];
      return lines[Math.floor(random() * lines.length)];
    },
    async decide(_rival, s) {
      const out: Decision = { block: null, horn: null };
      if (s.rival_ahead) {
        // the player is alongside its tail and faster: shut the door, the keener the higher the level
        if (s.gap_m < 14 && s.closing_kmh > 4 && Math.abs(s.lateral_m) > 0.8 && random() < eager[s.level]) out.block = s.corner.distance_m < 120 ? 3 : 4;
      } else if (s.gap_m < 9 && s.closing_kmh > 6 && random() < 0.5) out.horn = s.horns >= 2 ? 'double' : 'short';
      return out;
    },
  };
}

export interface MindOptions {
  rival: RivalPersona;
  level: AILevel;
  /** asked in this order; the scripted one is always behind them */
  brains?: readonly RivalBrain[];
  seed?: number;
  onBlock: (seconds: number) => void;
  onHorn: (style: Horn) => void;
}

/** seconds between two questions, and how old an answer may be when it is acted on */
const ASK_EVERY = 3.5;
const ANSWER_LIFE = 3;
/** a brain that gave no answer is left alone this long (s of wall clock) */
const REST = 30;

export class RivalMind {
  private readonly brains: RivalBrain[];
  private readonly rested = new Map<RivalBrain, number>();
  private asked = -Infinity;
  private waiting = false;
  private busyUntil = -Infinity;
  blocks = 0;
  horns = 0;
  /** who answered last (the readout and tests) */
  source = '';

  constructor(private readonly o: MindOptions) {
    this.brains = [...(o.brains ?? []), scriptedBrain(o.seed)];
  }

  private async ask<T>(fn: (b: RivalBrain) => Promise<T | null>): Promise<T | null> {
    for (const b of this.brains) {
      if ((this.rested.get(b) ?? 0) > Date.now()) continue;
      let out: T | null = null;
      try {
        out = await fn(b);
      } catch {
        out = null;
      }
      if (out !== null) {
        this.source = b.name;
        return out;
      }
      this.rested.set(b, Date.now() + REST * 1000);
    }
    return null;
  }

  /** A line in the rival's voice (never fails: the scripted lines are the last to be asked). */
  async taunt(facts: TauntFacts): Promise<string> {
    return (await this.ask((b) => b.taunt(this.o.rival, facts, this.o.level))) ?? '';
  }

  /** Is this a moment in which blocking or the horn could mean anything? (nothing is asked otherwise) */
  static worthAsking(s: Situation) {
    return s.rival_ahead ? s.gap_m < 22 && s.closing_kmh > 2 : s.gap_m < 12 && s.closing_kmh > 3;
  }

  /**
   * Called every frame of a race with the race clock `t` (s) and a function that reads the situation: asks when
   * there is something to decide, not more often than every `ASK_EVERY` s and never while an answer is awaited,
   * a block is on or the road is being left open after one. The answer is acted on when it comes, unless the moment has passed.
   */
  update(t: number, read: () => Situation) {
    this.clock = t;
    if (this.waiting || t - this.asked < ASK_EVERY || t < this.busyUntil) return;
    const s = read();
    if (!RivalMind.worthAsking(s)) return;
    this.asked = t;
    this.waiting = true;
    void this.ask((b) => b.decide(this.o.rival, { ...s, blocks: this.blocks, horns: this.horns })).then((d) => {
      this.waiting = false;
      if (!d || this.clock - t > ANSWER_LIFE) return;
      // (only a car in front can block)
      if (d.block && s.rival_ahead) {
        this.blocks++;
        // (and as long again left open after it, so it is a move and not a wall: in the duel sim a rookie that
        // blocked with a 2 s breath held a legend behind it for a whole motorway)
        this.busyUntil = this.clock + d.block * 2 + 1;
        this.o.onBlock(d.block);
      }
      if (d.horn) {
        this.horns++;
        this.o.onHorn(d.horn);
      }
    });
  }

  /** the race clock as last seen */
  private clock = 0;
  /** (for a caller that has no situation to offer this frame) */
  tick(t: number) {
    this.clock = t;
  }
}

/** The corner the model is told about: what comes next within `reach` m of road. */
export function cornerAhead(corners: readonly { start: number; apex: number; dir: 1 | -1; kind: 'hairpin' | 'tight' | 'medium' }[], s: number, reach = 400): Situation['corner'] {
  const c = corners.find((k) => k.apex >= s);
  if (!c || c.start - s > reach) return { distance_m: reach, kind: 'straight' };
  const side = c.dir > 0 ? 'left' : 'right';
  const kind = (c.kind === 'hairpin' ? `${side}_hairpin` : c.kind === 'medium' ? `${side}_fast` : side) as CornerAhead;
  return { distance_m: Math.max(0, c.start - s), kind };
}
