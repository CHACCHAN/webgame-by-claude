"""
A check scene for the shiden build (not part of the game): asphalt ground, sky and sun (Cycles, Khronos PBR Neutral),
cameras in the game frame, a night variant with the lamps lit, and flat orthographic silhouettes for photo overlays.
"""
import math

import bmesh
import bpy

from shiden_surf import B


def srgb(h):
    h = h.lstrip('#')
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return (*out, 1.0)


# game frame: eye, target, lens (mm, 36 mm sensor)
VIEWS = {
    'front34': ((4.2, 1.35, 5.6), (0.0, 0.55, 0.15), 45),
    'rear34': ((-4.3, 1.45, -5.4), (0.0, 0.6, -0.2), 45),
    'side': ((9.5, 0.75, 0.0), (0.0, 0.62, 0.0), 50),
    'front': ((0.0, 0.85, 9.0), (0.0, 0.6, 0.0), 60),
    'rear': ((0.0, 0.95, -9.0), (0.0, 0.62, 0.0), 60),
    'top': ((3.2, 7.5, 0.6), (0.0, 0.4, 0.0), 45),
    'wheel': ((2.3, 0.55, 2.4), (0.75, 0.33, 1.2), 50),
    'low34': ((3.6, 0.45, 4.6), (0.0, 0.5, 0.4), 32),
    'nose': ((1.6, 0.9, 4.0), (0.25, 0.55, 1.8), 45),
    'tail': ((-1.8, 1.05, -4.2), (-0.15, 0.65, -1.9), 45),
    'cabin': ((1.3, 1.6, 1.4), (0.0, 0.8, -0.2), 38),
}


def _mat(name, colour, rough=0.9, metallic=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    p = m.node_tree.nodes['Principled BSDF']
    p.inputs['Base Color'].default_value = srgb(colour)
    p.inputs['Roughness'].default_value = rough
    p.inputs['Metallic'].default_value = metallic
    return m


def _asphalt():
    m = bpy.data.materials.new('sc_asphalt')
    m.use_nodes = True
    nt = m.node_tree
    p = nt.nodes['Principled BSDF']
    noise = nt.nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 400.0
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = srgb('#3a3a3a')
    ramp.color_ramp.elements[1].color = srgb('#6a6866')
    nt.links.new(noise.outputs['Fac'], ramp.inputs['Fac'])
    nt.links.new(ramp.outputs['Color'], p.inputs['Base Color'])
    bump = nt.nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.25
    nt.links.new(noise.outputs['Fac'], bump.inputs['Height'])
    nt.links.new(bump.outputs['Normal'], p.inputs['Normal'])
    p.inputs['Roughness'].default_value = 0.92
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
        bg.inputs['Color'].default_value = srgb('#0b1020')
        bg.inputs['Strength'].default_value = 0.25
    else:
        sky = nt.nodes.new('ShaderNodeTexSky')
        for kind in ('MULTIPLE_SCATTERING', 'NISHITA'):
            try:
                sky.sky_type = kind
                break
            except TypeError:
                continue
        sky.sun_elevation = math.radians(40)
        sky.sun_rotation = math.radians(-120)
        try:
            sky.sun_disc = False
        except AttributeError:
            pass
        bg.inputs['Strength'].default_value = 0.15
        nt.links.new(sky.outputs['Color'], bg.inputs['Color'])
    nt.links.new(bg.outputs['Background'], out.inputs['Surface'])
    if not night:
        sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN'))
        sun.data.energy = 4.0
        sun.data.angle = math.radians(1.0)
        sun.rotation_euler = (math.radians(50), 0, math.radians(-30))
        sc.collection.objects.link(sun)
    else:
        moon = bpy.data.objects.new('moon', bpy.data.lights.new('moon', 'SUN'))
        moon.data.energy = 0.08
        moon.data.color = (0.6, 0.7, 1.0)
        moon.rotation_euler = (math.radians(55), 0, math.radians(140))
        sc.collection.objects.link(moon)
        # a street light above and behind
        lamp = bpy.data.objects.new('streetlamp', bpy.data.lights.new('streetlamp', 'POINT'))
        lamp.data.energy = 900
        lamp.data.color = (1.0, 0.8, 0.55)
        lamp.data.shadow_soft_size = 0.3
        lamp.location = B(-3.5, 6.0, -3.0)
        sc.collection.objects.link(lamp)
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
    vs.exposure = -0.6 if not night else 0.0
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.data.clip_start = 0.05
    cam.data.clip_end = 300


def light_from(eye, target, offset=40.0):
    sun = bpy.data.objects.get('sun')
    if sun is None:
        return
    dx, dz = eye[0] - target[0], eye[2] - target[2]
    theta = math.atan2(dx, dz) + math.radians(offset)
    sun.rotation_euler = (math.radians(48), 0, theta)
    sky = bpy.context.scene.world.node_tree.nodes.get('Sky Texture')
    if sky is not None:
        sky.sun_rotation = theta + math.pi / 2


def render(view, path, size=(1280, 720), samples=32, ortho=None, sun_offset=40.0):
    sc = bpy.context.scene
    eye, target, lens = VIEWS[view] if isinstance(view, str) else view
    if sun_offset is not None:
        light_from(eye, target, sun_offset)
    cam = sc.camera
    cam.location = B(*eye)
    cam.rotation_euler = (B(*target) - B(*eye)).to_track_quat('-Z', 'Y').to_euler()
    if ortho:
        cam.data.type = 'ORTHO'
        cam.data.ortho_scale = ortho
    else:
        cam.data.type = 'PERSP'
        cam.data.lens = lens
    sc.cycles.samples = samples
    sc.render.resolution_x, sc.render.resolution_y = size
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)


def silhouette(path, view, size=(1600, 600), ortho=4.8):
    """flat orthographic mask (car white on black) for overlays: view = 'side' | 'front' | 'rear' | 'top'"""
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_WORKBENCH'
    sh = sc.display.shading
    sh.light = 'FLAT'
    sh.color_type = 'SINGLE'
    sh.single_color = (1, 1, 1)
    sh.background_type = 'VIEWPORT'
    sh.background_color = (0, 0, 0)
    sc.view_settings.view_transform = 'Standard'
    try:
        sc.display.render_aa = 'OFF'
    except TypeError:
        pass
    g = bpy.data.objects.get('ground')
    if g:
        g.hide_render = True
    eyes = {'side': ((20, 0.6, 0), (0, 0.6, 0)), 'front': ((0, 0.6, 20), (0, 0.6, 0)),
            'rear': ((0, 0.6, -20), (0, 0.6, 0)), 'top': ((0, 20, 0.0), (0, 0, 0.0))}
    eye, target = eyes[view]
    cam = sc.camera
    cam.location = B(*eye)
    if view == 'top':
        cam.rotation_euler = (0, 0, 0)
    else:
        cam.rotation_euler = (B(*target) - B(*eye)).to_track_quat('-Z', 'Y').to_euler()
    cam.data.type = 'ORTHO'
    cam.data.ortho_scale = ortho
    sc.render.resolution_x, sc.render.resolution_y = size
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
