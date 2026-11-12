"""
Beech (ブナ, Fagus crenata; on the autobahn it stands for Fagus sylvatica): the natural forest above the plantations
and the young trees along the road's edge. A smooth grey trunk blotched with lichen that forks into rising limbs,
a broad rounded crown, leaves in two ranks on zigzag twigs, laid out in level sheets.

    blender --background --factory-startup --python buna.py -- --out <file.glb> [--render <dir>]
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

GREEN, LIGHT, WOOD = srgb('#2f4f1b'), srgb('#4f7527'), srgb('#4b4034')


def leaves(tw, rng, pts, n, size, t0=0.12):
    """leaves in two ranks along a shoot, one at each bend of its zigzag, the last at its tip"""
    for i in range(n):
        t = 1.0 if i == n - 1 else t0 + (1 - t0) * (i + rng.u(0.35, 0.65)) / n
        p, d = along(pts, min(t, 0.999))
        sgn = 1 if i % 2 else -1
        side = np.array([d[1], -d[0], 0]) * sgn
        ang = 0.0 if i == n - 1 else math.radians(52 + rng.n(9))
        ld = d * math.cos(ang) + side * math.sin(ang) + np.array([0, 0, rng.n(0.12)])
        length = size * rng.u(0.8, 1.15) * (0.75 + 0.25 * math.sin(math.pi * min(1, t * 1.1)))
        k = 1 + rng.n(0.12)
        # the face tilted a little, each its own way: not one flat sheet
        nrm = np.array([rng.n(0.22), rng.n(0.22), 1.0])
        tw.blade(p + ld * 0.006, ld, nrm, length, length * 0.58, GREEN * k, LIGHT * k, shape='ovate', fold=rng.u(0.05, 0.3), curl=rng.u(-0.05, 0.25),
                 segs=5, thickness=1.0)


def twig(rng):
    """a spray 0.9 m long: the shoot and its side shoots in one plane, a hundred leaves"""
    tw = Twig()
    main = curve(rng, (0, 0, 0), (rng.n(0.06), 1, 0), 0.9, 12, bend=(rng.n(0.2), 0, 0), wiggle=0.5)
    tw.stem(main, 0.005, 0.0015, WOOD)
    leaves(tw, rng, main, 15, 0.085)
    n = 10
    for i in range(n):
        t = 0.1 + 0.7 * (i + rng.u(0.2, 0.8)) / n
        p, d = along(main, t)
        side = np.array([d[1], -d[0], 0]) * (1 if i % 2 else -1)
        ang = math.radians(50 + rng.n(8))
        length = 0.46 * (1 - 0.55 * t) * rng.u(0.8, 1.15)
        sh = curve(rng, p, d * math.cos(ang) + side * math.sin(ang), length, 7, bend=d * 0.35, wiggle=0.45)
        tw.stem(sh, 0.0028, 0.001, WOOD)
        leaves(tw, rng, sh, max(4, int(length / 0.042)), 0.08)
        # the longer ones fork once more
        if length > 0.28:
            q, e = along(sh, rng.u(0.3, 0.5))
            s2 = np.array([e[1], -e[0], 0]) * (1 if rng.u() < 0.5 else -1)
            sub = curve(rng, q, e * 0.7 + s2 * 0.7, length * 0.5, 5, bend=e * 0.3, wiggle=0.4)
            tw.stem(sub, 0.0018, 0.0008, WOOD)
            leaves(tw, rng, sub, max(3, int(length * 0.5 / 0.042)), 0.075)
    return tw.result()


def crown(f):
    """limb length by its place up the trunk: the lowest reach far out, the top ones are short"""
    return 7.0 - 3.6 * f ** 1.2


RECIPE = {
    'trunk': dict(height=14.5, vary=0.12, radius=0.3, segs=16, sides=12, rep=2.0, taper=0.7, lean=0.05, wiggle=0.03, flare=0.55, flare_h=0.6),
    'levels': [
        # the limbs: steeply up at first, arching outwards
        dict(n=19, span=(0.3, 0.97), angle=lambda f, r: 68 - 36 * f + r.n(7), length=lambda f, p, r: crown(f) * r.u(0.8, 1.15),
             droop=-0.1, droop_by=lambda f: 1, wiggle=0.5, segs=7, radius=0.5, rmin=0.03, tip=0.012, flex=0.35),
        # the branches: all round the limb, held level in sheets
        dict(n=lambda p, r: max(3, int(p.length / 0.3)), span=(0.2, 0.98), angle=lambda f, r: 58 + r.n(10),
             length=lambda f, p, r: min(3.4, p.length * 0.52) * (1 - 0.45 * f) * r.u(0.7, 1.15), droop=0.3, upturn=0.1, wiggle=0.35, segs=4,
             radius_per_m=0.01, rmin=0.004, tip=0.003, flex=0.35, min=0.3),
    ],
    'leaf': dict(level=2, tips=[1], mode='radial', per_m=3.3, size=1.15, aspect=0.8, angle=50, face_up=1.0, face_out=0.55, face_rand=0.45,
                 bend=0.14, start=0.1, cells=['twig0', 'twig1'], tip_scale=1.1, flex=0.3),
    'clump1': 2, 'clump2': 2, 'lod1_twigs': 6, 'lod2_every': 3, 'lod2_grow': 1.9, 'lod1_branch_r': 0.04,
    'inner_dark': 0.3, 'volume_normal': 0.75,
}

BARK = smooth('#7c7970', '#55524b', '#a9a898')

SPECIES = dict(id='buna', seed=31, variants=3, recipe=RECIPE, twigs={'twig0': twig, 'twig1': twig}, twig_ao=0.02, alpha_gain=1.25,
               bark_height=BARK[0], bark_colour=BARK[1], bark_relief=1.2, impostor=(192, 256))

if __name__ == '__main__':
    K.run(SPECIES)
