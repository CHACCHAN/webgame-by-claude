"""
Japanese cedar (杉, Cryptomeria japonica): the tree of the planted mountain forests. A dead-straight trunk with
fibrous red-brown bark, a narrow cone of boughs that sag and turn up at their tips, foliage in dense spiky cords.

    blender --background --factory-startup --python sugi.py -- --out <file.glb> [--render <dir>]
(through `node tools/blender-models.cjs nature sugi`, which adds the textures to the GLB.)
"""
import math
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402

import nature_kit as K  # noqa: E402
from twigs import Twig, along, curve, srgb  # noqa: E402

GREEN, TIP, OLD, WOOD = srgb('#27421d'), srgb('#4f7030'), srgb('#5a4a26'), srgb('#4a3423')


def twig(rng):
    """a spray 0.55 m long: the leader and side shoots, all clothed in short awl needles that point forwards"""
    tw = Twig()
    main = curve(rng, (0, 0, 0), (rng.n(0.05), 1, 0), 0.55, 8, bend=(rng.n(0.15), 0, 0), wiggle=0.15)
    tw.stem(main, 0.0045, 0.0015, WOOD)
    axes = [(main, 1.0)]
    n = 15
    for i in range(n):
        t = 0.08 + 0.84 * (i + rng.u(0.2, 0.8)) / n
        p, d = along(main, t)
        sgn = 1 if i % 2 else -1
        side = np.array([d[1], -d[0], 0]) * sgn
        length = (0.2 * (1 - t) + 0.06) * rng.u(0.8, 1.2)
        ang = math.radians(48 + rng.n(8))
        sh = curve(rng, p, d * math.cos(ang) + side * math.sin(ang) + np.array([0, 0, rng.n(0.25)]), length, 5, bend=d * 0.5, wiggle=0.12)
        tw.stem(sh, 0.002, 0.001, WOOD)
        axes.append((sh, 0.9))
        # the longer shoots fork once more
        for j in range(int(length / 0.045)):
            q, e = along(sh, 0.25 + 0.6 * (j + rng.u()) / max(1, int(length / 0.045)))
            s2 = np.array([e[1], -e[0], 0]) * (1 if j % 2 else -1)
            axes.append((curve(rng, q, e * 0.75 + s2 * 0.6 + np.array([0, 0, rng.n(0.3)]), rng.u(0.035, 0.07), 3, bend=e * 0.4), 0.8))
    for pts, k in axes:
        # the oldest needles, near the base of the spray, go brown
        old = rng.u() < 0.08
        tw.needles(rng, pts, 0.013 * k, 0.0042, OLD if old else GREEN, OLD * 1.3 if old else TIP, spacing=0.0036, lean=38, thickness=0.75)
    return tw.result()


def bark_height(rng, h, w):
    """long fibrous strips that run along the trunk and peel at their edges"""
    strips = K.fft_noise((h, w), 1.25, rng, stretch=(0.07, 5.0))
    fibre = K.fft_noise((h, w), 0.7, rng, stretch=(0.05, 10.0))
    ridged = 1 - np.abs(strips) / 2.0
    hgt = np.clip(ridged, 0, 1) ** 1.6 * 0.75 + fibre * 0.09 + 0.1
    return np.clip(hgt, 0, 1)


def bark_colour(rng, hgt):
    crevice, ridge, grey = srgb('#2a1f18'), srgb('#5b4535'), srgb('#6f665c')
    weather = np.clip(K.fft_noise(hgt.shape, 1.8, rng, stretch=(1.0, 3.0)) * 0.5 + 0.3, 0, 1)[..., None]
    c = crevice + (ridge - crevice) * (hgt[..., None] ** 1.3)
    c = c + (grey - c) * weather * 0.5 * hgt[..., None]
    # a breath of green on the damp side
    moss = np.clip(K.fft_noise(hgt.shape, 2.2, rng) - 0.9, 0, 1)[..., None]
    return c + (srgb('#3a4a24') - c) * moss * 0.5


def crown(f):
    """bough length by its place up the crown (0 = lowest bough … 1 = the tip)"""
    low = 0.72 + 0.28 * min(1.0, f / 0.14)
    return (3.2 * (1 - f) ** 0.72 + 0.3) * low


RECIPE = {
    'trunk': dict(height=17.0, vary=0.1, radius=0.27, segs=20, sides=12, rep=2.0, taper=0.85, lean=0.035, wiggle=0.012, flare=0.5),
    'levels': [
        # the boughs: out and a little down, sagging under their own weight, the tips turned up; steeper near the top
        dict(n=92, span=(0.3, 0.985), angle=lambda f, r: 97 - 44 * f ** 1.6 + r.n(5), length=lambda f, p, r: crown(f) * r.u(0.82, 1.14),
             droop=0.55, droop_by=lambda f: 1 - 0.8 * f, upturn=0.45, wiggle=0.16, segs=6, radius_per_m=0.0125, tip=0.004, flex=0.5),
        # the laterals: left and right in the bough's plane, shorter towards its tip
        dict(n=lambda p, r: max(2, int(p.length / 0.26)), span=(0.14, 0.95), planar=True, angle=lambda f, r: 50 + r.n(7),
             length=lambda f, p, r: p.length * 0.44 * (1 - 0.72 * f) * r.u(0.7, 1.12), droop=0.12, wiggle=0.1, segs=3, radius_per_m=0.008,
             rmin=0.003, tip=0.002, flex=0.3, lift=0.2, min=0.12),
    ],
    'leaf': dict(level=2, tips=[1], mode='fan', per_m=3.6, size=0.8, aspect=0.64, angle=42, roll=42, bend=0.3, start=0.04,
                 cells=['twig0', 'twig1'], tip_scale=1.15, flex=0.25),
    'clump1': 1, 'clump2': 1, 'lod1_twigs': 5, 'lod2_every': 2, 'lod2_grow': 1.5,
    'inner_dark': 0.34, 'volume_normal': 0.72,
}

SPECIES = dict(id='sugi', seed=11, variants=3, recipe=RECIPE, twigs={'twig0': twig, 'twig1': twig}, twig_ao=0.02, alpha_gain=1.6,
               bark_height=bark_height, bark_colour=bark_colour, bark_relief=2.2, impostor=(128, 384))

if __name__ == '__main__':
    K.run(SPECIES)
