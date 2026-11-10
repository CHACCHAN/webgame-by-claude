"""holetrace.py: a lamp's outline on a photo as the hole in the paint round it. Inside the box, pixels close to the
paint colour (sampled at --paint x,y [;x,y...] or given as #rrggbb) are paint; the non-paint component holding the seed
is the lamp (holes filled, opened by --open px); its outline, shrunk by --seal px (the dark rubber seal), is written as
a polygon (photo px at the photo's size) into lamps.json [photo][lamp] and drawn on a 4x check crop.

  py holetrace.py <photo> <lamps.json> <photo name> <lamp> <x0,y0,x1,y1> <seed x,y> --paint x,y[;x,y] [--tol 40]
      [--seal 0] [--open 1] [--close 1] [--n 40] [--cut x0,y0,x1,y1 ...] [--keep x0,y0,x1,y1] [--check out.png] [--dry]
--chroma: paint by the chroma's direction (coloured paint under any shading; --tol in degrees, --minc chroma).
--cut boxes (and --cutpoly 'x,y;x,y;...' polygons) are forced to paint (walls off leaks into a grille or gap); --tol is the colour distance (0-255 RGB, in
chroma-weighted Lab-ish space) still counted as paint.
"""
import json, sys

import cv2
import numpy as np
from PIL import Image

a = sys.argv[1:]


def opt(k, d=None):
    return a[a.index(k) + 1] if k in a else d


photo, lj, ph, lamp = a[:4]
x0, y0, x1, y1 = (int(float(v)) for v in a[4].split(','))
sx, sy = (int(float(v)) for v in a[5].split(','))
img = np.array(Image.open(photo).convert('RGB'))
lab = cv2.cvtColor(img, cv2.COLOR_RGB2LAB).astype(float)
P = opt('--paint')
if P.startswith('#'):
    rgb = np.array([[[int(P[i:i + 2], 16) for i in (1, 3, 5)]]], np.uint8)
    refs = [cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB).astype(float)[0, 0]]
else:
    refs = []
    for s in P.split(';'):
        px, py = (int(float(v)) for v in s.split(','))
        refs.append(lab[py - 2:py + 3, px - 2:px + 3].reshape(-1, 3).mean(0))
tol = float(opt('--tol', '40'))
roi = lab[y0:y1, x0:x1]
if '--chroma' in a:
    # coloured paint: the chroma's direction within --tol degrees of the paint's, and at least --minc strong
    ref = np.mean([r[1:] - 128 for r in refs], 0)
    ch = roi[..., 1:] - 128
    mag = np.hypot(ch[..., 0], ch[..., 1])
    cosang = (ch @ ref) / np.maximum(mag * np.hypot(*ref), 1e-6)
    paint = (mag > float(opt('--minc', '12'))) & (cosang > np.cos(np.radians(tol)))
else:
    w = np.array([0.5, 1.0, 1.0])            # lightness counts half (shading on the paint)
    d = np.min([np.sqrt((((roi - r) * w) ** 2).sum(-1)) for r in refs], 0)
    paint = d < tol
for i, t in enumerate(a):
    if t == '--cut':
        c = [int(float(v)) for v in a[i + 1].split(',')]
        paint[max(0, c[1] - y0):max(0, c[3] - y0), max(0, c[0] - x0):max(0, c[2] - x0)] = True
for i, t in enumerate(a):
    if t == '--cutpoly':
        q = np.array([[float(v) for v in p.split(',')] for p in a[i + 1].split(';')]) - [x0, y0]
        cm = np.zeros(paint.shape, np.uint8)
        cv2.fillPoly(cm, [np.round(q).astype(np.int32)], 1)
        paint |= cm > 0
lampm = (~paint).astype(np.uint8)
k = int(opt('--open', '1'))
if k:
    lampm = cv2.morphologyEx(lampm, cv2.MORPH_OPEN, np.ones((2 * k + 1, 2 * k + 1), np.uint8))
k = int(opt('--close', '1'))
if k:
    lampm = cv2.morphologyEx(lampm, cv2.MORPH_CLOSE, np.ones((2 * k + 1, 2 * k + 1), np.uint8))
n, cl = cv2.connectedComponents(lampm)
comp = (cl == cl[sy - y0, sx - x0]).astype(np.uint8)
cs, _ = cv2.findContours(comp, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
c = max(cs, key=cv2.contourArea)
fill = np.zeros_like(comp)
cv2.drawContours(fill, [c], -1, 1, -1)
seal = int(opt('--seal', '0'))
if seal:
    fill = cv2.erode(fill, np.ones((2 * seal + 1, 2 * seal + 1), np.uint8))
cs, _ = cv2.findContours(fill, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
c = max(cs, key=cv2.contourArea)[:, 0, :].astype(float) + 0.5
# resample to N points evenly along the outline
N = int(opt('--n', '40'))
seg = np.r_[0, np.cumsum(np.hypot(*np.diff(np.vstack([c, c[:1]]), axis=0).T))]
t = np.linspace(0, seg[-1], N, endpoint=False)
cc = np.vstack([c, c[:1]])
poly = np.stack([np.interp(t, seg, cc[:, 0]), np.interp(t, seg, cc[:, 1])], 1) + [x0, y0]
print(f'{ph} {lamp}: {len(poly)} pts, bbox {poly[:, 0].min():.0f}..{poly[:, 0].max():.0f} x {poly[:, 1].min():.0f}..{poly[:, 1].max():.0f}')
if '--dry' not in a:
    db = json.load(open(lj))
    db.setdefault('photos', {}).setdefault(ph, {})[lamp] = {'poly': [[round(float(u), 2), round(float(v), 2)] for u, v in poly],
                                                           'how': 'holetrace ' + ' '.join(a[4:])}
    json.dump(db, open(lj, 'w'), indent=1)
chk = opt('--check')
if chk:
    S = 4
    crop = cv2.resize(img[y0:y1, x0:x1], ((x1 - x0) * S, (y1 - y0) * S), interpolation=cv2.INTER_CUBIC)
    pm = cv2.resize(paint.astype(np.uint8), ((x1 - x0) * S, (y1 - y0) * S), interpolation=cv2.INTER_NEAREST)
    tint = crop.copy()
    tint[pm > 0] = (0.6 * tint[pm > 0] + 0.4 * np.array([0, 160, 255])).astype(np.uint8)
    q = np.round((poly - [x0, y0]) * S).astype(np.int32)
    cv2.polylines(tint, [q], True, (0, 255, 0), 1, cv2.LINE_AA)
    cv2.polylines(crop, [q], True, (0, 255, 0), 1, cv2.LINE_AA)
    Image.fromarray(np.concatenate([crop, np.full((crop.shape[0], 6, 3), 255, np.uint8), tint], 1)).save(chk)
