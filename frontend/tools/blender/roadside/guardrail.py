"""
Guardrail (ガードレール, Gr-C-4E): one 4 m span. A W-beam with its splice (the next beam's end laps over, six bolts),
a round post in the middle of the span with its bracket and bolt, a cap on the post.
Module: z 0..4, the beam's face 0.06 m towards the traffic from the post line, top of the beam 0.775 m.

    blender -t 4 --background --factory-startup --python guardrail.py -- --out <dir> [--render <dir>]
"""
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import roadside_kit as R  # noqa: E402
from roadside_kit import K  # noqa: E402

L = 4.0


def build(out):
    mt = R.mats()
    g = mt['galvanised']
    m = K.M('guardrail')
    # the beam, a ring of the section every metre (the game bends the module along the road)
    with m.at(K.move(0, R.BEAM_Y, 0)):
        m.sweep(g, [(-0.06, 0, z) for z in (0.0, 1.0, 2.0, 3.0, 4.0)], R.beam_section())
        # the splice: the neighbour's end lying on this one for 0.3 m
        m.sweep(g, [(-0.06 - R.STEEL, 0, z) for z in (-0.02, 0.3)], R.beam_section())
    for z in (0.07, 0.23):
        for y, x in ((0.0975, -0.05), (-0.0975, -0.05), (0.0, -0.012)):
            R.bolt(m, g, -0.06 - R.STEEL + x, R.BEAM_Y + y, z)
    # post (φ114.3) with a domed cap, its bracket and the bolt through the beam's middle
    m.lathe(g, [(0.057, -0.25), (0.057, 0.74), (0.05, 0.765), (0.0, 0.775)], seg=10, cx=0.057, cz=2.0)
    m.box(g, -0.066, 0.0, 0.5, 0.7, 1.955, 2.045)
    R.bolt(m, g, -0.06 - 0.012, R.BEAM_Y, 2.0, r=0.016, h=0.012)
    return [m.build(sharp=40)]


SPEC = K.Spec('guardrail.glb', build, [
    dict(name='main', eye=(-4.2, 1.5, -1.6), target=(0, 0.5, 2.0), lens=38),
    dict(name='splice', eye=(-0.9, 0.9, -0.5), target=(-0.05, 0.6, 0.25), lens=50),
])

if __name__ == '__main__':
    K.run(SPEC)
