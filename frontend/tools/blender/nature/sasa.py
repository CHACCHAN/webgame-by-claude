"""
Bamboo grass (笹, Sasa veitchii, kumazasa): knee-high thickets on the slopes and under the trees. Thin canes, each
with a hand of broad leaves at its top; the leaves' edges dry to a pale margin.

    blender --background --factory-startup --python sasa.py -- --out <file.glb> [--render <dir>]
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

GREEN, TIP, MARGIN, CANE = srgb('#2f531d'), srgb('#4d7a2a'), srgb('#bdb78c'), srgb('#6a7036')


def hand(rng):
    """the top of a cane: leaves 20 cm long spread like the fingers of a hand, two more lower down"""
    tw = Twig()
    main = curve(rng, (0, 0, 0), (rng.n(0.05), 1, 0), 0.2, 5, wiggle=0.1)
    tw.stem(main, 0.0025, 0.0018, CANE, sides=4)
    spots = [(1.0, a) for a in (-70, -38, -8, 22, 52, 80)] + [(0.45, -60), (0.6, 64)]
    for t, a in spots:
        p, d = along(main, min(t, 0.999))
        ang = math.radians(a + rng.n(8))
        ld = d * math.cos(ang) + np.array([d[1], -d[0], 0]) * math.sin(ang) + np.array([0, 0, rng.n(0.1)])
        length = rng.u(0.17, 0.23)
        k = 1 + rng.n(0.1)
        nrm = np.array([rng.n(0.15), rng.n(0.15), 1.0])
        # the pale margin: the same leaf a little bigger, just behind
        tw.blade(p - np.array([0, 0, 0.002]), ld, nrm, length * 1.04, length * 0.3, MARGIN * k, MARGIN * k, shape='lance', fold=0.12, curl=0.2, segs=6, thickness=1.0)
        tw.blade(p, ld, nrm, length, length * 0.24, GREEN * k, TIP * k, shape='lance', fold=0.12, curl=0.2, segs=6, thickness=1.0)
    return tw.result()


RECIPE = {
    'trunk': dict(height=0.06, vary=0.0, radius=0.01, segs=2, hidden=True, lean=0.0, wiggle=0.0),
    'levels': [
        # the canes
        dict(n=12, span=(0.9, 0.99), angle=lambda f, r: r.u(4, 38), length=lambda f, p, r: r.u(0.35, 0.8), droop=0.25, wiggle=0.2, segs=3,
             radius_per_m=0.006, rmin=0.003, tip=0.002, flex=0.7, min=0.1),
    ],
    'leaf': dict(level=1, mode='radial', per_m=3.0, size=0.42, aspect=0.95, angle=55, rise=0.2, face_up=1.0, face_out=0.5, face_rand=0.5, bend=0.25,
                 start=0.45, cells=['twig0', 'twig1'], tip_scale=1.1, flex=0.3),
    'twig_r': 0.002,
    'clump1': 0, 'clump2': 0, 'lod1_twigs': 3, 'lod2_every': 1, 'lod2_grow': 1.1, 'clump_sway': 0.6,
    'inner_dark': 0.55, 'volume_normal': 0.5, 'normal_up': 0.4, 'ground_ao': 0.4,
}

BARK = smooth('#7a8048', '#5a6034', '#9a9a70')

SPECIES = dict(id='sasa', seed=83, variants=3, recipe=RECIPE, twigs={'twig0': hand, 'twig1': hand}, twig_ao=0.01, alpha_gain=1.3,
               bark_height=BARK[0], bark_colour=BARK[1], impostor=None)

if __name__ == '__main__':
    K.run(SPECIES)
