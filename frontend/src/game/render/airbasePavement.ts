import * as THREE from 'three';
import { MeshStandardNodeMaterial } from 'three/webgpu';
import { abs, attribute, clamp, float, floor, fract, fwidth, max, min, mix, positionWorld, smoothstep, step, texture, vec2, vec3, vec4 } from 'three/tsl';
import type { Slab } from '../track/courseDesign';
import type { Track } from '../track/Track';
import { hash2, vnoise, type Float, type Vec2, type Vec3, type Vec4 } from './tslNoise';
import { wetness } from './weather';

/**
 * The pavements of an airfield in one material and one mesh: the taxiways (asphalt, a strip along the course), the
 * runway and the apron (concrete slabs). Every vertex says where it is on its surface: `pv` = (metres right of the
 * surface's centre line, metres along it, the kind, half the surface's width).
 *
 * Runway: the markings of a precision runway at their real sizes (FAA AC 150/5340-1, widened as for a 300 ft
 * runway): threshold bars, the designation (number and letter from `runwayNumbers`), centre line (120 ft on, 80 ft
 * off), aiming points at 1,000 ft, touchdown zone bars to 3,000 ft, side stripes; the tyres' rubber where aircraft
 * touch down. Taxiway: yellow centre line, double yellow edge lines, the holding position before the runway.
 * Apron: the taxi lane, the lead-off to the taxiway, lead-ins to the parking spots and the game's start line.
 */
export const PAVE_TAXI = 0, PAVE_RUNWAY = 1, PAVE_APRON = 2;

export interface PaveMarks {
  runwayLength: number;
  /** track distance of the holding position on the taxiway */
  hold: number;
  /** the apron's taxi lane (m right of the apron's centre line), where the lead-off bend begins along it, its radius */
  lane: number;
  leadOff: number;
  turn: number;
  /** the parking spots' lead-ins: every this many metres along the apron, this far to the left of the lane */
  spots: { every: number; depth: number };
  /** the start line: metres along the apron */
  start: number;
}

/** numbers block on the runway (m): its width, its length, and where it begins behind the threshold */
const NUM_W = 22, NUM_H = 44, NUM_AT = 62;

/**
 * The runway's designations as a mask: left half "04" over "R", right half "22" over "L" (the letter nearer the
 * threshold), drawn as strokes (no font: the page's may not be there yet).
 */
export function runwayNumbers(near: [string, string], far: [string, string]): THREE.Texture {
  const c = document.createElement('canvas');
  c.width = 512;
  c.height = 512;
  const g = c.getContext('2d')!;
  g.fillStyle = '#000';
  g.fillRect(0, 0, 512, 512);
  g.strokeStyle = '#fff';
  g.lineCap = 'butt';
  g.lineJoin = 'miter';
  const kx = 256 / NUM_W, ky = 512 / NUM_H;
  g.lineWidth = 1.5 * kx;
  // glyphs on a 3 × 5 grid (x right, y up)
  const GLYPHS: Record<string, [number, number][][]> = {
    '0': [[[0.4, 0], [2.6, 0], [3, 0.6], [3, 4.4], [2.6, 5], [0.4, 5], [0, 4.4], [0, 0.6], [0.4, 0], [2.6, 0]]],
    '2': [[[0, 4.1], [0.6, 5], [2.4, 5], [3, 4.2], [3, 3.2], [0, 0], [3.2, 0]]],
    '4': [[[2.3, -0.2], [2.3, 5], [0, 1.5], [3.2, 1.5]]],
    R: [[[0, -0.2], [0, 5], [2.3, 5], [3, 4.4], [3, 3.2], [2.3, 2.6], [0, 2.6]], [[1.3, 2.6], [3, -0.2]]],
    L: [[[0, 5.2], [0, 0], [3.2, 0]]],
  };
  const glyph = (ch: string, block: number, x0: number, y0: number, w: number, h: number) => {
    for (const path of GLYPHS[ch] ?? []) {
      g.beginPath();
      path.forEach(([px, py], k) => {
        const X = block * 256 + (x0 + (px / 3) * w) * kx, Y = 512 - (y0 + (py / 5) * h) * ky;
        if (k) g.lineTo(X, Y);
        else g.moveTo(X, Y);
      });
      g.stroke();
    }
  };
  [near, far].forEach(([num, letter], block) => {
    glyph(num[0], block, 3.2, 24, 5.4, 17);
    glyph(num[1], block, 13.4, 24, 5.4, 17);
    glyph(letter, block, 8.3, 2.5, 5.4, 17);
  });
  const t = new THREE.CanvasTexture(c);
  t.generateMipmaps = true;
  t.minFilter = THREE.LinearMipmapLinearFilter;
  t.anisotropy = 8;
  return t;
}

const F = (n: unknown) => n as Float;
const V3 = (n: unknown) => n as Vec3;

export function pavementMaterial(marks: PaveMarks, numbers: THREE.Texture): MeshStandardNodeMaterial {
  const mat = new MeshStandardNodeMaterial({ metalness: 0, roughness: 1 });
  mat.envMapIntensity = 0.5;
  mat.name = 'pavement';
  // (the pavement lies a hand's breadth over the ground it is laid on: it wins where the two are too close to tell)
  mat.polygonOffset = true;
  mat.polygonOffsetFactor = -2;
  mat.polygonOffsetUnits = -4;
  mat.userData.lampBeam = 1;
  const pv = attribute('pv', 'vec4') as unknown as Vec4;
  const lat = pv.x as Float, along = pv.y as Float, kind = pv.z as Float, half = pv.w as Float;
  const at = (positionWorld as unknown as Vec3).xz as unknown as Vec2;
  const wet = wetness as unknown as Float;
  const isTaxi = F(step(kind, 0.5)), isRunway = F(step(0.5, kind).mul(step(kind, 1.5))), isApron = F(step(1.5, kind));
  // a pixel's size on the surface, across and along: what a line's edge is smoothed over
  const aL = F(clamp(fwidth(lat), 0.004, 4)), aA = F(clamp(fwidth(along), 0.004, 40));
  const across = (x: Float, lo: number, hi: number) => F(smoothstep(float(lo).sub(aL), float(lo).add(aL), x).mul(smoothstep(float(hi).add(aL), float(hi).sub(aL), x)));
  const lengthwise = (x: Float, lo: number, hi: number) => F(smoothstep(float(lo).sub(aA), float(lo).add(aA), x).mul(smoothstep(float(hi).add(aA), float(hi).sub(aA), x)));
  const n1 = vnoise(at.div(19) as Vec2), n2 = vnoise(at.mul(0.83) as Vec2), fine = vnoise(at.mul(5.1) as Vec2);
  const inside = F(half.sub(abs(lat)));

  // ---- the surfaces
  // concrete: slabs 25 ft square, each a shade of its own, the joints sealed dark
  const SL = 7.62;
  const cell = vec2(floor(lat.div(SL)), floor(along.div(SL))) as unknown as Vec2;
  const tone = F(hash2(cell).mul(0.12).add(0.94));
  const jl = F(abs(fract(lat.div(SL)).sub(0.5)).mul(-SL).add(SL / 2)), ja = F(abs(fract(along.div(SL)).sub(0.5)).mul(-SL).add(SL / 2));
  const joint = F(max(smoothstep(aL.add(0.035), aL.mul(0.3), jl).mul(clamp(float(0.05).div(aL), 0, 1)), smoothstep(aA.add(0.035), aA.mul(0.3), ja).mul(clamp(float(0.05).div(aA), 0, 1))));
  let concrete = V3(vec3(0.33, 0.325, 0.31).mul(tone).mul(n1.mul(0.16).add(0.92)).mul(fine.mul(0.1).add(0.95)));
  concrete = V3(mix(concrete, vec3(0.035, 0.034, 0.033), joint.mul(0.85)));
  // stains: oil and hydraulic fluid on the apron, grey streaks of weather everywhere
  concrete = V3(concrete.mul(float(1).sub(smoothstep(0.62, 0.9, n2.mul(0.6).add(n1.mul(0.4))).mul(isApron).mul(0.3))));
  const asphalt = V3(vec3(0.062, 0.062, 0.066).mul(n1.mul(0.3).add(0.85)).mul(fine.mul(0.3).add(0.85)));
  let col = V3(mix(concrete, asphalt, isTaxi));
  let rough = F(mix(float(0.9), float(0.86), isTaxi));

  // ---- the runway
  const L = marks.runwayLength;
  const fromEnd = F(min(along, float(L).sub(along)));
  const p = F(abs(lat));
  // rubber: where the main wheels come down, streaked along the runway
  const streak = vnoise(vec2(lat.mul(1.3), along.div(55)) as Vec2);
  const rubber = F(lengthwise(fromEnd, 150, 1150).mul(smoothstep(17, 3, p)).mul(streak.mul(0.55).add(0.3)).mul(isRunway));
  col = V3(mix(col, vec3(0.022, 0.022, 0.024), rubber.mul(0.82)));
  rough = F(mix(rough, float(0.7), rubber));
  let white: Float = float(0);
  // centre line: 120 ft stripes, 80 ft gaps, 3 ft wide
  const dash = F(step(fract(along.sub(115).div(60.96)), 0.6));
  white = F(max(white, across(p, -1, 0.46).mul(dash).mul(lengthwise(fromEnd, 115, 1e6))));
  // side stripes
  white = F(max(white, across(inside, 0.6, 1.5)));
  // threshold: sixteen bars
  const bars = F(step(fract(p.sub(2.6).div(5.2)), 0.5).mul(across(p, 2.6, 41.6)));
  white = F(max(white, bars.mul(lengthwise(fromEnd, 6, 51.7))));
  // aiming points
  white = F(max(white, across(p, 11, 20).mul(lengthwise(fromEnd, 305, 351))));
  // touchdown zone: three, two, two, one, one bars a side
  for (const [atFt, count] of [[500, 3], [1500, 2], [2000, 2], [2500, 1], [3000, 1]] as const) {
    const s0 = atFt * 0.3048;
    const group = F(across(p, 11, 11 + count * 3.3 - 1.5).mul(step(fract(p.sub(11).div(3.3)), 1.8 / 3.3)));
    white = F(max(white, group.mul(lengthwise(fromEnd, s0, s0 + 22.9))));
  }
  // the designations, each read from its own end
  const numNear = (texture(numbers, vec2(lat.add(NUM_W / 2).div(NUM_W).mul(0.5), along.sub(NUM_AT).div(NUM_H))) as unknown as Vec4).r;
  const numFar = (texture(numbers, vec2(lat.negate().add(NUM_W / 2).div(NUM_W).mul(0.5).add(0.5), float(L).sub(along).sub(NUM_AT).div(NUM_H))) as unknown as Vec4).r;
  const inBlock = F(step(p, NUM_W / 2 - 0.2).mul(step(NUM_AT + 0.2, fromEnd)).mul(step(fromEnd, NUM_AT + NUM_H - 0.2)));
  white = F(max(white, mix(numFar, numNear, step(along, L / 2)).mul(inBlock)));
  white = F(white.mul(isRunway));

  // ---- the taxiway
  let yellow: Float = float(0);
  yellow = F(max(yellow, across(p, -1, 0.16)));
  yellow = F(max(yellow, max(across(inside, 0.35, 0.5), across(inside, 0.65, 0.8))));
  // holding position: two solid lines, then two dashed ones on the runway's side
  const h = F(along.sub(marks.hold));
  const solid = F(max(lengthwise(h, 0, 0.3), lengthwise(h, 0.6, 0.9)));
  const dashed = F(max(lengthwise(h, 1.2, 1.5), lengthwise(h, 1.8, 2.1)).mul(step(fract(lat.div(1.8)), 0.5)));
  yellow = F(max(yellow, max(solid, dashed).mul(step(0.9, inside))));
  yellow = F(yellow.mul(isTaxi));

  // ---- the apron
  const dl = F(lat.sub(marks.lane));
  let lane = across(F(abs(dl)), -1, 0.16);
  // the lead-off to the taxiway: a quarter circle from the lane, then straight to the apron's edge
  const cA = F(along.sub(marks.leadOff)), cL = F(dl.sub(marks.turn));
  const onArc = F(step(cA, 0).mul(step(cL, 0)));
  const arcD = F(abs(vec2(cA, cL).length().sub(marks.turn)));
  const aBoth = F(max(aL, aA));
  lane = F(max(lane, smoothstep(aBoth.add(0.16), float(0.16).sub(aBoth), arcD).mul(onArc)));
  lane = F(max(lane, lengthwise(F(abs(cA.add(marks.turn))), -1, 0.16).mul(step(0, cL))));
  // the parking spots' lead-ins
  const spot = F(abs(fract(along.div(marks.spots.every)).sub(0.5)).mul(marks.spots.every));
  lane = F(max(lane, lengthwise(spot, -1, 0.13).mul(across(dl, -marks.spots.depth, 0))));
  yellow = F(max(yellow, lane.mul(isApron)));
  // the start line: two white bars across the lane
  const st = F(along.sub(marks.start));
  white = F(max(white, max(lengthwise(st, -0.9, -0.3), lengthwise(st, 0.3, 0.9)).mul(across(F(abs(dl)), -1, 55)).mul(isApron)));

  // paint: worn by the weather and by tyres
  const worn = F(n2.mul(0.22).add(0.8).mul(float(1).sub(rubber.mul(0.75))));
  col = V3(mix(col, vec3(0.72, 0.72, 0.68), white.mul(worn)));
  col = V3(mix(col, vec3(0.7, 0.5, 0.045), yellow.mul(worn)));
  const paint = F(max(white, yellow));
  rough = F(mix(rough, float(0.62), paint));

  // ---- rain: dark and glossy, water standing in the slabs' hollows
  const puddle = F(smoothstep(0.6, 0.72, n1.mul(0.55).add(n2.mul(0.45))).mul(wet));
  col = V3(col.mul(mix(float(1), mix(float(0.55), float(0.68), paint), wet)));
  col = V3(mix(col, col.mul(0.75), puddle));
  mat.colorNode = vec4(col, 1);
  mat.roughnessNode = clamp(mix(mix(rough, rough.mul(0.35), wet), float(0.04), puddle), 0.04, 1);
  return mat;
}

type Out = { pos: number[]; pv: number[]; idx: number[] };

/** rows of points (left → right), one row after another along the surface: triangles facing up */
function grid(out: Out, rows: number, cols: number, base: number) {
  for (let r = 0; r < rows - 1; r++)
    for (let c = 0; c < cols - 1; c++) {
      const a = base + r * cols + c, b = a + 1, d = a + cols, e = d + 1;
      out.idx.push(a, b, d, b, e, d);
    }
}

/** A paved rectangle: `heightAt` is the ground's height, `lift` what the pavement lies over it. */
export function addSlab(out: Out, slab: Slab, kind: number, heightAt: (x: number, z: number) => number, lift: number, step = 40, cols = 5) {
  const fx = Math.sin(slab.heading), fz = Math.cos(slab.heading), rx = -fz, rz = fx;
  const rows = Math.ceil(slab.length / step) + 1;
  const base = out.pos.length / 3;
  for (let r = 0; r < rows; r++) {
    const along = Math.min(slab.length, r * step);
    for (let c = 0; c < cols; c++) {
      const lat = (c / (cols - 1) - 0.5) * slab.width;
      const x = slab.x + fx * along + rx * lat, z = slab.z + fz * along + rz * lat;
      out.pos.push(x, heightAt(x, z) + lift, z);
      out.pv.push(lat, along, kind, slab.width / 2);
    }
  }
  grid(out, rows, cols, base);
}

/** The course's own paved strip from sample `a` to `b` (a taxiway): as wide as `track.pave`. */
export function addStrip(out: Out, track: Track, a: number, b: number, kind: number, lift: number) {
  const cols = 5, v = new THREE.Vector3();
  const base = out.pos.length / 3;
  let rows = 0;
  for (let i = a; ; i = Math.min(b, i + 2)) {
    const half = track.pave[i] / 2;
    for (let c = 0; c < cols; c++) {
      const lat = (c / (cols - 1) - 0.5) * 2 * half;
      track.pointAt(i, lat, v);
      out.pos.push(v.x, v.y + lift, v.z);
      out.pv.push(lat, i, kind, half);
    }
    rows++;
    if (i >= b) break;
  }
  grid(out, rows, cols, base);
}

export function pavementGeometry(out: Out) {
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(out.pos, 3));
  g.setAttribute('pv', new THREE.Float32BufferAttribute(out.pv, 4));
  const n = new Float32Array(out.pos.length);
  for (let i = 1; i < n.length; i += 3) n[i] = 1;
  g.setAttribute('normal', new THREE.BufferAttribute(n, 3));
  g.setIndex(out.idx);
  return g;
}
