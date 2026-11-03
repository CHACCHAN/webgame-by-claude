/**
 * Control pattern of a VVVF inverter as VVVF-Simulator reads it (its YAML files, converted to JSON by
 * tools/vvvf-patterns.ts): a port of `Data/Vvvf/Struct.cs` of VVVF-Simulator by VvvfGeeks
 * (https://github.com/VvvfGeeks/VVVF-Simulator; free for non-commercial use, link to the original required).
 * Field names are the YAML's; `normalizeVvvf` fills what a file leaves out with the simulator's defaults.
 */
import { customPwmName } from './customPwm';

export type FunctionType = 'Proportional' | 'Inv_Proportional' | 'Pow2_Exponential' | 'Sine';
export interface FunctionValue {
  Type: FunctionType;
  Start: number;
  StartValue: number;
  End: number;
  EndValue: number;
  Degree: number;
  CurveRate: number;
}

export type PulseTypeName = 'ASYNC' | 'SYNC' | 'CHM' | 'SHE' | 'HO' | 'ΔΣ';
export type BaseWaveType =
  | 'Sine' | 'Saw' | 'Square' | 'ModifiedSine1' | 'ModifiedSine2' | 'ModifiedSaw1' | 'SV'
  | 'DPWM30' | 'DPWM60C' | 'DPWM60P' | 'DPWM60N' | 'DPWM120P' | 'DPWM120N';
export type PulseDataKey = 'Dipolar' | 'PulseWidth' | 'Phase' | 'UpdateFrequency';

export interface PulseHarmonic {
  Harmonic: number;
  IsHarmonicProportional: boolean;
  Amplitude: number;
  IsAmplitudeProportional: boolean;
  InitialPhase: number;
  Type: 'Sine' | 'Saw' | 'Square';
}

export interface PulseDataValue {
  Mode: 'Const' | 'Moving';
  Constant: number;
  MovingValue: FunctionValue;
}

export interface Pulse {
  PulseType: PulseTypeName;
  PulseCount: number;
  /** `PulseAlternative` as its enum value: Default 0, CP 1, Square 2, AltN 2 + N (the YAML holds the name) */
  Alternative: number;
  DiscreteTime: { Enabled: boolean; Steps: number; Mode: 'Left' | 'Middle' | 'Right' };
  BaseWave: BaseWaveType;
  PulseHarmonics: PulseHarmonic[];
  CarrierWave: { Type: 'Triangle' | 'Saw' | 'Sine'; Option: 'RaiseStart' | 'FallStart' | 'TopStart' | 'BottomStart' };
  PulseData: Partial<Record<PulseDataKey, PulseDataValue>>;
}

export const ALT = { Default: 0, CP: 1, Square: 2, Alt1: 3, Alt2: 4 } as const;

export interface AmplitudeParameter {
  Mode: 'Linear' | 'LinearPolynomial' | 'InverseProportional' | 'Exponential' | 'Sine' | 'Table';
  StartFrequency: number;
  StartAmplitude: number;
  EndFrequency: number;
  EndAmplitude: number;
  CurveChangeRate: number;
  CutOffAmplitude: number;
  MaxAmplitude: number;
  DisableRangeLimit: boolean;
  Polynomial: number;
  AmplitudeTableInterpolation: boolean;
  AmplitudeTable: [number, number][];
}

export interface VibratoParameter {
  Mode: 'Const' | 'Moving';
  Constant: number;
  MovingValue: FunctionValue;
}

export interface CarrierTableEntry {
  ControlFrequencyFrom: number;
  CarrierFrequency: number;
  FreeRunStuckAtHere: boolean;
}

export interface AsyncControl {
  RandomData: {
    Range: { Mode: 'Const' | 'Moving'; Constant: number; MovingValue: FunctionValue };
    Interval: { Mode: 'Const' | 'Moving'; Constant: number; MovingValue: FunctionValue };
  };
  CarrierWaveData: {
    Mode: 'Const' | 'Moving' | 'Vibrato' | 'Table';
    Constant: number;
    MovingValue: FunctionValue;
    VibratoData: {
      Highest: VibratoParameter;
      Lowest: VibratoParameter;
      Interval: VibratoParameter;
      BaseWave: 'Sine' | 'Triangle' | 'Square' | 'SawUp' | 'SawDown';
    };
    CarrierFrequencyTable: { Table: CarrierTableEntry[] };
  };
}

export interface PulseControl {
  ControlFrequencyFrom: number;
  RotateFrequencyFrom: number;
  RotateFrequencyBelow: number;
  EnableFreeRunOn: boolean;
  StuckFreeRunOn: boolean;
  EnableFreeRunOff: boolean;
  StuckFreeRunOff: boolean;
  EnableNormal: boolean;
  PulseMode: Pulse;
  Amplitude: { Default: AmplitudeParameter; PowerOn: AmplitudeParameter; PowerOff: AmplitudeParameter };
  AsyncModulationData: AsyncControl;
}

export interface JerkInfo {
  FrequencyChangeRate: number;
  MaxControlFrequency: number;
}
export interface JerkSettings {
  Braking: { On: JerkInfo; Off: JerkInfo };
  Accelerating: { On: JerkInfo; Off: JerkInfo };
}

export interface VvvfData {
  Level: number;
  JerkSetting: JerkSettings;
  MinimumFrequency: { Accelerating: number; Braking: number };
  AcceleratePattern: PulseControl[];
  BrakingPattern: PulseControl[];
  /** switching-angle tables the CHM / SHE modes need (audio/vvvf/customPwm.ts; files in public/audio/vvvf-tables/) */
  CustomPwm: string[];
}

// ---- defaults (the C# initialisers) ----

type Raw = Record<string, unknown> | undefined | null;
const obj = (v: unknown): Record<string, unknown> => (v && typeof v === 'object' && !Array.isArray(v) ? (v as Record<string, unknown>) : {});
const num = (v: unknown, d: number) => (typeof v === 'number' ? v : typeof v === 'string' && v.trim() !== '' && !isNaN(+v) ? +v : d);
const bool = (v: unknown, d: boolean) => (typeof v === 'boolean' ? v : v === 'true' ? true : v === 'false' ? false : d);
const str = <T extends string>(v: unknown, d: T) => (typeof v === 'string' ? (v as T) : d);

function functionValue(r: Raw): FunctionValue {
  const o = obj(r);
  return {
    Type: str(o.Type, 'Proportional'),
    Start: num(o.Start, 0),
    StartValue: num(o.StartValue, 0),
    End: num(o.End, 1),
    EndValue: num(o.EndValue, 100),
    Degree: num(o.Degree, 2),
    CurveRate: num(o.CurveRate, 0),
  };
}

function alternative(v: unknown): number {
  if (typeof v === 'number') return v;
  const s = String(v ?? 'Default');
  if (s === 'Default') return 0;
  if (s === 'CP') return 1;
  if (s === 'Square') return 2;
  const m = /^Alt(\d+)$/.exec(s);
  return m ? 2 + +m[1] : 0;
}

function pulse(r: Raw): Pulse {
  const o = obj(r);
  const dt = obj(o.DiscreteTime);
  const cw = obj(o.CarrierWave);
  const pd = obj(o.PulseData);
  const data: Pulse['PulseData'] = {};
  for (const k of Object.keys(pd) as PulseDataKey[]) {
    const v = obj(pd[k]);
    data[k] = { Mode: str(v.Mode, 'Const'), Constant: num(v.Constant, -1), MovingValue: functionValue(v.MovingValue as Raw) };
  }
  return {
    PulseType: str(o.PulseType, 'ASYNC'),
    PulseCount: num(o.PulseCount, 1),
    Alternative: alternative(o.Alternative),
    DiscreteTime: { Enabled: bool(dt.Enabled, false), Steps: num(dt.Steps, 2), Mode: str(dt.Mode, 'Middle') },
    BaseWave: str(o.BaseWave, 'Sine'),
    PulseHarmonics: (Array.isArray(o.PulseHarmonics) ? o.PulseHarmonics : []).map((h) => {
      const x = obj(h);
      return {
        Harmonic: num(x.Harmonic, 3),
        IsHarmonicProportional: bool(x.IsHarmonicProportional, true),
        Amplitude: num(x.Amplitude, 0.2),
        IsAmplitudeProportional: bool(x.IsAmplitudeProportional, true),
        InitialPhase: num(x.InitialPhase, 0),
        Type: str(x.Type, 'Sine'),
      };
    }),
    CarrierWave: { Type: str(cw.Type, 'Triangle'), Option: str(cw.Option, 'FallStart') },
    PulseData: data,
  };
}

function amplitude(r: Raw): AmplitudeParameter {
  const o = obj(r);
  const table = (Array.isArray(o.AmplitudeTable) ? o.AmplitudeTable : []).map((e) => {
    if (Array.isArray(e)) return [num(e[0], 0), num(e[1], 0)] as [number, number];
    const x = obj(e);
    return [num(x.Item1 ?? x.Frequency, 0), num(x.Item2 ?? x.Amplitude, 0)] as [number, number];
  });
  return {
    Mode: str(o.Mode, 'Linear'),
    StartFrequency: num(o.StartFrequency, -1),
    StartAmplitude: num(o.StartAmplitude, -1),
    EndFrequency: num(o.EndFrequency, -1),
    EndAmplitude: num(o.EndAmplitude, -1),
    CurveChangeRate: num(o.CurveChangeRate, 0),
    CutOffAmplitude: num(o.CutOffAmplitude, -1),
    MaxAmplitude: num(o.MaxAmplitude, -1),
    DisableRangeLimit: bool(o.DisableRangeLimit, false),
    Polynomial: num(o.Polynomial, 0),
    AmplitudeTableInterpolation: bool(o.AmplitudeTableInterpolation, false),
    AmplitudeTable: table,
  };
}

function vibratoParameter(r: Raw): VibratoParameter {
  const o = obj(r);
  return { Mode: str(o.Mode, 'Const'), Constant: num(o.Constant, -1), MovingValue: functionValue(o.MovingValue as Raw) };
}

function asyncControl(r: Raw): AsyncControl {
  const o = obj(r);
  const rd = obj(o.RandomData);
  const range = obj(rd.Range), interval = obj(rd.Interval);
  const cw = obj(o.CarrierWaveData);
  const vib = obj(cw.VibratoData);
  const table = obj(cw.CarrierFrequencyTable);
  return {
    RandomData: {
      Range: { Mode: str(range.Mode, 'Const'), Constant: num(range.Constant, 0), MovingValue: functionValue(range.MovingValue as Raw) },
      Interval: { Mode: str(interval.Mode, 'Const'), Constant: num(interval.Constant, 0), MovingValue: functionValue(interval.MovingValue as Raw) },
    },
    CarrierWaveData: {
      Mode: str(cw.Mode, 'Const'),
      Constant: num(cw.Constant, -1),
      MovingValue: functionValue(cw.MovingValue as Raw),
      VibratoData: {
        Highest: vibratoParameter(vib.Highest as Raw),
        Lowest: vibratoParameter(vib.Lowest as Raw),
        Interval: vibratoParameter(vib.Interval as Raw),
        BaseWave: str(vib.BaseWave, 'Triangle'),
      },
      CarrierFrequencyTable: {
        Table: (Array.isArray(table.Table) ? table.Table : []).map((e) => {
          const x = obj(e);
          return {
            ControlFrequencyFrom: num(x.ControlFrequencyFrom, -1),
            CarrierFrequency: num(x.CarrierFrequency, 1000),
            FreeRunStuckAtHere: bool(x.FreeRunStuckAtHere, false),
          };
        }),
      },
    },
  };
}

function pulseControl(r: Raw): PulseControl {
  const o = obj(r);
  const a = obj(o.Amplitude);
  return {
    ControlFrequencyFrom: num(o.ControlFrequencyFrom, -1),
    RotateFrequencyFrom: num(o.RotateFrequencyFrom, -1),
    RotateFrequencyBelow: num(o.RotateFrequencyBelow, -1),
    EnableFreeRunOn: bool(o.EnableFreeRunOn, true),
    StuckFreeRunOn: bool(o.StuckFreeRunOn, false),
    EnableFreeRunOff: bool(o.EnableFreeRunOff, true),
    StuckFreeRunOff: bool(o.StuckFreeRunOff, false),
    EnableNormal: bool(o.EnableNormal, true),
    PulseMode: pulse(o.PulseMode as Raw),
    Amplitude: { Default: amplitude(a.Default as Raw), PowerOn: amplitude(a.PowerOn as Raw), PowerOff: amplitude(a.PowerOff as Raw) },
    AsyncModulationData: asyncControl(o.AsyncModulationData as Raw),
  };
}

function jerk(r: Raw): JerkInfo {
  const o = obj(r);
  return { FrequencyChangeRate: num(o.FrequencyChangeRate, 60), MaxControlFrequency: num(o.MaxControlFrequency, 60) };
}

/** A pattern as parsed from the YAML (any missing field gets VVVF-Simulator's default). */
export function normalizeVvvf(raw: unknown): VvvfData {
  const o = obj(raw);
  const js = obj(o.JerkSetting);
  const br = obj(js.Braking), ac = obj(js.Accelerating);
  const mf = obj(o.MinimumFrequency);
  const data: VvvfData = {
    Level: num(o.Level, 2),
    JerkSetting: { Braking: { On: jerk(br.On as Raw), Off: jerk(br.Off as Raw) }, Accelerating: { On: jerk(ac.On as Raw), Off: jerk(ac.Off as Raw) } },
    MinimumFrequency: { Accelerating: num(mf.Accelerating, -1), Braking: num(mf.Braking, -1) },
    AcceleratePattern: (Array.isArray(o.AcceleratePattern) ? o.AcceleratePattern : []).map((p) => pulseControl(p as Raw)),
    BrakingPattern: (Array.isArray(o.BrakingPattern) ? o.BrakingPattern : []).map((p) => pulseControl(p as Raw)),
    CustomPwm: [],
  };
  const tables = new Set<string>();
  for (const p of [...data.AcceleratePattern, ...data.BrakingPattern]) {
    const m = p.PulseMode;
    if (m.PulseType === 'CHM' || m.PulseType === 'SHE') tables.add(customPwmName(data.Level, m.PulseType, m.PulseCount, m.Alternative));
  }
  data.CustomPwm = [...tables].sort();
  return data;
}
