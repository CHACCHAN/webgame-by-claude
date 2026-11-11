"""
Delineator (視線誘導標): a white post with a round amber reflector in a dark housing on each face, the kind that stands
behind the guardrail and along the gutter. 1.05 m; module origin at its foot, the reflectors face ±z (up and down the
road).

    blender -t 4 --background --factory-startup --python delineator.py -- --out <dir> [--render <dir>]
"""
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import roadside_kit as R  # noqa: E402
from roadside_kit import K  # noqa: E402


def build(out):
    mt = R.mats()
    m = K.M('delineator')
    m.lathe(mt['post_white'], [(0.03, -0.2), (0.03, 0.9), (0.02, 0.93)], seg=8)
    # the housing: a short drum across the road's direction, a reflector on each face
    m.cyl(mt['grating'], (0, 0.985, -0.022), (0, 0.985, 0.022), 0.062, seg=14)
    m.cyl(mt['reflector'], (0, 0.985, 0.022), (0, 0.985, 0.027), 0.05, 0.046, seg=14, caps=(False, True))
    m.cyl(mt['reflector'], (0, 0.985, -0.022), (0, 0.985, -0.027), 0.05, 0.046, seg=14, caps=(False, True))
    return [m.build(sharp=40)]


SPEC = K.Spec('delineator.glb', build, [
    dict(name='main', eye=(-1.0, 1.0, -2.2), target=(0, 0.6, 0), lens=45, size=(540, 720)),
])

if __name__ == '__main__':
    K.run(SPEC)
