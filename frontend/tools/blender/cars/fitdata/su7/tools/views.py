"""
views.py (Blender): quick Workbench look at the SU7 from the repo scripts: orthographic side / front / rear / top and two
three-quarter views, light grey studio shading with cavity; and, with --cams, the same shading from each solved photo
camera blended over the photo (<name>_blend.png: photo | blend | render, by blend.py).

  PY=<python with PIL> blender.sh -t 6 -b --factory-startup --python views.py -- <outdir> [--noffd | --ffd f.json]
      [--cams cams.json --photos dir [--only a,b]] [--size 900]
"""
import json, math, os, subprocess, sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
REPO_CARS = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, REPO_CARS)
PY = os.environ.get('PY', 'python3')

import bpy
from mathutils import Matrix, Vector

argv = sys.argv[sys.argv.index('--') + 1:]
out = argv[0]
os.makedirs(out, exist_ok=True)


def opt(k, d=None):
    return argv[argv.index(k) + 1] if k in argv else d


import su7_kit as K
import su7_parts as PT
K.clear_scene()
mats = PT.materials('#9a9ea4')
root = K.empty('su7')
ffd = False if '--noffd' in argv else True
if opt('--ffd'):
    import su7_ffd as FF
    ffd = FF.Lattice.load(opt('--ffd'))
PT.build_all(root, mats, ffd=ffd, bare='--bare' in argv)
body = bpy.data.objects['body']

sc = bpy.context.scene
sc.render.engine = 'BLENDER_WORKBENCH'
sc.render.film_transparent = True
sc.view_settings.view_transform = 'Standard'
sc.render.image_settings.file_format = 'PNG'
sc.render.image_settings.color_mode = 'RGBA'
sh = sc.display.shading
sh.light, sh.color_type = 'STUDIO', 'MATERIAL'
sh.show_cavity, sh.cavity_type = True, 'BOTH'
sh.show_specular_highlight = True
sc.display.render_aa = '8'
for m in bpy.data.materials:
    nm = m.name
    col = {'paint': (0.62, 0.64, 0.67), 'glass': (0.12, 0.14, 0.17), 'tire': (0.08, 0.08, 0.08), 'under': (0.1, 0.1, 0.1),
           'headlight': (0.35, 0.55, 0.85), 'taillight': (0.6, 0.08, 0.08), 'carbon': (0.15, 0.15, 0.16),
           'trim': (0.1, 0.1, 0.11), 'accent': (0.75, 0.8, 0.1), 'rim': (0.45, 0.46, 0.48)}.get(nm, (0.35, 0.35, 0.37))
    m.diffuse_color = (*col, 1)
cam = bpy.data.objects.new('vcam', bpy.data.cameras.new('vcam'))
sc.collection.objects.link(cam)
sc.camera = cam
cam.data.clip_start = 0.05
cam.data.clip_end = 1000


def look(eye, target, up=(0, 1, 0)):
    e, t = K.B(*eye), K.B(*target)
    d = (t - e).normalized()
    upb = (K.B(*up) - K.B(0, 0, 0)).normalized()
    r = d.cross(upb).normalized()
    u = r.cross(d)
    cam.matrix_world = Matrix.Translation(e) @ Matrix((r, u, -d)).transposed().to_4x4()


S = int(opt('--size', '900'))
ORTHO = {'side': ((12, 0.65, 0), (0, 0.65, 0), 5.4), 'front': ((0, 0.65, 12), (0, 0.65, 0), 2.4),
         'rear': ((0, 0.65, -12), (0, 0.65, 0), 2.4), 'top': ((0, 12, 0.0001), (0, 0, 0), 5.4)}
for name, (eye, tgt, scale) in ORTHO.items():
    cam.data.type = 'ORTHO'
    cam.data.ortho_scale = scale
    look(eye, tgt, up=(0, 0, 1) if name == 'top' else (0, 1, 0))
    sc.render.resolution_x = S
    sc.render.resolution_y = int(S * (0.5 if name in ('side', 'top') else 0.75))
    sc.render.filepath = os.path.join(out, f'o_{name}.png')
    bpy.ops.render.render(write_still=True)
cam.data.type = 'PERSP'
cam.data.sensor_fit = 'HORIZONTAL'
cam.data.sensor_width = 36
for name, eye, tgt, lens in (('f34', (4.4, 1.3, 5.2), (0, 0.55, 0.2), 40), ('r34', (-4.2, 1.5, -5.4), (0, 0.6, -0.3), 40)):
    cam.data.lens = lens
    look(eye, tgt)
    sc.render.resolution_x, sc.render.resolution_y = S, int(S * 0.6)
    sc.render.filepath = os.path.join(out, f'p_{name}.png')
    bpy.ops.render.render(write_still=True)

if opt('--cams'):
    cd = json.load(open(opt('--cams')))
    cams, poses = cd['cams'], cd.get('pose', {})
    only = opt('--only').split(',') if opt('--only') else list(cams)
    body_m0 = body.matrix_basis.copy()
    for n in only:
        c = cams[n]
        W, H = c[7]
        d = Vector((math.sin(c[3]) * math.cos(c[4]), math.sin(c[4]), math.cos(c[3]) * math.cos(c[4])))
        r = d.cross(Vector((0, 1, 0))).normalized()
        u = r.cross(d)
        cr, sr = math.cos(c[5]), math.sin(c[5])
        r, u = cr * r + sr * u, -sr * r + cr * u
        cam.matrix_world = Matrix.Translation(K.B(*c[:3])) @ Matrix((K.B(*r) - K.B(0, 0, 0), K.B(*u) - K.B(0, 0, 0),
                                                                     -(K.B(*d) - K.B(0, 0, 0)))).transposed().to_4x4()
        cam.data.lens = c[6] * 36 / W
        sc.render.resolution_x, sc.render.resolution_y = int(W), int(H)
        p = poses.get(n, {})
        body.matrix_basis = Matrix.Translation(K.B(0, p.get('dy', 0.0), 0)) @ Matrix.Rotation(-math.radians(p.get('pitch_deg', 0.0)), 4, 'X') @ body_m0
        sc.render.filepath = os.path.join(out, f'{n}_shade.png')
        bpy.ops.render.render(write_still=True)
        body.matrix_basis = body_m0
        subprocess.run([PY, os.path.join(HERE, 'blend.py'), os.path.join(opt('--photos'), f'{n}.jpg'),
                        os.path.join(out, f'{n}_shade.png'), os.path.join(out, f'{n}_blend.png')])
