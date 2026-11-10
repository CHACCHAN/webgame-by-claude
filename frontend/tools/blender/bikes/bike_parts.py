"""
Parts shared by the three motorcycles: wheels (tyre, rim with spokes, discs, calipers), steering geometry, forks and
yokes, clip-on bars with grips and levers, mirrors, footpegs, chain, the fairing hull (a loft of U sections cut by a
side outline), screen, tank, seat and tail lofts, pipes and silencers. Everything in the game frame (bike_kit).
"""
import math

import bmesh
import numpy as np

import bike_kit as K

BEAD_R = 0.2159     # 17" rim bead seat radius


# ---------------------------------------------------------------- steering geometry

class Steering:
    """rake (rad), trail (m), front axle (z, y): the steering axis, fork offset, head stock"""

    def __init__(self, wb, rf, rake_deg, trail, head_y):
        self.rake = math.radians(rake_deg)
        self.trail = trail
        self.fz = wb / 2
        self.rf = rf
        self.axis = np.array([0.0, math.cos(self.rake), -math.sin(self.rake)])   # up the steering axis
        self.ground = np.array([0.0, 0.0, self.fz + trail])
        self.offset = rf * math.sin(self.rake) - trail * math.cos(self.rake)
        self.head = self.at_y(head_y)
        self.axle = np.array([0.0, rf, self.fz])
        # forward normal of the axis in the bike plane (the fork legs sit `offset` ahead of the axis)
        self.fwd = np.array([0.0, math.sin(self.rake), math.cos(self.rake)])

    def at_y(self, y):
        t = y / self.axis[1]
        return self.ground + self.axis * t

    def leg_point(self, y_along, x):
        """a point on a fork leg's axis: x sideways, `y_along` metres up the leg from the axle"""
        return self.axle + self.axis * y_along + np.array([x, 0, 0])


# ---------------------------------------------------------------- wheels

def tyre(part, centre, R, width, mat='tire', seg=48, rim_r=BEAD_R + 0.012):
    """a tyre about the x axis: profile from bead to bead over a round crown"""
    h = R - rim_r
    w2 = width / 2
    prof = []
    # (radius, x) from the left bead round the crown to the right bead
    pts = [(rim_r, w2 * 0.66), (rim_r + h * 0.25, w2 * 0.92), (rim_r + h * 0.55, w2 * 1.0), (rim_r + h * 0.78, w2 * 0.93),
           (R - h * 0.07, w2 * 0.62), (R, w2 * 0.2), (R, -w2 * 0.2), (R - h * 0.07, -w2 * 0.62), (rim_r + h * 0.78, -w2 * 0.93),
           (rim_r + h * 0.55, -w2 * 1.0), (rim_r + h * 0.25, -w2 * 0.92), (rim_r, -w2 * 0.66)]
    prof = K.catmull([(p[1], p[0]) for p in pts], 17)
    prof = [(p[1], p[0]) for p in prof]
    return part.revolve(mat, prof, centre, axis=(1, 0, 0), seg=seg)


def rim(part, centre, width, spokes=7, style='straight', mat='rim', seg=48, hub_w=None, spoke_w=0.026, phase=0.0,
        spoke_depth=0.03, offset=0.0):
    """rim: two lips, the barrel (inside, dark), a hub and the spokes (style 'straight' | 'split' | 'curved' | 'y')"""
    c = np.array(centre, float)
    w2 = width / 2
    lip = BEAD_R + 0.014
    # lips and barrel as one revolve (outer lip → bead seat → well → bead seat → outer lip)
    prof = [(lip - 0.004, w2 + 0.006), (lip, w2 + 0.002), (lip, w2 - 0.004), (BEAD_R, w2 - 0.008), (BEAD_R - 0.004, w2 * 0.55),
            (BEAD_R - 0.022, w2 * 0.25), (BEAD_R - 0.022, -w2 * 0.25), (BEAD_R - 0.004, -w2 * 0.55), (BEAD_R, -w2 + 0.008),
            (lip, -w2 + 0.004), (lip, -w2 - 0.002), (lip - 0.004, -w2 - 0.006), (lip - 0.012, -w2 - 0.002),
            (BEAD_R - 0.03, -w2 * 0.3), (BEAD_R - 0.03, w2 * 0.3), (lip - 0.012, w2 + 0.002)]
    prof = [(r, a + offset) for r, a in prof]
    part.revolve(mat, prof, c, axis=(1, 0, 0), seg=seg)
    # hub
    hw = hub_w if hub_w is not None else width * 0.9
    hp = [(0.012, hw / 2 + 0.01), (0.05, hw / 2), (0.06, hw / 4), (0.06, -hw / 4), (0.05, -hw / 2), (0.012, -hw / 2 - 0.01)]
    part.revolve(mat, hp, c, axis=(1, 0, 0), seg=20, cap0=True, cap1=True)
    # spokes: tapered beams from the hub to the barrel, in the wheel plane (with a dish)
    rin, rout = 0.055, BEAD_R - 0.026
    for k in range(spokes):
        a0 = 2 * math.pi * k / spokes + phase
        if style == 'split':
            angs = [a0 - 0.07, a0 + 0.07]
        else:
            angs = [a0]
        for a in angs:
            path = []
            n = 6
            for i in range(n):
                s = i / (n - 1)
                r = K.lerp(rin, rout, s)
                aa = a + (0.22 * math.sin(math.pi * s * 0.9) if style == 'curved' else 0.0)
                x = offset + K.lerp(0.012, 0.0, s) * 0
                path.append(c + np.array([x, r * math.cos(aa), r * math.sin(aa)]))
            wv = [spoke_w * K.lerp(1.25, 0.9, i / (n - 1)) for i in range(n)]
            dv = [spoke_depth * K.lerp(1.1, 0.75, i / (n - 1)) for i in range(n)]
            part.tube(path, wv, mat, seg=6, ry=dv, twist_ref=(1, 0, 0), cap0=False, cap1=False)
            del path


def disc(part, centre, x, r_out, r_in=None, thick=0.005, mat='disc', carrier='rim', bolts=6, holes=True, seg=40,
         wave=False):
    """a brake disc in the plane x = centre.x + x, with its carrier (spider) to the hub"""
    c = np.array(centre, float) + np.array([x, 0, 0])
    r_in = r_in if r_in is not None else r_out - 0.04
    t2 = thick / 2
    if wave:
        # petal (wave) outline: radius modulated round the disc
        rows = []
        n = 72
        for i in range(n):
            a = 2 * math.pi * i / n
            ro = r_out * (1 - 0.025 * (0.5 + 0.5 * math.cos(a * 12)))
            dv = np.array([0, math.cos(a), math.sin(a)])
            rows.append([tuple(c + dv * r_in + [t2, 0, 0]), tuple(c + dv * ro + [t2, 0, 0]), tuple(c + dv * ro - [t2, 0, 0]),
                         tuple(c + dv * r_in - [t2, 0, 0])])
        part.grid(rows, mat, smooth=False, closed_u=True, closed_v=True)
    else:
        prof = [(r_in, t2), (r_out, t2), (r_out, -t2), (r_in, -t2), (r_in, t2)]
        part.revolve(mat, prof, c, axis=(1, 0, 0), seg=seg, smooth=False)
    # carrier: arms from the hub to the disc's inner edge
    for k in range(bolts):
        a = 2 * math.pi * (k + 0.5) / bolts
        dv = np.array([0, math.cos(a), math.sin(a)])
        p0 = c + dv * 0.045
        p1 = c + dv * (r_in + 0.008)
        part.tube([tuple(p0), tuple(p1)], 0.010, carrier, seg=6, ry=0.004, twist_ref=(1, 0, 0))
        part.cylinder('chrome', tuple(p1 + [-0.004 * np.sign(x or 1), 0, 0]), tuple(p1 + [0.004 * np.sign(x or 1), 0, 0]),
                      0.006, seg=8)


def floating_disc(part, centre, x, r_out, r_in, thick=0.0055, ring='disc', carrier='disc_carrier', bobbin='gold',
                  bolt='gold', arms=5, bobbins=10, hub=(0.042, 0.068), hub_bolts=6, wave=0.02, reps=12, n=60, arm_w=0.013,
                  seg=30):
    """a brake disc as the eye reads it: the steel ring in the plane x = centre.x + x (its drilled pattern is the ring
    material's texture: u round the ring, `reps` tiles, v from the inner edge (0) to the outer edge (1); the edge faces
    sample the plain bands), `wave` = depth of the outer edge's petals (fraction of r_out, one per tile); inside it the
    carrier: a narrow ring under the ring's inner edge joined by `arms` arms (`arm_w` wide) to the hub flange, the
    floating bobbins (`bobbins`, 0 for a one-piece disc) across the joint and the hub bolts. The spokes show between the
    arms. n: segments round the steel ring, seg: round the carrier ring (the hub flange gets 2/3 of it)."""
    c = np.array(centre, float) + np.array([x, 0, 0])
    s = 1.0 if x >= 0 else -1.0
    t2 = thick / 2
    rows = [[], [], [], []]
    for i in range(n):
        a = 2 * math.pi * i / n
        ro = r_out * (1 - wave * (0.5 + 0.5 * math.cos(a * reps))) if wave else r_out
        dv = np.array([0, math.cos(a), math.sin(a)])
        rows[0].append(tuple(c + dv * r_in + [t2, 0, 0]))
        rows[1].append(tuple(c + dv * ro + [t2, 0, 0]))
        rows[2].append(tuple(c + dv * ro - [t2, 0, 0]))
        rows[3].append(tuple(c + dv * r_in - [t2, 0, 0]))
    faces, vs = part.grid(rows, ring, smooth=False, closed_u=True, closed_v=True)
    where = {}
    for j, row in enumerate(vs):
        for i, v in enumerate(row):
            where[v] = (i, j)
    for f in faces:
        ids = [where[v][0] for v in f.verts]
        seam = 0 in ids and (n - 1) in ids
        for lp in f.loops:
            i, j = where[lp.vert]
            if seam and i == 0:
                i = n
            lp[part.uv].uv = (i / n * reps, 0.012 if j in (0, 3) else 0.988)
    _orient(part, faces, (1, 0, 0), lambda f: K.G(f.calc_center_median())[0] > c[0] + t2 * 0.5)
    # the carrier: a narrow ring just inside the steel ring, the arms, the hub flange (a touch inboard of the ring)
    xc = -s * 0.001
    cr0, cr1 = r_in - 0.012, r_in - 0.001
    # (both as two flat faces: their 6-7 mm edges never show, and it halves their triangles)
    for (ra, rb), t, sg in (((cr0, cr1), 0.003, seg), ((hub[0], hub[1]), 0.0035, max(12, seg * 2 // 3))):
        for side in (1, -1):
            fs = part.revolve(carrier, [(ra, side * t), (rb, side * t)], tuple(c + [xc, 0, 0]), axis=(1, 0, 0), seg=sg,
                              smooth=False)
            _orient(part, fs, (side, 0, 0), lambda f: True)
    for k in range(arms):
        a = 2 * math.pi * (k + 0.25) / arms
        dv = np.array([0, math.cos(a), math.sin(a)])
        tv = np.array([0, -math.sin(a), math.cos(a)])
        r0, r1 = hub[1] - 0.006, cr0 + 0.004
        part.obox(carrier, tuple(c + [xc, 0, 0] + dv * (r0 + r1) / 2), (0.006, r1 - r0, arm_w),
                  axes=((1, 0, 0), tuple(dv), tuple(tv)))
    for k in range(bobbins):
        a = 2 * math.pi * (k + 0.5) / bobbins
        q = c + np.array([0, math.cos(a), math.sin(a)]) * (r_in - 0.002)
        part.cylinder(bobbin, tuple(q - [0.004, 0, 0]), tuple(q + [0.004, 0, 0]), 0.0062, seg=6, cap=False)
    for k in range(hub_bolts):
        a = 2 * math.pi * (k + 0.5) / hub_bolts
        q = c + [xc, 0, 0] + np.array([0, math.cos(a), math.sin(a)]) * (hub[0] + hub[1]) / 2
        part.cylinder(bolt, tuple(q + [s * 0.003, 0, 0]), tuple(q + [s * 0.0075, 0, 0]), 0.0055, seg=6)


def caliper(part, centre, x, r_disc, angle_deg, size=(0.032, 0.10, 0.05), mat='brake', side=1):
    """a caliper straddling the disc's edge at an angle round the wheel (0 = forward, 90 = up)"""
    a = math.radians(angle_deg)
    dv = np.array([0, math.sin(a), math.cos(a)])
    tv = np.array([0, math.cos(a), -math.sin(a)])
    c = np.array(centre, float) + np.array([x, 0, 0]) + dv * (r_disc - 0.018)
    part.obox(mat, tuple(c + np.array([side * 0.006, 0, 0])), (size[0], size[2], size[1]),
              axes=((1, 0, 0), dv, tv), bevel=0.01, seg=2)


def sprocket(part, centre, x, r, teeth=40, mat='chain'):
    c = np.array(centre, float) + np.array([x, 0, 0])
    prof = [(0.05, 0.003), (r, 0.003), (r, -0.003), (0.05, -0.003)]
    part.revolve(mat, prof, c, axis=(1, 0, 0), seg=teeth, smooth=False)


# ---------------------------------------------------------------- hull (fairing) and other lofts

def u_ring(half, z):
    """a U section: half = [(x, y)] from the left top edge to the bottom centre (x = 0 last); mirrored to the right"""
    left = [(x, y, z) for x, y in half]
    right = [(-x, y, z) for x, y in reversed(half[:-1])]
    return left + right


def polyline(ctl, per, camber=0.0):
    """a polyline through the control points, each segment split into `per` equal steps (the control points stay
    vertices: creases). camber: each segment but the last (the one under the belly to the centre line) bows outwards
    (away from the centre line) by up to `camber` metres at its middle, at most 15 % of its length: a pressed panel
    face between two creases is never flat."""
    out = []
    segs = list(zip(ctl, ctl[1:]))
    for si, (a, b) in enumerate(segs):
        a2, b2 = np.array(a[:2], float), np.array(b[:2], float)
        d = b2 - a2
        L = float(np.linalg.norm(d))
        nrm = np.array([d[1], -d[0]]) / max(L, 1e-9)
        mid = (a2 + b2) / 2
        if nrm[0] * mid[0] < 0 or (abs(mid[0]) < 1e-6 and nrm[0] < 0):
            nrm = -nrm
        bow = min(camber, 0.15 * L) if (camber and si < len(segs) - 1) else 0.0
        for k in range(per):
            t = k / per
            q = [a[i] + (b[i] - a[i]) * t for i in range(len(a))]
            off = bow * math.sin(math.pi * t)
            q[0] += nrm[0] * off
            q[1] += nrm[1] * off
            out.append(tuple(q))
    out.append(tuple(ctl[-1]))
    return out


def hull(part, zs, section, n_half=12, mat='paint', outline=None, sharp_rows=None, crease_per=None, camber=0.0):
    """loft of U sections along z (zs from front to back); section(z) → half control points (top edge → bottom centre).
    outline: closed (z, y) polygon of the panel in side view: faces outside it are removed (rear edge, wheel arch).
    crease_per: straight segments between the control points (`crease_per` steps each) instead of a smooth curve, so
    the control points become creases (angular bodywork)."""
    rings = []
    for z in zs:
        ctl = section(z)
        half = polyline(ctl, crease_per, camber) if crease_per else K.catmull(ctl, n_half)
        half[-1] = (0.0, half[-1][1])
        rings.append(u_ring(half, z))
    faces, vs = part.grid(rings, mat, smooth=True)
    _orient(part, faces, (1, 0, 0), lambda f: K.G(f.calc_center_median())[0] > 0.05)
    if outline is not None:
        clip_outline(part, faces, outline)
    return rings


def _orient(part, faces, outward, sel):
    """make the faces' normals point outwards (tested on the faces sel() picks)"""
    acc = 0.0
    for f in faces:
        if f.is_valid and sel(f):
            n = K.G(f.normal)
            acc += n[0] * outward[0] + n[1] * outward[1] + n[2] * outward[2]
    if acc < 0:
        for f in faces:
            if f.is_valid:
                f.normal_flip()
    part.bm.normal_update()


def clip_outline(part, faces, outline):
    """cut the side outline (z, y) through the given faces and delete the parts outside it"""
    fs = [f for f in faces if f.is_valid]
    K.cut_outline(part.bm, outline, 'side', side=1, keep=None, margin=0.03, min_facing=-2.0)
    dead = []
    for f in part.bm.faces:
        u, v = K._uv(f.calc_center_median(), 'side')
        if not K.inside(outline, u, v):
            dead.append(f)
    return dead


def delete_outside(part, outline, keep=None):
    dead = []
    for f in part.bm.faces:
        if keep is not None and not keep(f):
            continue
        u, v = K._uv(f.calc_center_median(), 'side')
        if not K.inside(outline, u, v):
            dead.append(f)
    bmesh.ops.delete(part.bm, geom=dead, context='FACES')


def closed_loft(part, zs, section, n=24, mat='paint', cap0=True, cap1=True, mats=None):
    """loft of closed sections along z; section(z) → closed list of (x, y) (any count, resampled to n)"""
    rings = []
    for z in zs:
        s = K.resample(section(z), n, closed=True)
        rings.append([(x, y, z) for x, y in s])
    faces = part.loft(rings, mat, closed=True, cap0=cap0, cap1=cap1, mats=mats)
    _orient(part, faces, (1, 0, 0), lambda f: K.G(f.calc_center_median())[0] > 0.02)
    return rings


def superellipse(cx, cy, a, b_top, b_bot, e_top=2.4, e_bot=2.4, n=24, x_scale_bot=1.0):
    """closed section: half-width a, heights above/below the centre; exponents shape the top and bottom"""
    out = []
    for i in range(n):
        t = 2 * math.pi * i / n
        c, s = math.cos(t), math.sin(t)
        e = e_top if s >= 0 else e_bot
        x = math.copysign(abs(c) ** (2 / e), c) * a * (1 if s >= 0 else x_scale_bot)
        y = math.copysign(abs(s) ** (2 / e), s) * (b_top if s >= 0 else b_bot)
        out.append((cx + x, cy + y))
    return out


# ---------------------------------------------------------------- pipes, silencers

def pipe(part, pts, radii, mat='exhaust', seg=14, n=None, cap0=False, cap1=True):
    """a pipe through control points (Catmull-Rom), radius interpolated along it"""
    m = n or max(8, int(sum(np.linalg.norm(np.subtract(pts[i + 1], pts[i])) for i in range(len(pts) - 1)) / 0.03))
    path = K.catmull(pts, m)
    # radius by arc length fraction
    P = np.array(path)
    s = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
    s /= s[-1]
    if isinstance(radii, (int, float)):
        rr = [radii] * len(path)
    else:
        f = K.Pchip(radii)
        rr = [f(t) for t in s]
    return part.tube(path, rr, mat, seg=seg, cap0=cap0, cap1=cap1)


def silencer(part, a, b, r0, r1, mat='exhaust', cap_mat='chrome', seg=18, oval=1.0, end_cap=0.02, tip_r=0.02):
    """a silencer can from a (inlet) to b (outlet): radius r0 → r1, end cap and tail pipe at b"""
    a, b = np.array(a, float), np.array(b, float)
    d = K.unit(b - a)
    L = np.linalg.norm(b - a)
    path, rad = [], []
    n = 8
    for i in range(n):
        s = i / (n - 1)
        path.append(a + (b - a) * s)
        rad.append(K.lerp(r0, r1, s) * (0.92 + 0.08 * math.sin(math.pi * min(1, s * 1.2))))
    part.tube(path, rad, mat, seg=seg, ry=[r * oval for r in rad], twist_ref=(0, 1, 0), cap0=True, cap1=False)
    # end cap and tail pipe
    part.tube([tuple(b - d * 0.003), tuple(b + d * end_cap)], [rad[-1] * 1.0, rad[-1] * 0.82], cap_mat, seg=seg,
              ry=[rad[-1] * oval, rad[-1] * 0.82 * oval], twist_ref=(0, 1, 0), cap0=False, cap1=True)
    part.tube([tuple(b + d * (end_cap - 0.005)), tuple(b + d * (end_cap + 0.02))], tip_r, cap_mat, seg=12, cap1=False)
    part.tube([tuple(b + d * (end_cap + 0.019)), tuple(b + d * (end_cap - 0.01))], tip_r * 0.8, 'trim', seg=12, cap1=True)


# ---------------------------------------------------------------- controls, mirrors, pegs

def clip_on(part, st, side, grip_c, mat_bar='chrome', lever=True, reservoir=None):
    """a clip-on bar from the fork leg (just under the top yoke) to the grip, with a grip, bar-end weight, lever"""
    g = np.array(grip_c, float)
    sgn = 1 if side > 0 else -1
    base = np.array(st.top_leg[0 if sgn > 0 else 1], float)
    out = K.unit(g - base)
    part.tube([tuple(base), tuple(g - out * 0.06)], 0.011, mat_bar, seg=10)
    part.tube([tuple(g - out * 0.065), tuple(g + out * 0.062)], 0.017, 'grip', seg=12)
    part.tube([tuple(g + out * 0.062), tuple(g + out * 0.085)], 0.014, 'chrome', seg=10)
    part.cylinder('trim', tuple(base - out * 0.01), tuple(base + out * 0.035), 0.026, seg=12)
    if lever:
        # lever ahead of the grip, its pivot near the clamp end
        piv = g - out * 0.07 + np.array([0, 0.005, 0.045])
        tip = g + out * 0.07 + np.array([0, -0.01, 0.07])
        part.tube([tuple(piv), tuple(tip)], 0.006, 'chrome', seg=6, ry=0.003)
        part.obox('trim', tuple(g - out * 0.085 + np.array([0, 0.01, 0.02])), (0.04, 0.04, 0.05), bevel=0.01)
    if reservoir is not None:
        part.cylinder('trim', tuple(g - out * 0.11 + np.array([0, 0.02, 0.0])), tuple(g - out * 0.11 + np.array([0, 0.06, 0.0])),
                      0.018, seg=10)


def mirror(part, base, head, size=(0.15, 0.075, 0.04), mat='trim', glass='mirror', stalk_r=0.008, yaw=0.0):
    """a mirror on a stalk: rounded housing with the mirror face towards the rider"""
    b, h = np.array(base, float), np.array(head, float)
    part.tube([tuple(b), tuple(h)], stalk_r, mat, seg=8)
    sgn = 1 if h[0] > 0 else -1
    ax = (1.0, 0, 0)
    fwd = (math.sin(yaw) * sgn, 0, math.cos(yaw))
    part.obox(mat, tuple(h + np.array([sgn * size[0] * 0.25, 0, 0.012])), (size[0], size[1], size[2]),
              axes=(ax, (0, 1, 0), fwd), bevel=min(size) * 0.45, seg=3)
    part.obox(glass, tuple(h + np.array([sgn * size[0] * 0.25, 0, 0.012 - size[2] / 2 - 0.001])),
              (size[0] * 0.86, size[1] * 0.78, 0.004), axes=(ax, (0, 1, 0), fwd), bevel=0.0015)


def peg(part, p, side, mat='chrome', length=0.08, hanger=True):
    """a foot peg (rubber over a stub) and, unless the bike models its own, a plain hanger plate behind it"""
    p = np.array(p, float)
    part.tube([tuple(p - np.array([side * 0.02, 0, 0])), tuple(p + np.array([side * length, 0, 0]))], 0.011, 'grip', seg=8)
    if hanger:
        part.obox('frame2', tuple(p + np.array([-side * 0.01, 0.03, -0.04])), (0.012, 0.11, 0.13), bevel=0.01)


def chain(part, front_c, r_front, rear_c, r_rear, x, mat='chain'):
    """the chain as a thin flat loop round both sprockets"""
    f, r = np.array(front_c, float), np.array(rear_c, float)
    pts = []
    d = K.unit(f - r)
    up = np.array([0, d[2], -d[1]])
    if up[1] < 0:
        up = -up
    for k in range(13):
        a = math.pi / 2 - math.pi * k / 12
        pts.append(f + (d * math.cos(a) + up * math.sin(a)) * r_front)
    for k in range(13):
        a = -math.pi / 2 - math.pi * k / 12
        pts.append(r + (d * math.cos(a) + up * math.sin(a)) * r_rear)
    rings = []
    for p in pts:
        rings.append([tuple(p + np.array([x + 0.008, 0, 0])), tuple(p + np.array([x - 0.008, 0, 0]))])
    # a flat band: inner and outer faces
    n = len(pts)
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        c = (pts[i] + pts[(i + 1) % n]) / 2
        part.face([tuple(a + [x + 0.008, 0, 0]), tuple(b + [x + 0.008, 0, 0]), tuple(b + [x - 0.008, 0, 0]),
                   tuple(a + [x - 0.008, 0, 0])], mat, smooth=False)
        part.face([tuple(a + [x - 0.008, 0, 0]), tuple(b + [x - 0.008, 0, 0]), tuple(b + [x + 0.008, 0, 0]),
                   tuple(a + [x + 0.008, 0, 0])], mat, smooth=False)


def beam_path(part, path, w, h, mat, up=(0, 1, 0), r=0.25, n=None, mats=None):
    """a box-section beam along a 3D path (control points, smoothed): w across (x-ish), h along `up` projected,
    corners rounded by r × the smaller side; w and h may be per-point lists"""
    pts = K.catmull(path, n) if n else [tuple(p) for p in path]
    P, T, N, Bn = K.frame_along(pts)
    upv = np.array(up, float)
    m = len(P)
    ws = w if isinstance(w, (list, tuple)) else [w] * m
    hs = h if isinstance(h, (list, tuple)) else [h] * m
    if len(ws) != m:
        f = K.Pchip([(i / (len(ws) - 1), v) for i, v in enumerate(ws)])
        ws = [f(i / (m - 1)) for i in range(m)]
    if len(hs) != m:
        f = K.Pchip([(i / (len(hs) - 1), v) for i, v in enumerate(hs)])
        hs = [f(i / (m - 1)) for i in range(m)]
    rings = []
    for i in range(m):
        t = T[i]
        u = K.unit(upv - t * (upv @ t))
        sd = np.cross(t, u)
        rr = r * min(ws[i], hs[i])
        corners = [(ws[i] / 2, hs[i] / 2), (-ws[i] / 2, hs[i] / 2), (-ws[i] / 2, -hs[i] / 2), (ws[i] / 2, -hs[i] / 2)]
        poly = K.round_poly(corners, rr, seg=2)
        rings.append([tuple(P[i] + sd * a + u * b) for a, b in poly])
    faces = part.loft(rings, mat, closed=True, cap0=True, cap1=True, mats=mats)
    return faces


def edge_return(part, src, depth, mat, keep=None):
    """a return flange along a single-skinned panel's free edges: strips from each edge straight in (against the
    vertex normals) by `depth`, so the panel shows its thickness and a shadow line where it laps over another"""
    bm = src.bm
    bm.normal_update()
    for e in bm.edges:
        if len(e.link_faces) != 1:
            continue
        lp = e.link_loops[0]
        a, b = lp.vert, lp.link_loop_next.vert
        A, Bv = np.array(K.G(a.co)), np.array(K.G(b.co))
        if keep is not None and not keep((A + Bv) / 2):
            continue
        na, nb = np.array(K.G(a.normal)), np.array(K.G(b.normal))
        part.face([tuple(Bv), tuple(A), tuple(A - na * depth), tuple(Bv - nb * depth)], mat, smooth=False)


def chamfered_can(part, a, b, half_w, half_h, mat, chamfer=0.45, slant=0.0, n=None):
    """an angular silencer can from a to b: elongated octagon sections (half widths across, half heights in the
    vertical plane through the axis) per station (lists over 0..1), the outlet end slanted by `slant` (m, top
    further back than the bottom for > 0); returns the last ring"""
    a, b = np.array(a, float), np.array(b, float)
    d = K.unit(b - a)
    up = K.unit(np.array([0.0, 1.0, 0.0]) - d * d[1])
    side = np.cross(d, up)          # the same winding as beam_path: normals outwards
    m = n or len(half_w)
    fw = K.Pchip([(i / (len(half_w) - 1), v) for i, v in enumerate(half_w)])
    fh = K.Pchip([(i / (len(half_h) - 1), v) for i, v in enumerate(half_h)])
    rings = []
    for i in range(m):
        s = i / (m - 1)
        w, h = fw(s), fh(s)
        c = a + (b - a) * s
        poly = [(w, chamfer * h), (chamfer * w, h), (-chamfer * w, h), (-w, chamfer * h), (-w, -chamfer * h),
                (-chamfer * w, -h), (chamfer * w, -h), (w, -chamfer * h)]
        ring = []
        for u, v in poly:
            q = c + side * u + up * v
            if i == m - 1:
                q = q + d * slant * (v / h)
            ring.append(tuple(q))
        rings.append(ring)
    part.loft(rings, mat, closed=True, cap0=True, cap1=True, smooth=False)
    return rings[-1]
