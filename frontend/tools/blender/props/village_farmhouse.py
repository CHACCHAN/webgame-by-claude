"""
Farmhouse of the AUTOBAHN course's village: a half-timbered upper floor (posts, rails, braces lying on the render)
over a rendered ground floor, with a boarded timber barn at one end (the big double door with its braces at the
front, a loft hatch in the gable). Same builder as village_house.py. ~16 x 11 m, ~12.3 m tall, origin at the centre
of the footprint on the ground.

    blender -t 4 --background --factory-startup --python village_farmhouse.py -- --out <dir> [--render <dir>]

One baked material (prop_bake).
"""
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import prop_kit as K  # noqa: E402
from village_house import build_house  # noqa: E402


def build(out):
    return build_house('village_farmhouse', 16.0, 11.0, 2, 50, 23, True, out, barn=0.35)


SPEC = K.Spec('village_farmhouse.glb', build, [
    dict(name='front', eye=(12.0, 6.0, 24.0), target=(0, 4.0, 0), lens=35),
    dict(name='back', eye=(-16.0, 7.0, -22.0), target=(0, 4.0, 0), lens=35),
    dict(name='night', eye=(12.0, 6.0, 24.0), target=(0, 4.0, 0), lens=35, night=True),
])

if __name__ == '__main__':
    K.run(SPEC)
