"""
lampfit.py (Blender): the lamp outlines of u9_data.py moved over the body until they best match their tracings in
every photo at once (fitdata/u9/lamps.json). A single photo fixes a lamp only up to depth (the head lamps came from
the head-on c12, the tail band from the straight-behind c18); the three-quarter photos (c00, c32, c17) give that depth.

The outline keeps its shape and stays on the shell: its points (u, v) in the lamp's frame (as u9_details lays the lamp
out) go through a low-dimensional warp (the head lamp: an affine map; the tail band: its half-width, height, height
position and a bow across), then onto the undeformed shell along the lamp's projection direction; the fitted field and
each photo's pose carry them into the photo. Levenberg-Marquardt on the warp: residuals are the outline distances both
ways (model outline samples -> traced outline, traced outline samples -> model outline, px), with a pull toward no
warp (--keep). Mirrored tracings (the car's right lamp; the outline is laid out on the left) are matched with x -> -x.
(Free points per vertex folded the outlines: the photos disagree by ~2 % among themselves.)

  blender.sh -t 6 -b --factory-startup --python lampfit.py -- <lamps.json> <cams.json> <ffd.json> <out.json>
      [--which hl,tl] [--iters 12] [--keep 0.05] [--w c12:1.4,... (per-photo weights)]
Out: {"HL": [[x, y, z] ...], "TL": [...]} (design frame; u9_data's order), read by tools/mkdata.py --lamps.
"""
import json, math, os, sys

sys.dont_write_bytecode = True
REPO_CARS = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'))
sys.path.insert(0, REPO_CARS)

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

import u9_kit as K
import u9_body as BD
import u9_ffd as FF
import u9_parts as PT
import u9_data as D

argv = sys.argv[sys.argv.index('--') + 1:]
traces = json.load(open(argv[0]))['photos']
camdata = json.load(open(argv[1]))
L = FF.Lattice.load(argv[2])
outp = argv[3]


def opt(k, d=None):
    return type(d)(argv[argv.index(k) + 1]) if k in argv else d


WHICH = opt('--which', 'hl,tl').split(',')
PW = {k: float(v) for k, v in (t.split(':') for t in opt('--w', '').split(',') if t)}   # per-photo weights
ITERS = opt('--iters', 12)
KEEP = opt('--keep', 0.05)

K.clear_scene()
shell = BD.shell('shell', PT.materials()).build(None, weld=0)
me = shell.data
co = np.empty(len(me.vertices) * 3)
me.vertices.foreach_get('co', co)
V0 = FF.blender_to_game(co.reshape(-1, 3))
me.calc_loop_triangles()
T = np.empty(len(me.loop_triangles) * 3, int)
me.loop_triangles.foreach_get('vertices', T)
T = T.reshape(-1, 3)
bvh0 = BVHTree.FromPolygons([Vector(v) for v in V0.tolist()], [tuple(t) for t in T.tolist()], all_triangles=True)


def basis(yaw, pitch, roll):
    d = np.array([math.sin(yaw) * math.cos(pitch), math.sin(pitch), math.cos(yaw) * math.cos(pitch)])
    r = np.cross(d, [0, 1, 0])
    r /= np.linalg.norm(r)
    u = np.cross(r, d)
    c, s = math.cos(roll), math.sin(roll)
    return d, c * r + s * u, -s * r + c * u


def project(n, X):
    c = camdata['cams'][n]
    p = camdata.get('pose', {}).get(n, {})
    th = math.radians(p.get('pitch_deg', 0.0))
    cth, sth = math.cos(th), math.sin(th)
    Xp = np.stack([X[:, 0], X[:, 1] * cth + X[:, 2] * sth + p.get('dy', 0.0), X[:, 2] * cth - X[:, 1] * sth], 1)
    d, r, u = basis(*c[3:6])
    q = Xp - np.array(c[:3])
    W, H = c[7]
    z = q @ d
    return np.stack([W / 2 + c[6] * (q @ r) / z, H / 2 - c[6] * (q @ u) / z], 1)


class Fr:
    def __init__(self, c, d, e1):
        self.c, self.d = np.array(c, float), np.array(d, float) / np.linalg.norm(d)
        e1 = np.array(e1, float)
        self.e1 = e1 - self.d * (e1 @ self.d)
        self.e1 /= np.linalg.norm(self.e1)
        self.e2 = np.cross(self.d, self.e1)

    def uv(self, P):
        q = np.asarray(P) - self.c
        return np.stack([q @ self.e1, q @ self.e2], -1)

    def hit(self, UV):
        out = []
        for u, v in UV:
            o = self.c + self.e1 * u + self.e2 * v + self.d * 1.2
            h = bvh0.ray_cast(Vector(o.tolist()), Vector((-self.d).tolist()), 3.6)
            out.append(np.array(h[0]) if h[0] is not None else self.c + self.e1 * u + self.e2 * v)
        return np.array(out)


def resample(poly, step, closed=True):
    P = np.asarray(poly, float)
    if closed:
        P = np.vstack([P, P[:1]])
    out = []
    for a, b in zip(P[:-1], P[1:]):
        k = max(1, int(math.ceil(np.linalg.norm(b - a) / step)))
        for j in range(k):
            out.append(a + (b - a) * j / k)
    return np.array(out)


def seg_dist(Q, poly):
    """distance from each point of Q to the closed polyline poly"""
    A = np.asarray(poly)
    B = np.roll(A, -1, 0)
    AB = B - A
    L2 = np.maximum((AB ** 2).sum(1), 1e-12)
    t = np.clip(((Q[:, None, :] - A[None]) * AB[None]).sum(-1) / L2[None], 0, 1)
    P = A[None] + t[..., None] * AB[None]
    return np.sqrt(((Q[:, None, :] - P) ** 2).sum(-1)).min(1)


def mirror(X):
    return X * np.array([-1, 1, 1])


# ---------------------------------------------------------------- the lamps
specs = {}
if 'hl' in WHICH:
    P0 = np.array(D.HL, float)
    c = P0.mean(0)
    obs = [(n, k, k.endswith('_R')) for n, v in traces.items() for k in v if k.startswith('hl')]
    specs['HL'] = dict(P0=P0, fr=Fr(c, D.HL_D, (1, 0, 0)), obs=obs, full=lambda X: X)
if 'tl' in WHICH:
    P0 = np.array(D.TL, float)
    obs = [(n, k, False) for n, v in traces.items() for k in v if k.startswith('tl')]
    # the band: the left half (centre top -> outer end -> centre bottom) and its mirror image
    specs['TL'] = dict(P0=P0, fr=Fr((0, 0, -2.3), (0, 0, -1), (-1, 0, 0)), obs=obs,
                       full=lambda X: np.vstack([X, mirror(X[::-1])[1:-1]]))

res_out = {}
for name, sp in specs.items():
    fr, P0, full = sp['fr'], sp['P0'], sp['full']
    UV0 = fr.uv(P0)
    n = len(UV0)
    tr = {(ph, k): resample(traces[ph][k]['poly'], 3.0) for ph, k, m in sp['obs'] if ph in camdata['cams']}
    trpoly = {(ph, k): np.array(traces[ph][k]['poly'], float) for ph, k, m in sp['obs'] if ph in camdata['cams']}
    obs = [o for o in sp['obs'] if o[0] in camdata['cams']]
    print(name, 'points', n, 'tracings', [(o[0], o[1]) for o in obs])

    cu = UV0.mean(0)

    def warp(x):
        if name == 'HL':          # an affine map of the outline in the lamp's frame (no folding, the shape kept)
            A = np.array([[1 + x[0], x[1]], [x[2], 1 + x[3]]])
            return (UV0 - cu) @ A.T + cu + x[4:6]
        # the band: its half-width, height, height position and a bow across
        U, V = UV0[:, 0], UV0[:, 1]
        return np.stack([U * (1 + x[0]), (V - cu[1]) * (1 + x[1]) + cu[1] + x[2] + x[3] * U ** 2], 1)

    def model_pts(x):
        X = fr.hit(warp(x))
        return X + L.displace(X)

    def residuals(x, report=False):
        XD = model_pts(x)
        F = full(XD)
        r = []
        rep = {}
        for ph, k, m in obs:
            Fm = mirror(F) if m else F
            poly = project(ph, Fm)
            samp = np.concatenate([poly + (np.roll(poly, -1, 0) - poly) * t for t in (0, 0.25, 0.5, 0.75)])
            a = seg_dist(samp, trpoly[(ph, k)])
            b = seg_dist(tr[(ph, k)], poly)
            wa, wb = PW.get(ph, 1.0) / math.sqrt(len(a)), PW.get(ph, 1.0) / math.sqrt(len(b))
            r += list(a * wa) + list(b * wb)
            if report:
                d_ = np.concatenate([a, b])
                rep[f'{ph}:{k}'] = (round(float(np.percentile(d_, 95)), 1), round(float(d_.max()), 1))
        r += list(x / KEEP * 0.05)
        return (np.array(r), rep) if report else np.array(r)

    x = np.zeros(6 if name == 'HL' else 4)
    r, rep = residuals(x, True)
    print(name, 'start cost', round(float(r @ r), 3), rep, flush=True)
    lam = 1e-2
    for it in range(ITERS):
        r = residuals(x)
        J = np.zeros((len(r), len(x)))
        h = 1e-3
        for j in range(len(x)):
            x2 = x.copy()
            x2[j] += h
            J[:, j] = (residuals(x2) - r) / h
        A = J.T @ J
        g = J.T @ r
        while True:
            dx = -np.linalg.solve(A + lam * np.diag(np.diag(A) + 1e-9), g)
            r2 = residuals(x + dx)
            if r2 @ r2 < r @ r:
                x = x + dx
                lam = max(lam / 3, 1e-6)
                break
            lam *= 4
            if lam > 1e6:
                break
        rr, rep = residuals(x, True)
        print(name, 'iter', it, 'cost', round(float(rr @ rr), 3), 'max |duv|', round(float(np.abs(x).max()), 3), rep, flush=True)
        if lam > 1e6:
            break
    XD = fr.hit(warp(x))
    res_out[name] = [[round(float(v), 4) for v in p] for p in XD]
    res_out[name + '_warp'] = [round(float(v), 4) for v in x]
json.dump(res_out, open(outp, 'w'), indent=1)
print('WROTE', outp)
