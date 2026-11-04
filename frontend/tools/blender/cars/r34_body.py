"""
The R34's body: the shell surface (r34_shell) turned into meshes, the wheel arches cut out, glass laid back into its
openings, and the fittings on the body (lamps, grille and intakes, panel lines, handles ...).
"""
import math
import os

import bmesh
import bpy
import numpy as np
from mathutils import Vector

import r34_fit as FIT
import r34_kit as K
import r34_parts as PARTS
import r34_shell as SH

PAINT = '#2f4fa6'          # Bayside Blue-like; the game recolours `paint`


def materials(tex):
    def img(name):
        p = os.path.join(tex, name)
        return bpy.data.images.load(p) if os.path.exists(p) else None
    m = {}
    m['paint'] = K.material('paint', PAINT, metallic=0.55, roughness=0.32, coat=1.0)
    m['glass'] = K.material('glass', '#0d1114', metallic=0.0, roughness=0.05)
    m['trim'] = K.material('trim', '#111213', roughness=0.55)
    m['chrome'] = K.material('chrome', '#d8dadc', metallic=1.0, roughness=0.12)
    m['headlight'] = K.material('headlight', '#dfe6ee', metallic=0.3, roughness=0.15, emissive='#fff4e0', strength=0.0,
                                image=img('headlight.png'))
    m['taillight'] = K.material('taillight', '#7a0a08', roughness=0.2, emissive='#ff1a10', strength=0.0,
                                image=img('taillight.png'))
    m['tire'] = K.material('tire', '#1a1a1b', roughness=0.85, image=img('tyre.png'))
    m['rim'] = K.material('rim', '#8a8c8f', metallic=0.85, roughness=0.32)
    m['brake'] = K.material('brake', '#c9922a', metallic=0.2, roughness=0.4)
    m['disc'] = K.material('disc', '#6c6b69', metallic=0.9, roughness=0.45)
    m['interior'] = K.material('interior', '#1c1c1e', roughness=0.8)
    m['grille'] = K.material('grille', '#0c0c0d', roughness=0.5, image=img('mesh.png'))
    m['plate'] = K.material('plate', '#f2f2ee', roughness=0.4, image=img('plate.png'))
    m['amber'] = K.material('amber', '#d9780f', roughness=0.2, emissive='#ff8a1a', strength=0.0)
    m['lens_clear'] = K.material('lens_clear', '#dfe3e6', metallic=0.3, roughness=0.12)
    m['lens_red'] = K.material('lens_red', '#8a0d0c', roughness=0.2, emissive='#ff1a10', strength=0.0)
    return m


def lamps_on(m):
    for name, s in (('headlight', 6.0), ('taillight', 3.0), ('lens_red', 1.5)):
        p = m[name].node_tree.nodes['Principled BSDF']
        p.inputs['Emission Strength'].default_value = s
        img = next((n for n in m[name].node_tree.nodes if n.type == 'TEX_IMAGE'), None)
        if img is not None:
            m[name].node_tree.links.new(img.outputs['Color'], p.inputs['Emission Color'])


# ---------------------------------------------------------------- shell


def shell_grid():
    P, named = SH.cage()
    us, vs = SH.params(P, named)
    S = SH.evaluate(P, us, vs)
    return P, named, us, vs, S


def _ring(S):
    """full rings: left half v 0..17, then the mirrored right half back down (centre points once)"""
    left = S
    right = S[:, -2:0:-1].copy()
    right[..., 0] *= -1
    return np.concatenate([left, right], axis=1)


def build_shell(mats):
    P, named, us, vs, S = shell_grid()
    nv = len(vs)
    F = _ring(S)
    nr = F.shape[1]
    vfull = np.concatenate([vs, vs[-2:0:-1]])

    def row_of(z):
        return named[round(z, 3)]

    rW1, rW0 = row_of(SH.Z_ROOF_F), row_of(SH.Z_COWL)
    rR1, rR0 = row_of(SH.Z_ROOF_R), row_of(SH.Z_BACK)
    rQ, rBr, rBf, rA = row_of(SH.Z_QUARTER), row_of(SH.B_PILLAR[0]), row_of(SH.B_PILLAR[1]), row_of(SH.Z_AFOOT)
    rmid0, rmid1 = row_of(SH.MID_Z[0]), row_of(SH.MID_Z[-1]) + 1.5

    def mat(i, j):
        u = 0.5 * (us[i] + us[min(i + 1, len(us) - 1)])
        j2 = (j + 1) % nr
        v = 0.5 * (vfull[j] + vfull[j2])
        if v < 2.5 and rmid0 <= u <= rmid1:
            return 'trim'
        if 15 <= v and rW1 <= u <= rW0:
            return 'glass'
        if 15 <= v and rR0 <= u <= rR1:
            return 'glass'
        if 12 <= v <= 14:
            if rQ <= u <= rBr and v <= 13:
                return 'glass'
            if rBr <= u <= rBf:
                return 'trim'
            if rBf <= u <= rA:
                return 'glass'
        return 'paint'

    part = K.Part('shell')
    part.grid(F, None, closed_v=True, mats=mat)
    bmesh.ops.remove_doubles(part.bm, verts=part.bm.verts, dist=1e-5)
    bmesh.ops.recalc_face_normals(part.bm, faces=part.bm.faces)
    obj = part.build(mats, merge_dist=1e-5)
    return obj, (P, named, us, vs, S), mat


def rear_bumper(mats):
    path = SH.rear_bumper_path()
    n = len(path)
    full = path + [(-x, z, -nx, nz) for x, z, nx, nz in reversed(path[:-1])]
    rows = []
    for i, (x, z, nx, nz) in enumerate(full):
        k = i if i < n else 2 * (n - 1) - i
        f = min(1.0, max(0.0, (k - 9) / (n - 12)))
        prof = SH.rear_bumper_profile(f)
        rows.append([(x + nx * pn, py, z + nz * pn) for pn, py in prof])
    P = np.array(rows)
    part = K.Part('rear_bumper')
    part.grid(P, 'paint', closed_v=True)
    # caps at both ends (inside the rear arches)
    for i in (0, len(rows) - 1):
        part.face([tuple(p) for p in P[i]], 'paint')
    bmesh.ops.remove_doubles(part.bm, verts=part.bm.verts, dist=1e-6)
    bmesh.ops.recalc_face_normals(part.bm, faces=part.bm.faces)
    return part.build(mats)


def cut(obj, cutters):
    """boolean difference with every cutter (exact solver), applied through the evaluated mesh"""
    for c in cutters:
        mod = obj.modifiers.new('cut', 'BOOLEAN')
        mod.operation = 'DIFFERENCE'
        mod.solver = 'EXACT'
        mod.material_mode = 'TRANSFER'
        mod.object = c
        c.hide_render = True
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(obj.evaluated_get(dg))
    obj.modifiers.clear()
    old = obj.data
    obj.data = me
    bpy.data.meshes.remove(old)
    for c in cutters:
        bpy.data.objects.remove(c, do_unlink=True)
    sharpen(obj)


def sharpen(obj, angle=48.0):
    """hard edges where materials meet or faces fold (cut edges): smooth shading must not spread over them"""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.normal_update()
    lim = math.radians(angle)
    for e in bm.edges:
        if len(e.link_faces) == 2:
            f1, f2 = e.link_faces
            if f1.material_index != f2.material_index or f1.normal.angle(f2.normal, 0.0) > lim:
                e.smooth = False
    bm.to_mesh(obj.data)
    bm.free()


def cylinder_cutter(centre, r, x0, x1, segments=64):
    part = K.Part('cutter')
    part.cylinder('trim', ((x0 + x1) / 2, centre[1], centre[2]), r, abs(x1 - x0), axis='x', segments=segments)
    return part.build({'trim': bpy.data.materials.get('trim')})


def split_material(obj, name, new_name):
    """move the faces of one material into their own object"""
    me = obj.data
    idx = [i for i, m in enumerate(me.materials) if m.name == name]
    if not idx:
        return None
    new = obj.copy()
    new.data = me.copy()
    new.name = new_name
    bpy.context.scene.collection.objects.link(new)
    for o, keep in ((obj, False), (new, True)):
        bm = bmesh.new()
        bm.from_mesh(o.data)
        dead = [f for f in bm.faces if (f.material_index in idx) != keep]
        bmesh.ops.delete(bm, geom=dead, context='FACES')
        bm.to_mesh(o.data)
        bm.free()
    return new


def build(mats, parent, tex):
    shell, grid, classify = build_shell(mats)
    bumper = rear_bumper(mats)

    def arches(which):
        cs = []
        for (zc, yc, r) in which:
            for s in (1, -1):
                cs.append(cylinder_cutter((0, yc, zc), r, s * 0.50, s * 1.3))
        return cs
    cut(shell, arches((SH.ARCH_F, SH.ARCH_R)) + FIT.front_cutters(mats, FIT.Surface(shell)))
    cut(bumper, arches((SH.ARCH_R,)) + FIT.rear_cutters(mats))
    glass = split_material(shell, 'glass', 'glass')
    fit = K.Part('fittings')
    s_shell, s_bumper = FIT.Surface(shell), FIT.Surface(bumper)
    FIT.front_fittings(fit, s_shell)
    FIT.rear_fittings(fit, s_shell, s_bumper)
    fittings = fit.build(mats, merge_dist=0)
    out = [('shell', shell), ('rear_bumper', bumper), ('fittings', fittings), ('exhaust', FIT.exhaust(mats, parent))]
    if glass is not None:
        out.append(('glass', glass))
    for _, o in out:
        o.parent = parent
    out += PARTS.build(mats, parent, shell, bumper, glass, grid, classify)
    return out
