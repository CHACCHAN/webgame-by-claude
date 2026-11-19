"""
The cockroach's back, what the wings uncover in flight (game frame, real mm; see roach_geom and roach_anatomy DORSUM /
PLATES): the mesonotum and the metanotum with the mounds the wings are hinged on, the abdomen's tergites lying over
one another like roof tiles, the supra-anal plate between the cerci, and the few bristles on its margins.

The surface is one function, `dorsum_y(x, z)`: the tegmina's envelope less what the folded wings need, nearly flat
across, falling to a sharp lateral margin (`half(z)`). A plate is a thin closed shell lofted across the body along
lines of constant u = x / half(z): its top rises from its front (under the plate before it) to its hind margin,
which stands a step above the next plate. `plate_of` tells the texture which plate a point of the back belongs to;
everything here takes numpy arrays as well as numbers.
"""
import math

import numpy as np

import roach_anatomy as A
from roach_geom import Part, bristle, smoothstep, unit
from roach_tex import LAYOUT

D = A.DORSUM
# the flat projections of the two patches of the atlas: (x0, x1, z0, z1)
NOTA_BOX = (-5.9, 5.9, -14.9, -6.7)
TERG_BOX = (-6.4, 6.4, -34.6, -13.4)

_Z = np.linspace(-35.0, -6.8, 1129)
_ENV_TOP = np.array([A.smooth_interp(A.ENV_TOP, z) for z in _Z])
_ENV_DROP = np.array([A.smooth_interp(A.ENV_DROP, z) for z in _Z])
_OFF = np.array([A.interp(D['off'], z)[0] for z in _Z])
_HALF = np.array([A.smooth_interp(D['half'], z) for z in _Z])
_SAG = np.array([A.interp(D['sag'], z)[0] for z in _Z])
HIND_Z = A.HIND['hinge'][1]


def env(x, z):
    """the envelope the tegmina lie on (roach_anatomy.env_y, for arrays)"""
    return np.interp(z, _Z, _ENV_TOP) - np.interp(z, _Z, _ENV_DROP) * (np.abs(x) / A.ENV_A) ** A.ENV_P


def half(z):
    return np.interp(z, _Z, _HALF)


def dorsum_y(x, z):
    """the back's surface: as high as the folded wings allow"""
    x = np.asarray(x, float)
    z = np.asarray(z, float)
    ax = np.abs(x)
    u = np.minimum(ax / half(z), 1.2)
    y = np.interp(z, _Z, _ENV_TOP) - np.interp(z, _Z, _OFF) - np.interp(z, _Z, _SAG) * u ** D['p']
    # under the hind wings (behind their hinge, as far out as their leading edges) more must stay free
    mid = D['clear_fore'] + (D['clear'] - D['clear_fore']) * smoothstep(HIND_Z + 0.7, HIND_Z + 0.1, z)
    c = D['clear_side'] + (mid - D['clear_side']) * (1 - smoothstep(4.2, 4.7, ax))
    return np.minimum(y, env(x, z) - c)


# ---------------------------------------------------------------- the plates

N_PLATES = len(A.PLATES)
NAMES = [p['name'] for p in A.PLATES]


def hind(k, u):
    """z of plate k's hind margin at u = |x| / half (0 the midline … 1 the lateral margin)"""
    P = A.PLATES[k]
    u = np.asarray(u, float)
    sw = P['sweep']
    if 'notch' in P:
        depth, width = P['notch']
        return P['hind'] - sw * u ** 4 + depth * np.exp(-(u / width) ** 2)
    if sw < 0:
        # longest in the middle (a notum's scutellum)
        return P['hind'] - sw * (1 - (1 - u * u) ** 2)
    return P['hind'] - sw * u ** 4


def seen(k, u):
    """z from which plate k is seen: the hind margin of the plate before it"""
    return np.full_like(np.asarray(u, float), A.NOTA_FRONT) if k == 0 else hind(k - 1, u)


def front(k, u):
    """z of plate k's front edge, under the plate before it"""
    return seen(k, u) if k == 0 else seen(k, u) + D['tuck']


def step_of(k, u):
    return A.PLATES[k].get('step', D['step']) * (1 - 0.55 * np.asarray(u, float) ** 6)


def plate_top(k, u, z):
    """(x, y) of plate k's upper surface on the line u at z"""
    zs, zh = seen(k, u), hind(k, u)
    tv = (zs - z) / (zs - zh)
    g = (1 - np.clip(tv, 0.0, 1.0)) ** 1.4 + 0.2 * np.clip(-tv, 0.0, 1.0)
    x = u * half(z)
    # (the hind margin turns down a touch)
    y = dorsum_y(x, z) - step_of(k, abs(u)) * g - 0.035 * smoothstep(0.9, 1.0, tv)
    return x, y


def plate_of(x, z):
    """which plate is seen at (x, z) of the back: its index, how far along it (0 where it comes out from under the
    plate before it … 1 its hind margin), mm from that front and mm to the hind margin, and u"""
    x = np.asarray(x, float)
    z = np.asarray(z, float)
    u = np.clip(np.abs(x) / half(z), 0.0, 1.0)
    k = np.zeros(x.shape, np.int64)
    zs = seen(0, u) + 0 * z
    zh = hind(0, u) + 0 * z
    for i in range(1, N_PLATES):
        m = z < hind(i - 1, u)
        k = np.where(m, i, k)
        zs = np.where(m, hind(i - 1, u), zs)
        zh = np.where(m, hind(i, u), zh)
    s = np.clip((zs - z) / (zs - zh), 0.0, 1.0)
    return k, s, zs - z, z - zh, u


US = [math.sin(math.pi / 2 * (i - 12) / 12) for i in range(25)]
TS = {'meso': (0.0, 0.15, 0.35, 0.55, 0.75, 0.9, 1.0), 'meta': (0.0, 0.15, 0.35, 0.55, 0.75, 0.9, 1.0),
      'T8': (0.0, 0.5, 1.0), 'T9': (0.0, 0.5, 1.0), 'T10': (0.0, 0.2, 0.45, 0.7, 0.88, 1.0)}
TS_TERGITE = (0.0, 0.2, 0.5, 0.82, 1.0)


def _uv(box, region):
    x0, x1, z0, z1 = box
    u0, v0, u1, v1 = region
    return lambda p: (u0 + (u1 - u0) * (p[0] - x0) / (x1 - x0), v0 + (v1 - v0) * (p[2] - z0) / (z1 - z0))


def build_plate(k):
    name = NAMES[k]
    nota = k < 2
    part = Part('plate_' + name, 'roach_body')
    rings = []
    for u in US:
        au = abs(u)
        zf, zh = float(front(k, au)), float(hind(k, au))
        th = D['thick'] * (1 - 0.45 * au ** 8)
        loop = []
        for t in TS.get(name, TS_TERGITE):
            z = zf + (zh - zf) * t
            x, y = plate_top(k, u, z)
            loop.append((float(x), float(y), z))
        xh, yh = (float(v) for v in plate_top(k, u, zh))
        # the hind margin's rounded edge, then back underneath
        loop.append((u * float(half(zh - 0.035)), yh - 0.5 * th - 0.01, zh - 0.035))
        z1 = zh + min(0.14, 0.4 * (zf - zh))
        loop.append((u * float(half(z1)), yh - th - 0.02, z1))
        zm = (zf + zh) / 2
        if zm > z1 + 0.05:
            loop.append((u * float(half(zm)), float(plate_top(k, u, zm)[1]) - th, zm))
        loop.append((u * float(half(zf)), float(plate_top(k, u, zf)[1]) - th, zf))
        rings.append(loop)
    box, region = (NOTA_BOX, LAYOUT['nota']) if nota else (TERG_BOX, LAYOUT['tergites'])
    part.plate(rings, _uv(box, region), {'thorax': 1.0} if nota else {'abdomen': 1.0})
    return part


# ---------------------------------------------------------------- the wings' roots

def root_top(kind, side=1):
    """how high a mound may stand: just under the folded wing at its hinge"""
    if kind == 'tegmen':
        x, z = A.TEGMEN_HINGE
        return float(env(x, z)) - 0.03
    x, z = A.HIND['hinge']
    return float(env(x, z)) - A.HIND['depth'] - 0.095 - 0.02


def build_roots():
    """
    Where the wings are hinged: a mound each on the notum's side (the wing process and the small sclerites of the
    wing's base, in one piece), reaching up to the hinge, so that an open wing stands on the back.
    """
    from roach_body import ellipsoid
    parts = []
    X, Y, Z = np.array((1.0, 0.0, 0.0)), np.array((0.0, 1.0, 0.0)), np.array((0.0, 0.0, 1.0))
    for kind, (hx, hz), rx, rz, dz in (('tegmen', A.TEGMEN_HINGE, 0.62, 1.25, -0.25), ('hind', A.HIND['hinge'], 0.52, 0.95, -0.2)):
        for side in (1, -1):
            part = Part(f'root_{kind}_{"L" if side > 0 else "R"}', 'roach_body')
            x, z = side * hx, hz + dz
            base = float(dorsum_y(x, z)) - 0.12
            top = root_top(kind)
            c = np.array((x, base, z))
            ellipsoid(part, c, X * side, Y, Z, rx, top - base, rz, LAYOUT['root'], {'thorax': 1.0}, n=10, m=6)
            parts.append(part)
    return parts


# ---------------------------------------------------------------- bristles on the margins

def build_margin_setae():
    """the fringe of the supra-anal plate and the bristles on the drawn-out hind corners of the rear tergites"""
    part = Part('margin_setae', 'roach_body')
    w = {'abdomen': 1.0}
    region = LAYOUT['seta']
    k10 = NAMES.index('T10')
    for sgn in (1, -1):
        for i, u in enumerate((0.2, 0.38, 0.56, 0.72, 0.86, 0.97)):
            z = float(hind(k10, u))
            x, y = (float(v) for v in plate_top(k10, sgn * u, z))
            d = unit((sgn * (0.25 + 0.75 * u), -0.12, -1.0 + 0.5 * u))
            bristle(part, (x, y - 0.06, z + 0.03), d, 0.34 + 0.12 * math.sin(2.1 * i + 0.4), 0.04, region, w)
        for name in ('T4', 'T5', 'T6', 'T7'):
            k = NAMES.index(name)
            for u, ln in ((0.99, 0.5), (0.93, 0.38)):
                z = float(hind(k, u))
                x, y = (float(v) for v in plate_top(k, sgn * u, z))
                d = unit((sgn * 0.55, -0.1, -0.83))
                bristle(part, (x - sgn * 0.03, y - 0.06, z + 0.03), d, ln, 0.045, region, w)
    return part


def build():
    parts = [build_plate(k) for k in range(N_PLATES)]
    parts += build_roots()
    parts.append(build_margin_setae())
    return parts


def clearance():
    """what is left between the back and the folded wings, and between the back and the bodies under it (mm; all
    should be positive): printed by roach.py"""
    import roach_body as RB
    rep = {}
    worst_t, worst_h, worst_tube = 9.0, 9.0, 9.0
    for k in range(N_PLATES):
        for u in np.linspace(-1, 1, 41):
            au = abs(u)
            zf, zh = float(front(k, au)), float(hind(k, au))
            for t in np.linspace(0, 1, 15):
                z = zf + (zh - zf) * t
                x, y = (float(v) for v in plate_top(k, u, z))
                e = float(env(x, z))
                worst_t = min(worst_t, e + 0.01 - 0.12 - y)                 # the tegmen's underside (its margin droops)
                if z < HIND_Z and abs(x) <= A.HIND['hinge'][0] + 0.05:
                    worst_h = min(worst_h, e - A.HIND['depth'] - 0.095 - y)  # the hind wing's (its thick base)
                # the tube underneath must not come through the part of a plate that is seen
                if z <= float(seen(k, au)) and z > A.ABDOMEN[-1][0] and z < A.ABDOMEN[0][0] - 0.3:
                    worst_tube = min(worst_tube, y - RB.abdomen_y(x, z))
    rep['under_tegmina'] = round(worst_t, 3)
    rep['under_hind_wings'] = round(worst_h, 3)
    rep['over_abdomen_tube'] = round(worst_tube, 3)
    return rep
