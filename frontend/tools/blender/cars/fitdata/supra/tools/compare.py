"""
compare.py (Blender; the Supra): the car in light silver (Cycles, the check scene) from every solved photo camera, posed
like the photo's car, and a side-by-side image photo | render per photo.

  blender.sh -t 4 -b --factory-startup --python compare.py -- <fit.json> <outdir> [--photos a,b] [--samples 32]
      [--maxw 1280] [--paint (keep the model's own paint)] [--paintmap n07=#8c8e92,n05=#101112 (each photo's car's paint)]
"""
import json, math, os, sys

sys.dont_write_bytecode = True
REPO_CARS = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'))
sys.path.insert(0, REPO_CARS)
sys.path.insert(0, os.environ.get('PYFIT', ''))   # where OpenCV / Pillow for Blender's Python live

import bpy
from mathutils import Matrix, Vector
from PIL import Image

import supra_kit as K
import supra_parts as P
import supra_scene as S

argv = sys.argv[sys.argv.index('--') + 1:]
fit = json.load(open(argv[0]))
out = argv[1]
os.makedirs(out, exist_ok=True)
only = argv[argv.index('--photos') + 1].split(',') if '--photos' in argv else None
MAXW = int(argv[argv.index('--maxw') + 1]) if '--maxw' in argv else 1280
samples = int(argv[argv.index('--samples') + 1]) if '--samples' in argv else 32
camdata = json.load(open(fit['cams']))
names = [n for n in fit['photos'] if only is None or n in only]

K.clear_scene()
mats = P.materials()
root = K.empty('supra')
P.build_all(root, mats)                     # the fitted field in fitdata/supra/ffd.json
body = bpy.data.objects['body']
S.scene()
S.see_through(mats['glass'], 0.88)
if '--paint' not in argv:                   # light silver, as supra.py --silver-views
    mats['paint'].node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = K.srgb('#b8babd')
PAINTMAP = dict(kv.split('=') for kv in argv[argv.index('--paintmap') + 1].split(',')) if '--paintmap' in argv else {}
paint_bsdf = mats['paint'].node_tree.nodes['Principled BSDF']
paint0 = tuple(paint_bsdf.inputs['Base Color'].default_value)
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


for n in names:
    c = camdata['cams'][n]
    W, H = c[7]
    k = min(MAXW / W, MAXW * 0.5625 / H)
    w, h = int(round(W * k)), int(round(H * k))
    d, r, u = basis(*c[3:6])
    cam.data.type = 'PERSP'
    cam.data.sensor_fit = 'HORIZONTAL'
    cam.data.sensor_width = 36
    cam.data.lens = c[6] * 36 / W
    cam.matrix_world = Matrix.Translation(Bv(c[:3])) @ Matrix((Bv(r), Bv(u), -Bv(d))).transposed().to_4x4()
    p = camdata.get('pose', {}).get(n, {})
    dy, th = p.get('dy', 0.0), math.radians(p.get('pitch_deg', 0.0))
    body.matrix_basis = Matrix.Translation(Bv((0, dy, 0))) @ Matrix.Rotation(-th, 4, 'X') @ body_m0
    S.light_from(c[:3], (0, 0.5, 0))
    paint_bsdf.inputs['Base Color'].default_value = K.srgb(PAINTMAP[n]) if n in PAINTMAP else paint0
    sc.cycles.samples = samples
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = False
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
