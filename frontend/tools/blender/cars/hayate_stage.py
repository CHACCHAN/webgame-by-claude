"""
A check scene for the car (not part of the game): asphalt ground, sky and sun (Cycles, Khronos PBR Neutral), cameras
placed like the reference photos, a night mode with the lamps lit, and orthographic views for silhouette overlays.
"""
import math

import bmesh
import bpy
from mathutils import Vector

import hayate_kit as K

# game frame: eye, target, lens (mm, 36 mm sensor); 'ortho_*': (eye, target, ortho scale)
VIEWS = {
    'front34': ((3.9, 1.25, 5.6), (0.0, 0.55, 0.35), 40),
    'rear34': ((-3.9, 1.35, -5.8), (0.0, 0.55, -0.3), 40),
    'side': ((9.0, 0.75, 0.0), (0.0, 0.62, 0.0), 50),
    'front': ((0.0, 0.85, 9.0), (0.0, 0.62, 0.0), 60),
    'rear': ((0.0, 0.95, -9.0), (0.0, 0.62, 0.0), 60),
    'top': ((3.2, 5.2, 0.6), (0.0, 0.5, 0.0), 32),
    'wheel': ((1.75, 0.45, 2.15), (0.75, 0.32, 1.2), 50),
    'pod': ((2.0, 1.45, 3.7), (0.45, 0.78, 1.75), 45),
    'low': ((2.6, 0.35, 4.6), (0.0, 0.55, 0.6), 30),
    'interior': ((1.6, 1.45, 0.2), (0.0, 0.85, 0.0), 30),
    'under': ((3.0, -0.6, 3.5), (0.0, 0.3, 0.0), 30),
    # solved from points picked on Commons "Toyota SPRINTER TRUENO 3door (AE86) front.JPG" (render at 960 x 719)
    'cpil': ((2.4, 1.8, -3.0), (0.62, 1.12, -1.35), 45),
    'cpil_r': ((-1.4, 1.7, -4.6), (-0.55, 1.1, -1.5), 45),
    'hatch': ((-2.3, 2.1, -4.4), (0.0, 1.0, -1.7), 40),
    'p04': ((2.2202, 1.574, 5.4189), (0.0522, 0.5903, 1.0221), 53.79),
    # ... "1986 Toyota Sprinter Trueno 3-door GT APEX.jpg" (960 x 588) and the rear photo 06 (render at 960 x 725)
    'p03': ((2.6131, 1.7997, 5.6356), (0.2758, 0.757, 1.3403), 60.97),
    'p06': ((-0.0484, 1.2243, -3.8504), (0.0607, -0.1067, 0.968), 39.57),
}
ORTHO = {
    'o_side': ((8.0, 0.65, 0.0), (0.0, 0.65, 0.0), 4.8),
    'o_front': ((0.0, 0.65, 8.0), (0.0, 0.65, 0.0), 2.0),
    'o_rear': ((0.0, 0.65, -8.0), (0.0, 0.65, 0.0), 2.0),
    'o_top': ((0.0, 8.0, 0.0), (0.0, 0.0, 0.0), 4.8),
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
    m = bpy.data.materials.new('st_asphalt')
    m.use_nodes = True
    nt = m.node_tree
    p = nt.nodes['Principled BSDF']
    noise = nt.nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 180.0
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = K.srgb('#3a3a3c')
    ramp.color_ramp.elements[1].color = K.srgb('#68676a')
    nt.links.new(noise.outputs['Fac'], ramp.inputs['Fac'])
    nt.links.new(ramp.outputs['Color'], p.inputs['Base Color'])
    bump = nt.nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.3
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
        bg.inputs['Color'].default_value = K.srgb('#0b0f1c')
        bg.inputs['Strength'].default_value = 0.35
    else:
        sky = nt.nodes.new('ShaderNodeTexSky')
        for kind in ('MULTIPLE_SCATTERING', 'NISHITA'):
            try:
                sky.sky_type = kind
                break
            except TypeError:
                continue
        sky.sun_elevation = math.radians(40)
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
        sun.rotation_euler = (math.radians(50), 0, 0)
        sc.collection.objects.link(sun)
    # ground
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
    cam.data.clip_start = 0.02
    cam.data.clip_end = 200


def light_from(eye, target, offset=40.0, elevation=42.0):
    sun = bpy.data.objects.get('sun')
    if sun is None:
        return
    dx, dz = eye[0] - target[0], eye[2] - target[2]
    theta = math.atan2(dx, dz) + math.radians(offset)
    sun.rotation_euler = (math.radians(90 - elevation), 0, theta)
    sky = bpy.context.scene.world.node_tree.nodes.get('Sky Texture')
    if sky is not None:
        sky.sun_rotation = theta + math.pi / 2


def render(view, path, size=(1280, 720), samples=32, sun_offset=40.0, transparent=False):
    sc = bpy.context.scene
    cam = sc.camera
    if isinstance(view, str) and view in ORTHO:
        eye, target, scale = ORTHO[view]
        cam.data.type = 'ORTHO'
        cam.data.ortho_scale = scale * 2
    else:
        eye, target, lens = VIEWS[view] if isinstance(view, str) else view
        cam.data.type = 'PERSP'
        cam.data.lens = lens
    if sun_offset is not None:
        light_from(eye, target, sun_offset)
    cam.location = K.B(*eye)
    up = 'Y' if abs(eye[1] - target[1]) < 0.9 * (Vector(eye) - Vector(target)).length else 'Y'
    d = K.B(*target) - K.B(*eye)
    if abs(d.normalized().z) > 0.99:
        cam.rotation_euler = (0, 0, 0) if d.z < 0 else (math.pi, 0, 0)
        cam.rotation_euler = d.to_track_quat('-Z', 'X').to_euler()
        cam.rotation_euler.z += math.pi / 2
    else:
        cam.rotation_euler = d.to_track_quat('-Z', up).to_euler()
    sc.cycles.samples = samples
    sc.render.resolution_x, sc.render.resolution_y = size
    sc.render.film_transparent = transparent
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
