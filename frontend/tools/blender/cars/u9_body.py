"""
The U9's body shell: a closed loft of half sections along z. Each half section is a smooth curve (Catmull-Rom,
mirrored at the centre line) through nine control points that move with z (monotone cubics over z):

  B0 (0, yb)            the floor's centre            B1 (xf, yb)        the floor's edge (W - tuck)
  B2                    the turn-under below the widest point
  P4 (W, ym)            the widest point              P3s                the upper flank (between P4 and P3)
  P3 (a3, c3)           shoulder: the front fenders' crown, the door top, the rear haunch
  P2 (a2, c2)           the belt (cabin) or the inner flank of a fender (hood, deck)
  P1 (a1, c1)           the roof rail (cabin) or the edge of the hood / deck centre
  P0 (0, c0)            the centre line: roof, windscreen, hood, nose, rear deck

Figures: Yangwang U9 (BYD), length 4,966, width 2,029 (no mirrors), height 1,295, wheelbase 2,900 mm (published).
The tables are a first layout from the reference photos (fitdata/u9/ref/list.json); the fitted shape is the FFD field
on top (u9_ffd, fitdata/u9/ffd.json).
"""
import math

import bmesh
from mathutils import Vector

import u9_kit as K

ZN, ZT = 2.466, -2.50       # the splitter's lip and the diffuser's end (4.966)
AXLE = 1.45                 # half the wheelbase
TRACK_F, TRACK_R = 1.73, 1.70
WHEEL_R = 0.363             # 275/35 R21 and 325/30 R21: about Ø 726 mm
WHEEL_Y = 0.358             # loaded wheel centre height

P = K.pchip

ZS = [-2.50, -2.47, -2.42, -2.30, -2.00, -1.70, -1.45, -1.10, -0.70, -0.30, 0.10, 0.40, 0.70, 1.00, 1.20, 1.45,
      1.80, 2.10, 2.30, 2.40, 2.44, 2.466]


def _tab(vals):
    return P(list(zip(ZS, vals)))


# centre line (roof, windscreen, hood, nose; rear deck, tail). The front (z >= 1.2): the hood's lip at y 0.6 at the
# nose (c12: the shut line; the lamps' inner tips, triangulated c12 + c00), the fenders above the hood centre and the
# lamp's outer top corner on them at (0.91, 0.8, 1.93) (triangulated)
C0 = _tab([0.97, 0.99, 1, 1.03, 1.1, 1.165, 1.205, 1.255, 1.29, 1.295, 1.29, 1.26, 1.17, 1.02, 0.95, 0.89, 0.8, 0.71,
           0.645, 0.6, 0.555, 0.46])
A1 = _tab([0.3, 0.4, 0.5, 0.56, 0.6, 0.6, 0.6, 0.58, 0.56, 0.55, 0.55, 0.55, 0.56, 0.52, 0.4, 0.33, 0.3, 0.28, 0.25,
           0.22, 0.2, 0.18])
D1 = _tab([0.0, 0.0, 0.01, 0.02, 0.03, 0.04, 0.04, 0.05, 0.05, 0.05, 0.05, 0.05, 0.04, 0.025, 0.02, 0.012, -0.015,
           -0.015, -0.006, 0.0, 0.0, 0.0])
# P2 is the belt (the side glass's lower edge; c14, rays on the door: ~0.99 fitted from z -0.4 to 0.6, 1.07 at the
# glass's rear tip), on the glass's plane carried down (the head-on outline kept). P2 / P3 ahead of the cabin (z 1.0 .. 1.8): the belt drops to the A-pillar's foot, which sits in a valley between the
# windscreen and the fender's crest (triangulated c00 + c32 + c12: the foot ~9 cm inside the old shell, the crest on the
# silhouette); the valley runs forward along the hood's side and fades toward the lamps
A2 = _tab([0.55, 0.62, 0.66, 0.72, 0.74, 0.7, 0.66, 0.62, 0.68, 0.745, 0.762, 0.778, 0.79, 0.76, 0.7, 0.66, 0.6, 0.52,
           0.45, 0.38, 0.32, 0.28])
C2 = _tab([0.93, 0.955, 0.97, 0.98, 0.99, 1.02, 1.06, 1.1, 1.04, 0.975, 0.955, 0.935, 0.915, 0.89, 0.845, 0.815, 0.765,
           0.71, 0.64, 0.58, 0.52, 0.4])
A3 = _tab([0.75, 0.82, 0.86, 0.92, 0.95, 0.93, 0.9, 0.88, 0.86, 0.86, 0.87, 0.88, 0.89, 0.9, 0.905, 0.89, 0.88, 0.86,
           0.8, 0.7, 0.6, 0.5])
C3 = _tab([0.92, 0.95, 0.96, 0.965, 0.97, 0.975, 0.975, 0.96, 0.9, 0.86, 0.85, 0.85, 0.85, 0.87, 0.92, 0.9, 0.84,
           0.66, 0.5, 0.42, 0.34, 0.25])
W_ = _tab([0.80, 0.86, 0.90, 0.95, 1.00, 1.012, 1.0145, 1.005, 0.98, 0.97, 0.965, 0.97, 0.985, 0.995, 1.0, 1.0, 0.99,
           0.96, 0.90, 0.82, 0.74, 0.66])
YM = _tab([0.55, 0.58, 0.60, 0.62, 0.66, 0.64, 0.60, 0.56, 0.50, 0.48, 0.48, 0.49, 0.50, 0.52, 0.52, 0.52, 0.50, 0.46,
           0.40, 0.33, 0.25, 0.12])
YB = _tab([0.30, 0.29, 0.27, 0.24, 0.18, 0.14, 0.13, 0.12, 0.12, 0.12, 0.12, 0.12, 0.12, 0.12, 0.12, 0.12, 0.12, 0.115,
           0.11, 0.10, 0.10, 0.10])
TUCK = _tab([0.10, 0.12, 0.14, 0.16, 0.17, 0.18, 0.18, 0.18, 0.18, 0.18, 0.18, 0.18, 0.18, 0.18, 0.18, 0.18, 0.17,
             0.16, 0.14, 0.12, 0.10, 0.08])


# creases: how sharp the section turns at P3 (0 smooth .. 1 a corner): the front fender's crest from the head lamp's
# top corner back to the A-pillar's foot (c00, c32: a hard edge in the paint's reflections); its edges are split
# (flat normals across it)
SHARP3 = P([(0.95, 0.0), (1.2, 0.8), (1.85, 0.8), (2.05, 0.0)])
SHARP_SPLIT = 0.3          # sharper than this: the crease's edges are marked sharp


def controls(z):
    """the half section's control points at z, from the floor's centre round to the top's centre"""
    yb, W, ym = YB(z), W_(z), YM(z)
    c0 = C0(z)
    a1, a2, a3 = A1(z), A2(z), A3(z)
    c1, c2, c3 = c0 - D1(z), C2(z), C3(z)
    # keep the order along x and a minimum height above the widest point
    a3 = min(a3, W - 0.02)
    a2 = min(a2, a3 - 0.02)
    a1 = min(a1, a2 - 0.02)
    c3 = max(c3, ym + 0.01)
    xf = max(0.02, W - TUCK(z))
    pts = [(0.0, yb), (0.5 * xf, yb), (xf, yb),
           (W - 0.25 * (W - xf), yb + 0.45 * (ym - yb)),
           (W, ym),
           (W - 0.30 * (W - a3), ym + 0.55 * (c3 - ym)),
           (a3, c3), (a2, c2), (a1, c1), (0.0, c0)]
    return pts


def _catmull_open(ctrl, per=10, sharp=None):
    """dense points through ctrl (2-D), Catmull-Rom, the ends reflected across x = 0 (horizontal tangents there);
    sharp {k: s}: at control point k the curve turns with a crease: the stretch arriving at k (from k - 1) runs
    into it along its own chord instead of the smooth tangent, by s; the stretch leaving k keeps the smooth tangent
    (the fender's outer side as full as before, the crease made from the inner side)"""
    a = (-ctrl[1][0], ctrl[1][1])
    b = (-ctrl[-2][0], ctrl[-2][1])
    pts = [a] + list(ctrl) + [b]
    sharp = sharp or {}
    out = []
    for i in range(1, len(pts) - 2):
        p0, p1, p2, p3 = (Vector(pts[i - 1]), Vector(pts[i]), Vector(pts[i + 1]), Vector(pts[i + 2]))
        s2 = sharp.get(i, 0.0)                                  # ctrl index of p2
        if s2 > 0:
            p3 = p3.lerp(p2 + (p2 - p1), s2)
        # centripetal parametrisation keeps tight bends from overshooting
        def tj(ti, pi, pj):
            return ti + max(1e-6, (pj - pi).length) ** 0.5
        t0 = 0.0
        t1 = tj(t0, p0, p1)
        t2 = tj(t1, p1, p2)
        t3 = tj(t2, p2, p3)
        for k in range(per):
            t = t1 + (t2 - t1) * k / per
            A1_ = (t1 - t) / (t1 - t0) * p0 + (t - t0) / (t1 - t0) * p1
            A2_ = (t2 - t) / (t2 - t1) * p1 + (t - t1) / (t2 - t1) * p2
            A3_ = (t3 - t) / (t3 - t2) * p2 + (t - t2) / (t3 - t2) * p3
            B1_ = (t2 - t) / (t2 - t0) * A1_ + (t - t0) / (t2 - t0) * A2_
            B2_ = (t3 - t) / (t3 - t1) * A2_ + (t - t1) / (t3 - t1) * A3_
            C = (t2 - t) / (t2 - t1) * B1_ + (t - t1) / (t2 - t1) * B2_
            out.append((C.x, C.y))
    out.append(tuple(ctrl[-1]))
    return out


# vertices per stretch between consecutive control points (floor centre ... top centre): the rows through the control
# points run the whole length, so the regions (glass, roof, engine cover, sill) follow them
SEG_N = (3, 3, 3, 5, 6, 6, 6, 12, 11)
ROW = [sum(SEG_N[:k]) for k in range(len(SEG_N) + 1)]      # row of control point k: 0, 3, 6, 9, 14, 20, 26, 32, 44, 55
NV = ROW[-1] + 1

# region boundaries along z (stations are put on them): the windscreen from the cowl to its top, the roof, the
# engine cover down to the deck; the side glass from the A-pillar back to its rear end (behind it the sail, paint)
Z_COWL = 1.05            # behind it every top face is glass or roof; ahead of it WS_BASE decides
Z_WS_TOP = 0.30
Z_ROOF_REAR = -0.75
Z_DECK = -2.36           # c18: the black cover reaches the deck lip
Z_DLO_REAR = -1.0        # c14: the side glass's rear tip at (0.61, 1.06, -1.02)
Z_MARKS = (Z_COWL, Z_WS_TOP, Z_ROOF_REAR, Z_DECK, Z_DLO_REAR)


def half_section(z, n=None):
    """the half section at z (floor centre -> top centre), NV points: SEG_N[k] steps between control points k and k+1,
    spaced by arc length on the curve"""
    per = 24
    dense = _catmull_open(controls(z), per=per, sharp={6: SHARP3(z)})
    dense[0] = (0.0, dense[0][1])
    dense[-1] = (0.0, dense[-1][1])
    out = []
    for k, m in enumerate(SEG_N):
        seg = dense[k * per:(k + 1) * per + 1]
        pts = _arc_resample(seg, m + 1)
        out.extend(pts if k == 0 else pts[1:])
    return out


def _arc_resample(poly, n):
    d = [0.0]
    for i in range(1, len(poly)):
        d.append(d[-1] + math.dist(poly[i], poly[i - 1]))
    out = []
    j = 0
    for k in range(n):
        s = d[-1] * k / (n - 1)
        while j < len(d) - 2 and d[j + 1] < s:
            j += 1
        L = d[j + 1] - d[j]
        t = 0.0 if L <= 0 else min(1.0, max(0.0, (s - d[j]) / L))
        a, b = poly[j], poly[j + 1]
        out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    return out


def weighted_resample(poly, n, beta=0.05):
    m = [0.0]
    for i in range(1, len(poly)):
        ds = math.dist(poly[i], poly[i - 1])
        turn = 0.0
        if 1 <= i < len(poly) - 1:
            a = math.atan2(poly[i][1] - poly[i - 1][1], poly[i][0] - poly[i - 1][0])
            b = math.atan2(poly[i + 1][1] - poly[i][1], poly[i + 1][0] - poly[i][0])
            turn = abs((b - a + math.pi) % (2 * math.pi) - math.pi)
        m.append(m[-1] + ds + beta * turn)
    total = m[-1]
    out = []
    j = 0
    for k in range(n):
        s = total * k / (n - 1)
        while j < len(m) - 2 and m[j + 1] < s:
            j += 1
        L = m[j + 1] - m[j]
        t = 0.0 if L <= 0 else min(1.0, max(0.0, (s - m[j]) / L))
        a, b = poly[j], poly[j + 1]
        out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    return out


def stations(n):
    """z of the sections, denser at the nose and the tail, with the region boundaries (Z_MARKS) among them"""
    out = []
    for k in range(n):
        s = k / (n - 1)
        u = 0.5 - 0.5 * math.cos(math.pi * s)
        w = 0.5 * u + 0.5 * s
        out.append(ZT + (ZN - ZT) * w)
    for zm in Z_MARKS:
        j = min(range(1, n - 1), key=lambda i: abs(out[i] - zm))
        out[j] = zm
    return sorted(out)


# the windscreen's base (|x|, z), design frame: triangulated from c00, c12 and c32 (the cowl line; all three within
# 1.5 px, the points within 1.2 cm of the fitted shell) and the A-pillar's foot (c00 + c32 + c12, ~0.75): the glass reaches 0.55 m further
# forward at the centre than at the pillars. The shell's vertices nearest to it are moved onto it (shell()).
WS_BASE = P([(0.0, 1.60), (0.147, 1.59), (0.292, 1.544), (0.437, 1.457), (0.598, 1.328), (0.75, 1.20), (1.0, 1.0)])


def region(zc, seg, yc=0.0, ahead=False):
    """the material of a shell face: zc its z, yc its height, seg the stretch of the half section it lies in (0 .. 8),
    ahead: the face lies ahead of the windscreen's base (WS_BASE)"""
    if seg == 8:
        if Z_WS_TOP <= zc and not ahead:
            return 'glass'
        if Z_ROOF_REAR <= zc < Z_WS_TOP:
            return 'roof'
        if Z_DECK <= zc < Z_ROOF_REAR:
            return 'cover'
    if seg == 7 and Z_DLO_REAR <= zc and not ahead:
        return 'glass'
    if seg <= 2:
        return 'under'
    if seg == 3 and -1.05 < zc < 1.05 and yc < 0.21 + 0.035 * (1.0 - zc):
        return 'sill'          # c14: the carbon sill, its top 0.21 m behind the front wheel rising to 0.28 at the rear
    return 'paint'


SLOT_OF = {'glass': 'glass', 'roof': 'trim', 'cover': 'carbon', 'under': 'under', 'sill': 'carbon', 'paint': 'paint'}


def _h(j):
    """ring index -> index along the half section (the left half mirrors the right)"""
    return j if j < NV else 2 * NV - 2 - j


def _snap_base(zs, halves):
    """move one vertex per column of the top (P2 .. P0) onto the windscreen's base: {h: station index}"""
    b = {}
    for h in range(ROW[7], NV):
        f = [zs[i] - WS_BASE(halves[i][h][0]) for i in range(len(zs))]
        i = next((k for k in range(1, len(zs) - 1) if f[k] >= 0), None)
        if i is None:
            continue
        if abs(f[i - 1]) < abs(f[i]):
            i -= 1
        z = WS_BASE(halves[i][h][0])
        for _ in range(2):
            z = WS_BASE(half_section(z)[h][0])
        lo, hi = zs[i - 1], zs[i + 1]
        if not lo + 0.25 * (zs[i] - lo) < z < hi - 0.25 * (hi - zs[i]):
            continue
        x, y = half_section(z)[h]
        halves[i][h] = (x, y, z)
        b[h] = i
    return b


def shell(name, mats, nu=120, nv=None):
    """the closed body shell as a Part, its faces in their regions (region()); ring index j < NV - 1 is the right
    half (x < 0) from the floor centre up, the left half follows from the top centre down. The windscreen's base runs
    through moved vertices (_snap_base); a quad it crosses diagonally is split along that diagonal."""
    part = K.Part(name)
    zs = stations(nu)
    halves = []
    for z in zs:
        half = half_section(z)
        if z in (zs[0], zs[-1]):
            half = [(0.0, y) for _, y in half]
        halves.append([(x, y, z) for x, y in half])
    base = _snap_base(zs, halves)
    rows = []
    for hv in halves:
        rows.append([(-x, y, z) for x, y, z in hv] + [(x, y, z) for x, y, z in reversed(hv[1:-1])])
    vs = [[part.vert(p) for p in r] for r in rows]
    n = len(rows[0])
    slots = {k: part.slot(mats[v]) for k, v in SLOT_OF.items()}

    def put(i, quad, seg, ahead):
        zc = sum(rows[a][b][2] for a, b in quad) / len(quad)
        yc = sum(rows[a][b][1] for a, b in quad) / len(quad)
        try:
            f = part.bm.faces.new([vs[a][b] for a, b in quad])
        except ValueError:
            return
        f.material_index = slots[region(zc, seg, yc, ahead)]
        f.smooth = True

    for i in range(len(rows) - 1):
        for j in range(n):
            j2 = (j + 1) % n
            # stretch of the half section: right half j in [0, NV-1), left half mirrored
            h = j if j < NV - 1 else (2 * (NV - 1) - j - 1)
            seg = max(k for k in range(len(SEG_N)) if ROW[k] <= h)
            quad = [(i, j), (i, j2), (i + 1, j2), (i + 1, j)]
            b1, b2 = base.get(_h(j)), base.get(_h(j2))
            if seg < 7 or b1 is None or b2 is None:
                zc = 0.25 * sum(rows[a][b][2] for a, b in quad)
                put(i, quad, seg, seg >= 7 and zc > WS_BASE(abs(sum(rows[a][b][0] for a, b in quad) / 4)))
            elif i + 1 <= min(b1, b2):
                put(i, quad, seg, False)
            elif i >= max(b1, b2):
                put(i, quad, seg, True)
            elif b1 == i + 1 and b2 == i:          # the base runs (i+1, j) -> (i, j2)
                put(i, [(i, j), (i, j2), (i + 1, j)], seg, False)
                put(i, [(i + 1, j), (i, j2), (i + 1, j2)], seg, True)
            elif b1 == i and b2 == i + 1:          # the base runs (i, j) -> (i+1, j2)
                put(i, [(i, j), (i, j2), (i + 1, j2)], seg, False)
                put(i, [(i, j), (i + 1, j2), (i + 1, j)], seg, True)
            else:                                   # steeper than a station per column: by the face's centre
                xc = abs(0.25 * sum(rows[a][b][0] for a, b in quad))
                zc = 0.25 * sum(rows[a][b][2] for a, b in quad)
                put(i, quad, seg, zc > WS_BASE(xc))
    for j in (ROW[6], 2 * NV - 2 - ROW[6]):
        for i in range(len(rows) - 1):
            if min(SHARP3(zs[i]), SHARP3(zs[i + 1])) > SHARP_SPLIT:
                e = part.bm.edges.get((vs[i][j], vs[i + 1][j]))
                if e is not None:
                    e.smooth = False
    bmesh.ops.remove_doubles(part.bm, verts=part.bm.verts, dist=1e-6)
    bmesh.ops.recalc_face_normals(part.bm, faces=part.bm.faces)
    part.bm.normal_update()
    return part
