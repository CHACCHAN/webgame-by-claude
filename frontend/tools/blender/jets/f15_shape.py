"""
The F-15's airframe as numbers: stations are metres aft of the nose tip (`d`), heights metres above the ground with the
gear down (`y`), widths metres from the centre line (`x`, + = the aircraft's left). Measured for this model on photos
with solved cameras (fitdata/f15c: a side view scaled by the published length and height, a front view, a planform
seen from below rectified by the published span and length) and checked against the published figures: length 19.43 m,
span 13.05 m, height 5.63 m, wheelbase 5.42 m, track 2.75 m, tailplane span 8.61 m, wing leading edge 45°, fin 36.6°.

Faces carry the name of their paint zone as material (`f15_paint` turns the zones into one atlas); `glass`, `beacon`
and `taxilight` stay materials of their own. Every shell is closed and may reach into its neighbours: the outer
mould line is their union.
"""
import math

import bmesh
import numpy as np

import jet_kit as K
from jet_kit import Part, Pchip

ZN = 9.33                      # the nose tip ahead of the origin (the nose wheel is 6.62 m aft of it)
WB, TRACK = 5.42, 2.75
R_MAIN, R_NOSE = 0.438, 0.279  # tyres 34.5x9.75-18 and 22x6.6-10
W_MAIN, W_NOSE = 0.248, 0.168
FIN_X = 1.72
ENG_X, ENG_Y = 0.68, 2.05
NOZ_D0, NOZ_D1 = 16.95, 17.97
STAB_PIVOT = (17.55, 2.12)     # (d, y)
LENGTH = 19.43


def at(x, y, d):
    return (x, y, ZN - d)


def spow(v, p):
    return math.copysign(abs(v) ** p, v)


def finish(part, flip=False, weld=1e-5):
    """weld, turn every shell's faces outwards (or inwards: a duct, a well)"""
    bmesh.ops.remove_doubles(part.bm, verts=part.bm.verts, dist=weld)
    bmesh.ops.recalc_face_normals(part.bm, faces=part.bm.faces)
    if flip:
        bmesh.ops.reverse_faces(part.bm, faces=part.bm.faces)
    return part


# ---------------------------------------------------------------- the forward fuselage and the spine

R_NOSE_OGIVE = Pchip([(0, 0), (0.03, 0.036), (0.1, 0.082), (0.25, 0.142), (0.5, 0.215), (0.8, 0.29), (1.16, 0.365), (1.6, 0.45), (2.09, 0.52),
                      (2.6, 0.585)])
YC_NOSE = Pchip([(0, 1.96), (0.5, 2.03), (1.16, 2.105), (2.09, 2.185), (2.6, 2.245)])
F_YB = Pchip([(2.6, 1.66), (3.0, 1.645), (3.56, 1.64), (6.6, 1.64), (7.2, 1.60), (7.9, 1.50), (8.5, 1.46), (10, 1.45), (12, 1.50), (13.2, 1.75),
              (14.2, 2.02)])
F_YT = Pchip([(2.6, 2.83), (3.0, 2.97), (3.56, 3.11), (4.56, 3.30), (5.6, 3.38), (6.8, 3.42), (7.52, 3.43), (8.2, 3.34), (9.3, 3.13),
              (10.8, 3.01), (12.0, 2.86), (13.2, 2.72), (14.2, 2.60)])
F_W = Pchip([(2.6, 0.585), (3.0, 0.62), (3.56, 0.66), (4.56, 0.70), (5.6, 0.72), (9.0, 0.72), (10, 0.80), (13.2, 0.85), (14.2, 0.6)])
F_YM = Pchip([(2.6, 2.245), (3.56, 2.24), (4.56, 2.20), (7.5, 2.15), (9, 2.12), (14.2, 2.20)])
F_EB = Pchip([(2.6, 2.0), (4.5, 2.3), (7, 2.6), (8.5, 4.0), (14.2, 4.0)])
F_ET = Pchip([(2.6, 2.0), (7.5, 2.0), (9, 2.6), (11, 3.0), (14.2, 3.0)])
FUS_END = 14.2
RADOME = 2.6
WSB, BOW, CAN_GLASS_END, CAN_END = 3.56, 4.56, 7.05, 7.52


def egg(d):
    """the section at a station: (height of the widest point, half width, depth below it, height above it, exponents)"""
    if d <= RADOME:
        r = R_NOSE_OGIVE(d)
        return YC_NOSE(d), r, r, r, 2.0, 2.0
    ym = F_YM(d)
    return ym, F_W(d), ym - F_YB(d), F_YT(d) - ym, F_EB(d), F_ET(d)


def egg_point(d, th):
    """a point of the section's right half outline: th = -90° (bottom) … +90° (top)"""
    ym, w, hb, ht, eb, et = egg(d)
    c, s = math.cos(th), math.sin(th)
    e = et if s >= 0 else eb
    return w * abs(c) ** (2 / e), ym + (ht if s >= 0 else hb) * spow(s, 2 / e)


def canopy_half_width(d, seats=1):
    """the canopy's footprint on the fuselage (half width at a station)"""
    if d <= WSB or d >= CAN_END:
        return 0.0
    if d < BOW:
        return 0.44 * math.sqrt((d - WSB) / (BOW - WSB))
    a = Pchip([(BOW, 0.44), (5.6, 0.46), (6.3, 0.455), (6.9, 0.42)])(d)
    if d > 6.9:
        a = 0.42 * math.sqrt(max(0.0, (CAN_END - d) / (CAN_END - 6.9)))
    return a


def canopy_top(d, seats=1):
    if seats == 2:
        # the two-seater's canopy keeps its height over the rear seat and comes down later
        return Pchip([(WSB, 3.11), (BOW, 3.61), (5.0, 3.70), (5.57, 3.745), (6.1, 3.77), (6.6, 3.755), (7.0, 3.69), (7.3, 3.57), (CAN_END, 3.43)])(d)
    return Pchip([(WSB, 3.11), (BOW, 3.61), (5.0, 3.70), (5.57, 3.74), (6.0, 3.73), (6.5, 3.68), (7.0, 3.58), (CAN_END, 3.43)])(d)


def canopy_foot(d, seats=1):
    """where the canopy stands on the fuselage: (half width, height, angle on the section)"""
    ym, w, hb, ht, eb, et = egg(d)
    a = canopy_half_width(d, seats)
    if a <= 1e-6:
        return 0.0, ym + ht, math.pi / 2
    th = math.acos(min(1.0, (a / w) ** (et / 2)))
    return a, ym + ht * math.sin(th) ** (2 / et), th


def tub_range(seats):
    return (4.62, 6.42) if seats == 1 else (4.62, 7.02)


TUB_FLOOR = 2.47
NL, NC = 19, 13


def fuselage(seats=1):
    """nose to the spine's end, with the cockpit's well; the canopy (glass and its solid rear) on top"""
    p = Part('fuselage')
    g = Part('canopy')
    t0, t1 = tub_range(seats)
    ds = [0.012, 0.03, 0.06, 0.1, 0.16, 0.25, 0.36, 0.5, 0.65, 0.8, 1.0, 1.2, 1.45, 1.7, 2.0, 2.3, RADOME, 2.8, 3.0, 3.2, 3.4, WSB]
    ds += [3.6, 3.66, 3.75, 3.86, t0 - 0.012, t0, 4.12, 4.26, 4.4, BOW, 4.75, 5.0, 5.3, 5.6, 5.9, 6.2, t1 if seats == 1 else 6.42, (t1 + 0.012) if seats == 1 else 6.6]
    ds += [6.75, 6.9] if seats == 1 else [6.8, t1, t1 + 0.012]
    ds += [CAN_GLASS_END, 7.15, 7.25, 7.34, 7.42, 7.48, CAN_END, 7.7, 7.9, 8.2, 8.6, 9.0, 9.4, 9.8, 10.3, 10.8, 11.4, 12.0, 12.6, 13.2, 13.7, FUS_END]
    ds = sorted(set(round(d, 4) for d in ds))
    rings, arcs = [], []
    for d in ds:
        a, yf, thf = canopy_foot(d, seats)
        half = [egg_point(d, -math.pi / 2 + (thf + math.pi / 2) * k / (NL - 1)) for k in range(NL)]
        half[0] = (0.0, half[0][1])
        half[-1] = (a, yf)
        tub = t0 <= d <= t1
        rim = min(0.035, a * 0.5)
        floor = TUB_FLOOR if tub else yf
        well = [(a - rim, yf), (a - rim, floor), (0.0, floor)]
        if a <= 1e-6:
            well = [(0.0, yf)] * 3
        right = half + well                                  # bottom centre … rim … well floor centre
        ring = [at(x, y, d) for x, y in right] + [at(-x, y, d) for x, y in right[-2:0:-1]]
        rings.append(ring)
        if WSB <= d <= CAN_END:
            yt = canopy_top(d, seats)
            arc = []
            for k in range(NC):
                t = math.pi / 2 * k / (NC - 1)
                arc.append((a * math.cos(t) ** (2 / 2.5), yf + (yt - yf) * math.sin(t) ** (2 / 2.5)))
            arcs.append((d, [at(x, y, d) for x, y in arc] + [at(-x, y, d) for x, y in arc[-2::-1]]))
    nring = len(rings[0])

    def zone(i, j):
        k = min(i, nring - 1 - i)                             # 0 = bottom centre … NL - 1 = the canopy's foot, then the well
        if k >= NL - 1:
            d = (ds[j] + ds[j + 1]) / 2
            return 'tub' if t0 - 0.02 <= d <= t1 + 0.02 else 'coaming'
        return 'radome' if ds[j + 1] <= RADOME + 1e-6 else 'fus'

    p.loft(rings, 'fus', closed=True, cap1=True, mats=zone)
    # the nose tip
    tip = at(0, YC_NOSE(0), 0)
    first = rings[0]
    for i in range(nring):
        p.face([first[i], first[(i + 1) % nring], tip], 'radome')
    finish(p)
    # the canopy: glass from the windscreen's base to the rear arch, the solid fairing behind it
    cd = [a[0] for a in arcs]
    g.loft([a[1] for a in arcs], 'glass', closed=False, mats=lambda i, j: 'glass' if cd[j + 1] <= CAN_GLASS_END + 1e-6 else 'fus')
    finish(g)
    # a closed shell's outside is found by its far end: an open one (the canopy) is checked by hand
    g.bm.normal_update()
    up = sum(f.normal.z * f.calc_area() for f in g.bm.faces)
    if up < 0:
        bmesh.ops.reverse_faces(g.bm, faces=g.bm.faces)
    return p, g


def canopy_frames(seats=1):
    """the windscreen's bow, the canopy's hoops and sill rails: bands a finger proud of the glass"""
    p = Part('frames')

    def arch(d, r, lean=0.0, n=14, mat='frame'):
        a, yf, _ = canopy_foot(d, seats)
        yt = canopy_top(d, seats)
        pts = []
        for k in range(2 * n + 1):
            t = math.pi * k / (2 * n)
            x = a * spow(math.cos(t), 2 / 2.5)
            y = yf + (yt - yf) * abs(math.sin(t)) ** (2 / 2.5)
            pts.append(at(x, y + 0.004, d + lean * (y - yf)))
        p.tube(pts, r * 0.4, mat, seg=6, cap0=True, cap1=True, ry=r, twist_ref=(0, 0, 1))

    arch(BOW, 0.034)
    arch(BOW + 0.07, 0.022)
    hoops = [6.32] if seats == 1 else [5.86, 6.02]
    for d in hoops:
        arch(d, 0.016)
    arch(CAN_GLASS_END - 0.02, 0.03)
    for s in (1, -1):
        pts = []
        for k in range(26):
            d = WSB + 0.25 + (CAN_GLASS_END - WSB - 0.25) * k / 25
            a, yf, _ = canopy_foot(d, seats)
            pts.append(at(s * (a + 0.002), yf + 0.028, d))
        p.tube(pts, 0.011, 'frame', seg=6, ry=0.03, twist_ref=(0, 1, 0))
    return finish(p)


# ---------------------------------------------------------------- lofts of superellipse sections

def section(xc, yc, a, b, e, d, n=28, et=None):
    """a ring of a superellipse section at a station (exponent e below the middle, et above)"""
    ring = []
    for k in range(n):
        t = 2 * math.pi * k / n
        c, s = math.cos(t), math.sin(t)
        ee = (et if et is not None and s > 0 else e)
        ring.append(at(xc + a * spow(c, 2 / ee), yc + b * spow(s, 2 / ee), d))
    return ring


def tables(rows):
    """columns of a table of stations as curves: rows [(d, v1, v2, …)] -> (stations, [Pchip])"""
    return [r[0] for r in rows], [Pchip([(r[0], r[k]) for r in rows]) for k in range(1, len(rows[0]))]


def stations(d0, d1, step, extra=()):
    n = max(1, round((d1 - d0) / step))
    return sorted(set([round(d0 + (d1 - d0) * k / n, 4) for k in range(n + 1)] + [round(e, 4) for e in extra if d0 < e < d1]))


NAC = [  # d, inner edge, outer edge, bottom, top, exponent
    (7.93, 0.734, 1.496, 1.424, 2.772, 14),
    (8.3, 0.73, 1.62, 1.42, 2.76, 9),
    (9.0, 0.72, 1.92, 1.425, 2.755, 6),
    (10.0, 0.64, 1.96, 1.43, 2.73, 5.5),
    (11.5, 0.50, 1.92, 1.43, 2.70, 4.5),
    (13.0, 0.30, 1.76, 1.43, 2.67, 3.2),
    (14.2, 0.16, 1.52, 1.435, 2.665, 2.6),
    (15.0, 0.11, 1.36, 1.44, 2.66, 2.3),
    (16.4, 0.08, 1.28, 1.45, 2.65, 2.0),
    (NOZ_D0, 0.095, 1.265, 1.465, 2.635, 2.0),
]


def nacelles():
    """the lower body of one side from the intake's end to the nozzle: a box that becomes the engine's round bay"""
    p = Part('nacelles')
    _, (xi, xo, yb, yt, e) = tables(NAC)
    rings = []
    for d in stations(NAC[0][0], NOZ_D0, 0.4, [r[0] for r in NAC]):
        rings.append(section((xi(d) + xo(d)) / 2, (yb(d) + yt(d)) / 2, (xo(d) - xi(d)) / 2, (yt(d) - yb(d)) / 2, e(d), d, n=32))
    p.loft(rings, 'nac', closed=True, cap0=True, cap1=True)
    p.mirror_x()
    return finish(p)


SLAB = [  # d, half width, bottom, top
    (7.75, 1.47, 2.25, 2.742), (8.4, 1.47, 2.25, 2.752), (8.85, 1.75, 2.25, 2.745), (9.5, 1.95, 2.25, 2.735), (11.0, 2.0, 2.10, 2.70),
    (13.0, 2.02, 2.0, 2.66), (14.6, 2.03, 2.0, 2.59), (15.5, 2.02, 2.0, 2.53), (16.1, 2.0, 2.0, 2.50), (17.0, 1.975, 2.0, 2.485), (17.35, 1.96, 2.02, 2.47),
]


def slab():
    """the shoulders, the deck between the fins and the shelves that carry fins and tailplanes"""
    p = Part('slab')
    _, (w, yb, yt) = tables(SLAB)
    rings = []
    ds = stations(SLAB[0][0], SLAB[-1][0], 0.45, [r[0] for r in SLAB])
    for d in ds:
        rings.append(section(0, (yb(d) + yt(d)) / 2, w(d), (yt(d) - yb(d)) / 2, 9, d, n=40))
    p.loft(rings, 'deck', closed=True, cap0=True, cap1=True)
    # the shelves' ends beside the nozzles
    for s in (1, -1):
        b = []
        for d, a, h in ((16.9, 0.345, 0.24), (17.35, 0.34, 0.235), (17.6, 0.32, 0.22), (17.8, 0.27, 0.19), (17.9, 0.17, 0.12)):
            b.append(section(s * 1.62, 2.245, a, h, 5, d, n=20))
        p.loft(b, 'metal', closed=True, cap0=True, cap1=True)
    # the pointed fairing on each shoulder that runs into the wing's leading edge
    for s in (1, -1):
        b = []
        for d, x, y, a, h in ((7.08, 1.50, 2.575, 0.004, 0.004), (7.2, 1.515, 2.572, 0.05, 0.045), (7.45, 1.54, 2.565, 0.115, 0.095), (7.9, 1.60, 2.54, 0.215, 0.155),
                              (8.4, 1.63, 2.49, 0.335, 0.185), (8.85, 1.61, 2.43, 0.42, 0.19), (9.7, 1.58, 2.41, 0.44, 0.19)):
            b.append(section(s * x, y, a, h, 2.3, d, n=18))
        p.loft(b, 'deck', closed=True, cap0=True, cap1=True)
    return finish(p)


# ---------------------------------------------------------------- the intakes

IN_XO, IN_XI = 1.50, 0.73
IN_TIP = (5.28, 2.36)          # the upper lip (the cowl hangs 11° down on the ground)
IN_TOP = (7.95, 2.776)
IN_LIP = (7.70, 1.66)          # the lower lip's upper edge
IN_BOT = 1.42
IN_BACK = 8.9


def intakes():
    """each cowl as a box with a raked mouth, and the duct inside it (returns the outside and the duct)"""
    out, duct = Part('cowls'), Part('ducts')
    th = 0.034

    def put(part, pts, mat, want):
        """a flat face that looks towards `want` (game frame)"""
        f = part.face(pts, mat, smooth=False)
        if f is None:
            return
        f.normal_update()
        if np.array(K.G(f.normal)) @ np.array(want, float) < 0:
            f.normal_flip()

    A, B = IN_TIP, IN_TOP
    C, D, E, F = (IN_TOP[0], IN_BOT), (7.80, IN_BOT), (7.70, 1.50), IN_LIP
    side = [A, B, C, D, E, F]
    # the duct's outline in (d, y): the ramp under the cowl's roof, the throat, the floor behind the lip
    A2, R1, R2, BT, BB, F2 = (5.33, 2.342), (6.9, 2.15), (8.3, 2.09), (IN_BACK, 2.07), (IN_BACK, 1.66), (7.76, 1.655)
    inner = [A2, R1, R2, BT, BB, F2]
    up, down, fwd, aft = (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)
    for s in (1, -1):
        xo, xi = s * IN_XO, s * IN_XI
        xo2, xi2 = xo - s * th, xi + s * th
        # outside: the two walls, roof, underside, the chin, the end inside the body
        put(out, [at(xo, y, d) for d, y in side], 'cowl', (s, 0, 0))
        put(out, [at(xi, y, d) for d, y in side], 'cowl', (-s, 0, 0))
        for (d0, y0), (d1, y1), want in ((A, B, up), (C, D, down), (D, E, (0, -1, 0.6)), (E, F, fwd), (B, C, aft)):
            put(out, [at(xi, y0, d0), at(xo, y0, d0), at(xo, y1, d1), at(xi, y1, d1)], 'cowl', want)
        # the mouth's edges: roof lip, side lips, the lower lip's top
        put(out, [at(xi, A[1], A[0]), at(xo, A[1], A[0]), at(xo2, A2[1], A2[0]), at(xi2, A2[1], A2[0])], 'lip', (0, -0.3, 1))
        put(out, [at(xi, F[1], F[0]), at(xo, F[1], F[0]), at(xo2, F2[1], F2[0]), at(xi2, F2[1], F2[0])], 'lip', up)
        for x, x2 in ((xo, xo2), (xi, xi2)):
            put(out, [at(x, A[1], A[0]), at(x2, A2[1], A2[0]), at(x2, F2[1], F2[0]), at(x, F[1], F[0])], 'lip', (0, -1, 0.3))
        # the duct: walls, ramp, floor, the dark end
        put(duct, [at(xo2, y, d) for d, y in inner], 'duct', (-s, 0, 0))
        put(duct, [at(xi2, y, d) for d, y in inner], 'duct', (s, 0, 0))
        for (d0, y0), (d1, y1), want, mat in ((A2, R1, down, 'duct'), (R1, R2, down, 'duct'), (R2, BT, down, 'duct'), (BT, BB, fwd, 'ductend'), (BB, F2, up, 'duct')):
            put(duct, [at(xi2, y0, d0), at(xo2, y0, d0), at(xo2, y1, d1), at(xi2, y1, d1)], mat, want)
    for part in (out, duct):
        bmesh.ops.remove_doubles(part.bm, verts=part.bm.verts, dist=1e-5)
    return out, duct


# ---------------------------------------------------------------- wings, tailplanes, fins

def foil(part, mat, sts, frame, n=10, p=0.38, mats=None):
    """
    A lifting surface through stations (u, le, te, thickness[, rise[, droop of the leading edge]]): u along the span,
    le / te as stations d, a symmetric section thickest at `p` of the chord, sharp at the trailing edge.
    `frame(u, v, d)` gives the point at span u, height v over the surface's plane, station d.
    """
    rings = []
    for st in sts:
        u, le, te, t = st[:4]
        v = st[4] if len(st) > 4 else 0.0
        droop = st[5] if len(st) > 5 else 0.0
        ch = te - le
        up, lo = [], []
        for k in range(n + 1):
            c = (1 - math.cos(math.pi * k / n)) / 2
            f = math.sqrt(max(0.0, 1 - ((p - c) / p) ** 2)) if c <= p else 1 - ((c - p) / (1 - p)) ** 1.6
            cam = -droop * max(0.0, 1 - c / 0.3) ** 2
            up.append(frame(u, v + cam + t / 2 * f, le + ch * c))
            lo.append(frame(u, v + cam - t / 2 * f, le + ch * c))
        rings.append(up + lo[-2:0:-1])
    return part.loft(rings, mat, closed=True, cap0=True, cap1=True, mats=mats)


WING_Y0, WING_DROP = 2.40, 0.03          # the wing's plane at the root, its fall per metre of span (1°, and the tanks' weight)


def wing_stations():
    le = lambda u: 6.85 + u
    te_in = 14.62
    out = []
    for u in (1.55, 2.0, 2.6, 3.3, 4.0, 4.7, 5.3, 5.9):
        te = te_in if u <= 4.0 else te_in + (u - 4.0) * (15.12 - te_in) / 1.9
        ch = te - le(u)
        tc = 0.066 - (0.066 - 0.035) * (u - 2.0) / 3.9
        out.append((u, le(u), te, ch * tc, -(u - 2.0) * WING_DROP, 0.012 * max(0.0, u - 2.0)))
    # the raked tip: from the trailing edge's corner the tip edge runs forward and out to the leading edge's corner
    for u, te in ((6.15, 14.60), (6.35, 14.19), (6.48, 13.90), (6.525, 13.74)):
        l = min(le(u), 13.42 + (u - 6.525) * 0.2) if u > 6.5 else le(u)
        out.append((u, l, te, max(0.02, (te - l) * 0.035), -(u - 2.0) * WING_DROP, 0.012 * (u - 2.0)))
    return out


def wings():
    p = Part('wings')
    for s in (1, -1):
        foil(p, 'wing', wing_stations(), lambda u, v, d: at(s * u, WING_Y0 + v, d), n=11)
    return finish(p)


STAB_Y = 2.12


def stab_stations():
    te = lambda u: 18.92 + (u - 1.88) * 0.255
    out = [
        (1.50, 17.90, 17.96, 0.02), (1.70, 17.86, 18.46, 0.06), (1.96, 17.82, te(1.96), 0.09),
        # the root at the shelf's side, the inboard leading edge back to the dog-tooth
        (1.98, 16.07, te(1.98), 0.13), (2.36, 16.50, te(2.36), 0.12), (2.735, 16.915, te(2.735), 0.11),
        (2.745, 16.60, te(2.745), 0.11), (3.3, 17.20, te(3.3), 0.09), (3.88, 17.82, 19.43, 0.07),
        (4.1, 18.06, 19.04, 0.05), (4.27, 18.24, 18.74, 0.035), (4.34, 18.34, 18.56, 0.02),
    ]
    # the photo's tailplane span came out 8.68 m: the published one is 8.61
    k = (8.61 / 2 - 1.98) / (4.34 - 1.98)
    return [((1.98 + (u - 1.98) * k) if u > 1.98 else u, le, te, t) for u, le, te, t in out]


def stabs():
    """both tailplanes (they turn together about one axis)"""
    p = Part('stab')
    for s in (1, -1):
        foil(p, 'stab', stab_stations(), lambda u, v, d: at(s * u, STAB_Y + v, d), n=9)
    return finish(p)


FIN_BASE, FIN_TOP = 2.44, 5.48


def fin_le(y):
    return 15.25 + (y - 2.48) * (17.45 - 15.25) / 3.0


def fin_te(y):
    return 18.05 + (y - 2.42) * (18.28 - 18.05) / 3.05


def fins(asym=True):
    """the two fins and what sits on their tips: `asym` = the F-15C's (the left one carries the thick pod)"""
    p = Part('fins')
    for s in (1, -1):
        sts = []
        for y in (2.30, FIN_BASE, 3.2, 4.0, 4.8, FIN_TOP):
            ch = fin_te(y) - fin_le(y)
            sts.append((y, fin_le(y), fin_te(y), ch * (0.05 - 0.012 * (y - 2.3) / 3.2)))
        foil(p, 'fin', sts, lambda u, v, d: at(s * FIN_X + v, u, d), n=9)
        # tip: the thick pod (left, C) or the slim rod with its spike; two small fairings on the trailing edge under it
        y = FIN_TOP + 0.045
        if s > 0 and asym:
            prof = [(0.0, -0.30), (0.035, -0.22), (0.075, -0.05), (0.08, 0.3), (0.08, 0.95), (0.065, 1.08), (0.0, 1.13)]
            p.revolve('fin', prof, at(s * FIN_X, y + 0.02, 17.38), axis=(0, 0, -1), seg=12)
        else:
            prof = [(0.0, -0.42), (0.012, -0.36), (0.018, -0.05), (0.045, 0.02), (0.05, 0.8), (0.035, 0.95), (0.0, 1.0)]
            p.revolve('fin', prof, at(s * FIN_X, y + 0.055, 17.42), axis=(0, 0, -1), seg=10)
        for k, yy in enumerate((FIN_TOP - 0.16, FIN_TOP - 0.36)):
            prof = [(0.0, -0.12), (0.045, -0.02), (0.05, 0.12), (0.035, 0.2), (0.0, 0.24)]
            p.revolve('fin', prof, at(s * FIN_X, yy, fin_te(yy) - 0.02), axis=(0, 0, -1), seg=10)
    return finish(p)


# ---------------------------------------------------------------- nozzles

def nozzles():
    """
    Both nozzles, open as at idle and in afterburner: the ring of divergent flaps and their links (the outer flaps,
    the "turkey feathers", are off on these aircraft), dark inside down to the flame holder.
    """
    p = Part('nozzles')
    L = NOZ_D1 - NOZ_D0
    for s in (1, -1):
        c = at(s * ENG_X, ENG_Y, NOZ_D0)
        outer = [(0.585, 0.0), (0.588, 0.10), (0.575, 0.2), (0.566, 0.45), (0.548, 0.75), (0.528, L)]
        p.revolve('nozzle', outer, c, axis=(0, 0, -1), seg=40, smooth=True)
        inner = [(0.528, L), (0.506, L), (0.50, 0.6), (0.47, 0.1), (0.45, -0.5), (0.0, -0.5)]
        p.revolve('nozzle_in', inner, c, axis=(0, 0, -1), seg=40, smooth=True, mat_of=lambda k: 'nozzle' if k == 0 else 'nozzle_in')
        # the flaps' actuating links: fifteen bars standing off the outside
        for k in range(15):
            a = 2 * math.pi * (k + 0.5) / 15
            dx, dy = math.cos(a), math.sin(a)
            pts = [at(s * ENG_X + dx * r, ENG_Y + dy * r, NOZ_D0 + z) for r, z in ((0.60, 0.12), (0.598, 0.42), (0.565, 0.86))]
            p.tube(pts, 0.014, 'nozzle', seg=4, cap0=True, cap1=True)
    return finish(p)


# ---------------------------------------------------------------- small things on the body

def details(variant):
    p = Part('details')
    j = variant['id'] == 'f15j'
    # pitot heads on the nose's sides, the angle-of-attack probes behind them
    for s in (1, -1):
        x, y = egg_point(2.95, math.radians(-12))
        p.tube([at(s * (x - 0.01), y, 2.95), at(s * (x + 0.07), y - 0.005, 2.93), at(s * (x + 0.085), y - 0.005, 2.75), at(s * (x + 0.085), y - 0.005, 2.55)],
               [0.012, 0.012, 0.011, 0.006], 'steel', seg=6)
        x, y = egg_point(3.42, math.radians(8))
        p.cylinder('steel', at(s * (x - 0.01), y, 3.42), at(s * (x + 0.08), y + 0.01, 3.42), 0.011, seg=6, r2=0.006)
    # blade antennas: two under the nose, one on the spine
    def blade(d, y, h, chord, up):
        sg = 1 if up else -1
        sts = [(0.0, d, d + chord, 0.022), (h, d + chord * 0.45, d + chord * 0.95, 0.008)]
        foil(p, 'fus', sts, lambda u, v, dd: at(v, y + sg * u, dd), n=4)

    blade(3.9, egg_point(3.9, -math.pi / 2)[1] + 0.02, 0.26, 0.26, False)
    blade(5.35, egg_point(5.35, -math.pi / 2)[1] + 0.02, 0.24, 0.24, False)
    blade(8.75, F_YT(8.75) - 0.02, 0.24, 0.24, True)
    if j:
        blade(10.2, F_YT(10.2) - 0.02, 0.16, 0.2, True)
        # the F-15J's own warning and jamming aerials: a blister under each intake, one on each shelf's end
        for s in (1, -1):
            b = []
            for d, a, h in ((8.25, 0.01, 0.01), (8.4, 0.06, 0.05), (8.7, 0.075, 0.065), (8.95, 0.05, 0.04), (9.1, 0.01, 0.01)):
                b.append(section(s * 1.12, 1.425, a, h, 2.0, d, n=10))
            p.loft(b, 'radome', closed=True, cap0=True, cap1=True)
            b = []
            for d, a, h in ((17.3, 0.07, 0.07), (17.75, 0.075, 0.075), (17.95, 0.05, 0.05), (18.05, 0.01, 0.01)):
                b.append(section(s * 1.62, 2.50, a, h, 2.0, d, n=10))
            p.loft(b, 'radome', closed=True, cap0=True, cap1=True)
    # the arresting hook under the tail, between the engines
    p.tube([at(0, 1.43, 15.3), at(0, 1.405, 16.4), at(0, 1.40, 17.2)], [0.045, 0.04, 0.035], 'steel', seg=8)
    p.box('steel', -0.05, 0.05, 1.35, 1.43, ZN - 17.4, ZN - 17.18, bevel=0.012)
    # the tail's point between the nozzles
    b = []
    for d, a, h in ((16.6, 0.2, 0.2), (17.0, 0.17, 0.2), (17.3, 0.1, 0.14), (17.45, 0.03, 0.05)):
        b.append(section(0, 2.33, a, h, 2.5, d, n=12))
    p.loft(b, 'metal', closed=True, cap0=True, cap1=True)
    # the gun's fairing at the right wing root (its muzzle is painted)
    b = []
    for d, a, h in ((8.2, 0.02, 0.02), (8.5, 0.09, 0.07), (9.2, 0.12, 0.09), (9.9, 0.05, 0.04)):
        b.append(section(-1.95, 2.62, a, h, 2.2, d, n=10))
    p.loft(b, 'deck', closed=True, cap0=True, cap1=True)
    # the inboard wing pylons (empty: no stores, no launch rails)
    for s in (1, -1):
        sts = [(0.0, 10.7, 13.6, 0.15), (0.2, 10.95, 13.55, 0.15), (0.43, 11.25, 13.45, 0.13)]
        foil(p, 'deck', sts, lambda u, v, dd: at(s * 2.95 + v, 2.32 - u, dd), n=6, p=0.3)
    return finish(p)


def lamps():
    """the anti-collision beacons (red, flashing): at each wing root's leading edge and behind the right fin's tip"""
    p = Part('beacons')
    for s in (1, -1):
        c = at(s * 2.32, WING_Y0 + 0.012, 6.85 + 2.32 - 0.012)
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=10, v_segments=6, radius=0.055)
        for v in bm.verts:
            v.co = K.B(c[0] + v.co.x, c[1] + v.co.z * 0.7, c[2] - v.co.y * 1.5)
        p.merge(bm, 'beacon', smooth=True)
    c = at(-FIN_X, FIN_TOP + 0.1, 18.43)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=10, v_segments=6, radius=0.046)
    for v in bm.verts:
        v.co = K.B(c[0] + v.co.x, c[1] + v.co.z, c[2] - v.co.y)
    p.merge(bm, 'beacon', smooth=True)
    return p


# ---------------------------------------------------------------- the cockpit

def seat(p, d, y):
    """an ejection seat: pan, back, the head box with its canopy breakers, side rails, the firing handles"""
    rec = math.radians(13)

    def back(u, v, w):                                         # u across, v up the back, w forward of it
        return at(u, y + v * math.cos(rec) + w * math.sin(rec), d + v * math.sin(rec) - w * math.cos(rec))

    def slab_(mat, u0, u1, v0, v1, w0, w1):
        c = [back(u, v, w) for w in (w0, w1) for v in (v0, v1) for u in (u0, u1)]
        for q in ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)):
            p.face([c[i] for i in q], mat, smooth=False)

    slab_('seat', -0.23, 0.23, 0.0, 0.78, 0.0, 0.09)          # the back
    slab_('seat', -0.17, 0.17, 0.74, 1.0, -0.02, 0.13)       # the head box
    slab_('cushion', -0.2, 0.2, 0.06, 0.7, 0.09, 0.13)
    slab_('cushion', -0.13, 0.13, 0.80, 0.98, 0.13, 0.16)
    for s in (1, -1):
        slab_('seat', s * 0.23, s * 0.27, -0.1, 0.9, -0.06, 0.02)   # rails
        slab_('handle', s * 0.2, s * 0.26, 0.02, 0.07, 0.36, 0.52)  # the firing handles beside the knees
    # the pan
    c0 = at(0, y - 0.02, d - 0.26)
    p.box('seat', -0.23, 0.23, y - 0.1, y + 0.0, c0[2] - 0.24, c0[2] + 0.26)
    p.box('cushion', -0.2, 0.2, y + 0.0, y + 0.05, c0[2] - 0.22, c0[2] + 0.24)


def pilot(p, d, y):
    """a pilot from the waist up: flight suit, harness, helmet with the visor down, mask and hose"""
    import bmesh as _b

    def ball(mat, c, r, seg=12, rings=8):
        bm = _b.new()
        _b.ops.create_uvsphere(bm, u_segments=seg, v_segments=rings, radius=1.0)
        for v in bm.verts:
            v.co = K.B(c[0] + v.co.x * r[0], c[1] + v.co.z * r[1], c[2] - v.co.y * r[2])
        p.merge(bm, mat, smooth=True)

    z = ZN - d
    ball('suit', (0, y + 0.36, z + 0.17), (0.2, 0.3, 0.13))                 # chest
    ball('suit', (0, y + 0.12, z + 0.2), (0.19, 0.16, 0.15))                # belly
    for s in (1, -1):
        ball('suit', (s * 0.21, y + 0.52, z + 0.16), (0.085, 0.08, 0.09))   # shoulders
        p.tube([(s * 0.23, y + 0.5, z + 0.17), (s * 0.27, y + 0.3, z + 0.24), (s * 0.2, y + 0.2, z + 0.46)], [0.062, 0.055, 0.045], 'suit', seg=8)
        ball('glove', (s * 0.19, y + 0.19, z + 0.5), (0.05, 0.045, 0.06), 8, 6)
        p.tube([(s * 0.1, y + 0.58, z + 0.2), (s * 0.09, y + 0.3, z + 0.31), (s * 0.1, y + 0.08, z + 0.33)], 0.022, 'harness', seg=4)
    p.cylinder('suit', (0, y + 0.56, z + 0.17), (0, y + 0.68, z + 0.19), 0.06, seg=8)
    ball('helmet', (0, y + 0.8, z + 0.2), (0.125, 0.135, 0.14), 14, 10)
    ball('visor', (0, y + 0.8, z + 0.262), (0.108, 0.07, 0.092), 12, 8)
    ball('mask', (0, y + 0.725, z + 0.3), (0.055, 0.06, 0.06), 8, 6)
    p.tube([(0.0, y + 0.69, z + 0.33), (0.05, y + 0.55, z + 0.34), (0.09, y + 0.38, z + 0.3)], 0.02, 'mask', seg=6)


def cockpit(seats=1, crew=True):
    """what shows through the canopy: seats and crew, the instrument panel under its hood, the head-up display's frame"""
    p = Part('cockpit')
    t0, _ = tub_range(seats)
    places = [(5.52, TUB_FLOOR + 0.22)] + ([(6.55, TUB_FLOOR + 0.22)] if seats == 2 else [])
    for d, y in places:
        seat(p, d, y)
        if crew:
            pilot(p, d, y + 0.05)
    # the front panel and its hood, side consoles, the stick
    a, yf, _ = canopy_foot(t0 + 0.05, seats)
    p.box('panel', -0.37, 0.37, TUB_FLOOR + 0.02, yf - 0.02, ZN - (t0 + 0.09), ZN - (t0 - 0.02))
    p.box('coaming', -0.385, 0.385, yf - 0.03, yf + 0.035, ZN - (t0 + 0.24), ZN - (t0 - 0.12), bevel=0.02)
    for s in (1, -1):
        p.box('panel', s * 0.27 - 0.13, s * 0.27 + 0.13, TUB_FLOOR, TUB_FLOOR + 0.3, ZN - 6.2, ZN - (t0 + 0.05))
    p.cylinder('panel', at(0, TUB_FLOOR + 0.02, 5.0), at(0, TUB_FLOOR + 0.42, 5.04), 0.018, seg=6)
    p.cylinder('handle', at(0, TUB_FLOOR + 0.42, 5.04), at(0, TUB_FLOOR + 0.54, 5.06), 0.026, seg=6)
    # the head-up display: its box on the hood, two posts and the bar that hold the combiner (no glass: the frame only)
    h0 = t0 - 0.2
    p.box('panel', -0.09, 0.09, yf + 0.02, yf + 0.1, ZN - (h0 + 0.2), ZN - (h0 - 0.04), bevel=0.01)
    for s in (1, -1):
        p.cylinder('panel', at(s * 0.085, yf + 0.09, h0 + 0.1), at(s * 0.085, yf + 0.29, h0 + 0.2), 0.008, seg=5)
    p.cylinder('panel', at(-0.09, yf + 0.29, h0 + 0.2), at(0.09, yf + 0.29, h0 + 0.2), 0.007, seg=5)
    if seats == 2:
        d2 = 5.95
        a2, yf2, _ = canopy_foot(d2, seats)
        p.box('panel', -0.3, 0.3, TUB_FLOOR + 0.25, yf2 - 0.04, ZN - d2 - 0.06, ZN - d2 + 0.02)
        p.box('coaming', -0.33, 0.33, yf2 - 0.05, yf2 + 0.0, ZN - d2 - 0.12, ZN - d2 + 0.2, bevel=0.02)
    return finish(p)


# ---------------------------------------------------------------- landing gear

NOSE_HINGE = (0.0, 1.70, WB / 2 + 0.02)
MAIN_HINGE = (0.95, 1.46, -WB / 2)
MAIN_AXLE_X = 1.22             # the strut's foot; the wheel is on its outside
STEER_Y = 0.95


def wheel(p, c, r, w, r_rim, side=1):
    """a tyre and its wheel about the X axis through c"""
    hw = w / 2
    tyre = [(r_rim, -hw * 0.78), (r_rim + (r - r_rim) * 0.45, -hw), (r - 0.035, -hw * 0.92), (r, -hw * 0.6), (r, hw * 0.6), (r - 0.035, hw * 0.92),
            (r_rim + (r - r_rim) * 0.45, hw), (r_rim, hw * 0.78)]
    p.revolve("tyre", tyre, c, axis=(1, 0, 0), seg=36)
    for sg in (1, -1):
        hub = [(r_rim, sg * hw * 0.78), (r_rim * 0.92, sg * hw * 0.55), (r_rim * 0.5, sg * hw * 0.5), (r_rim * 0.28, sg * hw * 0.75), (0.0, sg * hw * 0.75)]
        p.revolve("hub", hub, c, axis=(1, 0, 0), seg=24)


def nose_gear():
    """three parts: what hangs from the hinge and keeps its heading, what steers (with the wheel), the lamps' lenses"""
    fixed, steer, lens = Part('gear_nose'), Part('steer_nose'), Part('taxilight')
    z = WB / 2
    hy = NOSE_HINGE[1]
    fixed.cylinder('strut', (0, hy + 0.06, z), (0, STEER_Y, z), 0.062, seg=12)
    fixed.cylinder('strut', (0, STEER_Y + 0.07, z), (0, STEER_Y, z), 0.075, seg=12)
    fixed.tube([(0, 1.12, z + 0.05), (0, 1.42, z + 0.36), (0, hy + 0.04, z + 0.62)], 0.028, 'strut', seg=8)       # the drag brace
    for s in (1, -1):
        fixed.tube([(s * 0.06, 1.3, z + 0.02), (s * 0.2, hy + 0.05, z - 0.1)], 0.018, 'strut', seg=6)
    # the door on the strut's front, a narrow one behind
    fixed.box('door', -0.2, 0.2, 0.96, 1.62, z + 0.3, z + 0.318, bevel=0.004)
    fixed.box('door', 0.24, 0.255, 1.28, hy, z - 0.75, z - 0.1, bevel=0.003)
    fixed.box('door', -0.255, -0.24, 1.28, hy, z - 0.75, z - 0.1, bevel=0.003)
    # landing and taxi lamps, one over the other
    for y, r in ((1.36, 0.062), (1.19, 0.052)):
        fixed.cylinder('strut', (0, y, z + 0.03), (0, y, z + 0.115), r + 0.008, seg=12, cap=False)
        fixed.revolve('strut', [(r + 0.008, 0.03), (0.02, 0.0)], (0, y, z), axis=(0, 0, 1), seg=12)
        lens.revolve('taxilight', [(r + 0.008, 0.115), (r * 0.6, 0.128), (0.0, 0.132)], (0, y, z), axis=(0, 0, 1), seg=12)
    # the steering part: the piston, the scissors behind it, the cranked axle arm, the wheel
    steer.cylinder('chrome', (0, STEER_Y, z), (0, 0.5, z), 0.04, seg=10)
    steer.tube([(0, 0.52, z), (0.0, 0.45, z - 0.02), (0.085, 0.36, z - 0.03), (0.115, R_NOSE, z)], [0.045, 0.05, 0.045, 0.04], 'strut', seg=8)
    steer.cylinder('strut', (0.115, R_NOSE, z), (-0.03, R_NOSE, z), 0.028, seg=8)
    steer.tube([(0, 0.9, z - 0.05), (0, 0.72, z - 0.2), (0, 0.56, z - 0.06)], 0.018, 'strut', seg=6)
    wheel(steer, (0, R_NOSE, z), R_NOSE, W_NOSE, 0.14)
    for q in (fixed, steer, lens):
        finish(q)
    return fixed, steer, lens


def main_gear(s):
    """a main leg (s = +1 left): strut, braces and the strut's door on the hinge node; the wheel apart"""
    leg, wh = Part('gear_' + ('l' if s > 0 else 'r')), Part('spin_' + ('l' if s > 0 else 'r'))
    z = -WB / 2
    hx, hy = MAIN_HINGE[0], MAIN_HINGE[1]
    foot = (s * MAIN_AXLE_X, 0.46, z)
    mid = (s * (hx + (MAIN_AXLE_X - hx) * 0.55), hy + (0.46 - hy) * 0.55, z)
    leg.tube([(s * hx, hy + 0.05, z), mid], 0.075, 'strut', seg=12)
    leg.tube([mid, foot], 0.05, 'chrome', seg=10)
    leg.cylinder('strut', (s * (MAIN_AXLE_X - 0.06), R_MAIN, z), (s * (TRACK / 2 - 0.02), R_MAIN, z), 0.05, seg=10)
    leg.tube([(s * (MAIN_AXLE_X - 0.02), 0.56, z), (s * (MAIN_AXLE_X - 0.03), R_MAIN, z)], 0.055, 'strut', seg=8)
    # side brace up to the body's keel, the drag brace forward, the scissors
    leg.tube([(s * 1.1, 0.95, z), (s * 0.7, hy + 0.02, z - 0.02)], 0.03, 'strut', seg=8)
    leg.tube([(s * 1.08, 1.0, z + 0.04), (s * 1.0, hy + 0.02, z + 0.7)], 0.028, 'strut', seg=8)
    leg.tube([(s * 1.13, 0.86, z - 0.07), (s * 1.19, 0.7, z - 0.2), (s * 1.215, 0.55, z - 0.07)], 0.016, 'strut', seg=6)
    # the door carried by the strut, outside of it
    leg.box('door', min(s * 1.03, s * 1.05), max(s * 1.03, s * 1.05), 0.8, hy - 0.02, z - 0.34, z + 0.34, bevel=0.004,
            matrix=_lean(s * 1.04, hy, z, s * 0.28))
    wheel(wh, (s * TRACK / 2, R_MAIN, z), R_MAIN, W_MAIN, 0.235)
    # the brake's housing on the inside of the wheel
    wh_c = (s * (TRACK / 2 - 0.06), R_MAIN, z)
    leg.cylinder('brake', wh_c, (s * (TRACK / 2 - 0.13), R_MAIN, z), 0.17, seg=14)
    finish(leg)
    finish(wh)
    return leg, wh


def _lean(x, y, z, a):
    """a matrix that tips a box about the fore-aft line through (x, y) by `a` (the strut door follows the strut's cant)"""
    c, s = math.cos(a), math.sin(a)
    M = np.eye(4)
    M[:3, :3] = [[c, -s, 0], [s, c, 0], [0, 0, 1]]
    M[:3, 3] = np.array([x, y, z]) - M[:3, :3] @ np.array([x, y, z])
    return M


# gear retraction as the game plays it (JetInfo.gearFold): every leg swings forward about its hinge; the main legs'
# hinge lines are skewed so that the wheel ends lying flat, as the aircraft stows it
GEAR_FOLD = {
    'nose': {'axis': (1.0, 0.0, 0.0), 'angle': -math.radians(96)},
    'left': {'axis': (1.0, 1.0, -1.0), 'angle': -math.radians(120)},
    'right': {'axis': (1.0, -1.0, 1.0), 'angle': -math.radians(120)},
}
