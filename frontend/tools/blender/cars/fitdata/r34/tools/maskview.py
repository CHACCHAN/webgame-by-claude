"""maskview.py <photo> <mask.png> <out.png> x0 y0 x1 y1 [scale] : photo crop with the mask outline (green, grey = ignore
area outline in cyan) and a labelled 20-px grid, to check a mask and read polygon points for masks.json"""
import sys
import numpy as np
import cv2
from PIL import Image, ImageDraw
ph, mk, out = sys.argv[1:4]
x0, y0, x1, y1 = [int(v) for v in sys.argv[4:8]]
s = float(sys.argv[8]) if len(sys.argv) > 8 else 2.0
o = np.array(Image.open(ph).convert('RGB')).astype(np.uint8)
m = np.array(Image.open(mk).convert('L'))
for sel, col in ((m > 192, (0, 255, 0)), ((m > 64) & (m <= 192), (0, 255, 255))):
    e = sel.astype(np.uint8) - cv2.erode(sel.astype(np.uint8), np.ones((3, 3), np.uint8))
    o[e > 0] = col
im = Image.fromarray(o[y0:y1, x0:x1]).resize((int((x1 - x0) * s), int((y1 - y0) * s)), Image.LANCZOS)
d = ImageDraw.Draw(im)
for x in range((x0 // 20 + 1) * 20, x1, 20):
    d.line([((x - x0) * s, 0), ((x - x0) * s, 6)], fill=(255, 255, 0)); d.text(((x - x0) * s + 1, 7), str(x), fill=(255, 255, 0))
for y in range((y0 // 20 + 1) * 20, y1, 20):
    d.line([(0, (y - y0) * s), (6, (y - y0) * s)], fill=(255, 255, 0)); d.text((7, (y - y0) * s - 5), str(y), fill=(255, 255, 0))
im.save(out)
