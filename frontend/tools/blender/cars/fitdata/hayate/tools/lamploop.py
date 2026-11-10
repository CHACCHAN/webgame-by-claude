"""
lamploop.py (Blender): one of the own cars (hayate, shiden, s15, raijin) built from the repo scripts, posed like each
photo's car, rendered from each solved photo camera:
  <ph>_ids.png  material-id image (Workbench flat, palette.json) for lampfit.py
  <ph>_sil.png  silhouette (white on transparent) for the silhouette regression check
  <ph>_lamps.png  Cycles render in the photo car's paint (--paintmap), only round the traced lamps (--lamps) or whole
  <ph>_full.png   (--full) Cycles render of the whole frame
Pop-up cars: lamps folded (as in the photos) unless --open.

  blender.sh -t 4 -b --factory-startup --python lamploop.py -- <car> <cams.json> <outdir> [--photos a,b]
      [--lamps lamps.json] [--paintmap r02=#1d3c9c,...] [--samples 24] [--noids] [--nocycles] [--full] [--open]
      [--night] [--glb out.glb]
"""
import json, math, os, sys

sys.dont_write_bytecode = True
CARS = '/home/dev/Desktop/service/internal/webgame-by-claude/frontend/tools/blender/cars'
sys.path.insert(0, CARS)
import bpy
from mathutils import Matrix, Vector

argv = sys.argv[sys.argv.index('--') + 1:]
car, camfile, outdir = argv[:3]
os.makedirs(outdir, exist_ok=True)


def opt(k, d=None):
    return argv[argv.index(k) + 1] if k in argv else d


only = opt('--photos')
only = only.split(',') if only else None
samples = int(opt('--samples', '24'))
LAMPS = json.load(open(opt('--lamps')))['photos'] if '--lamps' in argv else None
PAINTS = dict(kv.split('=') for kv in opt('--paintmap', '').split(',') if '=' in kv)
NIGHT = '--night' in argv

camdata = json.load(open(camfile))
cams = {k: (v['cam'] if isinstance(v, dict) else v) for k, v in camdata['cams'].items()}
poses = camdata.get('pose', {})
names = [n for n in cams if only is None or n in only]


def srgb(h):
    h = h.lstrip('#')
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple((v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4) for v in c) + (1.0,)


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import carload
C = carload.load(car, night=NIGHT)
root, mats, scene, light, fold, export = C['root'], C['mats'], C['scene'], C['light'], C['fold'], C['export']
if '--glb' in argv:
    export(opt('--glb'))
fold('--open' not in argv)
bpy.context.view_layer.update()
body = bpy.data.objects['body']
body_m0 = body.matrix_basis.copy()
sc = bpy.context.scene


def B(x, y, z):
    return Vector((x, -z, y))


def basis(yaw, pitch, roll):
    d = Vector((math.sin(yaw) * math.cos(pitch), math.sin(pitch), math.cos(yaw) * math.cos(pitch)))
    r = d.cross(Vector((0, 1, 0))).normalized()
    u = r.cross(d)
    c, s = math.cos(roll), math.sin(roll)
    return d, c * r + s * u, -s * r + c * u


cam = bpy.data.objects.get('lampcam')
if cam is None:
    cam = bpy.data.objects.new('lampcam', bpy.data.cameras.new('lampcam'))
    sc.collection.objects.link(cam)


def place(n):
    c = cams[n]
    W, H = c[7]
    d, r, u = basis(*c[3:6])
    sc.camera = cam
    cam.data.type = 'PERSP'
    cam.data.sensor_fit = 'HORIZONTAL'
    cam.data.sensor_width = 36
    cam.data.shift_x = cam.data.shift_y = 0.0
    cam.data.clip_start, cam.data.clip_end = 0.05, 1000
    cam.data.lens = c[6] * 36 / W
    cam.matrix_world = Matrix.Translation(B(*c[:3])) @ Matrix((B(*r), B(*u), -B(*d))).transposed().to_4x4()
    sc.render.resolution_x, sc.render.resolution_y = int(W), int(H)
    sc.render.resolution_percentage = 100
    p = poses.get(n, {})
    dy, th = p.get('dy', 0.0), math.radians(p.get('pitch_deg', 0.0))
    body.matrix_basis = Matrix.Translation(B(0, dy, 0)) @ Matrix.Rotation(-th, 4, 'X') @ body_m0
    bpy.context.view_layer.update()
    return c, W, H


import random
random.seed(7)
palette = {m.name: (random.random(), random.random(), random.random(), 1) for m in sorted(bpy.data.materials, key=lambda m: m.name)}


def _s(c):
    return int(round(255 * (12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055)))


json.dump({k: [_s(v) for v in col[:3]] for k, col in palette.items()}, open(os.path.join(outdir, 'palette.json'), 'w'))
# which objects to hide in the id / silhouette renders (the check scene's ground etc. come later)
if '--noids' not in argv:
    eng0 = sc.render.engine
    sc.render.engine = 'BLENDER_WORKBENCH'
    sc.render.film_transparent = True
    sc.view_settings.view_transform = 'Standard'
    sc.display.render_aa = 'OFF'
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_mode = 'RGBA'
    sh = sc.display.shading
    sh.light = 'FLAT'
    sh.show_object_outline = False
    sh.show_cavity = False
    keep = {o.name for o in [root] + list(root.children_recursive)}
    hidden = []
    for o in sc.objects:
        if o.name not in keep and o.type == 'MESH' and not o.hide_render:
            o.hide_render = True
            hidden.append(o)
    dc0 = {m.name: tuple(m.diffuse_color) for m in bpy.data.materials}
    for n in names:
        place(n)
        sh.color_type = 'SINGLE'
        sh.single_color = (1, 1, 1)
        sc.render.filepath = os.path.join(outdir, f'{n}_sil.png')
        bpy.ops.render.render(write_still=True)
        for m in bpy.data.materials:
            m.diffuse_color = palette[m.name]
        sh.color_type = 'MATERIAL'
        sc.render.filepath = os.path.join(outdir, f'{n}_ids.png')
        bpy.ops.render.render(write_still=True)
        print('ids', n, flush=True)
    for m in bpy.data.materials:
        m.diffuse_color = dc0[m.name]
    for o in hidden:
        o.hide_render = False
    sc.render.film_transparent = False

if '--nocycles' in argv:
    body.matrix_basis = body_m0
    sys.exit(0)

scene()
sc = bpy.context.scene
if sc.camera is not cam:
    sc.camera = cam
pm = bpy.data.materials.get('paint')
bsdf = pm.node_tree.nodes.get('Principled BSDF') if pm else None
paint0 = tuple(bsdf.inputs['Base Color'].default_value) if bsdf else None
for n in names:
    if LAMPS is not None and n not in LAMPS and '--full' not in argv:
        continue
    c, W, H = place(n)
    eye = c[:3]
    light(eye, (0, 0.5, 0))
    sc.render.engine = 'CYCLES'
    sc.cycles.samples = samples
    sc.render.film_transparent = False
    if bsdf is not None:
        bsdf.inputs['Base Color'].default_value = srgb(PAINTS[n]) if n in PAINTS else paint0
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_mode = 'RGB'
    if LAMPS is not None and n in LAMPS and '--full' not in argv:
        import numpy as np
        P_ = np.concatenate([np.array(v['poly'], float) for v in LAMPS[n].values()])
        x0, y0 = P_.min(0) - 70
        x1, y1 = P_.max(0) + 70
        sc.render.use_border, sc.render.use_crop_to_border = True, False
        sc.render.border_min_x, sc.render.border_max_x = max(0.0, x0 / W), min(1.0, x1 / W)
        sc.render.border_min_y, sc.render.border_max_y = max(0.0, 1 - y1 / H), min(1.0, 1 - y0 / H)
        sc.render.filepath = os.path.join(outdir, f'{n}_lamps{"_night" if NIGHT else ""}.png')
    else:
        sc.render.use_border = False
        sc.render.filepath = os.path.join(outdir, f'{n}_full{"_night" if NIGHT else ""}.png')
    bpy.ops.render.render(write_still=True)
    print('cycles', n, flush=True)
body.matrix_basis = body_m0
