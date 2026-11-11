"""
Fern (シダ): the floor of the cedar forest and the damp banks of the cuttings. A rosette of arching fronds, each a
card of one frond modelled pinna by pinna.

    blender --background --factory-startup --python shida.py -- --out <file.glb> [--render <dir>]
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

GREEN, TIP, STALK = srgb('#2c5520'), srgb('#52802f'), srgb('#4c4a22')


def frond(rng):
    """the stalk with its pinnae left and right, longest a third of the way up, each pinna toothed into lobes"""
    tw = Twig()
    main = curve(rng, (0, 0, 0), (rng.n(0.04), 1, 0), 0.72, 12, bend=(rng.n(0.12), 0, 0), wiggle=0.05)
    tw.stem(main, 0.0028, 0.0008, STALK, sides=4)
    n = 22
    for i in range(n):
        t = 0.14 + 0.86 * (i + 0.5) / n
        p, d = along(main, t)
        size = 0.17 * math.sin(math.pi * min(1.0, (t - 0.08) ** 0.6)) ** 1.1 + 0.014
        for sgn in (-1, 1):
            side = np.array([d[1], -d[0], 0]) * sgn
            pd = d * 0.34 + side * 0.94
            k = 1 + rng.n(0.1)
            pin = curve(rng, p, pd, size * rng.u(0.9, 1.08), 4, bend=d * 0.25)
            # a pinna: lobes along its own little midrib
            m = max(3, int(size / 0.012))
            for j in range(m):
                q, e = along(pin, (j + 0.5) / m)
                w = 0.021 * (1 - 0.7 * j / m)
                for s2 in (-1, 1):
                    ld = e * 0.45 + np.array([e[1], -e[0], 0]) * s2 * 0.9
                    tw.blade(q, ld, (rng.n(0.15), rng.n(0.15), 1), w, w * 0.95, GREEN * k, TIP * k, shape='scale', fold=0.1, segs=2, thickness=1.0)
    return tw.result()


RECIPE = {
    'trunk': dict(height=0.06, vary=0.0, radius=0.01, segs=2, hidden=True, lean=0.0, wiggle=0.0),
    'levels': [
        dict(n=9, span=(0.9, 0.99), angle=lambda f, r: r.u(28, 62), length=lambda f, p, r: 0.03, segs=1, radius_per_m=0.01, rmin=0.001, tip=0.001,
             flex=0.0, min=0.01),
    ],
    'leaf': dict(level=9, tips=[1], mode='fan', face='up', size=0.8, aspect=0.5, roll=14, bend=0.55, card_segs=4, cells=['twig0', 'twig1'], flex=0.8),
    'clump1': 0, 'clump2': 0, 'lod1_twigs': 2, 'lod2_every': 1, 'lod2_grow': 1.1, 'clump_sway': 0.5,
    'inner_dark': 0.6, 'volume_normal': 0.3, 'normal_up': 0.6, 'ground_ao': 0.5,
}

BARK = smooth('#6a6a58', '#4a4a3c', '#8a8a70')

SPECIES = dict(id='shida', seed=79, variants=3, recipe=RECIPE, twigs={'twig0': frond, 'twig1': frond}, twig_ao=0.01, alpha_gain=1.4,
               bark_height=BARK[0], bark_colour=BARK[1], impostor=None)

if __name__ == '__main__':
    K.run(SPECIES)
