"""
Mesh building blocks for the AE86 (hayate) model: the game's car frame, a bmesh builder with material slots and UVs,
smooth splines for lofted surfaces, laying strips on a surface, and the GLB export.

Frame: the game's car frame (metres, +x = the car's left, +y up, +z forward, ground y = 0, origin midway between the
axles). B() turns it into Blender's frame so the glTF exporter (+Y up) gives the game's axes back:
Blender (x, y, z) = game (x, -z, y).
"""
import math

import bmesh
import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree


def B(x, y, z):
    """game frame → Blender"""
    return Vector((x, -z, y))


def G(v):
    """Blender → game frame"""
    return Vector((v.x, v.z, -v.y))


def srgb(hex_colour):
    """'#rrggbb' → linear RGBA"""
    h = hex_colour.lstrip('#')
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return (*out, 1.0)


def lerp(a, b, t):
    return a + (b - a) * t


def smoothstep(a, b, x):
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


# ---------------------------------------------------------------- splines


class Spline:
    """
    A smooth curve through points (any dimension, tuples) by a chord-length parameter: cubic Hermite with
    Catmull-Rom tangents (C1, no overshoot worth noting for evenly spread points). `at(t)` for t in [0, 1].
    """

    def __init__(self, pts, tension=0.5):
        self.p = [tuple(float(c) for c in p) for p in pts]
        n = len(self.p)
        d = [0.0]
        for i in range(1, n):
            d.append(d[-1] + max(1e-9, math.dist(self.p[i - 1], self.p[i])))
        self.s = [x / d[-1] for x in d]
        self.m = []
        for i in range(n):
            if n == 2:
                a, b = 0, 1
            else:
                a, b = max(0, i - 1), min(n - 1, i + 1)
            ds = self.s[b] - self.s[a]
            self.m.append(tuple((self.p[b][k] - self.p[a][k]) / ds * (2 * tension) for k in range(len(self.p[0]))))

    def at(self, t):
        t = min(1.0, max(0.0, t))
        s = self.s
        i = 0
        while i < len(s) - 2 and t > s[i + 1]:
            i += 1
        h = s[i + 1] - s[i]
        u = (t - s[i]) / h
        h00, h10, h01, h11 = 2 * u ** 3 - 3 * u ** 2 + 1, u ** 3 - 2 * u ** 2 + u, -2 * u ** 3 + 3 * u ** 2, u ** 3 - u ** 2
        return tuple(h00 * self.p[i][k] + h10 * h * self.m[i][k] + h01 * self.p[i + 1][k] + h11 * h * self.m[i + 1][k]
                     for k in range(len(self.p[0])))

    def knots(self):
        return list(self.s)


class Table:
    """
    A function of one variable through (x, value) points (value: float or tuple), monotone cubic (PCHIP) per
    component, so profiles measured on photos never wiggle between the points.
    """

    def __init__(self, pts):
        pts = sorted(pts, key=lambda p: p[0])
        self.x = [p[0] for p in pts]
        self.scalar = not isinstance(pts[0][1], (tuple, list))
        self.y = [(p[1],) if self.scalar else tuple(p[1]) for p in pts]
        self.k = len(self.y[0])
        self.d = [self._slopes([y[c] for y in self.y]) for c in range(self.k)]

    def _slopes(self, y):
        x = self.x
        n = len(x)
        if n == 1:
            return [0.0]
        h = [x[i + 1] - x[i] for i in range(n - 1)]
        dl = [(y[i + 1] - y[i]) / h[i] for i in range(n - 1)]
        d = [0.0] * n
        d[0], d[-1] = dl[0], dl[-1]
        for i in range(1, n - 1):
            if dl[i - 1] * dl[i] <= 0:
                d[i] = 0.0
            else:
                w1, w2 = 2 * h[i] + h[i - 1], h[i] + 2 * h[i - 1]
                d[i] = (w1 + w2) / (w1 / dl[i - 1] + w2 / dl[i])
        return d

    def __call__(self, x):
        xs = self.x
        if len(xs) == 1:
            out = self.y[0]
        else:
            x = min(xs[-1], max(xs[0], x))
            i = 0
            while i < len(xs) - 2 and x > xs[i + 1]:
                i += 1
            h = xs[i + 1] - xs[i]
            u = (x - xs[i]) / h
            h00, h10, h01, h11 = 2 * u ** 3 - 3 * u ** 2 + 1, u ** 3 - 2 * u ** 2 + u, -2 * u ** 3 + 3 * u ** 2, u ** 3 - u ** 2
            out = tuple(h00 * self.y[i][c] + h10 * h * self.d[c][i] + h01 * self.y[i + 1][c] + h11 * h * self.d[c][i + 1]
                        for c in range(self.k))
        return out[0] if self.scalar else out


def spread(knots, counts):
    """parameter values: between consecutive knots, counts[i] equal steps (every knot included once)"""
    out = []
    for i in range(len(knots) - 1):
        n = counts[i] if isinstance(counts, (list, tuple)) else counts
        for k in range(n):
            out.append(knots[i] + (knots[i + 1] - knots[i]) * k / n)
    out.append(knots[-1])
    return out


# ---------------------------------------------------------------- meshes


class Mesh:
    """A bmesh under construction in the game frame, with material slots (by name) and a UV layer."""

    def __init__(self, name):
        self.name = name
        self.bm = bmesh.new()
        self.uv = self.bm.loops.layers.uv.new('UVMap')
        self.slots = []
        self.sharp_keys = set()         # vertex positions (Blender frame, rounded) on crease lines: edges between two are sharp

    @staticmethod
    def _key(co):
        return (round(co[0], 4), round(co[1], 4), round(co[2], 4))

    def mark_sharp(self, pts):
        """game-frame points of a crease line (both sides: x and −x)"""
        for p in pts:
            self.sharp_keys.add(self._key(B(*p)))
            self.sharp_keys.add(self._key(B(-p[0], p[1], p[2])))

    def slot(self, mat):
        if mat not in self.slots:
            self.slots.append(mat)
        return self.slots.index(mat)

    def tris(self):
        return sum(len(f.verts) - 2 for f in self.bm.faces)

    def vert(self, p):
        return self.bm.verts.new(B(*p))

    def face(self, pts, mat, uvs=None, smooth=True, out=None):
        """a face from game-frame points (or BMVerts); flipped to face `out` (game-frame vector) if given"""
        if out is not None and not isinstance(pts[0], bmesh.types.BMVert):
            a, b, c = (Vector(p) for p in pts[:3])
            nrm = (b - a).cross(c - a)
            if nrm.length < 1e-12 and len(pts) > 3:
                nrm = (c - a).cross(Vector(pts[3]) - a)
            if nrm.dot(Vector(out)) < 0:
                pts = list(reversed(pts))
                uvs = list(reversed(uvs)) if uvs else uvs
        vs = [p if isinstance(p, bmesh.types.BMVert) else self.vert(p) for p in pts]
        try:
            f = self.bm.faces.new(vs)
        except ValueError:
            return None
        f.material_index = self.slot(mat)
        f.smooth = smooth
        if uvs:
            for loop, uv in zip(f.loops, uvs):
                loop[self.uv].uv = uv
        return f

    def grid(self, rows, mat, uvs=None, smooth=True, close_u=False, flip=False):
        """
        quads over a grid of game-frame points rows[j][i]; `mat` a name or fn(i, j) → name (None: no face);
        uvs[j][i] optional; faces wind (i, j) → (i+1, j) → (i+1, j+1) so the normal is d/di × d/dj (flip reverses).
        Returns the vertex grid.
        """
        V = [[self.vert(p) for p in row] for row in rows]
        nj, ni = len(rows), len(rows[0])
        for j in range(nj - 1):
            for i in range(ni - (0 if close_u else 1)):
                i2 = (i + 1) % ni
                m = mat(i, j) if callable(mat) else mat
                if m is None:
                    continue
                q = [V[j][i], V[j][i2], V[j + 1][i2], V[j + 1][i]]
                uq = [uvs[j][i], uvs[j][i2], uvs[j + 1][i2], uvs[j + 1][i]] if uvs else None
                if flip:
                    q.reverse()
                    uq = list(reversed(uq)) if uq else None
                if q[0] is q[3] or q[1] is q[2]:
                    continue
                try:
                    f = self.bm.faces.new(q)
                except ValueError:
                    continue
                f.material_index = self.slot(m)
                f.smooth = smooth
                if uq:
                    for loop, uv in zip(f.loops, uq):
                        loop[self.uv].uv = uv
        return V

    def merge(self, other, mat=None, smooth=None, matrix=None):
        """append another Mesh (keeping its materials unless `mat` is given) or a bmesh (needs `mat`)"""
        if isinstance(other, Mesh):
            bm, slots, uvl = other.bm, other.slots, other.uv
        else:
            bm, slots, uvl = other, None, bm_uv(other)
        vmap = {}
        for v in bm.verts:
            vmap[v] = self.bm.verts.new(matrix @ v.co if matrix is not None else v.co)
        for f in bm.faces:
            try:
                nf = self.bm.faces.new([vmap[v] for v in f.verts])
            except ValueError:
                continue
            name = mat if mat is not None else slots[f.material_index]
            nf.material_index = self.slot(name)
            nf.smooth = f.smooth if smooth is None else smooth
            if uvl is not None:
                for l0, l1 in zip(f.loops, nf.loops):
                    l1[self.uv].uv = l0[uvl].uv
        return self

    def mirror_x(self):
        """add the mirror image across x = 0 (faces flipped to keep them outward)"""
        mx = Matrix.Scale(-1, 4, Vector((1, 0, 0)))
        bm = self.bm
        faces = list(bm.faces)
        vmap = {}
        for v in list(bm.verts):
            vmap[v] = bm.verts.new(mx @ v.co)
        for f in faces:
            vs = [vmap[v] for v in reversed(f.verts)]
            uvs = [l[self.uv].uv.copy() for l in reversed(f.loops)]
            try:
                nf = bm.faces.new(vs)
            except ValueError:
                continue
            nf.material_index = f.material_index
            nf.smooth = f.smooth
            for l, uv in zip(nf.loops, uvs):
                l[self.uv].uv = uv
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
        return self

    def mirrored(self, name=None):
        """a new Mesh: the mirror image across x = 0 (faces flipped to stay outward)"""
        out = Mesh(name or self.name)
        out.merge(self)
        mx = Matrix.Scale(-1, 4, Vector((1, 0, 0)))
        bmesh.ops.transform(out.bm, matrix=mx, verts=out.bm.verts)
        bmesh.ops.reverse_faces(out.bm, faces=out.bm.faces, flip_multires=False)
        return out

    def warp(self, fn, verts=None):
        """move vertices by a function of their game-frame position: fn((x, y, z)) → (x, y, z)"""
        for v in (verts if verts is not None else self.bm.verts):
            v.co = B(*fn(tuple(G(v.co))))

    def transform(self, matrix, verts=None):
        bmesh.ops.transform(self.bm, matrix=matrix, verts=verts if verts is not None else self.bm.verts)

    def box(self, mat, x0, x1, y0, y1, z0, z1, bevel=0.0, segments=2, smooth=None):
        bm = bmesh.new()
        r = bmesh.ops.create_cube(bm, size=1.0)
        sx, sy, sz = x1 - x0, y1 - y0, z1 - z0
        for v in r['verts']:
            v.co = B(v.co.x * sx + (x0 + x1) / 2, v.co.y * sy + (y0 + y1) / 2, v.co.z * sz + (z0 + z1) / 2)
        if bevel > 0:
            bmesh.ops.bevel(bm, geom=list(bm.edges), offset=min(bevel, sx / 2.01, sy / 2.01, sz / 2.01), segments=segments,
                            profile=0.5, affect='EDGES', clamp_overlap=True)
        self.merge(bm, mat, smooth=bevel > 0 if smooth is None else smooth)
        bm.free()

    def cylinder(self, mat, centre, radius, length, axis='x', segments=16, cap=True, radius2=None, smooth=True):
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=cap, cap_tris=False, segments=segments, radius1=radius,
                              radius2=radius if radius2 is None else radius2, depth=length)
        rot = {'y': Matrix.Identity(4), 'x': Matrix.Rotation(math.pi / 2, 4, 'Y'), 'z': Matrix.Rotation(-math.pi / 2, 4, 'X')}[axis]
        bmesh.ops.transform(bm, matrix=Matrix.Translation(B(*centre)) @ rot, verts=bm.verts)
        self.merge(bm, mat, smooth=smooth)
        bm.free()

    def lathe(self, profile, segments, centre=(0, 0, 0), mats=None, uv=None, smooth=True, phase=0.0):
        """
        A surface of revolution about the game x axis through `centre`: profile [(x, r)] (r > 0), revolved
        `segments` times; mats: name or fn(k) per profile span; faces point away from the axis for profiles
        normals point away from the axis where x rises along the profile (towards it where x falls).
        """
        cx, cy, cz = centre
        rows = []
        for x, r in profile:
            row = []
            for s in range(segments + 1):
                a = phase + 2 * math.pi * s / segments
                row.append((cx + x, cy + r * math.cos(a), cz + r * math.sin(a)))
            rows.append(row)
        uvs = None
        if uv:
            uvs = [[uv(k, s / segments) for s in range(segments + 1)] for k in range(len(profile))]
        m = (lambda i, j: mats(j)) if callable(mats) else mats
        V = self.grid(rows, m, uvs=uvs, smooth=smooth)
        # weld the seam (keep the UVs on their own loops)
        seam = []
        for row in V:
            seam.extend([row[0], row[-1]])
        bmesh.ops.remove_doubles(self.bm, verts=seam, dist=1e-7)
        return V

    def build(self, parent, mats, sharp_deg=None, name=None):
        """the object (game frame vertices are already in Blender's frame), parented to `parent`"""
        bmesh.ops.remove_doubles(self.bm, verts=self.bm.verts, dist=1e-6)
        self.bm.normal_update()
        if sharp_deg is not None:
            lim = math.radians(sharp_deg)
            for e in self.bm.edges:
                if len(e.link_faces) == 2:
                    f1, f2 = e.link_faces
                    if f1.normal.angle(f2.normal, 0.0) > lim:
                        e.smooth = False
        if self.sharp_keys:
            for e in self.bm.edges:
                if all(self._key(v.co) in self.sharp_keys for v in e.verts):
                    e.smooth = False
        me = bpy.data.meshes.new(name or self.name)
        self.bm.to_mesh(me)
        for m in self.slots:
            me.materials.append(mats[m])
        obj = bpy.data.objects.new(name or self.name, me)
        bpy.context.scene.collection.objects.link(obj)
        obj.parent = parent
        return obj


def bm_uv(bm):
    return bm.loops.layers.uv.active


def bvh_of(mesh):
    mesh.bm.normal_update()
    return BVHTree.FromBMesh(mesh.bm)


def hit(bvh, origin, direction):
    """first hit of a ray (game frame) → (point, normal) in the game frame, or None"""
    loc, nrm, _, _ = bvh.ray_cast(B(*origin), B(*direction))
    if loc is None:
        return None
    return G(loc), G(nrm)


def nearest(bvh, p):
    loc, nrm, _, _ = bvh.find_nearest(B(*p))
    if loc is None:
        return None
    return G(loc), G(nrm)


# ---------------------------------------------------------------- subdivision


def subdivide(mesh, levels=1, creases=None):
    """Catmull-Clark subdivision of a Mesh (creases: {edge index: weight} on mesh.bm's edges) → new Mesh"""
    bm = mesh.bm
    bm.verts.index_update()
    bm.edges.index_update()
    me = bpy.data.meshes.new('_sub_' + mesh.name)
    bm.to_mesh(me)
    if creases:
        attr = me.attributes.get('crease_edge') or me.attributes.new('crease_edge', 'FLOAT', 'EDGE')
        vals = [0.0] * len(me.edges)
        for i, w in creases.items():
            vals[i] = w
        attr.data.foreach_set('value', vals)
    obj = bpy.data.objects.new('_sub_' + mesh.name, me)
    bpy.context.scene.collection.objects.link(obj)
    mod = obj.modifiers.new('sub', 'SUBSURF')
    mod.levels = levels
    mod.render_levels = levels
    mod.uv_smooth = 'PRESERVE_BOUNDARIES'
    mod.boundary_smooth = 'ALL'
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    me2 = ev.to_mesh()
    out = Mesh(mesh.name)
    out.slots = list(mesh.slots)
    out.bm.free()
    out.bm = bmesh.new()
    out.bm.from_mesh(me2)
    out.uv = out.bm.loops.layers.uv.active or out.bm.loops.layers.uv.new('UVMap')
    ev.to_mesh_clear()
    bpy.data.objects.remove(obj)
    bpy.data.meshes.remove(me)
    return out


# ---------------------------------------------------------------- strips laid on a surface


def lay_strip(mesh, bvh, path, width, mat, lift=0.002, direction=None, smooth=True, uv_v=(0.0, 1.0), steps=None, u_scale=1.0):
    """
    A ribbon `width` m wide laid on the surface along `path` (game-frame points near the surface): each point is
    pulled onto the surface (nearest point, or a ray along `direction`), offset by `lift` along the normal; the ribbon
    runs across the path within the surface. Returns the laid centre points.
    """
    pts = []
    for p in path:
        if direction is not None:
            h = hit(bvh, tuple(Vector(p) - Vector(direction) * 0.5), direction)
        else:
            h = nearest(bvh, p)
        if h is None:
            continue
        pts.append(h)
    rows_a, rows_b, cen = [], [], []
    for k, (p, n) in enumerate(pts):
        a = pts[max(0, k - 1)][0]
        b = pts[min(len(pts) - 1, k + 1)][0]
        t = (b - a).normalized()
        if n.dot(Vector(direction or (0, 0, 0))) > 0:
            n = -n
        side = n.cross(t).normalized()
        c = p + n * lift
        rows_a.append(tuple(c - side * width / 2))
        rows_b.append(tuple(c + side * width / 2))
        cen.append(c)
    if len(cen) < 2:
        return cen
    L = [0.0]
    for k in range(1, len(cen)):
        L.append(L[-1] + (cen[k] - cen[k - 1]).length)
    uvs = [[(l * u_scale, uv_v[0]) for l in L], [(l * u_scale, uv_v[1]) for l in L]]
    mesh.grid([rows_a, rows_b], mat, uvs=uvs, smooth=smooth)
    return cen


# ---------------------------------------------------------------- objects and export


def empty(name, parent=None, loc=(0, 0, 0)):
    e = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(e)
    e.parent = parent
    e.location = B(*loc)
    return e


def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def export_glb(path, root):
    bpy.ops.object.select_all(action='DESELECT')
    root.select_set(True)
    for c in root.children_recursive:
        c.select_set(True)
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', use_selection=True, export_yup=True, export_apply=True,
                              export_materials='EXPORT', export_extras=True, export_cameras=False, export_lights=False,
                              export_image_format='AUTO')


def rot_x(p, a, centre=(0.0, 0.0, 0.0)):
    """rotate a game-frame point about the game x axis through `centre` by a (y towards z)"""
    x, y, z = p
    cy, cz = centre[1], centre[2]
    y, z = y - cy, z - cz
    return (x, cy + y * math.cos(a) - z * math.sin(a), cz + y * math.sin(a) + z * math.cos(a))


def boolean_cut(mesh, cutters, solver='EXACT'):
    """cut Meshes `cutters` (closed) out of `mesh` (Boolean difference, hole tolerant) → a new Mesh"""
    bm = mesh.bm
    me = bpy.data.meshes.new('_bool_' + mesh.name)
    bm.to_mesh(me)
    for m in mesh.slots:
        me.materials.append(bpy.data.materials.get(m) or bpy.data.materials.new(m))
    obj = bpy.data.objects.new('_bool_' + mesh.name, me)
    bpy.context.scene.collection.objects.link(obj)
    cut_objs = []
    for k, c in enumerate(cutters):
        cm = bpy.data.meshes.new(f'_cutter{k}')
        c.bm.to_mesh(cm)
        co = bpy.data.objects.new(f'_cutter{k}', cm)
        bpy.context.scene.collection.objects.link(co)
        co.hide_render = True
        cut_objs.append(co)
        mod = obj.modifiers.new(f'cut{k}', 'BOOLEAN')
        mod.operation = 'DIFFERENCE'
        mod.solver = solver
        mod.object = co
        if solver == 'EXACT':
            mod.use_hole_tolerant = True
            mod.use_self = False
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    me2 = ev.to_mesh()
    out = Mesh(mesh.name)
    out.sharp_keys = set(mesh.sharp_keys)
    out.bm.free()
    out.bm = bmesh.new()
    out.bm.from_mesh(me2)
    out.uv = out.bm.loops.layers.uv.active or out.bm.loops.layers.uv.new('UVMap')
    names = [m.name if m else mesh.slots[0] for m in me2.materials]
    out.slots = names
    ev.to_mesh_clear()
    bpy.data.objects.remove(obj)
    bpy.data.meshes.remove(me)
    for co in cut_objs:
        m = co.data
        bpy.data.objects.remove(co)
        bpy.data.meshes.remove(m)
    return out
