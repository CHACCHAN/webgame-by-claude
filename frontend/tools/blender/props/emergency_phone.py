"""
Emergency telephone (Notrufsäule) of a German motorway: an orange glass-fibre column with a hood that stands out
over the front as a visor, bolted by its foot flange to a concrete plinth (which goes into the ground). On the
front the pictogram plate (handset, "SOS", the arrow, "NOTRUF") and under it the dark speech unit: a flap hinged
at its top with a pull, the loudspeaker's slots, the call button. Red reflectors on both sides, the service door
with its lock at the back. Years of road spray: faded, dirty towards the foot.
1.42 m above the ground, front (+Z) to the road, origin at the centre of the footprint on the ground.
Texture notruf.png (paint_autobahn.py), baked into the one material.

    blender -t 4 --background --factory-startup --python emergency_phone.py -- --out <dir> [--render <dir>]

One baked material (prop_bake).
"""
import math
import os
import subprocess
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import prop_kit as K  # noqa: E402
import prop_bake as PB  # noqa: E402

W, D = 0.36, 0.28      # column width (x) and depth (z)
Y0 = 0.14              # top of the plinth
H = 1.12               # height of the straight part


def painted(out, job):
    d = os.path.join(out, 'tex')
    os.makedirs(d, exist_ok=True)
    subprocess.run([K.host_python(), '-I', os.path.join(HERE, 'paint_autobahn.py'), d, job], check=True)
    return d


def build(out):
    d = painted(out, 'phone')
    tex = K.load_image(os.path.join(d, 'notruf.png'))
    orange = PB.surface('orange', '#e0641a', roughness=0.46, vary=0.1, mottle=0.35, mottle_scale=6, mottle_colour='#e58e56', mottle_rough=0.62,
                        dirt=0.6, streak=0.5, foot=0.75, foot_h=0.5, foot_colour='#4a4338', wear=0.3, wear_colour='#eab08a')
    plate = PB.surface('front', '#ffffff', roughness=0.4, image=tex, vary=0.03, dirt=0.45, streak=0.35)
    dark = PB.surface('dark', '#3a3c3e', roughness=0.55, vary=0.08, dirt=0.5, streak=0.3, dust=0.3, wear=0.35, wear_colour='#8a8c8c')
    steel = PB.surface('steel', '#a3a8a8', metallic=0.75, roughness=0.42, rust=0.3, dirt=0.5)
    concrete = PB.surface('plinth', '#8f8c86', roughness=0.9, vary=0.15, mottle=0.5, mottle_scale=14, grain=0.8, grain_scale=150, dirt=0.7,
                          foot=0.7, foot_h=0.08, moss=0.6)
    red = PB.surface('reflector', '#b3160f', roughness=0.22, vary=0.03, dirt=0.4)
    m = K.M('emergency_phone')
    # plinth, into the ground
    with m.dense(0.7):
        m.box(concrete, -0.32, 0.32, -0.4, Y0, -0.26, 0.26, bevel=0.02, seg=1)
    # the column: a foot flange with its four bolts, the body with a rounded section
    m.prism(orange, K.rounded_rect(0, 0, W + 0.07, D + 0.07, 0.06, n=3), Y0, Y0 + 0.022)
    for sx in (-1, 1):
        for sz in (-1, 1):
            m.bolt(steel, (sx * (W / 2 + 0.008), Y0 + 0.022, sz * (D / 2 + 0.008)), (0, 1, 0), r=0.011, h=0.009, washer=0.016)
    m.prism(orange, K.rounded_rect(0, 0, W, D, 0.05, n=4), Y0 + 0.02, Y0 + H, cap0=False)
    # hood: a half cylinder across the top, standing out over the front
    n = 14
    sec = [(math.cos(math.pi * k / n) * (W / 2 + 0.015), Y0 + H + math.sin(math.pi * k / n) * 0.16) for k in range(n + 1)]
    front, back = D / 2 + 0.06, -D / 2 - 0.012
    m.loft(orange, [[(x, y, back) for x, y in sec], [(x, y, front) for x, y in sec]])
    m.box(orange, -W / 2 - 0.015, W / 2 + 0.015, Y0 + H - 0.03, Y0 + H + 0.004, back, front)   # the hood's rim
    zf = D / 2
    # pictogram plate (the texture's upper 400 of 512 rows), riveted on
    px0, px1, py0, py1 = -0.15, 0.15, 0.935, 1.17
    m.box(steel, px0 - 0.004, px1 + 0.004, py0 - 0.004, py1 + 0.004, zf - 0.002, zf + 0.003)

    def plate_uv(cs):
        return [(0.03 + 0.94 * (c.x - px0) / (px1 - px0), 0.219 + 0.781 * (c.y - py0) / (py1 - py0)) for c in cs]

    with m.dense(2.5), m.uvmap(plate_uv, only=plate):
        m.quad(plate, [(px0, py0, zf + 0.0035), (px1, py0, zf + 0.0035), (px1, py1, zf + 0.0035), (px0, py1, zf + 0.0035)])
    for x in (px0 + 0.012, px1 - 0.012):
        for y in (py0 + 0.012, py1 - 0.012):
            m.cyl(steel, (x, y, zf + 0.0035), (x, y, zf + 0.006), 0.005, 0.003, seg=8, caps=(False, True))
    # the speech unit: frame, the flap hinged at its top, its pull; under it the loudspeaker's slots and the call button
    m.box(dark, -0.145, 0.145, 0.50, 0.90, zf - 0.004, zf + 0.008, bevel=0.004, seg=1)
    m.box(dark, -0.13, 0.13, 0.66, 0.885, zf + 0.008, zf + 0.02, bevel=0.005, seg=1)
    m.cyl(steel, (-0.12, 0.885, zf + 0.016), (0.12, 0.885, zf + 0.016), 0.007, seg=8)
    m.box(steel, -0.06, 0.06, 0.675, 0.70, zf + 0.02, zf + 0.034, bevel=0.004, seg=1)
    for k in range(5):
        m.box(steel, -0.10, 0.02, 0.535 + k * 0.022, 0.545 + k * 0.022, zf + 0.008, zf + 0.011)
    m.cyl(steel, (0.085, 0.58, zf + 0.008), (0.085, 0.58, zf + 0.014), 0.03, seg=14)
    m.cyl(red, (0.085, 0.58, zf + 0.014), (0.085, 0.58, zf + 0.024), 0.022, 0.019, seg=14)
    # a red reflector on each side, in its frame
    for side in (-1, 1):
        x = side * (W / 2)
        m.box(dark, min(x, x + side * 0.004), max(x, x + side * 0.004), 0.98, 1.10, -0.045, 0.045)
        m.box(red, min(x + side * 0.004, x + side * 0.007), max(x + side * 0.004, x + side * 0.007), 0.99, 1.09, -0.035, 0.035)
    # the service door at the back: its frame, hinges, lock
    zb = -D / 2
    m.box(orange, -0.13, 0.13, 0.30, 1.12, zb - 0.008, zb + 0.002, bevel=0.004, seg=1)
    for y in (0.42, 1.0):
        m.cyl(steel, (-0.135, y - 0.03, zb - 0.006), (-0.135, y + 0.03, zb - 0.006), 0.007, seg=8)
    m.cyl(steel, (0.095, 0.72, zb - 0.008), (0.095, 0.72, zb - 0.016), 0.014, seg=10, caps=(False, True))
    ob = m.build(sharp=40)
    PB.finish([ob], out, 'emergency_phone', size=1024, orm_size=512, normal_size=512, near=0.05, wide=0.3, edge=0.008, max_len=0.8)
    return [ob]


SPEC = K.Spec('emergency_phone.glb', build, [
    dict(name='front', eye=(0.9, 1.1, 2.4), target=(0, 0.72, 0), lens=45, ground=4.0, size=(540, 720)),
    dict(name='back', eye=(-1.0, 1.2, -2.0), target=(0, 0.72, 0), lens=45, ground=4.0, size=(540, 720)),
    dict(name='close', eye=(0.35, 0.95, 0.95), target=(0, 0.8, 0.1), lens=45, ground=4.0),
])

if __name__ == '__main__':
    K.run(SPEC)
