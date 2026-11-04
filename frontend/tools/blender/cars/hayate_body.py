"""
Body of the Toyota Sprinter Trueno AE86 (3-door GT-APEX, late model 1985-87): the lower hull, the glasshouse, the nose
and tail faces, the bumpers.

Surfaces are lofts through measured sections: each longitudinal "row" (a feature line such as the sill, the two-tone
line, the belt crease, the hood's shut line, the roof edge) is a monotone cubic of z through key stations, and each
section is a smooth spline through the rows (broken at the creases). The glasshouse rows have their own z per column
knot, so the A, B and C pillars and the quarter window's rear edge run diagonally like the real ones.

Figures: Toyota catalogue (length 4,205 mm, width 1,625, height 1,335, wheelbase 2,400, track F 1,355 / R 1,345,
185/60R14); everything else measured on the reference photos (see hayate.py) or estimated.
"""
import math

from mathutils import Matrix, Vector

import hayate_kit as K
from hayate_kit import Table, Spline, lerp, smoothstep

# ---------------------------------------------------------------- main dimensions (game frame)
# Side profile measured on Commons "Toyota E-AE86 Sprinter Trueno GT APEX (22092207238).jpg" (long lens, true side
# view; scaled by the wheelbase, heights shifted +0.074 m so the roof is the catalogue 1,335 mm: that car is lowered).
WB = 2.40
ZF, ZR = WB / 2, -WB / 2            # axles
TRACK_F, TRACK_R = 1.355, 1.345
R_TYRE = 0.30                       # carSpecs.wheelRadius (185/60R14 is 0.289 m)
ARCH_R = 0.338                      # wheel arch opening radius
ARCH_DY = 0.012                     # arch centre above the wheel centre

Z_NOSE = 1.968                      # front end of the sheet metal (hood edge)
Z_TAIL = -2.095                     # rear end of the sheet metal (tail panel)
Z_FBUMP = 2.045                     # front bumper face (overall length 4,205)
Z_RBUMP = -2.160
Z_COWL = 0.690                      # windscreen base at the A-pillar foot
Z_HATCH = -1.975                    # hatch glass base
Z_LID = 1.648                       # rear edge of the pop-up lids

LID_BANDS = (7, 8)                  # the lids span the fender top and the hood corner (rows h7..h9)
Y_TT = 0.475                        # two-tone line along the doors (black below)

# ---------------------------------------------------------------- hull rows: (z, x, y) key stations per row
# rows from the bottom centre up the side and over the hood to the top centre; CREASES break the section spline
_E = (Z_NOSE, 1.90, 1.75, 1.45, 1.0, Z_COWL, 0.0, -1.0, -1.45, -1.75, -1.98, Z_TAIL)


def _row(xs, ys, zs=_E):
    return [(z, x, y) for z, x, y in zip(zs, xs, ys)]


HULL_ROWS = {
    'h0': _row([0.0] * 12, [0.30, 0.27, 0.23, 0.205, 0.20, 0.20, 0.20, 0.20, 0.205, 0.23, 0.27, 0.31]),
    'h1': _row([0.60, 0.63, 0.66, 0.67, 0.67, 0.67, 0.67, 0.67, 0.67, 0.66, 0.63, 0.60],
               [0.30, 0.27, 0.23, 0.20, 0.19, 0.19, 0.19, 0.19, 0.20, 0.23, 0.27, 0.31]),
    'h2': _row([0.750, 0.770, 0.780, 0.784, 0.785, 0.786, 0.786, 0.786, 0.784, 0.780, 0.765, 0.745],
               [0.32, 0.29, 0.25, 0.20, 0.182, 0.18, 0.18, 0.18, 0.20, 0.25, 0.29, 0.33]),
    'h3': _row([0.772, 0.792, 0.800, 0.802, 0.803, 0.804, 0.805, 0.805, 0.803, 0.800, 0.788, 0.770],
               [0.37, 0.33, 0.29, 0.255, 0.245, 0.245, 0.245, 0.245, 0.255, 0.29, 0.33, 0.37]),
    'h4': _row([0.782, 0.800, 0.806, 0.808, 0.809, 0.810, 0.811, 0.811, 0.809, 0.805, 0.795, 0.778],
               [0.52, 0.515, 0.505, 0.49, Y_TT, Y_TT, Y_TT, Y_TT, 0.48, 0.49, 0.50, 0.50]),
    'h5': _row([0.785, 0.803, 0.809, 0.811, 0.812, 0.812, 0.8125, 0.811, 0.806, 0.800, 0.790, 0.776],
               [0.62, 0.625, 0.635, 0.645, 0.65, 0.65, 0.65, 0.66, 0.67, 0.68, 0.69, 0.69]),
    'h6': _row([0.785, 0.802, 0.808, 0.810, 0.811, 0.811, 0.811, 0.808, 0.800, 0.795, 0.785, 0.772],
               [0.70, 0.71, 0.735, 0.775, 0.81, 0.83, 0.84, 0.855, 0.87, 0.885, 0.895, 0.895]),
    'h7': _row([0.763, 0.779, 0.792, 0.794, 0.783, 0.774, 0.774, 0.762, 0.745, 0.740, 0.732, 0.722],
               [0.745, 0.756, 0.766, 0.808, 0.866, 0.905, 0.915, 0.935, 0.952, 0.968, 0.980, 0.972]),
    'h8': _row([0.738, 0.752, 0.757, 0.758, 0.758, 0.752, 0.750, 0.740, 0.720, 0.715, 0.705, 0.692],
               [0.752, 0.765, 0.784, 0.820, 0.878, 0.917, 0.927, 0.947, 0.964, 0.980, 0.992, 0.985]),
    'h9': _row([0.36] * 12, [0.762, 0.776, 0.795, 0.833, 0.891, 0.930, 0.940, 0.960, 0.977, 0.993, 1.002, 0.995]),
    'h10': _row([0.0] * 12, [0.766, 0.779, 0.799, 0.837, 0.895, 0.934, 0.944, 0.964, 0.981, 0.997, 1.005, 0.998]),
}
HULL_ORDER = ['h0', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'h7', 'h8', 'h9', 'h10']
HULL_CREASE = {'h1', 'h4', 'h6', 'h7'}          # sharp: floor edge, fender-top / belt crease
HULL_SUB = [2, 1, 2, 2, 2, 2, 2, 1, 3, 3]       # sub-rows per band


# column knots along z (each face column lies between two of them: features fall on grid lines)
def _arch_knots(zc):
    return [zc + ARCH_R + 0.03, zc + ARCH_R * 0.5, zc, zc - ARCH_R * 0.5, zc - ARCH_R - 0.03]


HULL_KNOTS = sorted({Z_NOSE, 1.93, 1.86, Z_LID, *_arch_knots(ZF), Z_COWL, 0.40, 0.10, -0.20, -0.50, -0.80,
                     *_arch_knots(ZR), -1.72, -1.86, Z_HATCH, -2.04, Z_TAIL}, reverse=True)


class Rows:
    """longitudinal rows → (x, y) at z"""

    def __init__(self, table):
        self.t = {k: Table([(z, (x, y)) for z, x, y in v]) for k, v in table.items()}

    def __call__(self, name, z):
        return self.t[name](z)


HULL = Rows(HULL_ROWS)


def section(rows, order, creases, subs, z):
    """the half section at z: [(x, y)] through the rows (sub-rows between), and each point's band index"""
    main = [rows(n, z) for n in order]
    pts, band = [], []
    # smooth groups between creases
    groups, cur = [], [0]
    for k in range(1, len(order)):
        cur.append(k)
        if order[k] in creases or k == len(order) - 1:
            groups.append(cur)
            cur = [k]
    for g in groups:
        sp = Spline([main[k] for k in g])
        kn = sp.knots()
        for a in range(len(g) - 1):
            k = g[a]
            n = subs[k]
            for s in range(n):
                t = kn[a] + (kn[a + 1] - kn[a]) * s / n
                pts.append(sp.at(t))
                band.append(k)
    pts.append(main[-1])
    band.append(len(order) - 1)
    return pts, band


def columns(knots, step=0.07, dense=None):
    """z sample positions: every knot, and evenly between them at about `step` (or `dense`(z0, z1) → count)"""
    zs = []
    for a, b in zip(knots[:-1], knots[1:]):
        n = dense(a, b) if dense else max(1, round(abs(b - a) / step))
        for k in range(n):
            zs.append(a + (b - a) * k / n)
    zs.append(knots[-1])
    return zs


def hull_columns():
    def dense(a, b):
        mid = (a + b) / 2
        st = 0.045 if (mid > 1.75 or mid < -1.85) else 0.075
        return max(1, round(abs(b - a) / st))
    return columns(HULL_KNOTS, dense=dense)


def hull_grid():
    """rows[j][i] (j: around the section bottom → top, i: along z front → rear), band of each j, the z list"""
    zs = hull_columns()
    secs = [section(HULL, HULL_ORDER, HULL_CREASE, HULL_SUB, z) for z in zs]
    band = secs[0][1]
    nj = len(band)
    rows = [[tail_warp((secs[i][0][j][0], secs[i][0][j][1], zs[i])) for i in range(len(zs))] for j in range(nj)]
    return rows, band, zs


def tail_warp(p):
    """lean the tail panel: the top of the rear face sits further forward than its bottom (as on the photos)"""
    x, y, z = p
    w = smoothstep(-1.80, Z_TAIL, z)
    return (x, y, z + w * max(0.0, y - 0.50) * 0.20)


def hull_material(band_lo, z0, z1, xmid=None):
    """paint zone of a hull face between two columns (z0 > z1) in a band; None = no face"""
    zc = (z0 + z1) / 2
    if band_lo >= 8 and Z_HATCH < zc < Z_COWL:
        return None                         # the glasshouse sits here
    if band_lo <= 1:
        return 'interior'
    if band_lo <= 3:
        return 'accent'
    return 'paint'


def build_hull(mesh):
    """the lower body (left half, mirrored later); returns the grid (for the caps) and the lid faces' rows"""
    rows, band, zs = hull_grid()
    nj, ni = len(rows), len(zs)

    def mat(i, j):
        z0, z1 = zs[i], zs[i + 1]
        m = hull_material(band[j], z0, z1)
        # the pop-up lids are separate (they swing): leave their opening
        if band[j] in LID_BANDS and (z0 + z1) / 2 > Z_LID:
            return None
        return m
    # rows run front → rear along i and bottom → top along j: d/di × d/dj points outward on the left (+x) half
    mesh.grid(rows, mat, flip=False)
    # the character line along the whole side (h6) and the shoulder (h7) stay crisp
    for name in ('h6', 'h7'):
        j = band.index(HULL_ORDER.index(name))
        mesh.mark_sharp(rows[j])
    return rows, band, zs


def lid_grid():
    """the pop-up lid surface (left), exactly the hull's faces it replaces: rows[j][i]"""
    rows, band, zs = hull_grid()
    js = [j for j in range(len(band)) if band[j] in LID_BANDS]
    js.append(js[-1] + 1)
    iz = [i for i, z in enumerate(zs) if z >= Z_LID - 1e-9]
    return [[rows[j][i] for i in iz] for j in js]


# ---------------------------------------------------------------- the glasshouse
# centre-line profile of windscreen, roof and hatch glass: (z, y)
TOP_CENTRE = Table([(0.730, 0.926), (0.60, 1.020), (0.41, 1.140), (0.25, 1.228), (0.13, 1.284), (0.0, 1.314), (-0.22, 1.334),
                    (-0.50, 1.336), (-0.72, 1.326), (-0.90, 1.296), (-1.15, 1.223), (-1.50, 1.118), (-1.85, 1.037), (-1.975, 1.004)])
# half width of the glass area edge (windscreen edge / roof edge / hatch glass edge) and the crown (y drop at the edge)
TOP_EDGE = Table([(0.695, (0.668, 0.034)), (0.40, (0.628, 0.040)), (0.10, (0.570, 0.046)), (-0.20, (0.562, 0.050)), (-0.60, (0.556, 0.050)),
                  (-0.85, (0.540, 0.040)), (-1.20, (0.528, 0.034)), (-1.60, (0.575, 0.024)), (-1.975, (0.602, 0.008))])

Z_ATOP = 0.13           # windscreen top / A-pillar top
Z_B0, Z_B1 = -0.490, -0.590   # B-pillar (door window rear edge, quarter window front edge)
Z_CTOP = -0.85          # hatch glass top
Z_QBOT = -1.70          # quarter window rear edge at the belt
Z_QTOP = -1.64          # ... and at the top


def g_belt(z):
    """greenhouse base on the hull (= hull row h8)"""
    return HULL('h8', z)


def g_glass_bottom(z):
    x, y = HULL('h8', z)
    return x - 0.012, y + 0.012


def g_rail(z):
    """g2: the A-pillar's outer edge, the drip rail, the C-pillar's outer top edge (x, y)"""
    return RAIL(z)


RAIL = Table([(Z_COWL, (0.745, 0.918)), (0.55, (0.721, 1.022)), (0.40, (0.694, 1.122)), (0.25, (0.666, 1.204)), (Z_ATOP, (0.644, 1.258)),
              (-0.10, (0.630, 1.274)), (-0.50, (0.624, 1.284)), (-0.80, (0.618, 1.273)), (-1.00, (0.606, 1.238)),
              (-1.30, (0.615, 1.160)), (-1.60, (0.637, 1.078)), (-1.85, (0.652, 1.015)), (Z_HATCH, (0.657, 0.998))])


def g_top(z, s):
    """the windscreen / roof / hatch surface: s = 0 at the glass edge, 1 at the centre line"""
    hw, crown = TOP_EDGE(z)
    yc = TOP_CENTRE(z)
    x = hw * (1 - s)
    return x, yc - crown * (1 - s) ** 2


# rows of the greenhouse: name → fn(z) → (x, y)
G_ROWS = [
    ('g0', g_belt),
    ('g1', g_glass_bottom),
    ('g2', g_rail),
]
G_TOP_SUBS = 7          # rows across the windscreen / roof / hatch from the edge to the centre line
# knots: per row group the z of each column knot (front → rear)
#            K0 base   K1 A-top  KB0   KB1    KC          KT
G_KNOTS = {
    'g0':    [Z_COWL, Z_ATOP, Z_B0, Z_B1, Z_QBOT, Z_HATCH],
    'g1':    [Z_COWL, Z_ATOP, Z_B0, Z_B1, Z_QBOT, Z_HATCH],
    'g2':    [Z_COWL, Z_ATOP, Z_B0, Z_B1, Z_QTOP, Z_HATCH],
    'edge':  [Z_COWL + 0.005, Z_ATOP, Z_B0, Z_B1, Z_CTOP, Z_HATCH],
    'centre': [0.730, Z_ATOP - 0.01, Z_B0, Z_B1, Z_CTOP - 0.03, Z_HATCH],
}
G_COUNTS = [10, 9, 1, 11, 7]


def _knot_z(name, i_knot, t):
    k = G_KNOTS[name]
    return lerp(k[i_knot], k[i_knot + 1], t)


def greenhouse_grid():
    """rows[j][i]: j = g0, g1, g2, round-over to the edge (2), across the top (G_TOP_SUBS); i along the knots"""
    cols = []          # (knot index, t)
    for k, n in enumerate(G_COUNTS):
        for s in range(n):
            cols.append((k, s / n))
    cols.append((len(G_COUNTS) - 1, 1.0))
    rows = []
    kinds = []
    for name, fn in G_ROWS:
        row = []
        for k, t in cols:
            z = _knot_z(name, k, t)
            x, y = fn(z)
            row.append((x, y, z))
        rows.append(row)
        kinds.append(name)
    # round-over from the rail (g2) to the glass edge: a quadratic bend bulging out and up
    for s in (0.35, 0.7):
        row = []
        for k, t in cols:
            z2 = _knot_z('g2', k, t)
            ze = _knot_z('edge', k, t)
            z = lerp(z2, ze, s)
            x2, y2 = g_rail(z2)
            xe, ye = g_top(ze, 0.0)
            # bulge: the corner point (x2, ye) pulls the curve outward/up
            cx, cy = lerp(x2, xe, 0.30), lerp(y2, ye, 0.65)
            x = (1 - s) ** 2 * x2 + 2 * (1 - s) * s * cx + s * s * xe
            y = (1 - s) ** 2 * y2 + 2 * (1 - s) * s * cy + s * s * ye
            row.append((x, y, z))
        rows.append(row)
        kinds.append('round')
    for q in range(G_TOP_SUBS + 1):
        s = q / G_TOP_SUBS
        row = []
        for k, t in cols:
            sq = s
            if q == 1 and k == 4:
                sq = lerp(1 / G_TOP_SUBS, 0.02, t)     # the hatch glass frame: wide at the roof, a thin lip at the base
            z = lerp(_knot_z('edge', k, t), _knot_z('centre', k, t), sq)
            x, y = g_top(z, sq)
            row.append((x, y, z))
        rows.append(row)
        kinds.append('edge' if q == 0 else ('centre' if q == G_TOP_SUBS else 'top'))
    rows = [[tail_warp(p) for p in row] for row in rows]
    return rows, kinds, cols


def greenhouse_material(kinds, j, col):
    """material of the face from row j (to j + 1) in column `col` (knot index, t)"""
    k, _ = col
    kind = kinds[j]
    if kind == 'g0':                      # belt weatherstrip
        return 'trim'
    if kind == 'g1':                      # the side glass band
        if k in (0, 1):
            return 'glass'
        if k == 2:
            return 'trim'                 # B-pillar
        if k == 3:
            return 'glass'                # quarter window
        return 'paint'                    # the sail
    if kind in ('g2', 'round'):
        return 'paint'
    # across the top: windscreen, roof, hatch glass
    if k == 0:
        return 'glass'
    if k == 4:
        # the hatch glass sits inside a body-colour frame (the first strip in from the edge)
        return 'paint' if kind == 'edge' else 'glass'
    return 'paint'


def build_greenhouse(mesh):
    rows, kinds, cols = greenhouse_grid()

    def mat(i, j):
        return greenhouse_material(kinds, j, cols[i])
    # i runs front → rear, j bottom → top: outward normal on the left half = d/di × d/dj
    mesh.grid(rows, mat, flip=False)
    return rows, kinds, cols


# ---------------------------------------------------------------- wheel arches


def arch_centre(front):
    return (R_TYRE + ARCH_DY, ZF if front else ZR)


ARCH_P = 3.2                   # superellipse exponent of the arch outline (2 = round; the AE86's arches are squarish)


def arch_point(a, r=ARCH_R, front=True):
    """the arch outline at angle a from the top (+ towards the front): (y, z)"""
    cy, cz = arch_centre(front)
    c, s = math.cos(a), math.sin(a)
    e = 2.0 / ARCH_P
    return cy + r * math.copysign(abs(c) ** e, c), cz + r * math.copysign(abs(s) ** e, s)


def cut_arches(hull):
    """the arch openings (both sides), cut out of the mirrored hull → new Mesh"""
    cutters = []
    n = 72
    for front in (True, False):
        for s in (1, -1):
            c = K.Mesh('cut')
            ring = [arch_point(2 * math.pi * k / n, front=front) for k in range(n)]
            x0, x1 = s * 0.54, s * 1.16
            a = [(x0, y, z) for y, z in ring]
            b = [(x1, y, z) for y, z in ring]
            cy, cz = arch_centre(front)
            c.face(a, 'paint', out=(-s, 0, 0), smooth=False)
            c.face(b, 'paint', out=(s, 0, 0), smooth=False)
            for k in range(n):
                k2 = (k + 1) % n
                mid = ((a[k][1] + a[k2][1]) / 2 - cy, (a[k][2] + a[k2][2]) / 2 - cz)
                c.face([a[k], a[k2], b[k2], b[k]], 'paint', out=(0, mid[0], mid[1]), smooth=False)
            cutters.append(c)
    return K.boolean_cut(hull, cutters)


ARCH_A = math.radians(100)     # the arch spans ±100° from the top (meets the sill)


def arch_parts(liner, lip, bvh):
    """wheel-well liners and the black arch lips (left side; mirrored with the rest)"""
    for front in (True, False):
        cy, cz = arch_centre(front)
        n = 40
        angs = [-ARCH_A + 2 * ARCH_A * k / n for k in range(n + 1)]
        # liner: from the inner wall (x = 0.50) out to the body side
        xs = [0.50, 0.62, 0.74, 0.86]
        rows = [[(x, *arch_point(a, front=front)) for a in angs] for x in xs]
        # rows[j][i]: j = x, i = angle; normal d/di × d/dj points away from the axis → flip
        liner.grid(rows, 'interior', flip=True)
        poly = [(0.50, *arch_point(a, front=front)) for a in angs]
        liner.face(poly, 'interior', out=(1, 0, 0), smooth=False)
        # lip: a flared moulding round the opening, on the body surface
        prof = [(-0.006, 0.012), (0.010, 0.022), (0.034, 0.018), (0.050, 0.0)]     # (radial out, proud of the body)
        lip_rows = []
        for dr, dx in prof:
            row = []
            for a in angs:
                y, z = arch_point(a, ARCH_R + dr, front)
                h = K.hit(bvh, (1.3, y, z), (-1, 0, 0))
                xb = h[0].x if h is not None else 0.80
                row.append((xb + dx, y, z))
            lip_rows.append(row)
        # j outward (radial), i along the arch: d/di × d/dj → check against +x
        lip.grid(lip_rows, 'trim', flip=False)



# ---------------------------------------------------------------- nose and tail faces


def ring(z):
    """the hull's half section at z (warped like the hull): points bottom → top and their bands"""
    pts, band = section(HULL, HULL_ORDER, HULL_CREASE, HULL_SUB, z)
    return [(x, y) for x, y in pts], band


def _cap_rows(z_end, y_bottom, nrows, depth_fn, top_fn=None):
    """
    an end face filling the hull's end ring: rows from y_bottom up to the top edge (the hood / deck edge from the
    centre line to the h7 corner), each from x = 0 to the side; depth_fn(t, u) → z offset into the car (t: up, u: out)
    """
    pts, band = ring(z_end)
    k7 = band.index(7)
    top = list(reversed(pts[k7:]))              # centre → corner along the top edge
    side = pts[:k7 + 1]                         # bottom → corner up the side
    nu = len(top) - 1

    def side_x(y):
        for a, b in zip(side[:-1], side[1:]):
            if a[1] <= y <= b[1] or b[1] <= y <= a[1]:
                t = 0 if abs(b[1] - a[1]) < 1e-9 else (y - a[1]) / (b[1] - a[1])
                return K.lerp(a[0], b[0], t)
        return side[-1][0] if y > side[-1][1] else side[0][0]
    rows = []
    corner = top[-1]
    for k in range(nrows + 1):
        t = k / nrows
        row = []
        for i in range(nu + 1):
            u = i / nu
            tx, ty = top[i]
            y_end = K.lerp(y_bottom, corner[1], t)
            yb = y_bottom
            y = K.lerp(yb, ty, t) if i < nu else y_end
            xr = side_x(y_end)
            x = K.lerp(u * side_x(yb), tx, t) if i < nu else xr
            # keep the right end on the side line: blend the top edge's x into the side's
            if i == nu:
                x = xr
            row.append((x, y, z_end + depth_fn(t, u)))
        rows.append(row)
    return rows


NOSE_Y0 = 0.30


def build_nose(mesh):
    """the face under the hood's front edge: the hood lip (paint), the black band (trim), dark below the bumper line"""
    zt = Z_NOSE
    pts, band = ring(zt)
    ytop = pts[-1][1]

    def depth(t, u):
        # hood lip rolls down and back; below it the black band is set back 2 cm
        y_frac = t
        if y_frac > 0.97:
            return -0.004 * (1 - y_frac) / 0.03
        return -0.022 - 0.01 * u * u
    rows = _cap_rows(zt, NOSE_Y0, 24, depth)
    ny = len(rows) - 1

    def mat(i, j):
        t = (j + 0.5) / ny
        y = rows[j][i][1]
        if t > 0.96:
            return 'paint'
        if y < 0.60:
            return 'interior'
        return 'trim'
    # rows[j][i]: i outward (+x), j up: d/di × d/dj = +x × +y = +z (forward) ✓
    mesh.grid(rows, mat)


def build_tail(mesh):
    """the rear face of the hull (tail lamp band and hatch panel sit on it; dark behind the bumper)"""
    zt = Z_TAIL

    def depth(t, u):
        return 0.0
    rows = _cap_rows(zt, 0.31, 18, depth)
    rows = [[tail_warp((x, y, z)) for x, y, z in row] for row in rows]
    ny = len(rows) - 1

    def mat(i, j):
        y = rows[j][i][1]
        if y < 0.47:
            return 'interior'
        return 'trim' if y < 0.78 else 'paint'        # the full-width black tail panel round the lamps
    # facing −z: flip
    mesh.grid(rows, mat, flip=True)


# ---------------------------------------------------------------- bumpers


def sweep(mesh, path, profile, mat_fn, flip=False, front=True):
    """
    a profile swept along a plan path: path [(x, z)] (from the centre line outwards), profile [(out, y)] with `out`
    along the path's outward horizontal normal; mat_fn(k) for the profile span k
    """
    n = len(path)
    rows = []
    for out, y in profile:
        row = []
        for i in range(n):
            a = path[max(0, i - 1)]
            b = path[min(n - 1, i + 1)]
            tx, tz = b[0] - a[0], b[1] - a[1]
            l = math.hypot(tx, tz)
            # outward normal: rotate the tangent (pointing from the centre outwards/backwards) to the right
            nx, nz = (-tz / l, tx / l) if front else (tz / l, -tx / l)
            row.append((path[i][0] + nx * out, y, path[i][1] + nz * out))
        rows.append(row)
    mesh.grid(rows, lambda i, j: mat_fn(j), flip=flip)
    return rows


def _plan(front, z_face, z_end, half, r_corner, bow, n_front=10, n_corner=8, n_side=6):
    """plan path from the centre line round the corner and back along the side (x ≥ 0)"""
    s = 1 if front else -1
    pts = []
    xc = half - r_corner
    for k in range(n_front + 1):
        x = xc * k / n_front
        pts.append((x, z_face - s * bow * (x / half) ** 2))
    zc = z_face - s * bow * (xc / half) ** 2 - s * r_corner
    for k in range(1, n_corner + 1):
        a = (math.pi / 2) * k / n_corner
        pts.append((xc + r_corner * math.sin(a), zc + s * r_corner * math.cos(a)))
    z0 = pts[-1][1]
    for k in range(1, n_side + 1):
        pts.append((half, K.lerp(z0, z_end, k / n_side)))
    return pts


# front bumper: (outward offset from the plan path, y) from the top back edge, over the white bar, down the black face
F_BUMPER_PROFILE = [(-0.075, 0.670), (-0.030, 0.678), (-0.002, 0.674), (0.010, 0.662), (0.015, 0.644), (0.014, 0.620),
                    (0.008, 0.606), (-0.004, 0.597), (-0.006, 0.589), (-0.008, 0.520), (-0.010, 0.420), (-0.012, 0.330),
                    (-0.018, 0.312), (-0.034, 0.288), (-0.060, 0.272), (-0.180, 0.278)]
F_BUMPER_MATS = ['paint'] * 7 + ['trim'] + ['accent'] * 6 + ['interior']
R_BUMPER_PROFILE = [(-0.070, 0.488), (-0.030, 0.494), (-0.008, 0.489), (0.005, 0.474), (0.010, 0.440), (0.008, 0.395),
                    (0.002, 0.368), (-0.006, 0.360), (-0.008, 0.352), (-0.010, 0.320), (-0.016, 0.285), (-0.030, 0.258),
                    (-0.060, 0.248), (-0.200, 0.255)]
R_BUMPER_MATS = ['paint'] * 7 + ['trim'] + ['accent'] * 5 + ['interior']


def bumper_paths():
    zf_end = ZF + ARCH_R + 0.035
    zr_end = ZR - ARCH_R - 0.035
    front = _plan(True, Z_FBUMP, zf_end, 0.800, 0.085, 0.030)
    rear = _plan(False, Z_RBUMP, zr_end, 0.820, 0.080, 0.020)
    return front, rear


def build_bumpers(mesh):
    front, rear = bumper_paths()
    fr = sweep(mesh, front, F_BUMPER_PROFILE, lambda k: F_BUMPER_MATS[k], flip=True)
    rr = sweep(mesh, rear, R_BUMPER_PROFILE, lambda k: R_BUMPER_MATS[k], flip=False, front=False)
    # close the side ends against the arches
    for rows, s in ((fr, 1), (rr, -1)):
        ring_pts = [row[-1] for row in rows]
        mesh.face(ring_pts, 'accent', out=(0, 0, -s), smooth=False)
    return fr, rr
