"""
Xiaomi SU7 Max (2024; game id `su7`) for TOUGE NOCTURNE, built from published figures and our own measurements of
Commons photos (no outside model, no photo pixels; the marks on it are our own simple drawings).
Run with Blender 5.x:

  blender -t 4 --background --factory-startup --python tools/blender/cars/su7.py -- --out <file.glb>
      [--render <dir> --views a,b --samples N --size WxH] [--night] [--paint #rrggbb] [--noffd | --ffd lattice.json]
      [--silver-views a,b (again in light silver, <view>_silver.png)] [--night-views a,b] [--bare]

Figures: length 4,997, width 1,963 (no mirrors), height 1,455 (the Max; the SU7 and the Pro 1,440), wheelbase 3,000 mm
(Xiaomi's configuration sheet, as cited by en.wikipedia "Xiaomi SU7"); the body is fitted to the photos in
fitdata/su7/ (ref/list.json: file, URL, author, licence). As the photos' cars: the 21-inch wheels with yellow
calipers, the active rear spoiler retracted (it rises only at speed).

GLB contract (render/CarModel.ts): metres, +Y up, +Z forward, +X = the car's left, ground at y = 0, origin midway
between the axles; node `body` (all body meshes), wheel pivots wheel_fl/fr/rl/rr at the wheel centres with spin_*
children (tyre, rim, disc) and the calipers beside spin; materials paint (the game recolours it), glass (windscreen,
side glass, the glass roof running into the rear window), trim, chrome, headlight, taillight, tire, rim, brake, plus
under, grille, disc, rimface, plate, reflector (the bumper's red reflectors: no lamp), sensor (the lidar's window),
screen (the cabin's displays), cal_yellow (the calipers).
No exhaust (electric). Modules: su7_kit (mesh helpers, booleans, export), su7_body (the shell), su7_ffd (the fitted
deformation), su7_parts (materials, arches, wheels, cabin), su7_details (mirrors, lidar, lamps, black sections, shut
lines, plates, marks), su7_data (the traced outlines), su7_textures (lamp and plate textures), su7_scene (the check
scene).
"""
import os
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy  # noqa: E402

import su7_kit as K  # noqa: E402
import su7_parts as PT  # noqa: E402

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []


def opt(name, default=None):
    return argv[argv.index(name) + 1] if name in argv else default


OUT = opt('--out')
RENDER = opt('--render')
VIEWS = opt('--views', 'front34')
SAMPLES = int(opt('--samples', '32'))
SIZE = tuple(int(v) for v in opt('--size', '1280x720').split('x'))
NIGHT = '--night' in argv
PAINT = opt('--paint', '#35b6cf')
NIGHT_VIEWS = opt('--night-views')
SILVER_VIEWS = opt('--silver-views')


def build():
    K.clear_scene()
    mats = PT.materials(PAINT)
    root = K.empty('su7')
    ffd = False if '--noffd' in argv else True
    if opt('--ffd'):
        import su7_ffd as FF
        ffd = FF.Lattice.load(opt('--ffd'))
    count = PT.build_all(root, mats, ffd=ffd, bare='--bare' in argv)
    total = 0
    for k, v in count.items():
        print(f'TRIS {k} {v}')
        total += v
    print('TRIS total', total)
    used = set()
    for ob in root.children_recursive:
        if ob.type == 'MESH':
            used.update(ms.name for ms in ob.data.materials)
    print('MATERIALS', len(used), sorted(used))
    return root, mats


def main():
    root, mats = build()
    if OUT:
        K.export_glb(OUT, root)
        print('WROTE', OUT, os.path.getsize(OUT))
    if RENDER:
        import su7_scene as S
        S.scene(night=NIGHT)
        if NIGHT:
            S.lamps_on(mats)
        S.see_through(mats['glass'], 0.88)
        os.makedirs(RENDER, exist_ok=True)

        def views(names, suffix):
            for v in names.split(','):
                S.render(v, os.path.join(RENDER, f'{v}{suffix}.png'), size=SIZE, samples=SAMPLES)
        views(VIEWS, '_night' if NIGHT else '')
        if SILVER_VIEWS:
            p = mats['paint'].node_tree.nodes['Principled BSDF']
            old = tuple(p.inputs['Base Color'].default_value)
            p.inputs['Base Color'].default_value = K.srgb('#b8babd')
            views(SILVER_VIEWS, '_silver')
            p.inputs['Base Color'].default_value = old
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
