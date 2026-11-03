"""
Torii, red-orange Myojin style: two round pillars on stone bases (black foot bands), a straight tie beam (nuki) with
wedges, a plaque post (gakuzuka), black shimaki and a black kasagi with upturned ends. 4.6 m tall; the way through
runs along Z (the beams run along X); origin at the centre of the footprint on the ground.

    blender -t 4 --background --factory-startup --python torii.py -- --out <dir> [--render <dir>]
"""
import math
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import prop_kit as K  # noqa: E402

PX = 1.55          # pillar centre at the foot
LEAN = 0.06        # inward at the top
Y_FOOT, Y_TOP = 0.16, 3.98


def pillar_x(y, sign):
    t = (y - Y_FOOT) / (Y_TOP - Y_FOOT)
    return sign * (PX - LEAN * t)


def curve(x, half, lift):
    return lift * (abs(x) / half) ** 2.4


def beam(m, mat, half, y0, section, lift, n=17, scale_end=1.0):
    """a beam along x, its underside at y0, the ends lifted by `lift`; section [(z, y)] (y relative to y0)"""
    rings = []
    for i in range(n):
        x = -half + 2 * half * i / (n - 1)
        dy = curve(x, half, lift)
        rings.append([(x, y0 + dy + y, z) for z, y in section])
    m.loft(mat, rings)


def build(out):
    red = K.material('vermilion', '#c9361c', roughness=0.5)
    black = K.material('black', '#17140f', roughness=0.45)
    stone = K.material('stone', '#8f8d86', roughness=0.85)
    m = K.M('torii')
    for s in (-1, 1):
        # stone foot and black root band
        m.cyl(stone, (s * PX, 0, 0), (s * PX, 0.10, 0), 0.34, seg=16)
        m.lathe(stone, [(0.34, 0.10), (0.30, 0.15), (0.27, 0.17)], seg=16, cx=s * PX)
        levels = [Y_FOOT, 0.30, 0.62, 1.2, 2.4, 3.4, Y_TOP]
        rad = lambda y: 0.205 - 0.04 * (y - Y_FOOT) / (Y_TOP - Y_FOOT)
        # black root band (nemaki) a hair thicker than the pillar, then the red shaft
        m.lathe(black, [(rad(Y_FOOT) + 0.02, Y_FOOT - 0.02), (rad(Y_FOOT) + 0.012, 0.30), (rad(0.62) + 0.012, 0.60), (rad(0.64) + 0.005, 0.64)],
                seg=18, cx=s * PX)
        rings = [[(pillar_x(y, s) + rad(y) * math.cos(2 * math.pi * k / 18), y, rad(y) * math.sin(2 * math.pi * k / 18)) for k in range(18)] for y in levels]
        m.loft(red, rings)
        # wedge (kusabi) and tie beam
    m.box(red, -1.98, 1.98, 3.22, 3.40, -0.10, 0.10, bevel=0.012, seg=1)
    for s in (-1, 1):
        m.box(red, s * 1.80, s * 1.86, 3.12, 3.50, -0.06, 0.06, bevel=0.008, seg=1)
    # plaque post and plaque
    m.box(red, -0.07, 0.07, 3.40, 3.99, -0.06, 0.06, bevel=0.008, seg=1)
    m.box(black, -0.30, 0.30, 3.50, 3.90, -0.085, 0.085, bevel=0.012, seg=1)
    m.box(red, -0.33, 0.33, 3.47, 3.53, -0.09, 0.09)   # plaque frame bottom/top rails
    m.box(red, -0.33, 0.33, 3.88, 3.93, -0.09, 0.09)
    # shimaki: black, underside at 3.93, ends rise slightly
    beam(m, black, 2.45, 3.93, [(-0.14, 0.0), (0.14, 0.0), (0.14, 0.15), (-0.14, 0.15)], 0.10)
    # kasagi: black, flat underside, vertical flanks, a low gable on top
    beam(m, black, 2.62, 4.07, [(-0.25, 0.0), (0.25, 0.0), (0.25, 0.14), (0.0, 0.28), (-0.25, 0.14)], 0.25)
    return [m.build()]


SPEC = K.Spec('torii.glb', build, [
    dict(name='main', eye=(-6.2, 2.4, 8.5), target=(0, 2.2, 0), lens=34),
    dict(name='front', eye=(0, 2.2, 10.5), target=(0, 2.3, 0), lens=34),
    dict(name='top', eye=(-3.5, 5.6, 4.8), target=(0, 4.1, 0), lens=40),
])

if __name__ == '__main__':
    K.run(SPEC)
