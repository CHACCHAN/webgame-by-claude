"""grid.py <img> <x0,y0,x1,y1> <out.png> [step] [scale] [pts.json key] : crop with a labelled pixel grid (original coords) to read
points by eye; optional overlay of points (list of [u,v]) or ellipses from a json"""
import sys, json
from PIL import Image, ImageDraw, ImageFont
im = Image.open(sys.argv[1]).convert('RGB')
x0, y0, x1, y1 = [int(float(v)) for v in sys.argv[2].split(',')]
step = int(sys.argv[4]) if len(sys.argv) > 4 else 20
sc = float(sys.argv[5]) if len(sys.argv) > 5 else 2.0
c = im.crop((x0, y0, x1, y1)).resize((int((x1 - x0) * sc), int((y1 - y0) * sc)), Image.LANCZOS)
d = ImageDraw.Draw(c)
f = ImageFont.load_default(size=11)
for x in range((x0 // step + 1) * step, x1, step):
    X = (x - x0) * sc
    d.line((X, 0, X, c.size[1]), fill=(0, 255, 255) if x % (5 * step) == 0 else (0, 120, 120), width=1)
    if x % (5 * step) == 0: d.text((X + 2, 2), str(x), fill=(255, 255, 0), font=f)
for y in range((y0 // step + 1) * step, y1, step):
    Y = (y - y0) * sc
    d.line((0, Y, c.size[0], Y), fill=(0, 255, 255) if y % (5 * step) == 0 else (0, 120, 120), width=1)
    if y % (5 * step) == 0: d.text((2, Y + 2), str(y), fill=(255, 255, 0), font=f)
if len(sys.argv) > 6:
    P = json.load(open(sys.argv[6]))
    for k in sys.argv[7:]:
        v = P[k]
        pts = v['pts'] if isinstance(v, dict) else v
        for u, w in pts:
            X, Y = (u - x0) * sc, (w - y0) * sc
            d.ellipse((X - 3, Y - 3, X + 3, Y + 3), outline=(255, 0, 255), width=2)
c.save(sys.argv[3])
print(c.size)
