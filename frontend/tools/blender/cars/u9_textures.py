"""
Textures of the U9 (game id `u9`), drawn with PIL (deterministic; no photo pixels):

  python3 tools/blender/cars/u9_textures.py      -> tools/blender/textures/u9/*.png

- headlamp.png   the smoked lens of the 'Gate of Time' lamps (dark, fine LED rows, a soft inner glow toward the blade);
                 a white block in the top right corner (u9_data.UV_WHITE) for the light line, a light grey one below it
                 for the gate's fins (u9_details.UV_FIN)
- taillamp.png   the full-width tail band: dark red under the cover, ~48 slim vertical bars per half (brighter toward the
                 middle of each bar), a bright line along the lower edge and the emblem gap at the centre
"""
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFilter

sys.dont_write_bytecode = True
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'textures', 'u9')


def headlamp(size=512):
    im = Image.new('RGB', (size, size), (14, 17, 22))
    dr = ImageDraw.Draw(im)
    # a vertical gradient: the lens darkest at the top
    for y in range(size):
        t = y / size
        c = (int(14 + 18 * t), int(17 + 20 * t), int(22 + 24 * t))
        dr.line([(0, y), (size, y)], fill=c)
    # fine LED rows (the inner reflector's segments)
    for k in range(0, size, 12):
        dr.line([(0, k), (size, k - size * 0.35)], fill=(40, 46, 54), width=2)
    for k in range(0, size, 32):
        dr.line([(k, 0), (k, size)], fill=(26, 30, 36), width=1)
    im = im.filter(ImageFilter.GaussianBlur(1.2))
    dr = ImageDraw.Draw(im)
    # the white block for the light lines (UV_WHITE = (0.96, 0.96))
    dr.rectangle([size - 28, 0, size, 28], fill=(255, 255, 255))
    # and a light grey one for the gate's fins (u9_details.UV_FIN = (0.975, 0.875))
    dr.rectangle([size - 28, 50, size, 78], fill=(150, 156, 164))
    return im


def taillamp(w=2048, h=128):
    im = Image.new('RGB', (w, h), (38, 4, 6))
    dr = ImageDraw.Draw(im)
    half = w // 2
    gap = int(w * 0.035)                     # the emblem at the centre
    n = 46
    for side in (0, 1):
        for k in range(n):
            t = (k + 0.5) / n
            x = int(t * (half - gap)) if side == 0 else int(half + gap + t * (half - gap))
            # each bar: brighter in its middle, a slight lean outward like the photos' slats
            for y in range(int(h * 0.12), int(h * 0.84)):
                g = 1 - abs((y / h) - 0.48) / 0.40
                c = (int(120 + 120 * max(0, g)), int(10 + 20 * max(0, g)), int(10 + 14 * max(0, g)))
                dr.line([(x - 3, y), (x + 3, y)], fill=c)
    # the bright line along the lower edge
    dr.rectangle([0, int(h * 0.86), w, int(h * 0.93)], fill=(255, 40, 30))
    dr.rectangle([half - gap, 0, half + gap, h], fill=(20, 20, 22))
    return im.filter(ImageFilter.GaussianBlur(0.8))


def main():
    os.makedirs(OUT, exist_ok=True)
    headlamp().save(os.path.join(OUT, 'headlamp.png'))
    taillamp().save(os.path.join(OUT, 'taillamp.png'))
    print('wrote', OUT)


if __name__ == '__main__':
    main()
