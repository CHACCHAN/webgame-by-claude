"""
loop.py (Blender): build the S15 from the repo scripts, pose the body like each photo's car (dy, pitch from the
bundle adjustment), render silhouette and material-id images from every solved camera, run silfit and darkfit on
every photo and print one table. (After fitdata/hayate/tools/loop2.py.)

  PY=<python with cv2+PIL> blender.sh -t 4 -b --factory-startup --python loop.py -- <fit.json> <outdir> [--photos a,b]
      [--glb out.glb] [--nofit] [--ffd lattice.json|none] [--pose cams_with_pose.json] [--gnd] [--import model.glb]

fit.json: {"cams": <ba.json>, "photos": {name: {"photo": path, "band": 0.06, "ignore": [[x0,y0,x1,y1]], "mask": path,
           "livery": "white"|"red"}}}
"""
import json, math, os, random, subprocess, sys, time

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
REPO_CARS = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
SILFIT = os.path.join(REPO_CARS, '..', '..', 'carfit', 'silfit.py')
DARKFIT = os.path.join(HERE, 'darkfit.py')
PY = os.environ.get('PY', 'python3')
sys.path.insert(0, REPO_CARS)

import bpy
from mathutils import Matrix, Vector

argv = sys.argv[sys.argv.index('--') + 1:]
fit = json.load(open(argv[0]))
outdir = argv[1]
os.makedirs(outdir, exist_ok=True)
only = argv[argv.index('--photos') + 1].split(',') if '--photos' in argv else None
camdata = json.load(open(argv[argv.index('--cams') + 1] if '--cams' in argv else fit['cams']))
if '--pose' in argv:
    camdata['pose'] = json.load(open(argv[argv.index('--pose') + 1]))['pose']
cams, poses = camdata['cams'], camdata.get('pose', {})
names = [n for n in fit['photos'] if (only is None or n in only) and n in cams]

t0 = time.time()
import s15
import s15_kit as K
K.clear_scene()
opts = {'paint': '#9a9ea4', 'wing': '--wing' in argv}
if '--ffd' in argv:
    import s15_ffd
    v = argv[argv.index('--ffd') + 1]
    opts['ffd'] = False if v == 'none' else s15_ffd.Lattice.load(v)
if '--import' in argv:
    # an exported GLB instead of the scripts (e.g. the WIP before the fit): its 'body' node is posed like the build's
    bpy.ops.import_scene.gltf(filepath=argv[argv.index('--import') + 1])
else:
    root, mats = s15.build(opts)
body = bpy.data.objects['body']
if '--glb' in argv:
    K.export_glb(argv[argv.index('--glb') + 1], root)
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
gplate = None
if '--gnd' in argv:
    # a ground plate round the footprint: where it shows under the model, the photo's ground shadow is left out
    import bmesh as _bm
    bmg = _bm.new()
    for p in ((-1.25, -2.8), (1.25, -2.8), (1.25, 2.7), (-1.25, 2.7)):
        bmg.verts.new(B(p[0], 0.003, p[1]))
    bmg.faces.new(bmg.verts)
    meg = bpy.data.meshes.new('gplate')
    bmg.to_mesh(meg)
    gplate = bpy.data.objects.new('gplate', meg)
    sc.collection.objects.link(gplate)
    gplate.hide_render = True


def _srgb(c):
    return int(round(255 * (12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055)))


json.dump({k: [_srgb(v) for v in col[:3]] for k, col in palette.items()}, open(os.path.join(outdir, 'palette.json'), 'w'))
for name in names:
    c = cams[name]
    W, H = c[7]
    d, r, u = basis(*c[3:6])
    cam.matrix_world = Matrix.Translation(B(*c[:3])) @ Matrix((B(*r), B(*u), -B(*d))).transposed().to_4x4()
    cam.data.lens = c[6] * 36 / W
    sc.render.resolution_x, sc.render.resolution_y = int(W), int(H)
    sc.render.resolution_percentage = 100
    p = poses.get(name, {})
    dy, th = p.get('dy', 0.0), math.radians(p.get('pitch_deg', 0.0))
    body.matrix_basis = Matrix.Translation(B(0, dy, 0)) @ Matrix.Rotation(-th, 4, 'X') @ body_m0
    sh.color_type = 'SINGLE'
    sh.single_color = (1, 1, 1)
    sc.render.filepath = os.path.join(outdir, f'{name}_sil.png')
    bpy.ops.render.render(write_still=True)
    if gplate is not None:
        gplate.hide_render = False
        sc.render.filepath = os.path.join(outdir, f'{name}_gnd.png')
        bpy.ops.render.render(write_still=True)
        gplate.hide_render = True
    for m in bpy.data.materials:
        m.diffuse_color = palette[m.name]
    sh.color_type = 'MATERIAL'
    sc.render.filepath = os.path.join(outdir, f'{name}_ids.png')
    bpy.ops.render.render(write_still=True)
body.matrix_basis = body_m0
t_render = time.time() - t0 - t_build
if '--nofit' in argv:
    sys.exit(0)


def run_all(cmds):
    procs = []
    for cmd in cmds:
        procs.append(subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT))
        while len([q for q in procs if q.poll() is None]) >= 3:
            time.sleep(0.1)
    for q in procs:
        out_, _ = q.communicate()
        if q.returncode:
            print(out_.decode()[-1500:])


cmds = []
for name in names:
    ph = fit['photos'][name]
    cmd = [PY, SILFIT, ph['photo'], os.path.join(outdir, f'{name}_sil.png'), outdir, '--name', name, '--ids',
           os.path.join(outdir, f'{name}_ids.png'), '--band', str(ph.get('band', 0.06))]
    for b in ph.get('ignore', []):
        cmd += ['--ignore', ','.join(str(v) for v in b)]
    if ph.get('mask'):
        cmd += ['--mask', ph['mask']]
    cmds.append(cmd)
run_all(cmds)
run_all([[PY, DARKFIT, fit['photos'][n]['photo'], os.path.join(outdir, f'{n}_ids.png'), os.path.join(outdir, 'palette.json'),
          os.path.join(outdir, f'{n}_mask.png'), outdir, n, fit['photos'][n].get('livery', 'white')] for n in names])
print(f'build {t_build:.1f}s render {t_render:.1f}s fit {time.time() - t0 - t_build - t_render:.1f}s')
print(f'{"photo":6s} {"IoU":>6s} {"p95":>5s} {"p95b":>5s} {"max":>5s}  zones (signed %: tl tm tr bl bm br)        lines: class IoU/mean/p90 %')
for name in names:
    j = json.load(open(os.path.join(outdir, f'{name}.json')))
    z = j['zones']
    zs = ' '.join(f'{z.get(k, {}).get("mean_signed_pct", float("nan")):+5.2f}' for k in ('top-left', 'top-middle', 'top-right', 'bottom-left', 'bottom-middle', 'bottom-right'))
    worst = max((abs(v['mean_signed_pct']) for v in z.values()), default=0)
    ok = j['iou'] >= 0.95 and j['render_to_photo_p95_pct'] <= 1.5 and worst <= 1.0
    dk = ''
    dj = os.path.join(outdir, f'{name}_dark.json')
    if os.path.exists(dj):
        q = json.load(open(dj))
        dk = '  ' + ' '.join(f'{k} {v["iou"]:.2f}/{v["mean_pct"]:.2f}/{v["p90_pct"]:.2f}' for k, v in q['classes'].items())
    print(f'{name:6s} {j["iou"]:6.4f} {j["render_to_photo_p95_pct"]:5.2f} {j["photo_to_render_p95_pct"]:5.2f} {j["max_pct"]:5.1f}  {zs}  {"PASS" if ok else "    "}{dk}')
