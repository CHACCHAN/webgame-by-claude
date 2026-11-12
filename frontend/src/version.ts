// The game's version: written once, in package.json (vite.config.ts hands it in). CLAUDE.md "Version" says when it moves.
declare const __APP_VERSION__: string;

export const APP_VERSION: string = __APP_VERSION__;

/** as shown to the player: 2.0.0 → v2.0, 2.0.3 → v2.0.3 */
export function versionLabel(version = APP_VERSION): string {
  return 'v' + version.replace(/^(\d+\.\d+)\.0$/, '$1');
}
