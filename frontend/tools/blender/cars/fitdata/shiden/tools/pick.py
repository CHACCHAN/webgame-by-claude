"""pick.py (Blender) -- <cams.json> <photo> u,v [u,v ...] : what the build shows at those pixels (object, material, game xyz)"""
import sys, json, math
sys.dont_write_bytecode = True
sys.path.insert(0, '/home/dev/Desktop/service/internal/webgame-by-claude/frontend/tools/blender/cars')
argv = sys.argv[sys.argv.index('--') + 1:]
cams = json.load(open(argv[0]))['cams']; c = cams[argv[1]]
import bpy
from mathutils import Vector
import shiden as CAR, shiden_parts as PARTS, shiden_ffd as FFD
import numpy as np
root, mats, counts = CAR.build_car(False)
PARTS.fold_pods(root)
bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get()
def B(x, y, z): return Vector((x, -z, y))
yaw, pitch, roll = c[3:6]
d = Vector((math.sin(yaw) * math.cos(pitch), math.sin(pitch), math.cos(yaw) * math.cos(pitch)))
r = d.cross(Vector((0, 1, 0))).normalized(); u = r.cross(d)
cr, sr = math.cos(roll), math.sin(roll); r, u = cr * r + sr * u, -sr * r + cr * u
W, H = c[7]; f = c[6]; C = Vector(c[:3])
for a in argv[2:]:
    px, py = map(float, a.split(','))
    D = (d * f + r * (px - W / 2) - u * (py - H / 2)).normalized()
    ok, loc, nrm, idx, ob, _ = bpy.context.scene.ray_cast(dg, B(*C), B(*D))
    if not ok:
        print('PICK', a, 'miss'); continue
    me = ob.data; poly = me.polygons[idx]
    mat = me.materials[poly.material_index].name if me.materials else '-'
    P = np.array((loc.x, loc.z, -loc.y)); Q = P.copy()
    for _ in range(6):
        Q = Q + (P - FFD.deform_game(Q[None])[0])
    print('PICK', a, ob.name, mat, 'game', [round(v, 3) for v in P], 'base', [round(v, 3) for v in Q], 'n', [round(nrm.x, 2), round(nrm.z, 2), round(-nrm.y, 2)])
