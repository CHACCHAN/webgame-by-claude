"""
compare.py (Blender): the r34 in light silver (Cycles, the check scene of r34_scene) from every solved photo camera, posed
like the photo's car, and a side-by-side photo | render per photo; optionally the standard views too.
(After fitdata/hayate/tools/compare.py.)
--lamps lamps.json: instead, only the region round the photo's traced lamps is rendered (Cycles border, full photo
resolution, the paint of that photo's car from --paintmap), saved as <name>_lamps.png for lampfit.py's close-ups.

  PYFIT=<dir with PIL> blender.sh -t 4 -b --factory-startup --python compare.py -- <fit.json> <outdir>
      [--cams cams.json] [--photos a,b] [--samples 32] [--maxw 1280] [--views front34,rear34,side,front,rear]
      [--paint #c9ccd1] [--ffd lattice.json] [--lamps lamps.json --paintmap r29=#1d3c9c,r38=#9a9a90]
"""
import json, math, os, sys

sys.dont_write_bytecode = True
REPO_CARS = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'))
sys.path.insert(0, REPO_CARS)
sys.path.insert(0, os.environ.get('PYFIT', ''))

import bpy
from mathutils import Matrix, Vector
from PIL import Image

import r34
import r34_kit as K
import r34_scene as S

argv = sys.argv[sys.argv.index('--') + 1:]


def opt(k, d):
    return type(d)(argv[argv.index(k) + 1]) if k in argv else d


fit = json.load(open(argv[0]))
out = argv[1]
os.makedirs(out, exist_ok=True)
only = opt('--photos', '')
MAXW = opt('--maxw', 1280)
samples = opt('--samples', 32)
camdata = json.load(open(opt('--cams', fit['cams'])))
names = [n for n in fit['photos'] if (not only or n in only.split(',')) and n in camdata['cams']]

K.clear_scene()
o = {'paint': opt('--paint', '#c9ccd1')}
if '--ffd' in argv:
    import r34_ffd as F
    o['ffd'] = F.Lattice.load(opt('--ffd', ''))
root, m, _ = r34.build(o)
body = bpy.data.objects['body']
S.setup()
sc = bpy.context.scene
cam = sc.camera
body_m0 = body.matrix_basis.copy()


def Bv(v):
    return Vector((v[0], -v[2], v[1]))


def basis(yaw, pitch, roll):
    d = Vector((math.sin(yaw) * math.cos(pitch), math.sin(pitch), math.cos(yaw) * math.cos(pitch)))
    r = d.cross(Vector((0, 1, 0))).normalized()
    u = r.cross(d)
    c, s = math.cos(roll), math.sin(roll)
    return d, c * r + s * u, -s * r + c * u


LAMPS = json.load(open(opt('--lamps', '')))['photos'] if '--lamps' in argv else None
PAINTS = dict(kv.split('=') for kv in opt('--paintmap', '').split(',') if '=' in kv)
bsdf = m['paint'].node_tree.nodes['Principled BSDF']
paint0 = tuple(bsdf.inputs['Base Color'].default_value)
for n in names:
    if LAMPS is not None and n not in LAMPS:
        continue
    c = camdata['cams'][n]
    W, H = c[7]
    k = min(MAXW / W, MAXW * 0.75 / H) if LAMPS is None else 1.0
    w, h = int(round(W * k)), int(round(H * k))
    d, r, u = basis(*c[3:6])
    cam.data.type = 'PERSP'
    cam.data.sensor_fit = 'HORIZONTAL'
    cam.data.sensor_width = 36
    cam.data.shift_x = cam.data.shift_y = 0.0
    cam.data.lens = c[6] * 36 / W
    cam.matrix_world = Matrix.Translation(Bv(c[:3])) @ Matrix((Bv(r), Bv(u), -Bv(d))).transposed().to_4x4()
    p = camdata.get('pose', {}).get(n, {})
    dy, th = p.get('dy', 0.0), math.radians(p.get('pitch_deg', 0.0))
    body.matrix_basis = Matrix.Translation(Bv((0, dy, 0))) @ Matrix.Rotation(-th, 4, 'X') @ body_m0
    S.light_from(c[:3], (0, 0.5, 0), 40.0)
    sc.cycles.samples = samples
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = False
    if LAMPS is not None:
        import numpy as _np
        P = _np.concatenate([_np.array(v['poly'], float) for v in LAMPS[n].values()])
        x0, y0 = P.min(0) - 60
        x1, y1 = P.max(0) + 60
        sc.render.use_border, sc.render.use_crop_to_border = True, False
        sc.render.border_min_x, sc.render.border_max_x = max(0.0, x0 / w), min(1.0, x1 / w)
        sc.render.border_min_y, sc.render.border_max_y = max(0.0, 1 - y1 / h), min(1.0, 1 - y0 / h)
        bsdf.inputs['Base Color'].default_value = K.srgb(PAINTS[n]) if n in PAINTS else paint0
        sc.render.filepath = os.path.join(out, f'{n}_lamps.png')
        bpy.ops.render.render(write_still=True)
        print('lamps', n, flush=True)
        continue
    sc.render.use_border = False
    sc.render.filepath = os.path.join(out, f'{n}_render.png')
    bpy.ops.render.render(write_still=True)
    ph = Image.open(fit['photos'][n]['photo']).convert('RGB').resize((w, h), Image.LANCZOS)
    rd = Image.open(sc.render.filepath).convert('RGB')
    cmp_ = Image.new('RGB', (2 * w + 8, h), 'white')
    cmp_.paste(ph, (0, 0))
    cmp_.paste(rd, (w + 8, 0))
    cmp_.save(os.path.join(out, f'{n}_compare.png'))
    print('compare', n, w, h, flush=True)
body.matrix_basis = body_m0
for v in filter(None, opt('--views', '').split(',')):
    S.render(v, os.path.join(out, f'{v}.png'), size=(1280, 720), samples=samples)
    print('view', v, flush=True)
