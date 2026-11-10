"""
Building blocks for the fighter aircraft of TOUGE NOCTURNE (f15c, f15j, su47) and their pilots: coordinates, curves,
materials, mesh parts (lofts, tubes, revolves, wings), graphics cut into surfaces, decals, the node tree, the GLB export.
(After bikes/bike_kit.py.)

Game frame: metres, +x = the aircraft's left, +y up (0 = ground), +z forward (the nose), origin on the ground midway
between the nose wheel's contact point and the main wheels' contact line. Blender frame: (x, -z, y), so the glTF
exporter (+Y up) gives the game frame back.
"""
import math

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree


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
    if b == a:
        return 1.0 if x >= a else 0.0
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    return a + (b - a) * t


def V(*a):
    return np.array(a[0] if len(a) == 1 else a, float)


def unit(v):
    v = np.asarray(v, float)
    n = np.linalg.norm(v)
    return v / n if n > 1e-12 else v


# ---------------------------------------------------------------- curves

class Pchip:
    """monotone cubic through (t, v) points; clamped outside"""

    def __init__(self, pts):
        pts = sorted(pts)
        self.t = [p[0] for p in pts]
        self.v = [p[1] for p in pts]
        n = len(pts)
        h = [self.t[i + 1] - self.t[i] for i in range(n - 1)]
        d = [(self.v[i + 1] - self.v[i]) / h[i] for i in range(n - 1)]
        m = [0.0] * n
        if n == 2:
            m = [d[0], d[0]]
        else:
            m[0], m[-1] = d[0], d[-1]
            for i in range(1, n - 1):
                if d[i - 1] * d[i] <= 0:
                    m[i] = 0.0
                else:
                    w1, w2 = 2 * h[i] + h[i - 1], h[i] + 2 * h[i - 1]
                    m[i] = (w1 + w2) / (w1 / d[i - 1] + w2 / d[i])
        self.m, self.h = m, h

    def __call__(self, t):
        T, Vv = self.t, self.v
        if t <= T[0]:
            return Vv[0]
        if t >= T[-1]:
            return Vv[-1]
        lo, hi = 0, len(T) - 1
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if T[mid] <= t:
                lo = mid
            else:
                hi = mid
        h = self.h[lo]
        s = (t - T[lo]) / h
        h00 = 2 * s ** 3 - 3 * s ** 2 + 1
        h10 = s ** 3 - 2 * s ** 2 + s
        h01 = -2 * s ** 3 + 3 * s ** 2
        h11 = s ** 3 - s ** 2
        return h00 * Vv[lo] + h10 * h * self.m[lo] + h01 * Vv[hi] + h11 * h * self.m[hi]


def catmull(pts, n, closed=False):
    """n points along a centripetal Catmull-Rom spline through 2D/3D points, evenly spaced by arc length"""
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
    want = np.linspace(0, s[-1], n + (0 if not closed else 1))
    out = np.stack([np.interp(want, s, D[:, k]) for k in range(D.shape[1])], axis=1)
    if closed:
        out = out[:-1]
    return [tuple(p) for p in out]


def resample(pts, n, closed=False):
    """n points evenly spaced along a polyline"""
    P = np.array(pts, float)
    if closed:
        P = np.vstack([P, P[:1]])
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
    s = np.concatenate([[0], np.cumsum(seg)])
    want = np.linspace(0, s[-1], n + (1 if closed else 0))
    out = np.stack([np.interp(want, s, P[:, k]) for k in range(P.shape[1])], axis=1)
    return [tuple(p) for p in (out[:-1] if closed else out)]


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
        t = min(rs[i] / max(1e-6, math.tan(ang / 2)), la * 0.45, lb * 0.45)
        q0, q2 = p1 + a * t, p1 + b * t
        for k in range(seg + 1):
            s = k / seg
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


def offset_poly(poly, d):
    """a closed 2D polygon offset by d (positive = outwards)"""
    n = len(poly)
    area = sum(poly[i][0] * poly[(i + 1) % n][1] - poly[(i + 1) % n][0] * poly[i][1] for i in range(n))
    sgn = 1.0 if area > 0 else -1.0
    out = []
    for i in range(n):
        p0, p1, p2 = np.array(poly[i - 1], float), np.array(poly[i], float), np.array(poly[(i + 1) % n], float)
        t0, t1 = unit(p1 - p0), unit(p2 - p1)
        n0 = np.array([t0[1], -t0[0]]) * sgn
        n1 = np.array([t1[1], -t1[0]]) * sgn
        m = n0 + n1
        m = n0 if np.linalg.norm(m) < 1e-6 else unit(m)
        c = max(0.35, float(m @ n0))
        out.append(tuple(p1 + m * d / c))
    return out


def ellipse2d(cx, cy, a, b, n, a0=0.0, a1=360.0, rot=0.0):
    out = []
    cr, sr = math.cos(math.radians(rot)), math.sin(math.radians(rot))
    for i in range(n):
        t = math.radians(a0 + (a1 - a0) * i / n)
        x, y = a * math.cos(t), b * math.sin(t)
        out.append((cx + x * cr - y * sr, cy + x * sr + y * cr))
    return out


def frame_along(path):
    """parallel-transport frames (tangent, normal, binormal) along a 3D polyline"""
    P = [np.array(p, float) for p in path]
    n = len(P)
    T = []
    for i in range(n):
        a = P[max(0, i - 1)]
        b = P[min(n - 1, i + 1)]
        T.append(unit(b - a))
    ref = np.array([0, 1.0, 0]) if abs(T[0][1]) < 0.9 else np.array([1.0, 0, 0])
    N = [unit(np.cross(np.cross(T[0], ref), T[0]))]
    for i in range(1, n):
        b = np.cross(T[i - 1], T[i])
        if np.linalg.norm(b) < 1e-9:
            N.append(N[-1])
            continue
        b = unit(b)
        ang = math.acos(max(-1.0, min(1.0, float(T[i - 1] @ T[i]))))
        v = N[-1]
        v = v * math.cos(ang) + np.cross(b, v) * math.sin(ang) + b * (b @ v) * (1 - math.cos(ang))
        N.append(unit(v - T[i] * (v @ T[i])))
    Bn = [np.cross(t, nn) for t, nn in zip(T, N)]
    return P, T, N, Bn


def rot_matrix(axis, ang):
    """3x3 numpy rotation about a unit axis (game frame)"""
    a = unit(axis)
    c, s = math.cos(ang), math.sin(ang)
    x, y, z = a
    return np.array([[c + x * x * (1 - c), x * y * (1 - c) - z * s, x * z * (1 - c) + y * s],
                     [y * x * (1 - c) + z * s, c + y * y * (1 - c), y * z * (1 - c) - x * s],
                     [z * x * (1 - c) - y * s, z * y * (1 - c) + x * s, c + z * z * (1 - c)]])


# ---------------------------------------------------------------- materials

class Materials:
    """Principled materials by name (exported as glTF PBR; no transmission, no alpha)"""

    def __init__(self):
        self.mats = {}

    def add(self, name, colour, metallic=0.0, roughness=0.5, emissive=None, strength=0.0, coat=0.0, image=None):
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        p = m.node_tree.nodes.get('Principled BSDF')
        p.inputs['Base Color'].default_value = srgb(colour)
        p.inputs['Metallic'].default_value = metallic
        p.inputs['Roughness'].default_value = roughness
        if coat:
            p.inputs['Coat Weight'].default_value = coat
            p.inputs['Coat Roughness'].default_value = 0.06
        if emissive:
            p.inputs['Emission Color'].default_value = srgb(emissive)
            p.inputs['Emission Strength'].default_value = strength
        if image is not None:
            nt = m.node_tree
            t = nt.nodes.new('ShaderNodeTexImage')
            t.image = image
            nt.links.new(t.outputs['Color'], p.inputs['Base Color'])
        m.diffuse_color = srgb(colour)
        self.mats[name] = m
        return m

    def __getitem__(self, k):
        return self.mats[k]


# ---------------------------------------------------------------- mesh parts

class Part:
    """a mesh under construction (bmesh in the Blender frame, faces given in the game frame)"""

    def __init__(self, name):
        self.name = name
        self.bm = bmesh.new()
        self.uv = self.bm.loops.layers.uv.new('UVMap')
        self.slots = []

    def slot(self, mat):
        if mat not in self.slots:
            self.slots.append(mat)
        return self.slots.index(mat)

    def tris(self):
        return sum(len(f.verts) - 2 for f in self.bm.faces)

    def face(self, pts, mat, smooth=True):
        vs = [self.bm.verts.new(B(*p)) for p in pts]
        try:
            f = self.bm.faces.new(vs)
        except ValueError:
            return None
        f.material_index = self.slot(mat)
        f.smooth = smooth
        return f

    def grid(self, rows, mat, smooth=True, closed_u=False, closed_v=False, flip=False, mats=None):
        """quads over rows[j][i] (game frame); mats(i, j) → material name per quad"""
        nj, ni = len(rows), len(rows[0])
        vs = [[self.bm.verts.new(B(*p)) for p in row] for row in rows]
        faces = []
        for j in range(nj - (0 if closed_v else 1)):
            j2 = (j + 1) % nj
            for i in range(ni - (0 if closed_u else 1)):
                i2 = (i + 1) % ni
                q = [vs[j][i], vs[j][i2], vs[j2][i2], vs[j2][i]]
                if flip:
                    q.reverse()
                if len(set(q)) < 3:
                    continue
                try:
                    f = self.bm.faces.new(q)
                except ValueError:
                    continue
                f.material_index = self.slot(mats(i, j) if mats else mat)
                f.smooth = smooth
                faces.append(f)
        return faces, vs

    def cap(self, ring_verts, mat, flip=False, smooth=False, centre=None):
        """close a ring of BMVerts with a fan around its centre (or one n-gon)"""
        ring = list(ring_verts)
        if flip:
            ring.reverse()
        if centre is None:
            try:
                f = self.bm.faces.new(ring)
                f.material_index = self.slot(mat)
                f.smooth = smooth
            except ValueError:
                pass
            return
        c = self.bm.verts.new(B(*centre))
        for i in range(len(ring)):
            try:
                f = self.bm.faces.new([ring[i], ring[(i + 1) % len(ring)], c])
                f.material_index = self.slot(mat)
                f.smooth = smooth
            except ValueError:
                pass

    def loft(self, rings, mat, closed=True, cap0=False, cap1=False, smooth=True, mats=None, flip=False, cap_centre=True):
        """surface through rings (lists of game points of equal length); closed = each ring is a loop"""
        faces, vs = self.grid(rings, mat, smooth=smooth, closed_u=closed, flip=flip, mats=mats)
        for capk, j in ((cap0, 0), (cap1, len(rings) - 1)):
            if capk:
                ctr = tuple(np.mean(np.array(rings[j]), axis=0)) if cap_centre else None
                self.cap(vs[j], capk if isinstance(capk, str) else mat, flip=(j == 0) != flip, centre=ctr)
        return faces

    def tube(self, path, radius, mat, seg=12, cap0=True, cap1=True, smooth=True, ry=None, twist_ref=None, mats=None):
        """a tube along a 3D path; radius (and optional ry for an elliptical section) as numbers or per-point lists.
        The section's ry axis follows parallel transport from twist_ref (or an up-ish vector)."""
        P, T, N, Bn = frame_along(path)
        if twist_ref is not None:
            ref = np.array(twist_ref, float)
            N = [unit(ref - t * (ref @ t)) if np.linalg.norm(ref - t * (ref @ t)) > 1e-6 else nn for t, nn in zip(T, N)]
            Bn = [np.cross(t, nn) for t, nn in zip(T, N)]
        n = len(P)
        rx = radius if isinstance(radius, (list, tuple, np.ndarray)) else [radius] * n
        rys = (ry if isinstance(ry, (list, tuple, np.ndarray)) else [ry] * n) if ry is not None else rx
        rings = []
        for i in range(n):
            ring = []
            for k in range(seg):
                t = 2 * math.pi * k / seg
                ring.append(tuple(P[i] + Bn[i] * math.cos(t) * rx[i] + N[i] * math.sin(t) * rys[i]))
            rings.append(ring)
        return self.loft(rings, mat, closed=True, cap0=cap0, cap1=cap1, smooth=smooth, mats=mats)

    def revolve(self, mat, profile, centre, axis=(1, 0, 0), seg=32, smooth=True, cap0=False, cap1=False, mat_of=None,
                phase=0.0, arc=None):
        """revolve a profile [(r, a)] (radius, position along the axis) about a game-frame axis through centre;
        arc=(a0, a1) in radians for a partial revolve"""
        ax = unit(axis)
        ref = np.array([0, 1.0, 0]) if abs(ax[1]) < 0.9 else np.array([0, 0, 1.0])
        e1 = unit(np.cross(ax, ref))
        e2 = np.cross(ax, e1)
        c = np.array(centre, float)
        full = arc is None
        nseg = seg if full else seg + 1
        rows = []
        for i in range(nseg):
            t = (2 * math.pi * i / seg + phase) if full else arc[0] + (arc[1] - arc[0]) * i / seg
            d = e1 * math.cos(t) + e2 * math.sin(t)
            rows.append([tuple(c + ax * a + d * r) for (r, a) in profile])
        vs = [[self.bm.verts.new(B(*p)) for p in r] for r in rows]
        faces = []
        for i in range(seg if full else seg):
            i2 = (i + 1) % nseg
            for k in range(len(profile) - 1):
                q = [vs[i][k], vs[i][k + 1], vs[i2][k + 1], vs[i2][k]]
                if len(set(q)) < 3:
                    continue
                try:
                    f = self.bm.faces.new(q)
                except ValueError:
                    continue
                f.material_index = self.slot(mat_of(k) if mat_of else mat)
                f.smooth = smooth
                faces.append(f)
        if full:
            for capk, k in ((cap0, 0), (cap1, len(profile) - 1)):
                if capk:
                    ring = [vs[i][k] for i in range(seg)]
                    ctr = tuple(c + ax * profile[k][1])
                    self.cap(ring, capk if isinstance(capk, str) else mat, flip=(k != 0), centre=ctr)
        return faces

    def box(self, mat, x0, x1, y0, y1, z0, z1, bevel=0.0, seg=2, matrix=None, smooth=None):
        """an axis-aligned box (game frame), optionally bevelled, optionally moved by a 4x4 game-frame matrix"""
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        sx, sy, sz = x1 - x0, y1 - y0, z1 - z0
        cx, cy, cz = (x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2
        for v in bm.verts:
            v.co = B(v.co.x * sx + cx, v.co.z * sy + cy, -v.co.y * sz + cz)
        if bevel > 0:
            bmesh.ops.bevel(bm, geom=list(bm.edges), offset=min(bevel, sx / 2.01, sy / 2.01, sz / 2.01), segments=seg,
                            profile=0.5, affect='EDGES', clamp_overlap=True)
        if matrix is not None:
            M = np.array(matrix)
            for v in bm.verts:
                g = M[:3, :3] @ np.array(G(v.co)) + M[:3, 3]
                v.co = B(*g)
        self.merge(bm, mat, smooth=(bevel > 0) if smooth is None else smooth)

    def obox(self, mat, centre, size, axes=None, bevel=0.0, seg=2):
        """an oriented box: centre, size (sx, sy, sz) along axes (3 game vectors; default x, y, z)"""
        A = np.eye(3) if axes is None else np.array([unit(a) for a in axes]).T
        M = np.eye(4)
        M[:3, :3] = A
        M[:3, 3] = centre
        self.box(mat, -size[0] / 2, size[0] / 2, -size[1] / 2, size[1] / 2, -size[2] / 2, size[2] / 2, bevel=bevel, seg=seg,
                 matrix=M)

    def cylinder(self, mat, a, b, r, seg=16, cap=True, r2=None, smooth=True):
        """a cylinder (or cone) from point a to point b"""
        a, b = np.array(a, float), np.array(b, float)
        L = np.linalg.norm(b - a)
        prof = [(0.0, 0.0), (r, 0.0), (r if r2 is None else r2, L), (0.0, L)] if cap else [(r, 0.0), (r if r2 is None else r2, L)]
        faces = self.revolve(mat, prof, a, axis=b - a, seg=seg, smooth=smooth)
        return faces

    def merge(self, bm, mat=None, smooth=False, mat_of=None):
        vmap = {v: self.bm.verts.new(v.co) for v in bm.verts}
        for f in bm.faces:
            try:
                nf = self.bm.faces.new([vmap[v] for v in f.verts])
            except ValueError:
                continue
            nf.material_index = self.slot(mat_of(f) if mat_of else mat)
            nf.smooth = smooth
        bm.free()

    def mirror_x(self, faces=None):
        """duplicate (the given or all) faces mirrored to the other side (x → -x), keeping materials"""
        src = list(self.bm.faces) if faces is None else list(faces)
        vmap = {}
        for f in src:
            vs = []
            for v in f.verts:
                if v not in vmap:
                    vmap[v] = self.bm.verts.new(Vector((-v.co.x, v.co.y, v.co.z)))
                vs.append(vmap[v])
            try:
                nf = self.bm.faces.new(list(reversed(vs)))
                nf.material_index = f.material_index
                nf.smooth = f.smooth
            except ValueError:
                pass

    def transform(self, M, faces=None):
        """apply a 4x4 game-frame matrix (numpy) to all verts (or the verts of faces)"""
        vs = self.bm.verts if faces is None else {v for f in faces for v in f.verts}
        M = np.array(M)
        for v in vs:
            g = np.array(G(v.co))
            g = M[:3, :3] @ g + M[:3, 3]
            v.co = B(*g)

    def build(self, parent, mats, sharp=40.0, weld=True, name=None):
        """the object under `parent`, its mesh data in the parent's local frame"""
        mesh = bpy.data.meshes.new(name or self.name)
        if weld:
            bmesh.ops.remove_doubles(self.bm, verts=self.bm.verts, dist=1e-5)
        self.bm.normal_update()
        self.bm.to_mesh(mesh)
        self.bm.free()
        for m in self.slots:
            mesh.materials.append(mats[m])
        obj = bpy.data.objects.new(name or self.name, mesh)
        bpy.context.scene.collection.objects.link(obj)
        if parent is not None:
            bpy.context.view_layer.update()
            mesh.transform(parent.matrix_world.inverted())
            obj.parent = parent
            obj.matrix_parent_inverse = Matrix.Identity(4)
            obj.matrix_basis = Matrix.Identity(4)
        smooth_by_angle(obj, sharp)
        return obj


def smooth_by_angle(obj, angle_deg):
    me = obj.data
    bm = bmesh.new()
    bm.from_mesh(me)
    lim = math.radians(angle_deg)
    bm.normal_update()
    for e in bm.edges:
        if len(e.link_faces) != 2:
            e.smooth = False
            continue
        f1, f2 = e.link_faces
        e.smooth = f1.smooth and f2.smooth and f1.normal.angle(f2.normal, 0.0) <= lim
    bm.to_mesh(me)
    bm.free()


# ---------------------------------------------------------------- graphics cut into a surface (projections)

PROJ = {
    'side': (2, 1, 0),     # u = z, v = y, seen along x
    'front': (0, 1, 2),    # u = x, v = y, seen along z
    'top': (0, 2, 1),      # u = x, v = z, seen along y
}


def _uv(co, proj):
    g = G(co)
    a, b, _ = PROJ[proj]
    return g[a], g[b]


def _facing(f, proj, side):
    n = G(f.normal)
    return n[PROJ[proj][2]] * side


def _bbox_uv(f, proj):
    us = [_uv(v.co, proj) for v in f.verts]
    return min(p[0] for p in us), max(p[0] for p in us), min(p[1] for p in us), max(p[1] for p in us)


def cut_outline(bm, poly, proj, side=1, keep=None, margin=0.03, closed=True, min_facing=0.05):
    """cut the edges of a 2D polygon (in a projection plane) into the faces of bm that face the viewer"""
    a, b, w = PROJ[proj]
    n = len(poly)
    lo_u, hi_u = min(p[0] for p in poly) - margin, max(p[0] for p in poly) + margin
    lo_v, hi_v = min(p[1] for p in poly) - margin, max(p[1] for p in poly) + margin
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
        res = bmesh.ops.bisect_plane(bm, geom=list(verts) + list(edges) + geom, dist=1e-6, plane_co=B(*co),
                                     plane_no=B(*no) - B(0, 0, 0))
        for g in res['geom']:
            if isinstance(g, bmesh.types.BMFace):
                cand.add(g)
    bm.faces.ensure_lookup_table()


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


def paint_region(part, poly, proj, mat, side=1, keep=None, min_facing=0.05, cut=True):
    """cut a polygon's outline into a Part and give the faces inside it material `mat`; returns those faces"""
    if cut:
        cut_outline(part.bm, poly, proj, side, keep, min_facing=min_facing)
    fs = faces_in(part.bm, poly, proj, side, keep, min_facing)
    idx = part.slot(mat)
    for f in fs:
        f.material_index = idx
    return fs


def subdivide_to(part, max_edge):
    """split long edges so cut graphics follow the surface"""
    for _ in range(4):
        long_e = [e for e in part.bm.edges if e.calc_length() > max_edge]
        if not long_e:
            break
        bmesh.ops.subdivide_edges(part.bm, edges=long_e, cuts=1, use_grid_fill=True)
    bmesh.ops.triangulate(part.bm, faces=[f for f in part.bm.faces if len(f.verts) > 4])


# ---------------------------------------------------------------- surfaces (ray casts)

def bvh_of_parts(parts):
    bm = bmesh.new()
    for p in parts:
        tmp = p.bm.copy()
        vmap = {v: bm.verts.new(v.co) for v in tmp.verts}
        for f in tmp.faces:
            try:
                bm.faces.new([vmap[v] for v in f.verts])
            except ValueError:
                pass
        tmp.free()
    bm.normal_update()
    t = BVHTree.FromBMesh(bm)
    bm.free()
    return t


class Surface:
    def __init__(self, tree):
        self.tree = tree

    def hit(self, origin, direction, dist=10.0):
        loc, nrm, _, _ = self.tree.ray_cast(B(*origin), (B(*direction) - B(0, 0, 0)).normalized(), dist)
        if loc is None:
            return None
        return np.array(G(loc)), np.array(G(nrm))

    def on(self, origin, direction, lift=0.0):
        h = self.hit(origin, direction)
        if h is None:
            return None
        p, n = h
        if n @ np.array(direction, float) > 0:
            n = -n
        return tuple(p + n * lift)


def decal(part, surf, poly, plane, mat, lift=0.0015, n=None, direction=None):
    """a flat 2D polygon (in a projection plane: 'side' → (z, y) seen from -x/+x by direction) laid onto a surface by
    ray casts; triangulated by ear clipping of the resampled outline plus interior grid points (Delaunay via bmesh)"""
    import bmesh as _bm
    from mathutils.geometry import delaunay_2d_cdt
    pts = list(poly)
    if n:
        pts = resample(pts, n, closed=True)
    us = [p[0] for p in pts]
    vs = [p[1] for p in pts]
    step = max(0.004, min(max(us) - min(us), max(vs) - min(vs)) / 6)
    inner = []
    u = min(us) + step / 2
    while u < max(us):
        v = min(vs) + step / 2
        while v < max(vs):
            if inside(pts, u, v) and poly_dist(pts, u, v) > step * 0.4:
                inner.append((u, v))
            v += step
        u += step
    from mathutils import Vector as _V
    allp = [_V(p) for p in pts] + [_V(p) for p in inner]
    edges = [(i, (i + 1) % len(pts)) for i in range(len(pts))]
    res = delaunay_2d_cdt(allp, edges, [], 2, 1e-7)
    verts2, faces2 = res[0], res[2]
    a, b, w = PROJ[plane]
    d = np.zeros(3)
    d[w] = 1.0
    dirv = np.array(direction, float) if direction is not None else d
    o3 = []
    for p in verts2:
        g = np.zeros(3)
        g[a], g[b] = p[0], p[1]
        g[w] = -dirv[w] * 2.0
        o3.append(surf.on(tuple(g), tuple(dirv), lift))
    for f in faces2:
        q = [o3[i] for i in f]
        if any(x is None for x in q):
            continue
        cen = np.mean(np.array(q), axis=0)
        # wind the face towards the viewer (against the ray)
        nrm = np.cross(np.array(q[1]) - q[0], np.array(q[2]) - q[0])
        if nrm @ dirv > 0:
            q = q[::-1]
        part.face(q, mat, smooth=True)


# ---------------------------------------------------------------- nodes, scene, export

def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def node(name, parent=None, origin=(0, 0, 0), y_axis=None):
    """an empty at a game-frame origin; y_axis: the node's local +Y (game) → Blender local Z (glTF converts back)"""
    e = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(e)
    M = Matrix.Identity(4)
    if y_axis is not None:
        yb = (B(*y_axis) - B(0, 0, 0)).normalized()            # Blender local Z
        xb = Vector((1, 0, 0))                                  # game x stays x
        xb = (xb - yb * xb.dot(yb)).normalized()
        zb = yb
        yb2 = zb.cross(xb)
        M = Matrix((xb, yb2, zb)).transposed().to_4x4()
    M.translation = B(*origin)
    if parent is not None:
        bpy.context.view_layer.update()
        e.parent = parent
        e.matrix_parent_inverse = Matrix.Identity(4)
        e.matrix_basis = parent.matrix_world.inverted() @ M
    else:
        e.matrix_basis = M
    bpy.context.view_layer.update()
    return e


def export_glb(path, root):
    bpy.ops.object.select_all(action='DESELECT')
    root.select_set(True)
    for c in root.children_recursive:
        c.select_set(True)
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', use_selection=True, export_yup=True, export_apply=True,
                              export_materials='EXPORT', export_extras=False, export_cameras=False, export_lights=False,
                              export_image_format='AUTO')


def tris_of(obj):
    return sum(len(p.vertices) - 2 for p in obj.data.polygons)


def report(root):
    """triangles per object and in all, materials used"""
    tot = 0
    used = set()
    rows = []
    for o in root.children_recursive:
        if o.type == 'MESH':
            t = tris_of(o)
            tot += t
            rows.append((o.name, o.parent.name if o.parent else '', t))
            used.update(m.name for m in o.data.materials)
    for n, p, t in sorted(rows, key=lambda r: -r[2]):
        print(f'TRIS {n:24s} {p:10s} {t}')
    print('TRIS total', tot)
    print('MATERIALS', len(used), sorted(used))
    return tot, sorted(used)


def lamp_report(root):
    out = {}
    for o in root.children_recursive:
        if o.type != 'MESH':
            continue
        names = [ms.name for ms in o.data.materials]
        for p in o.data.polygons:
            n = names[p.material_index] if p.material_index < len(names) else ''
            if n in ('headlight', 'taillight', 'indicator'):
                for vi in p.vertices:
                    g = G(o.matrix_world @ o.data.vertices[vi].co)
                    out.setdefault(n, []).append(g)
    res = {}
    for k, pts in out.items():
        lo = [min(p[i] for p in pts) for i in range(3)]
        hi = [max(p[i] for p in pts) for i in range(3)]
        res[k] = ([round((a + b) / 2, 3) for a, b in zip(lo, hi)], [round(b - a, 3) for a, b in zip(lo, hi)])
        print('LAMP', k, 'centre', res[k][0], 'size', res[k][1])
    return res
