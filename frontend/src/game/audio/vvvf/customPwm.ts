/**
 * Switching-angle tables of the CHM / SHE modes (`Vvvf/Modulation/CustomPwm.cs` of VVVF-Simulator by VvvfGeeks,
 * https://github.com/VvvfGeeks/VVVF-Simulator): per modulation index a quarter wave of switching angles, solved
 * offline by the simulator's authors. The tables are the simulator's own files (`Vvvf/SwitchAngle/<name>.bin`, served
 * from public/audio/vvvf-tables/); a pattern lists the ones it needs in `VvvfData.CustomPwm`.
 */
import { M_2PI, M_PI_2, toInt } from './math';
import type { PulseTypeName } from './data';

const MAX_PWM_LEVEL = 2;

/** the table's file name (`CustomPwmPresets.GetCustomPwm`: L<level><Chm|She><count><Default|AltN>) */
export function customPwmName(level: number, type: PulseTypeName, count: number, alternative: number) {
  const alt = alternative === 0 ? 'Default' : alternative === 1 ? 'CP' : alternative === 2 ? 'Square' : `Alt${alternative - 2}`;
  return `L${level}${type === 'CHM' ? 'Chm' : 'She'}${count}${alt}`;
}

export class CustomPwm {
  readonly switchCount: number;
  readonly division: number;
  readonly minimum: number;
  readonly blockCount: number;
  readonly angles: Float64Array;
  readonly outputs: Uint8Array;
  readonly startLevels: Uint8Array;

  /** the .bin layout: u8 count, f64 division, f64 minimum, u32 blocks, then per block u8 start level + count × (u8 output, f64 angle) */
  constructor(bin: ArrayBuffer) {
    const v = new DataView(bin);
    this.switchCount = v.getUint8(0);
    this.division = v.getFloat64(1, true);
    this.minimum = v.getFloat64(9, true);
    this.blockCount = v.getUint32(17, true);
    const n = this.blockCount * this.switchCount;
    this.angles = new Float64Array(n);
    this.outputs = new Uint8Array(n);
    this.startLevels = new Uint8Array(this.blockCount);
    let p = 21;
    for (let i = 0; i < this.blockCount; i++) {
      this.startLevels[i] = v.getUint8(p++);
      for (let j = 0; j < this.switchCount; j++) {
        this.outputs[i * this.switchCount + j] = v.getUint8(p);
        this.angles[i * this.switchCount + j] = v.getFloat64(p + 1, true);
        p += 9;
      }
    }
    if (p !== bin.byteLength) throw new Error(`CustomPwm: ${bin.byteLength - p} bytes left over`);
  }

  /** output level 0…2 at modulation index `m` and base-wave angle `x` (GetPwm) */
  getPwm(m: number, x: number) {
    let index = toInt((m - this.minimum) / this.division);
    index = Math.min(Math.max(index, 0), this.blockCount - 1);
    x %= M_2PI;
    const orthant = toInt(x / M_PI_2);
    let angle = x % M_PI_2;
    if ((orthant & 0x01) === 1) angle = M_PI_2 - angle;
    let pwm = this.startLevels[index];
    const base = index * this.switchCount;
    for (let i = 0; i < this.switchCount; i++) {
      if (this.angles[base + i] <= angle) pwm = this.outputs[base + i];
      else break;
    }
    if (orthant > 1) pwm = MAX_PWM_LEVEL - pwm;
    return pwm;
  }
}

/** the tables of a pattern from their files' bytes (name → .bin contents) */
export function customPwmTables(bins: Record<string, ArrayBuffer>) {
  const out: Record<string, CustomPwm> = {};
  for (const [name, bin] of Object.entries(bins)) out[name] = new CustomPwm(bin);
  return out;
}
