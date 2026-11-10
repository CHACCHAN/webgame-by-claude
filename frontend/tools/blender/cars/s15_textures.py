"""
Textures for the Silvia S15 model (deterministic, PIL on the host; Noto Sans CJK is the only font):
  python3 frontend/tools/blender/cars/s15_textures.py   →  frontend/tools/blender/textures/s15/*.png

- plate.png: a white Japanese number plate with fictional text (朧 300 / さ 12-34);
- taillight.png: the red tail/stop lens (u across the lamp from its inner tip to the outer end, v up); the bright
  parts are what glows at night (the game uses the map as the emissive pattern);
- headlight.png: the headlamp's face (front view): the black housing, high beam, projector, turn lamp; bright = glows.
"""
import math
import os
import sys

sys.dont_write_bytecode = True
from PIL import Image, ImageDraw, ImageFilter, ImageFont  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'textures', 's15')
FONT = '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'


def font(size, index=0):
    try:
        return ImageFont.truetype(FONT, size, index=index)
    except OSError:
        return ImageFont.truetype('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc', size, index=index)


def plate():
    W, H = 512, 256
    im = Image.new('RGB', (W, H), (238, 240, 236))
    d = ImageDraw.Draw(im)
    green = (22, 88, 52)
    d.rounded_rectangle((6, 6, W - 7, H - 7), radius=18, outline=green, width=6)
    # bolt holes
    for x in (120, W - 120):
        d.ellipse((x - 9, 24, x + 9, 42), fill=(170, 172, 168))
    f1 = font(58)
    d.text((W / 2, 52), '朧 300', fill=green, font=f1, anchor='mm')
    f2 = font(60)
    d.text((70, 170), 'さ', fill=green, font=f2, anchor='mm')
    f3 = font(132)
    d.text((290, 168), '12-34', fill=green, font=f3, anchor='mm')
    im.save(os.path.join(OUT, 'plate.png'))


def taillight():
    """u = (|x| - 0.33) / 0.50 across the lamp from its inner tip to the outer end, v = (y - 0.725) / 0.17 up (only the
    red part below the divider uses it, v < 0.5): the plain lit chamber towards the outer end, the grid of rounded
    cells over the inner half (beside the reverse lamp), fine horizontal ribs"""
    W, H = 512, 256

    def P(x, y):
        return ((x - 0.33) / 0.50 * W, (1 - (y - 0.725) / 0.17) * H)

    im = Image.new('RGB', (W, H), (60, 3, 5))
    d = ImageDraw.Draw(im)
    for xx in range(W):
        x = 0.33 + xx / W * 0.50
        g = 0.55 + 0.45 * min(1.0, max(0.0, (x - 0.70) / 0.07))
        col = (int(150 + 95 * g), int(12 + 20 * g), int(12 + 12 * g))
        d.line([(xx, 0), (xx, H)], fill=col)
    for y in [0.725 + k * 0.006 for k in range(16)]:
        a_, b_ = P(0.33, y)
        d.line([(0, b_), (W, b_)], fill=(132, 8, 9))
    # the cell grid: 3 rows between y 0.737 and 0.800, columns from x 0.490 to 0.700
    # (r48: six columns of rounded cells over half the lens, from the reverse lamp out to the plain outer chamber)
    nx, ny = 6, 3
    x0, x1, y0, y1 = 0.490, 0.700, 0.737, 0.800
    cw, ch = (x1 - x0) / nx, (y1 - y0) / ny
    for i in range(nx):
        for j in range(ny):
            a = P(x0 + i * cw + 0.0015, y0 + (j + 1) * ch - 0.0015)
            b = P(x0 + (i + 1) * cw - 0.0015, y0 + j * ch + 0.0015)
            # r48 / r10 (lamp review 2026-11-10): rounded dark-red cells on a lighter, pinkish grid, each with a lit rim
            d.rectangle((a[0], a[1], b[0], b[1]), fill=(214, 70, 76))
            a = P(x0 + i * cw + 0.003, y0 + (j + 1) * ch - 0.003)
            b = P(x0 + (i + 1) * cw - 0.003, y0 + j * ch + 0.003)
            d.rounded_rectangle((a[0], a[1], b[0], b[1]), radius=9, fill=(136, 10, 16))
            c = P(x0 + (i + 0.5) * cw, y0 + (j + 0.62) * ch)
            d.ellipse((c[0] - 7, c[1] - 4, c[0] + 7, c[1] + 4), fill=(196, 30, 34))
    im = im.filter(ImageFilter.GaussianBlur(0.8))
    im.save(os.path.join(OUT, 'taillight.png'))


def headlight():
    """the headlamp's face in front view (u = (|x| - 0.33) / 0.46, v = (y - 0.580) / 0.125): the spec-R's black inner
    housing, the high-beam reflector (inner), the projector low beam in its chrome ring (middle), the turn lamp's bowl
    with its amber bulb (outer end); bright = glows at night"""
    W, H = 512, 128
    su, sv = W / 0.46, H / 0.125

    def P(x, y):
        return ((x - 0.33) * su, (1 - (y - 0.580) / 0.125) * H)

    im = Image.new('RGB', (W, H))
    px = im.load()
    for yy in range(H):
        for xx in range(W):
            v = 0.19 + 0.06 * (1 - yy / H) + 0.015 * math.sin(xx * 0.9)
            px[xx, yy] = (int(255 * v), int(255 * v), int(258 * v))
    d = ImageDraw.Draw(im)

    def disc(x, y, r, col, outline=None):
        cx, cy = P(x, y)
        d.ellipse((cx - r * su, cy - r * sv, cx + r * su, cy + r * sv), fill=col, outline=outline, width=2)

    def bowl(x, y, rx, ry, lo, hi):
        cx, cy = P(x, y)
        R = int(rx * su)
        for r in range(R, 0, -1):
            c = lo + int((hi - lo) * (1 - r / R) ** 0.6) + (10 if r % 6 < 3 else 0)
            d.ellipse((cx - r, cy - r * ry / rx * sv / su, cx + r, cy + r * ry / rx * sv / su), fill=(c, c, min(255, c + 4)))
        d.ellipse((cx - R, cy - R * ry / rx * sv / su, cx + R, cy + R * ry / rx * sv / su), outline=(104, 106, 110), width=2)

    # high beam: a long dark-chrome reflector round a bright bulb
    bowl(0.428, 0.634, 0.060, 0.030, 46, 92)
    disc(0.428, 0.634, 0.006, (190, 190, 186))
    # projector low beam: chrome ring, the lens, its highlight
    # (lamp review 2026-11-10: on the photos the projector reads as a dim ring round a dark lens behind the smoked
    # cover, not a bright chrome ring)
    disc(0.559, 0.629, 0.036, (122, 124, 128))
    disc(0.559, 0.629, 0.031, (52, 54, 58))
    disc(0.559, 0.629, 0.026, (88, 92, 98))
    disc(0.552, 0.636, 0.005, (200, 202, 206))
    # turn lamp at the outer end: a chrome bowl, the amber bulb
    bowl(0.689, 0.640, 0.032, 0.030, 48, 96)
    disc(0.689, 0.640, 0.006, (176, 106, 34))
    # chrome blades across the blunt inner end
    for k in range(2):
        y0 = 0.612 + k * 0.016
        a = P(0.35, y0); b = P(0.37, y0 + 0.004)
        d.line((a, b), fill=(150, 152, 156), width=2)
    im = im.filter(ImageFilter.GaussianBlur(0.7))
    im.save(os.path.join(OUT, 'headlight.png'))


def main():
    os.makedirs(OUT, exist_ok=True)
    plate()
    taillight()
    headlight()
    print('textures in', OUT)


main()
