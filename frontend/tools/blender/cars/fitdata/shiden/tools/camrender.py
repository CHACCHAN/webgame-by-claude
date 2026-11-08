"""camrender.py (Blender) -- <cams.json> <outdir> <names> [--paint '#c8cbce'] [--scale 0.5] [--samples 24] [--closed]
Builds shiden and renders it in Cycles (the check-render scene) from each photo's solved camera: <name>_cy.png."""
import sys, os, json, math
sys.dont_write_bytecode = True
REPO = '/home/dev/Desktop/service/internal/webgame-by-claude/frontend/tools/blender/cars'
sys.path.insert(0, REPO)
argv = sys.argv[sys.argv.index('--') + 1:]
def opt(k, d=None):
    return argv[argv.index(k) + 1] if k in argv else d
cams = json.load(open(argv[0]))['cams']; out = argv[1]; names = argv[2].split(',')
SCALE = float(opt('--scale', 0.5)); SAMPLES = int(opt('--samples', 24))
os.makedirs(out, exist_ok=True)
import bpy
from mathutils import Matrix, Vector
import shiden as CAR
import shiden_scene as S
import shiden_parts as PARTS
root, mats, counts = CAR.build_car(False)
if '--closed' in argv:
    PARTS.fold_pods(root)
S.scene(night=False)
sc = bpy.context.scene
cam = sc.camera
cam.data.sensor_fit = 'HORIZONTAL'
cam.data.sensor_width = 36


def B(x, y, z):
    return Vector((x, -z, y))


def basis(yaw, pitch, roll):
    d = Vector((math.sin(yaw) * math.cos(pitch), math.sin(pitch), math.cos(yaw) * math.cos(pitch)))
    r = d.cross(Vector((0, 1, 0))).normalized()
    u = r.cross(d)
    c, s = math.cos(roll), math.sin(roll)
    return d, c * r + s * u, -s * r + c * u


for n in names:
    c = cams[n]
    W, H = c[7]
    d, r, u = basis(*c[3:6])
    M = Matrix((B(*r), B(*u), -B(*d))).transposed()
    cam.matrix_world = Matrix.Translation(B(*c[:3])) @ M.to_4x4()
    cam.data.type = 'PERSP'
    cam.data.lens = c[6] * 36 / W
    S.light_from(tuple(c[:3]), (0.0, 0.5, 0.0), 40.0)
    sc.cycles.samples = SAMPLES
    sc.render.resolution_x, sc.render.resolution_y = int(W * SCALE), int(H * SCALE)
    sc.render.resolution_percentage = 100
    sc.render.filepath = os.path.join(out, f'{n}_cy.png')
    bpy.ops.render.render(write_still=True)
    print('RENDERED', n, flush=True)
