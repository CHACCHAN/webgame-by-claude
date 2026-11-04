"""
The Supra's body shell: a closed loft of half sections along z, each one a floor, a rounded tuck to the widest point,
a superellipse over the shoulders and the bonnet / deck, and the glasshouse (a crowned roof, a rounded rail and
slanted side glass) blended in with a smooth maximum, so the cowl and the C-pillar bases come out filleted.

Figures: Toyota Supra RZ (JZA80, 1997-2002): length 4,520, width 1,810, height 1,275, wheelbase 2,550, tread
1,520 / 1,525 mm (published Toyota specification figures, not re-checked online here). Profile, plan and sections measured
on the reference photos (side view by Falcon Photography, Commons, CC BY-SA 2.0; front / rear three-quarters, see
docs). Our estimates: the sections' exponents, the tumblehome, the plan rounding of the nose and the tail.
"""
import math

import bmesh
import bpy
from mathutils import Vector

import supra_kit as K

ZN, ZT = 2.19, -2.29        # nose and tail (4.48: the side photo's tail; the published 4,520 is not reached)
AXLE = 1.275                # half the wheelbase
TRACK_F, TRACK_R = 1.52, 1.525
WHEEL_R = 0.33
WHEEL_Y = WHEEL_R           # wheel centre height (ground at 0)

P = K.pchip

# --- plan: half width at the widest point, before the end rounding
W_BASE = P([(-2.29, 0.872), (-2.0, 0.892), (-1.70, 0.905), (-1.275, 0.905), (-0.85, 0.890), (-0.4, 0.872),
            (0.2, 0.868), (0.7, 0.878), (1.1, 0.892), (1.40, 0.894), (1.75, 0.888), (2.19, 0.875)])
# plan rounding of the ends (starts at z, exponent): the bumper (below the widest point) is fuller than the bonnet and
# the lamps above it, so the bumper face juts out wide under the lamps
NOSE_LO = (1.55, 2.0)
NOSE_UP = (1.35, 2.2)
K_SHELF = 5.0              # how quickly a section narrows from the bumper's width to the upper plan above the widest point
TAIL_R = (-1.65, 2.0)
# height of the widest point
YM = P([(-2.29, 0.47), (-2.2, 0.52), (-2.0, 0.60), (-1.7, 0.635), (-1.275, 0.63), (-0.8, 0.57), (0.0, 0.53), (0.8, 0.52),
        (1.275, 0.52), (1.7, 0.49), (2.0, 0.47), (2.19, 0.45)])
# underside edge (rocker, bumper lips)
YB = P([(-2.29, 0.34), (-2.25, 0.30), (-2.15, 0.28), (-1.95, 0.26), (-1.70, 0.245), (-1.275, 0.235), (-0.6, 0.225),
        (0.6, 0.225), (1.275, 0.225), (1.70, 0.215), (1.92, 0.205), (2.06, 0.205), (2.13, 0.215), (2.17, 0.235),
        (2.19, 0.27)])
TUCK = P([(-2.29, 0.10), (-1.9, 0.15), (-1.275, 0.19), (-0.5, 0.25), (0.3, 0.25), (1.275, 0.18), (1.9, 0.10), (2.19, 0.08)])
NL = P([(-2.29, 3.0), (-1.9, 2.6), (-1.6, 2.3), (0.0, 2.1), (1.6, 2.4), (2.19, 2.9)])
# centre-line top of the lower body (bonnet, the deck under the glasshouse, the rear deck)
HD = P([(-2.29, 0.60), (-2.285, 0.68), (-2.27, 0.74), (-2.24, 0.80), (-2.19, 0.858), (-2.12, 0.912), (-2.03, 0.954),
        (-1.94, 0.975), (-1.80, 0.99), (-1.6, 1.0), (-1.0, 1.0), (-0.3, 0.99), (0.3, 0.95), (0.62, 0.885), (0.95, 0.842),
        (1.25, 0.808), (1.55, 0.765), (1.80, 0.705), (1.98, 0.648), (2.06, 0.620), (2.12, 0.590), (2.16, 0.558),
        (2.18, 0.528), (2.19, 0.50)])
PU = P([(-2.29, 3.2), (-2.0, 3.4), (-1.6, 3.3), (-0.6, 3.6), (0.2, 3.6), (0.8, 3.4), (1.3, 3.5), (1.7, 4.0), (1.95, 4.3),
        (2.19, 3.8)])
# glasshouse: roof centre height and half width at the belt
HR = P([(0.80, 0.74), (0.62, 0.855), (0.52, 0.892), (0.42, 0.952), (0.32, 1.012), (0.22, 1.058), (0.12, 1.113),
        (0.02, 1.178), (-0.08, 1.230), (-0.18, 1.252), (-0.28, 1.267), (-0.38, 1.274), (-0.48, 1.272), (-0.58, 1.267),
        (-0.68, 1.252), (-0.78, 1.232), (-0.88, 1.212), (-0.98, 1.177), (-1.08, 1.140), (-1.18, 1.108), (-1.28, 1.073),
        (-1.38, 1.046), (-1.48, 1.012), (-1.60, 0.975), (-1.80, 0.90)])
GW = P([(0.80, 0.70), (0.55, 0.705), (0.3, 0.712), (0.0, 0.716), (-0.5, 0.71), (-0.9, 0.682), (-1.2, 0.625),
        (-1.45, 0.545), (-1.62, 0.47), (-1.80, 0.38)])
# roof rail: half width, drop below the roof centre; roof crown exponent; rounding of the rail
RW = P([(0.80, 0.63), (0.55, 0.62), (0.2, 0.585), (-0.2, 0.565), (-0.6, 0.555), (-0.9, 0.54), (-1.2, 0.50),
        (-1.45, 0.44), (-1.65, 0.36), (-1.80, 0.30)])
DR = P([(0.6, 0.040), (0.0, 0.045), (-0.6, 0.050), (-1.2, 0.060), (-1.7, 0.06)])
PR = 2.2
K_RAIL = 0.05
K_BLEND = 0.03


# the scallop along the foot of the door: a shallow concave dent, starting behind the front arch and deepening back into
# the side intake ahead of the rear wheel (z: start, deepest, end; its centre height and half height along z)
SCALLOP_Z = (0.62, -0.70, -0.86)
SCALLOP_D = P([(0.62, 0.0), (0.55, 0.0012), (0.35, 0.008), (0.0, 0.015), (-0.40, 0.023), (-0.70, 0.030), (-0.80, 0.016), (-0.86, 0.0)])
SCALLOP_Y = P([(0.62, 0.36), (0.0, 0.375), (-0.5, 0.40), (-0.86, 0.43)])
SCALLOP_H = P([(0.62, 0.035), (0.0, 0.050), (-0.5, 0.068), (-0.86, 0.08)])


def scallop(z, y):
    """inward offset of the flank at (z, y)"""
    if not SCALLOP_Z[2] < z < SCALLOP_Z[0]:
        return 0.0
    t = (y - SCALLOP_Y(z)) / SCALLOP_H(z)
    if t > 1.0 or t < -1.6:
        return 0.0
    # a crisp upper edge (the crease), a long fade below
    f = (1 - t * t) if t > 0 else (1 - (t / 1.6) ** 2) ** 2
    return SCALLOP_D(z) * math.sqrt(max(0.0, f)) if t > 0 else SCALLOP_D(z) * f


def width(z, nose=NOSE_LO):
    w = W_BASE(z)
    z0, e = nose
    if z > z0:
        t = min(1.0, (z - z0) / (ZN - z0))
        w *= max(0.0, 1 - t ** e) ** (1 / e)
    z0, e = TAIL_R
    if z < z0:
        t = min(1.0, (z0 - z) / (z0 - ZT))
        w *= max(0.0, 1 - t ** e) ** (1 / e)
    return max(w, 0.012)


def smin(a, b, k):
    return 0.5 * (a + b - math.sqrt((a - b) ** 2 + k * k))


def smax(a, b, k=K_BLEND):
    return 0.5 * (a + b + math.sqrt((a - b) ** 2 + k * k))


class Section:
    """the half section at z, as functions"""

    def __init__(self, z):
        self.z = z
        self.W = width(z)
        self.Wu = width(z, NOSE_UP)
        self.ym = YM(z)
        self.yb = min(YB(z), self.ym - 0.02)
        self.hd = max(HD(z), self.ym + 0.02)
        self.xf = max(0.0, self.W - min(TUCK(z), 0.6 * self.W))
        self.nl = NL(z)
        self.pu = PU(z)
        hr = HR(z) if -1.80 <= z <= 0.80 else -10.0
        self.cab = None
        gw = min(GW(z), 0.98 * self.W)
        belt = self.lower(gw)
        if hr > belt + 0.002:
            rw = min(RW(z), gw - 0.05)
            yr = hr - min(DR(z), 0.5 * (hr - belt))
            self.cab = (hr, rw, yr, (yr - belt) / (gw - rw))
        self.belt = belt
        self.gw = gw

    def lower(self, x):
        """the lower body's top (bonnet / deck / shoulder) at |x|"""
        t = min(1.0, abs(x) / self.Wu)
        return self.ym + (self.hd - self.ym) * max(0.0, 1 - t ** self.pu) ** (1 / self.pu)

    def cabin(self, x):
        if self.cab is None:
            return -10.0
        hr, rw, yr, slope = self.cab
        x = abs(x)
        if x > self.gw:
            return self.belt - 6.0 * (x - self.gw)
        roof = hr - (hr - yr) * (x / rw) ** PR
        side = yr - (x - rw) * slope
        return smin(roof, side, K_RAIL)

    def top(self, x):
        return smax(self.lower(x), self.cabin(x)) if self.cab else self.lower(x)

    def polyline(self):
        pts = []
        for k in range(6):
            pts.append((self.xf * k / 6, self.yb))
        n = 160
        for k in range(n + 1):
            t = 0.5 * math.pi * k / n
            s, c = math.sin(t), math.cos(t)
            x = self.xf + (self.W - self.xf) * s ** (2 / self.nl)
            y = self.ym - (self.ym - self.yb) * c ** (2 / self.nl)
            pts.append((x, y))
        n = 1400
        for k in range(1, n + 1):
            t = 0.5 * math.pi * k / n
            s, c = math.sin(t), math.cos(t)
            x = (self.Wu + (self.W - self.Wu) * (1 - s) ** K_SHELF) * c ** (2 / self.pu)
            y0 = self.ym + (self.hd - self.ym) * s ** (2 / self.pu)
            y = smax(y0, self.cabin(x)) if self.cab else y0
            pts.append((x, y))
        pts[-1] = (0.0, pts[-1][1])
        # drop repeats
        out = [pts[0]]
        for p in pts[1:]:
            if math.dist(p, out[-1]) > 1e-5:
                out.append(p)
        return out


def weighted_resample(poly, n, beta=0.07, cheap=0):
    """n points along a polyline, spaced by arc length plus beta × turning angle (more points round corners); the
    first `cheap` segments (the flat floor) count a fifth"""
    m = [0.0]
    for i in range(1, len(poly)):
        ds = math.dist(poly[i], poly[i - 1]) * (0.2 if i <= cheap else 1.0)
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
    """z of the sections, denser at the nose and the tail"""
    out = []
    for k in range(n):
        s = k / (n - 1)
        u = 0.5 - 0.5 * math.cos(math.pi * s)        # clustered at the ends
        w = 0.55 * u + 0.45 * s
        out.append(ZT + (ZN - ZT) * w)
    return out


# height of the lower edge of the paint above YB: the black lip spoiler at the front, the valance at the rear; every
# section has a ring vertex exactly there, so the colour border runs as a smooth line
LIP = P([(-2.29, 0.065), (-1.90, 0.065), (-1.70, 0.045), (1.45, 0.045), (1.75, 0.030), (2.0, 0.058), (2.19, 0.06)])
N_LOW = 14          # ring points from the floor's centre up to that edge


def split_resample(poly, z, nv):
    """the half section resampled with its N_LOW-th point on the lip line"""
    yc = YB(z) + LIP(z)
    k = next((i for i in range(1, len(poly)) if poly[i][1] >= yc and poly[i - 1][1] < yc), None)
    if k is None or k < 3 or k > len(poly) - 3:
        return weighted_resample(poly, nv, cheap=6)
    a, b = poly[k - 1], poly[k]
    t = (yc - a[1]) / (b[1] - a[1])
    c = (a[0] + (b[0] - a[0]) * t, yc)
    lo = weighted_resample(poly[:k] + [c], N_LOW, cheap=6)
    hi = weighted_resample([c] + poly[k:], nv - N_LOW + 1)
    return lo + hi[1:]


def shell(name, mats, nu=110, nv=52):
    """the closed body shell as a Part (paint; dark underside; black lip and valance below the lip line)"""
    part = K.Part(name)
    rows = []
    for z in stations(nu):
        sec = Section(z)
        half = split_resample(sec.polyline(), z, nv)
        # the scallop moves the resampled points (resampling the dented outline would shift the rows and ripple)
        half = [(x - scallop(z, y) if x > 0.5 * sec.W else x, y) for x, y in half]
        ring = [(-x, y, z) for x, y in half] + [(x, y, z) for x, y in reversed(half[1:-1])]
        rows.append(ring)
    vs = part.grid(rows, mats['paint'], closed=True)
    m = 2 * nv - 2
    low = set()
    for row in vs:
        for j, v in enumerate(row[:m]):
            if j <= N_LOW - 1 or j >= m - (N_LOW - 1):
                low.add(v)
    low_faces = {f for f in part.bm.faces if all(v in low for v in f.verts)}
    # end caps
    for row, flip in ((vs[0], False), (vs[-1], True)):
        c = Vector((0, 0, 0))
        for v in row:
            c += v.co
        c /= len(row)
        cv = part.bm.verts.new(c)
        for j in range(len(row)):
            q = [row[j], row[(j + 1) % len(row)], cv]
            if flip:
                q.reverse()
            try:
                f = part.bm.faces.new(q)
                f.material_index = part.slot(mats['paint'])
                f.smooth = True
            except ValueError:
                pass
    bmesh.ops.remove_doubles(part.bm, verts=part.bm.verts, dist=1e-6)
    bmesh.ops.recalc_face_normals(part.bm, faces=part.bm.faces)
    part.bm.normal_update()
    under = part.slot(mats['under'])
    lip = part.slot(mats['trim'])
    for f in part.bm.faces:
        if not f.is_valid:
            continue
        c = K.G(f.calc_center_median())
        n = K.G(f.normal)
        if n.y < -0.7 and c.y < YB(c.z) + 0.012:
            f.material_index = under
        elif f in low_faces and (c.z > 1.62 or c.z < -1.90):
            f.material_index = lip          # the black lip spoiler under the bumper, the rear valance
    return part
