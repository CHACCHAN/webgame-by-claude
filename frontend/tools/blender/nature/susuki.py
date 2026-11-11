"""
Pampas grass (ススキ, Miscanthus sinensis) and the tall weeds that go with it: what grows along the guardrails and
at the road's edge where nobody mows. Long arching blades taller than the rail, pale plumes above them.

    blender --background --factory-startup --python susuki.py -- --out <file.glb> [--render <dir>]
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

GREEN, TIP, DRY, PLUME = srgb('#4a6a26'), srgb('#7d9440'), srgb('#a3975c'), srgb('#cdc3a0')


def bunch(plumes):
    def twig(rng):
        tw = Twig()
        for i in range(11):
            lean = rng.n(0.22)
            d = np.array([math.sin(lean), math.cos(lean), rng.n(0.1)])
            dry = rng.u() < 0.2
            k = 1 + rng.n(0.12)
            tw.blade((rng.n(0.02), 0, 0), d, (rng.n(0.3), 0, 1), rng.u(0.6, 1.05), rng.u(0.012, 0.018), (DRY if dry else GREEN) * k,
                     (DRY * 1.2 if dry else TIP) * k, shape='lance', fold=0.35, curl=rng.u(0.1, 0.5), segs=8, thickness=1.0)
        for i in range(plumes):
            st = curve(rng, (rng.n(0.02), 0, 0), (rng.n(0.1), 1, 0), rng.u(1.0, 1.15), 8, bend=(rng.n(0.25), 0, 0), wiggle=0.05)
            tw.stem(st, 0.003, 0.0012, DRY, sides=4)
            # the plume: a dozen drooping fingers from the top of the stalk, each feathered
            for j in range(12):
                p, e = along(st, 0.8 + 0.2 * j / 12)
                side = np.array([e[1], -e[0], 0]) * (1 if j % 2 else -1)
                f = curve(rng, p, e * 0.8 + side * 0.5, rng.u(0.14, 0.24), 5, bend=side * 0.6 - e * 0.5)
                tw.needles(rng, f, 0.012, 0.003, PLUME * 0.9, PLUME * 1.15, spacing=0.0035, lean=22, flat=0.5, thickness=1.0, shape='needle')
        return tw.result()

    return twig


RECIPE = {
    'trunk': dict(height=0.08, vary=0.0, radius=0.01, segs=2, hidden=True, lean=0.0, wiggle=0.0),
    'levels': [
        dict(n=7, span=(0.9, 0.99), angle=lambda f, r: r.u(6, 30), length=lambda f, p, r: 0.04, segs=1, radius_per_m=0.01, rmin=0.001, tip=0.001,
             flex=0.0, min=0.01),
    ],
    'leaf': dict(level=9, tips=[1], mode='fan', face='up', size=1.3, aspect=0.55, roll=35, bend=0.22, card_segs=4, cells=['twig0', 'twig1'], flex=1.0),
    'clump1': 0, 'clump2': 0, 'lod1_twigs': 2, 'lod2_every': 1, 'lod2_grow': 1.1, 'clump_sway': 0.8,
    'inner_dark': 0.7, 'volume_normal': 0.4, 'normal_up': 0.6, 'ground_ao': 0.5,
}

BARK = smooth('#6a6a58', '#4a4a3c', '#8a8a70')

SPECIES = dict(id='susuki', seed=73, variants=3, recipe=RECIPE, twigs={'twig0': bunch(0), 'twig1': bunch(2)}, twig_ao=0.015, alpha_gain=1.5,
               bark_height=BARK[0], bark_colour=BARK[1], impostor=None)

if __name__ == '__main__':
    K.run(SPECIES)
