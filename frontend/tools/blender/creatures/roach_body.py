"""
The cockroach's body shells (game frame, real mm; see roach_geom): pronotum, tegmina, thorax, abdomen, head with
compound eyes and mouthparts, antennae, maxillary and labial palps, cerci. Each builder returns Parts with bone
weights; UV rectangles come from roach_tex.LAYOUT.
"""
import math

import numpy as np

import roach_anatomy as A
from roach_geom import Part, cap_ts, end_profile, frame, rot, smoothstep, tube_rows, unit
from roach_tex import LAYOUT

UP = np.array((0.0, 1.0, 0.0))


# ---------------------------------------------------------------- developed coordinates over the dorsal envelope

class Envelope:
    """arc length across the tegmina's envelope at each z: σ(x) and its inverse"""

    def __init__(self):
        self.xs = np.linspace(0.0, A.ENV_A * 1.15, 400)

    def sigma(self, x, z):
        xs = self.xs
        sl = np.array([A.env_slope(v, z) for v in xs])
        ds = np.sqrt(1 + sl ** 2)
        cum = np.concatenate([[0.0], np.cumsum((ds[1:] + ds[:-1]) / 2 * np.diff(xs))])
        return math.copysign(float(np.interp(abs(x), xs, cum)), x), (xs, cum)

    def x_of(self, s, z):
        _, (xs, cum) = self.sigma(1.0, z)
        return math.copysign(float(np.interp(abs(s), cum, xs)), s)

    def point(self, x, z, off):
        """the envelope at (x, z), `off` mm out along its normal (in the x-y plane)"""
        y = A.env_y(x, z)
        sl = A.env_slope(x, z)
        n = unit((-sl, 1.0))
        return np.array((x + n[0] * off, y + n[1] * off, z))


ENV = Envelope()


class WingShape:
    """one tegmen's planform in developed coordinates (σ across, z along): inner (anal) and outer (costal) margins"""

    def __init__(self, side):
        self.side = side                                  # +1 left (on top), -1 right (under)
        self.inner0 = -A.OVERLAP_LEFT if side > 0 else A.OVERLAP_RIGHT    # projected x of the inner margin
        self.apex = (0.4, A.WING_TIP) if side > 0 else (-1.3, A.WING_TIP + 0.55)
        self.z0 = A.WING_BASE
        self.z_round_out = -32.5
        self.z_round_in = -34.3

    def margins_x(self, z):
        """projected x of the inner and outer margins at z (inner, outer)"""
        s = self.side
        ax, az = self.apex
        w = A.smooth_interp(A.WING_OUTLINE, max(z, self.z_round_out))
        if z < self.z_round_out:
            t = min(1.0, (self.z_round_out - z) / (self.z_round_out - az))
            w0 = s * A.smooth_interp(A.WING_OUTLINE, self.z_round_out)
            xo = ax + (w0 - ax) * math.sqrt(max(0.0, 1 - t ** 2.3))
        else:
            xo = s * w
        if z < self.z_round_in:
            t = min(1.0, (self.z_round_in - z) / (self.z_round_in - az))
            xi = ax + (self.inner0 - ax) * math.sqrt(max(0.0, 1 - t ** 2.0))
        else:
            xi = self.inner0
        return xi, xo

    def margins(self, z):
        xi, xo = self.margins_x(z)
        return ENV.sigma(xi, z)[0], ENV.sigma(xo, z)[0]

    def zs(self, n):
        """rows from the base to the apex, denser at the rounded apex"""
        az = self.apex[1]
        out = []
        for k in range(n):
            a = k / (n - 1)
            # uniform over the body, cosine-packed over the last 6 mm
            out.append(a)
        z_mid = self.z_round_out - 0.5
        n1 = int(n * 0.72)
        zs = [self.z0 + (z_mid - self.z0) * k / n1 for k in range(n1)]
        n2 = n - n1
        for k in range(n2 + 1):
            a = k / n2
            zs.append(z_mid + (az - z_mid) * math.sin(a * math.pi / 2))
        return zs


def wing_lift(x, side):
    """the left tegmen rides on the right one where they overlap"""
    if side < 0:
        return 0.0
    return (A.WING_THICK + 0.05) * (1 - float(smoothstep(A.OVERLAP_RIGHT + 0.3, A.OVERLAP_RIGHT + 1.7, x)))


def build_tegmen(side):
    shape = WingShape(side)
    name = 'tegmen_L' if side > 0 else 'tegmen_R'
    region = LAYOUT[name]
    part = Part(name, 'roach_shell')
    zs = shape.zs(52)
    nc = 14
    # σ range of the whole wing (for the UV rectangle)
    sig = [shape.margins(z) for z in zs]
    smin = min(min(a, b) for a, b in sig)
    smax = max(max(a, b) for a, b in sig)
    zmin, zmax = min(zs), max(zs)
    shape.uv_box = (smin, smax, zmin, zmax)
    u0, v0, u1, v1 = region

    def uv(s, z):
        return (u0 + (u1 - u0) * (s - smin) / (smax - smin), v0 + (v1 - v0) * (z - zmin) / (zmax - zmin))

    top, bot, uvs = [], [], []
    for i, z in enumerate(zs[:-1]):
        si, so = sig[i]
        rt, rb, ru = [], [], []
        for j in range(nc):
            a = j / (nc - 1)
            s = si + (so - si) * a
            x = ENV.x_of(s, z)
            lift = wing_lift(x, side)
            # the margins droop a touch (the tegmen is a little convex)
            edge = min(a, 1 - a)
            droop = -0.12 * (1 - float(smoothstep(0.0, 0.25, edge)))
            rt.append(ENV.point(x, z, lift + A.WING_THICK + droop))
            rb.append(ENV.point(x, z, lift + droop + 0.01))
            ru.append(uv(s, z))
        top.append(rt)
        bot.append(rb)
        uvs.append(ru)
    za = zs[-1]
    xa = shape.apex[0]
    pole_t = ENV.point(xa, za, wing_lift(xa, side) + A.WING_THICK * 0.6 - 0.12)
    pole_b = ENV.point(xa, za, wing_lift(xa, side) + A.WING_THICK * 0.2 - 0.12)
    sa = ENV.sigma(xa, za)[0]
    pole_uv = uv(sa, za)
    w = {'thorax': 1.0}
    nr = len(top)
    T = [[part.vert(p, w) for p in row] for row in top]
    Bt = [[part.vert(p, w) for p in row] for row in bot]
    pt, pb = part.vert(pole_t, w), part.vert(pole_b, w)
    for i in range(nr - 1):
        for j in range(nc - 1):
            q = (uvs[i][j], uvs[i][j + 1], uvs[i + 1][j + 1], uvs[i + 1][j])
            part.face((T[i][j], T[i][j + 1], T[i + 1][j + 1], T[i + 1][j]), q)
            part.face((Bt[i][j], Bt[i + 1][j], Bt[i + 1][j + 1], Bt[i][j + 1]), (q[0], q[3], q[2], q[1]))
    i = nr - 1
    for j in range(nc - 1):
        part.face((T[i][j], T[i][j + 1], pt), (uvs[i][j], uvs[i][j + 1], pole_uv))
        part.face((Bt[i][j + 1], Bt[i][j], pb), (uvs[i][j + 1], uvs[i][j], pole_uv))
    # the rim: base row, outer margin, apex, inner margin
    loop = [(0, j) for j in range(nc)] + [(i, nc - 1) for i in range(1, nr)] + [('pole', 0)] + \
           [(i, 0) for i in range(nr - 1, 0, -1)]

    def ids(k):
        a, b = loop[k]
        if a == 'pole':
            return pt, pb, pole_uv
        return T[a][b], Bt[a][b], uvs[a][b]

    for k in range(len(loop)):
        t0, b0, uv0 = ids(k)
        t1, b1, uv1 = ids((k + 1) % len(loop))
        part.face((t0, b0, b1, t1), (uv0, uv0, uv1, uv1))
    return part, shape


# ---------------------------------------------------------------- pronotum

def pronotum_outline(th):
    """projected outline point (x, z) at angle th around the centre (0 = +x, π/2 = front)"""
    P = A.PRONOTUM
    hw = P['half_w']
    fz = P['front'] - P['zc']
    rz = P['zc'] - P['rear']
    c, s = math.cos(th), math.sin(th)
    if s >= 0:
        # front half: an ellipse
        return hw * c, P['zc'] + fz * s
    n = P['rear_sq']
    x = hw * math.copysign(abs(c) ** (2 / n), c)
    z = P['zc'] - rz * abs(s) ** (2 / n)
    return x, z


def pronotum_y(x, z):
    """height of the pronotum's upper surface"""
    P = A.PRONOTUM
    # midline profile: the hood's front edge low, crest, rear margin over the wing bases
    prof = [(P['front'] + 0.3, P['front_y']), (-3.0, 6.75), (-4.6, 7.45), (-6.2, P['top']), (-7.8, P['top'] - 0.05),
            (P['rear'] - 0.4, P['rear_y'])]
    ym = A.smooth_interp(prof, z)
    hw = P['half_w']
    drop = A.smooth_interp([(P['front'], 1.7), (-4.5, 2.4), (-6.5, 2.2), (P['rear'], 1.25)], z)
    u = min(1.2, abs(x) / hw)
    return ym - drop * u ** 2.6


def build_pronotum():
    P = A.PRONOTUM
    part = Part('pronotum', 'roach_shell')
    u0, v0, u1, v1 = LAYOUT['pronotum']
    X0, X1, Z0, Z1 = -5.3, 5.3, P['rear'] - 0.5, P['front'] + 0.5

    def uv(x, z):
        return (u0 + (u1 - u0) * (x - X0) / (X1 - X0), v0 + (v1 - v0) * (z - Z0) / (Z1 - Z0))

    n_th, n_r = 60, 9
    ths = [2 * math.pi * k / n_th for k in range(n_th)]
    rhos = [1 - (1 - k / n_r) ** 1.6 for k in range(1, n_r + 1)]
    w = {'thorax': 1.0}
    top, bot, uvs = [], [], []
    for r in rhos:
        rt, rb, ru = [], [], []
        for th in ths:
            ox, oz = pronotum_outline(th)
            x, z = ox * r, P['zc'] + (oz - P['zc']) * r
            y = pronotum_y(x, z)
            # the explanate margin turns up a little at the very edge
            y += 0.12 * float(smoothstep(0.86, 1.0, r))
            rt.append((x, y, z))
            rb.append((x, y - P['thick'] * (0.55 + 0.45 * (1 - r)) - 0.15 * (1 - r), z))
            ru.append(uv(x, z))
        top.append(rt)
        bot.append(rb)
        uvs.append(ru)
    c = (0.0, pronotum_y(0.0, P['zc']), P['zc'])
    T = [[part.vert(p, w) for p in row] for row in top]
    Bt = [[part.vert(p, w) for p in row] for row in bot]
    ct = part.vert(c, w)
    cb = part.vert((c[0], c[1] - P['thick'] - 0.1, c[2]), w)
    cuv = uv(0.0, P['zc'])
    n = n_th
    for j in range(n):
        j2 = (j + 1) % n
        part.face((ct, T[0][j2], T[0][j]), (cuv, uvs[0][j2], uvs[0][j]))
        part.face((cb, Bt[0][j], Bt[0][j2]), (cuv, uvs[0][j], uvs[0][j2]))
        for i in range(len(rhos) - 1):
            q = (uvs[i][j], uvs[i][j2], uvs[i + 1][j2], uvs[i + 1][j])
            part.face((T[i][j], T[i][j2], T[i + 1][j2], T[i + 1][j]), q)
            part.face((Bt[i][j], Bt[i + 1][j], Bt[i + 1][j2], Bt[i][j2]), (q[0], q[3], q[2], q[1]))
        i = len(rhos) - 1
        # rounded rim: a middle ring pushed out
        part.face((T[i][j], Bt[i][j], Bt[i][j2], T[i][j2]), (uvs[i][j], uvs[i][j], uvs[i][j2], uvs[i][j2]))
    return part


# ---------------------------------------------------------------- thorax and abdomen (lofted along z)

def superellipse_ring(cx, cy, z, a, b_top, b_bot, n, p=2.4, zbend=None):
    """a ring around the body axis: half width a, heights above / below cy; seam at the top (θ = 90°)"""
    pts = []
    for k in range(n):
        th = math.pi / 2 + 2 * math.pi * k / n
        c, s = math.cos(th), math.sin(th)
        x = a * math.copysign(abs(c) ** (2 / p), c)
        y = cy + (b_top if s >= 0 else b_bot) * math.copysign(abs(s) ** (2 / p), s)
        zz = z + (zbend(x / max(a, 1e-6), s) if zbend else 0.0)
        pts.append((cx + x, y, zz))
    return np.array(pts)


def build_thorax():
    part = Part('thorax', 'roach_body')
    rows, vs = [], []
    zs = np.linspace(A.THORAX[0][0], A.THORAX[-1][0], 14)
    for z in zs:
        a, yb, yt = A.interp(A.THORAX, z)
        cy = (yb + yt) / 2
        rows.append(superellipse_ring(0.0, cy, z, a, yt - cy, cy - yb, 28, p=2.6))
    z0, z1 = zs[0], zs[-1]
    a0, yb0, yt0 = A.interp(A.THORAX, z0)
    a1, yb1, yt1 = A.interp(A.THORAX, z1)
    vs = [(z - z0) / (z1 - z0) for z in zs]
    part.loft(rows, LAYOUT['thorax'], {'thorax': 1.0}, pole0=(0, (yb0 + yt0) / 2, z0 + 0.6),
              pole1=(0, (yb1 + yt1) / 2, z1 - 0.6), v_of=vs)
    return part


def abdomen_zs():
    """ring positions: each visible sternite's posterior edge overlaps the next one (a small step)"""
    z_front, z_tip = A.ABDOMEN[0][0], A.ABDOMEN[-1][0]
    edges = [z_front + 0.4] + A.STERNITES + [z_tip + 0.9]
    zs, fac = [], []
    for a, b in zip(edges[:-1], edges[1:]):
        for s in (0.0, 0.18, 0.5, 0.82, 0.97):
            zs.append(a + (b - a) * s)
            fac.append(0.952 + 0.048 * float(smoothstep(0.0, 0.85, s)))
    return zs, fac


def build_abdomen():
    part = Part('abdomen', 'roach_body')
    zs, fac = abdomen_zs()
    z_front, z_tip = A.ABDOMEN[0][0], A.ABDOMEN[-1][0]
    # rounded front and rear ends
    pre = [z_front + 0.0, z_front - 0.2]
    rows, vv = [], []
    allz = [(z, 0.6 + 0.35 * k, 1.0) for k, z in enumerate(pre)] + [(z, 1.0, f) for z, f in zip(zs, fac)]
    tail = [(z_tip + 0.55, 0.75, 1.0), (z_tip + 0.25, 0.5, 1.0)]
    allz += tail
    for z, endf, f in allz:
        a, yb, yt = A.interp(A.ABDOMEN, z)
        cy = (yb + yt) / 2
        bend = (lambda u, s: 0.55 * u * u * (1 if s < 0 else 0.6))
        rows.append(superellipse_ring(0.0, cy, z, a * f * endf, (yt - cy) * f * endf, (cy - yb) * f * endf, 30,
                                      p=2.5, zbend=bend))
        vv.append((z_front - z) / (z_front - z_tip))
    vv = [min(1.0, max(0.0, v)) for v in vv]
    a, yb, yt = A.interp(A.ABDOMEN, z_tip)
    part.loft(rows, LAYOUT['abdomen'], {'abdomen': 1.0}, pole0=(0, 4.8, z_front + 0.35),
              pole1=(0, (yb + yt) / 2, z_tip), v_of=vv)
    return part


# ---------------------------------------------------------------- head

class HeadFrame:
    def __init__(self):
        H = A.HEAD
        self.V = np.array(H['vertex'], float)
        self.Y = unit(H['axis'])
        # Z: the face's normal (forward and up), X: the insect's left
        # X: the insect's left, Z: the face's normal (forward and up); (X, Y, Z) is left-handed here, it only spans
        # the capsule's sections (bones get proper frames of their own)
        self.X = np.array((1.0, 0.0, 0.0))
        self.Z = unit(np.cross(self.Y, self.X))
        if self.Z[2] < 0:
            self.Z = -self.Z
        self.L = H['length']

    def centre(self, t):
        return self.V + self.Y * (t * self.L)

    def dims(self, t):
        H = A.HEAD
        return (A.smooth_interp(H['width'], t), A.smooth_interp(H['front'], t), A.smooth_interp(H['back'], t))

    def surface(self, t, th, extra=0.0):
        """the capsule's surface: th = 0 at the back (−Z), π/2 at the left side, π at the face"""
        w, f, b = self.dims(t)
        e = end_profile(t, 0.13, 0.12)
        c, s = math.cos(th), math.sin(th)
        p = 2.3
        lat = w * math.copysign(abs(s) ** (2 / p), s)
        dep = (f if c < 0 else b) * math.copysign(abs(c) ** (2 / p), -c)
        return self.centre(t) + (self.X * lat + self.Z * dep) * e + self.normal(t, th) * extra

    def normal(self, t, th):
        d = 1e-3
        p0 = self.surface_raw(t, th)
        pt = self.surface_raw(min(1, t + d), th) - self.surface_raw(max(0, t - d), th)
        pa = self.surface_raw(t, th + d) - self.surface_raw(t, th - d)
        n = unit(np.cross(pa, pt))
        if np.dot(n, p0 - self.centre(t)) < 0:
            n = -n
        return n

    def surface_raw(self, t, th):
        w, f, b = self.dims(t)
        e = max(end_profile(t, 0.13, 0.12), 0.05)
        c, s = math.cos(th), math.sin(th)
        p = 2.3
        lat = w * math.copysign(abs(s) ** (2 / p), s)
        dep = (f if c < 0 else b) * math.copysign(abs(c) ** (2 / p), -c)
        return self.centre(t) + (self.X * lat + self.Z * dep) * e


HF = HeadFrame()


def build_head():
    part = Part('head', 'roach_shell')
    ts = cap_ts(18, 0.13, 0.12, n_cap=4)
    n = 32
    rows = []
    for t in ts:
        rows.append(np.array([HF.surface_raw(t, 2 * math.pi * k / n) for k in range(n)]))
    part.loft(rows, LAYOUT['head'], {'head': 1.0}, pole0=HF.centre(0.0) - HF.Y * 0.02,
              pole1=HF.centre(1.0) + HF.Y * 0.02, v_of=ts)
    return part


def eye_frame(side):
    """centre, long axis, width axis, outward normal of a compound eye"""
    E = A.EYE
    tm = (E['t0'] + E['t1']) / 2
    th = side * math.radians(118)        # a little forward of the side (π/2), towards the face (π)
    c = HF.surface_raw(tm, th)
    n = HF.normal(tm, th)
    L = unit(HF.Y - np.dot(HF.Y, n) * n)
    W = np.cross(n, L)
    return c, L, W, n, (E['t1'] - E['t0']) * HF.L / 2


def build_eye(side):
    E = A.EYE
    part = Part('eye_' + ('L' if side > 0 else 'R'), 'roach_body')
    c, L, W, n, half_l = eye_frame(side)
    # W points towards the face for the left eye; the kidney's notch (round the antenna socket) faces forward
    to_face = 1.0 if np.dot(W, HF.Z) > 0 else -1.0
    rows = []
    ts = cap_ts(10, 0.18, 0.18, n_cap=3)
    na = 12
    for t in ts:
        e = end_profile(t, 0.18, 0.18)
        l = (t - 0.5) * 2                    # -1..1 along the eye
        bend = -0.35 * (1 - l * l) * to_face  # concave towards the socket
        hw = E['half_w'] * (1 - 0.15 * l)    # broader at the top
        row = []
        for k in range(na):
            a = 2 * math.pi * k / na
            p = c + L * (l * half_l) + W * (bend + hw * math.cos(a) * e) + n * (E['depth'] * math.sin(a) * e - 0.18)
            row.append(p)
        rows.append(np.array(row))
    part.loft(rows, LAYOUT['eye'], {'head': 1.0}, pole0=c - L * half_l - n * 0.18, pole1=c + L * half_l - n * 0.18,
              v_of=ts)
    return part


def socket(side):
    """the antenna's socket on the face (point, outward normal)"""
    t = A.ANTENNA['t']
    # the angle round the capsule whose lateral offset is about ANTENNA x
    best = None
    for k in range(200):
        th = math.pi * 0.5 + math.pi * 0.5 * k / 199
        p = HF.surface_raw(t, side * th)
        d = abs(abs(np.dot(p - HF.centre(t), HF.X)) - A.ANTENNA['x'])
        if best is None or d < best[0]:
            best = (d, side * th)
    th = best[1]
    return HF.surface_raw(t, th), HF.normal(t, th)


# ---------------------------------------------------------------- antennae

ANT_BONES = [0.0, 1.75, 5.0, 10.0, 16.5, 24.0, 33.5, A.ANTENNA['length']]


def antenna_curve(side, n=240):
    """centreline points, tangents and arc lengths; the antenna rises forward and outward and curves out and back"""
    p0, nrm = socket(side)
    Lt = A.ANTENNA['length']
    s = np.linspace(0.0, Lt, n)
    pts, tans = [], []
    p = p0 - nrm * 0.15
    for i, si in enumerate(s):
        u = si / Lt
        yaw = math.radians(16 + 62 * u ** 1.15)                 # out from +z
        pitch = math.radians(16 - 10 * u - 14 * u ** 2)         # up a little first, then drooping
        d = np.array((side * math.sin(yaw) * math.cos(pitch), math.sin(pitch), math.cos(yaw) * math.cos(pitch)))
        if i > 0:
            p = p + d * (s[i] - s[i - 1])
        pts.append(p.copy())
        tans.append(d)
    return np.array(pts), np.array(tans), s


def antenna_radius(s):
    a = A.ANTENNA
    l_sc, r_sc = a['scape']
    l_pd, r_pd = a['pedicel']
    if s < l_sc:
        return r_sc * (0.85 + 0.15 * math.sin(math.pi * s / l_sc))
    if s < l_sc + l_pd:
        return r_pd * (0.9 + 0.1 * math.sin(math.pi * (s - l_sc) / l_pd))
    u = (s - l_sc - l_pd) / (a['length'] - l_sc - l_pd)
    return a['r0'] + (a['r1'] - a['r0']) * u ** 0.8


def chain_weight(s, bounds, names, blend=0.5):
    """weights along a bone chain by arc length: rigid inside a bone, blended over ±blend × the shorter bone's
    half length round each joint"""
    k = max(0, min(len(names) - 1, int(np.searchsorted(bounds, s, side='right') - 1)))
    w = {names[k]: 1.0}
    for j in (k, k + 1):
        if 0 < j < len(names):
            zone = blend * min(bounds[j] - bounds[j - 1], bounds[j + 1] - bounds[j]) / 2
            d = s - bounds[j]
            if abs(d) < zone:
                a = 0.5 + 0.5 * d / zone          # 0 → previous bone, 1 → next
                a = a * a * (3 - 2 * a)
                return {names[j - 1]: 1 - a, names[j]: a}
    return w


def ant_names(side):
    sd = 'L' if side > 0 else 'R'
    return [f'antenna_{sd}_{i}' for i in range(len(ANT_BONES) - 1)]


def build_antenna(side):
    part = Part('antenna_' + ('L' if side > 0 else 'R'), 'roach_body')
    pts, tans, s = antenna_curve(side)
    names = ant_names(side)
    # rings: dense at the base, then every ~0.6 mm
    ss = [0.0]
    while ss[-1] < s[-1] - 0.05:
        cur = ss[-1]
        ss.append(cur + (0.18 if cur < 2.0 else 0.35 if cur < 6 else 0.75))
    ss[-1] = s[-1] - 0.05
    n = 7
    rows, vv, ws = [], [], []
    # parallel-transported frame
    ref = np.array((0.0, 1.0, 0.0))
    prevN = None
    for sv in ss:
        c = np.array([np.interp(sv, s, pts[:, k]) for k in range(3)])
        t = unit([np.interp(sv, s, tans[:, k]) for k in range(3)])
        if prevN is None:
            N = unit(ref - np.dot(ref, t) * t)
        else:
            N = unit(prevN - np.dot(prevN, t) * t)
        prevN = N
        Bn = np.cross(t, N)
        r = antenna_radius(sv)
        th = np.arange(n) / n * 2 * math.pi
        rows.append(c + np.outer(r * np.cos(th), N) + np.outer(r * np.sin(th), Bn))
        vv.append(sv / s[-1])
        ws.append(chain_weight(sv, ANT_BONES, names))
    tip = pts[-1]
    base = pts[0] - tans[0] * 0.25
    part.loft(rows, LAYOUT['antenna'], lambda i, j: ws[i], pole0=base, pole1=tip, v_of=vv)
    return part


def antenna_bone_frames(side):
    """rest frames of the antenna bones: (head, tail, z axis = up-ish)"""
    pts, tans, s = antenna_curve(side)
    out = []
    for a, b in zip(ANT_BONES[:-1], ANT_BONES[1:]):
        h = np.array([np.interp(a, s, pts[:, k]) for k in range(3)])
        t = np.array([np.interp(b, s, pts[:, k]) for k in range(3)])
        out.append((h, t))
    return out


# ---------------------------------------------------------------- mouthparts

def mouth_frames(side):
    """the maxilla's base (where the palp starts) and the labium's palp base"""
    t = 0.9
    th = side * math.radians(80)
    mx = HF.surface_raw(t, th) - HF.normal(t, th) * 0.25
    lb = HF.surface_raw(1.0, side * math.radians(40)) + HF.Y * 0.15 - HF.Z * 0.15
    return mx, lb


def palp_path(side, lengths, start, dirs):
    """a palp's joints from segment directions (unit vectors in the game frame, left side; mirrored by side)"""
    pts = [np.array(start, float)]
    for L, d in zip(lengths, dirs):
        d = unit((d[0] * side, d[1], d[2]))
        pts.append(pts[-1] + d * L)
    return pts


MAX_PALP_DIRS = [(0.8, -0.2, 0.55), (0.6, -0.3, 0.75), (0.25, -0.3, 0.92), (0.02, -0.2, 0.98), (-0.08, -0.5, 0.86)]
LAB_PALP_DIRS = [(0.4, -0.3, 0.86), (0.3, -0.3, 0.9), (0.2, -0.45, 0.87)]


def max_palp_joints(side):
    mx, _ = mouth_frames(side)
    return palp_path(side, A.MAX_PALP, mx, MAX_PALP_DIRS)


def lab_palp_joints(side):
    _, lb = mouth_frames(side)
    return palp_path(side, A.LAB_PALP, lb, LAB_PALP_DIRS)


def segmented_tube(part, joints, radii, region, weight_of, n=7, rings=5, club_last=1.0):
    """a palp / cercus: one tube through the joints, each segment a slight spindle with a waist at the joints"""
    rows, vv, ws = [], [], []
    total = sum(np.linalg.norm(b - a) for a, b in zip(joints[:-1], joints[1:]))
    acc = 0.0
    ref = np.array((0.0, 0.0, 1.0))
    prevN = None
    for k, (a, b) in enumerate(zip(joints[:-1], joints[1:])):
        d = b - a
        L = np.linalg.norm(d)
        t = d / L
        r0, r1 = radii[k], radii[k + 1]
        for i in range(rings):
            u = (i + 0.5) / rings if False else i / rings
            if k == 0 and i == 0:
                u = 0.04
            c = a + d * u
            N = unit((prevN if prevN is not None else ref) - np.dot(prevN if prevN is not None else ref, t) * t)
            if np.linalg.norm(N) < 1e-6:
                N = unit(np.cross(t, (1, 0, 0)))
            prevN = N
            Bn = np.cross(t, N)
            r = r0 + (r1 - r0) * u
            r *= 0.78 + 0.22 * math.sin(math.pi * min(1, max(0, u * 1.1))) ** 0.6
            if k == len(joints) - 2:
                r *= 1 + (club_last - 1) * math.sin(math.pi * u * 0.8)
            th = np.arange(n) / n * 2 * math.pi
            rows.append(c + np.outer(r * np.cos(th), N) + np.outer(r * np.sin(th), Bn))
            vv.append((acc + L * u) / total)
            ws.append(weight_of(k, u))
        acc += L
    tip = joints[-1]
    d_end = unit(joints[-1] - joints[-2])
    part.loft(rows, region, lambda i, j: ws[i], pole0=joints[0] - unit(joints[1] - joints[0]) * radii[0] * 0.6,
              pole1=tip + d_end * radii[-1] * 0.6, v_of=vv)


def build_palps(side):
    sd = 'L' if side > 0 else 'R'
    parts = []
    p = Part('maxpalp_' + sd, 'roach_body')
    j = max_palp_joints(side)
    segmented_tube(p, j, [0.16, 0.15, 0.14, 0.13, 0.12, 0.1], LAYOUT['palp'],
                   lambda k, u: {f'palp_{sd}_0': 1.0} if k < 2 else {f'palp_{sd}_1': 1.0}, n=7, rings=4, club_last=1.25)
    parts.append(p)
    p = Part('labpalp_' + sd, 'roach_body')
    j = lab_palp_joints(side)
    segmented_tube(p, j, [0.12, 0.11, 0.1, 0.08], LAYOUT['lpalp'], lambda k, u: {f'lpalp_{sd}': 1.0}, n=6, rings=3,
                   club_last=1.2)
    parts.append(p)
    return parts


def ellipsoid(part, c, X, Y, Z, rx, ry, rz, region, weight, n=12, m=8, squash=None):
    rows, vv = [], []
    for i in range(1, m):
        a = math.pi * i / m
        row = []
        for k in range(n):
            b = 2 * math.pi * k / n
            x, y, z = math.sin(a) * math.cos(b), -math.cos(a), math.sin(a) * math.sin(b)
            if squash:
                x, y, z = squash(x, y, z)
            row.append(c + X * (x * rx) + Y * (y * ry) + Z * (z * rz))
        rows.append(np.array(row))
        vv.append(i / m)
    part.loft(rows, region, weight, pole0=c - Y * ry, pole1=c + Y * ry, v_of=vv)


def build_mouth():
    """labrum flap, mandibles, maxillae (cardo/stipes/galea as one lobe each), labium"""
    part = Part('mouth', 'roach_body')
    w = {'head': 1.0}
    r = LAYOUT['mouth']
    u0, v0, u1, v1 = r
    sub = lambda a, b: (u0 + (u1 - u0) * a, v0, u0 + (u1 - u0) * b, v1)
    # labrum: a rounded flap hanging from the clypeus
    c = HF.centre(0.97) + HF.Z * 0.45
    X, Y, Z = HF.X, HF.Y, HF.Z
    ellipsoid(part, c, X, Y, Z, 1.0, 0.55, 0.32, sub(0.0, 0.25), w)
    # mandibles: dark wedges either side behind the labrum, tips meeting
    for sd in (1, -1):
        c = HF.centre(0.98) + X * (0.55 * sd) + Z * 0.0 + Y * 0.2
        Ym = unit(Y + X * (-0.35 * sd))
        Xm, Ym2, Zm = frame(Ym, Z)
        ellipsoid(part, c, Xm, Ym2, Zm, 0.42, 0.62, 0.36, sub(0.25, 0.5), w,
                  squash=lambda x, y, z: (x * (1 - 0.6 * max(0, y)), y, z * (1 - 0.5 * max(0, y))))
    # maxillae: lobes at the sides behind the mandibles
    for sd in (1, -1):
        c = HF.centre(0.86) + X * (1.0 * sd) - Z * 0.55
        ellipsoid(part, c, X, Y, Z, 0.42, 0.85, 0.4, sub(0.5, 0.75), w)
    # labium (postmentum + glossae) behind
    c = HF.centre(0.93) - Z * 0.95
    ellipsoid(part, c, X, Y, Z, 0.75, 0.7, 0.35, sub(0.75, 1.0), w)
    return part


# ---------------------------------------------------------------- cerci

def cercus_joints(side):
    C = A.CERCUS
    b = np.array((C['base'][0] * side, C['base'][1], C['base'][2]))
    d = unit((C['dir'][0] * side, C['dir'][1], C['dir'][2]))
    segs = C['segs']
    L = C['length']
    pts = [b]
    for k in range(segs):
        # slightly curved up at the tip
        dk = unit(d + np.array((0, 0.02 * k, 0)))
        seg = L / segs * (1.25 - 0.5 * k / segs)
        pts.append(pts[-1] + dk * seg)
    return pts


def build_cercus(side):
    sd = 'L' if side > 0 else 'R'
    part = Part('cercus_' + sd, 'roach_body')
    j = cercus_joints(side)
    R = A.CERCUS['r']
    n = len(j)
    radii = [R * (0.75 + 0.25 * math.sin(math.pi * min(1, i / (n - 1) * 2.2))) * (1 - 0.82 * (i / (n - 1)) ** 1.3)
             for i in range(n)]
    segmented_tube(part, j, radii, LAYOUT['cercus'], lambda k, u: {f'cercus_{sd}': 1.0}, n=7, rings=3)
    return part
