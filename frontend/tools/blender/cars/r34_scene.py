"""
A check scene for the R34 (not part of the game): asphalt ground, sky and sun (Cycles, Khronos PBR Neutral), cameras
placed like the reference photos, orthographic elevations for silhouette overlays, and a night mode (dark sky, the
lamps' emission on).
"""
import math

import bmesh
import bpy

from r34_kit import B, srgb

# game frame: eye, target, lens (mm); 'ortho' views: (eye, target, ortho_scale)
VIEWS = {
    'front34': ((4.4, 1.35, 6.2), (0.0, 0.62, 0.35), 35),
    'rear34': ((-4.6, 1.55, -6.3), (0.0, 0.66, -0.35), 35),
    'side': ((-9.0, 0.75, 0.0), (0.0, 0.70, 0.0), 'o5.2'),
    'sidep': ((-7.5, 1.0, 0.0), (0.0, 0.62, 0.0), 40),
    'front': ((0.0, 0.75, 9.0), (0.0, 0.66, 0.0), 'o2.6'),
    'rear': ((0.0, 0.75, -9.0), (0.0, 0.66, 0.0), 'o2.6'),
    'top': ((-0.001, 9.0, 0.0), (0.0, 0.0, 0.0), 'o5.2'),
    'frontlow': ((2.6, 0.55, 4.4), (0.0, 0.5, 1.6), 30),
    'rearlow': ((-2.4, 0.7, -4.6), (0.0, 0.62, -1.6), 30),
    'archr': ((5.0, 0.55, -1.33), (0.0, 0.55, -1.33), 'o1.6'),
    'archr34': ((3.0, 1.0, -4.2), (0.8, 0.5, -1.5), 30),
    'archf': ((5.0, 0.55, 1.33), (0.0, 0.55, 1.33), 'o1.5'),
    'archf34': ((3.2, 1.6, 2.6), (0.8, 0.55, 1.33), 30),
    'cmp_f': ((3.3, 1.2, 4.3), (0.05, 0.58, 0.25), 24),
    'cmp_r': ((-4.2, 1.3, -3.0), (0.0, 0.62, -0.55), 24),
    'wheel': ((-2.6, 0.45, 2.4), (-0.75, 0.33, 1.33), 40),
    'interior': ((-1.7, 1.45, 0.4), (0.0, 0.85, -0.1), 30),
    'night34': ((4.8, 1.2, 7.4), (0.0, 0.55, 0.6), 32),
    'nightrear': ((-3.8, 1.3, -6.8), (0.0, 0.6, -0.8), 32),
}


def setup(night=False, exposure=-0.4):
    sc = bpy.context.scene
    world = sc.world or bpy.data.worlds.new('sky')
    sc.world = world
    world.use_nodes = True
    nt = world.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new('ShaderNodeOutputWorld')
    bg = nt.nodes.new('ShaderNodeBackground')
    if night:
        bg.inputs['Color'].default_value = srgb('#0b1020')
        bg.inputs['Strength'].default_value = 0.05
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
        nt.links.new(sky.outputs['Color'], bg.inputs['Color'])
        bg.inputs['Strength'].default_value = 0.16
    nt.links.new(bg.outputs['Background'], out.inputs['Surface'])
    if not night:
        sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN'))
        sun.data.energy = 3.6
        sun.data.angle = math.radians(1.0)
        sun.rotation_euler = (math.radians(50), 0, math.radians(-120))
        sc.collection.objects.link(sun)
    else:
        # a street lamp's glow from above and behind the camera side
        lamp = bpy.data.objects.new('lamp', bpy.data.lights.new('lamp', 'AREA'))
        lamp.data.energy = 120
        lamp.data.size = 3.0
        lamp.data.color = (1.0, 0.82, 0.6)
        lamp.location = B(3.0, 6.0, -2.0)
        lamp.rotation_euler = (0, 0, 0)
        sc.collection.objects.link(lamp)
    # asphalt
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=60)
    me = bpy.data.meshes.new('ground')
    bm.to_mesh(me)
    bm.free()
    g = bpy.data.objects.new('ground', me)
    sc.collection.objects.link(g)
    gm = bpy.data.materials.new('sc_asphalt')
    gm.use_nodes = True
    gnt = gm.node_tree
    p = gnt.nodes['Principled BSDF']
    noise = gnt.nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 180.0
    ramp = gnt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = srgb('#2e2e2f' if not night else '#141416')
    ramp.color_ramp.elements[1].color = srgb('#5a5957' if not night else '#232326')
    gnt.links.new(noise.outputs['Fac'], ramp.inputs['Fac'])
    gnt.links.new(ramp.outputs['Color'], p.inputs['Base Color'])
    p.inputs['Roughness'].default_value = 0.92
    me.materials.append(gm)
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
    vs.exposure = exposure
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.data.clip_start = 0.05
    cam.data.clip_end = 200
    cam.data.sensor_width = 36


def render(view, path, size=(1280, 720), samples=32, transparent=False):
    sc = bpy.context.scene
    cam = sc.camera
    if isinstance(view, dict):
        # a camera solved from a photo (location in the game frame, Blender euler, lens on a 36 mm wide sensor)
        cam.location = B(*view['loc'])
        cam.rotation_euler = view['euler']
        cam.data.type = 'PERSP'
        cam.data.sensor_fit = 'HORIZONTAL'
        cam.data.sensor_width = 36.0
        cam.data.lens = view['lens']
        sc.cycles.samples = samples
        sc.render.resolution_x, sc.render.resolution_y = size
        sc.render.film_transparent = transparent
        sc.render.filepath = path
        bpy.ops.render.render(write_still=True)
        return
    eye, target, lens = VIEWS[view] if isinstance(view, str) else view
    cam.location = B(*eye)
    d = B(*target) - B(*eye)
    cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    if view == 'top':
        # straight down with the car's nose to the right of the frame
        cam.rotation_euler = (0.0, 0.0, -math.pi / 2)
    if isinstance(lens, str) and lens.startswith('o'):
        cam.data.type = 'ORTHO'
        cam.data.ortho_scale = float(lens[1:])
    else:
        cam.data.type = 'PERSP'
        cam.data.lens = lens
    sc.cycles.samples = samples
    sc.render.resolution_x, sc.render.resolution_y = size
    sc.render.film_transparent = transparent
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
