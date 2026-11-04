"""
The FD3S's wheels (late Type RS): 17-inch forged five-spoke rims with spokes widening into the rim, 235/45R17
tyres scaled to the game's 0.31 m outer radius, ventilated discs and the calipers.

Pivots wheel_fl/fr/rl/rr sit at the wheel centres (children of the root); each has a child spin_* holding tyre,
rim and disc. The calipers hang under the pivot so they do not turn with the wheel.
"""
import math

import bpy
import numpy as np

import shiden_shape as SH
from shiden_surf import B, Mesh

R_OUT = SH.TYRE_R          # tyre outer radius (game spec)
R_RIM = 0.216              # 17-inch bead seat
R_LIP = 0.226              # rim flange
W_TYRE = 0.235
N_SEG = 40                 # segments round the wheel
SPOKES = 5
PCD = 0.1143 / 2


def _empty(name, parent, loc):
    e = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(e)
    e.location = B(*loc)
    e.parent = parent
    return e


def lathe(mesh, prof, mat, s, centre, n=N_SEG, smooth=True, a0=0.0, sharp_at=()):
    """
    Revolve a profile [(r, x)] round the wheel axis (game x). s = +1 for the left wheels (outer face +x), −1 for
    the right. `centre` (r, x): the faces point away from it in the profile plane.
    """
    cr, cx = centre
    for i in range(n):
        a1 = a0 + 2 * math.pi * i / n
        a2 = a0 + 2 * math.pi * (i + 1) / n
        for j in range(len(prof) - 1):
            (r1, x1), (r2, x2) = prof[j], prof[j + 1]
            if abs(r1 - r2) < 1e-9 and abs(x1 - x2) < 1e-9:
                continue
            pts = [(s * x1, r1 * math.cos(a1), r1 * math.sin(a1)), (s * x1, r1 * math.cos(a2), r1 * math.sin(a2)),
                   (s * x2, r2 * math.cos(a2), r2 * math.sin(a2)), (s * x2, r2 * math.cos(a1), r2 * math.sin(a1))]
            if r1 < 1e-9:
                pts = [pts[0], pts[2], pts[3]]
            elif r2 < 1e-9:
                pts = pts[:3]
            # outward in the profile plane: from the profile's centre point through the segment's middle
            mr, mx = (r1 + r2) / 2 - cr, (x1 + x2) / 2 - cx
            am = (a1 + a2) / 2
            out = (s * mx, mr * math.cos(am), mr * math.sin(am))
            mesh.face(pts, mat, smooth=smooth, out=out)


def tyre(mesh, s):
    """235/45R17 squeezed to the game radius: bead, bulging sidewall with a rim guard, rounded shoulder, tread
    with four circumferential grooves; closed torus"""
    h = W_TYRE / 2
    side = [(R_RIM - 0.004, 0.103), (R_RIM + 0.014, 0.112), (R_RIM + 0.024, 0.113), (0.255, 0.117),
            (0.278, 0.118), (0.296, 0.112), (0.306, 0.100)]
    tread = []
    grooves = (0.045, -0.045)
    xs = [0.092]
    for g in grooves:
        xs += [g + 0.008, g + 0.0075, g - 0.0075, g - 0.008]
    xs.append(-0.092)
    for k, x in enumerate(xs):
        in_groove = k % 4 in (2, 3) and 0 < k < len(xs) - 1
        tread.append((R_OUT - (0.009 if in_groove else 0.0), x))
    prof = side + tread + [(r, -x) for r, x in reversed(side)]
    # inner liner: closes the torus at the bead
    prof.append((R_RIM - 0.004, 0.103))
    lathe(mesh, prof, 'tire', s, centre=(0.263, 0.0))
    return h


def rim(mesh, s):
    """barrel and flanges (lathe), five spokes widening towards the rim, hub with nuts and centre cap"""
    # barrel: outer flange → inside of the barrel → inner flange (faces point at the axle inside)
    outer = [(R_LIP + 0.004, 0.100), (R_LIP + 0.006, 0.106), (R_LIP, 0.112), (R_RIM, 0.110), (R_RIM - 0.010, 0.100)]
    lathe(mesh, outer, 'rim', s, centre=(0.20, 0.06))
    barrel = [(R_RIM - 0.010, 0.100), (0.197, 0.085), (0.197, -0.095), (R_RIM - 0.004, -0.104)]
    lathe(mesh, barrel, 'rim', s, centre=(0.40, 0.0))
    # the bead seat between tyre and flange
    lathe(mesh, [(R_RIM - 0.004, 0.103), (R_LIP + 0.004, 0.100)], 'rim', s, centre=(0.22, 0.2))
    # spokes: each a loft between an inner (hub) and outer (rim) section; front face convex, slightly dished
    n_r = 9
    for k in range(SPOKES):
        th = 2 * math.pi * k / SPOKES + math.pi / 2
        rows = []
        for i in range(n_r + 1):
            t = i / n_r
            r = 0.068 + (0.200 - 0.068) * t
            hw = 0.033 + 0.016 * t + 0.026 * max(0.0, (t - 0.72) / 0.28) ** 2    # half width (m): broad spokes
            xf = 0.101 - 0.005 * t + 0.008 * max(0.0, (t - 0.82) / 0.18) ** 2     # front face: nearly flat
            xb = xf - 0.030
            row = []
            for u, x in ((-1.0, xb), (-1.0, xf - 0.006), (-0.6, xf), (0.0, xf + 0.003), (0.6, xf), (1.0, xf - 0.006),
                         (1.0, xb)):
                a = th + u * hw / r
                row.append((s * x, r * math.cos(a), r * math.sin(a)))
            rows.append(row)
        P = np.array(rows)
        for i in range(n_r):
            for j in range(len(rows[0]) - 1):
                q = [P[i, j], P[i + 1, j], P[i + 1, j + 1], P[i, j + 1]]
                # outward: sides point across the spoke, the face points +x
                if j == 0 or j == len(rows[0]) - 2:
                    sgn = -1 if j == 0 else 1
                    out = (0.0, -math.sin(th) * sgn, math.cos(th) * sgn)
                else:
                    out = (s, 0.0, 0.0)
                mesh.face([tuple(p) for p in q], 'rim', out=out)
        # back of the spoke
        for i in range(n_r):
            q = [P[i, 0], P[i + 1, 0], P[i + 1, -1], P[i, -1]]
            mesh.face([tuple(p) for p in q], 'rim', out=(-s, 0, 0))
    # hub: a dished disc with a raised ring
    hub = [(0.0, 0.094), (0.026, 0.094), (0.030, 0.099), (0.058, 0.101), (0.070, 0.101),
           (0.074, 0.090), (0.074, 0.060)]
    lathe(mesh, hub, 'rim', s, centre=(0.0, 0.0), n=25)
    # centre cap
    cap = [(0.0, 0.103), (0.016, 0.102), (0.021, 0.098), (0.022, 0.094)]
    lathe(mesh, cap, 'chrome', s, centre=(0.0, 0.0), n=20)
    # wheel nuts
    for k in range(SPOKES):
        a = 2 * math.pi * k / SPOKES + math.pi / 2 + math.pi / SPOKES
        cy, cz = PCD * math.cos(a), PCD * math.sin(a)
        n = 6
        ring_in, ring_out = [], []
        for i in range(n):
            b = 2 * math.pi * i / n
            ring_in.append((s * 0.098, cy + 0.0095 * math.cos(b), cz + 0.0095 * math.sin(b)))
            ring_out.append((s * 0.108, cy + 0.0085 * math.cos(b), cz + 0.0085 * math.sin(b)))
        for i in range(n):
            i2 = (i + 1) % n
            b = 2 * math.pi * (i + 0.5) / n
            mesh.face([ring_in[i], ring_in[i2], ring_out[i2], ring_out[i]], 'chrome', smooth=False,
                      out=(0, math.cos(b), math.sin(b)))
        mesh.face(ring_out, 'chrome', smooth=False, out=(s, 0, 0))


def disc(mesh, s):
    """ventilated disc: friction ring with the vane gap, hat to the hub"""
    r_o, r_i = 0.147, 0.088
    ring = [(r_i, 0.032), (r_o, 0.032), (r_o, 0.006), (r_i, 0.006), (r_i, 0.032)]
    lathe(mesh, ring, 'brake', s, centre=((r_o + r_i) / 2, 0.019), n=32)
    hat = [(r_i, 0.032), (0.078, 0.036), (0.074, 0.050), (0.0, 0.050)]
    lathe(mesh, hat, 'brake', s, centre=(0.0, 0.0), n=24)


def caliper(mesh, s, front):
    """a fixed caliper straddling the disc behind the axle (game −z), a little above the centre"""
    a_mid = math.radians(75 if front else 105)      # angle from +y (up) towards −z (rearwards)
    span = math.radians(44 if front else 36)
    r0, r1 = 0.108, 0.162
    x0, x1 = -0.010, 0.046
    n = 8
    pts = lambda r, a, x: (s * x, r * math.cos(a), -r * math.sin(a))
    a0, a1 = a_mid - span / 2, a_mid + span / 2
    for i in range(n):
        a, b = a0 + (a1 - a0) * i / n, a0 + (a1 - a0) * (i + 1) / n
        m = (a + b) / 2
        # outer face, top (r1), bottom (r0), inner face
        mesh.face([pts(r0, a, x1), pts(r0, b, x1), pts(r1, b, x1), pts(r1, a, x1)], 'brake', smooth=False,
                  out=(s, 0, 0))
        mesh.face([pts(r1, a, x0), pts(r1, b, x0), pts(r1, b, x1), pts(r1, a, x1)], 'brake',
                  out=(0, math.cos(m), -math.sin(m)))
        mesh.face([pts(r0, a, x0), pts(r0, b, x0), pts(r0, b, x1), pts(r0, a, x1)], 'brake',
                  out=(0, -math.cos(m), math.sin(m)))
        mesh.face([pts(r0, a, x0), pts(r0, b, x0), pts(r1, b, x0), pts(r1, a, x0)], 'brake', smooth=False,
                  out=(-s, 0, 0))
    for a, sg in ((a0, -1), (a1, 1)):
        t = (0, -math.sin(a) * sg, -math.cos(a) * sg)
        mesh.face([pts(r0, a, x0), pts(r1, a, x0), pts(r1, a, x1), pts(r0, a, x1)], 'brake', smooth=False, out=t)


def build(root, mats, counts):
    for name, s, z in (('fl', 1, SH.ZF), ('fr', -1, SH.ZF), ('rl', 1, SH.ZR), ('rr', -1, SH.ZR)):
        piv = _empty(f'wheel_{name}', root, (s * SH.TRACK / 2, SH.TYRE_R, z))
        spin = _empty(f'spin_{name}', piv, (0, 0, 0))
        m = Mesh(f'tyre_{name}')
        tyre(m, s)
        counts[f'tyre_{name}'] = m.tris()
        m.build(spin, mats, weld=1e-6)
        m = Mesh(f'rim_{name}')
        rim(m, s)
        counts[f'rim_{name}'] = m.tris()
        m.build(spin, mats, weld=1e-6)
        m = Mesh(f'disc_{name}')
        disc(m, s)
        counts[f'disc_{name}'] = m.tris()
        m.build(spin, mats, weld=1e-6)
        m = Mesh(f'caliper_{name}')
        caliper(m, s, name[0] == 'f')
        counts[f'caliper_{name}'] = m.tris()
        m.build(piv, mats, weld=1e-6)
