import { describe, expect, it } from 'vitest';
import { decodeGhost, encodeGhost, GhostPlayer, GhostRecorder } from '../race/Ghost';
import { Quaternion, Vector3 } from 'three';

describe('Ghost codec', () => {
  it('round-trips recorded frames with millimetre precision', async () => {
    const rec = new GhostRecorder();
    const q = new Quaternion();
    for (let k = 0; k <= 3600; k++) {
      const t = k / 60;
      q.setFromAxisAngle(new Vector3(0, 1, 0), t * 0.3);
      rec.sample(t, new Vector3(-220 + t * 30, 430 - t * 2, -620 + Math.sin(t) * 40), q, Math.sin(t * 2) * 0.4);
    }
    const data = rec.data();
    expect(data.frames.length).toBe(1201);
    const enc = await encodeGhost(data);
    expect(enc.frame_count).toBe(1201);
    expect(enc.data.length).toBeLessThan(60_000);
    const dec = await decodeGhost(enc);
    for (let i = 0; i < data.frames.length; i += 37) {
      const a = data.frames[i], b = dec.frames[i];
      expect(Math.abs(a.x - b.x)).toBeLessThan(0.002);
      expect(Math.abs(a.y - b.y)).toBeLessThan(0.002);
      expect(Math.abs(a.z - b.z)).toBeLessThan(0.002);
      expect(Math.abs(a.qy - b.qy)).toBeLessThan(0.001);
      expect(Math.abs(a.steer - b.steer)).toBeLessThan(0.001);
    }
    const player = new GhostPlayer(dec);
    expect(player.duration).toBeCloseTo(60, 1);
    const pos = new Vector3();
    player.pose(30.025, pos, new Quaternion());
    expect(pos.x).toBeCloseTo(-220 + 30.025 * 30, 0);
  });

  it('rejects corrupt payloads', async () => {
    const enc = await encodeGhost({ intervalMs: 50, frames: [{ x: 0, y: 0, z: 0, qx: 0, qy: 0, qz: 0, qw: 1, steer: 0 }] });
    await expect(decodeGhost({ ...enc, frame_count: 5 })).rejects.toThrow();
  });
});
