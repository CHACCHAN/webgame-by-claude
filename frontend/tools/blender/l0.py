"""
JR Central L0 series superconducting maglev (L0系, the first set of 2013), three cars as the game shows them: an end
car, a middle car and the other end car turned round. Our own model, built from published figures and fitted to
photos (fitdata/l0: the photos' list, the solved cameras, the fit tools); no outside model, no photo pixels.
Run with Blender 5.x:

  blender --background --factory-startup --python tools/blender/l0.py -- --out <file.glb>
      [--render <dir> [--views hero,head,...] [--samples N] [--size WxH] [--night] [--clay]] [--tex <dir>]
      views also 'photo:<cams.json>:<photo>' (a solved camera of the fit, for the comparison sheets)

Parts (tools/blender/parts/):
  l0_shape   the sections and the nose (fitted), the cars' frames      l0_body   shells, atlas, lamp panel, logo, hoods
  l0_under   bogies (magnet units, support and guide wheels), floor
The logo plate: textures/l0/l0_logo.png (l0_textures.py, our own drawing).

Cars (game car frame, origin halfway between the car's bogies; TrainInfo.consist
[{length 28, bogies 14.5, front 13.5}, {24.3, 24.3, 0}, {28, 14.5, 0}]):
  car0 end car at z = 0: nose tip +20.58 (the photos; +20.75 by the published 28.0 m), leading bogie +7.25,
  joint (and its bogie) −7.25;
  car1 middle car at z = −19.4: joints ±12.15, a bogie under each (carried by this car);
  car2 end car at z = −38.8, turned round: its nose tip at z = −59.38 in the train.
"""
import json
import math
import os
import sys
import tempfile

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, 'parts'))
import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import train_kit as K  # noqa: E402
import body_n1000 as BD  # noqa: E402
import l0_shape as S  # noqa: E402
import l0_body as LB  # noqa: E402
import l0_under as LU  # noqa: E402

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []


def opt(name, default=None):
    return argv[argv.index(name) + 1] if name in argv else default


OUT = opt('--out')
RENDER = opt('--render')
VIEWS = opt('--views', 'hero')
SAMPLES = int(opt('--samples', '64'))
SIZE = tuple(int(v) for v in opt('--size', '1600x900').split('x'))
TEX = opt('--tex')
CLAY = '--clay' in argv
NIGHT = '--night' in argv
SHAPE = opt('--shape')                  # a fit's working shape (JSON) in place of l0_shape's table

CARS = (('car0', 'end', False), ('car1', 'mid', False), ('car2', 'end', True))


def tris(part):
    return sum(len(f.verts) - 2 for f in part.bm.faces)


def build_parts(name, kind, shell):
    count = {}
    body = BD.UVPart(f'{name}_body', sharp=40.0)
    shell.build(body)
    count['shell'] = tris(body)
    n = tris(body)
    if kind == 'end':
        LB.logo_plates(body, shell)
        LB.lamp_panel(body, shell)
        LB.hood(body, S.JOINT_END + S.GAP, -1)
    else:
        for sign in (-1, 1):
            LB.hood(body, sign * (S.JOINT_MID - S.GAP), sign)
    count['fittings'] = tris(body) - n
    gear = K.Part(f'{name}_gear')
    LU.underfloor(gear, kind)
    count['under'] = tris(gear)
    return body, gear, count


def main():
    if SHAPE:
        sh = json.load(open(SHAPE))
        S.load_shape(sh)
    K.clear_scene()
    tex_dir = TEX or tempfile.mkdtemp(prefix='l0-tex-')
    shells = {k: LB.Shell(k) for k in LB.KINDS}
    built = {}
    for name, kind, flip in CARS:
        # each car gets its own shell object (the decals ray-cast on it); end cars share the shape
        sh = LB.Shell(kind) if name != 'car0' and kind == 'end' else shells[kind]
        built[name] = build_parts(name, kind, sh)
    m = K.Materials()
    LB.add_materials(m, tex_dir, shells)
    LU.add_materials(m)
    if CLAY:
        clay = m.add('clay', '#b8b8b8', roughness=0.5)
        for k in list(m.mats):
            m.mats[k] = clay
    roots = []
    total = 0
    for name, kind, flip in CARS:
        body, gear, count = built[name]
        root = K.car_empty(name, S.CAR_Z[name])
        if flip:
            root.rotation_euler = (0, 0, math.pi)
        body.build(root, m.mats)
        gear.build(root, m.mats)
        total += sum(count.values())
        print(f'TRIS {name}: {sum(count.values())} ' + ' '.join(f'{k} {v}' for k, v in count.items()))
        roots.append(root)
    print(f'TRIS total {total}')
    print('MATERIALS', len({id(v) for v in m.mats.values()}))
    for x, y in LB.lamp_centres():
        print(f'LAMP head x {x:+.3f} y {y:.3f} r {LB.HEAD_R}')
    if OUT:
        K.export_glb(OUT, roots)
    if RENDER:
        render_views()


# ---------------------------------------------------------------- check renders
# game frame: eye, target, lens (car0's nose tip at z = +20.58, car2's at −59.38)
VIEWS_L0 = {
    'hero': ((-7.0, 2.3, 36.0), (0.4, 1.4, 11.0), 40),
    'head': ((0.25, 1.3, 70.0), (0.0, 1.1, 20.0), 150),
    'front34': ((7.0, 2.6, 32.0), (0.0, 1.3, 14.0), 35),
    'side': ((45.0, 1.8, -4.0), (0.0, 1.8, -4.0), 50),
    'sidenose': ((26.0, 1.6, 10.0), (0.0, 1.6, 10.0), 45),
    'top': ((14.0, 24.0, 8.0), (0.0, 1.5, 6.0), 40),
    'low': ((6.0, 0.6, 30.0), (0.0, 1.0, 15.0), 30),
    'lamps': ((0.9, 1.1, 24.5), (0.0, 0.85, 20.6), 60),
    'bogie': ((4.0, 0.35, 1.0), (0.0, 0.45, 7.25), 30),
    'rear34': ((7.5, 2.4, -80.0), (0.0, 1.4, -52.0), 40),
    'roof': ((9.0, 9.0, -2.0), (0.0, 3.2, -14.0), 40),
    'joint': ((4.5, 2.2, -3.0), (0.0, 1.8, -7.25), 35),
}
LIT = {'hero', 'head', 'front34', 'lamps', 'low', 'ortho'}


def _panels():
    """bright soft panels out of view and a light ground horizon for the metal check"""
    for k, (pos, rot, size, energy) in enumerate((((25.0, 14.0, 30.0), (60, 0, 120), 30.0, 400.0),
                                                 ((-25.0, 14.0, 0.0), (60, 0, -60), 30.0, 300.0))):
        ld = bpy.data.lights.new(f'panel{k}', 'AREA')
        ld.size = size
        ld.energy = energy * 50
        ob = bpy.data.objects.new(f'panel{k}', ld)
        ob.location = K.B(*pos)
        ob.rotation_euler = tuple(math.radians(a) for a in rot)
        ob.visible_camera = False
        bpy.context.scene.collection.objects.link(ob)


def _guideway(z0=-110.0, z1=60.0):
    """the guideway's concrete floor (y = 0) over the showcase's ballast"""
    me = bpy.data.meshes.new('guideway')
    import bmesh
    bm = bmesh.new()
    vs = [bm.verts.new(K.B(x, y, z)) for x, y, z in ((-1.9, 0.003, z0), (1.9, 0.003, z0), (1.9, 0.003, z1), (-1.9, 0.003, z1))]
    f = bm.faces.new(vs)
    if f.normal.z < 0:
        f.normal_flip()
    bm.to_mesh(me)
    ob = bpy.data.objects.new('guideway', me)
    mat = bpy.data.materials.new('sc_guideway')
    mat.use_nodes = True
    mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = K.srgb('#a7a59f')
    mat.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.9
    me.materials.append(mat)
    bpy.context.scene.collection.objects.link(ob)


def photo_camera(spec):
    """'photo:<cams.json>:<name>[:scale]' → camera set from a solved photo camera (cam.py's model)"""
    parts = spec.split(':')
    cams = json.load(open(parts[1]))['cams']
    c = cams[parts[2]]
    scale = float(parts[3]) if len(parts) > 3 else 0.5
    x, y, z, yaw, pitch, roll, f, (W, H) = c
    sys.path.insert(0, os.path.join(HERE, 'fitdata', 'l0', 'tools'))
    import cam as C
    import numpy as np
    d, r, u = C.basis(yaw, pitch, roll)
    sc = bpy.context.scene
    cam = sc.camera
    rot = Matrix((K.B(*r), K.B(*u), -K.B(*d))).transposed()
    cam.matrix_world = Matrix.Translation(K.B(x, y, z)) @ rot.to_4x4()
    cam.data.sensor_fit = 'HORIZONTAL'
    cam.data.sensor_width = 36.0
    cam.data.lens = f * 36.0 / W
    cam.data.shift_x = cam.data.shift_y = 0.0
    sc.render.resolution_x, sc.render.resolution_y = int(round(W * scale)), int(round(H * scale))
    sc.render.resolution_percentage = 100
    if len(parts) > 4:
        # a crop: x0/y0/x1/y1 in the photo's working pixels
        x0, y0, x1, y1 = (float(t) for t in parts[4].split('/'))
        sc.render.use_border = True
        sc.render.use_crop_to_border = True
        sc.render.border_min_x, sc.render.border_max_x = x0 / W, x1 / W
        sc.render.border_min_y, sc.render.border_max_y = 1 - y1 / H, 1 - y0 / H
    else:
        sc.render.use_border = False
    return (x, y, z), tuple(np.array([x, y, z]) + 10 * np.array(d))


def render_views():
    import showcase as S2
    if NIGHT:
        S2.scene(sun_elevation=3.0, z0=-110.0, z1=60.0, sky_strength=0.006, sun_energy=0.03)
        S2.grade(exposure=0.8)
    else:
        S2.scene(z0=-110.0, z1=60.0)
        _panels()
    _guideway()
    sc = S2.bpy.context.scene
    sc.render.threads_mode = 'FIXED'
    sc.render.threads = 4
    os.makedirs(RENDER, exist_ok=True)
    for v in VIEWS.split(','):
        # the leading end shows its four lamps white, the trailing end the inner (white/red) ones red
        rear = v.startswith('rear')
        lit = (v in LIT or NIGHT) and not rear
        S2.headlamps(lit, material=LB.P + 'lamp', strength=60.0 if NIGHT else 25.0)
        tail = bpy.data.materials.get(LB.P + 'tail')
        if tail is not None:
            p = tail.node_tree.nodes.get('Principled BSDF')
            if rear:
                p.inputs['Emission Color'].default_value = (1.0, 0.05, 0.03, 1.0)
                p.inputs['Emission Strength'].default_value = 2.5 if NIGHT else 0.0
            else:
                p.inputs['Emission Color'].default_value = (1.0, 0.93, 0.82, 1.0)
                p.inputs['Emission Strength'].default_value = (60.0 if NIGHT else 25.0) if lit else 0.0
        name = v.replace(':', '_').replace('/', '_')
        if v in ('ortho', 'rearortho'):
            # head-on, orthographic, lamps lit: for measuring TrainInfo.lamps (2 mm a pixel over 3.2 m)
            cam = sc.camera
            cam.data.type = 'ORTHO'
            cam.data.ortho_scale = 3.2
            cam.location = K.B(0.0, 1.0, 60.0)
            cam.rotation_euler = (K.B(0.0, 1.0, 0.0) - K.B(0.0, 1.0, 60.0)).to_track_quat('-Z', 'Y').to_euler()
            sc.render.use_border = False
            sc.render.resolution_x = sc.render.resolution_y = 1600
            sc.cycles.samples = SAMPLES
            sc.render.filepath = os.path.join(RENDER, v + '.png')
            bpy.ops.render.render(write_still=True)
            cam.data.type = 'PERSP'
            continue
        if v.startswith('photo:'):
            name = 'photo_' + v.split(':')[2] + ('_crop' if len(v.split(':')) > 4 else '')
            eye, target = photo_camera(v)
            S2.light_from(eye, target, 35.0)
            sc.cycles.samples = SAMPLES
            sc.render.filepath = os.path.join(RENDER, name + '.png')
            bpy.ops.render.render(write_still=True)
            continue
        spec = VIEWS_L0[v]
        sc.render.use_border = False
        cam = sc.camera
        cam.data.shift_x = cam.data.shift_y = 0.0
        cam.data.sensor_fit = 'AUTO'
        S2.render(spec, os.path.join(RENDER, name + '.png'), size=SIZE, samples=SAMPLES)


main()
