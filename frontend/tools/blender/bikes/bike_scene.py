"""
Check renders for the motorcycles (not part of the game): a Cycles scene (asphalt, sky, sun; a night set-up with the
lamps lit), Workbench renders for quick looks, and the fit renders from solved photo cameras (silhouette, material ids,
grey shading; the front wheel steered like the photo's, the rider hidden).
"""
import json
import math
import os

import bmesh
import bpy
from mathutils import Matrix, Vector

import bike_kit as K

# game frame: eye, target, lens (mm, 36 mm sensor)
VIEWS = {
    'side': ((-7.5, 0.80, 0.0), (0.0, 0.72, 0.0), 75),
    'side_l': ((7.5, 0.80, 0.0), (0.0, 0.72, 0.0), 75),
    'front34': ((-3.6, 1.35, 4.2), (0.0, 0.70, 0.05), 50),
    'rear34': ((-3.6, 1.55, -4.2), (0.0, 0.70, -0.1), 50),
    'front34_l': ((3.6, 1.35, 4.2), (0.0, 0.70, 0.05), 50),
    'rear34_l': ((3.6, 1.55, -4.2), (0.0, 0.70, -0.1), 50),
    'front': ((0.0, 0.85, 7.0), (0.0, 0.62, 0.0), 100),
    'rear': ((0.0, 0.95, -7.0), (0.0, 0.62, 0.0), 100),
    'top': ((0.0, 7.0, 0.01), (0.0, 0.5, 0.0), 50),
    'rider': ((-2.2, 1.55, 1.2), (0.0, 1.02, -0.1), 45),
    'lamp': ((-0.9, 0.95, 2.3), (0.0, 0.80, 0.65), 40),
    'tail': ((-0.8, 1.15, -2.2), (0.0, 0.85, -0.75), 40),
    'metal': ((-1.9, 1.05, -0.75), (0.0, 0.50, -0.25), 40),       # frame, swingarm, exhaust, rear wheel: the metal parts
    'metal_f': ((-1.5, 0.95, 1.9), (0.0, 0.45, 0.55), 40),        # forks, discs, calipers
}


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
        # two large soft panels high on either side: the metal parts need something bright to reflect besides the sky
        for name, at, energy in (('panel_a', (-3.5, 3.2, 2.5), 900.0), ('panel_b', (3.0, 3.6, -3.0), 700.0)):
            pl = bpy.data.objects.new(name, bpy.data.lights.new(name, 'AREA'))
            pl.data.shape = 'RECTANGLE'
            pl.data.size, pl.data.size_y = 4.0, 1.6
            pl.data.energy = energy
            pl.location = K.B(*at)
            pl.rotation_euler = (K.B(0.0, 0.6, 0.0) - K.B(*at)).to_track_quat('-Z', 'Y').to_euler()
            sc.collection.objects.link(pl)
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
    sc.render.threads = 6
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


def light_from(eye, target, offset=40.0, elevation=42.0):
    sun = bpy.data.objects.get('sun')
    if sun is None:
        return
    dx, dz = eye[0] - target[0], eye[2] - target[2]
    theta = math.atan2(dx, dz) + math.radians(offset)
    sun.rotation_euler = (math.radians(90 - elevation), 0, theta)


def place_camera(view):
    sc = bpy.context.scene
    eye, target, lens = VIEWS[view] if isinstance(view, str) else view
    cam = sc.camera
    cam.location = K.B(*eye)
    cam.rotation_euler = (K.B(*target) - K.B(*eye)).to_track_quat('-Z', 'Y').to_euler()
    cam.data.type = 'PERSP'
    cam.data.lens = lens
    cam.data.sensor_width = 36
    cam.data.sensor_fit = 'HORIZONTAL'
    return eye, target


def render(view, path, size=(1280, 720), samples=32, sun_offset=40.0):
    sc = bpy.context.scene
    eye, target = place_camera(view)
    if sun_offset is not None:
        light_from(eye, target, sun_offset)
    sc.cycles.samples = samples
    sc.render.resolution_x, sc.render.resolution_y = size
    sc.render.resolution_percentage = 100
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)


def workbench(views, outdir, size=(1280, 720)):
    """quick grey studio renders (Workbench, seconds each)"""
    sc = bpy.context.scene
    if sc.camera is None:
        cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
        sc.collection.objects.link(cam)
        sc.camera = cam
    sc.render.engine = 'BLENDER_WORKBENCH'
    sc.render.film_transparent = False
    sh = sc.display.shading
    sh.light = 'STUDIO'
    sh.color_type = 'MATERIAL'
    sh.show_cavity = True
    sh.cavity_type = 'BOTH'
    sh.show_specular_highlight = True
    sh.background_type = 'VIEWPORT'
    sh.background_color = (0.42, 0.44, 0.47)
    sc.display.render_aa = '8'
    sc.view_settings.view_transform = 'Standard'
    for m in bpy.data.materials:
        if m.node_tree:
            p = m.node_tree.nodes.get('Principled BSDF')
            if p:
                c = p.inputs['Base Color'].default_value
                m.diffuse_color = (c[0], c[1], c[2], 1)
                m.metallic = min(0.6, p.inputs['Metallic'].default_value)
                m.roughness = p.inputs['Roughness'].default_value
    sc.render.resolution_x, sc.render.resolution_y = size
    sc.render.resolution_percentage = 100
    os.makedirs(outdir, exist_ok=True)
    for v in views:
        place_camera(v)
        sc.render.filepath = os.path.join(outdir, f'{v}.png')
        bpy.ops.render.render(write_still=True)


def night_lights(mats, lamps):
    for name, strength in (('headlight', 8.0), ('taillight', 5.0)):
        if name not in mats:
            continue
        nt = mats[name].node_tree
        p = nt.nodes['Principled BSDF']
        p.inputs['Emission Color'].default_value = p.inputs['Base Color'].default_value if name == 'taillight' else (1, 0.97, 0.9, 1)
        p.inputs['Emission Strength'].default_value = strength
        # a textured lens glows through its texture, as in the game (emissive map = the lens map)
        if p.inputs['Base Color'].is_linked:
            tex = p.inputs['Base Color'].links[0].from_node
            mix = nt.nodes.new('ShaderNodeMix')
            mix.data_type = 'RGBA'
            mix.blend_type = 'MULTIPLY'
            mix.inputs['Factor'].default_value = 1.0
            nt.links.new(tex.outputs['Color'], mix.inputs['A'])
            mix.inputs['B'].default_value = (1, 0.97, 0.9, 1)
            nt.links.new(mix.outputs['Result'], p.inputs['Emission Color'])
    sc = bpy.context.scene
    if 'headlight' in lamps:
        c = lamps['headlight'][0]
        l = bpy.data.objects.new('beam', bpy.data.lights.new('beam', 'SPOT'))
        l.data.energy = 700
        l.data.spot_size = math.radians(60)
        l.data.spot_blend = 0.6
        l.data.shadow_soft_size = 0.05
        l.location = K.B(c[0], c[1], c[2] + 0.06)
        l.rotation_euler = (math.radians(-84), 0, 0)
        sc.collection.objects.link(l)
    if 'taillight' in lamps:
        c = lamps['taillight'][0]
        l = bpy.data.objects.new('tailglow', bpy.data.lights.new('tailglow', 'POINT'))
        l.data.energy = 4
        l.data.color = (1.0, 0.1, 0.08)
        l.data.shadow_soft_size = 0.05
        l.location = K.B(c[0], c[1], c[2] - 0.08)
        sc.collection.objects.link(l)
    st = bpy.data.objects.new('street', bpy.data.lights.new('street', 'AREA'))
    st.data.energy = 500
    st.data.size = 1.0
    st.data.color = (1.0, 0.85, 0.65)
    st.location = K.B(-2.5, 6.0, -1.0)
    sc.collection.objects.link(st)


# ---------------------------------------------------------------- fit renders from solved photo cameras

def _basis(yaw, pitch, roll):
    d = Vector((math.sin(yaw) * math.cos(pitch), math.sin(pitch), math.cos(yaw) * math.cos(pitch)))
    r = d.cross(Vector((0, 1, 0))).normalized()
    u = r.cross(d)
    c, s = math.cos(roll), math.sin(roll)
    return d, c * r + s * u, -s * r + c * u


def fit_renders(root, cams_path, names, outdir, shade=True, palette_seed=7):
    """per photo: <n>_sil.png (white on alpha), <n>_ids.png (flat material colours), <n>_shade.png (grey studio)"""
    import random
    C = json.load(open(cams_path))
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_WORKBENCH'
    sc.render.film_transparent = True
    sc.view_settings.view_transform = 'Standard'
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_mode = 'RGBA'
    sh = sc.display.shading
    cam = bpy.data.objects.new('silcam', bpy.data.cameras.new('silcam'))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.data.clip_start = 0.05
    cam.data.clip_end = 1000
    cam.data.sensor_fit = 'HORIZONTAL'
    cam.data.sensor_width = 36
    random.seed(palette_seed)
    keep = {m.name: tuple(m.diffuse_color) for m in bpy.data.materials}
    palette = {m.name: (random.random(), random.random(), random.random(), 1) for m in sorted(bpy.data.materials, key=lambda m: m.name)}
    rider = bpy.data.objects.get('rider')
    hidden = []
    if rider is not None:
        for o in [rider] + list(rider.children_recursive):
            o.hide_render = True
            hidden.append(o)
    steer = bpy.data.objects.get('steer')
    s0 = steer.matrix_basis.copy() if steer else None
    os.makedirs(outdir, exist_ok=True)
    enc = lambda c: int(round(255 * (12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055)))
    json.dump({k: [enc(v) for v in col[:3]] for k, col in palette.items()}, open(os.path.join(outdir, 'palette.json'), 'w'))
    for n in names:
        c = C['cams'][n]
        W, H = c[7]
        d, r, u = _basis(*c[3:6])
        cam.matrix_world = Matrix.Translation(K.B(*c[:3])) @ Matrix((K.B(*r), K.B(*u), -K.B(*d))).transposed().to_4x4()
        cam.data.lens = c[6] * 36 / W
        sc.render.resolution_x, sc.render.resolution_y = int(W), int(H)
        sc.render.resolution_percentage = 100
        if steer is not None:
            st = C.get('steer', {}).get(n, 0.0)
            steer.matrix_basis = s0 @ Matrix.Rotation(st, 4, 'Z')
            wf = bpy.data.objects.get('wheel_f')
            if wf is not None and n in C.get('axle_f', {}):
                # the photo's front axle (from the camera solve): move the steered assembly onto it
                bpy.context.view_layer.update()
                d = K.B(*C['axle_f'][n]) - wf.matrix_world.translation
                steer.matrix_basis = Matrix.Translation(steer.parent.matrix_world.inverted().to_3x3() @ d) @ steer.matrix_basis
            bpy.context.view_layer.update()
        sc.display.render_aa = 'OFF'
        sh.light = 'FLAT'
        sh.show_cavity = False
        sh.color_type = 'SINGLE'
        sh.single_color = (1, 1, 1)
        sc.render.filepath = os.path.join(outdir, f'{n}_sil.png')
        bpy.ops.render.render(write_still=True)
        for m in bpy.data.materials:
            m.diffuse_color = palette[m.name]
        sh.color_type = 'MATERIAL'
        sc.render.filepath = os.path.join(outdir, f'{n}_ids.png')
        bpy.ops.render.render(write_still=True)
        for m in bpy.data.materials:
            m.diffuse_color = keep[m.name]
        if shade:
            sh.light, sh.color_type = 'STUDIO', 'MATERIAL'
            sh.show_cavity, sh.cavity_type = True, 'BOTH'
            sh.show_specular_highlight = True
            sc.display.render_aa = '8'
            sc.render.filepath = os.path.join(outdir, f'{n}_shade.png')
            bpy.ops.render.render(write_still=True)
    if steer is not None:
        steer.matrix_basis = s0
    for o in hidden:
        o.hide_render = False


def pick(cams_path, name, pts_in, pts_out):
    """ray casts from a solved photo camera through photo pixels onto the model (rider hidden): for measuring where a
    photo feature (a paint edge, a lamp) lies on the bodywork. pts_in: json {key: [[u, v], ...]}; pts_out: json
    {key: [{"p": [x, y, z], "obj": ..., "mat": ...} | null, ...]}"""
    from mathutils.bvhtree import BVHTree
    C = json.load(open(cams_path))
    c = C['cams'][name]
    W, H = c[7]
    f = c[6]
    d, r, u = _basis(*c[3:6])
    rider = bpy.data.objects.get('rider')
    skip = set([rider] + list(rider.children_recursive)) if rider is not None else set()
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    verts, polys, info = [], [], []
    for o in bpy.data.objects:
        if o.type != 'MESH' or o in skip:
            continue
        me = o.evaluated_get(dg).to_mesh()
        mw = o.matrix_world
        base = len(verts)
        verts += [mw @ v.co for v in me.vertices]
        for p in me.polygons:
            polys.append([base + i for i in p.vertices])
            info.append((o.name, o.material_slots[p.material_index].name if len(o.material_slots) else ''))
    tree = BVHTree.FromPolygons(verts, polys)
    eye = K.B(*c[:3])
    res = {}
    for key, pts in json.load(open(pts_in)).items():
        out = []
        for pu, pv in pts:
            g = d + ((pu - W / 2) / f) * r - ((pv - H / 2) / f) * u
            loc, nrm, idx, dist = tree.ray_cast(eye, K.B(*g).normalized(), 100.0)
            if loc is None:
                out.append(None)
            else:
                out.append({'p': [round(v, 4) for v in K.G(loc)], 'obj': info[idx][0], 'mat': info[idx][1]})
        res[key] = out
    json.dump(res, open(pts_out, 'w'))
    print('PICKED', pts_out)


def render_photo(cams_path, name, path, width=1280, samples=32, sun_offset=40.0, sun_elevation=42.0, sun_energy=None):
    """a Cycles render from a solved photo camera (front wheel steered as in the photo, rider shown), for the
    photo / render comparison sheets"""
    C = json.load(open(cams_path))
    c = C['cams'][name]
    W, H = c[7]
    sc = bpy.context.scene
    cam = sc.camera
    d, r, u = _basis(*c[3:6])
    cam.matrix_world = Matrix.Translation(K.B(*c[:3])) @ Matrix((K.B(*r), K.B(*u), -K.B(*d))).transposed().to_4x4()
    cam.data.lens = c[6] * 36 / W
    cam.data.sensor_fit = 'HORIZONTAL'
    cam.data.sensor_width = 36
    cam.data.clip_end = 1000
    steer = bpy.data.objects.get('steer')
    s0 = steer.matrix_basis.copy() if steer else None
    if steer is not None:
        steer.matrix_basis = s0 @ Matrix.Rotation(C.get('steer', {}).get(name, 0.0), 4, 'Z')
        wf = bpy.data.objects.get('wheel_f')
        if wf is not None and name in C.get('axle_f', {}):
            bpy.context.view_layer.update()
            dv = K.B(*C['axle_f'][name]) - wf.matrix_world.translation
            steer.matrix_basis = Matrix.Translation(steer.parent.matrix_world.inverted().to_3x3() @ dv) @ steer.matrix_basis
        bpy.context.view_layer.update()
    eye = c[:3]
    if sun_offset is not None:
        light_from(eye, (0, 0.7, 0), sun_offset, sun_elevation)
    if sun_energy is not None and bpy.data.objects.get('sun') is not None:
        bpy.data.objects['sun'].data.energy = sun_energy
    sc.cycles.samples = samples
    sc.render.resolution_x, sc.render.resolution_y = int(width), int(round(width * H / W))
    sc.render.resolution_percentage = 100
    sc.render.filepath = path
    # the photo's camera sits below our ground plane when the bike leans on its side stand: no ground, transparent film
    g = bpy.data.objects.get('ground')
    if g is not None:
        g.hide_render = True
    sc.render.film_transparent = True
    sc.render.image_settings.color_mode = 'RGBA'
    bpy.ops.render.render(write_still=True)
    sc.render.film_transparent = False
    sc.render.image_settings.color_mode = 'RGB'
    if g is not None:
        g.hide_render = False
    if steer is not None:
        steer.matrix_basis = s0
