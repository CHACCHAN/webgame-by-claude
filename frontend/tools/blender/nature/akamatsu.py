"""
Japanese red pine (赤松, Pinus densiflora): on the ridges and the dry, rocky slopes. A bare, leaning trunk that is
seldom straight, orange-red bark in plates, the crown high up and flat-topped, the long needles in tufts at the ends
of upturned shoots.

    blender --background --factory-startup --python akamatsu.py -- --out <file.glb> [--render <dir>]
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

GREEN, TIP, OLD, WOOD = srgb('#2c4a20'), srgb('#5d7f3a'), srgb('#7a6032'), srgb('#6b4630')


def twig(rng):
    """a shoot 0.6 m long with two whorls of side shoots: bare at the base, each end a brush of needles 9 cm long"""
    tw = Twig()
    main = curve(rng, (0, 0, 0), (rng.n(0.06), 1, 0), 0.6, 10, bend=(rng.n(0.1), 0, 0), wiggle=0.1)
    tw.stem(main, 0.007, 0.003, WOOD)
    axes = [main[6:]]
    for t0, count, reach in ((0.3, 4, 0.34), (0.62, 4, 0.24)):
        p, d = along(main, t0)
        for i in range(count):
            sgn = 1 if i % 2 else -1
            side = np.array([d[1], -d[0], 0]) * sgn
            ang = math.radians(40 + rng.n(8) + (16 if i > 1 else 0))
            sh = curve(rng, p, d * math.cos(ang) + side * math.sin(ang) + np.array([0, 0, rng.n(0.2)]), reach * rng.u(0.8, 1.15), 7, bend=d * 0.55, wiggle=0.1)
            tw.stem(sh, 0.004, 0.0024, WOOD)
            axes.append(sh[3:])
            # a side shoot's own fork
            q, e = along(sh, 0.5)
            s2 = np.array([e[1], -e[0], 0]) * sgn
            fork = curve(rng, q, e * 0.75 + s2 * 0.6, reach * 0.45, 5, bend=e * 0.5)
            tw.stem(fork, 0.003, 0.002, WOOD)
            axes.append(fork[1:])
    for pts in axes:
        old = rng.u() < 0.08
        tw.needles(rng, pts, 0.09, 0.0026, OLD if old else GREEN, OLD * 1.2 if old else TIP, spacing=0.0017, lean=38, thickness=0.7, vary=0.16)
    return tw.result()


RECIPE = {
    'trunk': dict(height=14.5, vary=0.14, radius=0.23, segs=18, sides=11, rep=2.0, taper=0.66, lean=0.14, wiggle=0.075, straighten=0.035,
                  flare=0.35, tip=0.03),
    'levels': [
        # the limbs: only the upper half of the trunk carries any; long ones low, a flat top
        dict(n=22, span=(0.5, 0.99), bias=0.85, angle=lambda f, r: 84 - 34 * f + r.n(8), length=lambda f, p, r: (4.4 - 2.3 * f) * r.u(0.75, 1.15),
             droop=0.12, upturn=0.5, wiggle=0.55, segs=6, radius_per_m=0.017, tip=0.009, flex=0.4),
        # the shoots: turned up towards the light
        dict(n=lambda p, r: max(3, int(p.length / 0.24)), span=(0.25, 0.97), angle=lambda f, r: 55 + r.n(12),
             length=lambda f, p, r: min(1.3, p.length * 0.42) * (1 - 0.35 * f) * r.u(0.7, 1.15), droop=-0.45, wiggle=0.3, segs=3,
             radius_per_m=0.012, rmin=0.005, tip=0.004, flex=0.35, min=0.25),
    ],
    'leaf': dict(level=2, tips=[1], mode='radial', per_m=4.5, size=0.95, aspect=0.9, angle=38, rise=0.35, face_up=1.0, face_out=0.4,
                 face_rand=0.5, bend=0.05, start=0.35, cells=['twig0', 'twig1'], tip_scale=1.2, flex=0.25),
    'clump1': 1, 'clump2': 1, 'lod1_twigs': 4, 'lod2_every': 1, 'lod2_grow': 1.35, 'lod1_branch_r': 0.03,
    'inner_dark': 0.4, 'volume_normal': 0.65,
}

BARK = plates('#2a1a14', '#7a4a31', '#96603d', '#6e6257')

SPECIES = dict(id='akamatsu', seed=47, variants=3, recipe=RECIPE, twigs={'twig0': twig, 'twig1': twig}, twig_ao=0.02, alpha_gain=1.9,
               bark_height=BARK[0], bark_colour=BARK[1], bark_relief=2.4, impostor=(160, 288))

if __name__ == '__main__':
    K.run(SPECIES)
