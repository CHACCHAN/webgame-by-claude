"""
drape.py (Blender): photo pixels → 3D points on the current model (ray cast from the photo's solved camera, the photo's
body pose undone), and 3D points → pixels in other photos (marked on them, to check a measurement in a second view).

  blender.sh -t 4 -b --factory-startup --python drape.py -- <fit.json> <spec.json> <outdir>

spec: {"pick": {photo: {label: [px, py]}}, "points": {label: [x, y, z]}, "show": [photo, ...], "plane": {label: "z=-2.1"}}
Picked points hit the model (or the given plane, body frame); "show" draws every point (picked and given) on those
photos: <outdir>/<photo>_pts.png. Prints label, photo, the 3D point (game frame, final shape), the material hit, and
the point before the fitted field and the nose drop (base = what hayate_body's tables describe).
"""
import json, math, os, sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
REPO_CARS = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'))
sys.path.insert(0, REPO_CARS)
sys.path.insert(0, os.path.join(HERE, '..', '..', '..', 'pyfit'))

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from PIL import Image, ImageDraw

import hayate_kit as K
import hayate_parts as P
import hayate_body as BD
import hayate_ffd as FF

argv = sys.argv[sys.argv.index('--') + 1:]
fit = json.load(open(argv[0]))
spec = json.load(open(argv[1]))
out = argv[2]
os.makedirs(out, exist_ok=True)
camdata = json.load(open(fit['cams']))
cams, poses = camdata['cams'], camdata.get('pose', {})

K.clear_scene()
mats, _ = P.materials()
root = K.empty('hayate')
body = K.empty('body', root)
parts = P.build_all(body, root, mats, {})
P.fold_popups(parts, closed=True)
bpy.context.view_layer.update()
verts, polys, pmat = [], [], []
for o in body.children_recursive:
    if o.type != 'MESH':
        continue
    M = o.matrix_world
    base = len(verts)
    verts += [tuple(M @ v.co) for v in o.data.vertices]
    for p in o.data.polygons:
        polys.append([base + i for i in p.vertices])
        pmat.append(o.material_slots[p.material_index].material.name if o.material_slots else '?')
bvh = BVHTree.FromPolygons(verts, polys)
L = FF.Lattice.load()


def basis(yaw, pitch, roll):
    d = np.array([math.sin(yaw) * math.cos(pitch), math.sin(pitch), math.cos(yaw) * math.cos(pitch)])
    r = np.cross(d, [0, 1, 0]); r /= np.linalg.norm(r)
    u = np.cross(r, d)
    c, s = math.cos(roll), math.sin(roll)
    return d, c * r + s * u, -s * r + c * u


def pose_R(n):
    p = poses.get(n, {})
    th = math.radians(p.get('pitch_deg', 0.0))
    ct, st = math.cos(th), math.sin(th)
    return np.array([[1, 0, 0], [0, ct, st], [0, -st, ct]]), np.array([0, p.get('dy', 0.0), 0])


def ray(n, px, py):
    c = cams[n]
    W, H = c[7]
    d, r, u = basis(*c[3:6])
    v = d + (px - W / 2) / c[6] * r - (py - H / 2) / c[6] * u
    R, t = pose_R(n)
    C = R.T @ (np.array(c[:3]) - t)
    return C, R.T @ (v / np.linalg.norm(v))


def project(n, P3):
    c = cams[n]
    W, H = c[7]
    d, r, u = basis(*c[3:6])
    R, t = pose_R(n)
    g = R @ np.array(P3) + t - np.array(c[:3])
    z = g @ d
    return W / 2 + c[6] * (g @ r) / z, H / 2 - c[6] * (g @ u) / z


def base_of(T):
    """undo the fitted field and the nose drop (two fixed-point steps)"""
    T = np.array(T, float)[None]
    B = T.copy()
    for _ in range(3):
        D = B + BD.front_drop(B)
        F = L.displace(D) if L is not None else 0
        B = T - BD.front_drop(B) - F
    return B[0]


pts = dict(spec.get('points', {}))
planes = spec.get('plane', {})
res = {}
for n, picks in spec.get('pick', {}).items():
    for lab, (px, py) in picks.items():
        C, v = ray(n, px, py)
        if lab in planes:
            ax, val = planes[lab].split('=')
            k = 'xyz'.index(ax)
            tt = (float(val) - C[k]) / v[k]
            P3, mat = C + tt * v, 'plane'
        else:
            h = bvh.ray_cast(Vector(K.B(*C)), Vector(K.B(*v)))
            if h[0] is None:
                print(f'{lab:12s} {n}: miss')
                continue
            P3, mat = np.array(K.G(h[0])), pmat[h[2]]
        b = base_of(P3)
        res.setdefault(lab, {})[n] = [round(float(t), 4) for t in P3]
        pts.setdefault(lab, P3.tolist())
        print(f'{lab:12s} {n:4s} final {P3[0]:+.3f} {P3[1]:+.3f} {P3[2]:+.3f}  base {b[0]:+.3f} {b[1]:+.3f} {b[2]:+.3f}  {mat}')
json.dump(res, open(os.path.join(out, 'drape.json'), 'w'), indent=1)
for n in spec.get('show', []):
    ph = fit['photos'][n]['photo']
    im = Image.open(ph).convert('RGB')
    d = ImageDraw.Draw(im)
    for lab, P3 in pts.items():
        x, y = project(n, P3)
        d.line([(x - 8, y), (x + 8, y)], fill=(255, 0, 255), width=2)
        d.line([(x, y - 8), (x, y + 8)], fill=(255, 0, 255), width=2)
        d.text((x + 6, y + 4), lab, fill=(255, 255, 0))
        print(f'show {n} {lab:12s} {x:7.1f} {y:7.1f}')
    im.save(os.path.join(out, f'{n}_pts.png'))
