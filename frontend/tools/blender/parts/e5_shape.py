"""
JR East E5 series (Hayabusa): the body's shape as numbers, shared by the shell, its painted textures and the parts that
sit on it. Pure numpy, no Blender.

Frame: the game's car frame of train_kit (metres; +x = the car's left, +y up from the rail top, +z forward). A cab
car has its nose at +z; `d` is the distance back from the nose tip (d = NOSE_TIP − z).

Figures (ja.wikipedia 新幹線E5系・H5系電車, read 2026-11-03):
- car length 26,500 mm (end cars, nose tip to the coupler face) and 25,000 mm (middle cars); body width 3,350 mm;
  height 3,650 mm (4,490 mm on a pantograph car); floor 1,300 mm; wheel ∅ 860 mm; nose "about 15 m"
  ("ダブルカスプ" double cusp, after the E954's "アローライン"); sides lean in above the waist (車体傾斜, 内傾).
- Bogie centres 17,500 mm, wheelbase 2,500 mm: the Shinkansen standard (not given for the E5 on the page: estimate).
  Body 24.5 m over the gangway faces (25.0 m over the couplers): the Shinkansen standard (estimate).
Measured on Commons photos (see the e5 scratch list.json; every figure an estimate within ±5–10 cm):
- side view "E5 S11 Sendai 20090725.JPG" (car E514 of S11, nose right) with a projective fit along the car: the
  nose's top line, canopy (windscreen from d ≈ 6.0 to 9.3), the green/white line on the nose, the skirt bottom
  (≈ 0.30 m above the rail), the pink stripe (1.90–2.08 m);
- head-on "E5系 U19編成.jpg" (telephoto, 143 px/m): canopy 1.70 m wide outside, four head lamps 0.16 m apart at
  ≈ 2.83 m, nose cap (coupler cover) 2.15 m wide, cap seam middle at ≈ 1.10 m;
- "H523-1 omiya 20160327.jpg", "JRE E523-1.jpg", "E514-1.jpg", "JRE E5 U2 200 K47.jpg", the museum mock-up
  "Railway Museum Saitama 2020-08-21 DSC02974": the plan of the nose cap, the cusp, the cover seams, the cheeks.
Our own: the section's exact curves (an elliptic tuck at the bottom, a leaning side, a superellipse roof), the
nose's sections between the measured lines.
"""
import math

import numpy as np

# ---------------------------------------------------------------- the car
HW = 1.675              # half the body width (3,350 mm)
ROOF = 3.65             # roof at the centre line
FLOOR = 1.30
BOGIE_Z = 8.75          # bogie centres ±8.75 (17.5 m)
WHEELBASE = 2.5
WHEEL_R = 0.43
END = 12.25             # gangway faces (body 24.5 m); couplers at ±12.5
COUPLER = 12.5
NOSE_TIP = 14.0         # cab car: nose tip (26.5 m from the rear coupler face at −12.5)
NOSE_LEN = 14.6         # full section from d = 14.6 (z = −0.6) back

# the body section (also the nose's sections at d ≥ NOSE_LEN)
BODY = dict(ybc=1.00, yb=0.30, xo=HW, fl=0.0, rbx=0.22, rby=0.75, ym=1.65, c=0.0, hc=0.12, xe=1.595, ye=3.20, yt=ROOF,
            nr=2.4)

# ---------------------------------------------------------------- the nose: parameters along d
# d: distance from the tip. Columns: the section's parameters (see `half_section`); fl = the lower cheek's flare (its
# foot stands out by fl beyond xo, the width at the crease; head-on photos: the white "wings" low on the nose).
_KEYS = ('ybc', 'yb', 'xo', 'fl', 'rbx', 'rby', 'ym', 'c', 'hc', 'xe', 'ye', 'yt', 'nr')
_NOSE = [
    # d      ybc   yb    xo     fl    rbx   rby   ym     c      hc    xe     ye    yt    nr
    (0.000, 1.12, 1.12, 0.000, 0.00, 0.00, 0.00, 1.12, 0.00, 0.00, 0.000, 1.12, 1.12, 2.0),
    (0.030, 0.84, 0.84, 0.270, 0.00, 0.13, 0.14, 1.09, 0.00, 0.02, 0.265, 1.14, 1.26, 2.0),
    (0.100, 0.62, 0.62, 0.500, 0.00, 0.22, 0.22, 1.06, 0.00, 0.03, 0.490, 1.15, 1.36, 2.0),
    (0.250, 0.48, 0.48, 0.770, 0.00, 0.30, 0.28, 1.04, 0.00, 0.03, 0.755, 1.13, 1.42, 2.0),
    (0.500, 0.40, 0.40, 0.960, 0.00, 0.36, 0.32, 1.02, 0.00, 0.03, 0.945, 1.12, 1.47, 2.0),
    (0.800, 0.37, 0.37, 1.070, 0.00, 0.28, 0.26, 1.01, 0.00, 0.03, 1.050, 1.12, 1.52, 2.05),
    (1.200, 0.35, 0.35, 1.200, 0.10, 0.16, 0.16, 1.00, 0.10, 0.05, 1.090, 1.16, 1.61, 2.2),
    (1.800, 0.33, 0.33, 1.340, 0.17, 0.10, 0.11, 0.99, 0.18, 0.08, 1.140, 1.24, 1.75, 2.35),
    (2.600, 0.31, 0.31, 1.450, 0.20, 0.09, 0.10, 0.985, 0.27, 0.10, 1.165, 1.36, 1.91, 2.5),
    (3.400, 1.00, 0.30, 1.510, 0.165, 0.09, 0.10, 0.975, 0.32, 0.12, 1.175, 1.48, 2.07, 2.65),
    (4.500, 1.00, 0.30, 1.560, 0.115, 0.09, 0.11, 0.96, 0.33, 0.15, 1.210, 1.64, 2.21, 2.75),
    (5.500, 1.00, 0.30, 1.600, 0.075, 0.10, 0.14, 0.96, 0.325, 0.17, 1.260, 1.80, 2.34, 2.8),
    (6.500, 1.00, 0.30, 1.640, 0.035, 0.13, 0.28, 0.975, 0.31, 0.18, 1.310, 1.97, 2.45, 2.8),
    (7.500, 1.00, 0.30, 1.665, 0.01, 0.18, 0.48, 1.01, 0.27, 0.18, 1.370, 2.14, 2.64, 2.7),
    (8.500, 1.00, 0.30, 1.675, 0.00, 0.21, 0.62, 1.11, 0.20, 0.16, 1.450, 2.32, 2.85, 2.6),
    (9.500, 1.00, 0.30, 1.675, 0.00, 0.22, 0.70, 1.27, 0.12, 0.13, 1.520, 2.50, 3.06, 2.5),
    (10.50, 1.00, 0.30, 1.675, 0.00, 0.22, 0.74, 1.46, 0.05, 0.11, 1.558, 2.68, 3.27, 2.45),
    (11.50, 1.00, 0.30, 1.675, 0.00, 0.22, 0.75, 1.60, 0.015, 0.115, 1.578, 2.85, 3.44, 2.42),
    (12.50, 1.00, 0.30, 1.675, 0.00, 0.22, 0.75, 1.65, 0.00, 0.12, 1.588, 3.00, 3.56, 2.4),
    (13.50, 1.00, 0.30, 1.675, 0.00, 0.22, 0.75, 1.65, 0.00, 0.12, 1.593, 3.12, 3.62, 2.4),
    (14.60, 1.00, 0.30, 1.675, 0.00, 0.22, 0.75, 1.65, 0.00, 0.12, 1.595, 3.20, 3.65, 2.4),
]


def _pchip_table(xs, ys):
    xs = np.asarray(xs, float)
    ys = np.asarray(ys, float)
    h = np.diff(xs)
    dlt = np.diff(ys) / h
    m = np.zeros_like(ys)
    for i in range(1, len(ys) - 1):
        if dlt[i - 1] * dlt[i] > 0:
            w1, w2 = 2 * h[i] + h[i - 1], h[i] + 2 * h[i - 1]
            m[i] = (w1 + w2) / (w1 / dlt[i - 1] + w2 / dlt[i])
    m[0], m[-1] = dlt[0], dlt[-1]

    def f(x):
        x = np.clip(np.asarray(x, float), xs[0], xs[-1])
        i = np.clip(np.searchsorted(xs, x) - 1, 0, len(xs) - 2)
        t = (x - xs[i]) / h[i]
        h00, h10, h01, h11 = 2 * t ** 3 - 3 * t ** 2 + 1, t ** 3 - 2 * t ** 2 + t, -2 * t ** 3 + 3 * t ** 2, t ** 3 - t ** 2
        return h00 * ys[i] + h10 * h[i] * m[i] + h01 * ys[i + 1] + h11 * h[i] * m[i + 1]
    return f


pchip = _pchip_table
_ND = [r[0] for r in _NOSE]
_NF = {k: _pchip_table(_ND, [r[i + 1] for r in _NOSE]) for i, k in enumerate(_KEYS)}

# The table's curves faired: pchip is only C1, so its curvature jumps at every row and the nose's highlights rippled.
# Each curve (but the bottom's step into the bogie well) is smoothed with a Gaussian whose width grows with d (tight at
# the tip, ±0.45 m over the long nose), on a 1 cm grid.
_FD = np.linspace(0.0, NOSE_LEN, 1461)


def _faired(f):
    v = f(_FD)
    sig = np.clip(0.11 * _FD, 0.012, 0.45)
    w = np.exp(-0.5 * ((_FD[None, :] - _FD[:, None]) / sig[:, None]) ** 2)
    # mirror about the ends so the smoothing does not pull the end values
    w2 = np.exp(-0.5 * ((-_FD[None, :] - _FD[:, None]) / sig[:, None]) ** 2)
    w3 = np.exp(-0.5 * ((2 * NOSE_LEN - _FD[None, :] - _FD[:, None]) / sig[:, None]) ** 2)
    vr = 2 * v[0] - v              # odd reflection at d = 0 keeps the slope
    ve = 2 * v[-1] - v
    out = (w @ v + w2 @ vr + w3 @ ve) / (w.sum(1) + w2.sum(1) + w3.sum(1))
    return out


_NG = {k: (_FD, (_faired(f) if k != 'ybc' else f(_FD))) for k, f in _NF.items()}


def nose_params(d):
    """the section's parameters at distance d from the tip (the body's beyond the nose)"""
    if d >= NOSE_LEN:
        return dict(BODY)
    if d <= 0.0:
        return {k: float(_NF[k](0.0)) for k in _KEYS}
    p = {k: float(np.interp(d, g, v)) for k, (g, v) in _NG.items()}
    for k in ('c', 'hc', 'fl'):
        p[k] = max(p[k], 0.0)
    return p


# ---------------------------------------------------------------- the half section
# point counts per segment (fixed, so every section has the same topology)
U_SIDE = (0.12, 0.30, 0.50, 0.70, 0.88, 0.974, 1.0)      # upper side: 1.65 → 3.20 on the body (3.16 = door top)
L_SIDE = (0.06, 0.16, 0.4167, 0.62, 0.81, 1.0)          # lower side: 1.05 → 1.65 on the body (0.4167: 1.30 = door sill)
L_SILL = 2                                                # index of the sill's point in L_SIDE
N_CORNER = 6
N_CUSP = 4
N_ROOF = 28
SKIRT_T = 0.04          # the skirt's thickness (inner face)
SEGMENTS = ('bottom', 'bottom', 'bottom', 'inner', 'inner', 'skirt') + ('corner',) * N_CORNER + ('lside',) * len(L_SIDE) \
    + ('cusp',) * N_CUSP + ('uside',) * len(U_SIDE) + ('roof',) * N_ROOF
HALF_N = len(SEGMENTS)


def half_section(p):
    """[(x, y)] from the bottom centre (x = 0) round the left side (+x) to the roof's centre line; HALF_N points"""
    ybc, yb, xo, rbx, rby = p['ybc'], p['yb'], p['xo'], p['rbx'], p['rby']
    ym, c, hc, xe, ye, yt, nr = p['ym'], p['c'], p['hc'], p['xe'], p['ye'], p['yt'], p['nr']
    xf = min(xo + p.get('fl', 0.0), HW)  # the cheek's foot (flared out below the crease)
    xk = xf - rbx                       # where the bottom corner starts
    xi = max(min(xk - SKIRT_T, xo - 0.08), 0.0)   # (inside the crease: the lip may stand out far beyond it)
    if p.get('jaw'):
        # the cab's jaw ahead of the bogie well: one gently convex underside out to the corner (no skirt step)
        pts = [(xk * f, yb - 0.012 * (1 - f * f)) for f in (0.0, 0.26, 0.5, 0.7, 0.86)]
    else:
        pts = [(0.0, ybc), (xi * 0.5, ybc), (xi, ybc)]
        pts += [(xi, ybc + (yb - ybc) * 0.5), (xi, yb)]
    pts += [(xk, yb)]
    for k in range(1, N_CORNER + 1):
        a = (math.pi / 2) * k / N_CORNER
        pts.append((xk + rbx * math.sin(a), yb + rby * (1 - math.cos(a))))
    y0 = yb + rby
    for f in L_SIDE:
        # the flare: the foot stands out as a lip and the side leans in fast above it (concave, a fin's edge)
        g = 1.0 - (1.0 - f) ** 2.4
        pts.append((xf + (xo - xf) * g, y0 + (ym - y0) * f))
    xu = xo - c
    for k in range(1, N_CUSP + 1):
        t = k / N_CUSP
        s = t * t * (3 - 2 * t)
        pts.append((xo - c * s, ym + hc * t))
    y1 = ym + hc
    for f in U_SIDE:
        pts.append((xu + (xe - xu) * f, y1 + (ye - y1) * f))
    b = yt - ye
    for k in range(1, N_ROOF + 1):
        th = (math.pi / 2) * (k / N_ROOF) ** 0.85
        cx = math.cos(th)
        sy = math.sin(th)
        x = xe * (abs(cx) ** (2.0 / nr)) if k < N_ROOF else 0.0
        y = ye + b * (abs(sy) ** (2.0 / nr))
        pts.append((x, y))
    return pts


# ---------------------------------------------------------------- the canopy bubble and the relief of the nose's top
# The cab's canopy stands proud of the nose as a bubble: a steep glazed front (the windscreen, the lamps along its top),
# glazed flanks, a rounded cap behind running back into the roof. Head-on (U19, aligned on the roof line) it is a
# bell: ≈ 1.70 m wide at its foot (≈ 2.2 m), ≈ 1.0 m over its rounded top (≈ 3.0 m), the sides slanting out as they go
# down; from the side ("E514-1", "E5 S11 Sendai", a projective fit along the car) its foot is ≈ 4.2 m behind the tip,
# the lamps ≈ 1.3 m further back. Around it the nose dips: a moat ahead of the foot (where the wipers park) and two
# valleys along its flanks, between it and the shoulders that run forward to the cap ("hood" look head-on).
# Our own: the profile functions below and their numbers (fitted on the head-on and 3/4 photos).
BUB_D = (4.20, 10.60)           # the bubble's foot at the centre line, and where its cap has run into the roof
_BH = _pchip_table([4.20, 4.40, 4.70, 5.00, 5.30, 5.55, 5.80, 6.20, 6.80, 7.60, 8.30, 9.00, 9.60, 10.20, 10.60],
                   [0.0, 0.07, 0.22, 0.36, 0.49, 0.58, 0.64, 0.67, 0.64, 0.53, 0.39, 0.25, 0.13, 0.04, 0.0])
_BW = _pchip_table([4.2, 4.6, 5.2, 8.0, 9.5, 10.6], [0.80, 0.87, 0.90, 0.90, 0.85, 0.78])
BUB_P = 2.2                     # across: cos²(π/2·u^P): a rounded top, steep flanks, a fillet at the foot
BUB_SWEEP = 0.30                # in plan the foot curves back at the sides by this much
# the valleys beside the bubble: depth and position along d; the moat ahead of the foot
_VD = _pchip_table([1.2, 2.2, 3.2, 4.2, 5.5, 7.5, 9.0, 10.5, 11.5], [0.0, 0.03, 0.06, 0.075, 0.08, 0.07, 0.04, 0.012, 0.0])
_VX = _pchip_table([1.2, 2.2, 3.2, 4.2, 5.0, 6.0, 9.0, 11.5], [0.45, 0.58, 0.70, 0.82, 0.95, 1.00, 1.00, 1.05])
VAL_W = 0.22
RIDGE = (0.55, 0.30, 0.14)      # the shoulders' ridge outboard of each valley: height (× the valley's depth), offset, width
MOAT = (0.045, 3.95, 0.32)      # depth, centre d, half width (Gaussian)
RELIEF_D = (1.2, 11.5)


def _smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def bubble_height_a(d):
    """the bubble's lift on the centre line at distance d"""
    d = np.asarray(d, float)
    return np.where((d > BUB_D[0]) & (d < BUB_D[1]), _BH(np.clip(d, *BUB_D)), 0.0)


def bubble_a(x, d):
    """how much the canopy bubble lifts the nose's top surface at (x, d)"""
    x = np.abs(np.asarray(x, float))
    d = np.asarray(d, float)
    w = _BW(np.clip(d, *BUB_D))
    u = np.clip(x / w, 0.0, 1.0)
    h = bubble_height_a(d - BUB_SWEEP * u * u)
    return h * np.cos(0.5 * math.pi * u ** BUB_P) ** 2


def bubble_halfwidth_a(d):
    return _BW(np.clip(np.asarray(d, float), *BUB_D))


def relief_a(x, d):
    """the top surface's relief at (x, d): the bubble, less the valleys and the moat"""
    x = np.abs(np.asarray(x, float))
    d = np.asarray(d, float)
    dc = np.clip(d, *RELIEF_D)
    inside = (d > RELIEF_D[0]) & (d < RELIEF_D[1])
    vd = np.where(inside, _VD(dc), 0.0)
    v = vd * np.exp(-((x - _VX(dc)) / VAL_W) ** 2)
    ridge = RIDGE[0] * vd * np.exp(-((x - _VX(dc) - RIDGE[1]) / RIDGE[2]) ** 2)
    m = MOAT[0] * np.exp(-((d - MOAT[1]) / MOAT[2]) ** 2) * (1.0 - _smooth(0.75, 1.05, x))
    return bubble_a(x, d) + ridge - np.sqrt(v * v + m * m)


def relief(x, d):
    return float(relief_a(x, d))


# ---------------------------------------------------------------- livery lines
STRIPE = (1.90, 2.08)           # pink stripe on the body (white below, green above)
STRIPE_D = (7.6, 11.0)          # down the nose the stripe tapers out between these distances from the tip
# on the nose the green/white line drops from the stripe to the cap's seam line (side view, d → y)
_BOUND = _pchip_table([0.0, 0.5, 1.0, 2.0, 4.0, 6.0, 7.5, 8.5, 9.5, 10.5, 11.5, 12.5, 13.5, 14.6, 30.0],
                      [1.06, 1.04, 1.03, 1.03, 1.05, 1.11, 1.16, 1.24, 1.36, 1.52, 1.68, 1.81, 1.88, 1.90, 1.90])


def green_line(d):
    """the white's top edge (green above, or the pink stripe where it runs) at distance d from the tip"""
    return float(_BOUND(d))


def stripe_width(d):
    """the pink stripe's width above the green line: full on the body, tapering out down the nose"""
    full = STRIPE[1] - STRIPE[0]
    if d >= STRIPE_D[1]:
        return full
    if d <= STRIPE_D[0]:
        return 0.0
    t = (d - STRIPE_D[0]) / (STRIPE_D[1] - STRIPE_D[0])
    return full * (t * t * (3 - 2 * t)) ** 0.6


# ---------------------------------------------------------------- array versions (painting)

def green_line_a(d):
    return _BOUND(np.asarray(d, float))


def stripe_width_a(d):
    d = np.asarray(d, float)
    full = STRIPE[1] - STRIPE[0]
    t = np.clip((d - STRIPE_D[0]) / (STRIPE_D[1] - STRIPE_D[0]), 0, 1)
    return full * (t * t * (3 - 2 * t)) ** 0.6
