"""
Nissan Silvia spec-R (S15, 1999-2002, stock, factory rear spoiler) for TOUGE NOCTURNE, built in Blender with Python.

  ~/.local/bin/blender -t 4 --background --factory-startup --python frontend/tools/blender/cars/s15.py -- \
      --out s15.glb [--render <dir> --views a,b --samples N --size WxH] [--night] [--cam cams.json] [--paint #rrggbb]

Textures come from s15_textures.py (python3, PIL) in frontend/tools/blender/textures/s15/.
Game contract (render/CarModel.ts): metres, +Y up, +Z forward, ground at y = 0, origin midway between the axles;
nodes body, wheel_fl/fr/rl/rr (pivots at the wheel centres) with spin_* children; materials by name (paint, glass,
trim, chrome, headlight, taillight, tire, rim, brake + own ones).
"""
import math
import os
import sys
import time

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bmesh  # noqa: E402
import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402

import s15_kit as K  # noqa: E402
import s15_body as BD  # noqa: E402
import s15_features as FT  # noqa: E402
import s15_parts as PT  # noqa: E402

TEX = os.path.join(os.path.dirname(HERE), 'textures', 's15')


def args():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    opt = {'out': None, 'render': None, 'views': 'front34,rear34,side,front,rear,top', 'samples': 24, 'size': (1280, 720),
           'paint': '#9a9ea4', 'night': False, 'cam': None, 'backface': False, 'sil': None, 'silout': None, 'silnames': None, 'silhide': ''}
    i = 0
    while i < len(argv):
        k = argv[i].lstrip('-')
        if k in ('night', 'backface'):
            opt[k] = True
            i += 1
            continue
        v = argv[i + 1]
        if k == 'size':
            v = tuple(int(t) for t in v.split('x'))
        elif k == 'samples':
            v = int(v)
        opt[k] = v
        i += 2
    return opt


# game frame: eye, target, lens (mm, 36 mm sensor)
VIEWS = {
    'front34': ((4.3, 1.30, 5.9), (0.0, 0.58, 0.30), 40),
    'rear34': ((-4.1, 1.40, -6.0), (0.0, 0.62, -0.30), 40),
    'side': ((9.5, 0.75, 0.0), (0.0, 0.62, 0.0), 32),
    'sider': ((-9.5, 0.75, 0.0), (0.0, 0.62, 0.0), 32),
    'front': ((0.0, 0.85, 9.0), (0.0, 0.62, 0.0), 32),
    'rear': ((0.0, 0.95, -9.0), (0.0, 0.62, 0.0), 32),
    'top': ((0.0, 12.0, 0.001), (0.0, 0.0, 0.0), 30),
    'wheel': ((1.75, 0.42, 2.05), (0.80, 0.31, 1.2625), 45),
    'low34': ((3.0, 0.55, 4.6), (0.0, 0.55, 0.6), 30),
    'corner': ((2.2, 1.3, 3.6), (0.55, 0.6, 1.8), 35),
    'rcorner': ((2.2, 1.5, -3.8), (0.5, 0.75, -1.9), 35),
    'cabin': ((2.6, 1.6, -0.2), (0.0, 0.8, -0.4), 30),
    'night34': ((4.6, 1.2, 6.8), (0.0, 0.5, 0.6), 38),
    'nightrear': ((-3.8, 1.2, -6.4), (0.0, 0.6, -0.8), 38),
}


def image(name):
    path = os.path.join(TEX, name)
    if not os.path.exists(path):
        raise SystemExit(f'missing {path}: run s15_textures.py first')
    return bpy.data.images.load(path)


def materials(paint):
    m = K.Materials()
    m.add('paint', paint, metallic=0.55, roughness=0.32, coat=1.0)
    m.add('trim', '#0d0e10', roughness=0.6)
    m.add('glass', '#0b1016', metallic=0.1, roughness=0.04)
    m.add('chrome', '#d8dade', metallic=1.0, roughness=0.12)
    m.add('amber', '#e8780e', roughness=0.2, metallic=0.1)
    m.add('lens_clear', '#dfe2e6', roughness=0.08, metallic=0.4)
    m.add('taillight', '#ffffff', roughness=0.25, image=image('taillight.png'))
    m.add('interior', '#2a2b2e', roughness=0.85)
    m.add('headlight', '#ffffff', roughness=0.1, metallic=0.4, image=image('headlight.png'))
    m.add('tire', '#151515', roughness=0.92)
    m.add('rim', '#c3c6cb', metallic=0.55, roughness=0.38)   # painted light-silver alloy
    m.add('brake', '#3a3b3e', roughness=0.5, metallic=0.4)
    m.add('disc', '#7b7c80', metallic=0.9, roughness=0.45)
    m.add('plate', '#ffffff', roughness=0.4, image=image('plate.png'))
    m.add('reflector', '#9a0c0a', roughness=0.25)
    return m


def tail_uv(bm):
    """planar UVs on the tail lenses: u from the inner tip to the outer end, v up"""
    uvl = bm.loops.layers.uv.verify()
    for f in bm.faces:
        if f.material_index not in (FT.TAIL, FT.AMBER, FT.CLEAR):
            continue
        for lp in f.loops:
            x, y, z = K.G(lp.vert.co)
            lp[uvl].uv = ((abs(x) - 0.30) / 0.52, (y - 0.778) / 0.127)


def corner_normals(bm, limit=38.0):
    """per-corner normals: area-weighted over the faces round each vertex that lie within `limit` degrees of the
    corner's own face (big flat n-gons stay flat, small faces follow them; shut lines, sockets and arch lips stay crisp)"""
    cosl = math.cos(math.radians(limit))
    bm.normal_update()
    area = {f: max(1e-9, f.calc_area()) for f in bm.faces}
    out = []
    for f in bm.faces:
        fn = f.normal
        for lp in f.loops:
            n = Vector()
            for g in lp.vert.link_faces:
                if g.normal.dot(fn) >= cosl:
                    n += g.normal * area[g]
            out.append(tuple(n.normalized() if n.length > 1e-12 else fn))
    return out


def head_uv(bm):
    """planar UVs on the headlamp lenses (front view): u from the inner tip to the outer end, v up"""
    uvl = bm.loops.layers.uv.verify()
    for f in bm.faces:
        if f.material_index != FT.HEAD:
            continue
        for lp in f.loops:
            x, y, z = K.G(lp.vert.co)
            lp[uvl].uv = ((abs(x) - 0.30) / 0.525, (y - 0.630) / 0.145)


def night(m, on=True):
    def glow(name, colour, strength):
        mat = m[name]
        nt = mat.node_tree
        p = nt.nodes['Principled BSDF']
        p.inputs['Emission Strength'].default_value = strength if on else 0.0
        tex = [n for n in nt.nodes if n.type == 'TEX_IMAGE']
        if tex:
            mix = nt.nodes.new('ShaderNodeMix')
            mix.data_type = 'RGBA'
            mix.blend_type = 'MULTIPLY'
            mix.inputs['Factor'].default_value = 1.0
            mix.inputs[6].default_value = K.srgb(colour)
            nt.links.new(tex[0].outputs['Color'], mix.inputs[7])
            nt.links.new(mix.outputs[2], p.inputs['Emission Color'])
        else:
            p.inputs['Emission Color'].default_value = K.srgb(colour)
    glow('headlight', '#fff4e0', 25.0)
    glow('taillight', '#ff1a10', 6.0)
    for s in (1, -1):
        lamp = bpy.data.objects.new(f'beam{s}', bpy.data.lights.new(f'beam{s}', 'SPOT'))
        lamp.data.energy = 900
        lamp.data.spot_size = math.radians(55)
        lamp.data.spot_blend = 0.6
        lamp.data.color = (1.0, 0.95, 0.85)
        lamp.location = K.B(s * 0.60, 0.70, 2.0)
        lamp.rotation_euler = (K.B(s * 0.4, 0.0, 12.0) - K.B(s * 0.6, 0.7, 2.0)).to_track_quat('-Z', 'Y').to_euler()
        bpy.context.scene.collection.objects.link(lamp)
    red = bpy.data.objects.new('tailglow', bpy.data.lights.new('tailglow', 'AREA'))
    red.data.energy = 30
    red.data.color = (1.0, 0.1, 0.06)
    red.data.size = 1.4
    red.location = K.B(0, 0.85, -2.35)
    red.rotation_euler = (K.B(0, 0.2, -4.0) - K.B(0, 0.85, -2.35)).to_track_quat('-Z', 'Y').to_euler()
    bpy.context.scene.collection.objects.link(red)


def backface_check():
    """diagnostic: every back face renders bright red (the game culls back faces)"""
    for mat in bpy.data.materials:
        if not mat.use_nodes or mat.name.startswith('sc_'):
            continue
        nt = mat.node_tree
        out = nt.nodes.get('Material Output')
        src = out.inputs['Surface'].links[0].from_socket if out.inputs['Surface'].links else None
        if src is None:
            continue
        geo = nt.nodes.new('ShaderNodeNewGeometry')
        em = nt.nodes.new('ShaderNodeEmission')
        em.inputs['Color'].default_value = (1, 0, 0, 1)
        em.inputs['Strength'].default_value = 3
        mix = nt.nodes.new('ShaderNodeMixShader')
        nt.links.new(geo.outputs['Backfacing'], mix.inputs[0])
        nt.links.new(src, mix.inputs[1])
        nt.links.new(em.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], out.inputs['Surface'])


def build(o):
    t0 = time.time()
    m = materials(o['paint'])
    root = K.empty('s15')
    body = K.empty('body', parent=root)
    count = {}
    bm = BD.shell()
    holes = FT.cut_all(bm, log=lambda s: print('CUT', s, round(time.time() - t0, 1)))
    tail_uv(bm)
    head_uv(bm)
    for f in bm.faces:
        f.smooth = True
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bvh = BVHTree.FromBMesh(bm)
    cn = corner_normals(bm)
    me = bpy.data.meshes.new('body_shell')
    bm.to_mesh(me)
    bm.free()
    me.normals_split_custom_set(cn)
    for name in FT.MATS:
        me.materials.append(m[name])
    shell = bpy.data.objects.new('body_shell', me)
    bpy.context.scene.collection.objects.link(shell)
    shell.parent = body
    count['shell'] = K.tris_of(shell)
    surf = PT.Surface(bvh)
    parts = K.Part('body_parts')
    PT.fog_units(parts, holes)
    PT.intake_slats(parts)
    PT.plate(parts, *holes['plate_f'], rear=False)
    PT.plate(parts, *holes['plate_r'], rear=True)
    PT.mirrors(parts, surf)
    PT.door_handles(parts, surf)
    PT.wipers(parts, surf)
    count['parts'] = parts.tris()
    parts.build(body, m.mats)
    wing = K.Part('spoiler')
    PT.spoiler(wing, surf)
    count['spoiler'] = wing.tris()
    wing.build(body, m.mats)
    ex = K.Part('exhaust')
    PT.exhaust(ex)
    count['exhaust'] = ex.tris()
    ex.build(body, m.mats)
    cab = K.Part('interior')
    PT.interior(cab)
    for v in cab.bm.verts:          # (the cabin sits 0.4 m further forward than the interior was first laid out)
        v.co.y -= 0.40
    count['interior'] = cab.tris()
    cab.build(body, m.mats)
    PT.wheels(root, m.mats, count)
    for k, v in count.items():
        print(f'TRIS {k} {v}')
    print('TRIS total', sum(count.values()))
    used = {mt.name for ob in bpy.data.objects if ob.type == 'MESH' for mt in ob.data.materials}
    print('MATERIALS', len(used), sorted(used))
    print('BUILD', round(time.time() - t0, 1), 's')
    return root, m


def sil_render(camfile, outdir, names=None):
    """silhouette and material-id renders from solved photo cameras (the carfit/silrender.py format and output)"""
    import json
    import random
    from mathutils import Matrix
    cams = json.load(open(camfile))['cams']
    names = names.split(',') if names else list(cams)
    os.makedirs(outdir, exist_ok=True)
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_WORKBENCH'
    sc.render.film_transparent = True
    sc.view_settings.view_transform = 'Standard'
    sc.display.render_aa = 'OFF'
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_mode = 'RGBA'
    sh = sc.display.shading
    sh.light = 'FLAT'
    sh.show_object_outline = False
    cam = bpy.data.objects.new('silcam', bpy.data.cameras.new('silcam'))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.data.clip_start = 0.05
    cam.data.clip_end = 1000
    cam.data.sensor_fit = 'HORIZONTAL'
    cam.data.sensor_width = 36
    random.seed(7)
    palette = {mt.name: (random.random(), random.random(), random.random(), 1) for mt in bpy.data.materials}
    for name in names:
        c = cams[name]
        W, H = c[7]
        yaw, pitch, roll = c[3:6]
        d = Vector((math.sin(yaw) * math.cos(pitch), math.sin(pitch), math.cos(yaw) * math.cos(pitch)))
        r = d.cross(Vector((0, 1, 0))).normalized()
        u = r.cross(d)
        cr, sr = math.cos(roll), math.sin(roll)
        r, u = cr * r + sr * u, -sr * r + cr * u
        M = Matrix((K.B(*r), K.B(*u), -K.B(*d))).transposed()
        cam.matrix_world = Matrix.Translation(K.B(*c[:3])) @ M.to_4x4()
        cam.data.lens = c[6] * 36 / W
        sc.render.resolution_x, sc.render.resolution_y = int(W), int(H)
        sc.render.resolution_percentage = 100
        sh.color_type = 'SINGLE'
        sh.single_color = (1, 1, 1)
        sc.render.filepath = os.path.join(outdir, f'{name}_sil.png')
        bpy.ops.render.render(write_still=True)
        for mt in bpy.data.materials:
            mt.diffuse_color = palette[mt.name]
        sh.color_type = 'MATERIAL'
        sc.render.filepath = os.path.join(outdir, f'{name}_ids.png')
        bpy.ops.render.render(write_still=True)
        print('SIL', name)


def main():
    o = args()
    K.clear_scene()
    root, m = build(o)
    if o['out']:
        K.export_glb(o['out'], root)
        print('GLB', o['out'], os.path.getsize(o['out']))
    if o['sil']:
        for n in filter(None, o['silhide'].split(',')):
            ob = bpy.data.objects.get(n)
            if ob is not None:
                ob.hide_render = True
        sil_render(o['sil'], o['silout'], o['silnames'])
    if o['render']:
        K.scene(night=o['night'])
        if o['night']:
            night(m)
        if o['backface']:
            backface_check()
        os.makedirs(o['render'], exist_ok=True)
        cams = {}
        if o['cam']:
            import json
            cams = json.load(open(o['cam']))
        for v in o['views'].split(','):
            if v in cams:
                K.render_cam(cams[v], os.path.join(o['render'], f'{v}.png'), samples=max(8, o['samples'] // 2))
                continue
            K.render(VIEWS[v], os.path.join(o['render'], f'{v}.png'), size=o['size'], samples=o['samples'])


main()
