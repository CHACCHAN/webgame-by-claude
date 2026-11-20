import { describe, expect, it } from 'vitest';
import { CAR_ORDER, CAR_SPECS, VEHICLE_ORDER, vehiclesFor, type CarId } from '../../game/vehicle/carSpecs';
import { RELEASED } from '../../game/release';
import { KIND_ORDER, KIND_TRAITS, kindOf } from '../../game/vehicle/kinds';
import { VEHICLE_STATS } from '../../game/vehicle/stats';
import { COURSE_ORDER } from '../../game/track/courses';
import { BAR_KNEE, BAR_SCALES, barFill, garageFramingFor, moveInGrid, pickerTabs, sortVehicles, tabVehicles, vehicleBars, type TabId } from './picker';

describe('measured vehicle figures (tools/vehicle-stats.ts)', () => {
  it('every vehicle a player can pick has an entry with sane numbers', () => {
    for (const id of VEHICLE_ORDER) {
      const s = VEHICLE_STATS[id];
      expect(s, `${id}: run npx tsx tools/vehicle-stats.ts ${id}`).toBeDefined();
      // (a tank is governed to its sheet's speed: 67–80 km/h on tracks, 100 on the 16式's wheels)
      const tank = !!CAR_SPECS[id].tank;
      expect(s!.topSpeed, id).toBeGreaterThan(tank ? 60 : 100);
      // (Mach 1 for the cockroach; a fighter in full afterburner on the ground a little more)
      expect(s!.topSpeed, id).toBeLessThan(CAR_SPECS[id].jet ? 1500 : 1300);
      // everything else in the game gets to 100 km/h (a commuter train in about a minute)
      if (!tank || s!.topSpeed >= 100) {
        expect(s!.zeroTo100, id).not.toBeNull();
        expect(s!.zeroTo100!, id).toBeGreaterThan(0.5);
        expect(s!.zeroTo100!, id).toBeLessThan(90);
      } else expect(s!.zeroTo100, id).toBeNull();
      expect(s!.lateralG, id).toBeGreaterThan(0.4);
      expect(s!.lateralG, id).toBeLessThan(6);
      expect(s!.massKg, id).toBeGreaterThan(100);
      expect(s!.powerKw, id).toBeGreaterThan(10);
      // the bars exist and stay inside their track
      const bars = vehicleBars(id)!;
      expect(bars.map((b) => b.key)).toEqual(['accel', 'speed', 'corner', 'power', 'weight']);
      for (const b of bars) {
        // (no bar for a 0–100 time that does not exist)
        if (b.key === 'accel' && s!.zeroTo100 === null) expect(b.fill, id).toBe(0);
        else expect(b.fill, `${id} ${b.key}`).toBeGreaterThan(0);
        expect(b.fill, `${id} ${b.key}`).toBeLessThanOrEqual(1);
      }
    }
  });

  it('the road cars sit on the linear part of the speed and cornering scales', () => {
    for (const id of CAR_ORDER.filter((c) => c !== 'u9')) {
      const s = VEHICLE_STATS[id]!;
      expect(s.topSpeed, id).toBeLessThan(BAR_SCALES.speed[0]);
      expect(s.lateralG, id).toBeLessThan(BAR_SCALES.corner[0]);
    }
  });
});

describe('car select', () => {
  it('has a tab per kind with vehicles in the list, and none for the others', () => {
    for (const course of COURSE_ORDER) {
      const list = vehiclesFor(course);
      const tabs = pickerTabs(list, []);
      const kinds = KIND_ORDER.filter((k) => list.some((id) => kindOf(CAR_SPECS[id]) === k));
      expect(tabs.map((t) => t.id)).toEqual(['all', ...kinds, 'fav']);
      for (const t of tabs) {
        const ids = tabVehicles(list, t.id, []);
        expect(ids.length, t.id).toBe(t.count);
        if (t.id !== 'fav') expect(t.count, t.id).toBeGreaterThan(0);
      }
      // every vehicle is on exactly one kind tab
      expect(kinds.flatMap((k) => tabVehicles(list, k, []))).toHaveLength(list.length);
    }
    for (const k of KIND_ORDER) expect(KIND_TRAITS[k].label).not.toBe('');
  });

  it('keeps the unreleased kinds out while they are switched off', () => {
    const tabs = pickerTabs(VEHICLE_ORDER, []).map((t) => t.id);
    expect(tabs.includes('tank')).toBe(RELEASED.tanks);
    expect(tabs.includes('jet')).toBe(RELEASED.edwards);
  });

  it('lists the starred vehicles on the favourites tab, in the list order', () => {
    const fav: CarId[] = ['roach', 'hayate', 'e5'];
    expect(tabVehicles(VEHICLE_ORDER, 'fav', fav)).toEqual(['hayate', 'e5', 'roach']);
    expect(pickerTabs(VEHICLE_ORDER, fav).find((t) => t.id === ('fav' as TabId))!.count).toBe(3);
  });

  it('sorts by the measured figures and keeps the default order otherwise', () => {
    expect(sortVehicles(VEHICLE_ORDER, 'default')).toEqual(VEHICLE_ORDER);
    const by = (key: 'accel' | 'speed' | 'corner' | 'power' | 'weight') => sortVehicles(VEHICLE_ORDER, key);
    // the cheat entry leads everything but the weight
    expect(by('accel')[0]).toBe('roach');
    // (but a fighter in full afterburner, once they are in the list)
    expect(by('speed')[0]).toBe(RELEASED.edwards ? 'su47' : 'roach');
    expect(by('corner')[0]).toBe('roach');
    expect(by('weight')[0]).toBe('nsr250r');
    // (what never reaches 100 km/h comes last)
    const t = by('accel').map((id) => VEHICLE_STATS[id]!.zeroTo100 ?? Infinity);
    expect([...t].sort((a, b) => a - b)).toEqual(t);
    const v = by('speed').map((id) => VEHICLE_STATS[id]!.topSpeed);
    expect([...v].sort((a, b) => b - a)).toEqual(v);
    const names = sortVehicles(VEHICLE_ORDER, 'name');
    expect([...names].sort()).toEqual([...VEHICLE_ORDER].sort());
    // sorting does not touch the list it is given
    expect(VEHICLE_ORDER[0]).toBe('hayate');
  });

  it('moves in the grid: left and right through the list, up and down by a row', () => {
    // 10 tiles, 4 wide: rows 0-3, 4-7, 8-9
    expect(moveInGrid(0, 10, 4, 'right')).toBe(1);
    expect(moveInGrid(3, 10, 4, 'right')).toBe(4);
    expect(moveInGrid(9, 10, 4, 'right')).toBe(0);
    expect(moveInGrid(0, 10, 4, 'left')).toBe(9);
    expect(moveInGrid(5, 10, 4, 'up')).toBe(1);
    expect(moveInGrid(1, 10, 4, 'up')).toBe(1);
    expect(moveInGrid(1, 10, 4, 'down')).toBe(5);
    expect(moveInGrid(5, 10, 4, 'down')).toBe(9);
    // under the short last row there is nothing: to its last tile
    expect(moveInGrid(7, 10, 4, 'down')).toBe(9);
    expect(moveInGrid(9, 10, 4, 'down')).toBe(9);
    // every tile is reachable with ← → alone
    const seen = new Set<number>();
    for (let i = 0, k = 0; k < 10; k++, i = moveInGrid(i, 10, 4, 'right')) seen.add(i);
    expect(seen.size).toBe(10);
    expect(moveInGrid(0, 1, 4, 'left')).toBe(0);
    expect(moveInGrid(0, 0, 4, 'down')).toBe(0);
  });

  it('aims the garage camera so that the vehicle stands in the free part of the screen', () => {
    // the whole screen free: the vehicle in the middle, at the standard distance
    const whole = garageFramingFor({ w: 1280, h: 720 }, { left: 0, right: 1280, top: 0, bottom: 720 });
    expect([whole.right, whole.zoom]).toEqual([0, 1]);
    // (the garage aims half a metre above a car's middle: taken back)
    expect(whole.up).toBeCloseTo(-0.45, 6);
    // the top right corner free: the aim goes left of and below the vehicle, the camera steps back to fit the height
    const f = garageFramingFor({ w: 1280, h: 720 }, { left: 650, right: 1280, top: 0, bottom: 240 });
    expect(f.right).toBeCloseTo(((640 - 965) * 5.92) / 720, 1);
    expect(f.up).toBeCloseTo(((120 - 360) * 5.92) / 720 - 0.45 / f.zoom, 1);
    // a bike with its rider is tall for its length: seen from further away, and aimed at higher up
    const bike = garageFramingFor({ w: 1280, h: 720 }, { left: 650, right: 1280, top: 0, bottom: 240 }, KIND_TRAITS.bike.garage);
    expect(bike.zoom).toBeGreaterThan(f.zoom);
    expect(bike.up).toBeGreaterThan(f.up + 0.3);
    expect(f.zoom).toBeGreaterThan(1);
    expect(f.zoom).toBeLessThan(1.4);
    // the free part goes along for the game's own check, in normalised device coordinates
    expect(f.free.left).toBeCloseTo(650 / 640 - 1, 6);
    expect([f.free.right, f.free.top]).toEqual([1, 1]);
    expect(f.free.bottom).toBeCloseTo(1 - 480 / 720, 6);
    // no room at all: still a finite view
    const none = garageFramingFor({ w: 844, h: 390 }, { left: 844, right: 844, top: 0, bottom: 0 });
    expect(none.zoom).toBe(2.6);
    expect(Number.isFinite(none.right + none.up)).toBe(true);
  });

  it('scales a bar linearly up to the knee and squeezes what lies beyond into the rest', () => {
    expect(barFill(0, 100, 1000)).toEqual({ fill: 0, over: false });
    expect(barFill(50, 100, 1000).fill).toBeCloseTo(BAR_KNEE / 2, 6);
    expect(barFill(100, 100, 1000)).toEqual({ fill: BAR_KNEE, over: false });
    const far = barFill(500, 100, 1000);
    expect(far.over).toBe(true);
    expect(far.fill).toBeGreaterThan(BAR_KNEE);
    expect(far.fill).toBeLessThan(1);
    expect(barFill(1000, 100, 1000).fill).toBeCloseTo(1, 6);
    expect(barFill(5000, 100, 1000).fill).toBe(1);
    // never shorter for a bigger value
    let last = 0;
    for (let v = 1; v < 2000; v += 7) {
      const f = barFill(v, 100, 1000).fill;
      expect(f).toBeGreaterThanOrEqual(last);
      last = f;
    }
  });
});
