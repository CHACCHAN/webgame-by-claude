"""
Check renders for the F-15 (not part of the game): an apron under a morning sky in Cycles, quick Workbench renders
for the shape, and orthographic outlines (side, top, front) to lay over the measurements.
"""
import math
import os

import bmesh
import bpy

import jet_kit as K

# game frame: eye, target, lens (mm, 36 mm sensor)
VIEWS = {
    'front34': ((13.5, 5.2, 19.0), (0.0, 2.3, 0.6), 50),
    'rear34': ((13.5, 6.0, -20.5), (0.0, 2.3, -1.6), 50),
    'side': ((40.0, 2.6, -0.4), (0.0, 2.9, -0.4), 62),
    'top': ((0.01, 44.0, -0.4), (0.0, 0.0, -0.4), 62),
    'front': ((0.0, 2.6, 34.0), (0.0, 2.9, 0.0), 85),
    'under': ((9.0, -7.5, 9.0), (0.0, 2.2, -0.6), 35),
    'cockpit': ((3.4, 4.3, 6.6), (0.0, 3.2, 3.7), 60),
    'gear': ((5.2, 1.1, 2.2), (0.6, 1.1, -1.2), 45),
    'nozzles': ((4.6, 3.6, -13.6), (0.0, 2.2, -8.0), 50),
    'intake': ((4.2, 1.9, 8.2), (0.9, 2.1, 2.6), 50),
    'tail': ((7.5, 6.0, -15.0), (1.2, 3.6, -8.0), 60),
}
ORTHO = {
    # name: (eye, target, scale m across the picture, size px)
    'o_side': ((60.0, 3.0, -0.385), (0.0, 3.0, -0.385), 21.0, (2100, 700)),
    'o_top': ((0.0, 60.0, -0.385), (0.0, 0.0, -0.385), 21.0, (2100, 1400)),
    'o_front': ((0.0, 3.0, 60.0), (0.0, 3.0, 0.0), 14.0, (1400, 700)),
}


def _ground():
    m = bpy.data.materials.new('sc_apron')
    m.use_nodes = True
    nt = m.node_tree
    p = nt.nodes['Principled BSDF']
    noise = nt.nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 40.0
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = K.srgb('#77756f')
    ramp.color_ramp.elements[1].color = K.srgb('#8e8c85')
    nt.links.new(noise.outputs['Fac'], ramp.inputs['Fac'])
    nt.links.new(ramp.outputs['Color'], p.inputs['Base Color'])
    p.inputs['Roughness'].default_value = 0.9
    return m


def camera():
    sc = bpy.context.scene
    if sc.camera is None:
        cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
        sc.collection.objects.link(cam)
        sc.camera = cam
        cam.data.clip_start = 0.1
        cam.data.clip_end = 500
    return sc.camera


def place(view):
    eye, target, lens = VIEWS[view] if isinstance(view, str) else view
    cam = camera()
    cam.location = K.B(*eye)
    d = K.B(*target) - K.B(*eye)
    cam.rotation_euler = d.to_track_quat('-Z', 'Y' if abs(d.normalized().z) < 0.999 else 'Y').to_euler()
    cam.data.type = 'PERSP'
    cam.data.lens = lens
    cam.data.sensor_width = 36
    cam.data.sensor_fit = 'HORIZONTAL'
    return eye, target


def studio(flat=False):
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_WORKBENCH'
    sh = sc.display.shading
    sh.light = 'FLAT' if flat else 'STUDIO'
    sh.color_type = 'SINGLE' if flat else 'MATERIAL'
    if flat:
        sh.single_color = (0, 0, 0)
    sh.show_cavity = not flat
    if not flat:
        sh.cavity_type = 'BOTH'
    sh.show_specular_highlight = not flat
    sh.background_type = 'VIEWPORT'
    sh.background_color = (1, 1, 1) if flat else (0.42, 0.44, 0.47)
    sc.display.render_aa = 'OFF' if flat else '8'
    sc.view_settings.view_transform = 'Standard'
    for m in bpy.data.materials:
        if m.node_tree:
            p = m.node_tree.nodes.get('Principled BSDF')
            if p:
                c = p.inputs['Base Color'].default_value
                m.diffuse_color = (c[0], c[1], c[2], 1)
                m.metallic = min(0.6, p.inputs['Metallic'].default_value)
                m.roughness = p.inputs['Roughness'].default_value


def workbench(views, outdir, size=(1600, 900)):
    sc = bpy.context.scene
    studio()
    sc.render.resolution_x, sc.render.resolution_y = size
    sc.render.resolution_percentage = 100
    for v in views:
        place(v)
        sc.render.filepath = os.path.join(outdir, f'{v}.png')
        bpy.ops.render.render(write_still=True)


def outlines(outdir):
    """black on white, orthographic: the pixel scale is known (ORTHO), so a picture can be measured"""
    sc = bpy.context.scene
    studio(flat=True)
    cam = camera()
    for name, (eye, target, scale, size) in ORTHO.items():
        place((eye, target, 50))
        cam.data.type = 'ORTHO'
        cam.data.ortho_scale = scale
        sc.render.resolution_x, sc.render.resolution_y = size
        sc.render.resolution_percentage = 100
        sc.render.filepath = os.path.join(outdir, f'{name}.png')
        bpy.ops.render.render(write_still=True)
    cam.data.type = 'PERSP'


def apron(night=False):
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
        sky.sun_elevation = math.radians(32)
        sky.sun_rotation = math.radians(-150)
        try:
            sky.sun_disc = False
        except AttributeError:
            pass
        bg.inputs['Strength'].default_value = 0.16
        nt.links.new(sky.outputs['Color'], bg.inputs['Color'])
        sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN'))
        sun.data.energy = 4.0
        sun.data.angle = math.radians(1.5)
        sun.rotation_euler = (math.radians(52), 0, math.radians(-120))
        sc.collection.objects.link(sun)
    nt.links.new(bg.outputs['Background'], out.inputs['Surface'])
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=300)
    me = bpy.data.meshes.new('ground')
    bm.to_mesh(me)
    g = bpy.data.objects.new('ground', me)
    sc.collection.objects.link(g)
    me.materials.append(_ground())
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.use_denoising = True
    sc.render.threads_mode = 'FIXED'
    sc.render.threads = 6
    vs = sc.view_settings
    try:
        vs.view_transform = 'Khronos PBR Neutral'
    except TypeError:
        vs.view_transform = 'Filmic'
    vs.exposure = -0.5 if not night else 0.0
    return g


def sun_for(eye, target, offset=40.0, elevation=40.0):
    sun = bpy.data.objects.get('sun')
    if sun is None:
        return
    dx, dz = eye[0] - target[0], eye[2] - target[2]
    theta = math.atan2(dx, dz) + math.radians(offset)
    sun.rotation_euler = (math.radians(90 - elevation), 0, theta)


def see_through():
    """the canopy for a render (in the game the glass is the game's own material)"""
    m = bpy.data.materials.get('glass')
    if m is not None and m.node_tree:
        p = m.node_tree.nodes.get('Principled BSDF')
        p.inputs['Base Color'].default_value = (0.03, 0.035, 0.04, 1)
        p.inputs['Roughness'].default_value = 0.03
        p.inputs['Alpha'].default_value = 0.25
    # by day the lamps are off (the game lights them at night)
    a = bpy.data.materials.get('airframe')
    if a is not None and a.node_tree:
        a.node_tree.nodes.get('Principled BSDF').inputs['Emission Strength'].default_value = 0.0


def cycles(views, outdir, size=(1600, 900), samples=40):
    sc = bpy.context.scene
    see_through()
    for v in views:
        eye, target = place(v)
        # from under the ground: no ground, and the sun shines up (a picture of the underside, not of a place)
        below = eye[1] < 0
        g = bpy.data.objects.get('ground')
        if g is not None:
            g.hide_render = below
        sun_for(eye, target, elevation=-35.0 if below else 40.0)
        sc.cycles.samples = samples
        sc.render.resolution_x, sc.render.resolution_y = size
        sc.render.resolution_percentage = 100
        sc.render.filepath = os.path.join(outdir, f'{v}.png')
        bpy.ops.render.render(write_still=True)


def render_all(root, outdir, views=None, quick=False, seats=1, size=(1600, 900), samples=40):
    os.makedirs(outdir, exist_ok=True)
    names = views or list(VIEWS)
    if quick:
        workbench(names, outdir, size)
        outlines(outdir)
    else:
        apron()
        cycles(names, outdir, size, samples)


