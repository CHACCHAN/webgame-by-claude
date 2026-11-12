import { createHash } from 'node:crypto';
import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { COURSE_ORDER } from '../../game/track/courses';
import FILMS from './courseFilms.json';

const file = (name: string) => fileURLToPath(new URL(`../../../public/video/courses/${name}`, import.meta.url));

// The course select asks for a film, its still and its track with the film's stamp, because their names are fixed
// and browsers and the CDN keep `/video/` for a day: a film recorded again without a new stamp is shown as the old
// one with the new one's track. `tools/course-clip-encode.sh` writes the stamp.
describe('the course films\' stamps', () => {
  const films = FILMS as Record<string, string>;
  it('every film in the tree has the stamp of its content', () => {
    for (const [id, stamp] of Object.entries(films)) {
      expect(existsSync(file(`${id}.mp4`)), id).toBe(true);
      expect(createHash('sha1').update(readFileSync(file(`${id}.mp4`))).digest('hex').slice(0, 8), id).toBe(stamp);
      expect(existsSync(file(`${id}.jpg`)) && existsSync(file(`${id}.json`)), id).toBe(true);
    }
  });
  it('a course with a film has a stamp, and a stamp belongs to a course', () => {
    for (const id of COURSE_ORDER) if (existsSync(file(`${id}.mp4`))) expect(films[id], id).toBeTruthy();
    for (const id of Object.keys(films)) expect(COURSE_ORDER as readonly string[]).toContain(id);
  });
});
