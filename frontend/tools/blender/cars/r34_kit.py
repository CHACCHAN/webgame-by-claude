"""
Small toolkit for the R34 build (own copy: no module is shared between the car scripts).

Frame: the game's car frame (metres, +x = the car's left, +y up, +z forward, origin on the ground between the
axles). B() turns it into Blender's frame so the glTF exporter (+Y up) gives the game's axes back:
Blender (x, y, z) = game (x, -z, y).
"""
import math

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree


def B(x, y, z):
    return Vector((x, -z, y))


def G(v):
    return (v[0], v[2], -v[1])


def srgb(hex_colour, alpha=1.0):
    h = hex_colour.lstrip('#')
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return (*out, alpha)


def material(name, colour, metallic=0.0, roughness=0.5, emissive=None, strength=0.0, image=None, coat=0.0):
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
    if emissive:
        p.inputs['Emission Color'].default_value = srgb(emissive)
        p.inputs['Emission Strength'].default_value = strength
    if image is not None:
        t = nt.nodes.new('ShaderNodeTexImage')
        t.image = image
        t.interpolation = 'Linear'
        nt.links.new(t.outputs['Color'], p.inputs['Base Color'])
    return m


class Part:
    """a mesh under construction: a bmesh in the game frame with material slots, UVs and per-face smoothing"""

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
        try:
            f = self.bm.faces.new(vs)
        except ValueError:
            return None
        f.material_index = self.slot(mat)
        f.smooth = smooth
        if uvs is not None:
            for loop, uv in zip(f.loops, uvs):
                loop[self.uv].uv = uv
        return f

    def grid(self, P, mat, smooth=True, closed_u=False, closed_v=False, uv=None, flip=False, mats=None):
        """faces over a (nu, nv, 3) grid of game-frame points; mats(i, j) may pick a material per face"""
        nu, nv = P.shape[:2]
        V = [[self.bm.verts.new(B(*P[i, j])) for j in range(nv)] for i in range(nu)]
        iu = range(nu if closed_u else nu - 1)
        iv = range(nv if closed_v else nv - 1)
        for i in iu:
            for j in iv:
                i2, j2 = (i + 1) % nu, (j + 1) % nv
                q = [V[i][j], V[i2][j], V[i2][j2], V[i][j2]]
                if flip:
                    q.reverse()
                if len(set(q)) < 3:
                    continue
                try:
                    f = self.bm.faces.new(q if len(set(q)) == 4 else list(dict.fromkeys(q)))
                except ValueError:
                    continue
                m = mats(i, j) if mats else mat
                f.material_index = self.slot(m)
                f.smooth = smooth
                if uv is not None:
                    uvs = [uv(i, j), uv(i2, j), uv(i2, j2), uv(i, j2)]
                    if flip:
                        uvs.reverse()
                    for loop, t in zip(f.loops, uvs):
                        loop[self.uv].uv = t
        return V

    def lathe(self, profile, mat, centre, axis='x', segments=32, smooth=True, flip=False, a0=0.0, a1=2 * math.pi,
              uv=None):
        """revolve a profile [(r, a)] (radius, position along the axis) about an axis through centre"""
        n = len(profile)
        closed = abs((a1 - a0) - 2 * math.pi) < 1e-6
        segs = segments if closed else segments + 1
        P = np.zeros((segs, n, 3))
        for s in range(segs):
            th = a0 + (a1 - a0) * s / segments
            c, sn = math.cos(th), math.sin(th)
            for k, (r, a) in enumerate(profile):
                if axis == 'x':
                    P[s, k] = (centre[0] + a, centre[1] + r * c, centre[2] + r * sn)
                elif axis == 'z':
                    P[s, k] = (centre[0] + r * c, centre[1] + r * sn, centre[2] + a)
                else:
                    P[s, k] = (centre[0] + r * c, centre[1] + a, centre[2] + r * sn)
        return self.grid(P, mat, smooth=smooth, closed_u=closed, flip=flip, uv=uv)

    def box(self, mat, x0, x1, y0, y1, z0, z1, bevel=0.0, segments=2, smooth=None):
        bm = bmesh.new()
        r = bmesh.ops.create_cube(bm, size=1.0)
        sx, sy, sz = x1 - x0, y1 - y0, z1 - z0
        for v in r['verts']:
            v.co = B(v.co.x * sx + (x0 + x1) / 2, v.co.y * sy + (y0 + y1) / 2, v.co.z * sz + (z0 + z1) / 2)
        if bevel > 0:
            bmesh.ops.bevel(bm, geom=list(bm.edges), offset=min(bevel, sx / 2.01, sy / 2.01, sz / 2.01),
                            segments=segments, profile=0.5, affect='EDGES', clamp_overlap=True)
        self.merge(bm, mat, smooth=bevel > 0 if smooth is None else smooth)

    def cylinder(self, mat, centre, radius, length, axis='x', segments=16, cap=True, smooth=True):
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=cap, cap_tris=False, segments=segments, radius1=radius, radius2=radius,
                              depth=length)
        rot = {'y': Matrix.Identity(4), 'x': Matrix.Rotation(math.pi / 2, 4, 'Y'),
               'z': Matrix.Rotation(math.pi / 2, 4, 'X')}[axis]
        bmesh.ops.transform(bm, matrix=Matrix.Translation(B(*centre)) @ rot, verts=bm.verts)
        self.merge(bm, mat, smooth=smooth)

    def merge(self, bm, mat, smooth=False, matrix=None):
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

    def tris(self):
        return sum(len(f.verts) - 2 for f in self.bm.faces)

    def build(self, mats, parent=None, merge_dist=1e-6, sharp=None):
        mesh = bpy.data.meshes.new(self.name)
        if merge_dist:
            bmesh.ops.remove_doubles(self.bm, verts=self.bm.verts, dist=merge_dist)
        self.bm.normal_update()
        if sharp is not None:
            for e in self.bm.edges:
                if len(e.link_faces) == 2:
                    f1, f2 = e.link_faces
                    if f1.normal.angle(f2.normal, 0.0) > math.radians(sharp) or f1.material_index != f2.material_index:
                        e.smooth = False
        self.bm.to_mesh(mesh)
        self.bm.free()
        for m in self.slots:
            mesh.materials.append(mats[m] if isinstance(m, str) else m)
        obj = bpy.data.objects.new(self.name, mesh)
        bpy.context.scene.collection.objects.link(obj)
        if parent is not None:
            obj.parent = parent
        return obj


def empty(name, loc=(0, 0, 0), parent=None):
    e = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(e)
    e.location = B(*loc)
    if parent is not None:
        e.parent = parent
    return e


def bvh_of(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.transform(obj.matrix_world)
    t = BVHTree.FromBMesh(bm)
    bm.free()
    return t


def tri_count(obj):
    return sum(len(p.vertices) - 2 for p in obj.data.polygons)
