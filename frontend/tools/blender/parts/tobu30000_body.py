"""
Body shell of the Tobu 30000 series as the 10-car Tojo Line sets look today (2021-2026): the stainless sides with their
beads, the roof, the gangway ends, the FRP cab front, the recessed doors and windows, and the painted textures (side:
stainless, royal maroon stripe, window sashes, door leaves, crew door; face: silver FRP, windscreens, gangway door,
red band, the band's ends on the cab sides), the LED displays, the car numbers and the cab front's fittings.

Figures (ja.wikipedia 東武30000系電車, read 2026-11-03): 20 m cars (20,000 mm over the couplers), body width 2,770 mm
(the body's reference width), height 4,045 mm with the AC, floor 1,150 mm, four pairs of sliding doors per side,
1,850 mm high; between the doors one two-pane unit window; FRP cab front with a gangway door; LED displays (type and
destination on the front, a large type + destination unit on the sides); royal maroon stripe on the stainless body.
Measured on Commons photos (scale from the body width, the door height 1.85 m and the coupler height 0.88 m):
- head-on "Tobu-Series30000 31612.jpg" (MaedaAkihiko, CC0, 2024; 232 px/m, rail top at image y 1115):
  windscreens |x| 0.48…1.32, y 1.95…3.43, corner r ≈ 0.13 with a black surround; gangway door surround |x| ≤ 0.445,
  y 0.93…3.10, door |x| ≤ 0.33, door window |x| ≤ 0.23, y 1.98…2.87; destination display |x| ≤ 0.385, y 3.29…3.49;
  type display x −1.19…−0.59, y 3.20…3.37 (inside the left windscreen seen from ahead); red band y 1.26…1.61; lamp units
  |x| 0.64…1.16, y 1.32…1.56 (tail lamp outside, head lamp inside); car number x −0.96…−0.49, y 1.66…1.79; chrome
  steps under the band |x| 0.63…1.24, y 1.01…1.06; face top 3.68 at the centre; corners round about 0.12 m at the
  sides, 0.30 m at the top.
- side "Tobu-Series30000 join.jpg" (MaedaAkihiko, CC BY-SA 4.0, 2021; 237 px/m vertically from the door): stripe
  0.18 m high just under the windows (y 1.65…1.83, its height checked against the face band beside it in the 31612
  photo), window opening 1.93…2.96, three beads on the lower panel (y 1.15, 1.33, 1.51) and two on the letterboard
  (3.08, 3.20), eave 3.34, body bottom 0.98; at the cab end: the face band runs 0.05…0.28 m onto the side as a
  parallelogram (top edge longer), the stripe starts 0.03 (bottom) … 0.14 m (top) behind the corner; crew door 0.62 m
  wide, 0.45 m behind the face's edge, y 1.09…2.89, with a tall window; door leaves with tall windows 0.36 m wide.
- door centres ±2.41 / ±7.23 m (the usual 4,820 mm pitch of 20 m four-door cars: estimate, no side-on photo), windows
  2.06 m wide between the doors, 0.60 m at the car ends (est. from the Musashi-Ranzan photo); side display 0.98 × 0.16 m
  over the middle window (photo 31612 and the close-up "Tobu Series30000-32401 Outside-LED.jpg").
Our estimates: the roof's shoulder radius 0.30 m and its arc, the plan bulge of the face (0.04 m), the bead section.

Frame: the game's car frame of train_kit (x left, y up, z forward, metres). A cab car has its cab at +z.
"""
import json
import math
import os

import bmesh  # noqa: F401
import bpy
import numpy as np
from mathutils import Vector

import train_kit as K
import body_n1000 as BD

UVPart = BD.UVPart

# ---------------------------------------------------------------- dimensions
HW = 1.385               # half the body width (2,770 mm)
BOTTOM = 0.98            # lower edge of the body side
EAVE = 3.34              # top of the vertical side (gutter)
SHOULDER = 0.30
ROOF = 3.68              # roof on the centre line
SILL = 1.13
DOOR_TOP = 2.98
DOOR_W = 1.30
DOOR_DEPTH = 0.030
DOORS = (-7.23, -2.41, 2.41, 7.23)
WIN = (1.93, 2.96)       # window openings (outer edge of the sashes)
WIN_DEPTH = 0.022
BAYS = (-4.82, 0.0, 4.82)
BAY_W = 2.06
END_WIN = (8.55, 9.15)   # |z| of the single-pane window at a gangway end
STRIPE = (1.65, 1.83)
BAND = (1.26, 1.61)
BEADS = (1.15, 1.33, 1.51, 3.08, 3.20)
BEAD_H, BEAD_W = 0.0035, 0.022
GUTTER = 0.012           # drip rail's overhang at the eave
END = 9.75               # gangway ends
END_R = 0.06
FACE_Z = 9.80            # cab face (centre line)
CAB_JOIN = 9.40          # side sweep ends here on a cab car, the nose starts
CAB_BULGE = 0.04
R_SIDE, R_TOP = 0.12, 0.30
CREW_DOOR = (8.71, 9.33, 1.09, 2.89)
SIDE_SIGN = (0.0, 3.14, 0.98, 0.16)      # z, y, w, h (both sides)
SIDE_LAMP = (-3.60, 3.15, 0.035)         # right side; the left side has it at +z
NUMBER_Z = 6.20                          # side numbers: beside door 1, at the window's top
NUMBER_Y = 2.82

# paint (sRGB)
STAINLESS = (0.80, 0.80, 0.81)
FRP = (0.75, 0.75, 0.75)                 # the painted silver cab front, a touch warmer and flatter than the steel
MAROON = (0.69, 0.06, 0.22)              # royal maroon film on the sides (sampled in sun: #c0184a…#b31946)
FRONT_RED = (0.72, 0.06, 0.18)           # the cab front's band (#cc0f2b in sun)
GLASS = (0.075, 0.085, 0.092)
SIDE_GLASS = (0.10, 0.115, 0.125)
RUBBER = (0.045, 0.045, 0.05)
SASH = (0.70, 0.71, 0.72)

SIGNS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'textures', 'tobu30000')


# ---------------------------------------------------------------- the section


def _roof_geometry():
    r = SHOULDER
    a = HW - r
    b = EAVE - ROOF
    rr = (r * r - a * a - b * b) / (2 * b + 2 * r)
    theta = math.atan2(EAVE - (ROOF - rr), a)
    return rr, theta


def half_profile(amp=1.0):
    """[(x, y, nx, ny)] from the bottom of the left side up to the roof's centre line; `amp` scales the beads and the
    gutter (0 at the car ends, where they stop); the point count does not depend on it"""
    pts = []
    for x, y in ((HW - 0.030, BOTTOM), (HW - 0.012, 1.005), (HW - 0.003, 1.035), (HW, 1.07)):
        pts.append((x, y, 1.0, 0.0))
    ys = {SILL, DOOR_TOP, WIN[0], WIN[1], STRIPE[0], STRIPE[1], EAVE}
    bead_pts = []
    for yb in BEADS:
        for dy, h in ((-BEAD_W / 2, 0.0), (-BEAD_W / 6, 1.0), (BEAD_W / 6, 1.0), (BEAD_W / 2, 0.0)):
            bead_pts.append((yb + dy, h))
    for y in np.arange(1.12, EAVE - 0.02, 0.10):
        if all(abs(y - k) > 0.03 for k in ys) and all(abs(y - b) > 0.03 for b in BEADS):
            ys.add(float(y))
    allp = [(y, 0.0) for y in ys] + bead_pts
    for y, h in sorted(allp):
        pts.append((HW + h * BEAD_H * amp, y, 1.0, 0.0))
    # drip rail at the eave (stainless, a small overhang)
    g = GUTTER * amp
    for dx, dy in ((g, 0.004), (g, 0.022), (0.3 * g, 0.028)):
        pts.append((HW + dx, EAVE + dy, 1.0, 0.0))
    r = SHOULDER
    rr, theta = _roof_geometry()
    ns = 8
    y0 = EAVE + 0.028
    for k in range(1, ns + 1):
        t = theta * k / ns
        y = EAVE + r * math.sin(t)
        if y <= y0 + 0.005:
            y = y0 + 0.005 + 0.001 * k
        pts.append((HW - r + r * math.cos(t), y, math.cos(t), math.sin(t)))
    nr = 9
    for k in range(1, nr + 1):
        a = theta + (math.pi / 2 - theta) * k / nr
        x = rr * math.cos(a)
        pts.append((0.0 if k == nr else x, ROOF - rr + rr * math.sin(a), math.cos(a), math.sin(a)))
    return pts


def ring(amp=1.0):
    half = half_profile(amp)
    right = [(-x, y, -nx, ny) for x, y, nx, ny in half]
    return right + list(reversed(half[:-1]))


def roof_half():
    """(x, y) of the built roof for the roof equipment (from the centre line out)"""
    return [(x, y) for x, y, _nx, _ny in half_profile(1.0)]


# ---------------------------------------------------------------- the cab end as a height field


def face_z(x, y):
    return FACE_Z - CAB_BULGE * (x / HW) ** 2


def corner_radius(y):
    return R_SIDE + (R_TOP - R_SIDE) * K.smoothstep(3.05, 3.50, y)


class Nose:
    """
    As body_n1000.Nose: for every ring point a column from the side wall into the face through a quarter-round, the
    face between the columns' ends as rows across; the ring is the one without beads or gutter.
    """

    def __init__(self, steps=8, across=32):
        self.ring = ring(0.0)
        n = len(self.ring)
        self.half = (n + 1) // 2
        self.steps = steps
        self.cols = []
        for x, y, nx, ny in self.ring:
            r = corner_radius(y)
            col = []
            for k in range(steps + 1):
                phi = (math.pi / 2) * k / steps
                d = r * (1 - math.cos(phi))
                px, py = x - nx * d, y - ny * d
                col.append((px, py, face_z(px, py) - r * (1 - math.sin(phi))))
            self.cols.append(col)
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
        """row i from the right side wall (at CAB_JOIN) through the face to the left side wall"""
        n = len(self.ring)
        xr, yr, _, _ = self.ring[i]
        xl, yl, _, _ = self.ring[n - 1 - i]
        right = [(xr, yr, CAB_JOIN)] + list(self.cols[i])
        left = list(reversed(self.cols[n - 1 - i])) + [(xl, yl, CAB_JOIN)]
        mid = self.rows[i][1:-1] if len(self.rows[i]) > 1 else []
        return right + mid + left

    @staticmethod
    def row_u(pts):
        p = np.array(pts)
        seg = np.linalg.norm(np.diff(p, axis=0), axis=1)
        s = np.concatenate([[0.0], np.cumsum(seg)])
        return s - np.interp(0.0, p[:, 0], s)


def _out(p, cz):
    return Vector(p) - Vector((0.0, 2.0, max(-9.0, min(9.0, cz))))


# ---------------------------------------------------------------- the shell


class Body:
    SIDE_UV = (-9.90, 9.90, 0.95, 3.40)
    FACE_UV = (-2.0, 2.0, 0.95, 3.75)

    def __init__(self, kind):
        self.kind = kind
        self.cab = kind == 'cab'
        self.n = len(ring(1.0))
        self.half = (self.n + 1) // 2
        self.nose = Nose() if self.cab else None
        self.side_mat = 'tb_side'          # one atlas: the cab car's side in the lower half, the middle car's above

    # openings in the side: (z0, z1, y0, y1, depth, kind)
    def openings(self):
        out = []
        for zd in DOORS:
            out.append((zd - DOOR_W / 2, zd + DOOR_W / 2, SILL, DOOR_TOP, DOOR_DEPTH, 'door'))
        for zb in BAYS:
            out.append((zb - BAY_W / 2, zb + BAY_W / 2, WIN[0], WIN[1], WIN_DEPTH, 'win'))
        out.append((-END_WIN[1], -END_WIN[0], WIN[0], WIN[1], WIN_DEPTH, 'win'))
        if not self.cab:
            out.append((END_WIN[0], END_WIN[1], WIN[0], WIN[1], WIN_DEPTH, 'win'))
        return out

    def side_uv(self, z, y):
        u0, u1, v0, v1 = self.SIDE_UV
        return ((z - u0) / (u1 - u0), ((y - v0) / (v1 - v0) + (0.0 if self.cab else 1.0)) / 2)

    def face_uv(self, u, y):
        u0, u1, v0, v1 = self.FACE_UV
        return ((u - u0) / (u1 - u0), (y - v0) / (v1 - v0))

    @staticmethod
    def zone(x, y):
        if y > EAVE + 0.03:
            return 'tb_roof'
        if y >= EAVE - 1e-6 and abs(x) > HW - 0.01:
            return 'tb_steel'
        return 'tb_steel'

    def textured(self, x, y):
        return abs(x) > HW - 0.035 and y < EAVE - 1e-6 + 0.0005

    def z_end(self):
        return CAB_JOIN if self.cab else END - END_R

    def stations(self):
        z0, z1 = -(END - END_R), self.z_end()
        zs = {z0, z1, z0 + 0.05, z1 - 0.05}
        for a, b, *_ in self.openings():
            zs.add(a)
            zs.add(b)
        if self.cab:
            zs.update((CREW_DOOR[0], CREW_DOOR[1]))
        out = sorted(zs)
        fine = []
        for a, b in zip(out[:-1], out[1:]):
            k = max(1, int(math.ceil((b - a) / 1.2)))
            fine += [a + (b - a) * i / k for i in range(k)]
        return fine + [out[-1]]

    def amp(self, z):
        z0, z1 = -(END - END_R), self.z_end()
        return 0.0 if (abs(z - z0) < 1e-6 or abs(z - z1) < 1e-6) else 1.0

    def in_opening(self, za, zb, ya, yb):
        for z0, z1, y0, y1, *_ in self.openings():
            if za >= z0 - 1e-6 and zb <= z1 + 1e-6 and ya >= y0 - 1e-6 and yb <= y1 + 1e-6:
                return True
        return False

    def build(self, part):
        zs = self.stations()
        rings = {z: ring(self.amp(z)) for z in zs}
        for za, zb in zip(zs[:-1], zs[1:]):
            ra, rb = rings[za], rings[zb]
            for i in range(self.n - 1):
                (xa, ya, nxa, _), (xb, yb, nxb, _) = ra[i], ra[i + 1]
                (xc, yc, _, _), (xd, yd, _, _) = rb[i + 1], rb[i]
                if abs(xa) > HW - 0.01 and abs(xb) > HW - 0.01 and self.in_opening(za, zb, min(ya, yb), max(ya, yb)):
                    continue
                pts = [(xa, ya, za), (xb, yb, za), (xc, yc, zb), (xd, yd, zb)]
                cx, cy = 0.5 * (xa + xb), 0.5 * (ya + yb)
                out = _out((cx, cy, 0.5 * (za + zb)), 0.5 * (za + zb))
                flat = abs(cx) > HW - 0.03 and cy < EAVE - 0.005      # beads: crisp edges, no smeared highlight
                if self.textured(cx, cy):
                    part.face_uv(pts, self.side_mat, [self.side_uv(p[2], p[1]) for p in pts], out=out, smooth=not flat)
                else:
                    part.face_uv(pts, self.zone(cx, cy), [(0, 0)] * 4, out=out, smooth=not flat)
        r0 = rings[zs[0]]
        part.face_uv([(-HW + 0.03, BOTTOM, zs[0]), (HW - 0.03, BOTTOM, zs[0]), (HW - 0.03, BOTTOM, zs[-1]), (-HW + 0.03, BOTTOM, zs[-1])],
                     'tb_under', [(0, 0)] * 4, smooth=False, out=(0, -1, 0))
        del r0
        self.gangway_end(part, -END, -1)
        if self.cab:
            self.cab_end(part)
        else:
            self.gangway_end(part, END, 1)
        for z0, z1, y0, y1, depth, kind in self.openings():
            for s in (1, -1):
                self.opening(part, z0, z1, y0, y1, depth, kind, s)

    def gangway_end(self, part, z_end, sign):
        steps = 3
        rg = ring(0.0)
        cols = []
        for x, y, nx, ny in rg:
            col = []
            for k in range(steps + 1):
                phi = (math.pi / 2) * k / steps
                d = END_R * (1 - math.cos(phi))
                col.append((x - nx * d, y - ny * d, z_end - sign * END_R * (1 - math.sin(phi))))
            cols.append(col)
        for i in range(self.n - 1):
            for k in range(steps):
                pts = [cols[i][k], cols[i + 1][k], cols[i + 1][k + 1], cols[i][k + 1]]
                cx = sum(p[0] for p in pts) / 4
                cy = sum(p[1] for p in pts) / 4
                c = Vector([sum(p[j] for p in pts) / 4 for j in range(3)])
                out = c - Vector((0.0, 2.0, z_end - sign * 1.0))
                if self.textured(cx, cy) and k == 0:
                    part.face_uv(pts, self.side_mat, [self.side_uv(p[2], p[1]) for p in pts], out=out)
                else:
                    part.face_uv(pts, self.zone(cx, cy), [(0, 0)] * 4, out=out)
        for i in range(self.half - 1):
            a, b = cols[i][-1], cols[self.n - 1 - i][-1]
            c, d = cols[i + 1][-1], cols[self.n - 2 - i][-1]
            pts = [a, b, d, c] if c != d else [a, b, c]
            part.face_uv(pts, 'tb_steel', [(0, 0)] * len(pts), smooth=False, out=(0, 0, sign))
        b0, b1 = cols[0], cols[self.n - 1]
        for k in range(steps):
            part.face_uv([b0[k], b1[k], b1[k + 1], b0[k + 1]], 'tb_under', [(0, 0)] * 4, smooth=False, out=(0, -1, 0))
        gangway_fittings(part, z_end, sign)

    def cab_end(self, part):
        nose = self.nose
        n = self.n
        rg = nose.ring
        # texture coordinates: u = arc length along each row from the centre line (through the side wall to CAB_JOIN)
        k1 = nose.steps + 2           # side-wall point + column points
        u_col, u_row = [None] * n, [None] * self.half
        for i in range(self.half):
            pts = nose.full_row(i)
            u = nose.row_u(pts)
            u_col[i] = list(u[:k1])
            if i != n - 1 - i:
                u_col[n - 1 - i] = list(reversed(u[len(u) - k1:]))
            if len(nose.rows[i]) > 1:
                u_row[i] = [u[k1 - 1]] + list(u[k1:len(u) - k1]) + [u[len(u) - k1]]
            else:
                u_row[i] = [0.0]

        def wall(i):
            x, y, _, _ = rg[i]
            return [(x, y, CAB_JOIN)] + list(nose.cols[i])

        out_c = Vector((0.0, 2.0, FACE_Z - 2.0))
        for i in range(n - 1):
            ca, cb = wall(i), wall(i + 1)
            for k in range(len(ca) - 1):
                pts = [ca[k], cb[k], cb[k + 1], ca[k + 1]]
                cy = sum(p[1] for p in pts) / 4
                cx = sum(p[0] for p in pts) / 4
                c = Vector([sum(p[j] for p in pts) / 4 for j in range(3)])
                if k == 0 and cy > EAVE + 0.03:
                    part.face_uv(pts, 'tb_roof', [(0, 0)] * 4, out=c - out_c)
                    continue
                uvs = [(u_col[i][k], pts[0][1]), (u_col[i + 1][k], pts[1][1]), (u_col[i + 1][k + 1], pts[2][1]), (u_col[i][k + 1], pts[3][1])]
                part.face_uv(pts, 'tb_face', [self.face_uv(u, v) for u, v in uvs], out=c - out_c)
                del cx
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
                part.face_uv(pts, 'tb_face', [self.face_uv(u, v) for u, v in uvs], out=(0, 0.3, 1))
        # underside of the nose
        bottom = nose.full_row(0)
        c = (0.0, BOTTOM, CAB_JOIN)
        prev = bottom[0]
        for p in bottom[1:]:
            q = (p[0], BOTTOM, p[2])
            if (Vector(q) - Vector(prev)).length > 1e-7:
                part.face_uv([c, prev, q], 'tb_under', [(0, 0)] * 3, smooth=False, out=(0, -1, 0))
            prev = q

    def opening(self, part, z0, z1, y0, y1, depth, kind, side):
        """a door or window opening on side +1 (left) or −1: jambs into the side, the leaves / sashes set back"""
        x0 = side * HW
        x1 = side * (HW - depth)
        sweep = [y for x, y, nx, ny in ring(1.0)[self.half - 1:] if abs(x - HW) < BEAD_H * 1.01 and y0 - 1e-6 <= y <= y1 + 1e-6]
        ys = sorted(set([y0, y1] + sweep))
        jamb = 'tb_jamb'
        for zj, facing in ((z0, 1), (z1, -1)):
            for ya, yb in zip(ys[:-1], ys[1:]):
                part.face_uv([(x0, ya, zj), (x0, yb, zj), (x1, yb, zj), (x1, ya, zj)], jamb, [(0, 0)] * 4, smooth=False, out=(0, 0, facing))
        part.face_uv([(x0, y1, z0), (x0, y1, z1), (x1, y1, z1), (x1, y1, z0)], jamb, [(0, 0)] * 4, smooth=False, out=(0, -1, 0))
        part.face_uv([(x0, y0, z0), (x0, y0, z1), (x1, y0, z1), (x1, y0, z0)], 'tb_sill' if kind == 'door' else jamb, [(0, 0)] * 4,
                     smooth=False, out=(0, 1, 0))
        # the set-back plane, split where the texture changes so its edges have vertices
        yl = sorted(set([y0, y1] + [y for y in (STRIPE[0], STRIPE[1], 2.0, 2.88) if y0 < y < y1]))
        zl = [z0, (z0 + z1) / 2, z1] if kind == 'door' else [z0, z1]
        for ya, yb in zip(yl[:-1], yl[1:]):
            for za, zb in zip(zl[:-1], zl[1:]):
                pts = [(x1, ya, za), (x1, yb, za), (x1, yb, zb), (x1, ya, zb)]
                part.face_uv(pts, self.side_mat, [self.side_uv(p[2], p[1]) for p in pts], smooth=False, out=(side, 0, 0))


def gangway_fittings(part, z_end, sign):
    """bellows between the cars and the two anti-fall plates (転落防止幌) at the end's sides"""
    BD.bellows(part, z_end, sign, half_gap=0.25, w=1.10, y0=1.13, y1=3.05)
    for s in (-1, 1):
        x0, x1 = sorted((s * 0.98, s * 1.30))
        z0, z1 = sorted((z_end, z_end + sign * 0.235))
        part.box('tb_plate', x0, x1, 1.12, 2.32, z0, z1, bevel=0.01, segments=1)


# ---------------------------------------------------------------- painting


class Canvas(BD.Canvas):
    """body_n1000.Canvas with a metallic channel (blue of the _mr image)"""

    def __init__(self, uv_box, w, h, metal=1.0):
        super().__init__(uv_box, w, h)
        self.metal = np.full((h, w), metal, np.float32)

    def paint(self, alpha, colour, rough=None, metal=None):
        super().paint(alpha, colour, rough)
        if metal is not None:
            self.metal = self.metal * (1 - alpha) + metal * alpha

    def image(self, name, path):
        img, mr = super().image(name, path)
        arr = np.array(mr.pixels[:], np.float32).reshape(self.h, self.w, 4)
        arr[..., 2] = np.clip(self.metal, 0, 1)
        mr.pixels.foreach_set(arr.ravel())
        mr.save()
        return img, mr


def _rr(U, V, z0, z1, y0, y1, r):
    return BD._sd_round_rect(U, V, (z0 + z1) / 2, (y0 + y1) / 2, z1 - z0, y1 - y0, r)


def _window_glass(cv, sd, U, V, base=SIDE_GLASS):
    """glass with the saloon behind it: a faint band of the far side's windows, darker below"""
    g = np.array(base, np.float32)
    far = ((V > 2.05) & (V < 2.80)).astype(np.float32)[..., None] * 0.06
    low = np.clip((2.15 - V) / 0.25, 0, 1)[..., None] * -0.03
    col = np.clip(g + far + low, 0, 0.27)
    a = cv.cover(sd)
    cv.paint(a, (0, 0, 0), 0.05, 0.0)
    cv.rgb = cv.rgb + col * a[..., None]


def paint_side(kind, w=4096, h=512):
    cv = Canvas(Body.SIDE_UV, w, h, metal=1.0)
    U, V = cv.U, cv.V
    cab = kind == 'cab'
    cv.fill(STAINLESS, 0.30)
    # panels: the letterboard and the lower panels a shade apart, faint rolling marks along the sheets
    cv.paint(((V > WIN[1]) & (V < EAVE)).astype(np.float32) * 0.5, (0.83, 0.83, 0.84), 0.27)
    streak = 0.5 + 0.5 * np.sin(V * 397.0) * np.sin(V * 151.0 + 1.3)
    cv.rough = cv.rough + 0.04 * (streak - 0.5)
    # the beads' shadow lines (geometry carries the ridge, this the dark lap under it)
    for yb in BEADS:
        sd = np.abs(V - (yb - BEAD_W / 2 - 0.002)) - 0.0018
        cv.paint(cv.cover(sd) * 0.45, (0.42, 0.42, 0.44), 0.4)
    # the stripe
    z_end = CAB_JOIN + 0.01 if cab else 9.90
    sd = np.maximum(np.maximum(STRIPE[0] - V, V - STRIPE[1]), U - z_end)
    cv.paint(cv.cover(sd), MAROON, 0.55, 0.0)
    doors = DOORS
    # door frames: polished strips round the openings (sides and head)
    for zd in doors:
        z0, z1 = zd - DOOR_W / 2, zd + DOOR_W / 2
        outer = np.maximum(np.maximum(z0 - 0.045 - U, U - z1 - 0.045), np.maximum(SILL - 0.02 - V, V - DOOR_TOP - 0.045))
        cv.paint(cv.cover(outer), (0.86, 0.86, 0.87), 0.16, 1.0)
        # the door leaves (seen on the set-back plane)
        for s in (-1, 1):
            zc = zd + s * DOOR_W / 4
            sd = _rr(U, V, zc - 0.18, zc + 0.18, 2.00, 2.88, 0.06)
            cv.paint(cv.cover(sd), RUBBER, 0.5, 0.0)
            _window_glass(cv, sd + 0.016, U, V)
        inside = np.maximum(np.maximum(z0 - U, U - z1), np.maximum(SILL - V, V - DOOR_TOP))
        for zl, wl in ((zd, 0.014), (z0 + 0.006, 0.012), (z1 - 0.006, 0.012)):
            sd = np.maximum(np.abs(U - zl) - wl / 2, inside)
            cv.paint(cv.cover(sd), RUBBER, 0.6, 0.0)
        # the leaves' bottom rail (a darker kick strip)
        sd = np.maximum(np.maximum(z0 - U, U - z1), np.abs(V - (SILL + 0.03)) - 0.03)
        cv.paint(cv.cover(sd) * 0.4, (0.55, 0.55, 0.56), 0.4)
    # windows: aluminium sashes in the opening, corners of the reveal outside them stay steel
    wins = [(zb - BAY_W / 2, zb + BAY_W / 2, 2) for zb in BAYS] + [(-END_WIN[1], -END_WIN[0], 1)]
    if not cab:
        wins.append((END_WIN[0], END_WIN[1], 1))
    for z0, z1, panes in wins:
        y0, y1 = WIN
        sd_open = _rr(U, V, z0, z1, y0, y1, 0.07)
        inside = np.maximum(np.maximum(z0 - U, U - z1), np.maximum(y0 - V, V - y1))
        cv.paint(cv.cover(inside) * (1 - cv.cover(sd_open)), (0.62, 0.62, 0.63), 0.35)
        cv.paint(cv.cover(sd_open), SASH, 0.32, 1.0)
        if panes == 2:
            zm = (z0 + z1) / 2
            pane = [(z0 + 0.012, zm - 0.022), (zm + 0.022, z1 - 0.012)]
        else:
            pane = [(z0 + 0.012, z1 - 0.012)]
        for a, b in pane:
            sd = _rr(U, V, a, b, y0 + 0.012, y1 - 0.012, 0.055)
            cv.paint(cv.cover(np.abs(sd) - 0.003), (0.50, 0.51, 0.52), 0.4, 1.0)
            _window_glass(cv, sd + 0.034, U, V)
            # the glazing rubber
            cv.paint(cv.cover(np.abs(sd + 0.034) - 0.003), RUBBER, 0.6, 0.0)
    if cab:
        cz0, cz1, cy0, cy1 = CREW_DOOR
        sd = _rr(U, V, cz0, cz1, cy0, cy1, 0.04)
        cv.paint(cv.cover(np.abs(sd) - 0.004), (0.18, 0.18, 0.19), 0.6, 0.3)
        cv.paint(cv.cover(sd + 0.006) * 0.6, (0.83, 0.83, 0.84), 0.22)
        sdw = _rr(U, V, cz0 + 0.08, cz1 - 0.08, 1.97, 2.74, 0.05)
        cv.paint(cv.cover(sdw), RUBBER, 0.5, 0.0)
        _window_glass(cv, sdw + 0.014, U, V)
        # the stripe crosses the crew door (painted over the leaf)
        sd = np.maximum(np.maximum(STRIPE[0] - V, V - STRIPE[1]), np.maximum(cz0 + 0.006 - U, U - cz1 + 0.006))
        cv.paint(cv.cover(sd), MAROON, 0.55, 0.0)
    # small marks: the bottom edge darkens a little (road grime)
    grime = np.clip((1.10 - V) / 0.12, 0, 1) ** 2 * 0.35
    cv.paint(grime.astype(np.float32), (0.45, 0.43, 0.40), 0.6)
    return cv


def _cab_interior(V):
    top = np.array((0.05, 0.053, 0.058), np.float32)
    wall = np.array((0.30, 0.31, 0.33), np.float32)
    desk = np.array((0.07, 0.072, 0.078), np.float32)

    def ss(e0, e1):
        t = np.clip((V - e0) / (e1 - e0), 0, 1)
        return (t * t * (3 - 2 * t))[..., None]
    a = ss(2.25, 2.38)
    b = ss(3.05, 3.15)
    lift = (1.0 - 0.3 * np.clip((V - 2.4) / 0.6, 0, 1))[..., None]
    return (desk * (1 - a) + wall * lift * a) * (1 - b) + top * b


def paint_face(body, w=2048, h=1440):
    """the cab front: u = arc length from the centre line along each row (round the corners onto the sides)"""
    nose = body.nose
    cv = Canvas(Body.FACE_UV, w, h, metal=0.6)
    U, V = cv.U, cv.V
    rows_y, rows_u, rows_x, rows_z = [], [], [], []
    for i in range(body.half):
        if len(nose.rows[i]) < 2:
            continue
        pts = nose.full_row(i)
        rows_y.append(nose.rows[i][0][1])
        rows_u.append(nose.row_u(pts))
        rows_x.append(np.array([p[0] for p in pts]))
        rows_z.append(np.array([p[2] for p in pts]))
    rows_y = np.array(rows_y)
    X = np.zeros_like(U)
    Z = np.zeros_like(U)
    for j in range(h):
        y = V[j, 0]
        i = int(np.clip(np.searchsorted(rows_y, y) - 1, 0, len(rows_y) - 2))
        t = float(np.clip((y - rows_y[i]) / max(rows_y[i + 1] - rows_y[i], 1e-6), 0, 1))
        xa = np.interp(U[j], rows_u[i], rows_x[i])
        xb = np.interp(U[j], rows_u[i + 1], rows_x[i + 1])
        za = np.interp(U[j], rows_u[i], rows_z[i])
        zb = np.interp(U[j], rows_u[i + 1], rows_z[i + 1])
        X[j] = xa + (xb - xa) * t
        Z[j] = za + (zb - za) * t
    dxdu = np.abs(np.gradient(X, axis=1)) / cv.px
    aa = np.maximum(cv.px * dxdu, 1e-4)
    # d: how far behind the start of the corner rounding a texel on the side lies (< 0 on the corner and the face)
    z_col = face_z(HW, 2.0) - R_SIDE
    D = z_col - Z
    on_side = np.abs(X) > HW - 0.004
    cv.fill(FRP, 0.32)
    # the steel side behind the mask's joint
    seam = z_col - 0.03
    steel = (Z < seam) & on_side
    cv.paint(steel.astype(np.float32), STAINLESS, 0.30, 1.0)
    cv.paint((on_side & (np.abs(Z - seam) < 0.003)).astype(np.float32), (0.25, 0.25, 0.26), 0.5, 0.2)
    # the windscreens: black surround and glass with the cab behind
    for s in (-1, 1):
        x0, x1 = sorted((s * 0.48, s * 1.32))
        sd = _rr(X, V, x0, x1, 1.95, 3.43, 0.13)
        cv.paint(cv.cover(sd, aa), RUBBER, 0.45, 0.0)
        sdg = sd + 0.045
        a = cv.cover(sdg, aa)
        cv.paint(a, (0, 0, 0), 0.04, 0.0)
        cv.rgb = cv.rgb + _cab_interior(V) * a[..., None]
    # the gangway door (the raised surround is geometry): leaf, its edge, its window
    leaf = _rr(X, V, -0.335, 0.335, 0.98, 3.06, 0.05)
    cv.paint(cv.cover(leaf, aa), (0.78, 0.78, 0.79), 0.30, 0.9)
    cv.paint(cv.cover(np.abs(leaf) - 0.005, aa), (0.16, 0.16, 0.17), 0.6, 0.2)
    sd = _rr(X, V, -0.21, 0.21, 2.02, 2.93, 0.05)
    cv.paint(cv.cover(sd, aa), RUBBER, 0.5, 0.0)
    a = cv.cover(sd + 0.02, aa)
    cv.paint(a, (0, 0, 0), 0.04, 0.0)
    cv.rgb = cv.rgb + np.array((0.16, 0.17, 0.18), np.float32) * a[..., None]
    # the red band: across the face and the door, onto the sides as a parallelogram (top edge longer)
    inband = (V >= BAND[0]) & (V <= BAND[1])
    lim = 0.04 + (V - BAND[0]) * 0.57
    sd = np.maximum(np.maximum(BAND[0] - V, V - BAND[1]), np.where(on_side, D - lim, -1.0))
    cv.paint(cv.cover(sd, aa), FRONT_RED, 0.35, 0.0)
    del inband
    # the side stripe's front end on the side (slanted, bottom ahead)
    lim = 0.03 + (V - STRIPE[0]) * 0.60
    sd = np.maximum(np.maximum(STRIPE[0] - V, V - STRIPE[1]), np.where(on_side, lim - D, 1.0))
    cv.paint(cv.cover(sd, aa), MAROON, 0.55, 0.0)
    # the face's lower edge
    cv.paint(np.clip((1.02 - V) / 0.04, 0, 1).astype(np.float32) * 0.5, (0.35, 0.35, 0.36), 0.5)
    return cv


# ---------------------------------------------------------------- materials


def _load(name):
    path = os.path.join(SIGNS, name)
    return bpy.data.images.load(path) if os.path.exists(path) else None


def _emissive(m, name, img):
    mat = BD.textured_material(name, img, img)
    nt = mat.node_tree
    p = nt.nodes.get('Principled BSDF')
    tex = [n for n in nt.nodes if n.type == 'TEX_IMAGE'][0]
    nt.links.new(tex.outputs['Color'], p.inputs['Emission Color'])
    p.inputs['Emission Strength'].default_value = 1.0
    for n in [n for n in nt.nodes if n.type == 'SEPARATE_COLOR']:
        nt.nodes.remove(n)
    p.inputs['Roughness'].default_value = 0.2
    p.inputs['Metallic'].default_value = 0.0
    m.mats[name] = mat
    return mat


def add_materials(m, tex_dir):
    """plain materials plus the painted textures (written to tex_dir); returns the atlas boxes"""
    os.makedirs(tex_dir, exist_ok=True)
    m.add('tb_steel', '#cccccf', metallic=1.0, roughness=0.32)
    m.add('tb_jamb', '#c4c4c7', metallic=1.0, roughness=0.28)
    m.add('tb_roof', '#8e8f8c', metallic=0.55, roughness=0.62)
    m.add('tb_under', '#2b2a28', roughness=0.85)
    m.add('tb_sill', '#b4b6b8', metallic=0.9, roughness=0.4)
    m.add('tb_chrome', '#dcdee0', metallic=1.0, roughness=0.14)
    m.add('tb_black', '#0e0e10', roughness=0.5)
    m.add('tb_rubber', '#1a1a1c', roughness=0.8)
    m.add('tb_plate', '#a9aba9', metallic=0.2, roughness=0.6)
    m.add('tb_bellows', '#2c2c2e', roughness=0.8)
    m.add('tb_head', '#d9dbdc', metallic=0.6, roughness=0.15)
    m.add('tb_tail', '#5a0a0e', roughness=0.25)
    m.add('tb_sidelamp', '#8f1f1b', roughness=0.25)
    m.add('tb_letter', '#1a1a1c', roughness=0.4)
    # body_n1000.bellows paints with kb_ names: give them our colours under those names in this train's set
    m.mats['kb_frame'] = m.add('tb_frame', '#3a3a3c', metallic=0.3, roughness=0.5)
    m.mats['kb_bellows'] = m.mats['tb_bellows']
    halves = [paint_side(kind) for kind in ('cab', 'middle')]
    cv = Canvas(Body.SIDE_UV, halves[0].w, 2 * halves[0].h)
    cv.rgb = np.concatenate([c.rgb for c in halves], axis=0)
    cv.rough = np.concatenate([c.rough for c in halves], axis=0)
    cv.metal = np.concatenate([c.metal for c in halves], axis=0)
    img, mr = cv.image('tb_side', os.path.join(tex_dir, 'side.png'))
    m.mats['tb_side'] = BD.textured_material('tb_side', img, mr)
    cv = paint_face(Body('cab'))
    img, mr = cv.image('tb_face', os.path.join(tex_dir, 'face.png'))
    m.mats['tb_face'] = BD.textured_material('tb_face', img, mr)
    boxes = {}
    pieces = [(k, _load(k + '.png')) for k in ('led_type', 'led_dest', 'led_side')]
    if all(img is not None for _, img in pieces):
        img, b = BD._atlas('tb_led', pieces, os.path.join(tex_dir, 'led.png'))
        _emissive(m, 'tb_led', img)
        boxes.update(b)
    path = os.path.join(SIGNS, 'numbers.json')
    if os.path.exists(path):
        with open(path) as f:
            boxes['_numbers'] = json.load(f)
    return boxes


def build(part, kind):
    Body(kind).build(part)


# ---------------------------------------------------------------- the cab's fittings


def _on_face(x, y, lift):
    return (x, y, face_z(x, y) + lift)


def _quad_on_face(part, mat, x0, x1, y0, y1, uv, lift, nx=4, ny=2):
    u0, v0, u1, v1 = uv
    for j in range(ny):
        for i in range(nx):
            xa, xb = x0 + (x1 - x0) * i / nx, x0 + (x1 - x0) * (i + 1) / nx
            ya, yb = y0 + (y1 - y0) * j / ny, y0 + (y1 - y0) * (j + 1) / ny
            pts = [_on_face(xa, ya, lift), _on_face(xb, ya, lift), _on_face(xb, yb, lift), _on_face(xa, yb, lift)]

            def uv_(x, y):
                return (u0 + (u1 - u0) * (x - x0) / (x1 - x0), v0 + (v1 - v0) * (y - y0) / (y1 - y0))
            part.face_uv(pts, mat, [uv_(xa, ya), uv_(xb, ya), uv_(xb, yb), uv_(xa, yb)], out=(0, 0.2, 1))


def _rr_outline(x0, x1, y0, y1, r, seg=5):
    pts = []
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    w, h = x1 - x0, y1 - y0
    for qx, qy, a in ((1, 1, 0.0), (-1, 1, 90.0), (-1, -1, 180.0), (1, -1, 270.0)):
        ox, oy = cx + qx * (w / 2 - r), cy + qy * (h / 2 - r)
        for k in range(seg + 1):
            t = math.radians(a + 90.0 * k / seg)
            pts.append((ox + r * math.cos(t), oy + r * math.sin(t)))
    return pts


def _ring_on_face(part, mat, outer, inner, lift, base=0.0, walls=(True, True)):
    """a raised ring on the face between two outlines with the same point count (outer, inner), `lift` m proud"""
    n = len(outer)
    for k in range(n):
        a, b = outer[k], outer[(k + 1) % n]
        c, d = inner[(k + 1) % n], inner[k]
        part.face_uv([_on_face(*a, lift), _on_face(*b, lift), _on_face(*c, lift), _on_face(*d, lift)], mat, [(0, 0)] * 4,
                     smooth=False, out=(0, 0, 1))
        if walls[0]:
            part.face_uv([_on_face(*a, base), _on_face(*b, base), _on_face(*b, lift), _on_face(*a, lift)], mat, [(0, 0)] * 4,
                         smooth=True, out=_wall_out(a, b, outer))
        if walls[1]:
            part.face_uv([_on_face(*d, base), _on_face(*c, base), _on_face(*c, lift), _on_face(*d, lift)], mat, [(0, 0)] * 4,
                         smooth=True, out=tuple(-v for v in _wall_out(d, c, inner)))


def _wall_out(a, b, poly):
    cx = sum(p[0] for p in poly) / len(poly)
    cy = sum(p[1] for p in poly) / len(poly)
    mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    return (mx - cx, my - cy, 0.0)


def _fan_on_face(part, mat, outline, lift, uv=None):
    cx = sum(p[0] for p in outline) / len(outline)
    cy = sum(p[1] for p in outline) / len(outline)
    c = _on_face(cx, cy, lift)
    n = len(outline)
    for k in range(n):
        a, b = outline[k], outline[(k + 1) % n]
        part.face_uv([c, _on_face(*a, lift), _on_face(*b, lift)], mat, [(0, 0)] * 3, smooth=False, out=(0, 0.1, 1))


LAMP_UNIT = (0.665, 1.20, 1.31, 1.55)     # |x| range, y range
TAIL_LENS = (0.965, 1.165)                 # |x| (outer)
HEAD_LENS = (0.715, 0.935)                 # |x| (inner)
LENS_Y = (1.365, 1.505)
TYPE_LED = (-1.19, -0.59, 3.20, 3.37)
DEST_LED = (-0.385, 0.385, 3.29, 3.49)
FACE_NUMBER = (-1.02, 1.655, 0.39, 0.105)  # left x, bottom y, width, height


def cab_fittings(part, boxes, number):
    """displays, windscreen gaskets, gangway door surround and its gear, lamp units, steps, handles, wipers, number"""
    # windscreen rubber, standing a little proud
    for s in (-1, 1):
        x0, x1 = sorted((s * 0.48, s * 1.32))
        outer = _rr_outline(x0 - 0.004, x1 + 0.004, 1.946, 3.434, 0.134)
        inner = _rr_outline(x0 + 0.04, x1 - 0.04, 1.99, 3.39, 0.095)
        _ring_on_face(part, 'tb_rubber', outer, inner, 0.008)
    # displays
    if 'led_type' in boxes:
        _quad_on_face(part, 'tb_led', *TYPE_LED, boxes['led_type'], 0.003)
    if 'led_dest' in boxes:
        x0, x1, y0, y1 = DEST_LED
        outer = _rr_outline(x0 - 0.035, x1 + 0.035, y0 - 0.03, y1 + 0.03, 0.03)
        _fan_on_face(part, 'tb_black', outer, 0.004)
        _ring_on_face(part, 'tb_black', outer, _rr_outline(x0 - 0.012, x1 + 0.012, y0 - 0.008, y1 + 0.008, 0.012), 0.012,
                      walls=(True, False))
        _quad_on_face(part, 'tb_led', x0, x1, y0, y1, boxes['led_dest'], 0.006)
    # gangway door surround (stainless, raised)
    outer = _rr_outline(-0.445, 0.445, 0.935, 3.10, 0.10, seg=6)
    inner = _rr_outline(-0.338, 0.338, 0.975, 3.065, 0.06, seg=6)
    _ring_on_face(part, 'tb_chrome', outer, inner, 0.030)
    # hinges (viewer's left = −x), latch handle and the lock on the other edge, hooks on the surround
    for y in (1.32, 2.12, 2.82):
        part.box('tb_steel', -0.37, -0.31, y - 0.04, y + 0.04, face_z(-0.34, y) - 0.005, face_z(-0.34, y) + 0.040, bevel=0.006, segments=1)
    part.box('tb_steel', 0.24, 0.31, 1.86, 1.95, face_z(0.27, 1.9), face_z(0.27, 1.9) + 0.045, bevel=0.008, segments=1)
    part.box('tb_black', 0.25, 0.30, 1.87, 1.94, face_z(0.27, 1.9) + 0.040, face_z(0.27, 1.9) + 0.048)
    part.box('tb_steel', 0.29, 0.32, 1.52, 1.64, face_z(0.3, 1.6), face_z(0.3, 1.6) + 0.025)
    for x in (-0.30, 0.30):
        part.box('tb_steel', x - 0.02, x + 0.02, 3.00, 3.08, face_z(x, 3.0) + 0.02, face_z(x, 3.0) + 0.05)
    # the gangway plate, folded up against the door's foot, with its two hooks
    zf = face_z(0, 1.1) + 0.035
    plate = [(-0.29, 0.985), (0.29, 0.985), (0.29, 1.08), (0.17, 1.27), (-0.17, 1.27), (-0.29, 1.08)]
    _slab(part, 'tb_plate', plate, zf, zf + 0.018)
    for x in (-0.24, 0.24):
        part.cylinder('tb_steel', (x, 1.17, zf + 0.03), 0.012, 0.05, axis='z', segments=8)
        part.box('tb_steel', x - 0.015, x + 0.015, 1.14, 1.27, zf + 0.018, zf + 0.03)
    for x in (-0.11, 0.11):
        part.box('tb_steel', x - 0.02, x + 0.02, 1.00, 1.05, zf + 0.018, zf + 0.04)
    # lamp units: chrome bezel, dark well, the two lenses
    for s in (-1, 1):
        ax0, ax1 = sorted((s * LAMP_UNIT[0], s * LAMP_UNIT[1]))
        y0, y1 = LAMP_UNIT[2], LAMP_UNIT[3]
        outer = _rr_outline(ax0, ax1, y0, y1, 0.035)
        inner = _rr_outline(ax0 + 0.025, ax1 - 0.025, y0 + 0.022, y1 - 0.022, 0.015)
        _ring_on_face(part, 'tb_chrome', outer, inner, 0.022)
        _fan_on_face(part, 'tb_black', inner, 0.004)
        tx0, tx1 = sorted((s * TAIL_LENS[0], s * TAIL_LENS[1]))
        hx0, hx1 = sorted((s * HEAD_LENS[0], s * HEAD_LENS[1]))
        _fan_on_face(part, 'tb_tail', _rr_outline(tx0, tx1, *LENS_Y, 0.012), 0.010)
        # head lamp: the LED unit, a rectangular lens in a thin bezel (photos 2024-2026)
        _fan_on_face(part, 'tb_sill', _rr_outline(hx0, hx1, *LENS_Y, 0.012), 0.008)
        _fan_on_face(part, 'tb_head', _rr_outline(hx0 + 0.012, hx1 - 0.012, LENS_Y[0] + 0.012, LENS_Y[1] - 0.012, 0.008), 0.012)
    # steps under the band, grab handles, the wipers
    for s in (-1, 1):
        x0, x1 = sorted((s * 0.63, s * 1.24))
        z = face_z((x0 + x1) / 2, 1.03)
        part.box('tb_chrome', x0, x1, 1.010, 1.060, z - 0.01, z + 0.055, bevel=0.012, segments=2)
        for gx, gy in ((s * 1.08, 1.86), (s * 0.80, 1.90), (s * 1.26, 2.02)):
            z = face_z(gx, gy)
            part.cylinder('tb_chrome', (gx, gy, z + 0.035), 0.008, 0.16, axis='x', segments=8)
            for ex in (-0.07, 0.07):
                part.cylinder('tb_chrome', (gx + ex, gy, z + 0.017), 0.007, 0.036, axis='z', segments=6)
        _wiper(part, s)
    # the car number (outlines as flat dark shapes, a hair proud of the face)
    x0, y0, w, h = FACE_NUMBER
    number_geometry(part, boxes, number, lambda x, y: _on_face(x0 + x, y0 + y, 0.0012), w, (0, 0.2, 1))


def number_tris(boxes, number):
    """triangles [(x, y) * 3] of a car number's outlines (numbers.json: cap height 0.130 m), even-odd filled"""
    from mathutils import geometry
    data = boxes.get('_numbers', {}).get(number)
    if not data:
        return [], (0.0, 0.0)
    polys = [[tuple(p) for p in c] for c in data['contours']]

    def inside(pt, poly):
        x, y = pt
        hit = False
        for (xa, ya), (xb, yb) in zip(poly, poly[1:] + poly[:1]):
            if (ya > y) != (yb > y) and x < xa + (y - ya) * (xb - xa) / (yb - ya):
                hit = not hit
        return hit

    def area(poly):
        return abs(sum(xa * yb - xb * ya for (xa, ya), (xb, yb) in zip(poly, poly[1:] + poly[:1]))) / 2
    depth = [sum(inside(c[0], o) for j, o in enumerate(polys) if j != i) for i, c in enumerate(polys)]
    outlines = [i for i, d in enumerate(depth) if d % 2 == 0]
    tris = []
    for i in outlines:
        holes = [j for j, d in enumerate(depth) if d % 2 == 1 and inside(polys[j][0], polys[i])
                 and min((area(polys[k]) for k in outlines if inside(polys[j][0], polys[k])), default=0) == area(polys[i])]
        group = [polys[i]] + [polys[j] for j in holes]
        vecs = [[Vector((x, y, 0.0)) for x, y in c] for c in group]
        flat = [v for c in vecs for v in c]
        for tri in geometry.tessellate_polygon(vecs):
            tris.append([(flat[k].x, flat[k].y) for k in tri])
    return tris, tuple(data['size'])


def number_geometry(part, boxes, number, place, width, out):
    """lay a number's shapes with `place(x, y)` → game point; x scaled so the number is `width` m wide"""
    tris, size = number_tris(boxes, number)
    if not tris:
        return
    sx = width / size[0]
    for t in tris:
        part.face_uv([place(x * sx, y) for x, y in t], 'tb_letter', [(0.0, 0.0)] * 3, smooth=False, out=out)


def _slab(part, mat, poly, z0, z1):
    """a flat plate of outline `poly` (x, y) between z0 and z1"""
    n = len(poly)
    cx = sum(p[0] for p in poly) / n
    cy = sum(p[1] for p in poly) / n
    for z, d in ((z1, 1), (z0, -1)):
        for k in range(n):
            a, b = poly[k], poly[(k + 1) % n]
            part.face_uv([(cx, cy, z), (a[0], a[1], z), (b[0], b[1], z)], mat, [(0, 0)] * 3, smooth=False, out=(0, 0, d))
    for k in range(n):
        a, b = poly[k], poly[(k + 1) % n]
        part.face_uv([(a[0], a[1], z0), (b[0], b[1], z0), (b[0], b[1], z1), (a[0], a[1], z1)], mat, [(0, 0)] * 4, smooth=False,
                     out=((a[0] + b[0]) / 2 - cx, (a[1] + b[1]) / 2 - cy, 0))


def _wiper(part, s):
    """parked wiper: pivot under the windscreen, arm and blade up and inwards (photo 31612)"""
    px, py = s * 0.93, 1.80
    z0 = face_z(px, py)
    part.cylinder('tb_black', (px, py, z0 + 0.02), 0.022, 0.04, axis='z', segments=10)
    tip = (s * 0.60, 2.42)
    ln = math.hypot(tip[0] - px, tip[1] - py)
    d = ((tip[0] - px) / ln, (tip[1] - py) / ln)
    a = (px, py, z0 + 0.04)
    b = (tip[0], tip[1], face_z(*tip) + 0.035)
    part.beam('tb_black', a, b, 0.014, 0.012)
    # blade: along the arm's outer part, a little to the side
    nrm = (-d[1], d[0])
    b0 = (px + d[0] * 0.18 + nrm[0] * 0.012, py + d[1] * 0.18 + nrm[1] * 0.012)
    b1 = (tip[0] + d[0] * 0.05 + nrm[0] * 0.012, tip[1] + d[1] * 0.05 + nrm[1] * 0.012)
    part.beam('tb_black', (b0[0], b0[1], face_z(*b0) + 0.022), (b1[0], b1[1], face_z(*b1) + 0.022), 0.010, 0.022)


# ---------------------------------------------------------------- side fittings


def side_fittings(part, boxes, kind, number):
    """side displays, side lamps, the side numbers; on a cab car the crew doors' grab rails, handles and steps"""
    cab = kind == 'cab'
    for side in (-1, 1):
        x = side * HW
        zc, yc, w, h = SIDE_SIGN
        if 'led_side' in boxes:
            u0, v0, u1, v1 = boxes['led_side']
            part.box('tb_black', *sorted((x - side * 0.004, x + side * 0.010)), yc - h / 2 - 0.025, yc + h / 2 + 0.025, zc - w / 2 - 0.03, zc + w / 2 + 0.03,
                     bevel=0.006, segments=1)
            nz = 4
            xs = x + side * 0.0115
            for i in range(nz):
                za, zb = zc - w / 2 + w * i / nz, zc - w / 2 + w * (i + 1) / nz
                pts = [(xs, yc - h / 2, za), (xs, yc - h / 2, zb), (xs, yc + h / 2, zb), (xs, yc + h / 2, za)]

                def uu(z):
                    t = (z - (zc - w / 2)) / w
                    return u0 + (u1 - u0) * ((1 - t) if side > 0 else t)
                part.face_uv(pts, 'tb_led', [(uu(p[2]), v0 + (v1 - v0) * (p[1] - (yc - h / 2)) / h) for p in pts], out=(side, 0, 0))
        lz, ly, lr = SIDE_LAMP
        lz *= -side
        part.box('tb_steel', *sorted((x, x + side * 0.012)), ly - lr - 0.012, ly + lr + 0.012, lz - lr - 0.012, lz + lr + 0.012, bevel=0.006, segments=1)
        part.cylinder('tb_sidelamp', (x + side * 0.018, ly, lz), lr, 0.014, axis='x', segments=14)
        # car number beside door 1 at the window's top, 0.093 m high (photos: 36610, 31410 on the join photo)
        sc = 0.093 / 0.130
        tris, size = number_tris(boxes, number)
        if tris:
            w_, h_ = size[0] * sc, size[1] * sc
            zl = NUMBER_Z + w_ / 2 if side > 0 else NUMBER_Z - w_ / 2     # the number's left end, seen from outside
            for t in tris:
                pts = [(x + side * 0.0012, NUMBER_Y - h_ / 2 + py * sc, zl - side * px * sc) for px, py in t]
                part.face_uv(pts, 'tb_letter', [(0.0, 0.0)] * 3, smooth=False, out=(side, 0, 0))
        # door sills: a stainless step plate under each door
        for zd in DOORS:
            part.box('tb_sill', *sorted((x - side * 0.03, x + side * 0.012)), BOTTOM - 0.025, SILL + 0.003, zd - DOOR_W / 2 - 0.03, zd + DOOR_W / 2 + 0.03)
    if not cab:
        return
    cz0, cz1, cy0, cy1 = CREW_DOOR
    for side in (-1, 1):
        x = side * HW
        # a long grab rail behind the crew door and a short one ahead of it
        for zr, ya, yb in ((cz0 - 0.07, 1.25, 2.55), (cz1 + 0.07, 1.30, 1.95)):
            part.cylinder('tb_chrome', (x + side * 0.045, (ya + yb) / 2, zr), 0.012, yb - ya, axis='y', segments=10)
            for yy in (ya + 0.03, yb - 0.03):
                part.cylinder('tb_chrome', (x + side * 0.022, yy, zr), 0.008, 0.045, axis='x', segments=8)
        # handles: the latch and a key lock
        part.box('tb_chrome', *sorted((x, x + side * 0.025)), 1.86, 1.89, cz0 + 0.04, cz0 + 0.16, bevel=0.006, segments=1)
        part.box('tb_chrome', *sorted((x, x + side * 0.012)), 1.40, 1.46, cz0 + 0.05, cz0 + 0.09)
        # foot step under the crew door
        part.box('tb_sill', *sorted((x - side * 0.10, x + side * 0.03)), 0.70, 0.74, cz0 + 0.06, cz1 - 0.06, bevel=0.005, segments=1)
        for zz in (cz0 + 0.08, cz1 - 0.08):
            part.box('tb_under', *sorted((x - side * 0.08, x - side * 0.05)), 0.72, BOTTOM, zz - 0.015, zz + 0.015)
