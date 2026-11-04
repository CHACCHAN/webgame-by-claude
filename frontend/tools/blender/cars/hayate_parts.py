"""
Parts of the AE86 model and the assembly: materials, body meshes (mirrored halves), pop-up lamps on their hinges,
wheels, lamps, interior and the small details.
"""
import math

import bmesh
import bpy
from mathutils import Matrix, Vector

import hayate_kit as K
import hayate_body as BD
import hayate_wheel as WH
import hayate_popup as PU
import hayate_details as DT
import hayate_tex as TX
import hayate_interior as IN

# ---------------------------------------------------------------- materials


def _principled(name, colour, metallic=0.0, roughness=0.5, emissive=None, strength=0.0, coat=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    p = m.node_tree.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value = K.srgb(colour)
    m.diffuse_color = K.srgb(colour)          # the Workbench check renders
    p.inputs['Metallic'].default_value = metallic
    p.inputs['Roughness'].default_value = roughness
    if coat:
        p.inputs['Coat Weight'].default_value = coat
        p.inputs['Coat Roughness'].default_value = 0.03
    if emissive:
        p.inputs['Emission Color'].default_value = K.srgb(emissive)
        p.inputs['Emission Strength'].default_value = strength
    return m


def materials():
    """the game's swappable materials by name, plus our own (≤ 16 in all)"""
    M = {}
    M['paint'] = _principled('paint', '#e9e7e2', metallic=0.0, roughness=0.3, coat=1.0)
    M['accent'] = _principled('accent', '#1a1b1e', metallic=0.15, roughness=0.45, coat=0.6)
    M['glass'] = _principled('glass', '#10161d', metallic=0.1, roughness=0.04)
    M['trim'] = _principled('trim', '#111214', roughness=0.65)
    M['chrome'] = _principled('chrome', '#d8dade', metallic=1.0, roughness=0.12)
    M['headlight'] = _principled('headlight', '#dfe6ee', metallic=0.4, roughness=0.1, emissive='#fff4e0')
    M['taillight'] = _principled('taillight', '#6a0808', roughness=0.25, emissive='#ff1a10')
    M['tire'] = _principled('tire', '#181818', roughness=0.92)
    M['rim'] = _principled('rim', '#a7aaae', metallic=0.75, roughness=0.42)
    M['brake'] = _principled('brake', '#3a3b3e', metallic=0.4, roughness=0.5)
    M['popup_lens'] = _principled('popup_lens', '#dfe6ee', metallic=0.3, roughness=0.12, emissive='#fff4e0')
    M['interior'] = _principled('interior', '#2a2a2d', roughness=0.85)
    M['amber'] = _principled('amber', '#e07a10', roughness=0.2, emissive='#ff8a10')
    M['reverse'] = _principled('reverse', '#d4d8dc', roughness=0.15)
    M['disc'] = _principled('disc', '#77787b', metallic=0.85, roughness=0.45)
    M['plate'] = _principled('plate', '#ffffff', roughness=0.5)
    # painted textures: the lenses glow through their own pattern (as in the game: emissiveMap = map)
    for name, paint in (('taillight', TX.tail_lamp), ('headlight', TX.clear_lamp), ('popup_lens', TX.popup_lens),
                        ('amber', TX.amber_lamp)):
        img = paint()
        t = TX.apply(M[name], img)
        TX.emission_from(M[name], t)
        if name == 'headlight':
            TX.apply(M['reverse'], img)          # the reverse lamps share the clear lamps' prism pattern
    TX.apply(M['tire'], TX.tyre(), multiply='#202020')
    img = TX.plate()
    if img is not None:
        TX.apply(M['plate'], img)
    return M, {}


def lamps_on(M, night):
    for name, s in (('headlight', 8.0), ('popup_lens', 30.0), ('taillight', 3.0 if night else 0.4), ('amber', 0.0)):
        p = M[name].node_tree.nodes['Principled BSDF']
        p.inputs['Emission Strength'].default_value = s if night or name == 'taillight' else 0.0


# ---------------------------------------------------------------- assembly


def tris_of(obj):
    return sum(len(p.vertices) - 2 for p in obj.data.polygons)


def build_all(body, root, M, count):
    parts = {}
    hull = K.Mesh('hull')
    BD.build_hull(hull)
    BD.build_nose(hull)
    BD.build_tail(hull)
    hull.mirror_x()
    hull = BD.cut_arches(hull)
    bvh = K.bvh_of(hull)
    o = hull.build(body, M, sharp_deg=50)
    count['hull'] = tris_of(o)
    liner, lip = K.Mesh('arch_liners'), K.Mesh('arch_lips')
    BD.arch_parts(liner, lip, bvh)
    for m in (liner, lip):
        m.mirror_x()
        o = m.build(body, M, sharp_deg=60)
        count[m.name] = tris_of(o)

    pod, tub, hinge = PU.build()
    parts['popups'] = []
    count['popups'] = 0
    for side, name in ((1, 'popup_l'), (-1, 'popup_r')):
        h = K.empty(name, body, (side * hinge[0], hinge[1], hinge[2]))
        h['popupClosed'] = PU.CLOSED
        m = pod if side > 0 else pod.mirrored()
        o = m.build(h, M, sharp_deg=40, name=f'{name}_pod')
        count['popups'] += tris_of(o)
        parts['popups'].append(h)
    tub.mirror_x()
    o = tub.build(body, M, name='popup_recess')
    count['popups'] += tris_of(o)

    bp = K.Mesh('bumpers')
    BD.build_bumpers(bp)
    bp.mirror_x()
    o = bp.build(body, M, sharp_deg=50)
    count['bumpers'] = tris_of(o)

    gh = K.Mesh('greenhouse')
    BD.build_greenhouse(gh)
    gh.mirror_x()
    o = gh.build(body, M, sharp_deg=50)
    count['greenhouse'] = tris_of(o)

    # details laid on the body: one BVH of the outer skin
    skin = K.Mesh('skin')
    for m in (hull, bp, gh):
        skin.merge(m)
    bvh = K.bvh_of(skin)
    det = K.Mesh('details')
    lamps_f = K.Mesh('front_lamps')
    lamps_r = K.Mesh('tail_lamps')
    DT.nose(det, bvh)
    DT.bumper_front(det, bvh)
    DT.tail(det, bvh)
    DT.stripe(det, bvh)
    DT.gaps(det, bvh)
    DT.handle(det, bvh)
    DT.mirror(det)
    DT.window_trim(det, bvh)
    DT.cowl_and_wipers(det, bvh)
    det.mirror_x()
    asym = K.Mesh('details_asym')
    DT.fuel_lid(asym, bvh)
    DT.plates(asym, bvh)
    det.merge(asym)
    # the lamp lenses go to their own objects (the game finds the lamps from the bounds of the meshes using them)
    for name, target in (('headlight', lamps_f), ('taillight', lamps_r)):
        _split_material(det, name, target)
    for m in (det, lamps_f, lamps_r):
        o = m.build(body, M, sharp_deg=45)
        count[m.name] = tris_of(o)
    cab = K.Mesh('cabin')
    IN.build_halves(cab)
    cab.mirror_x()
    IN.steering(cab)
    o = cab.build(body, M, sharp_deg=40)
    count['cabin'] = tris_of(o)
    ex = K.Mesh('exhaust')
    DT.exhaust(ex)
    o = ex.build(body, M, name='exhaust_pipe')
    count['exhaust'] = tris_of(o)

    count['wheels'] = 0
    for name, x, z, front in (('fl', BD.TRACK_F / 2, BD.ZF, True), ('fr', -BD.TRACK_F / 2, BD.ZF, True),
                              ('rl', BD.TRACK_R / 2, BD.ZR, False), ('rr', -BD.TRACK_R / 2, BD.ZR, False)):
        pivot = K.empty(f'wheel_{name}', root, (x, BD.R_TYRE, z))
        spin = K.empty(f'spin_{name}', pivot)
        sm, cm = WH.wheel_meshes(front)
        if x < 0:
            sm, cm = sm.mirrored(), cm.mirrored()
        o1 = sm.build(spin, M, name=f'wheel_{name}_parts')
        o2 = cm.build(pivot, M, name=f'caliper_{name}')
        count['wheels'] += tris_of(o1) + tris_of(o2)
    return parts


def _split_material(src, mat, dst):
    """move the faces using material `mat` from Mesh src into Mesh dst"""
    if mat not in src.slots:
        return
    k = src.slots.index(mat)
    faces = [f for f in src.bm.faces if f.material_index == k]
    tmp = bmesh.new()
    uvl = tmp.loops.layers.uv.new('UVMap')
    vmap = {}
    for f in faces:
        vs = []
        for v in f.verts:
            if v not in vmap:
                vmap[v] = tmp.verts.new(v.co)
            vs.append(vmap[v])
        nf = tmp.faces.new(vs)
        nf.smooth = f.smooth
        for l0, l1 in zip(f.loops, nf.loops):
            l1[uvl].uv = l0[src.uv].uv
    dst.merge(tmp, mat=mat)
    bmesh.ops.delete(src.bm, geom=faces, context='FACES')


def fold_popups(parts, closed=True):
    for h in parts.get('popups', []):
        h.rotation_euler.x = h['popupClosed'] if closed else 0.0
