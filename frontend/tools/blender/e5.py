"""
JR East E5 series Shinkansen "Hayabusa" (E5系 はやぶさ), three cars as the game shows them: E523 (car 1, the Tokyo
end's nose), E525 (a pantograph car, PS208) and E514 (car 10, Gran Class, the other nose, turned round). Built from
numbers and our own painted textures (no outside model, no photo pixels). Run with Blender 5.x:

  blender --background --factory-startup --python tools/blender/e5.py -- --out <file.glb> [--variant h5]
      [--render <dir> [--views hero,head,...] [--samples N] [--size WxH] [--night]] [--tex <dir>]

--variant h5 builds JR Hokkaido's H5 (北海道新幹線): the same cars with the 彩香パープル belt, the
H5 logo on all three cars, numbers H523-1 / H525-101 / H514-1 and 北海道新幹線 on the displays (textures/e5/h5/).

Parts (tools/blender/parts/, each module's docstring lists its figures and where they come from):
  e5_shape       the body section and the nose's sections along it, the canopy, the livery lines
  e5_body        the shells (loft), doors, gangway ends and hoods, the painted atlas, lamps, wipers, displays
  e5_roof        PS208 pantograph, its noise shields and insulators, roof hatches and antennas
  e5_under       underframe and equipment between the skirts, the snow plough, the bar couplers
  e5_bogie       DT209 / TR7008 bolsterless bogies (disc brakes, yaw dampers)
Signs (side LED displays, car numbers with the JR mark) and the service logos: tools/blender/textures/e5/ and
textures/e5/h5/ (e5_textures.py: our own drawings and Noto Sans CJK JP, OFL).

Cars (game car frame, origin at the bogie midpoint, bogie centres ±8.75 = 17.5 m apart):
  car0 E523 at z = 0: nose tip +14.0, rear gangway face −12.25, rear coupler face −12.5 (26.5 m; the leading bogie
       5.25 m behind the tip, the trailing one 3.75 m ahead of the coupler);
  car1 E525 at z = −25.0: gangway faces ±12.25, couplers ±12.5 (25.0 m; 3.75 m overhangs);
  car2 E514 at z = −50.0, turned round: as car0 in its own frame, its nose tip at z = −64.0 in the train.
  TrainInfo.consist: [{length 26.5, bogies 17.5, front 5.25}, {25, 17.5, 3.75}, {26.5, 17.5, 3.75}].
"""
import math
import os
import sys
import tempfile

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, 'parts'))
import train_kit as K  # noqa: E402
import body_n1000 as BD  # noqa: E402
import e5_shape as S  # noqa: E402
import e5_body as EB  # noqa: E402

try:
    import e5_roof as RF  # noqa: E402
except ImportError:
    RF = None
try:
    import e5_under as UF  # noqa: E402
except ImportError:
    UF = None
try:
    import e5_bogie as BG  # noqa: E402
except ImportError:
    BG = None

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []


def opt(name, default=None):
    return argv[argv.index(name) + 1] if name in argv else default


OUT = opt('--out')
RENDER = opt('--render')
VIEWS = opt('--views', opt('--view', 'hero'))
SAMPLES = int(opt('--samples', '64'))
SIZE = tuple(int(v) for v in opt('--size', '1600x900').split('x'))
TEX = opt('--tex')
CLAY = '--clay' in argv
NIGHT = '--night' in argv           # a dark scene with the head lamps lit
VARIANT = opt('--variant', 'e5')    # 'e5' (JR East) or 'h5' (JR Hokkaido)

CAR_Z = {'car0': 0.0, 'car1': -25.0, 'car2': -50.0}
CARS = (('car0', 'e523', False), ('car1', 'e525', False), ('car2', 'e514', True))


def tris(part):
    return sum(len(f.verts) - 2 for f in part.bm.faces)


def build_parts(name, kind):
    """the car's parts (not yet turned into meshes) and the triangle counts per family"""
    count = {}
    shell = EB.Shell(kind)
    body = BD.UVPart(f'{name}_body', sharp=50.0)
    shell.build(body)
    count['shell'] = tris(body)
    n = tris(body)
    EB.cab_fittings(body, kind) if hasattr(EB, 'cab_fittings') else None
    for z_end, sign in ((-S.END, -1),) + (((S.END, 1),) if kind == 'e525' else ()):
        EB.hood(body, z_end, sign)
    count['fittings'] = tris(body) - n
    gear = K.Part(f'{name}_gear')
    n = 0
    if RF:
        RF.roof(gear, kind)
        count['roof'] = tris(gear) - n
        n = tris(gear)
    if UF:
        UF.underfloor(gear, kind)
        count['underfloor'] = tris(gear) - n
        n = tris(gear)
    if BG:
        BG.bogies(gear, kind)
        count['bogies'] = tris(gear) - n
        n = tris(gear)
    return shell, body, gear, count


def main():
    EB.set_variant(VARIANT)
    K.clear_scene()
    tex_dir = TEX or tempfile.mkdtemp(prefix='e5-tex-')
    built = {}
    for name, kind, flip in CARS:
        built[name] = build_parts(name, kind)
    m = K.Materials()
    shells = {kind: built[name][0] for name, kind, _ in CARS}
    EB.add_materials(m, tex_dir, shells)
    for mod in (RF, UF, BG):
        if mod:
            mod.add_materials(m)
    if CLAY:
        clay = m.add('clay', '#b8b8b8', roughness=0.5)
        for k in list(m.mats):
            m.mats[k] = clay
    roots = []
    for name, kind, flip in CARS:
        shell, body, gear, count = built[name]
        root = K.car_empty(name, CAR_Z[name])
        if flip:
            root.rotation_euler = (0, 0, math.pi)
        body.build(root, m.mats)
        if gear.bm.faces:
            gear.build(root, m.mats)
        else:
            gear.bm.free()
        print(f'TRIS {name}: {sum(count.values())} ' + ' '.join(f'{k} {v}' for k, v in count.items()))
        roots.append(root)
    print('MATERIALS', len({id(v) for v in m.mats.values()}))
    for x, y, z in EB.lamp_centres():
        print(f'LAMP x {x:+.3f} y {y:.3f} z {z:.3f} (d {S.NOSE_TIP - z:.3f}) lens r {EB.LENS_R} bezel r {EB.BEZEL_R}')
    print(f'SIDE WINDOWS y {EB.WIN_Y[0]:.2f}..{EB.WIN_Y[1]:.2f} x {EB.side_x("e523", -5.0, EB.WIN_Y[0]):.3f}..'
          f'{EB.side_x("e523", -5.0, EB.WIN_Y[1]):.3f}')
    if OUT:
        K.export_glb(OUT, roots)
    if RENDER:
        import showcase as S2
        if NIGHT:
            S2.scene(sun_elevation=3.0, z0=-80.0, z1=30.0, sky_strength=0.006, sun_energy=0.03)
            S2.grade(exposure=0.8)
        else:
            S2.scene(z0=-80.0, z1=30.0)
        sc = S2.bpy.context.scene
        sc.render.threads_mode = 'FIXED'
        sc.render.threads = 4
        views = VIEWS.split(',')
        os.makedirs(RENDER if not RENDER.endswith('.png') else os.path.dirname(RENDER), exist_ok=True)
        for v in views:
            spec = view_spec(v)
            S2.headlamps(v in LIT or NIGHT, material=EB.P + 'lamp', strength=60.0 if NIGHT else 40.0)
            path = RENDER if RENDER.endswith('.png') else os.path.join(RENDER, v.replace(':', '_').replace('/', '_') + '.png')
            S2.render(spec, path, size=SIZE, samples=SAMPLES)


# game frame: eye, target, lens (the train: car0 nose at z = +14, car2's nose at z = −64)
VIEWS_E5 = {
    'hero': ((-9.0, 3.6, 46.0), (0.3, 1.9, 0.0), 70),
    'head': ((0.3, 2.6, 60.0), (0.0, 1.9, 13.0), 135),
    'front34': ((7.5, 2.6, 26.0), (0.0, 1.6, 8.0), 40),
    'side': ((40.0, 1.9, -1.0), (0.0, 1.9, -1.0), 50),
    'sidenose': ((28.0, 1.8, 6.0), (0.0, 1.8, 6.0), 50),
    'top': ((14.0, 22.0, 4.0), (0.0, 1.5, 4.0), 40),
    'low': ((6.0, 0.9, 24.0), (0.0, 1.2, 10.0), 32),
    'bogie': ((3.4, 0.16, -3.6), (0.0, 0.42, -8.75), 30),
    'roof': ((9.0, 8.5, -6.0), (0.0, 3.8, -16.0), 40),
    'rear34': ((-7.0, 3.0, -86.0), (0.0, 1.8, -58.0), 50),
    'skirt': ((3.0, 0.55, 17.5), (0.0, 0.55, 12.0), 35),
    'gangway': ((3.6, 0.5, -9.0), (0.0, 0.9, -12.5), 35),
}
LIT = {'hero', 'head', 'front34', 'low', 'skirt', 'sidenose', 'top'}


def view_spec(v):
    if v in VIEWS_E5:
        return VIEWS_E5[v]
    if v.startswith('cam:'):
        a = [float(t) for t in v[4:].split('/')]
        return ((a[0], a[1], a[2]), (a[3], a[4], a[5]), a[6])
    raise KeyError(v)


main()
