"""
The SU7's body shell: a closed loft of half sections along z. Each half section is a smooth curve (Catmull-Rom,
mirrored at the centre line) through eleven control points that move with z (monotone cubics over z):

  B0 (0, yb)            the floor's centre            B1 (xf, yb)        the floor's edge (W - tuck)
  B2                    the turn-under below the widest point
  P4 (W, ym)            the widest point              P3s                the upper flank (between P4 and P3)
  P3 (a3, c3)           shoulder: the front wings' crown, the doors' shoulder, the rear haunch
  P2 (a2, c2)           the belt (the side glass's lower edge) or the inner flank of a wing (bonnet, deck)
  P1 (a1, c1)           the roof rail's outer edge (the side glass's upper edge; along the windscreen the A-pillar,
                        behind the side glass the C-pillar) or the edge of the bonnet / deck centre
  P1b (a1 - rw, c1+rh)  the rail's inner edge: the edge of the windscreen, the glass roof and the rear window
  P0 (0, c0)            the centre line: roof, windscreen, bonnet, nose, rear deck

Figures: Xiaomi SU7 Max (2024), length 4,997, width 1,963, height 1,455 (the Max; the SU7 and the Pro 1,440), wheelbase 3,000 mm
(published: Xiaomi's configuration sheet as cited by en.wikipedia "Xiaomi SU7"). The tables are a first layout from
the reference photos (fitdata/su7/ref/list.json) and the points solved with their cameras (fitdata/su7/fit/ba.json:
the lamps' tips, the bonnet badge, the mirrors); the fitted shape is the FFD field on top (su7_ffd,
fitdata/su7/ffd.json).
"""
import math

import bmesh
from mathutils import Vector

import su7_kit as K

ZN, ZT = 2.48, -2.517       # the nose's tip and the tail's end (4.997; the nose from the front plate, fit/ba.json)
AXLE = 1.5                  # half the wheelbase
TRACK_F, TRACK_R = 1.693, 1.699   # (from memory of the configuration sheet; the hub caps solved at x 0.90 / 0.89)
WHEEL_R = 0.356             # 245/35 R21 (Ø 705 mm) and 265/35 R21 (Ø 719 mm): the Max's 21-inch option, as the photos' car
WHEEL_Y = 0.352             # loaded wheel centre height (fit/ba.json: 0.3518)

P = K.pchip

ZS = [-2.517, -2.49, -2.43, -2.30, -2.05, -1.75, -1.50, -1.10, -0.70, -0.30, 0.10, 0.40, 0.70, 1.00, 1.25, 1.50,
      1.80, 2.10, 2.30, 2.40, 2.45, 2.48]


def _tab(vals):
    assert len(vals) == len(ZS)
    return P(list(zip(ZS, vals)))


# centre line: tail, the short deck, rear window, the glass roof (its peak at z -0.3; 1,455 with the fitted field), windscreen (header z 0.24,
# cowl z 1.24), the bonnet falling to the badge (0, 0.76, 2.23: fit/ba.json) and the nose
C0 = _tab([0.72, 0.87, 0.985, 1.035, 1.1, 1.185, 1.27, 1.37, 1.428, 1.44, 1.415, 1.345, 1.21, 1.075, 0.972, 0.93,
           0.875, 0.81, 0.735, 0.665, 0.6, 0.5])
# P1, the rail's outer edge: 0.63 .. 0.65 off the centre line over the doors (k16, k21, k00: the far rail), out and down along the A-pillar to its
# foot (0.80, 1.0, 1.0) and along the C-pillar to the side glass's rear tip (0.775, 1.145, -1.5: k13)
A1 = _tab([0.38, 0.42, 0.50, 0.56, 0.62, 0.70, 0.775, 0.68, 0.645, 0.64, 0.63, 0.64, 0.715, 0.80, 0.60, 0.54, 0.50,
           0.44, 0.36, 0.30, 0.25, 0.22])
D1 = _tab([0.0, 0.005, 0.005, 0.004, 0.01, 0.09, 0.125, 0.085, 0.06, 0.052, 0.048, 0.05, 0.08, 0.08, 0.0, 0.005,
           0.005, 0.007, 0.003, 0.002, 0.002, 0.0])
# the rail's width and rise to its inner edge (the glass's edge): a slim rail over the doors, the C-pillar widening
# toward the haunch
RW = _tab([0.08, 0.08, 0.08, 0.08, 0.10, 0.09, 0.175, 0.075, 0.065, 0.065, 0.06, 0.06, 0.055, 0.05, 0.10, 0.10, 0.10,
           0.09, 0.08, 0.07, 0.06, 0.05])
RH = _tab([0.0, 0.0, 0.002, 0.002, 0.005, 0.055, 0.07, 0.035, 0.03, 0.03, 0.03, 0.025, 0.025, 0.02, 0.0, 0.002,
           0.002, 0.003, 0.002, 0.001, 0.001, 0.0])
# P2, the belt: 0.99 .. 1.02 along the doors, rising to meet the rail at the glass's rear tip; ahead of the cabin
# the bonnet's side, behind it the haunch's inner flank
A2 = _tab([0.50, 0.54, 0.60, 0.68, 0.74, 0.80, 0.80, 0.875, 0.90, 0.905, 0.905, 0.895, 0.875, 0.86, 0.72, 0.66, 0.62,
           0.56, 0.47, 0.40, 0.34, 0.30])
C2 = _tab([0.7, 0.85, 0.965, 1.015, 1.04, 1.06, 1.13, 1.05, 1.02, 1.005, 0.995, 0.99, 0.985, 0.99, 0.975, 0.935,
           0.878, 0.805, 0.728, 0.66, 0.59, 0.49])
# P3, the shoulder: the wings' crowns falling to the lamps' outer corners (0.89, 0.775, 1.95: fit/ba.json), the
# doors' shoulder under the belt, the rear haunch
A3 = _tab([0.60, 0.66, 0.72, 0.80, 0.88, 0.92, 0.94, 0.94, 0.935, 0.93, 0.93, 0.925, 0.915, 0.90, 0.87, 0.84, 0.80,
           0.74, 0.62, 0.52, 0.44, 0.38])
C3 = _tab([0.67, 0.8, 0.93, 0.985, 0.995, 1.0, 0.99, 0.96, 0.93, 0.92, 0.92, 0.925, 0.935, 0.96, 0.975, 0.955,
           0.895, 0.8, 0.69, 0.63, 0.565, 0.47])
# half width: 1,963 over the rear haunches, the doors drawn in between the axles
W_ = _tab([0.70, 0.76, 0.82, 0.89, 0.95, 0.975, 0.9815, 0.97, 0.955, 0.95, 0.95, 0.95, 0.955, 0.965, 0.97, 0.972,
           0.96, 0.905, 0.80, 0.70, 0.60, 0.52])
YM = _tab([0.61, 0.66, 0.7, 0.72, 0.72, 0.7, 0.7, 0.66, 0.6, 0.6, 0.6, 0.6, 0.6, 0.6, 0.62, 0.62, 0.6, 0.52, 0.46,
           0.42, 0.42, 0.43])
YB = _tab([0.52, 0.42, 0.34, 0.26, 0.2, 0.17, 0.16, 0.16, 0.16, 0.16, 0.16, 0.16, 0.16, 0.16, 0.16, 0.16, 0.16,
           0.17, 0.19, 0.215, 0.26, 0.36])
TUCK = _tab([0.10, 0.12, 0.14, 0.16, 0.17, 0.16, 0.14, 0.12, 0.10, 0.10, 0.10, 0.10, 0.10, 0.12, 0.14, 0.14, 0.14,
             0.14, 0.13, 0.12, 0.10, 0.08])


# creases at P3 (0 smooth .. 1 a corner): none, the SU7's surfaces are soft all round
SHARP3 = P([(-3.0, 0.0), (3.0, 0.0)])
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
    a1b = max(0.05, a1 - max(0.02, RW(z)))
    c1b = min(c0 - 0.0005, c1 + RH(z))
    c3 = max(c3, ym + 0.01)
    xf = max(0.02, W - TUCK(z))
    pts = [(0.0, yb), (0.5 * xf, yb), (xf, yb),
           (W - 0.25 * (W - xf), yb + 0.27 * (ym - yb)),
           (W, ym),
           (W - 0.30 * (W - a3), ym + 0.55 * (c3 - ym)),
           (a3, c3), (a2, c2), (a1, c1), (a1b, c1b), (0.0, c0)]
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
# points run the whole length, so the regions (glass, rail, sill) follow them
SEG_N = (3, 3, 3, 5, 6, 6, 6, 10, 2, 10)
ROW = [sum(SEG_N[:k]) for k in range(len(SEG_N) + 1)]      # row of control point k
NV = ROW[-1] + 1
SEG_BELT, SEG_RAIL, SEG_TOP = 7, 8, 9       # P2 -> P1 (side glass), P1 -> P1b (the rail), P1b -> P0 (the top)

# region boundaries along z (stations are put on them): the windscreen from the cowl to the header, the black header
# band the lidar sits on, the glass roof running into the rear window down to the deck; the side glass from the
# A-pillar's foot back to its rear tip, the gloss-black B-pillar between the doors' panes
Z_COWL = 1.24            # behind it every top face is glass; ahead of it WS_BASE decides
Z_WS_TOP = 0.24
Z_HEADER = 0.13
Z_DECK = -2.03           # the rear window's base
Z_DLO_REAR = -1.50       # k13: the side glass's rear tip
Z_BPILLAR = (-0.44, -0.30)
Z_MARKS = (Z_COWL, Z_WS_TOP, Z_HEADER, Z_DECK, Z_DLO_REAR, Z_BPILLAR[0], Z_BPILLAR[1])


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


# the windscreen's base (|x|, z), design frame: a first layout (cowl 1.24 at the centre, the A-pillar's foot about
# 0.95; the side glass's front tip beyond it). The shell's vertices nearest to it are moved onto it (shell()).
WS_BASE = P([(0.0, 1.24), (0.15, 1.232), (0.30, 1.20), (0.45, 1.15), (0.60, 1.08), (0.72, 1.01), (0.80, 0.95),
             (0.86, 0.84), (1.0, 0.80)])


def region(zc, seg, yc=0.0, ahead=False):
    """the material of a shell face: zc its z, yc its height, seg the stretch of the half section it lies in (0 .. 9),
    ahead: the face lies ahead of the windscreen's base (WS_BASE)"""
    if seg == SEG_TOP and not ahead:
        if zc >= Z_WS_TOP:
            return 'glass'
        if zc >= Z_HEADER:
            return 'header'
        if zc >= Z_DECK:
            return 'glass'
    if seg == SEG_BELT and Z_DLO_REAR <= zc and not ahead:
        return 'pillar' if Z_BPILLAR[0] <= zc < Z_BPILLAR[1] else 'glass'
    if seg <= 1:
        return 'under'
    if seg == 2:
        return 'sill' if -1.12 < zc < 1.12 else 'under' if yc < 0.2 else 'paint'      # k13: the black sill between the wheels
    return 'paint'


SLOT_OF = {'glass': 'glass', 'header': 'trim', 'pillar': 'trim', 'under': 'under', 'sill': 'trim', 'paint': 'paint'}


def _h(j):
    """ring index -> index along the half section (the left half mirrors the right)"""
    return j if j < NV else 2 * NV - 2 - j


def _snap_base(zs, halves):
    """move one vertex per column of the top (P2 .. P0) onto the windscreen's base: {h: station index}"""
    b = {}
    for h in range(ROW[SEG_BELT], NV):
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
            if seg < SEG_BELT or b1 is None or b2 is None:
                zc = 0.25 * sum(rows[a][b][2] for a, b in quad)
                put(i, quad, seg, seg >= SEG_BELT and zc > WS_BASE(abs(sum(rows[a][b][0] for a, b in quad) / 4)))
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
