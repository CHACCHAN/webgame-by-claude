"""
Roof equipment of the JR East E231 series 0番台 as converted for the Musashino Line (MU sets): the AU725 centralised
air conditioner, the PS33B single-arm pantograph, the gear round it (lightning arrester, high-voltage cable and conduit
down the car end, junction box), the cab roof's radio antenna and signal flare tube, and the roof's corrugations and
the low boxes at the car ends. A part module for the Blender model (train_kit.Part, the game's car frame, material prefix `er_`).

Frame: the game's car frame of train_kit (metres; +x = the car's left, +y up from the rail top, +z forward).
Every function adds faces to a K.Part and returns the number of triangles it added.

API
  add_materials(m)
  set_roof_profile(half)            the body's half section [(x, y)] from the roof centre outwards (replaces the stand-in)
  roof_profile_y(x)                 roof surface height at x
  air_conditioner(part, zc, louvre_end=-1)
  pantograph(part, zc, knee=-1, lowered=False, height=5.0)
  pantograph_gear(part, zc, knee=-1, side=-1, z_end=None)
  cab_roof_details(part, z_front, dz=ANT_DZ)
  roof_details(part, z0, z1, ribs=True, end_boxes=(), gaps=None)

Figures and where they come from
- ja.wikipedia JR東日本E231系電車 (read 2026-11-03): roof 3,655 mm at the centre line; height over the air conditioner
  4,051.5 mm (AU725A); with the pantograph folded 3,980 mm (all cars, for the narrow tunnels west of Takao);
  pantograph PS33B single arm with a magnetic hook release (電磁鉤外し) instead of an air cylinder; AU725-series
  centralised AC (48.84 kW) on every car; Musashino formation table: モハE231 drawn "＞" at its right (car-3) end =
  one PS33B at the end towards モハE230, knee towards that end. In the game set: car1 (モハE231), −z end, knee −z.
- AU726B data sheet (JR East Transportec, 2011, via the Wayback Machine; the AU725's successor on the same mounting):
  4,100 L × 2,140 W × 376 H; plan: the evaporator half (heat exchangers along both sides, blower in the middle) under
  the arched stainless hood, the condenser half with two fans side by side along the length, coils behind louvres
  along both long sides, a mesh over the fans; photo of the unit on the roof: the hood's outer end rounded down to the
  roof, the condenser half lower with a perforated top.
- Commons photos (measured / looked at, never copied into the model):
  - Saha E231-25･230-9 & Kumoya 143-11 in Omiya (side view of an E231-0 trailer): the hood and the lower condenser
    half about equally long, two seam lines along the hood's top, the hood's end slope; JRE Series-E231-0 MU7 / MU10
    (MaedaAkihiko, CC BY-SA 4.0), Series E231 MU2 in Shin-Urayasu (Wikimizuki, CC BY-SA 4.0), Series-E231-0-MU4F
    (MaedaAkihiko, CC BY-SA 4.0): on the クハE231 and on the モハE231 the condenser half lies at the −z end (towards
    the train's rear), the hood towards the cab.
  - Treinstel E231 MU3 ... Higashi-Tokorozawa (トトト, CC BY-SA 2.1 jp; from above): the hood's end face with
    horizontal ribs, light caps at its corners, a louvre grille on the condenser top; the roof is corrugated stainless
    (ribs ≈ 0.10 m apart over the flat middle); a low dark box on two feet with a cable at the クハ's rear end and on
    the モハ just inboard of the pantograph (what it is: not identified).
  - JR East E231-1000 Antenna (labelled on the car: 車両用信号炎管, 列車無線アンテナ) and the Musashino head-on
    photos (MU19, 20171127, Mu2; scale from the 2.95 m body width): radio antenna at x ≈ −0.72 (grey cylinder ∅ 0.12,
    0.31 tall, bolted flange ∅ 0.20, domed top), signal flare tube at x ≈ +0.40 (thin dark post, white finned spool,
    black cap, 0.25 tall), both just behind the cab top's rounded edge (0.40 m, est.).
  - E231 panta.JPG (toshonori baba, public domain), JR East E231-500 pantograph PS33B M584 / M648 (SEMISAYAMASHI,
    CC BY-SA 4.0), JREast-E231-1000-Pantograph (side view): low frame; squat porcelain insulators at the inboard end,
    taller three-shed ones at the knee end; lower arm a tapered box beam, upper arm a box tube; thin push rod from the
    frame to the lever below the knee, thin balance rod from the knee to the head; main-spring tubes along the frame;
    U-bolt hooks; head: two collector strips side by side, each with its own long horn at both ends (round tubes, up,
    over and down, the tips hanging well below the strips); the lightning arrester, a large light grey cylinder
    (≈ ∅ 0.24 × 0.22) on the roof under the knee, to one side; thick black cables from the frame to it and on to a grey
    conduit along the roof edge that runs to the car end. Arm angles at working height ≈ 29° and 34°; lower : upper
    arm ≈ 0.55 : 1 (side view).
- Estimates (no published figure found): AU725 hood half 2.1 m with a 0.5 m rounded end, condenser top 3.95;
  PS33B arms 0.72 (lower) and 1.28 m (upper) (scale from the strips' spacing 0.25 m, est.), main shaft 3.83 m, frame
  1.38 × 0.56 m, insulators 0.80 m apart across at u = −0.75 / +0.42, strips 1.25 m long, horns to |x| ≈ 0.96 m,
  tips 0.33 below the strips' top (so that folded at 3.98 they clear the roof);
  head pivot 0.50 m inboard of the shaft when raised, so with the shaft at z = −7.40 the head is over the bogie centre
  (−6.9); arrester at u = +0.92; conduit ∅ 0.052 at |x| = 1.02.
- The roof surface (`roof_profile_y`): the body's section once the assembly calls `set_roof_profile`; the stand-in:
  vertical side at x = ±1.475 to the eave 3.24, shoulder r 0.36 tangent to a roof arc r 12.2 through 3.655.

Use on the game set: car1 (モハE231): air_conditioner(part, 0.0); pantograph(part, PANTO_Z, knee=-1);
pantograph_gear(part, PANTO_Z, knee=-1); roof_details(part, -9.75, 9.75). Cab cars: air_conditioner(part, 0.0);
cab_roof_details(part, z_front); roof_details(part, -9.75, z_front - 0.3, end_boxes=(-9.35,)).

Run directly for the test renders (placeholder body):
  blender -t 4 --background --factory-startup --python parts/e231_roof.py -- <outdir> [--scene car|panto|ac|cab|low] [--clay]
"""
import math
import os
import sys

import bmesh
import bpy
from mathutils import Vector

if __name__ == '__main__':
    sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import train_kit as K  # noqa: E402
import roof_n1000 as RN  # noqa: E402  (generic mesh helpers only)

_Mesh, box, obox, beam, tube, cyl, lathe, disc = RN._Mesh, RN.box, RN.obox, RN.beam, RN.tube, RN.cyl, RN.lathe, RN.disc

# ---------------------------------------------------------------- materials
AC = 'er_ac'          # AC hood: bare stainless / aluminium sheet
LIGHT = 'er_light'    # light grey paint: AC louvre box and end caps, arrester, antenna, conduits
METAL = 'er_metal'    # pantograph, frames, brackets (dark grey)
DARK = 'er_dark'      # grille openings, rubber, cables, carbon strips
INSUL = 'er_insul'    # porcelain, the white spool of the small antenna
RIB = 'er_rib'        # the roof's corrugations (the roof's own stainless, a little darker than the AC)

MATERIALS = [
    (AC, '#b3b5b3', 0.75, 0.38),
    (LIGHT, '#b2b4b1', 0.0, 0.5),
    (METAL, '#3d4044', 0.45, 0.5),
    (DARK, '#1d1e20', 0.0, 0.75),
    (INSUL, '#e9e7e0', 0.0, 0.28),
    (RIB, '#8f8e8a', 0.8, 0.45),
]


def add_materials(m):
    for name, colour, metallic, roughness in MATERIALS:
        if name not in m.mats:
            m.add(name, colour, metallic=metallic, roughness=roughness)
    return 0


# ---------------------------------------------------------------- the roof surface
_HW, _SH_R, _ROOF, _ROOF_R = 1.475, 0.36, 3.655, 12.2
_PROFILE = None


def _shoulder():
    """(eave y, shoulder centre (x, y), x where the shoulder meets the roof arc) of the analytic stand-in"""
    cx = _HW - _SH_R
    cy_roof = _ROOF - _ROOF_R
    ye = cy_roof + math.sqrt((_ROOF_R - _SH_R) ** 2 - cx * cx)
    d = math.hypot(cx, ye - cy_roof)
    xt = cx * _ROOF_R / d
    return ye, (cx, ye), xt


def set_roof_profile(half):
    """use a body section's half profile [(x, y), ...] (x ≥ 0, any order) for `roof_profile_y`"""
    global _PROFILE
    _PROFILE = sorted({(round(abs(p[0]), 6), p[1]) for p in half if p[1] >= 3.0})


def roof_profile_y(x):
    """the roof surface's height at x"""
    x = abs(x)
    if _PROFILE:
        pts = _PROFILE
        if x <= pts[0][0]:
            return pts[0][1]
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            if x0 <= x <= x1:
                return y0 + (y1 - y0) * (x - x0) / (x1 - x0) if x1 > x0 else max(y0, y1)
        return pts[-1][1]
    ye, (cx, cy), xt = _shoulder()
    if x <= xt:
        return _ROOF - _ROOF_R + math.sqrt(_ROOF_R ** 2 - x * x)
    if x <= _HW:
        return cy + math.sqrt(max(0.0, _SH_R ** 2 - (x - cx) ** 2))
    return ye


def _slope(x):
    """d(roof y)/dx at x"""
    return (roof_profile_y(x + 0.002) - roof_profile_y(x - 0.002)) / 0.004


def _flat_half():
    """half width of the roof's flat-ish middle (slope under ~14°): where the corrugations run"""
    x = 0.0
    while x < _HW and abs(_slope(x)) < 0.25:
        x += 0.01
    return x - 0.04


# ---------------------------------------------------------------- small helpers

def _quad_strip(mm, mat, rows, ref=None, smooth=False, closed=False, smooth_fn=None):
    """faces between consecutive rows of verts (same length)"""
    for i in range(len(rows) - 1):
        a, b = rows[i], rows[i + 1]
        n = len(a)
        for k in range(n if closed else n - 1):
            k1 = (k + 1) % n
            sm = smooth_fn(i, k) if smooth_fn else smooth
            mm.face([a[k], a[k1], b[k1], b[k]], mat, smooth=sm, ref=ref(i, k) if callable(ref) else ref)


def _ubolt(mm, mat, x, y, z, w, h, r, along_z=False, seg=6):
    """an upright U-bar (hook) with legs `w` apart, `h` tall"""
    pts = []
    for k in range(9):
        a = math.pi * k / 8
        dx = (w / 2) * math.cos(a)
        dy = h - w / 2 + (w / 2) * math.sin(a)
        pts.append((x, y + dy, z + dx) if along_z else (x + dx, y + dy, z))
    pts = [((x, y, z + w / 2) if along_z else (x + w / 2, y, z))] + pts + [((x, y, z - w / 2) if along_z else (x - w / 2, y, z))]
    tube(mm, mat, pts, r, seg=seg)


# ---------------------------------------------------------------- air conditioner (AU725)
AC_LEN = 4.10             # AU726B data sheet (JR East Transportec): 4,100 L × 2,140 W × 376 H; AU725 the same frame
AC_HW = 1.07
AC_TOP = 4.0515           # the car's height over the AC (ja.wikipedia, AU725A)
AC_Y0 = 3.74              # the hood's arch is scaled down towards this height at its ends
AC_SIDE = 3.90            # hood side wall top: the arch starts here
CD_TOP = 3.95             # condenser section's top (est., lower than the hood on the photos)
U_J = -0.05               # hood / condenser joint (local u: −L/2 condenser end … +L/2 hood nose)
NOSE = 0.50               # the hood's outer end rounds down over this length


def _arch(hw, ys, ytop, n=14, flat=0.30):
    """across the hood: (x, y) from (−hw, ys) over the top to (hw, ys); a broad flat arch with rounded shoulders"""
    pts = []
    for k in range(n + 1):
        t = -1 + 2 * k / n
        u = max(0.0, (abs(t) - (1 - flat)) / flat)
        crown = 1 - 0.10 * t * t
        h = (ytop - ys) * crown * math.sqrt(max(0.0, 1 - u * u)) if abs(t) < 1 else 0.0
        pts.append((hw * t, ys + h))
    return pts


def _interp(pts, x):
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if min(x0, x1) <= x <= max(x0, x1):
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0) if x1 != x0 else max(y0, y1)
    return pts[0][1]


def _louvre(mm, p0, du, dv, n, nrm, slat=0.016):
    """a dark louvre opening (corner p0, edge vectors du (along the slats) and dv) with n light slats, facing nrm"""
    p0, du, dv, nrm = Vector(p0), Vector(du), Vector(dv), Vector(nrm).normalized()
    c = p0 + du / 2 + dv / 2
    vs = [mm.v(tuple(p)) for p in (p0, p0 + du, p0 + du + dv, p0 + dv)]
    mm.face(vs, DARK, ref=tuple(c - nrm * 0.05))
    for j in range(n):
        q = p0 + dv * ((j + 0.5) / n) + nrm * 0.008
        beam(mm, LIGHT, tuple(q + du.normalized() * 0.008), tuple(q + du - du.normalized() * 0.008), slat, 0.010,
             up=tuple(nrm))


def air_conditioner(part, zc, louvre_end=-1):
    """
    the AU725 on the roof centre line at zc: the stainless evaporator hood (broad flat arch, two seam lines, its outer
    end rounded down to the roof with horizontal ribs, light corner caps) over one half and the lower condenser section
    (a coil grille at the outer part of each side, louvred end, two fan grilles on top) over the `louvre_end` half (−1: towards −z).
    """
    mm = _Mesh(part)
    s = 1 if louvre_end < 0 else -1

    def Z(u):
        return zc + s * u

    def P(x, y, u):
        return (x, y, Z(u))

    hz = AC_LEN / 2
    hw = AC_HW
    ybot = lambda x: roof_profile_y(x) - 0.025  # noqa: E731
    sec = _arch(hw, AC_SIDE, AC_TOP)
    n = len(sec)
    fj = (CD_TOP + 0.02 - AC_Y0) / (AC_TOP - AC_Y0)
    # --- hood stations (u, height factor, plan taper)
    st = []
    for k in range(5):
        t = k / 4
        st.append((U_J + 0.20 * (1 - math.cos(t * math.pi / 2)), fj + (1 - fj) * math.sin(t * math.pi / 2), 1.0))
    for k in range(1, 4):
        st.append((U_J + 0.20 + (hz - NOSE - U_J - 0.20) * k / 3, 1.0, 1.0))
    for k in range(1, 8):
        t = k / 7
        a = t * math.pi / 2
        st.append((hz - NOSE + NOSE * math.sin(a), math.cos(a) ** 0.9, 1.0 - 0.05 * (1 - math.cos(a))))
    rows = []
    for u, f, tp in st:
        rows.append([mm.v((x * tp, AC_Y0 + (y - AC_Y0) * f, Z(u))) for x, y in sec])
    for i in range(len(rows) - 1):
        um = (st[i][0] + st[i + 1][0]) / 2
        for k in range(n - 1):
            mm.face([rows[i][k], rows[i][k + 1], rows[i + 1][k + 1], rows[i + 1][k]], AC, smooth=True,
                    ref=(0.0, 3.5, Z(um)))
    # side walls under the arch's feet, down to the roof
    for k in (0, n - 1):
        x0 = sec[k][0]
        top = [rows[i][k] for i in range(len(rows))]
        bot = [mm.v((x0 * tp, ybot(x0 * tp), Z(u))) for u, f, tp in st]
        for i in range(len(top) - 1):
            mm.face([top[i], top[i + 1], bot[i + 1], bot[i]], AC, ref=(0.0, 3.6, Z((st[i][0] + st[i + 1][0]) / 2)))
    # the nose's foot: a low vertical panel from the last row down to the roof
    last, tp = rows[-1], st[-1][2]
    lb = [mm.v((x * tp, ybot(x * tp), Z(hz))) for x, _ in sec]
    for k in range(n - 1):
        mm.face([last[k], last[k + 1], lb[k + 1], lb[k]], AC, ref=(0.0, 3.6, Z(hz - 0.3)))
    # seams along the top and ribs across the nose
    for xr in (-0.36, 0.36):
        yr = _interp(sec, xr)
        beam(mm, AC, P(xr, yr + 0.003, U_J + 0.22), P(xr, yr + 0.003, hz - NOSE - 0.02), 0.014, 0.008)
    for t in (0.28, 0.52, 0.76):
        a = t * math.pi / 2
        u = hz - NOSE + NOSE * math.sin(a)
        f, tq = math.cos(a) ** 0.9, 1.0 - 0.05 * (1 - math.cos(a))
        nrm = Vector((0.0, math.sin(a) * 0.5 + 0.5, math.cos(a) * 0.5)).normalized()
        pts = [(x * tq, AC_Y0 + (y - AC_Y0) * f + 0.006, Z(u) + s * 0.006 * nrm.z) for x, y in sec[1:-1]]
        tube(mm, AC, pts, 0.006, seg=4, smooth=False)
    # light corner caps at the nose (the white end pieces on the photos)
    for sx in (-1, 1):
        x0 = sx * hw * st[-1][2]
        box(mm, LIGHT, *sorted((x0 + sx * 0.005, x0 - sx * 0.20)), ybot(abs(x0)) + 0.01, AC_Y0 + 0.08,
            *sorted((Z(hz + 0.005), Z(hz - 0.40))), skip=('-y',))
    # mounting brackets along the foot
    for sx in (-1, 1):
        for u in (-1.55, -0.30, 0.95):
            x0 = sx * (hw + 0.035)
            box(mm, LIGHT, x0 - 0.035, x0 + 0.035, ybot(hw) + 0.01, ybot(hw) + 0.085, *sorted((Z(u - 0.07), Z(u + 0.07))),
                skip=('-y',))
    # --- condenser section: a lower box with rounded corners at its end
    cw = hw - 0.02
    r = 0.14
    u0, u1 = -hz, U_J + 0.12
    ring = [(cw, u1)]
    for k in range(4):
        a = math.radians(0 - 90 * k / 3)
        ring.append((cw - r + r * math.cos(a), u0 + r + r * math.sin(a)))
    for k in range(4):
        a = math.radians(-90 - 90 * k / 3)
        ring.append((-cw + r + r * math.cos(a), u0 + r + r * math.sin(a)))
    ring.append((-cw, u1))
    top = [mm.v((x, CD_TOP, Z(u))) for x, u in ring]
    chamf = [mm.v((x * (1 - 0.02 / cw), CD_TOP + 0.015, Z(u + (0.02 if u < u0 + r else 0)))) for x, u in ring]
    bot = [mm.v((x, ybot(x), Z(u))) for x, u in ring]
    cref = (0.0, 3.7, Z((u0 + u1) / 2))
    for k in range(len(ring) - 1):
        mm.face([bot[k], bot[k + 1], top[k + 1], top[k]], LIGHT, ref=cref)
        mm.face([top[k], top[k + 1], chamf[k + 1], chamf[k]], LIGHT, ref=cref)
    mm.face(chamf, LIGHT, ref=(0.0, CD_TOP - 0.1, Z((u0 + u1) / 2)))
    # louvres on both sides and the end, fan grilles on top
    for sx in (-1, 1):
        xg = sx * (cw + 0.003)
        yb, yt = ybot(cw) + 0.07, CD_TOP - 0.05
        # the outer part of each side is the perforated coil grille (fine slats here); towards the hood a plain panel
        _louvre(mm, (xg, yb, Z(u0 + r + 0.04)), (0, 0, Z(-1.10) - Z(u0 + r + 0.04)), (0, yt - yb, 0), 8, (sx, 0, 0),
                slat=0.010)
        for ua in (-0.72, -0.36):                 # panel seams
            beam(mm, DARK, (xg + sx * 0.002, yb - 0.04, Z(ua)), (xg + sx * 0.002, yt + 0.03, Z(ua)), 0.006, 0.004,
                 up=(sx, 0, 0))
    ze = Z(u0) - s * 0.003
    yb, yt = roof_profile_y(0.5) + 0.04, CD_TOP - 0.05
    for xa, xb in ((-cw + r + 0.03, -0.05), (0.05, cw - r - 0.03)):
        _louvre(mm, (xa, yb, ze), (xb - xa, 0, 0), (0, yt - yb, 0), 4, (0, 0, -s))
    for uc in (-1.48, -0.62):
        c = (0.0, CD_TOP + 0.016, Z(uc))
        g = 0.36
        vs = [mm.v((-g, c[1], Z(uc - g))), mm.v((g, c[1], Z(uc - g))), mm.v((g, c[1], Z(uc + g))), mm.v((-g, c[1], Z(uc + g)))]
        mm.face(vs, DARK, ref=(0.0, c[1] - 0.1, Z(uc)))
        for j in range(7):
            w = -g + 2 * g * (j + 0.5) / 7
            beam(mm, LIGHT, (w, c[1] + 0.008, Z(uc - g)), (w, c[1] + 0.008, Z(uc + g)), 0.012, 0.010, caps=False)
            beam(mm, LIGHT, (-g, c[1] + 0.016, Z(uc + w)), (g, c[1] + 0.016, Z(uc + w)), 0.012, 0.010, caps=False)
        cyl(mm, LIGHT, (0.0, c[1] - 0.01, Z(uc)), (0.0, c[1] + 0.02, Z(uc)), 0.07, seg=10, caps=(False, True))
    # strips of small louvres along both long edges of the top (the hatched blocks on the data sheet's plan)
    for sx in (-1, 1):
        for ua, ub in ((u0 + 0.20, -1.06), (-1.02, U_J - 0.05)):
            x0 = sx * (cw - 0.10)
            _louvre(mm, (x0 - 0.06, CD_TOP + 0.016, Z(ua)), (0.12, 0, 0), (0, 0, Z(ub) - Z(ua)), 6, (0, 1, 0), slat=0.02)
    return mm.tris


# ---------------------------------------------------------------- pantograph (PS33B)
P_L1, P_L2 = 0.72, 1.28      # lower and upper arm (E231-1000 side view: 0.55 : 1)
P_SHAFT_Y = 3.83             # main shaft centre
P_HEAD = 0.125               # strip top above the head pivot
P_LOWERED = 3.980            # ja.wikipedia: height with the pantograph folded
INS_X = 0.40
INS_U = ((-0.75, False), (0.42, True))   # (u, tall): squat ones at the inboard end, three-shed ones at the knee end
STRIP_W = 0.125              # the strips' centres at ±0.125 across the head (along the car)
STRIP_X = 0.625              # strip half length
PANTO_Z = -7.40              # モハE231: main shaft z with knee=-1 (head centre over the bogie centre -6.9)


def _insulator(mm, x, z, tall=False):
    """a squat post insulator on a pad on the roof (or the taller three-shed one); returns its top height"""
    y = roof_profile_y(x) - 0.006
    box(mm, METAL, x - 0.08, x + 0.08, y, y + 0.012, z - 0.06, z + 0.06, skip=('-y',))
    yb = y + 0.012
    if tall:
        prof = [(0.045, 0.0), (0.045, 0.018), (0.036, 0.022), (0.062, 0.034), (0.062, 0.042), (0.038, 0.054),
                (0.038, 0.062), (0.062, 0.074), (0.062, 0.082), (0.038, 0.094), (0.038, 0.102), (0.062, 0.114),
                (0.062, 0.122), (0.036, 0.132), (0.042, 0.134), (0.042, 0.158), (0.0, 0.162)]
        mats = [METAL, METAL] + [INSUL] * 12 + [METAL, METAL]
    else:
        prof = [(0.05, 0.0), (0.05, 0.018), (0.040, 0.022), (0.068, 0.034), (0.068, 0.044), (0.042, 0.056),
                (0.042, 0.064), (0.052, 0.066), (0.052, 0.090), (0.0, 0.090)]
        mats = [METAL, METAL] + [INSUL] * 5 + [METAL, METAL]
    lathe(mm, None, (x, yb, z), (0, 1, 0), prof, seg=12, cap0=False, mats=mats)
    return yb + prof[-1][1]


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


def pantograph(part, zc, knee=-1, lowered=False, height=5.0):
    """
    PS33B with its main shaft at z = zc, the knee pointing to +z (knee=+1) or −z (−1), the strips' top at `height`
    (or folded: 3.980 m, the car's height with the pantograph down). The head pivot sits 0.50 m inboard of the shaft
    when raised (0.58 folded).
    """
    mm = _Mesh(part)
    kz = 1 if knee >= 0 else -1

    def P(x, y, u):
        return (x, y, zc + kz * u)

    top = P_LOWERED if lowered else max(height, P_LOWERED)
    # --- base: insulators, outriggers, a frame of square tubes
    yf0 = 0.0
    for u, tall in INS_U:
        for x in (-INS_X, INS_X):
            yf0 = max(yf0, _insulator(mm, x, zc + kz * u, tall))
    yf0 = max(yf0, 3.76)
    yf1 = yf0 + 0.05
    ym = (yf0 + yf1) / 2
    for x in (-0.28, 0.28):
        beam(mm, METAL, P(x, ym, -0.86), P(x, ym, 0.52), 0.06, 0.05)
    for u in (-0.84, -0.40, 0.20, 0.50):
        beam(mm, METAL, P(-0.25, ym, u), P(0.25, ym, u), 0.05, 0.045, caps=False)
    for u, tall in INS_U:
        for x in (-1, 1):
            yi = roof_profile_y(INS_X) + (0.174 if tall else 0.102)
            # an outrigger from the frame side member out and down to the insulator cap
            beam(mm, METAL, P(x * 0.30, ym, u), P(x * INS_X, yi + 0.015, u), 0.07, 0.035)
    # bearing blocks, main shaft
    for x in (-0.28, 0.28):
        box(mm, METAL, x - 0.045, x + 0.045, yf1, P_SHAFT_Y + 0.035, *sorted((zc - 0.07, zc + 0.07)), skip=('-y',))
    cyl(mm, METAL, P(-0.34, P_SHAFT_Y, 0), P(0.34, P_SHAFT_Y, 0), 0.032, seg=12)
    # drive: two main-spring tubes along the frame inboard of the shaft, the hook-release box at their end
    for x in (-0.14, 0.14):
        lathe(mm, METAL, P(x, yf1 + 0.045, -0.08), (0, 0, -kz),
              [(0.04, 0.0), (0.048, 0.012), (0.048, 0.52), (0.04, 0.535), (0.02, 0.55)], seg=12, cap0=True, cap1=False)
    box(mm, METAL, -0.21, 0.21, yf1, yf1 + 0.10, *sorted((zc + kz * -0.63, zc + kz * -0.75)), skip=('-y',))
    box(mm, DARK, -0.09, 0.09, yf1 + 0.10, yf1 + 0.12, *sorted((zc + kz * -0.65, zc + kz * -0.73)), skip=('-y',))
    # U-bolt hooks at the inboard end, rubber rests under the folded head
    for x in (-0.22, 0.22):
        _ubolt(mm, METAL, x, yf1 - 0.005, zc + kz * -0.80, 0.06, 0.13, 0.009, along_z=True)
    for x in (-0.40, 0.40):
        cyl(mm, DARK, P(x, yf0 - 0.01, -0.57), P(x, P_LOWERED - P_HEAD - 0.045, -0.57), 0.022, seg=8, caps=(False, True))
        beam(mm, METAL, P(x * 0.68, ym, -0.57), P(x, ym, -0.57), 0.04, 0.035, caps=False)
    # --- arms
    hy = top - P_HEAD
    rise = max(0.0, min(1.0, (hy - (P_LOWERED - P_HEAD)) / 0.8))
    hu = -(0.58 - 0.08 * rise)
    ku, ky = _ik(hu, hy)
    shaft = Vector((0, P_SHAFT_Y, 0))
    kn = Vector((0, ky, ku))
    hd = Vector((0, hy, hu))

    def G3(v, x=0.0):
        return P(x, v.y, v.z)

    # lower arm: a tapered box beam, deep at the shaft; hub on the shaft
    d = (kn - shaft)
    tube(mm, METAL, [G3(shaft), G3(shaft + d * 0.45), G3(kn)], [0.07, 0.056, 0.038], seg=4, phase=math.pi / 4,
         scale=(0.65, 1.0), n0=(1, 0, 0), smooth=False)
    cyl(mm, METAL, P(-0.08, P_SHAFT_Y, 0), P(0.08, P_SHAFT_Y, 0), 0.052, seg=12)
    # knee: the elbow block and the lever beyond it
    cyl(mm, METAL, G3(kn, -0.06), G3(kn, 0.06), 0.04, seg=10)
    dlev = (kn - hd).normalized()
    lev = kn + dlev * 0.12 + Vector((0, -0.05, 0))
    for x in (-0.05, 0.05):
        beam(mm, METAL, G3(kn, x), G3(lev, x), 0.025, 0.06, up=(1, 0, 0))
    cyl(mm, METAL, G3(lev, -0.065), G3(lev, 0.065), 0.016, seg=8)
    # upper arm: a box-section tube, deeper at the knee
    tube(mm, METAL, [G3(kn + (hd - kn) * 0.02), G3(kn + (hd - kn) * 0.5), G3(hd)], [0.045, 0.036, 0.026], seg=4,
         phase=math.pi / 4, scale=(0.7, 1.0), n0=(1, 0, 0), smooth=False)
    # push rod from a bracket on the frame at the knee end to the lever, with a turnbuckle
    base = Vector((0, yf1 + 0.03, 0.30))
    box(mm, METAL, 0.05, 0.10, yf1, yf1 + 0.06, *sorted((zc + kz * 0.27, zc + kz * 0.33)), skip=('-y',))
    tube(mm, METAL, [G3(base, 0.075), G3(lev, 0.075)], 0.011, seg=6)
    tb = base + (lev - base) * 0.25
    tube(mm, METAL, [G3(tb, 0.075), G3(tb + (lev - base).normalized() * 0.10, 0.075)], 0.018, seg=6)
    # balance rod: from the knee to the head
    b0 = kn + (hd - kn).normalized() * 0.06 + Vector((0, 0.06, 0))
    b1 = hd + Vector((0, -0.06, 0.04))
    tube(mm, METAL, [G3(b0, -0.06), G3(b1, -0.06)], 0.008, seg=6)
    # shunt cables looping at the knee and at the shaft
    tube(mm, DARK, [G3(kn + Vector((0, -0.02, -0.04)), 0.07), G3(kn + Vector((0, -0.14, 0.03)), 0.09),
                    G3(shaft + d * 0.72 + Vector((0, -0.03, 0)), 0.07)], 0.009, seg=5)
    tube(mm, DARK, [P(0.24, yf1 + 0.02, 0.12), P(0.20, P_SHAFT_Y - 0.04, 0.16), G3(shaft + d * 0.28, 0.06)], 0.010, seg=5)
    # --- head
    hz = hd.z
    cyl(mm, METAL, P(-0.42, hy, hz), P(0.42, hy, hz), 0.022, seg=10)
    for x in (-0.38, 0.38):
        beam(mm, METAL, P(x, hy + 0.02, hz - STRIP_W - 0.04), P(x, hy + 0.02, hz + STRIP_W + 0.04), 0.05, 0.03)
        for w in (-STRIP_W, STRIP_W):
            lathe(mm, DARK, P(x, hy + 0.035, hz + w), (0, 1, 0),
                  [(0.022, 0.0), (0.028, 0.01), (0.02, 0.02), (0.028, 0.03), (0.02, 0.04), (0.022, 0.05)], seg=8,
                  cap0=False, cap1=False)
    for w in (-STRIP_W, STRIP_W):
        y1 = top - 0.016
        y0 = hy + 0.085
        ym = (y0 + y1) / 2
        path = [(-STRIP_X, ym - 0.025), (-STRIP_X + 0.04, ym), (STRIP_X - 0.04, ym), (STRIP_X, ym - 0.025)]
        tube(mm, METAL, [P(x, y, hz + w) for x, y in path], 1.0, seg=4, phase=math.pi / 4, smooth=False,
             scale=((y1 - y0) / math.sqrt(2), 0.06 / math.sqrt(2)), n0=(0, 1, 0))
        box(mm, DARK, -STRIP_X + 0.05, STRIP_X - 0.05, y1, top,
            *sorted((zc + kz * (hz + w - 0.022), zc + kz * (hz + w + 0.022))), skip=('-y',))
        # horns: a round tube from each carrier end, up a little, over and down, the tip hanging nearly vertical
        for sx in (-1, 1):
            pts = [P(sx * (STRIP_X - 0.06), ym, hz + w), P(sx * (STRIP_X + 0.04), ym + 0.012, hz + w)]
            # tip 0.33 below the strips' top: folded (3.98) it still clears the roof (≈ 3.62 at |x| 0.93)
            cx, cy, rx, ry = sx * (STRIP_X + 0.07), top - 0.15, 0.27, 0.15
            for k in range(1, 11):
                a = math.radians(95 - 105 * k / 10)
                pts.append(P(cx + sx * rx * math.cos(a), cy + ry * math.sin(a), hz + w))
            pts.append(P(cx + sx * (rx - 0.035), cy - 0.18, hz + w))
            tube(mm, METAL, pts, 0.013, seg=6)
    return mm.tris


# ---------------------------------------------------------------- the gear round the pantograph

def pantograph_gear(part, zc, knee=-1, side=-1, z_end=None):
    """
    round the PS33B at zc (same zc / knee as `pantograph`): the lightning arrester (a large grey cylinder on a low
    pedestal under the knee, on the `side`), the black HV cables from the frame to it and on to the conduit, the
    conduit along the roof's `side` (−1: −x) to the car end and down into the end wall, the low junction box on two feet
    inboard of the pantograph.
    """
    mm = _Mesh(part)
    kz = 1 if knee >= 0 else -1
    if z_end is None:
        z_end = kz * 9.75

    def P(x, y, u):
        return (x, y, zc + kz * u)

    sd = 1 if side >= 0 else -1
    # --- lightning arrester
    xa, ua = sd * 0.26, 0.92
    ya = roof_profile_y(abs(xa)) - 0.005
    box(mm, METAL, xa - 0.15, xa + 0.15, ya, ya + 0.02, *sorted((zc + kz * (ua - 0.13), zc + kz * (ua + 0.13))), skip=('-y',))
    lathe(mm, LIGHT, P(xa, ya + 0.02, ua), (0, 1, 0),
          [(0.115, 0.0), (0.12, 0.012), (0.12, 0.205), (0.112, 0.218), (0.06, 0.222), (0.0, 0.222)], seg=18, cap0=False)
    for k in range(3):                        # vent slots round the foot
        a = 2 * math.pi * (k + 0.25) / 3
        p = Vector(P(xa + 0.122 * math.cos(a), ya + 0.06, ua)) + Vector((0, 0, 0.122 * math.sin(a)))
        nrm = Vector((math.cos(a), 0, math.sin(a)))
        obox(mm, DARK, tuple(p), nrm.cross(Vector((0, 1, 0))), (0, 1, 0), nrm, 0.022, 0.03, 0.003)
    cyl(mm, METAL, P(xa, ya + 0.24, ua), P(xa, ya + 0.27, ua), 0.014, seg=6, caps=(False, True))
    # cable: frame → arrester top
    tube(mm, DARK, [P(0.26 * sd, 3.84, 0.48), P(0.28 * sd, 3.96, 0.62), P(xa, ya + 0.28, ua - 0.06),
                    P(xa, ya + 0.27, ua - 0.01)], 0.012, seg=6)
    # --- HV cable from the arrester's foot to the conduit; the conduit along the side to the car end
    xc = sd * 1.02
    yc = roof_profile_y(1.02) + 0.035
    u_end = (z_end - zc) * kz
    tube(mm, DARK, [P(xa + sd * 0.12, ya + 0.05, ua), P(sd * 0.55, roof_profile_y(0.55) + 0.05, ua + 0.06),
                    P(sd * 0.85, roof_profile_y(0.85) + 0.05, ua + 0.12), P(xc, yc, ua + 0.20)], 0.02, seg=6)
    box(mm, LIGHT, *sorted((xc - 0.06, xc + 0.06)), yc - 0.05, yc + 0.05, *sorted((zc + kz * (ua + 0.16), zc + kz * (ua + 0.30))),
        skip=('-y',))
    nrm = Vector((sd * -_slope(1.02), 1.0, 0)).normalized()
    path = [P(xc, yc, ua + 0.30), P(xc, yc, u_end - 0.28), P(xc, yc - 0.01, u_end - 0.15), P(xc, yc - 0.06, u_end - 0.07),
            P(xc, yc - 0.16, u_end - 0.035), P(xc, yc - 0.40, u_end - 0.03)]
    tube(mm, LIGHT, path, 0.026, seg=8, caps=(False, False))
    u = ua + 0.45
    while u < u_end - 0.35:
        obox(mm, METAL, (xc, yc - 0.012, zc + kz * u), nrm.cross(Vector((0, 0, 1))), nrm, (0, 0, 1), 0.045, 0.03, 0.02)
        u += 0.40
    # a second cable from the frame's inboard end along the roof to the other side's equipment (photo: from the base
    # out to the side) is left out; the junction box on two feet inboard of the pantograph, its cable to the frame
    end_box(mm, zc + kz * -1.25)
    tube(mm, DARK, [P(0.20, roof_profile_y(0.2) + 0.12, -1.16), P(0.22, 3.80, -1.02), P(0.25, 3.80, -0.88)], 0.010, seg=5)
    return mm.tris


def end_box(mm, z):
    """a low dark box (≈ 0.56 × 0.10 × 0.22 m) on two feet across the roof centre line, a cable out of one side"""
    y = roof_profile_y(0.28)
    for x in (-0.22, 0.22):
        box(mm, METAL, x - 0.025, x + 0.025, y - 0.01, y + 0.07, z - 0.10, z + 0.10, skip=('-y',))
    box(mm, DARK, -0.28, 0.28, y + 0.07, y + 0.15, z - 0.11, z + 0.11)
    box(mm, METAL, -0.24, 0.24, y + 0.15, y + 0.16, z - 0.08, z + 0.08, skip=('-y',))
    tube(mm, DARK, [(0.28, y + 0.10, z), (0.36, y + 0.09, z + 0.02), (0.42, y + 0.02, z + 0.08), (0.45, y - 0.01, z + 0.14)],
         0.008, seg=5, caps=(True, False))


# ---------------------------------------------------------------- cab roof
ANT_DZ = 0.40
ANT_X = (-0.72, 0.40)


def cab_roof_details(part, z_front, dz=ANT_DZ):
    """
    `dz` behind the cab top's edge (z_front): at −x the train radio antenna (列車無線アンテナ: a grey cylinder on a
    bolted flange, domed top), at +x the signal flare tube (車両用信号炎管: a thin dark post, a white finned spool, a
    black cap)
    """
    mm = _Mesh(part)
    z = z_front - dz
    x = ANT_X[0]
    y = roof_profile_y(x) - 0.004
    lathe(mm, LIGHT, (x, y, z), (0, 1, 0),
          [(0.10, 0.0), (0.10, 0.016), (0.075, 0.020), (0.068, 0.030), (0.064, 0.05), (0.058, 0.27), (0.052, 0.29),
           (0.036, 0.305), (0.0, 0.312)], seg=16, cap0=False)
    for k in range(6):
        a = 2 * math.pi * (k + 0.5) / 6
        cyl(mm, METAL, (x + 0.085 * math.cos(a), y + 0.016, z + 0.085 * math.sin(a)),
            (x + 0.085 * math.cos(a), y + 0.027, z + 0.085 * math.sin(a)), 0.009, seg=6, caps=(False, True))
    x = ANT_X[1]
    y = roof_profile_y(x) - 0.004
    lathe(mm, METAL, (x, y, z), (0, 1, 0),
          [(0.06, 0.0), (0.06, 0.014), (0.03, 0.018), (0.02, 0.03), (0.018, 0.14), (0.0, 0.14)], seg=12, cap0=False)
    prof = [(0.018, 0.14), (0.036, 0.145), (0.036, 0.155), (0.022, 0.16), (0.036, 0.165), (0.036, 0.175), (0.022, 0.18),
            (0.036, 0.185), (0.036, 0.195), (0.024, 0.20), (0.0, 0.20)]
    lathe(mm, INSUL, (x, y, z), (0, 1, 0), [(r, t - 0.14) for r, t in prof], seg=12, cap0=False)
    lathe(mm, DARK, (x, y + 0.20, z), (0, 1, 0), [(0.012, 0.0), (0.012, 0.025), (0.016, 0.03), (0.016, 0.045), (0.0, 0.05)],
          seg=10, cap0=False)
    # coax cable from each into the roof behind it
    for xx, h in ((ANT_X[0], 0.04), (ANT_X[1], 0.03)):
        yy = roof_profile_y(xx)
        tube(mm, DARK, [(xx, yy + h, z - 0.06), (xx, yy + h * 0.6, z - 0.14), (xx, yy + 0.005, z - 0.22)], 0.007, seg=5,
             caps=(True, False))
    return mm.tris


# ---------------------------------------------------------------- along the roof
RIB_PITCH = 0.10


def roof_details(part, z0, z1, ribs=True, end_boxes=(), gaps=None):
    """
    the corrugations of the stainless roof (low ridges ≈ 0.10 m apart over the flat middle, `ribs`), stopped in the
    `gaps` [(za, zb)] (under the AC, round the pantograph), and the low boxes at `end_boxes` (z on the centre line)
    """
    mm = _Mesh(part)
    if gaps is None:
        gaps = [(-AC_LEN / 2 + 0.06, AC_LEN / 2 - 0.06)]     # under the AC (at z = 0)
    if ribs:
        xh = _flat_half()
        nr = int(xh * 2 / RIB_PITCH)
        spans = []
        za = z0
        for g0, g1 in sorted(gaps):
            if g0 > za:
                spans.append((za, min(g0, z1)))
            za = max(za, g1)
        if za < z1:
            spans.append((za, z1))
        for k in range(nr + 1):
            x = -nr * RIB_PITCH / 2 + k * RIB_PITCH
            y = roof_profile_y(x)
            nx = -_slope(x)
            n = Vector((nx, 1.0)).normalized()
            t = Vector((n.y, -n.x))
            a = Vector((x, y)) - t * 0.022 - n * 0.002
            b = Vector((x, y)) - t * 0.010 + n * 0.012
            c = Vector((x, y)) + t * 0.010 + n * 0.012
            d = Vector((x, y)) + t * 0.022 - n * 0.002
            for sa, sb in spans:
                ra = [mm.v((p.x, p.y, sa)) for p in (a, b, c, d)]
                rb = [mm.v((p.x, p.y, sb)) for p in (a, b, c, d)]
                ref = (x - n.x * 0.05, y - n.y * 0.05, (sa + sb) / 2)
                for j in range(3):
                    mm.face([ra[j], ra[j + 1], rb[j + 1], rb[j]], RIB, ref=ref)
    for z in end_boxes:
        end_box(mm, z)
    return mm.tris


# ================================================================ test harness

def _scene_setup():
    return RN._scene_setup()


def _placeholder(z0, z1, rails=True):
    """the body section (stainless sides, roof) from z0 to z1, the rails"""
    part = K.Part('placeholder')
    if _PROFILE:
        half = [(_HW, 1.0)] + sorted(_PROFILE, key=lambda p: (-p[0], p[1]))
    else:
        ye = _shoulder()[0]
        half = [(_HW, 1.0), (_HW, ye)]
        for k in range(1, 41):
            x = _HW - _HW * k / 40
            half.append((x, roof_profile_y(x)))
    if half[-1][0] > 1e-6:
        half.append((0.0, roof_profile_y(0.0)))
    ring = [(-x, y) for x, y in half] + [(x, y) for x, y in reversed(half[:-1])]
    ra = [part.bm.verts.new(K.B(x, y, z0)) for x, y in ring]
    rb = [part.bm.verts.new(K.B(x, y, z1)) for x, y in ring]
    n = len(ring)
    for k in range(n - 1):
        f = part.bm.faces.new([ra[k], rb[k], rb[k + 1], ra[k + 1]])
        y = (ring[k][1] + ring[k + 1][1]) / 2
        f.material_index = part.slot('ph_roof' if y > 3.25 else ('ph_band' if 3.05 < y < 3.225 else 'ph_side'))
        f.smooth = True
    for r, rev in ((ra, False), (rb, True)):
        f = part.bm.faces.new(list(reversed(r)) if not rev else list(r))
        f.material_index = part.slot('ph_side')
    bmesh.ops.recalc_face_normals(part.bm, faces=part.bm.faces)
    if rails:
        for x in (-0.7175, 0.7175):
            part.box('ph_rail', x - 0.0315, x + 0.0315, 0.0, 0.16, z0 - 10, z1 + 10)
    return part


def _main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []

    def opt(name, default=None):
        return argv[argv.index(name) + 1] if name in argv else default

    out, skip = '.', False
    for a in argv:
        if skip:
            skip = False
        elif a in ('--scene', '--views', '--samples'):
            skip = True
        elif not a.startswith('--'):
            out = a
            break
    scene_name = opt('--scene', 'car')
    clay = '--clay' in argv
    os.makedirs(out, exist_ok=True)
    if '--analytic' not in argv:
        try:                    # the body's real section, as the assembly passes it
            import e231_body as EB
            set_roof_profile([(x, y) for x, y, _nx, _ny in EB.half_profile()])
        except Exception as e:  # noqa: BLE001
            print('WARNING: e231_body not usable, analytic roof', e)
    K.clear_scene()
    m = K.Materials()
    add_materials(m)
    m.add('ph_side', '#a9aba9', metallic=0.85, roughness=0.32)
    m.add('ph_roof', '#8a8985', metallic=0.7, roughness=0.5)
    m.add('ph_band', '#f05a1e', roughness=0.4)
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
    PZ = PANTO_Z
    if scene_name == 'ac':
        ph = _placeholder(-4.0, 4.0)
        counts['air_conditioner'] = air_conditioner(gear, 0.0)
        counts['roof_details'] = roof_details(gear, -4.0, 4.0)
    elif scene_name in ('panto', 'low'):
        ph = _placeholder(-9.75, -3.0)
        counts['pantograph'] = pantograph(gear, PZ, knee=-1, lowered=scene_name == 'low')
        counts['pantograph_gear'] = pantograph_gear(gear, PZ, knee=-1)
        counts['roof_details'] = roof_details(gear, -9.75, -3.0)
    elif scene_name == 'cab':
        ph = _placeholder(-9.75, 9.6)
        counts['air_conditioner'] = air_conditioner(gear, 0.0)
        counts['cab_roof_details'] = cab_roof_details(gear, 9.6)
        counts['roof_details'] = roof_details(gear, -9.75, 9.3, end_boxes=(-9.35,))
    else:
        ph = _placeholder(-9.75, 9.75)
        counts['air_conditioner'] = air_conditioner(gear, 0.0)
        counts['pantograph'] = pantograph(gear, PZ, knee=-1)
        counts['pantograph_gear'] = pantograph_gear(gear, PZ, knee=-1)
        counts['roof_details'] = roof_details(gear, -9.75, 9.75)
    ph.build(root, m.mats)
    obj = gear.build(root, m.mats)
    print('TRIANGLES', counts, 'total', sum(counts.values()), 'mesh', sum(len(p.vertices) - 2 for p in obj.data.polygons))
    cam = _scene_setup()
    scene = bpy.context.scene
    scene.cycles.samples = int(opt('--samples', '24'))
    tag = '_clay' if clay else ''
    views = {
        'ac': [('ac34', (5.0, 6.0, 6.5), (0, 3.8, 0), 40), ('ac_side', (9.0, 4.3, 0.0), (0, 3.8, 0), 38),
               ('ac_end', (1.6, 4.6, -7.5), (0, 3.85, 0), 45), ('ac_nose', (2.5, 4.9, 7.0), (0, 3.85, 1.5), 42)],
        'panto': [('panto_side', (-7.0, 4.5, -7.2), (0, 4.35, -7.2), 40), ('panto34', (-4.0, 5.6, -11.5), (0, 4.25, -7.3), 38),
                  ('panto_head', (-0.4, 4.7, -1.5), (0, 4.4, -7.3), 50), ('panto_top', (-2.4, 7.4, -5.0), (0, 3.9, -7.6), 40)],
        'low': [('low_side', (-6.0, 4.2, -7.3), (0, 3.85, -7.3), 40), ('low34', (-3.6, 5.2, -11.0), (0, 3.85, -7.5), 40)],
        'cab': [('cab34', (-3.5, 5.8, 13.5), (0, 3.75, 7.0), 40), ('cab_head', (-0.5, 4.0, 40.0), (0, 3.8, 8.0), 60)],
        'car': [('car34', (-8.5, 9.0, 14.0), (0, 3.9, 0.0), 30), ('car_side', (-30.0, 5.0, 0.0), (0, 4.0, 0.0), 35)],
    }[scene_name]
    sel = opt('--views')
    for name, eye, target, lens in views:
        if sel and name not in sel.split(','):
            continue
        RN._look(cam, eye, target, lens)
        RN._render(os.path.join(out, f'{name}{tag}.png'), size=(1280, 720))


if __name__ == '__main__':
    _main()
