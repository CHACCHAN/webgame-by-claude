"""probe.py (Blender): sections of the built model (final shape, game frame) by ray casts.
  blender.sh -t 4 -b --factory-startup --python probe.py -- <spec.json>
spec: {"down": {"x": [..], "z": [..]}, "fwd": {"x": [..], "y": [..]}, "side": {"y": [..], "z": [..]}, "back": {...}}
down: rays from above (y = 3) at (x, z); fwd: rays along +z from behind (z = -4) at (x, y); back: along -z from the
front; side: rays along -x from x = 3 at (y, z). Prints the first hit and its material."""
import json, os, sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..')))
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

import hayate_kit as K
import hayate_parts as P

spec = json.load(open(sys.argv[sys.argv.index('--') + 1]))
K.clear_scene()
mats, _ = P.materials()
root = K.empty('hayate')
body = K.empty('body', root)
parts = P.build_all(body, root, mats, {}, ffd=spec.get('ffd', True))
P.fold_popups(parts, closed=True)
bpy.context.view_layer.update()
verts, polys, pmat = [], [], []
for o in body.children_recursive:
    if o.type != 'MESH':
        continue
    M = o.matrix_world
    b = len(verts)
    verts += [tuple(M @ v.co) for v in o.data.vertices]
    for p in o.data.polygons:
        polys.append([b + i for i in p.vertices])
        pmat.append(o.material_slots[p.material_index].material.name)
bvh = BVHTree.FromPolygons(verts, polys)


def cast(o, d):
    h = bvh.ray_cast(Vector(K.B(*o)), Vector(K.B(*d)))
    if h[0] is None:
        return None
    g = K.G(h[0])
    return g, pmat[h[2]]


for kind, (a, b, mk, dirn) in {'down': ('x', 'z', lambda u, v: (u, 3.0, v), (0, -1, 0)),
                               'fwd': ('x', 'y', lambda u, v: (u, v, -4.0), (0, 0, 1)),
                               'back': ('x', 'y', lambda u, v: (u, v, 4.0), (0, 0, -1)),
                               'side': ('y', 'z', lambda u, v: (3.0, u, v), (-1, 0, 0))}.items():
    if kind not in spec:
        continue
    s = spec[kind]
    for u in s[a]:
        line = []
        for v in s[b]:
            h = cast(mk(u, v), dirn)
            line.append('   -   ' if h is None else f'{h[0][{"down": 1, "fwd": 2, "back": 2, "side": 0}[kind]]:+.3f}{h[1][:2]}')
        print(f'{kind} {a}={u:+.3f}: ' + ' '.join(line))
    print(f'{kind} {b}: ' + ' '.join(f'{v:+.3f}  ' for v in s[b]))
