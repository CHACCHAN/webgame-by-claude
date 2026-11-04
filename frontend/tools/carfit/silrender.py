"""
silrender.py: render a car GLB from solved photo cameras, for silfit.py.

  blender -b --factory-startup --python silrender.py -- <car.glb> <cams.json> <outdir> [name,name,...] [--fold-popups]

<cams.json>: {"cams": {"<photo name>": [x, y, z, yaw, pitch, roll, focal_px, [W, H]], ...}} in GAME coordinates
(metres, +Y up, +Z = the car's front; the camera looks along d = (sin yaw cos pitch, sin pitch, cos yaw cos pitch),
roll about d; focal in pixels of a W-wide image). This is the format of car-shiden/bundle.json; convert yours if it
differs (any camera you already fitted: position, view direction, focal length).

Writes per camera: <name>_sil.png (white car on a transparent background, 1 sample, no AA: the silhouette) and
<name>_ids.png (each material a flat colour on transparent: silfit.py --ids draws its colour borders as feature lines).
--fold-popups: rotate nodes popup_l / popup_r by their extras.popupClosed (radians about the hinge's local X), as the
game does by day.
"""
import json
import math
import os
import random
import sys

import bpy
from mathutils import Matrix, Vector

argv = sys.argv[sys.argv.index('--') + 1:]
fold = '--fold-popups' in argv
argv = [a for a in argv if a != '--fold-popups']
glb, camfile, outdir = argv[:3]
cams = json.load(open(camfile))['cams']
names = argv[3].split(',') if len(argv) > 3 and argv[3] else list(cams)
os.makedirs(outdir, exist_ok=True)

for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)
bpy.ops.import_scene.gltf(filepath=glb)
if fold:
    for n in ('popup_l', 'popup_r'):
        o = bpy.data.objects.get(n)
        if o is not None:
            a = float(o.get('popupClosed', 1.2))
            o.rotation_mode = 'XYZ'
            o.rotation_euler.x += a


def B(x, y, z):
    """game (x, y, z) → Blender (x, -z, y), as the glTF importer maps +Y up"""
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
palette = {}
for m in bpy.data.materials:
    palette[m.name] = (random.random(), random.random(), random.random(), 1)

for name in names:
    c = cams[name]
    W, H = c[7]
    d, r, u = basis(*c[3:6])
    M = Matrix((B(*r), B(*u), -B(*d))).transposed()
    cam.matrix_world = Matrix.Translation(B(*c[:3])) @ M.to_4x4()
    cam.data.lens = c[6] * 36 / W
    sc.render.resolution_x, sc.render.resolution_y = int(W), int(H)
    sc.render.resolution_percentage = 100
    # silhouette: everything white
    sh.color_type = 'SINGLE'
    sh.single_color = (1, 1, 1)
    sc.render.filepath = os.path.join(outdir, f'{name}_sil.png')
    bpy.ops.render.render(write_still=True)
    # material ids
    for m in bpy.data.materials:
        m.diffuse_color = palette[m.name]
    sh.color_type = 'MATERIAL'
    sc.render.filepath = os.path.join(outdir, f'{name}_ids.png')
    bpy.ops.render.render(write_still=True)
    print('RENDERED', name)
