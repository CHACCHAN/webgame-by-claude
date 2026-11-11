"""
Shared by the roadside parts (guardrail, its end, delineator, gutter grate, rockfall fence): they are modules the game
lays along the road (render/roadside.ts maps every vertex through the road's own frame, so a module bends with it).

Module frame (game frame of props/prop_kit.py): z = metres along the road from the module's start, x = metres outwards
from the line the module stands on (negative = towards the traffic), y = up from the road's edge.
Materials are found by name in the game and swapped for its own (render/roadsideModels.ts): `galvanised`, `grating`,
`post_white`, `reflector`, `rust`, `pit`, `rope` (weathered wire rope: dark, or a line thinner than a pixel
flickers bright under the upscaler), `net` (the wire mesh, cut out by the game's texture: uv in units of 0.5 m).
"""
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'props'))

import prop_kit as K  # noqa: E402


def mats():
    return dict(
        galvanised=K.material('galvanised', '#b9bcbb', metallic=0.85, roughness=0.42),
        grating=K.material('grating', '#55585a', metallic=0.8, roughness=0.5),
        post_white=K.material('post_white', '#e8e8e2', roughness=0.45),
        reflector=K.material('reflector', '#ff9a20', roughness=0.25, emit_colour='#ff8a10', emit_strength=0.6),
        rust=K.material('rust', '#6b4a35', metallic=0.3, roughness=0.8),
        pit=K.material('pit', '#050505', roughness=1.0),
        net=K.material('net', '#8f9492', metallic=0.6, roughness=0.5),
        rope=K.material('rope', '#4c4e4d', metallic=0.6, roughness=0.6),
    )


# the W-beam's face towards the traffic: (x, y) from the bottom lip to the top lip, y about the beam's centre line.
# 350 mm tall, two waves 50 mm deep (the Japanese Gr-C beam)
W_BEAM = [(0.0, -0.175), (-0.014, -0.163), (-0.05, -0.125), (-0.05, -0.07), (-0.012, -0.022), (-0.012, 0.022),
          (-0.05, 0.07), (-0.05, 0.125), (-0.014, 0.163), (0.0, 0.175)]
BEAM_Y = 0.6
STEEL = 0.005


def beam_section(dx=0.0):
    """closed section for prop_kit's sweep along +Z (a = −x, b = y): the face and, 5 mm behind it, the back"""
    front = [(-(x + dx), y) for x, y in W_BEAM]
    back = [(-(x + dx + STEEL), y) for x, y in reversed(W_BEAM)]
    return front + back


def bolt(m, mat, x, y, z, r=0.012, h=0.009):
    """a dome-headed bolt on the beam's face, its head towards the traffic"""
    m.cyl(mat, (x, y, z), (x - h, y, z), r, r * 0.6, seg=6, caps=(False, True))
