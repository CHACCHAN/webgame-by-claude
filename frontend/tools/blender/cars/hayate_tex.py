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
    """u: inboard (garnish side) → outboard round the corner; v: bottom → top"""
    c = Canvas(512, 128)
    c.fill(_srgb('#3c0607'))                                     # smoked lower lens
    U, V = c.U, c.V
    # upper red band with fine horizontal ribs
    top = c.box(-1, 2, 0.50, 1.2)
    c.paint(top, _srgb('#c4141a'))
    ribs = (np.sin(V * 2 * np.pi * 18) > 0.6) * top
    c.paint(ribs * 0.45, _srgb('#ff4a3c'))
    # a middle red line across the lower part and vertical flutes
    c.paint(c.box(-1, 2, 0.22, 0.27) * 0.8, _srgb('#9a0e12'))
    flutes = (np.sin(U * 2 * np.pi * 60) > 0.7) * (1 - top)
    c.paint(flutes * 0.25, _srgb('#6a0a0c'))
    # chrome-ish divider and the housing edge
    c.paint(c.box(-1, 2, 0.47, 0.50), _srgb('#1a1a1c'))
    edge = np.maximum(c.box(-1, 2, 0.0, 0.04), c.box(-1, 2, 0.96, 1.01))
    c.paint(edge, _srgb('#121214'))
    return c.image('tex_taillight', None)


def amber_lamp():
    """corner lamp strip: smoked front (u < 0.52), amber side; u 0.6..1 is also used by the bumper / rear turn lamps"""
    c = Canvas(256, 64)
    U, V = c.U, c.V
    c.fill(_srgb('#d8740c'))
    ribs = (np.sin(U * 2 * np.pi * 40) > 0.5)
    c.paint(ribs * 0.35, _srgb('#ffb24a'))
    smoke = c.box(-1, 0.52, -1, 2, soft=0.02)
    c.paint(smoke * 0.92, _srgb('#14110f'))
    c.paint(smoke * c.box(0.08, 0.46, 0.25, 0.75) * 0.25, _srgb('#a85808'))
    edge = np.maximum(c.box(-1, 2, -1, 0.06), c.box(-1, 2, 0.94, 2))
    c.paint(edge, _srgb('#101012'))
    return c.image('tex_amber', None)


def clear_lamp():
    """bumper clear lamps: a prismatic grid over a silver reflector"""
    c = Canvas(128, 64)
    U, V = c.U, c.V
    c.fill(_srgb('#cfd6dc'))
    grid = ((np.sin(U * 2 * np.pi * 10) > 0.75) | (np.sin(V * 2 * np.pi * 5) > 0.8))
    c.paint(grid * 0.5, _srgb('#8e979e'))
    c.paint(np.maximum(c.box(-1, 2, -1, 0.06), c.box(-1, 2, 0.94, 2)), _srgb('#2a2c2e'))
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
