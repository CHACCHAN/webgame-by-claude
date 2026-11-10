"""
Details of the U9 on the shell: mirrors, lamps, the black bumper sections, splitter, diffuser, the Xtreme's wing,
emblems.

Measured on the Commons photos (fitdata/u9/ref/list.json) with the solved cameras (fitdata/u9/fit/): outlines traced on
the photos (fitdata/u9/traces.json) are carried onto the body by rays from those cameras (tools/trace3d.py) and kept
here in the design frame (u9_data.py). The mirror head from c12 (head-on, 0.21 m across, top at y 1.01), its centre
triangulated from c00, c12 and c14.
"""
import math

import bmesh
from mathutils import Vector
from mathutils.geometry import delaunay_2d_cdt

import u9_kit as K
import u9_data as D


def loft(part, mat, sections, cap=True, smooth=True):
    """faces between closed rings of game points (same count); fans close the ends"""
    vs = part.grid(sections, mat, smooth=smooth, closed=True)
    if cap:
        idx = part.slot(mat)
        for ring, rev in ((vs[0], True), (vs[-1], False)):
            c = part.vert(sum((K.G(v.co) for v in ring), Vector()) / len(ring))
            n = len(ring)
            for k in range(n):
                q = [ring[k], ring[(k + 1) % n], c]
                if rev:
                    q.reverse()
                try:
                    f = part.bm.faces.new(q)
                except ValueError:
                    continue
                f.material_index = idx
                f.smooth = smooth
    return vs


def superellipse(cx, cy, rx, ry, n=20, p=3.0):
    out = []
    for k in range(n):
        a = 2 * math.pi * k / n
        c, s = math.cos(a), math.sin(a)
        out.append((cx + rx * math.copysign(abs(c) ** (2 / p), c), cy + ry * math.copysign(abs(s) ** (2 / p), s)))
    return out


# ------------------------------------------------------------------ projection frames and patches on the surface
class Frame:
    """a projection frame: centre c (game), outward direction d, e1 across (u), e2 = d x e1 (v)"""

    def __init__(self, c, d, e1):
        self.c = Vector(c)
        self.d = Vector(d).normalized()
        e1 = Vector(e1)
        self.e1 = (e1 - self.d * e1.dot(self.d)).normalized()
        self.e2 = self.d.cross(self.e1).normalized()

    def at(self, u, v, w=0.0):
        return self.c + self.e1 * u + self.e2 * v + self.d * w

    def uv(self, p):
        q = Vector(p) - self.c
        return (q.dot(self.e1), q.dot(self.e2))

    def hit(self, bvh, u, v, strict=False):
        p, n = K.project(bvh, self.at(u, v), self.d, back=1.2)
        if p is None:
            return (None, None) if strict else (self.at(u, v), self.d.copy())
        return p, n


def resample_closed(poly, step):
    """points every ~step along a closed 2-D outline (its corners kept)"""
    out = []
    n = len(poly)
    for i in range(n):
        a, b = Vector(poly[i]), Vector(poly[(i + 1) % n])
        k = max(1, int(math.ceil((b - a).length / step)))
        for j in range(k):
            out.append(tuple(a.lerp(b, j / k)))
    return out


def flat_patch(part, bvh, outline, fr, mat, lift=0.003, step=0.02, uvbox=None, holes=()):
    """a patch on the surface inside a 2-D outline (any simple polygon, frame fr): constrained Delaunay over the outline
    and a grid of inner points, every vertex projected onto the body along -d and lifted along the normal; UVs planar
    in the frame, into uvbox (u0, v0, u1, v1). Returns the outline's surface points."""
    ring = resample_closed(K.ccw(outline), step * 0.7)
    us = [p[0] for p in ring]
    vs = [p[1] for p in ring]
    u0, u1, v0, v1 = min(us), max(us), min(vs), max(vs)
    pts = [Vector((u, v)) for u, v in ring]
    nb = len(pts)
    edges = [(i, (i + 1) % nb) for i in range(nb)]
    faces = [list(range(nb))]
    for h in holes:
        hr = resample_closed(h, step * 0.7)
        o = len(pts)
        pts += [Vector(q) for q in hr]
        edges += [(o + i, o + (i + 1) % len(hr)) for i in range(len(hr))]
    u = u0 + step * 0.5
    while u < u1:
        v = v0 + step * 0.5
        while v < v1:
            if K.inside((u, v), ring) and all(not K.inside((u, v), h) for h in holes):
                if min((Vector((u, v)) - q).length for q in pts[:nb]) > step * 0.45:
                    pts.append(Vector((u, v)))
            v += step
        u += step
    vco, _e, tris, _ov, _oe, _of = delaunay_2d_cdt(pts, edges, faces, 1, 1e-7)
    vco = list(vco)
    hits = [fr.hit(bvh, q.x, q.y, strict=True) for q in vco]
    keep = []
    for t in tris:
        c = sum((vco[i] for i in t), Vector((0, 0))) / len(t)
        if K.inside((c.x, c.y), ring) and not any(K.inside((c.x, c.y), h) for h in holes):
            keep.append(tuple(t))
    # where the surface turns away from the projection (a bumper's corner), a flat triangle between surface points cuts
    # under the curved surface by more than the lift and the paint shows through: such edges are halved (the midpoint
    # put on the surface) and their triangles split, up to three times
    for _ in range(3):
        mid = {}

        def mid_of(i, j):
            k = (min(i, j), max(i, j))
            if k not in mid:
                mid[k] = None
                pi, pj = hits[i][0], hits[j][0]
                if pi is not None and pj is not None and (pi - pj).length > 0.25 * step:
                    q = (vco[i] + vco[j]) * 0.5
                    h = fr.hit(bvh, q.x, q.y, strict=True)
                    if h[0] is not None and abs((h[0] - (pi + pj) * 0.5).dot(h[1])) > 0.4 * lift:
                        vco.append(q)
                        hits.append(h)
                        mid[k] = len(vco) - 1
            return mid[k]

        split = []
        for a, b, c in keep:
            loop = []
            for i, j in ((a, b), (b, c), (c, a)):
                loop.append(i)
                m = mid_of(i, j)
                if m is not None:
                    loop.append(m)
            if len(loop) == 3:
                split.append((a, b, c))
                continue
            s = next(k for k, v in enumerate(loop) if v not in (a, b, c))   # fan from a midpoint: no flat triangle
            loop = loop[s:] + loop[:s]
            split += [(loop[0], loop[k], loop[k + 1]) for k in range(1, len(loop) - 1)]
        if len(split) == len(keep):
            break
        keep = split
    box = uvbox or (0, 0, 1, 1)
    vmap = []
    surf = []
    for p, n in hits:
        vmap.append(None if p is None else part.vert(p + n * lift))
        surf.append(p)
    idx = part.slot(mat)
    for t in keep:
        # no surface under a corner (off the body), or the corners on different surfaces (a ray past an edge)
        if any(vmap[i] is None for i in t) or max((surf[t[i]] - surf[t[i - 1]]).length for i in range(3)) > 6 * step:
            continue
        try:
            f = part.bm.faces.new([vmap[i] for i in t])
        except ValueError:
            continue
        f.material_index = idx
        f.smooth = True
        for loop, i in zip(f.loops, t):
            q = vco[i]
            loop[part.uv].uv = (box[0] + (box[2] - box[0]) * (q.x - u0) / max(1e-9, u1 - u0),
                                box[1] + (box[3] - box[1]) * (q.y - v0) / max(1e-9, v1 - v0))
    part.bm.normal_update()
    out = K.B(*fr.d) - K.B(0, 0, 0)
    for f in part.bm.faces:
        if f.material_index == idx and f.normal.dot(out) < 0:
            f.normal_flip()
    return surf


def strip(part, bvh, line, fr, width, mat, lift=0.0035, uv=(0.5, 0.5)):
    """a thin band on the surface along a 2-D polyline in frame fr (a lamp's light line, a shut line); all its UVs at
    one texel"""
    hits = [fr.hit(bvh, u, v, strict=True) for u, v in line]
    prev = None
    idx = part.slot(mat)
    for i, (p, n) in enumerate(hits):
        if p is None:
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
            except ValueError:
                prev = q
                continue
            f.material_index = idx
            f.smooth = True
            if K.G(f.normal).dot(n) < 0:
                f.normal_flip()
            for loop in f.loops:
                loop[part.uv].uv = uv
        prev = q


def polyline(pts, n):
    """n points evenly along an open 2-D polyline"""
    d = [0.0]
    for i in range(1, len(pts)):
        d.append(d[-1] + math.dist(pts[i], pts[i - 1]))
    out = []
    j = 0
    for k in range(n):
        s = d[-1] * k / (n - 1)
        while j < len(d) - 2 and d[j + 1] < s:
            j += 1
        L = d[j + 1] - d[j]
        t = 0.0 if L <= 0 else (s - d[j]) / L
        out.append((pts[j][0] + (pts[j + 1][0] - pts[j][0]) * t, pts[j][1] + (pts[j + 1][1] - pts[j][1]) * t))
    return out


# ------------------------------------------------------------------ mirrors
MIR_X0, MIR_X1 = 0.83, 1.045
MIR_ZC, MIR_YC = 0.64, 0.952      # the head's centre triangulated (c00, c12, c14): z 0.64 .. 0.69
MIR_HZ, MIR_HY = 0.085, 0.052


def mirror(part, mats, s=1):
    """one mirror (s = 1 left, -1 right): the pod (paint) with the glass on its back face, and the stalk"""
    rows = []
    n = 14
    for k in range(n + 1):
        t = k / n
        env = max((1 - (2 * t - 1) ** 4) ** 0.35, 0.12)
        x = MIR_X0 + (MIR_X1 - MIR_X0) * t
        hz = MIR_HZ * env * (0.92 + 0.08 * t)
        hy = MIR_HY * env * (1.0 - 0.15 * t)
        yc = MIR_YC + 0.012 * t
        ring = superellipse(MIR_ZC, yc, hz, hy, n=20, p=2.6)
        rows.append([(s * x, y, z) for z, y in ring])
    mp = K.Part('mirror')
    loft(mp, mats['paint'], rows)
    bmesh.ops.recalc_face_normals(mp.bm, faces=mp.bm.faces)
    mp.bm.normal_update()
    gi = mp.slot(mats['chrome'])
    for f in mp.bm.faces:
        if K.G(f.normal).z < -0.75 and abs(K.G(f.calc_center_median()).x) > MIR_X0 + 0.02:
            f.material_index = gi
    part.absorb(mp)
    st = K.Part('stalk')
    a, b = Vector((s * 0.72, 0.885, 0.74)), Vector((s * 0.86, 0.935, 0.66))
    rows = []
    for k in range(6):
        c = a.lerp(b, k / 5)
        rows.append([(c.x, c.y + dy, c.z + dz) for dz, dy in superellipse(0, 0, 0.035, 0.010, n=12, p=2.2)])
    loft(st, mats['trim'], rows)
    bmesh.ops.recalc_face_normals(st.bm, faces=st.bm.faces)
    part.absorb(st)


# ------------------------------------------------------------------ lamps
def _frame_of(pts3, d, e1):
    c = sum((Vector(p) for p in pts3), Vector()) / len(pts3)
    return Frame(c, d, e1)


UV_FIN = (0.975, 0.875)            # the headlamp texture's light grey block (u9_textures)


def headlamps(part, mats, bvh):
    """the 'Gate of Time' lamps: one dark lens round the body-coloured blade (the eyebrow above it, the outer side and
    the lower 'gate' below), the light line along the eyebrow's lower edge, the gate's slanted light bars"""
    for s in (1, -1):
        P = [(s * x, y, z) for x, y, z in D.HL]
        fr = _frame_of(P, (s * D.HL_D[0], D.HL_D[1], D.HL_D[2]), (s, 0, 0))
        uv = [fr.uv(p) for p in P]
        if s < 0:
            uv = list(reversed(uv))
        flat_patch(part, bvh, uv, fr, mats['headlight'], lift=0.004, step=0.012, uvbox=D.HL_UV)
        # the light line just inside the outer contour: the upper arm's top edge, the outer side, the lower arm's bottom
        full = [fr.uv((s * x, y, z)) for x, y, z in D.HL]
        area = sum(full[i - 1][0] * full[i][1] - full[i][0] * full[i - 1][1] for i in range(len(full)))
        outer = polyline(full[:D.HL_OUTER], 60)
        line = []
        for i, (u, v) in enumerate(outer):
            a, b = outer[max(0, i - 1)], outer[min(len(outer) - 1, i + 1)]
            t = Vector((b[0] - a[0], b[1] - a[1])).normalized()
            nrm = Vector((-t.y, t.x)) * (1 if area > 0 else -1)          # toward the lens's inside
            line.append((u + nrm.x * 0.007, v + nrm.y * 0.007))
        strip(part, bvh, line[1:-1], fr, 0.005, mats['headlight'], lift=0.0065, uv=D.UV_WHITE)
        # the gate's fins: fine, light grey (c12: chrome fins in the dark lens, not white bars)
        for a3, b3 in D.HL_BARS:
            a, b = fr.uv((s * a3[0], a3[1], a3[2])), fr.uv((s * b3[0], b3[1], b3[2]))
            strip(part, bvh, polyline([a, b], 5), fr, 0.003, mats['headlight'], lift=0.0065, uv=UV_FIN)


def taillamp(part, mats, bvh):
    """the full-width band: one patch across the tail (left and right halves meet at the emblem)"""
    fr = Frame((0, 0, -2.3), (0, 0, -1), (-1, 0, 0))
    half = [(-x, y) for x, y, z in D.TL]           # frame u = -x
    full = half + [(-u, v) for u, v in reversed(half)]
    flat_patch(part, bvh, full, fr, mats['taillight'], lift=0.004, step=0.02, uvbox=(0, 0, 1, 1))


# ------------------------------------------------------------------ the side
def side(part, mats, bvh):
    """the dark intake slot behind the door (leaning back, from the sill up to the black strip) with the carbon sill,
    the black strip along the side from the tail lamp to the front wheel, and the door's shut lines (c14)"""
    for s in (1, -1):
        fr = Frame((s * 1.0, 0, 0), (s, 0, 0), (0, 0, 1))
        P = [(s * x, y, z) for x, y, z in D.SIDE]
        flat_patch(part, bvh, [fr.uv(p) for p in P], fr, mats['carbon'], lift=0.003, step=0.03)
        line = [fr.uv((s * x, y, z)) for x, y, z in D.CHARLINE]
        strip(part, bvh, polyline(line, 60), fr, 0.014, mats['trim'], lift=0.0035)
        for pts in D.DOOR_LINES:
            line = [fr.uv((s * x, y, z)) for x, y, z in pts]
            strip(part, bvh, polyline(line, 16), fr, 0.004, mats['trim'], lift=0.0032)


# ------------------------------------------------------------------ black sections, splitter, diffuser
def front_black(part, mats, bvh):
    """the black lower bumper and corner intakes below the paint edge (front frame: u = x, v = y)"""
    fr = Frame((0, 0, 2.3), (0, 0, 1), (1, 0, 0))
    right = [(x, y) for x, y, z in D.FPAINT]              # outer corner -> centre (x < 0)
    left = [(-x, y) for x, y in reversed(right)]
    bot = D.FRONT_BLACK_BOTTOM
    poly = right + left[1:] + [(-right[0][0] + 0.02, bot), (right[0][0] - 0.02, bot)]
    flat_patch(part, bvh, poly, fr, mats['trim'], lift=0.0025, step=0.025)


def plate(part, mats, bvh):
    """the number plates on the black lower bumper (c12) and the carbon centre section (c18): grey panels, their
    corners rounded"""
    for key, fr in (('PLATE', Frame((0, 0, 2.3), (0, 0, 1), (1, 0, 0))),
                    ('PLATE_R', Frame((0, 0, -2.3), (0, 0, -1), (-1, 0, 0)))):
        if not getattr(D, key, None):
            continue
        hw, y0, y1, _ = getattr(D, key)
        flat_patch(part, bvh, superellipse(0.0, 0.5 * (y0 + y1), hw, 0.5 * (y1 - y0), n=28, p=8.0), fr,
                   mats['plate'], lift=0.006, step=0.02)


# our own simple emblem: a light rounded tile with one curling stroke (not the maker's drawing)
CURL = [(-0.55, 0.62), (-0.05, 0.6), (0.28, 0.42), (0.22, 0.12), (-0.18, 0.0), (-0.22, -0.25), (0.1, -0.45),
        (0.6, -0.55)]


def emblems(part, mats, bvh):
    for key, fr, (hw, hh), ink in (('BADGE_F', Frame((0, 0, 2.3), (0, 0, 1), (1, 0, 0)), (0.0275, 0.0235), 'trim'),
                                   ('BADGE_R', Frame((0, 0, -2.3), (0, 0, -1), (-1, 0, 0)), (0.025, 0.032), 'trim')):
        if not getattr(D, key, None):
            continue
        yc = getattr(D, key)[0]
        flat_patch(part, bvh, superellipse(0.0, yc, hw, hh, n=24, p=5.0), fr, mats['chrome'], lift=0.007, step=0.006)
        line = polyline([(u * hw, yc + v * hh) for u, v in CURL], 16)
        strip(part, bvh, line, fr, 0.15 * min(hw, hh) * 2, mats[ink], lift=0.0085)


def hood_line(part, mats, bvh):
    """the hood's front shut line between the lamps' inner tips (c12)"""
    if not getattr(D, 'HOODLINE', None):
        return
    fr = Frame((0, 0, 2.3), (0, 0.45, 1), (1, 0, 0))
    strip(part, bvh, polyline([fr.uv(p) for p in D.HOODLINE], 24), fr, 0.005, mats['trim'], lift=0.002)


def rear_black(part, mats, bvh):
    """the carbon centre section under the tail band (from the band's lower edge down the inner curves to the plate) and
    the diffuser's face across the tail below it (rear frame: u = -x, v = y)"""
    fr = Frame((0, 0, -2.3), (0, 0, -1), (-1, 0, 0))
    left = [(-x, y) for x, y, z in D.RPAINT[:7]]           # lamp's outer bottom -> down the inner curve (u < 0)
    right = [(-u, v) for u, v in reversed(left)]
    top_l = [(-x, y + 0.008) for x, y, z in D.TL[7:]]       # the band's lower edge, outer end -> centre (u < 0)
    top = [(-u, v) for u, v in top_l] + list(reversed(top_l))[1:]
    flat_patch(part, bvh, left + right + top, fr, mats['carbon'], lift=0.0025, step=0.025)
    edge = [(-x, y) for x, y, z in reversed(D.RPAINT[6:])]  # the diffuser's top edge, outer end -> centre (u < 0)
    yb = D.DIFFUSER_BOTTOM
    poly = edge + [(-u, v) for u, v in reversed(edge)][1:] + [(-edge[0][0], yb), (edge[0][0], yb)]
    flat_patch(part, bvh, poly, fr, mats['carbon'], lift=0.0025, step=0.03)


def diffuser_fins(part, mats):
    """the Xtreme's diffuser strakes: vertical carbon plates from the floor up the diffuser to the tail"""
    for x in D.FIN_X:
        for s in (1, -1):
            prof = [(-1.95, 0.12), (-2.20, 0.16), (-2.42, 0.25), (-2.535, 0.31), (-2.535, D.DIFFUSER_TOP - 0.04),
                    (-2.44, D.DIFFUSER_TOP - 0.04), (-2.30, 0.30), (-2.05, 0.16)]
            pts = [(s * x, y, z) for z, y in prof]
            part.absorb(_plate(pts, 0.008, mats['carbon']))


def _plate(pts, t, mat):
    """a flat plate (outline in a plane x = const, game points) with thickness t"""
    p = K.Part('plate')
    a = [(x - t / 2, y, z) for x, y, z in pts]
    b = [(x + t / 2, y, z) for x, y, z in pts]
    p.face(a, mat, smooth=False, out=(-1, 0, 0))
    p.face(b, mat, smooth=False, out=(1, 0, 0))
    n = len(pts)
    for i in range(n):
        j = (i + 1) % n
        p.face([a[i], a[j], b[j], b[i]], mat, smooth=False)
    bmesh.ops.remove_doubles(p.bm, verts=p.bm.verts, dist=1e-7)
    bmesh.ops.recalc_face_normals(p.bm, faces=p.bm.faces)
    return p


def splitter(part, mats):
    """the Xtreme's carbon splitter: a thin blade under the nose, proud of the bumper by a few cm"""
    rows = []
    for k in range(21):
        t = -1 + 2 * k / 20
        x = t * D.SPLIT_HALF
        e = abs(t) ** 2.6
        zf = D.SPLIT_Z - D.SPLIT_SWEEP * e                  # the lip sweeps back toward the corners
        rows.append([(x, D.SPLIT_Y, zf - 0.30), (x, D.SPLIT_Y, zf - 0.01), (x, D.SPLIT_Y + 0.004, zf),
                     (x, D.SPLIT_Y + 0.016, zf), (x, D.SPLIT_Y + 0.02, zf - 0.01), (x, D.SPLIT_Y + 0.02, zf - 0.30)])
    sp = K.Part('splitter')
    sp.grid(rows, mats['carbon'], smooth=False)
    bmesh.ops.recalc_face_normals(sp.bm, faces=sp.bm.faces)
    part.absorb(sp)


# ------------------------------------------------------------------ the Xtreme's engine cover
# c18 (behind) and c17: between the haunches, louvres stacked like shelves (three to four a side, dark gaps under
# them) either side of a narrow spine with two red light strips running from the roof's end to the deck's lip
LOUVRE_X = (0.10, 0.47)
LOUVRE_Z = (-1.40, -1.63, -1.86, -2.09)      # the slats' front edges; each 0.2 m deep, its rear edge level with its front
STRIP_X, STRIP_Z = 0.052, (-0.95, -2.31)


def rear_deck(part, mats, bvh):
    fr = Frame((0, 1.0, -1.8), (0, 1, 0), (1, 0, 0))          # from above (rays from y 2.2): u = x, v = -(z + 1.8)

    def surf(x, z):
        return fr.hit(bvh, x, -(z + 1.8))

    x0, x1 = LOUVRE_X
    for s in (1, -1):
        # the dark recess under the slats
        poly = [(s * x0, -(-1.33 + 1.8)), (s * x1, -(-1.33 + 1.8)), (s * x1, -(-2.31 + 1.8)), (s * x0, -(-2.31 + 1.8))]
        flat_patch(part, bvh, poly if s > 0 else list(reversed(poly)), fr, mats['grille'], lift=0.002, step=0.03)
        for zf in LOUVRE_Z:
            rows = []
            for k in range(9):
                x = s * (x0 + (x1 - x0) * k / 8)
                p, n = surf(x, zf)
                ftop = p + n * 0.006
                rtop = Vector((x, ftop.y - 0.004, zf - 0.20))
                rows.append([tuple(ftop), tuple(rtop), (x, rtop.y - 0.009, rtop.z), tuple(ftop - Vector((0, 0.009, 0)))])
            if s < 0:
                rows.reverse()
            lp = K.Part('louvre')
            loft(lp, mats['carbon'], rows, smooth=False)
            bmesh.ops.recalc_face_normals(lp.bm, faces=lp.bm.faces)
            part.absorb(lp)
    # the spine and its two red strips
    rows = []
    for k in range(15):
        z = STRIP_Z[0] + (STRIP_Z[1] - STRIP_Z[0]) * k / 14
        p, n = surf(0.0, z)
        b = p - n * 0.01
        rows.append([(-0.032, b.y, z), (-0.022, p.y + 0.022, z), (0.022, p.y + 0.022, z), (0.032, b.y, z)])
    sp = K.Part('spine')
    loft(sp, mats['carbon'], rows, smooth=False)
    bmesh.ops.recalc_face_normals(sp.bm, faces=sp.bm.faces)
    part.absorb(sp)
    for s in (1, -1):
        line = [(s * STRIP_X, -(z + 1.8)) for z in
                (STRIP_Z[0] + (STRIP_Z[1] - STRIP_Z[0]) * k / 30 for k in range(31))]
        strip(part, bvh, line, fr, 0.014, mats['lightstrip'], lift=0.003)


# ------------------------------------------------------------------ the Xtreme's rear wing
# Estimated from c18 (behind: endplates at |x| ~1.0 from y 1.14 to 1.35, the mainplane a thin band at y ~1.25, the swan
# necks at |x| ~0.45), c14 (side: at roof height, its trailing edge just behind the tail) and c17
WING_X = 1.0
WING_LE = (-2.28, 1.205)          # (z, y) of the leading edge
WING_TE = (-2.585, 1.27)          # and the trailing edge (the gurney on top of it)
WING_T = 0.034                    # the section's thickness


def _airfoil(n=14):
    """a cambered section (s along the chord 0..1, offsets of the upper and lower surface, chord units)"""
    up, lo = [], []
    for k in range(n + 1):
        sx = 0.5 - 0.5 * math.cos(math.pi * k / n)
        t = 5 * 0.12 * (0.2969 * math.sqrt(sx) - 0.126 * sx - 0.3516 * sx ** 2 + 0.2843 * sx ** 3 - 0.1036 * sx ** 4)
        camber = 0.05 * (1 - (2 * sx - 1) ** 2)
        up.append((sx, camber + t))
        lo.append((sx, camber - t))
    return up, lo


def wing(part, mats):
    up, lo = _airfoil()
    (z0, y0), (z1, y1) = WING_LE, WING_TE
    ch = math.hypot(z1 - z0, y1 - y0)
    tz, ty = (z1 - z0) / ch, (y1 - y0) / ch
    nz, ny = -ty, tz                              # the section's 'up', pointing up and back
    if ny < 0:
        nz, ny = -nz, -ny
    sec = [(z0 + tz * ch * sx + nz * ch * h * (WING_T / ch / 0.12 * 0.5), y0 + ty * ch * sx + ny * ch * h * (WING_T / ch / 0.12 * 0.5))
           for sx, h in list(reversed(up)) + lo[1:-1]]
    rows = []
    for k in range(17):
        x = -WING_X + 2 * WING_X * k / 16
        rows.append([(x, y, z) for z, y in sec])
    wp = K.Part('wing')
    loft(wp, mats['carbon'], rows, smooth=True)
    bmesh.ops.recalc_face_normals(wp.bm, faces=wp.bm.faces)
    part.absorb(wp)
    # the gurney: a carbon strip standing on the trailing edge (c17/c18: the wing is all dark carbon)
    g = K.Part('gurney')
    g.box(mats['carbon'], (0, y1 + 0.012, z1 + 0.006), (2 * WING_X - 0.02, 0.022, 0.006))
    part.absorb(g)
    # endplates
    ep = [(-2.235, 1.165), (-2.30, 1.305), (-2.47, 1.355), (-2.655, 1.345), (-2.705, 1.225), (-2.625, 1.12), (-2.40, 1.11)]
    for s in (1, -1):
        part.absorb(_plate([(s * (WING_X + 0.006), y, z) for z, y in ep], 0.012, mats['carbon']))
    # the swan necks: from the engine cover up over the leading edge, down onto the wing's upper surface
    path = [(-1.90, 1.02), (-1.97, 1.15), (-2.06, 1.29), (-2.17, 1.365), (-2.29, 1.37), (-2.38, 1.33), (-2.43, 1.27)]
    for s in (1, -1):
        rows = []
        n = len(path)
        for i, (z, y) in enumerate(path):
            a = path[max(0, i - 1)]
            b = path[min(n - 1, i + 1)]
            dz, dy = b[0] - a[0], b[1] - a[1]
            L = math.hypot(dz, dy)
            mz, my = -dy / L, dz / L                 # normal to the path in the (z, y) plane
            wdt = 0.13 - 0.07 * i / (n - 1)
            x = s * 0.45
            rows.append([(x - 0.007, y - my * wdt / 2, z - mz * wdt / 2), (x + 0.007, y - my * wdt / 2, z - mz * wdt / 2),
                         (x + 0.007, y + my * wdt / 2, z + mz * wdt / 2), (x - 0.007, y + my * wdt / 2, z + mz * wdt / 2)])
        nk = K.Part('neck')
        loft(nk, mats['carbon'], rows, smooth=False)
        bmesh.ops.recalc_face_normals(nk.bm, faces=nk.bm.faces)
        part.absorb(nk)


WING = True        # the fit tools leave the wing out (two of the photos show the U9 without it)
AERO = True        # and the splitter and the diffuser's strakes (the Xtreme's; the regular U9's photos have neither)


def build(body, mats, shell, bvh, count):
    p = K.Part('mirrors')
    for s in (1, -1):
        mirror(p, mats, s)
    count['mirrors'] = p.tris()
    p.build(body)
    if WING:
        wp = K.Part('wing')
        wing(wp, mats)
        count['wing'] = wp.tris()
        wp.build(body)
    if getattr(D, 'HL', None):
        lp = K.Part('lamps')
        headlamps(lp, mats, bvh)
        taillamp(lp, mats, bvh)
        count['lamps'] = lp.tris()
        lp.build(body)
        bp = K.Part('bumpers')
        front_black(bp, mats, bvh)
        plate(bp, mats, bvh)
        hood_line(bp, mats, bvh)
        emblems(bp, mats, bvh)
        rear_black(bp, mats, bvh)
        if getattr(D, 'SIDE', None):
            side(bp, mats, bvh)
        if AERO:
            diffuser_fins(bp, mats)
            splitter(bp, mats)
            rear_deck(bp, mats, bvh)
        count['bumpers'] = bp.tris()
        bp.build(body)
