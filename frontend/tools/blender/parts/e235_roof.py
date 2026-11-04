"""
Roof equipment of the JR East E235 series 0 (Yamanote Line): the AU737 air conditioner, the single-arm pantograph
of the モハE235 with its gear, the antennas on the cab car's roof. A part module for the Blender model (train_kit.Part,
the game's car frame, material prefix `er_`). The mesh helpers and the pantograph are roof_n1000's (Keikyu model),
used as they are; the pantograph is lowered by 0.10 m so it folds to the E235's 3,950 mm.

  air_conditioner(part, zc)          AU737 on the centre line at zc
  pantograph(part, zc, knee)         single arm (PS33H-like), raised to the contact wire, with its gear
  cab_roof_details(part)             antennas on a cab car (its cab at +z)
  add_materials(m)

Figures and where they come from:
- ja.wikipedia JR東日本E235系電車 (read 2026-11-03): height 3,620 mm (roof), 3,950 mm with the pantograph folded;
  pantograph PS33H single arm (some cars PS36A) on the モハE235 (formation table: 9号車 モハE235 ">"); air conditioner
  AU737 (50,000 kcal/h), one per car.
- Line-scan photo dllu 02 (Dllu, CC BY-SA 4.0): on the cab car's roof (z from the bogie midpoint) a thin mast at
  z ≈ 8.98 (0.06 wide, 0.27 tall), a T-shaped antenna at 8.69 (stem 0.10, a plate 0.39 across, a 0.12 × 0.24
  cylinder on top), a second T at 5.63 and a small dome at 2.01; the AC from z ≈ +1.26 to −2.85 with its top at
  3.90…3.95. Head-on photo (S5A-0043, CC BY 4.0): the mast at x ≈ −0.57, the T at x ≈ +0.28.
- "JR East mohaE235-2 20150419" (Rsa, CC BY-SA 3.0): the モハE235's AC off-centre along the car, the pantograph at
  the other end; the AC is a long silver-grey hood with rounded ends, a row of dark slots on its top, louvres along
  the sides' foot. Commons 3/4 views from above (Series-E235-20, E235系0番台): the hood's section is a low dome.
- Estimates: AC 4.1 × 2.2 m; the モハE235's AC at z +1.0 and the pantograph's main shaft at z −7.4 with the knee
  towards the car end; the pantograph's arms and head are the PT7117-A's of roof_n1000 (no PS33H drawing found).
"""
import math
import os
import sys

sys.dont_write_bytecode = True
try:
    import train_kit as K
except ImportError:
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
    import train_kit as K
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import roof_n1000 as RF  # noqa: E402

AC = 'er_ac'
GRILLE = 'er_grille'
ANT = 'er_antenna'

MATS = {
    AC: ('#b8b9b7', 0.55, 0.38),        # AC hood: silver-grey (stainless-like on the photos)
    GRILLE: ('#1c1d1f', 0.1, 0.7),      # slots, louvres
    ANT: ('#5c5f62', 0.4, 0.5),         # antennas
    'rf_metal': ('#8d9093', 0.5, 0.45),  # the pantograph: JR East's light grey (taken before roof_n1000 adds its own)
}

PANTO_DROP = 0.10       # roof_n1000's pantograph folds to 4.05; the E235's to 3.95
AC_LEN = 4.10
AC_HW = 1.10
AC_SIDE = 3.79          # the hood's vertical side ends here
AC_TOP = 3.93


def add_materials(m):
    for name, (col, met, rough) in MATS.items():
        if name not in m.mats:
            m.add(name, col, metallic=met, roughness=rough)
    RF.add_materials(m)


def _tris(part):
    return sum(len(f.verts) - 2 for f in part.bm.faces)


def _moved(part, build, dy=0.0):
    """run build(tmp_part) and copy its faces into part, raised by dy"""
    tmp = K.Part('tmp')
    build(tmp)
    vmap = {}
    for v in tmp.bm.verts:
        co = v.co.copy()
        co.z += dy
        vmap[v] = part.bm.verts.new(co)
    for f in tmp.bm.faces:
        nf = part.bm.faces.new([vmap[v] for v in f.verts])
        nf.material_index = part.slot(tmp.slots[f.material_index])
        nf.smooth = f.smooth
    tmp.bm.free()


# ---------------------------------------------------------------- air conditioner
def _dome(x, hw):
    """the hood's height above AC_SIDE at x: a low superellipse"""
    t = min(1.0, abs(x) / hw)
    return (AC_TOP - AC_SIDE) * (1 - t ** 3.2) ** 0.45


def air_conditioner(part, zc):
    mm = RF._Mesh(part)
    hz = AC_LEN / 2
    ybot = RF.roof_profile_y(AC_HW) - 0.05
    nx = 16
    xs = [-AC_HW * math.cos(math.pi * k / nx) for k in range(nx + 1)]
    # stations along z: the ends drop and round in plan over 0.45 m
    zs = []
    for k in range(6):
        t = k / 5
        zs.append((-hz + 0.45 * (1 - math.cos(t * math.pi / 2)), math.sin(t * math.pi / 2)))
    for k in range(1, 6):
        zs.append((-hz + 0.45 + (AC_LEN - 0.9) * k / 6, 1.0))
    for k in range(6):
        t = 1 - k / 5
        zs.append((hz - 0.45 * (1 - math.cos(t * math.pi / 2)), math.sin(t * math.pi / 2)))
    rows = []
    for z, f in zs:
        f = max(f, 0.12)
        hw = AC_HW * (0.82 + 0.18 * f)
        row = [mm.v((-hw, ybot, zc + z))]
        for x in xs:
            xx = x * hw / AC_HW
            row.append(mm.v((xx, AC_SIDE - 0.10 * (1 - f) + _dome(x, AC_HW) * f, zc + z)))
        row.append(mm.v((hw, ybot, zc + z)))
        rows.append(row)
    ref_y = ybot + 0.05
    for i in range(len(rows) - 1):
        a, b = rows[i], rows[i + 1]
        zm = zc + (zs[i][0] + zs[i + 1][0]) / 2
        for k in range(len(a) - 1):
            side = k == 0 or k == len(a) - 2
            mm.face([a[k], a[k + 1], b[k + 1], b[k]], AC, smooth=not side, ref=(0.0, ref_y, zm))
    for row, z in ((rows[0], zc - hz - 1), (rows[-1], zc + hz + 1)):
        mm.face(list(row), AC, ref=(0.0, ref_y, zc + (0.5 if z < zc else -0.5)))
    # dark slots on the top, in two fields either side of the middle (the photo's grille rows)
    ytop = AC_SIDE + _dome(0.0, AC_HW)
    for z0 in (-1.35, 0.15):
        for j in range(7):
            z = zc + z0 + j * 0.17
            for sx in (-1, 1):
                xa, xb = sorted((sx * 0.08, sx * 0.62))
                y = AC_SIDE + _dome(0.62, AC_HW) + 0.004
                RF.beam(mm, GRILLE, (xa, (ytop + y) / 2 + 0.003, z), (xb, y + 0.003, z), 0.07, 0.006, caps=False)
    # transverse lid seams
    for z in (-1.45, -0.05, 1.45):
        pts = [(x * 0.97, AC_SIDE + _dome(x, AC_HW) + 0.003, zc + z) for x in xs[2:-2]]
        RF.tube(mm, AC, pts, 0.006, seg=4, caps=(False, False))
    # louvres along the foot of both sides
    for sx in (-1, 1):
        for z0, z1 in ((-1.55, -0.35), (0.35, 1.55)):
            x = sx * (AC_HW + 0.003)
            y0, y1 = ybot + 0.09, AC_SIDE - 0.05
            vs = [mm.v((x, y0, zc + z0)), mm.v((x, y0, zc + z1)), mm.v((x, y1, zc + z1)), mm.v((x, y1, zc + z0))]
            mm.face(vs, GRILLE, ref=(0.0, (y0 + y1) / 2, zc))
            for j in range(4):
                y = y0 + (y1 - y0) * (j + 0.5) / 4
                RF.beam(mm, AC, (sx * (AC_HW + 0.012), y, zc + z0 + 0.01), (sx * (AC_HW + 0.012), y, zc + z1 - 0.01), 0.02, 0.012)
    return mm.tris


# ---------------------------------------------------------------- pantograph
def pantograph(part, zc, knee=-1, height=5.0):
    t0 = _tris(part)

    def build(p):
        RF.pantograph(p, zc, height=height + PANTO_DROP, knee=knee)
        RF.pantograph_gear(p, zc, knee=knee, side=-1, z_end=zc + knee * 2.3, z_mid=0.0)
    _moved(part, build, dy=-PANTO_DROP)
    return _tris(part) - t0


# ---------------------------------------------------------------- cab roof
def _flange(mm, x, z, r=0.07):
    y = RF.roof_profile_y(x) - 0.006
    RF.lathe(mm, ANT, (x, y, z), (0, 1, 0), [(r, 0.0), (r, 0.016), (r * 0.6, 0.022), (0.0, 0.022)], seg=14, cap0=False)
    return y + 0.022


def _t_antenna(mm, x, z, plate=0.195):
    y = _flange(mm, x, z, 0.08)
    prof = [(0.05, 0.0), (0.05, 0.09), (plate, 0.10), (plate, 0.115), (0.07, 0.125), (0.06, 0.13), (0.06, 0.33),
            (0.045, 0.355), (0.0, 0.365)]
    RF.lathe(mm, ANT, (x, y, z), (0, 1, 0), prof, seg=18, cap0=False)


def cab_roof_details(part):
    mm = RF._Mesh(part)
    # thin mast with a small insulator cap
    x, z = -0.57, 8.98
    y = _flange(mm, x, z, 0.05)
    RF.lathe(mm, ANT, (x, y, z), (0, 1, 0), [(0.026, 0.0), (0.026, 0.20), (0.04, 0.21), (0.04, 0.235), (0.02, 0.25),
                                             (0.02, 0.27), (0.0, 0.275)], seg=10, cap0=False)
    _t_antenna(mm, 0.28, 8.69)
    _t_antenna(mm, 0.0, 5.63, plate=0.17)
    # small dome (GPS / train radio)
    x, z = -0.30, 2.01
    y = RF.roof_profile_y(x) - 0.005
    RF.lathe(mm, ANT, (x, y, z), (0, 1, 0), [(0.09, 0.0)] + [(0.09 * math.cos(a), 0.10 * math.sin(a)) for a in
                                                          (0.3, 0.6, 0.9, 1.2, 1.45)] + [(0.0, 0.10)], seg=16, cap0=False)
    return mm.tris
