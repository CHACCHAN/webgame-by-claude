"""
One texture atlas over a whole aircraft, painted by numbers (no baking renderer): every face of the given objects is
unwrapped into one square (`unwrap`), each texel learns where on the aircraft it lies (`raster`: position, normal,
zone = the name of the face's material while the model is built), how much of the sky it sees (`occlusion`: ray casts
against the model itself), and a paint function of those gives base colour, occlusion / roughness / metalness, a height
for the normal map and the lamps' glow. `material` wires the four images into one Principled material the glTF exporter
writes as baseColorTexture / metallicRoughnessTexture + occlusionTexture / normalTexture / emissiveTexture.

Arrays are (size, size, n) with row 0 = v 0 (the bottom of the image); positions and normals are in the game frame.
"""
import math
import os

import bmesh
import bpy
import numpy as np
from bpy_extras import mesh_utils
from mathutils.bvhtree import BVHTree


def unwrap(objects, density=None, angle=66.0, margin=0.0025):
    """
    All faces of the objects into one UV square, every island at its true size times its faces' density
    (`density(object, material name)`: 1 = the common texel density; a buried or dark part gets less, a marking more).
    """
    bpy.ops.object.select_all(action='DESELECT')
    for ob in objects:
        me = ob.data
        while me.uv_layers:
            me.uv_layers.remove(me.uv_layers[0])
        me.uv_layers.new(name='atlas')
        ob.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(angle), island_margin=0.0, area_weight=0.0, correct_aspect=True, scale_to_bounds=False)
    bpy.ops.object.mode_set(mode='OBJECT')
    shift = 0
    for oi, ob in enumerate(objects):
        me = ob.data
        uv = me.uv_layers['atlas'].data
        names = [m.name for m in me.materials]
        for isl in mesh_utils.mesh_linked_uv_islands(me):
            loops = [li for pi in isl for li in me.polygons[pi].loop_indices]
            pts = np.array([uv[li].uv[:] for li in loops], dtype=np.float64)
            a3 = sum(me.polygons[pi].area for pi in isl)
            a2 = 0.0
            w = 0.0
            for pi in isl:
                poly = me.polygons[pi]
                q = [uv[li].uv for li in poly.loop_indices]
                a2 += abs(sum(q[i].x * q[(i + 1) % len(q)].y - q[(i + 1) % len(q)].x * q[i].y for i in range(len(q)))) / 2
                w += (density(ob, names[poly.material_index]) if density else 1.0) * poly.area
            scale = math.sqrt(a3 / a2) if a2 > 1e-14 else 0.0
            w = w / max(a3, 1e-12)
            pts = (pts - pts.mean(0)) * scale * w
            # moved apart so that no two islands touch (the packer brings them back)
            for li, q in zip(loops, pts):
                uv[li].uv = (q[0] + 40.0 * (shift % 64), q[1] + 40.0 * (shift // 64))
            shift += 1
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.pack_islands(rotate=True, rotate_method='CARDINAL', scale=True, margin_method='FRACTION', margin=margin, shape_method='CONCAVE')
    bpy.ops.object.mode_set(mode='OBJECT')
    used = area = 0.0
    for ob in objects:
        me = ob.data
        uv = me.uv_layers['atlas'].data
        names = [m.name for m in me.materials]
        for poly in me.polygons:
            q = [uv[li].uv for li in poly.loop_indices]
            used += abs(sum(q[i].x * q[(i + 1) % len(q)].y - q[(i + 1) % len(q)].x * q[i].y for i in range(len(q)))) / 2
            w = density(ob, names[poly.material_index]) if density else 1.0
            area += poly.area * w * w
    ppm = math.sqrt(used / max(area, 1e-9))
    print(f'ATLAS {used * 100:.0f} % in use, {2048 * ppm:.0f} px/m at 2048 px, {len(objects)} objects, {shift} islands')
    return ppm


def _game(a):
    """Blender (x, y, z) arrays -> game (x, z, -y)"""
    return np.stack([a[:, 0], a[:, 2], -a[:, 1]], 1)


def triangles(objects, skip=()):
    """world-space triangles of the objects (game frame): corners (n, 3, 3), corner normals, uv, zone name index, object index"""
    P, N, U, Z, O = [], [], [], [], []
    zones = []
    for oi, ob in enumerate(objects):
        me = ob.data
        me.calc_loop_triangles()
        nt = len(me.loop_triangles)
        if not nt:
            continue
        co = np.zeros(len(me.vertices) * 3, np.float64)
        me.vertices.foreach_get('co', co)
        co = co.reshape(-1, 3)
        M = np.array(ob.matrix_world)
        co = co @ M[:3, :3].T + M[:3, 3]
        tv = np.zeros(nt * 3, np.int32)
        me.loop_triangles.foreach_get('vertices', tv)
        tl = np.zeros(nt * 3, np.int32)
        me.loop_triangles.foreach_get('loops', tl)
        tp = np.zeros(nt, np.int32)
        me.loop_triangles.foreach_get('polygon_index', tp)
        cn = np.zeros(len(me.loops) * 3, np.float64)
        me.corner_normals.foreach_get('vector', cn)
        cn = cn.reshape(-1, 3) @ M[:3, :3].T
        pm = np.zeros(len(me.polygons), np.int32)
        me.polygons.foreach_get('material_index', pm)
        names = [m.name for m in me.materials]
        idx = []
        for n in names:
            if n not in zones:
                zones.append(n)
            idx.append(zones.index(n))
        z = np.array(idx, np.int32)[pm[tp]]
        if me.uv_layers.active is not None:
            uv = np.zeros(len(me.loops) * 2, np.float64)
            me.uv_layers.active.data.foreach_get('uv', uv)
            uv = uv.reshape(-1, 2)[tl].reshape(nt, 3, 2)
        else:
            uv = np.zeros((nt, 3, 2))
        keep = np.array([zones[k] not in skip for k in z])
        P.append(_game(co[tv]).reshape(nt, 3, 3)[keep])
        N.append(_game(cn[tl]).reshape(nt, 3, 3)[keep])
        U.append(uv[keep])
        Z.append(z[keep])
        O.append(np.full(int(keep.sum()), oi, np.int32))
    return np.concatenate(P), np.concatenate(N), np.concatenate(U), np.concatenate(Z), np.concatenate(O), zones


def raster(tris, size, pad=6):
    """
    The atlas' texels: {'pos', 'nrm', 'zone', 'obj', 'cover' (drawn by a face), 'fill' (cover or within `pad` texels of
    it: those carry their nearest covered neighbour's values, so the texture has no seams when it is filtered)}.
    """
    P, N, U, Z, O, zones = tris
    pos = np.zeros((size, size, 3), np.float32)
    nrm = np.zeros((size, size, 3), np.float32)
    zone = np.full((size, size), -1, np.int16)
    obj = np.full((size, size), -1, np.int16)
    UV = U * size
    lo = np.floor(UV.min(1) - 0.5).astype(np.int32)
    hi = np.ceil(UV.max(1) - 0.5).astype(np.int32)
    for t in range(len(P)):
        x0, y0 = max(0, lo[t, 0]), max(0, lo[t, 1])
        x1, y1 = min(size - 1, hi[t, 0]), min(size - 1, hi[t, 1])
        if x1 < x0 or y1 < y0:
            continue
        a, b, c = UV[t]
        den = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(den) < 1e-12:
            continue
        X, Y = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        w0 = ((b[1] - c[1]) * (X - c[0]) + (c[0] - b[0]) * (Y - c[1])) / den
        w1 = ((c[1] - a[1]) * (X - c[0]) + (a[0] - c[0]) * (Y - c[1])) / den
        w2 = 1 - w0 - w1
        m = (w0 >= -1e-4) & (w1 >= -1e-4) & (w2 >= -1e-4)
        if not m.any():
            continue
        yy, xx = np.nonzero(m)
        k0, k1, k2 = w0[m][:, None], w1[m][:, None], w2[m][:, None]
        pos[y0 + yy, x0 + xx] = k0 * P[t, 0] + k1 * P[t, 1] + k2 * P[t, 2]
        nrm[y0 + yy, x0 + xx] = k0 * N[t, 0] + k1 * N[t, 1] + k2 * N[t, 2]
        zone[y0 + yy, x0 + xx] = Z[t]
        obj[y0 + yy, x0 + xx] = O[t]
    cover = zone >= 0
    # nearest covered neighbour, a ring of texels at a time
    src = np.where(cover, np.arange(size * size).reshape(size, size), -1)
    for _ in range(pad):
        todo = src < 0
        if not todo.any():
            break
        new = src.copy()
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (1, -1), (-1, 1), (-1, -1)):
            sh = np.full_like(src, -1)
            ys = slice(max(0, dy), size + min(0, dy))
            yd = slice(max(0, -dy), size + min(0, -dy))
            xs = slice(max(0, dx), size + min(0, dx))
            xd = slice(max(0, -dx), size + min(0, -dx))
            sh[yd, xd] = src[ys, xs]
            take = todo & (new < 0) & (sh >= 0)
            new[take] = sh[take]
        src = new
    fill = src >= 0
    flat = src[fill]
    for arr in (pos, nrm):
        arr[fill] = arr.reshape(-1, 3)[flat]
    zone[fill] = zone.reshape(-1)[flat]
    obj[fill] = obj.reshape(-1)[flat]
    ln = np.linalg.norm(nrm, axis=2, keepdims=True)
    nrm /= np.maximum(ln, 1e-9)
    return {'pos': pos, 'nrm': nrm, 'zone': zone, 'obj': obj, 'cover': cover, 'fill': fill, 'zones': zones, 'size': size}


def _hemisphere(n):
    out = []
    for i in range(n):
        z = math.sqrt((i + 0.5) / n)                # cosine-weighted
        r = math.sqrt(1 - z * z)
        out.append((r * math.cos(i * 2.399963), r * math.sin(i * 2.399963), z))
    return np.array(out)


def occlusion(tris, R, reach=1.6, rays=20, floor=0.0):
    """share of the sky a texel sees (1 = open), by ray casts against the triangles; `floor`: the ground's height or None"""
    P = tris[0]
    verts = [tuple(v) for v in P.reshape(-1, 3)]
    polys = [(3 * i, 3 * i + 1, 3 * i + 2) for i in range(len(P))]
    if floor is not None:
        k = len(verts)
        verts += [(-40, floor, -40), (40, floor, -40), (40, floor, 40), (-40, floor, 40)]
        polys += [(k, k + 1, k + 2), (k, k + 2, k + 3)]
    tree = BVHTree.FromPolygons(verts, polys, all_triangles=True)
    H = _hemisphere(rays)
    size = R['size']
    ao = np.ones((size, size), np.float32)
    ys, xs = np.nonzero(R['fill'])
    pos, nrm = R['pos'], R['nrm']
    from mathutils import Vector
    for y, x in zip(ys, xs):
        n = nrm[y, x].astype(np.float64)
        p = pos[y, x].astype(np.float64) + n * 0.006
        t = np.cross(n, (0.0, 1.0, 0.0) if abs(n[1]) < 0.9 else (1.0, 0.0, 0.0))
        t /= max(np.linalg.norm(t), 1e-9)
        b = np.cross(n, t)
        D = H[:, :1] * t + H[:, 1:2] * b + H[:, 2:3] * n
        o = Vector(p)
        occ = 0.0
        for d in D:
            hit = tree.ray_cast(o, Vector(d), reach)
            if hit[0] is not None:
                occ += (1.0 - hit[3] / reach) ** 1.5
        ao[y, x] = 1.0 - occ / rays
    return ao


def spread(a, R):
    """a per-texel array painted on the covered texels only: its values carried into the padding (as `raster` did)"""
    return a


def resize(a, size):
    """bilinear resize of a square (h, w[, n]) array"""
    h = a.shape[0]
    if h == size:
        return a
    x = (np.arange(size) + 0.5) * h / size - 0.5
    i0 = np.clip(np.floor(x).astype(int), 0, h - 1)
    i1 = np.clip(i0 + 1, 0, h - 1)
    f = np.clip(x - i0, 0, 1)
    fy = f.reshape(-1, 1) if a.ndim == 2 else f.reshape(-1, 1, 1)
    fx = f.reshape(1, -1) if a.ndim == 2 else f.reshape(1, -1, 1)
    top = a[i0][:, i0] * (1 - fx) + a[i0][:, i1] * fx
    bot = a[i1][:, i0] * (1 - fx) + a[i1][:, i1] * fx
    return top * (1 - fy) + bot * fy


def blur(a, r):
    """box blur, r texels, thrice (near a Gaussian)"""
    if r <= 0:
        return a
    out = a.astype(np.float32)
    for _ in range(3):
        for ax in (0, 1):
            c = np.cumsum(np.concatenate([np.repeat(out.take([0], ax), r + 1, ax), out, np.repeat(out.take([-1], ax), r, ax)], ax), ax)
            n = out.shape[ax]
            out = (c.take(range(2 * r + 1, 2 * r + 1 + n), ax) - c.take(range(0, n), ax)) / (2 * r + 1)
    return out


def normal_from_height(h, texel_m, strength=1.0):
    """tangent-space normal map (row 0 = v 0) of a height in metres over the atlas (texel_m = metres a texel)"""
    dx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) / (2 * texel_m)
    dy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) / (2 * texel_m)
    n = np.stack([-dx * strength, -dy * strength, np.ones_like(h)], 2)
    n /= np.linalg.norm(n, axis=2, keepdims=True)
    return n * 0.5 + 0.5


def to_srgb(a):
    a = np.clip(a, 0, 1)
    return np.where(a <= 0.0031308, a * 12.92, 1.055 * np.power(a, 1 / 2.4) - 0.055)


def save(arr, path, srgb):
    """(h, w, 3) floats 0…1 (row 0 = bottom; colour arrays in linear light) -> PNG, and the Blender image of it"""
    h, w = arr.shape[:2]
    rgba = np.ones((h, w, 4), np.float32)
    rgba[..., :3] = to_srgb(arr) if srgb else np.clip(arr, 0, 1)
    img = bpy.data.images.new(os.path.basename(path)[:-4], w, h, alpha=False, float_buffer=False)
    img.colorspace_settings.name = 'sRGB' if srgb else 'Non-Color'
    # (the pixels are stored as given when the image's colour space is sRGB and they are sRGB values in a byte buffer)
    img.pixels.foreach_set(rgba.reshape(-1))
    img.filepath_raw = path
    img.file_format = 'PNG'
    img.save()
    return img


def material(name, files, emission=1.0):
    """one Principled material on the atlas' images {'base', 'orm', 'normal', 'emit'}"""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    p = nt.nodes.get('Principled BSDF')

    def tex(img):
        n = nt.nodes.new('ShaderNodeTexImage')
        n.image = img
        return n

    nt.links.new(tex(files['base']).outputs[0], p.inputs['Base Color'])
    on = tex(files['orm'])
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
    if files.get('normal') is not None:
        nm = nt.nodes.new('ShaderNodeNormalMap')
        nt.links.new(tex(files['normal']).outputs[0], nm.inputs['Color'])
        nt.links.new(nm.outputs[0], p.inputs['Normal'])
    if files.get('emit') is not None:
        nt.links.new(tex(files['emit']).outputs[0], p.inputs['Emission Color'])
        p.inputs['Emission Strength'].default_value = emission
    return m


def apply(objects, mat, keep=()):
    """every face of the objects takes the atlas' material, except those whose material is named in `keep`"""
    for ob in objects:
        me = ob.data
        names = [m.name for m in me.materials]
        kept = [n for n in names if n in keep]
        new = [mat.name] + kept
        remap = [new.index(n) if n in kept else 0 for n in names]
        idx = np.zeros(len(me.polygons), np.int32)
        me.polygons.foreach_get('material_index', idx)
        idx = np.array(remap, np.int32)[idx]
        mats = [mat] + [me.materials[names.index(n)] for n in kept]
        me.materials.clear()
        for m in mats:
            me.materials.append(m)
        me.polygons.foreach_set('material_index', idx)
        me.update()
