"""
Stock BNR34 wheels: 18 x 9J five-spoke (slender, slightly swept spokes, gunmetal), 245/40R18 tyres (outer radius
0.33 as in the game's carSpecs; real 0.327), ventilated discs (front 324 mm, rear 300 mm) and gold four-pot Brembo
calipers at the rear of the front discs, two-pot at the rear.

Each wheel is built for the car's left side (outboard = +x) in its pivot's frame and mirrored for the right side.
The tyre, rim and disc hang under spin_*; the caliper under wheel_* (it does not turn).
"""
import math

import bmesh
import numpy as np

import r34_kit as K

TRACK_F, TRACK_R = 1.48, 1.49
WHEELBASE = 2.665
R_TYRE = 0.33
SEG = 40


def _fix(f, want):
    if f is None:
        return
    f.normal_update()
    if np.dot(np.array(K.G(f.normal)), want) < 0:
        f.normal_flip()


def lathe(part, prof, mat, want, segs=SEG, uv=None, smooth=True, th0=0.0, th1=2 * math.pi, caps=False):
    """
    Revolve [(r, a)] about the x axis (a = x). want(r, a) -> (dr, da): the side each face should face.
    uv(s, k) -> (u, v) for ring s, profile point k.
    """
    closed = abs(th1 - th0 - 2 * math.pi) < 1e-9
    n = segs if closed else segs + 1
    P = []
    for s in range(n):
        th = th0 + (th1 - th0) * s / segs
        P.append([(a, r * math.cos(th), r * math.sin(th)) for r, a in prof])
    for s in range(segs):
        s2 = (s + 1) % n
        th = th0 + (th1 - th0) * (s + 0.5) / segs
        for k in range(len(prof) - 1):
            q = [P[s][k], P[s2][k], P[s2][k + 1], P[s][k + 1]]
            if prof[k][0] < 1e-6:
                q = [P[s][k], P[s2][k + 1], P[s][k + 1]]
            elif prof[k + 1][0] < 1e-6:
                q = [P[s][k], P[s2][k], P[s][k + 1]]
            uvs = None
            if uv is not None:
                uvs = [uv(s, k), uv(s + 1, k), uv(s + 1, k + 1), uv(s, k + 1)]
                if len(q) == 3:
                    uvs = [uvs[0], uvs[2] if prof[k][0] < 1e-6 else uvs[1], uvs[3]]
            f = part.face(q, mat, smooth=smooth, uvs=uvs)
            r = 0.5 * (prof[k][0] + prof[k + 1][0])
            a = 0.5 * (prof[k][1] + prof[k + 1][1])
            dr, da = want(r, a)
            _fix(f, np.array((da, dr * math.cos(th), dr * math.sin(th))))
    if caps and not closed:
        c = np.mean(np.array(prof), axis=0)
        for s, sg in ((0, -1), (n - 1, 1)):
            th = th0 if s == 0 else th1
            f = part.face(P[s], mat, smooth=False)
            _fix(f, np.array((0.0, -math.sin(th), math.cos(th))) * sg)
    return P


def tyre(part):
    prof = [(0.232, -0.112), (0.262, -0.121), (0.292, -0.123), (0.313, -0.119), (0.325, -0.108), (0.3302, -0.090),
            (0.3305, -0.045), (0.3305, 0.0), (0.3305, 0.045), (0.3302, 0.090), (0.325, 0.108), (0.313, 0.119),
            (0.292, 0.123), (0.262, 0.121), (0.232, 0.112)]
    L = np.concatenate([[0], np.cumsum([math.dist(prof[i], prof[i + 1]) for i in range(len(prof) - 1)])])
    vk = L / L[-1]
    lathe(part, prof, 'tire', lambda r, a: (r - 0.282, a), segs=SEG,
          uv=lambda s, k: (12.0 * s / SEG, float(vk[k])))


def rim(part):
    # lip and barrel: from the spokes' outer ends out over the lip to the tyre bead, and the barrel inside
    lip = [(0.219, 0.104), (0.224, 0.112), (0.229, 0.118), (0.236, 0.121), (0.242, 0.120), (0.246, 0.115),
           (0.240, 0.110), (0.232, 0.108)]
    lathe(part, lip, 'rim', lambda r, a: (0.4, 1.0) if r < 0.243 or a > 0.117 else (1.0, 0.2), segs=SEG)
    barrel = [(0.219, 0.104), (0.212, 0.080), (0.208, -0.105), (0.231, -0.112)]
    lathe(part, barrel, 'rim', lambda r, a: (-1.0, 0.0) if a > -0.1 else (-0.3, 1.0), segs=SEG)
    # hub with centre cap
    hub = [(0.0, 0.086), (0.024, 0.086), (0.029, 0.082), (0.056, 0.079), (0.074, 0.073), (0.078, 0.055),
           (0.078, 0.030)]
    lathe(part, hub, 'rim', lambda r, a: (0.3 if r > 0.08 else 0.0, 1.0), segs=30)
    # five spokes, swept slightly against the direction of travel, concave towards the lip
    for i in range(5):
        spoke(part, 2 * math.pi * i / 5 + math.pi / 2)
    # lug nuts between the spokes
    for i in range(5):
        th = 2 * math.pi * (i + 0.5) / 5 + math.pi / 2
        part.cylinder('chrome', (0.088, 0.057 * math.cos(th), 0.057 * math.sin(th)), 0.0105, 0.018, axis='x',
                      segments=6, smooth=False)


def spoke(part, th0):
    rs = np.linspace(0.064, 0.222, 10)
    loops = []
    for r in rs:
        t = (r - 0.064) / 0.158
        w = 0.044 - 0.018 * math.sin(min(t, 0.82) / 0.82 * math.pi / 2) + 0.030 * max(0.0, (t - 0.82) / 0.18) ** 2
        af = 0.079 + 0.012 * t + 0.016 * t ** 2
        depth = 0.030 - 0.008 * math.sin(t * math.pi)
        thc = th0 + 0.13 * t ** 1.4
        ring = []
        for tt, a in ((-w / 2, af - depth), (-w / 2, af - 0.007), (-w / 2 + 0.006, af), (w / 2 - 0.006, af),
                      (w / 2, af - 0.007), (w / 2, af - depth)):
            th = thc + tt / r
            ring.append((a, r * math.cos(th), r * math.sin(th)))
        loops.append((ring, (af - depth / 2, r * math.cos(thc), r * math.sin(thc))))
    m = 6
    for i in range(len(loops) - 1):
        (A, ca), (Bq, cb) = loops[i], loops[i + 1]
        c = 0.5 * (np.array(ca) + np.array(cb))
        for j in range(m):
            j2 = (j + 1) % m
            q = [A[j], A[j2], Bq[j2], Bq[j]]
            f = part.face(q, 'rim', smooth=j not in (5,))
            _fix(f, np.mean(np.array(q), axis=0) - c)


def disc(part, r):
    part.cylinder('disc', (-0.004, 0.0, 0.0), r, 0.028, axis='x', segments=40)
    part.cylinder('disc', (0.022, 0.0, 0.0), 0.088, 0.024, axis='x', segments=24)


def caliper(part, r_disc, front):
    """an arc-shaped caliper straddling the disc at the rear, a little above the axle"""
    r0, r1 = r_disc - 0.052, r_disc + 0.014
    a0, a1 = (-0.046, 0.042) if front else (-0.040, 0.034)
    span = 0.62 if front else 0.46
    thc = math.atan2(-1.0, 0.30)          # towards the rear (-z), raised (y = r cos, z = r sin)
    prof = [(r0, a0), (r1 - 0.006, a0), (r1, a0 + 0.008), (r1, a1 - 0.008), (r1 - 0.006, a1), (r0, a1), (r0, a0)]
    cr, ca = 0.5 * (r0 + r1), 0.5 * (a0 + a1)
    lathe(part, prof, 'brake', lambda r, a: (r - cr, a - ca), segs=10, th0=thc - span / 2, th1=thc + span / 2,
          smooth=False, caps=True)


def _mirror(part):
    bmesh.ops.scale(part.bm, vec=(-1.0, 1.0, 1.0), verts=part.bm.verts)
    bmesh.ops.reverse_faces(part.bm, faces=part.bm.faces)


def build(mats, root, tex):
    out = []
    for name, x, z in (('fl', TRACK_F / 2, WHEELBASE / 2), ('fr', -TRACK_F / 2, WHEELBASE / 2),
                       ('rl', TRACK_R / 2, -WHEELBASE / 2), ('rr', -TRACK_R / 2, -WHEELBASE / 2)):
        front = name[0] == 'f'
        pivot = K.empty(f'wheel_{name}', (x, R_TYRE, z), parent=root)
        spin = K.empty(f'spin_{name}', (0, 0, 0), parent=pivot)
        w = K.Part(f'wheel_{name}_turning')
        tyre(w)
        rim(w)
        disc(w, 0.162 if front else 0.150)
        c = K.Part(f'caliper_{name}')
        caliper(c, 0.162 if front else 0.150, front)
        if x < 0:
            _mirror(w)
            _mirror(c)
        out.append(('wheels', w.build(mats, parent=spin, merge_dist=0)))
        out.append(('calipers', c.build(mats, parent=pivot, merge_dist=0)))
    return out
