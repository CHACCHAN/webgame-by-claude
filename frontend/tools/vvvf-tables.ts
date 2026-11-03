/** The CHM / SHE switching-angle tables a pattern uses, read from public/audio/vvvf-tables/ (Node tools and tests). */
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import type { VvvfData } from '../src/game/audio/vvvf/data';

const dir = join(fileURLToPath(import.meta.url), '..', '..', 'public/audio/vvvf-tables');

export function tableFiles(data: VvvfData): Record<string, ArrayBuffer> {
  const out: Record<string, ArrayBuffer> = {};
  for (const name of data.CustomPwm) {
    const b = readFileSync(join(dir, name + '.bin'));
    out[name] = b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength) as ArrayBuffer;
  }
  return out;
}
