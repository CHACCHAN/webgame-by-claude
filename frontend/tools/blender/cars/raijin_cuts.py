"""
Openings cut into the closed body shell with exact booleans: the wheel wells (their walls become the arch liners),
the grille and the lower intake (pockets with a back wall), the fog lamp pockets and the number plate recess.
Each cutter is a closed prism; its faces left inside the body keep the cutter's material.
"""
import math

import bmesh
import bpy
from mathutils import Matrix, Vector

import raijin_kit as K
import raijin_shell as SH

ARCH_R = {'front': 0.378, 'rear': 0.372}
ARCH_Y = 0.335
WELL_INNER = 0.50        # the wheel well's inner wall (|x|)


def _obj(name, bm, mats, mat_names):
    me = bpy.data.meshes.new(name)
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    for n in mat_names:
        me.materials.append(mats[n])
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    return o


def prism(outline, z0, z1, matrix=None, flip=False):
    """a closed prism: `outline` [(x, y)] counter-clockwise seen from +z, from z0 to z1 (game frame), then moved"""
    bm = bmesh.new()
    ring0, ring1 = [], []
    for x, y in outline:
        p0, p1 = Vector((x, y, z0)), Vector((x, y, z1))
        if matrix is not None:
            p0, p1 = matrix @ p0, matrix @ p1
        ring0.append(bm.verts.new(K.B(*p0)))
        ring1.append(bm.verts.new(K.B(*p1)))
    n = len(outline)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new([ring0[i], ring0[j], ring1[j], ring1[i]])
    bm.faces.new(list(reversed(ring1)))
    bm.faces.new(ring0)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def rounded_outline(x0, x1, y0, y1, r, seg=5, top_inset=0.0):
    """a rounded rectangle (optionally a trapezoid: the top edge `top_inset` narrower per side), ccw from +z"""
    pts = []
    # bottom-right, top-right, top-left, bottom-left; a trapezoid narrows the top corners
    corners = [(x1 - r, y0 + r, -90), (x1 + top_inset - r, y1 - r, 0), (x0 - top_inset + r, y1 - r, 90), (x0 + r, y0 + r, 180)]
    for cx, cy, a0 in corners:
        for s in range(seg + 1):
            a = math.radians(a0 + 90 * s / seg)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def wells(mats):
    """four wheel-well cutters: cylinders across x from the inner wall out past the body"""
    out = []
    for key, zc in (('front', SH.FRONT_AXLE), ('rear', SH.REAR_AXLE)):
        r = ARCH_R[key]
        for side in (1, -1):
            bm = bmesh.new()
            bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=48, radius1=r, radius2=r, depth=0.75)
            # along Blender z → along game x
            rot = Matrix.Rotation(math.pi / 2, 4, 'Y')
            bmesh.ops.transform(bm, matrix=Matrix.Translation(K.B(side * (WELL_INNER + 0.375), ARCH_Y, zc)) @ rot,
                                verts=bm.verts)
            out.append(_obj(f'well_{key}_{side}', bm, mats, ['under']))
    return out


def round_poly(pts, r, seg=3):
    """round each corner of a polygon: the corner is replaced by a quadratic arc from r before it to r after it"""
    out = []
    n = len(pts)
    for i in range(n):
        p0, p1, p2 = Vector(pts[i - 1]), Vector(pts[i]), Vector(pts[(i + 1) % n])
        a = p1 + (p0 - p1).normalized() * min(r, (p0 - p1).length * 0.45)
        b = p1 + (p2 - p1).normalized() * min(r, (p2 - p1).length * 0.45)
        for k in range(seg + 1):
            t = k / seg
            q = a * (1 - t) ** 2 + p1 * 2 * t * (1 - t) + b * t * t
            out.append((q.x, q.y))
    return out


# outlines seen from the front (+x on the right), counter-clockwise
GRILLE = round_poly([(-0.205, 0.562), (0.205, 0.562), (0.242, 0.592), (0.284, 0.668), (0.268, 0.690), (-0.268, 0.690),
                     (-0.284, 0.668), (-0.242, 0.592)], 0.016)
INTAKE = round_poly([(-0.430, 0.274), (0.430, 0.274), (0.392, 0.455), (-0.392, 0.455)], 0.034)
# side intake (fog lamp pocket), in its own frame on the bumper's corner: x along the face (outwards), y up
FOG = round_poly([(-0.112, -0.066), (0.122, -0.066), (0.138, 0.036), (0.104, 0.070), (-0.112, 0.050)], 0.016)
FOG_AT = (0.612, 0.355, 2.0)
FOG_YAW = 28.0


def fog_frame(side):
    return Matrix.Translation((side * FOG_AT[0], FOG_AT[1], FOG_AT[2])) @ Matrix.Rotation(side * math.radians(FOG_YAW), 4, 'Y')


def fog_outline(side):
    return FOG if side > 0 else [(-x, y) for x, y in reversed(FOG)]


def front_cutters(mats):
    """grille (upper), the central intake (lower) and the two side intakes; each stops at a back wall"""
    out = [_obj('cut_grille', prism(GRILLE, 1.985, 2.4), mats, ['trim']),
           _obj('cut_intake', prism(INTAKE, 2.075, 2.5), mats, ['trim'])]
    for side in (1, -1):
        out.append(_obj(f'cut_fog_{side}', prism(fog_outline(side), 0.03, 0.6, matrix=fog_frame(side)), mats, ['trim']))
    return out


def apply(shell_obj, mats):
    for c in wells(mats) + front_cutters(mats):
        K.apply_boolean(shell_obj, c)


def check_manifold(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bad = sum(1 for e in bm.edges if not e.is_manifold)
    bm.free()
    return bad
