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
Measured on Commons photos (fitdata/e5/ref/list.json; every figure an estimate within ±5–10 cm):
- 3/4 front "Shinkansen E5 with E3 at Nasu-Shiobara Station.jpg" (telephoto), camera solved on the end car's gap, doors
  and windows and the far platform edge (2026-11-10): the nose read short because its front grew too fast and its
  canopy sat ≈ 2 m too far forward. Ray-cast on the fitted shell: windscreen foot ≈ 6.2 m behind the tip (centre
  line, ≈ 2.4 m up), the lamp row ≈ 7.5 m (2.86 m up), the side windows' rear end ≈ 8.5 m; the cap widest ≈ 1.1 m
  behind the tip, the chin below it narrower, the lower cheeks at full width only round the bogie; the pink stripe
  runs down the nose to ≈ 5 m from the tip, the white flank reaches ≈ 1.5 m up right behind the cap. (Its doors and
  windows fit best ≈ 1.5 m further forward than ours: left as is, the published nose is 15 m.)
- side view "E5 S11 Sendai 20090725.JPG" (car E514 of S11, nose right) with a projective fit along the car: the
  nose's top line, canopy (windscreen from d ≈ 6.0 to 9.3), the skirt bottom (≈ 0.30 m above the rail), the pink
  stripe (1.90–2.08 m);
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
    # d      ybc   yb    xo     fl     rbx   rby   ym     c      hc     xe     ye    yt    nr
    ( 0.000, 1.12, 1.12, 0.000, 0.000, 0.00, 0.00, 1.120, 0.000, 0.000, 0.000, 1.12, 1.12, 2.00),
    ( 0.030, 0.89, 0.89, 0.222, 0.000, 0.11, 0.12, 1.096, 0.000, 0.017, 0.218, 1.14, 1.24, 2.00),
    ( 0.100, 0.67, 0.67, 0.442, 0.000, 0.20, 0.20, 1.067, 0.000, 0.029, 0.434, 1.15, 1.34, 2.00),
    ( 0.250, 0.52, 0.52, 0.688, 0.000, 0.28, 0.26, 1.046, 0.000, 0.030, 0.674, 1.14, 1.40, 2.00),
    ( 0.500, 0.43, 0.43, 0.877, 0.000, 0.34, 0.31, 1.029, 0.000, 0.030, 0.862, 1.12, 1.45, 2.00),
    ( 0.800, 0.39, 0.39, 0.993, 0.000, 0.35, 0.31, 1.017, 0.000, 0.030, 0.979, 1.12, 1.48, 2.00),
    ( 1.100, 0.37, 0.37, 1.070, 0.000, 0.28, 0.26, 1.010, 0.000, 0.030, 1.050, 1.12, 1.52, 2.05),
    ( 1.500, 0.35, 0.35, 1.139, 0.000, 0.29, 0.27, 1.001, 0.090, 0.047, 1.086, 1.15, 1.60, 2.18),
    ( 2.000, 0.33, 0.33, 1.218, 0.009, 0.29, 0.27, 0.992, 0.163, 0.074, 1.131, 1.22, 1.72, 2.32),
    ( 2.600, 0.32, 0.32, 1.302, 0.045, 0.23, 0.21, 0.987, 0.226, 0.090, 1.155, 1.30, 1.83, 2.42),
    ( 3.400, 1.00, 0.31, 1.387, 0.092, 0.17, 0.16, 0.983, 0.285, 0.105, 1.168, 1.39, 1.95, 2.54),
    ( 4.200, 1.00, 0.30, 1.451, 0.142, 0.12, 0.12, 0.975, 0.319, 0.119, 1.174, 1.47, 2.06, 2.65),
    ( 5.000, 1.00, 0.30, 1.497, 0.145, 0.10, 0.11, 0.967, 0.327, 0.133, 1.187, 1.55, 2.14, 2.70),
    ( 6.000, 1.00, 0.30, 1.541, 0.120, 0.09, 0.11, 0.960, 0.330, 0.150, 1.210, 1.64, 2.21, 2.75),
    ( 7.000, 1.00, 0.30, 1.574, 0.094, 0.10, 0.12, 0.960, 0.327, 0.164, 1.242, 1.74, 2.30, 2.79),
    ( 8.000, 1.00, 0.30, 1.610, 0.063, 0.11, 0.18, 0.963, 0.321, 0.175, 1.278, 1.86, 2.38, 2.80),
    ( 9.000, 1.00, 0.30, 1.645, 0.030, 0.14, 0.31, 0.979, 0.306, 0.180, 1.319, 2.00, 2.47, 2.79),
    (10.000, 1.00, 0.30, 1.666, 0.009, 0.18, 0.50, 1.016, 0.265, 0.180, 1.377, 2.16, 2.66, 2.69),
    (11.000, 1.00, 0.30, 1.675, 0.000, 0.21, 0.63, 1.124, 0.192, 0.157, 1.458, 2.34, 2.87, 2.59),
    (12.000, 1.00, 0.30, 1.675, 0.000, 0.22, 0.71, 1.318, 0.100, 0.123, 1.532, 2.55, 3.12, 2.48),
    (13.000, 1.00, 0.30, 1.675, 0.000, 0.22, 0.75, 1.567, 0.023, 0.113, 1.573, 2.80, 3.39, 2.43),
    (13.800, 1.00, 0.30, 1.675, 0.000, 0.22, 0.75, 1.650, 0.000, 0.120, 1.589, 3.01, 3.57, 2.40),
    (14.600, 1.00, 0.30, 1.675, 0.000, 0.22, 0.75, 1.650, 0.000, 0.120, 1.595, 3.20, 3.65, 2.40),
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
# The cab's canopy stands proud of the nose as a bubble: a raked glazed front (the windscreen, the lamps along its top),
# glazed flanks, a long rounded cap behind running back into the roof. Head-on (U19, aligned on the roof line) it is a
# bell: ≈ 1.70 m wide at its foot (≈ 2.4 m), ≈ 1.0 m over its rounded top (≈ 3.0 m), the sides slanting out as they go
# down; from the front 3/4 (Nasu-Shiobara, a solved camera) its foot is ≈ 6.0 m behind the tip, the lamps ≈ 1.5 m
# further back, the cap into the roof by ≈ 12.6 m. Around it the nose dips: a moat ahead of the foot (where the wipers
# park) and two valleys along its flanks, between it and the shoulders that run forward to the cap ("hood" look
# head-on). Our own: the profile functions below and their numbers (fitted on the head-on and 3/4 photos).
BUB_D = (6.00, 12.60)           # the bubble's foot at the centre line, and where its cap has run into the roof
_BH = _pchip_table([6.00, 6.29, 6.74, 7.17, 7.55, 7.82, 8.07, 8.45, 9.03, 9.79, 10.45, 11.11, 11.67, 12.23, 12.60],
                   [0.0, 0.07, 0.22, 0.36, 0.49, 0.58, 0.64, 0.67, 0.64, 0.53, 0.39, 0.25, 0.13, 0.04, 0.0])
_BW = _pchip_table([6.0, 6.59, 7.43, 10.17, 11.57, 12.6], [0.80, 0.87, 0.90, 0.90, 0.85, 0.78])
BUB_P = 2.2                     # across: cos²(π/2·u^P): a rounded top, steep flanks, a fillet at the foot
BUB_SWEEP = 0.435               # in plan the foot curves back at the sides by this much
# the valleys beside the bubble: depth and position along d; the moat ahead of the foot
_VD = _pchip_table([1.55, 2.63, 3.96, 5.55, 7.49, 9.90, 11.37, 12.53, 13.20],
                   [0.0, 0.03, 0.06, 0.075, 0.08, 0.07, 0.04, 0.012, 0.0])
_VX = _pchip_table([1.55, 2.63, 3.96, 5.55, 6.76, 8.19, 11.37, 13.20], [0.45, 0.58, 0.70, 0.82, 0.95, 1.00, 1.00, 1.05])
VAL_W = 0.22
RIDGE = (0.55, 0.30, 0.14)      # the shoulders' ridge outboard of each valley: height (× the valley's depth), offset, width
MOAT = (0.045, 5.75, 0.48)      # depth, centre d, half width (Gaussian)
RELIEF_D = (1.55, 13.2)


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
STRIPE_D = (4.9, 7.2)           # down the nose the stripe tapers out between these distances from the tip
CAP_D = 1.33                    # the coupler cover's seam: its rear edge on the nose's top and flanks
# on the nose the green/white line follows the stripe down to ≈ 1.5 m, then steps down to the cap's line (≈ 1.05 m) at
# the cover's seam (3/4 front: the white flank reaches ≈ 1.5 m up right behind the cap)
_BOUND = _pchip_table([0.0, 0.5, CAP_D - 0.05, CAP_D + 0.30, 2.0, 2.7, 4.0, 5.0, 5.65, 7.25, 8.9, 10.5, 12.5, 14.6, 30.0],
                      [1.06, 1.04, 1.04, 1.40, 1.48, 1.53, 1.57, 1.59, 1.62, 1.71, 1.81, 1.86, 1.89, 1.90, 1.90])


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
