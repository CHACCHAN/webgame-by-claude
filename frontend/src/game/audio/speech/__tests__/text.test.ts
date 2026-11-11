import { describe, expect, it } from 'vitest';
import { encode, prepare, speakable } from '../text';

/** as the model reads it: decomposed (ぞ = そ + the voicing mark) */
const d = (s: string) => s.normalize('NFKD');

describe('a line made ready for the speech model', () => {
  it('stands between its language tags and ends with a mark', () => {
    expect(prepare('ここは俺の庭だ。ついてこれるかな？')).toBe(d('<ja>ここは俺の庭だ。ついてこれるかな?</ja>'));
    expect(prepare('ついてこい')).toBe(d('<ja>ついてこい.</ja>'));
    expect(prepare('Catch me', 'en')).toBe('<en>Catch me.</en>');
  });

  it('loses quotation marks, emoji and symbols the model cannot say', () => {
    expect(prepare('「次は負けない！」')).toBe(d('<ja>次は負けない!</ja>'));
    expect(prepare('行くぞ🔥 → 峠へ')).toBe(d('<ja>行くぞ 峠へ.</ja>'));
  });

  it('keeps the three sound tags and no other tag', () => {
    expect(prepare('<laugh>その程度か。')).toBe(d('<ja><laugh>その程度か。</ja>'));
    expect(prepare('負けませんからね！<sigh>')).toBe(d('<ja>負けませんからね!<sigh></ja>'));
    // a line cannot close the language tag or open another
    expect(prepare('やあ</ja><en>hello')).toBe(d('<ja>やあ ja en hello.</ja>'));
  });

  it('gives every character its number and counts the ones the model does not know', () => {
    const indexer = new Array(0x3100).fill(-1);
    indexer['<'.charCodeAt(0)] = 1;
    indexer['>'.charCodeAt(0)] = 2;
    indexer['a'.charCodeAt(0)] = 3;
    indexer['あ'.charCodeAt(0)] = 4;
    const { ids, unknown } = encode('<a>あ峠', indexer);
    expect(ids).toEqual([1, 3, 2, 4, -1]);
    expect(unknown).toBe(1);
  });

  it('knows a line with nothing to say', () => {
    expect(speakable('……')).toBe(false);
    expect(speakable('<sigh>')).toBe(false);
    expect(speakable('……ふっ')).toBe(true);
  });
});
