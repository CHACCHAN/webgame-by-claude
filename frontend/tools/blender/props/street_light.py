"""
Street light (Japanese mountain-road lamp): tapered steel pole, a curved arm along -X, a cobra-head luminaire whose
downward lens glows through an emissive map (white = lit, black = frame). ~7.6 m tall, origin at the foot of the pole.

    blender -t 4 --background --factory-startup --python street_light.py -- --out <dir> [--render <dir>]

Emission: the lens material's Emission Color is an image texture (lens_emit.png, written next to the GLB), Emission
Strength 1; the exporter writes it as emissiveTexture + emissiveFactor [1, 1, 1], which the game tints per lamp colour.
"""
import math
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402

import prop_kit as K  # noqa: E402

CX = -2.35          # centre of the luminaire along x
LENS_W, LENS_D = 0.98, 0.30


def lens_texture(path, n=128):
    """white where it glows (the refractor), black at the frame rim; faint prism stripes along the length"""
    # uv (0..1) → metres across the lens, then the signed distance to its rounded-rectangle outline
    u = (np.arange(n) + 0.5) / n
    uu, vv = np.meshgrid(u, u)
    x = (uu - 0.5) * LENS_W
    z = (vv - 0.5) * LENS_D
    r = 0.12
    qx, qz = np.abs(x) - (LENS_W / 2 - r), np.abs(z) - (LENS_D / 2 - r)
    sd = np.hypot(np.maximum(qx, 0), np.maximum(qz, 0)) + np.minimum(np.maximum(qx, qz), 0) - r  # < 0 inside
    inside = np.clip(-sd / 0.012, 0, 1)                      # 1 inside, falls to 0 over the last 12 mm
    stripes = 0.88 + 0.12 * np.cos(uu * 2 * np.pi * 26) ** 2  # prisms
    centre = 0.82 + 0.18 * np.clip(1 - (np.hypot(x / (LENS_W / 2), z / (LENS_D / 2))), 0, 1)
    g = inside * stripes * centre
    return np.dstack([g, g, g, np.ones_like(g)])


def build(out):
    tex = os.path.join(out, 'tex')
    os.makedirs(tex, exist_ok=True)
    emit = K.save_image('lens_emit', lens_texture(None), os.path.join(tex, 'lens_emit.png'))
    pole_m = K.material('pole', '#8d9396', metallic=0.35, roughness=0.5)
    housing_m = K.material('housing', '#6f7679', metallic=0.3, roughness=0.45)
    lens_m = K.material('lens', '#d9d9d2', roughness=0.15, emit_image=emit, emit_strength=1.0)

    m = K.M('street_light')
    # --- foundation, base cover, pole
    m.cyl(pole_m, (0, 0, 0), (0, 0.04, 0), 0.19, seg=12)
    m.lathe(pole_m, [(0.14, 0.04), (0.135, 0.12), (0.11, 0.30), (0.10, 0.34)], seg=12)
    prof = [(0.094, 0.34), (0.088, 2.0), (0.074, 3.7), (0.081, 3.72), (0.081, 3.80), (0.072, 3.82),
            (0.066, 5.6), (0.060, 6.9), (0.064, 6.93), (0.064, 7.0), (0.05, 7.04)]
    m.lathe(pole_m, prof, seg=12)
    # hand-hole door, a plate with a bevel on the front of the pole's foot
    m.box(housing_m, -0.055, 0.055, 0.55, 1.05, 0.086, 0.104, bevel=0.006, seg=1)
    m.box(pole_m, -0.012, 0.012, 0.78, 0.84, 0.104, 0.112)
    # --- arm: up out of the pole and over, then nearly level to the luminaire
    path = K.bezier((0, 6.85, 0), (0, 7.30, 0), (-0.32, 7.50, 0), (-0.95, 7.52, 0), 10)
    path += [(-1.25, 7.52, 0), (-1.55, 7.51, 0), (-1.95, 7.50, 0)]
    m.tube(pole_m, path, 0.043, seg=10, scales=[1.0] * 10 + [0.95, 0.9, 0.85, 0.85])
    m.cyl(pole_m, (0, 6.80, 0), (0, 7.02, 0), 0.075, seg=12)       # clamp where the arm leaves the pole
    m.cyl(housing_m, (-1.62, 7.50, 0), (-1.86, 7.50, 0), 0.06, seg=10)  # collar at the luminaire
    # --- luminaire (cobra head): a domed shell, the lens recessed under it
    outline = K.rounded_rect(CX, 0, 1.20, 0.40, 0.19, n=5)
    m.stack_rings(housing_m, outline, [(7.22, 1.0), (7.28, 1.0), (7.36, 0.975), (7.44, 0.90), (7.50, 0.75), (7.53, 0.56)])
    lens_outline = K.rounded_rect(CX, 0, LENS_W, LENS_D, 0.12, n=4)
    m.stack_rings(lens_m, lens_outline, [(7.185, 0.93), (7.205, 1.0), (7.24, 1.0)])
    m.uv(lens_m, lambda p, n: ((p.x - CX) / LENS_W + 0.5, (p.z) / LENS_D + 0.5))
    ob = m.build()
    return [ob]


SPEC = K.Spec('street_light.glb', build, [
    dict(name='main', eye=(-2.5, 3.9, 11.0), target=(-1.0, 3.8, 0), lens=35, size=(540, 720)),
    dict(name='close', eye=(-5.6, 4.6, 3.6), target=(-1.8, 7.3, 0), lens=45),
    dict(name='under', eye=(-2.3, 3.0, 4.2), target=(-2.3, 7.3, 0), lens=45),
    dict(name='night', eye=(-5.6, 4.6, 3.6), target=(-1.8, 7.0, 0), lens=45, night=True),
])

if __name__ == '__main__':
    K.run(SPEC)
