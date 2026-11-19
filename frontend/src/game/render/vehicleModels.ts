import { CAR_SPECS, type CarId } from '../vehicle/carSpecs';
import { kindOf } from '../vehicle/kinds';
import { loadCarTemplates } from './carAssets';
import { loadBikeModels } from './BikeModel';
import { loadJetModel } from './JetModel';
import { loadRoachModel } from './RoachModel';
import { loadTankModel } from './TankModel';
import { loadTrainModel } from './TrainModel';

/**
 * The vehicles' models are fetched when they are first needed, not all before the title: the game opens with the
 * course and one car, the rest follows in the background (`preloadVehicleModels`), and whoever is about to show a
 * vehicle asks for it first (`ensureVehicleModels`; `Game` does at the garage, the race start and the waiting room).
 * A model stays in memory once it is there. "Ready" means the fetch is over: a model that is missing or broken is
 * ready too, and its vehicle is drawn by the procedural builder as before.
 */
const ready = new Set<CarId>();
const fetching = new Map<CarId, Promise<void>>();

const fetchModel = (id: CarId): Promise<unknown> => {
  switch (kindOf(CAR_SPECS[id])) {
    case 'car':
      return loadCarTemplates([id]);
    case 'bike':
      return loadBikeModels([id]);
    case 'train':
      return loadTrainModel(id);
    case 'creature':
      return loadRoachModel();
    case 'jet':
      // the base model and the liveries that are models of their own (the two-seaters); a missing file leaves the
      // base model or the procedural stand-in
      return Promise.all([id as string, ...(CAR_SPECS[id].jet?.liveries ?? []).flatMap((l) => (l.variant ? [`${id}-${l.variant}`] : []))].map(loadJetModel));
    case 'tank':
      return loadTankModel(id);
    default:
      // built in code
      return Promise.resolve();
  }
};

const fetchOnce = (id: CarId) => {
  let p = fetching.get(id);
  if (!p) {
    p = fetchModel(id).then(
      () => void ready.add(id),
      (err) => {
        console.warn(`model of ${id} not loaded`, err);
        ready.add(id);
      },
    );
    fetching.set(id, p);
  }
  return p;
};

export const vehicleModelReady = (id: CarId) => ready.has(id);

/** how many `ensureVehicleModels` calls somebody is waiting on, for the "loading" mark (`onModelWait`) */
let waiting = 0;
const listeners = new Set<(waiting: number) => void>();
export function onModelWait(l: (waiting: number) => void) {
  listeners.add(l);
  return () => void listeners.delete(l);
}

/** Resolves when these vehicles' models are there (at once when they all are). */
export function ensureVehicleModels(ids: CarId[]): Promise<void> {
  const todo = ids.filter((id) => !ready.has(id));
  if (!todo.length) return Promise.resolve();
  const tell = () => listeners.forEach((l) => l(waiting));
  waiting++;
  tell();
  return Promise.all(todo.map(fetchOnce)).then(() => {
    waiting--;
    tell();
  });
}

/**
 * Fetches these models one after the other in the background, only while `idle()` (decoding a model takes the main
 * thread for a moment: not during a race). Returns when all are there.
 */
export async function preloadVehicleModels(ids: CarId[], idle: () => boolean) {
  for (const id of ids) {
    if (ready.has(id)) continue;
    while (!idle()) await new Promise((r) => setTimeout(r, 500));
    await fetchOnce(id);
    // a breath between two models: the menus stay smooth
    await new Promise((r) => setTimeout(r, 30));
  }
}
