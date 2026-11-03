"""
Curve mirror (カーブミラー): orange pole, one round convex mirror (0.8 m) facing +Z with an orange rim, hood and back,
tipped down a few degrees. 3.6 m tall, origin at the foot of the pole.

    blender -t 4 --background --factory-startup --python curve_mirror.py -- --out <dir> [--render <dir>]
"""
import math
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import prop_kit as K  # noqa: E402

CY, CZ = 3.14, 0.16   # mirror centre
TILT = math.radians(6)


def dome(m, mat, base_r, height, sign, seg=32, steps=7):
    """a spherical cap seen from +Z (sign +1: bulging towards +Z, -1: towards -Z), base on the z = 0 plane"""
    rs = (base_r ** 2 + height ** 2) / (2 * height)
    prof = [(base_r, 0.0)]
    for i in range(1, steps + 1):
        phi = math.asin(base_r / rs) * (1 - i / steps)
        prof.append((rs * math.sin(phi), (rs * math.cos(phi) - (rs - height))))
    prof[-1] = (0.0, height)
    with m.at(K.rot_x(sign * math.pi / 2)):
        m.lathe(mat, prof, seg=seg)


def build(out):
    orange = K.material('orange', '#e5651b', metallic=0.1, roughness=0.42)
    mirror = K.material('mirror', '#dfe6ea', metallic=1.0, roughness=0.05)
    white = K.material('white', '#e9e9e4', roughness=0.35)
    m = K.M('curve_mirror')
    # pole with a foot, two white bands and a cap
    m.lathe(orange, [(0.085, 0.0), (0.085, 0.04), (0.058, 0.07), (0.05, 0.12), (0.046, 3.30), (0.05, 3.31), (0.05, 3.35), (0.03, 3.38)], seg=14)
    for y in (1.9, 2.2):
        m.cyl(white, (0, y, 0), (0, y + 0.12, 0), 0.0525, seg=14)
    # the mirror assembly, tipped down about the X axis
    with m.at(K.move(0, CY, CZ) @ K.rot_x(TILT)):
        dome(m, mirror, 0.355, 0.07, +1, seg=28, steps=6)              # the convex glass
        m.torus(orange, (0, 0, 0.012), 0.372, 0.03, 'z', seg=30, tube=6)  # rim
        dome(m, orange, 0.385, 0.085, -1, seg=28, steps=4)               # back shell
        # hood over the top third
        arc = [(0.42 * math.cos(math.radians(a)), 0.42 * math.sin(math.radians(a)), 0.0) for a in range(25, 156, 10)]
        m.sweep(orange, arc, [(-0.008, -0.02), (0.008, -0.02), (0.008, 0.115), (-0.008, 0.115)], up=(0, 0, 1))
        # brackets from the back shell to the pole
        for dy in (-0.15, 0.15):
            m.box(orange, -0.03, 0.03, dy - 0.02, dy + 0.02, -0.12 - 0.02, -0.05, bevel=0.005, seg=1)
    m.box(orange, -0.07, 0.07, CY - 0.17, CY - 0.11, -CZ * 0.0 - 0.03, 0.04 - 0.0)  # clamp bands round the pole
    m.box(orange, -0.07, 0.07, CY + 0.11, CY + 0.17, -0.03, 0.04)
    return [m.build()]


SPEC = K.Spec('curve_mirror.glb', build, [
    dict(name='main', eye=(-4.2, 2.2, 7.5), target=(0, 1.8, 0), lens=38, size=(540, 720)),
    dict(name='close', eye=(-1.9, 3.6, 2.6), target=(0, 3.1, 0), lens=45),
    dict(name='band', eye=(0.25, 2.1, 0.5), target=(0, 2.05, 0), lens=50),
    dict(name='back', eye=(2.0, 3.2, -2.8), target=(0, 3.0, 0), lens=45),
])

if __name__ == '__main__':
    K.run(SPEC)
