"""
Bark for the species scripts: each function returns (height_fn, colour_fn) for nature_kit.bark_band. The band's x
runs along the trunk, y around it; heights are 0…1, colours linear.
"""
import numpy as np

import nature_kit as K
from twigs import srgb


def _mix(a, b, t):
    return a + (b - a) * t


def strips(crevice, ridge, grey, moss='#3a4a24', weathered=0.5):
    """long fibrous strips that run along the trunk and peel at their edges (cedar, cypress)"""

    def height(rng, h, w):
        s = K.fft_noise((h, w), 1.25, rng, stretch=(0.07, 5.0))
        fibre = K.fft_noise((h, w), 0.7, rng, stretch=(0.05, 10.0))
        ridged = 1 - np.abs(s) / 2.0
        return np.clip(np.clip(ridged, 0, 1) ** 1.6 * 0.75 + fibre * 0.09 + 0.1, 0, 1)

    def colour(rng, hgt):
        c0, c1, g = srgb(crevice), srgb(ridge), srgb(grey)
        weather = np.clip(K.fft_noise(hgt.shape, 1.8, rng, stretch=(1.0, 3.0)) * 0.5 + 0.3, 0, 1)[..., None]
        c = _mix(c0, c1, hgt[..., None] ** 1.3)
        c = _mix(c, g, weather * weathered * hgt[..., None])
        # a breath of green on the damp side
        m = np.clip(K.fft_noise(hgt.shape, 2.2, rng) - 0.9, 0, 1)[..., None]
        return _mix(c, srgb(moss), m * 0.5)

    return height, colour


def plates(crevice, plate, flake, grey, size=1.0):
    """plates with deep cracks between them, flaking at their faces (pine, spruce: `size` < 1 for small scales)"""

    def height(rng, h, w):
        a = K.fft_noise((h, w), 1.7, rng, stretch=(0.45 / size, 1.5 / size))
        b = K.fft_noise((h, w), 1.7, rng, stretch=(0.45 / size, 1.5 / size))
        # the cracks: where either field crosses zero
        crack = np.minimum(np.abs(a), np.abs(b))
        face = np.clip(crack * 3.2, 0, 1) ** 0.55
        flakes = K.fft_noise((h, w), 1.0, rng, stretch=(0.2, 0.6))
        return np.clip(face * 0.8 + flakes * 0.07 + 0.08, 0, 1)

    def colour(rng, hgt):
        c0, c1, c2, g = srgb(crevice), srgb(plate), srgb(flake), srgb(grey)
        patch = np.clip(K.fft_noise(hgt.shape, 2.0, rng, stretch=(0.6, 1.4)) * 0.5 + 0.5, 0, 1)[..., None]
        c = _mix(c1, c2, patch)
        weather = np.clip(K.fft_noise(hgt.shape, 1.8, rng) * 0.5 + 0.25, 0, 1)[..., None]
        c = _mix(c, g, weather * 0.45)
        return _mix(c0, c, np.clip(hgt[..., None] * 1.25, 0, 1) ** 1.5)

    return height, colour


def smooth(base, dark, lichen, moss='#55633a'):
    """smooth, thin bark with pale blotches of lichen and faint rings (beech)"""

    def height(rng, h, w):
        ripple = K.fft_noise((h, w), 1.6, rng, stretch=(3.0, 0.25))
        fine = K.fft_noise((h, w), 0.8, rng)
        return np.clip(0.6 + ripple * 0.08 + fine * 0.04, 0, 1)

    def colour(rng, hgt):
        b, d, li, m = srgb(base), srgb(dark), srgb(lichen), srgb(moss)
        shade = np.clip(K.fft_noise(hgt.shape, 2.0, rng, stretch=(1.0, 2.0)) * 0.5 + 0.5, 0, 1)[..., None]
        c = _mix(d, b, shade)
        # blotches with sharp edges
        blot = np.clip((K.fft_noise(hgt.shape, 2.4, rng) - 0.35) * 6, 0, 1)[..., None]
        c = _mix(c, li, blot * 0.75)
        green = np.clip((K.fft_noise(hgt.shape, 2.4, rng) - 0.8) * 4, 0, 1)[..., None]
        c = _mix(c, m, green * 0.6)
        return c * (0.8 + 0.2 * np.clip((hgt[..., None] - 0.45) * 4, 0, 1))

    return height, colour


def birch(white='#d6d2c6', black='#1c1917', cream='#b9ae98'):
    """white paper bark with dark lenticels across the trunk and black, cracked patches"""

    def height(rng, h, w):
        # lenticels: short dashes around the trunk (the band's y)
        dash = K.fft_noise((h, w), 1.1, rng, stretch=(9.0, 0.22))
        lent = np.clip((dash - 1.35) * 3.0, 0, 1)
        rough = np.clip((K.fft_noise((h, w), 2.3, rng, stretch=(1.0, 1.6)) - 1.0) * 3.5, 0, 1)
        cracks = np.clip(1 - np.abs(K.fft_noise((h, w), 1.5, rng, stretch=(0.3, 1.2))) * 2.0, 0, 1) * rough
        peel = K.fft_noise((h, w), 1.4, rng, stretch=(4.0, 0.5)) * 0.03
        # 1 = the white paper, lower = a lenticel or the black bark; the black patches stand proud and are cracked
        return np.clip(0.75 + peel - lent * 0.45 - rough * 0.3 - cracks * 0.3, 0, 1)

    def colour(rng, hgt):
        w0, k, c = srgb(white), srgb(black), srgb(cream)
        stain = np.clip(K.fft_noise(hgt.shape, 1.8, rng, stretch=(3.0, 0.6)) * 0.5 + 0.5, 0, 1)[..., None]
        paper = _mix(w0, c, stain * 0.6)
        return _mix(k, paper, np.clip((hgt[..., None] - 0.3) / 0.4, 0, 1) ** 1.5)

    return height, colour
