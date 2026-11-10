"""
lampscore.py (Blender): the U9's lamps against their outlines traced on the photos (fitdata/u9/lamps.json), lens by
lens. The model is built from the repo scripts with the fitted deformation; its lamp faces get an id colour (hl_L / hl_R
by side, tl), everything else black, and a flat render from each photo's solved camera and body pose gives the model's
lamp masks. Per lamp: IoU of the two areas and the outline deviation both ways (sampled on the mask edges): p95 and max
in px of the 1280-wide photo. Optionally close-up crops: photo with the tracing (green) and the model's outline
(magenta).

  PYFIT=<dir with cv2/PIL> blender.sh -t 6 -b --factory-startup --python lampscore.py -- <lamps.json> <cams.json>
      <ffd.json> <outdir> --photos <photo dir> [--only c00,c12] [--crops] [--before old.json]
Out: <outdir>/lampscore.json, <outdir>/<photo>_ids.png, <outdir>/crop_<photo>_<lamp>.png
"""
import json, math, os, sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
REPO_CARS = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, REPO_CARS)
sys.path.insert(0, os.environ.get('PYFIT', ''))

import bpy
import numpy as np
import cv2
from mathutils import Matrix, Vector
from PIL import Image, ImageDraw

argv = sys.argv[sys.argv.index('--') + 1:]
lj, cj, fj, out = argv[:4]
os.makedirs(out, exist_ok=True)


def opt(k, d=None):
    return argv[argv.index(k) + 1] if k in argv else d


import u9_kit as K
import u9_parts as PT
import u9_ffd as FF

traces = json.load(open(lj))['photos']
camdata = json.load(open(cj))
only = opt('--only').split(',') if opt('--only') else list(traces)
pdir = opt('--photos')
prev = json.load(open(opt('--before'))) if opt('--before') else {}

K.clear_scene()
mats = PT.materials('#9a9ea4')
root = K.empty('u9')
PT.build_all(root, mats, ffd=FF.Lattice.load(fj))
body = bpy.data.objects['body']
IDS = {'hl_L': (1, 0, 0), 'hl_R': (0, 1, 0), 'tl_C': (0, 0, 1)}
idm = {}
for k, c in IDS.items():
    m = bpy.data.materials.new('id_' + k)
    m.diffuse_color = (*c, 1)
    idm[k] = m
for m in bpy.data.materials:
    if not m.name.startswith('id_'):
        m.diffuse_color = (0, 0, 0, 1)
for ob in body.children_recursive:
    if ob.type != 'MESH':
        continue
    me = ob.data
    names = [m.name if m else '' for m in me.materials]
    if 'headlight' not in names and 'taillight' not in names:
        continue
    slot = {}
    for k in IDS:
        me.materials.append(idm[k])
        slot[k] = len(me.materials) - 1
    mw = ob.matrix_world
    for p in me.polygons:
        nm = names[p.material_index]
        if nm == 'headlight':
            p.material_index = slot['hl_L' if (mw @ p.center).x > 0 else 'hl_R']
        elif nm == 'taillight':
            p.material_index = slot['tl_C']

sc = bpy.context.scene
sc.render.engine = 'BLENDER_WORKBENCH'
sc.display.shading.light = 'FLAT'
sc.display.shading.color_type = 'MATERIAL'
sc.display.shading.show_cavity = False
sc.display.shading.show_specular_highlight = False
sc.display.render_aa = 'OFF'
sc.view_settings.view_transform = 'Standard'
sc.render.film_transparent = False
sc.world = sc.world or bpy.data.worlds.new('w')
sc.world.color = (0, 0, 0)
sc.render.image_settings.file_format = 'PNG'
cam = bpy.data.objects.new('lcam', bpy.data.cameras.new('lcam'))
sc.collection.objects.link(cam)
sc.camera = cam
cam.data.clip_start = 0.05
cam.data.sensor_fit = 'HORIZONTAL'
cam.data.sensor_width = 36


def edge(m):
    return m & ~(cv2.erode(m.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0)


def outline_dev(a, b):
    """distances (px) from the edge of a to the edge of b and back"""
    ea, eb = edge(a), edge(b)
    if not ea.any() or not eb.any():
        return np.array([999.0])
    da = cv2.distanceTransform((~eb).astype(np.uint8), cv2.DIST_L2, 5)
    db = cv2.distanceTransform((~ea).astype(np.uint8), cv2.DIST_L2, 5)
    return np.concatenate([da[ea], db[eb]])


res = {}
m0 = body.matrix_basis.copy()
for n in only:
    if n not in camdata['cams'] or n not in traces:
        continue
    c = camdata['cams'][n]
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
    p = camdata.get('pose', {}).get(n, {})
    body.matrix_basis = Matrix.Translation(K.B(0, p.get('dy', 0.0), 0)) @ \
        Matrix.Rotation(-math.radians(p.get('pitch_deg', 0.0)), 4, 'X') @ m0
    f = os.path.join(out, f'{n}_ids.png')
    sc.render.filepath = f
    bpy.ops.render.render(write_still=True)
    body.matrix_basis = m0
    ids = np.asarray(Image.open(f).convert('RGB')).astype(int)
    photo = Image.open(os.path.join(pdir, f'{n}.jpg')).convert('RGB')
    for k, tr in traces[n].items():
        col = np.array(IDS[k]) * 255
        mm = (np.abs(ids - col).sum(-1) < 60)
        tm = np.zeros((int(H), int(W)), np.uint8)
        cv2.fillPoly(tm, [np.round(np.array(tr['poly'])).astype(np.int32)], 1)
        tm = tm > 0
        if 'clip' in tr:            # a partial tracing (the rest hidden or not separable): both masks inside the clip
            cm = np.zeros((int(H), int(W)), np.uint8)
            cv2.fillPoly(cm, [np.round(np.array(tr['clip'])).astype(np.int32)], 1)
            mm = mm & (cm > 0)
            tm = tm & (cm > 0)
        iou = float((mm & tm).sum() / max(1, (mm | tm).sum()))
        dev = outline_dev(mm, tm)
        row = {'iou': round(iou, 3), 'p95': round(float(np.percentile(dev, 95)), 1), 'max': round(float(dev.max()), 1),
               'model_px': int(mm.sum()), 'trace_px': int(tm.sum())}
        res.setdefault(n, {})[k] = row
        b = prev.get(n, {}).get(k)
        print(f'LAMP {n} {k:5s} IoU {row["iou"]:.3f}  p95 {row["p95"]:5.1f}  max {row["max"]:5.1f} px'
              + (f'   (before {b["iou"]:.3f} / {b["p95"]} / {b["max"]})' if b else ''))
        if '--crops' in argv:
            ys, xs = np.nonzero(tm | mm)
            x0, x1 = max(0, xs.min() - 20), min(int(W), xs.max() + 20)
            y0, y1 = max(0, ys.min() - 20), min(int(H), ys.max() + 20)
            im = photo.copy()
            ov = np.asarray(im).copy()
            ov[edge(tm)] = (0, 255, 0)
            ov[edge(mm)] = (255, 0, 255)
            crop = Image.fromarray(ov).crop((x0, y0, x1, y1))
            s = 300 / max(1, y1 - y0)
            crop = crop.resize((int((x1 - x0) * s), int((y1 - y0) * s)), Image.NEAREST)
            crop.save(os.path.join(out, f'crop_{n}_{k}.png'))
json.dump(res, open(os.path.join(out, 'lampscore.json'), 'w'), indent=1)
print('WROTE', os.path.join(out, 'lampscore.json'))
