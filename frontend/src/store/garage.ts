import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { CarId } from '../game/vehicle/carSpecs';
import type { SortKey, TabId } from '../ui/garage/picker';

/** What the car select remembers between visits: the starred vehicles, the order of the list and the tab last open. */
interface GarageState {
  favourites: CarId[];
  sort: SortKey;
  tab: TabId;
  toggleFavourite: (id: CarId) => void;
  set: (patch: Partial<Pick<GarageState, 'sort' | 'tab'>>) => void;
}

export const useGarage = create<GarageState>()(
  persist(
    (set, get) => ({
      favourites: [],
      sort: 'default',
      tab: 'all',
      toggleFavourite: (id) => {
        const f = get().favourites;
        set({ favourites: f.includes(id) ? f.filter((x) => x !== id) : [...f, id] });
      },
      set: (patch) => set(patch),
    }),
    { name: 'touge-garage', version: 1 },
  ),
);
