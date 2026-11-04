"""
Mesh helpers for the Supra (game id `supra`): frames, curves, a bmesh Part with material slots and UVs, booleans,
projection onto the body, the export.

Frame: the game's car frame (metres, +x = the car's left, +y up, +z forward, origin on the ground midway between the
axles). B() turns it into Blender's frame so that the glTF exporter (+Y up) gives the game's axes back:
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
    h = hex_colour.lstrip('#')
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


def pchip(pts):
    """monotone cubic through (x, y) points (Fritsch-Carlson); constant outside"""
    pts = sorted(pts)
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    n = len(xs)
    d = [(ys[i + 1] - ys[i]) / (xs[i + 1] - xs[i]) for i in range(n - 1)]
    m = [0.0] * n
    m[0], m[-1] = d[0], d[-1]
    for i in range(1, n - 1):
        if d[i - 1] * d[i] <= 0:
            m[i] = 0.0
        else:
            w1 = 2 * (xs[i + 1] - xs[i]) + (xs[i] - xs[i - 1])
            w2 = (xs[i + 1] - xs[i]) + 2 * (xs[i] - xs[i - 1])
            m[i] = (w1 + w2) / (w1 / d[i - 1] + w2 / d[i])

    def f(x):
        if x <= xs[0]:
            return ys[0]
        if x >= xs[-1]:
            return ys[-1]
        lo, hi = 0, n - 1
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if xs[mid] <= x:
                lo = mid
            else:
                hi = mid
        h = xs[hi] - xs[lo]
        t = (x - xs[lo]) / h
        t2, t3 = t * t, t * t * t
        return ((2 * t3 - 3 * t2 + 1) * ys[lo] + (t3 - 2 * t2 + t) * h * m[lo] + (-2 * t3 + 3 * t2) * ys[hi]
                + (t3 - t2) * h * m[hi])
    return f


def resample(poly, n, closed=False):
    """n points evenly along a polyline (list of tuples)"""
    pts = list(poly) + ([poly[0]] if closed else [])
    seg = [math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
    total = sum(seg)
    out = []
    count = n if not closed else n
    for k in range(count):
        s = total * k / (count - (0 if closed else 1))
        acc = 0.0
        for i, L in enumerate(seg):
            if acc + L >= s - 1e-12 or i == len(seg) - 1:
                t = 0.0 if L == 0 else min(1.0, max(0.0, (s - acc) / L))
                a, b = pts[i], pts[i + 1]
                out.append(tuple(a[j] + (b[j] - a[j]) * t for j in range(len(a))))
                break
            acc += L
    return out


def rounded_rect(cx, cy, w, h, r, seg=5):
    """outline of a rounded rectangle (counter-clockwise), 2-D"""
    r = min(r, w / 2, h / 2)
    pts = []
    for (qx, qy, a0) in ((cx + w / 2 - r, cy + h / 2 - r, 0), (cx - w / 2 + r, cy + h / 2 - r, 90),
                         (cx - w / 2 + r, cy - h / 2 + r, 180), (cx + w / 2 - r, cy - h / 2 + r, 270)):
        for k in range(seg + 1):
            a = math.radians(a0 + 90 * k / seg)
            pts.append((qx + r * math.cos(a), qy + r * math.sin(a)))
    return pts


def ellipse(cx, cy, rx, ry, n=24, p=2.0, rot=0.0):
    """a superellipse outline (counter-clockwise)"""
    out = []
    c, s = math.cos(rot), math.sin(rot)
    for k in range(n):
        a = 2 * math.pi * k / n
        ca, sa = math.cos(a), math.sin(a)
        x = rx * math.copysign(abs(ca) ** (2 / p), ca)
        y = ry * math.copysign(abs(sa) ** (2 / p), sa)
        out.append((cx + x * c - y * s, cy + x * s + y * c))
    return out


def poly_area(p):
    return 0.5 * sum(p[i][0] * p[(i + 1) % len(p)][1] - p[(i + 1) % len(p)][0] * p[i][1] for i in range(len(p)))


def ccw(p):
    return p if poly_area(p) > 0 else list(reversed(p))


def inside(pt, poly):
    x, y = pt
    c = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            c = not c
    return c


class Mats:
    """Principled materials by name (glTF PBR)"""

    def __init__(self):
        self.mats = {}

    def add(self, name, colour, metallic=0.0, roughness=0.5, emissive=None, strength=0.0, image=None, coat=0.0):
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        nt = m.node_tree
        p = nt.nodes.get('Principled BSDF')
        p.inputs['Base Color'].default_value = srgb(colour)
        p.inputs['Metallic'].default_value = metallic
        p.inputs['Roughness'].default_value = roughness
        if coat:
            p.inputs['Coat Weight'].default_value = coat
            p.inputs['Coat Roughness'].default_value = 0.03
        if image is not None:
            t = nt.nodes.new('ShaderNodeTexImage')
            t.image = image
            t.interpolation = 'Linear'
            nt.links.new(t.outputs['Color'], p.inputs['Base Color'])
        if emissive:
            p.inputs['Emission Color'].default_value = srgb(emissive)
            p.inputs['Emission Strength'].default_value = strength
            if image is not None:
                nt.links.new(t.outputs['Color'], p.inputs['Emission Color'])
        self.mats[name] = m
        return m

    def __getitem__(self, name):
        return self.mats[name]

    def __len__(self):
        return len(self.mats)


class Part:
    """a mesh under construction in game coordinates: bmesh + material slots + one UV layer"""

    def __init__(self, name):
        self.name = name
        self.bm = bmesh.new()
        self.uv = self.bm.loops.layers.uv.new('UVMap')
        self.slots = []

    def slot(self, mat):
        if mat not in self.slots:
            self.slots.append(mat)
        return self.slots.index(mat)

    def vert(self, p):
        return self.bm.verts.new(B(*p))

    def face(self, pts, mat, smooth=True, uvs=None, out=None):
        """a face from game-frame points (or BMVerts); flipped to face `out` (game-frame vector) if given"""
        if out is not None and not isinstance(pts[0], bmesh.types.BMVert):
            a, b, c = (Vector(p) for p in pts[:3])
            nrm = (b - a).cross(c - a)
            if nrm.length < 1e-12 and len(pts) > 3:
                nrm = (c - a).cross(Vector(pts[3]) - a)
            if nrm.dot(Vector(out)) < 0:
                pts = list(reversed(pts))
                uvs = list(reversed(uvs)) if uvs else None
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

    def grid(self, rows, mat, smooth=True, closed=False, flip=False, uvs=None):
        """faces between rows of game-frame points (all rows the same length)"""
        vs = [[self.vert(p) for p in r] for r in rows]
        n = len(rows[0])
        last = n if closed else n - 1
        for i in range(len(rows) - 1):
            for j in range(last):
                j2 = (j + 1) % n
                q = [vs[i][j], vs[i][j2], vs[i + 1][j2], vs[i + 1][j]]
                if flip:
                    q.reverse()
                try:
                    f = self.bm.faces.new(q)
                except ValueError:
                    continue
                f.material_index = self.slot(mat)
                f.smooth = smooth
                if uvs:
                    uq = [uvs[i][j], uvs[i][j2], uvs[i + 1][j2], uvs[i + 1][j]]
                    if j2 == 0:
                        uq[1] = (uq[1][0] + 1.0, uq[1][1]) if uq[1][0] < uq[0][0] else uq[1]
                        uq[2] = (uq[2][0] + 1.0, uq[2][1]) if uq[2][0] < uq[3][0] else uq[2]
                    if flip:
                        uq.reverse()
                    for loop, uv in zip(f.loops, uq):
                        loop[self.uv].uv = uv
        return vs

    def merge(self, bm, mat, smooth=True, matrix=None):
        """append another bmesh (game frame already converted to Blender) with one material"""
        idx = self.slot(mat)
        if matrix is not None:
            bmesh.ops.transform(bm, matrix=matrix, verts=bm.verts)
        vmap = {v: self.bm.verts.new(v.co) for v in bm.verts}
        for f in bm.faces:
            try:
                nf = self.bm.faces.new([vmap[v] for v in f.verts])
            except ValueError:
                continue
            nf.material_index = idx
            nf.smooth = smooth
        bm.free()

    def box(self, mat, c, size, bevel=0.0, seg=2, rot=None, smooth=None):
        """a box centred at c (game frame), size (sx, sy, sz), optional rounded edges and a rotation matrix (game)"""
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        for v in bm.verts:
            v.co = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2]))
        if bevel > 0:
            bmesh.ops.bevel(bm, geom=list(bm.edges), offset=min(bevel, *(s / 2.01 for s in size)), segments=seg,
                            profile=0.5, affect='EDGES', clamp_overlap=True)
        for v in bm.verts:
            g = Vector(v.co)
            if rot is not None:
                g = rot @ g
            v.co = B(g.x + c[0], g.y + c[1], g.z + c[2])
        self.merge(bm, mat, smooth=(bevel > 0) if smooth is None else smooth)

    def cylinder(self, mat, c, r, length, axis='x', seg=16, cap=True, r2=None, smooth=True):
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=cap, cap_tris=False, segments=seg, radius1=r, radius2=r if r2 is None else r2,
                              depth=length)
        # create_cone runs along Blender z (= game y)
        rot = {'y': Matrix.Identity(4), 'x': Matrix.Rotation(math.pi / 2, 4, 'Y'), 'z': Matrix.Rotation(math.pi / 2, 4, 'X')}[axis]
        bmesh.ops.transform(bm, matrix=Matrix.Translation(B(*c)) @ rot, verts=bm.verts)
        self.merge(bm, mat, smooth=smooth)

    def tris(self):
        return sum(len(f.verts) - 2 for f in self.bm.faces)

    def absorb(self, other, mirror=False):
        """copy another Part's faces (materials, UVs, smoothing) into this one, mirrored to x -> -x if asked"""
        vmap = {}
        for v in other.bm.verts:
            co = v.co.copy()
            if mirror:
                co.x = -co.x
            vmap[v] = self.bm.verts.new(co)
        for f in other.bm.faces:
            vs = [vmap[v] for v in f.verts]
            uvs = [l[other.uv].uv.copy() for l in f.loops]
            if mirror:
                vs.reverse()
                uvs.reverse()
            try:
                nf = self.bm.faces.new(vs)
            except ValueError:
                continue
            nf.material_index = self.slot(other.slots[f.material_index])
            nf.smooth = f.smooth
            for l, uv in zip(nf.loops, uvs):
                l[self.uv].uv = uv

    def build(self, parent=None, mats=None, weld=1e-5, sharp=None):
        if weld:
            bmesh.ops.remove_doubles(self.bm, verts=self.bm.verts, dist=weld)
        me = bpy.data.meshes.new(self.name)
        self.bm.normal_update()
        if sharp is not None:
            for e in self.bm.edges:
                if len(e.link_faces) == 2:
                    f1, f2 = e.link_faces
                    if f1.normal.angle(f2.normal, 0.0) > math.radians(sharp):
                        e.smooth = False
        self.bm.to_mesh(me)
        self.bm.free()
        for m in self.slots:
            me.materials.append(m)
        o = bpy.data.objects.new(self.name, me)
        bpy.context.scene.collection.objects.link(o)
        if parent is not None:
            o.parent = parent
        return o


def empty(name, parent=None, loc=(0, 0, 0)):
    e = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(e)
    e.location = B(*loc)
    if parent is not None:
        e.parent = parent
    return e


def drop_unused_slots(obj):
    """remove material slots no face uses (e.g. the cutters' helper material)"""
    me = obj.data
    used = sorted({p.material_index for p in me.polygons})
    mats = [me.materials[i] for i in used]
    remap = {old: new for new, old in enumerate(used)}
    idx = [remap[p.material_index] for p in me.polygons]
    me.materials.clear()
    for m in mats:
        me.materials.append(m)
    for p, i in zip(me.polygons, idx):
        p.material_index = i


def obj_tris(o):
    return sum(len(p.vertices) - 2 for p in o.data.polygons)


def bvh_of(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.transform(obj.matrix_world)
    t = BVHTree.FromBMesh(bm)
    bm.free()
    return t


def project(bvh, p, d, back=1.0):
    """hit point on the surface from game point p, looking along -d (d points outwards); returns (point, normal) game"""
    d = Vector(d).normalized()
    o = Vector(p) + d * back
    hit = bvh.ray_cast(B(*o), B(*(-d)) - B(0, 0, 0), back * 3)
    if hit[0] is None:
        return None, None
    return G(hit[0]), G(hit[1])


def frame_for(d):
    """an orthonormal frame (e1, e2, d) for a projection direction d (game)"""
    d = Vector(d).normalized()
    up = Vector((0, 1, 0)) if abs(d.y) < 0.9 else Vector((0, 0, 1))
    e1 = up.cross(d).normalized()
    e2 = d.cross(e1).normalized()
    return e1, e2, d


def boolean(target, cutters, op='DIFFERENCE', solver='MANIFOLD'):
    """apply a boolean with the cutter objects joined into one operand (they are deleted); the cutters' materials are
    transferred to the faces they make"""
    bm = bmesh.new()
    mats = []
    for c in cutters:
        cb = bmesh.new()
        cb.from_mesh(c.data)
        cb.transform(c.matrix_world)
        remap = []
        for m in c.data.materials:
            if m not in mats:
                mats.append(m)
            remap.append(mats.index(m))
        vmap = {v: bm.verts.new(v.co) for v in cb.verts}
        for f in cb.faces:
            nf = bm.faces.new([vmap[v] for v in f.verts])
            nf.material_index = remap[f.material_index] if remap else 0
        cb.free()
    me = bpy.data.meshes.new('operand')
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)
    operand = bpy.data.objects.new('operand', me)
    bpy.context.scene.collection.objects.link(operand)
    mod = target.modifiers.new('bool', 'BOOLEAN')
    mod.operation = op
    mod.solver = solver
    mod.operand_type = 'OBJECT'
    mod.object = operand
    mod.material_mode = 'TRANSFER'
    dg = bpy.context.evaluated_depsgraph_get()
    ev = target.evaluated_get(dg)
    new = bpy.data.meshes.new_from_object(ev, preserve_all_data_layers=True, depsgraph=dg)
    target.modifiers.remove(mod)
    old = target.data
    target.data = new
    bpy.data.meshes.remove(old)
    for c in cutters:
        bpy.data.meshes.remove(c.data)
    bpy.data.meshes.remove(operand.data)
    return target


def delete_faces(obj, pred):
    """delete the faces of a mesh object for which pred(material_name, centre_game, normal_game) is true"""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    names = [m.name if m else '' for m in obj.data.materials]
    dead = [f for f in bm.faces if pred(names[f.material_index] if names else '', G(f.calc_center_median()), G(f.normal))]
    bmesh.ops.delete(bm, geom=dead, context='FACES')
    bm.to_mesh(obj.data)
    bm.free()


def prism3(name, pts, d, a, b, wall, floor, cap=None):
    """a closed prism through game points pts (a closed loop), extruded along d from a (inner end: `floor`) to b"""
    part = Part(name)
    d = Vector(d)
    lo = [part.vert(Vector(p) + d * a) for p in pts]
    hi = [part.vert(Vector(p) + d * b) for p in pts]
    n = len(pts)
    for i in range(n):
        j = (i + 1) % n
        f = part.bm.faces.new([lo[i], lo[j], hi[j], hi[i]])
        f.material_index = part.slot(wall)
    f = part.bm.faces.new(list(reversed(lo)))
    f.material_index = part.slot(floor)
    f = part.bm.faces.new(hi)
    f.material_index = part.slot(cap or wall)
    bmesh.ops.recalc_face_normals(part.bm, faces=part.bm.faces)
    return part.build(weld=0)


def catmull(ctrl, n, closed=True):
    """n points along a centripetal-ish Catmull-Rom spline through ctrl (2-D or 3-D tuples)"""
    m = len(ctrl)
    dense = []
    segs = m if closed else m - 1
    per = max(4, (n * 4) // segs)
    for i in range(segs):
        p0 = Vector(ctrl[(i - 1) % m] if closed or i > 0 else ctrl[0])
        p1 = Vector(ctrl[i % m])
        p2 = Vector(ctrl[(i + 1) % m])
        p3 = Vector(ctrl[(i + 2) % m] if closed or i + 2 < m else ctrl[-1])
        for k in range(per):
            t = k / per
            t2, t3 = t * t, t * t * t
            v = 0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3)
            dense.append(tuple(v))
    if not closed:
        dense.append(tuple(ctrl[-1]))
    return resample(dense, n, closed=closed) if closed else resample(dense, n)


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
