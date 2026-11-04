"""
Subaru Impreza WRX STI sedan (GDB, 2004: the "tear-drop" face, stock, with the factory high rear wing) for TOUGE
NOCTURNE, game id `raijin`, built from published figures and our own measurements of photos (no outside model, no
photo pixels, no badges). Run with Blender 5.x:

  blender -t 4 --background --factory-startup --python tools/blender/cars/raijin.py -- --out <file.glb>
      [--render <dir> --views a,b --samples N --size WxH] [--night]

GLB contract (render/CarModel.ts): metres, +Y up, +Z forward, ground at y = 0, origin midway between the axles;
node `body` (all body meshes), wheel pivots wheel_fl/fr/rl/rr at the wheel centres with spin_* children (tyre, rim,
disc) and the calipers beside spin; materials named paint, glass, trim, chrome, headlight, taillight, tire, rim, brake.
Modules: raijin_kit (frames, meshes, export), raijin_shell (the body loft), raijin_parts (lamps, grille, wing,
mirrors, trim, interior), raijin_wheels (wheels, brakes), raijin_scene (check renders).
"""
import os
import sys

sys.dont_write_bytecode = True  # no __pycache__ in the repo
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import raijin_kit as K  # noqa: E402
import raijin_shell as SH  # noqa: E402
import raijin_cuts as CU  # noqa: E402
import raijin_parts as PT  # noqa: E402
import raijin_wheels as WH  # noqa: E402
import bpy  # noqa: E402

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []


def opt(name, default=None):
    return argv[argv.index(name) + 1] if name in argv else default


OUT = opt('--out')
RENDER = opt('--render')
VIEWS = opt('--views', 'front34')
SAMPLES = int(opt('--samples', '32'))
SIZE = tuple(int(v) for v in opt('--size', '1280x720').split('x'))
NIGHT = '--night' in argv


TEX = os.path.join(os.path.dirname(HERE), 'textures', 'raijin')


def materials():
    m = K.Materials()
    m.add('paint', '#1f47a8', metallic=0.55, roughness=0.34, coat=0.35)
    m.add('glass', '#0d1218', metallic=0.1, roughness=0.05)
    m.add('trim', '#111214', roughness=0.6)
    m.add('under', '#0b0b0c', roughness=0.9)
    m.add('chrome', '#d8dade', metallic=1.0, roughness=0.12)
    m.add('indicator', '#d98c3c', roughness=0.12, metallic=0.2)
    m.add('lamp_clear', '#c9ccd2', roughness=0.12, metallic=0.6)
    m.add('interior', '#232325', roughness=0.85)
    m.add('rim', '#b8964a', metallic=0.9, roughness=0.3)
    m.add('brake', '#c8a032', metallic=0.3, roughness=0.4)
    m.add('disc', '#6a6c70', metallic=0.85, roughness=0.45)
    load = lambda n: bpy.data.images.load(os.path.join(TEX, n))
    m.textured('headlight', load('headlight.png'), roughness=0.1, metallic=0.3, emissive_map=True)
    m.textured('taillight', load('taillight.png'), roughness=0.2, emissive_map=True)
    m.textured('plate', load('plate.png'), roughness=0.5)
    m.textured('grille', load('grille.png'), roughness=0.6)
    m.textured('tire', load('tire.png'), roughness=0.9)
    m.mats['cowl'] = m.mats['trim']
    return m


def lamp_report(root):
    """centre and size of each lamp lens (game frame), per side; also the exhaust tip"""
    out = {}
    for o in root.children_recursive:
        if o.type != 'MESH':
            continue
        names = [ms.name for ms in o.data.materials]
        for p in o.data.polygons:
            n = names[p.material_index] if p.material_index < len(names) else ''
            if n in ('headlight', 'taillight', 'indicator') or (o.name == 'exhaust' and n == 'chrome'):
                key = 'exhaust' if o.name == 'exhaust' else n
                for vi in p.vertices:
                    g = K.G(o.matrix_world @ o.data.vertices[vi].co)
                    out.setdefault((key, 'L' if g[0] > 0 else 'R'), []).append(g)
    res = {}
    for (k, side), pts in sorted(out.items()):
        lo = [min(p[i] for p in pts) for i in range(3)]
        hi = [max(p[i] for p in pts) for i in range(3)]
        c = [round((a + b) / 2, 3) for a, b in zip(lo, hi)]
        sz = [round(b - a, 3) for a, b in zip(lo, hi)]
        res[(k, side)] = c
        print('LAMP', k, side, 'centre', c, 'size', sz)
    return res


def main():
    K.clear_scene()
    m = materials()
    root = K.empty('raijin')
    body = K.empty('body', parent=root)
    shell = K.Part('shell')
    _, shell_rows = SH.build(shell)
    print('TRIS shell', shell.tris())
    shell_obj = shell.build(body, m.mats, sharp=50.0)
    print('NONMANIFOLD before cuts', CU.check_manifold(shell_obj))
    clean = K.Surface(K.bvh_of([shell_obj]))     # the uncut shell: lamps follow it over the grille's opening
    CU.apply(shell_obj, m.mats)
    print('NONMANIFOLD after cuts', CU.check_manifold(shell_obj))
    K.smooth_by_angle(shell_obj, 50.0)
    surf = K.Surface(K.bvh_of([shell_obj]))
    det = K.Part('details')
    PT.lamps(det, clean)
    PT.shut_lines(det, surf, shell_rows)
    PT.lips(det, shell_rows)
    PT.side_details(det, surf)
    PT.grilles(det, surf)
    PT.door_mirror(det, surf)
    PT.nozzles(det, surf)
    PT.arch_lips(det, surf)
    PT.mirror(det)
    aero = K.Part('aero')
    PT.wing(aero, surf)
    PT.mirror(aero)
    PT.hood_scoop(aero, surf)
    PT.wipers(det, surf)
    fuel = K.Part('fuel')
    PT.fuel_lid(fuel, surf)
    PT.mirror(fuel)
    # keep the right side's lid only
    import bmesh as _bm
    _bm.ops.delete(fuel.bm, geom=[f for f in fuel.bm.faces if f.calc_center_median().x > 0], context='FACES')
    PT.plates(det, surf, clean)
    cab = K.Part('interior')
    PT.interior(cab)
    ex = K.Part('exhaust')
    PT.exhaust(ex)
    tris = {'shell': sum(len(p.vertices) - 2 for p in shell_obj.data.polygons), 'details': det.tris(), 'exhaust': ex.tris(),
            'aero': aero.tris(), 'interior': cab.tris()}
    cab.build(body, m.mats, sharp=40.0)
    aero.build(body, m.mats, sharp=40.0)
    det.build(body, m.mats, sharp=40.0, weld=False)
    fuel.build(body, m.mats, weld=False)
    ex.build(body, m.mats)
    pivots, wt = WH.build(root, m.mats)
    for k, v in wt.items():
        tris['wheel_' + k] = v
    for k, v in tris.items():
        print('TRIS', k, v)
    print('TRIS total', sum(tris.values()))
    used = set()
    for o in root.children_recursive:
        if o.type == 'MESH':
            used.update(ms.name for ms in o.data.materials)
    print('MATERIALS', len(used), sorted(used))
    lamps = lamp_report(root)
    if OUT:
        K.export_glb(OUT, root)
    if RENDER:
        import raijin_scene as S
        S.scene(night=NIGHT)
        if NIGHT:
            S.night_lights(m.mats, lamps)
        os.makedirs(RENDER, exist_ok=True)
        for v in VIEWS.split(','):
            if v.startswith('photo13'):
                # Commons "Streetcarl Subaru impreza sti (6661190347)": 1280×960, 264 px/m at the wheel faces
                D = 9.0
                view = S.photo_view(D, 1.37, -0.15, 264 * (D - 0.80), 1280)
                body.location = K.B(0, -float(opt('--drop', '0.06')), 0)
                S.render(view, os.path.join(RENDER, f'{v}.png'), size=(1280, 960), samples=SAMPLES, mask=True)
                continue
            S.render(v, os.path.join(RENDER, f'{v}.png'), size=SIZE, samples=SAMPLES)


main()
