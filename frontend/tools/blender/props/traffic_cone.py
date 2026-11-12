"""
Traffic cone (カラーコーン, the 700 mm kind): a blown red polyethylene cone, open at the tip, with its stacking ring
and two bands of white reflective sheeting, standing in a black recycled-rubber weight (380 mm square, rounded
corners, lifted off the ground on its feet). Used: scuffed pale where cones are stacked into each other, road dirt
up the skirt. 0.7 m tall, origin at the centre of the base on the ground; nothing in particular faces +Z.

    blender -t 4 --background --factory-startup --python traffic_cone.py -- --out <dir> [--render <dir>]

One baked material (prop_bake), without a normal map.
"""
import math
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import prop_kit as K  # noqa: E402
import prop_bake as PB  # noqa: E402

Y0, Y1 = 0.035, 0.70       # body from the top of the base to the tip
R0, R1 = 0.148, 0.026
SEG = 24


def radius(y, lift=0.0):
    t = (y - Y0) / (Y1 - Y0)
    return R0 + (R1 - R0) * t + lift


def band(m, mat, ya, yb, lift=0.0015):
    """reflective sheeting wrapped round the cone: a hair proud of it"""
    m.lathe(mat, [(radius(ya, lift), ya), (radius(yb, lift), yb)], seg=SEG, caps=(False, False))


def build(out):
    red = PB.surface('red', '#d5341c', roughness=0.5, vary=0.08, mottle=0.3, mottle_scale=6, mottle_colour='#e06a4c', mottle_rough=0.65,
                     dirt=0.6, streak=0.35, foot=0.75, foot_h=0.22, foot_colour='#4a4338', wear=0.5, wear_colour='#e8a08c')

    def sheeting(g, ch):
        # the sheeting's honeycomb of sealed cells, a shade apart
        cell = g.voronoi(150.0, feature='DISTANCE_TO_EDGE')[0]
        ch['base'] = g.mix(ch['base'], g.rgb('#b9bcb8'), g.step(cell, 0.06, 0.0))

    white = PB.surface('white', '#eceee9', roughness=0.28, vary=0.04, dirt=0.55, streak=0.4, foot=0.4, foot_h=0.22, wear=0.3,
                       wear_colour='#bfc2bd', custom=sheeting)
    rubber = PB.surface('rubber', '#1c1c1e', roughness=0.85, vary=0.12, mottle=0.4, mottle_scale=20, mottle_colour='#34322e', dirt=0.5,
                        dust=0.7, foot=0.6, foot_h=0.03, foot_colour='#5a5245', wear=0.4, wear_colour='#3c3c3e')
    pit = PB.surface('pit', '#050505', roughness=1.0, dirt=0.0, vary=0.0)

    m = K.M('traffic_cone')
    # the weight: a square of rubber with rounded corners, feet under it, a collar round the cone's skirt
    sq = K.rounded_rect(0, 0, 0.38, 0.38, 0.04, n=4)
    m.stack_rings(rubber, sq, [(0.006, 0.97), (0.012, 1.0), (0.03, 1.0), (0.038, 0.975)])
    for sx in (-1, 1):
        for sz in (-1, 1):
            m.box(rubber, sx * 0.15 - 0.025, sx * 0.15 + 0.025, 0.0, 0.008, sz * 0.15 - 0.025, sz * 0.15 + 0.025)
    m.lathe(rubber, [(0.178, 0.036), (0.178, 0.046), (0.166, 0.052), (0.158, 0.052)], seg=SEG, caps=(False, False))
    # the cone: skirt flange, stacking ring, the body, the open tip
    prof = [(0.172, 0.040), (0.172, 0.048), (0.158, 0.052), (radius(0.07), 0.07),
            (radius(0.11), 0.11), (radius(0.11, 0.004), 0.113), (radius(0.125, 0.004), 0.125), (radius(0.128), 0.128),
            (radius(0.688), 0.688), (radius(0.697, -0.003), 0.698), (radius(0.70, -0.008), 0.70), (radius(0.70, -0.010), 0.694)]
    m.lathe(red, prof, seg=SEG, caps=(False, False))
    m.lathe(pit, [(radius(0.694, -0.010), 0.694), (0.012, 0.60), (0.0, 0.60)], seg=SEG, caps=(False, False))
    band(m, white, 0.40, 0.52)   # wide upper band
    band(m, white, 0.26, 0.32)   # narrow lower band
    ob = m.build()
    PB.finish([ob], out, 'traffic_cone', size=512, orm_size=256, normal=False, near=0.04, wide=0.25, edge=0.006, max_len=0.5)
    return [ob]


SPEC = K.Spec('traffic_cone.glb', build, [
    dict(name='main', eye=(-0.9, 0.7, 1.7), target=(0, 0.34, 0), lens=45, size=(540, 720)),
    dict(name='close', eye=(0.5, 0.25, 0.7), target=(0, 0.2, 0), lens=45),
    dict(name='top', eye=(0.25, 1.0, 0.45), target=(0, 0.6, 0), lens=45),
])

if __name__ == '__main__':
    K.run(SPEC)
