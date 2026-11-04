"""
Building blocks for the Silvia S15 model (TOUGE NOCTURNE): coordinates, materials, mesh parts, a polygon cutter for
the subdivided body, the check scene and the GLB export. Own copy for this car (no module shared between cars).

Game frame: metres, +x = the car's left, +y up (0 = ground), +z forward, origin on the ground midway between the
axles. Blender frame: (x, -z, y), so the glTF exporter (+Y up) gives the game frame back.
"""
import math

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector


def B(x, y, z):
    """game → Blender"""
    return Vector((x, -z, y))


def G(v):
    """Blender → game"""
    return v[0], v[2], -v[1]


def srgb(h):
    h = h.lstrip('#')
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return (*out, 1.0)


def smoothstep(a, b, x):
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    return a + (b - a) * t


# ---------------------------------------------------------------- curves

class Pchip:
    """monotone cubic interpolation through (x, y) points (x ascending); clamped outside"""

    def __init__(self, pts):
        pts = sorted(pts)
        self.x = [p[0] for p in pts]
        self.y = [p[1] for p in pts]
        n = len(pts)
        h = [self.x[i + 1] - self.x[i] for i in range(n - 1)]
        d = [(self.y[i + 1] - self.y[i]) / h[i] for i in range(n - 1)]
        m = [0.0] * n
        if n == 2:
            m = [d[0], d[0]]
        else:
            for i in range(1, n - 1):
                if d[i - 1] * d[i] <= 0:
                    m[i] = 0.0
                else:
                    w1, w2 = 2 * h[i] + h[i - 1], h[i] + 2 * h[i - 1]
                    m[i] = (w1 + w2) / (w1 / d[i - 1] + w2 / d[i])
            m[0] = self._end(h[0], h[1], d[0], d[1])
            m[-1] = self._end(h[-1], h[-2], d[-1], d[-2])
        self.h, self.d, self.m = h, d, m

    @staticmethod
    def _end(h0, h1, d0, d1):
        m = ((2 * h0 + h1) * d0 - h0 * d1) / (h0 + h1)
        if m * d0 <= 0:
            return 0.0
        if d0 * d1 <= 0 and abs(m) > abs(3 * d0):
            return 3 * d0
        return m

    def __call__(self, t):
        x, y, m = self.x, self.y, self.m
        if t <= x[0]:
            return y[0] + m[0] * (t - x[0]) * 0.0
        if t >= x[-1]:
            return y[-1]
        lo, hi = 0, len(x) - 1
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if x[mid] <= t:
                lo = mid
            else:
                hi = mid
        h = x[hi] - x[lo]
        s = (t - x[lo]) / h
        h00 = (1 + 2 * s) * (1 - s) ** 2
        h10 = s * (1 - s) ** 2
        h01 = s * s * (3 - 2 * s)
        h11 = s * s * (s - 1)
        return h00 * y[lo] + h10 * h * m[lo] + h01 * y[hi] + h11 * h * m[hi]


def catmull(pts, n, closed=False):
    """n points along a centripetal Catmull-Rom spline through 2D/3D points, spaced evenly by arc length"""
    P = [np.array(p, float) for p in pts]
    if closed:
        P = [P[-1]] + P + [P[0], P[1]]
    else:
        P = [2 * P[0] - P[1]] + P + [2 * P[-1] - P[-2]]
    dense = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        t0 = 0.0
        t1 = t0 + max(np.linalg.norm(p1 - p0), 1e-6) ** 0.5
        t2 = t1 + max(np.linalg.norm(p2 - p1), 1e-6) ** 0.5
        t3 = t2 + max(np.linalg.norm(p3 - p2), 1e-6) ** 0.5
        for k in range(24):
            t = t1 + (t2 - t1) * k / 24
            a1 = (t1 - t) / (t1 - t0) * p0 + (t - t0) / (t1 - t0) * p1
            a2 = (t2 - t) / (t2 - t1) * p1 + (t - t1) / (t2 - t1) * p2
            a3 = (t3 - t) / (t3 - t2) * p2 + (t - t2) / (t3 - t2) * p3
            b1 = (t2 - t) / (t2 - t0) * a1 + (t - t0) / (t2 - t0) * a2
            b2 = (t3 - t) / (t3 - t1) * a2 + (t - t1) / (t3 - t1) * a3
            dense.append((t2 - t) / (t2 - t1) * b1 + (t - t1) / (t2 - t1) * b2)
    dense.append(P[-2])
    D = np.array(dense)
    seg = np.linalg.norm(np.diff(D, axis=0), axis=1)
    s = np.concatenate([[0], np.cumsum(seg)])
    want = np.linspace(0, s[-1], n)
    out = np.stack([np.interp(want, s, D[:, k]) for k in range(D.shape[1])], axis=1)
    return [tuple(p) for p in out]


def arc(cx, cy, r, a0, a1, n):
    return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)), cy + r * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]


def round_poly(pts, r, seg=4):
    """a closed 2D polygon with its corners rounded (radius r, or a list of radii)"""
    n = len(pts)
    rs = r if isinstance(r, (list, tuple)) else [r] * n
    out = []
    for i in range(n):
        p0, p1, p2 = np.array(pts[i - 1], float), np.array(pts[i], float), np.array(pts[(i + 1) % n], float)
        a, b = p0 - p1, p2 - p1
        la, lb = np.linalg.norm(a), np.linalg.norm(b)
        if rs[i] <= 0 or la < 1e-9 or lb < 1e-9:
            out.append(tuple(p1))
            continue
        a, b = a / la, b / lb
        ang = math.acos(max(-1.0, min(1.0, float(a @ b))))
        t = min(rs[i] / math.tan(ang / 2), la * 0.45, lb * 0.45)
        q0, q2 = p1 + a * t, p1 + b * t
        for k in range(seg + 1):
            s = k / seg
            # quadratic Bezier through the corner (close to an arc)
            q = (1 - s) ** 2 * q0 + 2 * s * (1 - s) * p1 + s * s * q2
            out.append(tuple(q))
    return out


def inside(poly, x, y):
    c = False
    n = len(poly)
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi:
            c = not c
        j = i
    return c


def seg_dist(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    L = dx * dx + dy * dy
    t = 0.0 if L < 1e-12 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)


def poly_dist(poly, x, y, closed=True):
    n = len(poly)
    rng = range(n) if closed else range(n - 1)
    return min(seg_dist(x, y, *poly[i], *poly[(i + 1) % n]) for i in rng)


# ---------------------------------------------------------------- materials

class Materials:
    def __init__(self):
        self.mats = {}

    def add(self, name, colour, metallic=0.0, roughness=0.5, emissive=None, strength=0.0, image=None, coat=0.0):
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        p = m.node_tree.nodes.get('Principled BSDF')
        p.inputs['Base Color'].default_value = srgb(colour)
        p.inputs['Metallic'].default_value = metallic
        p.inputs['Roughness'].default_value = roughness
        if coat:
            p.inputs['Coat Weight'].default_value = coat
            p.inputs['Coat Roughness'].default_value = 0.03
        if image is not None:
            t = m.node_tree.nodes.new('ShaderNodeTexImage')
            t.image = image
            m.node_tree.links.new(t.outputs['Color'], p.inputs['Base Color'])
        if emissive:
            p.inputs['Emission Color'].default_value = srgb(emissive)
            p.inputs['Emission Strength'].default_value = strength
        self.mats[name] = m
        return m

    def __getitem__(self, k):
        return self.mats[k]


# ---------------------------------------------------------------- mesh parts

class Part:
    """a bmesh under construction in game coordinates, with material slots and a UV layer"""

    def __init__(self, name):
        self.name = name
        self.bm = bmesh.new()
        self.uv = self.bm.loops.layers.uv.new('UVMap')
        self.slots = []

    def slot(self, mat):
        if mat not in self.slots:
            self.slots.append(mat)
        return self.slots.index(mat)

    def face(self, pts, mat, smooth=True, uvs=None):
        vs = [self.bm.verts.new(B(*p)) for p in pts]
        f = self.bm.faces.new(vs)
        f.material_index = self.slot(mat)
        f.smooth = smooth
        if uvs:
            for l, uv in zip(f.loops, uvs):
                l[self.uv].uv = uv
        return f

    def grid(self, rows, mat, smooth=True, closed_u=False, flip=False, uv=None, out=None):
        """quads between consecutive rows of points (each a list of game-frame points, same length); `out` (a function
        of a face centre giving the outward direction, game frame) orients the faces"""
        vs = [[self.bm.verts.new(B(*p)) for p in r] for r in rows]
        n = len(rows[0])
        faces = []
        for j in range(len(rows) - 1):
            for i in range(n if closed_u else n - 1):
                i2 = (i + 1) % n
                q = [vs[j][i], vs[j][i2], vs[j + 1][i2], vs[j + 1][i]]
                if flip:
                    q.reverse()
                if out is not None:
                    a, b, c = (Vector(G(v.co)) for v in q[:3])
                    nrm = (b - a).cross(c - a)
                    if nrm.length < 1e-12 and len(q) > 3:
                        nrm = (c - a).cross(Vector(G(q[3].co)) - a)
                    ctr = sum((Vector(G(v.co)) for v in q), Vector()) / len(q)
                    if nrm.dot(Vector(out(ctr))) < 0:
                        q.reverse()
                try:
                    f = self.bm.faces.new(q)
                except ValueError:
                    continue
                f.material_index = self.slot(mat)
                f.smooth = smooth
                if uv:
                    for l in f.loops:
                        l[self.uv].uv = uv(G(l.vert.co))
                faces.append(f)
        return faces

    def merge(self, bm, mat=None, smooth=True, mat_of=None):
        vmap = {v: self.bm.verts.new(v.co) for v in bm.verts}
        uvl = bm.loops.layers.uv.active
        for f in bm.faces:
            try:
                nf = self.bm.faces.new([vmap[v] for v in f.verts])
            except ValueError:
                continue
            nf.material_index = self.slot(mat_of(f) if mat_of else mat)
            nf.smooth = smooth if smooth is not None else f.smooth
            if uvl is not None:
                for l0, l1 in zip(f.loops, nf.loops):
                    l1[self.uv].uv = l0[uvl].uv
        bm.free()

    def box(self, mat, x0, x1, y0, y1, z0, z1, bevel=0.0, seg=2, smooth=None):
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        for v in bm.verts:
            v.co = B(lerp(x0, x1, v.co.x + 0.5), lerp(y0, y1, v.co.y + 0.5), lerp(z0, z1, v.co.z + 0.5))
        if bevel > 0:
            bmesh.ops.bevel(bm, geom=list(bm.edges), offset=min(bevel, abs(x1 - x0) / 2.01, abs(y1 - y0) / 2.01, abs(z1 - z0) / 2.01),
                            segments=seg, profile=0.5, affect='EDGES', clamp_overlap=True)
        self.merge(bm, mat, smooth=(bevel > 0) if smooth is None else smooth)

    def oriented_box(self, mat, centre, size, rot=(0, 0, 0), bevel=0.0, seg=2):
        """a box (size w, h, l along game x, y, z) rotated by (rx, ry, rz) radians about game axes (x, then y, then z)"""
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        if bevel > 0:
            bmesh.ops.scale(bm, vec=(size[0], size[2], size[1]), verts=bm.verts)
            bmesh.ops.bevel(bm, geom=list(bm.edges), offset=min(bevel, min(size) / 2.01), segments=seg, profile=0.5,
                            affect='EDGES', clamp_overlap=True)
        else:
            bmesh.ops.scale(bm, vec=(size[0], size[2], size[1]), verts=bm.verts)
        M = game_rot(*rot)
        for v in bm.verts:
            gx, gy, gz = G(v.co)
            p = M @ Vector((gx, gy, gz)) + Vector(centre)
            v.co = B(*p)
        self.merge(bm, mat, smooth=bevel > 0)

    def cylinder(self, mat, centre, r, length, axis='x', seg=16, cap=True, r2=None, smooth=True):
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=cap, cap_tris=False, segments=seg, radius1=r, radius2=r if r2 is None else r2, depth=length)
        rot = {'y': Matrix.Identity(4), 'x': Matrix.Rotation(math.pi / 2, 4, 'Y'), 'z': Matrix.Rotation(math.pi / 2, 4, 'X')}[axis]
        bmesh.ops.transform(bm, matrix=Matrix.Translation(B(*centre)) @ rot, verts=bm.verts)
        self.merge(bm, mat, smooth=smooth)
        # flat caps: mark their faces flat
        return

    def revolve(self, mat, profile, centre, axis='x', seg=32, smooth=True, cap0=False, cap1=False, mat_of=None, phase=0.0,
                twist=None):
        """revolve a profile [(r, a)] (radius, position along the axis) about a game axis through centre"""
        rows = []
        for i in range(seg):
            t = 2 * math.pi * i / seg + phase
            row = []
            for k, (r, a) in enumerate(profile):
                tt = t + (twist(k, r) if twist else 0.0)
                c, s = math.cos(tt), math.sin(tt)
                if axis == 'x':
                    p = (centre[0] + a, centre[1] + r * c, centre[2] + r * s)
                elif axis == 'z':
                    p = (centre[0] + r * c, centre[1] + r * s, centre[2] + a)
                else:
                    p = (centre[0] + r * c, centre[1] + a, centre[2] + r * s)
                row.append(p)
            rows.append(row)
        vs = [[self.bm.verts.new(B(*p)) for p in r] for r in rows]
        faces = []
        for i in range(seg):
            i2 = (i + 1) % seg
            for k in range(len(profile) - 1):
                q = [vs[i][k], vs[i][k + 1], vs[i2][k + 1], vs[i2][k]]
                try:
                    f = self.bm.faces.new(q)
                except ValueError:
                    continue
                f.material_index = self.slot(mat_of(k) if mat_of else mat)
                f.smooth = smooth
                faces.append(f)
        for cap, k in ((cap0, 0), (cap1, len(profile) - 1)):
            if cap:
                ring = [vs[i][k] for i in range(seg)]
                try:
                    f = self.bm.faces.new(ring if k else list(reversed(ring)))
                    f.material_index = self.slot(cap if isinstance(cap, str) else (mat_of(k) if mat_of else mat))
                    f.smooth = False
                except ValueError:
                    pass
        return faces

    def tris(self):
        return sum(len(f.verts) - 2 for f in self.bm.faces)

    def orient(self, centre=None, outward=None):
        """recalculate normals so they point outwards"""
        bmesh.ops.recalc_face_normals(self.bm, faces=self.bm.faces)

    def build(self, parent, mats, name=None):
        bmesh.ops.remove_doubles(self.bm, verts=self.bm.verts, dist=1e-6)
        me = bpy.data.meshes.new(name or self.name)
        self.bm.normal_update()
        self.bm.to_mesh(me)
        self.bm.free()
        for m in self.slots:
            me.materials.append(mats[m])
        o = bpy.data.objects.new(name or self.name, me)
        bpy.context.scene.collection.objects.link(o)
        o.parent = parent
        return o


def game_rot(rx, ry, rz):
    """rotation matrix about game axes: x, then y, then z"""
    cx, sx, cy, sy, cz, sz = math.cos(rx), math.sin(rx), math.cos(ry), math.sin(ry), math.cos(rz), math.sin(rz)
    Rx = Matrix(((1, 0, 0), (0, cx, -sx), (0, sx, cx)))
    Ry = Matrix(((cy, 0, sy), (0, 1, 0), (-sy, 0, cy)))
    Rz = Matrix(((cz, -sz, 0), (sz, cz, 0), (0, 0, 1)))
    return Rz @ Ry @ Rx


def tris_of(obj):
    return sum(len(p.vertices) - 2 for p in obj.data.polygons)


# ---------------------------------------------------------------- cutting outlines into the body

PROJ = {
    # (u axis, v axis, view axis) in game coordinates: u, v span the drawing plane, the view looks along -w
    'side': (2, 1, 0),     # u = z, v = y, seen from +x (the left side)
    'front': (0, 1, 2),    # u = x, v = y, seen from +z
    'rear': (0, 1, 2),     # u = x, v = y, seen from -z
    'top': (0, 2, 1),      # u = x, v = z, seen from above
}


def _uv(co, proj):
    g = G(co)
    a, b, _ = PROJ[proj]
    return g[a], g[b]


def _facing(f, proj, side):
    n = G(f.normal)
    w = PROJ[proj][2]
    return n[w] * side


def _bbox_uv(f, proj):
    us = [_uv(v.co, proj) for v in f.verts]
    return min(p[0] for p in us), max(p[0] for p in us), min(p[1] for p in us), max(p[1] for p in us)


def cut_outline(bm, poly, proj, side=1, keep=None, margin=0.03, closed=True, min_facing=0.05):
    """
    Cut the edges of a 2D polygon (drawn in a projection plane) into the faces of `bm` that face the viewer
    (normal along the view axis × `side` > min_facing) and pass `keep(face)`. Each polygon edge is a plane through the
    edge, extruded along the view axis.
    """
    a, b, w = PROJ[proj]
    n = len(poly)
    us_ = [p[0] for p in poly]
    vs_ = [p[1] for p in poly]
    lo_u, hi_u, lo_v, hi_v = min(us_) - margin, max(us_) + margin, min(vs_) - margin, max(vs_) + margin
    cand = set()
    for f in bm.faces:
        if _facing(f, proj, side) <= min_facing or (keep is not None and not keep(f)):
            continue
        u0, u1, v0, v1 = _bbox_uv(f, proj)
        if u1 < lo_u or u0 > hi_u or v1 < lo_v or v0 > hi_v:
            continue
        cand.add(f)
    rng = range(n) if closed else range(n - 1)
    for i in rng:
        (u0, v0), (u1, v1) = poly[i], poly[(i + 1) % n]
        du, dv = u1 - u0, v1 - v0
        L = math.hypot(du, dv)
        if L < 1e-6:
            continue
        eu0, eu1 = min(u0, u1) - margin, max(u0, u1) + margin
        ev0, ev1 = min(v0, v1) - margin, max(v0, v1) + margin
        geom = []
        for f in cand:
            if not f.is_valid:
                continue
            fu0, fu1, fv0, fv1 = _bbox_uv(f, proj)
            if fu1 < eu0 or fu0 > eu1 or fv1 < ev0 or fv0 > ev1:
                continue
            geom.append(f)
        if not geom:
            continue
        edges = {e for f in geom for e in f.edges}
        verts = {v for f in geom for v in f.verts}
        co = [0.0, 0.0, 0.0]
        co[a], co[b] = u0, v0
        no = [0.0, 0.0, 0.0]
        no[a], no[b] = -dv / L, du / L
        res = bmesh.ops.bisect_plane(bm, geom=list(verts) + list(edges) + geom, dist=1e-6, plane_co=B(*co), plane_no=B(*no) - B(0, 0, 0))
        for g in res['geom']:
            if isinstance(g, bmesh.types.BMFace):
                cand.add(g)
    bm.faces.ensure_lookup_table()


def offset_poly(poly, d):
    """a closed 2D polygon offset by d (positive = outwards for a counter-clockwise polygon)"""
    n = len(poly)
    area = sum(poly[i][0] * poly[(i + 1) % n][1] - poly[(i + 1) % n][0] * poly[i][1] for i in range(n))
    sgn = 1.0 if area > 0 else -1.0
    out = []
    for i in range(n):
        p0, p1, p2 = np.array(poly[i - 1], float), np.array(poly[i], float), np.array(poly[(i + 1) % n], float)
        t0, t1 = p1 - p0, p2 - p1
        t0 = t0 / max(1e-9, np.linalg.norm(t0))
        t1 = t1 / max(1e-9, np.linalg.norm(t1))
        n0 = np.array([t0[1], -t0[0]]) * sgn
        n1 = np.array([t1[1], -t1[0]]) * sgn
        m = n0 + n1
        lm = np.linalg.norm(m)
        if lm < 1e-6:
            m = n0
        else:
            m = m / lm
        c = max(0.35, float(m @ n0))
        out.append(tuple(p1 + m * d / c))
    return out


def faces_in(bm, poly, proj, side=1, keep=None, min_facing=0.05):
    out = []
    for f in bm.faces:
        if _facing(f, proj, side) <= min_facing:
            continue
        if keep is not None and not keep(f):
            continue
        u, v = _uv(f.calc_center_median(), proj)
        if inside(poly, u, v):
            out.append(f)
    return out


def region(bm, poly, proj, side=1, keep=None, min_facing=0.05, margin=0.03):
    """cut a polygon's outline and return the faces inside it"""
    cut_outline(bm, poly, proj, side, keep, margin, min_facing=min_facing)
    return faces_in(bm, poly, proj, side, keep, min_facing)


def offset_line(pts, d):
    """a 2D polyline offset sideways by d (left of the direction of travel)"""
    out = []
    n = len(pts)
    for i in range(n):
        p = np.array(pts[i], float)
        t0 = np.array(pts[i], float) - np.array(pts[i - 1], float) if i > 0 else None
        t1 = np.array(pts[i + 1], float) - p if i < n - 1 else None
        ts = [t / np.linalg.norm(t) for t in (t0, t1) if t is not None and np.linalg.norm(t) > 1e-9]
        t = sum(ts)
        t = t / np.linalg.norm(t)
        nrm = np.array([-t[1], t[0]])
        # keep the offset distance at corners
        scale = 1.0
        if len(ts) == 2:
            c = float(ts[0] @ ts[1])
            scale = 1 / max(0.35, math.sqrt((1 + c) / 2))
        out.append(tuple(p + nrm * d * scale))
    return out


def groove(bm, line, proj, width=0.004, side=1, keep=None, min_facing=0.05, closed=False):
    """cut a thin strip along a 2D polyline; returns its faces (shut lines)"""
    pts = list(line) + ([line[0]] if closed else [])
    for d in (-width / 2, width / 2):
        cut_outline(bm, offset_line(pts, d), proj, side, keep, margin=0.02, closed=False, min_facing=min_facing)
    out = []
    for f in bm.faces:
        if _facing(f, proj, side) <= min_facing:
            continue
        if keep is not None and not keep(f):
            continue
        u, v = _uv(f.calc_center_median(), proj)
        if poly_dist(pts, u, v, closed=False) < width / 2 * 1.02:
            out.append(f)
    return out


def sink(bm, faces, depth):
    """push the vertices of faces inwards along their normals (shut lines, recesses)"""
    vs = {v for f in faces for v in f.verts}
    for v in vs:
        v.co -= v.normal * depth


# ---------------------------------------------------------------- export and the check scene

def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def empty(name, loc=(0, 0, 0), parent=None):
    e = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(e)
    e.location = B(*loc)
    e.parent = parent
    return e


def export_glb(path, root):
    bpy.ops.object.select_all(action='DESELECT')
    root.select_set(True)
    for c in root.children_recursive:
        c.select_set(True)
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', use_selection=True, export_yup=True, export_apply=True,
                              export_materials='EXPORT', export_extras=True, export_cameras=False, export_lights=False,
                              export_image_format='AUTO')


def scene(night=False, sun_elev=40.0, ground='#3a3a3c'):
    sc = bpy.context.scene
    world = sc.world or bpy.data.worlds.new('sky')
    sc.world = world
    world.use_nodes = True
    nt = world.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    bg = nt.nodes.new('ShaderNodeBackground')
    out = nt.nodes.new('ShaderNodeOutputWorld')
    if night:
        bg.inputs['Color'].default_value = (0.006, 0.008, 0.016, 1)
        bg.inputs['Strength'].default_value = 1.0
        nt.links.new(bg.outputs['Background'], out.inputs['Surface'])
    else:
        sky = nt.nodes.new('ShaderNodeTexSky')
        for kind in ('MULTIPLE_SCATTERING', 'NISHITA'):
            try:
                sky.sky_type = kind
                break
            except TypeError:
                continue
        sky.sun_elevation = math.radians(sun_elev)
        try:
            sky.sun_disc = False
        except AttributeError:
            pass
        bg.inputs['Strength'].default_value = 0.18
        nt.links.new(sky.outputs['Color'], bg.inputs['Color'])
        nt.links.new(bg.outputs['Background'], out.inputs['Surface'])
        sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN'))
        sun.data.energy = 4.0
        sun.data.angle = math.radians(1.0)
        sun.rotation_euler = (math.radians(90 - sun_elev), 0, math.radians(-130))
        sc.collection.objects.link(sun)
    # asphalt
    m = bpy.data.materials.new('sc_asphalt')
    m.use_nodes = True
    ntm = m.node_tree
    p = ntm.nodes['Principled BSDF']
    noise = ntm.nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 400.0
    ramp = ntm.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = srgb('#2a2a2b' if not night else '#141416')
    ramp.color_ramp.elements[1].color = srgb(ground if not night else '#1d1d20')
    ntm.links.new(noise.outputs['Fac'], ramp.inputs['Fac'])
    ntm.links.new(ramp.outputs['Color'], p.inputs['Base Color'])
    p.inputs['Roughness'].default_value = 0.85
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=60)
    me = bpy.data.meshes.new('ground')
    bm.to_mesh(me)
    me.materials.append(m)
    g = bpy.data.objects.new('ground', me)
    sc.collection.objects.link(g)
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.use_denoising = True
    sc.render.threads_mode = 'FIXED'
    sc.render.threads = 4
    vs = sc.view_settings
    try:
        vs.view_transform = 'Khronos PBR Neutral'
    except TypeError:
        vs.view_transform = 'Filmic'
    vs.exposure = -0.4 if not night else 0.0
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.data.clip_start = 0.05
    cam.data.clip_end = 300


def sun_from(eye, target, offset=40.0, elev=None):
    sun = bpy.data.objects.get('sun')
    if sun is None:
        return
    dx, dz = eye[0] - target[0], eye[2] - target[2]
    theta = math.atan2(dx, dz) + math.radians(offset)
    sun.rotation_euler = (sun.rotation_euler[0] if elev is None else math.radians(90 - elev), 0, theta)
    sky = bpy.context.scene.world.node_tree.nodes.get('Sky Texture')
    if sky is not None:
        sky.sun_rotation = theta + math.pi / 2


def render_cam(cam, path, samples=8, transparent=True):
    """render from a solved photo camera {eye, target, up, lens, size} (game frame), optionally without the ground"""
    sc = bpy.context.scene
    c = sc.camera
    f = (Vector(cam['target']) - Vector(cam['eye'])).normalized()
    u = Vector(cam['up']).normalized()
    fb, ub = B(*f) - B(0, 0, 0), B(*u) - B(0, 0, 0)
    rb = fb.cross(ub)
    M = Matrix((rb, ub, -fb)).transposed()
    c.matrix_world = Matrix.Translation(B(*cam['eye'])) @ M.to_4x4()
    c.data.lens = cam['lens']
    c.data.sensor_width = 36.0
    c.data.sensor_fit = 'HORIZONTAL'
    c.data.shift_x = c.data.shift_y = 0.0
    g = bpy.data.objects.get('ground')
    if g is not None:
        g.hide_render = transparent
    sc.render.film_transparent = transparent
    sc.cycles.samples = samples
    sc.render.resolution_x, sc.render.resolution_y = cam['size']
    sc.render.resolution_percentage = 100
    sc.render.filepath = path
    sun_from(cam['eye'], cam['target'], 40.0)
    bpy.ops.render.render(write_still=True)
    if g is not None:
        g.hide_render = False
    sc.render.film_transparent = False


def render(view, path, size=(1280, 720), samples=32, sun_offset=40.0, sensor=36.0, shift=(0.0, 0.0), roll=0.0):
    sc = bpy.context.scene
    eye, target, lens = view
    if sun_offset is not None:
        sun_from(eye, target, sun_offset)
    cam = sc.camera
    cam.location = B(*eye)
    q = (B(*target) - B(*eye)).to_track_quat('-Z', 'Y')
    if roll:
        q = q @ Matrix.Rotation(roll, 4, 'Z').to_quaternion()
    cam.rotation_euler = q.to_euler()
    cam.data.lens = lens
    cam.data.sensor_width = sensor
    cam.data.sensor_fit = 'HORIZONTAL'
    cam.data.shift_x, cam.data.shift_y = shift
    sc.cycles.samples = samples
    sc.render.resolution_x, sc.render.resolution_y = size
    sc.render.resolution_percentage = 100
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
