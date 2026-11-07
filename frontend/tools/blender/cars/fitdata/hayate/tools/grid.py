"""grid.py <img> <out> [x0,y0,x1,y1] [scale] [step]: crop (work-image px), upscale, draw a labelled grid in work-image px"""
import sys
from PIL import Image, ImageDraw
im = Image.open(sys.argv[1]).convert('RGB')
box = [int(v) for v in sys.argv[3].split(',')] if len(sys.argv) > 3 and sys.argv[3] != '-' else [0, 0, *im.size]
s = float(sys.argv[4]) if len(sys.argv) > 4 else 1.0
step = int(sys.argv[5]) if len(sys.argv) > 5 else 50
c = im.crop(box).resize((int((box[2] - box[0]) * s), int((box[3] - box[1]) * s)), Image.LANCZOS)
d = ImageDraw.Draw(c)
for x in range((box[0] // step + 1) * step, box[2], step):
    X = (x - box[0]) * s
    major = x % (step * 2) == 0
    d.line([(X, 0), (X, c.size[1])], fill=(255, 255, 0) if major else (0, 255, 255), width=1)
    if major:
        d.text((X + 2, 2), str(x), fill=(255, 255, 0))
        d.text((X + 2, c.size[1] - 12), str(x), fill=(255, 255, 0))
for y in range((box[1] // step + 1) * step, box[3], step):
    Y = (y - box[1]) * s
    major = y % (step * 2) == 0
    d.line([(0, Y), (c.size[0], Y)], fill=(255, 255, 0) if major else (0, 255, 255), width=1)
    if major:
        d.text((2, Y + 2), str(y), fill=(255, 255, 0))
        d.text((c.size[0] - 30, Y + 2), str(y), fill=(255, 255, 0))
c.save(sys.argv[2])
