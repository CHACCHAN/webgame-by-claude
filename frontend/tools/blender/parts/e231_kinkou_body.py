"""
Body shell of the JR East E231 series 近郊タイプ (1000番台, Shōnan colours) as it runs today on the Tōkaidō / Utsunomiya /
Takasaki lines and the Ueno-Tokyo Line: the wide stainless body with its tapered lower sides (the commuter type's
section), the gangway ends, the high cab with its crash-zone structure (FRP cover, tall black glass with the headlamps
and the line display behind its top, the lamp panel with the tail lamps under the bands, a ledge along the bottom), the
passenger and crew doors, the skirt (strengthened V type with the deep notch for the electric coupler) and the painted
textures (stainless, the orange-over-green waist bands and the green band under the gutter, windows, the face). The
section, the shell sweep, the doors, the decals and the painting helpers are copied from parts/e231_body.py (E231-0)
and changed where the 1000番台 differs. Material prefix `kn_`.

API (the game's car frame of train_kit: x left, y up, z forward, metres; a cab car has its cab at +z)
  add_materials(m, tex_dir) -> LED atlas boxes      paints side.png / face.png into tex_dir
  build(part, kind)                                 kind 'cab' | 'middle' (part: a UVPart)
  cab_fittings(part, boxes)                         displays behind the glass, lamp lenses, wipers, bottom ledge
  side_fittings(part, boxes, kind)                  side LED displays, side lamps, crew-door rail / handle / step
  skirt(part)
  atlas_uvs(part, car), number_decals(part, car, kind)
  half_profile(), side_x(y), face_z(x, y), CAB_JOIN, END, P

Figures (ja.wikipedia JR東日本E231系電車, read 2026-11-04; the wikitext is in the scratch folder):
- car 20,000 mm over the couplers (all ordinary cars), body width 2,950, roof 3,655, floor 1,165 (door sill tip
  1,150), bogie centres 13,800 (as the commuter type: "通勤・近郊タイプの基本仕様を統一").
- 近郊タイプ: crash-zone structure after the E217; the cab 2,300 mm deep (commuter type 1,860), the driver's floor
  520 mm (335); headlamps above the windscreen (HID, renewed as LED from 2025: "前照灯LED化"); electric couplers on the
  cab cars (except クハE230-8000 of the 10-car sets); Shōnan colours #f68b1e (黄かん色) and #009900 (JR East green).
- The 5-car add-on set: 15 クハE231-8000 (semi-cross seats), 14 サハE231-3000, 13 モハE231-1000 ("＞": the PS33B at
  its end towards モハE230), 12 モハE230-1000, 11 クハE230-6000 (long seats, toilet). The game shows 15 / 13 / 11.
Measured on photos (Commons, scratch list.json). Method: a camera fitted to each photo (least squares over eye, aim,
roll and focal length through points of known position: door edges, band edges, the gutter, the gangway end) and the
render overlaid on the photo at 50 % until the edges sit on each other; heights from the body side 1.00 … gutter 3.24,
the 1,850 mm door and the coupler 0.88; head-on x from the 2.95 m face width.
- "JRE Series-E231-1000 S-13.jpg" (MaedaAkihiko, CC BY-SA 4.0), a 200 mm telephoto almost head-on: black glass
  |x| ≤ 1.33, y 1.94–3.51, corner r ≈ 0.22 (bottom) / 0.20 (top); the black frit over its top from 3.16 (line
  display, headlamps) with a blue tinted strip under it from 3.06, the clear windscreen under that down to the wiper
  ledge 2.10–2.17; headlamps at x ±0.92, y 3.325 (round, lens ∅ 0.08 lit, dark housing ∅ 0.13); line display
  0.84 × 0.26 (lit 0.78 × 0.195) centred at y 3.325; set plate x −1.09, y 2.49 (0.26 × 0.10); run-number box x −0.94,
  y 2.29 (0.42 × 0.12); wiper pivots (0.24, 2.105) and (1.02, 2.105), both arms lying up and to the left; bands:
  green 1.51–1.70, orange 1.70–1.83 (also on the cab section of the sides); JR mark on the green at x +1.12, 0.12
  high; lamp panel |x| ≤ 1.295, y 1.205–1.48; lamp units |x| 0.61–1.215, y 1.225–1.46; tail lenses at x ±0.92,
  y 1.335, 0.20 × 0.115; the FRP's lower ledge y 0.975–1.10 (|x| 0.325–1.27, notch for the coupler); skirt top
  0.665 at the sides, its notch down to 0.32 (half width 0.345 at the bottom, 0.375 at the top).
- "E231-1000 Series Kuha E231-8016 of JR East.jpg" (Hyper Maniac Man, CC BY-SA 4.0), side of a クハE231-8000 (camera
  fit with the lens fixed at 32 mm: the side's points alone are coplanar): door 1 at z ≈ 6.0 (pitch to door 2 ≈ 3.5 m:
  the longer cab), one small window 0.76 wide between doors 1 and 2, crew door 7.82–8.36, cab side window
  8.65–9.35; side bands: top green 3.05–3.21 (under the gutter, over the doors, under the side display), waist
  orange 1.70–1.82 over green 1.43–1.70 (stopping at the doors), on the cab section ahead of the crew door green
  1.51–1.70 / orange 1.70–1.83 as on the face; windows 1.95–2.90 (door windows 1.99–2.90); side display centred over
  the bay between doors 2 and 3.
- "JRE Series-E231 K04.jpg" (MaedaAkihiko, CC0), front three-quarter: the face's plan bulge and rake, the corner
  radius, the cab section's bands and the crew door against the overlay.
- "E231 E233 coupling.JPG" (E217, CC0), the cab end of a クハ (定員 138) square on: the FRP cover's joint to the
  stainless side (z 9.38), the cab side window with a divider in the middle, the crew door green down to the bottom
  of the green band (1.43) with a stainless kick plate and step slot under it, its window 2.06–2.86; the face almost
  vertical, the top rounded.
- "Treinstel E231 U514 … 1892E … 2026" (dusk, lamps lit, near head-on) and "Stoptrein naar Utsunomiya (543M) …
  2026" (night, tail lamps lit), both トトト, CC BY-SA 2.1 jp, for today's look (LED headlamps in the old housings,
  the orange 上野東京ライン display) and the night check; "JREast-E231-1000-LEDBoard.jpg" / "E231系 側面方向幕
  東海道線.JPG" for the displays.
Estimates: the face's rake and plan bulge (CAB_PROFILE, CAB_BULGE), the corner radii (0.24 at the sides, 0.10 at the
top: kept under the roof shoulder's 0.36, a larger one folds the columns' ends), the bottom ledge's depth, the door 1
position (±0.1), the window between doors 1 and 2 (the same on both sides), the toilet of クハE230-6000 (not shown:
its window side was not found on a photo), the side lamps (kept where the E231-0 has them), the cab interior, the
photos' roll (≤ 1.8°, fitted).
"""
import math
import os

import bmesh  # noqa: F401
import bpy
import numpy as np
from mathutils import Vector

import train_kit as K
import body_n1000 as BD

P = 'kn_'
UVPart = BD.UVPart

# ---------------------------------------------------------------- dimensions (the commuter type's section)
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
DOORS_CAB = (-7.41, -2.47, 2.47, 6.00)
WIN = (1.95, 2.90)      # side windows
DWIN = (1.99, 2.90)     # door windows
TOP_BAND = (3.05, 3.21)
CREW_DOOR = (7.82, 8.36, 1.07, 2.98)       # z0, z1, y0, y1 (hinged, green down to the waist band's bottom)
CREW_WIN = (2.06, 2.86)
CAB_WIN = (8.65, 9.35, 2.44, 2.97)         # the cab's side window (two panes)
SMALL_WIN = 0.76                           # the window between doors 1 and 2 of a cab car
# side destination display and side lamp (right side, −x; the left side has them point-symmetric)
SIDE_SIGN = (0.0, 3.13, 0.70, 0.19)        # centre z, centre y, frame width, frame height
SIDE_LAMP = (0.62, 3.13, 0.035)

# the cab end: centre-line profile of the face (y, z), its plan bulge, the corner radii
CAB_PROFILE = [(0.96, 9.800), (1.20, 9.805), (1.50, 9.808), (1.90, 9.806), (2.30, 9.800), (2.90, 9.790), (3.40, 9.776),
               (3.70, 9.762)]
CAB_BULGE = 0.05
CAB_R_SIDE = 0.24
CAB_R_TOP = 0.10
CAB_JOIN = 9.30
FRP_JOINT = 9.38          # the FRP cab cover's joint to the stainless side (photo "E231 E233 coupling")
END_R = 0.05

# paint (sRGB floats)
STEEL = (0.700, 0.705, 0.700)       # stainless, dull finish (metallic)
FRP = (0.735, 0.738, 0.732)         # the cab cover's silver paint
ORANGE = (0.965, 0.545, 0.118)      # #f68b1e 黄かん色
GREEN = (0.0, 0.60, 0.0)            # #009900
GLASS = (0.035, 0.040, 0.044)
SIDE_GLASS = (0.105, 0.125, 0.122)  # the saloon seen dimly through the green-tinted side windows
GASKET = (0.060, 0.060, 0.062)
BLACK = (0.030, 0.030, 0.033)
ROOF_GREY = '#9a9a96'

# the bands: waist on the passenger part, waist on the cab section (as on the face), the band under the gutter
WAIST = ((1.70, 1.82, ORANGE), (1.43, 1.70, GREEN))
WAIST_CAB = ((1.70, 1.83, ORANGE), (1.51, 1.70, GREEN))
FRONT_BANDS = ((1.70, 1.83, ORANGE), (1.51, 1.70, GREEN))

_TEXTURES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'textures', 'e231', 'kinkou')
SIGNS = _TEXTURES


# ---------------------------------------------------------------- the section


def side_x(y):
    """half width of the side at height y (below the eave)"""
    if y >= CREASE:
        return HW
    t = (CREASE - min(max(y, BOTTOM), CREASE)) / (CREASE - BOTTOM)
    return HW - TAPER * t ** 1.6


def _side_nx(y):
    """outward normal (nx, ny) of the side at height y"""
    if y >= CREASE:
        return 1.0, 0.0
    t = (CREASE - y) / (CREASE - BOTTOM)
    dxdy = TAPER * 1.6 * t ** 0.6 / (CREASE - BOTTOM)
    n = math.hypot(1.0, dxdy)
    return 1.0 / n, -dxdy / n


def _roof_geometry():
    r = SHOULDER
    a = HW - r
    b = EAVE - ROOF
    rr = (r * r - a * a - b * b) / (2 * b + 2 * r)
    theta = math.atan2(EAVE - (ROOF - rr), a)
    return rr, theta


def half_profile():
    """[(x, y, nx, ny)] from the bottom of the left side (+x) up to the roof's centre line"""
    pts = []
    ys = [BOTTOM, 1.07, 1.15, 1.25, 1.36, 1.43, 1.51, 1.60, 1.70, CREASE, 1.83, 1.95, 2.10, 2.30, 2.50, 2.70, 2.90,
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
    return CAB_R_SIDE + (CAB_R_TOP - CAB_R_SIDE) * K.smoothstep(3.30, 3.58, y)


def surface_z(x, y):
    """the cab face's z at head-on (x, y), the rounded corner included (for parts laid on the face)"""
    sx = side_x(y)
    r = corner_radius(y)
    ax = abs(x)
    if ax <= sx - r:
        return face_z(x, y)
    c = min(1.0, max(0.0, 1.0 - (sx - ax) / r))
    phi = math.acos(c)
    return face_z(x, y) - r * (1.0 - math.sin(phi))


class Nose(BD.Nose):
    """the Keikyu nose (quarter-round columns into a raked, bulged face) on this section"""

    def __init__(self, steps=10, across=32):
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
        # vertical downpipes at the corners, the joint between the end sheet and the roof
        for s in (-1, 1):
            x = s * (side_x(2.0) - 0.07)
            part.cylinder(P + 'steel', (x, (BOTTOM + 0.15 + EAVE) / 2, z_end + sign * 0.03), 0.022,
                          EAVE - BOTTOM - 0.15, axis='y', segments=8)
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
    """the car's half of the gangway bellows"""
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


def _line(cv, U, V, z=None, y=None, w=0.003, lo=None, hi=None, colour=(0.30, 0.30, 0.30), alpha=0.5, rough=0.5, aa=None):
    if z is not None:
        sd = np.abs(U - z) - w / 2
        if lo is not None:
            sd = np.maximum(sd, np.maximum(lo - V, V - hi))
    else:
        sd = np.abs(V - y) - w / 2
        if lo is not None:
            sd = np.maximum(sd, np.maximum(lo - U, U - hi))
    cv.paint((cv.cover(sd, aa) * alpha).astype(np.float32), colour, rough)


def _band(y0, y1, colour):
    return y0, y1, colour


def paint_side(kind, w=4096, h=512):
    """the side texture (u = z, v = y), shared by both sides (the left side mirrors it) and the door leaves"""
    cv = Canvas(Body.SIDE_UV, w, h)
    U, V = cv.U, cv.V
    cab = kind == 'cab'
    doors = DOORS_CAB if cab else DOORS_MID
    grain = (np.sin(V * 2900.0) * 0.5 + np.sin(V * 1210.0 + 1.3) * 0.5) * 0.008
    cv.fill(STEEL, 0.34, 1.0)
    cv.rgb += grain[..., None].astype(np.float32)
    # the lower panel below the crease is a separate sheet, a touch darker
    cv.paint((V < CREASE - 0.02).astype(np.float32) * 0.35, (0.66, 0.665, 0.66), 0.36, 1.0)
    z_end0 = -END + 0.04
    z_end1 = FRP_JOINT if cab else END - 0.04
    if cab:
        # the FRP cab cover from the joint forward: painted silver like the face, not stainless
        a = np.clip((U - FRP_JOINT) / cv.px + 0.5, 0, 1).astype(np.float32)
        cv.paint(a, FRP, 0.30, 0.55)
        _line(cv, U, V, z=FRP_JOINT, w=0.006, lo=BOTTOM, hi=EAVE, colour=(0.30, 0.30, 0.31), alpha=0.7)

    def in_doors(margin):
        m = np.zeros_like(U, dtype=bool)
        for zd in doors:
            m |= np.abs(U - zd) < DOOR_W / 2 + margin
        return m

    # the green band under the gutter, along the whole side (over the doors; the display stands on it)
    sd = np.maximum(np.maximum(TOP_BAND[0] - V, V - TOP_BAND[1]), np.maximum(z_end0 - U, U - z_end1))
    cv.paint(cv.cover(sd), GREEN, 0.42, 0.0)
    # waist bands: orange over green, stopping at the door openings (a little steel margin); on a cab car the cab
    # section ahead of the crew door carries the face's narrower green
    off = in_doors(0.035).astype(np.float32)
    cz0, cz1, cy0, cy1 = CREW_DOOR
    zw1 = (cz0 - 0.05) if cab else z_end1
    for y0, y1, col in WAIST:
        sd = np.maximum(np.maximum(y0 - V, V - y1), np.maximum(z_end0 - U, U - zw1))
        cv.paint(cv.cover(sd) * (1 - off), col, 0.42, 0.0)
    if cab:
        for y0, y1, col in WAIST_CAB:
            sd = np.maximum(np.maximum(y0 - V, V - y1), cz1 + 0.05 - U)
            cv.paint(cv.cover(sd), col, 0.42, 0.0)
        # the crew door: green from the top down to the waist band's bottom, a stainless kick plate under it
        sd = np.maximum(SRR(U, V, (cz0 + cz1) / 2, (cy0 + cy1) / 2, cz1 - cz0, cy1 - cy0, 0.04), WAIST[1][0] - V)
        cv.paint(cv.cover(sd), GREEN, 0.40, 0.0)
    # the crease above the waist band: a bright line over a shadow
    _line(cv, U, V, y=CREASE + 0.024, w=0.006, colour=(0.86, 0.86, 0.86), alpha=0.5, rough=0.25)

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
            zd0, zd1 = (zm + 0.035, z1 - 0.022)
            sdd = np.abs(SRR(U, V, (zd0 + zd1) / 2, cy, zd1 - zd0, hh - 0.044, 0.04)) - 0.006
            cv.paint(cv.cover(sdd) * 0.8, (0.48, 0.49, 0.49), 0.3, 1.0)
            sdt = np.maximum(np.abs(V - (y1 - 0.20)) - 0.012, np.maximum(zd0 - U, U - zd1))
            cv.paint(cv.cover(sdt) * 0.9, (0.42, 0.43, 0.43), 0.3, 1.0)

    gaps = list(zip(doors[:-1], doors[1:]))
    for a, b in gaps:
        c = (a + b) / 2
        if b - a > 4.5:
            window(c - 0.93, c + 0.93, mullion=c)
        else:      # the cab car's short bay between doors 1 and 2: one small fixed window
            window(c - SMALL_WIN / 2, c + SMALL_WIN / 2)
    window(-END + 0.20, -END + 0.98)
    if not cab:
        window(END - 0.98, END - 0.20)
    # door openings: a raised frame round the leaves (bright edge, shadow line), rounded at the top
    for zd in doors:
        sd = SRR(U, V, zd, (SILL + DOOR_TOP) / 2 + 0.03, DOOR_W + 0.08, DOOR_TOP - SILL + 0.10, 0.07)
        ring_ = np.abs(sd + 0.02) - 0.02
        cv.paint(cv.cover(ring_) * 0.55, (0.83, 0.83, 0.82), 0.22, 1.0)
        cv.paint(cv.cover(np.abs(sd + 0.002) - 0.003) * 0.7, (0.25, 0.25, 0.26), 0.5, 0.0)
        for s in (-1, 1):
            zc = zd + s * DOOR_W / 4
            sd = SRR(U, V, zc, sum(DWIN) / 2, 0.36, DWIN[1] - DWIN[0], 0.11)
            inside = (np.abs(U - zd) < DOOR_W / 2) & (V > SILL) & (V < DOOR_TOP)
            cv.paint(cv.cover(sd + 0.004) * inside, (0.86, 0.86, 0.86), 0.22, 1.0)
            cv.paint(cv.cover(sd) * inside, GASKET, 0.45, 0.0)
            cv.paint(cv.cover(sd + 0.020) * inside, SIDE_GLASS, 0.05, 0.0)
            _line(cv, U, V, z=zd + s * (DOOR_W / 2 - 0.05), w=0.004, lo=SILL + 0.06, hi=DOOR_TOP - 0.06, colour=(0.85, 0.85, 0.85), alpha=0.5, rough=0.25)
        for zl, wl in ((zd, 0.012), (zd - DOOR_W / 2 + 0.008, 0.016), (zd + DOOR_W / 2 - 0.008, 0.016)):
            sd = np.maximum(np.abs(U - zl) - wl / 2, np.maximum(SILL - V, V - DOOR_TOP))
            cv.paint(cv.cover(sd), GASKET, 0.6, 0.0)
        for zz in (zd - DOOR_W / 2 - 0.10, zd + DOOR_W / 2 + 0.10):
            _vdots(cv, U, V, zz, 1.95, 2.95)
        # the door button for the half-automatic doors (寒冷地仕様): a small plate beside the opening
        zb = zd + DOOR_W / 2 + 0.11
        sd = SRR(U, V, zb, 2.12, 0.050, 0.15, 0.008)
        cv.paint(cv.cover(sd), (0.80, 0.81, 0.80), 0.3, 0.6)
        cv.paint(cv.cover(np.sqrt((U - zb) ** 2 + (V - 2.09) ** 2) - 0.014), (0.86, 0.50, 0.12), 0.4, 0.0)
        cv.paint(cv.cover(SRR(U, V, zb, 2.165, 0.026, 0.024, 0.004)), (0.15, 0.15, 0.16), 0.4, 0.0)
    _dots(cv, U, V, 2.97, z_end0, z_end1)
    _dots(cv, U, V, 1.88, z_end0, z_end1)
    _dots(cv, U, V, TOP_BAND[0] - 0.035, z_end0, z_end1)
    _dots(cv, U, V, 1.25, z_end0, z_end1, pitch=0.07)
    for a, b in gaps:
        c = (a + b) / 2
        if b - a > 4.5:
            for zz in (c - 1.30, c + 1.30):
                _line(cv, U, V, z=zz, w=0.003, lo=CREASE + 0.04, hi=TOP_BAND[0] - 0.01, colour=(0.45, 0.45, 0.46), alpha=0.5)
    if cab:
        # the crew door: outline, its window, the step slot in the kick plate
        sd = SRR(U, V, (cz0 + cz1) / 2, (cy0 + cy1) / 2, cz1 - cz0, cy1 - cy0, 0.04)
        cv.paint(cv.cover(np.abs(sd) - 0.006), GASKET, 0.6, 0.0)
        cv.paint(cv.cover(np.abs(sd + 0.016) - 0.004) * 0.5, (0.80, 0.86, 0.80), 0.25, 0.0)
        sd = SRR(U, V, (cz0 + cz1) / 2, sum(CREW_WIN) / 2, 0.36, CREW_WIN[1] - CREW_WIN[0], 0.05)
        cv.paint(cv.cover(sd + 0.004), (0.86, 0.86, 0.86), 0.22, 1.0)
        cv.paint(cv.cover(sd), GASKET, 0.45, 0.0)
        cv.paint(cv.cover(sd + 0.016), SIDE_GLASS, 0.05, 0.0)
        sd = SRR(U, V, (cz0 + cz1) / 2, 1.27, 0.30, 0.06, 0.012)
        cv.paint(cv.cover(np.abs(sd) - 0.006), (0.30, 0.30, 0.31), 0.5, 0.6)
        cv.paint(cv.cover(sd + 0.010), (0.08, 0.08, 0.09), 0.6, 0.0)
        # the cab's side window: two panes in one rubber frame
        z0, z1, y0, y1 = CAB_WIN
        sd = SRR(U, V, (z0 + z1) / 2, (y0 + y1) / 2, z1 - z0, y1 - y0, 0.07)
        cv.paint(cv.cover(sd + 0.004), (0.86, 0.86, 0.86), 0.22, 1.0)
        cv.paint(cv.cover(sd), GASKET, 0.45, 0.0)
        cv.paint(cv.cover(sd + 0.022), SIDE_GLASS, 0.05, 0.0)
        zm = (z0 + z1) / 2
        sdm = np.maximum(np.abs(U - zm) - 0.022, np.maximum(y0 - V, V - y1))
        cv.paint(cv.cover(sdm), GASKET, 0.45, 0.0)
        _vdots(cv, U, V, cz0 - 0.08, 1.9, 2.95)
    return cv


def _cab_interior(V, X):
    """the cab behind the windscreen as photo S-13 shows it head-on: the console very dark below 2.43, the partition
    behind in a dim blue-grey with its big window (lighter) left of the centre (−x), the light grey monitor box on the
    console in front of it, the driver's side (+x) darker, the dark ceiling and sun blind at the top"""
    top = np.array((0.08, 0.13, 0.28), np.float32)
    wall = np.array((0.22, 0.24, 0.29), np.float32)
    desk = np.array((0.035, 0.037, 0.042), np.float32)

    def ss(e0, e1, v=V):
        t = np.clip((v - e0) / (e1 - e0), 0, 1)
        return (t * t * (3 - 2 * t))[..., None]
    a = ss(2.40, 2.46)
    b = ss(2.98, 3.06)
    col = wall * (1.0 - 0.35 * np.clip((X - 0.1) / 0.8, 0, 1))[..., None]
    win = np.maximum(np.abs(X + 0.43) - 0.39, np.abs(V - 2.75) - 0.13)
    col = np.where((win < 0)[..., None], np.array((0.44, 0.46, 0.49), np.float32), col)
    col = np.where((np.abs(win) < 0.012)[..., None], col * 0.5, col)
    door = np.maximum(np.abs(X + 1.02) - 0.22, np.abs(V - 2.72) - 0.30)
    col = np.where((np.abs(door) < 0.012)[..., None], col * 0.55, col)
    out = (desk * (1 - a) + col * a) * (1 - b) + top * b
    box = np.maximum(np.abs(X + 0.30) - 0.20, np.abs(V - 2.545) - 0.095)
    out = np.where((box < 0)[..., None], np.array((0.52, 0.54, 0.54), np.float32) * (0.85 + 0.15 * ss(2.45, 2.64)), out)
    seat = np.maximum(np.abs(X - 0.72) - 0.20, np.abs(V - 2.58) - 0.14)
    out = np.where((seat < 0)[..., None], np.array((0.05, 0.06, 0.10), np.float32), out)
    return out


# head-on figures of the face (x, y), measured on photo S-13 at 218 px/m (anchored at the orange band's top, 1.83; the
# face's top then lands on the roof's 3.65) and checked on U514 / K-04 (see the docstring)
GLASS_AREA = (1.33, 1.94, 3.51, 0.22, 0.20)     # half width, y0, y1, bottom corner r, top corner r
FRIT = 3.16                                    # the black frit over the glass's top part starts here
TINT = 3.06                                    # a blue tinted strip under it (sky in the glass's top edge)
CONSOLE = 2.43                                 # the console's top behind the glass (dark below)
LAMP_PANEL = (1.295, 1.205, 1.48, 0.06)        # half width, y0, y1, r
LAMP_UNIT = (0.61, 1.215, 1.225, 1.46)         # |x| from, to; y0, y1
HEAD = (0.92, 3.325, 0.080)                    # |x|, y, lens diameter (round; dark housing 0.13)
TAIL = (0.92, 1.335, 0.200, 0.115)             # |x|, y, w, h
LEDS = (('led_dest', 0.0, 3.325, 0.78, 0.195), ('led_runno', -0.94, 2.29, 0.42, 0.12))   # key, x, y, w, h
LED_BOX = (0.0, 3.325, 0.84, 0.26)              # the display's dark surround
SET_PLATE = (-1.09, 2.49, 0.26, 0.10)          # behind the glass: centre x, y, w, h
WIPERS = ((0.24, 2.105), (1.02, 2.105))        # pivots; arms 0.62 up-left at 162°, blades ~level, 0.64 long
LEDGE = (0.975, 1.10, 0.325, 0.04, 1.27)       # the FRP's bottom ledge: y0, y1, notch half width, depth, outer |x|
JR_FRONT = (1.12, 0.12, (0.92, 0.93, 0.92))    # centre x, height, colour (on the green band)
JR_SIDE = (-4.94, 0.15, (0.80, 0.82, 0.81))    # centre z, height, colour (on the green waist band)


class _Collect:
    """stands in for a UVPart: records the faces (game-frame points, texture coordinates) of one material"""

    def __init__(self, mat):
        self.mat, self.faces = mat, []

    def face_uv(self, pts, mat, uvs, smooth=True, out=None):
        if mat == self.mat:
            self.faces.append((pts, uvs))


def _raster_x(body, X):
    """X (h, w) with every texel inside a face of the cab end's face texture set to that point's head-on x"""
    col = _Collect(P + 'face')
    body.cab_end(col)
    h, w = X.shape
    X = X.copy()
    for pts, uvs in col.faces:
        tris = [(0, 1, 2)] + ([(0, 2, 3)] if len(pts) == 4 else [])
        for a, b, c in tris:
            P_ = np.array([(uvs[k][0] * w - 0.5, uvs[k][1] * h - 0.5) for k in (a, b, c)])
            xs = np.array([pts[k][0] for k in (a, b, c)])
            i0, i1 = int(np.floor(P_[:, 0].min())), int(np.ceil(P_[:, 0].max()))
            j0, j1 = int(np.floor(P_[:, 1].min())), int(np.ceil(P_[:, 1].max()))
            i0, j0 = max(i0, 0), max(j0, 0)
            i1, j1 = min(i1, w - 1), min(j1, h - 1)
            if i1 < i0 or j1 < j0:
                continue
            gi, gj = np.meshgrid(np.arange(i0, i1 + 1), np.arange(j0, j1 + 1))
            (x0, y0), (x1, y1), (x2, y2) = P_
            den = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
            if abs(den) < 1e-9:
                continue
            l0 = ((y1 - y2) * (gi - x2) + (x2 - x1) * (gj - y2)) / den
            l1 = ((y2 - y0) * (gi - x2) + (x0 - x2) * (gj - y2)) / den
            l2 = 1 - l0 - l1
            m = (l0 >= -1e-3) & (l1 >= -1e-3) & (l2 >= -1e-3)
            X[gj[m], gi[m]] = (l0 * xs[0] + l1 * xs[1] + l2 * xs[2])[m]
    return X


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
    # where the cab end's faces cover the texture, take the head-on x straight from them (rasterised over their
    # texture coordinates): exact on the rounded corners, where a row's y and its columns' y differ
    X = _raster_x(body, X)
    dxdu = np.abs(np.gradient(X, axis=1)) / cv.px
    aa = np.maximum(cv.px * dxdu, 1e-4)
    cv.fill(FRP, 0.30, 0.55)
    # the bands across the face and round the corners
    for y0, y1, col in FRONT_BANDS:
        sd = np.maximum(y0 - V, V - y1)
        cv.paint(cv.cover(sd), col, 0.38, 0.0)
    # the JR mark on the green band, right seen from ahead (+x)
    jr = BD._pixels(bpy.data.images.load(os.path.join(_TEXTURES, 'jr_mark.png')))
    jx, jh, jcol = JR_FRONT
    jw = jh * jr.shape[1] / jr.shape[0]
    jy = sum(FRONT_BANDS[1][:2]) / 2
    samp, inside = BD._sample(jr, X, V, jx - jw / 2, jx + jw / 2, jy - jh / 2, jy + jh / 2)
    cv.paint(samp[..., 3] * inside, jcol, 0.35, 0.0)
    # the black glass: a rounded rectangle (larger corners at the top) in a rubber gasket
    hw, y0, y1, rb, rt = GLASS_AREA
    sd_b = SRR(X, V, 0.0, (y0 + y1) / 2, 2 * hw, y1 - y0, rb)
    sd_t = SRR(X, V, 0.0, (y0 + y1) / 2, 2 * hw, y1 - y0, rt)
    sd = np.where(V > (y0 + y1) / 2, sd_t, sd_b)
    cv.paint(cv.cover(sd + 0.002, aa), (0.42, 0.42, 0.43), 0.3, 0.6)       # the frame's inner lip
    cv.paint(cv.cover(sd + 0.010, aa), (0.07, 0.07, 0.075), 0.4, 0.0)      # the rubber gasket
    cv.paint(cv.cover(sd + 0.020, aa), GLASS, 0.06, 0.0)
    # below the frit: the cab seen through the glass, a blue tinted strip at the top
    sds = np.maximum(sd + 0.03, V - FRIT)
    cab = _cab_interior(V, X)
    a = cv.cover(sds, aa)[..., None]
    cv.rgb = cv.rgb * (1 - a) + cab * a * 0.85 + np.array((0.03, 0.04, 0.06), np.float32) * a * 0.15
    cv.rough = cv.rough * (1 - a[..., 0]) + 0.04 * a[..., 0]
    tint = np.clip((V - TINT) / (FRIT - TINT), 0, 1) * (V < FRIT)
    cv.paint((cv.cover(sds, aa) * tint * 0.9).astype(np.float32), (0.08, 0.17, 0.46), 0.04)
    _line(cv, X, V, y=FRIT + 0.003, w=0.006, lo=-hw + 0.04, hi=hw - 0.04, colour=(0.12, 0.13, 0.16), alpha=0.8, rough=0.05, aa=aa)
    # the set number plate behind the glass, lower left of the windscreen
    if plate_img is not None:
        px_, py_, pw_, ph_ = SET_PLATE
        samp, inside = BD._sample(plate_img, X, V, px_ - pw_ / 2, px_ + pw_ / 2, py_ - ph_ / 2, py_ + ph_ / 2)
        a = (inside * 0.92)[..., None]
        cv.rgb = cv.rgb * (1 - a) + samp[..., :3] * 0.78 * a
    # the line display's dark surround and the headlamp housings in the frit
    bx, by, bw, bh = LED_BOX
    cv.paint(cv.cover(SRR(X, V, bx, by, bw, bh, 0.02), aa), (0.10, 0.11, 0.11), 0.2, 0.0)
    rx, ry, rd = HEAD
    for s in (-1, 1):
        d = np.sqrt((X - s * rx) ** 2 + (V - ry) ** 2)
        cv.paint(cv.cover(d - 0.065, aa), (0.07, 0.075, 0.08), 0.2, 0.3)
        cv.paint(cv.cover(np.abs(d - 0.052) - 0.004, aa), (0.30, 0.31, 0.32), 0.2, 1.0)
    # run-number box surround
    _, rx_, ry_, rw_, rh_ = LEDS[1]
    cv.paint(cv.cover(SRR(X, V, rx_, ry_, rw_ + 0.04, rh_ + 0.03, 0.015), aa), (0.06, 0.06, 0.065), 0.2, 0.0)
    # the lamp panel: glossy black, the two lamp units at its ends
    lw, ly0, ly1, lr = LAMP_PANEL
    sd = SRR(X, V, 0.0, (ly0 + ly1) / 2, 2 * lw, ly1 - ly0, lr)
    cv.paint(cv.cover(sd + 0.004, aa), (0.30, 0.30, 0.31), 0.3, 0.6)
    cv.paint(cv.cover(sd + 0.012, aa), (0.025, 0.025, 0.028), 0.15, 0.0)
    ux0, ux1, uy0, uy1 = LAMP_UNIT
    tx, ty, tw, th = TAIL
    for s in (-1, 1):
        sdu = SRR(X, V, s * (ux0 + ux1) / 2, (uy0 + uy1) / 2, ux1 - ux0, uy1 - uy0, 0.02)
        cv.paint(cv.cover(np.abs(sdu) - 0.009, aa), (0.24, 0.24, 0.25), 0.3, 0.8)    # the unit's bezel
        cv.paint(cv.cover(sdu + 0.012, aa), (0.07, 0.07, 0.075), 0.1, 0.0)         # its dark cover glass
        sdr = SRR(X, V, s * (tx - 0.02), ty, 0.44, 0.17, 0.02)
        cv.paint(cv.cover(sdr, aa), (0.33, 0.33, 0.34), 0.2, 0.9)                    # the reflector housing behind it
        cv.paint(cv.cover(np.abs(sdr) - 0.004, aa), (0.10, 0.10, 0.11), 0.3, 0.3)
        cv.paint(cv.cover(SRR(X, V, s * tx, ty, tw + 0.03, th + 0.03, 0.015), aa), (0.30, 0.30, 0.31), 0.25, 1.0)
    # the lower face: a crease where the FRP turns under, the ledge is geometry
    _line(cv, X, V, y=1.115, w=0.010, lo=-LEDGE[4] - 0.02, hi=LEDGE[4] + 0.02, colour=(0.14, 0.14, 0.15), alpha=0.85, aa=aa)
    return cv, X


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
    m.add(P + 'skirt', '#c9cac7', metallic=0.45, roughness=0.42)
    m.add(P + 'frp', '#bdbeba', metallic=0.5, roughness=0.32)
    m.add(P + 'lamp', '#e2e2dc', metallic=0.3, roughness=0.12)        # head lamp lens (showcase lights it)
    m.add(P + 'tail', '#4a0a10', roughness=0.2)
    m.add(P + 'sidelamp', '#b8212a', roughness=0.2)
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
    else:
        raise FileNotFoundError('run tools/blender/e231_kinkou_textures.py first (signs missing in ' + SIGNS + ')')
    return boxes


SIDE_ATLAS = {}     # car: v offset, v scale of its side texture in side.png (set by add_materials)
DECAL_UV = {}       # car: [((u0, u1, v0, v1) of a decal block in side.png, (z0, z1, y0, y1) it covers on the car)]
NUMBER_AT = (-0.55, 1.12)   # car numbers: left end z and bottom y on the side (photo: under the bands, mid-car)


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
    wid = hgt * nw / nh
    y0 = WAIST[1][0] + (WAIST[1][1] - WAIST[1][0] - hgt) / 2
    return _decal_block(cv, arr, zc - wid / 2, y0, wid, hgt, colour, 0.30, 0.6)


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
    return (x, y, surface_z(x, y) + lift)


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


def _lens(part, mat, cx, cy, w, h, r, depth, lift_rim, seg=3):
    """a lamp lens sunk `depth` behind a rim at `lift_rim` (a short tube of side faces + the lens); w = h = 2r: round"""
    ring_out, ring_in = [], []
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
        if (Vector(a) - Vector(b)).length < 1e-6:
            continue
        mid = Vector([(a[q] + b[q]) / 2 for q in range(3)])
        part.face_uv([a, b, c, d], P + 'black', [(0, 0)] * 4, smooth=False, out=mid - Vector((cx, cy, mid.z + 0.5)))
    c = _on_face(cx, cy, lift_rim - depth)
    for k in range(nn):
        if (Vector(ring_in[k]) - Vector(ring_in[(k + 1) % nn])).length < 1e-6:
            continue
        part.face_uv([c, ring_in[k], ring_in[(k + 1) % nn]], mat, [(0, 0)] * 3, smooth=False, out=(0, 0.1, 1))


def _ledge(part):
    """the FRP's bottom ledge: a bumper strip standing out from the lower face on each side of the coupler notch, its
    ends rounded off (photo S-13: |x| 0.325 … 1.27, y 0.975 … 1.10)"""
    y0, y1, notch, depth, outer = LEDGE
    for s in (-1, 1):
        n = 14
        xs = [s * (notch + (outer - notch) * k / n) for k in range(n + 1)]
        secs = []
        for i, x in enumerate(xs):
            end = min(1.0, (outer - abs(x)) / 0.06)
            dd = depth * math.sqrt(max(0.0, end)) if i == n else depth
            zt, zb = surface_z(x, y1), surface_z(x, y0)
            secs.append([(x, y1, zt - 0.01), (x, y1, zt + dd), (x, y1 - 0.012, zt + dd + 0.002), (x, y0 + 0.014, zb + dd),
                         (x, y0, zb + dd - 0.014), (x, y0, zb - 0.05)])
        nrm = ((0, 1, 0.1), (0, 0.6, 0.8), (0, 0.05, 1), (0, -0.6, 0.8), (0, -1, 0))
        mats = (P + 'frp', P + 'frp', P + 'frp', P + 'frp', P + 'under')
        for pa, pb in zip(secs[:-1], secs[1:]):
            for j in range(5):
                part.face_uv([pa[j], pb[j], pb[j + 1], pa[j + 1]], mats[j], [(0, 0)] * 4, smooth=j in (1, 2, 3), out=nrm[j])
        for sec, facing in ((secs[0], -s), (secs[-1], s)):
            c = Vector([sum(p[q] for p in sec) / len(sec) for q in range(3)])
            for j in range(len(sec)):
                part.face_uv([c, sec[j], sec[(j + 1) % len(sec)]], P + 'frp', [(0, 0)] * 3, smooth=False, out=(facing, 0, 0))


def cab_fittings(part, boxes):
    """front displays behind the glass, head and tail lamp lenses, wipers, the bottom ledge"""
    for key, cx, cy, w, h in LEDS:
        if key in boxes:
            _quad_on_face(part, P + 'led', cx - w / 2, cx + w / 2, cy - h / 2, cy + h / 2, boxes[key], 0.002)
    hx, hy, hd = HEAD
    tx, ty, tw, th = TAIL
    for s in (-1, 1):
        _lens(part, P + 'lamp', s * hx, hy, hd, hd, hd / 2 - 1e-4, 0.008, 0.012, seg=5)
        _lens(part, P + 'tail', s * tx, ty, tw, th, 0.016, 0.008, 0.012)
    # wipers parked low on the glass, pivots at their right ends (seen from ahead): arm up and to the left, the blade
    # lying almost level from the arm's end (photo S-13)
    for px_, py_ in WIPERS:
        a = math.radians(162.0)
        ex, ey = px_ + 0.62 * math.cos(a), py_ + 0.62 * math.sin(a)
        steps = 5
        prev = None
        for k in range(steps + 1):
            t = k / steps
            p = _on_face(px_ + (ex - px_) * t, py_ + (ey - py_) * t, 0.016)
            if prev is not None:
                part.beam(P + 'black', prev, p, 0.016, 0.010)
            prev = p
        bx0, bx1 = ex - 0.42, ex + 0.22
        prev = None
        for k in range(5):
            t = k / 4
            x = bx0 + (bx1 - bx0) * t
            p = _on_face(x, ey + 0.012 - 0.03 * (x - ex), 0.011)
            if prev is not None:
                part.beam(P + 'black', prev, p, 0.012, 0.008)
            prev = p
        part.cylinder(P + 'black', _on_face(px_, py_, 0.012), 0.026, 0.03, axis='z', segments=10)
    _ledge(part)


def side_fittings(part, boxes, kind):
    """side destination displays, side lamps, the crew doors' handles, grab rails and steps"""
    for side in (-1, 1):
        sz = 1 if side < 0 else -1
        zc, yc, w, h = SIDE_SIGN
        zc *= sz
        if 'led_side' in boxes:
            u0, v0, u1, v1 = boxes['led_side']
            iw, ih = 0.62, 0.14
            x = side * (HW + 0.006)
            pts = [(x, yc - ih / 2, zc - iw / 2), (x, yc - ih / 2, zc + iw / 2), (x, yc + ih / 2, zc + iw / 2), (x, yc + ih / 2, zc - iw / 2)]

            def uu(z):
                t = (z - (zc - iw / 2)) / iw
                return u0 + (u1 - u0) * ((1 - t) if side > 0 else t)
            part.face_uv(pts, P + 'led', [(uu(p[2]), v0 + (v1 - v0) * (p[1] - (yc - ih / 2)) / ih) for p in pts], out=(side, 0, 0))
            # the dark panel in a silver frame, standing a little proud of the side
            x0_, x1_ = sorted((side * (HW - 0.004), side * (HW + 0.004)))
            part.box(P + 'black', x0_, x1_, yc - h / 2 + 0.012, yc + h / 2 - 0.012, zc - w / 2 + 0.012, zc + w / 2 - 0.012, bevel=0.002, segments=1)
            x0_, x1_ = sorted((side * (HW - 0.004), side * (HW + 0.002)))
            for zz in (zc - w / 2 + 0.006, zc + w / 2 - 0.006):
                part.box(P + 'sill', x0_, x1_, yc - h / 2, yc + h / 2, zz - 0.006, zz + 0.006)
            for yy in (yc - h / 2 + 0.006, yc + h / 2 - 0.006):
                part.box(P + 'sill', x0_, x1_, yy - 0.006, yy + 0.006, zc - w / 2, zc + w / 2)
        lz, ly, lr = SIDE_LAMP
        lz *= sz
        part.cylinder(P + 'steel', (side * (HW + 0.004), ly, lz), lr + 0.012, 0.010, axis='x', segments=14)
        part.cylinder(P + 'sidelamp', (side * (HW + 0.012), ly, lz), lr, 0.012, axis='x', segments=14)
    if kind != 'cab':
        return
    cz0, cz1, cy0, cy1 = CREW_DOOR
    for side in (-1, 1):
        x = side * HW
        # long vertical grab rails either side of the crew door on stand-offs (photo "E231 E233 coupling")
        for zr in (cz1 + 0.07, cz0 - 0.07):
            ya, yb = 1.36, 2.50
            part.cylinder(P + 'chrome', (x + side * 0.045, (ya + yb) / 2, zr), 0.013, yb - ya, axis='y', segments=10)
            for yy in (ya + 0.03, yb - 0.03):
                part.cylinder(P + 'chrome', (x + side * 0.022, yy, zr), 0.009, 0.045, axis='x', segments=8)
        # door handle (lever on a plate) at the rear edge
        part.box(P + 'steel', *sorted((x, x + side * 0.006)), 1.82, 1.94, cz0 + 0.05, cz0 + 0.11, bevel=0.003, segments=1)
        part.box(P + 'chrome', *sorted((x + side * 0.006, x + side * 0.03)), 1.87, 1.89, cz0 + 0.05, cz0 + 0.17, bevel=0.004, segments=1)
        # the foot step below the crew door
        part.box(P + 'frame', *sorted((x - side * 0.10, x + side * 0.01)), 0.80, 0.83, cz0 + 0.05, cz1 - 0.05)
        for zz in (cz0 + 0.07, cz1 - 0.07):
            part.box(P + 'frame', *sorted((x - side * 0.06, x + side * 0.005)), 0.83, 1.00, zz - 0.012, zz + 0.012)


# ---------------------------------------------------------------- the skirt (strengthened V type, deep notch)

SKIRT_TOP = 0.665
SKIRT_NOTCH = (0.32, 0.345, 0.375)     # notch bottom y, half width at its bottom, half width at the top edge
SKIRT_BOTTOM = 0.165
SKIRT_T = 0.008
SKIRT_TIP = 9.94                     # the V's point (centre of its lower edge) — just behind the coupler face
SKIRT_CORNER = (1.15, 9.80)          # where the front panels meet the rounded corners (x, z)
SKIRT_SIDE = (1.34, 9.42)            # the wings' rear end (x, z)


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
    """top edge: level at the sides, sloping down into the notch round the coupler and its electric coupler"""
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
    for s_ in (-1, 1):
        part.box(P + 'under', *sorted((s_ * 0.36, s_ * 1.30)), 0.62, 1.00, 9.40, 9.46)
