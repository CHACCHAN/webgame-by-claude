"""
L0 series: the shells (a loft of l0_shape's sections with texture coordinates), the painted atlas (livery, windows,
doors, louvres, the roof panel), the nose's lamp panel, the logo plates and the hoods over the car joints.

Livery and fittings, measured on the photos of fitdata/l0/ref/list.json through the solved cameras
(fitdata/l0/tools/measure.py: pixel → the fitted shell), in the car frame of l0_shape (d = distance from the nose tip):
- side: a thick blue band y 2.40–2.63 and a thin line y 2.20–2.285 over the whole train (c04: 2.37–2.45 / 2.61–2.65
  and 2.15–2.22 / 2.22–2.31 at two places); on the nose both run forward into one point at d 12.75, y 2.14 (c04),
  the band's top edge 2.44 at d 14.4 and 2.56 at d 15.2, the line meeting the band at d ≈ 14.1 (y 2.27);
- nose top: seven stripes along the car, symmetric: |x| ≤ 0.22 (the wide centre one), 0.30–0.47, 0.61–0.69 and
  0.92–0.97 on the shoulders (c12 at d 11.7 and 12.9; c07 at d 8.7–11.7 after its lateral offset); their front ends
  on a chevron d = 6.6 + 3.3 |x| (c07: tips at d 7.1, 8.1, 9.0, 9.8), their rear ends across at d 15.2 (c12);
- roof: a grey panel |x| ≤ 0.75, d 16.2–21.2 (c12);
- end car: five small windows z 0.46 … −2.90 (0.84 m apart), y 1.75–2.10, 0.29 m wide (c04); the door just behind
  the nose, z 2.85–3.65 (front edge c04 3.54, c07 3.6–3.8), top y 2.18; the logo z −3.64 … −5.28, y 1.46–2.11; a
  louvred grille z −5.81 … −6.76, y 1.53–2.46 before the joint (c04); a slanted vent on the nose side at d 11.7–12.2,
  y 1.58–1.95, leaning forward (c04; c07: d 11.2–12.1, y 1.6–2.0);
- middle car: 17 windows (one a seat row) 0.84 m apart over 13.4 m (c04: car 3's windows z −37.1 … −50.8), the door
  near its front end (estimate), louvres at both ends as on the end car;
- lamp panel (snout): two dark lamp windows x ±0.21 … ±0.62, y 0.747–0.855 with two round head lamps each
  (x ±0.405, ±0.538, y 0.792) and a red tail lamp at the inner end; a camera window on the centre line y 0.80 and a
  second one below at y 0.54 (bundle adjustment on c07, c12, c09 and the lamps' outlines; ba.py).
Not seen on any photo (the guideway's walls hide everything below ≈ 1.4 m): the lower body and its covers, which
are drawn plain.
"""
import math
import os

import bmesh
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

import train_kit as K
import body_n1000 as BD
import l0_shape as S

P = 'l0_'
ATLAS = int(os.environ.get('L0_ATLAS', '4096'))
KINDS = ('end', 'mid')
STRIP = {'end': 0, 'mid': 1}
U_RANGE = {'end': (S.JOINT_END + S.GAP - 0.01, S.NOSE_TIP + 0.01),
           'mid': (-S.JOINT_MID + S.GAP - 0.01, S.JOINT_MID - S.GAP + 0.01)}

# colours (sRGB floats)
WHITE = (0.925, 0.933, 0.940)
BLUE = (0.105, 0.235, 0.545)           # JR Central blue: photos c04 (shade) ≈ #2a4171, c07 (sun + sky) ≈ #3f70b3
ROOF_GREY = (0.42, 0.44, 0.46)
DARK_GLASS = (0.060, 0.068, 0.078)           # linear luminance ≈ 0.006: lit at night (TrainInfo.lamps.windowLum 0.03)
GASKET = (0.20, 0.21, 0.22)
SEAM = (0.55, 0.57, 0.59)
LOUVRE_DARK = (0.21, 0.22, 0.24)          # linear ≈ 0.037: above windowLum, so the grilles stay dark at night
UNDER = (0.36, 0.37, 0.38)

# livery (see the docstring)
BAND = (2.40, 2.63)
LINE = (2.20, 2.285)
SWOOSH_TIP = (12.75, 2.14)
STRIPES = ((0.0, 0.22), (0.30, 0.47), (0.61, 0.69), (0.92, 0.97))
CHEVRON = (6.6, 3.3)
STRIPE_REAR = 15.2
ROOF_PANEL = (16.2, 21.2, 0.75)
WIN_Y = (1.75, 2.10)
WIN_W = 0.29
WIN_R = 0.11
END_WINDOWS = tuple(0.46 - 0.84 * i for i in range(5))
MID_WINDOWS = tuple(6.42 - 0.84 * i for i in range(17))
DOOR = {'end': (3.25, 0.80), 'mid': (8.90, 0.80)}     # centre z, width
DOOR_TOP = 2.18
DOOR_BOTTOM = 0.62
LOGO = (-5.28, -3.64, 1.46, 2.11)                      # z0, z1, y0, y1 (end cars)
LOUVRE = (0.49, 1.44, 1.53, 2.46)                      # from the joint's centre: near, far; y0, y1 (c04: z −6.76 … −5.81)
NOSE_VENT = (11.93, 12.24, 1.58, 1.95, 0.55)           # d0, d1 (at its foot), y0, y1, lean (d per m up)
# lamp panel: l0_shape (shared with the fit tools)
LAMP_WIN, HEAD_X, HEAD_Y, HEAD_R, TAIL_X, CAM_WIN, CAM_LOW = (S.LAMP_WIN, S.HEAD_X, S.HEAD_Y, S.HEAD_R, S.TAIL_X,
                                                            S.CAM_WIN, S.CAM_LOW)

def _vk():
    """texture v of each ring point: the arc length round the body's half section, 0 … 1"""
    pts = S.half_section(dict(S.BODY))
    L = np.concatenate([[0.0], np.cumsum(np.hypot(*np.diff(pts, axis=0).T))])
    return L / L[-1]


VK = _vk()


def nose_steps():
    """the nose's stations (distance from the tip): fine where the sections change quickly"""
    ds = []
    d = S.NOSE_LEN - 0.25
    while d > 2.4:
        ds.append(d)
        d -= 0.25 if d > 6.0 else 0.15
    ds += list(np.geomspace(2.4, 0.004, 34))
    return ds


class Shell:
    def __init__(self, kind):
        self.kind = kind
        self.R = S.rings(kind, step=1.0, nose_steps=nose_steps() if kind == 'end' else None)
        self.bvh = None

    def uv(self, z, j):
        u0, u1 = U_RANGE[self.kind]
        u = (z - u0) / (u1 - u0)
        v = (STRIP[self.kind] + 0.004 + 0.992 * VK[j]) / 2.0
        return (min(max(u, 0.0), 1.0), v)

    def build(self, part):
        mat = P + 'body'
        R = self.R
        n = S.HALF_N
        tris = []
        for i in range(len(R) - 1):
            (za, A), (zb, Bp) = R[i], R[i + 1]
            for j in range(n - 1):
                for side in (1, -1):
                    corners = [(A, za, j), (Bp, zb, j), (Bp, zb, j + 1), (A, za, j + 1)]
                    if side > 0:
                        corners = [corners[0], corners[3], corners[2], corners[1]]
                    q, u = [], []
                    for ring, z_, jj in corners:
                        p = (side * float(ring[jj][0]), float(ring[jj][1]), z_)
                        # drop repeated corners (the tip's rings are tiny; the centre line's points meet)
                        if q and (Vector(p) - Vector(q[-1])).length < 1e-7:
                            continue
                        q.append(p)
                        u.append(self.uv(z_, jj))
                    if len(q) >= 3 and (Vector(q[0]) - Vector(q[-1])).length < 1e-7:
                        q.pop()
                        u.pop()
                    if len(q) < 3:
                        continue
                    part.face_uv(q, mat, u)
                    tris.append(q)
        # the nose tip: a fan to the tip point; the joint end: a flat face (in the hood)
        if self.kind == 'end':
            z, A = R[-1]
            tip = (0.0, S.top_y(0.0), S.NOSE_TIP)
            ring = [(x, y, z) for x, y in A] + [(-x, y, z) for x, y in A[1:-1][::-1]]
            for k in range(len(ring)):
                a, b = ring[k], ring[(k + 1) % len(ring)]
                if (Vector(a) - Vector(b)).length < 1e-7:
                    continue
                part.face_uv([a, b, tip], mat, [self.uv(S.NOSE_TIP, S.HALF_N // 2)] * 3, out=(0, 0, 1))
                tris.append([a, b, tip])
        ends = [(R[0], -1)] + ([(R[-1], 1)] if self.kind == 'mid' else [])
        for (z, A), sign in ends:
            ring = [(x, y, z) for x, y in A] + [(-x, y, z) for x, y in A[1:-1][::-1]]
            c = (0.0, float(np.mean([p[1] for p in ring])), z)
            for k in range(len(ring)):
                a, b = ring[k], ring[(k + 1) % len(ring)]
                if (Vector(a) - Vector(b)).length < 1e-7:
                    continue
                f = part.face([a, b, c], P + 'end', smooth=False)
                f.normal_update()
                if f.normal.dot(K.B(0, 0, sign)) < 0:
                    f.normal_flip()
                tris.append([a, b, c])
        # a ray-cast copy (decals, lamps)
        bm = bmesh.new()
        for t in tris:
            vs = [bm.verts.new(K.B(*p)) for p in t]
            try:
                bm.faces.new(vs)
            except ValueError:
                pass
        bm.normal_update()
        self.bvh = BVHTree.FromBMesh(bm)
        bm.free()

    def hit(self, origin, direction):
        loc, nrm, _, _ = self.bvh.ray_cast(K.B(*origin), K.B(*direction))
        if loc is None:
            return None
        return Vector(K.G(loc)), Vector(K.G(nrm))


# ---------------------------------------------------------------- the atlas
class Paint:
    """texel → shell point lookup for one strip (rows: v, columns: u), and painting helpers"""

    def __init__(self, shell, w=ATLAS, h=ATLAS // 2):
        self.shell = shell
        self.w, self.h = w, h
        R = shell.R
        zs = np.array([z for z, _ in R])
        G = np.array([pts for _, pts in R], np.float32)            # (ns, HALF_N, 2)
        Nr = np.array([S._normals2d(pts) for _, pts in R], np.float32)
        u0, u1 = U_RANGE[shell.kind]
        Z = u0 + (np.arange(w) + 0.5) / w * (u1 - u0)
        v = (np.arange(h) + 0.5) / h
        vl = np.clip((v - 0.004) / 0.992, 0, 1)
        jf = np.interp(vl, VK, np.arange(S.HALF_N))
        i0 = np.clip(np.searchsorted(zs, Z) - 1, 0, len(zs) - 2)
        a = np.clip((Z - zs[i0]) / np.maximum(zs[i0 + 1] - zs[i0], 1e-6), 0, 1).astype(np.float32)
        j0 = np.clip(np.floor(jf).astype(int), 0, S.HALF_N - 2)
        b = (jf - j0).astype(np.float32)
        aa = a[:, None, None]
        bb = b[None, :, None]

        def bil(Gr):
            return (Gr[i0][:, j0] * (1 - aa) * (1 - bb) + Gr[i0 + 1][:, j0] * aa * (1 - bb) +
                    Gr[i0][:, j0 + 1] * (1 - aa) * bb + Gr[i0 + 1][:, j0 + 1] * aa * bb)
        P2 = bil(G)
        N2 = bil(Nr)
        self.X = np.ascontiguousarray(P2[..., 0].T)
        self.Y = np.ascontiguousarray(P2[..., 1].T)
        self.NY = np.ascontiguousarray(N2[..., 1].T)               # how much the surface faces up
        self.NX = np.ascontiguousarray(N2[..., 0].T)
        self.Z = np.broadcast_to(Z[None, :], (h, w)).copy()
        # the livery's distances are measured from the published tip (REF_TIP; the fitted face is 0.16 m behind it)
        self.D = (S.REF_TIP - self.Z) if shell.kind == 'end' else np.full((h, w), 99.0, np.float32)
        self.px = (u1 - u0) / w
        self.rgb = np.zeros((h, w, 3), np.float32)
        self.rough = np.full((h, w), 0.2, np.float32)
        self.metal = np.zeros((h, w), np.float32)

    def cover(self, sd, aa=None):
        return np.clip(0.5 - sd / (aa if aa is not None else self.px * 1.2), 0.0, 1.0)

    def paint(self, alpha, colour, rough=None, metal=None):
        a = alpha[..., None]
        self.rgb = self.rgb * (1 - a) + np.array(colour, np.float32) * a
        if rough is not None:
            self.rough = self.rough * (1 - alpha) + rough * alpha
        if metal is not None:
            self.metal = self.metal * (1 - alpha) + metal * alpha


def _sd_box(px, py, cx, cy, w, h, r):
    return BD._sd_round_rect(px, py, cx, cy, w, h, r)


def _curve(pts):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    f = S.pchip(xs, ys)
    return f


# the side swoosh's edges along the nose (d → y); flat beyond the last point
_BAND_TOP = _curve([(SWOOSH_TIP[0], SWOOSH_TIP[1]), (13.5, 2.30), (14.4, 2.44), (15.2, 2.56), (16.2, 2.625), (17.0, BAND[1])])
_BAND_BOT = _curve([(SWOOSH_TIP[0], SWOOSH_TIP[1]), (14.1, 2.27), (15.0, 2.335), (16.0, 2.385), (17.0, BAND[0])])
_LINE_TOP = _curve([(14.1, 2.27), (15.0, 2.284), (16.0, LINE[1])])
_LINE_BOT = _curve([(SWOOSH_TIP[0], SWOOSH_TIP[1]), (13.4, 2.17), (14.1, 2.205), (15.0, LINE[0]), (16.0, LINE[0])])


def _side_lines(pt, side):
    X, Y, D = pt.X, pt.Y, pt.D
    aa = 0.006
    if pt.shell.kind == 'end':
        Dc = np.clip(D, SWOOSH_TIP[0], 40.0)
        yt, yb = _BAND_TOP(np.minimum(Dc, 17.0)), _BAND_BOT(np.minimum(Dc, 17.0))
        lt, lb = _LINE_TOP(np.clip(Dc, 14.1, 16.0)), _LINE_BOT(np.minimum(Dc, 16.0))
        blue = np.minimum(np.clip(0.5 + (yt - Y) / aa, 0, 1), np.clip(0.5 + (Y - lb) / aa, 0, 1))
        gap = np.minimum(np.clip(0.5 + (yb - Y) / aa, 0, 1), np.clip(0.5 + (Y - lt) / aa, 0, 1))
        gap = gap * (yb > lt)
        blue = np.clip(blue - gap, 0, 1) * (D >= SWOOSH_TIP[0])
    else:
        band = np.minimum(np.clip(0.5 + (BAND[1] - Y) / aa, 0, 1), np.clip(0.5 + (Y - BAND[0]) / aa, 0, 1))
        line = np.minimum(np.clip(0.5 + (LINE[1] - Y) / aa, 0, 1), np.clip(0.5 + (Y - LINE[0]) / aa, 0, 1))
        blue = np.maximum(band, line)
    pt.paint(blue * side, BLUE, 0.22)


def _nose_top(pt):
    X, D = np.abs(pt.X), pt.D
    up = np.clip((pt.NY - 0.15) / 0.2, 0, 1)
    aa = 0.008
    alpha = np.zeros_like(X)
    for x0, x1 in STRIPES:
        a = np.minimum(np.clip(0.5 + (x1 - X) / aa, 0, 1), np.clip(0.5 + (X - x0) / aa, 0, 1) if x0 > 0 else 1.0)
        front = CHEVRON[0] + CHEVRON[1] * X
        a = a * np.clip(0.5 + (D - front) / (aa * 2), 0, 1) * np.clip(0.5 + (STRIPE_REAR - D) / aa, 0, 1)
        alpha = np.maximum(alpha, a)
    pt.paint(alpha * up, BLUE, 0.22)
    # the roof panel
    d0, d1, hw = ROOF_PANEL
    sd = _sd_box(D, X, (d0 + d1) / 2, 0.0, d1 - d0, 2 * hw, 0.25)
    pt.paint(pt.cover(sd, 0.01) * (pt.NY > 0.5), ROOF_GREY, 0.55)
    sd2 = np.abs(sd + 0.0) - 0.004
    pt.paint(pt.cover(sd2, 0.006) * (pt.NY > 0.5), GASKET, 0.6)
    # a small grille near the panel's rear end
    for k in range(6):
        sdg = _sd_box(D, X, d1 - 0.55 - 0.07 * k, 0.0, 0.03, 0.5, 0.01)
        pt.paint(pt.cover(sdg, 0.008) * (pt.NY > 0.5), LOUVRE_DARK, 0.6)


def _window(pt, zc, side):
    sd = _sd_box(pt.Z, pt.Y, zc, (WIN_Y[0] + WIN_Y[1]) / 2, WIN_W, WIN_Y[1] - WIN_Y[0], WIN_R)
    pt.paint(pt.cover(sd - 0.014, 0.006) * side, GASKET, 0.5)
    pt.paint(pt.cover(sd, 0.006) * side, DARK_GLASS, 0.05)


def _door(pt, zc, w, side):
    """a plug door: its outline (a fine dark gap), a rounded head"""
    yc = (DOOR_TOP + DOOR_BOTTOM) / 2
    sd = _sd_box(pt.Z, pt.Y, zc, yc, w, DOOR_TOP - DOOR_BOTTOM, 0.16)
    pt.paint(pt.cover(np.abs(sd) - 0.006, 0.005) * side, GASKET, 0.5)
    # a grab recess
    sdh = _sd_box(pt.Z, pt.Y, zc - 0.28, 1.25, 0.05, 0.16, 0.02)
    pt.paint(pt.cover(sdh, 0.005) * side, SEAM, 0.5)


def _louvre(pt, z0, z1, side):
    """a louvred grille: two columns of slats, each a dark slot with a light slat"""
    y0, y1 = LOUVRE[2], LOUVRE[3]
    zc = (z0 + z1) / 2
    w = abs(z1 - z0)
    sd = _sd_box(pt.Z, pt.Y, zc, (y0 + y1) / 2, w, y1 - y0, 0.03)
    inside = pt.cover(sd, 0.006) * side
    pt.paint(inside, LOUVRE_DARK, 0.5)
    col_w = w / 2 - 0.05
    n = 9
    for c in (-1, 1):
        cz = zc + c * (w / 4)
        for k in range(n):
            yk = y0 + 0.06 + (y1 - y0 - 0.12) * (k + 0.5) / n
            sl = _sd_box(pt.Z, pt.Y, cz, yk, col_w, 0.045, 0.006)
            pt.paint(pt.cover(sl, 0.005) * inside, (0.80, 0.82, 0.84), 0.4)
    # the frame round it
    pt.paint(pt.cover(np.abs(sd) - 0.008, 0.005) * side, SEAM, 0.5)


def _nose_vent(pt, side):
    """the slanted vent on the nose's side (c04): four dark slots in a stack leaning forward"""
    d0, d1, y0, y1, lean = NOSE_VENT
    Dm = pt.D + (pt.Y - y0) * lean
    sd = _sd_box(Dm, pt.Y, (d0 + d1) / 2, (y0 + y1) / 2, d1 - d0, y1 - y0, 0.02)
    inside = pt.cover(sd, 0.005) * side
    pt.paint(pt.cover(sd - 0.008, 0.005) * side, SEAM, 0.4)
    pt.paint(inside, (0.86, 0.87, 0.88), 0.35)
    for k in range(4):
        yk = y0 + (y1 - y0) * (k + 0.5) / 4
        sl = _sd_box(Dm, pt.Y, (d0 + d1) / 2, yk, d1 - d0 - 0.03, (y1 - y0) / 4 - 0.025, 0.005)
        pt.paint(pt.cover(sl, 0.005) * inside, LOUVRE_DARK, 0.5)


def _snout_seams(pt):
    """the riveted snout panel's joint across the nose, and the centre line seam of the lower snout"""
    D, X, Y = pt.D, np.abs(pt.X), pt.Y
    up = pt.NY > -0.2
    sd = np.abs(D - (1.95 + 0.25 * (X / 1.3) ** 2)) - 0.0025
    pt.paint(pt.cover(sd, 0.004) * up * (D < 3.0), SEAM, 0.4)


def paint_car(shell):
    pt = Paint(shell)
    side = (pt.X > 0.6) & (np.abs(pt.NX) > 0.5)
    side = side.astype(np.float32)
    pt.rgb[:] = WHITE
    pt.rough[:] = 0.2
    # the underside (beneath the lower side's turn)
    under = (pt.NY < -0.55).astype(np.float32)
    if shell.kind == 'end':
        under = under * (pt.D > 1.2)
    pt.paint(under, UNDER, 0.7)
    _side_lines(pt, side)
    if shell.kind == 'end':
        _nose_top(pt)
        for zc in END_WINDOWS:
            _window(pt, zc, side)
        zc, w = DOOR['end']
        _door(pt, zc, w, side)
        _louvre(pt, S.JOINT_END + LOUVRE[0], S.JOINT_END + LOUVRE[1], side)
        _nose_vent(pt, side)
        _snout_seams(pt)
    else:
        for zc in MID_WINDOWS:
            _window(pt, zc, side)
        zc, w = DOOR['mid']
        _door(pt, zc, w, side)
        _louvre(pt, -S.JOINT_MID + LOUVRE[0], -S.JOINT_MID + LOUVRE[1], side)
        _louvre(pt, S.JOINT_MID - LOUVRE[0], S.JOINT_MID - LOUVRE[1], side)
    # the body end's rounding: a fine seam where it starts
    for ze in ((S.JOINT_END + S.GAP + S.END_R,) if shell.kind == 'end' else (-S.JOINT_MID + S.GAP + S.END_R, S.JOINT_MID - S.GAP - S.END_R)):
        sd = np.abs(pt.Z - ze) - 0.003
        pt.paint(pt.cover(sd, 0.004) * (pt.Y > 0.6), SEAM, 0.4)
    return pt


def add_materials(m, tex_dir, shells):
    os.makedirs(tex_dir, exist_ok=True)
    m.add(P + 'end', '#5d6064', roughness=0.7)
    m.add(P + 'hood', '#2e3033', roughness=0.85)
    m.add(P + 'glass', '#0e1114', roughness=0.06)
    # behind the dark glass by day (c07): the lenses and reflectors read grey, the tail lamp dark red
    m.add(P + 'lamp', '#6d7277', metallic=0.0, roughness=0.08)
    m.add(P + 'reflector', '#8f949a', metallic=1.0, roughness=0.25)
    m.add(P + 'tail', '#5a1416', roughness=0.08)
    m.add(P + 'camera', '#1b1e22', roughness=0.1)
    m.add(P + 'lens', '#05070a', metallic=0.0, roughness=0.04)
    rgb = np.zeros((ATLAS, ATLAS, 3), np.float32)
    mr = np.zeros((ATLAS, ATLAS, 4), np.float32)
    mr[..., 3] = 1
    mr[..., 0] = 1
    for kind in KINDS:
        pt = paint_car(shells[kind])
        r0 = STRIP[kind] * (ATLAS // 2)
        rgb[r0:r0 + pt.h] = pt.rgb
        mr[r0:r0 + pt.h, :, 1] = pt.rough
        mr[r0:r0 + pt.h, :, 2] = pt.metal
    img = _save_image(P + 'atlas', rgb, os.path.join(tex_dir, 'l0_body.png'))
    img2 = _save_image(P + 'atlas_mr', mr, os.path.join(tex_dir, 'l0_body_mr.png'), data=True)
    mat = BD.textured_material(P + 'body', img, img2)
    m.mats[P + 'body'] = mat
    logo = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'textures', 'l0', 'l0_logo.png')
    if os.path.exists(logo):
        li = bpy.data.images.load(logo)
        sm = bpy.data.materials.new(P + 'logo')
        sm.use_nodes = True
        nt = sm.node_tree
        bsdf = nt.nodes.get('Principled BSDF')
        t = nt.nodes.new('ShaderNodeTexImage')
        t.image = li
        nt.links.new(t.outputs['Color'], bsdf.inputs['Base Color'])
        bsdf.inputs['Roughness'].default_value = 0.2
        m.mats[P + 'logo'] = sm
    else:
        m.add(P + 'logo', '#ecedef', roughness=0.2)
    return mat


def _save_image(name, arr, path, data=False):
    h, w = arr.shape[:2]
    rgba = np.ones((h, w, 4), np.float32)
    rgba[..., :min(arr.shape[2], 4)] = np.clip(arr[..., :4], 0, 1)
    if arr.shape[2] == 3:
        rgba[..., 3] = 1
    img = bpy.data.images.new(name, w, h, alpha=False)
    if data:
        img.colorspace_settings.name = 'Non-Color'
    img.pixels.foreach_set(rgba.ravel())
    img.filepath_raw = path
    img.file_format = 'PNG'
    img.save()
    return img


# ---------------------------------------------------------------- the lamp panel (geometry on the snout's face)
def lamp_panel(part, shell):
    """lamp windows (dark glass plates), the head lamps' lenses and reflectors, the tail lamps, the camera windows"""
    x0, x1, y0, y1, r = LAMP_WIN
    for s in (1, -1):
        K.rounded_rect(part, shell, P + 'glass', s * (x0 + x1) / 2, (y0 + y1) / 2, x1 - x0, y1 - y0, r, 'z', 1,
                       lift=0.004, segments=4, rings=3)
        for x in HEAD_X:
            K.rounded_rect(part, shell, P + 'reflector', s * x, HEAD_Y, 2 * HEAD_R + 0.016, 2 * HEAD_R + 0.016,
                           HEAD_R + 0.008, 'z', 1, lift=0.007, segments=4, rings=2)
            # the inner lamp is white and red (l0_shape): its lens reads red by day
            K.rounded_rect(part, shell, P + ('tail' if x == TAIL_X else 'lamp'), s * x, HEAD_Y, 2 * HEAD_R,
                           2 * HEAD_R, HEAD_R, 'z', 1, lift=0.009, segments=4, rings=2)
    for x, y, w, h in (CAM_WIN, CAM_LOW):
        K.rounded_rect(part, shell, P + 'camera', x, y, w, h, 0.012, 'z', 1, lift=0.004, segments=3, rings=2)
        K.rounded_rect(part, shell, P + 'lens', x, y, w * 0.45, w * 0.45, w * 0.22, 'z', 1, lift=0.007, segments=4,
                       rings=2)


def lamp_centres():
    return [(s * x, HEAD_Y) for s in (1, -1) for x in HEAD_X]


# ---------------------------------------------------------------- the logo plates
def logo_plates(part, shell, nu=12, nv=6, lift=0.003):
    """the logo on both sides, reading left to right from either side"""
    z0, z1, y0, y1 = LOGO
    for s in (1, -1):
        grid = []
        for jv in range(nv + 1):
            row = []
            for iu in range(nu + 1):
                fu, fv = iu / nu, jv / nv
                # viewer's right: −z on the left side (+x), +z on the right side
                z = z1 - fu * (z1 - z0) if s > 0 else z0 + fu * (z1 - z0)
                y = y0 + fv * (y1 - y0)
                h = shell.hit((s * 5.0, y, z), (-s, 0, 0))
                if h is None:
                    row.append(None)
                    continue
                p, n = h
                if n.x * s < 0:
                    n = -n
                row.append((tuple(p + n * lift), (fu, fv)))
            grid.append(row)
        for jv in range(nv):
            for iu in range(nu):
                q = [grid[jv][iu], grid[jv][iu + 1], grid[jv + 1][iu + 1], grid[jv + 1][iu]]
                if any(c is None for c in q):
                    continue
                part.face_uv([c[0] for c in q], P + 'logo', [c[1] for c in q], out=(s, 0, 0))


# ---------------------------------------------------------------- the hood over a joint
def hood(part, z_end, sign, inset=0.05, folds=3):
    """a flexible cover from a body end (z_end, facing sign) to the joint's centre: the body section shrunk by
    `inset`, in `folds` shallow folds"""
    body = S.half_section(dict(S.BODY))
    nrm = S._normals2d(body)
    gap = S.GAP + 0.002
    zs = [z_end - sign * 0.01 + sign * gap * k / (2 * folds) for k in range(2 * folds + 1)]
    rings = []
    for k, z in enumerate(zs):
        ins = inset + (0.025 if k % 2 else 0.0)
        pts = [(max(x - nx * ins, 0.0) if 0 < j < len(body) - 1 else 0.0, y - ny * ins)
               for j, ((x, y), (nx, ny)) in enumerate(zip(body, nrm))]
        pts = [p for p in pts if p[1] > 0.55]
        rings.append((z, pts))
    for (za, A), (zb, Bp) in zip(rings, rings[1:]):
        n = min(len(A), len(Bp))
        for j in range(n - 1):
            for s in (1, -1):
                q = [(s * A[j][0], A[j][1], za), (s * Bp[j][0], Bp[j][1], zb), (s * Bp[j + 1][0], Bp[j + 1][1], zb),
                     (s * A[j + 1][0], A[j + 1][1], za)]
                if (sign > 0) == (s > 0):
                    q.reverse()
                part.face(q, P + 'hood', smooth=True)
