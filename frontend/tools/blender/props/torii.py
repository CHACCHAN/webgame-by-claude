"""
Torii of a roadside shrine (Inari style, painted timber): two round pillars leaning in a little, each standing on a
granite kamebara that goes into the ground, a black root band (nemaki) and a ring (daiwa) under the beams; the tie
beam (nuki) through both pillars with its wedges, the name board 朧神社 hung in front of the centre post, the
vermilion shimaki and the black kasagi over it, both with rising ends cut on the slant; a straw rope (shimenawa)
with paper streamers and tassels between the pillars. The paint is old: faded where the sun reaches, checked along
the grain, rubbed to the wood at the edges, green at the foot. 4.6 m above the ground; the way through runs along Z
(the beams along X, the name board faces +Z); origin at the centre of the footprint on the ground (the stones reach
0.25 m into it).

    blender -t 4 --background --factory-startup --python torii.py -- --out <dir> [--render <dir>]

One baked material (prop_bake).
"""
import math
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import prop_kit as K  # noqa: E402
import prop_bake as PB  # noqa: E402

PX = 1.55          # pillar centre at the foot
LEAN = 0.06        # inward at the top
Y_FOOT, Y_TOP = 0.12, 3.98
SEG = 24
ROPE_Y, ROPE_SAG = 3.00, 0.16
TILT = math.radians(8)


def pillar_x(y, sign):
    t = (y - Y_FOOT) / (Y_TOP - Y_FOOT)
    return sign * (PX - LEAN * t)


def rad(y):
    return 0.205 - 0.04 * (y - Y_FOOT) / (Y_TOP - Y_FOOT)


def curve(x, half, lift):
    return lift * (abs(x) / half) ** 2.4


def beam(m, mat, half, y0, section, lift, n=25, cut=0.0):
    """a beam along x, its underside at y0, the ends lifted by `lift` and cut on the slant (`cut` m per m of height);
    section [(z, y)] (y relative to y0)"""
    rings = []
    for i in range(n):
        x = -half + 2 * half * i / (n - 1)
        dy = curve(x, half, lift)
        rings.append([(x + x / half * cut * y, y0 + dy + y, z) for z, y in section])
    m.loft(mat, rings)


def rope_at(x, half):
    return ROPE_Y - ROPE_SAG * (1 - (x / half) ** 2)


def rope(m, mat, half, n=56, lobes=3, pts=12):
    """a left-laid straw rope between the pillars, thickest in the middle"""
    rings = []
    for i in range(n + 1):
        x = -half + 2 * half * i / n
        y = rope_at(x, half)
        r = 0.032 + 0.022 * (1 - (x / half) ** 2)
        tw = x * 2 * math.pi / 0.42
        ring = []
        for k in range(pts):
            a = 2 * math.pi * k / pts
            rr = r * (0.80 + 0.20 * math.cos(lobes * a))
            ring.append((x, y + rr * math.cos(a + tw), rr * math.sin(a + tw)))
        rings.append(ring)
    m.loft(mat, rings)


def checks(stretch):
    """the timber's drying cracks under the paint, along the grain"""
    def fn(g, ch):
        n = g.noise(46.0, 2.0, 0.5, stretch=stretch, seed=7.0)
        line = g.step(n, 0.69, 0.74)
        ch['base'] = g.mix(ch['base'], g.rgb('#2e1a13'), g.mul(line, 0.85))
        ch['height'] = g.add(ch['height'], g.mul(line, -0.7))
        ch['rough'] = g.add(ch['rough'], g.mul(line, 0.3))
    return fn


def build(out):
    d = K.paint(out, ['torii'])
    paint = dict(roughness=0.44, vary=0.14, mottle=0.55, mottle_scale=3.5, mottle_colour='#c8674a', mottle_rough=0.7, grain=0.25,
                 grain_scale=70, dirt=0.6, streak=0.55, foot=0.35, foot_h=0.9, foot_colour='#5a3a2a', moss=0.25, wear=0.45,
                 wear_colour='#8f6f58')
    red_y = PB.surface('vermilion_y', '#b92f17', fibre=(1, 0.05, 1), custom=checks((1, 0.03, 1)), **paint)
    red_x = PB.surface('vermilion_x', '#b92f17', fibre=(0.05, 1, 1), custom=checks((0.03, 1, 1)), **paint)
    lacquer = dict(roughness=0.5, vary=0.1, mottle=0.4, mottle_scale=5, mottle_colour='#3a352d', mottle_rough=0.75, grain=0.2, grain_scale=70,
                   dirt=0.3, dust=0.6, moss=0.35, streak=0.3, wear=0.4, wear_colour='#6b5a48')
    black = PB.surface('black', '#1b1815', fibre=(0.05, 1, 1), **lacquer)
    black_y = PB.surface('black_y', '#1b1815', fibre=(1, 0.05, 1), foot=0.5, foot_h=0.3, foot_colour='#4a4636', **lacquer)
    stone = PB.surface('granite', '#85837c', roughness=0.88, vary=0.14, mottle=0.6, mottle_scale=60, mottle_colour='#55544f', grain=0.8,
                       grain_scale=160, dirt=0.8, foot=0.85, foot_h=0.14, foot_colour='#4f5339', moss=0.8, streak=0.3)
    straw = PB.surface('straw', '#b89f62', roughness=0.9, vary=0.12, mottle=0.5, mottle_scale=40, mottle_colour='#8d7446', grain=0.9,
                       grain_scale=220, fibre=(0.3, 1, 1), dirt=0.75, streak=0.2)
    paper = PB.surface('paper', '#efede4', roughness=0.8, vary=0.05, dirt=0.4, streak=0.25)
    plaque = PB.surface('plaque', '#ffffff', roughness=0.35, image=K.load_image(os.path.join(d, 'torii_plaque.png')), vary=0.05, dirt=0.5,
                        streak=0.3, dust=0.3)

    m = K.M('torii')
    for s in (-1, 1):
        # the stone under the pillar: a turned granite bun (kamebara) on its footing, into the ground
        m.lathe(stone, [(0.42, -0.25), (0.42, 0.015), (0.405, 0.055), (0.36, 0.095), (0.285, 0.12), (0.20, 0.125)], seg=SEG, cx=s * PX,
                caps=(False, True))
        # the black root band, a hair thicker than the pillar, with a lip at its top
        m.lathe(black_y, [(rad(Y_FOOT) + 0.018, Y_FOOT - 0.01), (rad(0.60) + 0.016, 0.60), (rad(0.62) + 0.022, 0.615), (rad(0.65) + 0.022, 0.645),
                        (rad(0.66) + 0.004, 0.66)], seg=SEG, cx=s * PX, caps=(False, False))
        levels = [Y_FOOT, 0.64, 1.3, 2.0, 2.7, 3.4, Y_TOP]
        rings = [[(pillar_x(y, s) + rad(y) * math.cos(2 * math.pi * k / SEG), y, rad(y) * math.sin(2 * math.pi * k / SEG)) for k in range(SEG)]
                 for y in levels]
        m.loft(red_y, rings, cap0=False, cap1=False)
        # the ring under the beams
        yd = 3.885
        m.lathe(red_y, [(rad(yd) + 0.004, yd - 0.012), (rad(yd) + 0.075, yd), (rad(yd) + 0.075, yd + 0.065), (rad(yd) + 0.004, yd + 0.075)], seg=SEG,
                cx=pillar_x(yd, s), caps=(False, False))
        # wedges driven in over the tie beam, from both sides
        xp = pillar_x(3.43, s)
        for o in (-1, 1):
            xa, xb = xp + o * (rad(3.43) - 0.03), xp + o * (rad(3.43) + 0.15)
            m.loft(red_x, [[(xa, 3.40, -0.045), (xa, 3.40, 0.045), (xa, 3.47, 0.045), (xa, 3.47, -0.045)],
                           [(xb, 3.40, -0.045), (xb, 3.40, 0.045), (xb, 3.432, 0.045), (xb, 3.432, -0.045)]])
        # the rope's turn round the pillar
        yr = ROPE_Y
        m.torus(straw, (pillar_x(yr, s), yr, 0), rad(yr) + 0.026, 0.03, axis='y', seg=SEG, tube=8)
    # tie beam, centre post
    m.box(red_x, -1.98, 1.98, 3.22, 3.40, -0.085, 0.085, bevel=0.01, seg=1)
    m.box(red_y, -0.075, 0.075, 3.40, 3.99, -0.06, 0.06, bevel=0.008, seg=1)
    # the name board in its frame, hung leaning forward
    w, h = 0.40, 0.60
    yc, zc = 3.665, 0.06 + 0.024 + h / 2 * math.sin(TILT)

    def board_uv(cs):
        return [((c.x + w / 2) / w, 0.5 + (c.y - yc) / (h * math.cos(TILT))) for c in cs]

    with m.at(K.move(0, yc, zc) @ K.rot_x(TILT)):
        with m.dense(3.0), m.uvmap(board_uv, only=plaque):
            m.box(black, -w / 2, w / 2, -h / 2, h / 2, -0.016, 0.016, front=plaque)
        for x0, x1, y0, y1 in ((-w / 2 - 0.03, w / 2 + 0.03, h / 2, h / 2 + 0.03), (-w / 2 - 0.03, w / 2 + 0.03, -h / 2 - 0.03, -h / 2),
                               (-w / 2 - 0.03, -w / 2, -h / 2, h / 2), (w / 2, w / 2 + 0.03, -h / 2, h / 2)):
            m.box(black, x0, x1, y0, y1, -0.02, 0.028, bevel=0.004, seg=1)
    # shimaki (vermilion) and kasagi (black, a low gable with a lip): the ends rise and are cut on the slant
    beam(m, red_x, 2.40, 3.93, [(-0.14, 0.0), (0.14, 0.0), (0.14, 0.15), (-0.14, 0.15)], 0.10, cut=0.18)
    beam(m, black, 2.57, 4.07, [(-0.24, 0.0), (0.24, 0.0), (0.24, 0.125), (0.265, 0.135), (0.265, 0.155), (0.0, 0.28), (-0.265, 0.155),
                                (-0.265, 0.135), (-0.24, 0.125)], 0.25, cut=0.18)
    # the rope, its paper streamers (shide) and straw tassels
    half = PX - LEAN * 0.75 - rad(ROPE_Y) + 0.02
    rope(m, straw, half)
    for x in (-0.96, -0.32, 0.32, 0.96):
        y = rope_at(x, half) - 0.03
        for k in range(4):
            dx = (0.045 if k % 2 else 0.0)
            m.box(paper, x + dx - 0.04, x + dx + 0.04, y - 0.085 * (k + 1), y - 0.085 * k + 0.004, 0.012 + k * 0.004, 0.015 + k * 0.004)
    for x in (-0.64, 0.0, 0.64):
        y = rope_at(x, half) - 0.02
        m.cyl(straw, (x, y, 0), (x, y - 0.30, 0), 0.014, 0.04, seg=8)
    ob = m.build()
    PB.finish([ob], out, 'torii', size=2048, orm_size=1024, normal_size=1024, near=0.10, wide=0.8, edge=0.012, max_len=1.6, margin=0.003)
    return [ob]


SPEC = K.Spec('torii.glb', build, [
    dict(name='main', eye=(-6.2, 2.4, 8.5), target=(0, 2.2, 0), lens=34),
    dict(name='top', eye=(-2.2, 3.0, 4.6), target=(-0.3, 3.7, 0), lens=45),
    dict(name='foot', eye=(-0.4, 0.9, 2.2), target=(-1.5, 0.35, 0), lens=40),
])

if __name__ == '__main__':
    K.run(SPEC)
