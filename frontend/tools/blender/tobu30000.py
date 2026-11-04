"""
Tobu 30000 series (東武30000系) as the 10-car Tojo Line sets run today (stainless body, FRP cab front, full-colour LED
displays, no electric coupler), three cars as the game shows them, built from numbers and our own painted textures
(no outside model, no photo pixels):

  car0  クハ31612  Tc1, leading cab car of 31612F (the Ikebukuro end of 31612F+31412F)
  car1  モハ32612  M1, the next car: VVVF + CP, two single-arm pantographs (one at each end)
  car2  クハ34412  Tc2, the Ogawamachi-end cab car of the 4-car half (31412F), turned round

Run with Blender 5.x:

  blender --background --factory-startup --python tools/blender/tobu30000.py -- --out <file.glb>
      [--variant isesaki] [--render <dir> [--views hero,head,...] [--samples N] [--size WxH]] [--tex <dir>]

Variants (materials / textures only; meshes, nodes and UVs identical):
  tojo (default)  the Tojo Line today: full-colour LED, 急行 (red field) + 東上線 / TOJO LINE
  isesaki         the Isesaki Line era with the Hanzomon line through service (1996-2011): 3-colour LED, 急行 in a red
                  frame + 伊勢崎線 in orange. The two-tier electric coupler the sets carried then is left out (it would
                  need geometry the Tojo version does not have).

The parts live in tools/blender/parts/ (each module's docstring lists its figures and where they come from):
  tobu30000_body        body shell, cab front, doors, windows, painted side / face textures, LED displays, numbers
  tobu30000_roof        air conditioners, the cab roof's antennas; pantographs from roof_n1000 at this roof's height
  tobu30000_underfloor  VVVF, SIV, CP, tanks, ATS / cable boxes, under frame
  tobu30000_bogie       SS138 / SS038 monolink bolsterless bogies
  tobu30000_coupler     the skirt, the tight-lock coupler and the gear behind the skirt, the bar couplers
Signs (LED displays, car number outlines): tools/blender/textures/tobu30000/ (tobu30000_textures.py, Noto Sans CJK JP,
OFL). --render renders the train on a trackside (showcase.py) for checking.
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
import tobu30000_body as BD  # noqa: E402
import tobu30000_bogie as BG  # noqa: E402
import tobu30000_coupler as CP  # noqa: E402
import tobu30000_roof as RF  # noqa: E402
import tobu30000_underfloor as UF  # noqa: E402

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []


def opt(name, default=None):
    return argv[argv.index(name) + 1] if name in argv else default


OUT = opt('--out')
RENDER = opt('--render')
VIEWS = opt('--views', opt('--view', 'hero'))
SAMPLES = int(opt('--samples', '64'))
SIZE = tuple(int(v) for v in opt('--size', '1600x900').split('x'))
TEX = opt('--tex')
VARIANT = opt('--variant', 'tojo')     # 'tojo' (today) or 'isesaki' (1996-2011): displays only, same geometry
assert VARIANT in ('tojo', 'isesaki'), VARIANT

CAR_LENGTH = 20.0       # over the couplers
BOGIE_Z = 6.90          # bogie centres ±6.9 m (13.8 m: estimate, see tobu30000_bogie)
COUPLER_FACE = 10.12    # the cab car's coupler face
# name, kind, position along the train, turned round, car number
CARS = (('car0', 'cab', 0.0, False, '31612'), ('car1', 'middle', -CAR_LENGTH, False, '32612'),
        ('car2', 'cab', -2 * CAR_LENGTH, True, '34412'))


def materials(tex_dir):
    m = K.Materials()
    boxes = BD.add_materials(m, tex_dir, VARIANT)
    for mod in (RF, UF, BG, CP):
        mod.add_materials(m)
    return m, boxes


# the gear's small parts share a few materials, so a car stays within 30 (contract budget)
GEAR_MERGE = {
    'tc_dark': 'tb_black', 'tu_dark': 'tb_black', 'tr_dark': 'tb_black', 'cp_dark': 'tb_black', 'rf_dark': 'tb_black',
    'cp_rubber': 'tb_rubber', 'tg_rubber': 'tb_rubber',
    'tc_steel': 'tg_dark', 'tu_steel': 'tg_dark', 'tr_metal': 'tg_dark', 'cp_grime': 'tg_dark',
    'cp_worn': 'tb_chrome', 'tu_hw': 'tb_chrome', 'cp_steel': 'tc_skirt',
    'tu_lid': 'tu_body', 'tc_box': 'tu_light', 'tg_shoe': 'tc_red', 'rf_ac': 'tr_ac',
}


def merge_slots(part, remap):
    names = [remap.get(n, n) for n in part.slots]
    new = list(dict.fromkeys(names))
    idx = [new.index(n) for n in names]
    for f in part.bm.faces:
        f.material_index = idx[f.material_index]
    part.slots = new


def tris(part):
    return sum(len(f.verts) - 2 for f in part.bm.faces)


def build_car(m, boxes, name, kind, z_offset, flip, number):
    cab = kind == 'cab'
    root = K.car_empty(name, z_offset)
    if flip:
        root.rotation_euler = (0, 0, math.pi)
    count = {}
    body = BD.UVPart(f'{name}_body')
    BD.build(body, kind)
    if cab:
        BD.cab_fittings(body, boxes, number)
    BD.side_fittings(body, boxes, kind, number)
    count['body'] = tris(body)

    gear = K.Part(f'{name}_gear')
    n = tris(gear)
    RF.roof(gear, kind, nose=-1 if flip else 1)   # rounded AC ends towards Ikebukuro
    count['roof'] = tris(gear) - n
    n = tris(gear)
    UF.underfloor(gear, kind)
    count['underfloor'] = tris(gear) - n
    n = tris(gear)
    for zc in (BOGIE_Z, -BOGIE_Z):
        BG.bogie(gear, zc, motor=not cab, facing=1 if zc > 0 else -1)
    count['bogies'] = tris(gear) - n
    n = tris(gear)
    if cab:
        CP.front(gear, COUPLER_FACE)
    if name != 'car2':      # one bar coupler per gap, carried by the car ahead
        CP.intercar_coupler(gear, -CAR_LENGTH / 2)
    count['couplers+skirt'] = tris(gear) - n

    merge_slots(gear, GEAR_MERGE)
    body.build(root, m.mats)
    gear.build(root, m.mats)
    mats = {s.material.name for o in root.children for s in o.material_slots if s.material}
    print(f'TRIS {name}: {sum(count.values())} ' + ' '.join(f'{k} {v}' for k, v in count.items()) + f' (materials {len(mats)})')
    return root


def main():
    K.clear_scene()
    tex_dir = TEX or tempfile.mkdtemp(prefix='tobu30000-tex-')
    m, boxes = materials(tex_dir)
    RF.set_roof_profile(BD.roof_half())
    cars = [build_car(m, boxes, *c) for c in CARS]
    used = set()
    for c in cars:
        for o in c.children:
            used.update(s.material.name for s in o.material_slots if s.material)
    print('MATERIALS', len(used))
    if OUT:
        K.export_glb(OUT, cars)
    if RENDER:
        import showcase as S
        S.scene(z0=-75.0, z1=45.0)
        bpy_scene_threads()
        lit = {'hero', 'head', 'front34', 'low', 'skirt', 'match_a', 'match_b'}
        views = VIEWS.split(',')
        if RENDER.endswith('.png'):
            v = views[0]
            S.headlamps(v in lit, material='tb_head')
            S.render(view(v), RENDER, size=SIZE, samples=SAMPLES)
        else:
            os.makedirs(RENDER, exist_ok=True)
            for v in views:
                S.headlamps(v in lit, material='tb_head')
                S.render(view(v), os.path.join(RENDER, f'{v}.png'), size=SIZE, samples=SAMPLES)


def bpy_scene_threads():
    import bpy
    sc = bpy.context.scene
    sc.render.threads_mode = 'FIXED'
    sc.render.threads = 4


# game frame: eye, target, lens (mm) — placed for 20 m cars
VIEWS_T = {
    'hero': ((-8.0, 3.2, 38.0), (0.3, 1.9, -4.0), 85),
    'head': ((0.0, 2.3, 27.0), (0.0, 2.0, 9.8), 105),
    'front34': ((-5.6, 2.0, 16.5), (0.0, 1.9, 7.0), 40),
    'side': ((-15.0, 1.8, -1.0), (0.0, 1.9, -1.0), 30),
    'low': ((-6.0, 0.9, 14.5), (0.0, 1.3, 4.0), 30),
    'bogie': ((-3.4, 0.75, 9.8), (0.0, 0.55, 6.6), 35),
    'bogie_m': ((-3.4, 0.75, -13.1), (0.0, 0.55, -16.4), 35),
    'roof': ((-8.5, 8.5, -6.0), (0.0, 3.6, -22.0), 40),
    'rear34': ((-5.5, 2.6, -66.0), (0.0, 1.9, -44.0), 50),
    'skirt': ((-1.4, 0.9, 13.6), (0.0, 0.7, 9.9), 50),
    'cabside': ((-6.0, 2.0, 12.5), (0.0, 1.9, 7.5), 50),
    # like the photos: 31612 (long lens, ahead and to the right of the train), Ikebukuro 31613 (head-on, close)
    'match_a': ((-6.2, 1.55, 52.0), (-0.6, 1.95, 2.0), 150),
    'match_b': ((0.9, 2.55, 15.6), (0.0, 1.35, 9.8), 26),    # portrait 720x960
}


def view(v):
    return VIEWS_T[v] if v in VIEWS_T else v


main()
