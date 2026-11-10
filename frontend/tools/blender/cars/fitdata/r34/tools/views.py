"""views.py (Blender): quick Workbench look at the r34 (light grey studio shading with cavity, or flat material colours)
from the standard views of r34_scene, for the fit loop (Cycles is slow without a GPU).

  blender.sh -t 8 -b --factory-startup --python views.py -- <outdir> [--views front34,rear34,side,front,rear]
      [--size 960x540] [--noffd | --ffd lattice.json] [--mat | --tex] [--glb out.glb]
"""
import math
import os
import sys

sys.dont_write_bytecode = True
REPO_CARS = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'))
sys.path.insert(0, REPO_CARS)

import bpy  # noqa: E402

argv = sys.argv[sys.argv.index('--') + 1:]


def opt(k, d):
    return type(d)(argv[argv.index(k) + 1]) if k in argv else d


out = argv[0]
os.makedirs(out, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
import r34  # noqa: E402
import r34_ffd  # noqa: E402
import r34_scene as S  # noqa: E402
from r34_kit import B  # noqa: E402

o = {'paint': '#c9ccd1'}
if '--noffd' in argv:
    o['ffd'] = False
elif '--ffd' in argv:
    o['ffd'] = r34_ffd.Lattice.load(opt('--ffd', ''))
root, mats, lamps = r34.build(o)
if '--glb' in argv:
    bpy.ops.object.select_all(action='DESELECT')
    root.select_set(True)
    for c in root.children_recursive:
        c.select_set(True)
    bpy.ops.export_scene.gltf(filepath=opt('--glb', ''), export_format='GLB', use_selection=True, export_yup=True,
                              export_apply=True, export_materials='EXPORT', export_cameras=False, export_lights=False)
sc = bpy.context.scene
sc.render.engine = 'BLENDER_WORKBENCH'
sc.view_settings.view_transform = 'Standard'
sc.display.render_aa = '8'
sh = sc.display.shading
sh.light = 'STUDIO'
sh.show_cavity = True
sh.cavity_type = 'BOTH'
sh.show_specular_highlight = True
if '--mat' in argv or '--tex' in argv:
    sh.color_type = 'TEXTURE' if '--tex' in argv else 'MATERIAL'
    for m in bpy.data.materials:
        p = m.node_tree.nodes.get('Principled BSDF') if m.node_tree else None
        if p is not None:
            m.diffuse_color = p.inputs['Base Color'].default_value
    mats['paint'].diffuse_color = (0.62, 0.64, 0.67, 1)
else:
    sh.color_type = 'SINGLE'
    sh.single_color = (0.78, 0.79, 0.81)
sc.world = bpy.data.worlds.new('w')
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
sc.collection.objects.link(cam)
sc.camera = cam
cam.data.clip_start = 0.05
cam.data.sensor_width = 36
W, H = (int(v) for v in opt('--size', '960x540').split('x'))
sc.render.resolution_x, sc.render.resolution_y = W, H
for v in opt('--views', 'front34,rear34,side,front,rear').split(','):
    eye, target, lens = S.VIEWS[v]
    cam.location = B(*eye)
    cam.rotation_euler = (B(*target) - B(*eye)).to_track_quat('-Z', 'Y').to_euler()
    if v == 'top':
        cam.rotation_euler = (0.0, 0.0, -math.pi / 2)
    if isinstance(lens, str) and lens.startswith('o'):
        cam.data.type = 'ORTHO'
        cam.data.ortho_scale = float(lens[1:])
    else:
        cam.data.type = 'PERSP'
        cam.data.lens = lens
    sc.render.filepath = os.path.join(out, f'{v}.png')
    bpy.ops.render.render(write_still=True)
