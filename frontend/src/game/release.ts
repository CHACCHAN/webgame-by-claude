/**
 * What is built but not shown to players yet. Each entry is switched on here, in the code, at its release; until
 * then a build can be made with it for checks (`VITE_TANKS=1 npm run build`, `TANKS=1 npx tsx tools/…`,
 * `TANKS=1 npx vitest run`): never by anything a player can set. The server has the same switch
 * (backend/config/game.php `$release`; a vitest compares the two).
 *
 * `edwards`: the Edwards AFB course and the three fighters that run only there (open since 11-13).
 * `tanks`: the five tanks with their guns (vehicle/tanks.ts, weapons/): everything is there but their models (the
 * procedural stand-ins are drawn) and the owner's look at the figures, which were written from memory.
 */
const asked = (name: string): boolean => {
  const vite = (import.meta as { env?: Record<string, string | undefined> }).env;
  const node = (globalThis as { process?: { env?: Record<string, string | undefined> } }).process?.env;
  return vite?.[`VITE_${name}`] === '1' || node?.[name] === '1';
};

export const RELEASED = {
  edwards: true,
  tanks: false || asked('TANKS'),
};
