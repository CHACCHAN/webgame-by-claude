"""
Norway spruce (Fichte, Picea abies): the dark forests along the autobahn. A straight trunk with grey-brown scaly
bark, boughs from near the ground in a narrow spire, their ends swept up and the branchlets hanging from them like
the teeth of a comb.

    blender --background --factory-startup --python fichte.py -- --out <file.glb> [--render <dir>]
"""
import math
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402

import nature_kit as K  # noqa: E402
from barks import plates  # noqa: E402
from twigs import Twig, along, curve, srgb  # noqa: E402

GREEN, TIP, OLD, WOOD = srgb('#1d3a22'), srgb('#3f6b36'), srgb('#5c4a28'), srgb('#5a4330')


def twig(rng):
    """a branchlet 0.5 m long with side shoots in one plane, short stiff needles all round every axis"""
    tw = Twig()
    main = curve(rng, (0, 0, 0), (rng.n(0.05), 1, 0), 0.5, 8, bend=(rng.n(0.1), 0, 0), wiggle=0.1)
    tw.stem(main, 0.004, 0.0015, WOOD)
    axes = [main]
    n = 12
    for i in range(n):
        t = 0.1 + 0.8 * (i + rng.u(0.25, 0.75)) / n
        p, d = along(main, t)
        sgn = 1 if i % 2 else -1
        side = np.array([d[1], -d[0], 0]) * sgn
        length = (0.2 * (1 - t) + 0.07) * rng.u(0.8, 1.2)
        ang = math.radians(54 + rng.n(7))
        sh = curve(rng, p, d * math.cos(ang) + side * math.sin(ang) + np.array([0, 0, rng.n(0.15)]), length, 5, bend=d * 0.3, wiggle=0.1)
        tw.stem(sh, 0.002, 0.001, WOOD)
        axes.append(sh)
        if length > 0.14:
            for j in range(2):
                q, e = along(sh, 0.35 + 0.3 * j + rng.u(0, 0.1))
                s2 = np.array([e[1], -e[0], 0]) * (1 if j % 2 else -1)
                axes.append(curve(rng, q, e * 0.7 + s2 * 0.7, length * 0.4, 3, bend=e * 0.3))
    for pts in axes:
        old = rng.u() < 0.05
        tw.needles(rng, pts, 0.016, 0.0019, OLD if old else GREEN, OLD * 1.2 if old else TIP, spacing=0.0021, lean=58, flat=0.35, thickness=0.7,
                   vary=0.15)
    return tw.result()


def crown(f):
    low = 0.6 + 0.4 * min(1.0, f / 0.2)
    return (3.5 * (1 - f) ** 0.9 + 0.28) * low


RECIPE = {
    'trunk': dict(height=19.0, vary=0.12, radius=0.27, segs=20, sides=12, rep=2.0, taper=0.9, lean=0.025, wiggle=0.01, flare=0.45),
    'levels': [
        # the boughs: down and out, the end swept up
        dict(n=104, span=(0.1, 0.985), angle=lambda f, r: 100 - 42 * f ** 1.4 + r.n(5), length=lambda f, p, r: crown(f) * r.u(0.84, 1.12),
             droop=0.35, droop_by=lambda f: 1 - 0.6 * f, upturn=0.8, wiggle=0.12, segs=6, radius_per_m=0.012, tip=0.004, flex=0.5),
        # the branchlets: they hang
        dict(n=lambda p, r: max(2, int(p.length / 0.25)), span=(0.14, 0.95), planar=True, angle=lambda f, r: 62 + r.n(7),
             length=lambda f, p, r: p.length * 0.42 * (1 - 0.6 * f) * r.u(0.7, 1.12), droop=0.95, wiggle=0.08, segs=3, radius_per_m=0.008,
             rmin=0.003, tip=0.002, flex=0.4, lift=0.1, min=0.12),
    ],
    'leaf': dict(level=2, tips=[1], mode='fan', per_m=3.7, size=0.76, aspect=0.6, angle=34, roll=34, bend=0.45, start=0.04,
                 cells=['twig0', 'twig1'], tip_scale=1.15, flex=0.3),
    'clump1': 1, 'clump2': 1, 'lod1_twigs': 5, 'lod2_every': 2, 'lod2_grow': 1.5,
    'inner_dark': 0.3, 'volume_normal': 0.72,
}

BARK = plates('#261c17', '#5f4838', '#6f5642', '#6d655c', size=0.55)

SPECIES = dict(id='fichte', seed=59, variants=3, recipe=RECIPE, twigs={'twig0': twig, 'twig1': twig}, twig_ao=0.02, alpha_gain=1.7,
               bark_height=BARK[0], bark_colour=BARK[1], bark_relief=2.0, impostor=(128, 352))

if __name__ == '__main__':
    K.run(SPECIES)
