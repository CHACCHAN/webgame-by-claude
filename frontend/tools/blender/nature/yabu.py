"""
A thicket shrub (藪: an evergreen like hisakaki or aoki; on the autobahn it passes for the hedge bushes of the
embankments): many stems from one stool, glossy dark leaves all the way down.

    blender --background --factory-startup --python yabu.py -- --out <file.glb> [--render <dir>]
"""
import math
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402

import nature_kit as K  # noqa: E402
from barks import smooth  # noqa: E402
from twigs import Twig, along, curve, srgb  # noqa: E402

GREEN, LIGHT, WOOD = srgb('#234a1b'), srgb('#467329'), srgb('#4a3d2c')


def twig(rng):
    """a shoot 0.45 m long, its leaves spirally set and held out flat"""
    tw = Twig()
    main = curve(rng, (0, 0, 0), (rng.n(0.06), 1, 0), 0.45, 9, bend=(rng.n(0.15), 0, 0), wiggle=0.25)
    tw.stem(main, 0.0025, 0.001, WOOD)
    n = 26
    for i in range(n):
        t = 1.0 if i == n - 1 else 0.1 + 0.9 * (i + rng.u(0.3, 0.7)) / n
        p, d = along(main, min(t, 0.999))
        side = np.array([d[1], -d[0], 0]) * (1 if i % 2 else -1)
        ang = 0.0 if i == n - 1 else math.radians(50 + rng.n(12))
        ld = d * math.cos(ang) + side * math.sin(ang) + np.array([0, 0, rng.n(0.2)])
        length = rng.u(0.075, 0.105)
        k = 1 + rng.n(0.12)
        # this year's leaves at the tip are lighter
        young = t > 0.75
        tw.blade(p + ld * 0.004, ld, (rng.n(0.25), rng.n(0.25), 1), length, length * 0.42, (LIGHT if young else GREEN) * k, LIGHT * k * (1.15 if young else 1),
                 shape='ovate', fold=rng.u(0.1, 0.35), curl=rng.u(0.0, 0.25), segs=5, thickness=0.8)
    return tw.result()


RECIPE = {
    'trunk': dict(height=0.2, vary=0.0, radius=0.03, segs=2, hidden=True, lean=0.0, wiggle=0.0),
    'levels': [
        # the stems
        dict(n=14, span=(0.8, 0.98), angle=lambda f, r: r.u(6, 58), length=lambda f, p, r: r.u(0.8, 1.6), droop=-0.25, wiggle=0.5, segs=4,
             radius_per_m=0.012, rmin=0.008, tip=0.004, flex=0.5),
        dict(n=lambda p, r: max(3, int(p.length / 0.15)), span=(0.12, 0.97), angle=lambda f, r: 52 + r.n(12),
             length=lambda f, p, r: r.u(0.28, 0.6) * (1 - 0.3 * f), droop=0.1, wiggle=0.3, segs=2, radius_per_m=0.01, rmin=0.003, tip=0.002,
             flex=0.4, min=0.15),
    ],
    'leaf': dict(level=2, tips=[1], mode='radial', per_m=6.0, size=0.52, aspect=0.8, angle=45, face_up=1.0, face_out=0.7, face_rand=0.5, bend=0.12,
                 start=0.1, cells=['twig0', 'twig1'], tip_scale=1.1, flex=0.3),
    'clump1': 0, 'clump2': 0, 'lod1_twigs': 3, 'lod2_every': 1, 'lod2_grow': 1.05, 'clump_sway': 0.3,
    'inner_dark': 0.3, 'volume_normal': 0.75, 'ground_ao': 0.3,
}

BARK = smooth('#6b5f4c', '#463d30', '#8b8872')

SPECIES = dict(id='yabu', seed=89, variants=3, recipe=RECIPE, twigs={'twig0': twig, 'twig1': twig}, twig_ao=0.015, alpha_gain=1.3,
               bark_height=BARK[0], bark_colour=BARK[1], impostor=None)

if __name__ == '__main__':
    K.run(SPECIES)
