"""
Stone lantern (春日灯籠, Kasuga style) of grey granite, cut in six pieces as the real ones are and set dry on each
other: a hexagonal ground stone with a turned-down lotus (into the ground), the round shaft with its three bands,
the lotus platform (nakadai), the hexagonal fire box (windows front and back, framed panels on the other four
sides), the roof with its six ridges and curled corner fronds (warabite), the lotus ring and the jewel. It has stood
for a long time: moss on everything that looks up, pale lichen blotches, dark runs under the eaves. 1.6 m above the
ground, origin at the centre of the base on the ground (the ground stone reaches 0.15 m into it); the windows face
+Z / -Z (the hexagon's flats do).

    blender -t 4 --background --factory-startup --python stone_lantern.py -- --out <dir> [--render <dir>]

One baked material (prop_bake).
"""
import math
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import prop_kit as K  # noqa: E402
import prop_bake as PB  # noqa: E402

SEG = 20
CORNERS = [math.radians(30 + 60 * k) for k in range(6)]   # the hexagon's corners: its flats face ±Z


def hexpts(R):
    return [(R * math.sin(a), R * math.cos(a)) for a in CORNERS]


def hexring(R, y, lift=0.0, mid=0.97):
    """12 points: corners (raised by lift) and edge middles (pulled in)"""
    pts = []
    for a in CORNERS:
        pts.append((R * math.sin(a), y + lift, R * math.cos(a)))
        b = a + math.radians(30)
        pts.append((R * mid * 0.866 * math.sin(b), y, R * mid * 0.866 * math.cos(b)))
    return pts


def frond(m, mat, a, d0, h0, r0=0.042, n=9, pts=6):
    """the roof corner's curled frond (warabite): a tapering round bar rolled up outwards, in the corner's upright plane"""
    s, c = math.sin(a), math.cos(a)
    rings = []
    for i in range(n):
        t = i / (n - 1)
        b = math.radians(-50 + 300 * t)          # the roll: from under the eave's tip outwards, up and back in
        r = r0 * (1 - 0.5 * t)
        d, h = d0 + r * math.sin(b), h0 + r0 - r * math.cos(b)
        # the bar's section: in the plane of the roll's radius and the horizontal across the corner
        rd, rh = math.sin(b), -math.cos(b)
        w = 0.017 * (1 - 0.55 * t)
        ring = []
        for k in range(pts):
            q = 2 * math.pi * k / pts
            u, v = w * math.cos(q), w * math.sin(q)
            dd, hh = d + rd * u, h + rh * u
            ring.append((dd * s + v * c, hh, dd * c - v * s))
        rings.append(ring)
    m.loft(mat, rings)


def aged(g, ch):
    """moss on what looks up, crusts of lichen (pale grey-green rounds, a few of them ochre), black runs below edges"""
    nz = g.xyz(g.normal())[2]
    up = g.step(nz, 0.25, 0.85)
    n = g.noise(4.0, 4.0, 0.62, seed=4.0)
    moss = g.mul(up, g.step(n, 0.36, 0.58))
    fine = g.noise(60.0, 2.0, 0.6, seed=6.0)
    green = g.mix(g.rgb('#3f4d24'), g.rgb('#6d7a3a'), fine)
    ch['base'] = g.mix(ch['base'], green, g.mul(moss, 0.9))
    ch['rough'] = g.add(ch['rough'], g.mul(moss, 0.1))
    ch['height'] = g.add(ch['height'], g.mul(g.mul(moss, fine), 0.6))
    cell = g.voronoi(7.0, seed=3.0)[0]
    patch = g.mul(g.step(cell, 0.24, 0.13), g.step(g.noise(3.0, 3.0, 0.6, seed=5.0), 0.46, 0.58))
    ch['base'] = g.mix(ch['base'], g.rgb('#a9ae9c'), g.mul(patch, 0.7))
    ochre = g.mul(g.step(g.voronoi(11.0, seed=9.0)[0], 0.13, 0.07), g.step(g.noise(2.0, 2.0, 0.5, seed=11.0), 0.56, 0.66))
    ch['base'] = g.mix(ch['base'], g.rgb('#a8843a'), g.mul(ochre, 0.7))


def build(out):
    stone = PB.surface('granite', '#7f7d77', roughness=0.9, vary=0.16, mottle=0.65, mottle_scale=70, mottle_colour='#4c4b47', grain=0.9,
                       grain_scale=170, dirt=0.85, streak=0.6, foot=0.7, foot_h=0.14, foot_colour='#4a4d36', moss=0.85, custom=aged)
    dark = PB.surface('dark', '#0b0b0c', roughness=1.0, vary=0.0, dirt=0.0)
    m = K.M('stone_lantern')
    # ground stone (kiso): hexagonal, into the ground, a turned-down lotus on it
    m.stack_rings(stone, hexpts(0.40), [(-0.15, 1.0), (0.085, 1.0), (0.10, 0.965)], cap0=False)
    m.lathe(stone, [(0.335, 0.098), (0.32, 0.125), (0.27, 0.155), (0.19, 0.178), (0.15, 0.19)], seg=SEG, caps=(False, False))
    for k in range(12):   # the lotus petals' ribs
        a = math.radians(30 * k)
        m.cyl(stone, (0.325 * math.sin(a), 0.112, 0.325 * math.cos(a)), (0.17 * math.sin(a), 0.184, 0.17 * math.cos(a)), 0.016, 0.009, seg=6,
              caps=(True, False))
    # shaft (sao): round, a band at the foot, in the middle and at the head
    shaft = [(0.14, 0.185), (0.14, 0.215), (0.104, 0.232), (0.094, 0.26), (0.090, 0.385), (0.098, 0.40), (0.118, 0.412), (0.126, 0.435),
             (0.126, 0.47), (0.118, 0.493), (0.098, 0.505), (0.090, 0.52), (0.088, 0.65), (0.10, 0.672), (0.128, 0.688), (0.128, 0.705)]
    m.lathe(stone, shaft, seg=SEG, caps=(False, False))
    # nakadai: a lotus platform opening upwards, a raised rim
    m.stack_rings(stone, hexpts(0.34), [(0.70, 0.50), (0.728, 0.74), (0.765, 0.95), (0.80, 1.0), (0.835, 1.0), (0.843, 0.975), (0.843, 0.60)],
                  cap0=False)
    for a in CORNERS:   # a rib up each corner of the platform
        m.cyl(stone, (0.175 * math.sin(a), 0.703, 0.175 * math.cos(a)), (0.335 * math.sin(a), 0.80, 0.335 * math.cos(a)), 0.012, 0.02, seg=6)
    # fire box (hibukuro): six thick wall panels between corner posts; windows in the front and the back
    R, t = 0.19, 0.05
    a_out = R * 0.866
    y0, y1 = 0.843, 1.122
    for k in range(6):
        with m.at(K.rot_y(math.radians(60 * k))):
            if k in (0, 3):
                w0, w1, wy0, wy1 = -0.045, 0.045, 0.925, 1.05
                m.box(stone, -R / 2, w0, y0, y1, a_out - t, a_out)
                m.box(stone, w1, R / 2, y0, y1, a_out - t, a_out)
                m.box(stone, w0, w1, y0, wy0, a_out - t, a_out)
                m.box(stone, w0, w1, wy1, y1, a_out - t, a_out)
            else:
                m.box(stone, -R / 2, R / 2, y0, y1, a_out - t, a_out)
                # a framed panel cut into the face
                for bx0, bx1, by0, by1 in ((-0.058, 0.058, 0.90, 0.912), (-0.058, 0.058, 1.058, 1.07), (-0.058, -0.046, 0.912, 1.058),
                                           (0.046, 0.058, 0.912, 1.058)):
                    m.box(stone, bx0, bx1, by0, by1, a_out - 0.002, a_out + 0.006)
    for a in CORNERS:
        m.cyl(stone, (R * 0.985 * math.sin(a), y0, R * 0.985 * math.cos(a)), (R * 0.985 * math.sin(a), y1, R * 0.985 * math.cos(a)), 0.02, seg=8,
              caps=(False, False))
    m.prism(dark, hexpts(R * 0.80), y0, y1 - 0.004, cap0=False, cap1=True)   # the dark inside, seen through the windows
    # roof (kasa): eaves lifted at the six corners, a hollow slope up to the neck, a ridge down each corner
    rings = [hexring(0.40, 1.115, 0.05), hexring(0.40, 1.15, 0.06), hexring(0.30, 1.195, 0.046), hexring(0.205, 1.252, 0.02),
             hexring(0.125, 1.31, 0.0), hexring(0.085, 1.345, 0.0)]
    m.loft(stone, rings, cap1=False)
    for a in CORNERS:
        s, c = math.sin(a), math.cos(a)
        m.tube(stone, [(0.09 * s, 1.343, 0.09 * c), (0.205 * s, 1.276, 0.205 * c), (0.30 * s, 1.244, 0.30 * c), (0.385 * s, 1.214, 0.385 * c)], 0.014,
               seg=6, cap0=False)
        frond(m, stone, a, 0.405, 1.17)
    # lotus ring (ukebana) and the jewel (hoju)
    m.lathe(stone, [(0.085, 1.34), (0.112, 1.362), (0.118, 1.388), (0.07, 1.41), (0.042, 1.416), (0.042, 1.432)], seg=SEG, caps=(False, False))
    m.lathe(stone, [(0.042, 1.43), (0.076, 1.47), (0.082, 1.505), (0.062, 1.555), (0.03, 1.587), (0.0, 1.60)], seg=SEG, caps=(False, False))
    ob = m.build()
    PB.finish([ob], out, 'stone_lantern', size=1024, orm_size=512, normal_size=1024, near=0.06, wide=0.4, edge=0.01, max_len=0.8)
    return [ob]


SPEC = K.Spec('stone_lantern.glb', build, [
    dict(name='main', eye=(-1.8, 1.3, 3.2), target=(0, 0.75, 0), lens=42, size=(540, 720)),
    dict(name='close', eye=(-0.9, 1.45, 1.5), target=(0, 1.0, 0), lens=45),
    dict(name='foot', eye=(1.2, 0.6, 1.2), target=(0, 0.25, 0), lens=42),
])

if __name__ == '__main__':
    K.run(SPEC)
