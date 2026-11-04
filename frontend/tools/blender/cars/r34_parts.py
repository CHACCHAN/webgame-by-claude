"""
Parts added onto the R34's finished shell: the adjustable rear wing on two stays, door mirrors on their sails, wipers
and washer nozzles, door handles, side repeaters and the bonnet / door / lid / fuel-lid shut lines, and a basic
interior seen through the glass (lining of the cabin, dash, steering wheel on the right, front buckets, rear bench,
console, parcel shelf).

Wing (tail-on photo, 1999 V-Spec 1): span 1.55 m, stays at |x| 0.47, top of the plane at y 1.21, chord over the
lid's rear half with the black adjustable flap behind. Mirrors: housing about 0.17 x 0.10 x 0.11 m on a black sail at
the window's front corner.
"""
import math

import bmesh
import numpy as np
from mathutils import Matrix

import r34_fit as FIT
import r34_kit as K
import r34_shell as SH


class Surfaces:
    """ray casts against several meshes, nearest hit"""

    def __init__(self, *objs):
        self.s = [FIT.Surface(o) for o in objs]

    def onto(self, u, v, axis, side, lift=0.0):
        best = None
        for s in self.s:
            p = s.onto(u, v, axis, side, lift)
            if p is not None and (best is None or p[FIT.AX[axis]] * side > best[FIT.AX[axis]] * side):
                best = p
        return best


def quad(part, q, mat, want, smooth=False, uvs=None):
    FIT.fix(part.face([tuple(p) for p in q], mat, smooth=smooth, uvs=uvs), np.asarray(want, float))


def loft(part, sections, mat, smooth=True, cap0=True, cap1=True, mats=None):
    """faces between closed sections (lists of points of equal length); normals away from each section's centre"""
    for i in range(len(sections) - 1):
        A, Bs = np.array(sections[i]), np.array(sections[i + 1])
        c = 0.5 * (A.mean(axis=0) + Bs.mean(axis=0))
        n = len(A)
        for j in range(n):
            j2 = (j + 1) % n
            q = [A[j], A[j2], Bs[j2], Bs[j]]
            m = mats(i, j) if mats else mat
            quad(part, q, m, np.mean(q, axis=0) - c, smooth=smooth)
    for S, other, on in ((sections[0], sections[1], cap0), (sections[-1], sections[-2], cap1)):
        if on:
            S = np.array(S)
            quad(part, S, mat, S.mean(axis=0) - np.array(other).mean(axis=0))


def strip(part, surf, pts, axis, side, width, mat, lift=0.0008):
    """a thin line laid on the surface along a polyline in the view plane of `axis` (shut lines)"""
    pts = [np.array(p, float) for p in pts]
    want = np.zeros(3)
    want[FIT.AX[axis]] = side
    for a, b in zip(pts[:-1], pts[1:]):
        d = b - a
        L = np.linalg.norm(d)
        if L < 1e-6:
            continue
        nrm = np.array((-d[1], d[0])) / L * width / 2
        q2 = [a - nrm, b - nrm, b + nrm, a + nrm]
        q = [surf.onto(p[0], p[1], axis, side, lift) for p in q2]
        if any(p is None for p in q):
            continue
        quad(part, q, mat, want)


def polyline(pts, step=0.04):
    out = []
    for a, b in zip(pts[:-1], pts[1:]):
        n = max(1, int(math.dist(a, b) / step))
        for k in range(n):
            t = k / n
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    out.append(pts[-1])
    return out


# ---------------------------------------------------------------- wing

WING_X = 0.775
STAY_X = 0.47


def airfoil(n=14):
    """closed section (chord c 0..1 from the leading edge, y offset) for a cambered plane, ccw from the trailing edge"""
    up, lo = [], []
    for k in range(n + 1):
        c = 0.5 - 0.5 * math.cos(math.pi * k / n)
        t = 0.12 * (1.4845 * math.sqrt(c) - 0.63 * c - 1.758 * c * c + 1.4215 * c ** 3 - 0.5075 * c ** 4)
        camber = 0.035 * math.sin(math.pi * c)
        up.append((c, camber + t / 2))
        lo.append((c, camber - t / 2))
    return up[::-1] + lo[1:-1]


def wing(part, deck_y):
    foil = airfoil()
    xs = list(np.linspace(-WING_X, WING_X, 23))
    secs = []
    for x in xs:
        t = abs(x) / WING_X
        chord = 0.25 - 0.03 * max(0.0, (t - 0.85) / 0.15) ** 2
        le_z = -1.86 - 0.012 * t * t
        y0 = 1.152 - 0.018 * max(0.0, (t - 0.80) / 0.20) ** 1.5
        sec = []
        for c, yo in foil:
            # the plane tilts nose-down slightly (rear edge higher): angle of attack for downforce
            sec.append((x, y0 + yo * chord + 0.03 * c, le_z - c * chord))
        secs.append(sec)
    loft(part, secs, 'paint', smooth=True)
    # adjustable flap (black) on top of the trailing edge
    fx = np.linspace(-WING_X + 0.035, WING_X - 0.035, 15)
    fsecs = []
    for x in fx:
        sec = []
        for c, yo in airfoil(8):
            sec.append((x, 1.194 + yo * 0.075 + 0.045 * c, -2.06 - c * 0.075))
        fsecs.append(sec)
    loft(part, fsecs, 'trim', smooth=True)
    # rounded pods closing the plane's tips
    for s in (1, -1):
        pod = []
        for k in range(1, 10):
            a = math.pi * k / 10
            x = s * (WING_X - 0.03 + 0.06 * (0.5 - 0.5 * math.cos(a)))
            r = math.sin(a)
            sec = []
            for j in range(16):
                b = 2 * math.pi * j / 16
                sec.append((x, 1.17 + 0.03 * r * math.sin(b) + 0.012 * math.cos(b),
                            -1.99 + 0.14 * r * math.cos(b)))
            pod.append(sec)
        loft(part, pod, 'paint', smooth=True)
    # stays: tapered blades from the lid to the plane
    for s in (1, -1):
        x = s * STAY_X
        secs = []
        for y, zc, ch, w in ((deck_y(x, -1.98) - 0.01, -1.99, 0.17, 0.034), (1.05, -1.975, 0.13, 0.028),
                             (1.155, -1.965, 0.10, 0.024)):
            sec = []
            for j in range(10):
                a = 2 * math.pi * j / 10
                sec.append((x + w / 2 * math.sin(a), y, zc + ch / 2 * math.cos(a)))
            secs.append(sec)
        loft(part, secs, 'paint', smooth=True, cap0=False, cap1=False)


# ---------------------------------------------------------------- mirrors, wipers, handles, lines


def corner_poly(pts, radii, seg=4):
    """a closed polygon with its own radius at each corner"""
    out = []
    n = len(pts)
    for i in range(n):
        p0, p1, p2 = (np.array(pts[k % n], float) for k in (i - 1, i, i + 1))
        a, b = p0 - p1, p2 - p1
        la, lb = np.linalg.norm(a), np.linalg.norm(b)
        rr = min(radii[i], la * 0.45, lb * 0.45)
        q0, q2 = p1 + a / la * rr, p1 + b / lb * rr
        for k in range(seg + 1):
            t = k / seg
            out.append(tuple((1 - t) ** 2 * q0 + 2 * t * (1 - t) * p1 + t * t * q2))
    return out


def mirror(part, surf, s):
    """door mirror: a body-coloured wedge on a short black foot at the window's front corner, glass at the back"""
    hit = surf.onto(0.47, 0.925, 'x', s)
    xs = abs(hit[0]) if hit is not None else 0.80
    # black sail on the window's front corner
    sail = [(0.735, 0.935), (0.43, 0.935), (0.45, 0.975), (0.66, 1.055), (0.73, 1.06)]
    if s < 0:
        sail = sail[::-1]
    FIT.patch(part, surf, FIT.resample(sail, 20), 'x', s, 'trim', lift=0.003, rings=2)
    # foot
    x0, x1 = xs - 0.02, xs + 0.06
    part.box('trim', min(s * x0, s * x1), max(s * x0, s * x1), 0.952, 0.992, 0.425, 0.505, bevel=0.008)
    # housing: sections across the mirror's span, from the foot out to the rounded outer end
    secs = []
    n = 9
    for k in range(n):
        t = k / (n - 1)
        x = xs + 0.045 + 0.175 * t
        zb, zf = 0.382 + 0.008 * t, 0.535 - 0.050 * t ** 1.3
        yb, yt = 0.952 + 0.012 * t, 1.088 - 0.012 * t
        if t > 0.75:                                   # round the outer end off
            e = (t - 0.75) / 0.25
            c = 1 - 0.55 * e ** 2
            zm, ym = 0.5 * (zb + zf), 0.5 * (yb + yt)
            zf, yb, yt = zm + (zf - zm) * c, ym + (yb - ym) * c, ym + (yt - ym) * c
            zb = zb + (zm - zb) * 0.35 * e ** 2
            x = xs + 0.045 + 0.175 * (0.75 + 0.25 * math.sin(e * math.pi / 2))
        loop = corner_poly([(zb, yb), (zf, yb + 0.012), (zf, yt - 0.01), (zb, yt)], [0.008, 0.03, 0.04, 0.008], 4)
        loop = FIT.resample(loop, 28)
        secs.append([(s * x, y, z) for z, y in loop])
    loft(part, secs, 'paint', smooth=True, cap0=True, cap1=True)
    # the glass on the flat back
    xa, xb = xs + 0.06, xs + 0.18
    gl = FIT.rounded_poly([(xa, 0.966), (xb, 0.972), (xb, 1.070), (xa, 1.074)], 0.012)
    pts = [(s * x, y, 0.382 + 0.008 * (x - xs - 0.045) / 0.175 - 0.002) for x, y in gl]
    c = np.mean(np.array(pts), axis=0)
    for a, b in zip(pts, pts[1:] + pts[:1]):
        quad(part, [a, b, tuple(c)], 'chrome', (0, 0, -1))


def frames(part, glass):
    """black frames round the glass: door sashes and the quarter window's surround, the windscreen's and the
    backlight's ceramic border"""
    bm = bmesh.new()
    bm.from_mesh(glass.data)
    bm.transform(glass.matrix_world)
    bm.normal_update()
    for e in bm.edges:
        if len(e.link_faces) != 1:
            continue
        f = e.link_faces[0]
        a, b = np.array(K.G(e.verts[0].co)), np.array(K.G(e.verts[1].co))
        n = np.array(K.G(f.normal))
        c = np.array(K.G(f.calc_center_median()))
        d = b - a
        L = np.linalg.norm(d)
        if L < 1e-6:
            continue
        inward = np.cross(n, d / L)
        if np.dot(inward, c - a) < 0:
            inward = -inward
        w = 0.042 if abs(n[0]) < 0.55 else 0.024
        lift = n * 0.0025
        ext = d / L * 0.004          # overlap neighbours at the corners
        q = [a - ext + lift, b + ext + lift, b + ext + inward * w + lift, a - ext + inward * w + lift]
        quad(part, q, 'trim', n)
    bm.free()


def wipers(part, surf):
    for (x0, x1, z, px) in ((-0.64, -0.05, 0.855, -0.04), (-0.07, 0.55, 0.892, 0.46)):
        # blade: a low ridge lying on the glass
        n = 8
        pts = [(x0 + (x1 - x0) * k / n, z) for k in range(n + 1)]
        top = [surf.onto(x, zz, 'y', 1, 0.014) for x, zz in pts]
        for w, lift in ((0.010, 0.014),):
            for a, b, pa, pb in zip(top[:-1], top[1:], pts[:-1], pts[1:]):
                if a is None or b is None:
                    continue
                fa = surf.onto(pa[0], pa[1] + 0.009, 'y', 1, 0.003)
                fb = surf.onto(pb[0], pb[1] + 0.009, 'y', 1, 0.003)
                ra = surf.onto(pa[0], pa[1] - 0.009, 'y', 1, 0.003)
                rb = surf.onto(pb[0], pb[1] - 0.009, 'y', 1, 0.003)
                if any(p is None for p in (fa, fb, ra, rb)):
                    continue
                quad(part, [fa, fb, b, a], 'trim', (0, 0.6, 1))
                quad(part, [a, b, rb, ra], 'trim', (0, 0.6, -1))
        # arm from the pivot (on the cowl) to the blade's middle
        xm = 0.5 * (x0 + x1)
        arm = [(px, 0.80), (xm + 0.04 * np.sign(px - xm), z + 0.01)]
        for k in range(6):
            t0, t1 = k / 6, (k + 1) / 6
            p0 = (arm[0][0] + (arm[1][0] - arm[0][0]) * t0, arm[0][1] + (arm[1][1] - arm[0][1]) * t0)
            p1 = (arm[0][0] + (arm[1][0] - arm[0][0]) * t1, arm[0][1] + (arm[1][1] - arm[0][1]) * t1)
            d = np.array(p1) - np.array(p0)
            nrm = np.array((-d[1], d[0])) / np.linalg.norm(d) * 0.007
            q = [surf.onto(*(np.array(p) + o), 'y', 1, 0.02) for p, o in ((p0, -nrm), (p1, -nrm), (p1, nrm), (p0, nrm))]
            if all(p is not None for p in q):
                quad(part, q, 'trim', (0, 1, 0))
        pv = surf.onto(px, 0.80, 'y', 1)
        part.cylinder('trim', (px, (pv[1] if pv is not None else 0.98) + 0.012, 0.80), 0.016, 0.024, axis='y',
                      segments=10)
    # washer nozzles on the bonnet's rear edge
    for x in (-0.22, 0.22):
        p = surf.onto(x, 0.95, 'y', 1)
        if p is not None:
            part.box('trim', x - 0.012, x + 0.012, p[1] - 0.004, p[1] + 0.009, 0.94, 0.965, bevel=0.003)


def handles(part, surf):
    for s in (1, -1):
        rec = FIT.rounded_poly([(-0.42, 0.826), (-0.21, 0.826), (-0.21, 0.866), (-0.42, 0.866)], 0.014)
        lever = FIT.rounded_poly([(-0.405, 0.836), (-0.24, 0.836), (-0.24, 0.857), (-0.405, 0.857)], 0.009)
        if s < 0:
            rec, lever = rec[::-1], lever[::-1]
        FIT.patch(part, surf, FIT.resample(rec, 24), 'x', s, 'trim', lift=0.0012, rings=2)
        FIT.patch(part, surf, FIT.resample(lever, 24), 'x', s, 'paint', lift=0.006, rings=2)
        # side repeater behind the front wheel
        rep = FIT.rounded_poly([(0.80, 0.708), (0.87, 0.708), (0.87, 0.732), (0.80, 0.732)], 0.01)
        if s < 0:
            rep = rep[::-1]
        FIT.patch(part, surf, FIT.resample(rep, 20), 'x', s, 'amber', lift=0.002, rings=2)


def door_line(part, surf):
    """the low character line on the doors (y ~0.52) from the front wheel arch to the rear one: a small ridge whose
    upper face tilts up (it catches the sky, a light line on photos) above a long shallow face back into the side"""
    prof = [(0.540, 0.0006), (0.526, 0.0040), (0.520, 0.0050), (0.503, 0.0016), (0.488, 0.0006)]
    zs = np.linspace(0.985, -0.985, 67)
    for s in (1, -1):
        rows = []
        for z in zs:
            e = min(1.0, (0.985 - abs(z)) / 0.06)
            e = e * e * (3 - 2 * e)
            rows.append([surf.onto(z, y, 'x', s, 0.0006 + (lift - 0.0006) * e) for y, lift in prof])
        for i in range(len(rows) - 1):
            for k in range(len(prof) - 1):
                q = [rows[i][k], rows[i + 1][k], rows[i + 1][k + 1], rows[i][k + 1]]
                if any(p is None for p in q):
                    continue
                quad(part, q, 'paint', (s, 0.0, 0.0))


def shut_lines(part, surf, glass_surf):
    w = 0.0045
    for s in (1, -1):
        # doors: front edge behind the front wheel arch, rear edge ahead of the rear arch, then up to the B-pillar
        strip(part, surf, polyline([(0.735, 0.24), (0.725, 0.70), (0.72, 0.93)]), 'x', s, w, 'trim')
        strip(part, surf, polyline([(-0.615, 0.24), (-0.62, 0.70), (-0.60, 0.93)]), 'x', s, w, 'trim')
    # bonnet: rear edge at the cowl, sides along the wings' tops, front edge over the lamps
    strip(part, surf, polyline([(-0.735, 0.875), (0.735, 0.875)]), 'y', 1, w, 'trim')
    for s in (1, -1):
        strip(part, surf, polyline([(s * 0.735, 0.875), (s * 0.745, 1.5), (s * 0.77, 2.02)]), 'y', 1, w, 'trim')
    strip(part, surf, polyline([(-0.84, 0.753), (0.84, 0.753)]), 'z', 1, w, 'trim')
    # boot lid: sides on the deck, rear edge between the inner lamps
    for s in (1, -1):
        strip(part, surf, polyline([(s * 0.64, -1.53), (s * 0.645, -2.0)]), 'y', 1, w, 'trim')
        strip(part, surf, polyline([(s * 0.60, 0.978), (s * 0.405, 0.93), (s * 0.405, 0.72)]), 'z', -1, w, 'trim')
    strip(part, surf, polyline([(0.405, 0.72), (-0.405, 0.72)]), 'z', -1, w, 'trim')
    # fuel lid: right rear quarter (car's right = -x)
    fl = FIT.resample(FIT.rounded_poly([(-1.06, 0.78), (-0.92, 0.78), (-0.92, 0.88), (-1.06, 0.88)], 0.02), 24)
    strip(part, surf, fl + [fl[0]], 'x', -1, 0.004, 'trim')


# ---------------------------------------------------------------- interior


def rbox(part, mat, centre, size, rot_x=0.0, bevel=0.01):
    """a bevelled box rotated about x (game frame), for seats"""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(size[0], size[2], size[1]), verts=bm.verts)
    if bevel:
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=bevel, segments=2, profile=0.5, affect='EDGES',
                        clamp_overlap=True)
    m = Matrix.Translation(K.B(*centre)) @ Matrix.Rotation(rot_x, 4, 'X')   # rot_x < 0 leans the top back
    bmesh.ops.transform(bm, matrix=m, verts=bm.verts)
    part.merge(bm, mat, smooth=True)


def lining(part, grid, classify):
    """the cabin's inside: the shell's inner face (moved in 2.5 cm, turned inwards) except the glass"""
    P, named, us, vs, S = grid
    zs = S[:, 0, 2]
    nr = S.shape[1]
    rows = [i for i in range(len(us)) if -1.52 < zs[i] < 0.86]
    rows = rows[::2] + ([rows[-1]] if (len(rows) - 1) % 2 else [])
    cols = list(range(4, nr, 2)) + ([nr - 1] if (nr - 1 - 4) % 2 else [])
    for i, i1 in zip(rows[:-1], rows[1:]):
        for j, j1 in zip(cols[:-1], cols[1:]):
            if all(classify(a, b) == 'glass' for a in range(i, i1) for b in range(j, j1)):
                continue
            # keep clear of the wheel arches: low on the sides only between the arches (door cards)
            zq = 0.5 * (zs[i] + zs[i1])
            if j < (14 if -0.95 < zq < 0.90 else 18):
                continue
            for sg in (1, -1):
                q = []
                for (a, b) in ((i, j), (i1, j), (i1, j1), (i, j1)):
                    p = S[a, b].copy()
                    p[0] *= sg
                    d = np.array((-p[0], 0.72 - p[1], 0.0))
                    nd = np.linalg.norm(d)
                    q.append(p + d / max(nd, 1e-6) * 0.025)
                c = np.mean(q, axis=0)
                quad(part, q, 'interior', np.array((0.0, 0.72, c[2])) - c, smooth=True)


def interior(part):
    # floor and bulkheads
    part.box('interior', -0.70, 0.70, 0.20, 0.25, -0.95, 0.80)
    part.box('interior', -0.52, 0.52, 0.20, 0.25, -1.40, -0.95)
    for sx in (-1, 1):                                                   # rear wheel tubs
        part.box('interior', min(sx * 0.52, sx * 0.60), max(sx * 0.52, sx * 0.60), 0.25, 0.62, -1.40, -0.95)
    part.box('interior', -0.72, 0.72, 0.25, 0.62, 0.70, 0.80)            # foot well wall / firewall
    part.box('interior', -0.52, 0.52, 0.25, 0.95, -1.40, -1.30)          # behind the rear seat
    part.box('interior', -0.66, 0.66, 0.95, 0.975, -1.52, -1.02)         # parcel shelf
    # dash: a deep slab under the windscreen with the binnacle on the right (driver)
    part.box('interior', -0.74, 0.74, 0.62, 0.86, 0.46, 0.84, bevel=0.03)
    part.box('interior', -0.52, -0.22, 0.86, 0.93, 0.48, 0.66, bevel=0.025)
    part.box('trim', -0.11, 0.11, 0.62, 0.82, 0.40, 0.47)                # centre stack
    part.box('interior', -0.11, 0.11, 0.25, 0.48, -0.55, 0.45, bevel=0.02)   # console
    # steering wheel (right-hand drive: driver at -x)
    sw = (-0.37, 0.86, 0.38)
    tilt = math.radians(22)
    bm = bmesh.new()
    segs, ts = 24, 8
    R, r = 0.18, 0.016
    vs = []
    for i in range(segs):
        a = 2 * math.pi * i / segs
        ring = []
        for j in range(ts):
            b = 2 * math.pi * j / ts
            rr = R + r * math.cos(b)
            ring.append(bm.verts.new((rr * math.cos(a), rr * math.sin(a), r * math.sin(b))))
        vs.append(ring)
    for i in range(segs):
        for j in range(ts):
            bm.faces.new([vs[i][j], vs[(i + 1) % segs][j], vs[(i + 1) % segs][(j + 1) % ts], vs[i][(j + 1) % ts]])
    bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=0.05, radius2=0.05, depth=0.05)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    # torus lies in its local xy plane; face it to the driver: rotate about x by 90 - tilt
    m = Matrix.Translation(K.B(*sw)) @ Matrix.Rotation(math.radians(90) - tilt, 4, 'X')
    bmesh.ops.transform(bm, matrix=m, verts=bm.verts)
    part.merge(bm, 'trim', smooth=True)
    part.cylinder('trim', (-0.37, 0.80, 0.52), 0.03, 0.30, axis='z', segments=10)
    # front buckets
    for x in (-0.37, 0.37):
        rbox(part, 'interior', (x, 0.33, -0.08), (0.50, 0.10, 0.50), 0.0, 0.03)
        rbox(part, 'interior', (x, 0.70, -0.40), (0.52, 0.66, 0.11), math.radians(-14), 0.035)
        for b in (-1, 1):
            rbox(part, 'interior', (x + b * 0.23, 0.62, -0.38), (0.07, 0.42, 0.14), math.radians(-14), 0.025)
        rbox(part, 'interior', (x, 1.09, -0.48), (0.26, 0.14, 0.10), math.radians(-14), 0.03)
    # rear bench (two places)
    rbox(part, 'interior', (0.0, 0.34, -0.80), (1.02, 0.12, 0.40), 0.0, 0.03)
    rbox(part, 'interior', (0.0, 0.66, -1.16), (1.02, 0.56, 0.12), math.radians(-22), 0.03)


# ---------------------------------------------------------------- assembly


def build(mats, parent, shell, bumper, glass, grid, classify):
    out = []
    surf = FIT.Surface(shell)
    deck = lambda x, z: surf.onto(x, z, 'y', 1)[1]
    w = K.Part('wing')
    wing(w, deck)
    out.append(('wing', w.build(mats, merge_dist=0)))
    d = K.Part('details')
    both = Surfaces(shell, glass) if glass is not None else surf
    for s in (1, -1):
        mirror(d, surf, s)
    wipers(d, both)
    if glass is not None:
        frames(d, glass)
    handles(d, surf)
    door_line(d, surf)
    shut_lines(d, surf, both)
    out.append(('details', d.build(mats, merge_dist=0)))
    cab = K.Part('interior')
    lining(cab, grid, classify)
    interior(cab)
    out.append(('interior', cab.build(mats, merge_dist=0)))
    for _, o in out:
        o.parent = parent
    return out
