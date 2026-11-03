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

/** JR East E231 (commuter type): Mitsubishi 3-level IGBT. Gear 99:14. */
export const E231_MITSUBISHI: TrainVvvf = {
  pattern: 'JRE_E231_MITSUBISHI',
  gear: [14, 99],
  polePairs: 2,
  slip: 2,
  source: 'E231系 三菱IGBT（YAML-Files JRE_E231_MITSUBISHI）',
};

/**
 * Tokyo Metro 1000 (Toshiba IGBT, permanent-magnet motors): no pattern has been published; stand-in: the Toshiba
 * 3-level IGBT of the JR West 207-2000. Gear 109:14.
 */
export const GINZA_TOSHIBA_STANDIN: TrainVvvf = {
  pattern: 'JRW_207-2000_TOSHIBA_IGBT',
  gear: [14, 109],
  polePairs: 2,
  slip: 0,
  source: '銀座線1000系は東芝IGBTのJR西日本207系2000番台で代用（YAML-Files JRW_207-2000_TOSHIBA_IGBT）',
};

/**
 * N700: no pattern has been published; our estimate in the simulator's format (tools/vvvf/N700_ESTIMATE.yaml) from
 * what is: 3-level IGBT, switching about 1.5 kHz, asynchronous for some 25 s of a start at 2.6 km/h/s. Gear 2.79
 * (teeth 81:29 for the ratio).
 */
export const N700_ESTIMATE: TrainVvvf = {
  pattern: 'N700_ESTIMATE',
  gear: [29, 81],
  polePairs: 2,
  slip: 1.5,
  source: 'N700系は公開情報からの独自の推定（3レベルIGBT・約1.5kHz）',
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
