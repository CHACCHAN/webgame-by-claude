"""
Textures for the Silvia S15 model (deterministic, PIL on the host; Noto Sans CJK is the only font):
  python3 frontend/tools/blender/cars/s15_textures.py   →  frontend/tools/blender/textures/s15/*.png

- plate.png: a white Japanese number plate with fictional text (朧 300 / さ 12-34);
- taillight.png: the red tail/stop lens (u across the lamp from its inner tip to the outer end, v up); the bright
  parts are what glows at night (the game uses the map as the emissive pattern);
- headlight.png: the headlamp's face (front view): housing, projector, high beam, clear corner; bright = glows.
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
    """u: 0 at the lamp's inner tip → 1 at the outer end; v: 0 bottom → 1 top (only the red part is used)"""
    W, H = 512, 128
    im = Image.new('RGB', (W, H), (70, 4, 6))
    d = ImageDraw.Draw(im)
    # the lit chamber: most of the red band, brighter towards the outer end
    for x in range(W):
        u = x / (W - 1)
        g = 0.55 + 0.45 * min(1.0, max(0.0, (u - 0.18) / 0.5))
        col = (int(150 + 100 * g), int(14 + 22 * g), int(12 + 14 * g))
        d.line([(x, 8), (x, H - 9)], fill=col)
    # horizontal optic ribs
    for y in range(10, H - 8, 6):
        d.line([(0, y), (W, y)], fill=(120, 8, 8))
    # two round lens elements (the S15 lamp's tail/stop optics), with their bright centres
    for cx, r in ((300, 40), (420, 44)):
        for k in range(r, 0, -1):
            t = k / r
            c = (int(255 - 70 * t * t), int(60 - 40 * t), int(40 - 28 * t))
            d.ellipse((cx - k * 1.25, H * 0.48 - k, cx + k * 1.25, H * 0.48 + k), fill=c)
        d.ellipse((cx - r * 1.25, H * 0.48 - r, cx + r * 1.25, H * 0.48 + r), outline=(140, 10, 10), width=3)
    # dark frame along the edges
    d.rectangle((0, 0, W - 1, 6), fill=(40, 2, 4))
    d.rectangle((0, H - 7, W - 1, H - 1), fill=(40, 2, 4))
    im = im.filter(ImageFilter.GaussianBlur(0.8))
    im.save(os.path.join(OUT, 'taillight.png'))


def headlight():
    """the headlamp's face in front view (u = (|x| - 0.30) / 0.525, v = (y - 0.63) / 0.145): chrome housing, the
    projector low beam (inner), the high-beam reflector (outer) and the clear corner; bright = glows at night"""
    W, H = 512, 144
    su, sv = W / 0.525, H / 0.145

    def P(x, y):
        return ((x - 0.30) * su, (1 - (y - 0.63) / 0.145) * H)

    im = Image.new('RGB', (W, H))
    px = im.load()
    for yy in range(H):
        for xx in range(W):
            v = 0.66 + 0.10 * (1 - yy / H) + 0.03 * math.sin(xx * 0.9)
            px[xx, yy] = (int(236 * v), int(234 * v), int(226 * v))
    d = ImageDraw.Draw(im)

    def disc(x, y, r, col):
        cx, cy = P(x, y)
        d.ellipse((cx - r * su, cy - r * sv, cx + r * su, cy + r * sv), fill=col)

    # clear corner: the position lamp's ribbed lens
    for k in range(12):
        x0 = 0.735 + k * 0.008
        a, _ = P(x0, 0.7)
        d.rectangle((a, 0, a + 3, H), fill=(236, 238, 240))
    # projector low beam: dark shroud, chrome ring, bright lens with a highlight
    disc(0.56, 0.680, 0.040, (110, 112, 116))
    disc(0.56, 0.680, 0.035, (196, 198, 202))
    disc(0.56, 0.680, 0.029, (226, 228, 230))
    disc(0.552, 0.688, 0.008, (255, 255, 255))
    # high beam: faceted reflector bowl round a bulb
    cx, cy = P(0.69, 0.700)
    for r in range(int(0.036 * su), 0, -1):
        c = 170 + int(60 * (1 - r / (0.036 * su)) ** 0.5) + (10 if r % 6 < 3 else 0)
        c = min(255, c)
        d.ellipse((cx - r, cy - r * sv / su, cx + r, cy + r * sv / su), fill=(c, c, min(255, c + 4)))
    disc(0.69, 0.700, 0.007, (255, 255, 250))
    # inner tip: a chrome blade
    for k in range(4):
        y0 = 0.655 + k * 0.012
        a = P(0.30, y0); b = P(0.43, y0 + 0.010)
        d.line((a, b), fill=(230, 232, 236), width=2)
    im = im.filter(ImageFilter.GaussianBlur(0.7))
    im.save(os.path.join(OUT, 'headlight.png'))


def main():
    os.makedirs(OUT, exist_ok=True)
    plate()
    taillight()
    headlight()
    print('textures in', OUT)


main()
