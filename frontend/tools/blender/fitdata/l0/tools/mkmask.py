"""
mkmask.py: a fixed photo mask for the silhouette fit (255 train, 0 not train, 128 ignore), made once per photo and
checked by eye. GrabCut seeded by the model's silhouette from the solved camera (definite train well inside it,
probable train / background in a band round its outline), then the polygons of masks.json:
  "ignore": the guideway's walls and masts in front of the train, the cars beyond the model's three: not scored;
  "white" / "black": forced train / not train (where GrabCut cannot tell white concrete from a white train);
  "near": N: pixels farther than N px from the model's silhouette are not train (once the model is close);
  "seed": a rough outline of the train traced by hand, used in place of the model's silhouette (camera not solved yet).

  py mkmask.py <cams.json> <photo> <workdir> [--spec masks.json] [--band 0.03] [--shape shape.json]
      -> <workdir>/masks/<photo>.png and <workdir>/masks/<photo>_check.jpg
masks.json: {photo: {"ignore": [[[u, v], ...], ...], "white": [...], "black": [...], "clip": [x0, y0, x1, y1]}}
(polygons in the working copy's pixels; "clip": only this box is scored, the rest ignored)
"""
import json, os, sys

import cv2
import numpy as np

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sil

a = sys.argv[1:]


def opt(k, d=None):
    return a[a.index(k) + 1] if k in a else d


cams = json.load(open(a[0]))['cams']
photo, wd = a[1], a[2]
sil.load_shape(opt('--shape'))
spec = json.load(open(opt('--spec'))).get(photo, {}) if opt('--spec') else {}
band_f = float(opt('--band', '0.03'))
c = cams[photo]
W, H = c[7]
img = cv2.imread(os.path.join(wd, 'work', photo + '.jpg'))
if spec.get('seed'):
    R = np.zeros((H, W), np.uint8)
    for p in spec['seed']:
        cv2.fillPoly(R, [np.array(p, np.int32)], 1)
    R = R > 0
else:
    R = sil.raster(c[:7], W, H)
ys, xs = np.nonzero(R)
band = max(3, int(round(band_f * min(np.ptp(xs) + 1, np.ptp(ys) + 1))))
k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * band + 1, 2 * band + 1))
dil = cv2.dilate(R.astype(np.uint8), k) > 0
ero = cv2.erode(R.astype(np.uint8), k) > 0
gc = np.full((H, W), cv2.GC_BGD, np.uint8)
gc[dil] = cv2.GC_PR_BGD
gc[R] = cv2.GC_PR_FGD
gc[ero] = cv2.GC_FGD


def poly_mask(polys):
    m = np.zeros((H, W), np.uint8)
    for p in polys:
        cv2.fillPoly(m, [np.array(p, np.int32)], 1)
    return m > 0


white, black, ign = poly_mask(spec.get('white', [])), poly_mask(spec.get('black', [])), poly_mask(spec.get('ignore', []))
if spec.get('near'):
    nk = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * spec['near'] + 1, 2 * spec['near'] + 1))
    far = cv2.dilate(sil.raster(c[:7], W, H).astype(np.uint8), nk) == 0
    black = black | far
gc[white] = cv2.GC_FGD
gc[black] = cv2.GC_BGD
bg, fg = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
cv2.grabCut(img, gc, None, bg, fg, 6, cv2.GC_INIT_WITH_MASK)
car = (gc == cv2.GC_FGD) | (gc == cv2.GC_PR_FGD)
car = cv2.morphologyEx(car.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)) > 0
out = np.where(car, 255, 0).astype(np.uint8)
out[white] = 255
out[black] = 0
out[ign] = 128
if 'clip' in spec:
    x0, y0, x1, y1 = spec['clip']
    keep = np.zeros((H, W), bool)
    keep[y0:y1, x0:x1] = True
    out[~keep] = 128
os.makedirs(os.path.join(wd, 'masks'), exist_ok=True)
cv2.imwrite(os.path.join(wd, 'masks', photo + '.png'), out)
chk = img.copy()
chk[out == 255] = (chk[out == 255] * 0.5 + np.array([0, 160, 0]) * 0.5).astype(np.uint8)
chk[out == 128] = (chk[out == 128] * 0.5 + np.array([160, 0, 160]) * 0.5).astype(np.uint8)
chk[sil.edge(R)] = (0, 0, 255)
cv2.imwrite(os.path.join(wd, 'masks', photo + '_check.jpg'), chk, [cv2.IMWRITE_JPEG_QUALITY, 85])
r = sil.compare(sil.raster(c[:7], W, H), out)
print(photo, f'IoU {r["iou"]:.4f} p95 {r["p95"]:.2f} max {r["max"]:.1f}')
