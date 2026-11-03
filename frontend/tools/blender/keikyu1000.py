"""
Keikyu New 1000 series, 1st batch (2002, Siemens GTO "ドレミファ" inverter; painted aluminium body), three cars
Muc + Tpu + Msc as the game shows them, built from numbers and our own painted textures (no outside model, no photo
pixels). Run with Blender 5.x:

  blender --background --factory-startup --python tools/blender/keikyu1000.py -- --out <file.glb>
      [--render <dir> [--views hero,head,...] [--samples N] [--size WxH]] [--tex <dir>]

The parts live in tools/blender/parts/ (each module's docstring lists its figures and where they come from):
  body_n1000      body shell, cab face, doors, windows, painted side / face / skirt textures, LED displays, skirt
  roof_n1000      air conditioners, PT7117-A pantographs and their gear, antennas, drip rails
  underfloor_n1000  traction container, SIV, CP, tanks, under frame
  bogie_th2100    TH-2100AM / AT bogies
  coupler_n1000   the tight-lock coupler in the skirt, the bar couplers between the cars
Signs (LED displays, car numbers, lamp units): tools/blender/textures/keikyu1000/ (keikyu1000_textures.py, Noto Sans
CJK JP, OFL). --render renders the train on a trackside (showcase.py) for checking and for the owner.
"""
import math
import os
import sys
import tempfile

sys.dont_write_bytecode = True  # no __pycache__ in the repo
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, 'parts'))
import train_kit as K  # noqa: E402
import body_n1000 as BD  # noqa: E402
import bogie_th2100 as BG  # noqa: E402
import coupler_n1000 as CP  # noqa: E402
import roof_n1000 as RF  # noqa: E402
import underfloor_n1000 as UF  # noqa: E402

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []


def opt(name, default=None):
    return argv[argv.index(name) + 1] if name in argv else default


OUT = opt('--out')
RENDER = opt('--render')
VIEWS = opt('--views', opt('--view', 'hero'))
SAMPLES = int(opt('--samples', '64'))
SIZE = tuple(int(v) for v in opt('--size', '1600x900').split('x'))
TEX = opt('--tex')

BOGIE_Z = 6.0           # bogie centres ±6.0 m (estimate, see bogie_th2100)
COUPLER_FACE = 9.0      # the cab car's coupler face: cars 18.0 m over the couplers
PANTOGRAPHS = ((7.1, 1), (-7.1, -1))   # Tpu: one near each end, knee towards the car end (roof_n1000)
# name, kind, position along the train, turned round, car number on the face
CARS = (('car0', 'cab', 0.0, False, '001'), ('car1', 'middle', -18.0, False, None), ('car2', 'cab', -36.0, True, '008'))


def materials(tex_dir):
    m = K.Materials()
    boxes = BD.add_materials(m, tex_dir)
    for mod in (RF, UF, BG, CP):
        mod.add_materials(m)
    return m, boxes


def tris(part):
    return sum(len(f.verts) - 2 for f in part.bm.faces)


def build_car(m, boxes, name, kind, z_offset, flip, number):
    """kind: 'cab' (cab at +z, motor car) or 'middle' (Tpu: pantograph trailer)"""
    cab = kind == 'cab'
    root = K.car_empty(name, z_offset)
    if flip:
        root.rotation_euler = (0, 0, math.pi)
    count = {}

    body = BD.UVPart(f'{name}_body')
    BD.build(body, kind)
    if cab:
        BD.cab_fittings(body, boxes, number)
        BD.skirt(body)
    BD.side_fittings(body, boxes, kind)
    count['body'] = tris(body)

    gear = K.Part(f'{name}_gear')
    n = tris(gear)
    RF.air_conditioner(gear, 0.0)
    if cab:
        RF.cab_roof_details(gear, 8.4)
        RF.roof_details(gear, -BD.END, 8.0)
    else:
        for zc, knee in PANTOGRAPHS:
            RF.pantograph(gear, zc, knee=knee)
            RF.pantograph_gear(gear, zc, knee=knee)
        RF.roof_details(gear, -BD.END, BD.END)
    count['roof'] = tris(gear) - n
    n = tris(gear)
    if cab:
        UF.underfloor_motor_car(gear)
    else:
        UF.underfloor_trailer_pantograph(gear)
    count['underfloor'] = tris(gear) - n
    n = tris(gear)
    for zc, facing in ((BOGIE_Z, 1), (-BOGIE_Z, -1)):
        BG.bogie(gear, zc, motor=cab, facing=facing, ceramic_jet=cab and zc > 0)
    count['bogies'] = tris(gear) - n
    n = tris(gear)
    if cab:
        CP.front_coupler(gear, COUPLER_FACE)
    if name != 'car2':      # one bar coupler per gap, carried by the car ahead
        CP.intercar_coupler(gear, -BD.END - 0.25)
    count['couplers'] = tris(gear) - n

    body.build(root, m.mats)
    gear.build(root, m.mats)
    print(f'TRIS {name}: {sum(count.values())} ' + ' '.join(f'{k} {v}' for k, v in count.items()))
    return root


def main():
    K.clear_scene()
    tex_dir = TEX or tempfile.mkdtemp(prefix='keikyu1000-tex-')
    m, boxes = materials(tex_dir)
    RF.set_roof_profile([(x, y) for x, y, _nx, _ny in BD.half_profile()])
    cars = [build_car(m, boxes, *c) for c in CARS]
    print('MATERIALS', len(m.mats))
    if OUT:
        K.export_glb(OUT, cars)
    if RENDER:
        import showcase as S
        S.scene()
        LIT = {'hero', 'head', 'front34', 'low', 'skirt', 'match08', 'match02'}   # views of car0's face only
        if RENDER.endswith('.png'):
            S.headlamps(VIEWS.split(',')[0] in LIT)
            S.render(VIEWS.split(',')[0], RENDER, size=SIZE, samples=SAMPLES)
        else:
            os.makedirs(RENDER, exist_ok=True)
            for v in VIEWS.split(','):
                S.headlamps(v in LIT)
                S.render(v, os.path.join(RENDER, f'{v}.png'), size=SIZE, samples=SAMPLES)


main()
