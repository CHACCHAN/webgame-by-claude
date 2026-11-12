"""
Silver birch (Birke, Betula pendula): the light edges of the autobahn's forests and the copses in the fields. A slender
white trunk with dark lenticels and black cracked patches, limbs that rise steeply and end in long hanging twigs,
small leaves that let the sky through.

    blender --background --factory-startup --python birke.py -- --out <file.glb> [--render <dir>]
"""
import math
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402

import nature_kit as K  # noqa: E402
from barks import birch  # noqa: E402
from twigs import Twig, along, curve, srgb  # noqa: E402

GREEN, LIGHT, WOOD = srgb('#4a7424'), srgb('#7b9f3a'), srgb('#3a2c26')


def leaves(tw, rng, pts, n, size):
    """small triangular leaves on thin stalks, alternate along a hanging shoot"""
    for i in range(n):
        t = 0.08 + 0.92 * (i + rng.u(0.3, 0.7)) / n
        p, d = along(pts, min(t, 0.999))
        sgn = 1 if i % 2 else -1
        side = np.array([d[1], -d[0], 0]) * sgn
        ang = math.radians(48 + rng.n(14))
        ld = d * math.cos(ang) + side * math.sin(ang) + np.array([0, 0, rng.n(0.15)])
        stalk = curve(rng, p, ld, 0.014, 2)
        tw.stem(stalk, 0.0006, 0.0005, WOOD, sides=3)
        length = size * rng.u(0.75, 1.15)
        k = 1 + rng.n(0.12)
        nrm = np.array([rng.n(0.25), rng.n(0.25), 1.0])
        tw.blade(stalk[-1], ld, nrm, length, length * 0.8, GREEN * k, LIGHT * k, shape='ovate', fold=rng.u(0.0, 0.25), curl=rng.u(-0.05, 0.2), segs=4,
                 thickness=1.0)


def twig(rng):
    """a whip 0.85 m long with side shoots, some ninety leaves"""
    tw = Twig()
    main = curve(rng, (0, 0, 0), (rng.n(0.08), 1, 0), 0.85, 12, bend=(rng.n(0.2), 0, 0), wiggle=0.3)
    tw.stem(main, 0.003, 0.0008, WOOD)
    leaves(tw, rng, main, 20, 0.055)
    for i in range(10):
        t = 0.06 + 0.72 * (i + rng.u(0.2, 0.8)) / 10
        p, d = along(main, t)
        side = np.array([d[1], -d[0], 0]) * (1 if i % 2 else -1)
        ang = math.radians(36 + rng.n(8))
        length = 0.34 * (1 - 0.45 * t) * rng.u(0.7, 1.2)
        sh = curve(rng, p, d * math.cos(ang) + side * math.sin(ang), length, 5, bend=d * 0.5, wiggle=0.3)
        tw.stem(sh, 0.0012, 0.0006, WOOD, sides=3)
        leaves(tw, rng, sh, max(3, int(length / 0.034)), 0.05)
    return tw.result()


RECIPE = {
    'trunk': dict(height=16.0, vary=0.14, radius=0.17, segs=18, sides=10, rep=1.6, taper=0.8, lean=0.06, wiggle=0.03, flare=0.4, tip=0.01),
    'levels': [
        # the limbs: steeply up, arching over at their ends
        dict(n=26, span=(0.27, 0.98), angle=lambda f, r: 44 - 20 * f + r.n(6), length=lambda f, p, r: (4.3 - 2.3 * f) * r.u(0.8, 1.15),
             droop=0.4, wiggle=0.4, segs=6, radius=0.38, rmin=0.012, tip=0.005, flex=0.5),
        # the twigs: they hang straight down
        dict(n=lambda p, r: max(3, int(p.length / 0.24)), span=(0.2, 0.98), angle=lambda f, r: 68 + r.n(12),
             length=lambda f, p, r: r.u(0.8, 1.8) * (1 - 0.3 * f), droop=1.7, wiggle=0.3, segs=4, radius_per_m=0.005, rmin=0.003, tip=0.002,
             flex=0.6, min=0.3),
    ],
    'leaf': dict(level=2, tips=[1], mode='radial', per_m=3.4, size=1.0, aspect=0.6, angle=20, rise=-0.3, face_up=0.25, face_out=1.0,
                 face_rand=0.6, bend=0.1, start=0.08, cells=['twig0', 'twig1'], tip_scale=1.1, flex=0.35),
    'clump1': 2, 'clump2': 2, 'lod1_twigs': 6, 'lod2_every': 4, 'lod2_grow': 2.0, 'lod1_branch_r': 0.02,
    'inner_dark': 0.45, 'volume_normal': 0.7,
}

BARK = birch()

SPECIES = dict(id='birke', seed=67, variants=3, recipe=RECIPE, twigs={'twig0': twig, 'twig1': twig}, twig_ao=0.015, alpha_gain=1.3,
               bark_height=BARK[0], bark_colour=BARK[1], bark_relief=1.6, impostor=(128, 320))

if __name__ == '__main__':
    K.run(SPECIES)
