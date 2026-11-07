"""tiles.py <img> <out.png> label:x,y ... [--r 40] [--s 4] [--cols 4]: zoomed tiles round approximate points, with a
grid in image px (lines every 5 px, labels every 10), so a feature's pixel position can be read to ~1 px"""
import sys
from PIL import Image, ImageDraw

args = sys.argv[1:]
R, SC, COLS = 40, 4, 4
for k, v in (('--r', 'R'), ('--s', 'SC'), ('--cols', 'COLS')):
    if k in args:
        i = args.index(k)
        globals()[v] = int(args[i + 1])
        del args[i:i + 2]
im = Image.open(args[0]).convert('RGB')
pts = []
for a in args[2:]:
    lab, xy = a.split(':')
    x, y = (int(float(t)) for t in xy.split(','))
    pts.append((lab, x, y))
T = 2 * R * SC
rows = (len(pts) + COLS - 1) // COLS
sheet = Image.new('RGB', (COLS * (T + 6), rows * (T + 22)), 'black')
for n, (lab, x, y) in enumerate(pts):
    box = (x - R, y - R, x + R, y + R)
    c = im.crop(box).resize((T, T), Image.NEAREST)
    d = ImageDraw.Draw(c)
    for g in range((box[0] // 5) * 5, box[2] + 1, 5):
        X = (g - box[0]) * SC + SC // 2
        col = (255, 255, 0) if g % 10 == 0 else (0, 160, 160)
        d.line([(X, 0), (X, T)], fill=col, width=1)
        if g % 10 == 0:
            d.text((X + 2, 2), str(g), fill=(255, 0, 255))
    for g in range((box[1] // 5) * 5, box[3] + 1, 5):
        Y = (g - box[1]) * SC + SC // 2
        col = (255, 255, 0) if g % 10 == 0 else (0, 160, 160)
        d.line([(0, Y), (T, Y)], fill=col, width=1)
        if g % 10 == 0:
            d.text((2, Y + 2), str(g), fill=(255, 0, 255))
    cx, cy = n % COLS, n // COLS
    sheet.paste(c, (cx * (T + 6), cy * (T + 22) + 20))
    ImageDraw.Draw(sheet).text((cx * (T + 6) + 4, cy * (T + 22) + 4), f'{lab} ({x},{y})', fill='white')
sheet.save(args[1])
