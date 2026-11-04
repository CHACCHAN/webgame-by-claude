"""
Parts of the Supra: materials, the openings cut into the shell (glass, intakes, lamp housings, wheel wells, side
scoops), the glass, the cabin lining, lamps, wheels, wing, interior and the small details.

Measured on the reference photos (Commons; list in the scratch notes / docs/ASSETS.md): the side window outline and
the wing on the side view r13 (Falcon Photography, CC BY-SA 2.0, scaled from the 2,550 mm wheelbase, perspective
matched by camera); the bumper openings, lamps and plate on r04 / r11 / r01 (CC0, 先従隗始 / Tokumeigakarinoaoshima);
the tail lamps and wing from behind on r06 (M 93, CC BY-SA 3.0). Estimated: depths of recesses, the interior.
"""
import math
import os

import bmesh
import bpy
from mathutils import Matrix, Vector

import supra_kit as K
import supra_body as BD

TEX = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'textures', 'supra')


def _img(name):
    p = os.path.join(TEX, name)
    return bpy.data.images.load(p) if os.path.exists(p) else None


def materials():
    m = K.Mats()
    m.add('paint', '#6c6d70', metallic=0.65, roughness=0.32, coat=1.0)
    m.add('glass', '#0b1016', metallic=0.1, roughness=0.04)
    m.add('trim', '#0d0e10', metallic=0.2, roughness=0.6)
    m.add('chrome', '#d8dade', metallic=1.0, roughness=0.12)
    m.add('headlight', '#dfe6ee', metallic=0.4, roughness=0.1, image=_img('headlamp.png'), emissive='#fff4e0')
    m.add('taillight', '#4a0505', roughness=0.25, image=_img('taillamp.png'), emissive='#ff1a10')
    m.add('tire', '#151515', roughness=0.92, image=_img('tyre.png'))
    m.add('rim', '#b3b6bb', metallic=0.55, roughness=0.34)
    m.add('brake', '#2a2b2e', metallic=0.3, roughness=0.5)
    m.add('under', '#121314', roughness=0.9)
    m.add('interior', '#2b2c2f', roughness=0.85)
    m.add('lamps', '#ffffff', roughness=0.15, image=_img('lamps.png'))
    m.add('plate', '#ffffff', roughness=0.5, image=_img('plate.png'))
    m.add('disc', '#6e6c6a', metallic=0.85, roughness=0.45)
    m.add('grille', '#060607', roughness=0.7)
    # helper (never exported): faces to delete after a cut
    m.cut = bpy.data.materials.new('_cut')
    return m


# ------------------------------------------------------------------ outlines
# side window opening (door glass + quarter glass), left side, (z, y): r13 at 5 cm resolution
DLO = [(0.315, 0.900), (0.29, 0.915), (0.13, 1.040), (-0.04, 1.170), (-0.10, 1.198), (-0.22, 1.214), (-0.40, 1.222),
       (-0.58, 1.212), (-0.72, 1.186), (-0.82, 1.137), (-0.885, 1.072), (-0.915, 1.014), (-0.895, 0.968),
       (-0.80, 0.938), (-0.62, 0.915), (-0.30, 0.902), (0.05, 0.898), (0.27, 0.897)]
DIVIDER_Z = -0.615      # black divider between the door glass and the quarter glass
# windscreen (x, z) seen from above; the A-pillar edges follow the side window's front edge, a pillar's width inside
WINDSCREEN = [(0.0, 0.592), (0.36, 0.578), (0.56, 0.548), (0.640, 0.505), (0.655, 0.455), (0.600, 0.250),
              (0.545, 0.030), (0.500, -0.040), (0.30, -0.075), (0.0, -0.085)]
# rear hatch glass (x, z) from above
REAR_GLASS = [(0.0, -0.840), (0.28, -0.852), (0.42, -0.895), (0.475, -0.985), (0.480, -1.150), (0.450, -1.320),
              (0.385, -1.470), (0.270, -1.555), (0.0, -1.585)]


def _mirror_x(pts):
    return [(-p[0], *p[1:]) for p in pts]


def _full(half_xz):
    """a symmetric outline (x, z) from its left half (centre → side → centre)"""
    right = [(-x, z) for x, z in reversed(half_xz[1:-1])]
    return half_xz + right


def loft_cutter(name, outer, inner, mat):
    """a closed cutter between two loops of game points (same count), capped with fans"""
    part = K.Part(name)
    o = [part.vert(p) for p in outer]
    i = [part.vert(p) for p in inner]
    n = len(outer)
    idx = part.slot(mat)
    for k in range(n):
        j = (k + 1) % n
        f = part.bm.faces.new([o[k], o[j], i[j], i[k]])
        f.material_index = idx
    for ring in (o, i):
        c = part.bm.verts.new(sum((v.co for v in ring), Vector()) / n)
        for k in range(n):
            f = part.bm.faces.new([ring[k], ring[(k + 1) % n], c])
            f.material_index = idx
    bmesh.ops.recalc_face_normals(part.bm, faces=part.bm.faces)
    return part.build(weld=0)


def _side_x(bvh, z, y, s=1):
    p, _n = K.project(bvh, (1.4 * s, y, z), (s, 0, 0), back=0.1)
    return abs(p.x) if p is not None else 0.6


def window_outlines(bvh):
    """the side window (z, y) and, from it, the windscreen (x, z): its A-pillar edge runs a pillar's width inside the
    side window's front edge"""
    dlo = K.catmull(DLO, 120)
    front = K.catmull(DLO[:5], 14, closed=False)
    edge = []
    for k, (z, y) in enumerate(front):
        t = k / (len(front) - 1)
        xs = _side_x(bvh, z, y)
        edge.append((xs - 0.012 - 0.052 * t, z + 0.075 - 0.058 * t))
    ws = [(0.0, 0.592), (0.30, 0.580), (0.50, 0.535)] + edge + [(0.30, -0.074)]
    ws = K.catmull(_full(ws + [(0.0, -0.084)]), 120)
    return dlo, ws


def window_cutters(mats, bvh):
    cut = mats.cut
    out = []
    dlo, ws = window_outlines(bvh)
    for s in (1, -1):
        outer = [(1.4 * s, y, z) for z, y in dlo]
        inner = [((_side_x(bvh, z, y, s) - 0.07) * s, y, z) for z, y in dlo]
        out.append(loft_cutter('cut_dlo', outer, inner, cut))
    out.append(K.prism3('cut_ws', [(x, 1.6, z) for x, z in ws], (0, 1, 0), -0.68, 0.1, cut, cut))
    rg = K.catmull(_full(REAR_GLASS), 100)
    out.append(K.prism3('cut_rg', [(x, 1.6, z) for x, z in rg], (0, 1, 0), -0.62, 0.1, cut, cut))
    return out


# ------------------------------------------------------------------ surface helpers


class Frame:
    """a projection frame: centre c (game, near the surface), axes e1, e2 across, d outwards"""

    def __init__(self, c, d, e1=None):
        self.c = Vector(c)
        if e1 is None:
            self.e1, self.e2, self.d = K.frame_for(d)
        else:
            self.d = Vector(d).normalized()
            self.e1 = Vector(e1).normalized()
            self.e2 = self.d.cross(self.e1).normalized()
            self.e1 = self.e2.cross(self.d).normalized()

    def at(self, u, v, w=0.0):
        return self.c + self.e1 * u + self.e2 * v + self.d * w

    def hit(self, bvh, u, v, strict=False):
        p, n = K.project(bvh, self.at(u, v), self.d, back=1.2)
        if p is None:
            return (None, None) if strict else (self.at(u, v), self.d.copy())
        return p, n


def rings_of(outline, n_rings):
    """an outline (2-D, closed) and rings shrunk toward its centroid: list of rings, the last one a single point"""
    cx = sum(p[0] for p in outline) / len(outline)
    cy = sum(p[1] for p in outline) / len(outline)
    out = []
    for k in range(n_rings):
        f = 1 - k / n_rings
        out.append([(cx + (u - cx) * f, cy + (v - cy) * f) for u, v in outline])
    out.append([(cx, cy)])
    return out


def surface_patch(part, bvh, outline, fr, mat, lift=0.002, n_rings=4, uvbox=None, flat=0.0):
    """a patch laid on the surface inside a 2-D outline (frame fr), lifted along the normal; UVs planar in the frame,
    mapped into uvbox (u0, v0, u1, v1); flat > 0 blends the patch toward its best plane (lenses)"""
    rs = rings_of(K.ccw(outline), n_rings)
    us = [p[0] for p in outline]
    vs = [p[1] for p in outline]
    u0, u1, v0, v1 = min(us), max(us), min(vs), max(vs)
    box = uvbox or (0, 0, 1, 1)

    def uv(u, v):
        return (box[0] + (box[2] - box[0]) * (u - u0) / (u1 - u0), box[1] + (box[3] - box[1]) * (v - v0) / (v1 - v0))
    pts = []
    for ring in rs:
        row = []
        for u, v in ring:
            p, n = fr.hit(bvh, u, v)
            row.append((p + n * lift, (u, v)))
        pts.append(row)
    if flat > 0:
        c = sum((p for row in pts for p, _ in row), Vector()) / sum(len(r) for r in pts)
        for row in pts:
            for i, (p, q) in enumerate(row):
                off = (p - c).dot(fr.d)
                row[i] = (p - fr.d * off * flat + fr.d * flat * 0.0, q)
    vmap = [[part.vert(p) for p, _ in row] for row in pts]
    idx = part.slot(mat)
    n = len(outline)
    for k in range(len(pts) - 1):
        a, b = vmap[k], vmap[k + 1]
        for i in range(n):
            j = (i + 1) % n
            q = [a[i], a[j], b[j], b[i]] if len(b) > 1 else [a[i], a[j], b[0]]
            quv = [pts[k][i][1], pts[k][j][1]] + ([pts[k + 1][j][1], pts[k + 1][i][1]] if len(b) > 1 else [pts[k + 1][0][1]])
            try:
                f = part.bm.faces.new(q)
            except ValueError:
                continue
            f.material_index = idx
            f.smooth = True
            for loop, (u, v) in zip(f.loops, quv):
                loop[part.uv].uv = uv(u, v)
    return pts


def fix_normals(part, out_dir):
    """turn every face of a Part to face out_dir (game vector) on average"""
    part.bm.normal_update()
    d = K.B(*out_dir) - K.B(0, 0, 0)
    for f in part.bm.faces:
        if f.normal.dot(d) < 0:
            f.normal_flip()


def pocket(name, bvh, outline, fr, depth, wall, floor, n_rings=3):
    """a closed cutter that follows the surface: its floor is the surface inside the outline pushed in by depth"""
    part = K.Part(name)
    rs = rings_of(K.ccw(outline), n_rings)
    hits = [[fr.hit(bvh, u, v) for u, v in ring] for ring in rs]
    outer = [part.vert(p + fr.d * 0.12) for p, _ in hits[0]]
    inner = [part.vert(p - fr.d * depth) for p, _ in hits[0]]
    n = len(outline)
    wi, fi = part.slot(wall), part.slot(floor)
    for i in range(n):
        j = (i + 1) % n
        f = part.bm.faces.new([outer[i], outer[j], inner[j], inner[i]])
        f.material_index = wi
    # floor: the rings pushed in
    rows = [inner] + [[part.vert(p - fr.d * depth) for p, _ in ring] for ring in hits[1:]]
    for k in range(len(rows) - 1):
        a, b = rows[k], rows[k + 1]
        for i in range(n):
            j = (i + 1) % n
            q = [a[i], a[j], b[j], b[i]] if len(b) > 1 else [a[i], a[j], b[0]]
            try:
                f = part.bm.faces.new(q)
                f.material_index = fi
            except ValueError:
                pass
    c = part.vert(sum((p for p, _ in hits[0]), Vector()) / n + fr.d * 0.12)
    for i in range(n):
        f = part.bm.faces.new([outer[i], outer[(i + 1) % n], c])
        f.material_index = wi
    bmesh.ops.remove_doubles(part.bm, verts=part.bm.verts, dist=1e-6)
    bmesh.ops.recalc_face_normals(part.bm, faces=part.bm.faces)
    return part.build(weld=0)


def strip(part, bvh, line, fr, width, mat, lift=0.0015):
    """a thin dark line on the surface (a shut line) along a 2-D polyline in frame fr"""
    hits = [fr.hit(bvh, u, v, strict=True) for u, v in line]
    prev = None
    for i, (p, n) in enumerate(hits):
        if p is None or n.dot(fr.d) < 0.2:
            prev = None
            continue
        a = hits[max(0, i - 1)][0] or p
        b = hits[min(len(hits) - 1, i + 1)][0] or p
        t = (b - a).normalized()
        s = t.cross(n).normalized() * (width / 2)
        q = (part.vert(p + s + n * lift), part.vert(p - s + n * lift))
        if prev is not None:
            try:
                f = part.bm.faces.new([prev[0], q[0], q[1], prev[1]])
                f.material_index = part.slot(mat)
                f.smooth = True
                if K.G(f.normal).dot(n) < 0:
                    f.normal_flip()
            except ValueError:
                pass
        prev = q


def lining(shell, mats, bvh, offset=0.024):
    """the cabin lining: the windowed shell pushed in and turned inside out (door cards, pillars, headliner seen
    through the glass), and the window reveals joining it to the shell"""
    bm = bmesh.new()
    bm.from_mesh(shell.data)
    bm.normal_update()
    src = {v.index: v.co.copy() for v in bm.verts}
    nrm = {}
    for v in bm.verts:
        hit = bvh.find_nearest(v.co)
        nrm[v.index] = hit[1].normalized() if hit[0] is not None else v.normal.copy()
    reveal = K.Part('reveals')
    trim = mats['trim']
    for e in bm.edges:
        if not e.is_boundary:
            continue
        f = e.link_faces[0]
        a, b = e.verts
        # the reveal faces into the opening: away from the face's centre
        mid = (a.co + b.co) / 2
        away = mid - f.calc_center_median()
        pa, pb = src[a.index], src[b.index]
        qa, qb = pa - nrm[a.index] * offset, pb - nrm[b.index] * offset
        va, vb = reveal.bm.verts.new(pa), reveal.bm.verts.new(pb)
        wa, wb = reveal.bm.verts.new(qa), reveal.bm.verts.new(qb)
        nf = reveal.bm.faces.new([va, vb, wb, wa])
        nf.material_index = reveal.slot(trim)
        nf.smooth = True
        nf.normal_update()
        if nf.normal.dot(away) < 0:
            nf.normal_flip()
    for v in bm.verts:
        v.co = v.co - nrm[v.index] * offset

    def keep(c):
        x, y, z = abs(c.x), c.y, c.z
        if not (-1.98 < z < 0.74 and y > 0.42):
            return False
        if y < 0.78 and x > 0.45 and -1.78 < z < -0.55:
            return False
        if z > 0.5 and y < 0.84:
            return False
        return True
    dead = [f for f in bm.faces if not keep(K.G(f.calc_center_median()))]
    bmesh.ops.delete(bm, geom=dead, context='FACES')
    for f in bm.faces:
        f.normal_flip()
        f.material_index = 0
    me = bpy.data.meshes.new('lining')
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mats['interior'])
    ob = bpy.data.objects.new('lining', me)
    bpy.context.scene.collection.objects.link(ob)
    bmesh.ops.remove_doubles(reveal.bm, verts=reveal.bm.verts, dist=1e-6)
    return ob, reveal


def tail_z(x, y):
    return None


# head lamp: frame (centre, outward direction, sweep direction) on the nose's left upper corner, its recess depth
HEAD_C, HEAD_D, HEAD_E1 = (0.555, 0.60, 1.93), (0.45, 0.30, 0.84), (0.80, 0.12, -0.58)
HEAD_DEPTH = 0.048
# rear lamp housing (left): centre, outward direction, long axis (outboard)
TAIL_C, TAIL_D, TAIL_E1 = (0.50, 0.835, -2.1), (0.30, 0.30, -1.0), (1.0, 0.0, 0.30)


def headlamp_outline():
    """the late-model head lamp unit, a long teardrop set into the wing top (u inboard → outboard and back, v up),
    metres: full and round inboard, tapering as it sweeps back along the wing, the top edge nearly straight"""
    ctrl = [(-0.320, -0.010), (-0.305, 0.050), (-0.255, 0.088), (-0.170, 0.100), (-0.050, 0.098), (0.080, 0.090),
            (0.200, 0.075), (0.280, 0.055), (0.318, 0.025), (0.322, -0.005), (0.300, -0.030), (0.230, -0.045),
            (0.120, -0.062), (0.000, -0.080), (-0.130, -0.095), (-0.240, -0.092), (-0.300, -0.060)]
    return K.catmull(ctrl, 56)


def headlamp_frame(bvh):
    p, _n = K.project(bvh, HEAD_C, HEAD_D, back=0.6)
    return Frame(p, HEAD_D, e1=HEAD_E1)


def _mirrored(ob):
    """the cutter mirrored to the right-hand side (game x = Blender x)"""
    from mathutils import Matrix
    ob.data.transform(Matrix.Scale(-1.0, 4, (1.0, 0.0, 0.0)))
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.reverse_faces(bm, faces=bm.faces)
    bm.to_mesh(ob.data)
    bm.free()
    return ob


def pocket_cutters(mats, bvh):
    """recesses: wheel wells, bumper openings, the rear lamp band, the plate recesses, the side scoops"""
    out = []
    under, trim, grille, paint = mats['under'], mats['trim'], mats['grille'], mats['paint']
    for s in (1, -1):
        for zc, r, xin in ((BD.AXLE, 0.352, 0.50), (-BD.AXLE, 0.358, 0.52)):
            circ = [(1.4 * s, 0.33 + r * math.sin(a), zc + r * math.cos(a)) for a in
                    (2 * math.pi * k / 64 for k in range(64))]
            out.append(K.prism3('cut_arch', circ, (s, 0, 0), -(1.4 - xin), 0.1, under, under))
        # bumper corner opening (late model): a rounded black duct under the indicator, outboard of the mouth
        fr = Frame((0.715 * s, 0.355, 1.95), (0.60 * s, 0.0, 1.0))
        out.append(pocket('cut_corner', bvh, K.rounded_rect(0.0, 0.0, 0.130, 0.105, 0.045, 6), fr, 0.07, trim, grille))
        # side scoop: a recess sweeping back along the foot of the door into the slot ahead of the rear wheel
        fr = Frame((0.88 * s, 0.44, -0.50), (s, 0, 0), e1=(0, 0, -1))
        out.append(pocket('cut_scoop', bvh, K.catmull(SCOOP, 48), fr, 0.03, paint, paint, n_rings=4))
        # rear lamp housing: a shallow black recess round the four lenses, wrapping round the corner
        fr = Frame((TAIL_C[0] * s, TAIL_C[1], TAIL_C[2]), (TAIL_D[0] * s, TAIL_D[1], TAIL_D[2]),
                   e1=(TAIL_E1[0] * s, TAIL_E1[1], TAIL_E1[2] * s))
        out.append(pocket('cut_lamps', bvh, K.rounded_rect(0.0, 0.0, 0.64, 0.170, 0.078, 6), fr, 0.014, trim, trim))
    # the head lamp recesses
    fr = headlamp_frame(bvh)
    out.append(pocket('cut_head', bvh, headlamp_outline(), fr, HEAD_DEPTH, mats['rim'], mats['chrome'], n_rings=4))
    out.append(_mirrored(pocket('cut_head', bvh, headlamp_outline(), fr, HEAD_DEPTH, mats['rim'], mats['chrome'],
                                n_rings=4)))
    # the mouth: a wide black intake across the bumper, the plate over its upper edge, a body-coloured band under it
    fr = Frame((0.0, 0.357, 2.1), (0, 0, 1))
    out.append(pocket('cut_intake', bvh, K.rounded_rect(0.0, 0.0, 1.18, 0.135, 0.05, 6), fr, 0.09, trim, grille, n_rings=4))
    # rear plate recess
    fr = Frame((0.0, 0.56, -2.25), (0, 0, -1), e1=(-1, 0, 0))
    out.append(pocket('cut_plate_r', bvh, K.rounded_rect(0.0, 0.0, 0.40, 0.205, 0.025, 4), fr, 0.025, paint, paint))
    return out


# the side scoop's outline (u back along the body from z = -0.50, v up from y = 0.44), from the side photo
SCOOP = [(-0.06, 0.004), (0.0, 0.022), (0.10, 0.048), (0.20, 0.060), (0.255, 0.045), (0.272, 0.0), (0.26, -0.05),
         (0.22, -0.072), (0.14, -0.066), (0.04, -0.042), (-0.03, -0.018)]


def _round_ends(outline):
    return K.catmull(outline[::3], 90)


def body_shell(body, mats, count):
    shell = BD.shell('shell', mats).build(body, weld=0)
    whole = shell.copy()
    whole.data = shell.data.copy()
    bpy.context.scene.collection.objects.link(whole)
    bvh = K.bvh_of(whole)
    ref = shell.copy()
    ref.data = shell.data.copy()
    K.boolean(shell, pocket_cutters(mats, bvh))
    # windows: holes in the shell; the same pieces of the uncut shell become the glass
    K.boolean(shell, window_cutters(mats, bvh))
    K.delete_faces(shell, lambda m, c, n: m == '_cut')
    glass = whole
    K.boolean(glass, window_cutters(mats, bvh), op='INTERSECT')
    K.delete_faces(glass, lambda m, c, n: m == '_cut')
    glass.name = 'glass'
    glass.data.materials.clear()
    glass.data.materials.append(mats['glass'])
    for p in glass.data.polygons:
        p.material_index = 0
        p.use_smooth = True
    glass.parent = body
    lin, reveal = lining(shell, mats, bvh)
    lin.parent = body
    rv = reveal.build(body, weld=0)
    surface_normals(shell, ref)
    me = ref.data
    bpy.data.objects.remove(ref)
    bpy.data.meshes.remove(me)
    for ob in (shell, glass, lin, rv):
        K.drop_unused_slots(ob)
        count[ob.name] = K.obj_tris(ob)
    return shell, glass, bvh


def surface_normals(ob, ref, tol=0.0015):
    """paint faces still lying on the designed surface take its smooth normals (interpolated from the uncut shell), so
    the cuts' slivers next to arches, openings and windows shade like the panel round them"""
    from mathutils.bvhtree import BVHTree
    from mathutils.interpolate import poly_3d_calc
    me = ref.data
    me.calc_loop_triangles()
    co = [v.co.copy() for v in me.vertices]
    vn = [v.normal.copy() for v in me.vertices]
    tris = [tuple(t.vertices) for t in me.loop_triangles]
    tree = BVHTree.FromPolygons(co, tris)
    m = ob.data
    keep = {i for i, mt in enumerate(m.materials) if mt is not None and mt.name in ('paint', 'trim', 'under')}

    def smooth_n(p):
        hit = tree.find_nearest(p)
        if hit[0] is None or hit[3] > tol:
            return None
        a, b, c = tris[hit[2]]
        w = poly_3d_calc([co[a], co[b], co[c]], hit[0])
        return (vn[a] * w[0] + vn[b] * w[1] + vn[c] * w[2]).normalized()
    out = [(0.0, 0.0, 0.0)] * len(m.loops)
    done = 0
    for poly in m.polygons:
        if poly.material_index not in keep or not poly.use_smooth or smooth_n(poly.center) is None:
            continue
        for li in poly.loop_indices:
            n = smooth_n(m.vertices[m.loops[li].vertex_index].co)
            if n is not None:
                out[li] = tuple(n)
                done += 1
    m.normals_split_custom_set(out)
    print('NORMALS', done, 'of', len(m.loops))


def build_all(root, mats):
    count = {}
    body = K.empty('body', root)
    shell, glass, bvh = body_shell(body, mats, count)
    import supra_details as DT
    DT.build(body, mats, bvh, K.bvh_of(shell), count)
    wheels(root, mats, count)
    return count


# ------------------------------------------------------------------ wheels
# late-model RZ: 17 × 8JJ / 17 × 9JJ five-spoke alloys, 235/45ZR17 / 255/40ZR17; rotors Ø323 / Ø324 mm
TYRE_W = {'f': 0.235, 'r': 0.255}
RIM_W = {'f': 0.203, 'r': 0.229}
RIM_R = 0.2159          # 17" bead seat
TYRE_R = 0.3225         # 235/45R17: Ø645 mm (the wheel centre stays at WHEEL_Y)
SEG = 40


def _lathe(part, prof, mat, seg=SEG, uv_v=None, u_rep=1.0, cap=False):
    """revolve a (x, r) profile round the game x axis; faces outwards when the profile runs with the material on its
    right-hand side"""
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


def tyre(part, mats, w):
    h = w / 2
    r0, R = RIM_R + 0.004, TYRE_R
    # inner bead → inner sidewall → tread (three grooves) → outer sidewall → outer bead
    prof = [(-h + 0.012, r0), (-h - 0.002, r0 + 0.03), (-h - 0.006, r0 + 0.07), (-h - 0.002, R - 0.022),
            (-h + 0.012, R - 0.004), (-h + 0.03, R)]
    g = [-0.25 * w, 0.0, 0.25 * w]
    for gx in g:
        prof += [(gx - 0.007, R), (gx - 0.006, R - 0.007), (gx + 0.006, R - 0.007), (gx + 0.007, R)]
    prof += [(h - 0.03, R), (h - 0.012, R - 0.004), (h + 0.002, R - 0.022), (h + 0.006, r0 + 0.07), (h + 0.002, r0 + 0.03),
             (h - 0.012, r0)]
    # v: arc-length fraction (texture rows: sidewall 0-0.3, tread 0.36-0.64, sidewall 0.7-1)
    L = [0.0]
    for i in range(1, len(prof)):
        L.append(L[-1] + math.dist(prof[i], prof[i - 1]))
    side = L[5]
    vv = []
    for i, l in enumerate(L):
        if l <= side:
            v = 0.3 * l / side
        elif l >= L[-1] - side:
            v = 0.7 + 0.3 * (l - (L[-1] - side)) / side
        else:
            v = 0.3 + 0.4 * (l - side) / (L[-1] - 2 * side)
        vv.append(v)
    _lathe(part, prof, mats['tire'], uv_v=vv, u_rep=12.0)
    fix_out(part)


def fix_out(part):
    """lathe faces: point away from the wheel's axis/centre"""
    part.bm.normal_update()
    for f in part.bm.faces:
        c = f.calc_center_median()
        g = K.G(c)
        radial = Vector((0, g.y, g.z))
        n = K.G(f.normal)
        if radial.length > 1e-6 and abs(n.normalized().dot(radial.normalized())) > 0.3:
            if n.dot(radial) < 0:
                f.normal_flip()
        elif n.x * g.x < 0:
            f.normal_flip()


def rim(part, mats, w):
    """the five-spoke wheel, its outer face toward +x"""
    m = mats['rim']
    xo = w / 2 + 0.012          # outer lip face
    # lip and barrel, seen from outside and through the spokes (the barrel's inner face points at the axle)
    lip = K.Part('lip')
    _lathe(lip, [(xo - 0.022, RIM_R + 0.004), (xo - 0.004, RIM_R + 0.019), (xo, RIM_R + 0.017), (xo + 0.003, RIM_R + 0.008),
                 (xo + 0.003, RIM_R - 0.006), (xo - 0.004, RIM_R - 0.014), (xo - 0.03, RIM_R - 0.018)], m)
    fix_out(lip)
    part.merge(_bm(lip), m)
    barrel = K.Part('barrel')
    _lathe(barrel, [(xo - 0.03, RIM_R - 0.018), (-w / 2, RIM_R - 0.022)], m)
    barrel.bm.normal_update()
    for f in barrel.bm.faces:          # toward the axis
        g = K.G(f.calc_center_median())
        if K.G(f.normal).dot(Vector((0, g.y, g.z))) > 0:
            f.normal_flip()
    part.merge(_bm(barrel), m)
    # spokes: five wide, nearly flat spokes, swept a little, widening into the rim so the windows end round
    for i in range(5):
        a0 = 2 * math.pi * i / 5
        sp = K.Part('spoke')
        rows = []
        n = 8
        for k in range(n + 1):
            t = k / n
            r = 0.066 + (RIM_R - 0.008 - 0.066) * t
            half = 0.033 + 0.006 * t + 0.056 * max(0.0, (t - 0.66) / 0.34) ** 2
            face = xo - 0.010 + 0.006 * t                  # a nearly flat face, flush with the lip
            a = a0 + 0.10 * t                              # the sweep
            ring = [(face - 0.030, -half), (face - 0.002, -half), (face, -half * 0.85), (face, 0.0),
                    (face, half * 0.85), (face - 0.002, half), (face - 0.030, half)]
            row = []
            for x, sd in ring:
                yy = r * math.sin(a) + sd * math.cos(a)
                zz = r * math.cos(a) - sd * math.sin(a)
                row.append((x, yy, zz))
            rows.append(row)
        sp.grid(rows, m, smooth=True)
        _orient(sp, Vector((1, 0, 0)))
        part.merge(_bm(sp), m)
    # the big flat centre cap over the hub (no badge)
    hub = K.Part('hub')
    _lathe(hub, [(xo - 0.050, 0.074), (xo - 0.014, 0.074), (xo - 0.009, 0.070), (xo - 0.008, 0.060), (xo - 0.008, 0.0)],
           m, seg=32)
    fix_out(hub)
    part.merge(_bm(hub), m)


def _bm(part):
    """a Part's bmesh, handed over (for merging)"""
    bm = part.bm
    part.bm = bmesh.new()
    return bm


def _orient(part, out):
    part.bm.normal_update()
    o = K.B(*out) - K.B(0, 0, 0)
    for f in part.bm.faces:
        if f.normal.dot(o) < -0.2:
            f.normal_flip()


def brake(part_spin, part_cal, mats, w, front):
    xo = w / 2 + 0.012
    xd = xo - 0.125
    # rotor ring and hat
    _lathe(part_spin, [(xd - 0.015, 0.16), (xd + 0.015, 0.16)], mats['disc'], seg=36)
    ring = K.Part('ring')
    _lathe(ring, [(xd + 0.015, 0.16), (xd + 0.015, 0.09), (xd + 0.045, 0.085), (xd + 0.045, 0.0)], mats['disc'], seg=36)
    _orient(ring, Vector((1, 0, 0)))
    part_spin.merge(_bm(ring), mats['disc'])
    # caliper behind the axle (4-pot front, 2-pot rear), straddling the rotor's edge
    ang0, ang1 = (math.radians(100), math.radians(160)) if front else (math.radians(105), math.radians(150))
    cal = K.Part('cal')
    rows = []
    n = 6
    for k in range(n + 1):
        a = ang0 + (ang1 - ang0) * k / n
        sec = [(xd - 0.045, 0.115), (xd + 0.045, 0.115), (xd + 0.05, 0.150), (xd + 0.045, 0.178), (xd - 0.045, 0.178),
               (xd - 0.05, 0.150)]
        rows.append([(x, r * math.sin(a), r * math.cos(a)) for x, r in sec])
    cal.grid(rows, mats['brake'], closed=True, smooth=False)
    for row in (rows[0], rows[-1]):
        cal.face(row, mats['brake'], smooth=False)
    bmesh.ops.recalc_face_normals(cal.bm, faces=cal.bm.faces)
    part_cal.merge(_bm(cal), mats['brake'])


def wheels(root, mats, count):
    total = 0
    for key, z, track, axle in (('fl', BD.AXLE, BD.TRACK_F, 'f'), ('fr', BD.AXLE, BD.TRACK_F, 'f'),
                                ('rl', -BD.AXLE, BD.TRACK_R, 'r'), ('rr', -BD.AXLE, BD.TRACK_R, 'r')):
        s = 1 if key[1] == 'l' else -1
        pivot = K.empty(f'wheel_{key}', root, loc=(s * track / 2, BD.WHEEL_Y, z))
        spin = K.empty(f'spin_{key}', pivot)
        ps = K.Part(f'wheel_{key}_spin')
        tyre(ps, mats, TYRE_W[axle])
        rim(ps, mats, RIM_W[axle])
        pc = K.Part(f'caliper_{key}')
        brake(ps, pc, mats, RIM_W[axle], axle == 'f')
        if s < 0:
            for p in (ps, pc):
                bmesh.ops.scale(p.bm, vec=(-1, 1, 1), verts=p.bm.verts)
                for f in p.bm.faces:
                    f.normal_flip()
        total += ps.tris() + pc.tris()
        ps.build(spin)
        pc.build(pivot)
    count['wheels'] = total
