"""
Details of the Supra laid on the finished shell: lamps (head, indicators, fog, side repeaters, the rear clusters in the
garnish, the high-mount stop lamp), plates, the hoop rear wing, door mirrors, wipers, door handles, the exhaust, shut
lines, and the interior seen through the glass. Left-hand parts are built once and mirrored.

Positions measured on the reference photos as noted in supra_parts; the interior is estimated (JDM, right-hand drive).
"""
import math

import bmesh
from mathutils import Matrix, Vector

import supra_kit as K
import supra_body as BD
from supra_parts import Frame, surface_patch, rings_of, headlamp_outline, headlamp_frame, HEAD_DEPTH, TAIL_C, TAIL_D, TAIL_E1

# atlas cells of lamps.png (as supra_textures.CELLS)
CELLS = {
    'indicator_front': (0.0, 0.75, 0.5, 1.0),
    'amber': (0.5, 0.75, 1.0, 1.0),
    'reverse': (0.0, 0.5, 0.25, 0.75),
    'fog': (0.25, 0.5, 0.5, 0.75),
    'stop': (0.5, 0.5, 1.0, 0.75),
    'reflector': (0.0, 0.25, 0.5, 0.5),
    'amber_round': (0.5, 0.25, 0.75, 0.5),
}


def disc_lens(part, mat, c, n, r, dome=0.006, seg=18, uvbox=(0, 0, 1, 1), up=Vector((0, 1, 0))):
    """a round domed lens at c facing n"""
    n = Vector(n).normalized()
    a = up - n * up.dot(n)
    if a.length < 1e-4:
        a = Vector((1, 0, 0)) - n * n.x
    a.normalize()
    b = n.cross(a)
    u0, v0, u1, v1 = uvbox
    rings = [(1.0, 0.0), (0.7, dome * 0.6), (0.35, dome * 0.92)]
    rows = []
    for f, h in rings:
        rows.append([(Vector(c) + (a * math.cos(t) + b * math.sin(t)) * r * f + n * h, (math.cos(t) * f, math.sin(t) * f))
                     for t in (2 * math.pi * k / seg for k in range(seg))])
    centre = (Vector(c) + n * dome, (0.0, 0.0))
    vs = [[part.vert(p) for p, _ in row] for row in rows]
    cv = part.vert(centre[0])
    idx = part.slot(mat)

    def uv(q):
        return (u0 + (u1 - u0) * (0.5 + 0.5 * q[1]), v0 + (v1 - v0) * (0.5 + 0.5 * q[0]))
    for k in range(len(rows)):
        for i in range(seg):
            j = (i + 1) % seg
            if k + 1 < len(rows):
                q = [vs[k][i], vs[k][j], vs[k + 1][j], vs[k + 1][i]]
                quv = [rows[k][i][1], rows[k][j][1], rows[k + 1][j][1], rows[k + 1][i][1]]
            else:
                q = [vs[k][i], vs[k][j], cv]
                quv = [rows[k][i][1], rows[k][j][1], centre[1]]
            f = part.bm.faces.new(q)
            f.material_index = idx
            f.smooth = True
            f.normal_update()
            if (K.G(f.normal)).dot(n) < 0:
                f.normal_flip()
            for loop, qq in zip(f.loops, quv if f.verts[0] == q[0] else list(reversed(quv))):
                loop[part.uv].uv = uv(qq)


def oriented_box(part, mat, c, n, along, size, bevel=0.0):
    """a box at c with its local z on n, local x along `along` (game vectors)"""
    n = Vector(n).normalized()
    ax = (Vector(along) - n * Vector(along).dot(n)).normalized()
    ay = n.cross(ax)
    rot = Matrix((ax, ay, n)).transposed()
    part.box(mat, c, size, bevel=bevel, rot=rot)


def plate(part, mats, c, n, w=0.33, h=0.165, up=Vector((0, 1, 0))):
    """a Japanese plate (330 × 165 mm): a thin slab, its face textured"""
    n = Vector(n).normalized()
    ax = up.cross(n).normalized()           # plate's right as seen from the front... (u axis)
    ay = n.cross(ax)
    t = 0.004
    pts = []
    for (u, v) in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        pts.append(Vector(c) + ax * u * w / 2 + ay * v * h / 2)
    front = [p + n * t for p in pts]
    part.face(front, mats['plate'], smooth=False, uvs=[(0, 0), (1, 0), (1, 1), (0, 1)], out=n)
    for i in range(4):
        j = (i + 1) % 4
        part.face([pts[i], pts[j], front[j], front[i]], mats['trim'], smooth=False,
                  out=((pts[i] + pts[j]) / 2 - Vector(c)))


# ------------------------------------------------------------------ lamps
# the unit's three lenses (u, v, radius in the lamp frame) and their circles in headlamp.png (x, y, r in pixels of
# 512 × 176): a big reflector inboard, two projectors outboard
HEAD_LENSES = [((-0.190, 0.000, 0.072), (117, 87, 64)), ((-0.010, 0.006, 0.060), (270, 81, 52)),
               ((0.160, 0.012, 0.047), (403, 77, 43))]

LAMP_TOP = {}       # 3-D points along the head lamp's top edge (left), for the bonnet's shut line


def lamps(left, part_r, mats, bvh, bvh_cut):
    """left-hand lamps into `left` (mirrored later); the red lenses go to part_r too (left only)"""
    lm = mats['lamps']
    # head lamp: a teardrop recess in the wing top (cut in supra_parts: silver walls, chrome back) filled with three
    # reflector bowls in thin bright bezels, a bulb shield in the inboard one, small projector lenses in the others; the
    # bowls, shield and lenses are `headlight` (they glow at night), the rest chrome
    fr = headlamp_frame(bvh)
    out = headlamp_outline()
    LAMP_TOP['pts'] = [fr.hit(bvh, u, v)[0] for u, v in out if v > 0.05]
    LAMP_TOP['frame'] = fr
    hl = mats['headlight']
    for k, ((u, v, r), (px, py, pr)) in enumerate(HEAD_LENSES):
        p, _n = fr.hit(bvh, u, v)
        n = fr.d
        floor = p - n * HEAD_DEPTH
        box = ((px - pr) / 512, 1 - (py + pr) / 176, (px + pr) / 512, 1 - (py - pr) / 176)
        bowl(left, hl, floor + n * 0.004, n, r, 0.027, box, seg=28)
        _ring(left, mats['chrome'], floor + n * 0.031, n, r * 1.10, r * 0.985, seg=28)
        if k == 0:
            disc_lens(left, hl, floor + n * 0.012, n, r * 0.22, dome=0.008, seg=12, uvbox=box)
        else:
            disc_lens(left, hl, floor + n * 0.010, n, r * 0.42, dome=0.014, seg=18, uvbox=box)
    # a thin bright bezel round the opening
    rim = [(u * 1.010 + (0.003 if u > 0 else -0.003), v * 1.04 + (0.002 if v > 0 else -0.002)) for u, v in out]
    _ring_strip(left, bvh, rim, out, fr, mats['chrome'], lift=0.0013)
    # front indicator: an amber oval at the bumper's upper corner, over the corner duct, in a chrome rim
    fr = Frame((0.70, 0.468, 1.95), (0.60, 0.0, 1.0))
    ind = K.rounded_rect(0.0, 0.0, 0.135, 0.046, 0.023, 6)
    surface_patch(left, bvh, ind, fr, lm, lift=0.005, uvbox=CELLS['amber'])
    _ring_strip(left, bvh, K.rounded_rect(0.0, 0.0, 0.149, 0.060, 0.030, 6), ind, fr, mats['chrome'], lift=0.004)
    # amber side marker on the bumper's flank, side repeater on the front wing
    fr = Frame((0.86, 0.50, 1.72), (1.0, 0.0, 0.35), e1=(0.35, 0, -1))
    surface_patch(left, bvh, K.rounded_rect(0.0, 0.0, 0.085, 0.026, 0.013, 5), fr, lm, lift=0.003,
                  uvbox=CELLS['indicator_front'])
    fr = Frame((0.88, 0.69, 0.98), (1, 0, 0), e1=(0, 0, -1))
    surface_patch(left, bvh, K.ellipse(0, 0, 0.034, 0.012, 16), fr, lm, lift=0.0025, uvbox=CELLS['amber'])
    # rear clusters: four big round lenses in raised black bezels in the housing recess (inboard reverse, two red,
    # outboard amber), the outer one wrapping round the corner
    us = (-0.205, -0.068, 0.068, 0.205)
    kinds = ('reverse', 'red', 'red', 'amber_round')
    R = 0.060
    fr = Frame(TAIL_C, TAIL_D, e1=TAIL_E1)
    for u, kind in zip(us, kinds):
        p, n = fr.hit(bvh_cut, u, 0.0, strict=True)
        if p is None:
            continue
        n = (n + Vector((0, 0, -0.35))).normalized()
        bezel(left, mats['chrome'], p - n * 0.004, n, R + 0.008, 0.018)
        top = p + n * 0.014
        if kind == 'red':
            disc_lens(part_r, mats['taillight'], top, n, R, dome=0.012, seg=24)
        else:
            disc_lens(left, lm, top, n, R, dome=0.012, seg=24, uvbox=CELLS[kind])
    # red reflector low on the bumper's flank
    fr = Frame((0.84, 0.50, -1.97), (1.0, 0, -0.35), e1=(0.3, 0, 1))
    surface_patch(left, bvh, K.rounded_rect(0, 0, 0.11, 0.028, 0.012, 4), fr, lm, lift=0.003, uvbox=CELLS['reflector'])


def bezel(part, mat, c, n, r, depth, seg=24):
    """a short black tube (open at the back) with a flat front ring: the raised bezel round a tail lens"""
    n = Vector(n).normalized()
    a = Vector((0, 1, 0)) - n * n.y
    a.normalize()
    b = n.cross(a)
    ring = [(a * math.cos(t) + b * math.sin(t)) for t in (2 * math.pi * k / seg for k in range(seg))]
    back = [Vector(c) + d * r for d in ring]
    front = [Vector(c) + d * r + n * depth for d in ring]
    inner = [Vector(c) + d * (r - 0.006) + n * depth for d in ring]
    for k in range(seg):
        j = (k + 1) % seg
        part.face([back[k], back[j], front[j], front[k]], mat, smooth=True, out=ring[k])
        part.face([front[k], front[j], inner[j], inner[k]], mat, smooth=False, out=n)


def bowl(part, mat, c, n, r, depth, uvbox, seg=24):
    """a concave reflector bowl: its rim at c + n·depth (radius r), its bottom at c; faces look out along n"""
    n = Vector(n).normalized()
    a = Vector((0, 1, 0)) - n * n.y
    a.normalize()
    b = n.cross(a)
    u0, v0, u1, v1 = uvbox
    rings = [(1.0, depth), (0.78, depth * 0.55), (0.52, depth * 0.24), (0.26, depth * 0.06)]
    rows = []
    for f, h in rings:
        rows.append([(Vector(c) + (a * math.cos(t) + b * math.sin(t)) * r * f + n * h, (math.cos(t) * f, math.sin(t) * f))
                     for t in (2 * math.pi * k / seg for k in range(seg))])
    rows.append([(Vector(c), (0.0, 0.0))])

    def uv(q):
        return (u0 + (u1 - u0) * (0.5 + 0.5 * q[1]), v0 + (v1 - v0) * (0.5 + 0.5 * q[0]))
    for k in range(len(rows) - 1):
        for i in range(seg):
            j = (i + 1) % seg
            if len(rows[k + 1]) > 1:
                q = [rows[k][i], rows[k][j], rows[k + 1][j], rows[k + 1][i]]
            else:
                q = [rows[k][i], rows[k][j], rows[k + 1][0]]
            f = part.face([p for p, _ in q], mat, uvs=[uv(t) for _, t in q], out=n)


def _disc(part, mat, c, n, r, seg=20):
    n = Vector(n).normalized()
    a = Vector((0, 1, 0)) - n * n.y
    a.normalize()
    b = n.cross(a)
    pts = [Vector(c) + (a * math.cos(t) + b * math.sin(t)) * r for t in (2 * math.pi * k / seg for k in range(seg))]
    part.face(pts, mat, smooth=False, out=n)


def _ring(part, mat, c, n, r0, r1, seg=20):
    n = Vector(n).normalized()
    a = Vector((0, 1, 0)) - n * n.y
    a.normalize()
    b = n.cross(a)
    for k in range(seg):
        t0, t1 = 2 * math.pi * k / seg, 2 * math.pi * (k + 1) / seg
        q = [Vector(c) + (a * math.cos(t) + b * math.sin(t)) * r for t, r in ((t0, r0), (t1, r0), (t1, r1), (t0, r1))]
        part.face(q, mat, smooth=False, out=n)


def _ring_strip(part, bvh, outer, inner, fr, mat, lift):
    """a band on the surface between two outlines with the same point count"""
    o = [fr.hit(bvh, u, v) for u, v in outer]
    i = [fr.hit(bvh, u, v) for u, v in inner]
    n = len(outer)
    for k in range(n):
        j = (k + 1) % n
        q = [o[k][0] + o[k][1] * lift, o[j][0] + o[j][1] * lift, i[j][0] + i[j][1] * lift, i[k][0] + i[k][1] * lift]
        part.face(q, mat, smooth=True, out=o[k][1])


# ------------------------------------------------------------------ wing
def _foil_loft(path, thick, plane):
    """rings of an airfoil section swept along path [(x, y, le_z, te_z)]: plane=True for the main plane (camber,
    trailing edge raised), False for a stay (symmetric); the section's thickness lies across the path in x-y"""
    rows = []
    for i, (x, y, le, te) in enumerate(path):
        a = path[max(0, i - 1)]
        b = path[min(len(path) - 1, i + 1)]
        t = Vector((b[0] - a[0], b[1] - a[1])).normalized()
        nrm = Vector((-t.y, t.x))
        if nrm.y < 0 or (abs(nrm.y) < 1e-6 and nrm.x < 0):
            nrm = -nrm
        chord = te - le
        sec = []
        for k in range(12):
            u = 0.5 * (1 - math.cos(math.pi * k / 11))
            th = thick * max(0.0, 1.2 * math.sqrt(u) - 1.0 * u - 0.3 * u * u) * 1.4
            sec.append((u, th))
        ring = []
        for u, th in sec:
            off = th * 0.5 + (0.012 * math.sin(math.pi * u) if plane else 0.0)
            lift = (u - 0.4) * chord * 0.10 if plane else 0.0
            ring.append((x + nrm.x * off, y + nrm.y * off + lift, le + chord * u))
        for u, th in reversed(sec[1:-1]):
            off = -th * 0.5 + (0.004 * math.sin(math.pi * u) if plane else 0.0)
            lift = (u - 0.4) * chord * 0.10 if plane else 0.0
            ring.append((x + nrm.x * off, y + nrm.y * off + lift, le + chord * u))
        rows.append(ring)
    return rows


def wing(part, mats, bvh):
    """the factory hoop wing: a thin blade across nearly the full deck at about roof height, its ends turned up a
    little, on tall slim stays rising from the deck's outer edges (left half, mirrored)"""
    m = mats['paint']
    left = K.Part('wingL')
    # the blade, chord ~0.24 m
    plane = [(0.0, 1.250, -1.800, -2.040), (0.30, 1.249, -1.800, -2.040), (0.55, 1.250, -1.800, -2.040),
             (0.68, 1.256, -1.802, -2.038), (0.76, 1.270, -1.808, -2.032), (0.81, 1.288, -1.815, -2.024)]
    plane = K.catmull(plane, 20, closed=False)
    blade = K.Part('blade')
    vs = blade.grid(_foil_loft(plane, 0.046, True), m, closed=True)
    tip = vs[-1]
    c = blade.bm.verts.new(sum((v.co for v in tip), Vector()) / len(tip))
    tip_faces = set()
    for k in range(len(tip)):
        try:
            f = blade.bm.faces.new([tip[k], tip[(k + 1) % len(tip)], c])
            f.material_index = blade.slot(m)
            f.smooth = True
            tip_faces.add(f)
        except ValueError:
            pass
    # a stay: a slim upright blade (chord ~0.14 m), foot inside the deck, top inside the blade
    stay = [(0.672, 0.870, -1.835, -1.985), (0.669, 0.98, -1.845, -1.990), (0.665, 1.08, -1.857, -1.997),
            (0.660, 1.17, -1.868, -2.003), (0.655, 1.250, -1.878, -2.008)]
    stay = K.catmull(stay, 10, closed=False)
    st = K.Part('stay')
    st.grid(_foil_loft(stay, 0.034, False), m, closed=True)
    for pt, path, cap in ((blade, plane, True), (st, stay, False)):
        pt.bm.normal_update()
        for f in pt.bm.faces:
            g = K.G(f.calc_center_median())
            n = K.G(f.normal)
            if n.length < 1e-9:
                continue
            best = min(path, key=lambda p: (p[0] - g.x) ** 2 + (p[1] - g.y) ** 2)
            o = Vector((g.x - best[0], g.y - best[1], 0.0))
            if cap and f in tip_faces:
                o = Vector((1.0, 0.0, 0.0))
            if o.length > 1e-6 and n.dot(o) < 0:
                f.normal_flip()
        left.absorb(pt)
    part.absorb(left)
    part.absorb(left, mirror=True)


# ------------------------------------------------------------------ mirrors, wipers, handles, exhaust
def mirror(left, mats, bvh):
    m = mats['paint']
    # housing: a squashed, tapered ellipsoid, its glass on the back
    c = Vector((0.905, 0.955, 0.285))
    rows = []
    n = 10
    seg = 16
    for k in range(n + 1):
        t = k / n                           # front (t = 0) → back (t = 1)
        z = c.z + 0.085 - 0.17 * t
        prof = math.sin(math.pi * min(1.0, t * 1.15) / 2) ** 0.6 if t < 0.87 else 1.0
        rx, ry = 0.055 * prof, 0.050 * prof
        row = []
        for j in range(seg):
            a = 2 * math.pi * j / seg
            row.append((c.x + 0.012 + rx * math.cos(a) * (1.0 if math.cos(a) > 0 else 0.85), c.y + ry * math.sin(a), z))
        rows.append(row)
    p = K.Part('mirror')
    vs = p.grid(rows, m, closed=True)
    fc = p.bm.verts.new(K.B(c.x + 0.012, c.y, c.z + 0.085))
    for j in range(seg):
        f = p.bm.faces.new([vs[0][(j + 1) % seg], vs[0][j], fc])
        f.material_index = p.slot(m)
        f.smooth = True
    back = [K.G(v.co) for v in vs[-1]]
    p.face(back, mats['chrome'], smooth=False, out=(0, 0, -1))
    bmesh.ops.recalc_face_normals(p.bm, faces=p.bm.faces)
    left.absorb(p)
    # stalk to the door's sail
    left.box(mats['paint'], (0.835, 0.925, 0.30), (0.13, 0.035, 0.07), bevel=0.014, rot=Matrix.Rotation(math.radians(-18), 3, 'Z'))


def wipers(part, mats, bvh):
    for x0, x1 in ((-0.50, 0.10), (0.06, 0.58)):
        pts = []
        for k in range(9):
            x = x0 + (x1 - x0) * k / 8
            zb = 0.585 - 0.12 * (abs(x) / 0.62) ** 2.2
            p, n = K.project(bvh, (x, 1.0, zb - 0.03), (0, 1, 0.35), back=1.0)
            if p is not None:
                pts.append(p + n * 0.012)
        for a, b in zip(pts, pts[1:]):
            d = b - a
            part.box(mats['trim'], (a + b) / 2, (d.length + 0.004, 0.012, 0.022), rot=_rot_along(d))


def _rot_along(d):
    x = d.normalized()
    up = Vector((0, 1, 0))
    z = x.cross(up).normalized()
    y = z.cross(x)
    return Matrix((x, y, z)).transposed()


def sail(left, mats, bvh):
    """the black sail at the door glass's front corner (the mirror's base), filling the foot of the A-pillar"""
    d = Vector((1.0, 0.55, 0.0)).normalized()
    outline = [(0.345, 0.888), (0.300, 0.912), (0.255, 0.948), (0.232, 0.968), (0.330, 0.945), (0.440, 0.910),
               (0.530, 0.886), (0.440, 0.884)]
    pts = []
    for z, y in K.catmull(outline, 24):
        p, n = K.project(bvh, (0.75, y, z), d, back=0.6)
        if p is None:
            return
        pts.append((p, n))
    c = sum((p for p, _ in pts), Vector()) / len(pts)
    cp, cn = K.project(bvh, c, d, back=0.6)
    if cp is None:
        return
    cv = left.vert(cp + cn * 0.003)
    ring = [left.vert(p + n * 0.003) for p, n in pts]
    for k in range(len(ring)):
        f = left.face([ring[k], ring[(k + 1) % len(ring)], cv], mats['trim'])
        if f is not None:
            f.normal_update()
            if K.G(f.normal).dot(cn) < 0:
                f.normal_flip()


def scoop_slot(left, mats, bvh_cut):
    """the dark slot at the rear end of the side scoop, ahead of the rear wheel"""
    fr = Frame((0.88, 0.44, -0.50), (1, 0, 0), e1=(0, 0, -1))
    surface_patch(left, bvh_cut, K.rounded_rect(0.225, -0.008, 0.055, 0.105, 0.026, 5), fr, mats['grille'], lift=0.002,
                  n_rings=2)


def handle(left, mats, bvh):
    fr = Frame((0.86, 0.795, -0.54), (1, 0, 0), e1=(0, 0, -1))
    surface_patch(left, bvh, K.rounded_rect(0, 0, 0.20, 0.042, 0.02, 4), fr, mats['trim'], lift=0.0015, n_rings=2)
    p, n = fr.hit(bvh, 0.0, 0.004)
    oriented_box(left, mats['paint'], p + n * 0.012, n, (0, 0, -1), (0.19, 0.026, 0.016), bevel=0.007)


def exhaust(mats):
    p = K.Part('exhaust')
    c = (0.52, 0.255, -2.12)
    p.cylinder(mats['chrome'], c, 0.048, 0.20, axis='z', seg=20, cap=False)
    p.cylinder(mats['under'], (c[0], c[1], c[2] - 0.06), 0.040, 0.004, axis='z', seg=20, cap=True)
    p.cylinder(mats['chrome'], (c[0], c[1], c[2] + 0.02), 0.045, 0.16, axis='z', seg=20, cap=False)
    # the pipe's inside faces inwards
    return p


def strip3d(part, bvh, pts, d, width, mat, lift=0.0015, back=0.3):
    """a shut line through game points, each dropped onto the surface along -d"""
    hits = []
    for q in pts:
        p, n = K.project(bvh, q, d, back=back)
        hits.append((p, n))
    prev = None
    for i, (p, n) in enumerate(hits):
        if p is None:
            prev = None
            continue
        a = hits[max(0, i - 1)][0] or p
        b = hits[min(len(hits) - 1, i + 1)][0] or p
        t = (b - a).normalized()
        sd = t.cross(n).normalized() * (width / 2)
        q = (part.vert(p + sd + n * lift), part.vert(p - sd + n * lift))
        if prev is not None:
            f = part.face([prev[0], q[0], q[1], prev[1]], mat)
            if f is not None and K.G(f.normal).dot(n) < 0:
                f.normal_flip()
        prev = q


def shut_lines(part, mats, bvh):
    from supra_parts import strip
    g = mats['grille']
    w = 0.006
    for s in (1, -1):
        fr = Frame((1.3 * s, 0.6, 0.0), (s, 0, 0), e1=(0, 0, -s))
        sgn = -s

        def zz(z):
            return z * sgn
        # door: front edge, bottom, rear edge (side view, z, y)
        door = [(0.50, 0.875), (0.49, 0.80), (0.475, 0.62), (0.47, 0.45), (0.455, 0.33), (0.43, 0.30)]
        door_b = [(0.43, 0.300), (0.0, 0.296), (-0.40, 0.296), (-0.60, 0.300)]
        door_r = [(-0.60, 0.300), (-0.675, 0.40), (-0.715, 0.55), (-0.73, 0.70), (-0.715, 0.82), (-0.68, 0.90), (-0.645, 0.925)]
        for line in (door, door_b, door_r):
            dense = K.catmull(line, 22, closed=False)
            strip(part, bvh, [(zz(z), y) for z, y in dense], fr, w, g)
        if s < 0:
            # fuel lid on the right rear quarter
            lid = [(zz(z), y) for z, y in K.rounded_rect(-1.62, 0.80, 0.17, 0.115, 0.03, 4)]
            strip(part, bvh, lid + lid[:1], fr, w, g)
    # bonnet: its sides along the wing crests from the windscreen to the head lamps' outer ends, its front edge across
    # the nose between the lamps' inner ends (the lamps' own seals close the line)
    fr = Frame((0.0, 1.6, 0.0), (0, 1, 0), e1=(1, 0, 0))
    top = LAMP_TOP['pts']
    outer = max(top, key=lambda p: p.x)
    inner = min(top, key=lambda p: p.x)
    for s in (1, -1):
        crest = [(0.600, 0.66), (0.625, 1.00), (0.660, 1.32), (0.700, 1.58), (outer.x - 0.012, outer.z - 0.02)]
        strip(part, bvh, [(x * s, -z) for x, z in K.catmull(crest, 30, closed=False)], fr, w, g)
    front = []
    for k in range(25):
        x = inner.x * (-1 + 2 * k / 24)
        front.append(Vector((x, inner.y + 0.006, inner.z + 0.035 * (1 - (x / inner.x) ** 2))))
    strip3d(part, bvh, front, (0, 0.55, 1.0), w, g)
    # the bumper's seam from each lamp's outer end down to the wheel arch
    for s in (1, -1):
        seam = [Vector((outer.x - 0.005, outer.y - 0.03, outer.z - 0.01)), Vector((outer.x + 0.04, 0.60, outer.z - 0.05)),
                Vector((0.88, 0.57, 1.66)), Vector((0.89, 0.55, 1.62))]
        strip3d(part, bvh, [Vector((p[0] * s, p[1], p[2])) for p in K.catmull(seam, 12, closed=False)], (s, 0.3, 0.3), w, g)
    # hatch: along the deck's sides and down to the lamp band
    for s in (1, -1):
        side = [(0.60 * s, -1.52), (0.63 * s, -1.75), (0.64 * s, -1.98), (0.62 * s, -2.14)]
        strip(part, bvh, [(x, -z) for x, z in K.catmull(side, 16, closed=False)], fr, w, g)
    # the hatch's tail: along the top of the lamp housings and down their inner ends to the bumper's crease, which runs
    # under the lamps across the full width and round the corners to the rear wheels
    for s in (1, -1):
        edge = [(0.62, 0.950), (0.40, 0.942), (0.215, 0.935), (0.192, 0.90), (0.188, 0.80), (0.186, 0.738)]
        strip3d(part, bvh, [Vector((x * s, y, -2.0)) for x, y in K.catmull(edge, 24, closed=False)], (0, 0.15, -1), w, g,
                back=0.7)
        corner = [(0.60, 0.736, -2.0), (0.75, 0.735, -1.95), (0.84, 0.732, -1.90)]
        strip3d(part, bvh, [Vector((x * s, y, z)) for x, y, z in K.catmull(corner, 10, closed=False)],
                (0.6 * s, 0.0, -1), w, g, back=0.7)
        side = [(0.84, 0.732, -1.90), (0.88, 0.715, -1.80), (0.90, 0.695, -1.68)]
        strip3d(part, bvh, [Vector((x * s, y, z)) for x, y, z in K.catmull(side, 8, closed=False)], (s, 0.0, -0.25), w, g,
                back=0.7)
    crease = [Vector((x, 0.736, -2.0)) for x in (-0.62 + 1.24 * k / 30 for k in range(31))]
    strip3d(part, bvh, crease, (0, 0, -1), w, g, back=0.7)


# ------------------------------------------------------------------ interior (RHD)
def interior(part, mats):
    it, tr = mats['interior'], mats['trim']
    # floor, door cards below the lining, the luggage deck and its back wall
    part.face([(-0.78, 0.21, -1.0), (0.78, 0.21, -1.0), (0.78, 0.21, 0.70), (-0.78, 0.21, 0.70)], it, smooth=False, out=(0, 1, 0))
    for s in (1, -1):
        part.face([(0.80 * s, 0.21, -0.95), (0.80 * s, 0.21, 0.62), (0.80 * s, 0.55, 0.62), (0.80 * s, 0.55, -0.95)], it,
                  smooth=False, out=(-s, 0, 0))
    part.face([(-0.70, 0.66, -1.98), (0.70, 0.66, -1.98), (0.70, 0.66, -1.0), (-0.70, 0.66, -1.0)], it, smooth=False, out=(0, 1, 0))
    part.face([(-0.70, 0.66, -1.0), (0.70, 0.66, -1.0), (0.70, 0.21, -1.0), (-0.70, 0.21, -1.0)], it, smooth=False, out=(0, 0, 1))
    part.face([(-0.75, 0.42, -1.97), (0.75, 0.42, -1.97), (0.75, 0.88, -1.97), (-0.75, 0.88, -1.97)], it, smooth=False, out=(0, 0, 1))
    # dash: a rounded slab under the windscreen, the meter hood on the right (driver), centre stack
    part.box(it, (0.0, 0.765, 0.43), (1.30, 0.15, 0.32), bevel=0.05, seg=2)
    part.box(it, (-0.37, 0.86, 0.30), (0.40, 0.07, 0.18), bevel=0.03, seg=2)
    part.box(tr, (-0.37, 0.82, 0.215), (0.30, 0.07, 0.012))
    part.box(it, (0.0, 0.52, 0.30), (0.26, 0.42, 0.32), bevel=0.03, seg=1)
    part.box(it, (0.0, 0.33, -0.15), (0.22, 0.24, 0.62), bevel=0.03, seg=1)
    part.cylinder(tr, (0.0, 0.50, -0.05), 0.012, 0.12, axis='y', seg=8)
    part.cylinder(tr, (0.0, 0.57, -0.05), 0.022, 0.03, axis='y', seg=10)
    # steering wheel (right), tilted toward the driver
    sw = K.Part('sw')
    rot = Matrix.Rotation(math.radians(-22), 4, 'X')
    bm = bmesh.new()
    bmesh.ops.create_circle(bm, cap_ends=False, radius=0.185, segments=24)
    ring = [v.co.copy() for v in bm.verts]
    bm.free()
    tube = []
    for k in range(25):
        a = 2 * math.pi * k / 24
        cc = Vector((0, 0.185 * math.sin(a), 0.185 * math.cos(a)))
        rr = []
        for j in range(6):
            b = 2 * math.pi * j / 6
            rad = Vector((0, math.sin(a), math.cos(a)))
            rr.append(cc + rad * 0.016 * math.cos(b) + Vector((0.016 * math.sin(b), 0, 0)))
        tube.append(rr)
    centre = Vector((-0.37, 0.86, 0.16))
    rows = []
    for rr in tube:
        rows.append([tuple(centre + _tilt(p)) for p in rr])
    sw.grid(rows, tr, closed=True)
    for a in (math.radians(90), math.radians(270), math.radians(180)):
        p0 = centre + _tilt(Vector((0, 0.0, 0.0)))
        p1 = centre + _tilt(Vector((0, 0.18 * math.sin(a), 0.18 * math.cos(a))))
        d = p1 - p0
        sw.box(tr, (p0 + p1) / 2, (0.05, 0.016, d.length), rot=_rot_z_along(d))
    sw.cylinder(tr, tuple(centre + _tilt(Vector((0.0, 0, 0)))), 0.05, 0.05, axis='x', seg=12)
    bmesh.ops.recalc_face_normals(sw.bm, faces=sw.bm.faces)
    part.absorb(sw)
    part.cylinder(tr, tuple(centre + Vector((0, -0.03, 0.12))), 0.03, 0.22, axis='z', seg=8)
    # seats: shell buckets with bolsters and head rests; small rear seats
    for x in (-0.37, 0.37):
        part.box(it, (x, 0.33, -0.25), (0.48, 0.12, 0.50), bevel=0.04, seg=2)
        for bx in (-0.21, 0.21):
            part.box(it, (x + bx, 0.40, -0.25), (0.07, 0.08, 0.46), bevel=0.03, seg=1)
        back = Matrix.Rotation(math.radians(-16), 3, 'X')
        part.box(it, (x, 0.66, -0.56), (0.48, 0.58, 0.12), bevel=0.04, seg=2, rot=back)
        for bx in (-0.22, 0.22):
            part.box(it, (x + bx, 0.62, -0.53), (0.07, 0.42, 0.16), bevel=0.03, seg=1, rot=back)
        part.box(it, (x, 1.03, -0.66), (0.26, 0.16, 0.10), bevel=0.04, seg=2, rot=back)
        part.box(it, (x * 0.95, 0.40, -1.00), (0.44, 0.10, 0.36), bevel=0.04, seg=1)
        part.box(it, (x * 0.95, 0.62, -1.20), (0.44, 0.44, 0.10), bevel=0.04, seg=1,
                 rot=Matrix.Rotation(math.radians(-30), 3, 'X'))


def _tilt(p):
    # the wheel's plane faces the driver (−z), leaning back at the top
    v = Vector((p.z, p.y, p.x))          # ring in the x-y plane
    return Matrix.Rotation(math.radians(24), 3, 'X') @ v


def _rot_z_along(d):
    z = d.normalized()
    up = Vector((0, 0, 1)) if abs(z.z) < 0.9 else Vector((1, 0, 0))
    x = up.cross(z).normalized()
    y = z.cross(x)
    return Matrix((x, y, z)).transposed()


def build(body, mats, bvh, bvh_cut, count):
    left = K.Part('detailsL')
    red = K.Part('taillamps')
    lamps(left, red, mats, bvh, bvh_cut)
    mirror(left, mats, bvh)
    sail(left, mats, bvh)
    scoop_slot(left, mats, bvh_cut)
    handle(left, mats, bvh)
    det = K.Part('details')
    det.absorb(left)
    det.absorb(left, mirror=True)
    red_all = K.Part('taillights')
    red_all.absorb(red)
    red_all.absorb(red, mirror=True)
    # high-mount stop lamp along the top of the boot lid's tail, under the wing, in a dark surround
    fr = Frame((0.0, 0.935, -2.08), (0, 0.6, -1.0), e1=(-1, 0, 0))
    hm = K.rounded_rect(0, 0, 0.50, 0.030, 0.012, 4)
    surface_patch(det, bvh, hm, fr, mats['lamps'], lift=0.003, n_rings=2, uvbox=CELLS['stop'])
    _ring_strip(det, bvh, K.rounded_rect(0, 0, 0.52, 0.048, 0.020, 4), hm, fr, mats['trim'], lift=0.0025)
    # plates: front on the bumper above the intake (offset to the right), rear in its recess
    p, n = K.project(bvh, (0.0, 0.425, 2.0), (0, 0, 1), back=0.6)
    plate(det, mats, p + n * 0.006, n)
    p, n = K.project(bvh_cut, (0.0, 0.56, -2.1), (0, 0, -1), back=0.6)
    plate(det, mats, p + n * 0.004, n)
    # the mouth: one slim body-coloured bar across it, a little inside the opening, black mesh behind
    for y in (0.362,):
        pts = []
        for k in range(15):
            x = -0.55 + 1.10 * k / 14
            p, n = K.project(bvh, (x, y, 2.0), (0, 0, 1), back=0.6)
            if p is not None:
                pts.append(Vector((x, y, p.z - 0.035)))
        for a, b in zip(pts, pts[1:]):
            dd = b - a
            det.box(mats['paint'], (a + b) / 2, (dd.length + 0.004, 0.010, 0.018), rot=_rot_along(dd))
    wing(det, mats, bvh)
    wipers(det, mats, bvh)
    shut_lines(det, mats, bvh_cut)
    inter = K.Part('interior')
    interior(inter, mats)
    ex = exhaust(mats)
    for p in (det, red_all, inter, ex):
        count[p.name] = p.tris()
        p.build(body)
