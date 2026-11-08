"""dump_mesh.py (Blender) -- <out.npz> [--noffd]: build shiden, fold the pods closed, dump world-space triangles in
game coordinates: body (deformable) and wheels (rigid, per wheel), with material names per triangle."""
import sys, os
sys.dont_write_bytecode = True
REPO = '/home/dev/Desktop/service/internal/webgame-by-claude/frontend/tools/blender/cars'
sys.path.insert(0, REPO)
argv = sys.argv[sys.argv.index('--') + 1:]
out = argv[0]
if '--noffd' in argv:
    os.environ['SHIDEN_NOFFD'] = '1'
sys.argv = [sys.argv[0]]
import bpy, numpy as np
import shiden as CAR
root, mats, counts = CAR.build_car(False)
for n in ('popup_l', 'popup_r'):
    o = bpy.data.objects.get(n)
    o.rotation_euler[0] = o['popupClosed']
bpy.context.view_layer.update()
def group(o):
    p = o
    while p is not None:
        if p.name.startswith('wheel_'):
            return p.name[6:]
        if p.name == 'body':
            return 'body'
        p = p.parent
    return None
V = {}; T = {}; M = {}; matnames = []
for o in root.children_recursive:
    if o.type != 'MESH':
        continue
    g = group(o)
    me = o.data
    mw = np.array(o.matrix_world)
    co = np.array([v.co for v in me.vertices]).reshape(-1, 3)
    co = co @ mw[:3, :3].T + mw[:3, 3]
    game = np.c_[co[:, 0], co[:, 2], -co[:, 1]]
    me.calc_loop_triangles()
    tri = np.array([t.vertices for t in me.loop_triangles], int).reshape(-1, 3)
    mat = []
    for t in me.loop_triangles:
        m = me.materials[t.material_index].name if me.materials else 'none'
        if m not in matnames:
            matnames.append(m)
        mat.append(matnames.index(m))
    base = len(V.get(g, []))
    V.setdefault(g, []).extend(game.tolist())
    T.setdefault(g, []).extend((tri + base).tolist())
    M.setdefault(g, []).extend(mat)
arrs = {'matnames': np.array(matnames)}
for g in V:
    arrs[f'{g}_v'] = np.array(V[g], np.float64); arrs[f'{g}_t'] = np.array(T[g], np.int32); arrs[f'{g}_m'] = np.array(M[g], np.int16)
    print('GROUP', g, len(V[g]), len(T[g]))
np.savez(out, **arrs)
