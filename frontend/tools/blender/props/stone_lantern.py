"""
Stone lantern (春日灯籠, Kasuga style) in grey granite: stepped base, shaft with a knop, lotus platform (nakadai),
hexagonal fire box with two windows (front and back), hexagonal roof with upturned corners, lotus ring and jewel
finial. 1.6 m tall, origin at the centre of the base, the windows face +Z / -Z.

    blender -t 4 --background --factory-startup --python stone_lantern.py -- --out <dir> [--render <dir>]
Texture: granite.png (numpy, tileable), written next to the GLB, mapped with a triplanar projection.
"""
import math
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402

import prop_kit as K  # noqa: E402


def granite(path, n=256, seed=7):
    """tileable grey granite: blotches from filtered noise (FFT, so it wraps) plus a speckle of dark and light grains"""
    rng = np.random.default_rng(seed)
    f = np.fft.fftfreq(n)[:, None] ** 2 + np.fft.fftfreq(n)[None, :] ** 2
    f[0, 0] = 1
    def field(alpha, s):
        a = np.fft.ifft2(np.fft.fft2(rng.standard_normal((n, n))) / (f ** (alpha / 2))).real
        a = a - a.mean()
        return a / (a.std() + 1e-9) * s
    v = 0.47 + field(1.4, 0.03) + field(0.5, 0.015)
    grain = rng.random((n, n))
    # grains 2 px wide
    g2 = np.repeat(np.repeat(rng.random((n // 2, n // 2)), 2, 0), 2, 1)
    v = np.where(g2 < 0.05, v - 0.14, v)
    v = np.where(g2 > 0.96, v + 0.12, v)
    v = v + (grain - 0.5) * 0.04
    r = v * 1.0
    g = v * 0.995
    b = v * 0.975
    img = np.dstack([np.clip(r, 0, 1), np.clip(g, 0, 1), np.clip(b, 0, 1), np.ones_like(v)])
    return K.save_image('granite', img, path)


def hexpts(R, rot=0.0):
    return [(R * math.sin(math.radians(60 * k) + rot), R * math.cos(math.radians(60 * k) + rot)) for k in range(6)]


def hexring(R, y, lift=0.0, mid=0.97):
    """12 points: corners (raised by lift) and edge middles (pulled in)"""
    pts = []
    for k in range(6):
        a = math.radians(60 * k)
        pts.append((R * math.sin(a), y + lift, R * math.cos(a)))
        b = math.radians(60 * k + 30)
        pts.append((R * mid * 0.866 * math.sin(b), y, R * mid * 0.866 * math.cos(b)))
    return pts


def build(out):
    tex = os.path.join(out, 'tex')
    os.makedirs(tex, exist_ok=True)
    img = granite(os.path.join(tex, 'granite.png'))
    stone = K.material('granite', '#ffffff', roughness=0.88, base_image=img)
    dark = K.material('dark', '#17171a', roughness=0.9)
    m = K.M('stone_lantern')
    hx = lambda R: [(x, z) for x, z in hexpts(R)]
    # base: two steps (kidan), the lower wide
    m.stack_rings(stone, hx(0.38), [(0.0, 1.0), (0.10, 0.97), (0.11, 0.80), (0.19, 0.76)])
    # shaft: round, with a knop (setsu) in the middle and a collar at each end
    shaft = [(0.14, 0.19), (0.14, 0.215), (0.095, 0.235), (0.088, 0.36), (0.10, 0.385), (0.145, 0.42), (0.162, 0.455), (0.145, 0.49),
             (0.10, 0.525), (0.088, 0.55), (0.088, 0.66), (0.125, 0.685), (0.125, 0.70)]
    m.lathe(stone, shaft, seg=16)
    # nakadai: a lotus platform, wide and low, with a raised rim
    m.stack_rings(stone, hx(0.34), [(0.70, 0.52), (0.735, 0.78), (0.775, 0.97), (0.805, 1.0), (0.83, 1.0), (0.83, 0.95), (0.845, 0.95)])
    # fire box: six wall panels (thick), windows in the front and back panels
    a_out, t = 0.19 * 0.866, 0.05
    y0, y1 = 0.845, 1.12
    R = 0.19
    for k in range(6):
        with m.at(K.rot_y(math.radians(60 * k))):
            if k in (0, 3):
                w0, w1, wy0, wy1 = -0.04, 0.04, 0.935, 1.045
                m.box(stone, -R / 2, w0, y0, y1, a_out - t, a_out, bevel=0.004, seg=1)
                m.box(stone, w1, R / 2, y0, y1, a_out - t, a_out, bevel=0.004, seg=1)
                m.box(stone, w0, w1, y0, wy0, a_out - t, a_out, bevel=0.004, seg=1)
                m.box(stone, w0, w1, wy1, y1, a_out - t, a_out, bevel=0.004, seg=1)
            else:
                m.box(stone, -R / 2, R / 2, y0, y1, a_out - t, a_out, bevel=0.004, seg=1)
    m.prism(dark, hexpts(0.19 * 0.80), y0, y1 - 0.004, cap0=False, cap1=True)   # the dark inside, seen through the windows
    # roof: eaves lifted at the six corners, a concave slope up to the knob
    rings = [hexring(0.40, 1.115, 0.05), hexring(0.40, 1.145, 0.058), hexring(0.30, 1.19, 0.045), hexring(0.205, 1.25, 0.02),
             hexring(0.125, 1.31, 0.0), hexring(0.085, 1.345, 0.0)]
    m.loft(stone, rings)
    for k in range(6):
        a = math.radians(60 * k)
        m.cyl(stone, (0.395 * math.sin(a), 1.19, 0.395 * math.cos(a)), (0.435 * math.sin(a), 1.235, 0.435 * math.cos(a)), 0.02, 0.011, seg=6)
    # lotus ring (uke-bana) and the jewel (hoju)
    m.lathe(stone, [(0.085, 1.34), (0.11, 1.36), (0.115, 1.385), (0.07, 1.41), (0.04, 1.415), (0.04, 1.43)], seg=14)
    m.lathe(stone, [(0.04, 1.43), (0.075, 1.47), (0.08, 1.505), (0.06, 1.555), (0.03, 1.585), (0.0, 1.60)], seg=14)
    m.uv_box(stone, 1.7)
    return [m.build()]


SPEC = K.Spec('stone_lantern.glb', build, [
    dict(name='main', eye=(-1.8, 1.3, 3.2), target=(0, 0.75, 0), lens=42, size=(540, 720)),
    dict(name='close', eye=(-0.9, 1.45, 1.5), target=(0, 1.0, 0), lens=45),
    dict(name='side', eye=(3.0, 1.0, 1.6), target=(0, 0.8, 0), lens=42),
])

if __name__ == '__main__':
    K.run(SPEC)
