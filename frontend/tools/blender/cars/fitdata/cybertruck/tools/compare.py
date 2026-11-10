"""
compare.py (Blender): the cybertruck (Cycles, the check scene of cybertruck_scene) from every solved photo camera,
posed like the photo's truck, and a side-by-side photo | render per photo. (After fitdata/raijin/tools/compare.py.)

  PYFIT=<dir with PIL> blender.sh -t 6 -b --factory-startup --python compare.py -- <fit.json> <outdir>
      [--cams shape.json] [--photos a,b] [--samples 32] [--maxw 1280] [--lit a,b] [--paint #b4b6b8]
--lit: photos whose render has the lamps lit (the light bar and tail lamps glowing, as those photos show them)
"""
import json, math, os, sys

sys.dont_write_bytecode = True
REPO_CARS = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'))
sys.path.insert(0, REPO_CARS)
sys.path.insert(0, os.environ.get('PYFIT', ''))

import bpy
from mathutils import Matrix, Vector
from PIL import Image

import cybertruck
import cybertruck_kit as K
import cybertruck_scene as S

argv = sys.argv[sys.argv.index('--') + 1:]


def opt(k, d):
    return type(d)(argv[argv.index(k) + 1]) if k in argv else d


fit = json.load(open(argv[0]))
out = argv[1]
os.makedirs(out, exist_ok=True)
only = opt('--photos', '')
lit = opt('--lit', '').split(',')
MAXW = opt('--maxw', 1280)
samples = opt('--samples', 32)
camdata = json.load(open(opt('--cams', fit['cams'])))
names = [n for n in fit['photos'] if (not only or n in only.split(',')) and n in camdata['cams']]

K.clear_scene()
root, m, _ = cybertruck.build({'paint': opt('--paint', '#b4b6b8')})
body = bpy.data.objects['body']
S.scene()
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


def glow(on):
    for name, strength in (('headlight', 2.5), ('taillight', 38.0)):   # the tail lens texture is smoked (dark)
        for n in m[name].node_tree.nodes:
            if n.type == 'BSDF_PRINCIPLED':
                n.inputs['Emission Strength'].default_value = strength if on else 0.0


for n in names:
    c = camdata['cams'][n]
    W, H = c[7]
    k = min(MAXW / W, MAXW * 0.75 / H)
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
    glow(n in lit)
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
