"""
Details of the SU7 on the shell: mirrors, the lidar, lamps, the black sections of the bumpers, the blades behind the
front wheels, shut lines, flush handles, the charge port, plates and badges.

Placed from the Commons photos (fitdata/su7/ref/list.json) with the solved cameras (fitdata/su7/fit/): outlines traced
on the photos (fitdata/su7/traces.json) are carried onto the body by rays from those cameras (tools/trace3d.py) and
kept in the design frame (su7_data.py: PATCH, LINE, HL, TL). The patch helpers are the U9's (u9_details).
"""
import math

import bmesh
from mathutils import Vector
from mathutils.geometry import delaunay_2d_cdt

import su7_kit as K
import su7_data as D


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


class Wrap:
    """the tail band's frame: the band runs round the car's corners onto the flanks, so its points are laid out by
    their bearing from a vertical axis through the car's middle line at z = za (u = -r x bearing: the car's left at
    u < 0, as in the frame from behind) and their height (v); a point is put on the body by a level ray from outside
    toward that axis, which meets the rear face and the flank alike at a fair angle"""
    wrap = True

    def __init__(self, za=D.TL_AXIS[0], r=D.TL_AXIS[1]):
        self.za, self.r = za, r
        self.d = Vector((0, 0, -1))

    def uv(self, p):
        return (-self.r * math.atan2(p[0], self.za - p[2]), p[1])

    def hit(self, bvh, u, v, strict=False):
        a = -u / self.r
        d = Vector((math.sin(a), 0.0, -math.cos(a)))
        o = Vector((0.0, v, self.za))
        p, n = K.project(bvh, o, d, back=1.8)
        if p is None:
            return (None, None) if strict else (o + d, d.copy())
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
    made = []
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
        made.append((f, hits[t[0]][1] + hits[t[1]][1] + hits[t[2]][1]))
        for loop, i in zip(f.loops, t):
            q = vco[i]
            loop[part.uv].uv = (box[0] + (box[2] - box[0]) * (q.x - u0) / max(1e-9, u1 - u0),
                                box[1] + (box[3] - box[1]) * (q.y - v0) / max(1e-9, v1 - v0))
    part.bm.normal_update()
    if getattr(fr, 'wrap', False):          # round a corner there is no one outward direction: by the surface's own
        for f, n in made:
            if f.normal.dot(K.B(*n) - K.B(0, 0, 0)) < 0:
                f.normal_flip()
        return surf
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



# ------------------------------------------------------------------ frames
def frame(key, s=1):
    """the projection frames the data's outlines are laid out in (s = 1 the car's left, -1 its right)"""
    if key == 'front':
        return Frame((0, 0, 2.3), (0, 0, 1), (1, 0, 0))
    if key == 'rear':
        return Frame((0, 0, -2.3), (0, 0, -1), (-1, 0, 0))
    if key == 'side':
        return Frame((s * 1.0, 0, 0), (s, 0, 0), (0, 0, 1))
    if key == 'nose':                # the bonnet's leading edge
        return Frame((0, 0, 2.3), (0, 0.6, 0.8), (1, 0, 0))
    if key == 'top':
        return Frame((0, 1.0, 0), (0, 1, 0), (1, 0, 0))
    if key == 'fq':                 # the bumper's front corner
        return Frame((s * 0.8, 0.4, 2.2), (s * 0.62, 0.0, 0.78), (0, 1, 0))
    if key == 'rq':                 # the bumper's rear corner
        return Frame((s * 0.8, 0.5, -2.2), (s * 0.62, 0.0, -0.78), (0, 1, 0))
    raise KeyError(key)


def _sided(pts, s):
    return [(s * x, y, z) for x, y, z in pts]


def patches(part, mats, bvh):
    """D.PATCH: (name, frame, material, lift, sym, points): closed outlines on the body. sym 'LR' = the left side's
    outline, mirrored to the right; 'C' = a half outline across the centre line (centre -> outer -> centre), completed
    by its mirror image; 'F' = as given"""
    for name, key, mat, lift, sym, pts in D.PATCH:
        fine = max(math.dist(pts[i], pts[i - 1]) for i in range(len(pts))) < 0.12
        step = 0.012 if fine else 0.025
        if sym == 'LR':
            for s in (1, -1):
                fr = frame(key, s)
                flat_patch(part, bvh, [fr.uv(p) for p in _sided(pts, s)], fr, mats[mat], lift=lift, step=step)
        else:
            fr = frame(key)
            uv = [fr.uv(p) for p in pts]
            if sym == 'C':
                uv = uv + [fr.uv((-x, y, z)) for x, y, z in reversed(pts)][1:-1]
            flat_patch(part, bvh, uv, fr, mats[mat], lift=lift, step=step)


def lines(part, mats, bvh):
    """D.LINE: (name, frame, material, width, sym, points): shut lines, handles, the charge port's lid ('LR' both
    sides, 'L' the left only, 'C' a half line mirrored across the centre, 'F' as given); a closed line repeats its
    first point"""
    for name, key, mat, width, sym, pts in D.LINE:
        n = max(8, int(sum(math.dist(pts[i], pts[i - 1]) for i in range(1, len(pts))) / 0.03))
        for s in ((1, -1) if sym == 'LR' else (1,)):
            fr = frame(key, s)
            uv = [fr.uv(p) for p in _sided(pts, s)]
            m = n
            if sym == 'C':
                uv = uv + [fr.uv((-x, y, z)) for x, y, z in reversed(pts)][1:]
                m = 2 * n
            strip(part, bvh, polyline(uv, m), fr, width, mats[mat], lift=0.0065 if mat == 'paint' else 0.0032)


# ------------------------------------------------------------------ mirrors
# k68 (head-on, the fitted camera): the head from 0.90 to 1.045 off the centre line, 0.13 tall; k13: 0.24 long, on a short
# black foot on the door, below the belt
MIR_X0, MIR_X1 = 0.900, 1.045
MIR_ZC, MIR_YC = 0.555, 1.030
MIR_HZ, MIR_HY = 0.105, 0.062


def mirror(part, mats, s=1):
    """one mirror (s = 1 left, -1 right): the cap (paint) with the glass on its back face, the black foot"""
    rows = []
    n = 14
    for k in range(n + 1):
        t = k / n
        env = max((1 - (2 * t - 1) ** 4) ** 0.4, 0.14)
        x = MIR_X0 + (MIR_X1 - MIR_X0) * t
        hz = MIR_HZ * env * (0.80 + 0.20 * t)
        hy = MIR_HY * env * (1.0 - 0.12 * t)
        ring = superellipse(MIR_ZC - 0.02 * t, MIR_YC + 0.008 * t, hz, hy, n=20, p=2.5)
        rows.append([(s * x, y, z) for z, y in ring])
    mp = K.Part('mirror')
    loft(mp, mats['paint'], rows)
    bmesh.ops.recalc_face_normals(mp.bm, faces=mp.bm.faces)
    mp.bm.normal_update()
    gi, ti = mp.slot(mats['chrome']), mp.slot(mats['trim'])
    for f in mp.bm.faces:
        g, nrm = K.G(f.calc_center_median()), K.G(f.normal)
        if nrm.z < -0.75 and abs(g.x) > MIR_X0 + 0.02:
            f.material_index = gi                       # the glass
        elif g.y < MIR_YC - 0.5 * MIR_HY and nrm.z > -0.75:
            f.material_index = ti                       # the cap's black underside
    part.absorb(mp)
    st = K.Part('foot')
    a, b = Vector((s * 0.86, 0.925, 0.66)), Vector((s * 0.925, 0.985, 0.585))
    rows = []
    for k in range(6):
        c = a.lerp(b, k / 5)
        rows.append([(c.x, c.y + dy, c.z + dz) for dz, dy in superellipse(0, 0, 0.055, 0.016, n=12, p=2.2)])
    loft(st, mats['trim'], rows)
    bmesh.ops.recalc_face_normals(st.bm, faces=st.bm.faces)
    part.absorb(st)


# ------------------------------------------------------------------ the lidar
LIDAR_HW, LIDAR_Z1, LIDAR_Z0, LIDAR_H = 0.155, 0.275, -0.02, 0.046      # k13 / k16: over the header, its top below the roof's peak


def lidar(part, mats, bvh):
    """the Max's lidar pod over the windscreen's header: a low rounded hump in the header's black, its window (dark
    glass) looking forward"""
    fr = frame('top')
    nx, nz = 12, 9
    rows = []
    for i in range(nx + 1):
        tx = -1 + 2 * i / nx
        x = tx * LIDAR_HW
        ex = max(0.0, 1 - abs(tx) ** 3.2) ** 0.6
        row = []
        for j in range(nz + 1):
            tz = j / nz                                        # 0 at the window, 1 at the pod's tail
            z = LIDAR_Z1 + (LIDAR_Z0 - LIDAR_Z1) * tz
            p, _n = fr.hit(bvh, x, -z)
            ez = min(1.0, tz / 0.10) ** 0.5 * (1 - K.smoothstep(0.30, 1.0, tz))
            if j == 0:
                row.append((x, p.y - 0.004, z + 0.012 * ex))                       # the window's foot
                row.append((x, p.y - 0.004 + (LIDAR_H + 0.004) * ex * 0.86, z - 0.02 * ex))
            else:
                row.append((x, p.y - 0.004 + (LIDAR_H + 0.004) * ex * ez, z))
        rows.append(row)
    lp = K.Part('lidar')
    lp.grid(rows, mats['trim'], smooth=True)
    bmesh.ops.recalc_face_normals(lp.bm, faces=lp.bm.faces)
    lp.bm.normal_update()
    up = K.B(0, 1, 0) - K.B(0, 0, 0)
    if sum(f.normal.dot(up) for f in lp.bm.faces) < 0:
        for f in lp.bm.faces:
            f.normal_flip()
    lp.bm.normal_update()
    wi = lp.slot(mats['sensor'])
    for f in lp.bm.faces:                                       # the window: the faces of the first row, mid span
        g = K.G(f.calc_center_median())
        if g.z > LIDAR_Z1 - 0.022 and abs(g.x) < LIDAR_HW * 0.72 and K.G(f.normal).z > 0.5:
            f.material_index = wi
    part.absorb(lp)


# ------------------------------------------------------------------ lamps
def head_frame(s=1):
    c, d, e = D.HL_C, D.HL_D, D.HL_E1          # the right lamp's frame mirrors the left's: u runs the other way
    return Frame((s * c[0], c[1], c[2]), (s * d[0], d[1], d[2]), (e[0], s * e[1], s * e[2]))


def headlamps(part, mats, bvh):
    """the 'water drop' lamps: one clear lens each, pointed toward the centre line, its inside (the light line along
    the upper edge, the four lens units) drawn on the texture laid over the outline's box (su7_textures)"""
    for s in (1, -1):
        fr = head_frame(s)
        uv = [fr.uv(p) for p in _sided(D.HL, s)]
        flat_patch(part, bvh, uv, fr, mats['headlight'], lift=0.004, step=0.012,
                   uvbox=(0, 0, 1, 1) if s > 0 else (1, 0, 0, 1))


def taillamp(part, mats, bvh):
    """the full-width band with its looped ends: one patch across the tail and round its corners onto the flanks"""
    fr = Wrap()
    half = [fr.uv(p) for p in D.TL]
    full = half + [(-u, v) for u, v in reversed(half)][1:-1]
    flat_patch(part, bvh, full, fr, mats['taillight'], lift=0.004, step=0.016, uvbox=(0, 0, 1, 1))


# ------------------------------------------------------------------ plates, badges
def plate(part, mats, c, n, w=0.33, h=0.165):
    """a Japanese plate (330 x 165 mm), as the game's other cars carry: a thin slab, its face textured"""
    n = Vector(n).normalized()
    ax = Vector((0, 1, 0)).cross(n).normalized()
    ay = n.cross(ax)
    pts = [Vector(c) + ax * u * w / 2 + ay * v * h / 2 for u, v in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    front = [p + n * 0.004 for p in pts]
    part.face(front, mats['plate'], smooth=False, uvs=[(0, 0), (1, 0), (1, 1), (0, 1)], out=n)
    for i in range(4):
        j = (i + 1) % 4
        part.face([pts[i], pts[j], front[j], front[i]], mats['trim'], smooth=False)


def plates(part, mats, bvh):
    for key, (y, back) in (('front', D.PLATE_F), ('rear', D.PLATE_R)):
        fr = frame(key)
        p, n = fr.hit(bvh, 0.0, y)
        n = Vector((0, n.y, n.z)).normalized()
        pp = K.Part('plate')
        plate(pp, mats, p + n * back, n)
        ti = pp.slot(mats['trim'])
        bmesh.ops.recalc_face_normals(pp.bm, faces=[f for f in pp.bm.faces if f.material_index == ti])
        part.absorb(pp)


# our own drawing of the marks (no artwork taken): a wide rounded tile with an arch, a stem under it and a stem beside
# it; plain letters across the boot lid and for the model's name on its right
MARK = [[(-0.62, -0.55), (-0.62, 0.50), (0.10, 0.50), (0.10, -0.55)], [(-0.26, -0.55), (-0.26, 0.12)],
        [(0.56, -0.55), (0.56, 0.50)]]


def _o(cx, r=0.5, n=10):
    return [(cx + r * 0.62 * math.cos(2 * math.pi * k / n), r * math.sin(2 * math.pi * k / n)) for k in range(n + 1)]


GLYPH = {   # strokes in a 1-high line, each letter's own x from 0; (advance, strokes)
    'x': (0.75, [[(0.0, -0.5), (0.62, 0.5)], [(0.0, 0.5), (0.62, -0.5)]]),
    'i': (0.30, [[(0.05, -0.5), (0.05, 0.5)]]),
    'a': (0.85, [_o(0.31), [(0.62, -0.5), (0.62, 0.5)]]),
    'o': (0.85, [_o(0.31)]),
    'm': (1.20, [[(0.0, -0.5), (0.0, 0.5), (0.48, 0.5), (0.48, -0.5)], [(0.48, 0.5), (0.96, 0.5), (0.96, -0.5)]]),
    'S': (0.85, [[(0.6, 0.32), (0.45, 0.5), (0.15, 0.5), (0.0, 0.3), (0.15, 0.05), (0.45, -0.05), (0.6, -0.3), (0.45, -0.5),
                  (0.15, -0.5), (0.0, -0.32)]]),
    'U': (0.85, [[(0.0, 0.5), (0.0, -0.3), (0.15, -0.5), (0.45, -0.5), (0.6, -0.3), (0.6, 0.5)]]),
    '7': (0.85, [[(0.0, 0.5), (0.6, 0.5), (0.2, -0.5)]]),
    'M': (0.95, [[(0.0, -0.5), (0.0, 0.5), (0.35, -0.1), (0.7, 0.5), (0.7, -0.5)]]),
    ' ': (0.35, []),
}


def lettering(part, mats, bvh, fr, text, uc, vc, h, mat, gap=0.0):
    """text in plain strokes on the surface, centred at (uc, vc) in frame fr, h high"""
    total = sum(GLYPH[c][0] + gap for c in text) * h
    u = uc - total / 2
    for c in text:
        w, strokes = GLYPH[c]
        for st in strokes:
            pts = [(u + a * h, vc + b * h) for a, b in st]
            strip(part, bvh, polyline(pts, max(4, 2 * len(pts))), fr, 0.17 * h, mats[mat], lift=0.004)
        u += (w + gap) * h


def badges(part, mats, bvh):
    fr = frame('nose')                                              # the bonnet's badge: 75 x 28 mm (k68)
    yc, hw, hh = fr.uv((0, D.BADGE_F[0], D.BADGE_F[1]))[1], 0.0375, 0.014
    flat_patch(part, bvh, superellipse(0.0, yc, hw, hh, n=24, p=4.5), fr, mats['chrome'], lift=0.004, step=0.008)
    for st in MARK:
        strip(part, bvh, polyline([(u * hh * 1.5, yc + v * hh * 0.95) for u, v in st], 10), fr, 0.22 * hh, mats['trim'], lift=0.0052)
    fr = frame('rear')                                              # the lettering on the boot lid, spaced wide (k32)
    lettering(part, mats, bvh, fr, 'xiaomi', 0.0, D.LETTER_Y, D.LETTER_H, 'chrome', gap=1.05)
    ux, uy = -D.MODEL_BADGE[0], D.MODEL_BADGE[1]                    # the model's name on the lid's right (k32)
    lettering(part, mats, bvh, fr, 'SU7', ux - 0.036, uy, 0.022, 'chrome')
    lettering(part, mats, bvh, fr, 'Max', ux + 0.042, uy, 0.020, 'reflector')


def build(body, mats, shell, bvh, count, bare=False):
    p = K.Part('mirrors')
    for s in (1, -1):
        mirror(p, mats, s)
    lidar(p, mats, bvh)
    count['mirrors'] = p.tris()
    p.build(body)
    if bare:
        return
    lp = K.Part('lamps')
    headlamps(lp, mats, bvh)
    taillamp(lp, mats, bvh)
    count['lamps'] = lp.tris()
    lp.build(body)
    bp = K.Part('trimwork')
    patches(bp, mats, bvh)
    lines(bp, mats, bvh)
    plates(bp, mats, bvh)
    badges(bp, mats, bvh)
    count['trimwork'] = bp.tris()
    bp.build(body)
