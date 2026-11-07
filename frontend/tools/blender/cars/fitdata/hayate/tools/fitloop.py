"""
fitloop.py (Blender): build the AE86 from the repo scripts, pose the body like each photo's car (dy, pitch from the
camera solve), render the silhouette and material-id images from every solved camera, run silfit on every photo and
print one table.

  blender.sh -t 4 -b --factory-startup --python fitloop.py -- <fit.json> <outdir> [--photos a,b] [--fold] [--glb f]

fit.json: {"cams": <cams.json path>, "photos": {name: {"photo": path, "band": 0.06, "ignore": [[x0,y0,x1,y1]], "mask": path}}}
"""
import json, math, os, random, subprocess, sys, time

sys.dont_write_bytecode = True
REPO_CARS = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'))
SILFIT = os.path.join(REPO_CARS, '..', '..', 'carfit', 'silfit.py')
PY = os.environ.get('PY', 'python3')      # a Python with numpy, OpenCV and Pillow (for silfit)
sys.path.insert(0, REPO_CARS)

import bpy
from mathutils import Matrix, Vector

argv = sys.argv[sys.argv.index('--') + 1:]
fit = json.load(open(argv[0]))
outdir = argv[1]
os.makedirs(outdir, exist_ok=True)
only = argv[argv.index('--photos') + 1].split(',') if '--photos' in argv else None
FOLD = '--fold' in argv
camdata = json.load(open(fit['cams']))
cams, poses = camdata['cams'], camdata.get('pose', {})
names = [n for n in fit['photos'] if (only is None or n in only)]

t0 = time.time()
if '--glb' in argv:
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    bpy.ops.import_scene.gltf(filepath=argv[argv.index('--glb') + 1])
    body = bpy.data.objects.get('body')
    pops = [bpy.data.objects.get(n) for n in ('popup_l', 'popup_r')]
else:
    import hayate_kit as K
    import hayate_parts as P
    K.clear_scene()
    mats, tex = P.materials()
    root = K.empty('hayate')
    count = {}
    body = K.empty('body', root)
    parts = P.build_all(body, root, mats, count)
    pops = parts.get('popups', [])
    print('TRIS', sum(count.values()))
keep = set()
for o in bpy.data.objects:
    if o.name in ('hayate', 'body') or (o.parent is not None and any(a.name in ('hayate',) for a in [o] + [p for p in iter(lambda q=[o]: (q.__setitem__(0, q[0].parent) or q[0]), None)][:0])):
        pass
def _root(o):
    while o.parent is not None:
        o = o.parent
    return o
extra = [o.name for o in bpy.data.objects if o.type == 'MESH' and _root(o).name not in ('hayate', 'Scene', 'hayate.001') and not o.name.startswith('silcam')]
for o in bpy.data.objects:
    if o.type == 'MESH' and _root(o).name != _root(body).name:
        o.hide_render = True
print('HIDDEN extra objects:', extra[:20])
if FOLD:
    for o in pops:
        if o is not None:
            o.rotation_mode = 'XYZ'
            o.rotation_euler.x = float(o.get('popupClosed', 1.2))
t_build = time.time() - t0


def B(x, y, z):
    return Vector((x, -z, y))


def basis(yaw, pitch, roll):
    d = Vector((math.sin(yaw) * math.cos(pitch), math.sin(pitch), math.cos(yaw) * math.cos(pitch)))
    r = d.cross(Vector((0, 1, 0))).normalized()
    u = r.cross(d)
    c, s = math.cos(roll), math.sin(roll)
    return d, c * r + s * u, -s * r + c * u


sc = bpy.context.scene
sc.render.engine = 'BLENDER_WORKBENCH'
sc.render.film_transparent = True
sc.view_settings.view_transform = 'Standard'
sc.display.render_aa = 'OFF'
sc.render.image_settings.file_format = 'PNG'
sc.render.image_settings.color_mode = 'RGBA'
sh = sc.display.shading
sh.light = 'FLAT'
sh.show_object_outline = False
cam = bpy.data.objects.new('silcam', bpy.data.cameras.new('silcam'))
sc.collection.objects.link(cam)
sc.camera = cam
cam.data.clip_start = 0.05
cam.data.clip_end = 1000
cam.data.sensor_fit = 'HORIZONTAL'
cam.data.sensor_width = 36
random.seed(7)
palette = {m.name: (random.random(), random.random(), random.random(), 1) for m in sorted(bpy.data.materials, key=lambda m: m.name)}
body_m0 = body.matrix_basis.copy()

for name in names:
    c = cams[name]
    W, H = c[7]
    d, r, u = basis(*c[3:6])
    M = Matrix((B(*r), B(*u), -B(*d))).transposed()
    cam.matrix_world = Matrix.Translation(B(*c[:3])) @ M.to_4x4()
    cam.data.lens = c[6] * 36 / W
    sc.render.resolution_x, sc.render.resolution_y = int(W), int(H)
    sc.render.resolution_percentage = 100
    p = poses.get(name, {})
    dy, th = p.get('dy', 0.0), math.radians(p.get('pitch_deg', 0.0))
    # body pose: game y' = y cos th + z sin th + dy (nose up for th > 0) = rotation about game x by -th in Blender terms
    body.matrix_basis = Matrix.Translation(B(0, dy, 0)) @ Matrix.Rotation(-th, 4, "X") @ body_m0
    sh.color_type = 'SINGLE'
    sh.single_color = (1, 1, 1)
    sc.render.filepath = os.path.join(outdir, f'{name}_sil.png')
    bpy.ops.render.render(write_still=True)
    if '--twice' in argv:
        sc.render.filepath = os.path.join(outdir, f'{name}_sil2.png')
        bpy.ops.render.render(write_still=True)
    for m in bpy.data.materials:
        m.diffuse_color = palette[m.name]
    sh.color_type = 'MATERIAL'
    sc.render.filepath = os.path.join(outdir, f'{name}_ids.png')
    bpy.ops.render.render(write_still=True)
    if '--shaded' in argv:
        sh.light = 'STUDIO'
        sh.color_type = 'SINGLE'
        sh.single_color = (0.8, 0.8, 0.82)
        sh.show_cavity = True
        sc.display.render_aa = '8'
        sc.render.filepath = os.path.join(outdir, f'{name}_shaded.png')
        bpy.ops.render.render(write_still=True)
        sh.light = 'FLAT'
        sh.show_cavity = False
        sc.display.render_aa = 'OFF'
body.matrix_basis = body_m0
if '--nofit' in argv:
    sys.exit(0)
t_render = time.time() - t0 - t_build

rows = []
procs = []
for name in names:
    ph = fit['photos'][name]
    cmd = [PY, SILFIT, ph['photo'], os.path.join(outdir, f'{name}_sil.png'), outdir, '--name', name, '--ids', os.path.join(outdir, f'{name}_ids.png'),
           '--band', str(ph.get('band', 0.06))]
    for b in ph.get('ignore', []):
        cmd += ['--ignore', ','.join(str(v) for v in b)]
    if ph.get('mask'):
        cmd += ['--mask', ph['mask']]
    procs.append((name, subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)))
    while len([q for q in procs if q[1].poll() is None]) >= 3:
        time.sleep(0.1)
for name, pr in procs:
    pr.wait()
print(f'build {t_build:.1f}s render {t_render:.1f}s fit {time.time() - t0 - t_build - t_render:.1f}s')
print(f'{"photo":6s} {"IoU":>6s} {"p95":>5s} {"p95b":>5s} {"max":>5s}  zones (signed %: tl tm tr bl bm br)')
for name in names:
    j = json.load(open(os.path.join(outdir, f'{name}.json')))
    z = j['zones']
    zs = ' '.join(f'{z.get(k, {}).get("mean_signed_pct", float("nan")):+5.2f}' for k in ('top-left', 'top-middle', 'top-right', 'bottom-left', 'bottom-middle', 'bottom-right'))
    worst = max((abs(v['mean_signed_pct']) for v in z.values()), default=0)
    ok = j['iou'] >= 0.95 and j['render_to_photo_p95_pct'] <= 1.5 and worst <= 1.0
    print(f'{name:6s} {j["iou"]:6.4f} {j["render_to_photo_p95_pct"]:5.2f} {j["photo_to_render_p95_pct"]:5.2f} {j["max_pct"]:5.1f}  {zs}  {"PASS" if ok else ""}')
