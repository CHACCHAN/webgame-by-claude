"""
JR East E231 series 0番台 as converted for the Musashino Line (set MU2, Keiyō depot), three cars クハE231 + モハE231 +
クハE230 as the game shows them, built from numbers and our own painted textures (no outside model, no photo pixels).
Run with Blender 5.x:

  blender --background --factory-startup --python tools/blender/e231.py -- --out <file.glb> [--variant sobu|joban|tozai]
      [--render <dir> [--views hero,head,...] [--samples N] [--size WxH] [--cams 'name:ex,ey,ez,tx,ty,tz,lens;...']]
      [--tex <dir>]

Variants (the line's name on the displays):
  (none)  Musashino Line, set MU2 (武蔵野線 / Musashino Line), orange / white / maroon
  sobu    Chūō-Sōbu local, set B11 (総武線各駅停車 / Chuo-Sobu Line), yellow 黄1号
  joban   Jōban rapid / Narita line, set 111 (常磐線 / Joban Line): emerald 青緑1号 over a yellow-green line, white cab
          FRP and skirt, outside-speaker blanks in the upper band, an electric coupler under the head (its only
          extra geometry)
  tozai   E231-800 (Tōzai Line through service, set K5): its own narrower body and asymmetric cab, parts/e231_800_*.py
The first three share the meshes, nodes and material names; they differ in paint and sign textures (and joban's
electric coupler).

The parts live in tools/blender/parts/ (each module's docstring lists its figures and where they come from):
  e231_body        body shell, cab face, doors, windows, painted side / face textures, LED displays, skirt
  e231_roof        AU725 air conditioners, PS33B pantograph and its gear, antennas
  e231_underfloor  the Tc and M cars' underfloor equipment, under frame
  e231_bogie       DT61G / TR246 / TR246M bogies
  e231_coupler     the tight-lock coupler under the cab, the bar couplers between the cars
Signs (LED displays, set plate, car numbers): tools/blender/textures/e231/ (e231_textures.py, Noto Sans CJK JP, OFL).
--render renders the train on a trackside (showcase.py) for checking and for the owner.
"""
import importlib
import math
import os
import sys
import tempfile

sys.dont_write_bytecode = True  # no __pycache__ in the repo
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, 'parts'))
import train_kit as K  # noqa: E402

_A = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
# the E231-800 (Tōzai Line through service) has its own narrower body and cab: parts/e231_800_body.py
BD = importlib.import_module('e231_800_body' if '--variant' in _A and _A[_A.index('--variant') + 1] == 'tozai'
                             else 'e231_body')


_ARGV = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
_PH = set(_ARGV[_ARGV.index('--ph') + 1].split(',')) if '--ph' in _ARGV else set()   # force placeholders


def _opt_module(name):
    if name.split('_')[-1] in _PH or 'all' in _PH:
        return None
    try:
        return importlib.import_module(name)
    except ImportError as e:
        print(f'WARNING: {name} not available ({e}); placeholder used')
        return None


RF = _opt_module('e231_roof')
UF = _opt_module('e231_underfloor')
BG = _opt_module('e231_bogie')
CP = _opt_module('e231_coupler')

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []


def opt(name, default=None):
    return argv[argv.index(name) + 1] if name in argv else default


OUT = opt('--out')
RENDER = opt('--render')
VIEWS = opt('--views', opt('--view', 'hero'))
SAMPLES = int(opt('--samples', '64'))
SIZE = tuple(int(v) for v in opt('--size', '1600x900').split('x'))
TEX = opt('--tex')
VARIANT = opt('--variant', 'musashino')

L = 20.0                # car length over the couplers
BOGIE_Z = 6.9           # bogie centres ±6.9 m (13,800 mm)
COUPLER_FACE = 10.0     # the cab car's front coupler face
PANTOGRAPH = (-7.40, -1)  # モハE231: main shaft z (raised head over the bogie centre), knee towards the car end
# name, kind, position along the train, turned round
CARS = (('car0', 'cab', 0.0, False), ('car1', 'middle', -L, False), ('car2', 'cab', -2 * L, True))

# game frame: eye, target, lens (mm, 36 mm sensor)
VIEWS_E231 = {
    'hero': ((-7.0, 3.6, 40.0), (0.2, 1.9, -2.0), 85),
    'head': ((0.25, 2.30, 27.0), (0.0, 2.0, 9.8), 100),
    'front34': ((6.0, 2.0, 17.5), (0.0, 1.8, 7.0), 40),
    'side': ((17.0, 1.8, -10.0), (0.0, 1.9, -10.0), 30),
    'side0': ((25.0, 1.9, 0.0), (0.0, 1.9, 0.0), 40),
    'low': ((6.0, 0.9, 15.0), (0.0, 1.3, 5.0), 30),
    'bogie': ((3.4, 0.75, 10.6), (0.0, 0.55, 6.9), 35),
    'roof': ((9.0, 8.5, -14.0), (0.0, 3.4, -28.0), 40),
    'rear34': ((-6.0, 2.6, -68.0), (0.0, 1.9, -44.0), 50),
    'skirt': ((1.4, 0.95, 13.8), (0.0, 0.7, 9.9), 50),
    # for side-by-side sheets with the reference photos
    'm04': ((-2.3, 2.3, 15.2), (-0.25, 1.85, 8.0), 41),
    'm19': ((1.25, 2.55, 15.8), (0.15, 2.0, 8.0), 33),
    'm14': ((-6.5, 2.4, 18.5), (-2.5, 1.7, 2.0), 28),
    'head2': ((-0.25, 2.30, -67.0), (0.0, 2.0, -49.8), 100),
    'num2': ((5.0, 1.45, -38.75), (0.0, 1.35, -38.75), 60),
    'num0': ((5.0, 1.45, -1.25), (0.0, 1.35, -1.25), 60),
    'num0r': ((-5.0, 1.45, -1.0), (0.0, 1.35, -1.0), 60),
    'num1': ((5.0, 1.45, -21.0), (0.0, 1.35, -21.0), 60),
    'm42': ((-4.6, 3.4, 33.0), (-0.6, 2.0, 5.0), 105),
    'jrR': ((-7.0, 1.75, -4.0), (0.0, 1.65, -4.94), 45),
    'jrL': ((7.0, 1.75, -4.0), (0.0, 1.65, -4.94), 45),
    'm10': ((-9.0, 4.4, 46.0), (-0.6, 2.1, 0.0), 120),
}


def materials(tex_dir):
    m = K.Materials()
    boxes = BD.add_materials(m, tex_dir)
    for mod in (RF, UF, BG, CP):
        if mod is not None:
            mod.add_materials(m)
    if RF is None or UF is None or BG is None or CP is None:
        m.add('ph_grey', '#55575a', roughness=0.7)
    return m, boxes


# Near-identical solid colours of the part modules share one material (≤ 30 materials per car): alias → kept one
ALIAS = {
    'ek_bellows': 'ek_under', 'er_dark': 'ek_under', 'eu_dark': 'ek_under', 'ec_rubber': 'ek_under',
    'ec_dark': 'ek_under',
    'er_metal': 'ek_frame', 'eu_steel': 'ek_frame', 'eb_dark': 'ek_frame',
    'ec_silver': 'ek_chrome', 'eu_hw': 'ek_chrome',
    'eu_fin': 'ek_steel',
    'ek_jamb': 'ek_end', 'eb_tread': 'ek_end',
    'ec_white': 'ek_skirt',
    'ec_rust': 'eb_rubber',
}


def _mats_view(mats):
    view = dict(mats)
    for a, t in ALIAS.items():
        if a in view and t in view:
            view[a] = view[t]
    return view


def tris(part):
    return sum(len(f.verts) - 2 for f in part.bm.faces)


def _ph_bogie(gear, zc):
    for s in (-1, 1):
        gear.box('ph_grey', s * 1.05 - 0.1, s * 1.05 + 0.1, 0.30, 0.80, zc - 1.4, zc + 1.4)
        for za in (zc - 1.05, zc + 1.05):
            gear.cylinder('ph_grey', (s * 0.75, 0.43, za), 0.43, 0.12, axis='x', segments=20)


def build_car(m, boxes, name, kind, z_offset, flip):
    cab = kind == 'cab'
    root = K.car_empty(name, z_offset)
    if flip:
        root.rotation_euler = (0, 0, math.pi)
    count = {}

    body = BD.UVPart(f'{name}_body')
    BD.build(body, kind)
    if cab:
        BD.cab_fittings(body, boxes)
        BD.skirt(body)
    BD.side_fittings(body, boxes, kind)
    BD.atlas_uvs(body, name)
    BD.number_decals(body, name, kind)
    count['body'] = tris(body)

    gear = K.Part(f'{name}_gear')
    n = tris(gear)
    if RF is not None:
        RF.air_conditioner(gear, 0.0)
        if cab:
            RF.cab_roof_details(gear, BD.CAB_JOIN + 0.3)
            RF.roof_details(gear, -BD.END, BD.CAB_JOIN, end_boxes=(-9.35,))
        else:
            zc, knee = PANTOGRAPH
            RF.pantograph(gear, zc, knee=knee)
            RF.pantograph_gear(gear, zc, knee=knee)
            RF.roof_details(gear, -BD.END, BD.END)
    else:
        gear.box('ph_grey', -0.95, 0.95, 3.60, 4.05, -2.3, 2.3)
    count['roof'] = tris(gear) - n
    n = tris(gear)
    if UF is not None:
        if cab:
            UF.underfloor_tc(gear, car='E230' if flip else 'E231')
        else:
            UF.underfloor_m(gear)
    else:
        gear.box('ph_grey', -1.2, 1.2, 0.45, 0.98, -4.6, 4.6)
    count['underfloor'] = tris(gear) - n
    n = tris(gear)
    for zc, facing in ((BOGIE_Z, 1), (-BOGIE_Z, -1)):
        if BG is not None:
            if cab:
                BG.bogie(gear, zc, 'TR246M' if zc > 0 else 'TR246', facing=facing)
            else:
                BG.bogie(gear, zc, 'DT61G', facing=facing)
        else:
            _ph_bogie(gear, zc)
    count['bogies'] = tris(gear) - n
    n = tris(gear)
    if CP is not None:
        if cab:
            lv = getattr(BD, 'LIVERY', {})      # joban: electric coupler; tozai (E231-800): no corner boxes
            CP.front_coupler(gear, COUPLER_FACE, corner_boxes=lv.get('corner_boxes', True),
                             electric=lv.get('electric_coupler', False))
        if name != 'car2':      # one bar coupler per gap, carried by the car ahead
            CP.intercar_coupler(gear, -L / 2)
    count['couplers'] = tris(gear) - n

    mats = _mats_view(m.mats)
    body.build(root, mats)
    gear.build(root, mats)
    print(f'TRIS {name}: {sum(count.values())} ' + ' '.join(f'{k} {v}' for k, v in count.items()))
    return root


def main():
    K.clear_scene()
    BD.set_variant(VARIANT)
    tex_dir = os.path.join(TEX, VARIANT) if TEX else tempfile.mkdtemp(prefix='e231-tex-')
    m, boxes = materials(tex_dir)
    if RF is not None and hasattr(RF, 'set_roof_profile'):
        RF.set_roof_profile([(x, y) for x, y, _nx, _ny in BD.half_profile()])
    cars = [build_car(m, boxes, *c) for c in CARS]
    print('MATERIALS', len({id(v) for v in _mats_view(m.mats).values()}))
    if OUT:
        K.export_glb(OUT, cars)
    if RENDER:
        import showcase as S
        S.scene(z0=-62.0, z1=12.0)
        S.VIEWS.update(VIEWS_E231)
        # extra cameras for checks: --cams 'name:ex,ey,ez,tx,ty,tz,lens;name2:...' (game frame)
        for spec in filter(None, (opt('--cams') or '').split(';')):
            name, nums = spec.split(':')
            v = [float(t) for t in nums.split(',')]
            S.VIEWS[name] = (tuple(v[0:3]), tuple(v[3:6]), v[6])
        LIT = {'hero', 'head', 'front34', 'low', 'skirt', 'm04', 'm10', 'm14', 'm42'}
        views = VIEWS.split(',')
        if RENDER.endswith('.png'):
            S.headlamps(views[0] in LIT, material=BD.P + 'lamp')
            S.render(views[0], RENDER, size=SIZE, samples=SAMPLES)
        else:
            os.makedirs(RENDER, exist_ok=True)
            for v in views:
                S.headlamps(v in LIT, material=BD.P + 'lamp')
                S.render(v, os.path.join(RENDER, f'{v}.png'), size=SIZE, samples=SAMPLES)


main()
