"""
Sign gantry (Schilderbrücke) over a motorway carriageway: a box truss of four galvanised chords with verticals and
zig-zag diagonals, carried by two ladder-braced legs on concrete foundations. The sign boards are not part of the
model: the game hangs them in front of the truss (+Z, towards the traffic) from the vertical rails.
Span 19 m between the legs' centres (x = ±9.5), truss chords at 5.9 and 7.3 m, origin on the ground at the centre.

    blender -t 4 --background --factory-startup --python sign_gantry.py -- --out <dir> [--render <dir>]
"""
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import prop_kit as K  # noqa: E402

HALF = 9.5            # legs' centres
TRUSS = 10.15         # chords' ends
Y0, Y1 = 5.9, 7.3     # bottom / top chords
ZB = 0.6              # chords at z = ±ZB
CHORD_R, BRACE_R = 0.085, 0.045


def build(out):
    steel = K.material('galvanised', '#a7adb0', metallic=0.6, roughness=0.42)
    concrete = K.material('foundation', '#8d8a83', roughness=0.9)
    m = K.M('sign_gantry')
    # --- truss: four chords, a frame every bay, zig-zag diagonals on all four faces
    for y in (Y0, Y1):
        for z in (-ZB, ZB):
            m.cyl(steel, (-TRUSS, y, z), (TRUSS, y, z), CHORD_R, seg=8)
    bays = 13
    xs = [-TRUSS + 2 * TRUSS * k / bays for k in range(bays + 1)]
    for k, x in enumerate(xs):
        for z in (-ZB, ZB):
            m.cyl(steel, (x, Y0, z), (x, Y1, z), BRACE_R, seg=6, caps=(False, False))
        for y in (Y0, Y1):
            m.cyl(steel, (x, y, -ZB), (x, y, ZB), BRACE_R, seg=6, caps=(False, False))
        if k == bays:
            break
        x2 = xs[k + 1]
        flip = k % 2
        for z in (-ZB, ZB):  # front and back faces
            a, b = (Y0, Y1) if flip else (Y1, Y0)
            m.cyl(steel, (x, a, z), (x2, b, z), BRACE_R, seg=6, caps=(False, False))
        for y in (Y0, Y1):  # top and bottom faces
            a, b = (-ZB, ZB) if flip else (ZB, -ZB)
            m.cyl(steel, (x, y, a), (x2, y, b), BRACE_R, seg=6, caps=(False, False))
    # vertical rails on the front face the boards hang from
    for x in (-8.4, -5.6, -2.8, 0.0, 2.8, 5.6, 8.4):
        m.box(steel, x - 0.05, x + 0.05, 4.95, 8.15, ZB + 0.05, ZB + 0.13)
    # --- legs: two posts (front / back) braced like a ladder, base plates on foundations
    for side in (-1, 1):
        x = side * HALF
        for z in (-ZB, ZB):
            m.cyl(steel, (x, 0.35, z), (x, Y1 + 0.15, z), 0.135, seg=12, caps=(False, True))
            m.box(steel, x - 0.25, x + 0.25, 0.30, 0.36, z - 0.25, z + 0.25)
        ys = [1.2 + k * 1.15 for k in range(5)]
        for k, y in enumerate(ys):
            m.cyl(steel, (x, y, -ZB), (x, y, ZB), BRACE_R, seg=6, caps=(False, False))
            if k + 1 < len(ys):
                a, b = (-ZB, ZB) if k % 2 else (ZB, -ZB)
                m.cyl(steel, (x, y, a), (x, ys[k + 1], b), BRACE_R, seg=6, caps=(False, False))
        # knee braces into the truss
        for z in (-ZB, ZB):
            m.cyl(steel, (x, Y0 - 1.0, z), (x - side * 1.0, Y0, z), BRACE_R, seg=6, caps=(False, False))
        m.box(concrete, x - 0.55, x + 0.55, -0.6, 0.30, -1.05, 1.05, bevel=0.03, seg=1)
    ob = m.build(sharp=40)
    return [ob]


SPEC = K.Spec('sign_gantry.glb', build, [
    dict(name='front', eye=(4.0, 4.0, 26.0), target=(0, 4.5, 0), lens=30),
    dict(name='leg', eye=(13.0, 3.0, 6.0), target=(9.5, 4.0, 0), lens=35),
])

if __name__ == '__main__':
    K.run(SPEC)
