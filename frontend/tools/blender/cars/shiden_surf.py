"""
Surface tools for the shiden (Mazda RX-7 FD3S) build: an interpolating spline surface through a grid of key points,
the mirrored body shell made from it, and trims (splitting the shell along an outline seen along an axis, to cut the
wheel arches and openings or to give the glass its own faces), shut-line ribbons and decals laid on the shell.

Game car frame throughout: metres, +x = the car's left, +y up (0 = ground), +z forward. `B()` turns a game point into
Blender's frame (the glTF exporter's +Y up gives the game's axes back).
"""
import math

import bmesh
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree


def B(x, y, z):
    return Vector((x, -z, y))


def G(v):
    return v[0], v[2], -v[1]


# ---------------------------------------------------------------- 1-D interpolation


def pchip(xk, yk):
    """monotone cubic through (xk, yk) (Fritsch–Carlson): no overshoot between key frames"""
    xk = np.asarray(xk, float)
    yk = np.asarray(yk, float)
    h = np.diff(xk)
    d = np.diff(yk) / h
    m = np.zeros_like(yk)
    for i in range(1, len(xk) - 1):
        if d[i - 1] * d[i] <= 0:
            m[i] = 0.0
        else:
            w1, w2 = 2 * h[i] + h[i - 1], h[i] + 2 * h[i - 1]
            m[i] = (w1 + w2) / (w1 / d[i - 1] + w2 / d[i])
    m[0] = d[0] if len(d) else 0.0
    m[-1] = d[-1] if len(d) else 0.0

    def f(x):
        x = np.asarray(x, float)
        xc = np.clip(x, xk[0], xk[-1])
        i = np.clip(np.searchsorted(xk, xc) - 1, 0, len(xk) - 2)
        t = (xc - xk[i]) / h[i]
        h00 = (1 + 2 * t) * (1 - t) ** 2
        h10 = t * (1 - t) ** 2
        h01 = t * t * (3 - 2 * t)
        h11 = t * t * (t - 1)
        return h00 * yk[i] + h10 * h[i] * m[i] + h01 * yk[i + 1] + h11 * h[i] * m[i + 1]
    return f


def table(keys):
    """{name: [(z, value), ...]} → {name: f(z)}"""
    out = {}
    for k, pts in keys.items():
        pts = sorted(pts)
        out[k] = pchip([p[0] for p in pts], [p[1] for p in pts])
    return out


# ---------------------------------------------------------------- Catmull–Rom curves


def _cr(p0, p1, p2, p3, ts, alpha=0.5):
    """centripetal Catmull–Rom between p1 and p2 at the fractions ts (Barry–Goldman)"""
    eps = 1e-9

    def knot(a, b):
        return max(float(np.linalg.norm(b - a)) ** alpha, eps)

    if np.linalg.norm(p2 - p1) < 1e-9:
        return [p1.copy() for _ in ts]
    t0 = 0.0
    t1 = t0 + knot(p0, p1)
    t2 = t1 + knot(p1, p2)
    t3 = t2 + knot(p2, p3)
    out = []
    for f in ts:
        t = t1 + (t2 - t1) * f
        a1 = (t1 - t) / (t1 - t0) * p0 + (t - t0) / (t1 - t0) * p1
        a2 = (t2 - t) / (t2 - t1) * p1 + (t - t1) / (t2 - t1) * p2
        a3 = (t3 - t) / (t3 - t2) * p2 + (t - t2) / (t3 - t2) * p3
        b1 = (t2 - t) / (t2 - t0) * a1 + (t - t0) / (t2 - t0) * a2
        b2 = (t3 - t) / (t3 - t1) * a2 + (t - t1) / (t3 - t1) * a3
        out.append((t2 - t) / (t2 - t1) * b1 + (t - t1) / (t2 - t1) * b2)
    return out


def curve(pts, counts, start=None, end=None):
    """
    A dense polyline through `pts` (n × d), segment i split into counts[i] steps. `start` / `end`: the phantom points
    beyond the ends ('mirror_x' = the neighbour mirrored in x = 0, so the curve crosses the centre line square;
    'line' = straight on; or an explicit point).
    """
    pts = [np.asarray(p, float) for p in pts]
    n = len(pts)

    def phantom(kind, a, b):
        if kind is None or kind == 'line':
            return 2 * a - b
        if kind == 'mirror_x':
            m = b.copy()
            m[0] = -m[0]
            return m
        return np.asarray(kind, float)

    ext = [phantom(start, pts[0], pts[1])] + pts + [phantom(end, pts[-1], pts[-2])]
    out = [pts[0]]
    for i in range(n - 1):
        c = counts[i] if hasattr(counts, '__len__') else counts
        ts = [s / c for s in range(1, c + 1)]
        out += _cr(ext[i], ext[i + 1], ext[i + 2], ext[i + 3], ts)
    return np.array(out)


def surface(K, sub_j, sub_k, ends_j=(None, None), ends_k=('mirror_x', 'mirror_x')):
    """
    Interpolating surface through the key grid K (J stations × N rails × 3): along each rail first, then across each
    dense station. Returns the dense grid (J' × N' × 3).
    """
    K = np.asarray(K, float)
    J, N, _ = K.shape
    rails = [curve(K[:, k], sub_j, *ends_j) for k in range(N)]
    rails = np.stack(rails, axis=1)          # J' × N × 3
    rows = [curve(rails[j], sub_k, *ends_k) for j in range(rails.shape[0])]
    return np.stack(rows, axis=0)


# ---------------------------------------------------------------- meshes


class Mesh:
    """faces in the game frame with material names; welded on build"""

    def __init__(self, name):
        self.name = name
        self.bm = bmesh.new()
        self.slots = []
        self.uv = None

    def slot(self, mat):
        if mat not in self.slots:
            self.slots.append(mat)
        return self.slots.index(mat)

    def uv_layer(self):
        if self.uv is None:
            self.uv = self.bm.loops.layers.uv.new('UVMap')
        return self.uv

    def face(self, pts, mat, smooth=True, uvs=None, out=None):
        if out is not None:
            a, b, c = (Vector(p) for p in pts[:3])
            nrm = (b - a).cross(c - a)
            if len(pts) > 3 and nrm.length < 1e-12:
                nrm = (c - a).cross(Vector(pts[3]) - a)
            if nrm.dot(Vector(out)) < 0:
                pts = list(reversed(pts))
                if uvs is not None:
                    uvs = list(reversed(uvs))
        vs = [self.bm.verts.new(B(*p)) for p in pts]
        try:
            f = self.bm.faces.new(vs)
        except ValueError:
            return None
        f.material_index = self.slot(mat)
        f.smooth = smooth
        if uvs is not None:
            lay = self.uv_layer()
            for loop, uv in zip(f.loops, uvs):
                loop[lay].uv = uv
        return f

    def grid(self, P, mat, smooth=True, closed_u=False, flip=False, uv=None):
        """quads over a grid of game points P (nu × nv × 3); uv: optional (nu × nv × 2)"""
        nu, nv = P.shape[0], P.shape[1]
        vs = [[self.bm.verts.new(B(*P[i, j])) for j in range(nv)] for i in range(nu)]
        idx = self.slot(mat)
        lay = self.uv_layer() if uv is not None else None
        rng = range(nu if closed_u else nu - 1)
        for i in rng:
            i2 = (i + 1) % nu
            for j in range(nv - 1):
                q = [vs[i][j], vs[i2][j], vs[i2][j + 1], vs[i][j + 1]]
                qi = [(i, j), (i2, j), (i2, j + 1), (i, j + 1)]
                if flip:
                    q.reverse()
                    qi.reverse()
                # drop collapsed corners (poles)
                seen, qq, qqi = [], [], []
                for v, ij in zip(q, qi):
                    if all((v.co - s.co).length > 1e-7 for s in seen):
                        seen.append(v)
                        qq.append(v)
                        qqi.append(ij)
                if len(qq) < 3:
                    continue
                try:
                    f = self.bm.faces.new(qq)
                except ValueError:
                    continue
                f.material_index = idx
                f.smooth = smooth
                if lay is not None:
                    for loop, (a, b) in zip(f.loops, qqi):
                        loop[lay].uv = tuple(uv[a, b])
        return vs

    def merge_bm(self, bm, mat=None, smooth=None):
        """append another bmesh (its faces keep their material index → our slot via `mat` if given)"""
        idx = self.slot(mat) if mat is not None else None
        vmap = {v: self.bm.verts.new(v.co) for v in bm.verts}
        for f in bm.faces:
            try:
                nf = self.bm.faces.new([vmap[v] for v in f.verts])
            except ValueError:
                continue
            nf.material_index = idx if idx is not None else f.material_index
            nf.smooth = f.smooth if smooth is None else smooth
        bm.free()

    def tris(self):
        return sum(len(f.verts) - 2 for f in self.bm.faces)

    def build(self, parent, mats, weld=1e-5, sharp=None):
        if weld:
            bmesh.ops.remove_doubles(self.bm, verts=self.bm.verts, dist=weld)
        self.bm.normal_update()
        if sharp is not None:
            for e in self.bm.edges:
                if len(e.link_faces) == 2:
                    f1, f2 = e.link_faces
                    if f1.normal.angle(f2.normal, 0.0) > math.radians(sharp) or f1.material_index != f2.material_index:
                        e.smooth = False
        me = bpy.data.meshes.new(self.name)
        self.bm.to_mesh(me)
        self.bm.free()
        for m in self.slots:
            me.materials.append(mats[m])
        obj = bpy.data.objects.new(self.name, me)
        bpy.context.scene.collection.objects.link(obj)
        obj.parent = parent
        return obj


# ---------------------------------------------------------------- 2-D outlines


def rounded_rect(cx, cy, w, h, r, seg=6):
    r = min(r, w / 2, h / 2)
    pts = []
    for ox, oy, a0 in ((cx + w / 2 - r, cy + h / 2 - r, 0), (cx - w / 2 + r, cy + h / 2 - r, 90),
                       (cx - w / 2 + r, cy - h / 2 + r, 180), (cx + w / 2 - r, cy - h / 2 + r, 270)):
        for s in range(seg + 1):
            a = math.radians(a0 + 90 * s / seg)
            pts.append((ox + r * math.cos(a), oy + r * math.sin(a)))
    return pts


def smooth_outline(pts, per=8, closed=True):
    """a closed Catmull–Rom outline through 2-D points"""
    P = [np.asarray(p, float) for p in pts]
    n = len(P)
    out = []
    for i in range(n if closed else n - 1):
        p0, p1, p2, p3 = P[(i - 1) % n], P[i], P[(i + 1) % n], P[(i + 2) % n]
        out += [tuple(q) for q in _cr(p0, p1, p2, p3, [s / per for s in range(per)])]
    return out


def resample(poly, step, closed=True):
    """evenly spaced points along a polyline"""
    P = np.asarray(poly, float)
    if closed:
        P = np.vstack([P, P[:1]])
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
    s = np.concatenate([[0], np.cumsum(seg)])
    n = max(3, int(s[-1] / step))
    t = np.linspace(0, s[-1], n, endpoint=not closed)
    return np.stack([np.interp(t, s, P[:, i]) for i in range(P.shape[1])], axis=1)


def inside(poly, px, py):
    """point in polygon (even–odd)"""
    n = len(poly)
    c = False
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > py) != (yj > py) and px < (xj - xi) * (py - yi) / (yj - yi + 1e-30) + xi:
            c = not c
        j = i
    return c


def nearest_on(poly, p):
    best, bd = None, 1e9
    n = len(poly)
    px, py = p
    for i in range(n):
        ax, ay = poly[i]
        bx, by = poly[(i + 1) % n]
        dx, dy = bx - ax, by - ay
        L = dx * dx + dy * dy
        t = 0.0 if L < 1e-18 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L))
        qx, qy = ax + t * dx, ay + t * dy
        d = (qx - px) ** 2 + (qy - py) ** 2
        if d < bd:
            bd, best = d, (qx, qy)
    return best


# projections: axis → (u index, v index, depth index) in the game frame
AXES = {'x': (2, 1, 0), 'y': (0, 2, 1), 'z': (0, 1, 2)}


def _uv(co_game, axis):
    a, b, _ = AXES[axis]
    return co_game[a], co_game[b]


class Shell:
    """the body shell as a bmesh in Blender's frame, with a BVH of its untrimmed surface for re-projection"""

    def __init__(self, mesh):
        self.mesh = mesh
        self.bm = mesh.bm
        self.bm.normal_update()
        self.bvh = BVHTree.FromBMesh(self.bm)

    def faces_where(self, pred):
        return [f for f in self.bm.faces if pred(f)]

    def split(self, outline, axis, side, select, mat=None, delete=False, snap=True, max_snap=0.05):
        """
        Split the shell along `outline` (2-D, in the plane across `axis`, e.g. 'x' → (z, y)) on the faces that
        `select(face, centre_game, normal_game)` accepts: faces inside get `mat` (or are deleted); the vertices on the
        border are moved onto the outline and back onto the surface (seen from `side` = +1 / −1 along the axis).
        Returns the faces inside (if kept).
        """
        a_u, a_v, a_d = AXES[axis]
        poly = [tuple(p) for p in outline]
        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        bx0, bx1, by0, by1 = min(xs), max(xs), min(ys), max(ys)
        inner = []
        for f in self.bm.faces:
            c = G(f.calc_center_median())
            u, v = c[a_u], c[a_v]
            if u < bx0 or u > bx1 or v < by0 or v > by1:
                continue
            n = G(f.normal)
            if not select(f, c, n):
                continue
            if inside(poly, u, v):
                inner.append(f)
        inset = set(inner)
        if snap:
            border = set()
            for f in inner:
                for e in f.edges:
                    others = [g for g in e.link_faces if g is not f]
                    if not others or any(g not in inset for g in others):
                        border.update(e.verts)
            for vtx in border:
                if not any(g not in inset for g in vtx.link_faces):
                    continue
                c = list(G(vtx.co))
                q = nearest_on(poly, (c[a_u], c[a_v]))
                if math.hypot(q[0] - c[a_u], q[1] - c[a_v]) > max_snap:
                    continue
                c[a_u], c[a_v] = q
                # back onto the surface: cast along the axis from outside on `side`
                origin = list(c)
                origin[a_d] = c[a_d] + side * 0.25
                d = [0.0, 0.0, 0.0]
                d[a_d] = -side
                loc, _, _, _ = self.bvh.ray_cast(B(*origin), B(*d) - B(0, 0, 0), 0.6)
                if loc is not None:
                    vtx.co = loc
                else:
                    vtx.co = B(*c)
        if delete:
            bmesh.ops.delete(self.bm, geom=inner, context='FACES')
            return []
        if mat is not None:
            idx = self.mesh.slot(mat)
            for f in inner:
                f.material_index = idx
        return inner

    def hit(self, origin, direction, dist=10.0):
        loc, nrm, _, _ = self.bvh.ray_cast(B(*origin), B(*direction) - B(0, 0, 0), dist)
        if loc is None:
            return None
        return np.array(G(loc)), np.array(G(nrm))


def lay_on(shell, pts2, axis, side, lift=0.0):
    """2-D points in the plane across `axis` → points on the shell seen from `side`, `lift` m off it"""
    a_u, a_v, a_d = AXES[axis]
    out = []
    for u, v in pts2:
        o = [0.0, 0.0, 0.0]
        o[a_u], o[a_v], o[a_d] = u, v, side * 5.0
        d = [0.0, 0.0, 0.0]
        d[a_d] = -side
        h = shell.hit(o, d)
        if h is None:
            out.append(None)
            continue
        p, n = h
        if np.dot(n, d) > 0:
            n = -n
        out.append(p + n * lift)
    return out


def ribbon(mesh, shell, poly, axis, side, mat, width=0.004, lift=0.0015, closed=True, step=0.01):
    """a thin strip laid along a 2-D polyline on the shell (shut lines)"""
    P = resample(poly, step, closed)
    pts = lay_on(shell, P, axis, side, 0.0)
    n = len(pts)
    rng = range(n if closed else n - 1)
    a_u, a_v, a_d = AXES[axis]
    for i in rng:
        p0, p1 = pts[i], pts[(i + 1) % n]
        if p0 is None or p1 is None:
            continue
        h0 = shell.hit(tuple(np.array(p0) + _axis_vec(a_d) * side * 0.05), tuple(-_axis_vec(a_d) * side))
        nrm = h0[1] if h0 is not None else _axis_vec(a_d) * side
        if np.dot(nrm, _axis_vec(a_d) * side) < 0:
            nrm = -nrm
        t = np.array(p1) - np.array(p0)
        L = np.linalg.norm(t)
        if L < 1e-6:
            continue
        t /= L
        w = np.cross(nrm, t)
        w /= max(np.linalg.norm(w), 1e-9)
        q = [np.array(p0) - w * width / 2 + nrm * lift, np.array(p1) - w * width / 2 + nrm * lift,
             np.array(p1) + w * width / 2 + nrm * lift, np.array(p0) + w * width / 2 + nrm * lift]
        mesh.face([tuple(x) for x in q], mat, smooth=False, out=tuple(nrm))


def _axis_vec(i):
    v = np.zeros(3)
    v[i] = 1.0
    return v


def patch(mesh, shell, outline, axis, side, mat, lift=0.002, rings=5, uv_box=None, smooth=True):
    """
    A decal plate filling a closed 2-D outline, laid on the shell (concentric rings to the centroid). uv_box =
    (u0, u1, v0, v1) maps the outline plane to texture coordinates.
    """
    poly = np.asarray(outline, float)
    c = poly.mean(axis=0)
    rings_pts = [[tuple(c + (p - c) * (k / rings)) for p in poly] for k in range(1, rings + 1)]
    laid = [lay_on(shell, r, axis, side, lift) for r in rings_pts]
    centre = lay_on(shell, [tuple(c)], axis, side, lift)[0]
    n = len(poly)
    a_u, a_v, a_d = AXES[axis]
    out = _axis_vec(a_d) * side

    def uvof(p2):
        if uv_box is None:
            return None
        u0, u1, v0, v1 = uv_box
        return ((p2[0] - u0) / (u1 - u0), (p2[1] - v0) / (v1 - v0))

    def put(pts3, pts2):
        if any(p is None for p in pts3):
            return
        uvs = [uvof(p) for p in pts2] if uv_box is not None else None
        mesh.face([tuple(p) for p in pts3], mat, smooth=smooth, uvs=uvs, out=tuple(out))

    for k in range(n):
        k2 = (k + 1) % n
        put([centre, laid[0][k], laid[0][k2]], [tuple(c), rings_pts[0][k], rings_pts[0][k2]])
        for j in range(rings - 1):
            put([laid[j][k], laid[j + 1][k], laid[j + 1][k2], laid[j][k2]],
                [rings_pts[j][k], rings_pts[j + 1][k], rings_pts[j + 1][k2], rings_pts[j][k2]])
