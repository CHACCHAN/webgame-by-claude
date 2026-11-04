"""
Body shell of the JR East E235 series 0 (Yamanote Line, sustina stainless body): the wide body with its tucked-in
lower side and the gutter built into the side, the roof, the gangway ends, the flat "smartphone" cab face, the
recessed door openings with curved door leaves, and the painted textures (stainless panels with their weld lines,
windows, the line colour on the door leaves and the frieze above each door, the cab face's black glass and display
band with the dot gradient below the windscreen, the car numbers) drawn here with numpy so their edges stay sharp.

Figures (ja.wikipedia JR東日本E235系電車, read 2026-11-03): body length 19,570 (cab car) / 19,500 mm (middle car),
20,000 mm between the coupler faces; body width 2,950 mm; height 3,620 mm; four pairs of double sliding doors per side;
sides vertical above the waist with the gutter inside the profile; the doors and the frieze above them painted in the
line colour 黄緑6号 with a dot gradient fading towards the door pockets; the face's line colour fades upwards in dots.
Measured on Commons photos (list.json in the scratch folder; see LAYOUT for the side): the cab face head-on
("(JPN-Tokyo) … 23 @ Shibuya", S5A-0043, CC BY 4.0, 626 px/m from the 2.95 m width, heights from the coupler
centre): green frame 0.10 wide at the sides, 0.08 on top; black display band 3.53…3.21 with the LED display
x −0.52…+0.55, y 3.25…3.41, the tail lamps beside it (|x| 0.57…0.67, y 3.27…3.43) and the head lamps outboard
(centre |x| 0.914, y 3.36); the glass divider bar 3.21…3.12; windscreen 3.12…2.15 (|x| ≤ 1.35); wiper band to 1.97;
dots 1.97…1.44 (rows growing downwards), solid green below, the panel's lower edge at 1.33 with corners r 0.27, a
groove to the bumper's lip at 1.163, the face's lower edge at 0.924, the coupler notch x ±0.37 up to 1.063.
The doors and frieze on "JR East mohaE235-2 20150419" (Rsa, CC BY-SA 3.0): the frieze a solid green panel about as
wide as the doorway's stainless surround, its ends fading over a short distance; the leaves green right to the edge.
Our estimates: the tuck-in of the lower side (half width 1.405 at the bottom edge), the shoulder radius, the face's
plan bulge and rake, the corner radii.

Frame: the game's car frame of train_kit (x left, y up, z forward, metres). A cab car has its cab at +z.
"""
import math
import os

import bmesh
import bpy
import numpy as np
from mathutils import Vector

import train_kit as K
import body_n1000 as BD

UVPart = BD.UVPart
_sd_rr = BD._sd_round_rect
_pixels = BD._pixels

# ---------------------------------------------------------------- dimensions
HW = 1.475              # half the body width
HW_BOT = 1.405          # half width at the side's lower edge (the tuck-in)
BOTTOM = 1.02           # lower edge of the body side
TUCK_Y = 1.75           # the side is vertical above this
EAVE = 3.30             # top of the vertical side (the gutter's line)
SHOULDER = 0.25         # shoulder radius (the roof arc, r ≈ 11 m, must clear the shoulder: est.)
ROOF = 3.62             # roof at the centre line
END = 9.75              # gangway ends (19.5 m body)
FACE = 9.82             # cab face (19.57 m body: −9.75 … +9.82)
SILL = 1.155            # door sill
DOOR_TOP = 2.985        # door opening 1,300 × 1,850 (line-scan: 2.98)
DOOR_W = 1.30
DOOR_DEPTH = 0.035      # door leaves set back from the side
ROOF_LINE = 3.52        # stainless shoulder below, the roof's grey above

FRIEZE = (3.02, 3.29)           # the green panel above each door: bottom, top (line scan)
FRIEZE_W = 1.40

# cab end
CAB_R_SIDE = 0.30       # plan rounding between the face and the sides
CAB_R_TOP = 0.26        # rounding between the face and the roof
CAB_JOIN = FACE - CAB_R_SIDE - 0.02     # side sweep ends here on a cab car, the nose starts
FACE_BOTTOM = 0.924     # the face's lower edge (lower than the sides)
GREEN_Z = FACE - 0.40   # the line colour wraps round onto the side to here
END_R = 0.06            # rounding of a gangway end

# colours (sRGB 0..1)
STAINLESS = (0.70, 0.71, 0.715)
GREEN = (0.50, 0.72, 0.26)       # 黄緑6号 as it reads on photos (door #78ad63 sunlit, face #7fab69…#91b974)
BLACK_PANEL = (0.025, 0.027, 0.03)
GLASS = (0.04, 0.05, 0.055)
SIDE_GLASS = (0.10, 0.115, 0.12)
GASKET = (0.06, 0.06, 0.065)
ROOF_GREY = '#9c9a95'

# ---------------------------------------------------------------- the section


def _roof_geometry():
    r = SHOULDER
    a = HW - r
    b = EAVE - ROOF
    rr = (r * r - a * a - b * b) / (2 * b + 2 * r)
    theta = math.atan2(EAVE - (ROOF - rr), a)
    return rr, theta


def _tuck_x(y):
    """half width of the side at y (the tuck-in below TUCK_Y: a circular arc tangent to the vertical side)"""
    if y >= TUCK_Y:
        return HW
    a = HW - HW_BOT
    b = TUCK_Y - BOTTOM
    R = (a * a + b * b) / (2 * a)
    return HW - R + math.sqrt(max(R * R - (TUCK_Y - y) ** 2, 0.0))


def side_x(y):
    """the body side's half width at height y (tuck-in, vertical side, then the shoulder)"""
    if y <= EAVE:
        return _tuck_x(y)
    dy = min(y - EAVE, SHOULDER)
    return HW - SHOULDER + math.sqrt(SHOULDER * SHOULDER - dy * dy)


def half_profile(bottom=BOTTOM):
    """[(x, y, nx, ny)] from the bottom of the left side (+x) up to the roof's centre line"""
    a = HW - HW_BOT
    b = TUCK_Y - BOTTOM
    R = (a * a + b * b) / (2 * a)
    pts = []
    ys = {SILL, DOOR_TOP, EAVE, TUCK_Y, WIN_Y[0], WIN_Y[1], FRIEZE[0], FRIEZE[1]}
    # the face's groove and bumper want fine rows low down
    for y in (1.10, 1.163, 1.20, 1.245, 1.29, 1.335, 1.38, 1.44, 1.52, 1.62):
        ys.add(y)
    for y in np.arange(1.80, EAVE - 0.02, 0.14):
        ys.add(round(float(y), 4))
    if bottom < BOTTOM:
        for y in np.linspace(bottom, BOTTOM, 4)[:-1]:
            ys.add(round(float(y), 4))
    ys.add(BOTTOM)
    ys = sorted(y for y in ys if bottom - 1e-9 <= y <= EAVE + 1e-9)
    clean = []
    for y in ys:
        if not clean or y - clean[-1] > 0.012:
            clean.append(y)
    for y in clean:
        x = _tuck_x(y)
        if y < TUCK_Y:
            nx, ny = (x - (HW - R)) / R, -(TUCK_Y - y) / R
            n = math.hypot(nx, ny)
            nx, ny = nx / n, ny / n
        else:
            nx, ny = 1.0, 0.0
        pts.append((x, y, nx, ny))
    r = SHOULDER
    rr, theta = _roof_geometry()
    ns = 7
    for k in range(1, ns + 1):
        t = theta * k / ns
        pts.append((HW - r + r * math.cos(t), EAVE + r * math.sin(t), math.cos(t), math.sin(t)))
    nr = 8
    for k in range(1, nr + 1):
        a_ = theta + (math.pi / 2 - theta) * k / nr
        x = rr * math.cos(a_)
        pts.append((0.0 if k == nr else x, ROOF - rr + rr * math.sin(a_), math.cos(a_), math.sin(a_)))
    return pts


def ring(bottom=BOTTOM):
    half = half_profile(bottom)
    right = [(-x, y, -nx, ny) for x, y, nx, ny in half]
    return right + list(reversed(half[:-1]))


# ---------------------------------------------------------------- the cab face as a height field

FACE_PROFILE = [      # centre line (y, z − FACE)
    (FACE_BOTTOM, -0.035), (0.95, 0.010), (1.00, 0.028), (1.10, 0.032), (1.163, 0.030),
    (1.40, 0.0), (2.15, -0.012), (3.12, -0.040), (3.53, -0.060), (3.70, -0.075)]
_ZC = BD._pchip(FACE_PROFILE)
PANEL_X = 1.39          # the black panel's half width; its lower corners r 0.27 round up from y 1.245 (groove)
GROOVE_Y = 1.245
GROOVE_R = 0.27
BULGE = 0.035           # plan bulge of the face's centre over its edges


def _groove_dist(x, y):
    """distance from (x, y) to the groove's line: the panel's bottom edge with its rounded corners"""
    xc = PANEL_X - GROOVE_R
    ax = abs(x)
    if ax <= xc:
        return y - GROOVE_Y, 1.0
    cy = GROOVE_Y + GROOVE_R
    d = math.hypot(ax - xc, y - cy)
    if y > cy:
        return (PANEL_X - ax), 0.0 if ax < PANEL_X else 1.0
    return GROOVE_R - d, 1.0


def face_z(x, y):
    """the cab face before its rounding: profile, bulge, and the groove along the panel's bottom edge"""
    z = FACE + _ZC(y) - BULGE * (x / HW) ** 2
    # the groove: below the panel the surface steps back 0.025 and comes forward again at the bumper's lip
    s, w = _groove_dist(x, y)
    if w > 0 and -0.09 < s < 0.10:
        if s >= 0:      # above the line: the panel's underside curves back into the groove
            z -= 0.028 * math.exp(-(s / 0.035) ** 2)
        else:           # below: the lip comes forward sharply
            z -= 0.028 * math.exp(-(s / 0.022) ** 2)
    return z


def corner_radius(y):
    return CAB_R_SIDE + (CAB_R_TOP - CAB_R_SIDE) * K.smoothstep(3.25, 3.50, y)


class Nose(BD.Nose):
    """the Keikyu module's nose (columns through a quarter-round into a height-field face) on our section"""

    def __init__(self, steps=9, across=34):
        self.ring = ring(FACE_BOTTOM)
        n = len(self.ring)
        self.half = (n + 1) // 2
        self.steps = steps
        self.cols = []
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


def _quad_out(p, centre_z):
    return Vector(p) - Vector((0.0, 2.0, max(-9.0, min(9.0, centre_z))))


# ---------------------------------------------------------------- the shell


class Body:
    """one car's shell; kind 'cab' (cab at +z) or 'middle'"""

    SIDE_UV = (-9.90, 9.90, 0.90, 3.56)      # u = z, v = y (each side has its own half of the image)
    FACE_UV = (-2.10, 2.10, 0.88, 3.80)      # u = arc length from the centre line, v = y
    BAY_UV = (-0.80, 0.80, 1.10, 3.36)       # door bay: u = z − door centre, v = y

    def __init__(self, kind, name=None):
        self.kind = kind
        self.side_mat = 'e_side_' + (name or ('car0' if kind == 'cab' else 'car1'))
        self.cab = kind == 'cab'
        self.ring = ring()
        self.n = len(self.ring)
        self.half = (self.n + 1) // 2
        self.nose = Nose() if self.cab else None
        self.doors = DOORS_CAB if self.cab else DOORS_MID

    # uv helpers: the left side (+x) uses the image's top half, mirrored in u so that lettering reads from outside
    def side_uv(self, z, y, side):
        u0, u1, v0, v1 = self.SIDE_UV
        u = (z - u0) / (u1 - u0)
        v = (y - v0) / (v1 - v0)
        if side > 0:
            return (1.0 - u, 0.5 + 0.5 * v)
        return (u, 0.5 * v)

    def bay_uv(self, dz, y):
        u0, u1, v0, v1 = self.BAY_UV
        return ((dz - u0) / (u1 - u0), (y - v0) / (v1 - v0))

    def face_uv(self, u, y):
        u0, u1, v0, v1 = self.FACE_UV
        return ((u - u0) / (u1 - u0), (y - v0) / (v1 - v0))

    def bay_of(self, za, zb):
        """the door whose frieze panel holds the span za…zb, or None"""
        for zd in self.doors:
            if za >= zd - FRIEZE_W / 2 - 1e-6 and zb <= zd + FRIEZE_W / 2 + 1e-6:
                return zd
        return None

    def zone(self, y, ny):
        if ny > 0.5 and y > ROOF_LINE:
            return 'e_roof'
        return 'e_stain'

    def stations(self):
        zs = {-(END - END_R), (END - END_R) if not self.cab else CAB_JOIN}
        for zd in self.doors:
            for dz in (DOOR_W / 2, FRIEZE_W / 2):
                zs.add(zd - dz)
                zs.add(zd + dz)
        if self.cab:
            zs.add(GREEN_Z)
        out = sorted(zs)
        fine = []
        for a, b in zip(out[:-1], out[1:]):
            k = max(1, int(math.ceil((b - a) / 1.6)))
            fine += [a + (b - a) * i / k for i in range(k)]
        return fine + [out[-1]]

    def in_door(self, za, zb, ya, yb):
        if ya < SILL - 1e-6 or yb > DOOR_TOP + 1e-6:
            return False
        for zd in self.doors:
            if za >= zd - DOOR_W / 2 - 1e-6 and zb <= zd + DOOR_W / 2 + 1e-6:
                return True
        return False

    def wall_face(self, part, pts, cy, nx, ny, out, side):
        """a face of the side sweep: the side texture, a door bay's frieze, or plain stainless / roof"""
        za = min(p[2] for p in pts)
        zb = max(p[2] for p in pts)
        if abs(nx) > 0.55 and cy < self.SIDE_UV[3] - 0.01:
            zd = self.bay_of(za, zb)
            if zd is not None and cy > DOOR_TOP and cy < self.BAY_UV[3]:
                part.face_uv(pts, 'e_bay', [self.bay_uv(p[2] - zd, p[1]) for p in pts], out=out)
            else:
                part.face_uv(pts, self.side_mat, [self.side_uv(p[2], p[1], side) for p in pts], out=out)
        else:
            part.face_uv(pts, self.zone(cy, ny), [(0, 0)] * len(pts), out=out)

    def build(self, part):
        ring = self.ring
        zs = self.stations()
        for za, zb in zip(zs[:-1], zs[1:]):
            for i in range(self.n - 1):
                (xa, ya, nxa, nya), (xb, yb, nxb, nyb) = ring[i], ring[i + 1]
                side = 1 if xa + xb > 0 else -1
                if abs(nxa) > 0.5 and abs(nxb) > 0.5 and self.in_door(za, zb, min(ya, yb), max(ya, yb)):
                    continue
                pts = [(xa, ya, za), (xb, yb, za), (xb, yb, zb), (xa, ya, zb)]
                out = _quad_out((0.5 * (xa + xb), (ya + yb) / 2, 0.5 * (za + zb)), 0.5 * (za + zb))
                self.wall_face(part, pts, (ya + yb) / 2, (nxa + nxb) / 2, (nya + nyb) / 2, out, side)
        # underside
        part.face_uv([(-HW_BOT, BOTTOM, zs[0]), (HW_BOT, BOTTOM, zs[0]), (HW_BOT, BOTTOM, zs[-1]), (-HW_BOT, BOTTOM, zs[-1])],
                     'e_under', [(0, 0)] * 4, smooth=False, out=(0, -1, 0))
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
                side = 1 if c.x > 0 else -1
                if abs(nx) > 0.55 and cy < self.SIDE_UV[3] - 0.01 and k == 0:
                    part.face_uv(pts, self.side_mat, [self.side_uv(p[2], p[1], side) for p in pts], out=out)
                else:
                    part.face_uv(pts, self.zone(cy, ny), [(0, 0)] * 4, out=out)
        for i in range(self.half - 1):
            a, b = cols[i][-1], cols[self.n - 1 - i][-1]
            c, d = cols[i + 1][-1], cols[self.n - 2 - i][-1]
            pts = [a, b, d, c] if c != d else [a, b, c]
            part.face_uv(pts, 'e_end', [(0, 0)] * len(pts), smooth=False, out=(0, 0, sign))
        b0, b1 = cols[0], cols[self.n - 1]
        for k in range(steps):
            pts = [b0[k], b1[k], b1[k + 1], b0[k + 1]]
            part.face_uv(pts, 'e_under', [(0, 0)] * 4, smooth=False, out=(0, -1, 0))

    def cab_end(self, part):
        nose = self.nose
        nring = nose.ring
        n = len(nring)
        # side wall from the sweep's end to where each column starts (the nose ring reaches lower than the sides)
        for i in range(n - 1):
            (xa, ya, nxa, nya), (xb, yb, nxb, nyb) = nring[i], nring[i + 1]
            a, b = nose.cols[i][0], nose.cols[i + 1][0]
            side = 1 if xa + xb > 0 else -1
            z0 = CAB_JOIN if min(ya, yb) >= BOTTOM - 1e-6 else GREEN_Z
            pts = [(xa, ya, z0), (xb, yb, z0), b, a]
            out = _quad_out((0.5 * (xa + xb), (ya + yb) / 2, CAB_JOIN + 0.3), CAB_JOIN + 0.3)
            if z0 < CAB_JOIN:
                # the green apron below the sides' lower edge: its own rear wall at GREEN_Z
                part.face_uv(pts, 'e_face', [self.face_uv(-side * (2.0), p[1]) for p in pts], out=out)
                continue
            self.wall_face(part, pts, (ya + yb) / 2, (nxa + nxb) / 2, (nya + nyb) / 2, out, side)
        # the apron's back walls and underside behind the columns' lowest row
        for side in (-1, 1):
            ys = [p[1] for p in nring if p[1] <= BOTTOM + 1e-6]
            x0 = side * HW_BOT
            pts = [(side * _tuck_x(ys[0]), ys[0], GREEN_Z), (side * _tuck_x(BOTTOM), BOTTOM, GREEN_Z),
                   (side * (HW_BOT - 0.12), BOTTOM, GREEN_Z), (side * (HW_BOT - 0.12), ys[0], GREEN_Z)]
            part.face_uv(pts, 'e_under', [(0, 0)] * 4, smooth=False, out=(0, 0, -1))
            part.face_uv([(side * _tuck_x(ys[0]), ys[0], GREEN_Z), (side * (HW_BOT - 0.12), ys[0], GREEN_Z),
                          (side * (HW_BOT - 0.12), ys[0], CAB_JOIN), (side * _tuck_x(ys[0]), ys[0], CAB_JOIN)],
                         'e_under', [(0, 0)] * 4, smooth=False, out=(0, -1, 0))
            del x0
        # texture coordinates of the nose (as the Keikyu module): u along each row, v = height
        u_col = [None] * n
        u_row = [None] * nose.half
        for i in range(nose.half):
            pts = nose.full_row(i)
            u = nose.row_u(pts)
            k = nose.steps + 1
            u_col[i] = list(u[:k])
            if i != n - 1 - i:
                u_col[n - 1 - i] = list(reversed(u[len(u) - k:]))
            mid = nose.rows[i]
            u_row[i] = [u[k - 1]] + list(u[k:len(u) - k]) + [u[len(u) - k]] if len(mid) > 1 else [0.0]
        self.u_col, self.u_row = u_col, u_row

        def mat_for(pts):
            cy = sum(p[1] for p in pts) / len(pts)
            return 'e_face' if cy < self.FACE_UV[3] - 0.02 else 'e_roof'

        out_c = Vector((0.0, 2.0, FACE - 2.5))
        for i in range(n - 1):
            for k in range(nose.steps):
                pts = [nose.cols[i][k], nose.cols[i + 1][k], nose.cols[i + 1][k + 1], nose.cols[i][k + 1]]
                uvs = [(u_col[i][k], pts[0][1]), (u_col[i + 1][k], pts[1][1]), (u_col[i + 1][k + 1], pts[2][1]), (u_col[i][k + 1], pts[3][1])]
                m = mat_for(pts)
                c = Vector([sum(p[j] for p in pts) / 4 for j in range(3)])
                part.face_uv(pts, m, [self.face_uv(u, v) for u, v in uvs] if m == 'e_face' else [(0, 0)] * 4, out=c - out_c)
        for i in range(nose.half - 1):
            ra, rb = nose.rows[i], nose.rows[i + 1]
            ua, ub = u_row[i], u_row[i + 1]
            for k in range(len(ra) - 1):
                if len(rb) > 1:
                    pts = [ra[k], ra[k + 1], rb[k + 1], rb[k]]
                    uvs = [(ua[k], ra[k][1]), (ua[k + 1], ra[k + 1][1]), (ub[k + 1], rb[k + 1][1]), (ub[k], rb[k][1])]
                else:
                    pts = [ra[k], ra[k + 1], rb[0]]
                    uvs = [(ua[k], ra[k][1]), (ua[k + 1], ra[k + 1][1]), (0.0, rb[0][1])]
                m = mat_for(pts)
                part.face_uv(pts, m, [self.face_uv(u, v) for u, v in uvs] if m == 'e_face' else [(0, 0)] * len(pts), out=(0, 0.3, 1))
        # underside of the nose: a fan under the lowest row
        bottom = nose.full_row(0)
        yb = bottom[0][1]
        c = (0.0, yb, GREEN_Z)
        prev = (nring[0][0], yb, GREEN_Z)
        for p in bottom + [(nring[n - 1][0], yb, GREEN_Z)]:
            q = (p[0], yb, p[2])
            if Vector(q) != Vector(prev):
                part.face_uv([c, prev, q], 'e_under', [(0, 0)] * 3, smooth=False, out=(0, -1, 0))
            prev = q

    def door(self, part, zd, side):
        """a door opening on side +1 (left) or −1: jambs into the side, the leaves set back (they follow the tuck)"""
        za, zb = zd - DOOR_W / 2, zd + DOOR_W / 2
        prof = [(x, y) for x, y, nx, ny in self.ring[self.half - 1:] if nx > 0.5 and SILL - 1e-6 <= y <= DOOR_TOP + 1e-6]
        prof.sort(key=lambda p: p[1])
        sx = side

        def P(x, y, z, inset=0.0):
            return (sx * (x - inset), y, z)

        for zj, facing in ((za, 1), (zb, -1)):
            for (xa, ya), (xb, yb) in zip(prof[:-1], prof[1:]):
                part.face_uv([P(xa, ya, zj), P(xb, yb, zj), P(xb, yb, zj, DOOR_DEPTH), P(xa, ya, zj, DOOR_DEPTH)], 'e_stain',
                             [(0, 0)] * 4, smooth=False, out=(0, 0, facing))
        xt, xs = prof[-1][0], prof[0][0]
        part.face_uv([P(xt, DOOR_TOP, za), P(xt, DOOR_TOP, zb), P(xt, DOOR_TOP, zb, DOOR_DEPTH), P(xt, DOOR_TOP, za, DOOR_DEPTH)],
                     'e_stain', [(0, 0)] * 4, smooth=False, out=(0, -1, 0))
        part.face_uv([P(xs, SILL, za), P(xs, SILL, zb), P(xs, SILL, zb, DOOR_DEPTH), P(xs, SILL, za, DOOR_DEPTH)],
                     'e_sill', [(0, 0)] * 4, smooth=False, out=(0, 1, 0))
        # the leaves, split at the centre seam
        for (xa, ya), (xb, yb) in zip(prof[:-1], prof[1:]):
            for z0, z1 in ((za, zd), (zd, zb)):
                pts = [P(xa, ya, z0, DOOR_DEPTH), P(xb, yb, z0, DOOR_DEPTH), P(xb, yb, z1, DOOR_DEPTH), P(xa, ya, z1, DOOR_DEPTH)]
                part.face_uv(pts, 'e_bay', [self.bay_uv(p[2] - zd, p[1]) for p in pts], smooth=True, out=(sx, 0, 0))


def bellows(part, z_end, sign, half_gap=0.25, w=1.10, y0=1.16, y1=3.15, folds=4, depth=0.035):
    """the car's half of the gangway bellows: a folded rubber box from the end wall to the middle of the gap"""
    zf = z_end + sign * 0.012
    part.box('e_frame', -w / 2 - 0.05, w / 2 + 0.05, y0 - 0.05, y1 + 0.05, min(z_end, zf), max(z_end, zf))
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
            part.face_uv(pts, 'e_bellows', [(0, 0)] * 4, smooth=False, out=(c.x, c.y - (y0 + y1) / 2, 0))
    zl = zs[-1]
    part.box('e_frame', -w / 2 - depth, w / 2 + depth, y0 - depth, y1 + depth, min(zl, zl - sign * 0.02), max(zl, zl - sign * 0.02))


def build(part, kind, name=None):
    body = Body(kind, name)
    body.build(part)
    return body


# ---------------------------------------------------------------- side layout (line-scan photo "dllu 02", 86.4 px/m
# along the car from the cab car's 19.57 m, heights from the door's 1,850 mm at 93.2 px/m, the sill at 1.155)
# windows: (z centre, width, mullion: fraction of the width from the +z end on the left side, or None)
WINDOWS_MID = ((-9.20, 0.70, None), (-4.93, 2.05, 0.36), (0.0, 2.05, 0.36), (4.93, 2.05, 0.36), (9.20, 0.70, None))
WINDOWS_CAB = ((-9.20, 0.71, None), (-4.93, 2.05, 0.36), (0.02, 2.07, 0.36), (4.27, 0.73, None))
DOORS_CAB = (-7.39, -2.46, 2.47, 6.08)
DOORS_MID = (-7.395, -2.465, 2.465, 7.395)
WIN_Y = (1.915, 2.865)          # glass of the side windows (the bright frame round it adds 0.025)
WIN_R = 0.12
CAB_WINDOW = (8.565, 9.375, 2.36, 2.95)   # z0, z1, y0, y1 (two panes)
CREW_DOOR = (7.737, 8.374, 1.18, 2.96)
CREW_WINDOW = (7.96, 8.30, 2.10, 2.95)
WAIST = 1.83                    # the panel joint along the side at the windows' foot
SIDE_SIGN = (0.0, 3.085, 0.54, 0.13)      # side destination display: z, y, width, height (centre of the car)
SIDE_LAMP = (-0.70, 3.13)                 # small indicator lamp on the frieze
SPEAKERS = (3.105, 0.23, 0.15)            # boxes on the frieze over the other window bays: y, width, height
NUMBER_Y = (1.20, 1.29)                   # car number lettering, centred at z ≈ 0


def _dots(cv, U, V, t, pitch=0.022, colour=GREEN, rough=0.35, metal=0.0, aa=None):
    """a dot gradient: squares on a staggered grid, their area following coverage t (0 = none, 1 = solid)"""
    j = np.floor(V / pitch)
    off = (j % 2) * 0.5 * pitch
    i = np.floor((U - off) / pitch)
    cu = (i + 0.5) * pitch + off
    cvv = (j + 0.5) * pitch
    tc = np.clip(t(cu, cvv), 0.0, 1.0)
    h = 0.5 * pitch * np.sqrt(tc) * 1.02
    sd = np.maximum(np.abs(U - cu), np.abs(V - cvv)) - h
    a = cv.cover(sd, aa)
    a = np.where(tc >= 0.999, 1.0, a)
    cv.paint(a, colour, rough, metal)


def _halftone(U, V, t, a, aa):
    """green coverage of the face's two-phase halftone (photo 612879 close up): a checkerboard of a × a cells; green
    squares grow on one set of cells up to the full checkerboard at t = 0.5, then black squares shrink on the other"""
    c = np.floor(U / a)
    j = np.floor(V / a)
    cx, cy = (c + 0.5) * a, (j + 0.5) * a
    tc = np.clip(t(cx, cy), 0.0, 1.0)
    on_a = ((c + j) % 2) == 0
    d = np.maximum(np.abs(U - cx), np.abs(V - cy))
    ha = 0.5 * a * np.sqrt(2 * np.minimum(tc, 0.5))
    hb = 0.5 * a * np.sqrt(2 * (1 - np.maximum(tc, 0.5)))
    r = 0.2 * np.where(on_a, ha, hb)          # slightly rounded corners
    dx, dy = np.abs(U - cx), np.abs(V - cy)
    sd_a = np.hypot(np.maximum(dx - ha + r, 0), np.maximum(dy - ha + r, 0)) - r
    sd_b = np.hypot(np.maximum(dx - hb + r, 0), np.maximum(dy - hb + r, 0)) - r
    k = 1.0 / np.maximum(aa, 1e-6)
    green_a = np.where(ha >= 0.5 * a * 0.999, 1.0, np.clip(0.5 - sd_a * k, 0, 1))
    black_b = np.where(hb >= 0.5 * a * 0.999, 1.0, np.clip(0.5 - sd_b * k, 0, 1))
    del d
    return np.where(on_a, green_a, 1.0 - black_b)


class Canvas(BD.Canvas):
    """the Keikyu module's painting canvas with a metallic channel"""

    def __init__(self, uv_box, w, h):
        super().__init__(uv_box, w, h)
        self.metal = np.zeros((h, w), np.float32)

    def paint(self, alpha, colour, rough=None, metal=None):
        super().paint(alpha, colour, rough)
        if metal is not None:
            self.metal = self.metal * (1 - alpha) + metal * alpha

    def fill(self, colour, rough, metal=0.0):
        super().fill(colour, rough)
        self.metal[:] = metal

    def image(self, name, path):
        img, mr = super().image(name, path)
        a = np.ones((self.h, self.w, 4), np.float32)
        a[..., 1] = np.clip(self.rough, 0, 1)
        a[..., 2] = np.clip(self.metal, 0, 1)
        mr.pixels.foreach_set(a.ravel())
        mr.save()
        return img, mr


def _stack(top, bottom, name, path):
    """two canvases one above the other (bottom half: right side, top half: left side) as one texture pair"""
    cv = Canvas((0, 1, 0, 1), top.w, top.h + bottom.h)
    cv.rgb = np.concatenate([bottom.rgb, top.rgb], axis=0)
    cv.rough = np.concatenate([bottom.rough, top.rough], axis=0)
    cv.metal = np.concatenate([bottom.metal, top.metal], axis=0)
    return cv.image(name, path)


def _sample_text(path):
    """a lettering image (black on white) as a coverage array, row 0 at the bottom"""
    img = bpy.data.images.load(path)
    a = _pixels(img)[..., :3].mean(axis=2)
    bpy.data.images.remove(img)
    return 1.0 - a


def paint_side(kind, side, number_path=None, w=4096, h=560):
    """one side of a car (u = z, v = y); side +1 = left (+x): drawn in z and flipped to read from outside later"""
    cv = Canvas(Body.SIDE_UV, w, h)
    U, V = cv.U, cv.V
    cab = kind == 'cab'
    doors = DOORS_CAB if cab else DOORS_MID
    cv.fill(STAINLESS, 0.30, 1.0)
    # the lower panel reflects a little differently, the shoulder above the gutter is rolled sheet
    cv.paint((V < WAIST).astype(np.float32), (0.735, 0.74, 0.745), 0.26, 1.0)
    cv.paint((V > EAVE).astype(np.float32), (0.66, 0.665, 0.67), 0.36, 1.0)
    # weld lines / panel joints: the waist, the frieze's foot, the gutter, the lower edge
    for yl, wl, col in ((WAIST, 0.004, (0.42, 0.43, 0.44)), (FRIEZE[0] - 0.01, 0.003, (0.48, 0.49, 0.50)),
                        (EAVE, 0.006, (0.30, 0.31, 0.32)), (BOTTOM + 0.012, 0.004, (0.45, 0.46, 0.47))):
        cv.paint(cv.cover(np.abs(V - yl) - wl / 2), col, 0.45, 1.0)
    # door openings: a bright frame round each (the stainless trim of the opening)
    for zd in doors:
        sd = _sd_rr(U, V, zd, (SILL + DOOR_TOP) / 2 + 0.01, DOOR_W + 0.09, DOOR_TOP - SILL + 0.06, 0.07)
        cv.paint(cv.cover(sd), (0.80, 0.81, 0.82), 0.18, 1.0)
        cv.paint(cv.cover(np.abs(sd) - 0.002), (0.35, 0.36, 0.37), 0.4, 1.0)

    def window(zc, ww, mullion, y0=WIN_Y[0], y1=WIN_Y[1], r=WIN_R, frame=0.025):
        cy, hh = (y0 + y1) / 2, y1 - y0
        sd = _sd_rr(U, V, zc, cy, ww + 2 * frame, hh + 2 * frame, r + frame)
        cv.paint(cv.cover(sd), (0.84, 0.85, 0.86), 0.16, 1.0)          # bright frame
        cv.paint(cv.cover(np.abs(sd) - 0.0015), (0.40, 0.41, 0.42), 0.4, 1.0)
        sd = _sd_rr(U, V, zc, cy, ww + 0.008, hh + 0.008, r + 0.004)
        cv.paint(cv.cover(sd), GASKET, 0.5, 0.0)
        sd = _sd_rr(U, V, zc, cy, ww, hh, r)
        # tinted glass: the saloon dim behind it, darker towards the top (ceiling), seats lighter low down
        g = np.array(SIDE_GLASS, np.float32)[None, None, :] * (1.0 - 0.35 * np.clip((V - cy) / hh + 0.5, 0, 1))[..., None]
        a = cv.cover(sd)[..., None]
        cv.rgb = cv.rgb * (1 - a) + g * a
        cv.rough = cv.rough * (1 - a[..., 0]) + 0.05 * a[..., 0]
        cv.metal = cv.metal * (1 - a[..., 0])
        if mullion is not None:
            f = mullion if side > 0 else 1.0 - mullion
            zm = zc + ww / 2 - f * ww
            sdm = np.maximum(np.abs(U - zm) - 0.014, sd)
            cv.paint(cv.cover(sdm), (0.05, 0.05, 0.055), 0.5, 0.2)

    for zc, ww, mul in (WINDOWS_CAB if cab else WINDOWS_MID):
        window(zc, ww, mul)
    if cab:
        z0, z1, y0, y1 = CAB_WINDOW
        sd = _sd_rr(U, V, (z0 + z1) / 2, (y0 + y1) / 2, z1 - z0 + 0.03, y1 - y0 + 0.03, 0.06)
        cv.paint(cv.cover(sd), (0.03, 0.03, 0.035), 0.5, 0.0)
        sd = _sd_rr(U, V, (z0 + z1) / 2, (y0 + y1) / 2, z1 - z0, y1 - y0, 0.05)
        cv.paint(cv.cover(sd), GLASS, 0.05, 0.0)
        zm = z0 + 0.42 * (z1 - z0) if side < 0 else z1 - 0.42 * (z1 - z0)
        cv.paint(cv.cover(np.maximum(np.abs(U - zm) - 0.012, sd)), (0.03, 0.03, 0.035), 0.5, 0.0)
        # crew door: its outline, the window, the step plate at the foot
        z0, z1, y0, y1 = CREW_DOOR
        sd = _sd_rr(U, V, (z0 + z1) / 2, (y0 + y1) / 2, z1 - z0, y1 - y0, 0.04)
        cv.paint(cv.cover(np.abs(sd) - 0.005), (0.10, 0.10, 0.11), 0.5, 0.3)
        z0, z1, y0, y1 = CREW_WINDOW
        sd = _sd_rr(U, V, (z0 + z1) / 2, (y0 + y1) / 2, z1 - z0, y1 - y0, 0.03)
        cv.paint(cv.cover(sd + 0.012), (0.05, 0.05, 0.055), 0.5, 0.0)
        cv.paint(cv.cover(sd), GLASS, 0.05, 0.0)
        cz = (CREW_DOOR[0] + CREW_DOOR[1]) / 2
        for yy in (1.27, 1.30, 1.33):
            cv.paint(cv.cover(np.maximum(np.abs(U - cz) - 0.10, np.abs(V - yy) - 0.006)), (0.25, 0.25, 0.26), 0.5, 1.0)
        # the line colour wraps round the cab corner onto the side
        cv.paint(cv.cover(GREEN_Z - U), GREEN, 0.32, 0.0)
    # car number below the big window at the car's centre (z ≈ 0; on the left side it reads from +z to −z)
    if number_path:
        cov = _sample_text(number_path)
        th, tw = cov.shape
        hgt = NUMBER_Y[1] - NUMBER_Y[0]
        wid = hgt * tw / th
        z0 = -wid / 2 + 0.02
        # text runs with the reader: on the right side (−x) from −z to +z, on the left from +z to −z
        X = (U - z0) / wid if side < 0 else ((z0 + wid) - U) / wid
        Y = (V - NUMBER_Y[0]) / hgt
        inside = (X >= 0) & (X < 1) & (Y >= 0) & (Y < 1)
        ix = np.clip((X * tw).astype(int), 0, tw - 1)
        iy = np.clip((Y * th).astype(int), 0, th - 1)
        a = np.where(inside, cov[iy, ix], 0.0).astype(np.float32)
        cv.paint(a, (0.03, 0.03, 0.035), 0.5, 0.0)
    # the small panel low in each window bay (a socket cover)
    for zc, ww, mul in (WINDOWS_CAB if cab else WINDOWS_MID):
        if ww > 1.0:
            zp = zc + (0.35 if side < 0 else -0.35)
            sd = _sd_rr(U, V, zp, 1.345, 0.20, 0.23, 0.015)
            cv.paint(cv.cover(np.abs(sd) - 0.002), (0.38, 0.39, 0.40), 0.45, 1.0)
    if side > 0:
        # the left side is seen with +z to the left: flip it so u runs against z (see Body.side_uv)
        cv.rgb = cv.rgb[:, ::-1].copy()
        cv.rough = cv.rough[:, ::-1].copy()
        cv.metal = cv.metal[:, ::-1].copy()
    return cv


def paint_bay(w=1024, h=1440):
    """a door bay (u = z − door centre, v = y): the green leaves with their windows, the green frieze panel above"""
    cv = Canvas(Body.BAY_UV, w, h)
    U, V = cv.U, cv.V
    cv.fill(STAINLESS, 0.30, 1.0)
    # frieze panel: solid in the middle, dots thinning towards both ends
    fw = FRIEZE_W / 2

    def t_frieze(u, v):
        inside = (v > FRIEZE[0]) & (v < FRIEZE[1])
        return np.where(inside, np.clip((fw - np.abs(u)) / 0.12, 0, 1) ** 1.2, 0.0)
    _dots(cv, U, V, t_frieze, pitch=0.012)
    cv.paint(cv.cover(np.abs(V - (FRIEZE[0] - 0.01)) - 0.0015), (0.48, 0.49, 0.50), 0.45, 1.0)
    # door leaves: green, the dots thinning towards the pockets (outer edges)
    hw = DOOR_W / 2

    def t_leaf(u, v):
        inside = (v > SILL) & (v < DOOR_TOP) & (np.abs(u) < hw)
        return np.where(inside, np.clip((hw - np.abs(u)) / 0.07, 0, 1) ** 0.8, 0.0)
    _dots(cv, U, V, t_leaf, pitch=0.010)
    in_leaf = cv.cover(np.maximum(np.abs(U) - hw, np.maximum(SILL - V, V - DOOR_TOP)))
    cv.rough = cv.rough * (1 - in_leaf) + 0.32 * in_leaf
    # the opening's rounded top corners (the trim shows there)
    sd = _sd_rr(U, V, 0.0, (SILL + DOOR_TOP) / 2 - 0.05, DOOR_W, DOOR_TOP - SILL + 0.1, 0.075)
    cv.paint(cv.cover(-sd) * (V > DOOR_TOP - 0.1) * (V < DOOR_TOP + 0.002), (0.80, 0.81, 0.82), 0.18, 1.0)
    # door windows, gaskets, the centre seam and the edge rubbers
    for s in (-1, 1):
        zc = s * DOOR_W / 4
        sd = _sd_rr(U, V, zc, (1.94 + 2.85) / 2, 0.39, 2.85 - 1.94, 0.04)
        cv.paint(cv.cover(sd - 0.012), GASKET, 0.5, 0.0)
        g = np.array(SIDE_GLASS, np.float32)[None, None, :] * (1.0 - 0.3 * np.clip((V - 1.94) / 0.91, 0, 1))[..., None]
        a = cv.cover(sd)[..., None]
        cv.rgb = cv.rgb * (1 - a) + g * a
        cv.rough = cv.rough * (1 - a[..., 0]) + 0.05 * a[..., 0]
        cv.metal = cv.metal * (1 - a[..., 0])
    for zl, wl in ((0.0, 0.022), (-hw + 0.006, 0.012), (hw - 0.006, 0.012)):
        sd = np.maximum(np.abs(U - zl) - wl / 2, np.maximum(SILL - V, V - DOOR_TOP))
        cv.paint(cv.cover(sd), (0.05, 0.05, 0.055), 0.6, 0.0)
    # the leaves' foot: a darker kick strip
    sd = np.maximum(np.abs(U) - hw, np.abs(V - (SILL + 0.012)) - 0.012)
    cv.paint(cv.cover(sd), (0.30, 0.31, 0.32), 0.5, 1.0)
    return cv


def _cab_interior(V):
    top = np.array((0.05, 0.053, 0.058), np.float32)
    wall = np.array((0.30, 0.32, 0.33), np.float32)
    desk = np.array((0.06, 0.063, 0.07), np.float32)

    def ss(e0, e1):
        t = np.clip((V - e0) / (e1 - e0), 0, 1)
        return (t * t * (3 - 2 * t))[..., None]
    a = ss(2.36, 2.48)
    b = ss(2.96, 3.06)
    return (desk * (1 - a) + wall * a) * (1 - b) + top * b


HEADLAMP = (0.914, 3.37, 0.135, 0.12)     # |x|, y, width, height of the lamp unit
TAILLAMP = (0.620, 3.35, 0.10, 0.16)
LED_FRONT = (0.015, 3.33, 1.07, 0.16)     # centre x, y, width, height
LED_RUNNO = (-0.94, 3.04, 0.42, 0.12)
LED_SETNO = (-1.18, 2.22, 0.11, 0.06)


def paint_face(body, w=2048, h=1456):
    """the cab face (u = arc length from the centre line along each row, v = y)"""
    nose = body.nose
    cv = Canvas(Body.FACE_UV, w, h)
    U, V = cv.U, cv.V
    rows_y, rows_u, rows_x = [], [], []
    for i in range(nose.half):
        if len(nose.rows[i]) < 2:
            continue
        pts = nose.full_row(i)
        rows_y.append(nose.rows[i][0][1])
        rows_u.append(nose.row_u(pts))
        rows_x.append(np.array([p[0] for p in pts]))
    rows_y = np.array(rows_y)
    X = np.zeros_like(U)
    for j in range(h):
        y = V[j, 0]
        i = int(np.clip(np.searchsorted(rows_y, y) - 1, 0, len(rows_y) - 2))
        t = float(np.clip((y - rows_y[i]) / max(rows_y[i + 1] - rows_y[i], 1e-6), 0, 1))
        xa = np.interp(U[j], rows_u[i], rows_x[i])
        xb = np.interp(U[j], rows_u[i + 1], rows_x[i + 1])
        X[j] = xa + (xb - xa) * t
    dxdu = np.abs(np.gradient(X, axis=1)) / cv.px
    aa = np.maximum(cv.px * dxdu, 1e-4)
    cv.fill(GREEN, 0.30, 0.0)
    # the black panel: display band, windscreen, wiper band, then the dots into the green
    top, bot = 3.528, GROOVE_Y + 0.09
    sd_panel = _sd_rr(X, V, 0.0, (top + bot) / 2, 2 * PANEL_X, top - bot, 0.26)
    sd_bottom = _sd_rr(X, V, 0.0, (top + bot) / 2, 2 * PANEL_X, top - bot, GROOVE_R)
    sd_panel = np.where(V < 2.4, sd_bottom, sd_panel)
    inside = cv.cover(sd_panel, aa)
    cv.paint(inside * (V > 1.97), BLACK_PANEL, 0.08, 0.0)

    def t_face(u, v):
        return np.where(v > 1.97, 0.0, np.clip((1.97 - v) / (1.97 - 1.44), 0, 1))
    # dots: a two-phase checkerboard halftone over a black field between 1.44 and 1.97 (cells 0.031, photo 612879)
    band = inside * (V > 1.40) * (V <= 1.97)
    cv.paint(band, BLACK_PANEL, 0.25, 0.0)
    cv.paint(band * _halftone(X, V, t_face, 0.031, aa), GREEN, 0.30, 0.0)
    # glass divider bar between the display band and the windscreen
    sd = np.maximum(np.abs(X) - 1.37, np.abs(V - 3.165) - 0.045)
    cv.paint(cv.cover(sd, aa), (0.07, 0.072, 0.075), 0.3, 0.3)
    cv.paint(cv.cover(np.maximum(np.abs(X) - 1.37, np.abs(V - 3.209) - 0.003), aa), (0.30, 0.31, 0.32), 0.2, 0.5)
    # windscreen: the cab behind the glass
    sd = _sd_rr(X, V, 0.0, (2.15 + 3.12) / 2, 2.70, 3.12 - 2.15, 0.05)
    a = cv.cover(sd, aa)
    cv.paint(a, (0.0, 0.0, 0.0), 0.04, 0.0)
    a3 = a[..., None]
    cv.rgb = cv.rgb * (1 - a3) + _cab_interior(V) * 0.55 * a3
    # lamp housings in the display band
    for s in (-1, 1):
        cx, cy, ww, hh = HEADLAMP
        sd = _sd_rr(X, V, s * cx, cy, ww + 0.03, hh + 0.03, 0.02)
        cv.paint(cv.cover(sd, aa), (0.16, 0.165, 0.17), 0.3, 0.6)
        cx, cy, ww, hh = TAILLAMP
        sd = _sd_rr(X, V, s * cx, cy, ww + 0.02, hh + 0.02, 0.01)
        cv.paint(cv.cover(sd, aa), (0.12, 0.12, 0.125), 0.3, 0.3)
    # the coupler notch in the face's lower edge and the small slot above it
    sd = _sd_rr(X, V, 0.0, 0.95, 0.74, 0.226, 0.05)
    cv.paint(cv.cover(sd, aa), (0.02, 0.02, 0.022), 0.8, 0.0)
    sd = _sd_rr(X, V, 0.025, 1.100, 0.17, 0.018, 0.004)
    cv.paint(cv.cover(sd, aa), (0.02, 0.02, 0.022), 0.6, 0.0)
    return cv, X


# ---------------------------------------------------------------- materials

SIGNS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'textures', 'e235')
NUMBERS = {'car0': 'num_kuha235.png', 'car1': 'num_moha235.png', 'car2': 'num_kuha234.png'}


def _load(name):
    path = os.path.join(SIGNS, name)
    return bpy.data.images.load(path) if os.path.exists(path) else None


def add_materials(m, tex_dir, cars=(('car0', 'cab'), ('car1', 'middle'), ('car2', 'cab'))):
    """plain paints plus the painted textures (written to tex_dir); one side texture per car (its number)"""
    os.makedirs(tex_dir, exist_ok=True)
    m.add('e_stain', '#b4b6b8', metallic=1.0, roughness=0.30)
    m.add('e_end', '#a9abad', metallic=1.0, roughness=0.36)
    m.add('e_roof', ROOF_GREY, metallic=0.3, roughness=0.62)
    m.add('e_under', '#2a2b2d', roughness=0.85)
    m.add('e_sill', '#c4c6c8', metallic=0.9, roughness=0.32)
    m.add('e_bellows', '#2a2a2c', roughness=0.8)
    m.add('e_frame', '#3a3b3d', metallic=0.3, roughness=0.5)
    m.add('e_dark', '#141516', roughness=0.4)
    m.add('e_lamp', '#e8ebee', metallic=0.2, roughness=0.12)
    m.add('e_tail', '#4a0f12', roughness=0.15)
    m.add('e_chrome', '#d0d3d6', metallic=1.0, roughness=0.2)
    m.add('e_speaker', '#c9cbcc', metallic=0.4, roughness=0.4)
    m.add('e_sidelamp', '#d0b080', roughness=0.25)
    for name, kind in cars:
        num = os.path.join(SIGNS, NUMBERS[name])
        num = num if os.path.exists(num) else None
        left = paint_side(kind, 1, num)
        right = paint_side(kind, -1, num)
        img, mr = _stack(left, right, f'e_side_{name}', os.path.join(tex_dir, f'side_{name}.png'))
        m.mats[f'e_side_{name}'] = BD.textured_material(f'e_side_{name}', img, mr)
    cv = paint_bay()
    img, mr = cv.image('e_bay', os.path.join(tex_dir, 'bay.png'))
    m.mats['e_bay'] = BD.textured_material('e_bay', img, mr)
    cv, _ = paint_face(Body('cab'))
    img, mr = cv.image('e_face', os.path.join(tex_dir, 'face.png'))
    m.mats['e_face'] = BD.textured_material('e_face', img, mr)
    # LED displays: one emissive atlas
    keys = ('led_front', 'led_runno', 'led_setno', 'led_side')
    pieces = [(k, _load(k + '.png')) for k in keys]
    boxes = {}
    if all(img is not None for _, img in pieces):
        img, b = BD._atlas('e_led', pieces, os.path.join(tex_dir, 'led.png'))
        mat = BD.textured_material('e_led', img, img)
        p = mat.node_tree.nodes.get('Principled BSDF')
        tex = [n for n in mat.node_tree.nodes if n.type == 'TEX_IMAGE'][0]
        mat.node_tree.links.new(tex.outputs['Color'], p.inputs['Emission Color'])
        p.inputs['Emission Strength'].default_value = 1.0
        for n in [n for n in mat.node_tree.nodes if n.type == 'SEPARATE_COLOR']:
            mat.node_tree.nodes.remove(n)
        p.inputs['Roughness'].default_value = 0.2
        p.inputs['Metallic'].default_value = 0.0
        m.mats['e_led'] = mat
        boxes.update(b)
    return boxes


# ---------------------------------------------------------------- the cab's fittings


def _on_face(x, y, lift):
    return (x, y, face_z(x, y) + lift)


def _quad_on_face(part, mat, x0, x1, y0, y1, uv, lift, nx=4, ny=2):
    """a rectangle laid on the face, textured with the atlas box uv (u0, v0, u1, v1); viewer's left = image left"""
    u0, v0, u1, v1 = uv if uv else (0, 0, 0, 0)
    for j in range(ny):
        for i in range(nx):
            xa, xb = x0 + (x1 - x0) * i / nx, x0 + (x1 - x0) * (i + 1) / nx
            ya, yb = y0 + (y1 - y0) * j / ny, y0 + (y1 - y0) * (j + 1) / ny
            pts = [_on_face(xa, ya, lift), _on_face(xb, ya, lift), _on_face(xb, yb, lift), _on_face(xa, yb, lift)]

            def uvp(x, y):
                return (u0 + (u1 - u0) * (x - x0) / (x1 - x0), v0 + (v1 - v0) * (y - y0) / (y1 - y0))
            part.face_uv(pts, mat, [uvp(xa, ya), uvp(xb, ya), uvp(xb, yb), uvp(xa, yb)], out=(0, 0.1, 1))


def _box_on_face(part, mat, cx, cy, w, h, depth, lift=0.0):
    """a shallow block standing on the face (its front follows the face)"""
    x0, x1, y0, y1 = cx - w / 2, cx + w / 2, cy - h / 2, cy + h / 2
    f = [_on_face(x0, y0, lift + depth), _on_face(x1, y0, lift + depth), _on_face(x1, y1, lift + depth), _on_face(x0, y1, lift + depth)]
    b = [_on_face(x0, y0, lift - 0.01), _on_face(x1, y0, lift - 0.01), _on_face(x1, y1, lift - 0.01), _on_face(x0, y1, lift - 0.01)]
    part.face_uv(f, mat, [(0, 0)] * 4, smooth=False, out=(0, 0.1, 1))
    for k in range(4):
        l = (k + 1) % 4
        c = Vector(((x0 + x1) / 2, (y0 + y1) / 2, face_z(cx, cy)))
        q = [b[k], b[l], f[l], f[k]]
        m = Vector([sum(p[i] for p in q) / 4 for i in range(3)])
        part.face_uv(q, mat, [(0, 0)] * 4, smooth=False, out=m - c)


WIPERS = (((0.212, 2.066), (-0.347, 2.274)), ((0.803, 2.066), (0.244, 2.274)), ((0.979, 2.066), (1.267, 2.578)))


def cab_fittings(part, boxes):
    """displays, lamps and wipers on the cab face"""
    for key, (cx, cy, w, h), lift in (('led_front', LED_FRONT, 0.003), ('led_runno', LED_RUNNO, 0.002),
                                      ('led_setno', LED_SETNO, 0.002)):
        if key in boxes:
            _quad_on_face(part, 'e_led', cx - w / 2, cx + w / 2, cy - h / 2, cy + h / 2, boxes[key], lift)
    for s in (-1, 1):
        cx, cy, w, h = HEADLAMP
        cx *= s
        _box_on_face(part, 'e_frame', cx, cy, w, h, 0.004)
        # the lamp: an upper lens and a row of LED cells below it
        _box_on_face(part, 'e_lamp', cx, cy + 0.022, w - 0.02, 0.06, 0.007)
        for k in range(4):
            xx = cx + (k - 1.5) * 0.027
            _box_on_face(part, 'e_lamp', xx, cy - 0.035, 0.019, 0.019, 0.007)
        cx, cy, w, h = TAILLAMP
        _box_on_face(part, 'e_frame', s * cx, cy, w + 0.01, h + 0.01, 0.003)
        _box_on_face(part, 'e_tail', s * cx, cy, w, h, 0.006)
    # wipers parked on the windscreen's foot: arm (thicker) to the pivot, blade along the glass
    for (xa, ya), (xb, yb) in WIPERS:
        for sx in (1,):
            a = Vector(_on_face(sx * xa, ya, 0.012))
            b = Vector(_on_face(sx * xb, yb, 0.012))
            part.beam('e_dark', tuple(a), tuple(b), 0.012, 0.012)
            part.cylinder('e_dark', _on_face(sx * xa, ya, 0.01), 0.018, 0.02, axis='z', segments=10)


def _side_decal(part, mat, side, zc, yc, w, h, uv, lift=0.004, nz=4):
    """a rectangle laid on the vertical side (x = ±HW), textured; the image reads from outside on both sides"""
    u0, v0, u1, v1 = uv
    x = side * (HW + lift)
    for i in range(nz):
        za, zb = zc - w / 2 + w * i / nz, zc - w / 2 + w * (i + 1) / nz
        pts = [(x, yc - h / 2, za), (x, yc - h / 2, zb), (x, yc + h / 2, zb), (x, yc + h / 2, za)]

        def uu(z):
            t = (z - (zc - w / 2)) / w
            return u0 + (u1 - u0) * ((1 - t) if side > 0 else t)
        uvs = [(uu(p[2]), v0 if p[1] < yc else v1) for p in pts]
        part.face_uv(pts, mat, uvs, out=(side, 0, 0))


def side_fittings(part, boxes, kind):
    """side destination displays, the indicator lamps, the frieze boxes; on a cab car the crew doors' rails"""
    cab = kind == 'cab'
    windows = WINDOWS_CAB if cab else WINDOWS_MID
    for side in (-1, 1):
        sz = -1 if side > 0 else 1         # point symmetry: the right side mirrors z
        zc, yc, w, h = SIDE_SIGN
        if 'led_side' in boxes:
            part.box('e_dark', *sorted((side * (HW - 0.01), side * (HW + 0.004))), yc - h / 2 - 0.018, yc + h / 2 + 0.018,
                     zc - w / 2 - 0.02, zc + w / 2 + 0.02)
            _side_decal(part, 'e_led', side, zc, yc, w, h, boxes['led_side'], lift=0.006)
        lz, ly = SIDE_LAMP
        lz = lz * (1 if side > 0 else -1)
        part.box('e_frame', *sorted((side * (HW - 0.005), side * (HW + 0.010))), ly - 0.035, ly + 0.035, lz - 0.025, lz + 0.025,
                 bevel=0.006, segments=2)
        part.cylinder('e_sidelamp', (side * (HW + 0.014), ly, lz), 0.020, 0.012, axis='x', segments=12)
        y, bw, bh = SPEAKERS
        for zw, ww, _ in windows:
            if ww > 1.0 and abs(zw) > 1.0 or (cab and ww < 1.0 and abs(zw) < 6.0):
                zz = zw if side > 0 else (zw if not cab else zw)
                part.box('e_speaker', *sorted((side * (HW - 0.005), side * (HW + 0.022))), y - bh / 2, y + bh / 2,
                         zz - bw / 2, zz + bw / 2, bevel=0.01, segments=2)
        del sz
    if not cab:
        return
    z0, z1, y0, y1 = CREW_DOOR
    for side in (-1, 1):
        x = side * HW
        for zr in (z0 - 0.045, z1 + 0.045):
            part.cylinder('e_chrome', (x + side * 0.045, 1.80, zr), 0.0125, 1.10, axis='y', segments=10)
            for yy in (1.27, 2.33):
                part.cylinder('e_chrome', (x + side * 0.022, yy, zr), 0.009, 0.045, axis='x', segments=8)
        part.box('e_frame', *sorted((x, x + side * 0.008)), 2.02, 2.16, z0 + 0.05, z0 + 0.10, bevel=0.003, segments=1)
        # the step under the crew door
        part.box('e_frame', *sorted((x - side * 0.22, x + side * 0.02)), 0.82, 0.85, z0 + 0.08, z1 - 0.08)
        for zs in (z0 + 0.10, z1 - 0.10):
            part.box('e_frame', *sorted((x - side * 0.02, x + side * 0.01)), 0.82, BOTTOM + 0.02, zs - 0.015, zs + 0.015)
