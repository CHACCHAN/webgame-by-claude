/**
 * VVVF control patterns: VVVF-Simulator's YAML files (tools/vvvf/*.yaml; VvvfGeeks/YAML-Files, or our own in the
 * same format) → src/game/audio/vvvf/patterns/<name>.json, every field filled in (audio/vvvf/data.ts). The CHM / SHE
 * switching-angle tables a pattern uses must be in public/audio/vvvf-tables/ (copied from the simulator's
 * VvvfSimulator/Vvvf/SwitchAngle/<name>.bin).
 *   npx tsx tools/vvvf-patterns.ts            convert all
 *   npx tsx tools/vvvf-patterns.ts --check    fail when a JSON is missing or stale (vvvf.test.ts runs this)
 */
import { readdirSync, readFileSync, writeFileSync, existsSync } from 'node:fs';
import { join, basename } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parse } from 'yaml';
import { normalizeVvvf } from '../src/game/audio/vvvf/data';

const root = join(fileURLToPath(import.meta.url), '..', '..');
const src = join(root, 'tools/vvvf');
const out = join(root, 'src/game/audio/vvvf/patterns');
export const tablesDir = join(root, 'public/audio/vvvf-tables');

export function convertPattern(yamlText: string) {
  return JSON.stringify(normalizeVvvf(parse(yamlText, { maxAliasCount: -1, merge: true }))) + '\n';
}

export function patternFiles() {
  return readdirSync(src)
    .filter((f) => f.endsWith('.yaml'))
    .map((f) => ({ yaml: join(src, f), json: join(out, basename(f, '.yaml') + '.json') }));
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  const check = process.argv.includes('--check');
  let bad = 0;
  for (const { yaml, json } of patternFiles()) {
    const text = convertPattern(readFileSync(yaml, 'utf8'));
    for (const t of (JSON.parse(text) as { CustomPwm: string[] }).CustomPwm) {
      if (!existsSync(join(tablesDir, t + '.bin'))) {
        console.error(`missing table ${t}.bin in ${tablesDir} (${basename(yaml)})`);
        bad++;
      }
    }
    if (check) {
      if (!existsSync(json) || readFileSync(json, 'utf8') !== text) {
        console.error('stale:', json);
        bad++;
      }
    } else {
      writeFileSync(json, text);
      console.log(json, text.length, 'bytes');
    }
  }
  if (bad) process.exit(1);
}
