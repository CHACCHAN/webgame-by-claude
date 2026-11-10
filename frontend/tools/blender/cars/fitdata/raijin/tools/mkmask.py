"""
mkmask.py: a fixed photo mask for silfit / ffdfit (255 car, 0 not car, 128 ignore), made once per photo and checked.
GrabCut seeded by the model's render (as silfit does), then:
  - ignore where the ground plate round the footprint shows under the model (<name>_gnd.png minus <name>_sil.png from
    loop.py --gnd): the ground shadow under a car is not car, and GrabCut cannot tell;
  - ignore boxes / polygons and forced car / not-car polygons from masks.json.

  $PY mkmask.py <photo> <rdir> <name> <out.png> [--band 0.08] [--spec masks.json] [--sal sal.png]
--sal: a salient-object map of the photo (U2Net type, 0..255, scratch tool sal.py) seeds GrabCut instead of the
render (definite car / background beyond +-6 px of its 0.5 contour); the ground plate is then not used.
masks.json: {name: {"ignore": [[x0,y0,x1,y1]], "grey": [[[x,y],...]], "black": [...], "white": [...], "nognd": false}}
"""
import json, sys

import cv2
import numpy as np
from PIL import Image

photo, rdir, name, out = sys.argv[1:5]
a = sys.argv[5:]
band_f = float(a[a.index('--band') + 1]) if '--band' in a else 0.08
spec = json.load(open(a[a.index('--spec') + 1])).get(name, {}) if '--spec' in a else {}
img = np.array(Image.open(photo).convert('RGB'))
h, w = img.shape[:2]


def alpha(p):
    return np.array(Image.open(p).convert('RGBA').resize((w, h), Image.NEAREST))[:, :, 3] > 127


R = alpha(f'{rdir}/{name}_sil.png')
import os
G = (alpha(f'{rdir}/{name}_gnd.png') & ~R) if os.path.exists(f'{rdir}/{name}_gnd.png') else np.zeros_like(R)
ys, xs = np.nonzero(R)
band = max(4, int(round(band_f * max(np.ptp(xs) + 1, np.ptp(ys) + 1))))
k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * band + 1, 2 * band + 1))
dil = cv2.dilate(R.astype(np.uint8), k).astype(bool)
ero = cv2.erode(R.astype(np.uint8), k).astype(bool)
gc = np.full((h, w), cv2.GC_BGD, np.uint8)
gc[dil] = cv2.GC_PR_BGD
gc[R] = cv2.GC_PR_FGD
gc[ero] = cv2.GC_FGD
if not spec.get('nognd'):
    gc[G & dil] = cv2.GC_PR_BGD
SAL = a[a.index('--sal') + 1] if '--sal' in a else None
if SAL:
    sal = np.array(Image.open(SAL).convert('L').resize((w, h), Image.BILINEAR)) / 255.0
    fg = sal > 0.5
    k6 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (13, 13))
    gc = np.full((h, w), cv2.GC_BGD, np.uint8)
    gc[cv2.dilate(fg.astype(np.uint8), k6) > 0] = cv2.GC_PR_BGD
    gc[fg] = cv2.GC_PR_FGD
    gc[cv2.erode(fg.astype(np.uint8), k6) > 0] = cv2.GC_FGD
    spec = dict(spec, nognd=True)
for poly in spec.get('white', []):
    m = np.zeros((h, w), np.uint8)
    cv2.fillPoly(m, [np.array(poly, np.int32)], 1)
    gc[m > 0] = cv2.GC_FGD
for poly in spec.get('black', []):
    m = np.zeros((h, w), np.uint8)
    cv2.fillPoly(m, [np.array(poly, np.int32)], 1)
    gc[m > 0] = cv2.GC_BGD
bgd = np.zeros((1, 65), np.float64)
fgd = np.zeros((1, 65), np.float64)
cv2.grabCut(cv2.cvtColor(img, cv2.COLOR_RGB2BGR), gc, None, bgd, fgd, 6, cv2.GC_INIT_WITH_MASK)
P = (gc == cv2.GC_FGD) | (gc == cv2.GC_PR_FGD)
n, lab, st, _ = cv2.connectedComponentsWithStats(P.astype(np.uint8), 8)
if n > 1:
    P = lab == 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
inv = (~P).astype(np.uint8)
n2, lab2, st2, _ = cv2.connectedComponentsWithStats(inv, 4)
for j in range(1, n2):
    x, y, ww, hh = st2[j, :4]
    if x > 0 and y > 0 and x + ww < w and y + hh < h:
        P[lab2 == j] = True
M = np.where(P, 255, 0).astype(np.uint8)
ign = np.zeros((h, w), bool)
if not spec.get('nognd'):
    ign |= G
for x0, y0, x1, y1 in spec.get('ignore', []):
    ign[int(y0):int(y1), int(x0):int(x1)] = True
for poly in spec.get('grey', []):
    m = np.zeros((h, w), np.uint8)
    cv2.fillPoly(m, [np.array(poly, np.int32)], 1)
    ign |= m > 0
M[ign] = 128
Image.fromarray(M).save(out)
vis = (img * 0.5).astype(np.uint8)
vis[M == 255] = (vis[M == 255] * 0.5 + np.array([0, 120, 255]) * 0.5).astype(np.uint8)
vis[M == 128] = (vis[M == 128] * 0.5 + np.array([128, 128, 128]) * 0.5).astype(np.uint8)
ol = (R.astype(np.uint8) - cv2.erode(R.astype(np.uint8), np.ones((3, 3), np.uint8))) > 0
vis[cv2.dilate(ol.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0] = (255, 40, 40)
Image.fromarray(vis).save(out.replace('.png', '_vis.png'))
print(name, 'car px', int((M == 255).sum()), 'ignored', int((M == 128).sum()))
