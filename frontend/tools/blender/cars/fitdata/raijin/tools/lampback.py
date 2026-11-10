"""
lampback.py (Blender): the traced lamp outlines (lamps.json) carried back onto the car: a ray from each photo's solved
camera through every outline point hits the built, posed model (the body's paint / lamp surfaces); the hit goes back to
the body's rest frame and through the inverse of the fitted FFD field, giving the outline in the frame the car's
scripts design in (game frame, before the FFD). Also the model's own lamp lenses' outlines as seen from the same
camera are NOT needed here (lampfit does that). Writes {photo: {lamp: [[x, y, z] | null]}}.

  blender.sh -t 4 -b --factory-startup --python lampback.py -- <car> <cams.json> <lamps.json> <out.json>
      [--skip interior,glass] [--open]
"""
import json, math, os, sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
import numpy as np
from mathutils import Matrix, Vector

argv = sys.argv[sys.argv.index('--') + 1:]
car, camfile, lj, outp = argv[:4]
import carload
C = carload.load(car)
C['fold']('--open' not in argv)
root = C['root']
camdata = json.load(open(camfile))
cams = {k: (v['cam'] if isinstance(v, dict) else v) for k, v in camdata['cams'].items()}
poses = camdata.get('pose', {})
lamps = json.load(open(lj))['photos']
skip_mats = set((argv[argv.index('--skip') + 1] if '--skip' in argv else 'glass,interior').split(','))
body = bpy.data.objects['body']
bpy.context.view_layer.update()


def B(x, y, z):
    return Vector((x, -z, y))


def basis(yaw, pitch, roll):
    d = Vector((math.sin(yaw) * math.cos(pitch), math.sin(pitch), math.cos(yaw) * math.cos(pitch)))
    r = d.cross(Vector((0, 1, 0))).normalized()
    u = r.cross(d)
    c, s = math.cos(roll), math.sin(roll)
    return d, c * r + s * u, -s * r + c * u


wheels = set()
for o in bpy.data.objects:
    if o.name.startswith(('wheel_', 'spin_')):
        wheels.add(o.name)
        wheels.update(c.name for c in o.children_recursive)
body_m0 = body.matrix_basis.copy()
res = {}
for ph, ls in lamps.items():
    if ph not in cams:
        continue
    c = cams[ph]
    W, H = c[7]
    d, r, u = basis(*c[3:6])
    p = poses.get(ph, {})
    dy, th = p.get('dy', 0.0), math.radians(p.get('pitch_deg', 0.0))
    body.matrix_basis = Matrix.Translation(B(0, dy, 0)) @ Matrix.Rotation(-th, 4, 'X') @ body_m0
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    back = body_m0 @ body.matrix_world.inverted()
    eye = B(*c[:3])
    for lamp, dd in ls.items():
        pts = []
        hitmats = []
        for px, py in dd['poly']:
            ray = (d * c[6] + r * (px - W / 2) - u * (py - H / 2)).normalized()
            org = eye
            hit = None
            for _ in range(8):
                ok, loc, nrm, idx, ob, mw = bpy.context.scene.ray_cast(dg, org, B(*ray))
                if not ok:
                    break
                mname = ''
                if ob.type == 'MESH' and ob.data.polygons and idx < len(ob.data.polygons):
                    mi = ob.data.polygons[idx].material_index
                    if mi < len(ob.data.materials) and ob.data.materials[mi] is not None:
                        mname = ob.data.materials[mi].name
                if ob.name in wheels or mname in skip_mats or ob.name.startswith('ground'):
                    org = loc + B(*ray) * 1e-3
                    continue
                hit = loc
                hitmats.append(mname)
                break
            if hit is None:
                pts.append(None)
                continue
            q = back @ hit
            pts.append([q.x, q.z, -q.y])
        ok = [i for i, q in enumerate(pts) if q is not None]
        if ok:
            G = np.array([pts[i] for i in ok])
            X = C['inv_ffd'](G)
            for i, x in zip(ok, X):
                pts[i] = [round(float(v), 4) for v in x]
        res.setdefault(ph, {})[lamp] = pts
        A = np.array([q for q in pts if q is not None]) if ok else np.zeros((1, 3))
        from collections import Counter
        print(f'{ph} {lamp}: {len(ok)}/{len(pts)} hits  x {A[:, 0].min():+.3f}..{A[:, 0].max():+.3f}  y {A[:, 1].min():.3f}..{A[:, 1].max():.3f}  '
              f'z {A[:, 2].min():+.3f}..{A[:, 2].max():+.3f}  mats {dict(Counter(hitmats))}', flush=True)
body.matrix_basis = body_m0
json.dump(res, open(outp, 'w'))
