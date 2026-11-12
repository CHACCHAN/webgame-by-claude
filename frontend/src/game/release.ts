/**
 * What is built but not shown to players yet. Each entry is switched on here, in the code, at its release; until
 * then a build can be made with it for checks (`VITE_EDWARDS=1 npm run build`, `EDWARDS=1 npx tsx tools/…`,
 * `EDWARDS=1 npx vitest run`): never by anything a player can set.
 *
 * `edwards`: the Edwards AFB course and the three fighters that run only there. `tanks`: the tanks (no cannon yet).
 */
const asked = (name: string): boolean => {
  const vite = (import.meta as { env?: Record<string, string | undefined> }).env;
  const node = (globalThis as { process?: { env?: Record<string, string | undefined> } }).process?.env;
  return vite?.[`VITE_${name}`] === '1' || node?.[name] === '1';
};

export const RELEASED = {
  edwards: false || asked('EDWARDS'),
  tanks: false || asked('TANKS'),
};
