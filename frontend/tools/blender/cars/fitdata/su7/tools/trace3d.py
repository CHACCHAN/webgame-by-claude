"""
trace3d.py (Blender): lines traced on the photos -> points on the body in the design frame.

  blender.sh -t 6 -b --factory-startup --python trace3d.py -- <traces.json> <cams.json> <ffd.json> <out.json>

traces.json: {"_note": ..., "<photo>": {"<key>": [[x, y], ...]}} in the photos' pixels (1280-wide thumbnails). Each
point casts a ray from the photo's solved camera onto the fitted (FFD), posed shell; the hit triangle and its
barycentric coordinates carry the point back onto the undeformed shell (the frame the parts are laid out in, before
the field moves them with the body). Misses (off the car) are null. Out: {"<photo>": {"<key>": [[x, y, z] | null]}}
and, per key, the same points mirrored to the left (+x) side where the key ends in _R ("<key>_toL").
"""
import json, math, os, sys

sys.dont_write_bytecode = True
REPO_CARS = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'))
sys.path.insert(0, REPO_CARS)

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

import su7_kit as K
import su7_body as BD
import su7_ffd as FF

argv = sys.argv[sys.argv.index('--') + 1:]
traces = json.load(open(argv[0]))
camdata = json.load(open(argv[1]))
L = FF.Lattice.load(argv[2])
outp = argv[3]

import su7_parts as PT
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
VD = V0 + (L.displace(V0) if L is not None else 0.0)
TL = [tuple(t) for t in T.tolist()]


def basis(yaw, pitch, roll):
    d = np.array([math.sin(yaw) * math.cos(pitch), math.sin(pitch), math.cos(yaw) * math.cos(pitch)])
    r = np.cross(d, [0, 1, 0])
    r /= np.linalg.norm(r)
    u = np.cross(r, d)
    c, s = math.cos(roll), math.sin(roll)
    return d, c * r + s * u, -s * r + c * u


def posed(G, dy, th):
    c, s = math.cos(th), math.sin(th)
    return np.stack([G[:, 0], G[:, 1] * c + G[:, 2] * s + dy, G[:, 2] * c - G[:, 1] * s], 1)


out = {}
for n, keys in traces.items():
    if n.startswith('_') or n not in camdata['cams']:
        continue
    c = camdata['cams'][n]
    p = camdata.get('pose', {}).get(n, {})
    VP = posed(VD, p.get('dy', 0.0), math.radians(p.get('pitch_deg', 0.0)))
    bvh = BVHTree.FromPolygons([Vector(v) for v in VP.tolist()], TL, all_triangles=True)
    d, r, u = basis(*c[3:6])
    f = c[6]
    W, H = c[7]
    C = Vector(c[:3])
    res = {}
    for key, pts in keys.items():
        row = []
        for q in pts:
            x, y = q[0], q[1]
            ray = d + ((x - W / 2) / f) * r - ((y - H / 2) / f) * u
            loc, nrm, ti, dist = bvh.ray_cast(C, Vector(ray / np.linalg.norm(ray)))
            if loc is None:
                row.append(None)
                continue
            a, b, cc = T[ti]
            A, B_, Cc = VP[a], VP[b], VP[cc]
            v0, v1, v2 = B_ - A, Cc - A, np.array(loc) - A
            d00, d01, d11 = v0 @ v0, v0 @ v1, v1 @ v1
            d20, d21 = v2 @ v0, v2 @ v1
            den = d00 * d11 - d01 * d01
            bb = (d11 * d20 - d01 * d21) / den
            cb = (d00 * d21 - d01 * d20) / den
            ab = 1 - bb - cb
            P0 = V0[a] * ab + V0[b] * bb + V0[cc] * cb
            row.append([round(float(v), 4) for v in P0])
        res[key] = row
        if key.endswith('_R'):
            res[key + '_toL'] = [None if q is None else [-q[0], q[1], q[2]] for q in row]
    out[n] = res
json.dump(out, open(outp, 'w'), indent=1)
print('WROTE', outp, {n: len(v) for n, v in out.items()})
