"""
Mesh building for the cockroach (roach.py): everything is written in the game frame in real millimetres
(+x = the insect's left, +y up, +z forward, ground at y = 0) and turned into Blender metres at game scale by `B()`.

A `Part` collects vertices (each with its bone weights), faces with per-corner UVs and a material slot; parts are
closed shells (rows of points lofted into quads, the ends closed on a single pole vertex). `assemble()` merges the
parts into one skinned mesh object.
"""
import math

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

# game metres per real millimetre: the body (head front to wing tips, 38 mm) becomes 3.4 m
S = 3.4 / 38.0

# game frame → Blender frame (a proper rotation): Blender (x, y, z) = game (x, −z, y)
R_GB = Matrix(((1, 0, 0), (0, 0, -1), (0, 1, 0)))


def B(x, y, z):
    """game frame (mm) → Blender (m)"""
    return Vector((x * S, -z * S, y * S))


def G(v):
    """Blender (m) → game frame (mm)"""
    return np.array((v.x / S, v.z / S, -v.y / S))


def unit(v):
    v = np.asarray(v, float)
    n = np.linalg.norm(v)
    return v / n if n > 1e-12 else v


def frame(y_axis, z_hint):
    """right-handed (X, Y, Z) with Y along `y_axis` and Z as close to `z_hint` as possible"""
    Y = unit(y_axis)
    X = unit(np.cross(Y, z_hint))
    Z = np.cross(X, Y)
    return X, Y, Z


def frame_matrix(origin, X, Y, Z):
    """a game-frame (mm) frame → a 4×4 Blender matrix (m), columns = axes"""
    m = Matrix.Identity(4)
    for c, ax in enumerate((X, Y, Z)):
        v = R_GB @ Vector(tuple(ax))
        for r in range(3):
            m[r][c] = v[r]
    o = B(*origin)
    for r in range(3):
        m[r][3] = o[r]
    return m


def rot(axis, ang):
    """3×3 rotation about a game-frame axis (numpy)"""
    a = unit(axis)
    c, s = math.cos(ang), math.sin(ang)
    x, y, z = a
    return np.array([[c + x * x * (1 - c), x * y * (1 - c) - z * s, x * z * (1 - c) + y * s],
                     [y * x * (1 - c) + z * s, c + y * y * (1 - c), y * z * (1 - c) - x * s],
                     [z * x * (1 - c) - y * s, z * y * (1 - c) + x * s, c + z * z * (1 - c)]])


def smoothstep(a, b, x):
    t = np.clip((np.asarray(x, float) - a) / (b - a), 0.0, 1.0)
    return t * t * (3 - 2 * t)


class Part:
    """one closed shell under construction"""

    def __init__(self, name, mat):
        self.name = name
        self.mat = mat
        self.co = []
        self.w = []
        self.faces = []          # (vertex ids, uvs)

    def vert(self, p, w):
        self.co.append(tuple(float(c) for c in p))
        self.w.append(w)
        return len(self.co) - 1

    def face(self, ids, uvs):
        self.faces.append((tuple(ids), tuple(tuple(float(c) for c in uv) for uv in uvs)))

    def loft(self, rows, uv_rect, weight, pole0=None, pole1=None, wrap=True, u_of=None, v_of=None):
        """
        rows: list of (n, 3) arrays of points around (same n), first to last along the part; pole0 / pole1: a point
        closing the first / last row (None leaves it open). UVs: u around (0..1 over the n columns, seam at column 0),
        v along (row index or `v_of[i]` in 0..1), mapped into uv_rect (u0, v0, u1, v1). weight: dict or f(i, j) → dict.
        """
        u0, v0, u1, v1 = uv_rect
        nr = len(rows)
        n = len(rows[0])
        vs = [i / (nr - 1) for i in range(nr)] if v_of is None else list(v_of)
        if pole0 is not None or pole1 is not None:
            # the poles take the row ends of the v range
            pass

        def W(i, j):
            return weight(i, j) if callable(weight) else weight

        ids = [[self.vert(rows[i][j], W(i, j)) for j in range(n)] for i in range(nr)]
        cols = n if wrap else n - 1

        def uv(i, j):
            uu = (j / n if wrap else j / (n - 1)) if u_of is None else u_of[j]
            return (u0 + (u1 - u0) * uu, v0 + (v1 - v0) * vs[i])

        for i in range(nr - 1):
            for j in range(cols):
                j2 = (j + 1) % n
                a, b, c, d = ids[i][j], ids[i][j2], ids[i + 1][j2], ids[i + 1][j]
                ua, ub = uv(i, j), uv(i, j + 1 if wrap else j2)
                uc, ud = uv(i + 1, j + 1 if wrap else j2), uv(i + 1, j)
                if wrap and j == n - 1:
                    ub = (u1, ub[1])
                    uc = (u1, uc[1])
                self.face((a, b, c, d), (ua, ub, uc, ud))
        for pole, i, sgn in ((pole0, 0, -1), (pole1, nr - 1, 1)):
            if pole is None:
                continue
            pid = self.vert(pole, W(i, 0))
            vp = v0 + (v1 - v0) * (0.0 if i == 0 else 1.0)
            for j in range(cols):
                j2 = (j + 1) % n
                ua, ub = uv(i, j), uv(i, j + 1 if wrap else j2)
                if wrap and j == n - 1:
                    ub = (u1, ub[1])
                um = ((ua[0] + ub[0]) / 2, vp)
                if i == 0:
                    self.face((pid, ids[i][j2], ids[i][j]), (um, ub, ua))
                else:
                    self.face((ids[i][j], ids[i][j2], pid), (ua, ub, um))
        return ids

    def mirrored(self, name, weight_map):
        """the same shell mirrored across x = 0 (faces turned round), bones renamed by weight_map"""
        p = Part(name, self.mat)
        p.co = [(-x, y, z) for x, y, z in self.co]
        p.w = [{weight_map.get(k, k): v for k, v in w.items()} for w in self.w]
        p.faces = [(tuple(reversed(ids)), tuple(reversed(uvs))) for ids, uvs in self.faces]
        return p


def tube_rows(origin, X, Y, Z, length, half_x, half_z, n_around, ts, offset=None, bulge=None):
    """
    rows of a straight tube along Y in a frame: at each t in ts (0..1 along), an ellipse half_x(t) × half_z(t)
    (functions); offset(t) → (dx, dz) shifts the centre; bulge(t, th) → extra radius factor. Returns rows, centres.
    """
    O = np.asarray(origin, float)
    th = np.arange(n_around) / n_around * 2 * math.pi
    rows, cs = [], []
    for t in ts:
        ox, oz = offset(t) if offset else (0.0, 0.0)
        ax, az = half_x(t), half_z(t)
        f = bulge(t, th) if bulge else 1.0
        c = O + Y * (t * length) + X * ox + Z * oz
        pts = c + np.outer(ax * np.cos(th) * f, X) + np.outer(az * np.sin(th) * f, Z)
        rows.append(pts)
        cs.append(c)
    return rows, cs


def end_profile(t, cap0, cap1):
    """radius factor along a tube with rounded ends: 0 at t = 0 and 1, elliptic over cap0 / cap1 of the length"""
    t = float(t)
    f = 1.0
    if cap0 > 0 and t < cap0:
        f = min(f, math.sqrt(max(0.0, 1 - ((cap0 - t) / cap0) ** 2)))
    if cap1 > 0 and t > 1 - cap1:
        f = min(f, math.sqrt(max(0.0, 1 - ((t - (1 - cap1)) / cap1) ** 2)))
    return f


def cap_ts(n_mid, cap0, cap1, n_cap=4):
    """parameter samples for a capped tube: denser in the rounded ends (no samples at exactly 0 / 1: poles)"""
    ts = []
    for k in range(1, n_cap + 1):
        a = k / (n_cap + 1)
        ts.append(cap0 * (1 - math.cos(a * math.pi / 2)))
    for k in range(n_mid + 1):
        ts.append(cap0 + (1 - cap0 - cap1) * k / n_mid)
    for k in range(n_cap, 0, -1):
        a = k / (n_cap + 1)
        ts.append(1 - cap1 * (1 - math.cos(a * math.pi / 2)))
    out = []
    for t in ts:
        if not out or t > out[-1] + 1e-6:
            out.append(t)
    return out


def assemble(name, parts, materials, armature, bone_names):
    """merge parts into one mesh object skinned to `armature`; normals outward per closed shell"""
    me = bpy.data.meshes.new(name)
    bm_all = bmesh.new()
    uv_all = bm_all.loops.layers.uv.new('UVMap')
    dl_all = bm_all.verts.layers.deform.verify()
    group = {b: i for i, b in enumerate(bone_names)}
    mat_index = {m.name: i for i, m in enumerate(materials)}
    for part in parts:
        bm = bmesh.new()
        uvl = bm.loops.layers.uv.new('UVMap')
        dl = bm.verts.layers.deform.verify()
        vs = []
        for p, w in zip(part.co, part.w):
            v = bm.verts.new(B(*p))
            for b, x in w.items():
                if x > 1e-4:
                    v[dl][group[b]] = x
            vs.append(v)
        bm.verts.ensure_lookup_table()
        for ids, uvs in part.faces:
            if len(set(ids)) < len(ids):
                continue
            try:
                f = bm.faces.new([vs[i] for i in ids])
            except ValueError:
                continue
            f.smooth = True
            f.material_index = mat_index[part.mat]
            for loop, uv in zip(f.loops, uvs):
                loop[uvl].uv = uv
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-7)
        bmesh.ops.dissolve_degenerate(bm, dist=1e-8, edges=bm.edges)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        # merge into the shared bmesh
        vmap = {}
        for v in bm.verts:
            nv = bm_all.verts.new(v.co)
            for g, x in v[dl].items():
                nv[dl_all][g] = x
            vmap[v] = nv
        for f in bm.faces:
            try:
                nf = bm_all.faces.new([vmap[v] for v in f.verts])
            except ValueError:
                continue
            nf.smooth = True
            nf.material_index = f.material_index
            for l0, l1 in zip(f.loops, nf.loops):
                l1[uv_all].uv = l0[uvl].uv
        bm.free()
    bm_all.to_mesh(me)
    bm_all.free()
    for m in materials:
        me.materials.append(m)
    obj = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(obj)
    for b in bone_names:
        obj.vertex_groups.new(name=b)
    obj.parent = armature
    mod = obj.modifiers.new('Armature', 'ARMATURE')
    mod.object = armature
    return obj
