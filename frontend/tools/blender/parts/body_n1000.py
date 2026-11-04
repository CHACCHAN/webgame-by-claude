"""
Body shell of the Keikyu New 1000 series, aluminium cars (1st batch, 2002): sides, roof, the rounded gangway ends, the
cab end, the recessed passenger doors, and the painted textures (red body, cream window band, windows, door leaves, the
cab's black glass area, wiper cover and lamp housings) drawn here with numpy so their edges stay sharp.

Figures (ja.wikipedia 京急1000形電車 (2代), 2026-11-03): body width 2,830 mm; doors 1,300 × 1,850 mm; windows between the
doors 2,325 mm (two panes and a 75 mm pillar on the 1st batch), at the car ends 1,455 mm; car end to the nearest door
centre 3,345 mm; all windows fixed and flush with the body. Measured on photos (Commons, see docs/ASSETS.md):
heights of the band, windows and doors (Keikyu-N1000-ALcar.jpg), the cab face head-on (KEIKYU N1000 SERIES 1001-.jpg:
black glass area |x| ≤ 1.285, 2.05…3.44 m; wiper cover 1.67…2.05 m; lamp housings |x| 0.69…1.12 at 1.39 m).
Our estimates: the section's shoulder and roof arcs, the cab's rake (≈ 9°) and plan bulge, the corner radius.

Frame: the game's car frame of train_kit (x left, y up, z forward, metres). A cab car has its cab at +z.
"""
import json
import math
import os

import bmesh
import bpy
import numpy as np
from mathutils import Vector, geometry

import train_kit as K

# ---------------------------------------------------------------- dimensions
HW = 1.415              # half the body width
BOTTOM = 0.985          # lower edge of the body side
EAVE = 3.12             # top of the vertical side, start of the shoulder
SHOULDER = 0.45         # shoulder radius (head-on outline of photo 02)
ROOF = 3.62             # roof at the centre line
GUTTER = 3.30           # red below, grey roof above (on the sides)
END = 8.75              # gangway ends
SILL = 1.14             # door sill
DOOR_TOP = 2.99
DOOR_W = 1.30
DOOR_DEPTH = 0.035      # doors sit this far into the side
BAND = (1.75, 3.00)     # cream round the windows
WIN = (1.935, 2.81)     # side windows (1st batch: 20 mm lower at the top than later batches)
DOORS = (-5.405, 0.0, 5.405)
CAB_DOORS = (-5.405, 0.0, 5.405)
# cab car, between door 1 and the cab (measured on photos 18, 09, 02: side-layout notes in the PROGRESS log)
CREW_DOOR = (7.22, 7.94, 1.14, 2.93)      # z0, z1, y0, y1: hinged, red, two grab rails at its rear edge
SMALL_WINDOW = (6.855, 7.015)             # glass; behind the crew door, beside the end cross seats
# side destination display and side lamp, right side (−x); the left side has them point-symmetric (z → −z)
SIDE_SIGN = (-2.39, 3.13, 0.88, 0.14)     # centre z, centre y, width, height
SIDE_LAMP = (-3.40, 3.14, 0.04)           # z, y, radius

# the cab end: centre-line profile of the face (y, z), its plan bulge, the corner radius along the outline
CAB_PROFILE = [(0.985, 8.890), (1.45, 8.905), (1.90, 8.895), (2.10, 8.885), (2.60, 8.825), (3.10, 8.738), (3.44, 8.668), (3.70, 8.60)]
CAB_BULGE = 0.24        # face centre ahead of its edges (at x = ±HW) by this much
CAB_R_SIDE = 0.48
CAB_R_TOP = 0.25
CAB_JOIN = 7.95         # body sweep ends here on a cab car, the nose starts
END_R = 0.07            # rounding of a gangway end
ROOF_GREY_END = 7.75    # on a cab car, the roof's grey stops here and the red front top begins

# paint (sRGB)
RED = (0.816, 0.063, 0.122)      # #d0101f
CREAM = (0.930, 0.893, 0.812)    # #ede4cf: ivory, as the band reads on sunlit photos (#efdfcf, #dbc8b9)
GLASS = (0.055, 0.075, 0.072)
SIDE_GLASS = (0.115, 0.132, 0.140)   # the saloon seen dimly through the side windows
GASKET = (0.07, 0.07, 0.075)
FRAME = (0.06, 0.06, 0.065)
SEAM = (0.18, 0.04, 0.06)
ROOF_GREY = '#8d8a84'

# ---------------------------------------------------------------- the section


def _roof_geometry():
    r = SHOULDER
    a = HW - r
    b = EAVE - ROOF
    rr = (r * r - a * a - b * b) / (2 * b + 2 * r)       # roof arc radius, tangent to the shoulder
    theta = math.atan2(EAVE - (ROOF - rr), a)           # where the two arcs meet
    return rr, theta


def half_profile():
    """[(x, y, nx, ny)] from the bottom of the left side (+x) up to the roof's centre line"""
    pts = []
    # the bottom tucks in a little; offsets there stay horizontal (the cab corner keeps its plan radius to the bottom)
    for x, y in ((HW - 0.034, BOTTOM), (HW - 0.016, 1.03), (HW - 0.005, 1.07), (HW - 0.0005, 1.105)):
        pts.append((x, y, 1.0, 0.0))
    ys = [SILL, DOOR_TOP, EAVE, BAND[0], BAND[1]]
    for y in np.arange(1.20, EAVE - 0.02, 0.08):
        if all(abs(y - k) > 0.025 for k in ys):
            ys.append(float(y))
    for y in sorted(ys):
        pts.append((HW, y, 1.0, 0.0))
    r = SHOULDER
    rr, theta = _roof_geometry()
    ns = 8
    for k in range(1, ns + 1):
        t = theta * k / ns
        pts.append((HW - r + r * math.cos(t), EAVE + r * math.sin(t), math.cos(t), math.sin(t)))
    nr = 9
    for k in range(1, nr + 1):
        a = theta + (math.pi / 2 - theta) * k / nr
        x = rr * math.cos(a)
        pts.append((0.0 if k == nr else x, ROOF - rr + rr * math.sin(a), math.cos(a), math.sin(a)))
    return pts


def ring():
    """the full section: right bottom (−x) over the roof to the left bottom; pairs (i, n−1−i) share a height"""
    half = half_profile()
    right = [(-x, y, -nx, ny) for x, y, nx, ny in half]
    return right + list(reversed(half[:-1]))


# ---------------------------------------------------------------- the cab end as a height field


def _pchip(pts):
    ys = np.array([p[0] for p in pts])
    zs = np.array([p[1] for p in pts])
    h = np.diff(ys)
    d = np.diff(zs) / h
    m = np.zeros_like(zs)
    for i in range(1, len(zs) - 1):
        if d[i - 1] * d[i] > 0:
            w1, w2 = 2 * h[i] + h[i - 1], h[i] + 2 * h[i - 1]
            m[i] = (w1 + w2) / (w1 / d[i - 1] + w2 / d[i])
    m[0], m[-1] = d[0], d[-1]

    def f(y):
        y = min(max(y, ys[0]), ys[-1])
        i = min(max(int(np.searchsorted(ys, y)) - 1, 0), len(ys) - 2)
        t = (y - ys[i]) / h[i]
        h00, h10, h01, h11 = 2 * t ** 3 - 3 * t ** 2 + 1, t ** 3 - 2 * t ** 2 + t, -2 * t ** 3 + 3 * t ** 2, t ** 3 - t ** 2
        return h00 * zs[i] + h10 * h[i] * m[i] + h01 * zs[i + 1] + h11 * h[i] * m[i + 1]
    return f


_ZC = _pchip(CAB_PROFILE)


def face_z(x, y):
    """the cab face before its rounding: raked centre line, bulged in plan"""
    return _ZC(y) - CAB_BULGE * (x / HW) ** 2


def corner_radius(y):
    """rounding between the face and the sides (large) or the roof (smaller), blended along the outline"""
    return CAB_R_SIDE + (CAB_R_TOP - CAB_R_SIDE) * K.smoothstep(2.55, 3.15, y)


class Nose:
    """
    The cab end's vertices, before they become faces: for every ring point a column running from the side wall into
    the face through a quarter-round (z = face − R·(1 − sin φ) at an offset R·(1 − cos φ)), and the face between the
    columns' ends as a ladder of rows across the car. Also gives the texture coordinate u (arc length from the centre
    line along each row) for painting.
    """

    def __init__(self, steps=10, across=28):
        self.ring = ring()
        n = len(self.ring)
        self.half = (n + 1) // 2
        self.steps = steps
        self.cols = []          # cols[s][k] = (x, y, z), k = 0 at the side wall
        self.radius = []
        for x, y, nx, ny in self.ring:
            r = corner_radius(y)
            col = []
            for k in range(steps + 1):
                phi = (math.pi / 2) * k / steps
                d = r * (1 - math.cos(phi))
                px, py = x - nx * d, y - ny * d
                col.append((px, py, face_z(px, py) - r * (1 - math.sin(phi))))
            self.cols.append(col)
            self.radius.append(r)
        # the face: rows between the pairs' column ends
        self.rows = []
        for i in range(self.half):
            a, b = self.cols[i][-1], self.cols[n - 1 - i][-1]
            if abs(a[0] - b[0]) < 1e-6:
                self.rows.append([a])
                continue
            row = []
            for k in range(across + 1):
                t = k / across
                x = a[0] + (b[0] - a[0]) * t
                y = a[1] + (b[1] - a[1]) * t
                row.append((x, y, face_z(x, y)))
            self.rows.append(row)

    def full_row(self, i):
        """row i from the right side wall through the face to the left side wall (head-on x increasing)"""
        n = len(self.ring)
        right = list(self.cols[i])            # side wall (k = 0) → face
        left = list(reversed(self.cols[n - 1 - i]))
        mid = self.rows[i][1:-1] if len(self.rows[i]) > 1 else []
        return right + mid + left

    def row_u(self, pts):
        """arc length along a row, 0 at its centre line (x = 0)"""
        p = np.array(pts)
        seg = np.linalg.norm(np.diff(p, axis=0), axis=1)
        s = np.concatenate([[0.0], np.cumsum(seg)])
        s0 = np.interp(0.0, p[:, 0], s)
        return s - s0


# ---------------------------------------------------------------- mesh helpers


class UVPart(K.Part):
    """a Part whose faces carry texture coordinates; marks edges sharper than `sharp` degrees when it is built"""

    def __init__(self, name, sharp=35.0):
        super().__init__(name)
        self.uv = self.bm.loops.layers.uv.new('UVMap')
        self.sharp = math.radians(sharp)

    def face_uv(self, pts, mat, uvs, smooth=True, out=None):
        """a face from game-frame points with their (u, v); flipped to face `out` (a game-frame vector) if given"""
        if out is not None:
            a, b, c = (Vector(p) for p in pts[:3])
            nrm = (b - a).cross(c - a)
            if len(pts) > 3 and nrm.length < 1e-12:
                nrm = (c - a).cross(Vector(pts[3]) - a)
            if nrm.dot(Vector(out)) < 0:
                pts, uvs = list(reversed(pts)), list(reversed(uvs))
        vs = [self.bm.verts.new(K.B(*p)) for p in pts]
        f = self.bm.faces.new(vs)
        f.material_index = self.slot(mat)
        f.smooth = smooth
        for loop, uv in zip(f.loops, uvs):
            loop[self.uv].uv = uv
        return f

    def build(self, parent, mats):
        bmesh.ops.remove_doubles(self.bm, verts=self.bm.verts, dist=1e-5)
        self.bm.normal_update()
        for e in self.bm.edges:
            if len(e.link_faces) == 2:
                f1, f2 = e.link_faces
                if f1.normal.angle(f2.normal, 0.0) > self.sharp or f1.material_index != f2.material_index and not (f1.smooth and f2.smooth):
                    e.smooth = False
        return super().build(parent, mats)


def _quad_out(p, centre_z):
    """outward hint for a shell face: away from the car's axis"""
    c = Vector(p)
    return c - Vector((0.0, 2.0, max(-7.6, min(7.6, centre_z))))


# ---------------------------------------------------------------- the shell


class Body:
    """one car's shell; kind 'cab' (cab at +z) or 'middle'"""

    # texture windows: what the side and face images cover (u0, u1, v0, v1 in metres)
    SIDE_UV = (-8.85, 8.85, 0.95, 3.34)
    FACE_UV = (-1.85, 1.85, 0.95, 3.55)

    def __init__(self, kind):
        self.kind = kind
        self.cab = kind == 'cab'
        self.ring = ring()
        self.n = len(self.ring)
        self.half = (self.n + 1) // 2
        self.nose = Nose() if self.cab else None
        self.doors = CAB_DOORS if self.cab else DOORS

    # uv helpers
    def side_uv(self, z, y):
        u0, u1, v0, v1 = self.SIDE_UV
        return ((z - u0) / (u1 - u0), (y - v0) / (v1 - v0))

    def face_uv(self, u, y):
        u0, u1, v0, v1 = self.FACE_UV
        return ((u - u0) / (u1 - u0), (y - v0) / (v1 - v0))

    def zone(self, y, ny, z):
        """plain paint by height and slope where no texture is used"""
        if ny > 0.55 and y > GUTTER - 0.01 and not (self.cab and z > ROOF_GREY_END):
            return 'kb_roof'
        return 'kb_red'

    def textured(self, y, nx):
        """faces carrying the side texture: the vertical side and its bottom tuck"""
        u0, u1, v0, v1 = self.SIDE_UV
        return abs(nx) > 0.6 and y < v1 - 0.02

    def stations(self):
        zs = {-(END - END_R), (END - END_R) if not self.cab else CAB_JOIN}
        for zd in self.doors:
            zs.add(zd - DOOR_W / 2)
            zs.add(zd + DOOR_W / 2)
        # break long spans so the faces stay modest (helps the renderer's shading, not the shape)
        out = sorted(zs)
        fine = []
        for a, b in zip(out[:-1], out[1:]):
            k = max(1, int(math.ceil((b - a) / 1.5)))
            fine += [a + (b - a) * i / k for i in range(k)]
        return fine + [out[-1]]

    def in_door(self, za, zb, ya, yb, side):
        if ya < SILL - 1e-6 or yb > DOOR_TOP + 1e-6:
            return False
        for zd in self.doors:
            if za >= zd - DOOR_W / 2 - 1e-6 and zb <= zd + DOOR_W / 2 + 1e-6:
                return True
        return False

    def build(self, part):
        ring = self.ring
        zs = self.stations()
        # sides and roof
        for za, zb in zip(zs[:-1], zs[1:]):
            for i in range(self.n - 1):
                (xa, ya, nxa, nya), (xb, yb, nxb, nyb) = ring[i], ring[i + 1]
                if abs(xa - xb) < 1e-9 and abs(xa) > HW - 1e-6 and self.in_door(za, zb, min(ya, yb), max(ya, yb), xa):
                    continue
                pts = [(xa, ya, za), (xb, yb, za), (xb, yb, zb), (xa, ya, zb)]
                cy = (ya + yb) / 2
                nx = (nxa + nxb) / 2
                ny = (nya + nyb) / 2
                out = _quad_out((0.5 * (xa + xb), cy, 0.5 * (za + zb)), 0.5 * (za + zb))
                if self.textured(cy, nx):
                    part.face_uv(pts, 'kb_side_' + self.kind, [self.side_uv(p[2], p[1]) for p in pts], out=out)
                else:
                    part.face_uv(pts, self.zone(cy, ny, 0.5 * (za + zb)), [(0, 0)] * 4, out=out)
        # underside
        part.face_uv([(-HW + 0.034, BOTTOM, zs[0]), (HW - 0.034, BOTTOM, zs[0]), (HW - 0.034, BOTTOM, zs[-1]), (-HW + 0.034, BOTTOM, zs[-1])],
                     'kb_under', [(0, 0)] * 4, smooth=False, out=(0, -1, 0))
        self.gangway_end(part, -END, -1)
        bellows(part, -END, -1)
        if self.cab:
            self.cab_end(part)
        else:
            self.gangway_end(part, END, 1)
            bellows(part, END, 1)
        for zd in self.doors:
            for s in (1, -1):
                self.door(part, zd, s)

    def gangway_end(self, part, z_end, sign):
        """a gangway end: the sides round into a flat end wall"""
        steps = 3
        cols = []
        for x, y, nx, ny in self.ring:
            col = []
            for k in range(steps + 1):
                phi = (math.pi / 2) * k / steps
                d = END_R * (1 - math.cos(phi))
                col.append((x - nx * d, y - ny * d, z_end - sign * END_R * (1 - math.sin(phi))))
            cols.append(col)
        for i in range(self.n - 1):
            for k in range(steps):
                pts = [cols[i][k], cols[i + 1][k], cols[i + 1][k + 1], cols[i][k + 1]]
                cy = sum(p[1] for p in pts) / 4
                nx = (self.ring[i][2] + self.ring[i + 1][2]) / 2
                ny = (self.ring[i][3] + self.ring[i + 1][3]) / 2
                c = Vector([sum(p[j] for p in pts) / 4 for j in range(3)])
                out = c - Vector((0.0, 2.0, z_end - sign * 1.0))
                if self.textured(cy, nx) and k == 0:
                    part.face_uv(pts, 'kb_side_' + self.kind, [self.side_uv(p[2], p[1]) for p in pts], out=out)
                else:
                    part.face_uv(pts, self.zone(cy, ny, z_end), [(0, 0)] * 4, out=out)
        # the end wall: rows across between pairs
        for i in range(self.half - 1):
            a, b = cols[i][-1], cols[self.n - 1 - i][-1]
            c, d = cols[i + 1][-1], cols[self.n - 2 - i][-1]
            pts = [a, b, d, c] if c != d else [a, b, c]
            part.face_uv(pts, 'kb_red', [(0, 0)] * len(pts), smooth=False, out=(0, 0, sign))
        # the underside under the rounding
        b0, b1 = cols[0], cols[self.n - 1]
        for k in range(steps):
            pts = [b0[k], b1[k], b1[k + 1], b0[k + 1]]
            part.face_uv(pts, 'kb_under', [(0, 0)] * 4, smooth=False, out=(0, -1, 0))

    def cab_end(self, part):
        nose = self.nose
        ring = self.ring
        n = self.n
        # side wall from the sweep's end to where each column starts
        for i in range(n - 1):
            (xa, ya, nxa, nya), (xb, yb, nxb, nyb) = ring[i], ring[i + 1]
            a, b = nose.cols[i][0], nose.cols[i + 1][0]
            pts = [(xa, ya, CAB_JOIN), (xb, yb, CAB_JOIN), b, a]
            cy = (ya + yb) / 2
            nx = (nxa + nxb) / 2
            ny = (nya + nyb) / 2
            out = _quad_out((0.5 * (xa + xb), cy, CAB_JOIN + 0.3), CAB_JOIN + 0.3)
            if self.textured(cy, nx):
                part.face_uv(pts, 'kb_side_cab', [self.side_uv(p[2], p[1]) for p in pts], out=out)
            else:
                part.face_uv(pts, self.zone(cy, ny, CAB_JOIN + 0.3), [(0, 0)] * 4, out=out)
        # texture coordinates of the nose: u along each row (pairs share a row), v = height
        u_col = [None] * n
        u_row = [None] * self.half
        for i in range(self.half):
            pts = nose.full_row(i)
            u = nose.row_u(pts)
            k = nose.steps + 1
            u_col[i] = list(u[:k])                       # right column, side wall → face
            if i != n - 1 - i:
                u_col[n - 1 - i] = list(reversed(u[len(u) - k:]))
            mid = nose.rows[i]
            if len(mid) > 1:
                u_row[i] = [u[k - 1]] + list(u[k:len(u) - k]) + [u[len(u) - k]]
            else:
                u_row[i] = [0.0]
        self.u_col, self.u_row = u_col, u_row

        def mat_for(pts, ny):
            cy = sum(p[1] for p in pts) / len(pts)
            if cy < self.FACE_UV[3] - 0.06:
                return 'kb_face'
            return 'kb_red'

        out_c = Vector((0.0, 2.0, 7.0))
        # the columns' quarter-rounds
        for i in range(n - 1):
            for k in range(nose.steps):
                pts = [nose.cols[i][k], nose.cols[i + 1][k], nose.cols[i + 1][k + 1], nose.cols[i][k + 1]]
                uvs = [(u_col[i][k], pts[0][1]), (u_col[i + 1][k], pts[1][1]), (u_col[i + 1][k + 1], pts[2][1]), (u_col[i][k + 1], pts[3][1])]
                m = mat_for(pts, 0)
                c = Vector([sum(p[j] for p in pts) / 4 for j in range(3)])
                part.face_uv(pts, m, [self.face_uv(u, v) for u, v in uvs] if m == 'kb_face' else [(0, 0)] * 4, out=c - out_c)
        # the face
        for i in range(self.half - 1):
            ra, rb = nose.rows[i], nose.rows[i + 1]
            ua, ub = u_row[i], u_row[i + 1]
            for k in range(len(ra) - 1):
                if len(rb) > 1:
                    pts = [ra[k], ra[k + 1], rb[k + 1], rb[k]]
                    uvs = [(ua[k], ra[k][1]), (ua[k + 1], ra[k + 1][1]), (ub[k + 1], rb[k + 1][1]), (ub[k], rb[k][1])]
                else:
                    pts = [ra[k], ra[k + 1], rb[0]]
                    uvs = [(ua[k], ra[k][1]), (ua[k + 1], ra[k + 1][1]), (0.0, rb[0][1])]
                m = mat_for(pts, 0)
                part.face_uv(pts, m, [self.face_uv(u, v) for u, v in uvs] if m == 'kb_face' else [(0, 0)] * len(pts), out=(0, 0.3, 1))
        # underside of the nose: a fan under the bottom row
        bottom = nose.full_row(0)
        c = (0.0, BOTTOM, CAB_JOIN)
        prev = (ring[0][0], BOTTOM, CAB_JOIN)
        for p in bottom + [(ring[n - 1][0], BOTTOM, CAB_JOIN)]:
            q = (p[0], BOTTOM, p[2])
            if Vector(q) != Vector(prev):
                part.face_uv([c, prev, q], 'kb_under', [(0, 0)] * 3, smooth=False, out=(0, -1, 0))
            prev = q

    def door(self, part, zd, side):
        """a passenger door opening on side +1 (left) or −1: jambs into the side, the leaves set back"""
        x0 = side * HW
        x1 = side * (HW - DOOR_DEPTH)
        za, zb = zd - DOOR_W / 2, zd + DOOR_W / 2
        ys = [y for x, y, nx, ny in self.ring[self.half - 1:] if abs(x - HW) < 1e-9 and SILL - 1e-6 <= y <= DOOR_TOP + 1e-6]
        ys = sorted(ys)
        # jambs at both ends (facing into the opening)
        for zj, facing in ((za, 1), (zb, -1)):
            for ya, yb in zip(ys[:-1], ys[1:]):
                part.face_uv([(x0, ya, zj), (x0, yb, zj), (x1, yb, zj), (x1, ya, zj)], 'kb_red', [(0, 0)] * 4, smooth=False, out=(0, 0, facing))
        # head and sill
        part.face_uv([(x0, DOOR_TOP, za), (x0, DOOR_TOP, zb), (x1, DOOR_TOP, zb), (x1, DOOR_TOP, za)], 'kb_red', [(0, 0)] * 4, smooth=False, out=(0, -1, 0))
        part.face_uv([(x0, SILL, za), (x0, SILL, zb), (x1, SILL, zb), (x1, SILL, za)], 'kb_sill', [(0, 0)] * 4, smooth=False, out=(0, 1, 0))
        # the leaves, split at the band's lower edge so the texture's colour change has an edge to sit on
        yl = [SILL, BAND[0], DOOR_TOP]
        zl = [za, zd, zb]
        for ya, yb in zip(yl[:-1], yl[1:]):
            for z0, z1 in zip(zl[:-1], zl[1:]):
                pts = [(x1, ya, z0), (x1, yb, z0), (x1, yb, z1), (x1, ya, z1)]
                part.face_uv(pts, 'kb_side_' + self.kind, [self.side_uv(p[2], p[1]) for p in pts], smooth=False, out=(side, 0, 0))


def bellows(part, z_end, sign, half_gap=0.25, w=1.12, y0=1.12, y1=3.12, folds=4, depth=0.035):
    """the car's half of the gangway bellows: a folded rubber box from the end wall to the middle of the gap"""
    # frame plate on the end wall
    zf = z_end + sign * 0.012
    part.box('kb_frame', -w / 2 - 0.05, w / 2 + 0.05, y0 - 0.05, y1 + 0.05, min(z_end, zf), max(z_end, zf))
    # the folds: rings stepping out and in
    n = folds * 2
    zs = [z_end + sign * (0.012 + (half_gap - 0.012) * k / n) for k in range(n + 1)]
    for k in range(n):
        za, zb = zs[k], zs[k + 1]
        ea = depth if k % 2 else 0.0
        eb = depth if (k + 1) % 2 else 0.0
        ra = [(-w / 2 - ea, y0 - ea), (w / 2 + ea, y0 - ea), (w / 2 + ea, y1 + ea), (-w / 2 - ea, y1 + ea)]
        rb = [(-w / 2 - eb, y0 - eb), (w / 2 + eb, y0 - eb), (w / 2 + eb, y1 + eb), (-w / 2 - eb, y1 + eb)]
        for i in range(4):
            j = (i + 1) % 4
            pts = [(ra[i][0], ra[i][1], za), (ra[j][0], ra[j][1], za), (rb[j][0], rb[j][1], zb), (rb[i][0], rb[i][1], zb)]
            c = Vector([sum(p[q] for p in pts) / 4 for q in range(3)])
            part.face_uv(pts, 'kb_bellows', [(0, 0)] * 4, smooth=False, out=(c.x, c.y - (y0 + y1) / 2, 0))
    # the face plate where the two halves meet
    zl = zs[-1]
    part.box('kb_frame', -w / 2 - depth, w / 2 + depth, y0 - depth, y1 + depth, min(zl, zl - sign * 0.02), max(zl, zl - sign * 0.02))


# ---------------------------------------------------------------- painting (numpy, sRGB floats; row 0 = bottom)


def _sd_round_rect(px, py, cx, cy, w, h, r):
    """signed distance to a rounded rectangle (negative inside)"""
    qx = np.abs(px - cx) - (w / 2 - r)
    qy = np.abs(py - cy) - (h / 2 - r)
    ox = np.maximum(qx, 0)
    oy = np.maximum(qy, 0)
    return np.sqrt(ox * ox + oy * oy) + np.minimum(np.maximum(qx, qy), 0) - r


def _pixels(img):
    """a Blender image as an (h, w, 4) array, row 0 at the bottom"""
    return np.array(img.pixels[:], np.float32).reshape(img.size[1], img.size[0], 4)


def _sample(img, X, V, x0, x1, y0, y1):
    """nearest texel of `img` stretched over [x0, x1] × [y0, y1] at each (X, V); and where that lies inside"""
    arr = _pixels(img) if not isinstance(img, np.ndarray) else img
    bh, bw = arr.shape[:2]
    inside = ((X >= x0) & (X < x1) & (V >= y0) & (V < y1)).astype(np.float32)
    ix = np.clip(((X - x0) / (x1 - x0) * bw).astype(int), 0, bw - 1)
    iy = np.clip(((V - y0) / (y1 - y0) * bh).astype(int), 0, bh - 1)
    return arr[iy, ix], inside


class Canvas:
    def __init__(self, uv_box, w, h):
        self.u0, self.u1, self.v0, self.v1 = uv_box
        self.w, self.h = w, h
        u = self.u0 + (np.arange(w) + 0.5) / w * (self.u1 - self.u0)
        v = self.v0 + (np.arange(h) + 0.5) / h * (self.v1 - self.v0)
        self.U, self.V = np.meshgrid(u, v)
        self.px = (self.u1 - self.u0) / w           # metres per texel
        self.rgb = np.zeros((h, w, 3), np.float32)
        self.rough = np.full((h, w), 0.3, np.float32)

    def cover(self, sd, aa=None):
        return np.clip(0.5 - sd / (aa if aa is not None else self.px), 0.0, 1.0)

    def paint(self, alpha, colour, rough=None):
        a = alpha[..., None]
        self.rgb = self.rgb * (1 - a) + np.array(colour, np.float32) * a
        if rough is not None:
            self.rough = self.rough * (1 - alpha) + rough * alpha

    def fill(self, colour, rough):
        self.rgb[:] = colour
        self.rough[:] = rough

    def image(self, name, path):
        rgba = np.ones((self.h, self.w, 4), np.float32)
        rgba[..., :3] = np.clip(self.rgb, 0, 1)
        img = bpy.data.images.new(name, self.w, self.h, alpha=False)
        img.pixels.foreach_set(rgba.ravel())
        img.filepath_raw = path
        img.file_format = 'PNG'
        img.save()
        mr = np.ones((self.h, self.w, 4), np.float32)
        mr[..., 0] = 1.0
        mr[..., 1] = np.clip(self.rough, 0, 1)
        mr[..., 2] = 0.0
        img2 = bpy.data.images.new(name + '_mr', self.w, self.h, alpha=False)
        img2.colorspace_settings.name = 'Non-Color'
        img2.pixels.foreach_set(mr.ravel())
        img2.filepath_raw = path.replace('.png', '_mr.png')
        img2.file_format = 'PNG'
        img2.save()
        return img, img2


def paint_side(kind, path, w=4096, h=552):
    """the side texture (u = z, v = y), shared by both sides and the door leaves"""
    cv = Canvas(Body.SIDE_UV, w, h)
    U, V = cv.U, cv.V
    cv.fill(RED, 0.28)
    cab = kind == 'cab'
    doors = CAB_DOORS if cab else DOORS
    z_band0 = -END + 0.06
    z_band1 = CREW_DOOR[0] if cab else END - 0.06
    band = (V >= BAND[0]) & (V < BAND[1]) & (U > z_band0) & (U < z_band1)
    sd = np.maximum(np.maximum(BAND[0] - V, V - BAND[1]), np.maximum(z_band0 - U, U - z_band1))
    cv.paint(cv.cover(sd), CREAM, 0.30)

    def window(z0, z1, y0=WIN[0], y1=WIN[1], r=0.045):
        cz, cy, ww, hh = (z0 + z1) / 2, (y0 + y1) / 2, z1 - z0, y1 - y0
        sd = _sd_round_rect(U, V, cz, cy, ww, hh, r)
        cv.paint(cv.cover(sd), GASKET, 0.45)
        cv.paint(cv.cover(sd + 0.016), SIDE_GLASS, 0.05)

    # windows between the doors: 2,325 mm, two panes and a 75 mm pillar
    for a, b in zip(doors[:-1], doors[1:]):
        c = (a + b) / 2
        window(c - 1.1625, c - 0.0375)
        window(c + 0.0375, c + 1.1625)
    # the car-end windows (1,455 mm), centred between the end door's pocket and the end
    w_end = 1.455
    rear = -END + 0.62
    window(rear, rear + w_end)
    if not cab:
        window(END - 0.62 - w_end, END - 0.62)
    if cab:
        # small window behind the crew door
        z0, z1 = SMALL_WINDOW
        window(z0, z1, r=0.03)
        # the crew door's outline
        cz0, cz1, cy0, cy1 = CREW_DOOR
        sd = np.abs(_sd_round_rect(U, V, (cz0 + cz1) / 2, (cy0 + cy1) / 2, cz1 - cz0, cy1 - cy0, 0.03)) - 0.005
        cv.paint(cv.cover(sd), GASKET, 0.6)
    # door leaves: windows, the centre seam, the rubber at the jambs
    for zd in doors:
        for s in (-1, 1):
            zc = zd + s * DOOR_W / 4
            sd = _sd_round_rect(U, V, zc, (1.94 + 2.83) / 2, 0.30, 2.83 - 1.94, 0.05)
            cv.paint(cv.cover(sd), GASKET, 0.45)
            cv.paint(cv.cover(sd + 0.014), SIDE_GLASS, 0.05)
        for zl, wl in ((zd, 0.010), (zd - DOOR_W / 2 + 0.006, 0.012), (zd + DOOR_W / 2 - 0.006, 0.012)):
            sd = np.maximum(np.abs(U - zl) - wl / 2, np.maximum(SILL - V, V - DOOR_TOP))
            cv.paint(cv.cover(sd), GASKET, 0.6)
    return cv


def _cab_interior(V):
    """
    the cab seen through the windscreen (photo 02: the display housing and the ceiling dark at the top, the partition
    behind the driver lighter, the desk dark below): a dim colour by height, under the glass's reflection
    """
    top = np.array((0.05, 0.053, 0.058), np.float32)
    wall = np.array((0.42, 0.44, 0.46), np.float32)
    desk = np.array((0.09, 0.093, 0.10), np.float32)
    def ss(e0, e1):
        t = np.clip((V - e0) / (e1 - e0), 0, 1)
        return (t * t * (3 - 2 * t))[..., None]
    a = ss(2.32, 2.45)            # desk → partition
    b = ss(3.02, 3.12)            # partition → ceiling
    lift = (1.0 - 0.25 * np.clip((V - 2.45) / 0.6, 0, 1))[..., None]   # lighter low on the partition
    return (desk * (1 - a) + wall * lift * a) * (1 - b) + top * b


def paint_face(body, path, band_img=None, lamp_imgs=None, w=2048, h=1440):
    """the cab face texture (u = arc length from the centre line along each row, v = y)"""
    nose = body.nose
    cv = Canvas(Body.FACE_UV, w, h)
    U, V = cv.U, cv.V
    # head-on x at each texel: interpolate each row's u → x, then between rows by height
    rows_y, rows_u, rows_x = [], [], []
    for i in range(body.half):
        if len(nose.rows[i]) < 2:
            continue
        pts = nose.full_row(i)
        rows_y.append(nose.rows[i][0][1])
        rows_u.append(nose.row_u(pts))
        rows_x.append(np.array([p[0] for p in pts]))
    rows_y = np.array(rows_y)
    X = np.zeros_like(U)
    Umax = np.zeros_like(U)
    for j in range(h):
        y = V[j, 0]
        i = int(np.clip(np.searchsorted(rows_y, y) - 1, 0, len(rows_y) - 2))
        t = float(np.clip((y - rows_y[i]) / max(rows_y[i + 1] - rows_y[i], 1e-6), 0, 1))
        xa = np.interp(U[j], rows_u[i], rows_x[i])
        xb = np.interp(U[j], rows_u[i + 1], rows_x[i + 1])
        X[j] = xa + (xb - xa) * t
        Umax[j] = rows_u[i][-1] + (rows_u[i + 1][-1] - rows_u[i][-1]) * t
    # how much head-on x changes per texel (anti-aliasing width for shapes drawn in x)
    dxdu = np.abs(np.gradient(X, axis=1)) / cv.px
    aa_x = np.maximum(cv.px * dxdu, 1e-4)
    cv.fill(RED, 0.28)
    # wiper cover (cream): square top corners, rounded bottom ones, ends just round the corners
    yc0, yc1 = 1.67, 2.05
    sd_r = _sd_round_rect(X, V, 0.0, (yc0 + yc1) / 2, 2 * 1.400, yc1 - yc0, 0.08)
    sd_top = np.maximum(np.abs(X) - 1.400, np.maximum((yc0 + yc1) / 2 - V, V - yc1))
    cv.paint(cv.cover(np.minimum(sd_r, sd_top), aa_x), CREAM, 0.30)
    # the emergency door's outline below the glass, through the cover and the red
    door_x = (-1.285, -0.455)
    sd_door = _sd_round_rect(X, V, sum(door_x) / 2, (1.20 + 2.30) / 2, door_x[1] - door_x[0], 2.30 - 1.20, 0.05)
    line = np.abs(sd_door) - 0.004
    cv.paint(cv.cover(line, aa_x) * (V < 2.06), SEAM, 0.5)
    # the cover's joint above the door's edge
    sd = np.maximum(np.abs(X + 0.455) - 0.003, np.maximum(yc0 - V, V - yc1))
    cv.paint(cv.cover(sd, aa_x), SEAM, 0.5)
    # black glass area: frame, the door's glass, the pillar, the main windscreen
    sd = _sd_round_rect(X, V, 0.0, (2.05 + 3.44) / 2, 2 * 1.285, 3.44 - 2.05, 0.11)
    sd = np.maximum(sd, 2.05 - V)                    # straight along the cover's top
    cv.paint(cv.cover(sd, aa_x), FRAME, 0.5)
    for x0, x1 in ((-1.255, -0.500), (-0.405, 1.255)):
        sdg = _sd_round_rect(X, V, (x0 + x1) / 2, (2.075 + 3.41) / 2, x1 - x0, 3.41 - 2.075, 0.085)
        cv.paint(cv.cover(sdg, aa_x), _cab_interior(V), 0.04)
    # the notch in the body's lower edge over the coupler
    sd = _sd_round_rect(X, V, 0.0, BOTTOM + 0.06, 0.68, 0.24, 0.04)
    cv.paint(cv.cover(sd, aa_x), (0.02, 0.02, 0.022), 0.8)
    # lamp housings at the waist (express lamp outside, tail lamp inside), from the signage textures
    for s_, img in ((-1, lamp_imgs[0] if lamp_imgs else None), (1, lamp_imgs[1] if lamp_imgs else None)):
        cx, cy, w_, h_ = s_ * 0.905, 1.39, 0.45, 0.17
        sd = _sd_round_rect(X, V, cx, cy, w_, h_, 0.07)
        cover = cv.cover(sd, aa_x)
        if img is None:
            cv.paint(cover, (0.03, 0.03, 0.035), 0.25)
            continue
        samp, inside = _sample(img, X, V, cx - w_ / 2, cx + w_ / 2, cy - h_ / 2, cy + h_ / 2)
        a = (cover * inside)[..., None]
        cv.rgb = cv.rgb * (1 - a) + samp[..., :3] * a
        cv.rough = cv.rough * (1 - a[..., 0]) + 0.12 * a[..., 0]
    # the markings on the wiper cover (from the signage textures)
    if band_img is not None:
        samp, inside = _sample(band_img, X, V, -1.45, 1.45, 1.66, 2.06)
        dark = (samp[..., :3].mean(axis=2) < 0.35) & (samp[..., 3] > 0.5) & (inside > 0) & (X > 0)
        cv.paint(dark.astype(np.float32), (0.04, 0.04, 0.045), 0.4)
    return cv, X


# ---------------------------------------------------------------- materials


def textured_material(name, img, mr):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    p = nt.nodes.get('Principled BSDF')
    t = nt.nodes.new('ShaderNodeTexImage')
    t.image = img
    t.interpolation = 'Linear'
    nt.links.new(t.outputs['Color'], p.inputs['Base Color'])
    t2 = nt.nodes.new('ShaderNodeTexImage')
    t2.image = mr
    t2.interpolation = 'Linear'
    sep = nt.nodes.new('ShaderNodeSeparateColor')
    nt.links.new(t2.outputs['Color'], sep.inputs['Color'])
    nt.links.new(sep.outputs['Green'], p.inputs['Roughness'])
    nt.links.new(sep.outputs['Blue'], p.inputs['Metallic'])
    p.inputs['Specular IOR Level'].default_value = 0.5
    return m


SIGNS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'textures', 'keikyu1000')

# front LED displays (behind the windscreen, measured on photo 02): name, centre x, width, height
LEDS = (('led_runno', -0.725, 0.35, 0.205), ('led_type', -0.185, 0.29, 0.205), ('led_dest', 0.505, 0.67, 0.21))
LED_Y = 3.20
HEADLAMP = (1.085, 3.16, 0.050)      # |x|, y, radius of the reflector
HEADLAMP_UNIT = (0.21, 0.14, 0.022)  # the lamp unit round it: width, height, corner radius (photo 02)
NUMBER_BOX = (-0.82, -0.42, 1.70, 1.89)   # where the car number sits on the cover (x0, x1, y0, y1)
# the numbers' outlines (cab_numbers.json) are drawn for x −0.80…−0.445; photo 02 puts the "1" ≈ 4 cm clear of the
# emergency door's edge (our −0.455), so they move left by this much
NUMBER_SHIFT = -0.045


def _load(name):
    path = os.path.join(SIGNS, name)
    return bpy.data.images.load(path) if os.path.exists(path) else None


def _atlas(name, pieces, path):
    """pack images side by side into one texture; returns the image and {key: (u0, v0, u1, v1)}"""
    arrs = [(k, _pixels(img) if not isinstance(img, np.ndarray) else img) for k, img in pieces]
    w = sum(a.shape[1] for _, a in arrs) + 8 * len(arrs)
    h = max(a.shape[0] for _, a in arrs)
    out = np.zeros((h, w, 4), np.float32)
    out[..., 3] = 1
    boxes = {}
    x = 0
    for k, a in arrs:
        ah, aw = a.shape[:2]
        out[:ah, x:x + aw, :] = a
        boxes[k] = ((x + 0.5) / w, 0.5 / h, (x + aw - 0.5) / w, (ah - 0.5) / h)
        x += aw + 8
    img = bpy.data.images.new(name, w, h, alpha=False)
    img.pixels.foreach_set(out.ravel())
    img.filepath_raw = path
    img.file_format = 'PNG'
    img.save()
    return img, boxes


def add_materials(m, tex_dir, kinds=('cab', 'middle')):
    """plain paints plus the painted textures (written to tex_dir) for the given car kinds"""
    os.makedirs(tex_dir, exist_ok=True)
    red_hex = '#%02x%02x%02x' % tuple(int(round(c * 255)) for c in RED)
    m.add('kb_red', red_hex, roughness=0.28)
    m.add('kb_roof', ROOF_GREY, roughness=0.75)
    m.add('kb_under', '#2a2a2c', roughness=0.85)
    m.add('kb_sill', '#b9bcbf', metallic=0.8, roughness=0.35)
    m.add('kb_chrome', '#d6d8db', metallic=0.95, roughness=0.18)
    m.add('kb_lamp', '#d9dad6', metallic=0.6, roughness=0.15)
    m.add('kb_bellows', '#2c2c2e', roughness=0.8)
    m.add('kb_sidelamp', '#a4592a', roughness=0.2)
    m.add('kb_frame', '#3a3a3c', metallic=0.3, roughness=0.5)
    m.add('kb_hinge', '#5a5650', metallic=0.4, roughness=0.6)
    for kind in kinds:
        cv = paint_side(kind, None)
        img, mr = cv.image(f'kb_side_{kind}', os.path.join(tex_dir, f'side_{kind}.png'))
        m.mats[f'kb_side_{kind}'] = textured_material(f'kb_side_{kind}', img, mr)
    if 'cab' not in kinds:
        return {}
    band = _load('cab_band_001.png')
    lamps = (_load('lamp_unit_L.png'), _load('lamp_unit_R.png'))
    cv, _ = paint_face(Body('cab'), None, band, lamps if all(lamps) else None)
    img, mr = cv.image('kb_face', os.path.join(tex_dir, 'face.png'))
    m.mats['kb_face'] = textured_material('kb_face', img, mr)
    cv = paint_skirt()
    img, mr = cv.image('kb_skirt', os.path.join(tex_dir, 'skirt.png'))
    m.mats['kb_skirt'] = textured_material('kb_skirt', img, mr)
    # LED displays and the car numbers: one emissive atlas, one plain atlas
    side = 'led_side_wide' if os.path.exists(os.path.join(SIGNS, 'led_side_wide.png')) else 'led_side'
    pieces = [(k, _load(k + '.png')) for k, *_ in LEDS] + [(side, _load(side + '.png'))]
    boxes = {}
    if all(img is not None for _, img in pieces):
        img, b = _atlas('kb_led', pieces, os.path.join(tex_dir, 'led.png'))
        mat = textured_material('kb_led', img, img)
        p = mat.node_tree.nodes.get('Principled BSDF')
        tex = [n for n in mat.node_tree.nodes if n.type == 'TEX_IMAGE'][0]
        mat.node_tree.links.new(tex.outputs['Color'], p.inputs['Emission Color'])
        p.inputs['Emission Strength'].default_value = 1.0
        for n in [n for n in mat.node_tree.nodes if n.type == 'SEPARATE_COLOR']:
            mat.node_tree.nodes.remove(n)
        p.inputs['Roughness'].default_value = 0.2
        p.inputs['Metallic'].default_value = 0.0
        m.mats['kb_led'] = mat
        boxes.update(b)
    m.add('kb_letter', '#141416', roughness=0.35)
    if os.path.exists(os.path.join(SIGNS, 'cab_numbers.json')):
        return boxes
    nums = []
    for k in ('001', '008'):
        im = _load(f'cab_band_{k}.png')
        if im is None:
            continue
        a = _pixels(im)
        bh, bw = a.shape[:2]
        x0, x1, y0, y1 = NUMBER_BOX
        c0, c1 = int((x0 + 1.45) / 2.9 * bw), int((x1 + 1.45) / 2.9 * bw)
        r0, r1 = int((y0 - 1.66) / 0.40 * bh), int((y1 - 1.66) / 0.40 * bh)
        crop = a[r0:r1, c0:c1].copy()
        dark = (crop[..., 3:4] > 0.5) & (crop[..., :3].mean(axis=2, keepdims=True) < 0.35)
        crop[..., :3] = np.where(dark, np.array((0.04, 0.04, 0.045), np.float32), np.array(CREAM, np.float32))
        crop[..., 3] = 1
        nums.append(('num_' + k, crop))
    if nums:
        img, b = _atlas('kb_number', nums, os.path.join(tex_dir, 'number.png'))
        mr = bpy.data.images.new('kb_number_mr', 4, 4, alpha=False)
        mr.colorspace_settings.name = 'Non-Color'
        mr.pixels.foreach_set(np.tile(np.array([1, 0.3, 0, 1], np.float32), 16))
        m.mats['kb_number'] = textured_material('kb_number', img, mr)
        boxes.update(b)
    return boxes


def build(part, kind):
    """the shell of one car into a UVPart"""
    Body(kind).build(part)


# ---------------------------------------------------------------- the cab's fittings


def _on_face(x, y, lift):
    """a point on the cab face (flat part), `lift` m in front of it"""
    return (x, y, face_z(x, y) + lift)


def _quad_on_face(part, mat, x0, x1, y0, y1, uv, lift, nx=4, ny=2):
    """a rectangle laid on the face (it follows the bulge and rake), textured with uv box (u0, v0, u1, v1)"""
    u0, v0, u1, v1 = uv
    for j in range(ny):
        for i in range(nx):
            xa, xb = x0 + (x1 - x0) * i / nx, x0 + (x1 - x0) * (i + 1) / nx
            ya, yb = y0 + (y1 - y0) * j / ny, y0 + (y1 - y0) * (j + 1) / ny
            pts = [_on_face(xa, ya, lift), _on_face(xb, ya, lift), _on_face(xb, yb, lift), _on_face(xa, yb, lift)]
            # the viewer's left (−x) is the image's left
            uvs = [(u0 + (u1 - u0) * (xa - x0) / (x1 - x0), v0 + (v1 - v0) * (ya - y0) / (y1 - y0)),
                   (u0 + (u1 - u0) * (xb - x0) / (x1 - x0), v0 + (v1 - v0) * (ya - y0) / (y1 - y0)),
                   (u0 + (u1 - u0) * (xb - x0) / (x1 - x0), v0 + (v1 - v0) * (yb - y0) / (y1 - y0)),
                   (u0 + (u1 - u0) * (xa - x0) / (x1 - x0), v0 + (v1 - v0) * (yb - y0) / (y1 - y0))]
            part.face_uv(pts, mat, uvs, out=(0, 0.2, 1))


def cab_fittings(part, boxes, number='001'):
    """displays and head lamps behind the windscreen, the car number on the wiper cover"""
    for key, cx, w, h in LEDS:
        if key in boxes:
            _quad_on_face(part, 'kb_led', cx - w / 2, cx + w / 2, LED_Y - h / 2, LED_Y + h / 2, boxes[key], 0.004)
    if not _number_geometry(part, number) and 'num_' + number in boxes:
        x0, x1, y0, y1 = NUMBER_BOX
        _quad_on_face(part, 'kb_number', x0, x1, y0, y1, boxes['num_' + number], 0.0025, nx=2, ny=1)
    # head lamps (photo 02): a light grey lamp unit 0.21 × 0.14 m behind the glass, a chrome reflector and the lamp
    hx, hy, r = HEADLAMP
    for s in (-1, 1):
        cx = s * hx
        _round_rect_on_face(part, 'kb_sill', cx, hy, *HEADLAMP_UNIT, 0.005)
        for r0, r1, mat, lift in ((r * 0.84, r, 'kb_chrome', 0.007), (0.0, r * 0.84, 'kb_lamp', 0.009)):
            seg = 24
            for k in range(seg):
                a0, a1 = 2 * math.pi * k / seg, 2 * math.pi * (k + 1) / seg
                pts = [_on_face(cx + r1 * math.cos(a0), hy + r1 * math.sin(a0), lift),
                       _on_face(cx + r1 * math.cos(a1), hy + r1 * math.sin(a1), lift)]
                if r0 > 0:
                    pts += [_on_face(cx + r0 * math.cos(a1), hy + r0 * math.sin(a1), lift), _on_face(cx + r0 * math.cos(a0), hy + r0 * math.sin(a0), lift)]
                else:
                    pts += [_on_face(cx, hy, lift + 0.004)]
                part.face_uv(pts, mat, [(0, 0)] * len(pts), out=(0, 0.2, 1))


def _number_geometry(part, number, lift=0.0012):
    """the car number as flat black shapes on the wiper cover (the digits' outlines from cab_numbers.json)"""
    path = os.path.join(SIGNS, 'cab_numbers.json')
    if not os.path.exists(path):
        return False
    with open(path) as f:
        contours = json.load(f).get(number, {}).get('contours')
    if not contours:
        return False
    polys = [[(x + NUMBER_SHIFT, y) for x, y in c] for c in contours]

    def inside(pt, poly):
        x, y = pt
        hit = False
        for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]):
            if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
                hit = not hit
        return hit

    def area(poly):
        return abs(sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]))) / 2

    # even-odd: a contour inside an even number of others is an outline, the rest are its holes; each outline is
    # filled on its own with the holes it holds (scanfill takes one outline at a time)
    depth = [sum(inside(c[0], o) for j, o in enumerate(polys) if j != i) for i, c in enumerate(polys)]
    outlines = [i for i, d in enumerate(depth) if d % 2 == 0]
    for i in outlines:
        holes = [j for j, d in enumerate(depth) if d % 2 == 1 and inside(polys[j][0], polys[i])
                 and min((area(polys[k]) for k in outlines if inside(polys[j][0], polys[k])), default=0) == area(polys[i])]
        group = [polys[i]] + [polys[j] for j in holes]
        vecs = [[Vector((x, y, 0.0)) for x, y in c] for c in group]
        flat = [v for c in vecs for v in c]
        for tri in geometry.tessellate_polygon(vecs):
            pts = [_on_face(flat[k].x, flat[k].y, lift) for k in tri]
            part.face_uv(pts, 'kb_letter', [(0.0, 0.0)] * 3, smooth=False, out=(0, 0.2, 1))
    return True


def _round_rect_on_face(part, mat, cx, cy, w, h, r, lift, seg=4):
    """a flat rounded rectangle on the cab face (a fan from its centre)"""
    ring = []
    for qx, qy, a in ((1, 1, 0.0), (-1, 1, 90.0), (-1, -1, 180.0), (1, -1, 270.0)):
        ox, oy = cx + qx * (w / 2 - r), cy + qy * (h / 2 - r)
        for k in range(seg + 1):
            t = math.radians(a + 90.0 * k / seg)
            ring.append(_on_face(ox + r * math.cos(t), oy + r * math.sin(t), lift))
    c = _on_face(cx, cy, lift)
    for a, b in zip(ring, ring[1:] + ring[:1]):
        part.face_uv([c, a, b], mat, [(0, 0)] * 3, out=(0, 0.2, 1))


def _side_x(y):
    """the body side's half width at height y (vertical side, then the shoulder)"""
    if y <= EAVE:
        return HW
    dy = min(y - EAVE, SHOULDER)
    return HW - SHOULDER + math.sqrt(SHOULDER * SHOULDER - dy * dy)


# The "KEIKYU" logotype on the lower side (owner allows company logos, 2026-11-04): a thin metal frame round six
# metal block letters on the red, near the car's right-hand end as seen from either side (point symmetry). Measured on
# photo 04 (Keikyu-N1000-ALcar, The RW place, CC BY-SA 3.0; a Tpu with its pantographs): the box ends 0.35 m short of
# the end window's outer edge, 0.39 x 0.13 m, its centre 0.33 m above the body's lower edge; the letters fill ~92 % of
# the box's width and ~2/3 of its height. Seen clearly only on that car; photos of the cab cars' lower sides are too
# oblique to tell, so the logo goes on the cars listed here.
SIDE_LOGO = (7.585, 1.317, 0.39, 0.13, 0.006)   # |z| of the centre, y of the centre, width, height, frame width
SIDE_LOGO_CARS = ('middle',)
LOGO_CAP = 0.088                                 # letter height
LOGO_STROKE = 0.17                               # stroke / letter height
LOGO_GAP = 0.14                                  # letter gap / letter height


def _logo_letters():
    """KEIKYU as polygons in letter-height units (a along the line of text, b up; baseline at b = 0); and the width"""
    t = LOGO_STROKE
    s = t * 1.25                                  # horizontal width of a slanted stroke

    def rect(a0, b0, a1, b1):
        return [(a0, b0), (a1, b0), (a1, b1), (a0, b1)]

    # the pieces of a letter only touch (overlapping coplanar faces render black)
    def K(w=0.62, lo=0.32, hi=0.62):
        # one outline: the stem, the leg from the stem at b = lo, the arm from the stem at b = hi; the leg's right edge
        # meets the arm's lower edge at (pa, pb)
        d1 = (w - s - t, 1 - hi)                  # along the arm
        d2 = (w - s - t, -lo)                     # along the leg
        k = -1 / (d1[1] - d2[1])
        pa, pb = w + k * d1[0], 1 + k * d1[1]
        return [[(0, 0), (t, 0), (t, lo), (w - s, 0), (w, 0), (pa, pb), (w, 1), (w - s, 1), (t, hi), (t, 1), (0, 1)]], w

    def E(w=0.52):
        return [rect(0, 0, t, 1), rect(t, 1 - t, w, 1), rect(t, 0.5 - t / 2, w * 0.92, 0.5 + t / 2), rect(t, 0, w, t)], w

    def I():
        return [rect(0, 0, t, 1)], t

    def Y(w=0.66):
        m, j = w / 2, 0.44                        # the arms meet the stem at b = j; their inner edges at b = j + 0.28
        return [rect(m - t / 2, 0, m + t / 2, j),
                [(m - t / 2, j), (m + t / 2, j), (w, 1), (w - s, 1), (m, j + 0.28), (s, 1), (0, 1)]], w

    def U(w=0.60, n=10):
        r0, r1, c = w / 2 - t, w / 2, 0.30
        polys = [rect(0, c, t, 1), rect(w - t, c, w, 1)]
        for k in range(n):                        # the bowl: a half ring below b = c
            a0, a1 = math.pi + math.pi * k / n, math.pi + math.pi * (k + 1) / n
            polys.append([(w / 2 + r1 * math.cos(a0), c + r1 * math.sin(a0) * (c / r1)),
                          (w / 2 + r1 * math.cos(a1), c + r1 * math.sin(a1) * (c / r1)),
                          (w / 2 + r0 * math.cos(a1), c + r0 * math.sin(a1) * ((c - t) / r0)),
                          (w / 2 + r0 * math.cos(a0), c + r0 * math.sin(a0) * ((c - t) / r0))])
        return polys, w

    out, a = [], 0.0
    for polys, w in (K(), E(), I(), K(), Y(), U()):
        out += [[(a + pa, pb) for pa, pb in p] for p in polys]
        a += w + LOGO_GAP
    return out, a - LOGO_GAP


def side_logo(part, kind, lift=0.0015):
    """the KEIKYU logotype on both sides (flat metal shapes just off the side)"""
    if kind not in SIDE_LOGO_CARS:
        return
    zc_abs, yc, w, h, fw = SIDE_LOGO
    letters, width = _logo_letters()
    for side in (-1, 1):
        x = side * (HW + lift)
        # the right-hand end as seen from outside: −z on the left side (+x), +z on the right side (−x); text runs
        # from the viewer's left to right, i.e. towards −z on the left side and +z on the right side
        zc = -side * zc_abs
        run = -side

        def at(a, b):                              # a, b in metres from the box centre (a to the viewer's right)
            return (x, yc + b, zc + run * a)

        def quad(pts):
            part.face_uv([at(*p) for p in pts], 'kb_sill', [(0.0, 0.0)] * len(pts), smooth=False, out=(side, 0, 0))

        # the frame
        for a0, b0, a1, b1 in ((-w / 2, h / 2 - fw, w / 2, h / 2), (-w / 2, -h / 2, w / 2, -h / 2 + fw),
                               (-w / 2, -h / 2 + fw, -w / 2 + fw, h / 2 - fw), (w / 2 - fw, -h / 2 + fw, w / 2, h / 2 - fw)):
            quad([(a0, b0), (a1, b0), (a1, b1), (a0, b1)])
        # the letters, centred in the box
        for p in letters:
            quad([((pa - width / 2) * LOGO_CAP, (pb - 0.5) * LOGO_CAP) for pa, pb in p])


def side_fittings(part, boxes, kind):
    """side destination displays, side lamps, the KEIKYU logotype, and on a cab car the crew doors' grab rails and handles"""
    side_logo(part, kind)
    for side in (-1, 1):
        sz = 1 if side < 0 else -1          # point symmetry: the left side mirrors z
        zc, yc, w, h = SIDE_SIGN
        zc *= sz
        if 'led_side_wide' in boxes or 'led_side' in boxes:
            u0, v0, u1, v1 = boxes.get('led_side_wide', boxes.get('led_side'))
            nz, ny = 4, 2
            for j in range(ny):
                for i in range(nz):
                    za, zb = zc - w / 2 + w * i / nz, zc - w / 2 + w * (i + 1) / nz
                    ya, yb = yc - h / 2 + h * j / ny, yc - h / 2 + h * (j + 1) / ny
                    pts = [(side * (_side_x(ya) + 0.004), ya, za), (side * (_side_x(ya) + 0.004), ya, zb),
                           (side * (_side_x(yb) + 0.004), yb, zb), (side * (_side_x(yb) + 0.004), yb, za)]
                    # seen from outside, the image's left is towards +z on the left side (+x) and −z on the right
                    def uu(z):
                        t = (z - (zc - w / 2)) / w
                        return u0 + (u1 - u0) * ((1 - t) if side > 0 else t)
                    uvs = [(uu(p[2]), v0 + (v1 - v0) * (p[1] - (yc - h / 2)) / h) for p in pts]
                    part.face_uv(pts, 'kb_led', uvs, out=(side, 0, 0))
            # a dark surround
            part.box('kb_frame', *sorted((side * (HW - 0.01), side * (HW + 0.003))), yc - h / 2 - 0.02, yc + h / 2 + 0.02, zc - w / 2 - 0.02, zc + w / 2 + 0.02)
        # side lamp: a small dome
        lz, ly, lr = SIDE_LAMP
        lz *= sz
        part.box('kb_frame', *sorted((side * (HW - 0.005), side * (HW + 0.012))), ly - lr - 0.012, ly + lr + 0.012, lz - lr - 0.012, lz + lr + 0.012, bevel=0.008, segments=2)
        part.cylinder('kb_sidelamp', (side * (HW + 0.016), ly, lz), lr, 0.012, axis='x', segments=16)
    if kind != 'cab':
        return
    cz0, cz1, cy0, cy1 = CREW_DOOR
    for side in (-1, 1):
        x = side * HW
        # grab rails at the door's rear edge: two vertical bars on stand-offs
        zr = cz0 + 0.07
        for ya, yb in ((1.84, 2.44), (1.24, 1.64)):
            part.cylinder('kb_chrome', (x + side * 0.05, (ya + yb) / 2, zr), 0.0125, yb - ya, axis='y', segments=10)
            for yy in (ya + 0.02, yb - 0.02):
                part.cylinder('kb_chrome', (x + side * 0.025, yy, zr), 0.009, 0.05, axis='x', segments=8)
        # door handle (recessed grip plate)
        part.box('kb_frame', *sorted((x, x + side * 0.006)), 2.05, 2.21, cz1 - 0.12, cz1 - 0.06, bevel=0.003, segments=1)


# ---------------------------------------------------------------- the skirt

SKIRT_TOP = 0.975
SKIRT_BOTTOM = 0.24
SKIRT_GAP = 0.025          # set back from the body's face
SKIRT_REAR = 7.95          # its sides reach back to here
OPEN_X = 0.63              # half width of the coupler opening
OPEN_Y = 0.40              # its bottom
OPEN_R = 0.07
SKIRT_T = 0.008
SKIRT_UV = (-2.3, 2.3, 0.2, 1.0)


def _skirt_outline():
    """the skirt's plan outline [(s, x, z, nx, nz)]: s = arc from the centre line, (nx, nz) outward"""
    nose = Nose()
    row = nose.full_row(0)
    pts = [(row[0][0], SKIRT_REAR)] + [(p[0], p[2]) for p in row] + [(row[-1][0], SKIRT_REAR)]
    p = np.array(pts)
    seg = np.linalg.norm(np.diff(p, axis=0), axis=1)
    keep = np.concatenate([[True], seg > 1e-6])
    p = p[keep]
    seg = np.linalg.norm(np.diff(p, axis=0), axis=1)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    s -= np.interp(0.0, p[:, 0], s)
    # resample evenly, keeping the opening's edges as columns
    total = np.arange(s[0], s[-1], 0.04)
    extra = [-OPEN_X, OPEN_X] + [sgn * (OPEN_X - OPEN_R + OPEN_R * math.sin(math.pi / 2 * k / 6)) for sgn in (-1, 1) for k in range(7)]
    ss = np.unique(np.concatenate([total, [s[-1]], extra]))
    x = np.interp(ss, s, p[:, 0])
    z = np.interp(ss, s, p[:, 1])
    t = np.gradient(np.stack([x, z], 1), axis=0)
    t /= np.linalg.norm(t, axis=1)[:, None]
    nrm = np.stack([-t[:, 1], t[:, 0]], 1)        # left of the direction of travel (−x → +x): outward
    if np.mean(nrm[:, 1][np.abs(x) < 0.5]) < 0:
        nrm = -nrm
    x = x - nrm[:, 0] * SKIRT_GAP
    z = z - nrm[:, 1] * SKIRT_GAP
    return [(float(a), float(b), float(c), float(d), float(e)) for a, b, c, d, e in zip(ss, x, z, nrm[:, 0], nrm[:, 1])]


def _skirt_bottom(s, smax):
    """lower edge: level across the front, rising along the sides towards the back"""
    return SKIRT_BOTTOM + 0.30 * K.smoothstep(smax - 0.75, smax, abs(s))


def _opening_top(s):
    """top of the bottom bar under the coupler (its rounded corners rise to the opening's sides)"""
    a = abs(s) - (OPEN_X - OPEN_R)
    if a <= 0:
        return OPEN_Y
    a = min(a, OPEN_R)
    return OPEN_Y + OPEN_R - math.sqrt(max(OPEN_R * OPEN_R - a * a, 0.0))


def skirt(part):
    """the light grey skirt under the cab face: two hatch panels, the bar under the coupler, wrapped round the corners"""
    ol = _skirt_outline()
    smax = max(abs(o[0]) for o in ol)
    u0, u1, v0, v1 = SKIRT_UV

    def uv(sv, y):
        return ((sv - u0) / (u1 - u0), (y - v0) / (v1 - v0))

    def pos(o, y, back=0.0):
        sv, x, z, nx, nz = o
        return (x - nx * back, y, z - nz * back)

    for back, flip in ((0.0, False), (SKIRT_T, True)):
        for a, b in zip(ol[:-1], ol[1:]):
            sm = (a[0] + b[0]) / 2
            inside = abs(sm) < OPEN_X - 1e-6
            ya_top = _opening_top(a[0]) if inside else SKIRT_TOP
            yb_top = _opening_top(b[0]) if inside else SKIRT_TOP
            ya_bot, yb_bot = _skirt_bottom(a[0], smax), _skirt_bottom(b[0], smax)
            rows = 3 if inside else 6
            for j in range(rows):
                t0, t1 = j / rows, (j + 1) / rows
                ya0, ya1 = ya_bot + (ya_top - ya_bot) * t0, ya_bot + (ya_top - ya_bot) * t1
                yb0, yb1 = yb_bot + (yb_top - yb_bot) * t0, yb_bot + (yb_top - yb_bot) * t1
                pts = [pos(a, ya0, back), pos(b, yb0, back), pos(b, yb1, back), pos(a, ya1, back)]
                uvs = [uv(a[0], ya0), uv(b[0], yb0), uv(b[0], yb1), uv(a[0], ya1)]
                nrm = Vector((a[3] + b[3], 0, a[4] + b[4]))
                part.face_uv(pts, 'kb_skirt', uvs, out=(-nrm if flip else nrm))
            # bottom edge and the opening's rim
            part.face_uv([pos(a, ya_bot), pos(b, yb_bot), pos(b, yb_bot, SKIRT_T), pos(a, ya_bot, SKIRT_T)], 'kb_skirt',
                         [uv(a[0], ya_bot)] * 4, smooth=False, out=(0, -1, 0)) if not flip else None
            if inside and not flip:
                part.face_uv([pos(a, ya_top), pos(b, yb_top), pos(b, yb_top, SKIRT_T), pos(a, ya_top, SKIRT_T)], 'kb_skirt',
                             [uv(a[0], ya_top)] * 4, smooth=False, out=(0, 1, 0))
    # the opening's vertical edges and the sides' back ends
    for o in ol:
        if abs(abs(o[0]) - OPEN_X) < 1e-6:
            y0 = OPEN_Y + OPEN_R
            part.face_uv([pos(o, y0), pos(o, SKIRT_TOP), pos(o, SKIRT_TOP, SKIRT_T), pos(o, y0, SKIRT_T)], 'kb_skirt',
                         [uv(o[0], y0)] * 4, smooth=False, out=(-math.copysign(1, o[0]) * o[4], 0, math.copysign(1, o[0]) * o[3]))
    for o in (ol[0], ol[-1]):
        yb = _skirt_bottom(o[0], smax)
        part.face_uv([pos(o, yb), pos(o, SKIRT_TOP), pos(o, SKIRT_TOP, SKIRT_T), pos(o, yb, SKIRT_T)], 'kb_skirt',
                     [uv(o[0], yb)] * 4, smooth=False, out=(0, 0, -1))
    # hinges and latches of the hatches (outer edge hinges, inner edge latches)
    for sgn in (-1, 1):
        for sv, ys in ((1.16, (0.89, 0.44)), (0.70, (0.86, 0.46))):
            o = min(ol, key=lambda q: abs(q[0] - sgn * sv))
            for yh in ys:
                cx, _, cz = pos(o, yh)
                hw = 0.035
                part.box('kb_hinge', cx - hw, cx + hw, yh - 0.03, yh + 0.03, cz - 0.004, cz + 0.014, bevel=0.004, segments=1)


def paint_skirt(w=1024, h=192):
    """the skirt's panel joints and a little grime towards the bottom"""
    cv = Canvas(SKIRT_UV, w, h)
    U, V = cv.U, cv.V
    grey = np.array((0.745, 0.742, 0.738), np.float32)   # photos: #c5c1c2 in sun, #b1b1b4 in shade
    cv.fill(grey, 0.45)
    grime = np.clip((0.55 - V) / 0.35, 0, 1) ** 1.5 * 0.25
    cv.paint(grime.astype(np.float32), (0.52, 0.48, 0.43), 0.6)
    for sgn in (-1, 1):
        # hatch outlines
        x0, x1 = sorted((sgn * 0.69, sgn * 1.17))
        sd = np.abs(_sd_round_rect(U, V, (x0 + x1) / 2, (0.32 + 0.965) / 2, x1 - x0, 0.965 - 0.32, 0.02)) - 0.003
        cv.paint(cv.cover(sd), (0.25, 0.25, 0.26), 0.6)
        # joints in the bar
        for xs in (0.42, OPEN_X + 0.02):
            sd = np.maximum(np.abs(U - sgn * xs) - 0.003, V - 0.42)
            cv.paint(cv.cover(sd), (0.25, 0.25, 0.26), 0.6)
    return cv
