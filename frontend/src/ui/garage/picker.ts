import { CAR_SPECS, type CarId } from '../../game/vehicle/carSpecs';
import { KIND_ORDER, KIND_TRAITS, kindOf, type VehicleKind } from '../../game/vehicle/kinds';
import { VEHICLE_STATS, type VehicleStats } from '../../game/vehicle/stats';

// The car select's data, free of React: tabs, sorting, moving in the grid and the scales of the performance bars
// (VehiclePicker.tsx draws it, picker.css styles it).

export type TabId = 'all' | 'fav' | VehicleKind;

export interface Tab {
  id: TabId;
  label: string;
  count: number;
}

/**
 * Tabs for a list of vehicles: everything, one per kind that has a vehicle in the list (so a kind that is not released
 * or not allowed on the course has no tab), then the starred ones.
 */
export function pickerTabs(vehicles: CarId[], favourites: CarId[]): Tab[] {
  const kinds = KIND_ORDER.map((k) => ({ id: k as TabId, label: KIND_TRAITS[k].label, count: vehicles.filter((id) => kindOf(CAR_SPECS[id]) === k).length }));
  return [
    { id: 'all', label: 'すべて', count: vehicles.length },
    ...kinds.filter((t) => t.count > 0),
    { id: 'fav', label: '★', count: vehicles.filter((id) => favourites.includes(id)).length },
  ];
}

export function tabVehicles(vehicles: CarId[], tab: TabId, favourites: CarId[]): CarId[] {
  if (tab === 'all') return vehicles;
  if (tab === 'fav') return vehicles.filter((id) => favourites.includes(id));
  return vehicles.filter((id) => kindOf(CAR_SPECS[id]) === tab);
}

export type SortKey = 'default' | 'name' | 'accel' | 'speed' | 'corner' | 'power' | 'weight';

export const SORTS: { key: SortKey; label: string }[] = [
  { key: 'default', label: '標準' },
  { key: 'name', label: '名前' },
  { key: 'accel', label: '加速' },
  { key: 'speed', label: '最高速' },
  { key: 'corner', label: 'コーナリング' },
  { key: 'power', label: '出力' },
  { key: 'weight', label: '軽さ' },
];

/** what a sort orders by: smaller comes first (a vehicle without a figure goes last) */
const SORT_VALUE: Record<Exclude<SortKey, 'default' | 'name'>, (s: VehicleStats) => number> = {
  accel: (s) => s.zeroTo100 ?? Infinity,
  speed: (s) => -s.topSpeed,
  corner: (s) => -s.lateralG,
  power: (s) => -s.powerKw,
  weight: (s) => s.massKg,
};

/** The list in the chosen order; ties and vehicles without figures keep the list's own order. */
export function sortVehicles(ids: CarId[], sort: SortKey): CarId[] {
  if (sort === 'default') return ids;
  if (sort === 'name') return [...ids].sort((a, b) => CAR_SPECS[a].name.localeCompare(CAR_SPECS[b].name, 'ja'));
  const value = (id: CarId) => {
    const s = VEHICLE_STATS[id];
    return s ? SORT_VALUE[sort](s) : Infinity;
  };
  return ids.map((id, i) => ({ id, i, v: value(id) })).sort((a, b) => a.v - b.v || a.i - b.i).map((x) => x.id);
}

/**
 * The cursor in a grid of `count` tiles, `columns` wide: left and right step through the list and wrap round (the
 * old car select's ← →), up and down move a row and stop at the edges (down from the row above a short last row
 * goes to its last tile).
 */
export function moveInGrid(index: number, count: number, columns: number, dir: 'left' | 'right' | 'up' | 'down'): number {
  if (count <= 0) return 0;
  const cols = Math.max(1, columns);
  if (dir === 'left') return (index + count - 1) % count;
  if (dir === 'right') return (index + 1) % count;
  if (dir === 'up') return index - cols >= 0 ? index - cols : index;
  if (index + cols < count) return index + cols;
  // a row below exists but is shorter than this column
  return Math.floor(index / cols) < Math.floor((count - 1) / cols) ? count - 1 : index;
}

export type BarKey = 'accel' | 'speed' | 'corner' | 'power' | 'weight';

export interface Bar {
  key: BarKey;
  label: string;
  /** the figure beside the bar */
  text: string;
  /** 0…1 */
  fill: number;
  /** the value is beyond the linear part of the scale (drawn hatched past the mark) */
  over: boolean;
  /** not a "more is better" figure (the weight): drawn in a neutral colour */
  neutral?: boolean;
}

/**
 * How the garage's camera has to aim (`Game.garageFraming`) for the vehicle to stand in the middle of a free part of
 * the screen (px), and how far it steps back for the vehicle to fit there. The camera's aim is given in metres at its
 * standard distance (8.6 m with a 38° field of view: the screen is 5.92 m high there, whatever the kind of vehicle,
 * the garage scales the distance per kind by `garage.scale`). With some air around it a vehicle takes `garage.span`
 * of width (a car 5.2 m: its near end, seen at an angle, looms large) and 2.6 m of height at a car's scale, a bike
 * with its rider more (twice the height of its middle, `garage.middle`).
 */
export function garageFramingFor(view: { w: number; h: number }, free: { left: number; right: number; top: number; bottom: number }, garage: { scale: number; middle: number; span: number } = KIND_TRAITS.car.garage) {
  const span = 2 * Math.tan((38 * Math.PI) / 360) * 8.6;
  const perPx = span / Math.max(1, view.h);
  const w = Math.max(1, free.right - free.left);
  const h = Math.max(1, free.bottom - free.top);
  // (the vehicle's middle above the road, at the standard distance)
  const middle = garage.middle / garage.scale;
  const zoom = Math.min(2.6, Math.max(1, garage.span / garage.scale / (0.88 * w * perPx), Math.max(2.6, 2 * middle + 0.4) / (h * perPx)));
  return {
    // (aiming right of the vehicle puts it left of the middle, aiming above it puts it lower)
    right: (view.w / 2 - (free.left + free.right) / 2) * perPx,
    // the garage aims 0.6 m above the road (at a car's scale); seen from above and off to the side as here, a
    // vehicle stands half a metre lower on the screen than its middle says (measured on pictures)
    up: ((free.top + free.bottom) / 2 - view.h / 2) * perPx - (0.5 + 0.6 - middle) / zoom,
    zoom,
  };
}

/** share of the bar that is linear; the rest holds everything beyond the knee, logarithmically */
export const BAR_KNEE = 0.82;

/**
 * Bar length on a scale that keeps the ordinary vehicles apart and still holds the joke entries: linear up to `knee`
 * (most of the bar), logarithmic from there to `max` (the cockroach's Mach 1, a train's megawatts), where the bar is
 * full. The real figure is always printed beside it.
 */
export function barFill(value: number, knee: number, max: number): { fill: number; over: boolean } {
  if (!(value > 0)) return { fill: 0, over: false };
  if (value <= knee) return { fill: (BAR_KNEE * value) / knee, over: false };
  return { fill: Math.min(1, BAR_KNEE + ((1 - BAR_KNEE) * Math.log(value / knee)) / Math.log(max / knee)), over: true };
}

/** [knee, max] per bar: acceleration as the mean m/s² to 100 km/h, km/h, g, kW, kg */
export const BAR_SCALES: Record<BarKey, [number, number]> = {
  accel: [10, 40],
  speed: [350, 1300],
  corner: [1.6, 6],
  power: [500, 12000],
  weight: [3500, 150000],
};

/** as the car list converts it */
const PS_PER_KW = 1.36;
const thousands = (n: number) => Math.round(n).toLocaleString('en-US');

/** 0–100 km/h time as printed ("4.7 秒"; a train's minute as "74 秒") */
export const accelText = (s: VehicleStats) => (s.zeroTo100 === null ? '100 km/h に届かない' : `${s.zeroTo100 < 20 ? s.zeroTo100.toFixed(1) : Math.round(s.zeroTo100)} 秒`);
/** kg up to ten tonnes, then tonnes */
export const weightText = (s: VehicleStats) => (s.massKg >= 10000 ? `${(s.massKg / 1000).toFixed(1)} t` : `${thousands(s.massKg)} kg`);
/** PS as the car list has it; a train's output in kW, as railways give it */
export const powerText = (id: CarId, s: VehicleStats) => (CAR_SPECS[id].train ? `${thousands(s.powerKw)} kW` : `${thousands(s.powerKw * PS_PER_KW)} PS`);

/** The performance bars of a vehicle (null without measured figures: a new vehicle before tools/vehicle-stats.ts ran). */
export function vehicleBars(id: CarId): Bar[] | null {
  const s = VEHICLE_STATS[id];
  if (!s) return null;
  const bar = (key: BarKey, label: string, value: number, text: string, neutral?: boolean): Bar => ({ key, label, text, neutral, ...barFill(value, ...BAR_SCALES[key]) });
  return [
    bar('accel', '加速 0-100', s.zeroTo100 === null ? 0 : 100 / 3.6 / s.zeroTo100, accelText(s)),
    bar('speed', '最高速', s.topSpeed, `${Math.round(s.topSpeed)} km/h`),
    bar('corner', 'コーナリング', s.lateralG, `${s.lateralG.toFixed(2)} G`),
    bar('power', '出力', s.powerKw, powerText(id, s)),
    bar('weight', '重量', s.massKg, weightText(s), true),
  ];
}

/** The figure a tile shows under the name for the current sort (nothing for the default and name orders). */
export function sortFigure(id: CarId, sort: SortKey): string | null {
  const s = VEHICLE_STATS[id];
  if (!s || sort === 'default' || sort === 'name') return null;
  if (sort === 'accel') return s.zeroTo100 === null ? '—' : `0-100 ${accelText(s)}`;
  if (sort === 'speed') return `${Math.round(s.topSpeed)} km/h`;
  if (sort === 'corner') return `${s.lateralG.toFixed(2)} G`;
  if (sort === 'power') return powerText(id, s);
  return weightText(s);
}
