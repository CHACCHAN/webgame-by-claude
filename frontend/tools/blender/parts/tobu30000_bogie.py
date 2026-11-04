"""
Bogies of the Tobu 30000 series: Sumitomo SS138 (motor) and SS038 (trailer), bolsterless with monolink axle boxes.
A part module for the Blender model (train_kit.Part, the game's car frame, material prefix `tg_`).

  add_materials(m)
  bogie(part, zc, motor, facing=1) -> triangles added      one bogie centred at z = zc, rails at y = 0

Figures (Commons "File:Tobu-30000-SS138-Truck.jpg" and "File:Tobu-30000-SS038-Truck.jpg", Rs1421, CC BY-SA 3.0:
square-on side views; scale from the 2.1 m wheelbase, ≈ 324 px/m at the side-frame plane, rail head at the photos'
wheel contact line; ja.wikipedia 東武30000系電車 for the types):
- wheelbase 2.10 m (Sumitomo SS series practice; est.), wheels ∅ 0.84 m on the photos (worn; ∅ 0.86 new).
- side frame over the axle boxes (x ±1.00, 0.22 wide, est.): ends at u ±1.30 with a round end cap ∅ 0.12 at y 0.77,
  top 0.84 over the axle boxes dropping to 0.70 in the middle, bottom 0.64 at the ends slanting down to 0.40 between
  u ±0.45 (fish-belly), the cross beams' tube ends (∅ 0.15) at u ±0.21, y 0.55, a centre block u ±0.11.
- monolink axle boxes: box u ±0.15 round the axle, y 0.30–0.52, the axle spring (y 0.52–0.64) between it and the
  frame, the link from the box to a bushed pin at u ±0.45, y 0.40. Caps: round on SS138, a triangular cover with three
  bolts on SS038.
- air spring ∅ 0.66 m, y 0.76–0.92, on a pedestal on the frame's middle (bolsterless: the body sits on it directly).
- tread brake units inside each wheel, low (y 0.16–0.36); SS038's brake shoes show red. A dark box under the centre
  (u ±0.16, y 0.20–0.37: traction link / stopper, est.).
- motor bogie: two 190 kW TM-95 motors (ja.wikipedia), ∅ 0.44 hung on the inner side of each axle, point-symmetric
  with their gear units (est., hidden on the photos).
- colour: brown-grey (dirty grey paint) on both photos; wheels the same, bright treads.
"""
import math

import train_kit as K  # noqa: F401
import roof_n1000 as RN

FRAME = 'tg_frame'
DARK = 'tg_dark'
WHEEL = 'tg_wheel'
TREAD = 'tg_tread'
RUBBER = 'tg_rubber'
SHOE = 'tg_shoe'

MATERIALS = [
    (FRAME, '#77675e', 0.15, 0.72),
    (DARK, '#3b3633', 0.2, 0.7),
    (WHEEL, '#6b5f58', 0.35, 0.65),
    (TREAD, '#aaa7a1', 1.0, 0.32),
    (RUBBER, '#1a1a1b', 0.0, 0.8),
    (SHOE, '#8a3b37', 0.1, 0.75),
]

AXLE_U = 1.05
R_WHEEL = 0.42
JX = 1.00               # journal / side frame centre line
FW = 0.11               # half the side frame's width


def add_materials(m):
    for name, colour, metallic, roughness in MATERIALS:
        if name not in m.mats:
            m.add(name, colour, metallic=metallic, roughness=roughness)
    return 0


def _tris(part):
    return sum(len(f.verts) - 2 for f in part.bm.faces)


def _prism_x(mm, mat, poly, x0, x1, zc, facing):
    """polygon [(u, y)] (any winding, may be concave) extruded along x from x0 to x1"""
    P = [(zc + facing * u, y) for u, y in poly]
    area = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(P, P[1:] + P[:1]))
    if area < 0:
        P.reverse()
    A = [mm.v((x0, y, z)) for z, y in P]
    Bv = [mm.v((x1, y, z)) for z, y in P]
    xm = (x0 + x1) / 2
    cz = sum(p[0] for p in P) / len(P)
    cy = sum(p[1] for p in P) / len(P)
    mm.face(A, mat, ref=(xm, cy, cz))
    mm.face(Bv, mat, ref=(xm, cy, cz))
    n = len(P)
    for i in range(n):
        j = (i + 1) % n
        (za, ya), (zb, yb) = P[i], P[j]
        # outward normal of a CCW (z, y) polygon edge: (dy, -dz)
        nz, ny = (yb - ya), -(zb - za)
        L = math.hypot(nz, ny) or 1.0
        ref = (xm, (ya + yb) / 2 - ny / L * 0.01, (za + zb) / 2 - nz / L * 0.01)
        mm.face([A[i], A[j], Bv[j], Bv[i]], mat, ref=ref)


def _wheelset(mm, zc_axle):
    RN.cyl(mm, WHEEL, (-0.70, R_WHEEL, zc_axle), (0.70, R_WHEEL, zc_axle), 0.085, seg=10)
    for s in (-1, 1):
        prof = [(0.12, -0.03), (0.20, -0.012), (0.36, 0.0), (0.447, 0.0), (0.447, 0.012), (0.426, 0.027), (0.42, 0.045),
                (0.41, 0.125), (0.37, 0.125), (0.24, 0.095), (0.14, 0.115), (0.12, 0.15), (0.0, 0.15)]
        mats = [WHEEL, WHEEL, WHEEL, TREAD, TREAD, TREAD, TREAD, TREAD, WHEEL, WHEEL, WHEEL, WHEEL]
        RN.lathe(mm, None, (s * 0.68, R_WHEEL, zc_axle), (s, 0, 0), prof, seg=28, mats=mats)


def bogie(part, zc, motor, facing=1):
    n0 = _tris(part)
    mm = RN._Mesh(part)
    f = 1 if facing >= 0 else -1

    def Z(u):
        return zc + f * u

    def zs(u0, u1):
        return tuple(sorted((Z(u0), Z(u1))))

    for su in (-1, 1):
        _wheelset(mm, Z(su * AXLE_U))
    for sx in (-1, 1):
        x0, x1 = sorted((sx * (JX - FW), sx * (JX + FW)))
        xo = sx * (JX + FW)
        # side frame
        poly = [(-1.30, 0.64), (-0.88, 0.62), (-0.45, 0.40), (0.45, 0.40), (0.88, 0.62), (1.30, 0.64),
                (1.30, 0.84), (0.92, 0.84), (0.62, 0.72), (0.35, 0.70), (-0.35, 0.70), (-0.62, 0.72), (-0.92, 0.84),
                (-1.30, 0.84)]
        _prism_x(mm, FRAME, poly, x0, x1, zc, f)
        for su in (-1, 1):
            RN.cyl(mm, FRAME, (x0, 0.77, Z(su * 1.30)), (x1, 0.77, Z(su * 1.30)), 0.065, seg=12)
            # spring housing on the frame end, axle box, axle spring, cap, monolink
            ua = su * AXLE_U
            RN.box(mm, FRAME, x0 - 0.02, x1 + 0.02, 0.80, 0.87, *zs(ua - 0.16, ua + 0.16))
            RN.box(mm, FRAME, x0 - 0.03, x1 + 0.03, 0.30, 0.52, *zs(ua - 0.15, ua + 0.15))
            RN.box(mm, FRAME, x0 - 0.04, x1 + 0.04, 0.47, 0.52, *zs(ua - 0.18, ua + 0.18))
            pts = []
            for k in range(49):
                a = 2 * math.pi * k / 12
                pts.append((sx * JX + 0.085 * math.cos(a), 0.52 + 0.12 * k / 48, Z(ua) + 0.085 * math.sin(a)))
            RN.tube(mm, DARK, pts, 0.017, seg=5, caps=(False, False))
            xc = sx * (JX + FW + 0.03)
            if motor:
                RN.lathe(mm, FRAME, (xc, R_WHEEL, Z(ua)), (sx, 0, 0),
                         [(0.11, 0.0), (0.11, 0.035), (0.09, 0.05), (0.0, 0.05)], seg=16, cap0=False)
            else:
                tri = [(0.11 * math.cos(math.pi / 2 + 2 * math.pi * k / 3), R_WHEEL + 0.11 * math.sin(math.pi / 2 + 2 * math.pi * k / 3))
                       for k in range(3)]
                ring0 = [mm.v((xc - sx * 0.03, y, Z(ua) + u)) for u, y in tri]
                ring1 = [mm.v((xc + sx * 0.015, y * 0.9 + R_WHEEL * 0.1, Z(ua) + u * 0.9)) for u, y in tri]
                ref = (xc - sx * 0.2, R_WHEEL, Z(ua))
                mm.face(ring1, FRAME, ref=ref)
                for k in range(3):
                    mm.face([ring0[k], ring0[(k + 1) % 3], ring1[(k + 1) % 3], ring1[k]], FRAME, ref=(xc, R_WHEEL, Z(ua)))
                for u, y in tri:
                    yb, zb = R_WHEEL + (y - R_WHEEL) * 0.5, Z(ua) + u * 0.5
                    RN.cyl(mm, DARK, (xc + sx * 0.012, yb, zb), (xc + sx * 0.03, yb, zb), 0.016, seg=6)
            # monolink: from the axle box to the bushed pin on the frame
            ui = su * 0.45
            RN.obox(mm, FRAME, (sx * (JX + FW + 0.02), 0.415, Z((ua + ui) / 2)), (0, 0, 1), (0, 1, 0), (1, 0, 0),
                    abs(ua - ui) / 2, 0.028, 0.03)
            for u in (ui, su * (AXLE_U - 0.16)):
                RN.cyl(mm, DARK, (sx * (JX + FW), 0.415, Z(u)), (sx * (JX + FW + 0.06), 0.415, Z(u)), 0.045, seg=10)
            # tread brake unit inside the wheel, low
            ub = su * (AXLE_U - 0.55)
            RN.box(mm, DARK, *sorted((sx * 0.56, sx * 0.86)), 0.16, 0.36, *zs(ub - 0.13, ub + 0.13))
            us = su * (AXLE_U - 0.39)
            RN.box(mm, SHOE if not motor else DARK, *sorted((sx * 0.66, sx * 0.82)), 0.17, 0.40,
                   *zs(us - 0.02, us + 0.02))
        # cross beam tube ends and the centre block on the side frame
        for u in (-0.21, 0.21):
            RN.cyl(mm, FRAME, (sx * (JX + FW), 0.55, Z(u)), (sx * (JX + FW + 0.015), 0.55, Z(u)), 0.075, seg=14)
            RN.cyl(mm, DARK, (sx * (JX + FW + 0.015), 0.55, Z(u)), (sx * (JX + FW + 0.02), 0.55, Z(u)), 0.05, seg=10)
        RN.box(mm, FRAME, *sorted((xo, xo + sx * 0.05)), 0.43, 0.66, *zs(-0.11, 0.11))
        # air spring on its pedestal
        RN.lathe(mm, FRAME, (sx * JX, 0.0, zc), (0, 1, 0), [(0.17, 0.70), (0.17, 0.77)], seg=16, cap0=False, cap1=False)
        RN.lathe(mm, RUBBER, (sx * JX, 0.0, zc), (0, 1, 0),
                 [(0.20, 0.76), (0.30, 0.775), (0.33, 0.83), (0.31, 0.89), (0.27, 0.915), (0.0, 0.915)], seg=24,
                 cap0=False)
        RN.lathe(mm, DARK, (sx * JX, 0.0, zc), (0, 1, 0), [(0.29, 0.915), (0.29, 0.96), (0.0, 0.96)], seg=20, cap0=False)
        # levelling valve rod
        RN.cyl(mm, DARK, (sx * (JX + FW + 0.04), 0.68, Z(0.52)), (sx * (JX + FW + 0.04), 0.97, Z(0.52)), 0.01, seg=6)
    # cross beams, the box under the centre
    for u in (-0.21, 0.21):
        RN.cyl(mm, FRAME, (-JX, 0.55, Z(u)), (JX, 0.55, Z(u)), 0.075, seg=12, caps=(False, False))
    RN.box(mm, DARK, -0.35, 0.35, 0.20, 0.40, *zs(-0.16, 0.16))
    if motor:
        for su in (-1, 1):
            ua = su * AXLE_U
            sx = su            # point-symmetric: the motors sit towards opposite sides
            um = ua - su * 0.43
            RN.cyl(mm, DARK, (sx * 0.58, R_WHEEL + 0.02, Z(um)), (-sx * 0.30, R_WHEEL + 0.02, Z(um)), 0.22, seg=18)
            RN.box(mm, DARK, *sorted((-sx * 0.44, -sx * 0.62)), 0.22, 0.60, *zs(ua - su * 0.50, ua + su * 0.12))
    return _tris(part) - n0
