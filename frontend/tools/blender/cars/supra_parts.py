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
    # metal reads as metal (owner, 2026-11-10): chrome, the alloy wheels, the discs fully metallic
    m.add('chrome', '#d8dade', metallic=1.0, roughness=0.08)
    m.add('headlight', '#dfe6ee', metallic=0.4, roughness=0.1, image=_img('headlamp.png'), emissive='#fff4e0')
    m.add('taillight', '#4a0505', roughness=0.25, image=_img('taillamp.png'), emissive='#ff1a10')
    m.add('rim', '#b8bbc0', metallic=1.0, roughness=0.26)
    m.add('brake', '#2a2b2e', metallic=0.3, roughness=0.5)
    m.add('under', '#121314', roughness=0.9)
    m.add('interior', '#2b2c2f', roughness=0.85)
    # the small lenses (indicators, reverse, amber, markers): coloured or clear lenses over chrome reflectors
    m.add('lamps', '#ffffff', metallic=0.5, roughness=0.15, image=_img('lamps.png'))
    m.add('plate', '#ffffff', roughness=0.5, image=_img('plate.png'))
    m.add('disc', '#8a8886', metallic=1.0, roughness=0.36)
    m.add('grille', '#060607', roughness=0.7)
    # the head lamps' housing under the clear cover: dark grey, a little sheen (n07, n14)
    m.add('housing', '#62666c', metallic=0.5, roughness=0.32)
    # helper (never exported): faces to delete after a cut
    m.cut = bpy.data.materials.new('_cut')
    import car_common as CC
    for name in ('c_dash', 'c_plastic', 'c_carpet'):        # the cabin's swatches (car_common)
        CC.material_for(m.mats, name)
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
# (the bubble hatch reaches down to the deck: its lower corners at (±0.385, 0.93, -1.78), triangulated on n01, n06, n15)
# (2026-11-10: wider at its lower corners, rays from n15 / n06 onto the body: far corner (0.45, 0.92, -1.79), the lower
# edge at z -1.84 near the centre line)
REAR_GLASS = [(0.0, -0.840), (0.28, -0.852), (0.42, -0.895), (0.475, -0.985), (0.488, -1.150), (0.488, -1.360),
              (0.478, -1.560), (0.462, -1.700), (0.432, -1.785), (0.320, -1.825), (0.150, -1.845), (0.0, -1.850)]


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
    # down to y 0.84: the glass's lower edge lies on the deck at y ~0.93 (a shallower prism left it short at y 0.98)
    out.append(K.prism3('cut_rg', [(x, 1.6, z) for x, z in rg], (0, 1, 0), -0.76, 0.1, cut, cut))
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


def pocket(name, bvh, outline, fr, depth, wall, floor, n_rings=3, cap=None):
    """a closed cutter that follows the surface: its floor is the surface inside the outline pushed in by depth (with
    cap: never higher than that height along fr.d, so parts set in the recess are not cut by a rising floor)"""
    part = K.Part(name)
    rs = rings_of(K.ccw(outline), n_rings)
    hits = [[fr.hit(bvh, u, v) for u, v in ring] for ring in rs]

    def down(p):
        q = p - fr.d * depth
        if cap is not None and q.dot(fr.d) > cap:
            q = q - fr.d * (q.dot(fr.d) - cap)
        return q
    outer = [part.vert(p + fr.d * 0.12) for p, _ in hits[0]]
    inner = [part.vert(down(p)) for p, _ in hits[0]]
    n = len(outline)
    wi, fi = part.slot(wall), part.slot(floor)
    for i in range(n):
        j = (i + 1) % n
        f = part.bm.faces.new([outer[i], outer[j], inner[j], inner[i]])
        f.material_index = wi
    # floor: the rings pushed in
    rows = [inner] + [[part.vert(down(p)) for p, _ in ring] for ring in hits[1:]]
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


def pocket_rect(name, bvh, fr, cu, cv, w, h, r, depth, wall, floor, cols=56, rows=4):
    """a rounded-rectangle recess (centre cu, cv in frame fr) whose floor is the surface pushed in by depth, laid as a
    grid of columns: a wide recess in a panel curved in plan shades evenly across (pocket's rings shrunk toward the
    centre leave diagonal facets from its corners)"""
    part = K.Part(name)
    a = w / 2 - r

    def span(u):
        e = max(0.0, abs(u - cu) - a)
        dv = r - math.sqrt(max(0.0, r * r - e * e))
        return cv - h / 2 + dv, cv + h / 2 - dv
    us = [cu + (w / 2) * math.sin(math.pi * (k / cols - 0.5)) for k in range(cols + 1)]
    pts, grid = [], []
    for u in us:
        v0, v1 = span(u)
        pts.append([fr.hit(bvh, u, v0 + (v1 - v0) * j / rows)[0] - fr.d * depth for j in range(rows + 1)])
        grid.append([part.vert(p) for p in pts[-1]])
    fi, wi = part.slot(floor), part.slot(wall)
    for i in range(cols):
        for j in range(rows):
            f = part.bm.faces.new([grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]])
            f.material_index = fi
            f.smooth = True
    ring = ([(us[i], i, 0) for i in range(cols + 1)] + [(us[cols], cols, j) for j in range(1, rows)] +
            [(us[i], i, rows) for i in range(cols, -1, -1)] + [(us[0], 0, j) for j in range(rows - 1, 0, -1)])
    inner = [grid[i][j] for _u, i, j in ring]
    rim = [pts[i][j] + fr.d * (depth + 0.12) for _u, i, j in ring]     # straight out along d: walls square to the frame
    outer = [part.vert(p) for p in rim]
    n = len(ring)
    for k in range(n):
        m = (k + 1) % n
        f = part.bm.faces.new([outer[k], outer[m], inner[m], inner[k]])
        f.material_index = wi
    c = part.vert(sum(rim, Vector()) / n)
    for k in range(n):
        f = part.bm.faces.new([outer[k], outer[(k + 1) % n], c])
        f.material_index = wi
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


# head lamp: frame (centre, outward direction, along the lens row) on the nose's left upper corner, its recess depth.
# Measured on n07 (rays onto the fitted body, pre-field frame): the unit's ends at (0.278, 0.570, 2.070) inboard and
# (0.662, 0.617, 1.819) outboard (0.46 m), its three elements level in a row along HEAD_E1, centres 0.124 / 0.106 apart
HEAD_C, HEAD_D, HEAD_E1 = (0.47, 0.60, 1.94), (0.45, 0.30, 0.84), (0.86, 0.03, -0.51)
HEAD_DEPTH = 0.042
# rear lamp housing (left): centre, outward direction, long axis (outboard)
# (lens centres triangulated on n03, n05, n06, n15: inner (0.267, 0.772, -2.14), outer (0.595, 0.765, -2.06))
# (2026-11-10: lenses 2 cm lower: n05 / n06 / n15 / n03 rays put their centres at y 0.757 .. 0.772 after the projection
# along TAIL_D, which lifts them ~1.5 cm)
# (2026-11-10: the traced units carried back onto the body rise outboard: 0.03 rad more (n05, square on) .. 0.07 (n06,
# n15): 0.04. Note the frame's v points down on this side)
TAIL_C, TAIL_D, TAIL_E1 = (0.431, 0.750, -2.10), (0.30, 0.30, -1.0), (0.971, 0.02, 0.237)


# the lamps' and openings' outlines as laid on the uncut shell (left side), for the photo check
# (fitdata/supra/tools/lamps.py): key -> ('surf', frame, 2-D outline) | ('disc', centre, normal, radius); keys ending
# in '_C' sit on the centre line (not mirrored)
OUTLINES = {}


# the head lamp unit's outline (outer edge of its black seal; u inboard -> outboard along the lens row, v up), metres:
# a teardrop eye: the top edge long and nearly straight under the bonnet line, the inboard end a blunt point low down
# (the top edge falling to it in a long slope), the outboard end tall and round where it wraps the corner, the bottom
# edge straight (2026-11-10: the traced seal on n07 (near lamp) and n14 (near lamp, its camera's offset taken out by
# the lens centres) carried back onto the body: fitdata/supra/tools/lamps.py back)
HEAD_RIM = [(-0.234, -0.040), (-0.229, -0.012), (-0.212, 0.020), (-0.190, 0.052), (-0.163, 0.082), (-0.135, 0.100),
            (-0.095, 0.109), (-0.030, 0.111), (0.050, 0.107), (0.130, 0.100), (0.180, 0.091), (0.208, 0.077),
            (0.225, 0.052), (0.233, 0.020), (0.234, -0.015), (0.228, -0.046), (0.214, -0.068), (0.190, -0.078),
            (0.130, -0.082), (0.050, -0.083), (-0.040, -0.080), (-0.130, -0.074), (-0.195, -0.068), (-0.222, -0.060)]


def headlamp_outline():
    """the recess inside the seal (supra_details lays the seal from it: u * 1.012 +- 0.003, v * 1.03 +- 0.003)"""
    ctrl = [((u - (0.003 if u > 0 else -0.003)) / 1.012, (v - (0.003 if v > 0 else -0.003)) / 1.03) for u, v in HEAD_RIM]
    return K.catmull(ctrl, 72)


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
        # bumper corner duct (late model): a scoop under the indicator, its lower edge sweeping down inboard toward the
        # mouth (n07: x 0.43 .. 0.66, y 0.30 .. 0.42); body-coloured walls, a dark opening at its back
        fr = Frame((0.555 * s, 0.360, 1.99), (0.50 * s, 0.0, 1.0), e1=(1.0, 0, -0.5 * s))   # e1 inboard on the right: u * s
        out.append(pocket('cut_corner', bvh, K.catmull([(u * s, v) for u, v in CORNER_DUCT], 40), fr, 0.055, paint, grille))
        if s == 1:
            OUTLINES['duct'] = ('surf', fr, K.catmull(CORNER_DUCT, 40))
        # side scoop: a recess sweeping back along the foot of the door into the slot ahead of the rear wheel
        fr = Frame((0.88 * s, 0.44, -0.50), (s, 0, 0), e1=(0, 0, -s))     # v up on both sides, u back as u * s
        out.append(pocket('cut_scoop', bvh, K.catmull([(u * s, v) for u, v in SCOOP], 48), fr, 0.03, paint, paint,
                          n_rings=4))
    # the head lamp recesses: the floor follows the curved wing top but stays below the reflector bowls' rims (set
    # square to the lamp's axis in supra_details), so no bowl is cut into a C by a rising floor
    fr = headlamp_frame(bvh)
    from supra_details import HEAD_LENSES
    cap = min(fr.hit(bvh, u, v)[0].dot(fr.d) for (u, v, _r), _px in HEAD_LENSES) - HEAD_DEPTH
    for mirror in (False, True):
        pk = pocket('cut_head', bvh, headlamp_outline(), fr, HEAD_DEPTH, mats['housing'], mats['housing'], n_rings=6,
                    cap=cap)
        out.append(_mirrored(pk) if mirror else pk)
    # the mouth: a wide black intake across the bumper (n07, n14: x +-0.395, y 0.30 .. 0.435), the plate over its upper
    # edge (2026-11-10: the n07 outline carried back onto the body: 0.79 x 0.135, its centre 3 mm lower)
    fr = Frame((0.0, 0.372, 2.1), (0, 0, 1))
    mouth = K.rounded_rect(0.0, -0.003, 0.79, 0.135, 0.045, 6)
    out.append(pocket('cut_intake', bvh, mouth, fr, 0.09, trim, grille, n_rings=4))
    OUTLINES['mouth_C'] = ('surf', fr, mouth)
    # rear plate recess: a wide shallow panel round the plate, its top edge a crisp horizontal crease
    # (2026-11-10: n05, n06 traced and carried onto the bumper: 0.70 x 0.19, centre 0.565)
    fr = Frame((0.0, 0.56, -2.25), (0, 0, -1), e1=(-1, 0, 0))
    out.append(pocket_rect('cut_plate_r', bvh, fr, 0.0, 0.005, 0.70, 0.19, 0.03, 0.022, paint, paint))
    return out


# the side scoop's outline (u back along the body from z = -0.50, v up from y = 0.44), from the side photo
SCOOP = [(-0.06, 0.004), (0.0, 0.022), (0.10, 0.048), (0.20, 0.060), (0.255, 0.045), (0.272, 0.0), (0.26, -0.05),
         (0.22, -0.072), (0.14, -0.066), (0.04, -0.042), (-0.03, -0.018)]


# the corner opening's outline (u outboard, v up, about (0.555, 0.36)): the indicator sits in its top (supra_details),
# the outboard side falls in a round curve to the bottom, the inboard side straight down from the indicator's end
# (2026-11-10: the n07 and n14 outlines carried back onto the body; n14 sees the inboard bottom as surface, n07 as
# opening: between them)
CORNER_DUCT = [(-0.088, 0.123), (-0.040, 0.125), (0.020, 0.126), (0.080, 0.124), (0.100, 0.119), (0.108, 0.105),
               (0.110, 0.080), (0.106, 0.050), (0.098, 0.025), (0.084, 0.000), (0.065, -0.020), (0.035, -0.033),
               (0.000, -0.038), (-0.035, -0.036), (-0.065, -0.025), (-0.085, -0.005), (-0.096, 0.025),
               (-0.100, 0.060), (-0.100, 0.095), (-0.096, 0.115)]


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


# the body is laid out 4.48 m long (ZN); everything ahead of the front arches is stretched to the published 4,520 (the
# photos' front overhang is the longer one: n01, n06, n07)
NOSE_EXT = 0.04
NOSE_Z0 = 1.65


def nose_disp(G):
    """the nose stretch as a displacement of game points (N, 3)"""
    import numpy as np
    a = 0.15
    t = np.clip((G[:, 2] - NOSE_Z0) / (BD.ZN - NOSE_Z0), 0.0, None)
    s = np.where(t < a, t * t / (2 * a), t - a / 2) / (1 - a / 2)    # a soft start, then a uniform stretch
    D = np.zeros_like(G)
    D[:, 2] = NOSE_EXT * s
    return D


def stretch_nose(body):
    import supra_ffd as FF
    FF.deform_body(body, nose_disp)


def build_all(root, mats, ffd=True):
    """ffd: True = the fitted field in fitdata/supra/ffd.json (when present), False = none, or a Lattice"""
    count = {}
    body = K.empty('body', root)
    shell, glass, bvh = body_shell(body, mats, count)
    import supra_details as DT
    DT.build(body, mats, bvh, K.bvh_of(shell), count)
    if NOSE_EXT:
        stretch_nose(body)
    if ffd is not False:
        import supra_ffd as FF
        FF.apply_to_body(body, None if ffd is True else ffd)
    DT.build_wing(body, mats, shell, count)
    wheels(root, mats, count)
    finish(root, body, mats, count)
    return count


# ------------------------------------------------------------------ wheels
# late-model RZ: 17 × 8JJ / 17 × 9JJ five-spoke alloys, 235/45ZR17 / 255/40ZR17; rotors Ø323 / Ø324 mm
TYRE_W = {'f': 0.235, 'r': 0.255}
RIM_W = {'f': 0.203, 'r': 0.229}
RIM_R = 0.2159          # 17" bead seat
TYRE_R = 0.3216         # 235/45R17: Ø643 mm (the wheel centre at WHEEL_Y, slightly loaded)
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


def wheels(root, mats, count):
    """four pivots with spin children. Tyre, disc and caliper come from the shared kit (car_common: profiled tyres
    with their own texture set, Ø323 vented discs, black fixed calipers behind the axle as before); the five-spoke
    rim is this car's own"""
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
        # the bead lies under the rim's lip (its crest at RIM_R + 0.019 stays proud of the sidewall's foot)
        got = CC.tyre(t, TYRE_R, RIM_R + 0.002, TYRE_W[axle], RIM_W[axle] - 0.006, grooves=4)
        info = info or got
        x_face = RIM_W[axle] / 2 + 0.012 - 0.125 + 0.015          # the old rotor's outer face
        thick = 0.030 if axle == 'f' else 0.018
        CC.brake_disc(t, 0.1615, x_face, thick=thick, r_hat=0.086, hat=0.030, vented=True)
        c = HK.Mesh(f'caliper_{key}')
        CC.caliper(c, 0.1615, x_face, thick=thick, kind='4pot', angle=-40.0, colour='cal_black')
        if s < 0:
            bmesh.ops.scale(ps.bm, vec=(-1, 1, 1), verts=ps.bm.verts)
            for f in ps.bm.faces:
                f.normal_flip()
            t, c = CC.turned(t), c.mirrored()
        total += ps.tris() + t.tris() + c.tris()
        ps.build(spin)
        made += [(t, spin), (c, pivot)]
    mats.mats['tire'] = CC.tyre_material(info, 'NOCTURNE', '235/45ZR17 94W')
    for mesh, parent in made:
        CC.build(mesh, parent, mats.mats)
    count['wheels'] = total


def finish(root, body, mats, count):
    """after the body's last deformation (car_common): the underside (a front engine driving the rear wheels on
    arms, the big silencer across the car behind the axle, its tailpipe on the left; the tank ahead of the axle), the plain materials and the small lamps' picture into two
    painted atlases, every corner's share of the sky"""
    import car_common as CC
    import hayate_kit as HK
    CC.underseal([o for o in body.children_recursive if o.type == 'MESH'], mats.mats)
    ub = HK.Mesh('underbody')
    CC.underbody(ub, 0.232, BD.AXLE, -BD.AXLE, BD.TRACK_F, BD.TRACK_R, BD.WHEEL_Y, tip=(0.52, 0.255, -2.02),
                 layout='FR', axle='irs', silencer='across')
    count['underbody'] = ub.tris()
    CC.build(ub, body, mats.mats)
    trim = CC.Atlas('trim')
    rim_atlas = CC.Atlas('rim', size=512, fill=('#8a8c8f', 0.32, 0.85))
    rim_atlas.region('disc', CC.disc_image(), 0.38, 0.85)
    made = CC.consolidate(root, trim, rim_atlas, own=('tire', 'plate'))
    tyres = [o for o in root.children_recursive
             if o.type == 'MESH' and any(mm and mm.name == 'tire' for mm in o.data.materials)]
    CC.bake_ao(root, made + tyres)
