"""
JR Central L0 series (L0系, the first set of 2013, 900 numbers): the body's shape as numbers, shared by the shells,
the painted atlas, the parts on the body and the photo fit (fitdata/l0/tools). Pure numpy, no Blender.

Frame: the game's car frame (metres; +x = the car's left, +y up from the guideway's running surface / the road, +z
forward). An end car has its nose at +z; d = NOSE_TIP − z is the distance back from the nose tip.

Published figures (ja.wikipedia L0系, en.wikipedia L0 Series, read 2026-11-10): end cars 28.0 m, middle cars 24.3 m,
width 2,900 mm, height 3,100 mm, a nose "15 m" long; articulated (Jacobs bogies under the car joints); one door a side
per car; 24 passengers in an end car (6 rows of 4), 68 in a middle car (17 rows); white with blue lines: the blue
lines run up the nose onto the roof, two blue lines along the side above the windows; a logo on the side. No cab
windscreen: a forward camera on the nose.
Game consist (vehicle/trains.ts): end cars 28 m with the leading bogie 13.5 m behind the tip (estimated) and the
trailing one under the joint; middle car 24.3 m between the joints. So in a car's own frame (origin halfway between its
bogies): end car tip at z = +20.75 (the photos put the face at +20.58: NOSE_TIP), joint at −7.25; middle car joints
at ±12.15.

The shape: each section is two superellipse quadrants (upper and lower) meeting at the widest line (height yw, half
width hw); along the nose their parameters follow the table _NOSE (rows by d), faired. Numbers marked "fit" come from
the photo fit (fitdata/l0: cameras solved on the Commons photos listed in fitdata/l0/ref/list.json, silhouettes and
livery points compared); the rest are estimates.
"""
import math

import numpy as np

# ---------------------------------------------------------------- the cars
HW = 1.45                # half the body width (2,900 mm)
ROOF = 3.10              # roof at the centre line (3,100 mm)
REF_TIP = 20.75          # end car: z of the nose tip by the published 28.0 m (the livery's d is measured from here)
NOSE_TIP = 20.583        # fit: the tip as the photos put it, 0.17 m behind REF_TIP (27.83 m from the joint)
JOINT_END = -7.25        # end car: z of the joint behind it (28.0 m from REF_TIP)
JOINT_MID = 12.15        # middle car: joints at ±12.15 (24.3 m)
BOGIE_FRONT = 7.25       # end car: the leading bogie (13.5 m behind REF_TIP, estimated; 13.33 m behind the tip)
GAP = 0.20               # a car body's end face stands GAP short of the joint (the hood bridges 2 × GAP)
END_R = 0.16             # rounding of a body end's edges
CAR_Z = {'car0': 0.0, 'car1': -19.4, 'car2': -38.8}      # the cars along the train (car2 turned round)

# body section (also the nose's sections at d ≥ NOSE_LEN)
BODY = dict(top=ROOF, yw=1.80, hw=HW, bot=0.42, nt=3.6, nb=3.4, lean=0.035, tuck=0.10)
_KEYS = ('top', 'yw', 'hw', 'bot', 'nt', 'nb', 'lean', 'tuck')

NOSE_LEN = 16.0
# the snout's face: a blunt cap. Sections nearer the tip than df are the section at df shrunk towards the face's centre
# (x 0, y yc) by s = (1 − (1 − d/df)^m)^(1/m): a superellipse in profile and plan (m 2 round, higher flatter).
CAP = dict(df=0.40, yc=0.405, m=2.684)        # fit
# d, then the section's parameters (see half_section): the nose's top line, widest line and its half width, keel,
# the upper and lower superellipses' exponents, the upper side's lean in and the lower side's tuck.
# fit: top, yw, hw (and bot, nt, nb for d <= 1.8), the face's cap and the tip's z from the silhouettes of photos c04,
# c07, c12, the livery points and the lamp panel's traced corners, cameras solved together (fitdata/l0/tools/fit.py,
# round gC: IoU 0.951 / 0.963 / 0.939); the other exponents, lean and tuck are estimates and the keel further back is
# hidden by the guideway walls on every photo. The photos put the face 0.17 m behind the published length (the fixed
# tip gave c07 twice the residual): the model keeps the photos' tip (NOSE_TIP), the livery keeps REF_TIP's frame.
_NOSE = [
    # d      top    yw     hw     bot    nt   nb    lean   tuck   (the rows nearer than CAP['df'] are not used)
    (0.00, 1.478, 0.718, 1.223, 0.625, 2.680, 2.186, 0.020, 0.020),
    (0.40, 1.478, 0.718, 1.223, 0.625, 2.680, 2.186, 0.020, 0.020),
    (0.60, 1.474, 0.767, 1.261, 0.613, 2.357, 2.397, 0.030, 0.030),
    (0.90, 1.471, 0.845, 1.290, 0.587, 2.726, 2.500, 0.040, 0.040),
    (1.80, 1.462, 1.028, 1.288, 0.479, 2.284, 2.702, 0.060, 0.060),
    (3.20, 1.545, 1.264, 1.291, 0.360, 2.500, 2.900, 0.070, 0.080),
    (5.20, 1.657, 1.401, 1.450, 0.380, 2.600, 3.100, 0.080, 0.090),
    (7.60, 1.807, 1.516, 1.450, 0.400, 2.800, 3.200, 0.070, 0.100),
    (10.00, 2.233, 1.626, 1.450, 0.410, 3.000, 3.300, 0.060, 0.100),
    (12.40, 2.580, 1.762, 1.450, 0.420, 3.300, 3.400, 0.045, 0.100),
    (14.20, 3.116, 1.796, 1.450, 0.420, 3.500, 3.400, 0.038, 0.100),
    (16.00, 3.100, 1.800, 1.450, 0.420, 3.600, 3.400, 0.035, 0.100),
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
    m[0], m[-1] = dlt[0], 0.0 if abs(dlt[-1]) < 1e-9 else dlt[-1]

    def f(x):
        x = np.clip(np.asarray(x, float), xs[0], xs[-1])
        i = np.clip(np.searchsorted(xs, x) - 1, 0, len(xs) - 2)
        t = (x - xs[i]) / h[i]
        h00, h10, h01, h11 = 2 * t ** 3 - 3 * t ** 2 + 1, t ** 3 - 2 * t ** 2 + t, -2 * t ** 3 + 3 * t ** 2, t ** 3 - t ** 2
        return h00 * ys[i] + h10 * h[i] * m[i] + h01 * ys[i + 1] + h11 * h[i] * m[i + 1]
    return f


pchip = _pchip_table


class Nose:
    """the nose's parameter curves (from a table, faired); `set_table` swaps the table (the fit)"""

    def __init__(self, table=None, body=None):
        self.set_table(table or _NOSE, body or BODY)

    def set_table(self, table, body=None):
        self.table = [tuple(float(v) for v in r) for r in table]
        self.body = dict(body or self.body)
        ds = [r[0] for r in self.table]
        self.f = {k: _pchip_table(ds, [r[i + 1] for r in self.table]) for i, k in enumerate(_KEYS)}
        g = np.linspace(0.0, NOSE_LEN, 1601)
        self.grid = g
        self.g = {k: self._faired(g, f(g)) if k not in ('hw',) else f(g) for k, f in self.f.items()}

    _W = None

    @classmethod
    def _weights(cls, d):
        if cls._W is None:
            sig = np.clip(0.06 * d, 0.01, 0.35)[:, None]
            w = np.exp(-0.5 * ((d[None, :] - d[:, None]) / sig) ** 2)
            wr = np.exp(-0.5 * ((2 * d[-1] - d[None, :] - d[:, None]) / sig) ** 2)
            cls._W = (w, wr, w.sum(1) + wr.sum(1))
        return cls._W

    @classmethod
    def _faired(cls, d, v):
        """the pchip curves are only C1: a light Gaussian fairing (tight at the tip, up to ±0.35 m along the nose)"""
        w, wr, n = cls._weights(d)
        out = (w @ v + wr @ (2 * v[-1] - v)) / n
        k = d < 0.05            # keep the tip's own values
        out[k] = v[k]
        return out

    def params(self, d):
        if d >= NOSE_LEN:
            return dict(self.body)
        d = max(d, 0.0)
        df = CAP['df']
        if d < df:
            # the snout's blunt face: the section at df shrunk towards the face's centre
            p = self.params(df)
            t = 1.0 - d / df
            sc = (1.0 - t ** CAP['m']) ** (1.0 / CAP['m'])
            yc = CAP['yc']
            for k in ('top', 'yw', 'bot'):
                p[k] = yc + sc * (p[k] - yc)
            p['hw'] *= sc
            return p
        return {k: float(np.interp(d, self.grid, v)) for k, v in self.g.items()}


NOSE = Nose()


def set_nose(table=None, body=None, cap=None, tip=None):
    """replace the nose table (fit tools); body: section parameters of the body; cap: the face (CAP); tip: z of the
    nose tip"""
    global BODY, NOSE_TIP
    if body:
        BODY = dict(body)
    if cap:
        CAP.update(cap)
    if tip is not None:
        NOSE_TIP = float(tip)
    NOSE.set_table(table or NOSE.table, BODY)


def load_shape(sh):
    """a fit's shape file (dict): nose table, body, cap, tip"""
    set_nose(sh.get('nose'), sh.get('body'), sh.get('cap'), sh.get('tip'))


# ---------------------------------------------------------------- the lamp panel on the snout's face
# laid on the shell along −z (as the game lays its lamp lenses). Measured through the solved cameras on the outlines
# traced on c12 (head-on from 200 m, head lamps lit: the most reliable for x and y) and c07 (close, from above; its y
# reads 2–3 cm higher), fitdata/l0/lamps.json + tools/measure.py; the bundle adjustment (ba.py) agrees within 1 cm:
# two lamp windows x ±0.20 … ±0.62, y 0.745–0.868 (c07 and c12 agree within 1.5 cm on the fitted shell); two round
# head lamps in the outer part of each (c12, lit: x ±0.407, ±0.540, y 0.80); the inner one reads red behind the glass on
# c07 (a red element seen at x 0.35–0.43 on the glass from above and to the side: behind it, further out and lower, at
# the inner lamp), so a white/red lamp; a camera window on the centre line 0.150 × 0.115 m at the windows' height, and
# a smaller one below it, 0.125 × 0.082 m at y 0.57 (c07).
LAMP_WIN = (0.20, 0.62, 0.745, 0.868, 0.03)            # x0, x1, y0, y1, corner radius
HEAD_X = (0.407, 0.542)
HEAD_Y = 0.80
HEAD_R = 0.036
TAIL_X = HEAD_X[0]                                     # the inner lamp shows red too (c07; white when lit on c12)
CAM_WIN = (0.0, 0.807, 0.150, 0.115)                   # x, y, w, h
CAM_LOW = (0.0, 0.570, 0.125, 0.082)


# ---------------------------------------------------------------- the half section
N_LOW = 16               # points on the lower quadrant (bottom centre excluded … the widest point included)
N_UP = 30                # points on the upper quadrant (… the roof's centre line)
HALF_N = 1 + N_LOW + N_UP
J_WIDE = N_LOW           # index of the widest point


def _quadrant(n, k, samples=400):
    """unit superellipse quadrant (x = cos^(2/n), y = sin^(2/n)) from (1, 0) to (0, 1), k + 1 points evenly spaced
    by arc length (the same fractions on every section, so the loft's topology holds)"""
    t = np.linspace(0.0, math.pi / 2, samples)
    c, s = np.cos(t), np.sin(t)
    x = np.abs(c) ** (2.0 / n)
    y = np.abs(s) ** (2.0 / n)
    L = np.concatenate([[0.0], np.cumsum(np.hypot(np.diff(x), np.diff(y)))])
    u = np.linspace(0.0, L[-1], k + 1)
    return np.interp(u, L, x), np.interp(u, L, y)


def half_section(p):
    """[(x, y)] from the bottom centre (x = 0) up the left side (+x) to the roof's centre line; HALF_N points"""
    top, yw, hw, bot = p['top'], p['yw'], p['hw'], p['bot']
    xl, yl = _quadrant(p['nb'], N_LOW)
    xu, yu = _quadrant(p['nt'], N_UP)
    hb, ht = max(yw - bot, 1e-6), max(top - yw, 1e-6)
    pts = []
    # lower: from the bottom centre (quadrant end) to the widest point
    for x, y in zip(xl[::-1], yl[::-1]):
        Y = yw - hb * y
        X = hw * x * (1.0 - p['tuck'] * y)
        pts.append((X, Y))
    # upper: from the widest point (excluded: already there) to the top centre
    for x, y in zip(xu[1:], yu[1:]):
        Y = yw + ht * y
        X = hw * x * (1.0 - p['lean'] * y)
        pts.append((X, Y))
    pts[0] = (0.0, pts[0][1])
    pts[-1] = (0.0, pts[-1][1])
    return np.array(pts)


def section(d, kind='end'):
    """half section at distance d from the nose tip ('end' cars), or the body's ('mid')"""
    p = NOSE.params(d) if kind == 'end' else dict(BODY)
    return half_section(p)


def top_y(d):
    return NOSE.params(d)['top']


# ---------------------------------------------------------------- stations along a car
def body_range(kind):
    """z of the body's rear face and front face (an end car's front is its nose tip)"""
    if kind == 'end':
        return JOINT_END + GAP, NOSE_TIP
    return -JOINT_MID + GAP, JOINT_MID - GAP


def stations(kind, step=0.5, nose_steps=None):
    """[(z, inset)]: inset > 0 rounds a body end"""
    z0, z1 = body_range(kind)
    st = []
    # rounded rear end (and the middle car's front end)
    for k in range(4, 0, -1):
        phi = (math.pi / 2) * k / 4
        st.append((z0 + END_R * (1 - math.sin(phi)), END_R * (1 - math.cos(phi))))
    zb = z1 - (NOSE_LEN if kind == 'end' else END_R)
    n = max(2, int(math.ceil((zb - z0 - END_R) / step)))
    for i in range(n + 1):
        st.append((z0 + END_R + (zb - z0 - END_R) * i / n, 0.0))
    if kind == 'end':
        ds = nose_steps if nose_steps is not None else nose_ds()
        for d in ds:
            st.append((NOSE_TIP - d, 0.0))
    else:
        for k in range(1, 5):
            phi = (math.pi / 2) * k / 4
            st.append((z1 - END_R * (1 - math.sin(phi)), END_R * (1 - math.cos(phi))))
    st.sort(key=lambda s: s[0])
    # drop near-duplicates
    out = [st[0]]
    for s in st[1:]:
        if s[0] - out[-1][0] > 1e-4:
            out.append(s)
    return out


def nose_ds():
    """distances from the tip of the nose's stations (dense at the tip where the sections close up)"""
    ds = []
    d = NOSE_LEN - 0.3
    while d > 2.4:
        ds.append(d)
        d -= 0.3 if d > 6.0 else 0.2
    ds += list(np.geomspace(2.4, 0.004, 30))
    return ds


def _normals2d(pts):
    out = []
    n = len(pts)
    for j in range(n):
        a = pts[max(j - 1, 0)]
        b = pts[min(j + 1, n - 1)]
        tx, ty = b[0] - a[0], b[1] - a[1]
        L = math.hypot(tx, ty) or 1.0
        out.append((ty / L, -tx / L))
    return out


def rings(kind, **kw):
    """[(z, half section)] along the car (an end car's nose sections, the rounded body ends inset)"""
    out = []
    for z, inset in stations(kind, **kw):
        d = NOSE_TIP - z if kind == 'end' else 99.0
        pts = section(d, kind)
        if inset > 0:
            nrm = _normals2d(pts)
            pts = np.array([(max(x - nx * inset, 0.0) if j not in (0, len(pts) - 1) else 0.0, y - ny * inset)
                            for j, ((x, y), (nx, ny)) in enumerate(zip(pts, nrm))])
        out.append((z, pts))
    return out


def shell_mesh(kind, **kw):
    """the closed shell as numpy arrays (vertices n × 3, triangles m × 3) in the car frame, for the fit tools"""
    R = rings(kind, **kw)
    n = HALF_N
    ring_n = 2 * n - 2               # both sides, the centre points shared
    V = []
    for z, pts in R:
        left = [(x, y, z) for x, y in pts]
        right = [(-x, y, z) for x, y in pts[1:-1][::-1]]
        V += left + right
    V = np.array(V, float)
    F = []
    for i in range(len(R) - 1):
        a, b = i * ring_n, (i + 1) * ring_n
        for j in range(ring_n):
            j2 = (j + 1) % ring_n
            F.append((a + j, b + j, b + j2))
            F.append((a + j, b + j2, a + j2))
    # end caps: fans round each end ring's centroid
    for i, (z, pts) in ((0, R[0]), (len(R) - 1, R[-1])):
        c = len(V)
        ring = V[i * ring_n:(i + 1) * ring_n]
        V = np.vstack([V, ring.mean(0)])
        for j in range(ring_n):
            F.append((c, i * ring_n + j, i * ring_n + (j + 1) % ring_n))
    return V, np.array(F, int)


def train_mesh(kinds=('end', 'mid', 'end'), **kw):
    """the three shells in the train frame (car0's), car2 turned round"""
    Vs, Fs, off = [], [], 0
    for name, kind in zip(('car0', 'car1', 'car2'), kinds):
        V, F = shell_mesh(kind, **kw)
        if name == 'car2':
            V = V * [-1, 1, -1]
        V = V + [0, 0, CAR_Z[name]]
        Vs.append(V)
        Fs.append(F + off)
        off += len(V)
    return np.vstack(Vs), np.vstack(Fs)
