import type { CarId, CarSpec } from './carSpecs';
import data from './vehicleStats.json';

/**
 * A vehicle's figures for the car select: measured by the headless simulation (tools/vehicle-stats.ts writes
 * vehicleStats.json: a flat, dry straight and a skid circle), with the mass and power its spec gives.
 */
export interface VehicleStats {
  /** seconds from standstill to 100 km/h at full throttle (null: it never gets there) */
  zeroTo100: number | null;
  /** km/h the vehicle settles at on the level */
  topSpeed: number;
  /** peak lateral acceleration held on a 45.7 m skid circle (g) */
  lateralG: number;
  massKg: number;
  powerKw: number;
}

export const VEHICLE_STATS = data.vehicles as Partial<Record<CarId, VehicleStats>>;

/** Peak power of the torque curve (kW, linear between its points, up to the redline) and the speed it is made at. */
export function peakPowerKw(spec: CarSpec) {
  const t = spec.engine.torque;
  let best = { kw: 0, rpm: 0 };
  for (let rpm = t[0][0]; rpm <= spec.engine.redline; rpm += 50) {
    let k = 0;
    while (k < t.length - 2 && t[k + 1][0] < rpm) k++;
    const f = Math.min(1, Math.max(0, (rpm - t[k][0]) / (t[k + 1][0] - t[k][0])));
    const kw = ((t[k][1] + (t[k + 1][1] - t[k][1]) * f) * rpm * 2 * Math.PI) / 60 / 1000;
    if (kw > best.kw) best = { kw, rpm };
  }
  return best;
}

/**
 * Mass and power as the spec has them. A train is simulated as one light bogie (`PHYS_MASS`) with the real train's
 * acceleration: its figures are the three cars' real mass and the bogie's power scaled up to it.
 */
export function specFigures(spec: CarSpec): Pick<VehicleStats, 'massKg' | 'powerKw'> {
  const kw = peakPowerKw(spec).kw;
  if (spec.train) {
    const massKg = spec.train.mass * 1000;
    return { massKg, powerKw: Math.round((kw * massKg) / spec.mass) };
  }
  return { massKg: spec.mass, powerKw: Math.round(kw * 10) / 10 };
}
