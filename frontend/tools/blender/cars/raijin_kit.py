"""
Building blocks for the Impreza (raijin) model: frames, colours, interpolation, mesh parts, export.

Everything is written in the game's car frame (render/CarModel.ts): metres, +x = the car's left, +y up (0 = road),
+z forward, origin on the ground midway between the axles. `B()` turns that into Blender's frame so the glTF exporter
(+Y up) gives the game's axes back: Blender (x, y, z) = game (x, -z, y).
"""
import math

import bmesh
import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree


def B(x, y, z):
    """game car frame → Blender"""
    return Vector((x, -z, y))


def G(v):
    """Blender → game car frame"""
    return v.x, v.z, -v.y


def srgb(hex_colour):
    """'#rrggbb' → linear RGBA (Blender's colour inputs are linear)"""
    h = hex_colour.lstrip('#')
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


def bump(x, c, half):
    """cos² bump: 1 at c, 0 beyond ±half"""
    d = abs(x - c) / half
    return math.cos(d * math.pi / 2) ** 2 if d < 1 else 0.0


class Pchip:
    """monotone cubic (Fritsch–Carlson) through [(t, v)] sorted by t; flat outside"""

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
        T, V = self.t, self.v
        if t <= T[0]:
            return V[0]
        if t >= T[-1]:
            return V[-1]
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
        return h00 * V[lo] + h10 * h * self.m[lo] + h01 * V[hi] + h11 * h * self.m[hi]


def resample_polyline(pts, counts):
    """a smooth curve through 2D points `pts`: segment i is split into counts[i] pieces (pchip along chord length)"""
    s = [0.0]
    for a, b in zip(pts, pts[1:]):
        s.append(s[-1] + max(1e-6, math.hypot(b[0] - a[0], b[1] - a[1])))
    fx = Pchip(list(zip(s, [p[0] for p in pts])))
    fy = Pchip(list(zip(s, [p[1] for p in pts])))
    out = [pts[0]]
    for i, n in enumerate(counts):
        for k in range(1, n + 1):
            t = s[i] + (s[i + 1] - s[i]) * k / n
            out.append((fx(t), fy(t)) if k < n else pts[i + 1])
    return out


class Materials:
    """Principled materials by name (exported as glTF PBR; no transmission)."""

    def __init__(self):
        self.mats = {}

    def add(self, name, colour, metallic=0.0, roughness=0.5, emissive=None, strength=1.0, coat=0.0):
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        p = m.node_tree.nodes.get('Principled BSDF')
        p.inputs['Base Color'].default_value = srgb(colour)
        p.inputs['Metallic'].default_value = metallic
        p.inputs['Roughness'].default_value = roughness
        if coat:
            p.inputs['Coat Weight'].default_value = coat
            p.inputs['Coat Roughness'].default_value = 0.08
        if emissive:
            p.inputs['Emission Color'].default_value = srgb(emissive)
            p.inputs['Emission Strength'].default_value = strength
        self.mats[name] = m
        return m

    def textured(self, name, img, roughness=0.4, metallic=0.0, emissive_map=False):
        """a material whose base colour is an image (and optionally glows by it for the night renders)"""
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        nt = m.node_tree
        p = nt.nodes.get('Principled BSDF')
        t = nt.nodes.new('ShaderNodeTexImage')
        t.image = img
        t.interpolation = 'Linear'
        nt.links.new(t.outputs['Color'], p.inputs['Base Color'])
        if emissive_map:
            nt.links.new(t.outputs['Color'], p.inputs['Emission Color'])
            p.inputs['Emission Strength'].default_value = 0.0
        p.inputs['Roughness'].default_value = roughness
        p.inputs['Metallic'].default_value = metallic
        self.mats[name] = m
        return m

    def __getitem__(self, name):
        return self.mats[name]


class Part:
    """A mesh under construction (a bmesh with its own material slots and a UV layer)."""

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

    def face(self, pts, mat, smooth=True, uvs=None):
        """a face from game-frame points (counter-clockwise seen from outside)"""
        vs = [self.bm.verts.new(B(*p)) for p in pts]
        f = self.bm.faces.new(vs)
        f.material_index = self.slot(mat)
        f.smooth = smooth
        if uvs:
            for loop, uv in zip(f.loops, uvs):
                loop[self.uv].uv = uv
        return f

    def grid(self, rows, mat, smooth=True, uvs=None, closed_u=False, flip=False, mats=None):
        """quads over a grid of game-frame points rows[j][i]; uvs[j][i] optional; mats(i, j) → material name"""
        nj, ni = len(rows), len(rows[0])
        vs = [[self.bm.verts.new(B(*p)) for p in row] for row in rows]
        faces = []
        for j in range(nj - 1):
            for i in range(ni - (0 if closed_u else 1)):
                i2 = (i + 1) % ni
                q = [vs[j][i], vs[j][i2], vs[j + 1][i2], vs[j + 1][i]]
                idx = [(j, i), (j, i2), (j + 1, i2), (j + 1, i)]
                if flip:
                    q.reverse()
                    idx.reverse()
                if len(set(q)) < 3:
                    continue
                try:
                    f = self.bm.faces.new(q)
                except ValueError:
                    continue
                f.material_index = self.slot(mats(i, j) if mats else mat)
                f.smooth = smooth
                if uvs:
                    for loop, (a, b) in zip(f.loops, idx):
                        loop[self.uv].uv = uvs[a][b]
                faces.append(f)
        return faces

    def box(self, mat, x0, x1, y0, y1, z0, z1, bevel=0.0, segments=2, matrix=None):
        """an axis-aligned box (game frame), optionally with rounded edges, optionally moved by a game-frame matrix"""
        bm = bmesh.new()
        r = bmesh.ops.create_cube(bm, size=1.0)
        sx, sy, sz = x1 - x0, y1 - y0, z1 - z0
        cx, cy, cz = (x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2
        for v in r['verts']:
            p = Vector((v.co.x * sx + cx, v.co.y * sy + cy, v.co.z * sz + cz))
            if matrix is not None:
                p = matrix @ p
            v.co = B(*p)
        if bevel > 0:
            bmesh.ops.bevel(bm, geom=list(bm.edges), offset=min(bevel, sx / 2.01, sy / 2.01, sz / 2.01), segments=segments,
                            profile=0.5, affect='EDGES', clamp_overlap=True)
        self.merge(bm, mat, smooth=bevel > 0)

    def cylinder(self, mat, centre, radius, length, axis='x', segments=16, cap=True, radius2=None, smooth=True, flip=False):
        """a cylinder (or cone) along a game axis; flip turns it inside out (a tube seen from inside)"""
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=cap, cap_tris=False, segments=segments, radius1=radius,
                              radius2=radius if radius2 is None else radius2, depth=length)
        rot = {'y': Matrix.Identity(4), 'x': Matrix.Rotation(math.pi / 2, 4, 'Y'), 'z': Matrix.Rotation(math.pi / 2, 4, 'X')}[axis]
        bmesh.ops.transform(bm, matrix=Matrix.Translation(B(*centre)) @ rot, verts=bm.verts)
        if flip:
            bmesh.ops.reverse_faces(bm, faces=bm.faces)
        self.merge(bm, mat, smooth=smooth)

    def beam(self, mat, a, b, w, h, up=(0, 1, 0)):
        """a square beam from a to b (game frame), w across × h along `up`"""
        a, b = Vector(a), Vector(b)
        d = (b - a)
        fwd = d.normalized()
        upv = Vector(up)
        side = fwd.cross(upv).normalized()
        upv = side.cross(fwd).normalized()
        corners = []
        for p in (a, b):
            ring = []
            for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                ring.append(p + side * (sx * w / 2) + upv * (sy * h / 2))
            corners.append(ring)
        bm = bmesh.new()
        v0 = [bm.verts.new(B(*p)) for p in corners[0]]
        v1 = [bm.verts.new(B(*p)) for p in corners[1]]
        for i in range(4):
            j = (i + 1) % 4
            bm.faces.new([v0[i], v0[j], v1[j], v1[i]])
        bm.faces.new(list(reversed(v0)))
        bm.faces.new(v1)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        self.merge(bm, mat)

    def merge(self, bm, mat, smooth=False):
        """append another bmesh's faces with one material"""
        idx = self.slot(mat)
        vmap = {}
        for v in bm.verts:
            vmap[v] = self.bm.verts.new(v.co)
        for f in bm.faces:
            nf = self.bm.faces.new([vmap[v] for v in f.verts])
            nf.material_index = idx
            nf.smooth = smooth
        bm.free()

    def build(self, parent, mats, sharp=40.0, weld=True):
        mesh = bpy.data.meshes.new(self.name)
        if weld:
            bmesh.ops.remove_doubles(self.bm, verts=self.bm.verts, dist=1e-5)
        self.bm.normal_update()
        self.bm.to_mesh(mesh)
        self.bm.free()
        for m in self.slots:
            mesh.materials.append(mats[m])
        obj = bpy.data.objects.new(self.name, mesh)
        bpy.context.scene.collection.objects.link(obj)
        obj.parent = parent
        smooth_by_angle(obj, sharp)
        return obj


def smooth_by_angle(obj, angle_deg):
    """mark edges sharper than the angle (and faces flagged flat stay flat): the exporter writes split normals"""
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
        e.smooth = f1.normal.angle(f2.normal, 0.0) <= lim
    bm.to_mesh(me)
    bm.free()


def empty(name, loc=(0, 0, 0), parent=None):
    e = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(e)
    e.location = B(*loc)
    e.parent = parent
    return e


def bvh_of(objs):
    """a BVH over evaluated meshes (world space, Blender frame)"""
    bm = bmesh.new()
    dg = bpy.context.evaluated_depsgraph_get()
    for o in objs:
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        tmp = bmesh.new()
        tmp.from_mesh(me)
        tmp.transform(o.matrix_world)
        vmap = {}
        for v in tmp.verts:
            vmap[v] = bm.verts.new(v.co)
        for f in tmp.faces:
            try:
                bm.faces.new([vmap[v] for v in f.verts])
            except ValueError:
                pass
        tmp.free()
        ev.to_mesh_clear()
    bm.normal_update()
    tree = BVHTree.FromBMesh(bm)
    bm.free()
    return tree


class Surface:
    """ray casts onto a BVH in the game frame"""

    def __init__(self, tree):
        self.tree = tree

    def hit(self, origin, direction, dist=20.0):
        loc, nrm, _, _ = self.tree.ray_cast(B(*origin), B(*direction).normalized(), dist)
        if loc is None:
            return None
        return Vector(G(loc)), Vector(G(nrm))

    def on(self, origin, direction, lift=0.0):
        """the hit point moved `lift` along the outward normal (towards the ray's origin)"""
        h = self.hit(origin, direction)
        if h is None:
            return None
        p, n = h
        if n.dot(Vector(direction)) > 0:
            n = -n
        return tuple(p + n * lift)


def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def apply_boolean(obj, cutter, op='DIFFERENCE'):
    m = obj.modifiers.new('bool', 'BOOLEAN')
    m.operation = op
    m.solver = 'EXACT'
    m.object = cutter
    try:
        m.material_mode = 'TRANSFER'
    except AttributeError:
        pass
    bpy.context.view_layer.objects.active = obj
    with bpy.context.temp_override(object=obj, active_object=obj):
        bpy.ops.object.modifier_apply(modifier=m.name)
    bpy.data.objects.remove(cutter, do_unlink=True)


def export_glb(path, root):
    bpy.ops.object.select_all(action='DESELECT')
    root.select_set(True)
    for c in root.children_recursive:
        c.select_set(True)
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', use_selection=True, export_yup=True, export_apply=True,
                              export_materials='EXPORT', export_extras=True, export_cameras=False, export_lights=False,
                              export_image_format='AUTO')
