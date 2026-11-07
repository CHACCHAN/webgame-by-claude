"""
Emergency telephone (Notrufsäule) of a German motorway: an orange column with a rounded hood, the pictogram plate
(handset, "SOS", the arrow) and "NOTRUF" on its front, a dark flap below, on a small concrete plinth.
1.32 m tall, front (+Z) to the road, origin at the centre of the footprint. Texture notruf.png (paint_autobahn.py).

    blender -t 4 --background --factory-startup --python emergency_phone.py -- --out <dir> [--render <dir>]
"""
import math
import os
import subprocess
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import prop_kit as K  # noqa: E402

W, D = 0.36, 0.28      # column width (x) and depth (z)
H = 1.12               # height of the straight part


def painted(out, job):
    d = os.path.join(out, 'tex')
    os.makedirs(d, exist_ok=True)
    subprocess.run([K.host_python(), '-I', os.path.join(HERE, 'paint_autobahn.py'), d, job], check=True)
    return d


def build(out):
    d = painted(out, 'phone')
    tex = K.load_image(os.path.join(d, 'notruf.png'))
    orange = K.material('orange', '#e2671c', roughness=0.45)
    plate = K.material('front', '#ffffff', roughness=0.4, base_image=tex)
    concrete = K.material('plinth', '#8f8c86', roughness=0.9)
    m = K.M('emergency_phone')
    # plinth
    m.box(concrete, -0.32, 0.32, -0.1, 0.14, -0.26, 0.26, bevel=0.02, seg=1)
    # column body with a slightly rounded section
    outline = K.rounded_rect(0, 0, W, D, 0.05, n=3)
    m.prism(orange, outline, 0.14, 0.14 + H)
    # hood: a half cylinder across the top, a little proud of the front
    rings = []
    for k in range(13):
        a = math.pi * k / 12
        rings.append(None)
    sec = [(math.cos(math.pi * k / 12) * (W / 2 + 0.015), 0.14 + H + math.sin(math.pi * k / 12) * 0.16) for k in range(13)]
    front, back = D / 2 + 0.05, -D / 2 - 0.01
    m.loft(orange, [[(x, y, back) for x, y in sec], [(x, y, front) for x, y in sec]])
    # front plate (texture 0..512 x 0..400 px) and the flap below (400..512)
    zf = D / 2 + 0.004
    with m.uvmap(lambda cs: [(0.03, 1 - 0.80), (0.97, 1 - 0.80), (0.97, 1 - 0.0), (0.03, 1 - 0.0)]):
        m.quad(plate, [(-0.15, 0.78, zf), (0.15, 0.78, zf), (0.15, 1.20, zf), (-0.15, 1.20, zf)])
    with m.uvmap(lambda cs: [(0.0, 0.0), (1.0, 0.0), (1.0, 1 - 0.80), (0.0, 1 - 0.80)]):
        m.quad(plate, [(-0.15, 0.30, zf), (0.15, 0.30, zf), (0.15, 0.72, zf), (-0.15, 0.72, zf)])
    # a red reflector on each side
    for side in (-1, 1):
        m.box(K.material('reflector', '#c41a12', roughness=0.25, emit_colour='#c41a12', emit_strength=0.2),
              side * (W / 2) - 0.005, side * (W / 2) + 0.005, 1.0, 1.08, -0.03, 0.03)
    ob = m.build(sharp=40)
    return [ob]


SPEC = K.Spec('emergency_phone.glb', build, [
    dict(name='front', eye=(0.9, 1.1, 2.4), target=(0, 0.75, 0), lens=45, ground=4.0),
])

if __name__ == '__main__':
    K.run(SPEC)
