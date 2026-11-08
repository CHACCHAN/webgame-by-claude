"""
Textures for the RX-7 FD3S model `shiden` (deterministic, PIL on the host; Noto Sans CJK is the only font):
  python3 frontend/tools/blender/cars/shiden_textures.py   →  frontend/tools/blender/textures/shiden/*.png

- plate.png: a white Japanese number plate with fictional text (朧 300 / さ 12-34);
- popup.png: the pop-up lamp's lens (u across from the inboard edge, v up): two reflector cells behind fluted glass;
  bright = what glows when the lamps are on;
- headlight.png: the bumper's clear position lamp (u from the inboard tip outwards, v up): reflector bowl + bulb;
- taillight.png: the smoked rear lamp (u from the inboard end outwards, v up): three round lamps, the middle one
  the indicator (amber behind the smoke); the corner pixel is the plain red the small reflectors use.
"""
import os
import sys

sys.dont_write_bytecode = True
from PIL import Image, ImageDraw, ImageFilter, ImageFont  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'textures', 'shiden')
FONT = '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'


def font(size):
    return ImageFont.truetype(FONT, size, index=0)


def plate():
    W, H = 512, 256
    im = Image.new('RGB', (W, H), (238, 240, 236))
    d = ImageDraw.Draw(im)
    green = (22, 88, 52)
    d.rounded_rectangle((6, 6, W - 7, H - 7), radius=16, outline=green, width=5)
    for x in (118, W - 118):
        d.ellipse((x - 9, 22, x + 9, 40), fill=(168, 170, 166))
    d.text((W / 2, 56), '朧 300', fill=green, font=font(56), anchor='mm')
    d.text((64, 172), 'さ', fill=green, font=font(62), anchor='mm')
    d.text((292, 160), '12-34', fill=green, font=font(128), anchor='mm')
    return im


def radial(im, cx, cy, r, inner, outer, steps=40):
    d = ImageDraw.Draw(im)
    for i in range(steps, 0, -1):
        t = i / steps
        col = tuple(int(outer[k] + (inner[k] - outer[k]) * (1 - t) ** 1.5) for k in range(3))
        d.ellipse((cx - r * t, cy - r * t, cx + r * t, cy + r * t), fill=col)


def popup():
    W, H = 512, 256
    im = Image.new('RGB', (W, H), (60, 62, 66))
    d = ImageDraw.Draw(im)
    # two cells: inboard high beam (smaller), outboard low beam
    for cx, r in ((150, 92), (370, 104)):
        d.rounded_rectangle((cx - r - 16, 20, cx + r + 16, H - 20), radius=26, fill=(118, 122, 128))
        radial(im, cx, H // 2, r, (255, 252, 240), (150, 155, 162))
        d = ImageDraw.Draw(im)
        d.ellipse((cx - 16, H // 2 - 16, cx + 16, H // 2 + 16), fill=(255, 255, 250))
    # flutes in the glass
    for x in range(0, W, 12):
        d.line((x, 0, x, H), fill=(205, 210, 215), width=1)
    im = im.filter(ImageFilter.GaussianBlur(1.2))
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, W - 1, H - 1), outline=(30, 30, 32), width=8)
    return im


def headlight():
    W, H = 512, 128
    im = Image.new('RGB', (W, H), (150, 154, 158))
    d = ImageDraw.Draw(im)
    for x in range(0, W, 10):
        d.line((x, 0, x - 30, H), fill=(178, 182, 186), width=2)
    radial(im, 300, 66, 58, (255, 250, 236), (120, 124, 130))
    d = ImageDraw.Draw(im)
    d.ellipse((288, 54, 312, 78), fill=(255, 255, 248))
    return im.filter(ImageFilter.GaussianBlur(0.8))


def taillight():
    W, H = 512, 128
    red = (110, 8, 8)
    im = Image.new('RGB', (W, H), (22, 9, 10))
    d = ImageDraw.Draw(im)
    # u from the inboard end (x 0.43 → 0.765 across the tail): two red lamps, the amber indicator outboard on the
    # corner (photo s14: centres x 0.49, 0.61, 0.73, about 100 mm across, crisp-edged behind the smoked lens);
    # v: the band's bottom (row 128) to top
    for cx, rx, lens, ring in ((92, 79, (150, 16, 14), (178, 34, 28)), (278, 79, (150, 16, 14), (178, 34, 28)),
                               (448, 56, (196, 104, 28), (222, 136, 52))):
        cy, ry = 70, 50
        d.ellipse((cx - rx - 6, cy - ry - 6, cx + rx + 6, cy + ry + 6), fill=(12, 4, 5))
        d.ellipse((cx - rx - 2, cy - ry - 2, cx + rx + 2, cy + ry + 2), fill=(92, 72, 72))
        d.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=lens)
        # the lens optics: concentric steps, a brighter middle round the bulb
        for k, col in ((0.82, ring), (0.62, lens), (0.45, ring), (0.22, tuple(min(255, c + 40) for c in ring))):
            d.ellipse((cx - rx * k, cy - ry * k, cx + rx * k, cy + ry * k), outline=col, width=3)
        d.ellipse((cx - rx * 0.12, cy - ry * 0.12, cx + rx * 0.12, cy + ry * 0.12), fill=ring)
    im = im.filter(ImageFilter.GaussianBlur(0.6))
    im.putpixel((0, 0), red)
    im.putpixel((0, H - 1), red)
    return im


def main():
    os.makedirs(OUT, exist_ok=True)
    for name, fn in (('plate', plate), ('popup', popup), ('headlight', headlight), ('taillight', taillight)):
        fn().save(os.path.join(OUT, f'{name}.png'), optimize=True)
        print('wrote', name)


if __name__ == '__main__':
    main()
