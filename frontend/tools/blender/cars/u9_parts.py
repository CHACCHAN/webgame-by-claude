"""
Parts of the U9: materials, the shell with its wheel arches, and the wheels. (Openings, glass, lamps, aero parts and
the small details: u9_details.)
"""
import math
import os

import bmesh
import bpy
from mathutils import Vector

import u9_kit as K
import u9_body as BD

TEX = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'textures', 'u9')


def _img(name):
    p = os.path.join(TEX, name)
    return bpy.data.images.load(p) if os.path.exists(p) else None


def materials(paint='#1b1d22'):
    m = K.Mats()
    # the Xtreme's dark paint (the game recolours it) with a clear coat
    m.add('paint', paint, metallic=0.55, roughness=0.30, coat=1.0)
    m.add('glass', '#0b1016', metallic=0.1, roughness=0.04)
    m.add('trim', '#0e0f11', metallic=0.2, roughness=0.55)
    m.add('carbon', '#141518', metallic=0.35, roughness=0.32, coat=0.6)
    m.add('chrome', '#d8dade', metallic=1.0, roughness=0.08)
    m.add('headlight', '#dfe6ee', metallic=0.4, roughness=0.1, image=_img('headlamp.png'), emissive='#fff4e0')
    m.add('taillight', '#3a0506', roughness=0.25, image=_img('taillamp.png'), emissive='#ff1a10')
    m.add('rim', '#2c2e32', metallic=1.0, roughness=0.34)          # dark graphite forged wheels
    m.add('rimface', '#c4c7cc', metallic=1.0, roughness=0.2)       # their machined spoke faces and lip
    m.add('brake', '#b3141a', metallic=0.2, roughness=0.4)           # red calipers (c00, c14, c32)
    m.add('disc', '#8a8886', metallic=1.0, roughness=0.36)
    m.add('under', '#101112', roughness=0.9)
    m.add('interior', '#1e1f22', roughness=0.85)
    m.add('grille', '#060607', roughness=0.7)
    m.add('plate', '#6c7076', metallic=0.3, roughness=0.45)        # the number plate (blank)
    m.add('lightstrip', '#3a0506', roughness=0.25, emissive='#ff2010', strength=1.5)   # the engine cover's strips
    m.cut = bpy.data.materials.new('_cut')
    import car_common as CC
    for name in ('c_dash', 'c_plastic', 'c_carpet'):        # the cabin's swatches (car_common)
        CC.material_for(m.mats, name)
    return m


# ------------------------------------------------------------------ wheel arches
ARCH_R = {'f': 0.415, 'r': 0.42}       # the tyres (r 0.363) fill the arches: ~5 cm round them


def arch_outline(axle):
    """the arch opening (z, y) round the axle: a circle, run down below the floor"""
    zc = BD.AXLE if axle == 'f' else -BD.AXLE
    r = ARCH_R[axle]
    pts = []
    n = 48
    a0 = math.radians(-10)
    for k in range(n + 1):
        a = a0 + (math.pi - 2 * a0) * k / n
        pts.append((zc + r * math.cos(a), BD.WHEEL_Y + r * math.sin(a)))
    pts.append((zc - r * math.cos(a0) - 0.02, -0.3))
    pts.append((zc + r * math.cos(a0) + 0.02, -0.3))
    return pts


def arch_cutters(mats):
    out = []
    for axle in ('f', 'r'):
        ol = arch_outline(axle)
        for s in (1, -1):
            x0 = 0.66 if axle == "f" else 0.64     # inside the tyres' inner faces (0.73 / 0.69)
            pts = [(s * x0, y, z) for z, y in ol]
            out.append(K.prism3(f'cut_arch_{axle}{s}', pts, (s, 0, 0), 0.0, 0.9, mats['under'], mats['under']))
    return out


def body_shell(body, mats, count):
    shell = BD.shell('shell', mats).build(body, weld=0)
    whole = shell.copy()
    whole.data = shell.data.copy()
    bpy.context.scene.collection.objects.link(whole)
    bvh = K.bvh_of(whole)
    K.boolean(shell, arch_cutters(mats))
    K.drop_unused_slots(shell)
    count['shell'] = K.obj_tris(shell)
    me = whole.data
    bpy.data.objects.remove(whole)
    bpy.data.meshes.remove(me)
    return shell, bvh


def build_all(root, mats, ffd=True):
    """ffd: True = the fitted field in fitdata/u9/ffd.json (when present), False = none, or a Lattice"""
    count = {}
    body = K.empty('body', root)
    shell, bvh = body_shell(body, mats, count)
    import u9_details as DT
    DT.build(body, mats, shell, bvh, count)
    if ffd is not False:
        import u9_ffd as FF
        FF.apply_to_body(body, None if ffd is True else ffd)
        wing_span(body)
    cabin(body, mats, count)            # after the fit's field: laid out under the fitted glass
    wheels(root, mats, count)
    finish(root, body, mats, count)
    return count


WING_SPAN = 1.99       # over the end plates, measured on c18 (the necks 0.90 m apart there)


def wing_span(body):
    """The fit's field was solved on photos whose masks leave the wing out, and up there it squeezes whatever it
    is given: the wing came out 1.84 m wide. c18 (from straight behind) shows its end plates 1,154 px apart where
    this one's stood 1,070, and the swan necks wider apart by the same share: the wing gets its width back."""
    for o in body.children_recursive:
        if o.type == 'MESH' and o.name == 'wing':
            half = max(abs(v.co.x) for v in o.data.vertices)
            k = WING_SPAN / 2 / half
            for v in o.data.vertices:
                v.co.x *= k
            o.data.update()
            print(f'WING span {2 * half:.3f} -> {WING_SPAN} x {k:.4f}')


# ------------------------------------------------------------------ wheels
# 21-inch forged wheels: 275/35 R21 front, 325/30 R21 rear (U9); the Xtreme's semi-slicks on the same sizes (estimate)
TYRE_W = {'f': 0.275, 'r': 0.325}
RIM_W = {'f': 0.241, 'r': 0.292}
RIM_R = 0.2667          # 21" bead seat
TYRE_R = BD.WHEEL_R
SEG = 48


def _lathe(part, prof, mat, seg=SEG, uv_v=None, u_rep=1.0):
    rows = []
    uvs = []
    for k in range(seg + 1):
        a = 2 * math.pi * k / seg
        rows.append([(x, r * math.sin(a), r * math.cos(a)) for x, r in prof])
        if uv_v:
            uvs.append([(u_rep * k / seg, v) for v in uv_v])
    vs = [[part.vert(p) for p in row] for row in rows[:-1]]
    vs.append(vs[0])
    idx = part.slot(mat)
    for k in range(seg):
        for j in range(len(prof) - 1):
            q = [vs[k][j], vs[k][j + 1], vs[k + 1][j + 1], vs[k + 1][j]]
            try:
                f = part.bm.faces.new(q)
            except ValueError:
                continue
            f.material_index = idx
            f.smooth = True
            if uv_v:
                quv = [uvs[k][j], uvs[k][j + 1], uvs[k + 1][j + 1], uvs[k + 1][j]]
                for loop, uv in zip(f.loops, quv):
                    loop[part.uv].uv = uv


def fix_out(part):
    part.bm.normal_update()
    for f in part.bm.faces:
        g = K.G(f.calc_center_median())
        radial = Vector((0, g.y, g.z))
        n = K.G(f.normal)
        if radial.length > 1e-6 and abs(n.normalized().dot(radial.normalized())) > 0.3:
            if n.dot(radial) < 0:
                f.normal_flip()
        elif n.x * g.x < 0:
            f.normal_flip()


def _bm(part):
    bm = part.bm
    part.bm = bmesh.new()
    return bm


def _orient(part, out):
    part.bm.normal_update()
    o = K.B(*out) - K.B(0, 0, 0)
    for f in part.bm.faces:
        if f.normal.dot(o) < -0.2:
            f.normal_flip()


def _spoke(part, mats, path, half, depth=0.032, xo=0.0, dish=0.034):
    """one spoke arm along path [(r, angle)], half widths per point; its face (outwards, +x) machined, the sides dark;
    the face sinks toward the hub (dish)"""
    rows = []
    n = len(path)
    for k, ((r, a), hw) in enumerate(zip(path, half)):
        t = (r - 0.06) / (RIM_R - 0.06)
        face = xo - 0.010 - dish * (1 - min(1.0, max(0.0, t))) ** 1.6
        ring = [(face - depth, -hw * 1.08), (face, -hw), (face, hw), (face - depth, hw * 1.08)]
        rows.append([(x, r * math.sin(a) + sd * math.cos(a), r * math.cos(a) - sd * math.sin(a)) for x, sd in ring])
    sp = K.Part('spoke')
    sp.grid(rows, mats['rim'], smooth=False, closed=True)
    for row in (rows[0], rows[-1]):
        sp.face(row, mats['rim'], smooth=False)
    bmesh.ops.recalc_face_normals(sp.bm, faces=sp.bm.faces)
    sp.bm.normal_update()
    fi = sp.slot(mats['rimface'])
    for f in sp.bm.faces:
        if K.G(f.normal).x > 0.8:
            f.material_index = fi
    part.absorb(sp)


def rim(part, mats, w):
    """the Xtreme's forged wheel (c14 / c17): five spokes, each splitting into two arms toward the rim; dark graphite,
    the spoke faces and the lip machined bright; a deep barrel; the centre cap"""
    xo = w / 2 + 0.012
    lip = K.Part('lip')
    _lathe(lip, [(xo - 0.022, RIM_R + 0.004), (xo - 0.004, RIM_R + 0.016), (xo, RIM_R + 0.014), (xo + 0.002, RIM_R + 0.006),
                 (xo + 0.002, RIM_R - 0.008), (xo - 0.03, RIM_R - 0.016)], mats['rimface'])
    fix_out(lip)
    part.absorb(lip)
    barrel = K.Part('barrel')
    _lathe(barrel, [(xo - 0.03, RIM_R - 0.016), (xo - 0.05, RIM_R - 0.02), (-w / 2 + 0.01, RIM_R - 0.02),
                    (-w / 2 - 0.004, RIM_R + 0.012)], mats['rim'])
    _orient(barrel, Vector((1, 0, 0)))
    for f in barrel.bm.faces:          # the barrel's inside faces the axle
        g = K.G(f.calc_center_median())
        if K.G(f.normal).dot(Vector((0, g.y, g.z))) > 0:
            f.normal_flip()
    part.absorb(barrel)
    for i in range(5):
        a0 = 2 * math.pi * i / 5
        # the trunk: hub to the split
        _spoke(part, mats, [(0.065 + 0.075 * k / 4, a0) for k in range(5)], [0.024 - 0.004 * k / 4 for k in range(5)], xo=xo)
        for sgn in (1, -1):
            path, hw = [], []
            for k in range(8):
                t = k / 7
                r = 0.13 + (RIM_R - 0.012 - 0.13) * t
                path.append((r, a0 + sgn * (0.012 + 0.205 * t ** 0.8)))
                hw.append(0.0105 + 0.004 * t)
            _spoke(part, mats, path, hw, xo=xo)
    hub = K.Part('hub')
    _lathe(hub, [(xo - 0.07, 0.072), (xo - 0.046, 0.072), (xo - 0.040, 0.064), (xo - 0.038, 0.0)], mats['rim'], seg=30)
    fix_out(hub)
    part.absorb(hub)
    cap = K.Part('cap')
    _lathe(cap, [(xo - 0.037, 0.040), (xo - 0.030, 0.036), (xo - 0.028, 0.0)], mats['rimface'], seg=24)
    fix_out(cap)
    part.absorb(cap)


def wheels(root, mats, count):
    """four pivots with spin children. Tyre, disc and caliper come from the shared kit (car_common: profiled tyres
    with their own texture set, big vented discs, red fixed calipers behind the axle as c00 / c14 / c32 show them);
    the forged rim is this car's own"""
    import car_common as CC
    import hayate_kit as HK
    total, made, info = 0, [], None
    for key, z, track, axle in (('fl', BD.AXLE, BD.TRACK_F, 'f'), ('fr', BD.AXLE, BD.TRACK_F, 'f'),
                                ('rl', -BD.AXLE, BD.TRACK_R, 'r'), ('rr', -BD.AXLE, BD.TRACK_R, 'r')):
        s = 1 if key[1] == 'l' else -1
        pivot = K.empty(f'wheel_{key}', root, loc=(s * track / 2, BD.WHEEL_Y, z))
        spin = K.empty(f'spin_{key}', pivot)
        ps = K.Part(f'wheel_{key}_rim')
        rim(ps, mats, RIM_W[axle])
        t = HK.Mesh(f'tyre_{key}')
        # the bead lies under the rim's lip (its crest at RIM_R + 0.016 stays proud of the sidewall's foot)
        # 12 mm over the tread's width at the sidewalls' bulge, as the tyre the photos were fitted with (the outline
        # of c12 / c32 lost that strip with the plain width)
        got = CC.tyre(t, TYRE_R, RIM_R + 0.002, TYRE_W[axle] + 0.012, RIM_W[axle] - 0.006, grooves=3)
        info = info or got
        r_disc = 0.205 if axle == 'f' else 0.195
        x_face = RIM_W[axle] / 2 + 0.012 - 0.14 + 0.018            # the old rotor's outer face
        CC.brake_disc(t, r_disc, x_face, thick=0.036, r_hat=0.100, hat=0.032, vented=True)
        c = HK.Mesh(f'caliper_{key}')
        CC.caliper(c, r_disc, x_face, thick=0.036, kind='4pot', angle=-40.0 if axle == 'f' else -35.0, colour='cal_red')
        if s < 0:
            bmesh.ops.scale(ps.bm, vec=(-1, 1, 1), verts=ps.bm.verts)
            for f in ps.bm.faces:
                f.normal_flip()
            t, c = CC.turned(t), c.mirrored()
        total += ps.tris() + t.tris() + c.tris()
        ps.build(spin)
        made += [(t, spin), (c, pivot)]
    mats.mats['tire'] = CC.tyre_material(info, 'NOCTURNE', '275/35ZR21 103Y')
    for mesh, parent in made:
        CC.build(mesh, parent, mats.mats)
    count['wheels'] = total


def cabin(body, mats, count):
    """The cabin (the car had none): a tub and car_common's furniture for two, left-hand drive. Laid out by
    proportion under the glass (windscreen header 1.31 up at z 0.4, its base about 0.92 up at z 1.5; side glass from
    0.92 up, back to z -0.95), not measured on a photo of the inside: it is there to be seen through the glass."""
    import car_common as CC
    import hayate_kit as HK
    tub = K.Part('interior')
    it, dash, pl, carpet = mats['interior'], mats['c_dash'], mats['c_plastic'], mats['c_carpet']
    tub.face([(-0.74, 0.20, -0.62), (0.74, 0.20, -0.62), (0.74, 0.20, 1.45), (-0.74, 0.20, 1.45)], carpet, smooth=False, out=(0, 1, 0))
    for s in (1, -1):
        tub.face([(0.76 * s, 0.20, -0.62), (0.76 * s, 0.20, 0.95), (0.76 * s, 0.90, 0.95), (0.76 * s, 0.90, -0.62)], it,
                 smooth=False, out=(-s, 0, 0))
    tub.face([(-0.76, 0.20, -0.62), (0.76, 0.20, -0.62), (0.76, 1.05, -0.62), (-0.76, 1.05, -0.62)], it, smooth=False, out=(0, 0, 1))
    tub.box(dash, (0.0, 0.80, 1.20), (1.50, 0.20, 0.56), bevel=0.05, seg=2)
    tub.box(pl, (0.0, 0.31, 0.20), (0.22, 0.22, 1.50), bevel=0.03, seg=1)
    tub.box(pl, (0.0, 0.62, 0.86), (0.26, 0.40, 0.20), bevel=0.03, seg=1)
    count['interior'] = tub.tris()
    tub.build(body)
    fur = HK.Mesh('furniture')
    for x in (-0.36, 0.36):
        CC.seat(fur, x, 0.20, 0.20, width=0.48, length=0.50, h=0.14, back=0.56, recline=24.0, headrest='bucket',
                bolster=1.4, cloth='c_leather', insert='c_red')
    CC.steering_wheel(fur, (0.36, 0.74, 0.78), tilt=20.0, R=0.175)
    CC.binnacle(fur, 0.36, 0.895, 0.93, width=0.36, height=0.07, depth=0.20)
    CC.inside_mirror(fur, 1.20, 0.46)
    count['furniture'] = fur.tris()
    CC.build(fur, body, mats.mats)


def finish(root, body, mats, count):
    """after the body's last deformation (car_common): what hangs under the floor of an electric car (the battery
    case, a drive unit, shafts and arms at each axle), the plain materials into two painted atlases, every corner's
    share of the sky. The carbon keeps its clear coat and the engine cover's strips their light: materials of
    their own."""
    import car_common as CC
    import hayate_kit as HK
    CC.underseal([o for o in body.children_recursive if o.type == 'MESH'], mats.mats)
    ub = HK.Mesh('underbody')
    # the battery's case lies above the sills' lower edge (0.14 up at the rear, 0.185 at the front)
    CC.underbody(ub, 0.195, BD.AXLE, -BD.AXLE, BD.TRACK_F, BD.TRACK_R, BD.WHEEL_Y, tip=(0.5, 0.2, -2.4), layout='EV')
    count['underbody'] = ub.tris()
    CC.build(ub, body, mats.mats)
    trim = CC.Atlas('trim')
    rim_atlas = CC.Atlas('rim', size=512, fill=('#8a8c8f', 0.32, 0.85))
    rim_atlas.region('disc', CC.disc_image(), 0.38, 0.85)
    made = CC.consolidate(root, trim, rim_atlas, own=('tire', 'carbon', 'lightstrip'))
    tyres = [o for o in root.children_recursive
             if o.type == 'MESH' and any(mm and mm.name == 'tire' for mm in o.data.materials)]
    CC.bake_ao(root, made + tyres)
