"""
JR East E235 series 0 (Yamanote Line, 2015–), three cars as the game shows them: クハE235 (cab, leading) + モハE235
(the motor car with the single-arm pantograph, 9号車 of the 11-car set) + クハE234 (cab, trailing, turned round), built
from numbers and our own painted textures (no outside model, no photo pixels, no logos). Run with Blender 5.x:

  blender --background --factory-startup --python tools/blender/e235.py -- --out <file.glb> [--variant sobu]
      [--render <dir> [--views hero,head,...] [--samples N] [--size WxH]] [--tex <dir>]

--variant sobu builds the E235-1000 of the Yokosuka / Sobu Rapid line (横須賀・総武快速線) instead: the same meshes
and nodes, only the paint and the signs differ (cream and blue bands along the sides, stainless doors, the blue face
with its cream-to-blue halftone, displays 横須賀・総武快速線, set F-35: クハE235-1035 + モハE235-1035 + クハE234-1035).

The parts live in tools/blender/parts/ (each module's docstring lists its figures and where they come from):
  e235_body        body shell, cab face, doors, windows, painted side / door / face textures, LED displays, fittings
  e235_roof        AU737 air conditioner, the pantograph (roof_n1000's single arm, lowered) and its gear, antennas
  e235_underfloor  SIV, battery, brake control, main converter, tanks, under frame (underfloor_n1000's helpers)
  e235_bogie       DT80 (motor) / TR264 (trailer) bolsterless bogies on 1,067 mm gauge
  e235_coupler     the skirt, the tight-lock coupler and vent boxes (coupler_n1000's pieces), the bar couplers
Signs (LED displays, car numbers): tools/blender/textures/e235/ (e235_textures.py, Noto Sans CJK JP, OFL).
--render renders the train on a trackside (showcase.py, its rails moved to 1,067 mm gauge) for checking.

Car frame: each car's origin is its bogie midpoint on the rail top; the cars are 20.0 m apart (20,000 mm over the
coupler faces), the bogie centres ±6.9 m (13.8 m, line-scan photo).
"""
import math
import os
import sys
import tempfile

sys.dont_write_bytecode = True  # no __pycache__ in the repo
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, 'parts'))
import bpy  # noqa: E402

import train_kit as K  # noqa: E402
import body_n1000 as BD  # noqa: E402
import e235_body as EB  # noqa: E402
import e235_bogie as BG  # noqa: E402
import e235_coupler as CP  # noqa: E402
import e235_roof as RF  # noqa: E402
import e235_underfloor as UF  # noqa: E402
import roof_n1000 as RN  # noqa: E402

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []


def opt(name, default=None):
    return argv[argv.index(name) + 1] if name in argv else default


OUT = opt('--out')
RENDER = opt('--render')
VIEWS = opt('--views', opt('--view', 'hero'))
SAMPLES = int(opt('--samples', '64'))
SIZE = tuple(int(v) for v in opt('--size', '1600x900').split('x'))
TEX = opt('--tex')
VARIANT = opt('--variant', 'yamanote')

BOGIE_Z = 6.9
COUPLER_FACE = 10.0
CAR_GAP = 20.0
PANTOGRAPH = (-7.4, -1)        # モハE235: main shaft z, knee towards −z (the car end)
AC_Z = {'cab': -0.8, 'middle': 1.0}
CARS = (('car0', 'cab', 0.0, False), ('car1', 'middle', -CAR_GAP, False), ('car2', 'cab', -2 * CAR_GAP, True))

# game frame: eye, target, lens (mm, 36 mm sensor)
VIEW_SET = {
    'hero': ((-8.2, 3.4, 40.0), (0.2, 1.9, -4.0), 85),
    'head': ((0.25, 2.3, 27.0), (0.0, 2.15, 9.8), 100),
    'front34': ((5.8, 2.0, 17.5), (0.0, 1.8, 7.0), 40),
    'side': ((19.0, 1.7, -1.0), (0.0, 1.8, -1.0), 28),
    'side_moha': ((19.0, 1.7, -20.0), (0.0, 1.9, -20.0), 28),
    'low': ((6.4, 0.9, 15.0), (0.0, 1.3, 4.0), 30),
    'bogie': ((3.0, 0.8, 9.9), (0.2, 0.6, 6.9), 32),
    'roof': ((8.5, 8.5, -5.0), (0.0, 3.4, -22.0), 40),
    'rear34': ((-6.0, 2.6, -66.0), (0.0, 1.9, -44.0), 50),
    'skirt': ((1.4, 0.9, 13.8), (0.0, 0.7, 9.8), 50),
    'panto': ((5.5, 6.2, -16.0), (0.0, 4.0, -27.0), 50),
    'sign': ((5.0, 2.8, 2.0), (1.47, 3.0, 0.0), 45),          # the side destination display of car0 (left side)
    # for the sheets with the reference photos: head-on (S5A-0043) and a 3/4 view from ahead and to the right
    'match_head': ((0.0, 2.2, 34.0), (0.0, 2.0, 9.8), 135),
    'match34': ((-4.5, 3.2, 32.0), (-0.4, 1.7, 5.0), 95),
    'match_sobu': ((2.6, 3.0, 40.0), (0.25, 2.0, 9.5), 150),     # like the E235-1000 photo "Series-E235-1000 F35"
}
LIT = {'hero', 'head', 'front34', 'low', 'skirt', 'match_head', 'match34', 'match_sobu', 'bogie'}
TAIL = {'rear34'}


def materials(tex_dir):
    m = K.Materials()
    boxes = EB.add_materials(m, tex_dir)
    for mod in (RF, UF, BG, CP):
        mod.add_materials(m)
    return m, boxes


# gear materials folded into the body's / each other's (≤ 30 materials per car): the helper modules' dark, rubber,
# steel and bright bits look the same at game distance
ALIAS = {
    'uf_dark': 'e_dark', 'cp_dark': 'e_dark', 'ec_back': 'e_dark', 'rf_dark': 'e_dark', 'er_grille': 'e_dark',
    'eu_fan': 'e_dark', 'cp_rubber': 'e_bellows', 'eb_rubber': 'e_bellows', 'uf_steel': 'e_frame', 'cp_grime': 'e_frame',
    'eb_dark': 'e_frame', 'uf_hw': 'e_sill', 'cp_worn': 'e_sill', 'eb_plate': 'e_sill', 'cp_steel': 'eb_wheel',
    'cp_cover': 'eb_wheel', 'uf_lid': 'uf_body', 'rf_ac': 'er_ac', 'eb_disc': 'eb_tread',
}


def alias(part):
    names = [ALIAS.get(s, s) for s in part.slots]
    uniq = list(dict.fromkeys(names))
    idx = [uniq.index(n) for n in names]
    for f in part.bm.faces:
        f.material_index = idx[f.material_index]
    part.slots = uniq


def tris(part):
    return sum(len(f.verts) - 2 for f in part.bm.faces)


def build_car(m, boxes, name, kind, z_offset, flip):
    """kind: 'cab' (cab at +z: クハE235 / クハE234) or 'middle' (モハE235)"""
    cab = kind == 'cab'
    root = K.car_empty(name, z_offset)
    if flip:
        root.rotation_euler = (0, 0, math.pi)
    count = {}

    body = BD.UVPart(f'{name}_body')
    EB.build(body, kind, name)
    if cab:
        EB.cab_fittings(body, boxes)
    EB.side_fittings(body, boxes, kind)
    count['body'] = tris(body)

    gear = K.Part(f'{name}_gear')
    n = tris(gear)
    RF.air_conditioner(gear, AC_Z[kind])
    if cab:
        RF.cab_roof_details(gear)
    else:
        RF.pantograph(gear, *PANTOGRAPH)
    count['roof'] = tris(gear) - n
    n = tris(gear)
    if cab:
        UF.underfloor_cab(gear)
    else:
        UF.underfloor_motor(gear)
    count['underfloor'] = tris(gear) - n
    n = tris(gear)
    for zc, facing in ((BOGIE_Z, 1), (-BOGIE_Z, -1)):
        BG.bogie(gear, zc, motor=not cab, facing=facing, parking=cab and zc > 0)
    count['bogies'] = tris(gear) - n
    n = tris(gear)
    if cab:
        CP.skirt(gear)
        CP.front_coupler(gear, COUPLER_FACE)
    if name != 'car2':      # one bar coupler per gap, carried by the car ahead
        CP.intercar_coupler(gear, -EB.END - 0.25)
    count['couplers'] = tris(gear) - n

    alias(gear)
    used = set(body.slots) | set(gear.slots)
    body.build(root, m.mats)
    gear.build(root, m.mats)
    print(f'TRIS {name}: {sum(count.values())} ' + ' '.join(f'{k} {v}' for k, v in count.items()) + f' | materials {len(used)}')
    return root


def narrow_gauge():
    """showcase lays standard-gauge rails: move them in to 1,067 mm"""
    d = 0.7175 - 0.5335
    for name in ('rails', 'railheads'):
        o = bpy.data.objects.get(name)
        if o is None:
            continue
        for v in o.data.vertices:
            v.co.x += -d if v.co.x > 0 else d


def lamps(view):
    import showcase as S
    S.headlamps(view in LIT, material='e_lamp', strength=40.0)
    t = bpy.data.materials.get('e_tail')
    if t is not None:
        p = t.node_tree.nodes.get('Principled BSDF')
        p.inputs['Emission Color'].default_value = (1.0, 0.05, 0.03, 1.0)
        p.inputs['Emission Strength'].default_value = 3.0 if view in TAIL else 0.0


def main():
    K.clear_scene()
    EB.set_variant(VARIANT)
    tex_dir = TEX or tempfile.mkdtemp(prefix='e235-tex-')
    m, boxes = materials(tex_dir)
    RN.set_roof_profile([(x, y) for x, y, _nx, _ny in EB.half_profile()])
    cars = [build_car(m, boxes, *c) for c in CARS]
    print('MATERIALS', len(m.mats))
    if OUT:
        K.export_glb(OUT, cars)
    if RENDER:
        import showcase as S
        S.scene()
        narrow_gauge()
        bpy.context.scene.render.threads = 4
        views = VIEWS.split(',')
        if RENDER.endswith('.png'):
            lamps(views[0])
            S.render(VIEW_SET.get(views[0], views[0]), RENDER, size=SIZE, samples=SAMPLES)
        else:
            os.makedirs(RENDER, exist_ok=True)
            for v in views:
                lamps(v)
                S.render(VIEW_SET[v] if v in VIEW_SET else v, os.path.join(RENDER, f'{v}.png'), size=SIZE, samples=SAMPLES)


main()
