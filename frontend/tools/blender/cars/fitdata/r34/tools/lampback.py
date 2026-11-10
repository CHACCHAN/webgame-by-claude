"""lampback.py (Blender): the traced lamp outlines (lamps.json) carried back onto the body: a ray from each photo's
solved camera through every outline point hits the fitted, posed model; the hit is taken back to the body's rest
frame and through the inverse of the FFD field, giving the outline in the frame the r34 scripts design in (game
frame, before the FFD). Prints and writes {photo: {lamp: [[x, y, z] | null]}}.

  blender.sh -t 8 -b --factory-startup --python lampback.py -- <cams.json (with pose)> <lattice.json|none> <lamps.json> <out.json>
      [--roll r29=0.02,0.03] [--cut]   (camera roll overrides to try, rad: one result set per value, keyed 'r29@0.02')
"""
import json, math, os, sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, '..', '..', '..')))
import bpy
import numpy as np
from mathutils import Matrix, Vector

argv = sys.argv[sys.argv.index('--') + 1:]
camdata = json.load(open(argv[0]))
cams, poses = camdata['cams'], camdata.get('pose', {})
import r34
import r34_body
import r34_ffd
import r34_kit as K
K.clear_scene()
r34_body.CUT_FRONT = '--cut' in argv          # rays meet the uncut nose (the surface the lamps are laid on)
L = None if argv[1] == 'none' else r34_ffd.Lattice.load(argv[1])
root, mats, _ = r34.build({'ffd': L if L is not None else False})
body = bpy.data.objects['body']
lamps = json.load(open(argv[2]))['photos']
rolls = {}
if '--roll' in argv:
    for spec in argv[argv.index('--roll') + 1].split(';'):
        k, v = spec.split('=')
        rolls[k] = [float(t) for t in v.split(',')]


def B(x, y, z):
    return Vector((x, -z, y))


def basis(yaw, pitch, roll):
    d = Vector((math.sin(yaw) * math.cos(pitch), math.sin(pitch), math.cos(yaw) * math.cos(pitch)))
    r = d.cross(Vector((0, 1, 0))).normalized()
    u = r.cross(d)
    c, s = math.cos(roll), math.sin(roll)
    return d, c * r + s * u, -s * r + c * u


wheels = {o.name for o in bpy.data.objects if o.name.startswith(('wheel_', 'spin_'))}
for o in list(bpy.data.objects):
    if o.parent is not None and o.parent.name in wheels:
        wheels.add(o.name)
body_m0 = body.matrix_basis.copy()
res = {}
jobs = []
for ph in lamps:
    if ph in cams:
        jobs += [(ph, ph, None)] + [(f'{ph}@{r}', ph, r) for r in rolls.get(ph, [])]
for key, ph, roll in jobs:
    ls = lamps[ph]
    c = list(cams[ph])
    if roll is not None:
        c[5] = roll
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
        for px, py in dd['poly']:
            ray = d * c[6] + r * (px - W / 2) - u * (py - H / 2)
            org = eye
            hit = None
            for _ in range(4):
                ok, loc, nrm, idx, ob, mw = bpy.context.scene.ray_cast(dg, org, B(*ray).normalized())
                if not ok:
                    break
                if ob.name not in ('shell', 'rear_bumper'):
                    org = loc + B(*ray).normalized() * 1e-3
                    continue
                hit = loc
                break
            if hit is None:
                pts.append(None)
                continue
            q = back @ hit
            g = np.array([[q.x, q.z, -q.y]])
            x = g.copy()
            if L is not None:
                for _ in range(30):
                    x = g - L.displace(x)
            pts.append([round(float(v), 4) for v in x[0]])
        res.setdefault(key, {})[lamp] = pts
        ok = [q for q in pts if q is not None]
        A = np.array(ok) if ok else np.zeros((1, 3))
        print(f'{key} {lamp}: {len(ok)}/{len(pts)} hits  x {A[:, 0].min():+.3f}..{A[:, 0].max():+.3f}  y {A[:, 1].min():.3f}..{A[:, 1].max():.3f}  z {A[:, 2].min():+.3f}..{A[:, 2].max():+.3f}')
json.dump(res, open(argv[3], 'w'))
