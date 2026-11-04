"""
Body shell of the Nissan Skyline GT-R (BNR34): one closed surface, a uniform bicubic B-spline over a control cage
(rows along the car, 18 columns per half from the bottom centre line round the side and over the top to the top
centre line), evaluated on a parameter grid. Rows are the "stations" of the car; columns are its long lines:

  c0..c3   floor, rocker corner          c10      shoulder crease (the R34's hard line under the windows)
  c4..c9   side (sill .. shoulder)       c11      ledge above the crease
  c12      belt (glass bottom)           c13      side glass middle
  c14      roof edge / A- and C-pillar   c15..c17 roof rail, roof, centre line (hood, glass, trunk across the top)

The window edges, the cowl, the roof edges and the quarter window's slanted rear edge lie on cage rows / columns, so
the glass is a set of faces (cut out and laid back as its own mesh, see r34.py) with clean outlines. Each end of the
car closes in nested rows (contours on the nose / tail) down to a pole at the bumper centre, which the front intake
and the rear plate recess cut away.

Frame: the game's (x = car's left, y up, z forward, metres, origin on the ground between the axles).
Figures: length 4,600, width 1,785, height 1,360, wheelbase 2,665 (Nissan, BNR34 V-spec). Measured on photos
(Commons; list in the scratch dir): the side elevation (Moscow 2026 Nür 01), the tail (1999 V-Spec 1), the nose
(P&S museum 22091110195 / 274). Our estimates: the sections between the measured lines.
"""
import math

import numpy as np

NCOL = 18

# ---------------------------------------------------------------- 1-D helpers


def pchip(xs, ys):
    """monotone cubic interpolation (Fritsch-Carlson); returns f(x) for arrays, clamped at the ends"""
    xs = np.asarray(xs, float)
    ys = np.asarray(ys, float)
    h = np.diff(xs)
    d = np.diff(ys) / h
    m = np.zeros_like(ys)
    for i in range(1, len(xs) - 1):
        if d[i - 1] * d[i] <= 0:
            m[i] = 0.0
        else:
            w1, w2 = 2 * h[i] + h[i - 1], h[i] + 2 * h[i - 1]
            m[i] = (w1 + w2) / (w1 / d[i - 1] + w2 / d[i])
    m[0] = d[0]
    m[-1] = d[-1]

    def f(x):
        x = np.clip(np.asarray(x, float), xs[0], xs[-1])
        i = np.clip(np.searchsorted(xs, x) - 1, 0, len(xs) - 2)
        t = (x - xs[i]) / h[i]
        t2, t3 = t * t, t * t * t
        return ((2 * t3 - 3 * t2 + 1) * ys[i] + (t3 - 2 * t2 + t) * h[i] * m[i] + (-2 * t3 + 3 * t2) * ys[i + 1]
                + (t3 - t2) * h[i] * m[i + 1])
    return f


def bump(z, z0, z1, edge):
    """1 on [z0, z1], easing to 0 over `edge` outside"""
    a = np.clip((z - (z0 - edge)) / edge, 0, 1)
    b = np.clip(((z1 + edge) - z) / edge, 0, 1)
    s = lambda t: t * t * (3 - 2 * t)
    return s(a) * s(b)


# ---------------------------------------------------------------- the long lines (mid body, z = -2.0 .. 2.0)

# the top centre line (c17): trunk, backlight, roof, windscreen, hood
YC = pchip([-2.00, -1.80, -1.60, -1.50, -1.30, -1.05, -0.88, -0.80, -0.60, -0.30, 0.00, 0.12, 0.30, 0.50, 0.72, 0.82,
            0.90, 1.00, 1.30, 1.60, 1.80, 2.00],
           [1.008, 1.016, 1.022, 1.034, 1.128, 1.255, 1.328, 1.344, 1.358, 1.364, 1.359, 1.343, 1.262, 1.150, 1.030,
            0.984, 0.975, 0.963, 0.920, 0.872, 0.836, 0.796])

Z_COWL = 0.82          # windscreen base (centre)
Z_ROOF_F = 0.12        # windscreen top
Z_ROOF_R = -0.86       # backlight top
Z_BACK = -1.48         # backlight base
Z_AFOOT = 0.72         # A-pillar foot
Z_QUARTER = -1.05      # quarter window's rear corner at the belt
B_PILLAR = (-0.585, -0.45)   # B-pillar at the belt (rear, front edge); leans forward at the top
WHEEL_Z = 1.3325
ARCH_F = (WHEEL_Z, 0.345, 0.372)
# the rear arch is tighter and sits a little ahead of the wheel (side photo: lip 2 cm over the tyre, front edge
# 4.5 cm clear of it, the rear edge overlapping it)
ARCH_R = (-1.300, 0.335, 0.348)

# side column heights as fractions between the sill (c4) and the crease (c10)
SIDE_F = {5: 0.13, 6: 0.42, 7: 0.65, 8: 0.85, 9: 0.95}
SIDE_X = {3: 0.832, 4: 0.852, 5: 0.860, 6: 0.862, 7: 0.861, 8: 0.857, 9: 0.852, 10: 0.846}
FLARE_W = {4: 0.55, 5: 0.9, 6: 1.0, 7: 1.0, 8: 1.0, 9: 0.92, 10: 0.45}

# crease (c10) height along the car
# (forward of the cowl it is the wing's top edge: it stays high up to the headlamp's outer corner)
Y_CREASE = pchip([-2.0, -1.6, -1.2, -0.6, 0.0, 0.6, 0.9, 1.3, 1.7, 2.0],
                 [0.872, 0.878, 0.884, 0.886, 0.884, 0.880, 0.874, 0.850, 0.812, 0.778])
Y_SILL = pchip([-2.0, -1.0, 1.0, 2.0], [0.235, 0.215, 0.215, 0.235])
Y_FLOOR = pchip([-2.0, -1.4, 1.4, 2.0], [0.175, 0.155, 0.150, 0.155])


# c13 between the belt (0) and the roof edge (1): rides the quarter window's slanted rear edge from the belt at
# Z_QUARTER up to the roof edge at -0.70, along the roof edge to the B-pillar, back to mid-glass in front of it
S13 = ([-1.53, -1.30, -1.05, -0.70, -0.585, -0.45, 0.80], [0.5, 0.06, 0.0, 1.0, 1.0, 0.5, 0.5])
TRUNK_X = [0.828, 0.785, 0.722, 0.655, 0.592, 0.300, 0.0]
TRUNK_DROP = [0.075, 0.042, 0.026, 0.017, 0.011, 0.003, 0.0]
HOOD_X0 = [0.826, 0.785, 0.765, 0.740, 0.705, 0.340, 0.0]     # at the cowl: matches the windscreen's corners
HOOD_X1 = [0.832, 0.792, 0.735, 0.650, 0.520, 0.270, 0.0]     # further forward
HOOD_DROP = [0.062, 0.044, 0.034, 0.026, 0.018, 0.005, 0.0]


def _lerp(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def _top_at(zz):
    yc = float(YC(zz))
    belt_y = 0.938 + 0.018 * float(np.clip((0.6 - zz) / 1.6, 0, 1))
    s13 = float(np.interp(zz, *S13))
    glass_bulge = lambda s: 0.010 * 4 * s * (1 - s)
    z_trunk = Z_BACK - 0.05
    if zz <= z_trunk:
        return [(TRUNK_X[i], yc - TRUNK_DROP[i]) for i in range(7)]
    if zz < Z_ROOF_R:                                   # backlight + C-pillar
        t = float(np.clip((zz - z_trunk) / (Z_ROOF_R - z_trunk), 0, 1))
        y_tr = float(YC(z_trunk))
        trunk = [(TRUNK_X[i], y_tr - TRUNK_DROP[i]) for i in range(7)]
        roof_edge = (0.588, yc - 0.044)
        c11 = _lerp(trunk[0], (0.822, belt_y - 0.042), min(1.0, t / 0.35))
        c12 = _lerp(trunk[1], (0.753, belt_y), min(1.0, t / 0.35))
        e = t ** 0.85
        c14 = (trunk[3][0] + (0.588 - trunk[3][0]) * t, trunk[3][1] + (roof_edge[1] - trunk[3][1]) * e)
        c15 = (0.592 - 0.042 * t, yc - 0.030 + 0.008 * t)
        c14 = (c14[0], max(c14[1], c15[1] - 0.05))
        c13 = _lerp(c12, c14, s13)
        c13 = (c13[0] + glass_bulge(s13), c13[1])
        c16 = (0.300 - 0.020 * t, yc - 0.008 + 0.002 * t)
        return [c11, c12, c13, c14, c15, c16, (0.0, yc)]
    if zz <= Z_ROOF_F:                                  # roof and side glass
        c12 = (0.753, belt_y)
        c14 = (0.588, yc - 0.044)
        c13 = _lerp(c12, c14, s13)
        c13 = (c13[0] + glass_bulge(s13), c13[1])
        return [(0.822, belt_y - 0.042), c12, c13, c14, (0.550, yc - 0.022), (0.280, yc - 0.006), (0.0, yc)]
    z_hood = Z_COWL + 0.08
    if zz < z_hood:                                     # windscreen, A-pillar, side glass narrowing to the foot
        wt = float(np.clip((zz - Z_ROOF_F) / (Z_COWL - Z_ROOF_F), 0, 1))
        c15 = (0.550 + (0.705 - 0.550) * wt, yc - 0.022 - 0.008 * wt)
        c16 = (0.280 + 0.060 * wt, yc - 0.006 - 0.004 * wt)
        hood = [(HOOD_X0[i], float(YC(z_hood)) - HOOD_DROP[i]) for i in range(7)]
        if zz <= Z_AFOOT:
            t = float(np.clip((zz - Z_ROOF_F) / (Z_AFOOT - Z_ROOF_F), 0, 1))
            c12 = (0.753 + 0.004 * t, belt_y)
            c14 = (0.588 + (0.740 - 0.588) * t, (float(YC(Z_ROOF_F)) - 0.044) * (1 - t) + 0.946 * t)
            c13 = _lerp(c12, c14, 0.5)
            c13 = (c13[0] + glass_bulge(0.5) * (1 - t), c13[1])
            c11 = (0.822, belt_y - 0.042)
        else:
            s = float(np.clip((zz - Z_AFOOT) / (z_hood - Z_AFOOT), 0, 1))
            c11 = _lerp((0.822, belt_y - 0.042), hood[0], s)
            c12 = _lerp((0.757, belt_y), hood[1], s)
            c13 = _lerp((0.7485, 0.942), hood[2], s)
            c14 = _lerp((0.740, 0.946), hood[3], s)
        if zz > Z_COWL:
            s2 = float(np.clip((zz - Z_COWL) / 0.08, 0, 1))
            c15 = _lerp(c15, hood[4], s2)
            c16 = _lerp(c16, hood[5], s2)
        return [c11, c12, c13, c14, c15, c16, (0.0, yc)]
    k = float(np.clip((zz - 0.95) / 0.5, 0, 1))
    k = k * k * (3 - 2 * k)
    flat = 1.0 - 0.55 * float(np.clip((zz - 1.2) / 0.8, 0, 1))      # the bonnet flattens towards the nose
    pts = [(HOOD_X0[i] + (HOOD_X1[i] - HOOD_X0[i]) * k, yc - HOOD_DROP[i] * flat) for i in range(7)]
    lift = 0.022 - 0.010 * float(np.clip((zz - 1.2) / 0.8, 0, 1))
    pts[0] = (pts[0][0], max(pts[0][1], float(Y_CREASE(zz)) + lift))
    return pts


def top_columns(z):
    """(x, y) of c11..c17 at stations z (array) for the mid body: trunk / backlight + C-pillar / roof + side glass /
    windscreen + A-pillar / hood"""
    return np.array([_top_at(float(zz)) for zz in np.atleast_1d(z)])


def flare_at(zz):
    """the GT-R's blistered wings: out by ~3.5 cm front and rear, stepping out right behind / ahead of the doors"""
    ramp = lambda t: float(np.clip(t, 0.0, 1.0)) ** 2 * (3 - 2 * float(np.clip(t, 0.0, 1.0)))
    front = 0.030 * ramp((zz - 0.745) / 0.05) * (1 - 0.35 * ramp((zz - 1.75) / 0.25))
    rear = 0.034 * ramp((-0.635 - zz) / 0.05) * (1 - 0.45 * ramp((-1.70 - zz) / 0.30))
    return front + rear


def mid_row(z, shear=None):
    """one cage row at station z (18 × (x, y, z)); shear: {column: dz} moves single columns along the car"""
    zc = np.full(NCOL, float(z))
    if shear:
        for c, dz in shear.items():
            zc[c] += dz
    row = np.zeros((NCOL, 3))
    for c in range(NCOL):
        zz = zc[c]
        floor, sill, crease = float(Y_FLOOR(zz)), float(Y_SILL(zz)), float(Y_CREASE(zz))
        flare = flare_at(zz)
        taper = 0.012 * float(np.clip((abs(zz) - 1.8) / 0.2, 0, 1))
        # behind the rear arch the bumper (its own piece) covers the lower sides: the shell steps in under it
        inset = 0.014 * float(np.clip((-1.62 - zz) / 0.08, 0, 1)) * {4: 1.0, 5: 1.0, 6: 1.0, 7: 0.45}.get(c, 0.0)
        if c == 0:
            p = (0.0, floor)
        elif c == 1:
            p = (0.42, floor)
        elif c == 2:
            p = (0.71, floor + 0.004)
        elif c == 3:
            p = (SIDE_X[3] - taper - 0.014 * float(np.clip((-1.62 - zz) / 0.08, 0, 1)), float(Y_SILL(zz)) - 0.022)
        elif c <= 10:
            if c == 4:
                y = sill
            elif c == 10:
                y = crease
            else:
                y = sill + SIDE_F[c] * (crease - sill)
            x = SIDE_X[c] - taper + flare * FLARE_W.get(c, 0.0) - inset
            p = (x, y)
        else:
            tc = top_columns([zz])[0]
            p = tuple(tc[c - 11])
        row[c] = (p[0], p[1], zz)
    return row


# ---------------------------------------------------------------- the ends


def _transform(base, top=None, hi=None, lo=None, bot=None, plan=None):
    """
    An end row made from a mid row: each group of columns gets its own height range, width scale and station.
      top  (c11..c17): dict(y=centre height, z=, sx=, crown=k)  heights keep the crown scaled by k
      hi   (c8..c10):  dict(sx=, y0=, y1=, z=)
      lo   (c4..c7):   dict(sx=, y0=, y1=, z=)
      bot  (c0..c3):   dict(y=, z=, sx=)
      plan: (depth, half width): the face recedes by depth·(x/hw)² towards the corners
    """
    row = base.copy()
    if top:
        yc0 = base[17, 1]
        for c in range(11, 18):
            row[c, 0] = base[c, 0] * top.get('sx', 1.0)
            row[c, 1] = top['y'] + (base[c, 1] - yc0) * top.get('crown', 1.0)
            row[c, 2] = top['z']
    for grp, cols in ((hi, (8, 9, 10)), (lo, (4, 5, 6, 7))):
        if not grp:
            continue
        ys = base[list(cols), 1]
        y0, y1 = ys.min(), ys.max()
        for c in cols:
            f = (base[c, 1] - y0) / max(1e-6, (y1 - y0))
            row[c, 0] = base[c, 0] * grp.get('sx', 1.0)
            if 'y0' in grp:
                row[c, 1] = grp['y0'] + f * (grp['y1'] - grp['y0'])
            row[c, 2] = grp['z']
    if bot:
        for c in range(0, 4):
            row[c, 0] = base[c, 0] * bot.get('sx', 1.0)
            row[c, 1] = bot['y'] + (base[c, 1] - base[0, 1])
            row[c, 2] = bot['z']
    if plan:
        depth, hw = plan
        sign = 1.0 if row[17, 2] > 0 else -1.0
        for c in range(NCOL):
            row[c, 2] -= sign * depth * (row[c, 0] / hw) ** 2
    return row


def face_ring(W, yb, yt, rb, rt, zf, centre=None, k=1.0):
    """
    A closed half ring (18 points) round a rounded rectangle x <= W, yb <= y <= yt (corner radii rb at the bottom, rt
    at the top), laid on the height field z = zf(x, y); scaled by k towards `centre` (x = 0, y) for the inner rings.
    Columns keep their roles: c0..c3 bottom (c3 in the lower corner), c4..c9 side, c10 upper corner, c11..c17 top.
    """
    pts = []
    for f in (0.0, 0.5, 0.86):
        pts.append(((W - rb) * f, yb))
    a = math.radians(45)
    pts.append((W - rb + rb * math.sin(a), yb + rb - rb * math.cos(a)))
    for f in (0.0, 0.14, 0.36, 0.58, 0.80, 0.95):
        pts.append((W, yb + rb + (yt - rt - yb - rb) * f))
    pts.append((W - rt + rt * math.cos(a), yt - rt + rt * math.sin(a)))
    for f in (0.0, 0.08, 0.2, 0.36, 0.56, 0.78, 1.0):
        pts.append(((W - rt) * (1 - f), yt))
    pts = np.array(pts)
    if centre is not None:
        pts[:, 1] = centre + (pts[:, 1] - centre) * k
        pts[:, 0] *= k
    z = np.array([zf(x, y) for x, y in pts])
    return np.column_stack([pts, z])


# the nose seen from the side (x = 0): face position z by height; the face recedes towards the corners in plan
# tall and blunt: the bumper face is nearly vertical up to its crease at y 0.60, the lamp / grille band above it
# leans back a little up to the bonnet's crisp leading edge at y 0.78
# the bumper's upper band (y 0.47 .. 0.58) is a brow standing ~2 cm proud of the intake band below it
_NOSE = pchip([0.13, 0.155, 0.18, 0.25, 0.32, 0.40, 0.47, 0.53, 0.575, 0.61, 0.68, 0.73, 0.762],
              [2.262, 2.276, 2.284, 2.284, 2.282, 2.288, 2.302, 2.302, 2.290, 2.248, 2.222, 2.200, 2.186])


def nose_z(x, y):
    t = min(abs(x) / 0.85, 1.0)
    return float(_NOSE(y)) - 0.028 * t ** 2 - 0.066 * t ** 6


def lamp_face_z(x, y):
    """the tail-lamp panel: vertical, receding a little towards its corners"""
    return -2.122 + 0.032 * (x / 0.84) ** 2


def front_rows():
    b = mid_row(2.0)
    rows = []
    rows.append(_transform(b, top=dict(y=0.770, z=2.10), hi=dict(sx=0.997, z=2.09), lo=dict(sx=0.997, z=2.10),
                           bot=dict(y=0.152, z=2.10), plan=(0.015, 0.86)))
    rows.append(_transform(b, top=dict(y=0.768, z=2.165, sx=0.99), hi=dict(sx=0.99, y0=0.58, y1=0.768, z=2.16),
                           lo=dict(sx=0.993, z=2.19), bot=dict(y=0.150, z=2.19), plan=(0.035, 0.86)))
    centre = 0.40
    for k in (1.0, 0.95, 0.75, 0.50, 0.25):
        rows.append(face_ring(0.85, 0.155, 0.760, 0.035, 0.018, nose_z, centre=centre, k=k))
    rows.append(np.tile(np.array([0.0, centre, nose_z(0.0, centre)]), (NCOL, 1)))
    return rows


def rear_rows():
    b = mid_row(-2.0)
    rows = []
    rows.append(_transform(b, top=dict(y=1.003, z=-2.065), hi=dict(sx=0.993, z=-2.05), lo=dict(sx=0.996, z=-2.05),
                           bot=dict(y=0.176, z=-2.06), plan=(0.015, 0.86)))
    rows.append(_transform(b, top=dict(y=0.999, z=-2.112, sx=0.99), hi=dict(sx=0.985, y0=0.70, y1=0.90, z=-2.09),
                           lo=dict(sx=0.98, y0=0.30, y1=0.62, z=-2.08), bot=dict(y=0.20, z=-2.10), plan=(0.035, 0.86)))
    centre = 0.46
    for k in (1.0, 0.95, 0.72, 0.46, 0.22):
        rows.append(face_ring(0.81, 0.30, 0.978, 0.05, 0.014, lamp_face_z, centre=centre, k=k))
    rows.append(np.tile(np.array([0.0, centre, lamp_face_z(0.0, centre)]), (NCOL, 1)))
    return rows[::-1]


def _cabin_shear(z):
    """the B-pillar leans forward at the top: its rows move the upper side-glass columns forward"""
    lean = {-0.585: 0.06, -0.45: 0.03}.get(round(z, 3), 0.0)
    return {13: lean * 0.5, 14: lean, 15: lean * 0.6}


MID_Z = [-2.0, -1.90, -1.80, -1.70, -1.60, -1.53, -1.48, -1.40, -1.30, -1.18, -1.05, -0.95, -0.86, -0.80, -0.70,
         -0.64, -0.585, -0.45, -0.30, -0.12, 0.04, 0.12, 0.22, 0.34, 0.46, 0.58, 0.66, 0.72, 0.76, 0.79, 0.82, 0.90, 1.00, 1.12, 1.24,
         1.36, 1.48, 1.60, 1.72, 1.84, 1.93, 2.0]


def cage():
    """the control grid (R × 18 × 3) and the indices of the named rows"""
    rows = rear_rows()
    named = {}
    for z in MID_Z:
        if -1.32 < z < -0.40:
            r = mid_row(z, _cabin_shear(z))
        else:
            r = mid_row(z)
        named[round(z, 3)] = len(rows)
        rows.append(r)
    rows += front_rows()
    return np.array(rows), named


# ---------------------------------------------------------------- B-spline surface


def _basis(t):
    t2, t3 = t * t, t * t * t
    return np.stack([(1 - t) ** 3, 3 * t3 - 6 * t2 + 4, -3 * t3 + 3 * t2 + 3 * t + 1, t3], axis=-1) / 6.0


def _extend(P):
    """phantom rows (reflected: the surface ends on the end rows) and mirrored columns (x → -x at both centre lines)"""
    R = P.shape[0]
    top = 2 * P[:1] - P[1:2]
    bot = 2 * P[-1:] - P[-2:-1]
    P = np.concatenate([top, P, bot], axis=0)
    m0 = P[:, 1:2].copy()
    m0[..., 0] *= -1
    m1 = P[:, -2:-1].copy()
    m1[..., 0] *= -1
    return np.concatenate([m0, P, m1], axis=1)


def evaluate(P, us, vs):
    """surface points at parameters us (rows, 0..R-1) × vs (columns, 0..17)"""
    E = _extend(P)
    R, N = P.shape[:2]
    us = np.asarray(us, float)
    vs = np.asarray(vs, float)
    iu = np.clip(np.floor(us).astype(int), 0, R - 2)
    tu = us - iu
    iv = np.clip(np.floor(vs).astype(int), 0, N - 2)
    tv = vs - iv
    bu = _basis(tu)       # (nu, 4)
    bv = _basis(tv)       # (nv, 4)
    out = np.zeros((len(us), len(vs), 3))
    for a in range(4):
        for b in range(4):
            # E index: row iu + a (phantom offset 1 → iu - 1 + a + 1), column iv + b
            out += bu[:, a, None, None] * bv[None, :, b, None] * E[iu + a][:, iv + b]
    return out


def params(P, named, row_density=0.045, col_subdiv=None):
    """sample parameters: each row interval split by its length; each column interval by col_subdiv[c]"""
    R = P.shape[0]
    us = []
    for i in range(R - 1):
        d = np.linalg.norm(P[i + 1] - P[i], axis=1).max()
        n = int(max(1, min(6, round(d / row_density))))
        for k in range(n):
            us.append(i + k / n)
    us.append(R - 1)
    if col_subdiv is None:
        col_subdiv = [2, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 3, 3, 2, 2, 3, 2]
    vs = []
    for c in range(NCOL - 1):
        n = col_subdiv[c]
        for k in range(n):
            vs.append(c + k / n)
    vs.append(NCOL - 1)
    return np.array(us), np.array(vs)


# ---------------------------------------------------------------- the rear bumper (its own closed piece)

def side_x(z, c=6):
    """the shell's side at column c (no inset) at station z"""
    flare = 0.030 * float(bump(z, -1.46, -1.20, 0.40)) + 0.018 * float(bump(z, 1.20, 1.46, 0.42))
    taper = 0.012 * float(np.clip((abs(z) - 1.8) / 0.2, 0, 1))
    return SIDE_X[c] - taper + flare * FLARE_W.get(c, 0.0)


def rear_bumper_path(n_side=10, n_corner=26):
    """plan outline of the rear bumper's face, left half: from inside the rear arch back to the centre line;
    [(x, z, nx, nz)] with the outward normal"""
    a, z0, b, ne = side_x(-2.0) + 0.002, -1.95, 0.36, 3.4
    pts = []
    for k in range(n_side):
        z = -1.62 + (z0 + 1.62) * k / n_side
        pts.append((side_x(z) + 0.002, z))
    for k in range(n_corner + 1):
        th = (math.pi / 2) * k / n_corner
        c, s = max(math.cos(th), 0.0), max(math.sin(th), 0.0)
        pts.append((a * c ** (2 / ne), z0 - b * s ** (2 / ne)))
    pts = np.array(pts)
    out = []
    for i, (x, z) in enumerate(pts):
        p0 = pts[max(0, i - 1)]
        p1 = pts[min(len(pts) - 1, i + 1)]
        t = p1 - p0
        t /= np.linalg.norm(t)
        out.append((x, z, -t[1], t[0]))        # tangent (dx, dz) turned to the right = outward
    return out


def rear_bumper_profile(f):
    """closed profile (n outward, y) at f = 0 (side, by the arch) .. 1 (back centre)"""
    yt = 0.600 + 0.022 * f
    yb = 0.285 - 0.02 * f
    bulge = 0.004 * f
    return [(-0.20, yb + 0.02), (-0.05, yb - 0.004), (-0.012, yb - 0.003), (-0.002, yb + 0.004), (0.0, yb + 0.02),
            (bulge * 0.7, yb + 0.12), (bulge, (yb + yt) / 2), (bulge * 0.6, yt - 0.05), (0.0, yt - 0.008),
            (-0.004, yt - 0.001), (-0.018, yt), (-0.20, yt + 0.002)]
