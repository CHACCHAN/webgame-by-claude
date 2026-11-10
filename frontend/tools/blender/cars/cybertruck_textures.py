"""
Paints the Cybertruck's textures (deterministic, our own drawing; no photo pixels) with PIL:

  python3 tools/blender/cars/cybertruck_textures.py [outdir]      (default tools/blender/textures/cybertruck/)

headlight.png  u < 0.5: the front light bar (a frosted strip, pale blue-white by day, the game lights it at night);
               u > 0.5: a headlamp slit (a row of clear cells in a dark frame)
taillight.png  u < 0.5: the tail light line across the band (u = 0..0.5 spans the line from the left housing to the
               right one; the middle part, the one the photos show lit by day, is brighter); u > 0.5: a corner block
               (upper strip, dark divider, lower block in a dark rim). Smoked, nearly black when unlit as on the
               photos (p120); the game glows through it: CarSpec.tailLampGain ~12 brings the lit lamps up to the photos'
               brightness (p150: the corner blocks and the line's middle lit by day).
tire.png       the all-terrain tyre: sidewall rings, shoulder lugs, three rows of tread blocks (u: one sixteenth of the
               circumference, v: inner bead 0 -> outer bead 1, tread 0.38..0.62 as cybertruck_wheels.tyre)
"""
import os
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from PIL import Image, ImageDraw, ImageFilter  # noqa: E402

import cybertruck_shape as CS  # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(HERE), 'textures', 'cybertruck')
SS = 4


def headlight():
    W, H = 256 * SS, 64 * SS
    img = Image.new('RGB', (W, H), (212, 219, 234))
    d = ImageDraw.Draw(img)
    # light bar: frosted, a touch brighter along its upper edge
    for i in range(H):
        t = i / H
        c = int(226 - 22 * t), int(231 - 18 * t), int(242 - 10 * t)
        d.line([(0, i), (W // 2, i)], fill=c)
    # headlamp slit: dark frame with six clear cells
    x0, x1 = W // 2, W
    d.rectangle([x0, 0, x1, H], fill=(30, 33, 37))
    n = 6
    cw = (x1 - x0) / n
    for k in range(n):
        a = x0 + k * cw + 0.08 * cw
        b = x0 + (k + 1) * cw - 0.08 * cw
        d.rectangle([a, 0.18 * H, b, 0.82 * H], fill=(176, 184, 194))
        d.rectangle([a, 0.18 * H, b, 0.34 * H], fill=(214, 220, 228))
    img.resize((256, 64), Image.LANCZOS).save(os.path.join(OUT, 'headlight.png'))


def taillight():
    P = CS.load()
    W, H = 512 * SS, 64 * SS
    img = Image.new('RGB', (W, H), (12, 4, 4))
    d = ImageDraw.Draw(img)
    # the line: u = 0..0.5 over x = +xl..-xl (left housing to right housing)
    xl = P['sw'] - P['tk_w']
    half = W // 2
    for i in range(half):
        x = xl - 2 * xl * (i + 0.5) / half
        lit = abs(x) <= P['tl_cw']
        d.line([(i, 0), (i, H)], fill=(56, 9, 7) if lit else (30, 6, 5))
    # corner block: dark rim, upper strip, divider, lower block
    x0, x1 = half, W
    d.rectangle([x0, 0, x1, H], fill=(14, 4, 4))
    r = 0.06
    d.rounded_rectangle([x0 + r * (x1 - x0), r * H, x1 - r * (x1 - x0), (0.27) * H], radius=SS * 4, fill=(58, 11, 8))
    d.rounded_rectangle([x0 + r * (x1 - x0), 0.33 * H, x1 - r * (x1 - x0), (1 - r) * H], radius=SS * 4, fill=(62, 12, 9))
    img = img.filter(ImageFilter.GaussianBlur(SS * 0.6))
    img.resize((512, 64), Image.LANCZOS).save(os.path.join(OUT, 'taillight.png'))


def tire():
    W, H = 256 * SS, 512 * SS
    img = Image.new('RGB', (W, H), (33, 33, 34))
    d = ImageDraw.Draw(img)
    v = lambda t: t * H
    # sidewalls: rim protector and raised rings
    for a, b, c in ((0.08, 0.11, (27, 27, 28)), (0.89, 0.92, (27, 27, 28)), (0.20, 0.215, (40, 40, 41)), (0.785, 0.80, (40, 40, 41))):
        d.rectangle([0, v(a), W, v(b)], fill=c)
    # shoulders: chunky lugs stepping onto the sidewall
    for side in (0, 1):
        for k in range(2):
            x = k * W / 2
            if side == 0:
                d.polygon([(x + 0.05 * W, v(0.30)), (x + 0.40 * W, v(0.30)), (x + 0.42 * W, v(0.38)), (x + 0.03 * W, v(0.38))], fill=(44, 44, 45))
                d.rectangle([x + 0.12 * W, v(0.25), x + 0.30 * W, v(0.30)], fill=(40, 40, 41))
            else:
                d.polygon([(x + 0.03 * W, v(0.62)), (x + 0.42 * W, v(0.62)), (x + 0.40 * W, v(0.70)), (x + 0.05 * W, v(0.70))], fill=(44, 44, 45))
                d.rectangle([x + 0.12 * W, v(0.70), x + 0.30 * W, v(0.75)], fill=(40, 40, 41))
    # tread: dark base, three rows of staggered blocks with zig-zag edges
    d.rectangle([0, v(0.38), W, v(0.62)], fill=(14, 14, 15))
    rows = [(0.385, 0.455, 0.0), (0.465, 0.535, 0.25), (0.545, 0.615, 0.0)]
    for a, b, off in rows:
        for k in range(4):
            x = (k + off) * W / 4
            w = W / 4 * 0.78
            pts = [(x, v(a)), (x + w, v(a)), (x + w + 0.03 * W, v((a + b) / 2)), (x + w, v(b)), (x, v(b)), (x + 0.03 * W, v((a + b) / 2))]
            d.polygon(pts, fill=(47, 47, 48))
            # sipes
            for s in (0.33, 0.66):
                d.line([(x + s * w, v(a) + 3 * SS), (x + s * w + 0.02 * W, v(b) - 3 * SS)], fill=(24, 24, 25), width=SS * 2)
    img.resize((256, 512), Image.LANCZOS).save(os.path.join(OUT, 'tire.png'))


def main():
    os.makedirs(OUT, exist_ok=True)
    headlight()
    taillight()
    tire()
    print('textures ->', OUT)


main()
