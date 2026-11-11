"""
Gutter grating (グレーチング): a steel grate of bearing bars in its angle frame, the lid of a catch basin in the
roadside gutter. 0.5 m across the gutter (x −0.25..0.25), 1 m along the road (z 0..1), its top at y = TOP.

    blender -t 4 --background --factory-startup --python gutter_grate.py -- --out <dir> [--render <dir>]
"""
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import roadside_kit as R  # noqa: E402
from roadside_kit import K  # noqa: E402


TOP = 0.06


def build(out):
    mt = R.mats()
    s = mt['grating']
    m = K.M('gutter_grate')
    # (modelled 0.06 m above its place, so that it stands on the ground of its check render)
    with m.at(K.move(0, TOP, 0)):
        # the frame
        for x0, x1, z0, z1 in ((-0.25, -0.235, 0, 1), (0.235, 0.25, 0, 1), (-0.25, 0.25, 0, 0.015), (-0.25, 0.25, 0.985, 1)):
            m.box(s, x0, x1, -0.05, 0.0, z0, z1)
        # bearing bars across the gutter, every 5 cm; cross rods along it
        for k in range(1, 20):
            z = k * 0.05
            m.box(s, -0.235, 0.235, -0.044, -0.002, z - 0.0025, z + 0.0025)
        for x in (-0.12, 0.0, 0.12):
            m.box(s, x - 0.004, x + 0.004, -0.012, -0.004, 0.015, 0.985)
        # the dark of the basin under it
        m.quad(mt['pit'], [(-0.235, -0.046, 0.015), (-0.235, -0.046, 0.985), (0.235, -0.046, 0.985), (0.235, -0.046, 0.015)])
    return [m.build(sharp=40)]


SPEC = K.Spec('gutter_grate.glb', build, [
    dict(name='main', eye=(-0.9, 0.9, -0.7), target=(0, 0, 0.5), lens=40),
])

if __name__ == '__main__':
    K.run(SPEC)
