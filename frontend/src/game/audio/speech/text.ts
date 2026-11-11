// What the speech model reads: a line of text made ready and turned into the numbers of its characters.
// After the publisher's own browser example (Supertonic, MIT: web/helper.js `UnicodeProcessor`), which the model
// was released with: the same normalisation and the same language tags, or it reads something else than it was taught.

/** the voices the model comes with (five women, five men) */
export const VOICES = ['F1', 'F2', 'F3', 'F4', 'F5', 'M1', 'M2', 'M3', 'M4', 'M5'] as const;
export type VoiceId = (typeof VOICES)[number];

/** sounds the model can make between words (it was taught these three tags) */
const TAGS = /<(laugh|breath|sigh)>/g;

const EMOJI = /[\u{1F600}-\u{1F64F}\u{1F300}-\u{1F5FF}\u{1F680}-\u{1F6FF}\u{1F700}-\u{1F77F}\u{1F780}-\u{1F7FF}\u{1F800}-\u{1F8FF}\u{1F900}-\u{1F9FF}\u{1FA00}-\u{1FA6F}\u{1FA70}-\u{1FAFF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}\u{1F1E6}-\u{1F1FF}]+/gu;
const SWAPS: [string, string][] = [
  ['–', '-'], ['‑', '-'], ['—', '-'], ['_', ' '], ['“', '"'], ['”', '"'], ['‘', "'"], ['’', "'"], ['´', "'"], ['`', "'"],
  ['[', ' '], [']', ' '], ['|', ' '], ['/', ' '], ['#', ' '], ['→', ' '], ['←', ' '],
];

/**
 * A line as the model wants it: normalised, without what it cannot say, closed by a mark, between its language's
 * tags. Angle brackets other than the three sound tags are taken out (a line comes from a language model: it must
 * not be able to write tags of its own).
 */
export function prepare(text: string, lang = 'ja'): string {
  const kept: string[] = [];
  text = text.replace(TAGS, (m) => `\u0000${kept.push(m) - 1}\u0000`).replace(/[<>]/g, ' ');
  text = text.normalize('NFKD').replace(EMOJI, '');
  for (const [a, b] of SWAPS) text = text.split(a).join(b);
  text = text.replace(/[♥☆♡©\\]/g, '');
  text = text.replace(/ ([,.!?;:'])/g, '$1').replace(/\s+/g, ' ').trim();
  // (the quotation marks a line may arrive in say nothing)
  text = text.replace(/^[「『"']+|[」』"']+$/g, '').trim();
  if (text && !/[.!?;:,'")\]}…。」』】〉》›»!?]$/.test(text.replace(/\u0000\d+\u0000$/, '')) && !/\u0000\d+\u0000$/.test(text)) text += '.';
  // eslint-disable-next-line no-control-regex
  text = text.replace(/\u0000(\d+)\u0000/g, (_, k) => kept[Number(k)]);
  return `<${lang}>${text}</${lang}>`;
}

/** The model's number for every character (−1: one it was never shown), and how many of those there are. */
export function encode(prepared: string, indexer: ArrayLike<number>): { ids: number[]; unknown: number } {
  const ids: number[] = [];
  let unknown = 0;
  // (by UTF-16 unit, as the model's own code does: its table has no characters beyond the first plane)
  for (let j = 0; j < prepared.length; j++) {
    const cp = prepared.charCodeAt(j);
    const id = cp < indexer.length ? indexer[cp] : -1;
    if (id < 0) unknown++;
    ids.push(id);
  }
  return { ids, unknown };
}

/** Is there anything in the line to say? (a line of marks and spaces alone is not sent to the model) */
export const speakable = (text: string) => /[\p{L}\p{N}]/u.test(text.replace(TAGS, ''));
