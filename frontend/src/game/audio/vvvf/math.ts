/**
 * `Vvvf/MyMath.cs` of VVVF-Simulator (VvvfGeeks), plus the two C# behaviours the port has to copy: banker's
 * rounding (`Math.Round`) and `List<T>.Sort` (introspective sort: on ≤ 16 items a sorting network or insertion
 * sort, which keeps or swaps equal items in its own way — the pattern lists have equal start frequencies).
 */
export const M_2_PI = 0.63661977236758134307553505349006;
export const M_1_PI = 0.31830988618379067153776752674503;
export const M_1_2PI = 0.15915494309189533576888376337251;
export const M_2PI = 6.283185307179586476925286766559;
export const M_2PI_3 = 2.0943951023931954923084289221863;
export const M_PI = 3.1415926535897932384626433832795;
export const M_PI_2 = 1.5707963267948966192313216916398;
export const M_PI_3 = 1.0471975511965977461542144610932;
export const M_PI_4 = 0.78539816339744830961566084581988;
export const M_PI_6 = 0.52359877559829887307710723054658;
export const M_SQRT3 = 1.7320508075688772935274463415059;
export const M_SQRT3_2 = 0.86602540378443864676372317075294;

export function triangle(x: number) {
  const phase = M_2_PI * x - 4 * Math.floor(x * M_1_2PI);
  let value = phase;
  if (1 <= phase && phase < 3) value = -phase + 2;
  else if (3 <= phase) value = phase - 4;
  return value;
}

export function saw(x: number) {
  return M_1_PI * x - 2 * Math.floor(x * M_1_2PI) - 1;
}

export const sine = Math.sin;

export function square(x: number) {
  const fixed = x - Math.floor(x * M_1_2PI) * M_2PI;
  if (fixed * M_1_PI > 1) return -1;
  return 1;
}

/** C# `Math.Round` (halves to even) */
export function roundEven(x: number) {
  const r = Math.round(x);
  return Math.abs(x % 1) === 0.5 ? 2 * Math.round(x / 2) : r;
}

/** C# `(int)x` */
export const toInt = Math.trunc;

/** .NET `List<T>.Sort(Comparison<T>)` in place (exact for lists of up to 16 items; longer ones fall back to a stable sort). */
export function dotnetSort<T>(keys: T[], cmp: (a: T, b: T) => number) {
  const n = keys.length;
  if (n < 2) return keys;
  const swapIfGreater = (i: number, j: number) => {
    if (cmp(keys[i], keys[j]) > 0) {
      const t = keys[i];
      keys[i] = keys[j];
      keys[j] = t;
    }
  };
  if (n > 16) return keys.sort(cmp);
  if (n === 2) {
    swapIfGreater(0, 1);
    return keys;
  }
  if (n === 3) {
    swapIfGreater(0, 1);
    swapIfGreater(0, 2);
    swapIfGreater(1, 2);
    return keys;
  }
  for (let i = 0; i < n - 1; i++) {
    const t = keys[i + 1];
    let j = i;
    while (j >= 0 && cmp(t, keys[j]) < 0) {
      keys[j + 1] = keys[j];
      j--;
    }
    keys[j + 1] = t;
  }
  return keys;
}

/** C# `double.CompareTo` for the numbers in the patterns (no NaN) */
export const compareTo = (a: number, b: number) => (a < b ? -1 : a > b ? 1 : 0);

/** xorshift32 in [0, 1): a repeatable stand-in for the carrier's random modulation (renders, tests, the C# check) */
export function xorshift32(seed = 2463534242) {
  let x = seed >>> 0;
  return () => {
    x ^= x << 13;
    x >>>= 0;
    x ^= x >>> 17;
    x ^= x << 5;
    x >>>= 0;
    return x / 4294967296.0;
  };
}
