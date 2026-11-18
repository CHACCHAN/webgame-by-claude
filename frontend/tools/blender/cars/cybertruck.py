"""
Tesla Cybertruck (production truck as delivered since late 2023; the tri-motor "Cyberbeast") for TOUGE NOCTURNE,
game id `cybertruck`, built from published figures and our own measurements of photos (no outside model, no photo
pixels; the T badge is our own simple drawing). Run with Blender 5.x:

  blender -t 4 --background --factory-startup --python tools/blender/cars/cybertruck.py -- --out <file.glb>
      [--render <dir> --views a,b --samples N --size WxH] [--night] [--paint #rrggbb] [--shape shape.json]

Figures: length 5683, width 2027 (no mirrors), height 1791 mm (standard ride height), wheelbase 3635 mm (143.1 in),
35-inch LT285/65R20 tyres; the panels, lamps and arches are fitted to Commons photos (fitdata/cybertruck/).

GLB contract (render/CarModel.ts): metres, +Y up, +Z forward, ground at y = 0, origin midway between the axles;
node `body` (all body meshes), wheel pivots wheel_fl/fr/rl/rr at the wheel centres with spin_* children (tyre, rim,
disc) and the calipers beside spin; materials paint (the stainless panels: the game recolours it), glass, trim,
chrome, headlight, taillight, tire, rim, brake, plus vault (the black vault cover), clad (the black textured plastic:
bumpers, arch flares, sills, the rear quarters under the stainless), under, interior, indicator (front side markers),
reflector (rear reflectors), disc.
Lamps: headlight = the full-width light bar (the chamfer between hood and face) and the two headlamp slits under the
face; taillight = the tail light line across the black band and the two corner blocks (textures from
cybertruck_textures.py: smoked when unlit, the game glows through them).
Modules: cybertruck_shape (the flat panels, plain Python, shared with the fitting tools), cybertruck_kit (frames,
meshes, export), cybertruck_parts (lamps, mirrors, wiper, cabin), cybertruck_wheels, cybertruck_scene (check renders).
"""
import json
import os
import sys

sys.dont_write_bytecode = True  # no __pycache__ in the repo
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cybertruck_kit as K  # noqa: E402
import cybertruck_shape as CS  # noqa: E402
import cybertruck_parts as PT  # noqa: E402
import cybertruck_wheels as WH  # noqa: E402
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
PAINT = '#b4b6b8'
TEX = os.path.join(os.path.dirname(HERE), 'textures', 'cybertruck')


def materials(paint=PAINT):
    m = K.Materials()
    # brushed stainless: light, metallic, a little rough (the game swaps the colour)
    m.add('paint', paint, metallic=0.85, roughness=0.30)
    m.add('glass', '#0d1114', metallic=0.1, roughness=0.04)
    m.add('trim', '#131415', roughness=0.55)
    m.add('vault', '#18191a', metallic=0.25, roughness=0.42)
    m.add('clad', '#232426', roughness=0.82)
    m.add('under', '#0a0a0b', roughness=0.9)
    m.add('chrome', '#c9cbce', metallic=1.0, roughness=0.15)
    m.add('indicator', '#cf7f2e', roughness=0.2, metallic=0.1)
    m.add('reflector', '#7a1210', roughness=0.25, metallic=0.1)
    m.add('interior', '#1c1d1f', roughness=0.85)
    m.add('rim', '#1c1d1f', metallic=0.45, roughness=0.42)
    m.add('brake', '#8e9195', metallic=0.4, roughness=0.45)
    m.add('disc', '#6a6c70', metallic=0.85, roughness=0.45)
    load = lambda n: bpy.data.images.load(os.path.join(TEX, n))
    if os.path.exists(os.path.join(TEX, 'headlight.png')):
        m.textured('headlight', load('headlight.png'), roughness=0.12, metallic=0.1, emissive_map=True)
        m.textured('taillight', load('taillight.png'), roughness=0.2, emissive_map=True)
        m.textured('tire', load('tire.png'), roughness=0.92)
    else:
        m.add('headlight', '#dfe3e8', roughness=0.12, metallic=0.1)
        m.add('taillight', '#4a0b0d', roughness=0.2)
        m.add('tire', '#202022', roughness=0.92)
    import car_common as CC
    for name in ('c_dash', 'c_plastic', 'c_carpet'):        # the cabin's swatches (car_common)
        CC.material_for(m.mats, name)
    return m


def lamp_report(root):
    """centre and size of each lamp lens (game frame), per side"""
    out = {}
    for o in root.children_recursive:
        if o.type != 'MESH':
            continue
        names = [ms.name for ms in o.data.materials]
        for p in o.data.polygons:
            n = names[p.material_index] if p.material_index < len(names) else ''
            if n in ('headlight', 'taillight', 'indicator'):
                for vi in p.vertices:
                    g = K.G(o.matrix_world @ o.data.vertices[vi].co)
                    out.setdefault((n, 'L' if g[0] > 0 else 'R'), []).append(g)
    res = {}
    for (k, side), pts in sorted(out.items()):
        lo = [min(p[i] for p in pts) for i in range(3)]
        hi = [max(p[i] for p in pts) for i in range(3)]
        c = [round((a + b) / 2, 3) for a, b in zip(lo, hi)]
        res[(k, side)] = c
        print('LAMP', k, side, 'centre', c, 'size', [round(b - a, 3) for a, b in zip(lo, hi)])
    return res


def narrow(body, width):
    """scale the body across the car to `width` over everything but the mirrors; returns the factor"""
    obs = [o for o in body.children_recursive if o.type == 'MESH']
    half = max(abs(v.co.x) for o in obs if o.name != 'mirrors' for v in o.data.vertices)
    k = width / (2 * half)
    for o in obs:
        for v in o.data.vertices:
            v.co.x *= k
        o.data.update()
    print('NARROW', round(2 * half, 4), '->', width, 'x', round(k, 4))
    return k


def finish(root, body, mats, P):
    """car_common: what hangs under the floor pan (the battery case a centimetre under it, ribbed across; a drive
    unit, shafts and arms at each axle), the plain materials into two painted atlases, every corner's share of the
    sky. The tyre keeps its own picture."""
    import car_common as CC
    import hayate_kit as HK
    ub = HK.Mesh('underbody')
    CC.underbody(ub, P['y_rk'] + 0.005, CS.WB / 2, -CS.WB / 2, P['track'], P['track'], P['hub_y'], tip=(0.5, 0.3, -2.5),
                 layout='EV')
    n = ub.tris()
    CC.build(ub, body, mats)
    trim = CC.Atlas('trim')
    rim = CC.Atlas('rim', size=512, fill=('#8a8c8f', 0.32, 0.85))
    rim.region('disc', CC.disc_image(), 0.38, 0.85)
    made = CC.consolidate(root, trim, rim, own=('tire', 'plate'))
    tyres = [o for o in root.children_recursive
             if o.type == 'MESH' and any(mm and mm.name == 'tire' for mm in o.data.materials)]
    CC.bake_ao(root, made + tyres)
    return n


def build(o=None):
    """the whole truck into the (cleared) scene; o: {'paint': '#rrggbb', 'P': parameter dict, 'interior': True}.
    Returns (root, materials, lamp report)"""
    o = o or {}
    P = o.get('P') or CS.load(o.get('shape', CS.SHAPE_JSON))
    m = materials(o.get('paint', PAINT))
    root = K.empty('cybertruck')
    body = K.empty('body', parent=root)
    S, shell = CS.shell(P)
    fb, rb = CS.bumpers(P, S)
    side = CS.cladding(P, S) + CS.rocker(P, S)
    tris = {}

    uv_for = {'headlight': (0.25, 0.5), 'taillight': (0.75, 0.5)}   # texture spots for lamp faces without UVs

    def put(name, faces, smooth=False, sharp=30.0):
        part = K.Part(name)
        PT.faces_to_part(part, faces, smooth=smooth, uv_for=uv_for)
        tris[name] = part.tris()
        return part.build(body, m.mats, sharp=sharp)
    put('body_shell', shell)
    put('bumpers', fb + rb)
    put('cladding', side + PT.mirrored(side))
    put('lamps', PT.lamps(P, S, o.get('lamps')) + PT.badge(P, S))
    mir = PT.mirror_unit(P, S)
    put('mirrors', mir + PT.mirrored(mir))
    sm = PT.seams(P, S)
    put('seams', sm + PT.mirrored(sm))
    det = K.Part('details')
    PT.bumper_details(det, P, S)
    PT.vault_ribs(det, P, S)
    PT.underbody(det, P, S)
    p0, p1 = PT.wiper(P, S)
    det.beam('trim', p0, p1, 0.022, 0.012, up=S.ws[0])
    tris['details'] = det.tris()
    det.build(body, m.mats, sharp=40.0)
    if o.get('interior', True):
        cab = K.Part('interior')
        PT.cabin(cab, P, S)
        tris['interior'] = cab.tris()
        cab.build(body, m.mats, sharp=40.0)
        import car_common as CC
        import hayate_kit as HK
        fur = HK.Mesh('furniture')
        PT.furnish(fur)
        tris['furniture'] = fur.tris()
        CC.build(fur, body, m.mats)
    # The catalogue's width (2,027 mm, mirrors folded in) is the truck over its arch cladding. The fit had put the
    # stainless there and the cladding 20 mm further out a side (2,068 mm). Narrowed to the catalogue, body and
    # track alike, every photo's outline fits better (mean IoU 0.9387 -> 0.9454, the gate's dimtest.py); the
    # catalogue's height does not (0.9342: the photographed trucks stand lower on their air springs), so that stays.
    kx = narrow(body, CS.WIDTH)
    P = dict(P, track=P['track'] * kx)
    pivots, wt = WH.build(root, m.mats, P)
    for k, v in wt.items():
        tris['wheel_' + k] = v
    tris['underbody'] = finish(root, body, m.mats, P)
    for k, v in tris.items():
        print('TRIS', k, v)
    print('TRIS total', sum(tris.values()))
    used = set()
    for ob in root.children_recursive:
        if ob.type == 'MESH':
            used.update(ms.name for ms in ob.data.materials)
    print('MATERIALS', len(used), sorted(used))
    bpy.context.view_layer.update()
    lamps = lamp_report(root)
    return root, m.mats, lamps


def main():
    K.clear_scene()
    o = {'paint': opt('--paint', PAINT)}
    if opt('--shape'):
        o['shape'] = opt('--shape')
    root, mats, lamps = build(o)
    if OUT:
        K.export_glb(OUT, root)
    if RENDER:
        import cybertruck_scene as S
        S.scene(night=NIGHT)
        if NIGHT:
            S.night_lights(mats, lamps)
        os.makedirs(RENDER, exist_ok=True)
        for v in VIEWS.split(','):
            S.render(v, os.path.join(RENDER, f'{v}.png'), size=SIZE, samples=SAMPLES)


if __name__ == '__main__':
    main()
