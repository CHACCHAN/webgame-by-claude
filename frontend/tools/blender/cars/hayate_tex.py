"""
Textures painted at build time with numpy (sRGB floats, row 0 = bottom): the lamp lenses (the game lights them through
these maps: bright parts glow), the tyre's tread and sidewall, and the number plate image made by hayate_textures.py.
"""
import os

import bpy
import numpy as np

import hayate_kit as K

TEX_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'textures', 'hayate')


class Canvas:
    def __init__(self, w, h):
        self.w, self.h = w, h
        u = (np.arange(w) + 0.5) / w
        v = (np.arange(h) + 0.5) / h
        self.U, self.V = np.meshgrid(u, v)
        self.rgb = np.zeros((h, w, 3), np.float32)

    def fill(self, c):
        self.rgb[:] = c

    def paint(self, alpha, c):
        a = np.clip(alpha, 0, 1)[..., None]
        self.rgb = self.rgb * (1 - a) + np.array(c, np.float32) * a

    def box(self, u0, u1, v0, v1, soft=0.004):
        """coverage of a box in uv (soft edges)"""
        su = soft
        a = np.clip((self.U - u0) / su + 0.5, 0, 1) * np.clip((u1 - self.U) / su + 0.5, 0, 1)
        b = np.clip((self.V - v0) / su + 0.5, 0, 1) * np.clip((v1 - self.V) / su + 0.5, 0, 1)
        return a * b

    def image(self, name, path=None):
        rgba = np.ones((self.h, self.w, 4), np.float32)
        rgba[..., :3] = np.clip(self.rgb, 0, 1)
        img = bpy.data.images.new(name, self.w, self.h, alpha=False)
        img.pixels.foreach_set(rgba.ravel())
        if path:
            img.filepath_raw = path
            img.file_format = 'PNG'
            img.save()
        img.pack()
        return img


def _srgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def tail_lamp():
    """u: inboard (garnish side) → outboard; v: bottom → top. As on the photos (r08, q02, n32; lamp review 2026-11-10):
    unlit, the upper row is a lighter, pinkish red (the clear-ish red lens over a white reflector), the lower row a deep
    red with each cell's reflector glowing in its middle, a fine grid of lens prisms over both, a smoked lower edge;
    the cells split at u 0.447 / 0.693 (the reverse lamp is the lower middle cell, a separate part)"""
    c = Canvas(512, 128)
    U, V = c.U, c.V
    c.fill(_srgb('#6e0a10'))                                     # lower row: deep red
    top = c.box(-1, 2, 0.65, 1.2, soft=0.02)        # the rows split at 65 % (hayate_details.TAIL_SPLIT)
    c.paint(top, _srgb('#a8303a'))                               # upper row: lighter, pinkish red
    # each lower cell's reflector glows in its middle (brighter red), the upper row a little lighter in the middle too
    for u0, u1 in ((0.0, 0.447), (0.447, 0.693), (0.693, 1.0)):
        cu = (u0 + u1) / 2
        r = np.sqrt(((U - cu) / ((u1 - u0) * 0.42)) ** 2 + ((V - 0.36) / 0.28) ** 2)
        c.paint(np.clip(1 - r, 0, 1) * 0.75 * (1 - top), _srgb('#c8161e'))
        r = np.sqrt(((U - cu) / ((u1 - u0) * 0.5)) ** 2 + ((V - 0.82) / 0.16) ** 2)
        c.paint(np.clip(1 - r, 0, 1) * 0.35 * top, _srgb('#cc5058'))
    # the lens prisms: a fine grid (darker lines), slightly lit edges
    fu = np.mod(U * 96, 1.0)
    fv = np.mod(V * 18, 1.0)
    c.paint(((fu < 0.16) | (fv < 0.14)) * 0.30, _srgb('#3a0508'))
    c.paint(((fv >= 0.14) & (fv < 0.24)) * 0.12, _srgb('#ff6a5a'))
    # cell dividers (dark), the soft step between the rows, the smoked lower edge and the lens rim
    for u in (0.447, 0.693):
        c.paint(c.box(u - 0.005, u + 0.005, -1, 2) * 0.85, _srgb('#14080a'))
    c.paint(c.box(-1, 2, 0.635, 0.665) * 0.6, _srgb('#3a0a0e'))
    c.paint(c.box(-1, 2, -1, 0.08, soft=0.04) * 0.8, _srgb('#22060a'))
    c.paint(c.box(-1, 2, 0.965, 2), _srgb('#121214'))
    return c.image('tex_taillight', None)


def amber_lamp():
    """corner lamp strip: smoked front (u < 0.52), amber side; u 0.6..1 is also used by the bumper / rear turn lamps.
    Unlit amber as on the photos (n24, r08): a deep orange-amber, darker low down (the reflector's shadow), a fine
    prism grid, not a bright flat orange"""
    c = Canvas(256, 64)
    U, V = c.U, c.V
    c.fill(_srgb('#a8560c'))
    c.paint(c.box(-1, 2, 0.55, 2, soft=0.25) * 0.6, _srgb('#cc7418'))
    c.paint(c.box(-1, 2, -1, 0.35, soft=0.2) * 0.5, _srgb('#6e3208'))
    r = np.sqrt(((np.mod(U * 4, 1.0) - 0.5) / 0.45) ** 2 + ((V - 0.5) / 0.45) ** 2)
    c.paint(np.clip(1 - r, 0, 1) * 0.35, _srgb('#e08a2a'))
    fu = np.mod(U * 64, 1.0)
    fv = np.mod(V * 12, 1.0)
    c.paint(((fu < 0.18) | (fv < 0.16)) * 0.28, _srgb('#4a2006'))
    smoke = c.box(-1, 0.52, -1, 2, soft=0.02)
    c.paint(smoke * 0.92, _srgb('#14110f'))
    c.paint(smoke * c.box(0.08, 0.46, 0.25, 0.75) * 0.25, _srgb('#a85808'))
    edge = np.maximum(c.box(-1, 2, -1, 0.06), c.box(-1, 2, 0.94, 2))
    c.paint(edge, _srgb('#101012'))
    return c.image('tex_amber', None)


def clear_lamp():
    """the front combination lamp's clear part (the clearance lamp; u inboard → outboard, v up), as on r03 / n06: fine
    vertical flutes over a chrome reflector (a bright band along its top, a second, softer one low down), the bulb's
    dark round socket near the inboard end, a light-grey housing rim round the lens"""
    c = Canvas(256, 64)
    U, V = c.U, c.V
    c.fill(_srgb('#aeb5bb'))
    c.paint(c.box(-1, 2, 0.58, 0.86, soft=0.14) * 0.75, _srgb('#eef2f5'))
    c.paint(c.box(0.25, 0.95, 0.16, 0.38, soft=0.12) * 0.55, _srgb('#e2e7eb'))
    c.paint(c.box(-1, 2, 0.40, 0.56, soft=0.10) * 0.35, _srgb('#7d858c'))
    flutes = 0.5 + 0.5 * np.sin(U * 2 * np.pi * 46)
    c.paint(flutes * 0.22, _srgb('#6f777e'))
    c.paint((np.mod(V * 6, 1.0) < 0.08) * 0.18, _srgb('#ffffff'))
    r = np.sqrt(((U - 0.075) / 0.050) ** 2 + ((V - 0.50) / 0.22) ** 2)
    c.paint(np.clip((1.0 - r) / 0.12, 0, 1), _srgb('#2e3236'))
    c.paint(np.clip((0.55 - r) / 0.12, 0, 1), _srgb('#14171a'))
    rim = np.maximum(np.maximum(c.box(-1, 0.018, -1, 2), c.box(0.982, 2, -1, 2)),
                     np.maximum(c.box(-1, 2, -1, 0.07), c.box(-1, 2, 0.93, 2)))
    c.paint(rim, _srgb('#8a8f94'))
    return c.image('tex_headlight', None)


def popup_lens():
    """the rectangular sealed beam's lens: vertical flutes, a horizontal band of prisms, the reflector's glow behind"""
    c = Canvas(256, 192)
    U, V = c.U, c.V
    c.fill(_srgb('#c9d2da'))
    r = np.sqrt(((U - 0.5) / 0.5) ** 2 + ((V - 0.48) / 0.55) ** 2)
    c.paint(np.clip(1 - r, 0, 1) * 0.6, _srgb('#ffffff'))
    flutes = np.abs(np.sin(U * np.pi * 24))
    c.paint((flutes < 0.25) * 0.35, _srgb('#8c96a0'))
    band = c.box(-1, 2, 0.40, 0.58)
    prism = (np.sin(U * 2 * np.pi * 36) > 0.2) * band
    c.paint(prism * 0.45, _srgb('#9aa4ae'))
    c.paint(np.clip(1 - np.sqrt(((U - 0.5) / 0.12) ** 2 + ((V - 0.5) / 0.16) ** 2), 0, 1) * 0.5, _srgb('#ffffff'))
    return c.image('tex_popup_lens', None)


def tyre():
    """multiplier map (the game tints it with its tyre colour): tread blocks and grooves, sidewall ribs and a plain
    lettering band (no brand). u: 1/6 of the way round, v: across the profile (inner bead 0 → outer bead 1)"""
    c = Canvas(512, 256)
    U, V = c.U, c.V
    c.fill((0.80, 0.80, 0.80))
    tread = (V > 0.34) & (V < 0.66)
    # lateral sipes and shoulder blocks
    s1 = (np.abs(((U * 28 + (V > 0.5) * 0.5) % 1.0) - 0.5) < 0.06) & tread
    c.paint(s1 * 0.8, (0.30, 0.30, 0.30))
    sh = ((V > 0.30) & (V < 0.38)) | ((V > 0.62) & (V < 0.70))
    sh_g = (np.abs(((U * 14) % 1.0) - 0.5) < 0.10) & sh
    c.paint(sh_g * 0.9, (0.25, 0.25, 0.25))
    # sidewall: a ring band and plain raised "lettering" blocks on the outer side
    for v0, v1 in ((0.04, 0.06), (0.94, 0.96), (0.80, 0.81)):
        c.paint(c.box(-1, 2, v0, v1), (0.60, 0.60, 0.60))
    letters = (np.abs(((U * 9) % 1.0) - 0.5) < 0.32) & (V > 0.845) & (V < 0.885)
    c.paint(letters * 0.6, (1.0, 1.0, 1.0))
    return c.image('tex_tire', None)


def plate():
    path = os.path.join(TEX_DIR, 'plate.png')
    if not os.path.exists(path):
        return None
    img = bpy.data.images.load(path)
    img.pack()
    return img


def apply(mat, img, multiply=None):
    """base colour from the image (× colour if given); for lamps the emission follows the image too"""
    nt = mat.node_tree
    p = nt.nodes.get('Principled BSDF')
    t = nt.nodes.new('ShaderNodeTexImage')
    t.image = img
    t.interpolation = 'Linear'
    if multiply is not None:
        mix = nt.nodes.new('ShaderNodeMix')
        mix.data_type = 'RGBA'
        mix.blend_type = 'MULTIPLY'
        mix.inputs['Factor'].default_value = 1.0
        nt.links.new(t.outputs['Color'], mix.inputs['A'])
        mix.inputs['B'].default_value = K.srgb(multiply)
        nt.links.new(mix.outputs['Result'], p.inputs['Base Color'])
    else:
        nt.links.new(t.outputs['Color'], p.inputs['Base Color'])
    return t


def emission_from(mat, tex_node):
    nt = mat.node_tree
    p = nt.nodes.get('Principled BSDF')
    nt.links.new(tex_node.outputs['Color'], p.inputs['Emission Color'])
