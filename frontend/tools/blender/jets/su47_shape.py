"""
The Su-47's airframe in numbers (tools/blender/jets/su47.py): stations, planforms, sections, and the skins made of
them. No drawing was traced and no photo fitted: the figures are the published ones (22.6 m long, 16.7 m span,
6.4 m high, 56 m² of wing, a 5 % aerofoil; forward fuselage, fins and landing gear of the Su-27 family) and the
layout as it is known (see the notes at each part). What was derived here and not published is said so.

Stations are `d`: metres aft of the tip of the nose probe. Game frame: x = the aircraft's left, y up from the
ground (gear down), z forward; the origin lies midway between the nose wheels and the main wheels, so z = Z0 - d
with the nose gear 5.6 m aft of the tip and a wheelbase of 6.0 m (vehicle/jets.ts).
"""
import math

import numpy as np

import jet_kit as K
from jet_kit import Pchip, smoothstep, lerp
import su47_skin as S

LENGTH, SPAN, HEIGHT = 22.6, 16.7, 6.4
Z0 = 8.6


def Z(d):
    return Z0 - d


def smin(a, b, k):
    h = min(1.0, max(0.0, 0.5 + 0.5 * (b - a) / k))
    return lerp(b, a, h) - k * h * (1 - h)


def smax(a, b, k):
    return -smin(-a, -b, k)


# ------------------------------------------------------------------------------------------------ forward fuselage
# The Su-27's: a round radome drooped to the tip, an oval body deeper than wide under the cockpit, the spine behind
# the canopy running down into the back. It ends inside the centre body (its keel is the belly between the intakes).

FB_W = Pchip([(0.90, 0.022), (1.00, 0.085), (1.25, 0.185), (1.6, 0.295), (2.1, 0.40), (2.7, 0.485), (3.3, 0.545), (4.0, 0.63),
              (4.8, 0.71), (5.6, 0.75), (6.6, 0.77), (8.0, 0.76), (9.5, 0.70), (11.0, 0.58), (12.5, 0.45), (13.6, 0.30)])
FB_YC = Pchip([(0.9, 2.24), (2.0, 2.33), (3.3, 2.43), (4.5, 2.50), (5.6, 2.52), (8.0, 2.55), (13.6, 2.55)])
# height of the top / depth of the bottom from the widest line (the radome is round: both = the half width)
FB_HT = Pchip([(0.90, 0.022), (1.00, 0.085), (1.25, 0.185), (1.6, 0.295), (2.1, 0.40), (2.7, 0.485), (3.3, 0.545), (4.0, 0.59),
               (4.25, 0.60), (4.8, 0.60), (5.6, 0.60), (6.6, 0.62), (7.0, 0.66), (7.6, 0.83), (8.4, 0.95), (9.5, 0.87),
               (11.0, 0.70), (12.5, 0.53), (13.6, 0.43)])
FB_HB = Pchip([(0.90, 0.022), (1.00, 0.085), (1.25, 0.185), (1.6, 0.295), (2.1, 0.40), (2.7, 0.485), (3.3, 0.545), (4.0, 0.62),
               (4.8, 0.705), (5.6, 0.77), (6.6, 0.83), (8.0, 0.87), (9.5, 0.79), (11.0, 0.72), (12.5, 0.63), (13.6, 0.35)])
FB_ET = Pchip([(0.9, 2.0), (6.6, 2.0), (7.6, 1.85), (11.0, 1.85), (13.6, 2.0)])
FB_EB = Pchip([(0.9, 2.0), (3.3, 2.0), (4.8, 2.4), (5.6, 2.7), (8.0, 3.0), (11.0, 2.6), (13.6, 2.2)])
# where the ring has its vertex for the canopy's sill (half width); the cockpit's opening is cut along it
FB_WS = Pchip([(0.9, 0.3), (3.9, 0.30), (4.25, 0.25), (4.5, 0.28), (4.8, 0.40), (5.05, 0.44), (5.9, 0.47), (6.95, 0.45),
               (7.6, 0.36), (8.4, 0.30), (9.5, 0.33), (13.6, 0.15)])
FB_STATIONS = [0.90, 0.93, 0.97, 1.0, 1.08, 1.25, 1.45, 1.7, 2.0, 2.35, 2.7, 3.0, 3.3, 3.6, 3.9, 4.25, 4.5, 4.8, 5.05, 5.3, 5.6,
               5.9, 6.25, 6.6, 6.95, 7.3, 7.6, 8.0, 8.4, 8.9, 9.5, 10.2, 11.0, 11.8, 12.5, 13.1, 13.6]
COCKPIT = (4.5, 6.95)            # the opening under the canopy
RADOME = 3.3                     # the radome's base


def fb_sill(d):
    return min(FB_WS(d), 0.55 * FB_W(d))


def fb_top_y(d, x):
    """the upper surface's height at x off the middle"""
    w, e = FB_W(d), FB_ET(d)
    r = min(1.0, abs(x) / w)
    return FB_YC(d) + FB_HT(d) * (1 - r ** e) ** (1 / e)


def fb_bottom_y(d, x=0.0):
    w, e = FB_W(d), FB_EB(d)
    r = min(1.0, abs(x) / w)
    return FB_YC(d) - FB_HB(d) * (1 - r ** e) ** (1 / e)


def fb_side_x(d, y):
    """half width of the forward fuselage at a height"""
    yc = FB_YC(d)
    if y >= yc:
        h, e = FB_HT(d), FB_ET(d)
    else:
        h, e = FB_HB(d), FB_EB(d)
    r = min(1.0, abs(y - yc) / h)
    return FB_W(d) * (1 - r ** e) ** (1 / e)


def fb_ring(d, n_lo=13, n_a=6, n_b=6):
    """half ring: bottom centre → side → the sill's vertex → top centre"""
    w, yc, ht, hb, et, eb = FB_W(d), FB_YC(d), FB_HT(d), FB_HB(d), FB_ET(d), FB_EB(d)
    phi_s = math.acos(min(0.999, fb_sill(d) / w) ** (et / 2))
    angles = [-math.pi / 2 + (math.pi / 2) * k / n_lo for k in range(n_lo)]
    angles += [phi_s * k / n_a for k in range(n_a)]
    angles += [phi_s + (math.pi / 2 - phi_s) * k / n_b for k in range(n_b + 1)]
    out = []
    for a in angles:
        c, s = max(0.0, math.cos(a)), math.sin(a)
        if s >= 0:
            out.append((w * c ** (2 / et), yc + ht * s ** (2 / et), Z(d)))
        else:
            out.append((w * c ** (2 / eb), yc - hb * (-s) ** (2 / eb), Z(d)))
    out[0] = (0.0, out[0][1], Z(d))
    out[-1] = (0.0, out[-1][1], Z(d))
    return out


FB_SILL_I = 19                   # the sill's vertex in the half ring (n_lo + n_a)
FB_GIRTH = 2.75


def forebody_skin(atlas):
    sheet = atlas.sheet('forebody', (FB_STATIONS[-1] - FB_STATIONS[0], FB_GIRTH))
    rows = [fb_ring(d) for d in FB_STATIONS]
    uv = S.loft_uv(rows, [d - FB_STATIONS[0] for d in FB_STATIONS], FB_GIRTH)
    j0, j1 = FB_STATIONS.index(COCKPIT[0]), FB_STATIONS.index(COCKPIT[1])
    return S.Skin('forebody', sheet, rows, uv, mirror=True, skip=lambda i, j: j0 <= j < j1 and i >= FB_SILL_I)


# ------------------------------------------------------------------------------------------------ canopy
# The Su-27's: a one-piece windscreen, a long bubble, the fairing behind it running into the spine.

CN_WS = Pchip([(4.25, 0.0), (4.33, 0.13), (4.45, 0.25), (4.5, 0.28), (4.8, 0.40), (5.05, 0.44), (5.9, 0.47), (6.95, 0.45),
               (7.6, 0.36), (8.2, 0.22), (8.6, 0.06)])
CN_TOP = Pchip([(4.25, 3.085), (4.45, 3.30), (4.8, 3.62), (5.05, 3.78), (5.5, 3.92), (5.9, 3.95), (6.5, 3.88), (7.0, 3.74),
                (7.6, 3.60), (8.2, 3.52), (8.6, 3.49)])
CN_STATIONS = [4.25, 4.29, 4.33, 4.39, 4.45, 4.5, 4.65, 4.8, 4.92, 5.0, 5.08, 5.25, 5.5, 5.9, 6.3, 6.6, 6.87, 6.95, 7.3, 7.6,
               7.9, 8.2, 8.45, 8.6]
CN_ARC = [0.0, 0.07, 0.18, 0.3, 0.42, 0.54, 0.66, 0.77, 0.87, 0.94, 1.0]
CN_E = 2.25
CN_GLASS_END = 6.95
CN_ARCH = (5.0, 5.08)
CN_REAR = (6.87, 6.95)


def canopy_point(d, t):
    """t: 0 at the sill … 1 at the top"""
    ws = CN_WS(d)
    ys = fb_top_y(d, ws)
    top = max(CN_TOP(d), ys + 1e-4)
    a = t * math.pi / 2
    return (ws * max(0.0, math.cos(a)) ** (2 / CN_E), ys + (top - ys) * math.sin(a) ** (2 / CN_E), Z(d))


def canopy_skin(atlas):
    sheet = atlas.sheet('canopy', (CN_STATIONS[-1] - CN_STATIONS[0], 1.2), density=1.2)
    rows = [[canopy_point(d, t) for t in CN_ARC] for d in CN_STATIONS]
    uv = S.loft_uv(rows, [d - CN_STATIONS[0] for d in CN_STATIONS], 1.2)
    jg = CN_STATIONS.index(CN_GLASS_END)
    frames = [(CN_STATIONS.index(CN_ARCH[0]), CN_STATIONS.index(CN_ARCH[1])), (CN_STATIONS.index(CN_REAR[0]), jg)]

    def mats(i, j):
        if j >= jg or i == 0 or any(a <= j < b for a, b in frames):
            return S.AIRFRAME
        return 'glass'

    # the frames beside the glass are seen from inside too
    return S.Skin('canopy', sheet, rows, uv, mirror=True, mats=mats, double=lambda i, j: j < jg and mats(i, j) == S.AIRFRAME)


# ------------------------------------------------------------------------------------------------ lifting surfaces

def aerofoil(n):
    """chord fractions (cosine spaced, n + 1) and the NACA four-digit half thickness per unit thickness there
    (closed trailing edge)"""
    xs = [0.5 * (1 - math.cos(math.pi * k / n)) for k in range(n + 1)]
    yt = [5 * (0.2969 * math.sqrt(x) - 0.1260 * x - 0.3516 * x ** 2 + 0.2843 * x ** 3 - 0.1036 * x ** 4) for x in xs]
    yt[-1] = 0.0
    return xs, yt


WING_Y = 2.56
WING_ROOT, WING_TIP = 2.0, SPAN / 2
WING_TIP_LE, WING_TIP_CHORD = 10.45, 1.5
WING_LE_SWEEP, WING_TE_SWEEP = math.tan(math.radians(20.0)), math.tan(math.radians(37.0))
WING_KINK = 2.9                  # the strake's leading edge meets the forward-swept one here
WING_ROOT_LE = 10.45
WING_TE_KINK = 3.7
WING_T = 0.05
WING_T_MAX = 0.30
WING_TIP_R = 0.3


def wing_le(x):
    main = WING_TIP_LE + (WING_TIP - x) * WING_LE_SWEEP
    k = WING_TIP_LE + (WING_TIP - WING_KINK) * WING_LE_SWEEP
    strake = WING_ROOT_LE + (x - WING_ROOT) * (k - WING_ROOT_LE) / (WING_KINK - WING_ROOT)
    return smin(strake, main, 0.35)


def wing_te(x):
    tip_te = WING_TIP_LE + WING_TIP_CHORD
    outer = tip_te + (WING_TIP - x) * WING_TE_SWEEP
    inner = tip_te + (WING_TIP - WING_TE_KINK) * WING_TE_SWEEP + (WING_TE_KINK - x) * 1.0
    return smax(outer, inner, 0.2)


def wing_station(x):
    """leading edge, chord, thickness ratio at a span station (the tip is rounded in plan)"""
    le, te = wing_le(x), wing_te(x)
    x0 = WING_TIP - WING_TIP_R
    f = 1.0
    if x > x0:
        f = math.sqrt(max(0.0, 1 - ((x - x0) / WING_TIP_R) ** 2))
        mid = le + (te - le) * 0.45
        le, te = mid - (mid - le) * f, mid + (te - mid) * f
    c = te - le
    t = min(WING_T, WING_T_MAX / max(c, 1e-6)) * f
    return le, c, t


def wing_surface_at(x, d):
    """heights of the wing's upper and lower surface at (x, d), or None off the wing"""
    le, c, t = wing_station(x)
    if not (le <= d <= le + c):
        return None
    xi = (d - le) / c
    yt = 5 * t * c * (0.2969 * math.sqrt(xi) - 0.1260 * xi - 0.3516 * xi ** 2 + 0.2843 * xi ** 3 - 0.1036 * xi ** 4)
    return WING_Y + yt, WING_Y - yt


def panel_skins(atlas, name, stations, n_chord, v_ref, frame, mirror=True, density=1.0, cap_root=False, one_sheet=False,
                u_of=None):
    """
    A wing, canard, tailplane or fin: `stations` = [(s, le_d, chord, t_ratio)] along its span; `frame(s)` gives the
    leading edge's (x, y) and the unit direction of the thickness there. Two skins (upper / outer, lower / inner),
    their sheets `<name>_a` / `<name>_b` (or one shared sheet).
    """
    xs, yt = aerofoil(n_chord)
    span = stations[-1][0] - stations[0][0]
    u_of = u_of or (lambda s: s - stations[0][0])
    sa = atlas.sheet(name if one_sheet else f'{name}_a', (span, v_ref), density)
    sb = sa if one_sheet else atlas.sheet(f'{name}_b', (span, v_ref), density)
    up, lo, uv = [], [], []
    for s, le, c, t in stations:
        (x, y), nrm = frame(s)
        ru, rl = [], []
        for k in range(n_chord + 1):
            h = yt[k] * t * c
            ru.append((x + nrm[0] * h, y + nrm[1] * h, Z(le + c * xs[k])))
            rl.append((x - nrm[0] * h, y - nrm[1] * h, Z(le + c * xs[k])))
        up.append(ru)
        lo.append(rl)
        uv.append([(u_of(s), xs[k] * v_ref) for k in range(n_chord + 1)])
    n0 = frame(stations[0][0])[1]
    out = [S.Skin(f'{name}_a', sa, up, uv, mirror=mirror, out=tuple(n0)),
           S.Skin(f'{name}_b', sb, lo, uv, mirror=mirror, out=tuple(-v for v in n0))]
    if cap_root:
        # the root rib of a surface that moves by itself
        out.append(S.Skin(f'{name}_rib', sb, [up[0], lo[0]], [uv[0], uv[0]], mirror=mirror,
                          out=(-1.0, 0.0, 0.0) if abs(n0[1]) > 0.5 else (0.0, -1.0, 0.0)))
    return out


def tip_stations(x0, x1, fn, r, extra=()):
    """span stations from x0 to x1, closer together over the rounded tip of radius r"""
    xs = list(extra)
    for a in (25, 45, 62, 76, 86, 90):
        xs.append(x1 - r + r * math.sin(math.radians(a)))
    return [(x, *fn(x)) for x in sorted(set(xs))]


def wing_skins(atlas):
    xs = [1.9, 2.0, 2.12, 2.26, 2.42, 2.58, 2.74, 2.9, 3.06, 3.25, 3.48, 3.7, 3.95, 4.4, 5.0, 5.6, 6.3, 6.9, 7.5, WING_TIP - WING_TIP_R]
    st = tip_stations(1.9, WING_TIP, wing_station, WING_TIP_R, xs)
    return panel_skins(atlas, 'wing', st, 22, 4.2, lambda s: ((s, WING_Y), (0.0, 1.0, 0.0)))


# the canards on the intakes' shoulders: 47° at the leading edge, a straight trailing edge (derived)
CANARD = {'y': 2.69, 'root': 2.02, 'tip': 3.75, 'le': 7.7, 'le_k': math.tan(math.radians(47.0)), 'te': 10.35, 'te_k': -0.012,
          't': 0.045, 'r': 0.12, 'pivot': 9.25}
# the tailplanes: small, all-moving, 62° at the leading edge (derived)
STAB = {'y': 2.52, 'root': 2.68, 'tip': 4.15, 'le': 17.1, 'le_k': math.tan(math.radians(62.0)), 'te': 20.5, 'te_k': 0.2 / 1.47, 't': 0.04,
        'r': 0.12, 'pivot': 19.4}


def trapezoid_station(p):
    def fn(x):
        le = p['le'] + (x - p['root']) * p['le_k']
        te = p['te'] + (x - p['root']) * p['te_k']
        x0 = p['tip'] - p['r']
        f = 1.0
        if x > x0:
            f = math.sqrt(max(0.0, 1 - ((x - x0) / p['r']) ** 2))
            mid = le + (te - le) * 0.5
            le, te = mid - (mid - le) * f, mid + (te - mid) * f
        return le, te - le, p['t'] * f
    return fn


def moving_skins(atlas, name, p, n=5):
    fn = trapezoid_station(p)
    xs = [p['root'] + (p['tip'] - p['r'] - p['root']) * k / n for k in range(n + 1)]
    st = tip_stations(p['root'], p['tip'], fn, p['r'], xs)
    return panel_skins(atlas, name, st, 14, 2.2, lambda s: ((s, p['y']), (0.0, 1.0, 0.0)), cap_root=True)


# the fins: the Su-27's shape (40° at the leading edge, the top cut down towards the rear) on the booms, canted out
FIN = {'x': 2.32, 'y': 2.80, 'cant': math.radians(8.0), 'le': 15.9, 'te': 19.5, 'tip_le': 18.92, 'tip_te': 20.17, 't': 0.045,
       'cut': 0.24, 'below': 0.3}


def fin_span():
    return (HEIGHT - FIN['y']) / math.cos(FIN['cant'])


def fin_frame(s):
    c = FIN['cant']
    return (FIN['x'] + s * math.sin(c), FIN['y'] + s * math.cos(c)), (math.cos(c), -math.sin(c), 0.0)


def fin_station(s):
    b = fin_span()
    k = s / b
    le = FIN['le'] + (FIN['tip_le'] - FIN['le']) * k
    te = FIN['te'] + (FIN['tip_te'] - FIN['te']) * k
    cut = b - FIN['cut']
    f = 1.0
    if s > cut:
        f = max(0.0, 1 - (s - cut) / FIN['cut'])
        te = le + 0.06 + (te - le - 0.06) * f
    return le, te - le, FIN['t'] * (0.35 + 0.65 * f)


def fin_skins(atlas):
    b = fin_span()
    ss = [-FIN['below'], 0.0, 0.5, 1.1, 1.7, 2.3, 2.8, b - FIN['cut'], b - FIN['cut'] * 0.5, b]
    st = [(s, *fin_station(s)) for s in ss]
    skins = panel_skins(atlas, 'fin', st, 14, 2.7, fin_frame, one_sheet=True, u_of=lambda s: s + FIN['below'])
    # the top closes with a thin rib
    a, c = skins[0], skins[1]
    skins.append(S.Skin('fin_top', a.sheet, [a.rows[-1], c.rows[-1]], [a.uv[-1], a.uv[-1]], mirror=True, out=(0.0, 1.0, 0.0)))
    return skins


# ------------------------------------------------------------------------------------------------ centre body
# One wide, flat body from the strakes beside the cockpit to the engines' end: the wing's roots are its edges, the
# canards stand on its shoulders, the intakes hang under it. Seen in a station it is a lens: `crown` in the
# middle, the edge at `DK_W`, between them the profile `g`. Under it, between the engines, the belly.

DK_W = Pchip([(5.6, 0.745), (6.2, 0.86), (6.8, 1.02), (7.3, 1.28), (7.7, 1.62), (8.0, 1.86), (8.3, 2.0), (19.05, 2.0)])
DK_YE = Pchip([(5.6, 2.64), (7.5, 2.64), (8.3, 2.68), (10.3, 2.68), (10.9, 2.57), (19.05, 2.56)])
DK_TE = Pchip([(5.6, 0.03), (7.5, 0.03), (7.9, 0.12), (10.2, 0.13), (10.45, 0.05), (11.0, 0.04), (19.05, 0.08)])
DK_CROWN = Pchip([(5.6, 2.70), (7.0, 2.74), (8.3, 2.85), (9.5, 2.93), (10.5, 3.0), (12.0, 3.06), (14.0, 3.06), (16.0, 3.0),
                  (17.5, 2.88), (19.05, 2.66)])
DK_ROOF = Pchip([(5.6, 2.58), (7.0, 2.55), (8.3, 2.47), (10.0, 2.40), (12.0, 2.35), (19.05, 2.35)])
DK_BELLY = Pchip([(5.6, 2.58), (7.0, 2.55), (8.3, 2.47), (9.0, 2.44), (10.0, 2.10), (11.0, 1.82), (12.0, 1.75), (16.5, 1.78),
                  (18.0, 2.0), (19.05, 2.28)])
DK_XI = [0.0, 0.11, 0.22, 0.31, 0.42, 0.54, 0.66, 0.76, 0.84, 0.90, 0.95, 0.98, 1.0]
DK_STATIONS = [5.6, 5.9, 6.2, 6.5, 6.8, 7.05, 7.3, 7.5, 7.7, 7.85, 8.0, 8.15, 8.3, 8.6, 9.0, 9.5, 10.0, 10.2, 10.35, 10.45,
               10.6, 10.8, 11.1, 11.5, 12.0, 12.6, 13.2, 14.0, 14.8, 15.6, 16.3, 16.8, 17.15, 17.5, 18.0, 18.5, 19.05]
TUNNEL = 0.44                    # half width of the belly between the engines


def dk_g(xi):
    return (1 - xi ** 2.4) ** 1.3


def dk_edge(d):
    """the edge's upper and lower height: the wing's root section where the wing is"""
    ye, te = DK_YE(d), DK_TE(d)
    top, bot = ye + te / 2, ye - te / 2
    w = wing_surface_at(WING_ROOT, d)
    if w:
        top, bot = max(top, w[0]), min(bot, w[1])
    return top, bot


def dk_top(d, x):
    w = DK_W(d)
    top, _ = dk_edge(d)
    return top + (DK_CROWN(d) - top) * dk_g(min(1.0, abs(x) / w))


def dk_bottom(d, x):
    w = DK_W(d)
    _, bot = dk_edge(d)
    lens = bot + (DK_ROOF(d) - bot) * dk_g(min(1.0, abs(x) / w))
    c = smoothstep(TUNNEL, TUNNEL + 0.18, abs(x))
    return lerp(DK_BELLY(d), lens, c)


def deck_skins(atlas):
    L = DK_STATIONS[-1] - DK_STATIONS[0]
    top = atlas.sheet('deck_top', (L, 2.1))
    bot = atlas.sheet('deck_bottom', (L, 2.1), density=0.8)
    rt, rb, ut, ub = [], [], [], []
    for d in DK_STATIONS:
        w = DK_W(d)
        et, eb = dk_edge(d)
        u = d - DK_STATIONS[0]
        # the edge is rounded by one point a little outside its middle
        rim = (w + 0.35 * (et - eb), (et + eb) / 2, Z(d))
        rt.append([(w * xi, dk_top(d, w * xi), Z(d)) for xi in DK_XI] + [rim])
        ut.append([(u, w * xi) for xi in DK_XI] + [(u, w + 0.05)])
        rb.append([rim] + [(w * xi, dk_bottom(d, w * xi), Z(d)) for xi in reversed(DK_XI)])
        ub.append([(u, w + 0.05)] + [(u, w * xi) for xi in reversed(DK_XI)])
    skins = [S.Skin('deck_top', top, rt, ut, mirror=True, out='up'), S.Skin('deck_bottom', bot, rb, ub, mirror=True, out='down')]
    # closed at the back (between the engines' fairings and the booms)
    skins.append(S.Skin('deck_end', bot, [rt[-1][:-1], list(reversed(rb[-1][1:]))], [ub[-1][1:], ub[-1][1:]], mirror=True,
                        out=(0.0, 0.0, -1.0)))
    return skins


# the flat tail between the nozzles
BV_STATIONS = [18.4, 18.8, 19.05, 19.4, 19.7, 19.95]
BV_W = Pchip([(18.4, 0.43), (19.05, 0.43), (19.95, 0.37)])
BV_TOP = Pchip([(18.4, 2.72), (18.8, 2.69), (19.05, 2.66), (19.4, 2.61), (19.7, 2.56), (19.95, 2.52)])
BV_BOT = Pchip([(18.4, 2.20), (18.8, 2.24), (19.05, 2.28), (19.4, 2.38), (19.7, 2.45), (19.95, 2.495)])


def beaver_skins(atlas):
    sheet = atlas.sheet('beaver', (BV_STATIONS[-1] - BV_STATIONS[0], 1.3))
    rows = []
    for d in BV_STATIONS:
        w, top, bot = BV_W(d), BV_TOP(d), BV_BOT(d)
        yc, h = (top + bot) / 2, (top - bot) / 2
        ring = []
        for k in range(11):
            a = -math.pi / 2 + math.pi * k / 10
            c, s = max(0.0, math.cos(a)), math.sin(a)
            ring.append((w * c ** 0.45, yc + h * math.copysign(abs(s) ** 0.45, s), Z(d)))
        ring[0] = (0.0, bot, Z(d))
        ring[-1] = (0.0, top, Z(d))
        rows.append(ring)
    uv = S.loft_uv(rows, [d - BV_STATIONS[0] for d in BV_STATIONS], 1.3)
    end = rows[-1]
    mid = [(0.0, (p[1] + end[0][1] + end[-1][1]) / 3, p[2]) for p in end]
    return [S.Skin('beaver', sheet, rows, uv, mirror=True),
            S.Skin('beaver_end', sheet, [end, mid], [uv[-1], uv[-1]], mirror=True, out=(0.0, 0.0, -1.0))]


# ------------------------------------------------------------------------------------------------ nacelles
# The intakes under the shoulders: a mouth with a flat roof and inner wall and a round outer lower corner, raked
# back from the roof to the lower lip; behind it the trunk grows round into the engine's bay.

NC_X, NC_Y, NC_R = 1.22, 2.0, 0.78
NC_LIP = 8.35                    # the lower lip; the roof's edge is NC_RAKE further forward
NC_RAKE = 0.6
NC_MOUTH = {'x0': 0.80, 'x1': 1.98, 'y0': 1.30, 'y1': 2.64}
NC_ROUND = 12.5                  # round from here on
NC_END = 19.05
NC_M = 40
NC_RADIUS = Pchip([(8.0, NC_R), (17.4, NC_R), (18.3, 0.765), (NC_END, 0.745)])
# the trunk's axis rises a little towards the nozzle (the underside's line in the side view)
NC_YC = Pchip([(8.0, NC_Y), (13.5, NC_Y), (16.5, NC_Y + 0.06), (NC_END, NC_Y + 0.12)])
NC_STATIONS = [NC_LIP, 8.5, 8.7, 9.0, 9.4, 9.9, 10.5, 11.2, 12.0, 12.5, 13.3, 14.2, 15.2, 16.2, 17.0, 17.6, 18.2, 18.7, NC_END]
NC_GIRTH = 3.9


def mouth_outline(inset=0.0):
    """the mouth's section as NC_M points from the roof's middle outwards, down and round"""
    m = NC_MOUTH
    x0, x1, y0, y1 = m['x0'] + inset, m['x1'] - inset, m['y0'] + inset, m['y1'] - inset
    pts = [((x0 + x1) / 2, y1), (x1, y1), (x1, y0), (x0, y0), (x0, y1)]
    rad = [0.0, 0.09, max(0.1, 0.78 - inset), 0.16, 0.06]
    return K.resample(K.round_poly(pts, rad, seg=8), NC_M, closed=True)


def circle_outline(r, y=NC_Y):
    return [(NC_X + r * math.cos(math.pi / 2 - 2 * math.pi * k / NC_M), y + r * math.sin(math.pi / 2 - 2 * math.pi * k / NC_M))
            for k in range(NC_M)]


def nacelle_ring(d, inset=0.0):
    """the section at a station as a closed ring (the first point again at the end): the mouth's shape growing
    round, its plane raked at the lip"""
    s = smoothstep(NC_LIP, NC_ROUND, d)
    a, b = mouth_outline(inset), circle_outline(NC_RADIUS(d) - inset, NC_YC(d))
    rake = NC_RAKE * (1 - smoothstep(NC_LIP, 9.6, d))
    m = NC_MOUTH
    ring = []
    for (ax, ay), (bx, by) in zip(a, b):
        x, y = lerp(ax, bx, s), lerp(ay, by, s)
        ring.append((x, y, Z(d - rake * (y - m['y0']) / (m['y1'] - m['y0']))))
    return ring + [ring[0]]


def nacelle_skins(atlas):
    sheet = atlas.sheet('nacelle', (NC_END - 7.7, NC_GIRTH), density=0.85)
    duct = atlas.sheet('duct', (3.2, 1.6), density=0.5)
    rows = [nacelle_ring(d) for d in NC_STATIONS]
    uv = S.loft_uv(rows, [d - 7.7 for d in NC_STATIONS], NC_GIRTH)
    skins = [S.Skin('nacelle', sheet, rows, uv, mirror=True)]
    # the lip rolls over into the duct, which runs back into the dark
    lip = rows[0]
    inner = nacelle_ring(NC_LIP, 0.045)
    mid = [((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (a[2] + b[2]) / 2 + 0.03) for a, b in zip(lip, inner)]
    deep = [nacelle_ring(d, 0.045 + 0.02 * k) for k, d in enumerate((8.9, 9.8, 11.0))]
    rows_d = [lip, mid, inner] + deep
    us = [0.0, 0.05, 0.1, 0.7, 1.6, 2.8]
    skins.append(S.Skin('duct', duct, rows_d, S.loft_uv(rows_d, us, 1.6), mirror=True, out='in'))
    back = deep[-1]
    c = np.mean(np.array(back[:-1]), axis=0)
    skins.append(S.Skin('duct_end', duct, [back, [tuple(c)] * len(back)], [[(3.1, 0.8)] * len(back)] * 2, mirror=True,
                        out=(0.0, 0.0, 1.0)))
    return skins


# ------------------------------------------------------------------------------------------------ tail booms
# Outboard of the nozzles, carrying the fins and the tailplanes, of unequal length: the left one the shorter (the
# rear radar's), the right one the longer (the brake parachute's).

BOOM_X, BOOM_Y = 2.32, 2.56
BOOM_COMMON = [(15.0, 0.02), (15.6, 0.20), (16.4, 0.34), (19.6, 0.34)]
BOOM_END = {'l': [(20.2, 0.30), (20.8, 0.20), (21.15, 0.10), (21.3, 0.02)],
            'r': [(20.6, 0.33), (21.4, 0.29), (22.0, 0.20), (22.4, 0.11), (LENGTH, 0.02)]}
BOOM_TIP = {'l': 20.45, 'r': 21.6}        # white (dielectric) from here to the end


def boom_skin(atlas, side):
    prof = Pchip(BOOM_COMMON + BOOM_END[side])
    end = BOOM_END[side][-1][0]
    ds = [15.0, 15.3, 15.6, 16.0, 16.4, 17.2, 18.0, 18.8, 19.6] + [p[0] for p in BOOM_END[side]]
    extra = [(ds[k] + ds[k + 1]) / 2 for k in range(9, len(ds) - 1)]
    ds = sorted(ds + extra)
    sheet = atlas.sheet(f'boom_{side}', (end - 15.0, 2.0), density=0.9)
    rows = []
    for d in ds:
        a = prof(d)
        ring = []
        for k in range(20):
            t = math.pi + 2 * math.pi * k / 20          # the seam on the inboard side
            c, s = math.cos(t), math.sin(t)
            ring.append((BOOM_X + a * math.copysign(abs(c) ** 0.9, c), BOOM_Y + 0.88 * a * math.copysign(abs(s) ** 0.9, s), Z(d)))
        rows.append(ring + [ring[0]])
    uv = S.loft_uv(rows, [d - 15.0 for d in ds], 2.0)
    return S.Skin(f'boom_{side}', sheet, rows, uv)


# ------------------------------------------------------------------------------------------------ nozzles
# The D-30F11's long afterburner nozzle, drawn closed down (military power): the outer flaps narrowing to the exit,
# inside them the divergent flaps, the throat and the dark of the jet pipe.

NOZZLE_OUT = [(0.745, 0.0), (0.74, 0.07), (0.722, 0.10), (0.70, 0.5), (0.65, 0.92), (0.60, 1.25)]
NOZZLE_IN = [(0.60, 1.25), (0.575, 1.24), (0.555, 0.9), (0.50, 0.45), (0.55, 0.1), (0.62, -0.25), (0.0, -0.25)]
NOZZLE_EXIT = NC_END + 1.25
NOZZLE_Y = NC_Y + 0.12                    # = NC_YC(NC_END)


def nozzle_skins(atlas):
    out = atlas.sheet('nozzle_out', (1.3, 2.4))
    inn = atlas.sheet('nozzle_in', (2.0, 2.4), density=0.6)
    M = 48

    def rows_of(profile):
        rows, us = [], []
        s = 0.0
        for k, (r, a) in enumerate(profile):
            if k:
                s += math.hypot(r - profile[k - 1][0], a - profile[k - 1][1])
            ring = [(NC_X + r * math.cos(2 * math.pi * i / M), NOZZLE_Y + r * math.sin(2 * math.pi * i / M), Z(NC_END + a)) for i in range(M)]
            rows.append(ring + [ring[0]])
            us.append(s)
        return rows, us

    ro, uo = rows_of(NOZZLE_OUT)
    ri, ui = rows_of(NOZZLE_IN)
    uvo = [[(u, 2.4 * i / M) for i in range(M + 1)] for u in uo]
    uvi = [[(u, 2.4 * i / M) for i in range(M + 1)] for u in ui]
    return [S.Skin('nozzle_out', out, ro, uvo), S.Skin('nozzle_in', inn, ri, uvi, out='in')]


# ------------------------------------------------------------------------------------------------ all of it

def planform_area():
    """the wing's reference area: both panels and the part of the body between them (the trailing and leading
    edges carried to the middle)"""
    n = 400
    area = 0.0
    for k in range(n):
        x = (k + 0.5) / n * WING_TIP
        if x >= WING_ROOT:
            area += wing_station(x)[1]
        else:
            main = WING_TIP_LE + (WING_TIP - x) * WING_LE_SWEEP
            area += wing_te(x) - main
    return 2 * area * WING_TIP / n
