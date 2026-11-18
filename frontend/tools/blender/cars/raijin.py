"""
Subaru Impreza WRX STI sedan (GDB, 2004: the "tear-drop" face, stock, with the factory high rear wing) for TOUGE
NOCTURNE, game id `raijin`, built from published figures and our own measurements of photos (no outside model, no
photo pixels; the Subaru oval on the grille is our own simple drawing). Run with Blender 5.x:

  blender -t 4 --background --factory-startup --python tools/blender/cars/raijin.py -- --out <file.glb>
      [--render <dir> --views a,b --samples N --size WxH] [--night] [--noffd] [--paint #rrggbb]

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
import raijin_ffd as FFD  # noqa: E402
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


def materials(paint='#1f47a8'):
    m = K.Materials()
    m.add('paint', paint, metallic=0.55, roughness=0.34, coat=0.35)
    m.add('glass', '#0d1218', metallic=0.1, roughness=0.05)
    m.add('trim', '#111214', roughness=0.6)
    m.add('under', '#0b0b0c', roughness=0.9)
    # metal parts are metal (metallic 1): the chrome trim, exhaust tip and badges, the gold-painted forged alloys
    # (a metallic paint: the base reads as metal), the brake discs, the fog lamps' reflectors; the head lamps'
    # reflectors are the textured lens, chrome under a clear cover
    m.add('chrome', '#d8dade', metallic=1.0, roughness=0.12)
    m.add('indicator', '#d98c3c', roughness=0.12, metallic=0.2)
    m.add('lamp_clear', '#c9ccd2', roughness=0.14, metallic=1.0)
    m.add('interior', '#232325', roughness=0.85)
    m.add('rim', '#a3844c', metallic=1.0, roughness=0.32)
    m.add('brake', '#c8a032', metallic=0.3, roughness=0.4)
    m.add('disc', '#6a6c70', metallic=1.0, roughness=0.40)
    load = lambda n: bpy.data.images.load(os.path.join(TEX, n))
    m.textured('headlight', load('headlight.png'), roughness=0.3, metallic=1.0, emissive_map=True, coat=1.0)
    m.textured('taillight', load('taillight.png'), roughness=0.2, emissive_map=True, coat=1.0)
    m.textured('plate', load('plate.png'), roughness=0.5)
    m.textured('grille', load('grille.png'), roughness=0.6)
    m.mats['cowl'] = m.mats['trim']
    import car_common as CC
    for name in ('c_dash', 'c_plastic', 'c_carpet'):        # the cabin's swatches (car_common)
        CC.material_for(m.mats, name)
    return m


def finish(root, body, mats):
    """after the body's last deformation (car_common): the underside (a front engine driving all four wheels, the
    rear on arms, the rear silencer across the car behind the axle, its big tip on the left; the tank ahead of the axle), the plain materials into two painted atlases, every
    corner's share of the sky. The grille's mesh picture repeats, so it stays a material; so does the plate."""
    import car_common as CC
    import hayate_kit as HK
    CC.underseal([o for o in body.children_recursive if o.type == 'MESH'], mats)
    ub = HK.Mesh('underbody')
    x, y, z = PT.EXHAUST
    CC.underbody(ub, 0.19, SH.FRONT_AXLE, SH.REAR_AXLE, WH.TRACK_F, WH.TRACK_R, WH.R_TYRE, tip=(x, y, z + 0.10),
                 layout='AWD', axle='irs', silencer='across')
    print('TRIS underbody', ub.tris())
    CC.build(ub, body, mats)
    trim = CC.Atlas('trim')
    rim = CC.Atlas('rim', size=512, fill=('#8a8c8f', 0.32, 0.85))
    rim.region('disc', CC.disc_image(), 0.38, 0.85)
    made = CC.consolidate(root, trim, rim, own=('tire', 'plate', 'grille'))
    tyres = [o for o in root.children_recursive
             if o.type == 'MESH' and any(mm and mm.name == 'tire' for mm in o.data.materials)]
    CC.bake_ao(root, made + tyres)


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


def build(o=None):
    """the whole car into the (cleared) scene; o: {'paint': '#rrggbb', 'ffd': True (fitdata/raijin/ffd.json) | False |
    a raijin_ffd.Lattice}. Returns (root, materials, lamp report)"""
    o = o or {}
    m = materials(o.get('paint', '#1f47a8'))
    root = K.empty('raijin')
    body = K.empty('body', parent=root)
    shell = K.Part('body_shell')
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
    PT.grilles(det, surf, clean)
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
    tris = {'body_shell': sum(len(p.vertices) - 2 for p in shell_obj.data.polygons), 'details': det.tris(), 'exhaust': ex.tris(),
            'aero': aero.tris(), 'interior': cab.tris()}
    cab.build(body, m.mats, sharp=40.0)
    import car_common as CC
    import hayate_kit as HK
    fur = HK.Mesh('furniture')
    PT.furnish(fur)
    tris['furniture'] = fur.tris()
    CC.build(fur, body, m.mats)
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
    for ob in root.children_recursive:
        if ob.type == 'MESH':
            used.update(ms.name for ms in ob.data.materials)
    print('MATERIALS', len(used), sorted(used))
    if o.get('ffd', True) is not False:
        # the fitted displacement field (fitdata/raijin/ffd.json, from the photo silhouettes) on every body mesh
        L = FFD.apply_to_body(body, None if o.get('ffd', True) is True else o['ffd'])
        print('FFD', 'none' if L is None else 'applied')
    bpy.context.view_layer.update()
    lamps = lamp_report(root)
    finish(root, body, m.mats)
    bpy.context.view_layer.update()
    return root, m.mats, lamps


def main():
    K.clear_scene()
    root, mats, lamps = build({'ffd': '--noffd' not in argv, 'paint': opt('--paint', '#1f47a8')})
    if OUT:
        K.export_glb(OUT, root)
    if RENDER:
        import raijin_scene as S
        S.scene(night=NIGHT)
        if NIGHT:
            S.night_lights(mats, lamps)
        os.makedirs(RENDER, exist_ok=True)
        for v in VIEWS.split(','):
            S.render(v, os.path.join(RENDER, f'{v}.png'), size=SIZE, samples=SAMPLES)


if __name__ == '__main__':
    main()
