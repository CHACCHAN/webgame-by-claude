"""
Nissan Skyline GT-R (BNR34, V-spec look, 1999-2002) for TOUGE NOCTURNE, built from numbers in Blender (no outside
model, no photo pixels). Run with Blender 5.x:

  blender -t 4 --background --factory-startup --python tools/blender/cars/r34.py -- --out <file.glb>
      [--render <dir> --views front34,rear34,... --samples N --size WxH] [--night] [--alpha] [--white] [--noffd]
      [--paint #rrggbb]

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
import r34_ffd as FFD  # noqa: E402

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


def lamp_report(root):
    """centre and size of each lamp lens (game frame), per side"""
    out = {}
    for o in root.children_recursive:
        if o.type != 'MESH':
            continue
        names = [ms.name for ms in o.data.materials]
        for p in o.data.polygons:
            n = names[p.material_index] if p.material_index < len(names) else ''
            if n in ('headlight', 'taillight'):
                for vi in p.vertices:
                    g = K.G(o.matrix_world @ o.data.vertices[vi].co)
                    out.setdefault((n, 'L' if g[0] > 0 else 'R'), []).append(g)
    res = {}
    for (k, side), pts in sorted(out.items()):
        lo = [min(p[i] for p in pts) for i in range(3)]
        hi = [max(p[i] for p in pts) for i in range(3)]
        res[(k, side)] = ([round((a + b) / 2, 3) for a, b in zip(lo, hi)], [round(b - a, 3) for a, b in zip(lo, hi)])
        print('LAMP', k, side, 'centre', res[(k, side)][0], 'size', res[(k, side)][1])
    return res


def finish(root, body, mats):
    """after the body's last deformation (car_common): the underside (a front engine driving all four wheels, the
    rear on arms, one silencer along the left of the tail), the floor undersealed, the plain materials into two
    painted atlases, every corner's share of the sky. The grille's mesh picture repeats, so it stays a material; so does the plate (car_common)."""
    import car_common as CC
    import hayate_kit as HK
    import r34_fit as FIT
    CC.underseal([o for o in body.children_recursive if o.type == 'MESH'], mats)
    ub = HK.Mesh('underbody')
    x, y, z = FIT.EXHAUST
    CC.underbody(ub, 0.155, WH.WHEELBASE / 2, -WH.WHEELBASE / 2, WH.TRACK_F, WH.TRACK_R, WH.R_TYRE, tip=(x, y, z + 0.30),
                 layout='AWD', axle='irs')
    print('TRIS underbody', ub.tris())
    CC.build(ub, body, mats)
    trim = CC.Atlas('trim')
    rim = CC.Atlas('rim', size=512, fill=('#8a8c8f', 0.32, 0.85))
    rim.region('disc', CC.disc_image(), 0.38, 0.85)
    made = CC.consolidate(root, trim, rim, own=('tire', 'plate', 'grille'))
    tyres = [o for o in root.children_recursive
             if o.type == 'MESH' and any(m and m.name == 'tire' for m in o.data.materials)]
    CC.bake_ao(root, made + tyres)


def build(o=None):
    """the whole car into the (cleared) scene. o: {'paint': '#rrggbb' (None: the default), 'ffd': True (the fitted
    field, fitdata/r34/ffd.json) | False | an r34_ffd.Lattice}. Returns (root, materials, lamp report)"""
    o = o or {}
    mats = BODY.materials(TEX)
    if o.get('paint'):
        bsdf = mats['paint'].node_tree.nodes['Principled BSDF']
        bsdf.inputs['Base Color'].default_value = K.srgb(o['paint'])
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
    for ob in root.children_recursive:
        if ob.type == 'MESH':
            used.update(m.name for m in ob.data.materials)
    print('MATERIALS', len(used), sorted(used))
    if o.get('ffd', True) is not False:
        # the fitted displacement field (fitdata/r34/ffd.json, from the photo silhouettes) on every body mesh
        L = FFD.apply_to_body(body, None if o.get('ffd', True) is True else o['ffd'])
        print('FFD', 'none' if L is None else 'applied')
    bpy.context.view_layer.update()
    finish(root, body, mats)
    bpy.context.view_layer.update()
    return root, mats, lamp_report(root)


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    root, mats, _ = build({'ffd': '--noffd' not in argv, 'paint': opt('--paint')})
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
        if WHITE:
            bsdf = mats['paint'].node_tree.nodes['Principled BSDF']
            bsdf.inputs['Base Color'].default_value = (0.80, 0.80, 0.78, 1)
            bsdf.inputs['Metallic'].default_value = 0.1
        os.makedirs(RENDER, exist_ok=True)
        for v in VIEWS.split(','):
            S.render(v, os.path.join(RENDER, f'{v}{"_night" if NIGHT else ""}{"_a" if ALPHA else ""}.png'),
                     size=SIZE, samples=SAMPLES, transparent=ALPHA)


if __name__ == '__main__':
    main()
