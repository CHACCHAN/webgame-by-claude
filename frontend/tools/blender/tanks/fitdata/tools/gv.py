"""gv.py <image> <out.png> x0 y0 x1 y1 [scale] [--pts name:u,v;name:u,v...] [--bright k]: a crop with a pixel grid for
reading points off a photo: thin lines every 10 px, labelled lines every 50 px (labels on all four edges, large);
optional named points drawn as magenta crosses (to check annotations)."""
import sys
from PIL import Image, ImageDraw, ImageEnhance, ImageFont
a = sys.argv[1:]
pts = []
if '--pts' in a:
    i = a.index('--pts')
    for p in a[i + 1].split(';'):
        if p:
            n, uv = p.split(':') if ':' in p else ('', p)
            u, v = (float(t) for t in uv.split(','))
            pts.append((n, u, v))
    a = a[:i] + a[i + 2:]
br = 1.0
if '--bright' in a:
    i = a.index('--bright'); br = float(a[i + 1]); a = a[:i] + a[i + 2:]
src, out = a[0], a[1]
x0, y0, x1, y1 = (int(v) for v in a[2:6])
s = float(a[6]) if len(a) > 6 else 2.0
im = Image.open(src).convert('RGB').crop((x0, y0, x1, y1))
if br != 1.0:
    im = ImageEnhance.Brightness(im).enhance(br)
im = im.resize((int((x1 - x0) * s), int((y1 - y0) * s)), Image.LANCZOS)
d = ImageDraw.Draw(im)
f = ImageFont.load_default(size=16)
W, H = im.size
for x in range((x0 // 10 + 1) * 10, x1, 10):
    X = (x - x0) * s
    major = x % 50 == 0
    d.line([(X, 0), (X, H)], fill=(255, 255, 0) if major else (120, 120, 0), width=1)
    if major:
        for yy in (2, H - 20):
            d.rectangle((X + 1, yy, X + 38, yy + 17), fill=(0, 0, 0)); d.text((X + 3, yy), str(x), fill=(255, 255, 0), font=f)
for y in range((y0 // 10 + 1) * 10, y1, 10):
    Y = (y - y0) * s
    major = y % 50 == 0
    d.line([(0, Y), (W, Y)], fill=(0, 255, 255) if major else (0, 110, 110), width=1)
    if major:
        for xx in (2, W - 42):
            d.rectangle((xx, Y + 1, xx + 38, Y + 18), fill=(0, 0, 0)); d.text((xx + 2, Y + 1), str(y), fill=(0, 255, 255), font=f)
for n, u, v in pts:
    X, Y = (u - x0) * s, (v - y0) * s
    d.line([(X - 9, Y), (X + 9, Y)], fill=(255, 0, 255), width=2); d.line([(X, Y - 9), (X, Y + 9)], fill=(255, 0, 255), width=2)
    if n:
        d.text((X + 6, Y - 20), n, fill=(255, 0, 255), font=f)
im.save(out)
