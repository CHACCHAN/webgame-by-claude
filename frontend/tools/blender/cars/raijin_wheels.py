"""
The GDB STI's wheels: 225/45R17 tyres on the stock 17 × 7.5J twin-five-spoke (ten spokes in pairs) wheels, brake
discs and the Brembo calipers (four-pot front, two-pot rear). Built for the left side (+x outwards) and mirrored for
the right. Pivots at the wheel centres; tyre, rim and disc under spin_*, the caliper beside spin (it steers, it does
not roll).
"""
import math

import bmesh
from mathutils import Matrix, Vector

import raijin_kit as K
import raijin_shell as SH

R_TYRE = 0.320          # carSpecs wheelRadius (225/45R17: 0.317)
R_RIM = 0.2159          # 17 in bead seat
TRACK_F, TRACK_R = 1.485, 1.480
SEG = 48


def _lathe(part, mat, prof, seg=SEG, uv_v=None, u_tiles=12, flip=False, smooth=True):
    """revolve a profile [(r, x)] about the wheel axis (game x); faces outwards when the profile runs inner → outer
    over the top (r increasing then decreasing ...)"""
    rows = []
    for k in range(seg + 1):
        a = 2 * math.pi * k / seg
        rows.append([(x, r * math.cos(a), r * math.sin(a)) for r, x in prof])
    uvs = None
    if uv_v is not None:
        uvs = [[(k / seg * u_tiles, uv_v[i]) for i in range(len(prof))] for k in range(seg + 1)]
    part.grid(rows, mat, smooth=smooth, uvs=uvs, flip=not flip)


def tyre(part):
    # profile: inner bead → inner sidewall → tread (with grooves) → outer sidewall → outer bead
    w = 0.1125
    p = [(R_RIM + 0.006, -0.094), (0.240, -0.106), (0.268, -w), (0.292, -0.108), (0.308, -0.098), (0.316, -0.088),
         (R_TYRE, -0.075)]
    vs = [0.02, 0.10, 0.20, 0.27, 0.32, 0.345, 0.36]
    # tread with four circumferential grooves (8 mm deep)
    grooves = (-0.048, -0.017, 0.017, 0.048)
    x = -0.075
    for g in grooves:
        for dx, r in ((-0.005, R_TYRE), (-0.004, R_TYRE - 0.008), (0.004, R_TYRE - 0.008), (0.005, R_TYRE)):
            p.append((r, g + dx))
            vs.append(0.36 + 0.28 * (g + dx + 0.075) / 0.15)
    p += [(R_TYRE, 0.075), (0.316, 0.088), (0.308, 0.098), (0.292, 0.108), (0.268, w), (0.240, 0.106), (R_RIM + 0.006, 0.094)]
    vs += [0.64, 0.655, 0.68, 0.73, 0.80, 0.90, 0.98]
    _lathe(part, 'tire', p, uv_v=vs)


def rim(part):
    """barrel, lip, the ten spokes in five pairs, hub, nuts, cap"""
    # outer lip and the barrel's inside (seen through the spokes)
    lip = [(R_RIM - 0.004, 0.096), (R_RIM + 0.008, 0.098), (R_RIM + 0.010, 0.104), (R_RIM - 0.002, 0.107), (0.200, 0.100),
           (0.196, 0.088)]
    _lathe(part, 'rim', lip, flip=False)
    barrel = [(0.196, 0.088), (0.199, 0.020), (0.200, -0.060), (0.205, -0.095)]
    _lathe(part, 'rim', barrel, flip=False)
    # spokes: pairs every 72°, each spoke a tapered bar from the hub to the lip, dished outwards at the rim
    for k in range(5):
        a0 = 2 * math.pi * k / 5
        for s in (-1, 1):
            _spoke(part, a0, s)
    # hub face and centre
    hub = [(0.0, 0.063), (0.026, 0.063), (0.029, 0.059), (0.052, 0.059), (0.064, 0.062), (0.070, 0.056), (0.072, 0.040)]
    _lathe(part, 'rim', hub, seg=30, flip=True)
    for k in range(5):
        a = 2 * math.pi * (k + 0.5) / 5
        c = (0.066, 0.050 * math.cos(a), 0.050 * math.sin(a))
        part.cylinder('chrome', c, 0.0085, 0.016, axis='x', segments=6)
    part.cylinder('chrome', (0.066, 0, 0), 0.024, 0.010, axis='x', segments=16)


def _spoke(part, a0, s):
    """one spoke of a pair: from the hub (r 0.075) to the lip (r 0.198); the pair spreads towards the rim"""
    def frame(r, off):
        a = a0 + s * off / r
        return Vector((0.0, math.cos(a), math.sin(a))), Vector((0.0, -math.sin(a), math.cos(a)))
    rows = []
    stations = [(0.060, 0.007, 0.060), (0.100, 0.011, 0.070), (0.145, 0.016, 0.080), (0.185, 0.021, 0.088), (0.199, 0.023, 0.091)]
    for r, off, xf in stations:
        radial, tang = frame(r, off)
        hw = 0.0068 + 0.0030 * (r - 0.07) / 0.13
        depth = 0.024
        c = radial * r
        # cross-section: back-left, front-left (rounded), front-right, back-right
        sec = [c + tang * (-hw * 0.8) + Vector((xf - depth, 0, 0)), c + tang * (-hw) + Vector((xf - 0.004, 0, 0)),
               c + tang * (-hw * 0.55) + Vector((xf, 0, 0)), c + tang * (hw * 0.55) + Vector((xf, 0, 0)),
               c + tang * hw + Vector((xf - 0.004, 0, 0)), c + tang * (hw * 0.8) + Vector((xf - depth, 0, 0))]
        rows.append([tuple(v) for v in sec])
    part.grid(rows, 'rim', flip=True)


def disc(part, front):
    r = 0.163 if front else 0.150
    x0, x1 = -0.020, 0.008
    prof = [(0.085, x1), (r, x1), (r, x0), (0.085, x0)]
    _lathe(part, 'disc', prof, seg=32, flip=True)
    # hat
    part.cylinder('disc', (0.020, 0, 0), 0.080, 0.03, axis='x', segments=24)


def caliper(part, front):
    """Brembo block over the disc's edge, behind the axle (front) / ahead of it (rear), at the top"""
    r = 0.163 if front else 0.150
    ang = math.radians(150 if front else 30)   # from +z towards +y: 150° = rear and up
    w = 0.13 if front else 0.10                # along the disc's edge
    n = 6
    # a closed box bent along the disc: outer face, top, inner face, bottom
    seg = []
    for k in range(n + 1):
        a = ang + (k / n - 0.5) * w / r
        ry, rz = math.sin(a), math.cos(a)
        inner, outer = r - 0.040, r + 0.016
        seg.append([(0.045, inner * ry, inner * rz), (0.045, outer * ry, outer * rz), (-0.050, outer * ry, outer * rz),
                    (-0.050, inner * ry, inner * rz), (0.045, inner * ry, inner * rz)])
    part.grid(seg, 'brake', flip=False)
    for end in (0, n):
        q = seg[end][:4]
        part.face(q if end == 0 else list(reversed(q)), 'brake')


def build(root, mats):
    """four pivots with spin children; returns their names and triangle counts"""
    count = {}
    pivots = {}
    for name, x, z, front in (('fl', TRACK_F / 2, SH.FRONT_AXLE, True), ('fr', -TRACK_F / 2, SH.FRONT_AXLE, True),
                              ('rl', TRACK_R / 2, SH.REAR_AXLE, False), ('rr', -TRACK_R / 2, SH.REAR_AXLE, False)):
        pivot = K.empty(f'wheel_{name}', (x, R_TYRE, z), parent=root)
        spin = K.empty(f'spin_{name}', (0, 0, 0), parent=pivot)
        roll = K.Part(f'wheel_{name}_roll')
        tyre(roll)
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
