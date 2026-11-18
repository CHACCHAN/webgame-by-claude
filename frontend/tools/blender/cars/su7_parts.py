"""
Parts of the SU7: materials, the shell with its wheel arches, the wheels, the cabin and what the shared kit adds
after the body's last deformation. (Lamps, black sections, mirrors, the lidar and the small details: su7_details.)
"""
import math
import os

import bmesh
import bpy
from mathutils import Vector

import su7_kit as K
import su7_body as BD

TEX = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'textures', 'su7')


def _img(name):
    p = os.path.join(TEX, name)
    return bpy.data.images.load(p) if os.path.exists(p) else None


def materials(paint='#35b6cf'):
    m = K.Mats()
    # Aqua Blue, the launch colour (the game recolours it), under a clear coat
    m.add('paint', paint, metallic=0.45, roughness=0.32, coat=1.0)
    m.add('glass', '#0b1016', metallic=0.1, roughness=0.04)
    m.add('trim', '#0c0d0f', metallic=0.2, roughness=0.42)             # gloss-black plastics: sills, blades, B-pillar
    m.add('chrome', '#d8dade', metallic=1.0, roughness=0.08)
    m.add('headlight', '#dfe6ee', metallic=0.4, roughness=0.1, image=_img('headlamp.png'), emissive='#fff4e0')
    m.add('taillight', '#3a0506', roughness=0.25, image=_img('taillamp.png'), emissive='#ff1a10')
    m.add('rim', '#17181b', metallic=0.85, roughness=0.36)             # the 21-inch wheels, gloss black (k13, k21)
    m.add('rimface', '#bfc2c7', metallic=1.0, roughness=0.22)          # the centre caps
    m.add('cal_yellow', '#e2b100', metallic=0.1, roughness=0.38)       # the Max's yellow four-pot calipers
    m.add('under', '#101112', roughness=0.9)
    m.add('interior', '#1e1f22', roughness=0.85)
    m.add('grille', '#060607', roughness=0.7)
    m.add('reflector', '#7a0c0c', roughness=0.3, metallic=0.2)         # the bumper's red reflectors (no lamp)
    m.add('sensor', '#07080a', metallic=0.3, roughness=0.12)           # the lidar's window, camera eyes
    m.add('screen', '#0a1a2c', metallic=0.2, roughness=0.14)           # the cabin's displays, dark
    m.add('plate', '#f6f7f4', roughness=0.5, image=_img('plate.png'))
    m.cut = bpy.data.materials.new('_cut')
    import car_common as CC
    for name in ('c_dash', 'c_plastic', 'c_carpet', 'c_lining'):       # the cabin's swatches (car_common)
        CC.material_for(m.mats, name)
    return m


# ------------------------------------------------------------------ wheel arches
ARCH_R = {'f': 0.383, 'r': 0.388}       # k13: about 3 cm round the tyres (r 0.352 / 0.360)


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
            x0 = 0.66                               # inside the tyres' inner faces (0.72 / 0.71)
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


def build_all(root, mats, ffd=True, bare=False):
    """ffd: True = the fitted field in fitdata/su7/ffd.json (when present), False = none, or a Lattice.
    bare: shell, mirrors and wheels only, plain tyres, no kit finish (the fit tools' quick builds)"""
    count = {}
    body = K.empty('body', root)
    shell, bvh = body_shell(body, mats, count)
    import su7_details as DT
    DT.build(body, mats, shell, bvh, count, bare=bare)
    if ffd is not False:
        import su7_ffd as FF
        FF.apply_to_body(body, None if ffd is True else ffd)
    if not bare:
        cabin(body, mats, count)            # after the fit's field: laid out under the fitted glass
    wheels(root, mats, count)
    if not bare:
        finish(root, body, mats, count)
    return count


# ------------------------------------------------------------------ wheels
# the Max's 21-inch option, as on the photos' cars (k13, k21: P Zero): 245/35 R21 front, 265/35 R21 rear
TYRE_W = {'f': 0.245, 'r': 0.265}
RIM_W = {'f': 0.229, 'r': 0.241}          # 9J and 9.5J (estimate)
RIM_R = 0.2667          # 21" bead seat
TYRE_R = {'f': 0.3525, 'r': 0.3595}
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


def _orient(part, out):
    part.bm.normal_update()
    o = K.B(*out) - K.B(0, 0, 0)
    for f in part.bm.faces:
        if f.normal.dot(o) < -0.2:
            f.normal_flip()


def _spoke(part, mats, path, half, depth=0.026, xo=0.0, dish=0.030):
    """one spoke arm along path [(r, angle)], half widths per point; a chamfered bar whose face sinks toward the
    hub (dish)"""
    rows = []
    for (r, a), hw in zip(path, half):
        t = (r - 0.06) / (RIM_R - 0.06)
        face = xo - 0.012 - dish * (1 - min(1.0, max(0.0, t))) ** 1.6
        ring = [(face - depth, -hw * 1.15), (face - 0.004, -hw), (face, -hw * 0.55), (face, hw * 0.55), (face - 0.004, hw),
                (face - depth, hw * 1.15)]
        rows.append([(x, r * math.sin(a) + sd * math.cos(a), r * math.cos(a) - sd * math.sin(a)) for x, sd in ring])
    sp = K.Part('spoke')
    sp.grid(rows, mats['rim'], smooth=False, closed=True)
    for row in (rows[0], rows[-1]):
        sp.face(row, mats['rim'], smooth=False)
    bmesh.ops.recalc_face_normals(sp.bm, faces=sp.bm.faces)
    part.absorb(sp)


def rim(part, mats, w):
    """the 21-inch wheel of the photos (k13, k07): five V-shaped pairs of spokes from the hub to the rim, a finer
    spoke branching off each arm half-way out (twenty ends at the rim), five bolts round the centre cap; gloss black"""
    xo = w / 2 + 0.010
    lip = K.Part('lip')
    _lathe(lip, [(xo - 0.022, RIM_R + 0.004), (xo - 0.004, RIM_R + 0.016), (xo, RIM_R + 0.014), (xo + 0.002, RIM_R + 0.006),
                 (xo + 0.002, RIM_R - 0.008), (xo - 0.03, RIM_R - 0.016)], mats['rim'])
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
    r_end = RIM_R - 0.010
    for i in range(5):
        a0 = 2 * math.pi * (i + 0.5) / 5
        for sgn in (1, -1):
            # a main arm: from the hub (beside its neighbour) out to the rim
            path, hw = [], []
            for k in range(8):
                t = k / 7
                path.append((0.058 + (r_end - 0.058) * t, a0 + sgn * (0.30 - 0.105 * t ** 0.9) * (0.058 / (0.058 + (r_end - 0.058) * t)) ** 0.0
                             if False else a0 + sgn * (0.17 + 0.035 * t)))
                hw.append(0.0125 - 0.004 * t)
            _spoke(part, mats, path, hw, xo=xo)
            # the finer branch: leaves the arm at 45 % of the way and runs out to the rim further round
            path, hw = [], []
            for k in range(6):
                t = k / 5
                r = 0.058 + (r_end - 0.058) * (0.42 + 0.58 * t)
                path.append((r, a0 + sgn * (0.185 + 0.275 * t ** 0.85)))
                hw.append(0.0062 - 0.0012 * t)
            _spoke(part, mats, path, hw, depth=0.020, xo=xo - 0.004)
    hub = K.Part('hub')
    _lathe(hub, [(xo - 0.075, 0.082), (xo - 0.050, 0.082), (xo - 0.044, 0.074), (xo - 0.042, 0.0)], mats['rim'], seg=30)
    fix_out(hub)
    part.absorb(hub)
    for i in range(5):                                   # the wheel bolts
        a = 2 * math.pi * i / 5
        b = K.Part('bolt')
        b.cylinder(mats['rim'], (xo - 0.036, 0.054 * math.sin(a), 0.054 * math.cos(a)), 0.0105, 0.016, axis='x', seg=6)
        part.absorb(b)
    cap = K.Part('cap')
    _lathe(cap, [(xo - 0.041, 0.031), (xo - 0.034, 0.029), (xo - 0.032, 0.0)], mats['rimface'], seg=24)
    fix_out(cap)
    part.absorb(cap)


def wheels(root, mats, count):
    """four pivots with spin children. Tyre, disc and caliper come from the shared kit (car_common: profiled tyres
    with their own texture set, big vented discs, yellow fixed calipers: behind the axle at the front, ahead of it
    at the rear, as k13 shows them); the rim is this car's own"""
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
        got = CC.tyre(t, TYRE_R[axle], RIM_R + 0.002, TYRE_W[axle] + 0.010, RIM_W[axle] - 0.006, grooves=3)
        info = info or got
        r_disc = 0.200 if axle == 'f' else 0.185
        x_face = RIM_W[axle] / 2 + 0.010 - 0.135 + 0.018
        CC.brake_disc(t, r_disc, x_face, thick=0.034, r_hat=0.098, hat=0.032, vented=True)
        c = HK.Mesh(f'caliper_{key}')
        CC.caliper(c, r_disc, x_face, thick=0.034, kind='4pot', angle=-38.0 if axle == 'f' else 218.0, colour='cal_yellow')
        if s < 0:
            bmesh.ops.scale(ps.bm, vec=(-1, 1, 1), verts=ps.bm.verts)
            for f in ps.bm.faces:
                f.normal_flip()
            t, c = CC.turned(t), c.mirrored()
        total += ps.tris() + t.tris() + c.tris()
        ps.build(spin)
        made += [(t, spin), (c, pivot)]
    mats.mats['tire'] = CC.tyre_material(info, 'NOCTURNE', '245/35ZR21 96Y')
    for mesh, parent in made:
        CC.build(mesh, parent, mats.mats)
    count['wheels'] = total


def cabin(body, mats, count):
    """The cabin, seen through the glass all round and from above through the glass roof: a tub, the shelf under
    the rear window, the dash with the wide centre screen standing free on it and the small display before the
    driver, the console, car_common's furniture for five (left-hand drive, as built). Laid out by proportion under
    the glass and from the cabin photos (k11, k71: looked at, not measured)."""
    import car_common as CC
    import hayate_kit as HK
    tub = K.Part('interior')
    it, dash, pl, carpet, lining = mats['interior'], mats['c_dash'], mats['c_plastic'], mats['c_carpet'], mats['c_lining']
    y0, zr, zf, hw = 0.26, -1.52, 1.20, 0.80
    tub.face([(-hw, y0, zr), (hw, y0, zr), (hw, y0, zf), (-hw, y0, zf)], carpet, smooth=False, out=(0, 1, 0))
    for s in (1, -1):               # the door cards up to the belt
        tub.face([(hw * s, y0, zr), (hw * s, y0, 0.95), (hw * s + 0.05 * s, 0.97, 0.95), (hw * s + 0.05 * s, 0.97, zr)], it,
                 smooth=False, out=(-s, 0, 0))
    tub.face([(-hw, y0, zr), (hw, y0, zr), (hw, 1.0, zr - 0.06), (-hw, 1.0, zr - 0.06)], it, smooth=False, out=(0, 0, 1))
    # the shelf under the rear window, and the dark beam across the roof where the glass panels meet
    tub.face([(-0.66, 1.0, zr - 0.06), (0.66, 1.0, zr - 0.06), (0.60, 1.01, -2.0), (-0.60, 1.01, -2.0)], lining, smooth=False,
             out=(0, 1, 0))
    tub.box(dash, (0.0, 0.86, 0.92), (1.62, 0.20, 0.56), bevel=0.06, seg=2)
    tub.box(pl, (0.0, 0.40, 0.02), (0.26, 0.30, 1.30), bevel=0.04, seg=1)            # the console between the seats
    tub.box(pl, (0.0, 0.62, 0.66), (0.30, 0.34, 0.24), bevel=0.04, seg=1)
    # the 16-inch centre screen, landscape, standing free; the slim instrument display behind the wheel
    tub.box(pl, (0.0, 1.035, 0.585), (0.385, 0.225, 0.014), bevel=0.004, seg=1)
    tub.face([(-0.185, 0.93, 0.5775), (0.185, 0.93, 0.5775), (0.185, 1.14, 0.5775), (-0.185, 1.14, 0.5775)], mats['screen'],
             smooth=False, out=(0, 0, -1))
    tub.box(pl, (0.37, 0.985, 0.66), (0.19, 0.075, 0.012), bevel=0.003, seg=1)
    tub.face([(0.28, 0.952, 0.6535), (0.46, 0.952, 0.6535), (0.46, 1.018, 0.6535), (0.28, 1.018, 0.6535)], mats['screen'],
             smooth=False, out=(0, 0, -1))
    count['interior'] = tub.tris()
    tub.build(body)
    fur = HK.Mesh('furniture')
    for x in (-0.37, 0.37):
        CC.seat(fur, x, y0, -0.34, width=0.50, length=0.50, h=0.25, back=0.62, recline=23.0, headrest='bucket',
                bolster=1.25, cloth='c_leather', insert='c_cloth2')
    CC.bench(fur, -0.66, 0.66, y0, -1.36, length=0.48, h=0.27, back=0.55, recline=27.0, places=3, headrests=True,
             cloth='c_leather', insert='c_cloth2')
    CC.steering_wheel(fur, (0.37, 0.90, 0.40), tilt=21.0, R=0.180)
    CC.inside_mirror(fur, 1.33, 0.36)
    count['furniture'] = fur.tris()
    CC.build(fur, body, mats.mats)


def finish(root, body, mats, count):
    """after the body's last deformation (car_common): what hangs under the floor of an electric car (the battery
    case, a drive unit, shafts and arms at each axle), the plain materials into two painted atlases, every corner's
    share of the sky"""
    import car_common as CC
    import hayate_kit as HK
    CC.underseal([o for o in body.children_recursive if o.type == 'MESH'], mats.mats)
    ub = HK.Mesh('underbody')
    CC.underbody(ub, 0.185, BD.AXLE, -BD.AXLE, BD.TRACK_F, BD.TRACK_R, BD.WHEEL_Y, tip=(0.5, 0.2, -2.4), layout='EV')
    count['underbody'] = ub.tris()
    CC.build(ub, body, mats.mats)
    trim = CC.Atlas('trim')
    rim_atlas = CC.Atlas('rim', size=512, fill=('#8a8c8f', 0.32, 0.85))
    rim_atlas.region('disc', CC.disc_image(), 0.38, 0.85)
    made = CC.consolidate(root, trim, rim_atlas, own=('tire', 'plate'))
    tyres = [o for o in root.children_recursive
             if o.type == 'MESH' and any(mm and mm.name == 'tire' for mm in o.data.materials)]
    CC.bake_ao(root, made + tyres)
