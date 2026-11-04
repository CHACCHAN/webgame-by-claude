"""
The E231 近郊タイプ (1000番台, Shōnan colours, an Ueno-Tokyo Line train) as a variant of tools/blender/e231.py:
`e231.py --variant kinkou` hands its arguments to build() here (or to run(), which also exports and renders).

  build(args=None) -> [car0, car1, car2]     clears the scene, makes the materials and textures, builds the cars
  run(args=None)                             build() + export (--out) + renders (--render, --views, --samples, --size)
  LAMP_MATERIAL, TAIL_MATERIAL, VIEWS        for showcase.headlamps() and the check cameras

`args`: None (sys.argv after '--'), a list of CLI words (e231.py's: --out, --render, --views, --samples, --size,
--tex, --cams), a dict or an argparse.Namespace with the same names. Textures go to <--tex>/kinkou (else a temp dir).
Standalone: blender -t 4 --background --factory-startup --python tools/blender/parts/e231_kinkou_build.py -- --out x.glb

The train (the 5-car add-on set's three cars that have the game's cab - motor - cab shape, numbers our own):
  car0 = クハE231-8072 (15号車, Tc, cab at +z, electric coupler), car1 = モハE231-1172 (13号車, M, the PS33B at its
  −z end: "＞", the end towards モハE230), car2 = クハE230-6072 (11号車, T'c, turned round). Same frame, node names
  (car0..car2 with <car>_body and <car>_gear) and figures (L 20 m, bogies ±6.9, coupler face 10.0) as e231.py.
Parts: body, cab, skirt, textures: e231_kinkou_body (kn_); the gear under the cab: e231_kinkou_coupler (on
e231_coupler, ec_); roof gear, underfloor, bogies, bar couplers: e231_roof / e231_underfloor / e231_bogie / e231_coupler
of the commuter type, unchanged (the 近郊タイプ shares the AU726 AC, the PS33B, the DT61 / TR246 bogie families and
the box layout's look; the 1000番台's own suffixes — DT61B / TR246 variants — and its exact underfloor layout are not
modelled: est.).
"""
import math
import os
import sys
import tempfile

sys.dont_write_bytecode = True
_here = os.path.dirname(os.path.abspath(__file__))
for _p in (os.path.dirname(_here), _here):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import train_kit as K  # noqa: E402
import e231_kinkou_body as KB  # noqa: E402
import e231_kinkou_coupler as KC  # noqa: E402
import e231_roof as RF  # noqa: E402
import e231_underfloor as UF  # noqa: E402
import e231_bogie as BG  # noqa: E402
import e231_coupler as CP  # noqa: E402

L = 20.0
BOGIE_Z = 6.9
COUPLER_FACE = 10.0
PANTOGRAPH = (-7.40, -1)
CARS = (('car0', 'cab', 0.0, False), ('car1', 'middle', -L, False), ('car2', 'cab', -2 * L, True))
LAMP_MATERIAL = KB.P + 'lamp'
TAIL_MATERIAL = KB.P + 'tail'

# game frame: eye, target, lens (mm, 36 mm sensor)
VIEWS = {
    'hero': ((-7.0, 3.6, 40.0), (0.2, 1.9, -2.0), 85),
    'head': ((0.0, 2.30, 27.0), (0.0, 2.0, 9.8), 100),
    'front34': ((6.0, 2.0, 17.5), (0.0, 1.8, 7.0), 40),
    'side': ((17.0, 1.8, -10.0), (0.0, 1.9, -10.0), 30),
    'side0': ((25.0, 1.9, 0.0), (0.0, 1.9, 0.0), 40),
    'bogie': ((3.4, 0.75, 10.6), (0.0, 0.55, 6.9), 35),
    'roof': ((9.0, 8.5, -14.0), (0.0, 3.4, -28.0), 40),
    'rear34': ((-6.0, 2.6, -68.0), (0.0, 1.9, -44.0), 50),
    'skirt': ((1.4, 0.95, 13.8), (0.0, 0.7, 9.9), 50),
    'cabside': ((-6.0, 1.9, 7.5), (0.0, 2.0, 7.5), 40),
}
LIT = {'hero', 'head', 'front34', 'skirt'}
GEAR_TONE = {'ec_grey': '#625e57', 'eb_frame': '#67635d', 'eb_wheel': '#5b5752'}

# near-identical solid colours of the part modules share one material (≤ 30 per car): alias → kept one
ALIAS = {
    'kn_bellows': 'kn_under', 'er_dark': 'kn_under', 'eu_dark': 'kn_under', 'ec_rubber': 'kn_under',
    'ec_dark': 'kn_under',
    'er_metal': 'kn_frame', 'eu_steel': 'kn_frame', 'eb_dark': 'kn_frame',
    'ec_silver': 'kn_chrome', 'eu_hw': 'kn_chrome',
    'eu_fin': 'kn_steel',
    'kn_jamb': 'kn_end', 'eb_tread': 'kn_end',
    'ec_white': 'kn_skirt',
    'ec_rust': 'eb_rubber',
}


def _args(args):
    """{'out': .., 'render': .., ...} from None / a list of CLI words / a dict / a namespace"""
    if args is None:
        args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    if isinstance(args, (list, tuple)):
        out = {}
        i = 0
        while i < len(args):
            a = args[i]
            if a.startswith('--'):
                if i + 1 < len(args) and not args[i + 1].startswith('--'):
                    out[a[2:]] = args[i + 1]
                    i += 2
                    continue
                out[a[2:]] = True
            i += 1
        return out
    if isinstance(args, dict):
        return dict(args)
    return {k: v for k, v in vars(args).items() if v is not None}


def _mats_view(mats):
    view = dict(mats)
    for a, t in ALIAS.items():
        if a in view and t in view:
            view[a] = view[t]
    return view


def _tris(part):
    return sum(len(f.verts) - 2 for f in part.bm.faces)


def materials(tex_dir):
    m = K.Materials()
    boxes = KB.add_materials(m, tex_dir)
    for mod in (RF, UF, BG, KC):
        mod.add_materials(m)
    # the gear under the cab is weathered brown-grey on the 1000番台 (S-13, U514), not the commuter type's clean grey
    for name, col in GEAR_TONE.items():
        p = m.mats[name].node_tree.nodes.get('Principled BSDF')
        p.inputs['Base Color'].default_value = K.srgb(col)
    return m, boxes


def build_car(m, boxes, name, kind, z_offset, flip):
    cab = kind == 'cab'
    root = K.car_empty(name, z_offset)
    if flip:
        root.rotation_euler = (0, 0, math.pi)
    count = {}
    body = KB.UVPart(f'{name}_body')
    KB.build(body, kind)
    if cab:
        KB.cab_fittings(body, boxes)
        KB.skirt(body)
    KB.side_fittings(body, boxes, kind)
    KB.atlas_uvs(body, name)
    KB.number_decals(body, name, kind)
    count['body'] = _tris(body)

    gear = K.Part(f'{name}_gear')
    n = _tris(gear)
    RF.air_conditioner(gear, 0.0)
    if cab:
        RF.cab_roof_details(gear, KB.CAB_JOIN + 0.3)
        RF.roof_details(gear, -KB.END, KB.CAB_JOIN, end_boxes=(-9.35,))
    else:
        zc, knee = PANTOGRAPH
        RF.pantograph(gear, zc, knee=knee)
        RF.pantograph_gear(gear, zc, knee=knee)
        RF.roof_details(gear, -KB.END, KB.END)
    count['roof'] = _tris(gear) - n
    n = _tris(gear)
    if cab:
        UF.underfloor_tc(gear, car='E230' if flip else 'E231')
    else:
        UF.underfloor_m(gear)
    count['underfloor'] = _tris(gear) - n
    n = _tris(gear)
    for zc, facing in ((BOGIE_Z, 1), (-BOGIE_Z, -1)):
        if cab:
            BG.bogie(gear, zc, 'TR246M' if zc > 0 else 'TR246', facing=facing)
        else:
            BG.bogie(gear, zc, 'DT61G', facing=facing)
    count['bogies'] = _tris(gear) - n
    n = _tris(gear)
    if cab:
        KC.front_gear(gear, COUPLER_FACE)
    if name != 'car2':
        CP.intercar_coupler(gear, -L / 2)
    count['couplers'] = _tris(gear) - n

    mats = _mats_view(m.mats)
    body.build(root, mats)
    gear.build(root, mats)
    print(f'TRIS {name}: {sum(count.values())} ' + ' '.join(f'{k} {v}' for k, v in count.items()))
    return root


def build(args=None):
    a = _args(args)
    K.clear_scene()
    tex = a.get('tex')
    tex_dir = os.path.join(tex, 'kinkou') if tex else tempfile.mkdtemp(prefix='e231-kinkou-tex-')
    m, boxes = materials(tex_dir)
    RF.set_roof_profile([(x, y) for x, y, _nx, _ny in KB.half_profile()])
    cars = [build_car(m, boxes, *c) for c in CARS]
    used = set()
    for car in cars:
        for ob in car.children:
            used |= {id(s.material) for s in ob.material_slots if s.material is not None}
    print('MATERIALS', len(used))
    return cars


def run(args=None):
    a = _args(args)
    cars = build(a)
    if a.get('out'):
        K.export_glb(a['out'], cars)
    if a.get('render'):
        import showcase as S
        S.scene(z0=-62.0, z1=12.0)
        S.VIEWS.update(VIEWS)
        for spec in filter(None, (a.get('cams') or '').split(';')):
            name, nums = spec.split(':')
            v = [float(t) for t in nums.split(',')]
            S.VIEWS[name] = (tuple(v[0:3]), tuple(v[3:6]), v[6])
        size = tuple(int(v) for v in str(a.get('size', '1600x900')).split('x'))
        samples = int(a.get('samples', 64))
        views = str(a.get('views', a.get('view', 'hero'))).split(',')
        path = a['render']
        if path.endswith('.png'):
            S.headlamps(views[0] in LIT, material=LAMP_MATERIAL)
            S.render(views[0], path, size=size, samples=samples)
        else:
            os.makedirs(path, exist_ok=True)
            for v in views:
                S.headlamps(v in LIT, material=LAMP_MATERIAL)
                S.render(v, os.path.join(path, f'{v}.png'), size=size, samples=samples)
    return cars


if __name__ == '__main__':
    run()
