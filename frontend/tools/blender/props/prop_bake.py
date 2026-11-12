"""
Weathered surfaces for the props, baked into one texture set per model (Blender 5, Cycles on the CPU).

A prop is built with `surface()` materials: procedural, in the model's own space (metres), each a base colour, a
metalness, a roughness, a height for the normal map and, for lamps and signs, a glow. What makes them look used is
shared: dirt lying in the creases and under overhangs (a baked occlusion mask), bare or pale worn edges (a baked edge
mask), rain runs down upright faces, splashed dirt and moss at the foot, rust blooming where the paint has gone.

`finish(objects, out, name)` then
  1. unwraps every face into one atlas (smart projection; long islands such as a pole are cut into pieces so that the
     texel density stays even; `M.dense(k)` parts get k times the density),
  2. bakes the masks (occlusion near and wide, edges), then base colour, occlusion / roughness / metalness, the
     tangent-space normal map and the glow from the procedural materials (all through emission, a sample or two each),
  3. replaces the materials by one material with these textures, which the glTF exporter writes as
     baseColorTexture / metallicRoughnessTexture + occlusionTexture / normalTexture / emissiveTexture.
So a prop is one draw call in the game (one more in a shadow map), whatever it is made of.
"""
import math
import os

import bmesh
import bpy
import numpy as np
from bpy_extras import mesh_utils

import prop_kit as K

CH = {}        # material name → its channels (sockets) and nodes


# ---------------------------------------------------------------------------------------------------- node graphs

class Graph:
    """a few node-building shorthands; a value is a socket or a constant"""

    def __init__(self, mat):
        self.mat = mat
        self.nt = mat.node_tree
        self._pos = None

    def new(self, kind, **props):
        n = self.nt.nodes.new(kind)
        for k, v in props.items():
            setattr(n, k, v)
        return n

    def put(self, inp, v):
        if isinstance(v, bpy.types.NodeSocket):
            self.nt.links.new(v, inp)
        elif v is not None:
            if hasattr(inp.default_value, '__len__') and not hasattr(v, '__len__'):
                v = (v, v, v, 1.0)[:len(inp.default_value)]
            inp.default_value = v

    def math(self, op, a, b=None, clamp=False):
        n = self.new('ShaderNodeMath', operation=op, use_clamp=clamp)
        self.put(n.inputs[0], a)
        if b is not None:
            self.put(n.inputs[1], b)
        return n.outputs[0]

    def mul(self, a, b):
        return self.math('MULTIPLY', a, b)

    def add(self, a, b):
        return self.math('ADD', a, b)

    def sat(self, a):
        return self.math('ADD', a, 0.0, clamp=True)

    def lerp(self, a, b, t):
        """floats"""
        n = self.new('ShaderNodeMix', data_type='FLOAT', clamp_factor=True)
        self.put(n.inputs[0], t)
        self.put(n.inputs[2], a)
        self.put(n.inputs[3], b)
        return n.outputs[0]

    def mix(self, a, b, t, mode='MIX'):
        """colours"""
        n = self.new('ShaderNodeMix', data_type='RGBA', blend_type=mode, clamp_factor=True)
        self.put(n.inputs[0], t)
        self.put(n.inputs[6], a)
        self.put(n.inputs[7], b)
        return n.outputs[2]

    def rgb(self, colour):
        n = self.new('ShaderNodeRGB')
        n.outputs[0].default_value = K.srgb(colour) if isinstance(colour, str) else (*colour, 1.0)
        return n.outputs[0]

    def step(self, x, lo, hi):
        """smooth 0 → 1 between lo and hi (lo > hi: falling)"""
        n = self.new('ShaderNodeMapRange', interpolation_type='SMOOTHSTEP')
        self.put(n.inputs['Value'], x)
        if lo > hi:
            n.inputs['From Min'].default_value, n.inputs['From Max'].default_value = hi, lo
            n.inputs['To Min'].default_value, n.inputs['To Max'].default_value = 1.0, 0.0
        else:
            n.inputs['From Min'].default_value, n.inputs['From Max'].default_value = lo, hi
        return n.outputs[0]

    def pos(self):
        """position in the model (Blender frame: x, -z of the game, y of the game = up)"""
        if self._pos is None:
            self._pos = self.new('ShaderNodeNewGeometry')
        return self._pos.outputs['Position']

    def normal(self):
        self.pos()
        return self._pos.outputs['Normal']

    def xyz(self, v):
        n = self.new('ShaderNodeSeparateXYZ')
        self.put(n.inputs[0], v)
        return n.outputs

    def scaled(self, v, s, offset=(0, 0, 0)):
        n = self.new('ShaderNodeMapping', vector_type='POINT')
        self.put(n.inputs['Vector'], v)
        n.inputs['Scale'].default_value = s
        n.inputs['Location'].default_value = offset
        return n.outputs[0]

    def noise(self, scale, detail=3.0, rough=0.55, vec=None, stretch=None, seed=0.0, distortion=0.0):
        """fractal noise 0..1 of the position; stretch (sx, sy, sz) in the game's axes scales the coordinates"""
        v = vec if vec is not None else self.pos()
        if stretch is not None or seed:
            sx, sy, sz = stretch or (1, 1, 1)
            v = self.scaled(v, (sx, sz, sy), (seed * 7.31, seed * 3.17, seed * 5.71))
        n = self.new('ShaderNodeTexNoise', noise_dimensions='3D')
        self.put(n.inputs['Vector'], v)
        n.inputs['Scale'].default_value = scale
        n.inputs['Detail'].default_value = detail
        n.inputs['Roughness'].default_value = rough
        n.inputs['Distortion'].default_value = distortion
        return n.outputs[0]

    def voronoi(self, scale, feature='F1', stretch=None, seed=0.0, randomness=1.0):
        v = self.pos()
        if stretch is not None or seed:
            sx, sy, sz = stretch or (1, 1, 1)
            v = self.scaled(v, (sx, sz, sy), (seed * 7.31, seed * 3.17, seed * 5.71))
        n = self.new('ShaderNodeTexVoronoi', feature=feature)
        self.put(n.inputs['Vector'], v)
        n.inputs['Scale'].default_value = scale
        n.inputs['Randomness'].default_value = randomness
        return n.outputs

    def image(self, img, uv='src', interpolation='Linear', extension='REPEAT'):
        um = self.new('ShaderNodeUVMap', uv_map=uv)
        n = self.new('ShaderNodeTexImage', interpolation=interpolation, extension=extension)
        n.image = img
        self.nt.links.new(um.outputs[0], n.inputs[0])
        return n


def surface(name, colour='#808080', metallic=0.0, roughness=0.5, *,
            image=None, emit=None, emit_image=None, emit_strength=1.0,
            vary=0.07, vary_scale=1.3, rough_vary=0.1,
            mottle=0.0, mottle_scale=9.0, mottle_colour=None, mottle_rough=None,
            grain=0.0, grain_scale=90.0, fibre=None,
            dirt=0.5, dirt_colour='#2b2620', streak=0.0, streak_scale=9.0,
            foot=0.0, foot_h=0.35, foot_colour='#3a3327', moss=0.0, dust=0.0,
            rust=0.0, rust_colour='#52301c', wear=0.0, wear_colour=None, wear_metal=None,
            custom=None):
    """
    A weathered material. All amounts are 0..1.
      image          a painted base colour (the faces' own UVs), multiplied by `colour`
      emit / emit_image, emit_strength   what glows (not weathered, but dimmed under dirt)
      vary           brightness wandering over about `vary_scale` metres;  rough_vary: the same for the roughness
      mottle         blotches of `mottle_colour` (default: darker) `1 / mottle_scale` m across: stains, spangle, lichen
      grain          fine relief (normal map), `grain_scale` per metre; fibre = (sx, sy, sz): stretched along an axis
                     (timber: 0.06 along the board), which also streaks the colour
      dirt           dark dirt in creases and under overhangs;  streak: rain runs on upright faces
      foot           splashed soil up to `foot_h` m above the ground;  moss: green where it stays damp;  dust: pale, on top
      rust           blooms where edges and creases are, `rust` of the surface at most
      wear           edges rubbed down to `wear_colour` (default: paler), with `wear_metal` metalness (bare steel)
      custom(g, ch)  may change ch['base' | 'rough' | 'metal' | 'height' | 'emit'] (sockets) with the graph g
    """
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    g = Graph(m)
    p = g.nt.nodes.get('Principled BSDF')
    p.inputs['IOR'].default_value = 1.5
    out = g.nt.nodes.get('Material Output')
    masks = g.image(None, uv='atlas')            # r: occlusion near, g: edges, b: occlusion wide (set by the bake)
    sep = g.new('ShaderNodeSeparateColor')
    g.nt.links.new(masks.outputs[0], sep.inputs[0])
    occ, edge, wide = sep.outputs[0], sep.outputs[1], sep.outputs[2]
    cav = g.math('SUBTRACT', 1.0, occ, clamp=True)
    shade = g.math('SUBTRACT', 1.0, wide, clamp=True)
    px, py, pz = g.xyz(g.pos())                      # pz = height above the ground
    nz = g.xyz(g.normal())[2]
    upright = g.math('SUBTRACT', 1.0, g.math('ABSOLUTE', nz), clamp=True)
    top = g.step(nz, 0.3, 0.9)

    big = g.noise(1.0 / vary_scale, 4.0, 0.6)
    mid = g.noise(6.0, 3.0, 0.6, seed=1.0)
    fine = g.noise(grain_scale, 3.0, 0.6, stretch=fibre, seed=2.0)
    # 1 at the ground, 0 from `foot_h` up (a ragged line)
    low = g.step(g.add(pz, g.mul(g.math('SUBTRACT', mid, 0.5), foot_h * 0.9)), foot_h, 0.0)

    col = g.rgb(colour)
    if image is not None:
        tex = g.image(image)
        col = g.mix(col, tex.outputs[0], 1.0, 'MULTIPLY')
    rough = g.add(roughness, g.mul(g.math('SUBTRACT', big, 0.5), 2.0 * rough_vary))
    metal = None
    height = g.mul(fine, grain)
    # brightness wandering, and the fibre's streaks in the colour
    k = g.add(1.0, g.mul(g.math('SUBTRACT', big, 0.5), 2.0 * vary))
    if fibre is not None:
        k = g.mul(k, g.add(0.8, g.mul(fine, 0.4)))
    col = g.mix(col, g.rgb((0, 0, 0)), g.math('SUBTRACT', 1.0, k, clamp=True))
    col = g.mix(col, g.rgb((1, 1, 1)), g.mul(g.math('SUBTRACT', k, 1.0, clamp=True), 0.5))
    if mottle:
        blot = g.step(g.noise(mottle_scale, 4.0, 0.65, seed=3.0, distortion=0.6), 0.5, 0.72)
        mc = g.rgb(mottle_colour) if mottle_colour else g.mix(col, g.rgb((0, 0, 0)), 0.45)
        col = g.mix(col, mc, g.mul(blot, mottle))
        if mottle_rough is not None:
            rough = g.lerp(rough, mottle_rough, g.mul(blot, mottle))
    # worn edges (only where nothing shelters them)
    if wear:
        w = g.mul(g.mul(g.step(edge, 0.12, 0.5), g.step(mid, 0.3, 0.62)), g.step(occ, 0.5, 0.85))
        w = g.mul(w, wear)
        col = g.mix(col, g.rgb(wear_colour) if wear_colour else g.mix(col, g.rgb((1, 1, 1)), 0.35), w)
        if wear_metal is not None:
            metal = g.lerp(metallic, wear_metal, w)
        height = g.math('SUBTRACT', height, g.mul(w, 0.3))
    if metal is None:
        metal = g.add(metallic, 0.0)
    # rust: blooms from creases and edges
    if rust:
        seedn = g.noise(5.0, 5.0, 0.7, seed=4.0, distortion=1.2)
        drive = g.add(g.add(g.mul(seedn, 0.6), g.mul(cav, 0.5)), g.add(g.mul(edge, 0.2), g.mul(low, 0.25)))
        r = g.step(drive, 1.0 - 0.85 * rust, 1.14 - 0.85 * rust)
        rc = g.mix(g.rgb(rust_colour), g.rgb('#8a4a22'), g.step(g.noise(40.0, 3.0, 0.7, seed=5.0), 0.35, 0.8))
        # a pale stain runs down from a bloom
        run = g.step(g.add(g.mul(g.noise(5.0, 5.0, 0.7, seed=4.0, distortion=1.2, stretch=(1, 0.25, 1)), 0.6), g.mul(cav, 0.45)), 0.93 - 0.85 * rust, 1.2 - 0.85 * rust)
        col = g.mix(col, g.rgb('#7a5a3c'), g.mul(g.mul(run, upright), 0.35))
        col = g.mix(col, rc, r)
        metal = g.mul(metal, g.math('SUBTRACT', 1.0, r, clamp=True))
        rough = g.lerp(rough, 0.92, r)
        height = g.add(height, g.mul(r, g.mul(g.noise(120.0, 2.0, 0.7, seed=6.0), 0.6)))
    # rain runs on upright faces, strongest under whatever overhangs
    if streak:
        runs = g.noise(streak_scale, 4.0, 0.7, stretch=(1, 0.035, 1), seed=7.0)
        s = g.mul(g.mul(g.step(runs, 0.48, 0.75), upright), g.add(0.45, g.mul(shade, 1.6)))
        s = g.mul(g.sat(s), streak)
        col = g.mix(col, g.rgb(dirt_colour), g.mul(s, 0.75))
        rough = g.lerp(rough, 0.85, g.mul(s, 0.6))
    # dirt in the creases and where the rain does not reach
    if dirt:
        d = g.add(g.mul(g.step(cav, 0.12, 0.75), 0.9), g.mul(shade, 0.35))
        d = g.mul(g.sat(g.mul(d, g.add(0.55, g.mul(mid, 0.9)))), dirt)
        col = g.mix(col, g.rgb(dirt_colour), d)
        rough = g.lerp(rough, 0.9, d)
        metal = g.mul(metal, g.math('SUBTRACT', 1.0, g.mul(d, 0.8), clamp=True))
    if dust:
        d = g.mul(g.mul(top, g.add(0.5, g.mul(mid, 0.5))), dust)
        col = g.mix(col, g.rgb('#8d8676'), d)
        rough = g.lerp(rough, 0.95, d)
        metal = g.mul(metal, g.math('SUBTRACT', 1.0, d, clamp=True))
    # the foot: splashed soil, moss where it stays damp
    if foot or moss:
        if foot:
            f = g.mul(low, foot)
            col = g.mix(col, g.rgb(foot_colour), g.mul(f, 0.85))
            rough = g.lerp(rough, 0.95, f)
            metal = g.mul(metal, g.math('SUBTRACT', 1.0, f, clamp=True))
        if moss:
            damp = g.sat(g.add(g.add(g.mul(low, 0.8), g.mul(cav, 0.8)), g.mul(g.mul(top, shade), 0.6)))
            patch = g.step(g.add(g.mul(g.noise(7.0, 4.0, 0.7, seed=8.0, distortion=0.8), 0.7), g.mul(damp, 0.36)), 0.7, 0.9)
            mo = g.mul(patch, moss)
            green = g.mix(g.rgb('#2c3a16'), g.rgb('#56602a'), g.noise(60.0, 2.0, 0.6, seed=9.0))
            col = g.mix(col, green, mo)
            rough = g.lerp(rough, 0.97, mo)
            metal = g.mul(metal, g.math('SUBTRACT', 1.0, mo, clamp=True))
            height = g.add(height, g.mul(mo, g.mul(g.noise(150.0, 2.0, 0.6, seed=10.0), 0.8)))
    em = None
    if emit_image is not None:
        em = g.image(emit_image).outputs[0]
    elif emit is not None:
        em = g.rgb(emit)
    if em is not None and emit_strength != 1.0:
        em = g.mix(g.rgb((0, 0, 0)), em, emit_strength)
    ch = dict(base=col, rough=g.sat(rough), metal=g.sat(metal), height=height, emit=em, occ=occ, wide=wide, edge=edge)
    if custom:
        custom(g, ch)
    # the Principled (for check renders of the unbaked model, and the normal bake)
    bump = g.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 1.0
    bump.inputs['Distance'].default_value = 0.004
    g.put(bump.inputs['Height'], ch['height'])
    g.put(p.inputs['Base Color'], ch['base'])
    g.put(p.inputs['Roughness'], ch['rough'])
    g.put(p.inputs['Metallic'], ch['metal'])
    g.nt.links.new(bump.outputs[0], p.inputs['Normal'])
    if ch['emit'] is not None:
        g.put(p.inputs['Emission Color'], ch['emit'])
        p.inputs['Emission Strength'].default_value = 1.0
    CH[m.name] = dict(ch, graph=g, masks=masks, principled=p, out=out)
    return m


# ---------------------------------------------------------------------------------------------------- the atlas

def _islands(me, layer):
    """faces grouped by their connection in the UV layer → [[polygon index]]"""
    return mesh_utils.mesh_linked_uv_islands(me)


_HEMI = []
for _i in range(14):
    # fourteen directions over a hemisphere about +Z (a golden-angle spiral)
    _z = 1.0 - (_i + 0.5) / 14 * 0.55
    _r = math.sqrt(1.0 - _z * _z)
    _HEMI.append((_r * math.cos(_i * 2.39996), _r * math.sin(_i * 2.39996), _z))


def prepare(ob, max_len, reach=0.025):
    """
    Before the unwrap: edges longer than `max_len` are cut (a pole made of full-length faces could not be cut into
    pieces of the atlas), and faces that nothing can see (a box's side inside another part, a cap inside a shell: every
    ray from them ends within `reach` metres) are tagged to take next to no room in the atlas.
    """
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    me = ob.data
    bm = bmesh.new()
    bm.from_mesh(me)
    for cuts in list(range(8, 0, -1)) * 2:
        long = [e for e in bm.edges if math.ceil(e.calc_length() / max_len) - 1 == cuts or (cuts == 8 and e.calc_length() / max_len > 9)]
        if long:
            bmesh.ops.subdivide_edges(bm, edges=long, cuts=cuts, use_grid_fill=True)
    bm.normal_update()
    bm.faces.ensure_lookup_table()
    tree = BVHTree.FromBMesh(bm)
    dens = bm.faces.layers.float.get('dense') or bm.faces.layers.float.new('dense')
    hidden = 0
    for f in bm.faces:
        n = f.normal
        if n.length < 0.5:
            continue
        t = n.orthogonal().normalized()
        b = n.cross(t)
        c = f.calc_center_median()
        pts = [c] + [c + (v.co - c) * 0.7 for v in f.verts]
        seen = False
        for q in pts:
            o = q + n * 2e-4
            for hx, hy, hz in _HEMI:
                d = t * hx + b * hy + n * hz
                hit = tree.ray_cast(o, d)
                # free, or something's outside a good way off; a hit from behind means the point lies inside a part
                if hit[0] is None or (hit[3] > reach and hit[1].dot(d) < 0):
                    seen = True
                    break
            if seen:
                break
        if not seen:
            f[dens] = 0.12 if f[dens] <= 0 else min(f[dens], 0.12)
            hidden += 1
    total = len(bm.faces)
    bm.to_mesh(me)
    bm.free()
    return hidden, total


def unwrap(objects, max_len=1.6, margin=0.004, angle=66.0):
    """
    One atlas (UV layer `atlas`) over all the objects' faces. Islands longer than `max_len` metres are cut across
    (a pole would otherwise set the scale for everything else); faces tagged with M.dense get their share.
    """
    bpy.ops.object.select_all(action='DESELECT')
    for ob in objects:
        hidden, total = prepare(ob, max_len)
        print(f'ATLAS {ob.name}: {hidden} of {total} faces are buried')
        me = ob.data
        if me.uv_layers:
            me.uv_layers[0].name = 'src'
        else:
            me.uv_layers.new(name='src')
        at = me.uv_layers.new(name='atlas')
        me.uv_layers.active = at
        ob.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(angle), island_margin=0.0, area_weight=0.0, correct_aspect=True, scale_to_bounds=False)
    bpy.ops.object.mode_set(mode='OBJECT')
    # every island to its true size (UV units = metres × its density), laid along its own long axis, the long ones cut
    def along(pts):
        """the points turned so that their widest spread lies along x"""
        c = pts.mean(0)
        q = pts - c
        cov = q.T @ q
        val, vec = np.linalg.eigh(cov)
        ax = vec[:, 1]
        rot = np.array([[ax[0], ax[1]], [-ax[1], ax[0]]])
        return q @ rot.T

    for oi, ob in enumerate(objects):
        me = ob.data
        uv = me.uv_layers['atlas'].data
        dens = me.attributes.get('dense')
        shift = 0
        for isl in _islands(me, 'atlas'):
            loops = [li for pi in isl for li in me.polygons[pi].loop_indices]
            pts = np.array([uv[li].uv[:] for li in loops], dtype=np.float64)
            a3 = sum(me.polygons[pi].area for pi in isl)
            a2 = 0.0
            for pi in isl:
                q = [uv[li].uv for li in me.polygons[pi].loop_indices]
                a2 += abs(sum(q[i].x * q[(i + 1) % len(q)].y - q[(i + 1) % len(q)].x * q[i].y for i in range(len(q)))) / 2
            scale = math.sqrt(a3 / a2) if a2 > 1e-12 else 0.0       # metres per UV unit
            w = 1.0
            if dens is not None:
                w = sum(dens.data[pi].value * me.polygons[pi].area for pi in isl) / max(a3, 1e-9)
                w = w if w > 0 else 1.0
            pts = along(pts) * scale
            where = {li: k for k, li in enumerate(loops)}
            lo, hi = pts[:, 0].min(), pts[:, 0].max()
            parts = max(1, math.ceil((hi - lo) / max_len)) if scale else 1
            box = (hi - lo) * (pts[:, 1].max() - pts[:, 1].min())
            # a ring (little of its bounding box is its own): cut into sectors about its middle, each then laid straight
            ring = scale and len(isl) >= 8 and a3 < 0.3 * box and (pts[:, 1].max() - pts[:, 1].min()) > 0.45 * (hi - lo)
            if ring:
                parts = 6
            bins = [[] for _ in range(parts)]
            for pi in isl:
                li = list(me.polygons[pi].loop_indices)
                if ring:
                    cx = sum(pts[where[i], 0] for i in li) / len(li)
                    cy = sum(pts[where[i], 1] for i in li) / len(li)
                    bins[min(parts - 1, int((math.atan2(cy, cx) / (2 * math.pi) + 0.5) * parts))].append(li)
                    continue
                mid = sum(pts[where[i], 0] for i in li) / len(li)
                bins[min(parts - 1, int((mid - lo) / max(hi - lo, 1e-9) * parts))].append(li)
            for b in bins:
                if not b:
                    continue
                idx = [i for li in b for i in li]
                piece = pts[[where[i] for i in idx]]
                piece = (along(piece) if parts > 1 and len(piece) > 2 else piece - piece.mean(0)) * w
                # moved apart far enough that no two pieces touch (the packer brings them back)
                for i, q in zip(idx, piece):
                    uv[i].uv = (q[0] + 60.0 * shift, q[1] + 60.0 * oi)
                shift += 1
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.pack_islands(rotate=True, rotate_method='CARDINAL', scale=True, margin_method='FRACTION', margin=margin, shape_method='CONCAVE')
    bpy.ops.object.mode_set(mode='OBJECT')
    # what came of it: the share of the atlas in use, and a plain face's texels per metre in a texture 1024 px wide
    used = area = 0.0
    for ob in objects:
        me = ob.data
        uv = me.uv_layers['atlas'].data
        dens = me.attributes.get('dense')
        for poly in me.polygons:
            q = [uv[li].uv for li in poly.loop_indices]
            used += abs(sum(q[i].x * q[(i + 1) % len(q)].y - q[(i + 1) % len(q)].x * q[i].y for i in range(len(q)))) / 2
            w = dens.data[poly.index].value if dens is not None else 1.0
            area += poly.area * (w if w > 0 else 1.0) ** 2
    print(f'ATLAS {used * 100:.0f} % in use, {1024 * math.sqrt(used / max(area, 1e-9)):.0f} px/m per 1024 px')


# ---------------------------------------------------------------------------------------------------- the bake

def _mask_material(near, wide, edge_r):
    m = bpy.data.materials.new('masks')
    m.use_nodes = True
    g = Graph(m)
    nt = g.nt
    for n in list(nt.nodes):
        if n.type != 'OUTPUT_MATERIAL':
            nt.nodes.remove(n)
    out = nt.nodes.get('Material Output')
    ao1 = g.new('ShaderNodeAmbientOcclusion', samples=8, only_local=False)
    ao1.inputs['Distance'].default_value = near
    ao2 = g.new('ShaderNodeAmbientOcclusion', samples=8, only_local=False)
    ao2.inputs['Distance'].default_value = wide
    bev = g.new('ShaderNodeBevel', samples=6)
    bev.inputs['Radius'].default_value = edge_r
    geo = g.new('ShaderNodeNewGeometry')
    dot = g.new('ShaderNodeVectorMath', operation='DOT_PRODUCT')
    nt.links.new(bev.outputs[0], dot.inputs[0])
    nt.links.new(geo.outputs['Normal'], dot.inputs[1])
    e = g.math('MULTIPLY', g.math('SUBTRACT', 1.0, dot.outputs['Value'], clamp=True), 3.5, clamp=True)
    comb = g.new('ShaderNodeCombineColor')
    nt.links.new(ao1.outputs['AO'], comb.inputs[0])
    g.put(comb.inputs[1], e)
    nt.links.new(ao2.outputs['AO'], comb.inputs[2])
    em = g.new('ShaderNodeEmission')
    nt.links.new(comb.outputs[0], em.inputs[0])
    nt.links.new(em.outputs[0], out.inputs['Surface'])
    tex = g.new('ShaderNodeTexImage')
    nt.nodes.active = tex
    return m, tex


def _bake(objects, kind, samples, margin):
    sc = bpy.context.scene
    sc.cycles.samples = samples
    bpy.ops.object.select_all(action='DESELECT')
    for ob in objects:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    if kind == 'NORMAL':
        bpy.ops.object.bake(type='NORMAL', normal_space='TANGENT', margin=margin, margin_type='EXTEND', use_clear=True)
    else:
        bpy.ops.object.bake(type='EMIT', margin=margin, margin_type='EXTEND', use_clear=True)


def _pixels(img):
    w, h = img.size
    a = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(a)
    return a.reshape(h, w, 4)


def _blur(a, r):
    """a small box blur, twice (noise in the occlusion masks)"""
    if r < 1:
        return a
    for _ in range(2):
        for ax in (0, 1):
            acc = np.zeros_like(a)
            for d in range(-r, r + 1):
                acc += np.roll(a, d, axis=ax)
            a = acc / (2 * r + 1)
    return a


def _to_srgb(a):
    a = np.clip(a, 0.0, 1.0)
    return np.where(a <= 0.0031308, a * 12.92, 1.055 * np.power(a, 1 / 2.4) - 0.055)


def _save(img, path, srgb_file):
    """the bake images hold plain scene-linear numbers: colours are encoded here, data is written as it is"""
    a = _pixels(img)[..., :3]
    K.write_png(path, _to_srgb(a) if srgb_file else a, srgb_colour=srgb_file)


def finish(objects, out, name, size=1024, orm_size=None, emit_size=None, normal=True, normal_size=None, normal_strength=1.0,
           near=0.10, wide=0.6, edge=0.012, ground=True, max_len=1.6, margin=0.004, mask_samples=24, angle=66.0,
           roughness_floor=0.0, mat_name=None):
    """
    Unwrap, bake and re-material the objects (see the module's header). Returns the material.
      size / orm_size / emit_size / normal_size   pixels of base colour / occlusion-roughness-metal / glow / normal map
                                    (the last three default to `size`)
      near, wide, edge              reach in metres of the two occlusion masks and of the edge mask
      ground                        a ground plane at y = 0 takes part in the occlusion (the foot of a prop is darker)
    """
    tex = os.path.join(out, 'tex')
    os.makedirs(tex, exist_ok=True)
    orm_size = orm_size or size
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.use_denoising = False
    sc.render.threads_mode = 'FIXED'
    sc.render.threads = 4
    sc.cycles.max_bounces = 0
    sc.render.bake.use_selected_to_active = False
    unwrap(objects, max_len=max_len, margin=margin, angle=angle)
    px = max(2, size // 256)
    floor = None
    if ground:
        bm = bmesh.new()
        bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=200.0)
        me = bpy.data.meshes.new('floor')
        bm.to_mesh(me)
        bm.free()
        floor = bpy.data.objects.new('floor', me)
        sc.collection.objects.link(floor)
    # 1. masks
    used = []
    for ob in objects:
        for m in ob.data.materials:
            if m not in used:
                used.append(m)
    mimg = bpy.data.images.new(f'{name}_masks', orm_size, orm_size, alpha=False, float_buffer=True)
    mimg.colorspace_settings.name = 'Non-Color'
    mm, mtex = _mask_material(near, wide, edge)
    mtex.image = mimg
    keep = [list(ob.data.materials) for ob in objects]
    for ob in objects:
        for i in range(len(ob.data.materials)):
            ob.data.materials[i] = mm
    _bake(objects, 'EMIT', mask_samples, px)
    for ob, mats in zip(objects, keep):
        for i, m in enumerate(mats):
            ob.data.materials[i] = m
    if floor is not None:
        bpy.data.objects.remove(floor)
    a = _pixels(mimg)
    a[..., :3] = _blur(a[..., :3], 1)
    mimg.pixels.foreach_set(a.ravel())
    mimg.update()
    masks_px = a
    # 2. the channels, each through an emission shader
    has_emit = any(CH[m.name]['emit'] is not None for m in used)

    def emit_pass(tag, sock_of, res, colourspace, samples=8):
        img = bpy.data.images.new(f'{name}_{tag}', res, res, alpha=False, float_buffer=True)
        img.colorspace_settings.name = 'Non-Color'
        for m in used:
            c = CH[m.name]
            g = c['graph']
            c['masks'].image = mimg
            em = g.new('ShaderNodeEmission')
            s = sock_of(c, g)
            g.put(em.inputs[0], s if s is not None else (0.0, 0.0, 0.0, 1.0))
            g.nt.links.new(em.outputs[0], c['out'].inputs['Surface'])
            t = g.new('ShaderNodeTexImage')
            t.image = img
            g.nt.nodes.active = t
            c['_tmp'] = (em, t)
        _bake(objects, 'EMIT', samples, max(2, res // 256))
        for m in used:
            c = CH[m.name]
            for n in c['_tmp']:
                c['graph'].nt.nodes.remove(n)
            c['graph'].nt.links.new(c['principled'].outputs[0], c['out'].inputs['Surface'])
        return img

    base = emit_pass('base', lambda c, g: c['base'], size, 'sRGB')

    def orm_sock(c, g):
        n = g.new('ShaderNodeCombineColor')
        g.put(n.inputs[0], 1.0)
        g.put(n.inputs[1], c['rough'])
        g.put(n.inputs[2], c['metal'])
        return n.outputs[0]

    orm = emit_pass('orm', orm_sock, orm_size, 'Non-Color')
    o = _pixels(orm)
    # occlusion: the near mask, deepened a little by the wide one
    occ = np.clip(masks_px[..., 0] * (0.55 + 0.45 * masks_px[..., 2]), 0.0, 1.0)
    o[..., 0] = occ
    if roughness_floor:
        o[..., 1] = np.maximum(o[..., 1], roughness_floor)
    orm.pixels.foreach_set(o.ravel())
    emit_img = emit_pass('emit', lambda c, g: c['emit'], emit_size or size, 'sRGB') if has_emit else None
    nimg = None
    if normal:
        nsize = normal_size or size
        nimg = bpy.data.images.new(f'{name}_normal', nsize, nsize, alpha=False, float_buffer=True)
        nimg.colorspace_settings.name = 'Non-Color'
        for m in used:
            c = CH[m.name]
            c['masks'].image = mimg
            t = c['graph'].new('ShaderNodeTexImage')
            t.image = nimg
            c['graph'].nt.nodes.active = t
            for n in c['graph'].nt.nodes:
                if n.type == 'BUMP':
                    n.inputs['Strength'].default_value = normal_strength
        _bake(objects, 'NORMAL', 4, max(2, nsize // 256))
    # 3. files, and the one material that uses them
    files = {}
    for tag, img in (('base', base), ('orm', orm), ('normal', nimg), ('emit', emit_img)):
        if img is None:
            continue
        path = os.path.join(tex, f'{name}_{tag}.png')
        _save(img, path, tag in ('base', 'emit'))
        files[tag] = K.load_image(path, srgb_colour=tag in ('base', 'emit'))
        files[tag].name = f'{name}_{tag}'
    m = bpy.data.materials.new(mat_name or name)
    m.use_nodes = True
    nt = m.node_tree
    p = nt.nodes.get('Principled BSDF')
    p.inputs['IOR'].default_value = 1.5

    def tex_node(img):
        n = nt.nodes.new('ShaderNodeTexImage')
        n.image = img
        return n

    nt.links.new(tex_node(files['base']).outputs[0], p.inputs['Base Color'])
    on = tex_node(files['orm'])
    sep = nt.nodes.new('ShaderNodeSeparateColor')
    nt.links.new(on.outputs[0], sep.inputs[0])
    nt.links.new(sep.outputs[1], p.inputs['Roughness'])
    nt.links.new(sep.outputs[2], p.inputs['Metallic'])
    # the exporter takes the occlusion from a group of this name
    grp = bpy.data.node_groups.get('glTF Material Output')
    if grp is None:
        grp = bpy.data.node_groups.new('glTF Material Output', 'ShaderNodeTree')
        grp.interface.new_socket('Occlusion', in_out='INPUT', socket_type='NodeSocketFloat')
    gn = nt.nodes.new('ShaderNodeGroup')
    gn.node_tree = grp
    nt.links.new(sep.outputs[0], gn.inputs[0])
    if 'normal' in files:
        nm = nt.nodes.new('ShaderNodeNormalMap')
        nt.links.new(tex_node(files['normal']).outputs[0], nm.inputs['Color'])
        nt.links.new(nm.outputs[0], p.inputs['Normal'])
    if 'emit' in files:
        nt.links.new(tex_node(files['emit']).outputs[0], p.inputs['Emission Color'])
        p.inputs['Emission Strength'].default_value = 1.0
    for ob in objects:
        me = ob.data
        me.uv_layers.remove(me.uv_layers['src'])
        me.uv_layers.active = me.uv_layers['atlas']
        me.materials.clear()
        me.materials.append(m)
        for poly in me.polygons:
            poly.material_index = 0
        if me.attributes.get('dense'):
            me.attributes.remove(me.attributes['dense'])
    for img in (mimg, base, orm, nimg, emit_img):
        if img is not None:
            bpy.data.images.remove(img)
    return m
