"""
Roof equipment of the Keikyu New 1000 series, 1st batch (2002): the Mitsubishi CU-71H air conditioner, the Toyo Denki
PT7117-A single-arm pantograph, the gear round a pantograph (lightning arrester, high-voltage conduits and cables,
junction box), the cab roof's antennas and the drip rails along the roof.

Frame: the game's car frame of train_kit (metres; +x = the car's left, +y up from the rail top, +z forward).
Every function adds faces to a K.Part and returns the number of triangles it added.

Figures and where they come from
- ja.wikipedia 京急1000形電車 (2代) (read 2026-11-03):
  - height with the air conditioner 4,026.5 mm; with a (lowered) pantograph 4,050 mm.
  - pantograph Toyo Denki PT7117-A, single arm; 8-car 1st batch: two on each of Tpu and Tps, drawn "＜ ＞" in the
    formation table = one at each end of the car with the knee pointing at the car end.
  - air conditioner Mitsubishi CU-71H, roof-mounted centralised, 41.86 kW; 整流板 (flow-guide plates) added because the
    condenser's exhaust could not leave through the boundary layer at speed (the CU-71G on the 2100 overheated).
  - 1st batch: lightning arrester on the pantograph frame "exposed" (no insulating cover; covered from the 3rd batch).
- Commons photos (measured / looked at, never copied into the model):
  - Keikyu-N1000-ALcar.jpg (side view of a Tp car, the best one): knee towards the car end; main shaft ≈ 1.6 m from
    the body end (z ≈ ±7.1), knee ≈ 1.0 m from it (z ≈ ±7.75), pan head centre ≈ 2.2 m from it (z ≈ ±6.55); lower
    arm rise ≈ 0.57 of the head's rise; the AC is a long low body with a raised hood over about half its length and a
    lower deck with grilles and a row of small plates on the other half; the bus conduit runs along one side of the
    roof from the pantograph past the AC; a white horizontal insulator (arrester) beside the pantograph base.
  - PT-7117.JPG (Hahifuheho, CC0; the pantograph on the workshop floor): base frame of square tubes on four post
    insulators on outriggers, main shaft across the middle, tapered lower arm, thin push rod beside it to a lever
    below the knee, round upper arm, spring box + lowering cylinder on the knee side of the shaft, rubber stops and
    U-shaped hooks at the other end, a coil spring on the frame; head: two strips, curved horns with yellow tips.
  - Keikyu 1000 series (II) pantograph head PT7117 1082 (2026): two collector strips (one-piece carriers) on bellows
    springs, a horn at each end bent down and out, a thin balance rod under the upper arm to the head.
  - Keikyu-Type1000-009.jpg, -1001F-Lot1.jpg, Keikyu-railway-1001F/1009F, Keikyun1000-kzb-kzh.jpg: AC ends (a lower
    nose block, the hood sloping down to it, the plate row along the deck's edge), cab roof: two dark grey radio
    antennas on bolted flanges with white brackets beside them, just behind the red cab top, right of the centre line
    seen from ahead (−x).
- Estimates (no figure found): AC 4.80 × 1.90 m (brief: 4.5–5 × 1.9–2.0), deck top 3.85 m, hood top 4.0265 m (the
  height figure), hood over 2.4 m of it; pantograph arm lengths 0.90 (lower) and 1.40 m (upper) from the ALcar photo
  proportions; base frame 1.35 × 0.60 m on insulators 1.0 m apart across, 1.1 m along; head: strips 1.10 m long,
  0.22 m apart, horns to |x| = 0.95 m and 0.32 m below the strip; post insulators 0.15 m.
- The roof surface (`roof_profile_y`): the body's section as measured by the main author on the head-on photo (eave
  3.12 at ±1.415, shoulder r 0.45 centred at (±0.965, 3.12), roof arc r 9.79 through 3.62; red below 3.30). The
  assembly passes the built half profile to `set_roof_profile`, which then replaces the analytic one.

Use on the 3-car game set (car1 = Tpu): air_conditioner(part, 0.0); pantograph(part, +7.1, knee=+1);
pantograph(part, -7.1, knee=-1); pantograph_gear(part, +7.1); pantograph_gear(part, -7.1); roof_details(part, -8.75, 8.75).
Cab cars: air_conditioner(part, 0.0); cab_roof_details(part, 8.4) (z of the face top on the centre line);
roof_details(part, -8.75, ≈ 8.0) (the drip rail ends where the cab top's rounding begins).

Run directly for the test renders:
  blender -t 4 --background --factory-startup --python parts/roof_n1000.py -- --scene ac|panto|car|cab --out <dir>
"""
import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

if __name__ == '__main__':
    sys.dont_write_bytecode = True
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import train_kit as K  # noqa: E402

# ---------------------------------------------------------------- materials
AC = 'rf_ac'          # AC body, conduits (weathered light grey, painted metal)
METAL = 'rf_metal'    # pantograph, frames, brackets (dark galvanised steel)
DARK = 'rf_dark'      # grille openings, fan wells, carbon strips, rubber, cables
INSUL = 'rf_insul'    # porcelain, white brackets
TIP = 'rf_tip'        # the horns' yellow tips

MATERIALS = [
    (AC, '#9a9b97', 0.3, 0.5),
    (METAL, '#4d5156', 0.6, 0.45),
    (DARK, '#1e2023', 0.0, 0.75),
    (INSUL, '#e6e3da', 0.0, 0.3),
    (TIP, '#dba51e', 0.0, 0.5),
]


def add_materials(m):
    for name, colour, metallic, roughness in MATERIALS:
        if name not in m.mats:
            m.add(name, colour, metallic=metallic, roughness=roughness)
    return 0


# ---------------------------------------------------------------- the roof surface
# the body's section (main author, measured on the head-on photo): vertical side to the eave, shoulder arc r 0.45
# centred at (0.965, 3.12), tangent to the roof arc r 9.79 through 3.62 on the centre line
_HW, _EAVE, _SHOULDER_C, _SHOULDER_R, _ROOF, _ROOF_R = 1.415, 3.12, 0.965, 0.45, 3.62, 9.79
_PROFILE = None     # [(x, y)] from the roof centre outwards, when set from a section


def set_roof_profile(half):
    """use a body section's half profile [(x, y), ...] (x ≥ 0, any order) for `roof_profile_y`"""
    global _PROFILE
    pts = sorted({(round(abs(p[0]), 6), p[1]) for p in half if p[1] >= 3.0})
    _PROFILE = pts


def roof_profile_y(x):
    """the roof surface's height at x (the body's section; `set_roof_profile` replaces it with the built one)"""
    x = abs(x)
    if _PROFILE:
        pts = _PROFILE
        if x <= pts[0][0]:
            return pts[0][1]
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            if x0 <= x <= x1:
                return y0 + (y1 - y0) * (x - x0) / (x1 - x0) if x1 > x0 else max(y0, y1)
        return pts[-1][1]
    cy = _ROOF - _ROOF_R
    d = math.hypot(_SHOULDER_C, _EAVE - cy)
    xt = _SHOULDER_C * _ROOF_R / d               # where the shoulder meets the roof arc
    if x <= xt:
        return cy + math.sqrt(_ROOF_R ** 2 - x * x)
    if x <= _HW:
        return _EAVE + math.sqrt(max(0.0, _SHOULDER_R ** 2 - (x - _SHOULDER_C) ** 2))
    return _EAVE


# ---------------------------------------------------------------- mesh building (game frame, per-face smoothing)

class _Mesh:
    """adds faces straight into a Part's bmesh; counts triangles"""

    def __init__(self, part):
        self.part = part
        self.bm = part.bm
        self.tris = 0

    def v(self, p):
        return self.bm.verts.new(K.B(*p))

    def face(self, vs, mat, smooth=False, ref=None):
        """vs: BMVerts in order; ref: a point (game frame) inside the solid, to turn the face outwards"""
        if len(set(vs)) < 3:
            return None
        if ref is not None:
            n = _newell([v.co for v in vs])
            c = sum((v.co for v in vs), Vector()) / len(vs)
            if n.dot(c - K.B(*ref)) < 0:
                vs = list(reversed(vs))
        try:
            f = self.bm.faces.new(vs)
        except ValueError:
            return None
        f.material_index = self.part.slot(mat)
        f.smooth = smooth
        self.tris += len(vs) - 2
        return f


def _newell(cos):
    n = Vector((0.0, 0.0, 0.0))
    for i, a in enumerate(cos):
        b = cos[(i + 1) % len(cos)]
        n.x += (a.y - b.y) * (a.z + b.z)
        n.y += (a.z - b.z) * (a.x + b.x)
        n.z += (a.x - b.x) * (a.y + b.y)
    return n


def _V(p):
    return Vector(p)


def _perp(t):
    t = t.normalized()
    up = Vector((0, 1, 0)) if abs(t.y) < 0.9 else Vector((1, 0, 0))
    n = up.cross(t).normalized()
    return n


def box(mm, mat, x0, x1, y0, y1, z0, z1, skip=()):
    """an axis-aligned box; skip: faces to leave out ('-y', '+y', '-x', '+x', '-z', '+z')"""
    c = ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2)
    P = {}
    for i, x in enumerate((x0, x1)):
        for j, y in enumerate((y0, y1)):
            for k, z in enumerate((z0, z1)):
                P[i, j, k] = mm.v((x, y, z))
    quads = {
        '-x': [P[0, 0, 0], P[0, 1, 0], P[0, 1, 1], P[0, 0, 1]],
        '+x': [P[1, 0, 0], P[1, 1, 0], P[1, 1, 1], P[1, 0, 1]],
        '-y': [P[0, 0, 0], P[1, 0, 0], P[1, 0, 1], P[0, 0, 1]],
        '+y': [P[0, 1, 0], P[1, 1, 0], P[1, 1, 1], P[0, 1, 1]],
        '-z': [P[0, 0, 0], P[1, 0, 0], P[1, 1, 0], P[0, 1, 0]],
        '+z': [P[0, 0, 1], P[1, 0, 1], P[1, 1, 1], P[0, 1, 1]],
    }
    for k, q in quads.items():
        if k not in skip:
            mm.face(q, mat, ref=c)


def obox(mm, mat, centre, ax, ay, az, hx, hy, hz, skip=()):
    """an oriented box: centre, unit axes (game frame), half sizes"""
    c, ax, ay, az = _V(centre), _V(ax), _V(ay), _V(az)
    P = {}
    for i, sx in enumerate((-1, 1)):
        for j, sy in enumerate((-1, 1)):
            for k, sz in enumerate((-1, 1)):
                P[i, j, k] = mm.v(tuple(c + ax * sx * hx + ay * sy * hy + az * sz * hz))
    quads = {
        '-x': [P[0, 0, 0], P[0, 1, 0], P[0, 1, 1], P[0, 0, 1]],
        '+x': [P[1, 0, 0], P[1, 1, 0], P[1, 1, 1], P[1, 0, 1]],
        '-y': [P[0, 0, 0], P[1, 0, 0], P[1, 0, 1], P[0, 0, 1]],
        '+y': [P[0, 1, 0], P[1, 1, 0], P[1, 1, 1], P[0, 1, 1]],
        '-z': [P[0, 0, 0], P[1, 0, 0], P[1, 1, 0], P[0, 1, 0]],
        '+z': [P[0, 0, 1], P[1, 0, 1], P[1, 1, 1], P[0, 1, 1]],
    }
    for k, q in quads.items():
        if k not in skip:
            mm.face(q, mat, ref=tuple(c))


def beam(mm, mat, a, b, w, h, up=(0, 1, 0), caps=True):
    """a rectangular beam from a to b: w across (perpendicular to `up`), h along `up`"""
    a, b = _V(a), _V(b)
    d = b - a
    t = d.normalized()
    u = _V(up)
    side = u.cross(t)
    if side.length < 1e-6:
        side = _perp(t)
    side.normalize()
    upv = t.cross(side).normalized()
    obox(mm, mat, tuple((a + b) / 2), side, upv, t, w / 2, h / 2, d.length / 2,
         skip=() if caps else ('-z', '+z'))


def tube(mm, mat, pts, radius, seg=8, caps=(True, True), smooth=True, closed=False, scale=None, phase=0.0, n0=None):
    """
    a tube swept along pts (game frame); radius: number or one per point; scale: (sx, sy) to flatten the section
    (sx along the frame's normal, sy along its binormal); n0: the first section's normal direction.
    """
    P = [_V(p) for p in pts]
    n = len(P)
    R = radius if isinstance(radius, (list, tuple)) else [radius] * n
    sx, sy = scale if scale else (1.0, 1.0)
    T = []
    for i in range(n):
        if closed:
            d = P[(i + 1) % n] - P[i - 1]
        elif i == 0:
            d = P[1] - P[0]
        elif i == n - 1:
            d = P[-1] - P[-2]
        else:
            d = (P[i + 1] - P[i]).normalized() + (P[i] - P[i - 1]).normalized()
        T.append(d.normalized())
    N = _V(n0) if n0 is not None else _perp(T[0])
    N = (N - T[0] * N.dot(T[0])).normalized()
    rings = []
    for i in range(n):
        if i > 0:
            q = T[i - 1].rotation_difference(T[i])
            N = q @ N
            N = (N - T[i] * N.dot(T[i])).normalized()
        Bn = T[i].cross(N)
        ring = []
        for k in range(seg):
            a = phase + 2 * math.pi * k / seg
            ring.append(mm.v(tuple(P[i] + N * (R[i] * sx * math.cos(a)) + Bn * (R[i] * sy * math.sin(a)))))
        rings.append(ring)
    last = n if closed else n - 1
    for i in range(last):
        r0, r1 = rings[i], rings[(i + 1) % n]
        for k in range(seg):
            mm.face([r0[k], r0[(k + 1) % seg], r1[(k + 1) % seg], r1[k]], mat, smooth=smooth)
    if not closed:
        if caps[0]:
            mm.face(list(rings[0]), mat, ref=tuple(P[0] + T[0] * 0.001))
        if caps[1]:
            mm.face(list(rings[-1]), mat, ref=tuple(P[-1] - T[-1] * 0.001))
    return rings


def cyl(mm, mat, a, b, r, seg=12, caps=(True, True), r2=None, smooth=True):
    """a cylinder (or a cone frustum with r2) from a to b"""
    return tube(mm, mat, [a, b], [r, r if r2 is None else r2], seg=seg, caps=caps, smooth=smooth)


def lathe(mm, mat, origin, axis, profile, seg=12, cap0=True, cap1=True, smooth=True, mats=None):
    """
    a solid of revolution: profile [(r, t)] from the bottom (t along `axis` from `origin`) to the top, traced over the
    outside; mats: optional material per profile band (len(profile) − 1)
    """
    o, A = _V(origin), _V(axis).normalized()
    U = _perp(A)
    W = A.cross(U)          # U × W = A: the band winding below then faces outwards
    rings = []
    for r, t in profile:
        c = o + A * t
        if r <= 1e-6:
            rings.append([mm.v(tuple(c))] * seg)
            continue
        rings.append([mm.v(tuple(c + U * (r * math.cos(2 * math.pi * k / seg)) + W * (r * math.sin(2 * math.pi * k / seg))))
                      for k in range(seg)])
    for i in range(len(rings) - 1):
        m = mats[i] if mats else mat
        a, b = rings[i], rings[i + 1]
        flat = abs(profile[i][1] - profile[i + 1][1]) < 1e-9
        for k in range(seg):
            q = [a[k], a[(k + 1) % seg], b[(k + 1) % seg], b[k]]
            if q[0] is q[1]:
                q = [q[0], q[2], q[3]]
            elif q[2] is q[3]:
                q = [q[0], q[1], q[2]]
            mm.face(q, m, smooth=smooth and not flat)
    if cap0 and profile[0][0] > 1e-6:
        mm.face(list(rings[0]), mats[0] if mats else mat, ref=tuple(o + A * (profile[0][1] + 0.001)))
    if cap1 and profile[-1][0] > 1e-6:
        mm.face(list(rings[-1]), mats[-1] if mats else mat, ref=tuple(o + A * (profile[-1][1] - 0.001)))


def disc(mm, mat, centre, normal, r, seg=16):
    """a flat disc facing `normal`"""
    c, n = _V(centre), _V(normal).normalized()
    u = _perp(n)
    w = n.cross(u)
    vs = [mm.v(tuple(c + u * (r * math.cos(2 * math.pi * k / seg)) + w * (r * math.sin(2 * math.pi * k / seg)))) for k in range(seg)]
    mm.face(vs, mat, ref=tuple(c - n * 0.01))


# ---------------------------------------------------------------- air conditioner (Mitsubishi CU-71H)
AC_LEN = 4.80
AC_HW = 0.95
AC_DECK = 3.85          # top of the low body (deck)
AC_TOP = 4.0265         # hood top = the car's height with the AC
AC_HOOD = (-0.10, 2.24)  # hood over this z range (relative, deck end at −z); a 0.16 m nose ledge beyond


def _rounded_rect(hx, hz, r, seg=3):
    """outline in (x, z) around the origin, counter-clockwise seen from above"""
    pts = []
    for cx, cz, a0 in ((hx - r, hz - r, 0), (-hx + r, hz - r, 90), (-hx + r, -hz + r, 180), (hx - r, -hz + r, 270)):
        for s in range(seg + 1):
            a = math.radians(a0 + 90 * s / seg)
            pts.append((cx + r * math.cos(a), cz + r * math.sin(a)))
    return pts


def _hood_section(hw, y0, y1, ytop, n=10):
    """arch across the hood: (x, y) from (−hw, y0) up the side, over the top to (hw, y0)"""
    pts = [(-hw, y0), (-hw, y1)]
    for k in range(1, n):
        a = math.pi * k / n
        x = -hw * math.cos(a)
        # flattened arch: the shoulders round off quickly, the middle stays near flat
        s = math.sin(a) ** 0.3
        pts.append((x, y1 + (ytop - y1) * s))
    pts += [(hw, y1), (hw, y0)]
    return pts


def air_conditioner(part, zc, deck_end=-1):
    """
    the CU-71H on the roof centre line at zc: a long low body (deck at 3.85) with a raised hood over half of it (top
    4.0265), the condenser deck at the `deck_end` side (−1: towards −z) with two fan openings and the row of flow-guide
    plates (整流板) along each edge, louvred grilles on the sides near both ends, a nose block at each end.
    """
    mm = _Mesh(part)
    s = 1 if deck_end < 0 else -1          # mirror along z so the deck lies at deck_end

    def Z(z):
        return zc + s * z

    hz = AC_LEN / 2
    # --- low body: rounded rectangle in plan, sides down into the roof, top edge chamfered
    out = _rounded_rect(AC_HW, hz, 0.16, 3)
    inner = _rounded_rect(AC_HW - 0.03, hz - 0.03, 0.13, 3)
    ybot = roof_profile_y(AC_HW) - 0.04
    yc = AC_DECK - 0.03
    r_bot = [mm.v((x, ybot, Z(z))) for x, z in out]
    r_mid = [mm.v((x, yc, Z(z))) for x, z in out]
    r_top = [mm.v((x, AC_DECK, Z(z))) for x, z in inner]
    ref = (0.0, (ybot + AC_DECK) / 2, zc)
    n = len(out)
    for k in range(n):
        k1 = (k + 1) % n
        mm.face([r_bot[k], r_bot[k1], r_mid[k1], r_mid[k]], AC, ref=ref)
        mm.face([r_mid[k], r_mid[k1], r_top[k1], r_top[k]], AC, ref=ref)
    # the deck top: only the part the hood leaves open (deck end) as one face, the rest under the hood is left out
    h0 = AC_HOOD[0]
    deck_pts = [p for p in inner if p[1] <= h0]
    dvs = [mm.v((x, AC_DECK, Z(z))) for x, z in deck_pts]
    # close it along the hood's foot
    e0 = mm.v((AC_HW - 0.03, AC_DECK, Z(h0)))
    e1 = mm.v((-(AC_HW - 0.03), AC_DECK, Z(h0)))
    ring = dvs + [e1, e0]
    # order by angle round the deck centre so the polygon is simple
    cxz = (0.0, (-hz + h0) / 2)
    ring.sort(key=lambda v: math.atan2(K.G(v.co)[2] - Z(cxz[1]), K.G(v.co)[0]))
    mm.face(ring, AC, ref=(0.0, AC_DECK - 0.1, Z(cxz[1])))
    # the nose ledge beyond the hood's end
    nose = [mm.v((x, AC_DECK, Z(z))) for x, z in inner if z >= AC_HOOD[1] - 1e-6]
    mm.face(nose, AC, ref=(0.0, AC_DECK - 0.1, Z(hz - 0.1)))
    # the hood
    hw = AC_HW - 0.035
    za, zb = AC_HOOD
    ys = AC_DECK + 0.10         # hood side wall top
    sec = _hood_section(hw, AC_DECK - 0.005, ys, AC_TOP, 12)
    # stations along z with the height factor: steep convex end towards the deck, longer slope at the nose end
    stations = []
    for k in range(7):
        t = k / 6
        stations.append((za + 0.40 * (1 - math.cos(t * math.pi / 2)), math.sin(t * math.pi / 2) ** 0.8))
    for k in range(1, 4):
        stations.append((za + 0.40 + (zb - 0.62 - za - 0.40) * k / 3, 1.0))
    for k in range(1, 8):
        t = k / 7
        stations.append((zb - 0.62 + 0.62 * math.sin(t * math.pi / 2), math.cos(t * math.pi / 2) ** 0.7))
    stations[0] = (stations[0][0], 0.06)
    stations[-1] = (stations[-1][0], 0.06)
    rows = []
    for z, f in stations:
        row = []
        for x, y in sec:
            yy = AC_DECK - 0.005 + (y - (AC_DECK - 0.005)) * f
            row.append(mm.v((x, yy, Z(z))))
        rows.append(row)
    mid = (0.0, AC_DECK + 0.02, Z((za + zb) / 2))
    for i in range(len(rows) - 1):
        a, b = rows[i], rows[i + 1]
        for k in range(len(sec) - 1):
            side = k == 0 or k == len(sec) - 2
            mm.face([a[k], a[k + 1], b[k + 1], b[k]], AC, smooth=not side,
                    ref=(0.0, AC_DECK - 0.2, Z((stations[i][0] + stations[i + 1][0]) / 2)))
    # seams along the hood's flat middle (the lids' longitudinal lines on the photos)
    for xr in (-0.42, 0.42):
        # height of the arch at xr
        yr = max(y for x, y in sec if abs(x - xr) < 1e-6) if any(abs(x - xr) < 1e-6 for x, _ in sec) else None
        if yr is None:
            pts = sorted(sec[1:-1])
            for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
                if x0 <= xr <= x1:
                    yr = y0 + (y1 - y0) * (xr - x0) / (x1 - x0)
        z0, z1 = za + 0.45, zb - 0.68
        beam(mm, AC, (xr, yr + 0.002, Z(z0)), (xr, yr + 0.002, Z(z1)), 0.012, 0.008)
    # end caps of the hood (low lips)
    for row, z, sgn in ((rows[0], za, 1), (rows[-1], zb, -1)):
        mm.face(list(row), AC, ref=(0.0, AC_DECK + 0.005, Z(z + sgn * 0.05)))
    # --- condenser fans on the deck: dark well, guard ring, spokes, hub
    dz = (-hz + h0) / 2
    for fx in (-0.45, 0.45):
        c = (fx, AC_DECK + 0.002, Z(dz))
        disc(mm, DARK, c, (0, 1, 0), 0.30, seg=24)
        ring_pts = [(fx + 0.285 * math.cos(2 * math.pi * k / 24), AC_DECK + 0.016, Z(dz) + 0.285 * math.sin(2 * math.pi * k / 24)) for k in range(24)]
        tube(mm, AC, ring_pts, 0.014, seg=6, closed=True)
        ring_pts = [(fx + 0.16 * math.cos(2 * math.pi * k / 16), AC_DECK + 0.016, Z(dz) + 0.16 * math.sin(2 * math.pi * k / 16)) for k in range(16)]
        tube(mm, AC, ring_pts, 0.007, seg=4, closed=True)
        for k in range(6):
            a = 2 * math.pi * (k + 0.5) / 6
            p0 = (fx + 0.05 * math.cos(a), AC_DECK + 0.016, Z(dz) + 0.05 * math.sin(a))
            p1 = (fx + 0.28 * math.cos(a), AC_DECK + 0.016, Z(dz) + 0.28 * math.sin(a))
            beam(mm, AC, p0, p1, 0.014, 0.012, caps=False)
        cyl(mm, AC, (fx, AC_DECK + 0.002, Z(dz)), (fx, AC_DECK + 0.03, Z(dz)), 0.055, seg=10, caps=(False, True))
    # --- 整流板: a row of small upright plates along each long edge of the deck
    nfin = 9
    for sx in (-1, 1):
        for k in range(nfin):
            z = -hz + 0.22 + (h0 - 0.12 - (-hz + 0.22)) * k / (nfin - 1)
            xa, xb = sorted((sx * (AC_HW - 0.05), sx * (AC_HW - 0.16)))
            box(mm, METAL, xa, xb, AC_DECK, AC_DECK + 0.055, Z(z) - 0.007, Z(z) + 0.007, skip=('-y',))
    # --- louvred grilles on both sides near both ends
    for sx in (-1, 1):
        xg = sx * (AC_HW + 0.004)
        for zg0, zg1 in ((-hz + 0.30, -hz + 0.95), (-hz + 1.10, -hz + 1.45), (hz - 0.95, hz - 0.30)):
            yg0, yg1 = roof_profile_y(AC_HW) + 0.06, AC_DECK - 0.06
            vs = [mm.v((xg, yg0, Z(zg0))), mm.v((xg, yg0, Z(zg1))), mm.v((xg, yg1, Z(zg1))), mm.v((xg, yg1, Z(zg0)))]
            mm.face(vs, DARK, ref=(0.0, (yg0 + yg1) / 2, Z((zg0 + zg1) / 2)))
            nl = 4
            for j in range(nl):
                y = yg0 + (yg1 - yg0) * (j + 0.5) / nl
                beam(mm, AC, (sx * (AC_HW + 0.012), y, Z(zg0 + 0.01)), (sx * (AC_HW + 0.012), y, Z(zg1 - 0.01)), 0.022, 0.012)
    # --- nose blocks at both ends (end face with a dark service grille)
    for e in (-1, 1):
        zf = e * hz
        zn = Z(zf + e * 0.004)
        y0, y1 = roof_profile_y(0.5) + 0.07, AC_DECK - 0.07
        vs = [mm.v((-0.42, y0, zn)), mm.v((0.42, y0, zn)), mm.v((0.42, y1, zn)), mm.v((-0.42, y1, zn))]
        mm.face(vs, DARK, ref=(0.0, (y0 + y1) / 2, Z(zf - e * 0.1)))
        for j in range(3):
            y = y0 + (y1 - y0) * (j + 0.5) / 3
            beam(mm, AC, (-0.41, y, Z(zf + e * 0.012)), (0.41, y, Z(zf + e * 0.012)), 0.022, 0.012)
    return mm.tris


# ---------------------------------------------------------------- pantograph (Toyo Denki PT7117-A)
P_L1, P_L2 = 0.90, 1.40         # lower and upper arm
P_SHAFT_Y = 3.835               # main shaft centre
P_HEAD = 0.16                   # strip top above the head pivot
P_LOWERED = 4.050


def _insulator(mm, x, z, rotate=False):
    """a post insulator standing on the roof at (x, z); returns its top height"""
    y = roof_profile_y(x) - 0.006
    box(mm, METAL, x - 0.09, x + 0.09, y, y + 0.014, z - 0.055, z + 0.055, skip=('-y',))
    yb = y + 0.014
    prof = [(0.052, 0.0), (0.052, 0.02), (0.042, 0.02), (0.042, 0.027), (0.072, 0.036), (0.072, 0.043),
            (0.044, 0.053), (0.044, 0.063), (0.066, 0.073), (0.066, 0.080), (0.042, 0.090), (0.042, 0.102),
            (0.048, 0.102), (0.048, 0.130), (0.0, 0.130)]
    mats = [METAL, METAL, METAL] + [INSUL] * 9 + [METAL, METAL]
    lathe(mm, None, (x, yb, z), (0, 1, 0), prof, seg=12, cap0=False, mats=mats)
    return yb + 0.130


def _ik(head_u, head_y):
    """knee (u, y) for a head pivot (u, y), shaft at (0, P_SHAFT_Y); the knee lies on the +u side"""
    dx, dy = head_u, head_y - P_SHAFT_Y
    D = math.hypot(dx, dy)
    D = min(max(D, abs(P_L2 - P_L1) + 1e-4), P_L1 + P_L2 - 1e-4)
    a = math.atan2(dy, dx)
    c = (P_L1 ** 2 + D ** 2 - P_L2 ** 2) / (2 * P_L1 * D)
    b = math.acos(max(-1.0, min(1.0, c)))
    k = a - b
    return P_L1 * math.cos(k), P_SHAFT_Y + P_L1 * math.sin(k)


def pantograph(part, zc, height=5.0, knee=1, lowered=False):
    """
    PT7117-A with its main shaft at z = zc, the knee pointing to +z (knee=+1) or −z (−1), the strips' top at
    `height` (or folded: 4.050 m, the car's height with a lowered pantograph).
    """
    mm = _Mesh(part)
    kz = 1 if knee >= 0 else -1

    def P(x, y, u):
        return (x, y, zc + kz * u)

    top = P_LOWERED if lowered else max(height, P_LOWERED)
    # --- base: four post insulators on outriggers, frame of square tubes
    tops = []
    for x in (-0.50, 0.50):
        for u in (-0.70, 0.40):
            tops.append(_insulator(mm, x, zc + kz * u))
    yf0 = max(tops)                  # frame members' underside
    yf1 = yf0 + 0.06
    for x in (-0.30, 0.30):          # side members
        beam(mm, METAL, P(x, (yf0 + yf1) / 2, -0.88), P(x, (yf0 + yf1) / 2, 0.52), 0.06, 0.06)
    for u in (-0.85, -0.42, 0.20, 0.49):   # cross members
        beam(mm, METAL, P(-0.27, (yf0 + yf1) / 2, u), P(0.27, (yf0 + yf1) / 2, u), 0.05, 0.05, caps=False)
    for x in (-1, 1):                # outriggers to the insulators
        for u in (-0.70, 0.40):
            beam(mm, METAL, P(x * 0.33, yf0 + 0.025, u), P(x * 0.52, yf0 + 0.025, u), 0.07, 0.05)
    # bearing blocks and main shaft
    for x in (-0.30, 0.30):
        box(mm, METAL, x - 0.045, x + 0.045, yf1, P_SHAFT_Y + 0.03, *sorted((zc - 0.065, zc + 0.065)), skip=('-y',))
    cyl(mm, METAL, P(-0.36, P_SHAFT_Y, 0), P(0.36, P_SHAFT_Y, 0), 0.034, seg=12)
    # spring box (raising springs) and the lowering cylinder on the knee side, the damper
    box(mm, METAL, -0.26, -0.08, yf1, yf1 + 0.11, *sorted((zc + kz * 0.10, zc + kz * 0.50)), skip=('-y',))
    lathe(mm, METAL, P(0.15, P_SHAFT_Y - 0.005, 0.11), (0, 0, kz), [(0.05, 0.0), (0.058, 0.01), (0.058, 0.27), (0.05, 0.28)], seg=12)
    cyl(mm, METAL, P(0.15, P_SHAFT_Y - 0.005, 0.39), P(0.15, P_SHAFT_Y - 0.005, 0.47), 0.012, seg=6, caps=(False, True))
    # rubber stops for the folded head, hooks (U-bars) at the far end
    for x in (-0.30, 0.30):
        cyl(mm, DARK, P(x, yf1, -0.50), P(x, P_LOWERED - P_HEAD - 0.024, -0.50), 0.024, seg=8, caps=(False, True))
    for x in (-0.18, 0.18):
        pts = [P(x, yf1 - 0.01, -0.86)]
        for k in range(7):
            a = math.pi * k / 6
            pts.append(P(x + 0.035 * math.cos(a), yf1 + 0.09 + 0.035 * math.sin(a), -0.86))
        pts.append(P(x - 0.035, yf1 - 0.01, -0.86))
        tube(mm, METAL, pts, 0.008, seg=6)
    # a coil spring along the frame (the head balance spring on the photo)
    coil = []
    turns, per = 6, 8
    for i in range(turns * per + 1):
        a = 2 * math.pi * i / per
        coil.append(P(0.16 + 0.028 * math.cos(a), yf1 + 0.035 + 0.028 * math.sin(a), -0.62 + 0.20 * i / (turns * per)))
    tube(mm, METAL, coil, 0.0055, seg=5)
    # --- arms
    hy = top - P_HEAD                                   # head pivot height
    rise = max(0.0, min(1.0, (hy - (P_LOWERED - P_HEAD)) / 1.0))
    hu = -(0.508 + 0.092 * rise)                        # head pivot: inward of the shaft (opposite the knee)
    ku, ky = _ik(hu, hy)
    shaft = Vector((0, P_SHAFT_Y, 0))
    kn = Vector((0, ky, ku))
    hd = Vector((0, hy, hu))

    def G3(v, x=0.0):
        return P(x, v.y, v.z)

    # lower arm: tapered, flattened octagon; a hub on the shaft
    tube(mm, METAL, [G3(shaft), G3(shaft + (kn - shaft) * 0.5), G3(kn)], [0.052, 0.042, 0.03], seg=8,
         scale=(1.0, 0.75), n0=(1, 0, 0), phase=math.pi / 8)
    cyl(mm, METAL, P(-0.07, P_SHAFT_Y, 0), P(0.07, P_SHAFT_Y, 0), 0.045, seg=12)
    # knee hinge and the lever beyond it
    cyl(mm, METAL, G3(kn, -0.07), G3(kn, 0.07), 0.034, seg=10)
    dlev = (kn - hd).normalized()
    lev = kn + dlev * 0.12
    beam(mm, METAL, G3(kn, 0.065), G3(lev, 0.065), 0.025, 0.04, up=(1, 0, 0))
    # upper arm: round tube to the head
    tube(mm, METAL, [G3(kn), G3(hd)], [0.028, 0.024], seg=10)
    # push rod (lower link) from the frame to the lever, with a turnbuckle
    base = Vector((0, yf1 + 0.02, -0.10))
    box(mm, METAL, 0.045, 0.095, yf1, yf1 + 0.05, *sorted((zc + kz * -0.13, zc + kz * -0.07)), skip=('-y',))
    tube(mm, METAL, [G3(base, 0.07), G3(lev, 0.07)], 0.011, seg=6)
    tb = base + (lev - base) * 0.25
    tube(mm, METAL, [G3(tb, 0.07), G3(tb + (lev - base).normalized() * 0.09, 0.07)], 0.018, seg=6)
    # balance rod: lower arm near the knee to the underside of the head
    b0 = shaft + (kn - shaft) * 0.86
    b1 = hd + Vector((0, -0.05, -0.04 * 1))
    tube(mm, METAL, [G3(b0, -0.055), G3(b1, -0.055)], 0.009, seg=6)
    # damper: frame to the lower arm
    d0 = Vector((0, yf1 + 0.02, -0.16))
    d1 = shaft + (kn - shaft) * 0.32
    dm = d0 + (d1 - d0) * 0.6
    tube(mm, METAL, [G3(d0, -0.10), G3(dm, -0.10)], 0.022, seg=8)
    tube(mm, METAL, [G3(dm, -0.10), G3(d1, -0.10)], 0.009, seg=6)
    box(mm, METAL, -0.13, -0.07, yf1, yf1 + 0.04, *sorted((zc + kz * -0.19, zc + kz * -0.13)), skip=('-y',))
    # --- head
    hz = hd.z
    cyl(mm, METAL, P(-0.47, hy, hz), P(0.47, hy, hz), 0.022, seg=10)
    cyl(mm, METAL, P(-0.40, hy - 0.05, hz - 0.04), P(0.40, hy - 0.05, hz - 0.04), 0.013, seg=8)
    for x in (-0.40, 0.40):
        beam(mm, METAL, P(x, hy - 0.05, hz - 0.04), P(x, hy, hz), 0.02, 0.02, up=(1, 0, 0))
    for x in (-0.42, 0.42):
        box(mm, METAL, x - 0.03, x + 0.03, hy + 0.015, hy + 0.04, *sorted((zc + kz * (hz - 0.16), zc + kz * (hz + 0.16))))
        cyl(mm, METAL, P(x, hy, hz), P(x, hy + 0.015, hz), 0.026, seg=8, caps=(False, False))
        for w in (-0.11, 0.11):
            lathe(mm, DARK, P(x, hy + 0.04, hz + w), (0, 1, 0),
                  [(0.028, 0.0), (0.034, 0.012), (0.026, 0.024), (0.034, 0.036), (0.026, 0.048), (0.028, 0.06)], seg=10,
                  cap0=False, cap1=False)
    for w in (-0.11, 0.11):
        z0, z1 = sorted((zc + kz * (hz + w - 0.035), zc + kz * (hz + w + 0.035)))
        y0, y1 = hy + 0.10, top - 0.014
        # carrier (rectangular section) with its ends bent down
        ym = (y0 + y1) / 2
        path = [(-0.70, ym - 0.075), (-0.63, ym - 0.016), (-0.57, ym), (0.57, ym), (0.63, ym - 0.016), (0.70, ym - 0.075)]
        hh, ww = (y1 - y0), 0.07
        tube(mm, METAL, [P(x, y, hz + w) for x, y in path], 1.0, seg=4, phase=math.pi / 4, smooth=False,
             scale=(hh / math.sqrt(2), ww / math.sqrt(2)), n0=(0, 1, 0))
        # carbon strip on top
        box(mm, DARK, -0.55, 0.55, y1, top, *sorted((zc + kz * (hz + w - 0.022), zc + kz * (hz + w + 0.022))), skip=('-y',))
    # cross plates joining the strips near the ends, the horns
    for sx in (-1, 1):
        box(mm, METAL, sx * 0.49 - 0.025, sx * 0.49 + 0.025, hy + 0.04, hy + 0.10, *sorted((zc + kz * (hz - 0.13), zc + kz * (hz + 0.13))))
        cx, cy = sx * 0.55, top - 0.30
        main, tip = [P(sx * 0.47, top - 0.06, hz)], []
        for k in range(13):
            a = math.radians(90 - 95 * k / 12)
            pnt = P(cx + sx * 0.40 * math.cos(a), cy + 0.265 * math.sin(a), hz)
            if k <= 10:
                main.append(pnt)
            if k >= 10:
                tip.append(pnt)
        tube(mm, METAL, main, 0.0135, seg=8, caps=(True, False))
        tube(mm, TIP, tip, 0.0145, seg=8)
    return mm.tris


# ---------------------------------------------------------------- the gear round a pantograph

def pantograph_gear(part, zc, knee=None, side=-1, z_end=None, z_mid=0.0):
    """
    round the pantograph at zc (same zc / knee as `pantograph`): the lightning arrester (horizontal, exposed porcelain
    on the 1st batch) beside the base, the cables from the frame, the high-voltage conduit along the roof's `side`
    (−1: −x) towards the car centre (`z_mid`, where the other pantograph's run meets it) and down into the end wall at
    the car end, a junction box on that run.
    """
    mm = _Mesh(part)
    kz = (1 if zc >= 0 else -1) if knee is None else (1 if knee >= 0 else -1)
    if z_end is None:
        z_end = kz * 8.75

    def P(x, y, u):
        return (x, y, zc + kz * u)

    sd = 1 if side >= 0 else -1
    # --- lightning arrester: porcelain body along x with sheds, metal ends, on a pedestal (opposite side)
    xa0, xa1 = -sd * 0.60, -sd * 0.86
    ua = -0.40
    ya = roof_profile_y(0.73) + 0.115
    yb = roof_profile_y(0.73) - 0.01
    box(mm, METAL, min(xa0, xa1) + 0.05, max(xa0, xa1) - 0.05, yb, ya - 0.05, *sorted((zc + kz * (ua - 0.05), zc + kz * (ua + 0.05))), skip=('-y',))
    prof = [(0.0, 0.0), (0.058, 0.0), (0.058, 0.03), (0.050, 0.03), (0.050, 0.045), (0.082, 0.06), (0.082, 0.07),
            (0.052, 0.085), (0.052, 0.105), (0.082, 0.12), (0.082, 0.13), (0.052, 0.145), (0.052, 0.165),
            (0.082, 0.18), (0.082, 0.19), (0.052, 0.205), (0.052, 0.22), (0.058, 0.22), (0.058, 0.25), (0.0, 0.25)]
    mats = [METAL, METAL, METAL] + [INSUL] * 15 + [METAL]
    lathe(mm, None, P(xa0, ya, ua), (-sd, 0, 0), prof, seg=12, mats=mats)
    # terminal stud and the cable to the frame
    cyl(mm, METAL, P(xa0, ya, ua), P(xa0 + sd * 0.05, ya, ua), 0.012, seg=6)
    cab = [P(xa0 + sd * 0.05, ya, ua), P(-sd * 0.48, ya + 0.04, ua + 0.02), P(-sd * 0.36, 3.80, ua + 0.05), P(-sd * 0.31, 3.80, ua + 0.05)]
    tube(mm, DARK, cab, 0.011, seg=6)
    # --- cable from the frame down to the conduit's terminal box on the roof
    xt = sd * 0.68
    yt = roof_profile_y(0.68)
    box(mm, METAL, xt - 0.07, xt + 0.07, yt - 0.01, yt + 0.11, *sorted((zc + kz * -1.02, zc + kz * -0.88)), skip=('-y',))
    cab = [P(sd * 0.31, 3.78, -0.75), P(sd * 0.45, 3.80, -0.80), P(sd * 0.62, yt + 0.16, -0.92), P(xt, yt + 0.11, -0.95)]
    tube(mm, DARK, cab, 0.014, seg=6)
    # --- conduit to the car centre: out to the roof's edge, along it past the AC
    rp = 0.024
    xe = sd * 1.07
    ye = roof_profile_y(1.07) + 0.045
    u_mid = (z_mid - zc) * kz
    path = [P(xt, yt + 0.05, -1.02), P(xt, yt + 0.05, -1.12), P(sd * 0.86, roof_profile_y(0.86) + 0.05, -1.35),
            P(xe, ye, -1.60)]
    path.append(P(xe, ye, u_mid))
    tube(mm, AC, path, rp, seg=8, caps=(False, False))
    # saddles holding it every ~1.2 m
    u = -1.75
    while u > u_mid + 0.3:
        z = zc + kz * u
        nrm = Vector((sd * 0.35, 1, 0)).normalized()
        obox(mm, METAL, (xe, ye - 0.005, z), nrm.cross(Vector((0, 0, 1))), nrm, (0, 0, 1), 0.04, 0.03, 0.02)
        u -= 1.2
    # junction box on the run between the AC and the pantograph
    ub = -2.30
    xj = sd * 0.62
    yj = roof_profile_y(0.62)
    box(mm, AC, min(xj - sd * 0.17, xj + sd * 0.17), max(xj - sd * 0.17, xj + sd * 0.17), yj - 0.01, yj + 0.13,
        *sorted((zc + kz * (ub - 0.30), zc + kz * (ub + 0.30))), skip=('-y',))
    tube(mm, DARK, [P(xj + sd * 0.17, yj + 0.07, ub), P(sd * 0.95, yj + 0.05, ub - 0.05), P(xe, ye + 0.02, ub - 0.25)], 0.011, seg=6)
    # --- conduit to the car end, down into the end wall (piping there is built into the body)
    u_end = (z_end - zc) * kz
    ye2 = roof_profile_y(0.68) + 0.05
    path = [P(xt, yt + 0.05, -0.88), P(xt, yt + 0.05, -0.78), P(sd * 0.74, ye2, -0.55), P(sd * 0.74, ye2, u_end - 0.42),
            P(sd * 0.74, ye2 - 0.005, u_end - 0.30), P(sd * 0.74, ye2 - 0.04, u_end - 0.24), P(sd * 0.74, ye2 - 0.12, u_end - 0.22)]
    tube(mm, AC, path, rp, seg=8, caps=(False, False))
    for uu in (0.1, 0.9):
        if uu < u_end - 0.5:
            z = zc + kz * uu
            box(mm, METAL, sd * 0.74 - 0.04, sd * 0.74 + 0.04, roof_profile_y(0.74) - 0.01, ye2 - 0.01, z - 0.02, z + 0.02, skip=('-y',))
    return mm.tris


# ---------------------------------------------------------------- cab roof

def cab_roof_details(part, z_front, dz=0.75):
    """
    on a cab car's roof, `dz` m behind the face's top on the centre line (z_front ≈ 8.4), i.e. just behind where the red
    cab top meets the grey roof (z ≈ 7.75): two radio antennas (dark grey cylinders with domed tops on
    bolted flanges) and the white bracket beside each, a cable from the left one into the roof
    """
    mm = _Mesh(part)
    z = z_front - dz
    for x in (-0.30, 0.02):
        y = roof_profile_y(x) - 0.004
        lathe(mm, METAL, (x, y, z), (0, 1, 0),
              [(0.095, 0.0), (0.095, 0.018), (0.07, 0.018), (0.07, 0.03), (0.062, 0.035), (0.062, 0.27),
               (0.055, 0.295), (0.04, 0.31), (0.02, 0.318), (0.0, 0.32)], seg=16, cap0=False)
        for k in range(6):
            a = 2 * math.pi * (k + 0.5) / 6
            cyl(mm, METAL, (x + 0.082 * math.cos(a), y + 0.018, z + 0.082 * math.sin(a)),
                (x + 0.082 * math.cos(a), y + 0.03, z + 0.082 * math.sin(a)), 0.009, seg=6, caps=(False, True))
        # the white bracket: two posts and a bar, on the −x side and a little behind
        xb = x - 0.15
        yb = roof_profile_y(xb)
        for zz in (z - 0.12, z + 0.06):
            box(mm, INSUL, xb - 0.018, xb + 0.018, yb - 0.01, yb + 0.30, zz - 0.018, zz + 0.018, skip=('-y',))
        box(mm, INSUL, xb - 0.022, xb + 0.022, yb + 0.28, yb + 0.32, z - 0.14, z + 0.08)
        box(mm, INSUL, xb - 0.05, xb + 0.05, yb + 0.05, yb + 0.15, z - 0.10, z + 0.04)
    y = roof_profile_y(-0.30)
    tube(mm, DARK, [(-0.37, y + 0.12, z), (-0.45, y + 0.10, z - 0.02), (-0.50, y + 0.04, z - 0.10), (-0.50, y - 0.01, z - 0.18)], 0.011, seg=6, caps=(True, False))
    return mm.tris


# ---------------------------------------------------------------- along the roof

GUTTER_Y = 3.30         # body_n1000: red below, grey roof above, on the shoulder


def _x_at(y):
    """x on the shoulder where the roof surface is at height y"""
    a, b = 1.0, _HW
    for _ in range(40):
        m = (a + b) / 2
        if roof_profile_y(m) > y:
            a = m
        else:
            b = m
    return (a + b) / 2


def roof_details(part, z0, z1):
    """drip rails along both sides on the paint line where the grey roof meets the red shoulder (y = 3.30)"""
    mm = _Mesh(part)
    x = _x_at(GUTTER_Y)
    dy = (roof_profile_y(x + 0.002) - roof_profile_y(x - 0.002)) / 0.004
    t = Vector((-1.0, -dy)).normalized()            # up the slope, towards the roof centre (for +x)
    n = Vector((-t.y, t.x))
    if n.y < 0:
        n = -n
    for sx in (-1, 1):
        base = Vector((x, GUTTER_Y))
        sec = [base - t * 0.010 - n * 0.003, base - t * 0.010 + n * 0.012, base + t * 0.008 + n * 0.014, base + t * 0.012 - n * 0.003]
        sec = [(sx * p.x, p.y) for p in sec]
        inside = base - n * 0.05
        ref_x, ref_y = sx * inside.x, inside.y
        ra = [mm.v((px, py, z0)) for px, py in sec]
        rb = [mm.v((px, py, z1)) for px, py in sec]
        for k in range(len(sec) - 1):
            mm.face([ra[k], ra[k + 1], rb[k + 1], rb[k]], AC, ref=(ref_x, ref_y, (z0 + z1) / 2))
        for r, zz, d in ((ra, z0, 1), (rb, z1, -1)):
            mm.face(list(r), AC, ref=(sx * base.x, base.y, zz + d * 0.01))
    return mm.tris


# ================================================================ test harness

def _scene_setup():
    scene = bpy.context.scene
    world = bpy.data.worlds.new('sky')
    scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    bg = nt.nodes.get('Background') or nt.nodes.new('ShaderNodeBackground')
    sky = nt.nodes.new('ShaderNodeTexSky')
    try:
        sky.sky_type = 'MULTIPLE_SCATTERING'
    except TypeError:
        pass
    sky.sun_elevation = math.radians(35)
    sky.sun_rotation = math.radians(150)
    nt.links.new(sky.outputs['Color'], bg.inputs['Color'])
    bg.inputs['Strength'].default_value = 0.09
    out = nt.nodes.get('World Output') or nt.nodes.new('ShaderNodeOutputWorld')
    nt.links.new(bg.outputs['Background'], out.inputs['Surface'])
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=120)
    me = bpy.data.meshes.new('ground')
    bm.to_mesh(me)
    g = bpy.data.objects.new('ground', me)
    scene.collection.objects.link(g)
    gm = bpy.data.materials.new('ground')
    gm.use_nodes = True
    gm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = K.srgb('#7d7b76')
    gm.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.9
    me.materials.append(gm)
    sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN'))
    sun.data.energy = 1.6
    sun.data.angle = math.radians(2)
    sun.rotation_euler = (math.radians(50), 0, math.radians(-35))
    scene.collection.objects.link(sun)
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
    scene.collection.objects.link(cam)
    scene.camera = cam
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 48
    scene.cycles.use_denoising = True
    scene.cycles.device = 'CPU'
    scene.render.threads_mode = 'FIXED'
    scene.render.threads = 4
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.exposure = -0.9
    return cam


def _placeholder(mats, z0, z1, rails=True):
    """the body section (red sides, grey roof) from z0 to z1, the rails"""
    part = K.Part('placeholder')
    half = [(1.415, 1.0)]
    for k in range(0, 41):
        x = 1.415 - 1.415 * k / 40
        half.append((x, roof_profile_y(x)))
    half[1] = (1.415, _EAVE)
    ring = [(-x, y) for x, y in half] + [(x, y) for x, y in reversed(half[:-1])]
    ra = [part.bm.verts.new(K.B(x, y, z0)) for x, y in ring]
    rb = [part.bm.verts.new(K.B(x, y, z1)) for x, y in ring]
    n = len(ring)
    for k in range(n - 1):
        f = part.bm.faces.new([ra[k], rb[k], rb[k + 1], ra[k + 1]])
        y = (ring[k][1] + ring[k + 1][1]) / 2
        f.material_index = part.slot('ph_roof' if y > 3.30 else 'ph_red')
        f.smooth = True
    for r, rev in ((ra, False), (rb, True)):
        f = part.bm.faces.new(list(reversed(r)) if not rev else list(r))
        f.material_index = part.slot('ph_red')
    bmesh.ops.recalc_face_normals(part.bm, faces=part.bm.faces)
    if rails:
        for x in (-0.7175, 0.7175):
            part.box('ph_rail', x - 0.0315, x + 0.0315, 0.0, 0.16, z0 - 10, z1 + 10)
    return part


def _look(cam, eye, target, lens):
    cam.location = K.B(*eye)
    d = K.B(*target) - K.B(*eye)
    cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    cam.data.lens = lens


def _render(path, size=(1280, 800)):
    scene = bpy.context.scene
    scene.render.resolution_x, scene.render.resolution_y = size
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


def _main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []

    def opt(name, default=None):
        return argv[argv.index(name) + 1] if name in argv else default

    scene_name = opt('--scene', 'car')
    out = opt('--out', os.path.dirname(os.path.abspath(__file__)))
    clay = '--clay' in argv
    os.makedirs(out, exist_ok=True)
    K.clear_scene()
    m = K.Materials()
    add_materials(m)
    m.add('ph_red', '#c8102e', roughness=0.35)
    m.add('ph_roof', '#8d8a84', roughness=0.7)
    m.add('ph_rail', '#6d6a66', metallic=0.7, roughness=0.4)
    if clay:
        for name, _, _, _ in MATERIALS:
            p = m[name].node_tree.nodes['Principled BSDF']
            p.inputs['Base Color'].default_value = K.srgb('#c9c9c6')
            p.inputs['Metallic'].default_value = 0.0
            p.inputs['Roughness'].default_value = 0.6
    root = K.car_empty('car1')
    gear = K.Part('roof')
    counts = {}
    if scene_name == 'ac':
        ph = _placeholder(m, -4.0, 4.0)
        counts['air_conditioner'] = air_conditioner(gear, 0.0)
    elif scene_name in ('panto', 'panto_low'):
        ph = _placeholder(m, 4.0, 8.75)
        counts['pantograph'] = pantograph(gear, 7.1, knee=1, lowered=scene_name == 'panto_low')
        counts['pantograph_gear'] = pantograph_gear(gear, 7.1, z_mid=4.0)
    elif scene_name == 'cab':
        ph = _placeholder(m, -2.0, 8.4)
        counts['air_conditioner'] = air_conditioner(gear, 0.0, deck_end=-1)
        counts['cab_roof_details'] = cab_roof_details(gear, 8.4)
        counts['roof_details'] = roof_details(gear, -2.0, 7.9)
    else:
        ph = _placeholder(m, -8.75, 8.75)
        counts['air_conditioner'] = air_conditioner(gear, 0.0)
        counts['pantograph+'] = pantograph(gear, 7.1, knee=1)
        counts['pantograph-'] = pantograph(gear, -7.1, knee=-1, lowered=scene_name == 'car_low')
        counts['pantograph_gear+'] = pantograph_gear(gear, 7.1)
        counts['pantograph_gear-'] = pantograph_gear(gear, -7.1)
        counts['roof_details'] = roof_details(gear, -8.75, 8.75)
    ph.build(root, m.mats)
    obj = gear.build(root, m.mats)
    print('TRIANGLES', counts, 'mesh total', sum(len(p.vertices) - 2 for p in obj.data.polygons))
    # check normals: faces whose normal points towards the roof centre line below them are suspect
    cam = _scene_setup()
    tag = '_clay' if clay else ''
    views = {
        'ac': [('ac34', (5.5, 6.2, 6.5), (0, 3.75, 0), 40), ('ac_side', (9.0, 4.1, 0.0), (0, 3.75, 0), 40),
               ('ac_end', (1.2, 4.4, -8.0), (0, 3.8, 0), 45)],
        'panto': [('panto_side', (7.0, 4.4, 6.9), (0, 4.3, 6.9), 40), ('panto34', (4.2, 5.4, 10.2), (0, 4.25, 6.9), 38),
                  ('panto_front', (0.4, 4.6, 13.5), (0, 4.3, 6.9), 45), ('panto_top', (2.2, 7.5, 5.0), (0, 4.0, 6.9), 40)],
        'panto_low': [('pantolow_side', (6.0, 4.2, 6.9), (0, 3.85, 6.9), 40), ('pantolow34', (3.6, 5.2, 9.8), (0, 3.8, 6.8), 40)],
        'cab': [('cab34', (3.5, 5.6, 12.5), (0, 3.7, 7.0), 40)],
        'car': [('car34', (8.5, 9.0, 14.0), (0, 3.9, 1.5), 30), ('car_side', (30.0, 5.0, 0.0), (0, 4.0, 0.0), 35)],
        'car_low': [('carlow34', (9.5, 11.0, 15.0), (0, 3.6, 1.0), 32)],
    }[scene_name]
    if '--cull' in argv:
        scene = bpy.context.scene
        scene.render.engine = 'BLENDER_WORKBENCH'
        scene.display.shading.show_backface_culling = True
        scene.display.shading.light = 'STUDIO'
        scene.display.shading.color_type = 'MATERIAL'
        tag += '_cull'
    for name, eye, target, lens in views:
        _look(cam, eye, target, lens)
        _render(os.path.join(out, f'{name}{tag}.png'))


if __name__ == '__main__':
    _main()
