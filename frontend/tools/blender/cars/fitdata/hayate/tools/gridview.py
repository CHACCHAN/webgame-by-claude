"""gridview.py <image> <out.png> x0 y0 x1 y1 [scale] [step] [--pts u,v;u,v...] : a crop with a labelled pixel grid (for reading
rim, plate and feature points off a photo); optional points drawn as magenta crosses"""
import sys
from PIL import Image, ImageDraw
a = sys.argv[1:]
pts = []
if '--pts' in a:
    i = a.index('--pts'); pts = [tuple(float(t) for t in p.split(',')) for p in a[i + 1].split(';') if p]; a = a[:i] + a[i + 2:]
src, out = a[0], a[1]
x0, y0, x1, y1 = (int(v) for v in a[2:6])
s = float(a[6]) if len(a) > 6 else 2.0
step = int(a[7]) if len(a) > 7 else 20
im = Image.open(src).convert('RGB').crop((x0, y0, x1, y1))
im = im.resize((int((x1 - x0) * s), int((y1 - y0) * s)), Image.LANCZOS)
d = ImageDraw.Draw(im)
for x in range((x0 // step + 1) * step, x1, step):
    X = (x - x0) * s
    d.line([(X, 0), (X, im.size[1])], fill=(255, 255, 0) if x % (5 * step) == 0 else (90, 90, 0), width=1)
    if x % (5 * step) == 0 or step >= 20:
        d.text((X + 2, 2), str(x), fill=(255, 255, 0))
for y in range((y0 // step + 1) * step, y1, step):
    Y = (y - y0) * s
    d.line([(0, Y), (im.size[0], Y)], fill=(0, 255, 255) if y % (5 * step) == 0 else (0, 90, 90), width=1)
    if y % (5 * step) == 0 or step >= 20:
        d.text((2, Y + 2), str(y), fill=(0, 255, 255))
for u, v in pts:
    X, Y = (u - x0) * s, (v - y0) * s
    d.line([(X - 6, Y), (X + 6, Y)], fill=(255, 0, 255), width=2); d.line([(X, Y - 6), (X, Y + 6)], fill=(255, 0, 255), width=2)
im.save(out)
