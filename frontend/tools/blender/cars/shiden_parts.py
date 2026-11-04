"""
The FD3S's parts other than the shell: materials, wheels (stock 17-inch five-spoke, 235/45R17 tyres at the game's
0.31 m radius), brakes, pop-up lamp pods, lamps, rear wing, mirrors, wipers, interior, underside, exhaust, plates.
"""
import math

import bpy
import os

import shiden_details as DETAILS
import shiden_lamps as LAMPS
import shiden_wheels as WHEELS

TEX = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'textures', 'shiden')
MAPS = {'plate': 'plate.png', 'popup_lens': 'popup.png', 'headlight': 'headlight.png', 'taillight': 'taillight.png'}

MATS = {
    # name: colour, metallic, roughness, (emission colour, strength)
    'paint': ('#e8b800', 0.0, 0.32),
    'glass': ('#10161c', 0.0, 0.05),
    'trim': ('#0d0d0e', 0.0, 0.65),
    'chrome': ('#d8d8d8', 1.0, 0.12),
    'headlight': ('#e8e8e2', 0.0, 0.1),
    'taillight': ('#8a0a0a', 0.0, 0.18),
    'tire': ('#1a1a1a', 0.0, 0.85),
    'rim': ('#c4c6c8', 0.8, 0.38),
    'brake': ('#5c5d60', 0.7, 0.45),
    'popup_lens': ('#dcdcd6', 0.0, 0.1),
    'interior': ('#1e1e20', 0.0, 0.8),
    'amber': ('#d06a00', 0.0, 0.2),
    'lens_clear': ('#cfd2d4', 0.0, 0.08),
    'plate': ('#f2f2ee', 0.0, 0.4),
    'gloss_black': ('#08080a', 0.0, 0.12),
    'reflector': ('#9a0c0a', 0.0, 0.25),
}


def srgb(h):
    h = h.lstrip('#')
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return (*out, 1.0)


def materials(night=False):
    mats = {}
    for name, (col, met, rough) in MATS.items():
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        p = m.node_tree.nodes['Principled BSDF']
        p.inputs['Base Color'].default_value = srgb(col)
        p.inputs['Metallic'].default_value = met
        p.inputs['Roughness'].default_value = rough
        if name in MAPS:
            img = bpy.data.images.load(os.path.join(TEX, MAPS[name]))
            t = m.node_tree.nodes.new('ShaderNodeTexImage')
            t.image = img
            m.node_tree.links.new(t.outputs['Color'], p.inputs['Base Color'])
        if name == 'paint':
            p.inputs['Coat Weight'].default_value = 0.6
            p.inputs['Coat Roughness'].default_value = 0.05
        mats[name] = m
    return mats


def lamps_on(mats):
    """night check: the lit lenses glow with their maps (as the game does)"""
    for name, s in (('headlight', 6.0), ('taillight', 10.0), ('popup_lens', 20.0)):
        nt = mats[name].node_tree
        p = nt.nodes['Principled BSDF']
        tex = [n for n in nt.nodes if n.type == 'TEX_IMAGE']
        if tex:
            nt.links.new(tex[0].outputs['Color'], p.inputs['Emission Color'])
        p.inputs['Emission Strength'].default_value = s


def fold_pods(root):
    for n in ('popup_l', 'popup_r'):
        o = bpy.data.objects.get(n)
        if o is not None and 'popupClosed' in o:
            o.rotation_euler[0] = o['popupClosed']


def cut(shell):
    LAMPS.cut(shell)
    DETAILS.cut(shell)


def build(root, body, shell, mats, counts):
    WHEELS.build(root, mats, counts)
    LAMPS.build(body, shell, mats, counts)
    DETAILS.build(body, shell, mats, counts)
