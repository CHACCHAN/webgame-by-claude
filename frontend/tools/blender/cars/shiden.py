"""
Mazda RX-7 (FD3S), 1999 Type RS (V型, GF-FD3S), for TOUGE NOCTURNE (game id `shiden`): built from numbers in Blender,
no outside model, no photo pixels, no maker's marks.

  blender -t 4 --background --factory-startup --python tools/blender/cars/shiden.py -- --out <file.glb>
      [--render <dir> --views front34,rear34,... --samples N --size WxH] [--night] [--closed] [--silhouettes <dir>]

Modules (tools/blender/cars/): shiden_surf (spline surface, trims, decals), shiden_shape (the body's numbers),
shiden_body (shell, openings, glass), shiden_parts (materials; calls the rest), shiden_wheels (rims, tyres, discs,
calipers), shiden_lamps (pop-up pods, lamps, lenses), shiden_details (intake, plates, wing, mirrors, wipers, shut
lines, cabin, exhaust), shiden_scene (check renders). Textures: tools/blender/textures/shiden/*.png, made by
`python3 tools/blender/cars/shiden_textures.py` (PIL, Noto Sans CJK for the plate); run it before the build.

GLB contract (render/CarModel.ts): metres, +Y up, +Z forward, origin on the ground midway between the axles; nodes
body, wheel_fl/fr/rl/rr (pivots) → spin_* (tyre, rim, disc); calipers under the pivots; popup_l / popup_r (hinged
pods, raised, extras.popupClosed); materials paint, glass, trim, chrome, headlight, taillight, tire, rim, brake,
popup_lens + our own.
"""
import os
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy  # noqa: E402

import shiden_body as BODY  # noqa: E402
import shiden_parts as PARTS  # noqa: E402

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []


def opt(name, default=None):
    return argv[argv.index(name) + 1] if name in argv else default


OUT = opt('--out')
RENDER = opt('--render')
VIEWS = opt('--views', 'front34')
SAMPLES = int(opt('--samples', '32'))
SIZE = tuple(int(v) for v in opt('--size', '1280x720').split('x'))
SIL = opt('--silhouettes')
NIGHT = '--night' in argv
CLOSED = '--closed' in argv


def empty(name, parent=None, loc=(0, 0, 0)):
    from shiden_surf import B
    e = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(e)
    e.location = B(*loc)
    e.parent = parent
    return e


def export(path, root):
    bpy.ops.object.select_all(action='DESELECT')
    root.select_set(True)
    for c in root.children_recursive:
        c.select_set(True)
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', use_selection=True, export_yup=True,
                              export_apply=True, export_materials='EXPORT', export_extras=True,
                              export_cameras=False, export_lights=False)


def build_car(night=False):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    mats = PARTS.materials(night=night)
    root = empty('shiden')
    body = empty('body', root)
    counts = {}
    shell = BODY.build(body, mats, counts, cuts=PARTS.cut)
    PARTS.build(root, body, shell, mats, counts)
    return root, mats, counts


def main():
    root, mats, counts = build_car(NIGHT)
    total = 0
    for k, v in counts.items():
        print(f'TRIS {k} {v}')
        total += v
    print('TRIS total', total)
    used = set()
    for o in root.children_recursive:
        if o.type == 'MESH':
            used |= {m.name for m in o.data.materials if m}
    print('MATERIALS', len(used), sorted(used))
    if OUT:
        export(OUT, root)
    if CLOSED:
        PARTS.fold_pods(root)
    if SIL:
        import shiden_scene as S
        os.makedirs(SIL, exist_ok=True)
        for v, size, scale in (('side', (1800, 600), 5.4), ('front', (1000, 600), 2.4), ('rear', (1000, 600), 2.4),
                               ('top', (1800, 1000), 5.4)):
            if v == 'top':
                size = (1000, 1800)
            S.silhouette(os.path.join(SIL, f'{v}.png'), v, size, scale)
    if RENDER:
        import shiden_scene as S
        S.scene(night=NIGHT)
        if NIGHT:
            PARTS.lamps_on(mats)
        os.makedirs(RENDER, exist_ok=True)
        for v in VIEWS.split(','):
            S.render(v, os.path.join(RENDER, f'{v}{"_night" if NIGHT else ""}{"_closed" if CLOSED else ""}.png'),
                     size=SIZE, samples=SAMPLES)


if __name__ == '__main__':
    main()
