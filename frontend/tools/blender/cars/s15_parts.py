"""
The S15's separate parts: wheels (the spec-R's 16" five-spoke, 205/55R16, discs, calipers), arch liners, lamp internals,
plates, mirrors, door handles, wipers, badges (drawn as our own shapes), the Aero wing (option), exhaust, and a basic
interior. All in the game frame (s15_kit.Part).
"""
import math

import numpy as np
from mathutils import Vector

import s15_kit as K
import s15_body as BD
from s15_kit import lerp


class Surface:
    """ray casts against the finished shell (game frame)"""

    def __init__(self, bvh):
        self.bvh = bvh

    def hit(self, origin, direction):
        loc, n, _, _ = self.bvh.ray_cast(K.B(*origin), K.B(*direction) - K.B(0, 0, 0))
        if loc is None:
            return None, None
        return Vector(K.G(loc)), Vector(K.G(n))

    def side(self, z, y, s=1):
        return self.hit((s * 2.0, y, z), (-s, 0, 0))

    def top(self, x, z):
        return self.hit((x, 3.0, z), (0, -1, 0))


# ---------------------------------------------------------------- wheels

TYRE_W = 0.205
RIM_R = 0.2032          # 16" bead seat
AX = TYRE_W / 0.215     # the profiles below were drawn for a 215 section
SPOKE_FACE = 0.058      # how far the spoke face sits outboard of the wheel's centre plane


def tyre(p, s, seg=48):
    """205/55R16 tyre about the origin (axis x, s = outward sign); tread blocks on the shoulders"""
    R = BD.TYRE_R
    h = TYRE_W / 2
    prof = [(RIM_R + 0.004, -0.086), (RIM_R + 0.022, -0.100), (R - 0.040, -0.108), (R - 0.016, -0.104), (R - 0.004, -0.092),
            (R, -0.080), (R, -0.058), (R - 0.008, -0.055), (R - 0.008, -0.047), (R, -0.044), (R, -0.014), (R - 0.008, -0.011),
            (R - 0.008, -0.003), (R, 0.000), (R, 0.030), (R - 0.008, 0.033), (R - 0.008, 0.041), (R, 0.044), (R, 0.080),
            (R - 0.004, 0.092), (R - 0.016, 0.104), (R - 0.040, 0.108), (RIM_R + 0.022, 0.100), (RIM_R + 0.004, 0.086)]
    rows = []
    for i in range(seg):
        t = 2 * math.pi * (i + 0.5 * (i % 2 == 0) * 0) / seg
        row = []
        for k, (r, a) in enumerate(prof):
            rr = r
            # shoulder blocks: every other segment's shoulder sits a little lower
            if k in (4, 5, 6, 18, 19, 20) and i % 2:
                rr -= 0.005
            row.append((s * a * AX, rr * math.cos(t), rr * math.sin(t)))
        rows.append(row)
    rows.append(rows[0])
    p.grid(rows, 'tire', flip=s > 0)


def rim(p, s, seg=48):
    """the rim barrel and lip, five broad swept spokes, hub, lug nuts and centre cap"""
    # barrel: from the outer lip in to the inner flange (inside faces visible through the spokes)
    prof = [(RIM_R + 0.012, s * 0.098), (RIM_R + 0.012, s * 0.090), (RIM_R - 0.004, s * 0.086), (RIM_R - 0.012, s * 0.078),
            (RIM_R - 0.022, s * 0.060), (RIM_R - 0.024, s * -0.080), (RIM_R - 0.010, s * -0.095)]
    rows = []
    for i in range(seg + 1):
        t = 2 * math.pi * i / seg
        rows.append([(a * AX, r * math.cos(t), r * math.sin(t)) for r, a in prof])
    # faces outboard on the lip, towards the axle inside the barrel (seen through the spokes)
    p.grid(rows, 'rim', out=lambda c: (s * 0.5, -c[1], -c[2]))
    # spokes
    for k in range(5):
        base = 2 * math.pi * k / 5
        _spoke(p, s, base)
    # hub disc and centre cap
    p.cylinder('rim', (s * (SPOKE_FACE - 0.004), 0, 0), 0.075, 0.03, 'x', seg=24)
    p.cylinder('chrome', (s * (SPOKE_FACE + 0.012), 0, 0), 0.030, 0.012, 'x', seg=20)
    for k in range(5):
        t = 2 * math.pi * (k + 0.5) / 5
        p.cylinder('chrome', (s * (SPOKE_FACE + 0.014), 0.050 * math.cos(t), 0.050 * math.sin(t)), 0.0105, 0.018, 'x', seg=6)


def _spoke(p, s, base):
    """one spoke of the spec-R wheel: broad, widening to the rim, swept round (its edges curve the same way), dished"""
    def depth(r):
        # dish: the face runs from the hub out to the lip
        return SPOKE_FACE + 0.030 * max(0.0, (r - 0.07) / 0.13) ** 1.5

    def swirl(r):
        return s * 0.30 * max(0.0, (r - 0.06) / 0.135) ** 1.3

    def strip(r0, r1, w0, w1, off0, off1, n=5, th=0.022):
        rows_top, rows_bot = [], []
        for j in range(n + 1):
            t = j / n
            r = lerp(r0, r1, t)
            w = lerp(w0, w1, t)
            off = lerp(off0, off1, t)
            ang = base + swirl(r) + off / r
            c, sn = math.cos(ang), math.sin(ang)
            tc, ts = -sn, c
            d = depth(r)
            row = []
            for e in (-1, -0.6, 0.6, 1):
                ww = w / 2 * e
                bevel = 0.006 if abs(e) == 1 else 0.0
                y = r * c + ww * tc
                z = r * sn + ww * ts
                row.append((s * (d - bevel), y, z))
            rows_top.append(row)
            rows_bot.append([(s * (d - th), y, z) for (_, y, z) in [row[0], row[3]]])
        p.grid(rows_top, 'rim', flip=s > 0)
        # sides
        p.grid([[rows_top[j][0], (s * (depth(lerp(r0, r1, j / n)) - th), rows_top[j][0][1], rows_top[j][0][2])] for j in range(n + 1)],
               'rim', flip=s < 0)
        p.grid([[rows_top[j][3], (s * (depth(lerp(r0, r1, j / n)) - th), rows_top[j][3][1], rows_top[j][3][2])] for j in range(n + 1)],
               'rim', flip=s > 0)
    strip(0.058, RIM_R - 0.006, 0.050, 0.092, 0.0, 0.0, n=8)


def disc_and_caliper(p_spin, p_pivot, s, front):
    r_disc = 0.140 if front else 0.129
    a = -0.045
    # (the profiles run so the faces look outward on either side)
    rot = [(0.085, s * (a - 0.012)), (r_disc, s * (a - 0.012)), (r_disc, s * (a + 0.012)), (0.085, s * (a + 0.012))]
    hat = [(0.06, s * (a + 0.012)), (0.085, s * (a + 0.012)), (0.085, s * (a + 0.03)), (0.06, s * (a + 0.03))]
    p_spin.revolve('disc', rot if s < 0 else rot[::-1], (0, 0, 0), 'x', seg=36, smooth=False)
    p_spin.revolve('disc', hat if s < 0 else hat[::-1], (0, 0, 0), 'x', seg=18, smooth=False)
    # caliper behind the axle (trailing), a curved block over the disc's edge
    ang0 = math.pi * (1.05 if front else 0.95)
    rows_o, rows_i = [], []
    for j in range(7):
        t = ang0 + (j / 6 - 0.5) * 0.85
        row = []
        for r in (r_disc - 0.035, r_disc + 0.012):
            row.append((r * math.cos(t), r * math.sin(t)))
        rows_o.append(row)
    for x0, x1 in ((a + 0.014, a + 0.040), (a - 0.040, a - 0.014)):
        pts_top = [[(s * x1, y, z) for y, z in row] for row in rows_o]
        pts_bot = [[(s * x0, y, z) for y, z in row] for row in rows_o]
        p_pivot.grid(pts_top, 'brake', flip=s < 0)
        p_pivot.grid(pts_bot, 'brake', flip=s > 0)
        p_pivot.grid([[pts_top[j][1], pts_bot[j][1]] for j in range(7)], 'brake', flip=s > 0)
        p_pivot.grid([[pts_top[j][0], pts_bot[j][0]] for j in range(7)], 'brake', flip=s < 0)
    # bridge over the disc
    t = ang0
    p_pivot.oriented_box('brake', (s * a, (r_disc + 0.006) * math.cos(t), (r_disc + 0.006) * math.sin(t)), (0.085, 0.018, 0.07),
                         rot=(t, 0, 0), bevel=0.004)


def wheels(root, mats, count):
    nodes = {}
    for name, zc, s in (('fl', BD.AXLE_F, 1), ('fr', BD.AXLE_F, -1), ('rl', BD.AXLE_R, 1), ('rr', BD.AXLE_R, -1)):
        x = s * (BD.TRACK_F if name[0] == 'f' else BD.TRACK_R) / 2
        pivot = K.empty(f'wheel_{name}', (x, BD.TYRE_R, zc), root)
        spin = K.empty(f'spin_{name}', (0, 0, 0), pivot)
        ps = K.Part(f'wheel_{name}_parts')
        tyre(ps, s)
        rim(ps, s)
        pc = K.Part(f'caliper_{name}')
        disc_and_caliper(ps, pc, s, name[0] == 'f')
        count['wheels'] = count.get('wheels', 0) + ps.tris() + pc.tris()
        ps.build(spin, mats)
        pc.build(pivot, mats)
        nodes[name] = pivot
    return nodes


# ---------------------------------------------------------------- arch liners

def liners(p):
    for zc in (BD.AXLE_F, BD.AXLE_R):
        for s in (1, -1):
            r = BD.ARCH_R + 0.004
            rows = []
            for i in range(25):
                t = math.radians(-12 + (192 + 12) * i / 24)
                rows.append([(s * x, BD.TYRE_R + r * math.sin(t), zc + r * math.cos(t)) for x in (0.47, 0.70, 0.835)])
            p.grid(rows, 'trim', out=lambda c, zc=zc: (0, BD.TYRE_R - c[1], zc - c[2]))
            # inner wall
            ring = [(s * 0.47, BD.TYRE_R + r * math.sin(math.radians(-12 + 204 * i / 24)), zc + r * math.cos(math.radians(-12 + 204 * i / 24)))
                    for i in range(25)]
            for i in range(24):
                q = [(s * 0.47, BD.TYRE_R - 0.06, zc), ring[i], ring[i + 1]]
                p.face(q if s > 0 else q[::-1], 'trim', smooth=False)


# ---------------------------------------------------------------- lamps

def head_units(p, info):
    d = Vector((0, 0.25, 1)).normalized()    # the lamps look forward and a little up
    for i, (pt, n) in enumerate(info['head']):
        if pt is None:
            continue
        s = 1 if pt.x > 0 else -1
        projector = i % 2 == 0
        # set back so nothing pokes through the (opaque) lens: the lens texture draws the units (lamp review
        # 2026-11-10: the shroud's rim showed as a bold white ring)
        back = pt - d * 0.062
        if projector:
            # projector: a chrome shroud, the lens (glows) in front
            _axis_cyl(p, 'chrome', back, d, 0.034, 0.030)
            _axis_cyl(p, 'trim', back + d * 0.030, d, 0.031, 0.004)
            _axis_cyl(p, 'headlight', back + d * 0.033, d, 0.027, 0.010, uv=True)
        else:
            # high beam: a reflector bowl and its bulb
            _axis_cyl(p, 'chrome', back, d, 0.032, 0.022, r2=0.020)
            _axis_cyl(p, 'headlight', back + d * 0.012, d, 0.011, 0.010, uv=True)


def _axis_cyl(p, mat, base, d, r, length, r2=None, seg=20, uv=False):
    """a capped cylinder (or cone) from `base` along unit vector d"""
    d = Vector(d).normalized()
    a = d.orthogonal().normalized()
    b = d.cross(a)
    r2 = r if r2 is None else r2
    ring0 = [base + (a * math.cos(2 * math.pi * k / seg) + b * math.sin(2 * math.pi * k / seg)) * r2 for k in range(seg)]
    ring1 = [base + d * length + (a * math.cos(2 * math.pi * k / seg) + b * math.sin(2 * math.pi * k / seg)) * r for k in range(seg)]
    for k in range(seg):
        k2 = (k + 1) % seg
        p.face([tuple(ring0[k]), tuple(ring0[k2]), tuple(ring1[k2]), tuple(ring1[k])], mat, smooth=True)
    uvs = [(0.5 + 0.5 * math.cos(2 * math.pi * k / seg), 0.5 + 0.5 * math.sin(2 * math.pi * k / seg)) for k in range(seg)] if uv else None
    p.face([tuple(v) for v in ring1], mat, smooth=False, uvs=uvs)


def fog_units(p, info):
    for pt, n in info['fog']:
        if pt is None:
            continue
        base = pt - Vector((0, 0, 0.040))
        _axis_cyl(p, 'chrome', base, (0, 0, 1), 0.040, 0.016, r2=0.026)
        _axis_cyl(p, 'chrome', base + Vector((0, 0, 0.016)), (0, 0, 1), 0.034, 0.006)
        _axis_cyl(p, 'lens_clear', base + Vector((0, 0, 0.020)), (0, 0, 1), 0.011, 0.004)
        _axis_cyl(p, 'trim', base + Vector((0, 0, 0.002)), (0, 0, 1), 0.047, 0.004)


def plate(p, pt, n, rear):
    """a white plate (330 × 165 mm) standing off the bumper by a bracket"""
    if pt is None:
        return
    s = -1 if rear else 1
    c = pt + Vector((0, 0, s * 0.006))
    z0, z1 = (c.z - 0.006, c.z) if not rear else (c.z, c.z + 0.006)
    # textured face: u across, v up
    w, h = 0.165, 0.0825
    pts = [(c.x - w * s, c.y - h, c.z + s * 0.0001), (c.x + w * s, c.y - h, c.z + s * 0.0001), (c.x + w * s, c.y + h, c.z + s * 0.0001),
           (c.x - w * s, c.y + h, c.z + s * 0.0001)]
    p.face(pts, 'plate', smooth=False, uvs=[(0, 0), (1, 0), (1, 1), (0, 1)])
    p.box('trim', c.x - w - 0.008, c.x + w + 0.008, c.y - h - 0.008, c.y + h + 0.008, min(z0, z1) - s * 0.004 - 0.004,
          max(z0, z1) - s * 0.004 - 0.002 if not rear else min(z0, z1) + 0.004, bevel=0.003)


# ---------------------------------------------------------------- body fittings

# door mirrors, measured on the photos (r48 rear-on, r43 front, r41 / r10 3/4: back-projected through the solved
# cameras): the painted housing reaches from x 0.76 to 0.98, y 0.875 to 1.01, centred about z 0.40, on a painted
# sail at the door's front corner. Built as their own object ('mirrors'): the fitted body field moves them rigidly
# with the door (s15_ffd, ffd_rigid) instead of squeezing their measured size.
MIRROR_ANCHOR = (0.43, 0.86)            # (z, y) of the sail's foot on the door skin


def mirrors(p, surf):
    """returns the left anchor (game frame) on the door skin; the right one mirrors it"""
    anchor = None
    for s in (1, -1):
        hit, n = surf.side(MIRROR_ANCHOR[0], MIRROR_ANCHOR[1], s)
        if hit is None:
            continue
        bx = hit.x
        if s == 1:
            anchor = (bx, MIRROR_ANCHOR[1], MIRROR_ANCHOR[0])
        # the sail: a painted wedge on the door's front corner, under the A-pillar foot
        p.oriented_box('paint', (bx - s * 0.004, 0.925, 0.47), (0.040, 0.115, 0.140), rot=(0.25, 0, 0), bevel=0.012)
        p.oriented_box('trim', (bx + s * 0.010, 0.900, 0.43), (0.028, 0.050, 0.060), bevel=0.008)
        # the housing: a rounded box, the glass on its rear face; toed in a little, the outer end swept back
        hc = (bx + s * 0.135, 0.943, 0.405)
        rot = (0, s * 0.10, 0)
        p.oriented_box('paint', hc, (0.215, 0.135, 0.110), rot=rot, bevel=0.048, seg=4)
        gz = hc[2] - 0.055 + 0.007
        p.oriented_box('chrome', (hc[0] + s * 0.004, 0.943, gz), (0.188, 0.106, 0.004), rot=rot, bevel=0.003)
    return anchor


def door_handles(p, surf):
    for s in (1, -1):
        hit, n = surf.side(-0.27, 0.835, s)
        if hit is None:
            continue
        x = hit.x
        p.oriented_box('trim', (x - s * 0.002, 0.835, -0.27), (0.006, 0.040, 0.125), bevel=0.003)
        p.oriented_box('paint', (x + s * 0.006, 0.838, -0.27), (0.014, 0.024, 0.115), bevel=0.006)


def wipers(p, surf):
    for x0, x1 in ((-0.50, 0.12), (0.06, 0.62)):
        pts = []
        for t in np.linspace(0, 1, 8):
            x = lerp(x0, x1, t)
            z = 0.95 - 0.18 * (abs(x) / 0.70) ** 2.2 - 0.03 - 0.02 * t
            hit, n = surf.top(x, z)
            if hit is None:
                continue
            pts.append(hit + n * 0.012)
        for a, b in zip(pts[:-1], pts[1:]):
            _beam(p, 'trim', a, b, 0.014, 0.010)
        if pts:
            _beam(p, 'trim', pts[0] + Vector((0, 0, 0.06)), pts[0], 0.02, 0.016)
    for s in (1, -1):
        hit, n = surf.top(s * 0.24, 1.13)
        if hit is not None:
            p.oriented_box('trim', tuple(hit + n * 0.004), (0.018, 0.012, 0.028), bevel=0.004)


def rear_wiper(p, surf):
    """the rear wiper along the backlight's base (r48, r30): the pivot just left of the centre, the blade to the left"""
    pts = []
    for x in np.linspace(0.06, 0.58, 7):
        hit, n = surf.top(x, -1.675 + 0.57 * x * x + 0.075)
        if hit is not None:
            pts.append(hit + n * 0.012)
    for a, b in zip(pts[:-1], pts[1:]):
        _beam(p, 'trim', a, b, 0.012, 0.010)
    if pts:
        hit, n = surf.top(0.05, -1.675 + 0.0014 + 0.03)
        if hit is not None:
            _beam(p, 'trim', hit + n * 0.010, pts[len(pts) // 2], 0.016, 0.012)
            p.oriented_box('trim', tuple(hit + n * 0.008), (0.03, 0.02, 0.03), bevel=0.006)


def _frame(n):
    """(ex, ey, ez) for a badge on a surface with outward normal n: ex to the viewer's right, ey up"""
    ez = Vector(n).normalized()
    ex = Vector((0, 1, 0)).cross(ez)
    if ex.length < 1e-6:
        ex = Vector((1, 0, 0))
    ex.normalize()
    ey = ez.cross(ex)
    return ex, ey, ez


def _place(p, bm, mat, c, frame, scale=1.0, lift=0.001):
    """merge a bmesh drawn in its own (X right, Y up, Z out) frame onto a surface point c"""
    ex, ey, ez = frame
    for v in bm.verts:
        X, Y, Z = v.co
        q = Vector(c) + ex * (X * scale) + ey * (Y * scale) + ez * (Z * scale + lift)
        v.co = K.B(*q)
    p.merge(bm, mat, smooth=False)


def text_bm(text, height, extrude=0.0012, shear=0.0):
    """a text in Blender's built-in font as a bmesh (X along the text, Y up, centred), scaled to the cap height"""
    import bmesh
    import bpy
    cu = bpy.data.curves.new('badge_txt', 'FONT')
    cu.body = text
    cu.size = 1.0
    cu.shear = shear
    cu.extrude = extrude
    cu.resolution_u = 2
    cu.align_x = 'CENTER'
    cu.align_y = 'CENTER'
    ob = bpy.data.objects.new('badge_txt', cu)
    bpy.context.scene.collection.objects.link(ob)
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    bm = bmesh.new()
    bm.from_mesh(me)
    ev.to_mesh_clear()
    bpy.data.objects.remove(ob)
    bpy.data.curves.remove(cu)
    ys = [v.co.y for v in bm.verts]
    k = height / max(1e-6, max(ys) - min(ys))
    for v in bm.verts:
        v.co = Vector((v.co.x * k, v.co.y * k, v.co.z))
    return bm


def badges(p, surf):
    """the badges, as our own shapes: the maker's ring-and-bar emblem, the model's script and the key cylinder on the
    boot lid (r48), the "S" mark on the bonnet's point (r43 / r10), "spec R" on the rear quarters (r14)"""
    import bmesh
    rear = lambda x, y: surf.hit((x, y, -4.0), (0, 0, 1))
    hit, n = rear(0.0, 0.833)
    if hit is not None:
        fr = _frame(n)
        # the ring: an annulus, the bar across it
        bm = bmesh.new()
        outer = [bm.verts.new((0.026 * math.cos(2 * math.pi * k / 28), 0.026 * math.sin(2 * math.pi * k / 28), 0.003)) for k in range(28)]
        inner = [bm.verts.new((0.0205 * math.cos(2 * math.pi * k / 28), 0.0205 * math.sin(2 * math.pi * k / 28), 0.003)) for k in range(28)]
        for k in range(28):
            k2 = (k + 1) % 28
            bm.faces.new([outer[k], outer[k2], inner[k2], inner[k]])
        _place(p, bm, 'chrome', hit, fr)
        p.oriented_box('chrome', tuple(hit + n * 0.0025), (0.074, 0.015, 0.004), bevel=0.0015)
        bm = text_bm('NISSAN', 0.0065, extrude=0.0)
        _place(p, bm, 'trim', hit, fr, lift=0.0047)
    hit, n = rear(0.0, 0.772)
    if hit is not None:
        bm = text_bm('Silvia', 0.034, extrude=0.0012, shear=0.35)
        _place(p, bm, 'chrome', hit, _frame(n), lift=0.0015)
    hit, n = rear(-0.232, 0.811)
    if hit is not None:
        p.cylinder('chrome', tuple(hit + n * 0.002), 0.017, 0.006, 'z', seg=16)
        p.oriented_box('trim', tuple(hit + n * 0.0055), (0.004, 0.016, 0.002))
    # the bonnet's "S" mark: a sharp-cornered bolt on the point of the bonnet
    hit, n = surf.top(0.0, 1.987)
    if hit is not None:
        bolt = [(0.010, 0.024), (-0.011, 0.003), (0.003, 0.003), (-0.010, -0.024), (0.011, -0.003), (-0.003, -0.003)]
        bm = bmesh.new()
        top = [bm.verts.new((u, v, 0.003)) for u, v in bolt]
        bot = [bm.verts.new((u, v, 0.0)) for u, v in bolt]
        bmesh.ops.triangle_fill(bm, edges=[bm.edges.new((top[i], top[(i + 1) % 6])) for i in range(6)], use_beauty=True)
        for i in range(6):
            i2 = (i + 1) % 6
            bm.faces.new([bot[i], bot[i2], top[i2], top[i]])
        _place(p, bm, 'chrome', hit, _frame(n))
    # "spec R" on both rear quarters, ahead of the rear arch
    for s in (1, -1):
        hit, n = surf.side(-0.715, 0.496, s)
        if hit is None:
            continue
        fr = _frame(n)
        bm = text_bm('spec', 0.011, extrude=0.0008, shear=0.3)
        _place(p, bm, 'chrome', hit - fr[0] * 0.006, fr)
        bm = text_bm('R', 0.014, extrude=0.0008, shear=0.3)
        _place(p, bm, 'reflector', hit + fr[0] * 0.026, fr)


def _beam(p, mat, a, b, w, h):
    a, b = Vector(a), Vector(b)
    d = b - a
    L = d.length
    if L < 1e-6:
        return
    c = (a + b) / 2
    yaw = math.atan2(d.x, d.z)
    pitch = -math.asin(max(-1, min(1, d.y / L)))
    p.oriented_box(mat, tuple(c), (w, h, L), rot=(pitch, yaw, 0), bevel=min(w, h) * 0.3)


def spoiler(p, surf):
    """the factory rear wing: a mainplane on two stands, a high-mount stop lamp under its middle"""
    # a low pedestal wing: ~9 cm uprights, the blade just above the boot lid
    ztr, zle = -2.200, -2.010
    span = 0.62
    hit, n = surf.top(0.50, -2.10)
    deck = hit.y if hit is not None else 0.96
    yb = deck + 0.090
    rows = []
    for x in np.linspace(-span, span, 15):
        f = abs(x) / span
        drop = 0.020 * max(0.0, (f - 0.85) / 0.15) ** 2
        y = yb - drop
        sec = []
        for t, dy in ((0.0, 0.0), (0.12, 0.012), (0.5, 0.017), (0.88, 0.009), (1.0, 0.0), (0.88, -0.007), (0.5, -0.010),
                      (0.12, -0.007)):
            z = lerp(zle, ztr, t)
            sec.append((x, y + dy + 0.022 * t, z))
        rows.append(sec)
    p.grid(rows, 'paint', closed_u=True, flip=True)
    for x in (-span, span):
        row = rows[0] if x < 0 else rows[-1]
        c = tuple(sum(np.array(v) for v in row) / len(row))
        for k in range(len(row)):
            q = [c, row[k], row[(k + 1) % len(row)]]
            p.face(q if x > 0 else q[::-1], 'paint', smooth=False)
    for s in (1, -1):
        x = s * 0.50
        hit, n = surf.top(x, -2.10)
        y0 = hit.y - 0.01 if hit is not None else deck - 0.01
        p.oriented_box('paint', (x, (y0 + yb + 0.01) / 2, -2.105), (0.030, yb + 0.01 - y0, 0.12), rot=(0.10, 0, 0), bevel=0.010)
    p.oriented_box('reflector', (0, yb - 0.004, -2.12), (0.22, 0.014, 0.022), bevel=0.005)


def exhaust(p):
    # two round tips side by side on the left (+x), as on the stock S15; measured on the rear-on photo (r48): centres
    # x 0.36 / 0.445, y 0.275, about 72 mm across (the fitted field lowers them ~17 mm, hence y 0.292 here)
    for x in (0.362, 0.448):
        # the tips just peek out under the bumper
        p.revolve('chrome', [(0.033, -2.10), (0.036, -2.205), (0.032, -2.21), (0.028, -2.17)], (x, 0.292, 0), 'z', seg=20)
        p.cylinder('trim', (x, 0.292, -2.175), 0.028, 0.004, 'z', seg=16)
    p.box('trim', 0.32, 0.49, 0.25, 0.32, -2.10, -1.90, bevel=0.02)


# ---------------------------------------------------------------- interior

def interior(p):
    m = 'interior'
    # floor and tunnel
    p.box(m, -0.74, 0.74, 0.20, 0.23, -1.62, 0.60)
    p.box(m, -0.12, 0.12, 0.23, 0.42, -1.10, 0.55, bevel=0.05)
    # dash: a wedge under the windshield, the binnacle in front of the driver (right-hand drive: x < 0)
    p.oriented_box(m, (0, 0.80, 0.30), (1.45, 0.16, 0.42), rot=(0.25, 0, 0), bevel=0.04)
    p.oriented_box(m, (0, 0.62, 0.20), (1.40, 0.24, 0.18), bevel=0.03)
    p.oriented_box(m, (-0.37, 0.90, 0.10), (0.36, 0.08, 0.16), rot=(-0.2, 0, 0), bevel=0.03)
    p.oriented_box(m, (0, 0.62, 0.08), (0.24, 0.30, 0.22), bevel=0.03)
    # steering wheel and column
    c = Vector((-0.37, 0.80, -0.06))
    d = Vector((0, 0.35, -1.0)).normalized()
    a = Vector((1, 0, 0))
    b = d.cross(a)
    ring = []
    for k in range(24):
        t = 2 * math.pi * k / 24
        ring.append(c + (a * math.cos(t) + b * math.sin(t)) * 0.180)
    for k in range(24):
        _beam(p, 'trim', ring[k], ring[(k + 1) % 24], 0.028, 0.028)
    for t in (0, math.pi, -math.pi / 2):
        _beam(p, 'trim', c, c + (a * math.cos(t) + b * math.sin(t)) * 0.17, 0.05, 0.02)
    _beam(p, 'trim', c - d * 0.02, c - d * 0.32, 0.06, 0.06)
    # front seats
    for s in (1, -1):
        x = s * 0.37
        p.oriented_box(m, (x, 0.36, -0.62), (0.50, 0.12, 0.52), rot=(-0.08, 0, 0), bevel=0.05)
        p.oriented_box(m, (x, 0.72, -0.94), (0.50, 0.66, 0.12), rot=(-0.28, 0, 0), bevel=0.05)
        p.oriented_box(m, (x, 1.08, -1.06), (0.26, 0.17, 0.10), rot=(-0.25, 0, 0), bevel=0.04)
        # door cards
        p.box(m, s * 0.70 - 0.02, s * 0.70 + 0.02, 0.30, 0.88, -0.62, 0.36, bevel=0.01)
        p.box(m, s * 0.66 - 0.02, s * 0.66 + 0.02, 0.32, 0.88, -1.28, -0.66, bevel=0.01)
    # rear seat and parcel shelf
    p.oriented_box(m, (0, 0.40, -1.32), (1.20, 0.14, 0.42), bevel=0.05)
    p.oriented_box(m, (0, 0.70, -1.52), (1.20, 0.55, 0.12), rot=(-0.35, 0, 0), bevel=0.05)
    p.box(m, -0.62, 0.62, 0.90, 0.93, -1.85, -1.55)
    # headliner (seen through the glass from below)
    rows = []
    for z in np.linspace(-1.10, 0.05, 7):
        row = []
        for x in np.linspace(-0.62, 0.62, 7):
            y = min(BD.YTOP(z), BD.YRAIL(z) + 0.05) - 0.035 - 0.05 * (abs(x) / 0.62) ** 2
            row.append((x, y, z))
        rows.append(row)
    p.grid(rows, m, flip=False)
