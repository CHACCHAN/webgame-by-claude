"""edges.py <photo> <rdir> <ph> <mask.png> <out.jpg> [mat=#hex ...] [--box x0,y0,x1,y1] [--w 1200]:
the photo with the mask outline (green), the model silhouette (red) and the given materials' outlines from the ids render"""
import json, sys
import cv2
import numpy as np
from PIL import Image
a = sys.argv[1:]
photo, rdir, ph, mask, out = a[:5]
s = np.array(Image.open(f'{rdir}/{ph}_sil.png'))[..., 3]
H, W = s.shape
img = np.array(Image.open(photo).convert('RGB').resize((W, H), Image.LANCZOS))
ids = np.array(Image.open(f'{rdir}/{ph}_ids.png').convert('RGB')).astype(int)
pal = json.load(open(f'{rdir}/palette.json'))


def draw(mm, col):
    e = cv2.Canny(mm.astype(np.uint8) * 255, 50, 150) > 0
    img[cv2.dilate(e.astype(np.uint8), np.ones((2, 2))) > 0] = col


for t in a[5:]:
    if '=' in t and not t.startswith('--'):
        n, c = t.split('=')
        draw(np.abs(ids - pal[n]).sum(-1) < 6, tuple(int(c[i:i + 2], 16) for i in (1, 3, 5)))
if mask != '-':
    m = np.array(Image.open(mask).convert('L').resize((W, H)))
    draw(m > 127, (0, 255, 0))
draw(s > 127, (255, 0, 0))
im = Image.fromarray(img)
if '--box' in a:
    im = im.crop(tuple(int(v) for v in a[a.index('--box') + 1].split(',')))
w = int(a[a.index('--w') + 1]) if '--w' in a else 1200
im.resize((w, round(im.height * w / im.width)), Image.LANCZOS).save(out)
