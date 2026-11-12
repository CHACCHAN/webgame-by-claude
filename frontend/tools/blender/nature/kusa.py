"""
Grass (草): the tufts of the verge and of every open bit of ground near the road. Each card is a bunch of blades
modelled one by one; a tuft is six of them leaning out from one root.

    blender --background --factory-startup --python kusa.py -- --out <file.glb> [--render <dir>]
"""
import math
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402

import nature_kit as K  # noqa: E402
from barks import smooth  # noqa: E402
from twigs import Twig, curve, srgb  # noqa: E402

GREEN, TIP, DRY = srgb('#38581d'), srgb('#6f8f38'), srgb('#93843f')


def bunch(seed_heads):
    def twig(rng):
        tw = Twig()
        for i in range(21):
            lean = rng.n(0.34)
            d = np.array([math.sin(lean), math.cos(lean), rng.n(0.15)])
            length = rng.u(0.2, 0.44)
            dry = rng.u() < 0.14
            k = 1 + rng.n(0.14)
            tw.blade((rng.n(0.012), 0, 0), d, (rng.n(0.3), 0, 1), length, rng.u(0.009, 0.014), (DRY if dry else GREEN) * k, (DRY * 1.25 if dry else TIP) * k,
                     shape='lance', fold=0.3, curl=rng.u(0.05, 0.4), segs=6, thickness=1.0)
        for i in range(seed_heads):
            # a stalk with a seed head above the blades
            st = curve(rng, (rng.n(0.01), 0, 0), (rng.n(0.14), 1, 0), rng.u(0.36, 0.46), 6, wiggle=0.1)
            tw.stem(st, 0.0012, 0.0007, DRY, sides=3)
            tw.needles(rng, st[4:], 0.012, 0.004, DRY * 1.1, DRY * 1.5, spacing=0.004, lean=24, flat=0.6, thickness=0.8, shape='scale')
        return tw.result()

    return twig


RECIPE = {
    # no stem: the "branches" are stubs at the root that only say which way each bunch leans
    'trunk': dict(height=0.06, vary=0.0, radius=0.01, segs=2, hidden=True, lean=0.0, wiggle=0.0),
    'levels': [
        dict(n=6, span=(0.9, 0.99), angle=lambda f, r: r.u(10, 42), length=lambda f, p, r: 0.03, segs=1, radius_per_m=0.01, rmin=0.001, tip=0.001,
             flex=0.0, min=0.01),
    ],
    'leaf': dict(level=9, tips=[1], mode='fan', face='up', size=0.5, aspect=0.8, roll=30, bend=0.3, card_segs=3, cells=['twig0', 'twig1'], flex=1.0),
    'clump1': 0, 'clump2': 0, 'lod1_twigs': 2, 'lod2_every': 1, 'lod2_grow': 1.1, 'clump_sway': 0.8,
    'inner_dark': 0.75, 'volume_normal': 0.3, 'normal_up': 0.75, 'ground_ao': 0.55,
}

BARK = smooth('#6a6a58', '#4a4a3c', '#8a8a70')

SPECIES = dict(id='kusa', seed=71, variants=3, recipe=RECIPE, twigs={'twig0': bunch(0), 'twig1': bunch(2)}, twig_ao=0.01, alpha_gain=1.5,
               bark_height=BARK[0], bark_colour=BARK[1], impostor=None)

if __name__ == '__main__':
    K.run(SPECIES)
