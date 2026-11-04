"""
The check scene for the Supra (not part of the game): asphalt, sky and sun (Cycles, Khronos PBR Neutral), cameras like
the reference photos, a night variant with the lamps lit, and a flat silhouette pass for overlays on the photos.
"""
import math

import bmesh
import bpy
from mathutils import Vector

import supra_kit as K

# game frame: eye, target, lens (mm, 36 mm sensor)
VIEWS = {
    'front34': ((4.2, 1.35, 5.6), (0.0, 0.55, 0.25), 45),
    'rear34': ((-4.0, 1.55, -5.8), (0.0, 0.6, -0.4), 45),
    'side': ((9.5, 0.75, 0.0), (0.0, 0.62, -0.02), 50),
    'front': ((0.0, 0.85, 9.5), (0.0, 0.62, 0.0), 60),
    'rear': ((0.0, 0.95, -9.5), (0.0, 0.65, 0.0), 60),
    'top': ((0.0, 11.0, -0.02), (0.0, 0.0, 0.0), 45),
    'wheel': ((2.4, 0.55, 2.6), (0.76, 0.34, 1.25), 50),
    'wheelr': ((2.6, 0.55, -2.4), (0.76, 0.34, -1.25), 50),
    'low34': ((3.2, 0.55, 4.8), (0.0, 0.55, 0.6), 35),
    'interior': ((1.9, 1.55, 1.2), (0.0, 0.8, -0.2), 35),
    'nose': ((1.8, 0.9, 4.0), (0.25, 0.5, 1.9), 40),
    'tail': ((-1.8, 1.1, -4.2), (0.2, 0.75, -2.0), 40),
    'cowl': ((1.6, 1.5, 1.6), (0.5, 1.0, 0.35), 40),
    'roofc': ((1.2, 1.8, 0.9), (0.5, 1.15, -0.05), 40),
    'under': ((3.5, 0.15, 2.5), (0.0, 0.25, 0.0), 35),
}


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
    noise.inputs['Scale'].default_value = 180.0
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = K.srgb('#3a3a3b')
    ramp.color_ramp.elements[1].color = K.srgb('#5d5c5a')
    nt.links.new(noise.outputs['Fac'], ramp.inputs['Fac'])
    nt.links.new(ramp.outputs['Color'], p.inputs['Base Color'])
    bump = nt.nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.25
    nt.links.new(noise.outputs['Fac'], bump.inputs['Height'])
    nt.links.new(bump.outputs['Normal'], p.inputs['Normal'])
    p.inputs['Roughness'].default_value = 0.92
    return m


def scene(night=False, sun_elevation=40.0):
    sc = bpy.context.scene
    world = bpy.data.worlds.new('sky')
    sc.world = world
    world.use_nodes = True
    nt = world.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    bg = nt.nodes.new('ShaderNodeBackground')
    out = nt.nodes.new('ShaderNodeOutputWorld')
    nt.links.new(bg.outputs['Background'], out.inputs['Surface'])
    if night:
        bg.inputs['Color'].default_value = K.srgb('#1a2235')
        bg.inputs['Strength'].default_value = 0.6
        moon = bpy.data.objects.new('moon', bpy.data.lights.new('moon', 'SUN'))
        moon.data.energy = 0.35
        moon.data.color = (0.65, 0.75, 1.0)
        moon.rotation_euler = (math.radians(50), 0, math.radians(140))
        sc.collection.objects.link(moon)
        lamp = bpy.data.objects.new('streetlamp', bpy.data.lights.new('streetlamp', 'POINT'))
        lamp.data.energy = 1500
        lamp.data.color = (1.0, 0.82, 0.6)
        lamp.data.shadow_soft_size = 0.3
        lamp.location = K.B(3.5, 6.0, -1.0)
        sc.collection.objects.link(lamp)
    else:
        sky = nt.nodes.new('ShaderNodeTexSky')
        for kind in ('MULTIPLE_SCATTERING', 'NISHITA'):
            try:
                sky.sky_type = kind
                break
            except TypeError:
                continue
        sky.sun_elevation = math.radians(sun_elevation)
        try:
            sky.sun_disc = False
        except AttributeError:
            pass
        bg.inputs['Strength'].default_value = 0.16
        nt.links.new(sky.outputs['Color'], bg.inputs['Color'])
        sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN'))
        sun.data.energy = 4.0
        sun.data.angle = math.radians(1.0)
        sc.collection.objects.link(sun)
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
        vs.view_transform = 'Standard'
    vs.exposure = -0.4 if not night else 0.0
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.data.clip_start = 0.05
    cam.data.clip_end = 300


def light_from(eye, target, offset=40.0, elevation=40.0):
    sun = bpy.data.objects.get('sun')
    if sun is None:
        return
    dx, dz = eye[0] - target[0], eye[2] - target[2]
    theta = math.atan2(dx, dz) + math.radians(offset)
    sun.rotation_euler = (math.radians(90 - elevation), 0, theta)
    sky = bpy.context.scene.world.node_tree.nodes.get('Sky Texture')
    if sky is not None:
        sky.sun_rotation = theta + math.pi / 2


def camera(eye, target, lens, shift=(0.0, 0.0)):
    cam = bpy.context.scene.camera
    cam.location = K.B(*eye)
    cam.rotation_euler = (K.B(*target) - K.B(*eye)).to_track_quat('-Z', 'Y').to_euler()
    cam.data.lens = lens
    cam.data.shift_x, cam.data.shift_y = shift


def render(view, path, size=(1280, 720), samples=32, sun_offset=40.0):
    sc = bpy.context.scene
    eye, target, lens = VIEWS[view] if isinstance(view, str) else view
    if sun_offset is not None:
        light_from(eye, target, sun_offset)
    camera(eye, target, lens)
    sc.cycles.samples = samples
    sc.render.resolution_x, sc.render.resolution_y = size
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)


def lamps_on(mats, on=True):
    """night look: head and tail lenses glow (the game drives these from its own materials)"""
    for name, colour, s in (('headlight', '#fff4e0', 5.0), ('taillight', '#ff1a10', 3.0)):
        m = mats.mats.get(name)
        if m is None:
            continue
        p = m.node_tree.nodes['Principled BSDF']
        p.inputs['Emission Color'].default_value = K.srgb(colour)
        p.inputs['Emission Strength'].default_value = s if on else 0.0
        tex = [n for n in m.node_tree.nodes if n.type == 'TEX_IMAGE']
        if tex and on:
            mix = m.node_tree.nodes.new('ShaderNodeMixRGB')
            mix.blend_type = 'MULTIPLY'
            mix.inputs['Fac'].default_value = 1.0
            mix.inputs['Color2'].default_value = K.srgb(colour)
            m.node_tree.links.new(tex[0].outputs['Color'], mix.inputs['Color1'])
            m.node_tree.links.new(mix.outputs['Color'], p.inputs['Emission Color'])
    if on:
        # head lamp beams on the road
        for side in (1, -1):
            spot = bpy.data.objects.new(f'beam{side}', bpy.data.lights.new(f'beam{side}', 'SPOT'))
            spot.data.energy = 900
            spot.data.spot_size = math.radians(50)
            spot.data.color = (1.0, 0.95, 0.85)
            spot.location = K.B(0.62 * side, 0.62, 2.1)
            spot.rotation_euler = (K.B(0.62 * side, 0.0, 9.0) - K.B(0.62 * side, 0.62, 2.1)).to_track_quat('-Z', 'Y').to_euler()
            bpy.context.scene.collection.objects.link(spot)


def silhouette_mode():
    """flat black car on white: for outline overlays"""
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_WORKBENCH'
    sh = sc.display.shading
    sh.light = 'FLAT'
    sh.color_type = 'SINGLE'
    sh.single_color = (0, 0, 0)
    sc.world.color = (1, 1, 1)
    sh.background_type = 'WORLD' if hasattr(sh, 'background_type') else None
    g = bpy.data.objects.get('ground')
    if g is not None:
        g.hide_render = True
    sc.view_settings.view_transform = 'Standard'
    sc.view_settings.exposure = 0


def see_through(glass, opacity):
    """render only: the game draws the glass at this opacity (the GLB's glass stays opaque)"""
    nt = glass.node_tree
    p = nt.nodes['Principled BSDF']
    p.inputs['Alpha'].default_value = opacity
