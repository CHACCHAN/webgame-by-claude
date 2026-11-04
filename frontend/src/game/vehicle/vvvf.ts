/**
 * VVVF inverters of the trains (audio/vvvf: VVVF-Simulator's calculation, https://github.com/VvvfGeeks/VVVF-Simulator).
 * Each train names a control pattern in the simulator's format (frontend/tools/vvvf/<pattern>.yaml → JSON by
 * tools/vvvf-patterns.ts: fans' recreations from VvvfGeeks/YAML-Files, "not exactly the same as the original", or our
 * own estimate where none is published) and what links it to the train: the gear teeth (the speed → inverter
 * frequency, and the gear whine), the motor's pole pairs and its slip.
 */
import type { VvvfDrive } from '../audio/vvvf/engine';

export interface TrainVvvf {
  /** control pattern: src/game/audio/vvvf/patterns/<pattern>.json */
  pattern: string;
  /** teeth of the pinion and of the wheel's gear (ratio = gear[1] / gear[0]) */
  gear: [number, number];
  /** pole pairs of the motor (2 = 4-pole) */
  polePairs: number;
  /** slip (Hz): the inverter runs this far ahead of the rotor under power, behind it when braking; 0 for PMSM */
  slip: number;
  /** gear whine calculated from the teeth, against the simulator's level (1); default 0 (none, as the simulator) */
  gearGain?: number;
  /** where the pattern comes from (credits) */
  source: string;
}

/**
 * JR East E231 (commuter type) as built: Mitsubishi 3-level IGBT, gear 99:14. No train in the game runs it since the
 * E231 became the renewed Musashino Line car (`E231_MUSASHINO_MITSUBISHI`); the tests check the port against it.
 */
export const E231_MITSUBISHI: TrainVvvf = {
  pattern: 'JRE_E231_MITSUBISHI',
  gear: [14, 99],
  polePairs: 2,
  slip: 2,
  source: 'E231系 三菱IGBT（YAML-Files JRE_E231_MITSUBISHI）',
};

/**
 * Keikyu New 1000, 1st and 2nd batch (2002–2003): Siemens SIBAS32 GTO, the "do-re-mi-fa inverter" (asynchronous
 * carrier stepping through a scale at the start, then CHM 15 … 3 pulses). Gear 83:14.
 */
export const KEIKYU_N1000_GTO: TrainVvvf = {
  pattern: 'N1000_SIEMENS_GTO',
  gear: [14, 83],
  polePairs: 2,
  slip: 2,
  source: '京急新1000形 1・2次車 シーメンスGTO（YAML-Files N1000_SIEMENS_GTO）',
};

/**
 * JR East E231-0 on the Musashino Line (renewed 2017–2020 on the move from the Chuo-Sobu Line): the original Mitsubishi
 * 3-level IGBT (SC60A, `E231_MITSUBISHI`) replaced by a new Mitsubishi 2-level IGBT, asynchronous carrier at a constant
 * centre (fan recordings: tetsuyukan.com, vvvfdb.stars.ne.jp). No recreation of it has been published; the E233
 * commuter type's Mitsubishi 2-level IGBT (SC85: constant ~750 Hz asynchronous → 3 → 1 pulse), the sound the renewal
 * is said to resemble, stands in. Gear 99:14 (7.07), MT73 4-pole.
 */
export const E231_MUSASHINO_MITSUBISHI: TrainVvvf = {
  pattern: 'JRE_E233_1000_MITSUBISHI',
  gear: [14, 99],
  polePairs: 2,
  slip: 2,
  source: 'E231系0番台 機器更新車（三菱2レベルIGBT）はE233系1000番台 三菱IGBTで代用（YAML-Files JRE_E233_1000_MITSUBISHI）',
};

/**
 * JR East E235-0 (Yamanote Line, mass production): Mitsubishi full-SiC SC104, 2-level, 1C4M. Our estimate
 * (tools/vvvf/E235_ESTIMATE.yaml, from ja.wikipedia and fans' analyses on VVVF名鑑): asynchronous at a constant ~1200 Hz
 * centre with narrow random modulation, a slight rise at its end, then synchronous 27 pulses in three over-modulated
 * steps to the top speed (never 1 pulse); the same backwards when braking, asynchronous to the stop. Stand-in kept as the
 * alternative: the Meitetsu 100's Mitsubishi IGBT (YAML-Files MEITETSU_100_MITSUBISHI_IGBT, ~1000 Hz → 3 → 1 pulse).
 * Gear 7.07 (99:14), MT79 4-pole.
 */
export const E235_MITSUBISHI_SIC: TrainVvvf = {
  pattern: 'E235_ESTIMATE',
  gear: [14, 99],
  polePairs: 2,
  slip: 2,
  source: 'E235系0番台 三菱フルSiCは公開情報からの独自の推定（非同期1200Hz→同期27パルス）',
};

/**
 * Tobu 30000: Hitachi 3-level IGBT VFI-HR1420B (1C4M). Our estimate (tools/vvvf/TOBU30000_ESTIMATE.yaml, pattern
 * "H3I-2" after VVVF名鑑): asynchronous dipolar → unipolar, the carrier rising an octave 900 → 1800 Hz, then the 3-level
 * 1 pulse (no 3 pulses); when braking, 200 Hz just before the stop. Stand-in kept as the alternative: the JR West
 * 223-2000's Hitachi 3-level IGBT (YAML-Files JRW_223-2000_HITACHI_IGBT, same family, 500 → 1000 Hz). Gear 99:14,
 * TM-95 4-pole.
 */
export const TOBU30000_HITACHI: TrainVvvf = {
  pattern: 'TOBU30000_ESTIMATE',
  gear: [14, 99],
  polePairs: 2,
  slip: 2,
  source: '東武30000系 日立3レベルIGBTは公開情報からの独自の推定（非同期900→1800Hz→1パルス）',
};

/**
 * JR East E5 (Hayabusa): 3-level IGBT PWM converter + 3-level IGBT inverter (CI18; Mitsubishi, Toshiba and Hitachi
 * build it), 3300 V 1200 A elements, MT207 300 kW. No pattern has been published: our N700 estimate (3-level IGBT,
 * ~1.5 kHz asynchronous → 3 → 1 pulse) with the E5's gear 82:31 (2.645); 4-pole motor assumed.
 */
export const E5_ESTIMATE: TrainVvvf = {
  pattern: 'N700_ESTIMATE',
  gear: [31, 82],
  polePairs: 2,
  slip: 1.5,
  source: 'E5系は公開情報からの推定（N700系と同じ推定パターン・3レベルIGBT、歯車比82:31）',
};

/** inverter output Hz per km/h at no slip: wheel rev/s × gear ratio × pole pairs */
export const hzPerKmh = (v: TrainVvvf, wheel: number) => ((v.gear[1] / v.gear[0]) * v.polePairs) / (Math.PI * wheel) / 3.6;

/** below this speed (km/h) the electric brake hands over to the air brake: the inverter shuts down */
export const ELECTRIC_BRAKE_FADE = 3;

/**
 * Seconds a train's tractive effort (and with it the inverter's slip) takes to build up after a notch-on, and the
 * electric brake's: a real EMU's jerk limit (~0.8 m/s³ at 3.5 km/h/s). `VehicleSim.traction` applies it to the
 * physics. Measured on recordings of the Keikyu's start (Commons `Keikyun1000.ogg`, `Keikyu2100.ogg`): the doremifa
 * takes 1.35–1.7 s from its first note to the top G; with this ramp the game's takes ~1.55 s (0.85 s without).
 */
export const TRACTION_RISE = 1.2;

/**
 * The inverter's drive at a speed and notch (1 power, −1 brake, 0 coast). Coasting keeps the last direction's
 * pattern (as the simulator's notch N) with the gates off; the voltage then ramps down at the pattern's own rate.
 * `slipShare`: how far the torque has built up (0…1, see TRACTION_RISE): from standstill the inverter starts at 0 Hz,
 * so a pattern's lowest steps (the N1000's first notes) are heard.
 */
export function vvvfDrive(v: TrainVvvf, wheel: number, kmh: number, notch: 1 | 0 | -1, wasBraking: boolean, out: VvvfDrive, slipShare = 1) {
  const rotor = Math.max(0, kmh) * hzPerKmh(v, wheel);
  const brakeOn = notch === -1 && kmh >= ELECTRIC_BRAKE_FADE;
  const slip = v.slip * Math.min(1, Math.max(0, slipShare));
  out.rotorHz = rotor;
  out.braking = notch === 0 ? wasBraking : notch === -1;
  out.powerOff = !(notch === 1 || brakeOn);
  out.hz = notch === 1 ? rotor + slip : brakeOn ? Math.max(0, rotor - slip) : rotor;
  return out;
}
