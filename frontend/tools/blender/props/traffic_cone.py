"""
Traffic cone, Japanese style: red body with two white reflective bands on a black square base. 0.7 m tall, origin at the
centre of the base, nothing in particular faces +Z (the base's sides are square).

    blender -t 4 --background --factory-startup --python traffic_cone.py -- --out <dir> [--render <dir>]
"""
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import prop_kit as K  # noqa: E402

Y0, Y1 = 0.035, 0.70       # body from the top of the base to the tip
R0, R1 = 0.148, 0.026


def radius(y, lift=0.0):
    t = (y - Y0) / (Y1 - Y0)
    return R0 + (R1 - R0) * t + lift


def band(m, mat, ya, yb, lift=0.003, seg=16):
    m.lathe(mat, [(radius(ya, lift - 0.002), ya), (radius(ya + 0.004, lift + 0.001), ya + 0.004), (radius(yb - 0.004, lift + 0.001), yb - 0.004), (radius(yb, lift - 0.002), yb)], seg=seg)


def build(out):
    red = K.material('red', '#d4261b', roughness=0.55)
    white = K.material('white', '#f0f0ec', roughness=0.32)
    black = K.material('black', '#1b1b1d', roughness=0.8)
    m = K.M('traffic_cone')
    # square base: a slab with chamfered edges and a raised collar
    m.box(black, -0.19, 0.19, 0.0, 0.032, -0.19, 0.19, bevel=0.012, seg=1)
    seg = 16
    prof = [(0.166, Y0 - 0.005), (0.166, Y0 + 0.012), (radius(Y0 + 0.03), Y0 + 0.03)]
    prof += [(radius(0.69), 0.69), (0.016, 0.698), (0.0, 0.70)]
    m.lathe(red, prof, seg=seg)
    band(m, white, 0.40, 0.52)   # wide upper band
    band(m, white, 0.26, 0.32)   # narrow lower band
    return [m.build()]


SPEC = K.Spec('traffic_cone.glb', build, [
    dict(name='main', eye=(-0.9, 0.7, 1.7), target=(0, 0.34, 0), lens=45, size=(540, 720)),
    dict(name='close', eye=(0.5, 0.25, 0.7), target=(0, 0.2, 0), lens=45),
])

if __name__ == '__main__':
    K.run(SPEC)
