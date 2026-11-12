"""
Curve mirror (道路反射鏡, the φ800 single-face kind): an orange steel pole (φ89.1) in a concrete collar, the convex
stainless mirror (curvature radius about 3 m) in its orange shell with a rim and a hood over the upper half, held by a
clamp block on two U-bolts and a pivot yoke, tipped down 6 degrees; under it the yellow 注意 plate on two band clamps,
on the pole the road office's sticker. The glass faces +Z. 3.57 m to the hood's top, origin at the foot of the pole on
the ground (the collar reaches 0.12 m into it).

    blender -t 4 --background --factory-startup --python curve_mirror.py -- --out <dir> [--render <dir>]

One baked material (prop_bake), without a normal map: the mirror's reflection must stay clean.
"""
import math
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import prop_kit as K  # noqa: E402
import prop_bake as PB  # noqa: E402

CY, CZ = 3.14, 0.20   # mirror centre
TILT = math.radians(6)
RP = 0.0445           # the pole's radius
RG = 0.37             # the glass


def dome(m, mat, base_r, height, sign, seg=32, steps=7):
    """a spherical cap seen from +Z (sign +1: bulging towards +Z, -1: towards -Z), base on the z = 0 plane"""
    rs = (base_r ** 2 + height ** 2) / (2 * height)
    prof = [(base_r, 0.0)]
    for i in range(1, steps + 1):
        phi = math.asin(base_r / rs) * (1 - i / steps)
        prof.append((rs * math.sin(phi), (rs * math.cos(phi) - (rs - height))))
    prof[-1] = (0.0, height)
    with m.at(K.rot_x(sign * math.pi / 2)):
        m.lathe(mat, prof, seg=seg, caps=(False, False))   # (its flat side lies inside the mirror)


def wrapped(m, mat, y0, y1, half, r, n=6):
    """a sticker lying round the pole's front (+Z), `half` metres to each side"""
    a = half / r
    for k in range(n):
        t0, t1 = -a + 2 * a * k / n, -a + 2 * a * (k + 1) / n
        pts = [(r * math.sin(t0), y0, r * math.cos(t0)), (r * math.sin(t1), y0, r * math.cos(t1)),
               (r * math.sin(t1), y1, r * math.cos(t1)), (r * math.sin(t0), y1, r * math.cos(t0))]
        uv = [(k / n, 0), ((k + 1) / n, 0), ((k + 1) / n, 1), (k / n, 1)]
        with m.uvmap(lambda cs, uv=uv: uv, only=mat):
            m.quad(mat, pts)


def build(out):
    d = K.paint(out, ['mirror'])
    orange = PB.surface('orange', '#e0611c', roughness=0.46, vary=0.1, mottle=0.3, mottle_scale=7, mottle_colour='#e58a52', mottle_rough=0.62,
                        dirt=0.55, streak=0.45, foot=0.5, foot_h=0.3, rust=0.3, wear=0.35, wear_colour='#b9ad9f')
    glass = PB.surface('mirror', '#dfe6ea', metallic=1.0, roughness=0.05, vary=0.0, rough_vary=0.0, mottle=0.14, mottle_scale=34,
                       mottle_colour='#cdd4d8', mottle_rough=0.2, dirt=0.5, streak=0.12)
    zinc = PB.surface('zinc', '#a3a8a8', metallic=0.7, roughness=0.45, rust=0.45, dirt=0.5)
    conc = PB.surface('concrete', '#8d8c85', roughness=0.9, vary=0.14, mottle=0.45, mottle_scale=30, dirt=0.7, foot=0.6, foot_h=0.05, moss=0.5)
    tag = PB.surface('tag', '#ffffff', roughness=0.4, image=K.load_image(os.path.join(d, 'mirror_tag.png')), dirt=0.45, streak=0.3, vary=0.03)
    chui = PB.surface('chui', '#ffffff', roughness=0.4, image=K.load_image(os.path.join(d, 'mirror_chui.png')), dirt=0.5, streak=0.45, vary=0.05,
                      rust=0.12, wear=0.2)

    m = K.M('curve_mirror')
    # collar, pole with a domed cap
    with m.dense(0.7):
        m.lathe(conc, [(0.17, -0.12), (0.17, 0.035), (0.155, 0.05), (0.05, 0.055)], seg=16)
    m.lathe(orange, [(RP, 0.04), (RP, 3.385), (RP - 0.006, 3.40), (0.0, 3.408)], seg=16)
    with m.dense(3.0):
        wrapped(m, tag, 1.45, 1.555, 0.035, RP + 0.0006)
    # the 注意 plate: two band clamps, a spacer each, the plate
    for y in (2.455, 2.535):
        m.cyl(zinc, (0, y - 0.011, 0), (0, y + 0.011, 0), RP + 0.003, seg=16, caps=(False, False))
        m.box(zinc, -0.03, 0.03, y - 0.011, y + 0.011, RP - 0.004, RP + 0.014)
        for sx in (-0.02, 0.02):
            m.bolt(zinc, (sx, y, RP + 0.019), (0, 0, 1), r=0.006, h=0.004)
    m.box(zinc, -0.20, 0.20, 2.42, 2.57, RP + 0.014, RP + 0.019, bevel=0.002, seg=1)
    with m.dense(2.0):
        with m.uvmap(lambda cs: [((c.x + 0.2) / 0.4, (c.y - 2.42) / 0.15) for c in cs], only=chui):
            m.quad(chui, [(-0.198, 2.422, RP + 0.0195), (0.198, 2.422, RP + 0.0195), (0.198, 2.568, RP + 0.0195), (-0.198, 2.568, RP + 0.0195)])
    # the clamp block on the pole: two U-bolts round it, their nuts on the block's face
    m.box(orange, -0.05, 0.05, CY - 0.08, CY + 0.08, RP - 0.012, RP + 0.03, bevel=0.005, seg=1)
    for y in (CY - 0.055, CY + 0.055):
        m.torus(zinc, (0, y, 0), RP + 0.005, 0.005, 'y', seg=20, tube=6)
        for sx in (-0.036, 0.036):
            m.bolt(zinc, (sx, y, RP + 0.03), (0, 0, 1), r=0.008, h=0.007, stud=0.006)
    # the mirror, tipped down about the X axis
    with m.at(K.move(0, CY, CZ) @ K.rot_x(TILT)):
        dome(m, glass, RG, 0.024, +1, seg=40, steps=7)                      # the convex glass
        m.torus(orange, (0, 0, 0.004), RG + 0.016, 0.02, 'z', seg=40, tube=8)  # rim
        dome(m, orange, RG + 0.03, 0.055, -1, seg=40, steps=4)              # back shell
        m.cyl(orange, (0, 0, -0.04), (0, 0, -0.068), 0.085, 0.075, seg=20)   # the boss the bracket bolts to
        for k in range(4):
            a = math.pi / 4 + k * math.pi / 2
            m.bolt(zinc, (0.055 * math.cos(a), 0.055 * math.sin(a), -0.068), (0, 0, -1), r=0.008, h=0.006)
        # hood over the upper half: deepest at the top, running out towards its ends
        rings = []
        for i in range(25):
            t = i / 24
            a = math.radians(-12 + 204 * t)
            depth = 0.03 + 0.125 * math.sin(math.pi * t) ** 0.6
            r0, r1 = RG + 0.034, RG + 0.039
            c, s = math.cos(a), math.sin(a)
            rings.append([(r0 * c, r0 * s, -0.02), (r1 * c, r1 * s, -0.02), (r1 * c, r1 * s, depth), (r0 * c, r0 * s, depth)])
        m.loft(orange, rings)
        # the yoke and its pivot bolt
        for sx in (-0.034, 0.034):
            m.box(orange, sx - 0.004, sx + 0.004, -0.035, 0.035, -0.135, -0.066, bevel=0.002, seg=1)
        m.cyl(zinc, (-0.05, 0, -0.112), (0.05, 0, -0.112), 0.007, seg=8)
        m.bolt(zinc, (0.038, 0, -0.112), (1, 0, 0), r=0.012, h=0.008)
        m.bolt(zinc, (-0.038, 0, -0.112), (-1, 0, 0), r=0.012, h=0.008)
    # the arm from the block to the pivot
    m.box(orange, -0.028, 0.028, CY - 0.03, CY + 0.03, RP + 0.025, CZ - 0.10, bevel=0.004, seg=1)
    ob = m.build()
    PB.finish([ob], out, 'curve_mirror', size=1024, orm_size=512, normal=False, near=0.06, wide=0.4, edge=0.008, max_len=1.2)
    return [ob]


SPEC = K.Spec('curve_mirror.glb', build, [
    dict(name='main', eye=(-4.2, 2.2, 7.5), target=(0, 1.8, 0), lens=38, size=(540, 720)),
    dict(name='close', eye=(-1.9, 3.6, 2.6), target=(0, 3.0, 0), lens=45),
    dict(name='plate', eye=(-0.7, 2.3, 1.4), target=(0, 2.4, 0), lens=45),
    dict(name='back', eye=(1.6, 3.3, -2.2), target=(0, 3.05, 0), lens=45),
])

if __name__ == '__main__':
    K.run(SPEC)
