import { MeshStandardNodeMaterial } from 'three/webgpu';
import { abs, atan, attribute, cameraPosition, clamp, float, floor, fract, max, min, mix, normalWorldGeometry, normalize, positionWorld, select, sin, smoothstep, step, vec2, vec3, vec4 } from 'three/tsl';
import { EDWARDS_FIELD, edwardsFrame } from '../track/courseDesign';
import { fbm, hash2, vnoise, type Float, type Vec2, type Vec3, type Vec4 } from './tslNoise';
import { wetness } from './weather';

/**
 * The ground of the Edwards course in one material, drawn from the place alone (no photo layers: the same at
 * every quality): the Mojave's sandy floor with its creosote scrub, graded bare around the pavements, and Rogers
 * Dry Lake, a pale, level playa of cracked clay. On the playa, what is painted there in oil: the edges of the
 * lakebed runways, the compass rose, and the game's finish band. The shore is `edwardsShore` of
 * track/landforms.ts, written out again here. In rain the playa darkens and stands under a film of water.
 *
 * Geometry: `gridGeometry(…, layered = true)`: `surf.x` says how far beyond the road's edge a place is.
 */
export interface LakeMarks {
  /** lakebed runways: a point on the centre line, its direction (unit), where the lines begin and end along it (m) and half the width between them */
  runways: { x: number; z: number; dx: number; dz: number; from: number; to: number; half: number }[];
  /** the compass rose: its middle, its radius and where its north points (degrees east of true north: it is laid out to magnetic north) */
  rose: { x: number; z: number; radius: number; north: number };
  /** the finish: a chequered band across the lakebed runway (a point on the line, the road's direction, half its width) */
  finish: { x: number; z: number; dx: number; dz: number; half: number };
}

const F = (n: unknown) => n as Float;
const V3 = (n: unknown) => n as Vec3;

/**
 * Dried clay breaks into polygons: the cells of points scattered one to a square. x = how near a place is to the
 * border between its cell and the next (0 on the crack), y = a number of its own for the cell.
 */
function clayCells(p: Vec2): { edge: Float; cell: Float } {
  const ip = floor(p).toVar(), fp = fract(p).toVar();
  let f1: Float = float(8), f2: Float = float(8), id: Float = float(0);
  for (let dx = -1; dx <= 1; dx++) for (let dz = -1; dz <= 1; dz++) {
    // (cell numbers are wrapped: the hash loses its digits a few kilometres from the origin)
    const c = ip.add(vec2(dx, dz)).mod(512).toVar() as unknown as Vec2;
    const o = vec2(hash2(c), hash2(c.add(vec2(37.2, 11.9)) as Vec2));
    const d = F(vec2(dx, dz).add(o).sub(fp).length().toVar());
    id = F(select(d.lessThan(f1), hash2(c.add(vec2(5.3, 91.7)) as Vec2), id).toVar());
    f2 = F(min(f2, max(f1, d)).toVar());
    f1 = F(min(f1, d).toVar());
  }
  return { edge: F(f2.sub(f1)), cell: id };
}

export function desertMaterial(marks: LakeMarks, far: boolean): MeshStandardNodeMaterial {
  const mat = new MeshStandardNodeMaterial({ metalness: 0, roughness: 1 });
  mat.envMapIntensity = 0.3;
  mat.name = far ? 'desert-far' : 'desert';
  const P = positionWorld as unknown as Vec3;
  const at = P.xz as unknown as Vec2;
  const N = normalize(normalWorldGeometry) as unknown as Vec3;
  const dist = F(P.sub(cameraPosition).length());
  const wet = wetness as unknown as Float;
  const e = edwardsFrame(), fld = EDWARDS_FIELD;
  const a = F(P.x.sub(fld.x).mul(e.ax).add(P.z.sub(fld.z).mul(e.az)));
  const b = F(P.x.sub(fld.x).mul(e.bx).add(P.z.sub(fld.z).mul(e.bz)));
  const shore = F(float(fld.runway.length).add(sin(b.div(700).add(0.4)).sub(Math.sin(0.4)).mul(70)).add(sin(b.div(230).add(2)).sub(Math.sin(2)).mul(30)));
  const n1 = fbm(at.div(170) as Vec2, 3, 2.3);
  const n2 = vnoise(at.div(13) as Vec2);
  // the shore is ragged: tongues of clay and sand a few metres deep
  const lake = F(smoothstep(-14, 14, a.sub(shore).add(n2.sub(0.5).mul(34))));
  // lines seen from far away are thinner than a pixel: they fade instead of flickering
  const aa = F(max(0.06, dist.mul(0.0011)));
  const line = (d: Float, half: number) => F(smoothstep(aa.add(half), float(half).sub(aa), d));
  const between = (x: Float, lo: number, hi: number) => F(smoothstep(float(lo).sub(aa), float(lo).add(aa), x).mul(smoothstep(float(hi).add(aa), float(hi).sub(aa), x)));

  // ---- the desert floor
  let desert = V3(mix(vec3(0.25, 0.19, 0.12), vec3(0.33, 0.265, 0.175), n1.mul(1.15)).mul(n2.mul(0.24).add(0.88)));
  let graded: Float = float(0);
  if (!far) {
    const surf = attribute('surf', 'vec4') as unknown as Vec4;
    // bare, levelled ground around the pavements and where the course runs beside them
    graded = F(float(1).sub(smoothstep(0.1, 0.8, surf.x)));
    const near = F(smoothstep(160, 40, dist));
    desert = V3(desert.mul(mix(float(1), vnoise(at.mul(1.9) as Vec2).mul(0.3).add(0.85), near)));
    // creosote bushes, one to a cell here and there: dark rounds, an even tint from far away
    const g = at.div(4.6) as Vec2;
    const cell = floor(g) as unknown as Vec2;
    const centre = cell.add(0.5).add(vec2(hash2(cell.add(3.1) as Vec2), hash2(cell.add(7.7) as Vec2)).sub(0.5).mul(0.55));
    const d = F(g.sub(centre).length().mul(4.6));
    const has = step(0.6, hash2(cell));
    const size = hash2(cell.add(1.3) as Vec2).mul(0.5).add(0.55);
    const seen = F(smoothstep(280, 110, dist));
    const open = F(float(1).sub(graded));
    const bush = F(has.mul(smoothstep(size, size.mul(0.55), d)).mul(open).mul(seen));
    desert = V3(mix(desert, vec3(0.085, 0.095, 0.06), bush.mul(0.8)));
    desert = V3(desert.mul(mix(float(1), float(0.88), open.mul(float(1).sub(seen)))));
    desert = V3(mix(desert, vec3(0.3, 0.245, 0.17).mul(n2.mul(0.16).add(0.92)), graded.mul(0.75)));
  } else desert = V3(desert.mul(0.88));
  // the ranges on the horizon: bare rock where the land is steep
  const rock = F(smoothstep(0.03, 0.22, float(1).sub(N.y)));
  desert = V3(mix(desert, vec3(0.19, 0.155, 0.125).mul(n1.mul(0.7).add(0.65)), rock));

  // ---- the playa
  let playa = V3(mix(vec3(0.47, 0.42, 0.335), vec3(0.56, 0.51, 0.42), n1.mul(1.15)).mul(n2.mul(0.08).add(0.96)));
  let oil: Float = float(0);
  if (!far) {
    // the clay's cracks: polygons a hand or two across in plates of a few metres; each plate a shade of its own.
    // A crack is finer than a pixel a few car lengths away: it thins out with the distance instead of flickering
    const fine = clayCells(at.mul(3.4) as Vec2), plates = clayCells(at.mul(0.23).add(3.7) as Vec2);
    const fineSeen = F(smoothstep(34, 5, dist)), plateSeen = F(smoothstep(170, 30, dist));
    const w = F(dist.mul(0.004).add(0.012));
    const crack = F(smoothstep(w.mul(3.4).add(0.03), w.mul(3.4), fine.edge).mul(fineSeen).mul(0.2)
      .add(smoothstep(w.mul(0.23).add(0.008), w.mul(0.23), plates.edge).mul(plateSeen).mul(0.1)));
    playa = V3(playa.mul(plates.cell.sub(0.5).mul(0.05).mul(plateSeen).add(1)).mul(fine.cell.sub(0.5).mul(0.035).mul(fineSeen).add(1)));
    playa = V3(playa.mul(float(1).sub(clamp(crack, 0, 0.5))));
    for (const r of marks.runways) {
      const u = F(P.x.sub(r.x).mul(r.dx).add(P.z.sub(r.z).mul(r.dz)));
      const v = F(P.x.sub(r.x).mul(r.dz).sub(P.z.sub(r.z).mul(r.dx)));
      const on = between(u, r.from, r.to);
      oil = F(max(oil, line(F(abs(abs(v).sub(r.half))), 1.1).mul(on)));
      // a bar across each end
      for (const end of [r.from, r.to]) oil = F(max(oil, line(F(abs(u.sub(end))), 1.4).mul(step(abs(v), r.half))));
      // tyres have rolled the clay smooth and a shade darker between the lines
      playa = V3(playa.mul(float(1).sub(on.mul(smoothstep(r.half, r.half * 0.5, abs(v))).mul(0.06))));
    }
    // the compass rose: two rings, a tick every 10°, longer rays every 30° and 45°, the four points from near the middle
    const c = marks.rose, R = c.radius;
    const qx = F(P.x.sub(c.x)), qz = F(P.z.sub(c.z));
    const rr = F(vec2(qx, qz).length());
    const bearing = F(atan(qx, qz.negate()).sub((c.north * Math.PI) / 180));
    const ray = (deg: number, from: number, half: number) => {
      const st = (deg * Math.PI) / 180;
      const off = F(abs(fract(bearing.div(st).add(0.5)).sub(0.5)).mul(st).mul(rr));
      return F(line(off, half).mul(between(rr, R * from, R)));
    };
    let rose = F(max(line(F(abs(rr.sub(R))), 1.3), line(F(abs(rr.sub(R * 0.84))), 0.8)));
    rose = F(max(max(rose, ray(10, 0.84, 0.7)), max(ray(30, 0.6, 0.9), max(ray(45, 0.36, 1.1), ray(90, 0.1, 1.5)))));
    oil = F(max(oil, rose.mul(step(rr, R + 3))));
    // the finish: two rows of squares across the runway
    const fin = marks.finish;
    const fu = F(P.x.sub(fin.x).mul(fin.dx).add(P.z.sub(fin.z).mul(fin.dz)));
    const fv = F(P.x.sub(fin.x).mul(fin.dz).sub(P.z.sub(fin.z).mul(fin.dx)));
    const SQ = 5;
    const check = F(abs(floor(fu.div(SQ)).add(floor(fv.div(SQ))).mod(2)));
    oil = F(max(oil, check.mul(between(fu, 0, 2 * SQ)).mul(between(F(abs(fv)), -1, fin.half))));
    oil = F(oil.mul(vnoise(at.mul(0.7) as Vec2).mul(0.3).add(0.72)));
    playa = V3(mix(playa, vec3(0.028, 0.025, 0.021), oil));
  }

  let col = V3(mix(desert, playa, lake));
  // ---- rain: sand drinks it, the clay turns dark and a film of water stands on it
  const film = F(wet.mul(lake).mul(smoothstep(0.3, 0.62, vnoise(at.div(37) as Vec2).mul(0.6).add(n2.mul(0.4)))));
  col = V3(col.mul(mix(float(1), mix(float(0.6), float(0.5), lake), wet)));
  col = V3(mix(col, col.mul(0.72), film));
  mat.colorNode = vec4(col, 1);
  const dry = F(mix(mix(float(0.96), float(0.9), lake), float(0.6), oil));
  mat.roughnessNode = clamp(mix(mix(dry, dry.mul(0.62), wet), float(0.07), film), 0.05, 1);
  // (the pools under the apron's lamps reach onto the ground beside it)
  mat.userData.lampBeam = 0.6;
  void graded;
  void min;
  return mat;
}
