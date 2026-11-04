"""
A check scene for the car (Cycles): asphalt, sky, sun, cameras placed like the reference photos; and a night set-up
with the lamps lit. Not part of the game.
"""
import math

import bmesh
import bpy

import raijin_kit as K

# game frame: eye, target, lens (mm, 36 mm sensor); 'ortho_*' are orthographic (scale = view width in m)
VIEWS = {
    'front34': ((4.3, 1.25, 5.6), (0.0, 0.62, 0.35), 45),
    'rear34': ((-4.0, 1.45, -5.6), (0.0, 0.70, -0.4), 45),
    'side': ((-9.5, 0.95, 0.0), (0.0, 0.66, 0.0), 50),
    'front': ((0.0, 0.95, 9.0), (0.0, 0.66, 0.0), 70),
    'rear': ((0.0, 1.05, -9.0), (0.0, 0.70, 0.0), 70),
    'top': ((3.5, 7.5, 0.6), (0.0, 0.5, 0.0), 40),
    'wheel': ((2.2, 0.55, 2.4), (0.75, 0.33, 1.26), 45),
    'low': ((2.6, 0.35, 5.2), (0.0, 0.45, 1.2), 32),
    'ortho_side': ((-12.0, 0.70, 0.0), (0.0, 0.70, 0.0), 5.2),
    'ortho_front': ((0.0, 0.72, 12.0), (0.0, 0.72, 0.0), 2.2),
    'ortho_rear': ((0.0, 0.72, -12.0), (0.0, 0.72, 0.0), 2.2),
    'ortho_top': ((0.0, 12.0, 0.0), (0.0, 0.0, 0.0), 5.2),
    'interior': ((1.6, 1.45, 1.4), (-0.2, 0.85, -0.3), 28),
    # roughly like the reference photos (for side-by-side sheets)
    'm_r04': ((1.3, 1.55, 4.7), (0.12, 0.66, 1.0), 46),
    'm_r05': ((-1.9, 1.6, -4.5), (-0.1, 0.72, -1.0), 44),
    'm_r02': ((-3.3, 1.25, 4.4), (-0.25, 0.62, 0.15), 48),
    'm_r12': ((-2.2, 1.55, -5.4), (-0.2, 0.75, -1.2), 34),
}


def photo_view(D, height, z, lens_px, width_px, look_y=None):
    """a camera on the car's right (−x) at distance D, aimed square at the side (for the side-photo overlays)"""
    eye = (-D, height, z)
    target = (0.0, height if look_y is None else look_y, z)
    return eye, target, lens_px / width_px * 36.0


def _mat(name, colour, rough=0.9, metallic=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    p = m.node_tree.nodes['Principled BSDF']
    p.inputs['Base Color'].default_value = K.srgb(colour)
    p.inputs['Roughness'].default_value = rough
    p.inputs['Metallic'].default_value = metallic
    return m


def _asphalt():
    m = bpy.data.materials.new('sc_asphalt')
    m.use_nodes = True
    nt = m.node_tree
    p = nt.nodes['Principled BSDF']
    noise = nt.nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 300.0
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = K.srgb('#3a3a3b')
    ramp.color_ramp.elements[1].color = K.srgb('#5c5b59')
    nt.links.new(noise.outputs['Fac'], ramp.inputs['Fac'])
    nt.links.new(ramp.outputs['Color'], p.inputs['Base Color'])
    p.inputs['Roughness'].default_value = 0.85
    return m


def scene(night=False):
    sc = bpy.context.scene
    world = sc.world or bpy.data.worlds.new('sky')
    sc.world = world
    world.use_nodes = True
    nt = world.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    bg = nt.nodes.new('ShaderNodeBackground')
    out = nt.nodes.new('ShaderNodeOutputWorld')
    if night:
        bg.inputs['Color'].default_value = (0.004, 0.006, 0.012, 1)
        bg.inputs['Strength'].default_value = 1.0
    else:
        sky = nt.nodes.new('ShaderNodeTexSky')
        for kind in ('MULTIPLE_SCATTERING', 'NISHITA'):
            try:
                sky.sky_type = kind
                break
            except TypeError:
                continue
        sky.sun_elevation = math.radians(40)
        sky.sun_rotation = math.radians(-150)
        try:
            sky.sun_disc = False
        except AttributeError:
            pass
        bg.inputs['Strength'].default_value = 0.15
        nt.links.new(sky.outputs['Color'], bg.inputs['Color'])
        sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN'))
        sun.data.energy = 4.0
        sun.data.angle = math.radians(1.0)
        sun.rotation_euler = (math.radians(50), 0, math.radians(-120))
        sc.collection.objects.link(sun)
    nt.links.new(bg.outputs['Background'], out.inputs['Surface'])
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=60)
    me = bpy.data.meshes.new('ground')
    bm.to_mesh(me)
    g = bpy.data.objects.new('ground', me)
    sc.collection.objects.link(g)
    me.materials.append(_asphalt())
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.use_denoising = True
    sc.render.threads_mode = 'FIXED'
    sc.render.threads = 4
    vs = sc.view_settings
    try:
        vs.view_transform = 'Khronos PBR Neutral'
    except TypeError:
        vs.view_transform = 'Filmic'
    vs.exposure = -0.4 if not night else 0.0
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.data.clip_start = 0.05
    cam.data.clip_end = 200


def light_from(eye, target, offset=40.0):
    sun = bpy.data.objects.get('sun')
    if sun is None:
        return
    dx, dz = eye[0] - target[0], eye[2] - target[2]
    theta = math.atan2(dx, dz) + math.radians(offset)
    # Blender: game heading theta (0 = +z) → light pointing back towards the car
    sun.rotation_euler = (math.radians(48), 0, theta)


def render(view, path, size=(1280, 720), samples=32, sun_offset=40.0, mask=False):
    sc = bpy.context.scene
    sc.render.film_transparent = mask
    g = bpy.data.objects.get('ground')
    if g is not None:
        g.hide_render = mask
    eye, target, lens = VIEWS[view] if isinstance(view, str) else view
    if sun_offset is not None:
        light_from(eye, target, sun_offset)
    cam = sc.camera
    cam.location = K.B(*eye)
    cam.rotation_euler = (K.B(*target) - K.B(*eye)).to_track_quat('-Z', 'Y').to_euler()
    if isinstance(view, str) and view.startswith('ortho'):
        cam.data.type = 'ORTHO'
        cam.data.ortho_scale = lens
    else:
        cam.data.type = 'PERSP'
        cam.data.lens = lens
    sc.cycles.samples = samples
    sc.render.resolution_x, sc.render.resolution_y = size
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)


def night_lights(mats, lamps):
    """lamps lit for the night check: lenses glow, spot lights throw the beams, one street lamp overhead"""
    import raijin_kit as K
    for name, strength in (('headlight', 6.0), ('taillight', 4.0)):
        nt = mats[name].node_tree
        for n in nt.nodes:
            if n.type == 'BSDF_PRINCIPLED':
                n.inputs['Emission Strength'].default_value = strength
    sc = bpy.context.scene
    for (k, side), c in lamps.items():
        if k == 'headlight':
            l = bpy.data.objects.new('beam', bpy.data.lights.new('beam', 'SPOT'))
            l.data.energy = 900
            l.data.spot_size = math.radians(55)
            l.data.spot_blend = 0.6
            l.data.shadow_soft_size = 0.05
            l.location = K.B(c[0], c[1], c[2] + 0.08)
            # point forward (+z game = −y Blender), a little down
            l.rotation_euler = (math.radians(-85), 0, 0)
            sc.collection.objects.link(l)
        elif k == 'taillight':
            l = bpy.data.objects.new('tailglow', bpy.data.lights.new('tailglow', 'POINT'))
            l.data.energy = 6
            l.data.color = (1.0, 0.1, 0.08)
            l.data.shadow_soft_size = 0.1
            l.location = K.B(c[0], c[1], c[2] - 0.12)
            sc.collection.objects.link(l)
    st = bpy.data.objects.new('street', bpy.data.lights.new('street', 'AREA'))
    st.data.energy = 900
    st.data.size = 1.0
    st.data.color = (1.0, 0.85, 0.65)
    st.location = K.B(3.0, 7.0, -1.0)
    sc.collection.objects.link(st)
