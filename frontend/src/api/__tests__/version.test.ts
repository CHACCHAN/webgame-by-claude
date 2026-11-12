import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { APP_VERSION, versionLabel } from '../../version';

describe('the game\'s version', () => {
  it('is package.json\'s, and the server\'s default says the same', () => {
    const pkg = JSON.parse(readFileSync(new URL('../../../package.json', import.meta.url), 'utf8')) as { version: string };
    expect(APP_VERSION).toBe(pkg.version);
    expect(APP_VERSION).toMatch(/^\d+\.\d+\.\d+$/);
    const server = readFileSync(new URL('../../../../backend/config/game.php', import.meta.url), 'utf8');
    expect(server).toContain(`env('GAME_VERSION', '${pkg.version}')`);
  });
  it('is shown without a patch number of zero', () => {
    expect(versionLabel('2.0.0')).toBe('v2.0');
    expect(versionLabel('2.0.3')).toBe('v2.0.3');
    expect(versionLabel('2.10.0')).toBe('v2.10');
  });
});
