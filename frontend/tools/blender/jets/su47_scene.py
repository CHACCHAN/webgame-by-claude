"""
A check scene for the Su-47 (not part of the game): a concrete apron, sky and sun (Cycles on the CPU), soft panels
for the black skin to mirror, and the views of the owner's sheet (perspective ones and true orthographic ones for
measuring: side, top, front, underside, all with the nose to the left or the aircraft upright).
"""
import math

import bpy
from mathutils import Matrix, Vector

import jet_kit as K

MID = -2.7                       # the airframe's middle (z)
# game frame: eye, target, lens in mm (36 mm sensor), up
VIEWS = {
    'front34': ((14.0, 5.2, 20.0), (0.0, 2.3, -1.5), 50, (0, 1, 0)),
    'rear34': ((-14.5, 6.5, -25.0), (0.0, 2.4, -3.5), 50, (0, 1, 0)),
    'low34': ((10.0, 1.3, 17.0), (0.0, 2.4, -1.0), 35, (0, 1, 0)),
    'high34': ((12.0, 13.0, 14.0), (0.0, 2.0, -3.0), 45, (0, 1, 0)),
    'cockpit': ((2.6, 4.25, 4.6), (0.0, 3.25, 2.75), 55, (0, 1, 0)),
    'cockpit_top': ((0.9, 5.6, 2.2), (0.0, 3.0, 2.75), 50, (0, 0, 1)),
    'gear': ((6.5, 1.25, 3.2), (1.0, 1.05, -1.2), 40, (0, 1, 0)),
    'nosegear': ((2.8, 1.1, 6.2), (0.0, 1.0, 3.0), 45, (0, 1, 0)),
    'maingear': ((5.2, 1.0, -0.9), (1.9, 0.9, -3.0), 45, (0, 1, 0)),
    'nozzles': ((-4.5, 3.6, -19.5), (0.0, 2.2, -11.5), 50, (0, 1, 0)),
    'intake': ((4.2, 1.9, 6.2), (1.2, 2.0, 0.2), 50, (0, 1, 0)),
    'tail': ((-9.5, 4.5, -14.5), (-1.5, 3.6, -10.0), 50, (0, 1, 0)),
    'nose': ((5.0, 3.4, 10.5), (0.0, 2.8, 4.0), 60, (0, 1, 0)),
    'belly': ((7.0, 0.5, 2.0), (0.0, 2.0, -4.0), 28, (0, 1, 0)),
}
# eye, target, orthographic scale, up
ORTHO = {
    'o_side': ((60.0, 3.3, MID), (0.0, 3.3, MID), 24.5, (0, 1, 0)),
    'o_top': ((0.0, 60.0, MID), (0.0, 0.0, MID), 31.0, (-1, 0, 0)),
    'o_under': ((0.0, -60.0, MID), (0.0, 0.0, MID), 31.0, (1, 0, 0)),
    'o_front': ((0.0, 3.3, 60.0), (0.0, 3.3, 0.0), 18.5, (0, 1, 0)),
    'o_rear': ((0.0, 3.3, -60.0), (0.0, 3.3, 0.0), 18.5, (0, 1, 0)),
}


def D(v):
    """a game direction as a Blender vector"""
    return K.B(*v) - K.B(0, 0, 0)


def look(obj, eye, target, up):
    f = (D(target) - D(eye)).normalized()
    r = f.cross(D(up)).normalized()
    u = r.cross(f)
    M = Matrix((r, u, -f)).transposed().to_4x4()
    M.translation = K.B(*eye)
    obj.matrix_world = M


def scene(mats, night=False):
    sc = bpy.context.scene
    world = bpy.data.worlds.new('sky')
    sc.world = world
    world.use_nodes = True
    nt = world.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    bg = nt.nodes.new('ShaderNodeBackground')
    out = nt.nodes.new('ShaderNodeOutputWorld')
    if night:
        bg.inputs['Color'].default_value = K.srgb('#0b0f1c')
        bg.inputs['Strength'].default_value = 0.25
    else:
        sky = nt.nodes.new('ShaderNodeTexSky')
        for kind in ('MULTIPLE_SCATTERING', 'NISHITA', 'HOSEK_WILKIE'):
            try:
                sky.sky_type = kind
                break
            except TypeError:
                continue
        try:
            sky.sun_elevation = math.radians(38)
            sky.sun_rotation = math.radians(215)
            sky.sun_disc = False
        except AttributeError:
            pass
        nt.links.new(sky.outputs['Color'], bg.inputs['Color'])
        bg.inputs['Strength'].default_value = 0.32
    nt.links.new(bg.outputs[0], out.inputs[0])
    # the apron: light concrete in slabs
    me = bpy.data.meshes.new('ground')
    s = 400.0
    me.from_pydata([(-s, -s, 0), (s, -s, 0), (s, s, 0), (-s, s, 0)], [], [(0, 1, 2, 3)])
    g = bpy.data.objects.new('ground', me)
    sc.collection.objects.link(g)
    gm = bpy.data.materials.new('st_concrete')
    gm.use_nodes = True
    gnt = gm.node_tree
    p = gnt.nodes['Principled BSDF']
    p.inputs['Roughness'].default_value = 0.9
    co = gnt.nodes.new('ShaderNodeTexCoord')
    brick = gnt.nodes.new('ShaderNodeTexBrick')
    brick.offset = 0.0
    brick.inputs['Scale'].default_value = 0.2
    brick.inputs['Mortar Size'].default_value = 0.004
    brick.inputs['Color1'].default_value = K.srgb('#85837d')
    brick.inputs['Color2'].default_value = K.srgb('#7b7973')
    brick.inputs['Mortar'].default_value = K.srgb('#4b4a47')
    brick.inputs['Brick Width'].default_value = 1.0
    brick.inputs['Row Height'].default_value = 1.0
    gnt.links.new(co.outputs['Object'], brick.inputs['Vector'])
    gnt.links.new(brick.outputs['Color'], p.inputs['Base Color'])
    me.materials.append(gm)
    if not night:
        sun = bpy.data.lights.new('sun', 'SUN')
        sun.energy = 3.4
        sun.angle = math.radians(1.5)
        so = bpy.data.objects.new('sun', sun)
        sc.collection.objects.link(so)
        look(so, (-30.0, 42.0, 28.0), (0.0, 0.0, 0.0), (0, 1, 0))
    else:
        for name, pos, e in (('mast_a', (18.0, 16.0, 12.0), 60000.0), ('mast_b', (-20.0, 16.0, -18.0), 45000.0)):
            L = bpy.data.lights.new(name, 'SPOT')
            L.energy = e
            L.spot_size = math.radians(80)
            L.color = (1.0, 0.82, 0.6)
            L.shadow_soft_size = 0.4
            o = bpy.data.objects.new(name, L)
            sc.collection.objects.link(o)
            look(o, pos, (0.0, 1.0, MID), (0, 1, 0))
    # see into the cockpit: the game's glass is its own material; here a clear, faintly tinted pane
    gl = mats.get('glass')
    if gl is not None:
        p = gl.node_tree.nodes.get('Principled BSDF')
        p.inputs['Transmission Weight'].default_value = 1.0
        p.inputs['Roughness'].default_value = 0.0
        p.inputs['IOR'].default_value = 1.05
        p.inputs['Base Color'].default_value = (0.75, 0.72, 0.6, 1.0)
    lamp = mats.get('navlight_all')
    if lamp is not None:
        lamp.node_tree.nodes.get('Principled BSDF').inputs['Emission Strength'].default_value = 6.0 if night else 0.6
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.use_denoising = True
    sc.cycles.max_bounces = 6
    sc.cycles.transmission_bounces = 8
    vs = sc.view_settings
    try:
        vs.view_transform = 'Khronos PBR Neutral'
    except TypeError:
        vs.view_transform = 'Filmic'
    vs.exposure = 1.6 if night else 0.0
    cam = bpy.data.cameras.new('cam')
    co = bpy.data.objects.new('cam', cam)
    sc.collection.objects.link(co)
    sc.camera = co


def backfaces():
    """a check: every face seen from behind glows red (the game draws one side only)"""
    for m in bpy.data.materials:
        if m.name in ('st_concrete', 'glass') or not m.use_nodes:
            continue
        nt = m.node_tree
        for n in list(nt.nodes):
            nt.nodes.remove(n)
        out = nt.nodes.new('ShaderNodeOutputMaterial')
        geo = nt.nodes.new('ShaderNodeNewGeometry')
        mix = nt.nodes.new('ShaderNodeMixShader')
        front = nt.nodes.new('ShaderNodeBsdfDiffuse')
        front.inputs['Color'].default_value = (0.5, 0.5, 0.5, 1)
        back = nt.nodes.new('ShaderNodeEmission')
        back.inputs['Color'].default_value = (1, 0, 0, 1)
        back.inputs['Strength'].default_value = 4.0
        nt.links.new(geo.outputs['Backfacing'], mix.inputs[0])
        nt.links.new(front.outputs[0], mix.inputs[1])
        nt.links.new(back.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], out.inputs[0])


def render(view, path, size=(1600, 900), samples=48):
    sc = bpy.context.scene
    cam = sc.camera
    ground = bpy.data.objects.get('ground')
    if view in ORTHO:
        eye, target, scale, up = ORTHO[view]
        cam.data.type = 'ORTHO'
        cam.data.ortho_scale = scale
        ground.hide_render = view == 'o_under'
    else:
        eye, target, lens, up = VIEWS[view]
        cam.data.type = 'PERSP'
        cam.data.lens = lens
        ground.hide_render = False
    cam.data.clip_start, cam.data.clip_end = 0.1, 500.0
    look(cam, eye, target, up)
    sc.render.resolution_x, sc.render.resolution_y = size
    sc.render.resolution_percentage = 100
    sc.cycles.samples = samples
    sc.render.film_transparent = False
    sc.render.image_settings.file_format = 'PNG'
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print('RENDER', path)
