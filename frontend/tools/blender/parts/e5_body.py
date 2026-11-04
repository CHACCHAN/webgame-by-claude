"""
JR East E5 series: the body shells of the three cars the game shows (E523 = car 1, E525 = a pantograph car, E514 =
car 10, Gran Class), lofted from the sections of e5_shape along z; the recessed doors; the gangway ends with the
full-circumference hood (全周幌) and the inter-car dampers; and the painted atlas (livery, windows, doors, the canopy's
glass, the nose cover's seams, the lower body's covers) drawn with numpy texel by texel from the 3D position under
each texel.

  add_materials(m, tex_dir, shells)  plain materials, the painted atlas (e5_body.png + _mr), the sign material
  Shell(kind).build(part)            kind 'e523' | 'e525' | 'e514'; part: body_n1000.UVPart
  hood(part, z_end, sign)            the car's half of the gangway hood, and the damper
  cab_fittings(part, kind)           head lamp pods, wipers, side displays, car numbers (JR mark), service logos
  set_variant(name)                  e5 (JR East) or h5 (JR Hokkaido): belt colour, logos, sign textures

Figures (see e5_shape for the body's): ja.wikipedia 新幹線E5系・H5系電車 (2026-11-03): normal doors 975 mm clear
(wheelchair cars 1,230), seat pitch 1,040 mm (ordinary), 1,300 mm (Gran Class), E523 29 seats (6 rows), E525 85
(17 rows), E514 18 (6 rows); doors only at the 新函館北斗 end on the Gran Class car; doors at both ends on ordinary cars;
crew door then a passenger door behind the cab (an equipment room in between, so both stand well back).
Measured on photos (Commons: "JRE Series-E5-E523-1 Outside-Door.jpg" (CC0), "E525-101.jpg", "E526-101.jpg",
"E525-1.jpg", "JRE E523-1.jpg", "E5 S11 Sendai 20090725.JPG", "H523-1 omiya 20160327.jpg"):
- door outline 1.05 × 1.86 m (sill 1.30, top 3.16), corner radius 0.10; crew door 0.70 wide; door windows
  0.40 × 0.58 (passenger, narrow, round ends) and 0.40 × 0.60 (crew); a drip strip over each door;
- side windows 0.40 × 0.45 m (2.17–2.62 m), corner radius 0.08, one per seat row;
- pink stripe 1.90–2.08 m (also across the doors); side destination display 0.60 × 0.17 m at 2.93 m beside a door;
- lower body: a long seam at 1.02 m (the top of the hinged cover panels), panels 1.2–1.6 m long with louvre grilles
  over the equipment; the carbon bogie covers round each bogie; skirt bottom 0.30 m above the rail;
- the gangway: dark rubber hood all round the section between the cars, a damper (black cylinder, plated rod) low
  on each side.
Layouts along the car (z, game car frame; estimates from the photos with a projective fit, ±0.3 m):
  E523: crew door −0.45, passenger door −1.70, 6 windows from −3.25 at 1.04 m, rear door −10.0;
  E514: crew door −0.45, passenger door −1.70, 6 windows from −3.90 at 1.07 m, no rear door;
  E525: doors +7.95 (toilet end, pantograph above) and −11.40, 17 windows from +6.60 at 1.04 m.
"""
import math
import os

import bmesh
import bpy
import numpy as np
from mathutils import Vector

import train_kit as K
import e5_shape as S
import body_n1000 as BD

P = 'e5_'
SILL = 1.30
DOOR_DEPTH = 0.018
END_R = 0.14            # rounding of a gangway end's edges

# paint (sRGB): sampled on daylight photos (p24, q09, p02 of the list) and the colour names' published swatches
GREEN = (0.185, 0.585, 0.500)       # 常盤グリーン: a deeper teal-green (U15 / U19 daylight; wiki #489a83)
WHITE = (0.850, 0.862, 0.866)       # 飛雲ホワイト
PINK = (0.870, 0.215, 0.555)        # つつじ / はやてピンク
GLASS = (0.040, 0.050, 0.058)       # tinted cab glass
SIDE_GLASS = (0.105, 0.118, 0.125)  # saloon windows (≤ 0.30 sRGB for the game's night glow)
GLASS_REFL = (0.74, 0.80, 0.77)     # the canopy's glass: a dark diffuse part, but mirror-like (metallic, smooth): it shows
GLASS_METAL = 0.92                  # the sky pale grey-green as on the photos (diffuse ≈ 0.045 linear, F0 ≈ 0.55)
LAMP_BAND = (0.64, 0.69, 0.68)      # the glass over the lamps' housing: a touch darker
FRAME = (0.720, 0.730, 0.745)       # the light grey frame round the visor (head-on U19)
# the visor's outlines head-on (U19 photo, aligned on the roof line): the glass's top arc, the windscreen's half width
# at its foot and its top (a rounded trapezoid), the pillar between it and the side windows, the bar under the lamps
ARC_Y, ARC_K = 3.00, 0.30
WS_W = (0.60, 0.50)
PILLAR = 0.04
LAMP_BAR = 2.755
VISOR_REAR = 7.25                   # the side windows' rear edge (distance from the tip)
GASKET = (0.10, 0.105, 0.11)
SEAM = (0.30, 0.31, 0.32)
UNDER = (0.16, 0.16, 0.165)
COVER = (0.78, 0.79, 0.795)         # the lower cover panels: the same white, a touch duller
GRILLE = (0.42, 0.43, 0.44)

# ---------------------------------------------------------------- line variants
# e5: JR East (はやぶさ, 東北新幹線). h5: JR Hokkaido's H5 (北海道新幹線): the same cars, the belt 彩香パープル
# (ja.wikipedia: #6c5098; sampled on "H5系 ロゴマーク.JPG" in daylight ≈ #774397: we take between), the doors' insides
# 萌黄 (moegi: their cabin side, not seen on our closed doors), its own logo on cars 1, 3, 5, 7 and 10 (all three
# of ours: car 7 is H525-101), numbers H5xx.
VARIANT = 'e5'
BELT = {'e5': (0.870, 0.215, 0.555), 'h5': (0.440, 0.300, 0.600)}
JAMB = {'e5': '#30a090', 'h5': '#30a090'}   # (moegi is the leaves' cabin side: not seen on our closed doors)
# service logos as decals on the green (e5_textures.py draws them; zc, yc, width, height in the car's frame):
# E5: cars 1 and 10 only (ja.wikipedia: 先頭車両の両側面), between the rear door and the gangway ("JRE Series-E5-E523-1
# Outside-Door.jpg"); H5: the end cars at the same place (the real ones show an upright version of the logo there:
# we use the one drawing, scaled to fit), the middle car's beside its pantograph-end door ("H525-101 omiya
# 20160327.jpg": ≈ 2.2 × 1.0 m from 0.45 m behind the door, its foot just over the belt)
LOGOS = {
    'e5': {'e523': (-11.30, 2.71, 0.47, 0.58), 'e514': (-11.30, 2.71, 0.47, 0.58)},
    'h5': {'e523': (-11.30, 2.62, 1.30, 0.59), 'e514': (-11.30, 2.62, 1.30, 0.59), 'e525': (10.02, 2.63, 2.20, 1.00)},
}


def set_variant(name):
    global VARIANT, PINK
    if name not in BELT:
        raise ValueError(f'unknown variant {name}')
    VARIANT = name
    PINK = BELT[name]


def tex_dir_variant():
    return SIGNS if VARIANT == 'e5' else os.path.join(SIGNS, VARIANT)


LAYOUT = {
    'e523': dict(cab=True, doors=((-0.45, 0.70, 'crew'), (-1.70, 1.05, 'pass'), (-10.00, 1.05, 'pass')),
                 windows=tuple(-3.25 - 1.04 * k for k in range(6)), display=(-2.75, 1)),
    'e514': dict(cab=True, doors=((-0.45, 0.70, 'crew'), (-1.70, 1.05, 'pass')),
                 windows=tuple(-3.90 - 1.07 * k for k in range(6)), display=(-2.75, 1)),
    'e525': dict(cab=False, doors=((7.95, 1.05, 'pass'), (-11.40, 1.05, 'pass')),
                 windows=tuple(6.60 - 1.04 * k for k in range(17)), display=(6.95, -1)),
}
KINDS = ('e523', 'e525', 'e514')
DOOR_H = (SILL, 3.163)
WIN_Y = (2.17, 2.62)
WIN_W = 0.40

# ---------------------------------------------------------------- texture atlas layout
ATLAS = int(os.environ.get("E5_ATLAS", "4096"))     # E5_ATLAS=2048 for quick check renders
STRIP = {k: i for i, k in enumerate(KINDS)}       # each car: a horizontal strip, a third of the atlas
U_RANGE = {'e523': (-12.30, 14.02), 'e514': (-12.30, 14.02), 'e525': (-12.30, 12.30)}
_SEG_W = {'bottom': 0.05, 'inner': 0.25, 'skirt': 1.0, 'corner': 1.0, 'lside': 1.0, 'cusp': 1.0, 'uside': 1.0, 'roof': 0.55}


def _vk():
    """texture v (0..1 within a strip) for each half-section point, from the body section's weighted arc length"""
    pts = S.half_section(_body_params())
    v = [0.0]
    for k in range(1, S.HALF_N):
        (x0, y0), (x1, y1) = pts[k - 1], pts[k]
        seg = S.SEGMENTS[k]
        L = max(math.hypot(x1 - x0, y1 - y0), 0.004)
        v.append(v[-1] + L * _SEG_W[seg])
    v = np.array(v)
    return v / v[-1]


def _body_params():
    p = dict(S.BODY)
    p['hc'] = 0.12
    return p


def params_at(d, cab):
    """section parameters at distance d from the tip (a middle car is all body)"""
    p = S.nose_params(d) if cab else dict(S.BODY)
    p['hc'] = max(p['hc'], 0.02)
    lift = p['yb'] + 0.25 * max(p['rby'], 0.05)
    if cab and d < 3.0 and p['ybc'] < lift:
        # ahead of the bogie well the jaw's underside is one gently convex surface (no channel up the middle)
        p['ybc'] = p['yb'] - 0.012
        p['jaw'] = True
    else:
        # (the bogie well's ceiling stays below the crease: with the tight lip its inner wall stands far out)
        p['ybc'] = min(max(p['ybc'], lift), p['ym'] - 0.04)
    return p


VK = _vk()

# The atlas's u runs along z, stretched towards a cab's tip, where the sections close up fast and the front face
# would otherwise get a few texel columns: u ∝ z + TIP_C·ln(1 + d / TIP_D0) (≈ 11× the density at the tip).
TIP_C, TIP_D0 = 0.5, 0.05


def u_metric(z, cab):
    if not cab:
        return z
    d = np.maximum(S.NOSE_TIP - np.asarray(z, float), -0.02)
    return z - TIP_C * np.log1p(d / TIP_D0)


_ZG = np.linspace(-13.0, S.NOSE_TIP + 0.05, 40000)
_MG = u_metric(_ZG, True)


def z_of_metric(m, cab):
    return np.asarray(m, float) if not cab else np.interp(m, _MG, _ZG)
J_SILL = S.SEGMENTS.index('lside') + S.L_SILL               # the lower side's sill point: y = 1.30 on the body
J_TOP = S.SEGMENTS.index('uside') + 5                       # upper side fraction 0.974: y = 3.163


def section_points(d, cab):
    """half section [(x, y)] at distance d from the nose tip, the top's relief (canopy bubble, valleys) added"""
    p = params_at(d, cab)
    pts = S.half_section(p)
    if cab and S.RELIEF_D[0] < d < S.RELIEF_D[1]:
        j_up = S.SEGMENTS.index('uside')
        xs = np.array([x for x, _ in pts[j_up:]])
        r = S.relief_a(xs, np.full_like(xs, d))
        pts = pts[:j_up] + [(x, y + float(dy)) for (x, y), dy in zip(pts[j_up:], r)]
    return pts


def _normals2d(pts):
    """outward 2D normals of a half section (x ≥ 0), from neighbouring points"""
    out = []
    n = len(pts)
    for j in range(n):
        a = pts[max(j - 1, 0)]
        b = pts[min(j + 1, n - 1)]
        tx, ty = b[0] - a[0], b[1] - a[1]
        L = math.hypot(tx, ty) or 1.0
        out.append((ty / L, -tx / L))        # walking up the left side, the outside is on the right
    return out


class Shell:
    def __init__(self, kind):
        self.kind = kind
        L = LAYOUT[kind]
        self.cab = L['cab']
        self.doors = L['doors']
        self.z_rear = -S.END
        self.z_front = S.NOSE_TIP if self.cab else S.END
        self.grid = None     # [(z, [(x, y)])] for painting

    # -------------------------------------------------------------- stations along z
    def stations(self):
        """[(z, inset)]: inset > 0 rounds a gangway end"""
        zs = set()
        z_body_front = S.NOSE_TIP - S.NOSE_LEN if self.cab else S.END - END_R
        z = -S.END + END_R
        while z < z_body_front - 1e-6:
            zs.add(round(z, 5))
            z += 0.6
        zs.add(round(z_body_front, 5))
        for zc, w, _ in self.doors:
            zs.add(round(zc - w / 2, 5))
            zs.add(round(zc + w / 2, 5))
        out = sorted(zs)
        # drop stations closer than 5 cm to a door edge (keep the door's)
        edges = {round(zc + s * w / 2, 5) for zc, w, _ in self.doors for s in (-1, 1)}
        keep = []
        for z in out:
            if z not in edges and any(abs(z - e) < 0.05 for e in edges):
                continue
            keep.append(z)
        st = [(z, 0.0) for z in keep]
        # the rounded ends
        rear = []
        for k in range(1, 5):
            phi = (math.pi / 2) * k / 4
            rear.append((-S.END + END_R * (1 - math.sin(phi)), END_R * (1 - math.cos(phi))))
        st = list(reversed(rear)) + st
        if self.cab:
            # the nose: dense near the tip and where the canopy and the cusp change quickly
            # (fine over the canopy bubble and its valleys, whose foot and flanks turn quickly)
            ds = []
            d = S.NOSE_LEN - 0.25
            while d > 2.0:
                ds.append(d)
                d -= 0.25 if d > 10.4 else (0.085 if d > 3.6 else 0.14)
            ds += list(np.geomspace(2.0, 0.006, 26))
            for d in ds:
                st.append((S.NOSE_TIP - d, 0.0))
        else:
            for k in range(1, 5):
                phi = (math.pi / 2) * k / 4
                st.append((S.END - END_R * (1 - math.sin(phi)), END_R * (1 - math.cos(phi))))
        st.sort(key=lambda s: s[0])
        return st

    # -------------------------------------------------------------- the loft
    def rings(self):
        out = []
        for z, inset in self.stations():
            d = S.NOSE_TIP - z if self.cab else 99.0
            pts = section_points(d, self.cab)
            if inset > 0:
                nrm = _normals2d(pts)
                pts = [(max(x - nx * inset, 0.0) if j not in (0, len(pts) - 1) else 0.0, y - ny * inset)
                       for j, ((x, y), (nx, ny)) in enumerate(zip(pts, nrm))]
            out.append((z, pts))
        return out

    def uv(self, z, j):
        m0, m1 = (u_metric(z_, self.cab) for z_ in U_RANGE[self.kind])
        s = STRIP[self.kind]
        u = float((u_metric(z, self.cab) - m0) / (m1 - m0))
        v = (s + 0.004 + 0.992 * VK[j]) / 3.0
        return (min(max(u, 0.0), 1.0), v)

    def in_door(self, za, zb, j):
        if not (J_SILL <= j < J_TOP):
            return None
        for zc, w, _ in self.doors:
            if za >= zc - w / 2 - 1e-6 and zb <= zc + w / 2 + 1e-6:
                return (zc, w)
        return None

    def build(self, part):
        mat = P + 'body_' + self.kind
        R = self.rings()
        self.grid = R
        n = S.HALF_N
        for i in range(len(R) - 1):
            (za, A), (zb, Bp) = R[i], R[i + 1]
            for j in range(n - 1):
                door = self.in_door(za, zb, j)
                for side in (1, -1):
                    pa = (side * A[j][0], A[j][1], za)
                    pb = (side * Bp[j][0], Bp[j][1], zb)
                    pc = (side * Bp[j + 1][0], Bp[j + 1][1], zb)
                    pd = (side * A[j + 1][0], A[j + 1][1], za)
                    quad = [pa, pd, pc, pb] if side > 0 else [pa, pb, pc, pd]
                    if _area(quad) < 1e-9:
                        continue
                    uvs = [self.uv(p[2], jj) for p, jj in zip(quad, ([j, j + 1, j + 1, j] if side > 0 else [j, j, j + 1, j + 1]))]
                    if door:
                        self._door_leaf(part, mat, quad, uvs, side, j, A, Bp, za, zb)
                        continue
                    part.face_uv(quad, mat, uvs)
        # door jambs, heads and sills
        for zc, w, _ in self.doors:
            self._door_frame(part, zc, w, R)
        self._end_wall(part, R[0], -1)
        if self.cab:
            self._tip(part, R[-1])
        else:
            self._end_wall(part, R[-1], 1)

    def _door_leaf(self, part, mat, quad, uvs, side, j, A, Bp, za, zb):
        """a face of the side, set into the opening by DOOR_DEPTH along the section's normal"""
        nA = _normals2d(A)
        nB = _normals2d(Bp)
        out = []
        for p in quad:
            jj = j if abs(p[1] - A[j][1]) < 1e-6 or abs(p[1] - Bp[j][1]) < 1e-6 else j + 1
            nx, ny = (nA if abs(p[2] - za) < 1e-6 else nB)[jj]
            out.append((p[0] - side * nx * DOOR_DEPTH, p[1] - ny * DOOR_DEPTH, p[2]))
        part.face_uv(out, mat, uvs, smooth=False)

    def _door_frame(self, part, zc, w, R):
        z0, z1 = zc - w / 2, zc + w / 2
        zs = [z for z, _ in R]
        i0 = min(range(len(zs)), key=lambda i: abs(zs[i] - z0))
        i1 = min(range(len(zs)), key=lambda i: abs(zs[i] - z1))
        mat = P + 'jamb'
        for side in (1, -1):
            for i, facing in ((i0, 1), (i1, -1)):
                z, pts = R[i]
                nrm = _normals2d(pts)
                for j in range(J_SILL, J_TOP):
                    a = (side * pts[j][0], pts[j][1], z)
                    b = (side * pts[j + 1][0], pts[j + 1][1], z)
                    ai = (a[0] - side * nrm[j][0] * DOOR_DEPTH, a[1] - nrm[j][1] * DOOR_DEPTH, z)
                    bi = (b[0] - side * nrm[j + 1][0] * DOOR_DEPTH, b[1] - nrm[j + 1][1] * DOOR_DEPTH, z)
                    part.face_uv([a, b, bi, ai], mat, [(0, 0)] * 4, smooth=False, out=(0, 0, facing))
            for j, up in ((J_SILL, 1), (J_TOP, -1)):
                for i in range(i0, i1):
                    (za, A), (zb, Bp) = R[i], R[i + 1]
                    nA, nB = _normals2d(A), _normals2d(Bp)
                    a = (side * A[j][0], A[j][1], za)
                    b = (side * Bp[j][0], Bp[j][1], zb)
                    ai = (a[0] - side * nA[j][0] * DOOR_DEPTH, a[1] - nA[j][1] * DOOR_DEPTH, za)
                    bi = (b[0] - side * nB[j][0] * DOOR_DEPTH, b[1] - nB[j][1] * DOOR_DEPTH, zb)
                    part.face_uv([a, b, bi, ai], mat if up < 0 else P + 'sill', [(0, 0)] * 4, smooth=False, out=(0, up, 0))

    def _end_wall(self, part, ring, sign):
        """the flat gangway end: a ladder of quads between the pairs of points at the same height"""
        z, pts = ring
        j0 = S.SEGMENTS.index('skirt')
        for j in range(j0, S.HALF_N - 1):
            a, b = pts[j], pts[j + 1]
            q = [(a[0], a[1], z), (b[0], b[1], z), (-b[0], b[1], z), (-a[0], a[1], z)]
            if _area(q) < 1e-9:
                continue
            part.face_uv(q, P + 'end', [(0, 0)] * 4, smooth=False, out=(0, 0, sign))

    def _tip(self, part, ring):
        """close the nose: a fan from the first section to the tip point"""
        z, pts = ring
        tip = (0.0, S.nose_params(0.0)['yt'], S.NOSE_TIP)
        mat = P + 'body_' + self.kind
        for j in range(S.HALF_N - 1):
            # the tip's uv on each triangle: between its two ring points (one shared uv swept the whole atlas column)
            ut = self.uv(S.NOSE_TIP, j)
            uvt = (ut[0], (self.uv(z, j)[1] + self.uv(z, j + 1)[1]) / 2)
            for side in (1, -1):
                a = (side * pts[j][0], pts[j][1], z)
                b = (side * pts[j + 1][0], pts[j + 1][1], z)
                tri = [a, b, tip] if side > 0 else [b, a, tip]
                uvs = [self.uv(z, j), self.uv(z, j + 1), uvt] if side > 0 else [self.uv(z, j + 1), self.uv(z, j), uvt]
                if _area(tri) < 1e-10:
                    continue
                part.face_uv(tri, mat, uvs)


def _area(pts):
    p = [Vector(q) for q in pts]
    a = Vector((0.0, 0.0, 0.0))
    for i in range(1, len(p) - 1):
        a += (p[i] - p[0]).cross(p[i + 1] - p[0])
    return a.length / 2


# ---------------------------------------------------------------- gangway hood and dampers

def hood(part, z_end, sign, gap=0.25, inset=0.035, folds=3):
    """the car's half of the full-circumference hood: a rubber band round the section from the end to the gap's middle"""
    pts = section_points(99.0, False)
    nrm = _normals2d(pts)
    j0 = S.SEGMENTS.index('corner')
    ring = [(x - nx * (inset + END_R * 0.6), y - ny * (inset + END_R * 0.6)) for (x, y), (nx, ny) in zip(pts[j0:], nrm[j0:])]
    zs = [z_end + sign * gap * k / (2 * folds) for k in range(2 * folds + 1)]
    mat = P + 'hood'
    for k in range(len(zs) - 1):
        ea = 0.012 if k % 2 else 0.0
        eb = 0.012 if (k + 1) % 2 else 0.0
        for j in range(len(ring) - 1):
            for side in (1, -1):
                (xa, ya), (xb, yb) = ring[j], ring[j + 1]
                (nxa, nya), (nxb, nyb) = nrm[j0 + j], nrm[j0 + j + 1]
                p1 = (side * (xa + nxa * ea), ya + nya * ea, zs[k])
                p2 = (side * (xb + nxb * ea), yb + nyb * ea, zs[k])
                p3 = (side * (xb + nxb * eb), yb + nyb * eb, zs[k + 1])
                p4 = (side * (xa + nxa * eb), ya + nya * eb, zs[k + 1])
                c = Vector([(p1[i] + p3[i]) / 2 for i in range(3)])
                part.face_uv([p1, p2, p3, p4], mat, [(0, 0)] * 4, smooth=True, out=(c.x, c.y - 2.0, 0))
    # damper: a black cylinder on a bracket each side, low on the end (photos E525-1 / E526-101)
    for side in (1, -1):
        x = side * 1.38
        part.box(P + 'frame', min(x, x + side * 0.12), max(x, x + side * 0.12), 0.92, 1.10, *sorted((z_end, z_end - sign * 0.06)))
        part.cylinder(P + 'damper', (x + side * 0.06, 1.01, z_end + sign * 0.11), 0.055, 0.22, axis='z', segments=12)
        part.cylinder(P + 'chrome', (x + side * 0.06, 1.01, z_end + sign * 0.23), 0.022, 0.06, axis='z', segments=8)


# ---------------------------------------------------------------- painting


class Paint:
    """texel → 3D position lookup for one car's strip, and painting helpers (sRGB floats)"""

    def __init__(self, shell, w=ATLAS, h=ATLAS // 3):
        self.shell = shell
        self.w, self.h = w, h
        R = shell.grid
        zs = np.array([z for z, _ in R])
        G = np.array([pts for _, pts in R], np.float32)        # (ns, HALF_N, 2)
        cab = shell.cab
        m0, m1 = (u_metric(z_, cab) for z_ in U_RANGE[shell.kind])
        u = (np.arange(w) + 0.5) / w
        Z = z_of_metric(m0 + u * (m1 - m0), cab)
        v = (np.arange(h) + 0.5) / h
        vl = np.clip((v - 0.004) / 0.992, 0, 1)
        jf = np.interp(vl, VK, np.arange(S.HALF_N))
        i0 = np.clip(np.searchsorted(zs, Z) - 1, 0, len(zs) - 2)
        a = np.clip((Z - zs[i0]) / np.maximum(zs[i0 + 1] - zs[i0], 1e-6), 0, 1).astype(np.float32)
        j0 = np.clip(np.floor(jf).astype(int), 0, S.HALF_N - 2)
        b = (jf - j0).astype(np.float32)
        # bilinear in (station, ring index): arrays (h, w)
        A00 = G[i0][:, j0]          # (w, h, 2)
        A01 = G[i0][:, j0 + 1]
        A10 = G[i0 + 1][:, j0]
        A11 = G[i0 + 1][:, j0 + 1]
        aa = a[:, None, None]
        bb = b[None, :, None]
        P2 = (A00 * (1 - aa) * (1 - bb) + A10 * aa * (1 - bb) + A01 * (1 - aa) * bb + A11 * aa * bb)
        self.X = np.ascontiguousarray(P2[..., 0].T)     # (h, w)
        self.Y = np.ascontiguousarray(P2[..., 1].T)
        self.Z = np.broadcast_to(Z[None, :], (h, w)).copy()
        self.J = np.broadcast_to(jf[:, None], (h, w)).copy()
        self.D = (S.NOSE_TIP - self.Z) if shell.cab else np.full((h, w), 99.0, np.float32)
        dz = np.gradient(Z)                                   # metres per texel column (finer at the tip)
        self.px = np.maximum(dz, 1e-4)[None, :].astype(np.float32)
        self.rgb = np.zeros((h, w, 3), np.float32)
        self.rough = np.full((h, w), 0.22, np.float32)
        self.metal = np.zeros((h, w), np.float32)

    def cover(self, sd, aa=None):
        return np.clip(0.5 - sd / (aa if aa is not None else self.px), 0.0, 1.0)

    def paint(self, alpha, colour, rough=None, metal=None):
        a = alpha[..., None]
        self.rgb = self.rgb * (1 - a) + np.array(colour, np.float32) * a
        if rough is not None:
            self.rough = self.rough * (1 - alpha) + rough * alpha
        if metal is not None:
            self.metal = self.metal * (1 - alpha) + metal * alpha


def _smax(terms, r):
    """a soft maximum of signed distances (rounds the corners where they meet by about r)"""
    t = np.stack(terms) / r
    m = t.max(0)
    return r * (m + np.log(np.exp(t - m).sum(0)))


def _sd_box(px, py, cx, cy, w, h, r):
    return BD._sd_round_rect(px, py, cx, cy, w, h, r)


def paint_car(shell):
    """the strip of one car: livery, windows, doors, lower covers, the nose's glass and seams"""
    pt = Paint(shell)
    X, Y, Z, D, J = pt.X, pt.Y, pt.Z, pt.D, pt.J
    L = LAYOUT[shell.kind]
    side = J >= S.SEGMENTS.index('skirt') - 0.5             # outer surface (not the underside)
    # base: green above the line, white below, the pink stripe between
    gl = S.green_line_a(np.clip(D, 0, 30)) if shell.cab else np.full_like(Y, S.STRIPE[0])
    sw = S.stripe_width_a(np.clip(D, 0, 30)) if shell.cab else np.full_like(Y, S.STRIPE[1] - S.STRIPE[0])
    pt.rgb[:] = WHITE
    pt.rough[:] = 0.24
    pt.metal[:] = 0.0
    aa_y = 0.004
    pt.paint(np.clip(0.5 + (Y - gl) / aa_y, 0, 1), PINK, 0.24, 0.0)
    pt.paint(np.clip(0.5 + (Y - gl - sw) / aa_y, 0, 1), GREEN, 0.26, 0.12)
    # underside
    under = ~side & (D > 1.6) if shell.cab else ~side
    pt.paint(under.astype(np.float32), UNDER, 0.8, 0.0)
    # lower body covers: panel seams and grilles (between the bogie covers)
    _lower_covers(pt, shell)
    # saloon windows
    for zc in L['windows']:
        _window(pt, zc, WIN_Y, WIN_W)
    # doors
    for zc, w, kind in L['doors']:
        _door(pt, zc, w, kind)
    # side destination display frame
    zc, _ = L['display']
    sd = _sd_box(Z, Y, zc, 2.935, 0.64, 0.21, 0.025)
    pt.paint(pt.cover(sd) * side, (0.05, 0.05, 0.055), 0.3, 0.0)
    if shell.cab:
        _nose(pt)
    # the gangway end's edge: a fine seam where the rounding starts
    for ze in (-S.END + END_R, S.END - END_R) if not shell.cab else (-S.END + END_R,):
        sd = np.abs(Z - ze) - 0.003
        pt.paint(pt.cover(sd) * side * (Y > 0.31), SEAM, 0.4)
    return pt


def _window(pt, zc, ys, w, r=0.08):
    X, Y, Z = pt.X, pt.Y, pt.Z
    cy, h = (ys[0] + ys[1]) / 2, ys[1] - ys[0]
    sd = _sd_box(Z, Y, zc, cy, w + 0.05, h + 0.05, r + 0.025)
    pt.paint(pt.cover(sd) * (X > 1.0), GASKET, 0.5, 0.0)
    sd = _sd_box(Z, Y, zc, cy, w, h, r)
    pt.paint(pt.cover(sd) * (X > 1.0), SIDE_GLASS, 0.06, 0.0)


def _door(pt, zc, w, kind):
    X, Y, Z = pt.X, pt.Y, pt.Z
    y0, y1 = DOOR_H
    side = X > 1.0
    # the gap round the leaf
    sd = np.abs(_sd_box(Z, Y, zc, (y0 + y1) / 2, w, y1 - y0, 0.10)) - 0.004
    pt.paint(pt.cover(sd) * side, (0.06, 0.06, 0.065), 0.6, 0.0)
    # its window
    if kind == 'pass':
        sd = _sd_box(Z, Y, zc, 2.67, 0.40, 0.58, 0.16)
    else:
        sd = _sd_box(Z, Y, zc, 2.68, 0.40, 0.60, 0.06)
    pt.paint(pt.cover(sd - 0.02) * side, GASKET, 0.5, 0.0)
    pt.paint(pt.cover(sd) * side, SIDE_GLASS, 0.06, 0.0)
    if kind == 'crew':
        # recessed hand holds beside the crew door (two vertical slots)
        for s in (-1, 1):
            sd = _sd_box(Z, Y, zc + s * (w / 2 + 0.11), 1.95, 0.035, 0.85, 0.017)
            pt.paint(pt.cover(sd) * side, (0.03, 0.03, 0.035), 0.6, 0.0)
            sd = np.abs(_sd_box(Z, Y, zc + s * (w / 2 + 0.11), 2.05, 0.10, 1.12, 0.03)) - 0.002
            pt.paint(pt.cover(sd) * side, SEAM, 0.5)
    # step plate under the door (the sill's edge)
    sd = _sd_box(Z, Y, zc, y0 - 0.025, w - 0.06, 0.03, 0.01)
    pt.paint(pt.cover(sd) * side, (0.62, 0.63, 0.64), 0.3, 0.8)
    # drip strip over the door: painted shadow line (the strip itself is geometry)
    sd = _sd_box(Z, Y, zc, y1 + 0.065, w + 0.10, 0.012, 0.005)
    pt.paint(pt.cover(sd) * side, (0.12, 0.30, 0.27), 0.4)


def _lower_covers(pt, shell):
    """the hinged cover panels of the lower body and the bogie covers (photos E525-1, E526-101, H523-1)"""
    X, Y, Z = pt.X, pt.Y, pt.Z
    side = (X > 1.0) & (Y > 0.29) & (Y < 1.30)
    if shell.cab:
        body_front = S.NOSE_TIP - 11.0            # the nose's own skin runs back to here
    else:
        body_front = S.END - 0.25
    zb = (-S.BOGIE_Z, S.BOGIE_Z)
    # bogie covers: z ± 1.75 round each bogie, a seam all round
    for zc in zb:
        if shell.cab and zc > 0:
            continue
        sd = np.abs(_sd_box(Z, Y, zc, 0.66, 3.5, 0.72, 0.06)) - 0.003
        pt.paint(pt.cover(sd) * side, SEAM, 0.4)
    # long seam at the top of the cover panels, from the rear bogie cover to the front one
    z0 = -S.BOGIE_Z + 1.75
    z1 = (S.BOGIE_Z - 1.75) if not shell.cab else body_front
    sd = np.maximum(np.abs(Y - 1.02) - 0.003, np.maximum(z0 - Z, Z - z1))
    pt.paint(pt.cover(sd) * side, SEAM, 0.4)
    # panels: alternate plain lids and grilles (deterministic pattern)
    k = 0
    z = z0 + 0.05
    while z < z1 - 0.9:
        wpan = (1.55, 1.25, 1.40, 1.10)[k % 4]
        za, zb2 = z, min(z + wpan, z1 - 0.05)
        sd = np.abs(_sd_box(Z, Y, (za + zb2) / 2, 0.66, zb2 - za - 0.02, 0.68, 0.03)) - 0.0025
        pt.paint(pt.cover(sd) * side, SEAM, 0.4)
        if k % 3 == 1:
            # a louvre grille in the panel
            gz, gw = (za + zb2) / 2, (zb2 - za) * 0.62
            sd = _sd_box(Z, Y, gz, 0.72, gw, 0.30, 0.02)
            inside = pt.cover(sd) * side
            pt.paint(inside, GRILLE, 0.6)
            slats = (np.sin((Y - 0.57) / 0.022 * math.pi) > 0.25).astype(np.float32)
            pt.paint(inside * slats, (0.22, 0.23, 0.24), 0.7)
        elif k % 3 == 2:
            # a recessed handle
            sd = _sd_box(Z, Y, zb2 - 0.15, 0.86, 0.10, 0.035, 0.012)
            pt.paint(pt.cover(sd) * side, (0.25, 0.26, 0.27), 0.5)
        z = zb2 + 0.02
        k += 1


def _nose(pt):
    """the cab end: the canopy's glass and lamp strip, the coupler cover's seams, the nose's panel joints"""
    X, Y, Z, D = pt.X, pt.Y, pt.Z, pt.D
    top = pt.J >= S.SEGMENTS.index('uside')
    # ---- canopy: a light grey frame over the whole visor (the bubble's front and flanks), the windscreen and the
    # flanks' side windows in it, the lamps' band along the windscreen's top above a bar. Outlines drawn head-on
    # (in x, y) where the photos give them, so the windscreen is the photo's rounded trapezoid.
    B = S.bubble_a(X, D)
    ax = np.abs(X)
    y_arc = ARC_Y - ARC_K * X * X
    gw = WS_W[0] + (WS_W[1] - WS_W[0]) * np.clip((Y - 2.25) / 0.70, 0, 1)
    vis = top & (D > S.BUB_D[0] - 0.3) & (D < S.BUB_D[1])
    sd_frame = _smax([(0.012 - B) / 1.5, Y - y_arc - 0.055, D - VISOR_REAR - 0.15], 0.03)
    pt.paint(pt.cover(sd_frame, 0.006) * vis, FRAME, 0.30, 0.15)
    sd_ws = _smax([(0.045 - B) / 1.5, ax - gw, Y - y_arc, D - 6.6], 0.035)
    sd_sw = _smax([(0.022 - B) / 1.5, gw + PILLAR - ax, Y - y_arc + 0.02, D - VISOR_REAR], 0.04)
    for sd in (sd_ws, sd_sw):
        pt.paint(pt.cover(sd - 0.007, 0.004) * vis, (0.02, 0.022, 0.025), 0.4, 0.0)     # the gasket
        pt.paint(pt.cover(sd, 0.004) * vis, GLASS_REFL, 0.05, GLASS_METAL)
    band = pt.cover(sd_ws, 0.004) * vis * np.clip(0.5 + (Y - LAMP_BAR - 0.012) / 0.004, 0, 1)
    pt.paint(band, LAMP_BAND, 0.06, GLASS_METAL)
    bar = pt.cover(np.maximum(sd_ws, np.abs(Y - LAMP_BAR) - 0.011), 0.004) * vis
    pt.paint(bar, FRAME, 0.3, 0.15)
    # the wipers' pivots in the moat under the windscreen's corners
    for s in (-1, 1):
        sd = np.hypot(X - s * WIPER_X[0], (D - wiper_foot_d(WIPER_X[0])) * 0.8) - 0.035
        pt.paint(pt.cover(sd, 0.004) * top, (0.05, 0.05, 0.055), 0.5)
    # ---- the coupler cover: its seam all round (museum mock-up, head-on photos)
    # (head-on: a closed oval 2.15 m wide round the nose's front metre, green above the line, white below)
    # the cover: everything ahead of d = 1.1 above a curve rising from 0.55 m in the middle to the sides
    sd = _smax([D - 1.0, 0.55 + 0.22 * np.abs(X) ** 2 - Y], 0.10)
    sd = np.abs(sd) - 0.015
    pt.paint(pt.cover(sd, 0.006) * (Y > 0.36), (0.03, 0.035, 0.04), 0.5)
    # ---- panel joints on the nose: the cab's side hatch outline, the skirt's joint
    for d0, d1, y0, y1 in ((10.2, 11.4, 0.55, 1.15), (3.6, 4.9, 0.40, 0.95)):
        sd = np.abs(_sd_box(D, Y, (d0 + d1) / 2, (y0 + y1) / 2, d1 - d0, y1 - y0, 0.04)) - 0.003
        pt.paint(pt.cover(sd) * (X > 0.6), SEAM, 0.4)
    # the white cheek's rear edge over the front bogie and the joint under the green line
    sd = np.maximum(np.abs(D - 7.0) - 0.003, Y - 1.05)
    pt.paint(pt.cover(sd) * (X > 1.0) * (Y > 0.31), SEAM, 0.4)


# ---------------------------------------------------------------- materials


SIGNS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'textures', 'e5')


def add_materials(m, tex_dir, shells):
    """plain materials and the body atlas (painted from the built shells)"""
    os.makedirs(tex_dir, exist_ok=True)
    m.add(P + 'end', '#2f8f7d', roughness=0.4)
    m.add(P + 'hood', '#2a2b2d', roughness=0.85)
    m.add(P + 'jamb', JAMB[VARIANT], roughness=0.35)
    m.add(P + 'sill', '#9ea2a6', metallic=0.8, roughness=0.35)
    m.add(P + 'frame', '#3a3b3d', metallic=0.3, roughness=0.5)
    m.add(P + 'damper', '#151516', roughness=0.4)
    m.add(P + 'chrome', '#d0d3d6', metallic=1.0, roughness=0.2)
    m.add(P + 'lamp', '#eef0f0', metallic=0.5, roughness=0.06)
    m.add(P + 'dark', '#141516', roughness=0.5)
    m.add(P + 'drip', '#2c9381', roughness=0.3)
    for name, fn, rough, metal in (('signs', 'e5_signs.png', 0.3, 0.0), ('logo', 'e5_logo.png', 0.26, 0.12)):
        path = os.path.join(tex_dir_variant(), fn)
        if not os.path.exists(path):
            m.add(P + name, '#202122', roughness=0.3)
            continue
        img = bpy.data.images.load(path)
        sm = bpy.data.materials.new(P + name)
        sm.use_nodes = True
        nt = sm.node_tree
        bsdf = nt.nodes.get('Principled BSDF')
        t = nt.nodes.new('ShaderNodeTexImage')
        t.image = img
        nt.links.new(t.outputs['Color'], bsdf.inputs['Base Color'])
        bsdf.inputs['Roughness'].default_value = rough
        bsdf.inputs['Metallic'].default_value = metal       # (the logo's ground matches the green paint's)
        m.mats[P + name] = sm
    rgb = np.zeros((ATLAS, ATLAS, 3), np.float32)
    mr = np.zeros((ATLAS, ATLAS, 4), np.float32)
    mr[..., 3] = 1
    mr[..., 0] = 1
    for kind in KINDS:
        pt = paint_car(shells[kind])
        s = STRIP[kind]
        r0 = s * (ATLAS // 3)
        rgb[r0:r0 + pt.h] = pt.rgb
        mr[r0:r0 + pt.h, :, 1] = pt.rough
        mr[r0:r0 + pt.h, :, 2] = pt.metal
    img = _save_image(P + 'atlas', rgb, os.path.join(tex_dir, 'e5_body.png'))
    img2 = _save_image(P + 'atlas_mr', mr, os.path.join(tex_dir, 'e5_body_mr.png'), data=True)
    mat = BD.textured_material(P + 'body', img, img2)
    for kind in KINDS:
        m.mats[P + 'body_' + kind] = mat
    m.mats[P + 'body'] = mat
    return mat


def _save_image(name, arr, path, data=False):
    h, w = arr.shape[:2]
    rgba = np.ones((h, w, 4), np.float32)
    rgba[..., :arr.shape[2] if arr.shape[2] <= 4 else 4] = np.clip(arr[..., :4], 0, 1)
    if arr.shape[2] == 3:
        rgba[..., 3] = 1
    img = bpy.data.images.new(name, w, h, alpha=False)
    if data:
        img.colorspace_settings.name = 'Non-Color'
    img.pixels.foreach_set(rgba.ravel())
    img.filepath_raw = path
    img.file_format = 'PNG'
    img.save()
    return img


# ---------------------------------------------------------------- fittings on the shell: lamps, wipers, signs
# head lamps: four round units in the band along the windscreen's top (head-on U19: 0.16 m apart, lenses ≈ 0.11 m,
# the row ≈ 1/3 of the visor's width), each a clear lens in a chrome bezel facing forward (tilted up a little); the
# glass slopes back there, so each unit is a short pod standing out of it. The tail lamps light in the same units.
LAMP_X = (0.08, 0.24)
LAMP_Y = 2.84                       # the lenses' centre height
LENS_R = 0.052
BEZEL_R = 0.064
LAMP_TILT = math.radians(35.0)      # the lamp axis's rise from +z
WIPER_X = (0.50, 0.535)             # the wiper arms parked upright at the windscreen's lower corners (foot, tip)
LED = (0.60, 0.15, 2.935)           # side display panel: width, height, centre height (inside its painted frame)
NUMBER_H = 0.075                    # body number's letter height


def top_y(x, d, cab=True):
    """the shell's top surface height at (x, d)"""
    pts = section_points(d, cab)
    j0 = S.SEGMENTS.index('uside')
    top = pts[j0:]
    xs = np.array([p[0] for p in top])[::-1]
    ys = np.array([p[1] for p in top])[::-1]
    return float(np.interp(abs(x), xs, ys))


def side_x(kind, z, y):
    """the shell's side (x ≥ 0) at height y, at z"""
    cab = LAYOUT[kind]['cab']
    d = S.NOSE_TIP - z if cab else 99.0
    pts = section_points(min(d, 99.0), cab)
    j0, j1 = S.SEGMENTS.index('lside'), S.SEGMENTS.index('roof')
    seg = pts[j0:j1]
    ys = np.array([p[1] for p in seg])
    xs = np.array([p[0] for p in seg])
    o = np.argsort(ys)
    return float(np.interp(y, ys[o], xs[o]))


def face_d(x, y, d0=None, d1=6.4):
    """distance from the tip where the canopy's front face reaches height y at x (bisection: the face rises with d)"""
    lo = S.BUB_D[0] - 0.3 if d0 is None else d0
    hi = d1
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        if top_y(x, mid) < y:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def wiper_foot_d(x):
    """where a wiper's pivot sits: just ahead of the bubble's foot, in the moat"""
    u = min(abs(x) / 0.87, 1.0)
    return S.BUB_D[0] + S.BUB_SWEEP * u * u - 0.03


def lamp_centres():
    """[(x, y, z)] of the four lenses' centres in the cab car's frame (z forward), right to left"""
    out = []
    st, ct = math.sin(LAMP_TILT), math.cos(LAMP_TILT)
    for x in (-LAMP_X[1], -LAMP_X[0], LAMP_X[0], LAMP_X[1]):
        # the bezel's lowest point stands just off the glass; everything above it is further forward of the face
        d_low = face_d(x, LAMP_Y - BEZEL_R * ct)
        z_low = S.NOSE_TIP - d_low + 0.006
        out.append((x, LAMP_Y, z_low - BEZEL_R * st))
    return out


def _lamp_pod(part, c, seg=20, depth=0.32):
    """a forward-facing round lamp: lens, chrome bezel, and the pod's wall back into the canopy"""
    c = np.array(c)
    a = np.array((0.0, math.sin(LAMP_TILT), math.cos(LAMP_TILT)))
    e1 = np.array((1.0, 0.0, 0.0))
    e2 = np.cross(a, e1)
    ring = [e1 * math.cos(t) + e2 * math.sin(t) for t in np.linspace(0, 2 * math.pi, seg, endpoint=False)]
    lens_c = c - a * 0.008
    part.face_uv([tuple(lens_c + r * LENS_R) for r in ring], P + 'lamp', [(0.5, 0.5)] * seg, smooth=False, out=tuple(a))
    for k in range(seg):
        r0, r1 = ring[k], ring[(k + 1) % seg]
        q = [c + r0 * LENS_R, c + r1 * LENS_R, c + r1 * BEZEL_R, c + r0 * BEZEL_R]
        part.face_uv([tuple(v) for v in q], P + 'chrome', [(0.5, 0.5)] * 4, smooth=False, out=tuple(a))
        q = [lens_c + r0 * LENS_R, lens_c + r1 * LENS_R, c + r1 * LENS_R, c + r0 * LENS_R]
        part.face_uv([tuple(v) for v in q], P + 'chrome', [(0.5, 0.5)] * 4, smooth=True, out=tuple(-(r0 + r1)))
        b = c - a * depth
        q = [c + r0 * BEZEL_R, c + r1 * BEZEL_R, b + r1 * BEZEL_R, b + r0 * BEZEL_R]
        part.face_uv([tuple(v) for v in q], P + 'sill', [(0.5, 0.5)] * 4, smooth=True, out=tuple(r0 + r1))


def _top_normal(x, d):
    e = 0.02
    fx = (top_y(x + e, d) - top_y(x - e, d)) / (2 * e)
    fd = (top_y(x, d + e) - top_y(x, d - e)) / (2 * e)
    n = np.array((-fx, 1.0, fd))            # z = TIP − d: ∂y/∂z = −∂y/∂d
    return n / np.linalg.norm(n)


def _strip_on_top(part, mat, pts_xd, w, lift):
    """a thin strip lying on the top surface along [(x, d)]"""
    rows = []
    for k, (x, d) in enumerate(pts_xd):
        x1, d1 = pts_xd[min(k + 1, len(pts_xd) - 1)]
        x0, d0 = pts_xd[max(k - 1, 0)]
        t = np.array((x1 - x0, d0 - d1))
        t /= np.linalg.norm(t)
        side = np.array((-t[1], t[0])) * w / 2
        n = _top_normal(x, d)
        row = []
        for s in (-1, 1):
            xx, zz = x + s * side[0], S.NOSE_TIP - d + s * side[1]
            row.append(np.array((xx, top_y(xx, S.NOSE_TIP - zz), zz)) + n * lift)
        rows.append(row)
    for a, b in zip(rows, rows[1:]):
        q = [tuple(a[0]), tuple(a[1]), tuple(b[1]), tuple(b[0])]
        part.face_uv(q, mat, [(0.5, 0.5)] * 4, smooth=False, out=tuple(_top_normal(*pts_xd[0])))


def _decal_side(part, mat, kind, zc, yc, w, h, uv_box, side, nz=4, ny=2, lift=0.004, smooth=False):
    """a sign on the car's side at (zc, yc) following its section, reading from outside; uv_box = (u0, v0, u1, v1)"""
    u0, v0, u1, v1 = uv_box
    cols = []
    for i in range(nz + 1):
        f = i / nz
        z = zc + w / 2 - w * f if side > 0 else zc - w / 2 + w * f     # text runs towards −z on the left side
        col = []
        for j in range(ny + 1):
            g = j / ny
            y = yc - h / 2 + h * g
            x = side * (side_x(kind, z, y) + lift)
            col.append(((x, y, z), (u0 + (u1 - u0) * f, v0 + (v1 - v0) * g)))
        cols.append(col)
    for a, b in zip(cols, cols[1:]):
        for j in range(ny):
            q = [a[j], b[j], b[j + 1], a[j + 1]]
            part.face_uv([p for p, _ in q], mat, [uv for _, uv in q], smooth=smooth, out=(side, 0.0, 0.0))


def _atlas_uv(px0, py0, px1, py1, W=1024, H=512):
    """the sign atlas's pixel box → uv box (v up from the image's bottom)"""
    return (px0 / W, 1 - py1 / H, px1 / W, 1 - py0 / H)


NUMBER_ROW = {'e523': 0, 'e525': 1, 'e514': 2}
NUMBER_PX = {'e5': {'e523': 244, 'e525': 296, 'e514': 244},       # the JR mark and the number (e5_textures prints
             'h5': {'e523': 250, 'e525': 303, 'e514': 250}}       # their widths in pixels)


def cab_fittings(part, kind):
    """lamps and wipers on a cab's canopy; side displays and body numbers on every car"""
    L = LAYOUT[kind]
    if L['cab']:
        for c in lamp_centres():
            _lamp_pod(part, c)
        # wipers: two arms parked upright from pivots in the moat, up the windscreen's lower corners
        y0 = top_y(WIPER_X[0], wiper_foot_d(WIPER_X[0]))
        for s in (-1, 1):
            arm = [(s * WIPER_X[0], wiper_foot_d(WIPER_X[0]))]
            for f in (0.35, 0.7, 1.0):
                x = WIPER_X[0] + (WIPER_X[1] - WIPER_X[0]) * f
                arm.append((s * x, face_d(x, y0 + 0.40 * f)))
            _strip_on_top(part, P + 'dark', arm, 0.028, 0.012)
    # side destination displays (both sides) and the body number under the window band
    zc, _ = L['display']
    for side in (1, -1):
        _decal_side(part, P + 'signs', kind, zc, LED[2], LED[0], LED[1], _atlas_uv(0, 0, 768, 192), side)
    door_z = [z for z, w, k in L['doors'] if k == 'pass'][0]
    door_w = [w for z, w, k in L['doors'] if k == 'pass'][0]
    px = NUMBER_PX[VARIANT][kind]                    # the text's extent in its atlas row (8 px margin each side)
    th = NUMBER_H * 64 / 36                 # the row's 64 px hold 36 px of capital height
    w = px / 64 * th
    row = NUMBER_ROW[kind]
    uv = _atlas_uv(0, 256 + 64 * row, px, 256 + 64 * row + 64)
    for side in (1, -1):
        z = door_z - door_w / 2 - 0.15 - w / 2
        _decal_side(part, P + 'signs', kind, z, 1.62, w, th, uv, side)
    # the service logo
    lg = LOGOS[VARIANT].get(kind)
    if lg:
        for side in (1, -1):
            _decal_side(part, P + 'logo', kind, lg[0], lg[1], lg[2], lg[3], (0.0, 0.0, 1.0, 1.0), side, nz=10,
                        ny=14, lift=0.0025, smooth=True)
