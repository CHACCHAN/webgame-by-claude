"""
The gear under the cab of the E231 近郊タイプ (1000番台): the commuter type's tight-lock coupler, carrier bar, louvred
boxes, stays and hoses (parts/e231_coupler.py, unchanged: front_coupler(..., corner_boxes=False) — the 1000番台 has
no boxes at the face's bottom corners, the FRP ledge runs there) plus the electric coupler that every cab car of the
add-on and basic sets carries (ja.wikipedia: 電気連結器, for coupling 10 + 5), a dark plate behind the skirt's deep
notch and the folding rod frame on the skirt's right half. Material names of e231_coupler (`ec_`).

  front_gear(part, z_face=10.0) -> triangles added

Measured on Commons "JRE Series-E231-1000 S-13.jpg" (MaedaAkihiko, CC BY-SA 4.0; head-on, scale from the lamp
panel's 2.59 m): the electric coupler box hangs under the head, x ±0.26, y 0.44…0.68, with a cylindrical cover (axis
across the car) on its front, x −0.13…+0.17 (seen from ahead: a little right of the centre), ∅ ≈ 0.17 at y 0.56, a
lever on its right end (−x); the rod frame on the skirt: x −0.86…−1.16, from the underframe (y 0.94) down to y 0.47,
two small hinge blocks at its bottom. Depths estimated (the cover's front 0.03 behind the coupler face).
"""
import math
import os
import sys

sys.dont_write_bytecode = True
_here = os.path.dirname(os.path.abspath(__file__))
for _p in (_here, os.path.dirname(_here)):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import train_kit as K  # noqa: E402,F401
import e231_coupler as CP  # noqa: E402

GR, DK, RB, SV = 'ec_grey', 'ec_dark', 'ec_rubber', 'ec_silver'

ELECTRIC = dict(x=0.26, y0=0.44, y1=0.68, cover_x=(-0.13, 0.17), cover_y=0.56, cover_r=0.085)
ROD_FRAME = dict(x=(-1.16, -0.86), y0=0.47, y1=0.94)


def add_materials(m):
    CP.add_materials(m)


def _tris(part):
    return sum(len(f.verts) - 2 for f in part.bm.faces)


def electric_coupler(part, z_face=10.0):
    e = ELECTRIC
    x, y0, y1 = e['x'], e['y0'], e['y1']
    zf = z_face - 0.03 - 2 * e['cover_r'] + 0.02          # the box's front, the cover standing out of it
    part.box(GR, -x, x, y0, y1, zf - 0.30, zf, bevel=0.012, segments=1)
    part.box(DK, -x + 0.02, x - 0.02, y0 - 0.015, y0, zf - 0.26, zf - 0.04)
    # the front plate with a seam round it
    part.box(GR, -x + 0.012, x - 0.012, y0 + 0.012, y1 - 0.012, zf, zf + 0.012, bevel=0.004, segments=1)
    # the cylindrical cover across the front
    c0, c1 = e['cover_x']
    r = e['cover_r']
    zc = zf + 0.012 + r - 0.03
    part.cylinder(GR, ((c0 + c1) / 2, e['cover_y'], zc), r, c1 - c0, axis='x', segments=20)
    for xx in (c0 + 0.01, c1 - 0.01):
        part.cylinder(DK, (xx, e['cover_y'], zc), r + 0.004, 0.012, axis='x', segments=20)
    # its lever (on the right seen from ahead: −x) and the latch
    part.box(SV, c0 - 0.045, c0 - 0.005, e['cover_y'] + 0.02, e['cover_y'] + 0.05, zc - 0.02, zc + r + 0.02, bevel=0.004, segments=1)
    part.box(SV, c0 - 0.03, c0 - 0.015, e['cover_y'] - 0.06, e['cover_y'] + 0.04, zc + r + 0.005, zc + r + 0.025)
    # the hanger up to the coupler shank and the cable bundle into the underframe
    part.box(DK, -0.07, 0.07, y1, 0.75, zf - 0.22, zf - 0.08)
    part.cylinder(RB, (0.0, (y0 + y1) / 2, zf - 0.40), 0.04, 0.22, axis='z', segments=8)


def rod_frame(part):
    """the folding rod frame on the skirt's right half (seen from ahead: left), standing just ahead of the skirt"""
    import e231_kinkou_body as KB
    xa, xb = ROD_FRAME['x']
    y0, y1 = ROD_FRAME['y0'], ROD_FRAME['y1']

    def zs(x):
        return KB.SKIRT_TIP - (KB.SKIRT_TIP - KB.SKIRT_CORNER[1]) * abs(x) / KB.SKIRT_CORNER[0] + 0.02
    pts = [(xa, y1, zs(xa) - 0.12), (xa, KB.SKIRT_TOP, zs(xa)), (xa, y0, zs(xa)), (xb, y0, zs(xb)), (xb, KB.SKIRT_TOP, zs(xb)),
           (xb, y1, zs(xb) - 0.12)]
    for a, b in zip(pts[:-1], pts[1:]):
        part.beam(GR, a, b, 0.009, 0.009)
    for xx in (xa + 0.08, xb - 0.08):
        part.box(GR, xx - 0.022, xx + 0.022, y0 - 0.012, y0 + 0.016, zs(xx) - 0.02, zs(xx) + 0.012)


def front_gear(part, z_face=10.0):
    t0 = _tris(part)
    CP.front_coupler(part, z_face, corner_boxes=False)
    electric_coupler(part, z_face)
    rod_frame(part)
    # a dark plate behind the skirt's notch below the commuter type's back plate (y 0.58…1.0)
    part.box(DK, -0.42, 0.42, 0.26, 0.60, 9.40, 9.42)
    return _tris(part) - t0
