"""
Toyota Supra RZ (JZA80, late model 1997-2002, stock, factory high rear wing) for TOUGE NOCTURNE (game id `supra`),
built from numbers and our own painted textures (no outside model, no photo pixels). Run with Blender 5.x:

  blender -t 4 --background --factory-startup --python tools/blender/cars/supra.py -- --out <file.glb>
      [--render <dir> --views front34,rear34,... --samples N --size WxH] [--night] [--night-views a,b] [--silhouette]
      [--silver-views a,b (again in light silver, <view>_silver.png)] [--sil-views m13,... (outlines, <view>_sil.png)]

Modules: supra_kit (mesh helpers, booleans, export), supra_body (the shell), supra_parts (openings, glass, lamps,
wheels, wing, interior, details), supra_scene (the check scene). Textures: tools/blender/textures/supra/ (made by
supra_textures.py on the host with PIL; Noto Sans CJK for the plates).
GLB contract: render/CarModel.ts (rigFromTemplate, deriveAnchors).
"""
import os
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy  # noqa: E402

import supra_kit as K  # noqa: E402
import supra_parts as PT  # noqa: E402

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []


def opt(name, default=None):
    return argv[argv.index(name) + 1] if name in argv else default


OUT = opt('--out')
RENDER = opt('--render')
VIEWS = opt('--views', 'front34')
SAMPLES = int(opt('--samples', '32'))
SIZE = tuple(int(v) for v in opt('--size', '1280x720').split('x'))
NIGHT = '--night' in argv
SILHOUETTE = '--silhouette' in argv
NIGHT_VIEWS = opt('--night-views')         # rendered after the day views, in the same run
SILVER_VIEWS = opt('--silver-views')       # the same scene with the paint in light silver (#b8babd)
SIL_VIEWS = opt('--sil-views')             # last: flat outlines of photo-matched views, for overlays

# cameras of the reference photos, solved from wheel hubs and contacts (wheelbase, track), plate corners (JP 330 × 165)
# and symmetric lamp pairs: game frame [x, y, z, yaw, pitch, roll, focal px, [W, H]] as carfit/silrender.py
MATCH = {}


def match_camera(c):
    import math
    from mathutils import Matrix, Vector
    d = Vector((math.sin(c[3]) * math.cos(c[4]), math.sin(c[4]), math.cos(c[3]) * math.cos(c[4])))
    r = d.cross(Vector((0, 1, 0))).normalized()
    u = r.cross(d)
    cr, sr = math.cos(c[5]), math.sin(c[5])
    r, u = cr * r + sr * u, -sr * r + cr * u
    cam = bpy.context.scene.camera
    M = Matrix((K.B(*r) - K.B(0, 0, 0), K.B(*u) - K.B(0, 0, 0), -(K.B(*d) - K.B(0, 0, 0)))).transposed()
    cam.matrix_world = Matrix.Translation(K.B(*c[:3])) @ M.to_4x4()
    cam.data.sensor_fit = 'HORIZONTAL'
    cam.data.sensor_width = 36
    cam.data.lens = c[6] * 36 / c[7][0]
    cam.data.shift_x = cam.data.shift_y = 0.0
    tgt = [c[i] + 5 * v for i, v in enumerate((d.x, d.y, d.z))]
    return tuple(c[:3]), tuple(tgt)


def main():
    K.clear_scene()
    mats = PT.materials()
    root = K.empty('supra')
    count = PT.build_all(root, mats)
    total = 0
    for k, v in count.items():
        print(f'TRIS {k} {v}')
        total += v
    print('TRIS total', total)
    print('MATERIALS', len(mats))
    if OUT:
        K.export_glb(OUT, root)
        print('WROTE', OUT, os.path.getsize(OUT))
    if RENDER:
        import supra_scene as S
        S.scene(night=NIGHT)
        if NIGHT:
            S.lamps_on(mats)
        if SILHOUETTE:
            S.silhouette_mode()
        S.see_through(mats['glass'], 0.88)
        os.makedirs(RENDER, exist_ok=True)
        sc = bpy.context.scene
        def views(names, suffix):
            for v in names.split(','):
                path = os.path.join(RENDER, f'{v}{suffix}.png')
                if v in MATCH:
                    eye, target = match_camera(MATCH[v])
                    S.light_from(eye, target, 40.0)
                    sc.cycles.samples = SAMPLES
                    sc.render.resolution_x, sc.render.resolution_y = MATCH[v][7]
                    sc.render.filepath = path
                    bpy.ops.render.render(write_still=True)
                else:
                    S.see_through(mats['glass'], 0.35 if v == 'interior' else 0.88)
                    S.render(v, path, size=SIZE, samples=SAMPLES)
        views(VIEWS, f'{"_night" if NIGHT else ""}{"_sil" if SILHOUETTE else ""}')
        if SILVER_VIEWS:
            p = mats['paint'].node_tree.nodes['Principled BSDF']
            old = tuple(p.inputs['Base Color'].default_value)
            p.inputs['Base Color'].default_value = K.srgb('#b8babd')
            views(SILVER_VIEWS, '_silver')
            p.inputs['Base Color'].default_value = old
        if SIL_VIEWS:
            S.silhouette_mode()
            views(SIL_VIEWS, '_sil')
        if NIGHT_VIEWS and not NIGHT:
            for name in ('sun', 'ground', 'cam'):
                ob = bpy.data.objects.get(name)
                if ob is not None:
                    bpy.data.objects.remove(ob)
            S.scene(night=True)
            S.lamps_on(mats)
            S.see_through(mats['glass'], 0.88)
            for v in NIGHT_VIEWS.split(','):
                S.render(v, os.path.join(RENDER, f'{v}_night.png'), size=SIZE, samples=SAMPLES)


main()
