"""
Hinoki cypress (檜, Chamaecyparis obtusa): planted beside the cedar on the drier slopes. A straight trunk with
red-brown bark in long strips, a dense broad cone with a blunt top, the foliage in flat fans of scale leaves that
lie level and droop at their tips.

    blender --background --factory-startup --python hinoki.py -- --out <file.glb> [--render <dir>]
"""
import math
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402

import nature_kit as K  # noqa: E402
from barks import strips  # noqa: E402
from twigs import Twig, along, curve, srgb  # noqa: E402

GREEN, TIP, OLD, WOOD = srgb('#27491f'), srgb('#4d772d'), srgb('#6a5226'), srgb('#5a3d28')


def twig(rng):
    """a flat fan 0.5 m long: the axis, side shoots left and right, each forked twice, all clothed in blunt scales"""
    tw = Twig()
    main = curve(rng, (0, 0, 0), (rng.n(0.05), 1, 0), 0.5, 8, bend=(rng.n(0.12), 0, 0), wiggle=0.08)
    tw.stem(main, 0.004, 0.0015, WOOD)
    axes = [main]
    n = 13
    for i in range(n):
        t = 0.1 + 0.85 * (i + rng.u(0.25, 0.75)) / n
        p, d = along(main, t)
        sgn = 1 if i % 2 else -1
        side = np.array([d[1], -d[0], 0]) * sgn
        length = (0.24 * (1 - t) ** 0.8 + 0.05) * rng.u(0.85, 1.15)
        ang = math.radians(46 + rng.n(5))
        sh = curve(rng, p, d * math.cos(ang) + side * math.sin(ang), length, 5, bend=d * 0.35, wiggle=0.05)
        axes.append(sh)
        m = max(2, int(length / 0.028))
        for j in range(m):
            q, e = along(sh, 0.15 + 0.8 * (j + rng.u(0.3, 0.7)) / m)
            s2 = np.array([e[1], -e[0], 0]) * (1 if j % 2 else -1)
            l2 = length * 0.36 * (1 - 0.6 * j / m) * rng.u(0.8, 1.2)
            sub = curve(rng, q, e * 0.72 + s2 * 0.7, l2, 3, bend=e * 0.3)
            axes.append(sub)
            # the last fork: the little fingers of the fan
            for k in range(int(l2 / 0.02)):
                u, g = along(sub, 0.3 + 0.6 * (k + 0.5) / max(1, int(l2 / 0.02)))
                s3 = np.array([g[1], -g[0], 0]) * (1 if k % 2 else -1)
                axes.append(curve(rng, u, g * 0.75 + s3 * 0.65, rng.u(0.012, 0.022), 2))
    for pts in axes:
        old = rng.u() < 0.05
        tw.needles(rng, pts, 0.0055, 0.0052, OLD if old else GREEN, OLD * 1.2 if old else TIP, spacing=0.0034, lean=28, flat=1.0, thickness=0.6,
                   vary=0.14, shape='scale')
    return tw.result()


def crown(f):
    """bough length by its place up the crown (0 = lowest bough … 1 = the tip): fuller than the cedar's, a blunt top"""
    low = 0.7 + 0.3 * min(1.0, f / 0.12)
    return (3.3 * (1 - f) ** 0.58 + 0.35) * low


RECIPE = {
    'trunk': dict(height=15.5, vary=0.1, radius=0.26, segs=18, sides=12, rep=2.0, taper=0.85, lean=0.03, wiggle=0.012, flare=0.5),
    'levels': [
        # the boughs: level, their tips hanging
        dict(n=86, span=(0.27, 0.985), angle=lambda f, r: 90 - 40 * f ** 1.5 + r.n(5), length=lambda f, p, r: crown(f) * r.u(0.82, 1.12),
             droop=0.3, droop_by=lambda f: 1 - 0.7 * f, upturn=0.12, wiggle=0.14, segs=6, radius_per_m=0.0125, tip=0.004, flex=0.5),
        dict(n=lambda p, r: max(2, int(p.length / 0.29)), span=(0.12, 0.95), planar=True, angle=lambda f, r: 54 + r.n(7),
             length=lambda f, p, r: p.length * 0.5 * (1 - 0.66 * f) * r.u(0.7, 1.12), droop=0.22, wiggle=0.08, segs=3, radius_per_m=0.008,
             rmin=0.003, tip=0.002, flex=0.3, lift=0.08, min=0.12),
    ],
    # the fans lie nearly flat in the bough's plane: the crown reads as plates of foliage
    'leaf': dict(level=2, tips=[1], mode='fan', per_m=4.0, size=0.72, aspect=0.82, angle=40, roll=20, bend=0.4, start=0.04,
                 cells=['twig0', 'twig1'], tip_scale=1.15, flex=0.25),
    'clump1': 1, 'clump2': 1, 'lod1_twigs': 5, 'lod2_every': 2, 'lod2_grow': 1.5,
    'inner_dark': 0.32, 'volume_normal': 0.7,
}

BARK = strips('#2b1e17', '#63432f', '#75695c', weathered=0.4)

SPECIES = dict(id='hinoki', seed=23, variants=3, recipe=RECIPE, twigs={'twig0': twig, 'twig1': twig}, twig_ao=0.015, alpha_gain=1.5,
               bark_height=BARK[0], bark_colour=BARK[1], bark_relief=2.0, impostor=(128, 320))

if __name__ == '__main__':
    K.run(SPECIES)
