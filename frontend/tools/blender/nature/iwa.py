"""
Rocks (岩): boulders of the slopes and the stones at the road's edge. A rock is one function of the direction from
its centre (a ball cut by planes into faces, then cracked and roughened); the three levels of detail are that function
on coarser and coarser octahedral grids, and the texture is the same function at every texel of an octahedral map
(colour with the cavities' shade baked in, and the surface normal in the rock's own frame): the lowest level still
shows every crack of the finest. Four rocks share one texture; the game puts moss on what faces the sky.

    blender --background --factory-startup --python iwa.py -- --out <file.glb> [--render <dir>]
"""
import math
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy  # noqa: E402
import numpy as np  # noqa: E402

import nature_kit as K  # noqa: E402
from twigs import srgb  # noqa: E402

ID = 'iwa'
CELL = 512          # texels of a rock's map (four rocks: a 1024² texture)
PADDING = 6         # texels at a cell's edge that repeat the map's rim
SEGS = (10, 4, 2)   # edge segments of the octahedron per level of detail: 800, 128, 32 triangles
SUNK = 0.28         # how far the rock's centre sits above the ground (× its height scale): the rest is buried


def unit(v):
    return v / (np.linalg.norm(v, axis=-1, keepdims=True) + 1e-12)


class Rock:
    def __init__(self, seed):
        g = np.random.default_rng(seed)
        self.scale = np.array([g.uniform(1.0, 1.35), g.uniform(0.62, 0.9), g.uniform(0.85, 1.1)])
        # the faces: planes that cut the ball, more of them from above and the sides than from below
        n = g.normal(0, 1, (16, 3))
        n[:, 1] = np.abs(n[:, 1]) * 0.9 - 0.25
        self.cut_n = unit(n)
        self.cut_c = g.uniform(0.6, 0.94, 16)
        wave = lambda count, freq: (unit(g.normal(0, 1, (count, 3))) * g.uniform(0.6, 1.4, (count, 1)) * freq, g.uniform(0, 2 * math.pi, count))
        self.lumps, self.ridges, self.grain, self.tone = wave(8, 1.3), wave(10, 3.4), wave(12, 10.0), wave(8, 2.0)
        self.cracks = [(unit(g.normal(0, 1, 3)), g.uniform(-0.3, 0.3), g.uniform(0.008, 0.016)) for _ in range(4)]
        self.strata = unit(g.normal(0, 1, 3) * np.array([0.3, 1.0, 0.3]))

    @staticmethod
    def waves(w, d):
        k, ph = w
        return np.sin(d @ k.T * 2 * math.pi + ph).sum(axis=-1) / math.sqrt(len(ph) / 2)

    def detail(self, d):
        """(ridges, grain, cracks): the fine relief by itself, each about −1…1 (cracks 0…1)"""
        ridge = 1 - 2 * np.abs(self.waves(self.ridges, d)) / 1.6
        crack = np.zeros(d.shape[:-1])
        for m, o, w in self.cracks:
            # (a crack runs part of the way round, not all of it)
            crack = np.maximum(crack, np.exp(-(((d @ m) - o) / w) ** 2) * np.clip(self.waves(self.lumps, d + m) * 1.5 + 0.4, 0, 1))
        return np.clip(ridge, -1, 1), self.waves(self.grain, d), crack

    def point(self, d, fine=True):
        """the surface point in the direction d (unit vectors, any shape … × 3)"""
        r = np.ones(d.shape[:-1])
        acc = r ** -14.0
        for n, c in zip(self.cut_n, self.cut_c):
            acc = acc + (c / np.maximum(d @ n, 1e-3)) ** -14.0
        r = acc ** (-1 / 14.0)
        r = r * (1 + 0.07 * self.waves(self.lumps, d))
        if fine:
            ridge, grain, crack = self.detail(d)
            r = r * (1 + 0.03 * ridge + 0.009 * grain - 0.05 * crack)
        p = d * r[..., None] * self.scale
        p[..., 1] += SUNK * self.scale[1]
        return p

    def normal(self, d, fine=True, eps=2e-3):
        a = unit(np.cross(d, np.where(np.abs(d[..., 1:2]) < 0.9, [0.0, 1.0, 0.0], [1.0, 0.0, 0.0])))
        b = np.cross(d, a)
        p0 = self.point(d, fine)
        n = unit(np.cross(self.point(unit(d + a * eps), fine) - p0, self.point(unit(d + b * eps), fine) - p0))
        return n * np.sign(np.sum(n * d, axis=-1, keepdims=True))


def octa_dirs(n):
    """the vertices (directions, octahedral uv in −1…1) and triangles of an octahedron with n segments per edge"""
    D, UV, T = [], [], []
    for sx in (1, -1):
        for sy in (1, -1):
            for sz in (1, -1):
                base = len(D)
                idx = {}
                for i in range(n + 1):
                    for j in range(n + 1 - i):
                        a, c = i / n, j / n
                        b = 1 - a - c
                        idx[(i, j)] = base + len(idx)
                        D.append((a * sx, b * sy, c * sz))
                        UV.append((a * sx, c * sz) if sy > 0 else ((1 - c) * sx, (1 - a) * sz))
                flip = sx * sy * sz < 0
                for i in range(n):
                    for j in range(n - i):
                        tris = [(idx[(i, j)], idx[(i + 1, j)], idx[(i, j + 1)])]
                        if j < n - i - 1:
                            tris.append((idx[(i + 1, j)], idx[(i + 1, j + 1)], idx[(i, j + 1)]))
                        for t in tris:
                            T.append(t if flip else (t[0], t[2], t[1]))
    return unit(np.array(D, float)), np.array(UV, float), np.array(T, int)


def texel_dirs():
    """the direction of every texel of a cell (rows top to bottom); the padding repeats the map's rim"""
    t = ((np.arange(CELL) + 0.5) / CELL - 0.5) / (0.5 - PADDING / CELL)
    u, v = np.meshgrid(np.clip(t, -1, 1), np.clip(t, -1, 1))
    au, av = np.abs(u), np.abs(v)
    upper = au + av <= 1
    x = np.where(upper, u, (1 - av) * np.sign(u))
    z = np.where(upper, v, (1 - au) * np.sign(v))
    y = np.where(upper, 1 - au - av, -(au + av - 1))
    return unit(np.stack([x, y, z], axis=-1))


def cell_uv(uv, k):
    """octahedral uv (−1…1) → the texture's (x right, y down, 0…1) inside the k-th cell"""
    s = uv * (0.5 - PADDING / CELL) + 0.5
    return np.stack([(k % 2 + s[:, 0]) / 2, (k // 2 + s[:, 1]) / 2], axis=1)


def bake(rock, seed):
    """colour (sRGB, the cavities' shade in it) and normal (the rock's frame; alpha: how gladly moss grows there)"""
    g = np.random.default_rng(seed)
    d = texel_dirs()
    n = rock.normal(d)
    ridge, grain, crack = rock.detail(d)
    p = rock.point(d)
    # shade: the cracks and the troughs between the ridges, and the foot where the ground is near
    ao = np.clip(1 - 0.6 * crack - 0.14 * np.clip(-ridge, 0, 1) - 0.07 * np.clip(-grain, 0, 1), 0.3, 1)
    ao = ao * (0.62 + 0.38 * np.clip(p[..., 1] / 0.45, 0, 1))
    tone = np.clip(rock.waves(rock.tone, d) * 0.22 + 0.5, 0, 1)[..., None]
    col = srgb('#5b5750') + (srgb('#77726a') - srgb('#5b5750')) * tone
    # the beds of the stone, tilted, and the weathering that browns the faces turned up
    beds = np.sin((p @ rock.strata) * 34 + rock.waves(rock.lumps, d) * 2.5)
    col = col * (1 + 0.05 * beds[..., None])
    rust = np.clip(rock.waves(rock.tone, d[..., ::-1]) - 0.7, 0, 1)[..., None]
    col = col + (srgb('#6e5a44') - col) * rust * 0.35
    col = col * (1 + g.normal(0, 0.035, d.shape[:2]))[..., None]
    lichen = np.clip((rock.waves(rock.ridges, d[..., ::-1] * 1.7) - 1.15) * 5, 0, 1) * np.clip(n[..., 1] * 2 + 0.4, 0, 1)
    col = col + (srgb('#a3a58c') - col) * lichen[..., None] * 0.6
    col = col * ao[..., None]
    moss = np.clip(0.5 + 0.35 * rock.waves(rock.lumps, d * 1.9) - 0.25 * ridge + 0.4 * crack, 0, 1)
    return np.dstack([K.lin2srgb(col), np.ones(d.shape[:2])]), np.dstack([n * 0.5 + 0.5, moss])


def mesh(rock, k, segs):
    d, uv, tris = octa_dirs(segs)
    # (a coarse level takes its vertices from the smooth shape: a crack's edge between two vertices would dent it)
    fine = segs >= 8
    P, N = rock.point(d, fine), rock.normal(d, fine)
    C = np.zeros((len(P), 4))
    C[:, 0] = 1
    return P, N, cell_uv(uv, k), C, tris


def sheet(out_dir, rocks, lods, col_png, nrm_png):
    """every rock's three levels side by side in daylight, with their triangle counts"""
    from mathutils import Vector
    os.makedirs(out_dir, exist_ok=True)
    K.clear_scene()
    sc = bpy.context.scene
    m = bpy.data.materials.new('rock')
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes['Principled BSDF']
    tex = nt.nodes.new('ShaderNodeTexImage')
    tex.image = bpy.data.images.load(col_png)
    nt.links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = 0.9
    # the normal map is in the game's axes (y up): Blender's are (x, −z, y)
    tn = nt.nodes.new('ShaderNodeTexImage')
    tn.image = bpy.data.images.load(nrm_png)
    tn.image.colorspace_settings.name = 'Non-Color'
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(tn.outputs['Color'], sep.inputs[0])
    comb = nt.nodes.new('ShaderNodeCombineXYZ')
    for src, dst, sign in (('X', 'X', 1), ('Z', 'Y', -1), ('Y', 'Z', 1)):
        f = nt.nodes.new('ShaderNodeMath')
        f.operation = 'MULTIPLY_ADD'
        nt.links.new(sep.outputs[src], f.inputs[0])
        f.inputs[1].default_value = 2 * sign
        f.inputs[2].default_value = -sign
        nt.links.new(f.outputs[0], comb.inputs[dst])
    nt.links.new(comb.outputs[0], bsdf.inputs['Normal'])
    font = bpy.data.materials.new('label')
    font.use_nodes = True
    font.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.9, 0.9, 0.9, 1)
    x = 0.0
    for k in range(len(rocks)):
        for l in range(3):
            ob = K.to_object(f'v{k}_lod{l}', lods[k][l], m)
            ob.location = (x + 1.3, 0, 0)
            cu = bpy.data.curves.new('txt', 'FONT')
            cu.body = f'v{k} lod{l}: {ob["tris"]} tris'
            cu.size = 0.24
            cu.align_x = 'CENTER'
            tx = bpy.data.objects.new('txt', cu)
            tx.location = (x + 1.3, -1.7, 0.02)
            tx.data.materials.append(font)
            sc.collection.objects.link(tx)
            x += 2.6
    import bmesh
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=x * 3)
    me = bpy.data.meshes.new('ground')
    bm.to_mesh(me)
    gr = bpy.data.objects.new('ground', me)
    sc.collection.objects.link(gr)
    gm = bpy.data.materials.new('ground')
    gm.use_nodes = True
    gm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.16, 0.15, 0.13, 1)
    me.materials.append(gm)
    world = bpy.data.worlds.new('sky')
    sc.world = world
    world.use_nodes = True
    world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.55, 0.68, 0.9, 1)
    world.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.9
    sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN'))
    sun.data.energy = 3.2
    sun.rotation_euler = (math.radians(55), 0, math.radians(35))
    sc.collection.objects.link(sun)
    W, H = 2400, 420
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.data.lens = 60
    dist = x * 0.53 / math.tan(math.atan(18 / 60))
    eye = Vector((x / 2, -dist, dist * 0.3))
    cam.location = eye
    cam.rotation_euler = (Vector((x / 2, 0, 0.2)) - eye).to_track_quat('-Z', 'Y').to_euler()
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.samples = 48
    sc.cycles.use_denoising = False
    sc.render.threads_mode = 'FIXED'
    sc.render.threads = 8
    sc.view_settings.view_transform = 'AgX'
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = W, H, 100
    try:
        sc.render.image_settings.media_type = 'IMAGE'
    except Exception:
        pass
    sc.render.image_settings.file_format = 'PNG'
    sc.render.filepath = os.path.join(out_dir, f'{ID}_sheet.png')
    bpy.ops.render.render(write_still=True)
    import shutil
    for f in (col_png, nrm_png):
        shutil.copy(f, os.path.join(out_dir, os.path.basename(f)))
    print('SHEET', sc.render.filepath)


def run():
    opt = K.parse_args()
    out = opt['out']
    if not out:
        raise SystemExit('usage: blender --background --factory-startup --python iwa.py -- --out <file.glb> [--render <dir>]')
    stem = os.path.join(os.path.dirname(os.path.abspath(out)), ID)
    rocks = [Rock(900 + k) for k in range(4)]
    col = np.zeros((2 * CELL, 2 * CELL, 4))
    nrm = np.zeros((2 * CELL, 2 * CELL, 4))
    for k, r in enumerate(rocks):
        c, n = bake(r, 950 + k)
        ys, xs = slice((k // 2) * CELL, (k // 2 + 1) * CELL), slice((k % 2) * CELL, (k % 2 + 1) * CELL)
        col[ys, xs], nrm[ys, xs] = c, n
    col_png, nrm_png = K.save_png(stem + '_rock.png', col), K.save_png(stem + '_rock_n.png', nrm)
    lods = [[mesh(r, k, s) for s in SEGS] for k, r in enumerate(rocks)]
    K.clear_scene()
    mat = K.named_material('rock')
    objs = []
    for k in range(len(rocks)):
        for l in range(3):
            ob = K.to_object(f'v{k}_lod{l}', lods[k][l], mat)
            objs.append(ob)
            print(f'TRIS {ID} v{k} lod{l}: {ob["tris"]}')
    K.export_glb(out, objs)
    print(f'NATURE {ID}: {len(rocks)} variants, {os.path.getsize(out) / 1024:.0f} KiB raw')
    if opt['render']:
        sheet(opt['render'], rocks, lods, col_png, nrm_png)


if __name__ == '__main__':
    run()
