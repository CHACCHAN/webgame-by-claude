"""
A trackside scene for looking at our train models in Blender (Cycles): ballast, sleepers and rails, sky and sun, and
cameras placed like the reference photos. Not part of the game; used to check a model and to show it to the owner.

  import showcase as S
  S.scene()                       # after the cars are built (car0 leads at z = 0, the others behind it)
  S.render('hero', '/tmp/x.png')  # views: see VIEWS
"""
import math

import bmesh
import bpy
from mathutils import Vector

import train_kit as K

# game frame: eye, target, lens (mm, 36 mm sensor)
VIEWS = {
    # like Commons "Keikyu-Type1000-009.jpg": the train comes round a curve, seen from ahead and to its right, long lens
    'hero': ((-7.5, 3.4, 34.0), (0.2, 1.9, -4.0), 85),
    # like "KEIKYU N1000 SERIES 1001-.jpg": head-on from a platform
    'head': ((0.25, 2.45, 24.0), (0.0, 1.95, 8.8), 105),
    'front34': ((5.2, 2.0, 15.5), (0.0, 1.8, 6.0), 40),
    'side': ((14.0, 1.6, -2.0), (0.0, 1.8, -2.0), 35),
    'low': ((6.0, 0.9, 13.0), (0.0, 1.3, 3.0), 30),
    'bogie': ((3.2, 0.75, 9.0), (0.0, 0.55, 5.6), 35),
    'roof': ((8.5, 8.0, -4.0), (0.0, 3.4, -20.0), 40),
    'rear34': ((-5.5, 2.6, -62.0), (0.0, 1.9, -40.0), 50),
    'skirt': ((1.2, 0.9, 12.5), (0.0, 0.7, 8.8), 50),
    # for side-by-side sheets with the reference photos 08 (long lens from the right, ahead) and 02 (head-on)
    'match08': ((-5.0, 3.6, 46.0), (-0.9, 1.9, 2.0), 150),
    'match02': ((0.25, 2.55, 30.0), (0.0, 2.0, 8.9), 135),
}


def _mat(name, colour, rough=0.9, metallic=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    p = m.node_tree.nodes['Principled BSDF']
    p.inputs['Base Color'].default_value = K.srgb(colour)
    p.inputs['Roughness'].default_value = rough
    p.inputs['Metallic'].default_value = metallic
    return m


def _ballast_material():
    m = bpy.data.materials.new('sc_ballast')
    m.use_nodes = True
    nt = m.node_tree
    p = nt.nodes['Principled BSDF']
    vor = nt.nodes.new('ShaderNodeTexVoronoi')
    vor.inputs['Scale'].default_value = 28.0
    noise = nt.nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 60.0
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = K.srgb('#4a3f36')
    ramp.color_ramp.elements[1].color = K.srgb('#8f8072')
    nt.links.new(noise.outputs['Fac'], ramp.inputs['Fac'])
    nt.links.new(ramp.outputs['Color'], p.inputs['Base Color'])
    bump = nt.nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.8
    nt.links.new(vor.outputs['Distance'], bump.inputs['Height'])
    nt.links.new(bump.outputs['Normal'], p.inputs['Normal'])
    p.inputs['Roughness'].default_value = 0.95
    return m


def _mesh(name, part_fn, mats):
    bm = bmesh.new()
    part_fn(bm)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    return o


def _box(bm, x0, x1, y0, y1, z0, z1):
    r = bmesh.ops.create_cube(bm, size=1.0)
    for v in r['verts']:
        v.co = K.B(v.co.x * (x1 - x0) + (x0 + x1) / 2, v.co.y * (y1 - y0) + (y0 + y1) / 2, v.co.z * (z1 - z0) + (z0 + z1) / 2)
    return r


def scene(sun_elevation=38.0, sun_heading=-150.0, z0=-75.0, z1=45.0, sky_strength=0.15, sun_energy=4.0):
    """the trackside: call after the train is built"""
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
    # sun lamp along the sky's sun
    sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN'))
    sun.data.energy = sun_energy
    sun.data.angle = math.radians(0.6)
    sun.rotation_euler = (math.radians(90 - sun_elevation), 0, math.radians(sun_heading - 90))
    sc.collection.objects.link(sun)
    # ground, ballast bed, sleepers, rails
    ground = _mat('sc_ground', '#5f5a48', 0.95)
    ballast = _ballast_material()
    concrete = _mat('sc_sleeper', '#a29f97', 0.85)
    steel = _mat('sc_rail', '#6b625b', 0.55, 0.6)
    head = _mat('sc_railhead', '#c9c6c2', 0.25, 1.0)

    def ground_fn(bm):
        for v in [(-60, -0.55, z0 - 40), (60, -0.55, z0 - 40), (60, -0.55, z1 + 60), (-60, -0.55, z1 + 60)]:
            bm.verts.new(K.B(*v))
        bm.faces.new(bm.verts)
    _mesh('ground', ground_fn, [ground])

    def bed_fn(bm):
        prof = [(-2.6, -0.55), (-1.55, -0.20), (1.55, -0.20), (2.6, -0.55)]
        ring0 = [bm.verts.new(K.B(x, y, z0 - 20)) for x, y in prof]
        ring1 = [bm.verts.new(K.B(x, y, z1 + 30)) for x, y in prof]
        for i in range(3):
            bm.faces.new([ring0[i], ring0[i + 1], ring1[i + 1], ring1[i]])
    bed = _mesh('ballast', bed_fn, [ballast])
    bed.data.polygons.foreach_set('use_smooth', [False] * len(bed.data.polygons))

    def sleepers_fn(bm):
        z = z0 - 15
        while z < z1 + 25:
            _box(bm, -1.2, 1.2, -0.34, -0.17, z - 0.1, z + 0.1)
            z += 0.6
    _mesh('sleepers', sleepers_fn, [concrete])

    def rails_fn(bm):
        for s in (-1, 1):
            x = s * (0.7175 + 0.0325)
            _box(bm, x - 0.0325, x + 0.0325, -0.045, 0.0, z0 - 15, z1 + 25)
            _box(bm, x - 0.009, x + 0.009, -0.13, -0.045, z0 - 15, z1 + 25)
            _box(bm, x - 0.065, x + 0.065, -0.17, -0.13, z0 - 15, z1 + 25)
    rails = _mesh('rails', rails_fn, [steel])

    def heads_fn(bm):
        for s in (-1, 1):
            x = s * (0.7175 + 0.0325)
            vs = [bm.verts.new(K.B(*v)) for v in [(x - 0.03, 0.0005, z0 - 15), (x + 0.03, 0.0005, z0 - 15), (x + 0.03, 0.0005, z1 + 25), (x - 0.03, 0.0005, z1 + 25)]]
            f = bm.faces.new(vs)
            if f.normal.z < 0:
                f.normal_flip()
    _mesh('railheads', heads_fn, [head])
    # render settings
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.use_denoising = True
    sc.render.threads_mode = 'FIXED'
    sc.render.threads = 8
    grade()
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.data.clip_start = 0.05
    cam.data.clip_end = 400


def grade(transform='Khronos PBR Neutral', look='None', exposure=-0.5):
    """the colour management (view transform, look, exposure)"""
    vs = bpy.context.scene.view_settings
    try:
        vs.view_transform = transform
        vs.look = look
    except TypeError:
        vs.view_transform = 'Filmic'
    vs.exposure = exposure


def light_from(eye, target, offset=35.0, elevation=None):
    """turn the sun (lamp and sky) to shine from `offset` degrees beside the camera's bearing"""
    sun = bpy.data.objects.get('sun')
    if sun is None:
        return
    dx, dz = eye[0] - target[0], eye[2] - target[2]
    theta = math.atan2(dx, dz) + math.radians(offset)       # the sun's bearing in the game frame (0 = +z)
    elev = sun.rotation_euler[0] if elevation is None else math.radians(90 - elevation)
    sun.rotation_euler = (elev, 0, theta)
    sky = bpy.context.scene.world.node_tree.nodes.get('Sky Texture')
    if sky is not None:
        sky.sun_rotation = theta + math.pi / 2


def headlamps(on, material='kb_lamp', strength=40.0):
    """light the head lamps' material (the real trains run with them on by day); the GLB's lamp stays unlit"""
    m = bpy.data.materials.get(material)
    if m is None:
        return
    p = m.node_tree.nodes.get('Principled BSDF')
    p.inputs['Emission Color'].default_value = (1.0, 0.93, 0.82, 1.0)
    p.inputs['Emission Strength'].default_value = strength if on else 0.0


def render(view, path, size=(1600, 900), samples=96, sun_offset=35.0):
    sc = bpy.context.scene
    eye, target, lens = VIEWS[view] if isinstance(view, str) else view
    if sun_offset is not None:
        light_from(eye, target, sun_offset)
    cam = sc.camera
    cam.location = K.B(*eye)
    cam.rotation_euler = (K.B(*target) - K.B(*eye)).to_track_quat('-Z', 'Y').to_euler()
    cam.data.lens = lens
    sc.cycles.samples = samples
    sc.render.resolution_x, sc.render.resolution_y = size
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
