"""
The guardrail's end (袖ビーム): the beam turns away from the road over the last metre and ends in a rolled nose, on a
post of its own. Module: z 0 (where the last span ends) .. 0.8; the game mirrors it for the other end of a run.

    blender -t 4 --background --factory-startup --python guardrail_end.py -- --out <dir> [--render <dir>]
"""
import math
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import roadside_kit as R  # noqa: E402
from roadside_kit import K  # noqa: E402


def build(out):
    mt = R.mats()
    g = mt['galvanised']
    m = K.M('guardrail_end')
    # the beam's line: straight for 0.35 m, then a quarter turn of 0.42 m radius away from the traffic
    path = [(-0.06, R.BEAM_Y, 0.0), (-0.06, R.BEAM_Y, 0.35)]
    rad = 0.42
    for k in range(1, 7):
        a = math.radians(15 * k)
        path.append((-0.06 + rad * (1 - math.cos(a)), R.BEAM_Y, 0.35 + rad * math.sin(a)))
    m.sweep(g, path, R.beam_section())
    # the rolled nose: a short tube closing the end of the beam
    ex, ez = path[-1][0], path[-1][2]
    m.cyl(g, (ex + 0.03, R.BEAM_Y - 0.175, ez - 0.01), (ex + 0.03, R.BEAM_Y + 0.175, ez - 0.01), 0.032, seg=8)
    m.lathe(g, [(0.057, -0.25), (0.057, 0.74), (0.05, 0.765), (0.0, 0.775)], seg=10, cx=0.057, cz=0.3)
    m.box(g, -0.066, 0.0, 0.5, 0.7, 0.255, 0.345)
    R.bolt(m, g, -0.06 - 0.012, R.BEAM_Y, 0.3, r=0.016, h=0.012)
    return [m.build(sharp=40)]


SPEC = K.Spec('guardrail_end.glb', build, [
    dict(name='main', eye=(-2.4, 1.3, -1.2), target=(0.1, 0.5, 0.5), lens=40),
])

if __name__ == '__main__':
    K.run(SPEC)
