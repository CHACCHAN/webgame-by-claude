"""
Body shell of the JR East E231 series 0番台 as converted for the Musashino Line (MU sets, 2017–2020): the wide
stainless body with its tapered lower sides, the roof, the gangway ends, the FRP-covered cab end, the passenger doors
(set into the sides and following the taper), the crew doors, the skirt, and the painted textures (stainless with its
spot-weld rows and seams, the orange / white / maroon stripes, windows, the cab face's black glass area, orange band
and lamp panel) drawn here with numpy. Material prefix `ek_`.

Figures (ja.wikipedia JR東日本E231系電車, 209系電車, read 2026-11-03):
- car 20,000 mm over the couplers, body 19,500, body width 2,950 (2,966 over the gutters), roof 3,655 at the centre
  line, floor 1,165 (door sill tip 1,150), bogie centres 13,800.
- 4 doors a side, 1,300 × 1,850 mm; door pitch 4,940 (209系 "客用扉間の寸法を4,800 mmから4,940 mm"); an intermediate
  car's end door centre 2,340 mm from the body end (E231 4600番台: "通常の中間車よりもドアが690 mm車体中央寄り … 車端部から
  3,030 mm"); a cab car is as long as an intermediate car, so only its front door pair is closer (6-seat bench, 2,700
  + 490 mm: door 1 at z = 6.96); cab depth 1,860.
- Musashino stripes: orange #f15a22, maroon #3c060f with a thin white line between (side: orange / white / maroon
  ≈ 20 : 0.3 : 5.7); the front has orange only; the crew doors carry the side stripes (Musashino conversion).
Measured on photos (Commons, ../e231/ref/list.json; heights scaled from the 1,850 mm doors and the 880 mm coupler):
- crop of "Series E231 MU2 in Shin-Urayasu Station.jpg" (Wikimizuki, CC BY-SA 4.0) at the cab car's door 1 and crew
  door: crease above the waist band y 1.79–1.83; orange 1.53–1.79; white 1.50–1.53; maroon below; door windows
  1.97–2.86; top band bottom 3.06.
- "Series-E231-0-MU4F.jpg" (MaedaAkihiko, CC BY-SA 4.0): side windows 1.93–2.86, about half the gap between the doors
  (1.70–1.90 m), two panes (drop + fixed); the top band runs over the doors, the waist stripes stop at the doors.
- "E231 Musashino-Line.jpg", "...Kuha E230-22 ... Fuchū-Hommachi" and the night head-on "京葉線の東京駅 ... E231系0番台.jpg"
  for the cab face (head-on X from the face width 2.95 m, heights between the coupler 0.88 and the roof 3.655):
  black glass area |x| ≤ 1.33, y 1.916–3.40 inside a silver FRP frame (sides ≈ 0.12–0.17, top ≈ 0.11–0.14 projected,
  top inner corners r ≈ 0.20: also "JRE Series-E231 B11.jpg", MaedaAkihiko, CC BY-SA 4.0); band 1.557–1.881 across the
  face; lamp panel |x| ≤ 1.38, 1.212–1.521 with a unit at each end (head lens |x| 0.79, tail lens 1.05, both y 1.367);
  run-number display centred at x −0.87, line-name display at x 0, both behind the glass at y 3.25 (inside the black
  area, under its top frame); skirt (the strengthened V-shaped type): top 0.69 at the sides, a notch down to 0.51
  round the coupler, bottom 0.16, V tip z 9.94.
Estimates: the section's taper (−0.06 at the bottom, from 1.80 down), the eave 3.24, shoulder r 0.36 (roof arc
r ≈ 12.2 m through 3.655), the face's rake and plan bulge, the cab corner radii, the crew door 8.40–9.00, end windows.

Frame: the game's car frame of train_kit (x left, y up, z forward, metres). A cab car has its cab at +z.
"""
import math
import os

import bmesh  # noqa: F401
import bpy
import numpy as np
from mathutils import Vector

import train_kit as K
import body_n1000 as BD

P = 'ek_'
UVPart = BD.UVPart

# ---------------------------------------------------------------- dimensions
HW = 1.475              # half the body width (2,950)
BOTTOM = 1.00           # lower edge of the body side
TAPER = 0.060           # the side is this much further in at the bottom than at the crease
CREASE = 1.80           # below: the side tapers in towards the bottom; above: vertical
EAVE = 3.24             # top of the vertical side: the gutter
SHOULDER = 0.36
ROOF = 3.655
END = 9.75              # body ends (gangway faces)
SILL = 1.15
DOOR_TOP = 3.015
DOOR_W = 1.30
DOOR_DEPTH = 0.032      # the leaves sit this far into the side
DOORS_MID = (-7.41, -2.47, 2.47, 7.41)
DOORS_CAB = (-7.41, -2.47, 2.47, 6.96)
WIN = (1.93, 2.86)      # side windows
DWIN = (1.97, 2.86)     # door windows
TOP_BAND = (3.05, 3.225)
ORANGE_BAND = (1.53, 1.79)
WHITE_LINE = (1.505, 1.53)
MAROON_BAND = (1.43, 1.505)
CREW_DOOR = (8.40, 9.00, 1.07, 3.00)       # z0, z1, y0, y1 (hinged; the stripes run over it)
# side destination display and side lamp (right side, −x; the left side has them point-symmetric)
SIDE_SIGN = (0.25, 3.145, 0.66, 0.17)      # centre z, centre y, frame width, frame height
SIDE_LAMP = (0.73, 3.145, 0.035)

# the cab end: centre-line profile of the face (y, z), its plan bulge, the corner radii
CAB_PROFILE = [(1.00, 9.785), (1.20, 9.800), (1.50, 9.802), (1.90, 9.795), (2.30, 9.770), (2.90, 9.715), (3.40, 9.660), (3.70, 9.630)]
CAB_BULGE = 0.07
CAB_R_SIDE = 0.34
CAB_R_TOP = 0.28
CAB_JOIN = 9.30
END_R = 0.05

# paint (sRGB floats)
STEEL = (0.700, 0.705, 0.700)       # stainless, dull finish (metallic)
FRP = (0.745, 0.748, 0.742)         # the cab face's silver paint
ORANGE = (0.945, 0.353, 0.133)      # #f15a22
MAROON = (0.235, 0.024, 0.059)      # #3c060f
WHITE = (0.93, 0.93, 0.91)
GLASS = (0.040, 0.045, 0.048)
SIDE_GLASS = (0.105, 0.125, 0.125)  # the saloon seen dimly through the green-tinted side windows
GASKET = (0.060, 0.060, 0.062)
BLACK = (0.030, 0.030, 0.033)
ROOF_GREY = '#9a9a96'

YELLOW = (1.0, 0.831, 0.0)           # 黄1号 #ffd400 (Chūō-Sōbu local)
EMERALD = (0.10, 0.64, 0.61)         # 青緑1号 (Jōban rapid), between the coordinator's #339999 and the photos' sunlit cyan
UGUISU = (0.40, 0.78, 0.26)          # the yellow-green line under it (sampled from j00 / j03, toned down)

_TEXTURES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'textures', 'e231')
SIGNS = _TEXTURES

# Liveries: only paint and signs differ, the geometry is the same for every variant.
#   top: the film band under the gutter (y0, y1, colour); waist: [(y0, y1, colour, roughness)] from the top down;
#   front: the band across the cab face (FRONT_BAND); crew_door: the hinged crew door wrapped in the band colour.
# Musashino (MU sets): orange #f15a22 over a white line and a maroon band (photos p04, p14, crop14: side heights
#   measured with the door 1,850 mm as the scale). Chūō-Sōbu local (as built, B sets): one yellow band at the waist,
#   a deeper one under the gutter, the crew door all yellow, the face band as on the Musashino cars (Commons
#   "Kuha E230-11 Mitaka Rolling Stock Center 20211101.jpg", Rsa, CC BY-SA 3.0: waist 1.44–1.80, top 3.02–gutter,
#   window bottom 1.93 and door sill 1.15 as the scale).
# Jōban rapid / Narita line (as running, Matsudo sets; joban/ref/list.json): the cab face's FRP white (`frp`), on it
#   an emerald band over a thin yellow-green line under the windscreen (`front_bands`; j03 head-on, the black area's
#   bottom 1.916 and the lamp panel's top 1.521 as the scale: emerald 1.64–1.835, line 1.568–1.64) and a white JR
#   mark on the emerald at x 1.04 (j00 / j03, `jr_front`); sides: emerald 1.52–1.80 over the line 1.46–1.52 (j00 /
#   j04 / j06: about 4 : 1, the emerald's top 0.13 under the windows), emerald under the gutter (3.03–3.235, j06) cut
#   by the blanked-off outside-speaker plates (`top_gaps`: z of their centres, one in each outer window bay, j06;
#   ja.wikipedia: メクラ蓋で塞いでおり、ラインが途切れている), the crew door wrapped in emerald (j06); the skirt
#   white (`skirt`), the electric coupler under the head (`electric_coupler`), JR marks white on the sides.
LIVERIES = {
    'musashino': dict(top=(3.05, 3.225, ORANGE),
                      waist=((1.53, 1.79, ORANGE, 0.42), (1.505, 1.53, WHITE, 0.42), (1.43, 1.505, MAROON, 0.40)),
                      front=ORANGE, crew_door=False, signs=''),
    'sobu': dict(top=(3.02, 3.235, YELLOW), waist=((1.44, 1.80, YELLOW, 0.42),),
                 front=YELLOW, crew_door=True, signs='sobu'),
    'joban': dict(top=(3.03, 3.235, EMERALD), waist=((1.52, 1.80, EMERALD, 0.42), (1.46, 1.52, UGUISU, 0.42)),
                  front=EMERALD, front_bands=((1.64, 1.835, EMERALD), (1.568, 1.64, UGUISU)),
                  frp=((0.93, 0.93, 0.91), 0.32, 0.0), jr_front=(1.04, 1.7375, 0.11, (0.95, 0.95, 0.95)),
                  jr_side=(0.92, 0.92, 0.92), top_gaps={'cab': (-4.94, 4.715), 'middle': (-4.94, 4.94)},
                  skirt=('#e4e4e0', 0.0, 0.40), electric_coupler=True, crew_door=True, signs='joban'),
}
LIVERY = LIVERIES['musashino']


def set_variant(name):
    """switch paint and signs ('musashino', 'sobu' or 'joban') before add_materials"""
    global LIVERY, SIGNS
    LIVERY = LIVERIES[name]
    SIGNS = os.path.join(_TEXTURES, LIVERY['signs']) if LIVERY['signs'] else _TEXTURES


# ---------------------------------------------------------------- the section

def side_x(y):
    """half width of the side at height y (below the eave)"""
    if y >= CREASE:
        return HW
    t = (CREASE - y) / (CREASE - BOTTOM)
    return HW - TAPER * t ** 1.6


def _side_nx(y):
    """outward normal (nx, ny) of the side at height y"""
    if y >= CREASE:
        return 1.0, 0.0
    t = (CREASE - y) / (CREASE - BOTTOM)
    dxdy = TAPER * 1.6 * t ** 0.6 / (CREASE - BOTTOM)      # x grows with y
    n = math.hypot(1.0, dxdy)
    return 1.0 / n, -dxdy / n


def _roof_geometry():
    r = SHOULDER
    a = HW - r
    b = EAVE - ROOF
    assert r < ROOF - EAVE, 'the shoulder radius must stay below the roof rise over the eave'
    rr = (r * r - a * a - b * b) / (2 * b + 2 * r)
    theta = math.atan2(EAVE - (ROOF - rr), a)
    return rr, theta


def half_profile():
    """[(x, y, nx, ny)] from the bottom of the left side (+x) up to the roof's centre line"""
    pts = []
    ys = [BOTTOM, 1.07, 1.15, 1.25, 1.36, 1.43, 1.505, 1.53, 1.66, CREASE, 1.93, 2.10, 2.30, 2.50, 2.70, 2.86,
          DOOR_TOP, TOP_BAND[0], TOP_BAND[1], EAVE]
    for y in ys:
        nx, ny = _side_nx(y)
        pts.append((side_x(y), y, nx, ny))
    r = SHOULDER
    rr, theta = _roof_geometry()
    ns = 7
    for k in range(1, ns + 1):
        t = theta * k / ns
        pts.append((HW - r + r * math.cos(t), EAVE + r * math.sin(t), math.cos(t), math.sin(t)))
    nr = 8
    for k in range(1, nr + 1):
        a = theta + (math.pi / 2 - theta) * k / nr
        x = rr * math.cos(a)
        pts.append((0.0 if k == nr else x, ROOF - rr + rr * math.sin(a), math.cos(a), math.sin(a)))
    return pts


def ring():
    half = half_profile()
    right = [(-x, y, -nx, ny) for x, y, nx, ny in half]
    return right + list(reversed(half[:-1]))


# ---------------------------------------------------------------- the cab end

_ZC = BD._pchip(CAB_PROFILE)


def face_z(x, y):
    return _ZC(y) - CAB_BULGE * (x / HW) ** 2


def corner_radius(y):
    return CAB_R_SIDE + (CAB_R_TOP - CAB_R_SIDE) * K.smoothstep(3.05, 3.45, y)


class Nose(BD.Nose):
    """the Keikyu nose (quarter-round columns into a raked, bulged face) on the E231 section"""

    def __init__(self, steps=10, across=30):
        self.ring = ring()
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


def _out(p, zc):
    c = Vector(p)
    return c - Vector((0.0, 2.2, max(-8.6, min(8.6, zc))))


# ---------------------------------------------------------------- the shell

class Body:
    SIDE_UV = (-9.80, 9.80, 0.98, 3.30)
    FACE_UV = (-1.80, 1.80, 0.95, 3.75)

    def __init__(self, kind):
        self.kind = kind
        self.cab = kind == 'cab'
        self.ring = ring()
        self.n = len(self.ring)
        self.half = (self.n + 1) // 2
        self.nose = Nose() if self.cab else None
        self.doors = DOORS_CAB if self.cab else DOORS_MID
        self.side_mat = P + 'side_' + kind

    def side_uv(self, z, y):
        u0, u1, v0, v1 = self.SIDE_UV
        return ((z - u0) / (u1 - u0), (y - v0) / (v1 - v0))

    def face_uv(self, u, y):
        u0, u1, v0, v1 = self.FACE_UV
        return ((u - u0) / (u1 - u0), (y - v0) / (v1 - v0))

    def zone(self, y, ny):
        if y > EAVE - 0.005 and ny > 0.05:
            return P + 'roof'
        return P + 'steel'

    def textured(self, y, nx):
        return abs(nx) > 0.6 and y < EAVE + 0.001

    def stations(self):
        zs = {-(END - END_R), (END - END_R) if not self.cab else CAB_JOIN}
        for zd in self.doors:
            zs.add(zd - DOOR_W / 2)
            zs.add(zd + DOOR_W / 2)
        out = sorted(zs)
        fine = []
        for a, b in zip(out[:-1], out[1:]):
            k = max(1, int(math.ceil((b - a) / 1.2)))
            fine += [a + (b - a) * i / k for i in range(k)]
        return fine + [out[-1]]

    def in_door(self, za, zb, ya, yb):
        if ya < SILL - 1e-6 or yb > DOOR_TOP + 1e-6:
            return False
        return any(za >= zd - DOOR_W / 2 - 1e-6 and zb <= zd + DOOR_W / 2 + 1e-6 for zd in self.doors)

    def build(self, part):
        ring = self.ring
        zs = self.stations()
        for za, zb in zip(zs[:-1], zs[1:]):
            for i in range(self.n - 1):
                (xa, ya, nxa, nya), (xb, yb, nxb, nyb) = ring[i], ring[i + 1]
                nx = (nxa + nxb) / 2
                ny = (nya + nyb) / 2
                if abs(nx) > 0.9 and self.in_door(za, zb, min(ya, yb), max(ya, yb)):
                    continue
                pts = [(xa, ya, za), (xb, yb, za), (xb, yb, zb), (xa, ya, zb)]
                cy = (ya + yb) / 2
                out = _out((0.5 * (xa + xb), cy, 0.5 * (za + zb)), 0.5 * (za + zb))
                if self.textured(cy, nx):
                    part.face_uv(pts, self.side_mat, [self.side_uv(p[2], p[1]) for p in pts], out=out)
                else:
                    part.face_uv(pts, self.zone(cy, ny), [(0, 0)] * 4, out=out)
        x0 = side_x(BOTTOM)
        part.face_uv([(-x0, BOTTOM, zs[0]), (x0, BOTTOM, zs[0]), (x0, BOTTOM, zs[-1]), (-x0, BOTTOM, zs[-1])],
                     P + 'under', [(0, 0)] * 4, smooth=False, out=(0, -1, 0))
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
        self.gutters(part)

    def gangway_end(self, part, z_end, sign):
        steps = 2
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
                out = c - Vector((0.0, 2.2, z_end - sign * 1.0))
                if self.textured(cy, nx) and k == 0:
                    part.face_uv(pts, self.side_mat, [self.side_uv(p[2], p[1]) for p in pts], out=out)
                else:
                    part.face_uv(pts, self.zone(cy, ny) if ny > 0.3 else P + 'steel', [(0, 0)] * 4, out=out)
        for i in range(self.half - 1):
            a, b = cols[i][-1], cols[self.n - 1 - i][-1]
            c, d = cols[i + 1][-1], cols[self.n - 2 - i][-1]
            pts = [a, b, d, c] if c != d else [a, b, c]
            part.face_uv(pts, P + 'end', [(0, 0)] * len(pts), smooth=False, out=(0, 0, sign))
        b0, b1 = cols[0], cols[self.n - 1]
        for k in range(steps):
            pts = [b0[k], b1[k], b1[k + 1], b0[k + 1]]
            part.face_uv(pts, P + 'under', [(0, 0)] * 4, smooth=False, out=(0, -1, 0))
        # round downpipes at the corners (Tokyu / Niitsu-built ends: round pipes, no beads)
        for s in (-1, 1):
            x = s * (side_x(2.0) - 0.07)
            part.cylinder(P + 'steel', (x, (BOTTOM + 0.15 + EAVE) / 2, z_end + sign * 0.03), 0.022,
                          EAVE - BOTTOM - 0.15, axis='y', segments=8)
        # end-wall top: the joint between the end sheet and the roof
        part.box(P + 'steel', -1.05, 1.05, EAVE + 0.10, EAVE + 0.13, min(z_end, z_end + sign * 0.02), max(z_end, z_end + sign * 0.02))

    def cab_end(self, part):
        nose = self.nose
        ring = self.ring
        n = self.n
        for i in range(n - 1):
            (xa, ya, nxa, nya), (xb, yb, nxb, nyb) = ring[i], ring[i + 1]
            a, b = nose.cols[i][0], nose.cols[i + 1][0]
            pts = [(xa, ya, CAB_JOIN), (xb, yb, CAB_JOIN), b, a]
            cy = (ya + yb) / 2
            nx = (nxa + nxb) / 2
            ny = (nya + nyb) / 2
            out = _out((0.5 * (xa + xb), cy, CAB_JOIN + 0.3), CAB_JOIN + 0.3)
            if self.textured(cy, nx):
                part.face_uv(pts, self.side_mat, [self.side_uv(p[2], p[1]) for p in pts], out=out)
            else:
                part.face_uv(pts, self.zone(cy, ny), [(0, 0)] * 4, out=out)
        u_col = [None] * n
        u_row = [None] * self.half
        for i in range(self.half):
            pts = nose.full_row(i)
            u = nose.row_u(pts)
            k = nose.steps + 1
            u_col[i] = list(u[:k])
            if i != n - 1 - i:
                u_col[n - 1 - i] = list(reversed(u[len(u) - k:]))
            mid = nose.rows[i]
            u_row[i] = [u[k - 1]] + list(u[k:len(u) - k]) + [u[len(u) - k]] if len(mid) > 1 else [0.0]
        self.u_col, self.u_row = u_col, u_row
        face = P + 'face'
        out_c = Vector((0.0, 2.2, 8.6))
        for i in range(n - 1):
            for k in range(nose.steps):
                pts = [nose.cols[i][k], nose.cols[i + 1][k], nose.cols[i + 1][k + 1], nose.cols[i][k + 1]]
                uvs = [(u_col[i][k], pts[0][1]), (u_col[i + 1][k], pts[1][1]), (u_col[i + 1][k + 1], pts[2][1]), (u_col[i][k + 1], pts[3][1])]
                c = Vector([sum(p[j] for p in pts) / 4 for j in range(3)])
                part.face_uv(pts, face, [self.face_uv(u, v) for u, v in uvs], out=c - out_c)
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
                part.face_uv(pts, face, [self.face_uv(u, v) for u, v in uvs], out=(0, 0.3, 1))
        bottom = nose.full_row(0)
        c = (0.0, BOTTOM, CAB_JOIN)
        prev = (ring[0][0], BOTTOM, CAB_JOIN)
        for p in bottom + [(ring[n - 1][0], BOTTOM, CAB_JOIN)]:
            q = (p[0], BOTTOM, p[2])
            if Vector(q) != Vector(prev):
                part.face_uv([c, prev, q], P + 'under', [(0, 0)] * 3, smooth=False, out=(0, -1, 0))
            prev = q

    def door(self, part, zd, side):
        """a passenger door: jambs into the side, the leaves set back, following the side's taper"""
        za, zb = zd - DOOR_W / 2, zd + DOOR_W / 2
        prof = [(x, y) for x, y, nx, ny in self.ring[self.half - 1:] if SILL - 1e-6 <= y <= DOOR_TOP + 1e-6 and nx > 0.9]
        prof = sorted(set([(side_x(SILL), SILL)] + prof + [(HW, DOOR_TOP)]), key=lambda p: p[1])
        for zj, facing in ((za, 1), (zb, -1)):
            for (xa, ya), (xb, yb) in zip(prof[:-1], prof[1:]):
                part.face_uv([(side * xa, ya, zj), (side * xb, yb, zj), (side * (xb - DOOR_DEPTH), yb, zj), (side * (xa - DOOR_DEPTH), ya, zj)],
                             P + 'jamb', [(0, 0)] * 4, smooth=False, out=(0, 0, facing))
        xt = HW
        part.face_uv([(side * xt, DOOR_TOP, za), (side * xt, DOOR_TOP, zb), (side * (xt - DOOR_DEPTH), DOOR_TOP, zb), (side * (xt - DOOR_DEPTH), DOOR_TOP, za)],
                     P + 'jamb', [(0, 0)] * 4, smooth=False, out=(0, -1, 0))
        xs = side_x(SILL)
        part.face_uv([(side * xs, SILL, za), (side * xs, SILL, zb), (side * (xs - DOOR_DEPTH - 0.05), SILL, zb), (side * (xs - DOOR_DEPTH - 0.05), SILL, za)],
                     P + 'sill', [(0, 0)] * 4, smooth=False, out=(0, 1, 0))
        zl = [za, zd, zb]
        for (xa, ya), (xb, yb) in zip(prof[:-1], prof[1:]):
            for z0, z1 in zip(zl[:-1], zl[1:]):
                pts = [(side * (xa - DOOR_DEPTH), ya, z0), (side * (xb - DOOR_DEPTH), yb, z0), (side * (xb - DOOR_DEPTH), yb, z1), (side * (xa - DOOR_DEPTH), ya, z1)]
                part.face_uv(pts, self.side_mat, [self.side_uv(p[2], p[1]) for p in pts], smooth=True, out=(side, 0, 0))

    def gutters(self, part):
        """drip rails along the eaves"""
        z0 = -END + 0.02
        z1 = (CAB_JOIN + 0.05) if self.cab else END - 0.02
        for s in (-1, 1):
            x = s * HW
            part.box(P + 'steel', *sorted((x - s * 0.002, x + s * 0.010)), EAVE - 0.012, EAVE + 0.022, z0, z1)


def bellows(part, z_end, sign, half_gap=0.25, w=1.06, y0=1.17, y1=3.12, folds=4, depth=0.03):
    """the car's half of the gangway bellows (as body_n1000.bellows, with this module's materials)"""
    zf = z_end + sign * 0.012
    part.box(P + 'frame', -w / 2 - 0.05, w / 2 + 0.05, y0 - 0.05, y1 + 0.05, min(z_end, zf), max(z_end, zf))
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
            part.face_uv(pts, P + 'bellows', [(0, 0)] * 4, smooth=False, out=(c.x, c.y - (y0 + y1) / 2, 0))
    zl = zs[-1]
    part.box(P + 'frame', -w / 2 - depth, w / 2 + depth, y0 - depth, y1 + depth, min(zl, zl - sign * 0.02), max(zl, zl - sign * 0.02))


# ---------------------------------------------------------------- painting


class Canvas(BD.Canvas):
    """BD.Canvas with a metallic channel (stainless 1, films / glass / rubber 0)"""

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
        rgba = np.ones((self.h, self.w, 4), np.float32)
        rgba[..., :3] = np.clip(self.rgb, 0, 1)
        img = bpy.data.images.new(name, self.w, self.h, alpha=False)
        img.pixels.foreach_set(rgba.ravel())
        img.filepath_raw = path
        img.file_format = 'PNG'
        img.save()
        mr = np.ones((self.h, self.w, 4), np.float32)
        mr[..., 1] = np.clip(self.rough, 0, 1)
        mr[..., 2] = np.clip(self.metal, 0, 1)
        img2 = bpy.data.images.new(name + '_mr', self.w, self.h, alpha=False)
        img2.colorspace_settings.name = 'Non-Color'
        img2.pixels.foreach_set(mr.ravel())
        img2.filepath_raw = path.replace('.png', '_mr.png')
        img2.file_format = 'PNG'
        img2.save()
        return img, img2


SRR = BD._sd_round_rect


def _dots(cv, U, V, y, z0, z1, pitch=0.05, r=0.0045, strength=0.10):
    """a row of spot welds: small darker, rougher dots"""
    mask = (np.abs(V - y) < 0.012) & (U > z0) & (U < z1)
    if not mask.any():
        return
    du = (U - z0) % pitch - pitch / 2
    sd = np.sqrt(du * du + (V - y) ** 2) - r
    a = cv.cover(sd) * mask * strength
    cv.paint(a.astype(np.float32), (0.40, 0.40, 0.40), 0.55)


def _vdots(cv, U, V, z, y0, y1, pitch=0.05, r=0.0045, strength=0.10):
    mask = (np.abs(U - z) < 0.012) & (V > y0) & (V < y1)
    if not mask.any():
        return
    dv = (V - y0) % pitch - pitch / 2
    sd = np.sqrt((U - z) ** 2 + dv * dv) - r
    a = cv.cover(sd) * mask * strength
    cv.paint(a.astype(np.float32), (0.40, 0.40, 0.40), 0.55)


def _line(cv, U, V, z=None, y=None, w=0.003, lo=None, hi=None, colour=(0.30, 0.30, 0.30), alpha=0.5, rough=0.5):
    if z is not None:
        sd = np.abs(U - z) - w / 2
        if lo is not None:
            sd = np.maximum(sd, np.maximum(lo - V, V - hi))
    else:
        sd = np.abs(V - y) - w / 2
        if lo is not None:
            sd = np.maximum(sd, np.maximum(lo - U, U - hi))
    cv.paint((cv.cover(sd) * alpha).astype(np.float32), colour, rough)


def paint_side(kind, number_img=None, w=4096, h=512):
    """the side texture (u = z, v = y), shared by both sides (the left side mirrors it) and the door leaves"""
    cv = Canvas(Body.SIDE_UV, w, h)
    U, V = cv.U, cv.V
    cab = kind == 'cab'
    doors = DOORS_CAB if cab else DOORS_MID
    # stainless: dull finish with faint horizontal grain
    grain = (np.sin(V * 2900.0) * 0.5 + np.sin(V * 1210.0 + 1.3) * 0.5) * 0.008
    cv.fill(STEEL, 0.34, 1.0)
    cv.rgb += grain[..., None].astype(np.float32)
    # the lower panel below the crease is a separate sheet, a touch darker
    cv.paint((V < CREASE - 0.02).astype(np.float32) * 0.35, (0.66, 0.665, 0.66), 0.36, 1.0)
    z_end0 = -END + 0.04
    z_end1 = (CAB_JOIN + 0.2) if cab else END - 0.04

    def in_doors(margin):
        m = np.zeros_like(U, dtype=bool)
        for zd in doors:
            m |= np.abs(U - zd) < DOOR_W / 2 + margin
        return m

    # the top band: orange film along the whole side, interrupted by the destination display
    ty0, ty1, tcol = LIVERY['top']
    sd = np.maximum(np.maximum(ty0 - V, V - ty1), np.maximum(z_end0 - U, U - z_end1))
    cv.paint(cv.cover(sd), tcol, 0.42, 0.0)
    for zg in LIVERY.get('top_gaps', {}).get(kind, ()):   # blanked-off speaker openings: a stainless plate in a seam
        sd = SRR(U, V, zg, (ty0 + ty1) / 2, 0.13, ty1 - ty0 + 0.01, 0.01)
        cv.paint(cv.cover(sd), STEEL, 0.36, 1.0)
        cv.paint(cv.cover(np.abs(sd + 0.006) - 0.002) * 0.6, (0.33, 0.33, 0.34), 0.5, 0.0)
    # waist stripes: orange, white, maroon; they stop at the door openings (with a little steel margin)
    stripe_z1 = (CAB_JOIN + 0.2) if cab else z_end1
    off = in_doors(0.035).astype(np.float32)
    if cab:   # the crew door carries the stripes
        pass
    if cab and LIVERY['crew_door']:   # the crew door wrapped in the band colour
        cz0, cz1, cy0, cy1 = CREW_DOOR
        sd = SRR(U, V, (cz0 + cz1) / 2, (cy0 + cy1) / 2, cz1 - cz0, cy1 - cy0, 0.04)
        cv.paint(cv.cover(sd), LIVERY['waist'][0][2], 0.42, 0.0)
    for y0, y1, col, rough in LIVERY['waist']:
        sd = np.maximum(np.maximum(y0 - V, V - y1), np.maximum(z_end0 - U, U - stripe_z1))
        cv.paint(cv.cover(sd) * (1 - off), col, rough, 0.0)
    # the crease above the waist stripes: a bright line over a shadow
    _line(cv, U, V, y=CREASE + 0.004, w=0.006, colour=(0.86, 0.86, 0.86), alpha=0.6, rough=0.25)
    _line(cv, U, V, y=CREASE - 0.006, w=0.008, colour=(0.33, 0.33, 0.34), alpha=0.45)

    def window(z0, z1, y0=WIN[0], y1=WIN[1], r=0.07, mullion=None):
        cz, cy, ww, hh = (z0 + z1) / 2, (y0 + y1) / 2, z1 - z0, y1 - y0
        sd = SRR(U, V, cz, cy, ww, hh, r)
        cv.paint(cv.cover(sd + 0.004), (0.86, 0.86, 0.86), 0.22, 1.0)         # bright frame edge
        cv.paint(cv.cover(sd), GASKET, 0.45, 0.0)
        cv.paint(cv.cover(sd + 0.022), SIDE_GLASS, 0.05, 0.0)
        if mullion is not None:
            zm = mullion
            sdm = np.maximum(np.abs(U - zm) - 0.035, np.maximum(y0 - V, V - y1))
            cv.paint(cv.cover(sdm), GASKET, 0.45, 0.0)
            sdm = np.maximum(np.abs(U - zm) - 0.012, np.maximum(y0 + 0.02 - V, V - y1 + 0.02))
            cv.paint(cv.cover(sdm), (0.55, 0.56, 0.56), 0.3, 1.0)
            # the drop pane's frame (the half towards +z): a thin aluminium surround inside the gasket
            zd0, zd1 = (zm + 0.035, z1 - 0.022) if zm < cz + 1 else (z0, zm)
            sdd = np.abs(SRR(U, V, (zd0 + zd1) / 2, cy, zd1 - zd0, hh - 0.044, 0.04)) - 0.006
            cv.paint(cv.cover(sdd) * 0.8, (0.48, 0.49, 0.49), 0.3, 1.0)
            # the drop pane's top rail
            sdt = np.maximum(np.abs(V - (y1 - 0.20)) - 0.012, np.maximum(zd0 - U, U - zd1))
            cv.paint(cv.cover(sdt) * 0.9, (0.42, 0.43, 0.43), 0.3, 1.0)

    gaps = list(zip(doors[:-1], doors[1:]))
    for a, b in gaps:
        c = (a + b) / 2
        wwin = 1.86 if (b - a) > 4.8 else 1.70
        window(c - wwin / 2, c + wwin / 2, mullion=c)
    # car-end windows
    window(-END + 0.20, -END + 0.98)
    if not cab:
        window(END - 0.98, END - 0.20)
    # door openings: a raised frame round the leaves (bright edge, shadow line), rounded at the top
    for zd in doors:
        sd = SRR(U, V, zd, (SILL + DOOR_TOP) / 2 + 0.03, DOOR_W + 0.08, DOOR_TOP - SILL + 0.10, 0.07)
        ring_ = np.abs(sd + 0.02) - 0.02
        cv.paint(cv.cover(ring_) * 0.55, (0.83, 0.83, 0.82), 0.22, 1.0)
        cv.paint(cv.cover(np.abs(sd + 0.002) - 0.003) * 0.7, (0.25, 0.25, 0.26), 0.5, 0.0)
        # door leaves (painted where the leaves lie: u = z of the leaf, they share the texture)
        for s in (-1, 1):
            zc = zd + s * DOOR_W / 4
            sd = SRR(U, V, zc, sum(DWIN) / 2, 0.36, DWIN[1] - DWIN[0], 0.11)
            inside = (np.abs(U - zd) < DOOR_W / 2) & (V > SILL) & (V < DOOR_TOP)
            cv.paint(cv.cover(sd + 0.004) * inside, (0.86, 0.86, 0.86), 0.22, 1.0)
            cv.paint(cv.cover(sd) * inside, GASKET, 0.45, 0.0)
            cv.paint(cv.cover(sd + 0.020) * inside, SIDE_GLASS, 0.05, 0.0)
            # the leaf's stiffening press line along its outer edge
            _line(cv, U, V, z=zd + s * (DOOR_W / 2 - 0.05), w=0.004, lo=SILL + 0.06, hi=DOOR_TOP - 0.06, colour=(0.85, 0.85, 0.85), alpha=0.5, rough=0.25)
        # centre seam with its rubber, and the rubbers along the jambs
        for zl, wl in ((zd, 0.012), (zd - DOOR_W / 2 + 0.008, 0.016), (zd + DOOR_W / 2 - 0.008, 0.016)):
            sd = np.maximum(np.abs(U - zl) - wl / 2, np.maximum(SILL - V, V - DOOR_TOP))
            cv.paint(cv.cover(sd), GASKET, 0.6, 0.0)
        # spot-weld rows framing the door pocket
        for zz in (zd - DOOR_W / 2 - 0.10, zd + DOOR_W / 2 + 0.10):
            _vdots(cv, U, V, zz, 1.95, 2.95)
    # spot-weld rows along the window header, the sill line and under the top band
    _dots(cv, U, V, 2.95, z_end0, z_end1)
    _dots(cv, U, V, 1.86, z_end0, z_end1)
    _dots(cv, U, V, TOP_BAND[0] - 0.035, z_end0, z_end1)
    _dots(cv, U, V, 1.25, z_end0, z_end1, pitch=0.07)
    # vertical sheet joints between the window panels and the pockets
    for a, b in gaps:
        c = (a + b) / 2
        for zz in (c - 1.30, c + 1.30):
            _line(cv, U, V, z=zz, w=0.003, lo=CREASE + 0.02, hi=TOP_BAND[0] - 0.01, colour=(0.45, 0.45, 0.46), alpha=0.5)
    if cab:
        # the crew door: outline, its window, the step pocket at the bottom
        cz0, cz1, cy0, cy1 = CREW_DOOR
        sd = SRR(U, V, (cz0 + cz1) / 2, (cy0 + cy1) / 2, cz1 - cz0, cy1 - cy0, 0.04)
        cv.paint(cv.cover(np.abs(sd) - 0.006), GASKET, 0.6, 0.0)
        cv.paint(cv.cover(np.abs(sd + 0.016) - 0.004) * 0.5, (0.86, 0.86, 0.86), 0.25, 1.0)
        sd = SRR(U, V, (cz0 + cz1) / 2 + 0.03, 2.43, 0.34, 0.88, 0.06)
        cv.paint(cv.cover(sd + 0.004), (0.86, 0.86, 0.86), 0.22, 1.0)
        cv.paint(cv.cover(sd), GASKET, 0.45, 0.0)
        cv.paint(cv.cover(sd + 0.018), SIDE_GLASS, 0.05, 0.0)
        sd = SRR(U, V, (cz0 + cz1) / 2 + 0.03, 1.17, 0.30, 0.10, 0.015)
        cv.paint(cv.cover(sd), (0.10, 0.10, 0.11), 0.6, 0.0)
        # the door between the crew door and the passenger door 1: nothing but the stripes and a weld row
        _vdots(cv, U, V, cz0 - 0.08, 1.9, 2.95)
    # car number at the lower end of the side (left on the right-hand side seen from outside: the −z end)
    if number_img is not None:
        arr = BD._pixels(number_img) if not isinstance(number_img, np.ndarray) else number_img
        nh, nw = arr.shape[:2]
        hgt = 0.075 * nh / max(1, nh - 8)
        wid = hgt * nw / nh
        z0 = -1.25
        y0 = 1.30
        samp, inside = BD._sample(arr, U, V, z0, z0 + wid, y0, y0 + hgt)
        a = (samp[..., 3] * inside)[..., None]
        cv.rgb = cv.rgb * (1 - a) + np.array((0.06, 0.06, 0.065), np.float32) * a
        cv.rough = cv.rough * (1 - a[..., 0]) + 0.5 * a[..., 0]
        cv.metal = cv.metal * (1 - a[..., 0])
    return cv


def _cab_interior(V, X):
    """the cab behind the windscreen (as on photos taken head-on): light grey partition with the door to the saloon on
    the right (−x) and a window into the saloon in the middle, the dark ceiling and the low desk across"""
    top = np.array((0.05, 0.052, 0.056), np.float32)
    wall = np.array((0.50, 0.51, 0.52), np.float32)
    desk = np.array((0.07, 0.072, 0.078), np.float32)

    def ss(e0, e1, v=V):
        t = np.clip((v - e0) / (e1 - e0), 0, 1)
        return (t * t * (3 - 2 * t))[..., None]
    a = ss(2.36, 2.42)
    b = ss(2.95, 3.03)
    lift = (1.0 - 0.25 * np.clip((V - 2.5) / 0.5, 0, 1))[..., None]
    col = wall * lift
    # partition door (−x): a frame and its window, the saloon behind (darker)
    door = np.maximum(np.abs(X + 0.62) - 0.30, np.abs(V - 2.66) - 0.30)
    col = np.where((np.abs(door) < 0.012)[..., None], col * 0.55, col)
    win = np.maximum(np.abs(X + 0.62) - 0.19, np.abs(V - 2.78) - 0.14)
    col = np.where((win < 0)[..., None], np.array((0.40, 0.41, 0.42), np.float32), col)
    # the window into the saloon in the middle
    mid = np.maximum(np.abs(X - 0.20) - 0.30, np.abs(V - 2.74) - 0.17)
    col = np.where((mid < 0)[..., None], np.array((0.38, 0.39, 0.40), np.float32), col)
    return (desk * (1 - a) + col * a) * (1 - b) + top * b


# head-on figures of the face (x, y), measured on the photos (see the docstring)
GLASS_AREA = (1.33, 1.916, 3.36, 0.22, 0.30)     # half width, y0, y1, bottom corner r, top corner r (silver frame round it;
#   owner 2026-11-04: the black ran out into the top corners. The face turns into the roof from y ≈ 3.29, so the black
#   ends just over the displays (top 3.35) with round corners (p19: r ≈ 0.3), the frame following the shoulders)
SCREEN = (1.29, 2.22, 3.07, 0.10)               # the clear windscreen inside it (half width, y0, y1, r)
FRONT_BAND = (1.557, 1.881)
LAMP_PANEL = (1.38, 1.212, 1.521, 0.10)          # half width, y0, y1, r
LAMP_UNIT = (0.63, 1.24, 1.245, 1.49)       # |x| from, to; y0, y1
HEAD = (0.790, 1.367, 0.200, 0.160)            # |x|, y, w, h (lens)
TAIL = (1.050, 1.367, 0.190, 0.150)
LEDS = (('led_runno', -0.87, 0.42, 0.17), ('led_dest', 0.0, 0.78, 0.20))
LED_Y = 3.25
SET_PLATE = (-0.93, 2.97, 0.26, 0.12)           # behind the glass: centre x, y, w, h


def paint_face(body, plate_img=None, w=2048, h=1600):
    nose = body.nose
    cv = Canvas(Body.FACE_UV, w, h)
    U, V = cv.U, cv.V
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
    for j in range(h):
        y = V[j, 0]
        i = int(np.clip(np.searchsorted(rows_y, y) - 1, 0, len(rows_y) - 2))
        t = float(np.clip((y - rows_y[i]) / max(rows_y[i + 1] - rows_y[i], 1e-6), 0, 1))
        xa = np.interp(U[j], rows_u[i], rows_x[i])
        xb = np.interp(U[j], rows_u[i + 1], rows_x[i + 1])
        X[j] = xa + (xb - xa) * t
    dxdu = np.abs(np.gradient(X, axis=1)) / cv.px
    aa = np.maximum(cv.px * dxdu, 1e-4)
    cv.fill(*LIVERY.get('frp', (FRP, 0.30, 0.55)))
    # the band(s) across the face and round the corners
    for by0, by1, bcol in LIVERY.get('front_bands', ((FRONT_BAND[0], FRONT_BAND[1], LIVERY['front']),)):
        sd = np.maximum(by0 - V, V - by1)
        cv.paint(cv.cover(sd), bcol, 0.38, 0.0)
    # the JR mark on the band (JR_FRONT)
    jr = BD._pixels(bpy.data.images.load(os.path.join(_TEXTURES, 'jr_mark.png')))
    jx, jh, jcol = JR_FRONT
    jy = (FRONT_BAND[0] + FRONT_BAND[1]) / 2
    if 'jr_front' in LIVERY:
        jx, jy, jh, jcol = LIVERY['jr_front']
    jw = jh * jr.shape[1] / jr.shape[0]
    samp, inside = BD._sample(jr, X, V, jx - jw / 2, jx + jw / 2, jy - jh / 2, jy + jh / 2)
    cv.paint(samp[..., 3] * inside, jcol, 0.35, 0.0)
    # black glass area: square-ish with rounded corners (larger at the top)
    hw, y0, y1, rb, rt = GLASS_AREA
    sd_b = SRR(X, V, 0.0, (y0 + y1) / 2, 2 * hw, y1 - y0, rb)
    sd_t = SRR(X, V, 0.0, (y0 + y1) / 2, 2 * hw, y1 - y0, rt)
    sd = np.where(V > (y0 + y1) / 2, sd_t, sd_b)
    # near the top a row of the face ends short of HW (its corners turn into the roof's shoulders): keep the frame
    # as wide as at the sides there, measured from the row's own end (with x alone the black ran out to the corners)
    edge = np.max(np.abs(X), axis=1, keepdims=True)
    sd = np.maximum(sd, np.abs(X) - (edge - (HW - hw)))
    cv.paint(cv.cover(sd + 0.010, aa), (0.10, 0.10, 0.105), 0.4, 0.0)        # the rubber gasket
    cv.paint(cv.cover(sd + 0.022, aa), GLASS, 0.06, 0.0)
    # the clear windscreen with the cab behind it
    sw, sy0, sy1, sr = SCREEN
    sds = SRR(X, V, 0.0, (sy0 + sy1) / 2, 2 * sw, sy1 - sy0, sr)
    cab = _cab_interior(V, X)
    a = cv.cover(sds, aa)[..., None]
    cv.rgb = cv.rgb * (1 - a) + cab * a * 0.88 + np.array(GLASS, np.float32) * a * 0.12
    cv.rough = cv.rough * (1 - a[..., 0]) + 0.04 * a[..., 0]
    # the defroster ledge across the lower black part
    sdl = np.maximum(np.abs(V - 2.06) - 0.008, np.abs(X) - 1.18)
    cv.paint(cv.cover(sdl, aa), (0.16, 0.16, 0.17), 0.3, 0.3)
    # the set number plate behind the glass, top left of the clear windscreen
    if plate_img is not None:
        px_, py_, pw_, ph_ = SET_PLATE
        samp, inside = BD._sample(plate_img, X, V, px_ - pw_ / 2, px_ + pw_ / 2, py_ - ph_ / 2, py_ + ph_ / 2)
        a = (inside * 0.92)[..., None]
        cv.rgb = cv.rgb * (1 - a) + samp[..., :3] * 0.8 * a
    # the lamp panel: black, rounded, slightly glossy, the two lamp units at its ends
    lw, ly0, ly1, lr = LAMP_PANEL
    sd = SRR(X, V, 0.0, (ly0 + ly1) / 2, 2 * lw, ly1 - ly0, lr)
    cv.paint(cv.cover(sd + 0.006, aa), (0.20, 0.20, 0.21), 0.35, 0.3)
    cv.paint(cv.cover(sd + 0.016, aa), (0.035, 0.035, 0.038), 0.18, 0.0)
    ux0, ux1, uy0, uy1 = LAMP_UNIT
    for s in (-1, 1):
        sdu = SRR(X, V, s * (ux0 + ux1) / 2, (uy0 + uy1) / 2, ux1 - ux0, uy1 - uy0, 0.03)
        cv.paint(cv.cover(np.abs(sdu) - 0.008, aa), (0.30, 0.30, 0.31), 0.3, 0.8)    # the unit's bezel
        for (lx, lyc, lw_, lh_), col in ((HEAD, (0.10, 0.10, 0.10)), (TAIL, (0.16, 0.035, 0.04))):
            sdl = SRR(X, V, s * lx, lyc, lw_ + 0.02, lh_ + 0.02, 0.025)
            cv.paint(cv.cover(sdl, aa), (0.06, 0.06, 0.065), 0.3, 0.0)
            sdl = SRR(X, V, s * lx, lyc, lw_, lh_, 0.02)
            cv.paint(cv.cover(sdl, aa), col, 0.12, 0.0)
    # the lower face: a crease line where the FRP turns under, the small boxes are geometry
    _line(cv, X, V, y=1.157, w=0.006, colour=(0.42, 0.42, 0.43), alpha=0.7)
    _line(cv, X, V, y=1.150, w=0.004, colour=(0.90, 0.90, 0.90), alpha=0.5, rough=0.2)
    # the notch in the FRP's lower edge over the coupler
    sd = SRR(X, V, 0.0, 1.0, 0.66, 0.20, 0.04)
    cv.paint(cv.cover(sd, aa), (0.02, 0.02, 0.022), 0.8, 0.0)
    # the FRP cover's joints to the stainless body: vertical lines just round the corners
    for s in (-1, 1):
        sdj = np.maximum(np.abs(X - s * 1.40) - 0.0025, np.maximum(1.0 - V, V - 3.40))
        cv.paint(cv.cover(sdj, aa) * 0.6, (0.40, 0.40, 0.41), 0.5, 0.3)
    return cv, X


def paint_skirt(w=1024, h=256):
    return None


# ---------------------------------------------------------------- materials


def _load(name):
    path = os.path.join(SIGNS, name)
    return bpy.data.images.load(path) if os.path.exists(path) else None


def add_materials(m, tex_dir, kinds=('cab', 'middle')):
    os.makedirs(tex_dir, exist_ok=True)
    m.add(P + 'steel', '#b4b5b3', metallic=1.0, roughness=0.34)
    m.add(P + 'roof', ROOF_GREY, roughness=0.8)
    m.add(P + 'under', '#2a2a2c', roughness=0.85)
    m.add(P + 'end', '#a9aaa8', metallic=1.0, roughness=0.42)
    m.add(P + 'jamb', '#9c9d9b', metallic=1.0, roughness=0.38)
    m.add(P + 'sill', '#c7c8c6', metallic=1.0, roughness=0.30)
    m.add(P + 'frame', '#3a3a3c', metallic=0.3, roughness=0.5)
    m.add(P + 'bellows', '#2c2c2e', roughness=0.8)
    m.add(P + 'chrome', '#d6d8db', metallic=1.0, roughness=0.18)
    m.add(P + 'black', '#111113', roughness=0.4)
    sk_col, sk_met, sk_rough = LIVERY.get('skirt', ('#c9cac7', 0.45, 0.42))
    m.add(P + 'skirt', sk_col, metallic=sk_met, roughness=sk_rough)
    m.add(P + 'lamp', '#e2e2dc', metallic=0.3, roughness=0.12)        # head lamp lens (showcase lights it)
    m.add(P + 'tail', '#3a0a0e', roughness=0.12)
    m.add(P + 'sidelamp', '#b8212a', roughness=0.2)
    # the sides of both kinds in one image, one material, and a strip above them with each car's number on a copy of
    # the side round it, and one with the JR mark (SIDE_ATLAS, DECAL_UV): decals, so they read the right way on both sides and
    # car2 carries its own
    sides = {kind: paint_side(kind) for kind in ('middle', 'cab')}
    jr = BD._pixels(bpy.data.images.load(os.path.join(_TEXTURES, 'jr_mark.png')))
    blocks = []
    for car, kind in (('car0', 'cab'), ('car1', 'middle'), ('car2', 'cab')):
        blocks.append((car, _number_block(sides[kind], _load(f'numbers_{car}.png'))))
        blocks.append((car, _jr_block(sides[kind], jr)))
    W, hs = sides['cab'].w, sides['cab'].h
    sh = max(64, max(blk[0].shape[0] for _, blk in blocks))
    H = 2 * hs + sh
    strip = [np.zeros((sh, W, 3), np.float32), np.full((sh, W), 0.34, np.float32), np.ones((sh, W), np.float32)]
    DECAL_UV.clear()
    c0 = 8
    for car, (rgb, rough, metal, extent) in blocks:
        r = rgb.shape
        strip[0][:r[0], c0:c0 + r[1]] = rgb
        strip[1][:r[0], c0:c0 + r[1]] = rough
        strip[2][:r[0], c0:c0 + r[1]] = metal
        DECAL_UV.setdefault(car, []).append(((c0 / W, (c0 + r[1]) / W, 2 * hs / H, (2 * hs + r[0]) / H), extent))
        c0 += r[1] + 16
    assert c0 <= W, 'decal strip overflow'
    SIDE_ATLAS.update({'car1': (0.0, hs / H), 'car0': (hs / H, hs / H), 'car2': (hs / H, hs / H)})
    cv = sides['cab']
    cv.rgb = np.concatenate([sides['middle'].rgb, cv.rgb, strip[0]], axis=0)
    cv.rough = np.concatenate([sides['middle'].rough, cv.rough, strip[1]], axis=0)
    cv.metal = np.concatenate([sides['middle'].metal, cv.metal, strip[2]], axis=0)
    cv.h = H
    img, mr = cv.image(P + 'side', os.path.join(tex_dir, 'side.png'))
    mat = BD.textured_material(P + 'side', img, mr)
    for kind in kinds:
        m.mats[f'{P}side_{kind}'] = mat
    boxes = {}
    if 'cab' in kinds:
        cv, _ = paint_face(Body('cab'), _load('set_plate.png'))
        img, mr = cv.image(P + 'face', os.path.join(tex_dir, 'face.png'))
        m.mats[P + 'face'] = BD.textured_material(P + 'face', img, mr)
    pieces = [(k, _load(k + '.png')) for k in ('led_runno', 'led_dest', 'led_side')]
    if all(img is not None for _, img in pieces):
        img, b = BD._atlas(P + 'led', pieces, os.path.join(tex_dir, 'led.png'))
        mat = BD.textured_material(P + 'led', img, img)
        p = mat.node_tree.nodes.get('Principled BSDF')
        tex = [n for n in mat.node_tree.nodes if n.type == 'TEX_IMAGE'][0]
        mat.node_tree.links.new(tex.outputs['Color'], p.inputs['Emission Color'])
        p.inputs['Emission Strength'].default_value = 1.0
        for n_ in [n_ for n_ in mat.node_tree.nodes if n_.type == 'SEPARATE_COLOR']:
            mat.node_tree.nodes.remove(n_)
        p.inputs['Roughness'].default_value = 0.2
        p.inputs['Metallic'].default_value = 0.0
        m.mats[P + 'led'] = mat
        boxes.update(b)
    return boxes


SIDE_ATLAS = {}     # car: v offset, v scale of its side texture in side.png (set by add_materials)
DECAL_UV = {}       # car: [((u0, u1, v0, v1) of a decal block in side.png, (z0, z1, y0, y1) it covers on the car)]
NUMBER_AT = (-1.25, 1.30)   # car numbers: left end z and bottom y on the side (car frame), cap height 0.075
# The JR mark on the sides: on the waist band, centred in the bay between doors 3 and 4 counted from the cab (both
# sides: "Series-E231-0-MU4F.jpg" right side, "Kuha E230-11 Mitaka ..." left side), 0.14 m high (≈ 0.55 of the
# Musashino orange, 0.4 of the Sōbu yellow), stainless grey; the middle car is given the same bay (not seen).
JR_SIDE = (-4.94, 0.14, (0.50, 0.51, 0.52))      # centre z, height, colour
# On the cab face: white, on the band at the right seen from ahead (+x), p04 / q42: centre x 1.12, height 0.115.
JR_FRONT = (1.12, 0.115, (0.90, 0.90, 0.90))


def _decal_block(cv, arr, z0, y0, wid, hgt, colour, rough_, metal_):
    """the side texels round a decal with the decal painted on: (rgb, rough, metal, (z0, z1, y0, y1))"""
    pad = 0.02
    us, vs = cv.U[0], cv.V[:, 0]
    cols = np.where((us >= z0 - pad) & (us <= z0 + wid + pad))[0]
    rows = np.where((vs >= y0 - pad) & (vs <= y0 + hgt + pad))[0]
    sl = (slice(rows[0], rows[-1] + 1), slice(cols[0], cols[-1] + 1))
    rgb, rough, metal = cv.rgb[sl].copy(), cv.rough[sl].copy(), cv.metal[sl].copy()
    samp, inside = BD._sample(arr, cv.U[sl], cv.V[sl], z0, z0 + wid, y0, y0 + hgt)
    a = samp[..., 3] * inside
    rgb = rgb * (1 - a[..., None]) + np.array(colour, np.float32) * a[..., None]
    rough = rough * (1 - a) + rough_ * a
    metal = metal * (1 - a) + metal_ * a
    du, dv = us[1] - us[0], vs[1] - vs[0]
    extent = (us[cols[0]] - du / 2, us[cols[-1]] + du / 2, vs[rows[0]] - dv / 2, vs[rows[-1]] + dv / 2)
    return rgb, rough, metal, extent


def _number_block(cv, img):
    arr = BD._pixels(img) if not isinstance(img, np.ndarray) else img
    nh, nw = arr.shape[:2]
    hgt = 0.075 * nh / max(1, nh - 8)
    wid = hgt * nw / nh
    return _decal_block(cv, arr, NUMBER_AT[0], NUMBER_AT[1], wid, hgt, (0.06, 0.06, 0.065), 0.5, 0.0)


def _jr_block(cv, img):
    arr = BD._pixels(img) if not isinstance(img, np.ndarray) else img
    nh, nw = arr.shape[:2]
    zc, hgt, colour = JR_SIDE
    colour = LIVERY.get('jr_side', colour)
    wid = hgt * nw / nh
    y0 = LIVERY['waist'][0][0] + (LIVERY['waist'][0][1] - LIVERY['waist'][0][0] - hgt) / 2
    metal = 0.0 if 'jr_side' in LIVERY else 1.0      # a white film mark (Jōban) or stainless grey
    return _decal_block(cv, arr, zc - wid / 2, y0, wid, hgt, colour, 0.30, metal)


def number_decals(part, car, kind):
    """the car number and the JR mark on both sides: quads 3 mm off the side, their texels from the decal strip of
    side.png (after atlas_uvs); on the left side (+x) the texture runs the other way, so they still read left to
    right"""
    mat = P + ('side_cab' if kind == 'cab' else 'side_middle')
    for (u0, u1, v0, v1), (z0, z1, y0, y1) in DECAL_UV[car]:
        for s in (-1, 1):
            xa, xb = s * (side_x(y0) + 0.003), s * (side_x(y1) + 0.003)
            pts = [(xa, y0, z0), (xa, y0, z1), (xb, y1, z1), (xb, y1, z0)]
            ua, ub = (u0, u1) if s < 0 else (u1, u0)
            uvs = [(ua, v0), (ub, v0), (ub, v1), (ua, v1)]
            part.face_uv(pts, mat, uvs, smooth=False, out=(s, 0.0, 0.0))


def build(part, kind):
    Body(kind).build(part)


def atlas_uvs(part, car):
    """move the side faces' v into the car's third of the side atlas (once the body and its fittings are built)"""
    off, sc = SIDE_ATLAS[car]
    for f in part.bm.faces:
        if part.slots[f.material_index] in (P + 'side_cab', P + 'side_middle'):
            for loop in f.loops:
                uv = loop[part.uv].uv
                loop[part.uv].uv = (uv[0], off + sc * min(1.0, max(0.0, uv[1])))


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


def _round_rect_on_face(part, mat, cx, cy, w, h, r, lift, seg=4):
    ring_ = []
    for qx, qy, a in ((1, 1, 0.0), (-1, 1, 90.0), (-1, -1, 180.0), (1, -1, 270.0)):
        ox, oy = cx + qx * (w / 2 - r), cy + qy * (h / 2 - r)
        for k in range(seg + 1):
            t = math.radians(a + 90.0 * k / seg)
            ring_.append(_on_face(ox + r * math.cos(t), oy + r * math.sin(t), lift))
    c = _on_face(cx, cy, lift)
    for a, b in zip(ring_, ring_[1:] + ring_[:1]):
        part.face_uv([c, a, b], mat, [(0, 0)] * 3, out=(0, 0.2, 1))


def _lens(part, mat, cx, cy, w, h, r, depth, lift_rim):
    """a lamp lens sunk `depth` behind a rim at `lift_rim` (a short tube of side faces + the lens)"""
    ring_out, ring_in = [], []
    seg = 3
    for qx, qy, a in ((1, 1, 0.0), (-1, 1, 90.0), (-1, -1, 180.0), (1, -1, 270.0)):
        ox, oy = cx + qx * (w / 2 - r), cy + qy * (h / 2 - r)
        for k in range(seg + 1):
            t = math.radians(a + 90.0 * k / seg)
            px, py = ox + r * math.cos(t), oy + r * math.sin(t)
            ring_out.append(_on_face(px, py, lift_rim))
            ring_in.append(_on_face(px, py, lift_rim - depth))
    nn = len(ring_out)
    for k in range(nn):
        a, b = ring_out[k], ring_out[(k + 1) % nn]
        c, d = ring_in[(k + 1) % nn], ring_in[k]
        mid = Vector([(a[q] + b[q]) / 2 for q in range(3)])
        part.face_uv([a, b, c, d], P + 'black', [(0, 0)] * 4, smooth=False, out=mid - Vector((cx, cy, mid.z + 0.5)))
    c = _on_face(cx, cy, lift_rim - depth)
    for k in range(nn):
        part.face_uv([c, ring_in[k], ring_in[(k + 1) % nn]], mat, [(0, 0)] * 3, smooth=False, out=(0, 0.1, 1))


def cab_fittings(part, boxes):
    """front displays behind the glass, head and tail lamp lenses, wipers, the small boxes at the lower corners"""
    for key, cx, w, h in LEDS:
        if key in boxes:
            _quad_on_face(part, P + 'led', cx - w / 2, cx + w / 2, LED_Y - h / 2, LED_Y + h / 2, boxes[key], 0.002)
    for s in (-1, 1):
        hx, hy, hw, hh = HEAD
        _lens(part, P + 'lamp', s * hx, hy, hw - 0.02, hh - 0.02, 0.018, 0.010, 0.016)
        tx, ty, tw, th = TAIL
        _lens(part, P + 'tail', s * tx, ty, tw - 0.02, th - 0.02, 0.018, 0.010, 0.016)
    # wipers: two arms parked low, pivots in the lower black part, lying up and to the left (photos p02-p04, p19)
    for px_, py_ in ((0.22, 2.13), (0.97, 2.13)):
        a = math.radians(157.0)
        length = 0.92
        x1, y1 = px_ + length * math.cos(a), py_ + length * math.sin(a)
        steps = 6
        prev = None
        for k in range(steps + 1):
            t = k / steps
            p = _on_face(px_ + (x1 - px_) * t, py_ + (y1 - py_) * t, 0.014)
            if prev is not None:
                part.beam(P + 'black', prev, p, 0.014, 0.010)
            prev = p
        # the blade along the arm's outer two thirds
        for k in range(2, steps):
            t0, t1 = k / steps, (k + 1) / steps
            pa = _on_face(px_ + (x1 - px_) * t0, py_ + (y1 - py_) * t0 - 0.012, 0.010)
            pb = _on_face(px_ + (x1 - px_) * t1, py_ + (y1 - py_) * t1 - 0.012, 0.010)
            part.beam(P + 'black', pa, pb, 0.020, 0.008)
        part.cylinder(P + 'black', _on_face(px_, py_, 0.012), 0.028, 0.03, axis='z', segments=10)
    # the small white boxes under the face's lower corners: e231_coupler.front_coupler(corner_boxes=True)


def side_fittings(part, boxes, kind):
    """side destination displays, side lamps, the crew doors' handles and grab rails"""
    for side in (-1, 1):
        sz = 1 if side < 0 else -1
        zc, yc, w, h = SIDE_SIGN
        zc *= sz
        if 'led_side' in boxes:
            u0, v0, u1, v1 = boxes['led_side']
            iw, ih = 0.62, 0.138
            x = side * (HW + 0.004)
            pts = [(x, yc - ih / 2, zc - iw / 2), (x, yc - ih / 2, zc + iw / 2), (x, yc + ih / 2, zc + iw / 2), (x, yc + ih / 2, zc - iw / 2)]

            def uu(z):
                t = (z - (zc - iw / 2)) / iw
                return u0 + (u1 - u0) * ((1 - t) if side > 0 else t)
            part.face_uv(pts, P + 'led', [(uu(p[2]), v0 + (v1 - v0) * (p[1] - (yc - ih / 2)) / ih) for p in pts], out=(side, 0, 0))
            # the dark rounded surround, standing a little proud of the side
            x0_, x1_ = sorted((side * (HW - 0.004), side * (HW + 0.002)))
            part.box(P + 'black', x0_, x1_, yc - h / 2, yc + h / 2, zc - w / 2, zc + w / 2, bevel=0.002, segments=1)
            for zz in (zc - w / 2 - 0.015, zc + w / 2 + 0.015):
                part.box(P + 'steel', *sorted((side * (HW - 0.002), side * (HW + 0.008))), yc - h / 2 - 0.01, yc + h / 2 + 0.01, zz - 0.012, zz + 0.012)
        lz, ly, lr = SIDE_LAMP
        lz *= sz
        part.cylinder(P + 'steel', (side * (HW + 0.004), ly, lz), lr + 0.012, 0.010, axis='x', segments=14)
        part.cylinder(P + 'sidelamp', (side * (HW + 0.012), ly, lz), lr, 0.012, axis='x', segments=14)
    if kind != 'cab':
        return
    cz0, cz1, cy0, cy1 = CREW_DOOR
    for side in (-1, 1):
        x = side * HW
        # a long vertical grab rail just ahead of the crew door (its hinge side) on stand-offs
        zr = cz1 + 0.06
        ya, yb = 1.30, 2.55
        part.cylinder(P + 'chrome', (x + side * 0.045, (ya + yb) / 2, zr), 0.013, yb - ya, axis='y', segments=10)
        for yy in (ya + 0.03, yb - 0.03):
            part.cylinder(P + 'chrome', (x + side * 0.022, yy, zr), 0.009, 0.045, axis='x', segments=8)
        # door handle (lever on a plate) at the rear edge
        part.box(P + 'steel', *sorted((x, x + side * 0.006)), 1.98, 2.10, cz0 + 0.05, cz0 + 0.11, bevel=0.003, segments=1)
        part.box(P + 'chrome', *sorted((x + side * 0.006, x + side * 0.03)), 2.03, 2.05, cz0 + 0.05, cz0 + 0.17, bevel=0.004, segments=1)
        # the foot step below the crew door
        part.box(P + 'frame', *sorted((x - side * 0.10, x + side * 0.01)), 0.80, 0.83, cz0 + 0.05, cz1 - 0.05)
        for zz in (cz0 + 0.07, cz1 - 0.07):
            part.box(P + 'frame', *sorted((x - side * 0.06, x + side * 0.005)), 0.83, 1.00, zz - 0.012, zz + 0.012)


# ---------------------------------------------------------------- the skirt (strengthened V type)

SKIRT_TOP = 0.69
SKIRT_NOTCH = (0.51, 0.53, 0.73)     # notch bottom y, half width at its bottom, half width at the top edge
SKIRT_BOTTOM = 0.16
SKIRT_T = 0.008
SKIRT_TIP = 9.94                     # the V's point (centre of its lower edge) — just behind the coupler face
SKIRT_CORNER = (1.15, 9.80)          # where the front panels meet the rounded corners (x, z)
SKIRT_SIDE = (1.34, 9.45)            # the wings' rear end (x, z)


def _skirt_outline():
    """the skirt's plan outline [(s, x, z, nx, nz)] from the right wing's back (−x) round the V to the left wing's back"""
    cxr, czr = SKIRT_CORNER
    bx, bz = SKIRT_SIDE

    def corner(sign):
        out = []
        for k in range(1, 9):
            t = k / 8
            x = (1 - t) ** 2 * cxr + 2 * (1 - t) * t * bx + t * t * bx
            z = (1 - t) ** 2 * czr + 2 * (1 - t) * t * (czr - 0.04) + t * t * bz
            out.append((sign * x, z))
        return out
    xs = sorted(set([round(-cxr + 2 * cxr * k / 14, 6) for k in range(15)] + [-SKIRT_NOTCH[2], -SKIRT_NOTCH[1], 0.0, SKIRT_NOTCH[1], SKIRT_NOTCH[2]]))
    front = [(x, SKIRT_TIP - (SKIRT_TIP - czr) * abs(x) / cxr) for x in xs]
    pts = list(reversed(corner(-1))) + front + corner(1)
    p = np.array(pts)
    seg = np.linalg.norm(np.diff(p, axis=0), axis=1)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    s -= np.interp(0.0, p[:, 0], s)
    t = np.gradient(p, axis=0)
    t /= np.linalg.norm(t, axis=1)[:, None]
    nrm = np.stack([-t[:, 1], t[:, 0]], 1)
    if np.mean(nrm[:, 1][np.abs(p[:, 0]) < 0.5]) < 0:
        nrm = -nrm
    return [(float(a), float(b[0]), float(b[1]), float(c[0]), float(c[1])) for a, b, c in zip(s, p, nrm)]


def _skirt_top(x):
    """top edge: level at the sides, sloping down into the notch round the coupler"""
    ax = abs(x)
    yb, w0, w1 = SKIRT_NOTCH
    if ax <= w0:
        return yb
    if ax >= w1:
        return SKIRT_TOP
    return yb + (SKIRT_TOP - yb) * (ax - w0) / (w1 - w0)


def _skirt_bottom(x, z):
    """bottom edge: level across the front, rising along the wings"""
    return SKIRT_BOTTOM + 0.28 * K.smoothstep(SKIRT_CORNER[1], SKIRT_SIDE[1], z) if abs(x) > SKIRT_CORNER[0] - 1e-6 else SKIRT_BOTTOM


def skirt(part):
    ol = _skirt_outline()

    def pos(o, y, back=0.0):
        _, x, z, nx, nz = o
        return (x - nx * back, y, z - nz * back)

    for a, b in zip(ol[:-1], ol[1:]):
        ya0, yb0 = _skirt_bottom(a[1], a[2]), _skirt_bottom(b[1], b[2])
        ya1, yb1 = _skirt_top(a[1]), _skirt_top(b[1])
        nrm = Vector((a[3] + b[3], 0, a[4] + b[4]))
        rows = 3
        for j in range(rows):
            t0, t1 = j / rows, (j + 1) / rows
            for back, flip in ((0.0, False), (SKIRT_T, True)):
                pts = [pos(a, ya0 + (ya1 - ya0) * t0, back), pos(b, yb0 + (yb1 - yb0) * t0, back),
                       pos(b, yb0 + (yb1 - yb0) * t1, back), pos(a, ya0 + (ya1 - ya0) * t1, back)]
                part.face_uv(pts, P + 'skirt', [(0, 0)] * 4, smooth=True, out=(-nrm if flip else nrm))
        part.face_uv([pos(a, ya0), pos(b, yb0), pos(b, yb0, SKIRT_T), pos(a, ya0, SKIRT_T)], P + 'skirt', [(0, 0)] * 4, smooth=False, out=(0, -1, 0))
        part.face_uv([pos(a, ya1), pos(b, yb1), pos(b, yb1, SKIRT_T), pos(a, ya1, SKIRT_T)], P + 'skirt', [(0, 0)] * 4, smooth=False, out=(0, 1, 0))
    for o in (ol[0], ol[-1]):
        yb = _skirt_bottom(o[1], o[2])
        yt = _skirt_top(o[1])
        part.face_uv([pos(o, yb), pos(o, yt), pos(o, yt, SKIRT_T), pos(o, yb, SKIRT_T)], P + 'skirt', [(0, 0)] * 4, smooth=False, out=(0, 0, -1))
    # stays: the skirt hangs from the underframe on vertical brackets behind its upper edge
    for xs in (-0.95, -0.62, 0.62, 0.95):
        o = min(ol, key=lambda q: abs(q[1] - xs))
        x, _, z = pos(o, 0.0, 0.05)
        top = _skirt_top(xs)
        part.box(P + 'frame', x - 0.03, x + 0.03, top - 0.20, 1.00, z - 0.06, z + 0.0)
    # a dark end beam behind it all, so the view under the face ends in shadow
    for s_ in (-1, 1):
        part.box(P + 'under', *sorted((s_ * 0.36, s_ * 1.30)), 0.62, 1.00, 9.40, 9.46)
