"""
A check scene for the cockroach (Cycles): asphalt, sky and sun, Khronos PBR Neutral, cameras by name (game frame,
real mm; see roach_geom.S for the scale). Not part of the game.
"""
import math

import bmesh
import bpy

from roach_geom import B, S

# game frame (mm): eye, target, lens (mm, 36 mm sensor)
VIEWS = {
    'top': ((0.0, 330.0, -14.0), (0.0, 0.0, -14.0), 70),
    'side': ((125.0, 8.0, -15.0), (0.0, 4.2, -15.0), 60),
    'front34': ((70.0, 52.0, 58.0), (0.0, 3.0, -14.0), 45),
    'rear34': ((-70.0, 45.0, -95.0), (0.0, 3.0, -16.0), 45),
    'below': ((6.0, -260.0, -14.0), (0.0, 4.0, -14.0), 70),
    'head': ((26.0, 13.0, 21.0), (0.0, 3.6, -1.8), 70),
    'leg': ((38.0, 13.0, -12.0), (10.5, 3.0, -25.5), 60),
    'front': ((0.0, 12.0, 120.0), (0.0, 4.0, -10.0), 60),
    # like the reference photos: Alex Wild's dorsal (25859665686) and oblique (25765232092) shots
    'match_top': ((0.0, 260.0, -19.0), (0.0, 0.0, -19.0), 60),
    'match_34': ((95.0, 85.0, -35.0), (0.0, 3.0, -18.0), 60),
    'gait_top': ((0.0, 150.0, -14.0), (0.0, 0.0, -14.0), 60),
    'gait_side': ((105.0, 9.0, -14.0), (0.0, 3.0, -14.0), 60),
}


def _ground_material():
    m = bpy.data.materials.new('st_asphalt')
    m.use_nodes = True
    nt = m.node_tree
    p = nt.nodes['Principled BSDF']
    tc = nt.nodes.new('ShaderNodeTexCoord')
    vor = nt.nodes.new('ShaderNodeTexVoronoi')
    vor.inputs['Scale'].default_value = 90.0
    nt.links.new(tc.outputs['Object'], vor.inputs['Vector'])
    noise = nt.nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 25.0
    nt.links.new(tc.outputs['Object'], noise.inputs['Vector'])
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = (0.035, 0.035, 0.037, 1)
    ramp.color_ramp.elements[1].color = (0.11, 0.105, 0.1, 1)
    nt.links.new(noise.outputs['Fac'], ramp.inputs['Fac'])
    nt.links.new(ramp.outputs['Color'], p.inputs['Base Color'])
    bump = nt.nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.6
    bump.inputs['Distance'].default_value = 0.01
    nt.links.new(vor.outputs['Distance'], bump.inputs['Height'])
    nt.links.new(bump.outputs['Normal'], p.inputs['Normal'])
    p.inputs['Roughness'].default_value = 0.88
    return m


def scene(sun_elevation=42.0, sun_heading=-140.0, sky_strength=0.2, sun_energy=4.0, threads=4):
    sc = bpy.context.scene
    world = sc.world or bpy.data.worlds.new('sky')
    sc.world = world
    world.use_nodes = True
    nt = world.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    sky = nt.nodes.new('ShaderNodeTexSky')
    for kind in ('MULTIPLE_SCATTERING', 'NISHITA'):
        try:
            sky.sky_type = kind
            break
        except TypeError:
            continue
    sky.sun_elevation = math.radians(sun_elevation)
    sky.sun_rotation = math.radians(sun_heading)
    try:
        sky.sun_disc = False
    except AttributeError:
        pass
    bg = nt.nodes.new('ShaderNodeBackground')
    bg.inputs['Strength'].default_value = sky_strength
    out = nt.nodes.new('ShaderNodeOutputWorld')
    nt.links.new(sky.outputs['Color'], bg.inputs['Color'])
    nt.links.new(bg.outputs['Background'], out.inputs['Surface'])
    sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN'))
    sun.data.energy = sun_energy
    sun.data.angle = math.radians(1.0)
    sun.rotation_euler = (math.radians(90 - sun_elevation), 0, math.radians(sun_heading - 90))
    sc.collection.objects.link(sun)
    # a fill from below for the underside view (off otherwise)
    fill = bpy.data.objects.new('fill', bpy.data.lights.new('fill', 'AREA'))
    fill.data.energy = 0.0
    fill.data.size = 20.0
    fill.location = B(0, -120, -14)
    fill.rotation_euler = (math.pi, 0, 0)
    sc.collection.objects.link(fill)
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=60.0)
    me = bpy.data.meshes.new('ground')
    bm.to_mesh(me)
    bm.free()
    g = bpy.data.objects.new('ground', me)
    sc.collection.objects.link(g)
    me.materials.append(_ground_material())
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.use_denoising = True
    sc.render.threads_mode = 'FIXED'
    sc.render.threads = threads
    vs = sc.view_settings
    try:
        vs.view_transform = 'Khronos PBR Neutral'
    except TypeError:
        vs.view_transform = 'Filmic'
    vs.exposure = -0.3
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.data.clip_start = 0.05
    cam.data.clip_end = 400


def light_from(eye, target, offset=40.0):
    sun = bpy.data.objects.get('sun')
    dx, dz = eye[0] - target[0], eye[2] - target[2]
    if abs(dx) + abs(dz) < 1e-3:
        theta = math.radians(150)
    else:
        theta = math.atan2(dx, dz) + math.radians(offset)
    sun.rotation_euler = (sun.rotation_euler[0], 0, theta)
    sky = bpy.context.scene.world.node_tree.nodes.get('Sky Texture')
    if sky is not None:
        sky.sun_rotation = theta + math.pi / 2


def render(view, path, size=(1280, 720), samples=32, sun_offset=40.0):
    sc = bpy.context.scene
    eye, target, lens = VIEWS[view] if isinstance(view, str) else view
    below = view == 'below'
    g = bpy.data.objects.get('ground')
    g.hide_render = below
    bpy.data.objects['fill'].data.energy = 600.0 * S * S * 100 if below else 0.0
    if sun_offset is not None and not below:
        light_from(eye, target, sun_offset)
    cam = sc.camera
    cam.location = B(*eye)
    d = B(*target) - B(*eye)
    up = 'Y'
    if abs(d.normalized().z) > 0.98:
        # straight down / up: the image's up is the insect's front
        cam.rotation_euler = (0.0, 0.0, math.pi) if d.z < 0 else (math.pi, 0.0, 0.0)
    else:
        cam.rotation_euler = d.to_track_quat('-Z', up).to_euler()
    cam.data.lens = lens
    sc.cycles.samples = samples
    sc.render.resolution_x, sc.render.resolution_y = size
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
