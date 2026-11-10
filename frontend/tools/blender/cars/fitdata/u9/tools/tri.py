"""
tri.py (Blender): feature points seen in several photos -> 3-D points by triangulation (least squares over the solved
cameras' rays, each photo's body pose undone), set against the fitted body: the reprojection error per photo, the
distance to the fitted (deformed) shell, and the nearest shell point carried back to the design frame (as trace3d.py).
A point traced on the car's other side is mirrored (x -> -x) before it joins the rays: give its photo as "<photo>:m".

  blender.sh -t 6 -b --factory-startup --python tri.py -- <points.json> <cams.json> <ffd.json> <out.json>

points.json: {"<feature>": {"<photo>[:m]": [x, y], ...}, ...} (pixels of the 1280-wide photos)
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

argv = sys.argv[sys.argv.index('--') + 1:]
pts = json.load(open(argv[0]))
camdata = json.load(open(argv[1]))
L = FF.Lattice.load(argv[2])
outp = argv[3]

K.clear_scene()
mats = PT.materials()
shell = BD.shell('shell', mats).build(None, weld=0)
me = shell.data
co = np.empty(len(me.vertices) * 3)
me.vertices.foreach_get('co', co)
V0 = FF.blender_to_game(co.reshape(-1, 3))
me.calc_loop_triangles()
T = np.empty(len(me.loop_triangles) * 3, int)
me.loop_triangles.foreach_get('vertices', T)
T = T.reshape(-1, 3)
VD = V0 + L.displace(V0)
bvh = BVHTree.FromPolygons([Vector(v) for v in VD.tolist()], [tuple(t) for t in T.tolist()], all_triangles=True)


def basis(yaw, pitch, roll):
    d = np.array([math.sin(yaw) * math.cos(pitch), math.sin(pitch), math.cos(yaw) * math.cos(pitch)])
    r = np.cross(d, [0, 1, 0])
    r /= np.linalg.norm(r)
    u = np.cross(r, d)
    c, s = math.cos(roll), math.sin(roll)
    return d, c * r + s * u, -s * r + c * u


def unpose(P, dy, th):
    """posed -> body frame (inverse of y' = y cos + z sin + dy, z' = z cos - y sin)"""
    c, s = math.cos(th), math.sin(th)
    y, z = P[1] - dy, P[2]
    return np.array([P[0], y * c - z * s, y * s + z * c])


def unrot(D, th):
    c, s = math.cos(th), math.sin(th)
    return np.array([D[0], D[1] * c - D[2] * s, D[1] * s + D[2] * c])


def project(n, X):
    c = camdata['cams'][n]
    p = camdata.get('pose', {}).get(n, {})
    th = math.radians(p.get('pitch_deg', 0.0))
    cth, sth = math.cos(th), math.sin(th)
    Xp = np.array([X[0], X[1] * cth + X[2] * sth + p.get('dy', 0.0), X[2] * cth - X[1] * sth])
    d, r, u = basis(*c[3:6])
    q = Xp - np.array(c[:3])
    W, H = c[7]
    return np.array([W / 2 + c[6] * (q @ r) / (q @ d), H / 2 - c[6] * (q @ u) / (q @ d)])


out = {}
for feat, obs in pts.items():
    if feat.startswith('_'):
        continue
    A = np.zeros((3, 3))
    b = np.zeros(3)
    rays = []
    for key, (x, y) in obs.items():
        n, m = (key.split(':') + [''])[:2]
        c = camdata['cams'][n]
        p = camdata.get('pose', {}).get(n, {})
        th = math.radians(p.get('pitch_deg', 0.0))
        d, r, u = basis(*c[3:6])
        W, H = c[7]
        ray = d + ((x - W / 2) / c[6]) * r - ((y - H / 2) / c[6]) * u
        ray /= np.linalg.norm(ray)
        o = unpose(np.array(c[:3]), p.get('dy', 0.0), th)
        v = unrot(ray, th)
        if m == 'm':
            o = o * [-1, 1, 1]
            v = v * [-1, 1, 1]
        rays.append((key, o, v, (x, y)))
        Pm = np.eye(3) - np.outer(v, v)
        A += Pm
        b += Pm @ o
    X = np.linalg.solve(A, b) if len(rays) > 1 else None
    res = {'rays': len(rays)}
    if X is not None:
        res['xyz'] = [round(float(v), 4) for v in X]
        errs = {}
        for key, o, v, xy in rays:
            n, m = (key.split(':') + [''])[:2]
            Xs = X * [-1, 1, 1] if m == 'm' else X
            errs[key] = round(float(np.linalg.norm(project(n, Xs) - np.array(xy))), 1)
        res['reproj_px'] = errs
        loc, nrm, ti, dist = bvh.find_nearest(Vector(X.tolist()))
        a, bb, cc = T[ti]
        A_, B_, C_ = VD[a], VD[bb], VD[cc]
        v0, v1, v2 = B_ - A_, C_ - A_, np.array(loc) - A_
        d00, d01, d11, d20, d21 = v0 @ v0, v0 @ v1, v1 @ v1, v2 @ v0, v2 @ v1
        den = d00 * d11 - d01 * d01
        w1 = (d11 * d20 - d01 * d21) / den
        w2 = (d00 * d21 - d01 * d20) / den
        P0 = V0[a] * (1 - w1 - w2) + V0[bb] * w1 + V0[cc] * w2
        sgn = 1 if (X - np.array(loc)) @ np.array(nrm) > 0 else -1
        res['off_surface_m'] = round(float(sgn * dist), 4)
        res['design'] = [round(float(v), 4) for v in P0]
    # each ray alone on the shell (what trace3d would give from that photo)
    for key, o, v, xy in rays:
        hit = bvh.ray_cast(Vector(o.tolist()), Vector(v.tolist()))
        res.setdefault('hits', {})[key] = None if hit[0] is None else [round(float(t), 3) for t in hit[0]]
    out[feat] = res
    print('TRI', feat, json.dumps(res))
json.dump(out, open(outp, 'w'), indent=1)
print('WROTE', outp)
