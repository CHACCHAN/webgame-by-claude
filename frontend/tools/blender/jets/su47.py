"""
Sukhoi Su-47 "Berkut" (the one prototype, black, bort number 01) for TOUGE NOCTURNE (game id `su47`), built from
numbers and our own painted textures: no outside model, no traced drawing, no photo pixels. Run with Blender 5.x:

  blender -t 4 --background --factory-startup --python tools/blender/jets/su47.py -- --out <file.glb>
      [--render <dir> --views front34,rear34,... --samples N --size WxH] [--gear 0..1] [--no-pilot] [--textures <dir>]
      [--measure] [--clay]

Modules: jet_kit (mesh kit, export), su47_shape (the airframe in numbers and its skins), su47_skin (skins, the
atlas), su47_paint (the textures), su47_parts (gear, cockpit, pilot, fittings), su47_scene (the check scene).
GLB contract: render/JetModel.ts. What the model gives the game:
  body               the airframe (material `airframe`: one atlas), the canopy (`glass`), the lamps (`navlight_all`)
  nozzle_l/_r        the afterburner nozzles (their aft end is where the flame starts)
  canard_l, stab_l   BOTH canards / BOTH tailplanes on one node each (they pitch about the same line): a draw call each
  gear_nose          the nose leg, doors and lamps (`taxilight`) → steer_nose → spin_nose (the two wheels)
  gear_l/_r          a main leg with its wheel and door (the wheel does not turn: one draw call a leg)
`--measure` prints the dimensions and the gear's fold (GEARFOLD lines for vehicle/jets.ts).
"""
import math
import os
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(1, os.path.join(HERE, '..', 'cars'))

import bmesh  # noqa: E402
import bpy  # noqa: E402
import numpy as np  # noqa: E402

import jet_kit as K  # noqa: E402
import car_common as CC  # noqa: E402  (text masks, images, the baked sky share)
import su47_paint as PT  # noqa: E402
import su47_parts as P  # noqa: E402
import su47_shape as SH  # noqa: E402
import su47_skin as S  # noqa: E402
from su47_shape import Z  # noqa: E402

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []


def opt(name, default=None):
    return argv[argv.index(name) + 1] if name in argv else default


OUT = opt('--out')
RENDER = opt('--render')
VIEWS = opt('--views', 'front34')
SAMPLES = int(opt('--samples', '48'))
SIZE = tuple(int(v) for v in opt('--size', '1600x900').split('x'))
GEAR = float(opt('--gear', '0'))
PILOT = '--no-pilot' not in argv
ATLAS = int(opt('--atlas', '2048'))

# the numerals on the nose and the mark on the fins: patches a hand above the skin, each side reading its own way
NOSE_MARK = {'d': (4.75, 5.95), 'y': (2.04, 2.59)}
FIN_MARK = {'d': (18.62, 19.82), 's': (1.85, 3.05)}
LIFT = 0.008


def mark_skins(atlas):
    num = atlas.sheet('numbers', (NOSE_MARK['d'][1] - NOSE_MARK['d'][0], NOSE_MARK['y'][1] - NOSE_MARK['y'][0]), density=2.2)
    fin = atlas.sheet('finmark', (FIN_MARK['d'][1] - FIN_MARK['d'][0], FIN_MARK['s'][1] - FIN_MARK['s'][0]), density=1.5)
    out = []
    d0, d1 = NOSE_MARK['d']
    y0, y1 = NOSE_MARK['y']
    ds, ys = np.linspace(d0, d1, 9), np.linspace(y0, y1, 6)
    rows, uv_l, uv_r = [], [], []
    for y in ys:
        row = []
        for d in ds:
            x = SH.fb_side_x(d, y)
            dx = (SH.fb_side_x(d, y + 0.01) - SH.fb_side_x(d, y - 0.01)) / 0.02
            n = K.unit((1.0, -dx))
            row.append((x + LIFT * n[0], y + LIFT * n[1], Z(d)))
        rows.append(row)
        uv_l.append([(d - d0, y - y0) for d in ds])
        uv_r.append([(d1 - d, y - y0) for d in ds])
    out.append((S.Skin('mark_nose_l', num, rows, uv_l, out=(1.0, 0.0, 0.0)), 1))
    out.append((S.Skin('mark_nose_r', num, rows, uv_r, out=(1.0, 0.0, 0.0)), -1))
    d0, d1 = FIN_MARK['d']
    s0, s1 = FIN_MARK['s']
    ds, ss = np.linspace(d0, d1, 7), np.linspace(s0, s1, 5)
    rows, uv_l, uv_r = [], [], []
    for s in ss:
        (fx, fy), nrm = SH.fin_frame(s)
        le, c, t = SH.fin_station(s)
        row = []
        for d in ds:
            xi = min(1.0, max(0.0, (d - le) / c))
            h = 5 * t * c * (0.2969 * math.sqrt(xi) - 0.1260 * xi - 0.3516 * xi ** 2 + 0.2843 * xi ** 3 - 0.1036 * xi ** 4) + LIFT
            row.append((fx + nrm[0] * h, fy + nrm[1] * h, Z(d)))
        rows.append(row)
        uv_l.append([(d - d0, s - s0) for d in ds])
        uv_r.append([(d1 - d, s - s0) for d in ds])
    nrm = SH.fin_frame(0)[1]
    out.append((S.Skin('mark_fin_l', fin, rows, uv_l, out=nrm), 1))
    out.append((S.Skin('mark_fin_r', fin, rows, uv_r, out=nrm), -1))
    return out


def polygon_mask(c, pts):
    """coverage of a polygon given in the sheet's metres (3 × 3 samples a pixel)"""
    ss = 3
    u = (np.arange(c.w * ss, dtype=np.float32) + 0.5) / (c.s * ss)
    v = (np.arange(c.h * ss, dtype=np.float32) + 0.5) / (c.s * ss)
    U, V = np.meshgrid(u, v)
    inside = np.zeros(U.shape, bool)
    n = len(pts)
    for i in range(n):
        (x0, y0), (x1, y1) = pts[i], pts[(i + 1) % n]
        if y0 == y1:
            continue
        cond = (y0 > V) != (y1 > V)
        xc = (x1 - x0) * (V - y0) / (y1 - y0) + x0
        inside ^= cond & (U < xc)
    return inside.reshape(c.h, ss, c.w, ss).mean((1, 3)).astype(np.float32)


def paint_numbers(c):
    c.weather(amount=0.6)
    m = CC.text_mask('01', c.w, c.h, height=0.74, font=CC.FONT_BLACK, spacing=1.08)
    c.fill(PT.WHITE, 0.45, 0.0, m)


def paint_finmark(c):
    """our own mark: a chevron of two wings over the number"""
    L, H = c.size
    c.weather(amount=0.6)
    wing = [(0.14, 0.98), (0.6, 0.66), (1.06, 0.98), (0.97, 1.03), (0.6, 0.80), (0.23, 1.03)]
    c.fill(PT.WHITE, 0.45, 0.0, polygon_mask(c, [(u * L / 1.2, v * H / 1.2) for u, v in wing]))
    h = int(c.h * 0.40)
    m = np.zeros((c.h, c.w), np.float32)
    m[int(c.h * 0.06):int(c.h * 0.06) + h] = CC.text_mask('01', c.w, h, height=0.86, font=CC.FONT_BLACK, spacing=1.08)
    c.fill(PT.WHITE, 0.45, 0.0, m)


def materials(atlas, clay=False):
    base, orm, nrm = PT.paint_atlas(atlas, {'numbers': paint_numbers, 'finmark': paint_finmark})
    if clay:
        base[:] = 0.55
        orm[:] = (1.0, 0.6, 0.0)
        nrm[:] = (0.5, 0.5, 1.0)
    tex_dir = opt('--textures')
    mats = {}
    m = bpy.data.materials.new('airframe')
    m.use_nodes = True
    nt = m.node_tree
    p = nt.nodes.get('Principled BSDF')
    tb = nt.nodes.new('ShaderNodeTexImage')
    tb.image = CC.new_image('su47_base', base)
    to = nt.nodes.new('ShaderNodeTexImage')
    to.image = CC.new_image('su47_orm', orm, colour=False)
    tn = nt.nodes.new('ShaderNodeTexImage')
    tn.image = CC.new_image('su47_normal', nrm, colour=False)
    CC._tinted_base(nt, p, tb)
    sep = nt.nodes.new('ShaderNodeSeparateColor')
    nt.links.new(to.outputs[0], sep.inputs[0])
    nt.links.new(sep.outputs[1], p.inputs['Roughness'])
    nt.links.new(sep.outputs[2], p.inputs['Metallic'])
    nm = nt.nodes.new('ShaderNodeNormalMap')
    nt.links.new(tn.outputs[0], nm.inputs['Color'])
    nt.links.new(nm.outputs[0], p.inputs['Normal'])
    mats['airframe'] = m
    # the lamps: their colours are swatches of the same picture, which also glows
    lamp = bpy.data.materials.new('navlight_all')
    lamp.use_nodes = True
    nt = lamp.node_tree
    p = nt.nodes.get('Principled BSDF')
    t = nt.nodes.new('ShaderNodeTexImage')
    t.image = tb.image
    nt.links.new(t.outputs[0], p.inputs['Base Color'])
    nt.links.new(t.outputs[0], p.inputs['Emission Color'])
    p.inputs['Emission Strength'].default_value = 1.0
    p.inputs['Roughness'].default_value = 0.2
    mats['navlight_all'] = lamp
    kit = K.Materials()
    mats['glass'] = kit.add('glass', '#0b1016', metallic=0.1, roughness=0.05)
    mats['taxilight'] = kit.add('taxilight', '#fffbe8', roughness=0.1)
    if tex_dir:
        os.makedirs(tex_dir, exist_ok=True)
        for img in (tb.image, to.image, tn.image):
            img.filepath_raw = os.path.join(tex_dir, img.name + '.png')
            img.file_format = 'PNG'
            img.save()
    return mats


def close(part, atlas, n_skin):
    """weld, turn the primitives' faces outwards (the skins know their own way), give the swatches their place"""
    bm = part.bm
    layer = bm.faces.layers.int.new('prim')
    for k, f in enumerate(bm.faces):
        f[layer] = 1 if k >= n_skin else 0
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    prim = [f for f in bm.faces if f[layer]]
    if prim:
        bmesh.ops.recalc_face_normals(bm, faces=prim)
    bm.faces.layers.int.remove(layer)
    S.swatch_part(part, atlas)


def build():
    K.clear_scene()
    atlas = S.Atlas(ATLAS)
    P.register(atlas)
    body_skins = [SH.forebody_skin(atlas), SH.canopy_skin(atlas)] + SH.deck_skins(atlas) + SH.beaver_skins(atlas)
    body_skins += SH.nacelle_skins(atlas) + SH.wing_skins(atlas) + SH.fin_skins(atlas) + P.cockpit_skins(atlas)
    boom_l, boom_r = SH.boom_skin(atlas, 'l'), SH.boom_skin(atlas, 'r')
    canard, stab = SH.moving_skins(atlas, 'canard', SH.CANARD), SH.moving_skins(atlas, 'stab', SH.STAB)
    nozzle = SH.nozzle_skins(atlas)
    marks = mark_skins(atlas)
    atlas.pack()
    mats = materials(atlas, clay='--clay' in argv)

    root = K.node('su47')
    body = K.node('body', root)
    parts = {}

    part = K.Part('airframe')
    for s in body_skins:
        s.emit(part, atlas)
    boom_l.emit(part, atlas, 1)
    boom_r.emit(part, atlas, -1)
    for s, sign in marks:
        s.emit(part, atlas, sign)
    n = len(part.bm.faces)
    P.cockpit_fittings(part, pilot=PILOT)
    P.details(part)
    close(part, atlas, n)
    parts['airframe'] = part.build(body, mats)

    for name, sign in (('nozzle_l', 1), ('nozzle_r', -1)):
        part = K.Part(name)
        for s in nozzle:
            s.emit(part, atlas, sign)
        close(part, atlas, len(part.bm.faces))
        parts[name] = part.build(body, mats)

    for name, skins, p in (('canard_l', canard, SH.CANARD), ('stab_l', stab, SH.STAB)):
        pivot = K.node(name, body, origin=(0.0, p['y'], Z(p['pivot'])))
        part = K.Part(name + '_mesh')
        for s in skins:
            s.emit(part, atlas)
        close(part, atlas, len(part.bm.faces))
        parts[name] = part.build(pivot, mats)

    x, r, z = P.NOSE_WHEEL
    gear_nose = K.node('gear_nose', body, origin=P.NOSE_HINGE)
    steer = K.node('steer_nose', gear_nose, origin=(0.0, r, z))
    spin = K.node('spin_nose', steer, origin=(0.0, r, z))
    leg, wheels = K.Part('nose_leg'), K.Part('nose_wheels')
    P.nose_gear(leg, wheels)
    close(leg, atlas, 0)
    close(wheels, atlas, 0)
    parts['gear_nose'] = leg.build(gear_nose, mats)
    parts['spin_nose'] = wheels.build(spin, mats)
    folds = {'nose': P.fold_of(np.array(P.NOSE_HINGE), (0.0, r, z), (0.0, P.NOSE_HINGE[1] - 0.02, P.NOSE_HINGE[2] + 1.6))}
    nodes = {'gear_nose': gear_nose}
    for name, sx in (('gear_l', 1), ('gear_r', -1)):
        H = (P.MAIN_HINGE[0] * sx, P.MAIN_HINGE[1], P.MAIN_HINGE[2])
        g = K.node(name, body, origin=H)
        leg = K.Part(name + '_mesh')
        P.main_gear(leg, sx)
        close(leg, atlas, 0)
        parts[name] = leg.build(g, mats)
        nodes[name] = g
        mw = P.MAIN_WHEEL
        folds['left' if sx > 0 else 'right'] = P.fold_of(np.array(H), (mw[0] * sx, mw[1], mw[2]),
                                                         (P.MAIN_STOWED[0] * sx, P.MAIN_STOWED[1], P.MAIN_STOWED[2]))
    bpy.context.view_layer.update()
    meshes = [o for o in root.children_recursive if o.type == 'MESH']
    CC.bake_ao(root, meshes, reach=1.3, rays=16, floor=0.34, power=0.85, wheel=(0.5, 0.4))
    return root, parts, nodes, folds, atlas, mats


def bounds(objs):
    lo, hi = np.full(3, 1e9), np.full(3, -1e9)
    for o in objs:
        M = o.matrix_world
        for v in o.data.vertices:
            g = np.array(K.G(M @ v.co))
            lo, hi = np.minimum(lo, g), np.maximum(hi, g)
    return lo, hi


def measure(root, parts, folds):
    meshes = [o for o in root.children_recursive if o.type == 'MESH']
    lo, hi = bounds(meshes)
    print(f'DIM length {hi[2] - lo[2]:.3f} (published {SH.LENGTH})  nose z {hi[2]:.3f}  tail z {lo[2]:.3f}')
    print(f'DIM span {hi[0] - lo[0]:.3f} (published {SH.SPAN})')
    print(f'DIM height {hi[1]:.3f} (published {SH.HEIGHT})  lowest point {lo[1]:.4f}')
    print(f'DIM wing reference area {SH.planform_area():.2f} m2 (published 56; other sources 61.87)')
    le = math.degrees(math.atan(SH.WING_LE_SWEEP))
    print(f'DIM wing sweep: leading edge -{le:.1f} deg, trailing edge -{math.degrees(math.atan(SH.WING_TE_SWEEP)):.1f} deg (derived, not published)')
    wl, wh = bounds([parts['spin_nose']])
    print(f'DIM nose wheels: contact y {wl[1]:.4f}, z {(wl[2] + wh[2]) / 2:.3f}, spread {wh[0] - wl[0]:.3f}')
    for name in ('gear_l', 'gear_r'):
        gl, gh = bounds([parts[name]])
        print(f'DIM {name}: lowest y {gl[1]:.4f}')
    for name in ('nozzle_l', 'nozzle_r'):
        nl, nh = bounds([parts[name]])
        print(f'DIM {name}: exit z {nl[2]:.3f}, centre x {(nl[0] + nh[0]) / 2:.3f} y {(nl[1] + nh[1]) / 2:.3f}, radius {(nh[0] - nl[0]) / 2:.3f}')
    bl, bh = bounds([parts['airframe']])
    print(f'DIM booms: the left one ends at d {SH.BOOM_END["l"][-1][0]:.2f}, the right one at d {SH.BOOM_END["r"][-1][0]:.2f}')
    for k, (axis, ang) in folds.items():
        print(f'GEARFOLD {k}: {{ axis: [{axis[0]:.3f}, {axis[1]:.3f}, {axis[2]:.3f}], angle: {ang:.3f} }}')


def check_winding(root):
    """faces whose outward ray meets an odd number of faces look inwards (or lie inside another shell): the share"""
    from mathutils.bvhtree import BVHTree
    verts, polys = [], []
    for o in root.children_recursive:
        if o.type != 'MESH':
            continue
        base = len(verts)
        verts.extend(o.matrix_world @ v.co for v in o.data.vertices)
        polys.extend([base + i for i in p.vertices] for p in o.data.polygons)
    tree = BVHTree.FromPolygons(verts, polys)
    for o in root.children_recursive:
        if o.type != 'MESH':
            continue
        odd = tot = 0
        R = o.matrix_world.to_3x3()
        for p in list(o.data.polygons)[::7]:
            n = (R @ p.normal).normalized()
            c = o.matrix_world @ p.center + n * 0.002
            hits = 0
            for _ in range(40):
                loc, _, _, _ = tree.ray_cast(c, n, 200.0)
                if loc is None:
                    break
                hits += 1
                c = loc + n * 0.0005
            tot += 1
            odd += hits % 2
        print(f'WINDING {o.name}: {odd}/{tot} sampled faces look into something')


def set_gear(nodes, folds, k):
    from mathutils import Quaternion
    e = k * k * (3 - 2 * k)
    for name, key in (('gear_nose', 'nose'), ('gear_l', 'left'), ('gear_r', 'right')):
        axis, ang = folds[key]
        o = nodes[name]
        # the fold is given in the game frame about the hinge
        q = Quaternion(K.B(*axis) - K.B(0, 0, 0), ang * e)
        loc = o.matrix_world.translation.copy()
        o.matrix_world = (q.to_matrix().to_4x4() @ o.matrix_world.to_3x3().to_4x4())
        o.matrix_world.translation = loc
        if k >= 0.98:
            for c in [o] + list(o.children_recursive):
                c.hide_render = True
    bpy.context.view_layer.update()


def main():
    root, parts, nodes, folds, atlas, mats = build()
    K.report(root)
    if '--measure' in argv:
        measure(root, parts, folds)
        check_winding(root)
    if OUT:
        K.export_glb(OUT, root)
    if RENDER:
        import su47_scene as SC
        if GEAR > 0:
            set_gear(nodes, folds, GEAR)
        SC.scene(mats, night='--night' in argv)
        if '--backfaces' in argv:
            SC.backfaces()
        os.makedirs(RENDER, exist_ok=True)
        for v in VIEWS.split(','):
            SC.render(v, os.path.join(RENDER, f'{v}.png'), size=SIZE, samples=SAMPLES)


main()
