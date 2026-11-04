"""
Nissan Skyline GT-R (BNR34, V-spec look, 1999-2002) for TOUGE NOCTURNE, built from numbers in Blender (no outside
model, no photo pixels). Run with Blender 5.x:

  blender -t 4 --background --factory-startup --python tools/blender/cars/r34.py -- --out <file.glb>
      [--render <dir> --views front34,rear34,... --samples N --size WxH] [--night] [--alpha] [--white] [--cams cams.json]

Modules (cars/): r34_shell (the body surface: a B-spline control cage), r34_body (cuts, glass, lamps, grille, panel
lines, trim), r34_wheels (stock 18" five-spoke wheels, tyres, brakes), r34_parts (wing, mirrors, interior, exhaust,
diffuser ...), r34_kit (helpers), r34_scene (check renders). Textures: textures/r34/ (r34_textures.py, PIL).

GLB contract (render/CarModel.ts): node `body` with every body mesh; wheel pivots wheel_fl/fr/rl/rr at the wheel
centres, each with spin_* holding tyre, rim and disc (calipers under the pivot); materials paint, glass, trim, chrome,
headlight, taillight, tire, rim, brake by name. +Z forward, +X = the car's left, ground at y = 0.
"""
import os
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy  # noqa: E402

import r34_kit as K  # noqa: E402
import r34_body as BODY  # noqa: E402
import r34_wheels as WH  # noqa: E402

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []


def opt(name, default=None):
    return argv[argv.index(name) + 1] if name in argv else default


OUT = opt('--out')
RENDER = opt('--render')
VIEWS = opt('--views', 'front34')
SAMPLES = int(opt('--samples', '32'))
SIZE = tuple(int(v) for v in opt('--size', '1280x720').split('x'))
NIGHT = '--night' in argv
ALPHA = '--alpha' in argv          # transparent film and no ground: silhouettes for photo overlays
WHITE = '--white' in argv          # renders only: white paint, as on the reference photos (blue hides the shape)
TEX = os.path.join(os.path.dirname(HERE), 'textures', 'r34')


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    mats = BODY.materials(TEX)
    root = K.empty('r34')
    body = K.empty('body', parent=root)
    counts = {}
    for name, obj in BODY.build(mats, body, TEX):
        counts[name] = counts.get(name, 0) + K.tri_count(obj)
    for name, obj in WH.build(mats, root, TEX):
        counts[name] = counts.get(name, 0) + K.tri_count(obj)
    for k, v in counts.items():
        print(f'TRIS {k} {v}')
    print('TRIS total', sum(counts.values()))
    used = set()
    for o in bpy.data.objects:
        if o.type == 'MESH' and o.name not in ('ground',):
            for m in o.data.materials:
                used.add(m.name)
    print('MATERIALS', len(used), sorted(used))
    if OUT:
        bpy.ops.object.select_all(action='DESELECT')
        root.select_set(True)
        for c in root.children_recursive:
            c.select_set(True)
        bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', use_selection=True, export_yup=True,
                                  export_apply=True, export_materials='EXPORT', export_extras=True,
                                  export_cameras=False, export_lights=False, export_image_format='AUTO')
    if RENDER:
        import r34_scene as S
        S.setup(night=NIGHT)
        if ALPHA:
            bpy.data.objects['ground'].hide_render = True
        if NIGHT:
            BODY.lamps_on(mats)
        # the game shows the glass see-through (opacity 0.88); the GLB's glass stays opaque
        mats['glass'].node_tree.nodes['Principled BSDF'].inputs['Alpha'].default_value = 0.88
        if WHITE:
            bsdf = mats['paint'].node_tree.nodes['Principled BSDF']
            bsdf.inputs['Base Color'].default_value = (0.80, 0.80, 0.78, 1)
            bsdf.inputs['Metallic'].default_value = 0.1
        os.makedirs(RENDER, exist_ok=True)
        cams = {}
        if opt('--cams'):                  # cameras solved from photos: {name: {loc, euler, lens, aspect}}
            import json
            cams = json.load(open(opt('--cams')))
        for v in VIEWS.split(','):
            size = SIZE
            if v in cams:
                size = (SIZE[0], int(round(SIZE[0] * cams[v]['aspect'])))
            S.render(cams.get(v, v), os.path.join(RENDER, f'{v}{"_night" if NIGHT else ""}{"_a" if ALPHA else ""}.png'),
                     size=size, samples=SAMPLES, transparent=ALPHA)


main()
