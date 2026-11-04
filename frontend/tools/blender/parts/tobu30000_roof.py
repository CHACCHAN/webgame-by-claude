"""
Roof equipment of the Tobu 30000 series (Tojo Line sets): three air conditioners per car, the cab roof's train-radio
antenna and signal-flare post, the pantographs of the M1 car (モハ32600) and their gear. A part module for the Blender
model (train_kit.Part, the game's car frame, material prefix `tr_`).

  add_materials(m), set_roof_profile(half)
  roof(part, kind)            kind 'cab' (Tc: antennas) or 'middle' (M1: two pantographs); -> triangles added
  air_conditioner(part, zc, nose)   one unit centred at zc, its rounded end towards +z (nose=1) or −z (−1)

Figures and sources:
- ja.wikipedia 東武30000系電車: Toshiba microcomputer-controlled semi-centralised (集約分散式) air conditioners, three per
  car, 16,000 kcal/h each; height 4,045 mm with the AC (so the units' top is at 4.045), 4,080 mm with a lowered
  pantograph; single-arm pantographs, M1 drawn "＜　＞" in the formation table (one at each end, knee towards the
  car end, as the Keikyu model reads the same notation; the 31612 / 31604 photos show one close behind car 0).
- Shape of the AC units (Commons "Tobu-Series30000 join.jpg", "Tobu-30000 Tojo-Line Musashi-Ranzan.jpg"): stainless
  boxes with vertical riveted side panels and a barrel top; one end (towards Ikebukuro on every car) rounds down to
  the roof in a long quarter curve, the other is square; on the sides an oval-slot louvre near the square end and a
  square patch of round holes in the middle, vertical panel joints; grilles on the top; the three units stand close
  together along the roof. Length 4.55 m each with 0.15 m gaps, the rounded end 1.75 m (38 %), width 1.80 m, side
  0.27 m high: estimates (Ranzan photo: three units of ~4.6-4.9 m nearly touching, from ~1.5 m behind the cab face on
  Tc1, so the cab cars' units sit 0.5 m towards the cab; the join photo for the proportions and side details).
- Pantograph: type not published on ja.wikipedia; the single-arm builder of roof_n1000 (Toyo Denki PT7117-A layout)
  is used with this roof's height (main shaft 0.215 m over the roof as there; lowered height 4.080).
- Cab roof (photos 31612, 31604, Ikebukuro 31613): a "1"-shaped train-radio antenna just right of the centre line seen
  from ahead (x −0.15) and a dark cylindrical post further left and back (signal flare, x −0.45).
"""
import math

import train_kit as K  # noqa: F401
import roof_n1000 as RN

AC = 'tr_ac'
DARK = 'tr_dark'
METAL = 'tr_metal'

MATERIALS = [
    (AC, '#b9bab8', 1.0, 0.44),
    (DARK, '#17181a', 0.0, 0.7),
    (METAL, '#4d5156', 0.6, 0.45),
]

AC_LEN = 4.55
AC_HW = 0.90
AC_SIDE = 0.27           # side panel height above the roof at its edge
AC_TOP = 4.045
AC_NOSE = 1.75           # length of the rounded end (38 % of the unit, join photo)
AC_PITCH = 4.70          # units 0.15 m apart
CAB_SHIFT = 0.50         # the cab cars' units sit this much towards the cab (Ranzan photo; estimate)
PANTO_Z = 8.05


def add_materials(m):
    for name, colour, metallic, roughness in MATERIALS:
        if name not in m.mats:
            m.add(name, colour, metallic=metallic, roughness=roughness)
    RN.add_materials(m)
    return 0


def set_roof_profile(half):
    RN.set_roof_profile(half)


def roof_y(x):
    return RN.roof_profile_y(x)


def _tris(part):
    return sum(len(f.verts) - 2 for f in part.bm.faces)


def _plate(mm, mat, x, sx, y0, y1, z0, z1):
    """one quad on the AC's side wall (x, facing sx), raised 2 mm"""
    xx = x + sx * 0.002
    vs = [mm.v((xx, y0, z0)), mm.v((xx, y1, z0)), mm.v((xx, y1, z1)), mm.v((xx, y0, z1))]
    mm.face(vs, mat, ref=(xx - sx, (y0 + y1) / 2, (z0 + z1) / 2))


def air_conditioner(part, zc, nose=1):
    """one unit: barrel-topped box, its rounded end towards +z·nose; louvres, grilles, joints, rivets"""
    mm = RN._Mesh(part)
    yb = roof_y(AC_HW)
    ys = yb + AC_SIDE                                  # top of the side panels
    rise = AC_TOP - ys

    def top_y(x):
        t = min(1.0, abs(x) / AC_HW)
        return ys + rise * (1 - t ** 2.2) ** 0.5

    def section(h):
        """cross-section from −x over the top to +x; h scales its height over the roof (the rounded end)"""
        pts = [(-AC_HW, yb - 0.02)]
        n = 12
        for k in range(n + 1):
            x = -AC_HW + 2 * AC_HW * k / n
            y0 = roof_y(x) - 0.02
            pts.append((x, y0 + (top_y(x) - y0) * h))
        pts.append((AC_HW, yb - 0.02))
        return pts

    z_sq = zc - nose * AC_LEN / 2                      # square end
    z_n0 = zc + nose * (AC_LEN / 2 - AC_NOSE)          # where the rounded end starts
    st = [(z_sq, 1.0), (z_n0, 1.0)]
    m = 10
    for k in range(1, m + 1):
        a = (math.pi / 2) * k / m
        st.append((z_n0 + nose * AC_NOSE * math.sin(a), max(math.cos(a) ** 0.85, 0.05)))
    rings = [[mm.v((x, y, z)) for x, y in section(h)] for z, h in st]
    ref_c = (0.0, yb - 0.5, zc)
    last = len(rings[0]) - 2
    for ra, rb in zip(rings[:-1], rings[1:]):
        for k in range(len(ra) - 1):
            mm.face([ra[k], ra[k + 1], rb[k + 1], rb[k]], AC, ref=ref_c, smooth=1 < k < last)
    for r, z, d in ((rings[0], z_sq, -nose), (rings[-1], st[-1][0], nose)):
        c = mm.v((0.0, yb - 0.02, z))
        for k in range(1, len(r) - 2):
            mm.face([c, r[k], r[k + 1]], AC, ref=(0.0, yb + 0.05, z - d * 1.0))
    L = AC_LEN

    def zz(u):           # distance u from the square end -> z
        return z_sq + nose * u
    for sx in (-1, 1):
        x = sx * AC_HW
        # louvre: two staggered rows of oval slots over the first quarter
        for yy, off, n in ((ys - 0.065, 0.0, 11), (ys - 0.115, 0.05, 10)):
            for k in range(n):
                u = 0.10 + off + k * 0.100
                _plate(mm, DARK, x, sx, yy - 0.012, yy + 0.012, *sorted((zz(u - 0.037), zz(u + 0.037))))
        # the round-hole patch
        uh = 0.42 * L
        for i in range(6):
            for j in range(6):
                u = uh + (i - 2.5) * 0.024
                y = ys - 0.075 - j * 0.024
                _plate(mm, DARK, x, sx, y - 0.007, y + 0.007, *sorted((zz(u - 0.007), zz(u + 0.007))))
        # panel joints and rivets
        for u in (0.35 * L, AC_LEN - AC_NOSE):
            _plate(mm, DARK, x, sx, yb + 0.01, ys - 0.012, *sorted((zz(u - 0.004), zz(u + 0.004))))
        for u in (0.04, 0.35 * L - 0.05, 0.35 * L + 0.05, 0.50 * L, AC_LEN - AC_NOSE - 0.05):
            for y in (yb + 0.06, ys - 0.05):
                RN.box(mm, METAL, *sorted((x, x + sx * 0.007)), y - 0.007, y + 0.007,
                       *sorted((zz(u - 0.007), zz(u + 0.007))), skip=(('-x',) if sx > 0 else ('+x',)))
    # the top: two grille fields with bars over the square half, a seam strip along each side's top edge
    for u0, u1 in ((0.15, 1.20), (1.40, 2.55)):
        for sx in (-1, 1):
            x0, x1 = sorted((sx * 0.14, sx * 0.60))
            y = top_y(0.37) + 0.004
            RN.box(mm, DARK, x0, x1, y - 0.01, y, *sorted((zz(u0), zz(u1))), skip=('-y',))
            nb = int((u1 - u0) / 0.06)
            for k in range(nb):
                u = u0 + (u1 - u0) * (k + 0.5) / nb
                RN.box(mm, AC, x0, x1, y, y + 0.006, *sorted((zz(u - 0.012), zz(u + 0.012))), skip=('-y',))
    for sx in (-1, 1):
        x = sx * (AC_HW - 0.01)
        RN.box(mm, METAL, *sorted((x, x - sx * 0.04)), ys - 0.004, ys + 0.008, *sorted((zz(0.02), zz(AC_LEN - AC_NOSE))),
               skip=('-y',))
    return mm.tris


def cab_roof(part, z_face=9.80):
    """the cab roof: a "1"-shaped train-radio antenna and the signal-flare post"""
    mm = RN._Mesh(part)
    z = z_face - 0.55
    x = -0.15
    y = roof_y(x)
    RN.box(mm, METAL, x - 0.07, x + 0.07, y - 0.01, y + 0.02, z - 0.10, z + 0.10)
    RN.box(mm, METAL, x - 0.025, x + 0.025, y + 0.02, y + 0.40, z - 0.03, z + 0.03)
    RN.box(mm, METAL, x - 0.025, x + 0.025, y + 0.34, y + 0.40, z - 0.03, z + 0.17)    # the flag of the "1"
    xp, zp = -0.45, z_face - 0.95
    yp = roof_y(xp)
    RN.lathe(mm, DARK, (xp, yp - 0.01, zp), (0, 1, 0),
             [(0.09, 0.0), (0.09, 0.02), (0.055, 0.02), (0.055, 0.24), (0.045, 0.26), (0.0, 0.27)], seg=14, cap0=False)
    return mm.tris


def roof(part, kind, nose=1):
    """all the roof equipment of one car; `nose`: which way the AC units' rounded ends point (towards Ikebukuro)"""
    n = _tris(part)
    shift = CAB_SHIFT if kind == 'cab' else 0.0
    for k in (-1, 0, 1):
        air_conditioner(part, shift + k * AC_PITCH, nose)
    if kind == 'cab':
        cab_roof(part)
    else:
        save = RN.P_SHAFT_Y, RN.P_LOWERED
        RN.P_SHAFT_Y = roof_y(0.0) + 0.215
        RN.P_LOWERED = 4.080
        try:
            for zc, knee in ((PANTO_Z, 1), (-PANTO_Z, -1)):
                RN.pantograph(part, zc, height=5.0, knee=knee)
                RN.pantograph_gear(part, zc, knee=knee, side=-1, z_end=knee * 9.75, z_mid=0.0)
        finally:
            RN.P_SHAFT_Y, RN.P_LOWERED = save
    return _tris(part) - n
