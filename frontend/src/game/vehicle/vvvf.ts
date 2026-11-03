/**
 * Control patterns of VVVF inverters (inverter output frequency → modulation), for the synthesised motor sound
 * (public/audio/vvvf-worklet.js via audio/TrainSound.ts). The figures are those of fans' measurements collected in
 * VvvfGeeks/YAML-Files (https://github.com/VvvfGeeks/YAML-Files: "a recreation, not exactly the same as the
 * original"), retyped as facts about the trains; where no pattern exists the stand-in is named.
 */
export interface VvvfBand {
  /** inverter output frequency (Hz) from which the band applies */
  from: number;
  /** synchronous pulse count (1 = 1-pulse); absent: asynchronous */
  pulses?: number;
  /** asynchronous carrier (Hz) at `from` and at the next band's start (a ramp), or one value */
  carrier?: number | [number, number];
  /** random modulation of the carrier frequency (± Hz) */
  random?: number;
}

export interface VvvfPattern {
  /** 2- or 3-level inverter */
  level: 2 | 3;
  /** inverter output frequency per km/h: gear ratio × pole pairs / (π × wheel diameter) / 3.6 */
  hzPerKmh: number;
  /** slip frequency of an induction motor (Hz, added under power, taken off when braking); 0 for PMSM */
  slip: number;
  power: VvvfBand[];
  brake: VvvfBand[];
  /** where the pattern comes from (shown in the credits) */
  source: string;
}

const hz = (gear: number, wheel: number, polePairs: number) => (gear * polePairs) / (Math.PI * wheel) / 3.6;

/** JR East E231 (commuter type): Mitsubishi 3-level IGBT (VvvfGeeks JRE_E231_MITSUBISHI). */
export const E231_MITSUBISHI: VvvfPattern = {
  level: 3,
  hzPerKmh: hz(7.07, 0.86, 2),
  slip: 2,
  power: [
    { from: 0, carrier: 198, random: 150 },
    { from: 2, carrier: [198, 460], random: 150 },
    { from: 14, carrier: [460, 880], random: 150 },
    { from: 35, carrier: 880, random: 150 },
    { from: 39, pulses: 3 },
    { from: 51, pulses: 1 },
  ],
  brake: [
    { from: 0, carrier: 169, random: 150 },
    { from: 4, carrier: [169, 1000], random: 150 },
    { from: 40, carrier: 1000, random: 150 },
    { from: 50, pulses: 3 },
    { from: 59, pulses: 1 },
  ],
  source: 'E231系（三菱 3レベルIGBT）',
};

/**
 * Tokyo Metro 1000 (Toshiba IGBT, permanent-magnet motors): no pattern has been published; stand-in: the Toshiba
 * 3-level IGBT of the JR West 207-2000 (VvvfGeeks JRW_207-2000_TOSHIBA_IGBT). Gear 109:14, wheel 0.78 m.
 */
export const GINZA_TOSHIBA_STANDIN: VvvfPattern = {
  level: 3,
  hzPerKmh: hz(109 / 14, 0.78, 2),
  slip: 0,
  // the carrier rises 1000 → 1500 Hz over 0–45.5 Hz (random modulation at the bottom)
  power: [
    { from: 0, carrier: [1000, 1000 + (500 * 14) / 45.5], random: 200 },
    { from: 14, carrier: [1000 + (500 * 14) / 45.5, 1500] },
    { from: 45.5, carrier: 1500 },
    { from: 53, pulses: 1 },
  ],
  brake: [
    { from: 0, carrier: [1000, 1000 + (500 * 14) / 61], random: 200 },
    { from: 14, carrier: [1000 + (500 * 14) / 61, 1500] },
    { from: 61, carrier: 1500 },
    { from: 71, pulses: 1 },
  ],
  source: '東芝 3レベルIGBT（JR西日本207系2000番台）で代用',
};

/**
 * N700: no pattern has been published; an approximation from what is (3-level IGBT, switching ~1.5 kHz, about 25 s
 * asynchronous after a start at 2.6 km/h/s ≈ 65 km/h; Nagoya Univ. OCW, Wikipedia). Gear 2.79, wheel 0.86 m.
 */
export const N700_APPROX: VvvfPattern = {
  level: 3,
  hzPerKmh: hz(2.79, 0.86, 2),
  slip: 1.5,
  power: [
    { from: 0, carrier: [1000, 1500], random: 100 },
    { from: 10, carrier: 1500 },
    { from: 37, pulses: 3 },
    { from: 52, pulses: 1 },
  ],
  brake: [
    { from: 0, carrier: 1500, random: 100 },
    { from: 40, pulses: 3 },
    { from: 55, pulses: 1 },
  ],
  source: '公開情報からの推定（3レベルIGBT・約1.5kHz）',
};

/** The modulation at an output frequency: band, carrier (asynchronous) and modulation index. */
export function vvvfAt(bands: VvvfBand[], f: number) {
  let i = 0;
  while (i < bands.length - 1 && f >= bands[i + 1].from) i++;
  const b = bands[i];
  const end = bands[i + 1]?.from ?? b.from + 1;
  const c = b.carrier;
  const along = Math.min(1, Math.max(0, (f - b.from) / Math.max(1e-6, end - b.from)));
  const carrier = c === undefined ? 0 : typeof c === 'number' ? c : c[0] + (c[1] - c[0]) * along;
  // full voltage at the 1-pulse band (V/f constant below it, over-modulated near it)
  const full = bands.find((x) => x.pulses === 1)?.from ?? bands[bands.length - 1].from;
  return { pulses: b.pulses ?? 0, carrier, random: b.random ?? 0, amp: Math.min(1.25, Math.max(0.06, (f / full) * 1.15)) };
}
