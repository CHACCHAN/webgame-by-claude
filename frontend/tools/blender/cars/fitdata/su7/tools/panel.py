"""panel.py <image> <out.png> <scale> <step> x0,y0,x1,y1 [x0,y0,x1,y1 ...] [--pts u,v;u,v] [--cols 3]: several crops of a
photo, each enlarged with a labelled pixel grid (lines every <step> px, labels every 2 steps), tiled into one sheet; for
reading feature points off the photos. Optional points drawn as magenta crosses."""
import sys
from PIL import Image, ImageDraw
a = sys.argv[1:]
pts = []
if '--pts' in a:
    i = a.index('--pts'); pts = [tuple(float(t) for t in p.split(',')) for p in a[i + 1].split(';') if p]; a = a[:i] + a[i + 2:]
cols = 3
if '--cols' in a:
    i = a.index('--cols'); cols = int(a[i + 1]); a = a[:i] + a[i + 2:]
src, out, s, step = a[0], a[1], float(a[2]), float(a[3])
boxes = [tuple(int(float(v)) for v in b.split(',')) for b in a[4:]]
img = Image.open(src).convert('RGB')
tiles = []
for (x0, y0, x1, y1) in boxes:
    im = img.crop((x0, y0, x1, y1)).resize((int((x1 - x0) * s), int((y1 - y0) * s)), Image.LANCZOS)
    d = ImageDraw.Draw(im)
    k = 0
    x = (x0 // step + 1) * step
    while x < x1:
        X = (x - x0) * s
        major = round(x / step) % 2 == 0
        d.line([(X, 0), (X, im.size[1])], fill=(255, 255, 0) if major else (120, 120, 0), width=1)
        if major:
            d.text((X + 2, 2), f'{x:g}', fill=(255, 255, 0))
        x += step
    y = (y0 // step + 1) * step
    while y < y1:
        Y = (y - y0) * s
        major = round(y / step) % 2 == 0
        d.line([(0, Y), (im.size[0], Y)], fill=(0, 255, 255) if major else (0, 120, 120), width=1)
        if major:
            d.text((2, Y + 2), f'{y:g}', fill=(0, 255, 255))
        y += step
    for u, v in pts:
        if x0 <= u < x1 and y0 <= v < y1:
            X, Y = (u - x0) * s, (v - y0) * s
            d.line([(X - 5, Y), (X + 5, Y)], fill=(255, 0, 255), width=1); d.line([(X, Y - 5), (X, Y + 5)], fill=(255, 0, 255), width=1)
    tiles.append(im)
rows = [tiles[i:i + cols] for i in range(0, len(tiles), cols)]
W = max(sum(t.size[0] for t in r) + 6 * (len(r) - 1) for r in rows)
H = sum(max(t.size[1] for t in r) for r in rows) + 6 * (len(rows) - 1)
sheet = Image.new('RGB', (W, H), 'white')
y = 0
for r in rows:
    x = 0
    for t in r:
        sheet.paste(t, (x, y)); x += t.size[0] + 6
    y += max(t.size[1] for t in r) + 6
sheet.save(out)
