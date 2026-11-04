"""
Toyota Sprinter Trueno AE86 (3-door GT-APEX, late model 1985-87) for TOUGE NOCTURNE (game id `hayate`), built from
numbers and our own painted textures (no outside model, no photo pixels). Run with Blender 5.x:

  blender -t 4 --background --factory-startup --python tools/blender/cars/hayate.py -- --out <file.glb>
      [--render <dir> --views front34,rear34,... --samples N --size WxH] [--night] [--closed]

Modules: hayate_kit (mesh helpers, export), hayate_body (hull, glasshouse, bumpers), hayate_parts (pop-ups, lamps,
wheels, interior, details), hayate_tex (painted textures), hayate_stage (the check scene).
GLB contract: render/CarModel.ts (rigFromTemplate) and CarVisual.ts (pop-up hinges popup_l / popup_r).
"""
import os
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy  # noqa: E402

import hayate_kit as K  # noqa: E402
import hayate_body as BD  # noqa: E402
import hayate_parts as P  # noqa: E402

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []


def opt(name, default=None):
    return argv[argv.index(name) + 1] if name in argv else default


OUT = opt('--out')
RENDER = opt('--render')
VIEWS = opt('--views', 'front34')
SAMPLES = int(opt('--samples', '32'))
SIZE = tuple(int(v) for v in opt('--size', '1280x720').split('x'))
NIGHT = '--night' in argv
CLOSED = '--closed' in argv


def main():
    K.clear_scene()
    mats, tex = P.materials()
    root = K.empty('hayate')
    count = {}
    body = K.empty('body', root)
    parts = P.build_all(body, root, mats, count)
    total = 0
    for k, v in count.items():
        print(f'TRIS {k} {v}')
        total += v
    print(f'TRIS total {total}')
    used = set()
    for o in root.children_recursive:
        if o.type == 'MESH':
            for m in o.data.materials:
                used.add(m.name)
    print('MATERIALS', len(used), sorted(used))
    if OUT:
        K.export_glb(OUT, root)
    if RENDER:
        import hayate_stage as S
        S.scene(night=NIGHT)
        P.lamps_on(mats, NIGHT)
        if '--transparent' in argv:
            g = bpy.data.objects.get('ground')
            g.hide_render = True
        for name in (opt('--hide') or '').split(','):
            o = bpy.data.objects.get(name)
            if o is not None:
                for c in [o] + list(o.children_recursive):
                    c.hide_render = True
        if CLOSED:
            P.fold_popups(parts, closed=True)
        if '--workbench' in argv:
            sc = bpy.context.scene
            sc.render.engine = 'BLENDER_WORKBENCH'
            sc.display.shading.light = 'STUDIO'
            sc.display.shading.color_type = 'MATERIAL'
            sc.display.shading.show_cavity = True
            sc.display.shading.show_object_outline = False
            sc.display.render_aa = '8'
        os.makedirs(RENDER, exist_ok=True)
        for v in VIEWS.split(','):
            S.render(v, os.path.join(RENDER, f'{v}{"_night" if NIGHT else ""}{"_closed" if CLOSED else ""}.png'), size=SIZE, samples=SAMPLES, transparent='--transparent' in argv)


main()
