"""
Sign gantry (Schilderbrücke) over a motorway carriageway: a box truss of four hot-dip galvanised chords (spliced with
flanges at the thirds) with verticals, zig-zag diagonals and gusset plates at the nodes, carried by two
ladder-braced legs: head plates under the truss, base plates with stiffeners and anchor bolts on grout pads, on
concrete foundations that go into the ground. On the right leg the cable duct comes down to the control cabinet
on its plinth. The sign boards are not part of the model: the game hangs them in front of the truss (+Z, towards
the traffic) from the vertical rails, which are clamped to the chords.
Span 19 m between the legs' centres (x = ±9.5), truss chords at 5.9 and 7.3 m, origin on the ground at the centre.

    blender -t 4 --background --factory-startup --python sign_gantry.py -- --out <dir> [--render <dir>]

One baked material (prop_bake), without a normal map.
"""
import math
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import prop_kit as K  # noqa: E402
import prop_bake as PB  # noqa: E402

HALF = 9.5            # legs' centres
TRUSS = 10.15         # chords' ends
Y0, Y1 = 5.9, 7.3     # bottom / top chords
ZB = 0.6              # chords at z = ±ZB
CHORD_R, BRACE_R = 0.085, 0.045
RAILS = (-8.4, -5.6, -2.8, 0.0, 2.8, 5.6, 8.4)


def build(out):
    steel = PB.surface('galvanised', '#a2a8aa', metallic=0.75, roughness=0.46, vary=0.1, mottle=0.5, mottle_scale=14, mottle_colour='#8b9092',
                       mottle_rough=0.6, dirt=0.5, streak=0.4, rust=0.22, foot=0.4, foot_h=0.5)
    concrete = PB.surface('foundation', '#8d8a83', roughness=0.9, vary=0.15, mottle=0.5, mottle_scale=8, dirt=0.7, foot=0.6, foot_h=0.12,
                          moss=0.5, streak=0.4)
    cabinet = PB.surface('cabinet', '#b9bcb8', roughness=0.5, vary=0.06, dirt=0.6, streak=0.5, foot=0.5, foot_h=0.3, rust=0.15, wear=0.2)
    m = K.M('sign_gantry')
    # --- truss: four chords (end plates, flanged splices), a frame every bay, zig-zag diagonals on all four faces
    for y in (Y0, Y1):
        for z in (-ZB, ZB):
            m.cyl(steel, (-TRUSS, y, z), (TRUSS, y, z), CHORD_R, seg=10)
            for x in (-3.38, 3.38):
                m.cyl(steel, (x - 0.03, y, z), (x + 0.03, y, z), CHORD_R + 0.06, seg=10)
            for x in (-TRUSS, TRUSS):
                m.cyl(steel, (x - 0.012, y, z), (x + 0.012, y, z), CHORD_R + 0.02, seg=10)
    bays = 13
    xs = [-TRUSS + 2 * TRUSS * k / bays for k in range(bays + 1)]
    for k, x in enumerate(xs):
        for z in (-ZB, ZB):
            m.cyl(steel, (x, Y0, z), (x, Y1, z), BRACE_R, seg=6, caps=(False, False))
            # gusset plates where the braces meet the chords
            s = 1 if z > 0 else -1
            for y, d in ((Y0, 1), (Y1, -1)):
                m.box(steel, x - 0.16, x + 0.16, min(y, y + d * 0.24), max(y, y + d * 0.24), z + s * 0.048, z + s * 0.06)
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
    # vertical rails on the front face the boards hang from, clamped to both chords
    for x in RAILS:
        m.box(steel, x - 0.05, x + 0.05, 4.95, 8.15, ZB + 0.05, ZB + 0.13)
        for y in (Y0, Y1):
            m.box(steel, x - 0.09, x + 0.09, y - 0.11, y + 0.11, ZB + 0.02, ZB + 0.055)
            for dy in (-0.085, 0.085):
                m.bolt(steel, (x + 0.07, y + dy, ZB + 0.055), (0, 0, 1), r=0.016, h=0.012)
                m.bolt(steel, (x - 0.07, y + dy, ZB + 0.055), (0, 0, 1), r=0.016, h=0.012)
    # --- legs: two posts (front / back) braced like a ladder, base plates on foundations
    for side in (-1, 1):
        x = side * HALF
        for z in (-ZB, ZB):
            m.cyl(steel, (x, 0.36, z), (x, Y1 + 0.15, z), 0.135, seg=14, caps=(False, False))
            m.cyl(steel, (x, Y1 + 0.15, z), (x, Y1 + 0.17, z), 0.16, seg=14)                    # cap plate
            m.box(steel, x - 0.27, x + 0.27, 0.32, 0.36, z - 0.27, z + 0.27)                     # base plate
            m.box(concrete, x - 0.31, x + 0.31, 0.29, 0.325, z - 0.31, z + 0.31, bevel=0.012, seg=1)   # grout pad
            for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):                                    # stiffeners
                a = (x + dx * 0.13, 0.36, z + dz * 0.13)
                b = (x + dx * 0.255, 0.36, z + dz * 0.255)
                c = (x + dx * 0.13, 0.62, z + dz * 0.13)
                px, pz = -dz * 0.007, dx * 0.007
                m.loft(steel, [[(a[0] + px, a[1], a[2] + pz), (b[0] + px, b[1], b[2] + pz), (c[0] + px, c[1], c[2] + pz)],
                               [(a[0] - px, a[1], a[2] - pz), (b[0] - px, b[1], b[2] - pz), (c[0] - px, c[1], c[2] - pz)]])
            for dx in (-1, 1):
                for dz in (-1, 1):
                    m.bolt(steel, (x + dx * 0.21, 0.36, z + dz * 0.21), (0, 1, 0), r=0.024, h=0.02, washer=0.036, stud=0.035)
            # the bracket that carries the bottom chord
            m.box(steel, x - 0.2, x + 0.2, Y0 - 0.115, Y0 - 0.085, z - 0.16, z + 0.16)
        ys = [1.2 + k * 1.15 for k in range(5)]
        for k, y in enumerate(ys):
            m.cyl(steel, (x, y, -ZB), (x, y, ZB), BRACE_R, seg=6, caps=(False, False))
            if k + 1 < len(ys):
                a, b = (-ZB, ZB) if k % 2 else (ZB, -ZB)
                m.cyl(steel, (x, y, a), (x, ys[k + 1], b), BRACE_R, seg=6, caps=(False, False))
        # knee braces into the truss
        for z in (-ZB, ZB):
            m.cyl(steel, (x, Y0 - 1.0, z), (x - side * 1.0, Y0, z), BRACE_R, seg=6, caps=(False, False))
        with m.dense(0.8):
            m.box(concrete, x - 0.55, x + 0.55, -0.6, 0.30, -1.05, 1.05, bevel=0.03, seg=1)
    # --- the cable duct down the right leg's back post and the control cabinet on its plinth
    x = HALF
    m.box(steel, x + 0.135, x + 0.21, 0.5, Y0 + 0.1, -ZB - 0.04, -ZB + 0.04)
    for y in (1.4, 3.0, 4.6):
        m.box(steel, x - 0.15, x + 0.225, y - 0.02, y + 0.02, -ZB - 0.155, -ZB - 0.14)
    # (behind the leg along the road, inside the leg's own width: the game stretches the model across the carriageway)
    with m.at(K.move(HALF, 0, -1.8) @ K.rot_y(math.pi / 2)):
        cx, cz = 0.0, 0.0
        m.box(concrete, cx - 0.5, cx + 0.5, -0.5, 0.16, cz - 0.35, cz + 0.35, bevel=0.02, seg=1)
        m.box(cabinet, cx - 0.42, cx + 0.42, 0.16, 1.42, cz - 0.24, cz + 0.24, bevel=0.012, seg=1)
        m.box(cabinet, cx - 0.46, cx + 0.46, 1.42, 1.47, cz - 0.28, cz + 0.30, bevel=0.01, seg=1)     # its roof
        m.box(cabinet, cx - 0.39, cx + 0.39, 0.2, 1.38, cz + 0.24, cz + 0.255, bevel=0.006, seg=1)    # door
        m.box(steel, cx + 0.28, cx + 0.32, 0.72, 0.86, cz + 0.255, cz + 0.275)                         # lock
        for k in range(4):
            m.box(steel, cx - 0.3, cx + 0.1, 1.14 + k * 0.045, 1.16 + k * 0.045, cz + 0.255, cz + 0.262)   # vent
    ob = m.build(sharp=40)
    PB.finish([ob], out, 'sign_gantry', size=1024, orm_size=512, normal=False, near=0.15, wide=1.0, edge=0.02, max_len=3.0, margin=0.002)
    return [ob]


SPEC = K.Spec('sign_gantry.glb', build, [
    dict(name='front', eye=(4.0, 4.0, 26.0), target=(0, 4.5, 0), lens=30),
    dict(name='leg', eye=(13.0, 2.2, 5.0), target=(9.7, 2.6, 0), lens=35),
    dict(name='truss', eye=(5.5, 5.2, 4.2), target=(7.5, 6.6, 0), lens=40),
])

if __name__ == '__main__':
    K.run(SPEC)
