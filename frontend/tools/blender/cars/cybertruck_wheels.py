"""
The Cybertruck's wheels: 35-inch LT285/65R20 all-terrain tyres (chunky shoulder lugs) on the black 20-inch wheels
(six split spokes round a six-lug hub), big discs and grey calipers. Built for the left side (+x outwards) and
mirrored for the right. Pivots at the wheel centres; tyre, rim and disc under spin_*, the caliper beside spin.
"""
import math

import bmesh

import cybertruck_kit as K
import cybertruck_shape as CS

R_TYRE = 0.444          # 35 in over the lugs (LT285/65R20: 508 / 2 + 0.65 x 285 = 439 mm nominal; photos: 0.444-0.448)
R_RIM = 0.254           # 20 in bead seat
R_LIP = 0.266           # the visible rim edge (measured on the side photo: 0.267)
HALF_W = 0.148          # half section width (bulge)
SEG = 96
TREAD = 0.009           # tread block height over the groove floor
RIM_X = 0.015           # the rim's face stands this much further out than the base design (photos: caps near the sidewall)


def _lathe(part, mat, prof, seg=SEG, uv_v=None, u_tiles=16, flip=False, smooth=True):
    """revolve a profile [(r, x)] about the wheel axis (game x)"""
    rows = []
    for k in range(seg + 1):
        a = 2 * math.pi * k / seg
        rows.append([(x, r * math.cos(a), r * math.sin(a)) for r, x in prof])
    uvs = None
    if uv_v is not None:
        uvs = [[(k / seg * u_tiles, uv_v[i]) for i in range(len(prof))] for k in range(seg + 1)]
    part.grid(rows, mat, smooth=smooth, uvs=uvs, flip=not flip)


def tyre(part):
    """profile inner bead → inner sidewall → tread → outer sidewall → outer bead; the texture draws the lugs"""
    R = R_TYRE
    p = [(R_RIM + 0.004, -0.112), (0.300, -0.135), (0.350, -HALF_W), (0.398, -0.146), (0.424, -0.138), (0.438, -0.126),
         (R - TREAD, -0.110), (R - TREAD, -0.040), (R - TREAD, 0.040), (R - TREAD, 0.110), (0.438, 0.126), (0.424, 0.138), (0.398, 0.146), (0.350, HALF_W),
         (0.300, 0.135), (R_LIP + 0.004, 0.112 + RIM_X)]
    vs = [0.0, 0.10, 0.20, 0.28, 0.33, 0.36, 0.38, 0.46, 0.54, 0.62, 0.64, 0.67, 0.72, 0.80, 0.90, 1.0]
    _lathe(part, 'tire', p, uv_v=vs, u_tiles=16)
    # shoulder lugs: raised blocks on the outer shoulder (the photos show them breaking the round outline)
    n = 48
    for k in range(n):
        a0 = 2 * math.pi * (k + 0.15) / n
        a1 = 2 * math.pi * (k + 0.62) / n
        for side in (1, -1):
            rows = []
            for a in (a0, a1):
                ca, sa = math.cos(a), math.sin(a)
                rows.append([(side * 0.150, 0.388 * ca, 0.388 * sa), (side * 0.152, 0.416 * ca, 0.416 * sa),
                             (side * 0.140, (R + 0.004) * ca, (R + 0.004) * sa), (side * 0.112, (R + 0.006) * ca, (R + 0.006) * sa)])
            part.grid(rows, 'tire', smooth=False, flip=side < 0)


def tread(part, n=48):
    """the all-terrain tread: raised blocks round the tyre; the middle row staggered by half a pitch, each shoulder
    row stepped (its inner half a fifth of a pitch on) as the photos' tyres show"""
    R = R_TYRE
    rows_x = ((-0.106, -0.073, 0.0), (-0.071, -0.042, 0.2), (-0.034, 0.034, 0.5), (0.042, 0.071, 0.2), (0.073, 0.106, 0.0))
    for (x0, x1, off) in rows_x:
        for k in range(n):
            a0 = 2 * math.pi * (k + off) / n
            a1 = 2 * math.pi * (k + off + 0.62) / n
            rows = []
            for a in (a0, a1):
                ca, sa = math.cos(a), math.sin(a)
                lo, hi = R - TREAD - 0.001, R
                rows.append([(x0, lo * ca, lo * sa), (x0 + 0.004, hi * ca, hi * sa), (x1 - 0.004, hi * ca, hi * sa), (x1, lo * ca, lo * sa)])
            part.grid(rows, 'tire', smooth=False, flip=True)
            for row, flip in ((rows[0], False), (rows[1], True)):
                part.face(list(reversed(row)) if flip else row, 'tire', smooth=False)


def rim(part):
    """barrel, lip, the six split spokes, hub plate with six lug nuts and the cap (face RIM_X further out)"""
    o = RIM_X
    lip = [(R_RIM - 0.002, 0.100 + o), (R_LIP, 0.104 + o), (R_LIP + 0.002, 0.110 + o), (R_LIP - 0.010, 0.114 + o),
           (0.245, 0.106 + o), (0.240, 0.092 + o)]
    _lathe(part, 'rim', lip, flip=False)
    barrel = [(0.240, 0.092 + o), (0.243, 0.020), (0.245, -0.080), (0.250, -0.110)]
    _lathe(part, 'rim', barrel, flip=False)
    for k in range(6):
        a0 = 2 * math.pi * k / 6 + math.pi / 6
        for s in (-1, 1):
            _arm(part, a0, s)
    # hub plate: a flat disc round the nuts
    hub = [(0.0, 0.088 + o), (0.030, 0.088 + o), (0.034, 0.084 + o), (0.100, 0.084 + o), (0.108, 0.078 + o), (0.110, 0.060 + o)]
    _lathe(part, 'rim', hub, seg=24, flip=True, smooth=False)
    for k in range(6):
        a = 2 * math.pi * k / 6
        c = (0.090 + o, 0.068 * math.cos(a), 0.068 * math.sin(a))
        part.cylinder('chrome', c, 0.011, 0.016, axis='x', segments=6)
    part.cylinder('chrome', (0.093 + o, 0, 0), 0.028, 0.012, axis='x', segments=16)


def _arm(part, a0, s):
    """one arm of a split spoke: from the hub (r 0.10) to the rim lip (r 0.243), the two arms spreading apart"""
    def frame(r, off):
        a = a0 + s * off / r
        return (math.cos(a), math.sin(a)), (-math.sin(a), math.cos(a))
    rows = []
    stations = [(0.098, 0.010, 0.082), (0.140, 0.026, 0.088), (0.190, 0.046, 0.094), (0.230, 0.062, 0.098),
                (0.244, 0.067, 0.099)]
    for r, off, xf in stations:
        rad, tang = frame(r, off)
        hw = 0.0105 + 0.004 * (r - 0.1) / 0.14
        depth = 0.032
        cy, cz = rad[0] * r, rad[1] * r
        sec = []
        for t, dx in ((-hw * 0.85, -depth), (-hw, -0.003), (-hw * 0.7, 0.0), (hw * 0.7, 0.0), (hw, -0.003), (hw * 0.85, -depth)):
            sec.append((xf + RIM_X + dx, cy + tang[0] * t, cz + tang[1] * t))
        rows.append(sec)
    part.grid(rows, 'rim', flip=True, smooth=False)


def disc(part, front):
    r = 0.190 if front else 0.180
    x0, x1 = -0.030, 0.000
    prof = [(0.110, x1), (r, x1), (r, x0), (0.110, x0)]
    _lathe(part, 'disc', prof, seg=48, flip=True)
    part.cylinder('disc', (0.020, 0, 0), 0.105, 0.04, axis='x', segments=24)


def caliper(part, front):
    """caliper block over the disc's edge, behind the axle, at the top"""
    r = 0.190 if front else 0.180
    ang = math.radians(150 if front else 30)
    w = 0.16 if front else 0.12
    n = 6
    seg = []
    for k in range(n + 1):
        a = ang + (k / n - 0.5) * w / r
        ry, rz = math.sin(a), math.cos(a)
        inner, outer = r - 0.045, r + 0.018
        seg.append([(0.040, inner * ry, inner * rz), (0.040, outer * ry, outer * rz), (-0.065, outer * ry, outer * rz),
                    (-0.065, inner * ry, inner * rz), (0.040, inner * ry, inner * rz)])
    part.grid(seg, 'brake', flip=False)
    for end in (0, n):
        q = seg[end][:4]
        part.face(q if end == 0 else list(reversed(q)), 'brake')


def build(root, mats, P):
    """four pivots with spin children; returns (pivots, triangle counts)"""
    count, pivots = {}, {}
    tf = P['track'] / 2
    for name, x, z, front in (('fl', tf, CS.WB / 2, True), ('fr', -tf, CS.WB / 2, True),
                              ('rl', tf, -CS.WB / 2, False), ('rr', -tf, -CS.WB / 2, False)):
        pivot = K.empty(f'wheel_{name}', (x, P['hub_y'], z), parent=root)
        spin = K.empty(f'spin_{name}', (0, 0, 0), parent=pivot)
        roll = K.Part(f'wheel_{name}_roll')
        tyre(roll)
        tread(roll)
        rim(roll)
        disc(roll, front)
        cal = K.Part(f'wheel_{name}_caliper')
        caliper(cal, front)
        if x < 0:
            for p in (roll, cal):
                _mirror_x(p)
        count[name] = roll.tris() + cal.tris()
        roll.build(spin, mats, sharp=35.0)
        cal.build(pivot, mats, sharp=35.0)
        pivots[name] = pivot
    return pivots, count


def _mirror_x(part):
    bmesh.ops.scale(part.bm, vec=(-1, 1, 1), verts=part.bm.verts)
    bmesh.ops.reverse_faces(part.bm, faces=part.bm.faces)
