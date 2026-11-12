"""
What the car models share (tools/blender/cars/<id>.py call it after their own build, before the export).

The game swaps a car's paint, accent, glass and lamp materials by name and keeps every other material as the GLB has
it; each material of each moving part (body, a pop-up pod, a wheel, a caliper) is a draw call, and one more in every
shadow map. So what is not swapped is gathered here:

  * `Atlas` + `consolidate()`: every plain material of the body (black plastics, chrome, the cabin, the underside, the
    number plate, the small lamps) becomes ONE material `trim` whose texture holds a swatch per old material (and the
    old materials' own images as regions); the wheels' rims, discs and calipers become ONE material `rim` the same
    way. A swatch has its colour, roughness and metalness (base colour + ORM textures).
  * `bake_ao()`: how much of the sky every corner of these parts sees (rays against the whole car and the ground),
    stored as a vertex colour that the atlas materials multiply into their colour: wheel wells, the underside, the
    cabin and the gaps behind spokes go dark by themselves. A wheel is lit by its own parts only (it turns).
  * `tyre()` + `tyre_material()`: a tyre with a real section (sidewall bulge, shoulder, grooves cut into the tread)
    and its texture set (tread blocks and sipes, raised lettering and ribs on the sidewall as a normal map).
  * `brake_disc()`, `caliper()`: a ventilated disc with its hat and scored faces, a floating or a four-piston caliper.
  * `underbody()`: what the chase camera sees under the tail and a low camera under the nose: engine sump, gearbox,
    propshaft, differential, axle or driveshafts, links, the exhaust line with its silencers, the fuel tank, rails.

Frame: the game's car frame (x = the car's left, y up, z forward; hayate_kit.B turns it into Blender's). The mesh kit
is hayate_kit (the first car's; nothing in it is about that car).
"""
import math
import re

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

import hayate_kit as K

FONT = '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'
FONT_BLACK = '/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc'

# the materials the game takes over by name (render/CarModel.ts LIVE_MATERIALS, the pop-up lens by its own name)
LIVE = {'paint', 'accent', 'glass', 'headlight', 'taillight', 'popup_lens'}
# a mesh found again by its name (CarModel.deriveAnchors: the tailpipe) stays an object of its own
KEEP = re.compile(r'muffler|exhaust|tailpipe', re.I)
WHEEL = re.compile(r'^(wheel_|spin_)')

# swatches of the shared parts: name → (colour, roughness, metalness)
SWATCHES = {
    # underside
    'u_seal': ('#0c0c0d', 0.92, 0.0),        # underseal on the floor and rails
    'u_black': ('#111214', 0.70, 0.1),       # painted arms, axle, crossmembers
    'u_cast': ('#4b4c4b', 0.62, 0.85),       # cast aluminium (sump, gearbox, diff), dull and dusty
    'u_iron': ('#2b2a29', 0.75, 0.7),        # cast iron
    'u_steel': ('#3c3c3d', 0.50, 0.9),       # shafts, links
    'u_exhaust': ('#5d554b', 0.52, 0.95),    # the exhaust's steel, browned by heat
    'u_zinc': ('#5c6062', 0.55, 0.85),       # tank, heat shields
    'u_rubber': ('#0a0a0a', 0.85, 0.0),      # boots, bushes
    # brakes
    'disc': ('#8a8b8d', 0.34, 1.0),          # (the friction faces take disc_image() when the atlas has it)
    'disc_edge': ('#55504b', 0.60, 0.9),
    'disc_vent': ('#141312', 0.85, 0.3),
    'disc_hat': ('#33312f', 0.68, 0.8),
    'cal_iron': ('#3d3e40', 0.62, 0.75),     # bare cast-iron caliper
    'cal_red': ('#a3140f', 0.38, 0.1),
    'cal_gold': ('#a8842a', 0.36, 0.55),
    'cal_black': ('#101011', 0.40, 0.2),
    'cal_blue': ('#1a3fa0', 0.38, 0.15),
    'cal_bolt': ('#8f9296', 0.40, 1.0),
    'pad': ('#1c1b1a', 0.9, 0.1),
}


def srgb_f(hex_colour):
    """'#rrggbb' → sRGB floats"""
    h = hex_colour.lstrip('#')
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def _to_srgb(lin):
    lin = np.clip(np.asarray(lin, np.float32), 0, 1)
    return np.where(lin <= 0.0031308, lin * 12.92, 1.055 * np.power(lin, 1 / 2.4) - 0.055)


def _to_lin(s):
    s = np.clip(np.asarray(s, np.float32), 0, 1)
    return np.where(s <= 0.04045, s / 12.92, np.power((s + 0.055) / 1.055, 2.4))


def material_for(mats, name):
    """mats[name], made from SWATCHES when a car's own list has none of that name"""
    if name not in mats:
        colour, rough, metal = SWATCHES[name]
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        p = m.node_tree.nodes.get('Principled BSDF')
        p.inputs['Base Color'].default_value = K.srgb(colour)
        p.inputs['Roughness'].default_value = rough
        p.inputs['Metallic'].default_value = metal
        m.diffuse_color = K.srgb(colour)
        mats[name] = m
    return mats[name]


def build(mesh, parent, mats, sharp_deg=None, name=None):
    """K.Mesh.build with the shared swatches' materials made on demand"""
    for s in mesh.slots:
        material_for(mats, s)
    return mesh.build(parent, mats, sharp_deg=sharp_deg, name=name)


# ---------------------------------------------------------------------------------------------------- images

def new_image(name, arr, colour=True):
    """a packed image from an (h, w, 3) float array, row 0 = bottom (sRGB values for colour, raw data otherwise)"""
    h, w = arr.shape[:2]
    rgba = np.ones((h, w, 4), np.float32)
    rgba[..., :3] = np.clip(arr, 0, 1)
    img = bpy.data.images.new(name, w, h, alpha=False)
    if not colour:
        img.colorspace_settings.name = 'Non-Color'
    img.pixels.foreach_set(rgba.ravel())
    img.pack()
    return img


def text_mask(text, w, h, height=0.8, font=None, spacing=1.0, centre=0.5):
    """the text as a coverage mask (h, w), row 0 = bottom: cap height = `height` × h (less if it would not fit the
    width), centred at `centre` × w. Our own lettering: Noto Sans CJK shapes rasterised from Blender's text curves."""
    cu = bpy.data.curves.new('mask_text', 'FONT')
    cu.body = text
    cu.font = bpy.data.fonts.load(font or FONT, check_existing=True)
    cu.size = 1.0
    cu.space_character = spacing
    cu.align_x = 'CENTER'
    cu.resolution_u = 4
    ob = bpy.data.objects.new('mask_text', cu)
    bpy.context.scene.collection.objects.link(ob)
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    me.calc_loop_triangles()
    P = np.array([v.co[:2] for v in me.vertices], np.float64)
    T = np.array([t.vertices[:] for t in me.loop_triangles], np.int64)
    ev.to_mesh_clear()
    bpy.data.objects.remove(ob)
    bpy.data.curves.remove(cu)
    out = np.zeros((h, w), np.float32)
    if not len(T):
        return out
    lo, hi = P.min(0), P.max(0)
    scale = min(height * h / (hi[1] - lo[1]), 0.96 * w / (hi[0] - lo[0]))
    P = (P - (lo + hi) / 2) * scale + np.array([centre * w, h / 2])
    ss = 2                                       # 2 × 2 samples a pixel
    for a, b, c in P[T]:
        x0, x1 = int(max(0, math.floor(min(a[0], b[0], c[0])))), int(min(w, math.ceil(max(a[0], b[0], c[0])) + 1))
        y0, y1 = int(max(0, math.floor(min(a[1], b[1], c[1])))), int(min(h, math.ceil(max(a[1], b[1], c[1])) + 1))
        if x1 <= x0 or y1 <= y0:
            continue
        d = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(d) < 1e-12:
            continue
        xs = (np.arange(x0 * ss, x1 * ss) + 0.5) / ss
        ys = (np.arange(y0 * ss, y1 * ss) + 0.5) / ss
        X, Y = np.meshgrid(xs, ys)
        l1 = ((b[1] - c[1]) * (X - c[0]) + (c[0] - b[0]) * (Y - c[1])) / d
        l2 = ((c[1] - a[1]) * (X - c[0]) + (a[0] - c[0]) * (Y - c[1])) / d
        inside = ((l1 >= 0) & (l2 >= 0) & (l1 + l2 <= 1)).astype(np.float32)
        cov = inside.reshape(y1 - y0, ss, x1 - x0, ss).mean((1, 3))
        out[y0:y1, x0:x1] = np.maximum(out[y0:y1, x0:x1], cov)
    return out


def blur(a, r, wrap_u=True):
    """a box blur of radius r pixels, twice (rows wrap in u when the texture tiles)"""
    if r <= 0:
        return a
    k = 2 * r + 1
    for _ in range(2):
        p = np.pad(a, ((0, 0), (r, r)), mode='wrap' if wrap_u else 'edge')
        c = np.cumsum(np.pad(p, ((0, 0), (1, 0))), 1)
        a = (c[:, k:] - c[:, :-k]) / k
        p = np.pad(a, ((r, r), (0, 0)), mode='edge')
        c = np.cumsum(np.pad(p, ((1, 0), (0, 0))), 0)
        a = (c[k:] - c[:-k]) / k
    return a.astype(np.float32)


def normal_from_height(hm, du, dv, wrap_u=True):
    """a tangent-space normal map (OpenGL: +v up) from heights in metres; du, dv: metres per pixel"""
    hu = (np.roll(hm, -1, 1) - np.roll(hm, 1, 1)) / (2 * du)
    if not wrap_u:
        hu[:, 0] = hu[:, 1]
        hu[:, -1] = hu[:, -2]
    hv = np.gradient(hm, axis=0) / dv
    n = np.stack([-hu, -hv, np.ones_like(hm)], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return (n * 0.5 + 0.5).astype(np.float32)


def noise(h, w, cells_u, cells_v, seed=1):
    """smooth value noise that tiles in u: (h, w) in 0..1"""
    rng = np.random.default_rng(seed)
    g = rng.random((cells_v + 1, cells_u), dtype=np.float32)
    u = (np.arange(w) + 0.5) / w * cells_u
    v = (np.arange(h) + 0.5) / h * cells_v
    iu, fu = np.floor(u).astype(int) % cells_u, u % 1.0
    iv, fv = np.minimum(np.floor(v).astype(int), cells_v - 1), v % 1.0
    fu, fv = fu * fu * (3 - 2 * fu), fv * fv * (3 - 2 * fv)
    a = g[iv][:, iu]
    b = g[iv][:, (iu + 1) % cells_u]
    c = g[iv + 1][:, iu]
    d = g[iv + 1][:, (iu + 1) % cells_u]
    return (a * (1 - fu) + b * fu) * (1 - fv)[:, None] + (c * (1 - fu) + d * fu) * fv[:, None]


# ---------------------------------------------------------------------------------------------------- the atlas

class Atlas:
    """
    One texture set for many plain materials: a cell per material (its colour; roughness and metalness in the ORM
    texture), cells from the top left, and regions for the materials that had an image, packed from the bottom left.
    """

    def __init__(self, name, size=1024, cell=32, fill=('#0f1012', 0.7, 0.0)):
        self.name, self.n, self.cell = name, size, cell
        self.base = np.empty((size, size, 3), np.float32)
        self.base[:] = srgb_f(fill[0])
        self.orm = np.empty((size, size, 3), np.float32)
        self.orm[:] = (1.0, fill[1], fill[2])
        self.where = {}
        self._cells = 0
        self._shelf = [0, 0, 0]
        self._material = None

    def swatch(self, name, colour, rough=0.6, metal=0.0):
        """colour: '#rrggbb' or sRGB floats"""
        if name in self.where:
            return
        per = self.n // self.cell
        i, j = self._cells % per, self._cells // per
        self._cells += 1
        y1 = self.n - j * self.cell
        y0, x0 = y1 - self.cell, i * self.cell
        assert y0 >= self._shelf[1] + self._shelf[2], f'atlas {self.name} is full'
        self.base[y0:y1, x0:x0 + self.cell] = srgb_f(colour) if isinstance(colour, str) else colour
        self.orm[y0:y1, x0:x0 + self.cell] = (1.0, rough, metal)
        self.where[name] = ('cell', (x0 + self.cell / 2) / self.n, (y0 + self.cell / 2) / self.n)

    def region(self, name, rgb, rough=0.6, metal=0.0, orm=None, pad=4):
        """rgb: (h, w, 3) sRGB floats, row 0 = bottom; the faces' UVs (0..1) are moved into its place"""
        if name in self.where:
            return
        h, w = rgb.shape[:2]
        x, y, rh = self._shelf
        if x + w + 2 * pad > self.n:
            x, y, rh = 0, y + rh, 0
        cells_bottom = self.n - (-(-self._cells // (self.n // self.cell))) * self.cell
        assert y + h + 2 * pad <= cells_bottom, f'atlas {self.name} is full'
        self.base[y:y + h + 2 * pad, x:x + w + 2 * pad] = np.pad(rgb[..., :3], ((pad, pad), (pad, pad), (0, 0)), mode='edge')
        if orm is None:
            self.orm[y:y + h + 2 * pad, x:x + w + 2 * pad] = (1.0, rough, metal)
        else:
            self.orm[y:y + h + 2 * pad, x:x + w + 2 * pad] = np.pad(orm, ((pad, pad), (pad, pad), (0, 0)), mode='edge')
        self.where[name] = ('rect', (x + pad) / self.n, (y + pad) / self.n, (x + pad + w) / self.n, (y + pad + h) / self.n)
        self._shelf = [x + w + 2 * pad, y, max(rh, h + 2 * pad)]

    def adopt(self, mat, name=None):
        """a place for a Blender material: its Principled colour / roughness / metalness, or its image as a region"""
        name = name or mat.name
        if name in self.where:
            return
        p = mat.node_tree.nodes.get('Principled BSDF')
        rough = p.inputs['Roughness'].default_value
        metal = p.inputs['Metallic'].default_value
        sock = p.inputs['Base Color']
        img, tint = None, None
        if sock.is_linked:
            n = sock.links[0].from_node
            if n.type == 'MIX':            # image × colour (whichever of the node's A / B pairs was wired)
                a = next((i for i in n.inputs if i.name == 'A' and i.is_linked), None)
                b = n.inputs[7]
                tint = np.array(b.default_value[:3], np.float32)
                n = a.links[0].from_node if a is not None else None
            if n is not None and n.type == 'TEX_IMAGE':
                img = n.image
        if img is None:
            self.swatch(name, tuple(_to_srgb(np.array(sock.default_value[:3]))), rough, metal)
            return
        w, h = img.size
        px = np.empty(w * h * 4, np.float32)
        img.pixels.foreach_get(px)
        rgb = px.reshape(h, w, 4)[..., :3]
        if tint is not None:
            rgb = _to_srgb(_to_lin(rgb) * tint)
        self.region(name, rgb, rough, metal)

    def material(self):
        if self._material is None:
            _free_name(self.name)
            m = bpy.data.materials.new(self.name)
            m.use_nodes = True
            nt = m.node_tree
            p = nt.nodes.get('Principled BSDF')
            base = nt.nodes.new('ShaderNodeTexImage')
            base.image = new_image(f'{self.name}_base', self.base)
            orm = nt.nodes.new('ShaderNodeTexImage')
            orm.image = new_image(f'{self.name}_orm', self.orm, colour=False)
            _tinted_base(nt, p, base)
            sep = nt.nodes.new('ShaderNodeSeparateColor')
            nt.links.new(orm.outputs[0], sep.inputs[0])
            nt.links.new(sep.outputs[1], p.inputs['Roughness'])
            nt.links.new(sep.outputs[2], p.inputs['Metallic'])
            m.diffuse_color = (*_to_lin(self.base.mean((0, 1))), 1.0)
            self._material = m
        return self._material


def _free_name(name):
    """a material of this name gives it up (Blender would call the new one name.001, and the game goes by names)"""
    old = bpy.data.materials.get(name)
    if old is not None:
        old.name = f'{name}_src'


def _tinted_base(nt, p, tex):
    """base colour = texture × the vertex colour `Col` (the baked sky share): the exporter writes it as COLOR_0"""
    col = nt.nodes.new('ShaderNodeVertexColor')
    col.layer_name = 'Col'
    mix = nt.nodes.new('ShaderNodeMix')
    mix.data_type = 'RGBA'
    mix.blend_type = 'MULTIPLY'
    mix.inputs['Factor'].default_value = 1.0
    # (a Mix node has an A / B / Result per data type: the colour ones are 6, 7 and 2)
    nt.links.new(tex.outputs['Color'], mix.inputs[6])
    nt.links.new(col.outputs['Color'], mix.inputs[7])
    nt.links.new(mix.outputs[2], p.inputs['Base Color'])


# ---------------------------------------------------------------------------------------------------- consolidation

def _pivot(obj):
    p = obj.parent
    while p is not None and p.type == 'MESH':
        p = p.parent
    return p


def _under_wheel(obj):
    p = obj
    while p is not None:
        if WHEEL.match(p.name):
            return p
        p = p.parent
    return None


def apply_modifiers(root):
    dg = bpy.context.evaluated_depsgraph_get()
    for o in [o for o in root.children_recursive if o.type == 'MESH' and len(o.modifiers)]:
        me = bpy.data.meshes.new_from_object(o.evaluated_get(dg))
        o.modifiers.clear()
        o.data = me


def consolidate(root, trim, rim, keep=LIVE, own=('tire',)):
    """
    Move every face whose material is neither swapped by the game (`keep`) nor has a texture set of its own (`own`)
    into one object per moving part, with the atlas material: `rim` for what hangs on a wheel, `trim` for the rest.
    Returns the new objects.
    """
    bpy.context.view_layer.update()
    apply_modifiers(root)
    bpy.context.view_layer.update()
    skip = set(keep) | set(own)
    targets = {}                # (pivot name | object name, atlas name) → dict(bm, uv, parent, atlas, name, obj)
    for o in [o for o in root.children_recursive if o.type == 'MESH']:
        me = o.data
        names = [m.name if m else None for m in me.materials]
        if not any(n and n not in skip for n in names):
            continue
        atlas = rim if _under_wheel(o) is not None else trim
        for m in me.materials:
            if m and m.name not in skip:
                atlas.adopt(m)
        pivot = _pivot(o)
        named = bool(KEEP.search(o.name))
        key = (o.name if named else pivot.name, atlas.name)
        t = targets.get(key)
        if t is None:
            bm = bmesh.new()
            t = targets[key] = dict(bm=bm, uv=bm.loops.layers.uv.new('UVMap'), parent=pivot, atlas=atlas,
                                    name=o.name if named else f'{pivot.name}_{atlas.name}')
        src = bmesh.new()
        src.from_mesh(me)
        suv = src.loops.layers.uv.active
        M = pivot.matrix_world.inverted() @ o.matrix_world
        vmap, moved = {}, []
        for f in src.faces:
            n = names[f.material_index] if f.material_index < len(names) else None
            if n is None or n in skip:
                continue
            moved.append(f)
            vs = []
            for v in f.verts:
                if v not in vmap:
                    vmap[v] = t['bm'].verts.new(M @ v.co)
                vs.append(vmap[v])
            try:
                nf = t['bm'].faces.new(vs)
            except ValueError:
                continue
            nf.smooth = f.smooth
            w = atlas.where[n]
            for l0, l1 in zip(f.loops, nf.loops):
                if w[0] == 'cell':
                    l1[t['uv']].uv = (w[1], w[2])
                else:
                    uv = l0[suv].uv if suv is not None else (0.5, 0.5)
                    l1[t['uv']].uv = (w[1] + min(1.0, max(0.0, uv[0])) * (w[3] - w[1]), w[2] + min(1.0, max(0.0, uv[1])) * (w[4] - w[2]))
        # the sharp edges go with the faces
        for e in src.edges:
            if not e.smooth and e.verts[0] in vmap and e.verts[1] in vmap:
                ne = t['bm'].edges.get((vmap[e.verts[0]], vmap[e.verts[1]]))
                if ne is not None:
                    ne.smooth = False
        if len(moved) == len(src.faces):
            src.free()
            bpy.data.objects.remove(o)
            continue
        bmesh.ops.delete(src, geom=moved, context='FACES')
        src.to_mesh(me)
        src.free()
    out = []
    for t in targets.values():
        me = bpy.data.meshes.new(t['name'])
        t['bm'].to_mesh(me)
        t['bm'].free()
        me.materials.append(t['atlas'].material())
        ob = bpy.data.objects.new(t['name'], me)
        bpy.context.scene.collection.objects.link(ob)
        ob.parent = t['parent']
        out.append(ob)
    bpy.context.view_layer.update()
    return out


# ---------------------------------------------------------------------------------------------------- sky share

def _hemisphere(n):
    """n directions over the hemisphere about +z, cosine weighted (a fixed, even pattern)"""
    out = []
    g = (1 + 5 ** 0.5) / 2
    for i in range(n):
        r = math.sqrt((i + 0.5) / n)
        a = 2 * math.pi * i / g
        out.append(Vector((r * math.cos(a), r * math.sin(a), math.sqrt(max(0.0, 1 - r * r)))))
    return out


def _occluders(objects, skip=('glass',), ground=None):
    verts, polys = [], []
    for o in objects:
        me = o.data
        names = [m.name if m else '' for m in me.materials]
        M = o.matrix_world
        base = len(verts)
        verts.extend(M @ v.co for v in me.vertices)
        for p in me.polygons:
            if names and names[p.material_index] in skip:
                continue
            polys.append([base + i for i in p.vertices])
    if ground is not None:
        base = len(verts)
        verts.extend(Vector(c) for c in ((-20, -20, ground), (20, -20, ground), (20, 20, ground), (-20, 20, ground)))
        polys.append([base, base + 1, base + 2, base + 3])
    return BVHTree.FromPolygons(verts, polys, all_triangles=False)


def bake_ao(root, objects, reach=0.55, rays=24, floor=0.16, power=0.9):
    """
    The vertex colour `Col` of `objects`: the share of the sky each corner sees, floor … 1. Occluders: every mesh of
    the car but the glass, and the ground; for what hangs on a wheel, that wheel's own parts only (it turns).
    """
    bpy.context.view_layer.update()
    meshes = [o for o in root.children_recursive if o.type == 'MESH']
    body = [o for o in meshes if _under_wheel(o) is None]
    everything = _occluders(meshes, ground=0.0)
    wheels = {}
    dirs = _hemisphere(rays)
    for o in objects:
        w = _under_wheel(o)
        if w is None:
            bvh = everything
        else:
            # the pivot of the whole wheel (wheel_xx), also for what hangs on its spin node
            while w.parent is not None and WHEEL.match(w.parent.name):
                w = w.parent
            if w.name not in wheels:
                wheels[w.name] = _occluders([m for m in meshes if m is w or w in _ancestors(m)])
            bvh = wheels[w.name]
        me = o.data
        M = o.matrix_world
        R = M.to_3x3()
        cols = np.ones((len(me.loops), 4), np.float32)
        cache = {}
        normals = me.corner_normals
        for li, loop in enumerate(me.loops):
            nrm = normals[li].vector
            key = (loop.vertex_index, round(nrm.x, 2), round(nrm.y, 2), round(nrm.z, 2))
            c = cache.get(key)
            if c is None:
                n = (R @ nrm).normalized()
                p = M @ me.vertices[loop.vertex_index].co + n * 0.004
                t = n.orthogonal().normalized()
                b = n.cross(t)
                hit = 0.0
                for d in dirs:
                    w_ = t * d.x + b * d.y + n * d.z
                    loc, _, _, dist = bvh.ray_cast(p, w_, reach)
                    if loc is not None:
                        hit += 1.0 - 0.6 * dist / reach
                c = cache[key] = floor + (1 - floor) * max(0.0, 1 - hit / rays) ** power
            cols[li, :3] = c
        attr = me.color_attributes.get('Col') or me.color_attributes.new('Col', 'FLOAT_COLOR', 'CORNER')
        attr.data.foreach_set('color', cols.ravel())
        me.color_attributes.active_color = attr
        me.color_attributes.render_color_index = me.color_attributes.find('Col')
        me.update()


def _ancestors(o):
    out = []
    p = o.parent
    while p is not None:
        out.append(p)
        p = p.parent
    return out


# ---------------------------------------------------------------------------------------------------- tyres

def tyre(mesh, r_out, r_rim, width, rim_width, grooves=3, seg=48, repeats=4, mat='tire'):
    """
    A tyre for a LEFT wheel round the origin (outer face +x): inner bead → sidewall → shoulder → tread with
    `grooves` cut round it → outer bead. UV: u = round the wheel (`repeats` tiles), v: 0 … 0.25 the inner sidewall,
    0.25 … 0.75 across the tread (by x), 0.75 … 1 the outer sidewall. Returns what the texture needs to know.
    """
    W, H = width, r_out - r_rim
    hb = rim_width / 2
    T = W / 2 - 0.014                    # half the tread zone (shoulder to shoulder)
    # the sidewall, bead → shoulder (x negative: the inner side), a smooth curve through these
    side = K.Spline([(-(hb + 0.013), r_rim + 0.024), (-(W / 2 - 0.004), r_rim + 0.34 * H), (-W / 2, r_rim + 0.54 * H),
                     (-(W / 2 - 0.004), r_rim + 0.75 * H), (-(W / 2 - 0.010), r_out - 0.024), (-(T + 0.004), r_out - 0.010),
                     (-T, r_out - 0.0045)])
    half = [(-(hb + 0.001), r_rim + 0.004), (-(hb + 0.011), r_rim + 0.014)] + [side.at(k / 7) for k in range(8)]
    gw = 0.009 if W < 0.2 else 0.011
    gd = 0.007
    centres = [(-1 + 2 * (k + 1) / (grooves + 1)) * (T - 0.012) * 1.12 for k in range(grooves)]

    def crown(x):
        return r_out - 0.0045 * (x / T) ** 2

    tread = []
    x_prev = -T
    for xc in centres:
        tread.append(((x_prev + xc - gw / 2) / 2, None))
        tread += [(xc - gw / 2, None), (xc - gw / 2 + 0.0012, -gd), (xc + gw / 2 - 0.0012, -gd), (xc + gw / 2, None)]
        x_prev = xc + gw / 2
    tread.append(((x_prev + T) / 2, None))
    tread = [(x, crown(x) + (d or 0.0)) for x, d in tread]
    prof = half + tread + [(-x, r) for x, r in reversed(half)]
    # v: by arc length on the sidewalls, by x across the tread
    L = [0.0]
    for a, b in zip(half[:-1], half[1:]):
        L.append(L[-1] + math.dist(a, b))
    vs = [0.25 * l / L[-1] for l in L] + [0.25 + 0.5 * (x + T) / (2 * T) for x, _ in tread] + [1 - 0.25 * l / L[-1] for l in reversed(L)]
    mesh.lathe(prof, seg, mats=mat, uv=lambda k, u: (u * repeats, vs[k]))
    return dict(tread=2 * T, sidewall=L[-1], round=2 * math.pi * r_out / repeats, grooves=[(x + T) / (2 * T) for x in centres],
                groove=gw / (2 * T), width=W, r_out=r_out, r_rim=r_rim)


def tyre_material(info, brand='NOCTURNE', size='185/60R14 82H', name='tire', w=1024, h=512):
    """
    The tyre's texture set from `tyre()`'s layout: tread blocks, sipes and shoulder slots, a sidewall with raised
    lettering (a brand of our own and the size), ribs near bead and shoulder, dust in the grooves and low on the
    sidewall. Base colour, ORM and a normal map; the base colour takes the baked sky share (vertex colour).
    """
    U, V = np.meshgrid((np.arange(w) + 0.5) / w, (np.arange(h) + 0.5) / h)
    in_tread = (V > 0.25) & (V < 0.75)
    t = np.clip((V - 0.25) / 0.5, 0, 1)                  # across the tread
    height = np.zeros((h, w), np.float32)                 # metres, 0 = the surface
    # ---- tread: the grooves are geometry; here the lateral cuts
    pitch = 18
    g = info['grooves']
    gw = info['groove']
    edges = [0.0] + [x for c in g for x in (c - gw / 2, c + gw / 2)] + [1.0]
    ribs = list(zip(edges[0::2], edges[1::2]))
    cut = np.zeros((h, w), np.float32)
    for k, (a, b) in enumerate(ribs):
        inside = in_tread & (t > a) & (t < b)
        mid = (a + b) / 2
        if k in (0, len(ribs) - 1):
            # shoulder blocks: slots across, running out over the shoulder
            ph = (U * pitch + (0.5 if k else 0.0)) % 1.0
            slot = (np.abs(ph - 0.5) < 0.11) & inside & ((t < a + (b - a) * 0.82) if k == 0 else (t > a + (b - a) * 0.18))
            cut = np.maximum(cut, slot * 0.0055)
            sipe = (np.abs(((U * pitch + (0.0 if k else 0.5)) % 1.0) - 0.5) < 0.025) & inside
            cut = np.maximum(cut, sipe * 0.002)
        else:
            # inner ribs: slanted sipes, the slant turning over from rib to rib; a notch at each edge
            slant = 0.9 if k % 2 else -0.9
            ph = (U * pitch * 1.5 + (t - mid) / (b - a) * slant + 0.25 * k) % 1.0
            sipe = (np.abs(ph - 0.5) < 0.05) & inside
            cut = np.maximum(cut, sipe * 0.003)
            notch = (np.abs(((U * pitch * 1.5 + 0.25 * k) % 1.0) - 0.5) < 0.12) & inside & (np.abs(t - mid) > (b - a) * 0.36)
            cut = np.maximum(cut, notch * 0.004)
    height -= cut
    groove = np.zeros((h, w), np.float32)
    for c in g:
        groove = np.maximum(groove, (in_tread & (np.abs(t - c) < gw / 2)).astype(np.float32))
    # ---- sidewalls: ribs, and on the outer one the lettering (read from outside with the wheel's top up: turned
    # half round in the texture, see tyre())
    px_v = info['sidewall'] / (0.25 * h)                  # metres per pixel across a sidewall
    letters = np.zeros((h, w), np.float32)
    band = int(0.25 * h)
    half_w = w // 2
    rows0 = h - band                                      # the outer sidewall's rows: v 0.75 (shoulder) … 1 (bead)
    cap1 = min(0.56, 0.024 / (px_v * band))               # brand: 24 mm caps
    cap2 = min(0.30, 0.011 / (px_v * band))               # size: 11 mm
    m1 = text_mask(brand, half_w, band, height=cap1, font=FONT_BLACK, spacing=1.15)
    m2 = text_mask(size, half_w, band, height=cap2, spacing=1.1)
    tile = np.zeros((band, w), np.float32)
    # (row 0 of the band = the shoulder; the letters sit in the upper sidewall, a third of the way down from it)
    shift = int(band * 0.06)
    tile[:, :half_w] = np.roll(m1, shift, 0)
    tile[:, half_w:] = np.roll(m2, shift, 0)
    letters[rows0:, :] = tile[::-1, ::-1]
    letters = blur(letters, 1)
    height += letters * 0.0009
    for v0, wd, hh in ((0.770, 0.004, 0.0006), (0.783, 0.002, 0.0004), (0.945, 0.003, 0.0006), (0.960, 0.003, 0.0006), (0.975, 0.003, 0.0006)):
        for vv in (v0, 1 - v0):
            height += (np.abs(V - vv) < wd / 2) * hh
    # fine radial serrations in a band under the shoulder (both sides)
    ser = (((U * 220) % 1.0) < 0.5) & (((V > 0.795) & (V < 0.815)) | ((V < 0.205) & (V > 0.185)))
    height += ser * 0.0003
    hm = blur(height, 1)
    du = info['round'] / w
    dv = np.where(V[:, :1] < 0.25, px_v, np.where(V[:, :1] > 0.75, px_v, info['tread'] / (0.5 * h)))
    nrm = normal_from_height(hm, du, dv)
    # ---- colour and roughness
    dust = noise(h, w, 12, 6, seed=7) * 0.6 + noise(h, w, 48, 24, seed=8) * 0.4
    base = np.empty((h, w, 3), np.float32)
    base[:] = srgb_f('#1b1b1c')
    wear = in_tread & (cut < 1e-4) & (groove < 0.5)
    base[wear] = srgb_f('#262627')                        # the worn running surface: a shade greyer
    lows = np.clip(cut / 0.004, 0, 1)[..., None]
    base = base * (1 - 0.55 * lows)
    dusty = (np.clip(groove + lows[..., 0], 0, 1) * 0.5 + (~in_tread) * np.clip(dust - 0.45, 0, 1) * 0.7)[..., None]
    base = base * (1 - dusty) + np.array(srgb_f('#3a332b'), np.float32) * dusty * 0.9 + base * dusty * 0.1
    base += (letters * 0.012)[..., None]
    rough = np.where(in_tread, 0.93, 0.80).astype(np.float32)
    rough = rough - letters * 0.14 + dusty[..., 0] * 0.1
    ao = 1 - 0.6 * np.clip(blur(lows[..., 0] + groove, 2), 0, 1)
    orm = np.stack([ao, np.clip(rough, 0, 1), np.zeros_like(rough)], -1)
    _free_name(name)
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    p = nt.nodes.get('Principled BSDF')
    tb = nt.nodes.new('ShaderNodeTexImage')
    tb.image = new_image(f'{name}_base', base)
    _tinted_base(nt, p, tb)
    to = nt.nodes.new('ShaderNodeTexImage')
    to.image = new_image(f'{name}_orm', orm, colour=False)
    sep = nt.nodes.new('ShaderNodeSeparateColor')
    nt.links.new(to.outputs[0], sep.inputs[0])
    nt.links.new(sep.outputs[1], p.inputs['Roughness'])
    nt.links.new(sep.outputs[2], p.inputs['Metallic'])
    grp = bpy.data.node_groups.get('glTF Material Output')
    if grp is None:
        grp = bpy.data.node_groups.new('glTF Material Output', 'ShaderNodeTree')
        grp.interface.new_socket('Occlusion', in_out='INPUT', socket_type='NodeSocketFloat')
    gn = nt.nodes.new('ShaderNodeGroup')
    gn.node_tree = grp
    nt.links.new(sep.outputs[0], gn.inputs[0])
    tn = nt.nodes.new('ShaderNodeTexImage')
    tn.image = new_image(f'{name}_normal', nrm, colour=False)
    nm = nt.nodes.new('ShaderNodeNormalMap')
    nt.links.new(tn.outputs[0], nm.inputs['Color'])
    nt.links.new(nm.outputs[0], p.inputs['Normal'])
    m.diffuse_color = K.srgb('#1b1b1c')
    return m


def turned(mesh, name=None):
    """a left wheel's part for the right side: turned half round about the vertical (not mirrored: lettering and the
    winding stay right)"""
    out = K.Mesh(name or mesh.name)
    out.merge(mesh)
    out.transform(Matrix.Rotation(math.pi, 4, 'Z'))        # Blender z = the game's y
    return out


# ---------------------------------------------------------------------------------------------------- brakes

def disc_image(w=256, h=32, seed=3):
    """the friction face: scored round and round (u = round the disc, v = inner → outer edge), a rusty margin where
    the pad does not reach"""
    rng = np.random.default_rng(seed)
    rows = 0.50 + 0.10 * rng.random((h, 1), dtype=np.float32) + 0.03 * rng.random((h, w), dtype=np.float32)
    rgb = np.repeat(rows[..., None] * np.ones((1, w, 1), np.float32), 3, -1) * np.array([1.0, 0.99, 0.97], np.float32)
    v = (np.arange(h) + 0.5) / h
    margin = np.clip(np.maximum((0.10 - v) / 0.06, (v - 0.94) / 0.04), 0, 1)[:, None, None]
    rgb = rgb * (1 - margin) + np.array(srgb_f('#4a3a2e'), np.float32) * margin
    return rgb


def brake_disc(mesh, r_disc, x_face, thick=0.022, r_hat=0.075, hat=0.034, vented=True, seg=40):
    """
    A disc for a LEFT wheel: the outer friction face at x_face (from the wheel's centre plane), the hat rising
    outward to the hub face; `vented`: a groove with the vanes' dark gap round the edge. Materials: disc (its image:
    atlas.region('disc', disc_image(), 0.34, 1.0)), disc_edge, disc_vent, disc_hat.
    """
    xi = x_face - thick
    prof = [(xi, r_hat + 0.004), (xi, r_disc)]
    mats = ['disc']
    if vented and thick > 0.014:
        g0, g1 = xi + thick * 0.36, xi + thick * 0.64
        prof += [(g0, r_disc), (g0, r_disc - 0.012), (g1, r_disc - 0.012), (g1, r_disc)]
        mats += ['disc_edge', 'disc_vent', 'disc_vent', 'disc_vent']
    prof += [(x_face, r_disc), (x_face, r_hat), (x_face + hat, r_hat - 0.005), (x_face + hat, 0.0)]
    mats += ['disc_edge', 'disc', 'disc_hat', 'disc_hat']
    span = r_disc - r_hat

    def uv(k, u):
        return (u, min(1.0, max(0.0, (prof[k][1] - r_hat) / span)))

    mesh.lathe(prof, seg, mats=lambda k: mats[k], uv=uv)


def caliper(mesh, r_disc, x_face, thick=0.022, kind='floating', angle=-62.0, colour='cal_iron'):
    """
    A caliper astride the disc's edge for a LEFT wheel, built at the top and turned `angle`° towards the front
    (negative: behind the axle). `floating`: one piston inboard, the fist reaching over; `4pot`: a fixed caliper, two
    pistons a side, the bridge open in the middle.
    """
    m = K.Mesh('cal')
    xi = x_face - thick
    if kind == '4pot':
        zl = 0.088
        m.box(colour, x_face + 0.005, x_face + 0.040, r_disc - 0.062, r_disc + 0.004, -zl, zl, bevel=0.012, segments=2)
        m.box(colour, xi - 0.040, xi - 0.005, r_disc - 0.062, r_disc + 0.004, -zl, zl, bevel=0.012, segments=2)
        for z0, z1 in ((-zl, -0.030), (0.030, zl)):
            m.box(colour, xi - 0.036, x_face + 0.036, r_disc - 0.004, r_disc + 0.020, z0, z1, bevel=0.007, segments=2)
        for z in (-0.040, 0.040):
            m.cylinder(colour, (x_face + 0.040, r_disc - 0.030, z), 0.023, 0.008, axis='x', segments=14)
        # the raised panel between the pistons (where the maker's name is cast)
        m.box(colour, x_face + 0.039, x_face + 0.043, r_disc - 0.016, r_disc - 0.002, -0.050, 0.050, bevel=0.0015, segments=1)
        m.box('pad', xi - 0.006, x_face + 0.006, r_disc - 0.050, r_disc + 0.002, -0.062, 0.062)
        for z in (-0.070, 0.070):
            m.cylinder('cal_bolt', (x_face + 0.041, r_disc - 0.052, z), 0.006, 0.006, axis='x', segments=6)
    else:
        m.box(colour, xi - 0.046, x_face + 0.020, r_disc - 0.050, r_disc + 0.016, -0.040, 0.040, bevel=0.010, segments=2)
        m.box(colour, x_face + 0.006, x_face + 0.024, r_disc - 0.056, r_disc + 0.004, -0.050, 0.050, bevel=0.007, segments=2)
        m.cylinder(colour, (xi - 0.052, r_disc - 0.024, 0.0), 0.028, 0.030, axis='x', segments=14)
        # the carrier with its two slider pins
        m.box('cal_iron', xi - 0.030, xi - 0.008, r_disc - 0.062, r_disc + 0.006, -0.066, 0.066, bevel=0.006, segments=1)
        for z in (-0.056, 0.056):
            m.cylinder('u_rubber', (xi - 0.044, r_disc - 0.012, z), 0.010, 0.036, axis='x', segments=8)
        m.box('pad', xi - 0.008, x_face + 0.008, r_disc - 0.046, r_disc + 0.002, -0.048, 0.048)
    a = math.radians(angle)
    m.warp(lambda p: K.rot_x(p, a))
    mesh.merge(m)


# ---------------------------------------------------------------------------------------------------- underside

def tube(mesh, mat, pts, r, seg=8, cap=True):
    """a round tube along game-frame points (r: a radius, or one per point)"""
    pts = [Vector(p) for p in pts]
    rs = list(r) if isinstance(r, (list, tuple)) else [r] * len(pts)
    rings = []
    n_prev = None
    for k, p in enumerate(pts):
        a = pts[max(0, k - 1)]
        b = pts[min(len(pts) - 1, k + 1)]
        t = (b - a).normalized()
        if n_prev is None:
            n = t.orthogonal().normalized()
        else:
            n = (n_prev - t * n_prev.dot(t))
            n = n.normalized() if n.length > 1e-6 else t.orthogonal().normalized()
        n_prev = n
        bnorm = t.cross(n)
        rings.append([tuple(p + (n * math.cos(2 * math.pi * s / seg) + bnorm * math.sin(2 * math.pi * s / seg)) * rs[k]) for s in range(seg)])
    mesh.grid(rings, mat, close_u=True)
    if cap:
        mesh.face(list(reversed(rings[0])), mat, smooth=False, out=tuple(pts[0] - pts[1]))
        mesh.face(rings[-1], mat, smooth=False, out=tuple(pts[-1] - pts[-2]))


def ellipsoid(mesh, mat, centre, radii, seg=14, rings=8):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=rings, radius=1.0)
    bmesh.ops.transform(bm, matrix=Matrix.Translation(K.B(*centre)) @ Matrix.Diagonal((radii[0], radii[2], radii[1], 1.0)), verts=bm.verts)
    mesh.merge(bm, mat, smooth=True)
    bm.free()


def can(mesh, mat, centre, rx, ry, length, seg=16, round_end=0.25, across=False):
    """a silencer: an oval can along z with rounded ends (`across`: lying across the car, along x; rx is then its
    half depth along z)"""
    if across:
        m = K.Mesh('can')
        can(m, mat, (0.0, 0.0, 0.0), rx, ry, length, seg, round_end)
        m.transform(Matrix.Translation(K.B(*centre)) @ Matrix.Rotation(math.pi / 2, 4, 'Z'))
        mesh.merge(m)
        return
    cx, cy, cz = centre
    prof = [(-0.5, 0.0), (-0.5, 0.55), (-0.5 + round_end * 0.3, 0.86), (-0.5 + round_end, 1.0), (0.5 - round_end, 1.0),
            (0.5 - round_end * 0.3, 0.86), (0.5, 0.55), (0.5, 0.0)]
    rows = []
    for t, s in prof:
        rows.append([(cx + rx * s * math.cos(2 * math.pi * k / seg), cy + ry * s * math.sin(2 * math.pi * k / seg), cz + t * length) for k in range(seg)])
    mesh.grid(rows, mat, close_u=True, flip=False)


def underbody(mesh, y0, zf, zr, track_f, track_r, r_tyre, tip, layout='FR', axle='live', twin=False,
              engine=(0.0, 0.32), tank=None, clearance=0.115, rails=0.40, z_ends=(1.75, -1.75), silencer='along',
              twin_gap=0.045):
    """
    The underside, hanging under a floor at height y0: engine sump and gearbox (layout FR / AWD: a front engine; EV:
    a flat battery case instead), propshaft, differential, the rear axle (`live`: a rigid axle with trailing links;
    `irs`: driveshafts and arms), front crossmember, arms and anti-roll bar, the exhaust from the engine to the
    tailpipe at `tip` (x, y, z: where the car's own tailpipe starts; `twin`: two pipes twin_gap either side of it),
    the fuel tank, floor rails. silencer: the rear one lies `along` the car beside the tank, or `across` it behind
    the axle (then the tank sits ahead of the axle, out of sight).
    engine: the sump's (z rear, z front) relative to the front axle; tank: (x0, x1, z0, z1) or None for its usual place.
    """
    low = clearance
    side = 1.0 if tip[0] >= 0 else -1.0                     # the side the exhaust runs on
    if layout == 'EV':
        # the battery case between the axles, ribbed across, and the two drive units
        mesh.box('u_zinc', -0.62, 0.62, y0 - 0.035, y0 + 0.01, zr + 0.42, zf - 0.42, bevel=0.012, segments=1)
        for k in range(9):
            z = K.lerp(zr + 0.50, zf - 0.50, k / 8)
            mesh.box('u_black', -0.60, 0.60, y0 - 0.041, y0 - 0.033, z - 0.012, z + 0.012)
        for z in (zf, zr):
            ellipsoid(mesh, 'u_cast', (0.0, r_tyre + 0.01, z), (0.20, 0.13, 0.15))
            for s in (1, -1):
                tube(mesh, 'u_steel', [(s * 0.18, r_tyre, z), (s * (track_f / 2 - 0.10), r_tyre, z)], 0.017, seg=6, cap=False)
                tube(mesh, 'u_black', [(s * 0.34, y0 - 0.02, z + 0.16), (s * (track_f / 2 - 0.12), r_tyre - 0.10, z),
                                       (s * 0.34, y0 - 0.02, z - 0.16)], 0.02, seg=6)
        return
    # ---- floor rails and crossmembers
    for s in (1, -1):
        mesh.box('u_seal', s * rails - 0.035, s * rails + 0.035, y0 - 0.030, y0 + 0.01, zr + 0.36, zf - 0.34, bevel=0.008, segments=1)
    for z in (zf - 0.62, zf - 1.25, zr + 0.62):
        mesh.box('u_seal', -rails, rails, y0 - 0.022, y0 + 0.01, z - 0.035, z + 0.035, bevel=0.006, segments=1)
    # ---- engine sump, bellhousing and gearbox on the centre line
    e0, e1 = zf + engine[0], zf + engine[1]
    mesh.box('u_cast', -0.13, 0.13, max(low, y0 - 0.075), y0 + 0.02, e0, e1, bevel=0.022, segments=2)
    for k in range(5):                                       # the sump's cooling fins
        x = -0.10 + 0.05 * k
        mesh.box('u_cast', x - 0.006, x + 0.006, max(low - 0.004, y0 - 0.081), y0 - 0.06, e0 + 0.03, e1 - 0.03)
    # (they sit up in the tunnel: only their lower third hangs under the floor)
    yg = y0 + 0.045
    mesh.cylinder('u_cast', (0.0, y0 + 0.075, e0 - 0.07), 0.14, 0.14, axis='z', segments=18, radius2=0.125)
    mesh.cylinder('u_cast', (0.0, yg, e0 - 0.42), 0.115, 0.56, axis='z', segments=14, radius2=0.075)
    zg = e0 - 0.70
    # ---- front crossmember, lower arms, anti-roll bar, steering rack
    mesh.box('u_black', -0.38, 0.38, max(low, y0 - 0.060), y0 - 0.012, zf - 0.07, zf + 0.07, bevel=0.012, segments=1)
    xf = track_f / 2 - 0.115
    yb = r_tyre - 0.105
    for s in (1, -1):
        tube(mesh, 'u_black', [(s * 0.36, y0 - 0.035, zf + 0.02), (s * xf, yb, zf)], [0.024, 0.02], seg=6)
        tube(mesh, 'u_black', [(s * xf, yb, zf - 0.01), (s * (xf - 0.10), y0 - 0.03, zf + 0.26), (s * (rails - 0.02), y0 - 0.02, zf + 0.44)], 0.013, seg=6)
        tube(mesh, 'u_steel', [(s * 0.30, y0 - 0.005, zf - 0.13), (s * (xf - 0.01), r_tyre - 0.02, zf - 0.12)], 0.008, seg=5, cap=False)
        ellipsoid(mesh, 'u_rubber', (s * 0.33, y0 - 0.006, zf - 0.13), (0.06, 0.022, 0.022), seg=8, rings=5)
    mesh.cylinder('u_steel', (0.0, y0 - 0.005, zf - 0.13), 0.022, 0.56, axis='x', segments=8, cap=False)
    bar = [(-xf + 0.03, yb + 0.02, zf + 0.03), (-xf + 0.05, y0 - 0.045, zf + 0.30), (-0.30, y0 - 0.05, zf + 0.36), (0.30, y0 - 0.05, zf + 0.36),
           (xf - 0.05, y0 - 0.045, zf + 0.30), (xf - 0.03, yb + 0.02, zf + 0.03)]
    tube(mesh, 'u_steel', bar, 0.011, seg=6)
    # ---- propshaft and the final drive
    yd = r_tyre + 0.005
    if layout in ('FR', 'AWD'):
        tube(mesh, 'u_steel', [(0.0, yg - 0.02, zg), (0.0, yg - 0.03, (zg + zr) / 2), (0.0, yd, zr + 0.20)], 0.030, seg=10, cap=False)
        ellipsoid(mesh, 'u_iron' if axle == 'live' else 'u_cast', (0.0, yd, zr), (0.115, 0.125, 0.125), seg=14, rings=8)
        mesh.cylinder('u_iron' if axle == 'live' else 'u_cast', (0.0, yd, zr + 0.16), 0.06, 0.12, axis='z', segments=10, radius2=0.045)
        # the cover's bolts ring (rear face)
        mesh.cylinder('u_iron' if axle == 'live' else 'u_cast', (0.0, yd, zr - 0.105), 0.085, 0.03, axis='z', segments=14)
    if layout == 'AWD':
        # the front final drive beside the sump and its shafts
        ellipsoid(mesh, 'u_cast', (-0.16, r_tyre, zf), (0.09, 0.08, 0.10), seg=10, rings=6)
        for s in (1, -1):
            tube(mesh, 'u_steel', [(s * 0.14, r_tyre, zf), (s * (track_f / 2 - 0.10), r_tyre, zf)], 0.015, seg=6, cap=False)
            for x in (0.22, track_f / 2 - 0.16):
                ellipsoid(mesh, 'u_rubber', (s * x, r_tyre, zf), (0.045, 0.036, 0.036), seg=8, rings=5)
    xr = track_r / 2 - 0.11
    if axle == 'live':
        mesh.cylinder('u_black', (0.0, yd, zr), 0.036, 2 * xr, axis='x', segments=10, cap=False)
        for s in (1, -1):
            # trailing links (lower and upper), the damper and the spring seat
            tube(mesh, 'u_black', [(s * (xr - 0.10), yd - 0.07, zr), (s * (xr - 0.10), y0 - 0.02, zr + 0.52)], 0.015, seg=6)
            tube(mesh, 'u_black', [(s * (xr - 0.28), yd + 0.06, zr), (s * (xr - 0.26), y0 + 0.0, zr + 0.34)], 0.012, seg=6)
            mesh.cylinder('u_black', (s * (xr - 0.16), yd - 0.045, zr - 0.02), 0.058, 0.014, axis='y', segments=10)
            tube(mesh, 'u_steel', [(s * (xr - 0.05), yd - 0.06, zr - 0.07), (s * (xr - 0.08), y0 + 0.06, zr - 0.10)], 0.021, seg=7)
        # the lateral (Panhard) rod behind the axle
        tube(mesh, 'u_black', [(-xr + 0.08, yd - 0.03, zr - 0.10), (xr - 0.10, y0 - 0.005, zr - 0.10)], 0.011, seg=6)
    else:
        # the subframe, driveshafts with their boots, lower arms, toe links
        mesh.box('u_black', -0.42, 0.42, yd + 0.085, yd + 0.125, zr + 0.14, zr + 0.21, bevel=0.012, segments=1)
        mesh.box('u_black', -0.40, 0.40, yd + 0.06, yd + 0.10, zr - 0.25, zr - 0.19, bevel=0.012, segments=1)
        for s in (1, -1):
            tube(mesh, 'u_steel', [(s * 0.11, yd, zr), (s * xr, yd, zr)], 0.014, seg=6, cap=False)
            for x in (0.17, xr - 0.07):
                ellipsoid(mesh, 'u_rubber', (s * x, yd, zr), (0.05, 0.04, 0.04), seg=8, rings=5)
            tube(mesh, 'u_black', [(s * 0.30, yd - 0.075, zr + 0.16), (s * (xr + 0.01), yd - 0.115, zr + 0.02)], 0.02, seg=6)
            tube(mesh, 'u_black', [(s * 0.30, yd - 0.075, zr - 0.20), (s * (xr + 0.01), yd - 0.115, zr - 0.03)], 0.02, seg=6)
            tube(mesh, 'u_black', [(s * 0.34, yd - 0.01, zr - 0.24), (s * (xr - 0.01), yd - 0.02, zr - 0.13)], 0.010, seg=5)
            tube(mesh, 'u_black', [(s * (xr + 0.0), yd - 0.09, zr + 0.03), (s * (xr - 0.04), y0 - 0.02, zr + 0.48)], 0.016, seg=6)
    # ---- exhaust: down from the engine, along the tunnel's side, a catalyst, a centre silencer, over the axle, the
    # rear silencer(s) and out
    xe = side * 0.17
    ye = max(y0 - 0.028, low + 0.03)
    over = max(yd + 0.155, y0 + 0.02) if axle == 'live' else yd + 0.165
    zc = zf - 0.80
    zm = (zc + zr) / 2 - 0.05
    pipe = [(side * 0.12, ye + 0.02, e0 + 0.10), (xe, ye, e0 - 0.16), (xe, ye, zc + 0.15)]
    tube(mesh, 'u_exhaust', pipe, 0.024, seg=8, cap=False)
    can(mesh, 'u_exhaust', (xe, max(ye, low + 0.046), zc), 0.070, 0.040, 0.30, seg=12)
    mesh.box('u_zinc', xe - 0.085, xe + 0.085, ye + 0.044, ye + 0.052, zc - 0.18, zc + 0.18)       # heat shield above it
    tube(mesh, 'u_exhaust', [(xe, ye, zc - 0.15), (xe, ye, zm + 0.20)], 0.024, seg=8, cap=False)
    can(mesh, 'u_exhaust', (xe, max(ye + 0.004, low + 0.054), zm), 0.085, 0.048, 0.42, seg=12)
    zt = tip[2]
    ym = max(low + 0.065, tip[1] + 0.01)
    if silencer == 'across':
        # one wide can across the tail, fed from the middle, the pipes leaving its end on the tailpipe's side
        mlen = 0.62
        xm = side * min(0.10, abs(tip[0]) - mlen / 2 + 0.06)
        mz = max(zt + 0.22, min(zr - 0.34, zt + 0.30))
        rise = [(xe, ye, zm - 0.20), (xe, ye + 0.01, zr + 0.34), (xe * 1.25, over, zr + 0.10), (xe * 1.1, over - 0.02, zr - 0.12),
                (xm - side * 0.12, ym + 0.02, mz + 0.14), (xm - side * 0.12, ym, mz + 0.06)]
        tube(mesh, 'u_exhaust', rise, 0.026, seg=8, cap=False)
        can(mesh, 'u_exhaust', (xm, ym, mz), 0.105, 0.078, mlen, seg=14, across=True)
        for dx in ((-twin_gap, twin_gap) if twin else (0.0,)):
            tube(mesh, 'u_exhaust', [(tip[0] + dx, ym, mz - 0.04), (tip[0] + dx, tip[1], mz - 0.13), (tip[0] + dx, tip[1], zt + 0.01)],
                 0.022, seg=8, cap=False)
        if tank is None:
            tank = (-0.36, 0.36, zr + 0.30, zr + 0.62)
    else:
        rx = 0.115 if not twin else 0.15
        xm = side * min(abs(tip[0]), 0.50 - rx)                 # inboard of the wheel well
        mz = zr - 0.30 - 0.5 * max(0.0, (zr - 0.30) - (zt + 0.34))      # the rear silencer's middle, ahead of the tailpipe
        mlen = min(0.44, max(0.26, (zr - 0.20) - (zt + 0.10)))
        mz = min(zr - 0.16 - mlen / 2, max(zt + 0.08 + mlen / 2, mz))
        rise = [(xe, ye, zm - 0.20), (xe, ye + 0.01, zr + 0.34), (xe * 1.25, over, zr + 0.10), (K.lerp(xe, xm, 0.5), over, zr - 0.06),
                (xm, ym + 0.02, mz + mlen / 2 + 0.05), (xm, ym, mz + mlen / 2 - 0.02)]
        tube(mesh, 'u_exhaust', rise, 0.024, seg=8, cap=False)
        can(mesh, 'u_exhaust', (xm, ym, mz), rx, 0.072, mlen, seg=14)
        for dx in ((-twin_gap, twin_gap) if twin else (0.0,)):
            tube(mesh, 'u_exhaust', [(xm + dx, ym, mz - mlen / 2 + 0.02), (tip[0] + dx, tip[1], zt + 0.01)], 0.022, seg=8, cap=False)
    # ---- fuel tank (on the other side of the tailpipe, behind the axle unless told otherwise)
    if tank is None:
        tank = (-side * 0.46, side * 0.02, zr - 0.62, zr - 0.20)
    x0, x1 = sorted(tank[:2])
    z0, z1 = sorted(tank[2:])
    yt = max(low + 0.02, y0 - 0.018)                          # (its ribbed bottom shows just under the floor line)
    mesh.box('u_zinc', x0, x1, yt, y0 + 0.03, z0, z1, bevel=0.03, segments=2)
    for k in range(3):
        z = K.lerp(z0 + 0.07, z1 - 0.07, k / 2)
        mesh.box('u_zinc', x0 + 0.04, x1 - 0.04, yt - 0.006, yt + 0.02, z - 0.02, z + 0.02, bevel=0.005, segments=1)
    for x in (x0 + 0.10, x1 - 0.10):                          # the straps
        mesh.box('u_black', x - 0.014, x + 0.014, yt - 0.004, y0 + 0.03, z0 - 0.006, z1 + 0.006)
